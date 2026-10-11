# Task-specific reconstruction interpretation — provisional reviewed snapshot

This memo adds task-specific N1/16/32 scaling and recorded reconstruction increments to presentation draft v3, not final findings or a qualitative prevalence estimate. Native v3 has 235/280 completed condition–task units; reconstruction v3 has 249 defined means (221 complete and 28 partial). The 469 questions were previously inspected, so interpretation remains exploratory.

Explained activation variance is `100 × (1 − squared residual / squared target)` using the first 32 cleaned tokens of each reconstruction atom; it measures the fixed fit objective, not correctness of full prose. Absolute means use each setting’s valid activation sites; paired changes use the recorded common-valid mask. Raw original N1 has no comparable saved fit: capped N1 is the named reference, and scored best-of-1 can differ (roles: capped 11,357 valid sites; best-of-1 11,400).

Transcript quality counts wrong specific readouts / all specific readouts, including off-topic readouts (lower is better). Other tasks count recovered questions / all questions, with ANY passing original site/layer sufficient (higher is better); N is candidates per vector. Every bracket is an existing pointwise grouped 95% interval. Fit diagnostics are outside the 496 native headline contrasts, whose simultaneous intervals remain withheld in this partial source. No paired interval is obtained by subtracting means or absolute CIs.

Tables separate fit and quality references. “Unmeasured” is not zero. Exact unrounded values, counts, masks, warnings, condition IDs and source array pointers are in the companion JSON; representative rows are chosen for explanation, not by outcome.

## Transcript contradictions

Best-of-1/16/32 explains 37.08%/41.82%/42.50% of activation variance, with a recorded N16→N32 increment of +0.684 pp [0.650, 0.719]; pooling adds +2.530 pp [2.454, 2.604] beyond best-of-32, although its contradiction rate is 47.18% versus best-of-32’s 45.82% (there is no recorded paired native interval for that comparison). Pruning best-of-32 loses only 0.151 pp fit but changes wrong specific readouts from 2,550/5,565 to 2,261/5,567, a recorded −5.21 pp [−6.64, −3.80] contradiction change; semantic consensus’s 9.21% fit and 377/1,783 contradictions must also show the smaller specific-readout denominator. Likelihood fit is measured here, but likelihood contradiction judgment is absent from this snapshot; the draft’s pruning example becoming consistent after removing an unsupported answer is not evidence of a supported-true answer.

