"""Small source/behavior fixtures; never scan production input."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from summarize_target_only_behavior import Behavior, checked_rows, fitted_parents
from merge_target_only_search import Sources, sha


def selection(text='new', k=1, fve=.4):
    return {'method': 'repeat_swap', 'n': 32, 'text': text, 'bullet_count': k,
        'token_count': 20, 'phrase_ids': ['a'] if k else [],
        'fits': {'exact': {'fve': fve}}, 'stop_flags': ['fit_budget', 'fit_budget'],
        'budget': {'subset_fits': 11},
        'trace': [{'action': 'prune', 'scope': 'cached_parent_fallback'}]}


class BehaviorTests(unittest.TestCase):
    def test_final_same_count_substitution_and_selected_truncation(self):
        b = Behavior()
        atoms = {'a': {'original_token_count': 33, 'truncated': True, 'scored_token_ids': list(range(32))},
            'unused': {'original_token_count': 100, 'truncated': True}}
        b.add(selection(), {'text': 'old', 'bullet_count': 1, 'token_count': 10, 'fve': .3}, atoms)
        r = b.result()
        self.assertEqual(r['counts']['same_bullet_count_different_text'], 1)
        self.assertEqual(r['counts']['fewer_bullets'], 0)
        self.assertEqual(r['counts']['selected_truncated_ar_bullets'], 1)
        self.assertEqual(r['stop_flag_output_counts'], {'fit_budget': 1})
        self.assertAlmostEqual(r['saved_numeric_fields']['paired_exact_fve_delta']['mean'], .1)

    def test_empty_has_no_truncation_denominator(self):
        b = Behavior()
        b.add(selection('', 0, 0), {'text': 'old', 'bullet_count': 1, 'token_count': 10, 'fve': .3}, {})
        self.assertIsNone(b.result()['selected_truncated_ar_bullet_proportion'])
        self.assertEqual(b.result()['counts']['fewer_bullets'], 1)

    def test_inconsistent_ar_metadata_fails(self):
        b = Behavior()
        with self.assertRaises(ValueError):
            b.add(selection(), {'text': '', 'bullet_count': 0, 'token_count': 0, 'fve': 0},
                {'a': {'original_token_count': 33, 'truncated': False, 'scored_token_ids': list(range(32))}})

    def test_partial_rows_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'rows.jsonl'
            path.write_text('')
            d = {'family': 'hallucination', 'selections': str(path)}
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                list(checked_rows(d, {'repeat_swap-n32'}, {'c': {'family': 'hallucination'}}, 'seal'))

    def test_fitted_parent_hash_and_missing_cohort_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'rows.jsonl'
            path.write_text('')
            d = {'source_parents': [{'path': str(path), 'sha256': sha(path)}]}
            with self.assertRaisesRegex(ValueError, 'Incomplete fitted'):
                fitted_parents({'d': d}, {'repeat_swap-n32'}, Sources(), {'c': {}})
            d['source_parents'][0]['sha256'] = 'stale'
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                fitted_parents({'d': d}, {'repeat_swap-n32'}, Sources(), {})


if __name__ == '__main__':
    unittest.main()
