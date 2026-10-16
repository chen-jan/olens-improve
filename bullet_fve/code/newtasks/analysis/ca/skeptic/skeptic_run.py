"""Skeptic pass for ca: recompute A2/A3/A4 headline numbers with my own code and test confounds.

Reads analysis/ca/skeptic/cache/sk_tables.pkl (skeptic_build.py). Writes analysis/ca/skeptic/sk_results.json.
Bootstrap: B=2000, resampling the 10 related-item groups (q01..q10) and, separately, the 100 items.
"""
import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
sys.path.insert(0, str(NT / 'code'))
import ntcommon as C  # noqa: E402

SK = NT / 'analysis/ca/skeptic'
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
SL = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
WRONG = ('contrast', 'other_value')
B = 2000
rng = np.random.default_rng(7)


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


bank = C.load_bank('conjunctive_association')
ITEMS = sorted(bank)
GROUPS = sorted({it['cluster'] for it in bank.values()})
I_OF = {k: i for i, k in enumerate(ITEMS)}
G_OF_ITEM = np.array([GROUPS.index(bank[k]['cluster']) for k in ITEMS])
WI = rng.multinomial(len(ITEMS), np.full(len(ITEMS), 1 / len(ITEMS)), size=B).astype(float)
WG = rng.multinomial(len(GROUPS), np.full(len(GROUPS), 1 / len(GROUPS)), size=B).astype(float)
# group weight applied to each item (an item's weight = its group's draw count)
WG_I = WG[:, G_OF_ITEM]


def ci(x, nd=3):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if not len(x):
        return None
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [round(float(lo), nd), round(float(hi), nd)]


def ratio_boot(N, Dn, nd=3):
    """N, Dn: per-item arrays (len 100). Returns est, item CI, group CI."""
    est = N.sum() / Dn.sum() if Dn.sum() > 0 else np.nan
    with np.errstate(invalid='ignore', divide='ignore'):
        ri = (WI @ N) / (WI @ Dn)
        rg = (WG_I @ N) / (WG_I @ Dn)
    return est, ri, rg


def per_item(items, vals):
    out = np.zeros(len(ITEMS))
    np.add.at(out, np.array([I_OF[i] for i in items], int), np.asarray(vals, float))
    return out


def fmt(est, ri, rg, nd=3, **extra):
    return {'est': None if not np.isfinite(est) else round(float(est), nd), 'ci_items': ci(ri, nd),
            'ci_groups': ci(rg, nd), **extra}


# ------------------------------------------------------------------------- pair rates within groups (readout / cell)
def pairs(df, gcol, score, isA, isB, match=None, len_tol=None, dedup_key='cache_key'):
    """P(score_A > score_B) for A/B rows in the same group (ties 1/2), pooled over pairs; also mean per-group AUROC.
    Returns dict with est + CIs (items and groups), pairs, groups, items."""
    d = df.loc[isA | isB, [gcol, 'item_id', score, dedup_key, 'stok'] + ([match] if match else [])].copy()
    d['A'] = isA[isA | isB]
    d['B'] = isB[isA | isB]
    W, P, Wm, Pm, its = [], [], [], [], []
    for _, g in d.groupby(gcol, sort=False):
        a = g[g.A]
        b = g[g.B]
        if not len(a) or not len(b):
            continue
        sa, sb = a[score].to_numpy(float), b[score].to_numpy(float)
        diff = sa[:, None] - sb[None, :]
        ok = np.isfinite(diff) & (a[dedup_key].to_numpy()[:, None] != b[dedup_key].to_numpy()[None, :])
        if match:
            ok &= a[match].to_numpy()[:, None] == b[match].to_numpy()[None, :]
        if len_tol is not None:
            ta, tb = a.stok.to_numpy(float)[:, None], b.stok.to_numpy(float)[None, :]
            ok &= np.abs(ta - tb) <= len_tol * np.maximum(ta, tb)
        p = ok.sum()
        if not p:
            continue
        w = ((diff > 0) & ok).sum() + 0.5 * ((diff == 0) & ok).sum()
        W.append(w)
        P.append(p)
        its.append(g.item_id.iloc[0])
    if not P:
        return {'est': None, 'pairs': 0, 'groups': 0}
    W, P = np.array(W, float), np.array(P, float)
    N, Dn = per_item(its, W), per_item(its, P)
    est, ri, rg = ratio_boot(N, Dn)
    Na, Da = per_item(its, W / P), per_item(its, np.ones_like(P))
    e2, ri2, rg2 = ratio_boot(Na, Da)
    return {**fmt(est, ri, rg), 'per_group_mean_auroc': fmt(e2, ri2, rg2), 'pairs': int(P.sum()),
            'groups': len(P), 'items': int((Dn > 0).sum()), 'rel_groups': int(len({bank[i]['cluster'] for i in its}))}


