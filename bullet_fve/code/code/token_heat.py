"""Per-token FVE "heat" for Oracle Lens bullets, WorkspaceBench Hallucination (chat).

For a bullet b (n scored AR tokens) in a readout with other bullets O:
  u_k      = whitened, unit-normalised AR prediction for the prefix of b's first k scored tokens
  joint_k  = exact NNLS FVE of {O's cached vectors} U {u_k};   joint_0 = FVE of O alone
  heat_k   = joint_k - joint_{k-1}     (telescopes to joint_n - joint_0)
  solo_k   = NNLS FVE of u_k alone = max(0, u_k.t)^2 / (|u_k|^2 |t|^2)
  joint_cached = FVE of O U {b's cached full vector} (= the saved readout FVE); drift = joint_n - joint_cached
Same conventions as olens_improve.reconstruction.JointNNLS.from_raw(solver='scipy_exact'):
per-layer pooled whitener (ridge 0.1), target whitened (magnitude kept), bullet vectors whitened then
unit-normalised with eps 1e-9, FVE = 1 - |resid|^2/|t|^2.

The AR (FrozenAR, Qwen3.6 backbone: Gated DeltaNet + full attention, all causal) reads the hidden state
at the last real token after the layer tag, so one forward over [tag + n scored tokens] gives every
prefix prediction (positions tag_len + k - 1). Right zero padding, as FrozenAR.encode_mixed.

NNLS with <= 4 columns is solved exactly by enumerating all column subsets on the float64 Gram matrix
(an NNLS optimum is the least-squares solution on some linearly independent support with
nonnegative coefficients; the best such feasible subset is the optimum). Validated against scipy.

Modes:
  nnls-selftest   CPU: Gram-enumeration NNLS vs scipy.optimize.nnls on >= 2000 fits
  test            GPU: equivalence test (single pass vs explicit prefixes vs cached vectors)
  run             GPU: full run in resumable (layer, split) chunks with done markers
  merge           CPU: merge chunks into heat/token_heat.jsonl + verify_sample.pt + meta/stats
READ-ONLY outside ${OLENS_SCRATCH}/olens-bullet-fve.
"""
import argparse
import collections
import hashlib
import itertools
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
INP = ROOT / 'inputs'
HEAT = ROOT / 'heat'
WORK = HEAT / 'work'
CHUNKS = WORK / 'chunks'
BOARD_JSON = Path('${OLENS_SCRATCH}/gpu_board/25832877.json')
PROJECT = Path('${OLENS_REPO_ROOT}')
ACTS = '${OLENS_COMPUTE_ROOT}/activations/core-v1/activations.safetensors'
WHITENERS = ('${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/'
             'snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners/'
             'whitening_iolens_pooled_L{}.safetensors')
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
LAYERS = (20, 36, 44, 52, 60)
SPLITS = ('development', 'validation', 'test')
D = 5120
T0 = time.time()


def log(**kw):
    print(json.dumps({'t': round(time.time() - T0, 1)} | kw), flush=True)


# ----------------------------------------------------------------------------- owner guard
class OwnerBusy(Exception):
    pass


def owner_state():
    try:
        return json.loads(BOARD_JSON.read_text()).get('state')
    except Exception as exc:  # file mid-write or missing
        return f'unreadable:{type(exc).__name__}'


def check_owner(where):
    # The user explicitly overrode the busy flag for this run (2026-10-15 14:2x EDT).
    # Still stop if another process starts using this GPU.
    if os.environ.get('HEAT_USER_OVERRIDE') == '1':
        try:
            import torch
            if torch.cuda.is_available() and torch.cuda.is_initialized():
                free, total = torch.cuda.mem_get_info()
                foreign = (total - free) - torch.cuda.memory_reserved()
                if foreign > 6e9:
                    raise OwnerBusy(f'{where}: another process holds {foreign / 1e9:.1f} GB on the GPU')
        except OwnerBusy:
            raise
        except Exception:
            pass
        return
    state = None
    for _ in range(3):
        state = owner_state()
        if state == 'idle':
            return
        if not str(state).startswith('unreadable'):
            break
        time.sleep(2)
    raise OwnerBusy(f'{where}: 25832877.json state={state!r}')


# ----------------------------------------------------------------------------- data
def rows_memmap(path, key):
    with open(path, 'rb') as f:
        n = int.from_bytes(f.read(8), 'little')
        header = json.loads(f.read(n))
    info = header[key]
    assert info['dtype'] == 'F32'
    return np.memmap(path, dtype='<f4', mode='r', offset=8 + n + info['data_offsets'][0],
                     shape=tuple(info['shape']))


def load_cells():
    return [json.loads(line) for line in open(INP / 'hall_three_settings.jsonl')]


def get_whitener(layer):
    """Whitener.load (float64 eigh, ridge 0.1) cached to WORK as float32 mu/W to make resumes cheap."""
    from olens_improve.reconstruction import Whitener
    WORK.mkdir(parents=True, exist_ok=True)
    cache = WORK / f'whitener_L{layer}.pt'
    if cache.exists():
        d = torch.load(cache, weights_only=True)
        return Whitener(d['mu'], d['w'], d['sha'], 0.1)
    w = Whitener.load(WHITENERS.format(layer))
    tmp = cache.with_suffix('.tmp')
    torch.save({'mu': w.mu, 'w': w.w, 'sha': w.artifact_sha256}, tmp)
    os.replace(tmp, cache)
    return w


