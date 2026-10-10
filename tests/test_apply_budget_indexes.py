"""Offline migration checks: preserved money, separate status events, no API."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget, HOTPATH_INDEX_SQL

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'apply_budget_indexes.py'
definition = importlib.util.spec_from_file_location('apply_budget_indexes', MODULE_PATH)
migration = importlib.util.module_from_spec(definition)
definition.loader.exec_module(migration)


class IndexApplicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.ledger = self.root / 'ledger.sqlite3'
        self.budget = AtomicBudget(self.ledger, bootstrap_claude=False)
        self.attempt = self.budget.reserve_attempt(100, 100, run_id='test', metadata={'pid': 9999999})
        with sqlite3.connect(self.ledger) as db:
            amount = db.execute('SELECT reserved FROM attempts WHERE attempt_id=?', (self.attempt,)).fetchone()[0]
            for statement in HOTPATH_INDEX_SQL:
                db.execute('DROP INDEX ' + statement.split(' ON ', 1)[0].split()[-1])
        self.spec = self.root / 'spec.json'
        self.data = {'ledger': str(self.ledger), 'job_id': 'fixture', 'node': 'fixture',
            'prechange_snapshot': str(self.root / 'before.sqlite3'), 'report': str(self.root / 'report.json'),
            'confirmed_absent_worker_pids': [9999999], 'abandoned_reservations': [
                {'attempt_id': self.attempt, 'prior_status': 'reserved',
                 'reserved_nanodollars': amount, 'pid': 9999999}]}

    def tearDown(self):
        self.directory.cleanup()

    def run_application(self):
        self.spec.write_text(json.dumps(self.data))
        checksum = hashlib.sha256(self.spec.read_bytes()).hexdigest()
        argv = ['apply_budget_indexes.py', '--spec', str(self.spec), '--spec-sha256', checksum, '--allow-apply']
        with patch.object(sys, 'argv', argv), patch.dict(os.environ, {'SLURM_JOB_ID': 'fixture'}), \
                patch.object(migration.socket, 'gethostname', return_value='fixture'), \
                patch.object(migration.os, 'kill', side_effect=ProcessLookupError), \
                contextlib.redirect_stdout(io.StringIO()):
            migration.main()

    def test_index_identity_then_full_hold_preserved_as_unknown(self):
        before = self.budget.snapshot()
        self.run_application()
        result = json.loads((self.root / 'report.json').read_text())
        self.assertEqual(result['before'], result['after_indexes'])
        self.assertEqual(result['financial_hold_released_nanodollars'], 0)
        self.assertEqual(result['after_abandoned_hold_classification']['committed_nanodollars'],
                         result['before']['committed_nanodollars'])
        self.assertEqual(result['after_abandoned_hold_classification']['event_count'],
                         result['before']['event_count'] + 1)
        after = self.budget.snapshot()
        self.assertEqual(before['committed_usd'], after['committed_usd'])
        self.assertEqual(after['unknown_usd'], before['reserved_usd'])
        with sqlite3.connect(self.root / 'before.sqlite3') as frozen:
            self.assertEqual(frozen.execute('SELECT status FROM attempts WHERE attempt_id=?',
                (self.attempt,)).fetchone()[0], 'reserved')
        with self.assertRaises(SystemExit):
            self.run_application()

    def test_retained_response_blocks_uncertain_classification(self):
        self.budget.record_evidence(self.attempt, 'physical_response', {'response_id': 'trusted-fixture'})
        with self.assertRaisesRegex(RuntimeError, 'Physical response exists'):
            self.run_application()
        self.assertFalse((self.root / 'before.sqlite3').exists())
        self.assertEqual(self.budget.snapshot()['attempt_counts'], {'reserved': 1})

    def test_changed_bound_amount_requires_new_review(self):
        self.data['abandoned_reservations'][0]['reserved_nanodollars'] += 1
        with self.assertRaisesRegex(RuntimeError, 'evidence changed'):
            self.run_application()
        self.assertFalse((self.root / 'before.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
