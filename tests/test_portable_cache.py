"""Persistence, effective-input aliases and fail-closed replay, without models/API."""
from contextlib import ExitStack
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import torch

from olens_improve.inference import Artifacts, CandidatePool, activation_hash, replay_select
from olens_improve.models import BASE_REVISION, PAIR_REVISION
from olens_improve.portable_cache import load_cache, save_cache
from olens_improve.__main__ import main


class Tokenizer:
    all_special_ids = []
    def __call__(self, text, **kwargs):
        return {'input_ids':[int(sha256(word.encode()).hexdigest()[:6],16) for word in text.split()]}


class Whitener:
    artifact_sha256 = 'w'*64
    ridge_c = .1
    def whiten(self, value): return value


class Reader:
    def __init__(self): self.calls = 0
    def encode(self, texts, layer):
        from olens_improve.reconstruction import ar_token_ids
        self.calls += 1
        ids = [ar_token_ids(Tokenizer(),text)[1][:32] for text in texts]
        rows = torch.stack([torch.ones(5120)*(i+1) for i in range(len(texts))])
        return rows, [{'input_ids':tokens,'tag_ids':[7,8]} for tokens in ids]


class PortableCacheTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        checkpoint = self.root/'ar'; (checkpoint/'lora').mkdir(parents=True)
        torch.save({'tag_ids':torch.tensor([[7,8]]),'layers':[44]},checkpoint/'heads.pt')
        (checkpoint/'meta.json').write_text(json.dumps({'config':{'head_layer_norm':True}}))
        (checkpoint/'lora/adapter_model.safetensors').write_bytes(b'fixture adapter')
        (checkpoint/'lora/adapter_config.json').write_text('{}')
        self.artifacts = Artifacts('fixture base',ar_checkpoint=str(checkpoint),whitener_directory='fixture whiteners',device='cpu')
        self.h = torch.ones(5120)
        self.reader = Reader(); self.stack = ExitStack()
        self.stack.enter_context(patch('olens_improve.inference.token_counter',return_value=(Tokenizer(),lambda x:len(x.split()))))
        self.stack.enter_context(patch('olens_improve.inference.FrozenAR.load',return_value=self.reader))
        self.stack.enter_context(patch('olens_improve.inference.release_reader'))
        self.stack.enter_context(patch('olens_improve.inference.Whitener.load',return_value=Whitener()))

    def tearDown(self):
        self.stack.close()
        for path in self.root.rglob('*'):
            if path.is_dir(): path.chmod(0o755)
            else: path.chmod(0o644)
        self.temp.cleanup()

    def pool(self,texts):
        rows = [dict(text=t,sample_index=i,layer=44,activation_sha256=activation_hash(self.h),
                     base_revision=BASE_REVISION,adapter_revision=PAIR_REVISION,original_field={'kept':i})
                for i,t in enumerate(texts)]
        return CandidatePool.from_records(rows,self.h,44,source_sha256='s'*64)

    def test_saved_cache_relocates_and_replays_without_encoding_identically(self):
        pool = self.pool(['- Nora owns books.','- Nora returns books.'])
        path = self.root/'new-cache'
        original = replay_select(self.artifacts,pool,self.h,encode_missing=True,save_cache_directory=path)
        self.assertEqual(self.reader.calls,1)
        moved = self.root/'moved-cache'; shutil.copytree(path,moved)
        replay = replay_select(self.artifacts,pool,self.h,cache_directory=moved)
        self.assertEqual(self.reader.calls,1)
        self.assertEqual(replay['phrase_ids'],original['phrase_ids'])
        self.assertEqual(replay['fits'],original['fits'])
        self.assertEqual(replay['execution']['missing_effective_keys_encoded'],0)
        usage = json.loads((moved/'usage.json').read_text())
        self.assertEqual(usage['source']['records'],list(pool.records))
        self.assertEqual(load_cache(moved).contract,load_cache(path).contract)

    def test_suffix_aliases_keep_source_variants_and_invalid_atom_not_zero(self):
        prefix = ' '.join('word'+str(i) for i in range(32))
        pool = self.pool(['- '+prefix+' alpha.','- '+prefix+' beta.','- <think>'])
        path = self.root/'alias-cache'
        result = replay_select(self.artifacts,pool,self.h,encode_missing=True,save_cache_directory=path)
        usage = json.loads((path/'usage.json').read_text())['atoms']
        self.assertEqual(result['saved_cache']['unique_vectors'],1)
        self.assertEqual(len(usage),3)
        self.assertNotEqual(usage[0]['text'],usage[1]['text'])
        self.assertEqual(usage[0]['cache_key'],usage[1]['cache_key'])
        self.assertTrue(usage[0]['truncated'])
        self.assertIsNone(usage[2]['cache_key'])
        self.assertEqual(usage[2]['reason'],'empty_after_AR_cleanup')
        self.assertEqual(len({row['source_phrase_id'] for row in usage}),3)

    def test_inherited_hits_copied_readonly_and_new_keys_encoded_once(self):
        parent = self.root/'parent'
        replay_select(self.artifacts,self.pool(['- Nora owns books.']),self.h,encode_missing=True,save_cache_directory=parent)
        before = {p.name:p.read_bytes() for p in parent.iterdir()}
        child = self.root/'child'
        result = replay_select(self.artifacts,self.pool(['- Nora owns books.','- Library closes early.']),self.h,
            cache_directory=parent,encode_missing=True,save_cache_directory=child)
        self.assertEqual(result['execution']['missing_effective_keys_encoded'],1)
        self.assertEqual(result['saved_cache']['unique_vectors'],2)
        self.assertEqual(before,{p.name:p.read_bytes() for p in parent.iterdir()})
        rows = json.loads((child/'raw_00000.index.json').read_text())['vectors']
        self.assertEqual({r['origin']['kind'] for r in rows},{'inherited_readonly_cache','new_portable_encoding'})
        parent.rename(self.root/'old-parent')
        replay = replay_select(self.artifacts,self.pool(['- Nora owns books.','- Library closes early.']),self.h,cache_directory=child)
        self.assertEqual(replay['fits'],result['fits'])

    def test_preflight_existing_and_baseline_paths_prevent_model_or_vector_load(self):
        existing = self.root/'exists'; existing.mkdir()
        with patch('olens_improve.inference.FrozenAR.load') as load:
            with self.assertRaises(FileExistsError):
                replay_select(self.artifacts,self.pool(['- Books.']),self.h,save_cache_directory=existing)
            with self.assertRaises(ValueError):
                replay_select(self.artifacts,self.pool(['- Books.']),self.h,method='capped_n1',save_cache_directory=self.root/'bad')
            load.assert_not_called()
        with patch('olens_improve.__main__.read_vector') as read:
            base=['replay','--activation','missing','--pool','missing','--artifacts','missing','--output',str(self.root/'out')]
            with self.assertRaises(FileExistsError): main(base+['--save-cache',str(existing)])
            with self.assertRaises(ValueError): main(base+['--method','raw_n1','--save-cache',str(self.root/'bad')])
            read.assert_not_called()

    def test_partial_corrupt_or_wrong_input_cache_rejected(self):
        path = self.root/'complete'
        replay_select(self.artifacts,self.pool(['- Books.']),self.h,encode_missing=True,save_cache_directory=path)
        contract = load_cache(path).contract
        for value in (torch.ones(5121),torch.full((5120,),float('nan'))):
            row = next(iter(load_cache(path).index.values())); key = row['cache_key']
            with self.assertRaises(ValueError):
                save_cache(self.root/'invalid',contract,{key:dict(row,vector=value)},[],{})
            self.assertFalse((self.root/'invalid').exists())
        partial = self.root/'partial'; partial.mkdir(); (partial/'portable_cache.claim.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'incomplete'): load_cache(partial)
        path.chmod(0o755); (path/'usage.json').chmod(0o644); (path/'usage.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'identity'): load_cache(path)

    def test_actual_encoder_ids_must_match_before_cache_publication(self):
        self.reader.encode = lambda texts,layer:(torch.ones((len(texts),5120)),[{'input_ids':[999],'tag_ids':[7,8]} for _ in texts])
        path = self.root/'wrong'
        with self.assertRaisesRegex(ValueError,'Actual AR encoding'):
            replay_select(self.artifacts,self.pool(['- Books.']),self.h,encode_missing=True,save_cache_directory=path)
        self.assertFalse(path.exists())

    def test_empty_invalid_pool_cache_and_legacy_cache_stay_distinct(self):
        path = self.root/'empty'
        result = replay_select(self.artifacts,self.pool(['- <think>']),self.h,encode_missing=True,save_cache_directory=path)
        self.assertEqual(result['saved_cache']['unique_vectors'],0)
        self.assertEqual(self.reader.calls,0)
        self.assertEqual(load_cache(path).index,{})
        complete = self.root/'original'
        replay_select(self.artifacts,self.pool(['- Books.']),self.h,encode_missing=True,save_cache_directory=complete)
        legacy = self.root/'legacy'; shutil.copytree(complete,legacy); legacy.chmod(0o755)
        for name in ('portable_cache.json','portable_cache.claim.json'): (legacy/name).unlink()
        index = legacy/'raw_00000.index.json'; index.chmod(0o644)
        rows = json.loads(index.read_text()); rows['tensor_path']=str(legacy/'raw_00000.safetensors')
        index.write_text(json.dumps(rows))
        replay = replay_select(self.artifacts,self.pool(['- Books.']),self.h,cache_directory=legacy)
        self.assertEqual(replay['execution']['missing_effective_keys_encoded'],0)
        self.assertEqual(self.reader.calls,1)

    def test_changed_local_artifact_contract_rejected_before_encoding(self):
        path = self.root/'contract-cache'
        p = self.pool(['- Books.'])
        replay_select(self.artifacts,p,self.h,encode_missing=True,save_cache_directory=path)
        (Path(self.artifacts.ar_checkpoint)/'lora/adapter_model.safetensors').write_bytes(b'changed weights')
        with patch('olens_improve.inference.FrozenAR.load') as load:
            with self.assertRaisesRegex(ValueError,'exact local AR artifacts'):
                replay_select(self.artifacts,p,self.h,cache_directory=path,encode_missing=True)
            load.assert_not_called()

    def test_falsy_portable_receipts_cannot_fall_back_to_legacy_loading(self):
        path = self.root/'receipt-cache'
        replay_select(self.artifacts,self.pool(['- Books.']),self.h,encode_missing=True,save_cache_directory=path)
        receipt = path/'portable_cache.json'; receipt.chmod(0o644)
        for malformed in ({},None,[]):
            receipt.write_text(json.dumps(malformed))
            with self.assertRaisesRegex(ValueError,'completed receipt'):
                load_cache(path)


if __name__ == '__main__': unittest.main()
