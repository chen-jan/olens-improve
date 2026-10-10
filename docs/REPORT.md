# Improving Oracle Lens with inference-time computation

Final research report, October 10, 2026. The signed twelve-method TEST comparison and the separate whole-bank descriptive analysis are complete. This report preserves the two operating points chosen before TEST: best-of-16 reconstruction selection and matched-control selection from 32 candidates. The [dashboard](../dashboard/index.html) provides the interactive evidence; the experiment records retain exact sources and reviews.

## Main findings

Additional inference computation produces useful local changes, with no clear improvement across all four tasks. On the 268 held-out questions, best-of-16 recovers 18/49 hidden-name questions, 36/70 arithmetic-intermediate questions and 40/50 directed-role questions. The released single sample recovers 15/49, 34/70 and 40/50. Their paired uncertainty intervals include zero. The judged hallucination error rate is almost unchanged: 48.7% versus 48.9%.

Sampling and activation-specific selection give modest gains in hidden-name recovery. Best-of-16 and best-of-32 each recover 18/49 questions; comparing target reconstruction with other activations recovers 19/49. That last difference is one question over best-of-32, with a paired change of +2.04 percentage points [0.00, +6.25]. Best-of-32 reduces the judged hallucination rate to 47.2%. A frozen random complete response reaches 46.9%, so this task does not establish an advantage from reconstruction ranking over the sampling control.

Deleting text reduces judged errors and can remove useful information. Pruning best-of-32 lowers its hallucination rate from 47.2% to 41.4%; deleting the same number of bullets at random reaches 39.5%. Targeted pruning is 1.96 percentage points worse than that control [+0.44, +3.50]. It also loses five hidden-name questions, falling from 18/49 to 13/49. The matched controls make shortening a central explanation for the lower error rate.

A benchmark pass captures a limited kind of recovery. Required names can appear alongside incorrect alternatives; a credited intermediate can sit inside wrong arithmetic; a correct abstract role can coexist with invented people or reversed relationships. Independent reviewers inspected fixed wins, regressions and unchanged cases for every reported contrast. Those cases help explain the measurements, and their deliberately selected frequencies do not estimate how common each failure is.

## What the results measure

Question-level recovery leads the three recovery tasks because it follows their original complete read grids. A **cell** is one activation at one layer and token position. A question passes if its task criterion is met somewhere in its fixed grid. Passing sites can be rare even when question coverage is high.

| Task | Original question or readout criterion | What a pass leaves unresolved |
|---|---|---|
| Hidden multi-hop names | Every required bridge matches within one layer across that layer's frozen positions. | Other statements may be wrong. A final target name alone cannot replace a required bridge. |
| Arithmetic intermediates | At any grid layer, the judge's top-named verified integer is a true hidden intermediate. | The rest of the calculation may be wrong; a correct final answer alone is insufficient. |
| Directed roles | At one site, all three agent/action/patient choices are correct. Names or role descriptions are permitted. | Invented names, contradictory bullets and extra events may remain. Answers from separate sites are never combined. |
| Transcript contradictions | Wrong readouts divided by specific readouts, over the original grid. Specific includes hallucinated, consistent and off-topic outputs. | This is a readout error rate. Its complement is not the proportion of fully correct explanations. |

The three recovery families use the original any-site question aggregation. Multi-hop uses the released deterministic matching rule. GPT-6 Luna, with reasoning fixed to `none`, supplies the chain, role and hallucination judgments. This is a pinned WorkspaceBench adaptation with the same banks, grids and aggregation; language-model-judged values are not direct reproductions of another judge's published scores. The multi-hop headline preserves the released regex rule rather than replacing it with historical optional multiple-choice judging.

Hallucination's denominator excludes generic and empty outputs. We therefore report assertion coverage, off-topic outputs, output length and supported-claim tallies alongside its error rate. False spans and true/unverifiable claims have different segmentation. They cannot be combined into claim accuracy. The second stage receives the first stage's wrong spans as established false, so its false-span tally is not an independent confirmation of the wrong labels.

## Cohorts and uncertainty

All four released banks in the frozen study are covered. Related questions, arithmetic templates and role reversals stay together in development, validation and TEST. The full-bank union is analyzed separately because development and validation informed method design.

| Cohort | Questions/items | Cells | Purpose |
|---|---:|---:|---|
| Small development pilot | 31 | 189 | Method iteration and targeted failure diagnosis; partial grids |
| Full development | 121 | 5,236 | Complete scaling curves and larger descriptive comparisons |
| Validation | 80 | 3,485 | Twelve prospectively fixed candidates; selection of at most two operating points |
| Held-out TEST | 268 | 10,714 | Final frozen twelve-method comparison |
| Whole-bank union | 469 | 19,435 | Descriptive DEV + VAL + TEST appendix |

The pilot is a subset of development. The complete question counts and independent related groups differ by task:

| Task | DEV items/groups | VAL items/groups | TEST items/groups | TEST cells |
|---|---:|---:|---:|---:|
| Transcript contradictions | 30/30 | 20/20 | 99/99 | 3,705 |
| Hidden multi-hop names | 31/29 | 20/17 | 49/48 | 539 |
| Arithmetic intermediates | 30/7 | 20/7 | 70/28 | 770 |
| Directed roles | 30/15 | 20/10 | 50/25 | 5,700 |

All reported 95% intervals use 2,000 bootstrap draws of whole related groups. Paired intervals resample the same groups for both methods and compute the difference within each draw. Hallucination uses the ratio of summed wrong and specific readouts. Question rates use passing items divided by intended items. Thousands of correlated cells do not create thousands of independent questions.

Intervals are pointwise and unadjusted for the many contrasts and endpoints examined. They describe uncertainty over these benchmark groups; they do not separately include rerunning the generator or judge. An interval touching zero is compatible with useful effects and does not prove equivalence. We report observed changes, regressions, costs and examples together. We use neither a significance gate nor an average of unlike task scores to declare a winner.

## The twelve held-out methods

Every method reads the same frozen activation. Each cell has a shared pool of 32 sampled descriptions. A16 and A32 use nested prefixes of that pool. Improved outputs contain at most four intact source bullets and 256 Qwen text tokens. The released baseline retains its 256-new-token generation limit. Its unmodified text remains available separately from a downstream capped baseline, so formatting and eligibility changes can be distinguished from search.

