"""Small offline fixtures for case-selection and immutable-source contracts."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_target_only_qualitative import (choose_cases, descriptor_index, pin,
    selected_sources, selection_difference)
import build_target_only_qualitative as exporter


def verdict(text='before', passed=False, kind=None, evidence=None):
    return {'text': text, 'pass': passed, 'empty': not text.strip(),
        'class': kind if kind is not None else ('empty' if not text.strip() else None),
        'evidence': evidence}


class TargetOnlyQualitativeTests(unittest.TestCase):
    def test_site_win_and_question_gain_are_distinct(self):
        cells = {cid: {'item_id': cid[0]} for cid in ('a0', 'a1', 'b0', 'b1')}
        before = {cid: verdict(passed=cid == 'a1') for cid in cells}
        after = {cid: verdict('after', passed=cid in ('a0', 'b1')) for cid in cells}
        cases, available = choose_cases(before, after, cells, 'chain_intermediates', 'method')
        chosen = {r['kind']: r for r in cases}
        self.assertEqual(chosen['win']['cell_id'], 'a0')
        self.assertTrue(chosen['win']['endpoint_evidence']['parent_item_pass'])
        self.assertTrue(chosen['win']['endpoint_evidence']['proposed_item_pass'])
        self.assertEqual(chosen['question_gain']['cell_id'], 'b1')
        self.assertFalse(chosen['question_gain']['endpoint_evidence']['parent_item_pass'])
        self.assertEqual(chosen['question_gain']['sampling_unit'], 'question')
        self.assertEqual(available['win']['count'], 2)
        self.assertEqual(available['question_gain']['count'], 1)
        self.assertEqual(available['question_loss']['status'], 'none_observed')

    def test_question_loss_uses_a_real_parent_passing_witness(self):
        cells = {'a0': {'item_id': 'a'}, 'a1': {'item_id': 'a'}}
        before = {'a0': verdict(), 'a1': verdict(passed=True)}
        after = {cid: verdict('after') for cid in cells}
        cases, _ = choose_cases(before, after, cells, 'multihop_mt', 'method')
        case = next(r for r in cases if r['kind'] == 'question_loss')
        self.assertEqual(case['cell_id'], 'a1')
        self.assertEqual(case['endpoint_evidence']['grid_cells'], 2)
        self.assertTrue(case['endpoint_evidence']['selected_cell_parent_pass'])

    def test_hall_silence_and_offtopic_do_not_count_as_consistent_wins(self):
        cells = {cid: {'item_id': cid} for cid in ('a', 'b', 'c', 'd')}
        before = {cid: verdict(kind='hallucinated') for cid in cells}
        after = {'a': verdict(''), 'b': verdict('unrelated', kind='off_topic'),
            'c': verdict('after', kind='consistent'), 'd': verdict(kind='hallucinated')}
        cases, available = choose_cases(before, after, cells, 'hallucination', 'method')
        chosen = {r['kind']: r for r in cases}
        self.assertEqual(chosen['win']['cell_id'], 'c')
        self.assertEqual(chosen['error_to_empty']['cell_id'], 'a')
        self.assertEqual(chosen['error_to_offtopic']['cell_id'], 'b')
        self.assertEqual(available['win']['count'], 1)
        self.assertEqual(available['regression']['status'], 'none_observed')

    def test_same_text_with_changed_judgment_is_retained(self):
        cells = {'a': {'item_id': 'a'}, 'b': {'item_id': 'b'}}
        before = {'a': verdict('identical', kind='consistent', evidence={'claims': {'true': 1}}),
            'b': verdict('identical', kind='consistent')}
        after = {'a': verdict('identical', kind='consistent', evidence={'claims': {'true': 2}}),
            'b': verdict('identical', kind='hallucinated')}
        cases, available = choose_cases(before, after, cells, 'hallucination', 'method')
        self.assertEqual(available['same_text_different_verdict']['count'], 2)
        case = next(r for r in cases if r['kind'] == 'same_text_different_verdict')
        self.assertEqual(case['cell_id'], 'a')
        self.assertEqual(next(r for r in cases if r['kind'] == 'regression')['cell_id'], 'b')

    def test_random_unchanged_selection_is_reproducible_and_not_first_case(self):
        cells = {f'a{i:02d}': {'item_id': f'a{i:02d}'} for i in range(30)}
        before = {cid: verdict() for cid in cells}
        after = {cid: verdict('changed') for cid in cells}
        one, _ = choose_cases(before, after, cells, 'multihop_mt', 'method')
        two, _ = choose_cases(before, after, dict(reversed(list(cells.items()))), 'multihop_mt', 'method')
        self.assertEqual(one, two)
        self.assertNotEqual(one[0]['cell_id'], 'a00')
        self.assertIn('seeded_uniform', one[0]['selection_policy'])
        with self.assertRaisesRegex(ValueError, 'complete identical grids'):
            choose_cases(before, {k: v for k, v in after.items() if k != 'a00'}, cells, 'multihop_mt', 'method')

    def test_pins_reject_changes_and_unanalysed_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.json'
            path.write_text('{}')
            pins = {}
            expected = pin(pins, path)
            path.write_text('{"changed": true}')
            with self.assertRaisesRegex(ValueError, 'Pinned source changed'):
                pin(pins, path, expected)
            with self.assertRaisesRegex(ValueError, 'absent from final native analysis'):
                pin({}, path, must_be_in_analysis=True)

    def test_descriptor_and_exact_selected_text_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = root / 'family.manifest.json'
            source = root / 'family.jsonl'
            ready = root / 'family.ready.json'
            manifest.write_text('{}')
            cell = {'family': 'multihop_mt', 'item_id': 'a', 'layer': 20,
                'position': 2, 'split': 'test', 'activation_sha256': 'activation'}
            row = cell | {'cell_id': 'a', 'selections': [{'method': 'method', 'n': 32,
                'text': '- exact', 'bullet_count': 1, 'token_count': 2}]}
            source.write_text(json.dumps(row)+'\n')
            pins = {}
            descriptor = {'ready': True, 'partial_grid': False, 'inventory_sha256': 'seal',
                'family': 'multihop_mt', 'manifest': str(manifest), 'manifest_sha256': pin(pins, manifest),
                'selections': str(source), 'selection_sha256': pin(pins, source),
                'conditions': [{'method': 'method', 'n': 32}]}
            ready.write_text(json.dumps(descriptor))
            pin(pins, ready)
            index = descriptor_index(root, {'method-n32'}, 'seal', pins)
            arms = {'method-n32': {'a': verdict('- exact')}}
            sources = selected_sources(index, 'multihop_mt', {'a'}, arms, {'a': cell})
            self.assertEqual(sources['method-n32', 'a']['selection']['text'], '- exact')
            arms['method-n32']['a']['text'] = '- rewritten'
            with self.assertRaisesRegex(ValueError, 'differs from official judged readout'):
                selected_sources(index, 'multihop_mt', {'a'}, arms, {'a': cell})
            descriptor['partial_grid'] = True
            ready.write_text(json.dumps(descriptor))
            pin(pins := {}, ready)
            with self.assertRaisesRegex(ValueError, 'sealed complete ready'):
                descriptor_index(root, {'method-n32'}, 'seal', pins)

    def test_unavailable_raw_fve_is_not_replaced_by_capped_score(self):
        before = {'selection': {'fits': None, 'bullet_count': 5, 'token_count': 100}}
        after = {'selection': {'fits': {'exact': {'fve': .8}}, 'bullet_count': 3, 'token_count': 80}}
        difference = selection_difference(before, after)
        self.assertIsNone(difference['exact_fve_delta'])
        self.assertIsNone(difference['parent_exact_fve'])
        self.assertEqual(difference['bullet_delta'], -2)
        self.assertEqual(difference['qwen_token_delta'], -20)

    def test_full_export_keeps_evidence_and_references_without_review_prose(self):
        """Four tiny banks exercise assembly; no upstream files or judge calls."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old, new = root/'old', root/'new'
            old.mkdir(); new.mkdir()
            pins = {}
            methods = {'repeat_swap-n32': 'pooled_greedy_swap-n32',
                'repeat_swap_then_prune_005-n32': 'repeat_swap-n32',
                'bounded_prune_refill_005-n32': 'pooled_greedy_swap_then_prune_0.005-n32',
                'repeated_swaps_random_delete_match_005-n32': 'repeat_swap-n32'}
            def write(path, value):
                path.write_text(json.dumps(value))
                return pin(pins, path)
            cells = {family: {'cell_id': family, 'family': family, 'item_id': family,
                'layer': 20, 'position': 2, 'split': 'test', 'activation_sha256': 'activation',
                'group_id': 'group', 'capture_spec': {'prompt': 'exact original prompt'}}
                for family in exporter.TITLES}
            fresh = root/'fresh.json'
            fresh_hash = write(fresh, {'cells': list(cells.values())})
            inventory = root/'inventory.json'
            inventory_hash = write(inventory, {'status': 'sealed', 'families': list(cells),
                'analysis': {'seed': exporter.SEED}, 'expected': {'cells': 4, 'items': 4},
                'fresh_manifest': {'path': str(fresh), 'sha256': fresh_hash},
                'conditions': [{'condition_id': c, 'actual_parent': p} for c, p in methods.items()]})
            names = set(methods) | set(exporter.REFERENCE_IDS)
            for directory, own_names, seal in [(old, exporter.REFERENCE_IDS, 'old-seal'), (new, methods, inventory_hash)]:
                for family, cell in cells.items():
                    own_manifest = directory/f'{family}.manifest.json'
                    mh = write(own_manifest, {'cells': [cell]})
                    journal = directory/f'{family}.jsonl'
                    selections = [{'method': c.rsplit('-n', 1)[0], 'n': int(c.rsplit('-n', 1)[1]),
                        'text': '- identical', 'fits': None, 'bullet_count': 1, 'token_count': 2} for c in own_names]
                    journal.write_text(json.dumps(cell | {'selections': selections})+'\n')
                    jh = pin(pins, journal)
                    write(directory/f'{family}.ready.json', {'family': family, 'ready': True,
                        'partial_grid': False, 'inventory_sha256': seal,
                        'manifest': str(own_manifest), 'manifest_sha256': mh,
                        'selections': str(journal), 'selection_sha256': jh,
                        'conditions': [{'method': r['method'], 'n': r['n']} for r in selections]})
            config = root/'api.json'
            write(config, {'baseline_descriptor_snapshot': str(old), 'baseline_inventory_sha256': 'old-seal',
                'output': 'new-judgments', 'baseline_judgments': 'old-judgments'})
            bank = root/'bank.json'
            write(bank, {'fixture': True})
            analysis = root/'analysis.json'
            analysis_hash = write(analysis, {'status': 'complete_exploratory', 'inventory_sha256': inventory_hash,
                'source_sha256': dict(pins), 'missing_condition_families': [],
                'cohort': {'questions': 4, 'cells': 4, 'all_previously_inspected': True},
                'complete_condition_families': [{'condition': c, 'family': f} for c in names for f in cells]})
            def read_arm(_root, family, _cells):
                return {family: verdict('- identical', passed=True,
                    kind='consistent' if family == 'hallucination' else None)}
            def enrich(traces, _measurement, _cells):
                for trace in traces:
                    for data in trace['families'].values():
                        for row in data['examples']['selected']:
                            for side in ('baseline', 'proposed'):
                                row[side]['evidence'] = {'retained_official_fixture': True}
                return {}
            args = SimpleNamespace(inventory=inventory, inventory_sha256=inventory_hash,
                analysis=analysis, analysis_sha256=analysis_hash, api_config=config,
                ready_directory=new, output=root/'cases.json')
            with patch.dict('os.environ', {'SLURM_JOB_ID': 'fixture'}), patch.object(exporter, 'read_arm', read_arm), \
                    patch.object(exporter, 'enrich_traces', enrich), patch.object(exporter, 'paths', lambda _: {'bank': bank}), \
                    patch.object(exporter, 'load_bank', lambda f: [{'id': f, 'prompt': 'original prompt'}]):
                summary = exporter.run(args)
            payload = json.loads(args.output.read_text())
            self.assertEqual(summary['cases'], 16)
            self.assertEqual(payload['new_judge_calls'], 0)
            for case in payload['cases']:
                self.assertEqual(case['kind'], 'unchanged')
                self.assertEqual(case['finding'], '')
                self.assertEqual(set(case['reference_outputs']), set(exporter.REFERENCE_IDS))
                self.assertTrue(case['original_raw']['evidence']['retained_official_fixture'])
                self.assertTrue(case['actual_parent']['evidence']['retained_official_fixture'])
                self.assertIn('original_capture_spec', payload['contexts'][case['context_ref']])


if __name__ == '__main__':
    unittest.main()
