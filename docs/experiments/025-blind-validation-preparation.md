# Blind validation candidate preparation

Status: blind N32 generation, the immutable validation snapshot, all four B128 AR workers, the read-only catalog merge, selectors, pruning and exact twelve-condition export are complete. All four validation judge queues have started; their results and review are tracked in [experiment 029](029-validation-comparison.md). The original blind launch was reviewed at `4aa8bc1` (root session `63693`); its scheduling boundary and signed gate remain preserved below. TEST analysis remains closed; the later prospective generation-only policy is recorded separately in [experiment 028](028-blind-test-preparation.md).

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

## Recorded launch and deferred analysis sequence

At **2026-10-10 06:43:11 UTC**, current validation statuses were running at **20/881, 12/847, 12/908 and 20/849** cells. Earlier shard 1/2 status files were still development terminal records while models loaded; those counts were not mistaken for validation progress. Startup logs showed no detected traceback or runtime-error category. No candidate text or quality was inspected. The immutable metadata-only sidecar is `durable/runs/validation-blind-preparation-v1/startup-observation-v1.json`, SHA256 `62156b38862ecf16d506601168eea4550e2d36285b6b140d44e3c1dcaaadd7f4`; it binds job/shard IDs, source hashes, log-prefix hashes and observed statuses. It records launch confirmation from root, rather than inventing exact Slurm step start times. The signed blind gate remains unchanged.

The following sequence was initially **prepared without analysis authorization**. Root subsequently recorded the development shortlist, thresholds, solver, batching, endpoints and decision rule in the immutable [validation freeze](027-validation-shortlist-freeze.md), then issued a **new** `configs/gates/validation-analysis-v1.json` with `authorization_scope: analysis`, identical cohort/fresh hashes, 3,485 authorized cells, sample maximum 32, passed recapture and production authorization. Its freeze path/hash binds the decision evidence. `frozen_test_authorized` remains false. The old blind gate and all source records remain unchanged; their blind provenance fields are not removed. Executed steps are recorded at the end of this document.

Run allocated work from the repository root. These shell variables name the separately authorized analysis inputs and stage output locations:

```bash
PY=${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python
POOL=${OLENS_DATA_ROOT}/readouts/shared-global-v1
COHORT=configs/validation-full-grid-blind-v1.json
GATE=configs/gates/validation-analysis-v1.json
FRESH=${OLENS_COMPUTE_ROOT}/activations/core-v1/fresh_manifest_v2.json
VAL=${OLENS_DATA_ROOT}/runs/validation-full-grid-v1
AR=${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/models--agu18dec--olens_and_ar/snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/ar_ptag_pooled
OLD=${OLENS_COMPUTE_ROOT}/vectors/shared-global-v1/a451cf49d28ac7447722
PARTS=${OLENS_COMPUTE_ROOT}/vectors/validation-partitions-v1
CAT=${OLENS_COMPUTE_ROOT}/vectors/validation-catalog-v1
CONTROLS=${OLENS_DATA_ROOT}/manifests/development-matched-controls-v2-metadata-v1.json
WHITENERS=${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners
```

1. **Freeze terminal generation before any further global append.** Require all four validation statuses complete, their journal hashes correct, and counts exactly 881/847/908/849. On the existing allocated CPU job:

   ```bash
   "$PY" scripts/freeze_pool.py --pool "$POOL" --manifest "$COHORT" \
     --fresh-manifest "$FRESH" --gate "$GATE" --output "$VAL" \
     --original-instrument ${OLENS_COMPUTE_ROOT}/runs/instrument_n2_v1/candidates.jsonl
   ```

   This creates source-bound terminal journals plus `samples-n32.jsonl` for validation only; cumulative development records remain provenance, not extra validation observations. Original instrument overlap must be recorded as zero, not silently skipped. No test append is permitted yet.

2. **Choose exactly one AR path after the analysis gate.** For faster terminal processing on available GPUs, prepare four disjoint effective-key partitions on allocated CPU resources:

   ```bash
   "$PY" scripts/partition_ar.py prepare --input "$VAL/samples-n32.jsonl" \
     --manifest "$COHORT" --fresh-manifest "$FRESH" --gate "$GATE" \
     --inherited "$OLD" --count 4 --checkpoint "$AR" --output "$PARTS/prepared"
   ```

   Run `partition_ar.py encode --plan "$PARTS/prepared/plan.json" --index 0 --checkpoint "$AR" --output "$PARTS/worker-0"` on one assigned H200, and likewise indexes 1–3 on separate assigned H200s. Each uses frozen B128, its own writer/cache root and the plan's exact key order. No source sample is regenerated. After all four workers terminate, CPU merge validates exact disjoint coverage and preserves every inherited first-computed row:

   ```bash
   "$PY" scripts/partition_ar.py merge --plan "$PARTS/prepared/plan.json" \
     --worker-cache "$PARTS/worker-0/a451cf49d28ac7447722" \
     --worker-cache "$PARTS/worker-1/a451cf49d28ac7447722" \
     --worker-cache "$PARTS/worker-2/a451cf49d28ac7447722" \
     --worker-cache "$PARTS/worker-3/a451cf49d28ac7447722" --output "$CAT"
   ```

   Alternatively use **one** `stream_ar.py` writer on an assigned H200: `--pool "$POOL" --cells-manifest "$COHORT" --fresh-manifest "$FRESH" --gate "$GATE" --checkpoint "$AR" --output ${OLENS_COMPUTE_ROOT}/vectors/shared-global-v1 --snapshots ${OLENS_COMPUTE_ROOT}/vectors/validation-stream-v1 --batch-size 128`. It preserves development metadata evidence before cache additions and snapshots only complete N32 validation cells. A later-issued analysis gate can permit streaming while unfinished generation continues, but blind scope cannot. Do not combine a stream writer with terminal partition preparation over a changing inherited cache. Declare the path and partition/batch order before scoring; retain the documented batch sensitivity rather than claiming B32 equivalence.

