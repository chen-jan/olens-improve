"""Export raw/capped N1, or separate candidate diagnostics, with the shared parser."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import random

from transformers import AutoTokenizer
from olens_improve.ar_cache import input_records
from olens_improve.selection import PARSER_POLICY, parse_bullets, render_bullets
from olens_improve.stage_io import validate_export_stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', action='append', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--fresh-manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--runtime', default='configs/runtime.json')
    parser.add_argument('--gate')
    parser.add_argument('--all-candidates', action='store_true',
                        help='Diagnostic only: one separate condition for each of the frozen 32 samples')
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Use allocated CPU resources')
    manifest_bytes = Path(args.manifest).read_bytes()
    manifest = json.loads(manifest_bytes)
    fresh_bytes = Path(args.fresh_manifest).read_bytes()
    gate_bytes = Path(args.gate).read_bytes() if args.gate else None
    stage, cells, fresh = validate_export_stage(manifest_bytes, fresh_bytes, gate_bytes)
    if args.all_candidates and stage != 'development':
        raise ValueError('Every-candidate diagnostic remains development-only')
    runtime = json.loads(Path(args.runtime).read_text())
    tokenizer = AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'], local_files_only=True)
    def token_count(text):
        return len(tokenizer(text, add_special_tokens=False)['input_ids'])
    originals, sources = {}, []
    indices = range(32) if args.all_candidates else range(1)
    for path in map(Path, args.input):
        body = path.read_bytes()
        status = json.loads(path.with_suffix('.status.json').read_text())
        if status['status'] != 'complete' or status['journal_sha256'] != sha256(body).hexdigest():
            raise ValueError('Source journal is not a complete frozen snapshot')
        sources.append({'path': str(path.resolve()), 'sha256': sha256(body).hexdigest()})
        for row in input_records(body):
            cid = row['cell_id']
            if cid not in cells or row['sample_index'] not in indices:
                continue
            key = (cid, row['sample_index'])
            if key in originals:
                raise ValueError('Duplicate source sample')
            if any(row[k] != cells[cid][k] for k in ('family','item_id','layer','position')) or row.get('split',stage) != stage:
                raise ValueError('Source sample identity/stage differs from frozen cohort')
            if row['activation_sha256'] != fresh[cid]['activation_sha256']:
                raise ValueError('Activation provenance mismatch')
            originals[key] = row
    if originals.keys() != {(cid, index) for cid in cells for index in indices}:
        raise ValueError('Sample coverage differs from frozen cohort/prefix')
    rows = []
    for cid in sorted(cells):
        cell = cells[cid]
        selections = []
        for index in indices:
            original = originals[(cid, index)]
            pool = original.get('global_pool_id', original['pool_id'])
            sample = parse_bullets(original['text'], f'{pool}:{cid}:{index}', index, token_count=token_count)
            entries = ([(f'candidate_index_{index:02d}', render_bullets(sample.bullets))]
                       if args.all_candidates else
                       [('raw_n1', original['text']), ('capped_n1', render_bullets(sample.bullets))])
            for method, text in entries:
                selections.append({'method': method, 'n': 32 if args.all_candidates else 1,
                                   'text': text, 'source_sample_index': index,
                                   'token_count': token_count(text), 'parser_flags': list(sample.flags),
                                   'fits': None, 'fits_scope': 'not_reconstruction_scored'})
        rows.append({k: cell[k] for k in ('cell_id', 'family', 'item_id', 'layer', 'position', 'split')} |
                    {'activation_sha256': fresh[cid]['activation_sha256'], 'selections': selections})
    payload = ''.join(json.dumps(row)+'\n' for row in rows).encode()
    metadata = {'manifest_sha256': sha256(manifest_bytes).hexdigest(),
                'fresh_manifest_sha256': sha256(fresh_bytes).hexdigest(),
                'coordinator_gate_sha256': sha256(gate_bytes).hexdigest() if gate_bytes else None,
                'split': stage,
                'selection_sha256': sha256(payload).hexdigest(), 'sources': sources,
                'cells': len(rows), 'parser': PARSER_POLICY, 'max_capped_tokens': 256,
                'diagnostic_all_candidates': args.all_candidates,
                'condition_dispatch_seed': 20261010 if args.all_candidates else None,
                'evaluation_rule': 'Exactly one selected readout per cell in each separate condition',
                'code_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
                'comparison_required': 'Final scored-selector raw/capped text must match this export exactly'}
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    conditions = ([{'method': f'candidate_index_{i:02d}', 'n': 32} for i in indices]
                  if args.all_candidates else [{'method': m, 'n': 1} for m in ('raw_n1', 'capped_n1')])
    if args.all_candidates:
        random.Random(20261010).shuffle(conditions)
    for name, data in [('selections.jsonl', payload),
                       ('export.json', (json.dumps(metadata, indent=2)+'\n').encode()),
                       ('conditions.json', (json.dumps(conditions)+'\n').encode())]:
        path = output/name
        if path.exists() and path.read_bytes() != data:
            raise ValueError('Refusing to replace different baseline artifact')
        if not path.exists():
            with path.open('xb') as stream: stream.write(data)
            path.chmod(0o444)
    print(json.dumps(metadata), flush=True)


if __name__ == '__main__':
    main()
