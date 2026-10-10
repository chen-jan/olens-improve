"""A healthy allocation, a real cap hit, and unavailable counters stay distinct."""
import importlib.util
import copy
import os
import tempfile
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

    def test_storage_roots_deduplicate_hardlinks_and_exclude_reused_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            fast, durable = Path(folder)/'fast', Path(folder)/'durable'
            fast.mkdir(); durable.mkdir()
            (fast/'a').write_bytes(b'12345')
            os.link(fast/'a', durable/'same')
            (durable/'b').write_bytes(b'678')
            (fast/'external').symlink_to(durable/'b')
            counts = watch.project_storage([fast, durable])
            self.assertEqual((counts['logical_bytes'], counts['files']), (8, 2))
            self.assertEqual(counts['per_root'][str(fast)]['logical_bytes'], 5)
            self.assertEqual(counts['per_root'][str(durable)]['logical_bytes'], 3)
            self.assertTrue(all(v['complete'] for v in counts['per_root'].values()))

    def test_storage_bound_is_not_a_complete_zero_for_unvisited_root(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder)/'first', Path(folder)/'second'
            first.mkdir(); second.mkdir(); (first/'a').write_bytes(b'a')
            counts = watch.project_storage([first, second], maximum_files=1)
            self.assertFalse(counts['complete'])
            self.assertFalse(counts['per_root'][str(second)]['complete'])


if __name__ == '__main__':
    unittest.main()
