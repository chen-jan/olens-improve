"""Fresh disposable same-node NFS writer fixture; no network or real charges.

Requires the coordinator-reviewed budget source hash and an existing allocation.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from olens_improve.budget import AtomicBudget, cost_units


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cycle(ledger, aid):
    ledger.reserve_attempt(512, 128, run_id='offline-admission-probe', attempt_id=aid,
                           metadata={'fixture_only': True, 'content_cache_key': aid})
    ledger.record_evidence(aid, 'physical_response', {
        'fixture_only': True, 'source_data_bytes': 'x' * 4096,
        'response': {'usage': {'prompt_tokens': 400, 'completion_tokens': 40,
            'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 100}}}})
    ledger.settle(aid, input_tokens=400, output_tokens=40, cache_write_tokens=100,
                  cached_tokens=0, billed_tier='default', response_id='fake-' + aid)


def worker(path, rank, ready, go, reports):
    started = time.monotonic()
    try:
        ledger = AtomicBudget(path, hard_usd='1', target_usd='1', bootstrap_claude=False)
        ready.put(rank)
        if not go.wait(30):
            raise TimeoutError('Fixture start gate timed out')
        durations = []
        for index in range(20):
            tick = time.monotonic()
            cycle(ledger, f'worker-{rank}-{index}')
            durations.append(time.monotonic() - tick)
        reports.put({'worker': rank, 'cycles': 20, 'seconds': time.monotonic() - started,
                     'cycle_max_seconds': max(durations), 'errors': []})
    except BaseException as error:
        reports.put({'worker': rank, 'errors': [type(error).__name__]})
        raise


def holder(path, ready):
    ledger = AtomicBudget(path, hard_usd='1', target_usd='1', bootstrap_claude=False)
    with ledger._transaction():
        ready.set()  # No mutation in the deliberately interrupted transaction.
        time.sleep(60)


def waiter(path, entered, finished, reports):
    entered.set()
    started = time.monotonic()
    ledger = AtomicBudget(path, hard_usd='1', target_usd='1', bootstrap_claude=False)
    cycle(ledger, 'after-killed-holder')
    reports.put({'seconds': time.monotonic() - started, 'cycles': 1})
    finished.set()


def audit(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True,
                                isolation_level=None, timeout=2)) as db:
        states = dict(db.execute('SELECT status,COUNT(*) FROM attempts GROUP BY status').fetchall())
        actual = db.execute('SELECT COALESCE(SUM(actual),0) FROM attempts').fetchone()[0]
        events = dict(db.execute('SELECT kind,COUNT(*) FROM events GROUP BY kind').fetchall())
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
        return {'attempt_counts': states, 'actual_nanodollars': actual,
                'event_counts': events, 'integrity_check': integrity}


def run(directory, budget_sha):
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Run the fixture through an allocated CPU step')
    source = REPO / 'src/olens_improve/budget.py'
    if digest(source) != budget_sha:
        raise ValueError('Reviewed budget source changed before fixture')
    allowed = Path('${OLENS_COMPUTE_ROOT}/diagnostics').resolve()
    directory = directory.resolve()
    if directory.parent != allowed or directory.exists():
        raise ValueError('Require a new direct project diagnostics directory')
    directory.mkdir()
    path = directory / 'fake-ledger.sqlite3'
    ledger = AtomicBudget(path, hard_usd='1', target_usd='1', bootstrap_claude=False)
    ledger.set_run_limit('offline-admission-probe', '.1')
    lock = path.with_name(path.name + '.admission.lock')
    initial_inode = (lock.stat().st_dev, lock.stat().st_ino)
    ctx = mp.get_context('spawn')
    ready, reports, go = ctx.Queue(), ctx.Queue(), ctx.Event()
    children = [ctx.Process(target=worker, args=(path, rank, ready, go, reports)) for rank in range(3)]
    tick = time.monotonic()
    try:
        for child in children:
            child.start()
        assert {ready.get(timeout=30) for _ in children} == {0, 1, 2}
        go.set()
        for child in children:
            child.join(180)
            if child.is_alive() or child.exitcode != 0:
                raise RuntimeError('Concurrent synthetic writer failed or exceeded bound')
        concurrent = [reports.get(timeout=2) for _ in children]
        assert all(not row['errors'] and row['cycles'] == 20 for row in concurrent)
        concurrent_seconds = time.monotonic() - tick
        before_kill = audit(path)
        unit = cost_units(400, 40, cache_write_tokens=100)
        assert before_kill == {'attempt_counts': {'settled': 60}, 'actual_nanodollars': 60 * unit,
                               'event_counts': {'reserved': 60, 'physical_response': 60, 'settled': 60},
                               'integrity_check': 'ok'}
        held, entered, finished = ctx.Event(), ctx.Event(), ctx.Event()
        owner = ctx.Process(target=holder, args=(path, held))
        follower = ctx.Process(target=waiter, args=(path, entered, finished, reports))
        children.extend([owner, follower])
        owner.start()
        if not held.wait(30):
            raise TimeoutError('Owned admission holder did not enter')
        follower.start()
        if not entered.wait(30):
            raise TimeoutError('Owned waiter did not start')
        time.sleep(.2)
        assert not finished.is_set()
        owner.kill()  # This exact disposable child only; no project worker signals.
        owner.join(5)
        assert owner.exitcode == -9
        follower.join(30)
        if follower.is_alive() or follower.exitcode != 0:
            raise RuntimeError('Admission was not released after killing its owned holder')
        killed_waiter = reports.get(timeout=2)
        final = audit(path)
        assert final == {'attempt_counts': {'settled': 61}, 'actual_nanodollars': 61 * unit,
                         'event_counts': {'reserved': 61, 'physical_response': 61, 'settled': 61},
                         'integrity_check': 'ok'}
        assert initial_inode == (lock.stat().st_dev, lock.stat().st_ino)
        assert digest(source) == budget_sha
        result = {'status': 'passed_synthetic_same_node_nfs', 'observed_utc': datetime.now(timezone.utc).isoformat(),
            'job_id': os.environ['SLURM_JOB_ID'], 'physical_cpu_affinity': sorted(os.sched_getaffinity(0)),
            'budget_source_sha256': budget_sha, 'probe_source_sha256': digest(__file__),
            'fake_ledger': str(path), 'fake_ledger_sha256': digest(path),
            'admission_lock': str(lock), 'admission_inode_unchanged': True,
            'concurrent_workers': concurrent, 'concurrent_phase_wall_seconds': concurrent_seconds,
            'concurrent_cycles': 60, 'representative_event_payload_bytes': 4096,
            'kill_holder_waiter': killed_waiter, 'before_kill': before_kill, 'final': final,
            'network_model_calls': 0, 'production_ledger_access': False,
            'limits': ['Three same-node processes on a fresh small synthetic ledger; not a production throughput prediction.',
                'Kernel owner death released the tested admission/SQLite locks; no strict fairness or remote-node guarantee.',
                'Synthetic accounting numbers are not real project charges or a new financial authority.',
                'All disposable evidence retained; no production source/data cleanup or financial transition.']}
        output = directory / 'report.json'
        with output.open('x') as handle:
            json.dump(result, handle, indent=2); handle.write('\n')
        output.chmod(0o444)
        return {'path': str(output), 'sha256': digest(output), 'result': result}
    finally:
        for child in children:
            if child.is_alive():
                child.kill()
            if child.pid is not None:
                child.join(5)
        for queue in (ready, reports):
            queue.close(); queue.join_thread()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--budget-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.directory, args.budget_sha256)), flush=True)
