"""Explicit one-family 16/400 ramp after a clean existing condition boundary."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

from resume_main_judges import digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--spec-sha256', required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--checkpoint-sha256', required=True)
    parser.add_argument('--family', choices=('hallucination','chain_intermediates','role_bound_association'), required=True)
    parser.add_argument('--prior-pid', type=int, required=True)
    parser.add_argument('--boundary-condition', required=True)
    parser.add_argument('--allow-paid', action='store_true')
    args = parser.parse_args()
    if not args.allow_paid or digest(args.spec) != args.spec_sha256 or digest(args.checkpoint) != args.checkpoint_sha256:
        raise SystemExit('Explicit reviewed ramp and exact source/checkpoint hashes required')
    spec = json.loads(args.spec.read_text())
    if str(os.environ.get('SLURM_JOB_ID')) != spec['job_id'] or socket.gethostname().split('.')[0] != spec['node']:
        raise SystemExit('Use the reviewed isolated allocation/node')
    for field in ('selections','manifest','conditions','healthcheck','incident','resource','index_application'):
        key = 'selection_sha256' if field=='selections' else field+'_sha256'
        if digest(Path(spec[field])) != spec[key]:
            raise SystemExit('Frozen source/evidence changed: '+field)
    checkpoint = json.loads(args.checkpoint.read_text())
    observed = checkpoint['workers'].get(str(args.prior_pid))
    if (checkpoint['run_id'] != spec['run_id'] or checkpoint['epoch'] != spec['recovery_epoch']
            or not observed or observed['attempt_counts'].get('settled',0) < 500
            or observed['attempt_counts'].get('unknown',0) or observed['latest_100_unknown_count']):
        raise SystemExit('Per-family sustained response health gate not met')
    if '/' in args.boundary_condition or args.boundary_condition in ('','.','..'):
        raise SystemExit('Invalid condition directory')
    history = Path(spec['judgments'])/args.boundary_condition/(args.family+'.execution.jsonl')
    boundary = json.loads(history.read_text().splitlines()[-1])
    if (boundary['status'] != 'completed' or boundary['pid'] != args.prior_pid
            or boundary['family'] != args.family or boundary['run_id'] != spec['run_id']):
        raise SystemExit('Prior family has not completed its reviewed condition')
    process = Path(f'/proc/{args.prior_pid}/stat')
    if process.exists() and process.read_text().rsplit(') ',1)[1].split()[0] != 'Z':
        raise SystemExit('Prior worker still active; preserve its in-flight work')
    incident = json.loads(Path(spec['incident']).read_text())
    with sqlite3.connect(f"file:{spec['ledger']}?mode=ro",uri=True,timeout=30) as db:
        cap = db.execute('SELECT cap FROM run_limits WHERE run_id=?',(spec['run_id'],)).fetchone()
        if cap is None or cap[0] != spec['run_cap_usd']*1e9:
            raise SystemExit('Frozen run cap differs')
        if db.execute("SELECT count(*) FROM attempts WHERE status='reserved' AND "
                "json_extract(metadata,'$.pid')=?",(args.prior_pid,)).fetchone()[0]:
            raise SystemExit('Prior worker still has active reservations')
        if db.execute("SELECT count(*) FROM attempts WHERE run_id=? AND created_utc>=? "
                "AND status='unknown'",(spec['run_id'],spec['recovery_epoch'])).fetchone()[0]:
            raise SystemExit('Recovery developed uncertain holds; fresh ramp review required')
        for attempt in incident['unknown_attempts']+incident.get('abandoned_reserved_attempts',[]):
            if db.execute('SELECT status FROM attempts WHERE attempt_id=?',(attempt['attempt_id'],)).fetchone() != ('unknown',):
                raise SystemExit('An original unknown hold changed')
    cpus = spec['cpu_pairs'][args.family]
    if not set(cpus)<=os.sched_getaffinity(0):
        raise SystemExit('Reviewed family cores unavailable')
    environment = os.environ.copy()
    environment['OLENS_TRANSPORT_RECOVERY_SINCE'] = spec['recovery_epoch']
    environment.update(PYTHONPATH='src',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
    log = Path(spec['logs'])/f'full-dev-judging-indexed16-{args.family}.log'
    command = ['taskset','-c',','.join(map(str,cpus)),sys.executable,'-m','olens_improve.evaluation',
        '--allow-paid','--family',args.family,'--selections',spec['selections'],'--manifest',spec['manifest'],
        '--output',spec['judgments'],'--method','raw_n1','--n','1',
        '--condition-list',spec['conditions'],'--run-id',spec['run_id'],'--run-cap-usd',str(spec['run_cap_usd']),
        '--ledger',spec['ledger'],'--tier',spec['tier'],'--concurrency','16','--rpm','400',
        '--shared-cache',spec['shared_cache'],'--stop-file',str(Path(spec['judgments'])/f'stop-indexed16-{args.family}')]
    with log.open('a') as handle:
        worker = subprocess.Popen(command,stdout=handle,stderr=subprocess.STDOUT,env=environment)
    print(json.dumps({'family':args.family,'pid':worker.pid,'transport':{'concurrency':16,'rpm':400},
        'epoch':spec['recovery_epoch'],'spec_sha256':args.spec_sha256,
        'checkpoint_sha256':args.checkpoint_sha256,'completed_boundary':args.boundary_condition,
        'boundary_history_sha256':digest(history),'log':str(log)}),flush=True)
    raise SystemExit(worker.wait())


if __name__ == '__main__':
    main()
