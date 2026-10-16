"""User modelling (um): analyses A1-A5 of DESIGN.md section 8, plus the 36-case reading sample.

Question: do bullets that NAME the user's attribute value (gold: "Paraguayan" for a Paraguayan user) get more
per-bullet FVE than bullets that name ANOTHER value of the same attribute class (wrong value: "Ukrainian",
"Argentinian"), or only the frame ("your nationality", "your job")?

Subcommands (run from newtasks/ with PYTHONPATH=code; each is one short CPU job via code/qt.sh; no GPU, no API):
  prep     join selected atoms, per-bullet metrics, lexicon-v2 labels (full text AND the 32-token scored window),
           the pool (every bullet of the cell's 32 samples) and judge rows -> analysis/um/cache/tables.pkl
  run      A1-A5 -> analysis/um/results.json
  sample   36 reading cases -> analysis/um/read_sample.json
  show KEY [setting] [--pool]    print one case (KEY = item.L<layer>.p<pos>, setting = Original|"Best of 32"|"Combine 32")

Bullet labels (lexicon v2 = code/um_lexicon.py, sha f8ac0339...; gold g = the item's attribute value; distractors D
= the 4 other WSB um-v2 options (build_options, seed 0); class universe = every value of the class in the lexicon):
  gold     names g and no other value: a name form ("Paraguayan", "fisherman", "Buddhist", "divorced"; for Gender
           also "man", "husband", ...), a coarse region/group word covering g and no option ("South American"),
           a value cue ("kimchi", "tides", "locks") or a pronoun ("he", "her")
  wrong    names another value of the same class and not g: subtype distractor (one of D) or other_value (any
           other value: "Argentinian" for Paraguay, "teacher" for fisherman, "Asian" for Africa)
  mixed    names g and a wrong value
  frame    frame words of the class ("nationality", "job", "marital status", "pet", "continent") and no value
  none     none of these.  ambiguous (a coarse word covering g AND an option) is kept apart and unused.
Strength of a mention = its strongest hit: name (an exact form, or a coarse region word) > cue > pronoun.
  Name-level labels (labN*): gold / wrong only when the mention is a name or region word; a cue- or pronoun-only
  mention becomes gold_weak / wrong_weak.  This is the "same frame, different value" filler test.
Echo flag (in-prompt copy): a matched surface or its stem occurs in the item's messages (system + user turn), as a
  word: surfaces of >= 4 letters match as a word prefix (stem = drop up to 3 final letters, keep >= 5), shorter ones
  as a whole word (+ optional "s"). Recomputed here because the lexicon's own in_prompt flag is a plain substring test
  ("he" is found in "the", "his" in "this"); the labels themselves are the lexicon's.
  In synthsys items the system prompt states the attribute ("dialogue partner's locale is Africa"), so most synthsys
  gold mentions are echoes; in selfdescribe items echoes are copies of the user's cues ("Maori culture" -> "Māori",
  "sopa paraguaya" -> "Paraguayan" by the stem rule).
  Value echo (used for gold): in synthsys items the attribute is STATED in the system prompt, so an exact form of the
  gold value is an echo even when the surface differs (a translation "佛教" / "非洲", an inflection "widowhood",
  "post-divorce", a paraphrase "losing a spouse"); coarse words, cues and finer instances ("Kenya" for Africa, "UK"
  for Europe, "purring" for cat) stay novel unless their surface is in the prompt.
  gold_novel = some gold hit is not an echo; gold_echo = every gold hit is an echo. Wrong hits: surface rule only.
  (g_echo_s = the surface/stem rule alone, kept for a sensitivity check.)
Window labels (suffix W): the same lexicon on the scored window, i.e. the first 32 AR tokens after the AR cleanup
  (reconstruction.ar_token_ids), which is all the AR vector -- hence FVE -- can see. FVE tests (A1-A3) use window
  labels; full-text labels (suffix F) are a variant. Readout-level tests (A4, A5) use full-text labels, because the
  judge reads the full text.
Subfamilies: selfdescribe (47 items: Country, Gender, Occupation, Religion; the user states cues and asks for an
  infobox/biography "for me") and synthsys (53 items: a system prompt states the attribute; unrelated request).
Bootstrap: 2,000 reps over the 31 related-item groups attr_class:attr ("ci_groups", the primary interval) and over
  the 100 items ("ci"); all statistics of one run share the same weights, so differences are paired.
Pair rate: P(score of an A bullet > score of a B bullet in the same readout / cell pool), ties 1/2, pairs pooled.
  Position-adjusted (adj): minus the mean at the same setting, layer, readout size and list slot, for Original and
  Best of 32; Combine 32 stays raw (its order is the greedy FVE order). Length-matched: scored tokens within 20%.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pickle
import random
import re
import sys
import time
from pathlib import Path

import numpy as np

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
sys.path.insert(0, str(NT / 'code'))
import ntcommon as C  # noqa: E402

C.setup_paths()
import um_lexicon as L  # noqa: E402

OUT = NT / 'analysis/um'
CACHE = OUT / 'cache'
FAM = 'user_modeling'
SETTINGS = C.SETTINGS
SL = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
LS = {v: k for k, v in SL.items()}
LAYERS = C.LAYERS
SEED = 20261016
B_BOOT = 2000
KIND_RANK = {'exact': 0, 'coarse': 1, 'cue': 2, 'pronoun': 3}
GROUP_OF_LABEL = {'gold_exact': 'gold', 'gold_coarse': 'gold', 'wrong_value': 'wrong', 'mixed': 'mixed',
                  'frame_only': 'frame', 'none': 'none', 'ambiguous': 'ambiguous'}
STOP = set('that this with from have your what about some like would could them they their there when which will been '
           'into than then just more most very also make want need here were where while being does dont i\'m you\'re '
           'it\'s that\'s please help know think really should these those only other such each over under after '
           'before because since many much well good great best sure'.split())
AR_CLEAN = re.compile(r"</?explanation>|<\|im_start\|>(system|user|assistant)?|<\|im_end\|>|<think>|</think>")
CJK = re.compile(r'[㐀-鿿]')
FIELD = re.compile(r'^\W{0,3}\**[\w 㐀-鿿]{1,24}\**\s*[:：]')


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def case_key(cell_id):
    _, item, lay, p = cell_id.split('|')
    return f'{item}.{lay}.p{int(p[1:])}'


def group_of(it):
    return f"{it['attr_class']}:{it['attr']}"


# ----------------------------------------------------------------------------------------------- label features
FEAT_COLS = ('grp', 'grpN', 'sub', 'gk', 'wk', 'g_novel', 'g_echo', 'g_name_novel', 'w_novel', 'w_echo', 'w_distr',
             'gvals', 'wvals', 'surfs', 'ocls', 'g_echo_s')


_ECHO_CACHE = {}


def echo_surface(surface, pf):
    """The surface (or its stem) occurs in the folded prompt pf as a word (see module docstring)."""
    k = (surface, pf)
    if k not in _ECHO_CACHE:
        s = re.sub(r'[\s\-]+', ' ', L._fold(surface)).strip()
        if not s or CJK.search(s):
            hit = False
        elif len(s) < 4:
            hit = re.search(r'(?<![a-z0-9])' + re.escape(s) + r's?(?![a-z0-9])', pf) is not None
        else:
            stem = s[:max(5, len(s) - 3)] if len(s) >= 6 else s
            hit = re.search(r'(?<![a-z0-9])' + re.escape(stem), pf) is not None
        _ECHO_CACHE[k] = hit
    return _ECHO_CACHE[k]


def fold_prompt(prompt):
    return re.sub(r'[\s\-]+', ' ', L._fold(prompt))


def derive(r, stated, pf):
    """Compact per-text features from a um_lexicon.label_bullet result (see module docstring).
    stated: the item's prompt states the attribute (synthsys), so exact gold forms are value echoes.
    pf: the item's folded prompt (for the word-boundary echo test)."""
    gh, wh = r['gold_hits'], r['wrong_hits']
    for h in gh + wh:
        h['in_prompt'] = echo_surface(h['surface'], pf)

    def echo(h):
        return bool(h['in_prompt']) or (stated and h['match'] == 'exact')
    grp = GROUP_OF_LABEL[r['label']]
    g_name = any(KIND_RANK[h['match']] <= 1 for h in gh)
    w_name = any(KIND_RANK[h['kind']] <= 1 for h in wh)
    if grp == 'gold':
        grpN = 'gold' if g_name else 'gold_weak'
    elif grp == 'wrong':
        grpN = 'wrong' if w_name else 'wrong_weak'
    else:
        grpN = grp
    gk = min((h['match'] for h in gh), key=KIND_RANK.get, default='')
    wk = min((h['kind'] for h in wh), key=KIND_RANK.get, default='')
    return (grp, grpN, r['subtype'] or '', gk, wk,
            bool(gh) and any(not echo(h) for h in gh),
            bool(gh) and all(echo(h) for h in gh),
            any(KIND_RANK[h['match']] <= 1 and not echo(h) for h in gh),
            bool(wh) and any(not h['in_prompt'] for h in wh),
            bool(wh) and all(h['in_prompt'] for h in wh),
            any(h['subtype'] == 'distractor' for h in wh),
            # value ids named by NAME forms (exact kind) -- for the consensus / two-direction tests
            tuple(sorted({h['value'] for h in gh if h['match'] == 'exact'})),
            tuple(sorted({h['value'] for h in wh if h['kind'] == 'exact' and 'value' in h})),
            tuple(sorted({h['surface'] for h in gh + wh + r.get('ambiguous', [])}, key=len, reverse=True)),
            bool(r['other_class']),
            bool(gh) and all(h['in_prompt'] for h in gh))


def opening(text, k):
    w = re.findall(r"[\w']+", text.lower())
    return ' '.join(w[:k]) if len(w) >= k else None


def masked(text, surfs):
    """Window text with every value surface replaced by VAL -> lower-cased word list (frame-with-value-masked)."""
    t = text
    for s in surfs:
        t = re.sub(re.escape(s), ' VAL ', t, flags=re.I)
    return re.findall(r"[\w']+", t.lower())


def prompt_words(prompt):
    return set(re.findall(r"[a-z]{4,}", L._fold(prompt))) - STOP


def overlap(text, pw):
    ws = [w for w in re.findall(r"[a-z]{4,}", L._fold(text)) if w not in STOP]
    return (sum(w in pw for w in ws) / len(ws)) if ws else 0.0


# ----------------------------------------------------------------------------------------------- prep
def contexts(bank):
    from wsbench.evals.user_modeling.judge import build_options
    opts = build_options(list(bank.values()))
    out = {}
    for k, it in bank.items():
        c = L.item_context(it, opts[k])
        c.update({'subfamily': it['subfamily'], 'group': group_of(it), 'options': opts[k][0],
                  'gold_position': opts[k][1], 'pw': prompt_words(c['prompt']), 'pf': fold_prompt(c['prompt'])})
        out[k] = c
    return out


