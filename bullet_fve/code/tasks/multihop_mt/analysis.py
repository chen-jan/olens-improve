"""Multihop (multi-token) (multihop_mt): are higher-FVE bullets / readouts more likely to be CORRECT?

The reverse of the Hallucination study (reading/REPORT.md, reading/synth_tests.py): there, does low FVE mark a
wrong bullet; here, does high FVE mark a bullet that carries the hidden bridge entity.

Inputs (all built earlier in tasks/multihop_mt/, read-only here):
  bullet_table.jsonl                       labels (judge-faithful regex rule, see MAP.md s6) + per-bullet metrics
  inputs/multihop_mt_three_settings.jsonl  atoms (scored_text = the <=32-token prefix the AR vector encodes)
  inputs/multihop_mt_candidates.jsonl      every full-grid selection per cell: sample index, exact FVE, Best-of-32 trace
  item_targets.json                        prompt, gold bridges, target, forms
  judgments: ${OLENS_DATA_ROOT}/expansion-v1/judgments/<cond>/multihop_mt/... (via load.py)

Settings: Original = capped_n1-n1, Best of 32 = best_n_exact-n32, Combine 32 = pooled_greedy_swap-n32.
No judge/API calls, no GPU. Exploratory (every question was inspected before).

Bootstrap: percentile, 1,000 reps, resampling the 94 related-question groups (multihop_mt:bridge-component:*),
which nest the 100 items. Pair rates: P(score of first group > second) over same-readout pairs, ties 1/2.

Usage: python -B analysis.py   ->  analysis.json, read_sample.json, logs/analysis.log (stdout)
"""
import collections
import json
import math
import random
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
TASK = ROOT / 'tasks/multihop_mt'
sys.path.insert(0, str(TASK))
import load  # noqa: E402  (pinned regex + judgments loader; hash-checked on import)

SEED, NREP = 20261015, 1000
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
OB = ['capped_n1-n1', 'best_n_exact-n32']  # list order = the lens's writing order (position adjustment applies)
SINGLE = (['capped_n1-n1'] + [f'best_n_exact-n{k}' for k in (1, 2, 4, 8, 16, 32)]
          + [f'random_complete-n{k}' for k in (1, 2, 4, 8, 16, 32)]
          + ['best_n_specificity_mean-n32', 'best_n_specificity_max-n32'])
RANDOMISH = ['capped_n1-n1'] + [f'random_complete-n{k}' for k in (1, 2, 4, 8, 16, 32)]
LENR = math.log(1.2)

# ----------------------------------------------------------------------------- text proxies (as synth_tests.py)
CJKR = '㐀-䶿一-鿿豈-﫿'
CJK_CHAR = re.compile('[' + CJKR + ']')
TOK = re.compile('[' + CJKR + ']|[^\\W_' + CJKR + ']+')
CAPW = re.compile(r'(?<![\w])([A-Z][A-Za-z\-]+)')


def toks(s):
    return [t.lower() for t in TOK.findall(s)]


def cjk_frac(s):
    ns = [c for c in s if not c.isspace()]
    return (len(CJK_CHAR.findall(s)) / len(ns)) if ns else 0.0


def caps_words(s):
    """Capitalised words that are not sentence/markup-initial (same rule as synth_tests.novel_caps)."""
    out = []
    for m in CAPW.finditer(s):
        pre = s[:m.start()].rstrip()
        if not pre or pre[-1] in '.!?:"“”*#-—–(（[>|`\'‘’' or m.group(1) in ('I', 'I’m'):
            continue
        out.append(m.group(1))
    return out


def ck(cell_id):
    _, item, L, p = cell_id.split('|')
    return f'{item}.{L}.p{int(p[1:])}'


# ----------------------------------------------------------------------------- load
items = json.loads((TASK / 'item_targets.json').read_text())
rows = [json.loads(line) for line in open(TASK / 'bullet_table.jsonl')]
cells = {}
atoms = {}
for line in open(TASK / 'inputs/multihop_mt_three_settings.jsonl'):
    c = json.loads(line)
    cells[c['cell_id']] = c
    for sid, s in c['settings'].items():
        for a in s['atoms']:
            atoms[(c['cell_id'], sid, a['source_phrase_id'])] = a
GROUPS = sorted({r['group_id'] for r in rows})
GIX = {g: i for i, g in enumerate(GROUPS)}
ITEM_GROUP = {r['item_id']: r['group_id'] for r in rows}
assert len(GROUPS) == 94 and len(ITEM_GROUP) == 100

item_vocab, item_goldwords = {}, {}
for iid, it in items.items():
    item_vocab[iid] = set(toks(it['prompt']))
    words = set()
    for role, fs in it['lenient'].items():
        for f in fs:
            words |= set(toks(f))
    for role, fs in (it.get('strict_forms') or {}).items():
        for f in fs:
            words |= set(toks(f))
    for d in [x for ds in it['distractors'].values() for x in ds]:
        words |= set(toks(d))
    item_goldwords[iid] = words

TOKZ = load.tokenizer()  # pinned Qwen3.6-27B tokenizer (local files only)
n_dec = 0
for r in rows:
    a = atoms[(r['cell_id'], r['setting'], r['phrase_id'])]
    assert a['cache_key'] == r['cache_key']
    # the extract's scored_text is the full cleaned bullet even when truncated; the AR vector encodes only
    # scored_token_ids (<= 32 tokens), so decode those for truncated atoms
    if a['truncated']:
        st = TOKZ.decode(a['scored_token_ids'])
        assert len(a['scored_token_ids']) == 32 and len(st) < len(a['scored_text']), r['phrase_id']
        n_dec += 1
    else:
        st = a['scored_text'] or ''
    r['scored_text'] = st
    r['sample_index'] = a['sample_index']
    r['slen'] = max(1, len(st))
    r['stok'] = a['scored_token_count']
    r['flen'] = len(r['text'].strip())
    r['ix'] = GIX[r['group_id']]
    r['k'] = ck(r['cell_id'])
    r['j'] = r['index']
    r['n'] = r['n_bullets_in_readout']
    r['sid'] = r['setting']
    r['solo'] = r['solo_fve']
    r['share'] = r['shapley_share']
    r['drop'] = r['loo_drop']
    r['coef0'] = float(r['coefficient'] == 0)
    r['is_hit'] = float(r['label'] == 'hit')
    r['is_ws'] = float(r['label'] == 'wrong-specific')
    r['near'] = float(bool(r['near_hit']))
    r['tgt'] = float(bool(r['target_hit_strict']))
    stt = toks(st)
    pv = item_vocab[r['item_id']]
    r['cjk'] = cjk_frac(st)
    r['prompt_ov'] = (sum(t in pv for t in stt) / len(stt)) if stt else 0.0
    head = stt[:8]
    r['prompt_head_ov'] = (sum(t in pv for t in head) / len(head)) if head else 0.0
    # a capitalised name that is neither in the prompt nor any bank form/alias/distractor of this item
    r['other_name'] = float(any(w.lower() not in pv and w.lower() not in item_goldwords[r['item_id']]
                                for w in caps_words(st)))
    r['clean_miss'] = r['label'] == 'miss' and not r['near_hit'] and not r['gold_cut_at_end']
