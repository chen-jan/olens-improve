import sys, json, collections
sys.path.insert(0, '${OLENS_SCRATCH}/olens-bullet-fve/tasks/multihop_mt')
import load
rows = list(load.iter_rows())
out = sys.argv[1]
c = collections.Counter(); near = collections.Counter(); distr = collections.Counter(); strict = collections.Counter()
ex = collections.defaultdict(list)
for r in rows:
    for b in r['bullets']:
        if b['near_hit']:
            for role, fs in b['lenient_forms'].items():
                if role != 'target':
                    for f in fs: near[(r['item_id'], role, f)] += 1
            ex['near'].append((r['cell_id'], r['setting'], b['index'], b['text'].strip(), b['lenient_forms']))
        if b['label'] == 'wrong-specific':
            for role, fs in b['distractors_named'].items():
                for f in fs: distr[(r['item_id'], role, f)] += 1
            ex['ws'].append((r['cell_id'], r['setting'], b['index'], b['text'].strip(), b['distractors_named']))
        if b['label'] == 'hit':
            for role, fs in b['strict_forms'].items():
                for f in fs: strict[(r['item_id'], role, f)] += 1
        if b['hedge']:
            ex['hedge'].append((r['cell_id'], r['setting'], b['index'], b['text'].strip(), b['strict_forms'], b['distractors_named']))
        if b['label'] == 'hit' and set(b['strict_roles_in_scored_prefix']) != set(b['strict_roles']):
            ex['outside_prefix'].append((r['cell_id'], r['setting'], b['index'], b['text'].strip(), b['strict_forms']))
        # distractor named alongside lenient hit (not ws because lenient)
        if b['distractor_roles'] and b['lenient_roles'] and not b['strict_roles']:
            ex['lenient_plus_distr'].append((r['cell_id'], r['setting'], b['index'], b['text'].strip(), b['lenient_forms'], b['distractors_named']))
        c['bullets'] += 1
        c['any_distractor'] += bool(b['distractor_roles'])
res = {'near_top': [[*k, v] for k, v in near.most_common(60)], 'n_near_alias_keys': len(near),
       'distr_top': [[*k, v] for k, v in distr.most_common(40)], 'n_distr_keys': len(distr),
       'strict_top': [[*k, v] for k, v in strict.most_common(30)], 'n_strict_keys': len(strict),
       'counts': dict(c), 'examples': {k: v[:40] for k, v in ex.items()}, 'n_examples': {k: len(v) for k, v in ex.items()}}
json.dump(res, open(out, 'w'), indent=1, ensure_ascii=False)
print(json.dumps({k: res[k] for k in ('n_near_alias_keys', 'n_distr_keys', 'n_strict_keys', 'counts', 'n_examples')}))
