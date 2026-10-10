# 019: Larger development comparison

Updated 2026-10-10 07:36 UTC: all 5,236×40 offline selector outputs and the four frozen E1 pruning controls are complete. **A32 versus capped N1 is complete on all four development families:** concept recovery improves modestly, while the hallucination difference remains uncertain and selected explanations still contain errors. The rest of the main queue is **paused by the transport guard**; successful verdicts and every uncertain charge are retained. Multi-hop is complete for all 24 arms, and other families have unfinished conditions. Blind validation generation has been authorized separately; validation outcomes and test outputs remain sealed. See the source-checked comparison below and [incident evidence](023-judge-transport-recovery.md).

The current useful result is a larger exploratory recovery signal, not an established improvement in complete explanation faithfulness. A32 combines more samples with reconstruction selection; its comparison with N1 cannot identify which component caused the gain. No validation choice follows from this comparison alone.

Frozen before full-development method selections or judgments: 2026-10-10,
approximately 04:17 UTC. This is an adaptive development follow-up to the
189-cell pilot, not a preregistered confirmatory test. Validation and test
readouts remain sealed. Baseline raw/capped N1 results have already been seen.

Use all 5,236 development cells from the complete original grids in
`configs/development-full-grid-v2.json`, the immutable 32-sample snapshot at
`durable/runs/development-full-grid-v2`, and the existing matched controls.
The four selection shards must use one identical scoring contract, preserve
every original source ID, and pass a complete-cohort merge check. Raw and capped
N1 texts must match the early baseline export exactly before reusing judgments.

The first comparison comprises 24 conditions:

| Conditions | Purpose |
|---|---|
| Raw and capped N1 | Released behavior and the common output cap |
| Best exact reconstruction at N=1,2,4,8,16,32 | Sampling curve; N1 also exposes parser-based abstention |
| One frozen random complete sample at N16 and N32 | Same-pool random controls |
| Pooled selection at N16 and N32 | Complementary information across samples |
| Best-of-32 followed by pruning at .001 and .005, and both matched-count random deletions | Contribution-based deletion versus simply shortening |
| Capped N1 followed by .005 pruning and its matched-count random deletion | Low-generation-cost pruning |
| Mean-control and maximum-control specificity at N32 | Selection using matched control activations |
| Mean specificity followed by .001/.005 pruning, and both matched-count random deletions | Promising combination and component/shortening controls |

All thresholds, donor lists, random seeds and numerical objectives are inherited
unchanged from the pilot. The .001 threshold remains sensitive to the measured
numerical drift scale. Source-compatible approximate reconstruction is retained
as an offline numerical diagnostic; the primary quality comparison uses exact
nonnegative least squares. No threshold is fitted to individual benchmark
answers. The inference modules never receive judge results.

The additional matched-donor N1 control is a separately labeled diagnostic of
activation dependence. The all32 candidate-quality diagnostic stays on the
original 189 cells. A new bounded pilot may combine pooling with specificity;
it is outside this frozen 24-condition list and requires its own recorded
decision before expansion. Semantic consensus, free editing and likelihood
selection are not broadly expanded on their present evidence. Their pilot
results and limitations remain part of the report.

The frozen condition lists are `configs/conditions_full_dev_v1.json` (20 base
selector conditions) and `configs/conditions_full_dev_combinations_v1.json`
(four additional specificity/pruning conditions). Judge every final readout
separately with the pinned Luna recipe, full hallucination stage2 and the
existing multihop regex. Reuse exact request keys, not merely similar text.
Forecast unique uncached requests before launch. Initial API run ceiling: $20
for these comparisons, inside the unchanged project ceiling; an incomplete
condition is never presented as a completed score.