assert len(rows) == 13196 and n_dec == 642, n_dec

by_ro = collections.defaultdict(list)
for r in rows:
    by_ro[(r['cell_id'], r['sid'])].append(r)
for v in by_ro.values():
    v.sort(key=lambda b: b['j'])
    assert [b['j'] for b in v] == list(range(len(v)))

# position-adjusted percentiles: mid-rank among all bullets at the same index in readouts of the same size and setting
grp = collections.defaultdict(list)
for r in rows:
    grp[(r['sid'], r['j'], r['n'])].append(r)
for g in grp.values():
    for sc in ('solo', 'share', 'drop'):
        v = np.array([x[sc] for x in g], dtype=float)
        order = np.sort(v)
        lo = np.searchsorted(order, v, 'left')
        hi = np.searchsorted(order, v, 'right')
        for x, p in zip(g, (lo + 0.5 * (hi - lo)) / len(v)):
            x[sc + '_pa'] = float(p)

# ----------------------------------------------------------------------------- bootstrap helpers (group level)
rng = np.random.default_rng(SEED)
BOOT = rng.integers(0, len(GROUPS), size=(NREP, len(GROUPS)))
BOOTW = np.stack([np.bincount(b, minlength=len(GROUPS)) for b in BOOT]).astype(float)


def rnd(x, d=4):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), d)


def ratio_ci(num, den):
    num, den = np.asarray(num, float), np.asarray(den, float)
    if den.sum() == 0:
        return {'est': None, 'lo': None, 'hi': None, 'n': 0, 'groups': 0}
    bn, bd = BOOTW @ num, BOOTW @ den
    with np.errstate(invalid='ignore', divide='ignore'):
        b = bn / bd
    b = b[np.isfinite(b)]
    return {'est': rnd(num.sum() / den.sum()), 'lo': rnd(np.percentile(b, 2.5)), 'hi': rnd(np.percentile(b, 97.5)),
            'n': int(round(den.sum())), 'groups': int((den > 0).sum())}


def diff_ci(num1, den1, num2, den2):
    num1, den1, num2, den2 = (np.asarray(x, float) for x in (num1, den1, num2, den2))
    est = num1.sum() / den1.sum() - num2.sum() / den2.sum()
    with np.errstate(invalid='ignore', divide='ignore'):
        b = (BOOTW @ num1) / (BOOTW @ den1) - (BOOTW @ num2) / (BOOTW @ den2)
    b = b[np.isfinite(b)]
    return {'est': rnd(est), 'lo': rnd(np.percentile(b, 2.5)), 'hi': rnd(np.percentile(b, 97.5))}


def per_group(triples):
    num, den = np.zeros(len(GROUPS)), np.zeros(len(GROUPS))
    for ix, a, b in triples:
        num[ix] += a
        den[ix] += b
    return num, den


def win(a, b):
    return 1.0 if a > b else (0.5 if a == b else 0.0)


def pair_rate(sids, score, sel_a, sel_b, match=None, ro_sel=None, equal_item=False):
    """Same-readout P(score[a] > score[b]) over pairs (a in A, b in B), ties 1/2, pooled over pairs."""
    acc, per_item = [], collections.defaultdict(list)
    for (cid, sid), bs in by_ro.items():
        if sid not in sids or (ro_sel and not ro_sel(bs)):
            continue
        A = [b for b in bs if sel_a(b)]
        B = [b for b in bs if sel_b(b) and b not in A]
        for a in A:
            for b in B:
                if match and not match(a, b):
                    continue
                w = win(a[score], b[score])
                acc.append((a['ix'], w, 1.0))
                per_item[a['item_id']].append(w)
    out = ratio_ci(*per_group(acc))
    out['readouts'] = len({(cid, sid) for (cid, sid), bs in by_ro.items() if sid in sids
                           and (not ro_sel or ro_sel(bs)) and any(sel_a(b) for b in bs)
                           and any(sel_b(b) and not sel_a(b) for b in bs)})
    if equal_item and per_item:
        out['equal_item_weight_est'] = rnd(np.mean([np.mean(v) for v in per_item.values()]))
        out['items'] = len(per_item)
    return out


def feat_pair_rate(sids, feat, score, sel=lambda r: True):
    """Same-readout P(score[a] > score[b]) over pairs with feat[a] > feat[b]."""
    acc = []
    for (cid, sid), bs in by_ro.items():
        if sid not in sids:
            continue
        bs = [b for b in bs if sel(b)]
        for a in bs:
            for b in bs:
                if a is not b and a[feat] > b[feat]:
                    acc.append((a['ix'], win(a[score], b[score]), 1.0))
    return ratio_ci(*per_group(acc))


HIT = lambda r: r['label'] == 'hit'
NON = lambda r: r['label'] != 'hit'
WS = lambda r: r['label'] == 'wrong-specific'
MISS = lambda r: r['label'] == 'miss'
lenmatch = lambda a, b: abs(math.log(a['slen'] / b['slen'])) < LENR
tokmatch = lambda a, b: abs(math.log(a['stok'] / b['stok'])) < LENR
out = {'meta': {
    'family': 'multihop_mt', 'display': 'Multihop (multi-token)', 'settings': SHORT,
    'n_bullets': len(rows), 'n_readouts': len(by_ro), 'n_items': 100, 'n_groups': len(GROUPS),
    'bootstrap': {'unit': 'related-question group (94; nests the 100 items)', 'reps': NREP, 'seed': SEED,
                  'interval': 'percentile 2.5-97.5'},
    'labels': 'hit = bullet alone hits >=1 required bridge under the judge regex (strict forms); wrong-specific = no '
              'strict/lenient hit but names a bank MC distractor; miss = rest. non-hit = miss + wrong-specific.',
    'pair_rate': 'P(score of the first group > second) over same-readout pairs, ties 1/2, pooled over pairs; '
                 '0.5 = no separation. *_pa = mid-rank percentile among bullets at the same index in readouts of the '
                 'same size and setting (Original, Best of 32 only; Combine order is greedy selection order).',
    'length_match': 'pairs whose scored texts (the <=32-token prefix the AR vector encodes; decoded from scored_token_ids for the 642 truncated atoms) differ by < 20% in '
                    'characters (|log ratio| < log 1.2), as in the Hallucination study; tok = same on scored tokens',
    'proxies': {'prompt_ov': 'share of the scored text\'s word tokens (Latin words or single CJK chars, lower-cased) '
                             'that occur in the item prompt',
                'prompt_head_ov': 'same for the first 8 tokens', 'cjk': 'CJK share of non-space scored chars',
                'other_name': 'non-initial capitalised word not in the prompt and not part of any bank form, alias or '
                              'distractor of the item (an invented / other specific name)',
                'tgt': 'bullet names the optional final answer (strict forms)'},
}}
log = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    log.append(s)