| Label | Procedure | Status in the final comparison |
|---|---|---|
| Released N1 | Original first sample, without the downstream bullet-selection cap | Primary baseline |
| Capped N1 | Same first sample under the four-bullet/256-text-token policy | Primary budget control |
| A16 | Select the complete candidate with the highest exact joint reconstruction fit among the first 16 | Preselected operating point; primary |
| A32 | The same complete-candidate selector among 32 | Primary sampling-budget control |
| Random complete, N32 | One frozen uniformly drawn eligible complete candidate from the same pool | Primary sampling control |
| E32 | Select by target reconstruction fit minus mean fit to eight frozen matched control activations | Preselected operating point; primary |
| D16 / D32 | Pool source bullets, greedily refit their nonnegative weights, then make a bounded local swap | Secondary pooling comparisons |
| E32 + pruning | Repeatedly delete a whole bullet with at most .005 reconstruction loss per step | Secondary combination |
| E32 + matched deletion | Random deletion from the same parent, retaining the targeted arm's bullet count | Secondary shortening control |
| A32 + pruning | Apply the same deletion rule to A32 | Secondary component comparison |
| A32 + matched deletion | The corresponding matched-count random deletion | Secondary shortening control |

The original six primary comparisons were frozen after validation. A prospective amendment added the other six existing validation variants before TEST judging or deliberate quality inspection. It preserved the original primary designation, A16/E32 operating points, thresholds, seeds and cells. The amendment addresses uncertainty from only twenty validation items per family; it does not imply that methods omitted from this twelve-arm menu are inferior.

The .005 pruning threshold permits an absolute loss of 0.5 percentage points of FVE **per sequential deletion**. Each deletion refits the remaining bullets. The threshold is neither a total loss budget nor a truth test. All random choices use their frozen seed and source-derived identity; neither these choices nor the threshold was fitted to TEST.

## Held-out question results

The table gives count/denominator, percentage and a grouped 95% interval. Higher question recovery is better. Lower hallucination error is better; that column keeps its native readout denominator. All twelve methods have complete intended coverage, including both hallucination stages. Failed transport attempts were repaired cache-aware or retained financially; they are never counted as successful abstentions.

| Method | Hallucination error ↓ | Bridge questions ↑ | Intermediate questions ↑ | Role questions ↑ |
|---|---:|---:|---:|---:|
| Released N1 | 1791/3664; 48.9% [44.6, 53.4] | 15/49; 30.6% [18.4, 44.9] | 34/70; 48.6% [35.4, 62.3] | 40/50; 80.0% [70.0, 90.0] |
| Capped N1 | 1785/3656; 48.8% [44.5, 53.4] | 15/49; 30.6% [18.4, 44.9] | 34/70; 48.6% [34.6, 62.9] | 40/50; 80.0% [70.0, 90.0] |
| A16: best complete | 1784/3661; 48.7% [44.2, 53.1] | 18/49; 36.7% [23.1, 50.0] | 36/70; 51.4% [35.0, 67.1] | 40/50; 80.0% [70.0, 90.0] |
| A32: best complete | 1728/3663; 47.2% [42.7, 51.6] | 18/49; 36.7% [22.9, 52.0] | 34/70; 48.6% [34.7, 62.1] | 38/50; 76.0% [66.0, 86.0] |
| Random complete, N32 | 1715/3654; 46.9% [42.6, 51.2] | 17/49; 34.7% [22.0, 49.0] | 29/70; 41.4% [28.6, 55.7] | 39/50; 78.0% [68.0, 88.0] |
| E32: matched controls | 1730/3663; 47.2% [43.0, 51.6] | 19/49; 38.8% [24.5, 53.1] | 34/70; 48.6% [35.5, 62.2] | 38/50; 76.0% [64.0, 86.0] |
| D16: pooled + swaps | 1799/3658; 49.2% [44.7, 53.5] | 18/49; 36.7% [22.9, 52.1] | 34/70; 48.6% [33.3, 64.2] | 41/50; 82.0% [72.0, 90.0] |
| D32: pooled + swaps | 1787/3662; 48.8% [44.5, 53.1] | 18/49; 36.7% [22.9, 52.1] | 33/70; 47.1% [33.3, 61.6] | 41/50; 82.0% [72.0, 92.0] |
| E32 + pruning | 1514/3670; 41.3% [36.6, 45.9] | 14/49; 28.6% [16.3, 42.0] | 33/70; 47.1% [32.4, 61.7] | 39/50; 78.0% [68.0, 88.0] |
| E32 + matched deletion | 1474/3620; 40.7% [36.3, 45.0] | 14/49; 28.6% [16.3, 41.7] | 25/70; 35.7% [23.2, 49.3] | 38/50; 76.0% [66.0, 86.0] |
| A32 + pruning | 1521/3670; 41.4% [36.7, 46.1] | 13/49; 26.5% [14.6, 39.6] | 36/70; 51.4% [37.0, 66.1] | 39/50; 78.0% [68.0, 88.0] |
| A32 + matched deletion | 1433/3629; 39.5% [35.1, 44.0] | 16/49; 32.7% [20.0, 45.8] | 38/70; 54.3% [39.4, 68.5] | 42/50; 84.0% [74.0, 94.0] |

A16's bridge gain over capped N1 is three questions, +6.12 percentage points [−2.08, +14.58]. Its chain gain is two questions, +2.86 [−10.45, +16.67]. Role question coverage is unchanged, with paired change 0.00 [−6.00, +6.00]. These observed changes support A16 as a measured lower-sample operating point, with uncertain gains and no established cross-task superiority.

E32 recovers four more bridge questions than capped N1, +8.16 points [0.00, +18.37]. Relative to A32 it adds one bridge question and leaves chain and role question counts unchanged. Its hallucination difference from A32 is +0.05 points [−0.47, +0.58]. E32 remains the prospectively chosen activation-specific comparator; this TEST result does not justify promoting a new winner.

Pooling reaches 41/50 role questions at both N16 and N32, compared with 40/50 for capped N1. The paired change is +2.00 points [−6.00, +10.00]. D32 also increases passing role cells relative to A32, but a cell-level advantage does not establish a question-level or complete-explanation improvement. The pooled bridge counts equal A16/A32, and its arithmetic counts are 34/70 and 33/70.

The next table reports all changes against capped N1. Entries are **percentage-point changes [paired 95% interval]**, calculated directly from the signed analysis. Marginal intervals in the previous table must not be subtracted to obtain a paired interval.

