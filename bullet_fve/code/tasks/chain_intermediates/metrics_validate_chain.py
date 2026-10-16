"""Concatenate the per-layer metrics shards (metrics/bullet_metrics.L{L}.jsonl, written by run_metrics_all.py
-> metrics_chain.py -> the unchanged code/metrics_job.py) into bullet_metrics.jsonl (extract cell order) and
validate. Generalises code/metrics_validate.py (Hallucination) to Chained intermediates (11 layers).

Output schema = metrics/bullet_metrics.jsonl of the Hallucination study: one line per cell,
{cell_id, item_id, group_id, layer, position, split, settings{sid: {joint_fve_saved, joint_fve_recomputed,
has_dup, bullets[{phrase_id, cache_key, coefficient, solo_fve, loo_drop, shapley, shapley_share, dup}]}}}.

Light (reads ~6 MB of shards + the 22 MB extract). Writes bullet_metrics.jsonl, metrics_validation.json.
"""
import collections
import json
import math
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYERS = list(range(20, 61, 4))
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
# MAP.md / EXPANDED_REPORT lines 165-173 and extract_summary.json
EXPECTED_MEAN_PCT = {'capped_n1-n1': 17.13, 'best_n_exact-n32': 23.79, 'pooled_greedy_swap-n32': 25.81}
EXPECTED_BULLETS = {'capped_n1-n1': 5276, 'best_n_exact-n32': 5275, 'pooled_greedy_swap-n32': 5222}
EXPECTED_DUP_READOUTS = {'capped_n1-n1': 19, 'best_n_exact-n32': 16, 'pooled_greedy_swap-n32': 0}
TOL = 1e-7

recs = {}
for L in LAYERS:
    for line in open(HERE / f'metrics/bullet_metrics.L{L}.jsonl'):
        r = json.loads(line)
        assert r['cell_id'] not in recs
        assert r['layer'] == L
        recs[r['cell_id']] = (line, r)
order, inp = [], {}
for line in open(HERE / 'chain_three_settings.jsonl'):
    c = json.loads(line)
    order.append(c['cell_id'])
    inp[c['cell_id']] = c
assert set(order) == set(recs), 'cell set mismatch'

out_path = HERE / 'bullet_metrics.jsonl'
with open(str(out_path) + '.tmp', 'w') as out:
    for cid in order:
        out.write(recs[cid][0] if recs[cid][0].endswith('\n') else recs[cid][0] + '\n')
os.replace(str(out_path) + '.tmp', out_path)

V = collections.Counter()
mx = collections.defaultdict(float)
mins = collections.defaultdict(lambda: math.inf)
sums = collections.defaultdict(float)
by_layer = collections.defaultdict(float)
dup_readouts = collections.Counter()
empties, drop_gt_solo, zero_coef_examples, worst = [], [], [], []
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
        V['readouts_diff_gt_1e-7'] += d > TOL
        worst.append((d, r['cell_id'], sid))
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
        if not any(b['dup'] for b in s['bullets']):
            mx['abs_coef_minus_saved_nondup'] = max(mx['abs_coef_minus_saved_nondup'], max(
                abs(b['coefficient'] - x) for b, x in zip(s['bullets'], si['coefficients'])))
        else:
            dup_readouts[sid] += 1
        for i, b in enumerate(s['bullets']):
            V['bullets'] += 1
            for k in ('solo_fve', 'loo_drop', 'shapley', 'coefficient'):
                x = b[k]
                if not math.isfinite(x):
                    V[f'nonfinite[{k}]'] += 1
                mins[k] = min(mins[k], x)
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
            if b['coefficient'] == 0.0 and not b['dup'] and len(zero_coef_examples) < 5:
                zero_coef_examples.append([r['cell_id'], sid, i, b['solo_fve'], b['loo_drop'], b['shapley']])

N = len(order)
means_pct = {kind: {sid: 100 * sums[(kind, sid)] / N for sid in SETTINGS} for kind in ('saved', 'recomputed')}
shards = {}
for L in LAYERS:
    s = json.load(open(HERE / f'metrics/summary.L{L}.json'))
    shards[f'L{L}'] = {'job': s['slurm_job_id'], 'host': s['host'], 'cells': s['cells'], 'vectors': s['vectors'],
                       'seconds': s['seconds'], 'peak_rss_gb': s['peak_rss_gb'],
                       'max_abs_recomputed_minus_saved': s['max'].get('abs_recomputed_minus_saved'),
                       'dup_by_vector_only': s['counts'].get('dup_by_vector_only', 0)}
checks = {
    'cells_1320': N == 1320 and lines == 1320,
    'readouts_3960': V['readouts'] == 3960,
    'bullets_match_map': {sid: V[f'bullets[{sid}]'] == EXPECTED_BULLETS[sid] for sid in SETTINGS},
    'mean_saved_fve_matches_report_2dp': {sid: round(means_pct['saved'][sid], 2) == EXPECTED_MEAN_PCT[sid]
                                          for sid in SETTINGS},
    'recomputed_within_1e-7_all': V['readouts_diff_gt_1e-7'] == 0,
    'shapley_efficiency_lt_1e-9': mx['abs_sum_shapley_minus_joint'] < 1e-9,
    'no_negative_metrics': all(V[f'below_-1e-9[{k}]'] == 0 for k in ('solo_fve', 'loo_drop', 'shapley', 'coefficient')),
    'no_nonfinite': not any(k.startswith('nonfinite') for k in V),
    'dup_readouts_match_map': {sid: dup_readouts[sid] == EXPECTED_DUP_READOUTS[sid] for sid in SETTINGS},
}
report = {
    'checks': checks,
    'lines': lines, 'readouts': V['readouts'], 'bullets': V['bullets'],
    'bullets_by_setting': {sid: V[f'bullets[{sid}]'] for sid in SETTINGS},
    'mean_fve_pct': means_pct, 'mean_fve_pct_expected': EXPECTED_MEAN_PCT,
    'mean_recomputed_fve_pct_by_layer': {sid: {L: round(100 * by_layer[(sid, L)] / 120, 3) for L in LAYERS}
                                         for sid in SETTINGS},
    'max': dict(mx), 'min': dict(mins),
    'counts': {k: v for k, v in V.items() if not k.startswith('bullets[')},
    'dup_readouts': dict(dup_readouts),
    'empty_readouts': empties,
    'worst_recomputed_vs_saved': [list(x) for x in sorted(worst, reverse=True)[:5]],
    'drop_gt_solo_examples': drop_gt_solo, 'zero_coef_nondup_examples': zero_coef_examples,
    'shards': shards,
}
(HERE / 'metrics_validation.json').write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
