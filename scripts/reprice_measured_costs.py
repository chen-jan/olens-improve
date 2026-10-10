"""Derive versioned usage-cost records from an immutable audited correction.

Reads the preserved pre-correction database and physical attempt identities;
never changes the ledger, source artifacts, or scientific judgments.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3


def corrected_cost(record, database, changes):
    ids = record['physical_attempt_ids']
    if len(ids) != len(set(ids)):
        raise ValueError('Repeated physical attempt identity')
    attempts = [database.execute('SELECT status,actual FROM attempts WHERE attempt_id=?', (attempt,)).fetchone() for attempt in ids]
    if any(row is None or row[0] != 'settled' for row in attempts):
        raise ValueError('Each charged physical attempt must be settled in the audit snapshot')
    before = sum(row[1] for row in attempts)
    if before != round(record['actual_usd'] * 1e9):
        raise ValueError('Preserved cost differs from its physical attempt sum')
    delta = 0
    writes = 0
    for attempt, row in zip(ids, attempts):
        if attempt in changes:
            change = changes[attempt]
            if change['before_units'] != row[1]:
                raise ValueError('Correction does not bind the preserved physical charge')
            delta += change['after_units'] - change['before_units']
            writes += change['cache_write_tokens']
    return {key: value for key, value in record.items() if key != 'physical_attempt_ids'} | {
        'pre_correction_usd': before / 1e9, 'actual_usd': (before + delta) / 1e9,
        'cache_write_delta_usd': delta / 1e9, 'cache_write_tokens': writes,
        'physical_attempt_ids_sha256': sha256(json.dumps(sorted(ids)).encode()).hexdigest(),
        'pricing_revision': 'luna-cache-write-v1', 'invoice_reconciled': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--durable', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Run source/database audits in a CPU allocation')
    durable, output = Path(args.durable), Path(args.output)
    if output.exists():
        raise FileExistsError('Use a new version; do not replace frozen cost records')
    sources = {}

    def read(path):
        raw = path.read_bytes()
        sources[str(path)] = sha256(raw).hexdigest()
        return json.loads(raw)

    correction = durable / 'budget/pricing-correction-v1'
    applied = read(correction / 'applied.json')
    if applied['pricing_revision'] != 'luna-cache-write-v1' or applied['missing_usage'] or applied['invalid_usage']:
        raise ValueError('Require the complete audited pricing correction')
    changes = {row['attempt_id']: row for row in applied['settled_changes']}
    database_path = correction / 'before.sqlite3'
    sources[str(database_path)] = sha256(database_path.read_bytes()).hexdigest()
    database = sqlite3.connect('file:' + str(database_path) + '?mode=ro', uri=True)
    database.execute('BEGIN')
    old = read(durable / 'diagnostics/costs-v1/components.json')
    raw_helpers = read(durable / 'runs/helper-semantic-pilot-v1/natural-audits/helper-costs-v1.json')
    helpers = [corrected_cost(row, database, changes) for row in raw_helpers]
    repaired = read(durable / 'runs/helper-semantic-repaired-pilot-v1/audits/B-v5-instrument-cost.json')
    v5 = corrected_cost(repaired['cost'], database, changes)
    baseline = read(durable / 'analysis/full-dev-baselines-v1/review.json')
    cost = baseline['judge_cost']
    ids = [row[0] for row in database.execute('SELECT attempt_id FROM attempts WHERE run_id=? ORDER BY attempt_id', (cost['run_id'],))]
    baseline['judge_cost'] = corrected_cost(cost | {'physical_attempt_ids': ids}, database, changes)
    database.commit()
    database.close()
    old['campaign']['helpers'] = helpers
    old['campaign']['helper_b_repaired_v5'] = v5
    for field, folder in [('pruning_combinations', 'combined-pruning-pilot189-v1'), ('exact_support_pooling', 'support-pooling-pilot189-v1')]:
        status = read(durable / 'selections' / folder / 'status.json')
        if status['status'] != 'complete':
            raise ValueError('Combination CPU timing requires terminal status')
        old['campaign'][field] = {'cells': status['cells'], 'conditions': status['conditions'], 'cpu_task_wall_seconds': status['seconds'], 'threads': 4}
    old['deployment']['helper_b_n16_usd_per_cell_observed'] = helpers[0]['actual_usd'] / 189
    old['deployment']['helper_b_repaired_v5_n16_usd_per_cell_observed'] = v5['actual_usd'] / 189
    old['deployment']['helper_f_two_rounds_usd_per_cell_observed'] = sum(row['actual_usd'] for row in helpers[1:]) / 189
    old['schema_version'] = 2
    old['generated_utc'] = datetime.now(timezone.utc).isoformat()
    old['pricing_revision'] = 'luna-cache-write-v1'
    old['invoice_reconciled'] = False
    old['pricing_note'] = 'Audited derived usage estimate including cache writes; provider invoice reconciliation remains unavailable.'
    old['source_sha256'] |= sources
    baseline['pricing_revision'] = 'luna-cache-write-v1'
    baseline['invoice_reconciled'] = False
    baseline['pricing_source_sha256'] = sources
    # Validate all source bytes once more before producing the new version.
    for path, expected in sources.items():
        if sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError('Cost source changed during audit: ' + path)
    output.mkdir(parents=True)
    (output / 'components.json').write_text(json.dumps(old, indent=2) + '\n')
    (output / 'baseline-review.json').write_text(json.dumps(baseline, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'helper_usd': [row['actual_usd'] for row in helpers], 'b_v5_usd': v5['actual_usd'], 'baseline_usd': baseline['judge_cost']['actual_usd'], 'invoice_reconciled': False}))


if __name__ == '__main__':
    main()
