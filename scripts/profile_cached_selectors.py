"""Measure cached CPU selection on a fixed eight-cell development sample."""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import statistics
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime',default='configs/runtime.json');p.add_argument('--output',required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use the allocated CPU job')
    import torch
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    from olens_improve.reconstruction import RawVectorCache,Whitener,JointNNLS
    from olens_improve.selection import parse_bullets,best_of_n,prune_leave_one_out,greedy_pool,output_admissible
    from olens_improve.contrastive import control_specificity
    torch.set_num_threads(4)
    runtime=json.loads(Path(a.runtime).read_text());fast=Path(runtime['paths']['fast']);durable=Path(runtime['paths']['durable'])
    snapshot=durable/'runs/development-shared-pilot-v2/pilot189-samples-v1.jsonl'
    manifest_path=Path('configs/splits_pilot_shared_v2.json');manifest=json.loads(manifest_path.read_text())
    selected=[]
    for family in sorted({c['family'] for c in manifest['cells']}):
        selected+=sorted([c['cell_id'] for c in manifest['cells'] if c['family']==family],key=lambda s:hashlib.sha256(('cost-v1:'+s).encode()).hexdigest())[:2]
    fresh_path=fast/'activations/core-v1/fresh_manifest_v2.json';fresh={c['cell_id']:c for c in json.loads(fresh_path.read_text())['cells']}
    controls_path=durable/'manifests/development-matched-controls-v2.json';controls=json.loads(controls_path.read_text())['control_cell_ids_by_target']
    records={cell:{} for cell in selected}
    for line in snapshot.read_text().splitlines():
        row=json.loads(line)
        if row['cell_id'] in records:records[row['cell_id']][row['sample_index']]=row
    cache_dir=fast/'vectors/shared-global-v1/a451cf49d28ac7447722'
    # Pilot keys live in the first six immutable shards; leave the appending cache alone.
    subset=Path(a.output).parent/'pilot-cache-view';subset.mkdir(parents=True,exist_ok=True)
    for path in [cache_dir/'contract.json',*sorted(cache_dir.glob('raw_*.index.json'))[:6]]:
        link=subset/path.name
        if not link.exists():link.symlink_to(path)
    cache=RawVectorCache(str(subset));usage={}
    usage_path=cache_dir/'usage_21ff917ecc3a46f1d633.jsonl'
    for line in usage_path.read_text().splitlines():
        row=json.loads(line);usage[(row['cell_id'],row['sample_index'],row['source_phrase_id'])]=row
    tensor=load_file(str(fast/'activations/core-v1/activations.safetensors'))['resid']
    tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    length=lambda text:len(tok(text,add_special_tokens=False)['input_ids']);admissible=output_admissible(length,256)
    whiteners={};rows=[]
    for cell_id in selected:
        setup=time.perf_counter();cell=fresh[cell_id];layer=cell['layer']
        if layer not in whiteners:
            path=fast/f'cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners/whitening_iolens_pooled_L{layer}.safetensors'
            whiteners[layer]=Whitener.load(str(path))
        w=whiteners[layer];samples=[];keys={}
        for index in range(32):
            record=records[cell_id][index];sample_id=f"{record.get('global_pool_id',record['pool_id'])}:{cell_id}:{index}"
            sample=parse_bullets(record['text'],sample_id,index,token_count=length,max_output_tokens=256);samples.append(sample)
            for bullet in sample.bullets:keys[bullet.phrase_id]=usage[(cell_id,index,bullet.phrase_id)]['cache_key']
        ids=list(keys);raw=torch.stack([cache.get(keys[k]) for k in ids]);vectors=w.whiten(raw);vectors=vectors/(vectors.norm(dim=1,keepdim=True)+1e-9);vectors=dict(zip(ids,vectors))
        target=w.whiten(tensor[cell['activation_row']].reshape(1,-1))[0]
        reference={k:w.whiten(tensor[fresh[k]['activation_row']].reshape(1,-1))[0] for k in controls[cell_id]}
        setup_seconds=time.perf_counter()-setup
        representatives={}
        for sample in samples:
            if not sample.parsing_uncertain:
                for bullet in sample.bullets:representatives.setdefault(bullet.text,bullet)
        remapped=[replace(s,bullets=tuple({representatives[b.text].phrase_id:representatives[b.text] for b in s.bullets}.values())) for s in samples if not s.parsing_uncertain]
        times={};fit_counts={}
        for method in ['A8','A16','A32','C32','D32','E1_mean32']:
            measured=[];fits=[]
            for repeat in range(3):
                start=time.perf_counter();objective=JointNNLS(target,vectors)
                if method.startswith('A'):best_of_n(samples,int(method[1:]),objective.score,admissible=admissible)
                elif method=='C32':
                    parent=best_of_n(samples,32,objective.score,admissible=admissible)
                    prune_leave_one_out(parent.bullets,objective.score,maximum_loss=.005)
                elif method=='D32':greedy_pool(list(representatives.values()),objective.score,admissible=admissible,swap_passes=1,complete_samples=remapped)
                else:
                    refs={k:JointNNLS(t,vectors) for k,t in reference.items()}
                    def score(ids):return control_specificity(objective.score(ids),{k:v.score(ids) for k,v in refs.items()},aggregation='mean')['score']
                    best_of_n(samples,32,score,admissible=admissible)
                measured.append(time.perf_counter()-start);fits.append(len(objective._cache)+(sum(len(r._cache) for r in refs.values()) if method=='E1_mean32' else 0))
            times[method]=statistics.median(measured);fit_counts[method]=fits[0]
        rows.append({'cell_id':cell_id,'family':cell['family'],'layer':layer,'cached_preparation_seconds':setup_seconds,'selector_seconds_median3':times,'distinct_nnls_fits':fit_counts})
    output={'scope':'eight-cell development CPU cost instrument; not a cohort-wide latency estimate','cpu_threads':4,'repeats':3,'job_id':os.environ['SLURM_JOB_ID'],'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),snapshot,manifest_path,fresh_path,controls_path,usage_path]},'rows':rows,'summary':{m:{'median_seconds_per_cell':statistics.median(r['selector_seconds_median3'][m] for r in rows),'minimum':min(r['selector_seconds_median3'][m] for r in rows),'maximum':max(r['selector_seconds_median3'][m] for r in rows)} for m in times},'limitations':['Only selector CPU time after cached-vector preparation; generation, encoding, capture and helper costs excluded.','C32 timing includes best-of-32 parent selection.','Cold CPU fit memoization per repetition; shared cached activations/raw vectors remain fixed.','No output quality claims; no GPU or API calls.']}
    Path(a.output).write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output['summary']))

if __name__=='__main__':main()
