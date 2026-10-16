"""Adversarial check of claim C6 (judge noise is large but does not hide an FVE signal). Exploratory.

Reuses the data loader of synth_tests.py (header + Part B loader, executed from its source text, so nothing is
re-implemented and nothing of synth_tests.py's outputs is overwritten). Writes reading/c6_confound_check.json.

Run: ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B c6_confound_check.py
"""
import collections
import json
import math
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'synth_tests.py')).read()
head = src[:src.index('# ============================================================================= Part A')]
partb = src[src.index('# ============================================================================= Part B'):
            src.index("OB = ['capped_n1-n1'")]
g = {'__file__': os.path.join(HERE, 'synth_tests.py'), '__name__': 'loader'}
exec(compile(head + '\n' + partb, 'synth_loader', 'exec'), g)
cells, rows, readouts, by_ro, LAB = g['cells'], g['rows'], g['readouts'], g['by_ro'], g['LAB']
ITEM_IX, SIDS, RAW, SHORT = g['ITEM_IX'], g['SIDS'], g['RAW'], g['SHORT']
ratio_ci, per_item, win, u16, sl = g['ratio_ci'], g['per_item'], g['win'], g['u16'], g['sl']
OB = ['capped_n1-n1', 'best_n_exact-n32']
out = {}


def nows(t):
    return re.sub(r'\s+', '', t or '')


def strip_ws_map(t):
    m, k16, kk = {}, 0, 0
    for ch in t:
        m[k16] = kk
        k16 += 2 if ord(ch) > 0xFFFF else 1
        if not ch.isspace():
            kk += 1
    m[k16] = kk
    return m


# ----------------------------------------------------------------------------- 1. test-retest, conditional view
both, o_only, r_only, ws_kinds, ws_cells = [], [], [], collections.Counter(), []
cond_o, cond_r, sym = [], [], []
for k, (iid, c) in cells.items():
    a, b = c['settings']['capped_n1-n1'], c['settings'][RAW]
    if (a['text'] or '') == (b['text'] or '') or nows(a['text']) != nows(b['text']):
        continue
    ws_cells.append(k)
    # what kind of whitespace difference
    ta, tb = a['text'], b['text']
    kind = []
    if ta.strip() == tb.strip():
        kind.append('leading/trailing only')
    if ta.count('\n') != tb.count('\n'):
        kind.append('newline count differs')
    if re.sub(r'[ \t]+', ' ', ta) == re.sub(r'[ \t]+', ' ', tb):
        kind.append('runs of spaces only')
    ws_kinds[' + '.join(kind) or 'other'] += 1
    ma, mb = strip_ws_map(ta), strip_ws_map(tb)
    rw = [(mb[x], mb[y]) for sp in b['spans'] if sp['verified'] and sp['type'] == 'wrong'
          for x, y in sp['offsets'] if x in mb and y in mb]
    ix = ITEM_IX[iid]
    for bb in a['bullets']:
        if bb['label'] not in ('w', 'c', 'o'):
            continue
        s0, e0 = ma.get(bb['start']), ma.get(bb['end'])
        if s0 is None or e0 is None:
            continue
        rwr = any(x < e0 and y > s0 for x, y in rw)
        ow = bb['label'] == 'w'
        if ow:
            cond_o.append((ix, float(rwr), 1.))
        if rwr:
            cond_r.append((ix, float(ow), 1.))
        if ow or rwr:
            # per-verdict retention: each WRONG verdict counts once; it 'holds' if the other run also says WRONG
            sym.append((ix, float(ow and rwr) * (2 if (ow and rwr) else 0), float(ow) + float(rwr)))
num = np.zeros(len(ITEM_IX)); den = np.zeros(len(ITEM_IX))
for ix, n_, d_ in sym:
    num[ix] += n_; den[ix] += d_
out['1_test_retest'] = {
    'n_cells': len(ws_cells), 'whitespace_difference_kinds': dict(ws_kinds),
    'P_raw_wrong_given_original_wrong': ratio_ci(*per_item(cond_o)),
    'P_original_wrong_given_raw_wrong': ratio_ci(*per_item(cond_r)),
    'per_WRONG_verdict_retention_(2*both/(2*both+one_only))': ratio_ci(num, den),
    'note': 'synth_tests reports both/(both+either-only) = 0.656, a Jaccard-type rate, not the chance that a '
            'given WRONG verdict is repeated'}
# representativeness of the 119 cells
allo = [readouts[(k, 'capped_n1-n1')] for k in cells]
wso = [readouts[(k, 'capped_n1-n1')] for k in ws_cells]
out['1_test_retest']['representativeness'] = {
    'layer_ws': dict(collections.Counter(r['L'] for r in wso)), 'layer_all': dict(collections.Counter(r['L'] for r in allo)),
    'source_ws': dict(collections.Counter(r['source'] for r in wso)),
    'source_all': dict(collections.Counter(r['source'] for r in allo)),
    'p_halluc_ws': round(np.mean([r['label'] == 'hallucinated' for r in wso]), 3),
    'p_halluc_all': round(np.mean([r['label'] == 'hallucinated' for r in allo]), 3),
    'mean_fve_ws': round(float(np.mean([r['fve'] for r in wso])), 4),
    'mean_fve_all': round(float(np.mean([r['fve'] for r in allo if r['fve'] is not None])), 4),
    'n_items_ws': len({readouts[(k, 'capped_n1-n1')]['item'] for k in ws_cells})}

