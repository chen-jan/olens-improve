"""Offline adversarial provenance fixtures: no clients or inference imports."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_expansion_judge_contracts import BENCHMARK_COMMIT, load_approved_runtime_pin, verify_judge_contract


def fixture():
    pin = {'src/wsbench/evals/hallucination/judge.py': 'a' * 64}
    descriptor = {'family': 'hallucination', 'ready': True, 'inventory_sha256': 'b' * 64,
                  'manifest_sha256': 'c' * 64, 'selection_sha256': 'd' * 64,
                  'conditions': [{'method': 'capped_n1', 'n': 1}]}
    contract = {'benchmark_commit': BENCHMARK_COMMIT, 'runtime_source_hashes': pin,
                'manifest_expected_cells': 2, 'manifest_produced_cells': 2, 'manifest_missing_cells': 0,
                'partial_grid': False, 'project_reasoning_effort': 'none', 'project_judge_model': 'gpt-6-luna',
                'scientific_status': 'exploratory-full-bank-comparison', 'inventory_sha256': 'b' * 64,
                'original_splits_preserved': True, 'hallucination_stage2': {'required': True}}
    embedded = copy.deepcopy(contract)
    embedded['scientific_status'] = 'frozen-grid-comparison'
    del embedded['inventory_sha256'], embedded['original_splits_preserved']
    result = {'family': 'hallucination', 'config': {'dry_run': False}, 'rows': [{'class': 'consistent'}],
              'complete': False, 'pinned_instrument': False}
    scientific = {'method': 'capped_n1', 'n': 1, 'inventory_sha256': 'b' * 64,
                  'manifest_sha256': 'c' * 64, 'selection_sha256': 'd' * 64, 'partial_grid': False,
                  'coverage': {'expected_cells': 2, 'produced_cells': 2, 'missing_cell_ids': [], 'readouts_per_cell': 1}}
    summary = {'condition': scientific, 'families': {'hallucination': {
               'upstream': copy.deepcopy(result), 'project_contract': embedded}}}
    return dict(family='hallucination', method='capped_n1', n=1, expected_cells=2,
                inventory_sha256='b' * 64, descriptor=descriptor, summary=summary,
                result=result, contract=contract, approved_runtime_source_hashes=copy.deepcopy(pin))


class JudgeContractTests(unittest.TestCase):
    def test_known_outer_metadata_sequence_and_false_upstream_flags_are_valid(self):
        result = verify_judge_contract(**fixture())
        self.assertFalse(result['preserved_upstream_complete'])
        self.assertFalse(result['preserved_upstream_pinned_instrument'])
        self.assertEqual(result['inference_calls'], 0)

    def test_refreshed_summary_snapshot_is_also_valid(self):
        f = fixture()
        f['summary']['families']['hallucination']['project_contract'] = copy.deepcopy(f['contract'])
        verify_judge_contract(**f)

    def test_changed_result_even_with_unchanged_headline_is_rejected(self):
        f = fixture()
        f['result']['rows'][0]['class'] = 'hallucinated'
        with self.assertRaisesRegex(ValueError, 'upstream payload'):
            verify_judge_contract(**f)

    def test_identity_pin_and_counts_mutations_fail(self):
        changes = [ ('result', 'family', 'multihop_mt'), ('contract', 'benchmark_commit', 'wrong'),
                    ('contract', 'manifest_expected_cells', 3), ('contract', 'manifest_produced_cells', 1),
                    ('contract', 'manifest_missing_cells', False), ('contract', 'partial_grid', True),
                    ('contract', 'project_judge_model', 'other'), ('contract', 'project_reasoning_effort', 'medium'),
                    ('contract', 'scientific_status', 'frozen-grid-comparison'),
                    ('contract', 'inventory_sha256', 'e' * 64), ('contract', 'original_splits_preserved', 1)]
        for obj, key, value in changes:
            with self.subTest(obj=obj, key=key):
                f = fixture(); f[obj][key] = value
                with self.assertRaises(ValueError): verify_judge_contract(**f)

    def test_dryrun_must_be_explicit_false(self):
        for value in (True, None, 0):
            with self.subTest(value=value):
                f = fixture(); f['result']['config']['dry_run'] = value
                with self.assertRaisesRegex(ValueError, 'non-dry-run'): verify_judge_contract(**f)

    def test_scientific_descriptor_binding_and_single_readout_coverage(self):
        changes = [('method', 'raw_n1'), ('n', True), ('manifest_sha256', 'e' * 64),
                   ('selection_sha256', 'e' * 64), ('inventory_sha256', 'e' * 64)]
        for key, value in changes:
            with self.subTest(key=key):
                f = fixture(); f['summary']['condition'][key] = value
                with self.assertRaises(ValueError): verify_judge_contract(**f)
        f = fixture(); f['summary']['condition']['coverage']['readouts_per_cell'] = 2
        with self.assertRaises(ValueError): verify_judge_contract(**f)
        f = fixture(); f['descriptor']['conditions'].append({'method': 'capped_n1', 'n': 1})
        with self.assertRaisesRegex(ValueError, 'duplicated'): verify_judge_contract(**f)

    def test_normalization_does_not_hide_instrument_or_stage2_changes(self):
        for key, value in [('runtime_source_hashes', {'src/wsbench/evals/hallucination/judge.py': 'e' * 64}),
                           ('hallucination_stage2', {'required': False}), ('unexpected_override', True)]:
            with self.subTest(key=key):
                f = fixture(); f['summary']['families']['hallucination']['project_contract'][key] = value
                with self.assertRaisesRegex(ValueError, 'three documented'): verify_judge_contract(**f)

    def test_embedded_metadata_cannot_contain_wrong_prior_values(self):
        for key, value in [('scientific_status', 'wrong'), ('inventory_sha256', None), ('original_splits_preserved', False)]:
            with self.subTest(key=key):
                f = fixture(); f['summary']['families']['hallucination']['project_contract'][key] = value
                with self.assertRaisesRegex(ValueError, 'embedded'): verify_judge_contract(**f)

    def test_self_consistent_runtime_drift_fails_approved_pin(self):
        f = fixture()
        f['contract']['runtime_source_hashes']['src/wsbench/evals/hallucination/judge.py'] = 'e' * 64
        f['summary']['families']['hallucination']['project_contract']['runtime_source_hashes'] = copy.deepcopy(f['contract']['runtime_source_hashes'])
        with self.assertRaisesRegex(ValueError, 'pre-expansion pin'): verify_judge_contract(**f)

    def test_numeric_boolean_aliases_do_not_hide_payload_changes(self):
        f = fixture(); f['result']['complete'] = 0
        with self.assertRaisesRegex(ValueError, 'upstream payload'): verify_judge_contract(**f)
        f = fixture(); f['summary']['families']['hallucination']['project_contract']['hallucination_stage2']['required'] = 1
        with self.assertRaisesRegex(ValueError, 'three documented'): verify_judge_contract(**f)

    def test_receipt_sha_and_explicit_pointer_bind_runtime_pin(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'receipt.json'
            pin = fixture()['approved_runtime_source_hashes']
            raw = json.dumps({'approved': {'runtime_source_hashes': pin}}).encode()
            path.write_bytes(raw); digest = hashlib.sha256(raw).hexdigest()
            self.assertEqual(load_approved_runtime_pin(path, digest, pointer='/approved/runtime_source_hashes'), pin)
            path.write_bytes(raw + b' ')
            with self.assertRaisesRegex(ValueError, 'bytes changed'):
                load_approved_runtime_pin(path, digest, pointer='/approved/runtime_source_hashes')


if __name__ == '__main__':
    unittest.main()
