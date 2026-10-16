"""Concatenate the per-layer shards into bullet_metrics.jsonl (extract cell order) and validate them
against the extract (generalises code/metrics_validate.py).

Checks: cell set == extract (11,400); phrase ids per readout == extract; saved fve copied exactly;
|recomputed - saved| <= 1e-7 for every fitted readout; Shapley sums to the joint fit; share sums to 1;
no negative values beyond -1e-9; bullet counts == extract atoms; skipped readouts == the 43 Original
readouts without fits.exact; mean saved FVE == MAP.md (19.40% n=11,357 / 23.08% / 25.04%);
shared-vector readouts == extract (21 Original / 2 Best of 32).

Usage: python -B metrics_validate_rba.py  -> bullet_metrics.jsonl, data/metrics_validation.json
"""
import collections
import json
import math
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYERS = (20, 28, 36, 44, 52, 60)
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
TOL = 1e-7
EXPECTED_MEAN = {'capped_n1-n1': 0.19402, 'best_n_exact-n32': 0.23077, 'pooled_greedy_swap-n32': 0.25040}
EXPECTED_N_FIT = {'capped_n1-n1': 11357, 'best_n_exact-n32': 11400, 'pooled_greedy_swap-n32': 11400}
EXPECTED_BULLETS = {'capped_n1-n1': 45545, 'best_n_exact-n32': 45567, 'pooled_greedy_swap-n32': 45572}
EXPECTED_SHARED = {'capped_n1-n1': 21, 'best_n_exact-n32': 2, 'pooled_greedy_swap-n32': 0}

recs = {}
for L in LAYERS:
    for line in open(HERE / f'metrics/bullet_metrics.L{L}.jsonl'):
        r = json.loads(line)
        assert r['cell_id'] not in recs
        recs[r['cell_id']] = line if line.endswith('\n') else line + '\n'
order, inp = [], {}
for line in open(HERE / 'data/rba_three_settings.jsonl'):
    c = json.loads(line)
    order.append(c['cell_id'])
    inp[c['cell_id']] = {'split': c['split'], 'layer': c['layer'], 'position': c['position'], 'item_id': c['item_id'],
                         'settings': {sid: {'fve': s['fve'], 'phrase_ids': s['phrase_ids'],
                                            'keys': [a['cache_key'] for a in s['atoms']]}
                                      for sid, s in c['settings'].items()}}
assert set(order) == set(recs), 'cell set mismatch'
out_path = HERE / 'bullet_metrics.jsonl'
with open(str(out_path) + '.tmp', 'w') as out:
    for cid in order:
        out.write(recs[cid])
os.replace(str(out_path) + '.tmp', out_path)
del recs

