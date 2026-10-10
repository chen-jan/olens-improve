"""Export raw/capped N1 before reconstruction finishes, using the shared parser."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from transformers import AutoTokenizer
from olens_improve.ar_cache import input_records
from olens_improve.selection import PARSER_POLICY, parse_bullets, render_bullets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', action='append', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--fresh-manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--runtime', default='configs/runtime.json')
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Use allocated CPU resources')
    manifest_bytes = Path(args.manifest).read_bytes()
    manifest = json.loads(manifest_bytes)
    cells = {c['cell_id']: c for c in manifest['cells']}
    if len(cells) != len(manifest['cells']) or any(c['split'] != 'development' for c in cells.values()):
        raise ValueError('Require unique frozen development cells')
    fresh_bytes = Path(args.fresh_manifest).read_bytes()
    fresh = {c['cell_id']: c for c in json.loads(fresh_bytes)['cells']}
    for cid, cell in cells.items():
        if cid not in fresh or any(fresh[cid][k] != cell[k]
                                  for k in ('family', 'item_id', 'layer', 'position', 'split')):
            raise ValueError('Frozen cohort differs from fresh activation manifest')
    runtime = json.loads(Path(args.runtime).read_text())
    tokenizer = AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'], local_files_only=True)
    def token_count(text):
        return len(tokenizer(text, add_special_tokens=False)['input_ids'])
    originals, sources = {}, []
    for path in map(Path, args.input):
        body = path.read_bytes()
        status = json.loads(path.with_suffix('.status.json').read_text())
        if status['status'] != 'complete' or status['journal_sha256'] != sha256(body).hexdigest():
            raise ValueError('Source journal is not a complete frozen snapshot')
        sources.append({'path': str(path.resolve()), 'sha256': sha256(body).hexdigest()})
        for row in input_records(body):
            cid = row['cell_id']
            if cid not in cells or row['sample_index'] != 0:
                continue
            if cid in originals:
                raise ValueError('Duplicate N1 record')
            if row['activation_sha256'] != fresh[cid]['activation_sha256']:
                raise ValueError('Activation provenance mismatch')
            originals[cid] = row
    if originals.keys() != cells.keys():
        raise ValueError('N1 sample coverage differs from frozen cohort')
    rows = []
    for cid in sorted(cells):
        cell, original = cells[cid], originals[cid]
        pool = original.get('global_pool_id', original['pool_id'])
        sample = parse_bullets(original['text'], f'{pool}:{cid}:0', 0, token_count=token_count)
        selections = []
        for method, text in [('raw_n1', original['text']), ('capped_n1', render_bullets(sample.bullets))]:
            selections.append({'method': method, 'n': 1, 'text': text,
                               'token_count': token_count(text), 'parser_flags': list(sample.flags),
                               'fits': None, 'fits_scope': 'not_reconstruction_scored'})
        rows.append({k: cell[k] for k in ('cell_id', 'family', 'item_id', 'layer', 'position', 'split')} |
                    {'activation_sha256': fresh[cid]['activation_sha256'], 'selections': selections})
    payload = ''.join(json.dumps(row)+'\n' for row in rows).encode()
    metadata = {'manifest_sha256': sha256(manifest_bytes).hexdigest(),
                'fresh_manifest_sha256': sha256(fresh_bytes).hexdigest(),
                'selection_sha256': sha256(payload).hexdigest(), 'sources': sources,
                'cells': len(rows), 'parser': PARSER_POLICY, 'max_capped_tokens': 256,
                'code_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
                'comparison_required': 'Final scored-selector raw/capped text must match this export exactly'}
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    for name, data in [('selections.jsonl', payload),
                       ('export.json', (json.dumps(metadata, indent=2)+'\n').encode()),
                       ('conditions.json', (json.dumps([{'method': m, 'n': 1} for m in ('raw_n1', 'capped_n1')])+'\n').encode())]:
        path = output/name
        if path.exists() and path.read_bytes() != data:
            raise ValueError('Refusing to replace different baseline artifact')
        if not path.exists():
            with path.open('xb') as stream: stream.write(data)
            path.chmod(0o444)
    print(json.dumps(metadata), flush=True)


if __name__ == '__main__':
    main()
