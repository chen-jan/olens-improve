"""Synthetic artifact-stage fixtures; no benchmark inputs or model calls."""
from hashlib import sha256
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from olens_improve.stage_io import intended_stage, validate_export_stage, original_prefix_overlap


def body(value):
    return (json.dumps(value) + '\n').encode()


class StageExportTests(unittest.TestCase):
    def fixture(self, stage):
        cells = [{'cell_id': f'c{i}', 'family': 'fixture', 'item_id': f'i{i}', 'layer': 44,
                  'position': i, 'group_id': f'g{i}', 'split': stage} for i in range(4)]
        manifest = body({'split': stage, 'cells': cells})
        fresh = body({'cells': [c | {'adapter_disabled': True, 'activation_sha256': f'a{i}'}
                                for i, c in enumerate(cells)]})
        gate = {'manifest_sha256': sha256(manifest).hexdigest(),
                'fresh_index_sha256': sha256(fresh).hexdigest(), 'recapture_status': 'passed',
                'production_generation_authorized': True, 'authorized_cells': 4,
                'maximum_samples_per_cell': 32}
        return cells, manifest, fresh, gate

    def test_stage_and_gate_fail_closed(self):
        cells, manifest, fresh, gate = self.fixture('validation')
        with self.assertRaises(ValueError): validate_export_stage(manifest, fresh)
        self.assertEqual(validate_export_stage(manifest, fresh, body(gate))[0], 'validation')
        with self.assertRaises(ValueError): validate_export_stage(manifest, fresh, body(gate | {'dry_run_only': True}))
        with self.assertRaises(ValueError): intended_stage({'cells': [cells[0], cells[1] | {'split': 'test'}]})
        cells, manifest, fresh, gate = self.fixture('test')
        with self.assertRaises(ValueError): validate_export_stage(manifest, fresh, body(gate))
        frozen = json.loads(manifest) | {'frozen_test_authorized': True}
        manifest = body(frozen)
        gate |= {'manifest_sha256': sha256(manifest).hexdigest(), 'frozen_test_authorized': True}
        self.assertEqual(validate_export_stage(manifest, fresh, body(gate))[0], 'test')

    def test_development_default_and_nonoverlap(self):
        cells, manifest, fresh, _ = self.fixture('development')
        self.assertEqual(validate_export_stage(manifest, fresh)[0], 'development')
        original = [{'cell_id': 'old', 'sample_index': 0, 'text': 'unchanged'}]
        self.assertEqual(original_prefix_overlap(original, {c['cell_id'] for c in cells}), {})

    def test_freeze_validation_zero_instrument_overlap_and_source_fields(self):
        self.run_freeze_fixture('validation', overlap=False)

    def test_freeze_development_preserves_all_original_fields(self):
        self.run_freeze_fixture('development', overlap=True)

    def test_freeze_rejects_changed_original_provenance(self):
        self.run_freeze_fixture('development', overlap=True, tamper=True)

    def test_baseline_export_validation_uses_gate_and_same_verbatim_cap(self):
        cells, manifest, fresh, gate = self.fixture('validation')
        spec = importlib.util.spec_from_file_location('baseline_stage_fixture',
                   Path(__file__).parents[1]/'scripts/export_baselines.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        class Tokenizer:
            def __call__(self, text, **_): return {'input_ids': text.split()}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, payload in [('manifest.json', manifest), ('fresh.json', fresh), ('gate.json', body(gate)),
                                  ('runtime.json', body({'paths': {'base_snapshot': 'synthetic_unused'}}))]:
                (root/name).write_bytes(payload)
            records = [c | {'sample_index': 0, 'activation_sha256': f'a{i}', 'pool_id': 'synthetic',
                            'text': '- A does not own 17 books.\n- B owns 2 books.\n'} for i, c in enumerate(cells)]
            journal = root/'input.jsonl'; journal.write_bytes(body({'records': records}))
            journal.with_suffix('.status.json').write_bytes(body({'status': 'complete',
                                               'journal_sha256': sha256(journal.read_bytes()).hexdigest()}))
            arguments = ['fixture', '--input', str(journal), '--manifest', str(root/'manifest.json'),
                         '--fresh-manifest', str(root/'fresh.json'), '--gate', str(root/'gate.json'),
                         '--runtime', str(root/'runtime.json'), '--output', str(root/'output')]
            with patch.object(sys, 'argv', arguments), patch.dict(os.environ, {'SLURM_JOB_ID': 'synthetic_fixture_only'}), \
                 patch.object(module.AutoTokenizer, 'from_pretrained', return_value=Tokenizer()):
                module.main()
            metadata = json.loads((root/'output/export.json').read_text())
            self.assertEqual(metadata['split'], 'validation')
            self.assertEqual(metadata['coordinator_gate_sha256'], sha256(body(gate)).hexdigest())
            outputs = [json.loads(line) for line in (root/'output/selections.jsonl').read_text().splitlines()]
            self.assertEqual(len(outputs), 4)
            for row, source in zip(outputs, records):
                self.assertEqual([s['text'] for s in row['selections']], [source['text']]*2)

    def run_freeze_fixture(self, stage, overlap, tamper=False):
        cells, manifest, fresh, gate = self.fixture(stage)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); pool = root/'pool'; pool.mkdir()
            (pool/'pool.json').write_bytes(body({'global_pool_id': 'synthetic'}))
            (root/'manifest.json').write_bytes(manifest); (root/'fresh.json').write_bytes(fresh)
            (root/'gate.json').write_bytes(body(gate)); first = None
            for i, cell in enumerate(cells):
                records = [cell | {'sample_index': n, 'activation_sha256': f'a{i}', 'text': f'- Claim {n}',
                                   'global_pool_id': 'synthetic', 'arbitrary_provenance': ['keep', n]}
                           for n in range(32)]
                if i == 0: first = records[0]
                journal = pool/f'shard-{i:03d}-of-004.jsonl'
                journal.write_bytes(body({'global_pool_id': 'synthetic', 'records': records}))
                journal.with_suffix('.status.json').write_bytes(body({'status': 'complete', 'completed_cells': 1,
                    'expected_cells': 1, 'target_n': 32, 'journal_sha256': sha256(journal.read_bytes()).hexdigest()}))
            original = first if overlap else {'cell_id': 'old', 'sample_index': 0, 'text': 'outside cohort'}
            if tamper: original = original | {'arbitrary_provenance': ['changed']}
            (root/'original.jsonl').write_bytes(body(original))
            command = [sys.executable, str(Path(__file__).parents[1]/'scripts/freeze_pool.py'), '--pool', str(pool),
                       '--manifest', str(root/'manifest.json'), '--fresh-manifest', str(root/'fresh.json'),
                       '--original-instrument', str(root/'original.jsonl'), '--output', str(root/'frozen')]
            if stage != 'development': command += ['--gate', str(root/'gate.json')]
            result = subprocess.run(command, env=os.environ | {'SLURM_JOB_ID': 'synthetic_fixture_only'},
                                    capture_output=True, text=True)
            if tamper:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('original instrument sample changed', result.stderr)
                self.assertFalse((root/'frozen').exists())
                return
            self.assertEqual(result.returncode, 0, result.stderr)
            snapshot = json.loads((root/'frozen/snapshot.json').read_text())
            flat_meta = json.loads((root/'frozen/samples-n32.manifest.json').read_text())
            self.assertEqual(snapshot['split'], stage)
            self.assertEqual(snapshot['preserved_original_samples'], int(overlap))
            self.assertEqual(snapshot['original_samples_overlapping_cohort'], int(overlap))
            self.assertEqual(flat_meta['scope'], 'full_grid_' + stage)
            output = json.loads((root/'frozen/samples-n32.jsonl').read_text().splitlines()[0])
            self.assertEqual(output, first)


if __name__ == '__main__':
    unittest.main()
