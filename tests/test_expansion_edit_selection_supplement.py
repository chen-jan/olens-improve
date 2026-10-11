import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from summarize_expansion_edit_selection import describe_event, copied_fit_counts, sha_text


def event(round_number, selected, edits=()):
    a = {'candidate_id': 'c:initial:best_n_exact', 'origin': 'unchanged_parent', 'text': 'best'}
    d = {'candidate_id': 'c:initial:pooled_greedy_swap', 'origin': 'unchanged_parent', 'text': 'pool\n'}
    candidates = [a, d] + list(edits)
    return {'cell_id': 'c', 'round': round_number, 'candidates': candidates,
            'best': next(c for c in candidates if c['candidate_id'] == selected)}


class SelectionSupplement(unittest.TestCase):
    def test_r2_inherited_edit_is_not_new(self):
        edit = {'candidate_id': 'c:F:r1:p0', 'origin': 'editing_round1', 'text': 'edited',
                'parent_candidate_id': 'c:initial:pooled_greedy_swap'}
        first = event(1, edit['candidate_id'], [edit]); _, previous = describe_event(first, None, {edit['candidate_id']})
        second = event(2, edit['candidate_id'], [edit]); counts, _ = describe_event(second, previous, set())
        self.assertEqual(counts['selected_prior_round_edit'], 1)
        self.assertEqual(counts['selected_new_current_round_edit'], 0)
        self.assertEqual(counts['previous_round_byte_identical'], 1)
        with self.assertRaisesRegex(ValueError, 'terminal history'):
            second['best']['text'] = 'changed inherited text'
            describe_event(second, previous, set())

    def test_new_candidate_with_equal_text_has_distinct_counts(self):
        edit = {'candidate_id': 'c:F:r2:p0', 'origin': 'editing_round2', 'text': 'pool\n',
                'parent_candidate_id': 'c:initial:pooled_greedy_swap'}
        _, previous = describe_event(event(1, 'c:initial:pooled_greedy_swap'), None, set())
        counts, _ = describe_event(event(2, edit['candidate_id'], [edit]), previous, {edit['candidate_id']})
        self.assertEqual(counts['selected_new_current_round_edit'], 1)
        self.assertEqual(counts['pooled_parent_byte_identical'], 1)
        self.assertEqual(counts['previous_round_byte_identical'], 1)
        self.assertEqual(counts['selected_current_edit_actual_parent_changed_text'], 0)

    def test_exact_text_preserves_whitespace_and_rejects_wrong_origin(self):
        edit = {'candidate_id': 'c:F:r1:p0', 'origin': 'editing_round1', 'text': 'pool',
                'parent_candidate_id': 'c:initial:pooled_greedy_swap'}
        counts, _ = describe_event(event(1, edit['candidate_id'], [edit]), None, {edit['candidate_id']})
        self.assertEqual(counts['pooled_parent_changed_text'], 1)
        bad = event(1, edit['candidate_id'], [dict(edit, origin='unchanged_parent')])
        with self.assertRaisesRegex(ValueError, 'original eligible parent'): describe_event(bad, None, set())
        with self.assertRaisesRegex(ValueError, 'exact proposal'): describe_event(event(1, edit['candidate_id'], [edit]), None, set())

    def test_fit_counts_copy_existing_masks_and_preserve_unavailable(self):
        row = {'parent_comparisons': [
            {'reference': 'pooled_greedy_swap-n32', 'kind': 'editor_initial_reference', 'paired_sites': 7,
             'intended_paired_sites': 11, 'improved_sites': 2, 'worsened_sites': 0,
             'unchanged_or_within_numerical_tolerance': 5, 'site_change_equivalence_tolerance': 1e-5},
            {'reference': 'editing_round1-n32', 'kind': 'editor_previous_round_diagnostic',
             'paired_sites': 0, 'warning': 'No common valid reconstruction sites'}]}
        before = copy.deepcopy(row); got = copied_fit_counts(row, 3)
        self.assertEqual(row, before)
        self.assertEqual(got[0]['improved_sites'], 2)
        self.assertEqual(got[0]['source_row_index'], 3)
        self.assertNotIn('improved_sites', got[1])
        self.assertEqual(got[1]['paired_sites'], 0)


if __name__ == '__main__': unittest.main()
