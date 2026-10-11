#!/usr/bin/env python3
"""Publish finite ready descriptors into the live API queue; no API/ledger reads.

Running judges keep their original condition in flight. This tiny bridge copies
only immutable pointer descriptors, and stops their queues at finite completion.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import time

from expanded_api import atomic_text, digest
from olens_improve.data import canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--inventory-sha256',required=True)
    parser.add_argument('--root',type=Path,default=Path('${OLENS_DATA_ROOT}/expansion-v1'))
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or digest(args.inventory)!=args.inventory_sha256:
        raise ValueError('Require allocated CPU and sealed finite menu')
    inventory = json.loads(args.inventory.read_text())
    expected = {c['condition_id'] for c in inventory['conditions'] if c['status'] not in
        ('obsolete_malformed_transport_diagnostic','exact_alias','computed_numerical_diagnostic_only')}
    # This directory is already registered in every live family worker. Prefix
    # pointer copies distinctly; original helper exports remain immutable.
    queue = args.root/'selections'/'semantic-semantic-v1'
    queue.mkdir(parents=True,exist_ok=True)
    state_path = Path('.state/expansion-api-v1.json')
    published = {}
    while True:
        for path in args.root.joinpath('selections').glob('**/*.ready.json'):
            if path.name.startswith('_queue_'):
                continue
            descriptor = json.loads(path.read_text())
            if not descriptor.get('ready',True):
                continue
            if descriptor.get('inventory_sha256')!=args.inventory_sha256:
                raise ValueError('Ready descriptor lies outside sealed authority')
            source_hash = digest(path)
            target = queue/f'_queue_{source_hash}.ready.json'
            if not target.exists():
                atomic_text(target,canonical(descriptor)+'\n')
                published[str(path)] = {'sha256':source_hash,'pointer_copy':str(target)}
        families = {}
        for family in inventory['families']:
            path = args.root/'judgments'/f'{family}.queue-state.json'
            if path.exists():
                row = json.loads(path.read_text())
                done = set(row['completed'])
                families[family] = {'completed':len(done & expected),'expected':len(expected),
                    'missing':sorted(expected-done),'pid':row.get('pid'),'running':row.get('running',False)}
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        state.update(queue_publisher_pid=os.getpid(),last_successful_check_unix=time.time(),
                     phase='running',judgments=families,published_descriptors=published)
        atomic_text(state_path,canonical(state)+'\n')
        if len(families)==len(inventory['families']) and all(not f['missing'] for f in families.values()):
            for family, row in families.items():
                if not row['running']:
                    continue
                pid = row['pid']
                cmdline = Path(f'/proc/{pid}/cmdline')
                if cmdline.exists():
                    command = cmdline.read_bytes().decode().replace('\x00',' ')
                    if ('scripts/expanded_judges.py' in command and args.inventory_sha256 in command
                            and f'--family {family}' in command):
                        os.kill(pid,signal.SIGUSR1)
            state.update(phase='finite_judging_complete',finished_unix=time.time())
            atomic_text(state_path,canonical(state)+'\n')
            return
        time.sleep(20)


if __name__=='__main__':
    main()
