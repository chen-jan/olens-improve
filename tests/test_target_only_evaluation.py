"""Small offline checks of eligibility, immutable source gates and accounting."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import evaluate_target_only_search as target
import analyze_target_only_search as analysis


def save(path, body):
    path.write_text(json.dumps(body))
    return path


def check_budget_reader_preserves_sqlite_bytes_and_outstanding_holds(tmp_path):
    path = tmp_path/'ledger.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE config(key TEXT,value INTEGER); '
            'CREATE TABLE attempts(status TEXT,reserved INTEGER,actual INTEGER);')
        db.executemany('INSERT INTO config VALUES (?,?)', [('hard',340000000000),('target',200000000000),('halted',0)])
        db.executemany('INSERT INTO attempts VALUES (?,?,?)', [('settled',9000000000,7000000000),
            ('reserved',3000000000,None),('unknown',2000000000,None),('released',5000000000,None)])
    before = path.read_bytes()
    report = target.read_only_budget(path)
    assert report['actual_usd'] == 7
    assert report['reserved_usd'] == 5
    assert report['committed_usd'] == 12
    assert report['remaining_hard_usd'] == 328
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('*-journal'))


def check_target_inventory_rejects_control_bank_or_label_access(tmp_path, testcase):
    old = target.load(ROOT/'configs/expansion_manifest_v1.json')
    body = {'status':'sealed','fresh_manifest':old['fresh_manifest'],
        'expected':{'items':469,'cells':19435},'families':list(target.evaluation.FAMILIES),
        'selection_access':{'target_activations_per_cell':1,'other_activations':False,'prompt_access':False,'label_access':False},
        'conditions':[{'condition_id':'repeat_swap-n32','method':'repeat_swap','n':32,
                       'status':'scheduled_full_bank','actual_parent':'pooled_greedy_swap-n32'}]}
    path = save(tmp_path/'inventory.json',body)
    args = SimpleNamespace(inventory=path, inventory_sha256=target.digest(path),api_config=ROOT/'configs/target_only_api_v1.json')
    assert list(target.authority(args)[2]) == ['repeat_swap-n32']
    body['control_bank'] = {'path':'some_other_activation.npy'}
    save(path,body);args.inventory_sha256=target.digest(path)
    with testcase.assertRaisesRegex(ValueError,'control banks'):
        target.authority(args)
    del body['control_bank'];body['selection_access']['label_access']=True
    save(path,body);args.inventory_sha256=target.digest(path)
    with testcase.assertRaisesRegex(ValueError,'one-target'):
        target.authority(args)


def check_dispatch_needs_review_and_unchanged_exact_forecast(tmp_path, testcase):
    config_path = save(tmp_path/'config.json',{'placeholder':'immutable'})
    descriptor = save(tmp_path/'family.ready.json',{'placeholder':'immutable'})
    forecast = save(tmp_path/'forecast.json',{'descriptor_sha256':target.digest(descriptor),
        'api_config_sha256':target.digest(config_path),'inventory_sha256':'a'*64})
    approval = save(tmp_path/'approval.json',{'status':'root_reviewed','approved_for_dispatch':True,
        'inventory_sha256':'a'*64,'api_config_sha256':target.digest(config_path),
        'family_forecasts':{'hallucination':{'path':str(forecast),'sha256':target.digest(forecast)}},
        'run_cap_usd':'30','expected_total_new_charge_usd':1})
    args = SimpleNamespace(allow_paid=False,dispatch_approval=approval,inventory_sha256='a'*64,
        api_config=config_path,family='hallucination',forecast=forecast,descriptor=descriptor)
    with testcase.assertRaisesRegex(ValueError,'explicit flag'):
        target.dispatch_gate(args,{}, {})
    args.allow_paid=True
    forecast.write_text(forecast.read_text()+'\n')
    with testcase.assertRaisesRegex(ValueError,'exact forecast changed'):
        target.dispatch_gate(args,{}, {})


class TargetOnlyEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def test_budget_reader_preserves_bytes_and_holds(self):
        check_budget_reader_preserves_sqlite_bytes_and_outstanding_holds(self.path)

    def test_scientific_eligibility(self):
        check_target_inventory_rejects_control_bank_or_label_access(self.path, self)

    def test_dispatch_source_gate(self):
        with patch.dict(os.environ, {'SLURM_JOB_ID':'test_cpu'}):
            check_dispatch_needs_review_and_unchanged_exact_forecast(self.path, self)

    def test_guided_outputs_need_complete_retained_bullet_evidence(self):
        cell = {'family':'chain_intermediates','item_id':'q1','layer':20,'position':7,
                'split':'test','activation_sha256':'a'*64}
        selection = {'method':'bounded_prune_refill_005','n':32,'text':'- a qualified detail',
                     'token_count':6,'bullet_count':1,'leave_one_out':{'phrase-a':.004}}
        source = self.path/'selections.jsonl'
        row = dict(cell,cell_id='cell1',selections=[selection])
        source.write_text(json.dumps(row)+'\n')
        descriptor = {'selections':str(source)}
        with self.assertRaisesRegex(ValueError,'retained per-bullet'):
            analysis.selections(descriptor, {'bounded_prune_refill_005-n32'}, {'cell1':cell})

        selection['leave_one_out'] = {'phrase-a':.005}
        source.write_text(json.dumps(row)+'\n')
        with self.assertRaisesRegex(ValueError,'retained per-bullet'):
            analysis.selections(descriptor, {'bounded_prune_refill_005-n32'}, {'cell1':cell})

        selection['leave_one_out'] = {'phrase-a':.005+2e-8}
        source.write_text(json.dumps(row)+'\n')
        accepted = analysis.selections(descriptor, {'bounded_prune_refill_005-n32'}, {'cell1':cell})
        self.assertEqual(accepted['bounded_prune_refill_005-n32']['cell1']['leave_one_out'],{'phrase-a':.005+2e-8})
        selection['bullet_count']=2
        source.write_text(json.dumps(row)+'\n')
        with self.assertRaisesRegex(ValueError,'retained per-bullet'):
            analysis.selections(descriptor, {'bounded_prune_refill_005-n32'}, {'cell1':cell})

    def test_terminal_judge_cannot_hide_missing_hallucination_second_stage(self):
        manifest = save(self.path/'manifest.json', {'cells':[{'item_id':'q1','layer':20,'position':4}]})
        (self.path/'hallucination').mkdir()
        readout = {'id':'q1','layer':20,'pos':4,'samples':['- A concrete assertion.']}
        (self.path/'hallucination.readouts.jsonl').write_text(json.dumps(readout)+'\n')
        result = {'rows':[dict(readout,verdict=[{'idx':0,'class':'consistent','claims':None}])]}
        save(self.path/'hallucination'/'results.json',result)
        coverage = target.terminal_coverage(self.path,'hallucination',{'manifest':str(manifest)})
        self.assertEqual(coverage['missing_stage1'],0)
        self.assertEqual(coverage['missing_stage2'],1)

    def test_disputed_secondary_preserves_native_endpoint_and_overlapping_tallies(self):
        cells = [{'item_id':'q1','layer':layer,'position':4} for layer in (20,36)]
        reads = [dict(id='q1',layer=c['layer'],pos=4,samples=['- A concrete assertion.']) for c in cells]
        tallies = [{'false':1,'true':2,'unverifiable':3,'disputed':2},
                   {'false':0,'true':1,'unverifiable':2,'disputed':1}]
        result = {'rows':[dict(r,verdict=[{'idx':0,'class':kind,'claims':claims}])
                          for r,kind,claims in zip(reads,('hallucinated','consistent'),tallies)],
                  'numbers':{'metric':'hallucination_rate','value':.5}}
        metrics, coverage = analysis.family_counts('hallucination',cells,reads,result)
        native = dict(metrics['contradiction_rate'])
        analysis.add_hallucination_diagnostics(metrics,result)
        self.assertEqual(metrics['contradiction_rate'],native)
        self.assertEqual(metrics['disputed_claim_tally'],{'q1':(3,2)})
        self.assertEqual(metrics['unverifiable_claims_per_output'],{'q1':(5,2)})
        self.assertEqual(metrics['false_span_tally'],{'q1':(1,2)})
        analysis.original_grid_pairs('hallucination',metrics,result)
        self.assertEqual(coverage['missing_stage2'],0)
        result['rows'][0]['verdict'][0]['claims']['disputed'] = 4
        with self.assertRaisesRegex(ValueError,'disputed subset'):
            analysis.add_hallucination_diagnostics(metrics,result)


if __name__ == '__main__':
    unittest.main()
