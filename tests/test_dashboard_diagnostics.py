"""Diagnostic disclosure and provenance failures on small synthetic fixtures."""
import importlib.util
from pathlib import Path
import unittest


def module(name, filename):
    spec=importlib.util.spec_from_file_location(name, Path(__file__).parents[1]/'scripts'/filename)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


append=module('append_diagnostics','append_diagnostic_dashboard.py')
dashboard=module('dashboard','build_dashboard.py')


class DiagnosticTests(unittest.TestCase):
    def artifact(self):
        return {'manifest_sha256':'frozen','analysis_status':'complete_development_partial_grid',
            'analysis_revision':'v2-source-item-bootstrap-metadata','missing_candidates':0,
            'judged_candidates':6048,'families':{'multihop_mt':{'items':8,
                'rank_minus_half_group_interval':{'items':8,'ci95_delta':[-.1,.2]}}},
            'limitations':[],'random_note':'Toy synthetic expectation'}

    def test_interval_is_absolute_rank_and_source_items_required(self):
        artifact=self.artifact()
        result=append.candidate_summary(artifact,'frozen')
        self.assertEqual(result['families']['multihop_mt']['rank_ci95'],[.4,.7])
        artifact['families']['multihop_mt']['rank_minus_half_group_interval']['items']=24
        with self.assertRaisesRegex(ValueError,'source item'):
            append.candidate_summary(artifact,'frozen')

    def test_incomplete_or_old_analysis_not_promoted(self):
        artifact=self.artifact();artifact['missing_candidates']=1
        with self.assertRaisesRegex(ValueError,'complete corrected'):
            append.candidate_summary(artifact,'frozen')
        artifact=self.artifact();artifact['analysis_revision']='v1'
        with self.assertRaises(ValueError):append.candidate_summary(artifact,'frozen')

    def test_rank_disclosure_and_text_escaping(self):
        family={'available':{'rate':.5,'numerator':1,'denominator':2},
            'random_expected':{'rate':.25,'numerator':.5,'denominator':2},
            'selected':{'rate':0,'numerator':0,'denominator':2},
            'within_cell_rank_pooled_pairs':{'rate':.5,'numerator':1,'denominator':2},
            'rank_ci95':[.2,.8],'rank_mixed_cells':1,'rank_undefined_cells':1,
            'independent_groups':2,'items':2,'rank_definition':'Passing versus failing'}
        section={'title':'<script>bad</script>','scope':'Synthetic fixture',
            'families':{'multihop_mt':family},'limits':['No fidelity claim'],
            'random_note':'Expected counts','source':{'sha256':'test'}}
        rendered=dashboard.candidate_diagnostic_section(section)
        self.assertIn('evaluation diagnostic',rendered)
        self.assertIn('class="whisker"',rendered)
        self.assertIn('&lt;script&gt;bad',rendered)
        self.assertNotIn('<script>bad',rendered)


if __name__=='__main__':unittest.main()
