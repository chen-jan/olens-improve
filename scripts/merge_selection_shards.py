"""Validate and join completed offline selection shards, without changing rows."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from olens_improve.ar_cache import digest


def merge(manifest_path, shard_paths, output):
    manifest_path, output = Path(manifest_path), Path(output)
    manifest_bytes = manifest_path.read_bytes()
    cells = json.loads(manifest_bytes)['cells']
    intended = {c['cell_id']: c for c in cells}
    if len(intended) != len(cells) or not cells:
        raise ValueError('Require a nonempty, unique manifest cohort')
    expected_ids = sorted(intended)
    common = None
    records, sources, indexes = {}, [], set()
    methods = None
    for directory in map(Path, shard_paths):
        files = {name: (directory/name).read_bytes()
                 for name in ('config.json', 'status.json', 'selections.jsonl')}
        config, status = (json.loads(files[name]) for name in ('config.json', 'status.json'))
        count, index = config['shard_count'], config['shard_index']
        if count != len(shard_paths) or not 0 <= index < count or index in indexes:
            raise ValueError('Missing, duplicate, or incompatible shard indexes')
        indexes.add(index)
        expected_shard = expected_ids[index::count]
        if (config['pilot_manifest_sha256'] != sha256(manifest_bytes).hexdigest()
                or config['full_cohort_cell_count'] != len(cells)
                or config['cell_ids'] != expected_shard):
            raise ValueError('Shard cohort differs from the frozen manifest stride')
        if (status['status'] != 'complete'
                or status['completed_cells'] != len(expected_shard)
                or status['expected_cells'] != len(expected_shard)
                or status['shard_index'] != index or status['shard_count'] != count):
            raise ValueError('Shard is not complete')
        scientific = {k: v for k, v in config.items()
                      if k not in ('cell_ids', 'controls', 'shard_index')}
        if common is not None and scientific != common:
            raise ValueError('Shards used different scientific configurations')
        common = scientific
        shard_ids = []
        for line in files['selections.jsonl'].splitlines(keepends=True):
            row = json.loads(line)
            cid = row['cell_id']
            if cid in records or cid not in intended:
                raise ValueError('Duplicate or unexpected output cell')
            cell = intended[cid]
            if row['config_sha256'] != digest(config) or any(
                    row[k] != cell[k] for k in ('family', 'item_id', 'layer', 'position', 'split')):
                raise ValueError('Output provenance or cell identity mismatch')
            arms = [(s['method'], s['n']) for s in row['selections']]
            if len(arms) != len(set(arms)) or (methods is not None and arms != methods):
                raise ValueError('Condition coverage differs across cells')
            methods = arms
            records[cid] = line if line.endswith(b'\n') else line + b'\n'
            shard_ids.append(cid)
        if shard_ids != expected_shard:
            raise ValueError('Shard rows differ from its declared cell list')
        sources.append({'path': str(directory.resolve()), 'shard_index': index,
                        'sha256': {name: sha256(data).hexdigest() for name, data in files.items()},
                        'elapsed_seconds': status['seconds']})
        if any((directory/name).read_bytes() != data for name, data in files.items()):
            raise ValueError('Input changed during merge')
    if set(records) != set(intended):
        raise ValueError('Merged cohort is incomplete')
    payload = b''.join(records[cid] for cid in expected_ids)
    metadata = {'schema_version': 1, 'status': 'complete', 'cells': len(records),
                'manifest_sha256': sha256(manifest_bytes).hexdigest(),
                'selection_sha256': sha256(payload).hexdigest(),
                'methods': methods, 'sources': sorted(sources, key=lambda s: s['shard_index']),
                'scope': common['scope'], 'row_policy': 'Original shard rows retained verbatim',
                'code_sha256': sha256(Path(__file__).read_bytes()).hexdigest()}
    output.mkdir(parents=True, exist_ok=True)
    for name, data in [('selections.jsonl', payload),
                       ('merge.json', (json.dumps(metadata, indent=2)+'\n').encode())]:
        path = output/name
        if path.exists() and path.read_bytes() != data:
            raise ValueError('Refusing to replace a different merged artifact')
        if not path.exists():
            with path.open('xb') as stream:
                stream.write(data)
            path.chmod(0o444)
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--shard', action='append', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(merge(args.manifest, args.shard, args.output), indent=2))
