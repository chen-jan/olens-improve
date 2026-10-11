# Oracle Lens: expanded inference-time comparison

Better reconstruction does not consistently produce more useful explanations.

**Scope:** 70 output settings, all 469 questions, four WorkspaceBench task banks, and 19,435 fixed activation sites. Every new comparison is exploratory.

**More reconstruction is not a reliable measure of truth** Best-of-32 adds 3.7–6.7 fit points; pooling adds another 2.0–2.5. Recovery does not consistently improve. Correct names or numbers can coexist with invented details.

**Filtering trades information for fewer contradictions** Pruning best-of-32 lowers contradictions by 5.21 points but loses nine name hits. Strict consensus removes many more names and relations. Report errors and coverage together.

**Editing contributes little beyond pooling** After two rounds, 445 of 19,435 cells change pooled prose. Fit rises by only 0.002–0.096 points; all three recovery totals stay unchanged. No universal winner is established.

## What was compared

The target model, Oracle Lens and matched activation reconstructor remain frozen. Each method explains the same target vector at the same layer and token position; control-based scorers additionally use the recorded matched activations. The shared pool contains at most 32 original descriptions per vector. Final outputs have at most four bullets and 256 Qwen tokens; the released raw baseline is retained separately with its original output. Pooling keeps intact source bullets. Editing uses explicitly recorded Luna proposals and fresh reconstruction vectors.

**Hallucination (chat)** measures wrong specific readouts divided by all specific readouts, including off-topic readouts. **Multihop (multi-token)** measures required intermediate entities; the final answer is optional. **Chained intermediates** counts only the judge’s first-ranked verified integer at a reading site; a required value appearing lower in the list does not count. **Role-bound association** checks the entity–role bindings. Number and role recovery then aggregate over the complete original question grid. Recovering that content can coexist with incorrect surrounding prose. We keep the four endpoints separate.

| Task | Questions | Related groups | Better direction |
|---|---:|---:|---|
| Hallucination (chat) | 149 | 149 | Lower |
| Multihop (multi-token) | 100 | 94 | Higher |
| Chained intermediates | 120 | 42 | Higher |
| Role-bound association | 100 | 50 | Higher |

## Direct comparison with the original released lens

The original output is one unmodified Oracle Lens sample. Its full-bank rates are **47.6%** for Hallucination (chat), **34.0%** for Multihop (multi-token), **49.2%** for Chained intermediates, and **78.0%** for Role-bound association. The four-bullet original differs, including 47.5% on Chained intermediates; these are separate references.

The following fixed representative settings are compared directly with that original output. Positive changes mean improvement: fewer hallucinations, or more recovered questions. These additional comparisons use the saved judgments and the same whole-group resampling. They were requested after inspecting results, so their pointwise 95% intervals are exploratory and are outside the original simultaneous comparison menu. No new inference or judging was needed.

| Approach | Hallucination (chat), fewer errors | Multihop (multi-token) | Chained intermediates | Role-bound association |
|---|---:|---:|---:|---:|
| More samples | +1.8 pp | +6.0 pp | +1.7 pp | -1.0 pp |
| Keep repeated statements | +26.5 pp | -29.0 pp | -8.3 pp | -57.0 pp |
| Remove weak bullets | +7.0 pp | -3.0 pp | -2.5 pp | -2.0 pp |
| Combine original bullets | +0.4 pp | +7.0 pp | -5.0 pp | +3.0 pp |
| Compare control activations | +1.8 pp | +7.0 pp | +1.7 pp | +3.0 pp |
| Edit pooled text twice | +0.4 pp | +7.0 pp | -5.0 pp | +3.0 pp |
| Combine and remove weak bullets | +3.0 pp | +5.0 pp | -6.7 pp | +3.0 pp |

Consensus still reduces specific-readout coverage from about 99% to 32%; its error reduction must be read alongside its recovery losses. Original full-prose reconstruction fit remains unavailable; the existing reconstruction reference is explicitly the four-bullet original.

Exact original-reference paired intervals are in [the source-bound supplement](https://olens-improve-research.jan618.chatgpt.site/downloads/original-reference-comparisons.json). The dashboard lets you switch between original, four-bullet original, and actual-parent comparisons.

## Findings by approach

### Choosing a complete readout

More samples reliably improve reconstruction, but recovery is not monotonic. Best-of-32 is not a universal quality winner.

Full-bank exploratory comparison; all related-question groups retained. Reconstruction is a secondary diagnostic. Selected cases illustrate mechanisms, not their prevalence or causal proof.

Representative comparison: **Choose the best complete readout (32 samples)** versus **Original, capped to four bullets**. These notes describe this setting, not every variant.

| WorkspaceBench task | Original released lens | What changed |
|---|---|---|
| Hallucination (chat) | 47.6% (2648/5560) | 2550/5565 versus 2641/5554. Fit +5.407 percentage points on 5615 common valid sites. Wrong specific readouts fall modestly; the joint interval still includes no change. Incorrect specifics remain despite higher fit. |
| Multihop (multi-token) | 34.0% (34/100) | 40/100 versus 34/100. Fit +4.972 percentage points on 1100 common valid sites. Six more questions recover a required name. Optional answers and invented collaborators remain separate; the joint interval includes no change. |
| Chained intermediates | 49.2% (59/120) | 61/120 versus 57/120. Fit +6.656 percentage points on 1320 common valid sites. Four more questions recover the first-ranked required integer. Audited hits can contain false equations; the joint interval includes losses and gains. |
| Role-bound association | 78.0% (78/100) | 77/100 versus 78/100. Fit +3.674 percentage points on 11357 common valid sites. One fewer question recovers who did what. Better topical fit does not guarantee correct direction or entity binding. |

### Keeping repeated statements

Strict repetition reduces contradictions by discarding many needed names and relations. It is a coverage tradeoff, not a free reliability gain.

Full-bank exploratory comparison; all related-question groups retained. Reconstruction is a secondary diagnostic. Selected cases illustrate mechanisms, not their prevalence or causal proof.

Representative comparison: **Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples)** versus **Exact repetition; at least 0 of 16 samples (16 samples)**. These notes describe this setting, not every variant.

| WorkspaceBench task | Original released lens | What changed |
|---|---|---|
| Hallucination (chat) | 47.6% (2648/5560) | 377/1783 versus 2591/5518. Fit -27.661 percentage points on 5615 common valid sites. Wrong readouts fall sharply among the much smaller specific-readout set. Abstention removes information as well as errors. |
| Multihop (multi-token) | 34.0% (34/100) | 5/100 versus 34/100. Fit -26.319 percentage points on 1100 common valid sites. Required-name recovery falls from 34 to 5 questions. Stable generic phrases can displace rare useful names. |
| Chained intermediates | 49.2% (59/120) | 49/120 versus 56/120. Fit -8.296 percentage points on 1320 common valid sites. Seven fewer questions recover the ranked intermediate. The joint interval includes no change; correct values can be unstable across samples. |
| Role-bound association | 78.0% (78/100) | 21/100 versus 78/100. Fit -15.895 percentage points on 11265 common valid sites. Complete relation recovery falls from 78 to 21 questions. Repeated scene descriptions do not preserve all agent/action/patient details. |

### Removing weak bullets

