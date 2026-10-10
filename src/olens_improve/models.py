"""Frozen Oracle Lens loader and adapter-free decoder-output capture.

The carrier/capture contract is copied from pinned WorkspaceBench, while adapter
key guards follow the original olens_suite loader. No network calls happen here.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE_REVISION = "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
PAIR_REVISION = "c95215d5d2f6250f20c305ae55c6e4d7569f92dc"
SUPPORTED_LAYERS = tuple(range(20, 61, 4))
CARRIER = (
    "An activation vector from layer {layer} of a language model is enclosed in activation "
    "tags: <activation>{char}</activation>. Produce distinct concepts that encode this "
    "activation, each as a '- ' bullet on its own line."
)


def resolve_blocks(model: Any) -> Any:
    for path in ("layers", "model.layers", "model.language_model.layers", "base_model.model.model.layers"):
        obj = model
        try:
            for part in path.split("."):
                obj = getattr(obj, part)
            return obj
        except AttributeError:
            pass
    raise AttributeError("No supported decoder block path")


def carrier(tokenizer: Any, layer: int) -> tuple[list[int], int, int]:
    if layer not in SUPPORTED_LAYERS:
        raise ValueError(f"Layer {layer} is outside the frozen O-lens contract")
    for code in range(0x3200, 0x3400):
        char = chr(code)
        isolated = tokenizer(char, add_special_tokens=False)["input_ids"]
        if len(isolated) != 1:
            continue
        result = tokenizer.apply_chat_template(
            [{"role": "user", "content": CARRIER.format(layer=layer, char=char)}],
            tokenize=True, add_generation_prompt=True, enable_thinking=False,
        )
        ids = list(result if isinstance(result, list) else result["input_ids"])
        slots = [i for i, token in enumerate(ids) if token == isolated[0]]
        if len(slots) == 1:
            return ids, slots[0], isolated[0]
    raise ValueError("No single-token marker survives the full carrier")


def prepare_adapter_key_wrappers(base: Any, adapter_path: Path) -> bool:
    """Preserve compiled checkpoint module names without compiling GPU graphs.

    torch.compile's _orig_mod wrapper changes state-dict paths, not the intended
    forward operation. This transparent wrapper is verified by the logit guard.
    """
    import torch.nn as nn
    from safetensors import safe_open
    with safe_open(str(adapter_path / "adapter_model.safetensors"), framework="pt") as f:
        needed = any("_orig_mod." in key for key in f.keys())
    if needed:
        class OriginalModule(nn.Module):
            def __init__(self, original: Any):
                super().__init__()
                self._orig_mod = original

            def forward(self, *args: Any, **kwargs: Any) -> Any:
                return self._orig_mod(*args, **kwargs)

        blocks = resolve_blocks(base)
        for i in range(len(blocks)):
            blocks[i] = OriginalModule(blocks[i])
    return needed


def verify_adapter_keys(model: Any, adapter_path: Path) -> int:
    from safetensors import safe_open
    def stem(key: str) -> str:
        return key.split("base_model.model.")[-1].replace(".default", "")
    live = {stem(k): v for k, v in model.named_parameters() if "lora_" in k}
    with safe_open(str(adapter_path / "adapter_model.safetensors"), framework="pt") as f:
        saved = {stem(k): f.get_tensor(k) for k in f.keys() if "lora_" in k}
    missing = set(saved) - set(live)
    if missing:
        raise RuntimeError(f"Adapter tensor keys missing: {len(missing)}/{len(saved)}")
    # Names alone do not prove weights landed. Check every tensor after dtype casting.
    for key, tensor in saved.items():
        value = live[key].detach().cpu()
        if not value.equal(tensor.to(value.dtype)):
            raise RuntimeError(f"Loaded adapter tensor differs: {key}")
    return len(saved)


@dataclass
class FrozenOLens:
    tokenizer: Any
    model: Any
    device: str
    probe_ids: Any
    on_logits: Any
    adapter_delta: float
    merged: bool = False

    @classmethod
    def load(cls, base_path: str, adapter_path: str, device: str = "cuda") -> "FrozenOLens":
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(base_path, local_files_only=True)
        tok.padding_side = "left"
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        base = AutoModelForCausalLM.from_pretrained(
            base_path, dtype=torch.bfloat16, device_map=device, local_files_only=True,
        ).eval()
        text_config = getattr(base.config, "text_config", base.config)
        if len(resolve_blocks(base)) != 64 or text_config.hidden_size != 5120:
            raise ValueError("Unexpected frozen base architecture")
        prepare_adapter_key_wrappers(base, Path(adapter_path))
        model = PeftModel.from_pretrained(base, adapter_path, is_trainable=False).eval()
        verify_adapter_keys(model, Path(adapter_path))
        ids = tok("The capital of France is", return_tensors="pt").input_ids.to(device)
        with torch.inference_mode():
            on = model(ids, use_cache=False).logits[0, -1].float()
            with model.disable_adapter():
                off = model(ids, use_cache=False).logits[0, -1].float()
        delta = float((on - off).abs().max())
        if not delta >= 1e-3:
            raise RuntimeError(f"Inert adapter: maximum logit delta={delta}")
        return cls(tok, model, device, ids, on, delta)

    def capture(self, ids: list[int], layers: list[int], positions: list[int]) -> dict[int, Any]:
        import torch
        if self.merged:
            raise RuntimeError("Cannot capture adapter-free activations after merge")
        if any(p < 0 or p >= len(ids) for p in positions):
            raise ValueError("Capture position out of range")
        outputs, handles = {}, []
        def hook(layer: int):
            def save(_module: Any, _args: Any, out: Any) -> None:
                h = out[0] if isinstance(out, tuple) else out
                outputs[layer] = h[0, positions, :].detach().float().cpu()
            return save
        try:
            blocks = resolve_blocks(self.model)
            for layer in layers:
                if layer not in SUPPORTED_LAYERS:
                    raise ValueError(f"Off-contract layer {layer}")
                handles.append(blocks[layer].register_forward_hook(hook(layer)))
            with torch.inference_mode(), self.model.disable_adapter():
                self.model(torch.tensor([ids], device=self.device), use_cache=False, logits_to_keep=1)
        finally:
            for handle in handles:
                handle.remove()
        return outputs

    def merge(self) -> float:
        import torch
        if self.merged:
            raise RuntimeError("Already merged")
        merged = self.model.merge_and_unload().eval()
        blocks = resolve_blocks(merged)
        for i in range(len(blocks)):
            if hasattr(blocks[i], "_orig_mod"):
                blocks[i] = blocks[i]._orig_mod
        with torch.inference_mode():
            logits = merged(self.probe_ids, use_cache=False).logits[0, -1].float()
        drift = float((logits - self.on_logits).abs().max())
        if not drift <= 0.5:
            raise RuntimeError(f"Merge drift {drift} exceeds source tolerance 0.5")
        self.model, self.merged = merged, True
        return drift

    def sample(self, activation: Any, layer: int, *, n: int = 1, seed: int = 0,
               max_new_tokens: int = 256) -> tuple[list[str], dict[str, Any]]:
        import torch
        if not 1 <= n <= 32:
            raise ValueError("Shared workflow permits at most 32 samples per cell")
        ids, slot, marker = carrier(self.tokenizer, layer)
        v = activation.to(self.device).float().reshape(-1)
        norm = v.norm()
        if not torch.isfinite(v).all() or float(norm) <= 1e-8:
            raise ValueError("Cannot inject nonfinite/near-zero activation")
        torch.manual_seed(seed)
        with torch.inference_mode():
            e = self.model.get_input_embeddings()(torch.tensor([ids], device=self.device))
            e[0, slot, :] = (16000.0 * v / norm).to(e.dtype)
            out = self.model.generate(
                inputs_embeds=e, attention_mask=torch.ones((1, len(ids)), device=self.device,
                dtype=torch.long), do_sample=True, temperature=1.0, top_p=0.95, top_k=64,
                max_new_tokens=max_new_tokens, num_return_sequences=n,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        texts = [s.strip() for s in self.tokenizer.batch_decode(out, skip_special_tokens=True)]
        eos = self.model.generation_config.eos_token_id
        eos_ids = set(eos if isinstance(eos, (tuple, list)) else [eos])
        if self.tokenizer.eos_token_id is not None:
            eos_ids.add(self.tokenizer.eos_token_id)
        from .sampling import sequence_metadata
        meta = sequence_metadata(out.tolist(), eos_ids, self.tokenizer.pad_token_id, max_new_tokens)
        meta.update(carrier_ids=ids, slot=slot, marker_id=marker,
                    padded_batch_width=int(out.shape[1]),
                    raw_sequence_lengths=[len(row) for row in out], seed=seed,
                    temperature=1.0, top_p=0.95, top_k=64,
                    max_new_tokens=max_new_tokens, alpha=16000.0)
        return texts, meta
