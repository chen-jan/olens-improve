"""Red-team C1, part 2: robustness of the length-matched separation; flexible length control; examples.

Run: ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B confounds2.py
"""
import collections
import json
import math
import os

import numpy as np

HERE_RT = os.path.dirname(os.path.abspath(__file__))
SYN = os.path.join(os.path.dirname(HERE_RT), 'synth_tests.py')
src = open(SYN).read().splitlines()
code = '\n'.join(src[14:42]) + '\n' + '\n'.join(src[279:527])
ns = {'__file__': SYN, '__name__': 'synth_loader'}
exec(compile(code, SYN, 'exec'), ns)
rows, LAB, by_ro, readouts, cells, items = (ns[x] for x in ['rows', 'LAB', 'by_ro', 'readouts', 'cells', 'items'])
ratio_ci, diff_ci, per_item, win, ITEM_IX, ITEM_IDS, BOOTW, SHORT, SIDS = (
    ns[x] for x in ['ratio_ci', 'diff_ci', 'per_item', 'win', 'ITEM_IX', 'ITEM_IDS', 'BOOTW', 'SHORT', 'SIDS'])
OB = ['capped_n1-n1', 'best_n_exact-n32']
SC = {sid: ('solo_pa' if sid in OB else 'solo') for sid in SIDS}
for r in LAB:
    r['log_slen'] = math.log(max(1, r['scored_len']))
    if r['label'] == 'w' and 'w_text' in r:
        r['wcov'] = min(1.0, r['w_frac'] * r['len'] * r['w_scored_frac'] / max(1, r['scored_len']))
out = {}


def ppr(score_of, sids, pair_ok=None, sel_w=lambda r: True, wlab='w'):
    acc = []
    for (k, sid), bs in by_ro.items():
        if sid not in sids:
            continue
        sc = score_of[sid]
        for w in [b for b in bs if b['label'] == wlab and sel_w(b)]:
            for c in [b for b in bs if b['label'] == 'c']:
                if pair_ok is None or pair_ok(w, c):
                    acc.append((w['ix'], win(c[sc], w[sc]), 1.0))
    return ratio_ci(*per_item(acc))


# 1. thresholds and token-count matching
o = {}
for nm, ok in [('chars within 10%', lambda w, c: abs(w['log_slen'] - c['log_slen']) < math.log(1.1)),
               ('chars within 20%', lambda w, c: abs(w['log_slen'] - c['log_slen']) < math.log(1.2)),
               ('chars within 35%', lambda w, c: abs(w['log_slen'] - c['log_slen']) < math.log(1.35)),
               ('word-tokens within +-1', lambda w, c: abs(w['n_tok_scored'] - c['n_tok_scored']) <= 1),
               ('wrong SHORTER than clean (scored chars)', lambda w, c: w['scored_len'] < c['scored_len']),
               ('wrong LONGER than clean (scored chars)', lambda w, c: w['scored_len'] > c['scored_len'])]:
    o[nm] = {SHORT[s]: ppr(SC, [s], ok) for s in SIDS}
    o[nm]['pooled'] = ppr(SC, SIDS, ok)
out['1_length_matching_robustness'] = o


# 2. flexible length control: within-readout regression with length-decile dummies (per setting)
def within_reg(sid, flex, label_terms=True):
    R = [r for r in LAB if r['sid'] == sid]
    dec = np.quantile([r['log_slen'] for r in R], np.linspace(0.1, 0.9, 9))
    P = sid in OB

    def vec(r):
        v = []
        if label_terms:
            v += [r['label'] == 'w', r['label'] == 'o']
        if P:
            v += [r['j'] == 1, r['j'] == 2, r['j'] == 3]
        if flex:
            d = int(np.searchsorted(dec, r['log_slen']))
            v += [d == i for i in range(1, 10)]
        else:
            v += [r['log_slen']]
        return v

    X = np.array([vec(r) for r in R], float)
    Y = np.array([r['solo'] for r in R])
    idx = collections.defaultdict(list)
    for i, r in enumerate(R):
        idx[r['k']].append(i)
    for ii in idx.values():
        X[ii] -= X[ii].mean(0)
        Y[ii] -= Y[ii].mean()
    ixs = np.array([r['ix'] for r in R])

    def fit(w):
        ww = w[ixs]
        return np.linalg.lstsq(X.T @ (X * ww[:, None]), X.T @ (Y * ww), rcond=None)[0]

    est = fit(np.ones(len(ITEM_IDS)))
    res = Y - X @ est
    r2 = 1 - (res ** 2).sum() / (Y ** 2).sum()
    o = {'R2': float(r2), 'sd_within': float(Y.std())}
    if label_terms:
        boots = np.array([fit(w) for w in BOOTW])
        o['is_w'] = {'est': round(float(est[0]), 4), 'lo': round(float(np.percentile(boots[:, 0], 2.5)), 4),
                     'hi': round(float(np.percentile(boots[:, 0], 97.5)), 4)}
        o['is_w_in_sd'] = round(float(est[0] / Y.std()), 3)
        o['is_o'] = {'est': round(float(est[1]), 4), 'lo': round(float(np.percentile(boots[:, 1], 2.5)), 4),
                     'hi': round(float(np.percentile(boots[:, 1], 97.5)), 4)}
    return o


