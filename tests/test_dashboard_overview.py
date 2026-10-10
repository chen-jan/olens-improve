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

    def test_all_method_variants_and_paired_intervals_preserved_without_filling_missing(self):
        report=fixture();m=overview.method_sections
        row={'family':'role_bound_association','condition':'consensus_exact_support0.125-n16',
             'endpoint':'Cell mention/binding recovery','value':.25,'ci':None,'numerator':2,
             'denominator':8,'eligible_count':8,'missing_count':0,'cohort':'Small development pilot',
             'uncertainty':'4 related groups; interval not supplied'}
        paired=dict(row,condition='consensus_exact_support0.125-n16 vs best_n_exact-n16',
                    endpoint='Paired delta: Cell mention/binding recovery',value=-.125,ci=[-.25,.125],
                    numerator=None,denominator=None)
        report['methods']['consensus']={'metrics':[row], 'paired_metrics':[paired], 'limits':['Audit failed; not a quality verdict']}
        before=copy.deepcopy(report);page=overview.build(report)
        self.assertEqual(report,before)
        self.assertIn('consensus_exact_support0.125-n16',page)
        self.assertIn('2/8',page);self.assertIn('Not estimated',page)
        self.assertIn('-12.50 pp',page);self.assertIn('-25.00 to +12.50 pp',page)
        self.assertIn('4 related groups',page)
        self.assertEqual(page.count('class="method-info" id="method-'),8)
        self.assertIn('No benchmark-quality curve',page)
        self.assertNotIn('0.0%<small>0/0',page)
        self.assertIn('Audit failed; not a quality verdict',page)

    def test_sampling_curve_keeps_every_prefix_and_separates_sparse_development(self):
        report=fixture();ns=[1,2,4,8,16,32]
        report['methods']['sample_selection']={'metrics':[], 'scaling':[{
            'label':'multihop_mt: recovery','cohort':'31 development items; partial grids',
            'points':[{'n':n,'value':.25,'ci':[.1,.5],'count':8} for n in ns]}]}
        page=overview.build(report)
        self.assertIn('Number of shared samples',page)
        self.assertIn('10.00–50.00%',page)
        for n in ns:self.assertIn(f'<td>{n}</td><td>25.00%',page)
        self.assertIn('N2/4/8/16 larger-development curve points are missing',page)
        self.assertIn('not an inferred best-of-1 curve point',page)
        self.assertIn('No per-prefix reconstruction-fit curve',page)

    def test_paired_validation_chart_never_claims_pilot_cohort(self):
        m=overview.method_sections
        row={'family':'multihop_mt','condition':'best_n_exact-n32 vs best_n_exact-n16',
             'endpoint':'Paired delta: Cell recovery','value':-.02,'ci':[-.05,.03],
             'cohort':'Validation: complete original grids','uncertainty':'20 items; 17 related groups'}
        rendered=m.paired_plot([row],'multihop_mt')
        self.assertIn('Validation: complete original grids',rendered)
        self.assertIn('17 related groups',rendered)
        self.assertNotIn('189 sites',rendered)
        self.assertIn('not a significance gate',rendered)

    def test_auxiliary_tallies_keep_count_units_and_do_not_become_paired_error_rates(self):
        report=fixture();s=report['signed_comparisons']['validation']
        metric={'numerator':220,'denominator':100,'value':2.2,'ci95':[1.8,2.7],
                'items':20,'independent_groups':5}
        s['auxiliary_rows']=[{'family':'hallucination','condition':'best_n_exact-n32',
                             'endpoint':'true_claim_tally','metric':metric}]
        s['paired_rows']=[{'family':'hallucination','condition':'best_n_exact-n32',
                          'baseline_condition':'capped_n1-n1','scope':'cell','endpoint':'off_topic_rate',
                          'delta':.99,'ci95_delta':[.9,1.],'items':20,'independent_groups':5}]
        page=overview.build(report)
        self.assertIn('True claims per intended output',page)
        self.assertIn('<td>2.2</td><td>1.8 to 2.7</td>',page)
        self.assertNotIn('+99.00 pp',page)
        self.assertIn('Unverifiable is not false',page)

    def test_operational_status_uses_source_and_not_hardcoded_six_arm_phase(self):
        report=fixture();report['activity']['overview_status']={
          'heldout_conditions':12,'development':'Extra curves incomplete.',
          'test':'Selection complete; quality pending.'}
        page=overview.build(report)
        self.assertIn('12 preselected comparisons',page)
        self.assertIn('Selection complete; quality pending.',page)
        self.assertNotIn('6 frozen methods',page)
        self.assertNotIn('reconstruction running',page)

    def test_pilot_unverifiable_tally_is_not_a_percentage_and_warnings_survive(self):
        row={'family':'hallucination','condition':'best_n_exact-n32',
             'endpoint':'Unverifiable claims per produced output','value':2.2,'ci':[1.8,2.7],
             'numerator':220,'denominator':100,'cohort':'Shared pilot'}
        table=overview.method_sections.table([row])
        self.assertIn('<td>2.2</td><td>1.8 to 2.7</td>',table)
        self.assertNotIn('220.00%',table)
        report=fixture();s=report['signed_comparisons']['validation']
        for r in s['cell_rows']:r['metric']['warning']='Few groups: uncertainty is fragile'
        page=overview.build(report)
        self.assertIn('Few groups: uncertainty is fragile',page)


if __name__=='__main__':unittest.main()
