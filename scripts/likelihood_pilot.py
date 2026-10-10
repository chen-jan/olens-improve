"""E3 same-pool DEV likelihood selection with fixed first-two matched controls."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file
from olens_improve.ar_cache import digest, input_records
from olens_improve.contrastive import teacher_forced_likelihood, teacher_forced_likelihood_batch
from olens_improve.models import FrozenOLens, BASE_REVISION, PAIR_REVISION
from olens_improve.selection import parse_bullets, render_bullets


def atomic(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp'); temporary.write_text(json.dumps(value,indent=2)+'\n')
    os.replace(temporary,path)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runtime',default='configs/runtime.json')
    p.add_argument('--input',required=True)
    p.add_argument('--cells-manifest',required=True)
    p.add_argument('--fresh-manifest',required=True)
    p.add_argument('--controls-manifest',required=True)
    p.add_argument('--selectors',required=True)
    p.add_argument('--adapter',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--batch-size',type=int,default=8)
    args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or args.batch_size<1: raise RuntimeError('Use allocated GPU')
    torch.set_num_threads(4); started=time.time()
    runtime=json.loads(Path(args.runtime).read_text())
    body=Path(args.input).read_bytes(); rows=defaultdict(dict)
    for row in input_records(body):
        if row['sample_index'] in rows[row['cell_id']]:
            raise ValueError('Duplicate candidate input sample')
        rows[row['cell_id']][row['sample_index']]=row
    manifest_bytes=Path(args.cells_manifest).read_bytes()
    requested=sorted(c['cell_id'] for c in json.loads(manifest_bytes)['cells'])
    fresh_bytes=Path(args.fresh_manifest).read_bytes()
    fresh={c['cell_id']:c for c in json.loads(fresh_bytes)['cells']}
    controls_bytes=Path(args.controls_manifest).read_bytes()
    control_manifest=json.loads(controls_bytes)
    bank={key:control_manifest['control_cell_ids_by_target'][key][:2] for key in requested}
    for cell_id in requested:
        if fresh[cell_id]['split']!='development' or set(rows[cell_id])!=set(range(32)) or len(bank[cell_id])!=2:
            raise ValueError('Require completedDEV32samplepool and2frozencontrols')
        for key in bank[cell_id]:
            if fresh[key]['split']!='development' or fresh[key]['group_id']==fresh[cell_id]['group_id'] or fresh[key]['layer']!=fresh[cell_id]['layer']:
                raise ValueError('Control bank boundary failed')
    a8={r['cell_id']:next(s for s in r['selections'] if s['method']=='best_n_exact' and s['n']==8)
        for r in [json.loads(line) for line in Path(args.selectors).read_text().splitlines()]}
    spec={'method':'likelihood_true_minus_mean_two_controls','n':8,'normalization':'mean_candidate_token_logprob',
          'include_eos':False,'controls':bank,'cell_ids':requested,'input_sha256':hashlib.sha256(body).hexdigest(),
          'cells_manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
          'fresh_manifest_sha256':hashlib.sha256(fresh_bytes).hexdigest(),
          'base_revision':BASE_REVISION,'adapter_revision':PAIR_REVISION,
          'adapter_sha256':hashlib.sha256((Path(args.adapter)/'adapter_model.safetensors').read_bytes()).hexdigest(),
          'carrier':'concepts_raw','injection_norm':16000,'dtype':'bfloat16',
          'controls_manifest_sha256':hashlib.sha256(controls_bytes).hexdigest(),
          'selector_sha256':hashlib.sha256(Path(args.selectors).read_bytes()).hexdigest(),
          'source_sha256':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in [Path(__file__),Path('src/olens_improve/contrastive.py'),Path('src/olens_improve/models.py')]},
          'batch_size':args.batch_size,'scope':'partial-grid development cell pilot'}
    output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    if (output/'spec.json').exists() and json.loads((output/'spec.json').read_text())!=spec:
        raise ValueError('Cannot resume different E3 configuration')
    atomic(output/'spec.json',spec)
    complete={}
    result_path=output/'readouts.jsonl'
    if result_path.exists():
        for line in result_path.read_text().splitlines():
            row=json.loads(line)
            if row['cell_id'] in complete or row['spec_sha256']!=digest(spec): raise ValueError('Duplicate or incompatible completed E3 cell')
            complete[row['cell_id']]=row
    tensor_paths={fresh[k]['activation_tensor_path'] for k in requested}
    if len(tensor_paths)!=1: raise ValueError('Expected one fresh tensor')
    tensor=load_file(next(iter(tensor_paths)))['resid']
    lens=FrozenOLens.load(runtime['paths']['base_snapshot'],args.adapter)
    lens.merge()
    count=lambda text:len(lens.tokenizer(text,add_special_tokens=False)['input_ids'])
    def activation(key):
        cell=fresh[key]; vector=tensor[cell['activation_row']]
        if hashlib.sha256(vector.numpy().tobytes()).hexdigest()!=cell['activation_sha256']: raise ValueError('Activation hash mismatch')
        return vector
    def candidates(cell_id):
        output=[]
        for index in range(8):
            row=rows[cell_id][index]
            if row['activation_sha256']!=fresh[cell_id]['activation_sha256']: raise ValueError('Pool activation differs')
            sample_id=f"{row.get('global_pool_id',row['pool_id'])}:{cell_id}:{index}"
            sample=parse_bullets(row['text'],sample_id,index,token_count=count,max_output_tokens=256)
            output.append((sample,render_bullets(sample.bullets)))
        return output
    first=requested[0]; fixture_candidates=[text for sample,text in candidates(first) if not sample.parsing_uncertain][:2]
    if len(fixture_candidates)!=2: raise ValueError('Need two valid fixture candidates')
    fixture_texts=[fixture_candidates[0],fixture_candidates[1],fixture_candidates[0]]
    fixture_ids=[first,first,bank[first][0]]; layer=fresh[first]['layer']
    batched=teacher_forced_likelihood_batch(lens,[activation(k) for k in fixture_ids],layer,fixture_texts)
    single=[teacher_forced_likelihood(lens,activation(k),layer,text) for k,text in zip(fixture_ids,fixture_texts)]
    deltas=[abs(b['average_log_likelihood']-s['average_log_likelihood']) for b,s in zip(batched,single)]
    atomic(output/'batch_fixture.json',{'cell_ids':fixture_ids,'texts':fixture_texts,'layer':layer,
        'average_log_likelihood_absolute_deltas':deltas,'batched':batched,'singleton':single,
        'provisional_guard_nats_per_token':.05,'causal_alignment_tests':'tests/test_likelihood_alignment.py'})
    if max(deltas)>.05: raise RuntimeError('Batch/singleton likelihood discrepancy exceeds provisional guard')
    measured_start=time.time()
    with result_path.open('a') as stream:
        for cell_id in requested:
            if cell_id in complete: continue
            layer=fresh[cell_id]['layer']; prepared=candidates(cell_id)
            work=[]
            for sample,text in prepared:
                if sample.parsing_uncertain or not text: continue
                for key in [cell_id,*bank[cell_id]]: work.append((sample.index,text,key))
            conditions=defaultdict(dict)
            for start in range(0,len(work),args.batch_size):
                chunk=work[start:start+args.batch_size]
                predictions=teacher_forced_likelihood_batch(lens,[activation(k) for _,_,k in chunk],layer,[text for _,text,_ in chunk])
                for (index,text,key),prediction in zip(chunk,predictions): conditions[index][key]=prediction
            scored=[]
            for sample,text in prepared:
                if sample.index not in conditions: continue
                values=conditions[sample.index]; true=values[cell_id]
                mean=sum(values[k]['average_log_likelihood'] for k in bank[cell_id])/2
                total=sum(values[k]['sum_log_likelihood'] for k in bank[cell_id])/2
                scored.append({'sample_index':sample.index,'text':text,'phrase_ids':[b.phrase_id for b in sample.bullets],
                    'score':true['average_log_likelihood']-mean,'total_difference':true['sum_log_likelihood']-total,
                    'token_count':true['candidate_token_count'],'own_mean_log_likelihood':true['average_log_likelihood'],
                    'control_mean_log_likelihood':mean,'conditions':values,'parser_flags':list(sample.flags)})
            winner=max(scored,key=lambda row:(row['score'],-row['sample_index'])) if scored else None
            baselines={}
            for key in ('own_mean_log_likelihood','control_mean_log_likelihood'):
                baseline=max(scored,key=lambda row:(row[key],-row['sample_index'])) if scored else None
                baselines[key]={'text':baseline['text'] if baseline else '',
                                'sample_index':baseline['sample_index'] if baseline else None,
                                'score':baseline[key] if baseline else None}
            event={'cell_id':cell_id,'family':fresh[cell_id]['family'],'item_id':fresh[cell_id]['item_id'],
                   'layer':layer,'position':fresh[cell_id]['position'],'split':'development','method':'likelihood_true_minus_mean_two_controls',
                   'n':8,'text':winner['text'] if winner else '', 'selected_sample_index':winner['sample_index'] if winner else None,
                   'reason':'selected' if winner else 'no_eligible_complete_candidate',
                   'candidates':scored,'likelihood_baselines':baselines,'a8_comparator':a8[cell_id],'spec_sha256':digest(spec),
                   'controls':bank[cell_id],'seconds_since_start':time.time()-started}
            stream.write(json.dumps(event)+'\n');stream.flush();os.fsync(stream.fileno());complete[cell_id]=event
            atomic(output/'status.json',{'status':'running','completed_cells':len(complete),'expected_cells':len(requested),
                                        'scoring_seconds':time.time()-measured_start})
            print(json.dumps({'completed_cells':len(complete),'expected_cells':len(requested)}),flush=True)
    atomic(output/'status.json',{'status':'complete','completed_cells':len(complete),'expected_cells':len(requested),
           'total_seconds':time.time()-started,'scoring_seconds':time.time()-measured_start,'quality_status':'unjudged'})


if __name__=='__main__': main()
