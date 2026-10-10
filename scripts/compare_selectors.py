"""Offline candidate-only A/C/D/E1 development comparison on a fixed shared pool.

GPU-free but CPU-heavy: use the assigned Slurm CPU allocation. Scientific verdicts
come from subsequent blind judging; FVE is recorded only as selection evidence.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import random
import time

import torch
from safetensors.torch import load_file
from transformers import AutoTokenizer
from olens_improve.ar_cache import digest, input_records
from olens_improve.contrastive import control_specificity
from olens_improve.reconstruction import JointNNLS, RawVectorCache, Whitener
from olens_improve.selection import (Selection, best_of_n, greedy_pool, output_admissible,
                                    parse_bullets, prune_leave_one_out, render_bullets)


def atomic_json(path, payload):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(payload,indent=2)+'\n'); os.replace(temporary,path)


def random_complete_selection(samples, n, admissible, rng):
    eligible=[s for s in samples[:n] if not s.parsing_uncertain and admissible(s.bullets)]
    if not eligible:
        return Selection('random_complete',(),None,reason='no_eligible_complete_sample')
    return Selection('random_complete',rng.choice(eligible).bullets,None)


def ar_scoreable(bullets, vectors):
    return all(b.phrase_id in vectors for b in bullets)


def selection_fits(selection, exact, released, raw_text=None):
    if not ar_scoreable(selection.bullets, exact.vectors):
        return None, 'unavailable_AR_empty_after_cleanup'
    if raw_text is not None:
        return None, 'unavailable_for_unmodified_raw_text'
    return {'exact':exact.fit(selection.phrase_ids).__dict__,
            'released80':released.fit(selection.phrase_ids).__dict__}, 'emitted_bullets'


def prune_parent(source, exact, maximum_loss):
    if not ar_scoreable(source.bullets, exact.vectors):
        return Selection('prune_loo',source.bullets,None,reason='unavailable_parent_AR')
    return prune_leave_one_out(source.bullets,exact.score,maximum_loss=maximum_loss)


def coefficient_parent(source, exact, threshold):
    if not ar_scoreable(source.bullets, exact.vectors):
        return Selection('prune_coefficient',source.bullets,None,reason='unavailable_parent_AR')
    fit=exact.fit(source.phrase_ids); scale=sum(fit.coefficients)
    retained=tuple(b for b,c in zip(source.bullets,fit.coefficients) if c>threshold*scale)
    return Selection('prune_coefficient',retained,None)


def pool_candidates(samples, n, vectors):
    from dataclasses import replace
    bullets=[]; representatives={}
    for sample in samples[:n]:
        if sample.parsing_uncertain:
            continue
        for bullet in sample.bullets:
            if bullet.phrase_id in vectors and bullet.text not in representatives:
                representatives[bullet.text]=bullet; bullets.append(bullet)
    remapped=[]
    for sample in samples[:n]:
        if not sample.parsing_uncertain and ar_scoreable(sample.bullets,vectors):
            mapped=tuple(dict((representatives[b.text].phrase_id,representatives[b.text])
                              for b in sample.bullets).values())
            remapped.append(replace(sample,bullets=mapped))
    return bullets,remapped


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime',default='configs/runtime.json')
    parser.add_argument('--input',action='append',required=True)
    parser.add_argument('--cache-directory',required=True)
    parser.add_argument('--fresh-manifest',required=True)
    parser.add_argument('--whitener-directory',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--max-cells',type=int)
    parser.add_argument('--cell-id',action='append')
    parser.add_argument('--shard-count',type=int,default=1)
    parser.add_argument('--shard-index',type=int,default=0)
    parser.add_argument('--controls-manifest',required=True)
    parser.add_argument('--pilot-manifest',required=True)
    args=parser.parse_args()
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        parser.error('Require 0 <= shard-index < positive shard-count')
    if args.shard_count > 1 and (args.cell_id or args.max_cells):
        parser.error('Sharding requires the complete declared cohort, without cell/max filters')
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Offline selection requires allocated CPU resources')
    torch.set_num_threads(4)
    started=time.time(); runtime=json.loads(Path(args.runtime).read_text())
    tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    counts={}
    def token_count(text):
        if text not in counts:
            counts[text]=len(tok(text,add_special_tokens=False)['input_ids'])
        return counts[text]
    admissible=output_admissible(token_count,256)
    source_inputs=[]; records=defaultdict(dict)
    for input_path in args.input:
        path=Path(input_path); body=path.read_bytes(); sha=hashlib.sha256(body).hexdigest()
        status_path=path.with_suffix('.status.json')
        if not status_path.exists():
            raise ValueError('Require completed shared journal with terminal status')
        status=json.loads(status_path.read_text())
        if status['status']!='complete' or status['journal_sha256']!=sha:
            raise ValueError('Journal is not the committed terminal snapshot')
        source_inputs.append({'path':str(path),'sha256':sha,'terminal_status':status})
        for row in input_records(body):
            cell=row['cell_id']; index=row['sample_index']
            if index in records[cell]:
                raise ValueError('Duplicate cell/sample record')
            records[cell][index]=row
    manifest_bytes=Path(args.fresh_manifest).read_bytes()
    manifest=json.loads(manifest_bytes); cells={c['cell_id']:c for c in manifest['cells']}
    target_ids=sorted(args.cell_id) if args.cell_id else sorted(records)
    if not set(target_ids).issubset(records):
        raise ValueError('Requested comparison cell has no shared-pool records')
    if args.max_cells:
        target_ids=target_ids[:args.max_cells]
    for cell_id in target_ids:
        if cells[cell_id]['split']!='development' or set(records[cell_id])!=set(range(32)):
            raise ValueError('Require complete32-sample DEVELOPMENT cells')
    cache=RawVectorCache(args.cache_directory)
    usage={}
    for path in sorted(Path(args.cache_directory).glob('usage_*.jsonl')):
        for line in path.read_text().splitlines():
            row=json.loads(line)
            key=(row['cell_id'],row['sample_index'],row['source_phrase_id'])
            if key in usage and usage[key]!=row:
                raise ValueError('Conflicting AR usage provenance')
            usage[key]=row
    tensor_paths={c['activation_tensor_path'] for c in cells.values()}
    if len(tensor_paths)!=1:
        raise ValueError('This pilot runner expects the single completed fresh tensor')
    activations=load_file(next(iter(tensor_paths)))['resid']
    whiteners={}; vectors_by_layer={}; target_by_layer={}
    controls_bytes=Path(args.controls_manifest).read_bytes()
    controls_manifest=json.loads(controls_bytes)
    pilot_bytes=Path(args.pilot_manifest).read_bytes()
    pilot=json.loads(pilot_bytes)
    pilot_ids={c['cell_id'] for c in pilot['cells']}
    if not set(target_ids).issubset(pilot_ids) or (not args.cell_id and not args.max_cells and set(target_ids)!=pilot_ids):
        raise ValueError('Comparison cell set differs from frozen pilot')
    full_target_count = len(target_ids)
    target_ids = target_ids[args.shard_index::args.shard_count]
    if not target_ids:
        raise ValueError('Empty selection shard')
    scope = ('partial-grid development cell diagnostics' if pilot.get('partial_grid', False)
             else 'full-grid development cell selections; item aggregation pending')
    bank={cell_id:controls_manifest['control_cell_ids_by_target'][cell_id] for cell_id in target_ids}
    for cell_id,control_ids in bank.items():
        own=cells[cell_id]
        for control_id in control_ids:
            other=cells[control_id]
            if other['split']!='development' or other['group_id']==own['group_id']:
                raise ValueError('Frozen E1 control violates split/group exclusion')
            ref=controls_manifest['control_bank'][control_id]
            if any(ref[k]!=own[k] for k in ('family','layer')):
                raise ValueError('Frozen control has unmatched family/layer')
    config={'schema_version':2,'primary_solver':'scipy_exact','compatibility_solver':'released80',
            'empty_AR_policy':'Invalid cleaned atoms excluded from AR complete selection/pooling; text baselines unchanged; unscoreable N1 pruning is explicit no-op',
            'prefixes':[1,2,4,8,16,32],'max_bullets':4,'max_output_qwen_tokens':256,
            'parser':'source_contiguous_dash_blocks_v1','loo_maximum_losses':[0.,.001,.005],
            'coefficient_relative_thresholds':[.01,.05],'pool_prefixes':[16,32],'swap_passes':1,
            'E1_requested_control_count':controls_manifest['requested_controls_per_cell'],'E1_beta':1.,'E1_primary':'mean',
            'E1_ablation':'max','controls':bank,'cell_ids':target_ids,
            'source_inputs':source_inputs,'fresh_manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
            'vector_contract':cache.contract,'split':'development',
            'controls_manifest_sha256':hashlib.sha256(controls_bytes).hexdigest(),
            'controls_multiplicity':'Frozen bank may include multiple cells from another group; never own related group',
            'pilot_manifest_sha256':hashlib.sha256(pilot_bytes).hexdigest(),
            'shard_index':args.shard_index,'shard_count':args.shard_count,
            'full_cohort_cell_count':full_target_count,
            'code_sha256':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in
                [Path(__file__),Path('src/olens_improve/selection.py'),Path('src/olens_improve/reconstruction.py'),Path('src/olens_improve/contrastive.py')]} ,'scope':scope}
    output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    config_path=output/'config.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:
        raise ValueError('Cannot resume different comparison configuration')
    atomic_json(config_path,config)
    completed=set(); result_path=output/'selections.jsonl'
    if result_path.exists():
        for line in result_path.read_text().splitlines():
            event=json.loads(line)
            if event['cell_id'] in completed or event['config_sha256']!=digest(config):
                raise ValueError('Duplicate completed cell or incompatible resumed event')
            completed.add(event['cell_id'])
    with result_path.open('a') as stream:
        for cell_id in target_ids:
            if cell_id in completed:
                continue
            cell=cells[cell_id]; layer=cell['layer']; rows=records[cell_id]
            if layer not in whiteners:
                whitener=Whitener.load(str(Path(args.whitener_directory)/f'whitening_iolens_pooled_L{layer}.safetensors'))
                whiteners[layer]=whitener; vectors_by_layer[layer]={}
                target_by_layer[layer]={}
            whitener=whiteners[layer]; whitened_vectors=vectors_by_layer[layer]
            targets=target_by_layer[layer]
            for target_id in [cell_id,*bank[cell_id]]:
                if target_id not in targets:
                    original=activations[cells[target_id]['activation_row']]
                    sha=hashlib.sha256(original.numpy().tobytes()).hexdigest()
                    if sha!=cells[target_id]['activation_sha256']:
                        raise ValueError('Fresh activation hash mismatch')
                    targets[target_id]=whitener.whiten(original.reshape(1,-1))[0]
            samples=[]; provenance={}; needed={}; invalid_by_sample={}
            for index in range(32):
                row=rows[index]
                if row['activation_sha256']!=cell['activation_sha256']:
                    raise ValueError('Generated pool target differs from fresh activation')
                pool=row.get('global_pool_id',row['pool_id'])
                sample_id=f'{pool}:{cell_id}:{index}'
                sample=parse_bullets(row['text'],sample_id,index,token_count=token_count,max_output_tokens=256)
                samples.append(sample)
                for bullet in sample.bullets:
                    info=usage[(cell_id,index,bullet.phrase_id)]
                    if info['text']!=bullet.text or info['activation_sha256']!=cell['activation_sha256']:
                        raise ValueError('AR text/target provenance differs')
                    provenance[bullet.phrase_id]=info
                    if info['cache_key'] is None:
                        if info.get('status')!='empty_after_cleanup':
                            raise ValueError('Missing AR key without explicit empty-cleanup status')
                        invalid_by_sample.setdefault(index,[]).append(info)
                        continue
                    needed[bullet.phrase_id]=info['cache_key']
            missing=sorted(set(needed.values())-whitened_vectors.keys())
            if missing:
                raw=torch.stack([cache.get(key) for key in missing])
                transformed=whitener.whiten(raw)
                transformed=transformed/(transformed.norm(dim=1,keepdim=True)+1e-9)
                whitened_vectors.update(zip(missing,transformed))
            phrase_vectors={phrase_id:whitened_vectors[key] for phrase_id,key in needed.items()}
            meta={'cell_id':cell_id,'whitener_sha256':whitener.artifact_sha256,
                  'vector_contract_sha256':cache.contract['sha256'],'control_ids':bank[cell_id]}
            exact=JointNNLS(targets[cell_id],phrase_vectors,metadata=meta)
            released=JointNNLS(targets[cell_id],phrase_vectors,solver='released80',metadata=meta)
            scoreable_admissible=lambda bullets: admissible(bullets) and ar_scoreable(bullets,phrase_vectors)
            results=[]
            def save(method,n,selection,raw_text=None,extra=None):
                text=selection.text if raw_text is None else raw_text
                ids=selection.phrase_ids
                fits,fit_scope=selection_fits(selection,exact,released,raw_text)
                if raw_text is None and not admissible(selection.bullets):
                    raise ValueError('Output violates final cap')
                results.append({'method':method,'n':n,'text':text,'phrase_ids':list(ids),
                    'token_count':token_count(text),'bullet_count':len(ids),'reason':selection.reason,
                    'fits':fits,'fits_scope':fit_scope,'scored_text':selection.text if fits is not None else None,'trace':list(selection.trace),'atoms':[provenance[k] for k in ids],
                    'extra':extra or {}})
            save('raw_n1',1,Selection('raw_n1',samples[0].bullets,None),rows[0]['text'],
                 {'raw_baseline_exempt_from_output_cap':True,'parser_flags':list(samples[0].flags)})
            save('capped_n1',1,Selection('capped_n1',samples[0].bullets,None))
            for n in config['prefixes']:
                best=best_of_n(samples,n,exact.score,admissible=scoreable_admissible)
                save('best_n_exact',n,best)
                compat=best_of_n(samples,n,released.score,admissible=scoreable_admissible)
                save('best_n_released80',n,compat)
                rng=random.Random(int(digest(['random_complete_v1',cell_id,n])[:16],16))
                save('random_complete',n,random_complete_selection(samples,n,admissible,rng))
            best=best_of_n(samples,32,exact.score,admissible=scoreable_admissible)
            for source_name,source in [('a32',best),('n1',Selection('capped_n1',samples[0].bullets,None))]:
                for loss in config['loo_maximum_losses']:
                    pruned=prune_parent(source,exact,loss)
                    save(f'prune_loo_{source_name}_{loss:g}',32 if source_name=='a32' else 1,pruned)
                    rng=random.Random(int(digest(['random_delete_v1',cell_id,source_name,loss])[:16],16))
                    chosen=set(rng.sample(range(len(source.bullets)),len(pruned.bullets)))
                    save(f'random_delete_matched_{source_name}_{loss:g}',32 if source_name=='a32' else 1,
                         Selection('random_delete',tuple(b for i,b in enumerate(source.bullets) if i in chosen),None,
                                   reason='unavailable_parent_AR' if pruned.reason=='unavailable_parent_AR' else 'selected'))
                for threshold in config['coefficient_relative_thresholds']:
                    save(f'prune_coefficient_{source_name}_{threshold:g}',32 if source_name=='a32' else 1,
                         coefficient_parent(source,exact,threshold))
            for n in config['pool_prefixes']:
                # Exact text dedup only; original source IDs remain provenance representatives.
                bullets,remapped=pool_candidates(samples,n,phrase_vectors)
                pooled=greedy_pool(bullets,exact.score,admissible=admissible,swap_passes=1,
                                   complete_samples=remapped)
                save('pooled_greedy_swap',n,pooled)
            controls={control:JointNNLS(targets[control],phrase_vectors,metadata=meta|{'cell_id':control,'selector_target_cell_id':cell_id}) for control in bank[cell_id]}
            if controls:
                for aggregation in ('mean','max'):
                    def objective(ids,aggregation=aggregation):
                        return control_specificity(exact.score(ids),{key:value.score(ids) for key,value in controls.items()},aggregation=aggregation)['score']
                    chosen=best_of_n(samples,32,objective,admissible=scoreable_admissible)
                    diagnostics=control_specificity(exact.score(chosen.phrase_ids),
                        {key:value.score(chosen.phrase_ids) for key,value in controls.items()},aggregation=aggregation)
                    save(f'best_n_specificity_{aggregation}',32,chosen,extra=diagnostics)
            event={'cell_id':cell_id,'family':cell['family'],'item_id':cell['item_id'],
                'layer':layer,'position':cell['position'],'split':'development','global_pool_id':pool,
                'activation_sha256':cell['activation_sha256'],'config_sha256':digest(config),
                'parser_flags_by_sample':{s.index:list(s.flags) for s in samples},
                'invalid_AR_atoms_by_sample':invalid_by_sample,
                'selections':results,'seconds_since_start':time.time()-started}
            stream.write(json.dumps(event)+'\n'); stream.flush(); os.fsync(stream.fileno())
            completed.add(cell_id)
            atomic_json(output/'status.json',{'status':'running','completed_cells':len(completed),
                        'expected_cells':len(target_ids),'seconds':time.time()-started})
            print(json.dumps({'completed_cells':len(completed),'expected_cells':len(target_ids)}),flush=True)
    atomic_json(output/'status.json',{'status':'complete','completed_cells':len(completed),
                'expected_cells':len(target_ids),'seconds':time.time()-started,
                'quality_status':'unjudged','scope':scope,
                'shard_index':args.shard_index,'shard_count':args.shard_count,
                'full_cohort_cell_count':full_target_count})


if __name__=='__main__':
    main()
