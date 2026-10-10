"""Synthetic provenance/support tests; no model/API calls or semantic guarantees."""
import asyncio
from dataclasses import asdict
import random
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from olens_improve.claim_spans import (ClaimSpan, exact_spans, extract_verified_spans,
    select_span_support, span_groups, span_pair_shortlist, extraction_only, random_matched_spans)
from olens_improve.helpers import HelperValidationError, PairRelation, clique_clusters
from olens_improve.selection import Bullet, Sample, output_admissible


def span(i, sample, text, position=0):
    return ClaimSpan(i, f'{sample}:b{position}', sample, int(sample[1:]), position, text,
                     0, len(text), 2, len(text)+2, text)


class ClaimSpanTests(unittest.TestCase):
    def test_exact_offsets_preserve_qualifications_not_rewrites(self):
        text = 'If Alice might own 17 books, Bob does not own 2 books.'
        bullet = Bullet('source', text, 's0', 0, 2, len(text)+2)
        result = {'sources': [{'source_id': 'b0', 'quotes': [text, 'Bob owns 2 books.']}]}
        spans, rejected = exact_spans(result, {'b0': (bullet, 0)})
        self.assertEqual(len(spans), 1); self.assertEqual(spans[0].text, text)
        self.assertEqual((spans[0].readout_start, spans[0].readout_end), (2, len(text)+2))
        self.assertEqual(rejected[0]['reason'], 'not_unique_exact_contiguous_source_quote')

    def test_ambiguous_quotes_and_more_than_two_are_not_salvaged(self):
        bullet = Bullet('source', 'Alice owns 2. Alice owns 2.', 's0', 0)
        spans, rejected = exact_spans({'sources': [{'source_id': 'b0', 'quotes': ['Alice owns 2.']}]}, {'b0': (bullet, 0)})
        self.assertFalse(spans); self.assertEqual(len(rejected), 1)
        with self.assertRaises(HelperValidationError):
            exact_spans({'sources': [{'source_id': 'b0', 'quotes': ['x', 'y', 'z']}]}, {'b0': (bullet, 0)})

    def test_exact_copy_with_lost_scope_receives_no_vote(self):
        source = 'If Alice owns the key, Bob owns 2 books.'
        sample = Sample('s0', 0, (Bullet('source', source, 's0', 0, 2, len(source)+2),))
        class FakeHelper:
            def __init__(self, check): self.check = check; self.payloads = []
            async def call(self, system, payload, schema, **kwargs):
                self.payloads.append(payload)
                result = ({'results': [{'check_id': 'p00', 'source_entails_claim': False,
                           'self_contained': True, 'qualifications_preserved': False, 'reason': 'Lost governing conditional.'}]}
                          if self.check else {'sources': [{'source_id': 'b000', 'quotes': ['Bob owns 2 books.']}]})
                kwargs['validate'](result); return result
        proposal, checking = FakeHelper(False), FakeHelper(True)
        accepted, report = asyncio.run(extract_verified_spans([sample], proposal, checking))
        self.assertFalse(accepted)
        self.assertEqual(report['proposed_spans'][0]['text'], 'Bob owns 2 books.')
        self.assertFalse(report['source_checks'][0]['accepted'])
        self.assertEqual(checking.payloads[0]['checks'][0]['source_text'], source)
        self.assertNotIn('source', str(proposal.payloads[0]['sources'][0]['source_id']))

    def test_votes_are_distinct_samples_and_clusters_are_not_transitive(self):
        spans = [span('a', 's0', 'Alice owns 2 books.'), span('b', 's0', 'Alice owns 2 books.', 1),
                 span('c', 's1', 'Alice owns 2 books.'), span('d', 's2', 'Alice has 2 books.')]
        evidence = {'clusters': [['c000'], ['c001']]}
        selected = select_span_support(spans, evidence, .125, lambda _: True, semantic=False)
        self.assertEqual(selected.phrase_ids, ('a',)); self.assertEqual(selected.trace[0]['support'], 2)
        relations = {('a','b'): PairRelation('a','b','equivalent',True,True,True,'fixture',{}),
                     ('b','c'): PairRelation('b','c','equivalent',True,True,True,'fixture',{})}
        self.assertEqual(clique_clusters(['a','b','c'], relations), [['a','b'], ['c']])

    def test_pair_budget_and_same_sample_exclusion(self):
        spans = [span(f'c{i}', f's{i%16}', f'Alice owns {i} books.') for i in range(128)]
        pairs = span_pair_shortlist(span_groups(spans)); self.assertEqual(len(pairs), 40)
        singleton = [span('a','s0','Alice owns books.'), span('b','s0','Alice has books.')]
        self.assertEqual(span_pair_shortlist(span_groups(singleton)), [])

    def test_extraction_control_and_random_use_same_verbatim_span_pool(self):
        spans = [span(f'c{i}', f's{i}', f'Alice owns {i} books.') for i in range(6)]
        allowed = output_admissible(lambda text: len(text.split()), 256)
        parent = extraction_only(spans, ['s2:b0', 's0:b0'], allowed)
        self.assertEqual(parent.phrase_ids, ('c2','c0'))
        random_control = random_matched_spans(spans, 2, allowed, random.Random(3))
        self.assertEqual(len(random_control.bullets), 2)
        self.assertTrue(all(b.text in {s.text for s in spans} for b in random_control.bullets))

    def test_helper_efforts_route_through_distinct_budgeted_transports(self):
        from olens_improve.budget import AtomicBudget
        from olens_improve.evaluation import BudgetedClient
        from olens_improve.helpers import HelperCache
        sys.path.insert(0, str(Path(__file__).parents[1]/'scripts'))
        import claim_consensus as runner
        requests, closed = [], []
        class Transport:
            def __init__(self, effort): self.effort = effort; self.chat = SimpleNamespace(completions=self)
            async def create(self, **request):
                requests.append((self.effort, request))
                return SimpleNamespace(id='synthetic', service_tier='default',
                    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20,
                          prompt_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0)),
                    choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content='{"ok":true}', refusal=None))])
            async def close(self): closed.append(self.effort)
        def factory(ledger, run_id, *, allow_paid, reasoning_effort=None, **_):
            return BudgetedClient(Transport(reasoning_effort or 'none'), ledger, run_id,
                                  allow_paid=allow_paid, helper_reasoning_effort=reasoning_effort)
        async def calls(extraction, checking, clients):
            for helper in (extraction, checking):
                result = await helper.call('Only candidate text.', {'text': 'Alice owns 2 books.'},
                        {'type': 'json_schema'}, version='routing-fixture', max_output_tokens=100,
                        validate=lambda r: self.assertEqual(r, {'ok': True}))
                self.assertEqual(result, {'ok': True})
            await asyncio.gather(*(client.close() for client in clients))
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'OLENS_ALLOW_PAID_CALLS': '1',
                     'OLENS_TRANSPORT_RECOVERY_SINCE': ''}), \
             patch.object(runner, 'make_luna_client', side_effect=factory), \
             patch.object(runner, 'make_luna_helper_diagnostic_client', side_effect=factory):
            ledger = AtomicBudget(Path(directory)/'ledger.sqlite3', bootstrap_claude=False)
            ledger.set_run_limit('same-run', '2')
            extraction, checking, clients = runner.helper_clients(ledger, 'same-run', HelperCache(Path(directory)/'cache.sqlite3'))
            self.assertIs(extraction.semaphore, checking.semaphore)
            asyncio.run(calls(extraction, checking, clients))
            self.assertEqual(ledger.snapshot()['attempt_counts'], {'settled': 2})
        self.assertEqual([effort for effort, _ in requests], ['none', 'medium'])
        self.assertNotIn('temperature', requests[1][1]); self.assertEqual(set(closed), {'none', 'medium'})


if __name__ == '__main__': unittest.main()
