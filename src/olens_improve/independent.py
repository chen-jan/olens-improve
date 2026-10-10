"""Frozen J++ vocabulary diagnostics from existing adapter-free activations.

Token support is not relational verification. Fitting-group overlap is unresolved;
this reader is restricted to development diagnostics and never edits candidates.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from typing import Any

JPP_REVISION = "6c96867a91c43c14cec17cf0f6d157b933c5fee5"
JPP_SOURCE_REVISION = "93f02cd6c27db765abb127f20eff656bb5d27340"


def candidate_mentions(text: str) -> list[dict]:
    """Bounded source-span heuristic, not named-entity recognition or gold access."""
    patterns = (("number", r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?!\w)"),
                ("capitalized_span", r"\b[A-Z][\w'-]*(?:[ \t]+[A-Z][\w'-]*){0,4}\b"))
    rows = []
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text):
            rows.append({"kind": kind, "text": match.group(), "start": match.start(), "end": match.end()})
    return sorted(rows, key=lambda row: (row["start"], row["end"], row["kind"]))


def changed_source_spans(left: str, right: str) -> list[dict]:
    """Exact word/number-level contrast spans, including ordered role changes."""
    pattern = r"\d+(?:[.,]\d+)*|\w+(?:[-']\w+)*|[^\w\s]"
    matches = [list(re.finditer(pattern, text)) for text in (left, right)]
    words = [[match.group() for match in row] for row in matches]
    output = []
    for tag, first, end_first, second, end_second in SequenceMatcher(a=words[0], b=words[1], autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        spans = []
        for text, row, begin, end in ((left, matches[0], first, end_first), (right, matches[1], second, end_second)):
            if begin == end:
                position = row[begin].start() if begin < len(row) else len(text)
                spans.append({"text": "", "start": position, "end": position})
            else:
                start, finish = row[begin].start(), row[end-1].end()
                spans.append({"text": text[start:finish], "start": start, "end": finish})
        output.append({"operation": tag, "left": spans[0], "right": spans[1]})
    return output


def component_support(text, tokenizer, prepared):
    ids = tokenizer(text, add_special_tokens=False)["input_ids"]
    return {"text": text, "token_ids": ids, "tokens": [tokenizer.decode([token]) for token in ids],
            "ranks": prepared["ranks"][ids].cpu().tolist(),
            "log_probabilities": prepared["log_probabilities"][ids].cpu().tolist(),
            "joint_sequence_probability": None}


@dataclass
class FrozenJPP:
    maps: dict[int, Any]
    norm: Any
    head: Any
    config: dict
    device: str

    @classmethod
    def load(cls, lens_path: str, base_path: str, layers: list[int], device: str = "cuda"):
        import torch
        from safetensors import safe_open
        from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5RMSNorm
        checkpoint = torch.load(lens_path, map_location="cpu", weights_only=True, mmap=True)
        config = checkpoint["config"]
        if config.get("hf_model_name") != "Qwen/Qwen3.6-27B" or config.get("d_model") != 5120 or config.get("lens_type") != "jacobian":
            raise ValueError("Unexpected J++ frozen model/transport configuration")
        saved = checkpoint["parameters"]["jacobians"]
        if set(saved) != set(checkpoint["source_layers"]) or any(layer not in saved for layer in layers):
            raise ValueError("J++ does not cover the requested zero-based block-output layers")
        maps = {layer: saved[layer].float().to(device) for layer in sorted(set(layers))}
        if any(matrix.shape != (5120, 5120) for matrix in maps.values()):
            raise ValueError("Unexpected J++ transport coordinates")
        base = Path(base_path)
        index = json.loads((base / "model.safetensors.index.json").read_text())["weight_map"]
        def weight(name):
            with safe_open(str(base / index[name]), framework="pt") as source:
                return source.get_tensor(name).to(device)
        head = weight("lm_head.weight")
        norm_weight = weight("model.language_model.norm.weight")
        cfg = json.loads((base / "config.json").read_text())
        cfg = cfg.get("text_config", cfg)
        norm = Qwen3_5RMSNorm(5120, eps=cfg["rms_norm_eps"]).to(device=device, dtype=norm_weight.dtype)
        with torch.no_grad():
            norm.weight.copy_(norm_weight)
        norm.eval()
        norm.requires_grad_(False)
        return cls(maps, norm, head, config, device)

    def transport(self, activation, layer: int):
        import torch
        if layer not in self.maps or activation.shape[-1] != 5120:
            raise ValueError("Invalid J++ layer or activation width")
        with torch.inference_mode():
            return activation.to(device=self.device, dtype=torch.float32) @ self.maps[layer].T

    def logits(self, activation, layer: int):
        import torch
        with torch.inference_mode():
            transported = self.transport(activation, layer)
            # Match pinned HFLensModel.unembed: cast to the base head dtype
            # before the original Qwen final norm, including its 1+weight rule.
            normalized = self.norm(transported.to(self.head.dtype))
            return torch.nn.functional.linear(normalized, self.head).float()


def vocabulary_summary(logits, tokenizer, top_k: int = 10) -> dict:
    """Prepare vocabulary ranks once per cell, reused for its candidate strings."""
    import torch
    if logits.ndim != 1 or top_k < 1 or top_k > logits.numel():
        raise ValueError("Expected one vocabulary-logit vector and valid top_k")
    order = logits.argsort(descending=True, stable=True)
    ranks = torch.empty_like(order)
    ranks[order] = torch.arange(1, logits.numel()+1, device=logits.device)
    ids = order[:top_k].cpu().tolist()
    return {"ranks": ranks, "log_probabilities": logits-torch.logsumexp(logits, dim=0),
            "top_token_ids": ids, "top_tokens": [tokenizer.decode([token]) for token in ids]}


def token_support(logits, text: str, tokenizer, top_k: int = 10, prepared=None) -> dict:
    """Ranks of candidate-derived token variants; no truth or support cutoff."""
    import torch
    if logits.ndim != 1 or top_k < 1 or top_k > logits.numel():
        raise ValueError("Expected one vocabulary-logit vector and valid top_k")
    with torch.inference_mode():
        prepared = prepared if prepared is not None else vocabulary_summary(logits, tokenizer, top_k)
        ranks = prepared["ranks"]
        mentions = []
        for mention in candidate_mentions(text):
            variants = []
            for variant in (mention["text"], " " + mention["text"]):
                ids = tokenizer(variant, add_special_tokens=False)["input_ids"]
                variants.append({"text": variant, "token_ids": ids,
                    "ranks": ranks[ids].cpu().tolist(),
                    "log_probabilities": prepared["log_probabilities"][ids].cpu().tolist()})
            mentions.append(mention | {"variants": variants})
        return {"mentions": mentions, "top_token_ids": prepared["top_token_ids"],
                "top_tokens": prepared["top_tokens"],
                "vocabulary_filter": "none", "rank_ties": "stable_token_id",
                "warning": "Presence is not relational proof; absence is not falsehood."}
