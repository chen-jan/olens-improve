"""Evidence-backed isolated E2 DEV diagnostic; labels never enter inference policy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file,save_file
from olens_improve.ar_cache import digest
from olens_improve.contrastive import two_by_two
from olens_improve.reconstruction import FrozenAR,JointNNLS,Whitener


def atomic(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)


def main():
    p=argparse.ArgumentParser()
    for key in ('diagnostic-manifest','fresh-manifest','checkpoint','whitener-directory','output'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--runtime',default='configs/runtime.json');args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use assigned GPU')
    torch.set_num_threads(4);started=time.time();runtime=json.loads(Path(args.runtime).read_text())
    raw=Path(args.diagnostic_manifest).read_bytes();manifest=json.loads(raw)
    cells={c['cell_id']:c for c in json.loads(Path(args.fresh_manifest).read_text())['cells']}
    specs=manifest['sets'];keys={};targets=set()
    for spec in specs:
        a,b=spec['a_cell_id'],spec['b_cell_id'];targets.update([a,b])
        if any(cells[k]['split']!='development' for k in (a,b)) or cells[a]['layer']!=cells[b]['layer']:
            raise ValueError('Diagnostic must use same-layer DEV cells')
        for field in ('a_phrase','b_phrase','generic_phrase'):
            phrase=spec[field];keys.setdefault((phrase,cells[a]['layer']),len(keys))
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    spec_record={'diagnostic_manifest_sha256':hashlib.sha256(raw).hexdigest(),'sets':len(specs),
                 'unique_raw_inputs':len(keys),'cell_ids':sorted(targets),'access_boundary':'Isolated gold-backed diagnostic only',
                 'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path('src/olens_improve/reconstruction.py')]}}
    atomic(output/'spec.json',spec_record)
    ar=FrozenAR.load(runtime['paths']['base_snapshot'],args.checkpoint)
    raw_vectors=[];encoding=[];ordered=list(keys)
    for start in range(0,len(ordered),32):
        batch=ordered[start:start+32];vectors,meta=ar.encode_mixed([t for t,l in batch],[l for t,l in batch])
        if any(r['truncated'] for r in meta):raise ValueError('Controlled description exceeds source AR span')
        raw_vectors.extend(vectors);encoding.extend(meta)
    save_file({'vectors':torch.stack(raw_vectors)},str(output/'raw_predictions.safetensors'))
    atomic(output/'raw_predictions.index.json',{'encoding':encoding,'rows':[{ 'text':t,'layer':l,'row':keys[t,l]} for t,l in ordered]})
    tensor_paths={cells[k]['activation_tensor_path'] for k in targets}
    if len(tensor_paths)!=1:raise ValueError('Expect completed single fresh tensor')
    target_vectors=load_file(next(iter(tensor_paths)))['resid'];whiteners={};results=[]
    for spec in specs:
        layer=cells[spec['a_cell_id']]['layer']
        if layer not in whiteners:whiteners[layer]=Whitener.load(str(Path(args.whitener_directory)/f'whitening_iolens_pooled_L{layer}.safetensors'))
        dictionary={name:raw_vectors[keys[spec[field],layer]] for name,field in [('a','a_phrase'),('b','b_phrase'),('generic','generic_phrase')]}
        scores_by_solver={}
        for solver in ('scipy_exact','released80'):
            matrix=[];generic=[];coefficients=[]
            for target_id in (spec['a_cell_id'],spec['b_cell_id']):
                cell=cells[target_id];target=target_vectors[cell['activation_row']]
                if hashlib.sha256(target.numpy().tobytes()).hexdigest()!=cell['activation_sha256']:raise ValueError('Target hash mismatch')
                scorer=JointNNLS.from_raw(target,dictionary,whiteners[layer],solver=solver)
                fits=[scorer.fit([key]) for key in ('a','b','generic')]
                matrix.append([f.fve for f in fits[:2]]);generic.append(fits[2].fve);coefficients.append([f.coefficients for f in fits])
            scores_by_solver[solver]=two_by_two(matrix,generic)|{'coefficients':coefficients}
        results.append(spec|{'layer':layer,'solvers':scores_by_solver,'whitener_sha256':whiteners[layer].artifact_sha256})
        atomic(output/'results.json',{'status':'running','spec':spec_record,'results':results,'negation':manifest['negation']})
    atomic(output/'results.json',{'status':'complete','spec':spec_record,'results':results,'negation':manifest['negation'],
                                 'seconds':time.time()-started,'independence_caveat':'Repeated layers and wording variants of the same pair are not independent items'})
    print(json.dumps({'status':'complete','sets':len(results),'seconds':time.time()-started}),flush=True)


if __name__=='__main__':main()
