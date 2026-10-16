"""Candidate-level inputs for the readout-level FVE <-> pass analysis (multihop_mt).

For every multihop_mt cell, read the frozen full-grid selector row and keep, for EVERY selection
in it, the minimal identity: method, n, the sample index(es) its atoms come from, its exact NNLS
FVE (fits.exact), text sha256, bullet count, and the Best-of-32 trace (FVE of each of the 32
complete capped samples). Single-sample conditions (capped_n1, best_n_exact-nK, random_complete-nK,
best_n_specificity_*, likelihood selectors) are then candidate readouts whose judged verdicts already
exist under expansion-v1/judgments/<cond>/. READ-ONLY on project data; no judge/API calls.

Usage: python -B extract_candidates.py   (writes tasks/multihop_mt/inputs/multihop_mt_candidates.jsonl)
"""
import collections
import hashlib
import json
import time
from pathlib import Path

FAMILY = 'multihop_mt'
D = '${OLENS_DATA_ROOT}'
SELECTIONS = {
    'development': f'{D}/selections/development-full-grid-v4/merged/selections.jsonl',
    'validation': f'{D}/selections/validation-full-grid-v1/merged/selections.jsonl',
    'test': f'{D}/selections/test-full-grid-v1/merged/selections.jsonl',
}
CACHED_V2 = f'{D}/expansion-v1/selections/cached-v2/{FAMILY}.jsonl'
OUT = Path('${OLENS_SCRATCH}/olens-bullet-fve/tasks/multihop_mt/inputs/multihop_mt_candidates.jsonl')
PREFIX = ('{"cell_id": "' + FAMILY + '|').encode()

t0 = time.time()
# expansion-level texts (what was judged) for every (method, n), keyed by cell
exp_text = collections.defaultdict(dict)
with open(CACHED_V2) as f:
    for line in f:
        r = json.loads(line)
        for s in r['selections']:
            exp_text[r['cell_id']][f"{s['method']}-n{s['n']}"] = hashlib.sha256(s['text'].encode()).hexdigest()
stats = collections.Counter()
seen = set()
with open(OUT, 'w') as out:
    for stage, path in SELECTIONS.items():
        with open(path, 'rb') as f:
            for raw in f:
                if not raw.startswith(PREFIX):
                    continue
                row = json.loads(raw)
                cid = row['cell_id']
                assert cid not in seen
                seen.add(cid)
                sels = []
                trace32 = None
                for s in row['selections']:
                    cond = f"{s['method']}-n{s['n']}"
                    exact = (s.get('fits') or {}).get('exact') or {}
                    samples = sorted({a.get('sample_index') for a in (s.get('atoms') or [])},
                                     key=lambda x: (x is None, x))
                    tsha = hashlib.sha256((s.get('text') or '').encode()).hexdigest()
                    sels.append({'cond': cond, 'method': s['method'], 'n': s['n'], 'samples': samples,
                                 'fve': exact.get('fve'), 'text_sha256': tsha, 'bullet_count': s.get('bullet_count'),
                                 'reason': s.get('reason'),
                                 'expansion_text_equal': exp_text[cid].get(cond) == tsha if cond in exp_text[cid]
                                 else None})
                    stats[f'cond[{cond}]'] += 1
                    if cond == 'best_n_exact-n32':
                        trace32 = [{'sample_id': t['sample_id'], 'sample_index': int(t['sample_id'].rsplit(':', 1)[1]),
                                    'score': t['score']} for t in s['trace']]
                out.write(json.dumps({'cell_id': cid, 'split': stage, 'item_id': row['item_id'], 'layer': row['layer'],
                                      'position': row['position'], 'selections': sels, 'trace32': trace32,
                                      'expansion_conds': sorted(exp_text[cid])}) + '\n')
        print(stage, 'done', round(time.time() - t0, 1), 's', flush=True)
print(len(seen), 'cells')
print(json.dumps(dict(sorted(stats.items())), indent=1))
