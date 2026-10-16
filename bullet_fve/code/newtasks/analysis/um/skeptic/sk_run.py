"""Skeptic pass for um: recompute A2 / A3 / A4 headlines and confound checks from sk_tables.pkl (my own code).

Bootstrap: 2,000 reps, seed 4242, over the 31 related-item groups attr_class:attr (primary, 'g') and over the 100
items ('i'); ratio of sums; every statistic of a run uses the same weights.
Writes analysis/um/skeptic/sk_results.json and prints a digest.
"""
import json
import math
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
SK = NT / 'analysis/um/skeptic'
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
SN = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
B = 2000
RES = {}


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


class Boot:
    def __init__(self, items):
        self.items = sorted(items)
        self.ix = {k: i for i, k in enumerate(self.items)}
        groups = sorted(set(items.values()))
        self.gix = np.array([groups.index(items[k]) for k in self.items])
        self.ng = len(groups)
        rng = np.random.default_rng(4242)
        self.Wg = rng.multinomial(self.ng, np.full(self.ng, 1 / self.ng), size=B).astype(float)
        self.Wi = rng.multinomial(len(self.items), np.full(len(self.items), 1 / len(self.items)), size=B).astype(float)

    def sums(self, item_ids, num, den=None):
        idx = np.array([self.ix[i] for i in item_ids], dtype=int)
        num = np.asarray(num, float)
        den = np.ones_like(num) if den is None else np.asarray(den, float)
        n = len(self.items)
        return np.bincount(idx, num, n), np.bincount(idx, den, n)

    def reps(self, N, Dn):
        Ng, Dg = np.bincount(self.gix, N, self.ng), np.bincount(self.gix, Dn, self.ng)
        with np.errstate(all='ignore'):
            return (self.Wg @ Ng) / (self.Wg @ Dg), (self.Wi @ N) / (self.Wi @ Dn)

    def ratio(self, N, Dn, nd=3):
        if Dn.sum() == 0:
            return None
        rg, ri = self.reps(N, Dn)
        return {'est': round(float(N.sum() / Dn.sum()), nd), 'g': ci(rg, nd), 'i': ci(ri, nd), 'n': float(Dn.sum()),
                'items': int((Dn > 0).sum()), 'groups': int((np.bincount(self.gix, Dn, self.ng) > 0).sum())}

    def diff(self, a, b, nd=3):
        (N1, D1), (N2, D2) = a, b
        g1, i1 = self.reps(N1, D1)
        g2, i2 = self.reps(N2, D2)
        return {'est': round(float(N1.sum() / D1.sum() - N2.sum() / D2.sum()), nd), 'g': ci(g1 - g2, nd),
                'i': ci(i1 - i2, nd)}


def ci(x, nd):
    x = x[np.isfinite(x)]
    if not len(x):
        return None
    return [round(float(np.percentile(x, 2.5)), nd), round(float(np.percentile(x, 97.5)), nd)]


