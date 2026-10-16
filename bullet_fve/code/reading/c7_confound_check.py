"""Confound checks for claim C7 (settings swap samples, not error kind). Exploratory, read-only on inputs.

Run: ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B c7_confound_check.py
Writes c7_confound_check.json next to this file. Chat-level (149 items) percentile bootstrap, 1000 reps, seed 0.
"""
import collections
import glob
import json
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = '${OLENS_SCRATCH}/olens-bullet-fve/page/data'
INP = '${OLENS_SCRATCH}/olens-bullet-fve/inputs/hall_three_settings.jsonl'
O, B, C = 'capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32'
SIDS = [O, B, C]
SHORT = {O: 'Original', B: 'Best of 32', C: 'Combine 32'}

items, cells = {}, {}
for f in sorted(glob.glob(os.path.join(DATA, 'items', '*.json'))):
    d = json.load(open(f))
    it = d['item']
    items[it['id']] = it
    for k, c in d['cells'].items():
        cells[k] = (it['id'], c)
IDS = sorted(items)
IX = {x: i for i, x in enumerate(IDS)}
rng = np.random.default_rng(0)
BOOTW = np.stack([np.bincount(b, minlength=len(IDS)) for b in rng.integers(0, len(IDS), (1000, len(IDS)))]).astype(float)


def per_item(pairs):
    num, den = np.zeros(len(IDS)), np.zeros(len(IDS))
    for ix, a, b in pairs:
        num[ix] += a
        den[ix] += b
    return num, den


def rci(pairs):
    num, den = per_item(pairs)
    if not den.sum():
        return {'est': None, 'n': 0}
    est = num.sum() / den.sum()
    with np.errstate(invalid='ignore', divide='ignore'):
        b = (BOOTW @ num) / (BOOTW @ den)
    b = b[np.isfinite(b)]
    return {'est': round(float(est), 4), 'lo': round(float(np.percentile(b, 2.5)), 4),
            'hi': round(float(np.percentile(b, 97.5)), 4), 'n': int(den.sum())}


def dci(p1, p2):
    n1, d1 = per_item(p1)
    n2, d2 = per_item(p2)
    est = n1.sum() / d1.sum() - n2.sum() / d2.sum()
    with np.errstate(invalid='ignore', divide='ignore'):
        b = (BOOTW @ n1) / (BOOTW @ d1) - (BOOTW @ n2) / (BOOTW @ d2)
    b = b[np.isfinite(b)]
    return {'est': round(float(est), 4), 'lo': round(float(np.percentile(b, 2.5)), 4),
            'hi': round(float(np.percentile(b, 97.5)), 4)}


def u16(s):
    return s.encode('utf-16-le')


def sl(b, a, e):
    return b[2 * max(0, a):2 * max(0, e)].decode('utf-16-le', errors='replace')


# phrase ids / traces
src = {}
with open(INP) as fh:
    for line in fh:
        r = json.loads(line)
        k = f"{r['item_id']}.L{r['layer']}.p{r['position']}"
        src[k] = r
assert set(src) == set(cells), (len(src), len(cells))

out = {}
H = lambda s: s['label'] == 'hallucinated'
K = lambda s: s['label'] == 'consistent'

# ---------------------------------------------------------------- 1. marginal label rates, paired differences
m = {}
for sid in SIDS:
    m[SHORT[sid]] = {'p_hallucinated': rci((IX[i], float(H(c['settings'][sid])), 1.) for k, (i, c) in cells.items()),
                     'p_consistent': rci((IX[i], float(K(c['settings'][sid])), 1.) for k, (i, c) in cells.items()),
                     'mean_joint_fve': round(float(np.mean([c['settings'][sid]['fve'] for i, c in cells.values()])), 4)}
