#!/usr/bin/env python3
"""Export a small immutable target-only case pack from complete pinned evidence.

No inference, refitting, judging, or qualitative conclusions. Full-bank source
verification/extraction must run on allocated CPUs. Reviewer prose comes later.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.data import item_id, load_bank, paths
from analyze_consensus_conditions import read_arm
from analyze_signed_menu import enrich_traces
from build_expansion_parent_qualitative import parent_endpoint, propagate_evidence
from expanded_cpu_cached import atomic, sha

REFERENCE_IDS = ('raw_n1-n1', 'capped_n1-n1', 'best_n_exact-n32',
    'pooled_greedy_swap-n32', 'pooled_greedy_swap_then_prune_0.005-n32',
    'pooled_greedy_swap_random_delete_matched_0.005-n32')
TITLES = {'hallucination': 'Hallucination (chat)', 'multihop_mt': 'Multihop (multi-token)',
    'chain_intermediates': 'Chained intermediates', 'role_bound_association': 'Role-bound association'}
SEED = 20261012


def choose_cases(before, after, cells, family, condition, seed=SEED):
    """One case per declared bucket; missing buckets remain explicitly missing.

    Site wins/regressions use lexicographic item/cell order. Unchanged is a
    seeded random site with the same endpoint, irrespective of text changes.
    Whole-question gains/losses use a first passing witness on the complete
    original grid. Same text with different scored verdicts is separately kept.
    """
    if set(before) != set(cells) or set(after) != set(cells):
        raise ValueError('Case selection requires complete identical grids')
    buckets = defaultdict(list)
    ordered = sorted(cells, key=lambda cid: (str(cells[cid]['item_id']), cid))
    for cid in ordered:
        b, a = before[cid], after[cid]
        if family == 'hallucination':
            category = ('win' if b['class'] == 'hallucinated' and a['class'] == 'consistent'
                else 'regression' if b['class'] == 'consistent' and a['class'] == 'hallucinated'
                else 'unchanged' if b['class'] == a['class'] else None)
            if b['class'] == 'hallucinated' and a['empty']:
                buckets['error_to_empty'].append(cid)
            elif b['class'] == 'hallucinated' and a['class'] == 'off_topic':
                buckets['error_to_offtopic'].append(cid)
            verdict_differs = b['class'] != a['class'] or b.get('evidence') != a.get('evidence')
        else:
            category = 'win' if a['pass'] and not b['pass'] else 'regression' if b['pass'] and not a['pass'] else 'unchanged'
            verdict_differs = b['pass'] != a['pass']
        if category:
            buckets[category].append(cid)
        if b['text'] == a['text'] and verdict_differs:
            buckets['same_text_different_verdict'].append(cid)
    categories = ['win', 'regression', 'unchanged', 'same_text_different_verdict']
    if family == 'hallucination':
        categories += ['error_to_empty', 'error_to_offtopic']
    else:
        categories += ['question_gain', 'question_loss']
        by_item = defaultdict(list)
        for cid in ordered:
            by_item[str(cells[cid]['item_id'])].append(cid)
        for ids in by_item.values():
            b = any(before[cid]['pass'] for cid in ids)
            a = any(after[cid]['pass'] for cid in ids)
            if b != a:
                kind = 'question_gain' if a else 'question_loss'
                witness = next(cid for cid in ids if (after if a else before)[cid]['pass'])
                buckets[kind].append(witness)
    selected, availability = [], {}
    for kind in categories:
        available = buckets[kind]
        availability[kind] = {'count': len(available), 'status': 'observed' if available else 'none_observed'}
        if not available:
            continue
        if kind == 'unchanged':
            domain = f'{seed}|{condition}|{family}|unchanged'
            value = int(hashlib.sha256(domain.encode()).hexdigest()[:16], 16)
            cid = random.Random(value).choice(available)
            policy = f'seeded_uniform_endpoint_unchanged_site; seed={seed}; domain={domain}'
        else:
            cid = available[0]
            policy = 'first_lexicographic_item_then_cell_in_declared_outcome_bucket'
            if kind.startswith('question_'):
                policy += '; first_passing_proposed_witness' if kind == 'question_gain' else '; first_passing_parent_witness'
        selected.append({'kind': kind, 'cell_id': cid, 'selection_policy': policy,
            'sampling_unit': 'question' if kind.startswith('question_') else 'activation_site',
            'endpoint_evidence': parent_endpoint(before, after, cid, cells, family)})
    return selected, availability


def load(path):
    return json.loads(Path(path).read_text())


def pin(pins, path, expected=None, *, must_be_in_analysis=False):
    path = str(path)
    actual = sha(path)
    if must_be_in_analysis and path not in pins:
        raise ValueError('Source absent from final native analysis: ' + path)
    if expected is not None and actual != expected:
        raise ValueError('Pinned source changed: ' + path)
    if path in pins and pins[path] != actual:
        raise ValueError('Conflicting evidence pin: ' + path)
    pins[path] = actual
    return actual


def descriptor_index(directory, wanted, seal, pins):
    index = {}
    for path in sorted(Path(directory).glob('**/*.ready.json')):
        descriptor = load(path)
        own = {f"{r['method']}-n{r['n']}" for r in descriptor.get('conditions', [])} & set(wanted)
        if not own:
            continue
        pin(pins, path, must_be_in_analysis=True)
        if descriptor.get('ready') is not True or descriptor.get('partial_grid') or descriptor['inventory_sha256'] != seal:
            raise ValueError('Require sealed complete ready descriptor')
        for field in ('manifest', 'selections'):
            hash_field = 'selection_sha256' if field == 'selections' else 'manifest_sha256'
            pin(pins, descriptor[field], descriptor[hash_field], must_be_in_analysis=True)
        for condition in own:
            key = condition, descriptor['family']
            if key in index:
                raise ValueError('Duplicate ready descriptor')
            index[key] = descriptor
    return index


def selected_sources(index, family, selected_ids, arms, cells):
    """Stream each journal once, retain rich metadata only for selected cells."""
    by_path = defaultdict(set)
    for (condition, own_family), descriptor in index.items():
        if own_family == family:
            by_path[descriptor['selections']].add(condition)
    outputs = {}
    for path, conditions in by_path.items():
        seen = set()
        with Path(path).open() as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                cid = row['cell_id']
                if cid not in selected_ids:
                    continue
                if cid in seen:
                    raise ValueError('Duplicate selected journal cell')
                seen.add(cid)
                for field in ('family', 'item_id', 'layer', 'position', 'split', 'activation_sha256'):
                    if row[field] != cells[cid][field]:
                        raise ValueError('Selector source cell identity differs')
                found = set()
                for selection in row['selections']:
                    condition = f"{selection['method']}-n{selection['n']}"
                    if condition not in conditions:
                        continue
                    if condition in found or selection['text'] != arms[condition][cid]['text']:
                        raise ValueError('Selected source text differs from official judged readout')
                    found.add(condition)
                    outputs[condition, cid] = {'selection': selection,
                        'source_selection_path': path,
                        'source_row_metadata': {k: v for k, v in row.items() if k not in ('selections', 'atoms', 'source_samples')},
                        'source_atoms': row.get('atoms', [])}
                if found != conditions:
                    raise ValueError('Selected source lacks a required condition')
        if seen != set(selected_ids):
            raise ValueError('Selected source grid is incomplete')
    return outputs


def selection_difference(before, after):
    """Saved exact FVE and output lengths, never refitted or substituted."""
    def fve(row):
        fits = row['selection'].get('fits') or {}
        return (fits.get('exact') or {}).get('fve')
    b, a = before['selection'], after['selection']
    bf, af = fve(before), fve(after)
    return {'parent_exact_fve': bf, 'proposed_exact_fve': af,
        'exact_fve_delta': af-bf if bf is not None and af is not None else None,
        'parent_bullets': b['bullet_count'], 'proposed_bullets': a['bullet_count'],
        'bullet_delta': a['bullet_count']-b['bullet_count'],
        'parent_qwen_tokens': b['token_count'], 'proposed_qwen_tokens': a['token_count'],
        'qwen_token_delta': a['token_count']-b['token_count'],
        'interpretation': 'Saved reconstruction objective and lengths; neither is a truth verdict.'}


def run(args):
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Full-bank source verification/extraction requires allocated CPUs')
    if args.output.exists():
        raise FileExistsError('Preserve immutable packs; choose a new output path')
    pins = {}
    pin(pins, args.inventory, args.inventory_sha256)
    pin(pins, args.analysis, args.analysis_sha256)
    inventory, analysis = load(args.inventory), load(args.analysis)
    if inventory.get('status') != 'sealed' or analysis.get('status') != 'complete_exploratory' or analysis['inventory_sha256'] != args.inventory_sha256:
        raise ValueError('Require a sealed inventory and complete matching exploratory analysis')
    if analysis.get('missing_condition_families'):
        raise ValueError('Incomplete official judgments')
    if tuple(inventory['families']) != tuple(TITLES) or inventory['analysis']['seed'] != SEED:
        raise ValueError('Require the four pinned families and frozen case-sampling seed')
    for path, expected in analysis['source_sha256'].items():
        pin(pins, path, expected)
    pin(pins, args.api_config, must_be_in_analysis=True)
    config = load(args.api_config)
    fresh = inventory['fresh_manifest']
    pin(pins, fresh['path'], fresh['sha256'], must_be_in_analysis=True)
    cells = {r['cell_id']: r for r in load(fresh['path'])['cells']}
    if len(cells) != inventory['expected']['cells'] or len({(r['family'], r['item_id']) for r in cells.values()}) != inventory['expected']['items']:
        raise ValueError('Original complete cohort differs')
    if analysis['cohort'] != {'questions': inventory['expected']['items'],
            'cells': inventory['expected']['cells'], 'all_previously_inspected': True}:
        raise ValueError('Final native cohort differs from original exploratory cohort')
    methods = {r['condition_id']: r for r in inventory['conditions']}
    names = set(methods) | set(REFERENCE_IDS)
    completed = {(r['condition'], r['family']) for r in analysis['complete_condition_families']}
    if completed != {(c, f) for c in names for f in inventory['families']}:
        raise ValueError('Final analysis must cover exactly the new menu and six original references')
    if any(r['actual_parent'] not in names for r in methods.values()):
        raise ValueError('Actual parent absent from declared source menu')
    baseline = descriptor_index(config['baseline_descriptor_snapshot'], REFERENCE_IDS, config['baseline_inventory_sha256'], pins)
    new = descriptor_index(args.ready_directory, methods, args.inventory_sha256, pins)
    index = baseline | new
    if set(index) != completed:
        raise ValueError('Ready sources differ from complete native analysis')
    roots = {condition: config['output'] if condition in methods else config['baseline_judgments'] for condition in names}
    traces, cases, availability, contexts, original_readouts = [], [], {}, {}, {}
    for family in inventory['families']:
        own = {cid: cell for cid, cell in cells.items() if cell['family'] == family}
        arms = {c: read_arm(Path(roots[c])/c, family, own) for c in sorted(names)}
        plans = []
        for condition, method in methods.items():
            parent = method['actual_parent']
            chosen, counts = choose_cases(arms[parent], arms[condition], own, family, condition)
            availability.setdefault(condition, {})[family] = counts
            plans.extend((condition, parent, row) for row in chosen)
        selected_ids = {row['cell_id'] for _, _, row in plans}
        sources = selected_sources(index, family, selected_ids, arms, own)
        bank_path = paths(family)['bank']
        bank_sha = pin(pins, bank_path)
        bank = {item_id(row): row for row in load_bank(family)}
        for condition, parent, choice in plans:
            cid = choice['cell_id']
            cell = own[cid]
            outputs = {c: dict(arms[c][cid]) for c in sorted(names)}
            for reference in sorted(names - {condition}):
                traces.append({'condition': condition, 'baseline_condition': reference,
                    'families': {family: {'examples': {'selected': [{'cell_id': cid,
                        'baseline': outputs[reference], 'proposed': outputs[condition]}]}}}})
            same_text = outputs[parent]['text'] == outputs[condition]['text']
            different_verdict = (outputs[parent]['class'], outputs[parent]['pass'], outputs[parent].get('evidence')) != (outputs[condition]['class'], outputs[condition]['pass'], outputs[condition].get('evidence'))
            case = choice | {'case_id': f"{condition}|{family}|{choice['kind']}|{cid}",
                'condition': condition, 'reference_id': parent, 'family': family,
                'task_title': TITLES[family], 'item_id': cell['item_id'], 'group_id': cell['group_id'],
                'layer': cell['layer'], 'position': cell['position'], 'cell': cell,
                'before': outputs[parent]['text'], 'after': outputs[condition]['text'],
                'actual_parent': outputs[parent], 'proposed': outputs[condition],
                'original_reference_id': 'raw_n1-n1', 'original_raw': outputs['raw_n1-n1'],
                'reference_outputs': {c: outputs[c] for c in REFERENCE_IDS},
                'reference_endpoint_evidence': {c: parent_endpoint(arms[c], arms[condition], cid, own, family) for c in REFERENCE_IDS},
                'selection_sources': {c: sources[c, cid] for c in sorted(set(REFERENCE_IDS) | {parent, condition})},
                'selection_difference': selection_difference(sources[parent, cid], sources[condition, cid]),
                'same_text': same_text, 'same_text_different_scored_verdict': same_text and different_verdict,
                'context_ref': cid, 'finding': '', 'review_status': 'unreviewed_source_evidence'}
            cases.append(case)
            contexts[cid] = {'source_bank_item': bank[str(cell['item_id'])],
                'bank_path': str(bank_path), 'bank_sha256': bank_sha,
                'original_capture_spec': cell['capture_spec'], 'evaluation_only': True}
            original_readouts[cid] = {'raw': outputs['raw_n1-n1'], 'capped': outputs['capped_n1-n1']}
    measurement = {'conditions': [{'condition': c, 'condition_root': roots[c]} for c in sorted(names)]}
    for path, expected in enrich_traces(traces, measurement, cells).items():
        if path in pins and pins[path] != expected:
            raise ValueError('Judge evidence differs from native analysis source')
        pins[path] = expected
    propagate_evidence(traces)
    # Copies held by multiple case/reference records get the same retained evidence.
    enriched = {(trace[side+'_condition'] if side == 'baseline' else trace['condition'], family, row['cell_id']): row[side]
        for trace in traces for family, data in trace['families'].items()
        for rows in data['examples'].values() for row in rows for side in ('baseline', 'proposed')}
    for case in cases:
        cid, family = case['cell_id'], case['family']
        for condition, row in [(case['reference_id'], case['actual_parent']), (case['condition'], case['proposed']),
                ('raw_n1-n1', case['original_raw']), *case['reference_outputs'].items()]:
            row.update(enriched[condition, family, cid])
        b, a = case['actual_parent'], case['proposed']
        case['same_text_different_retained_evidence'] = case['same_text'] and b['evidence'] != a['evidence']
        contexts[cid]['evaluation_context'] = a.get('evaluation_context')
    for cid, original in original_readouts.items():
        for condition, label in [('raw_n1-n1', 'raw'), ('capped_n1-n1', 'capped')]:
            original[label].update(enriched[condition, cells[cid]['family'], cid])
    for path, expected in pins.items():
        if sha(path) != expected:
            raise ValueError('Evidence changed during extraction: ' + path)
    payload = {'status': 'prepared_pending_independent_review', 'updated_utc': datetime.now(timezone.utc).isoformat(),
        'inventory_sha256': args.inventory_sha256, 'analysis_sha256': args.analysis_sha256,
        'original_reference': {'condition': 'raw_n1-n1', 'display_name': 'Original released Oracle Lens'},
        'cohort': analysis['cohort'], 'cases': cases, 'contexts': contexts, 'original_readouts': original_readouts,
        'available_categories': availability,
        'reviewer_partitions': {c: [row['case_id'] for row in cases if row['condition'] == c] for c in methods},
        'source_sha256': pins,
        'implementation_sha256': {path: sha(path) for path in (str(Path(__file__)),
            'scripts/analyze_consensus_conditions.py', 'scripts/analyze_signed_menu.py',
            'scripts/build_expansion_parent_qualitative.py')},
        'case_selection_contract': {'seed': SEED, 'max_per_declared_category_family_method': 1,
            'comparison': 'actual parent from sealed inventory; raw original is an additional reference',
            'site_cases': 'first lexicographic item/cell endpoint win and regression; uniform seeded unchanged endpoint site',
            'question_cases': 'separate complete-grid question gains/losses with passing witness',
            'missing_category': 'none_observed, never fabricated', 'finding': 'empty until independent human/agent review'},
        'new_model_calls': 0, 'new_judge_calls': 0,
        'limits': ['Exploratory on all four previously inspected banks; selected examples do not estimate prevalence.',
            'Site recovery gains/losses are secondary and may leave whole-question headline recovery unchanged.',
            'Hall contradiction-to-consistent cases are separate from contradiction-to-empty/off-topic cases.',
            'False counts are established spans; true/unverifiable counts enumerate claims. Their segmentation differs; no uniform claim precision.',
            'Recovering a name, number, or entity-role association does not verify every assertion in the prose.',
            'Unchanged text with differing scored verdicts or retained evidence is explicitly preserved; no verdict is reconciled here.',
            'Exact source text, official verdicts and reconstruction traces support inspection, not causal mechanism claims.',
            'All prompt/gold/judge context is evaluation-only and was unavailable to method selection.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic(args.output, payload)
    return {'output': str(args.output), 'sha256': sha(args.output), 'cases': len(cases), 'status': payload['status']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=Path('configs/target_only_inventory_v2.json'))
    parser.add_argument('--inventory-sha256', required=True)
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--analysis-sha256', required=True)
    parser.add_argument('--api-config', type=Path, default=Path('configs/target_only_api_v1.json'))
    parser.add_argument('--ready-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args())))


if __name__ == '__main__':
    main()
