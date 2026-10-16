"""Concatenate per-layer shards into metrics/bullet_metrics.jsonl (input-file cell order) and validate.

Usage: python -B metrics_validate.py   (light: reads ~27 MB of shards + the 104 MB slim input)
Writes metrics/bullet_metrics.jsonl and logs/metrics_validation.json.
"""
import collections
import json
import math
import os
from pathlib import Path

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
LAYERS = (20, 36, 44, 52, 60)
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
EXPECTED_MEAN = {'capped_n1-n1': 0.370946, 'best_n_exact-n32': 0.425020, 'pooled_greedy_swap-n32': 0.450317}
EXPECTED_BULLETS = {'capped_n1-n1': 22441, 'best_n_exact-n32': 22449, 'pooled_greedy_swap-n32': 22427}
KNOWN_DUPS = {  # from DATAMAP_REPORT (10 readouts)
    ('chat-lmsys-0050|L60|p00077', 'best_n_exact-n32'), ('chat-lmsys-0007|L60|p00053', 'best_n_exact-n32'),
    ('chat-lmsys-0038|L36|p00189', 'best_n_exact-n32'), ('chat-lmsys-0007|L60|p00053', 'capped_n1-n1'),
    ('chat-lmsys-0007|L60|p00128', 'capped_n1-n1'), ('chat-lmsys-0038|L44|p00252', 'capped_n1-n1'),
    ('chat-lmsys-0038|L52|p00364', 'capped_n1-n1'), ('chat-lmsys-0042|L52|p00331', 'capped_n1-n1'),
    ('chat-lmsys-0046|L52|p00461', 'capped_n1-n1'), ('chat-lmsys-0056|L36|p00164', 'capped_n1-n1'),
}

recs = {}
for L in LAYERS:
    for line in open(ROOT / f'metrics/bullet_metrics.L{L}.jsonl'):
        r = json.loads(line)
        assert r['cell_id'] not in recs
        recs[r['cell_id']] = (line, r)
order, inp = [], {}
for line in open(ROOT / 'inputs/hall_three_settings.jsonl'):
    c = json.loads(line)
    order.append(c['cell_id'])
    inp[c['cell_id']] = c
assert set(order) == set(recs), 'cell set mismatch'

out_path = ROOT / 'metrics/bullet_metrics.jsonl'
with open(str(out_path) + '.tmp', 'w') as out:
    for cid in order:
        out.write(recs[cid][0] if recs[cid][0].endswith('\n') else recs[cid][0] + '\n')
os.replace(str(out_path) + '.tmp', out_path)

V = collections.Counter()
mx = collections.defaultdict(float)
mins = collections.defaultdict(lambda: math.inf)
sums = collections.defaultdict(float)
by_split = collections.defaultdict(float)
by_split_n = collections.Counter()
dups_found, empties = set(), []
drop_gt_solo, zero_coef_examples = [], []
lines = 0
for line in open(out_path):
    r = json.loads(line)
    lines += 1
    c = inp[r['cell_id']]
    for k in ('item_id', 'layer', 'position', 'split'):
        assert r[k] == c[k]
    assert set(r['settings']) == set(SETTINGS)
    for sid in SETTINGS:
        s, si = r['settings'][sid], c['settings'][sid]
        V['readouts'] += 1
        assert s['joint_fve_saved'] == si['fve']
        assert [b['phrase_id'] for b in s['bullets']] == si['phrase_ids']
        sums[('saved', sid)] += s['joint_fve_saved']
        sums[('recomputed', sid)] += s['joint_fve_recomputed']
        by_split[(sid, r['split'])] += s['joint_fve_recomputed']
        by_split_n[(sid, r['split'])] += 1
        mx['abs_recomputed_minus_saved'] = max(mx['abs_recomputed_minus_saved'],
                                               abs(s['joint_fve_recomputed'] - s['joint_fve_saved']))
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
        if any(b['dup'] for b in s['bullets']):
            dups_found.add((r['cell_id'].split('|', 1)[1], sid))
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
            # bounds implied by monotone v: drop <= shapley <= solo (pairwise-submodular case) and all <= joint
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
means = {kind: {sid: sums[(kind, sid)] / N for sid in SETTINGS} for kind in ('saved', 'recomputed')}
shards = {}
for L in LAYERS:
    s = json.load(open(ROOT / f'logs/metrics_summary.L{L}.json'))
    shards[f'L{L}'] = {'job': s['slurm_job_id'], 'host': s['host'], 'cells': s['cells'], 'seconds': s['seconds'],
                       'peak_rss_gb': s['peak_rss_gb']}
report = {
    'lines': lines, 'unique_cells': len(recs), 'readouts': V['readouts'], 'bullets': V['bullets'],
    'bullets_by_setting': {sid: V[f'bullets[{sid}]'] for sid in SETTINGS},
    'bullets_by_setting_expected': EXPECTED_BULLETS,
    'mean_fve': means, 'mean_fve_expected': EXPECTED_MEAN,
    'mean_fve_recomputed_minus_expected': {sid: means['recomputed'][sid] - EXPECTED_MEAN[sid] for sid in SETTINGS},
    'mean_recomputed_fve_by_split': {f'{sid}|{sp}': by_split[(sid, sp)] / by_split_n[(sid, sp)]
                                     for (sid, sp) in sorted(by_split)},
    'max': dict(mx), 'min': dict(mins),
    'counts': {k: v for k, v in V.items() if not k.startswith('bullets[')},
    'empty_readouts': empties,
    'dup_readouts_found': sorted(['|'.join(x) for x in dups_found]),
    'dup_readouts_match_datamap': dups_found == KNOWN_DUPS,
    'drop_gt_solo_examples': drop_gt_solo, 'zero_coef_nondup_examples': zero_coef_examples,
    'shards': shards,
}
(ROOT / 'logs/metrics_validation.json').write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
