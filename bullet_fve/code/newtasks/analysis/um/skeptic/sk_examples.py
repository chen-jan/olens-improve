"""Skeptic pass for um: verify the readers' quoted examples against my tables and pull new verbatim examples.
Prints to stdout (logs/examples.log). Solo = pool solo FVE; pct = within-cell percentile (dedup pool)."""
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SK = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks/analysis/um/skeptic')
T = pickle.load(open(SK / 'cache/sk_tables.pkl', 'rb'))
pool, sel, items = T['pool'], T['sel'], T['items']
p = pool[pool.solo.notna()].drop_duplicates(['cell_id', 'cache_key']).copy()
p['pct'] = p.groupby('cell_id').solo.rank(pct=True)
p['key'] = p.cell_id.map(lambda c: f"{c.split('|')[1]}.{c.split('|')[2]}.p{int(c.split('|')[3][1:])}")
SN = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}


def lab(r):
    g = r.grp
    if g == 'gold':
        g += '(name' if r.gname else '(weak'
        g += ',novelV' if r.gnovV else ',echoV'
        g += ')'
    return g


def show(r, pre='  '):
    t = r.text.strip().replace('\n', ' ')
    print(f"{pre}{r.key} s{r.sample_index}.{r.pos} [{lab(r)}] solo {r.solo:.4f} pct {r.pct:.3f} tok {r.stok}: {t[:170]!r}")


def cell(key):
    it, L, pp = key.rsplit('.', 2)
    return f"user_modeling|{it}|{L}|p{int(pp[1:]):05d}"


def find(key, pat, n=6):
    d = p[(p.cell_id == cell(key)) & p.text.str.contains(pat, case=False, regex=True)].sort_values('solo', ascending=False)
    for r in d.head(n).itertuples():
        show(r)


def readout(key, setting):
    c = cell(key)
    s = sel[(sel.cell_id == c) & (sel.setting == setting)]
    print(f'  {key} {SN[setting]}: judge {s.pick.iloc[0]} / {s.basis.iloc[0]}')
    for r in s.itertuples():
        q = pool.iloc[r.pidx]
        t = q.text.strip().replace('\n', ' ')
        print(f"    [{r.idx}] [{q.grp}{'' if q.grp != 'gold' else (',novelV' if q.gnovV else ',echoV')}] solo {r.solo_m:.4f} share {r.share:.3f}: {t[:170]!r}")


def summary(key):
    d = p[p.cell_id == cell(key)]
    print(f"  {key}: pool {len(d)}; gold {int((d.grp == 'gold').sum())} wrong {int((d.grp == 'wrong').sum())} "
          f"frame {int((d.grp == 'frame').sum())}; mean solo {d.solo.mean():.3f}; site {d.site.iloc[0]}")


print('=== 1. reader examples: same frame, different value')
find('um-ss-maritalstatus-01.L60.p41', r'since you are (divorced|single)')
find('um-ss-diets-09.L44.p37', r'since you specified')
find('um-ss-employmentstatus-10.L52.p43', r"when you('re| are| have)", 8)
find('um-sd-occupation-00.L60.p53', r'retired (fisherman|sailor)')
print('=== 2. surface form, both gold')
find('um-sd-country-05.L44.p45', r'ukrain|乌克兰')
find('um-ss-maritalstatus-01.L60.p41', r'staycation')
print('=== 3. same item, two layers (locksmith)')
for k in ('um-sd-occupation-11.L60.p55', 'um-sd-occupation-11.L44.p55'):
    summary(k)
    readout(k, 'capped_n1-n1')
print('=== 4. wrong-value labels that are not the user attribute')
readout('um-ss-maritalstatus-13.L52.p49', 'pooled_greedy_swap-n32')
readout('um-ss-maritalstatus-13.L52.p49', 'best_n_exact-n32')
find('um-ss-religiousaffiliation-00.L60.p41', r'buddhis')
find('um-ss-continent-01.L20.p35', r'united states')
summary('um-ss-continent-01.L20.p35')
print('=== 5. gold in a non-user slot')
find('um-sd-country-11.L60.p51', r'new zealand|china')
readout('um-ss-continent-09.L20.p43', 'capped_n1-n1')

print('=== 6. Antarctica vs Arctic (largest A3 contributor)')
an = p[p.group == 'Continent:antarctica']
cp = []
for c, d in an.groupby('cell_id'):
    g, w = d[d.grp == 'gold'], d[d.grp == 'wrong']
    if len(g) and len(w):
        cp.append((c, len(g), len(w), g.solo.mean(), w.solo.mean(), (g.solo.values[:, None] > w.solo.values[None, :]).mean()))
