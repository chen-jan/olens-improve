import copy
from pathlib import Path
import sys
import json
import hashlib
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from expanded_final_reconstruction_gate import editor_dispatch_projection,task_signature,REPLAYS,FAMILIES,freeze_native_authority,unchanged_pins


class FinalSecondaryGateTests(unittest.TestCase):
    def fixture(self):
        tasks=[{'id':f'editing-round{r}-{f}-v1','command':['python','producer','--round',str(r)]}
            for r in (1,2)for f in FAMILIES]
        done={t['id']:{'task_sha256':task_signature(t),'seconds':1.,'finished_unix':1791686528.,'job_id':'25536297'}for t in tasks}
        return {'tasks':tasks},{'completed_tasks':done}

    def test_exact_eight_successful_tasks_retained(self):
        queue,service=self.fixture();projection=editor_dispatch_projection(queue,service)
        self.assertEqual(projection['tasks'],queue['tasks']);self.assertEqual(projection['completed_tasks'],service['completed_tasks'])
        self.assertEqual(len(REPLAYS),8)
        self.assertTrue(all(d.name.startswith('shard-')for d in REPLAYS[:-1]))
        self.assertEqual(REPLAYS[-1].name,'shard0')

    def test_missing_and_duplicate_task_cannot_freeze(self):
        queue,service=self.fixture()
        with self.assertRaises(ValueError):editor_dispatch_projection({'tasks':queue['tasks'][:-1]},service)
        with self.assertRaises(ValueError):editor_dispatch_projection({'tasks':queue['tasks']+[queue['tasks'][0]]},service)

    def test_mutated_argv_or_missing_completion_cannot_freeze(self):
        queue,service=self.fixture();changed=copy.deepcopy(queue);changed['tasks'][0]['command'].extend(['--whitener-directory','changed'])
        with self.assertRaises(ValueError):editor_dispatch_projection(changed,service)
        service['completed_tasks'].pop(queue['tasks'][0]['id'])
        with self.assertRaises(ValueError):editor_dispatch_projection(queue,service)

    def test_mutable_heartbeat_and_other_tasks_do_not_replace_authority(self):
        queue,service=self.fixture();original=editor_dispatch_projection(queue,service)
        queue['tasks'].append({'id':'likelihood-n8-two-controls-v1','command':['unrelated']});service['last_check_unix']=999.
        self.assertEqual(editor_dispatch_projection(queue,service),original)

    def test_changed_native_output_receipt_or_terminal_state_cannot_become_new_authority(self):
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);native=root/'native.json';receipt=root/'receipt.json';state=root/'state.json'
            native.write_text('{"approved_quality":true}');receipt.write_text('{"sealed":true}')
            terminal={'status':'complete_pending_root_review','scientific_inputs_validated_complete':True,
                'output_sha256':digest(native),'receipt_sha256':digest(receipt)}
            state.write_text(json.dumps(terminal));state_sha=digest(state);pins=freeze_native_authority(state,native,receipt,terminal,state_sha)
            for target in (native,receipt,state):
                old=target.read_bytes();target.write_bytes(old+b'\n')
                with self.assertRaises(ValueError):unchanged_pins(pins)
                # A newly calculated live hash must not substitute for terminal authority.
                with self.assertRaises(ValueError):freeze_native_authority(state,native,receipt,terminal,state_sha)
                target.write_bytes(old)
            unchanged_pins(pins)


if __name__=='__main__':unittest.main()
