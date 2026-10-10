"""Offline financial-side-effect checks; no SDK, credentials, or API calls."""
import multiprocessing
import asyncio
import os
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from olens_improve.budget import AtomicBudget, BudgetExceeded, HOTPATH_INDEX_SQL, cost_units
from olens_improve.evaluation import BudgetedCompletions, request_cache_key


def _race(path, queue):
    ledger = AtomicBudget(path, hard_usd='0.01', target_usd='0.01', bootstrap_claude=False)
    try:
        ledger.reserve_attempt(1, 12000, run_id='race')
        queue.put('reserved')
    except BudgetExceeded:
        queue.put('blocked')


class BudgetTests(unittest.TestCase):
    def test_snapshot_reads_consistent_precommit_state_under_reserved_writer(self):
        ledger = AtomicBudget(self.path, hard_usd='.01', target_usd='.01', bootstrap_claude=False)
        aid = ledger.reserve_attempt(100, 10000, run_id='snapshot')
        before = ledger.snapshot()
        writer = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        try:
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE attempts SET status='unknown' WHERE attempt_id=?", (aid,))
            writer.execute("UPDATE config SET value=1 WHERE key='halted'")
            # A RESERVED writer permits readers; the reporting operation must
            # neither request another writer lock nor expose uncommitted rows.
            self.assertEqual(ledger.snapshot(), before)
            writer.execute('COMMIT')
        finally:
            if writer.in_transaction: writer.execute('ROLLBACK')
            writer.close()
        after = ledger.snapshot()
        self.assertEqual(after['attempt_counts'], {'unknown': 1})
        self.assertEqual(after['committed_usd'], before['committed_usd'])
        self.assertTrue(after['halted'])
        # A previously permissive report never authorizes a new physical call:
        # the unchanged writer transaction checks the current financial state.
        with self.assertRaises(BudgetExceeded): ledger.reserve_attempt(1, 1, run_id='snapshot')

    def test_hotpath_indexes_preserve_accounting_and_latest_cache_origin(self):
        ledger = AtomicBudget(self.path, bootstrap_claude=False)
        first = ledger.reserve_attempt(100, 100, run_id='origin',
            metadata={'content_cache_key':'exact-key','request':{'text':'first'}})
        ledger.settle(first,input_tokens=10,output_tokens=5)
        ledger.record_evidence(first,'physical_response',{'response_id':'first-response'})
        second = ledger.reserve_attempt(100,100,run_id='origin',
            metadata={'content_cache_key':'exact-key','request':{'text':'second'}})
        ledger.settle(second,input_tokens=20,output_tokens=10)
        ledger.record_evidence(second,'physical_response',{'response_id':'second-response'})
        unknown = ledger.reserve_attempt(100,100,run_id='origin',
            metadata={'content_cache_key':'exact-key','request':{'text':'unknown'}})
        ledger.mark_unknown(unknown,'offline uncertain attempt')
        other = ledger.reserve_attempt(100,100,run_id='another')
        ledger.settle(other,input_tokens=30,output_tokens=15)
        indexes = [statement.split(' ON ',1)[0].split()[-1] for statement in HOTPATH_INDEX_SQL]
        origin_sql = "SELECT attempt_id,metadata FROM attempts WHERE status='settled' AND " \
            "json_extract(metadata,'$.content_cache_key')=? ORDER BY created_utc DESC LIMIT 1"
        event_sql = "SELECT details FROM events WHERE attempt_id=? AND kind='physical_response' " \
            "ORDER BY sequence DESC LIMIT 1"
        def values():
            with sqlite3.connect(self.path) as db:
                origin = db.execute(origin_sql,('exact-key',)).fetchone()
                event = db.execute(event_sql,(origin[0],)).fetchone()[0]
                return {'snapshot':ledger.snapshot(),'committed':ledger._committed(db),
                    'run_committed':ledger._committed(db,'origin'),'origin':origin,'event':event}
        with sqlite3.connect(self.path) as db:
            for name in indexes: db.execute('DROP INDEX '+name)
        before = values()
        AtomicBudget(self.path,bootstrap_claude=False)
        after = values()
        self.assertEqual(before,after)
        self.assertEqual(after['origin'][0],second)
        self.assertEqual(json.loads(after['event'])['response_id'],'second-response')
        with sqlite3.connect(self.path) as db:
            plan = ' '.join(str(row) for row in db.execute('EXPLAIN QUERY PLAN '+origin_sql,('exact-key',)))
            self.assertIn('attempts_request_origin',plan)
            event_plan = ' '.join(str(row) for row in db.execute('EXPLAIN QUERY PLAN '+event_sql,(second,)))
            self.assertIn('events_attempt_kind_sequence',event_plan)

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