cp = pd.DataFrame(cp, columns=['cell', 'ng', 'nw', 'g', 'w', 'rate']).sort_values('ng', ascending=False)
print(cp.head(8).to_string())
wsurf = an[an.grp == 'wrong'].text.str.extract(r'(?i)(arctic circle|arctic|north pole|北极)')[0].str.lower().value_counts()
print('wrong surfaces', wsurf.head(6).to_dict())
for c in cp.cell.head(3):
    d = p[p.cell_id == c]
    print('  cell', c, 'gold mean', round(d[d.grp == 'gold'].solo.mean(), 3), 'wrong mean', round(d[d.grp == 'wrong'].solo.mean(), 3))
    for r in d[d.grp == 'gold'].sort_values('solo', ascending=False).head(2).itertuples():
        show(r, '    G ')
    for r in d[d.grp == 'wrong'].sort_values('solo', ascending=False).head(2).itertuples():
        show(r, '    W ')
    for r in d[d.grp == 'wrong'].sort_values('solo').head(1).itertuples():
        show(r, '    W-low ')

print('=== 7. echo vs novel gold, same masked opening, same cell (selfdescribe)')
q = p[(p.grp == 'gold') & (p['sub'] == 'selfdescribe') & p.mopen4.notna()]
q = q.assign(nov=q.gnovV.astype(bool))
cnt = 0
for (c, m), d in q.groupby(['cell_id', 'mopen4']):
    if d.nov.any() and (~d.nov).any() and len(d) <= 8:
        e, n = d[~d.nov].iloc[0], d[d.nov].iloc[0]
        if abs(e.solo - n.solo) < 0.03 and min(e.solo, n.solo) > 0.3:
            show(e, '  echo  ')
            show(n, '  novel ')
            cnt += 1
            if cnt >= 4:
                break

print('=== 8. same masked frame, gold vs wrong, high FVE, from different groups')
seen = set()
G = p[(p.grp == 'gold') & p.mopen4.notna()]
W = p[(p.grp == 'wrong') & p.mopen4.notna()]
m = G.merge(W, on=['cell_id', 'mopen4'], suffixes=('_g', '_w'))
m = m[(m.solo_w >= m.solo_g) & (m.solo_g > 0.35)]
m['grpname'] = m.group_g
for r in m.sort_values('solo_w', ascending=False).itertuples():
    if r.grpname in seen:
        continue
    seen.add(r.grpname)
    print(f"  {r.key_g} {r.grpname} frame '{r.mopen4}': gold s{r.sample_index_g}.{r.pos_g} {r.solo_g:.4f} {r.text_g.strip()[:110]!r} | "
          f"wrong s{r.sample_index_w}.{r.pos_w} {r.solo_w:.4f} {r.text_w.strip()[:110]!r}")
    if len(seen) >= 8:
        break
print('=== 9. same masked frame, gold beats wrong by >= 0.1 (the other direction)')
m2 = G.merge(W, on=['cell_id', 'mopen4'], suffixes=('_g', '_w'))
m2 = m2[(m2.solo_g - m2.solo_w >= 0.1)]
seen = set()
for r in m2.sort_values('solo_g', ascending=False).itertuples():
    if r.group_g in seen:
        continue
    seen.add(r.group_g)
    print(f"  {r.key_g} {r.group_g} frame '{r.mopen4}': gold s{r.sample_index_g}.{r.pos_g} {r.solo_g:.4f} {r.text_g.strip()[:110]!r} | "
          f"wrong s{r.sample_index_w}.{r.pos_w} {r.solo_w:.4f} {r.text_w.strip()[:110]!r}")
    if len(seen) >= 6:
        break
print('=== 10. synthsys wrong vs frame (wrong-frame -0.007): default-locale wrong bullets')
ss = p[(p['sub'] == 'synthsys')]
for g in ('Continent:europe', 'Diets:halal', 'MaritalStatus:divorced'):
    d = ss[ss.group == g]
    print(' ', g, 'wrong', len(d[d.grp == 'wrong']), 'frame', len(d[d.grp == 'frame']),
          'within-cell dm wrong', round(float((d.solo - d.groupby('cell_id').solo.transform('mean'))[d.grp == 'wrong'].mean()), 4),
          'frame', round(float((d.solo - d.groupby('cell_id').solo.transform('mean'))[d.grp == 'frame'].mean()), 4))
    for r in d[d.grp == 'wrong'].sort_values('solo', ascending=False).head(2).itertuples():
        show(r, '    W ')
print('=== 11. Combine 32 adds echo gold: synthsys cells where Combine has gold-echo and Original has no gold, judge verbatim echo')
ss_sel = sel.join(pool[['grpF', 'gnovVF', 'sub', 'text']], on='pidx')
hasg = ss_sel.assign(g=ss_sel.grpF == 'gold').groupby(['cell_id', 'setting']).g.any().unstack()
pk = ss_sel.drop_duplicates(['cell_id', 'setting']).set_index(['cell_id', 'setting']).pick.unstack()
cand = hasg[(hasg['pooled_greedy_swap-n32']) & (~hasg['capped_n1-n1']) & (~hasg['best_n_exact-n32'])].index
cand = [c for c in cand if items[c.split('|')[1]]['sub'] == 'synthsys' and pk.loc[c, 'pooled_greedy_swap-n32'] == 'gold'
        and pk.loc[c, 'capped_n1-n1'] != 'gold']
print('  n cells', len(cand))
for c in cand[:2]:
    k = f"{c.split('|')[1]}.{c.split('|')[2]}.p{int(c.split('|')[3][1:])}"
    readout(k, 'capped_n1-n1')
    readout(k, 'pooled_greedy_swap-n32')
