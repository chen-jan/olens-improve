"""Per-bullet FVE attribution for every readout of ONE family, one layer per job.

Generalised copy of code/metrics_job.py (original untouched): --family/--inputs replace the
hard-coded Hallucination inputs; --limit takes the first N cells of the layer. Math unchanged.
Adapted from compute_bullet_metrics.py / bullet_attrib_lib.py (originals untouched). Same math as
olens_improve.reconstruction.JointNNLS.from_raw(solver='scipy_exact'):
  per-layer pooled whitener (ridge 0.1), target whitened (magnitude kept), each bullet's AR vector
  whitened then unit-normalised (eps 1e-9), scipy NNLS, FVE = 1 - |resid|^2/|t|^2, v(empty) = 0.
Per bullet: NNLS coefficient in the joint fit, solo FVE v({b}), leave-one-out drop v(all)-v(all\\b),
exact Shapley value over the readout's bullets (sums to joint FVE), shapley_share = shapley / joint.
Bullets whose vector also appears elsewhere in the same readout are flagged dup=true.

READ-ONLY on project data; writes only OUT.

Usage: python -B metrics_job_family.py --family multihop_mt --inputs tasks/multihop_mt/inputs --layer 20 --out OUT.jsonl [--cells id1,id2] [--limit N] [--summary S.json]
"""
import argparse
import collections
import hashlib
import itertools
import json
import math
import os
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, '${OLENS_REPO_ROOT}/src')
import numpy as np  # noqa: E402
import torch  # noqa: E402
from olens_improve.reconstruction import JointNNLS, Whitener  # noqa: E402

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
ACTS = '${OLENS_COMPUTE_ROOT}/activations/core-v1/activations.safetensors'
WHITENERS = ('${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/'
             'snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners')
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
NEG_TOL = -1e-9


def rows_memmap(path, key):
    """Random row access into a safetensors 2-D F32 tensor without loading the whole file."""
    with open(path, 'rb') as f:
        n = int.from_bytes(f.read(8), 'little')
        header = json.loads(f.read(n))
    info = header[key]
    assert info['dtype'] == 'F32'
    start, _ = info['data_offsets']
    return np.memmap(path, dtype='<f4', mode='r', offset=8 + n + start, shape=tuple(info['shape']))


