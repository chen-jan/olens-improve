"""Step 1: recompute joint/heat/solo for the 60 verify_sample.pt occurrences with scipy.optimize.nnls
(float64), independently of token_heat.py, and compare to token_heat.jsonl (tol 1e-6)."""
import json
import sys
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import nnls

HEAT = Path('${OLENS_SCRATCH}/olens-bullet-fve/heat')
OUT = HEAT / 'verify'
TOL = 1e-6


def fve(X, t):
    """X [m, D] float64 rows, t [D] float64. FVE = 1 - |t - X^T c|^2 / |t|^2, c = nnls."""
    tt = float(t @ t)
    if X.shape[0] == 0:
        return 0.0
    c, _ = nnls(X.T, t, maxiter=10_000)
    r = t - X.T @ c
    return 1.0 - float(r @ r) / tt


def main():
    d = torch.load(HEAT / 'verify_sample.pt', weights_only=True)
    samples = d['samples']
    print('doc:', d['doc'][:200], '...', 'n samples', len(samples))
    want = {(s['cell_id'], s['setting'], s['bullet']) for s in samples}
    recs = {}
    with open(HEAT / 'token_heat.jsonl') as f:
        for line in f:
            r = json.loads(line)
            k = (r['cell_id'], r['setting'], r['bullet'])
            if k in want:
                recs[k] = r
    assert len(recs) == len(want) == len(samples), (len(recs), len(want), len(samples))
    rows = []
    worst = {'joint': 0.0, 'heat': 0.0, 'solo': 0.0, 'joint_cached': 0.0, 'sample_joint': 0.0,
             'sample_solo': 0.0, 'cached_vs_saved': 0.0, 'unit_norm_dev': 0.0, 'solo_formula_vs_nnls': 0.0}
    layers = {}
    for s in samples:
        k = (s['cell_id'], s['setting'], s['bullet'])
        r = recs[k]
        t = s['target'].double().numpy()
        U = s['prefix_unit'].double().numpy()
        O = s['others_unit'].double().numpy().reshape(-1, t.shape[0])
        cvec = s['cached_unit'].double().numpy()
        n = s['n']
        assert U.shape[0] == n == r['n_scored'], (k, U.shape, n, r['n_scored'])
        assert s['layer'] == r['layer']
        assert O.shape[0] == r['n_bullets'] - 1, (k, O.shape, r['n_bullets'])
        layers[s['layer']] = layers.get(s['layer'], 0) + 1
        un = np.linalg.norm(U, axis=1)
        worst['unit_norm_dev'] = max(worst['unit_norm_dev'], float(np.abs(un - 1).max()))
        joint = [fve(O, t)] + [fve(np.vstack([O, U[i:i + 1]]), t) for i in range(n)]
        joint = np.array(joint)
        heat = np.diff(joint)
        tt = float(t @ t)
        solo_formula = np.array([max(0.0, float(U[i] @ t)) ** 2 / (float(U[i] @ U[i]) * tt) for i in range(n)])
        solo_nnls = np.array([fve(U[i:i + 1], t) for i in range(n)])
        jc = fve(np.vstack([O, cvec[None]]), t)
        dj = float(np.abs(joint - np.array(r['joint'])).max())
        dh = float(np.abs(heat - np.array(r['heat'])).max())
        ds = float(np.abs(solo_formula - np.array(r['solo'])).max())
        dsn = float(np.abs(solo_formula - solo_nnls).max())
        dc = abs(jc - r['joint_cached'])
        dsj = float(np.abs(joint - s['joint'].double().numpy()).max())
        dss = float(np.abs(solo_formula - s['solo'].double().numpy()).max())
        dcs = abs(jc - s['saved_fve'])
        for name, v in (('joint', dj), ('heat', dh), ('solo', ds), ('joint_cached', dc), ('sample_joint', dsj),
                        ('sample_solo', dss), ('cached_vs_saved', dcs), ('solo_formula_vs_nnls', dsn)):
            worst[name] = max(worst[name], v)
        # drift as recorded = joint_n - joint_cached
        ddrift = abs((joint[-1] - jc) - r['drift'])
        rows.append({'cell_id': k[0], 'setting': k[1], 'bullet': k[2], 'layer': s['layer'], 'n': n,
                     'n_others': int(O.shape[0]), 'max_abs_joint': dj, 'max_abs_heat': dh, 'max_abs_solo': ds,
                     'abs_joint_cached': dc, 'abs_cached_vs_saved_fve': dcs, 'abs_drift': ddrift,
                     'pass': bool(dj < TOL and dh < TOL and ds < TOL and dc < TOL and dcs < TOL and ddrift < TOL)})
    out = {'n': len(rows), 'tol': TOL, 'all_pass': all(r['pass'] for r in rows), 'n_fail': sum(not r['pass'] for r in rows),
           'worst': worst, 'by_layer': layers,
           'n_bullets_dist': {str(m): sum(1 for r in rows if r['n_others'] + 1 == m) for m in range(1, 5)},
           'n_prefix_fits': int(sum(r['n'] for r in rows)), 'rows': rows}
    (OUT / 'v1_sample_nnls.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))
    fails = [r for r in rows if not r['pass']]
    for r in fails[:10]:
        print('FAIL', r)


if __name__ == '__main__':
    main()
