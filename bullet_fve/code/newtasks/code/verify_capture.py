"""Verify the production capture (CPU): identity, hashes, finiteness, norms, smoke cross-check.

Checks (any failure -> exit 1):
  - capture_state.json complete; capture_audit.json / fresh_manifest.json / safetensors metadata all carry
    the sha256 of data/manifests/capture.json;
  - activations.safetensors 'resid' is F32 [n_cells, 5120], all finite, no all-zero row;
  - row i of the tensor is manifest cell i (cell_id, layer, position), adapter_disabled, fresh_recapture,
    not imported; sha256(row fp32 bytes) == audit activation_sha256 (the hash gen_worker re-checks);
  - each item's rendered ids have the n_tokens of design/sites.jsonl and rel_from_end = n-1-pos;
  - smoke cross-check: every cell also captured in the smoke run is compared (max |diff|, cosine).
Reports norms per family x layer, per (family, layer, rel_from_end), and outliers (> 5x the layer median).
Writes data/capture/verify_capture.json.  Usage: python -B verify_capture.py [--smoke-root data/smoke]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke-root', default=str(C.NT / 'data/smoke'))
    args = ap.parse_args()
    import torch
    from safetensors import safe_open
    cap = C.DATA / 'capture'
    man_path = C.DATA / 'manifests/capture.json'
    man_sha = C.file_sha(man_path)
    manifest = json.loads(man_path.read_text())
    state = json.loads((cap / 'capture_state.json').read_text())
    audit = json.loads((cap / 'capture_audit.json').read_text())
    fresh = json.loads((cap / 'fresh_manifest.json').read_text())
    fails = []

    def need(cond, msg):
        if not cond:
            fails.append(msg)

    need(state.get('status') == 'complete', f'state {state.get("status")}')
    for name, v in (('state', state['manifest_sha256']), ('audit', audit['manifest_sha256'])):
        need(v == man_sha, f'{name} manifest sha {v} != {man_sha}')
    cells = manifest['cells']
    n = len(cells)
    need(len(audit['cells']) == n and len(fresh['cells']) == n, 'row counts differ')
    with safe_open(str(cap / 'activations.safetensors'), framework='pt') as f:
        meta = f.metadata()
        X = f.get_tensor('resid')
    need(meta.get('manifest_sha256') == man_sha, 'tensor metadata manifest sha')
    need(meta.get('capture_adapter') == 'disabled', 'tensor metadata capture_adapter')
    need(X.dtype == torch.float32 and tuple(X.shape) == (n, 5120), f'tensor {X.dtype} {tuple(X.shape)}')
    need(bool(torch.isfinite(X).all()), 'non-finite values')
    norms = X.norm(dim=1)
    need(int((norms == 0).sum()) == 0, 'all-zero rows')
    bad_hash = 0
    shas = collections.Counter()
    for i, (c, a) in enumerate(zip(cells, audit['cells'])):
        if (a['cell_id'], a['layer'], a['position']) != (c['cell_id'], c['layer'], c['position']):
            fails.append(f'row {i} identity {a["cell_id"]} != {c["cell_id"]}')
            continue
        if a['activation_row'] != i or not a['activation_tensor_path'].endswith('activations.safetensors'):
            fails.append(f'row {i} tensor pointer')
        if a['adapter_disabled'] is not True or a['generation_activation_source'] != 'fresh_recapture' \
                or a['imported_instrument_vector']:
            fails.append(f'row {i} provenance')
        h = hashlib.sha256(X[i].numpy().tobytes()).hexdigest()
        shas[h] += 1
        if h != a['activation_sha256']:
            bad_hash += 1
    need(bad_hash == 0, f'{bad_hash} row hashes differ from the audit')
    dup_rows = sum(v for v in shas.values() if v > 1)
    # render lengths vs design/sites.jsonl
    sites = {(r['family'], r['id']): r for r in C.load_sites()}
    renders = {r['capture_spec_sha256']: r for r in audit['renders']}
    n_items = 0
    for a, c in zip(audit['cells'], cells):
        r = renders[a['capture_spec_sha256']]
        s = sites[(c['family'], c['item_id'])]
        if len(r['input_ids']) != s['n_tokens'] or c['rel_from_end'] != s['n_tokens'] - 1 - c['position']:
            fails.append(f'render length / rel_from_end {c["cell_id"]}')
    n_items = len(renders)
    need(n_items == 200, f'{n_items} rendered items')
    # norms
    by_fl = collections.defaultdict(list)
    by_role = collections.defaultdict(list)
    for c, v in zip(cells, norms.tolist()):
        by_fl[(C.SHORT[c['family']], c['layer'])].append(v)
        by_role[(C.SHORT[c['family']], c['layer'], c['rel_from_end'])].append((v, c['token']))
    fl = {f'{f}|L{L}': {'n': len(v), 'min': round(min(v), 2), 'median': round(statistics.median(v), 2),
                        'max': round(max(v), 2)} for (f, L), v in sorted(by_fl.items())}
    role = {}
    for (f, L, rel), vs in sorted(by_role.items()):
        toks = collections.Counter(t for _, t in vs).most_common(2)
        role[f'{f}|L{L}|rel{rel}'] = {'n': len(vs), 'median': round(statistics.median(v for v, _ in vs), 2),
                                      'top_tokens': toks}
    outliers = []
    for c, v in zip(cells, norms.tolist()):
        med = statistics.median(by_fl[(C.SHORT[c['family']], c['layer'])])
        if v > 5 * med or v < med / 5:
            outliers.append({'cell_id': c['cell_id'], 'token': c['token'], 'rel_from_end': c['rel_from_end'],
                             'norm': round(v, 1), 'layer_median': round(med, 1)})
    # smoke cross-check
    smoke = {}
    sroot = Path(args.smoke_root) / 'capture'
    if (sroot / 'capture_audit.json').exists():
        sa = json.loads((sroot / 'capture_audit.json').read_text())
        with safe_open(str(sroot / 'activations.safetensors'), framework='pt') as f:
            S = f.get_tensor('resid')
        row_of = {c['cell_id']: i for i, c in enumerate(cells)}
        diffs, coss, same_hash = [], [], 0
        for j, a in enumerate(sa['cells']):
            i = row_of.get(a['cell_id'])
            if i is None:
                continue
            d = (X[i] - S[j]).abs().max().item()
            diffs.append(d)
            coss.append(torch.nn.functional.cosine_similarity(X[i], S[j], dim=0).item())
            same_hash += a['activation_sha256'] == audit['cells'][i]['activation_sha256']
        smoke = {'overlap_cells': len(diffs), 'identical_hash': same_hash,
                 'max_abs_diff': max(diffs) if diffs else None, 'min_cosine': min(coss) if coss else None}
        need(not diffs or min(coss) > 0.999, f'smoke cross-check cosine {min(coss) if coss else None}')
    out = {'ok': not fails, 'fails': fails[:50], 'n_fails': len(fails), 'cells': n, 'items': n_items,
           'manifest_sha256': man_sha, 'tensor_sha256': C.file_sha(cap / 'activations.safetensors'),
           'tensor_shape': list(X.shape), 'tensor_dtype': str(X.dtype), 'row_hash_mismatches': bad_hash,
           'duplicate_rows': dup_rows,
           'cells_by_family': dict(collections.Counter(C.SHORT[c['family']] for c in cells)),
           'norms_by_family_layer': fl, 'outliers_5x': {'n': len(outliers), 'rows': outliers[:40]},
           'norms_by_role': role, 'smoke_cross_check': smoke}
    C.atomic_json(cap / 'verify_capture.json', out)
    print(json.dumps({k: v for k, v in out.items() if k != 'norms_by_role'}, indent=1, default=str))
    sys.exit(0 if out['ok'] else 1)


if __name__ == '__main__':
    main()
