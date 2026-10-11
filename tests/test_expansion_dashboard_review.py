import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'build_expansion_dashboard.py'
SPEC = importlib.util.spec_from_file_location('dashboard_build_review', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceBoundDashboardReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pack_path = self.root / 'pack.json'
        self.condition = 'pooled_greedy_swap-n16'
        case = {'cell_id': 'cell1', 'context_ref': 'cell1',
                'baseline_condition': 'capped_n1-n1',
                'baseline': {'text': 'Before', 'class': 'hallucinated', 'pass': False},
                'proposed': {'text': 'Exact source after', 'class': 'consistent', 'pass': False},
                'endpoint_evidence': {'unit': 'original_readout_site_class'},
                'selection_policy': 'deterministic_outcome_selected_supplement'}
        self.pack = {'manifest_sha256': 'inventory',
                     'conditions': {self.condition: {'families': {'hallucination': {
                         'outcome_selected': [case]}}}},
                     'contexts': {'cell1': {'source_bank_item': {'prompt': 'Source context'}}}}
        raw = json.dumps(self.pack).encode()
        self.pack_path.write_bytes(raw)
        self.pack_sha = hashlib.sha256(raw).hexdigest()
        self.review_path = self.root / 'review.json'
        self.review = {'status': 'root_reviewed_progress', 'manifest_sha256': 'inventory',
                       'results_sha256': 'results',
                       'qualitative_sources': [{'path': str(self.pack_path), 'sha256': self.pack_sha}],
                       'dashboard_examples': {self.condition: [{
                           'source_sha256': self.pack_sha, 'family': 'hallucination',
                           'kind': 'outcome_selected', 'cell_id': 'cell1',
                           'title': 'Audited change', 'analysis': 'Illustrative observation.'}]}}

    def resolve(self):
        self.review_path.write_text(json.dumps(self.review))
        return MODULE.checked_review(self.review_path, 'inventory', 'results', {self.condition})[0]

    def test_quotes_and_context_are_resolved_from_pinned_source(self):
        result = self.resolve()['resolved_examples'][self.condition][0]
        self.assertEqual(result['text'], 'Exact source after')
        self.assertEqual(result['baseline_text'], 'Before')
        self.assertEqual(json.loads(result['context']), {'prompt': 'Source context'})
        self.assertEqual(result['baseline_condition'], 'capped_n1-n1')

    def test_other_result_snapshot_is_rejected(self):
        self.review['results_sha256'] = 'other-results'
        with self.assertRaisesRegex(ValueError, 'bind'):
            self.resolve()

    def test_changed_evidence_pack_is_rejected(self):
        self.pack_path.write_text(json.dumps(self.pack) + '\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            self.resolve()

    def test_case_not_present_in_pinned_pack_is_rejected(self):
        self.review['dashboard_examples'][self.condition][0]['cell_id'] = 'different-cell'
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.resolve()

    def test_parent_comparison_uses_actual_parent_output(self):
        case = self.pack['conditions'][self.condition]['families']['hallucination']['outcome_selected'][0]
        case['original_baseline'] = case.pop('baseline')
        case['original_baseline_condition'] = case.pop('baseline_condition')
        case['parents'] = {'best_n_exact-n16': {'status': 'complete',
            'output': {'text': 'Actual chosen parent', 'class': 'hallucinated', 'pass': False},
            'endpoint_evidence': {'unit': 'original_readout_site_class', 'parent_class': 'hallucinated'}}}
        raw = json.dumps(self.pack).encode()
        self.pack_path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        self.review['qualitative_sources'][0]['sha256'] = digest
        selected = self.review['dashboard_examples'][self.condition][0]
        selected.update(source_sha256=digest, reference='best_n_exact-n16')
        result = self.resolve()['resolved_examples'][self.condition][0]
        self.assertEqual(result['baseline_text'], 'Actual chosen parent')
        self.assertEqual(result['baseline_condition'], 'best_n_exact-n16')

    def parent_case(self, *, status='complete', include_parent=True):
        case = self.pack['conditions'][self.condition]['families']['hallucination']['outcome_selected'][0]
        case['original_baseline'] = case.pop('baseline')
        case['original_baseline_condition'] = case.pop('baseline_condition')
        case['endpoint_evidence'] = None
        case['parents'] = {'capped_n1-n1': {
            'status': status, 'output': case['original_baseline'],
            'endpoint_evidence': {'unit': 'whole_original_question_grid',
                                  'parent_first_passing_cell': 'other-cell'}}} if include_parent else {}
        raw = json.dumps(self.pack).encode()
        self.pack_path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        self.review['qualitative_sources'][0]['sha256'] = digest
        self.review['dashboard_examples'][self.condition][0].update(
            source_sha256=digest, reference='capped_n1-n1')

    def test_original_reference_retains_declared_parent_grid_witness(self):
        self.parent_case()
        result = self.resolve()['resolved_examples'][self.condition][0]
        self.assertEqual(result['baseline_text'], 'Before')
        grid = json.loads(result['evidence'])['whole_question_evidence']
        self.assertEqual(grid['parent_first_passing_cell'], 'other-cell')

    def test_original_reference_without_declared_parent_keeps_original_evidence(self):
        self.parent_case(include_parent=False)
        result = self.resolve()['resolved_examples'][self.condition][0]
        self.assertEqual(result['baseline_text'], 'Before')
        self.assertIsNone(json.loads(result['evidence'])['whole_question_evidence'])

    def test_incomplete_declared_original_parent_is_rejected(self):
        self.parent_case(status='pending')
        with self.assertRaisesRegex(ValueError, 'not complete'):
            self.resolve()

    def artifact(self, kind, payload, *, bound=True):
        path = self.root / (kind + '.json')
        raw = json.dumps(payload).encode()
        path.write_bytes(raw)
        review = {kind + '_sha256': hashlib.sha256(raw).hexdigest()} if bound else {}
        return MODULE.checked_artifact(path, kind, review, {'vector_contract': {'sha256': 'vectors'}},
                                       'inventory', 'results', {self.condition})[0]

    def test_secondary_artifact_requires_explicit_review_and_exact_quality_source(self):
        payload = {'manifest_sha256': 'inventory', 'quality_analysis_sha256': 'results',
                   'objective': '1-squared_residual/squared_target', 'solver': 'scipy_exact',
                   'vector_contract_sha256': 'vectors', 'rows': []}
        self.assertEqual(self.artifact('reconstruction', payload), payload)
        with self.assertRaisesRegex(ValueError, 'bound'):
            self.artifact('reconstruction', payload, bound=False)
        payload['quality_analysis_sha256'] = 'different'
        with self.assertRaisesRegex(ValueError, 'source'):
            self.artifact('reconstruction', payload)

    def test_reconstruction_keeps_negative_fve_but_rejects_wrong_denominators(self):
        payload = {'manifest_sha256': 'inventory', 'quality_analysis_sha256': 'results',
                   'objective': '1-squared_residual/squared_target', 'solver': 'scipy_exact',
                   'vector_contract_sha256': 'vectors', 'rows': [{
                       'condition': self.condition, 'family': 'hallucination',
                       'mean_fve': -0.05, 'median_fve': 0.2, 'scored_site_count': 4,
                       'full_site_count': 5, 'parent_comparisons': []}]}
        self.assertEqual(self.artifact('reconstruction', payload)['rows'][0]['mean_fve'], -0.05)
        payload['rows'][0]['scored_site_count'] = 6
        with self.assertRaisesRegex(ValueError, 'coverage'):
            self.artifact('reconstruction', payload)

    def test_resource_artifact_must_preserve_exact_finite_menu(self):
        payload = {'manifest_sha256': 'inventory', 'status': 'partial_retrospective',
                   'method_effort': {self.condition: {'allocated_unique_method_api_usd': None}}}
        self.assertEqual(self.artifact('effort', payload), payload)
        payload['method_effort']['foreign'] = {}
        with self.assertRaisesRegex(ValueError, 'menu'):
            self.artifact('effort', payload)


if __name__ == '__main__':
    unittest.main()
