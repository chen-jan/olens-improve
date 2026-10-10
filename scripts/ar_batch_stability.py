"""Predeclared four-family DEV numerical batching audit; never replace production vectors."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file, save_file
from scipy.stats import spearmanr
from olens_improve.ar_cache import digest, input_records
from olens_improve.reconstruction import FrozenAR, JointNNLS, RawVectorCache, Whitener
from olens_improve.selection import parse_bullets, best_of_n, output_admissible


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runtime',default='configs/runtime.json')
    p.add_argument('--input',required=True)
    p.add_argument('--cache-directory',required=True)
    p.add_argument('--fresh-manifest',required=True)
    p.add_argument('--checkpoint',required=True)
    p.add_argument('--whitener-directory',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'): raise RuntimeError('Use assigned GPU')
    torch.set_num_threads(4); started=time.time()
    runtime=json.loads(Path(args.runtime).read_text())
    cells={c['cell_id']:c for c in json.loads(Path(args.fresh_manifest).read_text())['cells']}
    body=Path(args.input).read_bytes(); records={}
    for row in input_records(body): records.setdefault(row['cell_id'],{})[row['sample_index']]=row
    selected=[]
    for family in sorted({cells[k]['family'] for k in records}):
        eligible=sorted(k for k in records if cells[k]['family']==family and cells[k]['layer']==44)
        if not eligible: raise ValueError('No layer44 representative in family')
        selected.append(eligible[0])
    if any(cells[k]['split']!='development' for k in selected): raise ValueError('DEV only')
    output=Path(args.output); output.mkdir(parents=True,exist_ok=False)
    spec={'cell_ids':selected,'selection_rule':'lexicographically first L44 cell per family, before scoring',
          'prefix_n':16,'comparison':'immutable cached B32 vs re-encoding in B8; B1 for cached selected set',
          'input_sha256':hashlib.sha256(body).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output/'spec.json').write_text(json.dumps(spec,indent=2)+'\n')
    cache=RawVectorCache(args.cache_directory); usages={}
    for path in Path(args.cache_directory).glob('usage_*.jsonl'):
        for line in path.read_text().splitlines():
            row=json.loads(line); usages[row['source_phrase_id']]=row
    ar=FrozenAR.load(runtime['paths']['base_snapshot'],args.checkpoint)
    count=lambda text:len(ar.tokenizer(text,add_special_tokens=False)['input_ids'])
    admissible=output_admissible(count,256)
    whitener=Whitener.load(str(Path(args.whitener_directory)/'whitening_iolens_pooled_L44.safetensors'))
    tensor=load_file(cells[selected[0]]['activation_tensor_path'])['resid']
    results=[]
    for cell_id in selected:
        cell=cells[cell_id]; samples=[]; texts={}; keys={}
        for index in range(16):
            row=records[cell_id][index]; sample_id=f"{row.get('global_pool_id',row['pool_id'])}:{cell_id}:{index}"
            sample=parse_bullets(row['text'],sample_id,index,token_count=count)
            samples.append(sample)
            for atom in sample.bullets:
                info=usages[atom.phrase_id]
                if info['text']!=atom.text: raise ValueError('Scorer span changed')
                texts[atom.phrase_id]=atom.text; keys[atom.phrase_id]=info['cache_key']
        ids=list(texts); reencoded=[]; encoding=[]
        for start in range(0,len(ids),8):
            batch=ids[start:start+8]; vectors,meta=ar.encode([texts[k] for k in batch],44)
            reencoded.extend(vectors); encoding.extend(meta)
        b8=dict(zip(ids,reencoded)); b32={k:cache.get(keys[k]) for k in ids}
        target=tensor[cell['activation_row']]
        main=JointNNLS.from_raw(target,b32,whitener)
        alternative=JointNNLS.from_raw(target,b8,whitener)
        eligible=[s for s in samples if not s.parsing_uncertain and admissible(s.bullets)]
        scores32=[main.score(tuple(b.phrase_id for b in s.bullets)) for s in eligible]
        scores8=[alternative.score(tuple(b.phrase_id for b in s.bullets)) for s in eligible]
        winner32=best_of_n(samples,16,main.score,admissible=admissible)
        winner8=best_of_n(samples,16,alternative.score,admissible=admissible)
        selected_ids=list(winner32.phrase_ids)
        singletons={k:ar.encode([texts[k]],44)[0][0] for k in selected_ids}
        singleton=JointNNLS.from_raw(target,singletons,whitener)
        singleton_fve=singleton.score(selected_ids)
        delta=torch.tensor(scores8)-torch.tensor(scores32)
        ordered=sorted(scores32,reverse=True)
        correlation=float(spearmanr(scores32,scores8).statistic) if len(scores32)>1 else None
        if correlation is not None and not __import__('math').isfinite(correlation): correlation=None
        rel=[float((b8[k]-b32[k]).norm()/b32[k].norm().clamp_min(1e-12)) for k in ids]
        result={'cell_id':cell_id,'family':cell['family'],'layer':44,'eligible_complete_candidates':len(eligible),
                'sample_indices':[s.index for s in eligible],'fve_cached_b32':scores32,'fve_reencoded_b8':scores8,
                'maximum_absolute_fve_delta':float(delta.abs().max()) if len(delta) else None,
                'median_absolute_fve_delta':float(delta.abs().median()) if len(delta) else None,
                'spearman_rank_correlation':correlation,'winner_changed':winner32.phrase_ids!=winner8.phrase_ids,
                'winner32_ids':selected_ids,'winner8_ids':list(winner8.phrase_ids),
                'cached_top_two_gap':ordered[0]-ordered[1] if len(ordered)>1 else None,
                'cached_score_of_b8_winner':main.score(winner8.phrase_ids),
                'singleton_selected_fve':singleton_fve,'cached_selected_fve':main.score(selected_ids),
                'raw_prediction_relative_l2_max':max(rel) if rel else None,
                'raw_prediction_relative_l2_median':float(torch.tensor(rel).median()) if rel else None,
                'encoding':encoding,'phrase_ids':ids,'texts':[texts[k] for k in ids],
                'interpretation':'Numerical scorer stability; not semantic validity or a new sample pool'}
        results.append(result)
        save_file({'b8':torch.stack([b8[k] for k in ids]),'cached_b32':torch.stack([b32[k] for k in ids]),
                   'selected_singletons':torch.stack(list(singletons.values())) if singletons else torch.empty(0,5120)},
                  str(output/f"{digest(cell_id)[:16]}.safetensors"))
        (output/'results.json').write_text(json.dumps({'spec':spec,'results':results,'status':'running'},indent=2)+'\n')
        print(json.dumps({k:result[k] for k in ('family','maximum_absolute_fve_delta','winner_changed','cached_top_two_gap')}),flush=True)
    (output/'results.json').write_text(json.dumps({'spec':spec,'results':results,'status':'complete','seconds':time.time()-started,
                                                 'vector_contract':cache.contract,'whitener_sha256':whitener.artifact_sha256},indent=2)+'\n')


if __name__=='__main__': main()
