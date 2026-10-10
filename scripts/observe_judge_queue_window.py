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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--epoch', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Preserve checkpoint evidence; choose a new output path')
    started = time.monotonic()
    db = sqlite3.connect(f'file:{args.ledger}?mode=ro', uri=True, timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
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
