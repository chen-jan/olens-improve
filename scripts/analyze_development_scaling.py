"""Report the completed, original DEV sample prefixes; no inference or judging."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.reporting import digest, summarize
from analyze_consensus_conditions import read_arm

PREFIXES = (1, 2, 4, 8, 16, 32)
ORDER = [('raw_n1', 1), ('capped_n1', 1)] + [('best_n_exact', n) for n in PREFIXES]


def validate_menu(rows):
    if [(r['method'], r['n']) for r in rows] != ORDER:
        raise ValueError('Require raw/capped N1 then the six exact original DEV prefixes')


def collect_lengths(path, cells, conditions, retained):
    """Check every literal output against its retained readout before summarizing."""
    lengths = defaultdict(lambda: defaultdict(list))
    seen = set()
    wanted = {f"{r['method']}-n{r['n']}" for r in conditions}
    with path.open() as handle:
        for line in handle:
            row = json.loads(line)
            cid = row['cell_id']
            if cid in seen or cid not in cells or row['family'] != cells[cid]['family']:
                raise ValueError('Selection source has duplicate, foreign or misidentified cells')
            seen.add(cid)
            available = {}
            for selection in row['selections']:
                key = f"{selection['method']}-n{selection['n']}"
                if key not in wanted:
                    continue
                if key in available:
                    raise ValueError('Duplicate method output')
                available[key] = selection
            if set(available) != wanted:
                raise ValueError('Selection source is missing a frozen prefix')
            for key, selection in available.items():
                if selection['text'] != retained[key][cid]['text']:
                    raise ValueError('Selected text differs from the exact judged readout')
                for field in ('token_count', 'bullet_count'):
                    value = selection[field]
                    if type(value) is not int or value < 0:
                        raise ValueError('Invalid output length')
                lengths[key][row['family']].append(selection)
    if seen != set(cells):
        raise ValueError('Selection source lacks intended cells')
    return {key: {family: {
        'outputs': len(rows), 'empty_outputs': sum(not r['text'].strip() for r in rows),
        'mean_qwen_tokens_all_intended': statistics.mean(r['token_count'] for r in rows),
        'mean_bullets_all_intended': statistics.mean(r['bullet_count'] for r in rows)
    } for family, rows in families.items()} for key, families in lengths.items()}


def run(args):
    if args.output.exists():
        raise FileExistsError('Use a new immutable report path')
    rows = json.loads(args.conditions.read_text())
    validate_menu(rows)
    if digest(args.selections) != args.selection_sha256:
        raise ValueError('Wrong frozen selection bytes')
    manifest = json.loads(args.manifest.read_text())
    cells = {r['cell_id']: r for r in manifest['cells']}
    if len(cells) != len(manifest['cells']) or any(r['split'] != 'development' for r in cells.values()):
        raise ValueError('This report permits only the original development cells')
    pairs = [(f'best_n_exact-n{a}', f'best_n_exact-n{b}') for a, b in zip(PREFIXES, PREFIXES[1:])]
    measurement = summarize(args.manifest, args.conditions, args.judgments,
                            selection_sha=args.selection_sha256, comparison_pairs=pairs)
    if not all(r['measurement_complete'] for r in measurement['conditions']):
        raise ValueError('All four families and both hall stages must be complete')
    if not measurement['original_grid_contract']:
        raise ValueError('Require verified complete original DEV grids')
    retained = {}
    for row in rows:
        key = f"{row['method']}-n{row['n']}"
        root = Path(row.get('condition_root', args.judgments)) / key
        retained[key] = {}
        for family in sorted({r['family'] for r in cells.values()}):
            retained[key].update(read_arm(root, family, cells))
    lengths = collect_lengths(args.selections, cells, rows, retained)
    engineering = json.loads(args.engineering.read_text())
    if engineering['scientific_results_eligible'] or engineering['API_calls'] != 0:
        raise ValueError('Expected the separate no-API engineering calibration')
    timers = {r['stage']: r['wall_seconds'] for r in engineering['measurements']}
    effort = {}
    for method, n in ORDER:
        key = f'{method}-n{n}'
        timer = f'cached_replay_prefix-{n}' if method == 'best_n_exact' else f'cached_replay_{method}'
        effort[key] = {
            'required_samples': {'status': 'specified', 'value': n},
            'AR_candidate_phrase_input_upper_bound': {'status': 'specified', 'value': 4*n if method == 'best_n_exact' else 0,
                'basis': 'At most four source bullets per sample; unique effective inputs may deduplicate. Raw/capped N1 do not run the reconstruction encoder.'},
            'runtime_helper_calls': {'status': 'specified', 'value': 0},
            'cached_engineering_replay_wall_seconds': {'status': 'measured', 'value': timers[timer],
                'source_field': f'measurements[stage={timer}].wall_seconds',
                'basis': 'Single synthetic input, existing N32 sample/vector cache; includes replay preparation/refits. Not a fresh-input latency or a DEV per-cell timing.'},
            'fresh_input_latency': {'status': 'missing', 'basis': 'No per-prefix new-input latency inferred by linear scaling. Separate N32 engineering lifecycle is retained below.'},
            'benchmark_Luna_cost': {'status': 'missing', 'basis': 'No new ledger/history scan; per-condition physical charges and retained unknown holds require a separate auditable accounting artifact.'}
        }
    report = {
        'status': 'complete_four_family_development_scaling', 'measurement': measurement,
        'selection_source': str(args.selections), 'selection_source_sha256': args.selection_sha256,
        'lengths': lengths, 'effort_by_condition': effort,
        'engineering_reference': {'path': str(args.engineering), 'sha256': digest(args.engineering),
            'cold_N32_lifecycle_through_first_selection_seconds': engineering['cold_pipeline_through_first_selection_seconds'],
            'basis': 'Separate synthetic engineering input, one H200, sequential O-lens/AR loads, capture and N32 generation. Not a benchmark average or measured fresh N1/N16 latency.',
            'timer_nesting': 'Warm capture/generation/AR and cached replay timers are components or separate invocations; do not sum nested timers into end-to-end cost.'},
        'implementation_source_sha256': {str(Path(__file__).resolve()): digest(Path(__file__)),
            str(Path(sys.modules['olens_improve.reporting'].__file__)): digest(sys.modules['olens_improve.reporting'].__file__)},
        'limits': ['Late DEV scaling is descriptive and cannot change the prospectively frozen TEST menu or selected operating points.',
            'Nested maximum reconstruction fit is nondecreasing by construction; explanation quality need not be.',
            'A1 eligibility differs from capped N1: invalid-AR atoms can yield explicit empty outputs. Preserve these denominators.',
            'Cell recovery and items with ANY passing site are distinct; neither establishes whole-output truth.',
            'Intervals use 2,000 paired related-group draws, without multiple-comparison correction. Chain has seven groups.',
            'Shared campaign sampling/cache work is incurred once, not once per arm; cache reuse is not free fresh inference.',
            'GPU dollar cost is unavailable; Luna benchmark judging is separate from deployment inference.']}
    if digest(args.selections) != args.selection_sha256:
        raise ValueError('Frozen selection source changed')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    args.output.chmod(0o444)
    print(json.dumps({'path': str(args.output), 'sha256': digest(args.output),
                      'conditions': len(rows), 'cells': len(cells), 'complete': True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'conditions', 'judgments', 'selections', 'engineering', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--selection-sha256', required=True)
    run(parser.parse_args())
