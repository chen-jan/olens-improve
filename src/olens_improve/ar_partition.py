"""Isolated effective-key partitions and validated read-only vector catalogs.

No changes to the production encoder/scorer. Workers own separate directories;
the merged catalog references original immutable tensors without copying them.
"""
from hashlib import sha256
import json
from pathlib import Path
from .ar_cache import digest, vector_key
from .stage_permissions import require_gate_capability


def blind_test_generation_authorized(manifest, gate):
    """Separate prospective preparation authority; never test-analysis authority."""
    return (gate.get('authorization_scope') == 'blind_generation_only'
            and manifest.get('blind_test_generation_authorized') is True
            and gate.get('blind_test_generation_authorized') is True
            and manifest.get('frozen_test_authorized') is False
            and gate.get('frozen_test_authorized') is False)


def validate_stage(manifest,manifest_sha,fresh,fresh_sha,gate,*,capability='analysis'):
    require_gate_capability(gate, capability)
    cells={c['cell_id']:c for c in manifest['cells']}
    captures={c['cell_id']:c for c in fresh['cells']}
    if len(cells)!=len(manifest['cells']) or len(captures)!=len(fresh['cells']):
        raise ValueError('Duplicate frozen cell identity')
    stages={c['split'] for c in cells.values()}
    if len(stages)!=1 or not stages.issubset({'development','validation','test'}):
        raise ValueError('Require one explicit intended split')
    stage=next(iter(stages))
    blind_test = (capability == 'generation' and blind_test_generation_authorized(manifest, gate))
    if stage=='test' and gate.get('authorization_scope')=='blind_generation_only' and not blind_test:
        raise ValueError('Blind preparation is authorized for validation only; test remains sealed')
    if manifest.get('split')!=stage:raise ValueError('Manifest split differs from cells')
    if gate.get('manifest_sha256')!=manifest_sha or gate.get('fresh_index_sha256')!=fresh_sha:
        raise ValueError('Coordinator gate does not bind these exact stage/capture manifests')
    if gate.get('recapture_status')!='passed' or gate.get('production_generation_authorized') is not True:
        raise ValueError('Missing passed coordinator stage gate')
    if gate.get('dry_run_only') or gate.get('authorized_cells')!=len(cells) or gate.get('maximum_samples_per_cell')!=32:
        raise ValueError('Gate is dry-run, wrong cohort size or wrong shared sample contract')
    if stage=='test' and not blind_test and not (manifest.get('frozen_test_authorized') is True and gate.get('frozen_test_authorized') is True):
        raise ValueError('Sealed test stage is not scientifically authorized')
    for cid,c in cells.items():
        if cid not in captures or any(c[k]!=captures[cid][k] for k in ('family','item_id','layer','position','split','group_id')):
            raise ValueError('Stage cells differ from verified fresh capture')
        if captures[cid].get('adapter_disabled') is not True:
            raise ValueError('Capture does not verify disabled adapters')
    return stage,cells,captures


def partition_for(key, count):
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError('Positive partition count required')
    if len(key) != 64:
        raise ValueError('Expected SHA256 effective key')
    return int(key, 16) % count


def read_cache(directory):
    """Validate contract/key/row identity from immutable completed shard indexes."""
    from safetensors import safe_open
    directory = Path(directory)
    body = (directory/'contract.json').read_bytes()
    contract = json.loads(body)
    declared = contract['sha256']
    if digest({k:v for k,v in contract.items() if k!='sha256'}) != declared:
        raise ValueError('Cache contract digest differs')
    entries, sources, occupied = {}, [], set()
    for path in sorted(directory.glob('raw_*.index.json')):
        body = path.read_bytes()
        index = json.loads(body)
        if index['contract_sha256'] != declared:
            raise ValueError('Index contract differs')
        tensor_path = Path(index['tensor_path']).resolve()
        with safe_open(str(tensor_path), framework='pt', device='cpu') as tensor:
            shape = tensor.get_slice('vectors').get_shape()
            if (tensor.metadata() or {}).get('contract_sha256')!=declared:
                raise ValueError('Tensor header contract differs')
        if len(shape)!=2:
            raise ValueError('Expected matrix of vector rows')
        for row in index['vectors']:
            key = row['cache_key']
            if vector_key(declared,row['tag_ids'],row['scored_token_ids']) != key:
                raise ValueError('Vector key does not bind its effective input')
            location = (str(tensor_path),row['row'])
            if key in entries or location in occupied:
                raise ValueError('Duplicate key or tensor row')
            if not isinstance(row['row'],int) or not 0<=row['row']<shape[0]:
                raise ValueError('Vector row is out of range')
            occupied.add(location)
            entries[key] = row | {'tensor_path':str(tensor_path)}
        sources.append({'index_path':str(path.resolve()),'index_sha256':sha256(body).hexdigest(),
                        'tensor_path':str(tensor_path),'tensor_shape':shape,'vectors':len(index['vectors'])})
    return contract,entries,sources