for sid in (B, C):
    m[f'{SHORT[sid]} - Original'] = {
        'p_hallucinated': dci([(IX[i], float(H(c['settings'][sid])), 1.) for k, (i, c) in cells.items()],
                              [(IX[i], float(H(c['settings'][O])), 1.) for k, (i, c) in cells.items()]),
        'p_consistent': dci([(IX[i], float(K(c['settings'][sid])), 1.) for k, (i, c) in cells.items()],
                            [(IX[i], float(K(c['settings'][O])), 1.) for k, (i, c) in cells.items()]),
        # net = (fixes - breaks) / all cells, consistent<->hallucinated only
        'net_fix_minus_break_per_cell': rci((IX[i], float(H(c['settings'][O]) and K(c['settings'][sid]))
                                             - float(K(c['settings'][O]) and H(c['settings'][sid])), 1.)
                                            for k, (i, c) in cells.items())}
    for L in (20, 36, 44, 52, 60):
        m[f'{SHORT[sid]} - Original'][f'p_hallucinated_L{L}'] = dci(
            [(IX[i], float(H(c['settings'][sid])), 1.) for k, (i, c) in cells.items() if c['layer'] == L],
            [(IX[i], float(H(c['settings'][O])), 1.) for k, (i, c) in cells.items() if c['layer'] == L])
    for so in ('dailydialog', 'lmsys'):
        m[f'{SHORT[sid]} - Original'][f'p_hallucinated_{so}'] = dci(
            [(IX[i], float(H(c['settings'][sid])), 1.) for k, (i, c) in cells.items() if items[i]['source'] == so],
            [(IX[i], float(H(c['settings'][O])), 1.) for k, (i, c) in cells.items() if items[i]['source'] == so])
out['1_marginal_labels'] = m

# ---------------------------------------------------------------- 2. per-bullet wrong rate per setting
bw = {}
for sid in SIDS:
    bw[SHORT[sid]] = rci((IX[i], float(b['label'] == 'w'), 1.) for k, (i, c) in cells.items()
                         for b in c['settings'][sid]['bullets'] if b['label'] in ('w', 'c', 'o'))
    bw[SHORT[sid] + ' mean wrong bullets per readout'] = rci(
        (IX[i], sum(b['label'] == 'w' for b in c['settings'][sid]['bullets']), 1.) for k, (i, c) in cells.items())
for sid in (B, C):
    bw[f'{SHORT[sid]} - Original wrong bullets per readout'] = dci(
        [(IX[i], sum(b['label'] == 'w' for b in c['settings'][sid]['bullets']), 1.) for k, (i, c) in cells.items()],
        [(IX[i], sum(b['label'] == 'w' for b in c['settings'][O]['bullets']), 1.) for k, (i, c) in cells.items()])
out['2_bullet_wrong'] = bw

# ---------------------------------------------------------------- 3. Best-of-32 FVE gain: within-layer, net change
g = []
for k, (i, c) in cells.items():
    o, b = c['settings'][O], c['settings'][B]
    if (o['text'] or '') == (b['text'] or ''):
        continue
    tr = src[k]['settings'][B]['trace']
    sc = [t.get('score') for t in tr]
    if sc[0] is None:
        rank0 = 1.0
    else:
        v = [x for x in sc if x is not None]
        rank0 = float(sum(x > sc[0] for x in v)) / max(1, len(v) - 1)  # share of scored samples beating sample 0
    g.append({'ix': IX[i], 'L': c['layer'], 'gain': b['fve'] - o['fve'], 'ofve': o['fve'], 'rank0': rank0,
              'dH': float(H(b)) - float(H(o)), 'oh': H(o), 'ok': K(o), 'bh': H(b), 'bk': K(b),
              'dW': sum(x['label'] == 'w' for x in b['bullets']) - sum(x['label'] == 'w' for x in o['bullets'])})
res3 = {'n': len(g)}
# within-layer tertiles of gain
for x in g:
    pass
byL = collections.defaultdict(list)
for x in g:
    byL[x['L']].append(x)
for L, xs in byL.items():
    q = np.quantile([x['gain'] for x in xs], [1 / 3, 2 / 3])
    for x in xs:
        x['tL'] = 0 if x['gain'] < q[0] else (1 if x['gain'] < q[1] else 2)
