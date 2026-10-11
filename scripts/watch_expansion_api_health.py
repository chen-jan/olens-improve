"""Separate lightweight worker aliveness/staleness sentinel; never dispatches API.

Observe on the allocated node so PID identity is meaningful. A stale running JSON
must not mask a dead worker. Recovery remains a separately reviewed pinned step.
"""
import argparse
import fcntl
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import time

FAMILIES=('hallucination','multihop_mt','chain_intermediates','role_bound_association')


def sha(path):return sha256(Path(path).read_bytes()).hexdigest()


def worker_health(state,now,proc_root=Path('/proc'),stale_seconds=600):
    pid=state.get('pid');proc=proc_root/str(pid);alive=proc.exists();identity=False;rss=None
    if alive:
        try:
            argv=(proc/'cmdline').read_bytes().split(b'\0');argv=[s.decode(errors='replace') for s in argv if s]
            identity=any(s.endswith('scripts/expanded_judges.py') for s in argv)
            identity=identity and state['inventory_sha256'] in argv and '--family' in argv and argv[argv.index('--family')+1]==state['family']
            for line in (proc/'status').read_text().splitlines():
                if line.startswith('VmRSS:'):rss=int(line.split()[1])*1024
        except (FileNotFoundError,ProcessLookupError):alive=False;identity=False
    last=state.get('last_successful_check_utc',state.get('started_utc'));age=max(0,now-last) if isinstance(last,(float,int)) else None
    stale=age is None or age>stale_seconds
    completed=len(state.get('completed',{}));terminal=completed==70 and not state.get('running',False)
    status='terminal' if terminal else 'dead_process' if not alive else 'pid_identity_mismatch' if not identity else 'stale_alive' if stale else 'healthy'
    return {'family':state['family'],'pid':pid,'status':status,'completed_condition_families':completed,
            'heartbeat_age_seconds':age,'stale':stale,'process_exists':alive,'pid_identity_valid':identity,
            'resident_bytes':rss,'current_descriptor':state.get('current_descriptor'),
            'recovery_required':status in ('dead_process','pid_identity_mismatch'),
            'note':'No restart or financial mutation performed. Stale-but-alive may be a busy condition; inspect progress before intervention.'}


def snapshot(root,inventory_sha,now=None,proc_root=Path('/proc')):
    now=time.time() if now is None else now;workers={}
    for family in FAMILIES:
        path=root/'judgments'/f'{family}.queue-state.json'
        if not path.exists():workers[family]={'status':'missing_queue_state','recovery_required':True};continue
        state=json.loads(path.read_bytes())
        if state['inventory_sha256']!=inventory_sha:raise ValueError('Worker state uses another frozen inventory')
        workers[family]=worker_health(state,now,proc_root)
    return {'status':'attention_required' if any(w.get('recovery_required') for w in workers.values()) else 'observed',
            'generated_utc':datetime.fromtimestamp(now,timezone.utc).isoformat(),'unix':now,
            'hostname':socket.gethostname(),'observer_pid':os.getpid(),'inventory_sha256':inventory_sha,
            'workers':workers,'dead_or_mismatched_workers':[f for f,w in workers.items() if w.get('recovery_required')],
            'stale_workers':[f for f,w in workers.items() if w.get('stale')],
            'inference_calls':0,'financial_holds_mutated':False,'automatic_restarts':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True);p.add_argument('--inventory-sha256',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--interval',type=int,default=60)
    p.add_argument('--once',action='store_true');a=p.parse_args()
    if os.environ.get('SLURM_JOB_ID')!='25536291' or sha(a.inventory)!=a.inventory_sha256:raise ValueError('Observe only on the current allocated API node and exact finite seal')
    if a.interval<60:raise ValueError('Avoid busy polling')
    # A stale receipt must not cause two observers to race on its temporary file.
    owner=a.output.with_suffix('.owner.lock').open('a+')
    try:fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('Another health observer owns this output')
    while True:
        row=snapshot(a.root,a.inventory_sha256);row['sentinel_sha256']=sha(__file__)
        temp=a.output.with_suffix('.tmp');temp.write_text(json.dumps(row,indent=2)+'\n');temp.replace(a.output)
        if row['dead_or_mismatched_workers']:print(json.dumps({'attention_required':row['dead_or_mismatched_workers'],'unix':row['unix']}),flush=True)
        if a.once or all(w.get('status')=='terminal' for w in row['workers'].values()):return
        time.sleep(a.interval)


if __name__=='__main__':main()
