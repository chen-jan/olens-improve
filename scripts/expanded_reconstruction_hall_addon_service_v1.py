"""Bounded single-worker cached reconstruction diagnostics on one owned CPU job."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

from expanded_cpu_cached import atomic, sha

ROOT=Path('${OLENS_REPO_ROOT}')
SEAL='753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8'
PY='${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python'


def main():
    state=ROOT/'.state/expanded-reconstruction-hall-addon-v1.service.json'
    root=Path('${OLENS_DATA_ROOT}/expansion-v1/reconstruction/replay-hall-addon-v1')
    snapshot=ROOT/'.state/reconstruction-replay-hall-addon-snapshot-v1'
    base={'job_id':25536417,'pid':os.getpid(),'started_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'requested secondary CPU-only existing-vector replay','inventory_sha256':SEAL,
        'replay_code_sha256':sha(ROOT/'scripts/expanded_reconstruction_replay_v2.py'),
        'snapshot_receipt_sha256':sha(snapshot/'receipt.json'),'resources':{'physical_cores':4,'memory_gib':20},
        'output_root':str(root)}
    atomic(state,base|{'state':'launching'});workers=[]
    for i in range(1):
        folder=root/f'shard-{i}';log=Path(f'/tmp/expanded-reconstruction-hall-addon-v1-{i}.log');error=Path(f'/tmp/expanded-reconstruction-hall-addon-v1-{i}.err')
        command=['srun','--jobid=25536417','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=4','--mem=20G','--cpu-bind=cores',
            '/usr/bin/env',f'PYTHONPATH={ROOT}/src','OMP_NUM_THREADS=4','MKL_NUM_THREADS=4','OPENBLAS_NUM_THREADS=1',PY,
            str(ROOT/'scripts/expanded_reconstruction_replay_v2.py'),'--inventory-sha256',SEAL,'--output',str(folder),
            '--shard-count','1','--shard-index',str(i),'--threads','4']
        for name in ('likelihood-v1',):
            command+=['--ready-directory',str(snapshot/name)]
        with log.open('w') as stdout,error.open('w') as stderr:
            process=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr)
        workers.append((process,folder,log,error))
    while True:
        rows=[]
        for process,folder,log,error in workers:
            status=folder/'status.json'
            rows.append({'pid':process.pid,'exit_code':process.poll(),'status_path':str(status),
                'status':json.loads(status.read_text()) if status.exists() else {'status':'preparing'},
                'log':str(log),'error_log':str(error),
                'error_tail':error.read_text()[-3000:] if process.poll() not in (None,0) else None})
        terminal=all(p.poll() is not None for p,_,_,_ in workers)
        complete=terminal and all(r['exit_code']==0 and r['status']['status']=='complete' for r in rows)
        atomic(state,base|{'state':'complete' if complete else 'terminal_failed' if terminal else 'running',
            'last_check_utc':datetime.now(timezone.utc).isoformat(),'workers':rows})
        if terminal:return
        time.sleep(30)


if __name__=='__main__':main()
