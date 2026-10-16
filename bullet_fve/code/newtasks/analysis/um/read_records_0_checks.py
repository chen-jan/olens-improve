"""Reader 0 (um, cases 0-11): descriptive pool checks suggested by the reading. No API, no GPU.

Run from newtasks/ with PYTHONPATH=code (one mit_quicktest job via code/qt.sh):
  python -B analysis/um/read_records_0_checks.py > analysis/um/logs/read_records_0_checks.json
Pool = analysis.py pool_frame (deduplicated by AR vector, solo FVE). pct = within-cell percentile of solo FVE.
All numbers are descriptive (no CI) and use the WINDOW labels unless stated.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
sys.path.insert(0, str(NT / 'analysis/um'))
import analysis as A  # noqa: E402

L = A.L
out = {}
T = A.load_tables()
p = A.pool_frame(T['pool'])
p['pct'] = p.groupby('cell_id').solo.rank(pct=True)
out['n_pool'] = int(len(p))


def r(x, nd=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


# --- 1. digit list-marker openings ("2. **The ...", "2: Local ...", "1. Major ...")
LIST = re.compile(r'^\s*\d{1,2}\s*[.:)]')
p['list_open'] = p.window.str.match(LIST)
p['bold_open'] = p.window.str.match(r'^\s*(\*\*|#+\s)')
p['tokbin'] = np.select([p.stok < 16, p.stok < 24, p.stok < 31], ['<16', '16-23', '24-30'], '31-32')
c1 = {'share_list_open': r(p.list_open.mean()), 'n_list_open': int(p.list_open.sum()),
      'items_with_list_open': int(p[p.list_open].item_id.nunique()),
      'mean_pct': {'list_open': r(p[p.list_open].pct.mean()), 'bold_open': r(p[p.bold_open].pct.mean()),
                   'other': r(p[~p.list_open & ~p.bold_open].pct.mean())},
      'mean_pct_by_tokbin': {}, 'mean_pct_by_label': {}, 'list_open_rate_in_gold_name_by_pct_quarter': {}}
for b, g in p.groupby('tokbin'):
    c1['mean_pct_by_tokbin'][b] = {'list_open': r(g[g.list_open].pct.mean()), 'n_list': int(g.list_open.sum()),
                                   'other': r(g[~g.list_open].pct.mean())}
for lb, g in p.groupby('grpNW'):
    c1['mean_pct_by_label'][lb] = {'list_open': r(g[g.list_open].pct.mean()), 'n_list': int(g.list_open.sum()),
                                   'other': r(g[~g.list_open].pct.mean())}
gn = p[p.grpNW == 'gold']
for lo, hi in ((0, .25), (.25, .5), (.5, .75), (.75, 1.01)):
    g = gn[(gn.pct > lo) & (gn.pct <= hi)] if lo > 0 else gn[gn.pct <= hi]
    c1['list_open_rate_in_gold_name_by_pct_quarter'][f'{lo}-{min(hi, 1)}'] = {'rate': r(g.list_open.mean()),
                                                                              'n': int(len(g))}
# solo of list-open gold-name vs other gold-name bullets in the SAME cell (paired within cell)
cell_rates = []
for cid, g in gn.groupby('cell_id'):
    a, b = g[g.list_open].solo.to_numpy(), g[~g.list_open].solo.to_numpy()
    if len(a) and len(b):
        cell_rates.append(((a[:, None] > b[None, :]).sum() + .5 * (a[:, None] == b[None, :]).sum(), len(a) * len(b)))
if cell_rates:
    num, den = map(np.array, zip(*cell_rates))
    c1['gold_name_list_open_beats_gold_name_other_same_cell'] = {'pooled': r(num.sum() / den.sum()),
                                                                  'cells': len(cell_rates), 'pairs': int(den.sum())}
out['1_list_marker_openings'] = c1

# --- 2. infobox template in selfdescribe ("Here is a ... Wikipedia ... infobox for a fictional X")
TPL = re.compile(r"^\s*(here is|here's|here’s|below is)\b.{0,90}\b(infobox|wikipedia)", re.I)
sd = p[p.subfamily == 'selfdescribe'].copy()
sd['tpl'] = sd.window.str.match(TPL)
c2 = {'share_template_selfdescribe': r(sd.tpl.mean()), 'n_template': int(sd.tpl.sum()),
      'mean_pct_template_vs_other': {'template': r(sd[sd.tpl].pct.mean()), 'other': r(sd[~sd.tpl].pct.mean())},
      'template_mean_pct_by_label': {}}
for lb, g in sd[sd.tpl].groupby('grpNW'):
    c2['template_mean_pct_by_label'][lb] = {'mean_pct': r(g.pct.mean()), 'n': int(len(g))}
# within cell, among template bullets only: P(gold-name solo > wrong-name solo) and P(gold-name > none)
for B in ('wrong', 'none'):
    rates = []
    for cid, g in sd[sd.tpl].groupby('cell_id'):
        a, b = g[g.grpNW == 'gold'].solo.to_numpy(), g[g.grpNW == B].solo.to_numpy()
        if len(a) and len(b):
            rates.append(((a[:, None] > b[None, :]).sum() + .5 * (a[:, None] == b[None, :]).sum(), len(a) * len(b),
                          g.item_id.iloc[0]))
    if rates:
        num = np.array([x[0] for x in rates]); den = np.array([x[1] for x in rates])
        c2[f'template_only_P(gold_name > {B})_same_cell'] = {'pooled': r(num.sum() / den.sum()), 'cells': len(rates),
                                                             'items': len({x[2] for x in rates}),
                                                             'pairs': int(den.sum())}
out['2_infobox_template'] = c2

# --- 3. locksmith name-level gold carried only by lock-picking forms (an activity, not the occupation name)
LP = {'lockpicking', 'lock picking', 'lock-picking', 'lockpick', 'lockpicks', 'lock pick'}
lk = p[(p.attr_class == 'Occupation') & p.item_id.isin(
    [k for k, v in A.C.load_bank(A.FAM).items() if v.get('attr') == 'locksmith'])]
lkg = lk[lk.grpNW == 'gold']
only_lp = lkg[lkg.surfsW.map(lambda s: len(s) > 0 and all(x.lower().replace('-', ' ') in {y.replace('-', ' ') for y in LP}
                                                          or x.lower() in {'lock', 'locks', 'keys', 'locked out'}
                                                          for x in s) and any(x.lower().replace('-', ' ') in
                                                          {y.replace('-', ' ') for y in LP} for x in s))]
out['3_locksmith_lockpick_only_name_gold'] = {
    'locksmith_items': int(lk.item_id.nunique()), 'gold_name_bullets': int(len(lkg)),
    'name_gold_only_via_lockpick_forms': int(len(only_lp)), 'share': r(len(only_lp) / max(len(lkg), 1)),
    'their_mean_pct': r(only_lp.pct.mean()), 'other_gold_name_mean_pct': r(lkg.drop(only_lp.index).pct.mean()),
    'examples': [f"{A.case_key(c)} s{s}: {w[:110]!r}" for c, s, w in
                 only_lp.sample(min(5, len(only_lp)), random_state=0)[['cell_id', 'sample_index', 'window']].values]}

# --- 4. occupation words the lexicon misses (labelled none / frame), Occupation items
MISS = {'plumb': r'\bplumb(er|ers|ing)\b', 'skateboard': r'\bskateboard(er|ers|ing)?\b',
        'lighthouse keeper': r'\blighthouse keepers?\b', 'seafarer': r'\bseafarers?\b',
        'maritime worker': r'\bmaritime workers?\b'}
oc = p[p.attr_class == 'Occupation']
c4 = {}
for k, rx in MISS.items():
    g = oc[oc.window.str.contains(rx, case=False, regex=True)]
    c4[k] = {'n': int(len(g)), 'by_label': {a: int(b) for a, b in g.grpW.value_counts().items()},
             'items': int(g.item_id.nunique())}
out['4_occupation_lexicon_misses'] = c4

# --- 5. Continent: gold via a country name -- is the country the user's place or a destination / org location?
co = p[(p.attr_class == 'Continent') & (p.grpNW == 'gold') & (p.gkW == 'coarse')]
DEST = re.compile(r"\b(to|into|towards|for delivery to|ship(?:ping)? to|send(?:ing)? to)\s+(the\s+)?$", re.I)
ORG = re.compile(r"^[\s\-–]*(based|-based)", re.I)


def ctx_kind(w, surfs):
    for s in surfs:
        m = re.search(re.escape(s), w)
        if not m:
            continue
        if DEST.search(w[:m.start()]):
            return 'destination ("to X")'
        if ORG.match(w[m.end():]):
            return 'X-based organisation'
    return 'other'


co = co.assign(kind=[ctx_kind(w, s) for w, s in zip(co.window, co.surfsW)])
out['5_continent_country_gold_context'] = {
    'n': int(len(co)), 'by_kind': {a: int(b) for a, b in co.kind.value_counts().items()},
    'mean_pct_by_kind': {a: r(g.pct.mean()) for a, g in co.groupby('kind')},
    'examples_destination': [f"{A.case_key(c)}: {w[:110]!r}" for c, w in
                             co[co.kind.str.startswith('dest')].head(4)[['cell_id', 'window']].values]}

# --- 6. synthsys "novel" gold that ALSO contains an echoed (stated) gold form, e.g. "you are in Europe ... UK-based"
bank = A.C.load_bank(A.FAM)
ctx = A.contexts(bank)
ss = p[(p.subfamily == 'synthsys') & (p.grpW == 'gold') & p.g_novelW]
both = 0
by_cls = {}
for (item_id, w), g in ss.groupby(['item_id', 'window']):
    c = ctx[item_id]
    res = L.label_bullet(w, c['cls'], c['gold'], c['distractors'], c['prompt'])
    gh = res['gold_hits']
    for h in gh:
        h['in_prompt'] = A.echo_surface(h['surface'], c['pf'])
    any_echo = any(h['in_prompt'] or h['match'] == 'exact' for h in gh)
    both += len(g) if any_echo else 0
    k = c['cls']
    by_cls.setdefault(k, [0, 0])
    by_cls[k][0] += len(g) if any_echo else 0
    by_cls[k][1] += len(g)
out['6_synthsys_novel_gold_with_echo_too'] = {
    'synthsys_gold_novel_window_bullets': int(len(ss)), 'also_contain_an_echoed_gold_form': int(both),
    'share': r(both / max(len(ss), 1)),
    'by_attr_class': {k: {'also_echo': v[0], 'n': v[1], 'share': r(v[0] / max(v[1], 1))} for k, v in by_cls.items()}}

print(json.dumps(out, indent=1, ensure_ascii=False))
