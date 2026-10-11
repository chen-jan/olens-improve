import copy
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1]/'scripts/assemble_expansion_final_review.py'
spec = importlib.util.spec_from_file_location('final_review_assembly',PATH)
module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def pack(parent=False, context='original context', endpoint=None):
    before = {'text':'before\n','class':'good','pass':True,'evidence':{'hit':True}}
    after = {'text':'after','class':'good','pass':True,'evidence':{'hit':True}}
    case = {'cell_id':'cell','context_ref':'ctx','category':'fixed_anchor','selection_policy':'fixed',
            'proposed':after,'endpoint_evidence':endpoint}
    if parent:
        case.update(original_baseline_condition='capped_n1-n1',original_baseline=before,
                    parents={'capped_n1-n1':{'status':'complete','output':before,'endpoint_evidence':endpoint}})
    else:case.update(baseline_condition='capped_n1-n1',baseline=before)
    return {'contexts':{'ctx':{'source_bank_item':{'prompt':context}}},
            'conditions':{'method':{'families':{'multihop_mt':{'fixed_anchor':[case]}}}}}

def entry(source):
    return {'source_sha256':source,'family':'multihop_mt','kind':'fixed_anchor','cell_id':'cell',
            'reference':'capped_n1-n1','title':'approved title','analysis':'approved original note'}

def note(source, parent=False):
    case=source['conditions']['method']['families']['multihop_mt']['fixed_anchor'][0]
    r={'condition':'method','family':'multihop_mt','kind':'fixed_anchor','cell_id':'cell',
       'category':'fixed_anchor','selection_policy':'fixed','endpoint_evidence':case['endpoint_evidence']}
    if parent:r.update(parent_condition='capped_n1-n1',official_parent=case['parents']['capped_n1-n1']['output'],
                       official_proposed=case['proposed'],parent_endpoint_evidence=case['parents']['capped_n1-n1']['endpoint_evidence'])
    else:r.update(official_before=case['baseline'],official_after=case['proposed'])
    return {'source_reference':r,'context':source['contexts']['ctx'],
            'human_review':{'observation':'Human reviewed change.'},'review_path':'human.json','review_sha256':'hash'}

def merged(rows):return {'new_case_notes':rows,'required_new_case_reference_count':len(rows),'reviewed_new_case_reference_count':len(rows)}

class FinalAssembly(unittest.TestCase):
    def test_prior_entries_and_repeated_identities_preserved_verbatim(self):
        old=pack();prior={'dashboard_examples':{'method':[entry('old'),entry('old')]}}
        del prior['dashboard_examples']['method'][0]['reference']
        before=copy.deepcopy(prior)
        examples,receipt=module.assemble_examples(prior,merged([note(old)]),{'old':old,'cap':old},'cap','parent')
        self.assertEqual(examples,prior['dashboard_examples']);self.assertEqual(prior,before)
        self.assertEqual(receipt['prior_entries_preserved_verbatim'],2)
        self.assertEqual(receipt['new_distinct_entries'],0)

    def test_new_dual_pack_reference_prefers_parent_and_counts_refs(self):
        cap,parent=pack(),pack(True)
        examples,receipt=module.assemble_examples({'dashboard_examples':{}},merged([note(cap),note(parent,True)]),
                                                 {'cap':cap,'parent':parent},'cap','parent')
        self.assertEqual(receipt['new_source_references'],2);self.assertEqual(receipt['new_distinct_entries'],1)
        self.assertEqual(examples['method'][0]['source_sha256'],'parent')

    def test_different_full_context_cannot_dedup_into_old(self):
        old,new=pack(),pack(context='changed context')
        with self.assertRaisesRegex(ValueError,'conflicts'):
            module.assemble_examples({'dashboard_examples':{'method':[entry('old')]}},merged([note(new)]),
                                     {'old':old,'cap':new},'cap','parent')

    def test_conflicting_official_pair_cannot_be_silently_copied(self):
        cap=pack();row=note(cap);row['source_reference']['official_after']=dict(row['source_reference']['official_after'],**{'pass':False})
        with self.assertRaisesRegex(ValueError,'Official before/after'):
            module.assemble_examples({'dashboard_examples':{}},merged([row]),{'cap':cap},'cap','parent')

    def test_parent_first_uses_recorded_grid_and_rejects_incomplete_parent(self):
        p=pack(True,endpoint={'parent_item_pass':True,'proposed_item_pass':True})
        case=p['conditions']['method']['families']['multihop_mt']['fixed_anchor'][0]
        case['endpoint_evidence']=None
        resolved,_=module.resolve('method',entry('p'),{'p':p})
        self.assertEqual(resolved['endpoint']['parent_item_pass'],True)
        case['parents']['capped_n1-n1']['status']='pending'
        with self.assertRaisesRegex(ValueError,'Incomplete actual parent'):module.resolve('method',entry('p'),{'p':p})

    def test_ambiguous_source_and_duplicate_reference_fail(self):
        p=pack();row=note(p)
        with self.assertRaisesRegex(ValueError,'Duplicate final source reference'):
            module.assemble_examples({'dashboard_examples':{}},merged([row,row]),{'cap':p},'cap','parent')
        p['conditions']['method']['families']['multihop_mt']['fixed_anchor']*=2
        with self.assertRaisesRegex(ValueError,'Ambiguous'):module.resolve('method',entry('p'),{'p':p})

    def test_changed_grid_cannot_dedup_despite_equal_text(self):
        cap,parent=pack(endpoint={'baseline_item_pass':False}),pack(True,endpoint={'parent_item_pass':True})
        with self.assertRaisesRegex(ValueError,'different question-grid'):
            module.assemble_examples({'dashboard_examples':{}},merged([note(cap),note(parent,True)]),
                                     {'cap':cap,'parent':parent},'cap','parent')

    def test_null_cap_grid_reuses_existing_richer_parent_without_dropping_it(self):
        cap,parent=pack(),pack(True,endpoint={'parent_item_pass':True})
        prior={'dashboard_examples':{'method':[entry('parent')]}}
        examples,receipt=module.assemble_examples(prior,merged([note(cap)]),{'cap':cap,'parent':parent},'cap','parent')
        self.assertEqual(examples,prior['dashboard_examples']);self.assertEqual(receipt['new_distinct_entries'],0)
        with self.assertRaisesRegex(ValueError,'conflicts'):
            module.assemble_examples({'dashboard_examples':{'method':[entry('cap')]}},merged([note(parent,True)]),
                                     {'cap':cap,'parent':parent},'cap','parent')

    def test_cap_and_parent_grid_schema_extra_witnesses_preserve_counts(self):
        a={'unit':'whole_original_question_grid','item_id':'q','grid_cells':11,
           'baseline_item_pass':True,'proposed_item_pass':True,'baseline_passing_cells':7,'proposed_passing_cells':10,
           'witness_rule':'first text-changed site'}
        b={**a,'parent_item_pass':a['baseline_item_pass'],'parent_passing_cells':a['baseline_passing_cells'],
           'parent_first_passing_cell':'cell'}
        del b['baseline_item_pass'];del b['baseline_passing_cells'];del b['witness_rule']
        self.assertTrue(module.endpoint_compatible(a,b))
        b['proposed_passing_cells']=9;self.assertFalse(module.endpoint_compatible(a,b))

if __name__=='__main__':unittest.main()