| Method minus capped N1 | Hallucination error | Bridge question recovery | Intermediate question recovery | Role question recovery |
|---|---:|---:|---:|---:|
| Released N1 | +0.06 [-0.31, +0.44] | +0.00 [+0.00, +0.00] | +0.00 [-4.11, +4.17] | +0.00 [+0.00, +0.00] |
| A16: best complete | -0.09 [-1.72, +1.52] | +6.12 [-2.08, +14.58] | +2.86 [-10.45, +16.67] | +0.00 [-6.00, +6.00] |
| A32: best complete | -1.65 [-3.33, -0.01] | +6.12 [-2.08, +14.58] | +0.00 [-12.70, +13.16] | -4.00 [-12.00, +4.00] |
| Random complete, N32 | -1.89 [-3.79, -0.13] | +4.08 [+0.00, +10.20] | -7.14 [-20.78, +6.94] | -2.00 [-6.00, +0.00] |
| E32: matched controls | -1.59 [-3.26, +0.12] | +8.16 [+0.00, +18.37] | +0.00 [-11.11, +10.53] | -4.00 [-14.00, +4.00] |
| D16: pooled + swaps | +0.36 [-1.47, +2.29] | +6.12 [-2.08, +16.00] | +0.00 [-13.24, +13.04] | +2.00 [-6.00, +10.00] |
| D32: pooled + swaps | -0.03 [-1.84, +1.89] | +6.12 [-2.08, +14.58] | -1.43 [-14.75, +12.33] | +2.00 [-6.00, +10.00] |
| E32 + pruning | -7.57 [-9.81, -5.37] | -2.04 [-12.50, +8.16] | -1.43 [-14.49, +11.59] | -2.00 [-10.00, +6.00] |
| E32 + matched deletion | -8.11 [-10.09, -6.17] | -2.04 [-12.50, +8.16] | -12.86 [-25.76, +0.00] | -4.00 [-14.00, +6.00] |
| A32 + pruning | -7.38 [-9.57, -5.30] | -4.08 [-14.29, +4.17] | +2.86 [-8.33, +14.49] | -2.00 [-8.00, +4.00] |
| A32 + matched deletion | -9.34 [-11.48, -7.23] | +2.04 [-6.25, +10.42] | +5.71 [-6.06, +17.46] | +4.00 [+0.00, +10.00] |

## Shortening and component comparisons

The strongest apparent hallucination improvement comes from deleting content. Both targeted pruning arms lose five bridge questions from their respective complete parents. Each parent-to-prune change is −10.20 percentage points [−20.00, −2.08]. E32 pruning and its random control both recover 14/49 bridge questions; A32 pruning recovers 13/49 versus 16/49 for its random control.

There is a real task-specific contrast in chains: E32 pruning recovers 33/70 questions versus 25/70 for matched random deletion, +11.43 points [+1.45, +22.73]. Its unpruned parent recovers 34/70. Preserving more information than a damaged deletion control therefore does not establish improvement over the complete parent. A32 pruning recovers 36/70 versus 38/70 for its matched deletion control.

The component table makes those tradeoffs explicit. It also shows that increasing A16 to A32 improves the judged hallucination rate while leaving bridge question coverage unchanged and reducing chain and role question counts. Every change refers to the exact paired outputs, with no TEST-driven threshold changes.

| Baseline → proposed | Hallucination error | Bridge question recovery | Intermediate question recovery | Role question recovery |
|---|---:|---:|---:|---:|
| A16: best complete → A32: best complete | -1.56 [-2.56, -0.53] | +0.00 [-8.16, +8.16] | -2.86 [-12.33, +6.76] | -4.00 [-10.00, +0.00] |
| A32: best complete → Random complete, N32 | -0.24 [-1.99, +1.44] | -2.04 [-10.42, +6.25] | -7.14 [-22.73, +8.22] | +2.00 [-4.00, +8.00] |
| A32: best complete → E32: matched controls | +0.05 [-0.47, +0.58] | +2.04 [+0.00, +6.25] | +0.00 [-9.23, +8.96] | +0.00 [-6.00, +6.00] |
| A16: best complete → D16: pooled + swaps | +0.45 [-1.34, +2.31] | +0.00 [-10.20, +10.42] | -2.86 [-14.86, +10.34] | +2.00 [-6.00, +10.00] |
| A32: best complete → D32: pooled + swaps | +1.62 [-0.26, +3.40] | +0.00 [-10.42, +10.00] | -1.43 [-14.06, +10.96] | +6.00 [-2.00, +14.00] |
| E32: matched controls → E32 + pruning | -5.98 [-7.86, -4.14] | -10.20 [-20.00, -2.08] | -1.43 [-10.26, +7.69] | +2.00 [-4.00, +8.00] |
| E32: matched controls → E32 + matched deletion | -6.51 [-8.47, -4.66] | -10.20 [-20.00, -2.08] | -12.86 [-25.37, +1.32] | +0.00 [-8.00, +8.00] |
| E32 + matched deletion → E32 + pruning | +0.54 [-0.90, +2.06] | +0.00 [-6.12, +6.12] | +11.43 [+1.45, +22.73] | +2.00 [-4.00, +8.00] |
| A32: best complete → A32 + pruning | -5.73 [-7.52, -3.96] | -10.20 [-20.00, -2.08] | +2.86 [-4.76, +10.61] | +2.00 [-4.00, +10.00] |
| A32: best complete → A32 + matched deletion | -7.69 [-9.50, -5.94] | -4.08 [-10.42, +0.00] | +5.71 [-5.26, +17.33] | +8.00 [+0.00, +18.00] |
| A32 + matched deletion → A32 + pruning | +1.96 [+0.44, +3.50] | -6.12 [-16.00, +2.04] | -2.86 [-11.94, +5.56] | -6.00 [-12.00, +0.00] |
| A32 + pruning → E32 + pruning | -0.19 [-0.67, +0.30] | +2.04 [+0.00, +6.25] | -4.29 [-13.89, +4.48] | +0.00 [-6.00, +6.00] |

Random deletion matches bullet count, rather than exact token length. In hallucination, targeted pruning retains about 2.2 bullets and 59 tokens per output; its controls retain the same average bullet count and about 56–57 tokens. Targeted pruning still yields specific readouts at 3,670/3,705 sites. Its lower error rate cannot be explained solely by generic or empty readouts leaving the denominator. It does, however, remove substantial content, including supported claims. The controls demonstrate why saying less and selecting more truthful content need separate evaluation.

