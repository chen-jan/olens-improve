"""Reviewed, quiescent ledger DDL and separately audited abandoned holds; no API."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3

from olens_improve.budget import HOTPATH_INDEX_SQL


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def accounting(db: sqlite3.Connection) -> dict:
    rows = list(db.execute('SELECT attempt_id,run_id,status,reserved,actual,created_utc,updated_utc '
        'FROM attempts ORDER BY attempt_id'))
    committed = sum(row[4] if row[2] == 'settled' else row[3]
        if row[2] in ('reserved', 'unknown') else 0 for row in rows)
    return {'committed_nanodollars': committed,
        'financial_rows_sha256': hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
        'attempt_counts': dict(db.execute('SELECT status,count(*) FROM attempts GROUP BY status')),
        'event_count': db.execute('SELECT count(*) FROM events').fetchone()[0],
        'max_event_sequence': db.execute('SELECT max(sequence) FROM events').fetchone()[0],
        'config': list(db.execute('SELECT key,value FROM config ORDER BY key')),
        'run_limits': list(db.execute('SELECT run_id,cap FROM run_limits ORDER BY run_id'))}


def check_holds(db: sqlite3.Connection, spec: dict) -> None:
    expected = {row['attempt_id']: row for row in spec['abandoned_reservations']}
    actual = list(db.execute("SELECT attempt_id,status,reserved,metadata FROM attempts WHERE status='reserved'"))
    if {row[0] for row in actual} != set(expected):
        raise RuntimeError('Reserved IDs changed; a new quiescence review is required')
    for attempt, status, reserved, metadata in actual:
        known = expected[attempt]
        if (status, reserved, json.loads(metadata).get('pid')) != (
                known['prior_status'], known['reserved_nanodollars'], known['pid']):
            raise RuntimeError('Abandoned hold evidence changed')
        if db.execute("SELECT 1 FROM events WHERE attempt_id=? AND kind='physical_response' LIMIT 1",
                (attempt,)).fetchone():
            raise RuntimeError('Physical response exists; settlement evidence must be reviewed first')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--spec-sha256', required=True)
    parser.add_argument('--allow-apply', action='store_true')
    args = parser.parse_args()
    if not args.allow_apply or digest(args.spec) != args.spec_sha256:
        raise SystemExit('Explicit reviewed application and exact spec hash are required')
    spec = json.loads(args.spec.read_text())
    if str(os.environ.get('SLURM_JOB_ID')) != spec['job_id'] or socket.gethostname().split('.')[0] != spec['node']:
        raise SystemExit('Use the reviewed allocation/node')
    for pid in spec['confirmed_absent_worker_pids']:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        raise SystemExit('A reviewed worker PID exists; quiescence must be rechecked')
    ledger, snapshot, report = (Path(spec[key]) for key in ('ledger', 'prechange_snapshot', 'report'))
    if snapshot.exists() or report.exists():
        raise SystemExit('Preserve existing migration evidence; do not rerun')
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f'file:{ledger}?mode=ro', uri=True, timeout=30)
    before = accounting(source)
    check_holds(source, spec)
    destination = sqlite3.connect(snapshot)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    snapshot.chmod(0o444)
    snapshot_sha = digest(snapshot)
    with sqlite3.connect(snapshot) as frozen:
        if accounting(frozen) != before:
            raise RuntimeError('Prechange snapshot differs from the observed ledger')
    db = sqlite3.connect(ledger, timeout=30, isolation_level=None)
    try:
        if db.execute('PRAGMA journal_mode').fetchone()[0].casefold() != 'delete':
            raise RuntimeError('Unexpected ledger journal mode')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        if accounting(db) != before:
            raise RuntimeError('Ledger changed since backup; writer quiescence is not established')
        check_holds(db, spec)
        for statement in HOTPATH_INDEX_SQL:
            db.execute(statement)
        after_indexes = accounting(db)
        if after_indexes != before:
            raise RuntimeError('Index DDL changed accounting or events')
        db.execute('COMMIT')
        # This status-only transition is separate from the index identity check.
        db.execute('BEGIN IMMEDIATE')
        check_holds(db, spec)
        for row in spec['abandoned_reservations']:
            now = datetime.now(timezone.utc).isoformat()
            detail = {'reason': 'Owning worker exited without retained physical response; charge uncertain',
                'prior_status': row['prior_status'], 'reserved_nanodollars': row['reserved_nanodollars'],
                'dead_worker_pid': row['pid'], 'application_spec_sha256': args.spec_sha256,
                'classification': 'abandoned_reserved_to_unknown; full hold retained'}
            db.execute("UPDATE attempts SET status='unknown',updated_utc=? WHERE attempt_id=?",
                (now, row['attempt_id']))
            db.execute('INSERT INTO events(attempt_id,kind,details,utc) VALUES (?,?,?,?)',
                (row['attempt_id'], 'unknown', json.dumps(detail, sort_keys=True), now))
        after_holds = accounting(db)
        n = len(spec['abandoned_reservations'])
        if (after_holds['committed_nanodollars'] != before['committed_nanodollars']
                or after_holds['event_count'] != before['event_count'] + n
                or after_holds['max_event_sequence'] != before['max_event_sequence'] + n
                or after_holds['config'] != before['config'] or after_holds['run_limits'] != before['run_limits']
                or after_holds['attempt_counts'].get('reserved', 0) != 0):
            raise RuntimeError('Status transition accounting/event invariant failed')
        db.execute('COMMIT')
    except BaseException:
        if db.in_transaction:
            db.execute('ROLLBACK')
        raise
    finally:
        db.close()
    artifact = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'network_model_calls': 0,
        'status': 'applied', 'spec': str(args.spec), 'spec_sha256': args.spec_sha256,
        'script_sha256': digest(Path(__file__)), 'prechange_snapshot': str(snapshot),
        'prechange_snapshot_sha256': snapshot_sha, 'ledger': str(ledger),
        'index_sql': list(HOTPATH_INDEX_SQL), 'before': before, 'after_indexes': after_indexes,
        'after_abandoned_hold_classification': after_holds,
        'reclassified_ids': [row['attempt_id'] for row in spec['abandoned_reservations']],
        'financial_hold_released_nanodollars': 0, 'invoice_reconciled': False}
    report.write_text(json.dumps(artifact, indent=2) + '\n')
    report.chmod(0o444)
    print(json.dumps({'status': 'applied', 'report': str(report), 'report_sha256': digest(report),
        'prechange_snapshot_sha256': snapshot_sha, 'committed_nanodollars': before['committed_nanodollars'],
        'reclassified_count': len(spec['abandoned_reservations']), 'holds_released': 0}), flush=True)


if __name__ == '__main__':
    main()
