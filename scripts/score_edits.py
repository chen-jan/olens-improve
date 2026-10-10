"""Freshly score candidate-only F proposals and retain an unchanged-or-edited beam.

A separate editing cache has one writer; production vectors are read-only. All
original full text survives even when AR sees only its cleaned32-token prefix.
"""
import argparse
from collections import OrderedDict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file,save_file
from transformers import AutoTokenizer
from olens_improve.ar_cache import digest,input_records,vector_key
from olens_improve.reconstruction import FrozenAR,JointNNLS,RawVectorCache,Whitener,ar_token_ids
from olens_improve.editing import validate_lineage,validated_sample


def atomic(path,payload):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(payload,indent=2)+'\n');os.replace(tmp,path)


def main():
    p=argparse.ArgumentParser()
    for name in ('proposals','cells-manifest','fresh-manifest','checkpoint','production-cache','edit-cache','whitener-directory','output'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--runtime',default='configs/runtime.json');p.add_argument('--history')
    p.add_argument('--round',type=int,choices=(1,2),required=True);p.add_argument('--batch-size',type=int,default=32)
    args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use assigned GPU')
    torch.set_num_threads(4);started=time.time();runtime=json.loads(Path(args.runtime).read_text())
    tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda text:len(tok(text,add_special_tokens=False)['input_ids'])
    source_bytes=Path(args.proposals).read_bytes();proposals=list(input_records(source_bytes))
    manifest_bytes=Path(args.cells_manifest).read_bytes();allowed={c['cell_id'] for c in json.loads(manifest_bytes)['cells']}
    fresh_bytes=Path(args.fresh_manifest).read_bytes();fresh={c['cell_id']:c for c in json.loads(fresh_bytes)['cells']}
    previous={}
    if args.round==2 and not args.history:raise ValueError('Round2 needs all round1 scored candidates, not just beam')
    if args.history:
        for row in input_records(Path(args.history).read_bytes()):
            if row['cell_id'] in previous:raise ValueError('Duplicate history cell')
            previous[row['cell_id']]=row['candidates']
    main_cache=RawVectorCache(args.production_cache);contract=main_cache.contract
    for field,path in [('head_sha256','heads.pt'),('adapter_sha256','lora/adapter_model.safetensors'),('meta_sha256','meta.json')]:
        if hashlib.sha256((Path(args.checkpoint)/path).read_bytes()).hexdigest()!=contract[field]:raise ValueError('AR checkpoint differs from cache')
    cache_path=Path(args.edit_cache)/contract['sha256'][:20];cache_path.mkdir(parents=True,exist_ok=True)
    lock=(cache_path/'writer.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (cache_path/'contract.json').exists() and json.loads((cache_path/'contract.json').read_text())!=contract:
        raise ValueError('Editing vector contract changed')
    atomic(cache_path/'contract.json',contract);edit_cache=RawVectorCache(str(cache_path))
    state=torch.load(Path(args.checkpoint)/'heads.pt',map_location='cpu',weights_only=True)
    tags={int(layer):state['tag_ids'][i].tolist() for i,layer in enumerate(state['layers'])}
    candidates_by_cell={};pending=OrderedDict();rejected={}
    for row in proposals:
        cell_id=row['cell_id']
        if cell_id in candidates_by_cell:raise ValueError('Duplicate proposal cell')
        if cell_id not in allowed or fresh[cell_id]['split']!='development' or row['round']!=args.round:
            raise ValueError('Off-cohort or nondevelopment editing proposal')
        validate_lineage(row,previous.get(cell_id,[]),args.round)
        layer=fresh[cell_id]['layer']
        if int(row['layer'])!=layer:raise ValueError('Proposal changed layer')
        variants=OrderedDict((r['candidate_id'],dict(r)) for r in previous.get(cell_id,[]))
        for parent in row['parents']:
            key=parent['candidate_id']
            if key in variants and variants[key]['text']!=parent['text']:raise ValueError('Parent ID text changed')
            variants.setdefault(key,dict(parent)|{'origin':'unchanged_parent','parent_reported_fve':parent.get('exact_fve')})
        new=row['editing']['proposals']
        if len(new)>4:raise ValueError('More than4 aggregate proposals in a round')
        for proposal in new:
            key=proposal['candidate_id']
            if key in variants:raise ValueError('Proposal reused candidate ID')
            variants[key]=dict(proposal)|{'origin':f'editing_round{args.round}'}
        rejected[cell_id]=[];valid=[]
        for candidate in variants.values():
            key=candidate['candidate_id'];text=candidate['text']
            try:
                parsed=validated_sample(text,key,count)
            except ValueError as error:
                rejected[cell_id].append({'candidate_id':key,'reason':str(error)});continue
            # Exact full text is retained, including all qualifiers and whitespace.
            candidate=dict(candidate)|{'text':text,'parser_flags':list(parsed.flags),'atom_metadata':[]}
            for atom in parsed.bullets:
                cleaned,ids=ar_token_ids(tok,atom.text)
                if not ids:raise ValueError('Empty cleaned edit atom')
                cache_key=vector_key(contract['sha256'],tags[layer],ids[:32])
                info={'phrase_id':atom.phrase_id,'text':atom.text,'scored_text':cleaned,'scored_token_ids':ids[:32],
                      'original_token_count':len(ids),'scored_token_count':len(ids[:32]),'truncated':len(ids)>32,
                      'unscored_suffix_ids':ids[32:],'cache_key':cache_key,'layer':layer,'source_span':[atom.start,atom.end]}
                candidate['atom_metadata'].append(info)
                if cache_key not in main_cache.index and cache_key not in edit_cache.index:
                    pending.setdefault(cache_key,{'text':atom.text,'layer':layer,'token_ids':ids[:32],'tag_ids':tags[layer]})
            valid.append(candidate)
        candidates_by_cell[cell_id]=valid
    if set(candidates_by_cell)!=allowed:
        raise ValueError('Editing proposals do not cover the exact frozen cohort')
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    spec={'round':args.round,'proposal_sha256':hashlib.sha256(source_bytes).hexdigest(),
          'cells_manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),'fresh_manifest_sha256':hashlib.sha256(fresh_bytes).hexdigest(),
          'history_sha256':hashlib.sha256(Path(args.history).read_bytes()).hexdigest() if args.history else None,
          'vector_contract':contract,'acceptance_objective':'exact_joint_nnls_fve_only','beam_width':2,
          'all_initial_and_previous_proposals_retained':True,'candidate_ids':{k:[c['candidate_id'] for c in v] for k,v in candidates_by_cell.items()},
          'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path('src/olens_improve/reconstruction.py'),Path('src/olens_improve/editing.py')]},
          'batch_size':args.batch_size,'production_cache_read_only':True,'editing_cache':str(cache_path)}
    if (output/'spec.json').exists() and json.loads((output/'spec.json').read_text())!=spec:raise ValueError('Incompatible F scoring resume')
    atomic(output/'spec.json',spec)
    requested=list(pending.items());ar=None;shard=len(list(cache_path.glob('raw_*.index.json')))
    if requested:ar=FrozenAR.load(runtime['paths']['base_snapshot'],args.checkpoint)
    for start in range(0,len(requested),1024):
        chunk=requested[start:start+1024];vectors=[];encoding_meta=[]
        for offset in range(0,len(chunk),args.batch_size):
            batch=chunk[offset:offset+args.batch_size]
            encoded,metadata=ar.encode_mixed([v['text'] for _,v in batch],[v['layer'] for _,v in batch]);vectors.append(encoded)
            for (_,expected),actual in zip(batch,metadata):
                if actual['input_ids']!=expected['token_ids'] or actual['tag_ids']!=expected['tag_ids']:raise ValueError('Editing scorer token mismatch')
            encoding_meta.extend({'batch_size':len(batch),'padded_token_width':max(m['scored_token_count'] for m in metadata)+6} for _ in batch)
        tensor_path=cache_path/f'raw_{shard:05d}.safetensors';tmp=tensor_path.with_suffix('.safetensors.tmp')
        save_file({'vectors':torch.cat(vectors)},str(tmp));os.replace(tmp,tensor_path)
        atomic(cache_path/f'raw_{shard:05d}.index.json',{'contract_sha256':contract['sha256'],'tensor_path':str(tensor_path),
               'vectors':[{'cache_key':key,'row':index,'layer':data['layer'],'scored_token_ids':data['token_ids'],
                           'tag_ids':data['tag_ids'],'execution':encoding_meta[index]} for index,(key,data) in enumerate(chunk)]})
        shard+=1;print(json.dumps({'new_encoded_vectors':min(start+1024,len(requested)),'total_new_vectors':len(requested)}),flush=True)
    edit_cache=RawVectorCache(str(cache_path));tensor_paths={fresh[k]['activation_tensor_path'] for k in candidates_by_cell}
    if len(tensor_paths)!=1:raise ValueError('Expect one fresh tensor')
    activations=load_file(next(iter(tensor_paths)))['resid'];whiteners={};scored=[];beams=[]
    for cell_id,candidates in candidates_by_cell.items():
        cell=fresh[cell_id];layer=cell['layer'];target=activations[cell['activation_row']]
        if hashlib.sha256(target.numpy().tobytes()).hexdigest()!=cell['activation_sha256']:raise ValueError('Fresh target hash changed')
        if layer not in whiteners:whiteners[layer]=Whitener.load(str(Path(args.whitener_directory)/f'whitening_iolens_pooled_L{layer}.safetensors'))
        raw={}
        for candidate in candidates:
            for atom in candidate['atom_metadata']:
                key=atom['cache_key'];raw[atom['phrase_id']]=main_cache.get(key) if key in main_cache.index else edit_cache.get(key)
        exact=JointNNLS.from_raw(target,raw,whiteners[layer]);legacy=JointNNLS(exact.target,exact.vectors,solver='released80')
        for candidate in candidates:
            ids=[atom['phrase_id'] for atom in candidate['atom_metadata']]
            fit=exact.fit(ids);candidate['exact_fve']=fit.fve;candidate['coefficients']=fit.coefficients;candidate['released80_fve']=legacy.score(ids)
            candidate['token_count']=count(candidate['text']);candidate['bullet_count']=len(ids)
            reported=candidate.get('parent_reported_fve')
            if reported is not None and abs(reported-fit.fve)>1e-5:raise ValueError('Unchanged parent score differs from initial selection')
        ranked=sorted(enumerate(candidates),key=lambda pair:(-pair[1]['exact_fve'],pair[0]))
        best=[candidate for _,candidate in ranked[:2]]
        event={'cell_id':cell_id,'family':cell['family'],'item_id':cell['item_id'],'layer':layer,'position':cell['position'],
               'split':'development','round':args.round,'candidates':candidates,'rejected':rejected[cell_id],
               'best':best[0] if best else None,'spec_sha256':digest(spec),'activation_sha256':cell['activation_sha256']}
        scored.append(event);beams.append({'cell_id':cell_id,'parents':best,'spec_sha256':digest(spec)})
    for filename,rows in [('scored_candidates.jsonl',scored),('beam.jsonl',beams)]:
        tmp=output/(filename+'.tmp');tmp.write_text(''.join(json.dumps(row)+'\n' for row in rows));os.replace(tmp,output/filename)
    atomic(output/'status.json',{'status':'complete','cells':len(scored),'new_raw_vectors':len(requested),
                                'seconds':time.time()-started,'round':args.round,'quality_status':'unjudged'})


if __name__=='__main__':main()