V = collections.Counter()
mx = collections.defaultdict(float)
mins = collections.defaultdict(lambda: math.inf)
sums = collections.defaultdict(float)
nfit = collections.Counter()
skipped, shared_found, worst = [], collections.Counter(), []
for line in open(out_path):
    r = json.loads(line)
    c = inp[r['cell_id']]
    for k in ('item_id', 'layer', 'position', 'split'):
        assert r[k] == c[k]
    assert set(r['settings']) == set(SETTINGS)
    for sid in SETTINGS:
        s, si = r['settings'][sid], c['settings'][sid]
        V['readouts'] += 1
        assert [b['phrase_id'] for b in s['bullets']] == si['phrase_ids']
        assert [b['cache_key'] for b in s['bullets']] == si['keys']
        V[f'bullets[{sid}]'] += len(s['bullets'])
        if len(set(si['keys'])) != len(si['keys']):
            shared_found[sid] += 1
        if si['fve'] is None:
            assert s['skipped'] == 'no_saved_exact_fit' and s['joint_fve_recomputed'] is None
            assert all(b['shapley'] is None for b in s['bullets'])
            skipped.append([r['cell_id'], sid, sum(not b['has_vector'] for b in s['bullets'])])
            V[f'skipped_bullets[{sid}]'] += len(s['bullets'])
            continue
        assert s['skipped'] is None and s['joint_fve_saved'] == si['fve']
        nfit[sid] += 1
        sums[('saved', sid)] += s['joint_fve_saved']
        sums[('recomputed', sid)] += s['joint_fve_recomputed']
        d = abs(s['joint_fve_recomputed'] - s['joint_fve_saved'])
        mx['abs_recomputed_minus_saved'] = max(mx['abs_recomputed_minus_saved'], d)
        mx[f'abs_recomputed_minus_saved[{sid}]'] = max(mx[f'abs_recomputed_minus_saved[{sid}]'], d)
        V['readouts_diff_gt_tol'] += d > TOL
        if d > 2e-8:
            worst.append([r['cell_id'], sid, d])
        joint = s['joint_fve_recomputed']
        mx['abs_sum_shapley_minus_joint'] = max(mx['abs_sum_shapley_minus_joint'],
                                                abs(sum(b['shapley'] for b in s['bullets']) - joint))
        if joint > 0:
            mx['abs_sum_share_minus_1'] = max(mx['abs_sum_share_minus_1'],
                                              abs(sum(b['shapley_share'] for b in s['bullets']) - 1))
        else:
            V['joint_le_0'] += 1
        V[f'dup_readouts[{sid}]'] += bool(s['has_dup'])
        for b in s['bullets']:
            V['bullets_with_metrics'] += 1
            assert b['has_vector']
            for k in ('solo_fve', 'loo_drop', 'shapley', 'coefficient'):
                x = b[k]
                V[f'nonfinite[{k}]'] += not math.isfinite(x)
                mins[k] = min(mins[k], x)
                V[f'below_-1e-9[{k}]'] += x < -1e-9
            V['solo_gt_joint'] += b['solo_fve'] > joint + 1e-9
            V['drop_gt_solo'] += b['loo_drop'] > b['solo_fve'] + 1e-9
            V['coef_zero'] += b['coefficient'] == 0.0
            V['dup_bullets'] += b['dup']

means = {kind: {sid: sums[(kind, sid)] / nfit[sid] for sid in SETTINGS} for kind in ('saved', 'recomputed')}
assert dict(nfit) == EXPECTED_N_FIT, dict(nfit)
assert {sid: V[f'bullets[{sid}]'] for sid in SETTINGS} == EXPECTED_BULLETS
assert all(abs(means['saved'][sid] - EXPECTED_MEAN[sid]) < 5e-6 for sid in SETTINGS), means
assert mx['abs_recomputed_minus_saved'] <= TOL, mx
assert len(skipped) == 43 and all(x[1] == 'capped_n1-n1' and x[2] >= 1 for x in skipped)
assert {sid: shared_found[sid] for sid in SETTINGS} == EXPECTED_SHARED
assert all(V[f'below_-1e-9[{k}]'] == 0 for k in ('solo_fve', 'loo_drop', 'shapley', 'coefficient'))
shards = {}
for L in LAYERS:
    s = json.load(open(HERE / f'logs/metrics_summary.L{L}.json'))
    shards[f'L{L}'] = {'job': s['slurm_job_id'], 'host': s['host'], 'cells': s['cells'], 'vectors': s['vectors'],
                       'seconds': s['seconds'], 'peak_rss_gb': s['peak_rss_gb'],
                       'max_abs_recomputed_minus_saved': s['max'].get('abs_recomputed_minus_saved'),
                       'max_abs_coef_minus_saved_nondup': s['max'].get('abs_coef_minus_saved_nondup')}
report = {
    'lines': len(order), 'readouts': V['readouts'], 'fitted_readouts': dict(nfit),
    'bullets_by_setting': {sid: V[f'bullets[{sid}]'] for sid in SETTINGS},
    'bullets_with_metrics': V['bullets_with_metrics'],
    'mean_fve': means, 'mean_fve_expected': EXPECTED_MEAN, 'tolerance': TOL,
    'max': dict(mx), 'min': dict(mins),
    'counts': {k: v for k, v in V.items() if not k.startswith('bullets[')},
    'shared_vector_readouts': dict(shared_found),
    'skipped_readouts': skipped,
    'readouts_diff_gt_2e-8': sorted(worst, key=lambda x: -x[2])[:20],
    'shards': shards,
}
(HERE / 'data/metrics_validation.json').write_text(json.dumps(report, indent=1))
print(json.dumps({k: v for k, v in report.items() if k != 'skipped_readouts'}, indent=1))
