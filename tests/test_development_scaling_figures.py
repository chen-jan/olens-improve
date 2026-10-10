import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import export_development_scaling_figures as figures


def fixture():
    metric = {'numerator': 2, 'denominator': 5, 'value': .4,
              'ci95': [.13, .71], 'independent_groups': 3,
              'warning': 'Few independent groups'}
    families = {}
    for family in figures.FAMILIES:
        cell = 'contradiction_rate' if family == 'hallucination' else 'cell_recovery'
        item = ('original_grid_contradiction_rate' if family == 'hallucination'
                else 'original_grid_item_pass_rate')
        families[family] = {'metrics': {cell: copy.deepcopy(metric)},
                            'original_grid_metrics': {item: copy.deepcopy(metric)}}
    return {'status': 'complete_four_family_development_scaling',
            'measurement': {'conditions': [
                {'condition': condition, 'measurement_complete': True,
                 'families': copy.deepcopy(families)} for condition in figures.ORDER]}}


class ScalingFigureTests(unittest.TestCase):
    def test_preserves_supplied_counts_interval_warning_without_mutating(self):
        source = fixture(); original = copy.deepcopy(source)
        result = figures.source_metrics(source, 'item')
        self.assertEqual(result['role_bound_association'][2]['metric'],
                         source['measurement']['conditions'][2]['families']
                         ['role_bound_association']['original_grid_metrics']
                         ['original_grid_item_pass_rate'])
        result['role_bound_association'][2]['metric']['ci95'][0] = .2
        self.assertEqual(source, original)

    def test_rejects_incomplete_or_wrong_order(self):
        source = fixture(); source['measurement']['conditions'][0]['measurement_complete'] = False
        with self.assertRaises(ValueError): figures.source_metrics(source, 'cell')
        source = fixture(); source['measurement']['conditions'].reverse()
        with self.assertRaises(ValueError): figures.source_metrics(source, 'cell')

    def test_undefined_rate_is_never_zero(self):
        source = fixture()
        source['measurement']['conditions'][2]['families']['hallucination']['metrics']['contradiction_rate']['value'] = None
        with self.assertRaisesRegex(ValueError, 'Undefined'):
            figures.source_metrics(source, 'cell')


if __name__ == '__main__': unittest.main()
