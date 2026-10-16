"""Validate bullet_labels.jsonl, join it with bullet_metrics.jsonl, and write a flat per-bullet table.

Checks: coverage (every bullet of every readout labelled, counts == extract), join (same
phrase_id / cache_key order as the metrics file), judge reproduction from bullet evidence (per unit,
per cell), evidence located for every non-miss bullet. Counts ambiguous / edge cases per setting
and writes a stratified verbatim reading sample.

Writes: bullet_table.jsonl (one row per bullet: labels + evidence + metrics),
        logs/labels_validation.json, logs/label_reading_sample.txt
Usage: python -B validate_labels.py   (light; run in a CPU allocation)
"""
import collections
import json
import random
from pathlib import Path

TASK = Path('${OLENS_SCRATCH}/olens-bullet-fve/tasks/multihop_mt')
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
LABELS = ('hit', 'wrong-specific', 'miss')
METRIC_KEYS = ('coefficient', 'solo_fve', 'loo_drop', 'shapley', 'shapley_share', 'dup')

summ = json.load(open(TASK / 'inputs/multihop_mt_extract_summary.json'))
EXPECTED_BULLETS = {sid: summ['stats'][f'atoms[{sid}]'] for sid in SETTINGS}

labels = collections.defaultdict(list)
for line in open(TASK / 'bullet_labels.jsonl'):
    r = json.loads(line)
    labels[(r['cell_id'], r['setting'])].append(r)
metrics = {}
for line in open(TASK / 'bullet_metrics.jsonl'):
    r = json.loads(line)
    for sid, s in r['settings'].items():
        metrics[(r['cell_id'], sid)] = s

C = collections.Counter()
by = collections.defaultdict(collections.Counter)      # setting -> counter
ex = collections.defaultdict(list)
assert set(labels) == set(metrics), (len(labels), len(metrics))
table = []
for key in sorted(labels, key=lambda k: (k[0], SETTINGS.index(k[1]))):
    cid, sid = key
    bl = sorted(labels[key], key=lambda r: r['index'])
    m = metrics[key]
    assert [b['index'] for b in bl] == list(range(len(bl)))
    assert [b['phrase_id'] for b in bl] == [x['phrase_id'] for x in m['bullets']], key
    assert [b['cache_key'] for b in bl] == [x['cache_key'] for x in m['bullets']], key
    assert all(b['readout_fve_saved'] == m['joint_fve_saved'] for b in bl)
    c = by[sid]
    c['readouts'] += 1
    # judge reproduction from the bullets' own evidence
    req = bl[0]['required_roles']
    uh = bl[0]['readout_unit_hits']
    for role, judge_hit in uh.items():
        union = any(role in b['strict_roles'] for b in bl) if role != 'target' else any(b['target_hit_strict'] for b in bl)
        C['unit_union_' + ('ok' if union == judge_hit else 'MISMATCH')] += 1
    cell_pass = all(any(r in b['strict_roles'] for b in bl) for r in req)
    C['cell_pass_' + ('ok' if cell_pass == bl[0]['readout_pass'] else 'MISMATCH')] += 1
    c['readout_pass'] += cell_pass
    nh = sum(b['label'] == 'hit' for b in bl)
    c[f'readouts_with_{min(nh, 2)}{"+" if nh >= 2 else ""}_hit_bullets'] += 1
    if cell_pass and not any(b['label'] == 'hit' and b['strict_roles_in_scored_prefix'] for b in bl):
        c['passing_readouts_hit_invisible_to_all_vectors'] += 1
        ex['pass_invisible'].append((cid, sid, None))
    if cell_pass and len(req) == 2:
        one = any(set(req) <= set(b['strict_roles']) for b in bl)
        c['3hop_pass_both_bridges_in_one_bullet' if one else '3hop_pass_bridges_split_across_bullets'] += 1
    if not cell_pass and any(b['label'] == 'hit' for b in bl):
        c['failed_readouts_with_a_hit_bullet(3hop_partial)'] += 1
    for b, mb in zip(bl, m['bullets']):
        c['bullets'] += 1
        c[f'label={b["label"]}'] += 1
        c[f'label_lenient={b["label_lenient"]}'] += 1
        lab = b['label']
        if lab == 'miss':
            c['miss_in_passing_readout' if b['readout_pass'] else 'miss_in_failed_readout'] += 1
        if lab != 'miss' and not b['evidence_primary']:
            C['non_miss_without_evidence'] += 1
        if any(e['quote'] is None for e in b['evidence']):
            C['evidence_quote_unlocated'] += 1
        for e in b['evidence']:
            if e['quote'] is not None:
                assert b['text'][e['span'][0]:e['span'][1]] == e['quote']
        if b['near_hit']:
            c['near_hit(lenient_only)'] += 1
            ex['near_hit'].append((cid, sid, b['index']))
        if b['hedge']:
            c['hedge(gold+distractor_same_role)'] += 1
            ex['hedge'].append((cid, sid, b['index']))
        if lab == 'hit' and not b['strict_roles_in_scored_prefix']:
            c['hit_outside_scored_prefix'] += 1
            ex['hit_outside_prefix'].append((cid, sid, b['index']))
        if lab == 'hit' and all(' ' not in e['form'] and '-' not in e['form'] for e in b['evidence_primary']):
            # judge-faithful, but credited through a one-word authored form ('Simula', 'Tugela', 'Xuanzang')
            c['hit_via_one_word_strict_form_only'] += 1
            ex['hit_one_word'].append((cid, sid, b['index']))
        if lab == 'hit' and len(b['strict_roles']) > 1:
            c['hit_two_bridges_one_bullet'] += 1
        if lab == 'hit' and set(b['distractor_roles']) - set(b['strict_roles']):
            c['hit_plus_distractor_other_role'] += 1
            ex['hit_plus_distractor_other_role'].append((cid, sid, b['index']))
        if b['distractor_roles'] and b['lenient_roles'] and not b['strict_roles']:
            c['lenient_plus_distractor(miss,not_ws)'] += 1
            ex['lenient_plus_distractor'].append((cid, sid, b['index']))
        if lab == 'wrong-specific' and (b['target_hit_strict'] or b['target_hit_lenient']):
            c['wrong_specific_with_target'] += 1
        if b['target_hit_strict']:
            c[f'target_hit_strict[{lab}]'] += 1
        if b['gold_cut_at_end']:
            c[f'gold_cut_at_end[{lab}]'] += 1
            ex[f'gold_cut_at_end[{lab}]'].append((cid, sid, b['index']))
        if b['truncated']:
            c[f'truncated_gt32[{lab}]'] += 1
        if mb['dup']:
            c[f'dup_vector[{lab}]'] += 1
        if mb['coefficient'] == 0.0:
            c[f'coef_zero[{lab}]'] += 1
        if lab in ('hit', 'wrong-specific'):
            ex[lab].append((cid, sid, b['index']))
        elif b['readout_pass']:
            ex['miss_in_pass'].append((cid, sid, b['index']))
        else:
            ex['miss_in_fail'].append((cid, sid, b['index']))
        row = dict(b)
        row.update({k: mb[k] for k in METRIC_KEYS})
        row['joint_fve_recomputed'] = m['joint_fve_recomputed']
        table.append(row)

