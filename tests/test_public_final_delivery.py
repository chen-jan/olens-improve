"""Synthetic final-export authority, source, privacy and legacy regression checks."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import build_public_dashboard as public
from append_signed_comparison import comparison
from test_final_slide_builder import final_fixture


def write(path, value):
    path.write_text(json.dumps(value))
    return {'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()}


def fixture(root, whole=True):
    _, report = final_fixture(root, whole=whole)
    old = report['signed_comparisons']['test']
    names, counts = old['condition_ids'], old['family_counts']
    arms, lengths = [], {}
    for name in names:
        method, n = name.rsplit('-n', 1)
        arm = {'condition': name, 'method': method, 'n': int(n),
               'measurement_complete': True, 'errors': [], 'families': {}}
        lengths[name] = {}
        for family, cohort in counts.items():
            cell = next(r['metric'] for r in old['cell_rows'] if (r['condition'], r['family']) == (name, family))
            item = next(r for r in old['original_item_rows'] if (r['condition'], r['family']) == (name, family))
            arm['families'][family] = {'expected_cells': cohort['cells'], 'missing_stage1': 0,
                'missing_stage2': 0, 'metrics': {'contradiction_rate' if family == 'hallucination' else 'cell_recovery': cell},
                'original_grid_metrics': {item['endpoint']: item['metric']}}
            lengths[name][family] = {'outputs': cohort['cells'], 'mean_qwen_tokens_all_intended': 10.,
                                    'mean_bullets_all_intended': 1.}
        arms.append(arm)
    identities = old['identities']
    measurement = {'stage': 'test', 'original_grid_contract': {'scope': 'SYNTHETIC fixed grids'},
        'conditions': arms, **{k: identities[k] for k in ('manifest_sha256', 'conditions_sha256', 'selection_sha256')},
        'analysis_authorization': {'split': 'test', 'coordinator_gate_sha256': identities['gate_sha256'],
            'freeze_sha256': identities['freeze_sha256'], 'condition_list_sha256': identities['conditions_sha256']}}
    for scope, field in [('cell', 'paired_comparisons'), ('original_item', 'original_grid_paired_comparisons')]:
        measurement[field] = [{k: v for k, v in r.items() if k != 'scope'} for r in old['paired_rows'] if r['scope'] == scope]
    analysis = {'status': 'complete_four_family_test_comparison', 'measurement': measurement, 'lengths': lengths,
        'selection_source_sha256': identities['selection_sha256'], 'limits': ['SYNTHETIC only'], 'paired_traces': []}
    analysis_pin = write(root / 'analysis.json', analysis)
    review = old['review']; review['artifact_sha256'] = analysis_pin['sha256']
    review_pin = write(root / 'test-review.json', review)
    test = comparison(analysis, review, analysis_pin['path'], analysis_pin['sha256'], review_pin['sha256'])
    report['signed_comparisons']['test'] = test
    sources = {}
    if whole:
        section = report['descriptive_whole_cohort']
        sources['whole_cohort'] = write(root / 'whole.json', section['measurement'])
        section['source_sha256'] = section['review']['artifact_sha256'] = sources['whole_cohort']['sha256']
    figures = {'status': 'exported_supplied_values_no_aggregation', 'stage': 'test', 'reviewed_by': 'root',
        **{k: test[k] for k in ('source_sha256', 'review_metadata_sha256', 'identities', 'family_counts')},
        'method_order': names, 'files': []}
    for field, key in [('cell_rows', 'plotted_cell_metrics'), ('original_item_rows', 'plotted_question_metrics')]:
        figures[key] = {f: [{'condition': name, **next(r['metric'] for r in test[field]
            if (r['condition'], r['family']) == (name, f))} for name in names] for f in counts}
    for scope, field in [('cell', 'plotted_cell_metrics'), ('original_item', 'plotted_question_metrics')]:
        indexed = {(r['condition'], f): r for f, rows in figures[field].items() for r in rows}
        figures.setdefault('plotted_paired_metrics', {})[scope] = {f: [{**r,
            'baseline_metric': indexed[r['baseline_condition'], f], 'proposed_metric': indexed[r['condition'], f]}
            for r in test['paired_rows'] if r['scope'] == scope and r['family'] == f] for f in counts}
    for stem in ('family-cell-rates', 'family-question-rates', 'paired-question-deltas-01', 'paired-cell-deltas-01'):
        for ext in ('png', 'pdf'):
            path = root / (stem + '.' + ext); path.write_bytes(b'SYNTHETIC file bytes only')
            figures['files'].append({'path': path.name, 'sha256': sha256(path.read_bytes()).hexdigest()})
    sources['test_figures'] = write(root / 'provenance.json', figures)
    pptx = root / 'draft.pptx'
    with zipfile.ZipFile(pptx, 'w') as archive:
        archive.writestr('ppt/slides/slide1.xml', '<text>SYNTHETIC slides</text>')
    pdf = root / 'draft.pdf'; pdf.write_bytes(b'%PDF SYNTHETIC fixture, not a rendered document')
    notes = root / 'speaker-notes.md'; notes.write_text('SYNTHETIC notes; no measured results.')
    markdown = root / 'reviewed-report.md'; markdown.write_text('SYNTHETIC reviewed report.')
    downloads = []
    for kind, path, name in [('editable_slides', pptx, 'slides.pptx'), ('slides_pdf', pdf, 'slides.pdf'),
                             ('notes', notes, 'notes.md'), ('report', markdown, 'research-report.md')]:
        downloads.append({'kind': kind, 'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest(),
            'public_name': name, 'label': 'Synthetic ' + kind, 'public_content_verified': True})
    deck = {'mode': 'reviewed_test', 'slides': 16, 'test_artifact_sha256': test['source_sha256'],
        'whole_cohort_complete': whole, 'whole_cohort_artifact_sha256': sources.get('whole_cohort', {}).get('sha256'),
        'outputs': {p.name: sha256(p.read_bytes()).hexdigest() for p in (pptx, notes)},
        'native_pptx_rendering_validated': False}
    sources['deck_build'] = write(root / 'build.json', deck)
    sources['deck_render'] = write(root / 'render.json', {'pages': 16, 'pdf_sha256': downloads[1]['sha256']})
    delivery = {'status': 'root_reviewed', 'reviewed_by': 'root', 'reviewed_utc': '2026-10-10T19:00:00Z',
        'test_reveal_authorized': True, 'test_artifact_sha256': test['source_sha256'],
        'test_review_metadata_sha256': test['review_metadata_sha256'], 'sources': sources, 'downloads': downloads}
    pin = write(root / 'delivery.json', delivery)
    return report, delivery, pin, figures


class FinalDeliveryTests(unittest.TestCase):
    def test_exact_source_reconstruction_and_authority_before_artifact_access(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); report, _, _, _ = fixture(root)
            test = report['signed_comparisons']['test']
            self.assertEqual(public.reviewed_test_attachment(report), test)
            original = deepcopy(test['cell_rows'])
            test['cell_rows'][0]['metric']['ci95'] = [0., 1.]
            with self.assertRaisesRegex(ValueError, 'exact reviewed source'): public.reviewed_test_attachment(report)
            test['cell_rows'] = original
            test['review']['test_reveal_authorized'] = False
            test['source_path'] = '/does-not-exist/unreviewed.json'
            with self.assertRaisesRegex(ValueError, 'reveal'): public.reviewed_test_attachment(report)
            self.assertIsNone(public.reviewed_test_attachment({'signed_comparisons': {}}))

    def test_whole_is_separate_and_exact_numeric_downloads_survive_privacy_filter(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); report, _, pin, _ = fixture(root)
            bundle = public.delivery_files(pin['path'], pin['sha256'], report, public.reviewed_test_attachment(report))
            output = root / 'public'; output.mkdir()
            cards, appendix = public.package_delivery(bundle, output)
            self.assertIn('not 469 held-out', appendix); self.assertIn('Grouped 95% interval', appendix)
            self.assertIn('<details', appendix); self.assertEqual(appendix.count('<tr><td>'), 48)
            exported = json.loads((output / 'descriptive-whole-469.json').read_text())
            self.assertEqual(exported['measurement'], report['descriptive_whole_cohort']['measurement'])
            self.assertFalse(public.LOCAL_PATH.search(json.dumps(exported)))
            for row in bundle['downloads']:
                self.assertEqual((output / 'downloads' / row['public_name']).read_bytes(), Path(row['path']).read_bytes())
            self.assertEqual(len(cards), 15)

    def test_preview_scope_never_claims_project_delivery_complete(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); report, _, pin, _ = fixture(root, whole=False)
            bundle = public.delivery_files(pin['path'], pin['sha256'], report, public.reviewed_test_attachment(report))
            output = root / 'public'; output.mkdir()
            _, appendix = public.package_delivery(bundle, output)
            self.assertNotIn('All 469 questions: descriptive appendix', appendix)
            self.assertIn('not a complete-project delivery', appendix)
            self.assertIn('held-out results remain pending', public.snapshot_banner(None))
            self.assertNotIn('pending', public.snapshot_banner(report['signed_comparisons']['test']))

    def test_manifest_capability_and_whole_completion_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); report, delivery, pin, _ = fixture(root)
            test = public.reviewed_test_attachment(report)
            delivery['test_reveal_authorized'] = False
            delivery['sources']['test_figures']['path'] = '/not-readable/unreviewed.json'
            pin = write(root / 'delivery.json', delivery)
            with self.assertRaisesRegex(ValueError, 'reveal'): public.delivery_files(pin['path'], pin['sha256'], report, test)
            report, delivery, pin, _ = fixture(root)
            report['descriptive_whole_cohort']['review']['status'] = 'pending'
            delivery['sources']['whole_cohort']['path'] = '/not-readable/unreviewed-whole.json'
            pin = write(root / 'delivery.json', delivery)
            with self.assertRaisesRegex(ValueError, 'separate reviewed reveal'):
                public.delivery_files(pin['path'], pin['sha256'], report, public.reviewed_test_attachment(report))
            report, delivery, pin, _ = fixture(root)
            report['descriptive_whole_cohort']['measurement']['conditions'][0]['measurement_complete'] = False
            delivery['sources']['whole_cohort'] = write(root / 'whole.json', report['descriptive_whole_cohort']['measurement'])
            section = report['descriptive_whole_cohort']
            section['source_sha256'] = section['review']['artifact_sha256'] = delivery['sources']['whole_cohort']['sha256']
            pin = write(root / 'delivery.json', delivery)
            with self.assertRaisesRegex(ValueError, 'coverage is incomplete'):
                public.delivery_files(pin['path'], pin['sha256'], report, public.reviewed_test_attachment(report))

    def test_figures_reject_changed_values_pins_missing_pairs_and_path_traversal(self):
        edits = [('values', lambda r: r['plotted_question_metrics']['multihop_mt'][0].__setitem__('ci95', [0, 1])),
                 ('duplicate', lambda r: r['files'].append(r['files'][0])),
                 ('traversal', lambda r: r['files'][0].__setitem__('path', '../family-cell-rates.png')),
                 ('missing', lambda r: r['files'].pop(0)),
                 ('missing-paired', lambda r: r['files'].__setitem__(slice(None), [p for p in r['files'] if not p['path'].startswith('paired-')])),
                 ('paired', lambda r: r['plotted_paired_metrics']['cell']['hallucination'][0].__setitem__('ci95_delta', [-1, 1]))]
        for name, edit in edits:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                root = Path(d); report, delivery, _, figures = fixture(root)
                edit(figures); delivery['sources']['test_figures'] = write(root / 'provenance.json', figures)
                pin = write(root / 'delivery.json', delivery)
                with self.assertRaises(ValueError): public.delivery_files(pin['path'], pin['sha256'], report, report['signed_comparisons']['test'])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); report, _, pin, _ = fixture(root)
            (root / 'family-cell-rates.png').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'figure bytes'): public.delivery_files(pin['path'], pin['sha256'], report, report['signed_comparisons']['test'])

    def test_download_allowlist_privacy_and_deck_scope_are_not_trusted_from_filename(self):
        for change in ('traversal', 'raw-dump', 'duplicate', 'privacy', 'relationship-privacy', 'wrong-deck', 'wrong-pdf'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as d:
                root = Path(d); report, delivery, _, _ = fixture(root)
                if change == 'traversal': delivery['downloads'][0]['public_name'] = '../slides.pptx'
                if change == 'raw-dump': delivery['downloads'][3]['path'] = str(root / 'analysis.json')
                if change == 'duplicate': delivery['downloads'].append(delivery['downloads'][0])
                if change == 'privacy':
                    row = delivery['downloads'][3]; Path(row['path']).write_text('/srv/private/evidence.json')
                    row['sha256'] = sha256(Path(row['path']).read_bytes()).hexdigest()
                if change == 'relationship-privacy':
                    row = delivery['downloads'][0]
                    with zipfile.ZipFile(row['path'], 'a') as archive:
                        archive.writestr('ppt/_rels/presentation.xml.rels',
                                         '<Relationship Target="/srv/private/source.json"/>')
                    row['sha256'] = sha256(Path(row['path']).read_bytes()).hexdigest()
                if change == 'wrong-deck':
                    deck = json.loads((root / 'build.json').read_text()); deck['test_artifact_sha256'] = 'f'*64
                    delivery['sources']['deck_build'] = write(root / 'build.json', deck)
                if change == 'wrong-pdf':
                    delivery['sources']['deck_render'] = write(root / 'render.json', {'pages': 16, 'pdf_sha256': 'f'*64})
                pin = write(root / 'delivery.json', delivery)
                with self.assertRaises(ValueError): public.delivery_files(pin['path'], pin['sha256'], report, report['signed_comparisons']['test'])

    def test_copy_rechecks_exact_bytes_if_reviewed_file_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); report, _, pin, _ = fixture(root)
            bundle = public.delivery_files(pin['path'], pin['sha256'], report, report['signed_comparisons']['test'])
            Path(bundle['figures'][0]['path']).write_bytes(b'changed after validation')
            with self.assertRaisesRegex(ValueError, 'changed before copy'):
                public.package_delivery(bundle, root / 'public')

    def test_main_legacy_and_reviewed_final_status_are_separate(self):
        for final in (False, True):
            with self.subTest(final=final), tempfile.TemporaryDirectory() as d:
                root = Path(d); report, _, pin, _ = fixture(root)
                report.pop('qualitative_reviews'); report['updated_utc'] = 'SYNTHETIC'
                if not final:
                    report['signed_comparisons'].pop('test'); report.pop('descriptive_whole_cohort')
                (root / 'dashboard').mkdir(); write(root / 'dashboard/report.json', report)
                (root / 'docs').mkdir(); (root / 'docs/REPORT.md').write_text('SYNTHETIC report')
                (root / 'scripts').mkdir()
                output = root / 'dist'; argv = ['export', '--output', str(output)]
                if final: argv += ['--delivery-review', pin['path'], '--delivery-review-sha256', pin['sha256']]
                with patch.object(public, '__file__', str(root / 'scripts/export.py')), patch.object(sys, 'argv', argv), \
                     patch.object(public, 'build', return_value='<header>details</header>'), \
                     patch.object(public, 'build_overview', return_value='<main>unchanged overview</main>'):
                    public.main()
                self.assertEqual(json.loads((output / 'report.json').read_text()), public.public_data(report))
                header = (output / 'details.html').read_text()
                self.assertEqual('held-out results remain pending' in header, not final)
                overview = (output / 'index.html').read_text()
                self.assertEqual('descriptive appendix' in overview, final)
                receipt = json.loads((root / 'publication-review.json').read_text())
                self.assertEqual('delivery_review_sha256' in receipt, final)


if __name__ == '__main__': unittest.main()
