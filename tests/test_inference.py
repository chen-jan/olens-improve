"""Local replay contracts, without weights, GPU generation or API calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from olens_improve.inference import (Artifacts, CandidatePool, activation_hash, generate_pool,
                         replay_select, samples_for_pool, select_scored_pool, vector)
from olens_improve.models import BASE_REVISION, PAIR_REVISION
from olens_improve.reconstruction import JointNNLS


def pool(texts):
    activation = torch.ones(5120)
    records = [dict(text=text, sample_index=i, layer=44, activation_sha256=activation_hash(activation),
                    base_revision=BASE_REVISION, adapter_revision=PAIR_REVISION, original_field={'kept': i})
               for i, text in enumerate(texts)]
    return CandidatePool.from_records(records, activation, 44, source_sha256='f'*64), activation


class InferenceTests(unittest.TestCase):
    def test_nonfinite_wrong_dimensions_and_zero_rejected(self):
        for value in (torch.ones(5121), torch.zeros(5120), torch.full((5120,), float('nan'))):
            with self.assertRaises(ValueError): vector(value)

    def test_saved_records_provenance_and_budget_preserved(self):
        p, h = pool(['- Alice owns 2 books.', '- Bob owns 3 books.'])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'pool.json'; path.write_text(json.dumps(p.as_dict()))
            restored = CandidatePool.load(path)
            self.assertEqual(restored.records, p.records)
        records = [dict(r) for r in p.records]; records[1]['activation_sha256'] = '0'*64
        with self.assertRaises(ValueError): CandidatePool.from_records(records, h, 44, source_sha256='f'*64)
        with self.assertRaises(ValueError): samples_for_pool(p, len, 3)
        many = [dict(p.records[0], sample_index=i) for i in range(33)]
        with self.assertRaises(ValueError): CandidatePool.from_records(many, h, 44, source_sha256='f'*64)

    def test_existing_pool_and_interrupted_claim_refuse_resampling(self):
        p, h = pool(['- Alice owns 2 books.']); artifacts = Artifacts('base', olens_adapter='lens')
        with tempfile.TemporaryDirectory() as d, patch('olens_improve.inference.FrozenOLens.load') as load:
            path = Path(d)/'pool.json'; path.write_text('{}')
            with self.assertRaises(FileExistsError): generate_pool(artifacts, h, 44, path)
            path.unlink(); path.with_suffix('.json.generation-claim').write_text('{}')
            with self.assertRaises(FileExistsError): generate_pool(artifacts, h, 44, path)
            load.assert_not_called()

    def test_blind_benchmark_records_rejected_on_import_and_saved_load(self):
        p, h = pool(['- Alice owns 2 books.'])
        records = [dict(p.records[0], generation_authorization_scope='blind_generation_only')]
        with self.assertRaisesRegex(ValueError, 'coordinator analysis-gated'):
            CandidatePool.from_records(records, h, 44, source_sha256='f'*64)
        payload = p.as_dict(); payload['records'] = records
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'pool.json'; path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'coordinator analysis-gated'):
                CandidatePool.load(path)

    def test_replay_baseline_and_unavailable_AR_not_false_score(self):
        p, h = pool(['Preamble\n- <think>\n']); count = lambda s: len(s.split())
        with patch('olens_improve.inference.token_counter', return_value=(None, count)):
            raw = replay_select(Artifacts('base'), p, h, method='raw_n1')
            self.assertEqual(raw['text'], p.records[0]['text']); self.assertIsNone(raw['fits'])
            missing = replay_select(Artifacts('base'), p, h, method='best_n')
            self.assertEqual(missing['status'], 'unavailable'); self.assertIsNone(missing['text'])
            with self.assertRaises(ValueError): replay_select(Artifacts('base'), p, h+1, method='raw_n1')
        samples = samples_for_pool(p, count); scorer = JointNNLS([1., 0.], {})
        capped = select_scored_pool(p, samples, count, method='capped_n1', scorer=scorer)
        self.assertEqual(capped['text'], '- <think>\n'); self.assertIsNone(capped['fits'])
        pruned = select_scored_pool(p, samples, count, method='prune_n1', scorer=scorer)
        self.assertEqual(pruned['text'], capped['text']); self.assertEqual(pruned['reason'], 'unavailable_parent_AR')

    def test_exact_selection_reuses_saved_candidates_and_no_default_controls(self):
        p, _ = pool(['- Alice owns 2 books.', '- Bob owns 3 books.'])
        count = lambda s: len(s.split()); samples = samples_for_pool(p, count)
        scorer = JointNNLS([1., 0.], {samples[0].bullets[0].phrase_id: [0., 1.],
                                     samples[1].bullets[0].phrase_id: [1., 0.]})
        result = select_scored_pool(p, samples, count, method='best_n', scorer=scorer)
        self.assertEqual(result['text'], '- Bob owns 3 books.'); self.assertEqual(result['fits']['fve'], 1.)
        capped = select_scored_pool(p, samples, count, method='capped_n1', scorer=scorer)
        self.assertEqual(capped['n'], 1); self.assertEqual(capped['requested_prefix'], 2)
        self.assertEqual(capped['consumed_prefix'], 1)
        absent = select_scored_pool(p, samples, count, method='specificity_mean', scorer=scorer)
        self.assertEqual(absent['status'], 'unavailable')


if __name__ == '__main__': unittest.main()
