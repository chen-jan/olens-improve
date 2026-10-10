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
- The 189-cell N32 pilot is complete: 6,048 distinct saved samples, contiguous indices 0–31 in every cell, no length-truncated generations, and the original 16 instrument samples preserved. Its 53 generation batches took 882.4 GPU-seconds in aggregate. Immutable pilot snapshots are saved before expanding the global journals.
- Candidate encoding completed: 24,186 full-text bullet instances map to 23,750 distinct actual AR inputs; encoding took 323.94 seconds. Exact text, source spans, and scored/unscored token boundaries remain in the cache usage records.
- All four main H200s are expanding the shared pool to the complete 5,236-cell development grid; the numerical batching audit finished before the fourth joined. Validation and test readouts remain sealed. Two additional monitored preemptable H200s handle streaming AR encoding and bounded F/E/G diagnostics.

## Work in progress

| Worker | Responsibility | Owned implementation |
|---|---|---|
| Coordinator | Decisions, integration, status, local Git commits | Project contract, PLAN/STATUS |
| Resource worker | GPU allocation, storage, environment, job monitoring, selectors and sample runner | infra/, runtime config, package setup, selection module |
| Model worker | Released O-lens, matching AR and whitening, real smoke test | Model and reconstruction modules |
| Evaluation worker | Grouped splits, cached-cell provenance, Luna judges, atomic API ledger | Data/evaluation/budget modules |

Agents may inspect development traces after real runs. Held-out outputs remain sealed until the planned final comparison.

## Budget and limits

- Shared ledger at 02:42:51 UTC: actual $0.443410735, outstanding reservations $2.3432909 (including $2.3071494 unknown), committed $2.786701635. Values are a timestamped snapshot; the ledger is authoritative for subsequent updates.
- Existing unresolved Claude review reservation: $2; retain until reconciled.
- API target: $200; hard ceiling including outstanding reservations: $300.
- Maximum shared O-lens samples per cell: 32. Editing has separate explicit limits.
- Aggregate project storage allowance across Pattie compute and data: approximately 500 GB.
- Main generation uses four existing allocations. Diagnostic preemptable job 25459615/node4800 and streaming AR job 25460532/node4601 each provide one H200 under `${SLURM_GENERAL_PARTITION}`/`normal`; both were allocated within 25 seconds. Their current expirations are 22:23:24 and 22:40:24 UTC. Release extras when useful work ends; no further GPU requests are pending.

## Measured resource forecast

At 02:42:51 UTC, 1,618/5,236 development cells had complete N32 prefixes.
The four main GPUs were at 99–100% utilization, about 77,235 MiB each.
Recent four-cell batches took median 16.58–16.91 seconds, or 4.15–4.23
GPU-seconds per cell. Remaining generation projected 1.04–1.19 hours per
shard at that pace; allow roughly 1.2–2 hours for longer sequences and
interruptions. This forecasts generation, not completion of the experiments.

Conditionally sampling all 19,435 core cells would take about 25 GPU-hours
using the earlier representative pilot rate, roughly 6.3 hours on four cards.
Held-out generation still requires the frozen planned gate. Allow a 5–10-hour
generation range before encoding, numerical selection, API judging, editing,
and final audits. Single B32 AR encoding measured about 73 unique vectors/s;
streaming overlap and B64/B128 profiling aim to avoid a long encoding tail.
The API/selection/helper tail is not yet fully forecast and is not folded
into the generation estimate.

Project-owned storage was 10.97 GB across fast and durable roots, well below
the 500 GB aggregate allowance; the actual lab group quota remains unresolved.
Runtime paths, allocation expiry, live GPU observations, budget, generation
status, and claim ages are recorded in the fast `watcher/latest.json`.
Checks run during the active session only; no persistent external agent is
assumed after the session ends.

## Next concrete milestone

Judge the paired 189-cell selection comparisons and inspect wins, regressions, and unchanged examples. Candidate-only semantic helpers have a $2 pilot ceiling. The first audit caught unreliable model-produced character offsets; the repair asks for exact quotations and locates offsets locally, preserving failed paid responses. Verify the repaired helper and audit natural pairs before interpreting consensus gains. The implementation milestone passed 27 tests covering budget, resume, generation metadata, and selector invariants, with temporary files on actual durable storage; newer components have their own targeted checks.

## Recovery

Read PLAN.md, METHODS.md, this status, and the latest experiment records. Inspect live scheduler jobs and actual output manifests before restarting anything. Preserve completed shards, cached samples, paid judge responses, and all outstanding budget reservations. Monitoring is active only while its worker/session runs; do not assume an agent survives a stopped session. Git commits remain local; the user pushes.
