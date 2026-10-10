"""Freeze sanitized ledger/execution evidence; never contact a model endpoint."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--judgments', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--epoch', help='Also report this reviewed recovery epoch separately')
    parser.add_argument('--confirmed-absent-pid', action='append', type=int, default=[])
    parser.add_argument('--incident-kind', default='transport_guard')
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Incident snapshot already exists; preserve it and use a new version')
    db = sqlite3.connect(f'file:{args.ledger}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('BEGIN')
    run = args.run_id
    states = Counter(dict(db.execute('SELECT status,count(*) FROM attempts WHERE run_id=? GROUP BY status', (run,))))
    unknowns = []
    abandoned = []
    cause_counts = Counter()
    failures = {row['attempt_id']: row for row in db.execute(
        "SELECT e.attempt_id,e.details,e.utc FROM events e JOIN attempts a ON a.attempt_id=e.attempt_id "
        "WHERE a.run_id=? AND e.kind='transport_failure' ORDER BY e.sequence", (run,))}
    response_ids = {row[0] for row in db.execute(
        "SELECT DISTINCT e.attempt_id FROM events e JOIN attempts a ON a.attempt_id=e.attempt_id "
        "WHERE a.run_id=? AND e.kind='physical_response'", (run,))}
    for row in db.execute("SELECT * FROM attempts WHERE run_id=? AND status='unknown' ORDER BY created_utc", (run,)):
        metadata = json.loads(row['metadata'])
        req = metadata.get('request', {})
        failure = failures.get(row['attempt_id'])
        details = json.loads(failure['details']) if failure else {}
        causes = [{'class': x['class'], 'errno': x.get('errno')} for x in details.get('cause_chain', [])]
        cause_counts['>'.join(x['class'] for x in causes) or 'not_recorded'] += 1
        unknowns.append({'attempt_id':row['attempt_id'], 'pid':metadata.get('pid'),
            'created_utc':row['created_utc'], 'unknown_utc':row['updated_utc'],
            'reserved_usd':row['reserved']/1e9, 'actual_usd':None,
            'content_cache_key':metadata.get('content_cache_key'),
            'schema_name':req.get('response_format', {}).get('json_schema', {}).get('name'),
            'requested_tier':metadata.get('requested_tier'),
            'latency_seconds':details.get('latency_s'), 'cause_chain':causes})
    for row in db.execute("SELECT * FROM attempts WHERE run_id=? AND status='reserved' ORDER BY created_utc", (run,)):
        metadata = json.loads(row['metadata'])
        pid = metadata.get('pid')
        abandoned.append({'attempt_id':row['attempt_id'], 'prior_status':row['status'],
            'reserved_nanodollars':row['reserved'], 'pid':pid, 'created_utc':row['created_utc'],
            'has_physical_response':row['attempt_id'] in response_ids,
            'classification':'abandoned_uncertain_hold' if pid in args.confirmed_absent_pid else 'unverified_owner',
            'amount_released_nanodollars':0})
    epoch_counts = dict(db.execute('SELECT status,count(*) FROM attempts WHERE run_id=? AND created_utc>=? '
        'GROUP BY status', (run,args.epoch))) if args.epoch else None
    actual = db.execute("SELECT COALESCE(SUM(actual),0) FROM attempts WHERE run_id=? AND status='settled'", (run,)).fetchone()[0]/1e9
    reserved = db.execute("SELECT COALESCE(SUM(reserved),0) FROM attempts WHERE run_id=? AND status='reserved'", (run,)).fetchone()[0]/1e9
    run_cap = db.execute('SELECT cap FROM run_limits WHERE run_id=?', (run,)).fetchone()[0]/1e9
    last_sequence = db.execute('SELECT max(sequence) FROM events').fetchone()[0]
    db.rollback()
    execution = []
    for path in sorted(args.judgments.glob('*/*.execution.jsonl')):
        raw = path.read_bytes()
        latest = json.loads(raw.decode().splitlines()[-1])
        execution.append({'path':str(path), 'sha256':hashlib.sha256(raw).hexdigest(), 'latest':latest})
    artifact = {'schema_version':1, 'observed_utc':datetime.now(timezone.utc).isoformat(),
        'run_id':run, 'ledger_path':str(args.ledger), 'ledger_event_sequence':last_sequence,
        'ledger_invoice_reconciled':False, 'attempt_counts':dict(states),
        'actual_usage_usd':actual, 'active_reserved_usd':reserved,
        'unknown_reserved_usd':sum(row['reserved_usd'] for row in unknowns),
        'run_cap_usd':run_cap, 'sanitized_cause_counts':dict(cause_counts),
        'unknown_attempts':unknowns, 'abandoned_reserved_attempts':abandoned,
        'confirmed_absent_worker_pids':args.confirmed_absent_pid,
        'epoch':args.epoch, 'epoch_attempt_counts':epoch_counts, 'incident_kind':args.incident_kind,
        'execution_sidecars':execution,
        'interpretation':'Dispatch stopped; monetary ceiling was not exceeded. Full uncertain holds remain committed. Successful exact verdicts are retained; affected conditions are incomplete.',
        'limits':['No API payloads, exception messages, endpoint URLs or credentials are included.',
            'Causes are unresolved; concurrency, cgroup pressure and timestamps do not establish causation.',
            'Guard cancellation adds uncertain holds to the original failed physical requests.',
            'The old recovery epoch and all holds remain intact until an explicitly reviewed recovery.']}
    with args.output.open('x') as handle:
        json.dump(artifact, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'output':str(args.output), 'attempt_counts':dict(states),
        'actual_usage_usd':actual, 'unknown_usd':artifact['unknown_reserved_usd'],
        'cause_counts':dict(cause_counts)}))


if __name__ == '__main__':
    main()