with open(TASK / 'bullet_table.jsonl.tmp', 'w') as out:
    for r in table:
        out.write(json.dumps(r, ensure_ascii=False) + '\n')
(TASK / 'bullet_table.jsonl.tmp').replace(TASK / 'bullet_table.jsonl')

# items / groups with >= 1 hit bullet, and how concentrated the hits are
items_hit = collections.defaultdict(collections.Counter)
groups_hit = collections.defaultdict(set)
for r in table:
    if r['label'] == 'hit':
        items_hit[r['setting']][r['item_id']] += 1
        groups_hit[r['setting']].add(r['group_id'])
ws_items = collections.defaultdict(collections.Counter)
for r in table:
    if r['label'] == 'wrong-specific':
        ws_items[r['setting']][r['item_id']] += 1

# descriptive preview only (unadjusted; hits cluster by item/layer, see MAP.md section 8)
preview = {}
for sid in SETTINGS:
    rows = [r for r in table if r['setting'] == sid]
    d = {}
    for lab in LABELS:
        rs = [r for r in rows if r['label'] == lab]
        sh = [r['shapley_share'] for r in rs if r['shapley_share'] is not None]
        d[lab] = {'n': len(rs), 'mean_shapley_share': sum(sh) / len(sh) if sh else None,
                  'mean_solo_fve': sum(r['solo_fve'] for r in rs) / len(rs) if rs else None,
                  'mean_loo_drop': sum(r['loo_drop'] for r in rs) / len(rs) if rs else None}
    # within readout: readouts with >=1 hit and >=1 non-hit bullet
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r['cell_id']].append(r)
    diffs, wins, chance, n = [], 0, 0.0, 0
    for cid, rs in groups.items():
        h = [r['shapley_share'] for r in rs if r['label'] == 'hit' and r['shapley_share'] is not None]
        o = [r['shapley_share'] for r in rs if r['label'] != 'hit' and r['shapley_share'] is not None]
        if h and o:
            n += 1
            diffs.append(sum(h) / len(h) - sum(o) / len(o))
            wins += max(h) > max(o)
            chance += len(h) / (len(h) + len(o))
    d['within_readout_mixed'] = {'readouts': n, 'mean_share_hit_minus_nonhit': sum(diffs) / n if n else None,
                                 'frac_top_share_is_hit': wins / n if n else None,
                                 'chance_top_share_is_hit': chance / n if n else None}
    preview[sid] = d

