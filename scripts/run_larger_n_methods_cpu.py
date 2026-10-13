"""Frozen best/prune/pool/pool-prune algorithms on the saved N32/N64 pilot.

CPU and existing AR caches only; no labels, helpers, new vectors or generation.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.reconstruction import JointNNLS,RawVectorCache,Whitener
from olens_improve.selection import greedy_pool,prune_leave_one_out,output_admissible
from score_larger_n_pilot import load_inputs,prepare_samples,extended_best,verify_contract
from compare_selectors import pool_candidates

ROOT=Path('${OLENS_DATA_ROOT}/larger-n-pilot-v1')
PILOT=Path('configs/larger_n_pilot_batch256_v2.json')
PILOT_SHA='d8f2f0ee8f07397cd7fc9147e7fcf34d6f5a48939b939c9593ad46733e042af8'
CHECKPOINT=Path('${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/models--agu18dec--olens_and_ar/snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/ar_ptag_pooled')
WHITENERS=Path('${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners')


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(p,obj):
    body=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if p.exists() and p.read_text()!=body:raise ValueError(f'Immutable output changed: {p}')
    p.write_text(body)


def contexts():
    import torch
    from safetensors import safe_open
    from transformers import AutoTokenizer
    torch.set_num_threads(min(4,int(os.environ.get('SLURM_CPUS_PER_TASK','2'))))
    assert sha(PILOT)==PILOT_SHA
    manifest=json.loads(PILOT.read_text());path=ROOT/'sampling/samples_n064.jsonl'
    ready=json.loads(path.with_suffix('.ready.json').read_text())
    assert ready['samples_sha256']==sha(path) and ready['manifest_sha256']==PILOT_SHA
    cells,records=load_inputs(manifest,path,64)
    old=RawVectorCache(manifest['vector_cache']);new=RawVectorCache(str(ROOT/'score256/ar-cache'))
    assert old.contract==new.contract
    verify_contract(old,CHECKPOINT)
    state=torch.load(CHECKPOINT/'heads.pt',map_location='cpu',weights_only=True)
    tags={int(l):state['tag_ids'][i].tolist() for i,l in enumerate(state['layers'])}
    tok=AutoTokenizer.from_pretrained(manifest['base_snapshot'],local_files_only=True)
    samples,atoms,pending,count=prepare_samples(cells,records,tok,old.contract,tags,64)
    missing=[k for k in pending if k not in old.index and k not in new.index]
    if missing:raise ValueError(f'Missing existing AR vectors: {len(missing)}')
    reference={r['cell_id']:r for r in map(json.loads,(ROOT/'score256/selections.jsonl').read_text().splitlines())}
    whiteners={}
    for cid,c in sorted(cells.items(),key=lambda item:(item[1]['layer'],item[0])):
        if c['layer'] not in whiteners:whiteners[c['layer']]=Whitener.load(str(WHITENERS/f"whitening_iolens_pooled_L{c['layer']}.safetensors"))
        w=whiteners[c['layer']]
        with safe_open(c['activation_tensor_path'],framework='pt',device='cpu') as f:
            raw=f.get_slice('resid')[c['activation_row']:c['activation_row']+1][0]
        assert hashlib.sha256(raw.numpy().tobytes()).hexdigest()==c['activation_sha256']
        keys=sorted({a['cache_key'] for a in atoms[cid].values() if a['cache_key']})
        transformed=w.whiten(torch.stack([old.get(k) if k in old.index else new.get(k) for k in keys]))
        transformed=transformed/(transformed.norm(dim=1,keepdim=True)+1e-9)
        bykey=dict(zip(keys,transformed));vectors={pid:bykey[a['cache_key']] for pid,a in atoms[cid].items() if a['cache_key']}
        yield c,samples[cid],atoms[cid],w.whiten(raw.reshape(1,-1))[0],vectors,count,reference[cid]


def main(out):
    assert os.environ.get('SLURM_JOB_ID'), 'CPU allocation required'
    out.mkdir(parents=True,exist_ok=True);(out/'cells').mkdir(exist_ok=True)
    spec={'scope':'32 fixed development sites, 8/task; no official full-grid score',
          'pilot_sha256':PILOT_SHA,'sample_sha256':sha(ROOT/'sampling/samples_n064.jsonl'),
          'code_sha256':{str(p):sha(p) for p in [Path(__file__),Path('src/olens_improve/selection.py'),Path('src/olens_improve/reconstruction.py'),Path('scripts/compare_selectors.py')]},
          'prefixes':[32,64],'prune_maximum_loss':.005,'pool_swap_passes':1,'max_bullets':4,'max_qwen_tokens':256,
          'new_vectors':0,'new_olens_samples':0,'other_activations':False}
    write(out/'spec.json',spec)
    rows=[]
    for c,samples,atoms,target,vectors,count,reference in contexts():
        p=out/'cells'/(hashlib.sha256(c['cell_id'].encode()).hexdigest()[:24]+'.json')
        if p.exists():rows.append(json.loads(p.read_text()));continue
        start=time.monotonic();score=JointNNLS(target,vectors)
        admissible=output_admissible(count,256)
        eligible=lambda bs:admissible(bs) and all(b.phrase_id in vectors for b in bs)
        selections=[]
        for n in (32,64):
            best=extended_best(samples,n,score.score,eligible)
            saved=next(r for r in reference['results'] if r['n']==n)
            assert best.text==saved['text'] and abs(best.score-saved['fits']['exact']['fve'])<1e-5
            bullets,complete=pool_candidates(samples,n,vectors)
            pool=greedy_pool(bullets,score.score,admissible=admissible,swap_passes=1,complete_samples=complete)
            choices=[('best_n_exact',best),('prune_loo_best_0.005',prune_leave_one_out(best.bullets,score.score,maximum_loss=.005)),
                     ('pooled_greedy_swap',pool),('pooled_greedy_swap_then_prune_0.005',prune_leave_one_out(pool.bullets,score.score,maximum_loss=.005))]
            for method,choice in choices:
                assert eligible(choice.bullets)
                selections.append({'method':method,'n':n,'text':choice.text,'phrase_ids':list(choice.phrase_ids),
                    'token_count':count(choice.text),'bullet_count':len(choice.bullets),'fits':{'exact':asdict(score.fit(choice.phrase_ids))},
                    'trace':list(choice.trace),'atoms':[atoms[b.phrase_id] for b in choice.bullets]})
        row={k:c[k] for k in ('cell_id','family','item_id','layer','position','split','group_id','activation_sha256')}
        row.update(selections=selections,seconds=time.monotonic()-start)
        write(p,row);rows.append(row)
        print(json.dumps({'completed':len(rows),'total':32,'cell_id':c['cell_id'],'seconds':row['seconds']}),flush=True)
    rows.sort(key=lambda r:r['cell_id'])
    body=''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows)
    (out/'selections.jsonl').write_text(body)
    print(json.dumps({'status':'complete','cells':len(rows),'sha256':sha(out/'selections.jsonl')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