def cmd_prep(args):
    import pandas as pd
    from transformers import AutoTokenizer
    t0 = time.time()
    bank = C.load_bank(FAM)
    ctx = contexts(bank)
    summ = json.loads((C.DATA / 'labels/um_label_summary.json').read_text())
    lex_sha = C.file_sha(L.__file__)
    if summ['lexicon_sha256'] != lex_sha:
        raise SystemExit(f'lexicon changed since labelling: {summ["lexicon_sha256"]} vs {lex_sha}')
    tok = AutoTokenizer.from_pretrained(str(C.BASE))
    special = set(tok.all_special_ids)

    # --- full-text labels (um_text_labels.jsonl, key = sha(item \0 raw text)[:20])
    log('text labels')
    feat = {}
    with open(C.DATA / 'labels/um_text_labels.jsonl') as f:
        for ln in f:
            r = json.loads(ln)
            c = ctx[r['item_id']]
            feat[r['key']] = derive(r, c['subfamily'] == 'synthsys', c['pf'])
    log('text labels', len(feat))
    from label_um import text_key

    # --- pool (every bullet of the 32 samples; first 4 per sample)
    meta = {}
    three = list(C.read_jsonl(C.DATA / 'select/um_three_settings.jsonl'))
    for r in three:
        meta[r['cell_id']] = r
    prow, ptext = [], []
    for pe in C.read_jsonl(C.DATA / 'select/um_pool.jsonl'):
        r = meta[pe['cell_id']]
        for b in pe['bullets']:
            prow.append((pe['cell_id'], r['item_id'], r['layer'], r['position'], b['sample_index'], b['pos'],
                         b['phrase_id'], b['cache_key'], b['solo_fve']))
            ptext.append(b['text'])
    log('pool bullets', len(prow))
    # scored window (first 32 AR tokens after cleanup), tokenized once per distinct text
    uniq = sorted(set(ptext))
    cleaned = [AR_CLEAN.sub('', t).strip() for t in uniq]
    enc = tok(cleaned, add_special_tokens=False)['input_ids']
    win = {}
    for t, c, ids in zip(uniq, cleaned, enc):
        ids = [x for x in ids if x not in special]
        win[t] = (min(len(ids), 32), len(ids) > 32, tok.decode(ids[:32]) if len(ids) > 32 else c)
    log('tokenized', len(uniq))
    # window labels: re-label only truncated windows (otherwise window == full text)
    wfeat = {}
    n_relab = 0
    for (cid, item_id, *_), t in zip(prow, ptext):
        k = text_key(item_id, t)
        if k not in feat:
            raise SystemExit(f'no label for pool text {cid} {t[:60]!r}')
        stok, trunc, w = win[t]
        if not trunc:
            continue
        kk = (item_id, w)
        if kk not in wfeat:
            c = ctx[item_id]
            wfeat[kk] = derive(L.label_bullet(w, c['cls'], c['gold'], c['distractors'], c['prompt']),
                               c['subfamily'] == 'synthsys', c['pf'])
            n_relab += 1
    log('window relabelled', n_relab)
    rows = []
    for (cid, item_id, lay, pos, si, bpos, pid, ck, solo), t in zip(prow, ptext):
        stok, trunc, w = win[t]
        fF = feat[text_key(item_id, t)]
        fW = wfeat[(item_id, w)] if trunc else fF
        c = ctx[item_id]
        mw = masked(w, fW[13])
        rows.append((cid, item_id, c['group'], c['subfamily'], c['cls'], lay, pos, si, bpos, pid, ck, solo, t.strip(), w,
                     stok, trunc, *fF, *fW, bool(CJK.match(w.lstrip())), bool(CJK.search(w)),
                     bool(re.match(r'\s*[^\w\s]', w)) and not bool(CJK.match(w.lstrip())), bool(FIELD.match(w)),
                     overlap(w, c['pw']), opening(w, 2), opening(w, 3), ' '.join(mw[:4]) if len(mw) >= 4 else None,
                     ' '.join(mw)))
    cols = (['cell_id', 'item_id', 'group', 'subfamily', 'attr_class', 'layer', 'position', 'sample_index', 'pos',
             'phrase_id', 'cache_key', 'solo', 'text', 'window', 'stok', 'trunc']
            + [c + 'F' for c in FEAT_COLS] + [c + 'W' for c in FEAT_COLS]
            + ['cjk_lead', 'cjk_any', 'punct_open', 'field_open', 'overlap', 'open2', 'open3', 'mopen4', 'mfull'])
    pool = pd.DataFrame(rows, columns=cols)
    site = {cid: (r['read_position_kind'], r['rel_from_end'], r.get('token')) for cid, r in meta.items()}
    pool['site'] = pool.cell_id.map(lambda c: site[c][0])
    log('pool frame', pool.shape)

    # --- selected readouts: atoms joined to pool rows by phrase id, metrics, judge rows
    met = {}
    for lay in LAYERS:
        for r in C.read_jsonl(C.DATA / f'metrics/um_bullet_metrics.L{lay}.jsonl'):
            for sid, s in r['settings'].items():
                met[(r['cell_id'], sid)] = s
    pidx = {pid: k for k, pid in enumerate(pool.phrase_id)}
    judge = {}
    for sid in SETTINGS:
        for v in C.read_jsonl(C.DATA / f'judge/um/{sid}/um_cell_rows.jsonl'):
            judge[(v['cell_id'], sid)] = v
    try:
        R0 = pd.read_pickle(CACHE / 'readouts.pkl')  # judge_vs_labels.py prep: evidence re-located per fragment
        ev = {(c, s): (bool(f), list(b)) for c, s, f, b in zip(R0.cell_id, R0.setting, R0.ev_found, R0.ev_bullets)}
    except FileNotFoundError:
        ev = {}
    srows = []
    n_missing_pool, stok_mism, win_mism, n_win_checked = 0, 0, 0, 0
    for r in three:
        cid = r['cell_id']
        for sid in SETTINGS:
            s = r['settings'][sid]
            ms = met.get((cid, sid))
            mb = {b['phrase_id']: b for b in ms['bullets']} if ms and ms.get('bullets') else {}
            j = judge.get((cid, sid), {})
            evf, evb = ev.get((cid, sid), (False, []))
            nb = len(s['atoms'])
            for i, a in enumerate(s['atoms']):
                pid = a['source_phrase_id']
                k = pidx.get(pid)
                if k is None:
                    n_missing_pool += 1
                    continue
                if a['scored_token_count'] != pool.stok.iat[k]:
                    stok_mism += 1
                if a['truncated']:  # the AR input = the atoms' scored_token_ids (scored_text is a looser char span)
                    n_win_checked += 1
                    if tok.decode(a['scored_token_ids']).strip() != pool.window.iat[k].strip():
                        win_mism += 1
                b = mb.get(pid, {})
                srows.append({'pidx': k, 'cell_id': cid, 'setting': sid, 'idx': i, 'nb': nb,
                              'atom_text': a['text'], 'joint': ms.get('joint_fve_saved') if ms else None,
                              'solo_m': b.get('solo_fve'), 'share': b.get('shapley_share'), 'shapley': b.get('shapley'),
                              'drop': b.get('loo_drop'), 'coef': b.get('coefficient'), 'dup': b.get('dup'),
                              'judge_pick': j.get('pick'), 'judge_basis': j.get('basis'),
                              'judge_value': j.get('pick_value'), 'judge_evidence': j.get('evidence'),
                              'ev_found': evf, 'judge_ev': i in evb})
    sel = pd.DataFrame(srows)
    base = pool.drop(columns=['solo']).iloc[sel.pidx.to_numpy()].reset_index(drop=True)
    sel = pd.concat([sel.reset_index(drop=True), base.drop(columns=['cell_id'])], axis=1)
    sel['solo'] = sel.solo_m
    sel['solo_pool'] = pool.solo.to_numpy()[sel.pidx.to_numpy()]
    solo_diff = float(np.nanmax(np.abs(sel.solo.astype(float) - sel.solo_pool.astype(float))))
    log('max |metrics solo - pool solo|', solo_diff)
    sel['key'] = sel.cell_id.map(case_key)
    sel['text_match'] = [a.strip() == t for a, t in zip(sel.atom_text, sel.text)]
    log('selected bullets', len(sel), 'missing in pool', n_missing_pool, 'stok mismatch', stok_mism,
        'window mismatch', win_mism, 'of', n_win_checked, 'text mismatch', int((~sel.text_match).sum()))
    # sample-level joint FVE (Best of 32 trace) for all 32 samples
    srow = []
    for r in three:
        for t in r['settings']['best_n_exact-n32']['trace']:
            srow.append((r['cell_id'], int(t['sample_id'].rsplit(':', 1)[1]), t.get('score')))
    samples = pd.DataFrame(srow, columns=['cell_id', 'sample_index', 'joint'])
    CACHE.mkdir(parents=True, exist_ok=True)
    with open(CACHE / 'tables.pkl', 'wb') as f:
        pickle.dump({'sel': sel, 'pool': pool, 'samples': samples, 'site': site,
                     'meta': {'lexicon_sha256': lex_sha, 'pool_rows': int(len(pool)), 'selected_rows': int(len(sel)),
                              'selected_missing_in_pool': n_missing_pool, 'stok_mismatch_vs_atoms': stok_mism,
                              'window_text_mismatch_vs_atoms': win_mism, 'window_checked': n_win_checked,
                              'atom_text_mismatch': int((~sel.text_match).sum()),
                              'max_abs_metrics_solo_minus_pool_solo': solo_diff,
                              'pool_truncated_share': round(float(pool.trunc.mean()), 4),
                              'window_relabelled_texts': n_relab, 'built': time.strftime('%Y-%m-%d %H:%M:%S')}},
                    f, protocol=5)
    log('wrote', CACHE / 'tables.pkl', f'{time.time() - t0:.0f}s')
    print(pool.groupby('grpW').size().to_string())
    print(pd.crosstab(pool.grpF, pool.grpW).to_string())
    print(sel.groupby(['setting', 'grpW']).size().unstack(fill_value=0).to_string())


def load_tables():
    with open(CACHE / 'tables.pkl', 'rb') as f:
        return pickle.load(f)


