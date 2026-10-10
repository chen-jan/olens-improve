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
    """E3 likelihood with the exact carrier/injection and proper causal token shift.

    Candidate-only text; full candidate length, no AR32-token truncation. This does
    not generate new O-lens samples and exposes no original target prompt/context.
    """
    import torch
    from .models import carrier
    if not text:
        raise ValueError("Empty likelihood candidate")
    ids, slot, marker = carrier(lens.tokenizer, layer)
    candidate = lens.tokenizer(text, add_special_tokens=False)["input_ids"]
    if not candidate:
        raise ValueError("No candidate tokens")
    if len(candidate) > 256:
        raise ValueError("Likelihood candidate exceeds frozen256-token output limit")
    v = activation.to(lens.device).float().reshape(-1)
    if not torch.isfinite(v).all() or float(v.norm()) <= 1e-8:
        raise ValueError("Invalid activation")
    with torch.inference_mode():
        embedding = lens.model.get_input_embeddings()
        all_ids = torch.tensor([ids+candidate],device=lens.device)
        embeds = embedding(all_ids)
        embeds[0,slot,:] = (16000*v/v.norm()).to(embeds.dtype)
        logits = lens.model(inputs_embeds=embeds,attention_mask=torch.ones_like(all_ids),
                            use_cache=False).logits
        # Logits at the carrier's last token predict the candidate's first token.
        aligned = logits[0,len(ids)-1:len(ids)+len(candidate)-1].float()
        targets = torch.tensor(candidate,device=lens.device)
        logp = -torch.nn.functional.cross_entropy(aligned,targets,reduction="none")
    return {"average_log_likelihood": float(logp.mean()), "sum_log_likelihood":float(logp.sum()),
            "candidate_token_ids":candidate,"token_log_likelihoods":logp.cpu().tolist(),
            "include_eos":False,"carrier_ids":ids,"slot":slot,"marker_id":marker,
            "causal_shift":"carrier_last_logit_predicts_first_candidate_token"}
