"""Offline transport-gate and resume-provenance checks; no API calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from olens_improve.evaluation import evaluate_condition, positive_rpm, safe_exception_chain


class EvaluationTransportTests(unittest.TestCase):
    def test_connection_diagnostics_exclude_messages_and_bound_cycles(self):
        cause = OSError(24, 'secret URL or token')
        outer = RuntimeError('private provider response')
        outer.__cause__ = cause
        cause.__cause__ = outer
        self.assertEqual(safe_exception_chain(outer), [
            {'class': 'RuntimeError', 'errno': None}, {'class': 'OSError', 'errno': 24}])

    def test_invalid_rate_rejected_before_dispatch(self):
        for value in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                positive_rpm(value)

    def test_rate_forwarded_and_resume_keeps_scientific_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cell = {"cell_id": "fixture", "family": "multihop_mt", "item_id": "item",
                    "layer": 20, "position": 4, "split": "development"}
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"partial_grid": True, "cells": [cell]}))
            selections = root / "selections.jsonl"
            selections.write_text(json.dumps({**cell, "method": "fixture", "pool_n": 1, "text": "- example"}) + "\n")
            arguments = {"method": "fixture", "n": 1, "ledger_path": root / "budget.sqlite3",
                         "run_id": "offline", "family_only": "multihop_mt", "service_tier": "default"}
            with patch("olens_improve.evaluation.run_family", return_value={}) as dispatch:
                evaluate_condition(selections, manifest, root / "out", **arguments)
                self.assertEqual(dispatch.call_args.kwargs["rpm"], 120)
                before = (root / "out/condition.json").read_bytes()
                evaluate_condition(selections, manifest, root / "out", **arguments, concurrency=32, rpm=600)
                self.assertEqual(dispatch.call_args.kwargs["rpm"], 600)
                self.assertEqual(dispatch.call_args.kwargs["concurrency"], 32)
                self.assertEqual(before, (root / "out/condition.json").read_bytes())
            events = [json.loads(s) for s in (root / "out/multihop_mt.execution.jsonl").read_text().splitlines()]
            completed = [e for e in events if e["status"] == "completed"]
            self.assertEqual([e["transport"]["rpm"] for e in completed], [120, 600])
            self.assertEqual(completed[-1]["transport"]["concurrency"], 32)


if __name__ == "__main__":
    unittest.main()
