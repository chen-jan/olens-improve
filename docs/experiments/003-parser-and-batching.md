# Experiment 003: parser controls and bounded batch throughput

Status: completed instrument checks, not a recovery/error result. Updated 2026-10-10 01:54 UTC. Parent: the eight-cell development N=2 instrument pool; no held-out evaluation. Raw baseline remains unchanged.

## Parser policy and controls

The coordinator froze primary `source_contiguous_dash_blocks_v1`: preserve every continuation byte after a dash marker through the next dash marker. Preserve numbers, negation, qualifiers, headers, and explanations inside a source block. Flag substantive preamble before the first bullet as uncertain. `strict_single_line_v1` remains a separate parser ablation. No helper rewriting or compound-claim splitting is applied.

Proposed final readouts have at most four complete source bullets and at most 256 tokens under the frozen Qwen tokenizer, matching the raw generation limit. Deterministic capped N=1 drops trailing complete bullets until both constraints fit, never slicing within a bullet. All selection additions/fallbacks must use the same token-count/compatibility callback. Report the raw, same-cap N=1, and parser-ablation controls; parsing-induced abstention cannot count as a semantic improvement. Compound claims are preserved and their counts audited separately.

Readback on the 16 persisted instrument samples, counted with the frozen Qwen tokenizer:

| Parser | Uncertain samples | Samples capped to four bullets | Samples requiring token capping |
|---|---:|---:|---:|
| Source-contiguous dash blocks | 0/16 | 1/16 | 0/16 |
| Strict single lines | 6/16 | 2/16 | 0/16 |

Strict uncertainty by family: hallucination 1/2, multi-hop MT 0/4, chain 2/6, role-bound 3/4. Every primary sample has retained source provenance. This is a small format audit, not evidence of improved factual recovery. Twelve selector tests pass, including preservation of a negation-bearing continuation and complete-bullet token capping.

## Batch profiling

One existing H200 allocation, job25330007/node3301, ran synthetic activation vectors at layer44 with the frozen base/O-lens carrier, alpha16000 normalization, temperature1, top-p.95, top-k64, and 256 maximum new tokens. Seven distinct synthetic rows produced 224 persisted outputs; no extra core read cells were sampled. Each row received at most32 samples. In the multirow cases, each independent row retains its own injected activation; no observations or votes are combined across cells.

| Output sequences | Seconds | Generated tokens | Tokens/second | Peak allocated GPU memory, decimal GB |
|---|---:|---:|---:|---:|
| 32 from one row | 11.876 | 3423 | 288.22 | 59.97 |
| 64 from two rows | 13.876 | 6850 | 493.66 | 66.09 |
| 128 from four rows | 19.319 | 12745 | 659.72 | 78.34 |

All224 sequences stopped by EOS, none hit the token cap. First-case timing includes first-generation warmup. Synthetic vectors are off distribution; these timings establish batching feasibility, not real-benchmark throughput or quality. Calibrate the completion forecast on the representative189-cell shared pilot.

Artifacts: `${OLENS_COMPUTE_ROOT}/runs/synthetic_batch_profile_v1/{single_hf32,two_cells64,four_cells128,summary}.json`. Commands/code: `scripts/benchmark_sampling.py`, `src/olens_improve/sampling.py`. No paid APIs or new allocations were used.

## Resume and promotion decision

Use the existing four main allocations first. The production runner groups independent same-layer cells at the same persisted prefix, up to four rows/128 total sequences per batch, with no more than32 per cell. Immutable global pool identity includes frozen model/decode/seed/capture-version/four-shard settings; stage manifests, gates, and batch sizes are logged separately. First two outputs from the original instrument cells are imported unchanged only after exact FP32 activation-hash agreement; expansion appends indexes2..31. Journal batches are flushed/fsynced, progress manifests updated atomically, and complete sample records never regenerated. Uncommitted crash-tail loss is explicitly logged as unknown lost compute.

Production generation remains gated on the exact stage manifest, fresh-capture version, and coordinator authorization. Any test cell also requires frozen-test authorization. Five offline resume/state tests and one sequence-termination metadata test pass; no production pilot was launched by this record. Decision: prepare the representative N=32 shared pool once capture and the coordinator's gate are ready.

Environment limitation: this run's project-owned environment reuses historical lens site-packages read-only via a `.pth` overlay. Observed versions are recorded in `configs/runtime.json`; this is a working reuse setup, not a standalone dependency installation recipe. Portable dependency groups/snapshot can be finalized after the first representative pilot.
