# TEST analysis preparation after the final freeze

Status: commands and schema only. No final-method freeze or TEST analysis gate has been issued by this record. Blind TEST generation is separately authorized and monitored in [experiment 028 execution](028-blind-test-execution.md). No TEST samples, lengths, verdicts, vectors or scores were read to prepare this note. Generation-only authority cannot be reused below.

## Required final authority

After the prespecified validation comparisons, root records the final method, comparators, operating settings and endpoints in a new immutable freeze. The final menu remains unresolved here. A new TEST analysis manifest must preserve the exact ordered 10,714 original cells / 268 items and their family, item, group, layer, position and capture identities, while explicitly setting `frozen_test_authorized: true`. The original blind manifest and gate stay unchanged. The new gate must have `authorization_scope: analysis`, true frozen TEST authorization, passed captures, N32 maximum and exact manifest/fresh hashes. It must bind `freeze_path`/`freeze_sha256` and `condition_list_path`/`condition_list_sha256` to the reviewed final freeze and exact signed menu. The reporting freeze schema requires `status: root_reviewed_frozen`, `conditions_sha256` and the same ordered `conditions` list. This preparation creates none of these authorities.

Unchanged blind records retain their original generation scope/gate and samples 0–31. Later analysis verifies the same cell and activation identities; it does not regenerate, remove blind provenance or introduce additional sites. Donors remain the fixed DEV control bank. TEST judgments cannot choose a new threshold, N, layer or displayed operating point.

## Reuse sequence

Run allocated work from the repository root only after the separate final analysis gate exists. The following planned filenames are placeholders, **not existing permissions**:

Before preparation, reacquire a scoped `${SLURM_CPU_PARTITION}` CPU allocation using account `${SLURM_CPU_ACCOUNT}`: **16 physical CPU cores (`nomultithread`), 80 GiB RAM**, initially four hours for freezing, preparation, merges and four selector workers, then reforecast the actual remaining need. The previous VAL CPU allocation is released. Preparation is one process, bound to four physical cores with numerical threads capped at four; it simultaneously retains the approximately 1.06-million-key inherited catalog, pending new keys, source snapshot and usage metadata. After verifying the assigned topology/cpuset, use explicit `taskset` masks: four disjoint four-core masks for selectors within the shared 80 GiB limit. TEST peak memory is unmeasured: watch RSS/cgroup headroom, and reduce concurrent workers if needed rather than changing math or precision. No CPU request or launch is made by this note; confirm allocation and masks with the resource owner.

```bash
PY=${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python
POOL=${OLENS_DATA_ROOT}/readouts/shared-global-v1
COHORT=configs/test-full-grid-analysis-v1.json
GATE=configs/gates/test-analysis-v1.json
FREEZE=configs/test_final_method_freeze_v1.json
MENU=configs/conditions_test_final_v1.json
FRESH=${OLENS_COMPUTE_ROOT}/activations/core-v1/fresh_manifest_v2.json
RUN=${OLENS_DATA_ROOT}/runs/test-full-grid-v1
OLD=${OLENS_COMPUTE_ROOT}/vectors/validation-catalog-v1
PARTS=${OLENS_COMPUTE_ROOT}/vectors/test-partitions-v1
CAT=${OLENS_COMPUTE_ROOT}/vectors/test-catalog-v1
AR=${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/models--agu18dec--olens_and_ar/snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/ar_ptag_pooled
CONTROLS=${OLENS_DATA_ROOT}/manifests/development-matched-controls-v2-metadata-v1.json
WHITENERS=${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners
SEL=${OLENS_DATA_ROOT}/selections/test-full-grid-v1
```

1. Require all four generation workers terminal, exact shard counts 2,716 / 2,689 / 2,711 / 2,598 and correct journal hashes. Freeze the complete source before further global append:

   ```bash
   "$PY" scripts/freeze_pool.py --pool "$POOL" --manifest "$COHORT" \
     --fresh-manifest "$FRESH" --gate "$GATE" --output "$RUN" \
     --original-instrument ${OLENS_COMPUTE_ROOT}/runs/instrument_n2_v1/candidates.jsonl
   "$PY" scripts/partition_ar.py prepare --input "$RUN/samples-n32.jsonl" \
     --manifest "$COHORT" --fresh-manifest "$FRESH" --gate "$GATE" \
     --inherited "$OLD" --count 4 --checkpoint "$AR" --output "$PARTS/prepared"
   ```

   Preserve terminal parent hashes, exact TEST-only flat coverage and explicit zero instrument overlap. The preparation binds the final analysis manifests and source hashes, while retaining original blind records unchanged.

