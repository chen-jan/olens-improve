import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_expansion_reconstruction import saved_fit, references, active_conditions


class FitExtractionTests(unittest.TestCase):
    def test_published_menu_excludes_alias_and_obsolete_diagnostics(self):
        inventory={'conditions':[{'condition_id':f'c{i}','status':status} for i,status in enumerate((
            'scheduled_full_bank','cached_selector_full_bank','exact_alias','computed_numerical_diagnostic_only','obsolete_malformed_transport_diagnostic'))]}
        self.assertEqual(set(active_conditions(inventory)),{'c0','c1'})

    def test_raw_baseline_and_invalid_are_not_zero_improvement(self):
        self.assertEqual(saved_fit({'method':'raw_n1','text':'- original','fits':None})[0],None)
        self.assertEqual(saved_fit({'method':'capped_n1','text':'- <think>','fits':None,'fits_scope':'unavailable_AR_empty_after_cleanup'})[0],None)
        fve,status=saved_fit({'method':'capped_n1','text':'','phrase_ids':[],
            'fits':{'exact':{'fve':0.,'solver':'scipy_exact','coefficients':[],'atom_ids':[]}},'fits_scope':'emitted_bullets'})
        self.assertEqual((fve,status),(0.,'explicit_empty_fit_zero'))

    def test_wrong_solver_and_atom_identity_fail(self):
        row={'method':'pooled_greedy_swap','text':'- phrase','phrase_ids':['kept'],
            'fits':{'exact':{'fve':.4,'solver':'released80','coefficients':[1.],'atom_ids':['different']}},'fits_scope':'emitted_bullets'}
        with self.assertRaises(ValueError):saved_fit(row)
        row['fits']['exact']['solver']='scipy_exact'
        with self.assertRaises(ValueError):saved_fit(row)

    def test_pooling_has_exact_matching_n_reference(self):
        got=references('pooled_greedy_swap-n16',['best_n_exact-n16'])
        self.assertIn({'reference':'best_n_exact-n16','kind':'pooling_vs_best_complete_diagnostic'},got)


if __name__=='__main__':unittest.main()
