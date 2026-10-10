"""Time unchanged budget transactions on a hash-bound disposable copy only.

No network imports or calls. Root/compute supplies two copies of one consistent
baseline, one on NFS and one on local XFS. This script never opens production.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
import time
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.budget import AtomicBudget, usd_units

PRODUCTION = Path('${OLENS_DATA_ROOT}/budget/ledger.sqlite3')
ORIGINAL_CONNECT = sqlite3.connect


def digest(path):
    checksum = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def phase(sql):
    normalized = ' '.join(sql.upper().split())
    if normalized.startswith('PRAGMA'): return 'pragma.' + normalized.split()[1].split('=')[0].lower()
    if normalized.startswith('BEGIN'): return 'begin'
    if normalized == 'COMMIT': return 'commit'
    if normalized == 'ROLLBACK': return 'rollback'
    if "WHEN STATUS='SETTLED' THEN ACTUAL" in normalized:
        return 'body.committed.run' if 'WHERE RUN_ID=?' in normalized else 'body.committed.global'
    if 'ORDER BY CREATED_UTC DESC LIMIT 100' in normalized: return 'body.guard.recent'
    if "STATUS='UNKNOWN'" in normalized and 'CREATED_UTC>=?' in normalized: return 'body.guard.unknown_sum'
    if "SELECT VALUE FROM CONFIG WHERE KEY='HALTED'" in normalized: return 'body.halted_check'
    if 'SELECT CAP FROM RUN_LIMITS WHERE RUN_ID=?' in normalized: return 'body.run_cap'
    if normalized.startswith('INSERT INTO ATTEMPTS'): return 'body.insert_attempt'
    if normalized.startswith('INSERT INTO EVENTS'): return 'body.insert_event'
    if normalized.startswith('SELECT STATUS,RESERVED,ACTUAL FROM ATTEMPTS'): return 'body.settlement_lookup'
    if normalized.startswith('UPDATE ATTEMPTS SET STATUS='): return 'body.update_attempt'
    return 'body.other'


class Recorder:
    def __init__(self):
        self.operation = 'preflight'
        self.records = []

    def call(self, category, component, function, *args, **kwargs):
        started = time.perf_counter(); error = None
        try:
            return function(*args, **kwargs)
        except BaseException as exc:
            error = exc; raise
        finally:
            self.records.append({'operation':self.operation, 'phase':category,
                'component':component, 'seconds':time.perf_counter()-started,
                'exception_class':type(error).__name__ if error is not None else None,
                'sqlite_errorcode':getattr(error, 'sqlite_errorcode', None)})

    def connect(self, *args, **kwargs):
        recorder = self

        class TimedConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                category = phase(sql)
                cursor = recorder.call(category, 'execute', super().execute, sql, parameters)
                return TimedCursor(cursor, category, recorder)

            def close(self):
                return recorder.call('close', 'close', super().close)

        return self.call('connect', 'connect', ORIGINAL_CONNECT, *args,
                         **(kwargs | {'factory':TimedConnection}))


class TimedCursor:
    def __init__(self, cursor, category, recorder):
        self.cursor, self.category, self.recorder = cursor, category, recorder

    def fetchone(self):
        return self.recorder.call(self.category, 'fetchone', self.cursor.fetchone)

    def fetchall(self):
        return self.recorder.call(self.category, 'fetchall', self.cursor.fetchall)

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None: return
            yield row

    def close(self):
        return self.recorder.call(self.category, 'cursor_close', self.cursor.close)

    def __getattr__(self, name):
        return getattr(self.cursor, name)


def validate_copy(path, baseline_sha):
    path = path.resolve()
    # Hash equality alone must never authorize a production write. Require an
    # explicitly named diagnostic copy inside one of these small scratch roots.
    allowed = (str(path).startswith('/tmp/olens-ledger-reserve-phase-v1/') or
               str(path).startswith('/tmp/olens-ledger-reserve-phase-test-') or
               str(path).startswith('${OLENS_DATA_ROOT}/diagnostics/ledger-reserve-phase-v1/'))
    if not allowed or not path.name.endswith('-copy.sqlite3') or path == PRODUCTION.resolve():
        raise ValueError('Only explicitly named disposable phase-diagnostic copies are writable')
    if PRODUCTION.exists() and path.stat().st_dev == PRODUCTION.stat().st_dev and path.stat().st_ino == PRODUCTION.stat().st_ino:
        raise ValueError('Disposable copy must not be a production hard link')
    if digest(path) != baseline_sha:
        raise ValueError('Disposable copy differs from the immutable baseline hash')
    return path


def holdings(path, run_id):
    # Small covered aggregates; no prompt/response fields, no production path.
    with closing(ORIGINAL_CONNECT(f'file:{path}?mode=ro', uri=True, isolation_level=None)) as db:
        cursor = db.execute("SELECT COUNT(*),COALESCE(SUM(reserved),0) FROM attempts WHERE status='unknown'")
        try: unknown = cursor.fetchone()
        finally: cursor.close()
        cursor = db.execute('SELECT cap FROM run_limits WHERE run_id=?', (run_id,))
        try: cap = cursor.fetchone()
        finally: cursor.close()
        cursor = db.execute('SELECT key,value FROM config WHERE key IN (?,?,?)', ('hard','target','halted'))
        try: config = dict(cursor.fetchall())
        finally: cursor.close()
    if cap is None or cap[0] != usd_units('20') or config != {'hard':usd_units('300'), 'target':usd_units('200'), 'halted':0}:
        raise ValueError('Copy must preserve the original20/300/200 caps and unhalted state')
    return {'unknown_count':unknown[0], 'unknown_reserved_nanodollars':unknown[1]}


def run(args):
    if not args.allow_disposable_copy:
        raise ValueError('Explicit disposable-copy authorization required')
    if args.cycles not in (1, 2, 4) or not 0 < args.maximum_seconds <= 300:
        raise ValueError('Initial diagnostic is bounded to at most4 serial cycles and300 seconds')
    if args.run_id != 'development-full-grid-methods-v1' or args.epoch != '2026-10-10T07:52:00+00:00':
        raise ValueError('Keep the original development run and recovery guard epoch')
    if args.output.exists():
        raise ValueError('Preserve phase evidence; choose a fresh output')
    source_files = {'budget':Path(__file__).parents[1]/'src/olens_improve/budget.py',
                    'profiler':Path(__file__)}
    source_hashes = {name:digest(path) for name,path in source_files.items()}
    if source_hashes != {'budget':args.budget_source_sha256, 'profiler':args.profiler_source_sha256}:
        raise ValueError('Reviewed budget/profiler source hash differs before any database connection')
    path = validate_copy(args.copy, args.baseline_sha256)
    before = holdings(path, args.run_id)
    recorder = Recorder(); started = time.perf_counter(); cycles = []; status = 'completed'
    try:
        with patch('olens_improve.budget.sqlite3.connect', recorder.connect):
            recorder.operation = 'initialization'
            ledger = AtomicBudget(path)
            for index in range(args.cycles):
                if time.perf_counter()-started > args.maximum_seconds:
                    status = 'wall_bound_reached_after_drain'; break
                recorder.operation = f'reserve-{index}'
                tick = time.perf_counter()
                aid = ledger.reserve_attempt(1000, 100, run_id=args.run_id,
                    attempt_id='offline-phase-'+str(uuid.uuid4()),
                    metadata={'offline_disposable_diagnostic':True},
                    dispatch_guard={'since_utc':args.epoch})
                reserve_seconds = time.perf_counter()-tick
                recorder.operation = f'settle-{index}'
                tick = time.perf_counter()
                ledger.settle(aid, input_tokens=3, output_tokens=1)
                cycles.append({'index':index, 'reservation_seconds':reserve_seconds,
                               'synthetic_settlement_seconds':time.perf_counter()-tick})
    except Exception as exc:
        status = 'failed'
        failure = {'exception_class':type(exc).__name__, 'sqlite_errorcode':getattr(exc,'sqlite_errorcode',None)}
    after = holdings(path, args.run_id)
    if before != after:
        raise AssertionError('Historical unknown count or held amount changed on the disposable copy')
    output = {'schema_version':1,'status':status,'observed_utc':datetime.now(timezone.utc).isoformat(),
        'copy':str(path),'baseline_sha256':args.baseline_sha256,'filesystem_label':args.filesystem_label,
        'run_id':args.run_id,'epoch':args.epoch,'network_model_calls':0,'production_ledger_mutations':0,
        'wall_seconds':time.perf_counter()-started,'cycles_requested':args.cycles,'cycles':cycles,
        'historical_holdings_before':before,'historical_holdings_after':after,'records':recorder.records,
        'exception_counts':dict(Counter(r['exception_class'] for r in recorder.records if r['exception_class'])),
        'source_sha256':source_hashes,
        'source_unchanged_at_completion':all(digest(path)==source_hashes[name] for name,path in source_files.items()),
        'maximum_seconds_scope':'Drain/between-cycle bound; no mid-transaction interruption. It is not a hard process runtime limit.',
        'scope':'Unchanged AtomicBudget methods; SQLite call/fetch phase timings on a disposable copy only. Synthetic settlements are not API spend. File-local production lock contention, cache state and fsync tails may differ.'}
    if status == 'failed': output['failure'] = failure
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle: handle.write(json.dumps(output,indent=2)+'\n')
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-disposable-copy',action='store_true')
    parser.add_argument('--copy',type=Path,required=True)
    parser.add_argument('--baseline-sha256',required=True)
    parser.add_argument('--budget-source-sha256',required=True)
    parser.add_argument('--profiler-source-sha256',required=True)
    parser.add_argument('--filesystem-label',choices=('nfs','local_xfs','offline_fixture'),required=True)
    parser.add_argument('--run-id',default='development-full-grid-methods-v1')
    parser.add_argument('--epoch',default='2026-10-10T07:52:00+00:00')
    parser.add_argument('--cycles',type=int,default=2)
    parser.add_argument('--maximum-seconds',type=float,default=300)
    parser.add_argument('--output',type=Path,required=True)
    result = run(parser.parse_args())
    print(json.dumps({k:result[k] for k in ('status','wall_seconds','cycles_requested','network_model_calls')}))
    if result['status']=='failed': raise SystemExit(1)


if __name__ == '__main__': main()
