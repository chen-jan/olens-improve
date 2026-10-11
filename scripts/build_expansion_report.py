"""Render the expanded research report from complete counts and reviewed prose.

No inference, new statistics, or automatic recommendation is performed here.
The reviewer binds every conclusion to the exact measured result artifact.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from build_expansion_dashboard import FAMILIES, ACTIVE, label, category, checked_artifact

TITLES = dict(zip(FAMILIES, (
    'Transcript contradictions', 'Hidden intermediate names', 'Intermediate numbers', 'Who did what')))
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
    comparisons = {(c['condition'], c['reference'], c['family']) for c in full['comparisons']}
    for group, finding in review.get('method_findings', {}).items():
        task_comparison = finding.get('task_comparison')
        if task_comparison is None:
            continue
        condition, reference = task_comparison.get('condition'), task_comparison.get('reference')
        notes = task_comparison.get('notes', {})
        if (condition not in active or reference not in active
                or category(active[condition]['method']) != group
                or set(notes) != set(FAMILIES)
                or any(not isinstance(note, str) or not note.strip() or len(note) > 450
                       for note in notes.values())
                or any((condition, reference, family) not in comparisons for family in FAMILIES)):
            raise ValueError('Task-specific notes require a complete, declared representative comparison')
    for (_, family), metric in metrics.items():
        endpoint = ('original_grid_contradiction_rate' if family == 'hallucination'
                    else 'original_grid_item_pass_rate')
        if metric['name'] != endpoint:
            raise ValueError('Final report received a per-activation endpoint')
        if metric['independent_groups'] != inventory['family_group_counts'][family]:
            raise ValueError('Related-group counts differ from the frozen bank')
    return results, inventory, review, active, metrics, {
        'results': results_sha, 'inventory': inventory_sha, 'review': review_sha}


def checked_reconstruction(path, inventory, review, active, hashes):
    """Optional secondary data must match this reviewed result and frozen reader."""
    top = review.get('reconstruction_sha256')
    presentation = review.get('presentation', {}).get('reconstruction_sha256')
    if top and presentation and top != presentation:
        raise ValueError('Conflicting reviewed reconstruction source hashes')
    authority = top or presentation
    if path is None:
        if authority:
            raise ValueError('Reviewed reconstruction artifact must be supplied')
        return None, None
    artifact, artifact_sha = checked_artifact(
        path, 'reconstruction', {**review, 'reconstruction_sha256': authority},
        inventory, hashes['inventory'], hashes['results'], set(active))

    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def fit(value):
        if value is not None and (not number(value) or value > 1):
            raise ValueError('Invalid reconstruction FVE')

    def bounds(values, difference=False):
        if values is not None and (not isinstance(values, list) or len(values) != 2
                                   or not all(number(v) for v in values) or values[0] > values[1]
                                   or (not difference and values[1] > 1)):
            raise ValueError('Invalid reconstruction interval')

    def pp_matches(row, raw_field, pp_field):
        if pp_field not in row:
            return
        raw = row.get(raw_field)
        expected = None if raw is None else [100 * v for v in raw] if isinstance(raw, list) else 100 * raw
        if row[pp_field] != expected:
            raise ValueError('Reconstruction percentage-point field differs from raw value')

    def sites(value):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError('Invalid reconstruction site count')

    for row in artifact['rows']:
        for field in ('full_site_count', 'scored_site_count'):
            sites(row[field])
        fit(row['mean_fve']); fit(row['median_fve'])
        bounds(row.get('mean_fve_ci95'))
        if row['scored_site_count'] == 0 and (row['mean_fve'] is not None or row.get('mean_fve_ci95') is not None):
            raise ValueError('Empty reconstruction coverage must have unavailable mean and interval')
        pp_matches(row, 'mean_fve', 'mean_fve_percentage_points')
        pp_matches(row, 'mean_fve_ci95', 'mean_fve_ci95_percentage_points')
        seen = set()
        for paired in row.get('parent_comparisons', []):
            key = paired['reference'], paired.get('kind')
            if key in seen:
                raise ValueError('Duplicate reconstruction parent comparison')
            seen.add(key)
            sites(paired['paired_sites'])
            if paired['paired_sites'] > row['scored_site_count']:
                raise ValueError('Paired reconstruction mask exceeds scored coverage')
            if paired['mean_delta'] is not None and not number(paired['mean_delta']):
                raise ValueError('Invalid reconstruction difference')
            bounds(paired.get('ci95_delta'), difference=True)
            if paired['paired_sites'] == 0 and (paired['mean_delta'] is not None or paired.get('ci95_delta') is not None):
                raise ValueError('Empty paired mask must have unavailable difference and interval')
            pp_matches(paired, 'mean_delta', 'mean_delta_percentage_points')
            pp_matches(paired, 'ci95_delta', 'ci95_delta_percentage_points')
    return artifact, artifact_sha


def fve_points(value, difference=False):
    if value is None:
        return 'Unavailable'
    return (f'{100 * value:+.2f}' if difference else f'{100 * value:.2f}') + (' pp' if difference else '%')


def fve_interval(values, difference=False):
    if values is None:
        return 'Unavailable'
    return f'[{100 * values[0]:+.2f}, {100 * values[1]:+.2f}]' + (' pp' if difference else '%')


def reconstruction_section(artifact, artifact_sha, source, review, active):
    if artifact is None:
        return []
    source_link = Path(source).name
    conditions = review.get('reconstruction_conditions',
                            review.get('presentation', {}).get('chart_conditions', list(active)))
    if (not isinstance(conditions, list) or not conditions or len(set(conditions)) != len(conditions)
            or any(c not in active for c in conditions)):
        raise ValueError('Reconstruction table must name distinct frozen active settings')
    rows = {(r['condition'], r['family']): r for r in artifact['rows']}
    lines = ['## Reconstruction fit: a separate secondary diagnostic', '',
             'Fraction of variance explained (FVE) measures how well the fixed reconstructor fits '
             'a recorded activation vector after the original layer-specific whitening and exact '
             'nonnegative joint fit. It measures fit at activation sites, while the quality tables '
             'retain their native question-grid or transcript endpoints. Fit gains do not establish '
             'semantic faithfulness. Negative FVE values remain valid.', '',
             'FVE means give equal weight to valid activation sites. Pointwise 95% intervals resample '
             'whole related-question groups with those site weights. Parent-relative differences use '
             'only sites valid for both outputs, so their masks can differ from the absolute means '
             'and the quality comparisons. Each recorded reference is named below. These post-hoc '
             'intervals are outside the 496 headline contrast adjustment.', '',
             'Absolute FVE values are percentages; changes are percentage points (pp). '
             'For example, a change from 25% to 27.5% is +2.5 pp. '
             'The reconstructor scores at most the first 32 cleaned tokens per bullet; '
             'longer suffixes remain in the readout without independent reconstruction verification. '
             'Recorded valid empty outputs can have zero fit; unavailable fits and empty paired masks '
             'remain unavailable. Zero bootstrap variation does not establish certainty.', '',
             '| Setting | Task | Mean FVE; grouped pointwise 95% interval | Valid sites / intended sites |',
             '|---|---|---|---:|']
    for condition in conditions:
        for family in FAMILIES:
            row = rows.get((condition, family))
            if row is None:
                lines.append(f'| {label(active[condition])} | {TITLES[family]} | Unavailable: no recorded fit row | Unavailable |')
                continue
            warnings = row.get('mean_fve_warnings', [])
            suffix = ' † ' + '; '.join(warnings) if warnings else ''
            lines.append(f"| {label(active[condition])} | {TITLES[family]} | "
                         f"{fve_points(row['mean_fve'])}; {fve_interval(row.get('mean_fve_ci95'))}{suffix} | "
                         f"{row['scored_site_count']:,} / {row['full_site_count']:,} |")
    lines += ['', '| Setting | Task | Recorded reconstruction reference | Comparison kind | Δ FVE; grouped paired pointwise 95% interval | Common valid sites / intended pairs | Related groups |',
              '|---|---|---|---|---|---:|---:|']
    for condition in conditions:
        for family in FAMILIES:
            row = rows.get((condition, family), {})
            parents = row.get('parent_comparisons', [])
            if not parents:
                lines.append(f'| {label(active[condition])} | {TITLES[family]} | No recorded reference | — | Unavailable | — | — |')
            for paired in parents:
                warning = ' † ' + paired['warning'] if paired.get('warning') else ''
                intended = paired.get('intended_paired_sites')
                coverage = f"{paired['paired_sites']:,} / {intended:,}" if intended is not None else f"{paired['paired_sites']:,} / unrecorded"
                lines.append(f"| {label(active[condition])} | {TITLES[family]} | {label(active[paired['reference']])} | "
                             f"{paired.get('kind', 'unrecorded')} | {fve_points(paired['mean_delta'], True)}; "
                             f"{fve_interval(paired.get('ci95_delta'), True)}{warning} | {coverage} | "
                             f"{paired.get('independent_groups', 'unrecorded')} |")
    lines += ['', 'The settings shown here follow the reviewed presentation order; they are not ranked by fit. '
              'All method/family rows, every recorded parent comparison, masks, warnings and source pins '
              f'are retained in the [complete numeric reconstruction data]({source_link}).', '',
              f'Reconstruction artifact SHA-256: `{artifact_sha}`.', '']
    return lines


def render(results, inventory, review, active, metrics, hashes, *, reconstruction=None,
           reconstruction_sha256=None, reconstruction_source=None):
    full = results['cohorts']['full']
    lines = [f"# {review.get('title', 'Oracle Lens: expanded inference-time comparison')}",
             '', review['headline'], '',
             f"**Scope:** {len(active)} output settings, all 469 questions, four WorkspaceBench task banks, "
             'and 19,435 fixed activation sites. Every new comparison is exploratory.', '']
    for finding in review['findings']:
        lines += [f"**{finding['title']}** {finding['detail']}", '']
    lines += ['## What was compared', '',
              'The target model, Oracle Lens and matched activation reconstructor remain frozen. '
              'Each method explains the same target vector at the same layer and token position; '
              'control-based scorers additionally use the recorded matched activations. '
              'The shared pool contains at most 32 original descriptions per vector. '
              'Final outputs have at most four bullets and 256 Qwen tokens; the released raw baseline '
              'is retained separately with its original output. Pooling keeps intact source bullets. '
              'Editing uses explicitly recorded Luna proposals and fresh reconstruction vectors.', '',
              'Transcript contradictions measure wrong specific readouts divided by all specific readouts, '
              'including off-topic readouts. Hidden intermediate names measure required intermediate entities; '
              'the final answer is optional. Intermediate numbers count only the judge’s first-ranked '
              'verified integer at a reading site; a required value appearing lower in the list does not '
              'count. Number and role recovery then aggregate over the complete original question grid. '
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
        task_comparison = body.get('task_comparison')
        if task_comparison:
            condition, reference = task_comparison['condition'], task_comparison['reference']
            lines += [f"Representative comparison: **{label(active[condition])}** versus "
                      f"**{label(active[reference])}**. These notes describe this setting, not every variant.", '',
                      '| Task | What changed |', '|---|---|']
            for family in FAMILIES:
                note = task_comparison['notes'][family].replace('|', '\\|').replace('\n', ' ')
                lines.append(f'| {TITLES[family]} | {note} |')
            lines.append('')
    lines += reconstruction_section(reconstruction, reconstruction_sha256, reconstruction_source,
                                    review, active)
    lines += ['## Uncertainty and interpretation', '',
              f"We resample whole related groups with {full['bootstrap_replicates']:,} shared draws "
              'within each task. Paired intervals compare the same groups across methods. '
              f"The fixed menu contains {full['declared_contrasts']} headline contrasts. "
              f"{full.get('effective_non_degenerate_contrasts', 'Unrecorded')} are defined and nondegenerate; "
              f"{full.get('joint_interval_contrasts', 'unrecorded')} receive simultaneous intervals. "
              'Simultaneous intervals use a centered, standardized bootstrap maximum over its '
              'defined, nondegenerate contrasts. These intervals provide approximate coverage. '
              'Undefined ratio draws and zero bootstrap variation receive explicit warnings; '
              'their simultaneous intervals remain unavailable. A zero-width absolute interval for all-zero '
              'or all-one recovery does not establish certainty.', '',
              'All 469 questions were inspected before this expansion. Adjustment addresses the declared '
              'comparisons; it does not undo prior outcome access or create fresh held-out evidence. The original test subset '
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
              '| Setting | Contradictions ↓ | Hidden intermediate names ↑ | Intermediate numbers ↑ | Roles ↑ |',
              '|---|---:|---:|---:|---:|']
    for condition, row in active.items():
        values = []
        for family in FAMILIES:
            metric = metrics[condition, family]
            warning = ' †' if metric.get('warnings') else ''
            value = ('No specific readouts' if family == 'hallucination' and metric['denominator'] == 0
                     else percentage(metric['value']))
            values.append(f"{value} ({interval(metric['ci95'])}){warning}")
        lines.append(f"| {label(row)} | " + ' | '.join(values) + ' |')
    flagged = [(condition, family, metric['warnings']) for (condition, family), metric in metrics.items()
               if metric.get('warnings')]
    if flagged:
        lines += ['', '† Bootstrap warnings for the marked absolute intervals:', '']
        for condition, family, warnings in flagged:
            lines.append(f"- {label(active[condition])}, {TITLES[family]}: {'; '.join(warnings)}.")
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
    parser.add_argument('--reconstruction', type=Path, help='Root-reviewed secondary fit artifact bound to these exact quality results')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs = checked_inputs(args.results, args.inventory, args.review)
    reconstruction, reconstruction_sha = checked_reconstruction(args.reconstruction, inputs[1], inputs[2],
                                                               inputs[3], inputs[5])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(*inputs, reconstruction=reconstruction,
                                  reconstruction_sha256=reconstruction_sha,
                                  reconstruction_source=args.reconstruction))
    print(json.dumps({'output': str(args.output), 'conditions': len(inputs[3]), 'inference_calls': 0}))


if __name__ == '__main__':
    main()
