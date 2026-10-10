"""Bounded read-only operational checkpoint; never contacts a model endpoint."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import statistics
import time


def summarize(rows, now):
    states = Counter(row['status'] for row in rows)
    latest = sorted(rows, key=lambda row: row['created_utc'], reverse=True)[:100]
    observed = [row for row in rows if row.get('diagnostic_observed')]
    latencies = sorted(row['latency_seconds'] for row in observed
                       if row['latency_seconds'] is not None)
    first = min((row['created_utc'] for row in rows), default=None)
    elapsed = (now - datetime.fromisoformat(first)).total_seconds() if first else 0
    reserved = [row for row in rows if row['status'] == 'reserved']
    return {
        'attempt_counts': dict(states), 'first_attempt_utc': first,
        'elapsed_wall_seconds': elapsed,
        'settled_responses_per_minute': states['settled'] * 60 / elapsed if elapsed else None,
        'latest_100_unknown_count': sum(row['status'] == 'unknown' for row in latest),
        'unknown_reserved_nanodollars': sum(row['reserved'] for row in rows if row['status'] == 'unknown'),
        'active_reserved_nanodollars': sum(row['reserved'] for row in reserved),
        'actual_usage_nanodollars': sum(row['actual'] or 0 for row in rows if row['status'] == 'settled'),
        'oldest_active_age_seconds': max(((now - datetime.fromisoformat(row['created_utc'])).total_seconds()
                                         for row in reserved), default=None),
        'recent_latency_p50_seconds': statistics.median(latencies) if latencies else None,
        'recent_latency_p95_seconds': latencies[int(.95 * (len(latencies)-1))] if latencies else None,
        'recent_latency_observation_count': len(latencies),
        'sanitized_epoch_cause_counts': dict(Counter(row['cause'] for row in observed if row['cause'])),
    }


def fetch(db, sql, parameters=()):
    cursor = db.execute(sql, parameters)
    try:
        return [dict(row) for row in cursor]
    finally:
        cursor.close()


def active_pid_checkpoint(db, run_id, epoch, pids, *, now=None, worker_since=None):
    """Exact run aggregates and bounded active-worker windows, without DDL."""
    worker_since = worker_window_start(epoch, worker_since)
    aggregate = fetch(db,
        'SELECT status,COUNT(*) AS count,COALESCE(SUM(reserved),0) AS reserved,'
        'COALESCE(SUM(actual),0) AS actual FROM attempts INDEXED BY attempts_run_committed '
        'WHERE run_id=? GROUP BY status', (run_id,))
    states = {row['status']:row['count'] for row in aggregate}
    amounts = {row['status']:row for row in aggregate}
    first = fetch(db, 'SELECT MIN(created_utc) AS first FROM attempts INDEXED BY '
                  'attempts_run_recovery WHERE run_id=?', (run_id,))[0]['first']
    oldest = fetch(db, 'SELECT MIN(created_utc) AS oldest FROM attempts INDEXED BY '
                   "attempts_run_committed WHERE run_id=? AND status='reserved'", (run_id,))[0]['oldest']
    fields = ("attempt_id,status,reserved,actual,created_utc,"
              "json_extract(metadata,'$.pid') AS pid")
    unknown = fetch(db, 'SELECT '+fields+' FROM attempts INDEXED BY attempts_run_committed '
                    "WHERE run_id=? AND status='unknown' ORDER BY created_utc", (run_id,))
    recent = fetch(db, 'SELECT '+fields+' FROM attempts INDEXED BY attempts_run_recovery '
                   'WHERE run_id=? AND created_utc>=? ORDER BY created_utc DESC LIMIT 100',
                   (run_id, epoch))
    workers = {str(pid):fetch(db, 'SELECT '+fields+' FROM attempts INDEXED BY attempts_run_recovery '
        "WHERE run_id=? AND created_utc>=? AND json_extract(metadata,'$.pid')=? "
        'ORDER BY created_utc DESC LIMIT 100', (run_id, worker_since, pid)) for pid in sorted(set(pids))}
    selected = {row['attempt_id']:row for row in unknown+recent}
    for rows in workers.values():
        selected.update({row['attempt_id']:row for row in rows})
    latency_ids = {row['attempt_id'] for rows in workers.values() for row in rows}
    for row in selected.values():
        event = fetch(db,
            "SELECT (SELECT json_extract(details,'$.latency_s') FROM events WHERE attempt_id=? "
            "AND kind='physical_response' ORDER BY sequence DESC LIMIT 1) AS latency, "
            "(SELECT json_extract(details,'$.cause_chain') FROM events WHERE attempt_id=? "
            "AND kind='transport_failure' ORDER BY sequence DESC LIMIT 1) AS cause_chain",
            (row['attempt_id'], row['attempt_id']))[0]
        row['diagnostic_observed'] = True
        row['latency_seconds'] = event['latency'] if row['attempt_id'] in latency_ids else None
        chain = json.loads(event['cause_chain']) if event['cause_chain'] else []
        row['cause'] = '>'.join(value['class'] for value in chain) or None
    # Unify rows by ID so all bounded views share the same retained observations.
    workers = {pid:[selected[row['attempt_id']] for row in rows] for pid,rows in workers.items()}
    now = now or datetime.now(timezone.utc)
    total = summarize(list(selected.values()), now)
    elapsed = (now-datetime.fromisoformat(first)).total_seconds() if first else 0
    total.update(attempt_counts=states, first_attempt_utc=first, elapsed_wall_seconds=elapsed,
        settled_responses_per_minute=states.get('settled',0)*60/elapsed if elapsed else None,
        latest_100_unknown_count=sum(row['status']=='unknown' for row in recent),
        unknown_reserved_nanodollars=amounts.get('unknown',{}).get('reserved',0),
        active_reserved_nanodollars=amounts.get('reserved',{}).get('reserved',0),
        actual_usage_nanodollars=amounts.get('settled',{}).get('actual',0),
        oldest_active_age_seconds=(now-datetime.fromisoformat(oldest)).total_seconds() if oldest else None)
    total['sanitized_epoch_cause_counts'] = dict(Counter(row['cause'] for row in selected.values()
        if row['status']=='unknown' and row['created_utc']>=epoch and row['cause']))
    total['recent_physical_response_latency_samples'] = sum(row['latency_seconds'] is not None
                                                          for row in selected.values())
    output_workers = {}
    for pid, rows in workers.items():
        summary = summarize(rows, now)
        summary['status_scope'] = 'Latest at most 100 attempts for this requested PID after worker_since_utc; not cumulative worker counts.'
        summary['worker_since_utc'] = worker_since
        summary['window_coverage'] = {'requested_attempts':100, 'available_attempts':len(rows),
            'physical_response_latencies_observed':sum(row['latency_seconds'] is not None for row in rows),
            'missing_latency_samples':sum(row['latency_seconds'] is None for row in rows)}
        output_workers[pid] = summary
    return {'monitor_mode':'indexed_active_pid', 'run_id':run_id, 'epoch':epoch,
        'network_model_calls':0, 'active_pids':sorted(set(pids)), 'worker_since_utc':worker_since,
        'aggregate_scope':'Exact complete-run status aggregates; separate from epoch-filtered recent windows.',
        'status_snapshot':'Run aggregate, bounded attempts and events are separate autocommit read snapshots.',
        'latency_window':'Latest at most 100 attempts since the explicitly recorded worker bound per requested active PID; inactive-worker latency omitted.',
        'all_workers':total, 'workers':output_workers,
        'unknown_attempts':[{'attempt_id':row['attempt_id'],'pid':row['pid'],
            'created_utc':row['created_utc'],'reserved_nanodollars':row['reserved'],'cause':row['cause']}
            for row in selected.values() if row['status']=='unknown'],
        'limits':['No ledger/evaluator change or epoch reset; existing indexes only.',
            'Optional worker start bounds only PID windows; full-run totals, epoch guard window and retained unknowns keep the original scope.',
            'Worker counts and rates describe bounded recent windows, not cumulative worker throughput.',
            'Missing latency includes in-flight attempts or absent physical-response evidence.',
            'Settled can include malformed paid responses; this is not scientific coverage.',
            'All run unknown holds and their available causes are retained; no invoice reconciliation.']}


def worker_window_start(epoch, worker_since):
    if worker_since is None:
        return epoch
    start = datetime.fromisoformat(worker_since.replace('Z', '+00:00'))
    original = datetime.fromisoformat(epoch.replace('Z', '+00:00'))
    if start.utcoffset() is None or original.utcoffset() is None or start < original:
        raise ValueError('Worker start must be an aware timestamp at or after the unchanged recovery epoch')
    return start.astimezone(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--epoch', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--active-pid', type=int, action='append',
                        help='Optional bounded active-worker path; exact run aggregates use existing covering indexes')
    parser.add_argument('--worker-since', help='Known worker start UTC bound for PID windows only; leaves run totals/guard epoch unchanged')
    args = parser.parse_args()
    if args.worker_since and not args.active_pid:
        raise ValueError('Worker start requires explicit active PIDs')
    worker_window_start(args.epoch, args.worker_since)
    if args.output.exists():
        raise SystemExit('Preserve checkpoint evidence; choose a new output path')
    started = time.monotonic()
    db = sqlite3.connect(f'file:{args.ledger}?mode=ro', uri=True, timeout=30, isolation_level=None)
    try:
        write_checkpoint(args, db, started)
    finally:
        # Normal paths close before formatting/writing; errors must also close.
        db.close()


def write_checkpoint(args, db, started):
    db.row_factory = sqlite3.Row
    if args.active_pid:
        result = active_pid_checkpoint(db, args.run_id, args.epoch, args.active_pid,
                                       worker_since=args.worker_since)
        db.close()
        result.update(observed_utc=datetime.now(timezone.utc).isoformat(),
                      total_read_query_seconds=time.monotonic()-started)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        args.output.chmod(0o444)
        print(json.dumps(result), flush=True)
        return
    # Fetch only compact attempt metadata, then release the shared read lock.
    cursor = db.execute(
        "SELECT attempt_id,status,reserved,actual,created_utc,json_extract(metadata,'$.pid') AS pid "
        'FROM attempts WHERE run_id=? AND created_utc>=? ORDER BY created_utc',
        (args.run_id, args.epoch))
    rows = [dict(row) for row in cursor]
    cursor.close()
    counts_finished = time.monotonic()
    recent_ids = set()
    for pid in {row['pid'] for row in rows}:
        matching = [row for row in rows if row['pid'] == pid]
        recent_ids.update(row['attempt_id'] for row in matching[-100:])
    # All uncertain attempts retain cause evidence; response latency is bounded
    # to the latest 100 attempts per PID instead of loading every large response.
    selected = [row for row in rows if row['attempt_id'] in recent_ids or row['status'] == 'unknown']
    for row in selected:
        cursor = db.execute(
            "SELECT (SELECT json_extract(details,'$.latency_s') FROM events WHERE attempt_id=? "
            "AND kind='physical_response' ORDER BY sequence DESC LIMIT 1) AS latency, "
            "(SELECT json_extract(details,'$.cause_chain') FROM events WHERE attempt_id=? "
            "AND kind='transport_failure' ORDER BY sequence DESC LIMIT 1) AS cause_chain",
            (row['attempt_id'], row['attempt_id']))
        event = cursor.fetchone()
        cursor.close()
        row['diagnostic_observed'] = True
        # Older unknown rows contribute causes without expanding latency window.
        row['latency_seconds'] = event['latency'] if row['attempt_id'] in recent_ids else None
        chain = json.loads(event['cause_chain']) if event['cause_chain'] else []
        row['cause'] = '>'.join(value['class'] for value in chain) or None
    db.close()
    now = datetime.now(timezone.utc)
    result = {
        'observed_utc': now.isoformat(), 'run_id': args.run_id, 'epoch': args.epoch,
        'network_model_calls': 0, 'attempt_metadata_query_seconds': counts_finished-started,
        'total_read_query_seconds': time.monotonic()-started,
        'status_snapshot': 'Attempt states fetched once; bounded subsequent event reads may occur later.',
        'latency_window': 'Latest 100 physical attempts per PID; not the full epoch distribution.',
        'all_workers': summarize(rows, now),
        'workers': {str(pid): summarize([row for row in rows if row['pid'] == pid], now)
                    for pid in sorted({row['pid'] for row in rows if row['pid'] is not None})},
        'limits': ['Read-only point lookups release their lock before Python summary work.',
                   'Settled may include malformed paid responses; this is not scientific coverage.',
                   'Old uncertain charges remain held; this observation does not reconcile invoices.'],
    }
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    args.output.chmod(0o444)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
