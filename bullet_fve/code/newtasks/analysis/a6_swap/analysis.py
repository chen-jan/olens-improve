"""A6 filler swap, analysis (CPU only; no GPU, no API): does editing ONLY the value word of a lens bullet change its FVE?

Inputs (all read-only): variants.jsonl (build_variants.py), vectors/a6_L*.safetensors (encode_job.py; every original
re-encoded in the same run), the pipeline's cached AR vectors (data/vectors/a451cf49..., via data/select/{fam}_vector_index
.json) for the readout's OTHER bullets, the captured target activations (data/capture/activations.safetensors) and the
pooled whiteners (olens_improve.reconstruction.Whitener, ridge 0.1).

Subcommands (run from newtasks/, each one short mit_quicktest job via code/qt.sh):
  compute   -> cache/a6_variants.pkl (one row per variant), cache/a6_occ.pkl (one row per variant x readout occurrence),
               cache/a6_pool_sd.json (within-cell SD of pool solo FVE, the scale used to express deltas)
  run       -> results.json (all statistics below)
  show VID  print one source bullet with every variant, its texts and FVEs (VID = a variant_id or a source_key)

FVE (identical to data/metrics/*: metrics3.py / JointNNLS.from_raw(solver='scipy_exact')):
  target = whitened activation (magnitude kept); bullet = whitened AR vector / (norm + 1e-9); FVE = 1 - |resid|^2/|t|^2.
  solo FVE  = NNLS on the one bullet = max(0, t.u)^2 / |t|^2 (computed with JointNNLS; the closed form is a check).
  joint FVE = NNLS refit of the readout (<= 4 bullets) with the source slot replaced by the variant's vector and the
              other bullets' cached vectors fixed; one value per readout occurrence (a source can sit in several
              settings' readouts); source-level joint delta = mean over its occurrences.
  Every delta is variant minus the SAME-RUN re-encoded original (not the cached vector): the re-encode differs from
  the cache by bf16 batch noise (whitened rel. L2 <= 5.7%); that cached-vs-re-encoded delta is reported as the
  noise floor.

Variants (build_variants.py): right-value sources -> swap (UM swap_distractor = a WSB distractor of the item; UM
swap_neighbor = a hand-picked close value; CA swap_contrast = the contrast option's X value), synonym (same value, other
surface form; UM includes Chinese translations, kind translation_zh), frame (value kept, one frame/content word changed);
wrong-value sources -> reverse_to_gold (wrong value -> gold value).

Statistics (per family; 'main swap' = UM swap_distractor, CA swap_contrast):
  win_orig     P(original's FVE > variant's FVE), ties 1/2 (paired within source bullet)
  d            mean delta FVE (variant - original), solo and joint; |d| = mean absolute delta
  rel          sum(delta) / sum(original FVE) (ratio of sums)
  cosd         1 - whitened cosine(original, variant) (how far the AR vector moves)
  align        t_hat . (u_variant - u_original) / |u_variant - u_original|: the share of the edit's move that points
               at the target (signed; normalises away the size of the move)
  contrasts    paired on sources that have both variants: swap - synonym, swap - frame, synonym - frame, neighbour -
               distractor (UM), for win_orig, d, |d|, cosd, align
  reverse      wrong-value sources: P(gold edit's FVE > original) and mean delta; value effect
               V = (mean d_reverse - mean d_swap) / 2 (the shared generic edit cost cancels if it is the same size)
Size-matched section (results.json 'size_matched'): every edit pays a cost for moving away from the lens's own text,
  growing with how far the AR vector moves (cosd). Edits are therefore also compared inside 30 strata = cosd decile x
  original-solo tercile (family edges), weighted by the first type's counts ('matched'): swap vs frame / synonym /
  both, and the DIRECTION test reverse vs forward swap; V_matched = half that difference (> 0 = FVE prefers the right
  value net of the edit cost). alpha = cos(target, part of the edited unit vector orthogonal to the original), the
  direction of the move with the geometric cost -(1 - cos_w) * cos_t_o removed. direction_subsets repeats the matched
  tests on challenge subsets (Original setting, tok_delta 0, no CJK, value token < 8 / >= 8, demonym vs country, ...).
Bootstrap: 2,000 reps; ci_groups = related-item groups (UM 31 attr_class:attr groups, CA 10 groups q01..q10; primary,
  as in analysis/um and analysis/ca); ci = items. Ratio-of-sums estimators; one set of weights per family, so all
  contrasts are paired. 'all' pools both families (items/groups prefixed by family).
Strata: layer, read site, setting (occurrence level), value-word token position (start bin and tokens after it),
  tok_delta == 0, CJK in the bullet / CJK value word, UM role (demonym 'adj' vs country 'name' vs person ...), UM in_prompt
  (echo), UM subfamily and attr class, synonym kind, frame kind.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
A6 = NT / 'analysis/a6_swap'
CACHE = A6 / 'cache'
sys.path.insert(0, str(NT / 'code'))
sys.path.insert(0, str(A6))
import ntcommon as C  # noqa: E402

C.setup_paths()

SEED = 20261016
B_BOOT = 2000
FAMS = ('um', 'ca')
FAMNAME = {'um': 'user_modeling', 'ca': 'conjunctive_association'}
SL = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
MAIN_SWAP = {'um': 'swap_distractor', 'ca': 'swap_contrast'}
RIGHT_TYPES = {'um': ('swap_distractor', 'swap_neighbor', 'synonym', 'frame'), 'ca': ('swap_contrast', 'synonym', 'frame')}
CJK = re.compile('[　-鿿＀-￯]')


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def rows_memmap(path, key):
    with open(path, 'rb') as f:
        n = int.from_bytes(f.read(8), 'little')
        header = json.loads(f.read(n))
    info = header[key]
    assert info['dtype'] == 'F32'
    start, _ = info['data_offsets']
    return np.memmap(path, dtype='<f4', mode='r', offset=8 + n + start, shape=tuple(info['shape']))


def case_key(cell_id):
    _, item, layer, pos = cell_id.split('|')
    return f'{item}.{layer}.p{int(pos[1:])}'


# ================================================================================================ compute
def cmd_compute(args):
    import torch
    from olens_improve.reconstruction import JointNNLS, Whitener
    from safetensors.torch import load_file
    import encode_job as E
    import pandas as pd

    torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '4')))
    t0 = time.time()
    CACHE.mkdir(exist_ok=True)
    vpath = A6 / 'variants.jsonl'
    man = json.loads((A6 / 'vectors/manifest.json').read_text())
    vsha = file_sha(vpath)
    if man.get('status') != 'complete' or man.get('fake') or man.get('variants_sha256') != vsha:
        raise SystemExit('vectors/manifest.json is not a complete real run of this variants.jsonl')
    rows = [json.loads(l) for l in open(vpath)]
    log(f'variants {len(rows)}')
    done, _ = E.read_shards(A6 / 'vectors')
    missing = [r['vector_key'] for r in rows if r['vector_key'] not in done]
    if missing:
        raise SystemExit(f'{len(missing)} variants not encoded')
    vindex = {}
    for fam in FAMS:
        vindex[fam] = json.load(open(NT / f'data/select/{fam}_vector_index.json'))['nt']
    log('vector indexes loaded')
    acts = rows_memmap(C.DATA / 'capture/activations.safetensors', 'resid')

    src = collections.defaultdict(list)
    for r in rows:
        src[(r['family'], r['source_key'])].append(r)
    by_layer = collections.defaultdict(list)
    for k, vs in src.items():
        by_layer[vs[0]['layer']].append(k)
    tag = ''
    if args.test:  # quick smoke run: 30 sources of each family at one layer, separate output files
        tag = 'test_'
        keep = [k for k in by_layer[44] if k[0] == 'um'][:30] + [k for k in by_layer[44] if k[0] == 'ca'][:30]
        by_layer = {44: keep}

    var_out, occ_out = [], []
    chk = collections.Counter()
    mx = collections.defaultdict(float)
    for L in sorted(by_layer):
        tl = time.time()
        w = Whitener.load(str(C.WHITENERS / f'whitening_iolens_pooled_L{L}.safetensors'))
        keys = by_layer[L]
        vrows = [v for k in keys for v in src[k]]
        # ---- A6 vectors (this run)
        files = collections.defaultdict(list)
        for i, v in enumerate(vrows):
            p, row = done[v['vector_key']]
            files[str(p)].append((i, row))
        raw = torch.empty((len(vrows), 5120), dtype=torch.float32)
        for p, items in files.items():
            T = load_file(p)['vectors']
            idx = torch.tensor([r for _, r in items])
            raw[torch.tensor([i for i, _ in items])] = T[idx].float()
            del T
        wv = torch.cat([w.whiten(raw[i:i + 4096]) for i in range(0, len(raw), 4096)])
        unit = wv / (wv.norm(dim=1, keepdim=True) + 1e-9)
        vi = {v['variant_id']: i for i, v in enumerate(vrows)}
        # ---- cached vectors: every slot of every readout occurrence + each original's own cached vector
        need = {}
        for k in keys:
            fam = k[0]
            o = next(v for v in src[k] if v['variant_type'] == 'original')
            for occ in o['occurrences']:
                if any(ck is None for ck in occ['readout_cache_keys']):
                    continue
                for ck in occ['readout_cache_keys']:
                    need[ck] = tuple(vindex[fam][ck])
            need[o['original_cache_key']] = tuple(o['cached_vector'])
        cfiles = collections.defaultdict(list)
        for ck, (p, row) in need.items():
            cfiles[p].append((row, ck))
        ckeys, cblocks = [], []
        for p, items in cfiles.items():
            mm = rows_memmap(p, 'vectors')
            items.sort()
            cblocks.append(np.asarray(mm[[r for r, _ in items]]))
            ckeys += [ck for _, ck in items]
        craw = torch.from_numpy(np.concatenate(cblocks))
        cw = torch.cat([w.whiten(craw[i:i + 4096]) for i in range(0, len(craw), 4096)])
        cunit = cw / (cw.norm(dim=1, keepdim=True) + 1e-9)
        ci = {ck: i for i, ck in enumerate(ckeys)}
        log(f'L{L}: {len(keys)} sources, {len(vrows)} variants, {len(ckeys)} cached vectors')
        # ---- per source
        for k in keys:
            vs = src[k]
            o = next(v for v in vs if v['variant_type'] == 'original')
            t_raw = torch.from_numpy(np.asarray(acts[o['activation_row']]).copy())
            assert hashlib.sha256(t_raw.numpy().tobytes()).hexdigest() == o['activation_sha256'], o['cell_id']
            t = w.whiten(t_raw.reshape(1, -1))[0]
            tt = float(t.double().square().sum())
            that = t.double() / math.sqrt(tt)
            io = vi[o['variant_id']]
            uo = unit[io].double()
            vec = {v['variant_id']: unit[vi[v['variant_id']]] for v in vs}
            cache_id = 'CACHED::' + o['original_cache_key']
            vec[cache_id] = cunit[ci[o['original_cache_key']]]
            scorer = JointNNLS(t, vec, solver='scipy_exact')
            solo_cached = scorer.fit([cache_id]).fve
            for v in vs:
                i = vi[v['variant_id']]
                u = unit[i].double()
                solo = scorer.fit([v['variant_id']]).fve
                closed = max(0.0, float(u @ t.double())) ** 2 / (float(u @ u) * tt)
                mx['solo_nnls_minus_closed'] = max(mx['solo_nnls_minus_closed'], abs(solo - closed))
                cos_w = float(torch.nn.functional.cosine_similarity(wv[i].double(), wv[io].double(), dim=0))
                cos_raw = float(torch.nn.functional.cosine_similarity(raw[i].double(), raw[io].double(), dim=0))
                rel_w = float((wv[i].double() - wv[io].double()).norm() / wv[io].double().norm())
                dv = u - uo
                dn = float(dv.norm())
                align = float(that @ dv) / dn if dn > 0 else float('nan')
                rec = {c: v.get(c) for c in (
                    'variant_id', 'family', 'source_key', 'variant_type', 'source_kind', 'cell_id', 'item_id', 'group_id',
                    'layer', 'position', 'read_site', 'setting', 'bullet_index', 'value_from', 'value_surface', 'gold',
                    'role', 'attr_class', 'subfamily', 'in_prompt', 'wrong_subtype', 'label_full', 'contrast',
                    'contrast_axis', 'cluster', 'clean_item', 'lex2_full', 'llm_label', 'tok_delta', 'char_delta',
                    'edit_tok_orig', 'edit_tok_new', 'original_text', 'edited_text', 'vector_key', 'pool_solo_fve')}
                ed = v.get('edit') or {}
                rec.update({'edit_before': ed.get('before'), 'edit_after': ed.get('after'), 'value_to': ed.get('value_to'),
                            'synonym_kind': ed.get('synonym_kind'), 'frame_kind': ed.get('frame_kind'),
                            'edit_notes': ','.join(ed.get('notes') or []),
                            'neighbor_as_distractor': bool(ed.get('neighbor_as_distractor')),
                            'n_tok': len(v['ar_ids32']), 'solo': solo, 'cos_t': float(u @ that),
                            'cos_w': cos_w, 'cos_raw': cos_raw, 'rel_l2_w': rel_w, 'align': align,
                            'n_occ': len(o['occurrences'])})
                if v['variant_type'] == 'original':
                    rec['solo_cached'] = solo_cached
                    rec['cos_w_cached'] = float(torch.nn.functional.cosine_similarity(
                        wv[io].double(), cw[ci[o['original_cache_key']]].double(), dim=0))
                    if v.get('pool_solo_fve') is not None:
                        mx['solo_cached_minus_pool_saved'] = max(mx['solo_cached_minus_pool_saved'],
                                                                 abs(solo_cached - v['pool_solo_fve']))
                        chk['solo_cached_vs_pool_saved'] += 1
                var_out.append(rec)
            # joint, per readout occurrence
            for oi, occ in enumerate(o['occurrences']):
                ks = occ['readout_cache_keys']
                if any(ck is None for ck in ks):
                    chk['occ_unscored_skipped'] += 1
                    continue
                b = occ['bullet_index']
                assert ks[b] == o['original_cache_key'], (k, oi)
                ovec = {f's{j}': cunit[ci[ck]] for j, ck in enumerate(ks)}
                ovec.update({v['variant_id']: vec[v['variant_id']] for v in vs})
                # duplicate slot: two slots with one cached vector make JointNNLS ids distinct anyway (s0/s1)
                sc = JointNNLS(t, ovec, solver='scipy_exact')
                base = [f's{j}' for j in range(len(ks))]
                f_cached = sc.fit(base)
                if occ.get('readout_fve_saved') is not None:
                    d = abs(f_cached.fve - occ['readout_fve_saved'])
                    mx['joint_cached_minus_saved'] = max(mx['joint_cached_minus_saved'], d)
                    chk['joint_checked'] += 1
                    chk['joint_diff_gt_1e-6'] += d > 1e-6
                dup = ks.count(ks[b]) > 1
                chk['occ_dup_source'] += dup
                for v in vs:
                    ids = list(base)
                    ids[b] = v['variant_id']
                    f = sc.fit(ids)
                    occ_out.append({'variant_id': v['variant_id'], 'family': v['family'], 'source_key': v['source_key'],
                                    'variant_type': v['variant_type'], 'occ': oi, 'setting': occ['setting'],
                                    'bullet_index': b, 'n_bullets': len(ks), 'dup_source': dup, 'joint': f.fve,
                                    'coef_slot': f.coefficients[b], 'joint_cached_orig': f_cached.fve,
                                    'joint_saved': occ.get('readout_fve_saved')})
        log(f'L{L}: done in {time.time() - tl:.1f}s')
        del raw, wv, unit, craw, cw, cunit
    V = pd.DataFrame(var_out)
    O = pd.DataFrame(occ_out)
    V.to_pickle(CACHE / f'{tag}a6_variants.pkl')
    O.to_pickle(CACHE / f'{tag}a6_occ.pkl')
    if args.test:
        log(json.dumps({'checks': dict(chk), 'max_abs': dict(mx), 'rows': len(V), 'occ': len(O),
                        'seconds': round(time.time() - t0, 1)}))
        return

    # ---- within-cell SD of pool solo FVE for the cells that hold A6 sources (scale for deltas)
    cells = {fam: set(V[V.family == fam].cell_id) for fam in FAMS}
    sd = {}
    for fam in FAMS:
        ss, nn, ncell = 0.0, 0, 0
        with open(NT / f'data/select/{fam}_pool.jsonl') as f:
            for line in f:
                c = json.loads(line)
                if c['cell_id'] not in cells[fam]:
                    continue
                x = np.array([b['solo_fve'] for b in c['bullets'] if b.get('solo_fve') is not None], float)
                if len(x) > 1:
                    ss += float(((x - x.mean()) ** 2).sum())
                    nn += len(x) - 1
                    ncell += 1
        sd[fam] = {'within_cell_sd_pool_solo': math.sqrt(ss / nn), 'cells': ncell}
    meta = {'variants_sha256': vsha, 'rows': len(V), 'occ_rows': len(O), 'checks': dict(chk),
            'max_abs': dict(mx), 'pool_sd': sd, 'seconds': round(time.time() - t0, 1),
            'host': os.uname().nodename, 'slurm_job_id': os.environ.get('SLURM_JOB_ID')}
    (CACHE / 'a6_compute_meta.json').write_text(json.dumps(meta, indent=1))
    log(json.dumps(meta))


# ================================================================================================ bootstrap
class Boot:
    """Ratio-of-sums bootstrap over items and related-item groups; the same weights for every statistic."""

    def __init__(self, item_group, B=B_BOOT, seed=SEED):
        self.items = sorted(item_group)
        self.ii = {it: k for k, it in enumerate(self.items)}
        self.cl = sorted(set(item_group.values()))
        self.icl = np.array([self.cl.index(item_group[it]) for it in self.items])
        rng = np.random.default_rng(seed)
        n, m = len(self.items), len(self.cl)
        self.Wi = rng.multinomial(n, np.full(n, 1 / n), size=B).astype(float)
        self.Wc = rng.multinomial(m, np.full(m, 1 / m), size=B).astype(float)

    def agg(self, items, num, den=None):
        idx = np.array([self.ii[i] for i in items], dtype=int)
        num = np.asarray(num, float)
        den = np.ones_like(num) if den is None else np.asarray(den, float)
        n = len(self.items)
        return np.bincount(idx, num, n), np.bincount(idx, den, n)

    def reps(self, N, D):
        m = len(self.cl)
        Nc, Dc = np.bincount(self.icl, N, m), np.bincount(self.icl, D, m)
        with np.errstate(invalid='ignore', divide='ignore'):
            return (self.Wi @ N) / (self.Wi @ D), (self.Wc @ Nc) / (self.Wc @ Dc)


def _ci(x, nd):
    x = x[np.isfinite(x)]
    if not len(x):
        return None
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [round(float(lo), nd), round(float(hi), nd)]


def est(bt, items, x, nd=4):
    """Mean of x (ratio of sums over items) with item and group CIs. NaNs dropped."""
    items = np.asarray(items)
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    if not ok.any():
        return None
    N, D = bt.agg(items[ok], x[ok])
    ri, rc = bt.reps(N, D)
    return {'est': round(float(N.sum() / D.sum()), nd), 'ci': _ci(ri, nd), 'ci_groups': _ci(rc, nd),
            'n': int(ok.sum()), 'items': int((D > 0).sum()), 'groups': int(len(set(bt.icl[D > 0])))}


def est_ratio(bt, items, num, den, nd=4):
    items = np.asarray(items)
    num, den = np.asarray(num, float), np.asarray(den, float)
    ok = np.isfinite(num) & np.isfinite(den)
    N, _ = bt.agg(items[ok], num[ok])
    D, _ = bt.agg(items[ok], den[ok])
    ri, rc = bt.reps(N, D)
    return {'est': round(float(N.sum() / D.sum()), nd), 'ci': _ci(ri, nd), 'ci_groups': _ci(rc, nd), 'n': int(ok.sum())}


def est_diff(bt, items1, x1, items2, x2, scale=1.0, nd=4):
    """(mean x1 - mean x2) * scale, unpaired populations but the same bootstrap weights."""
    i1, i2 = np.asarray(items1), np.asarray(items2)
    x1, x2 = np.asarray(x1, float), np.asarray(x2, float)
    o1, o2 = np.isfinite(x1), np.isfinite(x2)
    if not o1.any() or not o2.any():
        return None
    a = bt.reps(*bt.agg(i1[o1], x1[o1]))
    b = bt.reps(*bt.agg(i2[o2], x2[o2]))
    e = (x1[o1].mean() - x2[o2].mean()) * scale
    return {'est': round(float(e), nd), 'ci': _ci((a[0] - b[0]) * scale, nd), 'ci_groups': _ci((a[1] - b[1]) * scale, nd)}


def quant(x, nd=5):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if not len(x):
        return None
    q = np.percentile(x, [1, 5, 25, 50, 75, 95, 99])
    return {'n': int(len(x)), 'mean': round(float(x.mean()), nd), 'p01': round(float(q[0]), nd),
            'p05': round(float(q[1]), nd), 'p25': round(float(q[2]), nd), 'median': round(float(q[3]), nd),
            'p75': round(float(q[4]), nd), 'p95': round(float(q[5]), nd), 'p99': round(float(q[6]), nd)}


# ================================================================================================ tables
def load_tables():
    import pandas as pd
    V = pd.read_pickle(CACHE / 'a6_variants.pkl')
    O = pd.read_pickle(CACHE / 'a6_occ.pkl')
    meta = json.loads((CACHE / 'a6_compute_meta.json').read_text())
    return V, O, meta


def item_groups():
    um = C.load_bank(FAMNAME['um'])
    ca = C.load_bank(FAMNAME['ca'])
    return ({k: f"{it['attr_class']}:{it['attr']}" for k, it in um.items()}, {k: it['cluster'] for k, it in ca.items()})


def build_wide(V, O):
    """Source-level and occurrence-level wide tables: one row per source (per source x occurrence), one block of
    columns per variant type (d_solo_T, win_T, d_joint_T, winj_T, cosd_T, align_T, ...)."""
    import pandas as pd
    orig = V[V.variant_type == 'original'].set_index(['family', 'source_key'])
    ed = V[V.variant_type != 'original'].copy()
    ok = orig.loc[list(zip(ed.family, ed.source_key))]
    ed['solo_o'] = ok.solo.to_numpy()
    ed['d_solo'] = ed.solo - ed.solo_o
    ed['win'] = (ed.solo_o > ed.solo) + 0.5 * (ed.solo_o == ed.solo)
    ed['tie'] = ed.solo_o == ed.solo
    ed['cosd'] = 1 - ed.cos_w
    # direction-only metric: cosine between the target and the part of the edit orthogonal to the original vector
    # (removes the geometric cost -(1 - cos_w) * cos_t_o that any move on the unit sphere pays)
    ed['cos_t_o'] = ok.cos_t.to_numpy()
    ed['alpha'] = (ed.cos_t - ed.cos_w * ed.cos_t_o) / np.sqrt(np.clip(1 - ed.cos_w ** 2, 1e-12, None))
    ed['geo'] = -(1 - ed.cos_w) * ed.cos_t_o
    # occurrence-level joint
    Oo = O[O.variant_type == 'original'][['family', 'source_key', 'occ', 'joint']].rename(columns={'joint': 'joint_o'})
    Oe = O[O.variant_type != 'original'].merge(Oo, on=['family', 'source_key', 'occ'], how='left')
    Oe['d_joint'] = Oe.joint - Oe.joint_o
    Oe['winj'] = (Oe.joint_o > Oe.joint) + 0.5 * (Oe.joint_o == Oe.joint)
    Oe['tiej'] = Oe.joint_o == Oe.joint
    g = Oe.groupby('variant_id')
    jj = pd.DataFrame({'d_joint': g.d_joint.mean(), 'winj': g.winj.mean(), 'joint': g.joint.mean(),
                       'joint_o': g.joint_o.mean(), 'tiej': g.tiej.mean()})
    ed = ed.join(jj, on='variant_id')
    # source attributes
    s = orig.reset_index()
    s['cjk_bullet'] = s.original_text.map(lambda x: bool(CJK.search(x)))
    s['cjk_value'] = s.value_surface.map(lambda x: bool(CJK.search(x or '')))
    # value-word token position from the main value edit of the source (swap or reverse: edit spans the value)
    vt = ed[ed.variant_type.isin(['swap_distractor', 'swap_contrast', 'reverse_to_gold'])]
    vpos = {(f, sk): (e[0], e[1]) for f, sk, e in zip(vt.family, vt.source_key, vt.edit_tok_orig)}
    s['val_tok0'] = [vpos.get((f, sk), (np.nan, np.nan))[0] for f, sk in zip(s.family, s.source_key)]
    s['val_tok1'] = [vpos.get((f, sk), (np.nan, np.nan))[1] for f, sk in zip(s.family, s.source_key)]
    s['tok_after'] = s.n_tok - s.val_tok1
    s['val_rel'] = s.val_tok0 / s.n_tok
    s['noise_d_solo'] = s.solo - s.solo_cached
    attrs = s.set_index(['family', 'source_key'])
    cols = ['d_solo', 'win', 'tie', 'd_joint', 'winj', 'tiej', 'cosd', 'align', 'alpha', 'solo', 'joint', 'joint_o', 'tok_delta',
            'char_delta',
            'synonym_kind', 'frame_kind', 'variant_id', 'edit_before', 'edit_after', 'edited_text', 'value_to', 'edit_tok_orig',
            'neighbor_as_distractor']
    wide = attrs.copy()
    for T, d in ed.groupby('variant_type'):
        d = d.set_index(['family', 'source_key'])[cols]
        d.columns = [f'{c}_{T}' for c in cols]
        wide = wide.join(d)
    wide = wide.reset_index()
    # occurrence-level wide (for the by-setting strata): solo columns replicated per occurrence
    Oe2 = Oe[['family', 'source_key', 'occ', 'setting', 'variant_type', 'd_joint', 'winj', 'dup_source', 'n_bullets']]
    occw = Oo.merge(O[O.variant_type == 'original'][['family', 'source_key', 'occ', 'setting', 'dup_source', 'n_bullets']],
                    on=['family', 'source_key', 'occ'])
    for T, d in Oe2.groupby('variant_type'):
        d = d[['family', 'source_key', 'occ', 'd_joint', 'winj']].rename(columns={'d_joint': f'd_joint_{T}', 'winj': f'winj_{T}'})
        occw = occw.merge(d, on=['family', 'source_key', 'occ'], how='left')
    keep = [c for c in wide.columns if not c.startswith(('d_joint_', 'winj_', 'tiej_', 'joint_'))]
    occw = occw.merge(wide[keep], on=['family', 'source_key'], how='left', suffixes=('', '_src'))
    return wide, occw, ed, Oe


# ================================================================================================ statistics
def summ_type(bt, W, T, *, reverse=False, occ=False):
    """One variant type on the rows of W that have it."""
    m = W[f'd_solo_{T}'].notna() if not occ else W[f'd_joint_{T}'].notna()
    d = W[m]
    if not len(d):
        return None
    it = d.item_id.to_numpy()
    out = {'n_sources': int(len(d))}
    if not occ:
        win = d[f'win_{T}'].to_numpy(float)
        out['p_orig_gt_edit_solo'] = est(bt, it, win)
        if reverse:
            out['p_edit_gt_orig_solo'] = est(bt, it, 1 - win)
        out['ties_solo'] = int(d[f'tie_{T}'].sum())
        out['mean_d_solo'] = est(bt, it, d[f'd_solo_{T}'], nd=5)
        out['mean_abs_d_solo'] = est(bt, it, d[f'd_solo_{T}'].abs(), nd=5)
        out['rel_d_solo'] = est_ratio(bt, it, d[f'd_solo_{T}'], d['solo'])
        out['mean_orig_solo'] = round(float(d['solo'].mean()), 5)
        out['mean_cosd'] = est(bt, it, d[f'cosd_{T}'], nd=5)
        out['mean_align'] = est(bt, it, d[f'align_{T}'], nd=5)
        out['quant_d_solo'] = quant(d[f'd_solo_{T}'])
        out['quant_cos_w'] = quant(1 - d[f'cosd_{T}'], nd=5)
        out['quant_tok_delta'] = quant(d[f'tok_delta_{T}'], nd=2)
    wj = d[f'winj_{T}'].to_numpy(float)
    out['p_orig_gt_edit_joint'] = est(bt, it, wj)
    if reverse:
        out['p_edit_gt_orig_joint'] = est(bt, it, 1 - wj)
    out['mean_d_joint'] = est(bt, it, d[f'd_joint_{T}'], nd=5)
    out['mean_abs_d_joint'] = est(bt, it, d[f'd_joint_{T}'].abs(), nd=5)
    if not occ:
        out['quant_d_joint'] = quant(d[f'd_joint_{T}'])
    return out


def contrast(bt, W, A, B, occ=False):
    """Paired A - B on sources holding both variant types."""
    a_col = f'd_solo_{A}' if not occ else f'd_joint_{A}'
    b_col = f'd_solo_{B}' if not occ else f'd_joint_{B}'
    if a_col not in W or b_col not in W:
        return None
    d = W[W[a_col].notna() & W[b_col].notna()]
    if not len(d):
        return None
    it = d.item_id.to_numpy()
    out = {'n_sources': int(len(d))}
    if not occ:
        out['win_orig_solo'] = est(bt, it, d[f'win_{A}'] - d[f'win_{B}'])
        out['d_solo'] = est(bt, it, d[f'd_solo_{A}'] - d[f'd_solo_{B}'], nd=5)
        out['abs_d_solo'] = est(bt, it, d[f'd_solo_{A}'].abs() - d[f'd_solo_{B}'].abs(), nd=5)
        out['abs_ratio_solo'] = est_ratio(bt, it, d[f'd_solo_{A}'].abs(), d[f'd_solo_{B}'].abs(), nd=3)
        out['cosd'] = est(bt, it, d[f'cosd_{A}'] - d[f'cosd_{B}'], nd=5)
        out['align'] = est(bt, it, d[f'align_{A}'] - d[f'align_{B}'], nd=5)
        # P(the A edit lowers FVE more than the B edit), ties 1/2
        x = (d[f'd_solo_{A}'] < d[f'd_solo_{B}']) + 0.5 * (d[f'd_solo_{A}'] == d[f'd_solo_{B}'])
        out['p_A_lower_than_B_solo'] = est(bt, it, x)
    out['win_orig_joint'] = est(bt, it, d[f'winj_{A}'] - d[f'winj_{B}'])
    out['d_joint'] = est(bt, it, d[f'd_joint_{A}'] - d[f'd_joint_{B}'], nd=5)
    out['abs_d_joint'] = est(bt, it, d[f'd_joint_{A}'].abs() - d[f'd_joint_{B}'].abs(), nd=5)
    return out


CONTRASTS = {'um': [('swap_distractor', 'synonym'), ('swap_distractor', 'frame'), ('synonym', 'frame'),
                    ('swap_neighbor', 'synonym'), ('swap_neighbor', 'swap_distractor'), ('swap_neighbor', 'frame')],
             'ca': [('swap_contrast', 'synonym'), ('swap_contrast', 'frame'), ('synonym', 'frame')]}


def compact(bt, W, fam, occ=False):
    """Short per-stratum block: main swap, synonym, frame (+ neighbour), and swap - synonym."""
    S = MAIN_SWAP[fam]
    right = W[W.source_kind == 'right']
    out = {'n_sources': int(len(right)), 'items': int(right.item_id.nunique())}
    if not len(right):
        return out
    types = RIGHT_TYPES[fam]
    for T in types:
        col = f'd_solo_{T}' if not occ else f'd_joint_{T}'
        d = right[right[col].notna()]
        if len(d) < 5:
            continue
        it = d.item_id.to_numpy()
        blk = {'n': int(len(d))}
        if not occ:
            blk['p_orig_gt_solo'] = est(bt, it, d[f'win_{T}'], nd=3)
            blk['mean_d_solo'] = est(bt, it, d[f'd_solo_{T}'], nd=4)
            blk['mean_abs_d_solo'] = round(float(d[f'd_solo_{T}'].abs().mean()), 4)
            blk['mean_cosd'] = round(float(d[f'cosd_{T}'].mean()), 4)
        blk['p_orig_gt_joint'] = est(bt, it, d[f'winj_{T}'], nd=3)
        blk['mean_d_joint'] = est(bt, it, d[f'd_joint_{T}'], nd=4)
        out[T] = blk
    if len(right) >= 5:
        c = {}
        for A, B in ((S, 'synonym'), (S, 'frame')) + ((('swap_neighbor', 'synonym'),) if fam == 'um' else ()):
            cc = contrast(bt, right, A, B, occ=occ)
            if cc and cc['n_sources'] >= 5:
                c[f'{A}-{B}'] = ({'n': cc['n_sources'], 'win_orig_solo': cc['win_orig_solo'], 'd_solo': cc['d_solo'],
                                  'win_orig_joint': cc['win_orig_joint'], 'd_joint': cc['d_joint']} if not occ else
                                 {'n': cc['n_sources'], 'win_orig_joint': cc['win_orig_joint'], 'd_joint': cc['d_joint']})
        out['contrasts'] = c
    wrong = W[W.source_kind == 'wrong']
    col = 'd_solo_reverse_to_gold' if not occ else 'd_joint_reverse_to_gold'
    if col in wrong and wrong[col].notna().sum() >= 5:
        d = wrong[wrong[col].notna()]
        it = d.item_id.to_numpy()
        blk = {'n': int(len(d))}
        if not occ:
            blk['p_gold_gt_wrong_solo'] = est(bt, it, 1 - d['win_reverse_to_gold'], nd=3)
            blk['mean_d_solo'] = est(bt, it, d['d_solo_reverse_to_gold'], nd=4)
        blk['p_gold_gt_wrong_joint'] = est(bt, it, 1 - d['winj_reverse_to_gold'], nd=3)
        blk['mean_d_joint'] = est(bt, it, d['d_joint_reverse_to_gold'], nd=4)
        out['reverse_to_gold'] = blk
    return out


def strata(bt, W, fam, col, occ=False, order=None, min_n=20):
    vals = order or sorted(W[col].dropna().unique(), key=str)
    out = {}
    for v in vals:
        d = W[W[col] == v]
        if (d.source_kind == 'right').sum() < min_n:
            continue
        out[str(v)] = compact(bt, d, fam, occ=occ)
    return out


def bin_pos(x):
    if not np.isfinite(x):
        return None
    return '0-3' if x < 4 else '4-7' if x < 8 else '8-15' if x < 16 else '16-31'


def bin_after(x):
    if not np.isfinite(x):
        return None
    return '0-3' if x < 4 else '4-11' if x < 12 else '12+'


def cmd_run(args):
    import pandas as pd
    t0 = time.time()
    V, O, meta = load_tables()
    um_g, ca_g = item_groups()
    W, OW, ED, OE = build_wide(V, O)
    for D in (W, OW):
        D['group'] = [um_g[i] if f == 'um' else ca_g[i] for f, i in zip(D.family, D.item_id)]
        D['val_pos_bin'] = D.val_tok0.map(bin_pos)
        D['tok_after_bin'] = D.tok_after.map(bin_after)
        D['val_half'] = np.where(D.val_rel < 0.5, 'first half', 'second half')
    log(f'wide: {len(W)} sources, {len(OW)} source occurrences')
    BT = {'um': Boot({i: g for i, g in um_g.items() if i in set(W[W.family == 'um'].item_id)}),
          'ca': Boot({i: g for i, g in ca_g.items() if i in set(W[W.family == 'ca'].item_id)})}
    allmap = {f'{f}:{i}': f'{f}:{g}' for f, mp in (('um', um_g), ('ca', ca_g)) for i, g in mp.items()
              if i in set(W[W.family == f].item_id)}
    BT['all'] = Boot(allmap)
    R = {'meta': {'compute': meta, 'bootstrap': {'B': B_BOOT, 'seed': SEED,
                                                 'units': 'ci_groups = related-item groups (UM 31 attr_class:attr, CA 10 '
                                                          'q01..q10; primary); ci = items'},
                  'n_sources': {f: {k: int(v) for k, v in W[W.family == f].source_kind.value_counts().items()} for f in FAMS},
                  'n_items': {f: int(W[W.family == f].item_id.nunique()) for f in FAMS},
                  'n_groups': {f: int(W[W.family == f].group.nunique()) for f in FAMS},
                  'variant_counts': {f'{f}|{t}': int(n) for (f, t), n in V.groupby(['family', 'variant_type']).size().items()}}}

    # ---- checks and noise floor (cached vs same-run re-encoded original)
    orig = W
    nz = {}
    for fam in FAMS:
        d = orig[orig.family == fam]
        bt = BT[fam]
        it = d.item_id.to_numpy()
        x = d.noise_d_solo.to_numpy()
        oo = O[(O.family == fam) & (O.variant_type == 'original')]
        xj = (oo.joint - oo.joint_cached_orig).to_numpy()
        nz[fam] = {'n': int(len(d)), 'frac_identical_solo': round(float((x == 0).mean()), 4),
                   'mean_abs_d_solo': est(bt, it, np.abs(x), nd=6), 'quant_abs_d_solo': quant(np.abs(x), nd=6),
                   'p_cached_gt_reencoded_nonidentical': round(float(((x < 0).sum()) / max(1, (x != 0).sum())), 4),
                   'quant_abs_d_joint': quant(np.abs(xj), nd=6),
                   'whitened_cos_cached_vs_reencoded': quant(d.cos_w_cached, nd=6)}
    R['checks'] = {'max_abs': meta['max_abs'], 'counts': meta['checks'], 'noise_floor_reencode': nz,
                   'pool_within_cell_sd': meta['pool_sd']}

    # ---- headline per family
    H = {}
    for fam in FAMS + ('all',):
        Wf = W if fam == 'all' else W[W.family == fam]
        Wf = Wf.copy()
        if fam == 'all':
            Wf['item_id'] = Wf.family + ':' + Wf.item_id
            # pooled main swap column
            for c in ('d_solo', 'win', 'tie', 'd_joint', 'winj', 'cosd', 'align', 'tok_delta'):
                Wf[f'{c}_mainswap'] = Wf[f'{c}_swap_distractor'].where(Wf.family == 'um', Wf[f'{c}_swap_contrast'])
        bt = BT[fam]
        right = Wf[Wf.source_kind == 'right']
        wrong = Wf[Wf.source_kind == 'wrong']
        types = RIGHT_TYPES[fam] if fam != 'all' else ('mainswap', 'synonym', 'frame')
        h = {'right': {T: summ_type(bt, right, T) for T in types},
             'reverse_to_gold': summ_type(bt, wrong, 'reverse_to_gold', reverse=True)}
        S = MAIN_SWAP.get(fam, 'mainswap')
        pairs = CONTRASTS.get(fam, [('mainswap', 'synonym'), ('mainswap', 'frame'), ('synonym', 'frame')])
        h['contrasts'] = {f'{A}-{B}': contrast(bt, right, A, B) for A, B in pairs}
        # value effect from the two directions: V = (mean d_reverse - mean d_swap) / 2 ; E = (d_rev + d_swap) / 2
        h['value_effect_two_directions'] = {
            'V_solo': est_diff(bt, wrong.item_id, wrong.d_solo_reverse_to_gold, right.item_id, right[f'd_solo_{S}'], 0.5, nd=5),
            'V_joint': est_diff(bt, wrong.item_id, wrong.d_joint_reverse_to_gold, right.item_id, right[f'd_joint_{S}'], 0.5, nd=5),
            'P_rev_edit_wins_minus_P_swap_edit_wins_solo': est_diff(
                bt, wrong.item_id, 1 - wrong.win_reverse_to_gold, right.item_id, 1 - right[f'win_{S}'], 1.0),
            'note': 'V > 0 means FVE prefers the right value: correcting a wrong value raises FVE more than breaking a '
                    'right one lowers it would predict under a value-blind FVE (different source sets, same weights)'}
        if fam != 'all':
            sd = meta['pool_sd'][fam]['within_cell_sd_pool_solo']
            sw = h['right'][S]
            h['scale'] = {'within_cell_sd_pool_solo': round(sd, 4),
                          'mean_d_solo_swap_in_sd': round(sw['mean_d_solo']['est'] / sd, 3),
                          'mean_abs_d_solo_swap_in_sd': round(sw['mean_abs_d_solo']['est'] / sd, 3),
                          'mean_abs_d_solo_synonym_in_sd': round(h['right']['synonym']['mean_abs_d_solo']['est'] / sd, 3),
                          'mean_abs_d_solo_frame_in_sd': round(h['right']['frame']['mean_abs_d_solo']['est'] / sd, 3)}
        H[fam] = h
    R['headline'] = H

    # ---- strata
    ST = {}
    for fam in FAMS:
        Wf = W[W.family == fam]
        OWf = OW[OW.family == fam]
        bt = BT[fam]
        st = {'layer': strata(bt, Wf, fam, 'layer'),
              'read_site': strata(bt, Wf, fam, 'read_site'),
              'setting_solo': {SL[s]: compact(bt, OWf[OWf.setting == s].drop_duplicates('source_key'), fam)
                               for s in SL},
              'setting_joint_occ': {SL[s]: compact(bt, OWf[OWf.setting == s], fam, occ=True) for s in SL},
              'value_tok_start': strata(bt, Wf, fam, 'val_pos_bin', order=['0-3', '4-7', '8-15', '16-31']),
              'tokens_after_value': strata(bt, Wf, fam, 'tok_after_bin', order=['0-3', '4-11', '12+']),
              'value_half': strata(bt, Wf, fam, 'val_half'),
              'cjk_bullet': strata(bt, Wf, fam, 'cjk_bullet'),
              'cjk_value': strata(bt, Wf, fam, 'cjk_value', min_n=10)}
        if fam == 'um':
            Wf2 = Wf.copy()
            Wf2['role2'] = Wf2.role.map(lambda r: r if r in ('adj', 'name', 'person', 'sg') else
                                        ('cjk' if str(r).startswith('cjk') else 'other'))
            st['role'] = strata(bt, Wf2, fam, 'role2', min_n=10)
            st['in_prompt'] = strata(bt, Wf, fam, 'in_prompt')
            st['subfamily'] = strata(bt, Wf, fam, 'subfamily')
            st['attr_class'] = strata(bt, Wf, fam, 'attr_class', min_n=15)
            st['subfamily_x_in_prompt'] = strata(bt, Wf.assign(sx=Wf.subfamily + '|' + Wf.in_prompt.astype(str)), fam, 'sx')
            st['reverse_by_wrong_subtype'] = {str(k): compact(bt, Wf[(Wf.source_kind == 'right') | (Wf.wrong_subtype == k)], fam)
                                              .get('reverse_to_gold') for k in ('distractor', 'other_value')}
        else:
            st['clean_item'] = strata(bt, Wf, fam, 'clean_item')
            st['llm_label'] = strata(bt, Wf, fam, 'llm_label', min_n=15)
            st['contrast_axis'] = strata(bt, Wf, fam, 'contrast_axis', min_n=15)
        ST[fam] = st
    R['strata'] = ST

    # ---- challenges
    CH = {}
    for fam in FAMS:
        Wf = W[W.family == fam]
        bt = BT[fam]
        S = MAIN_SWAP[fam]
        right = Wf[Wf.source_kind == 'right']
        c = {}
        # 1. tokenisation length: only edits that keep the token count
        r0 = right[(right[f'tok_delta_{S}'] == 0)]
        c['swap_tok_delta0'] = {'swap': summ_type(bt, r0, S)}
        r00 = right[(right[f'tok_delta_{S}'] == 0) & (right.tok_delta_synonym == 0)]
        c['swap_and_synonym_tok_delta0'] = {'n': int(len(r00)), 'swap-synonym': contrast(bt, r00, S, 'synonym'),
                                            'swap': summ_type(bt, r00, S), 'synonym': summ_type(bt, r00, 'synonym')}
        r000 = r00[r00.tok_delta_frame == 0]
        c['all_three_tok_delta0'] = {'n': int(len(r000)), 'swap-synonym': contrast(bt, r000, S, 'synonym'),
                                     'swap-frame': contrast(bt, r000, S, 'frame'),
                                     'synonym-frame': contrast(bt, r000, 'synonym', 'frame')}
        # |d| vs |tok_delta| (all right-source edits pooled)
        rows = []
        for T in RIGHT_TYPES[fam]:
            d = right[right[f'd_solo_{T}'].notna()]
            for td, dd in d.groupby(d[f'tok_delta_{T}'].abs().clip(upper=2)):
                rows.append({'type': T, 'abs_tok_delta': int(td), 'n': int(len(dd)),
                             'mean_abs_d_solo': round(float(dd[f'd_solo_{T}'].abs().mean()), 5),
                             'mean_d_solo': round(float(dd[f'd_solo_{T}'].mean()), 5),
                             'p_orig_gt': round(float(dd[f'win_{T}'].mean()), 3),
                             'mean_cosd': round(float(dd[f'cosd_{T}'].mean()), 5)})
        c['by_abs_tok_delta'] = rows
        # 2. selection: Original setting only (first sample, not chosen by FVE)
        OWf = OW[(OW.family == fam) & (OW.setting == 'capped_n1-n1')].drop_duplicates('source_key')
        c['original_setting_only'] = compact(bt, OWf, fam)
        # 3. Chinese: no CJK anywhere in the bullet; synonyms that are not translations
        c['no_cjk_bullet'] = compact(bt, Wf[~Wf.cjk_bullet], fam)
        if fam == 'um':
            rt = right[right.synonym_kind_synonym != 'translation_zh']
            c['synonym_table_only'] = {'swap-synonym': contrast(bt, rt, S, 'synonym'), 'synonym': summ_type(bt, rt, 'synonym')}
            rz = right[right.synonym_kind_synonym == 'translation_zh']
            c['synonym_translation_zh_only'] = {'synonym': summ_type(bt, rz, 'synonym'),
                                                'swap-synonym': contrast(bt, rz, S, 'synonym')}
            # 4. demonyms: adjective (demonym) sources only, tok_delta 0 swap and synonym
            ra = right[(right.role == 'adj')]
            c['demonym_adj_only'] = {'swap': summ_type(bt, ra, S), 'swap-synonym': contrast(bt, ra, S, 'synonym'),
                                     'neighbor-synonym': contrast(bt, ra, 'swap_neighbor', 'synonym')}
            rn = right[(right.role == 'name')]
            c['country_name_only'] = {'swap': summ_type(bt, rn, S), 'swap-synonym': contrast(bt, rn, S, 'synonym')}
            # 5. echo: the gold value is in the prompt and the target is read where the prompt is visible
            re_ = right[(right.in_prompt == True) & (right.subfamily == 'synthsys')]  # noqa: E712
            c['synthsys_echo'] = {'swap': summ_type(bt, re_, S), 'swap-synonym': contrast(bt, re_, S, 'synonym')}
            # neighbour as distractor sources excluded
            c['exclude_neighbor_as_distractor'] = {'swap': summ_type(bt, right[~right[f'neighbor_as_distractor_{S}'].fillna(False).astype(bool)], S)}
        else:
            rc = right[right.clean_item == True]  # noqa: E712
            c['clean_items_only'] = {'swap': summ_type(bt, rc, S), 'swap-synonym': contrast(bt, rc, S, 'synonym')}
            rl = right[right.llm_label == 'gold']
            c['llm_gold_sources_only'] = {'swap': summ_type(bt, rl, S), 'swap-synonym': contrast(bt, rl, S, 'synonym')}
        # 6. late layers and assistant-side read sites, where the value is most likely encoded
        late = right[right.layer >= 44]
        c['layers_44_60'] = {'swap': summ_type(bt, late, S), 'swap-synonym': contrast(bt, late, S, 'synonym')}
        # 7. joint without a duplicate of the source in its readout
        ow = OW[(OW.family == fam) & (~OW.dup_source)]
        c['joint_no_dup_occ'] = compact(bt, ow, fam, occ=True)
        # 8. large AR moves: swaps that moved the vector at least as far as the median frame edit
        thr = float(right.cosd_frame.median())
        big = right[right[f'cosd_{S}'] >= thr]
        c['swap_moves_ge_median_frame_move'] = {'threshold_cosd': round(thr, 5), 'swap': summ_type(bt, big, S)}
        # 9. sign consistency: per-item mean d_swap - d_synonym, fraction of items < 0
        r2 = right[right[f'd_solo_{S}'].notna() & right.d_solo_synonym.notna()]
        per_item = (r2[f'd_solo_{S}'] - r2.d_solo_synonym).groupby(r2.item_id).mean()
        c['items_with_swap_below_synonym'] = {'items': int(len(per_item)), 'frac': round(float((per_item < 0).mean()), 3)}
        CH[fam] = c
    R['challenges'] = CH

    # ---- move-size matched comparisons and the direction test (reverse vs forward swap)
    R['size_matched'] = {fam: size_matched(BT[fam], ED[ED.family == fam].copy(), W[W.family == fam], OW[OW.family == fam], fam)
                         for fam in FAMS}

    # ---- examples (seeded, representative: swap delta near the family median; plus one large-move case)
    R['examples'] = pick_examples(W)
    R['meta']['seconds'] = round(time.time() - t0, 1)
    tmp = A6 / 'results.json.tmp'
    tmp.write_text(json.dumps(R, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o)))
    os.replace(tmp, A6 / 'results.json')
    log(f'results.json written ({R["meta"]["seconds"]}s)')
    print_headline(R)


def matched_diff(bt, A, B, col, nd=5):
    """Stratified mean(A) - mean(B) over the strata in column 'mstrat', weighted by A's counts (strata where both
    occur). Item and group bootstrap with the family's weights."""
    A = A[np.isfinite(A[col].astype(float))]
    B = B[np.isfinite(B[col].astype(float))]
    if not len(A) or not len(B):
        return None
    S = int(max(A.mstrat.max(), B.mstrat.max()) + 1)
    n = len(bt.items)

    def mats(D):
        idx = np.array([bt.ii[i] for i in D.item_id])
        st = D.mstrat.to_numpy(int)
        N = np.zeros((n, S))
        K = np.zeros((n, S))
        np.add.at(N, (idx, st), D[col].to_numpy(float))
        np.add.at(K, (idx, st), 1.0)
        return N, K

    def stat(NA, KA, NB, KB):
        with np.errstate(invalid='ignore', divide='ignore'):
            ok = (KA > 0) & (KB > 0)
            dm = np.where(ok, NA / np.where(KA > 0, KA, 1) - NB / np.where(KB > 0, KB, 1), 0.0)
            w = np.where(ok, KA, 0.0)
            return (dm * w).sum(-1) / w.sum(-1)

    NA, KA = mats(A)
    NB, KB = mats(B)
    e = float(stat(NA.sum(0), KA.sum(0), NB.sum(0), KB.sum(0)))
    ri = stat(bt.Wi @ NA, bt.Wi @ KA, bt.Wi @ NB, bt.Wi @ KB)
    G = len(bt.cl)
    agg = lambda M: np.stack([np.bincount(bt.icl, M[:, j], G) for j in range(S)], 1)  # noqa: E731
    rc = stat(bt.Wc @ agg(NA), bt.Wc @ agg(KA), bt.Wc @ agg(NB), bt.Wc @ agg(KB))
    cov = float(((KA.sum(0) > 0) & (KB.sum(0) > 0)) @ KA.sum(0) / KA.sum())
    return {'est': round(e, nd), 'ci': _ci(ri, nd), 'ci_groups': _ci(rc, nd), 'nA': int(len(A)), 'nB': int(len(B)),
            'coverage_A': round(cov, 3)}


