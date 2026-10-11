"""Render the expanded research report from complete counts and reviewed prose.

No inference, new statistics, or automatic recommendation is performed here.
The reviewer binds every conclusion to the exact measured result artifact.
"""
import argparse
import hashlib
import json
from pathlib import Path

from build_expansion_dashboard import FAMILIES, ACTIVE, label, category

TITLES = dict(zip(FAMILIES, (
    'Transcript contradictions', 'Hidden names', 'Arithmetic steps', 'Who did what')))
GROUPS = {
    'selection': 'Choosing a complete readout',
    'consensus': 'Keeping repeated statements',
    'pruning': 'Removing weak bullets',
    'pooling': 'Combining original bullets',
    'verification': 'Comparing activation evidence',
    'editing': 'Editing a readout',
    'combinations': 'Combining approaches',
}


def read(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def percentage(value):
    return 'Undefined' if value is None else f'{100 * value:.1f}%'


def interval(values, *, difference=False):
    if values is None:
        return 'Unavailable'
    suffix = ' points' if difference else '%'
    return f'{100 * values[0]:.1f} to {100 * values[1]:.1f}{suffix}'


def checked_inputs(results_path, inventory_path, review_path):
    results, results_sha = read(results_path)
    inventory, inventory_sha = read(inventory_path)
    review, review_sha = read(review_path)
    if results['manifest_sha256'] != inventory_sha or review['manifest_sha256'] != inventory_sha:
        raise ValueError('Different method inventories')
    if review.get('status') != 'root_reviewed' or review.get('results_sha256') != results_sha:
        raise ValueError('Prose has not been reviewed against these exact results')
    active = {row['condition_id']: row for row in inventory['conditions'] if row['status'] in ACTIVE}
    full = results['cohorts']['full']
    metrics = {(row['condition'], row['family']): row['metric'] for row in full['rows']}
    expected = {(condition, family) for condition in active for family in FAMILIES}
    if len(metrics) != len(full['rows']) or set(metrics) != expected:
        raise ValueError('A final report requires every active condition and task')
    if results['missing_condition_families'] or not full['comparison_family_complete']:
        raise ValueError('The full question grids and contrast menu must be complete')
    for (_, family), metric in metrics.items():
        endpoint = ('original_grid_contradiction_rate' if family == 'hallucination'
                    else 'original_grid_item_pass_rate')
        if metric['name'] != endpoint:
            raise ValueError('Final report received a per-activation endpoint')
        if metric['independent_groups'] != inventory['family_group_counts'][family]:
            raise ValueError('Related-group counts differ from the frozen bank')
    return results, inventory, review, active, metrics, {
        'results': results_sha, 'inventory': inventory_sha, 'review': review_sha}


def render(results, inventory, review, active, metrics, hashes):
    full = results['cohorts']['full']
    lines = [f"# {review.get('title', 'Oracle Lens: expanded inference-time comparison')}",
             '', review['headline'], '',
             f"**Scope:** {len(active)} output settings, all 469 questions, four WorkspaceBench task banks, "
             'and 19,435 fixed activation sites. Every new comparison is exploratory.', '']
    for finding in review['findings']:
        lines += [f"**{finding['title']}** {finding['detail']}", '']
    lines += ['## What was compared', '',
              'The target model, Oracle Lens and matched activation reconstructor remain frozen. '
              'Each method reads the same single vector at the same layer and token position. '
              'The shared pool contains at most 32 original descriptions per vector. '
              'Final outputs have at most four bullets and 256 Qwen tokens; the released raw baseline '
              'is retained separately with its original output. Pooling keeps intact source bullets. '
              'Editing uses explicitly recorded Luna proposals and fresh reconstruction vectors.', '',
              'Transcript contradictions measure wrong specific readouts divided by all specific readouts, '
              'including off-topic readouts. The other tasks measure whether the required name, intermediate '
              'number, or role bindings appear at any site in the complete original question grid. '
              'Recovering that content can coexist with incorrect surrounding prose. '
              'We keep the four endpoints separate.', '',
              '| Task | Questions | Related groups | Better direction |',
              '|---|---:|---:|---|']
    for family, count in zip(FAMILIES, (149, 100, 120, 100)):
        lines.append(f"| {TITLES[family]} | {count} | {inventory['family_group_counts'][family]} | "
                     f"{'Lower' if family == 'hallucination' else 'Higher'} |")
    lines += ['', '## Findings by approach', '']
    for group, title in GROUPS.items():
        body = review['method_findings'][group]
        lines += [f'### {title}', '', body['finding'], '', body['limits'], '']
    lines += ['## Uncertainty and interpretation', '',
              f"We resample whole related groups with {full['bootstrap_replicates']:,} shared draws "
              'within each task. Paired intervals compare the same groups across methods. '
              f"Simultaneous intervals cover the fixed menu of {full['declared_contrasts']} headline contrasts "
              'using a centered, standardized bootstrap maximum. These intervals provide approximate '
              'coverage. Zero bootstrap variation receives an explicit warning rather than a certainty claim.', '',
              'All 469 questions were inspected before this expansion. Multiplicity adjustment accounts '
              'for the declared comparisons and preserves this adaptive history. The original test subset '
              'is now a descriptive subcohort; the earlier frozen test report is preserved separately. '
              'Adding methods or activation sites does not increase the number of independent questions. '
              'An overlapping interval is not a reason to discard an otherwise useful method.', '',
              '## Practical recommendations', '']
    for recommendation in review['recommendations']:
        lines += [f'- {recommendation}', '']
    lines += ['## Effort and retained data', '', review['resource_summary'], '',
              'Selection from a saved pool is cheaper than creating that pool for a new activation. '
              'Helpers, new likelihood scoring and edited-text reconstruction add separate work. '
              'The dashboard reports actual output lengths and component effort. '
              'The natural-length comparisons estimate practical method performance; they do not isolate '
              'a benefit independent of output length.', '',
              '## Complete result table', '',
              'Each entry gives the native percentage followed by its grouped 95% interval. '
              'Exact numerators, denominators, paired intervals, simultaneous intervals and '
              'secondary coverage measures are available in the accompanying data export.', '',
              '| Setting | Contradictions ↓ | Hidden names ↑ | Arithmetic ↑ | Roles ↑ |',
              '|---|---:|---:|---:|---:|']
    for condition, row in active.items():
        values = []
        for family in FAMILIES:
            metric = metrics[condition, family]
            values.append(f"{percentage(metric['value'])} ({interval(metric['ci95'])})")
        lines.append(f"| {label(row)} | " + ' | '.join(values) + ' |')
    lines += ['', '## Scope and reproducibility', '',
              'Independent-reader extensions, including J++, NLA and another reconstructor, remain '
              'postponed. Malformed historical semantic conditions, exact aliases and unjudged '
              'numerical diagnostics remain documented separately. The finite inventory records those '
              'states; absence from the usable menu is not an adverse benchmark result.', '',
              '- Benchmark: [WorkspaceBench](https://github.com/camilablank/workspace-bench), '
              'revision `92d763e722377f5bfae045e829a308ab5919a820`.',
              '- Model: [Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B), '
              'revision `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`.',
              '- Matched reader and reconstructor: [released Oracle Lens pair]'
              '(https://huggingface.co/agu18dec/olens_and_ar), revision '
              '`c95215d5d2f6250f20c305ae55c6e4d7569f92dc`.',
              '- GPT-6 Luna supplies the benchmark judgments; hidden-name matching uses '
              'the released deterministic rule. Helpers use separate recorded prompts.', '',
              f"Result source SHA-256: `{hashes['results']}`.  ",
              f"Frozen inventory SHA-256: `{hashes['inventory']}`.  ",
              f"Reviewed interpretation SHA-256: `{hashes['review']}`.", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, default=Path('configs/expansion_manifest_v1.json'))
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs = checked_inputs(args.results, args.inventory, args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(*inputs))
    print(json.dumps({'output': str(args.output), 'conditions': len(inputs[3]), 'inference_calls': 0}))


if __name__ == '__main__':
    main()
