# Fit and native-quality interpretation: current four-bank snapshot

Fit and useful recovery move differently across banks. The matrix below is draft slide/report material for seven approach groups, not a ranking or a final result. Each group uses a named representative setting selected for explanation, not because it wins; all 70 frozen settings remain in the inventory and dashboard.

**Scope.** Native v3 has 235/280 complete condition–bank units and 47 settings complete in all four banks. Reconstruction v3 has 280 inventory rows, 249 defined means, 221 fully comparable rows and 28 additional partial means. A defined fit does not imply that native quality is measured. All 469 questions were previously inspected; these comparisons remain exploratory.

**Units.** Explained activation variance is `100 × (1 − squared residual / squared target)` on scored activation sites, not a correctness probability. Absolute means use each setting’s valid sites; paired fit changes use the common valid mask, shown separately. Native quality is contradictions among specific transcript readouts (lower is better), or recovery somewhere on the whole original question grid (higher is better). Hidden intermediate names require the bridge entities; the final answer is optional. Arithmetic credits only the **first ranked extracted integer**, with verbatim-number/quote verification. Who-did-what requires the full agent/action/patient binding at one site. These different endpoints must not be averaged.

**Intervals.** Every bracket is an existing grouped pointwise 95% interval; changes are percentage points (pp), proposed minus the named reference. Fit intervals are secondary diagnostics outside the 496 headline contrast family. All simultaneous headline intervals are still withheld in this partial snapshot. An interval crossing or touching zero does not establish a gain. Degenerate/undefined intervals are not evidence of certainty. No interval is reconstructed by subtracting absolute intervals.

**Case scope.** Examples below use only the source-checked fresh-v4 merged review notes (including explicitly inherited reviewed parent evidence). Outcome-selected examples illustrate changes, not prevalence. For standalone methods without a fresh reviewed example, the text says so rather than borrowing an unreviewed trace.

## Choose a complete readout

**Setting:** Best of 32 by reconstruction (`best_n_exact-n32`). **Reference:** Capped first sample (`capped_n1-n1`).

| Bank | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common sites | Native quality, count and 95% CI | Paired quality change, 95% CI | Interpretation |
|---|---|---|---|---|---|
| Transcript contradictions | 42.50% [41.57, 43.40]; 5615/5615 | +5.407 pp [5.246, 5.570]; 5615/5615 | 45.82% (2550/5565) [42.28, 49.37] | -1.73 pp [-3.14, -0.33] | Reconstruction rises while contradictions fall modestly; the paired contradiction interval stays below zero. |
| Hidden intermediate names | 35.17% [33.57, 36.77]; 1100/1100 | +4.972 pp [4.693, 5.257]; 1100/1100 | 40.00% (40/100) [30.10, 50.00] | +6.00 pp [0.00, 12.24] | Reconstruction rises; six more questions recover a required hidden name. The paired interval reaches zero. |
| Intermediate numbers | 23.79% [22.93, 24.66]; 1320/1320 | +6.656 pp [6.335, 7.007]; 1320/1320 | 50.83% (61/120) [40.62, 61.34] | +3.33 pp [-6.31, 13.18] | Reconstruction rises; four more questions recover the first-ranked required integer. The paired interval includes loss and gain. |
| Who did what | 23.08% [22.91, 23.23]; 11400/11400 | +3.674 pp [3.632, 3.718]; 11357/11400 | 77.00% (77/100) [70.00, 84.00] | -1.00 pp [-6.00, 4.00] | Reconstruction rises; one fewer question recovers a complete binding. The paired interval includes loss and gain. |

**Hypothesis:** Choosing by fit can favor informative text, but fit is not a check of its claims. The role result shows that larger fit gains need not raise native quality.

**Effort:** Reuse the same 32 original samples and cached text vectors. New-input inference still needs candidate generation and reconstruction scoring; campaign cache reuse does not make that deployment work free.

**Example limit:** No standalone fresh-v4 reviewed trace is assigned to this group. The statements above describe measured aggregate changes; they do not invent a case-level explanation.

## Keep repeated statements

