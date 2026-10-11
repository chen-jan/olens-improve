import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('effort_gate',ROOT/'scripts/expanded_final_effort_gate.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class TerminalEffortGuards(unittest.TestCase):
 def test_native_duplicate_count_cannot_masquerade_as_terminal(self):
  active={f'c{i}' for i in range(70)};pairs=[{'condition':c,'family':f} for c in active for f in g.FAMILIES]
  body={'manifest_sha256':g.MANIFEST_SHA,'status':'complete_exploratory','missing_condition_families':[],'complete_condition_families':pairs}
  g.validate_native(body,active);body['complete_condition_families'][-1]=pairs[0]
  with self.assertRaisesRegex(ValueError,'duplicated'):g.validate_native(body,active)
 def test_missing_native_state_cannot_start_an_export(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);probe,_=g.terminal_probe(p,p,p/'missing',set())
   self.assertFalse(probe['ready']);self.assertTrue(probe['missing_states'])
 def test_complete_labels_do_not_override_partial_helper_checkpoints(self):
  expected={f:3 for f in g.FAMILIES}
  phases={p+'/'+f:{'status':'complete','completed_cells':3,'proposal_statistics':{'cells':3}} for p in ('semantic_ordinary','semantic_medium','editing_round1','editing_round2') for f in g.FAMILIES}
  body={'status':'complete_retrospective','manifest_sha256':g.MANIFEST_SHA,'judge_completion':{f:70 for f in g.FAMILIES},'method_effort':{str(i):{} for i in range(70)},'helper_phases_by_family':phases,'ledger_audit':{'run_commitment':[{'status':'settled','actual_usd':10},{'status':'unknown','reserved_usd':5}],'buckets':{'shared_helper':{'actual_usage_estimate_usd':4},'benchmark':{'actual_usage_estimate_usd':6}},'limits':{'hard':340.,'target':200.}}}
  g.validate_effort(body,expected)
  phases['editing_round2/'+g.FAMILIES[0]]['completed_cells']=2
  with self.assertRaisesRegex(ValueError,'checkpoint'):g.validate_effort(body,expected)
 def test_holds_are_retained_and_cost_buckets_must_partition_settled(self):
  expected={f:0 for f in g.FAMILIES};phases={p+'/'+f:{'status':'complete','completed_cells':0,'proposal_statistics':{'cells':0}} for p in ('semantic_ordinary','semantic_medium','editing_round1','editing_round2') for f in g.FAMILIES}
  body={'status':'complete_retrospective','manifest_sha256':g.MANIFEST_SHA,'judge_completion':{f:70 for f in g.FAMILIES},'method_effort':{str(i):{} for i in range(70)},'helper_phases_by_family':phases,'ledger_audit':{'run_commitment':[{'status':'settled','actual_usd':10},{'status':'unknown','reserved_usd':5},{'status':'reserved','reserved_usd':1}],'buckets':{'shared_helper':{'actual_usage_estimate_usd':10}},'limits':{'hard':340.,'target':200.}}}
  before=json.dumps(body,sort_keys=True);g.validate_effort(body,expected);self.assertEqual(before,json.dumps(body,sort_keys=True))
  body['ledger_audit']['buckets']['shared_helper']['actual_usage_estimate_usd']=16
  with self.assertRaisesRegex(ValueError,'partition'):g.validate_effort(body,expected)
if __name__=='__main__':unittest.main()