| Setting | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common/intended sites | Native endpoint, 95% CI; count | Paired native change, 95% CI |
|---|---|---|---|---|
| Capped N1 | 37.09% [36.14, 38.03]; 5615/5615 | — | 47.55% [44.07, 51.08]; 2641/5554 | — |
| Best N1 | 37.08% [36.12, 38.00]; 5615/5615 | -0.016 pp [-0.043, 0.000] vs Capped N1; 5615/5615 common | 47.57% [44.10, 51.09]; 2641/5552 | +0.02 pp [0.00, 0.04] vs Capped N1 |
| Best N16 | 41.82% [40.90, 42.71]; 5615/5615 | +4.724 pp [4.577, 4.872] vs Capped N1; 5615/5615 common | 47.32% [43.88, 50.74]; 2633/5564 | -0.23 pp [-1.55, 1.06] vs Capped N1 |
| Best N32 | 42.50% [41.57, 43.40]; 5615/5615 | +5.407 pp [5.246, 5.570] vs Capped N1; 5615/5615 common | 45.82% [42.28, 49.37]; 2550/5565 | -1.73 pp [-3.14, -0.33] vs Capped N1 |
| Pooling N32 | 45.03% [44.14, 45.92]; 5615/5615 | +7.937 pp [7.729, 8.149] vs Capped N1; 5615/5615 common | 47.18% [43.78, 50.71]; 2621/5555 | -0.37 pp [-1.81, 1.07] vs Capped N1 |
| Prune best N32, .005 | 42.35% [41.44, 43.26]; 5615/5615 | -0.151 pp [-0.156, -0.146] vs Best N32; 5615/5615 common | 40.61% [37.05, 44.21]; 2261/5567 | -5.21 pp [-6.64, -3.80] vs Best N32 |
| Target/control selection N32 | 42.49% [41.56, 43.37]; 5615/5615 | +5.391 pp [5.232, 5.558] vs Capped N1; 5615/5615 common | 45.81% [42.35, 49.34]; 2550/5566 | -1.74 pp [-3.20, -0.30] vs Capped N1 |
| Target−controls likelihood N8 | 37.16% [36.18, 38.11]; 5615/5615 | +0.069 pp [-0.043, 0.182] vs Capped N1; 5615/5615 common | Unmeasured | No recorded contrast |
| Own likelihood N8 | 37.36% [36.42, 38.31]; 5615/5615 | +0.270 pp [0.159, 0.386] vs Capped N1; 5615/5615 common | Unmeasured | No recorded contrast |
| Control likelihood N8 | 37.05% [36.10, 37.97]; 5615/5615 | -0.047 pp [-0.167, 0.078] vs Capped N1; 5615/5615 common | Unmeasured | No recorded contrast |
| Semantic consensus 2/16 | 9.21% [8.20, 10.28]; 5615/5615 | -27.661 pp [-28.701, -26.600] vs Exact support-zero; 5615/5615 common | 21.14% [17.88, 24.63]; 377/1783 | -25.81 pp [-29.16, -22.43] vs Exact support-zero |
| Exact consensus 2/16 | 3.51% [2.81, 4.30]; 5615/5615 | -33.587 pp [-34.667, -32.466] vs Capped N1; 5615/5615 common | 26.06% [18.87, 32.66]; 147/564 | -21.49 pp [-28.53, -14.97] vs Capped N1 |
| Pooled target/control parent | 44.99% [44.10, 45.87]; 5615/5615 | Unavailable | 47.15% [43.64, 50.75]; 2620/5557 | -0.40 pp [-1.89, 1.08] vs Capped N1 |
| Prune pooled target/control, .005 | 44.77% [43.87, 45.64]; 5615/5615 | -0.226 pp [-0.235, -0.216] vs Pooled target/control parent; 5615/5615 common | 44.64% [41.01, 48.32]; 2484/5564 | -2.50 pp [-3.42, -1.60] vs Pooled target/control parent |

**Additional recorded fit diagnostics:** N16→N32: +0.684 pp [0.650, 0.719] vs Best N16; 5615/5615 common. Pooling beyond best complete N32: +2.530 pp [2.454, 2.604] vs Best N32; 5615/5615 common. The pooling-versus-best fit comparison is secondary; no corresponding native paired contrast is present in this source, so absolute quality counts do not supply a paired CI.

## Hidden intermediate names

Best-of-1/16/32 fit increases 30.20%→34.48%→35.17%, while recovered questions go 34→41→40 of 100; the last 16 candidates add +0.694 pp [0.615, 0.777] fit without a higher question count. Pooling adds +2.247 pp [2.163, 2.334] over best-of-32 and recovers 41/100, whereas a 0.160 pp pruning loss relative to best-of-32 accompanies nine fewer recovered questions (−9.00 pp [−15.00, −3.92]); semantic consensus retains 5/100, and target-minus-controls likelihood stays at capped N1’s 34/100 despite the different likelihood-control results. These endpoints require hidden bridge names and leave the final answer optional; the draft’s Adwa-based verification example still names wrong generals, so a local bridge hit cannot establish correct surrounding prose or recovery caused by every component.

