"""Evidence-boundary tests for the additive presentation, without inference."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('target_presentation', ROOT/'scripts/build_target_only_presentation.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class TargetOnlyPresentationTests(unittest.TestCase):
    def test_pending_contains_no_results_and_preserves_raw_reference(self):
        data = p.validate(p.pending())
        self.assertEqual(len(data['methods']), 10)
        self.assertTrue(all(not m['metrics'] for m in data['methods']))
        slides = p.pages(data)
        self.assertEqual(len(slides), 11)
        for slide in (slides[0], slides[1], slides[2], slides[4], slides[6], slides[8]):
            labels = [i.get('text', '') for i in slide['items']]
            self.assertEqual(sum(x == 'Original released lens' for x in labels), 4)
            self.assertEqual(sum(x == 'Pending' for x in labels) % 4, 0)

    def test_reviewed_findings_lead_the_deck(self):
        data = p.pending()
        data.update(title='Reviewed action title', findings=['Reviewed task-specific finding'])
        slides = p.pages(data)
        self.assertEqual(slides[0]['title'], 'Reviewed action title')
        self.assertTrue(any(i.get('text') == 'Reviewed task-specific finding' for i in slides[0]['items']))

    def test_native_adapter_preserves_singular_uncertainty_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            analysis = base/'analysis.json'; inventory = base/'inventory.json'; review = base/'review.json'
            metrics = {f: {m: {'value': .5, 'numerator': 1, 'denominator': 2, 'ci95': [0, 1]}
                           for m in p.MENU} for f in p.TASKS}
            warning = 'Zero bootstrap variation; no certainty claim'
            analysis.write_text(json.dumps({'status': 'complete_exploratory', 'source_sha256': {},
                'cohort': p.pending()['coverage'], 'headline': {'conditions': metrics, 'comparisons': [
                    {'condition': p.REPEAT, 'reference': p.POOL, 'family': 'hallucination',
                     'delta': 0, 'ci95_delta': [0, 0], 'warning': warning}]}}))
            inventory.write_text(json.dumps({'conditions': [{'condition_id': m, 'actual_parent': p.MENU[m][1]}
                                                            for m in list(p.MENU)[6:]]}))
            review.write_text(json.dumps({'status': 'root_reviewed', 'analysis_sha256': p.digest(analysis),
                'inventory_sha256': p.digest(inventory), 'source_sha256': {},
                'resources': {'cards': [{'label': 'Measured CPU wall time', 'value': 'Unmeasured'}]}}))
            data = p.native_payload(analysis, inventory, review)
            method = next(m for m in data['methods'] if m['id'] == p.REPEAT)
            self.assertEqual(method['comparisons'][p.POOL]['hallucination']['warnings'], [warning])
            self.assertEqual(data['resources']['cards'][0]['value'], 'Unmeasured')

    def test_control_activation_methods_are_rejected(self):
        data = p.pending()
        data['methods'][3]['id'] = 'pooled_specificity_mean-n32'
        with self.assertRaisesRegex(ValueError, 'eligible'):
            p.validate(data)

    def test_actual_parent_cannot_be_replaced_by_specificity(self):
        data = p.pending()
        data['methods'][-1]['parent_id'] = 'pooled_specificity_mean-n32'
        with self.assertRaisesRegex(ValueError, 'parent'):
            p.validate(data)

    def test_unreviewed_metrics_cannot_enter_pending(self):
        data = p.pending()
        data['methods'][0]['metrics']['hallucination'] = {'value': .5, 'numerator': 1, 'denominator': 2, 'ci95': [0, 1]}
        with self.assertRaisesRegex(ValueError, 'unreviewed'):
            p.validate(data)

    def test_validated_requires_exact_counts_and_complete_cohort(self):
        data = p.pending()
        data.update(status='validated', source_hashes={'analysis': 'a'*64}, root_review={'status': 'root_reviewed'})
        for m in data['methods']:
            m['metrics'] = {f: {'value': .5, 'numerator': 1, 'denominator': 2, 'ci95': [0, 1]} for f in p.TASKS}
        p.validate(data)
        data['methods'][0]['metrics']['hallucination']['value'] = .4
        with self.assertRaisesRegex(ValueError, 'inconsistency'):
            p.validate(data)

    def test_native_adapter_rejects_stale_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            analysis = base/'analysis.json'; inventory = base/'inventory.json'; review = base/'review.json'
            analysis.write_text(json.dumps({'status': 'complete_exploratory', 'source_sha256': {}}))
            inventory.write_text(json.dumps({'conditions': []}))
            review.write_text(json.dumps({'status': 'root_reviewed', 'analysis_sha256': 'stale'}))
            with self.assertRaisesRegex(ValueError, 'bind'):
                p.native_payload(analysis, inventory, review)


if __name__ == '__main__':
    unittest.main()