2. Encode each disjoint effective-key partition on one assigned H200: `partition_ar.py encode --plan "$PARTS/prepared/plan.json" --index 0 --checkpoint "$AR" --output "$PARTS/worker-0"`, likewise indexes 1–3. Use explicit allocated resources and approved physical CPU masks. B128 and four hash partitions remain fixed; record actual key order and inherited first-computed rows. After all workers terminate:

   ```bash
   "$PY" scripts/partition_ar.py merge --plan "$PARTS/prepared/plan.json" \
     --worker-cache "$PARTS/worker-0/a451cf49d28ac7447722" \
     --worker-cache "$PARTS/worker-1/a451cf49d28ac7447722" \
     --worker-cache "$PARTS/worker-2/a451cf49d28ac7447722" \
     --worker-cache "$PARTS/worker-3/a451cf49d28ac7447722" --output "$CAT"
   ```

3. Reuse the stage-gated selector with the immutable flat input, `$CAT`, `$FRESH`, `$WHITENERS`, `$CONTROLS`, `$COHORT` and `$GATE`, exactly as [the validation sequence](025-blind-validation-preparation.md) describes. Four CPU shards remain non-overlapping. Merge with the exact cohort, then run only frozen combination wrappers and export exactly `$MENU` using `export_judging_inputs.py` with fresh/gate and all parent source SHAs. Do not expose any unscheduled computed conditions.

4. Forecast and reserve judging costs before dispatching the unchanged Luna benchmark judge. After every signed condition has all four families complete, run the gated reporter:

   ```bash
   "$PY" scripts/analyze_signed_menu.py --manifest "$COHORT" \
     --conditions "$MENU" --condition-list "$MENU" --freeze "$FREEZE" \
     --fresh-manifest "$FRESH" --gate "$GATE" --judgments "$RUN/judgments" \
     --selections "$RUN/judging-inputs.jsonl" --selection-sha256 EXACT_EXPORT_SHA \
     --output "$RUN/final-analysis-v1.json"
   ```

   Root supplies actual reviewed paths/hashes; `EXACT_EXPORT_SHA` is deliberately unresolved. Metrics retain separate family denominators and whole-related-group intervals. Sampled audit contexts are evaluation-only, not selector/helper inputs.

## Catalog compatibility and phase forecast

`partition_ar.prepare` uses `read_cache`, which accepts a standard contract and indexes pointing to external tensors; it does not require tensors inside the inherited directory. VAL's completed zero-copy catalog has 1,063,925 vectors over 262 referenced shards (`catalog.json` SHA256 `e3516d204c2a1d1d03149e4087e44d37b94323633343c6abc26e54ef6ad09bba`). Inheriting it preserves both DEV and VAL first-computed rows and their execution provenance. A new bounded synthetic test chains two zero-copy merges and verifies inherited row identity, exact coverage and no tensor copies. Keep all canonical referenced shards; catalog deletion/relocation must not break pointers.

VAL encoded 421,716 new keys over 3,485 cells at **95.28 vectors/second/GPU**, using summed recorded worker time including startup. Applying that key density to 10,714 TEST cells forecasts approximately **1.30 million new keys and 57 minutes on four H200s**. The capped pool offers at most 1,371,392 bullet inputs before cleanup/deduplication/inherited hits, bounding new FP32 raw vectors at approximately **28.09 GB** before index/usage metadata. Actual key counts and family composition may differ; no TEST text was inspected for this estimate. VAL selector workers took 590–608 seconds for 3,485 cells on four four-core workers; a similar full-menu TEST pass projects approximately **31 minutes**, before combinations, merges and reporting. Freeze/preparation and provider-dependent judging are additional; there is no measured end-to-end completion promise. Reforecast after authorized preparation, and report batching sensitivity rather than B32 equivalence.

