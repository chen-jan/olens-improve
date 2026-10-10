"""Heldout request planning must have authority before text or banks open."""
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from test_selector_inputs import inputs


def module(path):
    spec=importlib.util.spec_from_file_location('forecast_stage_test',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


forecast=module(Path('scripts/forecast_judging.py'))


class ForecastStageTests(unittest.TestCase):
    def fixture(self,root,stage='validation'):
        _,_,cb,fb,gb=inputs(stage)
        conditions=b'[{"method":"raw_n1","n":1}]'
        freeze=b'{"status":"root_reviewed_frozen"}'
        for name,raw in [('manifest.json',cb),('fresh.json',fb),('conditions.json',conditions),('freeze.json',freeze)]:
            (root/name).write_bytes(raw)
        gate=json.loads(gb)|{'authorization_scope':'analysis','condition_list_sha256':sha256(conditions).hexdigest(),
            'freeze_path':str(root/'freeze.json'),'freeze_sha256':sha256(freeze).hexdigest()}
        (root/'gate.json').write_text(json.dumps(gate))
        return SimpleNamespace(manifest=root/'manifest.json',fresh_manifest=root/'fresh.json',gate=root/'gate.json',
            conditions=[root/'conditions.json'],selections=[root/'must-not-open.jsonl'],output=root/'out.json')

    def test_missing_or_blind_gate_precedes_bank_and_selected_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);args=self.fixture(root)
            with patch.object(forecast,'load_upstream') as upstream,patch.object(forecast,'selection_rows') as text:
                args.gate=None
                with self.assertRaises(ValueError):forecast.run(args)
                args.gate=root/'gate.json';gate=json.loads(args.gate.read_bytes())|{'authorization_scope':'blind_generation_only'}
                args.gate.write_text(json.dumps(gate))
                with self.assertRaisesRegex(ValueError,'Blind-generation-only'):forecast.run(args)
                upstream.assert_not_called();text.assert_not_called()

    def test_signed_menu_and_freeze_required_before_banks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);args=self.fixture(root)
            original=args.conditions[0].read_bytes()
            with patch.object(forecast,'load_upstream') as upstream:
                args.conditions[0].write_bytes(b'[]')
                with self.assertRaisesRegex(ValueError,'signed stage menu'):forecast.run(args)
                args.conditions[0].write_bytes(original);(root/'freeze.json').write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError,'freeze changed'):forecast.run(args)
                upstream.assert_not_called()

    def test_valid_validation_and_legacy_dev_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);args=self.fixture(root)
            self.assertEqual(forecast.forecast_stage(args)[1],'validation')
            args=self.fixture(root,'development');args.fresh_manifest=args.gate=None
            self.assertEqual(forecast.forecast_stage(args)[1],'development')

    def test_selection_activation_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);_,cell,_,_,_=inputs()
            row={k:cell[k] for k in ('cell_id','family','item_id','layer','position','split')}
            row.update(activation_sha256='wrong',selections=[])
            path=root/'rows.jsonl';path.write_text(json.dumps(row)+'\n')
            with self.assertRaisesRegex(ValueError,'Selection activation'):
                forecast.selection_rows(path,set(),{cell['cell_id']:cell},{cell['cell_id']:cell})


if __name__=='__main__':unittest.main()
