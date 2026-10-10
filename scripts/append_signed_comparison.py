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
