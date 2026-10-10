"""Operational measurement must preserve financial state and expose blocking."""
import asyncio
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget
from olens_improve.evaluation import BudgetedCompletions
from olens_improve.performance import OperationalProfile, profile_condition


class PerformanceTests(unittest.TestCase):
    def test_heartbeat_observes_synchronous_block_and_stays_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            profile = OperationalProfile(Path(d)/'profile.json',heartbeat_seconds=.01,sample_limit=3)
            async def run():
                profile.ensure_heartbeat(); await asyncio.sleep(.025)
                time.sleep(.04)  # Deliberately model a blocking callback; no transport.
                await asyncio.sleep(.025)
            asyncio.run(run()); report = profile.close('completed')
            metric = report['metrics']['event_loop.scheduling_lag']
            self.assertGreater(metric['maximum_seconds'],.02)
            self.assertLessEqual(metric['sample_count'],3)

    def test_fake_response_and_cancellation_preserve_accounting_evidence(self):
        class Inner:
            async def create(self,**request):
                await asyncio.sleep(.001)
                if request['messages'][0]['content']=='cancel': raise asyncio.CancelledError()
                return SimpleNamespace(id='offline-response',service_tier='default',
                    usage=SimpleNamespace(prompt_tokens=100,completion_tokens=20,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=0,cache_write_tokens=0)))
        with tempfile.TemporaryDirectory() as d:
            ledger = AtomicBudget(Path(d)/'ledger.sqlite3',bootstrap_claude=False)
            ledger.set_run_limit('offline','1'); original = ledger.snapshot
            profile = OperationalProfile(Path(d)/'profile.json'); profile.attach_ledger(ledger)
            client = BudgetedCompletions(Inner(),ledger,'offline',allow_paid=True)
            request = dict(model='gpt-6-luna',reasoning_effort='none',service_tier='default',
                           max_completion_tokens=100,messages=[{'role':'user','content':'ok'}])
            async def run():
                await client.create(**request)
                with self.assertRaises(asyncio.CancelledError):
                    await client.create(**(request|{'messages':[{'role':'user','content':'cancel'}]}))
            with patch.dict('os.environ',{'OLENS_ALLOW_PAID_CALLS':'1'},clear=True): asyncio.run(run())
            snapshot = ledger.snapshot(); report = profile.close('completed')
            self.assertEqual(snapshot,original())
            self.assertEqual(snapshot['attempt_counts'],{'settled':1,'unknown':1})
            self.assertGreater(snapshot['unknown_usd'],0)
            self.assertEqual(report['metrics']['ledger.reserve_attempt']['count'],2)
            self.assertEqual(report['metrics']['ledger.settle']['count'],1)
            self.assertEqual(report['metrics']['ledger.mark_unknown']['count'],1)
            self.assertNotIn('offline-response',json.dumps(report))
            self.assertNotIn('messages',json.dumps(report))
            self.assertIsNone(ledger._operational_profile)

    def test_opt_in_wrapper_preserves_return_and_exception(self):
        @profile_condition
        def f(*,fail=False):
            if fail: raise ValueError('do not log this private message')
            return {'value':4}
        self.assertEqual(f(),{'value':4})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'failure.json'
            with self.assertRaises(ValueError): f(fail=True,performance_profile=path)
            body = json.loads(path.read_text())
            self.assertEqual(body['status'],'failed:ValueError')
            self.assertNotIn('private',path.read_text())

    def test_sidecar_write_failure_preserves_success_and_original_exception(self):
        @profile_condition
        def f(*, fail=False):
            if fail: raise ValueError('original private failure')
            return 7
        with tempfile.TemporaryDirectory() as d:
            with patch.object(OperationalProfile,'close',side_effect=OSError('private write path')):
                output = io.StringIO()
                with contextlib.redirect_stderr(output):
                    self.assertEqual(f(performance_profile=Path(d)/'success.json'),7)
                    with self.assertRaisesRegex(ValueError,'original private failure'):
                        f(fail=True,performance_profile=Path(d)/'failure.json')
                lines = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual([row['exception_class'] for row in lines],['OSError','OSError'])
                self.assertNotIn('private',output.getvalue())

    def test_worker_rejects_source_ledger_and_accepts_only_manifest_child(self):
        spec = importlib.util.spec_from_file_location('offline_load',
            Path(__file__).resolve().parents[1]/'scripts/profile_judge_local_load.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root/'production.sqlite3'; source.write_bytes(b'source')
            child = root/'load-slots8.sqlite3'; child.write_bytes(b'copy')
            args = SimpleNamespace(output=root/'slots8-hallucination',slots=8,ledger=source)
            with self.assertRaises(ValueError): module.validate_worker_copy(args)
            (root/'offline-copy-manifest.json').write_text(json.dumps({
                'scope':'offline-disposable-ledgers-only','source':str(source),
                'copies':['load-slots8.sqlite3']}))
            with self.assertRaises(ValueError): module.validate_worker_copy(args)
            args.ledger = child; module.validate_worker_copy(args)
            child.unlink(); child.hardlink_to(source)
            with self.assertRaises(ValueError): module.validate_worker_copy(args)


if __name__ == '__main__': unittest.main()
