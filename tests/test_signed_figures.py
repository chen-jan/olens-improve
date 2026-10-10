"""Synthetic-only figure authorization and exact-value/provenance checks."""
import copy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_signed_dashboard import fixture, module

figures = module('figure_exporter','export_signed_figures.py')


class SignedFigureTests(unittest.TestCase):
    def test_long_method_labels_receive_space_and_keep_exact_order(self):
        names = ['best_n_specificity_mean_random_delete_matched_0.005-n32',
                 'random_delete_matched_a32_0.005-n32','capped_n1-n1']
        display = figures.method_labels(names)
        wrapped, positions, extent = figures.label_positions(display)
        self.assertEqual(display[0],'Specificity + matched random deletion')
        self.assertEqual(display[-1],'Capped single response')
        self.assertGreater(positions[1]-positions[0],1)
        self.assertGreater(extent,positions[-1])
        self.assertEqual(len(wrapped),len(names))

    def test_review_capability_precedes_any_outcome_read(self):
        artifact, review = fixture('test')
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'review.json'; path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,'reveal'):
                figures.load_section(Path(tmp)/'absent-outcomes.json',path,review['artifact_sha256'])

    def test_supplied_values_intervals_warnings_and_order_are_preserved(self):
        artifact, review = fixture()
        before = copy.deepcopy(artifact)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'analysis.json'; source.write_text(json.dumps(artifact))
            review_path = root/'review.json'; review_path.write_text(json.dumps(review))
            section = figures.load_section(source,review_path,review['artifact_sha256'])
            result = figures.export(section,root/'figures',cross_task=True)
            self.assertEqual(result['method_order'],review['condition_ids'])
            for family in figures.FAMILIES:
                key = 'contradiction_rate' if family=='hallucination' else 'cell_recovery'
                for i,row in enumerate(result['plotted_cell_metrics'][family]):
                    expected = artifact['measurement']['conditions'][i]['families'][family]['metrics'][key]
                    self.assertEqual({k:v for k,v in row.items() if k!='condition'},expected)
            self.assertEqual(artifact,before)
            self.assertIn('lower is better',result['axis_definitions']['hallucination'])
            self.assertIn('Role task passes',result['axis_definitions']['role_bound_association'])
            self.assertEqual(len(result['files']),4)
            for record in result['files']:
                path = root/'figures'/record['path']
                self.assertEqual(sha256(path.read_bytes()).hexdigest(),record['sha256'])
                self.assertGreater(path.stat().st_size,1000)
            with self.assertRaisesRegex(ValueError,'immutable'):
                figures.export(section,root/'figures')

    def test_undefined_rate_and_absent_interval_remain_missing(self):
        artifact, review = fixture()
        metric = artifact['measurement']['conditions'][0]['families']['hallucination']['metrics']['contradiction_rate']
        metric.update(numerator=0,denominator=0,value=None,ci95=None,warning='Synthetic zero specific outputs')
        # Remove contrasts that reference this changed endpoint; do not invent replacements.
        artifact['measurement']['paired_comparisons'] = [p for p in artifact['measurement']['paired_comparisons']
            if not (p['family']=='hallucination' and p['baseline_condition']=='capped_n1-n1')]
        raw = json.dumps(artifact).encode(); review['artifact_sha256'] = sha256(raw).hexdigest()
        section = figures.adapter.comparison(artifact,review,'synthetic.json',review['artifact_sha256'],'a'*64)
        data = figures.figure_data(section)['hallucination'][0]
        self.assertIsNone(data['value']); self.assertIsNone(data['ci95'])
        self.assertEqual(data['denominator'],0)
        self.assertEqual(data['warning'],'Synthetic zero specific outputs')


if __name__=='__main__':
    unittest.main()
