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


if __name__=='__main__':unittest.main()
