import json
from pathlib import Path
import tempfile
import unittest
import torch
from safetensors.torch import save_file
from olens_improve.gpu_resume import recover_journal, validate_vector_shards


class GPUResumeTests(unittest.TestCase):
    def test_partial_tail_recovered_missing_unit_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'readouts.jsonl'
            committed=json.dumps(dict(cell_id='a',spec_sha256='spec'))+'\n'
            tail=b'{"cell_id":"b",'
            path.write_bytes(committed.encode()+tail)
            self.assertEqual(recover_journal(path,'spec',{'a','b'}),{'a'})
            self.assertEqual(path.read_bytes(),committed.encode())
            self.assertEqual(next(path.parent.glob('*.uncommitted-*')).read_bytes(),tail)
            self.assertEqual(recover_journal(path,'spec',{'a','b'}),{'a'})

    def test_duplicate_wrong_spec_and_corrupt_committed_line_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'readouts.jsonl'
            valid=json.dumps(dict(cell_id='a',spec_sha256='spec'))+'\n'
            for body in (valid+valid,valid.replace('spec','different'),valid+'{invalid}\n'):
                path.write_text(body)
                with self.assertRaises((ValueError,json.JSONDecodeError)):
                    recover_journal(path,'spec',{'a'})

    def test_tensor_before_index_is_not_completion_and_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            save_file({'vectors':torch.zeros(1,5120)},str(root/'raw_00000.safetensors'))
            self.assertEqual(validate_vector_shards(root,'spec'),(set(),1))
            (root/'raw_00000.index.json').write_text(json.dumps(dict(contract_sha256='spec',
                tensor_path=str(root/'raw_00000.safetensors'),vectors=[dict(row=0,cache_key='a')])))
            self.assertEqual(validate_vector_shards(root,'spec'),({'a'},1))
            save_file({'vectors':torch.full((1,5120),float('nan'))},str(root/'raw_00000.safetensors'))
            with self.assertRaises(ValueError):validate_vector_shards(root,'spec')

    def test_index_before_tensor_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'raw_00000.index.json').write_text(json.dumps(dict(contract_sha256='spec',
                tensor_path=str(root/'raw_00000.safetensors'),vectors=[dict(row=0,cache_key='a')])))
            with self.assertRaises(ValueError):validate_vector_shards(root,'spec')
