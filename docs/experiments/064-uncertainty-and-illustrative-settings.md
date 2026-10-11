# Experiment 064 — Explain uncertainty and the seven illustrative settings

## Key findings and status

Complete presentation clarification, published as public version 19 on 2026-10-11 at 13:46 UTC. No new scientific analysis, inference, judging or GPU allocation. All native results, reconstruction data, saved judgments and the original-reference supplement remain unchanged. The presentation source payload changes only its build timestamp. Slides remain those delivered with version 18.

The sampling chart shows uncertainty in each absolute task rate. The intervention chart shows uncertainty in a paired change on the same questions. The first is not a test of the second. Shared question difficulty can cancel in a paired difference; overlapping absolute intervals can coexist with an improvement interval excluding zero.

For all Hallucination (chat) questions, the original released lens has an error rate of 47.63% (pointwise 95% interval 44.20–51.09%). Best-of-32 has 45.82% (42.28–49.37%). The directly paired reduction is 1.80 percentage points (0.42–3.23). This is an individual, exploratory comparison against the raw original. Separately, the frozen many-comparison interval against the four-bullet original includes zero. That adjusted interval must not be attributed to the raw-original comparison, for which no adjusted interval was computed.

## Selection of the seven examples

The dashboard uses the same highlighted conditions as the seven method-result slides, copied from the final root review. The deck also retains other variants in its detailed appendix. These seven were chosen after results for explanation, not by a preregistered rule or a rule selecting each approach's best outcome. They are the same across tasks. The complete 70-setting experimental menu was sealed before expansion judging; the presentation shortlist was not.

| Approach | Exact illustrative setting |
|---|---|
| More samples | `best_n_exact-n32` |
| Keep repeats | `consensus_semantic_v5_support0.125_compaton_vetoon-n16` |
| Remove weak bullets | `prune_loo_a32_0.005-n32` |
| Combine bullets | `pooled_greedy_swap-n32` |
| Control activations | `best_n_specificity_mean-n32` |
| Edit pooled text | `editing_round2-n32` |
| Combine + prune | `pooled_specificity_mean_then_prune_0.005-n32` |

The frozen manifest was committed in `6767b26` and sealed at 00:18 UTC. The native final analysis was produced at 06:41 UTC; the seven final-review comparisons were recorded after that and committed in `1aa1f95` at 07:15 UTC. No outcome-independent selection claim is supported. All 70 settings remain available in the dashboard and slides. Candidate and editing budgets differ and are recorded separately.

## Checks and artifacts

An independent read-only reviewer verified the data, references and selection chronology. Root checked that all seven slide-highlight conditions match the dashboard. JavaScript syntax and actual source-bound browser checks passed in 22 desktop/mobile views; immutable numeric and qualitative objects remained unchanged through the interactions. A selected chart view was visually inspected.

- [Browser review](../reviews/ci-labels-browser-review-v1.json)
- [Public delivery receipt](../reviews/ci-labels-site-delivery-v1.json)
- [Original-reference supplement](../reviews/original-reference-comparisons-v1.json)

The final report's scientific interpretation is unchanged: assess an intervention with its paired difference, use adjusted intervals when discussing selection across many comparisons, and inspect effect size, information recovery, cost and examples. An individual interval excluding zero is not evidence of an established universal winner.
