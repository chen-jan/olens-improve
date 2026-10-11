# Extra bullet search adds little reconstruction and no established quality gain

Oracle Lens describes a model's internal activation as a short list of text bullets. We test whether searching more combinations of those bullets improves the descriptions. Reconstruction measures how well the frozen model's predictions from those bullets reproduce the activation; it does not measure factual accuracy.

All four new methods ran on the complete four-bank cohort: **469 questions and 19,435 fixed reading sites**, each a token position at a model layer. They reused the same 32 samples per site and frozen phrase vectors. Selection saw only the current activation and its own sampled bullets. No control activations, prompts or correct answers were available to selection.

Repeated swaps raise observed role recovery from 81 to 84 questions out of 100 relative to plain pooling. Their adjusted interval still includes no improvement. Pruning reduces the measured contradiction rate, but matched random deletion achieves almost the same reduction. Prune-and-refill adds bullets at only 1.3% of sites and offers no established improvement over plain pruning. These results leave different quality tradeoffs across tasks, with no method established to improve every task.

The questions were inspected in the earlier study, so these results are **exploratory**. This is the whole agreed four-bank cohort, not the entire WorkspaceBench suite.

## Full-bank measured results

The table preserves the original released Oracle Lens as a separate reference. Its four-bullet version is the same sample capped deterministically. Each new method emits at most four intact source bullets and 256 Qwen tokens. The original raw output is exempt from that cap.

| Method | Hallucination (chat) ↓ | Multihop (multi-token) ↑ | Chained intermediates ↑ | Role-bound association ↑ |
|---|---:|---:|---:|---:|
| Original released Oracle Lens | 47.63% (2,648/5,560) | 34/100 | 59/120 | 78/100 |
| Original, four bullets | 47.55% (2,641/5,554) | 34/100 | 57/120 | 78/100 |
| Best complete sample / 32 | 45.82% (2,550/5,565) | 40/100 | 61/120 | 77/100 |
| Plain pooled / 32 | 47.18% (2,621/5,555) | 41/100 | 53/120 | 81/100 |
| Plain pool, then prune | 44.51% (2,474/5,558) | 39/100 | 55/120 | 80/100 |
| Plain pool, random deletion | 43.95% (2,441/5,554) | 39/100 | 54/120 | 82/100 |
| Repeat bullet swaps | 47.10% (2,615/5,552) | 41/100 | 51/120 | 84/100 |
| Repeat swaps, then prune | 44.48% (2,472/5,557) | 38/100 | 53/120 | 84/100 |
| Prune and refill | 44.72% (2,487/5,561) | 38/100 | 53/120 | 83/100 |
| Repeat swaps, random deletion | 44.51% (2,471/5,552) | 36/100 | 51/120 | 84/100 |

Hallucination (chat) divides contradicted readouts by the total labeled contradicted, off-topic or consistent; lower is better. Generic and revoked outputs are excluded, so denominators vary slightly by method across the 5,615 intended sites. The other tasks count questions with at least one successful readout at the prescribed sites: required bridge names together for Multihop (multi-token), an accepted first-ranked intermediate number for Chained intermediates, and the required entity-role relation for Role-bound association. A successful name, number or binding can occur inside otherwise inaccurate prose.

## What each added step does

**Repeat bullet swaps** starts from the saved plain pooled result, including its complete-response fallback. It tries one-bullet replacements and refits the complete set jointly. Final text changes at 2,342 of 19,435 sites, with unchanged bullet count everywhere. Mean reconstruction rises by **0.0177 percentage points** across sites. Role recovery rises by three questions, name recovery stays at 41, and number recovery falls by two. Extra local search has no established quality advantage over plain pooling.

**Repeat swaps, then prune** removes the bullet whose deletion reduces reconstruction least and recalculates the fit after every deletion. The threshold is 0.005 explained activation variance, or 0.5 percentage points per bullet, with a fixed numerical tolerance. It changes 68.44% of sites and reduces mean bullet count from 3.994 to 2.911 across the cohort. Its measured contradiction rate falls from 47.10% to 44.48%. Name recovery falls from 41 to 38 questions. The lower contradiction rate comes with fewer questions recovering the required bridge names.

**Matched random deletion** starts from that same repeated-swaps parent and keeps exactly as many bullets as guided pruning at every site. It reaches 44.51% contradictions, almost identical to guided pruning's 44.48%. Guided pruning preserves more reconstruction: mean losses are 0.261 versus 1.061 percentage points for random deletion. That reconstruction advantage does not establish a correctness advantage. Their token lengths remain slightly different.

