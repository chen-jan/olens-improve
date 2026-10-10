"""One resumable AR writer over immutable stage-gated complete-cell snapshots."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import time
from types import SimpleNamespace
from olens_improve.ar_cache import digest
from olens_improve.stream_inputs import stream_context, stream_rows, snapshot_payload, preserved_cache_metadata
from encode_candidates import encode_snapshot,atomic_json


def completed_runs(output,snapshot_sha,path):
    runs=[]
    for run in sorted(output.glob('*/usage_*.run.json')):
        info=json.loads(run.read_text())
        if info.get('status')=='complete' and any(r['sha256']==snapshot_sha and r['path']==str(path)
                                                for r in info.get('source_inputs',[])):
            if not Path(info['usage_path']).exists():raise ValueError('Completed snapshot run has no usage evidence')
            runs.append({'path':str(run),'sha256':hashlib.sha256(run.read_bytes()).hexdigest(),
                         'new_unique_vectors':info['new_unique_vectors'],'seconds':info['seconds']})
    return runs


def main():
    p=argparse.ArgumentParser()
    for name in ('pool','cells-manifest','checkpoint','output','snapshots'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--fresh-manifest',required=True)
    p.add_argument('--gate',help='Exact coordinator gate; mandatory for validation/test')
    p.add_argument('--runtime',default='configs/runtime.json');p.add_argument('--batch-size',type=int,required=True)
    p.add_argument('--poll-seconds',type=int,default=30);p.add_argument('--once',action='store_true')
    args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use assigned GPU')
    pool=Path(args.pool);pool_bytes=(pool/'pool.json').read_bytes();configuration=json.loads(pool_bytes)
    manifest_bytes=Path(args.cells_manifest).read_bytes();fresh_bytes=Path(args.fresh_manifest).read_bytes()
    gate_bytes=Path(args.gate).read_bytes() if args.gate else None
    stage,allowed,captures=stream_context(manifest_bytes,fresh_bytes,gate_bytes)
    snapshots=Path(args.snapshots);snapshots.mkdir(parents=True,exist_ok=True)
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    if stage!='development' and args.batch_size!=128:raise ValueError('Frozen later-stage streaming batch size is128')
    # Shared across snapshot directories and standalone encoders for this output.
    with (output/'stream_writer.lock').open('a+') as outer_lock:
        fcntl.flock(outer_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        checkpoint_hashes={name:hashlib.sha256((Path(args.checkpoint)/name).read_bytes()).hexdigest()
                           for name in ('heads.pt','meta.json','lora/adapter_model.safetensors','lora/adapter_config.json')}
        contracts=list(output.glob('*/contract.json'))
        if stage!='development' and not contracts:raise ValueError('Later-stage stream requires the inherited frozen AR cache')
        for path in contracts:
            contract=json.loads(path.read_text())
            if contract['sha256']!=digest({k:v for k,v in contract.items() if k!='sha256'}):raise ValueError('Inherited AR contract digest changed')
            for name,field in [('heads.pt','head_sha256'),('meta.json','meta_sha256'),('lora/adapter_model.safetensors','adapter_sha256'),('lora/adapter_config.json','adapter_config_sha256')]:
                if contract[field]!=checkpoint_hashes[name]:raise ValueError('Inherited cache differs from exact checkpoint')
        spec={'global_pool_id':configuration['global_pool_id'],'pool_config_sha256':hashlib.sha256(pool_bytes).hexdigest(),
              'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),'fresh_manifest_sha256':hashlib.sha256(fresh_bytes).hexdigest(),
              'gate_sha256':hashlib.sha256(gate_bytes).hexdigest() if gate_bytes else None,
              'batch_size':args.batch_size,'sample_limit':32,'split':stage,'output_root':str(output.resolve()),
              'checkpoint_sha256':checkpoint_hashes,
              'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                  (Path(__file__),Path('src/olens_improve/stream_inputs.py'),Path('scripts/encode_candidates.py'),
                   Path('src/olens_improve/reconstruction.py'),Path('src/olens_improve/stage_io.py'),Path('src/olens_improve/ar_partition.py'))}}
        spec_path=snapshots/'spec.json'
        if spec_path.exists():
            old=json.loads(spec_path.read_text());history=old['preserved_cache_metadata']
            if {k:v for k,v in old.items() if k!='preserved_cache_metadata'}!=spec:raise ValueError('Streaming contract changed')
            if hashlib.sha256(Path(history['path']).read_bytes()).hexdigest()!=history['sha256']:
                raise ValueError('Historical cache metadata evidence changed')
        else:
            history=preserved_cache_metadata(output,snapshots/'inherited-cache-metadata')
        spec['preserved_cache_metadata']=history;atomic_json(spec_path,spec)
        state_path=snapshots/'state.json';done=set()
        if state_path.exists():
            state=json.loads(state_path.read_text())
            if state.get('spec_sha256')!=digest(spec):raise ValueError('Streaming resume identity changed')
            done=set(state['completed_cell_ids'])
            if done-set(allowed):raise ValueError('Streaming checkpoint contains off-cohort completed cells')
        ar=None;stop=False
        def interrupted(signum,frame):
            nonlocal stop
            stop=True
        signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
        while not stop:
            fresh,parents,historical=stream_rows(sorted(pool.glob('shard-*-of-*.jsonl')),allowed,captures,
                                                configuration['global_pool_id'],done)
            if fresh:
                cell_ids=sorted({r['cell_id'] for r in fresh})
                payload,original_hashes=snapshot_payload(fresh,stage,test_authorized=stage=='test' and gate_bytes is not None)
                snapshot_sha=hashlib.sha256(payload).hexdigest();path=snapshots/f'{snapshot_sha[:20]}.jsonl'
                if path.exists() and path.read_bytes()!=payload:raise ValueError('Snapshot collision')
                if not path.exists():path.write_bytes(payload);path.chmod(0o444)
                meta={'snapshot_sha256':snapshot_sha,'path':str(path),'cell_ids':cell_ids,'n':32,'split':stage,
                      'parent_journal_prefixes':parents,'spec_sha256':digest(spec),'original_source_record_hashes':original_hashes,
                      'historical_records_excluded':historical,'cohort_manifest_sha256':spec['manifest_sha256'],
                      'fresh_manifest_sha256':spec['fresh_manifest_sha256'],'gate_sha256':spec['gate_sha256'],
                      'authorization_policy':'Test authorization added only after exact verified coordinator TEST gate.'}
                meta_path=path.with_suffix('.manifest.json')
                if meta_path.exists():
                    previous=json.loads(meta_path.read_text())
                    for key in ('snapshot_sha256','cell_ids','spec_sha256','original_source_record_hashes'):
                        if previous[key]!=meta[key]:raise ValueError('Snapshot provenance changed')
                    for parent in previous['parent_journal_prefixes']:
                        prefix=Path(parent['path']).read_bytes()[:parent['committed_bytes']]
                        if hashlib.sha256(prefix).hexdigest()!=parent['committed_prefix_sha256']:
                            raise ValueError('Original committed source prefix changed')
                else:atomic_json(meta_path,meta);meta_path.chmod(0o444)
                encoding=SimpleNamespace(runtime=args.runtime,input=[str(path)],input_kind='candidates',checkpoint=args.checkpoint,
                                         output=args.output,batch_size=args.batch_size,shard_size=4096,max_output_tokens=256,
                                         writer_owner_lock=outer_lock)
                if stage != 'development':
                    encoding.analysis_manifest=args.cells_manifest
                    encoding.fresh_manifest=args.fresh_manifest
                    encoding.analysis_gate=args.gate
                runs=completed_runs(output,snapshot_sha,path)
                # Do not replace an already committed run's timing on crash recovery.
                if not runs:
                    ar=encode_snapshot(encoding,ar)
                    runs=completed_runs(output,snapshot_sha,path)
                # Per-snapshot run records remain separate from mutable aggregate progress.
                if not runs:raise ValueError('No completed encoding run for committed snapshot')
                addition=path.with_suffix('.encoding.json')
                value={'snapshot_sha256':snapshot_sha,'split':stage,'encoding_runs':runs,'spec_sha256':digest(spec)}
                if addition.exists() and json.loads(addition.read_text())!=value:raise ValueError('Stage timing evidence changed')
                if not addition.exists():atomic_json(addition,value);addition.chmod(0o444)
                done.update(cell_ids)
                atomic_json(state_path,{'status':'running','split':stage,'spec_sha256':digest(spec),'completed_cell_ids':sorted(done),
                                       'completed_cells':len(done),'expected_cells':len(allowed),'last_snapshot_sha256':snapshot_sha,
                                       'slurm_job_id':os.environ['SLURM_JOB_ID']})
            if len(done)==len(allowed) or args.once:break
            time.sleep(min(args.poll_seconds,30))
        atomic_json(state_path,{'status':'complete' if len(done)==len(allowed) else 'paused_or_once','split':stage,
                               'spec_sha256':digest(spec),'completed_cell_ids':sorted(done),'completed_cells':len(done),
                               'expected_cells':len(allowed),'slurm_job_id':os.environ['SLURM_JOB_ID']})



if __name__=='__main__':main()
