"""Complete-grid A32 versus capped N1, with existing metrics and trace sampling."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.reporting import digest, summarize
from analyze_consensus_conditions import read_arm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--conditions', type=Path, required=True)
    parser.add_argument('--judgments', type=Path, required=True)
    parser.add_argument('--selections', type=Path, required=True)
    parser.add_argument('--selection-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or digest(args.selections) != args.selection_sha256:
        raise SystemExit('Use a new output and the exact frozen selections')
    conditions = json.loads(args.conditions.read_text())
    if {(row['method'], row['n']) for row in conditions} != {('capped_n1', 1), ('best_n_exact', 32)}:
        raise ValueError('This compact comparison requires exactly capped N1 and A32')
    measurement = summarize(args.manifest, args.conditions, args.judgments,
        selection_sha=args.selection_sha256)
    if not all(row['measurement_complete'] for row in measurement['conditions']):
        raise ValueError('All four families must be complete before reporting this comparison')
    cells = {row['cell_id']: row for row in json.loads(args.manifest.read_text())['cells']}
    examples, paired_cell_changes = {}, {}
    for family in sorted({row['family'] for row in cells.values()}):
        baseline = read_arm(args.judgments / 'capped_n1-n1', family, cells)
        proposed = read_arm(args.judgments / 'best_n_exact-n32', family, cells)
        buckets = defaultdict(list)
        for cid in sorted(proposed):
            b, p = baseline[cid], proposed[cid]
            if family == 'hallucination':
                category = ('wrong_to_consistent' if b['class']=='hallucinated' and p['class']=='consistent'
                    else 'consistent_to_wrong' if b['class']=='consistent' and p['class']=='hallucinated'
                    else 'wrong_to_offtopic' if b['class']=='hallucinated' and p['class']=='off_topic'
                    else 'wrong_to_empty' if b['class']=='hallucinated' and p['empty']
                    else 'unchanged' if b['class']==p['class'] else 'other_class_change')
            else:
                category = ('win' if p['pass'] and not b['pass'] else
                    'regression' if b['pass'] and not p['pass'] else 'unchanged')
            buckets[category].append({'cell_id':cid, 'item_id':cells[cid]['item_id'],
                'layer':cells[cid]['layer'], 'position':cells[cid]['position'],
                'baseline':b, 'proposed':p})
        sampled = {}
        for category, rows in buckets.items():
            if category == 'unchanged':
                sampled[category] = random.Random(20261010).sample(rows, min(3,len(rows)))
            else:
                chosen, seen_items = [], set()
                for row in rows:
                    if row['item_id'] not in seen_items:
                        chosen.append(row); seen_items.add(row['item_id'])
                    if len(chosen) == 3: break
                sampled[category] = chosen
        examples[family] = sampled
        paired_cell_changes[family] = {category:len(rows) for category,rows in buckets.items()}
    lengths = defaultdict(lambda: defaultdict(list))
    with args.selections.open() as handle:
        for line in handle:
            row = json.loads(line)
            for selection in row['selections']:
                if (selection['method'],selection['n']) in {('capped_n1',1),('best_n_exact',32)}:
                    key = selection['method']+'-n'+str(selection['n'])
                    lengths[key][row['family']].append({'token_count':selection['token_count'],
                        'bullet_count':selection['bullet_count']})
    length_summary = {arm:{family:{'outputs':len(rows),
        'mean_qwen_tokens_all_intended':statistics.mean(row['token_count'] for row in rows),
        'mean_bullets_all_intended':statistics.mean(row['bullet_count'] for row in rows)}
        for family,rows in values.items()} for arm,values in lengths.items()}
    result = {'status':'complete_four_family_development_comparison',
        'measurement':measurement, 'selection_source':str(args.selections),
        'selection_source_sha256':args.selection_sha256, 'lengths':length_summary,
        'paired_cell_change_counts':paired_cell_changes, 'examples':examples,
        'example_sampling':'First three distinct item IDs per changed category; three seeded unchanged cells; seed20261010',
        'limits':['A32 versus N1 combines more sampling and reconstruction selection; it does not isolate selection quality.',
            'All endpoints are exploratory development evidence, with unadjusted grouped intervals.',
            'Item ANY recovery differs from cell-level success and complete prose correctness.',
            'Hallucination counts transcript contradiction; other families measure separate recovery cohorts.',
            'False spans and true/unverifiable claims have different segmentation; they are not atomic precision.',
            'Qualitative traces are systematically sampled examples, not prevalence estimates or judge corrections.']}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    args.output.chmod(0o444)
    compact = {'output':str(args.output),'families':{},'paired':measurement['paired_comparisons'],
        'original_grid_paired':measurement['original_grid_paired_comparisons']}
    for arm in measurement['conditions']:
        compact['families'][arm['condition']] = {family:{'metrics':row['metrics'],
            'original_grid_metrics':row['original_grid_metrics']} for family,row in arm['families'].items()}
    print(json.dumps(compact,indent=2),flush=True)


if __name__ == '__main__':
    main()
