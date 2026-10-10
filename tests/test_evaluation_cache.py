"""Offline paid-request reuse checks; no credentials, SDK, or benchmark imports."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget
from olens_improve.evaluation import install_shared_verdict_cache


class MemoryCache:
    def __init__(self):self.rows=[]
    def put(self,key,fp,payload):self.rows.append((key,fp,payload))


class ExactVerdictCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        self.ledger=AtomicBudget(self.path/'budget.sqlite3',bootstrap_claude=False)
        self.dispatches=[]
        def fingerprint(*parts):
            return hashlib.sha256(json.dumps(parts,sort_keys=True).encode()).hexdigest()
        self.fingerprint=fingerprint
        def original(calls,**kw):
            out={}
            for call in calls:
                fp=fingerprint(kw['prompt_version'],kw['judge'].model,kw['judge'].reasoning,
                    kw.get('temperature'),call.system,call.user)
                cached=kw['cache'].get(call.key,fp)
                if cached:out[call.key]=cached['result'];continue
                self.dispatches.append(call.key)
                result={'answer':'fixture'}
                if kw.get('validate') and not kw['validate'](call,result):result=None
                kw['cache'].put(call.key,fp,{'result':result,'meta':call.meta});out[call.key]=result
            return out
        package=ModuleType('wsbench')
        package.llm=SimpleNamespace(_DEFAULT_MAX_TOKENS={'openai':6000},_TEMP_OK={},openai_effort=lambda r:'none')
        package.mcjudge=SimpleNamespace()
        cache_module=ModuleType('wsbench.cache');cache_module.fingerprint=fingerprint
        self.family_module=ModuleType('wsbench.evals.role_bound_association.judge')
        self.family_module.run_calls=original
        self.modules=patch.dict(sys.modules,{'wsbench':package,'wsbench.cache':cache_module,
            'wsbench.evals.role_bound_association.judge':self.family_module})
        self.modules.start()
        self.provenance=patch('olens_improve.evaluation.load_upstream',return_value={'runtime_source_hashes':{'judge.py':'fixture-hash'}})
        self.provenance.start()
        install_shared_verdict_cache(self.path/'cache.sqlite3',self.ledger,'role_bound_association')
        self.kwargs={'schema':{'name':'fixture-v1'},'judge':SimpleNamespace(model='gpt-6-luna',reasoning={'effort':'none'}),
            'prompt_version':'fixture-v1','cache':MemoryCache(),'dry_run':False}
    def tearDown(self):
        self.provenance.stop();self.modules.stop();self.tmp.cleanup()
    def call(self,key,text='same text'):
        return SimpleNamespace(key=key,system='same system',user=text,meta={'source':key})
    def test_duplicate_batch_and_cross_cell_reuse(self):
        first=self.family_module.run_calls([self.call('a'),self.call('b')],**self.kwargs)
        self.assertEqual(first,{'a':{'answer':'fixture'},'b':{'answer':'fixture'}})
        self.assertEqual(self.dispatches,['a'])
        again=self.family_module.run_calls([self.call('c')],**self.kwargs)
        self.assertEqual(again['c'],first['a']);self.assertEqual(self.dispatches,['a'])
        hit=self.kwargs['cache'].rows[-1][2]['shared_cache_hit']
        self.assertEqual(hit['origin']['original_cell_key'],'a')
        self.assertEqual(hit['request_key'],hit['origin']['request_key'])
        self.assertEqual(self.ledger.snapshot()['actual_usd'],0)
    def test_schema_and_output_cap_invalidate(self):
        self.family_module.run_calls([self.call('a')],**self.kwargs)
        changed={**self.kwargs,'schema':{'name':'fixture-v2'}}
        self.family_module.run_calls([self.call('b')],**changed)
        changed={**self.kwargs,'max_tokens':7000}
        self.family_module.run_calls([self.call('c')],**changed)
        self.assertEqual(self.dispatches,['a','b','c'])
    def test_validator_rechecks_shared_hits(self):
        state={'valid':True}
        def validate(call,result):return state['valid']
        kwargs={**self.kwargs,'validate':validate}
        self.family_module.run_calls([self.call('a')],**kwargs)
        state['valid']=False
        result=self.family_module.run_calls([self.call('b')],**kwargs)
        self.assertIsNone(result['b']);self.assertEqual(self.dispatches,['a','b'])
    def test_content_and_source_contract_invalidate(self):
        self.family_module.run_calls([self.call('a')],**self.kwargs)
        self.family_module.run_calls([self.call('b','different text')],**self.kwargs)
        with patch('olens_improve.evaluation.load_upstream',return_value={'runtime_source_hashes':{'judge.py':'new-hash'}}):
            install_shared_verdict_cache(self.path/'cache.sqlite3',self.ledger,'role_bound_association')
            self.family_module.run_calls([self.call('c')],**self.kwargs)
        self.assertEqual(self.dispatches,['a','b','c'])


if __name__=='__main__':unittest.main()
