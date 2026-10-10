# 038 — Expand held-out comparisons before TEST judging

**Status:** prospective amendment independently reviewed and sealed by root at 2026-10-10T14:16:56.633100+00:00. Exact export, forecast and paid dispatch remain pending. **Recorded:** 2026-10-10 14:12:09 UTC. No TEST judgments, quality summaries or human inspection of selector scores informed this amendment. This is a comparison-design revision, not a result.

The user challenged an aggressive shortlist based on twenty VAL items per family. Those items represent only seven related groups for numerical chains and ten for role binding. The observed regressions support caution, but cannot establish that all excluded variants are worse. Preserve the original six primary comparisons and the two VAL-selected operating points, A16 and unpruned mean specificity N32. Add the remaining six already frozen VAL variants as secondary TEST comparisons, without tuning their settings.

| Status | Comparisons |
|---|---|
| Original primary six | Raw N1, capped N1, best-of-16, best-of-32, random complete N32, mean specificity N32 |
| Added secondary six | Pooling N16/N32; mean specificity then pruning .005 and its matched random deletion; best-of-32 then pruning .005 and its matched random deletion |

All twelve identities are exactly those in the signed VAL menu. This amendment does not cover every variant, add B/F/G helper runs, or establish that the seven approach families have been conclusively ranked. Their existing pilot results and instrument limitations remain reportable. Additional TEST scaling settings require a separate prospective decision; A2/A4/A8 are not added here.

## Authority and unchanged inputs

The new files are `configs/conditions_test_final_v2.json`, `configs/test_final_method_freeze_v2.json`, `configs/test-full-grid-analysis-v2.json` and `configs/gates/test-analysis-v2.json`. Every v1 authority file and the original blind-generation manifest/gate remain unchanged and hash-bound. The reviewed v2 gate authorizes only the fixed comparison preparation and analysis. It does not launch paid judging; the exact export, cost forecast and operational specification remain required.

Fixed N32 generation and AR preparation already completed; the unchanged selector workers are running under v1 authority. Their mechanically computed broader menu is not quality evidence used to choose secondary arms. Preserve their source hashes and existing first-computed vectors. Consume the terminal artifacts under the new sealed export authority, with the same ordered 10,714 cells, 268 items, source samples, seed, capture sites, whitening, exact NNLS, output caps and DEV-only controls. No regeneration, donor redraw or batch-protocol change is needed.

Pruning retains the original .005 maximum FVE loss **per sequential deletion**, not a cumulative .005 bound. The mean-specificity parent is selected with the unchanged specificity objective; its subsequent pruning uses target joint FVE. The A32 and Emean random controls retain their original cell-specific seed formulas and exactly the corresponding pruned bullet count. No full or partial claim rewriting occurs. The freeze binds the existing selector and combination implementations.

## Prepared execution sequence

The freeze and gate are sealed. Require all four existing selector shards terminal, then merge with the original v1 analysis manifest, whose hash matches the running producers. Audit that merged cohort/source before consuming it under the v2 export authority. Then, on allocated CPU resources, derive only the Emean pruning source with the unchanged implementation:

```bash
python scripts/combine_pruning.py \
  --selectors ${OLENS_DATA_ROOT}/selections/test-full-grid-v1/merged/selections.jsonl \
  --manifest configs/test-full-grid-analysis-v2.json \
  --fresh-manifest ${OLENS_COMPUTE_ROOT}/activations/core-v1/fresh_manifest_v2.json \
  --gate configs/gates/test-analysis-v2.json \
  --production-cache ${OLENS_COMPUTE_ROOT}/vectors/test-catalog-v1 \
  --whitener-directory ${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners \
  --parent-method best_n_specificity_mean \
  --output ${OLENS_DATA_ROOT}/selections/test-full-grid-e1-pruning-v2
```

Use the project runtime and a reviewed CPU mask. The existing script also computes its fixed .001 variants; these are mechanical byproducts, not additional authorized comparisons. Its repeated Emean parent must match the original text/counts exactly. A32 pruning and random deletion already come from the unchanged selector source.

Run `scripts/export_judging_inputs.py` with the merged selector source first, the completed Emean-pruning source second, both actual terminal SHAs, the v2 manifest/gate and `conditions_test_final_v2.json`. Write a new immutable export and provenance under `runs/test-full-grid-comparison-v2/`; preserve all earlier artifacts. The exporter supports multiple complete parent sources and checks exact text/count equality for repeated parents, fresh activation identity, signed dispatch order and full coverage. The launcher accepts a variable distinct menu size; no six-arm constant needs changing. Its operational spec must bind this v2 export, menu, freeze, gate and exact forecast.

Forecast with `scripts/forecast_judging.py` before paid dispatch, including shared exact-request reuse and the conditional hallucination stage2 bound. Before cache reuse, the added six have at most 83,280 first-attempt logical calls: 34,200 role, 44,460 across both hallucination stages, and 4,620 chain; MT is regex-only. Physical retries can increase this count. This is an operational upper count, not an empirical cost or latency estimate. Preserve all held charges and current financial caps. Fixed Standard Luna/none/8 slots/200 RPM and one cache owner per family remain required. Root reviews actual wall-time feasibility and a bounded run ceiling separately; this amendment authorizes no paid call.

## Interpretation and review

Report all twelve arms with fixed primary/secondary labels, four-family item and cell endpoints, grouped uncertainty, stage2 coverage, assertion/off-topic rates, output lengths, and per-arm inference effort. Contrast each pruning variant with its parent and matched deletion, and pooling with same-N complete selection. Cache reuse in this campaign is distinct from fresh-input deployment cost. Recovering a mention or intermediate amid incompatible statements is not full explanation faithfulness.

Secondary intervals are descriptive and unadjusted for multiple comparisons. Positive secondary evidence does not independently validate a TEST-selected deployment winner or change the two operating points. Do not retune, hide unfavorable arms, or report missing outputs as successful abstentions. Prioritize the original primary comparisons and protect approximately two hours for final review; if secondary completion is infeasible, retain explicit incomplete status. Independent review checks original-file preservation, exact signed identities, unchanged cell/source contracts, pruning/seeds, inactive draft authority and exporter/launcher compatibility before root sealing.
