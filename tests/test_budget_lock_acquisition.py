"""Disposable SQLite writer contention; no network or production ledger."""
from contextlib import ExitStack
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import olens_improve.budget as budget
from olens_improve.budget import AtomicBudget, BudgetExceeded


def sql_error(code):
    error = sqlite3.OperationalError('offline fixture')
    error.sqlite_errorcode = code
    return error


class BeginFixture:
    def __init__(self, errors, in_transaction=False):
        self.errors = list(errors)
        self.in_transaction = in_transaction
        self.begins = 0
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        if statement == 'BEGIN IMMEDIATE':
            self.begins += 1
            if self.errors:
                raise self.errors.pop(0)
            self.in_transaction = True


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = AtomicBudget(Path(self.temp.name) / 'ledger.sqlite3',
                                   hard_usd='1', target_usd='1', bootstrap_claude=False)

    def short_waits(self, deadline=0.5):
        stack = ExitStack()
        stack.enter_context(patch.object(budget, 'LOCK_ACQUISITION_SECONDS', deadline))
        stack.enter_context(patch.object(budget, 'LOCK_BUSY_WAIT_MS', 10))
        stack.enter_context(patch.object(budget, 'LOCK_RETRY_BACKOFF_SECONDS', 0.005))
        return stack

    def writer(self):
        writer = sqlite3.connect(self.ledger.path, isolation_level=None)
        writer.execute('BEGIN IMMEDIATE')
        self.addCleanup(writer.close)
        return writer

    def test_concurrent_writer_release_body_once_and_normal_timeout_restored(self):
        writer = self.writer()
        result = []
        errors = []

        def work():
            try:
                with self.ledger._transaction() as db:
                    result.append(db.execute('PRAGMA busy_timeout').fetchone()[0])
                    db.execute("INSERT INTO run_limits VALUES ('body-once', 123)")
            except BaseException as error:
                errors.append(error)

        with self.short_waits(), self.assertLogs('olens_improve.budget', 'WARNING') as log:
            worker = threading.Thread(target=work)
            worker.start()
            time.sleep(0.06)  # Writer remains reserved through several short BUSY waits.
            self.assertEqual(result, [])
            writer.execute('COMMIT')
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(result, [30000])
        self.assertTrue(any('status=acquired' in row and 'retries=' in row for row in log.output))
        with sqlite3.connect(self.ledger.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM run_limits WHERE run_id='body-once'").fetchone()[0], 1)

    def test_deadline_failure_never_enters_body_or_mutates_ledger(self):
        writer = self.writer()
        calls = []
        started = time.monotonic()
        with self.short_waits(0.07), self.assertLogs('olens_improve.budget', 'WARNING') as log:
            with self.assertRaises(sqlite3.OperationalError) as caught:
                with self.ledger._transaction():
                    calls.append('body')
        self.assertEqual(caught.exception.sqlite_errorcode & 0xff, sqlite3.SQLITE_BUSY)
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertEqual(calls, [])
        self.assertTrue(any('status=deadline' in row for row in log.output))
        writer.execute('ROLLBACK')
        self.assertEqual(self.ledger.snapshot()['attempt_counts'], {})

    def test_nonbusy_error_is_not_retried(self):
        db = BeginFixture([sql_error(sqlite3.SQLITE_LOCKED)])
        with patch.object(budget.time, 'sleep') as sleep:
            with self.assertRaises(sqlite3.OperationalError):
                AtomicBudget._begin_immediate(db)
        self.assertEqual(db.begins, 1)
        sleep.assert_not_called()

    def test_busy_after_transaction_started_is_not_retried(self):
        db = BeginFixture([sql_error(sqlite3.SQLITE_BUSY)], in_transaction=True)
        with patch.object(budget.time, 'sleep') as sleep:
            with self.assertRaises(sqlite3.OperationalError):
                AtomicBudget._begin_immediate(db)
        self.assertEqual(db.begins, 1)
        sleep.assert_not_called()

    def test_extended_busy_primary_code_retries_and_restores_timeout(self):
        db = BeginFixture([sql_error(sqlite3.SQLITE_BUSY | (1 << 8))])
        with self.short_waits(), self.assertLogs('olens_improve.budget', 'WARNING'):
            AtomicBudget._begin_immediate(db)
        self.assertEqual(db.begins, 2)
        self.assertEqual(db.statements[-1], 'PRAGMA busy_timeout=30000')

    def test_busy_in_body_and_commit_are_never_replayed(self):
        for failure in ('body', 'commit'):
            with self.subTest(failure=failure):
                real_connect = sqlite3.connect
                calls = []

                class Connection:
                    def __init__(self, *args, **kwargs):
                        self.db = real_connect(*args, **kwargs)

                    def __getattr__(self, name):
                        return getattr(self.db, name)

                    def execute(self, statement, *args):
                        calls.append(statement)
                        if statement == 'COMMIT' and failure == 'commit':
                            raise sql_error(sqlite3.SQLITE_BUSY)
                        return self.db.execute(statement, *args)

                bodies = []
                with patch.object(budget.sqlite3, 'connect', Connection):
                    with self.assertRaises(sqlite3.OperationalError):
                        with self.ledger._transaction() as db:
                            bodies.append('once')
                            db.execute("INSERT INTO run_limits VALUES ('rollback-body', 123)")
                            if failure == 'body':
                                raise sql_error(sqlite3.SQLITE_BUSY)
                self.assertEqual(bodies, ['once'])
                self.assertEqual(calls.count('BEGIN IMMEDIATE'), 1)
                self.assertEqual(calls.count('ROLLBACK'), 1)
                with real_connect(self.ledger.path) as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM run_limits WHERE run_id='rollback-body'").fetchone()[0], 0)

    def test_cap_and_unknown_holds_checked_after_acquisition(self):
        self.ledger.set_run_limit('frozen', '.01')
        aid = self.ledger.reserve_attempt(1, 15000, run_id='frozen')
        self.ledger.mark_unknown(aid, 'offline retained hold')
        before = self.ledger.snapshot()
        writer = self.writer()
        errors = []

        def work():
            try:
                self.ledger.reserve_attempt(1, 6000, run_id='frozen')
            except BaseException as error:
                errors.append(error)

        with self.short_waits(), self.assertLogs('olens_improve.budget', 'WARNING'):
            worker = threading.Thread(target=work)
            worker.start()
            time.sleep(0.04)
            writer.execute('COMMIT')
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BudgetExceeded)
        after = self.ledger.snapshot()
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
