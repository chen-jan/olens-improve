"""One family of the signed VAL menu; fail closed before paid dispatch."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.evaluation import evaluation_stage


FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')


def digest(path):
    checksum = sha256()
    with Path(path).open('rb') as source:
        for part in iter(lambda: source.read(1 << 20), b''):
            checksum.update(part)
    return checksum.hexdigest()


def preflight(spec, *, require_forecast=True):
    if (spec['concurrency'], spec['rpm'], spec['tier'], spec['reasoning_effort'],
            spec['automatic_ramp']) != (8, 200, 'default', 'none', False):
        raise ValueError('Transport differs from the reviewed fixed VAL policy')
    # Cohort authority precedes reading any selected text or financial state.
    manifest, stage, _, _ = evaluation_stage(Path(spec['manifest']), Path(spec['fresh_manifest']), Path(spec['gate']))
    if stage != 'validation':
        raise ValueError('This wrapper is restricted to the signed validation stage')
    if len(manifest['cells']) != spec['authorized_cells']:
        raise ValueError('Validation cohort size differs from the signed preparation spec')
    gate = json.loads(Path(spec['gate']).read_bytes())
    fields = ('manifest', 'fresh_manifest', 'gate', 'conditions', 'freeze', 'empirical_summary')
    for field in fields:
        if digest(spec[field]) != spec[field + '_sha256']:
            raise ValueError('Source hash differs: ' + field)
    if (spec['conditions_sha256'] != gate['condition_list_sha256']
            or spec['freeze_sha256'] != gate['freeze_sha256']):
        raise ValueError('VAL menu/freeze differs from its signed analysis gate')
    conditions = json.loads(Path(spec['conditions']).read_bytes())
    if len(conditions) != 12 or len({(row['method'], row['n']) for row in conditions}) != 12:
        raise ValueError('Require the exact twelve distinct signed VAL conditions')
    for path, expected in spec['implementation_source_sha256'].items():
        if digest(path) != expected:
            raise ValueError('Reviewed implementation changed: ' + path)
    required = ['selections', 'selection_sha256', 'export_provenance', 'export_provenance_sha256']
    if require_forecast:
        required += ['forecast', 'forecast_sha256', 'run_cap_usd']
    missing = [field for field in required if spec.get(field) is None]
    if missing:
        raise ValueError('Unresolved preparation fields: ' + ', '.join(missing))
    if digest(spec['selections']) != spec['selection_sha256']:
        raise ValueError('Immutable VAL selection export changed')
    if digest(spec['export_provenance']) != spec['export_provenance_sha256']:
        raise ValueError('Exact-text export provenance changed')
    exported = json.loads(Path(spec['export_provenance']).read_bytes())
    if (exported['status'] != 'complete_immutable_exact_text_projection'
            or exported['output_sha256'] != spec['selection_sha256']
            or exported['manifest_sha256'] != spec['manifest_sha256']
            or exported['dispatch_conditions_sha256'] != spec['conditions_sha256']
            or exported['fresh_manifest_sha256'] != spec['fresh_manifest_sha256']
            or exported['coordinator_gate_sha256'] != spec['gate_sha256']
            or exported['cells'] != spec['authorized_cells'] or exported['conditions'] != conditions
            or exported['condition_cell_counts'] != {
                row['method']+'-n'+str(row['n']):spec['authorized_cells'] for row in conditions}):
        raise ValueError('VAL projection does not bind the signed complete cohort/menu')
    if require_forecast:
        if digest(spec['forecast']) != spec['forecast_sha256']:
            raise ValueError('Reviewed forecast changed')
        forecast = json.loads(Path(spec['forecast']).read_bytes())
        expected = forecast['expected_charge_including_unknown_stage2_upper_using_empirical_means_usd']
        if (forecast['manifest_sha256'] != spec['manifest_sha256']
                or forecast['conditions'] != conditions
                or forecast['selection_sources'] != [{'path': spec['selections'], 'sha256': spec['selection_sha256']}]
                or forecast.get('analysis_authorization', {}).get('coordinator_gate_sha256') != spec['gate_sha256']
                or expected is None or expected > float(spec['run_cap_usd'])
                or float(spec['run_cap_usd']) <= 0):
            raise ValueError('Forecast does not support this exact reviewed queue/ceiling')
    return conditions


def forecast_command(spec):
    return [sys.executable, 'scripts/forecast_judging.py', '--selections', spec['selections'],
            '--manifest', spec['manifest'], '--fresh-manifest', spec['fresh_manifest'], '--gate', spec['gate'],
            '--conditions', spec['conditions'], '--cache', spec['shared_cache'], '--ledger', spec['ledger'],
            '--empirical-summary', spec['empirical_summary'], '--concurrency', '8', '--rpm', '200',
            '--output', spec['planned_forecast_path']]


def evaluation_command(spec, family):
    command = ['taskset', '-c', ','.join(map(str, spec['cpu_pairs'][family])), sys.executable,
            '-m', 'olens_improve.evaluation', '--allow-paid', '--family', family,
            '--selections', spec['selections'], '--manifest', spec['manifest'],
            '--fresh-manifest', spec['fresh_manifest'], '--gate', spec['gate'],
            '--output', spec['judgments'], '--condition-list', spec['conditions'],
            '--method', 'raw_n1', '--n', '1', '--run-id', spec['run_id'],
            '--run-cap-usd', str(spec['run_cap_usd']), '--ledger', spec['ledger'],
            '--tier', 'default', '--concurrency', '8', '--rpm', '200', '--shared-cache', spec['shared_cache'],
            '--stop-file', str(Path(spec['judgments']) / ('stop-' + family))]
    if spec.get('performance_profile_dir'):
        command += ['--performance-profile-dir', str(Path(spec['performance_profile_dir']) / family)]
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--family', choices=FAMILIES)
    parser.add_argument('--allow-paid', action='store_true')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--print-forecast-command', action='store_true')
    args = parser.parse_args()
    spec = json.loads(args.spec.read_bytes())
    preflight(spec, require_forecast=not args.print_forecast_command)
    if args.print_forecast_command:
        print(json.dumps({'network_model_calls': 0, 'command_argv': forecast_command(spec)}))
        return
    if args.validate_only:
        print(json.dumps({'status': 'validated_no_dispatch', 'network_model_calls': 0,
                          'spec_sha256': digest(args.spec)}))
        return
    if not args.allow_paid or spec['status'] != 'root_reviewed_ready':
        raise SystemExit('Root must seal the completed spec and explicitly authorize paid dispatch')
    if not args.family:
        raise SystemExit('Launch one family only after its previous cache owner has exited')
    if (str(os.environ.get('SLURM_JOB_ID')) != spec['job_id']
            or socket.gethostname().split('.')[0] != spec['node']):
        raise SystemExit('Use the reviewed isolated CPU allocation')
    if not set(spec['cpu_pairs'][args.family]) <= os.sched_getaffinity(0):
        raise SystemExit('Family placement lies outside the reviewed allocation')
    if spec.get('performance_profile_dir') and (Path(spec['performance_profile_dir']) / args.family).exists():
        raise SystemExit('Use a fresh per-family execution profile directory; retain older timing evidence')
    environment = os.environ.copy()
    environment.update(PYTHONPATH='src', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='2',
                       OLENS_TRANSPORT_RECOVERY_SINCE=spec['recovery_epoch'])
    # The evaluator acquires this family's existing exclusive cache lock before
    # any calls. This wrapper never stops/signals an older DEV owner itself.
    command = evaluation_command(spec, args.family)
    Path(spec['logs']).mkdir(parents=True, exist_ok=True)
    with (Path(spec['logs']) / ('validation-judging-v1-' + args.family + '.log')).open('a') as log:
        worker = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=environment)
        print(json.dumps({'family': args.family, 'pid': worker.pid, 'spec_sha256': digest(args.spec)}), flush=True)
        code = worker.wait()
    raise SystemExit(code)


if __name__ == '__main__':
    main()
