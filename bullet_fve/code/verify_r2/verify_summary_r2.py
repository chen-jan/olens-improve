#!/usr/bin/env python3
"""Round-2 independent recheck of summary.json headline numbers from page/data/index.json (+ items/*.json for
5-decimal per-bullet scores and span offsets). Own implementation (numpy); read-only except OUT.json.
Usage: python -B verify_summary_r2.py OUT.json [--reps 1000]
"""
import argparse, collections, json, sys, time
from pathlib import Path
import numpy as np

T0 = time.time()
PAGE = Path('${OLENS_SCRATCH}/olens-bullet-fve/page/data')
CODES = ['consistent', 'hallucinated', 'off_topic', 'generic', 'empty']
SC = ['shap', 'shap_share', 'solo', 'drop']
FAILS, NOTES = [], []
NCHK = [0]


def chk(ok, where, msg):
    NCHK[0] += 1
    if not ok:
        FAILS.append(f'{where}: {msg}')


def auc_w(vals, isw, isc, wts):
    """weighted P(clean > wrong) + 0.5 ties; wts per bullet."""
    v = vals
    w_w = np.where(isw, wts, 0.0); w_c = np.where(isc, wts, 0.0)
    order = np.argsort(v, kind='mergesort')
    vs = v[order]; ww = w_w[order]; wc = w_c[order]
    # group ties
    uniq, start = np.unique(vs, return_index=True)
    gw = np.add.reduceat(ww, start); gc = np.add.reduceat(wc, start)
    cw_below = np.cumsum(gw) - gw
    num = np.sum(gc * (cw_below + 0.5 * gw))
    den = ww.sum() * wc.sum()
    return num / den if den > 0 else np.nan


