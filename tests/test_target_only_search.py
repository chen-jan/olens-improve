"""Tiny CPU checks of bounded target-only search, independent of benchmark data."""
import unittest
import importlib.util
from pathlib import Path
import hashlib
import tempfile

from olens_improve.selection import Bullet
from olens_improve.target_only_search import SearchConfig, SubsetFitMeter, search_target_only


def bullets(*keys):
    return tuple(Bullet(k, k, "sample", i) for i, k in enumerate(keys))


class TargetOnlySearchTests(unittest.TestCase):
    def run_search(self, pool, parent, score, method="repeat_swap", **kwargs):
        return search_target_only(pool, parent, score,
                                  config=SearchConfig(method, **kwargs))

    def test_repeated_swaps_converge_beyond_first_swap(self):
        pool = bullets("a", "b", "c", "d")
        values = {frozenset(): 0, frozenset("ab"): .1, frozenset("bc"): .2,
                  frozenset("ac"): .15, frozenset("ad"): .12,
                  frozenset("bd"): .13, frozenset("cd"): .4}
        values.update({frozenset(k): .01 for k in "abcd"})
        result = self.run_search(pool, pool[:2], lambda ids: values[frozenset(ids)])
        self.assertEqual(set(result.selection.phrase_ids), {"c", "d"})
        self.assertEqual(sum(t["action"] == "swap" for t in result.selection.trace), 2)
        self.assertIn("swap_local_optimum", result.stop_flags)

    def test_canonical_meter_deduplicates_permutations(self):
        calls = []
        meter = SubsetFitMeter(lambda ids: calls.append(ids) or .5, 16)
        self.assertEqual(meter.fit(("b", "a")), meter.fit(("a", "b")))
        self.assertEqual(calls, [("a", "b")])
        self.assertEqual(meter.summary()["subset_fits"], 1)

    def test_pruning_threshold_is_strict_and_never_restores_superset(self):
        pool = bullets("a", "weak")
        score = lambda ids: .5 * ("a" in ids) + .004 * ("weak" in ids)
        result = self.run_search(pool, pool, score, "bounded_prune_refill_005")
        self.assertEqual(result.selection.phrase_ids, ("a",))
        self.assertEqual(result.leave_one_out, {"a": .5})
        self.assertLess(result.selection.score, score(("a", "weak")))
        self.assertIn("round_fixed_point", result.stop_flags)

    def test_exact_threshold_bullet_removed(self):
        pool = bullets("threshold")
        result = self.run_search(pool, pool, lambda ids: .005 if ids else 0.,
                                 "repeat_swap_then_prune_005")
        self.assertEqual(result.selection.phrase_ids, ())

    def test_threshold_tolerance_matches_existing_deletion_rule(self):
        pool = bullets("boundary")
        near = self.run_search(pool, pool, lambda ids: .005 + 1e-9 if ids else 0.,
                               "repeat_swap_then_prune_005")
        above = self.run_search(pool, pool, lambda ids: .005 + 2e-8 if ids else 0.,
                                "repeat_swap_then_prune_005")
        self.assertEqual(near.selection.phrase_ids, ())
        self.assertEqual(above.selection.phrase_ids, ("boundary",))

    def test_swap_then_prune_is_terminal_deletion_not_best_old_pruned_parent(self):
        pool = bullets("a", "b", "c")
        values = {frozenset(): 0., frozenset("a"): .6, frozenset("b"): .5,
                  frozenset("c"): .996, frozenset("ab"): .999,
                  frozenset("bc"): .9995, frozenset("ac"): .9991,
                  frozenset("abc"): 1.}
        score = lambda ids: values[frozenset(ids)]
        pruned = self.run_search(pool, pool[:2], score, "repeat_swap_then_prune_005")
        bounded = self.run_search(pool, pool[:2], score, "bounded_prune_refill_005")
        self.assertEqual(pruned.selection.phrase_ids, ("c",))
        self.assertEqual(pruned.leave_one_out, {"c": .996})
        self.assertEqual(bounded.selection.phrase_ids, ("a", "b"))

    def test_prune_refill_validates_all_retained_bullets(self):
        # Adding c makes redundant a/b. Prune both from the trial, then keep c/d.
        pool = bullets("a", "b", "c", "d")
        def score(ids):
            own = set(ids)
            return (.4 if "c" in own else .1 * len(own & {"a", "b"})) + .2 * ("d" in own)
        result = self.run_search(pool, pool[:2], score, "bounded_prune_refill_005")
        self.assertEqual(set(result.selection.phrase_ids), {"c", "d"})
        self.assertTrue(all(v > .005 for v in result.leave_one_out.values()))
        self.assertEqual(set(result.leave_one_out), set(result.selection.phrase_ids))
        # Its accepted swap/refill states never cycle.
        states = [tuple(sorted(t["to"])) for t in result.selection.trace if t["action"] in {"swap", "refill"}]
        self.assertEqual(len(states), len(set(states)))

    def test_budget_exhaustion_retains_validated_nonempty_parent(self):
        pool = bullets("parent", *(f"x{i}" for i in range(30)))
        score = lambda ids: .5 * ("parent" in ids) + .001 * len(set(ids) - {"parent"})
        for method in ("repeat_swap_then_prune_005", "bounded_prune_refill_005"):
            with self.subTest(method=method):
                result = self.run_search(pool, pool[:1], score, method, subset_fit_budget=16)
                self.assertEqual(result.selection.phrase_ids, ("parent",))
                self.assertLessEqual(result.budget["subset_fits"], 16)
                self.assertGreater(result.leave_one_out["parent"], .005)
                self.assertTrue(any("budget" in flag for flag in result.stop_flags))

    def test_partial_scan_accepts_best_seen_swap_and_marks_stop(self):
        pool = bullets("a", *(f"x{i}" for i in range(30)))
        score = lambda ids: 0. if not ids else (1. if ids[0].startswith("x") else .1)
        result = self.run_search(pool, pool[:1], score, subset_fit_budget=32)
        self.assertEqual(result.selection.phrase_ids, ("x0",))
        self.assertEqual(result.budget["subset_fits"], 18)
        self.assertIn("swap_budget_reserved_for_pruning", result.stop_flags)
        self.assertFalse(next(t for t in result.selection.trace if t["action"] == "swap")["neighborhood_complete"])

    def test_max_steps_and_caps_are_explicit(self):
        pool = bullets("a", "b", "c")
        score = lambda ids: sum({"a": .1, "b": .2, "c": .3}[k] for k in ids)
        stopped = self.run_search(pool, pool[:1], score, max_swap_steps=0)
        self.assertEqual(stopped.selection.phrase_ids, ("a",))
        self.assertIn("max_swap_steps", stopped.stop_flags)
        result = search_target_only(pool, pool[:1], score,
            config=SearchConfig("bounded_prune_refill_005"), admissible=lambda state: len(state) <= 1)
        self.assertEqual(result.selection.phrase_ids, ("c",))

    def test_empty_parent_may_refill_but_is_not_force_filled(self):
        pool = bullets("a", "b", "c", "d")
        result = self.run_search(pool, (), lambda ids: .2 * bool(ids), "bounded_prune_refill_005")
        self.assertEqual(result.selection.phrase_ids, ("a",))

    def test_earliest_candidate_wins_equal_swap_scores(self):
        pool = bullets("a", "c", "b")
        result = self.run_search(pool, pool[:1], lambda ids: 0. if not ids else (.1 if "a" in ids else .5))
        self.assertEqual(result.selection.phrase_ids, ("c",))

    def test_swap_parent_identical_for_pruning_ablation_at_budget_stop(self):
        pool = bullets("a", *(f"x{i}" for i in range(30)))
        score = lambda ids: 0. if not ids else (.1 if "a" in ids else .5)
        plain = self.run_search(pool, pool[:1], score, subset_fit_budget=32)
        pruned = self.run_search(pool, pool[:1], score, "repeat_swap_then_prune_005", subset_fit_budget=32)
        self.assertEqual(plain.selection.phrase_ids, pruned.refined_phrase_ids)
        self.assertEqual(plain.refined_phrase_ids, pruned.refined_phrase_ids)
        self.assertEqual(plain.budget["swap_phase_fit_limit"], pruned.budget["swap_phase_fit_limit"])

    def test_real_small_nnls_bounded_search(self):
        import numpy as np
        from scipy.optimize import nnls
        pool = bullets("a", "duplicate", "b", "weak")
        vectors = {"a": [1., 0., 0.], "duplicate": [1., 0., 0.],
                   "b": [0., 1., 0.], "weak": [0., 0., 1.]}
        target = np.array([1., 1., .01])
        calls = []
        def score(ids):
            calls.append(ids)
            if not ids:
                return 0.
            _, residual = nnls(np.array([vectors[k] for k in ids]).T, target)
            return 1. - residual ** 2 / (target @ target)
        result = self.run_search(pool, pool, score, "bounded_prune_refill_005")
        self.assertEqual(len(result.selection.bullets), 2)
        self.assertIn("b", result.selection.phrase_ids)
        self.assertNotIn("weak", result.selection.phrase_ids)
        self.assertTrue(all(v > .005 for v in result.leave_one_out.values()))
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(len(calls), result.budget["subset_fits"])

    def test_invalid_pools_configs_and_scores_fail_closed(self):
        a, = bullets("a")
        with self.assertRaises(ValueError):
            self.run_search((a, a), (a,), lambda ids: 0.)
        with self.assertRaises(ValueError):
            self.run_search((a,), (a,), lambda ids: float("nan"))
        with self.assertRaises(ValueError):
            SearchConfig("bounded_prune_refill_005", max_rounds=3)
        with self.assertRaises(ValueError):
            SearchConfig("repeat_swap", subset_fit_budget=15)


class TargetOnlyRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("target_only_runner", Path(__file__).parents[1] / "scripts/run_target_only_search.py")
        cls.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.runner)

    def test_pilot_metadata_coverage_is_staged_and_varied(self):
        cells = {}
        for stage in ("development", "validation", "test"):
            for family in ("a", "b", "c", "d"):
                for layer in range(20, 64, 4):
                    cid = f"{stage}:{family}:{layer}"
                    cells[cid] = {"split": stage, "family": family, "layer": layer}
        selected = self.runner.pilot_targets(cells, 12)
        self.assertEqual(len(selected), 12)
        self.assertEqual(len({(cells[c]["split"], cells[c]["family"]) for c in selected}), 12)
        self.assertGreater(len({cells[c]["layer"] for c in selected}), 1)
        self.assertEqual(selected, self.runner.pilot_targets(cells, 12))

    def test_four_arm_export_matches_random_deletion_and_reuses_exact_parent(self):
        import torch
        pool = bullets("a", "weak", "b", "duplicate")
        vectors = {"a": torch.tensor([1., 0., 0.]), "weak": torch.tensor([0., 0., 1.]),
                   "b": torch.tensor([0., 1., 0.]), "duplicate": torch.tensor([1., 0., 0.])}
        target = torch.tensor([1., 1., .01])
        output = self.runner.evaluate_target(pool, pool[:2], target, vectors, count=len,
                                             cell_id="synthetic", subset_fit_budget=32)
        by_method = {r["method"]: r for r in output}
        self.assertEqual(set(by_method), set(self.runner.METHODS) | {self.runner.RANDOM_METHOD})
        plain = by_method["repeat_swap"]
        pruned = by_method["repeat_swap_then_prune_005"]
        random = by_method[self.runner.RANDOM_METHOD]
        self.assertEqual(pruned["parent_phrase_ids"], plain["phrase_ids"])
        self.assertEqual(random["parent_phrase_ids"], plain["phrase_ids"])
        self.assertEqual(random["bullet_count"], pruned["bullet_count"])
        self.assertTrue(set(random["phrase_ids"]).issubset(plain["phrase_ids"]))
        again = self.runner.evaluate_target(pool, pool[:2], target, vectors, count=len,
                                            cell_id="synthetic", subset_fit_budget=32)
        self.assertEqual(random["phrase_ids"], again[-1]["phrase_ids"])
        for method in self.runner.METHODS:
            row = by_method[method]
            self.assertLessEqual(row["budget"]["subset_fits"], 32)
            self.assertEqual(set(row["fits"]["exact"]["atom_ids"]), set(row["phrase_ids"]))
            if row["leave_one_out"] is not None:
                self.assertTrue(all(g > .005 + 1e-8 for g in row["leave_one_out"].values()))

    def test_prepare_target_maps_parent_by_verbatim_text_and_batches_cache_rows(self):
        import torch
        from safetensors.torch import save_file
        from olens_improve.reconstruction import Whitener
        runner = self.runner
        class Tokenizer:
            all_special_ids = []
            def __call__(self, text, **kwargs):
                return {"input_ids": [ord(c) for c in text]}
        class Cache:
            contract = {"sha256": "frozen", "base_revision": "base", "pair_revision": "pair"}
            def __init__(self):
                self.calls = []
            def get(self, key):
                self.calls.append(key)
                return {runner.vector_key("frozen", [42], [97]): torch.tensor([1., 0.]),
                        runner.vector_key("frozen", [42], [98]): torch.tensor([0., 1.])}[key]
        class RecordingWhitener(Whitener):
            def whiten(self, x):
                self.batch_sizes.append(x.shape[0])
                return super().whiten(x)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "activations.safetensors")
            raw = torch.tensor([1., 1.])
            save_file({"resid": torch.stack([torch.tensor([999., 999.]), raw])}, path)
            cell = {"cell_id": "target", "family": "routing", "item_id": "item",
                    "layer": 20, "position": 0, "activation_tensor_path": path, "activation_row": 1,
                    "activation_sha256": hashlib.sha256(raw.numpy().tobytes()).hexdigest()}
            records = {i: {k: cell[k] for k in ("cell_id", "family", "item_id", "layer", "position", "activation_sha256")} |
                       {"sample_index": i, "text": "- a\n- b", "pool_id": "pool", "global_pool_id": "global",
                        "base_revision": "base", "adapter_revision": "pair"} for i in range(32)}
            parent = {"text": "- a\n- b", "bullet_count": 2,
                      "atoms": [{"phrase_id": "old_a", "text": "a\n"}, {"phrase_id": "old_b", "text": "b"}],
                      "fits": {"exact": {"fve": 1.}}}
            cache = Cache()
            whitener = RecordingWhitener(torch.zeros(2), torch.eye(2), "whitener")
            whitener.batch_sizes = []
            pool, mapped, target, vectors, atoms, sources, fit, count = runner.prepare_target(
                records, parent, cell, cache, {20: [42]}, Tokenizer(), whitener)
            self.assertEqual(len(pool), 2)
            self.assertEqual(len(cache.calls), 2)
            self.assertEqual(whitener.batch_sizes, [2, 1])
            self.assertEqual(runner.render_bullets(mapped), parent["text"])
            self.assertEqual([b.phrase_id for b in mapped], ["global:target:0:0", "global:target:0:1"])
            self.assertEqual(len(sources), 32)
            self.assertEqual(fit.fve, 1.)
            self.assertTrue(torch.equal(target, raw))


if __name__ == "__main__":
    unittest.main()
