"""Red-team C1, part 3: length-matched pair rates by layer and source (pooled settings); C vs D reader errors."""
import json, math, os
import numpy as np
HERE_RT = os.path.dirname(os.path.abspath(__file__))
SYN = os.path.join(os.path.dirname(HERE_RT), 'synth_tests.py')
src = open(SYN).read().splitlines()
ns = {'__file__': SYN, '__name__': 'synth_loader'}
exec(compile('\n'.join(src[14:42]) + '\n' + '\n'.join(src[279:527]), SYN, 'exec'), ns)
LAB, by_ro, readouts, ratio_ci, per_item, win, SHORT, SIDS = (ns[x] for x in ['LAB', 'by_ro', 'readouts', 'ratio_ci', 'per_item', 'win', 'SHORT', 'SIDS'])
OB = ['capped_n1-n1', 'best_n_exact-n32']
SC = {s: ('solo_pa' if s in OB else 'solo') for s in SIDS}
for r in LAB:
    r['log_slen'] = math.log(max(1, r['scored_len']))
ok = lambda w, c: abs(w['log_slen'] - c['log_slen']) < math.log(1.2)
def ppr(ro_sel, sids=SIDS):
    acc = []
    for (k, sid), bs in by_ro.items():
        if sid not in sids or not ro_sel(readouts[(k, sid)]):
            continue
        for w in [b for b in bs if b['label'] == 'w']:
            for c in [b for b in bs if b['label'] == 'c']:
                if ok(w, c):
                    acc.append((w['ix'], win(c[SC[sid]], w[SC[sid]]), 1.0))
    return ratio_ci(*per_item(acc))
out = {'by_layer_pooled': {L: ppr(lambda ro, L=L: ro['L'] == L) for L in (20, 36, 44, 52, 60)},
       'by_source_pooled': {s: ppr(lambda ro, s=s: ro['source'] == s) for s in ('dailydialog', 'lmsys')},
       'by_layer_x_setting': {f'{SHORT[s]} L{L}': ppr(lambda ro, L=L: ro['L'] == L, [s]) for s in SIDS for L in (20, 36, 44, 52, 60)}}
from math import comb
def fisher_two_sided(a, n1, b, n2):
    K = a + b; N = n1 + n2
    p = lambda x: comb(n1, x) * comb(n2, K - x) / comb(N, K)
    p0 = p(a)
    return sum(p(x) for x in range(max(0, K - n2), min(K, n1) + 1) if p(x) <= p0 + 1e-12)
out['C_vs_D_reader_errors_7of36_vs_1of36_fisher_p'] = fisher_two_sided(7, 36, 1, 36)
out['A_vs_B_45of60_each_diff_95pct_halfwidth_normal'] = 1.96 * math.sqrt(2 * .75 * .25 / 60)
json.dump(out, open(os.path.join(HERE_RT, 'confounds3.json'), 'w'), indent=1)
for k, v in out.items():
    if isinstance(v, dict):
        for kk, x in v.items(): print(k, kk, x)
    else: print(k, v)
