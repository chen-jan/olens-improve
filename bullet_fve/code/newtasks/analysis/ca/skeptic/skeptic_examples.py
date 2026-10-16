"""Print verbatim examples for the skeptic report (reads skeptic/cache/sk_tables.pkl)."""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
sys.path.insert(0, str(NT / 'code'))
import ntcommon as C  # noqa: E402

SL = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
WRONG = ('contrast', 'other_value')
bank = C.load_bank('conjunctive_association')
with open(NT / 'analysis/ca/skeptic/cache/sk_tables.pkl', 'rb') as f:
    T = pickle.load(f)
sel, pool = T['sel'], T['pool']


def key(cid):
    _, it, L, p = cid.split('|')
    return f'{it}.{L}.p{int(p[1:])}'


sel['key'] = sel.cell_id.map(key)
pool['key'] = pool.cell_id.map(key)
p = pool[pool.solo.notna()].drop_duplicates(['cell_id', 'cache_key']).copy()
p['pct'] = p.groupby('cell_id').solo.rank(pct=True)


def show_readout(k, setting):
    d = sel[(sel.key == k) & (sel.setting == setting)]
    it = bank[d.item_id.iloc[0]]
    print(f'\n### {k} {SL[setting]}  gold="{it["gold_label"]}" contrast="{it["contrast_label"]}" site={d.site.iloc[0]} joint={d.joint.iloc[0]:.3f} judge={d.judge_pick.iloc[0]}')
    for _, r in d.iterrows():
        print(f'  [{r.idx}] llm={r.llm_raw} lex2={r.lex2} solo={r.solo:.4f} share={r.share:.3f} tok={r.stok} :: {r.scored_text!r}')


for k, s in (('q04_a.L52.p73', 'best_n_exact-n32'), ('q01_c.L60.p88', None), ('q10_b.L36.p92', 'capped_n1-n1'),
             ('q09_f.L52.p84', 'best_n_exact-n32'), ('q08_c.L60.p67', None), ('q09_i.L60.p67', None),
             ('q03_h.L44.p78', 'pooled_greedy_swap-n32'), ('q01_c.L44.p92', 'best_n_exact-n32')):
    if s is None:
        for s2 in SL:
            if ((sel.key == k) & (sel.setting == s2)).any():
                show_readout(k, s2)
    else:
        show_readout(k, s)

# ---- pool: clean items, specific-word groups, in-frame wrong value beats in-frame gold in the same cell
print('\n\n======== POOL same-frame examples (groups q02, q03, q09): top gold vs top wrong in one cell')
for g in ('q02', 'q09', 'q03'):
    d = p[(p.group == g)]
    cells = []
    for cid, c in d.groupby('cell_id'):
        gg = c[c.lex2 == 'gold']
        ww = c[c.lex2 == 'contrast']
        if len(gg) >= 2 and len(ww) >= 2:
            cells.append((cid, len(gg), len(ww), ww.solo.max() - gg.solo.max()))
    cells.sort(key=lambda x: -(x[1] + x[2]))
    for cid, ng, nw, diff in cells[:3]:
        c = d[d.cell_id == cid]
        it = bank[c.item_id.iloc[0]]
        print(f'\n## {key(cid)} n_gold={ng} n_contrast={nw} gold="{it["gold_label"]}" contrast="{it["contrast_label"]}" site={c.site.iloc[0]}')
        for lab in ('gold', 'contrast'):
            for _, r in c[c.lex2 == lab].sort_values('solo', ascending=False).head(3).iterrows():
                print(f'   {lab:8s} s{r.sample_index}.{r.pos} solo={r.solo:.4f} pct={r.pct:.2f} :: {r.text[:220]!r}')

# ---- two-direction: q10 and q07, one cell per direction with both labels
print('\n\n======== TWO-DIRECTION examples')
for g in ('q10', 'q07'):
    d = p[p.group == g]
    for gl in sorted({bank[i]['gold_label'] for i in d.item_id.unique()})[:10]:
        pass
    done = set()
    for cid, c in d.groupby('cell_id'):
        it = bank[c.item_id.iloc[0]]
        gv = str(it['cell'].get(it['contrast_axis']))
        if gv in done:
            continue
        gg = c[c.lex2 == 'gold']
        ww = c[c.lex2 == 'contrast']
        if len(gg) >= 3 and len(ww) >= 3:
            done.add(gv)
            auc = np.mean([(a > b) + 0.5 * (a == b) for a in gg.solo for b in ww.solo])
            print(f'\n## {key(cid)} gold="{it["gold_label"]}" contrast="{it["contrast_label"]}" n_gold={len(gg)} n_contrast={len(ww)} AUROC(gold>contrast)={auc:.2f}')
            for lab, x in (('gold', gg), ('contrast', ww)):
                for _, r in x.sort_values('solo', ascending=False).head(2).iterrows():
                    print(f'   {lab:8s} s{r.sample_index}.{r.pos} solo={r.solo:.4f} pct={r.pct:.2f} :: {r.text[:200]!r}')
        if len(done) == 2:
            break

# ---- selection: pool has a high-percentile gold bullet, Best of 32 has no gold
print('\n\n======== SELECTION misses (Best of 32 readout has no lex2/LLM gold; pool has a gold bullet in the top 10% of the cell)')
b = sel[sel.setting == 'best_n_exact-n32']
nog = b.groupby('cell_id').apply(lambda x: not ((x.lex2 == 'gold') | (x.llm_raw == 'gold')).any())
nog = set(nog[nog].index)
cand = p[(p.lex2 == 'gold') & (p.pct >= 0.9) & p.cell_id.isin(nog) & (p.layer >= 44)]
cand = cand[~cand.text.str.match(r'^\s*(\d+[.:)]|\*\*|#)')]
shown = 0
for cid, c in cand.groupby('cell_id'):
    if shown >= 3:
        break
    if c.group.iloc[0] in ('q01', 'q04'):
        continue
    r = c.sort_values('solo', ascending=False).iloc[0]
    it = bank[r.item_id]
    print(f'\n## {key(cid)} gold="{it["gold_label"]}"  pool gold s{r.sample_index}.{r.pos} solo={r.solo:.4f} pct={r.pct:.2f} :: {r.text[:220]!r}')
    show_readout(key(cid), 'best_n_exact-n32')
    shown += 1

# ---- name echo / instruction echo within one readout
print('\n\n======== INSTRUCTION-ECHO bullets that out-score gold siblings (Original/Best, same readout)')
sc = sel[sel.solo.notna()]
shown = 0
for (cid, s), d in sc[sc.layer >= 44].groupby(['cell_id', 'setting']):
    if s == 'pooled_greedy_swap-n32':
        continue
    ins = d[d.instr & (d.lex2 == 'none') & (d.llm_raw == 'none')]
    gd = d[(d.lex2 == 'gold') & (d.llm_raw == 'gold')]
    if len(ins) and len(gd) and ins.solo.max() > gd.solo.max() + 0.1:
        show_readout(key(cid), s)
        shown += 1
    if shown >= 3:
        break
