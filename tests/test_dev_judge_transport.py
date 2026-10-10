import copy
import json
from pathlib import Path
import unittest

from infra import resume_main_judges as launch


class DevelopmentTransportTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(Path('configs/judging_dev12_remaining_role_v2.prepared.json').read_text())

    def higher(self):
        self.spec.update(concurrency=256, rpm=4000)
        self.spec['transport_review'] = {
            key: self.spec[key] for key in
            ('concurrency', 'rpm', 'tier', 'reasoning_effort', 'automatic_ramp', 'run_id', 'recovery_epoch')
        }
        self.spec['transport_review'].update(
            status='root_reviewed', profile='standard_none_256_4000_v1',
            family='role_bound_association', authority='Synthetic test only',
            reviewed_utc='2026-10-10T19:00:00Z')

    def test_only_transport_arguments_change(self):
        legacy = launch.evaluation_command(self.spec, 'role_bound_association', [13, 20])
        launch.validate_transport(self.spec)
        self.higher()
        launch.validate_transport(self.spec)
        higher = launch.evaluation_command(self.spec, 'role_bound_association', [13, 20])
        for flag, value in (('--concurrency', '256'), ('--rpm', '4000')):
            legacy[legacy.index(flag) + 1] = value
        self.assertEqual(legacy, higher)

    def test_foreign_family_epoch_or_missing_review_rejected(self):
        self.higher()
        good = copy.deepcopy(self.spec)
        changes = [
            lambda s: s.pop('transport_review'),
            lambda s: s['transport_review'].update(family='hallucination'),
            lambda s: s['transport_review'].update(recovery_epoch='new-epoch'),
            lambda s: s['transport_review'].update(run_id='another-run'),
            lambda s: s['transport_review'].update(authority=''),
            lambda s: s['cpu_pairs'].update(hallucination=[0, 3]),
        ]
        for change in changes:
            self.spec = copy.deepcopy(good)
            change(self.spec)
            with self.assertRaises(ValueError):
                launch.validate_transport(self.spec)

    def test_mixed_rates_tiers_and_ramping_rejected(self):
        self.higher()
        good = copy.deepcopy(self.spec)
        for changes in ({'rpm': 2400}, {'concurrency': 512}, {'concurrency': True},
                        {'tier': 'flex'}, {'reasoning_effort': 'medium'},
                        {'automatic_ramp': True}, {'automatic_ramp': 0}):
            self.spec = copy.deepcopy(good)
            self.spec.update(changes)
            self.spec['transport_review'].update(changes)
            with self.assertRaises(ValueError):
                launch.validate_transport(self.spec)


if __name__ == '__main__':
    unittest.main()
