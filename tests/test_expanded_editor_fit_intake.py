import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from expanded_editor_fit_intake import (NORMALIZATION, canonical_digest,
    pinned_editor_spec, validate_event_linkage, validate_editor_authority)


def raw_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin(path, expected):
    if raw_sha(path) != expected:
        raise ValueError('Changed raw source')


class EditorIntakeTests(unittest.TestCase):
    def test_real_pretty_spec_uses_canonical_event_digest(self):
        folder = Path('.state/editor-fit-intake-digest-fixture-v1')
        spec = folder / 'spec.json'; event = json.loads((folder / 'event.json').read_text())
        # This faithful serialization fixture isolates only the digest linkage;
        # supply the round field emitted by the real producer, without editing it.
        event['round'] = 1
        contract, linkage = pinned_editor_spec(spec, {str(spec): raw_sha(spec)})
        self.assertNotEqual(linkage, raw_sha(spec))
        self.assertEqual(linkage, '7f11379941549b0455d53a8928aba2c927ddcf90792009eba133cda3e19c116b')
        validate_event_linkage(event, contract, linkage)
        with self.assertRaises(ValueError):
            validate_event_linkage(event | {'spec_sha256': raw_sha(spec)}, contract, linkage)
        with self.assertRaises(ValueError):
            validate_event_linkage(event | {'round': 2}, contract, linkage)

    def test_missing_or_changed_raw_pin_cannot_hide_valid_canonical_linkage(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / 'spec.json'; spec.write_text(json.dumps({'round': 1}, indent=2))
            with self.assertRaises(ValueError):
                pinned_editor_spec(spec, {})
            pins = {str(spec): raw_sha(spec)}
            spec.write_text(spec.read_text() + '\n')  # Same parsed spec and canonical digest.
            with self.assertRaises(ValueError):
                pinned_editor_spec(spec, pins)

    def fixture(self, root):
        def write(name, value):
            path = root / name; path.write_text(json.dumps(value)); return str(path)
        code = write('scorer.py', 'approved scorer'); manifest = write('manifest.json', {})
        proposals = write('proposals.jsonl', {}); cells = write('cells.json', {})
        fresh = write('fresh.json', {}); history = write('history.jsonl', {})
        whitener = root / 'whitening_iolens_pooled_L20.safetensors'; whitener.write_bytes(b'approved moments')
        original = write('original.json', {'source_sha256': {str(whitener): raw_sha(whitener)}})
        policy = {'python': 'approved-python', 'checkpoint': 'approved-heads', 'production_cache': 'read-only-cache',
            'edit_cache': 'new-edit-cache', 'whitener_directory': str(root), 'runtime': 'approved-runtime',
            'sealed_manifest': manifest, 'sealed_manifest_sha256': raw_sha(manifest)}
        policy_path = write('policy.json', policy)
        authority = {'solver': 'scipy_exact', 'objective': '1-squared_residual/squared_target',
            'normalization': NORMALIZATION.copy(), 'manifest_sha256': raw_sha(manifest),
            'vector_contract_sha256': 'approved-vector', 'code_sha256': {code: raw_sha(code)},
            'whitening_authority': {'path': original, 'sha256': raw_sha(original)},
            'whitener_directory': str(root), 'whitener_sha256': {str(whitener): raw_sha(whitener)},
            'dispatch_policy': {'path': policy_path, 'sha256': raw_sha(policy_path)}}
        contract = {'round': 2, 'sealed_manifest_sha256': raw_sha(manifest), 'vector_contract': {'sha256': 'approved-vector'},
            'code_sha256': authority['code_sha256'].copy(), 'batch_size': 128, 'proposal_sha256': raw_sha(proposals),
            'cells_manifest_sha256': raw_sha(cells), 'fresh_manifest_sha256': raw_sha(fresh), 'history_sha256': raw_sha(history),
            'candidate_ids': {'cell': ['initial', 'edited']}, 'beam_width': 2, 'production_cache_read_only': True}
        command = ['approved-python', 'scripts/expanded_encode_edits.py', '--output', str(root), '--round', '2', '--batch-size', '128',
            '--proposals', proposals, '--cells-manifest', cells, '--fresh-manifest', fresh, '--history', history]
        for arg, field in (('--checkpoint', 'checkpoint'), ('--production-cache', 'production_cache'), ('--edit-cache', 'edit_cache'),
                ('--whitener-directory', 'whitener_directory'), ('--runtime', 'runtime'), ('--sealed-manifest', 'sealed_manifest')):
            command.extend([arg, policy[field]])
        task = {'id': 'fixture-round2', 'command': command, 'pins': [{'path': code, 'sha256': raw_sha(code)}]}
        signature = hashlib.sha256(json.dumps(task, sort_keys=True).encode()).hexdigest()
        dispatch = {'tasks': [task], 'completed_tasks': {task['id']: {'task_sha256': signature}}}
        return contract, authority, dispatch, {'cell': {'layer': 20}}, {'cells': 1, 'round': 2}, whitener

    def test_approved_code_dispatch_and_whitening_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); c, a, d, cells, terminal, _ = self.fixture(root)
            audit = validate_editor_authority(c, a, d, root, cells, terminal, pin)
            self.assertEqual(audit['canonical_spec_sha256'], canonical_digest(c))
            self.assertEqual(audit['sites'], 1)
            self.assertIn('not event metadata', audit['authority_scope'])

    def test_absolute_producer_code_path_matches_same_relative_queue_source(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            root = Path(tmp); c, a, d, cells, terminal, _ = self.fixture(root)
            original = next(iter(a['code_sha256'])); relative = str(Path(original).relative_to(Path.cwd()))
            a['code_sha256'] = {relative: a['code_sha256'][original]}
            d['tasks'][0]['pins'][0]['path'] = relative
            task = d['tasks'][0]
            d['completed_tasks'][task['id']]['task_sha256'] = hashlib.sha256(json.dumps(task, sort_keys=True).encode()).hexdigest()
            validate_editor_authority(c, a, d, root, cells, terminal, pin)

    def test_mutated_whitener_or_scorer_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); c, a, d, cells, terminal, w = self.fixture(root)
            w.write_bytes(b'other moments')
            with self.assertRaises(ValueError):
                validate_editor_authority(c, a, d, root, cells, terminal, pin)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); c, a, d, cells, terminal, _ = self.fixture(root)
            Path(next(iter(c['code_sha256']))).write_text('changed scorer')
            with self.assertRaises(ValueError):
                validate_editor_authority(c, a, d, root, cells, terminal, pin)

    def test_policy_and_successful_task_receipt_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); c, a, d, cells, terminal, _ = self.fixture(root)
            bad = copy.deepcopy(d); bad['completed_tasks'] = {}
            with self.assertRaises(ValueError):
                validate_editor_authority(c, a, bad, root, cells, terminal, pin)
            bad = copy.deepcopy(d); bad['tasks'][0]['command'][0] = 'unapproved-python'
            with self.assertRaises(ValueError):
                validate_editor_authority(c, a, bad, root, cells, terminal, pin)
            bad = copy.deepcopy(a); bad['normalization']['whitening_ridge_c'] = .2
            with self.assertRaises(ValueError):
                validate_editor_authority(c, bad, d, root, cells, terminal, pin)


if __name__ == '__main__':
    unittest.main()
