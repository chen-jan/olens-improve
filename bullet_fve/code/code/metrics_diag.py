"""Diagnostic for why LOO drop never exceeds solo FVE: within-readout geometry of whitened unit bullet
directions and a full diminishing-returns (submodularity) check of v(S) = NNLS FVE over all subset pairs.

Usage: python -B metrics_diag.py --layer L --summary logs/metrics_diag.L{L}.json   (one layer per job; ~30 s)
"""
import argparse
import collections
import hashlib
import itertools
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import torch  # noqa: E402
from metrics_job import ACTS, INPUTS, SETTINGS, WHITENERS, JointNNLS, Whitener, rows_memmap  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layer', type=int, required=True)
    ap.add_argument('--summary', required=True)
    args = ap.parse_args()
    torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '4')))
    t0 = time.time()
    cells = [c for c in map(json.loads, open(INPUTS / 'hall_three_settings.jsonl')) if c['layer'] == args.layer]
    vindex = json.load(open(INPUTS / 'hall_vector_index.json'))
    acts = rows_memmap(ACTS, 'resid')
    w = Whitener.load(f'{WHITENERS}/whitening_iolens_pooled_L{args.layer}.safetensors')
    need = sorted({(c['split'], a['cache_key']) for c in cells for s in c['settings'].values() for a in s['atoms']})
    by_file = collections.defaultdict(list)
    for split, key in need:
        path, row = vindex[split][key]
        by_file[path].append((row, (split, key)))
    unit = {}
    for path, items in by_file.items():
        mm = rows_memmap(path, 'vectors')
        rows = sorted(items)
        x = w.whiten(torch.from_numpy(np.asarray(mm[[r for r, _ in rows]])))
        x = x / (x.norm(dim=1, keepdim=True) + 1e-9)
        unit.update({sk: x[i] for i, (_, sk) in enumerate(rows)})

    st = collections.Counter()
    pair_cos, tgt_cos = [], []
    worst_sub = (0.0, None)
    neg_pair_examples = []
    for c in cells:
        tr = torch.from_numpy(np.asarray(acts[c['activation_row']]).copy())
        assert hashlib.sha256(tr.numpy().tobytes()).hexdigest() == c['activation_sha256']
        t = w.whiten(tr.reshape(1, -1))[0]
        tn = t / t.norm()
        for sid in SETTINGS:
            s = c['settings'][sid]
            ids = s['phrase_ids']
            if not ids:
                continue
            vecs = {a['source_phrase_id']: unit[(c['split'], a['cache_key'])] for a in s['atoms']}
            V = torch.stack([vecs[i] for i in ids]).double()
            G = V @ V.T
            for i, j in itertools.combinations(range(len(ids)), 2):
                pair_cos.append(float(G[i, j]))
                if G[i, j] < 0 and len(neg_pair_examples) < 5:
                    neg_pair_examples.append([c['cell_id'], sid, i, j, float(G[i, j])])
            tgt_cos.extend((V @ tn.double()).tolist())
            sc = JointNNLS(t, vecs, solver='scipy_exact')
            n = len(ids)
            v = {sub: (sc.score([ids[k] for k in sub]) if sub else 0.0)
                 for r in range(n + 1) for sub in itertools.combinations(range(n), r)}
            # diminishing returns: for every i, S subset T (both without i): gain(i|S) >= gain(i|T)
            for i in range(n):
                others = [k for k in range(n) if k != i]
                subs = [sub for r in range(n) for sub in itertools.combinations(others, r)]
                for S in subs:
                    gS = v[tuple(sorted(S + (i,)))] - v[S]
                    for T in subs:
                        if len(T) > len(S) and set(S) <= set(T):
                            gT = v[tuple(sorted(T + (i,)))] - v[T]
                            st['sub_pairs'] += 1
                            if gT > gS + 1e-9:
                                st['sub_violations'] += 1
                                if gT - gS > worst_sub[0]:
                                    worst_sub = (gT - gS, [c['cell_id'], sid, i, list(S), list(T), gS, gT])
            st['readouts'] += 1
    pc, tc = np.array(pair_cos), np.array(tgt_cos)
    summary = {
        'layer': args.layer, 'job': os.environ.get('SLURM_JOB_ID'), 'readouts': st['readouts'],
        'bullet_pairs': int(pc.size), 'pair_cos_min': float(pc.min()), 'pair_cos_p01': float(np.quantile(pc, 0.01)),
        'pair_cos_median': float(np.median(pc)), 'pair_cos_neg_frac': float((pc < 0).mean()),
        'pair_cos_neg_count': int((pc < 0).sum()), 'neg_pair_examples': neg_pair_examples,
        'bullet_target_cos_min': float(tc.min()), 'bullet_target_cos_median': float(np.median(tc)),
        'bullet_target_cos_neg_count': int((tc < 0).sum()), 'bullets': int(tc.size),
        'submodularity_pairs_checked': st['sub_pairs'], 'submodularity_violations_gt_1e-9': st['sub_violations'],
        'worst_violation': worst_sub, 'seconds': round(time.time() - t0, 1),
    }
    json.dump(summary, open(args.summary, 'w'), indent=1)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