# ----------------------------------------------------------------------------------------------- bootstrap
class Boot:
    """Ratio-of-sums bootstrap over items (100) and related-item groups (31, attr_class:attr); the same weights for
    every statistic, so differences are paired."""

    def __init__(self, item_group, B=B_BOOT, seed=SEED):
        self.items = sorted(item_group)
        self.ii = {it: k for k, it in enumerate(self.items)}
        self.cl = sorted(set(item_group.values()))
        self.icl = np.array([self.cl.index(item_group[it]) for it in self.items])
        rng = np.random.default_rng(seed)
        n, m = len(self.items), len(self.cl)
        self.Wi = rng.multinomial(n, np.full(n, 1 / n), size=B).astype(float)
        self.Wc = rng.multinomial(m, np.full(m, 1 / m), size=B).astype(float)

    def agg(self, items, num, den=None):
        idx = np.array([self.ii[i] for i in items], dtype=int)
        num = np.asarray(num, float)
        den = np.ones_like(num) if den is None else np.asarray(den, float)
        n = len(self.items)
        return np.bincount(idx, num, n), np.bincount(idx, den, n)

    def _reps(self, N, D):
        m = len(self.cl)
        Nc, Dc = np.bincount(self.icl, N, m), np.bincount(self.icl, D, m)
        with np.errstate(invalid='ignore', divide='ignore'):
            return (self.Wi @ N) / (self.Wi @ D), (self.Wc @ Nc) / (self.Wc @ Dc)

    def ratio(self, N, D, nd=3):
        if D.sum() <= 0:
            return {'est': None, 'n': 0, 'items': 0}
        ri, rc = self._reps(N, D)
        Dc = np.bincount(self.icl, D, len(self.cl))
        return {'est': round(float(N.sum() / D.sum()), nd), 'ci_groups': _ci(rc, nd), 'ci': _ci(ri, nd),
                'n': round(float(D.sum()), 2), 'items': int((D > 0).sum()), 'groups': int((Dc > 0).sum())}

    def diff(self, N1, D1, N2, D2, nd=3):
        if D1.sum() <= 0 or D2.sum() <= 0:
            return {'est': None}
        a, ac = self._reps(N1, D1)
        b, bc = self._reps(N2, D2)
        return {'est': round(float(N1.sum() / D1.sum() - N2.sum() / D2.sum()), nd), 'ci_groups': _ci(ac - bc, nd),
                'ci': _ci(a - b, nd)}

    def mean(self, items, x, nd=4):
        return self.ratio(*self.agg(items, x), nd=nd)


def _ci(x, nd):
    x = x[np.isfinite(x)]
    if not len(x):
        return None
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [round(float(lo), nd), round(float(hi), nd)]


def _r(x, nd=4):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if np.isfinite(x) else None


# ----------------------------------------------------------------------------------------------- pair rates
def group_pairs(gid, items, score, isA, isB, match=None, toks=None, tol=None, ck=None):
    """Within each group (readout or cell): wins (A > B, ties 1/2) and pairs, optionally only matched pairs.
    match: int codes (-1 = no key, never matches); toks + tol: |tA - tB| <= tol * max; ck: skip identical vectors.
    Returns (group items, wins, pairs, group ids) for groups with >= 1 pair."""
    order = np.argsort(gid, kind='stable')
    g = gid[order]
    bounds = np.flatnonzero(np.diff(g)) + 1
    starts = np.r_[0, bounds]
    ends = np.r_[bounds, len(g)]
    out_items, out_w, out_p, out_g = [], [], [], []
    sA, sB = isA[order], isB[order]
    for s, e in zip(starts, ends):
        if not sA[s:e].any() or not sB[s:e].any():
            continue
        sl = order[s:e]
        a = sl[sA[s:e]]
        b = sl[sB[s:e]]
        d = score[a][:, None] - score[b][None, :]
        ok = np.isfinite(d)
        if match is not None:
            ok &= (match[a][:, None] == match[b][None, :]) & (match[a][:, None] >= 0)
        if toks is not None:
            ta, tb = toks[a][:, None], toks[b][None, :]
            ok &= np.abs(ta - tb) <= tol * np.maximum(ta, tb)
        if ck is not None:
            ok &= ck[a][:, None] != ck[b][None, :]
        p = ok.sum()
        if not p:
            continue
        w = ((d > 0) & ok).sum() + 0.5 * ((d == 0) & ok).sum()
        out_items.append(items[sl[0]])
        out_w.append(w)
        out_p.append(p)
        out_g.append(g[s])
    return out_items, np.array(out_w, float), np.array(out_p, float), out_g


def pair_stat(bt, gid, items, score, isA, isB, **kw):
    """Pooled pair rate (all pairs) and mean per-group AUROC (each readout/cell weighted equally)."""
    it, w, p, _ = group_pairs(gid, items, score, isA, isB, **kw)
    if not len(p):
        return {'pooled': {'est': None, 'n': 0}, 'groups': 0, 'pairs': 0}
    N, D = bt.agg(it, w, p)
    Na, Da = bt.agg(it, w / p)
    return {'pooled': bt.ratio(N, D), 'per_group_mean': bt.ratio(Na, Da), 'groups': len(p), 'pairs': int(p.sum())}


def codes(series):
    """String keys -> int codes; None/NaN -> -1 (never matches)."""
    return series.astype('category').cat.codes.to_numpy().astype(int)


# ----------------------------------------------------------------------------------------------- FE regression
def fe_reg(bt, d, fe_col, y_col, xcols, contrasts, nd=4):
    """OLS of y on X after demeaning within fe_col (readout or cell fixed effects). CIs by bootstrapping per-item
    sufficient statistics (X'X, X'y) over items and over groups. contrasts: {name: {col: weight}}."""
    d = d[[fe_col, 'item_id', y_col] + list(xcols)].dropna()
    M = d[[y_col] + list(xcols)].astype(float)
    M = M - M.groupby(d[fe_col].to_numpy()).transform('mean')
    Y = M[y_col].to_numpy()
    X = M[list(xcols)].to_numpy()
    keep = np.abs(X).sum(0) > 0
    xcols = [c for c, k in zip(xcols, keep) if k]
    X = X[:, keep]
    k = X.shape[1]
    ii = np.array([bt.ii[i] for i in d.item_id])
    n = len(bt.items)
    XtX = np.zeros((n, k, k))
    Xty = np.zeros((n, k))
    for i in np.unique(ii):
        m = ii == i
        XtX[i] = X[m].T @ X[m]
        Xty[i] = X[m].T @ Y[m]
    ridge = 1e-9 * np.eye(k)
    beta = np.linalg.solve(XtX.sum(0) + ridge, Xty.sum(0))

    def reps(W, A, b):
        AA = (W @ A.reshape(len(A), -1)).reshape(-1, k, k) + ridge
        bb = W @ b
        return np.linalg.solve(AA, bb[..., None])[..., 0]
    m = len(bt.cl)
    Ag = np.zeros((m, k, k))
    bg = np.zeros((m, k))
    for i in range(n):
        Ag[bt.icl[i]] += XtX[i]
        bg[bt.icl[i]] += Xty[i]
    Bi, Bc = reps(bt.Wi, XtX, Xty), reps(bt.Wc, Ag, bg)
    out = {'n': int(len(d)), 'fe_units': int(d[fe_col].nunique()), 'within_sd_y': round(float(Y.std()), 4),
           'coef': {c: {'est': round(float(beta[j]), nd), 'ci': _ci(Bi[:, j], nd), 'ci_groups': _ci(Bc[:, j], nd)}
                    for j, c in enumerate(xcols)}}
    con = {}
    for name, wts in contrasts.items():
        v = np.array([wts.get(c, 0.0) for c in xcols])
        if not any(c in xcols for c in wts):
            continue
        con[name] = {'est': round(float(v @ beta), nd), 'ci': _ci(Bi @ v, nd), 'ci_groups': _ci(Bc @ v, nd)}
    out['contrasts'] = con
    return out


# ----------------------------------------------------------------------------------------------- derived columns
def add_derived(sel):
    # position-adjusted scores (Original / Best of 32): minus the mean at the same setting, layer, readout size, list
    # slot. Combine 32 stays raw (its order is the greedy FVE order).
    for col in ('solo', 'share', 'drop'):
        mu = sel.groupby(['setting', 'layer', 'nb', 'idx'])[col].transform('mean')
        sel[col + '_adj'] = np.where(sel.setting == 'pooled_greedy_swap-n32', sel[col], sel[col] - mu)
    sel['solo_pct'] = sel.groupby(['setting', 'layer']).solo.rank(pct=True)
    return sel


def pool_frame(pool):
    p = pool[pool.solo.notna()].drop_duplicates(['cell_id', 'cache_key']).reset_index(drop=True)
    p['solo_cell_dm'] = p.solo - p.groupby('cell_id').solo.transform('mean')
    return p


LABS = ('gold', 'wrong', 'mixed', 'frame', 'none')


# ----------------------------------------------------------------------------------------------- run
def cmd_run(args):
    t0 = time.time()
    T = load_tables()
    sel = add_derived(T['sel'])
    pool = T['pool']
    bank = C.load_bank(FAM)
    bt = Boot({k: group_of(it) for k, it in bank.items()})
    R = {'meta': {**T['meta'], 'bootstrap': {'B': B_BOOT, 'seed': SEED,
                                             'units': 'ci_groups = 31 related-item groups attr_class:attr (primary); '
                                                      'ci = 100 items'}}}
    sc = sel[sel.solo.notna()].copy()
    p = pool_frame(pool)
    R['label_counts'] = {
        'selected_window': {SL[s]: sc[sc.setting == s].grpW.value_counts().to_dict() for s in SETTINGS},
        'selected_window_namelevel': {SL[s]: sc[sc.setting == s].grpNW.value_counts().to_dict() for s in SETTINGS},
        'selected_full': {SL[s]: sc[sc.setting == s].grpF.value_counts().to_dict() for s in SETTINGS},
        'pool_window': p.grpW.value_counts().to_dict(), 'pool_window_namelevel': p.grpNW.value_counts().to_dict(),
        'pool_full': p.grpF.value_counts().to_dict(),
        'pool_full_x_window': {f'{a}|{b}': int(n) for (a, b), n in p.groupby(['grpF', 'grpW']).size().items()},
        'pool_gold_window_by_subfamily_echo': {
            f'{sf}|{"echo" if e else "novel"}': int(n) for (sf, e), n in
            p[p.grpW == 'gold'].groupby(['subfamily', 'g_echoW']).size().items()},
        'pool_gold_window_kind': p[p.grpW == 'gold'].gkW.value_counts().to_dict(),
        'pool_wrong_window_kind': p[p.grpW == 'wrong'].wkW.value_counts().to_dict(),
        'pool_wrong_window_subtype': p[p.grpW == 'wrong'].subW.value_counts().to_dict(),
        'pool_wrong_window_echo': int(p[(p.grpW == 'wrong')].w_echoW.sum()),
        'pool_dedup_bullets': int(len(p)),
    }
    log('A1')
    R['A1'] = run_a1(bt, sc, p)
    log('A2')
    R['A2'] = run_a2(bt, sc)
    log('A3')
    R['A3'] = run_a3(bt, p)
    log('A4')
    R['A4'] = run_a4(bt, sel, pool, T['samples'])
    log('A5')
    R['A5'] = run_a5(bt, sel)
    R['meta']['runtime_s'] = round(time.time() - t0, 1)
    C.atomic_json(OUT / 'results.json', R)
    log('wrote', OUT / 'results.json')


