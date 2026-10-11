"""Lightweight CPU bridge from immutable helper descriptors to one-device GPU queue."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
from olens_improve.gpu_resume import file_sha256
from expanded_gpu_service import atomic


def task_from_descriptor(descriptor_path, cfg, manifest, fresh):
    desc = json.loads(descriptor_path.read_text())
    family, round_number = desc['family'], desc['round']
    if family not in ('chain_intermediates','hallucination','multihop_mt','role_bound_association') or round_number not in (1,2):
        raise ValueError('Descriptor outside frozen four-family/two-round editing scope')
    if not Path(desc['output']).resolve().is_relative_to(Path('${OLENS_DATA_ROOT}/expansion-v1').resolve()):
        raise ValueError('Editing outputs must stay inside the new expansion artifact root')
    required = ('proposals','cells_manifest') + (('history',) if round_number == 2 else ())
    for field in required:
        pin = desc[field]
        if file_sha256(pin['path']) != pin['sha256']:
            raise ValueError('Immutable helper descriptor hash changed: ' + field)
    cohort = json.loads(Path(desc['cells_manifest']['path']).read_text())['cells']
    keys = [c['cell_id'] for c in cohort]
    expected = {key for key,row in fresh.items() if row['family'] == family}
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('Editor descriptor must cover the exact complete frozen family')
    if round_number == 2:
        history_status = json.loads((Path(desc['history']['path']).parent/'status.json').read_text())
        if history_status.get('status') != 'complete' or history_status.get('cells') != len(keys):
            raise ValueError('Round2 requires complete round1 scoring')
    command = [cfg['python'],'scripts/expanded_encode_edits.py',
               '--proposals',desc['proposals']['path'],'--cells-manifest',desc['cells_manifest']['path'],
               '--fresh-manifest',manifest['fresh_manifest']['path'],'--checkpoint',cfg['checkpoint'],
               '--production-cache',cfg['production_cache'],'--edit-cache',cfg['edit_cache'],
               '--whitener-directory',cfg['whitener_directory'],'--output',desc['output'],
               '--runtime',cfg['runtime'],'--round',str(round_number),'--batch-size','128',
               '--sealed-manifest',cfg['sealed_manifest']]
    if round_number == 2:
        command.extend(['--history',desc['history']['path']])
    paths = [str(descriptor_path),cfg['sealed_manifest'],cfg['runtime'],'scripts/expanded_encode_edits.py',
             'src/olens_improve/gpu_resume.py','src/olens_improve/reconstruction.py','src/olens_improve/editing.py']
    pins = [dict(path=path,sha256=file_sha256(path)) for path in paths]
    pins.extend(desc[field] for field in required)
    return dict(id=desc['id'],editing_round=round_number,family=family,
                sealed_manifest=cfg['sealed_manifest'],pins=pins,command=command)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--cpu',type=int)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Enqueue watcher must live inside authorized CPU allocation')
    if args.cpu is not None:
        if args.cpu not in os.sched_getaffinity(0):
            raise RuntimeError('Requested watcher core is outside current Slurm affinity')
        os.sched_setaffinity(0,{args.cpu})
    cfg = json.loads(Path(args.config).read_text())
    if file_sha256(cfg['sealed_manifest']) != cfg['sealed_manifest_sha256']:
        raise ValueError('Expansion seal changed before watcher startup')
    manifest = json.loads(Path(cfg['sealed_manifest']).read_text())
    original = json.loads(Path(manifest['fresh_manifest']['path']).read_text())['cells']
    fresh = {r['cell_id']:dict(family=r['family']) for r in original}
    del original
    descriptor_dir = Path(cfg['descriptors']);descriptor_dir.mkdir(parents=True,exist_ok=True)
    state = dict(pid=os.getpid(),job_id=os.environ['SLURM_JOB_ID'],started_unix=time.time(),
                 affinity=sorted(os.sched_getaffinity(0)),queued=[],errors={})
    boundaries={};cumulative=0
    for family in sorted({row['family'] for row in fresh.values()}):
        cumulative+=sum(row['family']==family for row in fresh.values())
        boundaries[family]=cumulative
    while not Path(cfg['stop_file']).exists():
        try:
            with Path(cfg['queue']+'.enqueue.lock').open('a+') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                queue = json.loads(Path(cfg['queue']).read_text())
                present = {t['id']:t for t in queue['tasks']}
                changed = False
                for path in sorted(descriptor_dir.glob('*.json')):
                    desc = json.loads(path.read_text())
                    # Each source descriptor is immutable after publication.
                    key = str(path)
                    if key in state.get('accepted_descriptors',{}):
                        if file_sha256(path) != state['accepted_descriptors'][key]:
                            raise ValueError('Published editor descriptor changed')
                        continue
                    try:
                        task = task_from_descriptor(path,cfg,manifest,fresh)
                        duplicates=[t for t in queue['tasks'] if t.get('editing_round')==task['editing_round']
                                    and t.get('family')==task['family'] and t['id']!=task['id']]
                        if duplicates:raise ValueError('Exactly one scoring task per family and editing round')
                        if task['id'] in present and present[task['id']] != task:
                            raise ValueError('Conflicting GPU task identity')
                        if task['id'] not in present:
                            queue['tasks'].append(task);present[task['id']]=task;changed=True
                        state.setdefault('accepted_descriptors',{})[key]=file_sha256(path)
                        state['errors'].pop(key,None)
                    except (ValueError,KeyError,FileNotFoundError) as error:
                        state['errors'][key]=str(error)
                if changed:
                    queue['status']='sealed_likelihood_and_editing_tasks'
                    atomic(cfg['queue'],queue)
                units={(t.get('family'),t.get('editing_round')) for t in queue['tasks'] if 'editing_round' in t}
                expected_units={(family,r) for family in boundaries for r in (1,2)}
                service_path=Path(cfg['gpu_service_state'])
                if units==expected_units and service_path.exists():
                    service=json.loads(service_path.read_text())
                    if set(present).issubset(service.get('completed_tasks',{})):
                        queue['finish']=True;queue['status']='all_frozen_gpu_tasks_complete'
                        atomic(cfg['queue'],queue)
                state['queued']=[t['id'] for t in queue['tasks']]
                state.update(status='watching',last_check_unix=time.time())
                atomic(cfg['state'],state)
            publisher=cfg.get('likelihood_publisher')
            if publisher and Path(publisher['status']).exists():
                progress=json.loads(Path(publisher['status']).read_text())
                complete={family for family,boundary in boundaries.items()
                          if progress.get('completed_cells',0)>=boundary}
                already=set(state.get('published_likelihood_families',[]))
                if complete-already:
                    if file_sha256(publisher['script'])!=publisher['script_sha256']:
                        raise ValueError('Pinned likelihood publisher source changed')
                    result=subprocess.run([cfg['python'],publisher['script'],
                        '--inventory',cfg['sealed_manifest'],'--inventory-sha256',cfg['sealed_manifest_sha256'],
                        '--input',publisher['input'],'--output',publisher['output']],capture_output=True,text=True)
                    state['likelihood_publish_receipt']=dict(returncode=result.returncode,
                        stdout=result.stdout[-4000:],stderr=result.stderr[-4000:],unix=time.time())
                    if result.returncode==0:
                        state['published_likelihood_families']=sorted(complete)
                        state['errors'].pop('likelihood_publisher',None)
                    else:state['errors']['likelihood_publisher']='Publisher failed; see receipt'
                    atomic(cfg['state'],state)
        except Exception as error:
            state.update(status='error',last_error=str(error),last_check_unix=time.time())
            atomic(cfg['state'],state)
        time.sleep(30)
    state.update(status='stopped',last_check_unix=time.time())
    atomic(cfg['state'],state)


if __name__ == '__main__':
    main()