def size_matched(bt, E, W, OW, fam, nbins=10):
    """Edits compared at the same AR move (1 - whitened cosine, family deciles) and the same original solo FVE
    (terciles): strata = 30. Also the direction-only metric alpha and a descriptive decile table."""
    S = MAIN_SWAP[fam]
    edges = np.quantile(E.cosd, np.linspace(0, 1, nbins + 1))
    E['cbin'] = np.clip(np.searchsorted(edges, E.cosd, side='right') - 1, 0, nbins - 1)
    so_edges = np.quantile(W.solo, [1 / 3, 2 / 3])
    E['sbin'] = np.searchsorted(so_edges, E.solo_o, side='right')
    E['mstrat'] = E.cbin * 3 + E.sbin
    E['wins_edit'] = 1 - E.win
    out = {'cosd_decile_edges': [round(float(x), 5) for x in edges],
           'solo_tercile_edges': [round(float(x), 4) for x in so_edges]}
    by = {t: E[E.variant_type == t] for t in E.variant_type.unique()}
    by['preserving'] = E[E.variant_type.isin(['synonym', 'frame'])]
    pairs = [(S, 'frame'), (S, 'synonym'), (S, 'preserving'), ('reverse_to_gold', S), ('reverse_to_gold', 'preserving'),
             ('reverse_to_gold', 'frame'), ('frame', 'synonym')]
    if fam == 'um':
        pairs += [('swap_neighbor', 'frame'), ('swap_neighbor', 'synonym'), ('reverse_to_gold', 'swap_neighbor')]
    M = {}
    for a, b in pairs:
        M[f'{a} vs {b}'] = {c: matched_diff(bt, by[a], by[b], c) for c in ('d_solo', 'win', 'd_joint', 'winj', 'alpha')}
    out['matched'] = M
    vs = M[f'reverse_to_gold vs {S}']

    def scaled(dct, a):
        o = dict(dct)
        o['est'] = round(dct['est'] * a, 5)
        for k in ('ci', 'ci_groups'):
            if dct.get(k):
                o[k] = sorted(round(x * a, 5) for x in dct[k])
        return o

    out['V_matched'] = {
        'V_solo': scaled(vs['d_solo'], 0.5), 'V_joint': scaled(vs['d_joint'], 0.5),
        'P_gold_edit_beats_orig_minus_P_swap_edit_beats_orig': scaled(vs['win'], -1.0),
        'note': 'half the size-matched difference (reverse - forward swap); > 0 = FVE prefers the right value net of '
                'the cost of editing the lens text'}
    # subsets for the direction test
    sub = {}
    orig_src = set(OW[OW.setting == 'capped_n1-n1'].source_key)
    srcinfo = W.set_index('source_key')
    E['val_tok0'] = srcinfo.val_tok0.reindex(E.source_key).to_numpy()
    E['cjk_bullet'] = srcinfo.cjk_bullet.reindex(E.source_key).to_numpy().astype(bool)
    masks = {'original_setting_sources': E.source_key.isin(orig_src), 'tok_delta0': E.tok_delta == 0,
             'no_cjk_bullet': ~E.cjk_bullet, 'value_tok_lt8': E.val_tok0 < 8, 'value_tok_ge8': E.val_tok0 >= 8}
    if fam == 'um':
        masks.update({'synthsys': E.subfamily == 'synthsys', 'selfdescribe': E.subfamily == 'selfdescribe',
                      'layers_44_60': E.layer >= 44, 'layers_20_36': E.layer < 44,
                      'role_adj_demonym': E.role == 'adj', 'role_name_country': E.role == 'name',
                      'attr_Continent': E.attr_class == 'Continent', 'attr_Country': E.attr_class == 'Country',
                      'no_cjk_and_tok_delta0': (~E.cjk_bullet) & (E.tok_delta == 0)})
    else:
        masks.update({'layers_44_60': E.layer >= 44, 'layers_20_36': E.layer < 44, 'clean_items': E.clean_item == True,  # noqa: E712
                      'axis_state': E.contrast_axis == 'state', 'no_cjk_and_tok_delta0': (~E.cjk_bullet) & (E.tok_delta == 0)})
    for name, m in masks.items():
        Em = E[m]
        bm = {t: Em[Em.variant_type == t] for t in Em.variant_type.unique()}
        bm['preserving'] = Em[Em.variant_type.isin(['synonym', 'frame'])]
        if 'reverse_to_gold' not in bm or len(bm['reverse_to_gold']) < 20 or S not in bm:
            continue
        sub[name] = {'n_reverse': int(len(bm['reverse_to_gold'])),
                     'reverse vs swap d_solo': matched_diff(bt, bm['reverse_to_gold'], bm[S], 'd_solo'),
                     'reverse vs swap win(orig>edit)': matched_diff(bt, bm['reverse_to_gold'], bm[S], 'win'),
                     'swap vs frame d_solo': matched_diff(bt, bm[S], bm['frame'], 'd_solo'),
                     'swap vs synonym d_solo': matched_diff(bt, bm[S], bm['synonym'], 'd_solo')}
    if fam == 'um':
        for wsub in ('distractor', 'other_value'):
            Rv = by['reverse_to_gold'][by['reverse_to_gold'].wrong_subtype == wsub]
            if len(Rv) >= 20:
                sub[f'reverse_from_{wsub}'] = {'n_reverse': int(len(Rv)),
                                               'reverse vs swap d_solo': matched_diff(bt, Rv, by[S], 'd_solo'),
                                               'reverse vs swap win(orig>edit)': matched_diff(bt, Rv, by[S], 'win')}
    out['direction_subsets'] = sub
    # alpha (direction only): per type and contrasts
    out['alpha'] = {t: est(bt, d.item_id.to_numpy(), d.alpha, nd=5) for t, d in by.items()}
    out['geo_cost_mean'] = {t: round(float(d.geo.mean()), 5) for t, d in by.items()}
    out['cosd_mean'] = {t: round(float(d.cosd.mean()), 5) for t, d in by.items()}
    out['solo_o_mean'] = {t: round(float(d.solo_o.mean()), 5) for t, d in by.items()}
    ac = {}
    for a, b in [(S, 'frame'), (S, 'synonym'), ('frame', 'synonym')] + ([('swap_neighbor', 'frame')] if fam == 'um' else []):
        pa = by[a].set_index('source_key').alpha
        pb = by[b].set_index('source_key').alpha
        j = pa.to_frame('a').join(pb.to_frame('b'), how='inner')
        items = by[a].set_index('source_key').item_id.loc[j.index].to_numpy()
        ac[f'{a} - {b} (paired)'] = est(bt, items, (j.a - j.b).to_numpy(), nd=5)
    rv = by['reverse_to_gold']
    ac[f'reverse_to_gold - {S}'] = est_diff(bt, rv.item_id, rv.alpha, by[S].item_id, by[S].alpha, 1.0, nd=5)
    ac['reverse_to_gold - frame'] = est_diff(bt, rv.item_id, rv.alpha, by['frame'].item_id, by['frame'].alpha, 1.0, nd=5)
    out['alpha_contrasts'] = ac
    # descriptive decile table
    tab = []
    for t, d in sorted(by.items()):
        if t == 'preserving':
            continue
        for cb, dd in d.groupby('cbin'):
            tab.append({'type': t, 'cosd_decile': int(cb), 'n': int(len(dd)), 'mean_d_solo': round(float(dd.d_solo.mean()), 5),
                        'p_orig_gt_edit': round(float(dd.win.mean()), 3), 'mean_alpha': round(float(dd.alpha.mean()), 4),
                        'mean_d_joint': round(float(dd.d_joint.mean()), 5)})
    out['decile_table'] = tab
    return out


