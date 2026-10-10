"""A healthy allocation, a real cap hit, and unavailable counters stay distinct."""
import importlib.util
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


if __name__ == '__main__':
    unittest.main()
