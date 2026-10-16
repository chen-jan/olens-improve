"""Does within-cell gold-vs-wrong AUROC follow which value the cell's pool names more often? (lex2 labels)"""
import pickle, sys
from pathlib import Path
import numpy as np
import pandas as pd
NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
sys.path.insert(0, str(NT / 'code'))
import ntcommon as C
bank = C.load_bank('conjunctive_association')
ITEMS = sorted(bank); I_OF = {k: i for i, k in enumerate(ITEMS)}
GROUPS = sorted({it['cluster'] for it in bank.values()})
G_OF = np.array([GROUPS.index(bank[k]['cluster']) for k in ITEMS])
rng = np.random.default_rng(11); B = 2000
WI = rng.multinomial(100, np.full(100, .01), size=B).astype(float)
WG = rng.multinomial(10, np.full(10, .1), size=B).astype(float)[:, G_OF]
T = pickle.load(open(NT / 'analysis/ca/skeptic/cache/sk_tables.pkl', 'rb'))
p = T['pool']; p = p[p.solo.notna()].drop_duplicates(['cell_id', 'cache_key'])
rows = []
for cid, c in p.groupby('cell_id'):
    a = c[c.lex2 == 'gold'].solo.to_numpy(); b = c[c.lex2.isin(['contrast', 'other_value'])].solo.to_numpy()
    if not len(a) or not len(b):
        continue
    d = a[:, None] - b[None, :]
    rows.append((cid, c.item_id.iloc[0], c.group.iloc[0], len(a), len(b), ((d > 0).sum() + .5 * (d == 0).sum()), d.size))
R = pd.DataFrame(rows, columns=['cell', 'item', 'group', 'ng', 'nw', 'w', 'p'])
R['m'] = R.ng / (R.ng + R.nw)
R['auc'] = R.w / R.p
R['clean'] = [i[:3] in ('q02','q03','q05','q06','q09','q10') or i in ('q01_a','q01_b','q01_c','q01_d') for i in R['item']]
print('cells', len(R), 'cells where wrong-value bullets outnumber gold:', int((R.m < .5).sum()), 'of', len(R))
def boot(sub, col='auc'):
    N = np.zeros(100); D = np.zeros(100)
    np.add.at(N, [I_OF[i] for i in sub['item']], sub[col]); np.add.at(D, [I_OF[i] for i in sub['item']], 1)
    est = N.sum() / D.sum()
    with np.errstate(invalid='ignore', divide='ignore'):
        ri = (WI @ N) / (WI @ D); rg = (WG @ N) / (WG @ D)
    q = lambda x: [round(float(v), 3) for v in np.nanpercentile(x, [2.5, 97.5])]
    return round(float(est), 3), q(ri), q(rg), len(sub), sub.group.nunique()
for name, sub in (('all', R), ('clean', R[R.clean])):
    print('==', name)
    for lo, hi in ((0, .25), (.25, .5), (.5, .75), (.75, 1.01)):
        s = sub[(sub.m >= lo) & (sub.m < hi)]
        if len(s):
            print(f'  gold share of value-naming bullets in [{lo},{hi}): mean per-cell AUROC', boot(s))
    # minority/majority framing: P(majority-value bullet beats minority-value bullet) per cell
    sub = sub.assign(maj=np.where(sub.m >= .5, sub.auc, 1 - sub.auc))
    s2 = sub[sub.m != .5]
    print('  majority value beats minority value (mean per-cell):', boot(s2, 'maj'))
    print('  spearman(m, auc) =', round(float(sub[['m', 'auc']].corr(method='spearman').iloc[0, 1]), 3))