# relative gain (gain / orig fve) tertiles overall
q = np.quantile([x['gain'] / max(x['ofve'], 1e-6) for x in g], [1 / 3, 2 / 3])
for x in g:
    rg = x['gain'] / max(x['ofve'], 1e-6)
    x['tR'] = 0 if rg < q[0] else (1 if rg < q[1] else 2)
for key, nm in (('tL', 'within_layer_gain_tertile'), ('tR', 'relative_gain_tertile')):
    res3[nm] = {}
    for t in range(3):
        xs = [x for x in g if x[key] == t]
        res3[nm][f't{t + 1}'] = {
            'p_fix': rci((x['ix'], float(x['bk']), 1.) for x in xs if x['oh']),
            'p_break': rci((x['ix'], float(x['bh']), 1.) for x in xs if x['ok']),
            'mean_delta_hallucinated': rci((x['ix'], x['dH'], 1.) for x in xs),
            'mean_delta_wrong_bullets': rci((x['ix'], x['dW'], 1.) for x in xs)}
    res3[nm]['t3 - t1 mean_delta_hallucinated'] = dci([(x['ix'], x['dH'], 1.) for x in g if x[key] == 2],
                                                      [(x['ix'], x['dH'], 1.) for x in g if x[key] == 0])
    res3[nm]['t3 - t1 mean_delta_wrong_bullets'] = dci([(x['ix'], x['dW'], 1.) for x in g if x[key] == 2],
                                                       [(x['ix'], x['dW'], 1.) for x in g if x[key] == 0])
# rank of sample 0: Original was near the top of the 32 (rank0 small) vs near the bottom
res3['by_rank_of_original_among_32'] = {}
for nm, lo, hi in (('orig in top third', -1, 1 / 3), ('orig in middle third', 1 / 3, 2 / 3), ('orig in bottom third', 2 / 3, 2)):
    xs = [x for x in g if lo <= x['rank0'] < hi]
    res3['by_rank_of_original_among_32'][nm] = {
        'n': len(xs), 'p_fix': rci((x['ix'], float(x['bk']), 1.) for x in xs if x['oh']),
        'p_break': rci((x['ix'], float(x['bh']), 1.) for x in xs if x['ok']),
        'mean_delta_hallucinated': rci((x['ix'], x['dH'], 1.) for x in xs)}
# linear slope of dH on gain with layer fixed effects (cluster bootstrap)
def slope(xs, wts=None):
    X = np.array([[x['gain']] + [float(x['L'] == L) for L in (20, 36, 44, 52, 60)] + [x['ofve']] for x in xs])
    y = np.array([x['dH'] for x in xs])
    w = np.ones(len(xs)) if wts is None else wts
    W = np.sqrt(w)[:, None]
    beta = np.linalg.lstsq(X * W, y * W[:, 0], rcond=None)[0]
    return beta[0]
ixs = np.array([x['ix'] for x in g])
est = slope(g)
bs = []
for bw_ in BOOTW[:300]:
    bs.append(slope(g, bw_[ixs]))
res3['slope_dHalluc_per_unit_gain_layerFE_origFVE'] = {'est': round(float(est), 4),
                                                       'lo': round(float(np.percentile(bs, 2.5)), 4),
                                                       'hi': round(float(np.percentile(bs, 97.5)), 4),
                                                       'note': 'per +1.0 FVE gain; 300 reps'}
out['3_best_gain'] = res3

