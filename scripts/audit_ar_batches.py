"""Same-input numerical audit of isolated parallel AR versus immutable production."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import time
import numpy as np
import torch
from safetensors.torch import load_file
from scipy.stats import spearmanr
from transformers import AutoTokenizer
from olens_improve.ar_cache import vector_key
from olens_improve.reconstruction import RawVectorCache,Whitener,JointNNLS,ar_token_ids
from olens_improve.selection import parse_bullets,best_of_n,output_admissible,prune_leave_one_out


def main():
    p=argparse.ArgumentParser()
    for field in ('fixture','merged','production','checkpoint','whitener-directory'):
        p.add_argument('--'+field,type=Path,required=True)
    p.add_argument('--runtime',default='configs/runtime.json');a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use allocated CPU resources')
    torch.set_num_threads(2);started=time.time();old=RawVectorCache(str(a.production));new=RawVectorCache(str(a.merged))
    if old.contract!=new.contract:raise ValueError('AR vector contracts differ')
    f=json.loads((a.fixture/'fixture.json').read_text()) if (a.fixture/'fixture.json').exists() else {};inherited=f.get('inherited_key')
    if inherited is not None and not torch.equal(old.get(inherited),new.get(inherited)):raise ValueError('Inherited vector changed')
    keys=sorted(new.index);x=torch.stack([old.get(k) for k in keys]);y=torch.stack([new.get(k) for k in keys])
    relative=(y-x).norm(dim=1)/x.norm(dim=1).clamp_min(1e-12)
    rows=[json.loads(l) for l in (a.fixture/'samples.jsonl').read_text().splitlines()]
    cells={c['cell_id']:c for c in json.loads((a.fixture/'fresh.json').read_text())['cells']}
    tensor_paths={c['activation_tensor_path'] for c in cells.values()}
    if len(tensor_paths)!=1:raise ValueError('Require one fresh tensor')
    activations=load_file(next(iter(tensor_paths)))['resid']
    runtime=json.loads(Path(a.runtime).read_text());tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    state=torch.load(a.checkpoint/'heads.pt',map_location='cpu',weights_only=True)
    tags={int(l):state['tag_ids'][i].tolist() for i,l in enumerate(state['layers'])}
    count=lambda s:len(tok(s,add_special_tokens=False)['input_ids']);admissible=output_admissible(count,256)
    whiteners={};reports=[];all_delta=[];top_raw=[];whitened_error=[];prune_changes=[]
    raw_errors={k:float(v) for k,v in zip(keys,relative)}
    for cid in sorted(cells):
        c=cells[cid];layer=c['layer'];source=sorted((r for r in rows if r['cell_id']==cid),key=lambda r:r['sample_index'])
        if len(source)!=32:raise ValueError('Incomplete frozen fixture')
        samples=[];phrase_keys={};phrase_text={}
        for r in source:
            sid=f"{r.get('global_pool_id',r['pool_id'])}:{cid}:{r['sample_index']}"
            sample=parse_bullets(r['text'],sid,r['sample_index'],token_count=count,max_output_tokens=256);samples.append(sample)
            for b in sample.bullets:
                _,ids=ar_token_ids(tok,b.text);phrase_keys[b.phrase_id]=vector_key(old.contract['sha256'],tags[layer],ids[:32]);phrase_text[b.phrase_id]=b.text
        ordered=sorted(set(phrase_keys.values()))
        if layer not in whiteners:whiteners[layer]=Whitener.load(str(a.whitener_directory/f'whitening_iolens_pooled_L{layer}.safetensors'))
        w=whiteners[layer];target=activations[c['activation_row']]
        if sha256(target.numpy().tobytes()).hexdigest()!=c['activation_sha256']:raise ValueError('Target changed')
        target=w.whiten(target.reshape(1,-1))[0];scorers=[];white_rows=[]
        for cache in (old,new):
            z=w.whiten(torch.stack([cache.get(k) for k in ordered]));white_rows.append(z);z=z/(z.norm(dim=1,keepdim=True)+1e-9)
            mapping=dict(zip(ordered,z));scorers.append(JointNNLS(target,{i:mapping[k] for i,k in phrase_keys.items()}))
        errors=(white_rows[1]-white_rows[0]).norm(dim=1)/white_rows[0].norm(dim=1).clamp_min(1e-12)
        whitened_error.extend(errors.tolist())
        white_map=dict(zip(ordered,errors.tolist()))
        for phrase,key in phrase_keys.items():
            top_raw.append({'cache_key':key,'cell_id':cid,'phrase_id':phrase,'text':phrase_text[phrase],
                            'raw_relative_l2':raw_errors[key],'whitened_relative_l2':white_map[key]})
        for sample in samples:
            for threshold in (.001,.005):
                selected=[prune_leave_one_out(sample.bullets,s.score,maximum_loss=threshold) for s in scorers]
                if selected[0].phrase_ids!=selected[1].phrase_ids:
                    prune_changes.append({'cell_id':cid,'sample_index':sample.index,'threshold':threshold,
                        'eligible':not sample.parsing_uncertain and admissible(sample.bullets),
                        'kept_ids':[list(x.phrase_ids) for x in selected],'traces':[list(x.trace) for x in selected]})
        scores=[[s.score(tuple(b.phrase_id for b in sample.bullets)) for sample in samples] for s in scorers]
        delta=np.array(scores[1])-np.array(scores[0]);all_delta.extend(abs(delta))
        winners=[best_of_n(samples,32,s.score,admissible=admissible) for s in scorers]
        eligible=[s.index for s in samples if not s.parsing_uncertain and admissible(s.bullets)]
        ids=[next((s.index for s in samples if tuple(b.phrase_id for b in s.bullets)==v.phrase_ids),None) for v in winners]
        ranking=sorted(eligible,key=lambda i:(-scores[0][i],i))
        gap=scores[0][ranking[0]]-scores[0][ranking[1]] if len(ranking)>1 else None
        correlation=float(spearmanr([scores[0][i] for i in eligible],[scores[1][i] for i in eligible]).statistic) if len(eligible)>1 else None
        reports.append({'cell_id':cid,'scores_production':scores[0],'scores_partitioned':scores[1],
            'eligible_sample_indices':eligible,'winner_sample_indices':ids,'winner_text_changed':winners[0].text!=winners[1].text,
            'original_top_two_gap':gap,'rank_spearman':correlation if correlation is not None and np.isfinite(correlation) else None,
            'maximum_absolute_fve_delta':float(max(abs(delta)))})
    result={'status':'complete','cells':len(cells),'unique_vectors':len(keys),'inherited_vector_bitwise_preserved':True if inherited is not None else None,
        'raw_relative_l2_max':float(relative.max()),'raw_relative_l2_median':float(relative.median()),
        'raw_max_abs_error':float((y-x).abs().max()),'fve_abs_delta_max':float(max(all_delta)),
        'fve_abs_delta_median':float(np.median(all_delta)),'winner_changes':sum(r['winner_text_changed'] for r in reports),
        'provisional_guards':{'raw_relative_l2_maximum':.02,'fve_absolute_maximum':.003},
        'guard_note':'Raw tolerance is existing mixed-tag fixture; FVE guard brackets prior observed .00213 drift. Not a global bound.',
        'whitened_relative_l2_max':max(whitened_error),'whitened_relative_l2_median':float(np.median(whitened_error)),
        'top_raw_drift_atoms':sorted(top_raw,key=lambda r:-r['raw_relative_l2'])[:20],
        'pruning_decision_flips':prune_changes,'pruning_flip_count_0.001':sum(x['threshold']==.001 for x in prune_changes),
        'pruning_flip_count_0.005':sum(x['threshold']==.005 for x in prune_changes),
        'guards_passed':bool(float(relative.max())<=.02 and max(all_delta)<=.003),'reports':reports,
        'seconds':time.time()-started,'cpu_threads':2,'model_forwards':0,
        'source_sha256':{str(p):sha256(p.read_bytes()).hexdigest() for p in
            [a.fixture/'samples.jsonl',a.fixture/('prepared/plan.json' if (a.fixture/'prepared/plan.json').exists() else 'spec.json'),a.merged/('catalog.json' if (a.merged/'catalog.json').exists() else 'contract.json'),Path(__file__)]},
        'production_modified':False,'scientific_outputs_replaced':False}
    path=a.fixture/'detailed-comparison.json'
    if path.exists():raise ValueError('Immutable comparison exists')
    path.write_text(json.dumps(result,indent=2)+'\n');path.chmod(0o444)
    print(json.dumps({k:v for k,v in result.items() if k not in ('reports','top_raw_drift_atoms','pruning_decision_flips')}),flush=True)


if __name__=='__main__':main()
