"""Frozen D+E1 mean-specificity greedy pooling, with optional own-fit deletion."""
import argparse
from collections import defaultdict
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import time
import torch
from safetensors.torch import load_file
from transformers import AutoTokenizer
from olens_improve.ar_cache import digest,vector_key
from olens_improve.reconstruction import RawVectorCache,Whitener,JointNNLS,ar_token_ids
from olens_improve.selection import parse_bullets,greedy_pool,prune_leave_one_out,Selection,output_admissible


def main():
    p=argparse.ArgumentParser()
    for name in ('pool','parents','manifest','fresh-manifest','controls','cache','checkpoint','whitener-directory','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--runtime',type=Path,default=Path('configs/runtime.json'))
    p.add_argument('--max-cells',type=int)
    a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use allocated CPU resources')
    torch.set_num_threads(4);started=time.time()
    bodies={name:getattr(a,name.replace('-','_')).read_bytes() for name in ('pool','parents','manifest','fresh-manifest','controls')}
    cells={c['cell_id']:c for c in json.loads(bodies['manifest'])['cells']}
    fresh={c['cell_id']:c for c in json.loads(bodies['fresh-manifest'])['cells']}
    parent_rows=[json.loads(l) for l in bodies['parents'].splitlines()];parents={r['cell_id']:r for r in parent_rows}
    controls=json.loads(bodies['controls']);pools=defaultdict(dict)
    for line in bodies['pool'].splitlines():
        r=json.loads(line)
        if r['sample_index'] in pools[r['cell_id']]:raise ValueError('Duplicate source sample')
        pools[r['cell_id']][r['sample_index']]=r
    if len(parent_rows)!=len(parents) or cells.keys()!=parents.keys() or cells.keys()!=pools.keys():
        raise ValueError('Frozen cohort differs')
    if controls['split_sha256']!=json.loads(bodies['manifest'])['split_sha256']:
        raise ValueError('Controls belong to another split')
    targets=sorted(cells)
    if a.max_cells:targets=targets[:a.max_cells]
    cache=RawVectorCache(str(a.cache));state=torch.load(a.checkpoint/'heads.pt',map_location='cpu',weights_only=True)
    if sha256((a.checkpoint/'heads.pt').read_bytes()).hexdigest()!=cache.contract['head_sha256']:
        raise ValueError('Head changed')
    tags={int(l):state['tag_ids'][i].tolist() for i,l in enumerate(state['layers'])}
    runtime=json.loads(a.runtime.read_text());tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda s:len(tok(s,add_special_tokens=False)['input_ids']);admissible=output_admissible(count,256)
    spec={'source_sha256':{k:sha256(v).hexdigest() for k,v in bodies.items()},'cell_ids':targets,
          'n':32,'max_bullets':4,'max_tokens':256,'objective':'target_exact_fve - mean(frozen_control_exact_fve)',
          'greedy_rounds':4,'swap_passes':1,'fallback':'Best complete same-dictionary output under identical objective/caps',
          'pruning_objective':'own_target_exact_fve','pruning_maximum_loss':.005,
          'random_control':'Seeded deletion retaining identical pruned bullet count; not exact token length',
          'new_model_calls':0,'vector_contract':cache.contract,'controls_by_target':{c:controls['control_cell_ids_by_target'][c] for c in targets},
          'code_sha256':{str(q):sha256(q.read_bytes()).hexdigest() for q in
              [Path(__file__),Path('src/olens_improve/reconstruction.py'),Path('src/olens_improve/selection.py')]}}
    a.output.mkdir(parents=True,exist_ok=True)
    path=a.output/'spec.json'
    if path.exists() and json.loads(path.read_text())!=spec:raise ValueError('Resume contract changed')
    path.write_text(json.dumps(spec,indent=2)+'\n')
    result=a.output/'selections.jsonl';done=set()
    if result.exists():
        for line in result.read_text().splitlines():
            r=json.loads(line)
            if r['cell_id'] in done or r['spec_sha256']!=digest(spec):raise ValueError('Invalid completed event')
            done.add(r['cell_id'])
    tensor_paths={fresh[c]['activation_tensor_path'] for c in targets}
    if len(tensor_paths)!=1:raise ValueError('Require one fresh tensor')
    act=load_file(next(iter(tensor_paths)))['resid'];whiteners={};whitened={};target_vectors={}
    conditions=[]
    with result.open('a') as out:
        for cid in targets:
            if cid in done:continue
            t0=time.time();cell=fresh[cid];layer=cell['layer']
            if cell['split']!='development' or set(pools[cid])!=set(range(32)):raise ValueError('Require complete DEV pool')
            if layer not in whiteners:
                whiteners[layer]=Whitener.load(str(a.whitener_directory/f'whitening_iolens_pooled_L{layer}.safetensors'))
                whitened[layer]={};target_vectors[layer]={}
            w=whiteners[layer];bank=spec['controls_by_target'][cid]
            if not bank:raise ValueError('No frozen controls')
            for target_id in [cid,*bank]:
                other=fresh[target_id];ref=controls['control_bank'][target_id]
                ownref=controls['control_bank'][cid]
                if other['split']!='development' or any(ref[k]!=ownref[k] for k in ('family','layer','read_position_kind')):
                    raise ValueError('Invalid matched control')
                if target_id!=cid and other['group_id']==cell['group_id']:raise ValueError('Related control')
                if target_id not in target_vectors[layer]:
                    original=act[other['activation_row']]
                    if sha256(original.numpy().tobytes()).hexdigest()!=other['activation_sha256']:raise ValueError('Activation changed')
                    target_vectors[layer][target_id]=w.whiten(original.reshape(1,-1))[0]
            samples=[];representatives={};vectors={};atoms={}
            for index in range(32):
                row=pools[cid][index]
                if row['activation_sha256']!=cell['activation_sha256']:raise ValueError('Pool activation changed')
                sample=parse_bullets(row['text'],f"{row.get('global_pool_id',row['pool_id'])}:{cid}:{index}",index,
                                    token_count=count,max_output_tokens=256)
                samples.append(sample)
                if sample.parsing_uncertain:continue
                for b in sample.bullets:representatives.setdefault(b.text,b)
            bullets=list(representatives.values())
            complete=[replace(s,bullets=tuple(dict((representatives[b.text].phrase_id,representatives[b.text]) for b in s.bullets).values()))
                      for s in samples if not s.parsing_uncertain]
            for b in bullets:
                _,ids=ar_token_ids(tok,b.text)
                if not ids:raise ValueError('Empty cleaned scorer input')
                key=vector_key(cache.contract['sha256'],tags[layer],ids[:32])
                if key not in whitened[layer]:
                    v=w.whiten(cache.get(key).reshape(1,-1))[0];whitened[layer][key]=v/(v.norm()+1e-9)
                vectors[b.phrase_id]=whitened[layer][key]
                atoms[b.phrase_id]={'phrase_id':b.phrase_id,'text':b.text,'source_sample_id':b.sample_id,
                    'sample_index':int(b.sample_id.rsplit(':',1)[1]),
                    'cache_key':key,'scored_token_ids':ids[:32],'original_token_count':len(ids),'truncated':len(ids)>32}
            exact=JointNNLS(target_vectors[layer][cid],vectors)
            others=[JointNNLS(target_vectors[layer][c],vectors) for c in bank]
            def objective(ids):return exact.score(ids)-sum(s.score(ids) for s in others)/len(others)
            pooled=greedy_pool(bullets,objective,admissible=admissible,swap_passes=1,complete_samples=complete)
            pruned=prune_leave_one_out(pooled.bullets,exact.score,maximum_loss=.005)
            rng=random.Random(int(digest(['specificity_pool_matched_deletion_v1',cid,.005])[:16],16))
            keep=set(rng.sample(range(len(pooled.bullets)),len(pruned.bullets)))
            random_output=Selection('random_delete',tuple(b for i,b in enumerate(pooled.bullets) if i in keep),None)
            selections=[]
            for method,selected in [('pooled_specificity_mean',pooled),('pooled_specificity_mean_then_prune_0.005',pruned),
                                    ('pooled_specificity_mean_random_delete_matched_0.005',random_output)]:
                selections.append({'method':method,'n':32,'text':selected.text,'phrase_ids':list(selected.phrase_ids),
                    'token_count':count(selected.text),'bullet_count':len(selected.bullets),'fits':{'exact':exact.fit(selected.phrase_ids).__dict__},
                    'specificity_objective':objective(selected.phrase_ids),'mean_control_fve':sum(s.score(selected.phrase_ids) for s in others)/len(others),
                    'atoms':[atoms[k] for k in selected.phrase_ids],'trace':list(selected.trace),
                    'stage_parent':{'text':pooled.text,'phrase_ids':list(pooled.phrase_ids),'exact_fve':exact.score(pooled.phrase_ids)}})
            # Unchanged comparator outputs are copied, never regenerated or canonically rewritten.
            for method in ('pooled_greedy_swap','best_n_specificity_mean'):
                matching=[s for s in parents[cid]['selections'] if s['method']==method and s['n']==32]
                if len(matching)!=1:raise ValueError('Missing component-off parent')
                mapped=tuple(dict.fromkeys(representatives[atom['text']].phrase_id for atom in matching[0]['atoms']))
                if abs(exact.score(mapped)-matching[0]['fits']['exact']['fve'])>1e-5:
                    raise ValueError('Component-off parent fit changed')
                selections.append(matching[0]|{'component_off_comparator':True})
            if not conditions:conditions=[{'method':s['method'],'n':s['n']} for s in selections]
            event={k:cell[k] for k in ('cell_id','family','item_id','layer','position','split')}
            event.update({'activation_sha256':cell['activation_sha256'],'spec_sha256':digest(spec),
                          'selections':selections,'seconds':time.time()-t0})
            out.write(json.dumps(event)+'\n');out.flush();os.fsync(out.fileno());done.add(cid)
            (a.output/'status.json').write_text(json.dumps({'status':'running','completed_cells':len(done),
                                                        'expected_cells':len(targets),'seconds':time.time()-started})+'\n')
            print(json.dumps({'completed_cells':len(done),'cell_seconds':time.time()-t0}),flush=True)
    if not conditions:
        first=json.loads(result.open().readline());conditions=[{'method':s['method'],'n':s['n']} for s in first['selections']]
    (a.output/'conditions.json').write_text(json.dumps(conditions)+'\n')
    status={'status':'complete','cells':len(targets),'conditions':len(conditions),'new_conditions':3,
            'seconds':time.time()-started,'selection_sha256':sha256(result.read_bytes()).hexdigest(),'quality_status':'unjudged'}
    (a.output/'status.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status),flush=True)


if __name__=='__main__':main()
