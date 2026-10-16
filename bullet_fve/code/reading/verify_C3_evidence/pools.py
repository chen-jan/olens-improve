import pickle, math, collections
import numpy as np
D = pickle.load(open('${OLENS_SCRATCH}/olens-bullet-fve/reading/verify_C3_evidence/rows.pkl', 'rb'))
rows = D['rows']
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']; SH = dict(zip(SIDS, ['Orig', 'Best', 'Comb']))
ok = [r for r in rows if r['share'] is not None and not r['dup']]
# within-readout shortest flag
ro = collections.defaultdict(list)
for r in ok: ro[(r['k'], r['sid'])].append(r)
for bs in ro.values():
    mn = min(b['len16'] for b in bs); mx_solo = max(b['solo'] for b in bs)
    for b in bs:
        b['shortest'] = b['len16'] == mn and len(bs) > 1
        b['short_rel'] = b['len16'] <= 0.6 * np.median([x['len16'] for x in bs])
for sid in SIDS:
    R = [r for r in ok if r['sid'] == sid]
    W = [r for r in R if r['label'] == 'w']; C = [r for r in R if r['label'] == 'c']; CH = [r for r in C if r['ro_label'] == 'hallucinated']
    qw = np.quantile([r['share'] for r in W], .2); qc = np.quantile([r['share'] for r in CH], .2)
    Bp = [r for r in W if r['share'] <= qw]; Cp = [r for r in CH if r['share'] <= qc]
    Cother = [r for r in CH if r['share'] > qc]; Wother = [r for r in W if r['share'] > qw]
    def explained(r):
        return r['coef'] == 0 or r['short_rel'] or r['cjk'] >= .5 or r['num_mis'] or (sid != SIDS[2] and r['j'] == 0)
    def explained_noearly(r):
        return r['coef'] == 0 or r['short_rel'] or r['cjk'] >= .5 or r['num_mis']
    print(f'== {SH[sid]}: B pool {len(Bp)}, C pool {len(Cp)}, rest-wrong {len(Wother)}, rest-clean-in-halluc {len(Cother)}')
    for nm, f in [('coef0', lambda r: r['coef'] == 0), ('shortest in readout', lambda r: r['shortest']),
                  ('len<=0.6*median', lambda r: r['short_rel']), ('cjk>=.5', lambda r: r['cjk'] >= .5),
                  ('lead CJK <.2', lambda r: r['lead_cjk'] and r['cjk'] < .2), ('num_mis', lambda r: r['num_mis']),
                  ('position 1', lambda r: r['j'] == 0), ('ANY(coef0|short|cjk>=.5|num_mis|pos1)', explained),
                  ('ANY w/o pos1', explained_noearly)]:
        p = lambda S: np.mean([bool(f(r)) for r in S])
        print(f'   {nm:40s} Cpool {p(Cp):.3f}  Bpool {p(Bp):.3f} | other clean-in-halluc {p(Cother):.3f}  other wrong {p(Wother):.3f}')