# ---------------------------------------------------------------- 4. Combine: pick order vs source position vs add-time gain
rows = []
for k, (i, c) in cells.items():
    s = c['settings'][C]
    S = src[k]['settings'][C]
    pids = S['phrase_ids']
    if len(pids) != len(s['bullets']):
        continue
    adds = [t for t in S['trace'] if t['action'] == 'add']
    gain_of = {t['phrase_id']: t['gain'] for t in adds}
    add_order = {t['phrase_id']: n for n, t in enumerate(adds)}
    swapped_in = set()
    for t in S['trace']:
        if t['action'] == 'swap':
            swapped_in |= set(t['to']) - set(t['from'])
    for j, (pid, b) in enumerate(zip(pids, s['bullets'])):
        if b['label'] not in ('w', 'c', 'o') or b['dup']:
            continue
        smp, pos = pid.rsplit(':', 2)[-2:]
        assert int(smp) == b['sample_index']
        rows.append({'ix': IX[i], 'k': k, 'L': c['layer'], 'j': j, 'n': len(pids), 'srcpos': int(pos),
                     'w': float(b['label'] == 'w'), 'gain': gain_of.get(pid), 'swapped': pid in swapped_in,
                     'add_n': add_order.get(pid), 'drop': b['drop'], 'solo': b['solo'], 'label': b['label']})
r4 = {'n_bullets': len(rows)}
r4['wrong_by_source_position_in_its_sample'] = {f'srcpos {p + 1}': rci((x['ix'], x['w'], 1.) for x in rows if min(x['srcpos'], 4) == p)
                                                for p in range(5)}
r4['mean_source_position_by_pick'] = {f'pick {j + 1}': round(float(np.mean([x['srcpos'] for x in rows if x['j'] == j])), 3)
                                      for j in range(4)}
r4['wrong_by_pick_within_source_position'] = {
    f'srcpos {p + 1}': {f'pick {j + 1}': rci((x['ix'], x['w'], 1.) for x in rows if x['j'] == j and min(x['srcpos'], 3) == p)
                        for j in range(4)} for p in range(4)}
r4['swapped_in_vs_added'] = {'swapped_in': rci((x['ix'], x['w'], 1.) for x in rows if x['swapped']),
                             'added': rci((x['ix'], x['w'], 1.) for x in rows if not x['swapped'])}
gq = np.quantile([x['gain'] for x in rows if x['gain'] is not None and not x['swapped']], [.25, .5, .75])
GQ = lambda v: 0 if v < gq[0] else (1 if v < gq[1] else (2 if v < gq[2] else 3))
r4['wrong_by_add_gain_quartile'] = {f'Q{t + 1}': rci((x['ix'], x['w'], 1.) for x in rows if x['gain'] is not None
                                                      and not x['swapped'] and GQ(x['gain']) == t) for t in range(4)}
r4['wrong_by_add_gain_quartile']['cutoffs'] = [round(float(v), 4) for v in gq]
r4['Q1 - Q4 add gain'] = dci([(x['ix'], x['w'], 1.) for x in rows if x['gain'] is not None and not x['swapped'] and GQ(x['gain']) == 0],
                             [(x['ix'], x['w'], 1.) for x in rows if x['gain'] is not None and not x['swapped'] and GQ(x['gain']) == 3])
# within-pick-slot: low vs high add gain (gain is strongly tied to pick order; compare at fixed slot)
r4['within_pick_low_vs_high_gain_half'] = {}
for j in range(1, 4):
    xs = [x for x in rows if x['j'] == j and x['gain'] is not None and not x['swapped']]
    med = np.median([x['gain'] for x in xs])
    r4['within_pick_low_vs_high_gain_half'][f'pick {j + 1}'] = dci(
        [(x['ix'], x['w'], 1.) for x in xs if x['gain'] < med], [(x['ix'], x['w'], 1.) for x in xs if x['gain'] >= med])
# same-readout pair rate on drop and on add gain: P(clean > wrong)
byro = collections.defaultdict(list)
for x in rows:
    byro[x['k']].append(x)
for sc in ('drop', 'gain', 'solo'):
    acc = []
    for k, xs in byro.items():
        ws = [x for x in xs if x['label'] == 'w' and x[sc] is not None]
        cs = [x for x in xs if x['label'] == 'c' and x[sc] is not None]
        acc += [(w['ix'], 1. if cc[sc] > w[sc] else (0.5 if cc[sc] == w[sc] else 0.), 1.) for w in ws for cc in cs]
    r4[f'same_readout_P(clean {sc} > wrong {sc})'] = rci(acc)