If the forecast approaches that ceiling, dispatch complete comparisons in this
priority order: raw/capped N1 and best-of-32; mean specificity and its two pruning
variants with both matched deletions; the remaining N scaling curve; pooled
selection and best-of-32 pruning with matched deletions; low-cost N1 pruning,
maximum-control specificity and frozen random draws. Reserve hallucination
stage2 and retries before starting each arm. Freeze the resulting dispatch list
before paid execution rather than stopping after a favorable result. Any omitted
arm remains explicitly incomplete. The separately judged 189-cell all32 pool
provides expected-random sensitivity evidence; it does not replace the frozen
full-development random controls.

Report original item aggregation and cell-level results side by side. The
primary hallucination endpoint retains its asserting-readout denominator;
include assertion share, off-topic outputs, claim tallies, missingness and
length. For recovery, an item-level ANY passing site is distinct from broadly
correct descriptions. Use related-group paired uncertainty, with family counts
and the small seven-group chain limitation visible. Inspect deterministic and
seeded examples of gains, losses and unchanged outputs; check whether recovered
names/numbers sit inside incorrect relations or computations.

Quality remains the priority. Show observed quality/cost tradeoffs rather than
selecting solely by a significance cutoff or a single pooled score. Keep campaign
spending, cached-selector work and estimated new-input inference costs separate.
Report shared generation/AR work, CPU selection, helper calls, tokens and
latency/throughput caveats. GPU dollar cost remains unknown.

After this comparison, freeze a small validation shortlist and its operating
settings. A method with a useful family-specific effect may advance despite a
wide interval; a tiny score advantage explained by shorter output, judge
instability or increased errors elsewhere is not sufficient by itself. Preserve
raw/capped N1 and best-of-N comparators, plus component-off and shortening
controls for any advancing combination. Freeze the final selection before
opening test results. Do not choose a favorable operating point on the test set.

## Execution corrections before judging

The first four CPU workers unintentionally shared the same four physical cores
under overlapping Slurm steps. They were stopped with 21 complete cell records
preserved, no malformed journal tail, and 3,075.95 summed process CPU-seconds
recorded. The source samples, vectors and evaluation settings were unchanged.

Before restarting, a coverage audit found two N1 samples with a non-bullet
preamble. The random-control branch previously omitted its result when every
sample in the prefix was parsing-ineligible. It now emits an explicit empty
readout with `no_eligible_complete_sample`, matching best-of-N's handling of
that case. Eligible seeded choices are unchanged; two regression tests pass.
This concerns the auxiliary random-N1 diagnostic, not a change to the frozen
20 base conditions above. The fix is local commit `7684d6f`.

The corrected outputs use `durable/selections/development-full-grid-v3/`;
the frozen cohort and sample snapshot remain development-full-grid-v2. Earlier
partial outputs and logs remain under the previous selector directory. Four
workers request the allocation-wide CPU set, then bind to disjoint four-core
subsets. Validate overlapping old/new completed scientific outputs, the final
cohort merge, and early raw/capped baseline identity before judging. Record the
restart's compute in campaign cost rather than dropping the initial attempt.

The v3 run then stopped at 2,018 committed cells because a bullet had no tokens
after released AR cleanup. A complete source audit found 523 such bullets in
395 samples and 103 role cells: 522 contain only formatting tags and one is
whitespace. Ten N1 cells contain 17 affected bullets. Every span and activation
hash matches the immutable generated pool; this is not a corrupted vector.
The source reconstructor treats empty-cleaned inputs as invalid. Its zero
placeholders must not be whitened and interpreted as concept predictions.

The reviewed fix preserves raw/capped/random baseline text and records absent
fits explicitly. Reconstruction-guided complete selection excludes an
unscoreable complete sample. Pooling may use its valid individual bullets but
cannot label a partial set as that complete-sample fallback. Pruning an
unscoreable N1 parent leaves it unchanged with an explicit unavailable reason;
its matched-count deletion control is likewise unchanged. A genuinely empty
selected set retains the defined FVE of zero. Per-sample invalid atom provenance
is included in every selection record. These eligibility differences must be
reported, not hidden as zero scores or missing cells.