# ----------------------------------------------------------------------------- 2. identical-text twins
# rebuild twin pairs exactly as synth_tests.py (b), keep positions and settings
def norm_b(t):
    return re.sub(r'\s+', ' ', t).strip()


twins = []
for k, (iid, c) in cells.items():
    seen = collections.defaultdict(list)
    for sid in SIDS:
        s = c['settings'][sid]
        tb = u16(s['text'] or '')
        for j, b in enumerate(s['bullets']):
            if b['label'] not in ('w', 'c', 'o'):
                continue
            seen[norm_b(sl(tb, b['start'], b['end']))].append((sid, j, b['label'], len(s['bullets'])))
    for t, lst in seen.items():
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                p, q = lst[x], lst[y]
                if p[0] == q[0]:
                    continue
                if (c['settings'][p[0]]['text'] or '') == (c['settings'][q[0]]['text'] or ''):
                    continue
                twins.append({'k': k, 'ix': ITEM_IX[iid], 'a': p, 'b': q, 'len': len(t)})
lp = collections.Counter(tuple(sorted((t['a'][2], t['b'][2]))) for t in twins)
ww, cw, ow_ = lp[('w', 'w')], lp[('c', 'w')], lp[('o', 'w')]
# per wrong copy: P(twin also WRONG | this copy WRONG)
acc = []
for t in twins:
    for me, other in ((t['a'], t['b']), (t['b'], t['a'])):
        if me[2] == 'w':
            acc.append((t['ix'], float(other[2] == 'w'), 1.))
acc_nc = []   # P(twin is CLEAN | this copy WRONG)
for t in twins:
    for me, other in ((t['a'], t['b']), (t['b'], t['a'])):
        if me[2] == 'w':
            acc_nc.append((t['ix'], float(other[2] == 'c'), 1.))
out['2_twins'] = {'n_pairs': len(twins), 'label_pairs': {f'{a}/{b}': n for (a, b), n in lp.items()},
                  'P_twin_WRONG_given_copy_WRONG_(per copy)': ratio_ci(*per_item(acc)),
                  'P_twin_CLEAN_given_copy_WRONG_(per copy)': ratio_ci(*per_item(acc_nc)),
                  'synth_tests_rate_(pairs with any w that differ)': round((cw + ow_) / (ww + cw + ow_), 4)}
# by setting pair
bysp = collections.defaultdict(list)
for t in twins:
    sp = ' vs '.join(sorted((SHORT[t['a'][0]], SHORT[t['b'][0]])))
    for me, other in ((t['a'], t['b']), (t['b'], t['a'])):
        if me[2] == 'w':
            bysp[sp].append((t['ix'], float(other[2] == 'w'), 1.))
out['2_twins']['P_twin_WRONG_given_copy_WRONG_by_setting_pair'] = {sp: ratio_ci(*per_item(v)) for sp, v in bysp.items()}
# direction of c/w disagreements: which setting / which position holds the WRONG copy
dirn = collections.Counter()
pos_acc, earlier = [], []
for t in twins:
    labs = {t['a'][2], t['b'][2]}
    if labs != {'c', 'w'}:
        continue
    wcopy, ccopy = (t['a'], t['b']) if t['a'][2] == 'w' else (t['b'], t['a'])
    dirn[(SHORT[wcopy[0]] + ' WRONG', SHORT[ccopy[0]] + ' clean')] += 1
    if wcopy[1] != ccopy[1]:
        earlier.append((t['ix'], float(wcopy[1] < ccopy[1]), 1.))
out['2_twins']['cw_direction_counts'] = {f'{a} / {b}': n for (a, b), n in sorted(dirn.items(), key=lambda x: -x[1])}
out['2_twins']['P_WRONG_copy_is_earlier_in_list_(cw pairs at different positions)'] = ratio_ci(*per_item(earlier))
# base rate for comparison: among all c/w pairs (same cell, different setting, identical text), how often would a
# randomly ordered pair have the WRONG copy in Combine
# also: does verdict instability depend on bullet length (more claims to nitpick)?
lenacc = collections.defaultdict(list)
for t in twins:
    if 'w' not in (t['a'][2], t['b'][2]):
        continue
    bucket = 'len<80' if t['len'] < 80 else ('80-160' if t['len'] < 160 else '>=160')
    lenacc[bucket].append((t['ix'], float(t['a'][2] != t['b'][2]), 1.))
out['2_twins']['P_labels_differ_given_any_w_by_bullet_chars'] = {b: ratio_ci(*per_item(v)) for b, v in lenacc.items()}

# ----------------------------------------------------------------------------- 3. FVE signal, length-controlled
# Within-readout pair rate P(score clean > score wrong) restricted to pairs of similar length (scored chars within
# a factor 1.25), for several label-cleanliness levels.
def is_vt(r):
    return r['n_claims'] > 0 and r['n_true'] == r['n_claims']


