"""CPU-stage checks for one family after select3 merge + metrics3 + lexicon labels (read-only on inputs).

Checks: every cell has the three settings; metrics joint FVE recomputed vs saved (<= 1e-6);
sum of per-bullet Shapley == joint FVE per readout; bullets per readout == phrase_ids.
Reports: mean joint FVE per setting (overall and per layer) with bootstrap CIs over related-item groups
(group_id = bank cluster for CA, 10 clusters; attr_class:attr for UM, 31 groups) and over items, paired setting differences, label counts.
Writes data/metrics/{fam}_stage_checks.json.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

B = 2000


def boot(values_by_group: dict, rng, reps=B):
    """Mean over all units; CI by resampling groups (each group contributes its units)."""
    groups = sorted(values_by_group)
    sums = np.array([np.sum(values_by_group[g]) for g in groups])
    cnts = np.array([len(values_by_group[g]) for g in groups])
    mean = sums.sum() / cnts.sum()
    idx = rng.integers(0, len(groups), size=(reps, len(groups)))
    bs = sums[idx].sum(1) / cnts[idx].sum(1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {'mean': float(mean), 'ci95': [float(lo), float(hi)], 'n': int(cnts.sum()), 'groups': len(groups)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--family', default='ca')
    args = ap.parse_args()
    fam = args.family
    rng = np.random.default_rng(C.SEED)
    three = list(C.read_jsonl(C.DATA / f'select/{fam}_three_settings.jsonl'))
    if fam == 'um':
        # UM related-item groups = items sharing the gold value (attr_class:attr), 31 groups over 100 items
        # (select3 writes group_id = item_id for um). CA keeps its bank cluster.
        bank = C.load_bank('user_modeling')
        for r in three:
            r['group_id'] = f"{bank[r['item_id']]['attr_class']}:{bank[r['item_id']]['attr']}"
    man_cells = set()
    stages = {'ca': ('ca',), 'um': ('umA', 'umB')}[fam]
    for st in stages:
        p = C.DATA / f'manifests/gen_{st}.json'
        if p.exists() and (C.DATA / 'gen' / st / 'pool.json').exists():
            man_cells |= {c['cell_id'] for c in json.loads(p.read_text())['cells']}
    out = {'family': fam, 'cells': len(three), 'manifest_cells': len(man_cells)}
    ids = [r['cell_id'] for r in three]
    out['cells_match_manifest'] = set(ids) == man_cells and len(ids) == len(set(ids))
    out['cells_with_all_three_settings'] = sum(set(r['settings']) == set(C.SETTINGS) for r in three)
    out['unscored'] = {sid: [r['cell_id'] for r in three if r['settings'][sid]['fve'] is None] for sid in C.SETTINGS}
    out['bullet_count_hist'] = {sid: dict(sorted(collections.Counter(r['settings'][sid]['bullet_count']
                                                                       for r in three).items())) for sid in C.SETTINGS}
    out['token_count_mean'] = {sid: float(np.mean([r['settings'][sid]['token_count'] for r in three]))
                               for sid in C.SETTINGS}
    meta = {r['cell_id']: r for r in three}

    # metrics3 per layer
    worst = collections.defaultdict(float)
    nread = collections.Counter()
    metric_cells = set()
    for L in C.LAYERS:
        for rec in C.read_jsonl(C.DATA / f'metrics/{fam}_bullet_metrics.L{L}.jsonl'):
            metric_cells.add(rec['cell_id'])
            for sid in C.SETTINGS:
                s = rec['settings'][sid]
                if s.get('unscored'):
                    nread['unscored'] += 1
                    continue
                nread[sid] += 1
                saved = meta[rec['cell_id']]['settings'][sid]['fve']
                worst['abs_recomputed_minus_saved'] = max(worst['abs_recomputed_minus_saved'],
                                                          abs(s['joint_fve_recomputed'] - s['joint_fve_saved']))
                worst['abs_saved_in_metrics_minus_select'] = max(worst['abs_saved_in_metrics_minus_select'],
                                                                 abs(s['joint_fve_saved'] - saved))
                sh = sum(b['shapley'] for b in s['bullets'])
                worst['abs_sum_shapley_minus_joint'] = max(worst['abs_sum_shapley_minus_joint'],
                                                           abs(sh - s['joint_fve_recomputed']))
                if len(s['bullets']) != len(meta[rec['cell_id']]['settings'][sid]['phrase_ids']):
                    nread['bullet_count_mismatch'] += 1
                if [b['phrase_id'] for b in s['bullets']] != meta[rec['cell_id']]['settings'][sid]['phrase_ids']:
                    nread['phrase_order_mismatch'] += 1
    out['metrics_cells'] = len(metric_cells)
    out['metrics_cover_all_cells'] = metric_cells == set(ids)
    out['metrics_readouts'] = dict(nread)
    out['max_abs'] = dict(worst)
    out['pass'] = {'three_settings_every_cell': out['cells_with_all_three_settings'] == len(three),
                   'recomputed_vs_saved_le_1e-6': worst['abs_recomputed_minus_saved'] <= 1e-6
                   and worst['abs_saved_in_metrics_minus_select'] <= 1e-6,
                   'shapley_sum_eq_joint_le_1e-9': worst['abs_sum_shapley_minus_joint'] <= 1e-9,
                   'bullets_match_phrase_ids': nread['bullet_count_mismatch'] == 0 and nread['phrase_order_mismatch'] == 0}

    # mean joint FVE per setting (scored readouts), CIs over clusters and over items; per layer
    def fve_table(rows):
        res = {}
        for sid in C.SETTINGS:
            by_g, by_i = collections.defaultdict(list), collections.defaultdict(list)
            for r in rows:
                v = r['settings'][sid]['fve']
                if v is not None:
                    by_g[r['group_id']].append(v)
                    by_i[r['item_id']].append(v)
            res[C.SETTING_LABEL[sid]] = {'by_group': boot(by_g, rng), 'by_item_ci95': boot(by_i, rng)['ci95']}
        both = [r for r in rows if all(r['settings'][s]['fve'] is not None for s in C.SETTINGS)]
        for a, b in (('best_n_exact-n32', 'capped_n1-n1'), ('pooled_greedy_swap-n32', 'capped_n1-n1'),
                     ('pooled_greedy_swap-n32', 'best_n_exact-n32')):
            by_g, by_i = collections.defaultdict(list), collections.defaultdict(list)
            for r in both:
                d = r['settings'][a]['fve'] - r['settings'][b]['fve']
                by_g[r['group_id']].append(d)
                by_i[r['item_id']].append(d)
            res[f'{C.SETTING_LABEL[a]} - {C.SETTING_LABEL[b]}'] = {'by_group': boot(by_g, rng),
                                                                  'by_item_ci95': boot(by_i, rng)['ci95']}
        return res
    out['mean_joint_fve'] = {'all': fve_table(three)}
    for L in C.LAYERS:
        out['mean_joint_fve'][f'L{L}'] = fve_table([r for r in three if r['layer'] == L])

    # label counts (lexicon)
    lab = C.DATA / (f'labels/{fam}_lex_label_summary.json' if fam == 'ca' else 'labels/um_label_summary.json')
    if lab.exists():
        s = json.loads(lab.read_text())
        out['lexicon_label_counts'] = s['by_source']
        if fam == 'ca':
            out['lexicon_readouts_with_label'] = s['readouts_with_label']
            out['lexicon_pool_gold_missed'] = s['pool_gold_missed']
        else:
            out['lexicon_sha256'] = s.get('lexicon_sha256')
            # readouts with >= 1 bullet of each label group, per setting (selected bullets only)
            per = collections.defaultdict(lambda: collections.defaultdict(set))
            for o in C.read_jsonl(C.DATA / 'labels/um_bullet_labels.jsonl'):
                if o['source'] == 'pool':
                    continue
                g = 'gold' if o['label'].startswith('gold') else o['label']
                per[o['source']][g].add(o['cell_id'])
            out['lexicon_readouts_with_label'] = {C.SETTING_LABEL[sid]: {g: len(v) for g, v in sorted(per[sid].items())}
                                                  for sid in C.SETTINGS}
    C.atomic_json(C.DATA / f'metrics/{fam}_stage_checks.json', out)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