# ------------------------------------------------------------------------- within-group FE regression
def fe_reg(df, gcol, y, cols, contrasts):
    """OLS of y on cols after demeaning within gcol; bootstrap by items and groups via per-item X'X, X'y."""
    d = df[[gcol, 'item_id', y] + cols].dropna().copy()
    Xr = d[cols].to_numpy(float)
    yr = d[y].to_numpy(float)
    gid = pd.factorize(d[gcol])[0]
    ng = gid.max() + 1
    cnt = np.bincount(gid, minlength=ng).astype(float)
    Xm = np.vstack([np.bincount(gid, Xr[:, j], ng) for j in range(Xr.shape[1])]).T / cnt[:, None]
    ym = np.bincount(gid, yr, ng) / cnt
    X = Xr - Xm[gid]
    yy = yr - ym[gid]
    ii = np.array([I_OF[i] for i in d.item_id])
    k = X.shape[1]
    XtX = np.zeros((len(ITEMS), k, k))
    Xty = np.zeros((len(ITEMS), k))
    for i in np.unique(ii):
        m = ii == i
        XtX[i] = X[m].T @ X[m]
        Xty[i] = X[m].T @ yy[m]
    beta = np.linalg.solve(XtX.sum(0), Xty.sum(0))

    def boot(Wt):
        out = []
        for w in Wt:
            A = np.tensordot(w, XtX, 1)
            bvec = w @ Xty
            try:
                out.append(np.linalg.solve(A, bvec))
            except np.linalg.LinAlgError:
                out.append(np.full(k, np.nan))
        return np.array(out)
    bi, bg = boot(WI), boot(WG_I)
    res = {'n': int(len(d)), 'coef': {}}
    for j, c in enumerate(cols):
        res['coef'][c] = fmt(beta[j], bi[:, j], bg[:, j], nd=4)
    for name, vec in contrasts.items():
        v = np.array([vec.get(c, 0.0) for c in cols])
        res['coef'][name] = fmt(beta @ v, bi @ v, bg @ v, nd=4)
    return res


# ------------------------------------------------------------------------- labels
def llm5(raw, lx):
    if raw == 'other_wrong':
        return 'other_value' if lx in ('contrast', 'other_value', 'mixed') else 'other_axis'
    return raw


def final(l5, lx):
    if l5 is None:
        return None
    G = l5 == 'gold' or lx == 'gold'
    Wl, Wx = l5 in WRONG, lx in WRONG
    if l5 == 'mixed' or lx == 'mixed' or (G and (Wl or Wx)):
        return 'mixed'
    if G:
        return 'gold'
    if Wl and Wx:
        return 'wrongX'
    if Wl or Wx:
        return 'wrongX_weak'
    if l5 == 'other_axis':
        return 'other_axis'
    if l5 == 'frame_only' or lx == 'frame_only':
        return 'frame_only'
    if lx == 'other_axis':
        return 'other_axis'
    return 'none'


def clean_item(i):
    return i[:3] in ('q02', 'q03', 'q05', 'q06', 'q09', 'q10') or i in ('q01_a', 'q01_b', 'q01_c', 'q01_d')


def frame_rx(item):
    X = item['contrast_axis']
    ws = sorted({w.lower() for ax, gs in item['credit'].items() if ax != X for g in gs for w in g}, key=len, reverse=True)
    if not ws:
        return None
    return re.compile(r'(?<![\w])(?:' + '|'.join(re.escape(w) for w in ws) + r')(?![\w])', re.I)


