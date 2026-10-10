"""Shared writer admission on disposable ledgers; no SDK or production state."""
from contextlib import closing
import errno
import fcntl
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

import olens_improve.budget as budget
from olens_improve.budget import AtomicBudget, BudgetExceeded


def _entry_worker(path, active, maximum, queue, cycles, delay):
    """Observe admission before connect, not merely SQLite's own body exclusion."""
    original = sqlite3.connect

    class Connection:
        def __init__(self, inner):
            self.inner = inner

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def close(self):
            try:
                self.inner.close()
            finally:
                with active.get_lock():
                    active.value -= 1

    def connect(*args, **kwargs):
        with active.get_lock():
            active.value += 1
            maximum.value = max(maximum.value, active.value)
        time.sleep(delay)
        return Connection(original(*args, **kwargs))

    try:
        with patch.object(budget.sqlite3, 'connect', connect):
            ledger = AtomicBudget(path, hard_usd='1', target_usd='1', bootstrap_claude=False)
            for _ in range(cycles):
                with ledger._transaction() as db:
                    db.execute('SELECT 1').fetchone()
        queue.put('complete')
    except BaseException as error:
        queue.put(type(error).__name__)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ledger.sqlite3'
        self.ledger = AtomicBudget(self.path, hard_usd='1', target_usd='1', bootstrap_claude=False)
        self.lock_path = self.path.with_name(self.path.name + '.admission.lock')

    def assert_lock_free(self):
        fd = os.open(self.lock_path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)

    def test_three_processes_exclude_before_connect_through_close(self):
        ctx = multiprocessing.get_context('spawn')
        active, maximum = ctx.Value('i', 0), ctx.Value('i', 0)
        queue = ctx.Queue()
        # One aggressive producer and two slower ones all have to complete.
        # This is a bounded starvation probe, not a proof of FIFO scheduling.
        workers = [ctx.Process(target=_entry_worker,
            args=(str(self.path), active, maximum, queue, cycles, delay))
            for cycles, delay in [(80, .001), (12, .012), (12, .006)]]
        try:
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(10)
            self.assertEqual([w.exitcode for w in workers], [0, 0, 0])
            self.assertEqual([queue.get(timeout=1) for _ in workers], ['complete'] * 3)
            self.assertEqual(maximum.value, 1)
            self.assertEqual(active.value, 0)
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                worker.join()
            queue.close()

    def test_timeout_enters_no_sqlite_and_preserves_all_holds(self):
        aid = self.ledger.reserve_attempt(100, 100, run_id='retained')
        self.ledger.mark_unknown(aid, 'offline uncertain charge')
        before = self.ledger.snapshot()
        fd = os.open(self.lock_path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(budget, 'ADMISSION_ACQUISITION_SECONDS', .025), \
                 patch.object(budget, 'ADMISSION_BACKOFF_SECONDS', .003), \
                 patch.object(budget.sqlite3, 'connect') as connect, \
                 self.assertLogs('olens_improve.budget', 'WARNING'), \
                 self.assertRaisesRegex(TimeoutError, 'no SQLite transaction entered'):
                self.ledger.reserve_attempt(100, 100, run_id='retained')
            connect.assert_not_called()
        finally:
            os.close(fd)
        self.assertEqual(self.ledger.snapshot(), before)
        self.assert_lock_free()

    def test_error_and_interrupt_roll_back_once_and_release(self):
        inode = self.lock_path.stat().st_ino
        for error in (RuntimeError('offline body failure'), KeyboardInterrupt()):
            with self.assertRaises(type(error)):
                with self.ledger._transaction() as db:
                    db.execute("INSERT INTO run_limits VALUES ('rollback-only', 1)")
                    raise error
            self.assert_lock_free()
            with closing(sqlite3.connect(self.path)) as db:
                self.assertIsNone(db.execute("SELECT cap FROM run_limits WHERE run_id='rollback-only'").fetchone())
        self.assertEqual(self.lock_path.stat().st_ino, inode)

    def test_connect_failure_releases_and_next_body_commits_once(self):
        with patch.object(budget.sqlite3, 'connect', side_effect=sqlite3.OperationalError('offline connect')):
            with self.assertRaises(sqlite3.OperationalError):
                with self.ledger._transaction():
                    self.fail('Connection failure must not enter body')
        self.assert_lock_free()
        with self.ledger._transaction() as db:
            db.execute("INSERT INTO run_limits VALUES ('once', 1)")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM run_limits WHERE run_id='once'").fetchone()[0], 1)

    def test_symlink_database_alias_uses_same_persistent_sibling(self):
        alias = self.path.with_name('database-alias.sqlite3')
        alias.symlink_to(self.path)
        other = object.__new__(AtomicBudget)
        other.path = alias
        fd = os.open(self.lock_path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(budget, 'ADMISSION_ACQUISITION_SECONDS', .015), \
                 patch.object(budget, 'ADMISSION_BACKOFF_SECONDS', .002), \
                 self.assertLogs('olens_improve.budget', 'WARNING'), \
                 self.assertRaises(TimeoutError):
                with other._writer_admission():
                    self.fail('An alias must not bypass admission')
        finally:
            os.close(fd)
        self.assertFalse(alias.with_name(alias.name + '.admission.lock').exists())

    def test_noncontention_lock_error_does_not_enter_sqlite(self):
        with patch.object(budget.fcntl, 'flock', side_effect=OSError(errno.EIO, 'offline lock I/O')), \
             patch.object(budget.sqlite3, 'connect') as connect, self.assertRaises(OSError):
            with self.ledger._transaction():
                self.fail('Lock I/O failure must not enter body')
        connect.assert_not_called()
        self.assert_lock_free()

    def test_native_reader_commit_lock_is_not_hidden_by_admission(self):
        with self.ledger._transaction() as db:
            db.execute("INSERT INTO run_limits VALUES ('reader', 1)")
        with closing(sqlite3.connect(self.path, isolation_level=None)) as reader:
            reader.execute('BEGIN')
            reader.execute('SELECT cap FROM run_limits').fetchall()
            with patch.object(budget, 'NORMAL_BUSY_WAIT_MS', 10), self.assertRaises(sqlite3.OperationalError):
                with self.ledger._transaction() as db:
                    db.execute("UPDATE run_limits SET cap=2 WHERE run_id='reader'")
            reader.execute('ROLLBACK')
        self.assert_lock_free()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT cap FROM run_limits WHERE run_id='reader'").fetchone()[0], 1)

    def test_caps_and_unknown_amount_remain_authoritative_after_admission(self):
        self.ledger.set_run_limit('frozen', '.00011')
        aid = self.ledger.reserve_attempt(100, 100, run_id='frozen')
        self.ledger.mark_unknown(aid, 'offline uncertain response')
        before = self.ledger.snapshot()
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve_attempt(100, 100, run_id='frozen')
        self.assertEqual(self.ledger.snapshot(), before)
        self.assertEqual(before['attempt_counts'], {'unknown': 1})
        self.assert_lock_free()


if __name__ == '__main__':
    unittest.main()
