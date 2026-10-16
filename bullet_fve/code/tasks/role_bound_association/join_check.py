"""Check that bullet_labels.jsonl and bullet_metrics.jsonl join 1:1 on (cell_id, setting, phrase_id)
and count, per setting and contrast_group, bullets that have metrics. -> data/join_check.json"""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
met = {}
for line in open(HERE / 'bullet_metrics.jsonl'):
    r = json.loads(line)
    for sid, s in r['settings'].items():
        for i, b in enumerate(s['bullets']):
            met[(r['cell_id'], sid, b['phrase_id'])] = (i, b['cache_key'], b['shapley'] is not None)
st = collections.Counter()
seen = set()
for line in open(HERE / 'bullet_labels.jsonl'):
    r = json.loads(line)
    k = (r['cell_id'], r['setting'], r['phrase_id'])
    assert k not in seen
    seen.add(k)
    m = met.get(k)
    if m is None:
        st['label_without_metrics_row'] += 1
        continue
    assert m[0] == r['index'] and m[1] == r['cache_key'], k
    st[f"{r['setting']}|{r['contrast_group']}|metrics={m[2]}"] += 1
st['metrics_rows'] = len(met)
st['label_rows'] = len(seen)
st['metrics_without_label_row'] = len(set(met) - seen)
assert st['label_without_metrics_row'] == 0 and st['metrics_without_label_row'] == 0
for key, n in st.items():
    if '|excluded' not in key and 'metrics=False' in key:
        raise AssertionError(('usable bullet without metrics', key, n))
(HERE / 'data/join_check.json').write_text(json.dumps(dict(sorted(st.items())), indent=1))
print(json.dumps(dict(sorted(st.items())), indent=1))
