"""Recompute the saved exact joint FVE for a few Role-bound association cells from raw AR vectors,
with the same math as code/metrics_job.py (per-layer pooled whitener, unit-normalised whitened
bullet vectors, scipy NNLS). One cell per split x layer (18 cells x 3 settings), plus one capped
readout without an exact fit to confirm it is skipped. Run through srun (6 whitener eighs).

Usage: python -B verify_fve.py  -> data/verify_fve.json
"""
import collections
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, '${OLENS_SCRATCH}/olens-bullet-fve/code')
sys.path.insert(0, '${OLENS_SCRATCH}/olens-bullet-fve/tasks/role_bound_association')
import numpy as np  # noqa: E402
import torch  # noqa: E402
from metrics_job import ACTS, WHITENERS, attribution, rows_memmap  # noqa: E402
from olens_improve.reconstruction import JointNNLS, Whitener  # noqa: E402
import load  # noqa: E402

torch.set_num_threads(int(os.environ.get('SLURM_CPUS_PER_TASK', '4')))
t0 = time.time()
picked, nofit = {}, None
for row in load.iter_extract():
    k = (row['split'], row['layer'])
    if k not in picked and all(s['fve'] is not None for s in row['settings'].values()):
        picked[k] = row
    if nofit is None and row['settings']['capped_n1-n1']['fve'] is None:
        nofit = row
vindex = json.load(open(load.VINDEX))
acts = rows_memmap(ACTS, 'resid')
res = {'cells': [], 'max_abs_diff': collections.defaultdict(float), 'max_shapley_efficiency_err': 0.0}
for layer in sorted({k[1] for k in picked}):
    w = Whitener.load(f'{WHITENERS}/whitening_iolens_pooled_L{layer}.safetensors')
    for (split, lay), row in sorted(picked.items()):
        if lay != layer:
            continue
        raw = torch.from_numpy(np.asarray(acts[row['activation_row']]).copy())
        assert hashlib.sha256(raw.numpy().tobytes()).hexdigest() == row['activation_sha256']
        target = w.whiten(raw.reshape(1, -1))[0]
        rec = {'cell_id': row['cell_id'], 'split': split, 'layer': layer}
        for cond, s in row['settings'].items():
            vecs = {}
            for a in s['atoms']:
                path, r = vindex[split][a['cache_key']]
                x = w.whiten(torch.from_numpy(np.asarray(rows_memmap(path, 'vectors')[r]).copy()).reshape(1, -1))[0]
                vecs[a['source_phrase_id']] = x / (x.norm() + 1e-9)
            sc = JointNNLS(target, vecs, solver='scipy_exact')
            full, attr, _ = attribution(sc.score, list(s['phrase_ids']))
            d = abs(full - s['fve'])
            res['max_abs_diff'][cond] = max(res['max_abs_diff'][cond], d)
            res['max_shapley_efficiency_err'] = max(res['max_shapley_efficiency_err'], abs(sum(a[2] for a in attr) - full))
            rec[cond] = {'saved': s['fve'], 'recomputed': full, 'abs_diff': d,
                         'shapley': [a[2] for a in attr]}
        res['cells'].append(rec)
    print('layer', layer, 'done', round(time.time() - t0, 1), 's', flush=True)
res['nofit_example'] = {'cell_id': nofit['cell_id'], 'capped_atoms_without_vector':
                        sum(a['cache_key'] is None for a in nofit['settings']['capped_n1-n1']['atoms'])}
res['seconds'] = round(time.time() - t0, 1)
res['max_abs_diff'] = dict(res['max_abs_diff'])
json.dump(res, open(load.DATA / 'verify_fve.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != 'cells'}, indent=1))
