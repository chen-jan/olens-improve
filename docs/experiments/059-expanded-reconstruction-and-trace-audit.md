# Reconstruction gains and what the readouts actually say

Status: secondary diagnostic completed for the first expanded snapshot; final campaign remains active.

The source is `expansion-v1/reconstruction/first-live-v2.json`, SHA
`f2fbe23e5c7ded42e7d86323559495d6b20a16976b9cec578d9befb899a9fd6d`.
It binds the quality snapshot `first-live-v2.json`, SHA
`bd501f26f228e1648f2be178b2fa3a1244fe64e4719e1ac304fc47aea99be9ae`.
Reconstruction was calculated from the already cached phrase vectors. No new model encoding or paid judging was needed for this diagnostic.

## What the number means

Explained activation variance measures how well the frozen reconstructor's phrase vectors jointly approximate the target activation, using the released whitening and non-negative reconstruction conventions. It is not the percentage of claims that are true. These results average reading sites, with uncertainty obtained by resampling whole related-question groups. The benchmark's recovery scores aggregate whole questions instead; their units differ.

The table gives paired changes relative to the capped one-sample output, in **percentage points of explained variance**, with pointwise 95% intervals. These are secondary diagnostics, outside the 496 declared headline quality comparisons.

| Task | Best complete readout from 32 samples | Combine bullets from 32 samples |
|---|---:|---:|
| Transcript contradictions | +5.41 [5.25, 5.57] | +7.94 [7.73, 8.15] |
| Required hidden names | +4.97 [4.69, 5.26] | +7.22 [6.90, 7.56] |
| Arithmetic intermediates | +6.66 [6.34, 7.01] | +8.67 [8.33, 9.06] |
| Who did what to whom | +3.67 [3.63, 3.72] | +5.63 [5.59, 5.68] |

The first three paired comparisons cover all 5,615, 1,100 and 1,320 reading sites, respectively. The role comparison uses 11,357 of 11,400 sites with valid fits for both outputs. Forty-three capped baseline fits are unavailable because cleaning leaves an empty AR input; they are not assigned a score of zero. All compared methods retain the same permitted activation grid and output caps.

Increasing best-of-N from 16 to 32 adds another 0.68, 0.69, 1.01 and 0.50 points across these tasks. Combining bullets from 32 samples adds 2.53, 2.25, 2.02 and 1.96 points over the best complete 32-sample readout. These fit improvements are expected when expanding the selection/search space; their practical value depends on the separately judged output.

## Removing weak bullets can preserve fit while losing information

For pooled 32-sample readouts, sequential pruning at the 0.005 contribution threshold gives:

| Task | Change in explained variance vs unpruned parent | Mean bullets removed |
|---|---:|---:|
| Transcript contradictions | -0.23 points | 0.83 |
| Required hidden names | -0.27 points | 0.96 |
| Arithmetic intermediates | -0.32 points | 1.39 |
| Who did what to whom | -0.27 points | 1.21 |

Small reconstruction losses do not prove a deleted bullet was false. Audited cases lose the only required intermediate name or an action-bearing sentence. Other deletions remove an incorrect entity or unnecessary detail. The final report must compare each deletion to its actual parent and its matched random-deletion control, rather than crediting improvements that were already achieved by selection.

## Different tasks expose different errors

- **Transcript contradictions:** some filters remove a clearly flagged specific detail, such as an incorrect DETR variant. Other official verdict improvements keep a previously flagged assertion word for word; these examples show judge context sensitivity, not demonstrated correction. Empty, generic and unverifiable outputs need to remain visible.
- **Required hidden names:** a correct bridge name can coexist with invented collaborators or titles. Keeping the optional final answer while deleting the required intermediate can lose a whole question. Bare `Simula` does not meet this bank's strict required forms `Simula 67` or `the Simula language`; that matching rule is explicit, not a judge mistake.
- **Arithmetic intermediates:** a recovered number can occur in the wrong equation or an unrelated calculation. More reconstructive bullets may compete with the actual intermediate. Judge extraction and complete-question recovery are distinct from mathematical correctness of the prose.
- **Who did what to whom:** output may name the right roles while reversing the action, or match the action while inventing names and scene details. Some saved choice indexes contradict the saved rationale. Those official results remain unchanged and the inconsistency is documented.

The four source-only delta reviews inspect all 426 unique new content comparisons. The dashboard review contains 1,476 deduplicated comparison references across 64 currently audited settings, including previous reviews. Fixed historical examples and deterministic improvement/regression supplements are illustrative; they do not estimate how frequently a failure occurs.

## Delivery requirements

Each approach's final results slide should have four task panels, quality uncertainty, reconstruction changes and inference effort. Its accompanying explanation should identify an observed success and limitation, use actual-parent comparisons when applicable, and label proposed mechanisms as hypotheses. The final statistical, resource and qualitative artifacts will be refreshed when the remaining likelihood and editing conditions finish.
