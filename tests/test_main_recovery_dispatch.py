"""No-network exact remaining DEV dispatch and unchanged-command safeguards."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from infra.resume_main_judges import digest, dispatch_conditions_path, evaluation_command


class MainDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.spec = json.loads(Path('configs/judging_main_post_validation_hall_v2.json').read_text())
        self.signed = [{'method':'first','n':1},{'method':'second','n':16},{'method':'third','n':32}]
        self.remaining = self.signed[1:]
        self.spec['conditions'] = str(self.write('full.json',self.signed))
        self.spec['conditions_sha256'] = digest(Path(self.spec['conditions']))
        policy = self.spec['prospective_handoff_policy']
        policy['unchanged_menu_remaining_order'] = self.remaining
        for field in ('validation_spec','signed_validation_freeze'):
            policy[field] = str(self.write(field+'.json',{'synthetic':True}))
            policy[field+'_sha256'] = digest(Path(policy[field]))
        self.set_remaining(self.remaining)

    def write(self,name,body):
        path=self.root/name;path.write_text(json.dumps(body));return path

    def set_remaining(self,rows):
        path=self.write('remaining.json',rows)
        self.spec['dispatch_condition_files']={'hallucination':{'path':str(path),'sha256':digest(path)}}

    def test_exact_remaining_accepted_and_original_menu_retained(self):
        self.assertEqual(dispatch_conditions_path(self.spec,'hallucination'),str(self.root/'remaining.json'))
        self.assertEqual(json.loads(Path(self.spec['conditions']).read_text()),self.signed)

    def test_foreign_duplicate_reordered_or_incomplete_rejected(self):
        for rows in ([{'method':'foreign','n':1}],self.remaining*2,list(reversed(self.remaining)),self.remaining[:1]):
            self.set_remaining(rows)
            with self.assertRaises(ValueError):dispatch_conditions_path(self.spec,'hallucination')

    def test_wrong_hash_and_missing_binding_rejected(self):
        self.spec['dispatch_condition_files']['hallucination']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash'):dispatch_conditions_path(self.spec,'hallucination')
        self.spec.pop('dispatch_condition_files')
        with self.assertRaisesRegex(ValueError,'binding'):dispatch_conditions_path(self.spec,'hallucination')

    def test_command_changes_only_condition_list(self):
        after=evaluation_command(self.spec,'hallucination',[24,30])
        old=copy.deepcopy(self.spec);old.pop('dispatch_condition_files');old.pop('prospective_handoff_policy')
        before=evaluation_command(old,'hallucination',[24,30])
        after[after.index('--condition-list')+1]=before[before.index('--condition-list')+1]
        self.assertEqual(before,after)


if __name__=='__main__':unittest.main()