Removing weak bullets reduces contradictions with very little reconstruction loss, but can also delete essential names.

Full-bank exploratory comparison; all related-question groups retained. Reconstruction is a secondary diagnostic. Selected cases illustrate mechanisms, not their prevalence or causal proof. Matched random-deletion comparisons do not establish an advantage for reconstruction-guided deletion.

Representative comparison: **Best complete readout; remove weak bullets 0.005 (32 samples)** versus **Choose the best complete readout (32 samples)**. These notes describe this setting, not every variant.

| WorkspaceBench task | Original released lens | What changed |
|---|---|---|
| Hallucination (chat) | 47.6% (2648/5560) | 2261/5567 versus 2550/5565. Fit -0.151 percentage points on 5615 common valid sites. Wrong readouts fall by 5.21 points, with the joint interval below zero. Audits show removal of false details, sometimes leaving generic or unverifiable prose. |
| Multihop (multi-token) | 34.0% (34/100) | 31/100 versus 40/100. Fit -0.160 percentage points on 1100 common valid sites. Nine required-name hits disappear despite a tiny fit loss. A weak reconstruction contribution can still carry the needed name. |
| Chained intermediates | 49.2% (59/120) | 56/120 versus 61/120. Fit -0.110 percentage points on 1320 common valid sites. Five fewer questions recover the intermediate. The joint interval includes losses and gains; weak-fit bullets are not necessarily incorrect. |
| Role-bound association | 78.0% (78/100) | 76/100 versus 77/100. Fit -0.162 percentage points on 11400 common valid sites. One fewer question recovers the complete relation. Removing low-fit bullets can remove bindings; retained details can still conflict. |

### Combining original bullets

Combining original bullets gives the largest fit gains among these comparisons. Recovery gains depend on the task; intermediate numbers can get worse.

Full-bank exploratory comparison; all related-question groups retained. Reconstruction is a secondary diagnostic. Selected cases illustrate mechanisms, not their prevalence or causal proof.

Representative comparison: **Combine original bullets (32 samples)** versus **Original, capped to four bullets**. These notes describe this setting, not every variant.

| WorkspaceBench task | Original released lens | What changed |
|---|---|---|
| Hallucination (chat) | 47.6% (2648/5560) | 2621/5555 versus 2641/5554. Fit +7.937 percentage points on 5615 common valid sites. Fit rises substantially, while the contradiction change remains uncertain. Combining complementary bullets also combines unsupported specifics. |
| Multihop (multi-token) | 34.0% (34/100) | 41/100 versus 34/100. Fit +7.219 percentage points on 1100 common valid sites. Seven more questions recover a required name. Some gains reflect fuller accepted phrases around existing clues, with invented details still present. |
| Chained intermediates | 49.2% (59/120) | 53/120 versus 57/120. Fit +8.674 percentage points on 1320 common valid sites. Four fewer questions recover the ranked intermediate. Stronger reconstruction can move competing numbers above the needed value. |
| Role-bound association | 78.0% (78/100) | 81/100 versus 78/100. Fit +5.635 percentage points on 11357 common valid sites. Three more questions recover complete relations. Audited direction gains coexist with wrong foods, names or competing interpretations. |

### Comparing activation evidence

Scoring against other activations shows some promising recovery changes, but does not establish fine-grained truth or a general improvement.

Full-bank exploratory comparison; all related-question groups retained. Reconstruction is a secondary diagnostic. Selected cases illustrate mechanisms, not their prevalence or causal proof.

Representative comparison: **Compare with average control activation (32 samples)** versus **Original, capped to four bullets**. These notes describe this setting, not every variant.

| WorkspaceBench task | Original released lens | What changed |
|---|---|---|
| Hallucination (chat) | 47.6% (2648/5560) | 2550/5566 versus 2641/5554. Fit +5.391 percentage points on 5615 common valid sites. Wrong readouts fall modestly; the joint interval includes no change. Specificity against controls does not verify every factual detail. |
| Multihop (multi-token) | 34.0% (34/100) | 41/100 versus 34/100. Fit +4.950 percentage points on 1100 common valid sites. Seven more questions recover a required name. The pointwise interval excludes zero, but the joint interval does not; invented people remain. |
| Chained intermediates | 49.2% (59/120) | 61/120 versus 57/120. Fit +4.906 percentage points on 1320 common valid sites. Four more questions recover the ranked intermediate. Control specificity can favor a number without validating the stated arithmetic. |
| Role-bound association | 78.0% (78/100) | 81/100 versus 78/100. Fit +1.521 percentage points on 11357 common valid sites. Three more questions recover complete relations. Generic scene matches and language priors remain possible; direction is not established by fit. |

### Editing a readout

Two editing rounds add little fit beyond pooling and no aggregate recovery gain. Most final cells retain the original pooled text.

Full-bank exploratory comparison; all related-question groups retained. Reconstruction is a secondary diagnostic. Selected cases illustrate mechanisms, not their prevalence or causal proof.

Representative comparison: **Edit twice (32 samples)** versus **Combine original bullets (32 samples)**. These notes describe this setting, not every variant.

| WorkspaceBench task | Original released lens | What changed |
|---|---|---|
| Hallucination (chat) | 47.6% (2648/5560) | 2623/5556 versus 2621/5555. Fit +0.013 percentage points on 5615 common valid sites. Contradiction rate changes by only +0.03 points versus pooling. New prose is selected at 150/5615 cells after two rounds; fit gain is tiny. |
| Multihop (multi-token) | 34.0% (34/100) | 41/100 versus 41/100. Fit +0.007 percentage points on 1100 common valid sites. Recovery stays 41/100, with changed prose at 32/1100 cells. Identical observed totals are not proof of equivalence; the joint interval is undefined. |
| Chained intermediates | 49.2% (59/120) | 53/120 versus 53/120. Fit +0.096 percentage points on 1320 common valid sites. Recovery stays 53/120, with changed prose at 165/1320 cells. Fit improves slightly, but false arithmetic and ranking sensitivity remain. |
| Role-bound association | 78.0% (78/100) | 81/100 versus 81/100. Fit +0.002 percentage points on 11400 common valid sites. Recovery stays 81/100, with changed prose at 98/11400 cells. Tiny fit gains do not establish corrected direction or names. |

### Combining approaches

Pruning a pooled specificity selection reduces contradictions further, with mixed recovery. Attribute changes to the actual parent, not the original baseline.

Full-bank exploratory comparison; all related-question groups retained. Reconstruction is a secondary diagnostic. Selected cases illustrate mechanisms, not their prevalence or causal proof.

Representative comparison: **Combine bullets with activation specificity; remove weak bullets 0.005 (32 samples)** versus **Combine bullets with activation specificity (32 samples)**. These notes describe this setting, not every variant.