def pick_examples(W):
    rng = np.random.default_rng(SEED)
    out = []

    def rec(r, types):
        e = {'case_key': case_key(r.cell_id), 'setting': SL.get(r.setting, r.setting), 'bullet_index': int(r.bullet_index),
             'source_key': r.source_key, 'family': r.family, 'read_site': r.read_site, 'gold': r.gold,
             'original_text': r.original_text, 'solo_orig': round(float(r.solo), 4),
             'joint_orig': round(float(r[f'joint_o_{types[0]}']), 4), 'variants': []}
        for T in types:
            if pd_isna(r.get(f'd_solo_{T}')):
                continue
            e['variants'].append({'type': T, 'variant_id': r[f'variant_id_{T}'], 'before': r[f'edit_before_{T}'],
                                  'after': r[f'edit_after_{T}'], 'edited_text': r[f'edited_text_{T}'],
                                  'solo': round(float(r[f'solo_{T}']), 4), 'd_solo': round(float(r[f'd_solo_{T}']), 4),
                                  'd_joint': round(float(r[f'd_joint_{T}']), 4), 'cos_w': round(1 - float(r[f'cosd_{T}']), 4),
                                  'tok_delta': int(r[f'tok_delta_{T}'])})
        return e

    for fam, kind, n in (('um', 'right', 2), ('ca', 'right', 2), ('um', 'wrong', 1), ('ca', 'wrong', 1)):
        d = W[(W.family == fam) & (W.source_kind == kind)]
        T = MAIN_SWAP[fam] if kind == 'right' else 'reverse_to_gold'
        x = d[f'd_solo_{T}']
        lo, hi = x.quantile(0.35), x.quantile(0.65)
        cand = d[(x >= lo) & (x <= hi) & (d.cjk_bullet == False)]  # noqa: E712
        if kind == 'right':
            cand = cand[cand.d_solo_synonym.notna() & cand.d_solo_frame.notna()]
        pick = cand.iloc[rng.choice(len(cand), size=min(n, len(cand)), replace=False)]
        types = RIGHT_TYPES[fam] if kind == 'right' else ('reverse_to_gold',)
        for _, r in pick.iterrows():
            out.append(rec(r, types))
    return out


