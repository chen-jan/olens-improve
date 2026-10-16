"""C2 confound check: is the solo-FVE / next-text-overlap link between readouts or within them? Exploratory."""
import os, math, collections, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'synth_tests.py')).read()
cut = src.index('# ----------------------------------------------------------------------------- T1 no separation')
g = {'__file__': os.path.join(HERE, 'synth_tests.py'), '__name__': 'synth_part'}
exec(compile(src[:cut], 'synth_tests_part', 'exec'), g)
globals().update({k: v for k, v in g.items() if not k.startswith('__')})
import numpy as np
from scipy.stats import spearmanr
res = {}
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid and not math.isnan(r['nxt_ov'])]
    by = collections.defaultdict(list)
    for r in R:
        by[(r['k'], sid)].append(r)
    ro_fve = np.array([readouts[k]['fve'] for k in by])
    ro_ov = np.array([np.mean([b['nxt_ov'] for b in bs]) for bs in by.values()])
    ro_solo = np.array([np.mean([b['solo'] for b in bs]) for bs in by.values()])
    # total vs within decomposition of solo~nxt_ov correlation
    s = np.array([r['solo'] for r in R]); o = np.array([r['nxt_ov'] for r in R])
    sm = np.array([np.mean([b['solo'] for b in by[(r['k'], sid)]]) for r in R])
    om = np.array([np.mean([b['nxt_ov'] for b in by[(r['k'], sid)]]) for r in R])
    res[SHORT[sid]] = {
        'n_readouts': len(by),
        'spearman_readout_fve_vs_mean_nxt_ov': round(float(spearmanr(ro_fve, ro_ov)[0]), 3),
        'pearson_bullet_solo_vs_nxt_ov_total': round(float(np.corrcoef(s, o)[0, 1]), 3),
        'pearson_bullet_solo_vs_nxt_ov_within_readout': round(float(np.corrcoef(s - sm, o - om)[0, 1]), 3),
        'pearson_bullet_solo_vs_nxt_ov_between_readout_means': round(float(np.corrcoef(ro_solo, ro_ov)[0, 1]), 3),
        'by_label_within': {lab: round(float(np.corrcoef((s - sm)[[r['label'] == lab for r in R]],
                                                          (o - om)[[r['label'] == lab for r in R]])[0, 1]), 3)
                            for lab in ('w', 'c')},
    }
print(json.dumps(res, indent=1))
with open(os.path.join(HERE, 'c2_readout_level.json'), 'w') as fh:
    json.dump(res, fh, indent=1)