# ----------------------------------------------------------------------------------------------- A1
def run_a1(bt, sc, p):
    out = {'note': ('mean per-bullet metric by WINDOW label (what the AR sees); selected readouts with metrics; pool = '
                    'every deduplicated bullet of the 32 samples (solo FVE only). within_cell = pool solo FVE minus the '
                    'cell mean (removes layer / site / item composition).')}
    pairs = (('gold', 'wrong'), ('gold', 'frame'), ('gold', 'none'), ('wrong', 'frame'), ('frame', 'none'))

    def table(d, metric, labcol='grpW', labs=LABS):
        row, NDs = {}, {}
        for lab in labs:
            m = (d[labcol] == lab).to_numpy()
            NDs[lab] = bt.agg(d.item_id.to_numpy()[m], d[metric].to_numpy(float)[m])
            row[lab] = bt.ratio(*NDs[lab], nd=4)
        for a, b in pairs:
            if a in NDs and b in NDs:
                row[f'{a}-{b}'] = bt.diff(*NDs[a], *NDs[b], nd=4)
        return row
    for metric in ('solo', 'share', 'drop'):
        t = {}
        for s in SETTINGS:
            d = sc[sc.setting == s]
            t[SL[s]] = table(d, metric)
            for lay in LAYERS:
                t[f'{SL[s]}|L{lay}'] = table(d[d.layer == lay], metric)
            for sf in ('selfdescribe', 'synthsys'):
                t[f'{SL[s]}|{sf}'] = table(d[d.subfamily == sf], metric)
        t['all_settings|full_text_labels'] = table(sc, metric, 'grpF')
        out[metric] = t
    # gold split by echo and by mention strength (selected, all settings)
    g = sc[sc.grpW == 'gold'].copy()
    g['split'] = np.where(g.g_echoW, 'gold_echo', 'gold_novel')
    out['solo_gold_by_echo_x_subfamily'] = {f'{sf}|{k}': bt.mean(d.item_id, d.solo) for (sf, k), d in
                                            g.groupby(['subfamily', 'split'])}
    out['solo_gold_by_kind'] = {k: bt.mean(d.item_id, d.solo) for k, d in g.groupby('gkW')}
    # pool
    pr = {}
    for key, d in [('all', p)] + [(f'L{lay}', p[p.layer == lay]) for lay in LAYERS] + \
            [(sf, p[p.subfamily == sf]) for sf in ('selfdescribe', 'synthsys')]:
        pr[key] = {'raw': table(d, 'solo'), 'within_cell': table(d, 'solo_cell_dm')}
    out['pool_solo'] = pr
    pg = p[p.grpW == 'gold'].copy()
    pg['split'] = np.where(pg.g_echoW, 'gold_echo', 'gold_novel')
    out['pool_within_cell_gold_by_echo_x_subfamily'] = {f'{sf}|{k}': bt.mean(d.item_id, d.solo_cell_dm)
                                                        for (sf, k), d in pg.groupby(['subfamily', 'split'])}
    out['pool_within_cell_wrong_by_subtype'] = {k: bt.mean(d.item_id, d.solo_cell_dm)
                                                for k, d in p[p.grpW == 'wrong'].groupby('subW')}
    out['pool_within_cell_by_site'] = {st: {lab: bt.mean(d[d.grpW == lab].item_id, d[d.grpW == lab].solo_cell_dm)
                                            for lab in ('gold', 'wrong', 'frame', 'none')} for st, d in p.groupby('site')}
    out['pool_within_cell_sd'] = round(float(p.solo_cell_dm.std()), 4)
    out['gold_rate_by_layer_pool'] = {f'L{lay}': round(float((p[p.layer == lay].grpW == 'gold').mean()), 4)
                                      for lay in LAYERS}
    out['mean_solo_by_layer_pool'] = {f'L{lay}': round(float(p[p.layer == lay].solo.mean()), 4) for lay in LAYERS}
    return out


# ----------------------------------------------------------------------------------------------- A2
def readout_gid(d):
    return codes(d.cell_id + '|' + d.setting)


def run_a2(bt, sc):
    out = {'note': ('within one readout: pair rate of A over B; adj = position-adjusted for Original / Best of 32, raw '
                    'for Combine 32; len = scored tokens within 20%; labels on the scored window. name = name-level '
                    'labels (cue- and pronoun-only mentions excluded); novel = gold bullet has a gold hit not in the '
                    'prompt (echo-only gold excluded)')}
    NONGOLD = ('wrong', 'wrong_weak', 'frame', 'none', 'ambiguous')
    comps = {
        'gold_vs_nongold': ('gold', NONGOLD),
        'gold_vs_wrong': ('gold', ('wrong',)),
        'gold_vs_frame': ('gold', ('frame',)),
        'gold_vs_none': ('gold', ('none',)),
        'wrong_vs_frame': ('wrong', ('frame',)),
        'wrong_vs_none': ('wrong', ('none',)),
        'frame_vs_none': ('frame', ('none',)),
    }
    variants = {'solo_raw': ('solo', False), 'solo_adj': ('solo_adj', False), 'solo_adj_len': ('solo_adj', True),
                'share_adj': ('share_adj', False), 'share_adj_len': ('share_adj', True), 'drop_adj': ('drop_adj', False)}

    def labcol(d, sub):
        """Analysis label for a subset: name-level labels for 'name*', and echo-only gold dropped for '*novel'."""
        lab = (d.grpNW if sub.startswith('name') else d.grpW).copy()
        if sub.endswith('novel'):
            lab = lab.where(~((lab == 'gold') & d.g_echoW), 'gold_echo_excluded')
        return lab

    def run(d, sub, A, Bs, score, lenm):
        lab = labcol(d, sub)
        isA = (lab == A).to_numpy()
        isB = lab.isin(Bs).to_numpy()
        kw = {'toks': d.stok.to_numpy(float), 'tol': 0.2} if lenm else {}
        return pair_stat(bt, readout_gid(d), d.item_id.to_numpy(), d[score].to_numpy(float), isA, isB,
                         ck=codes(d.cache_key), **kw)
    subsets = {'all': lambda d: d, 'selfdescribe': lambda d: d[d.subfamily == 'selfdescribe'],
               'synthsys': lambda d: d[d.subfamily == 'synthsys'], 'name': lambda d: d, 'novel': lambda d: d,
               'name_novel': lambda d: d}
    for name, (A, Bs) in comps.items():
        res = {}
        for sub, f in subsets.items():
            d0 = f(sc)
            vs = variants if sub == 'all' or name in ('gold_vs_wrong', 'gold_vs_nongold') else \
                {k: variants[k] for k in ('solo_adj', 'solo_adj_len')}
            for vname, (score, lenm) in vs.items():
                row = {SL[s]: run(d0[d0.setting == s], sub, A, Bs, score, lenm) for s in SETTINGS}
                row['pooled'] = run(d0, sub, A, Bs, score, lenm)
                res[f'{sub}|{vname}'] = row
        out[name] = res
    # top-share bullet is gold, vs chance (readouts with some but not all gold, no mixed)
    top = {}
    for s in SETTINGS:
        d = sc[(sc.setting == s) & (sc.grpW != 'mixed')]
        its, hit, ch = [], [], []
        for cid, g in d.groupby('cell_id'):
            ng = int((g.grpW == 'gold').sum())
            if 0 < ng < len(g):
                its.append(g.item_id.iloc[0])
                hit.append(float(g.grpW.iloc[int(np.argmax(g.share.to_numpy()))] == 'gold'))
                ch.append(ng / len(g))
        N1, D1 = bt.agg(its, hit)
        N2, D2 = bt.agg(its, ch)
        top[SL[s]] = {'top_is_gold': bt.ratio(N1, D1), 'chance': bt.ratio(N2, D2),
                      'minus_chance': bt.diff(N1, D1, N2, D2), 'readouts': len(its)}
    out['top_share_is_gold'] = top
    # readout fixed-effects regression of solo FVE on labels (+ list slot, log length)
    d = sc.copy()
    for lab in ('gold', 'wrong', 'mixed', 'frame'):
        d[f'L_{lab}'] = (d.grpW == lab).astype(float)
    d['L_gold_echo'] = ((d.grpW == 'gold') & d.g_echoW).astype(float)
    d['L_gold_novel'] = ((d.grpW == 'gold') & ~d.g_echoW).astype(float)
    for k in (1, 2, 3):
        d[f'slot{k}'] = (d.idx == k).astype(float)
    d['logtok'] = np.log(d.stok.clip(lower=1))
    d['rid'] = d.cell_id + '|' + d.setting
    con = {'gold-wrong': {'L_gold': 1, 'L_wrong': -1}, 'gold-frame': {'L_gold': 1, 'L_frame': -1},
           'wrong-frame': {'L_wrong': 1, 'L_frame': -1}, 'gold-none': {'L_gold': 1}}
    con2 = {'gold_novel-wrong': {'L_gold_novel': 1, 'L_wrong': -1}, 'gold_echo-wrong': {'L_gold_echo': 1, 'L_wrong': -1},
            'gold_novel-frame': {'L_gold_novel': 1, 'L_frame': -1}, 'gold_echo-gold_novel': {'L_gold_echo': 1, 'L_gold_novel': -1}}
    ob = d[d.setting != 'pooled_greedy_swap-n32']
    cb = d[d.setting == 'pooled_greedy_swap-n32']
    out['readout_fe_regression'] = {
        'Original+Best of 32': fe_reg(bt, ob, 'rid', 'solo', ['L_gold', 'L_wrong', 'L_mixed', 'L_frame', 'slot1', 'slot2',
                                                             'slot3', 'logtok'], con),
        'Combine 32': fe_reg(bt, cb, 'rid', 'solo', ['L_gold', 'L_wrong', 'L_mixed', 'L_frame', 'logtok'], con),
        'Original+Best of 32|echo_split': fe_reg(bt, ob, 'rid', 'solo', ['L_gold_novel', 'L_gold_echo', 'L_wrong',
                                                                        'L_mixed', 'L_frame', 'slot1', 'slot2', 'slot3',
                                                                        'logtok'], con2),
        'Combine 32|echo_split': fe_reg(bt, cb, 'rid', 'solo', ['L_gold_novel', 'L_gold_echo', 'L_wrong', 'L_mixed',
                                                               'L_frame', 'logtok'], con2),
    }
    # confounds: is gold later / longer than its siblings; mean solo by slot; gold share by slot
    conf = {}
    for s in SETTINGS:
        d = sc[sc.setting == s]
        isA = (d.grpW == 'gold').to_numpy()
        isB = d.grpW.isin(NONGOLD).to_numpy()
        isW = (d.grpW == 'wrong').to_numpy()
        conf[SL[s]] = {
            'gold_later_than_sibling': pair_stat(bt, readout_gid(d), d.item_id.to_numpy(), d.idx.to_numpy(float), isA, isB)['pooled'],
            'gold_longer_than_sibling': pair_stat(bt, readout_gid(d), d.item_id.to_numpy(), d.stok.to_numpy(float), isA, isB)['pooled'],
            'gold_later_than_wrong': pair_stat(bt, readout_gid(d), d.item_id.to_numpy(), d.idx.to_numpy(float), isA, isW)['pooled'],
            'gold_longer_than_wrong': pair_stat(bt, readout_gid(d), d.item_id.to_numpy(), d.stok.to_numpy(float), isA, isW)['pooled'],
            'mean_solo_by_slot': {int(k): round(float(v), 4) for k, v in d.groupby('idx').solo.mean().items()},
            'gold_share_by_slot': {int(k): round(float(v), 4) for k, v in d.groupby('idx').grpW.apply(lambda x: (x == 'gold').mean()).items()},
        }
    out['confounds'] = conf
    return out


