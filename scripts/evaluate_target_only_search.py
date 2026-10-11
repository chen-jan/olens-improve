#!/usr/bin/env python3
"""Additive target-only full-bank forecasting/judging with the frozen Luna recipe.

Forecast never opens a writer connection or loads credentials. Paid dispatch
requires a separate root-reviewed approval pinning this config, inventory,
descriptor and exact forecast. Historical result directories are read-only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import expanded_judges
import forecast_judging
from expanded_api import atomic_text, digest, load_key
from olens_improve import evaluation
from olens_improve.data import canonical
from olens_improve.reporting import family_counts, original_grid_pairs

IDENTITY = ('family', 'item_id', 'layer', 'position', 'split', 'activation_sha256')
REFERENCE_IDS = ('raw_n1-n1', 'capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32',
                 'pooled_greedy_swap_then_prune_0.005-n32',
                 'pooled_greedy_swap_random_delete_matched_0.005-n32')


def load(path):
    return json.loads(Path(path).read_text())


def read_only_budget(path):
    """Consistent live accounting without AtomicBudget's schema initialization."""
    with sqlite3.connect(f'file:{Path(path)}?mode=ro', uri=True, timeout=30,
                         isolation_level=None) as db:
        db.execute('BEGIN')
        config = dict(db.execute('SELECT key,value FROM config'))
        rows = db.execute('SELECT status,COUNT(*),SUM(reserved),SUM(actual) '
                          'FROM attempts GROUP BY status').fetchall()
        db.execute('COMMIT')
    actual = sum(r[3] or 0 for r in rows if r[0] == 'settled') / 1e9
    holds = sum(r[2] or 0 for r in rows if r[0] in ('reserved', 'unknown')) / 1e9
    return {'utc': datetime.now(timezone.utc).isoformat(), 'db_path': str(Path(path).resolve()),
            'hard_usd': config['hard']/1e9, 'target_usd': config['target']/1e9,
            'halted': bool(config['halted']), 'actual_usd': actual,
            'reserved_usd': holds, 'committed_usd': actual+holds,
            'remaining_hard_usd': config['hard']/1e9-actual-holds,
            'attempt_counts': {r[0]: r[1] for r in rows}, 'invoice_reconciled': False}


def authority(args):
    if digest(args.inventory) != args.inventory_sha256:
        raise ValueError('Target-only inventory seal changed')
    inventory, config = load(args.inventory), load(args.api_config)
    if inventory.get('status') != 'sealed':
        raise ValueError('Require a sealed finite target-only inventory')
    if 'control_bank' in inventory:
        raise ValueError('Other-activation control banks are ineligible for target-only search')
    if inventory.get('selection_access') != {'target_activations_per_cell': 1,
            'other_activations': False, 'prompt_access': False, 'label_access': False}:
        raise ValueError('Require an explicit one-target/no-prompt/no-label selector contract')
    if inventory['fresh_manifest'] != load('configs/expansion_manifest_v1.json')['fresh_manifest']:
        raise ValueError('Target-only search must use the original fresh capture')
    if tuple(inventory['families']) != tuple(evaluation.FAMILIES):
        raise ValueError('Require all four original task families')
    if inventory.get('expected', {}).get('cells') != 19435 or inventory['expected'].get('items') != 469:
        raise ValueError('Target-only inventory must retain all469questions/19435cells')
    if (config['judge_model'], config['reasoning_effort'], config['service_tier']) != ('gpt-6-luna', 'none', 'default'):
        raise ValueError('Frozen Standard Luna judge recipe changed')
    if not 1 <= config['concurrency'] <= 256 or not 0 < config['rpm'] <= 4000:
        raise ValueError('Transport exceeds reviewed bounds')
    if (config['hard_ceiling_usd'], config['target_usd']) != (340, 200):
        raise ValueError('Target-only work cannot change project limits')
    old_methods = {r['condition_id'] for r in load('configs/expansion_manifest_v1.json')['conditions']}
    new = {r['condition_id']: r for r in inventory['conditions']
           if r['condition_id'] not in old_methods and r['status'] not in
           ('exact_alias', 'obsolete_malformed_transport_diagnostic', 'computed_numerical_diagnostic_only')}
    if not new or any(r['n'] != 32 or r['condition_id'] != f"{r['method']}-n32" for r in new.values()):
        raise ValueError('Require unique additive N32 method identities')
    if len(new) != len({(r['method'], r['n']) for r in new.values()}):
        raise ValueError('Duplicate target-only methods')
    parents = set(new) | set(REFERENCE_IDS)
    if any(r.get('actual_parent') not in parents or r['actual_parent'] == key for key, r in new.items()):
        raise ValueError('Require an eligible declared actual parent for each new method')
    return inventory, config, new