3. **Select using the frozen pool, controls and math.** Once the chosen AR path is terminal, run four non-overlapping allocated CPU workers with `compare_selectors.py --input "$VAL/samples-n32.jsonl" --cache-directory "$CAT" --fresh-manifest "$FRESH" --whitener-directory "$WHITENERS" --controls-manifest "$CONTROLS" --pilot-manifest "$COHORT" --gate "$GATE" --shard-count 4 --shard-index 0 --output ${OLENS_DATA_ROOT}/selections/validation-full-grid-v1/shard-0`, repeating indexes/output names 1–3. For the stream alternative, substitute its completed cache directory for `$CAT`. Reserve distinct physical CPU cores, four threads and adequate RAM per worker. The existing script computes its frozen offline menu; only prespecified shortlisted conditions may be revealed/judged or inform validation choice. Missing controls fail preflight, and donors remain frozen development cells. Merge with `merge_selection_shards.py` using the exact cohort and four terminal directories; freeze the merged SHA.

   ```bash
   SEL=${OLENS_DATA_ROOT}/selections/validation-full-grid-v1
   "$PY" scripts/merge_selection_shards.py --manifest "$COHORT" \
     --shard "$SEL/shard-0" --shard "$SEL/shard-1" \
     --shard "$SEL/shard-2" --shard "$SEL/shard-3" --output "$SEL/merged"
   ```

4. **Reveal and judge only the signed validation shortlist.** Export the chosen conditions verbatim, verify raw/capped N1 identity and all-cell coverage, and forecast new judge calls against the central ledger before dispatch. Retain separate provisional validation outcomes. Test authorization requires its own later freeze/gate; this sequence creates no test permission.

   Wrapper gaps found during preparation have now been closed with the shared analysis validator: `export_judging_inputs.py` accepts `--fresh-manifest "$FRESH" --gate "$GATE"`; `combine_pruning.py` accepts `--gate "$GATE"` alongside its existing exact cohort/fresh arguments. If shortlisted, the E1 combination invocation uses `--selectors "$SEL/merged/selections.jsonl" --manifest "$COHORT" --fresh-manifest "$FRESH" --gate "$GATE" --production-cache "$CAT" --whitener-directory "$WHITENERS" --parent-method best_n_specificity_mean --output "$SEL/e1-pruning"`. Thresholds, seeds and pruning math remain unchanged; export/judge only the prespecified settings and their matched-deletion controls.

   The evaluation API/CLI also now requires `--fresh-manifest "$FRESH" --gate "$GATE"` for validation/test. It validates before reading selected text, opening the budget ledger or transport, loading credentials, or starting family workers. Blind or missing gates fail closed; a new analysis gate permits exact unchanged blind-generated records. Gated condition metadata binds fresh/gate hashes; legacy development condition identity and judge prompts are unchanged.

   Checks: four synthetic wrapper tests cover DEV export bytes, duplicate-parent exactness, valid VAL/TEST gates, wrong activations, and identical DEV/VAL pruning math/seed. Thirteen evaluation tests cover stage rejection before text/payment, successful synthetic analysis, existing cache/transport and queue behavior; six combination-parent regressions passed. One existing DEV raw/capped N1 projection is byte-identical to the committed `4aa8bc1` exporter (`/tmp/olens-wrapper-dev-replay-v1/result.json`, output SHA256 `c149ea7260e9f5db0c1e84e0d90d760928663427ad74e62b48374906da2223f3`). The five-condition synthetic DEV pruning/deletion outputs also match that legacy wrapper exactly on text, fits, traces, atoms and seeds; implementation/spec hashes intentionally differ (`combine-equivalence.json` in the same temporary directory). These were offline checks, not VAL quality results; later execution is distinguished below.

## Source-bound analysis execution

