#!/usr/bin/env python3
"""Wait for terminal finite services, then atomically seal one read-only effort bundle.

No API transport, database writes, native/reconstruction extraction or cancellation.
A previous failed attempt is retained for review; completed bundles are revalidated.
"""
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

ROOT=Path(__file__).resolve().parents[1]
MANIFEST_SHA='753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8'
FAMILIES=('hallucination','multihop_mt','chain_intermediates','role_bound_association')
ACTIVE=('cached_selector_full_bank','scheduled_full_bank')

def read(path):return json.loads(Path(path).read_text())
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1048576),b''):h.update(b)
    return h.hexdigest()
def require(value,message):
    if not value:raise ValueError(message)
def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)
def check_pins(pins):
    for path,value in pins.items():require(sha(path)==value,'Pinned intake implementation/input changed: '+path)

def terminal_probe(root,state_dir,native_state_path,active):
    """Small operational JSON only; no ledger/caches/source journals while waiting."""
    paths={'native_gate':native_state_path,'registrar':state_dir/'expansion-api-v1.json',
           'semantic':state_dir/'expansion-helpers-semantic-v1.json',
           'editing':state_dir/'expansion-helpers-editing-v1.json',
           'gpu':state_dir/'expanded-gpu-v1.service.json','gpu_queue':state_dir/'expanded-gpu-v1.queue.json'}
    paths.update({f:root/'judgments'/(f+'.queue-state.json') for f in FAMILIES})
    missing=[str(p) for p in paths.values() if not p.exists()]
    if missing:return {'ready':False,'missing_states':missing},{}
    objects={k:read(p) for k,p in paths.items()};reasons=[]
    for f in FAMILIES:
        q=objects[f]
        if q.get('inventory_sha256')!=MANIFEST_SHA:raise ValueError('Foreign worker inventory')
        if set(q['completed'])!=active or q.get('running') is not False:reasons.append('worker_not_terminal:'+f)
    for lane in ('semantic','editing'):
        if objects[lane].get('inventory_sha256')!=MANIFEST_SHA:raise ValueError('Foreign helper inventory')
        if objects[lane].get('phase')!='complete':reasons.append('helper_lane_not_terminal:'+lane)
    semantic={f'{p}:{f}' for p in ('semantic','medium') for f in FAMILIES}
    editing={f'{p}:{f}' for p in ('round1_proposals','round2_proposals','round2_scored_export') for f in FAMILIES}
    if set(objects['semantic'].get('completed',[]))!=semantic:reasons.append('semantic_phase_menu_incomplete')
    if set(objects['editing'].get('completed',[]))!=editing:reasons.append('editing_phase_menu_incomplete')
    if objects['registrar'].get('phase')!='finite_judging_complete':reasons.append('registrar_not_terminal')
    tasks={x['id'] for x in objects['gpu_queue']['tasks']}
    expected={'likelihood-n8-two-controls-v1'}|{f'editing-round{n}-{f}-v1' for n in (1,2) for f in FAMILIES}
    if tasks!=expected:reasons.append('gpu_task_menu_incomplete')
    if objects['gpu'].get('status')!='complete' or set(objects['gpu'].get('completed_tasks',{}))!=expected:reasons.append('gpu_not_terminal')
    if (objects['native_gate'].get('status')!='complete_pending_root_review'
            or objects['native_gate'].get('scientific_inputs_validated_complete') is not True):reasons.append('native_gate_not_terminal')
    return {'ready':not reasons,'waiting_for':reasons,'judge_units':{f:len(set(objects[f]['completed'])&active) for f in FAMILIES}},paths

def validate_native(native,active):
    require(native['manifest_sha256']==MANIFEST_SHA,'Foreign native inventory')
    require(native['status']=='complete_exploratory' and not native['missing_condition_families'],'Incomplete final native source')
    rows=native['complete_condition_families'];pairs=[(x['condition'],x['family']) for x in rows]
    require(len(pairs)==280 and set(pairs)=={(c,f) for c in active for f in FAMILIES},'Native terminal units duplicated or incomplete')

