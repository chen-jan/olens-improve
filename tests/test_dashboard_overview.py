"""Rendering preserves rates/intervals and refuses incomplete scientific input."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('overview',Path(__file__).parents[1]/'scripts/build_dashboard_overview.py')
overview=importlib.util.module_from_spec(spec);spec.loader.exec_module(overview)


def fixture():
    conditions=list(overview.NAMES)
    counts={f:{'items':20,'cells':100,'groups':5} for f in overview.FAMILIES}
    rows=[{'family':f,'condition':c,'metric':{'value':.12,'numerator':12,'denominator':100,
        'ci95':[.08,.2],'items':20,'independent_groups':5}} for f in counts for c in conditions]
    cost=[{'condition':c,'components':[{'component':'experimental_candidate_budget','value':int(c.rsplit('n',1)[1])},
        {'component':'recurring_helper','value':0}]} for c in conditions]
    return {'updated_utc':'2026-10-10T13:00:00+00:00','activity':{'heldout_items':268},
        'api':{'actual_usd':1.2,'reserved_usd':.4,'observed_utc':'a frozen timestamp'},'methods':{},
        'signed_comparisons':{'validation':{'stage':'validation','review':{'status':'root_reviewed','findings':[]},
            'family_counts':counts,'condition_ids':conditions,'cell_rows':rows,'original_item_rows':copy.deepcopy(rows),
            'cost_rows':cost,'source_sha256':'f'*64}}}


class OverviewTests(unittest.TestCase):
    def test_rendering_preserves_source_and_exposes_counts_intervals_scope(self):
        report=fixture();before=copy.deepcopy(report);page=overview.build(report)
        self.assertEqual(report,before)
        self.assertIn('12/100',page);self.assertIn('95% interval 8.00–20.00%',page)
        self.assertEqual(page.split('<script',1)[0].count('class="task-chart"'),4)
        self.assertIn('Whole items: any passing site',page)
        self.assertIn('No overall winner yet',page);self.assertIn('268 items',page)
        self.assertIn('Lower is better',page);self.assertIn('Higher is better',page)
        self.assertNotIn('/orcd/',page)

    def test_missing_metric_and_unreviewed_stage_fail_before_rendering(self):
        report=fixture();report['signed_comparisons']['validation']['cell_rows'].pop()
        with self.assertRaisesRegex(ValueError,'Incomplete'):overview.build(report)
        report=fixture();report['signed_comparisons']['validation']['review']['status']='draft'
        with self.assertRaisesRegex(ValueError,'reviewed'):overview.build(report)

    def test_heldout_count_never_inferred_from_quality(self):
        report=fixture();report['activity'].clear()
        with self.assertRaisesRegex(ValueError,'held-out item count'):overview.build(report)
        self.assertIn('268 items',overview.build(report,268))

    def test_focus_and_whole_item_axes_keep_original_rate_intervals(self):
        data=overview.data_for_page(fixture())
        focused=overview.chart(data,'multihop_mt',overview.DEFAULT)
        full=overview.chart(data,'multihop_mt',overview.DEFAULT,scope='items',full=True)
        for value in ('12/100','12.0%','95% interval 8.00–20.00%'):
            self.assertIn(value,focused);self.assertIn(value,full)
        self.assertIn('Axis: 0–20%',focused);self.assertIn('Axis: 0–100%',full)
        self.assertIn('a pass anywhere counts once',full)


if __name__=='__main__':unittest.main()
