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

For final cost reporting, cached replay is distinct from a new activation's generation, AR encoding and CPU selection. After the final profiles are chosen and TEST AR releases a main GPU, a possible small timing check uses one new off-benchmark engineering input and one shared pool up to N32, evaluating the chosen profiles and nested prefixes on that pool. Measure cold lifecycle, warm generation/new-vector encoding, CPU selection, then separately cached replay; record control-bank inputs explicitly if specificity is required. Use no extra allocation or judge/API, and exclude this input from all benchmark results. This is a proposal, not an implemented or authorized timing run; the earlier N2 cold smoke and amortized DEV throughput describe different regimes.
