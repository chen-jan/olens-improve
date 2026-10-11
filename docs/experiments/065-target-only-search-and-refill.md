# Experiment 065 — Repeat swaps and refill using only the current activation

## Key findings for a new reader

All four new selectors ran on the full four-bank cohort: 469 questions and 19,435 sites. Repeated swaps change 12.05% of site texts and add 0.0177 percentage points of reconstruction on average over plain pooling. Role recovery rises from 81 to 84/100, with unresolved adjusted uncertainty. Prune-and-refill adds bullets at only 1.26% of sites and adds 0.0238 reconstruction points over plain pruning. Guided and count-matched random deletion have almost identical measured contradiction rates. The [report](../TARGET_ONLY_REPORT.md) separates these observed endpoints from factual faithfulness.

## Status and question

- **Status:** complete; public version 20, with [publication receipt](../reviews/target-only-site-delivery-v1.json).
- **Date (UTC):** 2026-10-11.
- **Run / parent:** `target-only-search-v1` / frozen `expansion-v1` plain-pooling references.
- **Question:** Can repeated swaps or bounded prune/refill improve the existing combined readout without accessing another activation or generating new text?
- **Failure modes:** tiny local reconstruction gains; loss of exact names, numbers or relations; rewards for shortening; benchmark judge sensitivity.
- **Decision:** no general quality improvement established. Preserve the measured role gains and uncertainty; do not promote reconstruction gains alone as faithfulness evidence.

## Frozen inputs and procedure

The additive plan is [TARGET_ONLY_SEARCH_PLAN.md](../TARGET_ONLY_SEARCH_PLAN.md). Production inventory [target_only_inventory_v2.json](../../configs/target_only_inventory_v2.json) has SHA256 `181fcc259ed81213a7b26ea18142b6cd35648e89b83100a5cf07590ed75b2c47`; v1 remains an unjudged timing-pilot record. Model, matching AR, whitening, tokenizer, own N=32 sample pool and read cells are inherited unchanged from the earlier frozen capture. Full source identities and hashes are in the inventory, terminal descriptors and native analysis.

| WorkspaceBench family | Questions | Sites | Related-example groups |
|---|---:|---:|---:|
| Hallucination (chat) | 149 | 5,615 | 149 |
| Multihop (multi-token) | 100 | 1,100 | 94 |
| Chained intermediates | 120 | 1,320 | 42 |
| Role-bound association | 100 | 11,400 | 50 |

Selection receives exactly one own activation, its existing samples, matched frozen phrase vectors and tokenizer. Prompt, labels, other activations and control banks are inaccessible to selection. Administrative IDs route inputs and deterministic seeds. Outputs contain at most four verbatim bullets and 256 Qwen tokens. The original raw released-lens reference is cap-exempt.

The menu is repeated swaps; the same refined parent followed by leave-one-out pruning; bounded prune/refill from plain pooling; and deterministic random deletion with the guided method's per-cell retained bullet count. Search uses exact nonnegative reconstruction, 2,048 distinct subset fits, eight accepted swaps, two refill rounds and a fixed 0.005 contribution threshold plus numerical tolerance. The swap arms share the same 2,034-fit search phase and 14-fit terminal-pruning reserve. Prune/refill has a constrained objective and permits fewer than four bullets. It is a scaffold comparison, not a pure optimization-efficiency intervention.

Standard GPT-6 Luna, effort `none`, uses the original frozen prompts, parsers and both Hallucination stages. Multihop runs the released offline deterministic rule with API transport forbidden. Source-bound forecast and root dispatch receipt authorize $30 within the existing $340 project ceiling. Exact request caching, 256 concurrency per family and batched ledger reservations are retained; no Flex route or replacement judge is introduced.

## Comparisons and measurements

The final analysis contains 40 complete records: six original references plus four additions, each on all four families. Eleven declared pairs across the four native endpoints give 44 simultaneous contrasts. The frozen bootstrap uses 10,000 whole-group draws and seed 20261012, retaining pairing. Forty contrasts have nondegenerate simultaneous intervals; four preserve zero-variation warnings. All banks were previously inspected, so these are exploratory results. Historical adaptive choices, supplementary comparisons and secondary counts lie outside this new adjustment.

The [report](../TARGET_ONLY_REPORT.md) gives every count and denominator. Repeated-swaps parent-relative role change is +3 points with adjusted interval −2.39 to +8.39. Guided versus random deletion changes measured contradiction by −0.022 points with interval −1.39 to +1.34. Prune/refill's role gain over old plain pruning is +3 points with interval −2.34 to +8.34. No general upgrade is established.

The behavior supplement compares actual emitted text and actual parents, excluding discarded preparatory trace actions. It reports per-family and overall text changes, bullet/token distributions, fitted-score changes, truncation and stop flags. Four new final methods remain distinct from raw original, capped original, best-of-32 and earlier plain-pool deletion controls.

## Trace audit and qualitative findings

Three reviewers inspected disjoint partitions totaling 64 selected case entries: 14 repeated-swaps, 34 guided/random deletion and 16 refill. Cases include wins, regressions, question-level witnesses and seeded unchanged examples; absent categories are explicit. They are illustrative, not frequency estimates. Exact source texts, contexts, native verdict evidence and differences are retained.

Reviews show bridge-name recovery, lost complete names and directional relations, and incorrect calculations containing the required number. Some apparent Hallucination improvements retain the precise quote flagged in the parent. Some role/number losses reflect extraction changes despite surviving content. Official scores remain intact and these limitations are exposed. The reconstructor's first-32-token bullet scoring is also reported separately from complete-text judging.

Receipts: [numerical run](../reviews/target-only-run-review-v1.json), [statistics](../reviews/target-only-statistics-audit-v1.md), [judging](../reviews/target-only-judging-run-v1.json), [swaps](../reviews/target-only-qual-repeat-v1.json), [pruning/random](../reviews/target-only-qual-prune-random-v1.json), [refill](../reviews/target-only-qual-refill-v1.json), [resources](../reviews/target-only-resource-audit-v1.json), and [root results](../reviews/target-only-root-results-v1.json).

## Cost, time, storage and delivery

New API usage estimate: $2.0292, versus $2.0265 forecast; global usage $144.7578 with $5.0685 retained holds. Judging wall time was 195.018 seconds and all 16 new units have zero missing required verdicts. No new GPU or model encoding was used.

Selection finished 56 minutes after its initial launch, including a corrected shared-core placement error and a SIGKILL interruption whose cause is unconfirmed. Committed rows were resumed without changing scientific arguments. Selection process CPU accounting is approximately 7.10 hours; pilot and ancillary steps are reported separately. The inherited user allocation was preserved. Summed overlapping step reservations are not exclusive billing or active CPU utilization.

The dated follow-up footprint is 2.5466 GB logical / 0.7225 GB allocated blocks. The scoped project footprint is 125.9208 / 95.1468 GB, excluding external shared weights. Large outputs live under `${OLENS_DATA_ROOT}/target-only-search-v1`; code and compact receipts are local research commits. Historical artifacts remain intact. See [delivery](../TARGET_ONLY_DELIVERY.md) for the dashboard, 12-slide supplement and downloadable records.