def pd_isna(x):
    try:
        return x is None or (isinstance(x, float) and math.isnan(x))
    except Exception:
        return False


def print_headline(R):
    for fam in FAMS + ('all',):
        h = R['headline'][fam]
        print(f'== {fam}')
        for T, s in h['right'].items():
            if not s:
                continue
            print(f"  {T:16s} n={s['n_sources']:5d}  P(orig>edit) solo {s['p_orig_gt_edit_solo']['est']:.3f} "
                  f"{s['p_orig_gt_edit_solo']['ci_groups']}  joint {s['p_orig_gt_edit_joint']['est']:.3f} "
                  f"{s['p_orig_gt_edit_joint']['ci_groups']}  d_solo {s['mean_d_solo']['est']:+.5f} "
                  f"{s['mean_d_solo']['ci_groups']} |d| {s['mean_abs_d_solo']['est']:.5f} cosd {s['mean_cosd']['est']:.4f} "
                  f"align {s['mean_align']['est']:+.4f}")
        s = h['reverse_to_gold']
        print(f"  reverse          n={s['n_sources']:5d}  P(gold edit>orig) solo {s['p_edit_gt_orig_solo']['est']:.3f} "
              f"{s['p_edit_gt_orig_solo']['ci_groups']} joint {s['p_edit_gt_orig_joint']['est']:.3f} "
              f"d_solo {s['mean_d_solo']['est']:+.5f} {s['mean_d_solo']['ci_groups']}")
        for k, c in h['contrasts'].items():
            if c:
                print(f"  {k:30s} n={c['n_sources']} dwin {c['win_orig_solo']['est']:+.3f} {c['win_orig_solo']['ci_groups']}"
                      f" dd {c['d_solo']['est']:+.5f} {c['d_solo']['ci_groups']} |d| {c['abs_d_solo']['est']:+.5f} "
                      f"{c['abs_d_solo']['ci_groups']} cosd {c['cosd']['est']:+.4f}")
        print('  V', h['value_effect_two_directions']['V_solo'], h['value_effect_two_directions']['V_joint'])