**Setting:** Ordinary semantic repetition: at least 2/16, compatibility and veto (`consensus_semantic_v5_support0.125_compaton_vetoon-n16`). **Reference:** Exact-support zero threshold (`consensus_exact_support0-n16`).

| Bank | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common sites | Native quality, count and 95% CI | Paired quality change, 95% CI | Interpretation |
|---|---|---|---|---|---|
| Transcript contradictions | 9.21% [8.20, 10.28]; 5615/5615 | -27.661 pp [-28.701, -26.600]; 5615/5615 | 21.14% (377/1783) [17.88, 24.63] | -25.81 pp [-29.16, -22.43] | Contradictions among specific outputs fall sharply while explained variance falls. The smaller assertion denominator must accompany this result. |
| Hidden intermediate names | 3.80% [2.97, 4.69]; 1100/1100 | -26.319 pp [-28.044, -24.639]; 1100/1100 | 5.00% (5/100) [1.01, 9.80] | -29.00 pp [-38.14, -20.00] | Only five questions retain a required hidden name; a sharp fit loss accompanies 29 fewer recovered questions. |
| Intermediate numbers | 2.91% [2.70, 3.15]; 1320/1320 | -8.296 pp [-8.824, -7.738]; 1320/1320 | 40.83% (49/120) [31.30, 50.88] | -5.83 pp [-14.18, 2.16] | Fit falls substantially; seven fewer questions pass, with a paired interval crossing zero. A correct final answer alone is not the required intermediate. |
| Who did what† | 2.34% [2.22, 2.46]; 11271/11400 | -17.079 pp [-17.240, -16.918]; 11264/11400 | 1.00% (1/100) [0.00, 3.00] | -77.00 pp [-84.00, -69.00] | Exact repetition at least 2/16 retains only one question-level binding; most fit is removed. This row is the measured exact control, not an estimate of the unjudged semantic-role setting. |

† Role uses the measured exact-repetition setting `consensus_exact_support0.125-n16` versus capped N1. Its semantic counterpart has fit 3.42% [3.28, 3.55] on 11,276/11,400 sites, with recorded paired fit −15.895 pp [−16.066, −15.723] versus exact-support zero on 11,265/11,400 common sites; native quality is absent from this snapshot. This is not an inferred role recovery result.

**Hypothesis:** Repetition and compatibility may suppress weak or conflicting claims, but they can also omit a rare correct bridge or binding. Shorter text and missing assertions can reduce contradiction rates without improving useful recovery.

**Effort:** Reuse the original N16 pool. Ordinary semantic labels are shared across five variants, medium labels across four; do not charge each variant as a new full helper run. Medium uses the same proposal/pair identities. Exact repetition has no helper calls.

## Remove weak bullets

**Setting:** Delete bullets within 0.005 fit loss (`prune_loo_a32_0.005-n32`). **Reference:** Best complete readout, N32 (`best_n_exact-n32`).

| Bank | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common sites | Native quality, count and 95% CI | Paired quality change, 95% CI | Interpretation |
|---|---|---|---|---|---|
| Transcript contradictions | 42.35% [41.44, 43.26]; 5615/5615 | -0.151 pp [-0.156, -0.146]; 5615/5615 | 40.61% (2261/5567) [37.05, 44.21] | -5.21 pp [-6.64, -3.80] | A tiny fit loss accompanies fewer contradictions; the paired contradiction interval stays below zero. |
| Hidden intermediate names | 35.01% [33.43, 36.63]; 1100/1100 | -0.160 pp [-0.171, -0.149]; 1100/1100 | 31.00% (31/100) [21.87, 40.59] | -9.00 pp [-15.00, -3.92] | A tiny fit loss accompanies nine fewer bridge-recovered questions; the paired recovery interval stays below zero. |
| Intermediate numbers | 23.68% [22.84, 24.54]; 1320/1320 | -0.110 pp [-0.120, -0.100]; 1320/1320 | 46.67% (56/120) [36.75, 57.39] | -4.17 pp [-11.43, 3.06] | A tiny fit loss accompanies five fewer primary-integer recoveries; the paired interval includes no change. |
| Who did what | 22.92% [22.75, 23.08]; 11400/11400 | -0.162 pp [-0.165, -0.159]; 11400/11400 | 76.00% (76/100) [69.00, 83.00] | -1.00 pp [-5.00, 3.00] | A tiny fit loss accompanies one fewer complete binding; the paired interval includes no change. |

