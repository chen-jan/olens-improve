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
