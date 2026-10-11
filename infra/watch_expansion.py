"""Monitor expansion-owned jobs and receipts outside the preemptable GPU."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        return {'unavailable': str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', nargs='+', required=True)
    parser.add_argument('--cpu-job', required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--progress', type=Path, nargs='*', default=[])
    parser.add_argument('--interval', type=int, default=60)
    parser.add_argument('--hours', type=float, default=23.5)
    parser.add_argument('--config', type=Path, default=Path('.state/expansion-monitor-input-v1.json'))
    parser.add_argument('--cpu-core', type=int)
    args = parser.parse_args()
    if os.environ.get('SLURM_JOB_ID') != args.cpu_job:
        raise RuntimeError('Monitor requires its assigned CPU allocation')
    if args.interval < 60:
        raise ValueError('Cluster checks must be at least a minute apart')
    if args.cpu_core is not None:
        if args.cpu_core not in os.sched_getaffinity(0):
            raise RuntimeError('Monitor core is outside the assigned allocation')
        os.sched_setaffinity(0, {args.cpu_core})
    args.state.parent.mkdir(parents=True, exist_ok=True)
    lock = args.state.with_suffix('.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    deadline = time.monotonic() + args.hours * 3600
    receipt = {}
    while not stopping and time.monotonic() < deadline:
        started = time.monotonic()
        config = load(args.config) if args.config.exists() else {}
        jobs = config.get('jobs', args.jobs)
        paths = [Path(path) for path in config.get('progress', args.progress)]
        try:
            result = subprocess.run(['squeue', '-h', '-j', ','.join(map(str, jobs)),
                                     '-o', '%i|%T|%R|%M|%l'],
                                    capture_output=True, text=True, timeout=20)
            scheduler = {'returncode': result.returncode, 'rows': result.stdout.splitlines(),
                         'stderr': result.stderr[-1000:]}
        except (OSError, subprocess.TimeoutExpired) as error:
            scheduler = {'error': str(error)}
        progress = {str(path): load(path) for path in paths}
        alerts = [str(path) + ': ' + str(body.get('status'))
                  for path, body in progress.items()
                  if body.get('status') in ('failed', 'blocked')]
        for path, body in progress.items():
            if any(worker.get('exit_code') not in (None, 0) for worker in body.get('workers', [])):
                alerts.append(path + ': a worker exited with an error')
        receipt = {'utc': datetime.now(timezone.utc).isoformat(),
                   'pid': os.getpid(), 'cpu_job': args.cpu_job,
                   'status': 'monitoring', 'scheduler': scheduler,
                   'progress': progress, 'alerts': alerts,
                   'monitor_seconds': time.monotonic() - started}
        temp = args.state.with_suffix('.tmp')
        temp.write_text(json.dumps(receipt, indent=2) + '\n')
        os.replace(temp, args.state)
        remaining = args.interval - (time.monotonic() - started)
        while not stopping and remaining > 0:
            time.sleep(min(1, remaining))
            remaining = args.interval - (time.monotonic() - started)
    receipt['status'] = 'stopped'
    receipt['utc'] = datetime.now(timezone.utc).isoformat()
    args.state.write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
