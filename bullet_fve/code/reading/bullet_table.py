"""Per-bullet table for the reading sample (imported by build_sample.py).

One row per (cell k, setting, bullet j) for the three scored settings, from page/data/items/*.json.
"""
import glob
import json
import os

DATA = '${OLENS_SCRATCH}/olens-bullet-fve/page/data'
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']


def load_rows():
    rows, cells = [], {}
    for f in sorted(glob.glob(os.path.join(DATA, 'items', '*.json'))):
        with open(f) as fh:
            d = json.load(fh)
        it = d['item']
        for k, c in d['cells'].items():
            labels = {sid: c['settings'][sid]['label'] or 'empty' for sid in SIDS}
            cells[k] = {'k': k, 'item': it['id'], 'source': it['source'], 'L': c['layer'], 'labels': labels,
                        'fve': {sid: c['settings'][sid]['fve'] for sid in SIDS},
                        'bl': {sid: [b['label'] for b in c['settings'][sid]['bullets']] for sid in SIDS}}
            for sid in SIDS:
                s = c['settings'][sid]
                occ_w = [(a, e) for sp in s['spans'] if sp['verified'] and sp['type'] == 'wrong'
                         for a, e in sp['offsets']]
                for j, b in enumerate(s['bullets']):
                    hits = [(a, e) for a, e in occ_w if a < b['end'] and e > b['start']]
                    unscored_only = bool(hits) and all(max(a, b['start']) >= b['scored_end'] for a, e in hits)
                    rows.append({'k': k, 'item': it['id'], 'source': it['source'], 'L': c['layer'], 'setting': sid,
                                 'bullet': j, 'n': len(s['bullets']), 'label': b['label'],
                                 'readout': s['label'] or 'empty', 'fve': s['fve'], 'share': b['shap_share'],
                                 'shap': b['shap'], 'solo': b['solo'], 'drop': b['drop'], 'coef': b['coef'],
                                 'dup': b['dup'], 'truncated': b['truncated'], 'n_wrong_occ': len(hits),
                                 'wrong_unscored_only': unscored_only})
    return rows, cells
