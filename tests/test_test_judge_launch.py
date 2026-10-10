"""Offline TEST dispatch guards; synthetic metadata only, no model or API."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infra import launch_test_judges as launch


class TestJudgeLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.menu = [{'method': 'raw_n1', 'n': 1}, {'method': 'best_n_exact', 'n': 32}]
        self.manifest = {'frozen_test_authorized': True,
                         'cells': [{'cell_id': str(i), 'family': launch.FAMILIES[i % 4]}
                                   for i in range(10714)]}
        self.spec = {'concurrency': 8, 'rpm': 200, 'tier': 'default', 'reasoning_effort': 'none',
                     'automatic_ramp': False, 'authorized_cells': 10714,
                     'implementation_source_sha256': {}, 'run_cap_usd': 3,
                     'status': 'root_reviewed_ready', 'run_id': 'synthetic-test',
                     'cpu_pairs': {'hallucination': [0, 1]}, 'judgments': str(self.root/'judgments'),
                     'shared_cache': str(self.root/'cache'), 'ledger': str(self.root/'ledger'),
                     'performance_profile_dir': str(self.root/'profiles')}
        for field, value in [('manifest', self.manifest), ('fresh_manifest', {}),
                             ('conditions', self.menu), ('empirical_summary', {}), ('selections', [])]:
            self.bind(field, value)
        self.bind('freeze', {'status': 'root_reviewed_frozen', 'conditions': self.menu,
                             'conditions_sha256': self.spec['conditions_sha256']})
        self.gate = {'authorization_scope': 'analysis', 'frozen_test_authorized': True,
                     'condition_list_sha256': self.spec['conditions_sha256'],
                     'freeze_sha256': self.spec['freeze_sha256']}
        self.bind('gate', self.gate)
        self.export = {'status': 'complete_immutable_exact_text_projection',
                       'output_sha256': self.spec['selection_sha256'],
                       'manifest_sha256': self.spec['manifest_sha256'],
                       'dispatch_conditions_sha256': self.spec['conditions_sha256'],
                       'fresh_manifest_sha256': self.spec['fresh_manifest_sha256'],
                       'coordinator_gate_sha256': self.spec['gate_sha256'],
                       'cells': 10714, 'conditions': self.menu,
                       'condition_cell_counts': {r['method']+'-n'+str(r['n']):10714 for r in self.menu}}
        self.bind('export_provenance', self.export)
        self.bind('forecast', {'expected_charge_including_unknown_stage2_upper_using_empirical_means_usd': 1,
                               'manifest_sha256': self.spec['manifest_sha256'], 'conditions': self.menu,
                               'selection_sources': [{'path': self.spec['selections'],
                                                      'sha256': self.spec['selection_sha256']}],
                               'analysis_authorization': {'coordinator_gate_sha256': self.spec['gate_sha256']}})

    def bind(self, field, body):
        p = self.root/(field+'.json')
        p.write_text(json.dumps(body))
        self.spec[field] = str(p)
        # The selection digest has the established singular spelling.
        self.spec[('selection' if field == 'selections' else field)+'_sha256'] = launch.digest(p)

    def preflight(self):
        with patch.object(launch, 'evaluation_stage', return_value=(self.manifest, 'test', {}, {})):
            return launch.preflight(self.spec)

    def test_variable_signed_menu_accepted_and_fixed_transport(self):
        self.assertEqual(self.preflight(), self.menu)  # Two, rather than a hardcoded twelve.
        command = launch.evaluation_command(self.spec, 'hallucination')
        for flag, expected in [('--tier', 'default'), ('--concurrency', '8'), ('--rpm', '200'),
                               ('--run-cap-usd', '3'), ('--condition-list', self.spec['conditions'])]:
            self.assertEqual(command[command.index(flag)+1], expected)
        self.spec['concurrency'] = 16
        with self.assertRaises(ValueError): self.preflight()

    def test_blind_gate_rejected_before_export_or_forecast_access(self):
        self.gate['authorization_scope'] = 'blind_generation_only'
        self.bind('gate', self.gate)
        self.spec['selections'] = '/nonexistent/must-not-read'
        with self.assertRaisesRegex(ValueError, 'analysis authority'): self.preflight()

    def test_foreign_reordered_menu_and_wrong_export_identity_rejected(self):
        for rows in [[{'method': 'foreign', 'n': 32}], self.menu[::-1]]:
            self.bind('conditions', rows)
            with self.assertRaises(ValueError): self.preflight()
        self.bind('conditions', self.menu)
        self.export['conditions'] = self.menu[::-1]
        self.bind('export_provenance', self.export)
        with self.assertRaisesRegex(ValueError, 'projection'): self.preflight()

    def test_forecast_cap_and_source_hash_fail_closed(self):
        self.spec['run_cap_usd'] = 0.5
        with self.assertRaisesRegex(ValueError, 'ceiling'): self.preflight()
        self.spec['run_cap_usd'] = 3
        self.spec['freeze_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'hash'): self.preflight()

    def test_draft_missing_paid_flag_or_validate_only_never_spawns(self):
        p = self.root/'spec.json'
        for status, flags in [('prepared', ['--allow-paid']), ('root_reviewed_ready', []),
                              ('root_reviewed_ready', ['--allow-paid', '--validate-only'])]:
            p.write_text(json.dumps({'status': status}))
            with patch('sys.argv', ['launch', '--spec', str(p), '--family', 'hallucination']+flags), \
                 patch.object(launch, 'preflight'), patch.object(launch.subprocess, 'Popen') as worker, \
                 patch('builtins.print'):
                if '--validate-only' in flags: launch.main()
                else:
                    with self.assertRaises(SystemExit): launch.main()
                worker.assert_not_called()

    def test_verified_ready_launch_sets_frozen_flag_only_after_preflight(self):
        self.spec.update(job_id='synthetic-job', node='synthetic-node',
                         logs=str(self.root/'logs'), recovery_epoch='unchanged-reviewed-epoch')
        p = self.root/'spec.json'; p.write_text(json.dumps(self.spec))
        events = []
        def preflight(spec, **kwargs):
            events.append('preflight')
            return self.menu
        def spawn(*args, **kwargs):
            self.assertEqual(events, ['preflight'])
            self.assertEqual(kwargs['env']['OLENS_TEST_FROZEN'], '1')
            self.assertEqual(kwargs['env']['OLENS_TRANSPORT_RECOVERY_SINCE'],
                             'unchanged-reviewed-epoch')
            events.append('dispatch')
            return unittest.mock.Mock(pid=123, wait=lambda: 0)
        with patch('sys.argv', ['launch', '--spec', str(p), '--family', 'hallucination', '--allow-paid']), \
             patch.object(launch, 'preflight', side_effect=preflight), \
             patch.dict(launch.os.environ, {'SLURM_JOB_ID':'synthetic-job'}, clear=True), \
             patch.object(launch.socket, 'gethostname', return_value='synthetic-node'), \
             patch.object(launch.os, 'sched_getaffinity', return_value={0, 1}), \
             patch.object(launch.subprocess, 'Popen', side_effect=spawn), patch('builtins.print'):
            with self.assertRaises(SystemExit) as outcome: launch.main()
            self.assertEqual(outcome.exception.code, 0)
        self.assertEqual(events, ['preflight', 'dispatch'])


if __name__ == '__main__':
    unittest.main()