**Hypothesis:** A bullet can carry a required name or binding even when it contributes little to reconstruction. The transcript benefit does not establish the same benefit for entity recovery, or an advantage over length-matched random deletion.

**Effort:** Pruning reuses the selected parent and its encoded bullets; it adds CPU refits, not new lens samples or helper calls. Matched random-deletion controls are recorded. These are direct parent comparisons; do not describe every improvement as targeted semantic filtering.

**Example limit:** No standalone fresh-v4 reviewed trace is assigned to this group. The statements above describe measured aggregate changes; they do not invent a case-level explanation.

## Combine original bullets

**Setting:** Jointly fit up to four bullets, N32 (`pooled_greedy_swap-n32`). **Reference:** Capped first sample (`capped_n1-n1`).

| Bank | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common sites | Native quality, count and 95% CI | Paired quality change, 95% CI | Interpretation |
|---|---|---|---|---|---|
| Transcript contradictions | 45.03% [44.14, 45.92]; 5615/5615 | +7.937 pp [7.729, 8.149]; 5615/5615 | 47.18% (2621/5555) [43.78, 50.71] | -0.37 pp [-1.81, 1.07] | Fit rises clearly; the contradiction change is small and its paired interval crosses zero. |
| Hidden intermediate names | 37.42% [35.84, 39.00]; 1100/1100 | +7.219 pp [6.900, 7.558]; 1100/1100 | 41.00% (41/100) [31.31, 51.02] | +7.00 pp [0.00, 14.43] | Fit rises; seven more questions recover a hidden name, with the paired interval touching zero. |
| Intermediate numbers | 25.81% [25.00, 26.67]; 1320/1320 | +8.674 pp [8.327, 9.057]; 1320/1320 | 44.17% (53/120) [34.45, 54.17] | -3.33 pp [-12.73, 6.19] | Fit rises; four fewer questions recover the primary required integer, with an interval crossing zero. |
| Who did what | 25.04% [24.87, 25.20]; 11400/11400 | +5.635 pp [5.590, 5.680]; 11357/11400 | 81.00% (81/100) [73.00, 88.00] | +3.00 pp [-3.00, 10.00] | Fit rises; three more questions recover a full binding, with an interval crossing zero. |

**Hypothesis:** Combining useful fragments can improve fit while joining incompatible statements or changing which fact the reader emphasizes. Fit gain alone does not establish a coherent recovered explanation.

**Effort:** Reuse the N32 pool and encoded original bullets. Joint selection adds CPU nonnegative refits and swap search; it does not generate new phrases or invoke a helper.

## Compare activation evidence

**Setting:** Complete readout: true fit minus mean-control fit, N32 (`best_n_specificity_mean-n32`). **Reference:** Capped first sample (`capped_n1-n1`).

| Bank | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common sites | Native quality, count and 95% CI | Paired quality change, 95% CI | Interpretation |
|---|---|---|---|---|---|
| Transcript contradictions | 42.49% [41.56, 43.37]; 5615/5615 | +5.391 pp [5.232, 5.558]; 5615/5615 | 45.81% (2550/5566) [42.35, 49.34] | -1.74 pp [-3.20, -0.30] | Fit rises and contradictions fall modestly; the paired interval stays below zero. |
| Hidden intermediate names | 35.15% [33.55, 36.70]; 1100/1100 | +4.950 pp [4.674, 5.229]; 1100/1100 | 41.00% (41/100) [31.25, 50.98] | +7.00 pp [0.98, 13.59] | Fit rises; seven more hidden-name recoveries have a positive paired pointwise interval. |
| Intermediate numbers | 22.04% [21.07, 23.02]; 1320/1320 | +4.906 pp [4.531, 5.326]; 1320/1320 | 50.83% (61/120) [42.14, 59.79] | +3.33 pp [-4.63, 11.30] | Fit rises; four more primary-integer recoveries have a paired interval crossing zero. |
| Who did what | 20.92% [20.72, 21.11]; 11400/11400 | +1.521 pp [1.443, 1.600]; 11357/11400 | 81.00% (81/100) [74.00, 88.00] | +3.00 pp [-4.00, 9.00] | Fit rises; three more bindings have a paired interval crossing zero. |

