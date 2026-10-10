"""A healthy allocation, a real cap hit, and unavailable counters stay distinct."""
import importlib.util
import copy
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('watch', Path(__file__).parents[1] / 'infra/watch_resources.py')
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class CpuWatchTests(unittest.TestCase):
    def test_fresh_headroom(self):
        self.assertEqual(watch.cpu_memory_alerts(123, {'memory.usage_in_bytes': 20,
                                                      'memory.limit_in_bytes': 100,
                                                      'memory.failcnt': 0}), [])

    def test_cap_and_failures_are_both_visible(self):
        self.assertEqual(len(watch.cpu_memory_alerts(123, {'memory.usage_in_bytes': 99,
                                                          'memory.limit_in_bytes': 100,
                                                          'memory.failcnt': 5})), 2)

    def test_missing_counter_is_not_zero_usage(self):
        self.assertIn('unavailable', watch.cpu_memory_alerts(123, {'memory.usage_in_bytes': None,
                                                                 'memory.limit_in_bytes': None})[0])

    def test_concurrent_configuration_and_workload_updates_survive(self):
        before = {"watcher": {"status": "active"}, "additional_cpu_allocations": [
            {"job_id": 1, "state": "PENDING", "progress": "waiting"}]}
        observed = copy.deepcopy(before)
        observed["additional_cpu_allocations"][0].update(state="RUNNING", progress="allocated", node="node1")
        observed["watcher"]["last_check_utc"] = "now"
        latest = copy.deepcopy(before)
        latest["additional_cpu_allocations"][0].update(progress="selectors started", warn_when_remaining_seconds=900)
        latest["additional_cpu_allocations"].append({"job_id": 2, "state": "PENDING"})
        latest["selector_id"] = 1
        merged = watch.merge_runtime_observations(before, observed, latest)
        self.assertEqual(merged["selector_id"], 1)
        self.assertEqual(merged["additional_cpu_allocations"][0], {
            "job_id": 1, "state": "RUNNING", "progress": "selectors started",
            "warn_when_remaining_seconds": 900, "node": "node1"})
        self.assertEqual(merged["additional_cpu_allocations"][1], {"job_id": 2, "state": "PENDING"})
        self.assertEqual(merged["watcher"]["last_check_utc"], "now")


if __name__ == '__main__':
    unittest.main()
