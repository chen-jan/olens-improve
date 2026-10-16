"""Independent CPU verification of per-token heat records (does NOT import token_heat.py).

Usage: python -B verify_token_heat_cpu.py [--merged]
  default : verify the finished chunk files in heat/work/chunks (+ their .sample.pt)
  --merged: verify heat/token_heat.jsonl + heat/verify_sample.pt (after `token_heat.py merge`)
Writes logs/verify_token_heat_cpu.json.
"""
import argparse
import collections
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import nnls

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
INP = ROOT / 'inputs'
HEAT = ROOT / 'heat'
CHUNKS = HEAT / 'work' / 'chunks'
PROJECT = Path('${OLENS_REPO_ROOT}')
ACTS = '${OLENS_COMPUTE_ROOT}/activations/core-v1/activations.safetensors'
WHITENERS = ('${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/'
             'snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners/'
             'whitening_iolens_pooled_L{}.safetensors')
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
TOL = 1e-6
T0 = time.time()


def log(*a):
    print(f'[{time.time() - T0:6.1f}s]', *a, flush=True)


def rows_memmap(path, key):
    with open(path, 'rb') as f:
        n = int.from_bytes(f.read(8), 'little')
        h = json.loads(f.read(n))
    return np.memmap(path, dtype='<f4', mode='r', offset=8 + n + h[key]['data_offsets'][0],
                     shape=tuple(h[key]['shape']))


def fve_scipy(X, t):
    """X [m,D] float64 columns-as-rows, t [D] float64. FVE = 1 - |t - X^T c|^2/|t|^2, c = nnls."""
    if X.shape[0] == 0:
        return 0.0
    _, r = nnls(X.T, t)
    return 1.0 - r * r / float(t @ t)