**Hypothesis:** Control activations may discount broadly generic readouts. These observations do not prove that remaining prose reflects only target-specific information, and separate likelihood signals need their own controls.

**Effort:** Specificity reuses frozen candidate/vector pools but adds true/control activation scoring. The separate likelihood N8 experiment uses the same eight original candidates and true plus two control forward passes; it has no AR/NNLS selection step. No independent reader (G) experiment was run.

## Edit a readout

**Setting:** Two-round edited union (`editing_round2-n32`). **Reference:** One-round edited union (`editing_round1-n32`).

| Bank | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common sites | Native quality, count and 95% CI | Paired quality change, 95% CI | Interpretation |
|---|---|---|---|---|---|
| Transcript contradictions | Unmeasured; 0/5615 | Unavailable | Unmeasured in native v3 | Unavailable | Both rounds remain unmeasured in these pinned sources; no fit or contradiction gain can be stated. |
| Hidden intermediate names | Unmeasured; 0/1100 | Unavailable | Unmeasured in native v3 | Unavailable | Both rounds remain unmeasured in these pinned sources; no hidden-name recovery gain can be stated. |
| Intermediate numbers | Unmeasured; 0/1320 | Unavailable | Unmeasured in native v3 | Unavailable | Both rounds remain unmeasured in these pinned sources; no primary-integer recovery gain can be stated. |
| Who did what | Unmeasured; 0/11400 | Unavailable | Unmeasured in native v3 | Unavailable | Both rounds remain unmeasured in these pinned sources; no binding recovery gain can be stated. |

**Hypothesis:** Bounded edits may consolidate useful information or introduce unsupported content. This is a prospective possibility, not a result.

**Effort:** One/two Standard Luna proposal rounds, new-phrase AR encoding, and joint fits are method-inference components. The union retains original parents and previous scored proposals; accepting by reconstruction does not validate faithfulness. Benchmark judging is a separate experimental charge.

## Combine approaches

**Setting:** Pool N32, then prune within 0.005 loss (`pooled_greedy_swap_then_prune_0.005-n32`). **Reference:** Ordinary pooled output, N32 (`pooled_greedy_swap-n32`).

| Bank | Mean explained variance, 95% CI; scored/intended sites | Paired fit change, 95% CI; common sites | Native quality, count and 95% CI | Paired quality change, 95% CI | Interpretation |
|---|---|---|---|---|---|
| Transcript contradictions | 44.81% [43.91, 45.67]; 5615/5615 | -0.226 pp [-0.236, -0.217]; 5615/5615 | 44.51% (2474/5558) [40.94, 48.10] | -2.67 pp [-3.58, -1.79] | Pruning changes the pooled readout, but some reviewed class flips retain flagged phrases. Use the aggregate result and the uncertainty together. |
| Hidden intermediate names | 37.15% [35.59, 38.76]; 1100/1100 | -0.268 pp [-0.283, -0.253]; 1100/1100 | 39.00% (39/100) [29.41, 49.02] | -2.00 pp [-5.10, 0.00] | Removing bullets can remove a hidden-name witness; judge success does not require a correct optional final answer. |
| Intermediate numbers | 25.49% [24.69, 26.34]; 1320/1320 | -0.316 pp [-0.329, -0.304]; 1320/1320 | 45.83% (55/120) [35.65, 57.14] | +1.67 pp [-4.96, 8.33] | A correct required value in the text can remain lower-ranked; this endpoint credits the first ranked verified integer only. |
| Who did what | 24.77% [24.59, 24.93]; 11400/11400 | -0.275 pp [-0.278, -0.271]; 11400/11400 | 80.00% (80/100) [72.00, 87.00] | -1.00 pp [-5.00, 2.00] | Shortening generic summarize-the-scene prompts does not supply who did what; other grid sites can still recover the question. |