class LayerData:
    """Cached bullet vectors (whitened, unit) and targets (whitened) for one layer, on CPU float32,
    computed exactly as compute_bullet_metrics.py (which reproduced the saved FVE with diff 0.0)."""

    def __init__(self, layer, cells_layer, vindex, acts, w):
        self.layer = layer
        need = sorted({(c['split'], a['cache_key']) for c in cells_layer
                       for s in c['settings'].values() for a in s['atoms']})
        by_file = collections.defaultdict(list)
        for split, key in need:
            path, row = vindex[split][key]
            by_file[path].append((row, (split, key)))
        raw = {}
        for path, items in by_file.items():
            mm = rows_memmap(path, 'vectors')
            rows = sorted(items)
            block = np.asarray(mm[[r for r, _ in rows]])
            raw.update({sk: block[i] for i, (_, sk) in enumerate(rows)})
        keys = list(raw)
        unit = torch.empty((len(keys) + 1, D), dtype=torch.float32)  # last row = zero padding
        unit[-1] = 0
        for i in range(0, len(keys), 4096):
            chunk = keys[i:i + 4096]
            x = w.whiten(torch.from_numpy(np.stack([raw[k] for k in chunk])))
            unit[i:i + len(chunk)] = x / (x.norm(dim=1, keepdim=True) + 1e-9)
        del raw
        self.cindex = {k: i for i, k in enumerate(keys)}
        self.zero = len(keys)
        self.C = unit
        self.tindex = {}
        tg = torch.empty((len(cells_layer), D), dtype=torch.float32)
        for i, c in enumerate(cells_layer):
            t_raw = torch.from_numpy(np.asarray(acts[c['activation_row']]).copy())
            assert hashlib.sha256(t_raw.numpy().tobytes()).hexdigest() == c['activation_sha256']
            tg[i] = w.whiten(t_raw.reshape(1, -1))[0]
            self.tindex[c['cell_id']] = i
        self.T = tg


# ----------------------------------------------------------------------------- exact small NNLS
SUBSETS = [S for r in range(1, 5) for S in itertools.combinations(range(4), r)]


def nnls_gram(G, b, tt, present):
    """Exact NNLS FVE for <= 4 columns from Gram data (float64).
    G [R,4,4], b [R,4] (= X t), tt [R] (= |t|^2), present [R,4] bool.
    Returns fve [R], coef [R,4], kkt [R] (max positive gradient on zero coefficients; ~0 if optimal)."""
    R = G.shape[0]
    best = np.zeros(R)
    coef = np.zeros((R, 4))
    for S in SUBSETS:
        S = list(S)
        valid = present[:, S].all(1)
        if not valid.any():
            continue
        idx = np.nonzero(valid)[0]
        Gs = G[idx][:, S][:, :, S].copy()
        bs = b[idx][:, S]
        ev = np.linalg.eigvalsh(Gs)
        ok = ev[:, 0] > 1e-12 * np.maximum(1.0, ev[:, -1])
        Gs[~ok] = np.eye(len(S))
        c = np.linalg.solve(Gs, bs[..., None])[..., 0]
        feas = ok & (c >= 0).all(1)
        # true FVE of the feasible point c (valid even if the solve is inaccurate)
        val = (2 * (c * bs).sum(1) - np.einsum('ri,rij,rj->r', c, G[idx][:, S][:, :, S], c)) / tt[idx]
        upd = feas & (val > best[idx])
        if upd.any():
            rows = idx[upd]
            best[rows] = val[upd]
            coef[rows] = 0
            coef[np.ix_(rows, S)] = c[upd]
    grad = b - np.einsum('rij,rj->ri', G, coef)
    grad = np.where(present & (coef <= 0), grad, 0.0)
    kkt = np.maximum(grad.max(1), 0.0) / np.sqrt(tt)
    return best, coef, kkt


def scipy_fve(X, t):
    from scipy.optimize import nnls
    if X.shape[0] == 0:
        return 0.0
    _, res = nnls(X.astype('float64').T, t.astype('float64'))
    return 1 - res ** 2 / max(float((t.astype('float64') ** 2).sum()), 1e-12)


def gram_fve(X, t):
    X = X.astype('float64'); t = t.astype('float64')
    m = X.shape[0]
    G = np.eye(4)[None].copy(); b = np.zeros((1, 4)); pres = np.zeros((1, 4), bool)
    G[0, :m, :m] = X @ X.T; b[0, :m] = X @ t; pres[0, :m] = True
    return nnls_gram(G, b, np.array([t @ t]), pres)