For final cost reporting, cached replay is distinct from a new activation's generation, AR encoding and CPU selection. The prepared `scripts/deployment_timing.py` uses the same fixed synthetic library prompt as experiment 026, a single new N32 pool, an isolated new phrase cache and the installed portable tool. Two offline checks passed for frozen profile/control requirements and transparent timing wrappers. No GPU run has launched, and no final profiles have been supplied.

After validation selects the final profiles, root can assign an idle main GPU after its TEST generation or AR worker exits; the timing check must not delay the four-way TEST AR work. Measure model initialization, adapter-off capture, warm N32 generation, fresh AR loading/encoding and subsequent cached replays separately. Nested timings overlap and must not be added together. CUDA peaks are cumulative across this engineering run. Cold refers to model initialization in this process; filesystem caches are not flushed. Prefix replays do not measure actual smaller-N generation latency. Specificity requires an explicit frozen same-layer calibration manifest and matching policy. Use no extra allocation or judge/API, and exclude this input from all benchmark results. The earlier N2 lifecycle and amortized DEV throughput describe different regimes.


## Prepared dispatch and generation completion (11:52 UTC)

`infra/launch_test_judges.py` now supports the final variable-length, ordered
TEST menu with exact source/export/forecast hashes and the reviewed fixed
Luna 8-concurrency/200-RPM policy. Six synthetic guard tests passed independently
under root, and a second agent reviewed the source. `OLENS_TEST_FROZEN=1` reaches
the child only after final analysis permission, ready/paid flags, allocation,
CPU placement and fresh profile checks. No production TEST specification or
analysis permission was created and no TEST API call was dispatched.

Generation metadata v25 records all 10,714 cells complete (SHA256
`30f500f0a6dcb8aef0e6eb61af811d161130348b35df46214c12855de77f0d35`).
The independent resource receipt at
`${OLENS_DATA_ROOT}/diagnostics/test-generation-terminal-resource-v1/receipt.json`
(SHA256 `3b4761130fe43e75927befc35dfa0c1413ce3689253239a194b21897a5958d8d`)
shows absent generation wrappers, no generation steps, and idle retained GPUs.
This establishes preparation completion; held-out scientific scoring remains pending.


At 12:01 UTC, CPU allocation `25489638` is running on `node1607`, with
16 verified physical cores, 80 GiB memory and expiry 15:56:40 UTC. Root verified
four disjoint masks: `0,25,26,38`; `39,40,41,42`; `43,45,46,68`; `69,70,71,74`.
Use an allocation-wide `srun -c16 --cpu-bind=none` and the explicit mask for
each worker. The immutable resource receipt is
`durable/diagnostics/test-cpu-allocation-v1.json` (SHA256
`394a44d7ae4b9995bb6b4dd92f7e2f11ac99b4d046c7a9f80ca9379c4457708c`).
The existing watcher now includes this allocation. No TEST analysis launched.

## Execution after final freeze

The final six-arm menu and analysis gate were sealed in local commit `9544e96`.
The original blind files remain unchanged. On CPU allocation 25489638,
`freeze_pool.py` and `partition_ar.py prepare` both exited 0. The pool contains
exactly 10,714 cells and 342,848 samples, with zero original-instrument overlap.
Snapshot SHA: `9bebdb516e3435206c56a423356fad82f09cdde04aced212a7d7d214f66a55dc`;
flat samples SHA: `a9ac1a66d819a2da0a551e40f9b49b309a62aefb767071d7f866e84e36f61c6d`.

Preparation took 227.69 seconds, with 11,562,716 KiB maximum process RSS.
The resource observer measured 15.06 GiB peak for the whole 80-GiB allocation
and no memory-limit failures. The final plan contains 1,294,737 new keys split
323,234 / 323,679 / 323,944 / 323,880, using the frozen batch size 128.
Plan SHA: `b950bb00d23cb884987faf2f83be874250f16d8f0c3746d87c47895d3bde6629`.

All four encoding steps were launched by 12:44 UTC on the retained H200 jobs.
Their tool sessions are 47306, 32936, 36308 and 8980 for indices 0–3. Logs are
`fast/logs/test-ar-worker-{index}-v1.log`; outputs are
`fast/vectors/test-partitions-v1/worker-{index}`. These are running steps,
not terminal encodings. Require all four successful exits and exact planned
key coverage before catalog merge and selection.
