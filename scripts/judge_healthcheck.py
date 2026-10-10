"""One explicitly authorized direct Luna request; retain all older unknown holds."""
from __future__ import annotations

import argparse
import ast
import asyncio
from contextlib import closing
from datetime import datetime, timezone
from functools import wraps
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from olens_improve.budget import AtomicBudget
from olens_improve.evaluation import make_luna_client, request_cache_key, safe_exception_chain
from olens_improve.performance import OperationalProfile
from scripts.profile_reservation_copy import Recorder


class TransactionPhases:
    """Opt-in timing wrapper around unchanged methods for ONE guarded call."""
    def __init__(self, output):
        self.output = Path(output) if output else None
        self.recorder = Recorder() if output else None
        self.patches = []
        self.context = {}
        self.status = 'failed'
        self.patch = None
        if self.output is not None and self.output.exists():
            raise ValueError('Transaction phase evidence already exists; use a fresh path')

    def __enter__(self):
        if self.recorder is not None:
            self.recorder.operation = 'initialization'
            self.patch = patch('olens_improve.budget.sqlite3.connect', self.recorder.connect)
            self.patch.start()
        return self

    def attach_ledger(self, ledger):
        if self.recorder is None: return
        for name in ('set_run_limit', 'reserve_attempt', 'record_evidence', 'settle', 'mark_unknown', 'snapshot'):
            original = getattr(ledger, name)
            self.patches.append((ledger, name, original))

            def make_wrapper(method, function):
                @wraps(function)
                def call(*args, **kwargs):
                    prior = self.recorder.operation
                    self.recorder.operation = method
                    if method == 'reserve_attempt':
                        self.context['reserve_thread'] = 'main' if threading.current_thread() is threading.main_thread() else 'worker'
                        self.context['reservation_metadata_json_utf8_bytes_before_budget_fields'] = len(
                            json.dumps(kwargs.get('metadata') or {}, sort_keys=True).encode('utf-8'))
                    try: return function(*args, **kwargs)
                    finally: self.recorder.operation = prior
                return call

            setattr(ledger, name, make_wrapper(name, original))

    def __exit__(self, kind, error, traceback):
        # The caller first drains client/accounting and closes OperationalProfile;
        # restore our outer wrappers only afterward. No transaction is replayed.
        for ledger, name, original in reversed(self.patches):
            setattr(ledger, name, original)
        if self.patch is None: return False
        self.patch.stop()
        report = {'status':self.status if error is None else 'failed',
            'observed_utc':datetime.now(timezone.utc).isoformat(),
            'network_model_calls_allowed':1, 'context':self.context,
            'records':self.recorder.records,
            'exception_class':type(error).__name__ if error is not None else None,
            'recorder_source_sha256':sha256(Path(__file__).with_name('profile_reservation_copy.py').read_bytes()).hexdigest(),
            'scope':'Phase names/timings and byte counts only. Original methods, SQL, guard, journal, caps and holds unchanged; no synthetic production attempt and no extra SDK call.'}
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with self.output.open('x') as handle: handle.write(json.dumps(report,indent=2)+'\n')
        return False


async def check(args) -> dict:
    if not args.allow_paid:
        raise ValueError('One paid health request requires explicit authorization')
    epoch = os.environ.get('OLENS_TRANSPORT_RECOVERY_SINCE')
    preserve_guard = getattr(args, 'preserve_recovery_guard', False)
    if preserve_guard and not epoch:
        raise ValueError('Guarded canary requires the existing recovery epoch in the environment')
    if epoch and not preserve_guard:
        raise ValueError('Health probe does not reset or resume the paused recovery epoch; use a separate reviewed command')
    if args.output.exists():
        raise ValueError('Health artifact already exists; no repeat dispatch')
    with closing(sqlite3.connect(f'file:{args.ledger}?mode=ro', uri=True,
                                isolation_level=None)) as db:
        row = db.execute('SELECT status,run_id,metadata FROM attempts WHERE attempt_id=?',
                         (args.attempt_id,)).fetchone()
    if not row or row[0] != 'unknown' or row[1] != args.run_id:
        raise ValueError('Probe source must be an existing retained unknown from this run')
    original = json.loads(row[2])
    if preserve_guard:
        retained = original.get('transport_recovery_guard')
        if not isinstance(retained, dict) or retained.get('since_utc') != epoch:
            raise ValueError('Guarded canary must preserve the exact replay source recovery epoch')
    request = original['request']
    if request.get('model') != 'gpt-6-luna' or request.get('reasoning_effort') != 'none' or request.get('service_tier') != 'default':
        raise ValueError('Expected the exact frozen Standard Luna benchmark request')
    if request_cache_key(request) != original['content_cache_key']:
        raise ValueError('Original request content hash differs')
    if not os.environ.get('OPENAI_API_KEY'):
        for line in Path('.env').read_text().splitlines():
            key, sep, value = line.removeprefix('export ').partition('=')
            if sep and key.strip() == 'OPENAI_API_KEY':
                value = value.strip()
                os.environ[key.strip()] = ast.literal_eval(value) if value[:1] in ('"', "'") else value
    os.environ['OLENS_ALLOW_PAID_CALLS'] = '1'
    phase_path = getattr(args, 'transaction_phase_profile', None)
    if phase_path and (not preserve_guard or not getattr(args, 'performance_profile', None)):
        raise ValueError('Transaction phase capture requires guarded canary and terminal operational profile')
    with TransactionPhases(phase_path) as phases:
        return await dispatch(args, request, original, epoch, preserve_guard, phases)


