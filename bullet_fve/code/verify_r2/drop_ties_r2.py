#!/usr/bin/env python3
"""Does the mid-rank-percentile position adjustment of leave-one-out drop also break exact-zero ties by stratum?
Full-precision drops from metrics/bullet_metrics.jsonl, labels / sizes from page/data/index.json."""
import collections, json, sys
import numpy as np

ROOT = '${OLENS_SCRATCH}/olens-bullet-fve'
idx = json.load(open(f'{ROOT}/page/data/index.json'))
sids = [s['id'] for s in idx['meta']['settings']]
met = {}
with open(f'{ROOT}/metrics/bullet_metrics.jsonl') as fh:
    for line in fh:
        r = json.loads(line)
        met[r['cell_id']] = r['settings']


def midrank_pct(x):
    order = np.argsort(x, kind='mergesort'); xs = x[order]; r = np.empty(len(x)); i = 0; n = len(x)
    while i < n:
        j = i
        while j + 1 < n and xs[j + 1] == xs[i]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2.0 + 1; i = j + 1
    return r / n


rng = np.random.default_rng(7)
n_items = len(idx['items'])
M = np.stack([np.bincount(rng.integers(0, n_items, n_items), minlength=n_items) for _ in range(1000)]).astype(float)
out = {}
for j, sid in enumerate(sids):
    lab, pos, size, ro, item, drop, share, solo = [], [], [], [], [], [], [], []
    for ci, c in enumerate(idx['cells']):
        it, L, p = c['k'].split('.L')[0], c['L'], c['p']
        m = met[f'hallucination|{it}|L{L:02d}|p{p:05d}'][sid]
        st = c['s'][j]
        for bi, b in enumerate(m['bullets']):
            lab.append(st['bl'][bi]); pos.append(bi); size.append(st['n']); ro.append(ci); item.append(c['i'])
            drop.append(round(b['loo_drop'], 9)); share.append(round(b['shapley'] / m['joint_fve_recomputed'], 9) if m['joint_fve_recomputed'] > 0 else 0.0)
            solo.append(round(b['solo_fve'], 9))
    lab = np.array(lab); pos = np.array(pos); size = np.array(size); ro = np.array(ro); item = np.array(item)
    V = {'drop': np.array(drop), 'shap_share': np.array(share), 'solo': np.array(solo)}
    labelled = np.isin(lab, ['w', 'c', 'o'])
    strata = sorted(set(zip(pos[labelled], size[labelled])))
    pct = {}
    for s, v in V.items():
        p_ = np.full(len(v), np.nan)
        for key in strata:
            mm = labelled & (pos == key[0]) & (size == key[1])
            p_[mm] = midrank_pct(v[mm])
        pct[s] = p_
    zero_rate = {f'{a},{b}': float((V['drop'][labelled & (pos == a) & (size == b)] == 0).mean()) for a, b in strata if (labelled & (pos == a) & (size == b)).sum() > 100}
    byro = collections.defaultdict(lambda: ([], []))
    for b in np.nonzero(np.isin(lab, ['w', 'c']))[0]:
        byro[ro[b]][0 if lab[b] == 'w' else 1].append(b)
    P = np.array([(item[w], w, c) for ws, cs in byro.values() if ws and cs for w in ws for c in cs])
    res = {'zero_rate_by_stratum': zero_rate, 'n_pairs': len(P)}
    for s in ('drop', 'solo', 'shap_share'):
        v = V[s]; q = pct[s]
        raw_d = np.sign(v[P[:, 2]] - v[P[:, 1]])
        adj_d = np.sign(q[P[:, 2]] - q[P[:, 1]])
        tie = raw_d == 0
        keep_d = np.where(tie, 0, adj_d)
        def rate(d, wt=None):
            val = (d > 0) + 0.5 * (d == 0); wt = np.ones(len(d)) if wt is None else wt
            return float((val * wt).sum() / wt.sum())
        r = {'raw': rate(raw_d), 'adj': rate(adj_d), 'adj_raw_ties_kept': rate(keep_d), 'frac_raw_tie': float(tie.mean())}
        nz = ~tie
        r['raw_nontied'] = rate(raw_d[nz]); r['adj_nontied'] = rate(adj_d[nz])
        # what the adjustment does to the raw-tied pairs
        r['adj_on_raw_ties'] = rate(adj_d[tie]) if tie.any() else None
        b = np.array([rate(keep_d, M[k][P[:, 0]]) for k in range(1000)])
        r['adj_raw_ties_kept_ci'] = np.percentile(b, [2.5, 97.5]).round(4).tolist()
        res[s] = {k_: (round(x, 4) if isinstance(x, float) else x) for k_, x in r.items()}
    out[sid] = res
    print(sid, json.dumps(res, indent=0), flush=True)
json.dump(out, open(f'{ROOT}/verify_r2/drop_ties_r2.json', 'w'), indent=1)