def cell_pairs(df, A, Bm, match=None, tok_tol=None, gcol='cell_id', score='solo'):
    """Per group (cell or readout): wins of A over B (ties 1/2) and pairs. Returns DataFrame [gid, item, w, p]."""
    d = df.assign(_A=A, _B=Bm)
    d = d[d._A | d._B]
    out = []
    sc = d[score].to_numpy(float)
    aa, bb = d._A.to_numpy(), d._B.to_numpy()
    m = d[match].to_numpy() if match is not None else None
    tk = d.stok.to_numpy(float) if tok_tol is not None else None
    gid = d[gcol].to_numpy()
    it = d.item_id.to_numpy()
    order = np.argsort(gid, kind='stable')
    gs = gid[order]
    cuts = np.flatnonzero(gs[1:] != gs[:-1]) + 1
    for s, e in zip(np.r_[0, cuts], np.r_[cuts, len(gs)]):
        ix = order[s:e]
        ia, ib = ix[aa[ix]], ix[bb[ix]]
        if not len(ia) or not len(ib):
            continue
        if m is None and tk is None:
            bs = np.sort(sc[ib])
            lo = np.searchsorted(bs, sc[ia], 'left')
            hi = np.searchsorted(bs, sc[ia], 'right')
            w = lo.sum() + 0.5 * (hi - lo).sum()
            p = len(ia) * len(ib)
        else:
            ok = np.ones((len(ia), len(ib)), bool)
            if m is not None:
                ma, mb = m[ia], m[ib]
                ok &= (ma[:, None] == mb[None, :]) & np.array([x is not None and x == x for x in ma])[:, None]
            if tk is not None:
                ta, tb = tk[ia][:, None], tk[ib][None, :]
                ok &= np.abs(ta - tb) <= tok_tol * np.maximum(ta, tb)
            dd = sc[ia][:, None] - sc[ib][None, :]
            p = ok.sum()
            if not p:
                continue
            w = ((dd > 0) & ok).sum() + 0.5 * ((dd == 0) & ok).sum()
        out.append((gs[s], it[ix[0]], w, p))
    return pd.DataFrame(out, columns=['gid', 'item_id', 'w', 'p'])


def rate(bt, cp, nd=3):
    if not len(cp):
        return {'pooled': None, 'cells': 0, 'pairs': 0}
    pooled = bt.ratio(*bt.sums(cp.item_id, cp.w, cp.p), nd)
    percell = bt.ratio(*bt.sums(cp.item_id, cp.w / cp.p), nd)
    return {'pooled': pooled, 'per_cell': percell, 'cells': int(len(cp)), 'pairs': int(cp.p.sum())}


def fmt(r):
    if r is None or r.get('pooled') is None:
        return 'n/a'
    p, c = r['pooled'], r['per_cell']
    return f"{p['est']:.3f} {p['g']} | per-cell {c['est']:.3f} {c['g']} | {r['cells']} cells {r['pairs']} pairs"


def fe_reg(bt, d, fe, y, X, contrasts, nd=4):
    d = d[[fe, 'item_id', y] + X].dropna()
    M = d[[y] + X].astype(float)
    M = M - M.groupby(d[fe].to_numpy()).transform('mean')
    Y, Xm = M[y].to_numpy(), M[X].to_numpy()
    idx = np.array([bt.ix[i] for i in d.item_id])
    n, k = len(bt.items), len(X)
    XtX = np.zeros((n, k, k))
    Xty = np.zeros((n, k))
    for i in np.unique(idx):
        s = idx == i
        XtX[i] = Xm[s].T @ Xm[s]
        Xty[i] = Xm[s].T @ Y[s]
    R = 1e-9 * np.eye(k)
    beta = np.linalg.solve(XtX.sum(0) + R, Xty.sum(0))
    G = np.zeros((bt.ng, k, k))
    Gy = np.zeros((bt.ng, k))
    for g in range(bt.ng):
        G[g] = XtX[bt.gix == g].sum(0)
        Gy[g] = Xty[bt.gix == g].sum(0)
    bg = np.array([np.linalg.solve(np.tensordot(w, G, 1) + R, w @ Gy) for w in bt.Wg])
    bi = np.array([np.linalg.solve(np.tensordot(w, XtX, 1) + R, w @ Xty) for w in bt.Wi])
    out = {'n': int(len(d)), 'within_sd': round(float(Y.std()), 4), 'coef': {}, 'contrasts': {}}
    for j, c in enumerate(X):
        out['coef'][c] = {'est': round(float(beta[j]), nd), 'g': ci(bg[:, j], nd), 'i': ci(bi[:, j], nd)}
    for name, wts in contrasts.items():
        v = np.zeros(k)
        for c, w in wts.items():
            v[X.index(c)] = w
        out['contrasts'][name] = {'est': round(float(beta @ v), nd), 'g': ci(bg @ v, nd), 'i': ci(bi @ v, nd)}
    return out


