"""Reader 1 helper: dump the full pools (all labels) of read_sample.json cases 12-23 -> read1/read1_dump.json."""
import json, pickle, sys
from pathlib import Path
HERE = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks/analysis/um')
sys.path.insert(0, str(HERE))
import analysis as A
S = json.load(open(HERE / 'read_sample.json'))
cases = S['cases'][12:24]
cells = {c['cell_id'] for c in cases}
T = A.load_tables()
p = A.pool_frame(T['pool'])
print('pool cols', list(p.columns))
p = p[p.cell_id.isin(cells)]
out = {}
for cid, g in p.groupby('cell_id'):
    g = g.sort_values('solo', ascending=False)
    rows = []
    for _, r in g.iterrows():
        rows.append({'s': int(r.sample_index), 'pos': int(r.pos), 'grpW': r.grpW, 'grpNW': r.grpNW,
                     'subW': r.get('subW'), 'echo': bool(r.g_echoW) if r.g_echoW == r.g_echoW else None,
                     'solo': round(float(r.solo), 4), 'stok': int(r.stok), 'surf': list(r.surfsW),
                     'text': r.text[:220]})
    out[cid] = {'n': len(rows), 'mean_solo': round(float(g.solo.mean()), 4),
                'mean_by_label': {k: [round(float(v.mean()), 4), int(len(v))] for k, v in g.groupby('grpW').solo},
                'rows': rows}
json.dump(out, open(HERE / 'read1' / 'read1_dump.json', 'w'), ensure_ascii=False, indent=0, default=str)
print('cells', len(out))
