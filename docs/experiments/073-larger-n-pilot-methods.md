# Experiment 073 — Apply the existing methods to 64 saved samples

## Status and question

Completed, 2026-10-13 UTC. While experiment 072 was running, the user requested the existing methods, specifically removing weak bullets, combining bullets and combining plus pruning, on the saved 64-sample pool. Use the same 32 development sites from experiment 068, with all four task families and no full-bank extrapolation.

## Frozen procedure

Reuse the displayed algorithms and settings rather than tuning on these pilot outcomes: best complete sample, leave-one-out pruning with maximum sequential FVE loss 0.005, greedy pooling with one swap pass and complete-sample fallback, and pooled output pruned at 0.005. Retain four bullets and 256 Qwen tokens. Compare N32 and N64 on identical sites and retain the separate released raw N1 reference. Use saved target activations and saved AR vectors only for these four arms. Preserve historical selectors and caches.

The other displayed methods are semantic consensus (support fraction 0.125, pairwise compatibility and contradiction veto, 40-pair budget) and two-round candidate-only editing. Their unchanged helper contracts and any additional AR encoding needs are being checked before dispatch. No new Oracle Lens samples or benchmark-based selection are authorized by this implementation.

## Measurements and limits

All four native task endpoints, completeness, empty outputs, text length and AR reconstruction will be reported separately. Judge calls reuse exact caches and the pinned Luna recipe; both hallucination stages are required. These are sparse, previously inspected development sites, not full question grids or evidence of an overall benchmark improvement. New helper/GPU costs will be bounded and recorded before dispatch.

## Artifacts and access

Source pool, activations and reconstruction contract are those of experiment 068. New data will live under `${OLENS_DATA_ROOT}/larger-n-methods-v1/`. No production output or historical study asset is overwritten. No website changes are part of the current measurement step.

## Execution update

All 32 CPU selection cells completed and independently replayed the saved best N32 and N64 texts/FVE. Core selection SHA256: `c4bc0a79014bd9962a46c07a0b82183e6d63bbe683b83e34fdae2e42db71f6f9`. The fixed ten-arm core evaluation includes separate raw/capped N1 references and four methods at N32/N64. Exact-cache forecasting estimates $0.010015 of new judge usage before retries, under a $1 run cap.

All six displayed methods are being included. Candidate-only semantic consensus uses the original .25 proposal/compatibility stage followed by the fixed .125 support, compatibility-on, merge-veto-on readout, with 40 pair checks. The saved original reference for that method used N16 and will be labeled explicitly. Editing uses two rounds, at most four total proposals per cell per round, a two-parent beam and unchanged-parent fallback. Helper work is capped at $5 combined; it sees no tasks or answers. The N64 parent vector catalog references 228 existing vectors in 65 tensors without copying any tensors. A verified-idle H200 in user allocation 25637237 is used only for fresh edit AR encodings at batch 128. User allocations are preserved.

## Completed findings and verification

All six displayed methods are complete at N64 on the same 32 development sites. The final table contains 14 conditions (including raw/capped references and prior method budgets) × four families = 56 measured condition–task records, with no missing required verdicts. See [the report](../LARGER_N_METHODS_REPORT.md), [CSV](../reviews/larger-n-methods-v1.csv) and [source-bound receipt](../reviews/larger-n-methods-v1.json). The old Keep repeats reference uses N16; it is not mislabeled N32.

- Best complete sample: hallucination contradictions 5/8 → 4/8; multihop 1/8 unchanged; chain/role 0/8 unchanged.
- Remove weak bullets: hallucination contradictions 6/8 → 7/8; recovery totals unchanged.
- Combine bullets: hallucination contradictions 6/8 → 5/8, multihop 2/8 → 1/8, chain 0/8 and role 1/8 unchanged.
- Combine + prune: hallucination contradictions 8/8 unchanged; multihop 2/8 → 1/8, chain 0/8 and role 1/8 unchanged.
- Keep repeats (N16 → N64): hallucination goes from 1/2 contradictory specific outputs to an undefined rate because all eight N64 outputs are empty. Across all tasks N64 emits 24/32 empty outputs. Chained-intermediate recovery changes 1/8 → 2/8; multihop/role remain 0/8. This cannot be presented as reliable hallucination suppression without disclosing abstention.
- Edit pooled text: the same native totals as plain pooling at both budgets. At N64 two selected texts differ from unchanged parents, one from each edit round; neither changes its native recovery outcome.

These small paired samples do not establish a robust quality benefit. The best-of-N hallucination difference has 95% interval [−37.5, 0] percentage points. Other nonzero N32/N64 headline differences also retain zero in their paired interval. Zero-variation intervals do not establish equivalence. Pruning-related judge label changes are measurements, not proof that deletion introduced new facts.

All N32 pooling/pruning texts matched their original frozen exports in 64 checks; all best N32/N64 texts and scores replayed the saved pilot. Historical cached exports sometimes omit per-cell FVE; the audit labels that absence and does not invent a replayed historical score. The final selected texts are pinned before judging. Both hallucination stages are required for every nonempty readout. Existing caches reuse exact prompts, source hashes and validators only.

Two H200 scoring steps, 25637237.10 and 25637237.11, completed in 36 and 30 seconds (0.018333 H200-hours). They encoded 105 and 86 fresh edit vectors, respectively. No new Oracle Lens samples were generated. The GPU was verified idle after completion; user allocations were not cancelled. CPU selection, helpers and judging ran in bounded steps of allocation 25637145.

The four new run IDs together record estimated settled usage of $0.081772081 and $0.024962750 in retained uncertain reservations, not invoice-reconciled charges. Existing reservations were preserved. The native ledger and exact response evidence remain authoritative.

No website update was made: the live curves still represent the 469-question N1–N32 study. These sparse pilot measurements remain separate. Research Git stays local.

The [case inspection packet](../reviews/larger-n-methods-cases-v1.json) preserves two observed hallucination improvements (best-sample denim and pooled daily-dialogue), the reverse denim label change after pruning, the Adwa multihop bridge loss after pooling, and a seed-selected unchanged role case. It includes exact texts and native result rows. For multihop, a missing bridge at this inspected layer means this site's recovery failed; the upstream whole-question verdict remains undecided because other prescribed layers were not evaluated. None of these post-hoc examples is an independent replication.

## Validation and test access ledger

| UTC | Scope | Outputs inspected | Purpose |
|---|---|---|---|
| 2026-10-13 | Same 32 previously inspected development sites | Fixed candidate pools, original selectors, all 56 measured records and exact source texts | Authorized N64 method comparison; no parameter tuning or test access |
