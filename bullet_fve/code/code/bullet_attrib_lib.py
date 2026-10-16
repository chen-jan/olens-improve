"""Read-only helpers for per-bullet FVE attribution on WorkspaceBench Hallucination (chat).

Reuses olens-improve code (JointNNLS, Whitener, read_arm, render convention). Writes nothing.
Run heavy loops inside a Slurm CPU allocation, not on the shared node.
"""
import itertools
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

P = Path('${OLENS_REPO_ROOT}')
sys.path.insert(0, str(P / 'src'))
sys.path.insert(0, str(P / 'scripts'))

F = Path('${OLENS_COMPUTE_ROOT}')
D = Path('${OLENS_DATA_ROOT}')
FRESH_MANIFEST = F / 'activations/core-v1/fresh_manifest_v2.json'
WHITENERS = F / ('cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/'
                 '5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners')
JUDGMENTS = D / 'expansion-v1/judgments'
STAGE_SELECTIONS = {  # == configs/expansion_manifest_v1.json stages[*].selectors.path / vector_cache
    'development': (D / 'selections/development-full-grid-v4/merged/selections.jsonl',
                    F / 'vectors/shared-global-v1/a451cf49d28ac7447722'),
    'validation': (D / 'selections/validation-full-grid-v1/merged/selections.jsonl',
                   F / 'vectors/validation-catalog-v1'),
    'test': (D / 'selections/test-full-grid-v1/merged/selections.jsonl',
             F / 'vectors/test-catalog-v1'),
}
SETTINGS = {  # (method, n) in stage selections -> (expansion condition id, display label)
    ('capped_n1', 1): ('capped_n1-n1', 'Original, capped to four bullets'),
    ('best_n_exact', 32): ('best_n_exact-n32', 'Choose the best complete readout (32 samples)'),
    ('pooled_greedy_swap', 32): ('pooled_greedy_swap-n32', 'Combine original bullets (32 samples)'),
}
HALL_PREFIX = '{"cell_id": "hallucination|'


def iter_hall_rows(selections_path):
    """Stream one stage selections.jsonl; json-parse only hallucination rows (lines are ~250 KB)."""
    with open(selections_path) as fh:
        for line in fh:
            if line.startswith(HALL_PREFIX):
                yield json.loads(line)


def chosen(row):
    """{(method,n): selection} for the three settings; each has text, phrase_ids, atoms[cache_key,...], fits.exact."""
    return {(s['method'], s['n']): s for s in row['selections'] if (s['method'], s['n']) in SETTINGS}


def locate(vector_cache_dir, needed_keys):
    """cache_key -> (tensor_path,row) for needed keys only (lean RawVectorCache.index replacement)."""
    d = Path(vector_cache_dir)
    contract = json.loads((d / 'contract.json').read_text())
    found = {}
    for p in sorted(d.glob('raw_*.index.json')):
        info = json.loads(p.read_text())
        assert info['contract_sha256'] == contract['sha256']
        for r in info['vectors']:
            if r['cache_key'] in needed_keys:
                assert r['cache_key'] not in found, 'duplicate cache key'
                found[r['cache_key']] = (info['tensor_path'], r['row'])
    missing = set(needed_keys) - set(found)
    if missing:
        raise KeyError(f'{len(missing)} cache keys missing from {d}')
    return found


def load_vectors(found):
    """Read each safetensors shard once; cache_key -> raw 5120-d float32 AR prediction."""
    from safetensors import safe_open
    by_path = defaultdict(list)
    for k, (path, row) in found.items():
        by_path[path].append((row, k))
    out = {}
    for path, rows in by_path.items():
        with safe_open(path, framework='pt', device='cpu') as f:
            sl = f.get_slice('vectors')
            for row, k in rows:
                out[k] = sl[row:row + 1][0].clone()
    return out


def target_activation(cell):
    """Fresh adapter-off activation row for a fresh-manifest cell, hash-checked."""
    import hashlib
    from safetensors import safe_open
    with safe_open(cell['activation_tensor_path'], framework='pt', device='cpu') as f:
        raw = f.get_slice(cell['activation_tensor_key'])[cell['activation_row']:cell['activation_row'] + 1][0]
    assert hashlib.sha256(raw.numpy().tobytes()).hexdigest() == cell['activation_sha256']
    return raw


def bullet_metrics(scorer, ids):
    """Joint FVE, solo FVE, leave-one-out drop and exact Shapley value per bullet (<=4 bullets -> <=16 fits).

    v(S) = JointNNLS FVE of subset S (v(empty)=0). NNLS FVE is monotone in S, so solo, LOO and
    Shapley are all >= 0 and Shapley values sum exactly to the joint FVE (efficiency).
    """
    ids = tuple(ids)
    if not ids:
        return {'joint_fve': 0.0, 'bullets': []}
    def v(subset):
        subset = tuple(x for x in ids if x in subset)  # keep emitted order -> stable cache key
        return scorer.score(subset) if subset else 0.0
    joint = v(ids)
    n = len(ids)
    rows = []
    for b in ids:
        rest = [x for x in ids if x != b]
        shap = 0.0
        for k in range(n):
            w = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
            for S in itertools.combinations(rest, k):
                shap += w * (v(set(S) | {b}) - v(set(S)))
        rows.append({'phrase_id': b, 'solo_fve': v({b}), 'loo_drop': joint - v(set(rest)),
                     'shapley': shap, 'shapley_share': shap / joint if joint > 0 else None})
    return {'joint_fve': joint, 'bullets': rows}


def render_offsets(bullet_texts):
    """Char ranges of each bullet body inside selection.render_bullets(...) output (the judged text)."""
    out, ranges = '', []
    for t in bullet_texts:
        if out and not out.endswith('\n'):
            out += '\n'
        out += '- '
        ranges.append((len(out), len(out) + len(t)))
        out += t
    return out, ranges


def locate_spans(text, spans, kind):
    """All exact occurrences of each judge span; unlocated spans are returned with start=None."""
    hits = []
    for s in spans or []:
        starts, i = [], text.find(s) if s else -1
        while i >= 0:
            starts.append(i)
            i = text.find(s, i + 1)
        if not starts:
            hits.append({'kind': kind, 'span': s, 'start': None, 'end': None, 'occurrences': 0})
        for st in starts:
            hits.append({'kind': kind, 'span': s, 'start': st, 'end': st + len(s), 'occurrences': len(starts)})
    return hits


def read_site_context(bank_item, position, before=400, after=120):
    """Chat context around the read token. sites[pos]['char'] is the EXCLUSIVE end offset of the
    read token inside bank_item['response'] (verified for all 5,615 hallucination cells)."""
    site = {s['pos']: s for s in bank_item['sites']}[position]
    r, end = bank_item['response'], site['char']
    start = end - len(site['token'])
    assert r[start:end] == site['token']
    return {'prompt': bank_item['prompt'], 'before': r[max(0, start - before):start],
            'token': site['token'], 'after': r[end:end + after], 'site_kind': site['kind'],
            'char_start': start, 'char_end': end, 'response_len': len(r)}
