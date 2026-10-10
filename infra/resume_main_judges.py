"""Validated same-source recovery on the explicitly reviewed CPU allocation."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys


def digest(path: Path) -> str:
    checksum = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def dispatch_conditions_path(spec: dict, family: str) -> str:
    """Retain the full scientific menu, dispatch only a reviewed remaining list."""
    bindings = spec.get('dispatch_condition_files')
    policy = spec.get('prospective_handoff_policy', {})
    if bindings is None:
        if 'unchanged_menu_remaining_order' in policy:
            raise ValueError('Prepared handoff requires an exact remaining dispatch binding')
        return spec['conditions']  # Historical full-menu recovery contract.
    if set(bindings) != set(spec['cpu_pairs']) or family not in bindings:
        raise ValueError('Dispatch bindings differ from the reviewed family placement')
    if digest(Path(spec['conditions'])) != spec['conditions_sha256']:
        raise ValueError('Original full scientific menu changed')
    for field in ('validation_spec', 'signed_validation_freeze'):
        if digest(Path(policy[field])) != policy[field+'_sha256']:
            raise ValueError('Prospective handoff evidence changed: '+field)
    bound = bindings[family]
    if digest(Path(bound['path'])) != bound['sha256']:
        raise ValueError('Remaining dispatch file hash differs')
    signed = json.loads(Path(spec['conditions']).read_text())
    remaining = json.loads(Path(bound['path']).read_text())
    if not remaining or any(set(row) != {'method', 'n'} or isinstance(row['n'], bool)
                            or not isinstance(row['n'], int) for row in remaining):
        raise ValueError('Require nonempty exact remaining condition identities')
    indices = []
    for row in remaining:
        if row not in signed:
            raise ValueError('Remaining condition is outside the original scientific menu')
        indices.append(signed.index(row))
    if indices != sorted(set(indices)):
        raise ValueError('Remaining conditions must be distinct and keep original order')
    if remaining != policy['unchanged_menu_remaining_order']:
        raise ValueError('Dispatch differs from the exact prospective remaining list')
    return bound['path']


def evaluation_command(spec: dict, family: str, cpus: list[int]) -> list[str]:
    label = spec.get('recovery_label', 'v1')
    command = ['taskset','-c',','.join(map(str,cpus)),sys.executable,'-m','olens_improve.evaluation',
        '--allow-paid','--family',family,'--selections',spec['selections'],'--manifest',spec['manifest'],
        '--output',spec['judgments'],'--method','raw_n1','--n','1',
        '--condition-list',dispatch_conditions_path(spec,family),'--run-id',spec['run_id'],
        '--run-cap-usd',str(spec['run_cap_usd']),'--ledger',spec['ledger'],'--tier',spec['tier'],
        '--concurrency',str(spec['concurrency']),'--rpm',str(spec['rpm']),
        '--shared-cache',spec['shared_cache'],
        '--stop-file',str(Path(spec['judgments'])/f'stop-recovery-{label}-{family}')]
    if spec.get('performance_profile_dir'):
        command += ['--performance-profile-dir',str(Path(spec['performance_profile_dir'])/family)]
    return command


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--allow-paid',action='store_true')
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    if not args.allow_paid:
        raise SystemExit('Coordinator must explicitly authorize this reviewed paid queue')
    if spec.get('dispatch_condition_files') and spec.get('status') != 'root_reviewed_ready':
        raise SystemExit('Root must seal the exact remaining dispatch spec before paid launch')
    for family in spec['cpu_pairs']:
        dispatch_conditions_path(spec, family)
    if str(os.environ.get('SLURM_JOB_ID')) != spec['job_id'] or socket.gethostname().split('.')[0] != spec['node']:
        raise SystemExit('Recovery must run on the reviewed isolated allocation')
    if (spec['concurrency'],spec['rpm'],spec['tier'],spec['reasoning_effort'],spec['automatic_ramp']) != (8,200,'default','none',False):
        raise SystemExit('Recovery transport differs from the reviewed policy')
    evidence_fields = ['selections','manifest','conditions','healthcheck','incident','resource']
    if 'index_application' in spec:
        evidence_fields.append('index_application')
    if 'copied_load' in spec:
        evidence_fields.append('copied_load')
    for field in evidence_fields:
        key = 'selection_sha256' if field=='selections' else field+'_sha256'
        if digest(Path(spec[field])) != spec[key]:
            raise SystemExit('Recovery source/evidence hash mismatch: '+field)
    for path, expected in spec.get('implementation_source_sha256', {}).items():
        if digest(Path(path)) != expected:
            raise SystemExit('Reviewed operational implementation changed: '+path)
    health = json.loads(Path(spec['healthcheck']).read_text())
    if health['status']!='success' or health['run_id']!=spec['run_id'] or not health['original_unknown_status_preserved']:
        raise SystemExit('Fresh bounded healthcheck did not pass the reviewed contract')
    if datetime.fromisoformat(spec['recovery_epoch']) <= datetime.fromisoformat(health['started_utc']):
        raise SystemExit('Recovery epoch must follow the retained healthcheck')
    incident = json.loads(Path(spec['incident']).read_text())
    if 'copied_load' in spec:
        load = json.loads(Path(spec['copied_load']).read_text())
        if load['network_calls'] != 0 or not load['source_accounting_unchanged']:
            raise SystemExit('Copied-load diagnostic did not preserve the reviewed no-network accounting contract')
    if 'index_application' in spec:
        indexed = json.loads(Path(spec['index_application']).read_text())
        if (indexed['status'] != 'applied' or indexed['before'] != indexed['after_indexes']
                or indexed['financial_hold_released_nanodollars'] != 0
                or indexed['after_abandoned_hold_classification']['committed_nanodollars']
                    != indexed['before']['committed_nanodollars']):
            raise SystemExit('Index application did not preserve the reviewed accounting contract')
    with closing(sqlite3.connect(f"file:{spec['ledger']}?mode=ro",uri=True,
                                isolation_level=None)) as db:
        cap = db.execute('SELECT cap FROM run_limits WHERE run_id=?',(spec['run_id'],)).fetchone()
        if cap is None or cap[0]!=spec['run_cap_usd']*1e9:
            raise SystemExit('Shared run ceiling differs from the reviewed contract')
        retained = incident['unknown_attempts'] + incident.get('abandoned_reserved_attempts', [])
        for attempt in retained:
            state = db.execute('SELECT status FROM attempts WHERE attempt_id=?',(attempt['attempt_id'],)).fetchone()
            if state is None or state[0]!='unknown':
                raise SystemExit('An original uncertain hold changed; explicit reconciliation review required')
    allowed = os.sched_getaffinity(0)
    assigned = [cpu for pair in spec['cpu_pairs'].values() for cpu in pair]
    if len(assigned)!=len(set(assigned)) or not set(assigned)<=allowed:
        raise SystemExit('Family CPU placement is overlapping or outside the reviewed allocation')
    environment = os.environ.copy()
    environment['OLENS_TRANSPORT_RECOVERY_SINCE'] = spec['recovery_epoch']
    environment['PYTHONPATH'] = 'src'
    environment['OPENBLAS_NUM_THREADS'] = '1'
    environment['OMP_NUM_THREADS'] = '2'
    workers = []
    label = spec.get('recovery_label','v1')
    if not re.fullmatch('[a-z0-9-]{1,40}',label):
        raise SystemExit('Recovery label must be a safe provenance suffix')
    profile_root = Path(spec['performance_profile_dir']) if spec.get('performance_profile_dir') else None
    if profile_root is not None and profile_root.exists():
        raise SystemExit('Use a fresh execution-specific profile directory; preserve existing timing evidence')
    for family, cpus in spec['cpu_pairs'].items():
        log = Path(spec['logs'])/f'full-dev-judging-recovery-{label}-{family}.log'
        command = evaluation_command(spec, family, cpus)
        with log.open('a') as handle:
            worker = subprocess.Popen(command,stdout=handle,stderr=subprocess.STDOUT,env=environment)
        workers.append((family,worker))
        print(json.dumps({'family':family,'pid':worker.pid,'cpu_pair':cpus,'log':str(log),
            'recovery_epoch':spec['recovery_epoch'],'spec_sha256':digest(args.spec)}),flush=True)
    codes = {family:worker.wait() for family,worker in workers}
    print(json.dumps({'terminal_codes':codes}),flush=True)
    if any(codes.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