| WorkspaceBench task | Original released lens | What changed |
|---|---|---|
| Hallucination (chat) | 47.6% (2648/5560) | 2484/5564 versus 2620/5557. Fit -0.226 percentage points on 5615 common valid sites. Adding pruning to pooled specificity lowers contradictions by 2.50 points; the joint interval excludes zero. This is an incremental parent comparison. |
| Multihop (multi-token) | 34.0% (34/100) | 39/100 versus 42/100. Fit -0.272 percentage points on 1100 common valid sites. Three fewer questions recover a required name after pruning. Audits show removal of relevant names that barely affect fit. |
| Chained intermediates | 49.2% (59/120) | 51/120 versus 46/120. Fit -0.183 percentage points on 1320 common valid sites. Five more questions recover a ranked intermediate after pruning. The joint interval includes no change; reordering/removing competitors can explain hits. |
| Role-bound association | 78.0% (78/100) | 81/100 versus 81/100. Fit -0.197 percentage points on 11400 common valid sites. Complete recovery stays 81/100, but individual wins and losses occur. Equal totals hide changed bindings and judge-sensitive cases. |

## Reconstruction fit: a separate secondary diagnostic

Fraction of variance explained (FVE) measures how well the fixed reconstructor fits a recorded activation vector after the original layer-specific whitening and exact nonnegative joint fit. It measures fit at activation sites, while the quality tables retain their native question-grid or transcript endpoints. Fit gains do not establish semantic faithfulness. Negative FVE values remain valid.

FVE means give equal weight to valid activation sites. Pointwise 95% intervals resample whole related-question groups with those site weights. Parent-relative differences use only sites valid for both outputs, so their masks can differ from the absolute means and the quality comparisons. Each recorded reference is named below. These post-hoc intervals are outside the 496 headline contrast adjustment.

Absolute FVE values are percentages; changes are percentage points (pp). For example, a change from 25% to 27.5% is +2.5 pp. The reconstructor scores at most the first 32 cleaned tokens per bullet; longer suffixes remain in the readout without independent reconstruction verification. Recorded valid empty outputs can have zero fit; unavailable fits and empty paired masks remain unavailable. Zero bootstrap variation does not establish certainty.

| Setting | Task | Mean FVE; grouped pointwise 95% interval | Valid sites / intended sites |
|---|---|---|---:|
| Original, capped to four bullets | Hallucination (chat) | 37.09%; [+36.14, +38.03]% | 5,615 / 5,615 |
| Original, capped to four bullets | Multihop (multi-token) | 30.20%; [+28.60, +31.86]% | 1,100 / 1,100 |
| Original, capped to four bullets | Chained intermediates | 17.13%; [+16.38, +17.88]% | 1,320 / 1,320 |
| Original, capped to four bullets | Role-bound association | 19.40%; [+19.24, +19.56]% | 11,357 / 11,400 |
| Choose the best complete readout (32 samples) | Hallucination (chat) | 42.50%; [+41.57, +43.40]% | 5,615 / 5,615 |
| Choose the best complete readout (32 samples) | Multihop (multi-token) | 35.17%; [+33.57, +36.77]% | 1,100 / 1,100 |
| Choose the best complete readout (32 samples) | Chained intermediates | 23.79%; [+22.93, +24.66]% | 1,320 / 1,320 |
| Choose the best complete readout (32 samples) | Role-bound association | 23.08%; [+22.91, +23.23]% | 11,400 / 11,400 |
| Combine original bullets (32 samples) | Hallucination (chat) | 45.03%; [+44.14, +45.92]% | 5,615 / 5,615 |
| Combine original bullets (32 samples) | Multihop (multi-token) | 37.42%; [+35.84, +39.00]% | 1,100 / 1,100 |
| Combine original bullets (32 samples) | Chained intermediates | 25.81%; [+25.00, +26.67]% | 1,320 / 1,320 |
| Combine original bullets (32 samples) | Role-bound association | 25.04%; [+24.87, +25.20]% | 11,400 / 11,400 |
| Best complete readout; remove weak bullets 0.005 (32 samples) | Hallucination (chat) | 42.35%; [+41.44, +43.26]% | 5,615 / 5,615 |
| Best complete readout; remove weak bullets 0.005 (32 samples) | Multihop (multi-token) | 35.01%; [+33.43, +36.63]% | 1,100 / 1,100 |
| Best complete readout; remove weak bullets 0.005 (32 samples) | Chained intermediates | 23.68%; [+22.84, +24.54]% | 1,320 / 1,320 |
| Best complete readout; remove weak bullets 0.005 (32 samples) | Role-bound association | 22.92%; [+22.75, +23.08]% | 11,400 / 11,400 |
| Compare with average control activation (32 samples) | Hallucination (chat) | 42.49%; [+41.56, +43.37]% | 5,615 / 5,615 |
| Compare with average control activation (32 samples) | Multihop (multi-token) | 35.15%; [+33.55, +36.70]% | 1,100 / 1,100 |
| Compare with average control activation (32 samples) | Chained intermediates | 22.04%; [+21.07, +23.02]% | 1,320 / 1,320 |
| Compare with average control activation (32 samples) | Role-bound association | 20.92%; [+20.72, +21.11]% | 11,400 / 11,400 |
| Likelihood: true activation minus controls (8 samples) | Hallucination (chat) | 37.16%; [+36.18, +38.11]% | 5,615 / 5,615 |
| Likelihood: true activation minus controls (8 samples) | Multihop (multi-token) | 30.10%; [+28.50, +31.70]% | 1,100 / 1,100 |
| Likelihood: true activation minus controls (8 samples) | Chained intermediates | 17.12%; [+16.25, +17.95]% | 1,320 / 1,320 |
| Likelihood: true activation minus controls (8 samples) | Role-bound association | 19.37%; [+19.20, +19.53]% | 11,356 / 11,400 |
| Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples) | Hallucination (chat) | 9.21%; [+8.20, +10.28]% | 5,615 / 5,615 |
| Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples) | Multihop (multi-token) | 3.80%; [+2.97, +4.69]% | 1,100 / 1,100 |
| Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples) | Chained intermediates | 2.91%; [+2.70, +3.15]% | 1,320 / 1,320 |
| Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples) | Role-bound association | 3.42%; [+3.28, +3.55]% | 11,276 / 11,400 |
| Edit once (32 samples) | Hallucination (chat) | 45.04%; [+44.13, +45.93]% | 5,615 / 5,615 |
| Edit once (32 samples) | Multihop (multi-token) | 37.42%; [+35.85, +39.01]% | 1,100 / 1,100 |
| Edit once (32 samples) | Chained intermediates | 25.87%; [+25.05, +26.70]% | 1,320 / 1,320 |
| Edit once (32 samples) | Role-bound association | 25.04%; [+24.87, +25.20]% | 11,400 / 11,400 |
| Edit twice (32 samples) | Hallucination (chat) | 45.04%; [+44.13, +45.91]% | 5,615 / 5,615 |
| Edit twice (32 samples) | Multihop (multi-token) | 37.42%; [+35.89, +39.00]% | 1,100 / 1,100 |
| Edit twice (32 samples) | Chained intermediates | 25.90%; [+25.09, +26.74]% | 1,320 / 1,320 |
| Edit twice (32 samples) | Role-bound association | 25.04%; [+24.88, +25.20]% | 11,400 / 11,400 |

