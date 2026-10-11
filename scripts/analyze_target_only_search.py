#!/usr/bin/env python3
"""Source-checked native endpoints and paired CIs for the additive search menu.

Reuses frozen original judgments verbatim. The simultaneous family contains
only the new inventory's declared contrasts crossed with the four native task
endpoints; historical70setting intervals remain untouched. Never calls an API.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics

from analyze_expansion import runtime_authority
from evaluate_target_only_search import IDENTITY, REFERENCE_IDS, authority, digest, load
from expanded_judges import expansion_cohort
from expanded_api import atomic_text
from olens_improve.expanded_statistics import analyze
from olens_improve.reporting import family_counts, original_grid_pairs
from verify_expansion_judge_contracts import verify_judge_contract

TITLES = {'hallucination': 'Hallucination (chat)', 'multihop_mt': 'Multihop (multi-token)',
          'chain_intermediates': 'Chained intermediates', 'role_bound_association': 'Role-bound association'}
EXPLANATIONS = {'hallucination': 'Verified contradiction / (contradiction + off-topic + consistent), from original source counts; both judging stages required.',
    'multihop_mt': 'Question passes if its required bridge concept is recovered at any prescribed site/layer, using released regex.',
    'chain_intermediates': 'Question passes if an accepted intermediate is recovered anywhere on its original final-token layer grid.',
    'role_bound_association': 'Question passes if the required entity-role association is recovered at any prescribed site/layer.'}


def lines(path):
    with Path(path).open() as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def selections(descriptor, wanted, cells):
    outputs = {condition: {} for condition in wanted}
    seen = set()
    for row in lines(descriptor['selections']):
        cid = row['cell_id']
        if cid in seen or cid not in cells or any(row.get(k) != cells[cid][k] for k in IDENTITY):
            raise ValueError('Selection output identity differs')
        seen.add(cid)
        for selection in row['selections']:
            key = f"{selection['method']}-n{selection['n']}"
            if key not in wanted:
                continue
            if cid in outputs[key]:
                raise ValueError('Duplicate condition selection')
            reduced = {k: selection[k] for k in ('text', 'token_count', 'bullet_count')}
            for field in ('fits', 'budget', 'stop_flags', 'elapsed_seconds', 'seconds',
                          'retained_loo', 'loo_contributions', 'leave_one_out', 'trace', 'selected_atom_keys'):
                if field in selection:
                    reduced[field] = selection[field]
            if not isinstance(reduced['text'], str) or any(type(reduced[k]) is not int or reduced[k] < 0 for k in ('token_count', 'bullet_count')):
                raise ValueError('Invalid output lengths')
            if key != 'raw_n1-n1' and (reduced['token_count'] > 256 or reduced['bullet_count'] > 4):
                raise ValueError('Selected output exceeds common caps')
            if key in ('repeat_swap_then_prune_005-n32', 'bounded_prune_refill_005-n32'):
                loo = reduced.get('leave_one_out')
                if not isinstance(loo, dict) or len(loo) != reduced['bullet_count'] or any(
                    type(gain) not in (int, float) or not math.isfinite(gain) or gain <= .005+1e-8 for gain in loo.values()):
                    raise ValueError('Guided output lacks strict retained per-bullet contribution evidence')
            outputs[key][cid] = reduced
    if seen != set(cells) or any(set(rows) != set(cells) for rows in outputs.values()):
        raise ValueError('Condition selection grid is incomplete')
    return outputs


def descriptor_index(directory, wanted, inventory_sha, pins):
    result = {}
    for path in sorted(Path(directory).glob('**/*.ready.json')):
        descriptor = load(path)
        own = {f"{r['method']}-n{r['n']}" for r in descriptor.get('conditions', [])} & set(wanted)
        if not own:
            continue
        if descriptor.get('ready') is not True or descriptor.get('inventory_sha256') != inventory_sha or descriptor.get('partial_grid'):
            raise ValueError('Unsealed ready descriptor')
        pins[str(path)] = digest(path)
        for field, hash_key in (('manifest', 'manifest_sha256'), ('selections', 'selection_sha256')):
            if digest(descriptor[field]) != descriptor[hash_key]:
                raise ValueError('Ready source changed')
            pins[descriptor[field]] = descriptor[hash_key]
        for condition in own:
            key = (condition, descriptor['family'])
            if key in result:
                raise ValueError('Duplicate condition/family ready descriptor')
            result[key] = descriptor
    return result


def aggregate_search_diagnostics(outputs):
    """Descriptive saved diagnostics only; never refit or invent unavailable fields.

    Preserve the exported field paths in the summary so the reported counts
    cannot be mistaken for another selector's fitted evaluations or timings.
    Numeric budget/timing fields aggregate separately from the fit objective.
    """
    values, flags = {}, {}
    def number(path, value):
        if type(value) in (int, float) and math.isfinite(value):
            values.setdefault(path, []).append(value)
    def walk(prefix, obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                walk(prefix+'.'+key, value)
        else:
            number(prefix, obj)
    for row in outputs.values():
        for field in ('fits', 'budget', 'elapsed_seconds', 'seconds'):
            if field in row:
                walk(field, row[field])
        for field in ('retained_loo', 'loo_contributions'):
            own = row.get(field)
            if isinstance(own, list):
                valid = [v for v in own if type(v) in (int, float) and math.isfinite(v)]
                if valid:
                    number(field+'.minimum_retained_per_output', min(valid))
        loo = row.get('leave_one_out')
        if isinstance(loo, dict) and loo:
            valid = [v for v in loo.values() if type(v) in (int, float) and math.isfinite(v)]
            if len(valid) != len(loo):
                raise ValueError('Invalid saved retained leave-one-out contribution')
            number('leave_one_out.minimum_retained_per_output', min(valid))
        own_flags = row.get('stop_flags', {})
        if isinstance(own_flags, dict):
            for key, value in own_flags.items():
                if type(value) is bool:
                    flags[key] = flags.get(key, 0)+int(value)
        elif isinstance(own_flags, list):
            for key in own_flags:
                if isinstance(key, str):
                    flags[key] = flags.get(key, 0)+1
    return {'intended_outputs': len(outputs), 'saved_numeric_fields': {
        key: {'observed_outputs': len(samples), 'mean': statistics.mean(samples),
              'median': statistics.median(samples), 'minimum': min(samples),
              'maximum': max(samples), 'sum': sum(samples)} for key, samples in values.items()},
        'stop_flag_counts': flags,
        'interpretation': 'Descriptive saved selector diagnostics; missing numeric fields remain unmeasured. Total across conditions may double-count reused fits and cannot establish physical CPU time.'}


def add_hallucination_diagnostics(metrics, result):
    """Preserve native counts and expose the source's disputed subset separately.

    The frozen stage-2 tally includes disputed claims within unverifiable claims;
    disputed is therefore not another mutually exclusive truth category.
    """
    metrics['wrong_among_wrong_or_consistent'] = {item: (
        pair[0], pair[1]-metrics['off_topic_rate'][item][0])
        for item, pair in metrics['contradiction_rate'].items()}
    metrics['off_topic_share_all_readouts'] = {item: (
        pair[0], metrics['assertion_share'][item][1])
        for item, pair in metrics['off_topic_rate'].items()}
    disputed = {item: 0 for item in metrics['assertion_share']}
    for row in result['rows']:
        verdicts = row.get('verdict')
        claims = verdicts[0].get('claims') if isinstance(verdicts, list) and len(verdicts) == 1 else None
        if claims is None:
            continue  # Explicit blank abstentions may have no stage-2 tally.
        value = claims.get('disputed') if isinstance(claims, dict) else None
        if type(value) is not int or value < 0 or value > claims['unverifiable']:
            raise ValueError('Invalid source disputed subset of unverifiable claims')
        disputed[str(row['id'])] += value
    metrics['disputed_claim_tally'] = {item: (
        disputed[item], pair[1]) for item, pair in metrics['assertion_share'].items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', required=True)
    parser.add_argument('--api-config', type=Path, default=Path('configs/target_only_api_v1.json'))
    parser.add_argument('--ready-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bootstrap-replicates', type=int)
    parser.add_argument('--seed', type=int)
    args = parser.parse_args()
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Run whole-bank bootstrap/extraction on allocated CPUs')
    if args.output.exists():
        raise FileExistsError('Preserve an existing analysis; choose a new version')
    inventory, config, new = authority(args)
    frozen_analysis = inventory['analysis']
    if frozen_analysis['status'] != 'frozen_before_new_judgments':
        raise ValueError('Analysis procedure must be frozen before judging')
    for field in ('bootstrap_replicates', 'seed'):
        supplied = getattr(args, field)
        if supplied is not None and supplied != frozen_analysis[field]:
            raise ValueError('Analysis CLI differs from its frozen inventory: '+field)
        setattr(args, field, frozen_analysis[field])
    pins = {str(args.inventory): args.inventory_sha256, str(args.api_config): digest(args.api_config)}
    runtime, runtime_pins = runtime_authority(Path(config['runtime_authority']))
    pins.update(runtime_pins)
    baseline_sha = config['baseline_inventory_sha256']
    if digest(config['baseline_inventory']) != baseline_sha:
        raise ValueError('Original frozen baseline inventory changed')
    pins[config['baseline_inventory']] = baseline_sha
    cells_path = inventory['fresh_manifest']['path']
    if digest(cells_path) != inventory['fresh_manifest']['sha256']:
        raise ValueError('Original capture manifest changed')
    pins[cells_path] = inventory['fresh_manifest']['sha256']
    all_cells = {c['cell_id']: c for c in load(cells_path)['cells']}
    baseline_index = descriptor_index(config['baseline_descriptor_snapshot'], REFERENCE_IDS, baseline_sha, pins)
    new_index = descriptor_index(args.ready_directory, new, args.inventory_sha256, pins)
    methods = {r['condition_id']: r for r in load(config['baseline_inventory'])['conditions'] if r['condition_id'] in REFERENCE_IDS} | new
    contrasts = inventory['headline_comparison_family']
    if not contrasts or any(c['condition'] not in new or c['reference'] not in methods for c in contrasts):
        raise ValueError('Simultaneous family must compare new methods to original/actual-parent references')
    if any(not any(p['condition'] == c and p['reference'] == 'raw_n1-n1' for p in contrasts) for c in new):
        raise ValueError('Every new method requires an explicit original-relative headline contrast')
    if any(not any(p['condition'] == c and p['reference'] == row['actual_parent'] for p in contrasts) for c, row in new.items()):
        raise ValueError('Every new method requires an explicit actual-parent headline contrast')
    families, lengths, secondary, complete = {}, {}, {}, []
    paired_lengths = []
    diagnostics = {}
    if digest(config['baseline_reconstruction']) != config['baseline_reconstruction_sha256']:
        raise ValueError('Frozen reconstruction supplement changed')
    pins[config['baseline_reconstruction']] = config['baseline_reconstruction_sha256']
    baseline_reconstruction = [r for r in load(config['baseline_reconstruction'])['rows'] if r['condition'] in REFERENCE_IDS]
    missing = []
    for family in inventory['families']:
        own = {cid: c for cid, c in all_cells.items() if c['family'] == family}
        family_cells = list(own.values())
        families[family] = {'conditions': {}, 'group_of': {c['item_id']: c['group_id'] for c in family_cells}}
        # Decode each source only once; large caches stay out of the analysis.
        decoded = {}
        paired_sources = {}
        for condition, method in methods.items():
            is_new = condition in new
            lookup = (condition, family)
            index = new_index if is_new else baseline_index
            if lookup not in index:
                missing.append({'condition': condition, 'family': family, 'reason': 'missing_ready_descriptor'})
                continue
            descriptor = index[lookup]
            if is_new:
                _manifest, descriptor_cells, _captures = expansion_cohort(descriptor['manifest'], inventory, args.inventory_sha256)
                if set(descriptor_cells) != set(own):
                    raise ValueError('New descriptor does not retain its original complete family')
            key = descriptor['selections']
            if key not in decoded:
                wanted = {c for c, f in index if f == family and index[(c, f)]['selections'] == key}
                decoded[key] = selections(descriptor, wanted, own)
            outputs = decoded[key][condition]
            paired_sources[condition] = outputs
            if is_new:
                diagnostics.setdefault(condition, {})[family] = aggregate_search_diagnostics(outputs)
            root = Path(config['output'] if is_new else config['baseline_judgments'])/condition
            paths = [root/f'{family}.summary.json', root/family/'results.json',
                     root/family/'project_contract.json', root/f'{family}.readouts.jsonl']
            if not all(path.exists() for path in paths):
                missing.append({'condition': condition, 'family': family, 'reason': 'judgment_not_terminal'})
                continue
            for path in paths:
                pins[str(path)] = digest(path)
            summary, result, contract = (load(path) for path in paths[:3])
            verify_judge_contract(family=family, method=method['method'], n=method['n'],
                expected_cells=len(own), inventory_sha256=args.inventory_sha256 if is_new else baseline_sha,
                descriptor=descriptor, summary=summary, result=result, contract=contract,
                approved_runtime_source_hashes=runtime)
            if contract['requested_service_tier'] != 'default':
                raise ValueError('Changed Standard judge instrument')
            readouts = list(lines(paths[3]))
            sites = {(c['item_id'], c['layer'], c['position']): cid for cid, c in own.items()}
            read_ids = set()
            for row in readouts:
                cid = sites[(str(row['id']), row['layer'], row['pos'])]
                if cid in read_ids or row['samples'] != [outputs[cid]['text']]:
                    raise ValueError('Judged text differs from saved selection')
                read_ids.add(cid)
            if read_ids != set(own):
                raise ValueError('Incomplete judged readout grid')
            metrics, coverage = family_counts(family, family_cells, readouts, result)
            if coverage['missing_stage1'] or coverage['missing_stage2']:
                missing.append({'condition': condition, 'family': family, 'reason': 'missing_judgments', 'coverage': coverage})
                continue
            original_grid_pairs(family, metrics, result)
            if family == 'hallucination':
                add_hallucination_diagnostics(metrics, result)
            primary = metrics['contradiction_rate'] if family == 'hallucination' else {
                item: (int(pair[0] > 0), 1) for item, pair in metrics['cell_recovery'].items()}
            families[family]['conditions'][condition] = primary
            lengths.setdefault(condition, {})[family] = {
                'outputs': len(outputs), 'empty_outputs': sum(not r['text'].strip() for r in outputs.values()),
                'mean_qwen_tokens_all_intended': statistics.mean(r['token_count'] for r in outputs.values()),
                'median_qwen_tokens_all_intended': statistics.median(r['token_count'] for r in outputs.values()),
                'mean_bullets_all_intended': statistics.mean(r['bullet_count'] for r in outputs.values())}
            secondary.setdefault(condition, {})[family] = {
                metric: {'numerator': sum(p[0] for p in pairs.values()), 'denominator': sum(p[1] for p in pairs.values())}
                for metric, pairs in metrics.items()} | {'coverage': coverage}
            complete.append({'condition': condition, 'family': family, 'coverage': coverage})
        for condition in new:
            for reference in methods:
                if condition == reference or condition not in paired_sources or reference not in paired_sources:
                    continue
                if reference not in REFERENCE_IDS and not any(p['condition'] == condition and p['reference'] == reference for p in contrasts):
                    continue
                left, right = paired_sources[reference], paired_sources[condition]
                paired_lengths.append({'family': family, 'condition': condition, 'reference': reference,
                    'cells': len(own), 'text_changed_cells': sum(left[cid]['text'] != right[cid]['text'] for cid in own),
                    'mean_qwen_token_delta': statistics.mean(right[cid]['token_count']-left[cid]['token_count'] for cid in own),
                    'mean_bullet_delta': statistics.mean(right[cid]['bullet_count']-left[cid]['bullet_count'] for cid in own),
                    'new_empty_cells': sum(not right[cid]['text'].strip() and bool(left[cid]['text'].strip()) for cid in own)})
    populated = {f: r for f, r in families.items() if r['conditions']}
    headline = analyze(populated, contrasts, replicates=args.bootstrap_replicates, seed=args.seed) if populated else None
    supplementary_pairs = [ {'condition': c, 'reference': r, 'comparison_scope': 'supplementary_pointwise'}
        for c in new for r in methods if r != c and r in REFERENCE_IDS
        and not any(p['condition'] == c and p['reference'] == r for p in contrasts)]
    supplementary = analyze(populated, supplementary_pairs, replicates=args.bootstrap_replicates,
                            seed=args.seed) if populated and supplementary_pairs else None
    if headline and len(populated) != 4:
        headline['comparison_family_complete'] = False
        headline['joint_critical_value'] = None
        for row in headline['comparisons']:
            row['simultaneous_ci95_delta'] = None
    if supplementary:
        for row in supplementary['comparisons']:
            row['simultaneous_ci95_delta'] = None
    for path, expected in pins.items():
        if digest(path) != expected:
            raise ValueError('Scientific source changed during extraction: '+path)
    payload = {'status': 'complete_exploratory' if not missing else 'partial_exploratory',
        'updated_utc': datetime.now(timezone.utc).isoformat(), 'inventory_sha256': args.inventory_sha256,
        'cohort': {'questions': 469, 'cells': 19435, 'all_previously_inspected': True},
        'task_titles': TITLES, 'endpoint_explanations': EXPLANATIONS,
        'original_reference': {'condition': 'raw_n1-n1', 'display_name': 'Original released Oracle Lens'},
        'headline': headline, 'supplementary_pointwise_comparisons': supplementary['comparisons'] if supplementary else [],
        'simultaneous_family': {'definition': 'Exactly declared original-relative and actual-parent contrasts for new methods, crossed with four native task endpoints.',
                               'declared_contrasts': 4*len(contrasts), 'pairs': contrasts},
        'lengths': lengths, 'paired_lengths': paired_lengths, 'secondary': secondary, 'complete_condition_families': complete,
        'search_diagnostics': diagnostics, 'baseline_reconstruction': baseline_reconstruction,
        'missing_condition_families': missing, 'source_sha256': pins,
        'implementation_sha256': {str(Path(__file__)): digest(__file__),
            'scripts/evaluate_target_only_search.py': digest('scripts/evaluate_target_only_search.py'),
            'src/olens_improve/expanded_statistics.py': digest('src/olens_improve/expanded_statistics.py'),
            'src/olens_improve/reporting.py': digest('src/olens_improve/reporting.py')},
        'inference_calls': 0,
        'limits': ['Exploratory on previously inspected full banks; no fresh held-out confirmation.',
                   'The new simultaneous family does not cover the historical70setting menu or adaptive experiment history.',
                   'Question/group bootstrap uses the original grouping; native endpoints remain separate.',
                   'Both hallucination stages required; unverifiable content is not treated as false.',
                   'Disputed claims are included within the source unverifiable tally and also reported separately; these are overlapping counts.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(args.output, json.dumps(payload, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'status': payload['status'], 'output': str(args.output), 'complete': len(complete), 'missing': len(missing)}))


if __name__ == '__main__':
    main()
