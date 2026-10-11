"""Offline synthetic source guards and secondary fit units; no model/client calls."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_expansion_report as report
from test_expansion_slides import fixture, write


class ReconstructionReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths, _, inventory, self.review = fixture(self.root, qa=False)
        self.condition = 'best_n_exact-n32'
        self.artifact = {
            'manifest_sha256': self.review['manifest_sha256'],
            'quality_analysis_sha256': self.review['results_sha256'],
            'objective': '1-squared_residual/squared_target', 'solver': 'scipy_exact',
            'vector_contract_sha256': inventory['vector_contract']['sha256'], 'rows': []}
        for family in report.FAMILIES:
            self.artifact['rows'].append({
                'condition': self.condition, 'family': family, 'full_site_count': 100,
                'scored_site_count': 98, 'mean_fve': .4, 'median_fve': .42,
                'mean_fve_ci95': [.3, .5], 'mean_fve_warnings': [],
                'mean_fve_percentage_points': 40., 'mean_fve_ci95_percentage_points': [30., 50.],
                'parent_comparisons': [{
                    'reference': 'capped_n1-n1', 'kind': 'frozen_parent', 'paired_sites': 90,
                    'intended_paired_sites': 100, 'independent_groups': 40,
                    'mean_delta': .025, 'ci95_delta': [-.01, .04],
                    'mean_delta_percentage_points': 2.5, 'ci95_delta_percentage_points': [-1., 4.],
                    'warning': None}]})
        self.artifact_path = self.root / 'reconstruction.json'
        self.review['reconstruction_conditions'] = [self.condition]
        self.seal()

    def seal(self):
        self.review['reconstruction_sha256'] = write(self.artifact_path, self.artifact)
        write(self.paths[2], self.review)
        self.inputs = report.checked_inputs(*self.paths)

    def intake(self):
        return report.checked_reconstruction(self.artifact_path, self.inputs[1], self.inputs[2],
                                             self.inputs[3], self.inputs[5])

    def render(self):
        artifact, sha = self.intake()
        return report.render(*self.inputs, reconstruction=artifact,
                             reconstruction_sha256=sha, reconstruction_source=self.artifact_path)

    def test_exact_authority_quality_objective_and_vector_required(self):
        original = deepcopy(self.artifact)
        for field in ('manifest_sha256', 'quality_analysis_sha256', 'objective', 'solver', 'vector_contract_sha256'):
            with self.subTest(field=field):
                self.artifact = deepcopy(original)
                self.artifact[field] = 'wrong'
                self.seal()
                with self.assertRaises(ValueError):
                    self.intake()
        self.artifact = original
        self.seal()
        self.artifact_path.write_text(self.artifact_path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'bound'):
            self.intake()

    def test_reviewed_artifact_cannot_be_omitted_or_conflict(self):
        with self.assertRaisesRegex(ValueError, 'must be supplied'):
            report.checked_reconstruction(None, self.inputs[1], self.inputs[2], self.inputs[3], self.inputs[5])
        self.review['presentation']['reconstruction_sha256'] = 'different'
        write(self.paths[2], self.review)
        self.inputs = report.checked_inputs(*self.paths)
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.intake()

    def test_percentage_points_parent_mask_interval_and_source_link(self):
        rendered = self.render()
        self.assertIn('40.00 pp; [+30.00, +50.00] pp', rendered)
        self.assertIn('+2.50 pp; [-1.00, +4.00] pp', rendered)
        self.assertIn('90 / 100 | 40', rendered)
        self.assertIn('98 / 100', rendered)
        self.assertIn(f'({self.artifact_path.name})', rendered)
        self.assertNotIn(str(self.artifact_path), rendered)
        self.assertIn(self.review['reconstruction_sha256'], rendered)
        self.assertIn('outside the 496 headline contrast adjustment', rendered)
        self.artifact['rows'][0]['parent_comparisons'][0]['mean_delta_percentage_points'] = .025
        self.seal()
        with self.assertRaisesRegex(ValueError, 'percentage-point'):
            self.intake()

    def test_empty_coverage_unavailable_and_real_zero_are_distinct(self):
        empty = self.artifact['rows'][0]
        empty.update(scored_site_count=0, mean_fve=None, median_fve=None,
                     mean_fve_ci95=None, mean_fve_percentage_points=None,
                     mean_fve_ci95_percentage_points=None)
        parent = empty['parent_comparisons'][0]
        parent.update(paired_sites=0, mean_delta=None, ci95_delta=None,
                      mean_delta_percentage_points=None, ci95_delta_percentage_points=None,
                      warning='No common valid sites')
        zero = self.artifact['rows'][1]
        zero.update(mean_fve=0, mean_fve_ci95=[0, 0], mean_fve_percentage_points=0,
                    mean_fve_ci95_percentage_points=[0, 0],
                    mean_fve_warnings=['Zero bootstrap variation'])
        self.seal()
        rendered = self.render()
        self.assertIn('Unavailable; Unavailable', rendered)
        self.assertIn('0 / 100', rendered)
        self.assertIn('0.00 pp; [+0.00, +0.00] pp † Zero bootstrap variation', rendered)
        empty['mean_fve'] = 0
        empty['mean_fve_percentage_points'] = 0
        self.seal()
        with self.assertRaisesRegex(ValueError, 'Empty reconstruction coverage'):
            self.intake()

    def test_duplicate_foreign_rows_and_excess_pair_mask_rejected(self):
        original = deepcopy(self.artifact)
        for change in ('duplicate', 'foreign', 'oversized_mask'):
            with self.subTest(change=change):
                self.artifact = deepcopy(original)
                if change == 'duplicate':
                    self.artifact['rows'].append(deepcopy(self.artifact['rows'][0]))
                elif change == 'foreign':
                    self.artifact['rows'][0]['condition'] = 'unknown'
                else:
                    self.artifact['rows'][0]['parent_comparisons'][0]['paired_sites'] = 101
                self.seal()
                with self.assertRaises(ValueError):
                    self.intake()

    def test_existing_checked_inputs_and_render_callers_still_work(self):
        self.assertEqual(len(self.inputs), 6)
        rendered = report.render(*self.inputs)
        self.assertNotIn('## Reconstruction fit:', rendered)
        self.assertIn('Complete result table', rendered)

    def test_task_notes_stay_bound_to_their_declared_comparison(self):
        comparison = {'condition': self.condition, 'reference': 'capped_n1-n1',
                      'notes': {family: f'Reviewed observation for {family}.'
                                for family in report.FAMILIES}}
        self.review['method_findings']['selection']['task_comparison'] = comparison
        self.seal()
        rendered = self.render()
        self.assertIn('These notes describe this setting, not every variant.', rendered)
        self.assertIn('Reviewed observation for chain_intermediates.', rendered)
        comparison['notes'].pop('chain_intermediates')
        with self.assertRaisesRegex(ValueError, 'declared representative comparison'):
            self.seal()
        comparison['notes']['chain_intermediates'] = 'Restored task note.'
        comparison['reference'] = 'undeclared-reference'
        with self.assertRaisesRegex(ValueError, 'declared representative comparison'):
            self.seal()


if __name__ == '__main__':
    unittest.main()
