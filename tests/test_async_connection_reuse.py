"""Owned writer-lane lifecycle on disposable ledgers and fake SDKs only."""
import asyncio
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget, cost_units
from olens_improve.evaluation import BudgetedClient, LedgerOperationError
from olens_improve.performance import OperationalProfile
from test_async_ledger import FakeSDK, REQUEST, reached


class AsyncConnectionReuseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = AtomicBudget(Path(self.tmp.name) / 'ledger.sqlite3', bootstrap_claude=False)
        self.env = patch.dict(os.environ, {'OLENS_ALLOW_PAID_CALLS': '1',
            'OLENS_LEDGER_REUSE_WRITER_CONNECTION': '1'}, clear=True)
        self.env.start()
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            try:
                await client.close()
            except (RuntimeError, OSError):
                pass  # Explicitly injected close failures are asserted in their test.
        self.env.stop()
        self.tmp.cleanup()

    def client(self, sdk=None):
        sdk = sdk or FakeSDK()
        client = BudgetedClient(sdk, self.ledger, 'offline', allow_paid=True)
        self.clients.append(client)
        return client, sdk

    async def test_shared_lane_reuses_until_last_client_and_reports_effective_mode(self):
        profile = OperationalProfile(Path(self.tmp.name) / 'profile.json', metadata={'offline': True})
        self.ledger._operational_profile = profile
        first, sdk1 = self.client()
        second, sdk2 = self.client()
        lane = first.chat.completions.lane
        self.assertIs(lane, second.chat.completions.lane)
        self.assertTrue(profile.metadata['ledger_writer_connection_reuse'])
        self.assertFalse(profile.metadata['ledger_writer_reuse_started'])
        self.assertIsNone(self.ledger._writer_reuse)
        await first.chat.completions.create(**REQUEST)
        connection = self.ledger._writer_reuse['connection']
        self.assertIsNot(self.ledger._writer_reuse['owner'][1], threading.current_thread())
        self.assertTrue(profile.metadata['ledger_writer_reuse_started'])
        self.assertEqual(profile.metadata['ledger_writer_cache_kib'], 16384)
        await first.close()
        self.assertEqual(lane.users, 1)
        await second.chat.completions.create(**REQUEST)
        self.assertIs(connection, self.ledger._writer_reuse['connection'])
        self.assertFalse(connection.in_transaction)
        await second.close()
        self.assertIsNone(self.ledger._writer_reuse)
        self.assertFalse(hasattr(self.ledger, '_async_ledger_lane'))
        self.assertEqual((sdk1.closes, sdk2.closes), (1, 1))
        self.assertEqual(self.ledger.snapshot()['attempt_counts'], {'settled': 2})
        self.assertEqual(self.ledger.snapshot()['actual_usd'], 2 * cost_units(20, 10) / 1e9)
        profile.close('offline_complete')

    async def test_closing_lane_rejects_registration_and_repeated_cancel_waits_for_close(self):
        client, sdk = self.client()
        await client.chat.completions.create(**REQUEST)
        lane = client.chat.completions.lane
        started, release = threading.Event(), threading.Event()
        original = self.ledger.close_writer_connection
        def slow_close():
            started.set()
            release.wait(2)
            original()
        self.ledger.close_writer_connection = slow_close
        closing = asyncio.create_task(client.close())
        await reached(started)
        self.assertTrue(lane.closing)
        with self.assertRaisesRegex(RuntimeError, 'closing'):
            BudgetedClient(FakeSDK(), self.ledger, 'offline', allow_paid=True)
        with self.assertRaisesRegex(RuntimeError, 'closing'):
            await lane.call(lambda: None)
        closing.cancel()
        await asyncio.sleep(.005)
        closing.cancel()
        self.assertFalse(closing.done())
        self.assertEqual(sdk.closes, 0)
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await closing
        self.assertEqual(sdk.closes, 1)
        self.assertIsNone(self.ledger._writer_reuse)
        self.assertFalse(hasattr(self.ledger, '_async_ledger_lane'))
        replacement, replacement_sdk = self.client()
        self.assertIsNot(replacement.chat.completions.lane, lane)
        await replacement.chat.completions.create(**REQUEST)
        self.assertEqual(replacement_sdk.calls, 1)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'], {'settled': 2})

    async def test_cancelled_reservation_retains_exact_hold_without_dispatch(self):
        started, release = threading.Event(), threading.Event()
        original = self.ledger.reserve_attempt
        def slow(*args, **kwargs):
            started.set()
            release.wait(2)
            return original(*args, **kwargs)
        self.ledger.reserve_attempt = slow
        client, sdk = self.client()
        request = asyncio.create_task(client.chat.completions.create(**REQUEST))
        await reached(started)
        request.cancel()
        await asyncio.sleep(.005)
        request.cancel()
        self.assertFalse(request.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await request
        self.assertEqual(sdk.calls, 0)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'], {'unknown': 1})
        self.assertGreater(self.ledger.snapshot()['unknown_usd'], 0)
        await client.close()
        self.assertIsNone(self.ledger._writer_reuse)

    async def test_inode_change_stops_dispatch_and_poisoned_close_still_closes_sdk(self):
        client, sdk = self.client()
        await client.chat.completions.create(**REQUEST)
        before = self.ledger.snapshot()
        replacement = Path(self.tmp.name) / 'replacement.sqlite3'
        shutil.copyfile(self.ledger.path, replacement)
        os.replace(replacement, self.ledger.path)
        with self.assertRaises(LedgerOperationError):
            await client.chat.completions.create(**REQUEST)
        self.assertEqual(sdk.calls, 1)
        self.assertEqual(self.ledger.snapshot(), before)
        with self.assertRaisesRegex(RuntimeError, 'restart'):
            await client.close()
        self.assertEqual(sdk.closes, 1)
        self.assertIsNone(self.ledger._writer_reuse['connection'])
        self.assertFalse(hasattr(self.ledger, '_async_ledger_lane'))

    async def test_forked_lane_fails_before_queue_and_dispatch(self):
        client, sdk = self.client()
        lane = client.chat.completions.lane
        lane.owner_pid = -1  # Simulate fork identity without forking an event loop.
        with self.assertRaises(LedgerOperationError):
            await client.chat.completions.create(**REQUEST)
        with self.assertRaisesRegex(RuntimeError, 'forked'):
            BudgetedClient(FakeSDK(), self.ledger, 'offline', allow_paid=True)
        self.assertEqual(sdk.calls, 0)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'], {})
        lane.owner_pid = os.getpid()

    async def test_close_error_remains_primary_and_executor_sdk_both_close(self):
        class FailingSDK(FakeSDK):
            async def close(self):
                self.closes += 1
                raise TypeError('fake secondary SDK close failure')
        client, sdk = self.client(FailingSDK())
        await client.chat.completions.create(**REQUEST)
        original = self.ledger.close_writer_connection
        def fail_close():
            original()
            raise OSError('fake primary writer close failure')
        self.ledger.close_writer_connection = fail_close
        with self.assertRaisesRegex(OSError, 'primary'):
            await client.close()
        self.assertIsNone(self.ledger._writer_reuse)
        self.assertFalse(hasattr(self.ledger, '_async_ledger_lane'))
        self.assertEqual(sdk.closes, 1)
        self.assertEqual(self.ledger.snapshot()['attempt_counts'], {'settled': 1})

    async def test_default_and_invalid_env_do_not_enable_reuse(self):
        os.environ['OLENS_LEDGER_REUSE_WRITER_CONNECTION'] = 'yes'
        with self.assertRaises(ValueError):
            self.client()
        self.assertFalse(hasattr(self.ledger, '_async_ledger_lane'))
        os.environ.pop('OLENS_LEDGER_REUSE_WRITER_CONNECTION')
        client, sdk = self.client()
        await client.chat.completions.create(**REQUEST)
        self.assertFalse(client.chat.completions.lane.reuse_writer_connection)
        self.assertIsNone(self.ledger._writer_reuse)
        self.assertEqual(sdk.calls, 1)


if __name__ == '__main__':
    unittest.main()
