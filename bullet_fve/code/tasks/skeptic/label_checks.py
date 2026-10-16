"""Small label-validity counts (no judge calls). Usage: label_checks.py"""
import json, collections
T = '${OLENS_SCRATCH}/olens-bullet-fve/tasks/'
out = {}
# RBA: bullets naming all three parts, by readout pass
c = collections.Counter()
for line in open(T + 'role_bound_association/bullet_labels.jsonl'):
    r = json.loads(line)
    if r['n_components'] == 3:
        c[(r['setting_short'], r['judge']['pass'], r['label_fine'])] += 1
out['rba_all3parts'] = {f'{k[0]}|pass={k[1]}|{k[2]}': v for k, v in sorted(c.items())}
# chain: identical bullet text (same cell) with different primary labels across settings
by = collections.defaultdict(set)
for line in open(T + 'chain_intermediates/bullet_labels.jsonl'):
    r = json.loads(line)
    by[(r['cell_id'], r['cache_key'])].add((r['display'], r['label']))
diff = [k for k, v in by.items() if len({x[1] for x in v}) > 1]
hitdiff = [k for k, v in by.items() if 'hit' in {x[1] for x in v} and len({x[1] for x in v}) > 1]
out['chain_same_vector_same_cell_different_label'] = len(diff)
out['chain_same_vector_same_cell_hit_in_one_setting_not_other'] = len(hitdiff)
out['chain_distinct_vectors_labelled_hit_somewhere'] = sum('hit' in {x[1] for x in v} for v in by.values())
# multihop: same for strict hit (should be 0: label is bullet-intrinsic)
by = collections.defaultdict(set)
for line in open(T + 'multihop_mt/bullet_labels.jsonl'):
    r = json.loads(line)
    by[(r['cell_id'], r['cache_key'])].add(r['label'])
out['multihop_same_vector_different_label'] = sum(len(v) > 1 for v in by.values())
print(json.dumps(out, indent=1))
