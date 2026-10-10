"""Pool complete reviewed stage counts; retain the separate held-out reports.

No inference, judging, cache access, ledger access or operating-point selection.
"""
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.reporting import (FAMILIES, digest, family_counts,
                                    original_grid_contract, original_grid_pairs,
                                    reporting_stage)
from olens_improve.evaluation import paired_group_interval

STAGES = ('development', 'validation', 'test')
UNITS = {'cell_recovery': 'passing cells / intended cells',
         'contradiction_rate': 'contradictory / specific readouts',
         'assertion_share': 'specific / intended readouts',
         'off_topic_rate': 'off-topic / specific readouts',
         'false_span_tally': 'false spans / intended output',
         'true_claim_tally': 'supported claims / intended output',
         'unverifiable_claims_per_output': 'unverifiable claims / intended output',
         'original_grid_contradiction_rate': 'contradictory / specific readouts',
         'original_grid_item_pass_rate': 'items with any passing site / intended items'}


def checked_json(ref):
    path = Path(ref['path'])
    if digest(path) != ref['sha256']:
        raise ValueError('Reviewed source bytes changed: ' + str(path))
    return json.loads(path.read_bytes())


def method_names(rows):
    names = [f"{r['method']}-n{r['n']}" for r in rows]
    if len(names) != 12 or len(set(names)) != 12:
        raise ValueError('Require the identical fixed twelve-method menu')
    return names


def stage_method_names(rows, canonical):
    names = method_names(rows)
    if set(names) != set(canonical):
        raise ValueError('Stage method identities differ from fixed menu')
    return names


def validate_union(manifests, expected):
    """Qualify items/groups by family, and reject related groups split by stage."""
    cells_seen, items_seen, groups, group_stage = set(), {}, {}, {}
    stage_counts = {}
    for stage in STAGES:
        rows = manifests[stage]['cells']
        local_items = set()
        if {c['family'] for c in rows} != set(FAMILIES):
            raise ValueError('Require all four families in every stage')
        for cell in rows:
            cid = cell['cell_id']
            item = (cell['family'], str(cell['item_id']))
            group = (cell['family'], str(cell['group_id']))
            if cell['split'] != stage or cid in cells_seen:
                raise ValueError('Duplicate/foreign stage cell')
            cells_seen.add(cid)
            if item in items_seen and items_seen[item] != stage:
                raise ValueError('Item is shared across stages')
            if item in groups and groups[item] != group:
                raise ValueError('Item has inconsistent related-group membership')
            if group in group_stage and group_stage[group] != stage:
                raise ValueError('Related group is split across stages')
            items_seen[item], groups[item], group_stage[group] = stage, group, stage
            local_items.add(item)
        stage_counts[stage] = {'items': len(local_items), 'cells': len(rows)}
    actual = {'items': len(items_seen), 'cells': len(cells_seen)}
    if actual != expected:
        raise ValueError('Whole-cohort item/cell union differs from reviewed plan')
    return groups, {'union': actual, 'stages': stage_counts}


def metric(pairs, groups):
    num, den = (sum(p[i] for p in pairs.values()) for i in (0, 1))
    zero = {item: (0, pair[1]) for item, pair in pairs.items()}
    interval = paired_group_interval(zero, pairs, groups)
    return {'numerator': num, 'denominator': den,
            'value': num / den if den else None,
            'ci95': interval['ci95_delta'],
            **{k: interval[k] for k in ('items', 'independent_groups', 'defined_draws', 'warning')}}


def pool_counts(counts, groups, names, comparison_pairs):
    """Ratio of source sums, never an average of stage rates or intervals."""
    conditions, comparisons = [], []
    for name in names:
        families = {}
        for family, endpoints in counts[name].items():
            if not endpoints.keys() <= UNITS.keys():
                raise ValueError('Unknown endpoint units')
            families[family] = {endpoint: metric(pairs, groups) | {'unit': UNITS[endpoint],
                'scope': 'original_grid' if endpoint.startswith('original_grid_') else 'cell'}
                for endpoint, pairs in endpoints.items()}
        conditions.append({'condition': name, 'measurement_complete': True, 'families': families})
    for baseline, proposed in comparison_pairs:
        if baseline not in names or proposed not in names or baseline == proposed:
            raise ValueError('Paired contrast is outside the fixed method menu')
        for family in FAMILIES:
            left, right = counts[baseline][family], counts[proposed][family]
            if left.keys() != right.keys():
                raise ValueError('Paired endpoint coverage differs')
            for endpoint in right:
                comparisons.append({'baseline_condition': baseline, 'condition': proposed,
                    'family': family, 'endpoint': endpoint,
                    'unit': UNITS[endpoint],
                    'scope': 'original_grid' if endpoint.startswith('original_grid_') else 'cell',
                    **paired_group_interval(left[endpoint], right[endpoint], groups)})
    return conditions, comparisons


