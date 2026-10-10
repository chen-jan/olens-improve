# 001: Frozen model and reconstruction instrument setup

Status: real GPU instrument checks completed; core benchmark evaluation has not completed. Execution began 2026-10-10 UTC (2026-10-09 local). No paid model API calls were made by this experiment.

The question is whether the frozen released O-lens and its exact reconstructor can be loaded faithfully, and whether existing activation caches are sufficiently documented for reuse. Scientific claims about improved readouts require subsequent experiments.

## Frozen identities and source

- Base `Qwen/Qwen3.6-27B`, revision `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`, reused read-only from the existing scratch cache. No base download or copy.
- [Paired release](https://huggingface.co/agu18dec/olens_and_ar/tree/c95215d5d2f6250f20c305ae55c6e4d7569f92dc), revision `c95215d5d2f6250f20c305ae55c6e4d7569f92dc`: `olens_s3d_rl600` and `ar_ptag_pooled`. Only these adapters/metadata were fetched.
- WorkspaceBench source revision `92d763e722377f5bfae045e829a308ab5919a820`; its default O-lens source path points to `ckpts/ao/rl/s3d.ddp600.s0/iter_000600`.
- [Original inference source](https://github.com/agu18dec/olens_draft/tree/a32590085a6070d75f950155d3c2b3db3eec97ef): `${OLENS_COMPUTE_ROOT}/repos/olens_draft`, revision `a32590085a6070d75f950155d3c2b3db3eec97ef`. Source-file hashes are stored in fixture JSONs. Inspect `core/whitening.py`, `core/nnomp.py`, `pipeline/ar_loader.py`, `pipeline/multilayer_reconstructor.py`, `pipeline/scorer.py`, and `readout_text.py`.
- [Matching pooled moments](https://huggingface.co/datasets/agu18dec/local-workspace/tree/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners), dataset revision `5653a7fead43ecbd87e3b6d2a2990a98b32843ca`. Eleven `whitening_iolens_pooled_L{20,24,...,60}.safetensors` files, each 104,878,736 bytes; total 1,153,666,096 bytes. Also fetched the small pooled-provenance JSON. No activation archives or other whitening variants.

Artifact access initially returned unauthenticated 401, then authenticated 403 using the existing cached credential without exposing it. After the user accepted the dataset agreement, the exact artifacts downloaded successfully. This blocker is resolved.

The AR's pinned metadata identifies `whitener_prefix=whitening_iolens_pooled`, `ridge_c=.1`, `head_mode=prompt_tag`, and a shared LayerNorm/linear head. Moments metadata names `Qwen/Qwen3.6-27B`, the source layer, and the same prefix. Pooled provenance reports 2,088,997 samples: 1,048,298 chat and 1,040,699 pretraining samples; covariance includes between-group scatter, with source commit `76ec9581`. The layer-44 artifact SHA256 is `178ceb36251e5e7ed2eb51aa54ccc4eac45dc928116b7498b46d22657a31c62a`.

## Implementation and verified checks

`src/olens_improve/models.py` loads the text causal model, handles checkpoint `_orig_mod` paths using transparent structural wrappers, verifies every saved adapter tensor against the loaded value, and checks adapter-on versus adapter-off logits. Raw capture hooks decoder-block outputs and disables the adapter. Merging is followed by the original source's maximum-logit-drift check, with tolerance .5. Generation uses the exact `concepts_raw` carrier, marker selected inside the full chat render, `16000*h/||h||`, temperature 1, top-p .95, top-k 64, maximum 256 tokens. Capture after merging is prohibited.

The ad-hoc Paris instrument on H200 allocation `25417596` passed: maximum adapter logit change 6.375, merge drift .125, layer-44 final-token norm 83.502, marker token 158983. Load/capture took 20.8 seconds and N2 generation 9.39 seconds. `scripts/compare_sampler.py` independently executes the pinned WorkspaceBench `OLens` class with the same activation/seed/settings: carrier IDs, injection slot, and both generated strings matched exactly. This supports loader fidelity; it does not establish readout quality.

`src/olens_improve/reconstruction.py` implements the prompt-tag AR without importing training infrastructure. The loaded head has twelve explicit layer tags: 20–60 step four and 63. It reads the final real token from the text backbone with its final norm replaced by identity, applies the saved shared non-affine LayerNorm/linear head, and returns raw predicted activations.

`scripts/ar_smoke.py`, on H200 allocation `25330001`, verified all 992 saved AR adapter tensors, compared predictions with the actual upstream `PromptTagReconstructor` class using the saved head/tags, and obtained maximum prediction difference zero. Disabling the AR adapter changed predictions by up to 63.697. Five bare-tokenization fixtures cover ordinary text, scaffolding/special markers, Chinese, and long text.

The published whitening is `(x-mu)@W.T`, with `W=(sym(cov)+lambda*I)^(-1/2)`, `lambda=.1*mean(diag(cov))` floored at `1e-12`; eigendecomposition is FP64, negative eigenvalues clamp to zero, and W becomes FP32. Both predictions and targets are centered/whitened; phrase predictions become unit directions, while the target retains its magnitude. Joint FVE is `1-residual_squared_norm/target_squared_norm`, denominator floor `1e-12`, without score clipping.

The source NNLS uses 80 projected-gradient iterations with step size `1/trace(Gram)`, rather than an exact constrained solver. `scripts/reconstruction_check.py` compared 18 synthetic source fixtures: whitening matrices matched exactly; maximum FVE difference was `1.19e-7`. On the sixteen real instrument candidates, exact SciPy NNLS improved FVE by at most .000552; no N2 winner changed across eight cells. Total fit time was .0124 seconds for source80 versus .00525 for exact, on this tiny sample. Keep solver settings explicit; this does not prove equivalence on larger, correlated pools.

The coordinator froze exact SciPy NNLS for main A/C/D selection and primary joint-fit reporting; the released80 solver remains an explicitly labeled compatibility metric and same-pool numerical ablation. Judge only changed selected outputs. Exact fits support monotonic subset comparisons; do not compare the exact score directly to the card's .487 training-reward result. Recheck ranking differences when a larger pool exists.

**AR span limitation:** source reward tokenization removes scaffolding/special IDs, then truncates to 32 tokens per phrase. Encoding records retain original/scored token counts, encoded IDs, and the unscored suffix. FVE cannot validate details beyond that span. Preserve emitted readout text and judge its full content; do not silently truncate the scientific output or imply the suffix was reconstructed.

## Eight-cell development instrument

Frozen manifest: `configs/splits_pilot_instrument_v1.json`, eight actual development cells across all four families, all layer 44. This is a partial-grid instrument, not official item-level recovery. Exact rendered token IDs and selected-token spelling were checked for captured hallucination inputs, plain multi-hop, chat chain prompts, and role-summary prompts.

Fresh adapter-free vectors were used for generation. Against historical cached vectors, cosine similarities ranged .999885–.999977 and relative L2 errors .00747–.01592. Historical revision/adapter provenance remains incomplete. The coordinator chose fresh capture for all core items; closeness does not establish byte-identical compatibility.

The shared N2 pool contains sixteen raw outputs. Preserve samples 0/1 and their fresh activation bytes when expanding each cell's shared pool; never regenerate a fresh32 pool for these cells. Qualitative inspection finds mixed languages, repeated/compound bullets, invented bridge names, wrong numerical claims, and role narratives about restaurants instead of the comedy-club context. These are baseline failure traces, not an improvement verdict. The independent upstream generation match rules out a straightforward carrier/sampling discrepancy, but judged baseline results remain pending.

Per-sequence generation metadata now locates the first EOS, includes that sampled token in counts, records finish reasons and truncation independently, and keeps padded batch width separate. Original instrument pools have older count metadata; their batch widths were below 256, so none was length-truncated. Future outputs retain generated token IDs for auditing.

## Artifacts, continuation, and limits

All large/new artifacts live under `${OLENS_COMPUTE_ROOT}`:

- `logs/model_smoke.json`, `logs/sampler_comparison.json`, and `logs/ar_smoke.json`: model/source guards and real-score evidence.
- `runs/instrument_n2_v1/{activations.safetensors,capture_audit.json,candidates.jsonl,run.json}`: ordered fresh vectors, exact rendering, fixed shared texts, sampling provenance.
- `runs/instrument_n2_v1/ar_phrase_vectors.safetensors` and its index: reusable exact-text layer-44 raw AR predictions, tokenization/truncation provenance.
- `logs/reconstruction_check.json`: persisted small mathematical-source fixture.

Next: grouped fresh adapter-free capture using `scripts/capture_cells.py`; preserve the existing eight FP32 vectors exactly, store all rendering hashes and cell-to-row references, then judge the current development baseline before sampling expansion. Capture of sealed test activations is allowed; test readouts, labels, and selection decisions remain sealed until the plan's freeze. Remaining work includes full-grid capture, broader AR stability/batching checks, early negation/number/binding diagnostic, baseline judging, and development method pilots. No benchmark improvement or completed scientific comparison is claimed here.

Update: full-core fresh capture completed: 19,435 FP32 vectors from 469 grouped forwards, 398,029,080 bytes in the final tensor. The original eight vectors were verified exactly equal. Artifacts are `activations/core-v1/{activations.safetensors,capture_audit.json,fresh_manifest_v2.json}`. Corrected v2 split/group metadata was bound by identical cell IDs and capture-spec hashes without recapturing; capture provenance retains its original manifest hash. [004-contrastive-diagnostic.md](004-contrastive-diagnostic.md) records the initial isolated number/relation diagnostic. Baseline judging and method comparisons remain separate unfinished work.