def main():
    t0 = time.time()
    with open(SK / 'cache/sk_tables.pkl', 'rb') as f:
        T = pickle.load(f)
    sel, pool, samples = T['sel'], T['pool'], T['samples']
    R = {'bootstrap': {'B': B, 'units': 'ci_items = 100 items; ci_groups = 10 related-item groups q01..q10'}}

    # ---------------- selected-bullet labels
    sel['llm5'] = [llm5(a, b) if a is not None else None for a, b in zip(sel.llm_raw, sel.lex2)]
    sel['final'] = [final(a, b) for a, b in zip(sel.llm5, sel.lex2)]
    sel['clean'] = sel.item_id.map(clean_item)
    fr = {k: frame_rx(it) for k, it in bank.items()}
    sel['inframe'] = [bool(fr[i] and fr[i].search(t)) for i, t in zip(sel.item_id, sel.scored_text.fillna(sel.text))]
    sc = sel[sel.solo.notna() & sel.final.notna()].copy()
    # position adjustment (Original, Best of 32): subtract mean at setting x layer x readout size x position.
    for col in ('solo', 'share'):
        m = sc.groupby(['setting', 'layer', 'nb', 'idx'])[col].transform('mean')
        sc[col + '_adj'] = np.where(sc.setting == 'pooled_greedy_swap-n32', sc[col], sc[col] - m)
    sc['rid'] = sc.cell_id + '|' + sc.setting
    R['counts_final'] = {SL[s]: sc[sc.setting == s].final.value_counts().to_dict() for s in SETTINGS}
    # strict wrong value: how many have LLM raw contrast
    st = sc[sc.final == 'wrongX']
    R['strict_wrong_llm_raw'] = st.llm_raw.value_counts().to_dict()
    log('labels done; strict wrongX raw', R['strict_wrong_llm_raw'])

    # ---------------- A2 within readout
    A2 = {}
    defs = {
        'gold_vs_nongold': (sc.final == 'gold', sc.final.isin(('wrongX', 'wrongX_weak', 'other_axis', 'frame_only', 'none'))),
        'gold_vs_wrongX_strict': (sc.final == 'gold', sc.final == 'wrongX'),
        'gold_vs_wrongX_any': (sc.final == 'gold', sc.final.isin(('wrongX', 'wrongX_weak'))),
        'gold_vs_llmraw_contrast': (sc.final == 'gold', (sc.llm_raw == 'contrast') & (sc.final != 'mixed')),
        'llmgold_vs_llmraw_contrast': (sc.llm_raw == 'gold', sc.llm_raw == 'contrast'),
        'agreedgold_vs_llmraw_contrast_lexwrong': ((sc.llm_raw == 'gold') & (sc.lex2 == 'gold'),
                                                   (sc.llm_raw == 'contrast') & sc.lex2.isin(WRONG)),
        'gold_vs_frame': (sc.final == 'gold', sc.final == 'frame_only'),
        'gold_vs_none': (sc.final == 'gold', sc.final == 'none'),
        'frame_vs_none': (sc.final == 'frame_only', sc.final == 'none'),
    }
    for name, (a, b) in defs.items():
        a, b = a.to_numpy(), b.to_numpy()
        r = {}
        for score in ('solo', 'solo_adj', 'share_adj'):
            r[score] = pairs(sc, 'rid', score, a, b)
        r['solo_adj_len'] = pairs(sc, 'rid', 'solo_adj', a, b, len_tol=0.2)
        for s in SETTINGS:
            m = (sc.setting == s).to_numpy()
            r[f'solo_adj|{SL[s]}'] = pairs(sc, 'rid', 'solo_adj', a & m, b & m)
        A2[name] = r
        log('A2', name, r['solo_adj']['est'], r['solo_adj'].get('ci_groups'), r['solo_adj']['pairs'])
    # FE regression within readout, Original + Best (position dummies) and Combine (no position terms)
    for lab in ('gold', 'wrongX', 'wrongX_weak', 'mixed', 'other_axis', 'frame_only'):
        sc['L_' + lab] = (sc.final == lab).astype(float)
    sc['logtok'] = np.log(sc.stok.clip(lower=1))
    for k in (1, 2, 3):
        sc[f'P{k}'] = (sc.idx == k).astype(float)
    for c in ('cjk', 'scaf', 'instr', 'name'):
        sc[c] = sc[c].astype(float)
    labcols = ['L_gold', 'L_wrongX', 'L_wrongX_weak', 'L_mixed', 'L_other_axis', 'L_frame_only']
    con = {'gold-wrongX': {'L_gold': 1, 'L_wrongX': -1}, 'gold-frame': {'L_gold': 1, 'L_frame_only': -1},
           'wrongX-frame': {'L_wrongX': 1, 'L_frame_only': -1}, 'gold-wrongX_any(avg)': {'L_gold': 1, 'L_wrongX': -0.5, 'L_wrongX_weak': -0.5}}
    ob = sc[sc.setting != 'pooled_greedy_swap-n32']
    A2['fe_solo_orig_best_pos_len'] = fe_reg(ob, 'rid', 'solo', labcols + ['P1', 'P2', 'P3', 'logtok'], con)
    A2['fe_solo_orig_best_pos_len_conf'] = fe_reg(ob, 'rid', 'solo', labcols + ['P1', 'P2', 'P3', 'logtok', 'cjk', 'scaf', 'instr', 'echo', 'name'], con)
    A2['fe_solo_combine_len'] = fe_reg(sc[sc.setting == 'pooled_greedy_swap-n32'], 'rid', 'solo', labcols + ['logtok'], con)
    R['A2'] = A2
    log('A2 fe done')

    # ---------------- A3 within pool
    p = pool[pool.solo.notna()].drop_duplicates(['cell_id', 'cache_key']).reset_index(drop=True)
    p['clean'] = p.item_id.map(clean_item)
    p['inframe'] = [bool(fr[i] and fr[i].search(t[:240])) for i, t in zip(p.item_id, p.text)]
    p['stok'] = p.stok.astype(float)
    gold = (p.lex2 == 'gold').to_numpy()
    wrong = p.lex2.isin(WRONG).to_numpy()
    con_only = (p.lex2 == 'contrast').to_numpy()
    frame = (p.lex2 == 'frame_only').to_numpy()
    none = (p.lex2 == 'none').to_numpy()
    cl = p.clean.to_numpy()
    inf = p.inframe.to_numpy()
    nocjk = ~p.cjk.to_numpy()
    nosc = ~p.scaf.to_numpy()
    A3 = {'counts': {'pool_dedup': int(len(p)), 'gold': int(gold.sum()), 'wrongX': int(wrong.sum()),
                     'gold_inframe': int((gold & inf).sum()), 'wrongX_inframe': int((wrong & inf).sum()),
                     'cjk_rate_by_label': p.groupby('lex2').cjk.mean().round(3).to_dict(),
                     'scaf_rate_by_label': p.groupby('lex2').scaf.mean().round(3).to_dict(),
                     'echo_mean_by_label': p.groupby('lex2').echo.mean().round(3).to_dict(),
                     'instr_rate_by_label': p.groupby('lex2').instr.mean().round(3).to_dict(),
                     'inframe_rate_by_label': p.groupby('lex2').inframe.mean().round(3).to_dict(),
                     'stok_mean_by_label': p.groupby('lex2').stok.mean().round(1).to_dict(),
                     'pos_mean_by_label': p.groupby('lex2').pos.mean().round(2).to_dict()}}
    var = {
        'headline': (gold, wrong, {}),
        'contrast_only': (gold, con_only, {}),
        'clean_items': (gold & cl, wrong & cl, {}),
        'both_inframe': (gold & inf, wrong & inf, {}),
        'clean_and_inframe': (gold & cl & inf, wrong & cl & inf, {}),
        'no_cjk_no_scaffold': (gold & nocjk & nosc, wrong & nocjk & nosc, {}),
        'same_pos': (gold, wrong, {'match': 'pos'}),
        'len_matched': (gold, wrong, {'len_tol': 0.2}),
        'gold_vs_frame': (gold, frame, {}),
        'gold_vs_frame_inframe': (gold & inf, frame & inf, {}),
        'wrongX_vs_frame': (wrong, frame, {}),
        'wrongX_vs_frame_inframe': (wrong & inf, frame & inf, {}),
        'gold_vs_none': (gold, none, {}),
        'frame_vs_none': (frame, none, {}),
    }
    for name, (a, b, kw) in var.items():
        A3[name] = pairs(p, 'cell_id', 'solo', a, b, **kw)
        log('A3', name, A3[name]['est'], A3[name].get('ci_groups'), A3[name]['pairs'], A3[name].get('groups'))
    for L in (20, 36, 44, 52, 60):
        m = (p.layer == L).to_numpy()
        A3[f'L{L}'] = {'gold_vs_wrongX': pairs(p, 'cell_id', 'solo', gold & m, wrong & m),
                       'gold_vs_frame': pairs(p, 'cell_id', 'solo', gold & m, frame & m),
                       'frame_vs_none': pairs(p, 'cell_id', 'solo', frame & m, none & m)}
    for st_ in sorted(p.site.unique()):
        m = (p.site == st_).to_numpy()
        A3[f'site:{st_}'] = {'gold_vs_wrongX': pairs(p, 'cell_id', 'solo', gold & m, wrong & m),
                             'gold_vs_frame': pairs(p, 'cell_id', 'solo', gold & m, frame & m),
                             'frame_vs_none': pairs(p, 'cell_id', 'solo', frame & m, none & m)}
    for g in GROUPS:
        m = (p.group == g).to_numpy()
        A3[f'group:{g}'] = pairs(p, 'cell_id', 'solo', gold & m, wrong & m)
        A3[f'drop_group:{g}'] = pairs(p, 'cell_id', 'solo', gold & ~m, wrong & ~m)['est']
    # two-direction groups (balanced over which value is gold)
    gv = {k: json.dumps(it['cell'].get(it['contrast_axis']), sort_keys=True) for k, it in bank.items()}
    p['gval'] = p.item_id.map(gv)
    two = {}
    reps_i, reps_g, ests = [], [], []
    for g in GROUPS:
        if g == 'q01':
            continue
        vals = sorted(p[p.group == g].gval.unique())
        if len(vals) != 2:
            continue
        dirs = []
        for v in vals:
            m = ((p.group == g) & (p.gval == v)).to_numpy()
            d = p.loc[(gold | wrong) & m]
            # per-item wins/pairs
            W_, P_, its = [], [], []
            for cid, gg in d.groupby('cell_id'):
                a = gg[gg.lex2 == 'gold']
                b = gg[gg.lex2.isin(WRONG)]
                if not len(a) or not len(b):
                    continue
                diff = a.solo.to_numpy()[:, None] - b.solo.to_numpy()[None, :]
                W_.append((diff > 0).sum() + 0.5 * (diff == 0).sum())
                P_.append(diff.size)
                its.append(gg.item_id.iloc[0])
            if not P_:
                dirs = None
                break
            N, Dn = per_item(its, W_), per_item(its, P_)
            dirs.append(ratio_boot(N, Dn))
        if not dirs:
            two[g] = 'one direction missing'
            continue
        (e1, i1, g1), (e2, i2, g2) = dirs
        two[g] = {'dir_rates': [round(e1, 3), round(e2, 3)], 'balanced': round(0.5 * (e1 + e2), 3),
                  'balanced_ci_items': ci(0.5 * (i1 + i2))}
        ests.append(0.5 * (e1 + e2))
        reps_i.append(0.5 * (i1 + i2))
    two['mean_balanced'] = {'est': round(float(np.mean(ests)), 3), 'ci_items': ci(np.nanmean(np.vstack(reps_i), 0)),
                            'n_groups': len(ests),
                            # group-level: resample the balanced group estimates themselves
                            'ci_groups_resample_groups': ci([np.mean(rng.choice(ests, len(ests))) for _ in range(B)])}
    A3['two_direction'] = two
    # FE regression within cell
    for lab in ('gold', 'contrast', 'other_value', 'mixed', 'other_axis', 'frame_only'):
        p['L_' + lab] = (p.lex2 == lab).astype(float)
    p['L_wrongX'] = p.lex2.isin(WRONG).astype(float)
    p['logtok'] = np.log(p.stok.clip(lower=1))
    for k in (1, 2, 3):
        p[f'P{k}'] = (p.pos == k).astype(float)
    for c in ('cjk', 'scaf', 'instr', 'name', 'inframe'):
        p[c] = p[c].astype(float)
    p['pct'] = p.groupby('cell_id').solo.rank(pct=True)
    labc = ['L_gold', 'L_wrongX', 'L_mixed', 'L_other_axis', 'L_frame_only']
    conp = {'gold-wrongX': {'L_gold': 1, 'L_wrongX': -1}, 'gold-frame': {'L_gold': 1, 'L_frame_only': -1},
            'wrongX-frame': {'L_wrongX': 1, 'L_frame_only': -1}}
    A3['fe_solo_labels_only'] = fe_reg(p, 'cell_id', 'solo', labc, conp)
    A3['fe_solo_full'] = fe_reg(p, 'cell_id', 'solo', labc + ['P1', 'P2', 'P3', 'logtok', 'cjk', 'scaf', 'instr', 'echo', 'name', 'inframe'], conp)
    A3['fe_pct_full'] = fe_reg(p, 'cell_id', 'pct', labc + ['P1', 'P2', 'P3', 'logtok', 'cjk', 'scaf', 'instr', 'echo', 'name', 'inframe'], conp)
    pc = p[p.clean]
    A3['fe_solo_full_clean'] = fe_reg(pc, 'cell_id', 'solo', labc + ['P1', 'P2', 'P3', 'logtok', 'cjk', 'scaf', 'instr', 'echo', 'name', 'inframe'], conp)
    # cell-level solo scale: mean and sd of solo within cell, by layer (for converting FVE differences)
    A3['solo_scale'] = {'mean_within_cell_sd': round(float(p.groupby('cell_id').solo.std().mean()), 4),
                        'mean_solo_by_layer': p.groupby('layer').solo.mean().round(4).to_dict()}
    # pool solo means by label (A1 cross-check), item-weighted ratio
    A1p = {}
    for lab in ('gold', 'contrast', 'other_value', 'frame_only', 'none', 'other_axis'):
        m = (pool.lex2 == lab) & pool.solo.notna()
        N, Dn = per_item(pool.item_id[m], pool.solo[m]), per_item(pool.item_id[m], np.ones(m.sum()))
        e, ri, rg = ratio_boot(N, Dn)
        A1p[lab] = fmt(e, ri, rg, nd=4, n=int(m.sum()))
    R['A1_pool_solo'] = A1p
    R['A3'] = A3
    log('A3 done')

    # ---------------- A4 selection
    A4 = {}
    item_of = dict(zip(sel.cell_id, sel.item_id))
    cells = sorted(sel.cell_id.unique())
    has = {}
    for lab in ('gold', 'wrongX', 'frame_only'):
        vals = {}
        for s in SETTINGS:
            d = sel[(sel.setting == s) & sel.final.notna()]
            h = d.groupby('cell_id').final.apply(lambda x: float((x == lab).any()))
            vals[s] = h.reindex(cells)
        rr = {}
        for s in SETTINGS:
            v = vals[s].to_numpy()
            ok = np.isfinite(v)
            e, ri, rg = ratio_boot(per_item([item_of[c] for c in np.array(cells)[ok]], v[ok]),
                                   per_item([item_of[c] for c in np.array(cells)[ok]], np.ones(ok.sum())))
            rr[SL[s]] = fmt(e, ri, rg)
        for a_, b_ in ((1, 0), (2, 0), (2, 1)):
            va, vb = vals[SETTINGS[a_]].to_numpy(), vals[SETTINGS[b_]].to_numpy()
            ok = np.isfinite(va) & np.isfinite(vb)
            its = [item_of[c] for c in np.array(cells)[ok]]
            e, ri, rg = ratio_boot(per_item(its, va[ok] - vb[ok]), per_item(its, np.ones(ok.sum())))
            rr[f'{SL[SETTINGS[a_]]} - {SL[SETTINGS[b_]]}'] = fmt(e, ri, rg)
        has[f'final:{lab}'] = rr
    A4['readout_has'] = has
    # lex2 gold: selected vs random baselines from the pool
    pp = pool[pool.solo.notna()]
    flag = pp.lex2.eq('gold')
    samp = flag.groupby([pp.cell_id, pp.sample_index]).any()
    frac32 = samp.groupby(level=0).mean()
    any32 = samp.groupby(level=0).any().astype(float)
    pu = pp.drop_duplicates(['cell_id', 'cache_key'])
    ng = pu.lex2.eq('gold').groupby(pu.cell_id).sum()
    nn = pu.groupby('cell_id').size()
    from math import comb
    rand4 = pd.Series({c: (1 - comb(int(nn[c] - ng.get(c, 0)), 4) / comb(int(nn[c]), 4)) if nn[c] >= 4 else float(ng.get(c, 0) > 0)
                       for c in nn.index})
    selg = {s: sel[sel.setting == s].groupby('cell_id').lex2.apply(lambda x: float((x == 'gold').any())) for s in SETTINGS}
    cols = {'random one of 32': frac32, 'random 4 pool bullets': rand4, 'pool has it': any32, **{SL[s]: selg[s] for s in SETTINGS}}
    M = pd.DataFrame({k: v.reindex(cells) for k, v in cols.items()}).dropna()
    its = [item_of[c] for c in M.index]
    one = np.ones(len(M))
    base = {k: fmt(*ratio_boot(per_item(its, M[k]), per_item(its, one))) for k in M.columns}
    for a_, b_ in (('Original', 'random one of 32'), ('Best of 32', 'random one of 32'), ('Combine 32', 'random 4 pool bullets'),
                   ('Best of 32', 'Original')):
        base[f'{a_} - {b_}'] = fmt(*ratio_boot(per_item(its, M[a_] - M[b_]), per_item(its, one)))
    hp = M['pool has it'] > 0
    base['cells'] = int(len(M))
    base['missing_given_pool_has'] = {s: round(float((M.loc[hp, s] == 0).mean()), 3) for s in ('Original', 'Best of 32', 'Combine 32')}
    A4['lex2_gold_vs_random'] = base
    # sample-level: joint FVE of each sample (Best of 32 trace) vs whether it names gold
    sf = pp.assign(g=pp.lex2.eq('gold'), w=pp.lex2.isin(WRONG)).groupby(['cell_id', 'sample_index'])[['g', 'w']].any().reset_index()
    S = samples[samples.joint.notna()].merge(sf, on=['cell_id', 'sample_index'], how='left')
    S[['g', 'w']] = S[['g', 'w']].fillna(False).astype(bool)
    S['item_id'] = S.cell_id.map(item_of)
    S['stok'] = 1.0
    S['ck'] = S.sample_index
    g_, w_ = S.g.to_numpy(), S.w.to_numpy()
    A4['sample_gold_vs_nogold'] = pairs(S, 'cell_id', 'joint', g_, ~g_, dedup_key='ck')
    A4['sample_gold_vs_wrongonly'] = pairs(S, 'cell_id', 'joint', g_, w_ & ~g_, dedup_key='ck')
    cS = S.item_id.map(clean_item).to_numpy()
    A4['sample_gold_vs_wrongonly_clean'] = pairs(S, 'cell_id', 'joint', g_ & cS, w_ & ~g_ & cS, dedup_key='ck')
    # judge per cell
    j = sel.drop_duplicates(['cell_id', 'setting'])[['cell_id', 'setting', 'item_id', 'judge_pick']]
    jr = {}
    jv = {}
    for s in SETTINGS:
        d = j[j.setting == s].set_index('cell_id').reindex(cells)
        v = (d.judge_pick == 'gold').astype(float).to_numpy()
        jv[s] = v
        jr[SL[s]] = fmt(*ratio_boot(per_item([item_of[c] for c in cells], v), per_item([item_of[c] for c in cells], np.ones(len(v)))), nd=4)
    for a_, b_ in ((1, 0), (2, 0)):
        jr[f'{SL[SETTINGS[a_]]} - {SL[SETTINGS[b_]]}'] = fmt(*ratio_boot(
            per_item([item_of[c] for c in cells], jv[SETTINGS[a_]] - jv[SETTINGS[b_]]),
            per_item([item_of[c] for c in cells], np.ones(len(cells)))), nd=4)
    A4['judge_gold_per_cell'] = jr
    # judge gold rate by layer and site (pooled settings)
    jj = j.merge(sel.drop_duplicates('cell_id')[['cell_id', 'layer', 'site']], on='cell_id')
    A4['judge_gold_by_layer'] = jj.groupby('layer').judge_pick.apply(lambda x: round(float((x == 'gold').mean()), 4)).to_dict()
    A4['judge_gold_by_site'] = jj.groupby('site').judge_pick.apply(lambda x: round(float((x == 'gold').mean()), 4)).to_dict()
    A4['lex2gold_readout_by_layer'] = sel.groupby('layer').apply(lambda d: round(float(d.groupby(['cell_id', 'setting']).lex2.apply(lambda x: (x == 'gold').any()).mean()), 3)).to_dict()
    A4['lex2gold_readout_by_site'] = sel.groupby('site').apply(lambda d: round(float(d.groupby(['cell_id', 'setting']).lex2.apply(lambda x: (x == 'gold').any()).mean()), 3)).to_dict()
    R['A4'] = A4
    log('A4 done')

    # ---------------- confound descriptives on the pool (within-cell percentile)
    cd = {}
    for c in ('cjk', 'cjk_lead', 'scaf', 'instr', 'name'):
        cd[c] = {'rate': round(float(p[c].astype(bool).mean()), 3) if c in p else None,
                 'mean_pct_true': round(float(p.loc[p[c].astype(bool), 'pct'].mean()), 3),
                 'mean_pct_false': round(float(p.loc[~p[c].astype(bool), 'pct'].mean()), 3)}
    p['echo_bin'] = pd.cut(p.echo, [-0.01, 0, 0.1, 0.25, 1.0])
    cd['echo_bins_pct'] = {str(k): round(float(v), 3) for k, v in p.groupby('echo_bin', observed=True).pct.mean().items()}
    cd['echo_bins_n'] = {str(k): int(v) for k, v in p.groupby('echo_bin', observed=True).size().items()}
    cd['pos_pct'] = p.groupby('pos').pct.mean().round(3).to_dict()
    p['tokbin'] = pd.cut(p.stok, [0, 8, 16, 24, 31, 32])
    cd['tok_pct'] = {str(k): round(float(v), 3) for k, v in p.groupby('tokbin', observed=True).pct.mean().items()}
    cd['gold_rate_by_layer'] = p.groupby('layer').apply(lambda d: round(float((d.lex2 == 'gold').mean()), 4)).to_dict()
    cd['gold_rate_by_site'] = p.groupby('site').apply(lambda d: round(float((d.lex2 == 'gold').mean()), 4)).to_dict()
    cd['wrong_rate_by_layer'] = p.groupby('layer').apply(lambda d: round(float(d.lex2.isin(WRONG).mean()), 4)).to_dict()
    cd['cjk_rate_by_layer'] = p.groupby('layer').cjk.mean().round(3).to_dict()
    cd['cjk_rate_by_site'] = p.groupby('site').cjk.mean().round(3).to_dict()
    R['confounds_pool'] = cd
    # LLM vs lex2 on CJK selected bullets: is lexicon gold recall worse on CJK bullets?
    u = sc.drop_duplicates(['cell_id', 'text'])
    R['cjk_label_check'] = {
        'llm_gold_rate': u.groupby('cjk').llm_raw.apply(lambda x: round(float((x == 'gold').mean()), 4)).to_dict(),
        'lex2_gold_rate': u.groupby('cjk').lex2.apply(lambda x: round(float((x == 'gold').mean()), 4)).to_dict(),
        'lex2_recall_of_llm_gold': u[u.llm_raw == 'gold'].groupby('cjk').lex2.apply(lambda x: round(float((x == 'gold').mean()), 3)).to_dict(),
        'n': u.groupby('cjk').size().to_dict()}
    R['runtime_s'] = round(time.time() - t0, 1)
    with open(SK / 'sk_results.json', 'w') as f:
        json.dump(R, f, indent=1, default=str)
    log('wrote sk_results.json', R['runtime_s'])


if __name__ == '__main__':
    main()
