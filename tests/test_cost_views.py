"""Budget interpretation and exact cohort/completeness safeguards."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('cost_views', ROOT / 'scripts/populate_cost_views.py')
views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(views)


class CostViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((ROOT / 'dashboard/report.json').read_text())
        cls.measurements = json.loads((ROOT / 'dashboard/measurements-v2.json').read_text())
        # A small synthetic tariff/timer fixture verifies interpretation, not real cost.
        cls.costs = {'deployment': {'sampling_n32_gpu_seconds_per_cell': 32.0},
                     'incremental_cache': {k: {'median_seconds_per_cell': .01}
                                           for k in ('A8','A16','A32','C32','D32','E1_mean32')},
                     'campaign': {'helper_b_repaired_none_medium': {
                         'proposal': {'calls': 189}, 'medium_confirmation': {'settled_physical_responses': 195},
                         'medium_pipeline_usd': .378, 'none_pipeline_calls': 378, 'none_pipeline_usd': .189},
                         'helpers': [{'stage': 'helper-edit-pilot-v1/round1', 'requests': 189, 'actual_usd': .01},
                                     {'stage': 'helper-edit-pilot-v1/round2', 'requests': 189, 'actual_usd': .02}]}}

    def test_same_pool_random_control_keeps_eligibility_cost_unknown(self):
        report = views.populate(copy.deepcopy(self.report), self.measurements, self.costs, {})
        points = report['methods']['sample_selection']['cost_frontier'][0]['points']
        random = next(p for p in points if p['condition'] == 'random_complete-n32')
        self.assertEqual(random['cost'], 32)  # Actual experimental prefix.
        self.assertIsNone(random['required_olens_samples_for_fresh_baseline'])
        self.assertEqual(random['retained_samples_for_random_baseline'], 1)
        self.assertIsNone(random['generation_component_gpu_seconds'])
        self.assertIn('eligibility', random['control_note'])
        medium = next(p for p in points if p['condition'].startswith('consensus_semantic_v5_medium_'))
        self.assertAlmostEqual(medium['recurring_helper_calls_per_cell'], 384/189)
        self.assertAlmostEqual(medium['recurring_helper_usd_per_cell'], .002)
        self.assertIsNone(medium['cached_selector_wall_seconds'])

    def test_incomplete_stage_or_wrong_cohort_cannot_be_plotted(self):
        bad = copy.deepcopy(self.measurements)
        next(a for a in bad['conditions'] if a['condition']=='capped_n1-n1')['families']['hallucination']['missing_stage2']=1
        with self.assertRaisesRegex(ValueError,'stage coverage'):
            views.populate(copy.deepcopy(self.report), bad, self.costs, {})
        bad['manifest_sha256']='different'
        with self.assertRaisesRegex(ValueError,'cohort hash'):
            views.populate(copy.deepcopy(self.report), bad, self.costs, {})


if __name__ == '__main__':
    unittest.main()
