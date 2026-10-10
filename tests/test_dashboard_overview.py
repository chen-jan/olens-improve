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
        self.assertIn('Questions with at least one match',page)
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

    def test_scope_example_uses_bound_counts_and_hall_keeps_error_endpoint(self):
        report=fixture();section=report['signed_comparisons']['validation']
        for scope,counts in [('cell_rows',(7,200,.035)),('original_item_rows',(12,20,.6))]:
            row=next(r for r in section[scope] if r['family']=='role_bound_association' and r['condition']=='raw_n1-n1')
            row['metric'].update(numerator=counts[0],denominator=counts[1],value=counts[2],ci95=None)
        before=copy.deepcopy(report);page=overview.build(report)
        self.assertEqual(report,before)
        self.assertIn('7/200 activations match (3.50%)',page)
        self.assertIn('12/20 questions have at least one match (60.00%)',page)
        self.assertIn('Per activation',page)
        self.assertIn('its complement is not accuracy',page)
        self.assertIn('one unmodified released sample',page)
        self.assertIn('dropping only whole trailing bullets',page)
        data=overview.data_for_page(report)
        hall=overview.chart(data,'hallucination',overview.DEFAULT,scope='items')
        hall_cells=overview.chart(data,'hallucination',overview.DEFAULT,scope='cells')
        for condition in overview.DEFAULT:
            self.assertEqual(data['metrics']['cells']['hallucination'][condition],
                             data['metrics']['items']['hallucination'][condition])
        for numeric in ('12/100','12.0%','95% interval 8.00–20.00%'):
            self.assertEqual(hall.count(numeric),hall_cells.count(numeric))
        self.assertIn('question switch does not change this readout-level error rate',hall)
        self.assertIn('12/100',hall);self.assertIn('12.0%',hall)
        self.assertIn('Validation: 20 questions',hall)
        self.assertNotIn('Questions with at least one match at any',hall)
        role=overview.chart(data,'role_bound_association',overview.DEFAULT,scope='items')
        self.assertIn('Questions with at least one match at any',role)
        self.assertIn('12/20',role)

    def test_method_rate_labels_do_not_change_values_or_diagnostic_fit_units(self):
        m=overview.method_sections
        row={'family':'hallucination','condition':'raw_n1-n1','endpoint':'Contradictions / specific readouts',
             'value':.4,'ci':[.3,.5],'numerator':4,'denominator':10,'cohort':'Development pilot'}
        before=copy.deepcopy(row);plot=m.rate_plot([row],'Transcript contradictions','Development pilot')
        self.assertEqual(row,before)
        self.assertIn('Error rate per activation; lower is better, not accuracy',plot)
        self.assertIn('Development pilot',plot);self.assertIn('40.0%',plot);self.assertIn('4/10',plot)
        fit=dict(row,endpoint='FVE',value=.118,numerator=None,denominator=1,ci=None)
        table=m.table([fit])
        self.assertIn('activation reconstruction fit, not accuracy',table)
        self.assertIn('<td>0.118</td>',table);self.assertNotIn('11.80%',table)
        paired=dict(row,endpoint='Paired delta: Cell recovery',value=.02,numerator=None,
                    denominator=None,ci=[-.01,.04])
        paired_table=m.table([paired],paired=True)
        self.assertIn('change in percentage points; match per activation',paired_table)
        self.assertIn('+2.00 pp',paired_table)

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
        self.assertIn('complete development curve is not attached',page)
        self.assertIn('partial original grids',page)
        self.assertIn('No per-prefix reconstruction-fit curve',page)

    def test_complete_development_curves_keep_reference_counts_and_warn_about_eligibility(self):
        report=fixture();conditions=[]
        ids=['raw_n1-n1','capped_n1-n1']+[f'best_n_exact-n{n}' for n in (1,2,4,8,16,32)]
        for condition in ids:
            families={}
            for f in overview.FAMILIES:
                endpoint='contradiction_rate' if f=='hallucination' else 'cell_recovery'
                families[f]={'missing_stage1':0,'missing_stage2':0,'metrics':{endpoint:{
                    'value':.25,'numerator':25,'denominator':100,'ci95':[.1,.5],
                    'items':30,'independent_groups':7,'warning':'Few groups; interpret cautiously'}}}
            conditions.append({'condition':condition,'n':int(condition.rsplit('n',1)[1]),
                'measurement_complete':True,'families':families})
        report['development_scaling']={'reviewed_by':'root',
            'source_sha256':'bc582289b378a286a72ce239148dfc6f22aece28e79f47124cfa9a2ee12cc5cf',
            'measurement':{'conditions':conditions,'paired_comparisons':[]}}
        before=copy.deepcopy(report);text=overview.method_sections.development_scaling(report)
        self.assertEqual(report,before)
        self.assertEqual(text.count('class="task-chart"'),4)
        self.assertIn('25/100',text);self.assertIn('10.00 to 50.00%',text)
        self.assertIn('30 items · 7 related groups',text)
        self.assertIn('one transcript site and eleven role sites',text)
        self.assertIn('Few groups; interpret cautiously',text)
        self.assertIn('grey dashed: released original, unmodified',text)
        report['development_scaling']['measurement']['conditions'][0]['families']['hallucination']['missing_stage2']=1
        with self.assertRaisesRegex(ValueError,'Missing'):overview.method_sections.development_scaling(report)

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
