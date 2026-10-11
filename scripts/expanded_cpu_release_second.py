"""Release only the second owned allocation after its four validated workers exit."""
import json
from pathlib import Path
import subprocess
import time
from expanded_cpu_cached import atomic

def main():
    state_path=Path('.state/expanded-cpu-v1.service.json');receipt=Path('.state/expanded-cpu-second-release-v1.json')
    state={'job_id':25536927,'status':'waiting_for_terminal_workers_4_to_7','started_unix':time.time()}
    for _ in range(1440):
        service=json.loads(state_path.read_text())
        if service['job_ids']!=[25536417,25536927] or len(service['workers'])!=8:raise ValueError('Owned allocation/service identity differs')
        workers=service['workers'][4:8]
        if any(w.get('exit_code') not in (None,0) for w in workers):
            state.update(status='blocked_worker_failure',last_check_unix=time.time());atomic(receipt,state);return
        if all(w.get('exit_code')==0 and w['status']['status']=='complete' and w['status']['completed_cells']==w['status']['expected_cells'] for w in workers):
            result=subprocess.run(['/usr/bin/scancel','25536927'],capture_output=True,text=True)
            state.update(status='released' if result.returncode==0 else 'release_failed',last_check_unix=time.time(),
                exit_code=result.returncode,stderr=result.stderr,worker_terminal_evidence=[{'pid':w['pid'],'exit_code':w['exit_code'],'status':w['status']} for w in workers])
            atomic(receipt,state);return
        state.update(last_check_unix=time.time(),progress=[{'completed_cells':w['status'].get('completed_cells'),'expected_cells':w['status'].get('expected_cells')} for w in workers]);atomic(receipt,state)
        time.sleep(30)
    state.update(status='observer_timeout',last_check_unix=time.time());atomic(receipt,state)

if __name__=='__main__':main()