| Method | Specific / 3,705 | Off-topic / specific | True claims / output | Tokens / bullets, mean |
|---|---:|---:|---:|---:|
| Released N1 | 3664/3,705 (98.9%) | 379/3664 (10.3%) | 1.84 | 103.0 / 4.00 |
| Capped N1 | 3656/3,705 (98.7%) | 369/3656 (10.1%) | 1.82 | 101.7 / 4.00 |
| A16: best complete | 3661/3,705 (98.8%) | 358/3661 (9.8%) | 1.86 | 102.3 / 4.00 |
| A32: best complete | 3663/3,705 (98.9%) | 344/3663 (9.4%) | 1.87 | 102.4 / 4.00 |
| Random complete, N32 | 3654/3,705 (98.6%) | 399/3654 (10.9%) | 1.85 | 101.7 / 4.00 |
| E32: matched controls | 3663/3,705 (98.9%) | 346/3663 (9.4%) | 1.87 | 102.5 / 4.00 |
| D16: pooled + swaps | 3658/3,705 (98.7%) | 338/3658 (9.2%) | 1.85 | 108.5 / 3.99 |
| D32: pooled + swaps | 3662/3,705 (98.8%) | 347/3662 (9.5%) | 1.88 | 109.6 / 4.00 |
| E32 + pruning | 3670/3,705 (99.1%) | 266/3670 (7.2%) | 1.23 | 58.8 / 2.20 |
| E32 + matched deletion | 3620/3,705 (97.7%) | 237/3620 (6.5%) | 1.21 | 56.6 / 2.20 |
| A32 + pruning | 3670/3,705 (99.1%) | 261/3670 (7.1%) | 1.24 | 58.8 / 2.20 |
| A32 + matched deletion | 3629/3,705 (97.9%) | 235/3629 (6.5%) | 1.22 | 56.5 / 2.20 |

Supported-claim means are judge-produced tallies per intended output, including outputs without a specific assertion. Their decline from about 1.87 to 1.23–1.24 after targeted pruning accompanies the lower error rate. A lower wrong count is useful information about the retained text, with an explicit cost in how much that text says.

## What changes in individual explanations

The fixed final review inspected the first retained example in every nonempty win, regression and unchanged category of all 37 unique contrasts. Hallucination also includes separate class-change categories. Three reviewers covered 196 hallucination references, 212 chain/multi-hop references and 111 role references. Duplicate evidence is linked to each contrast; related examples are not independent observations. The [hallucination review](experiments/051-test-hall-review.md), [chain/multi-hop review](experiments/052-test-chain-multihop-review.md) and [role review](experiments/053-test-role-review.md) retain exact cell and artifact references.

**Useful bridge recovery can remain incomplete.** At `mhh-1976philadelphia-bacterium`, L44 p28, E32 adds the required Legionnaires' disease name and a correct disease relation. Competing organism and location claims survive. At `mhh-1975-kit-chip-designer`, L52 p30, A16 recovers the required bridge amid incompatible designer alternatives. These are useful name-recovery changes with limits on the surrounding explanation.

**Deletion can remove the concept needed for the task.** At `mhh-1973-triple-crown-stud-farm`, L56 p33, pruning removes Secretariat but leaves Claiborne Farm. A plausible final target remains, yet the required bridge disappears. This illustrates how pruning can lose bridge coverage.

**Some local calculations improve; other credited numbers are misleading.** At `chain-d2p-0227`, L48 p62, a pruned output correctly describes doubling 8 to get 16 and subtracting 2 to get 14, removing conflicting alternatives. At L32 p62, another retained output says “16.50”; the judge extracts 16 and the official criterion credits it. The recorded pass is preserved with the disputed numerical interpretation. A recovered integer alone cannot verify the calculation.

**Role descriptions can recover direction alongside invented details.** At `oa-accountant-client-deceive-ab`, L44 p143, A16 removes a conflicting client name and helps map accountant/client descriptions to the answer options. At L52 p146, E32 includes one reversed-role bullet and invented names alongside repeated accountant-to-client cues. Other audited cases have a returned choice that conflicts with the judge's own rationale. These distinctions matter because the prompt legitimately permits role descriptions without exact names.

**A changed hallucination label can leave the disputed content unchanged.** At `chat-dailydialog-0034`, L60 p47, raw and capped outputs differ only in whitespace but change from wrong to consistent. At `chat-dailydialog-0000`, L20 p38, pruning retains the same AI no-sleep/no-personal-life phrase that receives a new wrong flag. At L20 p23, deletion removes a denial that an AI has children, although that denial is compatible with the source. The pinned judging prompt tolerates reformatting, compatible extra detail and broken fragments. These examples illustrate label sensitivity without estimating its prevalence.

There are also clear company, address and architecture substitutions in the fixed hallucination cases. Removing an invented London apartment can be a useful local deletion, even when an unsupported partner statement survives. An accepted remnant saying little more than “Here is how we handle it” provides little explanatory content. Empty outputs abstain entirely. We preserve all these official verdicts and explain what changed, rather than treating every favorable class transition as a corrected explanation.

## Cell-level results

Question and cell metrics answer different questions. A question can pass after one successful site even when almost all its descriptions fail. D32, for example, has 269/5,700 role passes and 41/50 passing questions; A16 has 253/5,700 and 40/50. More passing sites within an already recovered question can improve the cell metric without changing question coverage.

The table reports passing cells, percentages and grouped 95% intervals. Hallucination's readout endpoint and its coverage already appear above.

