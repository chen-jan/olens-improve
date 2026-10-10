"""One resumable AR writer over immutable complete-cell snapshots of DEV journals."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import time
from types import SimpleNamespace
from olens_improve.ar_cache import committed_prefix,complete_cells,input_records,digest
from encode_candidates import encode_snapshot,atomic_json


def main():
    p=argparse.ArgumentParser()
    for name in ('pool','cells-manifest','checkpoint','output','snapshots'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--runtime',default='configs/runtime.json');p.add_argument('--batch-size',type=int,required=True)
    p.add_argument('--poll-seconds',type=int,default=30);p.add_argument('--once',action='store_true')
    args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use assigned GPU')
    pool=Path(args.pool);configuration=json.loads((pool/'pool.json').read_text())
    manifest_bytes=Path(args.cells_manifest).read_bytes();manifest=json.loads(manifest_bytes)
    allowed={c['cell_id']:c for c in manifest['cells']}
    if len(allowed)!=len(manifest['cells']) or any(c.get('split',manifest.get('split'))!='development' for c in allowed.values()):
        raise ValueError('Streaming writer is DEVELOPMENT only')
    snapshots=Path(args.snapshots);snapshots.mkdir(parents=True,exist_ok=True)
    outer_lock=(snapshots/'stream_writer.lock').open('a+');fcntl.flock(outer_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    spec={'global_pool_id':configuration['global_pool_id'],'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
          'batch_size':args.batch_size,'sample_limit':32,'split':'development','code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    spec_path=snapshots/'spec.json'
    if spec_path.exists() and json.loads(spec_path.read_text())!=spec:raise ValueError('Streaming contract changed')
    atomic_json(spec_path,spec)
    state_path=snapshots/'state.json';done=set()
    if state_path.exists():done=set(json.loads(state_path.read_text())['completed_cell_ids'])
    ar=None;stop=False
    def interrupted(signum,frame):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    while not stop:
        rows=[];parents=[]
        for path in sorted(pool.glob('shard-*-of-*.jsonl')):
            body=committed_prefix(path.read_bytes())
            parents.append({'path':str(path),'committed_bytes':len(body),'committed_prefix_sha256':hashlib.sha256(body).hexdigest()})
            for row in input_records(body):
                if row.get('global_pool_id',row.get('pool_id'))!=configuration['global_pool_id']:raise ValueError('Mixed global pools')
                if row['cell_id'] not in allowed:raise ValueError('Journal contains an off-DEV cell')
                rows.append(row)
        fresh=complete_cells(rows,allowed,done)
        if fresh:
            cell_ids=sorted({r['cell_id'] for r in fresh});payload=''.join(json.dumps(r|{'split':'development'},sort_keys=True)+'\n' for r in fresh)
            snapshot_sha=hashlib.sha256(payload.encode()).hexdigest();path=snapshots/f'{snapshot_sha[:20]}.jsonl'
            if path.exists() and path.read_text()!=payload:raise ValueError('Snapshot collision')
            if not path.exists():path.write_text(payload);path.chmod(0o444)
            meta={'snapshot_sha256':snapshot_sha,'path':str(path),'cell_ids':cell_ids,'n':32,'parent_journal_prefixes':parents,'spec_sha256':digest(spec)}
            meta_path=path.with_suffix('.manifest.json')
            if not meta_path.exists():atomic_json(meta_path,meta);meta_path.chmod(0o444)
            encoding=SimpleNamespace(runtime=args.runtime,input=[str(path)],input_kind='candidates',checkpoint=args.checkpoint,
                                     output=args.output,batch_size=args.batch_size,shard_size=4096,max_output_tokens=256)
            ar=encode_snapshot(encoding,ar)
            done.update(cell_ids)
            atomic_json(state_path,{'status':'running','completed_cell_ids':sorted(done),'completed_cells':len(done),
                                   'expected_cells':len(allowed),'last_snapshot_sha256':snapshot_sha,'slurm_job_id':os.environ['SLURM_JOB_ID']})
        if len(done)==len(allowed) or args.once:break
        time.sleep(min(args.poll_seconds,30))
    atomic_json(state_path,{'status':'complete' if len(done)==len(allowed) else 'paused_or_once',
                           'completed_cell_ids':sorted(done),'completed_cells':len(done),'expected_cells':len(allowed),
                           'slurm_job_id':os.environ['SLURM_JOB_ID']})


if __name__=='__main__':main()