| Setting | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common/intended sites | Native endpoint, 95% CI; count | Paired native change, 95% CI |
|---|---|---|---|---|
| Capped N1 | 30.20% [28.60, 31.86]; 1100/1100 | — | 34.00% [24.53, 43.69]; 34/100 | — |
| Best N1 | 30.20% [28.56, 31.86]; 1100/1100 | +0.000 pp [0.000, 0.000] vs Capped N1; 1100/1100 common | 34.00% [24.53, 43.69]; 34/100 | +0.00 pp [0.00, 0.00] vs Capped N1 |
| Best N16 | 34.48% [32.91, 36.09]; 1100/1100 | +4.278 pp [4.028, 4.545] vs Capped N1; 1100/1100 common | 41.00% [31.31, 51.00]; 41/100 | +7.00 pp [0.00, 14.14] vs Capped N1 |
| Best N32 | 35.17% [33.57, 36.77]; 1100/1100 | +4.972 pp [4.693, 5.257] vs Capped N1; 1100/1100 common | 40.00% [30.10, 50.00]; 40/100 | +6.00 pp [0.00, 12.24] vs Capped N1 |
| Pooling N32 | 37.42% [35.84, 39.00]; 1100/1100 | +7.219 pp [6.900, 7.558] vs Capped N1; 1100/1100 common | 41.00% [31.31, 51.02]; 41/100 | +7.00 pp [0.00, 14.43] vs Capped N1 |
| Prune best N32, .005 | 35.01% [33.43, 36.63]; 1100/1100 | -0.160 pp [-0.171, -0.149] vs Best N32; 1100/1100 common | 31.00% [21.87, 40.59]; 31/100 | -9.00 pp [-15.00, -3.92] vs Best N32 |
| Target/control selection N32 | 35.15% [33.55, 36.70]; 1100/1100 | +4.950 pp [4.674, 5.229] vs Capped N1; 1100/1100 common | 41.00% [31.25, 50.98]; 41/100 | +7.00 pp [0.98, 13.59] vs Capped N1 |
| Target−controls likelihood N8 | 30.10% [28.50, 31.70]; 1100/1100 | -0.101 pp [-0.349, 0.152] vs Capped N1; 1100/1100 common | 34.00% [24.74, 43.57]; 34/100 | +0.00 pp [-6.12, 6.06] vs Capped N1 |
| Own likelihood N8 | 30.45% [28.83, 32.07]; 1100/1100 | +0.249 pp [0.022, 0.474] vs Capped N1; 1100/1100 common | 36.00% [26.73, 45.54]; 36/100 | +2.00 pp [-4.08, 8.16] vs Capped N1 |
| Control likelihood N8 | 30.19% [28.56, 31.84]; 1100/1100 | -0.009 pp [-0.269, 0.244] vs Capped N1; 1100/1100 common | 42.00% [32.32, 52.00]; 42/100 | +8.00 pp [1.00, 15.31] vs Capped N1 |
| Semantic consensus 2/16 | 3.80% [2.97, 4.69]; 1100/1100 | -26.319 pp [-28.044, -24.639] vs Exact support-zero; 1100/1100 common | 5.00% [1.01, 9.80]; 5/100 | -29.00 pp [-38.14, -20.00] vs Exact support-zero |
| Exact consensus 2/16 | 1.31% [0.85, 1.80]; 1100/1100 | -28.890 pp [-30.513, -27.299] vs Capped N1; 1100/1100 common | 1.00% [0.00, 3.09]; 1/100 | -33.00 pp [-42.57, -23.76] vs Capped N1 |
| Pooled target/control parent | 37.37% [35.81, 38.96]; 1100/1100 | Unavailable | 42.00% [32.32, 52.08]; 42/100 | +8.00 pp [0.00, 15.69] vs Capped N1 |
| Prune pooled target/control, .005 | 37.10% [35.52, 38.67]; 1100/1100 | -0.272 pp [-0.286, -0.257] vs Pooled target/control parent; 1100/1100 common | 39.00% [29.41, 49.02]; 39/100 | -3.00 pp [-6.93, 0.00] vs Pooled target/control parent |

**Additional recorded fit diagnostics:** N16→N32: +0.694 pp [0.615, 0.777] vs Best N16; 1100/1100 common. Pooling beyond best complete N32: +2.247 pp [2.163, 2.334] vs Best N32; 1100/1100 common. The pooling-versus-best fit comparison is secondary; no corresponding native paired contrast is present in this source, so absolute quality counts do not supply a paired CI.

## Intermediate numbers

Best-of-1/16/32 fit increases 17.13%→22.78%→23.79% while first-ranked intermediate recovery is 57→61→61 of 120; N16→N32 adds +1.006 pp [0.913, 1.107] fit. Pooling adds +2.018 pp [1.903, 2.137] over best-of-32 but recovers 53/120; pruning loses 0.110 pp fit and recovers 56/120 versus best-of-32’s 61/120, with the recorded −4.17 pp quality interval [−11.43, 3.06] crossing zero. Target/control selection recovers 61/120 with lower fit than best-of-32, target-minus-controls likelihood recovers 48/120, and semantic consensus 49/120; the draft’s correct 75 inside a false equation and first-ranked-only endpoint prevent interpreting these counts as faithful calculation.

