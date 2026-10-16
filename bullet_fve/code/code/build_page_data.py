#!/usr/bin/env python3
"""Build the Bullet FVE Explorer page data (WorkspaceBench "Hallucination (chat)", three O-lens settings).

Writes ONLY under --out (default ${OLENS_SCRATCH}/olens-bullet-fve/page/data):
  index.json             meta + items + one compact row per cell (5,615)
  items/<item_id>.json   chat, read sites and every cell's readouts, bullets, judge spans and claims
  summary.json           definitions + descriptive statistics (provisional; the merge stage may replace it)
  heat/<item_id>.json    only with --heat

All character offsets written to the page data are JavaScript string indices (UTF-16 code units), so
`text.slice(start, end)` in the browser returns the exact characters. Python code points are used
internally and converted at write time (54 of 149 chats and many readouts contain emoji).

Usage:
  PYTHONPATH=<olens-improve>/src python -B build_page_data.py --generated 2026-10-15 \
      [--metrics metrics/bullet_metrics.jsonl] [--heat heat/heat.jsonl] [--out page/data]

Read-only inputs: the slim extract (inputs/hall_three_settings.jsonl), the judgment folders
(results.json + cells.jsonl, stage 1 and ':V' stage 2), the expansion chosen-text file (raw_n1 reference
text), the benchmark bank items.json and the AR tokenizer (for the 32-token scoring boundary).
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hall_judge_context import (BANK, EXP, judge_key, load_judgments, normalize_ws,  # noqa: E402
                                tally_claim_list, verify_quote)
from span_locate import _norm_with_map  # noqa: E402

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
SLIM = ROOT / 'inputs/hall_three_settings.jsonl'
CACHED_V2 = EXP / 'selections/cached-v2/hallucination.jsonl'
TOKENIZER = ('${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/'
             '6a9e13bd6fc8f0983b9b99948120bc37f49c13e9')
SETTINGS = [
    {'id': 'capped_n1-n1', 'label': 'Original, capped to four bullets', 'short': 'Original'},
    {'id': 'best_n_exact-n32', 'label': 'Choose the best complete readout (32 samples)', 'short': 'Best of 32'},
    {'id': 'pooled_greedy_swap-n32', 'label': 'Combine original bullets (32 samples)', 'short': 'Combine 32'},
]
SIDS = [s['id'] for s in SETTINGS]
REF_ID = 'raw_n1-n1'
REF_SELECTION = ('raw_n1', 1)
LAYERS = [20, 36, 44, 52, 60]
SPLITS = ['development', 'validation', 'test']
LABEL_CODES = ['consistent', 'hallucinated', 'off_topic', 'generic', 'empty']   # index = code
CODE = {k: i for i, k in enumerate(LABEL_CODES)}
SPECIFIC = ('hallucinated', 'consistent', 'off_topic')
AR_SPAN_LIMIT = 32


# ----------------------------------------------------------------------------- helpers
def rnd(x, d=5):
    """Round to d decimals; None/NaN -> None; never emit -0.0."""
    if x is None:
        return None
    x = float(x)
    if math.isnan(x) or math.isinf(x):
        return None
    v = round(x, d)
    return 0.0 if v == 0 else v


def rnd_sum(xs, total, d=5):
    """Round non-negative parts to d decimals so that they add up to round(total, d) exactly
    (largest-remainder rounding). Used for Shapley values (sum = joint FVE) and Shapley shares
    (sum = 1), so the page never shows parts that disagree with their total by a rounding residue.
    Falls back to plain rounding if a part is missing or the remainder cannot be distributed."""
    if not xs or total is None or any(x is None for x in xs):
        return [rnd(x, d) for x in xs]
    scale = 10 ** d
    vals = [max(0.0, float(x)) * scale for x in xs]
    target = round(float(total) * scale)
    base = [math.floor(v) for v in vals]
    k = target - sum(base)
    if not 0 <= k <= len(xs):
        return [rnd(x, d) for x in xs]
    order = sorted(range(len(xs)), key=lambda j: (-(vals[j] - base[j]), j))
    for j in order[:k]:
        base[j] += 1
    return [rnd(b / scale, d) for b in base]


class U16:
    """Python code-point offsets -> UTF-16 code-unit offsets for one string."""
    __slots__ = ('m',)

    def __init__(self, text):
        m = [0]
        for ch in text:
            m.append(m[-1] + (2 if ord(ch) > 0xFFFF else 1))
        self.m = m

    def __call__(self, o):
        return self.m[o]


def locate_all(text, span):
    """Every occurrence of a judge span in text as sorted [(start, end)] (code points).
    Exact str.find hits first, then normalize_ws hits (case / whitespace / quote marks, the judge's
    own verification rule) that do not overlap an exact hit. Returns (hits, n_exact, n_normalized)."""
    exact = []
    if span:
        i = text.find(span)
        while i != -1:
            exact.append((i, i + len(span)))
            i = text.find(span, i + 1)
    norm_hits = []
    q = normalize_ws(span or '')
    if len(q) >= 3:
        norm, idx = _norm_with_map(text)
        j = norm.find(q)
        while j != -1:
            s, e = idx[j], idx[j + len(q) - 1] + 1
            if not any(s < b and e > a for a, b in exact):
                norm_hits.append((s, e))
            j = norm.find(q, j + 1)
    hits = sorted(set(exact) | set(norm_hits))
    return hits, len(exact), len(norm_hits)


def overlapped(bullets, s, e):
    """Indices of bullets whose content range [start, end) overlaps [s, e)."""
    return [k for k, b in enumerate(bullets) if s < b['_end'] and e > b['_start']]


def render(atoms):
    """Mirror of olens_improve.selection.render_bullets; returns (text, [(content_start, raw_end)])."""
    out, spans = '', []
    for a in atoms:
        if out and not out.endswith('\n'):
            out += '\n'
        out += '- '
        spans.append((len(out), len(out) + len(a['text'])))
        out += a['text']
    return out, spans


def lcp(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    os.replace(tmp, path)
    return path.stat().st_size


def cell_key(item_id, layer, pos):
    return f'{item_id}.L{layer}.p{pos}'


_CID = re.compile(r'^hallucination\|(?P<item>[a-z0-9-]+)\|L(?P<layer>\d+)\|p(?P<pos>\d+)$')
_K = re.compile(r'^(?P<item>[a-z0-9-]+)\.L(?P<layer>\d+)\.p(?P<pos>\d+)$')


def parse_cell(cid):
    m = _CID.match(cid) or _K.match(cid)
    if not m:
        raise ValueError(f'unrecognised cell id {cid!r}')
    return m['item'], int(m['layer']), int(m['pos'])


# ----------------------------------------------------------------------------- scored boundary
class ScoredBoundary:
    """Char offset (code points, within scored_text) where AR scoring stops for a truncated atom.

    AR scores ar_token_ids(scored_text)[:32]. The boundary is the longest common prefix of
    tokenizer.decode(scored_token_ids) and scored_text. For 4,432 truncated atoms this equals
    offset_mapping[31][1]; for 30 atoms a multi-byte character is cut between token 32 and 33 and the
    decode ends in U+FFFD, so the cut character is treated as unscored (conservative boundary)."""

    def __init__(self):
        from transformers import AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)
        self.special = set(self.tok.all_special_ids)
        self.stats = collections.Counter()

    def __call__(self, atom):
        st = atom['scored_text']
        enc = self.tok(st, add_special_tokens=False, return_offsets_mapping=True)
        pairs = [(i, o) for i, o in zip(enc['input_ids'], enc['offset_mapping']) if i not in self.special]
        ids = [i for i, _ in pairs]
        assert ids[:AR_SPAN_LIMIT] == atom['scored_token_ids'], atom['source_phrase_id']
        assert ids[AR_SPAN_LIMIT:] == atom['unscored_suffix_ids'], atom['source_phrase_id']
        dec = self.tok.decode(atom['scored_token_ids'])
        cut = lcp(dec, st)
        if st.startswith(dec):
            assert cut == pairs[AR_SPAN_LIMIT - 1][1][1], atom['source_phrase_id']
            self.stats['clean_boundary'] += 1
        else:
            self.stats['multibyte_split_boundary'] += 1
        assert 0 < cut < len(st), atom['source_phrase_id']
        return cut


# ----------------------------------------------------------------------------- inputs
def load_bank():
    items = json.loads(BANK.read_text())['items']
    return {it['id']: it for it in items}


def load_raw_reference_text():
    out = {}
    with open(CACHED_V2) as fh:
        for line in fh:
            r = json.loads(line)
            for s in r['selections']:
                if (s['method'], s['n']) == REF_SELECTION:
                    out[(r['item_id'], r['layer'], r['position'])] = s
    return out


def judged_available(sid):
    base = EXP / 'judgments' / sid / 'hallucination'
    return (base / 'results.json').is_file() and (base / 'cells.jsonl').is_file()


def load_metrics(path):
    """cell_id -> {setting: {'joint': recomputed joint FVE, 'bullets': [{phrase_id, solo, drop, shap, share, coef}]}}.
    Accepts compute_bullet_metrics.py output (solo_fve / loo_drop / shapley / coefficient) and the
    short names (solo / drop / shap / shap_share)."""
    def g(d, *names):
        for n in names:
            if n in d and d[n] is not None:
                return d[n]
        return None
    out = {}
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            cid = r['cell_id']
            if not cid.startswith('hallucination|'):
                it, ly, ps = parse_cell(cid)
                cid = f'hallucination|{it}|L{ly:02d}|p{ps:05d}'
            rec = {}
            for sid, s in (r.get('settings') or {}).items():
                joint = g(s, 'joint_fve_recomputed', 'joint_fve')
                bl = []
                for b in s.get('bullets') or []:
                    shap = g(b, 'shapley', 'shap')
                    share = g(b, 'shapley_share', 'shap_share')
                    if share is None and shap is not None and joint:
                        share = shap / joint if joint > 0 else None
                    bl.append({'phrase_id': b.get('phrase_id'), 'solo': g(b, 'solo_fve', 'solo'),
                               'drop': g(b, 'loo_drop', 'drop'), 'shap': shap, 'share': share,
                               'coef': g(b, 'coefficient', 'coef')})
                rec[sid] = {'joint': joint, 'saved': s.get('joint_fve_saved'), 'bullets': bl}
            out[cid] = rec
    return out


def load_heat(path):
    """(cell_id, setting) -> {bullet: {ends_in_scored_text, heat, solo}}"""
    out = collections.defaultdict(dict)
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            it, ly, ps = parse_cell(r['cell_id'])
            out[(f'hallucination|{it}|L{ly:02d}|p{ps:05d}', r['setting'])][int(r['bullet'])] = r
    return out


# ----------------------------------------------------------------------------- per readout
def judge_record(text, key, J, stats, tag):
    """Label, spans and claims for one judged readout (offsets still in code points until u16())."""
    res, rows, s1, s2, _ = J
    row = rows.get(key)
    if row is None:
        assert not text.strip(), (tag, key, 'non-empty readout without a judge row')
        return None
    assert row['samples'][0] == text, (tag, key, 'judged text != selected text')
    ver = row['verdict'][0]
    raw1 = s1[key]['result']['samples'][0]
    raw2 = s2[key]['result']['samples'][0]
    spans = []
    for sp in raw1.get('spans') or []:
        stext = sp.get('text') or ''
        typ = 'off_topic' if sp.get('type') == 'off_topic' else 'wrong'
        hits, nx, nn = locate_all(text, stext)
        verified = verify_quote(stext, [text])
        stats[f'{tag}:spans'] += 1
        stats[f'{tag}:spans_verified_{typ}'] += verified
        if verified and not hits:
            stats[f'{tag}:verified_span_unlocated'] += 1
        if verified and nn:
            stats[f'{tag}:verified_span_occurrences_added_by_normalisation'] += nn
        spans.append({'text': stext, 'type': typ, 'why': sp.get('why'), 'verified': verified, '_hits': hits})
    # The verified spans reproduce results.json exactly (wrong / off_topic lists, raw order).
    assert [s['text'] for s in spans if s['verified'] and s['type'] == 'wrong'] == ver['wrong'], (tag, key)
    assert [s['text'] for s in spans if s['verified'] and s['type'] == 'off_topic'] == ver['off_topic'], (tag, key)
    claims = []
    for cl in tally_claim_list(raw2, text, ver['wrong']):
        hits, _, _ = locate_all(text, str(cl.get('quote') or ''))
        claims.append({'quote': cl.get('quote'), 'status': cl.get('status'), 'counted_as': cl['counted_as'],
                       'why': cl.get('why'), '_hits': hits})
    c = collections.Counter(x['counted_as'] for x in claims)
    mine = {'false': len(ver['wrong']), 'true': c['true'], 'unverifiable': c['unverifiable'] + c['disputed'],
            'disputed': c['disputed'], 'off_topic': c['off_topic'], 'n_unverified': c['n_unverified']}
    assert mine == ver['claims'], (tag, key, mine, ver['claims'])
    return {'label': ver['class'], 'judge_kind': ver['kind'], 'rationale': raw1.get('rationale'),
            'verify_rationale': raw2.get('rationale'), 'spans': spans, 'claims': claims,
            'claim_tally': ver['claims'], 'n_wrong': len(ver['wrong']), 'n_off': len(ver['off_topic'])}


def finish_spans(spans, bullets, u16, with_bullets=True):
    out = []
    for s in spans:
        r = {'text': s['text'], 'type': s['type'], 'why': s['why'], 'verified': s['verified'],
             'offsets': [[u16(a), u16(b)] for a, b in s['_hits']]}
        if with_bullets:
            occ_bullets = [overlapped(bullets, a, b) for a, b in s['_hits']]
            r['bullets'] = sorted({k for ob in occ_bullets for k in ob})
            unscored = []
            for (a, b), ob in zip(s['_hits'], occ_bullets):
                unscored.append(bool(ob) and all(max(a, bullets[k]['_start']) >= bullets[k]['_scored_end'] for k in ob))
            r['in_unscored'] = bool(unscored) and all(unscored)
        out.append(r)
    return out


def finish_claims(claims, bullets, u16, with_bullets=True):
    out = []
    for c in claims:
        r = {'quote': c['quote'], 'status': c['status'], 'counted_as': c['counted_as'], 'why': c['why'],
             'offsets': [[u16(a), u16(b)] for a, b in c['_hits']]}
        if with_bullets:
            r['bullets'] = sorted({k for a, b in c['_hits'] for k in overlapped(bullets, a, b)})
        out.append(r)
    return out


def build_setting(cell, sid, J, metrics_rec, boundary, stats):
    s = cell['settings'][sid]
    text, atoms = s['text'], s['atoms']
    tag = sid
    rendered, rspans = render(atoms)
    assert rendered == text, (cell['cell_id'], sid, 'render mismatch')
    u16 = U16(text)
    # ---- bullets (code points internally)
    bullets = []
    keys = [a['cache_key'] for a in atoms]
    cleaned = [a['scored_text'] for a in atoms]
    for j, (a, (cs, raw_end)) in enumerate(zip(atoms, rspans)):
        st = a['scored_text']
        assert st == a['text'].strip() and a['text'] == a['text'].lstrip(), (cell['cell_id'], sid, j)
        start, end = cs, cs + len(st)
        assert text[start:end] == st and end <= raw_end
        if a['truncated']:
            scored_end = start + boundary(a)
            stats[f'{tag}:bullets_truncated'] += 1
        else:
            assert len(a['scored_token_ids']) == a['original_token_count'] <= AR_SPAN_LIMIT
            scored_end = end
        dup = keys.count(a['cache_key']) > 1 or cleaned.count(st) > 1
        stats[f'{tag}:bullets'] += 1
        bullets.append({'_start': start, '_end': end, '_scored_end': scored_end, 'truncated': bool(a['truncated']),
                        'sample_index': a['sample_index'], 'coef': s['coefficients'][j], 'dup': dup,
                        'phrase_id': a['source_phrase_id']})
    if any(b['dup'] for b in bullets):
        stats[f'{tag}:readouts_with_dup'] += 1
    # ---- metrics
    m = (metrics_rec or {}).get(sid)
    if m is not None:
        assert [b['phrase_id'] for b in m['bullets']] in ([b['phrase_id'] for b in bullets], [None] * len(bullets)), \
            (cell['cell_id'], sid, 'metrics bullet order differs from atoms')
        if m.get('saved') is not None:
            assert abs(m['saved'] - s['fve']) < 1e-12, (cell['cell_id'], sid)
        if m['joint'] is not None:
            stats[f'{tag}:max_abs_fve_recomputed_minus_saved_e9'] = max(
                stats[f'{tag}:max_abs_fve_recomputed_minus_saved_e9'], round(abs(m['joint'] - s['fve']) * 1e9))
        stats[f'{tag}:readouts_with_metrics'] += 1
    for j, b in enumerate(bullets):
        mb = m['bullets'][j] if m is not None else {}
        b.update(solo=mb.get('solo'), drop=mb.get('drop'), shap=mb.get('shap'), shap_share=mb.get('share'))
    # ---- judge
    jr = judge_record(text, judge_key(cell['item_id'], cell['layer'], cell['position']), J, stats, tag)
    label = jr['label'] if jr else None
    stats[f'{tag}:label_{label or "empty"}'] += 1
    for b in bullets:
        if label in SPECIFIC:
            def hit(kind):
                return any(sp['verified'] and sp['type'] == kind and a < b['_end'] and e > b['_start']
                           for sp in jr['spans'] for a, e in sp['_hits'])
            b['label'] = 'w' if hit('wrong') else ('o' if hit('off_topic') else 'c')
        else:
            b['label'] = 'x'
        stats[f'{tag}:bullet_label_{b["label"]}'] += 1
    if label == 'hallucinated' and not any(b['label'] == 'w' for b in bullets):
        stats[f'{tag}:hallucinated_without_w_bullet'] += 1
    # Shapley values / shares rounded so they add up exactly to the shown joint FVE / to 1.
    have_m = m is not None and bullets and all(b['shap'] is not None for b in bullets)
    fve_shown = rnd(s['fve'])
    sh5 = rnd_sum([b['shap'] for b in bullets], fve_shown, 5) if have_m else [rnd(b['shap']) for b in bullets]
    pos_fve = have_m and fve_shown and fve_shown > 0
    ss5 = rnd_sum([b['shap_share'] for b in bullets], 1.0, 5) if pos_fve else [rnd(b['shap_share']) for b in bullets]
    ss4 = rnd_sum([b['shap_share'] for b in bullets], 1.0, 4) if pos_fve else \
        [rnd(b['shap_share'], 4) for b in bullets]
    out_bullets = [{'start': u16(b['_start']), 'end': u16(b['_end']), 'scored_end': u16(b['_scored_end']),
                    'truncated': b['truncated'], 'sample_index': b['sample_index'], 'coef': rnd(b['coef'], 4),
                    'solo': rnd(b['solo']), 'drop': rnd(b['drop']), 'shap': sh5[j],
                    'shap_share': ss5[j], 'dup': b['dup'], 'label': b['label']} for j, b in enumerate(bullets)]
    rec = {'text': text, 'fve': rnd(s['fve']), 'fve_recomputed': rnd(m['joint']) if m is not None else None,
           'label': label, 'judge_kind': jr['judge_kind'] if jr else None,
           'rationale': jr['rationale'] if jr else None, 'verify_rationale': jr['verify_rationale'] if jr else None,
           'bullets': out_bullets,
           'spans': finish_spans(jr['spans'], bullets, u16) if jr else [],
           'claims': finish_claims(jr['claims'], bullets, u16) if jr else [],
           'claim_tally': jr['claim_tally'] if jr else None}
    if sid == 'best_n_exact-n32':
        tr = s['trace']
        scores = [None] * 32
        for t in tr:
            scores[int(t['sample_id'].rsplit(':', 1)[1])] = rnd(t.get('score'))
        chosen = sorted({a['sample_index'] for a in atoms})
        assert len(chosen) <= 1
        rec['trace'] = {'chosen_sample': chosen[0] if chosen else None, 'scores': scores}
    for sp in rec['spans']:
        if sp['verified']:
            stats[f'{tag}:verified_spans_in_unscored_only'] += sp['in_unscored']
    compact = {'c': CODE[label or 'empty'], 'f': rnd(s['fve']), 'n': len(bullets),
               'w': jr['n_wrong'] if jr else 0, 'o': jr['n_off'] if jr else 0,
               'sh': sh5 if m is not None else None,
               'ss': ss4 if m is not None else None,
               'so': [rnd(b['solo'], 4) for b in bullets] if m is not None else None,
               'dr': [rnd(b['drop'], 4) for b in bullets] if m is not None else None,
               'bl': [b['label'] for b in bullets]}
    return rec, compact, bullets


def build_reference(cell, ref_sel, J, stats):
    text = ref_sel['text']
    jr = judge_record(text, judge_key(cell["item_id"], cell["layer"], cell["position"]), J, stats, REF_ID)
    u16 = U16(text)
    label = jr['label'] if jr else None
    stats[f'{REF_ID}:label_{label or "empty"}'] += 1
    rec = {'text': text, 'label': label,
           'spans': finish_spans(jr['spans'], [], u16, with_bullets=False) if jr else [],
           'claims': finish_claims(jr['claims'], [], u16, with_bullets=False) if jr else []}
    return rec, CODE[label or 'empty']


# ----------------------------------------------------------------------------- summary
def mean(xs):
    xs = [x for x in xs if x is not None]
    return rnd(statistics.fmean(xs)) if xs else None


def build_summary(rows, metrics_on, ref_available, generated):
    """rows: list of dicts {split, layer, site_kind, sid, label, fve, bullets:[{label, solo, drop, shap, shap_share, truncated, dup}]}"""
    by = collections.defaultdict(list)
    for r in rows:
        by[r['sid']].append(r)

    def label_block(rs):
        c = collections.Counter(r['label'] or 'empty' for r in rs)
        spec = sum(c[k] for k in SPECIFIC)
        return {'n': len(rs), 'counts': {k: c[k] for k in LABEL_CODES},
                'hallucinated_rate_of_specific': rnd(c['hallucinated'] / spec) if spec else None,
                'mean_joint_fve': mean(r['fve'] for r in rs if r['sid'] != REF_ID)}

    out = {'generated': generated, 'provisional': True,
           'scope': 'Exploratory description of all 5,615 cells. All 149 chats were inspected before this '
                    'analysis, so no split (including test) is a fresh held-out test.',
           'definitions': {
               'joint_fve': 'Joint fraction of variance explained: whiten the target activation and each bullet\'s AR '
                            'vector (per-layer pooled whitener, ridge 0.1), unit-normalise the bullet vectors, fit '
                            'non-negative least squares (scipy NNLS); FVE = 1 - |residual|^2 / |target|^2. The value '
                            'shown is the saved project value (fits.exact).',
               'solo': 'FVE of the bullet fitted alone.',
               'drop': 'Joint FVE minus the FVE of the readout refitted without this bullet (leave-one-out).',
               'shap': 'Exact Shapley value of the bullet over the readout\'s bullets with v(empty) = 0; the values of '
                       'one readout sum to its joint FVE.',
               'shap_share': 'shap / joint FVE: the bullet\'s share of the readout\'s FVE.',
               'scored_end': 'The AR model scores only the first 32 tokens of a bullet; characters at or after '
                             'scored_end do not affect any FVE number. For 30 bullets a multi-byte character is cut '
                             'by the 32-token limit; that character is counted as unscored.',
               'dup': 'Bullet has the same cleaned text (same AR vector) as another bullet in the readout; NNLS '
                      'coefficients are then not unique and Shapley credit is split equally.',
               'label': 'Readout label from the project judge (GPT-6 Luna, v5c-chat): hallucinated = at least one '
                        'verified wrong span; generic = judge kind generic/empty; off_topic = verified off-topic span '
                        'and no wrong span; consistent otherwise. Ground truth is the model\'s own reply.',
               'bullet_label': 'In hallucinated/consistent/off_topic readouts: w = overlaps an occurrence of a verified '
                               'wrong span, o = overlaps a verified off-topic span (and no wrong span), c = neither. '
                               'x = generic or empty readout.',
               'verified_span': 'A judge span counts only if its normalised text (whitespace, quote marks, case) '
                                'occurs in the readout and is at least 3 characters (benchmark rule).',
               'offsets': 'All offsets are JavaScript string indices (UTF-16 code units).',
           },
           'settings': {}}
    for sid, rs in by.items():
        blk = {'all': label_block(rs),
               'by_split': {sp: label_block([r for r in rs if r['split'] == sp]) for sp in SPLITS},
               'by_layer': {str(L): label_block([r for r in rs if r['layer'] == L]) for L in LAYERS}}
        if sid != REF_ID:
            blk['mean_joint_fve_by_label'] = {lab: mean(r['fve'] for r in rs if (r['label'] or 'empty') == lab)
                                              for lab in LABEL_CODES}
            bl = [b for r in rs for b in r['bullets']]
            blk['bullets'] = {'n': len(bl), 'by_label': dict(collections.Counter(b['label'] for b in bl)),
                              'truncated': sum(b['truncated'] for b in bl), 'dup': sum(b['dup'] for b in bl)}
            if metrics_on:
                blk['bullet_scores_by_label'] = {
                    lab: {'n': sum(1 for b in bl if b['label'] == lab),
                          **{f'mean_{k}': mean(b[k] for b in bl if b['label'] == lab)
                             for k in ('solo', 'drop', 'shap', 'shap_share')}}
                    for lab in ('w', 'o', 'c', 'x')}
        out['settings'][sid] = blk
    out['reference_available'] = ref_available
    return out


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(ROOT / 'page/data'))
    ap.add_argument('--generated', required=True, help='date string written to meta.generated')
    ap.add_argument('--metrics', default=None, help='bullet_metrics.jsonl (optional)')
    ap.add_argument('--heat', default=None, help='per-token heat JSONL (optional)')
    ap.add_argument('--heat-no-solo', action='store_true', help='leave the per-token solo FVE out of heat/ files')
    ap.add_argument('--limit-items', type=int, default=None, help='debug: only the first N items (sorted)')
    args = ap.parse_args()
    t0 = time.time()
    out = Path(args.out)
    assert str(out.resolve()).startswith(str(ROOT)), 'refusing to write outside the project scratch folder'

    bank = load_bank()
    metrics = load_metrics(args.metrics) if args.metrics else {}
    heat = load_heat(args.heat) if args.heat else None
    J = {sid: load_judgments(sid) for sid in SIDS}
    ref_available = judged_available(REF_ID)
    Jref = load_judgments(REF_ID) if ref_available else None
    ref_text = load_raw_reference_text() if ref_available else {}
    boundary = ScoredBoundary()
    print(f'loaded inputs in {time.time() - t0:.1f}s', flush=True)

    cells_by_item = collections.defaultdict(list)
    with open(SLIM) as fh:
        for line in fh:
            c = json.loads(line)
            cells_by_item[c['item_id']].append(c)
    item_ids = sorted(cells_by_item)
    if args.limit_items:
        item_ids = item_ids[:args.limit_items]
    split_of = {}
    for iid in item_ids:
        sp = {c['split'] for c in cells_by_item[iid]}
        assert len(sp) == 1, iid
        split_of[iid] = sp.pop()

    stats = collections.Counter()
    index_items, index_cells, summary_rows = [], [], []
    item_sizes = {}
    ref_same_as_capped = 0
    heat_written = collections.Counter()
    for ii, iid in enumerate(item_ids):
        it = bank[iid]
        resp_u16 = U16(it['response'])
        sites = {int(s['pos']): s for s in it['sites']}
        prompt_short = re.sub(r'\s+', ' ', it['prompt']).strip()
        prompt_short = prompt_short if len(prompt_short) <= 140 else prompt_short[:139].rstrip() + '…'
        index_items.append({'id': iid, 'source': it['source'], 'split': split_of[iid], 'prompt_short': prompt_short})
        item_out = {'item': {'id': iid, 'source': it['source'], 'split': split_of[iid], 'prompt': it['prompt'],
                             'response': it['response'],
                             'sites': [{'pos': int(s['pos']), 'token': s['token'], 'kind': s['kind'],
                                        'char': resp_u16(int(s['char']))} for s in it['sites']]},
                    'cells': {}}
        heat_out = {}
        for c in sorted(cells_by_item[iid], key=lambda c: (c['position'], c['layer'])):
            layer, pos = c['layer'], c['position']
            site = sites[pos]
            resp = it['response']
            ch = int(site['char'])
            assert resp[:ch].endswith(site['token']) and site['token'] == c['token'], c['cell_id']
            k = cell_key(iid, layer, pos)
            settings_out, compact = {}, []
            mrec = metrics.get(c['cell_id']) if metrics else None
            if metrics and mrec is None:
                stats['cells_missing_metrics'] += 1
            internal_bullets = {}
            for sid in SIDS:
                rec, comp, bl = build_setting(c, sid, J[sid], mrec, boundary, stats)
                settings_out[sid] = rec
                compact.append(comp)
                internal_bullets[sid] = bl
                summary_rows.append({'split': c['split'], 'layer': layer, 'sid': sid, 'label': rec['label'],
                                     'fve': c['settings'][sid]['fve'],
                                     'bullets': [{'label': b['label'], 'truncated': b['truncated'], 'dup': b['dup'],
                                                  'solo': b['solo'], 'drop': b['drop'], 'shap': b['shap'],
                                                  'shap_share': b['shap_share']} for b in bl]})
            r_code = None
            if ref_available:
                ref_rec, r_code = build_reference(c, ref_text[(iid, layer, pos)], Jref, stats)
                settings_out[REF_ID] = ref_rec
                ref_same_as_capped += ref_rec['text'] == settings_out['capped_n1-n1']['text']
                summary_rows.append({'split': c['split'], 'layer': layer, 'sid': REF_ID, 'label': ref_rec['label'],
                                     'fve': None, 'bullets': []})
            item_out['cells'][k] = {'layer': layer, 'pos': pos, 'site_kind': site['kind'], 'char': resp_u16(ch),
                                    'settings': settings_out}
            index_cells.append({'k': k, 'i': ii, 'L': layer, 'p': pos, 'sk': site['kind'], 'st': site['token'],
                                's': compact, 'r': r_code})
            if heat is not None:
                hk = {}
                for sid in SIDS:
                    text = c['settings'][sid]['text']
                    u16 = U16(text)
                    per = []
                    for j, b in enumerate(internal_bullets[sid]):
                        h = heat.get((c['cell_id'], sid), {}).get(j)
                        if h is None:
                            per.append(None)
                            continue
                        ends = [b['_start'] + int(e) for e in h['ends_in_scored_text']]
                        assert len(ends) == len(h['heat']) == len(h['solo']) > 0, (k, sid, j)
                        assert ends == sorted(ends) and b['_start'] <= ends[0], (k, sid, j)
                        assert ends[-1] == b['_scored_end'] <= b['_end'], (k, sid, j, ends[-1], b['_scored_end'])
                        # A character split across tokens belongs to the later token, so some tokens have an empty
                        # piece (e.g. the leading byte tokens of an emoji). The page cannot show an empty piece, so it
                        # is merged into the next non-empty piece (into the previous one when it ends the scored
                        # text): heat adds up (sum unchanged), solo is that of the group's last token.
                        me, mh, ms, acc, pend = [], [], [], 0.0, 0
                        for e, x, s_ in zip(ends, h['heat'], h['solo']):
                            acc += x
                            pend += 1
                            if e > (me[-1] if me else b['_start']):
                                me.append(e)
                                mh.append(acc)
                                ms.append(s_)
                                heat_written['empty_pieces_merged'] += pend - 1
                                acc, pend = 0.0, 0
                        if pend:
                            assert me, (k, sid, j, 'no non-empty piece')
                            mh[-1] += acc
                            ms[-1] = h['solo'][-1]
                            heat_written['empty_pieces_merged'] += pend
                            heat_written['bullets_with_trailing_empty_piece'] += 1
                        hb = {'ends': [u16(e) for e in me], 'heat': [rnd(x) for x in mh]}
                        if not args.heat_no_solo:
                            hb['solo'] = [rnd(x) for x in ms]
                        per.append(hb)
                        heat_written['bullets'] += 1
                        heat_written['tokens_in'] += len(ends)
                        heat_written['pieces_out'] += len(me)
                    if any(x is not None for x in per):
                        hk[sid] = per
                if hk:
                    heat_out[k] = hk
        item_sizes[iid] = write_json(out / 'items' / f'{iid}.json', item_out)
        if heat_out:
            write_json(out / 'heat' / f'{iid}.json', heat_out)
            heat_written['files'] += 1
        if (ii + 1) % 25 == 0:
            print(f'  {ii + 1}/{len(item_ids)} items, {time.time() - t0:.1f}s', flush=True)

    if heat is not None:
        heat_lines = sum(len(v) for v in heat.values())
        assert heat_written['bullets'] == heat_lines, (heat_written, heat_lines, 'heat lines that match no bullet')
    site_kinds = [k for k, _ in collections.Counter(c['sk'] for c in index_cells).most_common()]
    ref_note = ('The released Oracle Lens output before it was capped to four bullets and 256 tokens, judged by the '
                'same project judge. It has no FVE numbers (its text is not restricted to the scored bullets). '
                f'Its text is identical to "Original, capped to four bullets" in {ref_same_as_capped:,} of '
                f'{len(index_cells):,} cells.') if ref_available else \
        'No judged output for the original released Oracle Lens was found for this family.'
    meta = {
        'family': 'Hallucination (chat)',
        'settings': SETTINGS,
        'reference': {'id': REF_ID, 'label': 'Original released Oracle Lens (raw output)', 'available': ref_available,
                      'note': ref_note},
        'layers': LAYERS, 'splits': SPLITS, 'site_kinds': site_kinds,
        'judge': 'Project judge: GPT-6 Luna, prompt v5c-chat (stage 2: v5c-chat-verify-v1)',
        'heat_available': heat is not None,
        'metrics_available': bool(metrics),
        'generated': args.generated,
        'label_codes': LABEL_CODES,
        'offset_units': 'utf16',
        'notes': [
            'Exploratory: all 149 chats (and every question in the project) were inspected before this analysis. '
            'No split, including test, is a fresh held-out test.',
            'The reconstruction model scores only the first 32 tokens of each bullet. Text after that point is shown '
            'but does not change any FVE number.',
            'A low FVE or Shapley share is not a truth label: a correct bullet can explain little of the activation and '
            'a wrong one can explain a lot.',
            'Labels come from the project judge reading the whole readout against the model\'s own reply. Bullet labels '
            'are derived by finding the judge\'s quoted spans in the text; a span that appears in several bullets '
            'marks all of them.',
            'Judge verdicts for identical texts were reused across settings through the judge cache, so they are not '
            'independent draws.',
            'Repeated bullets (same cleaned text) share one vector: their NNLS coefficients are not unique and Shapley '
            'credit is split equally between the copies.',
            'Per-bullet scores (solo, drop, Shapley) are not yet available in this build.' if not metrics else
            'Per-bullet scores were recomputed from the saved AR vectors and match the saved joint FVE.',
            'Character offsets are JavaScript string indices (UTF-16 code units).',
        ] + ([
            # Fallback versions of the two confound caveats (summary.json carries the numbers; the page shows these
            # notes only when summary.json is missing, while it still computes AUROC and same-readout rates itself).
            'The AUROC over all bullets compares bullets from different readouts. Every wrong bullet sits in a '
            'hallucinated readout, most clean bullets sit in consistent readouts, and consistent readouts have higher '
            'joint FVE, so an AUROC above 0.5 can come from the readouts rather than the bullets. The same-readout '
            'rate compares bullets of one readout.',
            'The same-readout rate does not control bullet position. Wrong bullets tend to sit later in the list, and '
            'Shapley share depends on position (in Original and Best of 32 later bullets get larger shares), so a '
            'same-readout rate below 0.5 there can be a position effect rather than wrong bullets getting more '
            'credit.',
        ] if metrics else []),
    }
    index = {'meta': meta, 'items': index_items, 'cells': index_cells}
    index_size = write_json(out / 'index.json', index)
    summary = build_summary(summary_rows, bool(metrics), ref_available, args.generated)
    summary['build'] = {'stats': dict(sorted(stats.items())), 'scored_boundary': dict(boundary.stats),
                        'reference_text_identical_to_capped': ref_same_as_capped,
                        'heat': dict(heat_written)}
    # Build stats always go to logs/ (read by build_summary.py). summary.json is only (re)written here while it
    # is still the provisional one: the final summary.json comes from build_summary.py and must not be clobbered
    # by a later rebuild (e.g. one that only adds heat). Re-run build_summary.py after any rebuild.
    write_json(ROOT / 'logs' / 'build_stats.json', summary)
    sp = out / 'summary.json'
    final = False
    if sp.is_file():
        try:
            final = not json.loads(sp.read_text()).get('provisional', False)
        except ValueError:
            final = False
    if final:
        summary_size = sp.stat().st_size
        print('summary.json is the final one from build_summary.py: left unchanged (re-run build_summary.py)')
    else:
        summary_size = write_json(sp, summary)
    big = max(item_sizes, key=item_sizes.get)
    print(json.dumps({'cells': len(index_cells), 'items': len(index_items), 'index_bytes': index_size,
                      'summary_bytes': summary_size, 'largest_item': [big, item_sizes[big]],
                      'items_total_bytes': sum(item_sizes.values()), 'seconds': round(time.time() - t0, 1),
                      'scored_boundary': dict(boundary.stats), 'heat': dict(heat_written)}, indent=1))
    print(json.dumps(dict(sorted(stats.items())), indent=1))


if __name__ == '__main__':
    main()
