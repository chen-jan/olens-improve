"""Batch independent same-layer cells without combining their information."""

from olens_improve.models import carrier


def sequence_metadata(rows, eos_ids, pad_id, max_new_tokens):
    lengths, reasons, truncated = [], [], []
    for row in rows:
        end = next((index for index, token in enumerate(row) if token in eos_ids), None)
        if end is not None:
            lengths.append(end + 1)
            reasons.append("eos")
            truncated.append(False)
        else:
            end = next((index for index, token in enumerate(row) if token == pad_id), len(row))
            lengths.append(end)
            limited = end >= max_new_tokens
            reasons.append("length" if limited else "other_or_padding")
            truncated.append(limited)
    return {"token_counts": lengths, "sequence_lengths": lengths,
            "finish_reasons": reasons, "truncated": truncated,
            "generated_token_ids": [row[:length] for row, length in zip(rows, lengths)]}


def sample_many(lens, activations, layer, *, n_per_cell=32, seed=0, max_new_tokens=256):
    """Return cell-major samples, with at most 32 samples for each input row.

    RNG consumption changes with batching; callers must persist exact outputs,
    row order, seed, and batch shape. No support votes cross cell boundaries.
    """
    import torch
    if not 1 <= n_per_cell <= 32 or activations.ndim != 2 or activations.shape[1] != 5120:
        raise ValueError("Require rows of width 5120 and 1..32 samples per cell")
    if activations.shape[0] < 1:
        raise ValueError("Empty activation batch")
    ids, slot, marker = carrier(lens.tokenizer, layer)
    vectors = activations.to(lens.device).float()
    norms = vectors.norm(dim=1, keepdim=True)
    if not torch.isfinite(vectors).all() or bool((norms <= 1e-8).any()):
        raise ValueError("Cannot inject nonfinite/near-zero activation")
    torch.manual_seed(seed)
    with torch.inference_mode():
        inputs = torch.tensor([ids] * len(vectors), device=lens.device)
        embeddings = lens.model.get_input_embeddings()(inputs)
        embeddings[:, slot, :] = (16000. * vectors / norms).to(embeddings.dtype)
        out = lens.model.generate(inputs_embeds=embeddings,
            attention_mask=torch.ones(inputs.shape, device=lens.device, dtype=torch.long),
            do_sample=True, temperature=1., top_p=.95, top_k=64,
            max_new_tokens=max_new_tokens, num_return_sequences=n_per_cell,
            pad_token_id=lens.tokenizer.pad_token_id)
    expected = len(vectors) * n_per_cell
    if len(out) != expected:
        raise ValueError("Generator returned an unexpected number of sequences")
    flat_texts = [text.strip() for text in lens.tokenizer.batch_decode(out, skip_special_tokens=True)]
    eos = lens.model.generation_config.eos_token_id
    eos_ids = set(eos if isinstance(eos, (list, tuple)) else [eos])
    if lens.tokenizer.eos_token_id is not None:
        eos_ids.add(lens.tokenizer.eos_token_id)
    metadata = sequence_metadata(out.tolist(), eos_ids, lens.tokenizer.pad_token_id, max_new_tokens)
    metadata.update(carrier_ids=ids, slot=slot, marker_id=marker, seed=seed,
        input_rows=len(vectors), samples_per_cell=n_per_cell, output_order="cell_major",
        temperature=1., top_p=.95, top_k=64, alpha=16000., max_new_tokens=max_new_tokens,
        padded_batch_width=int(out.shape[1]))
    texts = [flat_texts[index*n_per_cell:(index+1)*n_per_cell] for index in range(len(vectors))]
    return texts, metadata
