"""Skeptic pass for um: extra checks (judge by site / layer, top-of-pool label, consensus) from sk_tables.pkl."""
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

SK = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks/analysis/um/skeptic')
T = pickle.load(open(SK / 'cache/sk_tables.pkl', 'rb'))
pool, sel, items = T['pool'], T['sel'], T['items']
p = pool[pool.solo.notna()].drop_duplicates(['cell_id', 'cache_key']).copy()
out = {}
# judge per cell by site and layer (all settings pooled)
j = sel.drop_duplicates(['cell_id', 'setting']).join(pool[['site', 'layer', 'sub']], on='pidx')
out['judge_gold_by_site'] = j.groupby('site').pick.apply(lambda s: round(float((s == 'gold').mean()), 3)).to_dict()
out['judge_gold_by_layer'] = {int(k): v for k, v in j.groupby('layer').pick.apply(lambda s: round(float((s == 'gold').mean()), 3)).items()}
out['pool_gold_rate_by_site_sub'] = {f'{a}|{b}': round(float(v), 3) for (a, b), v in
                                     p.groupby(['site', 'sub']).grp.apply(lambda s: (s == 'gold').mean()).items()}
# top-of-pool bullet label; cells with both gold and wrong: P(top among gold+wrong is gold) vs share of gold
rows = []
for c, d in p.groupby('cell_id'):
    gw = d[d.grp.isin(['gold', 'wrong'])]
    top = d.loc[d.solo.idxmax()]
    rows.append((c, d.item_id.iloc[0], top.grp, (d.grp == 'gold').any(), (d.grp == 'wrong').any(),
                 gw.loc[gw.solo.idxmax()].grp if len(gw) else None, (gw.grp == 'gold').mean() if len(gw) else np.nan))
R = pd.DataFrame(rows, columns=['cell', 'item', 'top', 'hasg', 'hasw', 'topgw', 'gshare'])
both = R[R.hasg & R.hasw]
out['top_bullet'] = {
    'cells_top_is_wrong': int((R.top == 'wrong').sum()),
    'of_those_pool_has_gold': round(float(R[R.top == 'wrong'].hasg.mean()), 3),
    'cells_top_is_gold': int((R.top == 'gold').sum()),
    'cells_with_both': int(len(both)),
    'both: top of gold+wrong is gold': round(float((both.topgw == 'gold').mean()), 3),
    'both: mean gold share of gold+wrong bullets (chance)': round(float(both.gshare.mean()), 3),
}
# consensus: value most often named by a single-value name bullet vs other values, within cell
q = p[((p.grp == 'gold') & p.gname) | ((p.grp == 'wrong') & p.wname)].copy()
q['val'] = [('GOLD' if g == 'gold' else (w[0] if w and len(w) == 1 else None)) for g, w in zip(q.grp, q.wvals)]
q = q[q.val.notna()]
res = []
for c, d in q.groupby('cell_id'):
    vc = d.val.value_counts()
    if len(vc) < 2 or vc.iloc[0] == vc.iloc[1]:
        continue
    maj = vc.index[0]
    a, b = d[d.val == maj].solo.to_numpy(), d[d.val != maj].solo.to_numpy()
    dd = a[:, None] - b[None, :]
    res.append((c, maj == 'GOLD', ((dd > 0).sum() + 0.5 * (dd == 0).sum()), dd.size))
C = pd.DataFrame(res, columns=['cell', 'gold_maj', 'w', 'n'])
out['consensus'] = {'cells': len(C), 'majority_is_gold_cells': int(C.gold_maj.sum()),
                    'P(majority > minority)': round(float(C.w.sum() / C.n.sum()), 3),
                    'when gold is majority': round(float(C[C.gold_maj].w.sum() / C[C.gold_maj].n.sum()), 3),
                    'when wrong is majority (majority=wrong wins)': round(float(C[~C.gold_maj].w.sum() / C[~C.gold_maj].n.sum()), 3)}
# synthsys stated-locale: share of wrong name bullets naming United States / North America
w = p[(p.grp == 'wrong') & p.wname]
us = w.wvals.map(lambda v: any(x in ('united_states', 'north_america') for x in v))
out['wrong_US_NA_share'] = {'all': round(float(us.mean()), 3),
                            'Continent': round(float(us[w.cls == 'Continent'].mean()), 3)}
# Antarctica share of all pool gold-vs-wrong pairs and wrong surfaces
print(json.dumps(out, indent=1))
json.dump(out, open(SK / 'sk_extra.json', 'w'), indent=1)
