# 011: Cached combinations and component ablations

Status: sequential pruning combinations and their blind judging completed on the same 189 development pilot cells. The source-checked exact whole-bullet support plus pooling pilot and its blind judging also completed. No new O-lens generations, helper calls or GPU forwards were needed for combination selection.

`scripts/combine_pruning.py` takes three already scored complete parents: pooled greedy selection at N32, mean matched-control specificity selection at N32, and the final two-round editing selection. Each parent undergoes sequential leave-one-out deletion at the existing maximum per-deletion FVE losses .001 and .005. Every trial refits exact nonnegative least squares against the original target. The specificity parent is chosen using its existing control objective; the subsequent deletion objective is explicitly own-target reconstruction FVE. No control bank or operating threshold is changed.

The 15 conditions are three unchanged component-off parents, six parent-plus-pruning outputs and six seeded random deletion controls retaining exactly the corresponding pruned bullet count. Original source atoms and IDs survive; a no-deletion output preserves the original parent text verbatim. All output caps and fresh activation hashes are checked. Parent scores reproduce within `1e-5`. Stage inputs, deletion traces, objective, thresholds, random seeds, retained IDs, exact scores and code/input hashes are stored for subtraction ablations. Random deletion matches bullet count rather than exact token length; report remaining length differences. The .001 threshold is numerically delicate at the observed batching drift scale.

The allocated CPU run used four Torch threads and took **46.54 seconds** for 189 cells × 15 conditions. No output was empty.

| Parent | Outputs changed by .001 pruning | Outputs changed by .005 pruning | Bullets removed at .001 / .005 |
|---|---:|---:|---:|
| Pooled greedy N32 | 32/189 | 134/189 | 42 / 197 |
| Mean specificity N32 | 170/189 | 186/189 | 283 / 373 |
| Final editing N32 | 32/189 | 135/189 | 43 / 198 |

These counts quantify intervention size, not semantic improvements. In particular, more deletion may reduce both erroneous claims and useful recovery. Compare every combination with its unchanged parent, matched-count random deletion, raw/capped N1 and same-pool best-of-N. Report separate family endpoints and paired examples; do not promote a combination merely for a better fit or shorter text.

Artifacts: `${OLENS_DATA_ROOT}/selections/combined-pruning-pilot189-v1/{spec.json,selections.jsonl,conditions.json,status.json}`. The selection SHA256 is `c6737d69f467970cfdac49946bfe29c3c4cd79581a7736f2dbc42ac8ceef84b0`. The cohort remains a partial-grid cell diagnostic, not official full-grid item accuracy.

`scripts/combine_support_pooling.py` retains the exact original D16 raw-text dictionary and deterministic representative order. It normalizes support keys only with `' '.join(text.split())`, counts distinct source samples, and adds a bonus only for repeat support above one vote. For a selected set S, the objective is `Q(S) = exact_FVE(S) + (lambda/4) * sum((support-1)/15)` over its unique normalized support keys. Lambda 0/.05/.20 were frozen before scoring. Every proposed addition/swap is jointly refitted, and complete-candidate fallback uses the same combined objective and caps. Lambda0 must reproduce existing D16 text, source IDs and fit within `1e-5`; it cannot change the dictionary. One support key contributes once even when multiple raw wordings appear in a selected set. The support-only comparator ranks normalized representatives by support, with ties broken by original sample and bullet appearance, without a hard cutoff.

Support was independently recomputed from the immutable N16 prefix and checked against every exported source group. The artifact is `${OLENS_DATA_ROOT}/selections/exact-support-n16-v1`, SHA256 `a440e18d7427164e3181c6eac226c33eb3436201f559b4b842a78f06da4644db`. Only 59 of 11,969 normalized groups have repeat support: 29 chain, 17 hallucination, 1 multihop and 12 role groups. This sparse evidence limits how much the support prior can change. It remains a hypothesis about repeated whole bullets, with no semantic merges or claim-truth certification.

The support-plus-pooling run completed in 123.59 seconds on allocated CPU resources, with four Torch threads. All 189 lambda-zero outputs reproduced the existing D16 text, source IDs and score within the fixed tolerance. Its four-condition selections are `${OLENS_DATA_ROOT}/selections/support-pooling-pilot189-v1/selections.jsonl`, SHA256 `d3532c5ee359914764a455fc1a3adcb483c7c5b5bd7e637b80b795c4a17d042c`. This is implementation compatibility evidence, not semantic improvement.

## Judged specificity-plus-pruning follow-up

