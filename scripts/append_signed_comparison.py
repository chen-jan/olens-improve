"""Attach an immutable signed-menu analysis after explicit coordinator review.

The review JSON binds stage, artifact/cohort/menu/selection/gate/freeze hashes,
ordered condition_ids, expected_family_counts ({cells,items,groups}), and
reviewed findings. Optional trace_refs name exact source examples. No inference,
new intervals, cost estimates, winner selection, or live result reads occur.
"""
import argparse
import copy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re

FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')
COST_SCOPES = ('new_input', 'campaign', 'cached_replay', 'benchmark_judging')


def cost_rows_checked(rows, names):
    """Validate reviewed quantities without deriving totals or latency."""
    if rows is None:
        return []
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows) or [r.get('condition') for r in rows] != names:
        raise ValueError('Cost rows must match the exact ordered method identities')
    for row in rows:
        components = row.get('components')
        if not isinstance(components, list) or not components or any(not isinstance(c, dict) for c in components):
            raise ValueError('Cost row requires components for all four scopes')
        if {c.get('scope') for c in components} != set(COST_SCOPES):
            raise ValueError('Cost row requires all four scopes, including explicit missing entries')
        seen = set()
        for component in components:
            for key in ('component', 'unit', 'basis'):
                if not isinstance(component.get(key), str) or not component[key].strip():
                    raise ValueError('Cost component requires name, unit and basis')
            identity = (component['scope'], component['component'], component['unit'])
            if identity in seen:
                raise ValueError('Duplicate cost component quantity')
            seen.add(identity)
            status, value = component.get('status'), component.get('value')
            if status not in ('measured', 'estimated', 'specified', 'missing'):
                raise ValueError('Unknown cost measurement status')
            if status == 'missing':
                if 'value' not in component or value is not None:
                    raise ValueError('Missing cost must have a null value')
                if component.get('source_refs') not in (None, []):
                    raise ValueError('Missing cost must not claim source quantities')
            else:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError('Cost quantity must be finite and nonnegative')
                refs = component.get('source_refs')
                if not isinstance(refs, list) or not refs:
                    raise ValueError('Nonmissing cost requires source evidence')
                for ref in refs:
                    if not isinstance(ref, dict) or any(not isinstance(ref.get(k), str) or not ref[k].strip() for k in ('path', 'field')):
                        raise ValueError('Cost evidence requires path and field')
                    if not Path(ref['path']).is_absolute():
                        raise ValueError('Cost source path must be absolute')
                    require_hash(ref.get('sha256'))
            if status == 'estimated' and (not isinstance(component.get('estimate_rule'), str) or not component['estimate_rule'].strip()):
                raise ValueError('Estimated cost requires an explicit estimate rule')
            if status == 'specified' and component['unit'] not in ('samples', 'calls', 'tokens', 'vectors', 'forward passes', 'refits'):
                raise ValueError('Specified status is for algorithmic workloads, not timing or monetary measurements')
            if component.get('note') is not None and not isinstance(component['note'], str):
                raise ValueError('Invalid cost limitation note')
    return copy.deepcopy(rows)


def verify_cost_source_bytes(rows):
    """Hash only reviewed references, after stage/cohort capability checks.

    This verifies byte identities, not the meaning of field locators, units,
    scaling assumptions or allocation of shared work; those remain reviewed.
    """
    seen = {}
    for row in rows:
        for component in row['components']:
            if component['status'] == 'missing':
                continue
            for ref in component['source_refs']:
                path = ref['path']
                if path not in seen:
                    digest = sha256()
                    with Path(path).open('rb') as source:
                        for chunk in iter(lambda: source.read(1024*1024), b''):
                            digest.update(chunk)
                    seen[path] = digest.hexdigest()
                if seen[path] != ref['sha256']:
                    raise ValueError('Cost source bytes differ from reviewed SHA')