def main():
    t0 = time.time()
    T = pickle.load(open(SK / 'cache/sk_tables.pkl', 'rb'))
    pool, sel, samples, items = T['pool'], T['sel'], T['samples'], T['items']
    bt = Boot({k: v['group'] for k, v in items.items()})
    RES['meta'] = T['meta'] | {'groups': bt.ng, 'group_sizes': pd.Series({k: v['group'] for k, v in items.items()}).value_counts().head(5).to_dict()}
    p = pool[pool.solo.notna()].drop_duplicates(['cell_id', 'cache_key']).reset_index(drop=True)
    RES['meta']['pool_dedup'] = len(p)
    log('pool dedup', len(p))
    G, W, F, N = (p.grp == 'gold'), (p.grp == 'wrong'), (p.grp == 'frame'), (p.grp == 'none')
    GN, WN = G & p.gname, W & p.wname
    sd, ss = p['sub'] == 'selfdescribe', p['sub'] == 'synthsys'
    a3 = {}

    def put(name, A, Bm, **kw):
        r = rate(bt, cell_pairs(p, A.to_numpy(), Bm.to_numpy(), **kw))
        a3[name] = r
        print(f'A3 {name:55s} {fmt(r)}', flush=True)
        return r
    put('gold_vs_wrong', G, W)
    put('gold_vs_wrong|full_text', p.grpF == 'gold', p.grpF == 'wrong')
    put('gold_vs_wrong|same_slot', G, W, match='pos')
    put('gold_vs_wrong|len_matched', G, W, tok_tol=0.2)
    put('gold_vs_wrong|same_frame_mopen4', G, W, match='mopen4')
    put('gold_vs_wrong|same_frame_mopen3', G, W, match='mopen3')
    put('gold_vs_wrong|same_frame_mopen4_len', G, W, match='mopen4', tok_tol=0.2)
    put('gold_vs_wrong|selfdescribe', G & sd, W & sd)
    put('gold_vs_wrong|synthsys', G & ss, W & ss)
    put('name|gold_vs_wrong', GN, WN)
    put('name|gold_vs_wrong|selfdescribe', GN & sd, WN & sd)
    put('name|gold_vs_wrong|synthsys', GN & ss, WN & ss)
    for rule in ('S', 'V', 'X'):
        nov = p['gnov' + rule].fillna(False).astype(bool)
        put(f'echo{rule}|novel_gold_vs_wrong', G & nov, W)
        put(f'echo{rule}|echo_gold_vs_wrong', G & ~nov, W)
        put(f'echo{rule}|echo_gold_vs_novel_gold', G & ~nov, G & nov)
        put(f'echo{rule}|name_novel_gold_vs_name_wrong', GN & nov, WN)
    novV = p.gnovV.fillna(False).astype(bool)
    put('echoV|novel_gold_vs_wrong|selfdescribe', G & novV & sd, W & sd)
    put('echoV|echo_gold_vs_wrong|selfdescribe', G & ~novV & sd, W & sd)
    put('echoV|novel_gold_vs_wrong|synthsys', G & novV & ss, W & ss)
    put('echoV|echo_gold_vs_wrong|synthsys', G & ~novV & ss, W & ss)
    put('gold_vs_wrong|distractor', G, W & p.wdis)
    put('gold_vs_wrong|other_value', G, W & ~p.wdis.fillna(False).astype(bool))
    # ladder
    for nm, A_, B_ in (('gold_vs_frame', G, F), ('wrong_vs_frame', W, F), ('gold_vs_none', G, N),
                       ('wrong_vs_none', W, N), ('frame_vs_none', F, N)):
        put(nm, A_, B_)
        put(nm + '|len_matched', A_, B_, tok_tol=0.2)
    # robustness slices
    nocjk = ~p.cjk_lead
    put('gold_vs_wrong|no_cjk_lead', G & nocjk, W & nocjk)
    put('gold_vs_wrong|cjk_lead_both', G & p.cjk_lead, W & p.cjk_lead)
    clean = ~p.cjk_lead & ~p.list_open & ~p.mark_open
    put('gold_vs_wrong|clean_opening', G & clean, W & clean)
    anta = p.group == 'Continent:antarctica'
    put('gold_vs_wrong|no_antarctica', G & ~anta, W & ~anta)
    usa = p.wvals.map(lambda v: bool(v) and any(x in ('united_states', 'north_america') for x in v))
    put('gold_vs_wrong|wrong_not_US_NA', G, W & ~usa)
    gm = p.group == 'Gender:male'
    put('gold_vs_wrong|no_gender', G & (p.cls != 'Gender'), W & (p.cls != 'Gender'))
    by = {}
    for L in (20, 36, 44, 52, 60):
        m = p.layer == L
        by[f'L{L}'] = put(f'gold_vs_wrong|L{L}', G & m, W & m)
    for st in sorted(p.site.unique()):
        m = p.site == st
        by[st] = put(f'gold_vs_wrong|site {st}', G & m, W & m)
        put(f'name_novelV|site {st}', GN & novV & m, WN & m)
    for c in sorted(p.cls.unique()):
        m = p.cls == c
        put(f'gold_vs_wrong|class {c}', G & m, W & m)
    # group contributions and leave-one-group-out
    cp = cell_pairs(p, G.to_numpy(), W.to_numpy())
    cp['group'] = cp.item_id.map(lambda i: items[i]['group'])
    gsum = cp.groupby('group')[['w', 'p']].sum()
    tot = gsum.sum()
    a3['group_share'] = {g: {'share': round(float(r.p / tot.p), 3), 'rate': round(float(r.w / r.p), 3),
                             'cells': int((cp.group == g).sum())} for g, r in gsum.sort_values('p', ascending=False).iterrows()}
    loo = {g: round(float((tot.w - r.w) / (tot.p - r.p)), 3) for g, r in gsum.iterrows()}
    a3['loo_group'] = {'min': min(loo.values()), 'max': max(loo.values()), 'argmin': min(loo, key=loo.get),
                       'argmax': max(loo, key=loo.get)}
    # cell-level: unweighted share of cells where gold wins > 0.5
    cp['r'] = cp.w / cp.p
    a3['cells_gold_ahead'] = {'share_r_gt_0.5': round(float((cp.r > 0.5).mean()), 3),
                              'share_r_lt_0.5': round(float((cp.r < 0.5).mean()), 3), 'cells': int(len(cp))}
    RES['A3'] = a3
    log('A3 pair rates done')

    # within-cell regression with controls
    d = p.copy()
    for lb in ('gold', 'wrong', 'mixed', 'frame'):
        d['L_' + lb] = (d.grp == lb).astype(float)
    for rule in ('V', 'X'):
        nv = d['gnov' + rule].fillna(False).astype(bool)
        d[f'L_gnov{rule}'] = ((d.grp == 'gold') & nv).astype(float)
        d[f'L_gech{rule}'] = ((d.grp == 'gold') & ~nv).astype(float)
    d['L_gname_nov'] = ((d.grp == 'gold') & d.gname & d.gname_novV.fillna(False).astype(bool)).astype(float)
    d['L_gname_ech'] = ((d.grp == 'gold') & d.gname & ~d.gname_novV.fillna(False).astype(bool)).astype(float)
    d['L_gweak'] = ((d.grp == 'gold') & ~d.gname).astype(float)
    d['L_wname'] = ((d.grp == 'wrong') & d.wname).astype(float)
    d['L_wweak'] = ((d.grp == 'wrong') & ~d.wname).astype(float)
    for k in (1, 2, 3):
        d[f'slot{k}'] = (d.pos == k).astype(float)
    d['logtok'] = np.log(d.stok.clip(lower=1))
    for c in ('cjk_lead', 'list_open', 'mark_open'):
        d[c] = d[c].astype(float)
    ctrl = ['slot1', 'slot2', 'slot3', 'logtok', 'cjk_lead', 'list_open', 'mark_open', 'overlap']
    base = ['L_gold', 'L_wrong', 'L_mixed', 'L_frame']
    con = {'gold-wrong': {'L_gold': 1, 'L_wrong': -1}, 'gold-frame': {'L_gold': 1, 'L_frame': -1},
           'wrong-frame': {'L_wrong': 1, 'L_frame': -1}, 'gold-none': {'L_gold': 1}, 'wrong-none': {'L_wrong': 1},
           'frame-none': {'L_frame': 1}}
    reg = {'labels_only': fe_reg(bt, d, 'cell_id', 'solo', base, con),
           'controls': fe_reg(bt, d, 'cell_id', 'solo', base + ctrl, con)}
    for rule in ('V', 'X'):
        Xs = [f'L_gnov{rule}', f'L_gech{rule}', 'L_wrong', 'L_mixed', 'L_frame'] + ctrl
        reg[f'echo{rule}_controls'] = fe_reg(bt, d, 'cell_id', 'solo', Xs, {
            'novel-wrong': {f'L_gnov{rule}': 1, 'L_wrong': -1}, 'echo-wrong': {f'L_gech{rule}': 1, 'L_wrong': -1},
            'echo-novel': {f'L_gech{rule}': 1, f'L_gnov{rule}': -1}})
    Xn = ['L_gname_nov', 'L_gname_ech', 'L_gweak', 'L_wname', 'L_wweak', 'L_mixed', 'L_frame'] + ctrl
    reg['name_controls'] = fe_reg(bt, d, 'cell_id', 'solo', Xn, {
        'gname_novel-wname': {'L_gname_nov': 1, 'L_wname': -1}, 'gname_echo-wname': {'L_gname_ech': 1, 'L_wname': -1}})
    for sf in ('selfdescribe', 'synthsys'):
        reg[f'controls|{sf}'] = fe_reg(bt, d[d['sub'] == sf], 'cell_id', 'solo', base + ctrl, con)
    reg['controls|no_antarctica'] = fe_reg(bt, d[d.group != 'Continent:antarctica'], 'cell_id', 'solo', base + ctrl, con)
    RES['regression'] = reg
    for k, v in reg.items():
        print('REG', k, 'sd', v['within_sd'], {c: (x['est'], x['g']) for c, x in v['contrasts'].items()}, flush=True)
    print('REG controls coef', {c: (x['est'], x['g']) for c, x in reg['controls']['coef'].items()}, flush=True)
    # feature rates by label
    RES['feature_rates'] = {lb: {c: round(float(p[p.grp == lb][c].astype(float).mean()), 3)
                                 for c in ('cjk_lead', 'list_open', 'mark_open', 'overlap', 'pos', 'stok', 'trunc')}
                            for lb in ('gold', 'wrong', 'frame', 'none')}
    print('FEAT', RES['feature_rates'], flush=True)
    # composition: gold rate and mean solo by layer / site
    RES['composition'] = {
        'gold_rate_by_layer': {int(L): round(float(x), 3) for L, x in p.groupby('layer').grp.apply(lambda s: (s == 'gold').mean()).items()},
        'mean_solo_by_layer': {int(L): round(float(x), 3) for L, x in p.groupby('layer').solo.mean().items()},
        'gold_rate_by_site': {k: round(float(x), 3) for k, x in p.groupby('site').grp.apply(lambda s: (s == 'gold').mean()).items()},
        'mean_solo_by_site': {k: round(float(x), 3) for k, x in p.groupby('site').solo.mean().items()},
        'raw_mean_solo_by_label': {k: round(float(x), 4) for k, x in p.groupby('grp').solo.mean().items()},
        'within_cell_mean_by_label': {k: round(float(x), 4) for k, x in
                                      (p.solo - p.groupby('cell_id').solo.transform('mean')).groupby(p.grp).mean().items()},
    }
    print('COMP', RES['composition'], flush=True)

    # ---------------- A2: within readout
    s = sel.copy()
    base_cols = ['cell_id', 'item_id', 'layer', 'site', 'grp', 'gname', 'gnovV', 'stok', 'cache_key', 'sub']
    s = s.join(pool[base_cols].drop(columns=['cell_id']), on='pidx')
    s['solo'] = s.solo_m
    s = s[s.solo.notna()].copy()
    mu = s.groupby(['setting', 'layer', 'nb', 'idx']).solo.transform('mean')
    s['solo_adj'] = np.where(s.setting == 'pooled_greedy_swap-n32', s.solo, s.solo - mu)
    s['rid'] = s.cell_id + '|' + s.setting
    a2 = {}
    NONG = s.grp.isin(['wrong', 'frame', 'none', 'ambiguous'])
    for nm, A_, B_ in (('gold_vs_nongold', s.grp == 'gold', NONG), ('gold_vs_wrong', s.grp == 'gold', s.grp == 'wrong'),
                       ('gold_vs_frame', s.grp == 'gold', s.grp == 'frame'), ('gold_vs_none', s.grp == 'gold', s.grp == 'none'),
                       ('wrong_vs_frame', s.grp == 'wrong', s.grp == 'frame'),
                       ('name_novel_gold_vs_nongold', (s.grp == 'gold') & s.gname & s.gnovV.fillna(False).astype(bool), NONG)):
        row = {}
        for st in SETTINGS + ('pooled',):
            m = (s.setting == st) if st != 'pooled' else np.ones(len(s), bool)
            sub_ = s[m]
            row[SN.get(st, st)] = rate(bt, cell_pairs(sub_, A_[m].to_numpy(), B_[m].to_numpy(), gcol='rid', score='solo_adj'))
            row[SN.get(st, st) + '|len'] = rate(bt, cell_pairs(sub_, A_[m].to_numpy(), B_[m].to_numpy(), gcol='rid',
                                                              score='solo_adj', tok_tol=0.2))
        a2[nm] = row
        print('A2', nm, {k: (v['pooled'] or {}).get('est') for k, v in row.items()},
              'pooled CI', (row['pooled']['pooled'] or {}).get('g'), 'len CI', (row['pooled|len']['pooled'] or {}).get('g'),
              'pairs', row['pooled']['pairs'], flush=True)
    RES['A2'] = a2

    # ---------------- A4: selection
    a4 = {}
    item_of = dict(zip(p.cell_id, p.item_id))
    cells = sorted(pool.cell_id.unique())
    for nm, f in (('gold', lambda d: d.grpF == 'gold'), ('gold_name', lambda d: (d.grpF == 'gold') & d.gnameF),
                  ('gold_novelX', lambda d: (d.grpF == 'gold') & d.gnovXF.fillna(False).astype(bool)),
                  ('wrong', lambda d: d.grpF == 'wrong')):
        fl = f(pool)
        sampf = fl.groupby([pool.cell_id, pool.sample_index]).any()
        r32 = sampf.groupby(level=0).mean()
        has = sampf.groupby(level=0).any()
        pu = pool[pool.solo.notna()].drop_duplicates(['cell_id', 'cache_key'])
        ng = f(pu).groupby(pu.cell_id).sum()
        nn = pu.groupby('cell_id').size()

        def hyp(n, g):
            return float(g > 0) if n < 4 else 1 - math.comb(int(n - g), 4) / math.comb(int(n), 4)
        r4 = {c: hyp(nn[c], ng.get(c, 0)) for c in nn.index}
        selh = {}
        for st in SETTINGS:
            ss_ = sel[sel.setting == st].join(pool[['grpF', 'gnameF', 'gnovXF']], on='pidx')
            selh[st] = f(ss_).groupby(ss_.cell_id).any()
        A = {'rand32': np.array([r32.get(c, np.nan) for c in cells], float),
             'rand4': np.array([r4.get(c, np.nan) for c in cells], float),
             'pool_has': np.array([float(has.get(c, False)) for c in cells])}
        for st in SETTINGS:
            A[SN[st]] = np.array([float(selh[st].get(c, False)) for c in cells])
        ok = np.isfinite(A['rand32']) & np.isfinite(A['rand4'])
        its = [item_of.get(c, c.split('|')[1]) for c, o in zip(cells, ok) if o]
        S = {k: bt.sums(its, v[ok]) for k, v in A.items()}
        r = {k: bt.ratio(*v) for k, v in S.items()}
        r['Original-rand32'] = bt.diff(S['Original'], S['rand32'])
        r['Best-rand32'] = bt.diff(S['Best of 32'], S['rand32'])
        r['Best-Original'] = bt.diff(S['Best of 32'], S['Original'])
        r['Combine-rand4'] = bt.diff(S['Combine 32'], S['rand4'])
        r['Combine-Original'] = bt.diff(S['Combine 32'], S['Original'])
        ph = A['pool_has'][ok] > 0
        for st in SETTINGS:
            r[f'missing_given_pool_has|{SN[st]}'] = round(float((A[SN[st]][ok][ph] == 0).mean()), 3)
        a4[nm] = r
        print('A4', nm, {k: (v['est'], v['g']) if isinstance(v, dict) and 'est' in v else v for k, v in r.items()}, flush=True)
    # judge per cell
    j = sel.drop_duplicates(['cell_id', 'setting'])[['cell_id', 'setting', 'pick', 'basis']].copy()
    j['item_id'] = j.cell_id.str.split('|').str[1]
    j['sub'] = j.item_id.map(lambda i: items[i]['sub'])
    jr = {}
    for kind, fn in (('gold', lambda d: d.pick == 'gold'),
                     ('gold_inferred', lambda d: (d.pick == 'gold') & (d.basis == 'inferred_characterization')),
                     ('gold_echo', lambda d: (d.pick == 'gold') & (d.basis == 'verbatim_echo')),
                     ('distractor', lambda d: d.pick == 'distractor')):
        for sf in ('all', 'selfdescribe', 'synthsys'):
            d0 = j if sf == 'all' else j[j['sub'] == sf]
            S = {st: bt.sums(d0[d0.setting == st].item_id, fn(d0[d0.setting == st]).astype(float)) for st in SETTINGS}
            r = {SN[st]: bt.ratio(*S[st], 4) for st in SETTINGS}
            r['Best-Original'] = bt.diff(S[SETTINGS[1]], S[SETTINGS[0]], 4)
            r['Combine-Original'] = bt.diff(S[SETTINGS[2]], S[SETTINGS[0]], 4)
            jr[f'{kind}|{sf}'] = r
            print('JUDGE', kind, sf, {k: (v['est'], v['g']) for k, v in r.items()}, flush=True)
    a4['judge'] = jr
    # sample level (joint FVE, Best-of-32 trace) gold sample vs wrong-only sample
    fl = pool.assign(g=pool.grpF.eq('gold'), w=pool.grpF.eq('wrong')).groupby(['cell_id', 'sample_index'])[['g', 'w']].any().reset_index()
    Sx = samples[samples.joint.notna()].merge(fl, on=['cell_id', 'sample_index'], how='left').fillna({'g': False, 'w': False})
    Sx['item_id'] = Sx.cell_id.str.split('|').str[1]
    Sx['stok'] = 0
    for nm, A_, B_ in (('gold_sample_vs_no_gold', Sx.g, ~Sx.g), ('gold_only_vs_wrong_only', Sx.g & ~Sx.w, Sx.w & ~Sx.g)):
        r = rate(bt, cell_pairs(Sx, A_.to_numpy(bool), B_.to_numpy(bool), score='joint'))
        a4['sample|' + nm] = r
        print('A4 sample', nm, fmt(r), flush=True)
    RES['A4'] = a4
    json.dump(RES, open(SK / 'sk_results.json', 'w'), indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    log('wrote', SK / 'sk_results.json', f'{time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
