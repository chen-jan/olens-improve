"""Refresh operational counters and attach only frozen, reviewed DEV pruning evidence."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

CHAIN_CONDITIONS = (
    'best_n_specificity_mean-n32',
    'best_n_specificity_mean_then_prune_0.005-n32',
    'best_n_specificity_mean_random_delete_matched_0.005-n32',
    'best_n_exact-n32', 'prune_loo_a32_0.005-n32',
    'random_delete_matched_a32_0.005-n32',
)


def pruning_evidence(bundle, source_path, source_sha):
    files = bundle['source_files']
    rows = []
    for condition in CHAIN_CONDITIONS:
        suffix = f'/{condition}/chain_intermediates/'
        sources = {}
        loaded = {}
        for name in ('results.json', 'project_contract.json'):
            matches = [p for p in files if p.endswith(suffix + name)]
            if len(matches) != 1:
                raise ValueError('Frozen condition source missing or ambiguous')
            path = matches[0]
            saved = files[path]
            raw = saved['source_bytes_utf8'].encode()
            if sha256(raw).hexdigest() != saved['sha256']:
                raise ValueError('Frozen embedded source hash mismatch')
            sources[path] = saved['sha256']
            loaded[name] = json.loads(raw)
        result, contract = loaded['results.json'], loaded['project_contract.json']
        counts, diagnostic = result['counts'], contract['cell_diagnostic']
        if (contract['partial_grid'] or contract['manifest_expected_cells'] != 330
                or contract['manifest_missing_cells'] or counts['n_missing_cells']
                or counts['n_unjudged_cells'] or diagnostic['api_or_missing_unjudged_cells']):
            raise ValueError('Pruning condition lacks complete frozen DEV coverage')
        if diagnostic['expected_cells'] != 330 or result['n_items'] != 30:
            raise ValueError('Chain cohort differs from frozen decision')
        items = result['numbers']['value'] * result['n_items']
        if abs(items - round(items)) > 1e-9:
            raise ValueError('Item ANY rate does not recover integer source count')
        rows.append({'condition': condition, 'passed_cells': diagnostic['passed_cells'],
                     'expected_cells': 330, 'passed_items': round(items), 'expected_items': 30,
                     'source_sha256': sources})
    return {'reviewed_by': 'root', 'rows': rows, 'independent_groups': 7,
            'scope': 'Frozen DEV chain decision evidence: complete original grids, 30 items / 330 cells; seven related template groups.',
            'source_path': str(source_path), 'source_sha256': source_sha,
            'limits': 'These are observed DEV losses, not a new held-out comparison. Mention recovery does not certify the calculation. No new interval is inferred.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--evidence-sha256', required=True)
    p.add_argument('--watcher', type=Path, required=True)
    p.add_argument('--selector-root', type=Path, required=True)
    p.add_argument('--sample-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    report = json.loads(a.report.read_text())
    raw = a.evidence.read_bytes()
    source_sha = sha256(raw).hexdigest()
    if source_sha != a.evidence_sha256:
        raise ValueError('Frozen DEV decision evidence changed')
    report['frozen_development_pruning'] = pruning_evidence(json.loads(raw), a.evidence, source_sha)
    watcher = json.loads(a.watcher.read_text())
    if watcher['budget']['status'] != 'observed_read_only':
        raise ValueError('Require observed campaign budget snapshot')
    report['api'].update(watcher['budget'])
    report['api']['observed_utc'] = watcher['checked_utc']
    report['api']['snapshot_path'] = str(a.watcher)
    report['api']['pricing_status'] = ('Usage-derived campaign estimate including cache writes; not invoice reconciled. '
        'Reserved totals include uncertain unknown holds. Shared research caches do not make fresh deployment free.')
    selectors = []
    for i in range(4):
        status_path = a.selector_root / f'shard-{i}' / 'status.json'
        status = json.loads(status_path.read_text())
        selectors.append({k: status[k] for k in ('status', 'completed_cells', 'expected_cells', 'seconds')})
    if sum(s['expected_cells'] for s in selectors) != 3485:
        raise ValueError('Unexpected validation selector cohort')
    sample_status = [json.loads(p.read_text()) for p in sorted(a.sample_root.glob('shard-*.status.json'))]
    if len(sample_status) != 4 or sum(s['expected_cells'] for s in sample_status) != 10714:
        raise ValueError('Require current blind TEST operational status cohort')
    # Keep only operational counters. Never load sample/selection text or quality.
    generation = [{k: s[k] for k in ('status', 'completed_cells', 'expected_cells')} for s in sample_status]
    now = datetime.now(timezone.utc)
    report['updated_utc'] = now.isoformat()
    selector_state = 'complete' if all(s['status'] == 'complete' for s in selectors) else 'running'
    generation_state = 'complete' if all(s['status'] == 'complete' for s in generation) else 'running'
    report['progress'].update(phase=f'Validation selection {selector_state}; VAL chain and multi-hop judging complete, hallucination and roles in progress; blind test generation {generation_state}',
        completed_cells=sum(s['completed_cells'] for s in selectors), expected_cells=3485,
        completed_label='VAL selector cells',
        elapsed_hours=(now - datetime(2026, 10, 10, 1, 25, 36, tzinfo=timezone.utc)).total_seconds()/3600)
    report['activity'] = {'checked_utc': now.isoformat(), 'validation_ar_status': 'complete',
        'validation_new_ar_vectors': 421716, 'shared_zero_copy_catalog_vectors': 1063925,
        'validation_selector_statuses': selectors, 'blind_test_generation_statuses': generation,
        'validation_judging_status': 'All four validation judge queues have launched. Chain and multi-hop judging are complete; hallucination and role judging are in progress. Remaining DEV judging stopped at clean family boundaries; incomplete comparisons are retained.',
        'quality_status': 'No validation or test quality outcomes reported. Only reviewed frozen DEV and pilot comparisons appear below.'}
    report['full_development_a32']['scope'] = ('121 DEV items / 5,236 cells, complete original grids. '
        'Separate from the 189-cell pilot; validation judging is underway; test outcomes remain sealed.')
    report['full_development']['method_comparison_status'] = ('The reviewed full-grid best-of-32 comparison leads this page. '
        'Frozen chain pruning losses appear separately. Remaining DEV judging stopped at clean family boundaries; incomplete comparisons are retained. '
        'Validation judging and blind test generation are shown as operational progress; no held-out quality results appear here.')
    a.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'output': str(a.output), 'api_snapshot_utc': watcher['checked_utc'],
                      'validation_selector_cells': report['progress']['completed_cells'],
                      'new_api_calls': 0, 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