| Setting | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common/intended sites | Native endpoint, 95% CI; count | Paired native change, 95% CI |
|---|---|---|---|---|
| Capped N1 | 17.13% [16.38, 17.88]; 1320/1320 | — | 47.50% [37.82, 57.98]; 57/120 | — |
| Best N1 | 17.13% [16.38, 17.90]; 1320/1320 | +0.000 pp [0.000, 0.000] vs Capped N1; 1320/1320 common | 47.50% [37.82, 57.98]; 57/120 | +0.00 pp [0.00, 0.00] vs Capped N1 |
| Best N16 | 22.78% [21.93, 23.65]; 1320/1320 | +5.651 pp [5.359, 5.957] vs Capped N1; 1320/1320 common | 50.83% [40.18, 61.76]; 61/120 | +3.33 pp [-7.14, 14.05] vs Capped N1 |
| Best N32 | 23.79% [22.93, 24.66]; 1320/1320 | +6.656 pp [6.335, 7.007] vs Capped N1; 1320/1320 common | 50.83% [40.62, 61.34]; 61/120 | +3.33 pp [-6.31, 13.18] vs Capped N1 |
| Pooling N32 | 25.81% [25.00, 26.67]; 1320/1320 | +8.674 pp [8.327, 9.057] vs Capped N1; 1320/1320 common | 44.17% [34.45, 54.17]; 53/120 | -3.33 pp [-12.73, 6.19] vs Capped N1 |
| Prune best N32, .005 | 23.68% [22.84, 24.54]; 1320/1320 | -0.110 pp [-0.120, -0.100] vs Best N32; 1320/1320 common | 46.67% [36.75, 57.39]; 56/120 | -4.17 pp [-11.43, 3.06] vs Best N32 |
| Target/control selection N32 | 22.04% [21.07, 23.02]; 1320/1320 | +4.906 pp [4.531, 5.326] vs Capped N1; 1320/1320 common | 50.83% [42.14, 59.79]; 61/120 | +3.33 pp [-4.63, 11.30] vs Capped N1 |
| Target−controls likelihood N8 | 17.12% [16.25, 17.95]; 1320/1320 | -0.011 pp [-0.303, 0.312] vs Capped N1; 1320/1320 common | 40.00% [30.00, 50.96]; 48/120 | -7.50 pp [-15.65, 0.85] vs Capped N1 |
| Own likelihood N8 | 17.49% [16.64, 18.33]; 1320/1320 | +0.356 pp [0.103, 0.619] vs Capped N1; 1320/1320 common | 44.17% [35.34, 53.57]; 53/120 | -3.33 pp [-10.26, 3.64] vs Capped N1 |
| Control likelihood N8 | 17.37% [16.57, 18.17]; 1320/1320 | +0.235 pp [-0.018, 0.509] vs Capped N1; 1320/1320 common | 46.67% [38.18, 55.37]; 56/120 | -0.83 pp [-11.02, 10.17] vs Capped N1 |
| Semantic consensus 2/16 | 2.91% [2.70, 3.15]; 1320/1320 | -8.296 pp [-8.824, -7.738] vs Exact support-zero; 1320/1320 common | 40.83% [31.30, 50.88]; 49/120 | -5.83 pp [-14.18, 2.16] vs Exact support-zero |
| Exact consensus 2/16 | 2.52% [2.29, 2.78]; 1320/1320 | -14.615 pp [-15.369, -13.885] vs Capped N1; 1320/1320 common | 38.33% [29.20, 47.93]; 46/120 | -9.17 pp [-18.18, 0.00] vs Capped N1 |
| Pooled target/control parent | 22.21% [21.29, 23.17]; 1320/1320 | Unavailable | 38.33% [28.33, 49.18]; 46/120 | -9.17 pp [-18.64, 0.81] vs Capped N1 |
| Prune pooled target/control, .005 | 22.03% [21.08, 22.98]; 1320/1320 | -0.183 pp [-0.195, -0.170] vs Pooled target/control parent; 1320/1320 common | 42.50% [33.33, 52.10]; 51/120 | +4.17 pp [-0.93, 9.17] vs Pooled target/control parent |