**Hypothesis:** Combining selection with deletion may alter both retained content and interpretation. A gain against capped N1 can be inherited from pooling; the direct parent contrast is the component evidence.

**Effort:** Reuse the named parents, original pool and encoded bullets; add only the specified refit/deletion components. Shared helper labels and edit proposals stay shared. Four edit-then-prune/delete arms are unmeasured here; do not extrapolate their behavior from pooling.

## Companion diagnostics for slide notes

**Pooling versus best complete.** This is an existing secondary fit comparison, with no corresponding frozen native paired contrast in these sources. Do not attach a quality-delta CI to it.

| Bank | Recorded paired fit change vs best complete N32; common sites |
|---|---|
| Transcript contradictions | +2.53 pp [2.45, 2.60]; 5615/5615 |
| Hidden intermediate names | +2.25 pp [2.16, 2.33]; 1100/1100 |
| Intermediate numbers | +2.02 pp [1.90, 2.14]; 1320/1320 |
| Who did what | +1.96 pp [1.95, 1.98]; 11400/11400 |

**Likelihood versus capped N1.** True-minus-two-controls likelihood, N8, is a distinct variant in activation-evidence comparison. The hall fit has been replayed even though its native judgment is absent in v3.

| Bank | Mean explained variance, 95% CI; sites | Paired fit change vs capped, 95% CI | Native quality; paired quality change vs capped, 95% CI |
|---|---|---|---|
| Transcript contradictions | 37.16% [36.18, 38.11]; 5615/5615 | +0.07 pp [-0.04, 0.18] | Unmeasured in native v3 |
| Hidden intermediate names | 30.10% [28.50, 31.70]; 1100/1100 | -0.10 pp [-0.35, 0.15] | 34.00% (34/100) [24.74, 43.57]; Δ +0.00 pp [-6.12, 6.06] |
| Intermediate numbers | 17.12% [16.25, 17.95]; 1320/1320 | -0.01 pp [-0.30, 0.31] | 40.00% (48/120) [30.00, 50.96]; Δ -7.50 pp [-15.65, 0.85] |
| Who did what | Unmeasured | Unavailable | Unmeasured in native v3 |

## Reviewed examples and usable slide bullets

| Approach/context | Exact reviewed reference | Plain-language observation |
|---|---|---|
| Pooling parent → combined pruning; transcript | `pooled_specificity_mean_then_prune_0.005-n32` vs `pooled_specificity_mean-n32`; `hallucination|chat-dailydialog-0000|L36|p00038`; docs/reviews/expanded-qualitative-v4-agent1-v2.json unit 4 | Deletion removes two bullets; the shorter readout becomes consistent, but career/work-home fragments flagged in the parent survive. Call this a preserved class change with framing uncertainty, not proof that every false claim was removed. |
| Pooling parent → combined deletion; roles | `pooled_greedy_swap_random_delete_matched_0.001-n32` vs `pooled_greedy_swap-n32`; `role_bound_association|oa-comedian-heckler-humiliate-ab|L60|p00178`; docs/reviews/expanded-qualitative-v4-agent1-v2.json unit 17 | The child is byte-identical to ordinary pooling. It recovers comedian-to-heckler direction while also naming Matthew Reily and Chris. The recovery is inherited from the parent; surrounding name contamination remains. |
| Semantic repetition; arithmetic | `consensus_semantic_v5_support0_compatoff_vetoon-n16` vs `consensus_exact_support0-n16`; `chain_intermediates|chain-d2p-0256|L28|p00061`; docs/reviews/expanded-qualitative-v4-agent1-v2.json unit 20 | Generic reasoning fragments replace the parent’s explicit 7. The sole passing question-grid witness disappears. This is a recorded component regression, not an estimate of how often all semantic settings fail. |
| Exact repetition; arithmetic | `consensus_exact_support0.125-n16` vs `capped_n1-n1`; `chain_intermediates|chain-w2-d2p-0013|L60|p00062`; docs/reviews/expanded-qualitative-v4-root-v2.json unit 9 | The late-layer readout retains final-answer 14 but no required intermediate 5. This anchor fails before and after; the reviewed whole-question loss occurs at a different site. Do not describe final-answer correctness as intermediate recovery. |
| Likelihood; hidden names | `likelihood_true_minus_mean_two_controls-n8` vs `capped_n1-n1`; `multihop_mt|mhh-adwa-baratieri|L52|p00033`; docs/reviews/expanded-qualitative-v4-agent1-v2.json unit 14 | The new readout adds Battle of Adwa, producing the only passing bridge site, while retaining incorrect commander alternatives and omitting Oreste Baratieri. Bridge recovery is not complete-answer faithfulness. |
| Likelihood; hidden names | `own_mean_log_likelihood-n8` vs `capped_n1-n1`; `multihop_mt|mhh-1967-norwegian-classes-objects-codesigner|L20|p00028`; docs/reviews/expanded-qualitative-v4-agent1-v2.json unit 13 | Both before and after recover Simula 67. The latter additionally names optional Kristen Nygaard while other co-designer names remain wrong; the question was already recovered and passing sites increase. |

