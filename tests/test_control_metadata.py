"""Metadata augmentation preserves all frozen assignments without reading labels."""
import json
from pathlib import Path
import sys
import unittest
from test_selector_inputs import cell
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_control_metadata import augment


class MetadataTests(unittest.TestCase):
    def test_exact_read_plan_kind_augmentation_without_redraw(self):
        donor=cell('dev','development','g0');target=cell('target','validation','g1')
        controls={'control_bank':{'dev':{k:v for k,v in donor.items() if k not in ('adapter_disabled','activation_sha256','cell_id')}},
                  'control_cell_ids_by_target':{'dev':['dev2'],'dev2':['dev'],'target':['dev']},'seed':20261010}
        other=cell('dev2','development','g2');controls['control_bank']['dev2']={k:v for k,v in other.items() if k not in ('adapter_disabled','activation_sha256','cell_id')}
        plan={'cells':[donor,other,target]};fresh=json.loads(json.dumps(plan))
        for c in fresh['cells']:del c['read_position_kind']
        result=augment(controls,plan,fresh,{'source_sha256':'fixture'})
        self.assertEqual(result['control_cell_ids_by_target'],controls['control_cell_ids_by_target'])
        self.assertEqual(result['control_bank'],controls['control_bank'])
        self.assertEqual(result['target_metadata']['target']['read_position_kind'],'final')
        self.assertNotIn('target_metadata',controls)
        wrong=json.loads(json.dumps(plan));wrong['cells'][-1]['read_position_kind']='other'
        with self.assertRaises(ValueError):augment(controls,wrong,fresh,{})
        wrong=json.loads(json.dumps(fresh));wrong['cells'][-1]['group_id']='bad'
        with self.assertRaises(ValueError):augment(controls,plan,wrong,{})


if __name__=='__main__':unittest.main()
