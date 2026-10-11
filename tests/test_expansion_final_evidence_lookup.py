import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('extractor',Path(__file__).resolve().parents[1]/'scripts/extract_expansion_final_evidence.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixture():
    active=[f'c{i}'for i in range(64)]+['best_n_exact-n16','best_n_exact-n32','random_complete-n16','random_complete-n32','pooled_greedy_swap-n16','pooled_greedy_swap-n32']
    contrasts=[{'condition':active[i//2+1],'reference':'c0','role':f'r{i}'}for i in range(124)]
    inventory={'conditions':[{'condition_id':c,'status':'scheduled_full_bank'}for c in active],'headline_comparison_family':contrasts}
    draft={'presentation':{'approaches':{f'a{i}':{'contrast':contrasts[i]}for i in range(7)}}}
    metric={'numerator':0,'denominator':10,'ci95':[0,0],'warnings':['zero_observed_variation'],'defined_draws':10000,'independent_groups':2}
    rows=[{'condition':c,'family':f,'metric':copy.deepcopy(metric)}for c in active for f in m.FAMILIES]
    pairs=[dict(p,family=f,delta=0,ci95_delta=[0,0],simultaneous_ci95_delta=None,defined_draws=10000,
                warning='zero_variation')for p in contrasts for f in m.FAMILIES]
    n={'status':'complete_exploratory','missing_condition_families':[],'complete_condition_families':[{}]*280,
       'cohorts':{'full':{'rows':rows,'comparisons':pairs,'declared_contrasts':496,'comparison_family_complete':True,
       'missing_comparisons':[],'bootstrap_replicates':10000,'effective_non_degenerate_contrasts':0,'joint_interval_contrasts':0,'joint_critical_value':None}}}
    fits=[{'condition':c,'family':f,'missing_selection_sites':0,'mean_fve':None,'mean_fve_ci95':None,
           'scored_site_count':0,'full_site_count':10,'mean_fve_warnings':['No valid fits'],'parent_comparisons':[]}
          for c in active for f in m.FAMILIES]
    r={'diagnostic_version':5,'solver':'scipy_exact','objective':'1-squared_residual/squared_target','rows':fits}
    return n,r,inventory,draft

class EvidenceCopy(unittest.TestCase):
    def test_exact_copy_pointers_and_null_warnings_no_source_mutation(self):
        n,r,i,d=fixture();before=copy.deepcopy((n,r,i,d));out=m.extract(n,r,i,d)
        self.assertEqual((n,r,i,d),before);self.assertEqual(len(out['primary_comparisons']),28)
        x=out['primary_comparisons'][0];self.assertEqual(x['native_condition']['record'],n['cohorts']['full']['rows'][4])
        self.assertEqual(x['native_condition']['source_array_pointer'],'/cohorts/full/rows/4')
        self.assertIsNone(x['native_paired_comparison']['record']['simultaneous_ci95_delta'])
        self.assertEqual(x['reconstruction_recorded_common_mask_comparison']['status'],'not_recorded')
        self.assertEqual(out['native_joint_family_metadata']['record']['effective_non_degenerate_contrasts'],0)
        self.assertEqual(x['reconstruction_condition']['record']['mean_fve_warnings'],['No valid fits'])

    def test_recorded_common_mask_copied_not_replaced_with_absolute_difference(self):
        n,r,i,d=fixture();row=next(x for x in r['rows']if x['condition']=='c1'and x['family']==m.FAMILIES[0])
        row.update(mean_fve=.9,scored_site_count=9)
        p={'kind':'frozen_parent','reference':'c0','paired_sites':3,'reference_mean_same_mask':.1,'proposed_mean_same_mask':.2,
           'mean_delta':.1,'ci95_delta':[-.1,.3],'missing_or_invalid_pairs':7,'warning':'partial common mask'}
        row['parent_comparisons']=[p];out=m.extract(n,r,i,d)
        copied=out['primary_comparisons'][0]['reconstruction_recorded_common_mask_comparison']
        self.assertEqual(copied['record'],p);self.assertTrue(copied['source_array_pointer'].endswith('/parent_comparisons/0'))

    def test_partial_family_missing_menu_or_duplicate_ref_rejected(self):
        for change in ('partial','missing','duplicate'):
            n,r,i,d=fixture()
            if change=='partial':n['status']='partial_exploratory'
            elif change=='missing':n['cohorts']['full']['comparisons'].pop()
            else:r['rows'][4]['parent_comparisons']=[{'reference':'c0','kind':'frozen_parent'},{'reference':'c0','kind':'frozen_parent'}]
            with self.assertRaises(ValueError):m.extract(n,r,i,d)

    def test_scaling_and_pool_extras_only_copy_existing_records(self):
        n,r,i,d=fixture()
        row=next(x for x in r['rows']if x['condition']=='pooled_greedy_swap-n32'and x['family']==m.FAMILIES[0])
        pair={'kind':'pooling_vs_best_complete_diagnostic','reference':'best_n_exact-n32','paired_sites':8,'mean_delta':.04,'ci95_delta':[-.01,.09],'warning':None}
        row['parent_comparisons']=[pair]
        result=m.extract(n,r,i,d)['existing_scaling_and_pool_fit_records']
        self.assertEqual(len(result),1);self.assertEqual(result[0]['comparison']['record'],pair)

    def test_same_reference_editor_kinds_all_retained_with_named_primary(self):
        n,r,i,d=fixture();row=r['rows'][4]
        frozen={'reference':'c0','kind':'frozen_parent','paired_sites':8,'mean_delta':.04,'ci95_delta':[-.01,.09]}
        editor={**frozen,'kind':'editor_initial_reference'}
        row['parent_comparisons']=[editor,frozen]
        pair=m.extract(n,r,i,d)['primary_comparisons'][0]['reconstruction_recorded_common_mask_comparison']
        self.assertEqual(pair['selected_kind'],'frozen_parent');self.assertEqual(pair['record'],frozen)
        self.assertEqual([x['record']for x in pair['all_matching_records']],[editor,frozen])
        self.assertEqual(pair['other_kind_records'][0]['record'],editor)
        self.assertTrue(pair['source_array_pointer'].endswith('/parent_comparisons/1'))
        row['parent_comparisons'].append(copy.deepcopy(editor))
        with self.assertRaisesRegex(ValueError,'same-kind'):m.extract(n,r,i,d)

if __name__=='__main__':unittest.main()
