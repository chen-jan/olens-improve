"""Role-bound association (`role_bound_association`): does higher per-bullet / per-readout FVE mean CORRECT?

The reverse of the Hallucination (chat) question. The judge answers three 6-way multiple-choice questions per readout
(agent, action, patient); a readout passes when all three are right. There are no per-bullet quotes, so a bullet is
`hit` by rule RBA-v1 (MAP.md section 7: names agent + patient + action, or 2 of 3 and is the bullet the judge's
evidence sentence points at, ...). Everything here is exploratory: all questions were inspected before, the labels
locate a readout-level verdict inside bullets by rule, and the text proxies are rough. No judge/API calls; read-only
outside this folder; no GPU.

Inputs (this folder unless noted)
  bullet_labels.jsonl              one row per bullet x setting (RBA-v1 labels, matched terms, judge fields)
  bullet_metrics.jsonl             per-bullet exact Shapley / share / solo / LOO drop / coefficient / dup
  data/rba_three_settings.jsonl    readout text, atoms (scored_token_count, sample_index), read-site kind
  candidates/candidates.jsonl      (extract_candidates.py) every whole-sample selection of each cell: sample index,
                                   exact FVE, text sha; plus the 32-sample FVE trace of Best of 32
  expansion-v1/judgments/<cond>/role_bound_association/results.json and ...readouts.jsonl for the whole-sample
                                   conditions capped_n1-n1, best_n_exact-n{1..32}, random_complete-n{1..32}
  item bank via load.load_bank()   story (stimulus), names, roles, action, options

Outputs
  analysis.json         every number quoted in ANALYSIS.md (95% percentile bootstrap intervals)
  read_sample.json      36 reading cases (12 high-share hit, 12 low-share hit, 12 high-share non-hit / wrong-specific)
  examples_analysis.txt candidate verbatim examples (for choosing the ones quoted in ANALYSIS.md)

Bootstrap: resampling unit = pair_id group (50 groups, MAP.md section 10); item-level (100 items) intervals are also
given for the headline rows. 1000 reps, seed 0.

Run (~2 min):
  env -u SLURM_JOB_ID srun --partition=mit_quicktest --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=16G \
    --time=00:15:00 --chdir=${OLENS_SCRATCH}/olens-bullet-fve /usr/bin/env \
    PYTHONPATH=${OLENS_REPO_ROOT}/src \
    ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B tasks/role_bound_association/analysis.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import math
import random
import re
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import load as L  # noqa: E402  (same folder: item bank, judge mirror, string rules)

T0 = time.time()
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
OB = SIDS[:2]               # writing order = lens order -> position adjustment (not Combine 32: selection order)
NREP, SEED = 1000, 0
LENMATCH = 0.8              # length-matched pair: shorter scored text >= 80% of the longer one (characters)
JUDG = Path(L.JUDGMENTS)
OUT_JSON = HERE / 'analysis.json'
OUT_SAMPLE = HERE / 'read_sample.json'
OUT_EX = HERE / 'examples_analysis.txt'


def log(*a):
    print(f'[{time.time() - T0:6.1f}s]', *a, flush=True)


# ============================================================================= load
bank = L.load_bank()

cells = {}
ntok = {}
with open(L.EXTRACT) as fh:
    for line in fh:
        c = json.loads(line)
        rpk = c['read_position_kind']
        cells[c['cell_id']] = {'item': c['item_id'], 'group': c['group_id'], 'layer': c['layer'], 'pos': c['position'],
                               'split': c['split'], 'token': c['token'], 'site_kind': rpk,
                               'offset': int(rpk.rsplit(':', 1)[1]), 'settings': {}}
        for sid in SIDS:
            s = c['settings'][sid]
            cells[c['cell_id']]['settings'][sid] = {
                'fve': s['fve'], 'text': s['text'], 'samples': sorted({a['sample_index'] for a in s['atoms']}),
                'trace32': ([(int(t['sample_id'].rsplit(':', 1)[1]), t.get('score')) for t in s['trace']]
                            if sid == 'best_n_exact-n32' else None)}
            for a in s['atoms']:
                ntok[(c['cell_id'], sid, a['source_phrase_id'])] = (a['scored_token_count'], a['sample_index'])
log('extract', len(cells))

metrics, ro_metrics = {}, {}
with open(HERE / 'bullet_metrics.jsonl') as fh:
    for line in fh:
        r = json.loads(line)
        for sid, s in r['settings'].items():
            ro_metrics[(r['cell_id'], sid)] = {'joint': s['joint_fve_saved'], 'skipped': s['skipped'],
                                               'has_dup': s['has_dup']}
            for j, b in enumerate(s['bullets']):
                metrics[(r['cell_id'], sid, b['phrase_id'])] = (j, b)
log('metrics', len(metrics))

KEEP = ('cell_id', 'setting', 'index', 'n_bullets', 'phrase_id', 'cache_key', 'has_vector', 'item_id', 'group_id',
        'pair_id', 'direction', 'stereotypicality', 'layer', 'position', 'split', 'token', 'text', 'scored_text',
        'truncated', 'label', 'label_fine', 'label_relaxed', 'label_visible', 'component', 'contrast_group', 'binding',
        'n_components', 'order', 'readout_fve_saved', 'readout_n_hit_bullets', 'item_pass')
rows, ro_judge = [], {}
with open(HERE / 'bullet_labels.jsonl') as fh:
    for line in fh:
        r0 = json.loads(line)
        r = {k: r0[k] for k in KEEP}
        ev = r0['evidence']
        r['terms'] = ev['matched_terms']
        r['cjk_only_parts'] = ev['cjk_only_parts']
        r['ev_overlap'] = ev['evidence_overlap']
        r['ev_best'] = ev['evidence_best']
        r['ev_quotes'] = ev['evidence_quotes_in_bullet']
        r['wrong_value'] = ev['wrong_value']
        key = (r['cell_id'], r['setting'])
        if key not in ro_judge:
            ro_judge[key] = dict(r0['judge'], evidence=ev['judge_evidence'], gold=r0['gold'])
        rows.append(r)
assert len(rows) == len(metrics) == len(ntok) == 136684
log('labels', len(rows))

GROUP_IDS = sorted({c['group'] for c in cells.values()})
ITEM_IDS = sorted(bank)
GIX = {g: i for i, g in enumerate(GROUP_IDS)}
IIX = {x: i for i, x in enumerate(ITEM_IDS)}
ITEM_GROUP = {c['item']: c['group'] for c in cells.values()}
assert len(GROUP_IDS) == 50 and len(ITEM_IDS) == 100

# ============================================================================= bullet features
CJKR = '㐀-䶿一-鿿豈-﫿'
CJK_CHAR = re.compile('[' + CJKR + ']')
LIST_OPEN = re.compile(r'^\W{0,4}\d+\s*[.):]\s*\S')                 # "1. ...", "2: ..."
MD_OPEN = re.compile(r'^\s*(?:\*\*[^*\n]{1,40}\*\*|#{1,4}\s)')              # "**Summary:** ...", "## ..."
HEAD_CHARS = 40
# summary / meta-instruction wording: the read sites are the tokens of "Summarize the preceding story in one sentence."
# and the chat tail, and the lens often continues that instruction ("marize this paragraph in one sentence") or adds
# assistant meta text ("Here is a summary of the scene"). instr_head = such wording starts in the first 40 characters;
# meta_tail = it occurs only later in the bullet (typically after story content).
INSTR = re.compile(r'(?i)(marize|summar|\bone sentence\b|\bin \w+ sentences?\b|\bpreceding\b|\bparagraph\b|'
                   r'\bpassage\b|\bsnippet\b|\bthis text\b|\bthe text\b)')


def cjk_frac(s):
    ns = [ch for ch in s if not ch.isspace()]
    return (len(CJK_CHAR.findall(s)) / len(ns)) if ns else 0.0


STORY_CW = {iid: set(L._content_words(it['stimulus'])) for iid, it in bank.items()}


def is_cjk_term(t):
    return bool(CJK_CHAR.search(t))


for r in rows:
    j, b = metrics[(r['cell_id'], r['setting'], r['phrase_id'])]
    nt, si = ntok[(r['cell_id'], r['setting'], r['phrase_id'])]
    assert j == r['index'] and b['cache_key'] == r['cache_key']
    rm = ro_metrics[(r['cell_id'], r['setting'])]
    scored = r['scored_text'] or ''
    cw = L._content_words(scored)
    people = r['terms']['agent'] + r['terms']['patient']
    valid = rm['skipped'] is None and b['has_vector'] and b['solo_fve'] is not None
    share = b['shapley_share'] if (valid and b['shapley_share'] is not None) else float('nan')
    r.update({
        'sid': r['setting'], 'k': f"{r['item_id']}.L{r['layer']}.p{r['position']}", 'j': r['index'], 'n': r['n_bullets'],
        'L': r['layer'], 'offset': cells[r['cell_id']]['offset'], 'gix': GIX[r['group_id']], 'iix': IIX[r['item_id']],
        'sample_index': si, 'valid': valid,
        'share': share, 'shap': b['shapley'] if valid else float('nan'),
        'solo': b['solo_fve'] if valid else float('nan'), 'drop': b['loo_drop'] if valid else float('nan'),
        'coef': b['coefficient'] if valid else float('nan'), 'dup': bool(b['dup']),
        'scored': scored, 'slen': len(scored), 'ntok': nt, 'cjk': cjk_frac(scored),
        'story_ov': (sum(w in STORY_CW[r['item_id']] for w in cw) / len(cw)) if cw else 0.0,
        'instr': float(bool(INSTR.search(scored))),
        'instr_head': float(any(m.start() < HEAD_CHARS for m in INSTR.finditer(scored))),
        'meta_tail': float(bool(INSTR.search(scored)) and not any(m.start() < HEAD_CHARS for m in INSTR.finditer(scored))),
        'md_open': float(bool(MD_OPEN.match(scored))),
        'list_open': float(bool(LIST_OPEN.match(scored))),
        'names_name': float(any(t[:1].isupper() for t in people)),
        'names_role': float(any((not is_cjk_term(t)) and not t[:1].isupper() for t in people)),
        'names_role_cjk': float(any(is_cjk_term(t) for t in people)),
        'names_action': float(bool(r['terms']['action'])),
        'ncomp': float(r['n_components']),
        'coef0': float(valid and b['coefficient'] == 0),
        'is_hit': float(r['label'] == 'hit'), 'is_wrong': float(r['label'] == 'wrong_specific'),
    })
    r['names_any_role'] = float(r['names_role'] or r['names_role_cjk'])

# analysis set: bullets with a vector in a fitted readout, not sharing a vector with a sibling
LAB = [r for r in rows if r['valid'] and not r['dup']]
log('LAB', len(LAB), 'dup', sum(r['dup'] for r in rows), 'invalid', sum(not r['valid'] for r in rows))

# position-adjusted percentiles: mid-rank among LAB bullets of the same (setting, list index, readout size) [_pa,
# the Hallucination definition]; *_paL adds the layer to the stratum (sensitivity)
for keyf, suf in ((lambda r: (r['sid'], r['j'], r['n']), '_pa'), (lambda r: (r['sid'], r['L'], r['j'], r['n']), '_paL')):
    grp = collections.defaultdict(list)
    for r in LAB:
        grp[keyf(r)].append(r)
    for gg in grp.values():
        for sc in ('solo', 'share', 'drop'):
            xs = [x for x in gg if not math.isnan(x[sc])]
            if not xs:
                continue
            v = np.array([x[sc] for x in xs], dtype=float)
            order = np.sort(v)
            lo = np.searchsorted(order, v, 'left')
            hi = np.searchsorted(order, v, 'right')
            for x, p in zip(xs, (lo + 0.5 * (hi - lo)) / len(v)):
                x[sc + suf] = float(p)
for r in rows:
    for sc in ('solo', 'share', 'drop'):
        for suf in ('_pa', '_paL'):
            r.setdefault(sc + suf, float('nan'))

by_ro = collections.defaultdict(list)       # all bullets
for r in rows:
    by_ro[(r['cell_id'], r['sid'])].append(r)
for v in by_ro.values():
    v.sort(key=lambda b: b['j'])
by_ro_nd = collections.defaultdict(list)    # LAB bullets only
for r in LAB:
    by_ro_nd[(r['cell_id'], r['sid'])].append(r)

# ============================================================================= bootstrap helpers
rng = np.random.default_rng(SEED)
BW = {'group': np.stack([np.bincount(b, minlength=len(GROUP_IDS)) for b in
                         rng.integers(0, len(GROUP_IDS), size=(NREP, len(GROUP_IDS)))]).astype(float),
      'item': np.stack([np.bincount(b, minlength=len(ITEM_IDS)) for b in
                        rng.integers(0, len(ITEM_IDS), size=(NREP, len(ITEM_IDS)))]).astype(float)}


def _unit_ix(item_id, unit):
    return GIX[ITEM_GROUP[item_id]] if unit == 'group' else IIX[item_id]


def agg(triples, unit='group'):
    nu = len(GROUP_IDS) if unit == 'group' else len(ITEM_IDS)
    num, den = np.zeros(nu), np.zeros(nu)
    for iid, a, b in triples:
        ix = _unit_ix(iid, unit)
        num[ix] += a
        den[ix] += b
    return num, den


def ratio_ci(triples, unit='group', nd=4):
    triples = list(triples)
    num, den = agg(triples, unit)
    if den.sum() == 0:
        return {'est': None, 'lo': None, 'hi': None, 'n': 0, 'units': 0}
    W = BW[unit]
    with np.errstate(invalid='ignore', divide='ignore'):
        b = (W @ num) / (W @ den)
    b = b[np.isfinite(b)]
    return {'est': round(float(num.sum() / den.sum()), nd), 'lo': round(float(np.percentile(b, 2.5)), nd),
            'hi': round(float(np.percentile(b, 97.5)), nd), 'n': int(round(den.sum())),
            'units': int((den > 0).sum())}


def diff_ci(t1, t2, unit='group', nd=4):
    n1, d1 = agg(list(t1), unit)
    n2, d2 = agg(list(t2), unit)
    if d1.sum() == 0 or d2.sum() == 0:
        return {'est': None, 'lo': None, 'hi': None}
    W = BW[unit]
    with np.errstate(invalid='ignore', divide='ignore'):
        b = (W @ n1) / (W @ d1) - (W @ n2) / (W @ d2)
    b = b[np.isfinite(b)]
    return {'est': round(float(n1.sum() / d1.sum() - n2.sum() / d2.sum()), nd),
            'lo': round(float(np.percentile(b, 2.5)), nd), 'hi': round(float(np.percentile(b, 97.5)), nd)}


def win(a, b):
    return 1.0 if a > b else (0.5 if a == b else 0.0)


def lenmatch(a, b):
    return min(a['slen'], b['slen']) / max(1, a['slen'], b['slen']) >= LENMATCH


def pair_triples(sids, score, A, B, match=None, ro_sel=None):
    """same-readout pairs (a in A, b in B) of LAB bullets: (item, win(score a, score b), 1)"""
    out = []
    for (cid, sid), bs in by_ro_nd.items():
        if sid not in sids or (ro_sel and not ro_sel(cid, sid, bs)):
            continue
        As = [x for x in bs if A(x)]
        if not As:
            continue
        Bs = [x for x in bs if B(x)]
        for a in As:
            for b in Bs:
                if a is b or (match and not match(a, b)) or math.isnan(a[score]) or math.isnan(b[score]):
                    continue
                out.append((a['item_id'], win(a[score], b[score]), 1.0))
    return out


def pr(sids, score, A, B, **kw):
    unit = kw.pop('unit', 'group')
    return ratio_ci(pair_triples(sids, score, A, B, **kw), unit)


def main_scores(sid):
    return ('solo_pa', 'share_pa', 'drop_pa') if sid in OB else ('solo', 'share', 'drop')


IS = lambda lab: (lambda r: r['label'] == lab)  # noqa: E731
NOT = lambda lab: (lambda r: r['label'] != lab)  # noqa: E731
FINE = lambda *f: (lambda r: r['label_fine'] in f)  # noqa: E731


def mixed(cid, sid, bs):
    return any(b['label'] == 'hit' for b in bs) and any(b['label'] != 'hit' for b in bs)


out = {'meta': {
    'family': 'role_bound_association (Role-bound association)', 'n_items': len(ITEM_IDS), 'n_groups': len(GROUP_IDS),
    'n_cells': len(cells), 'n_bullets': len(rows), 'n_analysis_bullets': len(LAB),
    'n_dup_bullets': sum(r['dup'] for r in rows), 'n_bullets_no_fit_or_vector': sum(not r['valid'] for r in rows),
    'bootstrap': {'unit': 'pair_id group (50); item-level (100) where marked', 'reps': NREP, 'seed': SEED,
                  'interval': 'percentile 2.5-97.5'},
    'pair_rate': 'P(score of the first group > score of the second) over same-readout pairs, ties 1/2; 0.5 = no '
                 'separation. Dup-vector bullets and bullets of the 43 unfitted Original readouts excluded.',
    'position_adjusted': '*_pa = mid-rank percentile among analysis bullets of the same setting, list index and '
                         'readout size (Original, Best of 32 only; Hallucination definition); *_paL also stratifies by '
                         'layer',
    'length_matched': f'shorter scored text >= {LENMATCH:.0%} of the longer (characters)',
    'labels': 'RBA-v1 (MAP.md section 7). Within a readout with >=1 hit, every other bullet is miss_pass_other; '
              'wrong_specific bullets only occur in failed readouts, so hit vs wrong_specific is never within a '
              'readout.'}}

# ============================================================================= T1 bullet level
log('T1')
t1 = {}
pooled_main = collections.defaultdict(list)
for sid in SIDS:
    S = SHORT[sid]
    d = {}
    sc_main, sh_main, dr_main = main_scores(sid)
    d['main_scores'] = [sc_main, sh_main, dr_main]
    d['n_pass_readouts'] = sum(1 for (cid, s), j in ro_judge.items() if s == sid and j['pass'])
    d['n_mixed_hit_readouts'] = sum(1 for (cid, s), bs in by_ro_nd.items() if s == sid and mixed(cid, s, bs))
    d['n_hit_bullets_in_mixed'] = sum(b['label'] == 'hit' for (cid, s), bs in by_ro_nd.items()
                                      if s == sid and mixed(cid, s, bs) for b in bs)
    d['n_nonhit_bullets_in_mixed'] = sum(b['label'] != 'hit' for (cid, s), bs in by_ro_nd.items()
                                         if s == sid and mixed(cid, s, bs) for b in bs)
    for sc in ('share', 'solo', 'drop'):
        d[f'hit_vs_nonhit_{sc}_raw'] = pr([sid], sc, IS('hit'), NOT('hit'))
        if sid in OB:
            d[f'hit_vs_nonhit_{sc}_posadj'] = pr([sid], sc + '_pa', IS('hit'), NOT('hit'))
            d[f'hit_vs_nonhit_{sc}_posadj_by_layer'] = pr([sid], sc + '_paL', IS('hit'), NOT('hit'))
    for sc in (sc_main, sh_main, dr_main):
        d[f'headline_{sc}_item_level'] = pr([sid], sc, IS('hit'), NOT('hit'), unit='item')
        pooled_main[sc.split('_')[0]].extend(pair_triples([sid], sc, IS('hit'), NOT('hit')))
    d['hit_vs_nonhit_solo_lenmatched'] = pr([sid], 'solo', IS('hit'), NOT('hit'), match=lenmatch)
    d['hit_vs_nonhit_share_lenmatched'] = pr([sid], 'share', IS('hit'), NOT('hit'), match=lenmatch)
    d['hit_vs_nonhit_drop_lenmatched'] = pr([sid], 'drop', IS('hit'), NOT('hit'), match=lenmatch)
    if sid in OB:
        d['hit_vs_nonhit_solo_posadj_lenmatched'] = pr([sid], 'solo_pa', IS('hit'), NOT('hit'), match=lenmatch)
        d['hit_vs_nonhit_share_posadj_lenmatched'] = pr([sid], 'share_pa', IS('hit'), NOT('hit'), match=lenmatch)
    d['hit_longer_than_nonhit_scored_chars'] = pr([sid], 'slen', IS('hit'), NOT('hit'))
    if sid in OB:
        d['hit_later_than_nonhit'] = pr([sid], 'j', IS('hit'), NOT('hit'))
    # label sensitivity
    d['strict_hit_vs_nonhit_' + sc_main] = pr([sid], sc_main, FINE('hit_strict'), NOT('hit'))
    d['strict_hit_vs_nonhit_solo_lenmatched'] = pr([sid], 'solo', FINE('hit_strict'), NOT('hit'), match=lenmatch)
    d['hit_vs_nonhit_naming_no_part_' + sc_main] = pr([sid], sc_main, IS('hit'),
                                                      lambda r: r['label'] != 'hit' and r['n_components'] == 0)
    d['hit_vs_nonhit_naming_no_part_solo_lenmatched'] = pr([sid], 'solo', IS('hit'),
                                                           lambda r: r['label'] != 'hit' and r['n_components'] == 0,
                                                           match=lenmatch)
    d['hit_vs_nonhit_naming_some_part_' + sc_main] = pr([sid], sc_main, IS('hit'),
                                                        lambda r: r['label'] != 'hit' and r['n_components'] >= 1)
    d['hit_no_cjk_only_match_vs_nonhit_' + sc_main] = pr([sid], sc_main,
                                                         lambda r: r['label'] == 'hit' and not r['cjk_only_parts'],
                                                         NOT('hit'))
    d['visible_label_hit_vs_nonhit_' + sc_main] = pr(
        [sid], sc_main, lambda r: r['label_visible'] == 'hit', lambda r: r['label_visible'] != 'hit',
        ro_sel=lambda cid, s, bs: any(b['label_visible'] == 'hit' for b in bs) and
        any(b['label_visible'] != 'hit' for b in bs))
    d['relaxed_hit_vs_nonhit_' + sc_main] = pr(
        [sid], sc_main, lambda r: r['label_relaxed'] == 'hit', lambda r: r['label_relaxed'] != 'hit',
        ro_sel=lambda cid, s, bs: ro_judge[(cid, s)]['pass'])
    d['relaxed_hit_vs_nonhit_solo_lenmatched'] = pr(
        [sid], 'solo', lambda r: r['label_relaxed'] == 'hit', lambda r: r['label_relaxed'] != 'hit', match=lenmatch,
        ro_sel=lambda cid, s, bs: ro_judge[(cid, s)]['pass'])
    # form/content confounds: drop bullets with summary/meta wording on both sides; drop bullets naming a protagonist by name
    # (names are copied from the story, role words never are) on both sides
    d['hit_vs_nonhit_no_summary_meta_wording_' + sc_main] = pr(
        [sid], sc_main, lambda r: r['label'] == 'hit' and not r['instr'], lambda r: r['label'] != 'hit' and not r['instr'])
    d['hit_vs_nonhit_neither_names_a_name_' + sc_main] = pr(
        [sid], sc_main, lambda r: r['label'] == 'hit' and not r['names_name'],
        lambda r: r['label'] != 'hit' and not r['names_name'])
    d['hit_vs_nonhit_neither_names_a_name_solo_lenmatched'] = pr(
        [sid], 'solo', lambda r: r['label'] == 'hit' and not r['names_name'],
        lambda r: r['label'] != 'hit' and not r['names_name'], match=lenmatch)
    # top-share bullet of a mixed readout is a hit, vs chance (= hit fraction)
    tops, chance = [], []
    for (cid, s), bs in by_ro_nd.items():
        if s != sid or not mixed(cid, s, bs) or any(math.isnan(b['share']) for b in bs):
            continue
        top = max(bs, key=lambda b: b['share'])
        tops.append((cells[cid]['item'], float(top['label'] == 'hit'), 1.0))
        chance.append((cells[cid]['item'], sum(b['label'] == 'hit' for b in bs) / len(bs), 1.0))
    d['top_share_bullet_is_hit'] = ratio_ci(tops)
    d['top_share_bullet_is_hit_chance'] = ratio_ci(chance)
    d['top_share_minus_chance'] = diff_ci(tops, chance)
    # slices: layer band, read-site band
    for name, sel in (('L20-28', lambda x: x <= 28), ('L36-44', lambda x: 36 <= x <= 44), ('L52-60', lambda x: x >= 52)):
        d[f'hit_vs_nonhit_{sc_main}_{name}'] = pr([sid], sc_main, IS('hit'), NOT('hit'),
                                                  ro_sel=lambda cid, s, bs, sel=sel: sel(cells[cid]['layer']))
    for name, sel in (('instruction tokens (offset 0-9)', lambda o: o <= 9),
                      ('chat-template tail (offset 10-18)', lambda o: o >= 10)):
        d[f'hit_vs_nonhit_{sc_main}_{name}'] = pr([sid], sc_main, IS('hit'), NOT('hit'),
                                                  ro_sel=lambda cid, s, bs, sel=sel: sel(cells[cid]['offset']))
    # wrong_specific bullets vs their sibling misses (failed readouts), and the carrier difference
    for sc in (sc_main, sh_main):
        d[f'wrong_specific_vs_sibling_miss_{sc}'] = pr([sid], sc, IS('wrong_specific'), IS('miss'))
        d[f'carrier_advantage_hit_minus_wrong_specific_{sc}'] = diff_ci(
            pair_triples([sid], sc, IS('hit'), NOT('hit')), pair_triples([sid], sc, IS('wrong_specific'), IS('miss')))
    d['wrong_specific_vs_sibling_miss_solo_lenmatched'] = pr([sid], 'solo', IS('wrong_specific'), IS('miss'),
                                                             match=lenmatch)
    for fine in ('wrong_reversed', 'wrong_reversed_partial', 'wrong_action', 'wrong_person'):
        d[f'{fine}_vs_sibling_miss_{sc_main}'] = pr([sid], sc_main, FINE(fine), IS('miss'))
    # judge-free content contrasts, all readouts (who-did-what words named in the bullet, regardless of verdict)
    nc = lambda lo, hi: (lambda r: lo <= r['n_components'] <= hi)  # noqa: E731
    d['content_3parts_vs_none_' + sc_main] = pr([sid], sc_main, nc(3, 3), nc(0, 0))
    d['content_3parts_vs_none_solo_lenmatched'] = pr([sid], 'solo', nc(3, 3), nc(0, 0), match=lenmatch)
    d['content_2plus_vs_none_' + sc_main] = pr([sid], sc_main, nc(2, 3), nc(0, 0))
    d['content_2plus_vs_none_solo_lenmatched'] = pr([sid], 'solo', nc(2, 3), nc(0, 0), match=lenmatch)
    d['content_2plus_vs_none_' + sc_main + '_pass_readouts'] = pr([sid], sc_main, nc(2, 3), nc(0, 0),
                                                                  ro_sel=lambda cid, s, bs: ro_judge[(cid, s)]['pass'])
    d['content_2plus_vs_none_' + sc_main + '_failed_readouts'] = pr(
        [sid], sc_main, nc(2, 3), nc(0, 0), ro_sel=lambda cid, s, bs: not ro_judge[(cid, s)]['pass'])
    # component labels: within readouts where the judge got that part right, bullets naming it vs bullets not
    for part, qi in (('agent', 0), ('action', 1), ('patient', 2)):
        d[f'component_{part}_hit_vs_not_named_{sc_main}'] = pr(
            [sid], sc_main, lambda r, p=part: r['component'][p] == 'hit', lambda r, p=part: not r['terms'][p],
            ro_sel=lambda cid, s, bs, q=qi: ro_judge[(cid, s)]['kinds'][q] == 'gold')
        d[f'component_{part}_wrong_vs_not_named_{sc_main}'] = pr(
            [sid], sc_main, lambda r, p=part: r['component'][p] == 'wrong',
            lambda r, p=part: r['component'][p] != 'wrong' and not r['terms'][p] and not r['wrong_value'])
    t1[S] = d
t1['pooled_three_settings'] = {
    'hit_vs_nonhit_' + k + ('_pa (Original, Best of 32) / raw (Combine 32)'): ratio_ci(v) for k, v in pooled_main.items()}
t1['pooled_three_settings'].update({
    'hit_vs_nonhit_' + k + '_item_level': ratio_ci(v, 'item') for k, v in pooled_main.items()})
t1['pooled_three_settings']['hit_vs_nonhit_solo_lenmatched'] = ratio_ci(
    sum((pair_triples([s], 'solo', IS('hit'), NOT('hit'), match=lenmatch) for s in SIDS), []))

# hit vs wrong_specific: never in the same readout, so compare across the three readouts of the same cell with SOLO
# FVE (bullet vs the cell's activation; does not depend on siblings). Same-vector bullets are skipped.
by_cell = collections.defaultdict(list)
for r in LAB:
    by_cell[r['cell_id']].append(r)


def cross_cell(score, A, B, match=None, unit='group'):
    acc = []
    for cid, bs in by_cell.items():
        As, Bs = {}, {}
        for x in bs:
            if A(x):
                As.setdefault(x['cache_key'], x)
            if B(x):
                Bs.setdefault(x['cache_key'], x)
        for ka, a in As.items():
            for kb, b in Bs.items():
                if ka == kb or (match and not match(a, b)):
                    continue
                acc.append((a['item_id'], win(a[score], b[score]), 1.0))
    return ratio_ci(acc, unit)


t1['cross_setting_same_cell'] = {
    'hit_vs_wrong_specific_solo': cross_cell('solo', IS('hit'), IS('wrong_specific')),
    'hit_vs_wrong_specific_solo_item_level': cross_cell('solo', IS('hit'), IS('wrong_specific'), unit='item'),
    'hit_vs_wrong_specific_solo_lenmatched': cross_cell('solo', IS('hit'), IS('wrong_specific'), match=lenmatch),
    'hit_vs_wrong_reversed_solo': cross_cell('solo', IS('hit'), FINE('wrong_reversed')),
    'hit_vs_clean_miss_solo': cross_cell('solo', IS('hit'), lambda r: r['contrast_group'] == 'clean_miss'),
    'hit_vs_clean_miss_solo_lenmatched': cross_cell('solo', IS('hit'), lambda r: r['contrast_group'] == 'clean_miss',
                                                    match=lenmatch),
    'wrong_specific_vs_clean_miss_solo': cross_cell('solo', IS('wrong_specific'),
                                                    lambda r: r['contrast_group'] == 'clean_miss'),
    'strict_hit_vs_failed_readout_bullet_naming_all_3_parts_solo': cross_cell(
        'solo', FINE('hit_strict'), lambda r: r['label'] != 'hit' and r['n_components'] == 3 and
        not ro_judge[(r['cell_id'], r['sid'])]['pass']),
    'note': 'pairs pooled over the three settings of one cell; bullets deduplicated by cache_key per class; raw solo '
            'FVE (position adjustment is not defined across settings)'}
out['T1_bullet_level'] = t1

# ============================================================================= T2 readout level
log('T2')
t2 = {}
PASS = {k: v['pass'] for k, v in ro_judge.items()}
FVE = {(cid, sid): c['settings'][sid]['fve'] for cid, c in cells.items() for sid in SIDS}
lay = {}
for sid in SIDS:
    lay[SHORT[sid]] = {}
    for Lr in sorted({c['layer'] for c in cells.values()}):
        cs = [cid for cid, c in cells.items() if c['layer'] == Lr]
        lay[SHORT[sid]][Lr] = {'pass_readouts': sum(PASS[(cid, sid)] for cid in cs), 'readouts': len(cs),
                               'mean_fve': round(float(np.mean([FVE[(cid, sid)] for cid in cs
                                                                if FVE[(cid, sid)] is not None])), 4)}
t2['by_layer'] = lay
site = {}
for sid in SIDS:
    site[SHORT[sid]] = {}
    for o in range(19):
        cs = [cid for cid, c in cells.items() if c['offset'] == o]
        site[SHORT[sid]][o] = {'token': collections.Counter(cells[cid]['token'] for cid in cs).most_common(1)[0][0],
                               'pass_readouts': sum(PASS[(cid, sid)] for cid in cs), 'readouts': len(cs),
                               'mean_fve': round(float(np.mean([FVE[(cid, sid)] for cid in cs
                                                                if FVE[(cid, sid)] is not None])), 4)}
t2['by_read_site_offset'] = site

# P(pass | FVE): pass rate by FVE quintile within (setting, layer, site offset) -- descriptive, across items
quint = {}
for sid in SIDS:
    strata = collections.defaultdict(list)
    for cid, c in cells.items():
        if FVE[(cid, sid)] is not None:
            strata[(c['layer'], c['offset'])].append(cid)
    qrows = collections.defaultdict(list)
    for cs in strata.values():
        v = np.array([FVE[(cid, sid)] for cid in cs])
        rk = np.argsort(np.argsort(v, kind='stable'), kind='stable')
        for cid, rr in zip(cs, rk):
            qrows[int(rr * 5 // len(cs))].append((cells[cid]['item'], float(PASS[(cid, sid)]), 1.0))
    quint[SHORT[sid]] = {f'Q{q + 1}': ratio_ci(qrows[q]) for q in range(5)}
    quint[SHORT[sid]]['Q5_minus_Q1'] = diff_ci(qrows[4], qrows[0])
t2['pass_rate_by_fve_quintile_within_layer_and_site'] = quint

# AUROC across items within (setting, layer, site offset): reference, confounded by item
auc_strat = {}
for sid in SIDS:
    acc = []
    strata = collections.defaultdict(list)
    for cid, c in cells.items():
        if FVE[(cid, sid)] is not None:
            strata[(c['layer'], c['offset'])].append(cid)
    for cs in strata.values():
        H = [cid for cid in cs if PASS[(cid, sid)]]
        N = [cid for cid in cs if not PASS[(cid, sid)]]
        for h in H:
            for n_ in N:
                acc.append((cells[h]['item'], win(FVE[(h, sid)], FVE[(n_, sid)]), 1.0))
    auc_strat[SHORT[sid]] = ratio_ci(acc)
t2['auroc_fve_pass_vs_fail_across_items_within_layer_and_site'] = auc_strat

# within (item, layer) across the 19 read sites, same setting (site and FVE both vary)
auc_sites = {}
for sid in SIDS:
    acc = []
    strata = collections.defaultdict(list)
    for cid, c in cells.items():
        if FVE[(cid, sid)] is not None:
            strata[(c['item'], c['layer'])].append(cid)
    for cs in strata.values():
        H = [cid for cid in cs if PASS[(cid, sid)]]
        N = [cid for cid in cs if not PASS[(cid, sid)]]
        acc += [(cells[h]['item'], win(FVE[(h, sid)], FVE[(n_, sid)]), 1.0) for h in H for n_ in N]
    auc_sites[SHORT[sid]] = ratio_ci(acc)
t2['auroc_fve_pass_vs_fail_within_item_layer_across_sites'] = auc_sites


# within cell across the three settings
def within_cell_settings(fail_sel=lambda cls: True, unit='group'):
    acc = []
    for cid, c in cells.items():
        for i, s1 in enumerate(SIDS):
            for s2 in SIDS[i + 1:]:
                p1, p2 = PASS[(cid, s1)], PASS[(cid, s2)]
                if p1 == p2 or c['settings'][s1]['text'] == c['settings'][s2]['text']:
                    continue
                if FVE[(cid, s1)] is None or FVE[(cid, s2)] is None:
                    continue
                hs, ns = (s1, s2) if p1 else (s2, s1)
                if not fail_sel(ro_judge[(cid, ns)]['readout_class']):
                    continue
                acc.append((c['item'], win(FVE[(cid, hs)], FVE[(cid, ns)]), 1.0))
    return ratio_ci(acc, unit)


t2['auroc_fve_within_cell_across_settings'] = within_cell_settings()
t2['auroc_fve_within_cell_across_settings_item_level'] = within_cell_settings(unit='item')
t2['auroc_fve_within_cell_across_settings_fail_is_wrong_binding'] = within_cell_settings(
    lambda cls: cls in ('reversed_binding', 'wrong_other'))
t2['auroc_fve_within_cell_across_settings_fail_is_partial_or_none'] = within_cell_settings(
    lambda cls: cls in ('partial', 'none'))
t2['readout_class_counts'] = {SHORT[sid]: dict(collections.Counter(ro_judge[(cid, sid)]['readout_class']
                                                                   for cid in cells)) for sid in SIDS}

# candidate level: every whole-sample readout judged by capped_n1-n1, best_n_exact-nK or random_complete-nK; its FVE is
# that sample's exact joint FVE in the Best of 32 trace (checked equal to the selection's own fit)
log('candidates')
KS = (1, 2, 4, 8, 16, 32)
COND_WHOLE = ['capped_n1-n1'] + [f'best_n_exact-n{k}' for k in KS] + [f'random_complete-n{k}' for k in KS]
RANDOMISH = {'capped_n1-n1'} | {f'random_complete-n{k}' for k in KS}
pass_by_cond, item_pass_by_cond, text_sha_by_cond = {}, {}, {}
for cond in COND_WHOLE:
    res = json.loads((JUDG / cond / L.FAMILY / 'results.json').read_text())
    pass_by_cond[cond] = {r['key']: bool(r['pass']) for r in res['rows']}
    assert len(pass_by_cond[cond]) == res['counts']['n_expected_cells'] - res['counts']['n_empty_cells'], cond
    ip = collections.defaultdict(bool)
    for r in res['rows']:
        ip[r['id']] |= bool(r['pass'])
    item_pass_by_cond[cond] = dict(ip)
    shas = {}
    with open(JUDG / cond / f'{L.FAMILY}.readouts.jsonl') as fh:
        for line in fh:
            x = json.loads(line)
            assert len(x['samples']) == 1
            shas[L.judge_key(x['id'], x['layer'], x['pos'])] = hashlib.sha256(x['samples'][0].encode()).hexdigest()
    text_sha_by_cond[cond] = shas
for sid in SIDS:  # the three settings' saved verdicts equal the labels file
    if sid in pass_by_cond:
        assert all(pass_by_cond[sid][L.judge_key(c['item'], c['layer'], c['pos'])] == PASS[(cid, sid)]
                   for cid, c in cells.items())
cand_stats = collections.Counter()
cand_cells = {}
with open(HERE / 'candidates' / 'candidates.jsonl') as fh:
    for line in fh:
        r = json.loads(line)
        cid = r['cell_id']
        c = cells[cid]
        key = L.judge_key(c['item'], c['layer'], c['pos'])
        trace = dict((s, v) for s, v in r['trace_best_n_exact_n32'])
        ordered = sorted(v for v in trace.values() if v is not None)
        per_sample = {}
        for x in r['candidates']:
            if x['cond'] not in COND_WHOLE:
                continue
            if key not in pass_by_cond[x['cond']] or not x['samples']:  # empty readout: not judged
                cand_stats['unjudged_empty_readout'] += 1                # (results.json counts n_empty_cells)
                continue
            s = x['samples'][0]
            if text_sha_by_cond[x['cond']][key] != x['text_sha256']:
                cand_stats['judged_text_sha_mismatch'] += 1
                continue
            if x['fve'] is None or trace.get(s) is None:
                cand_stats['candidate_without_fit'] += 1
                continue
            assert abs(trace[s] - x['fve']) < 1e-9, (cid, x['cond'])
            lo, hi = np.searchsorted(ordered, x['fve'], 'left'), np.searchsorted(ordered, x['fve'], 'right')
            e = per_sample.setdefault(s, {'sample': s, 'fve': x['fve'], 'verdicts': [], 'conds': [], 'shas': set(),
                                          'pct': float((lo + 0.5 * (hi - lo)) / len(ordered))})
            e['verdicts'].append(pass_by_cond[x['cond']][key])
            e['conds'].append(x['cond'])
            e['shas'].add(x['text_sha256'])
        for e in per_sample.values():
            assert len(e['shas']) == 1
            if len(set(e['verdicts'])) > 1:
                cand_stats['sample_with_conflicting_verdicts'] += 1
                cand_stats['conflict_judgments'] += len(e['verdicts'])
            cand_stats['sample_judged_more_than_once'] += len(e['verdicts']) > 1
            e['pass'] = all(e['verdicts'])
            e['pass_any'] = any(e['verdicts'])
            e['random'] = any(cd in RANDOMISH for cd in e['conds'])
        cand_cells[cid] = per_sample
        cand_stats['cells'] += 1
        cand_stats['distinct_judged_samples'] += len(per_sample)
        cand_stats['cells_with_pass_and_fail_candidate'] += (any(e['pass'] for e in per_sample.values()) and
                                                            any(not e['pass_any'] for e in per_sample.values()))
assert cand_stats['cells'] == 11400


def cand_auc(sel, unit='group'):
    acc = []
    for cid, ps in cand_cells.items():
        es = [e for e in ps.values() if sel(e)]
        for h in es:
            if not h['pass']:
                continue
            for n_ in es:
                if n_['pass_any']:
                    continue
                acc.append((cells[cid]['item'], win(h['fve'], n_['fve']), 1.0))
    return ratio_ci(acc, unit)


t2['candidates'] = {
    'stats': dict(cand_stats),
    'auroc_fve_within_cell_all_judged_candidates': cand_auc(lambda e: True),
    'auroc_fve_within_cell_all_judged_candidates_item_level': cand_auc(lambda e: True, 'item'),
    'auroc_fve_within_cell_random_picked_candidates_only': cand_auc(lambda e: e['random']),
    'auroc_fve_within_cell_random_picked_item_level': cand_auc(lambda e: e['random'], 'item'),
    'mean_fve_percentile_among_32_pass_candidates': ratio_ci(
        [(cells[cid]['item'], e['pct'], 1.0) for cid, ps in cand_cells.items() for e in ps.values() if e['pass']]),
    'mean_fve_percentile_among_32_fail_candidates': ratio_ci(
        [(cells[cid]['item'], e['pct'], 1.0) for cid, ps in cand_cells.items() for e in ps.values()
         if not e['pass_any']]),
    'mean_fve_percentile_among_32_pass_candidates_random_picked': ratio_ci(
        [(cells[cid]['item'], e['pct'], 1.0) for cid, ps in cand_cells.items() for e in ps.values()
         if e['pass'] and e['random']]),
    'mean_fve_percentile_among_32_fail_candidates_random_picked': ratio_ci(
        [(cells[cid]['item'], e['pct'], 1.0) for cid, ps in cand_cells.items() for e in ps.values()
         if not e['pass_any'] and e['random']]),
    'pass_rate_random_picked_candidates': ratio_ci(
        [(cells[cid]['item'], float(e['pass']), 1.0) for cid, ps in cand_cells.items() for e in ps.values()
         if e['random']]),
    'pass_rate_best_of_32_pick': ratio_ci(
        [(cells[cid]['item'], float(e['pass']), 1.0) for cid, ps in cand_cells.items() for e in ps.values()
         if 'best_n_exact-n32' in e['conds']]),
    'note': 'distinct source samples per cell judged by any of capped_n1-n1, best_n_exact-n{1..32}, '
            'random_complete-n{1..32}; judged text checked by sha256 against the condition readouts file. A sample '
            'judged by several conditions has byte-identical text; pass = all its verdicts pass, fail = none pass '
            '(samples with conflicting verdicts are dropped from AUROC pairs). random-picked = chosen by capped_n1 '
            'or random_complete (not by FVE). pct = mid-rank percentile of the sample FVE among the 32 samples.'}

# best-of-K (by FVE) vs random-of-K: readout pass rate and item pass, K = 1..32
curve = {}
for k in KS:
    row = {}
    # empty (unjudged) readouts count as not passing, as in the condition's own item verdicts
    bt = [(c['item'], float(pass_by_cond[f'best_n_exact-n{k}'].get(L.judge_key(c['item'], c['layer'], c['pos']),
                                                                    False)), 1.0) for c in cells.values()]
    rt = [(c['item'], float(pass_by_cond[f'random_complete-n{k}'].get(L.judge_key(c['item'], c['layer'], c['pos']),
                                                                       False)), 1.0) for c in cells.values()]
    for meth, tt in (('best_n_exact', bt), ('random_complete', rt)):
        cond = f'{meth}-n{k}'
        row[meth] = {'pass_readouts': int(sum(x[1] for x in tt)), 'readouts': len(tt),
                     'judged_readouts': len(pass_by_cond[cond]),
                     'items_pass': sum(item_pass_by_cond[cond].values())}
    row['pass_rate_best_minus_random'] = diff_ci(bt, rt, nd=5)
    curve[k] = row
t2['best_of_k_vs_random_of_k'] = curve

# settings vs Original
cmp_ = {}
O = 'capped_n1-n1'
for sid in SIDS[1:]:
    fixes = sum(not PASS[(cid, O)] and PASS[(cid, sid)] for cid in cells)
    breaks = sum(PASS[(cid, O)] and not PASS[(cid, sid)] for cid in cells)
    a = [(c['item'], float(PASS[(cid, sid)]), 1.0) for cid, c in cells.items()]
    b = [(c['item'], float(PASS[(cid, O)]), 1.0) for cid, c in cells.items()]
    cmp_[SHORT[sid]] = {'readout_pass_rate': ratio_ci(a, nd=5), 'readout_pass_rate_change': diff_ci(a, b, nd=5),
                        'fixes': fixes, 'breaks': breaks,
                        'same_text_as_original': sum(cells[cid]['settings'][sid]['text'] ==
                                                     cells[cid]['settings'][O]['text'] for cid in cells)}
    gains = {cid: FVE[(cid, sid)] - FVE[(cid, O)] for cid in cells if FVE[(cid, O)] is not None}
    q = np.quantile(list(gains.values()), [1 / 3, 2 / 3])
    for name, lo_, hi_ in (('low', -9, q[0]), ('mid', q[0], q[1]), ('high', q[1], 9)):
        cs = [cid for cid in gains if lo_ <= gains[cid] < hi_]
        cmp_[SHORT[sid]][f'gain_tertile_{name}'] = {
            'gain_range': [round(float(max(lo_, min(gains.values()))), 4), round(float(min(hi_, max(gains.values()))), 4)],
            'cells': len(cs),
            'fixes': sum(not PASS[(cid, O)] and PASS[(cid, sid)] for cid in cs),
            'breaks': sum(PASS[(cid, O)] and not PASS[(cid, sid)] for cid in cs)}
    ires = json.loads((JUDG / sid / L.FAMILY / 'results.json').read_text())['rows']
    ip_s = collections.defaultdict(bool)
    for rr in ires:
        ip_s[rr['id']] |= bool(rr['pass'])
    cmp_[SHORT[sid]]['item_pass_change'] = diff_ci([(i, float(ip_s[i]), 1.0) for i in ITEM_IDS],
                                                   [(i, float(item_pass_by_cond[O][i]), 1.0) for i in ITEM_IDS])
    cmp_[SHORT[sid]]['items_pass'] = sum(ip_s.values())
cmp_['Original'] = {'readout_pass_rate': ratio_ci([(c['item'], float(PASS[(cid, O)]), 1.0) for cid, c in cells.items()],
                                                  nd=5),
                    'items_pass': sum(item_pass_by_cond[O].values())}
t2['settings_vs_original'] = cmp_
t2['expanded_report_reference'] = {
    'released_original_lens': '78.0% (78/100) [70.0, 85.0]', 'four_bullet_original': '78.0% (78/100)',
    'best_of_32': '77/100 versus 78/100; fit +3.674 pp on 11357 common valid sites',
    'combine_32': '81/100 versus 78/100; fit +5.635 pp on 11357 common valid sites',
    'best_of_k_curve_item_pass': 'K=2 79.0%, K=4 83.0%, K=8 80.0%, K=16 81.0%, K=32 77.0%',
    'note': 'item pass = any of the 114 read sites passes (the report notes the any-of-grid floor saturates)',
    'source': 'olens-improve docs/EXPANDED_REPORT.md lines 24, 28, 61, 106, 166-174, 303-312'}
out['T2_readout_level'] = t2

# ============================================================================= T3 what FVE tracks within readouts
log('T3')
for r in rows:
    r['neg_cjk'] = -r['cjk']
    r['neg_coef0'] = -r['coef0']
    r['neg_list_open'] = -r['list_open']
    r['neg_instr'] = -r['instr']
    r['neg_md_open'] = -r['md_open']
    r['log_len'] = math.log(max(1, r['slen']))


def feat_pair(sids, feat, score, sel=lambda r: True, match=None):
    acc = []
    for (cid, sid), bs in by_ro_nd.items():
        if sid not in sids:
            continue
        bs = [b for b in bs if sel(b) and not math.isnan(b[score])]
        for a in bs:
            for b in bs:
                if a is not b and a[feat] > b[feat] and (match is None or match(a, b)):
                    acc.append((a['item_id'], win(a[score], b[score]), 1.0))
    return ratio_ci(acc)


t3 = {}
for sid in SIDS:
    S = SHORT[sid]
    p = {
        'longer scored text scores higher': feat_pair([sid], 'slen', 'solo'),
        'less CJK scores higher': feat_pair([sid], 'neg_cjk', 'solo'),
        'more story content-word overlap scores higher': feat_pair([sid], 'story_ov', 'solo'),
        'more story overlap scores higher, length-matched': feat_pair([sid], 'story_ov', 'solo', match=lenmatch),
        'no summary/meta wording anywhere scores higher': feat_pair([sid], 'neg_instr', 'solo'),
        'no summary/meta wording anywhere scores higher, length-matched': feat_pair([sid], 'neg_instr', 'solo',
                                                                                   match=lenmatch),
        'opens with summary/instruction wording scores higher (vs none)': feat_pair(
            [sid], 'instr_head', 'solo', sel=lambda r: not r['meta_tail']),
        'opens with summary/instruction wording scores higher (vs none), length-matched': feat_pair(
            [sid], 'instr_head', 'solo', sel=lambda r: not r['meta_tail'], match=lenmatch),
        'summary/meta wording only later in the bullet scores higher (vs none)': feat_pair(
            [sid], 'meta_tail', 'solo', sel=lambda r: not r['instr_head']),
        'summary/meta wording only later scores higher (vs none), length-matched': feat_pair(
            [sid], 'meta_tail', 'solo', sel=lambda r: not r['instr_head'], match=lenmatch),
        'no markdown-header opener (**...** / #) scores higher': feat_pair([sid], 'neg_md_open', 'solo'),
        'non-redundant (coef > 0) scores higher': feat_pair([sid], 'neg_coef0', 'solo'),
        'no list-number opener scores higher': feat_pair([sid], 'neg_list_open', 'solo'),
        'names a protagonist name (copied from the story) scores higher': feat_pair([sid], 'names_name', 'solo'),
        'names an English role word (never in the story) scores higher': feat_pair([sid], 'names_role', 'solo'),
        'names a role word (English or Chinese) scores higher, length-matched': feat_pair(
            [sid], 'names_any_role', 'solo', match=lenmatch),
        'names the action scores higher': feat_pair([sid], 'names_action', 'solo'),
        'names the action scores higher, length-matched': feat_pair([sid], 'names_action', 'solo', match=lenmatch),
        'names more of agent/action/patient scores higher': feat_pair([sid], 'ncomp', 'solo'),
        'names more of agent/action/patient scores higher, length-matched': feat_pair([sid], 'ncomp', 'solo',
                                                                                     match=lenmatch),
        'hit scores higher (label, raw solo)': feat_pair([sid], 'is_hit', 'solo'),
    }
    if sid in OB:
        p['later position scores higher'] = feat_pair([sid], 'j', 'solo')
    t3[S] = {'pair_rates_solo': p}
    t3[S]['feature_means_by_contrast_group'] = {}
    for g in ('hit', 'miss_pass_other', 'wrong_specific', 'miss_wrong_readout', 'clean_miss', 'excluded_unlocated'):
        R = [r for r in LAB if r['sid'] == sid and r['contrast_group'] == g]
        if not R:
            continue
        t3[S]['feature_means_by_contrast_group'][g] = {
            'n': len(R), 'median_scored_chars': float(np.median([r['slen'] for r in R])),
            'mean_solo': round(float(np.mean([r['solo'] for r in R])), 4),
            'mean_share': round(float(np.nanmean([r['share'] for r in R])), 4),
            'coef0': round(float(np.mean([r['coef0'] for r in R])), 3),
            'mean_cjk': round(float(np.mean([r['cjk'] for r in R])), 3),
            'any_cjk': round(float(np.mean([r['cjk'] > 0 for r in R])), 3),
            'mean_story_ov': round(float(np.mean([r['story_ov'] for r in R])), 3),
            'summary_meta_wording': round(float(np.mean([r['instr'] for r in R])), 3),
            'summary_wording_in_opening': round(float(np.mean([r['instr_head'] for r in R])), 3),
            'meta_wording_only_later': round(float(np.mean([r['meta_tail'] for r in R])), 3),
            'list_number_opener': round(float(np.mean([r['list_open'] for r in R])), 3),
            'markdown_header_opener': round(float(np.mean([r['md_open'] for r in R])), 3),
            'names_name': round(float(np.mean([r['names_name'] for r in R])), 3),
            'names_role_en': round(float(np.mean([r['names_role'] for r in R])), 3),
            'names_action': round(float(np.mean([r['names_action'] for r in R])), 3),
            'mean_position': round(float(np.mean([r['j'] for r in R])), 3),
            'truncated': round(float(np.mean([bool(r['truncated']) for r in R])), 3)}

FORM = ['log_len', 'cjk', 'story_ov', 'instr_head', 'meta_tail', 'list_open', 'md_open']
CONTENT = ['names_name', 'names_any_role', 'names_action']


def within_reg(sid, y='solo', content=False, with_coef0=False):
    R = [r for r in LAB if r['sid'] == sid and r['contrast_group'] != 'excluded_unlocated' and not math.isnan(r[y])]
    names = ['is_hit', 'is_wrong'] + FORM + (CONTENT if content else []) + (['coef0'] if with_coef0 else [])
    if sid in OB:
        names += ['pos2', 'pos3', 'pos4']
    X = []
    for r in R:
        v = [r[n] for n in names if not n.startswith('pos')]
        if sid in OB:
            v += [float(r['j'] == 1), float(r['j'] == 2), float(r['j'] == 3)]
        X.append(v)
    X, Y = np.array(X, dtype=float), np.array([r[y] for r in R])
    idx = collections.defaultdict(list)
    for i, r in enumerate(R):
        idx[(r['cell_id'], r['sid'])].append(i)
    Xd, Yd = X.copy(), Y.copy()
    for ii in idx.values():
        Xd[ii] -= X[ii].mean(0)
        Yd[ii] -= Y[ii].mean()
    sd = Xd.std(0)
    cont = {'log_len', 'cjk', 'story_ov'}
    Xs = Xd / np.array([sd[i] if n in cont else 1.0 for i, n in enumerate(names)])
    gx = np.array([r['gix'] for r in R])

    def fit(w):
        ww = w[gx]
        return np.linalg.lstsq(Xs.T @ (Xs * ww[:, None]), Xs.T @ (Yd * ww), rcond=None)[0]

    def r2_of(cols):
        bk = np.linalg.lstsq(Xs[:, cols], Yd, rcond=None)[0]
        rk = Yd - Xs[:, cols] @ bk
        return 1 - (rk ** 2).sum() / (Yd ** 2).sum()

    est = fit(np.ones(len(GROUP_IDS)))
    boots = np.array([fit(w) for w in BW['group']])
    r2 = r2_of(list(range(len(names))))
    res = {'n_bullets': len(R), 'n_hit': int(sum(r['is_hit'] for r in R)), 'n_wrong': int(sum(r['is_wrong'] for r in R)),
           'within_readout_R2': round(float(r2), 4), 'within_readout_sd_of_y': round(float(Yd.std()), 4),
           'units': f'change in {y} (same readout) per 1 within-readout SD for log_len, cjk, story_ov and per 0->1 for '
                    'binary terms; label reference = the sibling misses of the same readout',
           'coef': {n: {'est': round(float(est[i]), 4), 'lo': round(float(np.percentile(boots[:, i], 2.5)), 4),
                        'hi': round(float(np.percentile(boots[:, i], 97.5)), 4)} for i, n in enumerate(names)},
           'R2_lost_without_feature': {n: round(float(r2 - r2_of([x for x in range(len(names)) if x != i])), 5)
                                       for i, n in enumerate(names)},
           'R2_labels_only': round(float(r2_of([0, 1])), 5),
           'R2_added_by_labels_after_rest': round(float(r2 - r2_of(list(range(2, len(names))))), 5)}
    subsets = {'length': ['log_len'], 'CJK': ['cjk'], 'story overlap': ['story_ov'],
               'summary/meta wording (opening, later)': ['instr_head', 'meta_tail'],
               'list-number + markdown-header openers': ['list_open', 'md_open'], 'all form features': FORM}
    if content:
        subsets['content (name, role word, action)'] = CONTENT
    if sid in OB:
        subsets['position'] = ['pos2', 'pos3', 'pos4']
    res['R2_feature_subsets_alone'] = {nm: round(float(r2_of([names.index(f) for f in fs])), 4)
                                       for nm, fs in subsets.items()}
    hw = boots[:, 0] - boots[:, 1]
    res['hit_minus_wrong_specific'] = {'est': round(float(est[0] - est[1]), 4),
                                       'lo': round(float(np.percentile(hw, 2.5)), 4),
                                       'hi': round(float(np.percentile(hw, 97.5)), 4)}
    return res


for sid in SIDS:
    t3[SHORT[sid]]['within_readout_regression_solo_form'] = within_reg(sid)
    t3[SHORT[sid]]['within_readout_regression_solo_form_content'] = within_reg(sid, content=True)
    if sid in OB:  # coef 0 is itself an output of the fit (redundancy given siblings): secondary model only
        t3[SHORT[sid]]['within_readout_regression_solo_form_content_coef0'] = within_reg(sid, content=True,
                                                                                          with_coef0=True)
t3['coef0_rate_by_contrast_group'] = {
    SHORT[sid]: {g: ratio_ci([(r['item_id'], r['coef0'], 1.0) for r in LAB if r['sid'] == sid and
                              r['contrast_group'] == g])
                 for g in ('hit', 'miss_pass_other', 'wrong_specific', 'miss_wrong_readout', 'clean_miss')}
    for sid in SIDS}
out['T3_what_fve_tracks'] = t3


# ============================================================================= examples + reading sample
log('examples')


def fmt_case(cid, sid, focus=None):
    c = cells[cid]
    it = bank[c['item']]
    jd = ro_judge[(cid, sid)]
    lines = [f"k={c['item']}.L{c['layer']}.p{c['pos']} [{SHORT[sid]}] cell_id={cid} site={c['site_kind']} "
             f"token={c['token']!r} readout FVE={(FVE[(cid, sid)] or 0):.4f} class={jd['readout_class']}",
             f"   gold: {it['gold_label']} ({jd['gold']['agent']} -> {jd['gold']['action']} -> {jd['gold']['patient']})"
             f" | judge: {jd['choice_labels']} | evidence: {jd['evidence']!r}"]
    for b in by_ro[(cid, sid)]:
        mark = '>>' if focus is not None and b['j'] == focus else '  '
        sc = (f"share={b['share']:.3f} solo={b['solo']:.3f} drop={b['drop']:.4f} coef={b['coef']:.2f}"
              if b['valid'] else 'no metrics')
        lines.append(f"{mark} [{b['j']}] {b['label_fine']:<22} {b['binding']:<6} {sc}{' DUP' if b['dup'] else ''}"
                     f"{' TRUNC' if b['truncated'] else ''} | {json.dumps(b['text'], ensure_ascii=False)[:260]}")
    return '\n'.join(lines)


def rnd(x, d=4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, d)


def brec(b, bs):
    shares = sorted([x['share'] for x in bs if not math.isnan(x['share'])], reverse=True)
    return {
        'index': b['j'], 'text': b['text'], 'scored_text': b['scored'], 'truncated': bool(b['truncated']),
        'label': b['label'], 'label_fine': b['label_fine'], 'label_relaxed': b['label_relaxed'],
        'contrast_group': b['contrast_group'], 'binding_named': b['binding'], 'matched_terms': b['terms'],
        'cjk_only_parts': b['cjk_only_parts'], 'evidence_overlap': b['ev_overlap'], 'evidence_best': b['ev_best'],
        'evidence_quotes_in_bullet': b['ev_quotes'], 'wrong_value': b['wrong_value'],
        'shapley': rnd(b['shap'], 5), 'share': rnd(b['share']), 'solo': rnd(b['solo']), 'drop': rnd(b['drop'], 5),
        'coef': rnd(b['coef']), 'dup_vector': b['dup'],
        'solo_pos_pct': rnd(b['solo_pa'], 3) if b['sid'] in OB else None,
        'share_rank_in_readout': (1 + shares.index(b['share'])) if not math.isnan(b['share']) else None,
    }


def case_record(r, stratum, why):
    cid, sid = r['cell_id'], r['sid']
    c = cells[cid]
    it = bank[c['item']]
    jd = ro_judge[(cid, sid)]
    bs = by_ro[(cid, sid)]
    others = {}
    for s2 in SIDS:
        if s2 == sid:
            continue
        j2 = ro_judge[(cid, s2)]
        others[SHORT[s2]] = {'readout_fve': rnd(FVE[(cid, s2)]), 'readout_class': j2['readout_class'],
                             'judge_choices': j2['choice_labels'], 'judge_evidence': j2['evidence'],
                             'bullets': [{'index': b['j'], 'text': b['text'], 'label_fine': b['label_fine'],
                                          'share': rnd(b['share']), 'solo': rnd(b['solo'])} for b in by_ro[(cid, s2)]]}
    return {
        'case_id': None, 'stratum': stratum, 'why_selected': why,
        'k': r['k'], 'cell_id': cid, 'setting': sid, 'setting_display': SHORT[sid], 'focus_bullet': r['j'],
        'item_id': c['item'], 'pair_id': it['pair_id'], 'group_id': c['group'], 'split': c['split'],
        'stereotypicality': it['stereotypicality'], 'layer': c['layer'],
        'read_site': {'position': c['pos'], 'token': c['token'], 'kind': c['site_kind'],
                      'note': 'suffix token of "\\n\\nSummarize the preceding story in one sentence." + chat tail; '
                              'story tokens are never read'},
        'story': it['stimulus'],
        'target': {'gold_label': it['gold_label'], 'contrast_label': it['contrast_label'],
                   'agent': jd['gold']['agent'], 'action': jd['gold']['action'], 'patient': jd['gold']['patient'],
                   'names': it['names'], 'roles': {'a': it['role_a'], 'b': it['role_b']}, 'direction': it['direction'],
                   'agent_aliases': sorted(set(it['lex']['role'][it['agent_side']]) |
                                           {it['names'][it['agent_side']]} | set(it['lex']['role_cjk'][it['agent_side']])),
                   'patient_aliases': sorted(set(it['lex']['role'][it['patient_side']]) |
                                             {it['names'][it['patient_side']]} |
                                             set(it['lex']['role_cjk'][it['patient_side']])),
                   'action_aliases': it['lex']['action']['words'][:40] + it['lex']['action_cjk']},
        'judge': {'choices': jd['choice_labels'], 'kinds': jd['kinds'], 'readout_class': jd['readout_class'],
                  'pass': jd['pass'], 'evidence': jd['evidence'], 'options_shown': it['options']},
        'readout_fve': rnd(FVE[(cid, sid)], 5), 'readout_text': c['settings'][sid]['text'],
        'bullets': [brec(b, bs) for b in bs],
        'other_settings_same_cell': others,
        'reader_questions': [
            'Does the focus bullet itself state who did what to whom (agent, action, patient, direction), or does the '
            'binding only come together across bullets / from the judge\'s reading?',
            'Is the focus bullet\'s score explained by its form (length, script, instruction echo, position, '
            'redundancy, story wording) rather than by the binding it carries?',
            'Which sibling takes the most share, and what does it say?'],
    }


strata_pools = {}
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid and not math.isnan(r['share'])]
    mixed_ro = {(cid, s) for (cid, s), bs in by_ro_nd.items() if s == sid and mixed(cid, s, bs)}
    H = [r for r in R if r['label'] == 'hit' and (r['cell_id'], sid) in mixed_ro]
    hs = [r['share'] for r in H]
    q80, q20 = np.quantile(hs, .8), np.quantile(hs, .2)
    W = [r for r in R if r['label'] == 'wrong_specific' and len(by_ro_nd[(r['cell_id'], sid)]) > 1]
    wq80 = np.quantile([r['share'] for r in W], .8)
    Mx = [r for r in R if r['label'] == 'miss' and (r['cell_id'], sid) in mixed_ro and
          r['share'] > max(b['share'] for b in by_ro_nd[(r['cell_id'], sid)] if b['label'] == 'hit')]
    mq50 = np.quantile([r['share'] for r in Mx], .5) if Mx else 0
    strata_pools[sid] = {
        'A_hit_high_share': ([r for r in H if r['share'] >= q80],
                             f'hit bullet in a mixed readout, share >= q80 of hit shares ({q80:.3f})'),
        'B_hit_low_share': ([r for r in H if r['share'] <= q20],
                            f'hit bullet in a mixed readout, share <= q20 of hit shares ({q20:.3f})'),
        'C1_wrong_specific_high_share': ([r for r in W if r['share'] >= wq80],
                                         f'wrong_specific bullet, share >= q80 of wrong_specific shares ({wq80:.3f})'),
        'C2_miss_beats_hit_high_share': ([r for r in Mx if r['share'] >= mq50],
                                         f'miss bullet in a passing readout that out-shares every hit bullet, share '
                                         f'>= median of such misses ({mq50:.3f})'),
    }
PLAN = {'A_hit_high_share': 4, 'B_hit_low_share': 4, 'C1_wrong_specific_high_share': 2,
        'C2_miss_beats_hit_high_share': 2}
srng = random.Random(SEED)
sample = []
used_items = collections.defaultdict(set)
for stratum, per in PLAN.items():
    big = stratum[:1]
    for sid in SIDS:
        pool, why = strata_pools[sid][stratum]
        pool = sorted(pool, key=lambda r: (r['cell_id'], r['j']))
        srng.shuffle(pool)
        got, layers_used = 0, collections.Counter()
        for pass_ in range(3):  # spread over layers; at most one case per item within A, within B, within C
            for r in pool:
                if got >= per:
                    break
                if r['item_id'] in used_items[big] or any(x['cell_id'] == r['cell_id'] and x['setting'] == sid
                                                          for x in sample):
                    continue
                if pass_ == 0 and layers_used[r['L']] >= 1:
                    continue
                if pass_ == 1 and layers_used[r['L']] >= 2:
                    continue
                sample.append(case_record(r, stratum, why))
                used_items[big].add(r['item_id'])
                layers_used[r['L']] += 1
                got += 1
for i, cse in enumerate(sample):
    cse['case_id'] = f'rba-read-{i:02d}'
OUT_SAMPLE.write_text(json.dumps({
    'family': 'role_bound_association (Role-bound association)', 'seed': SEED, 'n_cases': len(sample),
    'design': {'A_hit_high_share': '12 = 4 per setting', 'B_hit_low_share': '12 = 4 per setting',
               'C_nonhit_high_share': '12 = per setting 2 wrong_specific with high share + 2 misses that out-share '
                                      'every hit bullet of a passing readout',
               'balance': 'at most one case per item within A, within B and within C; layers spread (seeded shuffle)',
               'pool_sizes': {SHORT[s]: {k: len(v[0]) for k, v in strata_pools[s].items()} for s in SIDS},
               'scores': 'share = exact Shapley share of the readout joint FVE; solo = bullet-alone FVE; drop = '
                         'leave-one-out FVE loss; coef = NNLS coefficient (0 = redundant); solo_pos_pct = '
                         'position-adjusted solo percentile (Original, Best of 32 only)',
               'labels': 'rule RBA-v1, tasks/role_bound_association/MAP.md section 7: the judge answers per readout, '
                         'so which bullet carries the binding is inferred from names/role words/action words and the '
                         "judge's evidence sentence"},
    'cases': sample}, ensure_ascii=False, indent=1))

with open(OUT_EX, 'w') as fh:
    def dump(title, rs, n=15):
        fh.write(f'\n######## {title}\n')
        for r in rs[:n]:
            fh.write(fmt_case(r['cell_id'], r['sid'], r['j']) + '\n\n')
    for sid in SIDS:
        R = [r for r in LAB if r['sid'] == sid and not math.isnan(r['share'])]
        mx = {(cid, s) for (cid, s), bs in by_ro_nd.items() if s == sid and mixed(cid, s, bs)}
        H = [r for r in R if r['label'] == 'hit' and (r['cell_id'], sid) in mx]
        dump(f'{SHORT[sid]}: high-share hits', sorted(H, key=lambda r: -r['share']))
        dump(f'{SHORT[sid]}: low-share hits', sorted(H, key=lambda r: r['share']))
        Wr = [r for r in R if r['label'] == 'wrong_specific' and r['n'] > 1]
        dump(f'{SHORT[sid]}: high-share wrong_specific', sorted(Wr, key=lambda r: -r['share']))
        dump(f'{SHORT[sid]}: high-solo hits', sorted([r for r in R if r['label'] == 'hit'], key=lambda r: -r['solo']), 8)
        dump(f'{SHORT[sid]}: high-solo wrong_specific', sorted(Wr, key=lambda r: -r['solo']), 8)
    # readouts mixing a bullet that opens with summary/instruction wording with a bullet that names >= 1 part of the
    # binding and has no summary wording (seeded)
    xr = random.Random(SEED + 1)
    pool = sorted(k for k, bs in by_ro_nd.items() if any(b['instr_head'] for b in bs) and
                  any(not b['instr'] and b['n_components'] >= 1 for b in bs))
    xr.shuffle(pool)
    fh.write(f'\n######## summary wording in the opening next to story content (random {min(15, len(pool))} of '
             f'{len(pool)})\n')
    for cid, sid in pool[:15]:
        fh.write(fmt_case(cid, sid) + '\n\n')
    # passing readouts where a bullet with summary/meta wording in its opening out-scores (solo) every hit bullet
    pool = sorted(k for k, bs in by_ro_nd.items() if any(b['label'] == 'hit' for b in bs) and
                  any(b['instr_head'] and b['label'] != 'hit' and
                      b['solo'] > max(h['solo'] for h in bs if h['label'] == 'hit') for b in bs))
    xr.shuffle(pool)
    fh.write(f'\n######## passing readouts where a summary-opening bullet out-scores every hit (random '
             f'{min(12, len(pool))} of {len(pool)})\n')
    for cid, sid in pool[:12]:
        fh.write(fmt_case(cid, sid) + '\n\n')

OUT_JSON.write_text(json.dumps(out, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))
log('wrote', OUT_JSON, OUT_SAMPLE, OUT_EX, 'cases', len(sample))
