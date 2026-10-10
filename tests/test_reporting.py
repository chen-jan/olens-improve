import unittest
import json
import tempfile
from pathlib import Path
from olens_improve.reporting import family_counts, summarize, digest, BENCHMARK_COMMIT
from olens_improve.evaluation import paired_group_interval

class ReportingTests(unittest.TestCase):
    def fixture(self, text='a claim'):
        cell={'item_id':'a','layer':20,'position':3}
        read={'id':'a','layer':20,'pos':3,'samples':[text]}
        verdict={'idx':0,'class':'hallucinated','revoked':False,'claims':{'false':1,'true':0,'unverifiable':2}}
        return [cell],[read],{'rows':[dict(read,verdict=[verdict])]}
    def test_missing_stage1_cannot_hide_behind_stage2_flag(self):
        cells,reads,result=self.fixture()
        result['rows'][0]['verdict']=None
        result['stage2_complete_for_produced_readouts']=True
        metrics,status=family_counts('hallucination',cells,reads,result)
        self.assertEqual((status['missing_stage1'],status['missing_stage2']),(1,1))
    def test_revoked_still_counts_in_frozen_headline(self):
        cells,reads,result=self.fixture()
        result['rows'][0]['verdict'][0]['revoked']=True
        pairs,_=family_counts('hallucination',cells,reads,result)
        self.assertEqual(pairs['contradiction_rate']['a'],(1,1))
    def test_missing_claim_tally(self):
        cells,reads,result=self.fixture()
        result['rows'][0]['verdict'][0]['claims']=None
        _,status=family_counts('hallucination',cells,reads,result)
        self.assertEqual((status['missing_stage1'],status['missing_stage2']),(0,1))
    def test_empty_claim_object_is_missing_stage2(self):
        cells,reads,result=self.fixture()
        result['rows'][0]['verdict'][0]['claims']={}
        _,status=family_counts('hallucination',cells,reads,result)
        self.assertEqual(status['missing_stage2'],1)
    def test_empty_abstention_is_not_api_failure(self):
        cells,reads,_=self.fixture('')
        pairs,status=family_counts('role_bound_association',cells,reads,{'rows':[]})
        self.assertEqual(status['empty_abstentions'],1)
        self.assertEqual(status['missing_stage1'],0)
        self.assertEqual(pairs['cell_recovery']['a'],(0,1))
        reads[0]['samples']=['nonempty']
        _,status=family_counts('role_bound_association',cells,reads,{'rows':[]})
        self.assertEqual(status['missing_stage1'],1)
    def test_duplicate_readout_rejected(self):
        cells,reads,result=self.fixture()
        with self.assertRaises(ValueError): family_counts('hallucination',cells,reads*2,result)
    def test_chain_any_layer_pass_not_used_for_cell_pass(self):
        cells,reads,_=self.fixture()
        pairs,_=family_counts('chain_intermediates',cells,reads,{'rows':[{'id':'a','pass':True,'kind_by_layer':{'20':'other'}}]})
        self.assertEqual(pairs['cell_recovery']['a'],(0,1))
    def test_manifest_hash_mismatch_never_marks_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); manifest=root/'manifest.json'; conditions=root/'arms.json'
            manifest.write_text(json.dumps({'partial_grid':True,'cells':[{'item_id':'a','cell_id':'a','family':'hallucination','layer':20,'position':3,'group_id':'g','split':'development'}]}))
            conditions.write_text(json.dumps([{'method':'raw_n1','n':1}]))
            arm=root/'raw_n1-n1';arm.mkdir()
            (arm/'condition.json').write_text(json.dumps({'method':'raw_n1','n':1,'manifest_sha256':'wrong','selection_sha256':'frozen'}))
            report=summarize(manifest,conditions,root,selection_sha='frozen')
            self.assertFalse(report['conditions'][0]['measurement_complete'])
            self.assertIn('hash mismatch',report['conditions'][0]['errors'][0])
            self.assertEqual(report['paired_comparisons'],[])
    def test_per_condition_root_and_selection_hash_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary); alternate=home/'alternate'; alternate.mkdir()
            families=['hallucination','multihop_mt','chain_intermediates','role_bound_association']
            cells=[{'item_id':'a','cell_id':f+'|a','family':f,'layer':20,'position':3,'group_id':f+':g','split':'development'} for f in families]
            manifest=home/'manifest.json';manifest.write_text(json.dumps({'partial_grid':True,'cells':cells}))
            arms=home/'arms.json';arms.write_text(json.dumps([{'method':'own_mean_log_likelihood','n':8,'condition_root':str(alternate),'selection_sha256':'override'}]))
            run=alternate/'own_mean_log_likelihood-n8';run.mkdir()
            identity={'method':'own_mean_log_likelihood','n':8,'manifest_sha256':digest(manifest),'selection_sha256':'override','partial_grid':True,'coverage':{'expected_cells':4,'produced_cells':4,'missing_cell_ids':[],'readouts_per_cell':1}}
            (run/'condition.json').write_text(json.dumps(identity))
            for family in families:
                folder=run/family;folder.mkdir()
                contract={'manifest_expected_cells':1,'manifest_produced_cells':1,'manifest_missing_cells':0,'benchmark_commit':BENCHMARK_COMMIT,'partial_grid':True,'split':['development']}
                (folder/'project_contract.json').write_text(json.dumps(contract))
                (run/(family+'.summary.json')).write_text(json.dumps({'condition':identity,'families':{family:{'project_contract':contract}}}))
                readout={'id':'a','layer':20,'pos':3,'samples':['a claim']}
                (run/(family+'.readouts.jsonl')).write_text(json.dumps(readout)+'\n')
                if family=='hallucination':row=dict(readout,verdict=[{'idx':0,'class':'consistent','claims':{'true':1,'false':0,'unverifiable':0}}])
                elif family=='role_bound_association':row=dict(readout,**{'pass':True})
                elif family=='chain_intermediates':row={'id':'a','kind_by_layer':{'20':'hit'}}
                else:row={'id':'a','roles':['bridge1'],'layers':{'20':{'hits':{'bridge1':['en']}}}}
                (folder/'results.json').write_text(json.dumps({'family':family,'config':{'dry_run':False},'rows':[row]}))
            report=summarize(manifest,arms,home/'unused-default',selection_sha='default')
            self.assertTrue(report['conditions'][0]['measurement_complete'],report['conditions'][0]['errors'])
            self.assertEqual(report['conditions'][0]['condition_root'],str(alternate))
            arms.write_text(json.dumps([{'method':'own_mean_log_likelihood','n':8,'condition_root':str(alternate),'selection_sha256':'wrong'}]))
            self.assertFalse(summarize(manifest,arms,home)['conditions'][0]['measurement_complete'])
    def test_ratio_of_sums_whole_groups(self):
        base={'a':(0,9),'b':(0,1)}; proposed={'a':(9,9),'b':(0,1)}
        result=paired_group_interval(base,proposed,{'a':'same','b':'same'},replicates=2000)
        self.assertEqual(result['delta'],.9)
        self.assertEqual(result['ci95_delta'],[.9,.9])
        self.assertEqual(result['independent_groups'],1)

if __name__=='__main__': unittest.main()