def validate_effort(payload,expected_cells,active=None):
    require(payload['status']=='complete_retrospective' and payload['manifest_sha256']==MANIFEST_SHA,'Effort remains partial or foreign')
    require(payload['judge_completion']=={f:70 for f in FAMILIES},'Effort judge counts are not 70x4')
    require(len(payload['method_effort'])==70,'Effort method inventory incomplete')
    if active is not None:require(set(payload['method_effort'])==active,'Effort method identities changed')
    phases=payload['helper_phases_by_family']
    for p in ('semantic_ordinary','semantic_medium','editing_round1','editing_round2'):
        for f in FAMILIES:
            x=phases[p+'/'+f];require(x['status']=='complete' and x['completed_cells']==expected_cells[f],'Helper checkpoint not terminal: '+p+'/'+f)
            if p.startswith('editing'):require(x['proposal_statistics']['cells']==expected_cells[f],'Editor proposal grid incomplete')
    ledger=payload['ledger_audit'];settled=next((x['actual_usd'] for x in ledger['run_commitment'] if x['status']=='settled'),0)
    require(abs(sum(x['actual_usage_estimate_usd'] for x in ledger['buckets'].values())-settled)<1e-7,'Cost buckets do not partition settled run usage')
    require(ledger['limits']=={'hard':340.0,'target':200.0},'Budget limits changed; intake does not alter them')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact-root',type=Path,default=Path('${OLENS_DATA_ROOT}/expansion-v1'))
    p.add_argument('--native-state',type=Path,default=ROOT/'.state/expanded-final-native-v1.service.json')
    p.add_argument('--state',type=Path,default=ROOT/'.state/expanded-final-effort-v1.service.json')
    p.add_argument('--output-directory',type=Path);p.add_argument('--poll-seconds',type=int,default=60)
    p.add_argument('--max-watch-seconds',type=int,default=28800);p.add_argument('--preflight',action='store_true')
    a=p.parse_args();os.chdir(ROOT)
    if not a.preflight:require(os.environ.get('SLURM_JOB_ID')=='25536291','Use existing approved API CPU 25536291')
    lock=a.state.with_suffix('.lock');lock.parent.mkdir(parents=True,exist_ok=True);handle=lock.open('a');fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    inventory_path=ROOT/'configs/expansion_manifest_v1.json';require(sha(inventory_path)==MANIFEST_SHA,'Expansion seal changed')
    inventory=read(inventory_path);active={x['condition_id'] for x in inventory['conditions'] if x['status'] in ACTIVE};require(len(active)==70,'Finite method menu changed')
    code=[Path(__file__),ROOT/'scripts/export_expansion_effort.py',ROOT/'scripts/build_expansion_dashboard.py',inventory_path]
    pins={str(x):sha(x) for x in code};a.output_directory=a.output_directory or a.artifact_root/'analysis/effort-final-v1'
    state={'status':'waiting_terminal_effort_dependencies','pid':os.getpid(),'job_id':os.getenv('SLURM_JOB_ID'),'started_utc':datetime.now(timezone.utc).isoformat(),'implementation_input_pins':pins,'native_state':str(a.native_state),'output_directory':str(a.output_directory),'api_calls':0,'ledger_writes':0,'new_allocations':0}
    def finished():
        receipt=read(a.output_directory/'receipt.json');require(receipt['status']=='terminal_effort_sealed_pending_root_review' and receipt['manifest_sha256']==MANIFEST_SHA,'Foreign completed effort receipt');check_pins(receipt['implementation_input_pins'])
        require(sha(a.output_directory/'effort.json')==receipt['effort_sha256'],'Completed effort artifact changed')
        require(sha(receipt['native']['path'])==receipt['native']['sha256'],'Bound final native changed')
        state.update(status='complete_pending_root_review',receipt_sha256=sha(a.output_directory/'receipt.json'),effort_sha256=receipt['effort_sha256'])
        if a.preflight:print(json.dumps(state))
        else:atomic(a.state,state)
    started=time.monotonic()
    while True:
        if a.output_directory.exists():finished();return
        probe,paths=terminal_probe(a.artifact_root,ROOT/'.state',a.native_state,active)
        state.update(probe=probe,updated_utc=datetime.now(timezone.utc).isoformat())
        if a.preflight:print(json.dumps(state));return
        atomic(a.state,state)
        if probe['ready']:break
        if time.monotonic()-started>=a.max_watch_seconds:state['status']='waiting_timeout_no_export';atomic(a.state,state);return
        time.sleep(a.poll_seconds)
    check_pins(pins);native_state=read(a.native_state);native_path=Path(native_state['output']);require(sha(native_path)==native_state['output_sha256'],'Native gate output hash differs')
    native=read(native_path);validate_native(native,active)
    snapshot=Path(native_state['snapshot'])/'receipt.json';receipt=read(snapshot)
    require(sha(snapshot)==native_state['receipt_sha256'] and receipt['status']=='sealed_all280_terminal_inputs' and receipt['descriptor_count']==32,'Native snapshot receipt is not terminal')
    pins[str(native_path)]=sha(native_path);pins[str(snapshot)]=sha(snapshot)
    fresh=Path(inventory['fresh_manifest']['path']);require(sha(fresh)==inventory['fresh_manifest']['sha256'],'Fresh cohort changed')
    expected={f:sum(c['family']==f for c in read(fresh)['cells']) for f in FAMILIES}
    terminal_states={str(x):sha(x) for x in paths.values()};work=a.output_directory.with_name(a.output_directory.name+'.preparing')
    require(not work.exists(),'Prior export attempt retained; review before any rerun');work.mkdir(parents=True)
    command=[sys.executable,str(ROOT/'scripts/export_expansion_effort.py'),'--inventory',str(inventory_path),'--root',str(a.artifact_root),'--output',str(work/'effort.json')]
    atomic(work/'attempt.json',{'command':command,'implementation_input_pins':pins,'started_utc':datetime.now(timezone.utc).isoformat()})
    state.update(status='exporting_terminal_effort',command=command);atomic(a.state,state)
    with (work/'export.log').open('x') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    require(r.returncode==0,'Effort exporter failed; preserve attempt without automatic retry')
    payload=read(work/'effort.json');validate_effort(payload,expected,active);check_pins(pins)
    # Terminal service states must remain stable; no ledger-byte hashing/transactions.
    check_pins(terminal_states)
    atomic(work/'receipt.json',{'status':'terminal_effort_sealed_pending_root_review','generated_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':MANIFEST_SHA,'effort_sha256':sha(work/'effort.json'),'native':{'path':str(native_path),'sha256':sha(native_path)},'native_snapshot':{'path':str(snapshot),'sha256':sha(snapshot)},'implementation_input_pins':pins,'terminal_service_state_pins':terminal_states,'settlement_cutoff_utc':payload['ledger_audit']['settlement_cutoff_utc'],'ledger_writes':0,'api_calls':0,'holds':'All unknown and reserved commitments retained; this receipt does not reconcile an invoice.'})
    os.rename(work,a.output_directory);finished();print(json.dumps({'status':state['status'],'effort':str(a.output_directory/'effort.json'),'sha256':state['effort_sha256']}))

if __name__=='__main__':main()
