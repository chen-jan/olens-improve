"""Per-bullet FVE attribution for every Role-bound association readout of the three settings, one
layer per job.

Generalises code/metrics_job.py (unchanged; its helpers attribution(), rows_memmap(), ACTS,
WHITENERS, SETTINGS and NEG_TOL are imported, not copied). The three changes listed in MAP.md:
  1. inputs are data/rba_three_settings.jsonl + data/rba_vector_index.json (same schema as the
     Hallucination extract);
  2. atoms with cache_key None (status empty_after_cleanup, 62 bullets in 43 Original readouts) have
     no AR vector, and their readouts have no saved fits.exact. Those readouts are written with
     'skipped' = 'no_saved_exact_fit' and null metrics for every bullet (the report drops these
     cells too); nothing is fitted for them;
  3. any layer in the extract works (20/28/36/44/52/60; L28 is new).
Math unchanged: per-layer pooled whitener (ridge 0.1), target whitened (magnitude kept), each bullet's
AR vector whitened then unit-normalised (eps 1e-9), olens_improve JointNNLS scipy_exact,
FVE = 1 - |resid|^2/|t|^2, v(empty) = 0; exact Shapley over the readout's <= 4 bullets, solo FVE,
leave-one-out drop, NNLS coefficient; dup=true when a bullet's vector also appears elsewhere in the
same readout (coefficients then not unique).

READ-ONLY on project data; writes only --out (+ --summary).

Usage (inside srun):
  python -B metrics_job_rba.py --layer 28 --out metrics/bullet_metrics.L28.jsonl [--cells id1,id2]
                               [--limit N] [--summary S.json]
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, '${OLENS_REPO_ROOT}/src')
sys.path.insert(0, str(HERE.parents[1] / 'code'))
import numpy as np  # noqa: E402
import torch  # noqa: E402
from metrics_job import ACTS, NEG_TOL, SETTINGS, WHITENERS, attribution, rows_memmap  # noqa: E402
from olens_improve.reconstruction import JointNNLS, Whitener  # noqa: E402

EXTRACT = HERE / 'data' / 'rba_three_settings.jsonl'
VINDEX = HERE / 'data' / 'rba_vector_index.json'
NULL_METRICS = {'coefficient': None, 'solo_fve': None, 'loo_drop': None, 'shapley': None,
                'shapley_share': None, 'dup': None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layer', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--cells', default='')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--summary', default='')
    args = ap.parse_args()
    torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '4')))
    t0 = time.time()
    host = os.uname().nodename

    want = set(filter(None, args.cells.split(',')))
    tag = f'|L{args.layer}|'
    cells = []
    with open(EXTRACT) as fh:
        for line in fh:
            cid = line[13:line.index('"', 13)]  # '{"cell_id": "' is 13 chars
            if tag not in cid or (want and cid not in want):
                continue
            c = json.loads(line)
            assert c['cell_id'] == cid and c['layer'] == args.layer, cid
            cells.append(c)
            if args.limit and len(cells) >= args.limit:
                break
    vindex = json.load(open(VINDEX))
    acts = rows_memmap(ACTS, 'resid')
    t_load = time.time() - t0

    w = Whitener.load(f'{WHITENERS}/whitening_iolens_pooled_L{args.layer}.safetensors')
    t_whit = time.time() - t0 - t_load

    need = sorted({(c['split'], a['cache_key']) for c in cells
                   for s in c['settings'].values() for a in s['atoms'] if a['cache_key'] is not None})
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
    dup_readouts, skipped_readouts = [], []
    examples_drop_gt_solo = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
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
                assert ids, ('empty readout', c['cell_id'], sid)  # none in this family (MAP.md section 3)
                st[f'readouts[{sid}]'] += 1
                no_vec = [a['cache_key'] is None for a in atoms]
                if s['fve'] is None:
                    # no saved exact fit: only happens when >= 1 bullet has no vector (asserted)
                    assert any(no_vec), (c['cell_id'], sid)
                    st[f'skipped_no_saved_fit[{sid}]'] += 1
                    st[f'skipped_bullets[{sid}]'] += len(atoms)
                    st[f'skipped_bullets_without_vector[{sid}]'] += sum(no_vec)
                    skipped_readouts.append([c['cell_id'], sid, sum(no_vec), len(atoms)])
                    rec['settings'][sid] = {
                        'joint_fve_saved': None, 'joint_fve_recomputed': None, 'has_dup': None,
                        'skipped': 'no_saved_exact_fit',
                        'bullets': [dict(phrase_id=pid, cache_key=a['cache_key'], has_vector=not nv, **NULL_METRICS)
                                    for pid, a, nv in zip(ids, atoms, no_vec)]}
                    continue
                assert not any(no_vec), ('saved fit but a bullet without vector', c['cell_id'], sid)
                fve_sum[sid] += s['fve']
                st[f'fitted[{sid}]'] += 1
                vecs = {a['source_phrase_id']: unit[(c['split'], a['cache_key'])] for a in atoms}
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
                mx[f'abs_recomputed_minus_saved[{sid}]'] = max(mx[f'abs_recomputed_minus_saved[{sid}]'], d)
                st['fits_diff_gt_1e-7'] += d > 1e-7
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
                        if len(examples_drop_gt_solo) < 200:
                            examples_drop_gt_solo.append([c['cell_id'], sid, pid.rsplit(':', 2)[-2] + ':' + pid.rsplit(':', 1)[-1],
                                                          so, lo, sh])
                    if so > lo + 1e-9:
                        st['solo_gt_drop'] += 1
                    bullets.append({'phrase_id': pid, 'cache_key': a['cache_key'], 'has_vector': True,
                                    'coefficient': coef, 'solo_fve': so, 'loo_drop': lo, 'shapley': sh,
                                    'shapley_share': (sh / full) if full > 0 else None, 'dup': dp})
                rec['settings'][sid] = {'joint_fve_saved': s['fve'], 'joint_fve_recomputed': full,
                                        'has_dup': has_dup, 'skipped': None, 'bullets': bullets}
            out.write(json.dumps(rec) + '\n')
            st['cells'] += 1
    os.replace(tmp_path, out_path)
    summary = {
        'layer': args.layer, 'host': host, 'slurm_job_id': os.environ.get('SLURM_JOB_ID'),
        'threads': torch.get_num_threads(), 'cells': st['cells'], 'vectors': len(keys),
        'counts': dict(st), 'max': dict(mx), 'min': {k: v for k, v in mins.items()},
        'saved_fve_sum': dict(fve_sum), 'dup_readouts': dup_readouts, 'skipped_readouts': skipped_readouts,
        'examples_drop_gt_solo': examples_drop_gt_solo,
        'seconds': {'load_inputs': round(t_load, 1), 'whitener': round(t_whit, 1), 'vectors': round(t_vec, 1),
                    'total': round(time.time() - t0, 1)},
        'peak_rss_gb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2),
    }
    print(json.dumps({k: v for k, v in summary.items() if k not in ('dup_readouts', 'skipped_readouts',
                                                                    'examples_drop_gt_solo')}), flush=True)
    if args.summary:
        Path(args.summary).write_text(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