Root froze the twelve prespecified conditions before revealing validation outcomes. The final freeze SHA256 is `30daad423ee9326971f5f08fa4f3a3e7eec37c857b3757a700a8fcbb3a7547e6`; condition-list SHA256 is `bed944371e050eff7898d07fe0a2ccb39a49a3359779640525b06c4904aca82a`. The new analysis gate SHA256 is `9ba4b92cbfa9f6a0400aa74b65cbf59d8614791efb2c5b404265a0ea455b88f8`, binding this freeze, the existing cohort/fresh hashes and only validation analysis. Independent shared-validator checks confirmed 3,485 matching cells/groups, adapter-disabled captures and false test authorization. The inference contract records exact SciPy NNLS, the fixed mean-control bank, .005 per sequential pruning deletion, B128/four disjoint key partitions and retained historical first-computed DEV vectors, with batch-sensitivity limits disclosed.

`freeze_pool.py` completed with exit zero in root session `71105`, using CPU resources in job `25330001`. Its immutable output is `${OLENS_DATA_ROOT}/runs/validation-full-grid-v1`: **3,485 cells / 111,520 samples**, terminal parent counts **881 / 847 / 908 / 849**, and original-instrument overlap explicitly **zero**. `samples-n32.jsonl` SHA256 is `9854b1b1afaa78ecb6cd1c1144a0990ecf569c86c4b81f1321641e6d01bf8024`; `snapshot.json` SHA256 is `9a97463f8176fedff6835da83b803096c0d2aa6f15197d2c5b433415ff85a319`. The snapshot and flat metadata bind exact source journals, gate, cohort, fresh captures and pool identity; cumulative development rows do not become validation observations.

Root then started the documented four-way `partition_ar.py prepare` step in session `40609` on job `25330001`, reading that immutable flat snapshot and the completed inherited DEV cache. Its output target is `${OLENS_COMPUTE_ROOT}/vectors/validation-partitions-v1/prepared`. At that checkpoint, `plan.json` was not yet present and preparation was in progress; no four-worker encode, catalog merge, selector or judge completion was claimed. This worker inspected metadata/hashes only. Root retained the four prepared H200 allocations for the terminal plan's separate B128 writers.

Subsequent launch record: preparation completed with `plan.json` SHA256 `b59fb883e6dbc13b956222cad1d8b7935fb8e5e380991aff0f64e2d65bc9f943`. It freezes **421,716 new effective-input keys**, partition counts **105,466 / 105,789 / 105,615 / 104,846**, and **445,649 original-bullet usage rows**, including inherited-key hits and explicitly unscoreable atoms. Partition order, gate/cohort/fresh hashes, inherited catalogs and B128 match the reviewed contract. Root launched all four encoders around 08:07 UTC: partition 0/session `57370`/job `25330001`; 1/`84878`/`25330006`; 2/`60951`/`25330007`; 3/`64293`/`25417596`. Each owns `fast/vectors/validation-partitions-v1/worker-{index}` and writes `fast/logs/validation-ar-v1-partition-{index}.log`, using the resource-verified four physical CPU cores per H200.

At **2026-10-10 08:12:21 UTC**, metadata-only progress showed **20,480 / 16,384 / 16,384 / 16,384** completed new vectors, all statuses running. All four loaders had finished; checkpoint/log inspection showed no detected traceback. Startup-inclusive rates were approximately 75–90 vectors/second/worker; the first two workers' successive checkpoints gave approximately 98 vectors/second excluding startup. The remaining encoding tail was forecast at roughly **15–20 minutes**, conditional on similar batches and no interruption, before separate catalog merge and selector work. This is not a completion claim or validation quality result. Preserve terminal vector/run hashes before merge; no test work was launched.

The four AR sessions subsequently exited zero. Exact terminal counts are **105,466 / 105,789 / 105,615 / 104,846**, totaling **421,716 new vectors**; recorded worker wall times are **1,093.573 / 1,111.824 / 1,129.482 / 1,091.130 seconds**. The immutable metadata-only completion sidecar is `durable/runs/validation-full-grid-v1/ar-workers-terminal-v1.json`, SHA256 `41ec5b45efe30634315ee601c7bcdac2ccd0beaaf50f4a211c9d4a0da9ab0065`. It binds each progress/contract/run metadata hash and the prepared source-code hashes, cohort, fresh captures and analysis gate; it contains no vector or candidate text.

Root's catalog merge, session `99563` on CPU allocation `25481193`, completed with exit zero: **1,063,925 vectors = 642,209 inherited DEV + 421,716 new VAL**, with zero vector copies. The catalog points to unchanged first-computed rows; batching sensitivity remains as recorded in experiment 018. Root then launched four disjoint selector workers on that CPU allocation: sessions **7455 / 32073 / 39259 / 13811**, intended cohort counts **872 / 871 / 871 / 871**. Outputs use `durable/selections/validation-full-grid-v1/shard-{index}`. These are launch/completion metadata for infrastructure, not validation outcome evidence; no unshortlisted results were inspected for this update.