out['4_combine_order'] = r4

# Original: wrong rate by writing position (reference)
out['4b_original_wrong_by_position'] = {f'pos {j + 1}': rci((IX[i], float(b['label'] == 'w'), 1.) for k, (i, c) in cells.items()
                                                          for jj, b in enumerate(c['settings'][O]['bullets'])
                                                          if jj == j and b['label'] in ('w', 'c', 'o') and not b['dup'])
                                       for j in range(4)}

# ---------------------------------------------------------------- 5. novel specifics: length, headings, numbers vs names
CJKR = '㐀-䶿一-鿿豈-﫿'
TOK = re.compile('[' + CJKR + ']|[^\\W_' + CJKR + ']+')
NUM = re.compile(r'\d+(?:[.,]\d+)*')
CAPW = re.compile(r'(?<![\w])([A-Z][A-Za-z\-]+)')
BOLD = re.compile(r'\*\*[^*]{0,200}\*\*|^#+.*$|`[^`]*`', re.M)


def toks(s):
    return [t.lower() for t in TOK.findall(s)]


def novel_caps(span, vocab):
    out_ = []
    for mm in CAPW.finditer(span):
        pre = span[:mm.start()].rstrip()
        if not pre or pre[-1] in '.!?:"“”*#-—–(（[>|`\'‘’' or mm.group(1) in ('I', 'I’m'):
            continue
        if mm.group(1).lower() not in vocab:
            out_.append(mm.group(1))
    return out_


brows = []
for k, (i, c) in cells.items():
    it = items[i]
    vocab = set(toks(it['prompt'] + ' ' + it['response']))
    nums = set(NUM.findall(it['prompt'] + ' ' + it['response']))
    for sid in SIDS:
        s = c['settings'][sid]
        tb = u16(s['text'] or '')
        for j, b in enumerate(s['bullets']):
            if b['label'] not in ('w', 'c', 'o') or b['dup'] or b['shap_share'] is None:
                continue
            scored = sl(tb, b['start'], b['scored_end'])
            plain = BOLD.sub(' ', scored)
            nn = any(x not in nums for x in NUM.findall(scored))
            nc = bool(novel_caps(scored, vocab))
            nc_plain = bool(novel_caps(plain, vocab))
            brows.append({'ix': IX[i], 'sid': sid, 'L': c['layer'], 'j': j, 'w': float(b['label'] == 'w'),
                          'slen': b['scored_end'] - b['start'], 'nn': float(nn), 'nc': float(nc),
                          'spec': float(nn or nc), 'spec_plain': float(nn or nc_plain), 'nc_plain': float(nc_plain),
                          'has_bold': float(bool(re.search(r'\*\*', scored)))})
r5 = {}
for sid in SIDS:
    R = [x for x in brows if x['sid'] == sid]
    r5[SHORT[sid]] = {'mean_scored_len_utf16': round(float(np.mean([x['slen'] for x in R])), 1),
                      'p_has_bold': rci((x['ix'], x['has_bold'], 1.) for x in R),
                      'p_novel_spec': rci((x['ix'], x['spec'], 1.) for x in R),
                      'p_novel_number': rci((x['ix'], x['nn'], 1.) for x in R),
                      'p_novel_name': rci((x['ix'], x['nc'], 1.) for x in R),
                      'p_novel_name_outside_bold_heading_code': rci((x['ix'], x['nc_plain'], 1.) for x in R),
                      'p_wrong': rci((x['ix'], x['w'], 1.) for x in R),
                      'p_wrong_and_novel_spec': rci((x['ix'], x['w'] * x['spec'], 1.) for x in R)}
allq = np.quantile([x['slen'] for x in brows], [.2, .4, .6, .8])
for x in brows:
    x['lbin'] = int(np.searchsorted(allq, x['slen'], 'right'))
