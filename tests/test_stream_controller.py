"""Frozen stream orchestration with a fake cache-hit encoder, no model/API calls."""
from hashlib import sha256
import fcntl
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_selector_inputs import inputs,rows,body
from olens_improve.ar_cache import digest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import stream_ar


class ControllerTests(unittest.TestCase):
    def test_cache_hit_stage_snapshot_resume_and_foreign_state_rejection(self):
        dev,target,cb,fb,gb=inputs()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pool=root/'pool';pool.mkdir();snap=root/'snap';out=root/'out';cache=out/'cache';cache.mkdir(parents=True)
            checkpoint=root/'checkpoint';(checkpoint/'lora').mkdir(parents=True)
            contract={}
            for name,field in [('heads.pt','head_sha256'),('meta.json','meta_sha256'),('lora/adapter_model.safetensors','adapter_sha256'),('lora/adapter_config.json','adapter_config_sha256')]:
                (checkpoint/name).write_bytes(name.encode());contract[field]=sha256(name.encode()).hexdigest()
            contract['sha256']=digest(contract);(cache/'contract.json').write_bytes(body(contract))
            old_progress=body({'status':'complete','seconds':324});(cache/'progress.json').write_bytes(old_progress)
            (pool/'pool.json').write_bytes(body({'global_pool_id':'fixed-pool'}))
            (pool/'shard-000-of-001.jsonl').write_bytes(body({'records':rows(dev)+rows(target)}))
            for name,value in [('cohort.json',cb),('fresh.json',fb),('gate.json',gb)]: (root/name).write_bytes(value)
            argv=['stream_ar','--pool',str(pool),'--cells-manifest',str(root/'cohort.json'),'--fresh-manifest',str(root/'fresh.json'),
                  '--gate',str(root/'gate.json'),'--checkpoint',str(checkpoint),'--output',str(out),'--snapshots',str(snap),
                  '--batch-size','128','--once']
            called=[]
            def fake_encoder(args,ar):
                with (out/'stream_writer.lock').open('a+') as competing:
                    with self.assertRaises(BlockingIOError):fcntl.flock(competing,fcntl.LOCK_EX|fcntl.LOCK_NB)
                called.append(args);path=Path(args.input[0]);payload=path.read_bytes();usage=cache/'usage_fixture.jsonl';usage.write_text('{}\n')
                (cache/'usage_fixture.run.json').write_bytes(body({'status':'complete','source_inputs':[{'path':str(path),'sha256':sha256(payload).hexdigest()}],
                    'usage_path':str(usage),'new_unique_vectors':0,'seconds':.25}))
                (cache/'progress.json').write_bytes(body({'status':'complete','seconds':.25}))
                return None
            with patch.object(sys,'argv',argv),patch.dict('os.environ',{'SLURM_JOB_ID':'synthetic'}),patch.object(stream_ar,'encode_snapshot',side_effect=fake_encoder):
                stream_ar.main();self.assertEqual(len(called),1)
                stream_ar.main();self.assertEqual(len(called),1)
                state=json.loads((snap/'state.json').read_text());self.assertEqual(state['status'],'complete')
                state['completed_cell_ids']=[];(snap/'state.json').write_bytes(body(state))
                stream_ar.main();self.assertEqual(len(called),1) # crash after run commit: preserve its timing
            emitted=[json.loads(s) for s in next(snap.glob('*.jsonl')).read_text().splitlines()]
            self.assertTrue(all(r['cell_id']=='target' and r['split']=='validation' for r in emitted))
            self.assertEqual(emitted[0]['text'],rows(target)[0]['text'])
            history=json.loads((snap/'spec.json').read_text())['preserved_cache_metadata']
            self.assertIn(old_progress,[p.read_bytes() for p in Path(history['path']).parent.glob('*progress.json')])
            state=json.loads((snap/'state.json').read_text());state['completed_cell_ids']=['foreign'];(snap/'state.json').write_bytes(body(state))
            with patch.object(sys,'argv',argv),patch.dict('os.environ',{'SLURM_JOB_ID':'synthetic'}):
                with self.assertRaisesRegex(ValueError,'off-cohort'):stream_ar.main()
            with (out/'stream_writer.lock').open('a+') as available:
                fcntl.flock(available,fcntl.LOCK_EX|fcntl.LOCK_NB) # released even on preflight failure


if __name__=='__main__':unittest.main()
