"""Reader 1 helper: how much of the window-labelled wrong-value set is (a) a US/American surface (default answer locale)
(b) item um-ss-religiousaffiliation-00 (temple topic word), by setting; selected bullets and pool."""
import json, sys, collections
from pathlib import Path
HERE = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks/analysis/um')
sys.path.insert(0, str(HERE))
import analysis as A
T = A.load_tables()
sel = A.add_derived(T['sel']); sel = sel[sel.solo.notna()]
p = A.pool_frame(T['pool'])
US = {'United States', 'US', 'U.S.', 'USA', 'American', 'Americans', 'America', 'the US', 'U.S'}
out = {}
for name, d in [('selected', sel), ('pool', p)]:
    w = d[d.grpNW == 'wrong']
    is_us = w.surfsW.map(lambda s: any(x in US for x in s))
    res = {'n_wrong_name': int(len(w)), 'us_surface': int(is_us.sum()),
           'relig00': int((w.item_id == 'um-ss-religiousaffiliation-00').sum()),
           'by_class': w.attr_class.value_counts().to_dict(),
           'us_by_class_layer': {f'{k[0]}|L{k[1]}': int(v) for k, v in w[is_us].groupby(['attr_class', 'layer']).size().items()},
           'top_wrong_surfaces': collections.Counter(x for s in w.surfsW for x in s).most_common(25)}
    if name == 'selected':
        res['by_setting'] = {A.SL[s]: {'n': int((w.setting == s).sum()), 'us': int(is_us[w.setting == s].sum())}
                             for s in A.SETTINGS}
    out[name] = res
json.dump(out, open(HERE / 'read1' / 'read1_counts.json', 'w'), indent=1, default=str)
print(json.dumps(out, indent=1, default=str)[:6000])
