# Experiment 072 — Judge the saved N32/N64 pilot

## Status and question

Completed, 2026-10-13 UTC. The user authorized comparison of saved N32/N64 readouts, then added all four task families. The scope is the same 32 fixed development sites (eight per family) from experiment 068, not complete question grids. Original raw N1 and capped N1 are separate reference arms. No generation or activation capture occurs.

## Frozen inputs and procedure

- Parent: `configs/larger_n_pilot_batch256_v2.json`, SHA256 `d8f2f0ee8f07397cd7fc9147e7fcf34d6f5a48939b939c9593ad46733e042af8`.
- Saved common-cache selections: `${OLENS_DATA_ROOT}/larger-n-pilot-v1/score256/selections.jsonl`, SHA256 `7b8c9488f4a65931ddba49e07bc45db42914e2b46a3d2116bcc2f4c43066b81e`.
- Runner: `scripts/evaluate_larger_n_pilot.py` delegates to unchanged pinned WorkspaceBench prompts, parsing, validators and project accounting.
- Judge: `gpt-6-luna`, reasoning `none`, Flex, concurrency 4, 120 requests/minute; both hallucination stages required. Multihop is deterministic regex.
- Exact request caches are reused; forecast identified two new hallucination stage-1 requests, at most two stage-2 requests, four chain requests and three role requests. Expected charge from earlier Standard usage is $0.001520; this is a forecast, not billed spend. Run cap $1, existing project cap $340, all old uncertain reservations preserved.
- Working evidence: `${OLENS_DATA_ROOT}/larger-n-quality-v1/`, including immutable manifest, selected texts, exact forecast, approval/source hashes, budget snapshots, per-arm judgments and final report.
- All selection was fixed before judging. These sites were previously inspected and are exploratory. Grouped paired intervals use the existing 2,000-draw implementation; eight or fewer groups cannot establish robust generalization.

## Completeness, cost and artifacts

Ran in a two-CPU, 4 GB step of existing CPU allocation 25637145. All 16 condition-family records are complete on their eight intended sites, with no missing required verdicts. The upstream missing-full-grid counts are preserved because this is a sparse pilot. No GPU work. Outputs remain outside the repository. The [compact receipt](../reviews/larger-n-quality-v1.json) records source hashes, native counts, intervals and costs.

| Task | Original raw N1 | Best N32 | Best N64 |
|---|---:|---:|---:|
| Hallucination (chat): contradictory / specific readouts | 5/8 | 5/8 | 4/8 |
| Multihop (multi-token): recovered sites | 0/8 | 1/8 | 1/8 |
| Chained intermediates: recovered sites | 1/8 | 0/8 | 0/8 |
| Role-bound association: recovered sites | 0/8 | 0/8 | 0/8 |

Hallucination assertion share remains 8/8 and off-topic readouts 1/8 at both N32/N64. False-span totals decrease 17 to 13; true-claim totals change 10 to 9 and unverifiable totals stay 14. False spans and claims have different segmentation. Both hallucination stages cover all eight outputs. The contradiction change is −12.5 percentage points, with a grouped paired 95% interval of [−37.5, 0] points (eight groups). Other native recovery totals are unchanged; their zero-variation intervals do not demonstrate equivalence or generalization. Chained intermediates has seven independent groups across eight sites.

The two changed hallucination readouts explain the result: the denim response moves from contradictory to consistent, while the extraction response still substitutes the wrong chemical/plant identities. The denim N64 readout retains truncated clauses and its stage-2 accepted claim tally is zero, so the result should not be described as completely informative or perfectly grounded.

The ledger records 12 settled physical attempts with estimated usage cost $0.000809352 and two uncertain attempts retaining $0.009825125. These are provider-usage estimates and reserved uncertainty, not invoice-reconciled charges; no holds were released. The remaining historical reservations are preserved.

## Validation and test access ledger

| UTC | Scope | Access | Purpose |
|---|---|---|---|
| 2026-10-13 | 32 previously inspected development sites | Fixed saved outputs and existing exact caches | Authorized N32/N64 pilot measurement; no test data or selector tuning |