def checked_descriptor(args, inventory, new):
    descriptor = load(args.descriptor)
    if descriptor.get('family') != args.family or descriptor.get('ready') is not True:
        raise ValueError('Require a terminal full-family ready descriptor')
    if descriptor.get('inventory_sha256') != args.inventory_sha256 or descriptor.get('partial_grid'):
        raise ValueError('Descriptor belongs to another scope or a pilot grid')
    for field, hash_key in (('manifest', 'manifest_sha256'), ('selections', 'selection_sha256')):
        if digest(descriptor[field]) != descriptor[hash_key]:
            raise ValueError('Completed family source changed: '+field)
    manifest, cells, _ = expanded_judges.expansion_cohort(descriptor['manifest'], inventory, args.inventory_sha256)
    declared = {(r['method'], r['n']) for r in descriptor['conditions']}
    conditions = [r for key, r in new.items() if (r['method'], r['n']) in declared]
    if not conditions:
        raise ValueError('Descriptor contains no new methods')
    seen = set()
    with Path(descriptor['selections']).open() as stream:
        for line in stream:
            row = json.loads(line)
            cid = row['cell_id']
            if cid in seen or cid not in cells or any(row.get(k) != cells[cid][k] for k in IDENTITY):
                raise ValueError('Selection cell identity changed')
            expected_spec = descriptor.get('search_spec_sha256_by_cell', {}).get(
                cid, descriptor.get('search_spec_sha256'))
            if row.get('inventory_sha256') != args.inventory_sha256 or row.get('search_spec_sha256') != expected_spec:
                raise ValueError('Selection search authority changed')
            seen.add(cid)
            for condition in conditions:
                matched = [s for s in row['selections'] if (s['method'], s['n']) == (condition['method'], condition['n'])]
                if len(matched) != 1:
                    raise ValueError('Missing or duplicate target-only method output')
                selection = matched[0]
                if not isinstance(selection.get('text'), str) or any(type(selection.get(k)) is not int or
                        not 0 <= selection[k] <= cap for k, cap in (('token_count', 256), ('bullet_count', 4))):
                    raise ValueError('Invalid text or final output cap')
                if condition['method'] != 'repeated_swaps_random_delete_match_005':
                    measured = selection.get('budget', {})
                    if measured.get('subset_fit_budget') != inventory['search']['subset_fit_budget'] or type(measured.get('subset_fits')) is not int or not 0 <= measured['subset_fits'] <= inventory['search']['subset_fit_budget']:
                        raise ValueError('Selection violated its frozen subset-fit budget')
                if condition['method'] in ('repeat_swap_then_prune_005', 'bounded_prune_refill_005'):
                    gains = selection.get('leave_one_out')
                    threshold = inventory['search']['threshold']+inventory['search']['tolerance']
                    if not isinstance(gains, dict) or len(gains) != selection['bullet_count'] or any(
                            type(value) not in (int, float) or not math.isfinite(value) or value <= threshold for value in gains.values()):
                        raise ValueError('Selection lacks strict retained per-bullet contribution evidence')
    if seen != set(cells):
        raise ValueError('Incomplete full-family selection export')
    return descriptor, conditions


def setup_forecast_adapter(args, inventory):
    def stage_adapter(manifest, fresh_manifest=None, gate=None):
        body, _cells, captures = expanded_judges.expansion_cohort(manifest, inventory, args.inventory_sha256)
        return body, 'development', captures, {'scope': 'exploratory_target_only_search',
                                                'inventory_sha256': args.inventory_sha256}
    forecast_judging.evaluation_stage = stage_adapter


