import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from expanded_final_qualitative_gate import preserve_prior,verify_delta_counts,verify_final_scope,FAMILIES


class FinalQualitativeGateTests(unittest.TestCase):
    def fixture(self):
        row={'cell_id':'site','context_ref':'site','category':'fixed_anchor','baseline':{'text':'before','pass':False},
            'proposed':{'text':'after','pass':True},'endpoint_evidence':{'whole_grid':True}}
        pack={'anchors':[{'cell_id':'site'}],'original_readouts':{'site':{'raw':'raw','capped':'before'}},
            'contexts':{'site':{'full_context':'source question'}},'conditions':{'method':{'families':{'hallucination':{'fixed_anchor':[row],'outcome_selected':[]}}}}}
        return pack

    def test_prior_full_case_context_and_official_evidence_cannot_change(self):
        prior=self.fixture();current=copy.deepcopy(prior);old,new=preserve_prior(prior,current)
        self.assertEqual(old,new)
        for mutate in ('context','official','raw'):
            current=copy.deepcopy(prior)
            if mutate=='context':current['contexts']['site']['full_context']='different question'
            if mutate=='official':current['conditions']['method']['families']['hallucination']['fixed_anchor'][0]['proposed']['pass']=False
            if mutate=='raw':current['original_readouts']['site']['raw']='changed raw'
            with self.assertRaises(ValueError):preserve_prior(prior,current)

    def test_completed_parent_evidence_preserved_while_missing_parent_can_complete(self):
        prior=self.fixture();row=prior['conditions']['method']['families']['hallucination']['fixed_anchor'][0]
        row['parents']={'parent':{'status':'complete','output':{'text':'parent','pass':False}},'pending':{'status':'parent_family_not_complete'}}
        current=copy.deepcopy(prior);now=current['conditions']['method']['families']['hallucination']['fixed_anchor'][0]
        now['parents']['pending']={'status':'complete','output':{'text':'actual parent'}}
        preserve_prior(prior,current,True)
        now['parents']['parent']['output']['pass']=True
        with self.assertRaises(ValueError):preserve_prior(prior,current,True)

    def test_missing_condition_or_task_family_rejected(self):
        prior=self.fixture();details=prior['conditions']['method']['families']['hallucination']
        prior['conditions']['method']['families']={f:copy.deepcopy(details)for f in FAMILIES}
        verify_final_scope(prior,{'method'})
        with self.assertRaises(ValueError):verify_final_scope(prior,{'method','missing_editor'})
        del prior['conditions']['method']['families']['role_bound_association']
        with self.assertRaises(ValueError):verify_final_scope(prior,{'method'})

    def test_reference_counts_and_explicit_zero_pending_partitions(self):
        key=('edited','hallucination','fixed_anchor','site');ref={'condition':key[0],'family':key[1],'kind':key[2],'cell_id':key[3]}
        before={};after={key:{}};parent_before={};parent_after={key:{'parents':{'actual_parent':{'status':'complete'}}}}
        index={'partitions':{n:[]for n in ('root','agent_1','agent_2','agent_3')},'partition_comparison_counts':{n:0 for n in ('root','agent_1','agent_2','agent_3')},
            'inherited_comparisons':[{'pair_kind':'capped_N1_pairs','pair':{'references':[ref]}},
                {'pair_kind':'actual_parent_pairs','pair':{'references':[ref|{'parent_condition':'actual_parent'}]}}],
            'retained_previous_cases':0,'new_capped_N1_case_references':1,'new_actual_parent_references':1}
        count=verify_delta_counts(index,before,after,parent_before,parent_after)
        self.assertEqual(count['pending_unique_comparisons'],0);self.assertEqual(count['inherited_unique_comparisons'],2)
        changed=copy.deepcopy(index);changed['inherited_comparisons'].pop()
        with self.assertRaises(ValueError):verify_delta_counts(changed,before,after,parent_before,parent_after)
        changed=copy.deepcopy(index);del changed['partitions']['agent_3']
        with self.assertRaises(ValueError):verify_delta_counts(changed,before,after,parent_before,parent_after)


if __name__=='__main__':unittest.main()
