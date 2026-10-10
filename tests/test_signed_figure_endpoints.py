"""Synthetic signed question/paired figures; no real outcome or API access."""
import copy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_signed_dashboard import fixture, module

figures = module('question_figure_exporter', 'export_signed_figures.py')


def synthetic_section():
    artifact, review = fixture()
    for family in figures.FAMILIES:
        review['expected_family_counts'][family]['cells'] = 8
    arms = {arm['condition']: arm for arm in artifact['measurement']['conditions']}
    for name, arm in arms.items():
        for family, status in arm['families'].items():
            status['expected_cells'] = 8
            artifact['lengths'][name][family]['outputs'] = 8
            metric = status['metrics']['contradiction_rate' if family == 'hallucination' else 'cell_recovery']
            metric.update(denominator=4 if family == 'hallucination' else 8)
            metric['value'] = metric['numerator']/metric['denominator']
            metric.update(ci95=None if name.startswith('prune') else [.1, .9],
                          warning='Synthetic few-group warning; not research evidence')
            if family == 'hallucination':
                status['original_grid_metrics']['original_grid_contradiction_rate'] = copy.deepcopy(metric)
    for field, key in [('paired_comparisons', 'metrics'), ('original_grid_paired_comparisons', 'original_grid_metrics')]:
        for row in artifact['measurement'][field]:
            left, right = (arms[name]['families'][row['family']][key][row['endpoint']]['value']
                           for name in (row['baseline_condition'], row['condition']))
            row.update(baseline=left, proposed=right, delta=right-left,
                       ci95_delta=None if row['condition'].startswith('prune') else [-.3, .6])
    review['artifact_sha256'] = sha256(json.dumps(artifact).encode()).hexdigest()
    section = figures.adapter.comparison(artifact, review, 'synthetic.json',
                                        review['artifact_sha256'], 'a'*64)
    return artifact, review, section