| Setting | Task | Recorded reconstruction reference | Comparison kind | Δ FVE; grouped paired pointwise 95% interval | Common valid sites / intended pairs | Related groups |
|---|---|---|---|---|---:|---:|
| Original, capped to four bullets | Hallucination (chat) | Original Oracle Lens | frozen_parent | Unavailable; Unavailable † No common valid reconstruction sites | 0 / 5,615 | 0 |
| Original, capped to four bullets | Multihop (multi-token) | Original Oracle Lens | frozen_parent | Unavailable; Unavailable † No common valid reconstruction sites | 0 / 1,100 | 0 |
| Original, capped to four bullets | Chained intermediates | Original Oracle Lens | frozen_parent | Unavailable; Unavailable † No common valid reconstruction sites | 0 / 1,320 | 0 |
| Original, capped to four bullets | Role-bound association | Original Oracle Lens | frozen_parent | Unavailable; Unavailable † No common valid reconstruction sites | 0 / 11,400 | 0 |
| Choose the best complete readout (32 samples) | Hallucination (chat) | Original, capped to four bullets | frozen_parent | +5.41 pp; [+5.25, +5.57] pp | 5,615 / 5,615 | 149 |
| Choose the best complete readout (32 samples) | Hallucination (chat) | Choose the best complete readout (16 samples) | sampling_prefix_diagnostic | +0.68 pp; [+0.65, +0.72] pp | 5,615 / 5,615 | 149 |
| Choose the best complete readout (32 samples) | Multihop (multi-token) | Original, capped to four bullets | frozen_parent | +4.97 pp; [+4.69, +5.26] pp | 1,100 / 1,100 | 94 |
| Choose the best complete readout (32 samples) | Multihop (multi-token) | Choose the best complete readout (16 samples) | sampling_prefix_diagnostic | +0.69 pp; [+0.62, +0.78] pp | 1,100 / 1,100 | 94 |
| Choose the best complete readout (32 samples) | Chained intermediates | Original, capped to four bullets | frozen_parent | +6.66 pp; [+6.34, +7.01] pp | 1,320 / 1,320 | 42 |
| Choose the best complete readout (32 samples) | Chained intermediates | Choose the best complete readout (16 samples) | sampling_prefix_diagnostic | +1.01 pp; [+0.91, +1.11] pp | 1,320 / 1,320 | 42 |
| Choose the best complete readout (32 samples) | Role-bound association | Original, capped to four bullets | frozen_parent | +3.67 pp; [+3.63, +3.72] pp | 11,357 / 11,400 | 50 |
| Choose the best complete readout (32 samples) | Role-bound association | Choose the best complete readout (16 samples) | sampling_prefix_diagnostic | +0.50 pp; [+0.49, +0.52] pp | 11,400 / 11,400 | 50 |
| Combine original bullets (32 samples) | Hallucination (chat) | Original, capped to four bullets | frozen_parent | +7.94 pp; [+7.73, +8.15] pp | 5,615 / 5,615 | 149 |
| Combine original bullets (32 samples) | Hallucination (chat) | Choose the best complete readout (32 samples) | pooling_vs_best_complete_diagnostic | +2.53 pp; [+2.45, +2.60] pp | 5,615 / 5,615 | 149 |
| Combine original bullets (32 samples) | Multihop (multi-token) | Original, capped to four bullets | frozen_parent | +7.22 pp; [+6.90, +7.56] pp | 1,100 / 1,100 | 94 |
| Combine original bullets (32 samples) | Multihop (multi-token) | Choose the best complete readout (32 samples) | pooling_vs_best_complete_diagnostic | +2.25 pp; [+2.16, +2.33] pp | 1,100 / 1,100 | 94 |
| Combine original bullets (32 samples) | Chained intermediates | Original, capped to four bullets | frozen_parent | +8.67 pp; [+8.33, +9.06] pp | 1,320 / 1,320 | 42 |
| Combine original bullets (32 samples) | Chained intermediates | Choose the best complete readout (32 samples) | pooling_vs_best_complete_diagnostic | +2.02 pp; [+1.90, +2.14] pp | 1,320 / 1,320 | 42 |
| Combine original bullets (32 samples) | Role-bound association | Original, capped to four bullets | frozen_parent | +5.63 pp; [+5.59, +5.68] pp | 11,357 / 11,400 | 50 |
| Combine original bullets (32 samples) | Role-bound association | Choose the best complete readout (32 samples) | pooling_vs_best_complete_diagnostic | +1.96 pp; [+1.95, +1.98] pp | 11,400 / 11,400 | 50 |
| Best complete readout; remove weak bullets 0.005 (32 samples) | Hallucination (chat) | Choose the best complete readout (32 samples) | frozen_parent | -0.15 pp; [-0.16, -0.15] pp | 5,615 / 5,615 | 149 |
| Best complete readout; remove weak bullets 0.005 (32 samples) | Multihop (multi-token) | Choose the best complete readout (32 samples) | frozen_parent | -0.16 pp; [-0.17, -0.15] pp | 1,100 / 1,100 | 94 |
| Best complete readout; remove weak bullets 0.005 (32 samples) | Chained intermediates | Choose the best complete readout (32 samples) | frozen_parent | -0.11 pp; [-0.12, -0.10] pp | 1,320 / 1,320 | 42 |
| Best complete readout; remove weak bullets 0.005 (32 samples) | Role-bound association | Choose the best complete readout (32 samples) | frozen_parent | -0.16 pp; [-0.16, -0.16] pp | 11,400 / 11,400 | 50 |
| Compare with average control activation (32 samples) | Hallucination (chat) | Original, capped to four bullets | frozen_parent | +5.39 pp; [+5.23, +5.56] pp | 5,615 / 5,615 | 149 |
| Compare with average control activation (32 samples) | Multihop (multi-token) | Original, capped to four bullets | frozen_parent | +4.95 pp; [+4.67, +5.23] pp | 1,100 / 1,100 | 94 |
| Compare with average control activation (32 samples) | Chained intermediates | Original, capped to four bullets | frozen_parent | +4.91 pp; [+4.53, +5.33] pp | 1,320 / 1,320 | 42 |
| Compare with average control activation (32 samples) | Role-bound association | Original, capped to four bullets | frozen_parent | +1.52 pp; [+1.44, +1.60] pp | 11,357 / 11,400 | 50 |
| Likelihood: true activation minus controls (8 samples) | Hallucination (chat) | Original, capped to four bullets | frozen_parent | +0.07 pp; [-0.04, +0.18] pp | 5,615 / 5,615 | 149 |
| Likelihood: true activation minus controls (8 samples) | Multihop (multi-token) | Original, capped to four bullets | frozen_parent | -0.10 pp; [-0.35, +0.15] pp | 1,100 / 1,100 | 94 |
| Likelihood: true activation minus controls (8 samples) | Chained intermediates | Original, capped to four bullets | frozen_parent | -0.01 pp; [-0.30, +0.31] pp | 1,320 / 1,320 | 42 |
| Likelihood: true activation minus controls (8 samples) | Role-bound association | Original, capped to four bullets | frozen_parent | -0.04 pp; [-0.10, +0.02] pp | 11,332 / 11,400 | 50 |
| Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples) | Hallucination (chat) | Exact repetition; at least 0 of 16 samples (16 samples) | frozen_parent | -27.66 pp; [-28.70, -26.60] pp | 5,615 / 5,615 | 149 |
| Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples) | Multihop (multi-token) | Exact repetition; at least 0 of 16 samples (16 samples) | frozen_parent | -26.32 pp; [-28.04, -24.64] pp | 1,100 / 1,100 | 94 |
| Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples) | Chained intermediates | Exact repetition; at least 0 of 16 samples (16 samples) | frozen_parent | -8.30 pp; [-8.82, -7.74] pp | 1,320 / 1,320 | 42 |
| Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples) | Role-bound association | Exact repetition; at least 0 of 16 samples (16 samples) | frozen_parent | -15.89 pp; [-16.07, -15.72] pp | 11,265 / 11,400 | 50 |
| Edit once (32 samples) | Hallucination (chat) | Choose the best complete readout (32 samples) | frozen_parent | +2.54 pp; [+2.46, +2.61] pp | 5,615 / 5,615 | 149 |
| Edit once (32 samples) | Hallucination (chat) | Combine original bullets (32 samples) | frozen_parent | +0.01 pp; [+0.01, +0.01] pp | 5,615 / 5,615 | 149 |
| Edit once (32 samples) | Hallucination (chat) | Choose the best complete readout (32 samples) | editor_initial_reference | +2.54 pp; [+2.46, +2.61] pp | 5,615 / 5,615 | 149 |
| Edit once (32 samples) | Hallucination (chat) | Combine original bullets (32 samples) | editor_initial_reference | +0.01 pp; [+0.01, +0.01] pp | 5,615 / 5,615 | 149 |
| Edit once (32 samples) | Multihop (multi-token) | Choose the best complete readout (32 samples) | frozen_parent | +2.25 pp; [+2.17, +2.34] pp | 1,100 / 1,100 | 94 |
| Edit once (32 samples) | Multihop (multi-token) | Combine original bullets (32 samples) | frozen_parent | +0.00 pp; [+0.00, +0.01] pp | 1,100 / 1,100 | 94 |
| Edit once (32 samples) | Multihop (multi-token) | Choose the best complete readout (32 samples) | editor_initial_reference | +2.25 pp; [+2.17, +2.34] pp | 1,100 / 1,100 | 94 |
| Edit once (32 samples) | Multihop (multi-token) | Combine original bullets (32 samples) | editor_initial_reference | +0.00 pp; [+0.00, +0.01] pp | 1,100 / 1,100 | 94 |
| Edit once (32 samples) | Chained intermediates | Choose the best complete readout (32 samples) | frozen_parent | +2.08 pp; [+1.96, +2.20] pp | 1,320 / 1,320 | 42 |
| Edit once (32 samples) | Chained intermediates | Combine original bullets (32 samples) | frozen_parent | +0.06 pp; [+0.04, +0.08] pp | 1,320 / 1,320 | 42 |
| Edit once (32 samples) | Chained intermediates | Choose the best complete readout (32 samples) | editor_initial_reference | +2.08 pp; [+1.96, +2.20] pp | 1,320 / 1,320 | 42 |
| Edit once (32 samples) | Chained intermediates | Combine original bullets (32 samples) | editor_initial_reference | +0.06 pp; [+0.04, +0.08] pp | 1,320 / 1,320 | 42 |
| Edit once (32 samples) | Role-bound association | Choose the best complete readout (32 samples) | frozen_parent | +1.96 pp; [+1.95, +1.98] pp | 11,400 / 11,400 | 50 |
| Edit once (32 samples) | Role-bound association | Combine original bullets (32 samples) | frozen_parent | +0.00 pp; [+0.00, +0.00] pp | 11,400 / 11,400 | 50 |
| Edit once (32 samples) | Role-bound association | Choose the best complete readout (32 samples) | editor_initial_reference | +1.96 pp; [+1.95, +1.98] pp | 11,400 / 11,400 | 50 |
| Edit once (32 samples) | Role-bound association | Combine original bullets (32 samples) | editor_initial_reference | +0.00 pp; [+0.00, +0.00] pp | 11,400 / 11,400 | 50 |
| Edit twice (32 samples) | Hallucination (chat) | Choose the best complete readout (32 samples) | frozen_parent | +2.54 pp; [+2.47, +2.62] pp | 5,615 / 5,615 | 149 |
| Edit twice (32 samples) | Hallucination (chat) | Combine original bullets (32 samples) | frozen_parent | +0.01 pp; [+0.01, +0.02] pp | 5,615 / 5,615 | 149 |
| Edit twice (32 samples) | Hallucination (chat) | Choose the best complete readout (32 samples) | editor_initial_reference | +2.54 pp; [+2.47, +2.62] pp | 5,615 / 5,615 | 149 |
| Edit twice (32 samples) | Hallucination (chat) | Combine original bullets (32 samples) | editor_initial_reference | +0.01 pp; [+0.01, +0.02] pp | 5,615 / 5,615 | 149 |
| Edit twice (32 samples) | Hallucination (chat) | Edit once (32 samples) | editor_previous_round_diagnostic | +0.00 pp; [+0.00, +0.01] pp | 5,615 / 5,615 | 149 |
| Edit twice (32 samples) | Multihop (multi-token) | Choose the best complete readout (32 samples) | frozen_parent | +2.25 pp; [+2.17, +2.34] pp | 1,100 / 1,100 | 94 |
| Edit twice (32 samples) | Multihop (multi-token) | Combine original bullets (32 samples) | frozen_parent | +0.01 pp; [+0.00, +0.01] pp | 1,100 / 1,100 | 94 |
| Edit twice (32 samples) | Multihop (multi-token) | Choose the best complete readout (32 samples) | editor_initial_reference | +2.25 pp; [+2.17, +2.34] pp | 1,100 / 1,100 | 94 |
| Edit twice (32 samples) | Multihop (multi-token) | Combine original bullets (32 samples) | editor_initial_reference | +0.01 pp; [+0.00, +0.01] pp | 1,100 / 1,100 | 94 |
| Edit twice (32 samples) | Multihop (multi-token) | Edit once (32 samples) | editor_previous_round_diagnostic | +0.00 pp; [+0.00, +0.00] pp | 1,100 / 1,100 | 94 |
| Edit twice (32 samples) | Chained intermediates | Choose the best complete readout (32 samples) | frozen_parent | +2.11 pp; [+1.99, +2.23] pp | 1,320 / 1,320 | 42 |
| Edit twice (32 samples) | Chained intermediates | Combine original bullets (32 samples) | frozen_parent | +0.10 pp; [+0.07, +0.13] pp | 1,320 / 1,320 | 42 |
| Edit twice (32 samples) | Chained intermediates | Choose the best complete readout (32 samples) | editor_initial_reference | +2.11 pp; [+1.99, +2.23] pp | 1,320 / 1,320 | 42 |
| Edit twice (32 samples) | Chained intermediates | Combine original bullets (32 samples) | editor_initial_reference | +0.10 pp; [+0.07, +0.13] pp | 1,320 / 1,320 | 42 |
| Edit twice (32 samples) | Chained intermediates | Edit once (32 samples) | editor_previous_round_diagnostic | +0.04 pp; [+0.02, +0.06] pp | 1,320 / 1,320 | 42 |
| Edit twice (32 samples) | Role-bound association | Choose the best complete readout (32 samples) | frozen_parent | +1.97 pp; [+1.95, +1.98] pp | 11,400 / 11,400 | 50 |
| Edit twice (32 samples) | Role-bound association | Combine original bullets (32 samples) | frozen_parent | +0.00 pp; [+0.00, +0.00] pp | 11,400 / 11,400 | 50 |
| Edit twice (32 samples) | Role-bound association | Choose the best complete readout (32 samples) | editor_initial_reference | +1.97 pp; [+1.95, +1.98] pp | 11,400 / 11,400 | 50 |
| Edit twice (32 samples) | Role-bound association | Combine original bullets (32 samples) | editor_initial_reference | +0.00 pp; [+0.00, +0.00] pp | 11,400 / 11,400 | 50 |
| Edit twice (32 samples) | Role-bound association | Edit once (32 samples) | editor_previous_round_diagnostic | +0.00 pp; [+0.00, +0.00] pp | 11,400 / 11,400 | 50 |

