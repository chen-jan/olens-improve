"""Print every bullet of the given cells (all 3 settings): label, solo, share, coef, text. Usage: show_cells.py FAMILY CELL_ID..."""
import json, sys, subprocess
fam = sys.argv[1]; cells = sys.argv[2:]
T = '${OLENS_SCRATCH}/olens-bullet-fve/tasks/'
pat = '\n'.join(f'"cell_id": "{c}"' for c in cells)
def grep(path):
    out = subprocess.run(['grep', '-F', '-f', '-', path], input=pat, capture_output=True, text=True).stdout
    return [json.loads(l) for l in out.splitlines() if l.strip()]
M = {}
for r in grep(T + fam + '/bullet_metrics.jsonl'):
    for s, st in r['settings'].items():
        M[(r['cell_id'], s)] = (st.get('joint_fve_saved'), {b['phrase_id']: b for b in st['bullets']})
rows = grep(T + fam + '/bullet_labels.jsonl')
rows.sort(key=lambda r: (r['cell_id'], r['setting'], r.get('index', r.get('bullet'))))
last = None
for r in rows:
    key = (r['cell_id'], r['setting'])
    fve, mb = M[key]
    if key != last:
        extra = r.get('readout_pass', r.get('readout_kind', (r.get('judge') or {}).get('readout_class')))
        print(f"\n== {r['cell_id']}  {r['setting']}  joint_fve={fve:.3f}  readout={extra}")
        last = key
    b = mb[r['phrase_id']]
    lab = r.get('label_fine') or r['label']
    if fam == 'chain_intermediates':
        lab += f" val={r.get('label_value')} stated={r.get('label_stated')} top={r.get('judge_values')}"
    if fam == 'multihop_mt':
        lab += f" near={r.get('near_hit')} tgt={r.get('target_hit_strict')}"
    print(f"  [{r.get('index', r.get('bullet'))}] {lab:28s} solo={b['solo_fve']:.4f} share={(b['shapley_share'] or 0):.4f} coef={b['coefficient']:.2f} | {r['text'][:170]!r}")
