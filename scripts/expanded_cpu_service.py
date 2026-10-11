"""Persistent lightweight launcher/observer for the four CPU combination shards."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

from expanded_cpu_cached import atomic, sha

ROOT=Path('${OLENS_REPO_ROOT}')
D=Path('${OLENS_DATA_ROOT}/expansion-v1/selections')
PY='${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python'
SEAL='753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8'

def main():
    p=argparse.ArgumentParser();p.add_argument('--job-id',type=int,action='append',required=True);p.add_argument('--wait-smoke',action='store_true');a=p.parse_args()
    state=ROOT/'.state/expanded-cpu-v1.service.json';workers=[]
    data={'job_id':a.job_id[0],'job_ids':a.job_id,'node':'node1623','cpu_count':16*len(a.job_id),'memory_gib':80*len(a.job_id),'end_utc':'2026-10-11T12:18:55Z',
        'cached_status':str(D/'cached-v2/status.json'),'cached_state':'complete','combinations_root':str(D/'combinations-v2'),
        'pid':os.getpid(),'started_utc':datetime.now(timezone.utc).isoformat(),'state':'waiting_smoke' if a.wait_smoke else 'launching',
        'inventory_sha256':SEAL,'code_sha256':sha(__file__)}
    atomic(state,data)
    if a.wait_smoke:
        deadline=time.time()+900
        while time.time()<deadline:
            status=D/'combinations-smoke-v2/status.json'
            if status.exists() and json.loads(status.read_text()).get('status')=='complete':break
            error=Path('/tmp/olens-expansion-combo-smoke-v2.err')
            if error.exists() and 'Traceback' in error.read_text():
                atomic(state,data|{'state':'smoke_failed','error':error.read_text()[-3000:]});return
            time.sleep(10)
        else:
            atomic(state,data|{'state':'smoke_timeout'});return
    for index in range(4*len(a.job_id)):
        output=D/f'combinations-v2/shard-{index}';log=Path(f'/tmp/olens-expansion-combo-v2-{index}.log');err=Path(f'/tmp/olens-expansion-combo-v2-{index}.err')
        command=['srun',f'--jobid={a.job_id[index//4]}','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=4','--mem=20G','--cpu-bind=cores',
            '/usr/bin/env',f'PYTHONPATH={ROOT}/src','OMP_NUM_THREADS=4','MKL_NUM_THREADS=4','OPENBLAS_NUM_THREADS=1',PY,
            str(ROOT/'scripts/expanded_cpu_combinations.py'),'--inventory-sha256',SEAL,'--shard-index',str(index),'--shard-count',str(4*len(a.job_id)),'--output',str(output)]
        with log.open('w') as stdout,err.open('w') as stderr:
            proc=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr)
        workers.append((proc,output,log,err))
    while True:
        rows=[]
        for proc,output,log,err in workers:
            path=output/'status.json';status=json.loads(path.read_text()) if path.exists() else {'status':'preparing'}
            rows.append({'pid':proc.pid,'exit_code':proc.poll(),'status_path':str(path),'status':status,
                'log':str(log),'error_log':str(err),'error_tail':err.read_text()[-2000:] if proc.poll() is not None and proc.returncode!=0 else None})
        terminal=all(proc.poll() is not None for proc,_,_,_ in workers)
        updated=data|{'state':'terminal' if terminal else 'running','last_check_utc':datetime.now(timezone.utc).isoformat(),'workers':rows}
        atomic(state,updated)
        if terminal:break
        time.sleep(30)
    # Only complete journals can enter immutable full-family projections.
    if all(r['exit_code']==0 and r['status']['status']=='complete' for r in rows):
        command=['srun',f'--jobid={a.job_id[0]}','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=4','--mem=20G','--cpu-bind=cores',
            '/usr/bin/env',f'PYTHONPATH={ROOT}/src',PY,str(ROOT/'scripts/expanded_cpu_merge.py'),
            '--inventory-sha256',SEAL,'--input-root',str(D/'combinations-v2'),'--shard-count',str(4*len(a.job_id)),'--output',str(D/'combinations-v2/merged')]
        result=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        atomic(state,updated|{'merge_exit_code':result.returncode,'merge_stdout':result.stdout[-2000:],'merge_stderr':result.stderr[-3000:]})

if __name__=='__main__':main()
