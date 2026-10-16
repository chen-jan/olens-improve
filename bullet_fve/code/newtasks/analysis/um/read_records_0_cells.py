"""Reader 0 (um): within-cell context for read_sample cases 0-11 (no API, no GPU). Prints JSON."""
import json
import sys
from pathlib import Path

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
sys.path.insert(0, str(NT / 'analysis/um'))
import analysis as A  # noqa: E402

rs = json.loads((NT / 'analysis/um/read_sample.json').read_text())['cases'][0:12]
T = A.load_tables()
p = A.pool_frame(T['pool'])
p['pct_cell'] = p.groupby('cell_id').solo.rank(pct=True)
p['pct_layer'] = p.groupby('layer').solo.rank(pct=True)
cm = p.groupby('cell_id').solo.agg(['mean', 'median', 'max'])
cm['cell_mean_pct_in_layer'] = cm['mean'].groupby(p.groupby('cell_id').layer.first()).rank(pct=True)
out = []
for c in rs:
    g = p[p.cell_id == c['cell_id']].sort_values('solo', ascending=False)
    rec = {'i': c['reading_index'], 'key': c['case_key'], 'setting': c['setting'], 'type': c['case_type'],
           'cell_solo_mean': round(float(cm.loc[c['cell_id'], 'mean']), 4),
           'cell_solo_max': round(float(cm.loc[c['cell_id'], 'max']), 4),
           'cell_mean_pct_among_cells_same_layer': round(float(cm.loc[c['cell_id'], 'cell_mean_pct_in_layer']), 3),
           'pool_n': int(len(g)), 'pool_labels_nameW': {k: int(v) for k, v in g.grpNW.value_counts().items()},
           'bullets_pct_in_cell': []}
    for b in c['bullets']:
        m = g[(g.solo - b['solo_fve']).abs() < 6e-5]
        m2 = m[m.text.str[:40] == b['text'].strip()[:40]] if len(m) > 1 else m
        rec['bullets_pct_in_cell'].append({'idx': b['index'], 'solo': b['solo_fve'],
                                           'pct_in_cell': round(float(m2.pct_cell.iloc[0]), 3) if len(m2) else None})
    rec['pool_top5'] = [f"{s:.3f} [{lb}] {w[:120]!r}" for s, lb, w in g.head(5)[['solo', 'grpNW', 'window']].values]
    rec['pool_bottom3'] = [f"{s:.4f} [{lb}] {w[:120]!r}" for s, lb, w in g.tail(3)[['solo', 'grpNW', 'window']].values]
    for lb in ('gold', 'wrong'):
        h = g[g.grpNW == lb]
        rec[f'pool_{lb}_name_mean_pct_in_cell'] = round(float(h.pct_cell.mean()), 3) if len(h) else None
        rec[f'pool_{lb}_name_examples'] = [f"{s:.3f} {w[:110]!r}" for s, w in h.head(3)[['solo', 'window']].values]
    out.append(rec)
print(json.dumps(out, indent=1, ensure_ascii=False))
