"""Extract the three Hallucination (chat) settings from the frozen full-grid selector outputs
and check AR-vector cache coverage. READ-ONLY on project data; writes only into OUT.

Usage: python -I extract_hall.py OUT_DIR
Outputs:
  OUT/hall_three_settings.jsonl  one row per hallucination cell (5,615), three settings each
  OUT/hall_vector_index.json     {stage: {cache_key: [tensor_path, row]}} for every needed key
  OUT/extract_summary.json       counts / coverage / cross-check results
"""
import collections
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, '${OLENS_REPO_ROOT}/src')
from olens_improve.ar_cache import vector_key  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
D = '${OLENS_DATA_ROOT}'
C = '${OLENS_COMPUTE_ROOT}'
SELECTIONS = {
    'development': f'{D}/selections/development-full-grid-v4/merged/selections.jsonl',
    'validation': f'{D}/selections/validation-full-grid-v1/merged/selections.jsonl',
    'test': f'{D}/selections/test-full-grid-v1/merged/selections.jsonl',
}
CACHES = {  # exactly the cache each stage's selector used (configs/expansion_manifest_v1.json stages.*.vector_cache)
    'development': f'{C}/vectors/shared-global-v1/a451cf49d28ac7447722',
    'validation': f'{C}/vectors/validation-catalog-v1',
    'test': f'{C}/vectors/test-catalog-v1',
}
FRESH = f'{C}/activations/core-v1/fresh_manifest_v2.json'
CACHED_V2 = f'{D}/expansion-v1/selections/cached-v2/hallucination.jsonl'
WANT = {('capped_n1', 1): 'capped_n1-n1', ('best_n_exact', 32): 'best_n_exact-n32',
        ('pooled_greedy_swap', 32): 'pooled_greedy_swap-n32'}
PREFIX = b'{"cell_id": "hallucination|'
CONTRACT = 'a451cf49d28ac74477229e74dfc738e51b8961b5376c688fd9e40abbd8c133b6'
ATOM_KEEP = ('source_phrase_id', 'sample_index', 'text', 'scored_text', 'cache_key', 'status',
             'original_token_count', 'scored_token_count', 'truncated', 'scored_token_ids',
             'unscored_suffix_ids', 'parser_flags', 'span_start', 'span_end')

t0 = time.time()
summary = collections.OrderedDict()
fresh = {c['cell_id']: c for c in json.load(open(FRESH))['cells'] if c['family'] == 'hallucination'}
summary['fresh_hall_cells'] = len(fresh)

# Expansion-level chosen outputs (what was judged); used only as a cross-check of identity.
expansion = {}
with open(CACHED_V2) as f:
    for line in f:
        r = json.loads(line)
        for s in r['selections']:
            cond = WANT.get((s['method'], s['n']))
            if cond:
                expansion[(r['cell_id'], cond)] = (hashlib.sha256(s['text'].encode()).hexdigest(),
                                                   s['token_count'], s['bullet_count'])
summary['cached_v2_pairs'] = len(expansion)

