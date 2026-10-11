import json,sqlite3,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import export_expansion_effort as e


class EffortExport(unittest.TestCase):
    def test_standalone_likelihood_does_not_require_the_reconstructor(self):
        row={'condition_id':'own_mean_log_likelihood-n8','method':'own_mean_log_likelihood','n':8,
             'new_olens_samples':0,'parent_condition_ids':['capped_n1-n1']}
        result=e.effort_definition(row,(5,8))
        self.assertFalse(result['original_bullet_ar_encoding_required'])
        self.assertEqual(result['likelihood_contexts_per_candidate_if_run_alone'],1)
        self.assertFalse(any('least-squares' in c for c in result['recurring_components']))

    def test_judge_invocation_summaries_preserve_resume_scope_and_ignore_unfinished_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'expansion-judge-chain_intermediates-v1.log').write_text('judge: 12 calls (90 cached, model=gpt-6-luna)\npartial phase without summary\n')
            (p/'expansion-judge-chain_intermediates-recovery-v1.log').write_text('judge: 0 calls (102 cached, model=gpt-6-luna)\n')
            sources=e.Sources();result=e.observed_judge_counters(sources,p)
            self.assertEqual(result['observed_logical_invocations'],204)
            self.assertEqual(result['observed_validated_cache_returns'],192)
            self.assertIn('Not unique',result['scope'])
            self.assertEqual(len(sources.rows),2)

    def test_physical_usage_is_partitioned_without_double_charging_shared_helpers(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger.sqlite3';q=sqlite3.connect(p)
            q.executescript('''CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY,run_id TEXT,status TEXT,reserved INTEGER,actual INTEGER,metadata TEXT,created_utc TEXT,updated_utc TEXT);
              CREATE TABLE events(sequence INTEGER PRIMARY KEY,attempt_id TEXT,kind TEXT,details TEXT);
              CREATE TABLE config(key TEXT,value INTEGER);
              CREATE INDEX attempts_global_committed ON attempts(status,actual,reserved);
              CREATE INDEX attempts_run_committed ON attempts(run_id,status,actual,reserved);
              CREATE INDEX attempts_run_recovery ON attempts(run_id,created_utc DESC,status,reserved);
              CREATE INDEX events_attempt_kind_sequence ON events(attempt_id,kind,sequence DESC);''')
            q.executemany('INSERT INTO config VALUES (?,?)',[('hard',340000000000),('target',200000000000)])
            for i,purpose in enumerate(['candidate-only-helper-effort-diagnostic','workspacebench-judge','workspacebench-judge']):
                q.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)',(str(i),'run','unknown' if i==2 else 'settled',9,5 if i<2 else None,json.dumps({'purpose':purpose,'request':{'reasoning_effort':'none'}}),'2020-01-01T00:00:00+00:00','2020-01-01T00:00:01+00:00'))
                usage={'input_tokens':10,'output_tokens':2,'cached_tokens':3,'cache_write_tokens':7,'response_id':str(i)}
                if i<2:q.execute('INSERT INTO events VALUES (?,?,?,?)',(i,str(i),'settled',json.dumps(usage)))
                else:q.execute('INSERT INTO events VALUES (?,?,?,?)',(i,str(i),'transport_failure',json.dumps({'exception_type':'APIConnectionError','cause_chain':[{'class':'RemoteProtocolError'}]})))
            q.commit();q.close();key='editing_round1/chain_intermediates';families={key:{'phase':'editing_round1',**e.empty_usage()}}
            out=e.ledger_audit(p,'run',{'0':(key,'editor',True)},families,batch=1)
            self.assertEqual(out['settled_record_count'],2)
            self.assertEqual(out['buckets']['editing_round1']['physical_settled_attempts'],1)
            self.assertEqual(out['buckets']['experimental_benchmark_judging']['actual_usage_estimate_usd'],5e-9)
            self.assertEqual(families[key]['cached_input_tokens'],3)
            self.assertEqual(out['unknown_holds'][0]['reserved_usd'],9e-9)
            with sqlite3.connect(p) as q:self.assertEqual(q.execute("SELECT status FROM attempts WHERE attempt_id='2'").fetchone()[0],'unknown')

    def test_append_only_source_prefix_is_exact_and_incomplete_line_is_not_a_request(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'log.jsonl';p.write_bytes(b'{"a":1}\n{"a":2}\n{"a":')
            sources=e.Sources();self.assertEqual(list(sources.lines(p)),[{'a':1},{'a':2}])
            r=sources.rows[str(p)];self.assertTrue(r['incomplete_last_record']);self.assertEqual(r['bytes'],p.stat().st_size)
            self.assertEqual(r['sha256'],e.sha256(p.read_bytes()).hexdigest())

    def test_shared_semantic_variant_dependencies_do_not_become_unique_prices(self):
        inventory=json.loads((ROOT/'configs/expansion_manifest_v1.json').read_text())
        row=next(r for r in inventory['conditions'] if r['condition_id']=='consensus_semantic_v5_medium_support0.125_compaton_vetoon-n16')
        out=e.effort_definition(row,(5,8))
        self.assertIsNone(out['allocated_unique_method_api_usd']);self.assertEqual(out['original_pool_n'],16)
        self.assertEqual(out['new_input_helper_recipe'],['source_pair_proposal','medium_confirmation_on_frozen_pairs'])
        self.assertFalse(out['benchmark_judging_is_deployment_inference'])


if __name__=='__main__':unittest.main()
