"""Attach actual frozen parents to unchanged qualitative cases; no inference."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from analyze_consensus_conditions import read_arm
from analyze_signed_menu import enrich_traces
from expanded_cpu_cached import atomic, sha


def parent_endpoint(parent, proposed, cid, cells, family):
    """Same-site hall classes or complete original-question recovery counts."""
    if family == 'hallucination':
        return {'unit': 'original_readout_site_class',
                'parent_class': parent[cid]['class'], 'proposed_class': proposed[cid]['class']}
    ids = sorted(k for k, cell in cells.items() if cell['item_id'] == cells[cid]['item_id'])
    before = [k for k in ids if parent[k]['pass']]
    after = [k for k in ids if proposed[k]['pass']]
    return {'unit': 'whole_original_question_grid', 'item_id': cells[cid]['item_id'],
            'grid_cells': len(ids), 'parent_item_pass': bool(before),
            'proposed_item_pass': bool(after), 'parent_passing_cells': len(before),
            'proposed_passing_cells': len(after), 'parent_first_passing_cell': next(iter(before), None),
            'proposed_first_passing_cell': next(iter(after), None),
            'selected_cell_parent_pass': parent[cid]['pass'],
            'selected_cell_proposed_pass': proposed[cid]['pass']}


def propagate_evidence(traces):
    retained = {}
    for trace in traces:
        for family, details in trace['families'].items():
            for records in details['examples'].values():
                for record in records:
                    for side, arm in [('baseline', trace['baseline_condition']), ('proposed', trace['condition'])]:
                        row = record[side]
                        if row['empty'] and row.get('evidence') is None:
                            row['evidence'] = {'evaluation_only': True, 'explicit_empty_abstention': True}
                        if row.get('evidence') is not None:
                            retained[arm, family, record['cell_id']] = row
    for trace in traces:
        for family, details in trace['families'].items():
            for records in details['examples'].values():
                for record in records:
                    for side, arm in [('baseline', trace['baseline_condition']), ('proposed', trace['condition'])]:
                        row = record[side]; source = retained[arm, family, record['cell_id']]
                        if any(row[k] != source[k] for k in ('text', 'empty', 'pass', 'class')):
                            raise ValueError('Conflicting duplicate identity')
                        row['evidence'] = source['evidence']
                        if 'evaluation_context' in source:
                            row['evaluation_context'] = source['evaluation_context']


def main():
    parser = argparse.ArgumentParser()
    for name in ('cases', 'analysis', 'judgments', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--cases-sha256', required=True)
    parser.add_argument('--analysis-sha256', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Allocated CPU required')
    if args.output.exists():
        raise FileExistsError('Use a new immutable parent pack')
    if sha(args.cases) != args.cases_sha256 or sha(args.analysis) != args.analysis_sha256:
        raise ValueError('Evidence pack or native analysis changed')
    source = json.loads(args.cases.read_text()); analysis = json.loads(args.analysis.read_text())
    pins = dict(source['source_sha256'])
    for path, value in analysis['source_sha256'].items():
        if path in pins and pins[path] != value:
            raise ValueError('Different hashes for shared immutable source')
        pins[path] = value
    pins[str(args.cases)] = args.cases_sha256; pins[str(args.analysis)] = args.analysis_sha256
    if any(sha(path) != value for path, value in pins.items()):
        raise ValueError('Pinned evidence changed')
    inventory_path = Path('configs/expansion_manifest_v1.json')
    if sha(inventory_path) != source['manifest_sha256'] or source['manifest_sha256'] != analysis['manifest_sha256']:
        raise ValueError('Expansion seal differs')
    inventory = json.loads(inventory_path.read_text())
    declared = {c['condition_id']: c['parent_condition_ids'] for c in inventory['conditions']}
    cells = {c['cell_id']: c for c in json.loads(Path(inventory['fresh_manifest']['path']).read_text())['cells']}
    completed = {(r['condition'], r['family']) for r in analysis['complete_condition_families']}
    grouped = {c: {'frozen_parent_condition_ids': declared[c], 'families': {}} for c in source['conditions']}
    traces = []; trace_lookup = {}; missing = []
    for family in inventory['families']:
        own = {cid: c for cid, c in cells.items() if c['family'] == family}
        arms = {}
        def arm(condition):
            if condition not in arms:
                arms[condition] = read_arm(args.judgments / condition, family, own)
            return arms[condition]
        for condition, entry in source['conditions'].items():
            if family not in entry['families']:
                continue
            if (condition, family) not in completed:
                raise ValueError('Selected condition absent from complete native analysis')
            result = {'fixed_anchor': [], 'outcome_selected': []}
            grouped[condition]['families'][family] = result
            proposed = arm(condition)
            for kind in ('fixed_anchor', 'outcome_selected'):
                for case in entry['families'][family][kind]:
                    cid = case['cell_id']
                    if any(case['proposed'][key] != proposed[cid][key] for key in ('text', 'empty', 'pass', 'class')):
                        raise ValueError('Chosen proposed case changed')
                    retained = {key: case[key] for key in ('cell_id', 'item_id', 'layer', 'position', 'category',
                        'endpoint_evidence', 'cell', 'context_ref', 'selection_policy')}
                    retained.update({'source_case_id': f'{condition}|{family}|{kind}|{case["category"]}|{cid}',
                        'original_baseline_condition': case['baseline_condition'],
                        'original_baseline': case['baseline'], 'proposed': case['proposed'], 'parents': {}})
                    result[kind].append(retained)
                    for parent in declared[condition]:
                        if (parent, family) not in completed:
                            retained['parents'][parent] = {'status': 'parent_family_not_complete'}
                            missing.append({'condition': condition, 'family': family, 'parent': parent})
                            continue
                        parent_rows = arm(parent)
                        key = condition, parent
                        if key not in trace_lookup:
                            trace_lookup[key] = {'condition': condition, 'baseline_condition': parent, 'families': {}}
                            traces.append(trace_lookup[key])
                        rows = trace_lookup[key]['families'].setdefault(family, {'examples': {'same_selected_cases': []}})
                        record = {'cell_id': cid, 'item_id': case['item_id'], 'layer': case['layer'],
                                  'position': case['position'], 'baseline': dict(parent_rows[cid]),
                                  'proposed': dict(proposed[cid])}
                        rows['examples']['same_selected_cases'].append(record)
                        retained['parents'][parent] = {'status': 'complete', 'output': record['baseline'],
                            'text_changed': parent_rows[cid]['text'] != proposed[cid]['text'],
                            'endpoint_evidence': parent_endpoint(parent_rows, proposed, cid, own, family)}
    names = sorted({arm for trace in traces for arm in (trace['condition'], trace['baseline_condition'])})
    pins.update(enrich_traces(traces, {'conditions': [{'condition': c, 'condition_root': str(args.judgments)} for c in names]}, cells))
    propagate_evidence(traces)
    if any(sha(path) != value for path, value in pins.items()):
        raise ValueError('Evidence source changed during extraction')
    missing_unique = list({(r['condition'], r['family'], r['parent']): r for r in missing}.values())
    output = {'status': 'prepared_pending_independent_parent_review',
        'updated_utc': datetime.now(timezone.utc).isoformat(), 'manifest_sha256': source['manifest_sha256'],
        'chosen_cases_sha256': args.cases_sha256, 'analysis_sha256': args.analysis_sha256,
        'contexts': source['contexts'], 'original_readouts': source['original_readouts'],
        'anchors': source['anchors'], 'conditions': grouped, 'missing_parent_families': missing_unique,
        'reviewer_partitions': source['reviewer_partitions'], 'source_sha256': pins,
        'implementation_sha256': {str(Path(__file__)): sha(__file__), 'scripts/analyze_signed_menu.py': sha('scripts/analyze_signed_menu.py')},
        'comparison_contract': {'parent_source': 'sealed parent_condition_ids',
            'case_selection': 'identical source cases; original capped-N1 category and endpoint retained',
            'parent_endpoint': 'separate same-site hall class or whole original question-grid recovery',
            'no_parent_conditions': 'empty parents is a frozen original condition, not missing evidence'},
        'limits': ['Parents are the frozen declared references; no extra inferred lineage is substituted.',
            'These cases were chosen against capped N1, not against each parent; they do not estimate parent-relative prevalence.',
            'Actual parent text and official evidence permit content comparisons, not causal mechanism conclusions.',
            'Required-bridge recovery does not establish complete final-answer correctness.',
            'No new calls, judge decisions, case choices or endpoint changes.']}
    args.output.parent.mkdir(parents=True, exist_ok=True); atomic(args.output, output)
    cases = [r for condition in grouped.values() for family in condition['families'].values() for rows in family.values() for r in rows]
    print(json.dumps({'output': str(args.output), 'sha256': sha(args.output), 'conditions': len(grouped),
        'cases': len(cases), 'parent_comparisons': sum(v['status'] == 'complete' for r in cases for v in r['parents'].values()),
        'missing_parent_families': len(missing_unique)}))


if __name__ == '__main__':
    main()
