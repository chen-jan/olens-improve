"""One source-bound final secondary aggregate after native and replay completion."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from expanded_cpu_cached import atomic, sha
from expanded_final_native_gate import GROUPS, FAMILIES


ROOT=Path(__file__).resolve().parents[1]
DATA=Path('${OLENS_DATA_ROOT}/expansion-v1')
REPLAYS=tuple(DATA/'reconstruction'/name/f'shard-{i}' for name, indices in (
    ('replay-v1',range(4)),('replay-addon-v1',range(2)),('replay-hall-addon-v1',range(1)),
    ) for i in indices)+(DATA/'reconstruction/replay-role-addon-v1/shard0',)


def task_signature(task):
    return hashlib.sha256(json.dumps(task,sort_keys=True).encode()).hexdigest()


def unchanged_pins(pins):
    if any(sha(path)!=value for path,value in pins.items()):
        raise ValueError('Pinned final numerical source changed')


def freeze_native_authority(state_path, native, receipt_path, terminal, state_sha256):
    """Retain hashes approved by the terminal state; never upgrade to live hashes."""
    body=Path(state_path).read_bytes()
    if hashlib.sha256(body).hexdigest()!=state_sha256 or json.loads(body)!=terminal or terminal['status']!='complete_pending_root_review' or terminal['scientific_inputs_validated_complete']is not True:
        raise ValueError('Native terminal state changed or is incomplete')
    pins={str(state_path):state_sha256,str(native):terminal['output_sha256'],str(receipt_path):terminal['receipt_sha256']}
    unchanged_pins(pins)
    return pins


def editor_dispatch_projection(queue, service):
    expected={f'editing-round{r}-{family}-v1' for r in (1,2)for family in FAMILIES}
    tasks=[t for t in queue['tasks']if t['id']in expected]
    if len(tasks)!=8 or {t['id']for t in tasks}!=expected:raise ValueError('Missing/duplicate final editor dispatch tasks')
    done=service['completed_tasks']
    if any(done.get(t['id'],{}).get('task_sha256')!=task_signature(t)for t in tasks):raise ValueError('Final editor task lacks exact successful completion receipt')
    return {'tasks':tasks,'completed_tasks':{t['id']:done[t['id']]for t in tasks}}


def main():
    p=argparse.ArgumentParser();p.add_argument('--pins',type=Path,required=True);p.add_argument('--pins-sha256',required=True)
    p.add_argument('--state',type=Path,required=True);p.add_argument('--editor-review',type=Path,required=True);p.add_argument('--editor-review-sha256',required=True)
    p.add_argument('--max-watch-seconds',type=int,default=28000);a=p.parse_args();os.chdir(ROOT)
    if os.environ.get('SLURM_JOB_ID')!='25536417':raise RuntimeError('Use owned CPU allocation')
    if sha(a.pins)!=a.pins_sha256 or sha(a.editor_review)!=a.editor_review_sha256:raise ValueError('Final secondary gate review/source authority changed')
    pins=json.loads(a.pins.read_text())['source_sha256'];pins[str(a.editor_review)]=a.editor_review_sha256
    review=json.loads(a.editor_review.read_text())
    if review['status']!='root_reviewed_offline_editor_fit_intake':raise ValueError('Final editor boundary has no approved offline review')
    for path,value in review['source_sha256'].items():
        if path in pins and pins[path]!=value:raise ValueError('Final code differs from the root-reviewed editor intake')
        pins[path]=value
    def check():
        unchanged_pins(pins)
    check();lock=a.state.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state={'status':'waiting_for_native_and_all_secondary_sources','pid':os.getpid(),'slurm_job_id':os.environ['SLURM_JOB_ID'],
        'started_utc':datetime.now(timezone.utc).isoformat(),'static_source_sha256':pins,'new_model_calls':0,'new_api_calls':0}
    native_state=ROOT/'.state/expanded-final-native-v1.service.json';native_snapshot=ROOT/'.state/expanded-final-native-ready-v1'
    snapshot=ROOT/'.state/reconstruction-analysis-final-ready-v1';output=DATA/'reconstruction/final-v1.json'
    native=DATA/'analysis/final-v1.json';start=time.monotonic()
    try:
        if output.exists():raise FileExistsError('Existing final aggregate requires root receipt review; no overwrite')
        while True:
            check();native_state_body=native_state.read_bytes();n=json.loads(native_state_body)
            replay_ready=all((d/'status.json').exists()and json.loads((d/'status.json').read_text()).get('status')=='complete'for d in REPLAYS)
            editor_ready=all((DATA/'editing-scores'/f'round{r}'/f/'status.json').exists()and json.loads((DATA/'editing-scores'/f'round{r}'/f/'status.json').read_text()).get('status')=='complete'for r in (1,2)for f in FAMILIES)
            state.update(updated_utc=datetime.now(timezone.utc).isoformat(),native_status=n['status'],terminal_replays=replay_ready,terminal_editor_families=editor_ready,elapsed_seconds=time.monotonic()-start)
            atomic(a.state,state)
            if n['status']=='complete_pending_root_review'and replay_ready and editor_ready:break
            if n['status'].startswith('failed'):raise RuntimeError('Native final gate failed; stop secondary dispatch')
            if time.monotonic()-start>=a.max_watch_seconds:state['status']='timeout_no_snapshot';atomic(a.state,state);return
            time.sleep(30)
        dynamic_pins=freeze_native_authority(native_state,native,native_snapshot/'receipt.json',n,hashlib.sha256(native_state_body).hexdigest())
        pins.update(dynamic_pins);state['terminal_native_source_sha256']=dynamic_pins
        native_sha=n['output_sha256'];native_receipt_sha=n['receipt_sha256'];check()
        quality=json.loads(native.read_text());seal=sha('configs/expansion_manifest_v1.json')
        if quality['manifest_sha256']!=seal or quality['status']!='complete_exploratory'or len(quality['complete_condition_families'])!=280 or quality['missing_condition_families']:raise ValueError('Final quality scope is incomplete')
        native_receipt=json.loads((native_snapshot/'receipt.json').read_text())
        if native_receipt['status']!='sealed_all280_terminal_inputs':raise ValueError('Native sealed source receipt differs')
        for path,value in native_receipt['source_sha256'].items():
            if sha(path)!=value:raise ValueError('Native final source changed')
        sources=[]
        for relative in native_receipt['canonical_relative_paths']:
            original=DATA/'selections'/relative;copied=native_snapshot/relative;expected=native_receipt['source_sha256'][str(original)]
            if sha(original)!=expected or sha(copied)!=expected:raise ValueError('Canonical final descriptor changed')
            sources.append({'path':str(original),'snapshot':str(copied),'sha256':expected})
        if len(sources)!=32:raise ValueError('Final numerical descriptor menu is not canonical32')
        queue_path=ROOT/'.state/expanded-gpu-v1.queue.json';service_path=ROOT/'.state/expanded-gpu-v1.service.json'
        queue_bytes=queue_path.read_bytes();service_bytes=service_path.read_bytes()
        dispatch=editor_dispatch_projection(json.loads(queue_bytes),json.loads(service_bytes))
        dispatch['observed_mutable_sources']=[{'path':str(path),'sha256':hashlib.sha256(body).hexdigest(),'observed_utc':datetime.now(timezone.utc).isoformat()}for path,body in ((queue_path,queue_bytes),(service_path,service_bytes))]
        dispatch['limits']=['The queue/service are append/heartbeat mutable. The copied eight exact tasks and successful receipts are the immutable authority; observed raw hashes describe the capture only.']
        if editor_dispatch_projection(json.loads(queue_path.read_text()),json.loads(service_path.read_text()))!={k:dispatch[k]for k in ('tasks','completed_tasks')}:raise ValueError('Completed editor task projection changed during capture')
        if snapshot.exists():raise FileExistsError('Existing final numeric snapshot requires root review; no reseal')
        temporary=snapshot.with_name(snapshot.name+'.preparing');temporary.mkdir();atomic(temporary/'editor-dispatch.json',dispatch)
        receipt={'manifest_sha256':seal,'quality_analysis_sha256':native_sha,'native_source_receipt_sha256':native_receipt_sha,
            'terminal_native_source_sha256':dynamic_pins,
            'sources':sources,'replay_directories':[str(d)for d in REPLAYS],'editor_review_sha256':a.editor_review_sha256,'sealed_utc':datetime.now(timezone.utc).isoformat()}
        atomic(temporary/'receipt.json',receipt);os.rename(temporary,snapshot);check()
        command=[sys.executable,str(ROOT/'scripts/analyze_expansion_reconstruction_v5.py'),'--inventory-sha256',seal,
            '--quality-analysis',str(native),'--quality-analysis-sha256',native_sha,'--descriptor-snapshot-receipt',str(snapshot/'receipt.json'),
            '--editor-fit-authority','configs/expansion_editor_fit_intake_v1.json','--editor-fit-authority-sha256',pins['configs/expansion_editor_fit_intake_v1.json'],
            '--editor-dispatch-snapshot',str(snapshot/'editor-dispatch.json'),'--editor-dispatch-snapshot-sha256',sha(snapshot/'editor-dispatch.json'),'--output',str(output)]
        for group in GROUPS:command.extend(['--ready-directory',str(native_snapshot/group)])
        for directory in REPLAYS:command.extend(['--replay-directory',str(directory)])
        atomic(snapshot/'analysis-attempt.json',{'command':command,'started_utc':datetime.now(timezone.utc).isoformat()})
        state.update(status='extracting_final_secondary',command=command,snapshot_receipt_sha256=sha(snapshot/'receipt.json'),updated_utc=datetime.now(timezone.utc).isoformat());atomic(a.state,state)
        check()  # Includes retained approved native output/receipt/terminal-state hashes.
        with a.state.with_suffix('.log').open('x')as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=False)
        if result.returncode:raise RuntimeError(f'Final numeric extractor exited {result.returncode}')
        check();body=json.loads(output.read_text())
        if body['quality_analysis_sha256']!=native_sha or len(body['rows'])!=280 or any(r['missing_selection_sites']for r in body['rows']):raise ValueError('Final numeric output lacks full immutable selection scope')
        state.update(status='complete_pending_root_review',output=str(output),output_sha256=sha(output),quality_analysis_sha256=native_sha,
            rows=len(body['rows']),defined_means=sum(r['mean_fve']is not None for r in body['rows']),complete_comparable_rows=sum(r['status']=='complete_comparable'for r in body['rows']),
            updated_utc=datetime.now(timezone.utc).isoformat(),limits=['All selection sources complete; explicit invalid/unavailable fits and grouped interval warnings are retained. No certainty or causal claim is inferred from source completion.'])
        atomic(a.state,state);print(json.dumps({'status':state['status'],'output':str(output),'sha256':state['output_sha256']}),flush=True)
    except Exception as error:
        state.update(status='failed_pending_root_review',error=str(error),updated_utc=datetime.now(timezone.utc).isoformat());atomic(a.state,state);raise


if __name__=='__main__':main()
