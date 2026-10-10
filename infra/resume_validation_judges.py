"""Resume only incident-bound, unfinished members of the signed VAL menu."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra.launch_validation_judges import digest, evaluation_command, preflight


def preflight_recovery(spec: dict, family: str) -> list[dict]:
    signed = preflight(spec)
    if family not in ('hallucination', 'role_bound_association'):
        raise ValueError('Only the two incident families require recovery')
    for field in ('incident', 'hold_action', 'hold_action_receipt', 'original_validation_spec'):
        if digest(spec[field]) != spec[field + '_sha256']:
            raise ValueError('Recovery evidence hash differs: ' + field)
    original = json.loads(Path(spec['original_validation_spec']).read_bytes())
    for field in ('run_id', 'run_cap_usd', 'manifest_sha256', 'gate_sha256',
                  'conditions_sha256', 'freeze_sha256', 'selection_sha256',
                  'judgments', 'shared_cache', 'ledger'):
        if spec[field] != original[field]:
            raise ValueError('Recovery changed the original scientific/budget contract: ' + field)
    incident = json.loads(Path(spec['incident']).read_bytes())
    action = json.loads(Path(spec['hold_action']).read_bytes())
    receipt = json.loads(Path(spec['hold_action_receipt']).read_bytes())
    if incident['run_id'] != spec['run_id'] or action['financial_hold_release_nanodollars'] != 0:
        raise ValueError('Recovery must retain the original incident and every uncertain hold')
    if (receipt['incident_sha256'] != spec['incident_sha256']
            or receipt['action_sha256'] != spec['hold_action_sha256']
            or receipt['released_nanodollars'] != 0
            or receipt['committed_before_nanodollars'] != receipt['committed_after_nanodollars']
            or receipt['all_fourteen_uncertain_hold_nanodollars'] != incident['all_fourteen_uncertain_hold_nanodollars']):
        raise ValueError('Applied hold transition differs from the reviewed invariant')
    bound = spec['recovery_condition_files'][family]
    if digest(bound['path']) != bound['sha256']:
        raise ValueError('Recovery condition-file hash differs')
    subset = json.loads(Path(bound['path']).read_bytes())
    if not subset or any(set(row) != {'method', 'n'} for row in subset):
        raise ValueError('Require nonempty, exact condition identities')
    indices = []
    for row in subset:
        if row not in signed:
            raise ValueError('Recovery condition is outside the signed menu')
        indices.append(signed.index(row))
    if indices != sorted(set(indices)):
        raise ValueError('Recovery conditions must be distinct and retain signed order')
    if subset != incident['remaining_conditions_by_family'][family]:
        raise ValueError('Recovery differs from the exact unfinished incident list')
    epoch = datetime.fromisoformat(spec['recovery_epoch'])
    if epoch <= max([datetime.fromisoformat(h['updated_utc']) for h in incident['uncertain_holds']]
                    + [datetime.fromisoformat(receipt['applied_utc'])]):
        raise ValueError('Reviewed recovery epoch must follow the documented local shutdown')
    if spec['no_extra_health_call'] is not True or spec['automatic_ramp'] is not False:
        raise ValueError('No extra health call or automatic ramp is authorized')
    if not re.fullmatch('[a-z0-9-]{1,40}', spec['recovery_label']):
        raise ValueError('Require a safe, fresh execution label')
    return subset


def check_retained_holds(spec: dict) -> None:
    incident = json.loads(Path(spec['incident']).read_bytes())
    db = sqlite3.connect(f"file:{spec['ledger']}?mode=ro", uri=True, timeout=5)
    try:
        cap = db.execute('SELECT cap FROM run_limits WHERE run_id=?', (spec['run_id'],)).fetchone()
        if cap is None or cap[0] != spec['run_cap_usd'] * 1_000_000_000:
            raise ValueError('Original shared run ceiling changed')
        for h in incident['uncertain_holds']:
            row = db.execute('SELECT status,reserved,actual FROM attempts WHERE attempt_id=?',
                             (h['attempt_id'],)).fetchone()
            if row != ('unknown', h['retained_reserved_nanodollars'], None):
                raise ValueError('Original uncertain hold differs or reviewed transition is pending')
    finally:
        db.close()


def recovery_command(spec: dict, family: str) -> list[str]:
    command = evaluation_command(spec, family)
    command[command.index('--condition-list') + 1] = spec['recovery_condition_files'][family]['path']
    command[command.index('--stop-file') + 1] = spec['stop_files'][family]
    return command


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--family', choices=('hallucination', 'role_bound_association'), required=True)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--allow-paid', action='store_true')
    args = parser.parse_args()
    spec = json.loads(args.spec.read_bytes())
    subset = preflight_recovery(spec, args.family)
    if args.validate_only:
        print(json.dumps({'status': 'validated_no_dispatch', 'network_model_calls': 0,
                          'spec_sha256': digest(args.spec), 'remaining_conditions': subset}))
        return
    if not args.allow_paid or spec['status'] != 'root_reviewed_ready':
        raise SystemExit('Root must review and explicitly authorize this narrow recovery')
    if str(os.environ.get('SLURM_JOB_ID')) != spec['job_id'] or socket.gethostname().split('.')[0] != spec['node']:
        raise SystemExit('Use the reviewed isolated CPU allocation')
    if not set(spec['cpu_pairs'][args.family]) <= os.sched_getaffinity(0):
        raise SystemExit('Family placement lies outside the reviewed allocation')
    profile = Path(spec['performance_profile_dir']) / args.family
    if profile.exists() or Path(spec['stop_files'][args.family]).exists():
        raise SystemExit('Use fresh profile and stop paths; preserve old execution evidence')
    check_retained_holds(spec)
    env = os.environ.copy()
    env.update(PYTHONPATH='src', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='2',
               OLENS_TRANSPORT_RECOVERY_SINCE=spec['recovery_epoch'])
    log = Path(spec['logs']) / f"validation-recovery-{spec['recovery_label']}-{args.family}.log"
    with log.open('a') as handle:
        worker = subprocess.Popen(recovery_command(spec, args.family), stdout=handle,
                                  stderr=subprocess.STDOUT, env=env)
        print(json.dumps({'family': args.family, 'pid': worker.pid, 'log': str(log),
                          'spec_sha256': digest(args.spec), 'remaining_conditions': subset}), flush=True)
        code = worker.wait()
    raise SystemExit(code)


if __name__ == '__main__':
    main()
