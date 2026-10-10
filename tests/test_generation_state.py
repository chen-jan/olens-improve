"""Offline durability/prefix tests; no model loads or GPU work."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("generate_samples", Path(__file__).parents[1] / "scripts/generate_samples.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def record(index, text=None):
    return {"cell_id": "cell", "sample_index": index, "text": text or f"sample-{index}",
            "base_revision": runner.BASE_REVISION, "adapter_revision": runner.PAIR_REVISION,
            "activation_sha256": "exact-fresh-vector"}


class GenerationStateTests(unittest.TestCase):
    def test_import_preserves_first_two_then_append_never_resamples(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "candidates.jsonl"
            source.write_text("\n".join(json.dumps(record(i)) for i in range(2)) + "\n")
            journal = Path(root) / "journal.jsonl"
            state = {}
            with journal.open("a") as stream:
                runner.import_records(source, [{"cell_id": "cell"}], "pool", state, stream, lambda _: "exact-fresh-vector")
                runner.import_records(source, [{"cell_id": "cell"}], "pool", state, stream, lambda _: "exact-fresh-vector")
                runner.append_event(stream, {"global_pool_id": "pool", "records": [record(2)]}, state)
            recovered = runner.read_journal(journal, "pool")
            self.assertEqual([recovered["cell"][i]["text"] for i in range(3)], ["sample-0", "sample-1", "sample-2"])
            self.assertEqual(len(journal.read_text().splitlines()), 2)

    def test_only_unterminated_tail_can_be_repaired(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Path(root) / "journal.jsonl"
            first = json.dumps({"global_pool_id": "pool", "records": [record(0)]}) + "\n"
            journal.write_text(first + '{"partial":')
            with self.assertRaises(ValueError):
                runner.read_journal(journal, "pool")
            self.assertEqual(runner.read_journal(journal, "pool", repair_tail=True)["cell"][0]["text"], "sample-0")
            self.assertEqual(journal.read_text(), first)
            journal.write_text(first + "corruption\n")
            with self.assertRaises(json.JSONDecodeError):
                runner.read_journal(journal, "pool", repair_tail=True)

    def test_duplicates_gaps_and_over_cap_fail(self):
        for rows in [[record(0), record(0)], [record(1)], [record(32)]]:
            with self.assertRaises(ValueError):
                runner.add_records({}, rows)

    def test_gate_requires_both_conditions(self):
        for gate in [{}, {"recapture_status": "passed"}, {"production_generation_authorized": True}]:
            with self.assertRaises(RuntimeError):
                runner.check_gate(gate)
        runner.check_gate({"recapture_status": "passed", "production_generation_authorized": True})

    def test_shards_partition_cells_and_seeds_do_not_depend_on_worker(self):
        assignments = [runner.shard_for(f"cell-{i}", 4) for i in range(50)]
        self.assertEqual(sum(assignments.count(i) for i in range(4)), 50)
        self.assertEqual(runner.batch_seed("pool", "cell", 2, 7), runner.batch_seed("pool", "cell", 2, 7))
        self.assertNotEqual(runner.batch_seed("pool", "cell", 0, 7), runner.batch_seed("pool", "cell", 2, 7))


if __name__ == "__main__":
    unittest.main()
