"""Frozen decision evidence must retain hashes and complete stage coverage."""
import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('activity', ROOT / 'scripts/refresh_dashboard_activity.py')
activity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activity)


def fixture(missing=0):
    files = {}
    for condition in activity.CHAIN_CONDITIONS:
        result = {'counts': {'n_missing_cells': missing, 'n_unjudged_cells': 0},
                  'n_items': 30, 'numbers': {'value': 2/30}}
        contract = {'partial_grid': False, 'manifest_expected_cells': 330, 'manifest_missing_cells': 0,
                    'cell_diagnostic': {'api_or_missing_unjudged_cells': 0, 'expected_cells': 330,
                                        'passed_cells': 3}}
        for name, body in [('results.json', result), ('project_contract.json', contract)]:
            raw = json.dumps(body)
            files[f'/frozen/{condition}/chain_intermediates/{name}'] = {
                'source_bytes_utf8': raw, 'sha256': sha256(raw.encode()).hexdigest()}
    return {'source_files': files}


class ActivityTests(unittest.TestCase):
    def test_frozen_hash_and_stage_coverage_are_required(self):
        with self.assertRaisesRegex(ValueError, 'coverage'):
            activity.pruning_evidence(fixture(missing=1), 'synthetic', 'synthetic')
        bad = fixture()
        next(iter(bad['source_files'].values()))['sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            activity.pruning_evidence(bad, 'synthetic', 'synthetic')

    def test_cell_and_item_counts_stay_separate(self):
        result = activity.pruning_evidence(fixture(), 'synthetic', 'synthetic')
        self.assertEqual(len(result['rows']), 6)
        self.assertEqual(result['rows'][0]['passed_cells'], 3)
        self.assertEqual(result['rows'][0]['passed_items'], 2)
        self.assertEqual(result['rows'][0]['expected_cells'], 330)
        self.assertEqual(result['rows'][0]['expected_items'], 30)


if __name__ == '__main__':
    unittest.main()
