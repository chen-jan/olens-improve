"""Analysis authorization precedes selected text, ledger and judge dispatch."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_selector_inputs import inputs, body
from olens_improve.evaluation import evaluate_condition, _main


class EvaluationStageTests(unittest.TestCase):
    def fixture(self,root,stage='validation'):
        _,target,cb,fb,gb=inputs(stage)
        for name,raw in [('manifest.json',cb),('fresh.json',fb),('gate.json',gb)]:
            (root/name).write_bytes(raw)
        return target

    def test_api_blind_or_missing_gate_rejected_before_text_and_payment(self):
        for stage in ('validation','test'):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);self.fixture(root,stage)
                gate=json.loads((root/'gate.json').read_bytes())|{'authorization_scope':'blind_generation_only'}
                (root/'gate.json').write_bytes(body(gate))
                kwargs={'method':'fixture','n':1,'ledger_path':root/'must-not-exist.sqlite3',
                        'run_id':'fixture','allow_paid':True,'fresh_manifest':root/'fresh.json'}
                with patch('olens_improve.evaluation.AtomicBudget') as ledger, \
                     patch('olens_improve.evaluation.run_family') as judge, \
                     patch('olens_improve.evaluation.transport_settings') as transport:
                    for supplied in (None,root/'gate.json'):
                        with self.assertRaises(ValueError):
                            evaluate_condition(root/'no-text-file.jsonl',root/'manifest.json',root/'out',
                                               **kwargs,gate=supplied)
                    ledger.assert_not_called();judge.assert_not_called();transport.assert_not_called()
                    self.assertFalse((root/'out').exists())

    def test_cli_rejects_blind_gate_before_family_workers_or_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.fixture(root)
            gate=json.loads((root/'gate.json').read_bytes())|{'authorization_scope':'blind_generation_only'}
            (root/'gate.json').write_bytes(body(gate))
            argv=['evaluation','--manifest',str(root/'manifest.json'),'--fresh-manifest',str(root/'fresh.json'),
                  '--gate',str(root/'gate.json'),'--selections',str(root/'unread.jsonl'),'--output',str(root/'out'),
                  '--method','fixture','--run-id','fixture','--allow-paid','--all-families']
            with patch('sys.argv',argv),patch('olens_improve.evaluation.subprocess.Popen') as workers, \
                 patch('olens_improve.evaluation.evaluate_condition') as dispatch:
                with self.assertRaisesRegex(ValueError,'Blind-generation-only'):_main()
                workers.assert_not_called();dispatch.assert_not_called()

    def test_analysis_gate_is_bound_before_source_activation_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=self.fixture(root)
            gate=json.loads((root/'gate.json').read_bytes())|{'authorization_scope':'analysis'}
            (root/'gate.json').write_bytes(body(gate))
            row={k:target[k] for k in ('cell_id','family','item_id','layer','position','split')}
            row.update({'method':'fixture','pool_n':1,'text':'Synthetic preserved text.','activation_sha256':'wrong'})
            (root/'source.jsonl').write_bytes(body(row))
            with patch('olens_improve.evaluation.AtomicBudget') as ledger,patch('olens_improve.evaluation.run_family') as judge:
                with self.assertRaisesRegex(ValueError,'source activation'):
                    evaluate_condition(root/'source.jsonl',root/'manifest.json',root/'out',method='fixture',n=1,
                        ledger_path=root/'unused.sqlite3',run_id='fixture',allow_paid=True,
                        fresh_manifest=root/'fresh.json',gate=root/'gate.json')
                ledger.assert_not_called();judge.assert_not_called()

    def test_valid_analysis_gate_preserves_source_text_and_records_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=self.fixture(root)
            gate=json.loads((root/'gate.json').read_bytes())|{'authorization_scope':'analysis'}
            (root/'gate.json').write_bytes(body(gate))
            row={k:target[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')}
            row.update({'method':'fixture','pool_n':1,'text':'- A does not own 17 books.',
                        'generation_authorization_scope':'blind_generation_only'})
            raw=body(row);(root/'source.jsonl').write_bytes(raw)
            with patch('olens_improve.evaluation.run_family',return_value={}) as judge:
                result=evaluate_condition(root/'source.jsonl',root/'manifest.json',root/'out',method='fixture',n=1,
                    ledger_path=root/'synthetic.sqlite3',run_id='offline',allow_paid=False,family_only='toy',
                    fresh_manifest=root/'fresh.json',gate=root/'gate.json')
                self.assertTrue(judge.call_args.kwargs['dry_run'])
            self.assertEqual((root/'source.jsonl').read_bytes(),raw)
            readout=json.loads((root/'out/toy.readouts.jsonl').read_bytes())
            self.assertEqual(readout['samples'],[row['text']])
            self.assertEqual(result['condition']['analysis_authorization']['split'],'validation')


if __name__=='__main__':unittest.main()