The settings shown here follow the reviewed presentation order; they are not ranked by fit. All method/family rows, every recorded parent comparison, masks, warnings and source pins are retained in the [complete numeric reconstruction data](final-v1.json).

Reconstruction artifact SHA-256: `0c3f99db532641326d4d432a9587d9ee10d9ea978fe16f9c74c9d96740965ba8`.

## Uncertainty and interpretation

We resample whole related groups with 10,000 shared draws within each task. Paired intervals compare the same groups across methods. The fixed menu contains 496 headline contrasts. 451 are defined and nondegenerate; 451 receive simultaneous intervals. Simultaneous intervals use a centered, standardized bootstrap maximum over its defined, nondegenerate contrasts. These intervals provide approximate coverage. Undefined ratio draws and zero bootstrap variation receive explicit warnings; their simultaneous intervals remain unavailable. A zero-width absolute interval for all-zero or all-one recovery does not establish certainty.

All 469 questions were inspected before this expansion. Adjustment addresses the declared comparisons; it does not undo prior outcome access or create fresh held-out evidence. The original test subset is now a descriptive subcohort; the earlier frozen test report is preserved separately. Adding methods or activation sites does not increase the number of independent questions. An overlapping interval is not a reason to discard an otherwise useful method.

## Practical recommendations

