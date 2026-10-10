"""Candidate-only contrastive score utilities; diagnostic labels live outside this module."""
from typing import Any, Sequence
import math


def semantic_margin(original_score: float, alternative_scores: Sequence[float]) -> float:
    """Original minus strongest plausible single-edit alternative; not a truth label."""
    if not alternative_scores:
        raise ValueError("A near-miss margin requires at least one alternative")
    scores = [original_score, *alternative_scores]
    if not all(math.isfinite(value) for value in scores):
        raise ValueError("Nonfinite contrastive score")
    return original_score - max(alternative_scores)


def control_specificity(original_score: float, controls: dict[str, float], beta: float = 1.0,
                        aggregation: str = "mean") -> dict[str, Any]:
    """Use the supplied frozen control bank; caller owns split/group exclusions."""
    if not controls or not math.isfinite(beta) or beta < 0 or aggregation not in {"mean", "max"}:
        raise ValueError("Specificity requires controls and nonnegative beta")
    if not all(math.isfinite(x) for x in [original_score, *controls.values()]):
        raise ValueError("Nonfinite specificity score")
    worst = max(controls, key=controls.get)
    mean = math.fsum(controls.values()) / len(controls)
    baseline = mean if aggregation == "mean" else controls[worst]
    return {"score": original_score-beta*baseline, "own_fve": original_score,
            "aggregation": aggregation, "mean_control_fve": mean,
            "mean_specificity": original_score-beta*mean,
            "max_specificity": original_score-beta*controls[worst],
            "max_control_fve": controls[worst], "max_control_id": worst,
            "control_ids": list(controls), "beta": beta}


def two_by_two(scores: Sequence[Sequence[float]], generic: Sequence[float]) -> dict[str, Any]:
    """Rows are two targets, columns their respective paired diagnostic descriptions."""
    if len(scores) != 2 or any(len(row) != 2 for row in scores) or len(generic) != 2:
        raise ValueError("Diagnostic requires two-by-two scores and two generic scores")
    if not all(math.isfinite(x) for row in scores for x in row) or not all(math.isfinite(x) for x in generic):
        raise ValueError("Nonfinite diagnostic score")
    margins = [scores[0][0]-scores[0][1], scores[1][1]-scores[1][0]]
    return {"scores": [list(row) for row in scores], "self_minus_cross": margins,
            "interaction": sum(margins), "both_correct_pairings_win": all(x > 0 for x in margins),
            "generic_scores": list(generic),
            "specific_minus_generic": [scores[0][0]-generic[0], scores[1][1]-generic[1]]}


def teacher_forced_likelihood(lens: Any, activation: Any, layer: int, text: str) -> dict[str, Any]:
    """Singleton wrapper around the identical batched causal likelihood contract."""
    return teacher_forced_likelihood_batch(lens, [activation], layer, [text])[0]


def causal_candidate_logprobs(logits: Any, prefix_length: int, candidate_ids: Sequence[int]):
    """Carrier last-token logit predicts first candidate; exclude padding and EOS."""
    import torch
    if prefix_length < 1 or not candidate_ids:
        raise ValueError("Nonempty carrier and candidate required")
    aligned = logits[prefix_length-1:prefix_length+len(candidate_ids)-1].float()
    if len(aligned) != len(candidate_ids):
        raise ValueError("Logits do not cover causal candidate positions")
    targets = torch.tensor(candidate_ids, device=logits.device)
    return -torch.nn.functional.cross_entropy(aligned, targets, reduction="none")


def teacher_forced_likelihood_batch(lens: Any, activations: Sequence[Any], layer: int,
                                    texts: Sequence[str]) -> list[dict[str, Any]]:
    """Independent same-layer conditional likelihood rows, not jointly read cells.

    Full capped candidate text with no EOS, exact carrier and unit16000 injection.
    Each target/control uses identical candidate tokens. No target transcript input.
    """
    import torch
    from .models import carrier
    if not texts or len(texts) != len(activations):
        raise ValueError("Aligned nonempty likelihood inputs required")
    prefix, slot, marker = carrier(lens.tokenizer, layer)
    candidates = [lens.tokenizer(text, add_special_tokens=False)["input_ids"] for text in texts]
    if any(not row or len(row)>256 for row in candidates):
        raise ValueError("Each likelihood candidate needs1..256tokens")
    vectors = torch.stack([torch.as_tensor(v).reshape(-1) for v in activations]).to(lens.device).float()
    norms = vectors.norm(dim=1, keepdim=True)
    if not torch.isfinite(vectors).all() or bool((norms<=1e-8).any()):
        raise ValueError("Invalid likelihood activation")
    width = len(prefix)+max(map(len,candidates))
    pad = lens.tokenizer.pad_token_id
    if pad is None:
        raise ValueError("Frozen tokenizer requires explicit pad token")
    inputs = torch.full((len(texts),width),pad,dtype=torch.long,device=lens.device)
    mask = torch.zeros_like(inputs)
    for index,row in enumerate(candidates):
        sequence=prefix+row
        inputs[index,:len(sequence)] = torch.tensor(sequence,device=lens.device)
        mask[index,:len(sequence)] = 1
    with torch.inference_mode():
        embeds=lens.model.get_input_embeddings()(inputs)
        embeds[:,slot,:]=(16000*vectors/norms).to(embeds.dtype)
        logits=lens.model(inputs_embeds=embeds,attention_mask=mask,use_cache=False).logits
        outputs=[]
        for index,row in enumerate(candidates):
            logp=causal_candidate_logprobs(logits[index],len(prefix),row)
            outputs.append({"average_log_likelihood":float(logp.mean()),"sum_log_likelihood":float(logp.sum()),
                "candidate_token_ids":row,"candidate_token_count":len(row),
                "token_log_likelihoods":logp.cpu().tolist(),"include_eos":False,
                "carrier_ids":prefix,"slot":slot,"marker_id":marker,
                "batch_size":len(texts),"padding":"right",
                "causal_shift":"carrier_last_logit_predicts_first_candidate_token"})
    return outputs
