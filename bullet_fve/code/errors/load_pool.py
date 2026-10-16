#!/usr/bin/env python
"""Extract the 32-sample lens pools for all 5,615 Hallucination (chat) cells (read-only inputs).

Sources (configs/expansion_manifest_v1.json stages.*.samples):
  development: runs/development-full-grid-v2/samples-n32.jsonl  (flat file whose manifest lists the
               four shard-00{0..3}-of-004.jsonl journals named in the expansion manifest as parents;
               sha256 of those parents is checked against the expansion manifest below)
  validation : runs/validation-full-grid-v1/samples-n32.jsonl
  test       : runs/test-full-grid-v1/samples-n32.jsonl
Also extracts the development all-candidate pilot pool (pilot189-samples-v1.jsonl) for its 72
hallucination cells, to compare its sample texts with the full-grid pool.

Writes errors/pool_hall.json: {meta, pools: {cell_key: [32 texts]}, pilot: {cell_key: [32 texts]}}
cell_key = "<item>.L<layer>.p<pos>" (page key format).
"""
import json
import sys
import time

ROOT = '${OLENS_DATA_ROOT}'
MANIFEST = '${OLENS_REPO_ROOT}/configs/expansion_manifest_v1.json'
OUT = '${OLENS_SCRATCH}/olens-bullet-fve/errors/pool_hall.json'
FLAT = {
    'development': f'{ROOT}/runs/development-full-grid-v2/samples-n32.jsonl',
    'validation': f'{ROOT}/runs/validation-full-grid-v1/samples-n32.jsonl',
    'test': f'{ROOT}/runs/test-full-grid-v1/samples-n32.jsonl',
}
PILOT = f'{ROOT}/runs/development-shared-pilot-v2/pilot189-samples-v1.jsonl'
NEEDLE = b'"family": "hallucination"'


def key_of(rec):
    return f"{rec['item_id']}.L{rec['layer']}.p{rec['position']}"


def read_flat(path):
    pools, meta = {}, {}
    n = 0
    with open(path, 'rb') as f:
        for line in f:
            if NEEDLE not in line:
                continue
            r = json.loads(line)
            if r.get('family') != 'hallucination':
                continue
            k = key_of(r)
            pools.setdefault(k, {})[r['sample_index']] = r['text']
            meta.setdefault(k, {'cell_id': r['cell_id'], 'activation_sha256': r['activation_sha256']})
            n += 1
    return pools, meta, n


def main():
    t0 = time.time()
    man = json.load(open(MANIFEST))
    checks = {}
    # the dev flat file's manifest must list exactly the expansion manifest's dev shard journals
    dev_flat_man = json.load(open(FLAT['development'].replace('.jsonl', '.manifest.json')))
    exp_dev = {s['path'].rsplit('/', 1)[1]: s['sha256'] for s in man['stages']['development']['samples']}
    flat_par = {p.rsplit('/', 1)[1]: h for p, h in dev_flat_man['parent_journal_sha256'].items()}
    checks['dev_flat_parents_match_expansion_manifest'] = exp_dev == flat_par
    for split in ('validation', 'test'):
        exp = man['stages'][split]['samples'][0]
        fm = json.load(open(FLAT[split].replace('.jsonl', '.manifest.json')))
        checks[f'{split}_flat_sha_matches_manifest'] = fm['flat_sha256'] == exp['sha256']
    pools, cellmeta, counts = {}, {}, {}
    for split, path in FLAT.items():
        p, m, n = read_flat(path)
        counts[split] = {'cells': len(p), 'samples': n}
        for k in p:
            assert k not in pools, k
            pools[k] = [p[k][i] for i in range(32)]  # KeyError if any index missing
            cellmeta[k] = dict(m[k], split=split)
        print(split, counts[split], f'{time.time()-t0:.0f}s', flush=True)
    pp, pm, pn = read_flat(PILOT)
    pilot = {k: [pp[k][i] for i in range(32)] for k in pp}
    same = sum(pilot[k] == pools.get(k) for k in pilot)
    per_sample_same = sum(a == b for k in pilot for a, b in zip(pilot[k], pools.get(k, [None] * 32)))
    checks['pilot_cells'] = len(pilot)
    checks['pilot_cells_identical_32_texts_to_full_grid'] = same
    checks['pilot_samples_identical'] = per_sample_same
    checks['pilot_activation_sha_match'] = sum(pm[k]['activation_sha256'] == cellmeta.get(k, {}).get('activation_sha256') for k in pilot)
    print(checks, flush=True)
    json.dump({'meta': {'counts': counts, 'checks': checks, 'sources': FLAT, 'pilot_source': PILOT,
                        'cellmeta': cellmeta},
               'pools': pools, 'pilot': pilot}, open(OUT, 'w'))
    print('wrote', OUT, f'{time.time()-t0:.0f}s')


if __name__ == '__main__':
    sys.exit(main())
