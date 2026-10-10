"""Committed stream boundaries and complete cells under an exact frozen stage gate."""
from hashlib import sha256
import json
from pathlib import Path
from .ar_cache import committed_prefix, complete_cells, input_records, digest
from .models import BASE_REVISION, PAIR_REVISION
from .stage_io import validate_export_stage


def stream_context(cohort_body, fresh_body, gate_body=None):
    stage, cohort, captures = validate_export_stage(cohort_body, fresh_body, gate_body)
    for cid, cell in cohort.items():
        if cell['group_id'] != captures[cid]['group_id'] or captures[cid].get('adapter_disabled') is not True:
            raise ValueError('Streaming cohort lacks verified fresh adapter-free capture')
    return stage, cohort, captures


def stream_rows(paths, cohort, captures, global_pool_id, completed=()):
    if set(completed) - set(cohort): raise ValueError('Streaming checkpoint contains off-cohort completed cells')
    rows = []; parents = []; seen = set(); historical = 0
    for path in paths:
        path = Path(path); raw = path.read_bytes(); body = committed_prefix(raw)
        parents.append({'path': str(path), 'committed_bytes': len(body),
                        'committed_prefix_sha256': sha256(body).hexdigest(),
                        'observed_bytes': len(raw), 'uncommitted_tail_bytes': len(raw)-len(body)})
        for row in input_records(body):
            cid, index = row['cell_id'], row['sample_index']
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < 32:
                raise ValueError('Invalid streaming sample index')
            if (cid, index) in seen: raise ValueError('Duplicate streaming record, including historical cells')
            seen.add((cid,index))
            if row.get('base_revision') != BASE_REVISION or row.get('adapter_revision') != PAIR_REVISION:
                raise ValueError('Streaming verbalizer differs from frozen revisions')
            if row.get('global_pool_id') != global_pool_id: raise ValueError('Mixed streaming global pools')
            if cid not in captures: raise ValueError('Streaming source cell absent from verified capture')
            capture = captures[cid]
            if any(row[k] != capture[k] for k in ('family','item_id','layer','position')) or row['activation_sha256'] != capture['activation_sha256']:
                raise ValueError('Streaming source identity/activation differs from verified capture')
            if row.get('split',capture['split']) != capture['split']:
                raise ValueError('Streaming source stage differs from verified capture')
            if cid not in cohort: historical += 1; continue
            rows.append(row)
    return complete_cells(rows,cohort,completed), parents, historical


def snapshot_payload(rows, stage, *, test_authorized=False):
    if stage == 'test' and not test_authorized: raise ValueError('Sealed test snapshot not authorized by verified gate')
    enriched = []; original_hashes = []
    for row in rows:
        if row.get('split',stage) != stage: raise ValueError('Mixed-stage snapshot')
        if stage != 'test' and row.get('frozen_test_authorized') is True:
            raise ValueError('Test authorization cannot propagate through another stage')
        original_hashes.append({'cell_id':row['cell_id'],'sample_index':row['sample_index'],'record_sha256':digest(row)})
        emitted = dict(row); emitted['split'] = stage
        if stage == 'test': emitted['frozen_test_authorized'] = True
        enriched.append(emitted)
    body = ''.join(json.dumps(row,sort_keys=True)+'\n' for row in enriched).encode()
    return body, original_hashes


def preserved_cache_metadata(output_root, destination):
    """Immutable metadata-only history; original vectors/indexes/usages remain in place."""
    output_root = Path(output_root); destination = Path(destination)
    files = []
    for directory in sorted(output_root.iterdir()):
        if not directory.is_dir() or not (directory/'contract.json').exists(): continue
        for path in sorted(directory.iterdir()):
            if path.name in ('contract.json','progress.json','catalog.json','mixed_tag_fixture.json') or path.name.endswith('.index.json') or path.name.endswith('.run.json'):
                body = path.read_bytes(); files.append((path,body))
    summary = [{'path':str(p),'sha256':sha256(b).hexdigest(),'bytes':len(b)} for p,b in files]
    identity = digest(summary); folder = destination/identity[:20]
    folder.mkdir(parents=True,exist_ok=True)
    for i,(path,body) in enumerate(files):
        target=folder/f'{i:05d}-{path.name}'
        if target.exists() and target.read_bytes()!=body: raise ValueError('Historical cache metadata changed')
        if not target.exists(): target.write_bytes(body); target.chmod(0o444)
    manifest=folder/'manifest.json'; payload=(json.dumps({'source_files':summary,'content_sha256':identity,
              'policy':'Metadata-only before-stage snapshot; original tensors/indexes/usages retained.'},indent=2)+'\n').encode()
    if manifest.exists() and manifest.read_bytes()!=payload: raise ValueError('Historical cache snapshot identity changed')
    if not manifest.exists():manifest.write_bytes(payload);manifest.chmod(0o444)
    return {'path':str(manifest),'sha256':sha256(payload).hexdigest(),'files':len(files)}
