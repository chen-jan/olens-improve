"""Validate complete CPU shards and publish immutable family judgment exports."""
from collections import Counter
import argparse
import json
import os
from pathlib import Path
from expanded_cpu_cached import atomic, committed_lines, sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--inventory-sha256',required=True);p.add_argument('--input-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--shard-count',type=int,default=4);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPUs required')
    if sha(a.inventory)!=a.inventory_sha256:raise ValueError('Inventory changed')
    inventory=json.loads(a.inventory.read_text());fresh=json.loads(Path(inventory['fresh_manifest']['path']).read_text());cells={c['cell_id']:c for c in fresh['cells']}
    a.output.mkdir(parents=True,exist_ok=True);conditions=None;sources=[];seen=set()
    paths={family:a.output/f'{family}.jsonl' for family in inventory['families']}
    # All output is regenerated only from terminal journals; partial earlier temp files are disposable.
    streams={family:path.with_suffix('.jsonl.tmp').open('w') for family,path in paths.items()}
    try:
        for index in range(a.shard_count):
            root=a.input_root/f'shard-{index}';status=json.loads((root/'status.json').read_text());path=root/'selections.jsonl'
            if status['status']!='complete' or status['selection_sha256']!=sha(path):raise ValueError('Nonterminal or changed shard')
            sources.append({'path':str(path),'sha256':status['selection_sha256']})
            n=0
            for row in committed_lines(path):
                cid=row['cell_id'];cell=cells[cid];n+=1
                if cid in seen or row['inventory_sha256']!=a.inventory_sha256 or any(row[k]!=cell[k] for k in ('family','item_id','layer','position','split','activation_sha256')):raise ValueError('Shard metadata differs')
                seen.add(cid);menu=[{'method':s['method'],'n':s['n']} for s in row['selections']]
                if conditions is None:conditions=menu
                if menu!=conditions:raise ValueError('Condition menu differs across rows')
                for s in row['selections']:
                    if s['token_count']>256 or s['bullet_count']>4:raise ValueError('Cap exceeded')
                compact={k:row[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256','inventory_sha256')}
                compact['selections']=[{k:s.get(k) for k in ('method','n','text','token_count','bullet_count','reason','fits_scope')} for s in row['selections']]
                streams[row['family']].write(json.dumps(compact,ensure_ascii=False)+'\n')
            if n!=status['expected_cells']:raise ValueError('Shard coverage differs')
    finally:
        for stream in streams.values():stream.close()
    if seen!=set(cells):raise ValueError('Incomplete19435-cell union')
    for family,path in paths.items():
        temp=path.with_suffix('.jsonl.tmp')
        if path.exists() and sha(path)!=sha(temp):raise ValueError('Immutable export would change')
        os.replace(temp,path);path.chmod(0o444)
        own=[{k:c[k] for k in ('cell_id','family','item_id','layer','position','split','group_id','activation_sha256')} for c in cells.values() if c['family']==family]
        manifest=a.output/f'{family}.manifest.json';atomic(manifest,{'schema_version':1,'split':'expansion','scope':inventory['scope'],'cells':own,'inventory_sha256':a.inventory_sha256})
        descriptor={'ready':True,'family':family,'manifest':str(manifest),'manifest_sha256':sha(manifest),'selections':str(path),
            'selection_sha256':sha(path),'conditions':conditions,'inventory_sha256':a.inventory_sha256,'source_parents':sources,'cells':len(own),'items':len({c['item_id'] for c in own})}
        atomic(a.output/f'{family}.ready.json',descriptor)
    atomic(a.output/'conditions.json',conditions)
    atomic(a.output/'status.json',{'status':'complete','cells':len(seen),'conditions':len(conditions),'source_parents':sources})
    print(json.dumps({'status':'complete','cells':len(seen),'conditions':len(conditions)}))

if __name__=='__main__':main()