| Same N32 pool condition | Transcript contradictions / asserting readouts | Multihop recovery | Chain recovery | Role recovery |
|---|---:|---:|---:|---:|
| Mean-control specificity parent | 38/71 | 7/24 | 1/21 | 9/72 |
| Parent then .001 pruning | 38/70 | 7/24 | 1/21 | 12/72 |
| Parent then .005 pruning | 36/72 | 7/24 | 1/21 | 12/72 |
| Matched-count random deletion, .005 | 37/72 | 5/24 | 0/21 | 7/72 |

All three apparent role gains are retained at both thresholds, with no role pass regressions; random deletion instead loses two parent passes. The gains occur at `oa-father-daughter-worry-ab` layer 44 position 153 and `oa-lawyer-witness-interrogate-ab` layers 44/60 position 141. The pinned judge explicitly allows descriptions and partial names: the options show “Martin, the father”/“Elise, the daughter” and “Marcus, the lawyer”/“Elena, the witness”. Absence of full names is therefore **not** a protocol failure; parent/random refusals solely for missing names can be overly strict. The gains are judge-sensitive, not automatically invalid. The father/daughter output still has a son alternative; the lawyer outputs retain plaintiff/witness or wrong-name conflicts, with partial matching permitted. Deleting competing fragments could help disambiguate roles, but the comparisons do not independently verify richer binding accuracy. The exact prompt and options are preserved in the audit from pinned `src/wsbench/evals/role_bound_association/{prompts,judge}.py` and the golden option fixture.

For .005 pruning, paired hallucination transitions include eight wrong-to-nonwrong changes (six consistent, two off-topic) and six nonwrong-to-wrong changes (three formerly consistent, three off-topic). One generic parent becomes consistent. Random deletion has seven wrong-to-nonwrong and six reverse changes. Thus the aggregate extra benefit over random deletion is small. Audited retained spans sometimes change judgment: a “packing list” phrase stays in a pruned output despite its wrong-to-consistent transition; introduced-name fragments can become off-topic without being deleted. These observations motivate a controlled judge/context stability check, not automatic verdict overrides: deleting neighboring text can also change attribution and meaning.

Decision: this is a promising bounded follow-up, especially relative to matched random deletion, with enough uncertainty to require wider development coverage and trace checks. Keep the unchanged parent, both thresholds and matched deletion controls in the next full-grid comparison; do not select a favorable layer or claim an established general gain from this partial-grid pilot. Exact paired evidence, all changed cases, first-by-ID and seeded random unchanged cases are at `${OLENS_DATA_ROOT}/analysis/e1-pruning-pilot189-review-v1`; judgments are `development-shared-pilot-v2/judgments-combinations`. This review stays outside selector/helper inputs.


## Judged exact-support-plus-pooling result

| Same N16 pool condition | Transcript contradictions / asserting readouts | Multihop recovery | Chain recovery | Role recovery |
|---|---:|---:|---:|---:|
| Lambda zero, unchanged pooled selector | 43/72 | 8/24 | 1/21 | 8/72 |
| Repeat-support bonus .05 | 43/72 | 8/24 | 1/21 | 8/72 |
| Repeat-support bonus .20 | 43/71 | 8/24 | 1/21 | 8/72 |
| Exact whole-bullet support only | 42/71 | 4/24 | 0/21 | 8/72 |

The .05 bonus changes text in 17 cells but leaves every judged outcome unchanged. The .20 bonus changes 33 outputs, with no recovery transitions in any of the three recovery families. Its hallucination transitions comprise one wrong-to-consistent, one consistent-to-wrong and one consistent-to-generic output; the unchanged wrong count is not proof of identical behavior. Support-only selection loses multihop and chain recovery.

Reproducible changed and unchanged traces show the mechanism's limit. A repeated generic step-by-step instruction can gain weight without recovering the chain's missing number. Repeated playlist or getaway phrases retain the disputed packing-list content. Other boosted bullets discuss summarizing the passage rather than establish role binding. In the multihop example, the repeated Berzelius phrase was already present without recovering the required bridge. These are observed failures of sparse exact whole-bullet repetition, not evidence that carefully audited semantic consensus cannot help: paraphrases do not share votes in this arm.

Decision: no broader exact-repeat expansion on the present evidence. Keep this bounded null result and its component-off comparison; a materially different semantic-support mechanism requires its own faithful-equivalence audit. All changed-case transition counts, deterministic first-by-ID changed examples and seeded random unchanged examples, full texts, atom supports and judge evidence are saved at `${OLENS_DATA_ROOT}/analysis/support-pooling-pilot189-review-v1`. No reviewed verdicts enter selector/helper inputs.