# ============================================================================= B1 bullet level: hit vs non-hit
P('# B1 bullet level')
mixed = lambda bs: any(HIT(b) for b in bs) and any(NON(b) for b in bs)
B1 = {}
for sid in SIDS:
    S = [sid]
    d = {
        'readouts_mixed': sum(1 for (c, s2), bs in by_ro.items() if s2 == sid and mixed(bs)),
        'hit_vs_nonhit': {sc: pair_rate(S, sc, HIT, NON, equal_item=True) for sc in ('share', 'solo', 'drop')},
    }
    if sid in OB:
        d['hit_vs_nonhit_position_adjusted'] = {sc + '_pa': pair_rate(S, sc + '_pa', HIT, NON)
                                                for sc in ('share', 'solo', 'drop')}
    sc_main = 'solo_pa' if sid in OB else 'solo'
    d['hit_vs_nonhit_length_matched'] = {
        'solo (scored chars within 20%)': pair_rate(S, 'solo', HIT, NON, match=lenmatch),
        'share (scored chars within 20%)': pair_rate(S, 'share', HIT, NON, match=lenmatch),
        'solo (scored tokens within 20%)': pair_rate(S, 'solo', HIT, NON, match=tokmatch)}
    if sid in OB:
        d['hit_vs_nonhit_length_matched']['solo_pa (scored chars within 20%)'] = pair_rate(
            S, 'solo_pa', HIT, NON, match=lenmatch)
        d['hit_vs_nonhit_length_matched']['share_pa (scored chars within 20%)'] = pair_rate(
            S, 'share_pa', HIT, NON, match=lenmatch)
    d['hit_vs_wrong_specific'] = {sc: pair_rate(S, sc, HIT, WS) for sc in ('share', 'solo', 'drop')}
    d['wrong_specific_vs_miss'] = {sc: pair_rate(S, sc, WS, MISS) for sc in ('share', 'solo')}
    d['robustness'] = {
        f'visible hit vs clean miss ({sc_main})': pair_rate(S, sc_main, lambda r: HIT(r) and r['hit_visible_to_vector'],
                                                           lambda r: r['clean_miss']),
        f'hit vs non-hit naming another name ({sc_main})': pair_rate(S, sc_main, HIT,
                                                                    lambda r: NON(r) and r['other_name'] == 1),
        'hit vs non-hit naming another name, length-matched (solo)': pair_rate(
            S, 'solo', HIT, lambda r: NON(r) and r['other_name'] == 1, match=lenmatch),
        f'hit vs non-hit that does NOT name the final answer ({sc_main})': pair_rate(
            S, sc_main, HIT, lambda r: NON(r) and not r['tgt']),
        f'hit without final answer vs non-hit without final answer ({sc_main})': pair_rate(
            S, sc_main, lambda r: HIT(r) and not r['tgt'], lambda r: NON(r) and not r['tgt']),
        f'lenient hit vs lenient non-hit ({sc_main})': pair_rate(S, sc_main, lambda r: r['label_lenient'] == 'hit',
                                                                lambda r: r['label_lenient'] != 'hit'),
        f'near-hit (lenient only) vs clean miss ({sc_main})': pair_rate(S, sc_main, lambda r: r['near_hit'],
                                                                       lambda r: r['clean_miss']),
        f'hit vs non-hit, coef > 0 both ({sc_main})': pair_rate(S, sc_main, lambda r: HIT(r) and r['coefficient'] > 0,
                                                               lambda r: NON(r) and r['coefficient'] > 0),
        'hit vs non-hit, coef > 0 both (drop)': pair_rate(S, 'drop', lambda r: HIT(r) and r['coefficient'] > 0,
                                                          lambda r: NON(r) and r['coefficient'] > 0),
    }
    d['slices'] = {}
    for nm, Ls in (('L20-32', (20, 24, 28, 32)), ('L36-48', (36, 40, 44, 48)), ('L52-60', (52, 56, 60))):
        d['slices'][f'{nm} ({sc_main})'] = pair_rate(S, sc_main, HIT, NON, ro_sel=lambda bs, Ls=Ls: bs[0]['layer'] in Ls)
    for sf in ('2hop', '3hop'):
        d['slices'][f'{sf} ({sc_main})'] = pair_rate(S, sc_main, HIT, NON, ro_sel=lambda bs, sf=sf: bs[0]['subfamily'] == sf)
    d['slices'][f'readout passes ({sc_main})'] = pair_rate(S, sc_main, HIT, NON, ro_sel=lambda bs: bs[0]['readout_pass'])
    d['slices'][f'readout fails (3-hop partial) ({sc_main})'] = pair_rate(
        S, sc_main, HIT, NON, ro_sel=lambda bs: not bs[0]['readout_pass'])
    # top / bottom share bullet in mixed readouts vs chance
    tops, bots = [], []
    for (c, s2), bs in by_ro.items():
        if s2 != sid or not mixed(bs):
            continue
        exp = sum(HIT(b) for b in bs) / len(bs)
        top = max(bs, key=lambda b: b['share'])
        bot = min(bs, key=lambda b: b['share'])
        tops.append((bs[0]['ix'], float(HIT(top)), exp))
        bots.append((bs[0]['ix'], float(HIT(bot)), exp))
    for nm, L in (('top_share_bullet_is_hit', tops), ('lowest_share_bullet_is_hit', bots)):
        n1, d1 = per_group((ix, o, 1.) for ix, o, e in L)
        n2, d2 = per_group((ix, e, 1.) for ix, o, e in L)
        d[nm] = {'observed': ratio_ci(n1, d1), 'chance': ratio_ci(n2, d2), 'observed_minus_chance': diff_ci(n1, d1, n2, d2)}
    B1[SHORT[sid]] = d
    P(SHORT[sid], 'mixed', d['readouts_mixed'], 'share', d['hit_vs_nonhit']['share'], 'solo',
      d['hit_vs_nonhit']['solo'])
    if sid in OB:
        P('   pa', d['hit_vs_nonhit_position_adjusted'])
    P('   lenmatched', d['hit_vs_nonhit_length_matched'])
    P('   top-share is hit', d['top_share_bullet_is_hit'])
# pooled over settings (pairs from all three; each readout once per setting)
B1['pooled_3_settings'] = {
    'share': pair_rate(SIDS, 'share', HIT, NON), 'solo': pair_rate(SIDS, 'solo', HIT, NON),
    'solo, length-matched': pair_rate(SIDS, 'solo', HIT, NON, match=lenmatch),
    'hit vs wrong-specific, share': pair_rate(SIDS, 'share', HIT, WS),
    'hit vs wrong-specific, solo': pair_rate(SIDS, 'solo', HIT, WS)}
P('pooled', B1['pooled_3_settings'])
out['B1_bullet_hit_vs_nonhit'] = B1