**Additional recorded fit diagnostics:** N16→N32: +1.006 pp [0.913, 1.107] vs Best N16; 1320/1320 common. Pooling beyond best complete N32: +2.018 pp [1.903, 2.137] vs Best N32; 1320/1320 common. The pooling-versus-best fit comparison is secondary; no corresponding native paired contrast is present in this source, so absolute quality counts do not supply a paired CI.

## Who did what

Best-of-1/16/32 fit increases 19.32%→22.57%→23.08% while whole-question binding recovery goes 78→81→77 of 100; N16→N32 adds +0.503 pp [0.487, 0.519] fit, the corresponding native paired quality interval is unavailable for this prefix contrast. Pooling adds +1.963 pp [1.947, 1.980] over best-of-32 and recovers 81/100, while target/control selection also recovers 81/100 with 20.92% fit; pruning loses 0.162 pp fit and changes 77→76/100 with a paired quality interval crossing zero. Semantic consensus fit is available on 11,276/11,400 sites but its native role endpoint is not; exact consensus’s 1/100 is a different setting, not a substitute, and role likelihood/editing remain unmeasured here while the reviewed role example retains conflicting details.

| Setting | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common/intended sites | Native endpoint, 95% CI; count | Paired native change, 95% CI |
|---|---|---|---|---|
| Capped N1 | 19.40% [19.24, 19.56]; 11357/11400 | — | 78.00% [70.00, 85.00]; 78/100 | — |
| Best N1 | 19.32% [19.16, 19.48]; 11400/11400 | -0.004 pp [-0.010, 0.000] vs Capped N1; 11357/11400 common | 78.00% [70.00, 85.00]; 78/100 | +0.00 pp [0.00, 0.00] vs Capped N1 |
| Best N16 | 22.57% [22.40, 22.74]; 11400/11400 | +3.172 pp [3.131, 3.217] vs Capped N1; 11357/11400 common | 81.00% [74.00, 87.00]; 81/100 | +3.00 pp [-2.00, 8.00] vs Capped N1 |
| Best N32 | 23.08% [22.91, 23.23]; 11400/11400 | +3.674 pp [3.632, 3.718] vs Capped N1; 11357/11400 common | 77.00% [70.00, 84.00]; 77/100 | -1.00 pp [-6.00, 4.00] vs Capped N1 |
| Pooling N32 | 25.04% [24.87, 25.20]; 11400/11400 | +5.635 pp [5.590, 5.680] vs Capped N1; 11357/11400 common | 81.00% [73.00, 88.00]; 81/100 | +3.00 pp [-3.00, 10.00] vs Capped N1 |
| Prune best N32, .005 | 22.92% [22.75, 23.08]; 11400/11400 | -0.162 pp [-0.165, -0.159] vs Best N32; 11400/11400 common | 76.00% [69.00, 83.00]; 76/100 | -1.00 pp [-5.00, 3.00] vs Best N32 |
| Target/control selection N32 | 20.92% [20.72, 21.11]; 11400/11400 | +1.521 pp [1.443, 1.600] vs Capped N1; 11357/11400 common | 81.00% [74.00, 88.00]; 81/100 | +3.00 pp [-4.00, 9.00] vs Capped N1 |
| Target−controls likelihood N8 | Unavailable; 0/11400 | Unavailable | Unmeasured | No recorded contrast |
| Own likelihood N8 | Unavailable; 0/11400 | Unavailable | Unmeasured | No recorded contrast |
| Control likelihood N8 | Unavailable; 0/11400 | Unavailable | Unmeasured | No recorded contrast |
| Semantic consensus 2/16 | 3.42% [3.28, 3.55]; 11276/11400 | -15.895 pp [-16.066, -15.723] vs Exact support-zero; 11265/11400 common | Unmeasured | No recorded contrast |
| Exact consensus 2/16 | 2.34% [2.22, 2.46]; 11271/11400 | -17.079 pp [-17.240, -16.918] vs Capped N1; 11264/11400 common | 1.00% [0.00, 3.00]; 1/100 | -77.00 pp [-84.00, -69.00] vs Capped N1 |
| Pooled target/control parent | 19.36% [18.96, 19.75]; 11400/11400 | Unavailable | Unmeasured | No recorded contrast |
| Prune pooled target/control, .005 | 19.16% [18.76, 19.54]; 11400/11400 | -0.197 pp [-0.202, -0.193] vs Pooled target/control parent; 11400/11400 common | Unmeasured | No recorded contrast |