def run(plan):
    # Check pending/reviewed inputs before opening any outcome artifact.
    if plan['status'] != 'root_reviewed_ready' or plan.get('reviewed_by') != 'root':
        raise ValueError('Pending descriptive inputs are not execution authority')
    if set(plan['stages']) != set(STAGES) or any(
            not plan['stages'][s].get('report') for s in STAGES):
        raise ValueError('Three complete reviewed stage reports are required')
    for path, expected_sha in plan.get('implementation_source_sha256', {}).items():
        if digest(path) != expected_sha:
            raise ValueError('Reviewed aggregation implementation changed')
    menu = checked_json(plan['menu'])
    names = method_names(menu)
    manifests, bindings, stage_names = {}, {}, {}
    # All existing stage capabilities precede all outcome reads.
    for stage in STAGES:
        binding = plan['stages'][stage]
        for key in ('manifest', 'conditions'):
            checked_json(binding[key])
        authority = binding.get('authority', {})
        for ref in authority.values():
            checked_json(ref)
        args = {key: ref['path'] for key, ref in authority.items()}
        frozen, actual_stage, _ = reporting_stage(binding['manifest']['path'],
            binding['conditions']['path'], **args)
        if actual_stage != stage or original_grid_contract(frozen, stage) is None:
            raise ValueError('Require the original authorized stage grids')
        stage_names[stage] = stage_method_names(checked_json(binding['conditions']), names)
        manifests[stage], bindings[stage] = frozen, binding
    groups, coverage = validate_union(manifests, plan['expected_union'])
    if plan.get('expected_stage_counts', coverage['stages']) != coverage['stages']:
        raise ValueError('Per-stage counts differ from reviewed union plan')
    counts = {name: {f: defaultdict(dict) for f in FAMILIES} for name in names}
    stage_refs, stage_lengths, coverage_by_condition = {}, {}, {}
    verified_hashes = {}
    for stage in STAGES:
        binding = bindings[stage]
        artifact = checked_json(binding['report'])
        measurement = artifact['measurement']
        if (measurement['manifest_sha256'] != binding['manifest']['sha256']
                or measurement['conditions_sha256'] != binding['conditions']['sha256']
                or not measurement.get('original_grid_contract')
                or [a['condition'] for a in measurement['conditions']] != stage_names[stage]):
            raise ValueError('Reviewed report differs from exact cohort/method order')
        stage_refs[stage] = binding['report']
        stage_lengths[stage] = artifact['lengths']
        for arm in measurement['conditions']:
            if not arm['measurement_complete'] or arm.get('errors') or set(arm['families']) != set(FAMILIES):
                raise ValueError('Missing stage/condition/family measurement')
            for path, expected_sha in arm['source_sha256'].items():
                if digest(path) != expected_sha:
                    raise ValueError('Validated result source changed')
                verified_hashes[path] = expected_sha
            root = Path(arm['condition_root']) / arm['condition']
            for family in FAMILIES:
                cell_rows = [r for r in manifests[stage]['cells'] if r['family'] == family]
                result_path = root / family / 'results.json'
                reads_path = root / f'{family}.readouts.jsonl'
                if str(result_path) not in verified_hashes or str(reads_path) not in verified_hashes:
                    raise ValueError('Outcome inputs lack reviewed source hashes')
                result = json.loads(result_path.read_bytes())
                reads = [json.loads(line) for line in reads_path.read_bytes().splitlines() if line.strip()]
                values, status = family_counts(family, cell_rows, reads, result)
                if status['missing_stage1'] or status['missing_stage2']:
                    raise ValueError('Missing intended outcome stage')
                values.update(original_grid_pairs(family, values, result))
                coverage_by_condition.setdefault(arm['condition'], {}).setdefault(stage, {})[family] = status
                for endpoint, pairs in values.items():
                    qualified = {(family, str(item)): pair for item, pair in pairs.items()}
                    destination = counts[arm['condition']][family][endpoint]
                    if destination.keys() & qualified.keys():
                        raise ValueError('Duplicate source item in pooled endpoint')
                    destination.update(qualified)
                length = stage_lengths[stage][arm['condition']][family]
                if length['outputs'] != len(cell_rows):
                    raise ValueError('Length coverage differs from intended cells')
                if length.get('empty_outputs', status['empty_abstentions']) != status['empty_abstentions']:
                    raise ValueError('Length abstentions differ from verified readouts')
                length['empty_outputs'] = status['empty_abstentions']
                for key in ('mean_qwen_tokens_all_intended', 'mean_bullets_all_intended'):
                    if not math.isfinite(length[key]) or length[key] < 0:
                        raise ValueError('Invalid reviewed output lengths')
    conditions, paired = pool_counts(counts, groups, names, plan['comparison_pairs'])
    lengths = {name: {family: {
        'outputs': sum(stage_lengths[s][name][family]['outputs'] for s in STAGES),
        'empty_outputs': sum(stage_lengths[s][name][family]['empty_outputs'] for s in STAGES),
        **{key: sum(stage_lengths[s][name][family][key] * stage_lengths[s][name][family]['outputs'] for s in STAGES)
                    / sum(stage_lengths[s][name][family]['outputs'] for s in STAGES)
           for key in ('mean_qwen_tokens_all_intended', 'mean_bullets_all_intended')}}
        for family in FAMILIES} for name in names}
    if any(digest(p) != sha for p, sha in verified_hashes.items()):
        raise ValueError('Source changed during descriptive aggregation')
    return {'status': 'complete_descriptive_whole_cohort', 'scope': 'descriptive DEV + VAL + TEST; TEST remains separately held out',
        'generated_utc': datetime.now(timezone.utc).isoformat(), 'stage_reports': stage_refs,
        'coverage': coverage, 'coverage_by_condition': coverage_by_condition,
        'conditions': conditions, 'paired_comparisons': paired, 'lengths': lengths,
        'stage_lengths': stage_lengths, 'source_sha256': verified_hashes,
        'bootstrap_replicates': 2000,
        'limits': ['Whole469 is descriptive, not469 held-out items; preserve separate stage reports.',
            'Related groups are family-qualified and resampled intact; intervals are unadjusted.',
            'Cells and items with any passing site are separate; neither establishes full-output truth.',
            'No hidden family average, winner selection, new trace sampling or cost numbers.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve prior reports; use a new immutable path')
    result = run(json.loads(args.plan.read_bytes()))
    result['plan'] = {'path': str(args.plan), 'sha256': digest(args.plan)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2); handle.write('\n')
    args.output.chmod(0o444)
    print(json.dumps({'path': str(args.output), 'sha256': digest(args.output)}))
