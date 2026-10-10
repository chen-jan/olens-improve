"""Analyze completed MT arms only; no API calls or cross-family conclusions."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.evaluation import paired_group_interval
from analyze_consensus_conditions import read_arm, aggregate


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--conditions', type=Path, required=True)
    parser.add_argument('--judgments', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Preserve previous analysis; use a new output version')
    manifest = json.loads(args.manifest.read_text())
    cells = {row['cell_id']: row for row in manifest['cells']}
    groups = {row['item_id']:row['group_id'] for row in cells.values() if row['family']=='multihop_mt'}
    methods = json.loads(args.conditions.read_text())
    outcomes, sources, item_outcomes = {}, {}, {}
    for method in methods:
        name = f"{method['method']}-n{method['n']}"
        root = args.judgments / name
        condition = json.loads((root / 'condition.json').read_text())
        if condition['manifest_sha256'] != sha(args.manifest) or condition['partial_grid']:
            raise ValueError('Expected identical complete frozen grid')
        events = [json.loads(line) for line in (root / 'multihop_mt.execution.jsonl').read_text().splitlines()]
        if events[-1]['status'] != 'completed':
            raise ValueError('Incomplete arm cannot enter a completed comparison')
        rows = read_arm(root, 'multihop_mt', cells)
        results = json.loads((root / 'multihop_mt/results.json').read_text())
        item_hits = {row['id']:(int(row['pass']),1) for row in results['rows']}
        by_item = defaultdict(list)
        for cid, row in rows.items():
            by_item[cells[cid]['item_id']].append(row['pass'])
        if item_hits != {item:(int(any(hits)),1) for item,hits in by_item.items()}:
            raise ValueError('Upstream any-site result does not match complete-cell outcomes')
        outcomes[name] = rows
        item_outcomes[name] = item_hits
        sources[name] = {'condition_path':str(root / 'condition.json'),
            'condition_sha256':sha(root / 'condition.json'),
            'selection_sha256':condition['selection_sha256'],
            'results_path':str(root / 'multihop_mt/results.json'),
            'results_sha256':sha(root / 'multihop_mt/results.json'),
            'contract_sha256':sha(root / 'multihop_mt/project_contract.json'),
            'upstream_complete_preserved':results['complete']}
    baseline_name = 'capped_n1-n1'
    baseline = outcomes[baseline_name]
    summaries = {}
    for name, rows in outcomes.items():
        buckets = defaultdict(list)
        for cid in sorted(rows):
            b,p = baseline[cid], rows[cid]
            kind = ('win' if p['pass'] and not b['pass'] else
                'regression' if b['pass'] and not p['pass'] else 'unchanged')
            buckets[kind].append({'cell_id':cid, 'baseline':b, 'proposed':p})
        examples = {key:(random.Random(20261010).sample(value,min(2,len(value)))
            if key=='unchanged' else value[:2]) for key,value in buckets.items()}
        summaries[name] = {'passed_cells':sum(row['pass'] for row in rows.values()),
            'intended_cells':len(rows), 'empty_outputs':sum(row['empty'] for row in rows.values()),
            'passing_any_site_items':sum(value[0] for value in item_outcomes[name].values()),
            'intended_items':len(item_outcomes[name]),
            'paired_cell_ratio_vs_capped_N1':paired_group_interval(
                aggregate(baseline,'multihop_mt'),aggregate(rows,'multihop_mt'),groups),
            'paired_item_ANY_vs_capped_N1':paired_group_interval(
                item_outcomes[baseline_name],item_outcomes[name],groups),
            'examples_vs_capped_N1':examples}
    component_pairs = [
        ('pooled_greedy_swap-n16','best_n_exact-n16'),
        ('pooled_greedy_swap-n32','best_n_exact-n32'),
        ('best_n_exact-n32','random_complete-n32'),
        ('best_n_specificity_mean-n32','best_n_exact-n32'),
        ('best_n_specificity_mean_then_prune_0.005-n32','best_n_specificity_mean-n32'),
        ('best_n_specificity_mean_then_prune_0.005-n32','best_n_specificity_mean_random_delete_matched_0.005-n32')]
    paired = {}
    for proposed, parent in component_pairs:
        paired[f'{proposed} vs {parent}'] = {
            'paired_cell_ratio':paired_group_interval(aggregate(outcomes[parent],'multihop_mt'),
                aggregate(outcomes[proposed],'multihop_mt'),groups),
            'paired_item_ANY':paired_group_interval(item_outcomes[parent],item_outcomes[proposed],groups)}
    artifact = {'status':'complete_MT_family_only_development',
        'manifest_sha256':sha(args.manifest), 'conditions_sha256':sha(args.conditions),
        'family':'multihop_mt', 'intended_items':len(groups), 'independent_groups':len(set(groups.values())),
        'conditions':summaries, 'component_comparisons':paired, 'sources':sources,
        'limits':['All24 exploratory development arms share the same candidate pool.',
            'The endpoint is the frozen required bridge-alias regex, not verified factual relations or complete prose correctness.',
            'Item ANY passing site differs from cell-level recovery; both are reported.',
            'Intervals resample related groups; multiple arm comparisons are exploratory and unadjusted.',
            'Other families are incomplete during a transport pause; no cross-family winner or validation decision is established.',
            'Examples are deterministic first2 gains/regressions and seeded unchanged cases, not prevalence estimates.']}
    with args.output.open('x') as handle:
        json.dump(artifact,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    print(json.dumps({'output':str(args.output), 'items':len(groups),
        'groups':len(set(groups.values())), 'component_comparisons':paired},indent=2))


if __name__ == '__main__':
    main()
