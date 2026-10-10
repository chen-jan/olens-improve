"""Synthetic only; no real held-out artifacts are opened."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'scripts/analyze_whole_cohort_descriptive.py'
spec = importlib.util.spec_from_file_location('whole_descriptive', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def manifest(stage, item_suffix=''):
    return {'cells': [{'cell_id': f'{f}|{stage}', 'family': f,
                       'item_id': stage + item_suffix, 'group_id': stage,
                       'layer': 20, 'position': 0, 'split': stage}
                      for f in m.FAMILIES]}


class WholeDescriptiveTests(unittest.TestCase):
    def test_pending_inputs_fail_before_artifact_reads(self):
        with patch.object(m, 'checked_json') as read:
            with self.assertRaisesRegex(ValueError, 'Pending'):
                m.run({'status': 'prepared_pending_root_review', 'reviewed_by': None})
        read.assert_not_called()

    def test_changed_implementation_pin_fails_before_artifact_reads(self):
        plan = {'status': 'root_reviewed_ready', 'reviewed_by': 'root',
                'stages': {s: {'report': {'path': 'unopened'}} for s in m.STAGES},
                'implementation_source_sha256': {'synthetic-script': 'expected'}}
        with patch.object(m, 'digest', return_value='changed'), patch.object(m, 'checked_json') as read:
            with self.assertRaisesRegex(ValueError, 'implementation changed'):
                m.run(plan)
        read.assert_not_called()

    def test_family_qualified_items_and_groups_and_exact_union(self):
        stages = {s: manifest(s) for s in m.STAGES}
        groups, counts = m.validate_union(stages, {'items': 12, 'cells': 12})
        self.assertEqual(len(groups), 12)  # Same literal item IDs across families are distinct.
        self.assertEqual(len(set(groups.values())), 12)
        self.assertEqual(counts['stages']['test'], {'items': 4, 'cells': 4})
        with self.assertRaisesRegex(ValueError, 'union'):
            m.validate_union(stages, {'items': 11, 'cells': 12})

    def test_shared_item_and_group_split_and_inconsistent_membership_rejected(self):
        for kind in ('item', 'group', 'inconsistent'):
            stages = {s: manifest(s) for s in m.STAGES}
            if kind == 'item':
                stages['test']['cells'][0]['item_id'] = 'development'
            elif kind == 'group':
                stages['test']['cells'][0]['group_id'] = 'development'
            else:
                copy = dict(stages['test']['cells'][0], cell_id='new-cell', group_id='other')
                stages['test']['cells'].append(copy)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                m.validate_union(stages, {'items': 12, 'cells': 12})

    def test_pool_ratio_of_sums_and_whole_group_paired_interval(self):
        names = ['baseline', 'proposed']
        counts = {n: {} for n in names}
        groups = {}
        for family in m.FAMILIES:
            keys = [(family, i) for i in ('dev1', 'dev2', 'test')]
            groups.update({keys[0]: (family, 'dev'), keys[1]: (family, 'dev'), keys[2]: (family, 'test')})
            endpoint = 'contradiction_rate' if family == 'hallucination' else 'cell_recovery'
            counts['baseline'][family] = {endpoint: dict(zip(keys, [(1, 1), (0, 1), (0, 8)]))}
            counts['proposed'][family] = {endpoint: dict(zip(keys, [(1, 1), (1, 1), (2, 8)]))}
        rows, paired = m.pool_counts(counts, groups, names, [('baseline', 'proposed')])
        value = rows[1]['families']['hallucination']['contradiction_rate']
        self.assertEqual((value['numerator'], value['denominator'], value['value']), (4, 10, .4))
        self.assertNotEqual(value['value'], (1 + .25) / 2)
        delta = paired[0]
        self.assertEqual(delta['independent_groups'], 2)
        self.assertEqual(delta['bootstrap_replicates'], 2000)
        expected = m.paired_group_interval(counts['baseline']['hallucination']['contradiction_rate'],
            counts['proposed']['hallucination']['contradiction_rate'], groups)
        self.assertEqual(delta['ci95_delta'], expected['ci95_delta'])
        self.assertAlmostEqual(delta['delta'], .3)

    def test_missing_menu_and_unknown_endpoint_units_rejected(self):
        with self.assertRaises(ValueError):
            m.method_names([{'method': 'a', 'n': 1}] * 12)
        with self.assertRaisesRegex(ValueError, 'units'):
            m.pool_counts({'a': {'hallucination': {'unknown': {('hallucination', 'x'): (1, 1)}}}},
                          {('hallucination', 'x'): ('hallucination', 'g')}, ['a'], [])

    def test_stage_menu_set_requires_all_exact_identities(self):
        menu = [{'method': f'm{i}', 'n': 1} for i in range(12)]
        names = m.method_names(menu)
        self.assertEqual(m.stage_method_names(menu[::-1], names), names[::-1])
        for changed in (menu[:-1], menu + [{'method': 'extra', 'n': 1}],
                        menu[:-1] + [{'method': 'extra', 'n': 1}], menu[:-1] + [menu[0]]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                m.stage_method_names(changed, names)

    def test_end_to_end_synthetic_preserves_counts_lengths_and_stage_refs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def write(path, body):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(body))
                return {'path': str(path), 'sha256': m.digest(path)}

            menu = [{'method': f'm{i}', 'n': 1} for i in range(12)]
            menu_ref = write(root / 'menu.json', menu)
            plan = {'status': 'root_reviewed_ready', 'reviewed_by': 'root', 'menu': menu_ref,
                    'stages': {}, 'expected_union': {'items': 12, 'cells': 12},
                    'comparison_pairs': [('m0-n1', 'm1-n1')]}
            for stage in m.STAGES:
                frozen = manifest(stage)
                manifest_ref = write(root / stage / 'manifest.json', frozen)
                # Historical VAL order differs, while its exact identities stay fixed.
                stage_menu = menu[::-1] if stage == 'validation' else menu
                stage_menu_ref = write(root / stage / 'menu.json', stage_menu)
                arms, lengths = [], {}
                for condition in m.method_names(stage_menu):
                    arm_root = root / stage / 'judgments'
                    sources = {}
                    lengths[condition] = {}
                    for cell in frozen['cells']:
                        family, item = cell['family'], cell['item_id']
                        read = {'id': item, 'layer': 20, 'pos': 0, 'samples': ['synthetic']}
                        if family == 'hallucination':
                            row = read | {'verdict': [{'idx': 0, 'class': 'consistent',
                                'claims': {'false': 0, 'true': 1, 'unverifiable': 0}}]}
                            numbers = {'metric': 'hallucination_rate', 'value': 0}
                        else:
                            row = {'id': item, 'layer': 20, 'pos': 0, 'pass': True,
                                   'kind_by_layer': {'20': 'hit'}, 'roles': ['bridge'],
                                   'layers': {'20': {'hits': {'bridge': True}}}}
                            numbers = {'metric': 'pass_rate', 'value': 1}
                        path = arm_root / condition / family / 'results.json'
                        ref = write(path, {'rows': [row], 'numbers': numbers})
                        sources[ref['path']] = ref['sha256']
                        read_path = arm_root / condition / f'{family}.readouts.jsonl'
                        ref = write(read_path, read)
                        sources[ref['path']] = ref['sha256']
                        lengths[condition][family] = {'outputs': 1,
                            'mean_qwen_tokens_all_intended': 3, 'mean_bullets_all_intended': 1}
                    arms.append({'condition': condition, 'condition_root': str(arm_root),
                        'measurement_complete': True, 'errors': [],
                        'families': {f: {} for f in m.FAMILIES}, 'source_sha256': sources})
                report_ref = write(root / stage / 'report.json', {'measurement': {
                    'manifest_sha256': manifest_ref['sha256'], 'conditions_sha256': stage_menu_ref['sha256'],
                    'original_grid_contract': {'synthetic': True}, 'conditions': arms}, 'lengths': lengths})
                plan['stages'][stage] = {'manifest': manifest_ref, 'conditions': stage_menu_ref, 'report': report_ref}

            def authorize(path, conditions, **kwargs):
                data = json.loads(Path(path).read_text())
                return data, data['cells'][0]['split'], {'synthetic': True}

            with patch.object(m, 'reporting_stage', side_effect=authorize), \
                    patch.object(m, 'original_grid_contract', return_value={'synthetic': True}):
                result = m.run(plan)
                self.assertEqual(result['coverage']['union'], {'items': 12, 'cells': 12})
                self.assertEqual(result['conditions'][0]['families']['multihop_mt']['cell_recovery']['numerator'], 3)
                self.assertEqual(result['conditions'][0]['families']['multihop_mt']['original_grid_item_pass_rate']['denominator'], 3)
                self.assertEqual(result['lengths']['m0-n1']['hallucination']['outputs'], 3)
                self.assertEqual(result['lengths']['m0-n1']['hallucination']['empty_outputs'], 0)
                self.assertEqual(result['stage_reports'], {s: plan['stages'][s]['report'] for s in m.STAGES})
                self.assertEqual([a['condition'] for a in result['conditions']], m.method_names(menu))
                # A report must still follow its own frozen stage menu exactly.
                val_path = Path(plan['stages']['validation']['report']['path'])
                val_pristine = val_path.read_bytes()
                wrong_order = json.loads(val_pristine)
                wrong_order['measurement']['conditions'].reverse()
                plan['stages']['validation']['report'] = write(val_path, wrong_order)
                with self.assertRaisesRegex(ValueError, 'method order'):
                    m.run(plan)
                val_path.write_bytes(val_pristine)
                plan['stages']['validation']['report']['sha256'] = m.digest(val_path)
                # Refuse an incomplete arm even if the new report hash is bound.
                report_path = Path(plan['stages']['test']['report']['path'])
                pristine = report_path.read_bytes()
                incomplete = json.loads(pristine)
                incomplete['measurement']['conditions'][0]['measurement_complete'] = False
                plan['stages']['test']['report'] = write(report_path, incomplete)
                with self.assertRaisesRegex(ValueError, 'Missing stage/condition'):
                    m.run(plan)
                report_path.write_bytes(pristine)
                plan['stages']['test']['report']['sha256'] = m.digest(report_path)

                # Every stage capability is checked before ANY outcome artifact.
                dev_path = Path(plan['stages']['development']['report']['path'])
                dev_pristine = dev_path.read_bytes(); dev_path.unlink()
                def deny_test(path, conditions, **kwargs):
                    answer = authorize(path, conditions, **kwargs)
                    if answer[1] == 'test':
                        raise ValueError('No TEST capability')
                    return answer
                with patch.object(m, 'reporting_stage', side_effect=deny_test):
                    with self.assertRaisesRegex(ValueError, 'No TEST capability'):
                        m.run(plan)  # Missing DEV report must not be opened first.
                dev_path.write_bytes(dev_pristine)

                # Changed source bytes fail closed.
                Path(next(iter(arms[0]['source_sha256']))).write_text('{}')
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    m.run(plan)


if __name__ == '__main__':
    unittest.main()
