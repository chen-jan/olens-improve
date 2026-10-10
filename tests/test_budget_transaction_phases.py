"""Opt-in phase timings preserve exact SQL, accounting, and failure behavior."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import olens_improve.budget as budget
from olens_improve.budget import AtomicBudget, BudgetExceeded
from olens_improve.performance import OperationalProfile


class TransactionPhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def ledger(self, name):
        return AtomicBudget(self.root / (name + '.sqlite3'), hard_usd='1',
                            target_usd='1', bootstrap_claude=False)

    def profile(self, ledger, name='phases'):
        profile = OperationalProfile(self.root / (name + '.json'))
        profile.attach_ledger(ledger)
        return profile

    def test_same_sql_rows_caps_and_holds_with_profile_on_or_off(self):
        plain, timed = self.ledger('plain'), self.ledger('timed')
        profile = self.profile(timed)
        traces = []
        snapshots = []
        rows = []
        original = sqlite3.connect
        for ledger in (plain, timed):
            trace = []

            def connect(*args, **kwargs):
                db = original(*args, **kwargs)
                db.set_trace_callback(trace.append)
                return db

            with patch.object(budget.sqlite3, 'connect', connect), \
                 patch.object(budget, '_utc', return_value='2026-10-10T00:00:00+00:00'):
                ledger.set_run_limit('frozen', '.00013')
                aid = ledger.reserve_attempt(100, 100, run_id='frozen', attempt_id='one',
                    metadata={'synthetic_secret': 'not_in_the_profile'},
                    dispatch_guard={'since_utc': '2026-10-10T00:00:00+00:00'})
                ledger.record_evidence(aid, 'physical_response', {'synthetic': True})
                ledger.settle(aid, input_tokens=100, output_tokens=10)
                aid = ledger.reserve_attempt(100, 100, run_id='frozen', attempt_id='two')
                ledger.mark_unknown(aid, 'uncertain')
                with self.assertRaises(BudgetExceeded):
                    ledger.reserve_attempt(100, 100, run_id='frozen', attempt_id='three')
                snapshot = ledger.snapshot()
                snapshot.pop('db_path')
                snapshots.append(snapshot)
            traces.append(trace)
            with closing(original(ledger.path)) as db:
                rows.append((db.execute('SELECT * FROM attempts ORDER BY attempt_id').fetchall(),
                             db.execute('SELECT * FROM events ORDER BY sequence').fetchall()))
        report = profile.close('completed')
        self.assertEqual(traces[0], traces[1])
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(report['metrics']['ledger.transaction.rollback']['count'], 1)
        self.assertNotIn('not_in_the_profile', json.dumps(report))
        self.assertNotIn('synthetic_secret', json.dumps(report))
        self.assertFalse(hasattr(plain, '_operational_profile'))

    def test_delay_is_attributed_to_connect_body_commit_and_close(self):
        ledger = self.ledger('delays')
        profile = self.profile(ledger)
        original = sqlite3.connect

        class SlowConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                if sql == 'COMMIT':
                    time.sleep(.01)
                return super().execute(sql, parameters)

            def close(self):
                time.sleep(.01)
                return super().close()

        def connect(*args, **kwargs):
            time.sleep(.01)
            return original(*args, **kwargs, factory=SlowConnection)

        with patch.object(budget.sqlite3, 'connect', connect):
            with ledger._transaction() as db:
                time.sleep(.01)
                db.execute('SELECT 1').fetchone()
        report = profile.close('completed')
        for name in ('connect', 'body', 'commit', 'close'):
            metric = report['metrics']['ledger.transaction.' + name]
            self.assertEqual(metric['count'], 1)
            self.assertGreaterEqual(metric['total_seconds'], .008)
        for name in ('pragma.busy_timeout', 'pragma.journal_mode', 'pragma.synchronous', 'begin_acquire'):
            self.assertEqual(report['metrics']['ledger.transaction.' + name]['count'], 1)
        self.assertGreaterEqual(report['metrics']['ledger.admission.hold']['total_seconds'], .04)

    def test_body_exception_and_interrupt_roll_back_once_and_keep_original(self):
        ledger = self.ledger('failures')
        profile = self.profile(ledger)
        for error in (ValueError('private payload'), KeyboardInterrupt()):
            with self.assertRaises(type(error)) as caught:
                with ledger._transaction() as db:
                    db.execute("INSERT INTO run_limits VALUES ('rolled-back', 1)")
                    raise error
            self.assertIs(caught.exception, error)
        report = profile.close('failed')
        self.assertEqual(report['metrics']['ledger.transaction.body']['exception_classes'],
                         {'ValueError': 1, 'KeyboardInterrupt': 1})
        self.assertEqual(report['metrics']['ledger.transaction.rollback']['count'], 2)
        self.assertEqual(report['metrics']['ledger.transaction.close']['count'], 2)
        self.assertNotIn('ledger.transaction.commit', report['metrics'])
        self.assertNotIn('private payload', json.dumps(report))
        with ledger._transaction() as db:
            self.assertIsNone(db.execute("SELECT cap FROM run_limits WHERE run_id='rolled-back'").fetchone())

    def test_commit_failure_is_distinct_from_body_and_rolls_back(self):
        ledger = self.ledger('commit')
        ledger.set_run_limit('reader', '1')
        profile = self.profile(ledger)
        with closing(sqlite3.connect(ledger.path, isolation_level=None)) as reader:
            reader.execute('BEGIN')
            reader.execute('SELECT cap FROM run_limits').fetchall()
            with patch.object(budget, 'NORMAL_BUSY_WAIT_MS', 10), self.assertRaises(sqlite3.OperationalError):
                with ledger._transaction() as db:
                    db.execute("UPDATE run_limits SET cap=2 WHERE run_id='reader'")
            reader.execute('ROLLBACK')
        report = profile.close('failed')
        self.assertEqual(report['metrics']['ledger.transaction.commit']['exception_classes'], {'OperationalError': 1})
        self.assertEqual(report['metrics']['ledger.transaction.body']['exception_classes'], {})
        self.assertEqual(report['metrics']['ledger.transaction.rollback']['count'], 1)
        self.assertEqual(report['metrics']['ledger.transaction.close']['count'], 1)
        with closing(sqlite3.connect(ledger.path)) as db:
            self.assertEqual(db.execute("SELECT cap FROM run_limits WHERE run_id='reader'").fetchone()[0], budget.usd_units('1'))

    def test_concurrent_call_frames_do_not_share_phase_or_error_state(self):
        good, bad = self.ledger('good'), self.ledger('bad')
        profile = self.profile(good)
        profile.attach_ledger(bad)
        barrier = threading.Barrier(2)

        def cycles(ledger, count, fail):
            for index in range(count):
                try:
                    with ledger._transaction() as db:
                        if index == 0:
                            barrier.wait(timeout=2)
                        db.execute('SELECT 1').fetchone()
                        if fail:
                            raise ValueError('synthetic failure')
                except ValueError:
                    if not fail:
                        raise

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(cycles, good, 7, False)
            b = pool.submit(cycles, bad, 4, True)
            a.result(timeout=5)
            b.result(timeout=5)
        report = profile.close('completed')
        self.assertEqual(report['metrics']['ledger.transaction.body']['count'], 11)
        self.assertEqual(report['metrics']['ledger.transaction.body']['exception_classes'], {'ValueError': 4})
        self.assertEqual(report['metrics']['ledger.transaction.commit']['count'], 7)
        self.assertEqual(report['metrics']['ledger.transaction.rollback']['count'], 4)
        self.assertEqual(report['metrics']['ledger.transaction.close']['count'], 11)
        self.assertEqual(report['metrics']['ledger.admission.hold']['count'], 11)

    def test_profiler_failure_cannot_change_financial_commit_or_mask_exception(self):
        ledger = self.ledger('observer')
        profile = self.profile(ledger)
        with patch.object(profile, 'observe', side_effect=RuntimeError('private observer')), \
             self.assertLogs('olens_improve.budget', 'WARNING') as logs:
            ledger.set_run_limit('committed', '1')
            error = ValueError('original body failure')
            with self.assertRaises(ValueError) as caught:
                with ledger._transaction():
                    raise error
            self.assertIs(caught.exception, error)
        profile.close('completed')
        self.assertTrue(all('private observer' not in line for line in logs.output))
        with closing(sqlite3.connect(ledger.path)) as db:
            self.assertEqual(db.execute("SELECT cap FROM run_limits WHERE run_id='committed'").fetchone()[0], budget.usd_units('1'))

    def test_only_completed_slow_phases_log_without_payloads(self):
        ledger = self.ledger('slow-logs')
        profile = self.profile(ledger)
        with patch.object(budget, 'ADMISSION_LOG_SECONDS', .005), \
             self.assertLogs('olens_improve.budget', 'WARNING') as logs:
            ledger._observe_transaction_phase('transaction.synthetic_fast', 0.)
            for error in (None, ValueError('private body payload')):
                try:
                    with ledger._transaction() as db:
                        # No start message or per-fast-call message is emitted.
                        body_before = sum('phase=transaction.body ' in r.getMessage()
                                          for r in logs.records)
                        db.execute('SELECT 1').fetchone()
                        time.sleep(.008)
                        self.assertEqual(sum('phase=transaction.body ' in r.getMessage()
                                             for r in logs.records), body_before)
                        if error is not None:
                            raise error
                except ValueError as caught:
                    self.assertIs(caught, error)
        profile.close('completed')
        body = [line for line in logs.output if 'phase=transaction.body ' in line]
        self.assertEqual(len(body), 2)
        self.assertIn('exception_class=none', body[0])
        self.assertIn('exception_class=ValueError', body[1])
        self.assertTrue(all('elapsed_seconds=' in line for line in body))
        self.assertTrue(all('private body payload' not in line for line in logs.output))
        # Ordinary phases below the threshold remain absent.
        self.assertFalse(any('phase=transaction.synthetic_fast ' in line for line in logs.output))


if __name__ == '__main__':
    unittest.main()
