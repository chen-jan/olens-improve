"""Synthetic selector checks, not real-model or scientific validation."""

import unittest
from olens_improve.selection import (Bullet, Sample, best_of_n, exact_consensus,
                                     greedy_pool, parse_bullets, parse_strict_bullets,
                                     cap_sample, output_admissible, prune_leave_one_out)


def bullet(key, text=None, sample="s", position=0):
    return Bullet(key, text or key, sample, position)


class SelectionTests(unittest.TestCase):
    def test_parser_preserves_source_and_flags_uncertain_continuations(self):
        source = "- Alice  owns 17 books.\n  unexplained continuation\n2. Bob does not own books.\n"
        sample = parse_strict_bullets(source, "s0", 0)
        self.assertTrue(sample.parsing_uncertain)
        self.assertEqual(sample.bullets[0].text, "Alice  owns 17 books.")
        for value in sample.bullets:
            self.assertEqual(source[value.start:value.end], value.text)
        self.assertEqual(parse_strict_bullets("\n", "s", 0).flags, ("empty",))
        self.assertEqual(len(parse_bullets("\n".join(f"- {n}" for n in range(5)), "s", 0).bullets), 4)

    def test_primary_blocks_preserve_negation_continuations_verbatim(self):
        source = "- Alice owns books.\n  This does not establish that Bob owns them.\n### Explanation\n- Bob has 17 books."
        sample = parse_bullets(source, "s", 0)
        self.assertFalse(sample.parsing_uncertain)
        self.assertEqual(sample.parser_policy, "source_contiguous_dash_blocks_v1")
        self.assertEqual(sample.bullets[0].text, "Alice owns books.\n  This does not establish that Bob owns them.\n### Explanation\n")
        for value in sample.bullets:
            self.assertEqual(source[value.start:value.end], value.text)
        self.assertTrue(parse_bullets("Intro\n- Fact.", "s", 0).parsing_uncertain)

    def test_token_cap_drops_complete_tail_never_part_of_qualifier(self):
        source = "- Alice owns books.\n  Bob does not.\n- Bob owns seventeen books."
        sample = parse_bullets(source, "s", 0)
        # Synthetic counting callback checks the truncation rule; production
        # supplies the pinned Qwen tokenizer's exact token counter.
        capped = cap_sample(sample, len, max_output_tokens=40)
        self.assertEqual(len(capped.bullets), 1)
        self.assertIn("Bob does not.", capped.bullets[0].text)
        self.assertEqual(capped.bullets[0].text, sample.bullets[0].text)
        self.assertTrue(output_admissible(len, 40)(capped.bullets))
        self.assertFalse(output_admissible(len, 40)(sample.bullets))

    def test_nested_prefixes_tie_by_earliest_sample(self):
        samples = [Sample("late", 2, (bullet("c"),)), Sample("early", 0, (bullet("a"),)), Sample("middle", 1, (bullet("b"),))]
        scorer = lambda ids: {"a": 1, "b": 1, "c": 2}[ids[0]]
        self.assertEqual(best_of_n(samples, 1, scorer).phrase_ids, ("a",))
        self.assertEqual(best_of_n(samples, 2, scorer).phrase_ids, ("a",))
        self.assertEqual(best_of_n(samples, 3, scorer).phrase_ids, ("c",))
        with self.assertRaises(ValueError):
            best_of_n(samples, 33, scorer)

    def test_exact_votes_are_per_sample_and_do_not_merge_negation(self):
        samples = [Sample("one", 0, (bullet("a", "A owns 3", "one"), bullet("b", "A  owns 3", "one"))),
                   Sample("two", 1, (bullet("c", "A owns 3", "two"), bullet("d", "A does not own 3", "two")))]
        result = exact_consensus(samples, min_support_fraction=.75)
        self.assertEqual(result.phrase_ids, ("a",))
        self.assertEqual(result.trace[0]["support"], 2)
        self.assertEqual(result.bullets[0].text, "A owns 3")

    def test_incomplete_and_duplicate_pool_records_are_errors(self):
        sample = Sample("one", 0, (bullet("a"),))
        scorer = lambda ids: float(len(ids))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            best_of_n([sample], 2, scorer)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            best_of_n([Sample("missing_zero", 1, (bullet("b"),))], 1, scorer)
        duplicates = [[sample, Sample("one", 1, (bullet("b"),))],
                      [sample, Sample("two", 0, (bullet("b"),))]]
        for pool in duplicates:
            with self.assertRaisesRegex(ValueError, "duplicate"):
                best_of_n(pool, 1, scorer)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                exact_consensus(pool)

    def test_leave_one_out_recomputes_redundant_contributions(self):
        # a and b explain the same dimension; c explains a distinct dimension.
        scorer = lambda ids: float(bool(set(ids) & {"a", "b"})) + float("c" in ids)
        result = prune_leave_one_out([bullet("a"), bullet("b"), bullet("c")], scorer, maximum_loss=0)
        self.assertEqual(result.phrase_ids, ("b", "c"))
        self.assertEqual(result.score, 2)
        self.assertFalse(result.trace[-1]["accepted"])

    def test_nonnegative_zero_gain_does_not_pack_redundant_bullets(self):
        scorer = lambda ids: float(bool(ids))
        result = greedy_pool([bullet("a"), bullet("b")], scorer)
        self.assertEqual(result.phrase_ids, ("a",))
        self.assertEqual(result.score, 1)

    def test_real_tiny_nnls_refits_redundant_columns(self):
        import numpy as np
        from scipy.optimize import nnls
        vectors = {"a": np.array([1., 0.]), "duplicate": np.array([1., 0.]), "c": np.array([0., 1.])}
        target = np.ones(2)

        def score(ids):
            if not ids:
                return 0.
            _, residual = nnls(np.stack([vectors[key] for key in ids], axis=1), target)
            return 1. - residual ** 2 / 2.

        pool = [bullet("a"), bullet("duplicate"), bullet("c")]
        result = greedy_pool(pool, score)
        self.assertEqual(result.phrase_ids, ("a", "c"))
        self.assertAlmostEqual(result.score, 1.)
        pruned = prune_leave_one_out(pool, score, maximum_loss=0)
        self.assertEqual(pruned.phrase_ids, ("duplicate", "c"))

    def test_fallback_cannot_restore_ineligible_claim(self):
        scorer = lambda ids: 10.0 if "bad" in ids else float(bool(ids))
        samples = [Sample("s", 0, (bullet("good"), bullet("bad")))]
        result = greedy_pool([bullet("good"), bullet("bad")], scorer,
                             eligible_ids={"good"}, complete_samples=samples)
        self.assertEqual(result.phrase_ids, ("good",))

    def test_complete_fallback_recovers_non_greedy_joint_solution(self):
        values = {frozenset(): 0, frozenset({"a"}): 3, frozenset({"b"}): 2,
                  frozenset({"c"}): 2, frozenset({"a", "b"}): 4,
                  frozenset({"a", "c"}): 4, frozenset({"b", "c"}): 7}
        scorer = lambda ids: values[frozenset(ids)]
        pool = [bullet("a"), bullet("b"), bullet("c")]
        complete = [Sample("pair", 0, (pool[1], pool[2]))]
        result = greedy_pool(pool, scorer, max_bullets=2, complete_samples=complete)
        self.assertEqual(result.phrase_ids, ("b", "c"))
        self.assertEqual(result.trace[-1]["action"], "complete_sample_fallback")
        swapped = greedy_pool(pool, scorer, max_bullets=2, swap_passes=1)
        self.assertEqual(set(swapped.phrase_ids), {"b", "c"})

    def test_output_admissibility_applies_to_additions_and_fallback(self):
        a, b = bullet("a", "longer"), bullet("b", "short")
        scorer = lambda ids: float(len(ids))
        limit = lambda values: sum(len(v.text) for v in values) <= 6
        result = greedy_pool([a, b], scorer, admissible=limit,
                             complete_samples=[Sample("both", 0, (a, b))])
        self.assertEqual(result.phrase_ids, ("a",))


if __name__ == "__main__":
    unittest.main()
