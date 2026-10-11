"""Bounded recorded cache-only combinations on the complete exploratory bank."""
from collections import defaultdict
from dataclasses import replace
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.ar_cache import digest, vector_key
from olens_improve.reconstruction import JointNNLS, RawVectorCache, Whitener, ar_token_ids
from olens_improve.selection import (Bullet, Selection, exact_consensus, greedy_pool,
                                    output_admissible, parse_bullets, prune_leave_one_out)
from expanded_cpu_cached import atomic, committed_lines, sha

F=Path('${OLENS_COMPUTE_ROOT}')
WHITENERS=F/'cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners'
CHECKPOINT=F/'cache/huggingface/hub/models--agu18dec--olens_and_ar/snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/ar_ptag_pooled'

def resume(path,inventory_sha):
    done=set()
    if path.exists():
        with path.open('rb+') as stream:
            last=0
            while line:=stream.readline():
                if not line.endswith(b'\n'):stream.truncate(last);break
                row=json.loads(line)
                if row['cell_id'] in done or row['inventory_sha256']!=inventory_sha:raise ValueError('Incompatible restart event')
                done.add(row['cell_id']);last=stream.tell()
    return done

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--inventory-sha256',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--shard-count',type=int,default=4);p.add_argument('--shard-index',type=int,required=True)
    p.add_argument('--max-cells',type=int);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU resources required')
    if sha(a.inventory)!=a.inventory_sha256:raise ValueError('Inventory seal differs')
    import torch
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    torch.set_num_threads(4);start=time.time()
    inventory=json.loads(a.inventory.read_text());fresh=json.loads(Path(inventory['fresh_manifest']['path']).read_text())
    cells={c['cell_id']:c for c in fresh['cells']};controls=json.loads(Path(inventory['control_bank']['path']).read_text())
    runtime=json.loads(Path('configs/runtime.json').read_text());tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda text:len(tok(text,add_special_tokens=False)['input_ids']);admissible=output_admissible(count,256)
    state=torch.load(CHECKPOINT/'heads.pt',map_location='cpu',weights_only=True)
    if sha(CHECKPOINT/'heads.pt')!=inventory['vector_contract']['head_sha256']:raise ValueError('AR head changed')
    tags={int(layer):state['tag_ids'][i].tolist() for i,layer in enumerate(state['layers'])}
    # Assign entire items deterministically, preserving complete reading grids in each worker.
    items=sorted({(c['family'],c['item_id']) for c in cells.values()})
    own_items=set(items[a.shard_index::a.shard_count]);targets={cid for cid,c in cells.items() if (c['family'],c['item_id']) in own_items}
    if a.max_cells:
        # Instrument each journal representation/stage before production.
        staged=[next((cid for cid in sorted(targets) if cells[cid]['split']==stage),None)
                for stage in ('development','validation','test')]
        staged=[cid for cid in staged if cid is not None]
        targets=set((staged+[cid for cid in sorted(targets) if cid not in staged])[:a.max_cells])
    a.output.mkdir(parents=True,exist_ok=True);journal=a.output/'selections.jsonl'
    config={'inventory_sha256':a.inventory_sha256,'code_sha256':sha(__file__),'shard_index':a.shard_index,
        'shard_count':a.shard_count,'max_cells':a.max_cells,'expected_cells':len(targets),'torch_threads':4,
        'contract':'Recorded sourceparser/emptyARpolicy, NNLS/whitening, unchanged thresholds and random seeds'}
    if (a.output/'spec.json').exists() and json.loads((a.output/'spec.json').read_text())!=config:raise ValueError('Resume spec differs')
    atomic(a.output/'spec.json',config);done=resume(journal,a.inventory_sha256)
    if not done.issubset(targets):raise ValueError('Foreign completed cell')
    activations=load_file(next(iter({c['activation_tensor_path'] for c in cells.values()})))['resid']
    whiteners={};target_vectors={};conditions=None
    with journal.open('a') as out:
        for stage,spec in inventory['stages'].items():
            own={cid for cid in targets-done if cells[cid]['split']==stage}
            if not own:continue
            pools=defaultdict(dict)
            for src in spec['samples']:
                if sha(src['path'])!=src['sha256']:raise ValueError('Sample source changed')
                for envelope in committed_lines(src['path']):
                    records=envelope.get('records',[envelope])
                    if not isinstance(records,list):raise ValueError('Malformed generation envelope')
                    for row in records:
                        if row['cell_id'] in own:
                            pool=pools[row['cell_id']]
                            if row['sample_index'] in pool:raise ValueError('Duplicate source sample')
                            pool[row['sample_index']]=row
            if set(pools)!=own or any(set(v)!=set(range(32)) for v in pools.values()):raise ValueError('Incomplete fixed N32 pool')
            cache=RawVectorCache(spec['vector_cache'])
            if cache.contract!=inventory['vector_contract']:raise ValueError('Vector contract changed')
            if sha(spec['selectors']['path'])!=spec['selectors']['sha256']:raise ValueError('Parent selectors changed')
            for parent_row in committed_lines(spec['selectors']['path']):
                cid=parent_row['cell_id']
                if cid not in own:continue
                cell=cells[cid];layer=cell['layer'];t0=time.time()
                if layer not in whiteners:
                    whiteners[layer]=Whitener.load(str(WHITENERS/f'whitening_iolens_pooled_L{layer}.safetensors'))
                    target_vectors[layer]={}
                w=whiteners[layer];tv=target_vectors[layer];bank=controls['control_cell_ids_by_target'][cid]
                for target_id in [cid,*bank]:
                    other=cells[target_id]
                    if target_id!=cid and (other['split']!='development' or other['group_id']==cell['group_id'] or other['family']!=cell['family'] or other['layer']!=layer or other['read_position_kind']!=cell['read_position_kind']):raise ValueError('Invalid original frozen control')
                    if target_id not in tv:
                        raw=activations[other['activation_row']]
                        if hashlib.sha256(raw.numpy().tobytes()).hexdigest()!=other['activation_sha256']:raise ValueError('Activation changed')
                        tv[target_id]=w.whiten(raw.reshape(1,-1))[0]
                samples=[];all_bullets=[];atoms={};keys={};representatives={}
                for index,row in sorted(pools.pop(cid).items()):
                    if row['activation_sha256']!=cell['activation_sha256']:raise ValueError('Pool activation differs')
                    sample=parse_bullets(row['text'],f"{row.get('global_pool_id',row['pool_id'])}:{cid}:{index}",index,token_count=count,max_output_tokens=256)
                    samples.append(sample)
                    for bullet in sample.bullets:
                        _,ids=ar_token_ids(tok,bullet.text);key=vector_key(cache.contract['sha256'],tags[layer],ids[:32]) if ids else None
                        atoms[bullet.phrase_id]={'phrase_id':bullet.phrase_id,'source_phrase_id':bullet.phrase_id,'text':bullet.text,'source_sample_id':bullet.sample_id,
                            'sample_index':index,'cache_key':key,'scored_token_ids':ids[:32],'original_token_count':len(ids),'truncated':len(ids)>32}
                        if key:keys[bullet.phrase_id]=key;all_bullets.append(bullet)
                        if not sample.parsing_uncertain and key:representatives.setdefault(bullet.text,bullet)
                unique=list(dict.fromkeys(keys.values()))
                transformed=w.whiten(torch.stack([cache.get(key) for key in unique])) if unique else torch.empty((0,5120))
                transformed=transformed/(transformed.norm(dim=1,keepdim=True)+1e-9)
                raw_vectors=dict(zip(unique,transformed));vectors={pid:raw_vectors[key] for pid,key in keys.items()}
                exact=JointNNLS(tv[cid],vectors);others=[JointNNLS(tv[k],vectors) for k in bank]
                def objective(ids):return exact.score(ids)-sum(s.score(ids) for s in others)/len(others)
                def candidate_pool(n):
                    reps={}
                    for sample in samples[:n]:
                        if not sample.parsing_uncertain:
                            for bullet in sample.bullets:
                                if bullet.phrase_id in vectors:reps.setdefault(bullet.text,bullet)
                    complete=[replace(s,bullets=tuple(dict((reps[b.text].phrase_id,reps[b.text]) for b in s.bullets).values()))
                        for s in samples[:n] if not s.parsing_uncertain and all(b.phrase_id in vectors for b in s.bullets)]
                    return list(reps.values()),complete
                selections=[]
                def record(method,n,selected,parent=None,extra=None):
                    text=selected.text
                    if not admissible(selected.bullets):raise ValueError('Final cap violated')
                    fits={'exact':exact.fit(selected.phrase_ids).__dict__} if all(pid in vectors for pid in selected.phrase_ids) else None
                    selections.append({'method':method,'n':n,'text':text,'phrase_ids':list(selected.phrase_ids),'token_count':count(text),
                        'bullet_count':len(selected.bullets),'fits':fits,'fits_scope':'emitted_bullets' if fits else 'unavailable_AR_empty_after_cleanup',
                        'atoms':[atoms[k] for k in selected.phrase_ids],'trace':list(selected.trace),'parent_method':parent,'extra':extra or {}})
                for fraction in (0.,.125,.25):
                    selection=exact_consensus(samples[:16],min_support_fraction=fraction,admissible=admissible)
                    record(f'consensus_exact_support{fraction:g}',16,selection)
                    if fraction==0:record('exact_support_only',16,selection,extra={'named_control_same_output_as':'consensus_exact_support0-n16'})
                bullets,complete=candidate_pool(16);votes=defaultdict(set)
                for sample in samples[:16]:
                    if not sample.parsing_uncertain:
                        for bullet in sample.bullets:votes[' '.join(bullet.text.split())].add(sample.index)
                normalize=lambda pid:' '.join(atoms[pid]['text'].split())
                pooled0=greedy_pool(bullets,exact.score,admissible=admissible,swap_passes=1,complete_samples=complete)
                original16=next(s for s in parent_row['selections'] if s['method']=='pooled_greedy_swap' and s['n']==16)
                if pooled0.text!=original16['text'] or list(pooled0.phrase_ids)!=original16['phrase_ids'] or abs(exact.score(pooled0.phrase_ids)-original16['fits']['exact']['fve'])>1e-5:raise ValueError('D16 component-off reproduction failed')
                for coefficient in (.05,.20):
                    def support_objective(ids):return exact.score(ids)+coefficient/4*sum((len(votes[k])-1)/15 for k in {normalize(pid) for pid in ids})
                    selection=greedy_pool(bullets,support_objective,admissible=admissible,swap_passes=1,complete_samples=complete)
                    record(f'pooling_exact_support_lambda{coefficient:g}',16,selection,parent='pooled_greedy_swap',extra={'lambda':coefficient,'objective':support_objective(selection.phrase_ids)})
                original32=next(s for s in parent_row['selections'] if s['method']=='pooled_greedy_swap' and s['n']==32)
                d32=tuple(Bullet(x['source_phrase_id'],x['text'],x['source_phrase_id'].rsplit(':',1)[0],i) for i,x in enumerate(original32['atoms']))
                if abs(exact.score(tuple(b.phrase_id for b in d32))-original32['fits']['exact']['fve'])>1e-5:raise ValueError('D32 fit changed')
                for loss in (.001,.005):
                    pruned=prune_leave_one_out(d32,exact.score,maximum_loss=loss)
                    record(f'pooled_greedy_swap_then_prune_{loss:g}',32,pruned,parent='pooled_greedy_swap')
                    seed=int(digest(['combination_random_delete_v1',cid,'pooled_greedy_swap',loss])[:16],16)
                    keep=set(random.Random(seed).sample(range(len(d32)),len(pruned.bullets)))
                    record(f'pooled_greedy_swap_random_delete_matched_{loss:g}',32,Selection('random_delete',tuple(b for i,b in enumerate(d32) if i in keep),None),parent='pooled_greedy_swap',extra={'seed':seed})
                bullets,complete=candidate_pool(32)
                pooled=greedy_pool(bullets,objective,admissible=admissible,swap_passes=1,complete_samples=complete)
                record('pooled_specificity_mean',32,pooled,extra={'specificity_objective':objective(pooled.phrase_ids)})
                pruned=prune_leave_one_out(pooled.bullets,exact.score,maximum_loss=.005)
                record('pooled_specificity_mean_then_prune_0.005',32,pruned,parent='pooled_specificity_mean')
                seed=int(digest(['specificity_pool_matched_deletion_v1',cid,.005])[:16],16)
                keep=set(random.Random(seed).sample(range(len(pooled.bullets)),len(pruned.bullets)))
                record('pooled_specificity_mean_random_delete_matched_0.005',32,Selection('random_delete',tuple(b for i,b in enumerate(pooled.bullets) if i in keep),None),parent='pooled_specificity_mean',extra={'seed':seed})
                if conditions is None:conditions=[{'method':s['method'],'n':s['n']} for s in selections]
                declared={(r['method'],r['n']) for r in inventory['conditions'] if r['status'] not in ('exact_alias','obsolete_malformed_transport_diagnostic','computed_numerical_diagnostic_only')}
                if any((s['method'],s['n']) not in declared for s in selections):raise ValueError('Undeclared condition')
                event={k:cell[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')}
                event.update({'selections':selections,'inventory_sha256':a.inventory_sha256,'seconds':time.time()-t0,
                    'original_parent_source':spec['selectors'],'vector_contract_sha256':cache.contract['sha256']})
                out.write(json.dumps(event,ensure_ascii=False)+'\n');out.flush();os.fsync(out.fileno());done.add(cid)
                atomic(a.output/'status.json',{'status':'running','completed_cells':len(done),'expected_cells':len(targets),'seconds':time.time()-start,'last_cell':cid})
                print(json.dumps({'completed_cells':len(done),'expected_cells':len(targets),'cell_seconds':time.time()-t0}),flush=True)
    atomic(a.output/'conditions.json',conditions or [])
    atomic(a.output/'status.json',{'status':'complete','completed_cells':len(done),'expected_cells':len(targets),'selection_sha256':sha(journal),'seconds':time.time()-start,'new_model_calls':0,'new_api_calls':0})

if __name__=='__main__':main()
