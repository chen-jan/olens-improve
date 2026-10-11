"""Wait for immutable role likelihood selections, then run one additive replay."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

from expanded_cpu_cached import atomic, sha, committed_lines


def main():
    p=argparse.ArgumentParser();p.add_argument('--pins',type=Path,required=True);p.add_argument('--pins-sha256',required=True)
    p.add_argument('--state',type=Path,required=True);p.add_argument('--python',required=True);a=p.parse_args()
    if os.environ.get('SLURM_JOB_ID')!='25536417':raise RuntimeError('Use owned CPU allocation')
    if sha(a.pins)!=a.pins_sha256:raise ValueError('Role addon authority changed')
    pins=json.loads(a.pins.read_text())['source_sha256']
    def check():
        if any(sha(path)!=value for path,value in pins.items()):raise ValueError('Role addon implementation changed')
    check();inventory=json.loads(Path('configs/expansion_manifest_v1.json').read_text());seal=sha('configs/expansion_manifest_v1.json')
    root=Path(inventory['artifact_root']);ready=root/'selections/likelihood-v1/role_bound_association.ready.json'
    snapshot=Path('.state/reconstruction-replay-role-addon-snapshot-v1');output=root/'reconstruction/replay-role-addon-v1/shard0'
    lock=a.state.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state={'status':'waiting_for_role_likelihood_descriptor','pid':os.getpid(),'slurm_job_id':os.environ['SLURM_JOB_ID'],
        'started_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':pins,'output':str(output),'new_model_calls':0,'new_api_calls':0}
    start=time.monotonic()
    try:
        while not ready.exists():
            check();state['updated_utc']=datetime.now(timezone.utc).isoformat();atomic(a.state,state)
            if time.monotonic()-start>21600:state['status']='timeout_no_snapshot';atomic(a.state,state);return
            time.sleep(20)
        d=json.loads(ready.read_text());expected={('likelihood_true_minus_mean_two_controls',8),('own_mean_log_likelihood',8),('control_mean_log_likelihood',8)}
        if d['family']!='role_bound_association' or d['ready']is not True or d['inventory_sha256']!=seal or {(c['method'],c['n'])for c in d['conditions']}!=expected:raise ValueError('Role likelihood descriptor menu differs')
        source_pins={str(ready):sha(ready),d['manifest']:d['manifest_sha256'],d['selections']:d['selection_sha256']}
        if any(sha(p)!=h for p,h in source_pins.items()):raise ValueError('Role selection source changed')
        fresh=json.loads(Path(inventory['fresh_manifest']['path']).read_text());own={c['cell_id']:c for c in fresh['cells']if c['family']=='role_bound_association'};seen=set()
        for row in committed_lines(d['selections']):
            cid=row['cell_id']
            if cid in seen or cid not in own or any(row[k]!=own[cid][k]for k in ('family','item_id','layer','position','split','activation_sha256')):raise ValueError('Role likelihood cohort identity differs')
            if {(s['method'],s['n'])for s in row['selections']}!=expected:raise ValueError('Role likelihood site menu differs')
            seen.add(cid)
        if seen!=set(own):raise ValueError('Role likelihood incomplete original grid')
        snapshot.mkdir(exist_ok=True);destination=snapshot/ready.name
        if destination.exists()and sha(destination)!=source_pins[str(ready)]:raise ValueError('Role immutable descriptor snapshot changed')
        if not destination.exists():destination.write_bytes(ready.read_bytes());destination.chmod(0o444)
        receipt=snapshot/'receipt.json';data={'inventory_sha256':seal,'scope':'role likelihood three recipes only; existing vectors replay v2',
            'sources':[{'path':str(ready),'sha256':source_pins[str(ready)],'snapshot':str(destination.resolve())}],'selection_source_sha256':source_pins}
        if receipt.exists()and json.loads(receipt.read_text())!=data:raise ValueError('Role addon snapshot receipt changed')
        if not receipt.exists():atomic(receipt,data)
        command=[a.python,'scripts/expanded_reconstruction_replay_v2.py','--inventory-sha256',seal,'--ready-directory',str(snapshot.resolve()),
            '--output',str(output),'--shard-index','0','--shard-count','1','--threads','4']
        if (output/'status.json').exists()and json.loads((output/'status.json').read_text()).get('status')=='complete':
            terminal=json.loads((output/'status.json').read_text());state['status']='complete_reused'
        else:
            state.update(status='replaying_role_likelihood',command=command,snapshot_receipt_sha256=sha(receipt),updated_utc=datetime.now(timezone.utc).isoformat());atomic(a.state,state)
            with a.state.with_suffix('.log').open('a')as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=False)
            if result.returncode:raise RuntimeError(f'Role replay exited {result.returncode}')
            terminal=json.loads((output/'status.json').read_text());state['status']='complete'
        check()
        if terminal['status']!='complete'or terminal['completed_cells']!=len(own)or terminal['expected_cells']!=len(own)or sha(output/'fits.jsonl')!=terminal['fits_sha256']:raise ValueError('Role replay terminal count/journal differs')
        for path,value in terminal['source_sha256'].items():
            if sha(path)!=value:raise ValueError('Role replay terminal source changed')
        state.update(updated_utc=datetime.now(timezone.utc).isoformat(),completed_cells=len(own),fits_sha256=terminal['fits_sha256'],
            status_sha256=sha(output/'status.json'),elapsed_seconds=time.monotonic()-start);atomic(a.state,state)
        print(json.dumps({'status':state['status'],'output':str(output),'cells':len(own)}),flush=True)
    except Exception as error:
        state.update(status='failed_pending_root_review',error=str(error),updated_utc=datetime.now(timezone.utc).isoformat());atomic(a.state,state);raise


if __name__=='__main__':main()
