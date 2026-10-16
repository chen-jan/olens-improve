"""A6: whitened identity check of the re-encoded originals (CPU; run after encode_job.py completes).

For every variant_type == 'original' row of variants.jsonl, compare the A6 re-encoded vector (vectors/a6_L*.safetensors)
with the pipeline's cached vector (row['cached_vector'] in data/vectors/a451cf49...), both whitened with the same
pooled whitener the pipeline uses for FVE (olens_improve.reconstruction.Whitener, whitening_iolens_pooled_L{layer},
ridge 0.1). Reports raw and whitened cosine and whitened relative L2, overall and per layer -> vectors/identity_whitened.json.

Run (mit_quicktest; from newtasks/):  $PY -B analysis/a6_swap/whitened_identity.py
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time
from pathlib import Path

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
A6 = NT / 'analysis/a6_swap'
sys.path.insert(0, str(NT / 'code'))
sys.path.insert(0, str(A6))
import ntcommon as C  # noqa: E402

C.setup_paths()
import encode_job as E  # noqa: E402


def main():
    import torch
    from olens_improve.reconstruction import Whitener
    torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '4')))
    t0 = time.time()
    out = A6 / 'vectors'
    man = json.loads((out / 'manifest.json').read_text())
    if man.get('status') != 'complete' or man.get('fake'):
        raise SystemExit('encode manifest is not a complete real run')
    done, _ = E.read_shards(out)
    rows = []
    with open(A6 / 'variants.jsonl') as f:
        for line in f:
            r = json.loads(line)
            if r['variant_type'] == 'original' and r.get('cached_vector'):
                rows.append((r['vector_key'], int(r['layer']), r['family'], r['source_key'], r['cached_vector']))
    by_layer = collections.defaultdict(list)
    for x in rows:
        by_layer[x[1]].append(x)
    res = {'n_originals': len(rows), 'per_layer': {}, 'ridge_c': 0.1, 'whiteners': str(C.WHITENERS)}
    all_wcos, all_rcos, all_wrel, worst = [], [], [], []
    for L in sorted(by_layer):
        xs = by_layer[L]
        missing = [x[0] for x in xs if x[0] not in done]
        if missing:
            raise SystemExit(f'L{L}: {len(missing)} originals not encoded')
        mine = torch.stack(E.read_rows([done[x[0]] for x in xs])).double()
        cached = torch.stack(E.read_rows([x[4] for x in xs])).double()
        wh = Whitener.load(str(C.WHITENERS / f'whitening_iolens_pooled_L{L}.safetensors'))
        wm = wh.whiten(mine.float()).double()
        wc = wh.whiten(cached.float()).double()
        rcos = torch.nn.functional.cosine_similarity(mine, cached, dim=1).tolist()
        wcos = torch.nn.functional.cosine_similarity(wm, wc, dim=1).tolist()
        wrel = ((wm - wc).norm(dim=1) / wc.norm(dim=1).clamp_min(1e-12)).tolist()
        fam = collections.defaultdict(list)
        for x, c in zip(xs, wcos):
            fam[x[2]].append(c)
        res['per_layer'][str(L)] = {'n': len(xs), 'whitened_cos': E.summary(wcos), 'raw_cos': E.summary(rcos),
                                    'whitened_rel_l2': E.summary(wrel),
                                    'whitened_cos_min_by_family': {k: min(v) for k, v in sorted(fam.items())},
                                    'whitener_sha256': wh.artifact_sha256}
        all_wcos += wcos
        all_rcos += rcos
        all_wrel += wrel
        worst += [{'vector_key': x[0], 'layer': L, 'family': x[2], 'source_key': x[3], 'whitened_cos': c, 'raw_cos': rc,
                   'whitened_rel_l2': w} for x, c, rc, w in zip(xs, wcos, rcos, all_wrel[-len(xs):])]
        print(f'L{L}: n={len(xs)} whitened cos min {min(wcos):.6f} median {res["per_layer"][str(L)]["whitened_cos"]["median"]:.6f}'
              f' | raw cos min {min(rcos):.6f}', flush=True)
    res['whitened_cos'] = E.summary(all_wcos)
    res['raw_cos'] = E.summary(all_rcos)
    res['whitened_rel_l2'] = E.summary(all_wrel)
    res['n_whitened_cos_below_0.999'] = sum(c < .999 for c in all_wcos)
    res['n_whitened_cos_below_0.99'] = sum(c < .99 for c in all_wcos)
    res['worst'] = sorted(worst, key=lambda d: d['whitened_cos'])[:20]
    res['seconds'] = round(time.time() - t0, 1)
    E.atomic_json(out / 'identity_whitened.json', res)
    print(f'all: n={len(all_wcos)} whitened cos min {res["whitened_cos"]["min"]:.6f} median '
          f'{res["whitened_cos"]["median"]:.6f}; {res["n_whitened_cos_below_0.999"]} below 0.999; {res["seconds"]}s')


if __name__ == '__main__':
    main()
