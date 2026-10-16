#!/usr/bin/env python3
"""Diagnose two verifier claims about summary.json (exploratory, all splits):
 1) pooled AUROC > 0.5 for solo / shap is driven by readout-level differences (clean bullets mostly come from
    consistent readouts, which have higher joint FVE);
 2) the same-readout pair rate is confounded by bullet position (wrong bullets sit later; later bullets get more
    share in Original / Best of 32).
Reads page/data (index + items) and metrics/bullet_metrics.jsonl through build_summary's loaders."""
import collections
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_summary as B  # noqa: E402

D = B.ROOT / 'page/data'
meta, items, cells, sids, full, item_files = B.load(D, B.ROOT / 'metrics/bullet_metrics.jsonl')
arrays = B.bullet_rows(meta, items, cells, sids, full, item_files)
codes_names = meta['label_codes']
print('label codes', codes_names)
W, C, O = B.LAB['w'], B.LAB['c'], B.LAB['o']


def auc(pos, neg):
    """P(pos > neg), ties 0.5."""
    if len(pos) == 0 or len(neg) == 0:
        return float('nan')
    return mannwhitneyu(pos, neg, alternative='two-sided', method='asymptotic').statistic / (len(pos) * len(neg))


def pair_rate(v, lab, readout):
    num = den = 0.0
    by = collections.defaultdict(lambda: ([], []))
    for t in np.flatnonzero((lab == W) | (lab == C)):
        by[readout[t]][0 if lab[t] == W else 1].append(v[t])
    for ws, cs in by.values():
        if ws and cs:
            ws, cs = np.array(ws), np.array(cs)
            num += (cs[:, None] > ws[None, :]).sum() + 0.5 * (cs[:, None] == ws[None, :]).sum()
            den += len(ws) * len(cs)
    return num / den


out = {}
for j, sid in enumerate(sids):
    a = arrays[sid]
    n_ro = len(cells)
    # readout label code of every bullet and readout size
    ro_code = np.array([c['s'][j]['c'] for c in cells])
    ro_n = np.array([c['s'][j]['n'] for c in cells])
    # readout ids: assigned cell by cell, setting by setting -> readout = cell_index * 3 + j
    cell_idx = a['readout'] // len(sids)
    assert np.all(a['readout'] % len(sids) == j)
    rlab = ro_code[cell_idx]
    rsize = ro_n[cell_idx]
    lab = a['lab']
    r = {}
    # ---- issue 1
    fves = np.array([full[c['k']][sid]['saved'] for c in cells])
    r['readout_auc_fve_cons_vs_hall'] = auc(fves[ro_code == 0], fves[ro_code == 1])
    r['clean_by_readout_label'] = {codes_names[k]: int(((lab == C) & (rlab == k)).sum()) for k in range(5)}
    r['wrong_by_readout_label'] = {codes_names[k]: int(((lab == W) & (rlab == k)).sum()) for k in range(5)}
    r['auroc_pooled'] = {}
    r['auroc_clean_from_halluc'] = {}
    r['pair'] = {}
    for sc in B.SCORES:
        v = a[sc]
        r['auroc_pooled'][sc] = auc(v[lab == C], v[lab == W])
        r['auroc_clean_from_halluc'][sc] = auc(v[(lab == C) & (rlab == 1)], v[lab == W])
        r['pair'][sc] = pair_rate(v, lab, a['readout'])
    # ---- issue 2: positions in mixed readouts
    has_w = collections.Counter(a['readout'][lab == W].tolist())
    has_c = collections.Counter(a['readout'][lab == C].tolist())
    mixed = np.array([has_w[x] > 0 and has_c[x] > 0 for x in a['readout'].tolist()])
    r['mixed_mean_pos'] = {'wrong': float(a['pos'][mixed & (lab == W)].mean()),
                           'clean': float(a['pos'][mixed & (lab == C)].mean())}
    r['mixed_n'] = {'readouts': int(len(set(a['readout'][mixed].tolist()))),
                    'wrong': int((mixed & (lab == W)).sum()), 'clean': int((mixed & (lab == C)).sum())}
    # mixed-readout size distribution
    r['mixed_size_counts'] = dict(collections.Counter(rsize[mixed & (lab == W)].tolist()))
    # centring on the (position, readout size) mean; two reference sets
    spec = (lab == W) | (lab == C) | (lab == O)
    r['pair_centred_spec'] = {}
    r['pair_centred_all'] = {}
    r['pair_pctl_spec'] = {}
    for sc in B.SCORES:
        v = a[sc]
        for name, ref in (('pair_centred_spec', spec), ('pair_centred_all', np.ones_like(spec))):
            cv = v.copy()
            for q in range(4):
                for n in range(1, 5):
                    m = (a['pos'] == q) & (rsize == n)
                    if m.any():
                        mm = m & ref
                        cv[m] = v[m] - (v[mm].mean() if mm.any() else 0.0)
            r[name][sc] = pair_rate(np.round(cv, 9), lab, a['readout'])
        # percentile within (position, size) stratum among spec bullets
        pv = np.full(len(v), np.nan)
        for q in range(4):
            for n in range(1, 5):
                m = (a['pos'] == q) & (rsize == n) & spec
                if m.any():
                    ref = np.sort(v[m])
                    pv[m] = (np.searchsorted(ref, v[m], 'left') + np.searchsorted(ref, v[m], 'right')) / (2 * len(ref))
        r['pair_pctl_spec'][sc] = pair_rate(np.round(np.nan_to_num(pv), 9), lab, a['readout'])
    # mean share by (pos) for size-4 readouts only
    r['share_by_pos_size4'] = [float(a['shap_share'][spec & (a['pos'] == q) & (rsize == 4)].mean()) for q in range(4)]
    r['wrong_rate_by_pos_size4'] = [float((lab[spec & (a['pos'] == q) & (rsize == 4)] == W).mean()) for q in range(4)]
    out[sid] = r
    print(f'\n=== {sid}')
    for k, v in r.items():
        if isinstance(v, dict):
            print(f'  {k}: ' + ', '.join(f'{kk}={vv:.4f}' if isinstance(vv, float) else f'{kk}={vv}' for kk, vv in v.items()))
        elif isinstance(v, list):
            print(f'  {k}: ' + ', '.join(f'{x:.4f}' for x in v))
        else:
            print(f'  {k}: {v:.4f}')
json.dump(out, open(B.ROOT / 'logs/diag_summary_confounds.json', 'w'), indent=1)
