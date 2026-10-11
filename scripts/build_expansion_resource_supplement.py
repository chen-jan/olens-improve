"""Offline parent-allocation accounting from one saved UTC sacct capture."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
JOBS = ('25536297', '25536291', '25536417', '25536927')
TERMINAL = {'COMPLETED', 'CANCELLED', 'FAILED', 'TIMEOUT', 'PREEMPTED',
            'NODE_FAIL', 'OUT_OF_MEMORY', 'BOOT_FAIL', 'DEADLINE', 'REVOKED'}
OWNED = (Path('${OLENS_COMPUTE_ROOT}'),
         Path('${OLENS_DATA_ROOT}'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp(value):
    if value in ('', 'Unknown', 'None', 'N/A'):
        return None
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def allocations(text, partial=False):
    rows = list(csv.DictReader(io.StringIO(text), delimiter='|'))
    fields = {'JobIDRaw', 'State', 'Start', 'End', 'ElapsedRaw', 'AllocTRES'}
    if not rows or not fields.issubset(rows[0]):
        raise ValueError('Require headed UTC sacct --duplicates --parsable2 capture')
    result = {job: [] for job in JOBS}
    seen = set(); pending = []
    for row in rows:
        job = row['JobIDRaw']
        if job not in result:
            continue  # Never add .batch/.extern/diagnostic-step durations.
        start, end = stamp(row['Start']), stamp(row['End'])
        state = row['State'].split()[0].rstrip('+')
        if start is None:
            if state not in TERMINAL and not partial:
                raise ValueError('Owned allocation is not terminal')
            pending.append(row)
            continue
        if (job, start) in seen:
            raise ValueError('Duplicate parent allocation start; do not double count')
        seen.add((job, start))
        terminal = state in TERMINAL and end is not None
        if not terminal and not partial:
            raise ValueError('Owned allocation is ongoing; use a dated partial snapshot')
        elapsed = int(row['ElapsedRaw'])
        if elapsed < 0 or (end is not None and abs((end-start).total_seconds()-elapsed) > 1):
            raise ValueError('Allocation elapsed disagrees with UTC start/end')
        tres = dict(item.split('=', 1) for item in row['AllocTRES'].split(',') if '=' in item)
        cpus = int(tres['cpu'])
        gpus = int(tres.get('gres/gpu', tres.get('gres/gpu:h200', '0')))
        if cpus < 1 or gpus != (1 if job == JOBS[0] else 0) or (job == JOBS[0] and int(tres.get('gres/gpu:h200', '0')) != 1):
            raise ValueError('Unexpected owned allocation resources')
        result[job].append({'start_utc': start.isoformat(), 'end_utc': end.isoformat() if end else None,
                            'state': row['State'], 'terminal': terminal, 'allocated_seconds': elapsed,
                            'allocated_cpus': cpus, 'allocated_gpus': gpus,
                            'allocated_cpu_core_hours': cpus*elapsed/3600,
                            'allocated_gpu_hours': gpus*elapsed/3600,
                            'node': row.get('NodeList'), 'source_parent_row': row})
    for job, intervals in result.items():
        if not intervals:
            raise ValueError('Missing owned parent allocation: '+job)
        intervals.sort(key=lambda row: row['start_utc'])
        for previous, current in zip(intervals, intervals[1:]):
            if previous['end_utc'] is None or stamp(previous['end_utc']) > stamp(current['start_utc']):
                raise ValueError('Overlapping parent intervals within one job')
    return result, pending


def preserve_first_interval(intervals, receipt):
    original = receipt['resource_intervals_utc'][0]
    matched = [r for r in intervals[JOBS[0]]
               if stamp(r['start_utc']) == stamp(original['Start'])]
    if len(matched) != 1 or not matched[0]['terminal'] or stamp(matched[0]['end_utc']) != stamp(original['End']) or matched[0]['allocated_seconds'] != 13332 or matched[0]['source_parent_row']['AllocTRES'] != original['AllocTRES']:
        raise ValueError('Preserved first 13,332-second H200 interval is absent or changed')


def scoped_storage(config):
    roots = [Path(p) for p in config['owned_roots']]
    for root in roots:
        if root.is_symlink() or not any(root.resolve().is_relative_to(base) for base in OWNED):
            raise ValueError('Storage roots must be explicit owned project subtrees')
        if not root.is_dir():
            raise ValueError('Requested storage subtree is absent')
    if not roots or len(set(roots)) != len(roots):
        raise ValueError('Require distinct scoped storage roots')
    sys.path.insert(0, str(ROOT/'infra'))
    from watch_resources import project_storage
    inventory = project_storage(roots, maximum_files=50000)
    return {'observed_utc': datetime.now(timezone.utc).isoformat(), 'owned_subtrees': inventory,
            'externally_reused_artifacts': config.get('externally_reused_artifacts', []),
            'scope': 'Specified subtrees only; inode-deduplicated logical bytes and filesystem allocated blocks. Symlinks excluded; externally reused weights are listed separately without traversal. Not a project quota or peak-storage claim.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('sacct', 'preemption-receipt', 'effort', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--preemption-receipt-sha256', required=True)
    p.add_argument('--effort-sha256', required=True)
    p.add_argument('--captured-utc', required=True)
    p.add_argument('--allow-partial', action='store_true')
    p.add_argument('--storage-roots', type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError('Use a new immutable supplement path')
    captured = datetime.fromisoformat(a.captured_utc.replace('Z', '+00:00'))
    if captured.utcoffset() is None or captured.utcoffset().total_seconds() != 0:
        raise ValueError('Require explicit UTC capture timestamp')
    pins = {str(path): digest(path) for path in (a.sacct, a.preemption_receipt, a.effort)}
    if pins[str(a.preemption_receipt)] != a.preemption_receipt_sha256 or pins[str(a.effort)] != a.effort_sha256:
        raise ValueError('Approved receipt/effort hash differs')
    receipt = json.loads(a.preemption_receipt.read_text()); effort = json.loads(a.effort.read_text())
    intervals, unallocated = allocations(a.sacct.read_text(), a.allow_partial)
    preserve_first_interval(intervals, receipt)
    storage = None
    if a.storage_roots:
        pins[str(a.storage_roots)] = digest(a.storage_roots)
        pins[str(ROOT/'infra/watch_resources.py')] = digest(ROOT/'infra/watch_resources.py')
        storage = scoped_storage(json.loads(a.storage_roots.read_text()))
    terminal = all(r['terminal'] for rows in intervals.values() for r in rows) and all(
        row['State'].split()[0].rstrip('+') in TERMINAL for row in unallocated)
    result = {'schema_version': 1, 'status': 'terminal_allocation_supplement' if terminal else 'dated_partial_allocation_supplement',
              'generated_utc': datetime.now(timezone.utc).isoformat(), 'sacct_captured_utc': captured.isoformat(),
              'effort_generated_utc': effort['generated_utc'], 'effort_status': effort['status'],
              'manifest_sha256': effort['manifest_sha256'], 'parent_allocations_by_job': intervals,
              'unallocated_parent_rows': unallocated,
              'total_allocated_H200_hours': sum(r['allocated_gpu_hours'] for r in intervals[JOBS[0]]),
              'total_allocated_cpu_core_hours': sum(r['allocated_cpu_core_hours'] for rows in intervals.values() for r in rows),
              'cpu_core_hours_scope': 'Allocated host CPUs in all four jobs, including the GPU allocation; not measured process CPU consumption.',
              'first_attempt_committed_scoring_loop_seconds': receipt['first_attempt_last_committed_scoring_loop_wall_seconds'],
              'scoring_loop_scope': receipt['scoring_wall_scope'],
              'operational_timings_from_effort': effort.get('operational_timings', []),
              'actual_gpu_kernel_seconds': None, 'actual_process_cpu_seconds': None,
              'GPU_dollars': None, 'CPU_dollars': None, 'storage': storage, 'source_sha256': pins,
              'implementation_sha256': digest(__file__),
              'limits': ['Allocation totals exclude queue wait and sum parent intervals only; step durations are excluded.',
                         'The prior resumed 232-second snapshot is not added: its interval is replaced by this capture.',
                         'Concurrent allocations contribute separate resource-hours; these are not end-to-end wall latency.',
                         'Scoring-loop timers include host work/inference/I/O and are separate observations, never added to allocation hours.',
                         'Completed-task seconds after resume describe the successful last attempt, not cumulative campaign time.',
                         'No prices, invoice reconciliation, kernel utilization, project quota or exclusive ownership of reused weights inferred.']}
    if any(digest(path) != value for path, value in pins.items()):
        raise ValueError('Source changed while building supplement')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'output': str(a.output), 'sha256': digest(a.output), 'status': result['status']}))


if __name__ == '__main__':
    main()