def merge_catalog(plan, inherited, workers, output):
    """Require exactly the planned keys and preserve first-computed inherited rows."""
    if len(workers)!=plan['partition_count']:
        raise ValueError('Missing worker partition')
    contract = plan['contract']
    all_entries, all_sources = {}, []
    def add(entries):
        for key,row in entries.items():
            if key in all_entries:
                raise ValueError('Duplicate effective key across cache writers')
            all_entries[key]=row
    old_contract,old_entries,old_sources=read_cache(inherited)
    if old_contract!=contract or digest(sorted(old_entries))!=plan['inherited_keys_sha256']:
        raise ValueError('Inherited cache contract or key set changed')
    if old_sources!=plan['inherited_sources']:
        raise ValueError('Inherited shard provenance changed')
    add(old_entries);all_sources.extend(old_sources)
    expected_new=set()
    for number,directory in enumerate(workers):
        part=plan['partitions'][number]
        body=Path(part['path']).read_bytes()
        if sha256(body).hexdigest()!=part['sha256']:
            raise ValueError('Prepared partition changed')
        records=[json.loads(line) for line in body.splitlines()]
        wanted={r['cache_key'] for r in records}
        if len(wanted)!=len(records) or any(partition_for(k,len(workers))!=number for k in wanted):
            raise ValueError('Prepared partition has duplicate or foreign keys')
        if wanted & (set(old_entries)|expected_new):
            raise ValueError('Partition overlaps inherited/another partition')
        current,entries,sources=read_cache(directory)
        if current!=contract or set(entries)!=wanted:
            raise ValueError('Worker cache does not exactly cover its planned partition')
        # Each worker must have a completed usage run matching its prepared input.
        runs=[json.loads(p.read_text()) for p in Path(directory).glob('usage_*.run.json')]
        if not any(r['status']=='complete' and any(s['sha256']==part['sha256']
                   for s in r['source_inputs']) for r in runs):
            raise ValueError('Worker lacks the terminal prepared-input encoding record')
        add(entries);all_sources.extend(sources);expected_new.update(wanted)
    if len(expected_new)!=plan['new_keys']:
        raise ValueError('Prepared new-key count differs')
    if len({s['tensor_shape'][1] for s in all_sources})>1:
        raise ValueError('Vector widths differ across writers')
    usage_path=Path(plan['usage']['path'])
    usage_body=usage_path.read_bytes()
    if sha256(usage_body).hexdigest()!=plan['usage']['sha256']:
        raise ValueError('Prepared candidate provenance changed')
    # Validate everything before creating the catalog; no partial scientific catalog.
    output=Path(output)
    if output.exists():
        raise ValueError('Refuse replacing catalog')
    output.mkdir(parents=True)
    (output/'contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    grouped={}
    for row in all_entries.values():
        grouped.setdefault(row['tensor_path'],[]).append(row)
    for number,(path,rows) in enumerate(sorted(grouped.items())):
        index={'contract_sha256':contract['sha256'],'tensor_path':path,
               'vectors':[{k:v for k,v in row.items() if k!='tensor_path'} for row in rows]}
        (output/f'raw_{number:05d}.index.json').write_text(json.dumps(index)+'\n')
    (output/'usage_partition_prepared.jsonl').write_bytes(usage_body)
    metadata={'status':'complete','read_only_catalog':True,'vectors':len(all_entries),
              'new_vectors':len(expected_new),'sources':all_sources,'plan_sha256':digest(plan),
              'tensor_copies':0,'policy':'First computed rows retained; worker usages not treated as source-bullet provenance'}
    (output/'catalog.json').write_text(json.dumps(metadata,indent=2)+'\n')
    for path in output.iterdir():path.chmod(0o444)
    output.chmod(0o555)
    return metadata
