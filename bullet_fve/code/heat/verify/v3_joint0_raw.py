"""Step 3: joint_0 (FVE of the readout without bullet b) recomputed from raw cached AR vectors + the activation
row + Whitener.load via olens_improve.reconstruction.JointNNLS.from_raw(solver='scipy_exact'), for 100 random
occurrences (+ targeted edge cases: readouts with < 4 bullets and readouts with a duplicated bullet).
Also full readout FVE vs joint_cached / saved and LOO drop vs bullet_metrics.jsonl."""
import collections
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, '${OLENS_REPO_ROOT}/src')
from olens_improve.reconstruction import JointNNLS, Whitener  # noqa: E402

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
HEAT = ROOT / 'heat'
OUT = HEAT / 'verify'
ACTS = '${OLENS_COMPUTE_ROOT}/activations/core-v1/activations.safetensors'
WHT = ('${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/'
       'snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners/whitening_iolens_pooled_L{}.safetensors')
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')


def rows_memmap(path, key):
    with open(path, 'rb') as f:
        n = int.from_bytes(f.read(8), 'little')
        h = json.loads(f.read(n))
    return np.memmap(path, dtype='<f4', mode='r', offset=8 + n + h[key]['data_offsets'][0], shape=tuple(h[key]['shape']))


def main():
    torch.set_num_threads(8)
    t0 = time.time()
    cells = {}
    for l in open(ROOT / 'inputs/hall_three_settings.jsonl'):
        c = json.loads(l)
        cells[c['cell_id']] = c
    occ = [(cid, st, j) for cid, c in cells.items() for st in SETTINGS for j in range(len(c['settings'][st]['atoms']))]
    rng = random.Random(4242)
    pick = rng.sample(occ, 100)
    small = [o for o in occ if len(cells[o[0]]['settings'][o[1]]['atoms']) < 4]
    dups = []
    for o in occ:
        s = cells[o[0]]['settings'][o[1]]
        keys = [a['cache_key'] for a in s['atoms']]
        if keys.count(keys[o[2]]) > 1:
            dups.append(o)
    edge = rng.sample(small, 10) + rng.sample(dups, 6)
    targets = [(o, 'random') for o in pick] + [(o, 'edge_small' if i < 10 else 'edge_dup') for i, o in enumerate(edge)]
    want = {o for o, _ in targets}
    heat = {}
    for line in open(HEAT / 'token_heat.jsonl'):
        r = json.loads(line)
        k = (r['cell_id'], r['setting'], r['bullet'])
        if k in want:
            heat[k] = r
    metrics = {}
    for line in open(ROOT / 'metrics/bullet_metrics.jsonl'):
        m = json.loads(line)
        if any((m['cell_id'], st, j) in want for st in SETTINGS for j in range(4)):
            metrics[m['cell_id']] = m
    vindex = json.load(open(ROOT / 'inputs/hall_vector_index.json'))
    acts = rows_memmap(ACTS, 'resid')
    print('loaded', round(time.time() - t0, 1), 's', flush=True)
    by_layer = collections.defaultdict(list)
    for o, kind in targets:
        by_layer[cells[o[0]]['layer']].append((o, kind))
    rows = []
    for layer in sorted(by_layer):
        tw = time.time()
        w = Whitener.load(WHT.format(layer))
        print('whitener', layer, w.artifact_sha256[:8], round(time.time() - tw, 1), 's', flush=True)
        for (cid, st, j), kind in by_layer[layer]:
            c = cells[cid]
            s = c['settings'][st]
            t_raw = np.array(acts[c['activation_row']])
            assert hashlib.sha256(t_raw.astype('<f4').tobytes()).hexdigest() == c['activation_sha256']
            vecs = {}
            for a in s['atoms']:
                path, row = vindex[c['split']][a['cache_key']]
                vecs[a['source_phrase_id']] = torch.from_numpy(np.array(rows_memmap(path, 'vectors')[row]))
            sc = JointNNLS.from_raw(torch.from_numpy(t_raw), vecs, w, solver='scipy_exact')
            ids = s['phrase_ids']
            assert ids == [a['source_phrase_id'] for a in s['atoms']]
            others = [p for i, p in enumerate(ids) if i != j]
            j0 = sc.score(others) if others else 0.0
            full = sc.score(ids)
            r = heat[(cid, st, j)]
            m = metrics[cid]['settings'][st]
            mb = m['bullets'][j]
            assert mb['phrase_id'] == ids[j]
            rows.append({'cell_id': cid, 'setting': st, 'bullet': j, 'kind': kind, 'layer': layer,
                         'n_bullets': len(ids), 'dup': r['dup_in_readout'],
                         'joint0_raw': j0, 'joint0_heat': r['joint'][0], 'd_joint0': r['joint'][0] - j0,
                         'full_raw': full, 'saved': s['fve'], 'joint_cached': r['joint_cached'],
                         'd_cached': r['joint_cached'] - full, 'd_saved': s['fve'] - full,
                         'loo_raw': full - j0, 'loo_metrics': mb['loo_drop'], 'd_loo': mb['loo_drop'] - (full - j0),
                         'sum_heat': float(np.sum(r['heat'])), 'drift': r['drift'],
                         'sumheat_minus_loo': float(np.sum(r['heat'])) - (full - j0)})
        del w
    for k in ('d_joint0', 'd_cached', 'd_saved', 'd_loo'):
        for kind in ('random', 'edge_small', 'edge_dup'):
            v = [abs(x[k]) for x in rows if x['kind'] == kind]
            print(k, kind, 'n', len(v), 'max', max(v))
    rnd = [x for x in rows if x['kind'] == 'random']
    shl = np.array([x['sumheat_minus_loo'] for x in rnd])
    dr = np.array([x['drift'] for x in rnd])
    out = {'n_random': len(rnd), 'n_edge': len(rows) - len(rnd),
           'max_abs': {k: {kind: max(abs(x[k]) for x in rows if x['kind'] == kind)
                           for kind in ('random', 'edge_small', 'edge_dup')}
                       for k in ('d_joint0', 'd_cached', 'd_saved', 'd_loo')},
           'random_sumheat_minus_loo': {'median_abs': float(np.median(np.abs(shl))), 'max_abs': float(np.abs(shl).max()),
                                        'max_abs_minus_drift': float(np.abs(shl - dr).max())},
           'layers': dict(collections.Counter(x['layer'] for x in rows)),
           'settings': dict(collections.Counter(x['setting'] for x in rows)),
           'seconds': round(time.time() - t0, 1), 'rows': rows}
    (OUT / 'v3_joint0_raw.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))


if __name__ == '__main__':
    main()