class SignedEndpointFigureTests(unittest.TestCase):
    def test_item_counts_and_intervals_are_copied_not_cell_averages(self):
        artifact, _, section = synthetic_section()
        before = copy.deepcopy(section)
        questions = figures.question_data(section)
        cells = figures.figure_data(section)
        for family in figures.FAMILIES:
            for i, name in enumerate(section['condition_ids']):
                endpoint = 'original_grid_contradiction_rate' if family == 'hallucination' else 'original_grid_item_pass_rate'
                exact = artifact['measurement']['conditions'][i]['families'][family]['original_grid_metrics'][endpoint]
                self.assertEqual(questions[family][i], {'condition': name, **exact})
                if family == 'hallucination':
                    self.assertEqual(questions[family][i], cells[family][i])
                    self.assertEqual(questions[family][i]['denominator'], 4)
                else:
                    self.assertEqual(questions[family][i]['denominator'], 2)
                    self.assertEqual(cells[family][i]['denominator'], 8)
                    self.assertNotEqual(questions[family][i]['value'], cells[family][i]['value'])
        self.assertEqual(section, before)

    def test_missing_duplicate_foreign_or_reaggregated_question_rows_reject(self):
        _, _, section = synthetic_section()
        mutations = []
        bad = copy.deepcopy(section); bad['original_item_rows'].pop(); mutations.append(bad)
        bad = copy.deepcopy(section); bad['original_item_rows'].append(bad['original_item_rows'][0]); mutations.append(bad)
        bad = copy.deepcopy(section); bad['original_item_rows'][0]['condition'] = 'foreign-n1'; mutations.append(bad)
        bad = copy.deepcopy(section); bad['original_item_rows'][0]['endpoint'] = 'item_accuracy'; mutations.append(bad)
        bad = copy.deepcopy(section); bad['original_item_rows'][0]['metric']['ci95'] = [.2, .8]; mutations.append(bad)
        bad = copy.deepcopy(section)
        metric = next(row['metric'] for row in bad['original_item_rows'] if row['family'] == 'multihop_mt')
        metric.update(denominator=8, value=metric['numerator']/8); mutations.append(bad)
        for bad in mutations:
            with self.subTest(rows=bad['original_item_rows'][:1]), self.assertRaises(ValueError):
                figures.question_data(bad)

    def test_paired_counts_delta_and_intervals_copy_the_correct_scope(self):
        _, _, section = synthetic_section()
        before = copy.deepcopy(section)
        for scope in ('original_item', 'cell'):
            pairs = figures.paired_data(section, scope)
            source = figures.question_data(section) if scope == 'original_item' else figures.figure_data(section)
            for family, rows in pairs.items():
                self.assertEqual(len(rows), 2)
                for row in rows:
                    exact = next(r for r in section['paired_rows'] if r['scope'] == scope and
                                 r['family'] == family and r['baseline_condition'] == row['baseline_condition'] and
                                 r['condition'] == row['condition'])
                    self.assertEqual({k: v for k, v in row.items() if not k.endswith('_metric')}, exact)
                    for key, name in [('baseline_metric', row['baseline_condition']), ('proposed_metric', row['condition'])]:
                        self.assertEqual(row[key], next(r for r in source[family] if r['condition'] == name))
                    if row['condition'].startswith('prune'):
                        self.assertIsNone(row['ci95_delta'])
        self.assertEqual(section, before)

    def test_foreign_scope_duplicate_delta_or_cohort_mismatch_rejects(self):
        _, _, section = synthetic_section()
        for field, value in [('scope', 'items_guess'), ('delta', .123), ('items', 99),
                             ('independent_groups', 99), ('condition', 'foreign-n1')]:
            bad = copy.deepcopy(section)
            row = next(r for r in bad['paired_rows'] if r['scope'] == 'original_item')
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                figures.paired_data(bad, 'original_item')
        bad = copy.deepcopy(section)
        bad['paired_rows'].append(copy.deepcopy(next(r for r in bad['paired_rows'] if r['scope'] == 'original_item')))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            figures.paired_data(bad, 'original_item')

    def test_optional_figures_are_png_pdf_with_exact_source_provenance(self):
        _, _, section = synthetic_section()
        before = copy.deepcopy(section)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'figures'
            result = figures.export(section, root, question_level=True, paired_deltas=True)
            stems = ['family-cell-rates', 'family-question-rates', 'paired-question-deltas-01', 'paired-cell-deltas-01']
            self.assertEqual({r['path'] for r in result['files']}, {f'{stem}.{ext}' for stem in stems for ext in ('png', 'pdf')})
            self.assertEqual(result['plotted_question_metrics'], figures.question_data(section))
            self.assertEqual(result['plotted_paired_metrics'], {s: figures.paired_data(section, s) for s in ('original_item', 'cell')})
            self.assertEqual(result['source_sha256'], section['source_sha256'])
            self.assertEqual(result['identities'], section['identities'])
            self.assertIn('not a question accuracy', result['question_task_rules']['hallucination'])
            self.assertEqual(result['missing_paired_scopes'], [])
            for row in result['files']:
                raw = (root/row['path']).read_bytes()
                self.assertEqual(sha256(raw).hexdigest(), row['sha256'])
                self.assertTrue(raw.startswith(b'\x89PNG\r\n\x1a\n') if row['path'].endswith('.png') else raw.startswith(b'%PDF-'))
            self.assertEqual(json.loads((root/'provenance.json').read_text())['plotted_question_metrics'], result['plotted_question_metrics'])
        self.assertEqual(section, before)

    def test_absent_pairs_and_undefined_native_hall_remain_missing(self):
        _, _, section = synthetic_section()
        section['paired_rows'] = []
        for rows in (section['cell_rows'], section['original_item_rows']):
            row = next(r for r in rows if r['family'] == 'hallucination')
            row['metric'].update(numerator=0, denominator=0, value=None, ci95=None)
        data = figures.question_data(section)['hallucination'][0]
        self.assertIsNone(data['value']); self.assertIsNone(data['ci95'])
        self.assertEqual(data['denominator'], 0)
        self.assertFalse(any(figures.paired_data(section, 'original_item').values()))

    def test_cli_legacy_defaults_and_new_optins_forward_to_export(self):
        args = ['export_signed_figures.py', '--analysis', 'fixture.json', '--review', 'review.json',
                '--output', 'new-figures', '--expected-sha256', 'a'*64]
        for flags, enabled in [([], False), (['--question-level', '--paired-deltas'], True)]:
            with patch('sys.argv', args+flags), patch.object(figures, 'load_section', return_value='checked') as load, \
                    patch.object(figures, 'export', return_value={'stage': 'validation', 'source_sha256': 'a'*64}) as export:
                figures.main()
            load.assert_called_once()
            self.assertIs(export.call_args.kwargs['question_level'], enabled)
            self.assertIs(export.call_args.kwargs['paired_deltas'], enabled)

    def test_test_reveal_required_before_outcome_bytes_even_with_new_flags(self):
        _, review = fixture('test')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'review.json'; path.write_text(json.dumps(review))
            args = ['export_signed_figures.py', '--analysis', str(Path(directory)/'absent-outcomes.json'),
                    '--review', str(path), '--output', str(Path(directory)/'figures'),
                    '--expected-sha256', review['artifact_sha256'], '--question-level', '--paired-deltas']
            with patch('sys.argv', args), patch.object(figures, 'export') as export, self.assertRaisesRegex(ValueError, 'reveal'):
                figures.main()
            export.assert_not_called()


if __name__ == '__main__':
    unittest.main()
