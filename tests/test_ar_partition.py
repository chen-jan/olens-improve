import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
import torch
from safetensors.torch import save_file
from olens_improve.ar_cache import digest,vector_key
from olens_improve.ar_partition import partition_for,read_cache,merge_catalog,validate_stage


class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.contract={'model':'fixture'};self.contract['sha256']=digest(self.contract)
        self.rows=[]
        for i in range(20):
            self.rows.append({'cache_key':vector_key(self.contract['sha256'],[10],[i]),
                              'tag_ids':[10],'scored_token_ids':[i],'layer':20,'row':0,
                              'execution':{'batch_size':128}})
    def tearDown(self):
        for p in self.root.iterdir():
            if p.is_dir():p.chmod(0o755)
        self.tmp.cleanup()
    def cache(self,name,rows):
        p=self.root/name;p.mkdir()
        (p/'contract.json').write_text(json.dumps(self.contract))
        tensor=p/'vectors.safetensors';save_file({'vectors':torch.arange(len(rows)*3).reshape(len(rows),3).float()},str(tensor),
                                                metadata={'contract_sha256':self.contract['sha256']})
        (p/'raw_00000.index.json').write_text(json.dumps({'contract_sha256':self.contract['sha256'],
             'tensor_path':str(tensor),'vectors':[r|{'row':i} for i,r in enumerate(rows)]}))
        return p
    def plan(self):
        inherited=self.cache('old',self.rows[:2]);_,old,sources=read_cache(inherited)
        partitions=[];workers=[]
        for i in range(2):
            rows=[r for r in self.rows[2:] if partition_for(r['cache_key'],2)==i]
            path=self.root/f'part{i}.jsonl';body=''.join(json.dumps(r)+'\n' for r in rows).encode();path.write_bytes(body)
            partitions.append({'path':str(path),'sha256':sha256(body).hexdigest()})
            worker=self.cache(f'worker{i}',rows)
            (worker/'usage_test.run.json').write_text(json.dumps({'status':'complete','source_inputs':[{'sha256':sha256(body).hexdigest()}]}))
            workers.append(worker)
        usage=self.root/'usage.jsonl';usage.write_text('{"source":"original candidate"}\n')
        return {'contract':self.contract,'partition_count':2,'partitions':partitions,'new_keys':18,
                'inherited_keys_sha256':digest(sorted(old)),'inherited_sources':sources,
                'usage':{'path':str(usage),'sha256':sha256(usage.read_bytes()).hexdigest()}},inherited,workers
    def test_effective_key_partition_is_deterministic(self):
        for r in self.rows:self.assertEqual(partition_for(r['cache_key'],4),partition_for(r['cache_key'],4))
        with self.assertRaises(ValueError):partition_for(self.rows[0]['cache_key'],0)
    def test_merge_preserves_original_vector_rows_and_provenance(self):
        plan,old,workers=self.plan();dest=self.root/'merged';meta=merge_catalog(plan,old,workers,dest)
        _,expected,_=read_cache(old)
        for worker in workers:expected.update(read_cache(worker)[1])
        _,actual,_=read_cache(dest)
        self.assertEqual(actual,expected);self.assertEqual(meta['vectors'],20)
        self.assertEqual(meta['tensor_copies'],0)
        self.assertEqual((dest/'usage_partition_prepared.jsonl').read_bytes(),Path(plan['usage']['path']).read_bytes())
    def test_cross_writer_duplicates_rejected(self):
        plan,old,workers=self.plan()
        workers[0]=self.cache('duplicate',self.rows[:2])
        with self.assertRaises(ValueError):merge_catalog(plan,old,workers,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
    def test_zero_copy_catalog_can_be_inherited_by_next_stage(self):
        plan,old,workers=self.plan()
        inherited=self.root/'first-catalog';merge_catalog(plan,old,workers,inherited)
        contract,previous,sources=read_cache(inherited)
        new_rows=[self.rows[0]|{'cache_key':vector_key(contract['sha256'],[10],[i]),
                             'scored_token_ids':[i]} for i in range(100,105)]
        next_parts=[];next_workers=[]
        for i in range(2):
            rows=[r for r in new_rows if partition_for(r['cache_key'],2)==i]
            path=self.root/f'next-part{i}.jsonl';body=''.join(json.dumps(r)+'\n' for r in rows).encode();path.write_bytes(body)
            next_parts.append({'path':str(path),'sha256':sha256(body).hexdigest()})
            worker=self.cache(f'next-worker{i}',rows)
            (worker/'usage_next.run.json').write_text(json.dumps({'status':'complete','source_inputs':[{'sha256':sha256(body).hexdigest()}]}))
            next_workers.append(worker)
        next_plan=plan|{'inherited_keys_sha256':digest(sorted(previous)),'inherited_sources':sources,
                       'partitions':next_parts,'new_keys':5}
        final=self.root/'second-catalog';metadata=merge_catalog(next_plan,inherited,next_workers,final)
        _,actual,_=read_cache(final)
        self.assertEqual(len(actual),25)
        self.assertEqual({k:actual[k] for k in previous},previous)
        self.assertEqual(metadata['tensor_copies'],0)
        self.assertFalse(list(final.glob('*.safetensors')))
    def test_missing_worker_and_mutated_contract_rejected(self):
        plan,old,workers=self.plan()
        with self.assertRaises(ValueError):merge_catalog(plan,old,workers[:1],self.root/'bad')
        p=workers[0]/'contract.json';d=json.loads(p.read_text());d['model']='changed';p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):merge_catalog(plan,old,workers,self.root/'bad')
    def test_key_input_tampering_and_row_bounds_rejected(self):
        p=self.cache('tampered',[self.rows[0]]);f=p/'raw_00000.index.json';d=json.loads(f.read_text())
        d['vectors'][0]['scored_token_ids']=[999];f.write_text(json.dumps(d))
        with self.assertRaises(ValueError):read_cache(p)
        d['vectors'][0]=self.rows[0]|{'row':3};f.write_text(json.dumps(d))
        with self.assertRaises(ValueError):read_cache(p)
    def test_missing_terminal_worker_record_rejected(self):
        plan,old,workers=self.plan();(workers[0]/'usage_test.run.json').unlink()
        with self.assertRaises(ValueError):merge_catalog(plan,old,workers,self.root/'bad')
    def test_stage_gate_binds_exact_cohort_capture_and_test_freeze(self):
        cell={'cell_id':'a','family':'role','item_id':'item','layer':44,'position':9,
              'split':'validation','group_id':'pair'}
        manifest={'split':'validation','cells':[cell]};fresh={'cells':[cell|{'adapter_disabled':True}]}
        gate={'manifest_sha256':'m','fresh_index_sha256':'f','recapture_status':'passed',
              'production_generation_authorized':True,'authorized_cells':1,'maximum_samples_per_cell':32}
        self.assertEqual(validate_stage(manifest,'m',fresh,'f',gate)[0],'validation')
        for modified in [gate|{'manifest_sha256':'other'},gate|{'dry_run_only':True}]:
            with self.assertRaises(ValueError):validate_stage(manifest,'m',fresh,'f',modified)
        foreign={'cells':[cell|{'group_id':'different','adapter_disabled':True}]}
        with self.assertRaises(ValueError):validate_stage(manifest,'m',foreign,'f',gate)
        test_manifest={'split':'test','cells':[cell|{'split':'test'}]}
        test_fresh={'cells':[cell|{'split':'test','adapter_disabled':True}]}
        with self.assertRaises(ValueError):validate_stage(test_manifest,'m',test_fresh,'f',gate)
        self.assertEqual(validate_stage(test_manifest|{'frozen_test_authorized':True},'m',test_fresh,'f',
                         gate|{'frozen_test_authorized':True})[0],'test')


if __name__=='__main__':unittest.main()
