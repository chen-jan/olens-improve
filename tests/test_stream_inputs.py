"""Synthetic stage streams and cache-history evidence; no paid/model calls."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from olens_improve.stream_inputs import stream_context,stream_rows,snapshot_payload,preserved_cache_metadata
from test_selector_inputs import inputs,rows,body


class StreamInputTests(unittest.TestCase):
    def test_cumulative_partial_stream_waits_for_complete_cells(self):
        dev,target,cb,fb,gb=inputs();stage,cohort,captures=stream_context(cb,fb,gb)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'stream.jsonl';p.write_bytes(body({'records':rows(dev)+rows(target)[:-1]})+b'{partial')
            complete,parents,historical=stream_rows([p],cohort,captures,'fixed-pool')
            self.assertFalse(complete);self.assertEqual(historical,32);self.assertEqual(parents[0]['uncommitted_tail_bytes'],8)
            p.write_bytes(body({'records':rows(dev)+rows(target)}))
            complete,_,_=stream_rows([p],cohort,captures,'fixed-pool')
            self.assertEqual(len(complete),32)
            self.assertFalse(stream_rows([p],cohort,captures,'fixed-pool',completed={'target'})[0])
            with self.assertRaises(ValueError):stream_rows([p],cohort,captures,'fixed-pool',completed={'foreign'})

    def test_historical_duplicates_revision_and_target_mutations_rejected(self):
        dev,target,cb,fb,gb=inputs();stage,cohort,captures=stream_context(cb,fb,gb)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'stream.jsonl'
            data=rows(dev)+rows(target)+[rows(dev)[0]];p.write_bytes(body({'records':data}))
            with self.assertRaisesRegex(ValueError,'Duplicate'):stream_rows([p],cohort,captures,'fixed-pool')
            for field,value in [('adapter_revision','bad'),('global_pool_id','wrong'),('activation_sha256','wrong')]:
                data=rows(dev)+rows(target);data[0][field]=value;p.write_bytes(body({'records':data}))
                with self.assertRaises(ValueError):stream_rows([p],cohort,captures,'fixed-pool')

    def test_verified_test_gate_only_source_of_snapshot_authorization(self):
        dev,target,cb,fb,gb=inputs('test')
        with self.assertRaises(ValueError):stream_context(cb,fb)
        stage,cohort,captures=stream_context(cb,fb,gb)
        originals=rows(target)
        with self.assertRaises(ValueError):snapshot_payload(originals,'test')
        payload,hashes=snapshot_payload(originals,stage,test_authorized=True)
        emitted=[json.loads(x) for x in payload.splitlines()]
        self.assertTrue(all(x['frozen_test_authorized'] for x in emitted));self.assertFalse(any('frozen_test_authorized' in x for x in originals))
        self.assertEqual(len(hashes),32)
        devrow=rows(dev)[0]|{'frozen_test_authorized':True}
        with self.assertRaises(ValueError):snapshot_payload([devrow],'development')

    def test_cache_history_copy_retains_old_timing_and_original_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cache=root/'output'/'contract';cache.mkdir(parents=True)
            old={'contract.json':body({'sha256':'original'}),'progress.json':body({'seconds':324,'status':'complete'}),
                 'raw_00000.index.json':body({'tensor_path':'original-reference'}),'usage_old.run.json':body({'seconds':300})}
            for name,b in old.items():(cache/name).write_bytes(b)
            preserved=preserved_cache_metadata(root/'output',root/'history');manifest=json.loads(Path(preserved['path']).read_text())
            (cache/'progress.json').write_bytes(body({'seconds':1,'status':'running'}))
            for i,source in enumerate(manifest['source_files']):
                copy=Path(preserved['path']).parent/f'{i:05d}-{Path(source["path"]).name}'
                self.assertEqual(sha256(copy.read_bytes()).hexdigest(),source['sha256'])
            self.assertEqual((cache/'raw_00000.index.json').read_bytes(),old['raw_00000.index.json'])


if __name__=='__main__':unittest.main()
