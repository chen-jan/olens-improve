"""Concatenate per-layer metric shards into <task>/bullet_metrics.jsonl (input-file cell order) and validate.

Generalised copy of code/metrics_validate.py (original untouched): family / task dir / layers are
arguments, the expected numbers come from the extract summary and EXPANDED_REPORT (rounded).

Usage: python -B metrics_validate_family.py --family multihop_mt --task tasks/multihop_mt \
          --layers 20,24,...,60 --report-mean 0.3020,0.3517,0.3742
Writes <task>/bullet_metrics.jsonl and <task>/logs/metrics_validation.json.
"""
import argparse
import collections
import json
import math
import os
from pathlib import Path

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
TOL_FVE = 1e-7

ap = argparse.ArgumentParser()
ap.add_argument('--family', required=True)
ap.add_argument('--task', required=True)
ap.add_argument('--layers', required=True)
ap.add_argument('--report-mean', required=True, help='rounded mean saved FVE per setting from the report, comma list')
args = ap.parse_args()
TASK = ROOT / args.task
LAYERS = [int(x) for x in args.layers.split(',')]
REPORT_MEAN = dict(zip(SETTINGS, (float(x) for x in args.report_mean.split(','))))
summ = json.load(open(TASK / f'inputs/{args.family}_extract_summary.json'))
EXPECTED_BULLETS = {sid: summ['stats'][f'atoms[{sid}]'] for sid in SETTINGS}

recs = {}
for L in LAYERS:
    for line in open(TASK / f'metrics/bullet_metrics.L{L}.jsonl'):
        r = json.loads(line)
        assert r['cell_id'] not in recs
        assert r['layer'] == L
        recs[r['cell_id']] = (line, r)
order, inp = [], {}
for line in open(TASK / f'inputs/{args.family}_three_settings.jsonl'):
    c = json.loads(line)
    order.append(c['cell_id'])
    inp[c['cell_id']] = c
assert set(order) == set(recs), ('cell set mismatch', len(order), len(recs))

out_path = TASK / 'bullet_metrics.jsonl'
with open(str(out_path) + '.tmp', 'w') as out:
    for cid in order:
        out.write(recs[cid][0] if recs[cid][0].endswith('\n') else recs[cid][0] + '\n')
os.replace(str(out_path) + '.tmp', out_path)

V = collections.Counter()
mx = collections.defaultdict(float)
mins = collections.defaultdict(lambda: math.inf)
sums = collections.defaultdict(float)
by_layer = collections.defaultdict(float)
dups_found, empties = [], []
drop_gt_solo, zero_coef_examples = [], []
lines = 0
for line in open(out_path):
    r = json.loads(line)
    lines += 1
    c = inp[r['cell_id']]
    for k in ('item_id', 'group_id', 'layer', 'position', 'split'):
        assert r[k] == c[k]
    assert set(r['settings']) == set(SETTINGS)
    for sid in SETTINGS:
        s, si = r['settings'][sid], c['settings'][sid]
        V['readouts'] += 1
        assert s['joint_fve_saved'] == si['fve']
        assert [b['phrase_id'] for b in s['bullets']] == si['phrase_ids']
        assert [b['cache_key'] for b in s['bullets']] == [a['cache_key'] for a in si['atoms']]
        sums[('saved', sid)] += s['joint_fve_saved']
        sums[('recomputed', sid)] += s['joint_fve_recomputed']
        by_layer[(sid, r['layer'])] += s['joint_fve_recomputed']
        d = abs(s['joint_fve_recomputed'] - s['joint_fve_saved'])
        mx['abs_recomputed_minus_saved'] = max(mx['abs_recomputed_minus_saved'], d)
        V['readouts_fve_diff_gt_1e-7'] += d > TOL_FVE
        V[f'bullets[{sid}]'] += len(s['bullets'])
        if not s['bullets']:
            empties.append([r['cell_id'], sid, s['joint_fve_saved'], s['joint_fve_recomputed']])
            continue
        joint = s['joint_fve_recomputed']
        mx['abs_sum_shapley_minus_joint'] = max(mx['abs_sum_shapley_minus_joint'],
                                                abs(sum(b['shapley'] for b in s['bullets']) - joint))
        if joint > 0:
            mx['abs_sum_share_minus_1'] = max(mx['abs_sum_share_minus_1'],
                                              abs(sum(b['shapley_share'] for b in s['bullets']) - 1))
        else:
            V['readouts_joint_le_0'] += 1
        if s['has_dup']:
            dups_found.append([r['cell_id'], sid, sum(b['dup'] for b in s['bullets'])])
        for i, b in enumerate(s['bullets']):
            V['bullets'] += 1
            for k in ('solo_fve', 'loo_drop', 'shapley', 'coefficient'):
                x = b[k]
                if not math.isfinite(x):
                    V[f'nonfinite[{k}]'] += 1
                mins[k] = min(mins[k], x)
                mx[k] = max(mx[k], x)
                V[f'below_-1e-9[{k}]'] += x < -1e-9
            if b['shapley_share'] is not None:
                mins['shapley_share'] = min(mins['shapley_share'], b['shapley_share'])
                mx['shapley_share'] = max(mx['shapley_share'], b['shapley_share'])
            V['drop_gt_solo'] += b['loo_drop'] > b['solo_fve'] + 1e-9
            V['shap_gt_solo'] += b['shapley'] > b['solo_fve'] + 1e-9
            V['drop_gt_shap'] += b['loo_drop'] > b['shapley'] + 1e-9
            V['solo_gt_joint'] += b['solo_fve'] > joint + 1e-9
            V['coef_zero'] += b['coefficient'] == 0.0
            V['coef_zero_nondup'] += b['coefficient'] == 0.0 and not b['dup']
            V['loo_drop_lt_1e-9'] += b['loo_drop'] < 1e-9
            V['dup_bullets'] += b['dup']
            if b['loo_drop'] > b['solo_fve'] + 1e-9 and len(drop_gt_solo) < 20:
                drop_gt_solo.append([r['cell_id'], sid, i, b['solo_fve'], b['loo_drop']])
            if b['coefficient'] == 0.0 and not b['dup'] and len(zero_coef_examples) < 10:
                zero_coef_examples.append([r['cell_id'], sid, i, b['solo_fve'], b['loo_drop'], b['shapley']])

