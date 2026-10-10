"""Fixed DEV inputs: AR batch throughput and numerical ranking, no cache overwrites."""
import argparse
from collections import OrderedDict
import hashlib
import json
import math
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file,save_file
from scipy.stats import spearmanr
from olens_improve.ar_cache import digest,input_records
from olens_improve.models import BASE_REVISION,PAIR_REVISION
from olens_improve.reconstruction import FrozenAR,JointNNLS,RawVectorCache,Whitener
from olens_improve.selection import parse_bullets,best_of_n,output_admissible


def main():
    p=argparse.ArgumentParser()
    for name in ('input','cache-directory','fresh-manifest','checkpoint','whitener-directory','stability-spec','output'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--runtime',default='configs/runtime.json');p.add_argument('--inputs',type=int,default=512)
    p.add_argument('--repeats',type=int,default=2);args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use assigned GPU')
    torch.set_num_threads(4);started=time.time()
    runtime=json.loads(Path(args.runtime).read_text());cache=RawVectorCache(args.cache_directory)
    requested=json.loads(Path(args.stability_spec).read_text())['cell_ids']
    fresh={c['cell_id']:c for c in json.loads(Path(args.fresh_manifest).read_text())['cells']}
    all_usage={};by_source={}
    for path in sorted(Path(args.cache_directory).glob('usage_*.jsonl')):
        for line in path.read_text().splitlines():
            row=json.loads(line);key=row['cache_key']
            if key is not None:all_usage.setdefault(key,row)
            by_source[row['source_phrase_id']]=row
    fixed=OrderedDict()
    for key,row in all_usage.items():
        if row['cell_id'] in requested and row['sample_index']<16:fixed[key]=row
    for key in sorted(all_usage):
        if len(fixed)>=args.inputs:break
        fixed.setdefault(key,all_usage[key])
    if len(fixed)!=args.inputs:raise ValueError('Not enough fixed DEV inputs')
    if any(fresh[row['cell_id']]['split']!='development' for row in fixed.values()):raise ValueError('DEV only')
    keys=list(fixed);texts=[row['text'] for row in fixed.values()];layers=[row['layer'] for row in fixed.values()]
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    spec={'input_count':len(keys),'selection_rule':'Prior four fixed N16 cells first, then remaining cache keys in hash order',
          'effective_input_keys':keys,'layers':layers,'texts':texts,'batch_sizes':[32,64,128],
          'repeats':args.repeats,'model_revision':BASE_REVISION,'reader_revision':PAIR_REVISION,
          'vector_contract':cache.contract,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path('src/olens_improve/reconstruction.py')]}}
    (output/'spec.json').write_text(json.dumps(spec,indent=2)+'\n')
    ar=FrozenAR.load(runtime['paths']['base_snapshot'],args.checkpoint);results=[];vectors={}
    token_counts=[row['scored_token_count']+6 for row in fixed.values()]
    for batch_size in spec['batch_sizes']:
        ar.encode_mixed(texts[:batch_size],layers[:batch_size]);torch.cuda.synchronize()
        times=[];peaks=[];padded=0
        for repeat in range(args.repeats):
            torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();before=time.perf_counter();predictions=[]
            for start in range(0,len(keys),batch_size):
                batch_texts=texts[start:start+batch_size];batch_layers=layers[start:start+batch_size]
                rows,encoding=ar.encode_mixed(batch_texts,batch_layers);predictions.append(rows)
                if repeat==0:
                    for offset,actual in enumerate(encoding):
                        expected=fixed[keys[start+offset]]
                        if actual['input_ids']!=expected['scored_token_ids']:raise ValueError('Scorer input differs')
                    padded+=len(batch_texts)*max(token_counts[start:start+batch_size])
            torch.cuda.synchronize();times.append(time.perf_counter()-before)
            peaks.append(torch.cuda.max_memory_allocated())
            if repeat==0:vectors[batch_size]=torch.cat(predictions)
        record={'batch_size':batch_size,'seconds':times,'vectors_per_second':[len(keys)/seconds for seconds in times],
                'effective_tokens_per_second':[sum(token_counts)/seconds for seconds in times],
                'padded_tokens_per_pass':padded,'peak_allocated_bytes':peaks,'effective_tokens_per_pass':sum(token_counts)}
        results.append(record);print(json.dumps(record),flush=True)
    source_rows={}
    for row in input_records(Path(args.input).read_bytes()):source_rows.setdefault(row['cell_id'],{})[row['sample_index']]=row
    count=lambda text:len(ar.tokenizer(text,add_special_tokens=False)['input_ids']);allowed=output_admissible(count,256)
    tensor=load_file(fresh[requested[0]]['activation_tensor_path'])['resid']
    w=Whitener.load(str(Path(args.whitener_directory)/'whitening_iolens_pooled_L44.safetensors'))
    position={key:i for i,key in enumerate(keys)};audits=[]
    for cell_id in requested:
        samples=[];mapping={}
        for index in range(16):
            row=source_rows[cell_id][index];sample_id=f"{row.get('global_pool_id',row['pool_id'])}:{cell_id}:{index}"
            sample=parse_bullets(row['text'],sample_id,index,token_count=count);samples.append(sample)
            for atom in sample.bullets:mapping[atom.phrase_id]=by_source[atom.phrase_id]['cache_key']
        eligible=[s for s in samples if not s.parsing_uncertain];target=tensor[fresh[cell_id]['activation_row']]
        cached=JointNNLS.from_raw(target,{k:cache.get(v) for k,v in mapping.items()},w)
        baseline=[cached.score(tuple(b.phrase_id for b in s.bullets)) for s in eligible]
        baseline_winner=best_of_n(samples,16,cached.score,admissible=allowed)
        for batch_size in spec['batch_sizes']:
            fit=JointNNLS.from_raw(target,{k:vectors[batch_size][position[v]] for k,v in mapping.items()},w)
            scores=[fit.score(tuple(b.phrase_id for b in s.bullets)) for s in eligible]
            winner=best_of_n(samples,16,fit.score,admissible=allowed);delta=torch.tensor(scores)-torch.tensor(baseline)
            rho=float(spearmanr(scores,baseline).statistic);rho=rho if math.isfinite(rho) else None
            audits.append({'cell_id':cell_id,'family':fresh[cell_id]['family'],'batch_size':batch_size,
                'maximum_absolute_fve_delta':float(delta.abs().max()),'median_absolute_fve_delta':float(delta.abs().median()),
                'rank_correlation':rho,'winner_changed':winner.phrase_ids!=baseline_winner.phrase_ids,
                'winner_ids':list(winner.phrase_ids),'cached_winner_ids':list(baseline_winner.phrase_ids),
                'fve':scores,'cached_fve':baseline,'cached_top_two_gap':sorted(baseline,reverse=True)[0]-sorted(baseline,reverse=True)[1]})
    save_file({f'batch_{size}':pred for size,pred in vectors.items()},str(output/'diagnostic_vectors.safetensors'))
    (output/'results.json').write_text(json.dumps({'spec':spec,'throughput':results,'score_audit':audits,'status':'complete',
                                                  'total_seconds':time.time()-started},indent=2)+'\n')


if __name__=='__main__':main()