Five focused tests and a two-cell real replay passed, including one affected
N1 parent and the whitespace case, with all 40 offline condition rows retained.
Local commit `3b96f8e` records the fix. A new four-shard run writes
`durable/selections/development-full-grid-v4/`; v3 files remain unchanged and
bound by `error-provenance.json`. The frozen scientific 24-condition list,
candidate pools, controls and thresholds are unchanged. Check overlapping
scientific outputs and all early baseline texts before judging v4.

## Verified outputs and eligibility before judging

The completed v4 merge contains all 5,236 cells and forty offline conditions, SHA256 `54ee50e61ebc11ac66d8d11c294dda60e17a7f9e06ad8632665e6bbb6505635e`, at `durable/selections/development-full-grid-v4/merged/selections.jsonl`. The four requested E1-pruning controls come from `durable/selections/development-full-grid-e1-pruning-v1/selections.jsonl`, SHA256 `a645983ab2e24eb4ef6f6fb298698405b4a2cee29c221af3da00d2e06ec6935a`. Original source samples, source IDs, read cells and scoring settings remain frozen.

The baseline identity audit passed all **10,472 raw/capped outputs** across 5,236 cells, including exact text, Qwen-token counts, cell/vector identity and source hashes. Evidence is `merged/baseline-identity-audit.json`. `scripts/audit_selection_eligibility.py` independently checked the complete merged events on two allocated CPU cores; its artifact is `merged/eligibility-audit-v1.json`.

| Family | Intended cells | Parsing-ineligible N32 samples | Samples with invalid AR atoms | Additional AR exclusions after parsing |
| --- | ---: | ---: | ---: | ---: |
| Hallucination | 1,145 | 40 | 0 | 0 |
| Multi-hop | 341 | 0 | 0 | 0 |
| Chain | 330 | 0 | 0 | 0 |
| Role | 3,420 | 24 | 395 | 385 |

The 395 role samples affect 103 cells and contain 523 invalid retained bullets; ten samples overlap parsing exclusions. These formatting/empty-cleanup cases are not false-claim labels. At N1, best-of-N differs from capped N1 only by twelve empty outputs: one hall preamble, one role preamble, and ten role samples with invalid AR atoms. Capped N1 remains nonempty in all twelve cases. Every unscoreable N1 pruning/matched-deletion branch leaves the parent unchanged on those ten role cells. Thus A1-versus-capped-N1 differences here are eligibility/abstention differences, not improved semantic ranking. Random N16/N32 retain twenty/six AR-unscoreable role outputs, while reconstruction-guided A/E cannot choose those complete samples. The full audit preserves prefix, per-arm, reason, null-fit and empty-output counts with the original intended denominators.

## Compact input, forecast and frozen dispatch

`scripts/export_judging_inputs.py` projects exact final text, token/bullet counts and provenance for the frozen 24 conditions. It verifies source SHAs, every cell/activation identity and full condition coverage without rewriting or re-tokenizing. The repeated E1 parent matches on all 5,236 cells; the v4 source stays authoritative. The compact immutable input is `durable/selections/development-full-grid-judging-v1/selections.jsonl`, **71.60 MB**, SHA256 `acfcdefc425f48da612059f7bcb157bf037f91ba4e70fa9c68b0db142bfc46a4`. Full fits/traces remain in the 1.425 GB parent. The evaluator now streams records, avoiding whole-file copies; seven focused offline evaluation/cache/transport tests passed.

The same directory preserves `export.json`, `base20-forecast-v1.json` and `forecast-v1.json`; files copied from `/tmp` retain their exact byte hashes. `scripts/forecast_judging.py` uses the pinned upstream prompt builders, original validator source and exact request-cache identity. Its completed three-arm pilot check reproduced all 550 unique requests as validated cache hits. The combined forecast sees **12,557 new hall stage1 requests, up to 12,557 additional stage2 requests, 4,156 chain and 46,010 role requests**; multi-hop uses no API. New stage1 wrong spans are unavailable before judging, so stage2 cache/cost is explicitly conditional. The observed-mean usage forecast is **about $10.19**, not a guaranteed bound; the atomic $20 run ceiling, retry reservations and project ceiling govern dispatch.