# ----------------------------------------------------------------------------- token offsets
def _bytes_to_unicode():
    bs = list(range(ord('!'), ord('~') + 1)) + list(range(ord('¡'), ord('¬') + 1)) + list(range(ord('®'), ord('ÿ') + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b); cs.append(256 + n); n += 1
    return dict(zip(bs, map(chr, cs)))


BYTE_DEC = {v: k for k, v in _bytes_to_unicode().items()}
SCAFFOLD = r"</?explanation>|<\|im_start\|>(system|user|assistant)?|<\|im_end\|>|<think>|</think>"


def ends_from_bytes(tok, ids, text):
    """Char (code point) end offsets from raw token bytes; an incomplete UTF-8 char belongs to the
    token that completes it. Returns (ends, ok)."""
    buf = b''
    ends = []
    s = ''
    for i in ids:
        piece = tok.convert_ids_to_tokens(i)
        try:
            buf += bytes(BYTE_DEC[ch] for ch in piece)
        except KeyError:
            buf += tok.decode([i]).encode('utf-8')
        s = None
        for cut in range(len(buf), max(len(buf) - 4, 0) - 1, -1):
            try:
                s = buf[:cut].decode('utf-8')
                break
            except UnicodeDecodeError:
                continue
        if s is None:
            return None, False
        ends.append(len(s))
    return ends, text.startswith(s)


def token_ends(tok, special, atom):
    """ends_in_scored_text from the tokenizer offset mapping on scored_text (multi-byte splits:
    shared char assigned to the later token); fallback to raw-byte incremental decode."""
    text = atom['scored_text']
    sids = atom['scored_token_ids']
    n = len(sids)
    method = 'offsets'
    ends = None
    cleaned = re.sub(SCAFFOLD, '', text).strip()
    if cleaned == text:
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
        pairs = [(i, o) for i, o in zip(enc['input_ids'], enc['offset_mapping']) if i not in special]
        if [i for i, _ in pairs][:n] == sids:
            offs = [o for _, o in pairs]
            ends = []
            prev = 0
            for k in range(n):
                e = offs[k][1]
                if k + 1 < len(offs) and offs[k + 1][0] < e:
                    e = offs[k + 1][0]
                e = max(e, prev)
                ends.append(e)
                prev = e
    bends, bok = ends_from_bytes(tok, sids, text)
    agree = ends is not None and bends is not None and ends == bends
    if ends is None:
        method = 'bytes'
        ends = bends if bends is not None else []
        if not bok:
            method = 'bytes_misaligned'
    pieces = []
    prev = 0
    for e in ends:
        pieces.append(text[prev:e])
        prev = e
    return ends, pieces, method, agree


# ----------------------------------------------------------------------------- AR forward
def load_ar():
    from olens_improve.reconstruction import FrozenAR
    rt = json.loads((PROJECT / 'configs/runtime.json').read_text())
    ckpt = json.loads((PROJECT / 'configs/expansion_gpu_enqueue_v1.json').read_text())['checkpoint']
    t = time.time()
    ar = FrozenAR.load(rt['paths']['base_snapshot'], ckpt, device='cuda')
    log(event='ar_loaded', seconds=round(time.time() - t, 1), layers=list(ar.layers),
        tag_len=int(ar.tags.shape[1]), matched_adapter_tensors=ar.metadata['matched_adapter_tensors'])
    return ar


def ar_forward(ar, seqs, layers, all_positions):
    """Mirror of FrozenAR.encode_mixed on explicit token ids (<= 32 each), right zero padding.
    all_positions=True returns head(h) at every real scored position (row-concatenated, k = 1..n);
    False returns only the last real position, exactly like encode_mixed. Output float32 on GPU."""
    dev = ar.device
    li = [ar.layers.index(layer) for layer in layers]
    width = max(map(len, seqs))
    ids = torch.zeros((len(seqs), width), dtype=torch.long, device=dev)
    mask = torch.zeros_like(ids)
    for i, row in enumerate(seqs):
        assert 0 < len(row) <= 32
        ids[i, :len(row)] = torch.tensor(row, device=dev)
        mask[i, :len(row)] = 1
    tag = ar.tags[torch.tensor(li, device=ar.tags.device)]
    ids, mask = torch.cat((tag, ids), 1), torch.cat((torch.ones_like(tag), mask), 1)
    tl = tag.shape[1]
    with torch.inference_mode():
        out = ar.backbone(input_ids=ids, attention_mask=mask, use_cache=False)
        H = out.last_hidden_state
        if all_positions:
            hidden = torch.cat([H[i, tl:tl + len(r)] for i, r in enumerate(seqs)])
        else:
            last = mask.sum(1) - 1
            hidden = H[torch.arange(len(seqs), device=dev), last]
        return ar.head(hidden).float()


def whiten_unit_gpu(x, mu_g, w_g):
    y = (x.float() - mu_g) @ w_g.T
    return y / (y.norm(dim=1, keepdim=True) + 1e-9)


# ----------------------------------------------------------------------------- per-occurrence fits
def fit_occurrences(occs, U, T64, C64, zero):
    """occs: dicts with tix, oix (<=3 cached idx), bix (cached idx of b), ustart, n.
    U: [N,D] float32 GPU unit prefix vectors. T64/C64 float64 GPU. Returns per occ dict of arrays."""
    dev = U.device
    O = len(occs)
    tix = torch.tensor([o['tix'] for o in occs], device=dev)
    oix = torch.tensor([o['oix'] + [zero] * (3 - len(o['oix'])) for o in occs], device=dev)
    bix = torch.tensor([o['bix'] for o in occs], device=dev)
    opres = np.array([[j < len(o['oix']) for j in range(3)] for o in occs])
    tt = np.empty(O); ot = np.empty((O, 3)); oo = np.empty((O, 3, 3)); ct = np.empty(O)
    co = np.empty((O, 3)); cc = np.empty(O)
    for s in range(0, O, 1024):
        sl = slice(s, s + 1024)
        t = T64[tix[sl]]
        ov = C64[oix[sl]]
        cv = C64[bix[sl]]
        tt[sl] = (t * t).sum(1).cpu().numpy()
        ot[sl] = torch.einsum('pjd,pd->pj', ov, t).cpu().numpy()
        oo[sl] = torch.einsum('pjd,pkd->pjk', ov, ov).cpu().numpy()
        ct[sl] = (cv * t).sum(1).cpu().numpy()
        co[sl] = torch.einsum('pjd,pd->pj', ov, cv).cpu().numpy()
        cc[sl] = (cv * cv).sum(1).cpu().numpy()
    # rows (occ, k)
    rocc = np.concatenate([np.full(o['n'], i) for i, o in enumerate(occs)])
    ridx = np.concatenate([np.arange(o['ustart'], o['ustart'] + o['n']) for o in occs])
    R = len(rocc)
    ut = np.empty(R); uo = np.empty((R, 3)); uu = np.empty(R)
    rocc_t = torch.from_numpy(rocc).to(dev)
    ridx_t = torch.from_numpy(ridx).to(dev)
    for s in range(0, R, 8192):
        sl = slice(s, s + 8192)
        u = U[ridx_t[sl]].double()
        t = T64[tix[rocc_t[sl]]]
        ov = C64[oix[rocc_t[sl]]]
        ut[sl] = (u * t).sum(1).cpu().numpy()
        uo[sl] = torch.einsum('pjd,pd->pj', ov, u).cpu().numpy()
        uu[sl] = (u * u).sum(1).cpu().numpy()

    def gram(n_rows, o_idx, col3_dot_o, col3_dot_t, col3_sq, col3_present):
        G = np.zeros((n_rows, 4, 4)); G[:, :3, :3] = oo[o_idx]
        G[:, :3, 3] = col3_dot_o; G[:, 3, :3] = col3_dot_o
        G[:, 3, 3] = np.where(col3_present, col3_sq, 1.0)
        b = np.zeros((n_rows, 4)); b[:, :3] = ot[o_idx]; b[:, 3] = col3_dot_t
        pres = np.zeros((n_rows, 4), bool); pres[:, :3] = opres[o_idx]; pres[:, 3] = col3_present
        # absent other columns: identity diagonal so subsets never use them
        for j in range(3):
            miss = ~pres[:, j]
            G[miss, j, :] = 0; G[miss, :, j] = 0; G[miss, j, j] = 1; b[miss, j] = 0
        return G, b, pres

    allo = np.arange(O)
    G, b, pres = gram(O, allo, np.zeros((O, 3)), np.zeros(O), np.ones(O), np.zeros(O, bool))
    j0, _, k0 = nnls_gram(G, b, tt, pres)
    G, b, pres = gram(O, allo, co, ct, cc, np.ones(O, bool))
    jc, coef_c, kc = nnls_gram(G, b, tt, pres)
    G, b, pres = gram(R, rocc, uo, ut, uu, np.ones(R, bool))
    jk, _, kk = nnls_gram(G, b, tt[rocc], pres)
    solo = np.where(ut > 0, ut ** 2 / (uu * tt[rocc]), 0.0)
    res = []
    pos = 0
    for i, o in enumerate(occs):
        n = o['n']
        res.append({'joint': np.concatenate([[j0[i]], jk[pos:pos + n]]), 'solo': solo[pos:pos + n],
                    'joint_cached': jc[i], 'coef_cached': coef_c[i],
                    'kkt': max(k0[i], kc[i], kk[pos:pos + n].max())})
        pos += n
    return res


def build_occs(cells_chunk, ld, key_start, key_n):
    occs = []
    for c in cells_chunk:
        for st in SETTINGS:
            s = c['settings'][st]
            atoms = s['atoms']
            if not atoms:
                continue
            keys = [a['cache_key'] for a in atoms]
            cidx = [ld.cindex[(c['split'], k)] for k in keys]
            for j, a in enumerate(atoms):
                k = a['cache_key']
                occs.append({'cell': c, 'setting': st, 'bullet': j, 'atom': a,
                             'tix': ld.tindex[c['cell_id']], 'bix': cidx[j],
                             'oix': [cidx[i] for i in range(len(atoms)) if i != j],
                             'ustart': key_start[k], 'n': key_n[k],
                             'dup': keys.count(k) > 1, 'n_bullets': len(atoms),
                             'saved_fve': s['fve']})
    return occs


# ----------------------------------------------------------------------------- shared setup
def setup_cpu(layers):
    sys.path.insert(0, str(PROJECT / 'src'))
    torch.set_num_threads(min(8, os.cpu_count() or 8))
    cells = load_cells()
    vindex = json.load(open(INP / 'hall_vector_index.json'))
    acts = rows_memmap(ACTS, 'resid')
    by_layer = collections.defaultdict(list)
    for c in cells:
        by_layer[c['layer']].append(c)
    return cells, vindex, acts, by_layer


def get_tokenizer():
    from transformers import AutoTokenizer
    rt = json.loads((PROJECT / 'configs/runtime.json').read_text())
    tok = AutoTokenizer.from_pretrained(rt['paths']['base_snapshot'], local_files_only=True)
    return tok, set(tok.all_special_ids)


# ----------------------------------------------------------------------------- mode: nnls-selftest
def mode_nnls_selftest(args):
    from scipy.optimize import nnls  # noqa: F401
    cells, vindex, acts, by_layer = setup_cpu(LAYERS)
    rng = random.Random(1234)
    nrng = np.random.default_rng(1234)
    diffs = []
    kinds = collections.Counter()
    t = time.time()
    for layer in args.layers:
        w = get_whitener(layer)
        sub = rng.sample(by_layer[layer], 120)
        ld = LayerData(layer, sub, vindex, acts, w)
        C = ld.C.numpy().astype('float64'); T = ld.T.numpy().astype('float64')
        per_layer = max(1, args.fits // len(args.layers))
        for _ in range(per_layer):
            c = rng.choice(sub)
            s = c['settings'][rng.choice(SETTINGS)]
            if not s['atoms']:
                continue
            cols = [C[ld.cindex[(c['split'], a['cache_key'])]] for a in s['atoms']]
            rng.shuffle(cols)
            cols = cols[:rng.randint(1, 4)]
            kind = 'readout'
            r = rng.random()
            if r < 0.35:  # emulate a prefix vector: perturb one column
                i = rng.randrange(len(cols)); eps = rng.uniform(0.01, 1.0)
                v = cols[i] + eps * nrng.standard_normal(D) / np.sqrt(D)
                cols[i] = v / np.linalg.norm(v); kind = 'perturbed'
            elif r < 0.55 and len(cols) < 4:  # foreign vector (often zero coefficient)
                cols.append(C[rng.randrange(len(C) - 1)]); kind = 'foreign'
            elif r < 0.62 and len(cols) < 4:  # exact duplicate column
                cols.append(cols[0].copy()); kind = 'duplicate'
            X = np.stack(cols).astype('float32').astype('float64')
            tgt = T[ld.tindex[c['cell_id']]]
            if rng.random() < 0.15:
                tgt = -tgt; kind += '+negtarget'
            a = scipy_fve(X, tgt)
            g = gram_fve(X, tgt)[0][0]
            diffs.append(abs(a - g)); kinds[kind] += 1
    diffs = np.array(diffs)
    out = {'fits': len(diffs), 'max_abs_diff': float(diffs.max()), 'median_abs_diff': float(np.median(diffs)),
           'n_gt_1e-7': int((diffs > 1e-7).sum()), 'kinds': dict(kinds), 'seconds': round(time.time() - t, 1)}
    log(event='nnls_selftest', **out)
    (HEAT / 'nnls_selftest.json').write_text(json.dumps(out, indent=1) + '\n')


# ----------------------------------------------------------------------------- mode: test
def cos_rows(a, b):
    a = a.double(); b = b.double()
    return ((a * b).sum(1) / (a.norm(dim=1) * b.norm(dim=1))).cpu().numpy()


def q(x):
    x = np.asarray(x, dtype=float)
    return {'n': int(x.size), 'min': float(x.min()), 'p01': float(np.quantile(x, 0.01)),
            'median': float(np.median(x)), 'max': float(x.max())}


def mode_test(args):
    from olens_improve.reconstruction import ar_token_ids
    torch.set_float32_matmul_precision('highest')
    cells, vindex, acts, by_layer = setup_cpu(LAYERS)
    tok, special = get_tokenizer()
    rng = random.Random(7)
    check_owner('test:start')
    # choose 40 bullets: per layer 3 truncated, 1 short (<=6 tokens), 4 random; spread over splits
    chosen = []
    for layer in LAYERS:
        occ = [(c, st, j) for c in by_layer[layer] for st in SETTINGS
               for j, a in enumerate(c['settings'][st]['atoms'])]
        trunc = [x for x in occ if x[0]['settings'][x[1]]['atoms'][x[2]]['truncated']]
        short = [x for x in occ if len(x[0]['settings'][x[1]]['atoms'][x[2]]['scored_token_ids']) <= 6]
        pick = rng.sample(trunc, 3) + rng.sample(short, 1) + rng.sample(occ, 4)
        chosen += [(layer, *x) for x in pick]
    # per-layer data restricted to the cells involved
    lds = {}
    whit = {}
    for layer in LAYERS:
        whit[layer] = get_whitener(layer)
        sub = list({x[1]['cell_id']: x[1] for x in chosen if x[0] == layer}.values())
        lds[layer] = LayerData(layer, sub, vindex, acts, whit[layer])
    log(event='test_data_ready', bullets=len(chosen))
    ar = load_ar()
    check_owner('test:after_load')
    rec = collections.defaultdict(list)
    report = {'bullets': []}
    for layer in LAYERS:
        ld = lds[layer]; w = whit[layer]
        mu_g, w_g = w.mu.cuda(), w.w.cuda()
        sel = [x for x in chosen if x[0] == layer]
        atoms = [x[1]['settings'][x[2]]['atoms'][x[3]] for x in sel]
        seqs = [a['scored_token_ids'] for a in atoms]
        # tokenization identity
        for a in atoms:
            rec['ar_token_ids_match'].append(ar_token_ids(tok, a['scored_text'])[1][:32] == a['scored_token_ids'])
        # (1) single pass, this layer's 8 bullets as one batch (sorted by length, like the run)
        order = sorted(range(len(seqs)), key=lambda i: -len(seqs[i]))
        P = ar_forward(ar, [seqs[i] for i in order], [layer] * len(seqs), True)
        U1 = {}
        pos = 0
        for i in order:
            U1[i] = whiten_unit_gpu(P[pos:pos + len(seqs[i])], mu_g, w_g); pos += len(seqs[i])
        # (1b) same bullets each alone (B=1, no padding)
        U1b = {i: whiten_unit_gpu(ar_forward(ar, [seqs[i]], [layer], True), mu_g, w_g) for i in range(len(seqs))}
        # (2) explicit prefixes: FrozenAR.encode_mixed on decoded prefix text where it re-tokenizes to the
        #     same ids, else the id-level mirror (last position only); all prefixes of a bullet in one batch
        U2 = {}
        for i, s in enumerate(seqs):
            texts = [tok.decode(s[:k]) for k in range(1, len(s) + 1)]
            rt_ok = [ar_token_ids(tok, tx)[1] == s[:k] for k, tx in zip(range(1, len(s) + 1), texts)]
            rec['explicit_roundtrip_ok'] += rt_ok
            if all(rt_ok):
                preds, _ = ar.encode_mixed(texts, [layer] * len(texts))
                preds = preds.cuda()
                # sanity: id-level mirror == encode_mixed on the same batch
                mirror = ar_forward(ar, [s[:k] for k in range(1, len(s) + 1)], [layer] * len(s), False)
                rec['mirror_vs_encode_mixed_maxabs'].append(float((mirror - preds).abs().max()))
            else:
                preds = ar_forward(ar, [s[:k] for k in range(1, len(s) + 1)], [layer] * len(s), False)
            U2[i] = whiten_unit_gpu(preds, mu_g, w_g)
        # (3) explicit full text, B=1, via encode_mixed on scored_text
        U3 = {}
        for i, a in enumerate(atoms):
            preds, meta = ar.encode_mixed([a['scored_text']], [layer])
            assert meta[0]['input_ids'] == a['scored_token_ids']
            U3[i] = whiten_unit_gpu(preds.cuda(), mu_g, w_g)
        Cg = ld.C.cuda()
        for i in range(len(seqs)):
            c_cached = Cg[ld.cindex[(sel[i][1]['split'], atoms[i]['cache_key'])]][None]
            rec['cos_single_vs_explicit'] += list(cos_rows(U1[i], U2[i]))
            rec['cos_single_vs_alone'] += list(cos_rows(U1[i], U1b[i]))
            rec['cos_singleN_vs_cached'].append(float(cos_rows(U1[i][-1:], c_cached)[0]))
            rec['cos_explicitFullB1_vs_cached'].append(float(cos_rows(U3[i], c_cached)[0]))
            rec['cos_singleN_vs_explicitFullB1'].append(float(cos_rows(U1[i][-1:], U3[i])[0]))
            rec['cos_explicitN_vs_cached'].append(float(cos_rows(U2[i][-1:], c_cached)[0]))
        # fits with each source
        T64, C64 = ld.T.cuda().double(), Cg.double()
        cells_l = {x[1]['cell_id']: x[1] for x in sel}
        fits = {}
        for name, Us in (('single', U1), ('explicit', U2), ('alone', U1b)):
            U = torch.cat([Us[i] for i in range(len(seqs))])
            starts = np.cumsum([0] + [len(s) for s in seqs])
            occs = []
            for i, x in enumerate(sel):
                c, st, j = x[1], x[2], x[3]
                s_ = c['settings'][st]
                keys = [a['cache_key'] for a in s_['atoms']]
                cidx = [ld.cindex[(c['split'], k)] for k in keys]
                occs.append({'tix': ld.tindex[c['cell_id']], 'bix': cidx[j],
                             'oix': [cidx[m] for m in range(len(keys)) if m != j],
                             'ustart': int(starts[i]), 'n': len(seqs[i]), 'saved': s_['fve']})
            fits[name] = fit_occurrences(occs, U, T64, C64, ld.zero)
            if name == 'single':
                for i, (o, f) in enumerate(zip(occs, fits[name])):
                    rec['joint_cached_vs_saved'].append(abs(f['joint_cached'] - o['saved']))
                    rec['drift_jointN_vs_cached'].append(abs(f['joint'][-1] - f['joint_cached']))
                    rec['kkt'].append(f['kkt'])
                    # scipy cross-check of every prefix fit for this bullet
                    t = T64[o['tix']].cpu().numpy(); Ov = C64[o['oix']].cpu().numpy()
                    Ub = U[o['ustart']:o['ustart'] + o['n']].double().cpu().numpy()
                    for k in range(o['n']):
                        X = np.vstack([Ov, Ub[k:k + 1]])
                        rec['gram_vs_scipy'].append(abs(scipy_fve(X, t) - f['joint'][k + 1]))
                    rec['gram_vs_scipy'].append(abs(scipy_fve(Ov, t) - f['joint'][0]))
        for i in range(len(seqs)):
            a, b_, c_ = fits['single'][i], fits['explicit'][i], fits['alone'][i]
            rec['joint_single_vs_explicit'] += list(np.abs(a['joint'][1:] - b_['joint'][1:]))
            rec['heat_single_vs_explicit'] += list(np.abs(np.diff(a['joint']) - np.diff(b_['joint'])))
            rec['solo_single_vs_explicit'] += list(np.abs(a['solo'] - b_['solo']))
            rec['joint_single_vs_alone'] += list(np.abs(a['joint'][1:] - c_['joint'][1:]))
            report['bullets'].append({'cell_id': sel[i][1]['cell_id'], 'setting': sel[i][2], 'bullet': sel[i][3],
                                      'n': len(seqs[i]), 'truncated': atoms[i]['truncated'],
                                      'joint_single': [round(float(v), 5) for v in a['joint']],
                                      'max_joint_diff_explicit': float(np.abs(a['joint'] - b_['joint']).max()),
                                      'joint_cached': float(a['joint_cached']), 'saved': sel[i][1]['settings'][sel[i][2]]['fve']})
        check_owner(f'test:layer{layer}')
        log(event='test_layer_done', layer=layer)
    summary = {}
    for k, v in rec.items():
        if not v:
            summary[k] = None
        elif k in ('ar_token_ids_match', 'explicit_roundtrip_ok'):
            summary[k] = {'true': int(sum(v)), 'n': len(v)}
        else:
            summary[k] = q(v)
    report['summary'] = summary
    report['note'] = ('cos_* are cosines of whitened vectors; joint_* are |FVE differences| per prefix fit; '
                      'single = one forward over all n tokens (batch of the layer\'s 8 bullets, right padded), '
                      'alone = same single pass with batch size 1, explicit = FrozenAR.encode_mixed on each '
                      'prefix (batch = the bullet\'s n prefixes), explicitFullB1 = encode_mixed(scored_text) alone.')
    (HEAT / 'equivalence_test.json').write_text(json.dumps(report, indent=1) + '\n')
    log(event='test_summary', **summary)


# ----------------------------------------------------------------------------- mode: run
def chunk_name(layer, split):
    return f'L{layer}_{split}'


def mode_run(args):
    torch.set_float32_matmul_precision('highest')
    cells, vindex, acts, by_layer = setup_cpu(LAYERS)
    tok, special = get_tokenizer()
    CHUNKS.mkdir(parents=True, exist_ok=True)
    # deterministic verify sample over all non-empty occurrences in file order
    all_occ = [(c['cell_id'], st, j) for c in cells for st in SETTINGS for j in range(len(c['settings'][st]['atoms']))]
    sample = set(random.Random(20261015).sample(all_occ, 60))
    order = {(c['cell_id'], st): (ci, si) for ci, c in enumerate(cells) for si, st in enumerate(SETTINGS)}
    todo = [(layer, split) for layer in LAYERS for split in SPLITS
            if not (CHUNKS / (chunk_name(layer, split) + '.done')).exists()]
    log(event='run_start', todo=[chunk_name(*x) for x in todo], sample=len(sample))
    if not todo:
        return
    check_owner('run:start')
    ar = None
    for layer in LAYERS:
        chunks_l = [x for x in todo if x[0] == layer]
        if not chunks_l:
            continue
        check_owner(f'run:L{layer}:prep')
        w = get_whitener(layer)
        ld = LayerData(layer, by_layer[layer], vindex, acts, w)
        log(event='layer_data', layer=layer, cached=ld.zero, cells=len(ld.tindex))
        if ar is None:
            ar = load_ar()
        mu_g, w_g = w.mu.cuda(), w.w.cuda()
        Cg = ld.C.cuda(); C64 = Cg.double(); T64 = ld.T.cuda().double()
        for _, split in chunks_l:
            name = chunk_name(layer, split)
            check_owner(f'run:{name}:start')
            tc = time.time()
            cells_chunk = [c for c in by_layer[layer] if c['split'] == split]
            keyids = {}
            for c in cells_chunk:
                for st in SETTINGS:
                    for a in c['settings'][st]['atoms']:
                        keyids[a['cache_key']] = a['scored_token_ids']
            keys = sorted(keyids, key=lambda k: (-len(keyids[k]), k))
            key_start, key_n = {}, {}
            pos = 0
            for k in keys:
                key_start[k] = pos; key_n[k] = len(keyids[k]); pos += len(keyids[k])
            U = torch.empty((pos, D), dtype=torch.float32, device='cuda')
            tf = time.time()
            for i in range(0, len(keys), args.batch):
                check_owner(f'run:{name}:batch{i // args.batch}')
                bk = keys[i:i + args.batch]
                P = ar_forward(ar, [keyids[k] for k in bk], [layer] * len(bk), True)
                U[key_start[bk[0]]:key_start[bk[0]] + P.shape[0]] = whiten_unit_gpu(P, mu_g, w_g)
            torch.cuda.synchronize()
            fwd_s = time.time() - tf
            occs = build_occs(cells_chunk, ld, key_start, key_n)
            res = fit_occurrences(occs, U, T64, C64, ld.zero)
            # sample tensors for independent CPU verification
            samp = []
            lines = []
            stats = collections.Counter()
            tele = 0.0
            for o, r in zip(occs, res):
                c, a = o['cell'], o['atom']
                ends, pieces, method, agree = token_ends(tok, special, a)
                stats['offsets_' + method] += 1
                stats['offsets_bytes_agree'] += bool(agree)
                joint = r['joint']
                jr = [round(float(v), 7) for v in joint]
                heat = [round(jr[k] - jr[k - 1], 7) for k in range(1, len(jr))]
                tele = max(tele, abs(float(np.diff(joint).sum() - (joint[-1] - joint[0]))))
                rec = {'cell_id': c['cell_id'], 'setting': o['setting'], 'bullet': o['bullet'],
                       'phrase_id': a['source_phrase_id'], 'cache_key': a['cache_key'], 'layer': layer,
                       'split': split, 'n_scored': o['n'], 'truncated': bool(a['truncated']),
                       'n_bullets': o['n_bullets'], 'dup_in_readout': o['dup'],
                       'ends_in_scored_text': ends, 'pieces': pieces, 'heat': heat,
                       'solo': [round(float(v), 7) for v in r['solo']], 'joint': jr,
                       'joint_cached': round(float(r['joint_cached']), 7),
                       'drift': round(float(joint[-1] - r['joint_cached']), 7),
                       'readout_fve_saved': round(float(o['saved_fve']), 7),
                       '_ord': list(order[(c['cell_id'], o['setting'])]) + [o['bullet']],
                       '_cached_vs_saved': float(abs(r['joint_cached'] - o['saved_fve'])),
                       '_kkt': float(r['kkt'])}
                lines.append(json.dumps(rec, ensure_ascii=False))
                if (c['cell_id'], o['setting'], o['bullet']) in sample:
                    samp.append({'cell_id': c['cell_id'], 'setting': o['setting'], 'bullet': o['bullet'],
                                 'layer': layer, 'n': o['n'],
                                 'prefix_unit': U[o['ustart']:o['ustart'] + o['n']].cpu().clone(),
                                 'target': ld.T[o['tix']].clone(),
                                 'others_unit': ld.C[o['oix']].clone() if o['oix'] else torch.empty((0, D)),
                                 'cached_unit': ld.C[o['bix']].clone(),
                                 'joint': torch.tensor(joint), 'solo': torch.tensor(r['solo']),
                                 'joint_cached': float(r['joint_cached']), 'saved_fve': o['saved_fve']})
            tmp = CHUNKS / (name + '.jsonl.tmp')
            tmp.write_text('\n'.join(lines) + '\n')
            os.replace(tmp, CHUNKS / (name + '.jsonl'))
            if samp:
                torch.save(samp, CHUNKS / (name + '.sample.pt'))
            done = {'chunk': name, 'occurrences': len(occs), 'unique_keys': len(keys), 'tokens': pos,
                    'forward_seconds': round(fwd_s, 1), 'seconds': round(time.time() - tc, 1),
                    'telescoping_max_unrounded': tele, 'samples': len(samp),
                    'max_kkt': max([r['kkt'] for r in res], default=0.0),
                    'max_cached_vs_saved': max([abs(r['joint_cached'] - o['saved_fve']) for o, r in zip(occs, res)], default=0.0),
                    **{k: int(v) for k, v in stats.items()}}
            (CHUNKS / (name + '.done')).write_text(json.dumps(done) + '\n')
            log(event='chunk_done', **done)
            del U
        del Cg, C64, T64, ld
        torch.cuda.empty_cache()
    log(event='run_complete')


# ----------------------------------------------------------------------------- mode: merge
def mode_merge(args):
    missing = [chunk_name(layer, split) for layer in LAYERS for split in SPLITS
               if not (CHUNKS / (chunk_name(layer, split) + '.done')).exists()]
    if missing:
        raise SystemExit(f'missing chunks: {missing}')
    recs = []
    for layer in LAYERS:
        for split in SPLITS:
            for line in open(CHUNKS / (chunk_name(layer, split) + '.jsonl')):
                if line.strip():
                    recs.append(json.loads(line))
    recs.sort(key=lambda r: r['_ord'])
    tele_r, cached_saved, kkt, drift = [], [], [], []
    tokens = 0
    for r in recs:
        tele_r.append(abs(sum(r['heat']) - (r['joint'][-1] - r['joint'][0])))
        cached_saved.append(r.pop('_cached_vs_saved'))
        kkt.append(r.pop('_kkt'))
        drift.append(abs(r['drift']))
        tokens += r['n_scored']
        r.pop('_ord')
    tmp = HEAT / 'token_heat.jsonl.tmp'
    with open(tmp, 'w') as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(tmp, HEAT / 'token_heat.jsonl')
    samples = []
    for layer in LAYERS:
        for split in SPLITS:
            p = CHUNKS / (chunk_name(layer, split) + '.sample.pt')
            if p.exists():
                samples += torch.load(p, weights_only=True)
    torch.save({'doc': ('Whitened (pooled whitener, ridge 0.1) vectors for 60 random occurrences. prefix_unit[k-1] = '
                        'unit AR prediction for the first k scored tokens; target = whitened target (not normalised); '
                        'others_unit = cached unit vectors of the other bullets in the readout; cached_unit = b\'s '
                        'cached unit vector. joint[k] = NNLS FVE of others U {prefix_unit[k-1]} (joint[0] = others '
                        'only); solo[k-1] = FVE of prefix_unit[k-1] alone; joint_cached = FVE of others U {cached_unit}. '
                        'FVE = 1 - |t - Xc|^2/|t|^2 with c = scipy.optimize.nnls(X.T, t) in float64.'),
                'samples': samples}, HEAT / 'verify_sample.pt')
    chunk_stats = [json.loads((CHUNKS / (chunk_name(l, s) + '.done')).read_text()) for l in LAYERS for s in SPLITS]
    drift = np.array(drift)
    meta = {'file': 'token_heat.jsonl', 'occurrences': len(recs), 'scored_tokens': tokens,
            'fields': {
                'bullet': 'index of the bullet in the readout (atoms order)',
                'ends_in_scored_text': 'Python code-point end offset of scored token k in scored_text (JS: index '
                                       'Array.from(scored_text), not UTF-16 units); a char split across tokens '
                                       'belongs to the later token, so a piece can be empty',
                'pieces': 'scored_text[ends[k-1]:ends[k]]; concatenation = scored prefix of scored_text',
                'heat': 'joint[k]-joint[k-1] (k=1..n), from 7-decimal rounded joints so sum(heat) = joint[n]-joint[0]',
                'solo': 'FVE of the k-token prefix vector alone', 'joint': 'joint_0..joint_n',
                'joint_cached': 'FVE with b\'s cached full vector (= readout_fve_saved)',
                'drift': 'joint_n - joint_cached (single-pass recompute vs frozen cache; bf16 batch noise)',
                'dup_in_readout': 'another bullet in this readout has the identical cache key (same vector): '
                                  'joint_0 already contains it, so heat ~ 0'},
            'empty_readouts_skipped': 'readouts with 0 bullets produce no lines',
            'telescoping_max_abs_rounded': float(max(tele_r)),
            'telescoping_max_abs_unrounded': max(c['telescoping_max_unrounded'] for c in chunk_stats),
            'joint_cached_vs_saved_max_abs': float(max(cached_saved)),
            'kkt_max': float(max(kkt)),
            'abs_drift': {'median': float(np.median(drift)), 'p90': float(np.quantile(drift, 0.9)),
                          'p99': float(np.quantile(drift, 0.99)), 'max': float(drift.max())},
            'chunks': chunk_stats}
    (HEAT / 'token_heat.meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    log(event='merged', occurrences=len(recs), tokens=tokens, samples=len(samples),
        telescoping_rounded=meta['telescoping_max_abs_rounded'], cached_vs_saved=meta['joint_cached_vs_saved_max_abs'],
        abs_drift=meta['abs_drift'], kkt=meta['kkt_max'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('nnls-selftest', 'test', 'run', 'merge'))
    p.add_argument('--layers', type=int, nargs='*', default=list(LAYERS))
    p.add_argument('--fits', type=int, default=2500)
    p.add_argument('--batch', type=int, default=256)
    args = p.parse_args()
    HEAT.mkdir(parents=True, exist_ok=True)
    try:
        {'nnls-selftest': mode_nnls_selftest, 'test': mode_test, 'run': mode_run, 'merge': mode_merge}[args.mode](args)
    except OwnerBusy as exc:
        log(event='owner_busy_stop', detail=str(exc))
        (HEAT / 'STOPPED_OWNER_BUSY').write_text(json.dumps({'when': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                                                             'detail': str(exc)}) + '\n')
        sys.exit(3)


if __name__ == '__main__':
    main()
