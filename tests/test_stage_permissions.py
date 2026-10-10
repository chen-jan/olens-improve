"""Blind sampling capability cannot accidentally enable outcome-producing stages."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import tempfile
import unittest

from test_selector_inputs import inputs, rows
from olens_improve.ar_partition import validate_stage
from olens_improve.stage_io import validate_export_stage
from olens_improve.stream_inputs import stream_context
from olens_improve.selector_inputs import load_selector_inputs
from olens_improve.stage_permissions import require_gate_capability, require_record_analysis
from hashlib import sha256
import contextlib
import io


def script(name):
    spec = importlib.util.spec_from_file_location(name, Path('scripts') / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class StagePermissionTests(unittest.TestCase):
    def test_blind_generation_allows_only_validated_generation(self):
        _, _, cb, fb, gb = inputs()
        gate = json.loads(gb) | {'authorization_scope': 'blind_generation_only'}
        blind = json.dumps(gate).encode()
        args = (json.loads(cb), sha256(cb).hexdigest(), json.loads(fb), sha256(fb).hexdigest(), gate)
        self.assertEqual(validate_stage(*args, capability='generation')[0], 'validation')
        script('generate_samples').check_gate(gate)
        for function in (lambda: validate_stage(*args),
                         lambda: validate_export_stage(cb, fb, blind),
                         lambda: stream_context(cb, fb, blind),
                         lambda: load_selector_inputs([], cb, fb, blind)):
            with self.assertRaisesRegex(ValueError, 'Blind-generation-only'):
                function()
        with self.assertRaises(ValueError):
            require_gate_capability({'authorization_scope': 'unrecognized'}, 'generation')

    def test_test_remains_closed_even_with_blind_capability(self):
        _, _, cb, fb, gb = inputs('test')
        gate = json.loads(gb) | {'authorization_scope': 'blind_generation_only'}
        with self.assertRaisesRegex(ValueError, 'test remains sealed'):
            validate_stage(json.loads(cb), sha256(cb).hexdigest(), json.loads(fb), sha256(fb).hexdigest(),
                           gate, capability='generation')

    def blind_test_fixture(self):
        _, target, cb, fb, gb = inputs('test')
        manifest = json.loads(cb) | {'blind_test_generation_authorized': True,
                                     'frozen_test_authorized': False}
        cb = json.dumps(manifest).encode()
        gate = json.loads(gb) | {'authorization_scope': 'blind_generation_only',
            'blind_test_generation_authorized': True, 'frozen_test_authorized': False,
            'manifest_sha256': sha256(cb).hexdigest(), 'capture_version': 'fresh-core-v1'}
        return target, cb, fb, json.dumps(gate).encode()

    def test_explicit_blind_test_authority_is_generation_only(self):
        _, cb, fb, gb = self.blind_test_fixture()
        manifest, fresh, gate = map(json.loads, (cb, fb, gb))
        args = (manifest, sha256(cb).hexdigest(), fresh, sha256(fb).hexdigest(), gate)
        self.assertEqual(validate_stage(*args, capability='generation')[0], 'test')
        for owner in ('manifest', 'gate'):
            for field, value in [('blind_test_generation_authorized', False),
                                 ('frozen_test_authorized', True), ('frozen_test_authorized', None)]:
                changed_m = manifest | {field: value} if owner == 'manifest' else manifest
                changed_g = gate | {field: value} if owner == 'gate' else gate
                with self.assertRaises(ValueError):
                    validate_stage(changed_m, sha256(cb).hexdigest(), fresh,
                                   sha256(fb).hexdigest(), changed_g, capability='generation')
        for function in (lambda: validate_stage(*args),
                         lambda: validate_export_stage(cb, fb, gb),
                         lambda: stream_context(cb, fb, gb),
                         lambda: load_selector_inputs([], cb, fb, gb)):
            with self.assertRaisesRegex(ValueError, 'Blind-generation-only'): function()

    def test_blind_test_generator_validate_only_and_fixed_pool(self):
        _, cb, fb, gb = self.blind_test_fixture()
        generator = script('generate_samples')
        fresh = json.loads(fb)
        for row in fresh['cells']:
            row.update(generation_activation_source='fresh_recapture',
                       activation_tensor_path='synthetic.safetensors', activation_row=0)
        fb = json.dumps(fresh).encode(); gate = json.loads(gb)
        gate['fresh_index_sha256'] = sha256(fb).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, content in [('manifest.json', cb), ('fresh.json', fb),
                                  ('gate.json', json.dumps(gate).encode()), ('runtime.json', b'{}')]:
                (root/name).write_bytes(content)
            argv = ['generate_samples.py', '--runtime', str(root/'runtime.json'),
                '--manifest', str(root/'manifest.json'), '--gate', str(root/'gate.json'),
                '--adapter', str(root/'not-loaded-adapter'), '--fresh-index', str(root/'fresh.json'),
                '--capture-version', 'fresh-core-v1', '--output', str(root/'not-created-pool'),
                '--n', '32', '--seed', '20261010', '--shard-count', '4', '--shard-index', '0', '--validate-only']
            argv.extend(['--batch-size', '32', '--cells-per-batch', '4', '--maximum-batch-sequences', '128'])
            output = io.StringIO()
            with patch('sys.argv', argv), contextlib.redirect_stdout(output): generator.main()
            self.assertFalse(json.loads(output.getvalue())['launch'])
            self.assertFalse((root/'not-created-pool').exists())
            for flag, value in [('--n', '16'), ('--seed', '1'), ('--shard-count', '2')]:
                bad = list(argv); bad[bad.index(flag)+1] = value
                with patch('sys.argv', bad), self.assertRaisesRegex(ValueError, 'unchanged N32'):
                    generator.main()
            for flag, value in [('--batch-size', '16'), ('--cells-per-batch', '1'),
                                ('--maximum-batch-sequences', '64')]:
                bad = list(argv); bad[bad.index(flag)+1] = value
                with patch('sys.argv', bad), self.assertRaisesRegex(ValueError, 'sampling batch recipe'):
                    generator.main()
            with patch('sys.argv', argv + ['--import-pool', str(root/'not-read.jsonl')]), \
                    self.assertRaisesRegex(ValueError, 'cannot import'):
                generator.main()
            self.assertFalse((root/'not-created-pool').exists())

    def test_blind_test_resume_rejects_unmarked_target_and_preserves_history(self):
        generator = script('generate_samples'); target = {'cell_id': 'test-target'}
        marked = {'generation_authorization_scope': 'blind_generation_only',
                  'generation_gate_sha256': 'b'*64}
        state = {'old-dev': {0: {'text': 'unchanged history'}}, 'test-target': {0: marked}}
        before = json.dumps(state, sort_keys=True)
        generator.validate_blind_test_resume(state, [target])
        self.assertEqual(before, json.dumps(state, sort_keys=True))
        for row in ({}, marked | {'generation_authorization_scope': 'analysis'},
                    marked | {'generation_gate_sha256': ''}, marked | {'generation_gate_sha256': 'not-a-hash'}):
            with self.assertRaisesRegex(ValueError, 'gate provenance'):
                generator.validate_blind_test_resume({'test-target': {0: row}}, [target])

    def test_later_final_analysis_consumes_same_blind_test_record(self):
        target, cb, fb, gb = self.blind_test_fixture()
        record = rows(target)[0] | {'generation_authorization_scope': 'blind_generation_only',
                                   'generation_gate_sha256': sha256(gb).hexdigest()}
        with self.assertRaises(ValueError): require_record_analysis(record)
        manifest = json.loads(cb) | {'frozen_test_authorized': True}
        analysis_cb = json.dumps(manifest).encode()
        gate = json.loads(gb) | {'authorization_scope': 'analysis', 'frozen_test_authorized': True,
                                'manifest_sha256': sha256(analysis_cb).hexdigest()}
        _, cohort, captures = validate_export_stage(analysis_cb, fb, json.dumps(gate).encode())
        before = dict(record); require_record_analysis(record, cohort, captures)
        self.assertEqual(before, record)

    def test_unchanged_blind_record_requires_separate_analysis_gate(self):
        _, target, cb, fb, gb = inputs()
        record = rows(target)[0] | {'generation_authorization_scope': 'blind_generation_only'}
        with self.assertRaisesRegex(ValueError, 'separately verified'):
            require_record_analysis(record)
        _, cohort, fresh = validate_export_stage(cb, fb, gb)
        original = dict(record); require_record_analysis(record, cohort, fresh)
        self.assertEqual(record, original)
        with self.assertRaisesRegex(ValueError, 'activation'):
            require_record_analysis(record | {'activation_sha256': 'wrong'}, cohort, fresh)
        # Direct AR entrypoint rejects before loading tokenizer, checkpoint or GPU model.
        encoder = script('encode_candidates')
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'blind.jsonl'; source.write_text(json.dumps(record) + '\n')
            args = SimpleNamespace(input=[str(source)], batch_size=128, shard_size=4096)
            with patch.dict('os.environ', {'SLURM_JOB_ID': 'synthetic'}), \
                 patch.object(encoder.AutoTokenizer, 'from_pretrained') as tokenizer, \
                 patch.object(encoder.FrozenAR, 'load') as model:
                with self.assertRaisesRegex(ValueError, 'separately verified'):
                    encoder.encode_snapshot(args)
                tokenizer.assert_not_called(); model.assert_not_called()


if __name__ == '__main__':
    unittest.main()
