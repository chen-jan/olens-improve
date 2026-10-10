import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from infra.resume_validation_judges import (
    check_retained_holds, digest, preflight_recovery, recovery_command,
)
from infra.launch_validation_judges import evaluation_command


class ValidationRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.spec = json.loads(Path('configs/judging_validation_v1.json').read_text())
        self.signed = json.loads(Path('configs/conditions_validation_v1.json').read_text())
        self.subset = self.signed[7:]
        self.spec.update(recovery_epoch='2026-10-10T10:40:00+00:00',
                         recovery_label='v2-readonly-snapshot', no_extra_health_call=True)
        self.holds = [{'attempt_id': 'uncertain', 'updated_utc': '2026-10-10T10:09:00+00:00',
                       'retained_reserved_nanodollars': 1234}]
        original = self.write('original.json', self.spec)
        incident = self.write('incident.json', {
            'run_id': self.spec['run_id'], 'uncertain_holds': self.holds,
            'all_fourteen_uncertain_hold_nanodollars': 1234,
            'remaining_conditions_by_family': {'role_bound_association': self.subset}})
        action = self.write('action.json', {'financial_hold_release_nanodollars': 0})
        receipt = self.write('receipt.json', {
            'incident_sha256': digest(incident), 'action_sha256': digest(action),
            'released_nanodollars': 0, 'committed_before_nanodollars': 1234,
            'committed_after_nanodollars': 1234, 'all_fourteen_uncertain_hold_nanodollars': 1234,
            'applied_utc': '2026-10-10T10:37:00+00:00'})
        for field, path in [('original_validation_spec', original), ('incident', incident),
                            ('hold_action', action), ('hold_action_receipt', receipt)]:
            self.spec[field] = str(path)
            self.spec[field+'_sha256'] = digest(path)
        self.spec['recovery_condition_files'] = {}
        self.set_subset(self.subset)
        self.spec['stop_files'] = {'role_bound_association': str(self.root/'new-stop')}

    def write(self, name, value):
        path = self.root/name
        path.write_text(json.dumps(value))
        return path

    def set_subset(self, rows):
        path = self.write('remaining.json', rows)
        self.spec['recovery_condition_files']['role_bound_association'] = {
            'path': str(path), 'sha256': digest(path)}

    def preflight(self):
        # The reused original preflight owns cohort/gate/export/source checks.
        # These tests isolate the additional strict recovery boundary.
        with patch('infra.resume_validation_judges.preflight', return_value=self.signed):
            return preflight_recovery(self.spec, 'role_bound_association')

    def test_exact_remaining_suffix_accepted(self):
        self.assertEqual(self.preflight(), self.subset)

    def test_foreign_duplicate_out_of_order_or_incomplete_rejected(self):
        for rows in [[{'method': 'foreign', 'n': 32}], [self.subset[0]]*2,
                     list(reversed(self.subset)), self.subset[:2]]:
            with self.subTest(rows=rows):
                self.set_subset(rows)
                with self.assertRaises(ValueError): self.preflight()

    def test_wrong_file_hash_rejected(self):
        self.spec['recovery_condition_files']['role_bound_association']['sha256'] = '0'*64
        with self.assertRaises(ValueError): self.preflight()

    def test_original_cap_epoch_and_receipt_invariants_rejected(self):
        self.spec['run_cap_usd'] = 16
        with self.assertRaises(ValueError): self.preflight()
        self.spec['run_cap_usd'] = 15
        self.spec['recovery_epoch'] = '2026-10-10T10:20:00+00:00'
        with self.assertRaises(ValueError): self.preflight()

    def test_command_preserves_all_original_semantic_and_transport_arguments(self):
        before = evaluation_command(self.spec, 'role_bound_association')
        after = recovery_command(self.spec, 'role_bound_association')
        for flag in ('--condition-list', '--stop-file'):
            after[after.index(flag)+1] = before[before.index(flag)+1]
        self.assertEqual(before, after)

    def set_handoff(self):
        self.spec['status'] = 'root_reviewed_ready'
        prior = self.write('prior-recovery.json', self.spec)
        remaining = self.subset[-2:]
        record = self.write('boundary.json', {
            'no_hold_or_epoch_changes': True,
            'families': [{'family': 'role_bound_association', 'run_id': self.spec['run_id'],
                          'pid_exists': False, 'exclusive_cache_owner_released': True,
                          'completed_signed_count': len(self.signed)-2,
                          'signed_menu_count': len(self.signed),
                          'remaining_signed_conditions': remaining,
                          'total': {'active_reserved_nanodollars': 0},
                          'boundary_events': [{'status': 'condition_queue_stopped_at_boundary',
                                               'family': 'role_bound_association',
                                               'run_id': self.spec['run_id'],
                                               'next_condition': remaining[0]}]}]})
        self.spec['boundary_handoff'] = {
            'record': str(record), 'record_sha256': digest(record),
            'prior_recovery_spec': str(prior), 'prior_recovery_spec_sha256': digest(prior)}
        # Preserve the parent's dispatch artifact before preparing the new file.
        path = self.write('handoff-remaining.json', remaining)
        self.spec['recovery_condition_files'] = {'role_bound_association': {
            'path': str(path), 'sha256': digest(path)}}
        return remaining

    def test_clean_boundary_accepts_only_exact_unfinished_suffix(self):
        remaining = self.set_handoff()
        self.assertEqual(self.preflight(), remaining)
        for rows in [remaining[:1], self.subset, remaining[::-1],
                     [remaining[0]]*2, [{'method': 'foreign', 'n': 32}]]:
            with self.subTest(rows=rows):
                # Leave the prior source immutable: use only the handoff file.
                path = self.write('handoff-remaining.json', rows)
                self.spec['recovery_condition_files']['role_bound_association'] = {
                    'path': str(path), 'sha256': digest(path)}
                with self.assertRaises(ValueError): self.preflight()

    def test_handoff_requires_ready_hashes_and_unchanged_epoch(self):
        self.set_handoff()
        for field, value in [('status', 'prepared'),
                             ('recovery_epoch', '2026-10-10T11:40:00+00:00')]:
            old = self.spec[field]
            self.spec[field] = value
            with self.assertRaises(ValueError): self.preflight()
            self.spec[field] = old
        self.spec['boundary_handoff']['record_sha256'] = '0'*64
        with self.assertRaises(ValueError): self.preflight()

    def test_handoff_keeps_operational_arguments_and_epoch(self):
        before = recovery_command(self.spec, 'role_bound_association')
        self.set_handoff()
        after = recovery_command(self.spec, 'role_bound_association')
        after[after.index('--condition-list')+1] = before[before.index('--condition-list')+1]
        self.assertEqual(before, after)
        self.assertEqual(self.spec['recovery_epoch'], '2026-10-10T10:40:00+00:00')

    def test_live_holds_check_is_read_only_and_rejects_pending_transition(self):
        path = self.root/'ledger.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE run_limits(run_id TEXT PRIMARY KEY,cap INTEGER)')
            db.execute('CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY,status TEXT,reserved INTEGER,actual INTEGER)')
            db.execute('INSERT INTO run_limits VALUES (?,?)', (self.spec['run_id'], 15_000_000_000))
            db.execute("INSERT INTO attempts VALUES ('uncertain','unknown',1234,NULL)")
        self.spec['ledger'] = str(path)
        before = digest(path)
        check_retained_holds(self.spec)
        self.assertEqual(before, digest(path))
        with sqlite3.connect(path) as db:
            db.execute("UPDATE attempts SET status='reserved'")
        with self.assertRaises(ValueError): check_retained_holds(self.spec)


if __name__ == '__main__':
    unittest.main()