# ----------------------------------------------------------------------------------------------- A3
def run_a3(bt, p):
    out = {'note': ('pool = every bullet of the cell\'s 32 samples (first 4 per sample), deduplicated by AR vector, '
                    'scored by solo FVE; window labels unless "|full"; per cell P(solo of A > solo of B), ties 1/2, '
                    'pooled over pairs and as the mean of per-cell rates (each cell weighted equally). '
                    'same_open2/3 = same first 2/3 words; same_mopen4 = same first 4 words with every value surface '
                    'replaced by VAL ("since you\'re in VAL"); masked_exact = identical windows up to the value words.')}
    gid = codes(p.cell_id)
    items = p.item_id.to_numpy()
    solo = p.solo.to_numpy(float)
    toks = p.stok.to_numpy(float)
    M = {'same_pos': p.pos.to_numpy().astype(int), 'same_open2': codes(p.open2), 'same_open3': codes(p.open3),
         'same_mopen4': codes(p.mopen4), 'masked_exact': codes(p.mfull.where((' ' + p.mfull + ' ').str.contains(' val ', regex=False), None))}
    lab, labN, labF = p.grpW, p.grpNW, p.grpF
    sf = p.subfamily.to_numpy()
    one = np.ones(len(p), bool)
    gnov, wnov = (~p.g_echoW).to_numpy(), (~p.w_echoW).to_numpy()
    nogender = (p.attr_class != 'Gender').to_numpy()

    def ps(isA, isB, **kw):
        return pair_stat(bt, gid, items, solo, isA, isB, **kw)

    def variants(isA, isB, full=True):
        r = {'raw': ps(isA, isB)}
        if full:
            for k, m in M.items():
                r[k] = ps(isA, isB, match=m)
            r['len_matched'] = ps(isA, isB, toks=toks, tol=0.2)
            r['same_open2_len'] = ps(isA, isB, match=M['same_open2'], toks=toks, tol=0.2)
            r['same_mopen4_len'] = ps(isA, isB, match=M['same_mopen4'], toks=toks, tol=0.2)
        return r
    # the filler test: gold vs wrong in many slices
    G, W, Fr, Nn = (lab == 'gold').to_numpy(), (lab == 'wrong').to_numpy(), (lab == 'frame').to_numpy(), (lab == 'none').to_numpy()
    GN, WN = (labN == 'gold').to_numpy(), (labN == 'wrong').to_numpy()
    Wd = W & (p.subW == 'distractor').to_numpy()
    Wo = W & (p.subW == 'other_value').to_numpy()
    fil = {
        'all': variants(G, W),
        'selfdescribe': variants(G & (sf == 'selfdescribe'), W & (sf == 'selfdescribe')),
        'synthsys': variants(G & (sf == 'synthsys'), W & (sf == 'synthsys')),
        'name': variants(GN, WN),
        'novel': variants(G & gnov, W & wnov),
        'name_novel': variants(GN & gnov, WN & wnov),
        'name_novel|selfdescribe': variants(GN & gnov & (sf == 'selfdescribe'), WN & wnov & (sf == 'selfdescribe'), False),
        'name_novel|synthsys': variants(GN & gnov & (sf == 'synthsys'), WN & wnov & (sf == 'synthsys'), False),
        'gold_echo_vs_wrong': variants(G & ~gnov, W, False),
        'novel_surface_rule': variants(G & ~p.g_echo_sW.to_numpy(), W & wnov, False),
        'name_novel_surface_rule': variants(GN & ~p.g_echo_sW.to_numpy(), WN & wnov, False),
        'no_gender': variants(G & nogender, W & nogender),
        'name|no_gender': variants(GN & nogender, WN & nogender, False),
        'vs_distractor': variants(G, Wd, False), 'vs_other_value': variants(G, Wo, False),
        'name|vs_distractor': variants(GN, WN & (p.subW == 'distractor').to_numpy(), False),
        'full_text_labels': variants((labF == 'gold').to_numpy(), (labF == 'wrong').to_numpy(), False),
    }
    out['gold_vs_wrong'] = fil
    # the ladder: value vs frame vs none
    lad = {}
    for name, (A, B) in {'gold_vs_frame': (G, Fr), 'wrong_vs_frame': (W, Fr), 'gold_vs_none': (G, Nn),
                         'wrong_vs_none': (W, Nn), 'frame_vs_none': (Fr, Nn),
                         'gold_novel_vs_frame': (G & gnov, Fr), 'gold_echo_vs_frame': (G & ~gnov, Fr),
                         'gold_novel_vs_none': (G & gnov, Nn), 'gold_echo_vs_none': (G & ~gnov, Nn),
                         'gold_echo_vs_gold_novel': (G & ~gnov, G & gnov)}.items():
        lad[name] = {'all': variants(A, B, name in ('gold_vs_frame', 'wrong_vs_frame', 'gold_vs_none', 'frame_vs_none')),
                     'selfdescribe': ps(A & (sf == 'selfdescribe'), B & (sf == 'selfdescribe')),
                     'synthsys': ps(A & (sf == 'synthsys'), B & (sf == 'synthsys'))}
    out['ladder'] = lad
    # by layer / site / attr_class (filler test, window labels and name-level novel)
    out['gold_vs_wrong_by_layer'] = {f'L{lay}': {'all': ps(G & (p.layer == lay).to_numpy(), W & (p.layer == lay).to_numpy())['pooled'],
                                                'name_novel': ps(GN & gnov & (p.layer == lay).to_numpy(), WN & wnov & (p.layer == lay).to_numpy())['pooled']}
                                     for lay in LAYERS}
    out['gold_vs_wrong_by_site'] = {st: ps(G & (p.site == st).to_numpy(), W & (p.site == st).to_numpy())['pooled']
                                    for st in sorted(p.site.unique())}
    out['gold_vs_wrong_by_attr_class'] = {}
    for ac in sorted(p.attr_class.unique()):
        m = (p.attr_class == ac).to_numpy()
        r = ps(G & m, W & m)
        out['gold_vs_wrong_by_attr_class'][ac] = {'pooled': r['pooled'], 'per_cell_mean': r.get('per_group_mean'),
                                                  'cells': r.get('groups', 0), 'pairs': r.get('pairs', 0),
                                                  'name_novel': ps(GN & gnov & m, WN & wnov & m)['pooled']}
    out['gold_vs_wrong_by_group'] = {}
    for gr in sorted(p.group.unique()):
        m = (p.group == gr).to_numpy()
        r = ps(G & m, W & m)
        if r.get('pairs'):
            out['gold_vs_wrong_by_group'][gr] = {'est': r['pooled']['est'], 'cells': r['groups'], 'pairs': r['pairs']}
    # leave one group out (pooled filler test)
    it, w, pp, _ = group_pairs(gid, items, solo, G, W)
    grp_of_item = {i: bt.cl[bt.icl[bt.ii[i]]] for i in bt.items}
    gw = collections.defaultdict(lambda: [0.0, 0.0])
    for i, a, b in zip(it, w, pp):
        gw[grp_of_item[i]][0] += a
        gw[grp_of_item[i]][1] += b
    totw, totp = sum(v[0] for v in gw.values()), sum(v[1] for v in gw.values())
    loo = {g: round((totw - v[0]) / (totp - v[1]), 3) for g, v in gw.items() if totp > v[1]}
    out['gold_vs_wrong_leave_one_group_out'] = {'min': min(loo.values()), 'max': max(loo.values()),
                                                'pair_share_by_group': {g: round(v[1] / totp, 3) for g, v in
                                                                        sorted(gw.items(), key=lambda x: -x[1][1])[:8]}}
    # two directions: value pairs (a, b) where a is gold in some items and b gold in others. If FVE tracked truth, the
    # gold value would win in both directions; if it tracked the word, the same word would win in both.
    out['value_pairs_two_directions'] = two_directions(bt, p, gid, items, solo)
    # consensus: within a cell, bullets naming the pool's most-named value vs bullets naming another single value
    out['consensus'] = consensus(bt, p, gid, items, solo)
    # within-cell regression with controls (pool)
    d = p.copy()
    for labn in ('gold', 'wrong', 'mixed', 'frame'):
        d[f'L_{labn}'] = (d.grpW == labn).astype(float)
    d['L_gold_novel'] = ((d.grpW == 'gold') & ~d.g_echoW).astype(float)
    d['L_gold_echo'] = ((d.grpW == 'gold') & d.g_echoW).astype(float)
    d['L_wrong_name'] = ((d.grpNW == 'wrong')).astype(float)
    d['L_wrong_weak'] = ((d.grpNW == 'wrong_weak')).astype(float)
    d['L_gold_name_novel'] = ((d.grpNW == 'gold') & ~d.g_echoW).astype(float)
    d['L_gold_name_echo'] = ((d.grpNW == 'gold') & d.g_echoW).astype(float)
    d['L_gold_weak'] = ((d.grpNW == 'gold_weak')).astype(float)
    for k in (1, 2, 3):
        d[f'slot{k}'] = (d.pos == k).astype(float)
    d['logtok'] = np.log(d.stok.clip(lower=1))
    for c in ('cjk_lead', 'punct_open', 'field_open'):
        d[c] = d[c].astype(float)
    ctrl = ['slot1', 'slot2', 'slot3', 'logtok', 'cjk_lead', 'punct_open', 'field_open', 'overlap']
    con = {'gold-wrong': {'L_gold': 1, 'L_wrong': -1}, 'gold-frame': {'L_gold': 1, 'L_frame': -1},
           'wrong-frame': {'L_wrong': 1, 'L_frame': -1}, 'frame-none': {'L_frame': 1}, 'gold-none': {'L_gold': 1}}
    con2 = {'gold_novel-wrong': {'L_gold_novel': 1, 'L_wrong': -1}, 'gold_echo-wrong': {'L_gold_echo': 1, 'L_wrong': -1},
            'gold_echo-gold_novel': {'L_gold_echo': 1, 'L_gold_novel': -1}, 'gold_novel-frame': {'L_gold_novel': 1, 'L_frame': -1},
            'wrong-frame': {'L_wrong': 1, 'L_frame': -1}}
    con3 = {'gold_name_novel-wrong_name': {'L_gold_name_novel': 1, 'L_wrong_name': -1},
            'gold_name_echo-wrong_name': {'L_gold_name_echo': 1, 'L_wrong_name': -1},
            'gold_name_novel-frame': {'L_gold_name_novel': 1, 'L_frame': -1},
            'wrong_name-frame': {'L_wrong_name': 1, 'L_frame': -1}}
    base4 = ['L_gold', 'L_wrong', 'L_mixed', 'L_frame']
    split5 = ['L_gold_novel', 'L_gold_echo', 'L_wrong', 'L_mixed', 'L_frame']
    name7 = ['L_gold_name_novel', 'L_gold_name_echo', 'L_gold_weak', 'L_wrong_name', 'L_wrong_weak', 'L_mixed', 'L_frame']
    reg = {'labels_only': fe_reg(bt, d, 'cell_id', 'solo', base4, con),
           'with_controls': fe_reg(bt, d, 'cell_id', 'solo', base4 + ctrl, con),
           'echo_split_with_controls': fe_reg(bt, d, 'cell_id', 'solo', split5 + ctrl, con2),
           'name_level_with_controls': fe_reg(bt, d, 'cell_id', 'solo', name7 + ctrl, con3)}
    for sfam in ('selfdescribe', 'synthsys'):
        reg[f'echo_split_with_controls|{sfam}'] = fe_reg(bt, d[d.subfamily == sfam], 'cell_id', 'solo', split5 + ctrl, con2)
        reg[f'name_level_with_controls|{sfam}'] = fe_reg(bt, d[d.subfamily == sfam], 'cell_id', 'solo', name7 + ctrl, con3)
    out['within_cell_regression'] = reg
    out['counts'] = {'pool_bullets_dedup': int(len(p)), 'cells_with_gold': int(p[G].cell_id.nunique()),
                     'cells_with_wrong': int(p[W].cell_id.nunique()),
                     'cells_with_both': int(len(set(p[G].cell_id) & set(p[W].cell_id))),
                     'cells_with_both_name_novel': int(len(set(p[GN & gnov].cell_id) & set(p[WN & wnov].cell_id))),
                     'gold_bullets': int(G.sum()), 'wrong_bullets': int(W.sum()),
                     'gold_name_novel_bullets': int((GN & gnov).sum()), 'wrong_name_novel_bullets': int((WN & wnov).sum()),
                     'feature_rates': {lb: {'cjk_lead': round(float(p[p.grpW == lb].cjk_lead.mean()), 3),
                                            'punct_open': round(float(p[p.grpW == lb].punct_open.mean()), 3),
                                            'field_open': round(float(p[p.grpW == lb].field_open.mean()), 3),
                                            'overlap': round(float(p[p.grpW == lb].overlap.mean()), 3),
                                            'mean_slot': round(float(p[p.grpW == lb].pos.mean()), 3),
                                            'mean_stok': round(float(p[p.grpW == lb].stok.mean()), 2),
                                            'truncated': round(float(p[p.grpW == lb].trunc.mean()), 3)}
                                       for lb in ('gold', 'wrong', 'frame', 'none')}}
    return out


