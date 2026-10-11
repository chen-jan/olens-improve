"""Crash-safe boundaries shared by the expansion GPU phases."""
import hashlib
import json
import os
from pathlib import Path


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def recover_journal(path, spec_sha256, allowed):
    """Validate complete lines; preserve then discard only an uncommitted tail."""
    path = Path(path)
    done = set()
    if not path.exists():
        return done
    committed = 0
    tail = None
    with path.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):
                tail = line
                break
            row = json.loads(line)
            key = row.get('cell_id')
            if key not in allowed or key in done or row.get('spec_sha256') != spec_sha256:
                raise ValueError('Off-cohort, duplicate or incompatible GPU journal cell')
            done.add(key)
            committed += len(line)
    if tail:
        backup = path.with_name(path.name + '.uncommitted-' + hashlib.sha256(tail).hexdigest()[:20])
        if backup.exists() and backup.read_bytes() != tail:
            raise ValueError('Uncommitted tail backup collision')
        backup.write_bytes(tail)
        with path.open('r+b') as stream:
            stream.truncate(committed)
            stream.flush()
            os.fsync(stream.fileno())
    return done


def validate_vector_shards(root, contract_sha256):
    """Accept indexed finite tensors only; orphan tensors never imply completion."""
    import torch
    from safetensors import safe_open
    root = Path(root)
    known = set()
    for index_path in sorted(root.glob('raw_*.index.json')):
        info = json.loads(index_path.read_text())
        tensor_path = Path(info['tensor_path'])
        if info['contract_sha256'] != contract_sha256 or not tensor_path.is_file():
            raise ValueError('Vector index has incompatible contract or missing tensor')
        with safe_open(str(tensor_path), framework='pt', device='cpu') as stream:
            if list(stream.keys()) != ['vectors']:
                raise ValueError('Unexpected vector tensor keys')
            vectors = stream.get_tensor('vectors')
            if vectors.ndim != 2 or vectors.shape != (len(info['vectors']), 5120) or not torch.isfinite(vectors).all():
                raise ValueError('Invalid completed vector shard')
        if [v['row'] for v in info['vectors']] != list(range(len(info['vectors']))):
            raise ValueError('Vector index row mapping changed')
        for row in info['vectors']:
            if row['cache_key'] in known:
                raise ValueError('Duplicate vector cache key')
            known.add(row['cache_key'])
    # Never overwrite a tensor that was atomically written before its index.
    numbers = [int(p.name.split('_')[1].split('.')[0]) for p in root.glob('raw_*')
               if p.name.endswith(('.safetensors', '.index.json'))]
    return known, max(numbers, default=-1) + 1