def forecast(args, inventory, config, descriptor, conditions):
    if args.forecast.exists():
        raise FileExistsError('Preserve immutable existing forecast')
    conditions_path = args.forecast.with_suffix('.conditions.json')
    if conditions_path.exists():
        if load(conditions_path) != conditions:
            raise ValueError('Forecast conditions changed')
    else:
        atomic_text(conditions_path, canonical(conditions)+'\n')
    setup_forecast_adapter(args, inventory)
    if args.family == 'multihop_mt':
        result = {'status': 'read_only_request_forecast', 'conditions': conditions,
                  'expected_charge_including_unknown_stage2_upper_using_empirical_means_usd': 0,
                  'logical_rows': {'multihop_mt': len(load(descriptor['manifest'])['cells'])*len(conditions)},
                  'exact_cached_request_counts': {}, 'deterministic_regex': True}
    else:
        forecast_judging.run(SimpleNamespace(manifest=Path(descriptor['manifest']),
            fresh_manifest=None, gate=None, family=args.family,
            selections=[Path(descriptor['selections'])], conditions=[conditions_path],
            cache=Path(config['shared_cache']), ledger=Path(config['ledger']), output=args.forecast,
            empirical_summary=Path(config['empirical_summary']), empirical_since=config['empirical_since'],
            concurrency=config['concurrency'], rpm=config['rpm']))
        result = load(args.forecast)
    result.update(inventory_sha256=args.inventory_sha256,
                  api_config_sha256=digest(args.api_config), descriptor_sha256=digest(args.descriptor),
                  family=args.family, approved_for_dispatch=False,
                  budget=read_only_budget(config['ledger']), inference_calls=0)
    code_paths = [Path(__file__), Path('scripts/expanded_judges.py'),
                  Path('scripts/forecast_judging.py'), Path('src/olens_improve/evaluation.py'),
                  Path('src/olens_improve/budget.py')]
    result['implementation_sha256'] = {str(path): digest(path) for path in code_paths}
    atomic_text(args.forecast, canonical(result)+'\n')
    print(canonical({'forecast': str(args.forecast), 'sha256': digest(args.forecast),
                     'family': args.family, 'expected_new_charge_usd': result[
                         'expected_charge_including_unknown_stage2_upper_using_empirical_means_usd'],
                     'cache_counts': result['exact_cached_request_counts'], 'budget': result['budget']}))


def dispatch_gate(args, config, descriptor):
    if not args.allow_paid or args.dispatch_approval is None or not os.getenv('SLURM_JOB_ID'):
        raise ValueError('Paid dispatch requires explicit flag, CPU allocation and root-reviewed approval')
    approval = load(args.dispatch_approval)
    if approval.get('status') != 'root_reviewed' or approval.get('approved_for_dispatch') is not True:
        raise ValueError('Root has not approved target-only dispatch')
    for field, expected in (('inventory_sha256', args.inventory_sha256),
                            ('api_config_sha256', digest(args.api_config))):
        if approval.get(field) != expected:
            raise ValueError('Dispatch authority differs: '+field)
    entry = approval['family_forecasts'][args.family]
    if entry['path'] != str(args.forecast) or entry['sha256'] != digest(args.forecast):
        raise ValueError('Root-approved exact forecast changed')
    saved = load(args.forecast)
    if saved['descriptor_sha256'] != digest(args.descriptor) or saved['api_config_sha256'] != digest(args.api_config) or saved['inventory_sha256'] != args.inventory_sha256:
        raise ValueError('Forecast sources changed')
    for path, expected_sha in saved['implementation_sha256'].items():
        if digest(path) != expected_sha:
            raise ValueError('Reviewed forecasting/evaluation implementation changed: '+path)
    from analyze_expansion import runtime_authority
    runtime_hashes, _pins = runtime_authority(Path(config['runtime_authority']))
    if saved['source_contract'] != runtime_hashes or evaluation.load_upstream()['runtime_source_hashes'] != runtime_hashes:
        raise ValueError('Approved frozen judge source contract changed')
    live = read_only_budget(config['ledger'])
    if live['halted'] or live['hard_usd'] != 340 or live['target_usd'] != 200:
        raise ValueError('Live project budget is halted or differs')
    if not 0 < float(approval['run_cap_usd']) <= float(config['run_cap_usd']):
        raise ValueError('Run cap exceeds prepared authority')
    expected = approval['expected_total_new_charge_usd']
    if expected is None or expected < 0 or expected > float(approval['run_cap_usd']) or expected > live['remaining_hard_usd']:
        raise ValueError('Reviewed forecast does not fit the live budget')
    receipt = load(config['budget_activation_receipt'])
    if receipt['after'] != {'hard': 340000000000, 'target': 200000000000, 'halted': 0}:
        raise ValueError('Original expansion budget receipt differs')
    os.environ['OLENS_TRANSPORT_RECOVERY_SINCE'] = receipt['utc']
    return approval


