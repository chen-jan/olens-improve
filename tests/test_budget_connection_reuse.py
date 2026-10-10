"""Disposable-ledger writer reuse checks; no production data or paid calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget, BudgetExceeded


def tables(path):
    with closing(sqlite3.connect(path)) as db:
        return {name: db.execute('SELECT * FROM ' + name + ' ORDER BY 1').fetchall()
                for name in ('config', 'run_limits', 'attempts', 'events')}


class ConnectionReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'ledger.sqlite3'
        self.ledger = AtomicBudget(self.path, bootstrap_claude=False)
        self.pool = ThreadPoolExecutor(max_workers=1)

    def tearDown(self):
        try:
            self.pool.submit(self.ledger.close_writer_connection).result(timeout=3)
        except RuntimeError:
            pass  # A deliberately poisoned owner remains fail-closed.
        self.pool.shutdown(wait=True)
        self.tmp.cleanup()

    def owner(self, function, *args, **kwargs):
        return self.pool.submit(function, *args, **kwargs).result(timeout=3)

    def enable(self):
        self.owner(self.ledger.enable_writer_connection_reuse)

    def test_default_connections_close_and_reuse_is_owner_only_with_fixed_pragmas(self):
        original = sqlite3.connect; opened = []
        def connect(*a, **kw):
            db = original(*a, **kw); opened.append(db); return db
        with patch('olens_improve.budget.sqlite3.connect', side_effect=connect):
            self.ledger.set_run_limit('legacy', 1)
            self.ledger.set_run_limit('legacy', 1)
        self.assertEqual(len(opened), 2)
        for db in opened:
            with self.assertRaises(sqlite3.ProgrammingError): db.execute('SELECT 1')
        self.enable()
        self.owner(self.ledger.set_run_limit, 'reuse', 1)
        first = self.ledger._writer_reuse['connection']
        self.owner(self.ledger.set_run_limit, 'reuse', 1)
        self.assertIs(first, self.ledger._writer_reuse['connection'])
        def pragmas():
            return [first.execute('PRAGMA ' + key).fetchone()[0] for key in
                    ('cache_size', 'journal_mode', 'synchronous', 'busy_timeout')], first.in_transaction
        self.assertEqual(self.owner(pragmas), ([-16384, 'delete', 2, 30000], False))
        # Main-thread setup and read snapshots keep separate ephemeral handles.
        self.ledger.set_run_limit('main', 1)
        self.assertIs(first, self.ledger._writer_reuse['connection'])
        with self.assertRaisesRegex(RuntimeError, 'owning thread'): self.ledger.close_writer_connection()
        with self.assertRaisesRegex(RuntimeError, 'different owner'): self.ledger.enable_writer_connection_reuse()
        self.owner(self.ledger.close_writer_connection)
        self.assertIsNone(self.ledger._writer_reuse)
        with self.assertRaises(sqlite3.ProgrammingError): self.owner(first.execute, 'SELECT 1')

    def test_exact_rows_events_caps_and_holds_match_legacy(self):
        other = AtomicBudget(Path(self.tmp.name) / 'other.sqlite3', bootstrap_claude=False)
        def cycle(ledger):
            ledger.set_run_limit('same', 1)
            for name in ('settled', 'unknown', 'released'):
                ledger.reserve_attempt(100, 100, run_id='same', attempt_id=name, metadata={'source': 'fake'})
            ledger.record_evidence('settled', 'physical_response', {'response_id': 'fake'})
            ledger.settle('settled', input_tokens=20, output_tokens=10)
            ledger.mark_unknown('unknown', 'offline uncertainty')
            ledger.release_uncharged('released', evidence='offline proof, no dispatch')
        self.enable()
        with patch('olens_improve.budget._utc', return_value='2026-10-10T00:00:00Z'):
            self.owner(cycle, self.ledger); cycle(other)
        self.assertEqual(tables(self.path), tables(other.path))
        left, right = self.ledger.snapshot(), other.snapshot()
        left.pop('db_path'); right.pop('db_path')
        self.assertEqual(left, right)
        self.assertGreater(left['unknown_usd'], 0)

    def test_snapshot_is_precommit_consistent_and_idle_cache_does_not_block_writer(self):
        self.enable(); entered = threading.Event(); release = threading.Event()
        before = self.ledger.snapshot()
        def transaction():
            with self.ledger._transaction() as db:
                db.execute("INSERT INTO run_limits VALUES ('not-yet-committed', 1)")
                db.execute("UPDATE config SET value=1 WHERE key='halted'")
                entered.set(); release.wait(2)
        future = self.pool.submit(transaction)
        try:
            self.assertTrue(entered.wait(1)); self.assertEqual(self.ledger.snapshot(), before)
        finally:
            release.set(); future.result(timeout=3)
        self.assertTrue(self.ledger.snapshot()['halted'])
        # A live but idle reused handle must not retain SQLite transaction locks.
        with closing(sqlite3.connect(self.path, timeout=.1, isolation_level=None)) as db:
            db.execute('BEGIN IMMEDIATE'); db.execute('COMMIT')

    def test_body_failure_rolls_back_once_and_discards_without_replay(self):
        self.enable(); calls = []
        def failing():
            with self.ledger._transaction() as db:
                calls.append(1); db.execute("INSERT INTO run_limits VALUES ('bad', 1)")
                raise ValueError('offline body error')
        with self.assertRaisesRegex(ValueError, 'body error'): self.owner(failing)
        self.assertEqual(calls, [1]); self.assertIsNone(self.ledger._writer_reuse['connection'])
        self.assertFalse(self.ledger._writer_reuse['poisoned'])
        self.owner(self.ledger.set_run_limit, 'good', 1)
        self.assertNotIn(('bad', 1), tables(self.path)['run_limits'])

    def test_commit_failure_before_or_after_commit_never_replays_body(self):
        original = sqlite3.connect
        for after in (False, True):
            self.owner(self.ledger.close_writer_connection); self.enable(); calls = []
            class Connection:
                def __init__(self, db): self.db = db
                def __getattr__(self, name): return getattr(self.db, name)
                def execute(self, sql, *args):
                    if sql == 'COMMIT':
                        if after: self.db.execute(sql)
                        raise sqlite3.OperationalError('offline commit failure')
                    return self.db.execute(sql, *args)
                def close(self): self.db.close()
            def failing():
                with self.ledger._transaction() as db:
                    calls.append(1)
                    db.execute('INSERT INTO run_limits VALUES (?,1)', ('after' if after else 'before',))
            with patch('olens_improve.budget.sqlite3.connect', side_effect=lambda *a, **k: Connection(original(*a, **k))):
                with self.assertRaisesRegex(sqlite3.OperationalError, 'commit failure'): self.owner(failing)
            self.assertEqual(calls, [1]); self.assertIsNone(self.ledger._writer_reuse['connection'])
        rows = tables(self.path)['run_limits']
        self.assertNotIn(('before', 1), rows); self.assertEqual(rows.count(('after', 1)), 1)

    def test_failed_rollback_or_close_preserves_primary_error_and_poisons_owner(self):
        original = sqlite3.connect
        for failure in ('rollback', 'close'):
            ledger = AtomicBudget(Path(self.tmp.name) / (failure + '.sqlite3'), bootstrap_claude=False)
            self.owner(ledger.enable_writer_connection_reuse)
            class Connection:
                def __init__(self, db): self.db = db
                def __getattr__(self, name): return getattr(self.db, name)
                def execute(self, sql, *args):
                    if failure == 'rollback' and sql == 'ROLLBACK': raise OSError('offline rollback failure')
                    return self.db.execute(sql, *args)
                def close(self):
                    self.db.close()
                    if failure == 'close': raise OSError('offline close failure')
            def failing():
                with ledger._transaction() as db:
                    db.execute("INSERT INTO run_limits VALUES ('bad', 1)")
                    raise ValueError('original body error')
            with patch('olens_improve.budget.sqlite3.connect', side_effect=lambda *a, **k: Connection(original(*a, **k))), \
                 self.assertLogs('olens_improve.budget', 'WARNING'):
                with self.assertRaisesRegex(ValueError, 'original body error'): self.owner(failing)
            self.assertTrue(ledger._writer_reuse['poisoned']); self.assertIsNone(ledger._writer_reuse['connection'])
            with self.assertRaisesRegex(RuntimeError, 'failed cleanup'): self.owner(ledger.reserve_attempt, 1, 1, run_id='blocked')
            self.assertEqual(ledger.snapshot()['attempt_counts'], {})
            self.assertEqual(tables(ledger.path)['run_limits'], [])

    def test_pid_and_inode_changes_fail_before_any_mutation(self):
        self.enable(); self.owner(self.ledger.reserve_attempt, 1, 1, run_id='retained')
        before = self.ledger.snapshot(); pid = os.getpid()
        with patch('olens_improve.budget.os.getpid', return_value=pid + 1):
            with self.assertRaisesRegex(RuntimeError, 'fork'): self.owner(self.ledger.reserve_attempt, 1, 1, run_id='blocked')
        self.assertEqual(self.ledger.snapshot(), before)
        clone = self.path.with_name('clone.sqlite3'); shutil.copyfile(self.path, clone); os.replace(clone, self.path)
        with self.assertRaisesRegex(RuntimeError, 'identity changed'): self.owner(self.ledger.reserve_attempt, 1, 1, run_id='blocked')
        self.assertEqual(self.ledger.snapshot(), before)
        with self.assertRaisesRegex(RuntimeError, 'restart required'): self.owner(self.ledger.close_writer_connection)
        self.assertIsNone(self.ledger._writer_reuse['connection'])

    def test_reused_and_legacy_writers_enforce_one_atomic_cap(self):
        path = Path(self.tmp.name) / 'race.sqlite3'
        reused = AtomicBudget(path, hard_usd='.01', target_usd='.01', bootstrap_claude=False)
        legacy = AtomicBudget(path, hard_usd='.01', target_usd='.01', bootstrap_claude=False)
        reused.set_run_limit('race', '.01'); barrier = threading.Barrier(2)
        def attempt(ledger, reuse):
            if reuse: ledger.enable_writer_connection_reuse()
            try:
                barrier.wait(timeout=2)
                try: ledger.reserve_attempt(1, 12000, run_id='race'); return 'reserved'
                except BudgetExceeded: return 'blocked'
            finally:
                if reuse: ledger.close_writer_connection()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(attempt, reused, True); b = pool.submit(attempt, legacy, False)
            self.assertEqual(sorted([a.result(timeout=3), b.result(timeout=3)]), ['blocked', 'reserved'])
        snapshot = reused.snapshot()
        self.assertEqual(snapshot['attempt_counts'], {'reserved': 1})
        self.assertLessEqual(snapshot['committed_usd'], .01)


if __name__ == '__main__': unittest.main()