def two_directions(bt, p, gid, items, solo):
    """Single-value name bullets: for every (gold value a, wrong value b), P(a-bullet solo > b-bullet solo) within cell.
    Where the reverse direction (gold b, wrong a) also has pairs, balanced = mean of both gold-win rates (what tracking
    the truth would raise) and word = half their difference (a preference for a's word whatever is true)."""
    q = p[(p.grpNW.isin(['gold', 'wrong']))].copy()
    # value named: gold bullets -> their gold value id; wrong bullets naming exactly one value by name form
    q['val'] = [gv[0] if lb == 'gold' and len(gv) == 1 else (wv[0] if lb == 'wrong' and len(wv) == 1 else None)
                for lb, gv, wv in zip(q.grpNW, q.gvalsW, q.wvalsW)]
    q = q[q.val.notna()]
    gval = q[q.grpNW == 'gold'].groupby('item_id').val.agg(lambda x: x.mode().iloc[0]).to_dict()
    q['gold_val'] = q.item_id.map(gval)
    q = q[q.gold_val.notna()]
    res = {}
    full_idx = q.index.to_numpy()
    for (a, b), _ in q[q.grpNW == 'wrong'].groupby(['gold_val', 'val']):
        m = (q.gold_val == a).to_numpy()
        isA = m & (q.val == a).to_numpy() & (q.grpNW == 'gold').to_numpy()
        isB = m & (q.val == b).to_numpy() & (q.grpNW == 'wrong').to_numpy()
        it, w, pp, _ = group_pairs(gid[full_idx], items[full_idx], solo[full_idx], isA, isB)
        if len(pp):
            res[(a, b)] = (it, w, pp)
    out, bal_reps, bal_ests, pairs_used = {}, [], [], 0
    done = set()
    for (a, b), (it1, w1, p1) in sorted(res.items(), key=lambda x: -x[1][2].sum()):
        if (b, a) in done or (a, b) in done:
            continue
        N1, D1 = bt.agg(it1, w1, p1)
        r1, _ = bt._reps(N1, D1)
        e1 = float(N1.sum() / D1.sum())
        entry = {'gold_a_vs_wrong_b': round(e1, 3), 'pairs_ab': int(D1.sum()), 'items_ab': int((D1 > 0).sum())}
        if (b, a) in res:
            it2, w2, p2 = res[(b, a)]
            N2, D2 = bt.agg(it2, w2, p2)
            r2, _ = bt._reps(N2, D2)
            e2 = float(N2.sum() / D2.sum())
            entry.update({'gold_b_vs_wrong_a': round(e2, 3), 'pairs_ba': int(D2.sum()), 'items_ba': int((D2 > 0).sum()),
                          'balanced': round(0.5 * (e1 + e2), 3), 'balanced_ci': _ci(0.5 * (r1 + r2), 3),
                          'word_pref_for_a': round(0.5 * (e1 - e2), 3), 'word_ci': _ci(0.5 * (r1 - r2), 3)})
            if min(D1.sum(), D2.sum()) >= 20:
                bal_reps.append(0.5 * (r1 + r2))
                bal_ests.append(0.5 * (e1 + e2))
                pairs_used += int(D1.sum() + D2.sum())
            done.add((b, a))
        done.add((a, b))
        if entry['pairs_ab'] >= 200 or 'balanced' in entry:
            out[f'{a}|{b}'] = entry
    if bal_reps:
        mb = np.nanmean(np.vstack(bal_reps), axis=0)
        out['_mean_balanced_over_value_pairs'] = {'est': round(float(np.mean(bal_ests)), 3), 'ci_items': _ci(mb, 3),
                                                  'value_pairs': len(bal_reps), 'pairs': pairs_used,
                                                  'note': 'value pairs with >= 20 pairs in each direction'}
    return out


def consensus(bt, p, gid, items, solo):
    """Bullets naming exactly one value by a name form; per cell the most-named value (ties: skip cell)."""
    q = p[p.grpNW.isin(['gold', 'wrong'])].copy()
    q['val'] = [gv[0] if lb == 'gold' and len(gv) == 1 else (wv[0] if lb == 'wrong' and len(wv) == 1 else None)
                for lb, gv, wv in zip(q.grpNW, q.gvalsW, q.wvalsW)]
    q = q[q.val.notna()]
    cnt = q.groupby(['cell_id', 'val']).size()
    maj, gold_is_maj = {}, {}
    for cid, s in cnt.groupby(level=0):
        s = s.droplevel(0).sort_values(ascending=False)
        if len(s) < 2 or s.iloc[0] == s.iloc[1]:
            continue
        maj[cid] = s.index[0]
    q = q[q.cell_id.isin(maj)]
    q['is_maj'] = [v == maj[c] for c, v in zip(q.cell_id, q.val)]
    gold_maj_cells = set(q[q.is_maj & (q.grpNW == 'gold')].cell_id)
    idx = q.index.to_numpy()
    g2, it2, s2 = gid[idx], items[idx], solo[idx]
    A = q.is_maj.to_numpy()
    out = {'all': pair_stat(bt, g2, it2, s2, A, ~A)}
    m = q.cell_id.isin(gold_maj_cells).to_numpy()
    out['majority_is_gold'] = pair_stat(bt, g2, it2, s2, A & m, ~A & m)
    out['majority_is_wrong'] = pair_stat(bt, g2, it2, s2, A & ~m, ~A & ~m)
    out['cells'] = {'with_majority': len(maj), 'majority_is_gold': len(gold_maj_cells),
                    'majority_is_wrong': len(maj) - len(gold_maj_cells)}
    return out