def require_hash(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Require an exact SHA-256 identity')
    return value


def metric_checked(metric, expected):
    for key in ('numerator', 'denominator'):
        value = metric[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid metric counts')
    value = metric['numerator'] / metric['denominator'] if metric['denominator'] else None
    if metric['value'] != value:
        raise ValueError('Metric value differs from its numerator/denominator')
    if metric['items'] != expected['items'] or metric['independent_groups'] != expected['groups']:
        raise ValueError('Metric item/group cohort differs from reviewed counts')
    ci = metric.get('ci95')
    if ci is not None and (not isinstance(ci, list) or len(ci) != 2
            or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in ci)
            or ci[0] > ci[1]):
        raise ValueError('Invalid within-arm interval')
    if metric.get('warning') is not None and not isinstance(metric['warning'], str):
        raise ValueError('Invalid within-arm warning')
    return copy.deepcopy(metric)


def reviewed_identity(review, source_sha):
    """Check review capability before opening a held-out artifact."""
    stage = review.get('stage')
    if (review.get('status') != 'root_reviewed' or not review.get('reviewed_by')
            or not review.get('reviewed_utc') or stage not in ('validation', 'test')):
        raise ValueError('Require explicit reviewed held-out stage metadata')
    datetime.fromisoformat(review['reviewed_utc'].replace('Z', '+00:00'))
    if require_hash(source_sha) != review.get('artifact_sha256'):
        raise ValueError('Reviewed artifact SHA mismatch')
    if stage == 'test' and review.get('test_reveal_authorized') is not True:
        raise ValueError('Test attachment requires explicit reviewed reveal authorization')
    return stage


def comparison(artifact, review, source_path, source_sha, review_sha):
    stage = reviewed_identity(review, source_sha)
    m = artifact['measurement']
    if (artifact.get('status') != f'complete_four_family_{stage}_comparison'
            or m.get('stage') != stage or not m.get('original_grid_contract')):
        raise ValueError('Require complete signed original-grid stage analysis')
    auth = m['analysis_authorization']
    identities = {'manifest_sha256': m['manifest_sha256'], 'conditions_sha256': m['conditions_sha256'],
                  'selection_sha256': m['selection_sha256'],
                  'gate_sha256': auth['coordinator_gate_sha256'], 'freeze_sha256': auth['freeze_sha256']}
    if auth['split'] != stage or auth['condition_list_sha256'] != m['conditions_sha256']:
        raise ValueError('Analysis gate/menu stage mismatch')
    for key, actual in identities.items():
        if require_hash(actual) != review.get(key):
            raise ValueError(f'Reviewed {key} mismatch')
    if artifact['selection_source_sha256'] != m['selection_sha256']:
        raise ValueError('Selected-output identity differs from measurement')
    names = [a['condition'] for a in m['conditions']]
    if not names or len(set(names)) != len(names) or names != review.get('condition_ids'):
        raise ValueError('Condition menu differs from exact reviewed order')
    costs = cost_rows_checked(review.get('cost_rows'), names)
    expected = review['expected_family_counts']
    if set(expected) != set(FAMILIES):
        raise ValueError('Require reviewed counts for all four families')
    findings = review.get('findings')
    if (not isinstance(findings, list) or not 1 <= len(findings) <= 5
            or any(not f.get('claim') or not f.get('evidence') for f in findings)):
        raise ValueError('Require one to five root-authored findings with evidence')
    cell_rows, item_rows, auxiliary_rows, lengths = [], [], [], []
    arms = {a['condition']: a for a in m['conditions']}
    for name, arm in arms.items():
        if (not arm.get('measurement_complete') or arm.get('errors')
                or set(arm['families']) != set(FAMILIES)
                or name != f"{arm['method']}-n{arm['n']}"):
            raise ValueError('Incomplete, foreign, or misidentified condition')
        if set(artifact['lengths'].get(name, {})) != set(FAMILIES):
            raise ValueError('Missing output-length family')
        for family in FAMILIES:
            status, counts = arm['families'][family], expected[family]
            if any(isinstance(counts[k], bool) or not isinstance(counts[k], int) or counts[k] < 1
                   for k in ('cells', 'items', 'groups')):
                raise ValueError('Invalid reviewed cohort counts')
            if (status['expected_cells'] != counts['cells'] or status['missing_stage1']
                    or status['missing_stage2']):
                raise ValueError('Stage coverage is incomplete')
            key = 'contradiction_rate' if family == 'hallucination' else 'cell_recovery'
            cell = metric_checked(status['metrics'][key], counts)
            if (cell['numerator'] > cell['denominator'] or
                    (family != 'hallucination' and cell['denominator'] != counts['cells']) or cell['denominator'] > counts['cells']):
                raise ValueError('Cell denominator differs from cohort')
            cell_rows.append({'condition': name, 'family': family, 'metric': cell})
            original_endpoint = 'original_grid_contradiction_rate' if family == 'hallucination' else 'original_grid_item_pass_rate'
            if set(status['original_grid_metrics']) != {original_endpoint}:
                raise ValueError('Missing or unexpected original-grid endpoint')
            for endpoint, metric in status['original_grid_metrics'].items():
                checked = metric_checked(metric, counts)
                if family != 'hallucination' and (endpoint != 'original_grid_item_pass_rate'
                                                 or checked['denominator'] != counts['items']):
                    raise ValueError('Original item denominator differs from reviewed cohort')
                item_rows.append({'condition': name, 'family': family, 'endpoint': endpoint, 'metric': checked})
            for endpoint, metric in status['metrics'].items():
                if endpoint != key:
                    auxiliary_rows.append({'condition': name, 'family': family, 'endpoint': endpoint,
                                           'metric': metric_checked(metric, counts)})
            length = artifact['lengths'][name][family]
            if length['outputs'] != counts['cells']:
                raise ValueError('Length cohort differs from intended outputs')
            for key in ('mean_qwen_tokens_all_intended', 'mean_bullets_all_intended'):
                if (isinstance(length[key], bool) or not isinstance(length[key], (int, float))
                        or not math.isfinite(length[key]) or length[key] < 0):
                    raise ValueError('Invalid output length')
            lengths.append({'condition': name, 'family': family, **length})
    paired = []
    seen = set()
    for field, scope in (('paired_comparisons', 'cell'), ('original_grid_paired_comparisons', 'original_item')):
        for pair in m[field]:
            b, p, family, key = (pair[k] for k in ('baseline_condition', 'condition', 'family', 'endpoint'))
            identity = (scope, b, p, family, key)
            if b not in arms or p not in arms or family not in FAMILIES or identity in seen:
                raise ValueError('Foreign or duplicate paired contrast')
            seen.add(identity)
            metrics = 'metrics' if scope == 'cell' else 'original_grid_metrics'
            left, right = (arms[n]['families'][family][metrics][key]['value'] for n in (b, p))
            delta = right-left if left is not None and right is not None else None
            if pair['baseline'] != left or pair['proposed'] != right or pair['delta'] != delta:
                raise ValueError('Paired values differ from source endpoint')
            if pair['independent_groups'] != expected[family]['groups'] or pair['items'] != expected[family]['items']:
                raise ValueError('Paired group/item cohort differs from reviewed counts')
            ci = pair['ci95_delta']
            if ci is not None and (not isinstance(ci, list) or len(ci) != 2
                    or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in ci)
                    or ci[0] > ci[1]):
                raise ValueError('Invalid paired interval')
            paired.append({'scope': scope, **pair})
    selected_traces = []
    for ref in review.get('trace_refs', []):
        matches = [example for comparison in artifact['paired_traces']
                   if (comparison['baseline_condition'], comparison['condition']) == (ref['baseline_condition'], ref['condition'])
                   for example in comparison['families'][ref['family']]['examples'].get(ref['category'], [])
                   if example['cell_id'] == ref['cell_id']]
        if len(matches) != 1 or not ref.get('interpretation'):
            raise ValueError('Reviewed trace reference is missing, ambiguous, or unreviewed')
        row = matches[0]
        selected_traces.append({'cell_id': row['cell_id'], 'kind': ref['category'],
            'baseline': row['baseline']['text'], 'selected': row['proposed']['text'],
            'evidence': f"{ref['family']}: {ref['baseline_condition']} versus {ref['condition']}; immutable analysis {source_sha}",
            'interpretation': ref['interpretation']})
    return {'stage': stage, 'cohort': stage, 'title': f"Reviewed {stage} comparison: preselected methods",
        'review': copy.deepcopy(review), 'review_metadata_sha256': require_hash(review_sha),
        'source_path': str(source_path), 'source_sha256': source_sha,
        'identities': identities, 'condition_ids': names, 'family_counts': copy.deepcopy(expected),
        'cell_rows': cell_rows, 'original_item_rows': item_rows, 'auxiliary_rows': auxiliary_rows,
        'paired_rows': paired, 'length_rows': lengths, 'traces': selected_traces,
        'cost_rows': costs,
        'cost_source_verification': 'Root-reviewed references; source bytes have not been independently checked by this in-memory adapter.',
        'limits': artifact['limits'] + ['No combined score across task families or automatic winner is computed.',
            'Only source-provided paired contrasts are displayed; absent intervals remain missing.'],
        'cost_status': 'Timings and helper costs for new inputs in this comparison are not attached. Earlier pilot/DEV costs are separate cohorts; cached replay is not complete inference cost.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('report', 'artifact', 'review', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    review_raw = args.review.read_bytes()
    review = json.loads(review_raw)
    # Check reviewed identity before parsing any held-out artifact contents.
    if review.get('artifact_sha256') != require_hash(args.expected_sha256):
        raise ValueError('Review does not authorize the requested artifact')
    reviewed_identity(review, args.expected_sha256)
    raw = args.artifact.read_bytes()
    actual = sha256(raw).hexdigest()
    if actual != args.expected_sha256:
        raise ValueError('Artifact bytes differ from reviewed SHA')
    section = comparison(json.loads(raw), review, args.artifact, actual, sha256(review_raw).hexdigest())
    if section['cost_rows']:
        verify_cost_source_bytes(section['cost_rows'])
        section['cost_source_verification'] = 'Source byte SHA-256 identities verified after review and cohort checks. Field meanings, measurement scope and estimate rules remain root-reviewed claims.'
    report = json.loads(args.report.read_text())
    existing = report.setdefault('signed_comparisons', {})
    if section['stage'] in existing and existing[section['stage']]['source_sha256'] != actual:
        raise ValueError('Use a new report version to replace an attached immutable stage')
    existing[section['stage']] = section
    if section['stage'] == 'test':
        report['test_reveal_authorized'] = True
    report['updated_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'stage': section['stage'], 'source_sha256': actual,
                      'new_api_calls': 0, 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
