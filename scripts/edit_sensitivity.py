"""Reencode selected edit/parent pairs together; never replace cached results."""
import argparse
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file, save_file
from olens_improve.reconstruction import FrozenAR, JointNNLS, Whitener


def main():
    parser = argparse.ArgumentParser()
    for name in ('scored', 'fresh-manifest', 'checkpoint', 'whitener-directory', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--runtime', default='configs/runtime.json')
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Use the assigned GPU')
    torch.set_num_threads(4)
    started = time.time()
    source = Path(args.scored).read_bytes()
    rows = [json.loads(line) for line in source.splitlines()]
    fresh_bytes = Path(args.fresh_manifest).read_bytes()
    cells = {row['cell_id']: row for row in json.loads(fresh_bytes)['cells']}
    pairs = []
    inputs = OrderedDict()
    for row in rows:
        if row['best']['origin'] == 'unchanged_parent':
            continue
        cell = cells[row['cell_id']]
        if cell['split'] != 'development':
            raise ValueError('Development only')
        original = max((c for c in row['candidates'] if c['origin'] == 'unchanged_parent'),
                       key=lambda c: c['exact_fve'])
        edited = row['best']
        pairs.append((row, original, edited))
        for candidate in (original, edited):
            for atom in candidate['atom_metadata']:
                inputs.setdefault(atom['cache_key'], atom)
    if not pairs or len(inputs) > 128:
        raise ValueError('Expected a bounded single-batch sensitivity diagnostic')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    spec = {'selection_rule': 'All round1 edits selected over the best unchanged parent',
            'scored_input_sha256': hashlib.sha256(source).hexdigest(),
            'fresh_manifest_sha256': hashlib.sha256(fresh_bytes).hexdigest(),
            'cell_ids': [row['cell_id'] for row, _, _ in pairs],
            'ordered_keys': list(inputs), 'single_batch_size': len(inputs),
            'production_cache_modified': False,
            'code_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                           [Path(__file__), Path('src/olens_improve/reconstruction.py')]}}
    runtime = json.loads(Path(args.runtime).read_text())
    previous_spec = json.loads(Path(args.scored).with_name('spec.json').read_text())
    contract = previous_spec['vector_contract']
    for field, filename in [('head_sha256', 'heads.pt'), ('adapter_sha256', 'lora/adapter_model.safetensors'),
                            ('meta_sha256', 'meta.json')]:
        if hashlib.sha256((Path(args.checkpoint) / filename).read_bytes()).hexdigest() != contract[field]:
            raise ValueError('Checkpoint contract changed')
    spec['vector_contract'] = contract
    (output / 'spec.json').write_text(json.dumps(spec, indent=2) + '\n')
    ar = FrozenAR.load(runtime['paths']['base_snapshot'], args.checkpoint)
    atoms = list(inputs.values())
    vectors, metadata = ar.encode_mixed([a['text'] for a in atoms], [a['layer'] for a in atoms])
    for original, encoded in zip(atoms, metadata):
        if original['scored_token_ids'] != encoded['input_ids']:
            raise ValueError('Scorer tokens changed')
    save_file({'vectors': vectors}, str(output / 'diagnostic_vectors.safetensors'))
    positions = {key: i for i, key in enumerate(inputs)}
    (output / 'encoding.json').write_text(json.dumps(metadata, indent=2) + '\n')
    tensor_paths = {cells[row['cell_id']]['activation_tensor_path'] for row, _, _ in pairs}
    if len(tensor_paths) != 1:
        raise ValueError('Expected one fresh target tensor')
    targets = load_file(next(iter(tensor_paths)))['resid']
    whiteners = {}
    results = []
    for row, original, edited in pairs:
        cell = cells[row['cell_id']]
        target = targets[cell['activation_row']]
        if hashlib.sha256(target.numpy().tobytes()).hexdigest() != cell['activation_sha256']:
            raise ValueError('Target changed')
        layer = cell['layer']
        if layer not in whiteners:
            whiteners[layer] = Whitener.load(str(Path(args.whitener_directory) /
                                                f'whitening_iolens_pooled_L{layer}.safetensors'))
        scores = []
        for candidate in (original, edited):
            raw = {a['phrase_id']: vectors[positions[a['cache_key']]] for a in candidate['atom_metadata']}
            scorer = JointNNLS.from_raw(target, raw, whiteners[layer])
            scores.append(scorer.score(tuple(raw)))
        cached_delta = edited['exact_fve'] - original['exact_fve']
        results.append({'cell_id': row['cell_id'], 'family': row['family'], 'layer': layer,
                        'original_candidate_id': original['candidate_id'], 'edited_candidate_id': edited['candidate_id'],
                        'cached_parent_fve': original['exact_fve'], 'cached_edited_fve': edited['exact_fve'],
                        'matched_parent_fve': scores[0], 'matched_edited_fve': scores[1],
                        'cached_gain': cached_delta, 'matched_gain': scores[1] - scores[0],
                        'gain_delta': scores[1] - scores[0] - cached_delta,
                        'positive_gain_preserved': scores[1] > scores[0],
                        'whitener_sha256': whiteners[layer].artifact_sha256})
    summary = {'status': 'complete', 'spec': spec, 'results': results, 'seconds': time.time() - started,
               'quality_status': 'unjudged; selected winners only, not an unbiased effect estimate'}
    (output / 'results.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
