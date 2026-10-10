# Completing the fixed-method descriptive comparison

Status: prepared for root review; no new judging, cache scan or ledger query. The fixed twelve methods remain unchanged. Completing the remaining DEV results would provide a descriptive appendix across 469 source items: 121 DEV, 80 VAL and 268 TEST. The 268-item TEST comparison remains separate and is the held-out result. Pooling the three stages does not create 469 held-out observations.

## Remaining DEV work

The metadata receipt `.state/dev12-coverage-verified-v1.json` verifies 37 of 48 fixed-method family contracts. All twelve multihop and chain conditions are complete. Five hallucination conditions and six role conditions remain. Their exact source outputs already exist; no additional candidate generation, AR encoding, selector search or method tuning is required.

| Family | Exact remaining methods in original DEV dispatch order | Required handoff |
| --- | --- | --- |
| Role | Emean matched deletion .005; pooled bullets N16; pooled bullets N32; A32 pruning .005; A32 matched deletion .005; random complete N32 | All twelve TEST role contracts complete, worker absent and role cache owner released |
| Hallucination | Pooled bullets N16; pooled bullets N32; A32 pruning .005; A32 matched deletion .005; random complete N32 | All twelve TEST hallucination contracts complete, both judge stages complete, worker absent and hallucination cache owner released |

These are ordered subsets of the original DEV24 menu. The descriptive report will use the fixed twelve-method VAL/TEST display order. Preserve every existing complete DEV contract and artifact; dispatch only the missing eleven family conditions. If a condition becomes complete before handoff, prepare a smaller reviewed subset instead of replaying it.

Prepared menus and specs:

- `configs/conditions_dev12_remaining_role_v1.json`
- `configs/judging_dev12_remaining_role_v1.prepared.json`
- `configs/conditions_dev12_remaining_hall_v1.json`
- `configs/judging_dev12_remaining_hall_v1.prepared.json`

Both specs retain `development-full-grid-methods-v1`, its $20 run ceiling, original 07:52 UTC recovery epoch, all uncertain holds, the authoritative ledger, exact request/cache identity, Standard with no reasoning, fixed concurrency 8 and 200 requests/minute. They have prepared status and no current resource binding, so the existing launcher refuses paid dispatch until root seals them. No new health call, epoch reset or concurrency ramp is included.

Role DEV may overlap remaining TEST hallucination once TEST role releases its family cache. Hallucination DEV waits for TEST hallucination. Final clean TEST analysis and the deck have priority; late DEV results cannot change operating points or the fixed menu. Review the prepared CPU successor at 19:00 UTC, before the current hold ends at 21:25:37. A successor must use the same ledger and a clean family-boundary operational rebind.

## Forecast at the family boundary

Only after a TEST family finishes and releases its cache should root authorize an exact cache-aware forecast for that family's prepared subset. Keep the original DEV run and global headroom/unknown holds in the accounting review. Do not sum formal maximum-output reservations as expected cost.

The old immutable DEV forecast is a workload reference, not current cache state. Its original-order increments for these missing methods were 3,647 new hallucination first-stage requests plus at most 3,647 second-stage requests, and 14,863 role requests. A no-cache logical ceiling is 5,725 plus at most 5,725 hallucination calls and 20,520 role calls. Historical mean-service/rate references suggest roughly 45–71 minutes for hallucination and 74–111 minutes for role before cached-row IO, barriers, retries and incidents. Actual cache reuse may reduce these counts. This is not a completion guarantee or a current usage/invoice quote.

## Minimal descriptive analysis plan

1. Bind immutable completed results for each stage to its exact cohort, source readouts, fixed twelve-method identity/order and analysis artifact hashes. Reuse the 37 complete DEV contracts byte-for-byte; add only the eleven completed contracts. Require zero missing API verdicts, complete hallucination stages for produced nonempty readouts, and explicit abstention counts. An upstream whole-bank `complete` flag does not replace project coverage checks.
2. Verify the stage item/cell identities are disjoint and their union equals the intended 469 items and 19,435 read cells (DEV 5,236; VAL 3,485; TEST 10,714), with each item's original layer/read-position grid intact. Check related-group membership before pooling; do not silently split a related group between bootstrap units.
3. Preserve TEST and VAL tables and supplied paired comparisons separately. Add a clearly labeled descriptive whole-cohort table for the identical twelve methods, with each family shown separately. Hallucination uses contradiction/specific-readout counts and also assertion/consistent coverage; multihop/chain recovery and role task passes use their intended denominators. Preserve empty outputs, errors and other classes explicitly. Do not introduce a hidden cross-family average.
4. Compute pooled values from source numerators and denominators, not means of stage percentages or stage intervals. If pooled uncertainty is requested, use the existing related-group paired bootstrap on the complete union, with supplied stage/group provenance and a descriptive interpretation. Keep cell endpoints distinct from original-item endpoints (items with any passing site); mentions, role passes and ANY-grid success do not establish full-output faithfulness.
5. Retain exact output lengths, source/condition hashes, stage scopes and missingness. Attach only root-reviewed findings; do not select a new winner or settings from the late DEV appendix. Research campaign, cached selector replay, fresh-input effort and benchmark-judge charges stay separate; unavailable fresh latency/GPU dollars remain unavailable.

The source review for this preparation validated exact subset order, frozen membership, current implementation hashes and historical health/incident/index/copied-load evidence using the existing resume wrapper's source-only functions. No production DB connection, live cache inspection, paid dispatch or TEST outcome access occurred.
