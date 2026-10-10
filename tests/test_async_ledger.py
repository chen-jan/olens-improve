"""Disposable local-ledger tests, fake responses only; no SDK/network or source edits."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from olens_improve.budget import AtomicBudget, BudgetExceeded, cost_units
from olens_improve.evaluation import BudgetedClient, LedgerOperationError, install_upstream_transport
from olens_improve.performance import OperationalProfile

REQUEST = dict(model='gpt-6-luna', reasoning_effort='none', service_tier='default',
    max_completion_tokens=100, messages=[{'role':'user','content':'offline fixture'}])


def response():
    return SimpleNamespace(id='offline-response', service_tier='default',
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0)))


async def reached(event):
    async def poll():
        while not event.is_set(): await asyncio.sleep(.001)
    await asyncio.wait_for(poll(),2)


class FakeSDK:
    def __init__(self, function=None):
        self.calls=0; self.closes=0; self.function=function
        self.chat=SimpleNamespace(completions=self)
    async def create(self, **request):
        self.calls+=1
        return await self.function() if self.function else response()
    async def close(self): self.closes+=1


class AsyncLedgerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.ledger=AtomicBudget(Path(self.tmp.name)/'ledger.sqlite3',bootstrap_claude=False)
        self.env=patch.dict(os.environ,{'OLENS_ALLOW_PAID_CALLS':'1'},clear=True); self.env.start()
        self.clients=[]
    async def asyncTearDown(self):
        for client in self.clients: await client.close()
        self.env.stop(); self.tmp.cleanup()
    def client(self, inner=None):
        inner=inner or FakeSDK()
        client=BudgetedClient(inner,self.ledger,'offline',allow_paid=True)
        self.clients.append(client)
        return client,inner
    def events(self,kind):
        with sqlite3.connect(self.ledger.path) as db:
            return [json.loads(r[0]) for r in db.execute('SELECT details FROM events WHERE kind=?',(kind,))]

    async def test_slow_reservation_does_not_block_loop_or_dispatch_before_commit(self):
        started=threading.Event(); release=threading.Event(); original=self.ledger.reserve_attempt
        def slow(*a,**k):
            started.set(); release.wait(2)
            return original(*a,**k)
        self.ledger.reserve_attempt=slow
        client,inner=self.client(); task=asyncio.create_task(client.chat.completions.create(**REQUEST))
        await reached(started)
        for _ in range(5): await asyncio.sleep(.005)
        self.assertFalse(task.done()); self.assertEqual(inner.calls,0)
        release.set(); await task
        self.assertEqual(inner.calls,1); self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'settled':1})

    async def test_repeated_cancel_during_reservation_drains_exact_hold_without_dispatch(self):
        started=threading.Event(); release=threading.Event(); original=self.ledger.reserve_attempt
        recorded=[]
        def slow(*a,**k):
            recorded.append(k['attempt_id']); started.set(); release.wait(2)
            return original(*a,**k)
        self.ledger.reserve_attempt=slow
        client,inner=self.client(); task=asyncio.create_task(client.chat.completions.create(**REQUEST))
        await reached(started); task.cancel(); await asyncio.sleep(.005); task.cancel()
        self.assertFalse(task.done()); release.set()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(inner.calls,0); self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'unknown':1})
        with sqlite3.connect(self.ledger.path) as db:
            self.assertEqual(db.execute('SELECT attempt_id FROM attempts').fetchone()[0],recorded[0])
        self.assertGreater(self.ledger.snapshot()['unknown_usd'],0)

    async def test_atomic_run_cap_blocks_dispatch_without_precheck(self):
        self.ledger.set_run_limit('offline','.000000001')
        client,inner=self.client()
        with self.assertRaises(BudgetExceeded): await client.chat.completions.create(**REQUEST)
        self.assertEqual(inner.calls,0); self.assertEqual(self.ledger.snapshot()['attempt_counts'],{})

    async def test_network_cancel_retains_hold_and_transport_evidence_no_retry(self):
        entered=asyncio.Event()
        async def network():
            entered.set(); await asyncio.Event().wait()
        client,inner=self.client(FakeSDK(network))
        task=asyncio.create_task(client.chat.completions.create(**REQUEST)); await entered.wait(); task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(inner.calls,1); self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'unknown':1})
        self.assertEqual(self.events('transport_failure')[0]['exception_type'],'CancelledError')

    async def test_response_cancel_and_close_wait_for_evidence_and_exact_settlement(self):
        started=threading.Event(); release=threading.Event(); original=self.ledger.record_evidence
        def slow(aid,kind,details):
            if kind=='physical_response': started.set(); release.wait(2)
            return original(aid,kind,details)
        self.ledger.record_evidence=slow
        client,inner=self.client(); task=asyncio.create_task(client.chat.completions.create(**REQUEST))
        await reached(started); task.cancel(); await asyncio.sleep(.005); task.cancel()
        closing=asyncio.create_task(client.close()); await asyncio.sleep(.005)
        self.assertFalse(closing.done()); self.assertEqual(inner.closes,0)
        release.set()
        with self.assertRaises(asyncio.CancelledError): await task
        await closing
        snap=self.ledger.snapshot();self.assertEqual(snap['attempt_counts'],{'settled':1})
        self.assertEqual(snap['actual_usd'],cost_units(20,10)/1e9)
        self.assertEqual(len(self.events('physical_response')),1)
        self.assertFalse(client.chat.completions.lane.pending)
        self.assertFalse(hasattr(self.ledger,'_async_ledger_lane'))

    async def test_repeated_cancelled_close_is_coalesced_and_drains_before_sdk_close(self):
        started=threading.Event(); release=threading.Event(); original=self.ledger.settle
        def slow(*a,**k):
            started.set(); release.wait(2)
            return original(*a,**k)
        self.ledger.settle=slow
        client,inner=self.client();request=asyncio.create_task(client.chat.completions.create(**REQUEST))
        await reached(started)
        first=asyncio.create_task(client.close());await asyncio.sleep(.002);first.cancel()
        second=asyncio.create_task(client.close());await asyncio.sleep(.002);first.cancel()
        self.assertFalse(first.done());self.assertFalse(second.done());self.assertEqual(inner.closes,0)
        release.set();await request
        with self.assertRaises(asyncio.CancelledError):await first
        await second
        self.assertEqual(inner.closes,1);self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'settled':1})

    async def test_unknown_write_failure_stops_and_preserves_committed_hold_and_error_evidence(self):
        def failing(*a,**k):raise OSError('offline unknown write failed')
        self.ledger.mark_unknown=failing
        async def network():raise TimeoutError('offline fixture')
        client,inner=self.client(FakeSDK(network))
        with self.assertRaises(LedgerOperationError):await client.chat.completions.create(**REQUEST)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'reserved':1})
        self.assertGreater(self.ledger.snapshot()['reserved_usd'],0)
        self.assertEqual(len(self.events('transport_failure')),1);self.assertEqual(inner.calls,1)

    async def test_reservation_error_after_commit_never_dispatches_or_discards_hold(self):
        original=self.ledger.reserve_attempt
        def failing(*a,**k):
            original(*a,**k)
            raise OSError('offline failure after commit')
        self.ledger.reserve_attempt=failing
        client,inner=self.client()
        with self.assertRaises(LedgerOperationError):await client.chat.completions.create(**REQUEST)
        self.assertEqual(inner.calls,0);self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'reserved':1})
        self.assertGreater(self.ledger.snapshot()['reserved_usd'],0)

    async def test_failed_evidence_still_settles_observed_usage_then_stops(self):
        original=self.ledger.record_evidence
        def failing(aid,kind,details):
            if kind=='physical_response': raise OSError('offline evidence failure')
            return original(aid,kind,details)
        self.ledger.record_evidence=failing
        client,inner=self.client()
        with self.assertRaises(LedgerOperationError): await client.chat.completions.create(**REQUEST)
        self.assertEqual(inner.calls,1); self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'settled':1})
        self.assertEqual(self.ledger.snapshot()['actual_usd'],cost_units(20,10)/1e9)

    async def test_response_serialization_failure_still_settles_observed_usage(self):
        async def received():
            value=response()
            def failing(**k):raise ValueError('offline response serialization failure')
            value.model_dump=failing
            return value
        client,inner=self.client(FakeSDK(received))
        with self.assertRaises(LedgerOperationError):await client.chat.completions.create(**REQUEST)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'settled':1})
        self.assertEqual(self.ledger.snapshot()['actual_usd'],cost_units(20,10)/1e9)
        self.assertEqual(len(self.events('physical_response')),1);self.assertEqual(inner.calls,1)

    async def test_failed_settlement_preserves_response_evidence_and_full_reservation(self):
        def failing(*a,**k): raise OSError('offline settlement failure')
        self.ledger.settle=failing
        client,inner=self.client()
        with self.assertRaises(LedgerOperationError): await client.chat.completions.create(**REQUEST)
        snap=self.ledger.snapshot();self.assertEqual(snap['attempt_counts'],{'reserved':1})
        self.assertGreater(snap['reserved_usd'],0);self.assertEqual(len(self.events('physical_response')),1)
        self.assertEqual(inner.calls,1)

    async def test_missing_usage_retains_hold(self):
        async def missing(): return SimpleNamespace(id='offline-response',usage=None)
        client,inner=self.client(FakeSDK(missing))
        await client.chat.completions.create(**REQUEST)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'unknown':1})
        self.assertEqual(len(self.events('physical_response')),1)

    async def test_clients_share_serialized_lane_and_one_close_keeps_other_client_valid(self):
        active=0; peak=0; lock=threading.Lock(); original=self.ledger.reserve_attempt
        def counted(*a,**k):
            nonlocal active,peak
            with lock: active+=1;peak=max(peak,active)
            try: return original(*a,**k)
            finally:
                with lock:active-=1
        self.ledger.reserve_attempt=counted
        a,_=self.client();b,_=self.client()
        self.assertIs(a.chat.completions.lane,b.chat.completions.lane)
        await asyncio.gather(*(a.chat.completions.create(**REQUEST) for _ in range(4)))
        await a.close();await b.chat.completions.create(**REQUEST)
        self.assertEqual(peak,1);self.assertEqual(self.ledger.snapshot()['attempt_counts'],{'settled':5})

    async def test_upstream_noop_check_cannot_bypass_atomic_reserve(self):
        llm=ModuleType('wsbench.llm');llm.SpendCapError=type('SpendCapError',(RuntimeError,),{})
        llm.JudgeConfigError=type('JudgeConfigError',(RuntimeError,),{})
        wsbench=ModuleType('wsbench');wsbench.llm=llm
        client,inner=self.client();self.ledger.set_run_limit('offline','.000000001')
        with patch.dict('sys.modules',{'wsbench':wsbench,'wsbench.llm':llm}),patch('olens_improve.evaluation.make_luna_client',return_value=client):
            install_upstream_transport(self.ledger,'offline',allow_paid=True,service_tier='default')
            with patch.object(self.ledger,'snapshot',side_effect=AssertionError('Redundant synchronous snapshot')):
                llm._LEDGER.check()
                wrapped=llm._make_client('openai','offline-placeholder')
                with self.assertRaises(llm.SpendCapError): await wrapped.chat.completions.create(**REQUEST)
        self.assertEqual(inner.calls,0)


class ThreadSafeProfileTests(unittest.TestCase):
    def test_concurrent_observation_keeps_exact_counts_and_bounded_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile=OperationalProfile(Path(tmp)/'profile.json',sample_limit=8)
            def observe(_):
                for i in range(100):profile.observe('threaded',.01)
            with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(observe,range(4)))
            metric=profile.close('completed')['metrics']['threaded']
            self.assertEqual(metric['count'],400);self.assertEqual(metric['sample_count'],8)
            self.assertAlmostEqual(metric['total_seconds'],4)

if __name__=='__main__':unittest.main()