At eight request slots and 200 logical calls/minute per family, the idealized service/rate reference is 3.83 hours for the role critical path and 2.61 hours for hallucination; a p95-wave reference is 5.31 hours for role. These are not promised walltimes or statistical bounds. Queue/stage barriers, cache IO, startup, retries and transport incidents add time; healthy response averages may not represent every new context. Observed throughput controls subsequent adjustments rather than extrapolating the small pilot as a speed guarantee.

The unchanged scientific list is reordered in `configs/conditions_full_dev_priority_v1.json`: raw/capped/A32, then E1 and its four shortening controls, then remaining scaling/pooling/pruning/random conditions. The first three use `conditions_full_dev_tranche1_v1.json`, SHA256 `5f80a746db27769b32a701ba3f71cd07bee96a580c05208d3b135dd5bf8505c2`; the remaining twenty-one use `conditions_full_dev_tranche2_v1.json`, SHA256 `7cf2ee9b644090b59f09b2c299cee4a2f5a10df2279736f6ffaebe1a0f10b881`. Their union is exactly the original 20+4 conditions. Both tranches share `development-full-grid-methods-v1`, the $20 ceiling, compact input, exact cache and frozen recovery epoch `2026-10-10T04:50:43+00:00`.

Tranche1 was launched by the coordinator with Standard Luna, benchmark effort none, eight slots/200 rpm, SDK retries disabled and bounded outer attempts. Logs are `fast/logs/full-dev-judging-tranche1-v1.log`; outputs are `durable/runs/development-full-grid-v2/judgments-methods-v1`. Let it finish naturally. Before tranche2, the coordinator may approve sixteen slots/400 rpm only after at least 1,000 healthy new main requests, no new unknown reservations and latency review. Never interrupt in-flight calls merely to raise concurrency; retain existing holds and epoch. This changes transport throughput, not the scientific condition or judge semantics. Further ramps require fresh measured evidence. An incomplete arm remains incomplete, and these adaptive development comparisons cannot certify a chosen winner before the frozen validation/test procedure.

The first cache-only baseline replay completed with zero new API charges. Within-family execution times for raw/capped N1 were hall 4.88/2.49 seconds, role 1.98/1.37 seconds and chain .81/.27 seconds; regex multi-hop was below .16 seconds. Including compact-input startup, all baseline-family stages finished within about nine seconds. The per-hit SQLite/local-cache IO is therefore not a measured bottleneck here. At the subsequent 1,126-new-response check, all physical attempts settled or remained in flight, with zero new unknown reservations; pooled p50/p95 physical latency was 2.98/5.84 seconds. Hall and role A32 were still active, so this observation permits a later reviewed ramp rather than interrupting them or declaring tranche1 complete.

## Transport pause and recovery boundary

After the healthy gate, chain tranche2 started at 06:11:53 UTC with sixteen slots/400 rpm; multi-hop completed its remaining conditions without API calls. Hall and role continued their original A32 runs at eight slots/200 rpm. The first new connection failure was reserved at 06:12:30 and marked uncertain at 06:12:53. Recurring errors preceded the shared guard pause around 06:22:17–20. No manual interrupt was sent by the boundary watcher.

The immutable sanitized snapshot is `durable/runs/development-full-grid-v2/judgments-methods-v1/transport-incident-v1.json`, reproduced by `scripts/record_judge_incident.py`. It records **4,551 settled physical requests, $0.6401183 in usage-accounted spend, 42 uncertain attempts reserving $0.208778875, and zero live reservations**. Twenty-one failures have connection/read cause chains (fourteen ReadError and seven ConnectError); twenty-one further holds are cancellations during guard shutdown. This was a transport stop, not an exhausted $20 run ceiling. Retain all holds; later cache success cannot prove an earlier attempt was uncharged.