def is_specific_w(r):
    return r['label'] == 'w' and (r.get('w_novel_num') or r.get('w_novel_name'))


def pair_rate(sid, score, sel_w, sel_c, len_tol=None, label_w='w'):
    acc = []
    for (k, s2), bs in by_ro.items():
        if s2 != sid:
            continue
        ws = [b for b in bs if b['label'] == label_w and sel_w(b)]
        cs = [b for b in bs if b['label'] == 'c' and sel_c(b)]
        for w in ws:
            for cc in cs:
                if len_tol is not None:
                    if abs(math.log(max(1, w['scored_len']) / max(1, cc['scored_len']))) > math.log(len_tol):
                        continue
                acc.append((w['ix'], win(cc[score], w[score]), 1.))
    return ratio_ci(*per_item(acc))


T = lambda r: True
res3 = {}
for sid in SIDS:
    sc = 'solo_pa' if sid in OB else 'solo'
    d = {}
    for name, sw, scl in [('all wrong vs all clean', T, T),
                          ('all wrong vs verified-true clean', T, is_vt),
                          ('invented-specific wrong (novel number/name) vs verified-true clean', is_specific_w, is_vt)]:
        d[name] = {'unmatched': pair_rate(sid, sc, sw, scl), 'length_matched_1.25x': pair_rate(sid, sc, sw, scl, 1.25)}
    res3[SHORT[sid]] = d
out['3_length_matched_pair_rates'] = res3
# length difference between the label groups (same readout)
lenpr = {}
for sid in SIDS:
    acc = []
    for (k, s2), bs in by_ro.items():
        if s2 != sid:
            continue
        ws = [b for b in bs if b['label'] == 'w']
        cs = [b for b in bs if b['label'] == 'c' and is_vt(b)]
        acc += [(w['ix'], win(w['scored_len'], cc['scored_len']), 1.) for w in ws for cc in cs]
    lenpr[SHORT[sid]] = ratio_ci(*per_item(acc))
out['3_P_wrong_longer_than_verified_true_clean'] = lenpr


# within-readout regression: solo ~ readout FE + label dummies + log scored length + position dummies (O/B)
def within_fit(sid, lab_fn):
    rs = [r for r in LAB if r['sid'] == sid]
    grp = collections.defaultdict(list)
    for r in rs:
        y = lab_fn(r)
        if y is None:
            continue
        grp[(r['k'])].append((r, y))
    X, Y, IX = [], [], []
    for k, lst in grp.items():
        if len(lst) < 2:
            continue
        xs = []
        for r, y in lst:
            row = [float(y == 'w'), math.log(max(1, r['scored_len']))]
            if sid in OB:
                row += [float(r['j'] == p) for p in (1, 2, 3)]
            xs.append(row)
        xs = np.array(xs); ys = np.array([r['solo'] for r, _ in lst])
        X.append(xs - xs.mean(0)); Y.append(ys - ys.mean()); IX += [r['ix'] for r, _ in lst]
    X, Y, IX = np.vstack(X), np.concatenate(Y), np.array(IX)
    beta = np.linalg.lstsq(X, Y, rcond=None)[0]
    bs = []
    rng = np.random.default_rng(1)
    for _ in range(300):
        pick = rng.integers(0, len(ITEM_IX), len(ITEM_IX))
        w = np.bincount(pick, minlength=len(ITEM_IX))[IX].astype(float)
        sw = np.sqrt(w)
        bb = np.linalg.lstsq(X * sw[:, None], Y * sw, rcond=None)[0]
        bs.append(bb[0])
    sdy = float(np.std(Y))
    return {'coef_is_w': round(float(beta[0]), 4), 'lo': round(float(np.percentile(bs, 2.5)), 4),
            'hi': round(float(np.percentile(bs, 97.5)), 4), 'within_sd_y': round(sdy, 4),
            'coef_in_within_sd': round(float(beta[0]) / sdy, 3), 'n': int(len(Y))}


reg = {}
for sid in SIDS:
    reg[SHORT[sid]] = {
        'all wrong vs all clean': within_fit(sid, lambda r: r['label'] if r['label'] in ('w', 'c') else None),
        'all wrong vs verified-true clean': within_fit(
            sid, lambda r: 'w' if r['label'] == 'w' else ('c' if r['label'] == 'c' and is_vt(r) else None)),
        'invented-specific wrong vs verified-true clean': within_fit(
            sid, lambda r: 'w' if is_specific_w(r) else ('c' if r['label'] == 'c' and is_vt(r) else None)),
    }
out['3_within_readout_regression_solo'] = reg

# ----------------------------------------------------------------------------- 4. reading-sample reweighting
# judge-too-strict vs judge-missed-error, reweighted from the stratified sample to the bullet population
out['4_note'] = 'computed by hand in the report from tables.json counts and sample.json thresholds'

with open(os.path.join(HERE, 'c6_confound_check.json'), 'w') as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x))
print(json.dumps(out, indent=1, ensure_ascii=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x)))
