import unittest
import torch
from olens_improve.contrastive import causal_candidate_logprobs


class LikelihoodAlignmentTests(unittest.TestCase):
    def test_carrier_last_logit_and_padding_exclusion(self):
        logits=torch.tensor([[0.,9.,0.],[0.,0.,9.],[9.,0.,0.],[0.,9.,0.],[9.,0.,0.],[9.,0.,0.]])
        actual=causal_candidate_logprobs(logits,3,[0,1])
        expected=torch.log_softmax(logits[[2,3]],dim=-1)[[0,1],[0,1]]
        self.assertTrue(torch.equal(actual,expected))
        wrong=torch.log_softmax(logits[[3,4]],dim=-1)[[0,1],[0,1]]
        self.assertFalse(torch.equal(actual,wrong))

    def test_short_logits_rejected(self):
        with self.assertRaises(ValueError):
            causal_candidate_logprobs(torch.zeros(2,3),2,[0,1])

    def test_batch_rows_match_singletons_with_different_lengths(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from olens_improve.contrastive import teacher_forced_likelihood_batch, teacher_forced_likelihood
        class Tokenizer:
            pad_token_id=0
            def __call__(self,text,add_special_tokens=False):
                return {'input_ids':{'short':[1],'long':[2,1,2]}[text]}
        class Model:
            def __init__(self):
                self.embedding=torch.nn.Embedding(3,3)
                with torch.no_grad(): self.embedding.weight.copy_(torch.eye(3))
            def get_input_embeddings(self): return self.embedding
            def __call__(self,inputs_embeds,attention_mask,use_cache):
                hidden=(inputs_embeds*attention_mask[:,:,None]).cumsum(dim=1)
                return SimpleNamespace(logits=hidden*.0001)
        lens=SimpleNamespace(tokenizer=Tokenizer(),model=Model(),device='cpu')
        acts=[torch.tensor([1.,0.,0.]),torch.tensor([0.,1.,0.])]
        with patch('olens_improve.models.carrier',return_value=([1,2],0,1)):
            batched=teacher_forced_likelihood_batch(lens,acts,44,['short','long'])
            singles=[teacher_forced_likelihood(lens,a,44,t) for a,t in zip(acts,['short','long'])]
        for batch,single in zip(batched,singles):
            self.assertEqual(batch['candidate_token_ids'],single['candidate_token_ids'])
            self.assertEqual(batch['token_log_likelihoods'],single['token_log_likelihoods'])
        self.assertEqual([r['candidate_token_count'] for r in batched],[1,3])
