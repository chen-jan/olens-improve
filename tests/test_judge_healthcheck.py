"""Bounded health dispatch checks with fake transport; no network or secrets."""
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget
from olens_improve.evaluation import request_cache_key
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


if __name__ == '__main__':unittest.main()