- Keep a small menu: best-of-N, pooled selection and optional pruning. Choose according to the task and the acceptable loss of information.

- Do not scale editing or strict consensus on this evidence. Higher reconstruction fit alone should not justify additional inference.

- Use a fresh, independent evaluation to confirm promising task-specific changes. Improve judge diagnostics for ranked numbers and reversed relations before claiming faithfulness.

## Effort and retained data

469 questions, 19,435 activation sites, 70 settings and all 280 task/settings complete. Shared pool: 621,920 original samples. Recorded API usage: $142.73 overall, $106.22 expansion; $5.07 unresolved/reserved. Expansion used 5.825 allocated H200-hours. GPU costs are not priced; API figures are estimates, not invoices. Project storage: 122.97 GB logical, excluding shared weights.

Selection from a saved pool is cheaper than creating that pool for a new activation. Helpers, new likelihood scoring and edited-text reconstruction add separate work. The dashboard reports actual output lengths and component effort. The natural-length comparisons estimate practical method performance; they do not isolate a benefit independent of output length.

## Complete result table

Each entry gives the native percentage followed by its grouped 95% interval. Exact numerators, denominators, paired intervals, simultaneous intervals and secondary coverage measures are available in the accompanying data export.

| Setting | Hallucination (chat) ↓ | Multihop (multi-token) ↑ | Chained intermediates ↑ | Role-bound association ↑ |
|---|---:|---:|---:|---:|
| Original Oracle Lens | 47.6% (44.2 to 51.1%) | 34.0% (24.5 to 43.7%) | 49.2% (40.2 to 59.1%) | 78.0% (70.0 to 85.0%) |
| Original, capped to four bullets | 47.6% (44.1 to 51.1%) | 34.0% (24.5 to 43.7%) | 47.5% (37.8 to 58.0%) | 78.0% (70.0 to 85.0%) |
| Choose the best complete readout | 47.6% (44.1 to 51.1%) | 34.0% (24.5 to 43.7%) | 47.5% (37.8 to 58.0%) | 78.0% (70.0 to 85.0%) |
| Choose the best complete readout (2 samples) | 47.9% (44.3 to 51.6%) | 41.0% (31.6 to 50.5%) | 50.8% (40.3 to 61.7%) | 79.0% (71.0 to 86.0%) |
| Choose the best complete readout (4 samples) | 47.3% (43.7 to 50.8%) | 41.0% (31.3 to 51.0%) | 54.2% (45.0 to 63.6%) | 83.0% (75.0 to 90.0%) |
| Choose the best complete readout (8 samples) | 47.2% (43.6 to 50.8%) | 37.0% (27.5 to 46.9%) | 51.7% (41.8 to 61.0%) | 80.0% (72.0 to 87.0%) |
| Choose the best complete readout (16 samples) | 47.3% (43.9 to 50.7%) | 41.0% (31.3 to 51.0%) | 50.8% (40.2 to 61.8%) | 81.0% (74.0 to 87.0%) |
| Choose the best complete readout (32 samples) | 45.8% (42.3 to 49.4%) | 40.0% (30.1 to 50.0%) | 50.8% (40.6 to 61.3%) | 77.0% (70.0 to 84.0%) |
| Choose a random complete readout (16 samples) | 47.9% (44.3 to 51.4%) | 36.0% (26.5 to 45.5%) | 42.5% (31.1 to 54.1%) | 81.0% (74.0 to 88.0%) |
| Choose a random complete readout (32 samples) | 46.3% (42.9 to 49.8%) | 37.0% (27.6 to 46.6%) | 45.0% (35.1 to 55.8%) | 76.0% (68.0 to 84.0%) |
| Combine original bullets (16 samples) | 47.6% (44.1 to 51.2%) | 44.0% (34.3 to 54.0%) | 46.7% (36.4 to 57.1%) | 83.0% (76.0 to 89.0%) |
| Combine original bullets (32 samples) | 47.2% (43.8 to 50.7%) | 41.0% (31.3 to 51.0%) | 44.2% (34.5 to 54.2%) | 81.0% (73.0 to 88.0%) |
| Best complete readout; remove weak bullets 0.001 (32 samples) | 43.0% (39.4 to 46.6%) | 35.0% (25.5 to 44.6%) | 50.8% (40.3 to 61.5%) | 77.0% (70.0 to 84.0%) |
| Best complete readout; remove weak bullets 0.005 (32 samples) | 40.6% (37.0 to 44.2%) | 31.0% (21.9 to 40.6%) | 46.7% (36.8 to 57.4%) | 76.0% (69.0 to 83.0%) |
| Best complete readout; random deletion control 0.001 (32 samples) | 41.4% (37.9 to 45.0%) | 33.0% (23.7 to 42.7%) | 40.8% (30.4 to 52.3%) | 76.0% (67.0 to 84.0%) |
| Best complete readout; random deletion control 0.005 (32 samples) | 38.6% (35.2 to 42.0%) | 34.0% (24.7 to 43.6%) | 55.8% (45.4 to 66.7%) | 79.0% (72.0 to 86.0%) |
| Original capped readout; remove weak bullets 0.005 | 42.5% (38.9 to 46.0%) | 31.0% (21.8 to 40.4%) | 46.7% (37.2 to 57.3%) | 81.0% (74.0 to 88.0%) |
| Original capped readout; random deletion control 0.005 | 42.2% (38.6 to 45.8%) | 26.0% (17.5 to 35.0%) | 44.2% (35.8 to 53.4%) | 75.0% (67.0 to 82.0%) |
| Compare with average control activation (32 samples) | 45.8% (42.3 to 49.3%) | 41.0% (31.2 to 51.0%) | 50.8% (42.1 to 59.8%) | 81.0% (74.0 to 88.0%) |
| Compare with strongest control activation (32 samples) | 46.4% (43.0 to 49.9%) | 40.0% (30.2 to 50.0%) | 45.8% (35.5 to 56.9%) | 83.0% (76.0 to 89.0%) |
| Compare with average control activation; remove weak bullets 0.001 (32 samples) | 42.9% (39.3 to 46.5%) | 36.0% (26.5 to 45.6%) | 42.5% (32.4 to 53.5%) | 80.0% (73.0 to 87.0%) |
| Compare with average control activation; remove weak bullets 0.005 (32 samples) | 40.5% (36.9 to 44.0%) | 32.0% (22.8 to 41.6%) | 42.5% (32.1 to 53.7%) | 79.0% (72.0 to 85.0%) |
| Compare with average control activation; random deletion control 0.001 (32 samples) | 41.8% (38.4 to 45.2%) | 33.0% (23.8 to 42.6%) | 46.7% (36.7 to 57.1%) | 82.0% (75.0 to 88.0%) |
| Compare with average control activation; random deletion control 0.005 (32 samples) | 39.3% (36.0 to 42.8%) | 31.0% (22.0 to 40.4%) | 44.2% (34.3 to 53.7%) | 77.0% (70.0 to 84.0%) |
| Likelihood: true activation minus controls (8 samples) | 47.8% (44.3 to 51.4%) | 34.0% (24.7 to 43.6%) | 40.0% (30.0 to 51.0%) | 82.0% (75.0 to 88.0%) |
| Likelihood under the true activation (8 samples) | 46.2% (42.8 to 49.7%) | 36.0% (26.7 to 45.5%) | 44.2% (35.3 to 53.6%) | 77.0% (70.0 to 84.0%) |
| Likelihood under control activations (8 samples) | 47.1% (43.5 to 50.8%) | 42.0% (32.3 to 52.0%) | 46.7% (38.2 to 55.4%) | 79.0% (72.0 to 86.0%) |
| Exact repetition; at least 0 of 16 samples (16 samples) | 47.0% (43.5 to 50.4%) | 34.0% (24.5 to 43.7%) | 46.7% (37.0 to 56.9%) | 78.0% (70.0 to 85.0%) |
| Exact repetition; at least 2 of 16 samples (16 samples) | 26.1% (18.9 to 32.7%) | 1.0% (0.0 to 3.1%) | 38.3% (29.2 to 47.9%) | 1.0% (0.0 to 3.0%) |
| Exact repetition; at least 4 of 16 samples (16 samples) | 40.0% (19.1 to 58.6%) | 1.0% (0.0 to 3.1%) | 30.0% (21.1 to 39.3%) | 0.0% (0.0 to 0.0%) † |
| Edit once (32 samples) | 47.1% (43.7 to 50.6%) | 41.0% (31.3 to 51.0%) | 44.2% (34.5 to 54.2%) | 81.0% (73.0 to 88.0%) |
| Edit twice (32 samples) | 47.2% (43.8 to 50.7%) | 41.0% (31.3 to 51.0%) | 44.2% (34.5 to 54.2%) | 81.0% (73.0 to 88.0%) |
| Combine original bullets; remove weak bullets 0.001 (32 samples) | 47.1% (43.7 to 50.7%) | 41.0% (31.3 to 51.0%) | 44.2% (34.4 to 54.4%) | 81.0% (73.0 to 88.0%) |
| Combine original bullets; random deletion control 0.001 (32 samples) | 46.9% (43.4 to 50.4%) | 41.0% (31.3 to 51.0%) | 41.7% (31.8 to 51.7%) | 81.0% (73.0 to 88.0%) |
| Combine original bullets; remove weak bullets 0.005 (32 samples) | 44.5% (40.9 to 48.1%) | 39.0% (29.4 to 49.0%) | 45.8% (35.7 to 57.1%) | 80.0% (72.0 to 87.0%) |
| Combine original bullets; random deletion control 0.005 (32 samples) | 44.0% (40.4 to 47.5%) | 39.0% (29.3 to 49.5%) | 45.0% (35.5 to 54.8%) | 82.0% (75.0 to 89.0%) |
| Edit twice; remove weak bullets 0.001 (32 samples) | 47.2% (43.7 to 50.8%) | 41.0% (31.3 to 51.0%) | 43.3% (33.3 to 53.5%) | 81.0% (73.0 to 88.0%) |
| Edit twice; random deletion control 0.001 (32 samples) | 46.8% (43.3 to 50.3%) | 40.0% (30.3 to 50.0%) | 42.5% (31.8 to 53.6%) | 81.0% (73.0 to 88.0%) |
| Edit twice; remove weak bullets 0.005 (32 samples) | 44.4% (40.8 to 48.0%) | 40.0% (30.3 to 50.0%) | 45.8% (35.5 to 57.0%) | 81.0% (73.0 to 88.0%) |
| Edit twice; random deletion control 0.005 (32 samples) | 44.6% (41.1 to 48.2%) | 37.0% (27.5 to 46.9%) | 47.5% (38.0 to 57.8%) | 82.0% (74.0 to 89.0%) |
| Combine bullets with repetition weight 0.05 (16 samples) | 47.6% (44.1 to 51.2%) | 44.0% (34.3 to 54.0%) | 47.5% (37.7 to 57.5%) | 83.0% (76.0 to 89.0%) |
| Combine bullets with repetition weight 0.2 (16 samples) | 47.4% (43.9 to 50.9%) | 44.0% (34.3 to 54.0%) | 47.5% (38.0 to 57.3%) | 83.0% (76.0 to 89.0%) |
| Exact repetition only (16 samples) | 47.0% (43.5 to 50.4%) | 34.0% (24.5 to 43.7%) | 46.7% (37.0 to 56.9%) | 78.0% (70.0 to 85.0%) |
| Semantic repetition; at least 0 of 16 samples (16 samples) | 45.5% (42.0 to 49.0%) | 33.0% (23.8 to 42.6%) | 42.5% (32.0 to 53.8%) | 78.0% (70.0 to 85.0%) |
| Semantic repetition; at least 0 of 16 samples; contradiction filter (16 samples) | 45.6% (42.2 to 49.1%) | 33.0% (23.8 to 42.6%) | 43.3% (32.8 to 54.6%) | 78.0% (70.0 to 85.0%) |
| Semantic repetition; at least 0 of 16 samples; compatibility check; contradiction filter (16 samples) | 23.2% (20.5 to 26.0%) | 16.0% (8.9 to 24.0%) | 49.2% (38.2 to 60.8%) | 60.0% (50.0 to 69.0%) |
| Semantic repetition; at least 2 of 16 samples; contradiction filter (16 samples) | 26.6% (22.9 to 30.5%) | 6.0% (2.0 to 11.1%) | 40.8% (31.9 to 50.4%) | 22.0% (14.0 to 31.0%) |
| Semantic repetition; at least 2 of 16 samples; compatibility check; contradiction filter (16 samples) | 21.1% (17.9 to 24.6%) | 5.0% (1.0 to 9.8%) | 40.8% (31.3 to 50.9%) | 21.0% (13.0 to 29.0%) |
| Combine bullets with activation specificity (32 samples) | 47.1% (43.6 to 50.8%) | 42.0% (32.3 to 52.1%) | 38.3% (28.3 to 49.2%) | 81.0% (74.0 to 88.0%) |
| Combine bullets with activation specificity; remove weak bullets 0.005 (32 samples) | 44.6% (41.0 to 48.3%) | 39.0% (29.4 to 49.0%) | 42.5% (33.3 to 52.1%) | 81.0% (73.0 to 88.0%) |
| Combine bullets with activation specificity; random deletion control 0.005 (32 samples) | 44.7% (41.1 to 48.3%) | 40.0% (30.3 to 50.0%) | 40.8% (29.3 to 53.8%) | 82.0% (75.0 to 89.0%) |
| Control comparison, omit nonpositive results (32 samples) | 45.8% (42.3 to 49.3%) | 41.0% (31.2 to 51.0%) | 50.8% (42.1 to 59.8%) | 81.0% (74.0 to 88.0%) |
| Semantic repetition; at least 0 of 16 samples; more helper reasoning; contradiction filter (16 samples) | 46.1% (42.6 to 49.7%) | 34.0% (24.5 to 43.7%) | 42.5% (32.8 to 53.0%) | 78.0% (70.0 to 85.0%) |
| Semantic repetition; at least 0 of 16 samples; more helper reasoning; compatibility check; contradiction filter (16 samples) | 23.1% (20.5 to 25.9%) | 14.0% (7.1 to 21.6%) | 50.0% (39.7 to 60.9%) | 59.0% (49.0 to 69.0%) |
| Semantic repetition; at least 2 of 16 samples; more helper reasoning; contradiction filter (16 samples) | 24.2% (19.5 to 28.9%) | 5.0% (1.0 to 9.8%) | 44.2% (35.5 to 53.5%) | 6.0% (1.0 to 12.0%) |
| Semantic repetition; at least 2 of 16 samples; more helper reasoning; compatibility check; contradiction filter (16 samples) | 19.3% (15.5 to 23.4%) | 5.0% (1.0 to 9.8%) | 44.2% (34.5 to 54.5%) | 6.0% (1.0 to 12.0%) |
| Choose a random complete readout | 47.6% (44.1 to 51.1%) | 34.0% (24.5 to 43.7%) | 47.5% (37.8 to 58.0%) | 78.0% (70.0 to 85.0%) |
| Choose a random complete readout (2 samples) | 48.1% (44.5 to 51.8%) | 36.0% (26.8 to 45.5%) | 45.8% (34.9 to 56.0%) | 79.0% (71.0 to 86.0%) |
| Choose a random complete readout (4 samples) | 47.1% (43.5 to 50.7%) | 37.0% (27.5 to 47.0%) | 48.3% (37.1 to 60.3%) | 78.0% (70.0 to 86.0%) |
| Choose a random complete readout (8 samples) | 47.3% (43.7 to 50.8%) | 37.0% (27.7 to 46.9%) | 44.2% (34.5 to 54.1%) | 77.0% (69.0 to 84.0%) |
| Best complete readout; remove weak bullets 0 (32 samples) | 44.6% (41.0 to 48.1%) | 39.0% (29.3 to 49.0%) | 51.7% (41.0 to 62.3%) | 75.0% (67.0 to 82.0%) |
| Best complete readout; random deletion control 0 (32 samples) | 43.4% (39.9 to 46.9%) | 35.0% (25.5 to 44.6%) | 50.0% (39.1 to 60.2%) | 79.0% (72.0 to 86.0%) |
| Best complete readout; remove small reconstruction weights 0.01 (32 samples) | 44.5% (40.9 to 48.1%) | 38.0% (28.3 to 47.9%) | 51.7% (41.0 to 62.3%) | 75.0% (67.0 to 82.0%) |
| Best complete readout; remove small reconstruction weights 0.05 (32 samples) | 43.2% (39.6 to 46.9%) | 36.0% (26.5 to 45.6%) | 50.0% (39.7 to 60.5%) | 76.0% (69.0 to 83.0%) |
| Original capped readout; remove weak bullets 0 | 46.0% (42.5 to 49.6%) | 33.0% (23.8 to 42.6%) | 50.0% (40.1 to 60.9%) | 78.0% (70.0 to 85.0%) |
| Original capped readout; random deletion control 0 | 45.1% (41.5 to 48.5%) | 34.0% (24.5 to 43.7%) | 45.8% (35.2 to 57.4%) | 79.0% (71.0 to 86.0%) |
| Original capped readout; remove weak bullets 0.001 | 45.0% (41.5 to 48.6%) | 31.0% (21.8 to 40.4%) | 47.5% (38.3 to 57.3%) | 79.0% (72.0 to 86.0%) |
| Original capped readout; random deletion control 0.001 | 43.9% (40.4 to 47.5%) | 30.0% (21.0 to 39.4%) | 45.8% (37.3 to 54.8%) | 78.0% (71.0 to 85.0%) |
| Original capped readout; remove small reconstruction weights 0.01 | 45.8% (42.2 to 49.3%) | 33.0% (23.8 to 42.6%) | 49.2% (39.5 to 59.7%) | 78.0% (70.0 to 85.0%) |
| Original capped readout; remove small reconstruction weights 0.05 | 45.3% (41.7 to 48.9%) | 31.0% (21.8 to 40.4%) | 49.2% (39.7 to 59.1%) | 78.0% (70.0 to 85.0%) |

