"""Random controls retain full condition coverage when a prefix is ineligible."""
import importlib.util
from pathlib import Path
import random
import unittest

from olens_improve.selection import Sample, Bullet, best_of_n


spec = importlib.util.spec_from_file_location(
    'compare_selectors_coverage', Path(__file__).parents[1] / 'scripts/compare_selectors.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RandomConditionCoverageTests(unittest.TestCase):
    def test_ineligible_first_sample_keeps_all_nested_conditions(self):
        samples = [Sample('s0', 0, (Bullet('a', 'Fact A', 's0', 0),), flags=('preamble_before_first_bullet',))]
        samples += [Sample(f's{i}', i, (Bullet(str(i), f'Fact {i}', f's{i}', 0),))
                    for i in range(1, 32)]
        outputs = {}
        for n in (1, 2, 4, 8, 16, 32):
            rng = random.Random(123 + n)
            outputs[n] = module.random_complete_selection(samples, n, lambda _: True, rng)
            if n > 1:
                expected = random.Random(123 + n).choice(samples[1:n])
                self.assertEqual(outputs[n].phrase_ids, tuple(b.phrase_id for b in expected.bullets))
        self.assertEqual(set(outputs), {1, 2, 4, 8, 16, 32})
        self.assertEqual(outputs[1].text, '')
        self.assertEqual(outputs[1].reason, 'no_eligible_complete_sample')
        self.assertEqual(outputs[1].reason,
                         best_of_n(samples, 1, lambda _: 0., admissible=lambda _: True).reason)

    def test_admissibility_exclusion_also_emits_empty_control(self):
        sample = Sample('s', 0, (Bullet('a', 'Too long', 's', 0),))
        selected = module.random_complete_selection([sample], 1, lambda _: False, random.Random(7))
        self.assertEqual(selected.phrase_ids, ())
        self.assertEqual(selected.reason, 'no_eligible_complete_sample')


if __name__ == '__main__':
    unittest.main()
