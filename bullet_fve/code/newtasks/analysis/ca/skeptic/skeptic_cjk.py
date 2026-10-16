"""Small descriptive checks: CJK x position x instruction-echo (pool, within-cell percentile); A3 pair share by group."""
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
T = pickle.load(open(NT / 'analysis/ca/skeptic/cache/sk_tables.pkl', 'rb'))
p = T['pool']
p = p[p.solo.notna()].drop_duplicates(['cell_id', 'cache_key']).copy()
p['pct'] = p.groupby('cell_id').solo.rank(pct=True)
print('CJK rate by pos'); print(p.groupby('pos').cjk.mean().round(3).to_string())
print('mean pct by cjk x pos'); print(p.groupby(['cjk', 'pos']).pct.mean().unstack().round(3).to_string())
print('mean pct by cjk x instr'); print(p.groupby(['cjk', 'instr']).pct.mean().unstack().round(3).to_string())
print('n by cjk x instr'); print(p.groupby(['cjk', 'instr']).size().unstack().to_string())
print('mean pct by cjk x layer'); print(p.groupby(['layer', 'cjk']).pct.mean().unstack().round(3).to_string())
print('mean stok by cjk'); print(p.groupby('cjk').stok.mean().round(2).to_string())
# within-cell: cjk vs non-cjk among bullets with same pos & both non-instr, length within 20%
g = (p.lex2 == 'gold'); w = p.lex2.isin(['contrast', 'other_value'])
both = set(p[g].cell_id) & set(p[w].cell_id)
d = p[p.cell_id.isin(both) & (g | w)]
print('A3 pairs by group:')
pr = {}
for cid, c in d.groupby('cell_id'):
    a = c[c.lex2 == 'gold']; b = c[c.lex2.isin(['contrast', 'other_value'])]
    pr[c.group.iloc[0]] = pr.get(c.group.iloc[0], 0) + len(a) * len(b)
tot = sum(pr.values()); print({k: (v, round(v / tot, 3)) for k, v in sorted(pr.items())}, tot)
print('cells by group with both', d.groupby('group').cell_id.nunique().to_dict())
# name echo rate by label
print('name echo by lex2'); print(p.groupby('lex2').name.mean().round(3).to_string())
