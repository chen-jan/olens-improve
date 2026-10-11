import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from expanded_gpu_enqueue_edits import task_from_descriptor


class GPUEnqueueTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        def artifact(name,payload):
            p=self.root/name;p.write_text(json.dumps(payload)+'\n')
            return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        self.cohort=artifact('cohort.json',{'cells':[{'cell_id':'a'},{'cell_id':'b'}]})
        self.proposals=artifact('proposals.json',[])
        runtime=artifact('runtime.json',{'paths':{'base_snapshot':'cached'}})
        seal=artifact('seal.json',{'status':'sealed'})
        self.cfg=dict(python='python',runtime=runtime['path'],sealed_manifest=seal['path'],checkpoint='checkpoint',
            production_cache='read-only-cache',edit_cache='new-edit-cache',whitener_directory='matching-whiteners')
        self.fresh={'a':{'family':'chain_intermediates'},'b':{'family':'chain_intermediates'},'c':{'family':'multihop_mt'}}
        self.manifest={'fresh_manifest':{'path':'original-fresh.json'}}
        self.desc=dict(id='chain-r1',family='chain_intermediates',round=1,proposals=self.proposals,cells_manifest=self.cohort,
            history=None,output='${OLENS_DATA_ROOT}/expansion-v1/editing-scores/round1/chain_intermediates')
        self.path=self.root/'descriptor.json'

    def task(self):
        self.path.write_text(json.dumps(self.desc))
        return task_from_descriptor(self.path,self.cfg,self.manifest,self.fresh)

    def test_exact_family_is_pinned_fixed_ar_task(self):
        task=self.task()
        self.assertEqual(task['editing_round'],1)
        self.assertIn('scripts/expanded_encode_edits.py',task['command'])
        self.assertEqual(task['command'][task['command'].index('--batch-size')+1],'128')
        self.assertIn(self.proposals,task['pins'])

    def test_incomplete_or_foreign_family_rejected(self):
        for keys in (['a'],['a','c'],['a','a']):
            p=Path(self.cohort['path']);p.write_text(json.dumps({'cells':[{'cell_id':k} for k in keys]}))
            self.cohort['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):self.task()

    def test_changed_proposal_hash_rejected(self):
        Path(self.proposals['path']).write_text('changed')
        with self.assertRaises(ValueError):self.task()

    def test_round2_requires_complete_round1_history(self):
        p=self.root/'scored_candidates.jsonl';p.write_text('{}\n')
        self.desc.update(round=2,history={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        (self.root/'status.json').write_text(json.dumps({'status':'running','cells':2}))
        with self.assertRaises(ValueError):self.task()

    def test_historical_output_root_rejected(self):
        self.desc['output']='${OLENS_DATA_ROOT}/selections/old-study'
        with self.assertRaises(ValueError):self.task()
