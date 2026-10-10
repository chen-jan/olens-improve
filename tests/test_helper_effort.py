"""An optional helper effort must never change the benchmark judge contract."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from olens_improve.budget import AtomicBudget
from olens_improve.evaluation import BudgetedCompletions, request_cache_key
from olens_improve.helpers import HelperCache, LunaHelper


class FakeCompletions:
    def __init__(self):
        self.requests = []

    async def create(self, **request):
        self.requests.append(request)
        return SimpleNamespace(id='fake-response', service_tier='default',
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20,
                                  prompt_tokens_details=SimpleNamespace(cached_tokens=0)),
            choices=[SimpleNamespace(finish_reason='stop',
                                     message=SimpleNamespace(content='{"ok":true}', refusal=None))])


class HelperEffortTests(unittest.TestCase):
    def test_benchmark_rejects_medium_before_reservation(self):
        with TemporaryDirectory() as tmp, patch.dict('os.environ', {'OLENS_ALLOW_PAID_CALLS': '1'}):
            ledger = AtomicBudget(Path(tmp)/'ledger.sqlite3', bootstrap_claude=False)
            ledger.set_run_limit('test', '1')
            inner = FakeCompletions()
            client = BudgetedCompletions(inner, ledger, 'test', allow_paid=True)
            with self.assertRaises(ValueError):
                asyncio.run(client.create(model='gpt-6-luna', reasoning_effort='medium'))
            self.assertEqual(inner.requests, [])
            self.assertEqual(ledger.snapshot()['attempt_counts'], {})

    def test_helper_medium_omits_temperature_and_settles(self):
        with TemporaryDirectory() as tmp, patch.dict('os.environ', {'OLENS_ALLOW_PAID_CALLS': '1'}):
            ledger = AtomicBudget(Path(tmp)/'ledger.sqlite3', bootstrap_claude=False)
            ledger.set_run_limit('test', '1')
            inner = FakeCompletions()
            guarded = BudgetedCompletions(inner, ledger, 'test', allow_paid=True,
                                         helper_reasoning_effort='medium')
            helper = LunaHelper(SimpleNamespace(chat=SimpleNamespace(completions=guarded)),
                                HelperCache(Path(tmp)/'cache.sqlite3'), attempts=1,
                                reasoning_effort='medium')
            schema = {'type': 'json_schema', 'json_schema': {'name': 'test', 'strict': True,
                      'schema': {'type': 'object', 'properties': {'ok': {'type': 'boolean'}},
                                 'required': ['ok'], 'additionalProperties': False}}}
            result = asyncio.run(helper.call('Compare only supplied candidate text.',
                                  {'a': '12', 'b': '13'}, schema, version='fixture',
                                  validate=lambda value: self.assertEqual(value, {'ok': True})))
            self.assertEqual(result, {'ok': True})
            self.assertNotIn('temperature', inner.requests[0])
            self.assertEqual(inner.requests[0]['reasoning_effort'], 'medium')
            self.assertEqual(ledger.snapshot()['attempt_counts'], {'settled': 1})
            medium = request_cache_key(inner.requests[0])
            self.assertNotEqual(medium, request_cache_key({**inner.requests[0], 'reasoning_effort': 'none'}))

    def test_medium_sampling_override_rejected(self):
        with TemporaryDirectory() as tmp, patch.dict('os.environ', {'OLENS_ALLOW_PAID_CALLS': '1'}):
            ledger = AtomicBudget(Path(tmp)/'ledger.sqlite3', bootstrap_claude=False)
            client = BudgetedCompletions(FakeCompletions(), ledger, 'test', allow_paid=True,
                                        helper_reasoning_effort='medium')
            for field, value in [('temperature', 0), ('top_p', 1), ('logprobs', False), ('top_logprobs', 0)]:
                with self.subTest(field=field), self.assertRaises(ValueError):
                    asyncio.run(client.create(model='gpt-6-luna', reasoning_effort='medium', **{field: value}))


if __name__ == '__main__':
    unittest.main()
