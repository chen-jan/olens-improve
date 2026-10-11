from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from build_expansion_resource_supplement import allocations, preserve_first_interval, scoped_storage


class ResourceSupplementTests(unittest.TestCase):
    def capture(self, ongoing=False):
        header = 'JobIDRaw|State|Start|End|ElapsedRaw|AllocTRES|NodeList\n'
        rows = ['25536297|PREEMPTED|2026-10-11T00:15:43|2026-10-11T03:57:55|13332|cpu=8,gres/gpu:h200=1,gres/gpu=1|node4603',
                '25536297.batch|CANCELLED|2026-10-11T00:15:43|2026-10-11T03:57:55|13332|cpu=8,gres/gpu=1|node4603',
                '25536297|'+('RUNNING' if ongoing else 'COMPLETED')+'|2026-10-11T04:01:02|'+('Unknown' if ongoing else '2026-10-11T05:01:02')+'|3600|cpu=8,gres/gpu:h200=1,gres/gpu=1|node4010']
        rows += [job+'|COMPLETED|2026-10-11T00:00:00|2026-10-11T01:00:00|3600|cpu=8|cpu'
                 for job in ('25536291', '25536417', '25536927')]
        return header+'\n'.join(rows)+'\n'

    def test_parent_intervals_replace_snapshot_and_ignore_steps(self):
        intervals, _ = allocations(self.capture())
        self.assertEqual(len(intervals['25536297']), 2)
        self.assertEqual(sum(r['allocated_seconds'] for r in intervals['25536297']), 16932)
        self.assertAlmostEqual(sum(r['allocated_gpu_hours'] for r in intervals['25536297']), 4.703333333333333)
        receipt = {'resource_intervals_utc': [intervals['25536297'][0]['source_parent_row']]}
        preserve_first_interval(intervals, receipt)
        intervals['25536297'][0]['allocated_seconds'] = 13331
        with self.assertRaises(ValueError):
            preserve_first_interval(intervals, receipt)

    def test_partial_requires_explicit_flag(self):
        with self.assertRaises(ValueError):
            allocations(self.capture(True))
        intervals, _ = allocations(self.capture(True), partial=True)
        self.assertFalse(intervals['25536297'][1]['terminal'])

    def test_duplicate_overlap_missing_and_bad_elapsed_rejected(self):
        text = self.capture()
        mutations = [text+text.splitlines()[1]+'\n',
                     text.replace('04:01:02', '03:50:02').replace('05:01:02', '04:50:02'),
                     '\n'.join(r for r in text.splitlines() if not r.startswith('25536927|'))+'\n',
                     text.replace('|13332|', '|13000|')]
        for changed in mutations:
            with self.assertRaises(ValueError):
                allocations(changed)

    def test_storage_is_scoped_deduplicated_and_excludes_reused_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); owned = base/'owned'; owned.mkdir()
            (owned/'data').write_bytes(b'12345')
            os.link(owned/'data', owned/'same-inode')
            (base/'external-weight').write_bytes(b'0123456789')
            (owned/'reused-weight').symlink_to(base/'external-weight')
            external = [{'path': str(base/'external-weight'), 'scope': 'externally reused weight'}]
            with patch('build_expansion_resource_supplement.OWNED', (base,)):
                result = scoped_storage({'owned_roots': [str(owned)], 'externally_reused_artifacts': external})
            self.assertEqual(result['owned_subtrees']['logical_bytes'], 5)
            self.assertEqual(result['owned_subtrees']['files'], 1)
            self.assertTrue(result['owned_subtrees']['complete'])
            self.assertEqual(result['externally_reused_artifacts'], external)
        with self.assertRaises(ValueError):
            scoped_storage({'owned_roots': ['${LAB_COMPUTE_ROOT}']})


if __name__ == '__main__':
    unittest.main()
