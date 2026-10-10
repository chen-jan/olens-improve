"""Synthetic stage/cap/provenance checks; no heldout inputs, models or API calls."""
import contextlib
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import torch
from safetensors.torch import save_file
from olens_improve.reconstruction import JointNNLS
from test_selector_inputs import inputs, body


def load(name):
    spec=importlib.util.spec_from_file_location(name,Path('scripts')/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


exporter=load('export_judging_inputs')
combiner=load('combine_pruning')


class AnalysisWrapperTests(unittest.TestCase):
    def fixture(self,root,stage='development'):
        _,target,cb,fb,gb=inputs(stage)
        for name,value in [('manifest.json',cb),('fresh.json',fb),('gate.json',gb)]:
            (root/name).write_bytes(value)
        selection={'method':'best_n_specificity_mean','n':32,
                   'text':'- A does not own 17 books.\n- B owns 2 books.',
                   'token_count':13,'bullet_count':2,'reason':None,'fits_scope':'emitted_bullets'}
        row={k:target[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')}
        row['selections']=[selection]
        (root/'source.jsonl').write_bytes(body(row))
        (root/'conditions.json').write_bytes(body([{'method':selection['method'],'n':32}]))
        return target,row

    def export_args(self,root,gate=True):
        return SimpleNamespace(source=[root/'source.jsonl'],source_sha256=[sha256((root/'source.jsonl').read_bytes()).hexdigest()],
            manifest=root/'manifest.json',conditions=root/'conditions.json',output=root/'export.jsonl',
            provenance=root/'provenance.json',fresh_manifest=root/'fresh.json' if gate else None,
            gate=root/'gate.json' if gate else None)

    def test_legacy_dev_export_bytes_and_duplicate_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target,row=self.fixture(root)
            args=self.export_args(root,gate=False)
            duplicate=root/'duplicate.jsonl';duplicate.write_bytes(body(row))
            args.source.append(duplicate);args.source_sha256.append(sha256(duplicate.read_bytes()).hexdigest())
            with contextlib.redirect_stdout(io.StringIO()):exporter.export(args)
            parents=[{'path':str(p),'sha256':s} for p,s in zip(args.source,args.source_sha256)]
            expected={k:target[k] for k in ('cell_id','family','item_id','layer','position','split')}
            expected.update({'activation_sha256':target['activation_sha256'],'parent_sources':parents,
                             'selections':[row['selections'][0]|{'parent_source_index':0}]})
            self.assertEqual(args.output.read_bytes(),(json.dumps(expected,ensure_ascii=False)+'\n').encode())
            self.assertEqual(json.loads(args.provenance.read_text())['identical_duplicate_parent_counts'],
                             {'best_n_specificity_mean-n32':1})
            changed=json.loads(body(row));changed['selections'][0]['text']+=' Different claim.'
            duplicate.write_bytes(body(changed));args.source_sha256[-1]=sha256(duplicate.read_bytes()).hexdigest()
            args.output=root/'conflict.jsonl';args.provenance=root/'conflict-provenance.json'
            with self.assertRaisesRegex(ValueError,'Conflicting duplicated'):exporter.export(args)

    def test_validation_test_authorization_and_activation_binding(self):
        for stage in ('validation','test'):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);_,row=self.fixture(root,stage);args=self.export_args(root)
                gate=json.loads(args.gate.read_bytes())|{'authorization_scope':'blind_generation_only'}
                args.gate.write_bytes(body(gate))
                with self.assertRaisesRegex(ValueError,'Blind-generation-only'):exporter.export(args)
                args.gate=None
                with self.assertRaisesRegex(ValueError,'require exact'):exporter.export(args)
                args.gate=root/'gate.json';args.gate.write_bytes(body(gate|{'authorization_scope':'analysis'}))
                with contextlib.redirect_stdout(io.StringIO()):exporter.export(args)
                exported=json.loads(args.output.read_bytes())
                self.assertEqual(exported['selections'][0]['text'],row['selections'][0]['text'])
                self.assertEqual(json.loads(args.provenance.read_bytes())['split'],stage)
                row['activation_sha256']='wrong';args.source[0].write_bytes(body(row))
                args.source_sha256=[sha256(args.source[0].read_bytes()).hexdigest()]
                args.output=root/'bad.jsonl';args.provenance=root/'bad-provenance.json'
                with self.assertRaisesRegex(ValueError,'Source activation'):exporter.export(args)

    def test_combination_stage_guard_precedes_parent_cache_access(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.fixture(root,'validation')
            gate=json.loads((root/'gate.json').read_bytes())|{'authorization_scope':'blind_generation_only'}
            (root/'gate.json').write_bytes(body(gate))
            args=SimpleNamespace(manifest=root/'manifest.json',fresh_manifest=root/'fresh.json',gate=root/'gate.json')
            with patch.dict('os.environ',{'SLURM_JOB_ID':'synthetic'}),patch.object(combiner,'parse_args',return_value=args), \
                 patch.object(combiner,'read_rows') as parents,patch.object(combiner,'RawVectorCache') as cache:
                with self.assertRaisesRegex(ValueError,'Blind-generation-only'):combiner.main()
                parents.assert_not_called();cache.assert_not_called()

    def test_combination_validation_uses_same_dev_math_and_seed(self):
        scientific=[]
        for stage in ('development','validation'):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);target,_=self.fixture(root,stage)
                h=torch.tensor([1.,.02]);vectors={'a':torch.tensor([1.,0.]),'b':torch.tensor([0.,1.])}
                class Identity:
                    artifact_sha256='identity-fixture';ridge_c=.1
                    def whiten(self,x):return x
                score=JointNNLS.from_raw(h,vectors,Identity())
                tensor=root/'target.safetensors';save_file({'resid':h.reshape(1,-1)},str(tensor))
                fresh=json.loads((root/'fresh.json').read_bytes())
                target['activation_sha256']=sha256(h.numpy().tobytes()).hexdigest()
                for c in fresh['cells']:
                    if c['cell_id']==target['cell_id']:
                        c.update({'activation_sha256':target['activation_sha256'],'activation_row':0,'activation_tensor_path':str(tensor)})
                (root/'fresh.json').write_bytes(body(fresh));gate=json.loads((root/'gate.json').read_bytes())
                gate.update({'fresh_index_sha256':sha256(body(fresh)).hexdigest(),'authorization_scope':'analysis'})
                (root/'gate.json').write_bytes(body(gate))
                atoms=[{'phrase_id':k,'cache_key':k,'text':text} for k,text in [('a','A exists.'),('b','B exists.')]]
                parent={k:target[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')}
                parent['selections']=[{'method':'best_n_specificity_mean','n':32,'text':'- A exists.\n- B exists.',
                                      'atoms':atoms,'fits':{'exact':{'fve':score.score(('a','b'))}}}]
                (root/'source.jsonl').write_bytes(body(parent));(root/'runtime.json').write_bytes(body({'paths':{'base_snapshot':'unused'}}))
                class Cache:
                    contract={'sha256':'synthetic'};index={'a':{},'b':{}}
                    def __init__(self,*_):pass
                    def get(self,key):return vectors[key]
                class Tokenizer:
                    def __call__(self,text,**_):return {'input_ids':text.split()}
                args=SimpleNamespace(manifest=root/'manifest.json',fresh_manifest=root/'fresh.json',gate=root/'gate.json' if stage!='development' else None,
                    selectors=root/'source.jsonl',edits=None,editing_cache=None,production_cache=root/'cache',runtime=root/'runtime.json',
                    whitener_directory=root,output=root/'out',parent_method=['best_n_specificity_mean'])
                with patch.dict('os.environ',{'SLURM_JOB_ID':'synthetic'}),patch.object(combiner,'parse_args',return_value=args), \
                     patch.object(combiner,'RawVectorCache',Cache),patch.object(combiner.AutoTokenizer,'from_pretrained',return_value=Tokenizer()), \
                     patch.object(combiner.Whitener,'load',return_value=Identity()),contextlib.redirect_stdout(io.StringIO()):
                    combiner.main()
                result=json.loads((args.output/'selections.jsonl').read_bytes())
                scientific.append(result['selections'])
                self.assertEqual(len(result['selections']),5)
                self.assertEqual(result['selections'][0]['text'],parent['selections'][0]['text'])
                self.assertEqual(result['selections'][1]['bullet_count'],1)
                self.assertEqual(result['selections'][2]['bullet_count'],1)
        self.assertEqual(scientific[0],scientific[1])


if __name__=='__main__':unittest.main()