rng = random.Random(0)
lookup = {(r['cell_id'], r['setting'], r['index']): r for r in table}
lines = []


def show(tag, keys, k):
    keys = list(keys)
    pick = keys if len(keys) <= k else rng.sample(keys, k)
    lines.append(f'##### {tag}: showing {len(pick)} of {len(keys)}')
    for cid, sid, i in pick:
        if i is None:
            rs = [lookup[(cid, sid, j)] for j in range(8) if (cid, sid, j) in lookup]
            lines.append(f'--- {cid} [{SHORT[sid]}] readout pass={rs[0]["readout_pass"]} gold={rs[0]["gold"]}')
            for r in rs:
                lines.append(f'   [{r["index"]}] {r["label"]} in_prefix={r["strict_roles_in_scored_prefix"]} '
                             f'{json.dumps(r["text"].strip(), ensure_ascii=False)}')
            continue
        r = lookup[(cid, sid, i)]
        evs = [(e['kind'], e['role'], e['form'], e['quote']) for e in r['evidence']]
        lines.append(f'--- {cid} [{SHORT[sid]}] bullet [{i}] label={r["label"]} lenient={r["label_lenient"]} '
                     f'readout_pass={r["readout_pass"]} gold={r["gold"]} share={r["shapley_share"]} '
                     f'trunc={r["truncated"]} cut={[(c["role"], c["cut"]) for c in r["gold_cut_at_end"]]}')
        lines.append(f'    TEXT {json.dumps(r["text"], ensure_ascii=False)}')
        lines.append(f'    EVIDENCE {json.dumps(evs, ensure_ascii=False)}')


for tag, k in (('hit', 12), ('wrong-specific', 12), ('miss_in_pass', 8), ('miss_in_fail', 8), ('near_hit', 10),
               ('hedge', 20), ('hit_outside_prefix', 20), ('hit_plus_distractor_other_role', 20),
               ('lenient_plus_distractor', 20), ('gold_cut_at_end[miss]', 12), ('gold_cut_at_end[hit]', 8),
               ('pass_invisible', 10), ('hit_one_word', 10)):
    show(tag, ex.get(tag, []), k)
(TASK / 'logs/label_reading_sample.txt').write_text('\n'.join(lines) + '\n')

report = {
    'checks': {
        'all_readouts_joined': len(labels) == len(metrics) == 3300,
        'bullets_match_extract': all(by[s]['bullets'] == EXPECTED_BULLETS[s] for s in SETTINGS),
        'unit_union_reproduces_judge': C['unit_union_MISMATCH'] == 0,
        'cell_pass_reproduces_judge': C['cell_pass_MISMATCH'] == 0,
        'every_non_miss_has_located_evidence': C['non_miss_without_evidence'] == 0 and C['evidence_quote_unlocated'] == 0,
    },
    'global': dict(C),
    'by_setting': {SHORT[s]: dict(sorted(by[s].items())) for s in SETTINGS},
    'items_with_hit_bullet': {SHORT[s]: len(items_hit[s]) for s in SETTINGS},
    'groups_with_hit_bullet': {SHORT[s]: len(groups_hit[s]) for s in SETTINGS},
    'top_hit_items': {SHORT[s]: items_hit[s].most_common(8) for s in SETTINGS},
    'top_wrong_specific_items': {SHORT[s]: ws_items[s].most_common(8) for s in SETTINGS},
    'preview_unadjusted_metric_means_by_label': preview,
    'n_examples': {k: len(v) for k, v in ex.items()},
}
report['all_checks_pass'] = all(report['checks'].values())
(TASK / 'logs/labels_validation.json').write_text(json.dumps(report, indent=1, ensure_ascii=False))
print(json.dumps(report, indent=1, ensure_ascii=False))
assert report['all_checks_pass'], report['checks']
