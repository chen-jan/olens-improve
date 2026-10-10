"""Copied-ledger phase profiling: no production connection or network."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget
from scripts.profile_reservation_copy import PRODUCTION, run


class CopyProfileTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix='olens-ledger-reserve-phase-test-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name); path = root/'fixture-copy.sqlite3'
        ledger = AtomicBudget(path)
        ledger.set_run_limit('development-full-grid-methods-v1', '20')
        aid = ledger.reserve_attempt(100, 50, run_id='development-full-grid-methods-v1')
        ledger.mark_unknown(aid, 'offline fixture retained hold')
        args = SimpleNamespace(allow_disposable_copy=True, copy=path,
            baseline_sha256=sha256(path.read_bytes()).hexdigest(), filesystem_label='offline_fixture',
            budget_source_sha256=sha256((Path(__file__).parents[1]/'src/olens_improve/budget.py').read_bytes()).hexdigest(),
            profiler_source_sha256=sha256((Path(__file__).parents[1]/'scripts/profile_reservation_copy.py').read_bytes()).hexdigest(),
            run_id='development-full-grid-methods-v1', epoch='2026-10-10T07:52:00+00:00',
            cycles=2, maximum_seconds=300, output=root/'report.json')
        return ledger, args

    def test_unchanged_reserve_and_guard_phases_materialize_then_commit_with_holds_retained(self):
        ledger, args = self.fixture()
        before = ledger.snapshot()
        report = run(args)
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(len(report['cycles']), 2)
        self.assertEqual(report['network_model_calls'], 0)
        self.assertEqual(report['historical_holdings_before'], report['historical_holdings_after'])
        for index in range(2):
            observed = {(r['phase'], r['component']) for r in report['records']
                        if r['operation']==f'reserve-{index}'}
            self.assertTrue({('begin','execute'),('commit','execute'),('body.guard.recent','fetchall'),
                ('body.guard.unknown_sum','fetchone'),('body.committed.global','fetchone'),
                ('body.committed.run','fetchone'),('close','close')} <= observed)
        after = ledger.snapshot()
        self.assertEqual(after['unknown_usd'], before['unknown_usd'])
        self.assertEqual(after['attempt_counts']['settled'], 2)
        self.assertEqual(report['exception_counts'], {})
        self.assertTrue(report['source_unchanged_at_completion'])

    def test_production_path_refused_before_sqlite_connection(self):
        _, args = self.fixture(); args.copy = PRODUCTION
        with patch('scripts.profile_reservation_copy.ORIGINAL_CONNECT') as connect:
            with self.assertRaisesRegex(ValueError, 'disposable'):
                run(args)
            connect.assert_not_called()

    def test_source_changes_refused_before_sqlite_connection(self):
        _, args = self.fixture(); args.budget_source_sha256 = '0'*64
        with patch('scripts.profile_reservation_copy.ORIGINAL_CONNECT') as connect:
            with self.assertRaisesRegex(ValueError, 'source hash'):
                run(args)
            connect.assert_not_called()

    def test_hash_and_epoch_changes_refused_before_sqlite_connection(self):
        _, args = self.fixture(); args.baseline_sha256 = '0'*64
        with patch('scripts.profile_reservation_copy.ORIGINAL_CONNECT') as connect:
            with self.assertRaisesRegex(ValueError, 'baseline hash'):
                run(args)
            connect.assert_not_called()
        args.epoch = '2026-10-10T10:40:00+00:00'
        with patch('scripts.profile_reservation_copy.ORIGINAL_CONNECT') as connect:
            with self.assertRaisesRegex(ValueError, 'original development run'):
                run(args)
            connect.assert_not_called()

    def test_original_guard_failure_is_reported_without_releasing_holds(self):
        ledger, args = self.fixture()
        for _ in range(5):
            aid = ledger.reserve_attempt(100, 50, run_id=args.run_id)
            ledger.mark_unknown(aid, 'offline guard fixture')
        args.baseline_sha256 = sha256(args.copy.read_bytes()).hexdigest()
        report = run(args)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['cycles'], [])
        self.assertEqual(report['failure']['exception_class'], 'BudgetExceeded')
        self.assertEqual(report['historical_holdings_before'], report['historical_holdings_after'])
        self.assertEqual(ledger.snapshot()['attempt_counts']['unknown'], 7)
        self.assertTrue(any(r['phase']=='rollback' for r in report['records']))


if __name__ == '__main__': unittest.main()