**Additional recorded fit diagnostics:** N16→N32: +0.503 pp [0.487, 0.519] vs Best N16; 11400/11400 common. Pooling beyond best complete N32: +1.963 pp [1.947, 1.980] vs Best N32; 11400/11400 common. The pooling-versus-best fit comparison is secondary; no corresponding native paired contrast is present in this source, so absolute quality counts do not supply a paired CI.

## Exact settings and field contract

| Label | Condition ID |
|---|---|
| Capped N1 | `capped_n1-n1` |
| Best N1 | `best_n_exact-n1` |
| Best N16 | `best_n_exact-n16` |
| Best N32 | `best_n_exact-n32` |
| Pooling N32 | `pooled_greedy_swap-n32` |
| Prune best N32, .005 | `prune_loo_a32_0.005-n32` |
| Target/control selection N32 | `best_n_specificity_mean-n32` |
| Target−controls likelihood N8 | `likelihood_true_minus_mean_two_controls-n8` |
| Own likelihood N8 | `own_mean_log_likelihood-n8` |
| Control likelihood N8 | `control_mean_log_likelihood-n8` |
| Semantic consensus 2/16 | `consensus_semantic_v5_support0.125_compaton_vetoon-n16` |
| Exact consensus 2/16 | `consensus_exact_support0.125-n16` |
| Pooled target/control parent | `pooled_specificity_mean-n32` |
| Prune pooled target/control, .005 | `pooled_specificity_mean_then_prune_0.005-n32` |

Exact support-zero reference: `consensus_exact_support0-n16`. Editing rounds 1/2 have no fit or native results in these pinned sources; the draft-v3 contrast against `pooled_greedy_swap-n32` remains pending. All three role likelihood variants lack fit/native rows; hall likelihood native quality is absent. The pooled target/control pruning row uses its actual pooled-specificity parent, distinct from ordinary pooling/pruning.

Absolute fit fields: `rows[i].mean_fve`, `.mean_fve_ci95`, `.mean_fve_percentage_points`, `.mean_fve_ci95_percentage_points`, `.scored_site_count`, `.full_site_count`, `.mean_fve_warnings`. Paired fit fields: `rows[i].parent_comparisons[j].{reference,kind,mean_delta,ci95_delta,mean_delta_percentage_points,ci95_delta_percentage_points,paired_sites,intended_paired_sites,reference_mean_same_mask,proposed_mean_same_mask,warning}`. Native absolute fields: `cohorts.full.rows[k].metric.{value,numerator,denominator,ci95,warnings}`; paired: `cohorts.full.comparisons[k].{condition,reference,family,delta,ci95_delta,simultaneous_ci95_delta}`. The JSON retains exact indices, identities and all matching unavailable editor comparison records, including their distinct kinds; nulls/warnings are not replaced.

Sampling/pooling/pruning/specificity reuse cached original candidates/vectors in this campaign; new-input inference still needs those components. Ordinary/medium semantic labels and editor proposal/encoding phases are shared across variants; table rows are not separate full API charges. The three likelihood signals use N8 candidates with distinct target/control conditioning; no independent reader experiment was run. Mechanism explanations remain hypotheses, and examples do not estimate prevalence.

Native source: `${OLENS_DATA_ROOT}/expansion-v1/analysis/first-live-v3.json`, SHA `eea3510637c4f0b849585882e88f6dec00f85073f10525460070ab70e75d8082`; reconstruction: `${OLENS_DATA_ROOT}/expansion-v1/reconstruction/first-live-v3.json`, SHA `c7d6ee68c9481fc52e7bbbd01cda416c416b8f8bf15854a730977e958ded7e75`; read presentation draft v3 SHA `d1889a8c31c5422b5805577cf00e8df9b353e81af9ac84a79a72a5c9bb17b2f7`. Native snapshot: 2026-10-11T02:37:32.366532+00:00; reconstruction snapshot: 2026-10-11T02:45:05.558901+00:00.