N = len(order)
means = {kind: {sid: sums[(kind, sid)] / N for sid in SETTINGS} for kind in ('saved', 'recomputed')}
shards = {}
for L in LAYERS:
    s = json.load(open(TASK / f'logs/metrics_summary.L{L}.json'))
    shards[f'L{L}'] = {'job': s['slurm_job_id'], 'host': s['host'], 'cells': s['cells'], 'seconds': s['seconds'],
                       'peak_rss_gb': s['peak_rss_gb'], 'max': s['max'],
                       'min_marginal_over_all_subsets': s['min'].get('min_marginal_over_all_subsets')}
checks = {
    'all_cells_present': len(recs) == N,
    'bullets_match_extract': all(V[f'bullets[{sid}]'] == EXPECTED_BULLETS[sid] for sid in SETTINGS),
    'joint_fve_within_1e-7': V['readouts_fve_diff_gt_1e-7'] == 0,
    'shapley_efficiency_1e-9': mx['abs_sum_shapley_minus_joint'] < 1e-9,
    'saved_mean_matches_report_4dp': all(abs(means['saved'][sid] - REPORT_MEAN[sid]) < 5e-5 for sid in SETTINGS),
    'no_nonfinite': not any(k.startswith('nonfinite') for k in V),
    'min_marginal_ge_minus_1e-9': all(v['min_marginal_over_all_subsets'] >= -1e-9 for v in shards.values()),
}
report = {
    'family': args.family, 'checks': checks, 'all_checks_pass': all(checks.values()),
    'lines': lines, 'unique_cells': len(recs), 'readouts': V['readouts'], 'bullets': V['bullets'],
    'bullets_by_setting': {sid: V[f'bullets[{sid}]'] for sid in SETTINGS},
    'bullets_by_setting_expected': EXPECTED_BULLETS,
    'mean_fve': means, 'mean_fve_report_rounded': REPORT_MEAN,
    'mean_recomputed_fve_by_layer': {f'{sid}|L{L}': by_layer[(sid, L)] / sum(1 for c in order if inp[c]['layer'] == L)
                                     for sid in SETTINGS for L in LAYERS},
    'max': dict(mx), 'min': dict(mins),
    'counts': {k: v for k, v in V.items() if not k.startswith('bullets[')},
    'empty_readouts': empties, 'dup_readouts': dups_found,
    'drop_gt_solo_examples': drop_gt_solo, 'zero_coef_nondup_examples': zero_coef_examples,
    'shards': shards,
}
(TASK / 'logs/metrics_validation.json').write_text(json.dumps(report, indent=1))
print(json.dumps({k: report[k] for k in ('checks', 'all_checks_pass', 'lines', 'readouts', 'bullets',
                                          'bullets_by_setting', 'mean_fve', 'max', 'min', 'counts', 'dup_readouts',
                                          'empty_readouts')}, indent=1))
assert report['all_checks_pass'], checks
