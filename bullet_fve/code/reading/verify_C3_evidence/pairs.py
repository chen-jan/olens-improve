import pickle, math, collections, sys
import numpy as np
D = pickle.load(open('${OLENS_SCRATCH}/olens-bullet-fve/reading/verify_C3_evidence/rows.pkl', 'rb'))
rows, items = D['rows'], D['items']; IX = {x: i for i, x in enumerate(items)}
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']; SH = dict(zip(SIDS, ['Orig', 'Best', 'Comb']))
rng = np.random.default_rng(12345); B = 2000
W = np.stack([np.bincount(rng.integers(0, len(items), len(items)), minlength=len(items)) for _ in range(B)]).astype(float)
def ci(num, den):
    est = num.sum() / den.sum(); b = (W @ num) / (W @ den)
    return f"{est:.3f} [{np.percentile(b,2.5):.3f}, {np.percentile(b,97.5):.3f}] n={int(den.sum())}"
EXCL_DUP = '--keepdup' not in sys.argv
LAB = [r for r in rows if r['label'] in ('w', 'c', 'o') and r['share'] is not None and not (EXCL_DUP and r['dup'])]
ro = collections.defaultdict(list)
for r in LAB: ro[(r['k'], r['sid'])].append(r)
def win(a, b): return 1. if a > b else (.5 if a == b else 0.)
def fpr(sid, fa, score='solo', sel=lambda r: True):
    num, den = np.zeros(len(items)), np.zeros(len(items))
    for (k, s), bs in ro.items():
        if s != sid: continue
        bs = [b for b in bs if sel(b)]
        for a in bs:
            for b in bs:
                if a is b: continue
                fa_, fb_ = fa(a), fa(b)
                if fa_ is None or fb_ is None or (isinstance(fa_, float) and math.isnan(fa_)) or (isinstance(fb_, float) and math.isnan(fb_)): continue
                if fa_ > fb_:
                    num[IX[a['item']]] += win(a[score], b[score]); den[IX[a['item']]] += 1
    return ci(num, den)
tests = {
 'longer (len16) scores higher': lambda r: r['len16'],
 'longer scored part (slen16) scores higher': lambda r: r['slen16'],
 'later position scores higher': lambda r: r['j'],
 'noCJK beats >=50% CJK': lambda r: 1. if r['cjk'] == 0 else (0. if r['cjk'] >= .5 else None),
 'noCJK beats lead-CJK (<20%)': lambda r: 1. if r['cjk'] == 0 else (0. if (r['lead_cjk'] and r['cjk'] < .2) else None),
 'no num_open_mismatch scores higher': lambda r: -float(r['num_mis']),
 'no number-not-used-in-reply opener scores higher': lambda r: -float(r['num_unused']),
 'higher prv_ov scores higher': lambda r: r['prv_ov'],
 'higher recap3 (3-gram before & not after) scores higher': lambda r: r['recap3'],
}
print('exclude dup:', EXCL_DUP)
for sid in SIDS:
    print('==', SH[sid])
    for nm, f in tests.items():
        if nm.startswith('later') and sid == SIDS[2]: continue
        print(f'  {nm}: {fpr(sid, f)}')
