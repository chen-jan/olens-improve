"""Invalid cleaned text stays visible; no placeholder is treated as evidence."""
import importlib.util
from pathlib import Path
import random
import unittest
from olens_improve.reconstruction import ar_token_ids, JointNNLS
from olens_improve.selection import parse_bullets, Selection, best_of_n, greedy_pool

spec = importlib.util.spec_from_file_location('selector_invalid_fixture',
        Path(__file__).parents[1]/'scripts/compare_selectors.py')
selector = importlib.util.module_from_spec(spec); spec.loader.exec_module(selector)


class Tokens:
    all_special_ids = [9]
    def __call__(self, text, **_):
        return {'input_ids': [] if not text.strip() else [9] if text == '<special>' else [1]}


class InvalidCandidateTests(unittest.TestCase):
    def fixture(self):
        import torch
        raw = '- <think></think>\n- Alice does not own 17 books.\n'
        invalid = parse_bullets(raw, 's0', 0)
        valid = parse_bullets('- Alice does not own 17 books.\n', 's1', 1)
        vectors = {invalid.bullets[1].phrase_id: torch.tensor([1., 0.]),
                   valid.bullets[0].phrase_id: torch.tensor([1., 0.])}
        exact = JointNNLS(torch.tensor([1., 0.]), vectors)
        released = JointNNLS(torch.tensor([1., 0.]), vectors, solver='released80')
        return raw, invalid, valid, exact, released

    def test_cleanup_empty_and_special_only_are_not_defined_vectors(self):
        for text in (' ', '<think></think>', '<special>'):
            self.assertEqual(ar_token_ids(Tokens(), text)[1], [])

    def test_baseline_and_random_text_unchanged_fit_unavailable(self):
        raw, invalid, _, exact, released = self.fixture()
        baseline = Selection('capped_n1', invalid.bullets, None)
        self.assertEqual(baseline.text, raw)
        self.assertEqual(selector.selection_fits(baseline, exact, released),
                         (None, 'unavailable_AR_empty_after_cleanup'))
        random_control = selector.random_complete_selection([invalid], 1, lambda _: True, random.Random(2))
        self.assertEqual(random_control.text, raw)
        self.assertEqual(selector.selection_fits(random_control, exact, released)[0], None)

    def test_complete_selection_excludes_invalid_not_falsely_zero_scores(self):
        _, invalid, valid, exact, _ = self.fixture()
        allowed = lambda bullets: selector.ar_scoreable(bullets, exact.vectors)
        first = best_of_n([invalid, valid], 1, exact.score, admissible=allowed)
        self.assertEqual(first.phrase_ids, ())
        winner = best_of_n([invalid, valid], 2, exact.score, admissible=allowed)
        self.assertEqual(winner.phrase_ids, valid.bullets and tuple(b.phrase_id for b in valid.bullets))

    def test_pool_keeps_valid_atoms_but_never_partial_complete_fallback(self):
        _, invalid, valid, exact, _ = self.fixture()
        bullets, fallback = selector.pool_candidates([invalid, valid], 2, exact.vectors)
        self.assertEqual(len(bullets), 1)
        self.assertEqual([s.index for s in fallback], [1])
        pooled = greedy_pool(bullets, exact.score, complete_samples=fallback)
        self.assertAlmostEqual(pooled.score, 1.)

    def test_unscoreable_parent_filters_are_explicit_noop_and_empty_set_zero(self):
        raw, invalid, _, exact, released = self.fixture()
        parent = Selection('capped_n1', invalid.bullets, None)
        for selection in (selector.prune_parent(parent, exact, .005),
                          selector.coefficient_parent(parent, exact, .05)):
            self.assertEqual(selection.text, raw)
            self.assertEqual(selection.reason, 'unavailable_parent_AR')
        empty = Selection('empty', (), None)
        fits, scope = selector.selection_fits(empty, exact, released)
        self.assertEqual(scope, 'emitted_bullets'); self.assertEqual(fits['exact']['fve'], 0.)


if __name__ == '__main__': unittest.main()
