"""Reviewed TEST transport changes; synthetic authorities and no SDK/ledger."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

from infra import launch_test_judges as launch
from infra import launch_validation_judges as validation
from tests import test_test_judge_launch as fixtures


class TestJudgeTransportTests(unittest.TestCase):
    setUp = fixtures.TestJudgeLaunchTests.setUp
    bind = fixtures.TestJudgeLaunchTests.bind

    def prepare_transport(self):
        self.spec.update(concurrency=16, rpm=400, recovery_epoch='unchanged-guard-epoch',
                         planned_forecast_path=str(self.root/'new-forecast.json'))
        self.spec['transport_review'] = {
            'status': 'root_reviewed', 'profile': 'standard_none_16_400_v1',
            'family': 'hallucination', 'run_id': self.spec['run_id'],
            'recovery_epoch': self.spec['recovery_epoch'], 'concurrency': 16, 'rpm': 400,
            'tier': 'default', 'reasoning_effort': 'none', 'automatic_ramp': False,
            'reviewed_utc': '2026-10-10T18:00:00+00:00',
            'authority': 'Synthetic root authorization for one clean-boundary family.'}

    def preflight(self, family=None):
        with patch.object(launch, 'evaluation_stage', return_value=(self.manifest, 'test', {}, {})):
            return launch.preflight(self.spec, family=family)

    def assert_flags(self, argv, concurrency, rpm):
        for flag, expected in [('--concurrency', concurrency), ('--rpm', rpm)]:
            self.assertEqual(argv[argv.index(flag)+1], expected)

    def test_legacy_preflight_and_both_actual_commands_remain_8_200(self):
        self.spec['planned_forecast_path'] = str(self.root/'forecast-next.json')
        self.assertEqual(self.preflight('hallucination'), self.menu)
        self.assert_flags(launch.evaluation_command(self.spec, 'hallucination'), '8', '200')
        self.assert_flags(launch.forecast_command(self.spec), '8', '200')

    def test_reviewed_16_400_passes_and_commands_preserve_other_arguments(self):
        baseline = launch.evaluation_command(self.spec, 'hallucination')
        self.prepare_transport()
        before = copy.deepcopy(self.spec)
        self.assertEqual(self.preflight('hallucination'), self.menu)
        argv = launch.evaluation_command(self.spec, 'hallucination')
        self.assert_flags(argv, '16', '400')
        self.assert_flags(launch.forecast_command(self.spec), '16', '400')
        # Actual judge arguments change only these two reviewed values.
        for flag in ('--concurrency', '--rpm'):
            baseline[baseline.index(flag)+1] = argv[argv.index(flag)+1]
        self.assertEqual(argv, baseline)
        self.assertEqual(self.spec, before)

    def test_missing_or_unreviewed_authority_rejected_before_stage_data(self):
        self.prepare_transport()
        good = copy.deepcopy(self.spec)
        for change in [lambda s: s.pop('transport_review'),
                       lambda s: s['transport_review'].update(status='prepared'),
                       lambda s: s['transport_review'].update(authority=''),
                       lambda s: s['transport_review'].update(reviewed_utc='')]:
            with self.subTest(change=change):
                self.spec = copy.deepcopy(good); change(self.spec)
                with patch.object(launch, 'evaluation_stage') as stage:
                    with self.assertRaisesRegex(ValueError, 'profile authority'):
                        launch.preflight(self.spec, family='hallucination')
                    stage.assert_not_called()

    def test_review_binds_family_run_epoch_and_exact_profile_values(self):
        self.prepare_transport()
        good = copy.deepcopy(self.spec)
        for key, value in [('run_id', 'foreign-run'), ('recovery_epoch', 'new-epoch'),
                           ('profile', 'any-faster-profile'), ('concurrency', 32),
                           ('rpm', 600), ('tier', 'flex'), ('reasoning_effort', 'medium'),
                           ('automatic_ramp', True), ('family', 'foreign-family')]:
            with self.subTest(key=key):
                self.spec = copy.deepcopy(good); self.spec['transport_review'][key] = value
                with self.assertRaises(ValueError): launch.validate_transport(self.spec, 'hallucination')
        self.spec = good
        with self.assertRaisesRegex(ValueError, 'one reviewed family'):
            launch.validate_transport(self.spec, 'role_bound_association')

    def test_mixed_profiles_and_automatic_ramp_cannot_widen_silently(self):
        for concurrency, rpm, ramp in [(16, 200, False), (8, 400, False), (32, 600, False),
                                        (8, 200, True), (8, 200, 0), (8, True, False)]:
            with self.subTest(concurrency=concurrency, rpm=rpm, ramp=ramp):
                self.spec.update(concurrency=concurrency, rpm=rpm, automatic_ramp=ramp)
                with self.assertRaises(ValueError): launch.validate_transport(self.spec)

    def test_validation_preflight_still_rejects_higher_transport_before_data(self):
        self.prepare_transport()
        with patch.object(validation, 'evaluation_stage') as stage:
            with self.assertRaisesRegex(ValueError, 'fixed VAL policy'):
                validation.preflight(self.spec)
            stage.assert_not_called()

    def test_real_main_generates_16_400_and_keeps_guard_before_fake_spawn(self):
        self.prepare_transport()
        self.spec.update(job_id='synthetic-job', node='synthetic-node', logs=str(self.root/'logs'))
        p = self.root/'spec.json'; p.write_text(json.dumps(self.spec))
        def spawn(argv, **kwargs):
            self.assert_flags(argv, '16', '400')
            self.assertEqual(argv[argv.index('--tier')+1], 'default')
            self.assertEqual(argv[argv.index('--ledger')+1], self.spec['ledger'])
            self.assertEqual(argv[argv.index('--run-cap-usd')+1], '3')
            self.assertEqual(kwargs['env']['OLENS_TRANSPORT_RECOVERY_SINCE'], 'unchanged-guard-epoch')
            self.assertEqual(kwargs['env']['OLENS_TEST_FROZEN'], '1')
            return Mock(pid=123, wait=lambda: 0)
        with patch('sys.argv', ['launch', '--spec', str(p), '--family', 'hallucination', '--allow-paid']), \
             patch.object(launch, 'evaluation_stage', return_value=(self.manifest, 'test', {}, {})), \
             patch.dict(launch.os.environ, {'SLURM_JOB_ID': 'synthetic-job'}, clear=True), \
             patch.object(launch.socket, 'gethostname', return_value='synthetic-node'), \
             patch.object(launch.os, 'sched_getaffinity', return_value={0, 1}), \
             patch.object(launch.subprocess, 'Popen', side_effect=spawn) as worker, patch('builtins.print'):
            with self.assertRaises(SystemExit) as outcome: launch.main()
            self.assertEqual(outcome.exception.code, 0)
            worker.assert_called_once()

    def test_foreign_family_actual_main_never_spawns(self):
        self.prepare_transport()
        p = self.root/'spec.json'; p.write_text(json.dumps(self.spec))
        with patch('sys.argv', ['launch', '--spec', str(p), '--family', 'role_bound_association', '--allow-paid']), \
             patch.object(launch, 'evaluation_stage') as stage, patch.object(launch.subprocess, 'Popen') as worker:
            with self.assertRaisesRegex(ValueError, 'one reviewed family'): launch.main()
            stage.assert_not_called(); worker.assert_not_called()


if __name__ == '__main__':
    unittest.main()
