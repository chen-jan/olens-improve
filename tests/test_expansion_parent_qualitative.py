import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_expansion_parent_qualitative import parent_endpoint, propagate_evidence


class ParentEvidenceTests(unittest.TestCase):
    def test_empty_hall_abstention_has_explicit_evidence_without_new_verdict(self):
        empty={'text':'','empty':True,'pass':False,'class':'empty','evidence':None}
        record={'cell_id':'a','baseline':dict(empty),'proposed':dict(empty)}
        trace={'baseline_condition':'parent','condition':'derived','families':{'hallucination':{'examples':{'fixed':[record]}}}}
        propagate_evidence([trace])
        self.assertEqual(record['proposed']['class'],'empty')
        self.assertEqual(record['proposed']['evidence'],{'evaluation_only':True,'explicit_empty_abstention':True})

    def test_selected_failure_keeps_other_site_whole_question_success(self):
        cells = {'a': {'item_id': 'q'}, 'b': {'item_id': 'q'}, 'c': {'item_id': 'other'}}
        parent = {k: {'pass': k == 'b'} for k in cells}
        proposed = {k: {'pass': k == 'a'} for k in cells}
        got = parent_endpoint(parent, proposed, 'a', cells, 'chain_intermediates')
        self.assertTrue(got['parent_item_pass'])
        self.assertFalse(got['selected_cell_parent_pass'])
        self.assertEqual((got['grid_cells'], got['parent_first_passing_cell']), (2, 'b'))

    def test_repeated_parent_copy_receives_exact_judge_evidence(self):
        plain = {'text': '- retained', 'empty': False, 'pass': True, 'class': None, 'evidence': None}
        one = dict(plain); two = dict(plain, evidence={'official': 'retained'})
        records = [{'cell_id': 'a', 'baseline': one, 'proposed': dict(two)},
                   {'cell_id': 'a', 'baseline': two, 'proposed': dict(two)}]
        trace = {'baseline_condition': 'parent', 'condition': 'derived',
                 'families': {'chain_intermediates': {'examples': {'same': records}}}}
        propagate_evidence([trace])
        self.assertEqual(one['evidence'], {'official': 'retained'})


if __name__ == '__main__':
    unittest.main()
