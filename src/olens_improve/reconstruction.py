"""Prompt-tag AR inference and published-score-compatible small NNLS fits.

Source contract: public olens_draft a32590085a6070d75f950155d3c2b3db3eec97ef.
Mathematical checks can run without model weights. Missing whitening fails closed.
"""
from dataclasses import dataclass
import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Sequence


class RawVectorCache:
    """Read completed raw-vector shards lazily; never infer semantic equivalence from cache hits."""
    def __init__(self, directory: str, max_resident_shards: int = 2):
        self.directory = Path(directory)
        self.contract = json.loads((self.directory / "contract.json").read_text())
        self.index = {}
        self.max_resident_shards = max_resident_shards
        self._shards = OrderedDict()
        for path in sorted(self.directory.glob("raw_*.index.json")):
            info = json.loads(path.read_text())
            if info["contract_sha256"] != self.contract["sha256"]:
                raise ValueError("Raw-vector cache contract mismatch")
            for row in info["vectors"]:
                if row["cache_key"] in self.index:
                    raise ValueError("Duplicate raw-vector cache key")
                self.index[row["cache_key"]] = dict(row, tensor_path=info["tensor_path"])

    def get(self, key: str) -> Any:
        from safetensors.torch import load_file
        row = self.index[key]
        path = row["tensor_path"]
        if path not in self._shards:
            self._shards[path] = load_file(path, device="cpu")["vectors"]
        self._shards.move_to_end(path)
        while len(self._shards) > self.max_resident_shards:
            self._shards.popitem(last=False)
        return self._shards[path][row["row"]]

    def get_many(self, keys: Sequence[str]) -> dict[str, Any]:
        return {key: self.get(key) for key in keys}


def ar_token_ids(tokenizer: Any, text: str) -> tuple[str, list[int]]:
    """Published bare reward tokenization, before its separate32-token span cap."""
    pattern = r"</?explanation>|<\|im_start\|>(system|user|assistant)?|<\|im_end\|>|<think>|</think>"
    cleaned = re.sub(pattern, "", text).strip()
    special = set(tokenizer.all_special_ids)
    ids = tokenizer(cleaned, add_special_tokens=False)["input_ids"]
    return cleaned, [token for token in ids if token not in special]


def whitening_matrix(cov: Any, ridge_c: float = 0.1) -> Any:
    import torch
    covariance = cov.to(torch.float64)
    covariance = (covariance + covariance.T) * 0.5
    ridge = (ridge_c * covariance.diagonal().mean()).clamp_min(1e-12)
    eigenvalues, eigenvectors = torch.linalg.eigh(covariance)
    scales = (eigenvalues.clamp_min(0) + ridge).rsqrt()
    return ((eigenvectors * scales[None, :]) @ eigenvectors.T).float()


@dataclass
class Whitener:
    mu: Any
    w: Any
    artifact_sha256: str
    ridge_c: float = 0.1

    @classmethod
    def load(cls, path: str, ridge_c: float = 0.1, device: str = "cpu") -> "Whitener":
        from safetensors.torch import load_file
        artifact = Path(path)
        if not artifact.is_file():
            raise FileNotFoundError("Matching pooled whitening artifact required; no fallback ruler")
        moments = load_file(str(artifact), device="cpu")
        if set(moments) != {"mu", "cov"}:
            raise ValueError(f"Unexpected whitener moment keys: {list(moments)}")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        return cls(moments["mu"].to(device), whitening_matrix(moments["cov"], ridge_c).to(device),
                   digest, ridge_c)

    def whiten(self, x: Any) -> Any:
        return (x.float() - self.mu.to(x.device)) @ self.w.to(x.device).T


def released_nnls(vectors: Any, target: Any, iterations: int = 80) -> tuple[Any, float]:
    """Published projected-gradient solver, including its finite-iteration convention."""
    import torch
    if vectors.shape[0] == 0:
        return torch.zeros(0, dtype=target.dtype, device=target.device), 0.0
    gram = vectors @ vectors.T
    rhs = vectors @ target
    step = 1.0 / gram.diagonal().sum().clamp_min(1e-12)
    weights = torch.zeros_like(rhs)
    for _ in range(iterations):
        weights = (weights - step * (gram @ weights - rhs)).clamp_min(0)
    residual = target - weights @ vectors
    fve = 1 - residual.square().sum() / target.square().sum().clamp_min(1e-12)
    return weights, float(fve)