**Draft action titles (representative results only):**

- Choosing the best-fitting complete sample raises fit in every bank; quality gains differ.
- Removing low-contribution bullets trades a small fit loss for fewer contradictions and some lost entity recovery.
- Combining bullets raises fit more than complete selection; useful recovery still depends on the bank.
- Repetition filters can remove both contradictions and the facts needed for recovery.
- Control-based selection and likelihood are distinct signals; bridge hits can coexist with wrong answers.
- Edited readouts await scoring and judging; no gain is established yet.
- Judge combined methods against their actual parents before attributing a component gain.

**Near misses and postponed work.** Ranked-lower integer matches, near-number matches and `any_of_3` are diagnostics only; none changes the primary arithmetic pass rule. Existing original chain results retain `numbers.extras.any_of_3_rate` and per-item `any_of_3`, while this native/dashboard snapshot exposes only primary recovery. No independent-reader G experiment, new reader comparison or newly defined quality diagnostic is included.

**Inference versus research costs.** The 621,920 original readouts and compatible encoded vectors are shared scientific inputs. Reusing them makes this campaign’s incremental work cheaper, not a zero-cost new-input pipeline. Helper proposals/labels and method components belong to inference effort; the separate Luna benchmark judge is research evaluation cost. These notes give component scope, not per-method unique API charges, invoices, GPU dollar costs or Codex-agent billing.

## Exact source binding

Generated 2026-10-11T03:15:07.580987+00:00. Draft awaiting root synthesis; no paid calls, score changes or source-text edits.

| Artifact | SHA-256 |
|---|---|
| `${OLENS_DATA_ROOT}/expansion-v1/analysis/first-live-v3.json` | `eea3510637c4f0b849585882e88f6dec00f85073f10525460070ab70e75d8082` |
| `${OLENS_DATA_ROOT}/expansion-v1/reconstruction/first-live-v3.json` | `c7d6ee68c9481fc52e7bbbd01cda416c416b8f8bf15854a730977e958ded7e75` |
| `configs/expansion_manifest_v1.json` | `753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8` |
| `docs/reviews/expanded-qualitative-v4-merged-notes-v1.json` | `1ff9945d87c319266daec27109f0ead60b64b358141725a7e9927f0178973ffc` |
| Approved arithmetic parser, lines 59–97: `${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2/src/wsbench/evals/chain_intermediates/judge.py` | `4f4d005ba32c9623e2c1a400353088d65446690632afd7d1f10a88273e32126b` |

All numerical cells were formatted directly from the two pinned JSON artifacts. Each paired row requires an existing exact condition/reference/family record; unavailable pairs remain unavailable. Case references must resolve to an exact reviewed fresh-v4 source row. Public synthetic benchmark examples are retained as supplied, not externally fact-checked.