def midrank_pct(x):
    order = np.argsort(x, kind='mergesort')
    xs = x[order]
    r = np.empty(len(x))
    i = 0
    n = len(x)
    while i < n:
        j = i
        while j + 1 < n and xs[j + 1] == xs[i]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    return r / n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--reps', type=int, default=1000)
    args = ap.parse_args()
    idx = json.load(open(PAGE / 'index.json'))
    summ = json.load(open(PAGE / 'summary.json'))
    sids = [s['id'] for s in idx['meta']['settings']]
    short = {s['id']: s['short'] for s in idx['meta']['settings']}
    items = {}
    for it in idx['items']:
        items[it['id']] = json.load(open(PAGE / 'items' / f"{it['id']}.json"))
    n_items = len(idx['items'])
    print('loaded', f'{time.time()-T0:.0f}s', flush=True)
    rng = np.random.default_rng(12345)
    M = np.stack([np.bincount(rng.integers(0, n_items, n_items), minlength=n_items) for _ in range(args.reps)]).astype(float)
    out = {}
    for j, sid in enumerate(sids):
        S = summ['settings'][sid]
        W = short[sid]
        # readout level
        codes = np.array([c['s'][j]['c'] for c in idx['cells']])
        f = np.array([c['s'][j]['f'] for c in idx['cells']])
        it_of = np.array([c['i'] for c in idx['cells']])
        lc = {CODES[k]: int((codes == k).sum()) for k in range(5)}
        chk(lc == S['label_counts'], W, f'label counts {lc} vs {S["label_counts"]}')
        chk(abs(f.mean() - S['mean_fve']) < 2e-5, W, f'mean fve {f.mean():.5f} vs {S["mean_fve"]}')
        hr = lc['hallucinated'] / (lc['hallucinated'] + lc['consistent'] + lc['off_topic'])
        chk(abs(hr - S['hallucinated_rate_of_specific']) < 1e-5, W, f'hall rate {hr}')
        for k in range(5):
            if (codes == k).any():
                chk(abs(f[codes == k].mean() - S['mean_fve_by_label'][CODES[k]]) < 2e-5, W, f'mean fve {CODES[k]}')
        cons = codes == 0; hal = codes == 1
        ra = auc_w(f, hal, cons, np.ones(len(f)))
        chk(abs(ra - S['readout_fve_auroc']['est']) < 6e-4, W, f'readout fve auroc mine {ra:.4f} vs {S["readout_fve_auroc"]["est"]}')
        # readout auroc bootstrap
        rb = np.array([auc_w(f, hal, cons, M[r][it_of]) for r in range(min(args.reps, 300))])
        lo, hi = np.percentile(rb, [2.5, 97.5])
        chk(abs(lo - S['readout_fve_auroc']['lo']) < 0.006 and abs(hi - S['readout_fve_auroc']['hi']) < 0.006, W,
            f'readout auroc CI mine [{lo:.4f},{hi:.4f}] vs [{S["readout_fve_auroc"]["lo"]},{S["readout_fve_auroc"]["hi"]}]')
        # bullet rows from items (5dp)
        B = collections.defaultdict(list)
        for ci, c in enumerate(idx['cells']):
            st = c['s'][j]
            pc = items[idx['items'][c['i']]['id']]['cells'][c['k']]['settings'][sid]
            chk([b['label'] for b in pc['bullets']] == st['bl'], W, f'{c["k"]} bl index vs item')
            for bi, b in enumerate(pc['bullets']):
                B['lab'].append(b['label']); B['item'].append(c['i']); B['ro'].append(ci); B['pos'].append(bi)
                B['size'].append(st['n']); B['layer'].append(c['L']); B['rc'].append(st['c'])
                B['shap'].append(b['shap']); B['shap_share'].append(b['shap_share']); B['solo'].append(b['solo']); B['drop'].append(b['drop'])
                B['idx_ss'].append(st['ss'][bi]); B['idx_so'].append(st['so'][bi])
                # strict: own wrong span with an occurrence starting before scored_end
                if b['label'] == 'w':
                    own = False
                    for sp in pc['spans']:
                        if sp['verified'] and sp['type'] == 'wrong' and sp['bullets'] == [bi]:
                            if any(a < b['scored_end'] and e > b['start'] for a, e in sp['offsets']):
                                own = True
                    B['strict_keep'].append(own)
                else:
                    B['strict_keep'].append(True)
        A = {k: np.array(v) for k, v in B.items()}
        lab = A['lab']
        bc = {x: int((lab == x).sum()) for x in 'wocx'}
        chk(bc == S['bullet_counts'], W, f'bullet counts {bc} vs {S["bullet_counts"]}')
        isw = lab == 'w'; isc = lab == 'c'
        cbl = {CODES[k]: int((isc & (A['rc'] == k)).sum()) for k in range(3)}
        chk(cbl == S['clean_by_readout_label'], W, f'clean_by_readout_label {cbl}')
        chk(int((isw & (A['rc'] != 1)).sum()) == 0, W, 'wrong bullets outside hallucinated readouts')
        ones = np.ones(len(lab))
        res = {}
        # position-adjusted percentiles
        labelled = np.isin(lab, ['w', 'c', 'o'])
        pct = {}
        cen = {}
        for s in SC:
            v = np.round(A[s].astype(float), 9)
            p_ = np.full(len(v), np.nan); c_ = np.full(len(v), np.nan)
            for key in set(zip(A['pos'][labelled], A['size'][labelled])):
                m = labelled & (A['pos'] == key[0]) & (A['size'] == key[1])
                p_[m] = midrank_pct(v[m]); c_[m] = v[m] - v[m].mean()
            pct[s] = p_; cen[s] = c_
        # mixed readouts and pairs
        ro = A['ro']
        mixed = set(ro[isw]) & set(ro[isc])
        inmix = np.isin(ro, list(mixed))
        mp = S['mixed_readout_position']
        mw = A['pos'][isw & inmix].mean(); mc = A['pos'][isc & inmix].mean()
        chk(len(mixed) == mp['n_readouts'] and abs(mw - mp['mean_bullet_index_wrong']) < 1e-4 and abs(mc - mp['mean_bullet_index_clean']) < 1e-4, W,
            f'mixed n {len(mixed)} idx w {mw:.4f} c {mc:.4f} vs {mp}')
        # pairs
        pairs = []  # (item, wi, ci)
        byro = collections.defaultdict(lambda: ([], []))
        for bi_ in np.nonzero(inmix & (isw | isc))[0]:
            byro[ro[bi_]][0 if isw[bi_] else 1].append(bi_)
        for r_, (ws, cs) in byro.items():
            for a in ws:
                for c_ in cs:
                    pairs.append((A['item'][a], a, c_))
        P = np.array(pairs)
        for s in SC:
            v = np.round(A[s].astype(float), 9)
            Sb = S['scores'][s]
            a_ = auc_w(v, isw, isc, ones)
            chk(abs(a_ - Sb['auroc']['est']) < 1.5e-3, W, f'{s} auroc mine {a_:.4f} vs {Sb["auroc"]["est"]}')
            hcl = isc & (A['rc'] == 1)
            a2 = auc_w(v, isw, hcl, ones)
            chk(abs(a2 - Sb['auroc_clean_in_hallucinated']['est']) < 1.5e-3, W, f'{s} auroc_clean_in_hall mine {a2:.4f} vs {Sb["auroc_clean_in_hallucinated"]["est"]}')
            def prate(vv, w_items=None):
                d = np.sign(vv[P[:, 2]] - vv[P[:, 1]])
                val = (d > 0) + 0.5 * (d == 0)
                wt = np.ones(len(P)) if w_items is None else w_items[P[:, 0]]
                return (val * wt).sum() / wt.sum()
            pr = prate(v)
            chk(abs(pr - Sb['pair_rate']['est']) < 1.5e-3 and len(P) == Sb['pair_rate']['n_pairs'], W, f'{s} pair mine {pr:.4f} n {len(P)} vs {Sb["pair_rate"]}')
            pa = prate(pct[s])
            chk(abs(pa - Sb['pair_rate_pos_adj']['est']) < 1.5e-3, W, f'{s} pair_pos_adj mine {pa:.4f} vs {Sb["pair_rate_pos_adj"]["est"]}')
            pcn = prate(np.round(cen[s], 9))
            chk(abs(pcn - Sb['pair_rate_pos_centred']['est']) < 2e-3, W, f'{s} pair_pos_centred mine {pcn:.4f} vs {Sb["pair_rate_pos_centred"]["est"]}')
            # bootstrap CIs (own rng)
            R = min(args.reps, 400)
            bA = np.array([auc_w(v, isw, isc, M[r][A['item']]) for r in range(R)])
            bP = np.array([prate(v, M[r]) for r in range(R)])
            bQ = np.array([prate(pct[s], M[r]) for r in range(R)])
            ciA = np.percentile(bA, [2.5, 97.5]); ciP = np.percentile(bP, [2.5, 97.5]); ciQ = np.percentile(bQ, [2.5, 97.5])
            for nm, ci_, ref in (('auroc', ciA, Sb['auroc']), ('pair', ciP, Sb['pair_rate']), ('pos_adj', ciQ, Sb['pair_rate_pos_adj'])):
                chk(abs(ci_[0] - ref['lo']) < 0.006 and abs(ci_[1] - ref['hi']) < 0.006, W, f'{s} {nm} CI mine [{ci_[0]:.4f},{ci_[1]:.4f}] vs [{ref["lo"]},{ref["hi"]}]')
            res[s] = dict(auroc=a_, auroc_hcl=a2, pair=pr, pos_adj=pa, pos_cent=pcn, ciA=ciA.tolist(), ciP=ciP.tolist(), ciQ=ciQ.tolist())
            # by layer
            for L in idx['meta']['layers']:
                bl_ = S['by_layer'][str(L)]
                if s in bl_['auroc']:
                    mL = A['layer'] == L
                    aL = auc_w(v, isw & mL, isc & mL, ones)
                    chk(abs(aL - bl_['auroc'][s]['est']) < 2e-3, W, f'L{L} {s} auroc mine {aL:.4f} vs {bl_["auroc"][s]["est"]}')
                    PL = A['layer'][P[:, 1]] == L
                    d = np.sign(v[P[PL, 2]] - v[P[PL, 1]]); prL = ((d > 0) + 0.5 * (d == 0)).mean()
                    chk(abs(prL - bl_['pair_rate'][s]['est']) < 2e-3 and PL.sum() == bl_['pair_rate'][s]['n_pairs'], W, f'L{L} {s} pair mine {prL:.4f} vs {bl_["pair_rate"][s]["est"]}')
                    d = np.sign(pct[s][P[PL, 2]] - pct[s][P[PL, 1]]); paL = ((d > 0) + 0.5 * (d == 0)).mean()
                    chk(abs(paL - bl_['pair_rate_pos_adj'][s]['est']) < 2e-3, W, f'L{L} {s} pos_adj mine {paL:.4f} vs {bl_["pair_rate_pos_adj"][s]["est"]}')
            # means
            for g, m in (('wrong', isw), ('clean', isc), ('off_topic', lab == 'o')):
                chk(abs(v[m].mean() - Sb[g]['mean']) < 2e-5 and int(m.sum()) == Sb[g]['n'], W, f'{s} {g} mean {v[m].mean():.5f} vs {Sb[g]["mean"]}')
        # by position (specific readouts)
        for pi, bp in enumerate(S['by_position']):
            m = labelled & (A['pos'] == pi)
            chk(int(m.sum()) == bp['n'] and int((m & isw).sum()) == bp['n_wrong'] and int((m & isc).sum()) == bp['n_clean'], W, f'by_position {pi} counts')
            chk(abs(A['shap_share'][m].mean() - bp['mean_shap_share']) < 2e-4 and abs(A['shap_share'][m & isc].mean() - bp['mean_shap_share_clean']) < 2e-4
                and abs(A['shap_share'][m & isw].mean() - bp['mean_shap_share_wrong']) < 2e-4, W,
                f'by_position {pi} shares mine {A["shap_share"][m].mean():.4f}/{A["shap_share"][m & isc].mean():.4f}/{A["shap_share"][m & isw].mean():.4f} vs {bp}')
        # 4-bullet single-wrong readouts with wrong at index 2/3 (fixer cell-level evidence)
        one = []
        for r_, (ws, cs) in byro.items():
            if len(ws) == 1 and A['size'][ws[0]] == 4:
                one.append((r_, ws[0], cs))
        late = [x for x in one if A['pos'][x[1]] in (2, 3)]
        def pr_sub(sub, vv):
            vals = [((vv[c_] > vv[w_]) + 0.5 * (vv[c_] == vv[w_])) for _, w_, cs in sub for c_ in cs]
            return float(np.mean(vals)) if vals else None
        out_sub = {'n_single_wrong_4': len(one), 'n_late': len(late)}
        for pp in (2, 3):
            sub = [x for x in one if A['pos'][x[1]] == pp]
            out_sub[f'raw_share_pos{pp}'] = pr_sub(sub, np.round(A['shap_share'].astype(float), 9))
            out_sub[f'adj_share_pos{pp}'] = pr_sub(sub, pct['shap_share'])
        # strict
        SS = summ['settings_strict'][sid]
        keep = A['strict_keep'].astype(bool)
        nw_strict = int((isw & keep).sum())
        chk(nw_strict == SS['bullet_counts']['w'] and int((isw & ~keep).sum()) == SS['excluded_wrong']['total'], W,
            f'strict w mine {nw_strict} excluded {int((isw & ~keep).sum())} vs {SS["bullet_counts"]["w"]} / {SS["excluded_wrong"]["total"]}')
        for s in SC:
            v = np.round(A[s].astype(float), 9)
            a_ = auc_w(v, isw & keep, isc, ones)
            chk(abs(a_ - SS['scores'][s]['auroc']['est']) < 1.5e-3, W, f'strict {s} auroc mine {a_:.4f} vs {SS["scores"][s]["auroc"]["est"]}')
        out[sid] = {'readout_auroc': ra, 'scores': res, 'mixed': [len(mixed), mw, mc], 'subset': out_sub, 'strict_w': nw_strict}
        print(sid, 'done', f'{time.time()-T0:.0f}s', len(FAILS), flush=True)
        # example cells cited by fixer (pct of shares)
        if sid == 'best_n_exact-n32':
            for k_, wb, cb in (('chat-dailydialog-0027.L52.p59', 3, 0), ('chat-dailydialog-0013.L44.p69', 3, 0)):
                ci = next(i for i, c in enumerate(idx['cells']) if c['k'] == k_)
                bis = np.nonzero(ro == ci)[0]
                out[sid].setdefault('examples', {})[k_] = [(int(A['pos'][b]), str(lab[b]), float(A['shap_share'][b]), float(pct['shap_share'][b])) for b in bis]
    # caveats / examples
    for e in summ['examples']:
        it = e['k'].split('.L')[0]
        pc = items[it]['cells'][e['k']]['settings'][e['setting']]
        b = pc['bullets'][e['bullet']]
        chk(abs(b['shap_share'] - e['shap_share']) < 2e-4 and abs(b['solo'] - e['solo']) < 2e-5 and b['label'] == 'w'
            and pc['label'] == e['readout_label'] and abs(pc['fve'] - e['joint_fve']) < 2e-5
            and pc['text'][b['start']:b['end']] == e['bullet_text'], 'examples', f'{e["k"]} {e["setting"]} b{e["bullet"]}')
    res = {'n_checks': NCHK[0], 'n_fail': len(FAILS), 'fails': FAILS, 'out': out, 'wall': round(time.time() - T0, 1)}
    json.dump(res, open(args.out, 'w'), indent=1, default=float)
    print('checks', NCHK[0], 'fails', len(FAILS))
    for f_ in FAILS:
        print('FAIL', f_)
    print(json.dumps(out, indent=0, default=float)[:6000])


if __name__ == '__main__':
    main()
