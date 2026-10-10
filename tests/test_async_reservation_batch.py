"""Batch ownership and dispatch order with disposable ledgers and a fake SDK."""
import asyncio
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget, BudgetExceeded, cost_units
from olens_improve.evaluation import BudgetedClient, LedgerOperationError
from olens_improve.performance import OperationalProfile
from test_async_ledger import FakeSDK, REQUEST, reached


class AsyncReservationBatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = AtomicBudget(Path(self.tmp.name) / 'ledger.sqlite3', bootstrap_claude=False)
        self.env = patch.dict(os.environ, {'OLENS_ALLOW_PAID_CALLS': '1',
            'OLENS_LEDGER_REUSE_WRITER_CONNECTION': '1',
            'OLENS_LEDGER_RESERVATION_BATCH_SIZE': '16'}, clear=True)
        self.env.start()
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        self.env.stop()
        self.tmp.cleanup()

    def client(self):
        sdk = FakeSDK()
        client = BudgetedClient(sdk, self.ledger, 'offline', allow_paid=True)
        self.clients.append(client)
        return client, sdk

    async def test_batching_coalesces_and_preserves_every_request_and_charge(self):
        sizes = []
        original = self.ledger.reserve_attempts
        def observed(requests):
            sizes.append(len(requests))
            return original(requests)
        self.ledger.reserve_attempts = observed
        profile = OperationalProfile(Path(self.tmp.name) / 'profile.json', metadata={'offline': True})
        profile.attach_ledger(self.ledger)
        first, sdk1 = self.client()
        second, sdk2 = self.client()
        self.assertIs(first.chat.completions.lane, second.chat.completions.lane)
        await asyncio.gather(*(self.clients[i % 2].chat.completions.create(**REQUEST) for i in range(35)))
        self.assertEqual(sum(sizes), 35)
        self.assertLessEqual(max(sizes), 16)
        self.assertGreater(max(sizes), 1)
        self.assertEqual(sdk1.calls + sdk2.calls, 35)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'], {'settled': 35})
        self.assertEqual(self.ledger.snapshot()['actual_usd'], 35 * cost_units(20, 10) / 1e9)
        with sqlite3.connect(self.ledger.path) as db:
            self.assertEqual(db.execute('SELECT count(DISTINCT attempt_id) FROM attempts').fetchone()[0], 35)
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE kind='physical_response'").fetchone()[0], 35)
        await first.close()
        await second.close()
        self.assertEqual(profile.metadata['ledger_reservation_batch_size'], 16)
        report = profile.close('offline_complete')
        self.assertEqual(report['metrics']['ledger.reserve_attempts']['count'], len(sizes))
        self.assertIsNone(self.ledger._writer_reuse)

    async def test_cancellation_and_close_wait_for_committed_batch(self):
        entered, release = threading.Event(), threading.Event()
        original = self.ledger.reserve_attempts
        def slow(requests):
            entered.set()
            release.wait(2)
            return original(requests)
        self.ledger.reserve_attempts = slow
        client, sdk = self.client()
        canceled = asyncio.create_task(client.chat.completions.create(**REQUEST))
        completed = asyncio.create_task(client.chat.completions.create(**REQUEST))
        await reached(entered)
        canceled.cancel()
        await asyncio.sleep(.005)
        canceled.cancel()
        closing = asyncio.create_task(client.close())
        await asyncio.sleep(.005)
        closing.cancel()
        await asyncio.sleep(.005)
        closing.cancel()
        self.assertEqual(sdk.calls, 0)
        self.assertFalse(canceled.done())
        self.assertFalse(closing.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await canceled
        await completed
        with self.assertRaises(asyncio.CancelledError):
            await closing
        self.assertEqual(sdk.calls, 1)
        self.assertEqual(sdk.closes, 1)
        snap = self.ledger.snapshot()
        self.assertEqual(snap['attempt_counts'], {'settled': 1, 'unknown': 1})
        self.assertGreater(snap['unknown_usd'], 0)
        lane = client.chat.completions.lane
        self.assertFalse(lane.reserve_operations)
        self.assertFalse(lane.reserve_queue)
        self.assertIsNone(lane.reserve_worker)
        self.assertFalse(lane.pending)

    async def test_failed_batch_dispatches_nothing_and_close_does_not_hang(self):
        self.ledger.set_run_limit('offline', '.000000001')
        client, sdk = self.client()
        errors = await asyncio.gather(*(client.chat.completions.create(**REQUEST) for _ in range(16)),
                                      return_exceptions=True)
        self.assertTrue(all(isinstance(error, BudgetExceeded) for error in errors))
        self.assertEqual(sdk.calls, 0)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'], {})
        await asyncio.wait_for(client.close(), 2)

    async def test_batch_io_failure_never_dispatches(self):
        def failure(_requests):
            raise OSError('offline injected failure')
        self.ledger.reserve_attempts = failure
        client, sdk = self.client()
        errors = await asyncio.gather(*(client.chat.completions.create(**REQUEST) for _ in range(20)),
                                      return_exceptions=True)
        self.assertTrue(all(isinstance(error, LedgerOperationError) for error in errors))
        self.assertEqual(sdk.calls, 0)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'], {})
        await asyncio.wait_for(client.close(), 2)

    async def test_wrong_returned_ids_fail_closed_and_retain_committed_holds(self):
        original = self.ledger.reserve_attempts
        def wrong_ids(requests):
            ids = original(requests)
            return list(reversed(ids)) if len(ids) > 1 else ['wrong-offline-id']
        self.ledger.reserve_attempts = wrong_ids
        client, sdk = self.client()
        errors = await asyncio.gather(*(client.chat.completions.create(**REQUEST) for _ in range(2)),
                                      return_exceptions=True)
        self.assertTrue(all(isinstance(error, LedgerOperationError) for error in errors))
        self.assertEqual(sdk.calls, 0)
        snap = self.ledger.snapshot()
        self.assertEqual(snap['attempt_counts'], {'reserved': 2})
        self.assertGreater(snap['reserved_usd'], 0)

    async def test_default_path_and_invalid_setting(self):
        os.environ['OLENS_LEDGER_RESERVATION_BATCH_SIZE'] = '32'
        with self.assertRaises(ValueError):
            self.client()
        os.environ.pop('OLENS_LEDGER_RESERVATION_BATCH_SIZE')
        client, sdk = self.client()
        self.assertEqual(client.chat.completions.lane.reserve_batch_size, 1)
        def forbidden(_requests):
            raise AssertionError('Default path must not batch')
        self.ledger.reserve_attempts = forbidden
        await client.chat.completions.create(**REQUEST)
        self.assertEqual(sdk.calls, 1)


if __name__ == '__main__':
    unittest.main()
