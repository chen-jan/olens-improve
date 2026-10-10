"""Sequential authorized diagnostic batches; one owner per exact-verdict family cache."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path('configs/evaluation_diagnostic_queue_v1.json'))
    p.add_argument('--allow-paid', action='store_true')
    p.add_argument('--concurrency', type=int, default=8)
    p.add_argument('--rpm', type=float, default=200)
    p.add_argument('--only', choices=('B-v5-none', 'D-specificity-pooling', 'E-nonpositive-abstention', 'B-medium-confirmation'))
    a = p.parse_args()
    if not a.allow_paid:
        p.error('Explicit reviewed --allow-paid required')
    if not os.environ.get('OLENS_TRANSPORT_RECOVERY_SINCE'):
        p.error('Frozen recovery epoch required; do not reset it after errors')
    config = json.loads(a.config.read_text())
    digest = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
    if digest(config['manifest']) != config['manifest_sha256']:
        raise ValueError('Frozen diagnostic manifest differs')
    for row in config['queue']:
        if a.only and row['name'] != a.only:
            continue
        if digest(row['selections']) != row['source_sha256']:
            raise ValueError('Frozen selection SHA differs: ' + row['name'])
        conditions = json.loads(Path(row['conditions']).read_text())
        if not conditions:
            raise ValueError('Empty condition list')
        command = [sys.executable, '-m', 'olens_improve.evaluation', '--allow-paid', '--all-families',
            '--selections', row['selections'], '--manifest', config['manifest'], '--output', row['output'],
            '--method', conditions[0]['method'], '--n', str(conditions[0]['n']), '--condition-list', row['conditions'],
            '--run-id', row['run_id'], '--run-cap-usd', row['run_cap_usd'], '--tier', 'default',
            '--concurrency', str(a.concurrency), '--rpm', str(a.rpm), '--shared-cache', config['shared_cache']]
        print(json.dumps({'queue_stage': row['name'], 'conditions': len(conditions), 'source_sha256': row['source_sha256']}), flush=True)
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
