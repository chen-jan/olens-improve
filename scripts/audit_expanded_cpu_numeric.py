"""Independent three-stage target/control and complete-selector numeric replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.ar_cache import vector_key
from olens_improve.reconstruction import RawVectorCache, Whitener, JointNNLS, ar_token_ids
from olens_improve.selection import best_of_n, output_admissible, parse_bullets
from expanded_cpu_cached import atomic, committed_lines, sha
from expanded_cpu_combinations import CHECKPOINT, WHITENERS

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--inventory-sha256',required=True);p.add_argument('--smoke',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPUs required')
    if sha(a.inventory)!=a.inventory_sha256:raise ValueError('Inventory differs')
    import torch
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    torch.set_num_threads(1)
    inventory=json.loads(a.inventory.read_text());fresh=json.loads(Path(inventory['fresh_manifest']['path']).read_text());cells={c['cell_id']:c for c in fresh['cells']}
    references={r['split']:r for r in committed_lines(a.smoke)}
    if set(references)!={'development','validation','test'}:raise ValueError('Require original three-stage real-cell smoke')
    controls=json.loads(Path(inventory['control_bank']['path']).read_text());runtime=json.loads(Path('configs/runtime.json').read_text())
    tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True);count=lambda t:len(tok(t,add_special_tokens=False)['input_ids']);admissible=output_admissible(count,256)
    state=torch.load(CHECKPOINT/'heads.pt',map_location='cpu',weights_only=True)
    tags={int(layer):state['tag_ids'][i].tolist() for i,layer in enumerate(state['layers'])}
    act=load_file(next(iter({c['activation_tensor_path'] for c in cells.values()})))['resid'];whiteners={};results=[]
    for stage,spec in inventory['stages'].items():
        cid=references[stage]['cell_id'];cell=cells[cid];layer=cell['layer'];pool={}
        for src in spec['samples']:
            for envelope in committed_lines(src['path']):
                for row in envelope.get('records',[envelope]):
                    if row['cell_id']==cid:
                        if row['sample_index'] in pool:raise ValueError('Duplicate pool index')
                        pool[row['sample_index']]=row
        if set(pool)!=set(range(32)):raise ValueError('Incomplete actual source prefix')
        parent=next(r for r in committed_lines(spec['selectors']['path']) if r['cell_id']==cid)
        cache=RawVectorCache(spec['vector_cache']);samples=[];keys={}
        for index,row in sorted(pool.items()):
            if row['activation_sha256']!=cell['activation_sha256']:raise ValueError('Source activation differs')
            sample=parse_bullets(row['text'],f"{row.get('global_pool_id',row['pool_id'])}:{cid}:{index}",index,token_count=count,max_output_tokens=256);samples.append(sample)
            for bullet in sample.bullets:
                _,ids=ar_token_ids(tok,bullet.text)
                if ids:keys[bullet.phrase_id]=vector_key(cache.contract['sha256'],tags[layer],ids[:32])
        if layer not in whiteners:whiteners[layer]=Whitener.load(str(WHITENERS/f'whitening_iolens_pooled_L{layer}.safetensors'))
        w=whiteners[layer];unique=list(dict.fromkeys(keys.values()));v=w.whiten(torch.stack([cache.get(k) for k in unique]));v=v/(v.norm(dim=1,keepdim=True)+1e-9)
        vectors={pid:dict(zip(unique,v))[key] for pid,key in keys.items()}
        bank=controls['control_cell_ids_by_target'][cid];targets={}
        for other in [cid,*bank]:
            raw=act[cells[other]['activation_row']]
            if hashlib.sha256(raw.numpy().tobytes()).hexdigest()!=cells[other]['activation_sha256']:raise ValueError('Activation SHA changed')
            targets[other]=w.whiten(raw.reshape(1,-1))[0]
        own=JointNNLS(targets[cid],vectors);scorers=[JointNNLS(targets[k],vectors) for k in bank]
        def objective(ids):return own.score(ids)-sum(s.score(ids) for s in scorers)/len(scorers)
        valid=lambda bullets:admissible(bullets) and all(b.phrase_id in vectors for b in bullets)
        audit={'stage':stage,'cell_id':cid,'bank_control_ids':bank,'checks':[]}
        for method,objective_fn in [('best_n_exact',own.score),('best_n_specificity_mean',objective)]:
            selected=best_of_n(samples,32,objective_fn,admissible=valid)
            expected=next(s for s in parent['selections'] if s['method']==method and s['n']==32)
            if selected.text!=expected['text'] or list(selected.phrase_ids)!=expected['phrase_ids']:raise ValueError('Complete selected text/IDs changed with threads')
            own_fve=own.score(selected.phrase_ids);difference=abs(own_fve-expected['fits']['exact']['fve'])
            if difference>1e-5:raise ValueError('Own exact FVE changed')
            record={'method':method,'text_identity':True,'phrase_identity':True,'own_fve_absolute_difference':difference}
            if method=='best_n_specificity_mean':
                values=[s.score(selected.phrase_ids) for s in scorers]
                record.update(mean_control_fve_absolute_difference=abs(sum(values)/len(values)-expected['extra']['mean_control_fve']),
                    max_control_fve_absolute_difference=abs(max(values)-expected['extra']['max_control_fve']),
                    specificity_absolute_difference=abs(objective(selected.phrase_ids)-expected['extra']['score']))
                if max(v for k,v in record.items() if k.endswith('absolute_difference'))>1e-5:raise ValueError('Control FVE changed')
            audit['checks'].append(record)
        results.append(audit)
    atomic(a.output,{'status':'passed','inventory_sha256':a.inventory_sha256,'code_sha256':sha(__file__),
        'smoke_sha256':sha(a.smoke),'torch_threads':1,'openblas_threads':os.environ.get('OPENBLAS_NUM_THREADS'),'results':results})
    print(json.dumps({'status':'passed','original_stages':3,'complete_selectors_reproduced':6}),flush=True)

if __name__=='__main__':main()
