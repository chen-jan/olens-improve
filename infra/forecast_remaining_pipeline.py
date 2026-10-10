"""Conditional N32 forecast from frozen DEV timings; no held-out execution."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path


if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Read generation journals in a CPU allocation')
durable=Path('${OLENS_DATA_ROOT}');fast=Path('${OLENS_COMPUTE_ROOT}')
pool=durable/'runs/development-full-grid-v2';manifest_sha='dd382ff6e8bc8e70f1d13710e5235efd943537b4936921726b7d59655289ca80'
batches=[];sources=[]
for shard in range(4):
    path=pool/f'shard-{shard:03d}-of-004.jsonl';digest=sha256();seconds=0.;samples=0;count=0
    with path.open('rb') as stream:
        for line in stream:
            digest.update(line);row=json.loads(line)
            if row.get('kind')=='generation' and row['launch']['manifest_sha256']==manifest_sha:
                seconds+=row['seconds'];samples+=len(row['records']);count+=1
    status=json.loads(path.with_suffix('.status.json').read_text())
    if status['status']!='complete' or digest.hexdigest()!=status['journal_sha256']:raise ValueError('Frozen generation source changed')
    sources.append({'path':str(path),'sha256':digest.hexdigest()})
    batches.append({'shard':shard,'batches':count,'model_task_seconds':seconds,'samples':samples})
seconds=sum(r['model_task_seconds'] for r in batches);samples=sum(r['samples'] for r in batches)
if not samples:raise ValueError('No full DEV timing batches')
per_cell=seconds/(samples/32);remaining=19435-5236
progress=fast/'vectors/shared-global-v1/a451cf49d28ac7447722/progress.json';ar=json.loads(progress.read_text())
if ar['status']!='complete' or ar['completed_unique_vectors']!=642209:raise ValueError('Require terminal measured AR source')
vectors_per_cell=ar['completed_unique_vectors']/5236;vector_rate=ar['new_vectors']/ar['seconds']
generation_hours=remaining*per_cell/3600;ar_hours=remaining*vectors_per_cell/vector_rate/3600
selector_status=[json.loads((durable/f'selections/development-full-grid-v4/shard-{i}/status.json').read_text()) for i in range(4)]
if any(s['status']!='complete' for s in selector_status):raise ValueError('Require terminal selector timing')
selectors_hours=max(s['seconds'] for s in selector_status)*(remaining/5236)/3600
prune_path=durable/'selections/development-full-grid-e1-pruning-v1/status.json';prune=json.loads(prune_path.read_text())
result={'checked_utc':datetime.now(timezone.utc).isoformat(),'scope':'Conditional forecast for N32 on all remaining VAL+TEST cells; no execution authorized by this artifact',
        'remaining_cells':remaining,'remaining_samples_if_n32':remaining*32,'generation_dev_shards':batches,
        'measured_generation_model_seconds_per_n32_cell':per_cell,
        'projected_generation_gpu_task_hours':generation_hours,'projected_generation_wall_hours_four_gpus':generation_hours/4,
        'measured_unique_ar_vectors_per_dev_cell':vectors_per_cell,'measured_final_ar_vectors_per_second':vector_rate,
        'projected_ar_unique_vectors':remaining*vectors_per_cell,'projected_ar_one_gpu_task_hours':ar_hours,
        'projected_one_ar_gpu_plus_three_generation_gpus_wall_hours':max(generation_hours/3,ar_hours),
        'projected_one_extra_ar_gpu_plus_four_generation_gpus_wall_hours':max(generation_hours/4,ar_hours),
        'projected_four_generation_then_one_ar_gpu_wall_hours':generation_hours/4+ar_hours,
        'projected_full_40_selector_arm_wall_hours_four_cpu_workers':selectors_hours,
        'projected_e1_pruning_wall_hours_single_four_thread_worker':prune['seconds']*(remaining/5236)/3600,
        'estimated_ar_vector_storage_gb_fp32':remaining*vectors_per_cell*5120*4/1e9,
        'source_hashes':sources+[{'path':str(progress),'sha256':sha256(progress.read_bytes()).hexdigest()},
                                {'path':str(prune_path),'sha256':sha256(prune_path.read_bytes()).hexdigest()}],
        'limits':['Generation timing is the sum of measured B128 model-call wall time; CPU setup, model reload, pauses and reviewer gates are additional.',
                  'Projected AR inputs inherit DEV deduplication and bullet-length statistics. Changed sample/output distributions can alter rates.',
                  'Selection projection is the full 40-arm DEV implementation; a smaller frozen shortlist may require less work.',
                  'VAL and TEST run as separate gated stages, with additional startup and review time. These central estimates are not completion guarantees.',
                  'No extra allocation should be requested before a scientific stage gate. One AR extra could then overlap the four existing generation workers without a second cache writer.',
                  'No fresh target capture is required if the frozen all-core activation/input contract is retained. New candidate strings and AR vectors are still deployment costs.']}
target=durable/'diagnostics/remaining-pipeline-forecast-v1.json'
if target.exists():raise FileExistsError('Preserve immutable forecast')
target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('source_hashes','limits','generation_dev_shards')},indent=2))
