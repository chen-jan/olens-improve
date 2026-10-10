"""Offline pin, complete-bundle, numeric and privacy contracts."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_public_dashboard as public
from render_descriptive_grid import FAMILIES


def write_json(path, value):
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root):
    metric = {'numerator': 2, 'denominator': 5, 'value': .4, 'ci95': [.1, .7],
              'independent_groups': 3, 'warning': 'Small illustrative group count'}
    grid = {'slots': [{'expected_cells': 5, 'accounted_cells': 5,
                      'missing_required_results': 0, 'metric': metric}]}
    data = {'test_outcomes_accessed': False, 'private_source': '/srv/private/source.json',
            'job_id': 12345, 'stages': [
                {'stage': stage, 'conditions': [{'condition': 'capped_n1-n1',
                 'families': {f: grid for f in FAMILIES}}]}
                for stage in ('development', 'validation')]}
    analysis = root / 'data.json'; analysis_sha = write_json(analysis, data)
    figures = []
    for stage in ('development', 'validation'):
        for family in FAMILIES:
            for ext in ('png', 'pdf'):
                path = root / f'{stage}-{family}.{ext}'; path.write_bytes(path.name.encode())
                figures.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    receipt = {'source_sha256': analysis_sha, 'test_outcomes_accessed': False,
               'metrics_and_intervals_recomputed': False, 'figures': figures}
    figure_path = root / 'figures.json'; figure_sha = write_json(figure_path, receipt)
    review = {'status': 'root_reviewed', 'reviewed_by': 'root', 'sources': {
        'analysis': {'path': str(analysis), 'sha256': analysis_sha},
        'figures': {'path': str(figure_path), 'sha256': figure_sha}}}
    review_path = root / 'review.json'; review_sha = write_json(review_path, review)
    return review_path, review_sha, data, review, receipt


class DescriptiveMapTests(unittest.TestCase):
    def test_exact_complete_bundle_and_numeric_preservation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); path, sha, data, _, _ = fixture(root)
            bundle = public.descriptive_site_files(path, sha)
            self.assertEqual(len(bundle[0]), 16)
            self.assertEqual(bundle[1]['stages'], data['stages'])
            self.assertNotIn('job_id', bundle[1])
            self.assertFalse(public.LOCAL_PATH.search(json.dumps(bundle[1])))
            output = root / 'public'; output.mkdir()
            cards = public.package_descriptive_sites(bundle, output)
            copied = json.loads((output / 'figures/read-sites/grid-data.json').read_text())
            self.assertEqual(copied['stages'], data['stages'])
            self.assertEqual(len(cards), 9)
            self.assertEqual(sum('class="map-download"' in c for c in cards), 8)
            rendered = ''.join(cards)
            targets = re.findall(r'href="([^"]+)"', rendered)
            self.assertEqual(len(targets), 18)
            self.assertEqual(len(set(targets)), 18)
            for stage in ('Development', 'Validation'):
                for family in ('Transcript contradictions', 'Multi-hop facts', 'Arithmetic steps', 'Who did what'):
                    self.assertIn(stage + ': ' + family, rendered)
            for target in targets:
                self.assertTrue((output / target).is_file())
            self.assertEqual(rendered.count('>PNG</a>'), 8)
            self.assertEqual(rendered.count('>PDF</a>'), 8)
            for original in bundle[0]:
                self.assertEqual((output / 'figures/read-sites' / original.name).read_bytes(), original.read_bytes())

    def test_wrong_pins_and_missing_or_changed_figures_reject(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); path, sha, _, review, receipt = fixture(root)
            with self.assertRaisesRegex(ValueError, 'review pin'):
                public.descriptive_site_files(path, '0' * 64)
            figure = Path(receipt['figures'][0]['path']); original = figure.read_bytes()
            figure.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'figure bytes'):
                public.descriptive_site_files(path, sha)
            figure.write_bytes(original); figure.unlink()
            with self.assertRaises(FileNotFoundError): public.descriptive_site_files(path, sha)
            receipt['figures'].pop(0)
            review['sources']['figures']['sha256'] = write_json(root / 'figures.json', receipt)
            sha = write_json(path, review)
            with self.assertRaisesRegex(ValueError, 'all 16'): public.descriptive_site_files(path, sha)

    def test_receipt_binding_and_private_credentials_reject(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); path, sha, data, review, receipt = fixture(root)
            receipt['source_sha256'] = 'foreign'
            review['sources']['figures']['sha256'] = write_json(root / 'figures.json', receipt)
            sha = write_json(path, review)
            with self.assertRaisesRegex(ValueError, 'unchanged DEV/VAL'): public.descriptive_site_files(path, sha)
            data['secret'] = 'hf_' + 'x' * 25
            review['sources']['analysis']['sha256'] = write_json(root / 'data.json', data)
            receipt['source_sha256'] = review['sources']['analysis']['sha256']
            review['sources']['figures']['sha256'] = write_json(root / 'figures.json', receipt)
            sha = write_json(path, review)
            with self.assertRaisesRegex(ValueError, 'credentials'): public.descriptive_site_files(path, sha)


if __name__ == '__main__': unittest.main()
