#!/usr/bin/env python3
"""One persistent family judge/cache writer consuming atomic complete exports."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from expanded_api import atomic_text, budget, digest, load_key, paid_gate
import forecast_judging
from forecast_judging import run as forecast_requests
from olens_improve import evaluation
from olens_improve.budget import AtomicBudget
from olens_improve.data import canonical


class ExpansionBudget(AtomicBudget):
    """Explicit expansion factory used only inside this process."""
    def __init__(self, path, **kwargs):
        project = json.loads(Path('configs/project.json').read_text())
        if project['api_hard_ceiling_usd'] != 340 or project['api_target_usd'] != 200:
            raise ValueError('Sealed expansion limits differ')
        super().__init__(path, hard_usd=340, target_usd=200, **kwargs)


def validate_ready(path, args, inventory):
    descriptor = json.loads(path.read_text())
    if descriptor.get('family') != args.family or descriptor.get('ready') is False:
        return None
    if descriptor.get('inventory_sha256', args.inventory_sha256) != args.inventory_sha256:
        raise ValueError('Completed export belongs to another inventory')
    conditions = descriptor['conditions']
    if isinstance(conditions, str):
        conditions = json.loads(Path(conditions).read_text())
    allowed = {(c['method'], c['n']) for c in inventory['conditions']
        if c['status'] not in ('obsolete_malformed_transport_diagnostic', 'exact_alias',
                               'computed_numerical_diagnostic_only')}
    if not conditions or any((c['method'], c['n']) not in allowed for c in conditions):
        raise ValueError('Export condition lies outside the finite active menu')
    for field in ('manifest', 'selections'):
        hash_key = 'selection_sha256' if field == 'selections' else 'manifest_sha256'
        if digest(descriptor[field]) != descriptor[hash_key]:
            raise ValueError('Atomic completed export changed: '+field)
    manifest = json.loads(Path(descriptor['manifest']).read_text())
    if not manifest['cells'] or any(c['family'] != args.family for c in manifest['cells']):
        raise ValueError('Descriptor is not a single complete family')
    if manifest.get('partial_grid'):
        raise ValueError('Partial shards cannot enter the complete-family judge queue')
    return descriptor, conditions


def expansion_cohort(path, inventory, inventory_sha256):
    manifest = json.loads(Path(path).read_text())
    if manifest.get('inventory_sha256') != inventory_sha256:
        raise ValueError('Expansion cohort lacks its exact finite authority')
    fresh_info = inventory['fresh_manifest']
    if digest(fresh_info['path']) != fresh_info['sha256']:
        raise ValueError('Original fresh activation manifest changed')
    fresh = {c['cell_id']: c for c in json.loads(Path(fresh_info['path']).read_text())['cells']}
    indexed = {c['cell_id']: c for c in manifest['cells']}
    if len(indexed) != len(manifest['cells']):
        raise ValueError('Duplicate expansion cell')
    families = {c['family'] for c in indexed.values()}
    if len(families) != 1:
        raise ValueError('Require one exact full-family cohort')
    expected = {cid for cid,c in fresh.items() if c['family'] in families}
    if set(indexed) != expected:
        raise ValueError('Expansion family grid differs from the frozen full-bank capture')
    for cid, cell in indexed.items():
        if any(cell.get(k) != fresh[cid][k] for k in
                ('family','item_id','layer','position','split','activation_sha256')):
            raise ValueError('Original split/cell/activation identity changed')
    return manifest, indexed, {cid:fresh[cid] for cid in indexed}


def evaluate_expansion(descriptor, condition, args, inventory):
    """Preserve original cohort fields while calling the unchanged family judge."""
    manifest, cells, captures = expansion_cohort(descriptor['manifest'], inventory, args.inventory_sha256)
    rows, seen = [], set()
    with Path(descriptor['selections']).open() as source:
        for line in source:
            row = json.loads(line)
            cid = row['cell_id']
            if cid in seen or cid not in cells:
                raise ValueError('Duplicate or off-cohort selected cell')
            seen.add(cid)
            if any(row.get(k) != cells[cid][k] for k in
                   ('family','item_id','layer','position','split','activation_sha256')):
                raise ValueError('Selected output changed an original identity')
            matched = [s for s in row['selections'] if s['method'] == condition['method'] and s['n'] == condition['n']]
            if len(matched) != 1:
                raise ValueError('Require exactly one finite-condition output per original cell')
            rows.append({k:row[k] for k in ('cell_id','family','item_id','layer','position')} |
                        {'text':matched[0]['text'], 'sample_index':0})
    if seen != set(cells):
        raise ValueError('Selected output grid is incomplete')
    by_family, coverage = evaluation.convert_selected_readouts(rows, manifest['cells'])
    out = args.output/f"{condition['method']}-n{condition['n']}"
    out.mkdir(parents=True, exist_ok=True)
    scientific = {**condition, 'selection_sha256':descriptor['selection_sha256'],
        'manifest_sha256':descriptor['manifest_sha256'], 'inventory_sha256':args.inventory_sha256,
        'run_id':args.run_id, 'coverage':coverage, 'partial_grid':False,
        'scientific_scope':'exploratory_full_bank_all_questions_previously_inspected',
        'original_splits_preserved':True, 'service_tier':'default'}
    # All four workers share the condition directory, while each family has
    # different complete selection/cohort sources. Keep those pins independent.
    condition_path = out/f'{args.family}.condition.json'
    if condition_path.exists() and json.loads(condition_path.read_text()) != scientific:
        raise ValueError('Immutable expansion condition changed on resume')
    atomic_text(condition_path, canonical(scientific)+'\n')
    readout_path = out/f'{args.family}.readouts.jsonl'
    content = ''.join(canonical(r)+'\n' for r in by_family[args.family])
    if readout_path.exists() and readout_path.read_text() != content:
        raise ValueError('Original selected text changed on resume')
    atomic_text(readout_path, content)
    offline = getattr(args, 'offline_regex', False)
    ledger = None if offline else budget(args.ledger)
    if ledger is not None:
        ledger.set_run_limit(args.run_id, args.run_cap_usd)
    evaluation.load_upstream()
    if args.family != 'multihop_mt':
        evaluation.install_shared_verdict_cache(args.shared_cache/f'{args.family}.sqlite3', ledger, args.family)
    started = time.monotonic()
    execution = {'pid':os.getpid(), 'family':args.family,'condition':condition,
        'concurrency':args.concurrency, 'rpm':args.rpm, 'service_tier':'default',
        'reasoning_effort':'none', 'started_utc':time.time(), 'status':'running'}
    execution_path = out/f'{args.family}.execution.jsonl'
    with execution_path.open('a') as handle:
        handle.write(canonical(execution)+'\n')
    try:
        result = evaluation.run_family(args.family, readout_path, out/args.family, manifest['cells'],
            ledger=ledger, run_id=args.run_id, allow_paid=not offline, dry_run=False, partial_grid=False,
            concurrency=args.concurrency, rpm=args.rpm, service_tier='default')
    except BaseException as error:
        execution.update(status='failed', error_type=type(error).__name__)
        raise
    else:
        execution['status'] = 'completed'
        contract_path = out/args.family/'project_contract.json'
        if contract_path.exists():
            contract = json.loads(contract_path.read_text())
            contract.update(scientific_status='exploratory-full-bank-comparison',
                            inventory_sha256=args.inventory_sha256,
                            original_splits_preserved=True)
            atomic_text(contract_path, canonical(contract)+'\n')
        atomic_text(out/f'{args.family}.summary.json', canonical({'condition':scientific,
            'families':{args.family:result}, 'budget':ledger.snapshot() if ledger else None,
            'api_dispatch_forbidden':offline})+'\n')
    finally:
        execution.update(wall_seconds=time.monotonic()-started, finished_utc=time.time())
        with execution_path.open('a') as handle:
            handle.write(canonical(execution)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', required=True)
    parser.add_argument('--forecast', type=Path, required=True)
    parser.add_argument('--budget-receipt', type=Path, default=Path('${OLENS_DATA_ROOT}/expansion-v1/receipts/budget-activation-v1.json'))
    parser.add_argument('--ledger', type=Path, default=Path('${OLENS_DATA_ROOT}/budget/ledger.sqlite3'))
    parser.add_argument('--run-id', default='expanded-all-four-banks-v1')
    parser.add_argument('--run-cap-usd', default='298')
    parser.add_argument('--allow-paid', action='store_true')
    parser.add_argument('--family', choices=evaluation.FAMILIES, required=True)
    parser.add_argument('--ready-directory', type=Path, action='append', required=True)
    parser.add_argument('--shared-cache', type=Path, default=Path('${OLENS_DATA_ROOT}/runs/development-shared-pilot-v2/judgments/shared-exact-cache'))
    parser.add_argument('--empirical-summary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--concurrency', type=int, default=256)
    parser.add_argument('--rpm', type=float, default=4000)
    parser.add_argument('--stop-file', type=Path)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--forecast-only', action='store_true')
    parser.add_argument('--offline-regex', action='store_true',
                        help='Deterministic multihop only; no key loading, ledger or network sockets')
    args = parser.parse_args()
    if args.offline_regex:
        if args.family != 'multihop_mt' or args.allow_paid:
            raise ValueError('Offline regex cannot enable paid work or another family')
        if digest(args.inventory) != args.inventory_sha256 or not os.environ.get('SLURM_JOB_ID'):
            raise ValueError('Offline regex requires allocated CPU and finite original authority')
        inventory = json.loads(args.inventory.read_text())
        def forbidden(*_args, **_kwargs):
            raise RuntimeError('Network/API dispatch is forbidden in this offline regex process')
        evaluation.install_upstream_transport = forbidden
        evaluation.make_luna_client = forbidden
        import socket
        socket.socket.connect = forbidden
        socket.socket.connect_ex = forbidden
        socket.create_connection = forbidden
    elif args.forecast_only:
        if digest(args.inventory) != args.inventory_sha256 or not os.environ.get('SLURM_JOB_ID'):
            raise ValueError('Read-only forecast requires allocated CPU and sealed authority')
        inventory = json.loads(args.inventory.read_text())
    else:
        inventory = paid_gate(args)
        load_key()
    os.environ.update(OLENS_LEDGER_REUSE_WRITER_CONNECTION='1', OLENS_LEDGER_RESERVATION_BATCH_SIZE='16')
    # The unchanged evaluate_condition implementation otherwise constructs its
    # historical300-dollar default. Only this expansion process substitutes its
    # explicitly reconciled ledger factory; no historical source is changed.
    evaluation.AtomicBudget = ExpansionBudget
    # The forecast's legacy API accepts the development label solely to enable
    # family-scoped planning. This adapter validates original mixed-split rows
    # itself, and retains their fields byte-for-byte in all saved artifacts.
    def forecast_stage_adapter(manifest, fresh_manifest=None, gate=None):
        body, _cells, captures = expansion_cohort(manifest, inventory, args.inventory_sha256)
        return body, 'development', captures, {'scope':'exploratory_expansion',
                                               'inventory_sha256':args.inventory_sha256}
    forecast_judging.evaluation_stage = forecast_stage_adapter
    os.environ['OLENS_TEST_FROZEN'] = '1'
    args.output.mkdir(parents=True, exist_ok=True)
    args.shared_cache.mkdir(parents=True, exist_ok=True)
    owner = (args.shared_cache/f'{args.family}.owner.lock').open('a')
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state_path = args.output/f'{args.family}.queue-state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {
        'inventory_sha256':args.inventory_sha256, 'family':args.family,
        'completed':{}, 'pid':os.getpid(), 'started_utc':time.time()}
    if state['inventory_sha256'] != args.inventory_sha256:
        raise ValueError('Queue state belongs to another finite menu')
    state.update(pid=os.getpid(), cpu_job=os.environ['SLURM_JOB_ID'], running=True)
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGUSR1, stop)
    while not stopping and not (args.stop_file and args.stop_file.exists()):
        paths = sorted({p for directory in args.ready_directory for p in directory.glob('**/*.ready.json')})
        did_work = False
        for path in paths:
            checked = validate_ready(path, args, inventory)
            if checked is None:
                continue
            descriptor, conditions = checked
            pending = [c for c in conditions if f"{c['method']}-n{c['n']}" not in state['completed']]
            if not pending:
                continue
            did_work = True
            token = digest(path)[:16]
            conditions_path = args.output/f'{args.family}-{token}.conditions.json'
            atomic_text(conditions_path, canonical(pending)+'\n')
            forecast_path = args.output/f'{args.family}-{token}.exact-forecast.json'
            if args.family != 'multihop_mt' and not forecast_path.exists():
                forecast_requests(SimpleNamespace(manifest=Path(descriptor['manifest']),
                    fresh_manifest=None, gate=None, family=args.family,
                    selections=[Path(descriptor['selections'])], conditions=[conditions_path],
                    cache=args.shared_cache, ledger=args.ledger, output=forecast_path,
                    empirical_summary=args.empirical_summary, empirical_since='2026-10-10T04:50:43+00:00',
                    concurrency=args.concurrency, rpm=args.rpm))
            if args.forecast_only:
                print(canonical({'status':'forecast_only', 'family':args.family,
                                 'path':str(forecast_path)}), flush=True)
                continue
            state.update(current_descriptor=str(path), current_forecast=str(forecast_path),
                         last_successful_check_utc=time.time())
            atomic_text(state_path, canonical(state)+'\n')
            for condition in pending:
                if stopping or (args.stop_file and args.stop_file.exists()):
                    break
                key = f"{condition['method']}-n{condition['n']}"
                started = time.monotonic()
                evaluate_expansion(descriptor, condition, args, inventory)
                state['completed'][key] = {'selection_sha256':descriptor['selection_sha256'],
                    'manifest_sha256':descriptor['manifest_sha256'], 'descriptor':str(path),
                    'wall_seconds':time.monotonic()-started, 'finished_utc':time.time()}
                state['last_successful_check_utc'] = time.time()
                atomic_text(state_path, canonical(state)+'\n')
                print(canonical({'completed':key, 'family':args.family,
                    'wall_seconds':state['completed'][key]['wall_seconds']}), flush=True)
        if args.once:
            break
        if not did_work:
            state['last_successful_check_utc'] = time.time()
            atomic_text(state_path, canonical(state)+'\n')
            time.sleep(20)
    state.update(running=False, stopped_utc=time.time())
    atomic_text(state_path, canonical(state)+'\n')


if __name__ == '__main__':
    main()