| Method | Bridge cells / 539 | Intermediate cells / 770 | Role cells / 5,700 |
|---|---:|---:|---:|
| Released N1 | 51/539; 9.5% [4.6, 15.0] | 52/770; 6.8% [4.6, 9.1] | 256/5700; 4.5% [3.4, 5.6] |
| Capped N1 | 51/539; 9.5% [4.6, 15.0] | 52/770; 6.8% [4.5, 9.2] | 254/5700; 4.5% [3.4, 5.6] |
| A16: best complete | 55/539; 10.2% [5.3, 16.1] | 58/770; 7.5% [5.0, 10.1] | 253/5700; 4.4% [3.1, 5.9] |
| A32: best complete | 57/539; 10.6% [5.9, 16.0] | 58/770; 7.5% [5.1, 10.1] | 234/5700; 4.1% [2.8, 5.4] |
| Random complete, N32 | 58/539; 10.8% [5.5, 16.5] | 44/770; 5.7% [3.8, 7.9] | 244/5700; 4.3% [3.1, 5.5] |
| E32: matched controls | 59/539; 10.9% [6.1, 16.5] | 48/770; 6.2% [4.3, 8.4] | 234/5700; 4.1% [2.9, 5.4] |
| D16: pooled + swaps | 63/539; 11.7% [6.2, 18.0] | 55/770; 7.1% [4.5, 10.2] | 244/5700; 4.3% [3.2, 5.5] |
| D32: pooled + swaps | 61/539; 11.3% [5.9, 17.6] | 52/770; 6.8% [4.1, 9.8] | 269/5700; 4.7% [3.5, 6.0] |
| E32 + pruning | 39/539; 7.2% [3.6, 11.4] | 62/770; 8.1% [4.9, 11.7] | 217/5700; 3.8% [2.7, 4.9] |
| E32 + matched deletion | 33/539; 6.1% [2.8, 9.7] | 35/770; 4.5% [2.6, 6.9] | 224/5700; 3.9% [2.7, 5.2] |
| A32 + pruning | 38/539; 7.1% [3.5, 11.2] | 61/770; 7.9% [5.0, 11.2] | 215/5700; 3.8% [2.6, 5.0] |
| A32 + matched deletion | 40/539; 7.4% [3.8, 11.9] | 52/770; 6.8% [4.8, 8.8] | 216/5700; 3.8% [2.7, 5.0] |

## Why reconstruction fit needs independent evaluation