o2 = {}
for sid in SIDS:
    full = within_reg(sid, True)
    nolab = within_reg(sid, True, label_terms=False)
    o2[SHORT[sid]] = {'flex_length': full, 'incremental_R2_of_labels_given_position_and_length':
                      round(full['R2'] - nolab['R2'], 5)}
out['2_flexible_length_regression'] = o2

# 3. wrong bullets longer? median scored chars by label
o3 = {}
for sid in SIDS:
    o3[SHORT[sid]] = {lab: float(np.median([r['scored_len'] for r in LAB if r['sid'] == sid and r['label'] == lab]))
                      for lab in 'wco'}
out['3_median_scored_chars_by_label'] = o3

# 4. readout level: Best of 32 minus Original hallucinated rate (same cells)
num_o, den = per_item((ITEM_IX[ro['item']], float(ro['label'] == 'hallucinated'), 1.)
                      for (k, s2), ro in readouts.items() if s2 == 'capped_n1-n1')
num_b, den_b = per_item((ITEM_IX[ro['item']], float(ro['label'] == 'hallucinated'), 1.)
                        for (k, s2), ro in readouts.items() if s2 == 'best_n_exact-n32')
out['4_best_minus_original_p_hallucinated'] = diff_ci(num_b, den_b, num_o, den)

# 5. example pairs: same readout, scored length within 10%, wrong bullet with wrong span covering >= 60% of the
# scored text (or head-located), wrong solo clearly below clean solo
ex = []
for (k, sid), bs in by_ro.items():
    for w in [b for b in bs if b['label'] == 'w' and b.get('wcov', 0) >= .6 and b['coef'] >= 0]:
        for c in [b for b in bs if b['label'] == 'c' and b['n_true'] > 0 and b['n_disp'] == 0]:
            if abs(w['log_slen'] - c['log_slen']) < math.log(1.1) and c['solo'] - w['solo'] > .05:
                ex.append({'k': k, 'setting': SHORT[sid], 'wrong_j': w['j'], 'wrong_text': w['text'],
                           'wrong_span': w['w_text'], 'wrong_solo': w['solo'], 'wrong_share': w['share'],
                           'wrong_coef': w['coef'], 'clean_j': c['j'], 'clean_text': c['text'],
                           'clean_solo': c['solo'], 'clean_share': c['share'], 'clean_n_true': c['n_true'],
                           'fve': readouts[(k, sid)]['fve'], 'L': readouts[(k, sid)]['L']})
out['5_examples_n'] = len(ex)
rng = np.random.default_rng(1)
pick = [ex[i] for i in rng.choice(len(ex), size=min(12, len(ex)), replace=False)]
out['5_examples_random12'] = pick
# counter-examples: same filter but wrong solo clearly ABOVE clean
cx = []
for (k, sid), bs in by_ro.items():
    for w in [b for b in bs if b['label'] == 'w' and b.get('wcov', 0) >= .6]:
        for c in [b for b in bs if b['label'] == 'c' and b['n_true'] > 0 and b['n_disp'] == 0]:
            if abs(w['log_slen'] - c['log_slen']) < math.log(1.1) and w['solo'] - c['solo'] > .05:
                cx.append(1)
out['5_counter_examples_n'] = len(cx)

with open(os.path.join(HERE_RT, 'confounds2.json'), 'w') as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x))
print('done')
