# 027: Prospective validation shortlist

Status: coordinator reviewed and froze the menu and inference contract on 2026-10-10, before any validation analysis gate was written. Development evidence was snapshotted at 07:53 UTC. Validation generation completed blindly; no validation text, score, selected output, verdict or example was inspected to choose this menu. Test remains sealed.

The menu is narrowed now to protect the 20-hour execution window. Transport failures have left part of development judging unfinished. Completing every development arm is useful descriptive work, but it is not a necessary condition for prospectively fixing a conservative validation menu from the already reviewed pilot and completed family evidence. This is an explicit revision to scheduling, not a new threshold fit or a declaration that every candidate is promising.

`configs/conditions_validation_v1.json` fixes twelve arms:

| Arms | Purpose |
| --- | --- |
| Raw N1 and capped N1 | Released behavior and the common four-bullet/256-token reference |
| A16 and A32 | Best complete readout by exact reconstruction; sample-budget alternatives |
| Random complete N32 | One frozen draw from the same pool, testing selection against random |
| D16 and D32 | Pool complementary bullets; compare with A at the same candidate budget |
| Mean-control specificity N32 | E1 parent |
| E1 followed by .005 pruning; E1 matched-count random deletion | Combined method and its shortening control |
| A32 followed by .005 pruning; A32 matched-count random deletion | Specificity-off component and its shortening control |

A32, E1, A32+pruning and E1+pruning form the complete specificity×pruning comparison. Both random deletions use their own parent's deletion count. All methods use the existing source read cells, immutable samples, decoding provenance, caps, control assignments, solver and whitening contract. N16 is the original nested prefix of the shared N32 pool. No threshold, helper or read plan is changed by this menu. Random N32 is a selection control; drawing one readout at deployment need not generate 32 unused readouts.

The freeze JSON explicitly pins exact SciPy NNLS, its unclipped residual-FVE convention, pooled whitening revision and ridge/centering/unit-direction rules, current scientific source hashes and the earlier DEV producer hashes. Pruning loss remains **.005 per sequential deletion**, with joint coefficients refitted after each removal; random selection/deletion retain their deterministic per-cell hash seeds, with split/audit seed 20261010. The fixed DEV control-bank metadata SHA256 is `ccca28d80794d4de7e612b3a7b1924a9f1e2a43259e31f3b77841e14a18be520`.

New AR rows use the accepted **B128** implementation, four deterministic effective-key partitions in first-occurrence order and one shared catalog. All first-computed inherited DEV rows stay unchanged; missing historical execution metadata is not invented. The prepared plan must bind actual partition/order/catalog hashes before encoding. Failed B32/B128 numerical guards and observed D/E output sensitivity remain disclosed in experiment018; this is a frozen implementation, not a claim of numerical equivalence or robust near-threshold decisions. Invalid-atom eligibility/no-op rules remain those already used in DEV.

Evidence at the decision consists of all 65 complete pilot arms and finalized development contracts for **4/24 hallucination, 24/24 multi-hop, 21/24 chain and 3/24 role arms**. Missing conditions are explicitly unfinished, with successful cached verdicts retained. Complete A32 versus capped N1 covers all 5,236 development cells. Its recovery gains are modest; hallucination improvement is uncertain. E1 pruning loses substantial numerical recovery: chain E1 has 27 passing cells, versus 16 after .005 pruning and 23 after matched random deletion. Such a loss is not established to be a small practical tradeoff. Pooling is retained as a complementary-information candidate, despite numerical regressions and uncertain general usefulness.

An immutable single-file snapshot preserves exact reviewed development result/contract bytes, scientific identities, the 65-arm pilot summary, A32 metrics and raw trace supplement, multi-hop comparisons and incident evidence. It is at `durable/runs/validation-shortlist-freeze-v1/development-evidence.json`, SHA256 `e79ce139d5462100d4ca68eeb1de1d15ca21bb31d85420c0cec98dfbc1c67640`. Its source index is `snapshot.json`, SHA256 `80f2c44add8f83310898f194c50c0cfdd778e4eca0a01367af53efff1c7e32bc`. `configs/validation_shortlist_freeze_v1.json` binds these, the exact menu and source hashes, and complete/unfinished arm lists. Later development judging may update the descriptive report; it cannot add validation arms, retune thresholds or revise the selection procedure after validation opens.

After a separately reviewed analysis gate, judge the twelve arms on the same complete validation grids with Luna reasoning-none and the pinned upstream recipe, including both hallucination stages. Select **at most two quality/cost operating points** manually and record the reasons before test. Assess all four families with original item aggregation and paired cell metrics, related-group uncertainty, assertion/empty/off-topic coverage, systematic wins/regressions/seeded unchanged traces, collateral errors and new-input inference cost. Distinguish recovered names/numbers from correct surrounding relations; preserve raw judge evidence. Family counts and few-group limitations stay visible. No significance cutoff decides advancement, and no hidden macro lets thousands of role cells overwhelm other families.

A useful family-specific gain with wide uncertainty may merit follow-up. A substantial numerical loss requires an explicit tradeoff and cannot be called global improvement. Pruning must be judged against its parent, the specificity-off component and matched deletion, rather than against N1 alone. If there is no convincing practical gain, an inconclusive or negative outcome is acceptable; do not force a new method.

Final test comparisons, component ablations and shortening controls will be frozen in a separate manifest after validation selection. Test cannot choose an operating point. Validation intervals are exploratory selection evidence, not the final unbiased estimate. No gate or paid validation request is created by this document.
