"""Atomically freeze complete global journals before the next stage appends."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--pool',required=True);p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);p.add_argument('--original-instrument',required=True);p.add_argument('--fresh-manifest',required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Freeze large journals inside the allocated CPU job')
    pool=Path(a.pool);manifest=Path(a.manifest);output=Path(a.output)
    cells=json.loads(manifest.read_text())['cells'];wanted={c['cell_id'] for c in cells}
    fresh_path=Path(a.fresh_manifest);fresh=json.loads(fresh_path.read_text());fresh_cells=fresh['cells'] if isinstance(fresh,dict) else fresh
    activation_hashes={c['cell_id']:c['activation_sha256'] for c in fresh_cells}
    if not wanted<=activation_hashes.keys():raise ValueError('Fresh activation provenance lacks a cohort cell')
    if len(wanted)!=len(cells) or any(c['split']!='development' for c in cells):raise ValueError('Require distinct frozen development cells')
    journals=sorted(pool.glob('shard-*-of-*.jsonl'))
    if len(journals)!=4:raise ValueError('Require the stable four-shard pool')
    parents=[]
    for journal in journals:
        status_path=journal.with_suffix('.status.json');status=json.loads(status_path.read_text());actual=sha(journal)
        if status['status']!='complete' or status['completed_cells']!=status['expected_cells'] or status['target_n']!=32 or status['journal_sha256']!=actual:raise ValueError('All four journals must be terminal and hash-verified')
        parents.append({'path':str(journal),'sha256':actual,'status_path':str(status_path),'status_sha256':sha(status_path),'cells':status['expected_cells']})
    if sum(p['cells'] for p in parents)!=len(cells):raise ValueError('Terminal shard counts differ from the frozen cohort')
    if output.exists():raise FileExistsError('Frozen output already exists; verify it rather than overwrite')
    staging=output.with_name('.'+output.name+'.tmp.'+str(os.getpid()));staging.mkdir(parents=True)
    sources=[pool/'pool.json',manifest,fresh_path,*[Path(p[k]) for p in parents for k in ('path','status_path')]]
    source_hashes={str(p):sha(p) for p in sources}
    for source in sources:
        target=staging/(source.name if source!=manifest else 'cells.json');shutil.copyfile(source,target)
        if sha(target)!=source_hashes[str(source)]:raise ValueError('Snapshot copy differs from source')
        target.chmod(0o444)
    flat=staging/'samples-n32.jsonl'
    subprocess.run([sys.executable,str(Path(__file__).with_name('export_samples.py')),'--pool',str(staging),'--manifest',str(staging/'cells.json'),'--output',str(flat),'--n','32'],check=True)
    original=[json.loads(line) for line in Path(a.original_instrument).read_text().splitlines()]
    expected={(r['cell_id'],r['sample_index']):r for r in original};matched=0;seen=set()
    for line in flat.open():
        row=json.loads(line);key=row['cell_id'],row['sample_index'];seen.add(key[0])
        if row['activation_sha256']!=activation_hashes[key[0]]:raise ValueError('Sample activation hash differs from the fresh capture')
        if key in expected:
            if any(row.get(k)!=v for k,v in expected[key].items()):raise ValueError('An original instrument sample changed')
            matched+=1
    if seen!=wanted or matched!=len(original):raise ValueError('Cohort or original-prefix preservation failed')
    if any(sha(source)!=expected for source,expected in source_hashes.items()):raise ValueError('Global sources changed during freeze')
    flat_manifest_path=flat.with_suffix('.manifest.json');flat_manifest=json.loads(flat_manifest_path.read_text())
    flat_manifest['flat_path']=str(output/flat.name)
    flat_manifest['parent_journal_sha256']={str(output/Path(path).name):value for path,value in flat_manifest['parent_journal_sha256'].items()}
    flat_manifest_path.write_text(json.dumps(flat_manifest,indent=2)+'\n')
    flat.chmod(0o444);flat_manifest_path.chmod(0o444)
    record={'scope':'complete original development grids','global_pool_id':json.loads((staging/'pool.json').read_text())['global_pool_id'],'cells':len(cells),'samples':len(cells)*32,'n':32,'manifest_sha256':sha(manifest),'flat_sha256':sha(flat),'preserved_original_samples':matched,'parents':parents,'source_sha256':source_hashes}
    snapshot=staging/'snapshot.json';snapshot.write_text(json.dumps(record,indent=2)+'\n');snapshot.chmod(0o444)
    staging.rename(output)
    print(json.dumps({'output':str(output),'cells':len(cells),'samples':len(cells)*32,'snapshot_sha256':sha(output/'snapshot.json'),'flat_sha256':sha(output/'samples-n32.jsonl')}))

if __name__=='__main__':main()
