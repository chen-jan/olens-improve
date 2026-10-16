import pickle, math, collections
import numpy as np
D = pickle.load(open('${OLENS_SCRATCH}/olens-bullet-fve/reading/verify_C3_evidence/rows.pkl', 'rb'))
rows, items = D['rows'], D['items']; IX = {x: i for i, x in enumerate(items)}
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']; SH = dict(zip(SIDS, ['Orig', 'Best', 'Comb']))
rng = np.random.default_rng(3); B = 1000
W = np.stack([np.bincount(rng.integers(0, len(items), len(items)), minlength=len(items)) for _ in range(B)]).astype(float)
LAB = [r for r in rows if r['label'] in ('w', 'c', 'o') and r['share'] is not None and not r['dup']]
def run(sid, feats, y='solo', label_only=False, extra=None):
    R = [r for r in LAB if r['sid'] == sid and not math.isnan(r['prv_ov']) and not math.isnan(r['nxt_ov'])]
    cols = []
    for r in R:
        v = [float(r['label'] == 'w'), float(r['label'] == 'o')]
        if not label_only:
            v += [f(r) for _, f in feats]
            if sid != SIDS[2]: v += [float(r['j'] == 1), float(r['j'] == 2), float(r['j'] == 3)]
        cols.append(v)
    X = np.array(cols); Y = np.array([r[y] for r in R]); g = collections.defaultdict(list)
    for i, r in enumerate(R): g[r['k']].append(i)
    for ii in g.values(): X[ii] -= X[ii].mean(0); Y[ii] -= Y[ii].mean()
    names = ['is_w', 'is_o'] + ([n for n, _ in feats] + (['pos2', 'pos3', 'pos4'] if sid != SIDS[2] else []) if not label_only else [])
    sd = X.std(0); cont = {'log_len', 'cjk', 'nxt_ov', 'prv_ov'}
    X = X / np.array([sd[i] if n in cont else 1. for i, n in enumerate(names)])
    ix = np.array([IX[r['item']] for r in R])
    fit = lambda w: np.linalg.solve(X.T @ (X * w[ix][:, None]), X.T @ (Y * w[ix]))
    est = fit(np.ones(len(items))); bs = np.array([fit(w) for w in W])
    r2 = 1 - ((Y - X @ est) ** 2).sum() / (Y ** 2).sum()
    return names, est, bs, r2, len(R), Y.std()
feats = [('log_len', lambda r: math.log(max(1, r['len16']))), ('cjk', lambda r: r['cjk']), ('nxt_ov', lambda r: r['nxt_ov']),
         ('prv_ov', lambda r: r['prv_ov']), ('num_mis', lambda r: float(r['num_mis']))]
for y in ['solo', 'share']:
  for sid in SIDS:
    names, est, bs, r2, n, sdy = run(sid, feats, y)
    _, _, _, r2l, _, _ = run(sid, feats, y, label_only=True)
    print(f'== {y} {SH[sid]} n={n} R2={r2:.4f} R2(label only)={r2l:.4f} within-sd(y)={sdy:.4f}')
    for i, nm in enumerate(names):
        print(f'   {nm}: {est[i]:+.4f} [{np.percentile(bs[:,i],2.5):+.4f}, {np.percentile(bs[:,i],97.5):+.4f}]')
