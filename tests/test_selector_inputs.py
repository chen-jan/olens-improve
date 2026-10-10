"""Synthetic stage/journal/control fixtures; no real VAL/TEST artifacts opened."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from olens_improve.selector_inputs import load_selector_inputs, validate_controls
from olens_improve.models import BASE_REVISION, PAIR_REVISION


def body(value): return (json.dumps(value)+'\n').encode()

def cell(cid, stage, group):
    return {'cell_id': cid, 'family': 'toy', 'item_id': cid, 'layer': 44, 'position': 7,
            'group_id': group, 'split': stage, 'activation_sha256': 'a'*64,
            'adapter_disabled': True, 'read_position_kind': 'final'}

def rows(c):
    return [{**{k: c[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')},
             'sample_index': i, 'text': '- Synthetic claim.', 'base_revision': BASE_REVISION,
             'adapter_revision': PAIR_REVISION, 'global_pool_id': 'fixed-pool'} for i in range(32)]

def write_journal(path, records):
    raw = body({'kind': 'batch', 'records': records}); path.write_bytes(raw)
    path.with_suffix('.status.json').write_bytes(body({'status':'complete','journal_sha256':sha256(raw).hexdigest()}))
    return raw


def inputs(stage='validation'):
    dev = cell('dev', 'development', 'g0'); target = cell('target', stage, 'g1')
    cohort = {'split': stage, 'cells': [target]}
    if stage == 'test': cohort['frozen_test_authorized'] = True
    cb, fb = body(cohort), body({'cells':[dev,target]})
    gate = {'manifest_sha256':sha256(cb).hexdigest(),'fresh_index_sha256':sha256(fb).hexdigest(),
            'recapture_status':'passed','production_generation_authorized':True,'authorized_cells':1,
            'maximum_samples_per_cell':32,'frozen_test_authorized':stage=='test'}
    return dev,target,cb,fb,body(gate)


class SelectorInputTests(unittest.TestCase):
    def test_cumulative_history_filtered_only_after_full_duplicate_validation(self):
        dev,target,cb,fb,gb=inputs()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'journal.jsonl';write_journal(p,rows(dev)+rows(target))
            stage,cohort,captures,records,sources,excluded=load_selector_inputs([p],cb,fb,gb)
            self.assertEqual(stage,'validation');self.assertEqual(set(records),{'target'})
            self.assertEqual(excluded,32);self.assertEqual(len(sources),1)
            write_journal(p,rows(dev)+rows(target)+[rows(dev)[0]])
            with self.assertRaisesRegex(ValueError,'Duplicate'):load_selector_inputs([p],cb,fb,gb)

    def test_stage_gate_binding_and_sealed_test_are_mandatory(self):
        dev,target,cb,fb,gb=inputs('test')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'journal.jsonl';write_journal(p,rows(target))
            with self.assertRaises(ValueError):load_selector_inputs([p],cb,fb)
            wrong=json.loads(gb);wrong['manifest_sha256']='0'*64
            with self.assertRaises(ValueError):load_selector_inputs([p],cb,fb,body(wrong))
            wrong=json.loads(gb);wrong['frozen_test_authorized']=False
            with self.assertRaises(ValueError):load_selector_inputs([p],cb,fb,body(wrong))
            mixed=json.loads(cb);mixed['cells'].append(dev)
            with self.assertRaises(ValueError):load_selector_inputs([p],body(mixed),fb,gb)
            self.assertEqual(load_selector_inputs([p],cb,fb,gb)[0],'test')

    def test_flat_snapshot_requires_exact_cohort_and_immutable_terminal_parents(self):
        dev,target,cb,fb,gb=inputs()
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/'journal.jsonl';parent_bytes=write_journal(parent,rows(dev)+rows(target))
            flat=Path(d)/'flat.jsonl';flat_bytes=b''.join(body(r) for r in rows(target));flat.write_bytes(flat_bytes)
            metadata={'flat_sha256':sha256(flat_bytes).hexdigest(),'cohort_manifest_sha256':sha256(cb).hexdigest(),
                      'parent_journal_sha256':{str(parent):sha256(parent_bytes).hexdigest()}}
            flat.with_suffix('.manifest.json').write_bytes(body(metadata))
            self.assertEqual(load_selector_inputs([flat],cb,fb,gb)[5],0)
            parent.write_bytes(parent_bytes+b'\n')
            with self.assertRaises(ValueError):load_selector_inputs([flat],cb,fb,gb)

    def test_complete_pool_identity_and_terminal_tail_fail_closed(self):
        dev,target,cb,fb,gb=inputs('development')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'journal.jsonl';write_journal(p,rows(target)[:-1])
            with self.assertRaises(ValueError):load_selector_inputs([p],cb,fb)
            bad=rows(target);bad[0]['activation_sha256']='0'*64;write_journal(p,bad)
            with self.assertRaisesRegex(ValueError,'activation'):load_selector_inputs([p],cb,fb)
            raw=write_journal(p,rows(target));p.write_bytes(raw[:-1])
            with self.assertRaisesRegex(ValueError,'tail'):load_selector_inputs([p],cb,fb)

    def test_wrong_verbalizer_revision_or_mixed_historical_pool_rejected(self):
        dev,target,cb,fb,gb=inputs()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'journal.jsonl'
            for field,value in [('base_revision','wrong'),('adapter_revision','wrong'),('global_pool_id','other-pool')]:
                data=rows(dev)+rows(target);data[0][field]=value;write_journal(p,data)
                with self.assertRaisesRegex(ValueError,'revisions|pool'):load_selector_inputs([p],cb,fb,gb)

    def test_controls_only_frozen_dev_matching_site_and_foreign_groups(self):
        dev,target,cb,fb,gb=inputs()
        controls={'control_cell_ids_by_target':{'target':['dev']},'control_bank':{'dev':dict(dev)},
                  'target_metadata':{'target':dict(target)}}
        cohort={'target':target};captures={'target':target,'dev':dev}
        self.assertEqual(validate_controls(controls,['target'],cohort,captures),{'target':['dev']})
        for field,value in [('split','validation'),('group_id','g1'),('read_position_kind','other')]:
            bad=json.loads(json.dumps(controls));bad['control_bank']['dev'][field]=value
            with self.assertRaises(ValueError):validate_controls(bad,['target'],cohort,captures)
        bad=json.loads(json.dumps(controls));bad['control_cell_ids_by_target']['target']=['dev','dev']
        with self.assertRaises(ValueError):validate_controls(bad,['target'],cohort,captures)
        bad=json.loads(json.dumps(controls));bad['control_cell_ids_by_target']['target']=[]
        with self.assertRaisesRegex(ValueError,'nonempty'):validate_controls(bad,['target'],cohort,captures)


if __name__ == '__main__':unittest.main()