def q(x):
    x = np.asarray(x, float)
    if x.size == 0:
        return None
    return {'n': int(x.size), 'min': float(x.min()), 'median': float(np.median(x)),
            'p90': float(np.quantile(x, .9)), 'p99': float(np.quantile(x, .99)), 'max': float(x.max()),
            'mean': float(x.mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--merged', action='store_true')
    ap.add_argument('--n-from-raw', type=int, default=50)
    args = ap.parse_args()
    torch.set_num_threads(8)
    sys.path.insert(0, str(PROJECT / 'src'))
    from olens_improve.reconstruction import JointNNLS, Whitener

    out = {'mode': 'merged' if args.merged else 'chunks', 'issues': []}

    # ------------------------------------------------------------ load records
    if args.merged:
        files = [HEAT / 'token_heat.jsonl']
        sample_files = [HEAT / 'verify_sample.pt']
    else:
        files = sorted(CHUNKS.glob('*.jsonl'))
        sample_files = sorted(CHUNKS.glob('*.sample.pt'))
    recs = []
    for fp in files:
        for line in open(fp):
            if line.strip():
                recs.append(json.loads(line))
    out['files'] = [str(f) for f in files]
    out['n_records'] = len(recs)
    log('records', len(recs), [f.name for f in files])

    cells = {}
    for line in open(INP / 'hall_three_settings.jsonl'):
        c = json.loads(line)
        cells[c['cell_id']] = c
    vindex = json.load(open(INP / 'hall_vector_index.json'))

    # ------------------------------------------------------------ coverage
    covered_chunks = sorted({(r['layer'], r['split']) for r in recs})
    expected = set()
    n_empty = 0
    for c in cells.values():
        if (c['layer'], c['split']) not in covered_chunks:
            continue
        for st in SETTINGS:
            atoms = c['settings'][st]['atoms']
            if not atoms:
                n_empty += 1
            for j in range(len(atoms)):
                expected.add((c['cell_id'], st, j))
    got = [(r['cell_id'], r['setting'], r['bullet']) for r in recs]
    dupl = [k for k, v in collections.Counter(got).items() if v > 1]
    all_atoms = sum(len(c['settings'][st]['atoms']) for c in cells.values() for st in SETTINGS)
    out['coverage'] = {'chunks_present': [f'L{l}_{s}' for l, s in covered_chunks],
                       'expected_occurrences_in_present_chunks': len(expected),
                       'records': len(got), 'missing': len(expected - set(got)),
                       'extra': len(set(got) - expected), 'duplicates': len(dupl),
                       'empty_readouts_in_present_chunks': n_empty,
                       'all_atoms_full_dataset': all_atoms}
    if expected != set(got) or dupl:
        out['issues'].append(f'coverage mismatch: missing {len(expected - set(got))} extra {len(set(got) - expected)} dup {len(dupl)}')
    if args.merged and len(recs) != all_atoms:
        out['issues'].append(f'merged line count {len(recs)} != non-empty atom count {all_atoms}')
    log('coverage', out['coverage'])

    # ------------------------------------------------------------ structural / numeric per record
    from transformers import AutoTokenizer
    rt = json.loads((PROJECT / 'configs/runtime.json').read_text())
    tok = AutoTokenizer.from_pretrained(rt['paths']['base_snapshot'], local_files_only=True)

    bad = collections.Counter()
    examples = collections.defaultdict(list)
    tele, cached_saved, drift_signed, drift_fieldchk, heat_round = [], [], [], [], []
    loo_vs_metrics, joint_cached_vs_metrics_recomp, solo_n_vs_metrics = [], [], []
    nonstrict_ends, nonstrict_explained = 0, 0
    empty_pieces = 0
    tokens = 0
    drift_by = collections.defaultdict(list)
    dup_heat = []
    decode_end_mismatch = 0
    single_tok_decode_mismatch = 0
    single_tok_mismatch_explained = 0
    ends_last_vs_len = collections.Counter()

    # metrics (independent CPU path) for LOO cross-check
    metrics = {}
    for layer in sorted({r['layer'] for r in recs}):
        for line in open(ROOT / 'metrics' / f'bullet_metrics.L{layer}.jsonl'):
            m = json.loads(line)
            for st, s in m['settings'].items():
                for j, b in enumerate(s['bullets']):
                    metrics[(m['cell_id'], st, j)] = (b, s)

    def flag(kind, r, detail=''):
        bad[kind] += 1
        if len(examples[kind]) < 3:
            examples[kind].append(f"{r['cell_id']}|{r['setting']}|b{r['bullet']} {detail}")

    for r in recs:
        c = cells[r['cell_id']]
        s = c['settings'][r['setting']]
        a = s['atoms'][r['bullet']]
        text = a['scored_text']
        ids = a['scored_token_ids']
        n = r['n_scored']
        tokens += n
        # identity
        if r['phrase_id'] != a['source_phrase_id']: flag('phrase_id', r)
        if r['cache_key'] != a['cache_key']: flag('cache_key', r)
        if n != len(ids): flag('n_scored_vs_atom', r, f'{n} vs {len(ids)}')
        if bool(r['truncated']) != bool(a['truncated']): flag('truncated', r)
        if r['n_bullets'] != len(s['atoms']): flag('n_bullets', r)
        if r['layer'] != c['layer'] or r['split'] != c['split']: flag('layer_split', r)
        keys = [x['cache_key'] for x in s['atoms']]
        if bool(r['dup_in_readout']) != (keys.count(a['cache_key']) > 1): flag('dup_flag', r)
        # lengths
        L = {len(r['heat']), len(r['solo']), len(r['ends_in_scored_text']), len(r['pieces']), len(r['joint']) - 1}
        if L != {n}: flag('lengths', r, str(L))
        ends = r['ends_in_scored_text']
        # ends
        if any(ends[k] < ends[k - 1] for k in range(1, len(ends))) or (ends and ends[0] < 0):
            flag('ends_decreasing', r)
        strict = all(ends[k] > ends[k - 1] for k in range(1, len(ends))) and (not ends or ends[0] > 0)
        if ends and ends[-1] > len(text): flag('ends_beyond_text', r, f'{ends[-1]} > {len(text)}')
        if ends:
            ends_last_vs_len[('trunc' if a['truncated'] else 'full',
                              'eq' if ends[-1] == len(text) else 'lt')] += 1
        # pieces vs ends
        prev = 0
        for k, e in enumerate(ends):
            if r['pieces'][k] != text[prev:e]:
                flag('piece_vs_slice', r, f'k={k}')
                break
            prev = e
        if ''.join(r['pieces']) != text[:ends[-1] if ends else 0]: flag('pieces_concat', r)
        empty_pieces += sum(1 for p in r['pieces'] if p == '')
        # independent ends: decode(ids[:k]), strip trailing U+FFFD of an incomplete char
        my_ends = []
        okdec = True
        for k in range(1, n + 1):
            sdec = tok.decode(ids[:k], clean_up_tokenization_spaces=False)
            while not text.startswith(sdec) and sdec.endswith('�'):
                sdec = sdec[:-1]
            if not text.startswith(sdec):
                okdec = False
                break
            my_ends.append(len(sdec))
        if not okdec or my_ends != ends:
            decode_end_mismatch += 1
            if len(examples['decode_ends_mismatch']) < 5:
                examples['decode_ends_mismatch'].append(
                    f"{r['cell_id']}|{r['setting']}|b{r['bullet']} ok={okdec} mine={my_ends[:40]} rec={ends[:40]}")
        if not strict:
            nonstrict_ends += 1
        # per-token piece vs decode([id]); a mismatch must be a token that is part of a multi-byte split
        expl_all = True
        for k in range(n):
            single = tok.decode([ids[k]], clean_up_tokenization_spaces=False)
            if single != r['pieces'][k]:
                single_tok_decode_mismatch += 1
                partial = '�' in single or r['pieces'][k] == '' or (k + 1 < n and r['pieces'][k + 1] == '') \
                    or (k > 0 and r['pieces'][k - 1] == '') or (k > 0 and '�' in tok.decode([ids[k - 1]]))
                if partial:
                    single_tok_mismatch_explained += 1
                else:
                    expl_all = False
                    if len(examples['single_token_piece_mismatch']) < 5:
                        examples['single_token_piece_mismatch'].append(
                            f"{r['cell_id']}|{r['setting']}|b{r['bullet']} k={k} decode={single!r} piece={r['pieces'][k]!r}")
        if not strict and expl_all:
            nonstrict_explained += 1
        # numbers
        j = np.array(r['joint'], float)
        h = np.array(r['heat'], float)
        so = np.array(r['solo'], float)
        heat_round.append(float(np.abs(h - np.round(np.diff(j), 7)).max()) if n else 0.0)
        tele.append(abs(h.sum() - (j[-1] - j[0])))
        cached_saved.append(abs(r['joint_cached'] - s['fve']))
        if abs(r['readout_fve_saved'] - s['fve']) > 1e-7: flag('readout_fve_saved_field', r)
        d = j[-1] - r['joint_cached']
        drift_signed.append(d)
        drift_fieldchk.append(abs(d - r['drift']))
        drift_by['setting=' + r['setting']].append(abs(d))
        drift_by['truncated=' + str(bool(a['truncated']))].append(abs(d))
        drift_by['dup=' + str(bool(r['dup_in_readout']))].append(abs(d))
        if r['dup_in_readout']:
            dup_heat.append(float(np.abs(h).max()))
        # invariants: NNLS over a superset of columns can only fit better
        if (j[1:] < j[0] - 2e-7).any(): flag('joint_k_below_joint0', r, f'{(j[1:] - j[0]).min():.2e}')
        if (j[1:] < so - 2e-7).any(): flag('joint_k_below_solo_k', r, f'{(j[1:] - so).min():.2e}')
        if r['joint_cached'] < j[0] - 2e-7: flag('joint_cached_below_joint0', r)
        if (so < 0).any() or (so > 1).any() or (j < 0).any() or (j > 1).any(): flag('range', r)
        # cross-check with independent metrics run (LOO drop of the cached vector)
        mb = metrics.get((r['cell_id'], r['setting'], r['bullet']))
        if mb is None:
            flag('metrics_missing', r)
        else:
            b, ms = mb
            if b['phrase_id'] != r['phrase_id']: flag('metrics_phrase', r)
            loo_vs_metrics.append(abs((r['joint_cached'] - j[0]) - b['loo_drop']))
            joint_cached_vs_metrics_recomp.append(abs(r['joint_cached'] - ms['joint_fve_recomputed']))
            solo_n_vs_metrics.append(so[-1] - b['solo_fve'])

    tele = np.array(tele); cached_saved = np.array(cached_saved); drift_signed = np.array(drift_signed)
    for name, arr in (('telescoping', tele), ('joint_cached_vs_saved', cached_saved),
                      ('heat_vs_rounded_diff_joint', np.array(heat_round)),
                      ('drift_field_vs_recomputed', np.array(drift_fieldchk)),
                      ('loo_vs_metrics', np.array(loo_vs_metrics)),
                      ('joint_cached_vs_metrics_recomputed', np.array(joint_cached_vs_metrics_recomp))):
        nbad = int((arr >= TOL).sum())
        out.setdefault('checks', {})[name] = {'max': float(arr.max()), 'n_ge_1e-6': nbad}
        if nbad:
            out['issues'].append(f'{name}: {nbad} records >= 1e-6 (max {arr.max():.3g})')
    out['scored_tokens'] = tokens
    out['structural_failures'] = dict(bad)
    out['structural_examples'] = {k: v for k, v in examples.items()}
    for k, v in bad.items():
        out['issues'].append(f'structural {k}: {v}')
    out['ends'] = {'records_not_strictly_increasing': nonstrict_ends,
                   'of_which_all_offending_tokens_are_multibyte_splits': nonstrict_explained,
                   'empty_pieces_total': empty_pieces,
                   'ends_last_vs_len_scored_text': {f'{a_}/{b_}': v for (a_, b_), v in ends_last_vs_len.items()},
                   'independent_decode_ends_mismatch_records': decode_end_mismatch,
                   'tokens_where_decode_single_id_ne_piece': single_tok_decode_mismatch,
                   'of_which_multibyte_split': single_tok_mismatch_explained}
    if decode_end_mismatch:
        out['issues'].append(f'independent decode-derived ends differ for {decode_end_mismatch} records')
    if single_tok_decode_mismatch != single_tok_mismatch_explained:
        out['issues'].append(f'{single_tok_decode_mismatch - single_tok_mismatch_explained} token pieces differ '
                             'from decode([id]) without a multi-byte split')
    out['drift'] = {'abs': q(np.abs(drift_signed)), 'signed': q(drift_signed),
                    'n_abs_ge_1e-3': int((np.abs(drift_signed) >= 1e-3).sum()),
                    'by': {k: q(v) for k, v in sorted(drift_by.items())}}
    out['dup_in_readout'] = {'n': len(dup_heat), 'max_abs_heat': q(dup_heat)}
    out['solo_n_minus_metrics_solo_cached'] = q(np.abs(solo_n_vs_metrics)) if solo_n_vs_metrics else None
    log('structural done', dict(bad), out['checks'])

    # ------------------------------------------------------------ whitener + raw data (independent path)
    layers = sorted({r['layer'] for r in recs})
    W = {}
    for layer in layers:
        W[layer] = Whitener.load(WHITENERS.format(layer))
        cache_pt = HEAT / 'work' / f'whitener_L{layer}.pt'
        if cache_pt.exists():  # the GPU agent's cached copy should equal a fresh load
            d = torch.load(cache_pt, weights_only=True)
            out.setdefault('whitener_cache_vs_fresh', {})[f'L{layer}'] = {
                'mu_maxabs': float((d['mu'] - W[layer].mu).abs().max()),
                'w_maxabs': float((d['w'] - W[layer].w).abs().max()), 'sha_equal': d['sha'] == W[layer].artifact_sha256}
        log('whitener', layer, W[layer].artifact_sha256[:12])
    acts = rows_memmap(ACTS, 'resid')

    def raw_vec(split, key):
        path, row = vindex[split][key]
        return np.array(rows_memmap(path, 'vectors')[row])

    def raw_target(c):
        t = np.array(acts[c['activation_row']])
        assert hashlib.sha256(t.astype('<f4').tobytes()).hexdigest() == c['activation_sha256']
        return t

    # (a) 50 random occurrences through JointNNLS.from_raw (project recipe, CPU)
    rng = random.Random(20261015)
    pick = rng.sample(recs, min(args.n_from_raw, len(recs)))
    fr = []
    for r in pick:
        c = cells[r['cell_id']]
        s = c['settings'][r['setting']]
        vecs = {a['source_phrase_id']: torch.from_numpy(raw_vec(c['split'], a['cache_key'])) for a in s['atoms']}
        sc = JointNNLS.from_raw(torch.from_numpy(raw_target(c)), vecs, W[c['layer']], solver='scipy_exact')
        others = [a['source_phrase_id'] for i, a in enumerate(s['atoms']) if i != r['bullet']]
        j0 = sc.score(others) if others else 0.0
        jall = sc.score([a['source_phrase_id'] for a in s['atoms']])
        fr.append({'id': f"{r['cell_id']}|{r['setting']}|b{r['bullet']}", 'n_others': len(others),
                   'joint0_rec': r['joint'][0], 'joint0_raw': float(j0), 'd_joint0': abs(r['joint'][0] - j0),
                   'joint_cached_rec': r['joint_cached'], 'joint_all_raw': float(jall),
                   'd_cached': abs(r['joint_cached'] - jall)})
    d0 = np.array([x['d_joint0'] for x in fr]); dc = np.array([x['d_cached'] for x in fr])
    out['from_raw_50'] = {'n': len(fr), 'joint0_maxabs': float(d0.max()), 'joint0_n_ge_1e-6': int((d0 >= TOL).sum()),
                          'cached_maxabs': float(dc.max()), 'cached_n_ge_1e-6': int((dc >= TOL).sum()),
                          'n_with_no_others': sum(x['n_others'] == 0 for x in fr), 'first5': fr[:5]}
    if (d0 >= TOL).any() or (dc >= TOL).any():
        out['issues'].append(f'from_raw: joint0 max {d0.max():.3g}, cached max {dc.max():.3g}')
    log('from_raw', out['from_raw_50']['joint0_maxabs'], out['from_raw_50']['cached_maxabs'])

    # (b) all records: own whitening + own unit norm + scipy NNLS for joint_0 and joint_cached
    allj0, allcj = [], []
    by_readout = collections.defaultdict(list)
    for r in recs:
        by_readout[(r['cell_id'], r['setting'])].append(r)
    for (cid, st), rs in by_readout.items():
        c = cells[cid]
        s = c['settings'][st]
        w = W[c['layer']]
        mu = w.mu.double().numpy(); Wm = w.w.double().numpy()
        t = (raw_target(c).astype('float64') - mu) @ Wm.T
        U = []
        for a in s['atoms']:
            x = (raw_vec(c['split'], a['cache_key']).astype('float64') - mu) @ Wm.T
            U.append(x / (np.linalg.norm(x) + 1e-9))
        U = np.stack(U)
        full = fve_scipy(U, t)
        for r in rs:
            idx = [i for i in range(len(U)) if i != r['bullet']]
            allj0.append(abs(fve_scipy(U[idx], t) - r['joint'][0]))
            allcj.append(abs(full - r['joint_cached']))
    allj0 = np.array(allj0); allcj = np.array(allcj)
    out['own_path_all'] = {'n': len(allj0), 'joint0_maxabs': float(allj0.max()), 'joint0_n_ge_1e-6': int((allj0 >= TOL).sum()),
                           'cached_maxabs': float(allcj.max()), 'cached_n_ge_1e-6': int((allcj >= TOL).sum())}
    if (allj0 >= TOL).any() or (allcj >= TOL).any():
        out['issues'].append(f"own float64 path: joint0 max {allj0.max():.3g}, cached max {allcj.max():.3g}")
    log('own path', out['own_path_all'])

    # ------------------------------------------------------------ sample tensors: recompute every prefix fit
    samples = []
    for p in sample_files:
        obj = torch.load(p, weights_only=True)
        samples += obj['samples'] if isinstance(obj, dict) else obj
    rec_by = {(r['cell_id'], r['setting'], r['bullet']): r for r in recs}
    sres = []
    for sm in samples:
        r = rec_by.get((sm['cell_id'], sm['setting'], sm['bullet']))
        if r is None:
            out['issues'].append(f"sample without record: {sm['cell_id']}")
            continue
        c = cells[sm['cell_id']]
        s = c['settings'][sm['setting']]
        t = sm['target'].double().numpy()
        O = sm['others_unit'].double().numpy().reshape(-1, t.shape[0])
        P = sm['prefix_unit'].double().numpy()
        cu = sm['cached_unit'].double().numpy()
        joint = [fve_scipy(O, t)] + [fve_scipy(np.vstack([O, P[k:k + 1]]), t) for k in range(P.shape[0])]
        joint = np.array(joint)
        solo_nnls = np.array([fve_scipy(P[k:k + 1], t) for k in range(P.shape[0])])
        solo_formula = np.array([max(0.0, P[k] @ t) ** 2 / float(t @ t) for k in range(P.shape[0])])
        jc = fve_scipy(np.vstack([O, cu[None]]), t)
        heat = np.diff(joint)
        # independent check of the sample's inputs against raw data + fresh whitener
        w = W[c['layer']]
        mu = w.mu.double().numpy(); Wm = w.w.double().numpy()
        t_raw = (raw_target(c).astype('float64') - mu) @ Wm.T
        def unit_raw(a):
            x = (raw_vec(c['split'], a['cache_key']).astype('float64') - mu) @ Wm.T
            return x / (np.linalg.norm(x) + 1e-9)
        O_raw = np.stack([unit_raw(a) for i, a in enumerate(s['atoms']) if i != sm['bullet']]) if len(s['atoms']) > 1 else np.zeros((0, t.shape[0]))
        cu_raw = unit_raw(s['atoms'][sm['bullet']])
        d = {'id': f"{sm['cell_id']}|{sm['setting']}|b{sm['bullet']}", 'n': int(P.shape[0]),
             'joint_vs_record': float(np.abs(joint - np.array(r['joint'])).max()),
             'heat_vs_record': float(np.abs(heat - np.array(r['heat'])).max()),
             'solo_nnls_vs_record': float(np.abs(solo_nnls - np.array(r['solo'])).max()),
             'solo_formula_vs_nnls': float(np.abs(solo_formula - solo_nnls).max()),
             'joint_cached_vs_record': abs(jc - r['joint_cached']),
             'joint_vs_sample_unrounded': float(np.abs(joint - sm['joint'].double().numpy()).max()),
             'solo_vs_sample_unrounded': float(np.abs(solo_nnls - sm['solo'].double().numpy()).max()),
             'sample_target_vs_raw_relmax': float(np.abs(t - t_raw).max() / np.abs(t_raw).max()),
             'sample_others_vs_raw_maxabs': float(np.abs(O - O_raw).max()) if O.size else 0.0,
             'sample_cached_vs_raw_maxabs': float(np.abs(cu - cu_raw).max()),
             'prefix_unit_norms': [float(np.linalg.norm(P, axis=1).min()), float(np.linalg.norm(P, axis=1).max())],
             'cos_prefix_n_vs_cached': float(P[-1] @ cu / (np.linalg.norm(P[-1]) * np.linalg.norm(cu))),
             'joint_record': r['joint'], 'joint_mine': [round(float(v), 7) for v in joint]}
        sres.append(d)
        for k in ('joint_vs_record', 'heat_vs_record', 'solo_nnls_vs_record', 'joint_cached_vs_record'):
            if d[k] >= TOL:
                out['issues'].append(f"sample {d['id']} {k} = {d[k]:.3g}")
    out['sample_recompute'] = {'files': [str(p) for p in sample_files], 'n_samples': len(sres), 'per_sample': sres}
    log('samples', len(sres), [(x['joint_vs_record'], x['heat_vs_record'], x['solo_nnls_vs_record']) for x in sres])

    # ------------------------------------------------------------ 5 random token-alignment printouts
    rng2 = random.Random(5)
    show = rng2.sample(recs, 5)
    # make sure at least one shown example contains an empty piece (multi-byte split), if any exist
    withempty = [r for r in recs if '' in r['pieces']]
    if withempty and not any('' in r['pieces'] for r in show):
        show[-1] = rng2.choice(withempty)
    tok_show = []
    for r in show:
        a = cells[r['cell_id']]['settings'][r['setting']]['atoms'][r['bullet']]
        text = a['scored_text']
        tok_show.append({'id': f"{r['cell_id']}|{r['setting']}|b{r['bullet']}", 'n': r['n_scored'],
                         'truncated': a['truncated'], 'len_scored_text': len(text),
                         'concat_eq_prefix': ''.join(r['pieces']) == text[:r['ends_in_scored_text'][-1]],
                         'slices_eq_pieces': all(r['pieces'][k] == text[(r['ends_in_scored_text'][k - 1] if k else 0):r['ends_in_scored_text'][k]] for k in range(r['n_scored'])),
                         'pieces': r['pieces'], 'ends': r['ends_in_scored_text'],
                         'decode_single_ids': [tok.decode([i]) for i in a['scored_token_ids']],
                         'scored_text': text, 'heat': r['heat']})
    out['token_alignment_examples'] = tok_show
    out['seconds'] = round(time.time() - T0, 1)
    dst = ROOT / 'logs' / ('verify_token_heat_cpu' + ('.merged' if args.merged else '.chunks') + '.json')
    dst.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    log('wrote', dst, 'issues:', out['issues'])


if __name__ == '__main__':
    main()
