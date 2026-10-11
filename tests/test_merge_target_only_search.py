"""Small source-bound merge checks; no model or production data needed."""
import importlib.util
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("merge_target_only_search", Path(__file__).parents[1] / "scripts/merge_target_only_search.py")
merge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge_module)


def save(path, body):
    path.write_text(json.dumps(body) + "\n")
    return path


class TargetOnlyMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "merged"
        self.cells = [dict(cell_id=f"{family}:{position}", family=family, item_id=f"item-{family}",
            group_id=f"group-{family}", layer=20, position=position, split="development",
            activation_sha256=f"activation-{family}-{position}", activation_row=position,
            activation_tensor_path="frozen-activations.safetensors") for family in ("a", "b", "c", "d") for position in (0, 1)]
        fresh = save(self.root / "fresh.json", {"cells": self.cells})
        self.inventory = {"status": "sealed", "scope": "target-only", "families": ["a", "b", "c", "d"],
            "expected": {"cells": 8, "items": 4}, "fresh_manifest": {"path": str(fresh), "sha256": merge_module.sha(fresh)},
            "vector_contract": {"sha256": "vector-contract"},
            "stages": {"development": {"selectors": {"path": "frozen-parent.jsonl", "sha256": "original-parent"}}},
            "conditions": merge_module.CONDITIONS,
            "search": {"threshold": .005, "tolerance": 1e-8, "max_bullets": 4, "max_qwen_tokens": 256,
                "subset_fit_budget": 2048, "max_swap_steps": 8, "max_rounds": 2},
            "runtime_inputs": {"runtime": {"sha256": "runtime"}, "whitener_directory": "/frozen/whiteners",
                "whitener_moments_sha256": {"20": "whitener"}}}
        self.inventory_path = save(self.root / "inventory.json", self.inventory)
        self.inventory_sha = merge_module.sha(self.inventory_path)
        self.paths = [self.root / f"worker-{i}" for i in range(2)]
        routing = {k: self.inventory[k] for k in ("fresh_manifest", "stages", "vector_contract", "families", "scope")}
        for index, directory in enumerate(self.paths):
            directory.mkdir()
            own_families = self.inventory["families"][index::2]
            search_spec = {"schema_version": 1, "shard_count": 2, "shard_index": index,
                "cell_ids": sorted(c["cell_id"] for c in self.cells if c["family"] in own_families),
                "partial_grid": True, "inventory_sha256": self.inventory_sha, "conditions": merge_module.CONDITIONS,
                "configs": [{"method": m} | {k: self.inventory["search"][k] for k in
                    ("subset_fit_budget", "max_swap_steps", "max_rounds", "threshold", "tolerance", "max_bullets")}
                    for m in merge_module.METHODS],
                "source_routing": routing, "controls_used": False, "new_model_calls": 0, "new_api_calls": 0,
                "input_contract": "one_target_activation_shared_32_readouts_matched_frozen_AR_whitener",
                "max_output_tokens": 256, "parent_method": merge_module.PARENT_METHOD, "n": 32,
                "runtime_sha256": "runtime", "whitener_directory": "/frozen/whiteners",
                "whitener_sources": {"20": {"path": "/frozen/whiteners/whitening_iolens_pooled_L20.safetensors", "sha256": "whitener"}}}
            save(directory / "spec.json", search_spec)
            rows = [self.row(cell, search_spec) for cell in self.cells if cell["cell_id"] in search_spec["cell_ids"]]
            # Intentional noncanonical whitespace proves journal rows are copied,
            # rather than decoded and serialized again by the merge.
            (directory / "selections.jsonl").write_text("".join(json.dumps(r, separators=(", ", ":  ")) + "\n" for r in rows[::-1]))
            self.seal_worker(directory)

    def row(self, cell, search_spec):
        atoms = [{"phrase_id": f"{cell['cell_id']}:p{i}", "text": f"bullet {i}",
                  "sample_id": f"pool:{cell['cell_id']}:0"} for i in range(2)]
        ids = [a["phrase_id"] for a in atoms]
        seed = int(merge_module.digest(["target_only_random_delete_match_005_v1", cell["cell_id"]])[:16], 16)
        random_id = ids[random.Random(seed).sample(range(2), 1)[0]]
        selections = []
        for method in (*merge_module.METHODS, merge_module.RANDOM_METHOD, merge_module.PARENT_METHOD):
            selected = ids if method in ("repeat_swap", merge_module.PARENT_METHOD) else [random_id] if method == merge_module.RANDOM_METHOD else ids[:1]
            texts = {a["phrase_id"]: a["text"] for a in atoms}
            output = {"method": method, "n": 32, "phrase_ids": selected,
                "text": "\n".join("- " + texts[pid] for pid in selected), "bullet_count": len(selected), "token_count": 8,
                "fits_scope": "emitted_bullets", "fits": {"exact": {"fve": .5, "atom_ids": selected}},
                "parent_phrase_ids": ids, "parent_method": "repeat_swap" if method in
                ("repeat_swap_then_prune_005", merge_module.RANDOM_METHOD) else merge_module.PARENT_METHOD}
            if method in merge_module.METHODS:
                output["budget"] = {"subset_fit_budget": 2048, "subset_fits": 20}
            if method in merge_module.METHODS[1:]:
                output["leave_one_out"] = {pid: .2 for pid in selected}
            if method == merge_module.RANDOM_METHOD:
                output["random_control"] = {"seed": seed, "retained_bullet_count": 1}
            selections.append(output)
        return {k: cell[k] for k in merge_module.IDENTITY} | {
            "inventory_sha256": self.inventory_sha, "search_spec_sha256": merge_module.digest(search_spec),
            "atoms": atoms, "source_samples": [{"sample_index": i, "sample_id": f"pool:{cell['cell_id']}:{i}"} for i in range(32)],
            "whitener_sha256": "whitener", "vector_contract_sha256": "vector-contract", "selections": selections,
            "cached_parent_source": {"path": "frozen-parent.jsonl", "sha256": "original-parent", "method": merge_module.PARENT_METHOD,
                "n": 32, "source_exact_fve": .5, "replayed_exact_fve": .5}}

    def seal_worker(self, directory):
        search_spec = json.loads((directory / "spec.json").read_text())
        rows = [json.loads(line) for line in (directory / "selections.jsonl").read_bytes().splitlines()]
        descriptors = []
        for family in sorted({row["family"] for row in rows}):
            own = sorted((r for r in rows if r["family"] == family), key=lambda r: r["cell_id"])
            selection = directory / f"{family}.jsonl"
            selection.write_text("".join(json.dumps(r) + "\n" for r in own))
            own_ids = {r["cell_id"] for r in own}
            manifest = save(directory / f"{family}.manifest.json", {"cells": [c for c in self.cells if c["cell_id"] in own_ids],
                "inventory_sha256": self.inventory_sha, "search_spec_sha256": merge_module.digest(search_spec), "partial_grid": True})
            descriptor = {"family": family, "ready": False, "partial_grid": True, "inventory_sha256": self.inventory_sha,
                "search_spec_sha256": merge_module.digest(search_spec), "conditions": merge_module.CONDITIONS,
                "cells": len(own), "items": len({r["item_id"] for r in own}), "manifest": str(manifest),
                "manifest_sha256": merge_module.sha(manifest), "selections": str(selection), "selection_sha256": merge_module.sha(selection)}
            save(directory / f"{family}.ready.json", descriptor)
            descriptors.append(descriptor)
        save(directory / "conditions.json", merge_module.CONDITIONS)
        save(directory / "status.json", {"status": "complete", "expected_cells": len(search_spec["cell_ids"]),
            "completed_cells": len(rows), "partial_grid": True, "inventory_sha256": self.inventory_sha,
            "search_spec_sha256": merge_module.digest(search_spec), "selection_sha256": merge_module.sha(directory / "selections.jsonl"),
            "new_model_calls": 0, "new_api_calls": 0, "family_descriptors": descriptors})

    def run_merge(self, paths=None):
        return merge_module.merge(self.inventory_path, self.inventory_sha, paths or self.paths, self.out, whole_journal=True)

    def change_rows(self, directory, change):
        rows = [json.loads(line) for line in (directory / "selections.jsonl").read_bytes().splitlines()]
        change(rows)
        (directory / "selections.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        self.seal_worker(directory)

    def test_nominal_streaming_merge_preserves_raw_rows_and_fresh_manifests(self):
        sources = {json.loads(line)["cell_id"]: line for p in self.paths
                   for line in (p / "selections.jsonl").read_bytes().splitlines(keepends=True)}
        before = {str(p): merge_module.sha(p) for d in self.paths for p in d.iterdir()}
        result = self.run_merge(self.paths[::-1])
        self.assertEqual((result["status"], result["cells"], result["items"]), ("complete", 8, 4))
        self.assertEqual((self.out / "selections.jsonl").read_bytes(), b"".join(sources[cid] for cid in sorted(sources)))
        for descriptor in result["family_descriptors"]:
            family = descriptor["family"]
            self.assertTrue(descriptor["ready"])
            self.assertFalse(descriptor["partial_grid"])
            self.assertEqual(json.loads(Path(descriptor["manifest"]).read_text())["cells"],
                             [c for c in self.cells if c["family"] == family])
            for line in Path(descriptor["selections"]).read_bytes().splitlines(keepends=True):
                row = json.loads(line)
                self.assertEqual(line, sources[row["cell_id"]])
                self.assertEqual(row["search_spec_sha256"], descriptor["search_spec_sha256_by_cell"][row["cell_id"]])
        self.assertEqual(before, {str(p): merge_module.sha(p) for d in self.paths for p in d.iterdir()})
        self.assertEqual(self.run_merge(), result)

    def test_incomplete_worker_and_incomplete_declared_grid_fail_closed(self):
        status = self.paths[0] / "status.json"
        body = json.loads(status.read_text()); body["status"] = "running"; save(status, body)
        with self.assertRaisesRegex(ValueError, "not complete"):
            self.run_merge()
        self.assertFalse(self.out.exists())
        self.seal_worker(self.paths[0])
        path = self.paths[0] / "spec.json"
        body = json.loads(path.read_text()); body["cell_ids"].pop(); save(path, body)
        with self.assertRaisesRegex(ValueError, "Incomplete grid"):
            self.run_merge()
        self.assertFalse(self.out.exists())

    def test_duplicate_worker_index_and_duplicate_journal_cell_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "shard indexes"):
            self.run_merge([self.paths[0], self.paths[0]])
        # Keep count complete and terminal receipts consistent: duplicate replaces
        # an intended row, so only actual journal coverage can detect this error.
        journal = self.paths[0] / "selections.jsonl"
        lines = journal.read_bytes().splitlines(keepends=True)
        lines[1] = lines[0]
        journal.write_bytes(b"".join(lines))
        status_path = self.paths[0] / "status.json"
        status = json.loads(status_path.read_text())
        status["selection_sha256"] = merge_module.sha(journal)
        save(status_path, status)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_merge()
        self.assertFalse(self.out.exists())

    def test_wrong_terminal_journal_hash_fails_closed(self):
        path = self.paths[0] / "status.json"
        body = json.loads(path.read_text()); body["selection_sha256"] = "0" * 64; save(path, body)
        with self.assertRaisesRegex(ValueError, "Journal hash mismatch"):
            self.run_merge()
        self.assertFalse(self.out.exists())

    def test_changed_common_config_even_with_refreshed_receipts_fails_closed(self):
        directory = self.paths[1]
        path = directory / "spec.json"
        body = json.loads(path.read_text()); body["torch_threads"] = 99; save(path, body)
        self.change_rows(directory, lambda rows: [r.update(search_spec_sha256=merge_module.digest(body)) for r in rows])
        with self.assertRaisesRegex(ValueError, "changed common configurations"):
            self.run_merge()
        self.assertFalse(self.out.exists())

    def test_invalid_strict_pruning_and_deterministic_random_subset_fail_closed(self):
        directory = self.paths[0]
        originals = (directory / "selections.jsonl").read_bytes()
        self.change_rows(directory, lambda rows: rows[0]["selections"][1]["leave_one_out"].update(
            {rows[0]["selections"][1]["phrase_ids"][0]: .005 + 1e-8}))
        with self.assertRaisesRegex(ValueError, "strict retained"):
            self.run_merge()
        (directory / "selections.jsonl").write_bytes(originals); self.seal_worker(directory)
        self.change_rows(directory, lambda rows: rows[0]["selections"][3]["random_control"].update(seed=0))
        with self.assertRaisesRegex(ValueError, "deterministic exact-count"):
            self.run_merge()
        self.assertFalse(self.out.exists())

    def test_source_change_after_validation_stops_publication(self):
        original = merge_module.validate_row
        changed = False
        def mutate_then_validate(*args):
            nonlocal changed
            if not changed:
                with (self.paths[0] / "status.json").open("a") as stream:
                    stream.write(" ")
                changed = True
            return original(*args)
        with patch.object(merge_module, "validate_row", side_effect=mutate_then_validate):
            with self.assertRaisesRegex(ValueError, "Source changed during merge"):
                self.run_merge()
        self.assertFalse(self.out.exists())

    def test_activation_identity_and_output_cap_are_verified(self):
        directory = self.paths[0]
        originals = (directory / "selections.jsonl").read_bytes()
        self.change_rows(directory, lambda rows: rows[0].update(activation_sha256="foreign-activation"))
        with self.assertRaisesRegex(ValueError, "activation SHA changed"):
            self.run_merge()
        (directory / "selections.jsonl").write_bytes(originals); self.seal_worker(directory)
        self.change_rows(directory, lambda rows: rows[0]["selections"][0].update(token_count=257))
        with self.assertRaisesRegex(ValueError, "output caps"):
            self.run_merge()
        self.assertFalse(self.out.exists())

    def test_control_bank_path_is_rejected_without_reading_it(self):
        body = dict(self.inventory, control_bank_path="/does/not/exist/control-bank.json")
        save(self.inventory_path, body)
        self.inventory_sha = merge_module.sha(self.inventory_path)
        with self.assertRaisesRegex(ValueError, "control-bank paths"):
            self.run_merge()
        self.assertFalse(self.out.exists())

    def test_changed_output_is_never_overwritten(self):
        self.run_merge()
        path = self.out / "a.jsonl"
        path.chmod(0o644)
        path.write_bytes(b"existing user artifact\n")
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            self.run_merge()
        self.assertEqual(path.read_bytes(), b"existing user artifact\n")


if __name__ == "__main__":
    unittest.main()
