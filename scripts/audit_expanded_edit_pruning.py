"""Replay the editor-pruning core on three actual frozen D32 source parents."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from expanded_cpu_cached import atomic, committed_lines, sha
from expanded_cpu_combinations import WHITENERS
from expanded_edit_pruning import controls

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory-sha256',required=True)
    p.add_argument('--smoke',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU required')
    inventory_path=Path('configs/expansion_manifest_v1.json')
    if sha(inventory_path)!=a.inventory_sha256:raise ValueError('Inventory changed')
    import torch
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    from olens_improve.reconstruction import JointNNLS, RawVectorCache, Whitener
    torch.set_num_threads(1);inventory=json.loads(inventory_path.read_text())
    fresh_path=Path(inventory['fresh_manifest']['path'])
    if sha(fresh_path)!=inventory['fresh_manifest']['sha256']:raise ValueError('Fresh manifest changed')
    cells={c['cell_id']:c for c in json.loads(fresh_path.read_text())['cells']}
    refs={r['split']:r for r in committed_lines(a.smoke)}
    if set(refs)!={'development','validation','test'}:raise ValueError('Require three actual original stages')
    runtime=json.loads(Path('configs/runtime.json').read_text());tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda text:len(tok(text,add_special_tokens=False)['input_ids'])
    tensors={p:load_file(p)['resid'] for p in {cells[r['cell_id']]['activation_tensor_path'] for r in refs.values()}}
    whiteners={};results=[]
    for stage,reference in refs.items():
        spec=inventory['stages'][stage];selector=spec['selectors']
        if sha(selector['path'])!=selector['sha256']:raise ValueError('Original selector changed')
        cid=reference['cell_id'];cell=cells[cid];layer=cell['layer']
        source=next(row for row in committed_lines(selector['path']) if row['cell_id']==cid)
        selected=next(s for s in source['selections'] if s['method']=='pooled_greedy_swap' and s['n']==32)
        atoms=[dict(a,phrase_id=a.get('phrase_id',a['source_phrase_id'])) for a in selected['atoms']]
        cache=RawVectorCache(spec['vector_cache'])
        if cache.contract!=inventory['vector_contract']:raise ValueError('Original vector contract changed')
        raw={a['phrase_id']:cache.get(a['cache_key']) for a in atoms}
        target=tensors[cell['activation_tensor_path']][cell['activation_row']]
        if hashlib.sha256(target.numpy().tobytes()).hexdigest()!=cell['activation_sha256']:raise ValueError('Actual activation changed')
        if layer not in whiteners:whiteners[layer]=Whitener.load(str(WHITENERS/f'whitening_iolens_pooled_L{layer}.safetensors'))
        score=JointNNLS.from_raw(target,raw,whiteners[layer]);parent={'candidate_id':'actual-original-D32-parent',
            'text':selected['text'],'exact_fve':selected['fits']['exact']['fve'],'atom_metadata':atoms}
        outputs=controls(cid,parent,score,count)
        checks=[]
        for loss in (.001,.005):
            expected=next(s for s in reference['selections'] if s['method']==f'pooled_greedy_swap_then_prune_{loss:g}')
            actual=next(s for s in outputs if s['method']==f'editing_round2_then_prune_{loss:g}')
            if actual['text']!=expected['text'] or actual['phrase_ids']!=expected['phrase_ids']:raise ValueError('Shared pruning numerical core changed selected source bullets')
            delta=abs(actual['fits']['exact']['fve']-expected['fits']['exact']['fve'])
            if delta>1e-5:raise ValueError('Pruning fit changed')
            checks.append({'threshold':loss,'text_identity':True,'phrase_identity':True,'fve_absolute_difference':delta})
        results.append({'stage':stage,'cell_id':cid,'source_selector_sha256':selector['sha256'],'checks':checks})
    atomic(a.output,{'status':'passed','scope':'three actual original D32 parents; shared pruning core, not new editor model outputs',
        'inventory_sha256':a.inventory_sha256,'smoke_sha256':sha(a.smoke),'code_sha256':sha('scripts/expanded_edit_pruning.py'),
        'torch_threads':1,'openblas_threads':os.environ.get('OPENBLAS_NUM_THREADS'),'results':results})
    print(json.dumps({'status':'passed','stages':3,'pruning_conditions_reproduced':6}))

if __name__=='__main__':main()