for sid in (B, C):
    R1 = [x for x in brows if x['sid'] == sid]
    R0 = [x for x in brows if x['sid'] == O]
    d = {}
    for f in ('spec', 'nn', 'nc', 'nc_plain', 'spec_plain', 'w'):
        d[f] = dci([(x['ix'], x[f], 1.) for x in R1], [(x['ix'], x[f], 1.) for x in R0])
    d['w_and_spec'] = dci([(x['ix'], x['w'] * x['spec'], 1.) for x in R1], [(x['ix'], x['w'] * x['spec'], 1.) for x in R0])
    # length-reweighted: weight setting-sid bullets so their scored-length bin distribution matches Original's
    c0 = collections.Counter(x['lbin'] for x in R0)
    c1 = collections.Counter(x['lbin'] for x in R1)
    wt = {bn: (c0[bn] / len(R0)) / (c1[bn] / len(R1)) for bn in c1}
    d['spec_length_reweighted'] = dci([(x['ix'], x['spec'] * wt[x['lbin']], wt[x['lbin']]) for x in R1],
                                      [(x['ix'], x['spec'], 1.) for x in R0])
    d['spec_plain_length_reweighted'] = dci([(x['ix'], x['spec_plain'] * wt[x['lbin']], wt[x['lbin']]) for x in R1],
                                            [(x['ix'], x['spec_plain'], 1.) for x in R0])
    d['length_bin_share_vs_Original'] = {int(bn): round(c1[bn] / len(R1) - c0[bn] / len(R0), 4) for bn in sorted(c0)}
    r5[f'{SHORT[sid]} - Original'] = d
out['5_novel_specifics'] = r5

# ---------------------------------------------------------------- 6. noise floor from whitespace-only re-judgement
out['6_note'] = ('see synth_tests.json T6 raw_vs_original_whitespace_only (119 cells) and '
                 'identical_bullet_text_across_settings')

with open(os.path.join(HERE, 'c7_confound_check.json'), 'w') as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))


# ---------------------------------------------------------------- 7. follow-ups
r7 = {}
OT = lambda s: s['label'] in ('off_topic',)
OTH = lambda s: s['label'] not in ('consistent', 'hallucinated')
for sid in (B, C):
    r7[f'{SHORT[sid]} - Original p_other_label'] = dci(
        [(IX[i], float(OTH(c['settings'][sid])), 1.) for k, (i, c) in cells.items()],
        [(IX[i], float(OTH(c['settings'][O])), 1.) for k, (i, c) in cells.items()])
    r7[f'{SHORT[sid]} - Original p_offtopic_bullet'] = dci(
        [(IX[i], float(b['label'] == 'o'), 1.) for k, (i, c) in cells.items() for b in c['settings'][sid]['bullets']
         if b['label'] in ('w', 'c', 'o')],
        [(IX[i], float(b['label'] == 'o'), 1.) for k, (i, c) in cells.items() for b in c['settings'][O]['bullets']
         if b['label'] in ('w', 'c', 'o')])
# was Original capped (raw text differs) -> does Best's improvement live there?
capped = {k: (c['settings'][O]['text'] or '') != (c['settings']['raw_n1-n1']['text'] or '') for k, (i, c) in cells.items()}
for nm, flag in (('original_capped', True), ('original_uncapped', False)):
    ks = [k for k in cells if capped[k] == flag]
    r7[f'Best - Original p_hallucinated | {nm}'] = dci(
        [(IX[cells[k][0]], float(H(cells[k][1]['settings'][B])), 1.) for k in ks],
        [(IX[cells[k][0]], float(H(cells[k][1]['settings'][O])), 1.) for k in ks])
    r7[f'n | {nm}'] = len(ks)
# Combine: reweight to Original's position mix (source position within sample)
pos_rows = collections.defaultdict(list)
for k, (i, c) in cells.items():
    S = src[k]['settings'][C]
    s = c['settings'][C]
    if len(S['phrase_ids']) != len(s['bullets']):
        continue
    for pid, b in zip(S['phrase_ids'], s['bullets']):
        if b['label'] in ('w', 'c', 'o') and not b['dup']:
            pos_rows['C'].append((IX[i], int(pid.rsplit(':', 1)[1]), float(b['label'] == 'w')))
    for j, b in enumerate(c['settings'][O]['bullets']):
        if b['label'] in ('w', 'c', 'o') and not b['dup']:
            pos_rows['O'].append((IX[i], j, float(b['label'] == 'w')))
