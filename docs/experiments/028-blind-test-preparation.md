# 028: Prospective blind test candidate preparation

Status: capability implementation and synthetic guards prepared for coordinator and independent review. No real test gate, preprocessing command or generation has been authorized or executed by this record. Test outcomes remain sealed.

The original policy deferred test generation until the final method freeze. The coordinator proposes a narrow scheduling revision: after the twelve-arm validation menu is frozen and validation AR work finishes, decode the already fixed common test pool while validation judging runs. This may remove approximately three hours of decoding from the critical path; it is a forecast, not a measured test runtime. It does not change any method, data, source layer/position, sampling setting, candidate budget or decision rule. [The validation freeze](027-validation-shortlist-freeze.md) retains its historical sealed-test status; this record documents the prospective revision separately.

Only `authorization_scope: blind_generation_only` can use this capability. **Both** the exact test manifest and its source-bound gate must explicitly contain `blind_test_generation_authorized: true` and `frozen_test_authorized: false`. Missing, mismatched or nonboolean flags fail closed. The manifest/gate must still bind the existing fresh adapter-disabled captures, exact homogeneous test cells and related groups, 10,714 authorized cells, passed recapture, production authorization and maximum N32. The generator also requires exactly N32, seed 20261010, four original hash shards and sampling batch size 32 / four cells per batch / maximum 128 sequences. The batch grouping affects seeded generation, so alternative grouping is rejected. Frozen Qwen/pair, carrier, T1/top-p .95/top-k64/256-new-token decoding and the existing global pool identity remain unchanged.

Blind preparation permits generation counts, hashes, process/resource health and timing only. Do not inspect test readout text, AR vectors/scores, selected outputs, per-readout lengths or termination patterns, quality, labels, traces, helper results or dashboard views. No AR, selection, export or judging is allowed under this gate. All current analysis entrypoints still reject its scope; the standalone portable tool rejects blind-marked records. Existing validation/development gates and test rejection without the new paired flags remain intact.

After validation, root freezes at most two final settings plus their prespecified comparators, component/shortening controls and judge recipe. Root then issues a separate exact analysis manifest/gate with `frozen_test_authorized: true`, binding that final freeze and the same original cells/capture hashes. This later authority consumes immutable blind-generated records without regeneration, removing their provenance, or looking at test results to select an operating point. A failed or interrupted generator resumes its persisted sample indices. Blind test preparation rejects external `--import-pool`; persisted target test rows must retain blind-generation scope and a valid nonempty generation-gate hash before any loader runs. Unrelated historical development/validation rows remain untouched. Sealed output storage and source hashes must survive a paused chat.

Implementation changes only `ar_partition.py`'s generation-capability check and `generate_samples.py`'s preparation checks/launch metadata. Partition keys, batching, AR math, parser and selection methods are unchanged. Seven focused capability tests and seven partition-contract tests pass. Synthetic checks cover paired flags and explicit false analysis authorization; unchanged old test rejection; generator validate-only with no pool created; wrong N/seed/shard/batch recipe and external-import rejection; resume provenance with unchanged unrelated history; analysis/export/stream/selector rejection; and later final authorization accepting an unchanged blind record. These checks involve no real test readouts, GPU work or API calls.

After root approves an immutable test manifest/gate, run **validate-only** for each original shard using the existing runtime and verified paths. This example is prepared only; the named real manifest/gate do not yet exist:

```bash
${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B scripts/generate_samples.py \
  --runtime configs/runtime.json \
  --manifest configs/test-full-grid-blind-v1.json \
  --gate configs/gates/test-full-grid-blind-v1.json \
  --adapter ${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/models--agu18dec--olens_and_ar/snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/olens_s3d_rl600 \
  --fresh-index ${OLENS_COMPUTE_ROOT}/activations/core-v1/fresh_manifest_v2.json \
  --capture-version fresh-core-v1 \
  --output ${OLENS_DATA_ROOT}/readouts/shared-global-v1 \
  --n 32 --seed 20261010 --shard-count 4 --shard-index 0 \
  --batch-size 32 --cells-per-batch 4 --maximum-batch-sequences 128 \
  --max-new-tokens 256 --validate-only
```

Repeat only shard indices 1–3. Root reviews all four unchanged pool IDs, expected cell counts and source hashes before a separate GPU launch decision. Resource ownership, allocation expiry, memory and idle GPU checks remain mandatory. Neither this document nor validate-only starts generation, opens test analysis, or authorizes paid calls.
