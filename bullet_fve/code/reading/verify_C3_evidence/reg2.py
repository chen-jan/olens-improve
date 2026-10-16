import pickle, math, collections
import numpy as np
D = pickle.load(open('${OLENS_SCRATCH}/olens-bullet-fve/reading/verify_C3_evidence/rows.pkl', 'rb'))
rows, items = D['rows'], D['items']; IX = {x: i for i, x in enumerate(items)}
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']; SH = dict(zip(SIDS, ['Orig', 'Best', 'Comb']))
rng = np.random.default_rng(5); B = 1000
W = np.stack([np.bincount(rng.integers(0, len(items), len(items)), minlength=len(items)) for _ in range(B)]).astype(float)
LAB = [r for r in rows if r['label'] in ('w', 'c', 'o') and r['share'] is not None and not r['dup'] and not math.isnan(r['nxt_ov']) and not math.isnan(r['prv_ov'])]
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid]
    names = ['is_w', 'is_o', 'log_len', 'lead_cjk(<.2)', 'heavy_cjk(>=.5)', 'mid_cjk', 'nxt_ov', 'prv_ov', 'num_mis'] + (['pos2', 'pos3', 'pos4'] if sid != SIDS[2] else [])
    def v(r):
        x = [float(r['label'] == 'w'), float(r['label'] == 'o'), math.log(max(1, r['len16'])), float(r['lead_cjk'] and r['cjk'] < .2),
             float(r['cjk'] >= .5), float(r['cjk'] > 0 and r['cjk'] < .5 and not (r['lead_cjk'] and r['cjk'] < .2)), r['nxt_ov'], r['prv_ov'], float(r['num_mis'])]
        if sid != SIDS[2]: x += [float(r['j'] == 1), float(r['j'] == 2), float(r['j'] == 3)]
        return x
    X = np.array([v(r) for r in R]); Y = np.array([r['solo'] for r in R]); g = collections.defaultdict(list)
    for i, r in enumerate(R): g[r['k']].append(i)
    for ii in g.values(): X[ii] -= X[ii].mean(0); Y[ii] -= Y[ii].mean()
    sd = X.std(0); cont = {'log_len', 'nxt_ov', 'prv_ov'}
    X = X / np.array([sd[i] if n in cont else 1. for i, n in enumerate(names)])
    ix = np.array([IX[r['item']] for r in R])
    fit = lambda w: np.linalg.solve(X.T @ (X * w[ix][:, None]), X.T @ (Y * w[ix]))
    est = fit(np.ones(len(items))); bs = np.array([fit(w) for w in W])
    print('==', SH[sid], 'within-sd solo', round(Y.std(), 4))
    for i, n in enumerate(names):
        print(f'   {n}: {est[i]:+.4f} [{np.percentile(bs[:,i],2.5):+.4f}, {np.percentile(bs[:,i],97.5):+.4f}]')
    # lead-CJK bullets: mean len vs no-CJK
    lc = [r for r in R if r['lead_cjk'] and r['cjk'] < .2]; nc = [r for r in R if r['cjk'] == 0]
    print('   mean len lead-CJK', round(np.mean([r['len16'] for r in lc]), 1), 'no-CJK', round(np.mean([r['len16'] for r in nc]), 1),
          '| mean j lead', round(np.mean([r['j'] for r in lc]), 2), 'no-CJK', round(np.mean([r['j'] for r in nc]), 2))
