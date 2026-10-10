import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from hashlib import sha256

from olens_improve.ar_cache import digest

spec = importlib.util.spec_from_file_location('merge_selection_shards', Path(__file__).parents[1]/'scripts/merge_selection_shards.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MergeSelectionTests(unittest.TestCase):
    def fixture(self, root):
        cells = [dict(cell_id=f'c{i}', family='f', item_id=str(i), layer=20,
                      position=3, split='development') for i in range(4)]
        manifest = root/'manifest.json'
        manifest.write_text(json.dumps({'cells': cells}))
        paths = []
        for index in range(2):
            folder = root/str(index); folder.mkdir(); paths.append(folder)
            config = dict(shard_count=2, shard_index=index, full_cohort_cell_count=4,
                          pilot_manifest_sha256=sha256(manifest.read_bytes()).hexdigest(),
                          cell_ids=[c['cell_id'] for c in cells[index::2]], controls={},
                          scope='full-grid development', solver='exact')
            (folder/'config.json').write_text(json.dumps(config))
            (folder/'status.json').write_text(json.dumps(dict(status='complete',
                completed_cells=2, expected_cells=2, shard_index=index, shard_count=2, seconds=1)))
            rows = [c | dict(config_sha256=digest(config), selections=[dict(method='baseline', n=1)])
                    for c in cells[index::2]]
            (folder/'selections.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        return manifest, paths

    def test_complete_join_preserves_rows_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, paths = self.fixture(root)
            result = module.merge(manifest, paths, root/'out')
            self.assertEqual(result['cells'], 4)
            self.assertEqual(module.merge(manifest, paths[::-1], root/'out'), result)
            source = {json.loads(line)['cell_id']: line for p in paths
                      for line in (p/'selections.jsonl').read_bytes().splitlines(keepends=True)}
            self.assertEqual((root/'out/selections.jsonl').read_bytes(), b''.join(source[k] for k in sorted(source)))

    def test_duplicate_shard_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, paths = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'shard indexes'):
                module.merge(manifest, [paths[0], paths[0]], root/'out')

    def test_changed_scientific_contract_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, paths = self.fixture(root)
            path = paths[1]/'config.json'
            config = json.loads(path.read_text()); config['solver'] = 'different'
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'different scientific'):
                module.merge(manifest, paths, root/'out')

    def test_missing_row_is_rejected_even_with_complete_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, paths = self.fixture(root)
            path = paths[0]/'selections.jsonl'
            path.write_text(path.read_text().splitlines(keepends=True)[0])
            with self.assertRaisesRegex(ValueError, 'declared cell list'):
                module.merge(manifest, paths, root/'out')


if __name__ == '__main__':
    unittest.main()
