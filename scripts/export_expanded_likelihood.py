"""Publish complete likelihood families from committed resumable GPU cells."""
from collections import defaultdict
import argparse
import hashlib
import json
import os
from pathlib import Path

from expanded_cpu_cached import atomic, sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--inventory-sha256',required=True);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU resources required')
    if sha(a.inventory)!=a.inventory_sha256:raise ValueError('Inventory differs')
    from transformers import AutoTokenizer
    inventory=json.loads(a.inventory.read_text());fresh_path=Path(inventory['fresh_manifest']['path'])
    if sha(fresh_path)!=inventory['fresh_manifest']['sha256']:raise ValueError('Fresh source changed')
    cells={c['cell_id']:c for c in json.loads(fresh_path.read_text())['cells']}
    runtime=json.loads(Path('configs/runtime.json').read_text());tok=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda text:len(tok(text,add_special_tokens=False)['input_ids'])
    methods=('likelihood_true_minus_mean_two_controls','own_mean_log_likelihood','control_mean_log_likelihood')
    conditions=[{'method':method,'n':8} for method in methods];rows=defaultdict(dict);committed_hash=hashlib.sha256();partial_tail=False
    with a.input.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):partial_tail=True;break
            committed_hash.update(line);row=json.loads(line);cid=row['cell_id'];cell=cells[cid]
            if cid in rows[row['family']] or any(row[k]!=cell[k] for k in ('family','item_id','layer','position','split','activation_sha256')):raise ValueError('Likelihood cell differs')
            if row['n']!=8 or row['method']!=methods[0]:raise ValueError('Changed likelihood contract')
            candidates={c['sample_index']:c for c in row['candidates']}
            if len(candidates)!=len(row['candidates']) or any(not isinstance(index,int) or not 0<=index<8 for index in candidates):raise ValueError('Invalid candidate identities')
            choices=[{'method':methods[0],'n':8,'text':row['text'],'sample_index':row['selected_sample_index']}]
            choices.extend({'method':method,'n':8,**row['likelihood_baselines'][method]} for method in methods[1:])
            for choice in choices:
                index=choice['sample_index'];text=choice['text']
                if index is None:
                    if text!='' or candidates:raise ValueError('Abstention differs from absent eligible candidate contract')
                    bullet_count=0
                else:
                    if index not in candidates or candidates[index]['text']!=text:raise ValueError('Saved candidate text changed')
                    bullet_count=len(candidates[index]['phrase_ids'])
                tokens=count(text)
                if tokens>256 or bullet_count>4:raise ValueError('Likelihood output violates cap')
                choice.update({'token_count':tokens,'bullet_count':bullet_count,'reason':'selected' if index is not None else 'no_eligible_complete_candidate'})
            out={k:row[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')}
            out.update({'selections':choices,'inventory_sha256':a.inventory_sha256,'likelihood_spec_sha256':row['spec_sha256']})
            rows[row['family']][cid]=out
    a.output.mkdir(parents=True,exist_ok=True);ready=[];incomplete={}
    for family in inventory['families']:
        expected={cid for cid,c in cells.items() if c['family']==family}
        if set(rows[family])!=expected:
            incomplete[family]={'committed_cells':len(rows[family]),'expected_cells':len(expected)};continue
        path=a.output/f'{family}.jsonl';temp=path.with_suffix('.jsonl.tmp')
        temp.write_text(''.join(json.dumps(rows[family][cid],ensure_ascii=False)+'\n' for cid in sorted(expected)))
        if path.exists():
            if sha(path)!=sha(temp):raise ValueError('Published immutable family would change')
            temp.unlink()
        else:os.replace(temp,path);path.chmod(0o444)
        own=[{k:cells[cid][k] for k in ('cell_id','family','item_id','layer','position','split','group_id','activation_sha256')} for cid in sorted(expected)]
        manifest=a.output/f'{family}.manifest.json';payload={'schema_version':1,'split':'expansion','scope':inventory['scope'],'cells':own,'inventory_sha256':a.inventory_sha256}
        if manifest.exists() and json.loads(manifest.read_text())!=payload:raise ValueError('Family manifest changed')
        if not manifest.exists():atomic(manifest,payload)
        descriptor={'ready':True,'family':family,'manifest':str(manifest),'manifest_sha256':sha(manifest),'selections':str(path),
            'selection_sha256':sha(path),'conditions':conditions,'inventory_sha256':a.inventory_sha256,
            'source_committed_prefix_sha256':committed_hash.hexdigest(),'source_path':str(a.input),'partial_tail_ignored':partial_tail,
            'cells':len(expected),'items':len({cells[cid]['item_id'] for cid in expected})}
        descriptor_path=a.output/f'{family}.ready.json'
        if not descriptor_path.exists():atomic(descriptor_path,descriptor)
        ready.append(family)
    atomic(a.output/'status.json',{'status':'complete' if not incomplete else 'partial_complete_families',
        'ready_families':ready,'incomplete_families':incomplete,'committed_prefix_sha256':committed_hash.hexdigest()})
    print(json.dumps({'ready_families':ready,'incomplete_families':incomplete}),flush=True)

if __name__=='__main__':main()
