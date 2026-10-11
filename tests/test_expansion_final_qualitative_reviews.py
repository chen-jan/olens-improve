import importlib.util,json,sys,tempfile,unittest
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('final_notes',ROOT/'scripts/validate_expansion_qualitative_final_reviews.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)

class FinalReviewGuards(unittest.TestCase):
 def fixture(self,root):
  def write(name,value):
   p=root/name;p.write_text(json.dumps(value));return p
  before={'text':'Original 7','pass':True};after={'text':'Generic fragment','pass':False}
  ref={'condition':'old','official_before':before,'official_after':after}
  pair={'before':before,'after':after,'references':[ref]}
  unit={'family':'chain_intermediates','cell_id':'cell','context_ref':'c','capped_N1_pairs':[pair],'actual_parent_pairs':[]}
  prior={'manifest_sha256':'seal','analysis_sha256':'prior-analysis','source_sha256':{},'contexts':{'c':{'required':7}},'partitions':{'root':[unit]},'partition_comparison_counts':{'root':1},'inherited_comparisons':[]}
  pp=write('prior-index.json',prior)
  def review(index,index_path):
   u=index['partitions']['root'][0]
   return {'status':'complete','manifest_sha256':index['manifest_sha256'],'analysis_sha256':index['analysis_sha256'],'index_sha256':g.sha(index_path),'source_sha256':index['source_sha256'],'partition':'root','unit_reviews':[{'unit_index':0,'family':u['family'],'cell_id':u['cell_id'],'exact_unit_sha256':g.blob(u),'condition_case_references':[r for k in g.KINDS for p in u[k] for r in p['references']],'note':'Observed loss, no causal conclusion'}]}
  pr=write('prior-review.json',review(prior,pp))
  notes={'status':'all_fresh_and_inherited_reviews_validated','manifest_sha256':'seal','index_sha256':g.sha(pp),'pending_partitions':[],'source_sha256':{str(pp):g.sha(pp),str(pr):g.sha(pr)},'historical_reviewed_pair_count':0,'new_case_notes':[{'source_reference':ref,'human_review':{'note':'old note retained'}}]}
  np=write('prior-notes.json',notes)
  pending=deepcopy(unit);pending['capped_N1_pairs'][0]['references'][0]['condition']='new-pending'
  inherited=deepcopy(pair);inherited['references'][0]['condition']='new-inherited';inherited['prior_exact_text_context_review_links']=[{'partition':'root','prior_unit_index':0,'pair_kind':'capped_N1_pairs','prior_pair_index':0,'path':str(pr),'sha256':g.sha(pr)}]
  final={'manifest_sha256':'seal','analysis_sha256':'final-analysis','source_sha256':{str(pp):g.sha(pp),str(pr):g.sha(pr)},'contexts':prior['contexts'],'partitions':{'root':[pending]},'partition_comparison_counts':{'root':1},'inherited_comparisons':[{'family':'chain_intermediates','cell_id':'cell','context_ref':'c','pair_kind':'capped_N1_pairs','pair':inherited}]}
  fp=write('final-index.json',final);fr=write('final-review.json',review(final,fp))
  return pp,np,pr,fp,fr,final,notes
 def test_variable_counts_preserve_old_bundle_and_bind_new_pairs(self):
  with tempfile.TemporaryDirectory() as d:
   pp,np,pr,fp,fr,final,notes=self.fixture(Path(d));out=g.run(fp,pp,np,{'root':pr},{'root':fr})
   self.assertEqual(out['status'],'all_fresh_and_inherited_reviews_validated');self.assertEqual(out['required_new_case_reference_count'],2);self.assertEqual(out['inherited_reference_count'],1);self.assertEqual(out['prior_audited_bundle_verbatim'],notes)
   partial=g.run(fp,pp,np,{'root':pr},{})
   self.assertEqual(partial['status'],'partial_review_coverage_validated');self.assertFalse(partial['eligible_for_complete_final_public_notes']);self.assertEqual(partial['pending_partitions'],['root'])
 def test_context_change_cannot_inherit_identical_text(self):
  with tempfile.TemporaryDirectory() as d:
   pp,np,pr,fp,fr,final,notes=self.fixture(Path(d));prior=json.loads(pp.read_text());old=prior['partitions']['root'][0]['capped_N1_pairs'][0];link=final['inherited_comparisons'][0]['pair']['prior_exact_text_context_review_links'][0]
   final['contexts']['c']={'required':9}
   with self.assertRaisesRegex(ValueError,'context'):g.inherited_note(final['inherited_comparisons'][0],final['inherited_comparisons'][0]['pair']['references'][0],final,prior,{('root',0,'capped_N1_pairs',0):(old,{},pr,g.sha(pr))})
 def test_official_verdict_change_cannot_inherit_same_text(self):
  with tempfile.TemporaryDirectory() as d:
   pp,np,pr,fp,fr,final,notes=self.fixture(Path(d));prior=json.loads(pp.read_text());old=prior['partitions']['root'][0]['capped_N1_pairs'][0];u=final['inherited_comparisons'][0];u['pair']['references'][0]['official_after']['pass']=True
   with self.assertRaisesRegex(ValueError,'official pair'):g.inherited_note(u,u['pair']['references'][0],final,prior,{('root',0,'capped_N1_pairs',0):(old,{},pr,g.sha(pr))})
 def test_duplicate_reference_cannot_count_twice(self):
  with tempfile.TemporaryDirectory() as d:
   pp,np,pr,fp,fr,final,notes=self.fixture(Path(d));final['inherited_comparisons'][0]['pair']['references'][0]=deepcopy(final['partitions']['root'][0]['capped_N1_pairs'][0]['references'][0])
   with self.assertRaisesRegex(ValueError,'Duplicate'):g.refs(final)

if __name__=='__main__':unittest.main()
