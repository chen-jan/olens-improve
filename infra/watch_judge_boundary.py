"""Stop one explicitly authorized worker only at an idle condition boundary.

This is an operational watcher, not a judge or a spending client. It never
prints process environments, API requests, provider URLs or exception text.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import sqlite3
import time
from datetime import datetime, timezone


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--family', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--maximum-seconds', type=float, default=1200)
    args = parser.parse_args()
    proc = Path('/proc') / str(args.pid)
    original = (proc / 'cmdline').read_bytes().split(b'\0')
    required = [b'olens_improve.evaluation', args.family.encode(), args.run_id.encode()]
    if any(token not in original for token in required):
        raise SystemExit('PID does not match the authorized evaluation worker')
    start_identity = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
    db = sqlite3.connect(f'file:{args.ledger}?mode=ro', uri=True, timeout=.05,
                         isolation_level=None)

    def current() -> dict | None:
        events = []
        for path in args.output.glob(f'*/{args.family}.execution.jsonl'):
            for line in path.read_text().splitlines():
                event = json.loads(line)
                if event.get('pid') == args.pid:
                    events.append(event)
        if not events:
            return None
        # Completed/failed events take precedence within the same condition.
        return max(events, key=lambda e: (e['started_utc'], e['status'] != 'running'))

    def reserved() -> int:
        cursor = db.execute("SELECT count(*) FROM attempts WHERE run_id=? AND status='reserved' "
            "AND json_extract(metadata,'$.pid')=?", (args.run_id, args.pid))
        try:
            return cursor.fetchone()[0]
        finally:
            cursor.close()

    def same_process() -> bool:
        return (proc / 'cmdline').read_bytes().split(b'\0') == original and (
            proc / 'stat').read_text().rsplit(')', 1)[1].split()[19] == start_identity

    try:
        deadline = time.monotonic() + args.maximum_seconds
        print(json.dumps({'status': 'watching', 'pid': args.pid, 'family': args.family}), flush=True)
        while time.monotonic() < deadline:
            try:
                if not same_process():
                    raise SystemExit('PID identity changed; no signal sent')
                event = current()
                if event is None or event['status'] != 'completed' or reserved():
                    time.sleep(.10)
                    continue
                frozen = False
                try:
                    # Freeze only the candidate boundary to make the ledger/event
                    # recheck safe against another dispatch from this process.
                    os.kill(args.pid, signal.SIGSTOP)
                    frozen = True
                    checked = current()
                    if same_process() and checked == event and reserved() == 0:
                        os.kill(args.pid, signal.SIGINT)
                        print(json.dumps({'status': 'idle_boundary_interrupt', 'pid': args.pid,
                            'family': args.family, 'condition': event['condition'],
                            'utc': datetime.now(timezone.utc).isoformat(),
                            'reserved_requests': 0}), flush=True)
                        return
                except sqlite3.OperationalError:
                    # Never hold a process stopped while waiting for an NFS lock.
                    pass
                finally:
                    if frozen:
                        os.kill(args.pid, signal.SIGCONT)
            except FileNotFoundError:
                print(json.dumps({'status': 'worker_already_exited', 'pid': args.pid}), flush=True)
                return
            time.sleep(.10)
        print(json.dumps({'status': 'no_safe_boundary_before_deadline', 'pid': args.pid}), flush=True)
    finally:
        db.close()


if __name__ == '__main__':
    main()
