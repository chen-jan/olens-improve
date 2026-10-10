# Execution status

Started: 2026-10-10 01:25:36 UTC (October 9, 21:25:36 EDT).
Target finish: 2026-10-10 21:25:36 UTC, subject to the first real throughput forecast.

## Current findings

- Execution is authorized; no further routine approvals are needed.
- Real O-lens instrument smoke passed on H200 job 25417596: saved adapter tensors matched, enabling the adapter changed logits (maximum difference 6.375), and merging stayed within the source tolerance (maximum drift 0.125). Two sample texts are saved; these are instrument outputs, not benchmark results.
- The first model load and adapter-free capture took 20.81 seconds; two generated readouts took 9.39 seconds. This tiny run is not a campaign throughput estimate.
- Matching whitening access is resolved after the user accepted the dataset agreement. All 11 matched layer files and the small provenance record downloaded successfully; the subset totals 1,153,666,096 bytes (1.15 GB). No bulk research archive is needed.
- The local whitening and published 80-step fitting math matched 18 synthetic source fixtures (maximum whitening difference zero; maximum FVE difference 1.19e-7).
- Full matched-AR validation subsequently passed: all 992 saved LoRA tensors matched, and the local head predictions agreed exactly with the original prompt-tag class, including five tokenizer edge cases. Independent seeded generation also produced exactly the same two strings as the pinned WorkspaceBench O-lens implementation.
- The first eight-cell sample-0 Luna judging pilot completed in 46 seconds: eight physical responses including preflight, 6,166 input tokens and 617 output tokens, estimated usage cost $0.00046255, no API errors. Median call latency was 7.17 seconds, 95th percentile 10.94 seconds. These tiny partial-grid diagnostics do not establish benchmark performance or a full-run cost estimate.
- Historical cached vectors differed from fresh captures by roughly 0.75–1.59% relative L2 distance and lacked complete provenance. Fresh capture is complete: 19,435 core cells from 469 forwards, 398 MB in the final FP32 tensor. The original eight pilot vectors match exactly. This does not open test readouts for development.
- The main selection solver is now frozen to exact NNLS; the published 80-step approximation is retained as a separate compatibility metric and ablation. See METHODS.md for evidence and limits.
- The alias-safe split manifest is now v2: multi-hop has 31 development / 20 validation / 49 test items; other families are unchanged. Four alias crossings in v1 were repaired before any held-out readouts. Reuse the same captured rows with v2 split/group bindings.
- The primary parser will preserve contiguous dash-bullet blocks, with at most four complete bullets and 256 Qwen text tokens. Keep strict single-line parsing as an ablation and use the same primary parser/cap for the N=1 comparator.
- The pinned base-model cache contains all 15 weight shards (55.56 GB) and was successfully loaded without copying it.
- Four owned H200 allocations and the project runtime are verified; see `configs/runtime.json`. The current host, node3107, is a CPU allocation.
- The four core read plans contain 19,435 cells. Grouped development, validation, and test manifests are frozen. The initial eight-cell N=1/2 instrument is complete; the representative pilot uses 189 cells from 31 development items, explicitly a partial-grid comparison.
- WorkspaceBench remote HEAD was checked during execution and still equals the pinned revision `92d763e722377f5bfae045e829a308ab5919a820`. Its default O-lens points to the same source checkpoint as our paired release.
- The two-pair contrastive diagnostic found correct role-direction ranking on both paired examples, but the numeric scorer preferred the same number across two different answers. A generic role description scored much higher than the detailed descriptions. These are instrument examples, not general performance estimates; see experiment 004.
- All four existing H200s are generating the 189-cell shared N32 pool. Source hashes and batch provenance are recorded. Synthetic throughput improved from 288 to 660 output tokens/second with 128 independent sequences per batch; actual campaign throughput will be measured separately.

## Work in progress

| Worker | Responsibility | Owned implementation |
|---|---|---|
| Coordinator | Decisions, integration, status, local Git commits | Project contract, PLAN/STATUS |
| Resource worker | GPU allocation, storage, environment, job monitoring, selectors and sample runner | infra/, runtime config, package setup, selection module |
| Model worker | Released O-lens, matching AR and whitening, real smoke test | Model and reconstruction modules |
| Evaluation worker | Grouped splits, cached-cell provenance, Luna judges, atomic API ledger | Data/evaluation/budget modules |

Agents may inspect development traces after real runs. Held-out outputs remain sealed until the planned final comparison.

## Budget and limits

- Experimental API usage cost recorded at the first pilot: $0.00046255. The shared ledger is authoritative for subsequent updates.
- Existing unresolved Claude review reservation: $2; retain until reconciled.
- API target: $200; hard ceiling including outstanding reservations: $300.
- Maximum shared O-lens samples per cell: 32. Editing has separate explicit limits.
- Aggregate project storage allowance across Pattie compute and data: approximately 500 GB.
- The model smoke used an existing GPU allocation. No additional GPU allocations or preemptable requests have been made.

## Next concrete milestone

Finish the shared 189-cell N32 pool, encode its candidate bullets once, and compare selection methods on identical cells. Candidate-only semantic-helper prompts have been reviewed; a bounded $2 pilot will check synthetic traps and real candidate pairs before interpreting consensus gains. The current implementation passed 27 tests, including budget, resume, generation metadata, and selector invariants; the tests ran with temporary files on the actual durable storage.

## Recovery

Read PLAN.md, METHODS.md, this status, and the latest experiment records. Inspect live scheduler jobs and actual output manifests before restarting anything. Preserve completed shards, cached samples, paid judge responses, and all outstanding budget reservations. Monitoring is active only while its worker/session runs; do not assume an agent survives a stopped session. Git commits remain local; the user pushes.
