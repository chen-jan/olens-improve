"""Index existing N64 parent vectors without copying or modifying tensors."""
from collections import defaultdict
import json
from pathlib import Path
import os
from run_larger_n_methods_cpu import PILOT,ROOT,write,sha
from olens_improve.reconstruction import RawVectorCache

assert os.environ.get('SLURM_JOB_ID')
out=Path('${OLENS_DATA_ROOT}/larger-n-methods-v1')
manifest=json.loads(PILOT.read_text())
old=RawVectorCache(manifest['vector_cache']);new=RawVectorCache(str(ROOT/'score256/ar-cache'))
assert old.contract==new.contract
keys=set()
for r in map(json.loads,(out/'cpu/selections.jsonl').read_text().splitlines()):
    for s in r['selections']:
        if s['n']==64 and s['method'] in ('best_n_exact','pooled_greedy_swap'):
            keys.update(a['cache_key'] for a in s['atoms'] if a['cache_key'])
groups=defaultdict(list)
for k in sorted(keys):
    r=old.index.get(k) or new.index[k]
    groups[r['tensor_path']].append({name:value for name,value in r.items() if name!='tensor_path'})
catalog=out/'parent-vector-catalog';catalog.mkdir(parents=True,exist_ok=True)
write(catalog/'contract.json',old.contract)
for i,(path,rows) in enumerate(sorted(groups.items())):
    write(catalog/f'raw_{i:05d}.index.json',{'contract_sha256':old.contract['sha256'],'tensor_path':path,'vectors':rows})
write(catalog/'source.json',{'source_selection_sha256':sha(out/'cpu/selections.jsonl'),
     'vectors':len(keys),'referenced_tensors':len(groups),'copied_tensor_bytes':0,'historical_data_modified':False})
assert set(RawVectorCache(str(catalog)).index)==keys
print(json.dumps({'vectors':len(keys),'referenced_tensors':len(groups),'copied_tensor_bytes':0}),flush=True)