cO = collections.Counter(p for _, p, _ in pos_rows['O'])
cC = collections.Counter(p for _, p, _ in pos_rows['C'])
wt = {p: (cO[p] / len(pos_rows['O'])) / (cC[p] / len(pos_rows['C'])) for p in cC}
r7['combine_source_position_share'] = {p: round(cC[p] / len(pos_rows['C']), 3) for p in sorted(cC)}
r7['Combine - Original p_wrong, Combine reweighted to Original position mix'] = dci(
    [(ix, w * wt[p], wt[p]) for ix, p, w in pos_rows['C']], [(ix, w, 1.) for ix, p, w in pos_rows['O']])
# novel specifics by source position, and position-reweighted difference
spec_by = {}
bi = 0
pos_of = {}
for k, (i, c) in cells.items():
    S = src[k]['settings'][C]
    s = c['settings'][C]
    if len(S['phrase_ids']) != len(s['bullets']):
        continue
    for j, pid in enumerate(S['phrase_ids']):
        pos_of[(k, j)] = int(pid.rsplit(':', 1)[1])
krows = []
for k, (i, c) in cells.items():
    for sid in (O, C):
        s = c['settings'][sid]
        for j, b in enumerate(s['bullets']):
            if b['label'] not in ('w', 'c', 'o') or b['dup'] or b['shap_share'] is None:
                continue
            p = j if sid == O else pos_of.get((k, j))
            if p is None:
                continue
            krows.append((sid, IX[i], k, j, p))
# reuse brows (same filter order) -> map by (sid, ix, j) is ambiguous across cells; recompute spec quickly
spec_map = {}
for k, (i, c) in cells.items():
    it = items[i]
    vocab = set(toks(it['prompt'] + ' ' + it['response']))
    nums = set(NUM.findall(it['prompt'] + ' ' + it['response']))
    for sid in (O, C):
        s = c['settings'][sid]
        tb = u16(s['text'] or '')
        for j, b in enumerate(s['bullets']):
            scored = sl(tb, b['start'], b['scored_end'])
            spec_map[(sid, k, j)] = float(any(x not in nums for x in NUM.findall(scored)) or bool(novel_caps(scored, vocab)))
r7['p_novel_spec_by_position'] = {}
for sid in (O, C):
    r7['p_novel_spec_by_position'][SHORT[sid]] = {f'pos {p + 1}': rci((ix, spec_map[(sid, k, j)], 1.) for s2, ix, k, j, pp in krows
                                                                     if s2 == sid and pp == p) for p in range(4)}
cO2 = collections.Counter(p for s2, ix, k, j, p in krows if s2 == O)
cC2 = collections.Counter(p for s2, ix, k, j, p in krows if s2 == C)
nO2, nC2 = sum(cO2.values()), sum(cC2.values())
wt2 = {p: (cO2[p] / nO2) / (cC2[p] / nC2) for p in cC2}
r7['Combine - Original p_novel_spec, Combine reweighted to Original position mix'] = dci(
    [(ix, spec_map[(C, k, j)] * wt2[p], wt2[p]) for s2, ix, k, j, p in krows if s2 == C],
    [(ix, spec_map[(O, k, j)], 1.) for s2, ix, k, j, p in krows if s2 == O])
r7['Combine - Original p_novel_spec, unweighted (same rows)'] = dci(
    [(ix, spec_map[(C, k, j)], 1.) for s2, ix, k, j, p in krows if s2 == C],
    [(ix, spec_map[(O, k, j)], 1.) for s2, ix, k, j, p in krows if s2 == O])
out['7_followups'] = r7
with open(os.path.join(HERE, 'c7_confound_check.json'), 'w') as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
print(json.dumps(r7, indent=1, ensure_ascii=False))
