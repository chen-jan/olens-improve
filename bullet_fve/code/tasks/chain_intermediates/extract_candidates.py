"""Chained intermediates: candidate-level (whole-sample) readouts for the readout-level FVE analysis.

READ-ONLY on project data; writes only candidates.jsonl / candidates_summary.json in this folder.
Streams the three frozen full-grid selector files (the same ones load.py extract reads) and keeps, for every
chain cell, each whole-sample selection (capped_n1-n1, best_n_exact-nK, random_complete-nK, raw_n1-n1,
best_n_released80-nK) with its source sample index (from phrase_ids), exact-fit FVE, text sha256 and bullet count,
plus the per-sample joint-FVE trace of best_n_exact-n32 (scores of all 32 capped samples).

These are needed to put the judge verdicts of the other judged whole-sample conditions
(expansion-v1/judgments/<condition>/chain_intermediates) on a sample index and an FVE, so that the readout-level
AUROC can be computed across candidates of the same cell. No judge/API calls.

Run (srun, mit_quicktest; ~20 s):
  env -u SLURM_JOB_ID srun --partition=mit_quicktest --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=16G \
    --time=00:15:00 --chdir=${OLENS_SCRATCH}/olens-bullet-fve /usr/bin/env \
    PYTHONPATH=${OLENS_REPO_ROOT}/src \
    ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B tasks/chain_intermediates/extract_candidates.py
"""
import collections
import hashlib
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = Path('${OLENS_DATA_ROOT}')
SELECTIONS = {
    'development': D / 'selections/development-full-grid-v4/merged/selections.jsonl',
    'validation': D / 'selections/validation-full-grid-v1/merged/selections.jsonl',
    'test': D / 'selections/test-full-grid-v1/merged/selections.jsonl',
}
PREFIX = b'{"cell_id": "chain_intermediates|'
WHOLE = {'capped_n1', 'best_n_exact', 'random_complete', 'raw_n1', 'best_n_released80'}
OUT = HERE / 'candidates.jsonl'
SUMMARY = HERE / 'candidates_summary.json'


def main():
    t0 = time.time()
    stats = collections.Counter()
    top_keys = None
    tmp = OUT.with_suffix('.jsonl.tmp')
    with open(tmp, 'w') as out:
        for stage, path in SELECTIONS.items():
            with open(path, 'rb') as f:
                for raw in f:
                    if not raw.startswith(PREFIX):
                        continue
                    row = json.loads(raw)
                    if top_keys is None:
                        top_keys = sorted(row)
                        stats['example_line_bytes'] = len(raw)
                    cands = []
                    trace32 = None
                    for s in row['selections']:
                        if s['method'] not in WHOLE:
                            continue
                        samples = sorted({int(p.rsplit(':', 2)[1]) for p in s['phrase_ids']})
                        exact = (s.get('fits') or {}).get('exact') or {}
                        cands.append({
                            'cond': f"{s['method']}-n{s['n']}", 'method': s['method'], 'n': s['n'],
                            'samples': samples, 'fve': exact.get('fve'),
                            'text_sha256': hashlib.sha256(s['text'].encode()).hexdigest(),
                            'bullet_count': s['bullet_count'], 'token_count': s['token_count'],
                            'reason': s['reason'], 'fits_scope': s['fits_scope']})
                        stats[f"multi_sample[{s['method']}]"] += len(samples) > 1
                        if s['method'] == 'best_n_exact' and s['n'] == 32:
                            trace32 = [[int(t['sample_id'].rsplit(':', 1)[1]), t['score']] for t in s['trace']]
                    out.write(json.dumps({'cell_id': row['cell_id'], 'item_id': row['item_id'], 'layer': row['layer'],
                                          'position': row['position'], 'split': stage, 'candidates': cands,
                                          'trace_best_n_exact_n32': trace32}) + '\n')
                    stats[f'cells[{stage}]'] += 1
            print(stage, 'done', round(time.time() - t0, 1), 's', flush=True)
    tmp.replace(OUT)
    SUMMARY.write_text(json.dumps({'stats': dict(stats), 'top_level_keys': top_keys,
                                   'seconds': round(time.time() - t0, 1)}, indent=1))
    print(json.dumps(stats, indent=1))


if __name__ == '__main__':
    main()
