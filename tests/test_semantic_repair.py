"""Real semantic-helper format failures and conservative-cluster safeguards."""
import unittest
from olens_improve.helpers import (canonicalize_proposals, conservative_merge_veto,
                                  report_with_merge_veto, validate_matches, HelperValidationError)
from olens_improve.selection import parse_bullets


class SemanticRepairTests(unittest.TestCase):
    def test_duplicate_reversed_and_unknown_proposals_preserve_valid_work(self):
        accepted, skipped = canonicalize_proposals({'pairs': [
            {'a':'b000','b':'b001'}, {'a':'b001','b':'b000'},
            {'a':'missing','b':'b000'}, {'a':'b001','b':'b002'}]},
            {'b000':'first','b001':'second','b002':'third'},1)
        self.assertEqual(accepted,[('b000','b001')])
        self.assertEqual([r['reason'] for r in skipped],
                         ['duplicate_pair','unknown_source_id','beyond_fixed_pair_budget'])

    def test_missing_results_remain_unverified(self):
        payload=[{'pair_id':'p00','a_text':'15','b_text':'Answer: 15'}]
        with self.assertRaises(HelperValidationError):
            validate_matches({'results':[]},payload)
        # Complete locally retained source text replaces generated quotes/offsets.
        validate_matches({'results':[{'pair_id':'p00','label':'equivalent',
            'a_entails_b':True,'b_entails_a':True,'compatible':True,'reason':'Same number.'}]},payload)

    def test_known_restatement_and_temporal_traps_are_vetoed(self):
        self.assertTrue(conservative_merge_veto(
            'A father reveals disappointment. Or more concisely: he masks disappointment.',
            'A father feels disappointment and accepts his son.'))
        self.assertTrue(conservative_merge_veto('Marco apologizes and delivers the meal.',
                                               'Marco apologizes, then delivers the meal.'))
        self.assertEqual(conservative_merge_veto('Result is 7.','Result is 7.\n'),[])

    def test_veto_splits_support_without_changing_native_labels(self):
        a=parse_bullets('- Marco apologizes and delivers.', 's0',0)
        b=parse_bullets('- Marco apologizes then delivers.', 's1',1)
        report={'source_mapping':{'b000':['s0:0'],'b001':['s1:0']},
            'semantic_clusters':1,'clusters':[{'opaque_members':['b000','b001'],
                'source_phrase_ids':['s0:0','s1:0'],'supporting_samples':['s0','s1']}],
            'relations':[{'a':'b000','b':'b001','label':'equivalent','a_entails_b':True,
                'b_entails_a':True,'compatible':True,'reason':'fixture','evidence':{}}]}
        guarded=report_with_merge_veto([a,b],report,enabled=True)
        self.assertEqual([len(c['supporting_samples']) for c in guarded['clusters']],[1,1])
        self.assertEqual(report['semantic_clusters'],1)
        self.assertEqual(guarded['relations'],report['relations'])


if __name__ == '__main__':
    unittest.main()
