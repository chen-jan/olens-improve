import pickle, math, collections
import numpy as np
D = pickle.load(open('${OLENS_SCRATCH}/olens-bullet-fve/reading/verify_C3_evidence/rows.pkl', 'rb'))
rows, items = D['rows'], D['items']; IX = {x: i for i, x in enumerate(items)}
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']; SH = dict(zip(SIDS, ['Orig', 'Best', 'Comb']))
rng = np.random.default_rng(7); B = 2000
W = np.stack([np.bincount(rng.integers(0, len(items), len(items)), minlength=len(items)) for _ in range(B)]).astype(float)
def agg(rs, f):
    num, den = np.zeros(len(items)), np.zeros(len(items))
    for r in rs: num[IX[r['item']]] += f(r); den[IX[r['item']]] += 1
    return num, den
def dci(a, b):
    e = a[0].sum()/a[1].sum() - b[0].sum()/b[1].sum(); bb = (W@a[0])/(W@a[1]) - (W@b[0])/(W@b[1])
    return f"{a[0].sum()/a[1].sum():.3f} vs {b[0].sum()/b[1].sum():.3f}  diff {e:+.3f} [{np.percentile(bb,2.5):+.3f}, {np.percentile(bb,97.5):+.3f}]"
LABALL = [r for r in rows if r['label'] in ('w', 'c')]
props = {
 'len16 (mean chars)': lambda r: r['len16'],
 'log len16': lambda r: math.log(max(1, r['len16'])),
 'position j (0-based)': lambda r: r['j'],
 'P(position 1)': lambda r: float(r['j'] == 0),
 'P(cjk>=.5)': lambda r: float(r['cjk'] >= .5),
 'P(cjk>0)': lambda r: float(r['cjk'] > 0),
 'P(lead CJK, <20%)': lambda r: float(r['lead_cjk'] and r['cjk'] < .2),
 'P(num_open_mismatch)': lambda r: float(r['num_mis']),
 'P(coef==0)': lambda r: float(r['coef'] == 0),
 'P(dup)': lambda r: float(r['dup']),
 'solo': lambda r: r['solo'],
}
for sid in SIDS:
    print('==', SH[sid])
    w = [r for r in LABALL if r['sid'] == sid and r['label'] == 'w']; c = [r for r in LABALL if r['sid'] == sid and r['label'] == 'c']
    print('   n wrong', len(w), 'n clean', len(c))
    for nm, f in props.items():
        print(f'   {nm}: wrong vs clean {dci(agg(w, f), agg(c, f))}')
    # within-readout pair rates: P(wrong has larger feature than clean sibling), ties 1/2
    ro = collections.defaultdict(list)
    for r in LABALL:
        if r['sid'] == sid and not r['dup'] and r['share'] is not None: ro[r['k']].append(r)
    for nm, f in [('len16', lambda r: r['len16']), ('position', lambda r: r['j'])]:
        num, den = np.zeros(len(items)), np.zeros(len(items))
        for k, bs in ro.items():
            for a in [b for b in bs if b['label'] == 'w']:
                for b in [b for b in bs if b['label'] == 'c']:
                    num[IX[a['item']]] += (1. if f(a) > f(b) else .5 if f(a) == f(b) else 0.); den[IX[a['item']]] += 1
        bb = (W@num)/(W@den)
        print(f'   same-readout P(wrong {nm} > clean {nm}): {num.sum()/den.sum():.3f} [{np.percentile(bb,2.5):.3f}, {np.percentile(bb,97.5):.3f}] n={int(den.sum())}')