# ----------------------------------------------------------------------------------------------- A4
def run_a4(bt, sel, pool, samples):
    out = {'note': ('readout-level, FULL-TEXT labels (what the judge reads). random baselines from the same labels on '
                    'the pool: "random one of 32" = mean over the 32 samples of "the sample\'s first 4 bullets hold the '
                    'label"; "random 4 pool bullets" = 1 - C(n-g,4)/C(n,4) over the deduplicated pool. Original is '
                    'sample 0, itself a random one of the 32.')}
    item_of = dict(zip(sel.cell_id, sel.item_id))
    cells = sorted(sel.cell_id.unique())
    flags = {
        'gold': lambda d: d.grpF == 'gold',
        'gold_or_mixed': lambda d: d.grpF.isin(['gold', 'mixed']),
        'gold_name': lambda d: d.grpNF == 'gold',
        'gold_name_novel': lambda d: (d.grpNF == 'gold') & d.g_name_novelF,
        'gold_novel': lambda d: (d.grpF == 'gold') & d.g_novelF,
        'wrong': lambda d: d.grpF == 'wrong',
        'wrong_name': lambda d: d.grpNF == 'wrong',
        'wrong_distractor': lambda d: (d.grpF == 'wrong') & d.w_distrF,
        'frame': lambda d: d.grpF == 'frame',
    }
    pu = pool.drop_duplicates(['cell_id', 'cache_key'])

    def hyper(n, g, k=4):
        if n < k:
            return float(g > 0)
        return 1.0 - math.comb(int(n - g), k) / math.comb(int(n), k)
    res = {}
    for name, f in flags.items():
        fl = f(pool)
        samp = fl.groupby([pool.cell_id, pool.sample_index]).any()
        frac32 = samp.groupby(level=0).mean()
        any32 = samp.groupby(level=0).any().astype(float)
        ng = f(pu).groupby(pu.cell_id).sum()
        nn = pu.groupby('cell_id').size()
        rand4 = {c: hyper(nn[c], ng.get(c, 0)) for c in nn.index}
        selh = {s: f(sel[sel.setting == s]).groupby(sel[sel.setting == s].cell_id).any().astype(float) for s in SETTINGS}
        for sub in ('all', 'selfdescribe', 'synthsys'):
            cs = [c for c in cells if sub == 'all' or c.split('|')[1].startswith('um-sd' if sub == 'selfdescribe' else 'um-ss')]

            def arr(series):
                return np.array([float(series.get(c, np.nan)) for c in cs])
            A = {'random one of 32 samples': arr(frac32), 'random 4 pool bullets': arr(rand4), 'pool has it': arr(any32)}
            for s in SETTINGS:
                A[SL[s]] = arr(selh[s])
            ok = np.all([np.isfinite(v) for v in A.values()], axis=0)
            its = [item_of[c] for c, o in zip(cs, ok) if o]
            NDs = {k: bt.agg(its, v[ok]) for k, v in A.items()}
            r = {k: bt.ratio(*nd) for k, nd in NDs.items()}
            r['Original - random one of 32'] = bt.diff(*NDs['Original'], *NDs['random one of 32 samples'])
            r['Best of 32 - random one of 32'] = bt.diff(*NDs['Best of 32'], *NDs['random one of 32 samples'])
            r['Best of 32 - Original'] = bt.diff(*NDs['Best of 32'], *NDs['Original'])
            r['Combine 32 - random 4 pool bullets'] = bt.diff(*NDs['Combine 32'], *NDs['random 4 pool bullets'])
            r['Combine 32 - Original'] = bt.diff(*NDs['Combine 32'], *NDs['Original'])
            r['cells'] = int(ok.sum())
            pg = A['pool has it'][ok] > 0
            r['cells_pool_has_it'] = int(pg.sum())
            for s in SETTINGS:
                r[f'missing_from_readout_given_pool_has_it[{SL[s]}]'] = round(float(np.mean(A[SL[s]][ok][pg] == 0)), 3) if pg.any() else None
            res[f'{name}|{sub}'] = r
    out['readout_has_label_vs_random'] = res
    # sample level: within a cell, joint FVE of the 32 samples (Best of 32 trace) by what the sample's first 4 bullets name
    fl = pool.assign(g=pool.grpF.eq('gold'), gn=(pool.grpNF == 'gold') & pool.g_name_novelF, w=pool.grpF.eq('wrong'),
                     wn=pool.grpNF.eq('wrong'))
    fl = fl.groupby(['cell_id', 'sample_index'])[['g', 'gn', 'w', 'wn']].any().reset_index()
    S = samples[samples.joint.notna()].merge(fl, on=['cell_id', 'sample_index'], how='left')
    S[['g', 'gn', 'w', 'wn']] = S[['g', 'gn', 'w', 'wn']].fillna(False).astype(bool)
    S['item_id'] = S.cell_id.map(item_of)
    S['subfamily'] = np.where(S.item_id.str.startswith('um-sd'), 'selfdescribe', 'synthsys')
    gid = codes(S.cell_id)
    J = S.joint.to_numpy(float)
    it = S.item_id.to_numpy()
    sl = {}
    for sub in ('all', 'selfdescribe', 'synthsys'):
        m = np.ones(len(S), bool) if sub == 'all' else (S.subfamily == sub).to_numpy()
        g, gn, w, wn = (S[c].to_numpy() for c in ('g', 'gn', 'w', 'wn'))
        sl[f'gold_sample_vs_no_gold|{sub}'] = pair_stat(bt, gid, it, J, g & m, ~g & m)
        sl[f'gold_sample_vs_wrong_only_sample|{sub}'] = pair_stat(bt, gid, it, J, g & ~w & m, w & ~g & m)
        sl[f'gold_name_novel_sample_vs_wrong_name_only|{sub}'] = pair_stat(bt, gid, it, J, gn & ~w & m, wn & ~g & m)
        sl[f'gold_sample_vs_neither|{sub}'] = pair_stat(bt, gid, it, J, g & ~w & m, ~g & ~w & m)
        sl[f'wrong_only_sample_vs_neither|{sub}'] = pair_stat(bt, gid, it, J, w & ~g & m, ~g & ~w & m)
    out['sample_level_joint_fve'] = sl
    # judge per cell
    j = sel.drop_duplicates(['cell_id', 'setting'])[['cell_id', 'setting', 'item_id', 'subfamily', 'judge_pick', 'judge_basis']]
    j = j.assign(gold=j.judge_pick.eq('gold'), gold_inf=j.judge_pick.eq('gold') & j.judge_basis.eq('inferred_characterization'),
                 gold_echo=j.judge_pick.eq('gold') & j.judge_basis.eq('verbatim_echo'), distractor=j.judge_pick.eq('distractor'))
    jr = {}
    for kind in ('gold', 'gold_inf', 'gold_echo', 'distractor'):
        for sub in ('all', 'selfdescribe', 'synthsys'):
            d0 = j if sub == 'all' else j[j.subfamily == sub]
            NDs, r = {}, {}
            for s in SETTINGS:
                d = d0[d0.setting == s]
                NDs[s] = bt.agg(d.item_id, d[kind].astype(float))
                r[SL[s]] = bt.ratio(*NDs[s], nd=4)
            r['Best of 32 - Original'] = bt.diff(*NDs[SETTINGS[1]], *NDs[SETTINGS[0]], nd=4)
            r['Combine 32 - Original'] = bt.diff(*NDs[SETTINGS[2]], *NDs[SETTINGS[0]], nd=4)
            r['Combine 32 - Best of 32'] = bt.diff(*NDs[SETTINGS[2]], *NDs[SETTINGS[1]], nd=4)
            jr[f'{kind}|{sub}'] = r
    out['judge_per_cell'] = jr
    # item level on the reduced grid (any cell gold; WSB-headline style): per setting
    il = {}
    for s in SETTINGS:
        d = j[j.setting == s]
        il[SL[s]] = {'items_any_cell_gold': int(d.groupby('item_id').gold.any().sum()),
                     'items_any_cell_gold_inferred': int(d.groupby('item_id').gold_inf.any().sum()),
                     'items_any_cell_distractor': int(d.groupby('item_id').distractor.any().sum())}
    out['judge_item_level_reduced_grid'] = il
    return out


# ----------------------------------------------------------------------------------------------- A5
def readout_table(sel):
    import pandas as pd
    rows = []
    for (cid, s), g in sel.groupby(['cell_id', 'setting'], sort=False):
        labs = set(g.grpF)
        has_gold = bool(labs & {'gold', 'mixed'})
        has_wrong = bool(labs & {'wrong', 'mixed'})
        gname_nov = bool(((g.grpNF == 'gold') & g.g_name_novelF).any())
        gname = bool((g.grpNF == 'gold').any())
        gnov = bool((g.grpF.isin(['gold', 'mixed']) & g.g_novelF).any())
        echo_only = has_gold and not gnov
        ev = g[g.judge_ev]
        rows.append({'cell_id': cid, 'setting': s, 'item_id': g.item_id.iloc[0], 'subfamily': g.subfamily.iloc[0],
                     'attr_class': g.attr_class.iloc[0], 'key': g.key.iloc[0], 'site': g.site.iloc[0],
                     'layer': int(g.layer.iloc[0]),
                     'has_gold': has_gold, 'has_wrong': has_wrong, 'gold_name': gname, 'gold_name_novel': gname_nov,
                     'gold_novel': gnov, 'gold_echo_only': echo_only,
                     'gold_kind': min((k for k in g[g.grpF.isin(['gold', 'mixed'])].gkF if k), key=KIND_RANK.get, default=''),
                     'pick': g.judge_pick.iloc[0], 'basis': g.judge_basis.iloc[0], 'value': g.judge_value.iloc[0],
                     'evidence': g.judge_evidence.iloc[0], 'ev_found': bool(g.ev_found.iloc[0]),
                     'ev_labels': ','.join(sorted(set(ev.grpF))) if len(ev) else '',
                     'ev_echo': bool(len(ev)) and bool(((ev.grpF == 'gold') & ev.g_echoF).any()) and not bool(((ev.grpF == 'gold') & ~ev.g_echoF).any())})
    return pd.DataFrame(rows)


def run_a5(bt, sel):
    out = {'note': ('judge = WSB um-v2 per readout (GPT-6 Luna, reasoning none, run nt-um-judge-v1; not WSB numbers of '
                    'record); labels = lexicon v2 on the full text. See analysis/um/a5_results.json '
                    '(judge_vs_labels.py) for the reading verdicts and more slices.')}
    Rt = readout_table(sel)
    jg = (Rt.pick == 'gold').to_numpy()

    def kappa(a, b):
        a, b = np.asarray(a, bool), np.asarray(b, bool)
        po = np.mean(a == b)
        pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
        return round(float((po - pe) / (1 - pe)), 3) if pe < 1 else None

    def agree(d, col):
        a, b = (d.pick == 'gold').to_numpy(), d[col].to_numpy()
        return {'kappa': kappa(a, b), 'both': int((a & b).sum()), 'judge_only': int((a & ~b).sum()),
                'labels_only': int((~a & b).sum()), 'neither': int((~a & ~b).sum()),
                'P(judge gold | labels)': bt.ratio(*bt.agg(d.item_id, (a & b).astype(float), b.astype(float))),
                'P(labels | judge gold)': bt.ratio(*bt.agg(d.item_id, (a & b).astype(float), a.astype(float)))}
    ag = {}
    for col in ('has_gold', 'gold_name', 'gold_name_novel', 'gold_novel'):
        ag[col] = {'all': agree(Rt, col), **{sf: agree(Rt[Rt.subfamily == sf], col) for sf in ('selfdescribe', 'synthsys')},
                   **{SL[s]: agree(Rt[Rt.setting == s], col) for s in SETTINGS}}
    out['agreement'] = ag
    # misses: a novel NAME of the gold value in the readout, no wrong value anywhere, judge says cannot tell
    clean = Rt[Rt.gold_name_novel & ~Rt.has_wrong]
    miss = clean[clean.pick == 'cannot_tell']
    out['miss_named_gold'] = {'n': int(len(miss)), 'of': int(len(clean)),
                              'P(cannot_tell)': bt.ratio(*bt.agg(clean.item_id, (clean.pick == 'cannot_tell').astype(float))),
                              'by_attr_class': miss.attr_class.value_counts().to_dict(),
                              'by_subfamily': miss.subfamily.value_counts().to_dict(),
                              'by_gold_kind': miss.gold_kind.value_counts().to_dict(),
                              'P(cannot_tell) by gold kind': {k: bt.ratio(*bt.agg(d.item_id, (d.pick == 'cannot_tell').astype(float)))
                                                             for k, d in clean.groupby('gold_kind')},
                              'rows': miss[['key', 'setting', 'pick', 'evidence']].assign(setting=miss.setting.map(SL)).to_dict('records')[:60]}
    # echo crediting: judge says gold on readouts whose gold mentions are ALL copies of the prompt
    eo = Rt[Rt.gold_echo_only & ~Rt.has_wrong]
    out['echo_only_gold_readouts'] = {
        'n': int(len(eo)), 'by_subfamily': eo.subfamily.value_counts().to_dict(),
        'P(judge gold)': {sf: bt.ratio(*bt.agg(d.item_id, (d.pick == 'gold').astype(float))) for sf, d in
                          [('all', eo)] + [(sf, eo[eo.subfamily == sf]) for sf in ('selfdescribe', 'synthsys')]},
        'P(basis inferred | judge gold)': {sf: bt.ratio(*bt.agg(d[d.pick == 'gold'].item_id,
                                                               (d[d.pick == 'gold'].basis == 'inferred_characterization').astype(float)))
                                           for sf, d in [('all', eo)] + [(sf, eo[eo.subfamily == sf]) for sf in ('selfdescribe', 'synthsys')]},
        'inferred_rows': eo[(eo.pick == 'gold') & (eo.basis == 'inferred_characterization')][['key', 'setting', 'evidence']]
        .assign(setting=lambda x: x.setting.map(SL)).to_dict('records')[:60]}
    nov = Rt[Rt.gold_novel & ~Rt.has_wrong]
    out['novel_gold_readouts'] = {
        'n': int(len(nov)),
        'P(judge gold)': {sf: bt.ratio(*bt.agg(d.item_id, (d.pick == 'gold').astype(float))) for sf, d in
                          [('all', nov)] + [(sf, nov[nov.subfamily == sf]) for sf in ('selfdescribe', 'synthsys')]},
        'P(basis echo | judge gold)': {sf: bt.ratio(*bt.agg(d[d.pick == 'gold'].item_id,
                                                           (d[d.pick == 'gold'].basis == 'verbatim_echo').astype(float)))
                                       for sf, d in [('all', nov)] + [(sf, nov[nov.subfamily == sf]) for sf in ('selfdescribe', 'synthsys')]}}
    # judge basis vs label echo, on judge-gold readouts with a gold label
    gg = Rt[(Rt.pick == 'gold') & Rt.has_gold]
    out['basis_x_label_echo'] = {sf: {f'{b}|{"echo_only" if e else "novel"}': int(n) for (b, e), n in
                                      d.groupby(['basis', 'gold_echo_only']).size().items()}
                                 for sf, d in [('all', gg)] + [(sf, gg[gg.subfamily == sf]) for sf in ('selfdescribe', 'synthsys')]}
    # evidence bullet: the judge's quote sits on which label
    ev = Rt[(Rt.pick == 'gold') & Rt.ev_found]
    out['judge_gold_evidence_bullet_labels'] = dict(collections.Counter(ev.ev_labels).most_common(15))
    out['judge_gold_evidence_on_echo_only_gold_bullet'] = {'n': int(ev.ev_echo.sum()), 'of': int(len(ev)),
                                                           'by_subfamily': ev[ev.ev_echo].subfamily.value_counts().to_dict()}
    # wrong value named, judge picks gold anyway / picks a distractor
    wr = Rt[Rt.has_wrong & ~Rt.has_gold]
    out['wrong_only_readouts'] = {'n': int(len(wr)), 'picks': wr.pick.value_counts().to_dict()}
    # reading verdicts from judge_vs_labels.py (manual)
    rd = {}
    for kind in ('miss', 'miss3', 'judge_only', 'distractor'):
        rp = OUT / f'a5_{kind}_reading.tsv'
        if rp.exists():
            rows = [ln.split('\t') for ln in rp.read_text().splitlines()[1:] if ln.strip()]
            rd[kind] = {'n_read': len(rows), 'verdicts': dict(collections.Counter(r[2] for r in rows))}
    out['reading_verdicts_judge_vs_labels'] = rd
    Rt.to_pickle(CACHE / 'a5_readouts.pkl')
    return out


