"""Synthetic-only signed stage coverage, identity and display safeguards."""
import copy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


adapter = module('signed_adapter', 'append_signed_comparison.py')
dashboard = module('signed_renderer', 'build_dashboard.py')


def fixture(stage='validation'):
    families = adapter.FAMILIES
    counts = {f:{'cells':2, 'items':2, 'groups':1} for f in families}
    ids = ['capped_n1-n1', 'best_n_exact-n32', 'prune_loo_a32_0.005-n32']
    conditions, lengths = [], {}
    for ident, passed in zip(ids, (1, 2, 1)):
        method, n = ident.rsplit('-n', 1)
        entry = {'method':method, 'n':int(n), 'condition':ident,
                 'measurement_complete':True, 'errors':[], 'families':{}}
        lengths[ident] = {}
        for f in families:
            metric = {'numerator':passed, 'denominator':2, 'value':passed/2,
                      'items':2, 'independent_groups':1, 'ci95':[0,1]}
            key = 'contradiction_rate' if f == 'hallucination' else 'cell_recovery'
            original = 'original_grid_contradiction_rate' if f == 'hallucination' else 'original_grid_item_pass_rate'
            entry['families'][f] = {'expected_cells':2, 'empty_abstentions':0,
                'missing_stage1':0, 'missing_stage2':0, 'metrics':{key:metric},
                'original_grid_metrics':{original:copy.deepcopy(metric)}}
            if f == 'hallucination':
                entry['families'][f]['metrics']['false_span_tally'] = {
                    **metric, 'numerator':3, 'denominator':2, 'value':1.5}
            lengths[ident][f] = {'outputs':2, 'mean_qwen_tokens_all_intended':12.5,
                               'mean_bullets_all_intended':1.5}
        conditions.append(entry)
    pairs, originals = [], []
    for b,p in ((0,1), (1,2)):
        for f in families:
            key = 'contradiction_rate' if f == 'hallucination' else 'cell_recovery'
            left = conditions[b]['families'][f]['metrics'][key]['value']
            right = conditions[p]['families'][f]['metrics'][key]['value']
            pair = {'baseline_condition':ids[b], 'condition':ids[p], 'family':f, 'endpoint':key,
                'baseline':left, 'proposed':right, 'delta':right-left,
                'ci95_delta':[-.5,.5], 'items':2, 'independent_groups':1,
                'warning':'Synthetic tiny group count'}
            pairs.append(pair)
            originals.append({**pair, 'endpoint':'original_grid_contradiction_rate' if f == 'hallucination' else 'original_grid_item_pass_rate'})
    hashes = {k:sha256(k.encode()).hexdigest() for k in ('manifest_sha256','conditions_sha256','selection_sha256','gate_sha256','freeze_sha256')}
    m = {'stage':stage, 'original_grid_contract':{'scope':'synthetic original grids'},
         'conditions':conditions, 'paired_comparisons':pairs, 'original_grid_paired_comparisons':originals,
         **{k:hashes[k] for k in ('manifest_sha256','conditions_sha256','selection_sha256')},
         'analysis_authorization':{'split':stage,'coordinator_gate_sha256':hashes['gate_sha256'],
             'freeze_sha256':hashes['freeze_sha256'], 'condition_list_sha256':hashes['conditions_sha256']}}
    artifact = {'status':f'complete_four_family_{stage}_comparison', 'measurement':m,
        'lengths':lengths, 'selection_source_sha256':hashes['selection_sha256'], 'limits':['Synthetic only'],
        'paired_traces':[{'baseline_condition':ids[0], 'condition':ids[1], 'families':{
            'role_bound_association':{'examples':{'win':[{'cell_id':'synthetic-cell',
                'baseline':{'text':'</script><script>bad</script>'},
                'proposed':{'text':'- She does not trust him.'}}]}}}}]}
    raw = json.dumps(artifact).encode()
    review = {'status':'root_reviewed', 'reviewed_by':'synthetic reviewer',
        'reviewed_utc':'2026-10-10T10:00:00Z' if stage=='validation' else '2026-10-10T11:00:00Z',
        'stage':stage, 'artifact_sha256':sha256(raw).hexdigest(), **hashes,
        'condition_ids':ids, 'expected_family_counts':counts,
        'findings':[{'claim':'Synthetic reviewed finding', 'evidence':'Synthetic fixture; no empirical conclusion'}]}
    return artifact, review


def section(artifact, review):
    return adapter.comparison(artifact, review, 'synthetic.json', review['artifact_sha256'], 'a'*64)


