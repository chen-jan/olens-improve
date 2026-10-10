"""Bind systematically selected DEV traces to retained upstream evidence; no calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.data import SOURCE_ROOT, item_id, load_bank, paths


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--judgments', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Preserve the existing supplement and use a new output')
    comparison, manifest = load(args.comparison), load(args.manifest)
    if manifest.get('split') not in ('dev', 'development'):
        raise ValueError('Only the frozen development cohort may be inspected')
    cells = {r['cell_id']: r for r in manifest['cells']}
    if any(r.get('split') not in ('dev', 'development') for r in cells.values()):
        raise ValueError('Heldout trace inspection is not authorized')
    upstream = SOURCE_ROOT / 'scratch/repos/workspace-bench-v2'
    sys.path.insert(0, str(upstream / 'src'))
    from wsbench.evals.role_bound_association.judge import build_block
    from wsbench.evals.chain_intermediates.judge import near_set, verdict
    banks = {f: load_bank(f) for f in ('role_bound_association', 'chain_intermediates')}
    bank_by_id = {f: {item_id(r): r for r in rows} for f, rows in banks.items()}
    sources, results, caches = {}, {}, {}
    for family in banks:
        sources[str(paths(family)['bank'])] = sha(paths(family)['bank'])
        for arm in ('capped_n1-n1', 'best_n_exact-n32'):
            directory = args.judgments / arm / family
            result_path, cache_path = directory / 'results.json', directory / 'cells.jsonl'
            sources[str(result_path)], sources[str(cache_path)] = sha(result_path), sha(cache_path)
            results[arm, family] = load(result_path)['rows']
            latest = {}
            for line in cache_path.read_text().splitlines():
                row = json.loads(line)
                if row.get('result') is not None:
                    latest[row['key']] = row
            caches[arm, family] = latest
    for family in banks:
        names = ('judge.py', 'prompts.py', 'score.py') if family == 'role_bound_association' else ('judge.py', 'prompts.py')
        for name in names:
            path = upstream / 'src/wsbench/evals' / family / name
            sources[str(path)] = sha(path)
    traces = []
    for family in banks:
        for category, selected in comparison['examples'][family].items():
            for sample in selected:
                ref = cells[sample['cell_id']]
                if any(sample[k] != ref[k] for k in ('item_id', 'layer', 'position')):
                    raise ValueError('Comparison trace is outside the frozen cohort')
                item = bank_by_id[family][sample['item_id']]
                trace = {'family': family, 'category': category, 'cell_id': sample['cell_id'],
                    'item_id': sample['item_id'], 'layer': sample['layer'],
                    'position': sample['position'], 'source_bank_item': item, 'arms': {}}
                if family == 'role_bound_association':
                    block, golds = build_block(item, banks[family])
                    trace['exact_upstream_mc_block'] = block
                    trace['gold_choice_indexes'] = list(golds)
                for label, arm in (('baseline', 'capped_n1-n1'), ('proposed', 'best_n_exact-n32')):
                    rows = results[arm, family]
                    if family == 'role_bound_association':
                        found = [r for r in rows if (r['id'], r['layer'], r['pos']) ==
                            (sample['item_id'], sample['layer'], sample['position'])]
                        if len(found) != 1:
                            raise ValueError('Role trace must resolve to one retained result')
                        scored = found[0]
                        raw = caches[arm, family][scored['key']]
                        if raw['meta']['golds'] != list(golds):
                            raise ValueError('Rendered question choices differ from the frozen verdict')
                        returned = [raw['result'][f'q{i}_choice'] for i in (1, 2, 3)]
                        if [v == g for v, g in zip(returned, golds)] != scored['correct']:
                            raise ValueError('Cached choices differ from the official scored result')
                    else:
                        found = [r for r in rows if r['id'] == sample['item_id']]
                        if len(found) != 1:
                            raise ValueError('Chain trace must resolve to one retained item result')
                        official, layer = found[0], str(sample['layer'])
                        scored = {k: official[k] for k in ('id', 'depth', 'intermediates', 'answer', 'start')}
                        scored.update({'layer': sample['layer'],
                            'named_values': official['named_by_layer'][layer],
                            'kind': official['kind_by_layer'][layer],
                            'basis': official['basis_by_layer'][layer]})
                        raw = caches[arm, family][f"{sample['item_id']}|L{sample['layer']:03d}"]
                        replay = verdict(raw['result'], item['intermediates'],
                            near_set(item['intermediates'], (item['start'], item['answer'])), sample[label]['text'])
                        if (replay['values'] != scored['named_values'] or replay['basis'] != scored['basis']
                                or replay['kind'] != scored['kind']):
                            raise ValueError('Cached chain extraction differs from the official scored layer')
                    trace['arms'][label] = {'condition': arm, 'text': sample[label]['text'],
                        'upstream_scored_result': scored, 'retained_raw_cache_record': raw}
                traces.append(trace)
    output = {'schema_version': 1, 'evaluation_only': True,
        'comparison_path': str(args.comparison), 'comparison_sha256': sha(args.comparison),
        'manifest_path': str(args.manifest), 'manifest_sha256': sha(args.manifest),
        'source_file_sha256': sources, 'trace_count': len(traces), 'traces': traces,
        'selection_rule': comparison['example_sampling'],
        'limits': ['No new model calls, judgment changes or selection feedback.',
            'Only already selected DEV examples are inspected; source labels are evaluation evidence.',
            'The exact upstream MC block uses the bank-wide frozen distractor recipe, including public labels.',
            'Correct-choice flags measure the official endpoint, not whole-output factual correctness.',
            'Systematically selected examples are qualitative evidence, not a prevalence estimate.']}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    args.output.chmod(0o444)
    print(json.dumps({'output': str(args.output), 'sha256': sha(args.output), 'traces': len(traces)}))


if __name__ == '__main__':
    main()
