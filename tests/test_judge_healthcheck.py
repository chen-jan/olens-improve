"""Bounded health dispatch checks with fake transport; no network or secrets."""
import asyncio
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget
from olens_improve.evaluation import BudgetedClient, request_cache_key
from scripts.judge_healthcheck import check


class HealthcheckTests(unittest.TestCase):
    def test_one_exact_call_closes_client_and_preserves_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = AtomicBudget(root/'ledger.sqlite3')
            request = {'model':'gpt-6-luna','reasoning_effort':'none','service_tier':'default',
                'messages':[{'role':'user','content':'offline fixture'}], 'max_completion_tokens':50}
            aid = ledger.reserve_attempt(100,50,run_id='fixture',metadata={
                'request':request,'content_cache_key':request_cache_key(request)})
            ledger.mark_unknown(aid,'offline fixture')
            calls=[]
            closed=[]
            async def create(**kwargs):
                calls.append(kwargs)
                dump=lambda **kwargs:{'input_tokens':3,'output_tokens':2}
                return SimpleNamespace(id='fixture-response',usage=SimpleNamespace(model_dump=dump),model_dump=dump)
            async def close():closed.append(True)
            client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),close=close)
            args=SimpleNamespace(allow_paid=True,ledger=root/'ledger.sqlite3',run_id='fixture',
                run_cap_usd='20',attempt_id=aid,output=root/'health.json')
            with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-fixture'},clear=True), \
                    patch('scripts.judge_healthcheck.make_luna_client',return_value=client):
                result=asyncio.run(check(args))
                self.assertEqual(result['status'],'success')
                self.assertEqual(calls,[request|{'timeout':90}])
                self.assertEqual(closed,[True])
                self.assertEqual(ledger.snapshot()['attempt_counts']['unknown'],2)
                with self.assertRaises(ValueError):asyncio.run(check(args))
                self.assertEqual(len(calls),1)

    def test_probe_rejects_an_active_recovery_epoch_before_dispatch(self):
        args=SimpleNamespace(allow_paid=True)
        with patch.dict(os.environ,{'OLENS_TRANSPORT_RECOVERY_SINCE':'frozen'},clear=True), \
                patch('scripts.judge_healthcheck.make_luna_client') as factory:
            with self.assertRaises(ValueError):asyncio.run(check(args))
            factory.assert_not_called()

    def guarded_fixture(self, root, epoch='2000-01-01T00:00:00+00:00'):
        ledger=AtomicBudget(root/'ledger.sqlite3')
        request={'model':'gpt-6-luna','reasoning_effort':'none','service_tier':'default',
            'messages':[{'role':'user','content':'offline guarded fixture'}], 'max_completion_tokens':50}
        aid=ledger.reserve_attempt(100,50,run_id='fixture',metadata={
            'request':request,'content_cache_key':request_cache_key(request)},
            dispatch_guard={'since_utc':epoch})
        ledger.mark_unknown(aid,'offline fixture')
        args=SimpleNamespace(allow_paid=True,ledger=ledger.path,run_id='fixture',run_cap_usd='20',
            attempt_id=aid,output=root/'health.json',preserve_recovery_guard=True,
            performance_profile=root/'profile.json')
        return ledger,request,args

    def guarded_factory(self, calls, closed):
        async def create(**request):
            calls.append(request)
            dump={'id':'offline-response','service_tier':'default','usage':{
                'prompt_tokens':3,'completion_tokens':2,
                'prompt_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}}}
            usage=SimpleNamespace(**dump['usage'],model_dump=lambda **kwargs:dump['usage'])
            return SimpleNamespace(id=dump['id'],service_tier='default',usage=usage,
                                   model_dump=lambda **kwargs:dump)
        async def close():closed.append(True)
        inner=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),close=close)
        def factory(ledger,run_id,**kwargs):
            return BudgetedClient(inner,ledger,run_id,allow_paid=kwargs['allow_paid'],metadata=kwargs.get('metadata'))
        return factory

    def test_guarded_canary_preserves_exact_epoch_and_hold_then_drains_one_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ledger,request,args=self.guarded_fixture(root);calls=[];closed=[]
            epoch='2000-01-01T00:00:00+00:00'
            with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-fixture',
                    'OLENS_TRANSPORT_RECOVERY_SINCE':epoch},clear=True), \
                    patch('scripts.judge_healthcheck.make_luna_client',self.guarded_factory(calls,closed)):
                result=asyncio.run(check(args))
            self.assertEqual(result['status'],'success')
            self.assertEqual(calls,[request|{'timeout':90}])
            self.assertEqual(closed,[True])
            self.assertTrue(result['transport_guard_preserved'])
            self.assertEqual(result['recovery_epoch'],epoch)
            self.assertFalse(result['review_after_drain']['flagged'])
            self.assertEqual(json.loads(args.performance_profile.read_text())['status'],'success')
            self.assertEqual(ledger.snapshot()['attempt_counts'],{'settled':1,'unknown':2})
            with sqlite3.connect(ledger.path) as db:
                metadata=json.loads(db.execute("SELECT metadata FROM attempts WHERE run_id='fixture' AND status='settled'").fetchone()[0])
                original=db.execute('SELECT status,reserved FROM attempts WHERE attempt_id=?',(args.attempt_id,)).fetchone()
            self.assertEqual(metadata['transport_recovery_guard'],{'since_utc':epoch})
            self.assertEqual(original[0],'unknown')
            self.assertGreater(original[1],0)

    def test_guarded_canary_rejects_changed_source_epoch_before_client(self):
        with tempfile.TemporaryDirectory() as directory:
            _,_,args=self.guarded_fixture(Path(directory))
            with patch.dict(os.environ,{'OLENS_TRANSPORT_RECOVERY_SINCE':'2001-01-01T00:00:00+00:00'},clear=True), \
                    patch('scripts.judge_healthcheck.make_luna_client') as factory:
                with self.assertRaisesRegex(ValueError,'exact replay source recovery epoch'):
                    asyncio.run(check(args))
                factory.assert_not_called()

    def test_opt_in_phases_capture_real_worker_guard_queries_and_commit_then_restore_connect(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ledger,request,args=self.guarded_fixture(root);calls=[];closed=[]
            args.transaction_phase_profile=root/'sql-phases.json'
            original_connect=sqlite3.connect
            with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-fixture',
                    'OLENS_TRANSPORT_RECOVERY_SINCE':'2000-01-01T00:00:00+00:00'},clear=True), \
                    patch('scripts.judge_healthcheck.make_luna_client',self.guarded_factory(calls,closed)):
                result=asyncio.run(check(args))
            self.assertIs(sqlite3.connect,original_connect)
            self.assertEqual(calls,[request|{'timeout':90}])
            self.assertEqual(closed,[True])
            phase=json.loads(args.transaction_phase_profile.read_text())
            self.assertEqual(phase['status'],'success')
            self.assertEqual(phase['context']['reserve_thread'],'worker')
            self.assertGreater(phase['context']['reservation_metadata_json_utf8_bytes_before_budget_fields'],0)
            observed={(r['phase'],r['component']) for r in phase['records'] if r['operation']=='reserve_attempt'}
            self.assertTrue({('begin','execute'),('commit','execute'),('body.guard.recent','fetchall'),
                ('body.guard.unknown_sum','fetchone'),('body.committed.global','fetchone')}<=observed)
            self.assertEqual(result['transaction_phase_profile'],str(args.transaction_phase_profile))
            self.assertEqual(ledger.snapshot()['attempt_counts'],{'settled':1,'unknown':2})

    def test_phase_capture_requires_existing_guard_and_fresh_profile_before_client(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);_,_,args=self.guarded_fixture(root)
            args.transaction_phase_profile=root/'sql-phases.json'
            args.transaction_phase_profile.write_text('preserve this evidence')
            with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-fixture',
                    'OLENS_TRANSPORT_RECOVERY_SINCE':'2000-01-01T00:00:00+00:00'},clear=True), \
                    patch('scripts.judge_healthcheck.make_luna_client') as factory:
                with self.assertRaisesRegex(ValueError,'phase evidence already exists'):
                    asyncio.run(check(args))
                factory.assert_not_called()
            args.transaction_phase_profile.unlink();args.preserve_recovery_guard=False
            with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-fixture'},clear=True), \
                    patch('scripts.judge_healthcheck.make_luna_client') as factory:
                with self.assertRaisesRegex(ValueError,'requires guarded canary'):
                    asyncio.run(check(args))
                factory.assert_not_called()

    def test_guarded_canary_is_stopped_by_existing_atomic_transport_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ledger,_,args=self.guarded_fixture(root);calls=[];closed=[]
            args.transaction_phase_profile=root/'sql-phases.json'
            for _ in range(5):
                aid=ledger.reserve_attempt(100,50,run_id='fixture')
                ledger.mark_unknown(aid,'offline fixture')
            with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-fixture',
                    'OLENS_TRANSPORT_RECOVERY_SINCE':'2000-01-01T00:00:00+00:00'},clear=True), \
                    patch('scripts.judge_healthcheck.make_luna_client',self.guarded_factory(calls,closed)):
                result=asyncio.run(check(args))
            self.assertEqual(result['status'],'failed')
            self.assertEqual(calls,[])
            self.assertEqual(closed,[True])
            self.assertTrue(result['review_after_drain']['flagged'])
            self.assertEqual(ledger.snapshot()['attempt_counts'],{'unknown':7})
            self.assertEqual(json.loads(args.transaction_phase_profile.read_text())['status'],'failed')


if __name__ == '__main__':unittest.main()