@dataclass
class Fit:
    coefficients: list[float]
    fve: float
    atom_ids: tuple[str, ...]
    solver: str


class JointNNLS:
    """Per-cell scorer; candidate IDs refer to this target's fixed vector dictionary.

    Inputs must already be centered/whitened; phrase rows are unit directions,
    while the target keeps its whitened magnitude. Use from_raw for that contract.
    """
    def __init__(self, target: Any, vectors: dict[str, Any], *, solver: str = "scipy_exact",
                 metadata: dict[str, Any] | None = None):
        import torch
        self.target = torch.as_tensor(target).float().cpu().reshape(-1).clone()
        self.vectors = {k: torch.as_tensor(v).float().cpu().reshape(-1).clone() for k, v in vectors.items()}
        if not torch.isfinite(self.target).all():
            raise ValueError("Nonfinite score target")
        for value in self.vectors.values():
            if value.shape != self.target.shape or not torch.isfinite(value).all():
                raise ValueError("Incompatible/nonfinite candidate vector")
        if solver not in {"released80", "scipy_exact"}:
            raise ValueError("Unknown solver")
        self.solver = solver
        self.metadata = dict(metadata or {}) | {
            "target_sha256": hashlib.sha256(self.target.numpy().tobytes()).hexdigest(),
            "solver": solver, "objective": "1-squared_residual/squared_target", "clip": False,
        }
        self._cache: dict[tuple[str, ...], Fit] = {}

    @classmethod
    def from_raw(cls, target: Any, vectors: dict[str, Any], whitener: Whitener, **kwargs: Any):
        import torch
        target = whitener.whiten(torch.as_tensor(target).reshape(1, -1))[0].cpu()
        transformed = {}
        for key, value in vectors.items():
            row = whitener.whiten(torch.as_tensor(value).reshape(1, -1))[0].cpu()
            transformed[key] = row / (row.norm() + 1e-9)
        metadata = dict(kwargs.pop("metadata", {})) | {
            "whitener_sha256": whitener.artifact_sha256, "ridge_c": whitener.ridge_c,
            "center_predictions": True, "unit_phrase_directions": True,
        }
        return cls(target, transformed, metadata=metadata, **kwargs)

    def fit(self, atom_ids: Sequence[str]) -> Fit:
        import torch
        key = tuple(atom_ids)
        if len(set(key)) != len(key):
            raise ValueError("Repeated candidate IDs in fit")
        if key in self._cache:
            return self._cache[key]
        rows = torch.stack([self.vectors[k] for k in key]) if key else self.target.new_empty((0, len(self.target)))
        if self.solver == "released80" or not key:
            coeff, fve = released_nnls(rows, self.target)
        else:
            from scipy.optimize import nnls
            coeff_np, residual = nnls(rows.numpy().astype("float64").T,
                                      self.target.numpy().astype("float64"))
            coeff = torch.from_numpy(coeff_np)
            fve = 1 - residual**2 / max(float(self.target.double().square().sum()), 1e-12)
        result = Fit(coeff.tolist(), fve, key, self.solver)
        self._cache[key] = result
        return result

    def score(self, atom_ids: Sequence[str]) -> float:
        return self.fit(atom_ids).fve