needed = {stage: set() for stage in SELECTIONS}
stats = collections.Counter()
seen = set()
with open(OUT / 'hall_three_settings.jsonl', 'w') as out:
    for stage, path in SELECTIONS.items():
        with open(path, 'rb') as f:
            for raw in f:
                if not raw.startswith(PREFIX):
                    continue
                row = json.loads(raw)
                cid = row['cell_id']
                cell = fresh[cid]
                assert cid not in seen, cid
                seen.add(cid)
                assert row['split'] == stage == cell['split'], (cid, row['split'], stage)
                for k in ('family', 'item_id', 'layer', 'position', 'activation_sha256'):
                    assert row[k] == cell[k], (cid, k)
                settings = {}
                for s in row['selections']:
                    cond = WANT.get((s['method'], s['n']))
                    if not cond:
                        continue
                    exact = (s.get('fits') or {}).get('exact')
                    assert exact is not None and exact['solver'] == 'scipy_exact', (cid, cond)
                    assert list(exact['atom_ids']) == s['phrase_ids'], (cid, cond)
                    assert [a['source_phrase_id'] for a in s['atoms']] == s['phrase_ids'], (cid, cond)
                    tsha = hashlib.sha256(s['text'].encode()).hexdigest()
                    exp = expansion[(cid, cond)]
                    if exp != (tsha, s['token_count'], s['bullet_count']):
                        stats['expansion_text_mismatch'] += 1
                    atoms = [{k: a.get(k) for k in ATOM_KEEP} for a in s['atoms']]
                    for a in atoms:
                        stats[f'atoms[{cond}]'] += 1
                        if a['cache_key'] is None:
                            stats[f'atoms_without_key[{cond}]'] += 1
                        else:
                            needed[stage].add(a['cache_key'])
                        if a['truncated']:
                            stats[f'atoms_truncated_gt32[{cond}]'] += 1
                    keys = [a['cache_key'] for a in atoms]
                    if len(set(keys)) != len(keys):
                        stats[f'readouts_with_shared_vector[{cond}]'] += 1
                    stats[f'bullets={len(atoms)}[{cond}]'] += 1
                    rel = (s.get('fits') or {}).get('released80') or {}
                    settings[cond] = {
                        'method': s['method'], 'n': s['n'], 'text': s['text'], 'text_sha256': tsha,
                        'token_count': s['token_count'], 'bullet_count': s['bullet_count'],
                        'reason': s['reason'], 'fits_scope': s['fits_scope'], 'phrase_ids': s['phrase_ids'],
                        'fve': exact['fve'], 'coefficients': exact['coefficients'],
                        'released80_fve': rel.get('fve'), 'trace': s['trace'], 'atoms': atoms,
                    }
                assert set(settings) == set(WANT.values()), (cid, sorted(settings))
                out.write(json.dumps({
                    'cell_id': cid, 'family': 'hallucination', 'item_id': row['item_id'],
                    'group_id': cell['group_id'], 'layer': row['layer'], 'position': row['position'],
                    'split': stage, 'token': cell.get('token'), 'read_position_kind': cell.get('read_position_kind'),
                    'activation_row': cell['activation_row'], 'activation_sha256': cell['activation_sha256'],
                    'global_pool_id': row['global_pool_id'], 'vector_cache': CACHES[stage],
                    'source_selections': path, 'settings': settings,
                }, ensure_ascii=False) + '\n')
                stats[f'cells[{stage}]'] += 1
                stats[f'cells[L{row["layer"]}]'] += 1
        print(stage, 'done', round(time.time() - t0, 1), 's', flush=True)
summary['cells_extracted'] = len(seen)
summary['missing_vs_fresh'] = sorted(set(fresh) - seen)[:20]
summary['stats'] = dict(sorted(stats.items()))

# Coverage: locate every needed key in the stage's own cache (index JSON only).
index = {}
cov = {}
found_meta = {}
tags = {}
for stage, directory in CACHES.items():
    contract = json.load(open(Path(directory) / 'contract.json'))
    assert contract['sha256'] == CONTRACT
    want = needed[stage]
    found = {}
    files = sorted(Path(directory).glob('raw_*.index.json'))
    for p in files:
        info = json.load(open(p))
        assert info['contract_sha256'] == CONTRACT
        for v in info['vectors']:
            k = v['cache_key']
            if k in want:
                assert k not in found, ('duplicate key in one cache', k)
                assert vector_key(CONTRACT, v['tag_ids'], v['scored_token_ids']) == k
                assert tags.setdefault(v['layer'], v['tag_ids']) == v['tag_ids']
                found[k] = [info['tensor_path'], v['row'], v['layer'], len(v['scored_token_ids'])]
    index[stage] = {k: v[:2] for k, v in found.items()}
    found_meta[stage] = found
    cov[stage] = {'index_files': len(files), 'needed_keys': len(want), 'found_keys': len(found),
                  'missing_keys': sorted(want - set(found))[:20],
                  'tensor_files_touched': len({v[0] for v in found.values()})}
    print(stage, cov[stage]['needed_keys'], cov[stage]['found_keys'], round(time.time() - t0, 1), 's', flush=True)
summary['coverage'] = cov

# Atom-level consistency: the index row's layer equals the cell layer, and the atom's own
# scored_token_ids (<=32, after cleanup) + that layer's prompt tag reproduce its cache_key.
checks = collections.Counter()
with open(OUT / 'hall_three_settings.jsonl') as f:
    for line in f:
        r = json.loads(line)
        for cond, s in r['settings'].items():
            for a in s['atoms']:
                k = a['cache_key']
                if k is None or k not in found_meta[r['split']]:
                    continue
                meta = found_meta[r['split']][k]
                checks['layer_ok' if meta[2] == r['layer'] else 'layer_mismatch'] += 1
                ok = vector_key(CONTRACT, tags[r['layer']], a['scored_token_ids']) == k
                checks['atom_tokens_reproduce_key' if ok else 'atom_tokens_key_mismatch'] += 1
                checks['scored_le_32' if len(a['scored_token_ids']) <= 32 else 'scored_gt_32'] += 1
summary['atom_key_checks'] = dict(checks)
summary['tag_ids_by_layer'] = {str(k): v for k, v in sorted(tags.items())}
summary['seconds'] = time.time() - t0
json.dump(index, open(OUT / 'hall_vector_index.json', 'w'))
json.dump(summary, open(OUT / 'extract_summary.json', 'w'), indent=1)
print(json.dumps(summary, indent=1)[:6000])
