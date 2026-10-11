import unittest
from olens_improve.expanded_statistics import analyze, grouped_draws


class ExpandedStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.groups = {str(i): str(i // 2) for i in range(40)}
        self.base = {str(i): [int(i % 3 == 0), 1] for i in range(40)}
        self.new = {str(i): [int(i % 3 == 0 or i % 5 == 0), 1] for i in range(40)}
        self.source = {'conditions': {'base': self.base, 'new': self.new}, 'group_of': self.groups}

    def test_point_is_ratio_of_sums_with_unequal_denominators(self):
        result = grouped_draws({'a': {'x': [1, 1], 'y': [0, 9]}}, {'x': 'g1', 'y': 'g2'}, replicates=200)
        self.assertAlmostEqual(result['point'][0], .1)
        self.assertEqual(result['groups'], 2)

    def test_pairing_and_direction_share_draws(self):
        result = analyze({'task': self.source}, [{'reference': 'base', 'condition': 'new'},
                                                {'reference': 'new', 'condition': 'base'}], replicates=1000)
        a, b = result['comparisons']
        self.assertAlmostEqual(a['delta'], -b['delta'])
        self.assertAlmostEqual(a['ci95_delta'][0], -b['ci95_delta'][1])
        self.assertEqual(a['independent_groups'], 20)
        self.assertLessEqual(a['simultaneous_ci95_delta'][0], a['ci95_delta'][0])
        self.assertGreaterEqual(a['simultaneous_ci95_delta'][1], a['ci95_delta'][1])

    def test_identity_warns_instead_of_claiming_robust_zero_uncertainty(self):
        result = analyze({'task': self.source}, [{'reference': 'base', 'condition': 'base'}], replicates=200)
        row = result['comparisons'][0]
        self.assertEqual(row['delta'], 0)
        self.assertIsNone(row['simultaneous_ci95_delta'])
        self.assertIn('Zero bootstrap variation', row['warning'])

    def test_incomplete_declared_family_does_not_get_simultaneous_interval(self):
        result = analyze({'task': self.source}, [{'reference': 'base', 'condition': 'new'},
                                                {'reference': 'base', 'condition': 'missing'}], replicates=200)
        self.assertFalse(result['comparison_family_complete'])
        self.assertEqual(len(result['missing_comparisons']), 1)
        self.assertIsNone(result['comparisons'][0]['simultaneous_ci95_delta'])

    def test_incomplete_item_cohort_is_rejected(self):
        with self.assertRaises(ValueError):
            grouped_draws({'base': self.base, 'bad': {'0': [1, 1]}}, self.groups, replicates=200)

    def test_undefined_denominator_does_not_become_a_success(self):
        result = grouped_draws({'blank': {'a': [0, 0]}}, {'a': 'one'}, replicates=200)
        self.assertNotEqual(result['point'][0], result['point'][0])

    def test_boundary_rate_has_visible_zero_variation_warning(self):
        source = {'conditions': {'perfect': {'a': [1, 1], 'b': [1, 1]}},
                  'group_of': {'a': 'g1', 'b': 'g2'}}
        result = analyze({'task': source}, [], replicates=200)
        metric = result['conditions']['task']['perfect']
        self.assertEqual(metric['ci95'], [1, 1])
        self.assertIn('Zero bootstrap variation', ' '.join(metric['warnings']))
        self.assertEqual(metric['bootstrap_replicates'], 200)

    def test_undefined_ratio_draws_are_disclosed(self):
        source = {'conditions': {'sparse': {'a': [1, 1], 'b': [0, 0]}},
                  'group_of': {'a': 'g1', 'b': 'g2'}}
        metric = analyze({'task': source}, [], replicates=200)['conditions']['task']['sparse']
        self.assertLess(metric['defined_draws'], metric['bootstrap_replicates'])
        self.assertIn('defined draws', ' '.join(metric['warnings']))

    def test_joint_effective_count_excludes_degenerate_contrasts(self):
        result = analyze({'task': self.source}, [{'reference': 'base', 'condition': 'new'},
                                                {'reference': 'base', 'condition': 'base'}], replicates=200)
        self.assertEqual(result['declared_contrasts'], 2)
        self.assertEqual(result['effective_non_degenerate_contrasts'], 1)
        self.assertEqual(result['joint_interval_contrasts'], 1)


if __name__ == '__main__':
    unittest.main()
