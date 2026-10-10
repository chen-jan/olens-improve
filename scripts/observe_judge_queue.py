"""Read-only, sanitized physical-response checkpoint for an existing queue."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import statistics


def summary(rows: list[dict], now: datetime) -> dict:
    states = Counter(row['status'] for row in rows)
    latest = sorted(rows, key=lambda row: row['created_utc'], reverse=True)[:100]
    latencies = sorted(row['latency_seconds'] for row in rows if row['latency_seconds'] is not None)
    first = min((row['created_utc'] for row in rows), default=None)
    elapsed = (now - datetime.fromisoformat(first)).total_seconds() if first else 0
    reserved = [row for row in rows if row['status'] == 'reserved']
    return {'attempt_counts': dict(states), 'first_attempt_utc': first,
        'elapsed_wall_seconds': elapsed,
        'settled_responses_per_minute': states['settled'] * 60 / elapsed if elapsed else None,
        'latest_100_unknown_count': sum(row['status'] == 'unknown' for row in latest),
        'unknown_reserved_nanodollars': sum(row['reserved'] for row in rows if row['status'] == 'unknown'),
        'active_reserved_nanodollars': sum(row['reserved'] for row in reserved),
        'actual_usage_nanodollars': sum(row['actual'] or 0 for row in rows if row['status'] == 'settled'),
        'oldest_active_age_seconds': max(((now - datetime.fromisoformat(row['created_utc'])).total_seconds()
            for row in reserved), default=None),
        'latency_p50_seconds': statistics.median(latencies) if latencies else None,
        'latency_p95_seconds': latencies[int(.95 * (len(latencies) - 1))] if latencies else None,
        'latency_observation_count': len(latencies),
        'sanitized_cause_counts': dict(Counter(row['cause'] for row in rows if row['cause']))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--epoch', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Preserve checkpoint evidence; choose a new output path')
    db = sqlite3.connect(f'file:{args.ledger}?mode=ro', uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('BEGIN')
    rows = [dict(row) for row in db.execute('SELECT attempt_id,status,reserved,actual,created_utc,updated_utc, '
        "json_extract(metadata,'$.pid') AS pid FROM attempts WHERE run_id=? AND created_utc>=? "
        'ORDER BY created_utc', (args.run_id, args.epoch))]
    for row in rows:
        response = db.execute("SELECT json_extract(details,'$.latency_s') FROM events WHERE attempt_id=? "
            "AND kind='physical_response' ORDER BY sequence DESC LIMIT 1", (row['attempt_id'],)).fetchone()
        row['latency_seconds'] = response[0] if response else None
        failure = db.execute("SELECT details FROM events WHERE attempt_id=? AND kind='transport_failure' "
            'ORDER BY sequence DESC LIMIT 1', (row['attempt_id'],)).fetchone()
        chain = json.loads(failure[0]).get('cause_chain', []) if failure else []
        row['cause'] = '>'.join(value['class'] for value in chain) or None
    db.rollback()
    db.close()
    now = datetime.now(timezone.utc)
    result = {'observed_utc': now.isoformat(), 'run_id': args.run_id, 'epoch': args.epoch,
        'network_model_calls': 0, 'all_workers': summary(rows, now),
        'workers': {str(pid): summary([row for row in rows if row['pid'] == pid], now)
            for pid in sorted({row['pid'] for row in rows if row['pid'] is not None})},
        'limits': ['Settled responses include malformed provider output that was still billed.',
            'This is physical transport health, not completed benchmark coverage or quality.',
            'Wall throughput includes cache/condition gaps; it does not guarantee future capacity.',
            'Old uncertain charges are retained and excluded only from this epoch observation.']}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    args.output.chmod(0o444)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