# ================================================================================================ show
def cmd_show(args):
    V, O, _ = load_tables()
    key = args.key
    d = V[(V.variant_id == key) | (V.source_key == key)]
    if not len(d):
        d = V[V.variant_id.str.contains(re.escape(key), regex=True)]
    for sk, g in d.groupby('source_key'):
        g0 = V[V.source_key == sk]
        o = g0[g0.variant_type == 'original'].iloc[0]
        print(f'# {case_key(o.cell_id)}  {o.read_site}  setting {SL.get(o.setting)}  bullet {o.bullet_index}  gold {o.gold}')
        print(f'  source_key {sk}')
        oc = O[(O.source_key == sk)]
        for _, v in g0.iterrows():
            j = oc[oc.variant_id == v.variant_id].joint.mean()
            print(f'  [{v.variant_type:16s}] solo {v.solo:.4f} joint {j:.4f} cos_w {v.cos_w:.4f} tokd {v.tok_delta:+d}'
                  f'  {v.edit_before!r} -> {v.edit_after!r}')
            print(f'      {v.edited_text!r}')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('compute')
    p.add_argument('--test', action='store_true')
    sub.add_parser('run')
    p = sub.add_parser('show')
    p.add_argument('key')
    args = ap.parse_args()
    {'compute': cmd_compute, 'run': cmd_run, 'show': cmd_show}[args.cmd](args)


if __name__ == '__main__':
    main()
