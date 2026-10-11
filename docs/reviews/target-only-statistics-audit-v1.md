# Target-only follow-up: independent statistics audit

Reviewed 2026-10-11 before new quality outcomes. This is a source review, not a replay of final judgments or bootstrap output. No fitting, inference, API calls, installation or heavy computation was performed. After the initial read-only review, root explicitly authorized the three narrow analyzer corrections documented below; selectors, evaluation and judge implementations were not changed.

The core endpoint extraction, paired resampling and declared comparison menu are consistent with the follow-up plan. I found no native denominator, question/site pairing or 44-contrast multiplicity error. Final results still require terminal coverage, source-bound root review and inspection of any degenerate/undefined intervals.

## Reviewed sources and scope

- `configs/target_only_inventory_v2.json`: SHA256 `181fcc259ed81213a7b26ea18142b6cd35648e89b83100a5cf07590ed75b2c47` (verified).
- `scripts/analyze_target_only_search.py`: initial reviewed SHA256 `f91063ef19fac8618bb26f6ed79a4eec0e8d16d99f892dd70e928a8cf13461f4`; corrected SHA256 `1fcb8f0083d6a6a55991b70420e94674452633181d38d04f08995b247ac56aab`.
- `src/olens_improve/expanded_statistics.py`: SHA256 `66dc640a6a4c0760f2a9591e78554bdd5dfb3dba35e306675448c4280b1458c9`.
- `src/olens_improve/reporting.py`: SHA256 `7bc728136f19eac771ed3fb8c3b9077f416d047197bb3c9c0de2c431985ee319`.

Also inspected `evaluate_target_only_search.py`, `expanded_judges.py:expansion_cohort`, `analyze_expansion.py:runtime_authority`, `verify_expansion_judge_contracts.py`, existing focused tests, presentation source gates, and the frozen WorkspaceBench Hallucination judge/scorer. Existing focused tests were rerun after the authorized corrections.

A tiny read-only capture-manifest tally verified: Hallucination (chat), 149 questions/5,615 sites/149 groups; Multihop (multi-token), 100/1,100/94; Chained intermediates, 120/1,320/42; Role-bound association, 100/11,400/50. Each question has one consistent group ID. Total: 469 questions and 19,435 sites. These banks have already been inspected; bootstrap uncertainty does not turn them into a fresh holdout.

## Findings

1. **Native endpoints and pairing pass.** Hallucination retains unrevoked `wrong / (wrong + off_topic + consistent)` as a ratio of sums. Related sites aggregate under each question before whole-group resampling; the headline is not a mean of question percentages. Its assertion share and both off-topic denominators remain available. Recovery requires the original per-site rule and then ANY passing site/layer for question recovery; independent checks compare reconstructed question flags and native headline numbers to saved upstream results. Site recovery is secondary descriptive count data, with no site-level independent-sample claim.

2. **Both Hallucination stages are required for nonempty outputs.** Missing stage 1/2 prevents an arm from entering native analysis. Explicit blanks are abstentions, remain in intended-output denominators and do not become successful recoveries. Disputed claims are a subset of the source unverifiable tally, not an additional mutually exclusive category. False spans have different segmentation from true/unverifiable claims. Secondary per-output tallies use all intended outputs, including blanks; do not label that denominator as the upstream source's narrower stage-2-judged-readout denominator.

3. **Bootstrap and menu pass with normal limitations.** Each family's bootstrap resamples its original whole groups and uses identical group weights for every arm, retaining pairing. Families use independent random draws. Eleven unique frozen comparisons cross four endpoints, giving 44 declared contrasts. Pointwise percentile intervals are separate from approximate centered standardized joint-maximum intervals. The simultaneous hull contains the pointwise interval and is clipped to the feasible rate-difference range. Degenerate/undefined contrasts have warnings and no simultaneous interval; report declared versus effective counts honestly. Absolute-rate intervals are pointwise, and secondary outcomes/supplementary comparisons are outside the 44-contrast adjustment.

4. **References and interpretation pass.** All four additions retain raw original comparisons and their declared actual parents; capped original, best-of-32, plain pooling, prior pruning and prior matched deletion remain distinct references. No control-activation condition enters this menu. Guided versus random deletion isolates the chosen deletion rule conditional on the repeated-swaps parent and matched bullet count; token lengths can still differ. Prune/refill versus terminal pruning compares different constrained scaffolds, not a pure optimization-efficiency intervention. Reconstruction contribution is not truth or established faithfulness.

5. **Scientific source gates are strong; implementation receipt was corrected.** Ready descriptors bind exact inventory/manifest/selections. Judged readouts must match saved selected text on every fixed site. Terminal summaries must embed identical upstream results and approved contracts, including the original benchmark/runtime source pins. Scientific inputs are checked again after extraction, and existing analysis outputs cannot be overwritten. Initially, implementation hashes were taken only at the end and omitted imported `runtime_authority`, `expansion_cohort`, and `verify_judge_contract` implementations. The authorized correction snapshots contributing implementation hashes before extraction and verifies them again before writing, avoiding a receipt of disk bytes changed during analysis.

## Authorized corrections applied

- Corrected the simultaneous-family description to include **all 11 frozen named contrasts crossed with four native endpoints**, including guided-versus-random and other scaffold comparisons. Numerical inclusion of the contrasts was already correct.
- Reset `headline.joint_interval_contrasts` to zero when an entire family is absent, together with the critical value and erased intervals. This does not affect a complete final analysis.
- Added an initial snapshot of the analyzer and ten contributing implementation files, including runtime/descriptor/terminal-contract helpers, and an immutability check before writing. The receipt retains the initial hashes instead of hashing implementations only at completion.

These changes leave all endpoints, bootstrap recipes, seeds, resampling and declared scientific comparisons unchanged. The frozen inventory still has its original verified SHA. Validation: existing `test_target_only_evaluation.py` (6 tests) and `test_expanded_statistics.py` (9 tests) passed, with bytecode writes disabled; both suites together used less than one second. No new tests, jobs, dependencies or inference were needed.

Final displays should preserve warnings/effective counts and state explicitly that this adjustment covers this fixed new menu, not historical adaptive choices, all secondary outcomes, or the original 70-setting study.

Final terminal metrics were unavailable for independent replay at review time. This review approves the inspected statistical structure with the above corrections applied; it does not certify unseen final counts or causal conclusions.
