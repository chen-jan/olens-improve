"""Synthetic reporting gates; no validation/test artifacts or transport."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from olens_improve.reporting import FAMILIES, BENCHMARK_COMMIT, digest, summarize, reporting_stage


class ReportingStageTests(unittest.TestCase):
    def fixture(self, root, stage):
        root.mkdir()
        write = lambda name, body: (root/name).write_text(json.dumps(body))
        cells = [{'cell_id':f+'|a','family':f,'item_id':'a','layer':20,'position':3,
                  'group_id':f+':g','split':stage} for f in FAMILIES]
        write('manifest.json', {'split':stage,'partial_grid':True,'cells':cells})
        write('fresh.json', {'cells':[c | {'adapter_disabled':True,'activation_sha256':'synthetic'} for c in cells]})
        menu = [{'method':'capped_n1','n':1},{'method':'best_n_exact','n':32}]
        write('conditions.json',menu)
        write('freeze.json',{'status':'root_reviewed_frozen','conditions':menu,
                            'conditions_sha256':digest(root/'conditions.json')})
        gate = {'authorization_scope':'analysis','manifest_sha256':digest(root/'manifest.json'),
                'fresh_index_sha256':digest(root/'fresh.json'),'recapture_status':'passed',
                'production_generation_authorized':True,'authorized_cells':4,'maximum_samples_per_cell':32,
                'condition_list_sha256':digest(root/'conditions.json'),'freeze_sha256':digest(root/'freeze.json')}
        write('gate.json',gate)
        selections = [{'cell_id':c['cell_id'],'family':c['family'],'item_id':'a','layer':20,
                       'position':3,'split':stage,'activation_sha256':'synthetic',
                       'selections':[m | {'text':'a claim','token_count':3,'bullet_count':1} for m in menu]} for c in cells]
        (root/'selections.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selections))
        selection_sha = digest(root/'selections.jsonl')
        for arm in menu:
            folder = root/f"{arm['method']}-n{arm['n']}";folder.mkdir()
            identity = arm | {'manifest_sha256':digest(root/'manifest.json'),
                'selection_sha256':selection_sha,'partial_grid':True,
                'coverage':{'expected_cells':4,'produced_cells':4,'missing_cell_ids':[],'readouts_per_cell':1}}
            if stage != 'development':
                identity['analysis_authorization'] = {'split':stage,'fresh_manifest_sha256':digest(root/'fresh.json'),
                                                     'coordinator_gate_sha256':digest(root/'gate.json')}
            (folder/'condition.json').write_text(json.dumps(identity))
            for family in FAMILIES:
                fdir=folder/family;fdir.mkdir()
                contract={'manifest_expected_cells':1,'manifest_produced_cells':1,'manifest_missing_cells':0,
                          'benchmark_commit':BENCHMARK_COMMIT,'partial_grid':True,'split':[stage]}
                readout={'id':'a','layer':20,'pos':3,'samples':['a claim']}
                if family=='hallucination':
                    row=readout | {'verdict':[{'idx':0,'class':'consistent','claims':{'true':1,'false':0,'unverifiable':0}}]}
                    contract['hallucination_stage2']={'stage1_api_or_missing_readouts':0,'stage2_api_or_missing_readouts':0}
                else:
                    contract['cell_diagnostic']={'api_or_missing_unjudged_cells':0,
                        'rows':[{'item_id':'a','layer':20,'position':3,'pass':True}]}
                    if family=='role_bound_association':
                        row=readout | {'pass':True,'key':'synthetic-role','correct':[True,True,True]}
                        raw={'key':'synthetic-role','meta':{'golds':[1,1,1]},
                             'result':{'q1_choice':1,'q2_choice':1,'q3_choice':1,'evidence':'synthetic rationale'}}
                        (fdir/'cells.jsonl').write_text(json.dumps(raw)+'\n')
                    elif family=='chain_intermediates':
                        row={'id':'a','kind_by_layer':{'20':'hit'},'named_by_layer':{'20':[1]},
                             'basis_by_layer':{'20':'stated_result'},'start':0,'intermediates':[1],'answer':2,'depth':2}
                        raw={'key':'a|L020','result':{'values':[1],'basis':'stated_result','quote':'a claim','states_value':True}}
                        (fdir/'cells.jsonl').write_text(json.dumps(raw)+'\n')
                    else:row={'id':'a','roles':['bridge1'],'layers':{'20':{'hits':{'bridge1':['x']}}}}
                (fdir/'project_contract.json').write_text(json.dumps(contract))
                (fdir/'results.json').write_text(json.dumps({'family':family,'config':{'dry_run':False},'rows':[row]}))
                (folder/f'{family}.summary.json').write_text(json.dumps({'condition':identity,'families':{family:{'project_contract':contract}}}))
                (folder/f'{family}.readouts.jsonl').write_text(json.dumps(readout)+'\n')
        return selection_sha

    def kwargs(self, root):
        return {'fresh_manifest':root/'fresh.json','gate':root/'gate.json',
                'condition_list':root/'conditions.json','freeze':root/'freeze.json'}

    def test_equivalent_dev_val_metrics_and_grouped_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            dev=Path(tmp)/'dev';val=Path(tmp)/'val'
            dsha=self.fixture(dev,'development');vsha=self.fixture(val,'validation')
            d=summarize(dev/'manifest.json',dev/'conditions.json',dev,selection_sha=dsha)
            v=summarize(val/'manifest.json',val/'conditions.json',val,selection_sha=vsha,**self.kwargs(val))
            self.assertTrue(all(r['measurement_complete'] for r in v['conditions']))
            self.assertEqual([r['families'] for r in d['conditions']],[r['families'] for r in v['conditions']])
            self.assertEqual(d['paired_comparisons'],v['paired_comparisons'])
            self.assertNotIn('stage',d)
            self.assertEqual(v['stage'],'validation')

    def test_missing_blind_wrong_menu_and_test_gates_fail_before_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'v';self.fixture(root,'validation')
            with self.assertRaises(ValueError):reporting_stage(root/'manifest.json',root/'conditions.json')
            gate=json.loads((root/'gate.json').read_text());gate['authorization_scope']='blind_generation_only'
            (root/'gate.json').write_text(json.dumps(gate))
            with self.assertRaisesRegex(ValueError,'Blind'):reporting_stage(root/'manifest.json',root/'conditions.json',**self.kwargs(root))
            gate['authorization_scope']='analysis';(root/'gate.json').write_text(json.dumps(gate))
            (root/'enriched.json').write_text(json.dumps([{'method':'capped_n1','n':1,'extra':True},{'method':'best_n_exact','n':32}]))
            with self.assertRaisesRegex(ValueError,'exact freeze'):reporting_stage(root/'manifest.json',root/'enriched.json',**self.kwargs(root))
            body=json.loads((root/'manifest.json').read_text());body['split']='test'
            for c in body['cells']:c['split']='test'
            (root/'manifest.json').write_text(json.dumps(body))
            with self.assertRaises(ValueError):reporting_stage(root/'manifest.json',root/'conditions.json',**self.kwargs(root))

    def test_entrypoint_guard_and_complete_fixture(self):
        spec=importlib.util.spec_from_file_location('signed_menu',Path(__file__).parents[1]/'scripts/analyze_signed_menu.py')
        module=importlib.util.module_from_spec(spec)
        import sys
        with patch.object(sys,'path',[str(Path(__file__).parents[1]/'scripts')]+sys.path):spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'v';selection_sha=self.fixture(root,'validation')
            args=SimpleNamespace(manifest=root/'manifest.json',conditions=root/'conditions.json',judgments=root,
                selections=root/'selections.jsonl',selection_sha256=selection_sha,output=root/'analysis.json',
                fresh_manifest=None,gate=None,condition_list=None,freeze=None)
            with patch.object(module,'digest',side_effect=AssertionError('Must not read selected output before gate')):
                with self.assertRaises(ValueError):module.run(args)
            for k,v in self.kwargs(root).items():setattr(args,k,v)
            context={'a':{'exact_upstream_mc_block':'synthetic choices','gold_choice_indexes':[1,1,1]}}
            with patch.object(module,'role_contexts',return_value=(context,{})):module.run(args)
            result=json.loads(args.output.read_text())
            self.assertEqual(result['status'],'complete_four_family_validation_comparison')
            self.assertEqual(result['lengths']['best_n_exact-n32']['hallucination']['outputs'],1)
            self.assertTrue(result['paired_traces'])
            example=result['paired_traces'][0]['families']['role_bound_association']['examples']['unchanged'][0]
            self.assertEqual(example['proposed']['evidence']['returned_choice_indexes'],[1,1,1])
            self.assertEqual(example['proposed']['evidence']['rationale'],'synthetic rationale')
            self.assertTrue(result['trace_evidence_source_sha256'])
            cache=root/'best_n_exact-n32/role_bound_association/cells.jsonl'
            body=json.loads(cache.read_text());body['result']['q1_choice']=2;cache.write_text(json.dumps(body)+'\n')
            args.output=root/'wrong-cache-analysis.json'
            with patch.object(module,'role_contexts',return_value=(context,{})):
                with self.assertRaisesRegex(ValueError,'Retained role choices'):module.run(args)

    def test_component_and_budget_pairs_use_only_signed_arms(self):
        spec=importlib.util.spec_from_file_location('signed_menu_pairs',Path(__file__).parents[1]/'scripts/analyze_signed_menu.py')
        module=importlib.util.module_from_spec(spec)
        import sys
        with patch.object(sys,'path',[str(Path(__file__).parents[1]/'scripts')]+sys.path):spec.loader.exec_module(module)
        menu=[{'method':m,'n':n} for m,n in [('best_n_exact',16),('best_n_exact',32),
            ('pooled_greedy_swap',16),('pooled_greedy_swap',32),('best_n_specificity_mean',32),
            ('prune_loo_a32_0.005',32),('best_n_specificity_mean_then_prune_0.005',32),
            ('best_n_specificity_mean_random_delete_matched_0.005',32)]]
        pairs=module.component_pairs(menu)
        self.assertIn(('prune_loo_a32_0.005-n32','best_n_specificity_mean_then_prune_0.005-n32'),pairs)
        self.assertIn(('best_n_exact-n16','best_n_exact-n32'),pairs)
        self.assertIn(('pooled_greedy_swap-n16','pooled_greedy_swap-n32'),pairs)
        self.assertIn(('best_n_specificity_mean_random_delete_matched_0.005-n32',
                       'best_n_specificity_mean_then_prune_0.005-n32'),pairs)
        signed={f"{r['method']}-n{r['n']}" for r in menu}
        self.assertTrue(all(set(pair)<=signed for pair in pairs))
        self.assertFalse(any('0.001' in name for pair in pairs for name in pair))
        self.assertEqual(module.component_pairs([{'method':'raw_n1','n':1}]),[])


if __name__=='__main__':unittest.main()
