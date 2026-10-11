"""Four frozen round-two pruning/deletion controls, from terminal edited vectors."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.ar_cache import digest
from olens_improve.selection import Bullet, prune_leave_one_out, render_bullets
from expanded_cpu_cached import atomic, committed_lines, sha
from expanded_cpu_combinations import WHITENERS, resume

def controls(cid, parent, score, count):
    atoms=parent['atom_metadata'];text=parent['text']
    bullets=tuple(Bullet(a['phrase_id'],a['text'],parent['candidate_id'],i) for i,a in enumerate(atoms))
    ids=tuple(b.phrase_id for b in bullets)
    if len(set(ids))!=len(ids):raise ValueError('Duplicate edited atom')
    if abs(score.score(ids)-parent['exact_fve'])>1e-5:raise ValueError('Edited parent FVE changed')
    selections=[]
    def record(method,retained,trace,extra):
        selected_ids=tuple(b.phrase_id for b in retained)
        emitted=text if selected_ids==ids else render_bullets(retained)
        tokens=count(emitted)
        if tokens>256 or len(retained)>4:raise ValueError('Edited pruning violates cap')
        selections.append({'method':method,'n':32,'text':emitted,'token_count':tokens,
            'bullet_count':len(retained),'phrase_ids':list(selected_ids),
            'atoms':[a for a in atoms if a['phrase_id'] in selected_ids],
            'fits':{'exact':score.fit(selected_ids).__dict__},'trace':list(trace),
            'parent_method':'editing_round2','parent_candidate_id':parent['candidate_id'],
            'parent_text':text,'parent_fve':parent['exact_fve'],'extra':extra})
    for loss in (.001,.005):
        pruned=prune_leave_one_out(bullets,score.score,maximum_loss=loss)
        record(f'editing_round2_then_prune_{loss:g}',pruned.bullets,pruned.trace,
               {'maximum_loss_per_sequential_deletion':loss})
        seed=int(digest(['combination_random_delete_v1',cid,'editing_round2',loss])[:16],16)
        keep=set(random.Random(seed).sample(range(len(bullets)),len(pruned.bullets)))
        retained=tuple(b for i,b in enumerate(bullets) if i in keep)
        record(f'editing_round2_random_delete_matched_{loss:g}',retained,(),
               {'seed':seed,'matched_retained_bullets':len(pruned.bullets)})
    return selections

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--inventory-sha256',required=True);p.add_argument('--editing-source',type=Path,required=True)
    p.add_argument('--family',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--threads',type=int,default=4);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU required')
    if sha(a.inventory)!=a.inventory_sha256:raise ValueError('Expansion seal changed')
    import torch
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    from olens_improve.reconstruction import RawVectorCache, JointNNLS, Whitener
    torch.set_num_threads(a.threads);started=time.time()
    inventory=json.loads(a.inventory.read_text());fresh_path=Path(inventory['fresh_manifest']['path'])
    if sha(fresh_path)!=inventory['fresh_manifest']['sha256']:raise ValueError('Fresh activation manifest changed')
    fresh={c['cell_id']:c for c in json.loads(fresh_path.read_text())['cells']}
    own={cid:c for cid,c in fresh.items() if c['family']==a.family}
    if a.family not in inventory['families'] or not own:raise ValueError('Unknown frozen family')
    source=a.editing_source/'scored_candidates.jsonl';parent_spec=a.editing_source/'spec.json'
    terminal=a.editing_source/'status.json';status=json.loads(terminal.read_text());editing=json.loads(parent_spec.read_text())
    if status['status']!='complete' or status['round']!=2 or status['cells']!=len(own):raise ValueError('Round-two family scoring not complete')
    if editing['round']!=2 or editing['sealed_manifest_sha256']!=a.inventory_sha256 or editing['fresh_manifest_sha256']!=inventory['fresh_manifest']['sha256'] or editing['vector_contract']!=inventory['vector_contract']:raise ValueError('Editor authority or vector contract differs')
    if editing['acceptance_objective']!='exact_joint_nnls_fve_only' or editing['beam_width']!=2 or editing['all_initial_and_previous_proposals_retained'] is not True:raise ValueError('Editor scoring contract differs')
    runtime=json.loads(Path('configs/runtime.json').read_text())
    tokenizer=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda text:len(tokenizer(text,add_special_tokens=False)['input_ids'])
    caches=[RawVectorCache(str(path)) for path in dict.fromkeys([r['vector_cache'] for r in inventory['stages'].values()]+[editing['editing_cache']])]
    if any(cache.contract!=inventory['vector_contract'] for cache in caches):raise ValueError('Edited/source cache contract differs')
    source_sha=sha(source);spec={'inventory_sha256':a.inventory_sha256,'editing_source_sha256':source_sha,
        'fresh_manifest_sha256':inventory['fresh_manifest']['sha256'],'parent_condition_id':'editing_round2-n32',
        'solver':'scipy_exact','objective':'1-squared_residual/squared_target',
        'editor_spec_sha256':sha(parent_spec),'terminal_sha256':sha(terminal),'family':a.family,
        'code_sha256':{str(path):sha(path) for path in [Path(__file__),Path('src/olens_improve/selection.py'),Path('src/olens_improve/reconstruction.py')]},
        'thresholds':[.001,.005],'random_seed_contract':'combination_random_delete_v1',
        'vector_contract_sha256':inventory['vector_contract']['sha256'],'threads':a.threads}
    a.output.mkdir(parents=True,exist_ok=True);spec_path=a.output/f'{a.family}.spec.json';journal=a.output/f'{a.family}.journal.jsonl'
    if spec_path.exists() and json.loads(spec_path.read_text())!=spec:raise ValueError('Pruning resume contract changed')
    atomic(spec_path,spec);done=resume(journal,a.inventory_sha256)
    if not done<=set(own):raise ValueError('Foreign resume cell')
    tensors={path:load_file(path)['resid'] for path in {c['activation_tensor_path'] for c in own.values()}}
    whiteners={};seen=set();menu=None;declared={(r['method'],r['n']) for r in inventory['conditions']}
    with journal.open('a') as stream:
        for row in committed_lines(source):
            cid=row['cell_id']
            if cid in seen or cid not in own:raise ValueError('Duplicate/foreign editor cell')
            seen.add(cid);cell=own[cid]
            if any(row[k]!=cell[k] for k in ('family','item_id','layer','position','split','activation_sha256')) or row['round']!=2 or row['spec_sha256']!=digest(editing):raise ValueError('Edited parent identity differs')
            best=row['best']
            if best is None or not row['candidates'] or best!=sorted(enumerate(row['candidates']),key=lambda pair:(-pair[1]['exact_fve'],pair[0]))[0][1]:raise ValueError('Edited parent is not exact chosen candidate')
            if cid in done:continue
            target=tensors[cell['activation_tensor_path']][cell['activation_row']]
            if hashlib.sha256(target.numpy().tobytes()).hexdigest()!=cell['activation_sha256']:raise ValueError('Target activation changed')
            layer=cell['layer']
            if layer not in whiteners:whiteners[layer]=Whitener.load(str(WHITENERS/f'whitening_iolens_pooled_L{layer}.safetensors'))
            raw={}
            for atom in best['atom_metadata']:
                if atom['layer']!=layer:raise ValueError('Edited atom layer differs')
                cache=next((cache for cache in caches if atom['cache_key'] in cache.index),None)
                if cache is None:raise ValueError('Fresh edited vector unavailable')
                raw[atom['phrase_id']]=cache.get(atom['cache_key'])
            score=JointNNLS.from_raw(target,raw,whiteners[layer]);selections=controls(cid,best,score,count)
            current=[{'method':s['method'],'n':s['n']} for s in selections]
            if menu is None:menu=current
            if menu!=current or any((s['method'],s['n']) not in declared for s in selections):raise ValueError('Frozen pruning menu differs')
            event={k:cell[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')}
            event.update(inventory_sha256=a.inventory_sha256,selections=selections)
            stream.write(json.dumps(event,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno());done.add(cid)
            if len(done)%32==0:atomic(a.output/f'{a.family}.status.json',{'status':'running','completed_cells':len(done),'expected_cells':len(own),'seconds':time.time()-started})
    if seen!=set(own) or done!=set(own) or sha(source)!=source_sha or sha(parent_spec)!=spec['editor_spec_sha256'] or sha(terminal)!=spec['terminal_sha256']:raise ValueError('Incomplete/changed editing family')
    destination=a.output/f'{a.family}.jsonl';temp=destination.with_suffix('.jsonl.tmp')
    with temp.open('w') as stream:
        for row in committed_lines(journal):
            row['selections']=[{k:s[k] for k in ('method','n','text','token_count','bullet_count')} for s in row['selections']]
            if menu is None:menu=[{'method':s['method'],'n':s['n']} for s in row['selections']]
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    if destination.exists() and sha(destination)!=sha(temp):raise ValueError('Immutable pruning export changed')
    os.replace(temp,destination);destination.chmod(0o444)
    manifest=a.output/f'{a.family}.manifest.json'
    atomic(manifest,{'schema_version':1,'split':'expansion','scope':inventory['scope'],'inventory_sha256':a.inventory_sha256,
        'cells':[{k:c[k] for k in ('cell_id','family','item_id','layer','position','split','group_id','activation_sha256')} for c in own.values()]})
    descriptor={'ready':True,'family':a.family,'manifest':str(manifest),'manifest_sha256':sha(manifest),
        'selections':str(destination),'selection_sha256':sha(destination),'conditions':menu,'inventory_sha256':a.inventory_sha256,
        'source_parents':[{'path':str(source),'sha256':source_sha},{'path':str(parent_spec),'sha256':spec['editor_spec_sha256']},
            {'path':str(journal),'sha256':sha(journal)},{'path':str(spec_path),'sha256':sha(spec_path)}],
        'cells':len(own),'items':len({c['item_id'] for c in own.values()})}
    atomic(a.output/f'{a.family}.ready.json',descriptor)
    atomic(a.output/f'{a.family}.status.json',{'status':'complete','completed_cells':len(done),'expected_cells':len(own),
        'seconds':time.time()-started,'selection_sha256':sha(destination),'journal_sha256':sha(journal),'new_model_calls':0,'new_api_calls':0})
    print(json.dumps({'status':'complete','family':a.family,'cells':len(own),'descriptor':str(a.output/f'{a.family}.ready.json')}))

if __name__=='__main__':main()