# ----------------------------------------------------------------------------------------------- show / sample
def hits_record(r, suffix):
    return {'label': r['grp' + suffix], 'name_level': r['grpN' + suffix], 'subtype': r['sub' + suffix] or None,
            'gold_kind': r['gk' + suffix] or None, 'wrong_kind': r['wk' + suffix] or None,
            'gold_echo': bool(r['g_echo' + suffix]), 'gold_novel': bool(r['g_novel' + suffix]),
            'wrong_echo': bool(r['w_echo' + suffix]), 'gold_values_named': list(r['gvals' + suffix]),
            'wrong_values_named': list(r['wvals' + suffix]), 'value_surfaces': list(r['surfs' + suffix])}


def bullet_record(r):
    return {'index': int(r.idx), 'text': r.text, 'scored_window': r.window if r.trunc else None,
            'scored_tokens': int(r.stok), 'truncated': bool(r.trunc),
            'label_window': hits_record(r, 'W'), 'label_full_text': hits_record(r, 'F'),
            'solo_fve': _r(r.solo), 'solo_pct_in_setting_layer': _r(r.solo_pct, 3), 'shapley_share': _r(r.share),
            'shapley': _r(r.shapley), 'loo_drop': _r(r['drop']), 'coefficient': _r(r.coef, 3),
            'sample_index': int(r.sample_index), 'judge_quote_on_this_bullet': bool(r.judge_ev)}


def item_record(it, c):
    return {'id': it['name'], 'subfamily': it['subfamily'], 'attr_class': it['attr_class'], 'group': group_of(it),
            'gold_value': it['attr'], 'judge_options': c['options'], 'distractor_options': c['distractors'],
            'messages': it['messages']}


def cmd_show(args):
    T = load_tables()
    sel = add_derived(T['sel'])
    bank = C.load_bank(FAM)
    d = sel[sel.key == args.key]
    if args.setting:
        d = d[d.setting.map(SL) == args.setting]
    if not len(d):
        raise SystemExit('no such case')
    it = bank[d.item_id.iloc[0]]
    print(json.dumps({'id': it['name'], 'attr': it['attr'], 'class': it['attr_class'],
                      'messages': [m['content'] for m in it['messages']]}, ensure_ascii=False, indent=1))
    print('site', d.site.iloc[0], 'layer', d.layer.iloc[0], 'pos', d.position.iloc[0])
    for s, g in d.groupby('setting', sort=False):
        print(f'\n== {SL[s]}  joint {_r(g.joint.iloc[0])}  judge {g.judge_pick.iloc[0]}/{g.judge_basis.iloc[0]} '
              f'{g.judge_value.iloc[0]!r} ev={g.judge_evidence.iloc[0]!r}')
        for _, r in g.sort_values('idx').iterrows():
            print(f"  [{r.idx}] W={r.grpW}/{r.grpNW} F={r.grpF} sub={r.subW} gk={r.gkW} echo={r.g_echoW} "
                  f"solo={_r(r.solo)} pct={_r(r.solo_pct, 2)} share={_r(r.share)} stok={r.stok} ev={r.judge_ev} "
                  f"surf={list(r.surfsW)}")
            print('      ', repr(r.text[:300]))
    if args.pool:
        p = pool_frame(T['pool'])
        p = p[(p.cell_id == d.cell_id.iloc[0]) & p.grpW.isin(['gold', 'wrong', 'mixed'])]
        print('\n== pool bullets naming a value (window):', len(p))
        for _, r in p.sort_values('solo', ascending=False).head(args.n).iterrows():
            print(f'  s{r.sample_index}.{r.pos} {r.grpW}/{r.grpNW} echo={r.g_echoW} solo={_r(r.solo)} stok={r.stok} '
                  f'surf={list(r.surfsW)} | {r.text[:160]!r}')


def cmd_sample(args):
    T = load_tables()
    sel = add_derived(T['sel'])
    bank = C.load_bank(FAM)
    ctx = contexts(bank)
    sc = sel[sel.solo.notna()]
    gold = sc[(sc.grpNW == 'gold') & (sc.grpNF == 'gold')]          # a gold NAME inside the scored window
    wrong = sc[(sc.grpNW == 'wrong') & (sc.grpNF == 'wrong')]       # a wrong NAME inside the window, no gold anywhere

    def pick(cands, n, ascending, prefer=None):
        cands = cands.sort_values(['solo_pct', 'solo'], ascending=ascending)
        if prefer is not None:
            cands = cands.assign(_p=prefer(cands)).sort_values(['_p', 'solo_pct'], ascending=[False, ascending], kind='stable')
        chosen, items, groups, sets, sfs = [], set(), collections.Counter(), collections.Counter(), collections.Counter()
        for _, r in cands.iterrows():
            if (r.item_id in items or groups[r.group] >= 2 or sets[r.setting] >= 5 or sfs[r.subfamily] >= 7):
                continue
            chosen.append(r)
            items.add(r.item_id)
            groups[r.group] += 1
            sets[r.setting] += 1
            sfs[r.subfamily] += 1
            if len(chosen) == n:
                break
        return chosen
    hi_g = gold[gold.solo_pct >= 0.75]
    lo_g = gold[gold.solo_pct <= 0.25]
    hi_w = wrong[wrong.solo_pct >= 0.75]
    picks = {'high_fve_gold': pick(hi_g, 12, False, prefer=lambda d: d.g_name_novelW.astype(int)),
             'high_fve_wrong_value': pick(hi_w, 12, False, prefer=lambda d: (d.subW == 'distractor').astype(int)),
             'low_fve_gold': pick(lo_g, 12, True, prefer=lambda d: d.g_name_novelW.astype(int))}
    pu = pool_frame(T['pool'])
    cases = []
    for ctype, rows in picks.items():
        for r in rows:
            g = sc[(sc.cell_id == r.cell_id) & (sc.setting == r.setting)].sort_values('idx')
            pc = pu[pu.cell_id == r.cell_id]
            ga = pc[pc.grpW == 'gold'].solo.to_numpy()
            wa = pc[pc.grpW == 'wrong'].solo.to_numpy()
            auc = None
            if len(ga) and len(wa):
                dd = ga[:, None] - wa[None, :]
                auc = round(float(((dd > 0).sum() + 0.5 * (dd == 0).sum()) / dd.size), 3)
            it = bank[r.item_id]
            lay, pos = int(r.layer), int(r.position)
            st = T['site'][r.cell_id]
            cases.append({
                'case_key': r.key, 'cell_id': r.cell_id, 'setting': SL[r.setting], 'case_type': ctype,
                'focal_bullet': int(r.idx),
                'focal_summary': {'label_window': r.grpNW, 'subtype': r.subW or None, 'gold_echo': bool(r.g_echoW),
                                  'value_surfaces': list(r.surfsW), 'solo_fve': _r(r.solo),
                                  'solo_pct_in_setting_layer': _r(r.solo_pct, 3), 'shapley_share': _r(r.share),
                                  'rank_by_share_in_readout': int((g.share > r.share).sum() + 1)},
                'item': item_record(it, ctx[r.item_id]),
                'read_site': {'layer': lay, 'position': pos, 'site': st[0], 'tokens_from_end': st[1], 'token': st[2]},
                'readout': {'joint_fve': _r(r.joint), 'n_bullets': int(r.nb),
                            'judge': {'pick': r.judge_pick, 'basis': r.judge_basis, 'value': r.judge_value,
                                      'evidence': r.judge_evidence}},
                'bullets': [bullet_record(b) for _, b in g.iterrows()],
                'pool_context_window_labels': {'pool_bullets': int(len(pc)), 'gold': int(len(ga)), 'wrong_value': int(len(wa)),
                                               'P(gold solo > wrong-value solo)': auc},
            })
    random.Random(SEED).shuffle(cases)
    for k, c in enumerate(cases):
        c['reading_index'] = k
    payload = {'about': ('36 user-modelling reading cases: 12 high-FVE gold bullets, 12 high-FVE wrong-value bullets, '
                         '12 low-FVE gold bullets, shuffled. Gold = the bullet names the user\'s attribute value by a '
                         'name form or region word (not only a cue or a pronoun) inside the 32-token scored window, and '
                         'no other value of the class anywhere in the bullet; novel (not copied from the prompt) gold '
                         'bullets are preferred. Wrong value = names another value of the same class by a name form '
                         'inside the window and never the gold value; distractor options are preferred. High / low = '
                         'top / bottom quarter of solo FVE within setting x layer; at most one case per item and two per '
                         'related-item group per stratum, at most 5 per setting and 7 per subfamily. case_key = '
                         'item.L<layer>.p<pos>. Labels: analysis.py module docstring; statistics: results.json.'),
               'strata_counts': {k: len(v) for k, v in picks.items()},
               'candidates': {'gold_name_window': int(len(gold)), 'high_gold': int(len(hi_g)), 'low_gold': int(len(lo_g)),
                              'wrong_name_window': int(len(wrong)), 'high_wrong': int(len(hi_w))},
               'cases': cases}
    C.atomic_json(OUT / 'read_sample.json', payload)
    log('wrote', OUT / 'read_sample.json', payload['strata_counts'], payload['candidates'])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('prep')
    sub.add_parser('run')
    sub.add_parser('sample')
    s = sub.add_parser('show')
    s.add_argument('key')
    s.add_argument('setting', nargs='?')
    s.add_argument('--pool', action='store_true')
    s.add_argument('--n', type=int, default=30)
    a = ap.parse_args()
    {'prep': cmd_prep, 'run': cmd_run, 'sample': cmd_sample, 'show': cmd_show}[a.cmd](a)
