# Improve pooled readouts using only the current activation

Status: authorized; full-bank CPU selection running after a completed timing pilot and independent review, 2026-10-11.

The user approved testing the next combine-and-prune upgrades. This is an additive follow-up to the completed four-bank study. Earlier data, judgments, reports and source manifests remain immutable. All four banks have already been inspected; the new results are exploratory, not a fresh held-out confirmation.

## Information available to the method

A valid method receives one target activation, the shared 32 Oracle Lens samples generated from that activation, cached matched-reconstructor vectors, frozen whitening statistics and the fixed tokenizer. It may combine existing source bullets, preserving their text. It may not read another example's activation, a control-activation bank, benchmark answers, benchmark identity or judge verdicts to make selection decisions. Administrative family and cell metadata are used only to route inputs and evaluate outputs.

The user's new scope excludes every control-activation method and every combination that uses such controls from current valid-method comparisons. Historical results remain available as out-of-scope diagnostics. In particular, the previous highlighted specificity-based combine-and-prune setting is not the eligible plain-pooling parent used here.

## Small comparison menu

1. **Repeat bullet swaps.** Start from the saved plain pooled-32 result, after its original complete-response fallback. Search for a better one-bullet replacement, refitting reconstruction jointly. Repeat within a fixed numerical-evaluation budget.
2. **Repeat swaps, then prune.** Apply the existing sequential leave-one-out pruning rule to the improved pooled result. Remove a bullet when its refitted contribution is at most 0.005 explained activation variance, then refit again.
3. **Prune and refill.** Start from the plain pooled result, prune weak bullets, and explore bounded additions or replacements from the same sample pool. Keep the best explicitly validated set whose remaining bullets each contribute more than 0.005. Do not force four bullets or restore a weak superset solely because its reconstruction score is higher.
4. **Matched random deletion.** Start from the repeated-swaps parent and randomly remove exactly the number of bullets removed by its guided pruning on that activation. Freeze deterministic seeds. This isolates guided deletion from shortening.

Use at most four bullets and 256 Qwen text tokens, verbatim source text, the same candidate eligibility as plain pooling, and the existing exact nonnegative reconstruction fit. Count unique fitted subsets, cache hits, accepted moves, stop reasons, tokens and bullet counts. Selection tolerance and budget rules are recorded in the sealed configuration before production or new judgment inspection. A timing pilot may adjust resource budgets without inspecting new benchmark outcomes. The initial proposed budget is 2,048 distinct subsets per search, eight accepted swaps and two prune/refill rounds; the sealed configuration is authoritative.

The prune/refill method uses a different constrained objective from unconstrained repeated swaps. Its comparison tests the resulting inference scaffold, not an isolated change to optimization efficiency. A reconstruction contribution is not a truth label.

## Evaluation and independent review

Reuse all 469 questions and 19,435 fixed activation sites across **Hallucination (chat)**, **Multihop (multi-token)**, **Chained intermediates** and **Role-bound association**. Retain both the original released Oracle Lens and the four-bullet original reference. Compare to best-of-32, plain pooled-32, plain pooled-32 plus pruning and its earlier matched deletion control. Report actual-parent changes for each new component.

Use the same frozen WorkspaceBench evaluator and GPT-6 Luna recipe. Cache identical requests; judge changed inputs only. Hallucination evaluation includes both stages and reports the official contradiction endpoint, assertion share, off-topic rate, true claims, false spans, unverifiable claims and empty outputs. The other tasks retain their original question-level recovery rules; site-level recovery and reconstruction are secondary.

Freeze a small named comparison family before viewing new outcomes. Report grouped paired pointwise and simultaneous confidence intervals, counts, denominators, output lengths and compute costs. The original 70-setting analysis is not replaced or retroactively reclassified as a new held-out study. Audit representative gains, regressions and randomly sampled unchanged cases, using independent Sol 6.1 reviewers.

## Resources and spending

Reuse cached generation and phrase encoding; no new GPU allocation is needed for this menu. Run heavy CPU work through Slurm, using the existing 32-CPU/128-GiB allocation if available. Start with a small diverse timing and numerical-replay pilot, then choose worker count from measured throughput and memory. Preserve unrelated user jobs.

The existing project API ceiling remains $340, with a preferred total below $200. The live pre-dispatch ledger check estimated $142.7286 usage and $5.0685 retained reservations on 2026-10-11. These are usage-derived estimates, not invoice charges. The proposed new run ceiling is $30 within the existing project ceiling, conditional on the exact cache-miss forecast. Preserve all uncertain-charge reservations. Use the already validated bounded high-concurrency Standard Luna transport when it fits this forecast.

Large outputs go under the existing project compute/data storage, not Git. Record compact provenance, source hashes, job identities, storage growth, runtime and API accounting. Commit locally; the user handles pushing.

## Delivery

Produce an additive experiment record, source-bound results and a clear visual comparison against the original Oracle Lens and actual parents. Update the dashboard's current valid-method scope and provide a compact slide supplement for the upgrades. Preserve historical artifacts and clearly label excluded control-activation diagnostics. Do not present a numerical reconstruction improvement as an established faithfulness improvement.