@dataclass
class FrozenAR:
    tokenizer: Any
    backbone: Any
    head: Any
    tags: Any
    layers: tuple[int, ...]
    device: str
    metadata: dict[str, Any]

    @classmethod
    def load(cls, base_path: str, checkpoint: str, device: str = "cuda") -> "FrozenAR":
        import torch
        import torch.nn as nn
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from .models import prepare_adapter_key_wrappers, verify_adapter_keys
        path = Path(checkpoint)
        state = torch.load(path / "heads.pt", map_location="cpu", weights_only=True)
        cfg = json.loads((path / "meta.json").read_text())["config"]
        if "tag_ids" not in state or "layers" not in state:
            raise ValueError("Expected explicit prompt-tag head state")
        layers = tuple(state["layers"])
        tok = AutoTokenizer.from_pretrained(base_path, local_files_only=True)
        base = AutoModelForCausalLM.from_pretrained(base_path, dtype=torch.bfloat16,
                                                   device_map=device, local_files_only=True).eval()
        inner = None
        for module in base.modules():
            if isinstance(getattr(module, "layers", None), nn.ModuleList) and hasattr(module, "norm"):
                inner = module
                break
        if inner is None:
            raise RuntimeError("Text backbone not found")
        del inner.layers[max(layers) + 1:]
        inner.norm = nn.Identity()  # source AR reads block output, without final RMSNorm
        # Key wrapper helper also handles a direct text-backbone object.
        prepare_adapter_key_wrappers(inner, path / "lora")
        backbone = PeftModel.from_pretrained(inner, str(path / "lora"), is_trainable=False).eval()
        matched = verify_adapter_keys(backbone, path / "lora")
        class Head(nn.Module):
            def __init__(self):
                super().__init__()
                self.linear = nn.Linear(state["head"]["linear.weight"].shape[1],
                                        state["head"]["linear.weight"].shape[0])
            def forward(self, h):
                h = h.float()
                if cfg.get("head_layer_norm", True):
                    h = torch.nn.functional.layer_norm(h, (h.shape[-1],))
                return self.linear(h)
        head = Head().float()
        head.load_state_dict(state["head"], strict=True)
        head = head.to(device).eval()
        return cls(tok, backbone, head, state["tag_ids"].to(device), layers, device,
                   {"matched_adapter_tensors": matched, "head_layer_norm": cfg.get("head_layer_norm", True),
                    "whitener_prefix": cfg["whitener_prefix"], "span_limit": 32, "final_norm": "Identity",
                    "tag_ids_by_layer": state["tag_ids"].tolist()})

    def encode(self, texts: list[str], layer: int) -> tuple[Any, list[dict[str, Any]]]:
        return self.encode_mixed(texts, [layer] * len(texts))

    def encode_mixed(self, texts: list[str], layers: list[int]) -> tuple[Any, list[dict[str, Any]]]:
        import torch
        if not texts or len(texts) != len(layers):
            raise ValueError("Encoding requires aligned nonempty text/layer lists")
        layer_indices = [self.layers.index(layer) for layer in layers]
        prepared = [ar_token_ids(self.tokenizer, text) for text in texts]
        rows = [tokens for _, tokens in prepared]
        if any(not ids for ids in rows):
            raise ValueError("Empty AR text cannot be encoded")
        truncated = [ids[:32] for ids in rows]
        width = max(map(len, truncated))
        ids = torch.zeros((len(rows), width), dtype=torch.long, device=self.device)
        mask = torch.zeros_like(ids)
        for i, row in enumerate(truncated):
            ids[i, :len(row)] = torch.tensor(row, device=self.device)
            mask[i, :len(row)] = 1
        tag = self.tags[torch.tensor(layer_indices, device=self.tags.device)]
        ids, mask = torch.cat((tag, ids), 1), torch.cat((torch.ones_like(tag), mask), 1)
        with torch.inference_mode():
            out = self.backbone(input_ids=ids, attention_mask=mask, use_cache=False)
            last = mask.sum(1) - 1
            hidden = out.last_hidden_state[torch.arange(len(rows), device=self.device), last]
            predictions = self.head(hidden).float().cpu()
        metadata = [{"text": text, "scored_text": cleaned, "input_ids": tokens, "original_token_count": len(original),
                     "scored_token_count": len(tokens), "unscored_suffix_ids": original[32:],
                     "truncated": len(original) > 32, "tag_ids": self.metadata["tag_ids_by_layer"][layer_index],
                     "layer": layer}
                    for text, (cleaned, _), tokens, original, layer_index, layer in
                    zip(texts, prepared, truncated, rows, layer_indices, layers)]
        return predictions, metadata
