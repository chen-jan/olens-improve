"""Low-cost periodic read-only checks inside the project's CPU allocation."""
import argparse
from datetime import datetime, timezone
import json
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runtime', default='configs/runtime.json')
    p.add_argument('--interval', type=int, default=600)
    p.add_argument('--stop-utc', required=True)
    a=p.parse_args()
    runtime=json.loads(Path(a.runtime).read_text())
    if os.environ.get('SLURM_JOB_ID') != str(runtime['cpu_allocation']['job_id']):
        raise RuntimeError('Run the watcher inside the assigned CPU allocation')
    if a.interval < 60: raise ValueError('Avoid overly frequent cluster probes')
    stop=datetime.fromisoformat(a.stop_utc.replace('Z','+00:00'))
    folder=Path(runtime['paths']['fast'])/'watcher';folder.mkdir(exist_ok=True)
    lock=(folder/'loop.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
    heartbeat=folder/'loop.json'
    stopping=False
    def requested(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM, requested);signal.signal(signal.SIGINT, requested)
    def record(state, **extra):
        tmp=heartbeat.with_suffix('.tmp')
        tmp.write_text(json.dumps({'state':state,'pid':os.getpid(),'job_id':os.environ['SLURM_JOB_ID'],'checked_utc':datetime.now(timezone.utc).isoformat(),'interval_seconds':a.interval,'stop_utc':a.stop_utc,**extra},indent=2)+'\n')
        tmp.replace(heartbeat)
    while not stopping and datetime.now(timezone.utc) < stop:
        record('checking')
        try:
            code=subprocess.run([sys.executable,str(Path(__file__).with_name('watch_resources.py')),'--runtime',a.runtime],timeout=120).returncode
        except subprocess.TimeoutExpired:
            code=124
            print('Resource check timed out; retry at the next interval',flush=True)
        next_check=time.monotonic()+a.interval
        record('waiting',last_check_exit_code=code)
        while not stopping and time.monotonic() < next_check and datetime.now(timezone.utc) < stop:
            time.sleep(min(1,next_check-time.monotonic()))
    record('stopped')

if __name__=='__main__':main()
