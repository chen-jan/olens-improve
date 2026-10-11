"""Exact cached expansion projection, with zero-Q and parent controls.

Reads historical selector journals as streams; no model/API calls. Complete
four-family outputs become immutable only after all original grids are checked.
"""
from collections import Counter
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def atomic(path,payload):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(payload,indent=2)+'\n');os.replace(temp,path)

def committed_lines(path):
    with Path(path).open() as stream:
        for line in stream:
            if not line.endswith('\n'): raise ValueError('Uncommitted source tail')
            yield json.loads(line)

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--inventory-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU resources required')
    if sha(a.inventory)!=a.inventory_sha256:raise ValueError('Inventory seal differs')
    inventory=json.loads(a.inventory.read_text());start=time.time()
    if inventory['status']!='sealed':raise ValueError('Unsealed inventory')
    fresh=json.loads(Path(inventory['fresh_manifest']['path']).read_text())
    if sha(inventory['fresh_manifest']['path'])!=inventory['fresh_manifest']['sha256']:raise ValueError('Fresh source changed')
    cells={c['cell_id']:c for c in fresh['cells']}
    menu=[{'method':r['method'],'n':r['n']} for r in inventory['conditions'] if r['status']=='cached_selector_full_bank']
    menu.extend({'method':r['method'],'n':r['n']} for r in inventory['conditions'] if r['method'].startswith('best_n_specificity_mean_'))
    wanted={(r['method'],r['n']) for r in menu}
    a.output.mkdir(parents=True,exist_ok=True)
    config={'inventory_sha256':a.inventory_sha256,'conditions':menu,'code_sha256':sha(__file__),'expected_cells':19435}
    if (a.output/'spec.json').exists() and json.loads((a.output/'spec.json').read_text())!=config:raise ValueError('Resume spec differs')
    atomic(a.output/'spec.json',config)
    sources=[];extra={}
    for stage,spec in inventory['stages'].items():
        source=Path(spec['selectors']['path'])
        if sha(source)!=spec['selectors']['sha256']:raise ValueError('Cached selector source changed')
        sources.append(spec['selectors'])
        sub={'development':'development-full-grid-e1-pruning-v1','validation':'validation-full-grid-v1/e1-pruning','test':'test-full-grid-e1-pruning-v2'}[stage]
        q=source.parents[2]/sub/'selections.jsonl'
        status=json.loads(q.with_name('status.json').read_text())
        if status['status']!='complete' or sha(q)!=status['selection_sha256']:raise ValueError('Specificity pruning parent changed')
        sources.append({'path':str(q),'sha256':status['selection_sha256']})
        for row in committed_lines(q):
            if row['cell_id'] in extra:raise ValueError('Duplicate historical combination cell')
            extra[row['cell_id']]={ (r['method'],r['n']):r for r in row['selections']
                if (r['method'],r['n']) in wanted and r['method']!='best_n_specificity_mean' }
    if set(extra)!=set(cells):raise ValueError('Combination sources do not span19435')
    completed={}
    for family in inventory['families']:
        path=a.output/f'{family}.jsonl'
        if path.exists():
            with path.open('rb+') as stream:
                last=0
                while line:=stream.readline():
                    if not line.endswith(b'\n'):stream.truncate(last);break
                    row=json.loads(line)
                    if row['cell_id'] in completed:raise ValueError('Duplicate restart cell')
                    if row['inventory_sha256']!=a.inventory_sha256:raise ValueError('Restart inventory differs')
                    completed[row['cell_id']]=row['family'];last=stream.tell()
    streams={f:(a.output/f'{f}.jsonl').open('a') for f in inventory['families']};seen=set()
    try:
        for stage,spec in inventory['stages'].items():
            stage_seen=set()
            for row in committed_lines(spec['selectors']['path']):
                cid=row['cell_id'];cell=cells[cid]
                if cid in seen or any(row[k]!=cell[k] for k in ('family','item_id','layer','position','split','activation_sha256')):raise ValueError('Source cell identity differs')
                seen.add(cid);stage_seen.add(cid)
                selections={(r['method'],r['n']):r for r in row['selections'] if (r['method'],r['n']) in wanted}
                selections.update(extra.pop(cid))
                parent=selections[('best_n_specificity_mean',32)]
                q=parent['extra']['score'];abstain=dict(parent,method='best_n_specificity_mean_abstain_nonpositive',
                    abstention_control={'threshold':0.,'parent_Q':q,'abstained':q<=0,'parent_text':parent['text'],'parent_phrase_ids':parent['phrase_ids']})
                if q<=0:
                    abstain.update(text='',phrase_ids=[],token_count=0,bullet_count=0,atoms=[],trace=[],reason='nonpositive_complete_mean_Q',
                        fits={'exact':{'coefficients':[],'fve':0.,'atom_ids':[],'solver':'scipy_exact'},'released80':{'coefficients':[],'fve':0.,'atom_ids':[],'solver':'released80'}},
                        fits_scope='emitted_bullets',scored_text='',extra={'score':0.,'abstention_objective':'empty_Q_zero'})
                selections[('best_n_specificity_mean_abstain_nonpositive',32)]=abstain
                if set(selections)!=wanted:raise ValueError('Missing/foreign cached condition')
                if cid in completed:continue
                final=[]
                for item in menu:
                    s=selections[(item['method'],item['n'])]
                    if s['method']!='raw_n1' and (s['bullet_count']>4 or s['token_count']>256):raise ValueError('Final cap violated')
                    final.append({k:s.get(k) for k in ('method','n','text','token_count','bullet_count','reason','fits_scope')})
                out={k:row[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')}
                out.update({'inventory_sha256':a.inventory_sha256,'selections':final,'source_stage':stage})
                stream=streams[row['family']];stream.write(json.dumps(out,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
                completed[cid]=row['family']
                if len(completed)%100==0:
                    atomic(a.output/'status.json',{'status':'running','completed_cells':len(completed),'expected_cells':19435,'seconds':time.time()-start})
                    print(json.dumps({'completed_cells':len(completed)}),flush=True)
            if len(stage_seen)!=spec['cells']:raise ValueError('Incomplete original stage')
    finally:
        for stream in streams.values():stream.close()
    if seen!=set(cells) or set(completed)!=set(cells):raise ValueError('Incomplete full bank')
    for family in inventory['families']:
        own=[{k:c[k] for k in ('cell_id','family','item_id','layer','position','split','group_id','activation_sha256')} for c in cells.values() if c['family']==family]
        manifest=a.output/f'{family}.manifest.json';atomic(manifest,{'schema_version':1,'split':'expansion','scope':inventory['scope'],'cells':own,'inventory_sha256':a.inventory_sha256})
        path=a.output/f'{family}.jsonl';descriptor={'ready':True,'family':family,'manifest':str(manifest),'manifest_sha256':sha(manifest),
            'selections':str(path),'selection_sha256':sha(path),'conditions':menu,'inventory_sha256':a.inventory_sha256,
            'source_parents':sources,'cells':len(own),'items':len({c['item_id'] for c in own})}
        atomic(a.output/f'{family}.ready.json',descriptor)
    atomic(a.output/'conditions.json',menu)
    atomic(a.output/'status.json',{'status':'complete','completed_cells':len(completed),'conditions':len(menu),'expected_cells':19435,
        'source_parents':sources,'seconds':time.time()-start,'new_api_calls':0,'new_model_calls':0})
    print(json.dumps({'status':'complete','cells':len(completed),'conditions':len(menu)}),flush=True)

if __name__=='__main__':main()
