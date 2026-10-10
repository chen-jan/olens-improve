"""New immutable, relocatable raw-vector caches for portable replay only."""
from hashlib import sha256
import json
from pathlib import Path

from .ar_cache import digest, vector_key
from .reconstruction import RawVectorCache


def new_cache_path(path):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError('Saved AR cache must be a new directory; existing caches remain read-only')
    return path


def load_cache(path):
    """Historical caches stay compatible; portable caches require a complete receipt."""
    path = Path(path)
    portable = path/'portable_cache.json'
    if (path/'portable_cache.claim.json').exists() and not portable.exists():
        raise ValueError('Portable cache is incomplete; preserve it and choose a new directory')
    is_portable = portable.exists()
    receipt = json.loads(portable.read_text()) if is_portable else None
    if is_portable:
        if not isinstance(receipt,dict) or receipt.get('status') != 'complete':
            raise ValueError('Portable cache has no completed receipt')
        required = {'portable_cache.claim.json','contract.json','raw_00000.safetensors','raw_00000.index.json','usage.json'}
        if set(receipt.get('files_sha256',{})) != required or {p.name for p in path.iterdir()} != required | {'portable_cache.json'}:
            raise ValueError('Portable cache receipt lacks exact standalone files')
        for name, expected in receipt['files_sha256'].items():
            if Path(name).name != name or sha256((path/name).read_bytes()).hexdigest() != expected:
                raise ValueError('Portable cache file identity differs')
    cache = RawVectorCache(str(path))
    declared = dict(cache.contract); expected = declared.pop('sha256')
    if digest(declared) != expected:
        raise ValueError('AR cache contract digest differs')
    if is_portable:
        if receipt['contract_sha256'] != expected or receipt['unique_vectors'] != len(cache.index):
            raise ValueError('Portable cache receipt differs from its index')
        # Index pointers are relative filenames so the whole standalone cache can move.
        for row in cache.index.values():
            name = row['tensor_path']
            if Path(name).name != name or name not in receipt['files_sha256']:
                raise ValueError('Portable vector points outside its standalone cache')
            row['tensor_path'] = str(path/name)
    return cache


def save_cache(path, contract, entries, usages, provenance):
    """Persist all used effective inputs, never targets, whitening copies or old caches."""
    import torch
    from safetensors.torch import save_file
    path = new_cache_path(path)
    declared = dict(contract); expected = declared.pop('sha256')
    if digest(declared) != expected:
        raise ValueError('Cannot persist an unverified AR cache contract')
    ordered = sorted(entries)
    for key in ordered:
        row = entries[key]
        value = row['vector'].detach().cpu().float()
        if value.shape != (5120,) or not torch.isfinite(value).all():
            raise ValueError('Portable raw vector must be finite and width 5120')
        if key != vector_key(expected, row['tag_ids'], row['scored_token_ids']):
            raise ValueError('Portable vector key differs from effective AR input')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()  # Exclusive claim; a failed attempt is retained, never overwritten.
    def write(name, payload):
        (path/name).write_text(json.dumps(payload, indent=2, allow_nan=False)+'\n')
    write('portable_cache.claim.json', {'status':'building', 'contract_sha256':expected})
    write('contract.json', contract)
    vectors = torch.stack([entries[k]['vector'].detach().cpu().float() for k in ordered]) if ordered else torch.empty((0,5120))
    save_file({'vectors':vectors.contiguous()}, str(path/'raw_00000.safetensors'), metadata={'contract_sha256':expected})
    rows = [{k:v for k,v in entries[key].items() if k!='vector'} | {'cache_key':key,'row':i}
            for i,key in enumerate(ordered)]
    write('raw_00000.index.json', {'contract_sha256':expected,'tensor_path':'raw_00000.safetensors','vectors':rows})
    write('usage.json', {'contract_sha256':expected,'atoms':usages,'source':provenance})
    files = {p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(path.iterdir())}
    receipt = {'status':'complete','contract_sha256':expected,'unique_vectors':len(ordered),
               'full_text_variants':len(usages),'files_sha256':files}
    write('portable_cache.json', receipt)  # Completion is last; partial caches fail closed.
    for file in path.iterdir(): file.chmod(0o444)
    path.chmod(0o555)
    return {'directory':str(path),'receipt_sha256':sha256((path/'portable_cache.json').read_bytes()).hexdigest(),
            'unique_vectors':len(ordered),'full_text_variants':len(usages)}
