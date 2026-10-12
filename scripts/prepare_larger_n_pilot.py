"""Freeze a metadata-selected 32-site timing/reconstruction pilot, without labels."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261012
FAMILIES = ['hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association']


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()


def main():
    target = ROOT / 'configs/larger_n_pilot_v1.json'
    if target.exists():
        raise FileExistsError(target)
    inventory = json.loads((ROOT / 'configs/target_only_inventory_v2.json').read_text())
    fresh_path = Path(inventory['fresh_manifest']['path'])
    fresh_bytes = fresh_path.read_bytes()
    assert hashlib.sha256(fresh_bytes).hexdigest() == inventory['fresh_manifest']['sha256']
    fresh = json.loads(fresh_bytes)
    chosen = []
    for family in FAMILIES:
        groups = set()
        for layer in [36, 52]:
            candidates = [c for c in fresh['cells'] if c['split'] == 'development' and c['family'] == family and c['layer'] == layer]
            candidates.sort(key=lambda c: (c['group_id'] in groups, digest([SEED, 'larger_n_pilot', c['cell_id']])))
            selected = []
            layer_groups = set()
            for cell in candidates:
                if cell['group_id'] not in layer_groups:
                    selected.append(cell); groups.add(cell['group_id']); layer_groups.add(cell['group_id'])
                if len(selected) == 4:
                    break
            assert len(selected) == 4, (family, layer)
            chosen.extend(selected)
    own = {c['cell_id'] for c in chosen}
    samples = {cid: {} for cid in own}
    provenance = []
    for source in inventory['stages']['development']['samples']:
        hasher = hashlib.sha256()
        with Path(source['path']).open('rb') as handle:
            for line in handle:
                assert line.endswith(b'\n')
                hasher.update(line)
                row = json.loads(line)
                for sample in row.get('records', [row]):
                    if sample['cell_id'] in own:
                        bucket = samples[sample['cell_id']]
                        assert sample['sample_index'] not in bucket
                        bucket[sample['sample_index']] = sample
        assert hasher.hexdigest() == source['sha256'], source['path']
        provenance.append(source)
    baseline = {}
    source = inventory['stages']['development']['selectors']
    hasher = hashlib.sha256()
    with Path(source['path']).open('rb') as handle:
        for line in handle:
            assert line.endswith(b'\n'); hasher.update(line)
            row = json.loads(line)
            if row['cell_id'] in own:
                matches = [s for s in row['selections'] if s['method'] == 'best_n_exact' and s['n'] == 32]
                assert len(matches) == 1
                baseline[row['cell_id']] = matches[0]
    assert hasher.hexdigest() == source['sha256']
    cells = []
    keys = ['cell_id','family','item_id','layer','position','split','group_id',
            'activation_tensor_path','activation_tensor_key','activation_row','activation_sha256']
    for source_cell in chosen:
        cell = {k: source_cell[k] for k in keys}
        bucket = samples[cell['cell_id']]
        assert set(bucket) == set(range(32))
        cell['baseline_samples'] = [bucket[i] for i in range(32)]
        cell['baseline_samples_sha256'] = digest(cell['baseline_samples'])
        cell['baseline_selection'] = baseline[cell['cell_id']]
        cells.append(cell)
    runtime = json.loads((ROOT/'configs/runtime.json').read_text())
    manifest = {
        'schema_version':'larger_n_sampling_pilot_v1','pilot_id':'larger-n-pilot-v1','pilot_seed':SEED,
        'target_n':256,'chunk_size':32,'cells_per_batch':4,
        'authorized_job_ids':['25681811','25637237','25637240'],
        'base_snapshot':runtime['paths']['base_snapshot'],
        'adapter':str(Path(runtime['paths']['fast'])/'cache/huggingface/hub/models--agu18dec--olens_and_ar/snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/olens_s3d_rl600'),
        'base_revision':'6a9e13bd6fc8f0983b9b99948120bc37f49c13e9',
        'adapter_revision':'c95215d5d2f6250f20c305ae55c6e4d7569f92dc',
        'sampling_recipe':{'temperature':1.0,'top_p':0.95,'top_k':64,'max_new_tokens':256,'n_per_call':32},
        'selection_policy':'development only; 4 seeded distinct groups per family at each of layers36 and52; prefer different groups across layers (Chained intermediates has only7 available); no outcome lookup',
        'partial_grid':True,'use_for':'timing and exploratory per-site diagnostics; not original whole-question benchmark accuracy',
        'source_inventory_sha256':hashlib.sha256((ROOT/'configs/target_only_inventory_v2.json').read_bytes()).hexdigest(),
        'source_samples':provenance,'source_selectors':source,'fresh_manifest':inventory['fresh_manifest'],
        'vector_cache':inventory['stages']['development']['vector_cache'],
        'vector_contract':inventory['vector_contract'],'runtime_inputs':inventory['runtime_inputs'],
        'cells':cells,
    }
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'manifest':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                      'cells':len(cells),'new_samples':len(cells)*224}))


if __name__ == '__main__':
    main()