async def dispatch(args, request, original, epoch, preserve_guard, phases):
    if phases.recorder is not None:
        phases.context = {'request_json_utf8_bytes':len(json.dumps(request, sort_keys=True).encode('utf-8')),
            'source_metadata_json_utf8_bytes':len(json.dumps(original, sort_keys=True).encode('utf-8')),
            'copy_diagnostic_metadata_json_utf8_bytes':len(json.dumps({'offline_disposable_diagnostic':True}, sort_keys=True).encode('utf-8')),
            'thread_scope':'Copied driver uses main thread; actual reserve thread is recorded after lane dispatch.'}
    ledger = AtomicBudget(args.ledger)
    phases.attach_ledger(ledger)
    ledger.set_run_limit(args.run_id, args.run_cap_usd)
    profile_path = getattr(args, 'performance_profile', None)
    profiler = OperationalProfile(profile_path, metadata={'concurrency':1}) if profile_path else None
    if profiler is not None:
        profiler.attach_ledger(ledger)
    client = make_luna_client(ledger,args.run_id,allow_paid=True,
        metadata={'purpose':'single-authorized-transport-healthcheck','source_unknown_attempt':args.attempt_id})
    started = time.monotonic()
    result = {'started_utc':datetime.now(timezone.utc).isoformat(), 'run_id':args.run_id,
        'original_unknown_attempt_id':args.attempt_id,'original_unknown_status_preserved':True,
        'content_cache_key':original['content_cache_key'],'physical_attempts_allowed':1,
        'source_semantics_unchanged':True,'primary_verdict_replaced':False,
        'transport_guard_preserved':preserve_guard,'recovery_epoch':epoch if preserve_guard else None}
    try:
        response = await client.chat.completions.create(**request,timeout=90)
        result.update(status='success', response_id=response.id,
            usage=response.usage.model_dump(mode='json'), response=response.model_dump(mode='json'))
    except BaseException as error:
        result.update(status='failed', cause_chain=safe_exception_chain(error))
    finally:
        try:
            await client.close()
        finally:
            if profiler is not None:
                profile = profiler.close(result.get('status', 'failed'))
    result['wall_seconds'] = time.monotonic() - started
    result['budget'] = ledger.snapshot()
    phases.status = result['status']
    if phases.output is not None:
        result['transaction_phase_profile'] = str(phases.output)
    if profiler is not None:
        metrics = profile['metrics']
        reservation = metrics.get('ledger.reserve_attempt', {}).get('maximum_seconds')
        heartbeat = metrics.get('event_loop.scheduling_lag', {}).get('maximum_seconds')
        result['performance_profile'] = str(profile_path)
        result['review_after_drain'] = {'reservation_max_seconds':reservation,
            'event_loop_max_lag_seconds':heartbeat, 'wall_seconds':result['wall_seconds'],
            'flagged':result['status']!='success' or result['wall_seconds']>60
                or (reservation is not None and reservation>2)
                or (heartbeat is not None and heartbeat>1),
            'scope':'Diagnostic thresholds after the single request and accounting drain; never cancel to enforce timing or claim throughput.'}
    with args.output.open('x') as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    return {key:value for key,value in result.items() if key not in ('response','budget')}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-paid',action='store_true')
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--run-cap-usd',required=True)
    parser.add_argument('--attempt-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preserve-recovery-guard',action='store_true',
                        help='Opt-in guarded canary; environment epoch must equal the retained source attempt epoch')
    parser.add_argument('--performance-profile',type=Path,
                        help='Fresh terminal operational profile; no content or financial changes')
    parser.add_argument('--transaction-phase-profile',type=Path,
                        help='Opt-in SQL phase timings for one guarded canary; requires terminal operational profile')
    args = parser.parse_args()
    result = asyncio.run(check(args))
    print(json.dumps(result))
    if result['status'] != 'success':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
