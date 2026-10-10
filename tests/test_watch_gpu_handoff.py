"""GPU handoff metadata prevents live probes while project jobs remain monitored."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "watch_handoff", Path(__file__).parents[1] / "infra/watch_resources.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class GpuHandoffTests(unittest.TestCase):
    def test_explicit_gpu_markers_only(self):
        self.assertTrue(watch.gpu_handed_back({"gpu": "h200", "project_active": False}))
        self.assertTrue(watch.gpu_handed_back({"gpu": "h200", "handed_back_to_user_utc": "2026-10-10T18:10:48Z"}))
        for fields in ({}, {"project_active": True}, {"project_active": 0},
                       {"handed_back_to_user_utc": ""}, {"handed_back_to_user_utc": None}):
            self.assertFalse(watch.gpu_handed_back({"gpu": "h200", **fields}))
        self.assertFalse(watch.gpu_handed_back({"project_active": False}))

    def test_concurrent_handoff_preserves_historical_observations(self):
        before = {"watcher": {}, "gpu_allocations": [
            {"job_id": 1, "gpu": "h200", "end_utc": "old", "state": "RUNNING"}]}
        observed = copy.deepcopy(before)
        observed["gpu_allocations"][0].update(end_utc="new", state="COMPLETED")
        observed["watcher"]["last_check_utc"] = "now"
        latest = copy.deepcopy(before)
        latest["gpu_allocations"][0].update(project_active=False,
                                          handed_back_to_user_utc="handoff")
        merged = watch.merge_runtime_observations(before, observed, latest)
        self.assertEqual(merged["gpu_allocations"], latest["gpu_allocations"])
        self.assertEqual(merged["watcher"]["last_check_utc"], "now")

    def test_one_shot_skips_handed_back_gpu_and_preserves_other_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "orcd").mkdir()
            (root / "orcd/.quota").write_text("synthetic quota")
            fast, durable = root / "fast", root / "durable"
            fast.mkdir()
            durable.mkdir()
            handed_back = [
                {"job_id": 25330001, "gpu": "h200", "project_active": False,
                 "handed_back_to_user_utc": "2026-10-10T18:10:48Z", "end_utc": "2000-01-01T00:00:00Z"},
                {"job_id": 25330006, "gpu": "h200", "project_active": False},
                {"job_id": 25330007, "gpu": "h200", "handed_back_to_user_utc": "2026-10-10T18:10:48Z"},
                {"job_id": 25417596, "gpu": "h200", "project_active": False}]
            runtime = {"gpu_allocations": handed_back + [{"job_id": 10, "gpu": "h200"}],
                       "preemptable_allocations": [{"job_id": 11, "gpu": "h200", "requested_utc": "2026-01-01T00:00:00Z"}],
                       "additional_cpu_allocations": [{"job_id": 12, "requested_utc": "2026-01-01T00:00:00Z"}],
                       "paths": {"fast": str(fast), "durable": str(durable)},
                       "watcher": {"agent": "synthetic"}, "storage_group_quota_status": "synthetic",
                       "gpu_owner_uid": 123, "storage_authorized_aggregate_bytes": 1000}
            runtime_path = root / "runtime.json"
            runtime_path.write_text(json.dumps(runtime))
            calls = []

            def fake_command(argv):
                calls.append(argv)
                if argv[0] == "scontrol":
                    return {"returncode": 0, "stdout": "JobState=RUNNING Reason=None NodeList=node1 UserId=${USER}(123)", "stderr": ""}
                if "nvidia-smi" in argv:
                    return {"returncode": 0, "stdout": "synthetic gpu", "stderr": ""}
                return {"returncode": 0, "stdout": json.dumps({"memory.usage_in_bytes": 1,
                         "memory.limit_in_bytes": 100, "memory.failcnt": 0}), "stderr": ""}

            with patch.object(watch, "command", side_effect=fake_command), \
                 patch.object(watch, "budget_snapshot", return_value={"status": "synthetic_no_sql"}), \
                 patch.object(watch, "project_storage", return_value={"complete": True, "logical_bytes": 0}), \
                 patch.object(watch.Path, "home", return_value=root), \
                 patch("sys.argv", ["watch_resources.py", "--runtime", str(runtime_path)]), \
                 patch("builtins.print"):
                watch.main()

            snapshot = json.loads((fast / "watcher/latest.json").read_text())
            rewritten = json.loads(runtime_path.read_text())
            self.assertEqual(rewritten["gpu_allocations"][:4], handed_back)
            self.assertEqual([c[-1] for c in calls if c[0] == "scontrol"], ["10", "11", "12"])
            self.assertEqual(set(snapshot["gpu_status"]), {"10", "11"})
            self.assertEqual(set(snapshot["additional_cpu_status"]), {"12"})
            self.assertEqual(snapshot["alerts"], [])
            for job in handed_back:
                self.assertEqual(snapshot["jobs"][str(job["job_id"])], {
                    "observation_skipped": "outside_project_scope", "historical_allocation": job})


if __name__ == "__main__":
    unittest.main()