† Bootstrap warnings for the marked absolute intervals:

- Exact repetition; at least 4 of 16 samples (16 samples), Role-bound association: Zero bootstrap variation; the displayed interval does not establish certainty.

## Scope and reproducibility

Independent-reader extensions, including J++, NLA and another reconstructor, remain postponed. Malformed historical semantic conditions, exact aliases and unjudged numerical diagnostics remain documented separately. The finite inventory records those states; absence from the usable menu is not an adverse benchmark result.

- Benchmark: [WorkspaceBench](https://github.com/camilablank/workspace-bench), revision `92d763e722377f5bfae045e829a308ab5919a820`.
- Model: [Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B), revision `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`.
- Matched reader and reconstructor: [released Oracle Lens pair](https://huggingface.co/agu18dec/olens_and_ar), revision `c95215d5d2f6250f20c305ae55c6e4d7569f92dc`.
- GPT-6 Luna supplies the benchmark judgments; hidden-name matching uses the released deterministic rule. Helpers use separate recorded prompts.

Result source SHA-256: `e2773e297d7724f20d656ecf07c5de00097604d8a85c516938a565626b07876e`.  
Frozen inventory SHA-256: `753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8`.  
Reviewed interpretation SHA-256: `a861d9b0002b48f2d493b4be6dcf6f06f9cecbfb59af20bdf11561539b91a14d`.
