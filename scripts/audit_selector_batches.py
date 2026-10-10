"""Fixed B32/B128 cached-score sensitivity for D32 and E1/pruning outputs."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file
from transformers import AutoTokenizer
from olens_improve.ar_cache import vector_key
from olens_improve.reconstruction import RawVectorCache,Whitener,JointNNLS,ar_token_ids
from olens_improve.selection import parse_bullets,greedy_pool,best_of_n,prune_leave_one_out,output_admissible


def main():
    p=argparse.ArgumentParser()
    for k in ('fixture','b32','b128','fresh-manifest','controls','checkpoint','whitener-directory'):
        p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--runtime',default='configs/runtime.json');a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use allocated CPU')
    torch.set_num_threads(2);started=time.time();cache=[RawVectorCache(str(p)) for p in (a.b32,a.b128)]
    if cache[0].contract!=cache[1].contract:raise ValueError('Vector contract changed')
    sources={};data={}
    for k,p in [('samples',a.fixture/'samples.jsonl'),('fresh',a.fresh_manifest),('controls',a.controls)]:
        body=p.read_bytes();sources[k]=sha256(body).hexdigest();data[k]=body
    rows=[json.loads(l) for l in data['samples'].splitlines()]
    cells={c['cell_id']:c for c in json.loads(data['fresh'])['cells']};controls=json.loads(data['controls'])
    target_ids=sorted({r['cell_id'] for r in rows})
    if len(target_ids)!=12 or any(cells[c]['split']!='development' for c in target_ids):raise ValueError('Require exact12DEV cells')
    frozen=json.loads((a.fixture/'spec.json').read_text())
    if target_ids!=sorted(frozen['cell_ids']):raise ValueError('Expanded frozen cohort differs')
    tensor_paths={cells[c]['activation_tensor_path'] for c in target_ids}
    if len(tensor_paths)!=1:raise ValueError('Expected one fresh tensor')
    activations=load_file(next(iter(tensor_paths)))['resid']
    state=torch.load(a.checkpoint/'heads.pt',map_location='cpu',weights_only=True)
    if sha256((a.checkpoint/'heads.pt').read_bytes()).hexdigest()!=cache[0].contract['head_sha256']:raise ValueError('Head changed')
    tags={int(l):state['tag_ids'][i].tolist() for i,l in enumerate(state['layers'])}
    runtime=json.loads(Path(a.runtime).read_text());tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda s:len(tok(s,add_special_tokens=False)['input_ids']);allowed=output_admissible(count,256)
    whiteners={};records=[]
    for cid in target_ids:
        layer=cells[cid]['layer'];bank=controls['control_cell_ids_by_target'][cid]
        if not bank:raise ValueError('Missing frozen controls')
        if layer not in whiteners:whiteners[layer]=Whitener.load(str(a.whitener_directory/f'whitening_iolens_pooled_L{layer}.safetensors'))
        w=whiteners[layer];targets={}
        for c in [cid,*bank]:
            ref=controls['control_bank'][c];own=controls['control_bank'][cid]
            if any(ref[k]!=own[k] for k in ('family','layer','read_position_kind')) or cells[c]['split']!='development':
                raise ValueError('Unmatched frozen control')
            if c!=cid and cells[c]['group_id']==cells[cid]['group_id']:raise ValueError('Related control')
            x=activations[cells[c]['activation_row']]
            if sha256(x.numpy().tobytes()).hexdigest()!=cells[c]['activation_sha256']:raise ValueError('Fresh target changed')
            targets[c]=w.whiten(x.reshape(1,-1))[0]
        source=sorted((r for r in rows if r['cell_id']==cid),key=lambda r:r['sample_index'])
        if [r['sample_index'] for r in source]!=list(range(32)):raise ValueError('Incomplete shared pool')
        samples=[];keys={};reps={}
        for r in source:
            if r['activation_sha256']!=cells[cid]['activation_sha256']:raise ValueError('Pool target changed')
            s=parse_bullets(r['text'],f"{r.get('global_pool_id',r['pool_id'])}:{cid}:{r['sample_index']}",r['sample_index'],token_count=count,max_output_tokens=256)
            samples.append(s)
            for b in s.bullets:
                _,ids=ar_token_ids(tok,b.text);keys[b.phrase_id]=vector_key(cache[0].contract['sha256'],tags[layer],ids[:32])
                if not s.parsing_uncertain:reps.setdefault(b.text,b)
        dictionary=list(reps.values())
        complete=[replace(s,bullets=tuple(dict((reps[b.text].phrase_id,reps[b.text]) for b in s.bullets).values())) for s in samples if not s.parsing_uncertain]
        ordered=sorted(set(keys.values()));arms=[];scorers=[];control_scorers=[]
        for c in cache:
            z=w.whiten(torch.stack([c.get(k) for k in ordered]));z=z/(z.norm(dim=1,keepdim=True)+1e-9)
            vectors=dict(zip(ordered,z));vectors={i:vectors[k] for i,k in keys.items()}
            own=JointNNLS(targets[cid],vectors);others=[JointNNLS(targets[k],vectors) for k in bank]
            def q(ids):return own.score(ids)-sum(s.score(ids) for s in others)/len(others)
            d=greedy_pool(dictionary,own.score,admissible=allowed,swap_passes=1,complete_samples=complete)
            e=best_of_n(samples,32,q,admissible=allowed)
            arms.append({'D32':d,'E1mean':e,'E1mean_prune_0.001':prune_leave_one_out(e.bullets,own.score,maximum_loss=.001),
                         'E1mean_prune_0.005':prune_leave_one_out(e.bullets,own.score,maximum_loss=.005)})
            scorers.append(own);control_scorers.append(others)
        for method in arms[0]:
            selections=[arm[method] for arm in arms];metrics=[]
            for i,selected in enumerate(selections):
                own=scorers[i].score(selected.phrase_ids);other=sum(s.score(selected.phrase_ids) for s in control_scorers[i])/len(bank)
                metrics.append({'text':selected.text,'phrase_ids':list(selected.phrase_ids),'own_fve':own,
                    'mean_control_fve':other,'Q':own-other,'trace':list(selected.trace),'bullet_count':len(selected.bullets)})
            fixed=[]
            for selected in selections:
                per_cache=[]
                for i in range(2):
                    own=scorers[i].score(selected.phrase_ids);other=sum(s.score(selected.phrase_ids) for s in control_scorers[i])/len(bank)
                    per_cache.append({'own_fve':own,'mean_control_fve':other,'Q':own-other})
                fixed.append(per_cache)
            records.append({'cell_id':cid,'method':method,'controls':bank,'batch32':metrics[0],'batch128':metrics[1],
                'text_changed':selections[0].text!=selections[1].text,'matched_text_scores':fixed,
                'nonpositive_selected_Q':[m['Q']<=0 for m in metrics],
                'near_zero_note':'Operational Q stops only; no claim-falsity interpretation'})
    summary={m:{'text_changes':sum(r['text_changed'] for r in records if r['method']==m),
                'Q_sign_changes':sum(r['nonpositive_selected_Q'][0]!=r['nonpositive_selected_Q'][1] for r in records if r['method']==m)}
             for m in arms[0]}
    result={'status':'complete','cells':12,'conditions':['D32','E1mean','E1mean_prune_0.001','E1mean_prune_0.005'],
        'summary':summary,'records':records,'seconds':time.time()-started,'cpu_threads':2,'new_gpu_calls':0,'new_judge_calls':0,
        'source_sha256':sources,'code_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'thresholds_unchanged':True,
        'production_modified':False,'scientific_outputs_replaced':False}
    path=a.fixture/'selector-sensitivity.json'
    if path.exists():raise ValueError('Immutable audit exists')
    path.write_text(json.dumps(result,indent=2)+'\n');path.chmod(0o444)
    print(json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)


if __name__=='__main__':main()
