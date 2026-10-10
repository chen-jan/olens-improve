import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('qualitative', Path(__file__).parents[1]/'scripts/dashboard_qualitative.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def fixture():
    return {'status':'root_reviewed','stage':'development_pilot','panel_sha256':q.PANEL_SHA,
        'anchors':[{'cell_id':cid,'label':cid} for cid in q.PANEL_IDS],
        'methods':{'editing':{'takeaway':'No anchor changed.', 'variants':[{'id':'F2','label':'Two rounds',
            'cases':[{'cell_id':cid,'baseline':{'text':'- Original','label':'Parent','verdict':'pass'},
                'proposed':{'text':'- Original','label':'Edited selection','verdict':'pass'},
                'unchanged':True,'assessment':'Unchanged, not a failure to execute.',
                'context':'Synthetic context','judge_evidence':{'pass':True},
                'provenance':{'sample_index':1}} for cid in q.PANEL_IDS]}], 'supplements':[]}}}


class QualitativeCards(unittest.TestCase):
    def test_all_fixed_cases_retained_but_only_one_initial_dom_card(self):
        text = q.method_cards(fixture(), 'editing')
        self.assertEqual(text.count('data-case-current='),1)
        self.assertEqual(text.count('<option value='),9)
        self.assertNotIn('data-case-panel=',text)
        self.assertIn('qualitative-evidence.json',text)
        self.assertIn('not improvement rates',text)

    def test_unavailable_diagnostic_has_no_invented_prose(self):
        text=q.card({'status':'unavailable','reason':'No retained token diagnostic.'})
        self.assertIn('No retained token diagnostic',text)
        self.assertNotIn('Before',text)

    def test_canonical_default_matches_initial_card_without_reordering(self):
        section=fixture();variants=section['methods']['editing']['variants']
        first=copy.deepcopy(variants[0]);first['id']='editing_round1-n32'
        second=copy.deepcopy(first);second['id']='editing_round2-n32';second['label']='Two-round default'
        for c in second['cases']:c['proposed']['text']='- Second-round text'
        section['methods']['editing']['variants']=[first,second]
        page=q.method_cards(section,'editing')
        self.assertIn('<option value="1" selected>Two-round default',page)
        self.assertIn('- Second-round text',page)
        self.assertEqual([v['id'] for v in section['methods']['editing']['variants']],
                         ['editing_round1-n32','editing_round2-n32'])

    def test_blind_stage_or_wrong_panel_rejected(self):
        for field,value in [('status','pending'),('stage','test'),('panel_sha256','wrong')]:
            section=fixture();section[field]=value
            with self.assertRaises(ValueError):q.validated(section)
        section=fixture();section['anchors'][0]['cell_id']='foreign'
        with self.assertRaises(ValueError):q.validated(section)

    def test_missing_case_and_too_many_supplements_rejected(self):
        section=fixture();section['methods']['editing']['variants'][0]['cases'].pop()
        with self.assertRaises(ValueError):q.validated(section)
        section=fixture();section['methods']['editing']['supplements']=[{}, {}, {}]
        with self.assertRaises(ValueError):q.validated(section)

    def test_unsafe_infrastructure_rejected_quotes_escaped(self):
        section=fixture();section['methods']['editing']['takeaway']='/orcd/private/artifact'
        with self.assertRaises(ValueError):q.validated(section)
        row={'baseline':{'text':'<script>alert(1)</script>'},'proposed':{'text':''},'assessment':'No quote rewriting.'}
        text=q.card(row)
        self.assertNotIn('<script>',text)
        self.assertIn('&lt;script&gt;',text)
        self.assertIn('abstention, not missing',text)


if __name__=='__main__':unittest.main()