# ============================================================================= B2 within-readout regression
def within_reg(sid, y='solo'):
    names = ['is_hit', 'is_ws', 'near', 'tgt', 'log_slen', 'cjk', 'prompt_ov', 'other_name', 'truncated']
    if sid in OB:
        names += ['pos2', 'pos3', 'pos4']
    R = [r for r in rows if r['sid'] == sid]

    def vec(r):
        v = [r['is_hit'], r['is_ws'], r['near'], r['tgt'], math.log(r['slen']), r['cjk'], r['prompt_ov'],
             r['other_name'], float(r['truncated'])]
        if sid in OB:
            v += [float(r['j'] == 1), float(r['j'] == 2), float(r['j'] == 3)]
        return v

    X, Y = np.array([vec(r) for r in R]), np.array([r[y] for r in R])
    idx = collections.defaultdict(list)
    for i, r in enumerate(R):
        idx[(r['cell_id'], r['sid'])].append(i)
    Xd, Yd = X.copy(), Y.copy()
    for ii in idx.values():
        Xd[ii] -= X[ii].mean(0)
        Yd[ii] -= Y[ii].mean()
    sd = Xd.std(0)
    cont = {'log_slen', 'cjk', 'prompt_ov'}
    Xs = Xd / np.array([sd[i] if n in cont else 1.0 for i, n in enumerate(names)])
    ixs = np.array([r['ix'] for r in R])

    def fit(w, cols=None):
        ww = w[ixs]
        Z = Xs if cols is None else Xs[:, cols]
        return np.linalg.lstsq(Z.T @ (Z * ww[:, None]), Z.T @ (Yd * ww), rcond=None)[0]

    est = fit(np.ones(len(GROUPS)))
    boots = np.array([fit(w) for w in BOOTW])
    r2 = 1 - ((Yd - Xs @ est) ** 2).sum() / (Yd ** 2).sum()
    lab = [0, 1, 2]
    bl = fit(np.ones(len(GROUPS)), lab)
    r2l = 1 - ((Yd - Xs[:, lab] @ bl) ** 2).sum() / (Yd ** 2).sum()
    drops = {}
    for i, n in enumerate(names):
        keep = [x for x in range(len(names)) if x != i]
        bk = fit(np.ones(len(GROUPS)), keep)
        drops[n] = rnd(r2 - (1 - ((Yd - Xs[:, keep] @ bk) ** 2).sum() / (Yd ** 2).sum()))
    sdy = float(Yd.std())
    return {'n_bullets': len(R), 'within_readout_sd_of_y': rnd(sdy), 'within_readout_R2': rnd(r2),
            'within_readout_R2_labels_only(hit, ws, near)': rnd(r2l),
            'units': 'change in y (same readout) per within-readout SD for continuous features (log_slen, cjk, '
                     'prompt_ov), per 0->1 for binary ones',
            'coef': {n: {'est': rnd(est[i]), 'lo': rnd(np.percentile(boots[:, i], 2.5)),
                         'hi': rnd(np.percentile(boots[:, i], 97.5)), 'in_sd_of_y': rnd(est[i] / sdy, 3)}
                     for i, n in enumerate(names)},
            'R2_lost_without_feature': drops}


P('# B2 regression')
B2 = {}
for sid in SIDS:
    B2[SHORT[sid]] = {'solo': within_reg(sid, 'solo'), 'share': within_reg(sid, 'share')}
    c = B2[SHORT[sid]]['solo']['coef']
    P(SHORT[sid], 'solo is_hit', c['is_hit'], 'R2', B2[SHORT[sid]]['solo']['within_readout_R2'],
      'R2 labels', B2[SHORT[sid]]['solo']['within_readout_R2_labels_only(hit, ws, near)'])
out['B2_within_readout_regression'] = B2

# ============================================================================= T3 what FVE tracks inside a readout
P('# T3 what FVE tracks')
for r in rows:
    r['neg_cjk'] = -r['cjk']
    r['nocjk_vs_heavy'] = 1.0 if r['cjk'] == 0 else (0.0 if r['cjk'] >= .5 else float('nan'))
    r['non_redundant'] = 1.0 - r['coef0']
    r['later'] = r['j']
T3 = {}
for sid in SIDS:
    S = [sid]
    pr = {
        'longer bullet (scored chars) scores higher': feat_pair_rate(S, 'slen', 'solo'),
        'longer bullet (full chars) scores higher': feat_pair_rate(S, 'flen', 'solo'),
        'less CJK in scored part scores higher': feat_pair_rate(S, 'neg_cjk', 'solo'),
        'no-CJK bullet beats mostly-CJK (>=50%) bullet': feat_pair_rate(
            S, 'nocjk_vs_heavy', 'solo', sel=lambda r: not math.isnan(r['nocjk_vs_heavy'])),
        'more prompt overlap scores higher': feat_pair_rate(S, 'prompt_ov', 'solo'),
        'more prompt overlap in first 8 tokens scores higher': feat_pair_rate(S, 'prompt_head_ov', 'solo'),
        'names the final answer scores higher': feat_pair_rate(S, 'tgt', 'solo'),
        'names another (non-bank) capitalised name scores higher': feat_pair_rate(S, 'other_name', 'solo'),
        'hit scores higher than non-hit (raw solo, for comparison)': pair_rate(S, 'solo', HIT, NON),
    }
    if sid in OB:
        pr['later position scores higher'] = feat_pair_rate(S, 'later', 'solo')
        pr['non-redundant (coef > 0) scores higher'] = feat_pair_rate(S, 'non_redundant', 'solo')
    # how hit bullets differ from their non-hit siblings (the confounds)
    conf = {
        'hit is longer (scored chars)': pair_rate(S, 'slen', HIT, NON),
        'hit is longer (full chars)': pair_rate(S, 'flen', HIT, NON),
        'hit has less CJK': pair_rate(S, 'neg_cjk', HIT, NON),
        'hit has more prompt overlap': pair_rate(S, 'prompt_ov', HIT, NON),
        'hit names the final answer more often': pair_rate(S, 'tgt', HIT, NON),
        'hit is truncated (>32 tokens) more often': pair_rate(S, 'truncated', HIT, NON),
    }
    if sid in OB:
        conf['hit sits later in the list'] = pair_rate(S, 'later', HIT, NON)
        conf['hit is non-redundant (coef > 0) more often'] = pair_rate(S, 'non_redundant', HIT, NON)
    R = [r for r in rows if r['sid'] == sid]
    rates = {}
    for nm, sel in (('hit', HIT), ('wrong-specific', WS), ('miss', MISS), ('all', lambda r: True)):
        sub = [r for r in R if sel(r)]
        n_, d_ = per_group((r['ix'], r['coef0'], 1.) for r in sub)
        rates[nm] = {'p_coef0': ratio_ci(n_, d_) if sid in OB else None,
                     'mean_cjk': rnd(np.mean([r['cjk'] for r in sub])), 'mean_scored_chars': rnd(np.mean([r['slen'] for r in sub]), 1),
                     'mean_scored_tokens': rnd(np.mean([r['stok'] for r in sub]), 2),
                     'p_names_final_answer': rnd(np.mean([r['tgt'] for r in sub])),
                     'mean_prompt_ov': rnd(np.mean([r['prompt_ov'] for r in sub])),
                     'p_truncated': rnd(np.mean([float(r['truncated']) for r in sub])),
                     'mean_solo': rnd(np.mean([r['solo'] for r in sub])), 'mean_share': rnd(np.mean([r['share'] for r in sub]))}
    T3[SHORT[sid]] = {'pair_rates_solo': pr, 'hit_vs_nonhit_sibling_features': conf, 'label_profiles': rates}
    P(SHORT[sid], {k: v['est'] for k, v in pr.items()})
    P('   conf', {k: v['est'] for k, v in conf.items()})
