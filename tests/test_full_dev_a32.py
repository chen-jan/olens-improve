"""Reject partial stage coverage and mismatched paired evidence in the DEV panel."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('append_a32', ROOT / 'scripts/append_full_dev_a32.py')
append = importlib.util.module_from_spec(spec)
spec.loader.exec_module(append)


def fixture():
    arms, pairs, items = [], [], []
    for condition, value in [('capped_n1-n1', .2), ('best_n_exact-n32', .3)]:
        families = {}
        for family, (expected, groups) in append.FAMILIES.items():
            endpoint = 'contradiction_rate' if family == 'hallucination' else 'cell_recovery'
            metric = {'value': value, 'numerator': 2, 'denominator': 10, 'independent_groups': groups}
            families[family] = {'expected_cells': expected, 'missing_stage1': 0, 'missing_stage2': 0,
                                'metrics': {endpoint: metric},
                                'original_grid_metrics': {'original_grid_item_pass_rate': metric}}
            if condition == 'best_n_exact-n32':
                pair = {'family': family, 'endpoint': endpoint, 'baseline_condition': 'capped_n1-n1',
                        'condition': condition, 'baseline': .2, 'proposed': .3, 'delta': .1,
                        'ci95_delta': [-.1, .2], 'independent_groups': groups, 'warning': 'Synthetic'}
                pairs.append(pair)
                if family != 'hallucination':
                    items.append(dict(pair, endpoint='original_grid_item_pass_rate'))
        arms.append({'condition': condition, 'measurement_complete': True, 'families': families})
    return {'measurement': {'original_grid_contract': True, 'conditions': arms,
            'paired_comparisons': pairs, 'original_grid_paired_comparisons': items,
            'manifest_sha256': 'synthetic', 'bootstrap_replicates': 2000},
            'limits': [], 'selection_source': 'synthetic', 'selection_source_sha256': 'synthetic'}


class FullDevPanelTests(unittest.TestCase):
    def test_partial_stage_is_rejected(self):
        source = fixture()
        source['measurement']['conditions'][1]['families']['hallucination']['missing_stage2'] = 1
        with self.assertRaisesRegex(ValueError, 'coverage incomplete'):
            append.comparison(source, 'synthetic', 'synthetic')

    def test_pair_must_match_source_and_keep_grid_separate(self):
        source = fixture()
        result = append.comparison(source, 'synthetic', 'synthetic')
        self.assertEqual(len(result['cell_endpoints']), 4)
        self.assertEqual(len(result['original_item_endpoints']), 3)
        self.assertIn('capped single-sample baseline', result['title'])
        bad = copy.deepcopy(source)
        bad['measurement']['paired_comparisons'][0]['proposed'] = .5
        with self.assertRaisesRegex(ValueError, 'differs from source'):
            append.comparison(bad, 'synthetic', 'synthetic')


if __name__ == '__main__':
    unittest.main()
