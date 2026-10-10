"""Released-family forecasts use synthetic sources/caches, never a live ledger."""
from contextlib import closing, redirect_stdout
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


spec=importlib.util.spec_from_file_location('forecast_family_fixture',Path('scripts/forecast_judging.py'))
forecast=importlib.util.module_from_spec(spec);spec.loader.exec_module(forecast)


class ForecastFamilyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.contract={'synthetic_upstream':'unchanged'}
        self.conditions=[{'method':'fixture','n':1}]
        self.cells=[{'cell_id':f'{family}-cell','family':family,'item_id':item,'layer':20,
            'position':4,'split':'development'} for family,item in
            [('hallucination','h'),('role_bound_association','r'),('chain_intermediates','c'),('multihop_mt','m')]]
        self.rows=[cell|{'selections':[{'method':'fixture','n':1,'text':'- synthetic claim'}]} for cell in self.cells]
        self.manifest=self.root/'manifest.json';self.manifest.write_text(json.dumps({'partial_grid':True,'cells':self.cells}))
        self.selection=self.root/'selections.jsonl';self.write_rows()
        self.menu=self.root/'conditions.json';self.menu.write_text(json.dumps(self.conditions))
        self.cache=self.root/'cache';self.cache.mkdir()
        for family in ('hallucination','role_bound_association','chain_intermediates'):
            with closing(sqlite3.connect(self.cache/f'{family}.sqlite3')) as db:
                db.execute('CREATE TABLE verdicts(content_key TEXT PRIMARY KEY,body TEXT NOT NULL)');db.commit()
        self.reference=self.root/'empirical.json'
        self.reference.write_text(json.dumps({'source_contract':self.contract,'output_cap':6000,
            'empirical_standard_response_measurements':{stage:{'mean_actual_usd':.001,'mean_latency_s':1,'p95_latency_s':3}
                for stage in ('hall_stage1','hall_stage2_known','role','chain')}}))
        self.cache_opens=[]
        original_connect=sqlite3.connect
        def connect(path,*args,**kwargs):
            self.cache_opens.append(str(path))
            self.assertIn(str(self.cache),str(path),'A non-family-cache database was opened')
            return original_connect(path,*args,**kwargs)
        package=ModuleType('wsbench');package.__path__=[]
        package.llm=SimpleNamespace(_DEFAULT_MAX_TOKENS={'openai':6000})
        mcjudge=ModuleType('wsbench.mcjudge')
        mcjudge.load_bank=lambda family: {'items':[{'id':'h','sites':[{'pos':4}]}]} if family=='hallucination' else [{'id':'r'}]
        hall=SimpleNamespace(JUDGE_SCHEMA={'name':'hall'},VERIFY_SCHEMA={'name':'verify'},
            PROMPT_VERSION='hall-v1',VERIFY_PROMPT_VERSION='verify-v1')
        prompts=SimpleNamespace(judge_prompt=lambda *args:('system','user'),verify_prompt=lambda *args:('verify','user'))
        role=SimpleNamespace(SYSTEM='role system',SCHEMA={'name':'role'},PROMPT_VERSION='role-v1',
            build_block=lambda *args:('block',None),prompts=SimpleNamespace(render_user=lambda *args:'role user'))
        chain=SimpleNamespace(BANK='fake',SYSTEM='chain system',SCHEMA={'name':'chain'},PROMPT_VERSION='chain-v1',
            load_bank=lambda bank:('ignored',[{'id':'c'}]),render_user=lambda text:'chain user')
        mapping={'wsbench.evals.hallucination.judge':hall,'wsbench.evals.hallucination.prompts':prompts,
            'wsbench.evals.role_bound_association.judge':role,'wsbench.evals.chain_intermediates.judge':chain}
        self.patches=[patch.dict(sys.modules,{'wsbench':package,'wsbench.mcjudge':mcjudge}),
            patch.object(forecast,'load_upstream',return_value={'runtime_source_hashes':self.contract}),
            patch.object(forecast.importlib,'import_module',side_effect=lambda name:mapping[name]),
            patch.object(forecast,'source_validator',return_value=(lambda call,result:True,'synthetic validator')),
            patch.object(forecast.sqlite3,'connect',side_effect=connect)]
        for replacement in self.patches:replacement.start()

    def tearDown(self):
        for replacement in reversed(self.patches):replacement.stop()
        self.temp.cleanup()

    def write_rows(self):
        self.selection.write_text(''.join(json.dumps(row)+'\n' for row in self.rows))

    def args(self,family=None):
        return SimpleNamespace(manifest=self.manifest,fresh_manifest=None,gate=None,
            selections=[self.selection],conditions=[self.menu],cache=self.cache,
            ledger=self.root/'LIVE-LEDGER-MUST-NOT-OPEN.sqlite3',empirical_summary=self.reference,
            empirical_since='2026-10-10T07:52:00+00:00',concurrency=8,rpm=200,
            family=family,output=self.root/f'{family or "default"}-forecast.json')

    def run_forecast(self,args):
        with redirect_stdout(io.StringIO()):forecast.run(args)
        return json.loads(args.output.read_text())

    def test_default_preserves_full_cohort_counts_and_three_caches(self):
        result=self.run_forecast(self.args())
        self.assertNotIn('forecast_scope',result)
        self.assertEqual(result['source_contract'],self.contract)
        self.assertEqual(result['logical_rows'],{family:1 for family in ('hallucination','role_bound_association','chain_intermediates','multihop_mt')})
        self.assertEqual(len(self.cache_opens),3)
        self.assertEqual(result['unknown_hall_stage2_unique_requests_upper'],1)

    def test_family_opens_only_released_cache_and_preserves_request_counts(self):
        baseline=self.run_forecast(self.args());self.cache_opens.clear()
        result=self.run_forecast(self.args('role_bound_association'))
        self.assertEqual(self.cache_opens,['file:'+str(self.cache/'role_bound_association.sqlite3')+'?mode=ro'])
        self.assertEqual(result['logical_rows'],{'role_bound_association':1})
        self.assertEqual(result['exact_cached_request_counts'],{'role':baseline['exact_cached_request_counts']['role']})
        self.assertEqual(result['unknown_hall_stage2_unique_requests_upper'],0)
        self.assertEqual(result['forecast_scope']['validated_full_manifest_cells'],4)
        self.assertEqual(result['forecast_scope']['forecast_cells'],1)
        self.assertFalse(result['forecast_scope']['active_ledger_access'])
        self.assertEqual(result['source_contract'],baseline['source_contract'])
        self.assertEqual(result['selection_sources'][0]['sha256'],sha256(self.selection.read_bytes()).hexdigest())

    def test_family_keeps_both_hall_stages_and_only_hall_cache(self):
        result=self.run_forecast(self.args('hallucination'))
        self.assertEqual(len(self.cache_opens),1)
        self.assertIn('hallucination.sqlite3',self.cache_opens[0])
        self.assertEqual(result['logical_rows'],{'hallucination':1})
        self.assertEqual(result['unknown_hall_stage2_unique_requests_upper'],1)

    def test_foreign_family_missing_condition_or_identity_rejected_before_cache(self):
        for mode in ('missing','duplicate','identity','coverage'):
            with self.subTest(mode=mode):
                saved=json.loads(json.dumps(self.rows))
                if mode=='missing':self.rows[0]['selections']=[]
                elif mode=='duplicate':self.rows[0]['selections']*=2
                elif mode=='identity':self.rows[0]['layer']=44
                else:self.rows.pop(0)
                self.write_rows()
                with self.assertRaises(ValueError):self.run_forecast(self.args('role_bound_association'))
                self.assertEqual(self.cache_opens,[])
                self.rows=saved;self.write_rows()

    def test_family_rejects_heldout_before_text_banks_and_cache(self):
        for stage in ('validation','test'):
            with self.subTest(stage=stage),patch.object(forecast,'evaluation_stage',return_value=({},stage,{},{})), \
                 patch.object(forecast,'selection_rows') as rows,patch.object(forecast,'load_upstream') as banks:
                with self.assertRaisesRegex(ValueError,'restricted to development'):
                    forecast.run(self.args('role_bound_association'))
                rows.assert_not_called();banks.assert_not_called()
        self.assertEqual(self.cache_opens,[])

    def test_family_requires_frozen_empirical_reference_before_source_access(self):
        args=self.args('role_bound_association');args.empirical_summary=None
        with patch.object(forecast,'load_upstream') as banks,patch.object(forecast,'selection_rows') as rows:
            with self.assertRaisesRegex(ValueError,'frozen empirical summary'):forecast.run(args)
            banks.assert_not_called();rows.assert_not_called()
        self.assertEqual(self.cache_opens,[])


if __name__=='__main__':unittest.main()
