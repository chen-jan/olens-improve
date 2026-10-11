"""Post-hoc semantic/likelihood fits from frozen existing vectors only."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import time

from expanded_cpu_cached import atomic, committed_lines, sha
from expanded_cpu_combinations import CHECKPOINT, WHITENERS
from olens_improve.ar_cache import vector_key
from olens_improve.reconstruction import JointNNLS, RawVectorCache, Whitener, ar_token_ids
from olens_improve.selection import parse_bullets, render_bullets


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--inventory', type=Path, default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--inventory-sha256', required=True)
    p.add_argument('--ready-directory', action='append', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--shard-index', type=int, default=0); p.add_argument('--shard-count', type=int, default=1)
    p.add_argument('--fixture', action='store_true'); p.add_argument('--threads', type=int, default=4)
    p.add_argument('--interrupt-after-cells',type=int,default=0)
    a = p.parse_args()
    if a.interrupt_after_cells and (not a.fixture or a.interrupt_after_cells<1):raise ValueError('Controlled interruption is fixture-only')
    if not os.environ.get('SLURM_JOB_ID'): raise RuntimeError('Allocated CPU required')
    if sha(a.inventory) != a.inventory_sha256: raise ValueError('Expansion seal changed')
    import torch
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    torch.set_num_threads(a.threads); started = time.time()
    inventory = json.loads(a.inventory.read_text()); pins = {str(a.inventory): a.inventory_sha256}
    fresh = Path(inventory['fresh_manifest']['path'])
    if sha(fresh) != inventory['fresh_manifest']['sha256']: raise ValueError('Fresh source changed')
    pins[str(fresh)] = sha(fresh); cells = {c['cell_id']: c for c in json.loads(fresh.read_text())['cells']}
    items = sorted({(c['family'], c['item_id']) for c in cells.values()})
    own_items = set(items[a.shard_index::a.shard_count])
    own = {cid for cid, c in cells.items() if (c['family'], c['item_id']) in own_items}
    selections = defaultdict(dict)
    for directory in a.ready_directory:
        for ready in sorted(directory.glob('*.ready.json')):
            d = json.loads(ready.read_text())
            if not d['ready'] or d['inventory_sha256'] != a.inventory_sha256: raise ValueError('Unsealed descriptor')
            path = Path(d['selections'])
            if sha(path) != d['selection_sha256']: raise ValueError('Selection source changed')
            pins[str(ready)] = sha(ready); pins[str(path)] = d['selection_sha256']
            manifest = Path(d['manifest'])
            if sha(manifest) != d['manifest_sha256']: raise ValueError('Family source changed')
            pins[str(manifest)] = d['manifest_sha256']; seen = set()
            for row in committed_lines(path):
                cid = row['cell_id']; cell = cells[cid]
                if cid in seen or any(row[k] != cell[k] for k in ('family','item_id','layer','position','split','activation_sha256')): raise ValueError('Published identity changed')
                seen.add(cid)
                if cid not in own: continue
                for s in row['selections']:
                    condition = f'{s["method"]}-n{s["n"]}'
                    if not (s['method'].startswith('consensus_semantic_v5') or s['method'] in ('likelihood_true_minus_mean_two_controls','own_mean_log_likelihood','control_mean_log_likelihood')): continue
                    if condition in selections[cid] and selections[cid][condition] != s: raise ValueError('Conflicting output')
                    selections[cid][condition] = s
            if seen != {cid for cid,c in cells.items() if c['family']==d['family']}: raise ValueError('Incomplete family descriptor')
    own = set(selections)
    if a.fixture:
        # Actual DEV/VAL/TEST sources, plus each available family to expose its parser.
        required = [('split', k) for k in ('development','validation','test')]
        required += [('family', k) for k in inventory['families']]
        own = {next((cid for cid in sorted(own) if cells[cid][field] == value), None) for field,value in required} - {None}
        selections = {cid: selections[cid] for cid in own}
    a.output.mkdir(parents=True, exist_ok=True); journal = a.output/'fits.jsonl'
    implementation = {str(Path(__file__)):sha(__file__), 'src/olens_improve/reconstruction.py':sha('src/olens_improve/reconstruction.py'),
                      'src/olens_improve/selection.py':sha('src/olens_improve/selection.py'), 'src/olens_improve/ar_cache.py':sha('src/olens_improve/ar_cache.py')}
    spec = {'inventory_sha256':a.inventory_sha256,'source_sha256':pins,'implementation_sha256':implementation,
            'shard_index':a.shard_index,'shard_count':a.shard_count,'fixture':a.fixture,'expected_cells':len(own),
            'objective':'1-squared_residual/squared_target','solver':'scipy_exact','vector_contract':inventory['vector_contract'],
            'normalization':{'center_predictions':True,'whitening_ridge_c':0.1,'unit_phrase_directions':True,
                'phrase_norm_epsilon':1e-9,'target_unit_normalized':False,'clip_fve':False,'scored_atom_tokens':32},
            'scope':'post_hoc_descriptive_secondary; existing cached vectors; no encoding or selection change',
            'resume_pin_policy':'durable_cumulative_used_source_map_v2; pinned before each dependent journal commit'}
    if (a.output/'spec.json').exists() and json.loads((a.output/'spec.json').read_text()) != spec: raise ValueError('Changed replay resume authority')
    atomic(a.output/'spec.json', spec); spec_sha = sha(a.output/'spec.json'); done = set()
    if journal.exists():
        with journal.open('rb+') as stream:
            boundary = 0
            while line := stream.readline():
                if not line.endswith(b'\n'): stream.truncate(boundary); break
                row = json.loads(line)
                if row['cell_id'] in done or row['spec_sha256'] != spec_sha: raise ValueError('Incompatible committed replay')
                done.add(row['cell_id']); boundary = stream.tell()
    if not done <= own: raise ValueError('Foreign replay cell')
    resumed_existing_cells=len(done);source_map=a.output/'source-pins.json'
    if source_map.exists():
        restored=json.loads(source_map.read_text())
        if restored['spec_sha256']!=spec_sha:raise ValueError('Resume source-map authority differs')
        for path,value in restored['source_sha256'].items():
            if sha(path)!=value or path in pins and pins[path]!=value:raise ValueError('Previously committed replay source changed')
            pins[path]=value
    elif done:
        raise ValueError('Committed replay rows lack cumulative source-map receipt')
    runtime = json.loads(Path('configs/runtime.json').read_text())
    tok = AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'], local_files_only=True)
    count = lambda text: len(tok(text,add_special_tokens=False)['input_ids'])
    head = CHECKPOINT/'heads.pt'
    if sha(head) != inventory['vector_contract']['head_sha256']: raise ValueError('Frozen tag heads changed')
    pins[str(head)] = sha(head); state = torch.load(head, map_location='cpu', weights_only=True)
    tags = {int(layer):state['tag_ids'][i].tolist() for i,layer in enumerate(state['layers'])}
    tensor_paths = {c['activation_tensor_path'] for c in cells.values()}
    if len(tensor_paths) != 1: raise ValueError('Expected global frozen tensor')
    tensor_path = next(iter(tensor_paths)); pins[tensor_path] = sha(tensor_path)
    activations = load_file(tensor_path)['resid']; whiteners = {}; whitening_pins = {}; vector_files = set()
    with journal.open('a') as output:
        for stage, stage_spec in inventory['stages'].items():
            required = {cid for cid in own-done if cells[cid]['split']==stage}
            if not required: continue
            pool = defaultdict(dict)
            for source in stage_spec['samples']:
                if sha(source['path']) != source['sha256']: raise ValueError('Original pool changed')
                pins[source['path']] = source['sha256']
                for envelope in committed_lines(source['path']):
                    for row in envelope.get('records',[envelope]):
                        if row['cell_id'] in required:
                            if row['sample_index'] in pool[row['cell_id']]: raise ValueError('Duplicate pool sample')
                            pool[row['cell_id']][row['sample_index']] = row
            if set(pool) != required or any(set(v)!=set(range(32)) for v in pool.values()): raise ValueError('Original pool incomplete')
            original = Path(stage_spec['selectors']['path'])
            if sha(original) != stage_spec['selectors']['sha256']: raise ValueError('A32 source changed')
            pins[str(original)] = stage_spec['selectors']['sha256']; cache = RawVectorCache(stage_spec['vector_cache'])
            if cache.contract != inventory['vector_contract']: raise ValueError('Original vector contract changed')
            cache_path = Path(stage_spec['vector_cache'])
            pins[str(cache_path/'contract.json')] = sha(cache_path/'contract.json')
            for index_path in sorted(cache_path.glob('raw_*.index.json')):
                pins[str(index_path)] = sha(index_path)
            for original_row in committed_lines(original):
                cid = original_row['cell_id']
                if cid not in required: continue
                cell = cells[cid]; layer = cell['layer']; raw = activations[cell['activation_row']]
                if hashlib.sha256(raw.numpy().tobytes()).hexdigest() != cell['activation_sha256']: raise ValueError('Target activation changed')
                if layer not in whiteners:
                    wp = WHITENERS/f'whitening_iolens_pooled_L{layer}.safetensors'
                    whiteners[layer] = Whitener.load(str(wp)); whitening_pins[str(wp)] = sha(wp)
                w = whiteners[layer]; sources = pool.pop(cid); parsed = {}; keys = {}; selected_ids = {}; invalid = {}
                for condition, s in selections[cid].items():
                    if 'sample_index' in s:
                        index = s['sample_index']; indices = [] if index is None else [index]
                    else:
                        indices = sorted({int(pid.rsplit(':',2)[1][1:]) for pid in s['phrase_ids']})
                    for index in indices:
                        if index not in parsed:
                            source = sources[index]
                            if source['activation_sha256'] != cell['activation_sha256']: raise ValueError('Pool target differs')
                            parsed[index] = parse_bullets(source['text'],f'{cid}:s{index:02d}',index,token_count=count,max_output_tokens=256)
                    ids = list(s.get('phrase_ids', [])) if 'phrase_ids' in s else ([] if index is None else [b.phrase_id for b in parsed[index].bullets])
                    atoms = {b.phrase_id:b for i in indices for b in parsed[i].bullets}
                    if any(pid not in atoms for pid in ids) or render_bullets([atoms[pid] for pid in ids]) != s['text']: raise ValueError('Verbatim source atoms do not reproduce chosen text')
                    if len(ids) != s['bullet_count'] or count(s['text']) != s['token_count']: raise ValueError('Chosen text cap/parser differs')
                    selected_ids[condition] = ids
                    for pid in ids:
                        _, token_ids = ar_token_ids(tok, atoms[pid].text)
                        if not token_ids: invalid[condition] = 'unavailable_AR_empty_after_cleanup'; continue
                        keys[pid] = vector_key(cache.contract['sha256'], tags[layer], token_ids[:32])
                parent = next(s for s in original_row['selections'] if s['method']=='best_n_exact' and s['n']==32)
                for atom in parent['atoms']: keys[atom['source_phrase_id']] = atom['cache_key']
                unique = list(dict.fromkeys(keys.values())); transformed = w.whiten(torch.stack([cache.get(key) for key in unique])) if unique else torch.empty((0,len(raw)))
                vector_files.update(cache.index[key]['tensor_path'] for key in unique)
                used_paths={cache.index[key]['tensor_path'] for key in unique}|{str(WHITENERS/f'whitening_iolens_pooled_L{layer}.safetensors')}
                changed=False
                for path in used_paths:
                    if path not in pins:pins[path]=sha(path);changed=True
                if changed or not source_map.exists():
                    atomic(source_map,{'spec_sha256':spec_sha,'source_sha256':pins})
                transformed = transformed/(transformed.norm(dim=1,keepdim=True)+1e-9)
                vectors = {pid:dict(zip(unique,transformed))[key] for pid,key in keys.items()}
                scorer = JointNNLS(w.whiten(raw.reshape(1,-1))[0],vectors)
                parent_fve = scorer.score(parent['phrase_ids'])
                if parent['fits'] is None or abs(parent_fve-parent['fits']['exact']['fve']) > 1e-5: raise ValueError('Saved A32 reference fit not reproduced')
                fits = []
                for condition,s in selections[cid].items():
                    ids = selected_ids[condition]; unavailable = invalid.get(condition)
                    fits.append({'condition':condition,'text_sha256':hashlib.sha256(s['text'].encode()).hexdigest(),
                        'phrase_ids':ids,'bullet_count':s['bullet_count'],'token_count':s['token_count'],
                        'fve':None if unavailable else (scorer.score(ids) if ids else 0.),
                        'status':unavailable or ('explicit_empty_fit_zero' if not ids else 'cached_exact_replay'),
                        'solver':'scipy_exact','fits_scope':'emitted_bullets'})
                event = {k:cell[k] for k in ('cell_id','family','item_id','group_id','layer','position','split','activation_sha256')}
                event.update({'fits':fits,'a32_fve':parent_fve,'a32_saved_fve':parent['fits']['exact']['fve'],
                              'whitener_sha256':w.artifact_sha256,'spec_sha256':spec_sha,'inventory_sha256':a.inventory_sha256})
                output.write(json.dumps(event,ensure_ascii=False)+'\n');output.flush();os.fsync(output.fileno());done.add(cid)
                if a.interrupt_after_cells and len(done)==a.interrupt_after_cells:
                    atomic(a.output/'status.json',{'status':'controlled_interrupted_fixture','completed_cells':len(done),
                        'expected_cells':len(own),'source_map_sha256':sha(source_map),'seconds':time.time()-started})
                    print(json.dumps({'status':'controlled_interrupted_fixture','cells':len(done)}),flush=True)
                    return
                if len(done)%25==0:
                    atomic(a.output/'status.json',{'status':'running','completed_cells':len(done),'expected_cells':len(own),'seconds':time.time()-started})
                    print(json.dumps({'completed_cells':len(done),'seconds':time.time()-started}),flush=True)
    if done != own: raise ValueError('Replay grid incomplete')
    pins.update(whitening_pins)
    for vector_path in sorted(vector_files): pins[vector_path] = sha(vector_path)
    if any(sha(path)!=value for path,value in pins.items()): raise ValueError('Replay source changed during scoring')
    if any(sha(path)!=value for path,value in implementation.items()):raise ValueError('Replay implementation changed during scoring')
    atomic(source_map,{'spec_sha256':spec_sha,'source_sha256':pins})
    atomic(a.output/'status.json',{'status':'complete','completed_cells':len(done),'expected_cells':len(own),
        'fits_sha256':sha(journal),'source_sha256':pins,'implementation_sha256':implementation,
        'resumed_existing_cells':resumed_existing_cells,'source_map_sha256':sha(source_map),'seconds':time.time()-started})
    print(json.dumps({'status':'complete','cells':len(done),'seconds':time.time()-started,'output':str(journal)}),flush=True)


if __name__ == '__main__': main()