def attribution(score, ids):
    """v over all 2^k subsets (k<=4) -> joint, [(solo, loo_drop, shapley)] per bullet."""
    n = len(ids)
    v = {sub: (score([ids[i] for i in sub]) if sub else 0.0)
         for r in range(n + 1) for sub in itertools.combinations(range(n), r)}
    full = v[tuple(range(n))]
    res = []
    for i in range(n):
        others = tuple(j for j in range(n) if j != i)
        sh = sum(math.factorial(r) * math.factorial(n - r - 1) / math.factorial(n)
                 * (v[tuple(sorted(sub + (i,)))] - v[sub])
                 for r in range(n) for sub in itertools.combinations(others, r))
        res.append((v[(i,)], full - v[others], sh))
    # monotonicity check over all subset pairs S subset S+{i}: NNLS FVE should never decrease
    min_marg = min((v[tuple(sorted(sub + (i,)))] - v[sub]
                    for i in range(n) for r in range(n)
                    for sub in itertools.combinations([j for j in range(n) if j != i], r)), default=0.0)
    return full, res, min_marg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--family', required=True)
    ap.add_argument('--inputs', required=True)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--layer', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--cells', default='')
    ap.add_argument('--summary', default='')
    args = ap.parse_args()
    torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '4')))
    t0 = time.time()
    host = os.uname().nodename

    want = set(filter(None, args.cells.split(',')))
    cells = []
    inputs = Path(args.inputs)
    with open(inputs / f'{args.family}_three_settings.jsonl') as fh:
        for line in fh:
            c = json.loads(line)
            if c['layer'] == args.layer and (not want or c['cell_id'] in want):
                cells.append(c)
    if args.limit:
        cells = cells[:args.limit]
    vindex = json.load(open(inputs / f'{args.family}_vector_index.json'))
    acts = rows_memmap(ACTS, 'resid')
    t_load = time.time() - t0

    w = Whitener.load(f'{WHITENERS}/whitening_iolens_pooled_L{args.layer}.safetensors')
    t_whit = time.time() - t0 - t_load

    need = sorted({(c['split'], a['cache_key']) for c in cells
                   for s in c['settings'].values() for a in s['atoms']})
    by_file = collections.defaultdict(list)
    for split, key in need:
        path, row = vindex[split][key]
        by_file[path].append((row, (split, key)))
    raw = {}
    for path, items in by_file.items():
        mm = rows_memmap(path, 'vectors')
        rows = sorted(items)
        block = np.asarray(mm[[r for r, _ in rows]])
        raw.update({sk: block[i] for i, (_, sk) in enumerate(rows)})
    keys = list(raw)
    unit = {}
    for i in range(0, len(keys), 4096):
        chunk = keys[i:i + 4096]
        x = w.whiten(torch.from_numpy(np.stack([raw[k] for k in chunk])))
        x = x / (x.norm(dim=1, keepdim=True) + 1e-9)
        unit.update(zip(chunk, x))
    del raw
    t_vec = time.time() - t0 - t_load - t_whit

    st = collections.Counter()
    mx = collections.defaultdict(float)
    mins = collections.defaultdict(lambda: math.inf)
    fve_sum = collections.Counter()
    dup_readouts = []
    examples_drop_gt_solo = []
    out_path = Path(args.out)
    tmp_path = out_path.with_suffix(out_path.suffix + '.tmp')
    with open(tmp_path, 'w') as out:
        for c in cells:
            target_raw = torch.from_numpy(np.asarray(acts[c['activation_row']]).copy())
            assert hashlib.sha256(target_raw.numpy().tobytes()).hexdigest() == c['activation_sha256'], c['cell_id']
            target = w.whiten(target_raw.reshape(1, -1))[0]
            rec = {k: c[k] for k in ('cell_id', 'item_id', 'group_id', 'layer', 'position', 'split')}
            rec['settings'] = {}
            for sid in SETTINGS:
                s = c['settings'][sid]
                ids = list(s['phrase_ids'])
                atoms = s['atoms']
                assert ids == [a['source_phrase_id'] for a in atoms], (c['cell_id'], sid)
                st[f'readouts[{sid}]'] += 1
                fve_sum[sid] += s['fve']
                if not ids:
                    st[f'empty[{sid}]'] += 1
                    rec['settings'][sid] = {'joint_fve_saved': s['fve'], 'joint_fve_recomputed': 0.0,
                                            'has_dup': False, 'bullets': []}
                    mx['abs_recomputed_minus_saved'] = max(mx['abs_recomputed_minus_saved'], abs(s['fve']))
                    continue
                vecs = {a['source_phrase_id']: unit[(c['split'], a['cache_key'])] for a in atoms}
                # duplicate vectors within this readout: same cache key, or (belt and braces) cosine ~ 1
                kc = collections.Counter(a['cache_key'] for a in atoms)
                dup = [kc[a['cache_key']] > 1 for a in atoms]
                for i, j in itertools.combinations(range(len(ids)), 2):
                    if float(vecs[ids[i]] @ vecs[ids[j]]) > 1 - 1e-6:
                        if not (dup[i] and dup[j]):
                            st['dup_by_vector_only'] += 1
                        dup[i] = dup[j] = True
                has_dup = any(dup)
                if has_dup:
                    st[f'dup_readouts[{sid}]'] += 1
                    st['dup_bullets'] += sum(dup)
                    dup_readouts.append([c['cell_id'], sid, sum(dup)])
                scorer = JointNNLS(target, vecs, solver='scipy_exact')
                fit = scorer.fit(ids)
                full, attr, min_marg = attribution(scorer.score, ids)
                assert full == fit.fve
                d = abs(full - s['fve'])
                mx['abs_recomputed_minus_saved'] = max(mx['abs_recomputed_minus_saved'], d)
                st['fits_diff_gt_1e-6'] += d > 1e-6
                eff = abs(sum(a[2] for a in attr) - full)
                mx['abs_sum_shapley_minus_joint'] = max(mx['abs_sum_shapley_minus_joint'], eff)
                mins['min_marginal_over_all_subsets'] = min(mins['min_marginal_over_all_subsets'], min_marg)
                if not has_dup:
                    cd = max(abs(x - y) for x, y in zip(fit.coefficients, s['coefficients']))
                    mx['abs_coef_minus_saved_nondup'] = max(mx['abs_coef_minus_saved_nondup'], cd)
                bullets = []
                for pid, a, coef, (so, lo, sh), dp in zip(ids, atoms, fit.coefficients, attr, dup):
                    vals = (so, lo, sh, coef)
                    if not all(math.isfinite(x) for x in vals):
                        st['nonfinite'] += 1
                    for name, x in (('solo_fve', so), ('loo_drop', lo), ('shapley', sh), ('coefficient', coef)):
                        mins[name] = min(mins[name], x)
                        st[f'neg_lt_tol[{name}]'] += x < NEG_TOL
                    st['bullets'] += 1
                    st[f'bullets[{sid}]'] += 1
                    if lo > so + 1e-9:
                        st['drop_gt_solo'] += 1
                        st[f'drop_gt_solo[{sid}]'] += 1
                        if not dp:
                            st['drop_gt_solo_nondup'] += 1
                        if len(examples_drop_gt_solo) < 400:
                            examples_drop_gt_solo.append([c['cell_id'], sid, pid.rsplit(':', 2)[-2] + ':' + pid.rsplit(':', 1)[-1],
                                                          so, lo, sh])
                    if so > lo + 1e-9:
                        st['solo_gt_drop'] += 1
                    b = {'phrase_id': pid, 'cache_key': a['cache_key'], 'coefficient': coef,
                         'solo_fve': so, 'loo_drop': lo, 'shapley': sh,
                         'shapley_share': (sh / full) if full > 0 else None, 'dup': dp}
                    bullets.append(b)
                rec['settings'][sid] = {'joint_fve_saved': s['fve'], 'joint_fve_recomputed': full,
                                        'has_dup': has_dup, 'bullets': bullets}
            out.write(json.dumps(rec) + '\n')
            st['cells'] += 1
    os.replace(tmp_path, out_path)
    summary = {
        'layer': args.layer, 'host': host, 'slurm_job_id': os.environ.get('SLURM_JOB_ID'),
        'threads': torch.get_num_threads(), 'cells': st['cells'], 'vectors': len(keys),
        'counts': dict(st), 'max': dict(mx), 'min': {k: v for k, v in mins.items()},
        'saved_fve_sum': dict(fve_sum), 'dup_readouts': dup_readouts,
        'examples_drop_gt_solo': examples_drop_gt_solo,
        'seconds': {'load_inputs': round(t_load, 1), 'whitener': round(t_whit, 1), 'vectors': round(t_vec, 1),
                    'total': round(time.time() - t0, 1)},
        'peak_rss_gb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2),
    }
    print(json.dumps(summary), flush=True)
    if args.summary:
        Path(args.summary).write_text(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