out['T3_what_fve_tracks'] = T3

# ============================================================================= R readout level
P('# R readout level')
JUD = {}
for cond in sorted(set(SINGLE) | set(SIDS)):
    JUD[cond] = load.load_judgments(cond)[0]
ro = {}  # (cell, sid) -> readout record
for (cid, sid), bs in by_ro.items():
    c = cells[cid]
    j = JUD[sid][(c['item_id'], c['layer'], c['position'])]
    assert j['cell_pass'] == bs[0]['readout_pass']
    ro[(cid, sid)] = {'cid': cid, 'sid': sid, 'item': c['item_id'], 'L': c['layer'], 'ix': GIX[c['group_id']],
                      'fve': c['settings'][sid]['fve'], 'pass': bool(j['cell_pass'])}
# layer-demeaned FVE (setting x layer mean over items)
mu = collections.defaultdict(list)
for v in ro.values():
    mu[(v['sid'], v['L'])].append(v['fve'])
for v in ro.values():
    v['fve_ld'] = v['fve'] - float(np.mean(mu[(v['sid'], v['L'])]))


def wauc(pos, wp, neg, wn):
    """weighted P(pos > neg), ties 1/2."""
    pos, wp, neg, wn = map(np.asarray, (pos, wp, neg, wn))
    if wp.sum() == 0 or wn.sum() == 0:
        return float('nan')
    o = np.argsort(neg)
    ns, nw = neg[o], wn[o]
    cw = np.concatenate([[0.], np.cumsum(nw)])
    lo = np.searchsorted(ns, pos, 'left')
    hi = np.searchsorted(ns, pos, 'right')
    below, eq = cw[lo], cw[hi] - cw[lo]
    return float((wp * (below + 0.5 * eq)).sum() / (wp.sum() * wn.sum()))


def auc_ci(recs, key='fve', strata=None):
    """Unpaired AUROC pass vs fail, optionally within strata (pairs only inside a stratum), group bootstrap."""
    st = collections.defaultdict(lambda: ([], []))
    for v in recs:
        st[strata(v) if strata else 0][0 if v['pass'] else 1].append(v)

    def one(w):
        num = den = 0.
        for P_, F_ in st.values():
            if not P_ or not F_:
                continue
            wp = np.array([w[v['ix']] for v in P_])
            wn = np.array([w[v['ix']] for v in F_])
            if wp.sum() == 0 or wn.sum() == 0:
                continue
            a = wauc([v[key] for v in P_], wp, [v[key] for v in F_], wn)
            num += a * wp.sum() * wn.sum()
            den += wp.sum() * wn.sum()
        return num / den if den else float('nan')

    est = one(np.ones(len(GROUPS)))
    b = np.array([one(w) for w in BOOTW])
    b = b[np.isfinite(b)]
    npairs = sum(len(P_) * len(F_) for P_, F_ in st.values())
    return {'est': rnd(est), 'lo': rnd(np.percentile(b, 2.5)), 'hi': rnd(np.percentile(b, 97.5)), 'pairs': npairs,
            'pass': sum(v['pass'] for v in recs), 'fail': sum(not v['pass'] for v in recs)}


R = {}
for sid in SIDS:
    recs = [v for v in ro.values() if v['sid'] == sid]
    fp = [v['fve'] for v in recs if v['pass']]
    ff = [v['fve'] for v in recs if not v['pass']]
    R[SHORT[sid]] = {
        'mean_fve_pass': rnd(np.mean(fp)), 'mean_fve_fail': rnd(np.mean(ff)),
        'auroc_unadjusted': auc_ci(recs),
        'auroc_within_layer': auc_ci(recs, strata=lambda v: v['L']),
        'auroc_within_item_across_layers_raw': auc_ci(recs, strata=lambda v: v['item']),
        'auroc_within_item_across_layers_layer_demeaned': auc_ci(recs, key='fve_ld', strata=lambda v: v['item']),
    }
    P(SHORT[sid], {k: (v['est'] if isinstance(v, dict) else v) for k, v in R[SHORT[sid]].items()})


# within cell, across the three settings (discordant pairs)
def within_cell_pairs(pairs_of_settings, key='fve'):
    acc = []
    counts = collections.Counter()
    for cid in cells:
        for s1, s2 in pairs_of_settings:
            a, b = ro[(cid, s1)], ro[(cid, s2)]
            if a['pass'] == b['pass']:
                counts['concordant'] += 1
                continue
            p_, f_ = (a, b) if a['pass'] else (b, a)
            acc.append((a['ix'], win(p_[key], f_[key]), 1.))
            counts[f'pass={SHORT[p_["sid"]]}'] += 1
    r = ratio_ci(*per_group(acc))
    r['counts'] = dict(counts)
    return r


R['within_cell_across_settings'] = {
    'all three settings': within_cell_pairs([(SIDS[0], SIDS[1]), (SIDS[0], SIDS[2]), (SIDS[1], SIDS[2])]),
    'Original vs Best of 32': within_cell_pairs([(SIDS[0], SIDS[1])]),
    'Original vs Combine 32': within_cell_pairs([(SIDS[0], SIDS[2])]),
    'Best of 32 vs Combine 32': within_cell_pairs([(SIDS[1], SIDS[2])]),
    'note': 'Best of 32 FVE >= Original FVE by construction (argmax over 32 samples incl. sample 0), so for that pair '
            'the rate is fixes / (fixes + breaks). Combine 32 FVE exceeds Original in most cells for the same reason.',
}
P('within cell across settings', {k: v['est'] for k, v in R['within_cell_across_settings'].items() if isinstance(v, dict)})

# within cell, across the 32 candidate samples that already have a judged verdict
cand = collections.defaultdict(dict)  # cid -> sample_index -> {fve, pass, conds}
trace_rank = {}
cstats = collections.Counter()
for line in open(TASK / 'inputs/multihop_mt_candidates.jsonl'):
    r = json.loads(line)
    cid = r['cell_id']
    c = cells[cid]
    key = (c['item_id'], c['layer'], c['position'])
    tr = {t['sample_index']: t['score'] for t in r['trace32']}
    order = sorted(tr, key=lambda i: tr[i])
    rk = {i: (order.index(i) + 0.5) / 32 for i in tr}
    S_ = {s['cond']: s for s in r['selections']}
    for cond in SINGLE:
        s = S_[cond]
        assert len(s['samples']) == 1 and s['expansion_text_equal'] is True
        i = s['samples'][0]
        assert abs(tr[i] - s['fve']) < 1e-6
        p = bool(JUD[cond][key]['cell_pass'])
        rec = cand[cid].setdefault(i, {'fve': tr[i], 'pass': p, 'conds': [], 'rank32': rk[i]})
        if rec['pass'] != p:
            cstats['same_sample_verdict_disagree'] += 1
        rec['conds'].append(cond)
    trace_rank[cid] = tr
    cstats['cells'] += 1
assert cstats['same_sample_verdict_disagree'] == 0, cstats


