"""Red-team of claim C1 (no separation anywhere): confound tests on all data (exploratory).

Reuses the Part-B loader of ../synth_tests.py (lines 15-42 and 280-527, executed in this namespace; nothing is
written by it). Outputs reading/redteam_C1/confounds.json.

Run: ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B confounds.py
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
label_pair_rate = ns['label_pair_rate']
OB = ['capped_n1-n1', 'best_n_exact-n32']
SC = {sid: ('solo_pa' if sid in OB else 'solo') for sid in SIDS}

for r in LAB:
    if r['label'] == 'w' and 'w_text' in r:
        # fraction of the SCORED text covered by verified wrong spans
        r['wcov'] = min(1.0, r['w_frac'] * r['len'] * r['w_scored_frac'] / max(1, r['scored_len']))
    r['log_slen'] = math.log(max(1, r['scored_len']))

out = {}


def pooled_pair_rate(score_of, sel_w=lambda r: True, sel_c=lambda r: True, sids=SIDS, pair_ok=None):
    """Same-readout P(clean > wrong) pooled over the given settings (score chosen per setting)."""
    acc = []
    for (k, sid), bs in by_ro.items():
        if sid not in sids:
            continue
        sc = score_of[sid]
        ws = [b for b in bs if b['label'] == 'w' and sel_w(b)]
        cs = [b for b in bs if b['label'] == 'c' and sel_c(b)]
        for w in ws:
            for c in cs:
                if pair_ok is None or pair_ok(w, c):
                    acc.append((w['ix'], win(c[sc], w[sc]), 1.0))
    return ratio_ci(*per_item(acc))


# ---------------------------------------------------------------- 1. length: wrong bullets are longer; matched pairs
len_ok = lambda w, c: abs(w['log_slen'] - c['log_slen']) < math.log(1.2)
o1 = {}
for sid in SIDS:
    o1[SHORT[sid]] = {
        'all_pairs': pooled_pair_rate(SC, sids=[sid]),
        'scored_length_within_20pct': pooled_pair_rate(SC, sids=[sid], pair_ok=len_ok),
        'scored_length_within_20pct_raw_solo': pooled_pair_rate({sid: 'solo'}, sids=[sid], pair_ok=len_ok),
    }
o1['pooled_3_settings_len_matched'] = pooled_pair_rate(SC, pair_ok=len_ok)
out['1_length_matched_pairs'] = o1


# ---------------------------------------------------------------- 2. regression without mediators
def within_reg(sid, names, vec, y='solo', sel=lambda r: True):
    R = [r for r in LAB if r['sid'] == sid and sel(r)]
    X = np.array([vec(r) for r in R], float)
    Y = np.array([r[y] for r in R], float)
    idx = collections.defaultdict(list)
    for i, r in enumerate(R):
        idx[r['k']].append(i)
    Xd, Yd = X.copy(), Y.copy()
    for ii in idx.values():
        Xd[ii] -= X[ii].mean(0)
        Yd[ii] -= Y[ii].mean()
    ixs = np.array([r['ix'] for r in R])

    def fit(w):
        ww = w[ixs]
        return np.linalg.lstsq(Xd.T @ (Xd * ww[:, None]), Xd.T @ (Yd * ww), rcond=None)[0]

    est = fit(np.ones(len(ITEM_IDS)))
    boots = np.array([fit(w) for w in BOOTW])
    res = Yd - Xd @ est
    return {'n': len(R), 'sd_within': round(float(Yd.std()), 4),
            'R2': round(float(1 - (res ** 2).sum() / (Yd ** 2).sum()), 4),
            'coef': {n: {'est': round(float(est[i]), 4), 'lo': round(float(np.percentile(boots[:, i], 2.5)), 4),
                         'hi': round(float(np.percentile(boots[:, i], 97.5)), 4)} for i, n in enumerate(names)}}


def posd(r):
    return [float(r['j'] == 1), float(r['j'] == 2), float(r['j'] == 3)]


o2 = {}
for sid in SIDS:
    P = sid in OB
    nm_a = ['is_w', 'is_o'] + (['pos2', 'pos3', 'pos4'] if P else [])
    va = lambda r, P=P: [r['label'] == 'w', r['label'] == 'o'] + (posd(r) if P else [])
    nm_b = nm_a + ['log_scored_len']
    vb = lambda r, P=P: va(r) + [r['log_slen']]
    has_sp = lambda r: r['label'] != 'w' or 'w_text' in r
    nm_c = ['w_head', 'w_tail', 'is_o'] + (['pos2', 'pos3', 'pos4'] if P else []) + ['log_scored_len']
    vc = lambda r, P=P: [r['label'] == 'w' and r.get('w_loc') == 'head', r['label'] == 'w' and r.get('w_loc') != 'head',
                         r['label'] == 'o'] + (posd(r) if P else []) + [r['log_slen']]
    nm_d = ['w_cov_lt35', 'w_cov_ge35', 'is_o'] + (['pos2', 'pos3', 'pos4'] if P else []) + ['log_scored_len']
    vd = lambda r, P=P: [r['label'] == 'w' and r['wcov'] < .35, r['label'] == 'w' and r['wcov'] >= .35,
                         r['label'] == 'o'] + (posd(r) if P else []) + [r['log_slen']]
    o2[SHORT[sid]] = {'label(+position)': within_reg(sid, nm_a, va),
                      'label(+position)+scored_length': within_reg(sid, nm_b, vb),
                      'head/tail(+position)+scored_length': within_reg(sid, nm_c, vc, sel=has_sp),
                      'wrong_coverage_of_scored_text(+position)+scored_length': within_reg(sid, nm_d, vd, sel=has_sp)}
out['2_regression_no_mediators'] = o2

# ---------------------------------------------------------------- 3. dose-response: share of scored text that is wrong
bins = [(0, .15), (.15, .35), (.35, .6), (.6, 1.01)]
o3 = {}
for sid in SIDS + ['pooled']:
    sids = SIDS if sid == 'pooled' else [sid]
    nm = 'pooled_3_settings' if sid == 'pooled' else SHORT[sid]
    o3[nm] = {}
    for lo, hi in bins:
        sel = lambda r, lo=lo, hi=hi: 'wcov' in r and lo <= r['wcov'] < hi
        o3[nm][f'wrong covers [{lo},{min(hi, 1)}) of scored text'] = pooled_pair_rate(SC, sel_w=sel, sids=sids)
        o3[nm][f'wrong covers [{lo},{min(hi, 1)}) | len-matched'] = pooled_pair_rate(SC, sel_w=sel, sids=sids,
                                                                                     pair_ok=len_ok)
    o3[nm]['head-located errors'] = pooled_pair_rate(SC, sel_w=lambda r: r.get('w_loc') == 'head', sids=sids)
    o3[nm]['head-located errors | len-matched'] = pooled_pair_rate(SC, sel_w=lambda r: r.get('w_loc') == 'head',
                                                                   sids=sids, pair_ok=len_ok)
    o3[nm]['tail-located errors'] = pooled_pair_rate(SC, sel_w=lambda r: r.get('w_loc') == 'tail', sids=sids)
    o3[nm]['tail-located errors | len-matched'] = pooled_pair_rate(SC, sel_w=lambda r: r.get('w_loc') == 'tail',
                                                                   sids=sids, pair_ok=len_ok)
    for kd in ['novel_number', 'novel_capitalised_name', 'first_person', 'short_other(<=4 words)', 'long_other']:
        o3[nm][f'kind {kd}'] = pooled_pair_rate(SC, sel_w=lambda r, kd=kd: r.get('wkind') == kd, sids=sids)
        o3[nm][f'kind {kd} | len-matched'] = pooled_pair_rate(SC, sel_w=lambda r, kd=kd: r.get('wkind') == kd,
                                                              sids=sids, pair_ok=len_ok)
    # off-topic vs clean
    acc = []
    for (k, s2), bs in by_ro.items():
        if s2 not in sids:
            continue
        for w in [b for b in bs if b['label'] == 'o']:
            for c in [b for b in bs if b['label'] == 'c']:
                acc.append((w['ix'], win(c[SC[s2]], w[SC[s2]]), 1.0))
    o3[nm]['OFF-TOPIC vs clean'] = ratio_ci(*per_item(acc))
# share of wrong bullets per coverage bin
for sid in SIDS:
    W = [r for r in LAB if r['sid'] == sid and 'wcov' in r]
    o3[SHORT[sid]]['n_wrong_by_cov_bin'] = [sum(lo <= r['wcov'] < hi for r in W) for lo, hi in bins]
out['3_dose_response'] = o3

# ---------------------------------------------------------------- 4. same cell (same target), different samples
# solo FVE of a bullet is computed against the cell's target activation, so bullets from different readouts of the
# same cell are directly comparable. Pairs: clean vs wrong from different sample_index and different text.
o4 = {}
ident = []
for k in cells:
    seen = {}
    for sid in SIDS:
        for b in by_ro.get((k, sid), []):
            key = b['text']
            if key in seen:
                ident.append(abs(seen[key] - b['solo']))
            else:
                seen[key] = b['solo']
o4['identical_text_solo_abs_diff_max'] = float(max(ident)) if ident else None
o4['identical_text_n'] = len(ident)


def cross_pairs(sid_pairs, same_sample):
    acc = []
    for k in cells:
        for sa, sb in sid_pairs:
            A, B = by_ro.get((k, sa), []), by_ro.get((k, sb), [])
            for a in A:
                for b in B:
                    if a is b or a['text'] == b['text']:
                        continue
                    if (a['sample'] == b['sample']) != same_sample:
                        continue
                    if {a['label'], b['label']} != {'w', 'c'}:
                        continue
                    w, c = (a, b) if a['label'] == 'w' else (b, a)
                    acc.append((w['ix'], win(c['solo'], w['solo']), 1.0))
    return ratio_ci(*per_item(acc))


o4['Original_vs_Best_bullets_diff_sample_raw_solo'] = cross_pairs([('capped_n1-n1', 'best_n_exact-n32')], False)
o4['all_3_settings_cross_readout_diff_sample_raw_solo'] = cross_pairs(
    [('capped_n1-n1', 'best_n_exact-n32'), ('capped_n1-n1', 'pooled_greedy_swap-n32'),
     ('best_n_exact-n32', 'pooled_greedy_swap-n32')], False)
o4['within_readout_raw_solo_Original'] = pooled_pair_rate({'capped_n1-n1': 'solo'}, sids=['capped_n1-n1'])
o4['within_readout_raw_solo_Best'] = pooled_pair_rate({'best_n_exact-n32': 'solo'}, sids=['best_n_exact-n32'])
o4['cross_readout_diff_sample_len_matched'] = None
acc = []
for k in cells:
    for sa, sb in [('capped_n1-n1', 'best_n_exact-n32'), ('capped_n1-n1', 'pooled_greedy_swap-n32'),
                   ('best_n_exact-n32', 'pooled_greedy_swap-n32')]:
        for a in by_ro.get((k, sa), []):
            for b in by_ro.get((k, sb), []):
                if a['text'] == b['text'] or a['sample'] == b['sample'] or {a['label'], b['label']} != {'w', 'c'}:
                    continue
                if not len_ok(a, b):
                    continue
                w, c = (a, b) if a['label'] == 'w' else (b, a)
                acc.append((w['ix'], win(c['solo'], w['solo']), 1.0))
o4['cross_readout_diff_sample_len_matched'] = ratio_ci(*per_item(acc))
# readout level, same cell: Original vs Best of 32 (different sample): hallucinated rate, and does higher joint FVE
# go with fewer hallucinations?
hr = {}
for sid in SIDS:
    hr[SHORT[sid]] = ratio_ci(*per_item((ITEM_IX[ro['item']], float(ro['label'] == 'hallucinated'), 1.)
                                        for (k, s2), ro in readouts.items() if s2 == sid))
o4['p_hallucinated_readout_by_setting'] = hr
out['4_same_cell_cross_sample'] = o4

# ---------------------------------------------------------------- 5. label-noise attenuation bound
# Mixture model: observed (pair rate - 0.5) = (1 - f - g) * true, f = share of judge-WRONG bullets that are not errors,
# g = share of judge-clean bullets that are errors. Reader rates used as rough inputs (records).
o5 = {'f_reader_no_error_in_A_B': (8 + 7 + 9 + 5) / 120, 'g_reader_error_in_C': 7 / 36,
      'note': 'C oversamples clean bullets in hallucinated readouts, so g is an upper-ish guess'}
fac = 1 - o5['f_reader_no_error_in_A_B'] - o5['g_reader_error_in_C']
o5['attenuation_factor'] = round(fac, 3)
for sid in SIDS:
    x = label_pair_rate([sid], SC[sid])
    o5[SHORT[sid]] = {'observed': x, 'implied_true_upper': round(0.5 + (x['hi'] - 0.5) / fac, 3)}
out['5_attenuation'] = o5

with open(os.path.join(HERE_RT, 'confounds.json'), 'w') as fh:
    json.dump(out, fh, indent=1, default=lambda x: x.item() if isinstance(x, np.generic) else str(x))
print(json.dumps(out, indent=1, default=lambda x: x.item() if isinstance(x, np.generic) else str(x)))