All twenty-four multi-hop conditions, seven chain conditions, and the two baseline conditions in each remaining family completed. A32 hallucination/role and chain E1-matched deletion at .005 failed before terminal outputs; their successes remain in the exact cache. Report unfinished conditions as incomplete rather than zero scores or successful abstentions. Recovery must reuse identical source text, frozen conditions, original run ID/ceiling and exact caches on a reviewed fresh CPU allocation, initially eight slots/200 rpm. A new recovery epoch requires resource headroom and one bounded Luna health check; it does not erase prior uncertain holds.

Cause remains unresolved. Source inspection confirms each upstream async stream creates and closes its own client before its event loop exits; no cached client is reused across closed loops. Observed open descriptors were 16–24 versus a 131,072 limit. The existing allocation's memory cgroup was near its 128 GiB limit despite ample node RAM and small judge processes; resource ownership and unrelated work require separate handling. Neither concurrency, shared CPU affinity nor these timestamps establish why the requests failed.

Future family workers support a **SIGUSR1** or `--stop-file` request to finish the current condition and stop before dispatching the next. This leaves prompts, caches and scientific identities unchanged. Two focused boundary tests plus the existing seven evaluation tests pass. The safety guard remains necessary within a long condition; a boundary stop is an operational scheduling control.

## Isolated recovery and completed multi-hop evidence

The single exact-request health check passed on the fresh allocation at 06:31:47.818715 UTC in 2.2926 seconds, with 573 input and 35 output tokens and no reasoning tokens. It retained the older unknown request and did not replace a primary verdict. The coordinator authorized recovery epoch `2026-10-10T06:32:00+00:00`. `configs/judging_main_recovery_v1.json` binds the fresh CPU/resource evidence, health/incident hashes and unchanged source/manifest/condition hashes. Its SHA256 is `356de39e8149d19e82c846457cfd7da0bcbb0465291d3aa0f4ac85b6ed72e99b`.

Recovery runs through `infra/resume_main_judges.py` on allocation 25474685/node1600, eight physical CPUs and 32 GiB. Hall, chain and role use distinct CPU pairs, eight request slots/200 rpm per family, the original $20 ceiling, identical Standard Luna/none semantics and exact cached successes. All old holds remain reserved. There is no automatic ramp. Completed multi-hop judgments are not relaunched. The first 226 new physical responses settled with zero new unknowns; this early sample is not a sustained throughput guarantee.

The completed multi-hop family uses **31 development items, 29 related groups and 341 cells**. Its endpoint requires bridge-string recovery using the frozen regex, rather than checking the truth of all emitted relations. Both the original item-ANY aggregation and cell recovery are preserved:

| Arm | Items with any passing cell / 31 | Passing cells / 341 |
| --- | ---: | ---: |
| Capped N1 | 11 | 29 |
| Best reconstruction N16 | 14 | 48 |
| Best reconstruction N32 | 14 | 43 |
| Random complete sample N32 | 12 | 45 |
| Pooled N16 | 17 | 54 |
| Pooled N32 | 14 | 56 |
| Mean specificity N32 | 14 | 41 |
| Mean specificity then .005 pruning | 10 | 34 |

The paired 29-group interval for A32 versus capped N1 is **+4.11 percentage points in cells [1.82, 6.61]** and **+9.68 points in item ANY [0, 22.58]**. Pooled N32 versus A32 adds 3.81 cell points [.91, 7.04], but item ANY is tied with an interval of [-15.63, 15.63] points. Pooled N16 versus A16 adds 1.76 cell points [-1.25, 4.69] and 9.68 item points [-6.45, 25]. These exploratory comparisons are unadjusted; wide intervals do not make an observed gain worthless, and a family-specific gain does not select a global winner.