def cand_pairs(sel):
    acc = []
    cells_disc = 0
    for cid, d in cand.items():
        ix = GIX[cells[cid]['group_id']]
        ss = [(i, v) for i, v in d.items() if sel(v)]
        P_ = [v for i, v in ss if v['pass']]
        F_ = [v for i, v in ss if not v['pass']]
        if P_ and F_:
            cells_disc += 1
        for a in P_:
            for b in F_:
                acc.append((ix, win(a['fve'], b['fve']), 1.))
    r = ratio_ci(*per_group(acc))
    r['cells_with_both'] = cells_disc
    return r


nd = [len(d) for d in cand.values()]
R['within_cell_across_judged_candidates'] = {
    'distinct_judged_samples_per_cell': {'mean': rnd(np.mean(nd), 2), 'min': int(min(nd)), 'max': int(max(nd))},
    'candidates_judged': int(sum(nd)), 'candidates_pass': int(sum(v['pass'] for d in cand.values() for v in d.values())),
    'all judged samples': cand_pairs(lambda v: True),
    'random-pick samples only (sample 0 + random_complete-nK)': cand_pairs(lambda v: any(c in RANDOMISH for c in v['conds'])),
    'note': 'Candidates = distinct samples (of the 32) that some single-sample condition selected and the expansion '
            'already judged: capped_n1, best_n_exact-n{1,2,4,8,16,32}, random_complete-n{1,...,32}, '
            'best_n_specificity_{mean,max}-n32. FVE = the Best-of-32 trace score of that sample (checked equal to the '
            'condition\'s own exact fit). Same sample -> same verdict in every condition (checked).',
}
# pass rate by within-cell FVE rank among all 32 samples (random-pick samples only, so rank is ~uniform)
bins = [(0, .25), (.25, .5), (.5, .75), (.75, 1.01)]
rk_rows = [(GIX[cells[cid]['group_id']], v['rank32'], float(v['pass'])) for cid, d in cand.items() for v in d.values()
           if any(c in RANDOMISH for c in v['conds'])]
R['within_cell_across_judged_candidates']['pass_rate_by_fve_rank_quartile_among_32 (random-pick samples)'] = {
    f'{lo:.2f}-{min(hi, 1):.2f}': ratio_ci(*per_group((ix, p, 1.) for ix, q, p in rk_rows if lo <= q < hi))
    for lo, hi in bins}
top_n, top_d = per_group((ix, p, 1.) for ix, q, p in rk_rows if q >= .5)
bot_n, bot_d = per_group((ix, p, 1.) for ix, q, p in rk_rows if q < .5)
R['within_cell_across_judged_candidates']['top_half_minus_bottom_half_pass_rate (random-pick samples)'] = diff_ci(
    top_n, top_d, bot_n, bot_d)
# selection lift: argmax sample vs random sample
lift = {}
for cond in ['capped_n1-n1', 'random_complete-n32', 'best_n_exact-n32', 'best_n_specificity_mean-n32']:
    n_, d_ = per_group((GIX[cells[cid]['group_id']], float(JUD[cond][(cells[cid]['item_id'], cells[cid]['layer'],
                                                                         cells[cid]['position'])]['cell_pass']), 1.)
                       for cid in cells)
    lift[cond] = ratio_ci(n_, d_)
R['within_cell_across_judged_candidates']['cell_pass_rate_by_single_sample_selector'] = lift
# cells whose random-pick samples include both a pass and a fail: pass rate by FVE-rank quartile there
disc = {cid for cid, d in cand.items()
        if len({v['pass'] for v in d.values() if any(c in RANDOMISH for c in v['conds'])}) == 2}
rk_disc = [(GIX[cells[cid]['group_id']], v['rank32'], float(v['pass'])) for cid, d in cand.items() if cid in disc
           for v in d.values() if any(c in RANDOMISH for c in v['conds'])]
R['within_cell_across_judged_candidates']['pass_rate_by_fve_rank_quartile_in_cells_with_both (random-pick samples)'] = {
    'cells': len(disc), **{f'{lo:.2f}-{min(hi, 1):.2f}': ratio_ci(*per_group((ix, p, 1.) for ix, q, p in rk_disc
                                                                           if lo <= q < hi)) for lo, hi in bins}}
tq_n, tq_d = per_group((ix, p, 1.) for ix, q, p in rk_disc if q >= .75)
rq_n, rq_d = per_group((ix, p, 1.) for ix, q, p in rk_disc if q < .75)
R['within_cell_across_judged_candidates']['top_quartile_minus_rest_in_cells_with_both'] = diff_ci(tq_n, tq_d, rq_n, rq_d)
ncell_any = sum(any(v['pass'] for v in d.values()) for d in cand.values())
ncell_all = sum(all(v['pass'] for v in d.values()) for d in cand.values())
R['within_cell_across_judged_candidates']['cells_by_judged_pool'] = {
    'no judged candidate passes': len(cand) - ncell_any, 'all judged candidates pass': ncell_all,
    'both': ncell_any - ncell_all}


# paired (same cell) differences between single-sample selectors
def paired_sel(c1, c2=None, nonzero_random=False):
    tri_a, tri_b = [], []
    for cid in cells:
        key = (cells[cid]['item_id'], cells[cid]['layer'], cells[cid]['position'])
        ix = GIX[cells[cid]['group_id']]
        tri_a.append((ix, float(JUD[c1][key]['cell_pass']), 1.))
        if nonzero_random:
            vs = [v['pass'] for i, v in cand[cid].items() if i != 0 and any(c in RANDOMISH for c in v['conds'])]
            if vs:
                tri_b.append((ix, float(np.mean(vs)), 1.))
            else:
                tri_b.append((ix, float(cand[cid][0]['pass']), 1.))
        else:
            tri_b.append((ix, float(JUD[c2][key]['cell_pass']), 1.))
    return diff_ci(*per_group(tri_a), *per_group(tri_b))


R['within_cell_across_judged_candidates']['paired_cell_pass_differences'] = {
    'Best of 32 (argmax FVE) minus random_complete-n32 (one random sample)': paired_sel('best_n_exact-n32', 'random_complete-n32'),
    'Best of 32 minus mean of the cell\'s other random-pick samples (excl. sample 0)': paired_sel('best_n_exact-n32', nonzero_random=True),
    'random_complete-n32 minus Original (sample 0)': paired_sel('random_complete-n32', 'capped_n1-n1'),
    'mean of other random-pick samples minus Original (sample 0)': {
        k: -v if isinstance(v, float) else v for k, v in paired_sel('capped_n1-n1', nonzero_random=True).items()},
}
_d = R['within_cell_across_judged_candidates']['paired_cell_pass_differences']['mean of other random-pick samples minus Original (sample 0)']
_d['lo'], _d['hi'] = _d['hi'], _d['lo']
R['within_cell_across_judged_candidates']['reference_pilot189_all_32_judged'] = (
    'olens-improve docs/experiments/012-all-candidate-diagnostic.md: 24 development multihop cells with all 32 capped '
    'samples judged; within-cell good-vs-bad FVE rank rate .541 (equal-cell mean .496), related-group interval includes .5; '
    'a passing candidate existed in 14/24 cells, A32 selected one in 7/24 (random expectation 6.09).')