The released [Oracle Lens and activation reconstructor](https://huggingface.co/agu18dec/olens_and_ar) are frozen Qwen3.6-27B readers. We capture the same source model activation for every method and make no weight updates. Selectors receive candidate text and activation-based scores, without benchmark answers, transcripts or quality judgments. Matched controls come only from the frozen development bank, excluding related groups and matching family, layer and site type.

The reconstructor predicts an activation direction for each phrase. We center and whiten predictions and target using the released matched statistics, normalize phrase directions and retain target magnitude. Exact SciPy nonnegative least squares fits nonnegative phrase weights. Fraction of variance explained (FVE) measures reconstruction fit. It supplies a selection objective and does not establish the truth of a phrase.

With fixed scores and nested pools, best-of-N's maximum fit cannot decrease as N grows. Pooling retains a best-complete fallback under the same objective and admissible dictionary. Those are properties of the search rules. Semantic quality, required-name recovery and directed relations remain separate empirical measurements.

The encoder sees only the first 32 cleaned tokens of each bullet; the judge sees the complete output. In the all-candidate pilot diagnostic, 1,418/6,048 eligible candidates have at least one unscored suffix. Ranking disagreements occur with and without suffixes. No two different full readouts share an identical complete effective AR-key multiset in that diagnostic, so it provides no direct full-readout collision demonstration. Truncation is a concrete resolution limit, without an established causal attribution for every ranking error.

The small all-candidate diagnostic also exposes missed opportunities: at least one candidate contains a required bridge in 14/24 pilot cells, versus 7/24 selected by A32. This is an evaluation-only availability ceiling. It cannot be used to choose a deployable answer, and a passing candidate can still contain wrong surrounding claims. See [candidate ranking](experiments/012-all-candidate-diagnostic.md).

Numerical reproducibility has limits near small margins. Earlier batch-32 vectors remain immutable; new vectors use the fixed batch-128 convention, common across methods. An expanded batching audit exceeded provisional equivalence limits: maximum FVE drift was .003524, pooled text changed in 2/12 cells and matched-control selection changed in 1/12. Exact SciPy fitting and source-bound caches make the implementation reproducible, with uncertain robustness of tiny score margins and some pruning decisions. The [numerical audit](experiments/018-parallel-ar-cache.md) preserves those findings.

A matched-donor diagnostic tests whether the target activation supplies information beyond task/layer priors. It replaces capped N1 with a frozen donor readout from another related group, matched on family, layer and site type, and judges against the target context. Bridge cell recovery falls from 29/341 to 0/341; role recovery falls from 151/3,420 to 0/3,420. Chain recovery falls from 26/330 to 10/330, showing residual numerical hits. This supports target-specific recovery under the stated control and does not establish that every target-conditioned claim is true.

The same donor control lowers judged hallucination error from 543/1,137 to 25/992, yet 956/1,145 donor outputs are off-topic and only 11 are consistent. Its low error rate reflects largely irrelevant readouts. Frozen donor reuse also couples targets, beyond the dependence captured by target-group intervals. This is a direct reason to show content and coverage beside the headline error rate; see [the matched-donor experiment](experiments/014-matched-donor-readouts.md).

## What all seven approaches contributed

The study explored all seven approach categories, with different levels of evidence. The final twelve-method comparison covers selected A/C/D/E variants and their controls. B and F have judged development pilots; G has numerical/token diagnostics. A completed instrument or a specified method is distinct from a completed held-out quality comparison.

| Approach | Implemented and evaluated work | Scope and result | Remaining limits |
|---|---|---|---|
| **A: complete-sample selection** | Exact reconstruction selection on N1/2/4/8/16/32; raw/capped and random controls | All six prefixes judged on full DEV; A16/A32 and controls judged on VAL and TEST | Quality is task-dependent and nonmonotonic despite improved fit. |
| **B: repeated support** | Exact whole-bullet support, repaired semantic matching, support thresholds, compatibility/veto controls, medium reasoning replay | Judged on the same 189 pilot cells; soft variants lose useful bridge/numerical coverage, strict thresholds mostly abstain | Whole-bullet equivalence has audited false merges; exact-span revision stopped after input-contract failures. No claim that all atomic-claim consensus fails. |
| **C: deletion** | Coefficient/leave-one-out pilots and .005 sequential whole-bullet pruning with matched deletion | Selected parent/combination variants judged on pilot, VAL and TEST | Reconstruction contribution is dispensability for the fit; required bridges and supported details can be deleted. |
| **D: pooled composition** | Fully refitted greedy selection and bounded local swaps from the existing N16/N32 pool | Judged on pilot, VAL and TEST; local mention/role gains coexist with wrong relations | This is greedy NNLS selection, rather than classical OMP's correlation rule. Residual resampling was deferred under the shared 32-sample cap. |
| **E: activation specificity** | Mean matched-control reconstruction, controlled near misses, N8 conditional likelihood and component controls | E32 and deletion variants judged on VAL/TEST; other checks remain development diagnostics | Controls distinguish specificity, not factual truth. Likelihood has no broad pilot advantage; semantic discrimination depends on layer/wording. |
| **F: bounded editing** | Two sequential proposal rounds, fresh encoding, best-state retention and all selected-edit audits | Judged 189-cell pilot; eight final edited winners, with no aggregate recovery gain over D32 | Added completions and one name-surface alteration violate source preservation. More powerful iterative editing remains untested. |
| **G: independent check** | Compatible J++ token-support instrument and adversarial numerical probes | Development numerical evidence; no established improved output selector | Unknown fitting-data overlap prevents clean held-out claims. A second compatible reconstructor and optional layer-42 NLA study were not run. |

**Consensus encountered both coverage and contract problems.** The repaired none-effort semantic helper labels all requested pairs after one successful retry, so its later weak outputs cannot be attributed to missing comparisons alone. Its native .25 support rule empties 178/189 cells. Soft consensus recovers 4/24 bridges and 0/21 intermediates, compared with A16's 9/24 and 3/21. Manual audits find unsafe merges that ignore entity, arithmetic history or qualifications. These are concrete selection/faithfulness issues, rather than exclusion solely for a nonsignificant p-value.

The medium replay reuses exactly 2,685 proposed pairs, obtaining 2,639 valid labels and leaving 46 unknown. Whole-chunk validation rejects inconsistent relation fields; the unknown labels are not negative support. A fresh audit finds a false domain-restriction merge that affects a cluster. Its soft outputs also recover 4/24 bridges and 0/21 intermediates. No dedicated compatibility-phase requests were made, so compatibility-filtered variants retain an explicit coverage caveat. The [consensus record](experiments/015-consensus-pilot.md) and [reasoning replay](experiments/021-medium-consensus-reconfirmation.md) keep these versions separate.

The separate exact-source-span revision tests the atomic-claim idea more directly. An eight-cell audit finds accepted bare-number fragments and unresolved references despite a source-entailment/qualification check. A versioned repair removes some numeric fragments but does not resolve all self-containedness failures. Its planned 32-cell expansion and quality judging were not completed. This is an input-contract failure in that implementation, and a better claim-preserving extraction method remains an open direction. See [the source-span experiment](experiments/024-exact-source-span-consensus.md).

**Editing was iterative within a small bound.** Each of two rounds returns four proposals total across at most two retained states: eight proposals per cell across both rounds. The second round receives the full first-round history; earlier candidates remain available. New strings receive fresh reconstruction vectors and are accepted by the fixed reconstruction objective. Eight of 189 final outputs change: three chain, three hallucination, one bridge and one role output. All eight were inspected. Aggregate bridge/chain/role recovery stays at 10/24, 1/21 and 8/72, and wrong hallucination readouts remain 42. Most selected changes remove formatting or headings while preserving wrong numbers or mixed roles. A name-surface alteration and added fragment completions expose source-preservation failures. This evidence limits promotion of the tested editor, with substantial uncertainty about a better editor or objective. See [editing and rescoring](experiments/010-editing-scoring.md).

**Independent token support has a narrower meaning than semantic verification.** J++ supplies a compatible frozen development reader after coordinate checks. Its token ranking cannot by itself distinguish 16 from a larger number containing the same digits or validate who did what to whom. Fitting-data overlap remains unresolved, so no G output was invented or folded into clean held-out results. The [J++ diagnostic](experiments/006-jpp-development-reader.md) describes engineering coverage and its boundaries.

## Pilot and combination evidence

The shared pilot uses 189 cells from 31 development items and partial grids. These are cell diagnostics with few related groups, rather than the original full-grid question scores. The selected comparisons below retain the same pool and explicit hallucination denominators.

| Method | Wrong / specific | Bridge cells / 24 | Intermediate cells / 21 | Role cells / 72 |
|---|---:|---:|---:|---:|
| Capped N1 | 46/71 | 4 | 0 | 8 |
| A4 | 42/72 | 7 | 1 | 9 |
| A16 | 40/71 | 9 | 3 | 8 |
| A32 | 39/71 | 7 | 3 | 9 |
| Frozen random complete N32 | 38/72 | 8 | 2 | 8 |
| D32 | 42/70 | 10 | 1 | 8 |
| E32 | 38/71 | 7 | 1 | 9 |
| E32 + pruning | 36/72 | 7 | 1 | 12 |
| E32 + matched deletion | 37/72 | 5 | 0 | 7 |

The early E32-pruning pilot looked promising for role recovery. Larger development and validation exposed substantial losses of bridge and numerical coverage, and the final TEST comparisons confirm the need for deletion controls. The pilot therefore motivated experiments without certifying a generally better method. Full pilot intervals remain in [the grouped comparisons](experiments/009-pilot-grouped-comparisons.md).

Combination search was bounded and adaptive. We tested pooling with pruning; specificity with pruning; editing with pruning; support-filtered pooling; pooling with specificity; and the three-part pooling/specificity/pruning method. Each promising combination retained its unchanged parent, component-off alternatives and shortening controls when applicable. This covers concrete combinations, rather than an exhaustive cross-product of every algorithm and threshold.

On the pilot, pooling + specificity + pruning recovers six bridge cells, zero chain cells and twelve role cells, with 39/71 wrong specific readouts. Simpler E32 + pruning recovers seven, one and twelve, with 36/72 wrong. The additional pooling component gives no clear practical advantage in those bounded results. A separate nonpositive-specificity abstention control accounts for the empty-set option; its gaps remain explicit. See [cached combinations and support pooling](experiments/011-cached-combinations.md) and [pooled specificity](experiments/020-pooled-specificity.md).

Conditional-likelihood selection adds local model forwards rather than external helper calls. On the same N8 pilot, target minus control likelihood scores 39/70 wrong specific readouts and 6/24 bridge, 2/21 chain and 8/72 role passes. A8 scores 39/70, 7/24, 2/21 and 7/72. The control-only likelihood proxy scores better on bridge and role, weakening an activation-specific interpretation. Isolated changes and broad intervals keep this as an exploratory component rather than a disproven idea. See [the likelihood pilot](experiments/007-likelihood-pilot.md).

The earlier qualitative review also uses eight outcome-blind anchors shared across runnable methods, two distinct items/groups per family. At most two clearly labeled supplemental changed examples are added per conceptual method or materially distinct variant. Exact source/context and independent checks are recorded in [qualitative coverage](QUALITATIVE_COVERAGE.md). F changes none of these shared anchors; rare edited winners are shown separately. Missing or unrun diagnostics remain visible.

## Inference effort and campaign cost

Every deployment method pays for its required sampling, encoding, fitting and recurring helper work on a new activation. Research cache reuse amortizes those costs across comparisons. Benchmark judging is a separate campaign cost, and its dollars are not a method's deployment inference bill.

| Final method | Candidate generation budget | Reconstruction/helper work beyond capture | Median cached selector seconds per cell, where measured |
|---|---:|---|---:|
| Released/capped N1 | 1 sample | Formatting only; no reconstructor or helper required | Not measured as a selector |
| A16 | 16 samples | Up to 64 retained source-bullet inputs before deduplication; exact fits | 0.00690 |
| A32 | 32 samples | Up to 128 retained source-bullet inputs before deduplication; exact fits | 0.01122 |
| Random complete N32 | Shared 32-sample campaign pool | Fixed eligible draw; no reconstruction objective or helper | Not measured |
| E32 | 32 samples | Same candidate inputs, target and eight frozen-control fits | 0.05908 |
| D16 / D32 | 16 / 32 samples | Up to 64 / 128 source inputs; greedy joint refits and local swaps | D32: 0.23227 |
| A32 + pruning | 32 samples | A32 plus repeated subset refits; no new phrase inputs or helpers | 0.01232 including parent |
| A32 + matched deletion | 32 samples | Same A32 parent plus seeded matched-count deletion | Not measured |
| E32 + pruning | 32 samples | E32 plus repeated subset refits; no new phrase inputs or helpers | No isolated measurement |
| E32 + matched deletion | 32 samples | Same E32 parent plus seeded matched-count deletion | No isolated measurement |

These twelve methods require zero recurring language-model helper calls. The cached times are medians from eight fixed DEV cells, three repetitions and four CPU threads, measured after parsing/vector preparation. They exclude model loading, activation capture, sampling and encoding. The 64/128 phrase bounds apply after the four-bullet cap; raw prose can contain more bullet markers. Random complete selection uses one retained candidate, but a standalone implementation may need resampling to satisfy eligibility. The experimental control's N32 pool should not be presented as a guaranteed one-draw deployment cost.

Measured larger-development collection averaged about 4.33 H200 task wall-seconds per N32 cell, with filled batches. Phrase encoding implied about 1.25 further task seconds per cell at the measured throughput. These averages depend on batching, deduplication and startup. They are not single-input latency guarantees or directly measured N16 serving time.

One synthetic installed-tool input provides a separate practical timing. With the model loaded, capture took 0.30 seconds and 32 descriptions took 12.04 seconds. Starting without a model loaded in the process, the complete pipeline through its first selected description took 59.59 seconds, including sequential model loads and 128 phrase encodings. Encoding took 1.34 seconds within that total. This is one engineering input using existing filesystem caches, not a latency distribution. Nested times must not be added twice. See [new-input timing](experiments/035-new-input-timing.md).

Pilot runtime helpers have additional recurring costs. Repaired none-effort B costs about $0.00101 per cell. Medium confirmation costs about $0.00196 per cell after including the necessary proposal phase, even though the campaign reuses it. Two editing rounds cost about $0.000282 per cell, plus the parent method and fresh phrase encodings. N8 conditional likelihood requires 4,536 teacher-forced sequence evaluations on 1,512 candidates and took 176.15 scoring seconds on one H200. These measured components, exact token counts, retries and scope limits are in [measured costs](experiments/013-measured-costs.md). Full fresh-input latency and GPU dollar prices remain unavailable for most variants.

The paid campaign ends with a usage-derived API estimate of **$36.50759506**, plus **$4.8597425 retained reservations**, for **$41.36733756 committed**. The reservations include $4.85435575 in unknown-charge holds and one inactive reservation. No uncertain charge was released. Original full-DEV judging accounts for $7.61822211 estimated usage; final TEST judging accounts for $19.492558205. These runs are subsets of the global figure, so adding them again would double count. Usage estimates include reported cache writes and are not provider-invoice reconciliation.

Project storage at the final inventory is 98.704 GB logical, 79.355 GB allocated and 14,974 files, excluding 55.563 GB of reused external weights. Recorded generation and main reconstructor tasks total 30.192 task-hours. Project-reserved H200 windows total 70.220 GPU-hours, including idle holds, through the 18:10:48 UTC handoff to the user. The two timers measure different things and must not be summed. Capture, separate diagnostics, abandoned work and CPU use are not fully totaled. Cluster prices and Codex/research-agent billing are excluded. The [final resource record](experiments/054-final-resources.md) preserves the dated receipt and all limits.

## Appendix: complete development sampling curves

All six nested prefixes N1/2/4/8/16/32 are judged on all 5,236 DEV cells. The following table shows nonmonotonic quality even as the highest attainable reconstruction fit increases. Late DEV results cannot change the already frozen validation menu or TEST operating points.

| Method | Wrong / specific | Bridge cells / 341 | Chain cells / 330 | Role cells / 3,420 | Bridge questions / 31 | Chain questions / 30 | Role questions / 30 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Released N1 | 545/1136 | 29 | 28 | 155 | 11 | 16 | 23 |
| Capped N1 | 543/1137 | 29 | 26 | 151 | 11 | 15 | 23 |
| A1 | 543/1136 | 29 | 26 | 150 | 11 | 15 | 23 |
| A2 | 554/1139 | 38 | 24 | 160 | 13 | 16 | 23 |
| A4 | 550/1139 | 44 | 20 | 164 | 15 | 16 | 25 |
| A8 | 538/1140 | 45 | 20 | 163 | 13 | 15 | 24 |
| A16 | 542/1141 | 48 | 19 | 185 | 14 | 14 | 24 |
| A32 | 523/1140 | 43 | 30 | 182 | 14 | 19 | 23 |

A32 versus capped N1 changes cell bridge recovery by +4.11 percentage points [+1.82, +6.61] and role recovery by +0.91 [+0.15, +1.73]. Role question coverage stays 23/30. Its chain change is +1.21 [−3.16, +4.85], and hallucination change is −1.88 [−5.42, +1.75]. A16 recovers more bridge and role cells than A32 but fewer arithmetic cells. These exploratory comparisons have only seven independent chain-template groups; they do not establish a scaling law or a universal sample budget.

A1 reconstruction eligibility is distinct from capped N1: it produces one empty hallucination output and eleven empty role outputs for invalid scoring atoms. The baselines preserve their original text. Those differences are an eligibility control, rather than a reconstruction-quality gain. The [complete scaling record](experiments/034-development-scaling-completion.md) contains exact denominators, lengths, absolute/paired intervals and source identity.

The original smaller validation comparison has twenty items per family, with only 17 bridge, 7 chain and 10 role independent groups. A16 recovers 9/20 bridge, 11/20 chain and 17/20 role items; E32 recovers 8/20, 10/20 and 17/20. Validation motivates the two prospective operating points, with broad uncertainty and no claim that excluded approaches are worse. The [validation comparison](experiments/029-validation-comparison.md) retains all twelve arms and their fixed traces.

## Appendix: all 469 questions, descriptive comparison

The full-bank appendix combines 121 DEV, 80 VAL and 268 TEST items, with 19,435 cells and all twelve fixed methods complete. Family totals are 149 hallucination, 100 bridge, 120 chain and 100 role items. It answers how the fixed methods behave across the complete four-bank collection. Development and validation informed their design, so this union is descriptive evidence; the independent held-out comparison remains the 268-item TEST above.

| Method | Hallucination error ↓ | Bridge questions / 100 ↑ | Intermediate questions / 120 ↑ | Role questions / 100 ↑ |
|---|---:|---:|---:|---:|
| Released N1 | 2648/5560 (47.6%) | 34/100 (34.0%) | 59/120 (49.2%) | 78/100 (78.0%) |
| Capped N1 | 2641/5554 (47.6%) | 34/100 (34.0%) | 57/120 (47.5%) | 78/100 (78.0%) |
| A16: best complete | 2633/5564 (47.3%) | 41/100 (41.0%) | 61/120 (50.8%) | 81/100 (81.0%) |
| A32: best complete | 2550/5565 (45.8%) | 40/100 (40.0%) | 61/120 (50.8%) | 77/100 (77.0%) |
| Random complete, N32 | 2572/5556 (46.3%) | 37/100 (37.0%) | 54/120 (45.0%) | 76/100 (76.0%) |
| E32: matched controls | 2550/5566 (45.8%) | 41/100 (41.0%) | 61/120 (50.8%) | 81/100 (81.0%) |
| D16: pooled + swaps | 2647/5558 (47.6%) | 44/100 (44.0%) | 56/120 (46.7%) | 83/100 (83.0%) |
| D32: pooled + swaps | 2621/5555 (47.2%) | 41/100 (41.0%) | 53/120 (44.2%) | 81/100 (81.0%) |
| E32 + pruning | 2252/5567 (40.5%) | 32/100 (32.0%) | 51/120 (42.5%) | 79/100 (79.0%) |
| E32 + matched deletion | 2167/5510 (39.3%) | 31/100 (31.0%) | 53/120 (44.2%) | 77/100 (77.0%) |
| A32 + pruning | 2261/5567 (40.6%) | 31/100 (31.0%) | 56/120 (46.7%) | 76/100 (76.0%) |
| A32 + matched deletion | 2124/5508 (38.6%) | 34/100 (34.0%) | 67/120 (55.8%) | 79/100 (79.0%) |

A16 and E32 each recover 41/100 bridge items in this union. D16 recovers 44/100. Those descriptive counts do not supersede the held-out ranking uncertainty or promote pooling. Pruning again reduces bridge coverage: A32 falls from 40/100 to 31/100, and E32 from 41/100 to 32/100. A32's matched deletion retains 34/100. The complete artifact also preserves stage-specific results, paired group intervals and lengths, so the union cannot hide a task or cohort regression.

Descriptive layer/position maps accompany the complete DEV/VAL comparisons. Position is ranked within each item's read grid; the same rank is not the same absolute token or semantic location across items. The maps show sampled coverage and task rates, with related-group uncertainty where applicable. They are descriptive views of the fixed grids, with no layer or position selected from TEST outcomes.

## Boundaries and reproducibility

The evidence covers four WorkspaceBench families with their full released banks and original grids. Broader WorkspaceBench families remain a separate second-stage study. This study runs no new generations beyond the shared 32-candidate cap, performs no weight training and uses no gold answer in inference selection. The fixed menu is preserved after TEST opening, including secondary variants whose results are less favorable.

The two selected points remain A16 and E32. The results support reporting their tradeoffs and useful local examples, with further evaluation needed before an automatic upgrade across tasks. A better independent semantic scorer, source-preserving claim extraction or editing objective could change the outcome. The current B/F evidence combines small samples with concrete coverage or contract failures; weak evidence does not exclude entire approach categories.

The signed TEST analysis is `final-analysis-v2.json`, SHA256 `75dee255d88104450fa4424610178baa4df24964394be77812fa218379cfcef8`. Its exact frozen menu is [conditions_test_final_v2.json](../configs/conditions_test_final_v2.json), SHA256 `111b0684c8f5eb780e2b3887218757dee9ef6cca25efd26a8c0a515d008f4807`. The [prospective amendment](experiments/038-expanded-heldout-comparison.md) binds the unchanged source pool, ordered cells and primary/secondary status. The original method freeze and inference conventions are in [experiment 032](experiments/032-test-final-method-freeze.md).

The whole-bank descriptive source is `whole-cohort-descriptive-v1.json`, SHA256 `a6510b74fabb410efe859197d295c31ba67bc7274537eeb084c1d16382d5e00f`. The final resource receipt is `final-resources-v1/receipt.json`, SHA256 `07f91cc0508af646bc8f7670a14e0816157d5621bd638f3e025ccb7b7d0d2ee1`. Model revisions, whitening, exact solver, input order, parser/cap rules and control bank hashes are recorded in [METHODS.md](METHODS.md) and the frozen configuration files. Raw source hashes, retained evidence and target-to-representative cache provenance remain auditable; no manual review rewrites a paid verdict.

There was one scoped pre-review exposure. An operational observer inadvertently emitted two auxiliary raw-N1 hallucination fields between 21:29:11.640535 and 21:31:56 UTC. The original six primary comparisons were frozen hours earlier, and the early-report proposal predated that exposure. No synthesis, menu or tuning change was based on it. The exposure is recorded in `primary-six-completion-contracts-v2.json`, SHA256 `b0b69992c882e503ab8e016c2090d216b0c3d51491224a6fd5b7b7e4ef8b1758`; the complete scientific review was subsequently authorized after all 48 family/condition contracts passed.