`scripts/analyze_completed_mt.py` produced `judgments-methods-v1/mt-paired-analysis-v1.json` with all 24 source-checked conditions, paired intervals and deterministic/seeded traces. At `mhh-1967-norwegian-classes-objects-codesigner`, layers 28/44, the selected readouts recover **Simula 67** while still listing competing collaborator names. The endpoint verifies the bridge phrase, not those names or their relations. At `mhh-mesopotamian-wildman-cedar`, layer 52, pooling removes **Enkidu** while retaining Humbaba and adding different role relationships; naming the final ogre cannot replace recovery of the hidden bridge. At `mhh-pitchblende-jachymov`, layer 52, pooled text retains the town but drops the required ore name. These examples explain why mention recovery and a faithful complete explanation remain distinct. No validation decision follows from this family alone.

## First complete four-family comparison: A32 versus capped N1

`scripts/analyze_a32_baseline.py` requires complete original grids, verifies the compact source SHA, and reuses the existing reporting and paired related-group bootstrap. Its immutable result is `durable/runs/development-full-grid-v2/judgments-methods-v1/a32-baseline-paired-v1.json`. Every intended cell is present; hallucination has both stages complete. Intervals use 2,000 paired group draws, seed 20261010, without adjustment for the other exploratory comparisons.

The separate evaluation-only `a32-trace-supplement-v1.json` preserves eighteen selected role/chain traces, both texts, exact upstream role options and gold/returned choice indexes, raw rationale, chain values/quote/basis, and the official scored layer. Source bank/result/cache/prompt/scorer hashes are bound in the artifact. `scripts/supplement_a32_traces.py` replays the pinned chain verdict transform, including the three-value cap, and checks exact agreement with every selected scored layer; role cached choices must reproduce the official correctness flags. Original comparison v1 remains unchanged. Supplement SHA256: `ecdf20d23c25d352f3a4aac7cf5283ded306fa7d441a85cb74216629610cca74`. This substantiates the interpretation with retained evidence rather than passing flags alone.

| Family and endpoint | Capped N1 | A32 | Paired change, percentage points [95% interval] | Items / related groups |
| --- | ---: | ---: | ---: | ---: |
| Hallucination: wrong / (wrong + off-topic + consistent) | 543/1,137 | 523/1,140 | −1.88 [−5.41, +1.76] | 30/30 |
| Multi-hop: passing cells | 29/341 | 43/341 | +4.11 [+1.82, +6.61] | 31/29 |
| Chain: passing cells | 26/330 | 30/330 | +1.21 [−3.16, +4.85] | 30/7 |
| Role binding: passing cells | 151/3,420 | 182/3,420 | +0.91 [+0.15, +1.73] | 30/15 |

Original-grid item-ANY recovery is multi-hop **11→14/31**, chain **15→19/30**, and role **23→23/30**. Paired intervals for those item-rate changes are respectively +9.68 [0, +22.58], +13.33 [−6.67, +43.48], and 0 [−10, +10] points. Chain has only seven related template groups, so its interval cannot establish broad robustness. Role has 114 read cells per item; the unchanged item-ANY count and the cell gain answer different questions. These family axes measure different item banks and must not be presented as within-item precision and recall.

Hallucination assertion share is **1,137/1,145→1,140/1,145**; off-topic readouts are **148→134**, while true-claim tallies are **1,827→1,839**, unverifiable tallies **4,057→3,910**, and established false-span tallies **1,305→1,324**. Thus fewer wrong readouts do not imply fewer false spans. False spans and true/unverifiable claims have different segmentation and cannot form an atomic precision score. The secondary wrong/(wrong+consistent) ratio is 543/989→523/1,006. Mean Qwen-token counts change from 101.01→102.16 in hallucination, 99.67→100.70 in multi-hop, 83.74→87.02 in chain, and 97.31→97.81 in role; both use the same four-bullet/256-token cap. These are similar average lengths, not an exact matched-length ablation.

The artifact selects the first three distinct item IDs in each changed category and three seeded unchanged cells. The following inspected examples connect endpoint changes to actual text; they do not correct the frozen verdicts or estimate prevalence:

- **Recovery with incorrect surrounding details:** `chain-d2p-0239`, L40 p64, requires the intermediate 18 from starting at 6 and multiplying by 3. N1 names other calculations; A32 names 18 but explains it as “First add 2 to get 5, then multiply by 3,” alongside 36, 126 and 42. Its recovery hit is useful evidence that 18 became available, not a faithful computation. At `chain-d2p-0298`, L20 p66, A32 gains the required 12 while other bullets assert 50 and −1.5.
- **A genuine loss of a recovered number:** `chain-d2p-0256`, L28 p61, needs the intermediate 7. N1 contains “The final number is **7**”; A32 replaces it with 30/3 and “The final number is **4**.” The former is itself mislabeled as final rather than intermediate. The numerical endpoint detects presence of the required intermediate, not correctness of its stated role.
- **Role signal and judge ambiguity:** `oa-boss-employee-envy-ab`, L28 p100, changes from approvals/influence to “secretly envied their creative output,” matching the boss→employee direction. It still adds unsupported code/music details. At L36 p91, N1 passes from a boss affected by a coworker's art; A32 fails despite approval/admiration language. The judge rejects its invented Jane/Mara names, while accepting unnamed role mapping in the L28 win. The separate reverse-direction item at L36 p122 similarly passes “Dan/Daniel” with the wrong counterpart name but rejects A32's invented names. These traces expose identity-mapping sensitivity; they do not establish that all 31 extra passing cells are reliable binding gains.
- **A hallucination flip needing caution:** `chat-dailydialog-0002`, L36 p22, changes from “李芳 is not my name” and other rejected names to “李老师 … is not my identity,” with wrong→consistent verdicts. The source response identifies Qwen and does not assert those human identities. At L52 p20, adding “not Dr. Lu” instead produces consistent→wrong. The frozen labels remain authoritative benchmark outputs, but unsupported names versus transcript contradiction are not cleanly separated in these examples. This is a limitation of the endpoint, not proof of a method win.
- **Unchanged failures:** seeded examples include `chain-w2-d2p-0082`, L52 p61, with confused doubling calculations in both arms, and `oa-comedian-heckler-humiliate-ab`, L52 p167, with instructions to summarize rather than a role binding. The seeded hallucination example `chat-dailydialog-0051`, L44 p22, remains off-topic movie-grammar advice in both arms. Preserving unchanged traces avoids presenting only favorable cases.

The remaining full-development arms, particularly the frozen random controls, are still needed to judge selection quality. The separate complete 189-cell all-candidate diagnostic is already available; it does not replace those full-development comparisons. This evidence supports continued investigation of the modest recovery gains; it does not select a universally better operating setting, establish a faithfulness frontier, or justify a claim that reconstruction beats random sampling.
# Remaining development judging after validation handoff

At 10:58 UTC on 2026-10-10, the development hallucination evaluator resumed
only its fourteen unfinished conditions. The validation hallucination worker
had completed all twelve signed conditions, exited with code zero and released
its exclusive cache-owner lock. Its completed validation artifacts and the ten
already completed development condition artifacts are preserved.

The reviewed launch is `configs/judging_main_post_validation_hall_v2.json`,
SHA-256 `ddc48860e47a2d54dbb5fe6122ece309bd0282cf56fe0fb9d4fac01effe5a718`;
the new PID is 3432184 on CPU cores 24 and 30 of the existing judge allocation.
The full twenty-four-method menu remains unchanged. A separately hashed ordered
remaining-condition list avoids replaying and rewriting completed artifacts.
Four focused checks cover subset identity, order, hashes and unchanged command
arguments. The old v1 preparation specs remain intact.

The shared $20 development ceiling, eight slots/200 RPM, Standard Luna with
reasoning disabled, 07:52 recovery epoch and every prior uncertain hold remain
unchanged. No new health request or epoch reset was made. These later development
results are descriptive and cannot change the earlier frozen validation menu or
its evidence cutoff. Test judging has priority at a clean condition boundary.
Role development remains prepared pending the corresponding validation worker's
completion and cache release; this paragraph does not authorize its launch.