P('candidates', {k: (v['est'] if isinstance(v, dict) and 'est' in v else v) for k, v in
                 R['within_cell_across_judged_candidates'].items() if k != 'reference_pilot189_all_32_judged'})

# setting changes vs Original (cell level and question level)
chg = {}
for sid in SIDS[1:]:
    fix = brk = 0
    tri = []
    gains = []
    for cid in cells:
        a, b = ro[(cid, SIDS[0])], ro[(cid, sid)]
        tri.append((a['ix'], float(b['pass']) - float(a['pass']), 1.))
        fix += (not a['pass']) and b['pass']
        brk += a['pass'] and (not b['pass'])
        gains.append((b['fve'] - a['fve'], a, b))
    n_, d_ = per_group(tri)
    q = np.quantile([g for g, _, _ in gains], [1 / 3, 2 / 3])
    terc = {}
    for nm, lo, hi in (('low', -9, q[0]), ('mid', q[0], q[1]), ('high', q[1], 9)):
        sub = [(a, b) for g, a, b in gains if lo <= g < hi or (nm == 'high' and g >= q[1])]
        fx = per_group((a['ix'], float(b['pass']), 1.) for a, b in sub if not a['pass'])
        bk = per_group((a['ix'], float(not b['pass']), 1.) for a, b in sub if a['pass'])
        terc[nm] = {'fve_gain_range': [rnd(lo if nm != 'low' else min(g for g, _, _ in gains)),
                                       rnd(hi if nm != 'high' else max(g for g, _, _ in gains))],
                    'fix_rate_of_failing_original': ratio_ci(*fx), 'break_rate_of_passing_original': ratio_ci(*bk),
                    'net_cells': int(sum(float(b['pass']) - float(a['pass']) for a, b in sub))}
    item_pass = collections.defaultdict(lambda: [False, False])
    for cid in cells:
        it = cells[cid]['item_id']
        item_pass[it][0] |= ro[(cid, SIDS[0])]['pass']
        item_pass[it][1] |= ro[(cid, sid)]['pass']
    qi = per_group((GIX[ITEM_GROUP[it]], float(v[1]) - float(v[0]), 1.) for it, v in item_pass.items())
    chg[SHORT[sid]] = {'cells_fixed': int(fix), 'cells_broken': int(brk),
                       'cell_pass_change': ratio_ci(n_, d_),
                       'question_pass': f"{sum(v[1] for v in item_pass.values())}/100 vs "
                                        f"{sum(v[0] for v in item_pass.values())}/100",
                       'question_pass_change': ratio_ci(*qi),
                       'questions_gained': sum((not v[0]) and v[1] for v in item_pass.values()),
                       'questions_lost': sum(v[0] and (not v[1]) for v in item_pass.values()),
                       'mean_fve_gain': rnd(np.mean([g for g, _, _ in gains])),
                       'by_fve_gain_tertile': terc}
chg['cell_pass_counts'] = {SHORT[s]: sum(ro[(c, s)]['pass'] for c in cells) for s in SIDS}
chg['expanded_report_reference'] = (
    'docs/EXPANDED_REPORT.md: question-level recovery 34/100 (original released lens and four-bullet original), '
    'Best of 32 40/100 (+6.0 pp; fit +4.972 pp on 1,100 sites; joint interval includes no change), Combine 32 41/100 '
    '(+7.0 pp; fit +7.219 pp). Mean saved FVE 30.20% / 35.17% / 37.42%.')
R['setting_changes_vs_original'] = chg
P('changes', {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'by_fve_gain_tertile'})
              for k, v in chg.items()})
out['R_readout_level'] = R


# ============================================================================= examples + reading sample
def brec(b):
    ev = [{'kind': e['kind'], 'role': e['role'], 'form': e['form'], 'quote': e['quote']} for e in b['evidence_primary']]
    return {'index': b['j'], 'text': b['text'].rstrip('\n'),
            'scored_text_if_truncated': b['scored_text'] if b['truncated'] else None,
            'label': b['label'], 'label_lenient': b['label_lenient'], 'near_hit': b['near_hit'],
            'strict_roles': b['strict_roles'], 'evidence_primary': ev,
            'names_final_answer': b['target_hit_strict'], 'distractors_named': b['distractor_roles'],
            'hit_visible_to_vector': b['hit_visible_to_vector'], 'gold_cut_at_end': b['gold_cut_at_end'],
            'solo_fve': rnd(b['solo']), 'shapley_share': rnd(b['share']), 'loo_drop': rnd(b['drop']),
            'nnls_coefficient': rnd(b['coefficient'], 3), 'coef0': bool(b['coef0']),
            'scored_tokens': b['stok'], 'truncated': b['truncated'],
            'share_rank_in_readout': 1 + sorted(by_ro[(b['cell_id'], b['sid'])], key=lambda x: -x['share']).index(b),
            'solo_pa': rnd(b.get('solo_pa')) if b['sid'] in OB else None}


def case(b, stratum, cid_):
    c = cells[b['cell_id']]
    it = items[b['item_id']]
    bs = by_ro[(b['cell_id'], b['sid'])]
    others = {SHORT[s]: {'fve': rnd(ro[(b['cell_id'], s)]['fve']), 'pass': ro[(b['cell_id'], s)]['pass'],
                         'labels': [x['label'] for x in by_ro[(b['cell_id'], s)]]} for s in SIDS if s != b['sid']}
    return {'case_id': cid_, 'stratum': stratum, 'k': b['k'], 'cell_id': b['cell_id'], 'setting': SHORT[b['sid']],
            'setting_id': b['sid'], 'item_id': b['item_id'], 'group_id': b['group_id'], 'subfamily': b['subfamily'],
            'split': b['split'], 'layer': c['layer'], 'position': c['position'],
            'read_site': {'kind': c['read_position_kind'], 'token': c['token'],
                          'note': 'activation read at the final prompt token; the next token the model would write is '
                                  'the start of its answer'},
            'prompt': it['prompt'],
            'target': {'final_answer': it['target'], 'final_answer_alts': it['target_alts'],
                       'final_answer_is_optional': True,
                       'required_bridges_gold': it['gold'], 'required_roles': it['required_roles'],
                       'strict_forms_credited': it['strict_forms'], 'lenient_aliases': it['lenient'],
                       'bank_distractors': it['distractors']},
            'focus_bullet_index': b['j'],
            'readout': {'joint_fve': rnd(ro[(b['cell_id'], b['sid'])]['fve']), 'judge_cell_pass': bs[0]['readout_pass'],
                        'judge_unit_hits': bs[0]['readout_unit_hits'], 'n_bullets': len(bs),
                        'bullets': [brec(x) for x in bs]},
            'same_cell_other_settings': others}


def pick(pool, n_per_setting, used_items, rnd_, max_per_item=1):
    chosen = []
    for sid in SIDS:
        P_ = [b for b in pool if b['sid'] == sid]
        rnd_.shuffle(P_)
        got = 0
        for b in P_:
            if got >= n_per_setting:
                break
            if used_items[b['item_id']] >= max_per_item:
                continue
            used_items[b['item_id']] += 1
            chosen.append(b)
            got += 1
    return chosen


