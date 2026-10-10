"""Offline financial-side-effect checks; no SDK, credentials, or API calls."""
import multiprocessing
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from olens_improve.budget import AtomicBudget, BudgetExceeded, cost_units
from olens_improve.evaluation import BudgetedCompletions, request_cache_key


def _race(path, queue):
    ledger = AtomicBudget(path, hard_usd='0.01', target_usd='0.01', bootstrap_claude=False)
    try:
        ledger.reserve_attempt(1, 12000, run_id='race')
        queue.put('reserved')
    except BudgetExceeded:
        queue.put('blocked')


class BudgetTests(unittest.TestCase):
    def test_shared_transport_guard_ignores_old_epoch_and_blocks_new_unknowns(self):
        ledger = AtomicBudget(self.path, bootstrap_claude=False)
        old = ledger.reserve_attempt(1, 1, run_id='recovery')
        ledger.mark_unknown(old, 'old outage')
        from datetime import datetime, timezone
        guard = {'since_utc': datetime.now(timezone.utc).isoformat()}
        for _ in range(6):
            aid = ledger.reserve_attempt(1, 1, run_id='recovery', dispatch_guard=guard)
            ledger.mark_unknown(aid, 'transport')
        with self.assertRaises(BudgetExceeded):
            ledger.reserve_attempt(1, 1, run_id='recovery', dispatch_guard=guard)
        other = ledger.reserve_attempt(1, 1, run_id='independent', dispatch_guard=guard)
        self.assertIsInstance(other, str)

    def test_transport_guard_blocks_large_unknown_before_next_paid_attempt(self):
        ledger = AtomicBudget(self.path, bootstrap_claude=False)
        guard = {'since_utc': '2000-01-01T00:00:00+00:00'}
        aid = ledger.reserve_attempt(1, 210000, run_id='recovery', dispatch_guard=guard)
        ledger.mark_unknown(aid, 'uncertain')
        with self.assertRaises(BudgetExceeded):
            ledger.reserve_attempt(1, 1, run_id='recovery', dispatch_guard=guard)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'ledger.sqlite3'

    def tearDown(self):
        self.temp.cleanup()

    def test_two_process_reservation_cannot_oversubscribe(self):
        AtomicBudget(self.path, hard_usd='0.01', target_usd='0.01', bootstrap_claude=False)
        ctx = multiprocessing.get_context('spawn')
        queue = ctx.Queue()
        children = [ctx.Process(target=_race, args=(str(self.path), queue)) for _ in range(2)]
        for child in children: child.start()
        answers = [queue.get(timeout=15) for _ in children]
        for child in children:
            child.join(15)
            self.assertEqual(child.exitcode, 0)
        self.assertEqual(sorted(answers), ['blocked', 'reserved'])

    def test_timeout_reservation_remains_until_evidence(self):
        ledger = AtomicBudget(self.path, hard_usd='0.01', target_usd='0.01', bootstrap_claude=False)
        aid = ledger.reserve_attempt(100, 10000, run_id='timeout')
        before = ledger.snapshot()['committed_usd']
        ledger.mark_unknown(aid, 'HTTP timeout; charge unknown')
        self.assertEqual(ledger.snapshot()['committed_usd'], before)
        with self.assertRaises(BudgetExceeded): ledger.reserve_attempt(100, 10000, run_id='timeout')
        with self.assertRaises(ValueError): ledger.release_uncharged(aid, evidence='')
        ledger.release_uncharged(aid, evidence='Provider reconciliation confirms zero billed usage for request ID')
        self.assertEqual(ledger.snapshot()['committed_usd'], 0)

    def test_malformed_but_billed_response_settles(self):
        ledger = AtomicBudget(self.path, bootstrap_claude=False)
        aid = ledger.reserve_attempt(10000, 8000, run_id='malformed')
        ledger.settle(aid, input_tokens=1000, cached_tokens=500, output_tokens=800, billed_tier='flex')
        expected = cost_units(1000, 800, 500, 'flex') / 1e9
        self.assertEqual(ledger.snapshot()['actual_usd'], expected)
        self.assertEqual(ledger.snapshot()['reserved_usd'], 0)
        ledger.settle(aid, input_tokens=1000, cached_tokens=500, output_tokens=800, billed_tier='flex')
        self.assertEqual(ledger.snapshot()['actual_usd'], expected)

    def test_bootstrap_and_frozen_caps(self):
        first = AtomicBudget(self.path)
        second = AtomicBudget(self.path)
        self.assertEqual(first.snapshot()['unknown_usd'], 2)
        self.assertEqual(second.snapshot()['attempt_counts'], {'unknown': 1})
        with self.assertRaises(ValueError): AtomicBudget(self.path, hard_usd='301')

    def test_run_cap_covers_retries(self):
        ledger = AtomicBudget(self.path, bootstrap_claude=False)
        ledger.set_run_limit('tiny', '.006')
        aid = ledger.reserve_attempt(100, 10000, run_id='tiny')
        ledger.mark_unknown(aid, 'first physical attempt timed out')
        with self.assertRaises(BudgetExceeded): ledger.reserve_attempt(100, 10000, run_id='tiny')

    def test_excess_actual_usage_is_recorded_then_stops(self):
        ledger = AtomicBudget(self.path, bootstrap_claude=False)
        aid = ledger.reserve_attempt(1, 1, run_id='bad-bound')
        with self.assertRaises(BudgetExceeded): ledger.settle(aid, input_tokens=100, output_tokens=100)
        self.assertGreater(ledger.snapshot()['actual_usd'], 0)
        self.assertTrue(AtomicBudget(self.path, bootstrap_claude=False).snapshot()['halted'])
        with self.assertRaises(BudgetExceeded): ledger.reserve_attempt(1, 1, run_id='other-process')
        with self.assertRaises(ValueError): ledger.clear_accounting_halt(reconciliation_evidence='')
        ledger.clear_accounting_halt(reconciliation_evidence='Offline fixture only; real bounds reviewed separately')
        self.assertFalse(ledger.snapshot()['halted'])

    def test_transport_bills_before_downstream_malformed_parse(self):
        ledger = AtomicBudget(self.path, bootstrap_claude=False)
        response = SimpleNamespace(id='fixture-response', service_tier='flex',
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20,
                                  prompt_tokens_details=SimpleNamespace(cached_tokens=0)),
            choices=[SimpleNamespace(message=SimpleNamespace(content='not JSON'))])
        class Fake:
            async def create(self, **kwargs): return response
        client = BudgetedCompletions(Fake(), ledger, 'fixture', allow_paid=True)
        request = dict(model='gpt-6-luna', reasoning_effort='none', service_tier='flex',
            max_completion_tokens=100, messages=[{'role': 'user', 'content': 'fixture'}])
        with patch.dict(os.environ, {'OLENS_ALLOW_PAID_CALLS': '1'}):
            actual = asyncio.run(client.create(**request))
        self.assertIs(actual, response)
        self.assertGreater(ledger.snapshot()['actual_usd'], 0)
        self.assertEqual(ledger.snapshot()['reserved_usd'], 0)

    def test_transport_timeout_does_not_release_or_auto_retry(self):
        ledger = AtomicBudget(self.path, bootstrap_claude=False)
        class Fake:
            calls = 0
            async def create(self, **kwargs):
                self.calls += 1
                raise TimeoutError('offline fixture')
        inner = Fake()
        client = BudgetedCompletions(inner, ledger, 'fixture', allow_paid=True)
        request = dict(model='gpt-6-luna', reasoning_effort='none', service_tier='flex',
            max_completion_tokens=100, messages=[{'role': 'user', 'content': 'fixture'}])
        with patch.dict(os.environ, {'OLENS_ALLOW_PAID_CALLS': '1'}):
            with self.assertRaises(TimeoutError): asyncio.run(client.create(**request))
        self.assertEqual(inner.calls, 1)
        self.assertEqual(ledger.snapshot()['attempt_counts'], {'unknown': 1})
        self.assertGreater(ledger.snapshot()['unknown_usd'], 0)

    def test_cache_identity_includes_content_but_not_service_tier(self):
        request = dict(model='gpt-6-luna', reasoning_effort='none', service_tier='flex',
            max_completion_tokens=100, messages=[{'role': 'user', 'content': 'fixture'}])
        key = request_cache_key(request)
        self.assertEqual(key, request_cache_key({**request, 'service_tier': 'default'}))
        self.assertNotEqual(key, request_cache_key({**request, 'max_completion_tokens': 200}))
        self.assertNotEqual(key, request_cache_key({**request, 'response_format': {'type': 'json_object'}}))


if __name__ == '__main__':
    unittest.main()
