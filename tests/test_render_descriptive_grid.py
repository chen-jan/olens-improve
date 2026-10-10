"""Rendering must retain endpoint denominators and the DEV/VAL boundary."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'render_descriptive_grid', Path(__file__).parents[1] / 'scripts/render_descriptive_grid.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RenderingContractTests(unittest.TestCase):
    def test_actual_denominator_not_intended_site_count(self):
        self.assertEqual(module.count_label({'numerator': 12, 'denominator': 28,
                                            'value': 12 / 28}), '43%\n12/28')

    def test_undefined_is_not_zero(self):
        self.assertIsNone(module.count_label({'numerator': 0, 'denominator': 0, 'value': None}))
        with self.assertRaises(ValueError):
            module.count_label({'numerator': 1, 'denominator': 4, 'value': 0})

    def test_test_rejected_before_any_rendering(self):
        with self.assertRaisesRegex(ValueError, 'TEST is closed'):
            module.validate_artifact({'stages': [{'stage': 'test'}]})


if __name__ == '__main__':
    unittest.main()