**Prune and refill** starts by pruning plain pooling, then explores bounded additions and replacements from the same pool. Every retained bullet must exceed the contribution threshold. It keeps the highest-scoring set it actually tested that satisfies the threshold and permits fewer than four bullets. Compared with plain pruning, 14.65% of sites change text; 13.38% keep the same bullet count with different wording, and only 1.26% gain bullets. Mean count changes from 2.898 to 2.910. Reconstruction rises by **0.0238 percentage points**, but contradictions rise slightly, names and numbers fall, and role recovery improves by three questions. In this experiment, refilling mainly replaces bullets.

The pooled-site behavior averages above are descriptive and weight each reading site equally; they are not an average quality score across tasks. The downloadable behavior record also gives every family separately.

## Paired uncertainty

We froze 11 named comparisons across four endpoints before inspecting the new judgments. We resampled the benchmark's original question groups 10,000 times, comparing methods on the same groups in each draw. We report ordinary 95% intervals and adjusted intervals accounting for the **44 declared comparisons** together. Forty comparisons have nonzero variation and adjusted intervals. Four have zero variation and retain warnings without an adjusted interval; this is not evidence of certainty. This adjustment does not cover the earlier adaptive research history or supplementary outcomes.

For repeated swaps versus plain pooling, role recovery changes by +3 percentage points, with a simultaneous interval of **−2.39 to +8.39 points**. For guided pruning versus matched random deletion, contradiction changes by −0.022 points, with an interval of **−1.39 to +1.34 points**. Prune-and-refill's role gain over plain pruning is +3 points, with an interval of **−2.34 to +8.34 points**. These comparisons remain unresolved.

Repeated swaps followed by pruning lowers measured contradictions relative to the original released lens by 3.14 points, with an interval of **−5.58 to −0.71 points**. Matched random deletion lowers them by 3.12 points, with an interval of **−5.59 to −0.65 points**. Both methods have lower observed contradiction rates on this cohort, with adjusted intervals excluding zero. Their near-identical rates do not establish a correctness benefit from choosing deletions by reconstruction score.

## What the exact readouts reveal

Three Sol 6.1 reviewers separately inspected partitions covering all **64 selected case entries**, including gains, regressions, question-level witnesses and seeded unchanged examples. These examples illustrate failure mechanisms and judge behavior; they do not estimate their prevalence.

Swaps sometimes insert a needed bridge name such as Menelik II. Pruning can delete the only full Constantin Brâncuși name or the only required praise relationship. Refilling can clarify a role description, but a recovered intermediate such as 7 can still appear in an incorrect calculation. These cases separate benchmark recovery from the truth of surrounding prose.

Some Hallucination labels change even when the quote flagged in the parent survives unchanged. For example, a pruning “win” retains “I'm happily married to my algorithms!” and removes a different follow-up bullet; the official label changes from hallucinated to consistent. Guided and matched random deletion produce the same text in that case. Several role or number verdicts also depend on how the judge extracts names or values. The report preserves the official scores and flags these examples rather than treating every label change as a factual repair.

The matched reconstructor scores only the first 32 tokens of each bullet under the frozen released convention. Around 7.4% of selected bullets in the pruned methods have longer tails. Luna sees their complete text. This is a scoring limitation; these observations alone do not establish that truncation caused a particular error.

## Cost, reproducibility and practical conclusion

This follow-up used **no new GPU inference or model training**. Additional Standard Luna usage is estimated at **$2.03**; the four-family evaluation finished in **195 seconds**. The project total is **$144.76** in recorded usage plus **$5.07** in retained uncertain reservations. These estimates are not invoice-reconciled charges.

The dated storage snapshot records **2.55 GB logical / 0.72 GB allocated blocks** for the follow-up and **125.92 GB logical / 95.15 GB allocated blocks** across the scoped project roots. External shared model weights are excluded. CPU search took 56 minutes from first launch through completion, including a corrected CPU-placement error and an interruption resumed from committed progress. Selection consumed approximately 7.10 process CPU-hours. The inherited user allocation remains available; overlapping step reservations do not represent additional exclusive billing.

All 19,435 sites passed complete provenance, token/bullet-cap, verbatim-text, exact-fit, pruning-threshold and matched-deletion checks. All 40 method–task records have complete frozen evaluator coverage. Heavy work ran in the existing Slurm allocation. New records preserve the previous study and its judgments. Control-activation methods and their combinations remain available only in the explicitly excluded historical archive; independent-reader checks remain postponed.

The strongest practical signal is that the additional local search brings small reconstruction gains and uncertain quality changes. Simple sampling, plain pooling and optional shortening remain useful comparison points. More elaborate search has not earned a claim of generally more faithful readouts. A future confirmation should use new questions and assess judge stability before making stronger faithfulness claims.

The updated dashboard provides four-task graphs, ordinary and simultaneous paired intervals, exact before/after examples and all downloadable records. The 12-slide supplement explains the methods before their results and retains the original Oracle Lens in every task comparison. Earlier sampling curves, variants and the longer deck remain in the historical archive.
