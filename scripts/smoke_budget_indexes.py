"""Bounded synthetic NFS locking check on a disposable ledger copy; no API."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import queue
import shutil
import sqlite3
import statistics
import time

from olens_improve.budget import AtomicBudget, cost_units


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def worker(path: str, index: int, cycles: int, replies) -> None:
    timings = []
    try:
        budget = AtomicBudget(path)
        for number in range(cycles):
            started = time.monotonic()
            key = f'offline-index-smoke-{index}-{number}'
            attempt = budget.reserve_attempt(100, 100, run_id='offline-index-smoke',
                metadata={'content_cache_key': key, 'synthetic_only': True})
            budget.record_evidence(attempt, 'physical_response',
                {'synthetic_only': True, 'response_id': key})
            budget.settle(attempt, input_tokens=10, output_tokens=5)
            with sqlite3.connect(path, timeout=30) as db:
                origin = db.execute("SELECT attempt_id FROM attempts WHERE status='settled' "
                    "AND json_extract(metadata,'$.content_cache_key')=? "
                    "ORDER BY created_utc DESC LIMIT 1", (key,)).fetchone()
                event = db.execute("SELECT details FROM events WHERE attempt_id=? "
                    "AND kind='physical_response' ORDER BY sequence DESC LIMIT 1", (attempt,)).fetchone()
            if origin != (attempt,) or json.loads(event[0])['response_id'] != key:
                raise AssertionError('Exact origin/event mismatch')
            timings.append(time.monotonic() - started)
        replies.put({'worker': index, 'cycles': len(timings), 'seconds': timings})
    except BaseException as error:
        replies.put({'worker': index, 'error_class': type(error).__name__})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--snapshot-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=float, default=120)
    args = parser.parse_args()
    if args.output.exists() or not 0 < args.timeout_seconds <= 180:
        raise SystemExit('Use a new disposable output directory and a bounded timeout')
    if digest(args.snapshot) != args.snapshot_sha256:
        raise SystemExit('Pristine snapshot hash changed')
    args.output.mkdir(parents=True)
    copied = args.output / 'synthetic-ledger.sqlite3'
    started = time.monotonic()
    shutil.copyfile(args.snapshot, copied)
    budget = AtomicBudget(copied)
    before = budget.snapshot()
    with sqlite3.connect(copied) as db:
        before_events = db.execute('SELECT count(*) FROM events').fetchone()[0]
    context = multiprocessing.get_context('spawn')
    replies = context.Queue()
    children = [context.Process(target=worker, args=(str(copied), index, 10, replies))
        for index in range(3)]
    for child in children:
        child.start()
    deadline = time.monotonic() + args.timeout_seconds
    results = []
    try:
        for _ in children:
            results.append(replies.get(timeout=max(.01, deadline - time.monotonic())))
        for child in children:
            child.join(max(.01, deadline - time.monotonic()))
    except queue.Empty:
        results.append({'error_class': 'BoundedSmokeTimeout'})
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
            child.join(5)
    after = budget.snapshot()
    with sqlite3.connect(copied) as db:
        smoke_counts = dict(db.execute('SELECT status,count(*) FROM attempts WHERE run_id=? '
            'GROUP BY status', ('offline-index-smoke',)))
        after_events = db.execute('SELECT count(*) FROM events').fetchone()[0]
    durations = [value for result in results for value in result.get('seconds', [])]
    complete = (len(durations) == 30 and all(child.exitcode == 0 for child in children)
        and not any('error_class' in result for result in results)
        and smoke_counts == {'settled': 30} and after_events - before_events == 90
        and round((after['actual_usd'] - before['actual_usd']) * 1e9) == 30 * cost_units(10, 5)
        and after['reserved_usd'] == before['reserved_usd']
        and after['unknown_usd'] == before['unknown_usd'])
    artifact = {'observed_utc': datetime.now(timezone.utc).isoformat(),
        'synthetic_only': True, 'network_model_calls': 0,
        'snapshot': str(args.snapshot), 'snapshot_sha256': args.snapshot_sha256,
        'disposable_ledger': str(copied), 'ledger_bytes': copied.stat().st_size,
        'processes': 3, 'cycles_per_process': 10, 'timeout_seconds': args.timeout_seconds,
        'wall_seconds': time.monotonic() - started, 'status': 'passed' if complete else 'failed',
        'results': results, 'exit_codes': [child.exitcode for child in children],
        'cycle_p50_seconds': statistics.median(durations) if durations else None,
        'cycle_p95_seconds': sorted(durations)[int(.95 * (len(durations) - 1))] if durations else None,
        'before': before, 'after': after, 'synthetic_attempt_counts': smoke_counts,
        'event_count_delta': after_events - before_events,
        'limits': ['This synthetic check does not establish provider latency or production throughput.',
            'Synthetic dollars exist only in the disposable copy and are not campaign spend.']}
    (args.output / 'report.json').write_text(json.dumps(artifact, indent=2) + '\n')
    print(json.dumps({key: artifact[key] for key in ('status', 'wall_seconds',
        'cycle_p50_seconds', 'cycle_p95_seconds', 'event_count_delta')}), flush=True)
    if not complete:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
