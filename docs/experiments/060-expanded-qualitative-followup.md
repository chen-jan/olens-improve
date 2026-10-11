# Reconstruction gains need task-specific interpretation

Status: reviewed progress snapshot, 2026-10-11 03:14 UTC. The expanded campaign remains active; editing and role-family likelihood results are pending.

This follows [the reconstruction diagnostic](059-expanded-reconstruction-and-trace-audit.md). The numeric source is `expansion-v1/reconstruction/first-live-v3.json`, SHA `c7d6ee68c9481fc52e7bbbd01cda416c416b8f8bf15854a730977e958ded7e75`, bound to native quality `analysis/first-live-v3.json`, SHA `eea3510637c4f0b849585882e88f6dec00f85073f10525460070ab70e75d8082`. Existing vectors and frozen fitting conventions are reused.

## Size of the reconstruction change

These are mean percentages of explained activation variance across valid reading sites, not percentages of correct explanations. Whole-related-group intervals, paired parent changes and scored-site masks are retained in the numeric artifact and displayed in the dashboard. The three methods share the same permitted activation grid and output cap.

| Task | Capped one-sample output | Best complete sample of 32 | Bullets combined from 32 samples |
|---|---:|---:|---:|
| Transcript contradictions | 37.09% | 42.50% | 45.03% |
| Hidden intermediate names | 30.20% | 35.17% | 37.42% |
| Intermediate numbers | 17.13% | 23.79% | 25.81% |
| Who did what | 19.40% | 23.08% | 25.04% |

The role baseline has 43 unavailable fits out of 11,400 sites, because cleaning leaves an empty reconstruction input. Its paired comparisons use common valid sites; the displayed marginal means use each method's valid sites. Missing fits are not zero. The earlier diagnostic records paired improvements and intervals. Increasing the fit from 17.13% to 25.81% on numbers does not establish more correct mathematical reasoning.

## Expanded example review

Four Sol 6.1/root source reviews inspect all 190 fresh before/after content pairs. Seventeen unchanged context-and-official-evidence pairs inherit previous reviews, covering another 29 case references. The [validated merger](../reviews/expanded-qualitative-v4-merged-notes-v1.json), SHA `1ff9945d87c319266daec27109f0ead60b64b358141725a7e9927f0178973ffc`, therefore covers all 330 new references exactly, with no duplication. It preserves full source contexts, official evidence and exact parent identities. Prior reviewed comparisons remain available; selected examples do not estimate error prevalence.

- **Transcript contradictions:** deleting a bullet sometimes changes the verdict on a statement that survives verbatim. For example, the retained “I don’t have a future” fragment becomes flagged after another bullet is deleted. Official results are preserved; this is evidence of interpretation sensitivity, not a demonstrated newly introduced false assertion.
- **Hidden intermediate names:** likelihood selection adds “Battle of Adowa” at an Adwa witness but still invents commander names. The control-only selector chooses the same local output, so that example does not demonstrate activation-specific verification. Another control-only selection preserves the final title but deletes the required Belisarius and Procopius bridges.
- **Intermediate numbers:** more focused text can make the judge rank the correct number first when it was already present. Conversely, competing wrong answers can push a retained correct number down the ranking. Some combined/pruned readouts preserve a correct intermediate operation, while apparent gains over the original are already present in their unpruned parent.
- **Who did what:** a relation hit may survive pruning alongside invented names. Early reading sites can remain generic instructions to summarize a story, even when another site makes the original question pass. A fixed example that fails locally must not be called the witness for a whole-question gain or loss elsewhere.

## The number benchmark's exact endpoint

The approved WorkspaceBench parser `chain_intermediates/judge.py`, SHA `4f4d005ba32c9623e2c1a400353088d65446690632afd7d1f10a88273e32126b`, lines 59–97, credits only the **first ranked extracted integer**, subject to its documented text/quote verification. A lower-ranked target number does not make the primary endpoint a hit. Its `any_of_3` field is a separate diagnostic, not a pass rule.

The updated [root review](../reviews/expanded-qualitative-v4-root-v2.json) and corresponding agent reviews distinguish this endpoint limitation from inconsistent grading. No official scores or output texts were changed. The dashboard now calls the family **Intermediate numbers** and explains the ranking rule, avoiding the implication that a hit verifies an entire calculation.

## Presentation

The deck's separate reconstruction scaling slide now shows all four tasks, six sampling budgets, pooled 16/32 markers, grouped intervals and explicitly named parent gains. Real populated browser checks passed; the native PowerPoint rendering has not been checked. Each approach will also have a visual explanation and a results slide with four task panels, qualitative evidence and inference effort. Final versions remain gated on completed, source-checked outputs.

At 03:32 UTC, report and slide wording explicitly preserves the number task’s first-ranked-integer rule. The final presentation can also include four task-specific notes for each approach, tied to a declared representative method/parent comparison. The report verifies all four task identities and the recorded comparison before accepting these notes; the website keeps them in an expandable section, and the slides retain them in speaker notes. Twenty focused offline report/slide checks passed on owned CPU allocation 25536417; JavaScript syntax validation passed. This changes presentation only, with no model calls or official score changes. These additional notes are not yet populated or published as final results.
