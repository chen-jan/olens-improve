# Blind validation candidate preparation

Status: prepared and preflight checked; no validation generation launched by this worker. This scheduling change uses idle GPUs while development judging finishes. It does not permit validation-informed development or open test.

The coordinator authorized **only blind, fixed N32 O-lens generation**. Pair, carrier, layer/position grids, sampling settings and the shared pool were frozen on development. Preserve all 32 samples per cell, including poor or malformed outputs; do not inspect their text, scores, traces, judge results or dashboard views before the development shortlist and operating settings are frozen. Monitor counts, hashes, memory, latency and process health only. No AR, helper, selector or judge runs are authorized by this gate.

## Frozen inputs and capability boundary

- Cohort: [validation-full-grid-blind-v1.json](../../configs/validation-full-grid-blind-v1.json), SHA256 `9293de810635a5ee69fcee3c010ede25c7e147d12d172c2f637015c64042f19d`.
- Gate: [validation-full-grid-blind-v1.json](../../configs/gates/validation-full-grid-blind-v1.json), SHA256 `c80e0137a18a220af8253610266c3f98aa92370be5b7eefa02f507d3fe6d7e6e`, scope `blind_generation_only`.
- Exactly **3,485 cells / 80 items / 111,520 generations**: hallucination 765 cells, multi-hop MT 220, chain 220, role association 2,280. These are full original grids from frozen split v2.
- Original read-plan SHA256 `3cf1cc9c477d24ad3ecda9eafe947bff947a8afe46a08c2c5a4620f0d49412c9`; fresh adapter-disabled index SHA256 `5a61cff89aca532f3e022233b6d2d8e12dab0d3a3f4f44085097bc6dc58fc385`. Cell identities, related-group keys and split assignments match.
- Append existing pool `e8cfd09f7ff1c9195cfd4c3a`, seed `20261010`, unchanged four hash shards, N32, temperature 1, top-p .95, top-k 64, maximum 256 new tokens. No new pool identity, regeneration or extra samples.

Shared stage validation rejects blind scope for exports, streaming/partitioned AR and selectors. Generation alone requests the generation capability. New records carry `generation_authorization_scope` and the generation-gate SHA without changing the pool configuration. Direct AR encoding rejects those records before loading tokenizer/checkpoint/model unless a separate, verified analysis gate binds their exact cohort and fresh activations. Later analysis consumes the original records unchanged. Legacy development gates retain their previous authorization; unknown scope values fail closed. Test remains sealed, including attempts to reuse blind scope on test.

## Validation and proposed launch

Three focused capability tests passed: blind generation allowed but outcome stages blocked; test still closed; immutable blind records require independent analysis authorization, including direct AR rejection before model work. Six exporter and five streaming regression tests passed. Four generator `--validate-only` checks returned `launch:false`, the unchanged pool ID and shard counts **881 / 847 / 908 / 849**. No model, GPU or API calls were made for these checks.

Root reviews and authorizes the exact source-bound launch. The resource worker verifies ownership, expiry, CPU placement, RAM and empty GPUs immediately beforehand. Existing assignment: shard 0/job 25330001; shard 1/25330006; shard 2/25330007; shard 3/25417596. Use the original production batching, and retain terminal source hashes plus the commit/source hashes recorded by the runner. Do not launch the legacy instrument `pool_worker.py`.

Run the following once per assigned shard after coordinator approval; substitute only the listed job/shard pair and the resource-approved CPU binding:

```bash
JOB_ID=25330001
SHARD_INDEX=0
srun --jobid="$JOB_ID" --overlap --nodes=1 --ntasks=1 \
  --cpus-per-task=8 --mem=64G --cpu-bind=cores \
  /usr/bin/env PYTHONPATH=${OLENS_REPO_ROOT}/src \
  OMP_NUM_THREADS=4 \
  ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python \
  scripts/generate_samples.py \
  --runtime configs/runtime.json \
  --manifest configs/validation-full-grid-blind-v1.json \
  --gate configs/gates/validation-full-grid-blind-v1.json \
  --adapter ${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/models--agu18dec--olens_and_ar/snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/olens_s3d_rl600 \
  --fresh-index ${OLENS_COMPUTE_ROOT}/activations/core-v1/fresh_manifest_v2.json \
  --capture-version fresh-core-v1 \
  --output ${OLENS_DATA_ROOT}/readouts/shared-global-v1 \
  --n 32 --batch-size 32 --cells-per-batch 4 --maximum-batch-sequences 128 \
  --shard-index "$SHARD_INDEX" --shard-count 4 --seed 20261010 \
  --max-new-tokens 256
```

Run from the repository root and save separate validation logs. Generation resumes its existing shard journal and retains earlier development records. A dead worker claim may be recovered only after confirming that its process is absent. Keep development terminal snapshots immutable while global journals append. Paused or preempted workers resume persisted sample indices, never resample.

The measured development reference, 4.33 GPU task-seconds per N32 cell, suggests approximately **63 minutes on four GPUs**, plus startup, unequal shard tails and interruptions. This is a forecast, not a guarantee or measured validation runtime. AR preprocessing is deliberately deferred under this gate. Before any validation analysis, root records the development shortlist/settings freeze and issues a separate `analysis` gate for the same exact manifest and fresh index. That reveal authorizes prespecified validation comparisons; it does not authorize test or an adaptive new pool.