class SignedDashboardTests(unittest.TestCase):
    def test_signed_charts_use_only_source_primary_pairs_and_keep_scopes(self):
        artifact, review = fixture()
        result = section(artifact, review)
        before = copy.deepcopy(result['paired_rows'])
        output = dashboard.signed_paired_charts(result['paired_rows'], 'validation')
        self.assertEqual(result['paired_rows'], before)
        self.assertEqual(output.count('<svg '), 16)  # Four families, two scopes and two controls.
        self.assertIn('Cell endpoint', output)
        self.assertIn('Original item endpoint', output)
        self.assertIn('Best-of-32 comparisons', output)
        self.assertIn('Capped single-sample comparisons', output)
        self.assertIn('-50.0 pp', output)
        self.assertIn('50.0 pp', output)
        self.assertIn('class="whisker"', output)
        self.assertIn('class="axis"', output)  # Existing helper draws the zero reference.
        self.assertIn('These validation comparisons', output)
        self.assertNotIn('These development comparisons', output)
        row = copy.deepcopy(before[0]); row['baseline_condition'] = 'prune_loo_a32_0.005-n32'
        row['ci95_delta'] = None
        output = dashboard.signed_paired_charts([row], 'test')
        self.assertIn('Component and sampling controls', output)
        self.assertIn('Not measured', output)
        row['delta'] = None
        self.assertEqual(dashboard.signed_paired_charts([row], 'test'), '')

    def test_within_arm_intervals_and_warnings_survive_each_endpoint_table(self):
        artifact, review = fixture()
        fam = artifact['measurement']['conditions'][0]['families']['hallucination']
        for field, endpoint, ci, warning in (
                ('metrics', 'contradiction_rate', [.1,.9], 'Cell interval warning <cell>'),
                ('original_grid_metrics', 'original_grid_contradiction_rate', [.2,.8], 'Item ratio warning'),
                ('metrics', 'false_span_tally', [.25,2.5], 'Span interval warning')):
            fam[field][endpoint]['ci95'] = ci
            fam[field][endpoint]['warning'] = warning
        result = section(artifact, review)
        self.assertEqual(result['auxiliary_rows'][0]['metric']['ci95'], [.25,2.5])
        output = dashboard.signed_comparison_section(result)
        for text in ('Per-method 95% interval: [10.00%, 90.00%]',
                     'Per-method 95% interval: [20.00%, 80.00%]',
                     '[0.25 spans per output, 2.50 spans per output]',
                     'Cell interval warning &lt;cell&gt;', 'Item ratio warning', 'Span interval warning',
                     'Paired-change intervals below'):
            self.assertIn(text, output)
        for ci in ([.9,.1], [0,float('inf')], [False,1], [1]):
            bad = copy.deepcopy(artifact)
            bad['measurement']['conditions'][0]['families']['hallucination']['metrics']['contradiction_rate']['ci95'] = ci
            with self.assertRaisesRegex(ValueError, 'within-arm interval'):
                section(bad, review)

    def test_paired_tally_units_are_explicit_and_unknown_unit_is_missing(self):
        artifact, review = fixture()
        endpoints = {'false_span_tally': 'spans per output',
                     'true_claim_tally': 'claims per output',
                     'unverifiable_claims_per_output': 'claims per output',
                     'disputed_claims_per_output': 'claims per output',
                     'future_endpoint': 'Unit not specified by this renderer'}
        for endpoint in endpoints:
            for i, arm in enumerate(artifact['measurement']['conditions']):
                arm['families']['hallucination']['metrics'][endpoint] = {
                    'numerator':i+2, 'denominator':2, 'value':(i+2)/2,
                    'ci95':None, 'warning':'No per-method interval', 'items':2, 'independent_groups':1}
            artifact['measurement']['paired_comparisons'].append({
                'baseline_condition':review['condition_ids'][0], 'condition':review['condition_ids'][1],
                'family':'hallucination', 'endpoint':endpoint, 'baseline':1, 'proposed':1.5,
                'delta':.5, 'ci95_delta':[.1,.9], 'items':2, 'independent_groups':1})
        output = dashboard.signed_comparison_section(section(artifact, review))
        for endpoint, unit in endpoints.items():
            label, scale, actual_unit = dashboard.signed_endpoint(endpoint)
            self.assertEqual((scale,actual_unit), (1,unit))
            self.assertIn(label+'; cell score; '+unit, output)
        self.assertIn('+0.50 [+0.10 to +0.90]', output)
        self.assertIn('Per-method 95% interval: not measured; No per-method interval', output)
        self.assertNotIn('future endpoint; cell score; claims per output', output)

    def test_complete_menu_and_endpoint_units_remain_separate(self):
        artifact, review = fixture()
        result = section(artifact, review)
        self.assertEqual(len(result['cell_rows']), 12)
        self.assertEqual(len(result['original_item_rows']), 12)
        self.assertEqual(len(result['length_rows']), 12)
        output = dashboard.build({'signed_comparisons':{'validation':result}})
        for label in ('Role task passes','Bridge mentions','Intermediate-number recovery',
                      'Original item aggregation','Output lengths','Earlier pilot/DEV costs are separate cohorts'):
            self.assertIn(label, output)
        self.assertNotIn('150.0%', output)  # False span means are not percentages.
        self.assertIn('1.5', output)
        for label in ('preselected methods', 'Preselected method', 'Per-method 95% interval', 'Items with any passing site'):
            self.assertIn(label, output)
        for jargon in ('signed menu', 'signed conditions', 'Within-arm 95%', 'Original item ANY pass', 'Stage provenance'):
            self.assertNotIn(jargon, output)

    def test_exact_hash_menu_and_stage_authority_are_required(self):
        artifact, review = fixture()
        for key in ('artifact_sha256','manifest_sha256','conditions_sha256','selection_sha256','gate_sha256','freeze_sha256'):
            bad = copy.deepcopy(review); bad[key] = 'b'*64
            with self.assertRaises(ValueError):
                adapter.comparison(artifact, bad, 'synthetic', review['artifact_sha256'], 'a'*64)
        bad = copy.deepcopy(review); bad['condition_ids'] = list(reversed(bad['condition_ids']))
        with self.assertRaisesRegex(ValueError, 'menu'):
            section(artifact, bad)
        bad = copy.deepcopy(artifact); bad['measurement']['analysis_authorization']['split'] = 'test'
        with self.assertRaisesRegex(ValueError, 'stage mismatch'):
            section(bad, review)

    def test_incomplete_stage_and_missing_lengths_or_original_metrics_fail(self):
        artifact, review = fixture()
        bad = copy.deepcopy(artifact)
        bad['measurement']['conditions'][1]['families']['hallucination']['missing_stage2'] = 1
        with self.assertRaisesRegex(ValueError, 'coverage'):
            section(bad, review)
        bad = copy.deepcopy(artifact); bad['lengths'][review['condition_ids'][1]]['multihop_mt']['outputs'] = 1
        with self.assertRaisesRegex(ValueError, 'Length cohort'):
            section(bad, review)
        bad = copy.deepcopy(artifact); bad['measurement']['conditions'][1]['families']['multihop_mt']['original_grid_metrics'] = {}
        with self.assertRaisesRegex(ValueError, 'original-grid endpoint'):
            section(bad, review)

    def test_pair_must_use_identical_source_values_and_groups(self):
        artifact, review = fixture()
        bad = copy.deepcopy(artifact); bad['measurement']['paired_comparisons'][0]['delta'] = 0
        with self.assertRaisesRegex(ValueError, 'Paired values'):
            section(bad, review)
        bad = copy.deepcopy(artifact); bad['measurement']['paired_comparisons'][0]['independent_groups'] = 2
        with self.assertRaisesRegex(ValueError, 'Paired group'):
            section(bad, review)

    def test_test_requires_explicit_reviewed_reveal_and_retains_validation(self):
        test, review = fixture('test')
        with self.assertRaisesRegex(ValueError, 'reveal'):
            section(test, review)
        review['test_reveal_authorized'] = True
        test_section = section(test, review)
        val, val_review = fixture()
        report = {'signed_comparisons':{'validation':section(val,val_review),'test':test_section}}
        with self.assertRaisesRegex(ValueError, 'reveal'):
            dashboard.build(report)
        report['test_reveal_authorized'] = True
        output = dashboard.build(report)
        self.assertLess(output.index('Reviewed test comparison'), output.index('Reviewed validation comparison'))
        self.assertIn('Cohort: test / validation / development', output)

    def test_only_explicitly_reviewed_traces_are_attached_and_escaped(self):
        artifact, review = fixture()
        self.assertEqual(section(artifact,review)['traces'], [])
        review['trace_refs'] = [{'baseline_condition':'capped_n1-n1','condition':'best_n_exact-n32',
            'family':'role_bound_association','category':'win','cell_id':'synthetic-cell',
            'interpretation':'Synthetic example only'}]
        output = dashboard.build({'signed_comparisons':{'validation':section(artifact,review)}})
        self.assertIn('She does not trust him.', output)
        self.assertNotIn('</script><script>bad</script>', output)
        self.assertIn('&lt;/script&gt;', output)
        review['trace_refs'][0]['cell_id'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'trace reference'):
            section(artifact,review)


if __name__ == '__main__':
    unittest.main()