def terminal_coverage(root, family, descriptor):
    """A returned judge process can still contain missing verdicts; check native rows."""
    readout_path, result_path = root/f'{family}.readouts.jsonl', root/family/'results.json'
    if not readout_path.exists() or not result_path.exists():
        return None
    manifest = load(descriptor['manifest'])['cells']
    with readout_path.open() as stream:
        readouts = [json.loads(line) for line in stream if line.strip()]
    result = load(result_path)
    metrics, coverage = family_counts(family, manifest, readouts, result)
    if coverage['missing_stage1'] or coverage['missing_stage2']:
        return coverage
    original_grid_pairs(family, metrics, result)
    return coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', required=True)
    parser.add_argument('--api-config', type=Path, default=Path('configs/target_only_api_v1.json'))
    parser.add_argument('--family', choices=evaluation.FAMILIES, required=True)
    parser.add_argument('--descriptor', type=Path, required=True)
    parser.add_argument('--forecast', type=Path, required=True)
    parser.add_argument('--mode', choices=('forecast', 'evaluate', 'offline-regex'), default='forecast')
    parser.add_argument('--dispatch-approval', type=Path)
    parser.add_argument('--allow-paid', action='store_true')
    args = parser.parse_args()
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Use an allocated CPU for full-bank preprocessing and evaluation')
    inventory, config, new = authority(args)
    descriptor, conditions = checked_descriptor(args, inventory, new)
    if args.mode == 'forecast':
        if args.allow_paid:
            raise ValueError('Forecast mode cannot enable paid dispatch')
        forecast(args, inventory, config, descriptor, conditions)
        return
    offline = args.mode == 'offline-regex'
    if offline and (args.family != 'multihop_mt' or args.allow_paid):
        raise ValueError('Offline mode is only the released hidden-name regex')
    approval = None if offline else dispatch_gate(args, config, descriptor)
    args.output, args.shared_cache = Path(config['output']), Path(config['shared_cache'])
    historical = Path('${OLENS_DATA_ROOT}/expansion-v1/judgments').resolve()
    if args.output.resolve() == historical or historical in args.output.resolve().parents:
        raise ValueError('Historical results are immutable')
    args.output.mkdir(parents=True, exist_ok=True)
    args.ledger, args.run_id = Path(config['ledger']), config['run_id']
    args.run_cap_usd = config['run_cap_usd'] if offline else approval['run_cap_usd']
    args.concurrency, args.rpm, args.offline_regex = config['concurrency'], config['rpm'], offline
    os.environ.update(OLENS_LEDGER_REUSE_WRITER_CONNECTION='1',
        OLENS_LEDGER_RESERVATION_BATCH_SIZE='16', OLENS_TEST_FROZEN='1')
    evaluation.AtomicBudget = expanded_judges.ExpansionBudget
    if not offline:
        load_key()
    else:
        def forbidden(*_args, **_kwargs):
            raise RuntimeError('API/network dispatch forbidden in offline regex mode')
        evaluation.install_upstream_transport = forbidden
        evaluation.make_luna_client = forbidden
        import socket
        socket.socket.connect = forbidden
        socket.socket.connect_ex = forbidden
        socket.create_connection = forbidden
    # Same ownership convention as original expansion workers; one writer/family.
    lock_path = args.output/f'{args.family}.offline.lock' if offline else args.shared_cache/f'{args.family}.owner.lock'
    with lock_path.open('a') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for condition in conditions:
            output = args.output/f"{condition['method']}-n{condition['n']}"
            summary = output/f'{args.family}.summary.json'
            if summary.exists():
                scientific = load(summary)['condition']
                if any(scientific.get(k) != v for k, v in (
                    ('selection_sha256', descriptor['selection_sha256']),
                    ('manifest_sha256', descriptor['manifest_sha256']),
                    ('inventory_sha256', args.inventory_sha256))):
                    raise ValueError('Completed result belongs to another sealed selection')
                coverage = terminal_coverage(output, args.family, descriptor)
                if coverage is not None and not coverage['missing_stage1'] and not coverage['missing_stage2']:
                    print(canonical({'status': 'already_complete', 'condition': condition['condition_id'], 'family': args.family}))
                    continue
                print(canonical({'status': 'resume_incomplete_verdicts', 'condition': condition['condition_id'],
                                 'family': args.family, 'coverage': coverage}))
            expanded_judges.evaluate_expansion(descriptor, condition, args, inventory)
            coverage = terminal_coverage(output, args.family, descriptor)
            if coverage is None or coverage['missing_stage1'] or coverage['missing_stage2']:
                raise RuntimeError('Returned judge is incomplete; saved verdicts remain reusable on resume')
            print(canonical({'status': 'completed', 'condition': condition['condition_id'], 'family': args.family}))


if __name__ == '__main__':
    main()