rnd_ = random.Random(SEED)
tops = {}
bots = {}
for (cid, sid), bs in by_ro.items():
    tops[(cid, sid)] = max(bs, key=lambda b: b['share'])
    bots[(cid, sid)] = min(bs, key=lambda b: b['share'])
poolA = [t for (cid, sid), t in tops.items() if HIT(t) and mixed(by_ro[(cid, sid)])]
poolB = [t for (cid, sid), t in bots.items() if HIT(t) and mixed(by_ro[(cid, sid)])]
poolC_ws = [t for (cid, sid), t in tops.items() if WS(t)]
poolC_non = [t for (cid, sid), t in tops.items() if NON(t) and not WS(t) and mixed(by_ro[(cid, sid)])]
usedA, usedB, usedC = collections.Counter(), collections.Counter(), collections.Counter()
A = pick(poolA, 4, usedA, rnd_)
B = pick(poolB, 4, usedB, rnd_)
Cws = pick(poolC_ws, 2, usedC, rnd_)
Cnon = []
for sid in SIDS:
    need = 4 - sum(1 for b in Cws if b['sid'] == sid)
    P_ = [b for b in poolC_non if b['sid'] == sid]
    rnd_.shuffle(P_)
    for b in P_:
        if need <= 0:
            break
        if usedC[b['item_id']] >= 1:
            continue
        usedC[b['item_id']] += 1
        Cnon.append(b)
        need -= 1
C = Cws + Cnon
assert len(A) == len(B) == len(C) == 12, (len(A), len(B), len(C))
cases = []
for nm, L, tag in (('A_high_share_hit', A, 'A'), ('B_low_share_hit', B, 'B'), ('C_high_share_nonhit_or_wrong_specific', C, 'C')):
    for i, b in enumerate(sorted(L, key=lambda x: (SIDS.index(x['sid']), -x['share']))):
        cases.append(case(b, nm, f'{tag}{i + 1:02d}'))
EXAMPLE_KEYS = [  # (k, setting, focus bullet index): the verbatim examples quoted in ANALYSIS.md
    ('mhh-mansamusa-sahili.L60.p38', 'capped_n1-n1', 3), ('mhh-wyeth-chaddsford.L60.p49', 'best_n_exact-n32', 3),
    ('mhh-fourrow-layout.L60.p26', 'capped_n1-n1', 0), ('mhh-fourrow-layout.L60.p26', 'best_n_exact-n32', 0),
    ('mhh-borglum-son.L60.p33', 'best_n_exact-n32', 1), ('mhh-51peg-peebles.L60.p46', 'capped_n1-n1', 1),
    ('mhh-wallenstein-schiller-raeuber.L60.p46', 'best_n_exact-n32', 3), ('mhh-akbar-dinilahi.L60.p31', 'best_n_exact-n32', 1),
    ('mhh-moho-mohole.L40.p51', 'capped_n1-n1', 1)]
bykey = {(b['k'], b['sid'], b['j']): b for b in rows}
ex_cases = [case(bykey[key], 'analysis_example', f'X{i + 1:02d}') for i, key in enumerate(EXAMPLE_KEYS)]
sample = {'meta': {
    'family': 'multihop_mt', 'display': 'Multihop (multi-token)', 'n_cases': len(cases), 'seed': SEED,
    'strata': {
        'A_high_share_hit': f'hit bullet that is the top-Shapley-share bullet of a mixed readout (>=1 hit, >=1 non-hit); '
                            f'pool {len(poolA)}; 4 per setting, random, <=1 per item',
        'B_low_share_hit': f'hit bullet that is the lowest-share bullet of a mixed readout; pool {len(poolB)}; 4 per '
                           f'setting, random, <=1 per item',
        'C_high_share_nonhit_or_wrong_specific': f'top-share bullet that is wrong-specific (any readout; pool '
                                                 f'{len(poolC_ws)}; up to 2 per setting) or otherwise non-hit in a mixed '
                                                 f'readout (pool {len(poolC_non)}); 4 per setting, random, <=1 per item'},
    'labels': out['meta']['labels'],
    'scores': 'solo_fve = FVE of the bullet alone; shapley_share = exact Shapley share of the joint FVE over the '
              'readout\'s bullets; loo_drop = joint FVE lost when the bullet is left out; coef0 = zero NNLS weight '
              '(redundant). The AR vector encodes only the first 32 tokens of each bullet (scored_text_if_truncated).',
    'reader_questions': [
        'Does the focus bullet state the hidden bridge entity (the gold), as a claim about the right slot?',
        'Is the high/low score explained by the bullet\'s frame (length, language, list position, echo of the prompt, '
        'naming the final answer) rather than by the bridge name?',
        'For non-hit / wrong-specific bullets: is there a wrong value of the right kind, an invented name, or only '
        'generic text?'],
    'source_files': ['tasks/multihop_mt/bullet_table.jsonl', 'tasks/multihop_mt/item_targets.json',
                     'tasks/multihop_mt/inputs/multihop_mt_three_settings.jsonl']},
    'cases': cases,
    'analysis_examples': ex_cases}
sample['meta']['analysis_examples'] = ('X01-X09: the readouts quoted in ANALYSIS.md (chosen by hand from the extremes '
                                       'printed in analysis.json example_candidates); not part of the 36-case strata')
(TASK / 'read_sample.json').write_text(json.dumps(sample, ensure_ascii=False, indent=1))
P('read_sample', len(cases), 'cases; pools A/B/Cws/Cnon', len(poolA), len(poolB), len(poolC_ws), len(poolC_non))

# example candidates for the write-up (printed; chosen by hand into ANALYSIS.md)
EX = {}


def exrow(b):
    return {'k': b['k'], 'setting': SHORT[b['sid']], 'index': b['j'], 'label': b['label'],
            'text': b['text'].rstrip('\n'), 'solo': rnd(b['solo'], 3), 'share': rnd(b['share'], 3),
            'drop': rnd(b['drop'], 4), 'coef0': bool(b['coef0']), 'readout_fve': rnd(b['readout_fve_saved'], 3),
            'pass': b['readout_pass'], 'tgt': b['target_hit_strict'], 'gold': b['gold'],
            'siblings': [(x['j'], x['label'], rnd(x['solo'], 3), rnd(x['share'], 3), x['text'].rstrip('\n'))
                         for x in by_ro[(b['cell_id'], b['sid'])] if x is not b]}


EX['high_fve_hit'] = [exrow(b) for b in sorted(poolA, key=lambda b: -b['share'])[:15]]
EX['low_fve_hit'] = [exrow(b) for b in sorted(poolB, key=lambda b: b['share'])[:15]]
EX['high_fve_wrong_specific'] = [exrow(b) for b in sorted(poolC_ws, key=lambda b: -b['share'])[:15]]
EX['top_nonhit_over_hit'] = [exrow(b) for b in sorted(poolC_non, key=lambda b: -b['share'])[:10]]
out['example_candidates'] = EX
(TASK / 'analysis.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
P('wrote analysis.json, read_sample.json')
