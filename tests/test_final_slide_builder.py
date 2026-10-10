"""Source/units and editable-output checks on a synthetic deck; no inference."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import build_final_slides as builder
from dashboard_qualitative import PANEL_IDS,PANEL_SHA


def fixture(root):
    conditions=['raw_n1-n1','capped_n1-n1']+[f'best_n_exact-n{n}' for n in [1,2,4,8,16,32]]
    metric={'value':.12,'numerator':12,'denominator':100,'ci95':[.08,.2],
            'items':20,'independent_groups':5,'warning':'Synthetic counts, not research evidence'}
    families={f:{'metrics':{'contradiction_rate' if f=='hallucination' else 'cell_recovery':deepcopy(metric)}} for f in builder.FAMILIES}
    rows=[{'condition':c,'family':f,'metric':deepcopy(metric)} for c in builder.KEY for f in builder.FAMILIES]
    case=lambda cid:{'cell_id':cid,'baseline':{'label':'Synthetic before','text':'- 2 + 2 = 4'},
                     'proposed':{'label':'Synthetic after','text':'- 2 + 2 = 4'},'assessment':'Unchanged; fixture only.'}
    q={'status':'root_reviewed','stage':'development_pilot','panel_sha256':PANEL_SHA,
       'anchors':[{'cell_id':cid} for cid in PANEL_IDS],'methods':{}}
    methods={}
    for k in builder.METHODS:
        methods[k]={'status':'Synthetic fixture','hypothesis':'Fixture hypothesis',
                    'limits':['Not measured evidence'],'next_action':'None','metrics':[]}
        q['methods'][k]={'takeaway':'Fixture only','variants':[{'id':'synthetic','cases':[case(cid) for cid in PANEL_IDS]}],'supplements':[]}
    methods['combinations'].pop('hypothesis')
    report={'updated_utc':'synthetic','signed_comparisons':{'validation':{'stage':'validation',
            'review':{'status':'root_reviewed'},'condition_ids':builder.KEY,'source_sha256':'a'*64,
            'cell_rows':rows,'paired_rows':[]}},'development_scaling':{'reviewed_by':'root','source_sha256':'b'*64,
            'measurement':{'conditions':[{'condition':c,'families':deepcopy(families)} for c in conditions]},
            'engineering_reference':{'cold_N32_lifecycle_through_first_selection_seconds':10,'basis':'Synthetic fixture'}},
            'qualitative_reviews':q,'methods':methods,'measured_cost_components':{}}
    p=root/'report.json';p.write_text(json.dumps(report));return p,report


def final_fixture(root, whole=False):
    """Invented rates only; no held-out files are opened."""
    p, report = fixture(root)
    names = ['raw_n1-n1', 'capped_n1-n1', 'best_n_exact-n16', 'best_n_exact-n32',
             'random_complete-n32', 'best_n_specificity_mean-n32', 'pooled_greedy_swap-n16',
             'pooled_greedy_swap-n32', 'best_n_specificity_mean_then_prune_0.005-n32',
             'best_n_specificity_mean_random_delete_matched_0.005-n32',
             'prune_loo_a32_0.005-n32', 'random_delete_matched_a32_0.005-n32']
    val = report['signed_comparisons']['validation']
    val['condition_ids'] = names
    val['cell_rows'] = [{'condition': name, 'family': f, 'metric': deepcopy(val['cell_rows'][0]['metric'])}
                        for name in names for f in builder.FAMILIES]
    counts = {f: {'items': 67, 'groups': 33, 'cells': 2678 + (2 if i == 3 else 0)}
              for i, f in enumerate(builder.FAMILIES)}
    pins = {key: 'c'*64 for key in ('manifest_sha256', 'conditions_sha256', 'selection_sha256', 'gate_sha256', 'freeze_sha256')}
    review = dict(status='root_reviewed', stage='test', reviewed_by='root', reviewed_utc='2026-10-10T18:00:00+00:00',
                  test_reveal_authorized=True, artifact_sha256='d'*64, condition_ids=names,
                  expected_family_counts=counts, findings=[{'claim': 'Synthetic finding, not research evidence.',
                                                           'evidence': 'Invented fixture rates only.'}], **pins)
    test = {'stage': 'test', 'review': review, 'source_sha256': 'd'*64, 'identities': pins,
            'condition_ids': names, 'family_counts': counts, 'cell_rows': [], 'original_item_rows': [], 'paired_rows': []}
    for name in names:
        for f in builder.FAMILIES:
            denominator = 100 if f == 'hallucination' else counts[f]['cells']
            cell = dict(value=12/denominator, numerator=12, denominator=denominator,
                        ci95=[.08,.2] if f=='hallucination' else [.001,.02], items=67,
                        independent_groups=33, warning='Synthetic source warning; not research evidence.')
            item = deepcopy(cell) if f == 'hallucination' else dict(cell, numerator=33 if 'specificity' in name else 32,
                denominator=67, value=(33 if 'specificity' in name else 32)/67, ci95=[.3,.7])
            endpoint = 'original_grid_contradiction_rate' if f == 'hallucination' else 'original_grid_item_pass_rate'
            test['cell_rows'].append({'condition':name, 'family':f, 'metric':cell})
            test['original_item_rows'].append({'condition':name, 'family':f, 'endpoint':endpoint, 'metric':item})
    for scope, rows in [('cell',test['cell_rows']), ('original_item',test['original_item_rows'])]:
        for f in builder.FAMILIES:
            b,pname = 'best_n_exact-n32','best_n_specificity_mean-n32'
            left = next(r['metric']['value'] for r in rows if r['family']==f and r['condition']==b)
            right = next(r['metric']['value'] for r in rows if r['family']==f and r['condition']==pname)
            endpoint = ('original_grid_contradiction_rate' if f=='hallucination' else 'original_grid_item_pass_rate') if scope=='original_item' else ('contradiction_rate' if f=='hallucination' else 'cell_recovery')
            test['paired_rows'].append(dict(scope=scope, family=f, baseline_condition=b, condition=pname,
                endpoint=endpoint, baseline=left, proposed=right, delta=right-left, ci95_delta=[-.04,.06],
                items=67, independent_groups=33, warning='Synthetic paired uncertainty'))
    report['signed_comparisons']['test'] = test
    if whole:
        all_counts = {f: {'items':117+(i==3), 'groups':50, 'cells':4858+(3 if i==3 else 0)}
                      for i,f in enumerate(builder.FAMILIES)}
        measurement = {'status':'complete_descriptive_whole_cohort','conditions':[],'paired_comparisons':[],
                       'source_sha256':{'synthetic':'e'*64},'limits':['Descriptive only; invented fixture.']}
        for name in names:
            families = {}
            for f in builder.FAMILIES:
                hall = f == 'hallucination'; den = 100 if hall else all_counts[f]['items']
                endpoint = 'original_grid_contradiction_rate' if hall else 'original_grid_item_pass_rate'
                families[f] = {endpoint: dict(value=50/den, numerator=50, denominator=den, ci95=[.3,.7],
                    items=all_counts[f]['items'], independent_groups=50, scope='original_grid',
                    unit='contradictory / specific readouts' if hall else 'items with any passing site / intended items')}
            measurement['conditions'].append({'condition':name,'measurement_complete':True,'families':families})
        for f in builder.FAMILIES:
            endpoint='original_grid_contradiction_rate' if f=='hallucination' else 'original_grid_item_pass_rate'
            value=measurement['conditions'][0]['families'][f][endpoint]['value']
            measurement['paired_comparisons'].append(dict(scope='original_grid', family=f,
                baseline_condition='best_n_exact-n32', condition='best_n_specificity_mean-n32',
                endpoint=endpoint, baseline=value, proposed=value, delta=0.0, ci95_delta=[-.02,.04],
                items=all_counts[f]['items'], independent_groups=50))
        report['descriptive_whole_cohort'] = {'status':'root_reviewed','reviewed_by':'root','source_sha256':'e'*64,
            'review':dict(status='root_reviewed', test_reveal_authorized=True, reviewed_utc='2026-10-10T18:01:00+00:00',
                         artifact_sha256='e'*64, condition_ids=names, expected_family_counts=all_counts),
            'measurement':measurement}
    p.write_text(json.dumps(report));return p,report


class FinalDraftTests(unittest.TestCase):
    def test_review_gate_and_empty_test_slots(self):
        with tempfile.TemporaryDirectory() as d:
            p,r=fixture(Path(d));source=builder.prepared(p)
            self.assertEqual(source['core_slides'],16);self.assertFalse(source['test_quality_access'])
            self.assertEqual(source['slides'][1]['kind'],'pending')
            self.assertEqual(source['slides'][5]['rows'][0]['value'],.12)
            missing=deepcopy(r);missing['signed_comparisons']['validation']['cell_rows'].pop();p.write_text(json.dumps(missing))
            with self.assertRaisesRegex(ValueError,'Complete four-family'):builder.prepared(p)
            r['signed_comparisons']['validation']['review']['status']='pending';p.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,'reviewed'):builder.prepared(p)

    def test_modified_measured_source_fails_and_counts_are_not_percentages(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,_=fixture(root);source=builder.prepared(p)
            source['slides'][5]['rows'][0]['value']=.25;s=root/'source.json';s.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,'exact reviewed'):builder.build(s,p,root/'out')
            source=builder.prepared(p);source['slides']=[{'kind':'table','title':'Count units',
                'rows':[{'condition':'synthetic','family':'hallucination','endpoint':'Unverifiable claims per produced output',
                         'value':2.2,'numerator':220,'denominator':100}]}]
            rendered=builder.pages(source);values=[x['text'] for x in rendered[0]['items'] if x['kind']=='text']
            self.assertIn('2.2',values);self.assertNotIn('220.00%',values)

    def test_editable_pptx_notes_and_immutable_output(self):
        from pptx import Presentation
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,_=fixture(root);s=root/'source.json';s.write_text(json.dumps(builder.prepared(p)))
            receipt=builder.build(s,p,root/'out');deck=Presentation(root/'out/draft.pptx')
            self.assertEqual(len(deck.slides),receipt['slides']);self.assertEqual(receipt['core_slides'],16)
            self.assertFalse(receipt['native_pptx_rendering_validated'])
            self.assertIn('not PPTX-to-PDF',receipt['native_pptx_renderer_limit'])
            self.assertTrue(all(slide.notes_slide.notes_text_frame.text for slide in deck.slides))
            self.assertTrue(any(shape.has_text_frame for slide in deck.slides for shape in slide.shapes))
            with self.assertRaisesRegex(ValueError,'immutable'):builder.build(s,p,root/'out')

    def test_options_branch_and_paired_axes_preserve_source_values(self):
        with tempfile.TemporaryDirectory() as d:
            p,r=fixture(Path(d));source=builder.prepared(p)
            self.assertEqual(source['slides'][3]['kind'],'options')
            rows=[{'family':f,'baseline_condition':'best_n_exact-n32',
                   'condition':'prune_loo_a32_0.005-n32','delta':-.012,
                   'ci95_delta':[-.031,.006],'items':20,'independent_groups':5}
                  for f in builder.FAMILIES]
            source['slides'][11]['rows']=deepcopy(rows)
            rendered=builder.pages(source)
            self.assertEqual(source['slides'][11]['rows'],rows)
            branch_lines=[x for x in rendered[3]['items'] if x['kind']=='line' and x['y']<800]
            self.assertEqual(len(branch_lines),6)  # shared stem and four alternatives
            labels=[x['text'] for x in rendered[11]['items'] if x['kind']=='text']
            self.assertIn('-3.10 pp',labels);self.assertIn('+3.10 pp',labels)
            self.assertEqual(labels.count('0 pp'),4)
            self.assertTrue(any('Lower is better: left' in x for x in labels))
            self.assertEqual(sum('Higher is better: right' in x for x in labels),3)
            self.assertEqual(labels.count('Paired change; lines: grouped 95% intervals'),4)


class ReviewedFinalTests(unittest.TestCase):
    def test_legacy_draft_ignores_optional_test_and_final_requires_explicit_reveal(self):
        with tempfile.TemporaryDirectory() as d:
            p,r=final_fixture(Path(d));without=deepcopy(r);without['signed_comparisons'].pop('test')
            p.write_text(json.dumps(without));old=builder.prepared(p)
            p.write_text(json.dumps(r));self.assertEqual(builder.prepared(p),dict(old,report_sha256=builder.digest(p)))
            r['signed_comparisons']['test']['review']['test_reveal_authorized']=False
            p.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,'reveal authority'):builder.prepared(p,final=True)
            class NotReadable:
                def __iter__(self):raise AssertionError('Unreviewed rows were accessed')
            r['signed_comparisons']['test']['original_item_rows']=NotReadable()
            with self.assertRaisesRegex(ValueError,'reveal authority'):builder.reviewed_test(r['signed_comparisons']['test'])

    def test_question_counts_intervals_and_native_hall_are_exact(self):
        with tempfile.TemporaryDirectory() as d:
            p,r=final_fixture(Path(d));source=builder.prepared(p,final=True)
            self.assertEqual(source['core_slides'],16);self.assertTrue(source['test_quality_access'])
            self.assertFalse(source['whole_cohort_complete']);self.assertIn('PREVIEW',source['status'])
            for i,f in enumerate(builder.FAMILIES,5):
                for row in source['slides'][i]['rows']:
                    exact=next(x for x in r['signed_comparisons']['test']['original_item_rows'] if x['family']==f and x['condition']==row['condition'])
                    self.assertEqual(row['source_metric'],exact['metric'])
                    self.assertEqual(row['ci'],exact['metric']['ci95'])
                    self.assertIn('Synthetic source warning',row['uncertainty'])
                    self.assertEqual(row['denominator'],100 if f=='hallucination' else 67)
            pairs=[s for s in source['slides'] if s['kind']=='paired' and 'TEST' in s['title']]
            found=[x for s in pairs for x in s['rows'] if x['family']=='multihop_mt']
            exact=next(x for x in r['signed_comparisons']['test']['paired_rows'] if x['scope']=='original_item' and x['family']=='multihop_mt')
            self.assertIn(exact,found)
            self.assertIn(exact,source['slides'][11]['rows'])
            pages=builder.pages(source);texts=[x['text'] for x in pages[5]['items'] if x['kind']=='text']
            self.assertIn('12/100',texts)
            self.assertTrue(all('TEST quality pending' not in x['text'] for page in pages for x in page['items'] if x['kind']=='text'))

    def test_foreign_revision_menu_endpoint_hall_and_missing_coverage_reject(self):
        with tempfile.TemporaryDirectory() as d:
            p,r=final_fixture(Path(d))
            edits=[lambda t:t['identities'].__setitem__('gate_sha256','f'*64),
                   lambda t:t['review'].__setitem__('condition_ids',list(reversed(t['condition_ids']))),
                   lambda t:t['original_item_rows'][1].__setitem__('endpoint','cell_recovery'),
                   lambda t:t['original_item_rows'][0]['metric'].__setitem__('ci95',[.01,.9]),
                   lambda t:t['original_item_rows'].pop(),
                   lambda t:t['paired_rows'][-1].__setitem__('delta',.1),
                   lambda t:t['cell_rows'][1]['metric'].update(denominator=100,value=.12),
                   lambda t:t['paired_rows'][-1].__setitem__('scope','items')]
            for edit in edits:
                changed=deepcopy(r);edit(changed['signed_comparisons']['test']);p.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):builder.prepared(p,final=True)

    def test_whole469_is_separate_descriptive_and_wrong_units_or_review_reject(self):
        with tempfile.TemporaryDirectory() as d:
            p,r=final_fixture(Path(d),whole=True);source=builder.prepared(p,final=True)
            self.assertTrue(source['whole_cohort_complete']);self.assertIn('DESCRIPTIVE',source['status'])
            self.assertEqual(source['whole_cohort_measurement'],r['descriptive_whole_cohort']['measurement'])
            whole=[s for s in source['slides'] if s['kind']=='rates' and ': all 469' in s['title']]
            self.assertEqual(len(whole),8)
            self.assertTrue(all('Descriptive DEV + VAL + TEST' in s['cohort'] for s in whole))
            self.assertEqual(sum(c['items'] for c in source['whole_cohort_review']['expected_family_counts'].values()),469)
            self.assertTrue(all(s['cohort'].startswith('Held-out TEST') for s in source['slides'][5:9]))
            paired=next(s for s in source['slides'] if s['title']=='All 469: descriptive paired changes')
            self.assertEqual(paired['rows'],r['descriptive_whole_cohort']['measurement']['paired_comparisons'])
            for edit in [lambda w:w['review'].__setitem__('test_reveal_authorized',False),
                         lambda w:w['measurement']['conditions'][0]['families']['multihop_mt']['original_grid_item_pass_rate'].__setitem__('unit','accuracy')]:
                changed=deepcopy(r);edit(changed['descriptive_whole_cohort']);p.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):builder.prepared(p,final=True)

    def test_final_editable_build_receipt_and_immutable_source(self):
        from pptx import Presentation
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,r=final_fixture(root,whole=True);source=builder.prepared(p,final=True)
            s=root/'source.json';s.write_text(json.dumps(source));receipt=builder.build(s,p,root/'out')
            self.assertTrue(receipt['test_quality_access']);self.assertTrue(receipt['whole_cohort_complete'])
            self.assertFalse(receipt['native_pptx_rendering_validated'])
            self.assertEqual(receipt['implementation_sha256']['build_final_slides.py'],builder.digest(builder.__file__))
            deck=Presentation(root/'out/draft.pptx')
            self.assertEqual(len(deck.slides),receipt['slides'])
            self.assertTrue(all(x.notes_slide.notes_text_frame.text for x in deck.slides))
            self.assertEqual(json.loads((root/'out/source.json').read_text()),source)
            for entry in source['slides'][16]['entries']:
                self.assertGreaterEqual(entry['page'],18)
                self.assertLessEqual(entry['page'],len(source['slides']))
            source['slides'][5]['rows'][0]['value']=.2;s.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,'exact reviewed'):builder.build(s,p,root/'changed')

    def test_undefined_native_hall_stays_unavailable_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,r=final_fixture(root)
            test=r['signed_comparisons']['test']
            for field in ('cell_rows','original_item_rows'):
                for row in test[field]:
                    if row['family']=='hallucination':
                        row['metric'].update(value=None,numerator=0,denominator=0,ci95=None)
            for row in test['paired_rows']:
                if row['family']=='hallucination':
                    row.update(baseline=None,proposed=None,delta=None,ci95_delta=None)
            p.write_text(json.dumps(r));source=builder.prepared(p,final=True)
            self.assertTrue(all(x['value'] is None for x in source['slides'][5]['rows']))
            text=[x['text'] for page in builder.pages(source) for x in page['items'] if x['kind']=='text']
            self.assertIn('Not measured',text);self.assertIn('Unavailable; missing denominator',text)

if __name__=='__main__':unittest.main()
