# A/C/D: fixed-case qualitative review

Status: root approved after the [independent crosscheck](acd-review-v1.crosscheck.json) verified all 326 output references and inspected the eight anchors and six supplements. Reviewer: `compute_storage_audit`. This is an illustrative development review, not a rate estimate or inspection of TEST outcomes. The [sealed eight-cell panel](../../configs/qualitative_shared_panel_v1.json) and [shared protocol](../QUALITATIVE_REVIEW.md) are unchanged.

The full retained evidence is `${OLENS_DATA_ROOT}/analysis/qualitative-shared-v1/acd-review.json`, SHA256 `da61cff192ed155fc775805debe861ef6b596485b31f20ada1e70fbeddc3eaeb` (4.0 MB). It preserves source stimuli, exact outputs, original sample/bullet IDs, parser flags, fresh activation provenance, numeric selection records, original judge evidence and exact source hashes. [The compact annotations](acd-review-v1.json) bind each output by text hash. Official verdicts remain unchanged.

All eight anchors have all **38 A/C/D, baseline and numerical-control variants** from the retained 40-arm selector run; the two E variants are reviewed separately. Twenty variants have authoritative pilot judgments, while eighteen remain explicitly unjudged. There are 304 fixed-anchor output records plus 22 output records across six bounded supplements. Every distinct fixed-anchor text was inspected. This does not turn the numerical-only variants into evaluated methods.

## Main observations

Choosing a complete sample can recover the benchmark's required mention while retaining invented entities or calculations. Removing bullets sometimes removes an explicit wrong identity, but can also leave unsupported fragments or delete the only useful mention. Pooling does not check semantic compatibility between independently useful bullets; several cases combine wrong names, event ownership or calculations.

The six exact-solver and released-80-step sample-prefix choices select identical text on these eight anchors. This is local output agreement, not numerical equivalence or a population result. The maximum reconstruction score is nondecreasing for a nested pool by construction; the quality judgments can change in either direction.

## Eight shared anchors

`N` is the recorded sample prefix. The primary comparisons below use capped N1, A16/A32, C's A32 leave-one-out pruning at .001/.005, and D16/D32 pooling. All source context and judge details are in the durable case record.

| Anchor | Source and before/after interpretation |
|---|---|
| Sodium nitrite, L20 p253 | Capped N1 substitutes potassium chloride; A32 substitutes benzoic acid. Both are flagged. C .005 removes the benzoic-acid bullet: 116 → 55 tokens, four → two bullets, official hallucinated → consistent. The survivor gives no sodium-nitrite value; stage 2 records zero supported claims and one unverifiable claim. D substitutes an unsupported room-temperature number. This is topic similarity and selective deletion, not recovery of the requested fact. |
| DETR small objects, L60 p464 | A16/A32 avoid the baseline's DETR-D wording and receive consistent labels. Their additional attention/query/position explanations are not stated by the transcript; A32 has four unverifiable claims. C removes an incomplete first bullet, keeping consistent at 101 → 82 tokens. D16/D32 select the same text and the judge flags “Later versions (DETR).” A label improvement need not validate the added causal detail. |
| Simula co-designer, L44 p28 | The source names Ole-Johan Dahl and Kristen Nygaard. A16/A32 recover the required Simula 67 bridge but invent collaborators. A32's “Kai Nygaard” also triggers the optional target matcher, which is not exact correct identity. C removes that target-bearing bullet and keeps wrong collaborator bullets; bridge pass stays true at 97 → 38 tokens. D mixes more collaborators while retaining the bridge. |
| Enkidu/Humbaba, L60 p46 | A16 and A32 are unchanged. They acquire Enkidu and pass the bridge endpoint, while retaining unsupported aliases and attributes. C reduces 101 → 45 tokens but keeps the Gogmagog-or-Humbaba wording. D combines Goliath/Yaksha and other descriptions. Required-name recovery coexists with an unreliable narrative. |
| Add 3, then 9, L60 p62 | The source chain is 2 → 5 → 14. Primary A/C/D outputs mention final 14 but miss the tested intermediate 5 and use mismatched operands. C keeps “9 + 15 = 2”; D mixes several incompatible 14-prefixed fragments. All primary conditions fail the intermediate endpoint. Mentioning the final answer is not recovery of the chain. |
| Halve 20, then add 5, L20 p66 | The source chain is 20 → 10 → 15. A outputs subtraction, different starting values or unrelated results. C shortens 88 → 49 tokens without recovering 10. D shares the start value but substitutes subtraction/division/rounding. The answer-instruction style survives while the actual operations do not. |
| Waiter apologizes to customer, L20 p92 | Capped N1/A32 are incomplete summarization instructions with unrelated people, not the Marcus/Priya scene. The judge abstains on all three questions. C .005 leaves one 15-token instruction about Elias. D introduces dinner/financial fragments. More sampling or shorter output does not produce the directed relation here. |
| Comedian humiliates heckler, L60 p178 | Capped N1 already passes. A16 loses the action choice; A32 passes through the scathing-comeback wording but adds comedian Tyler. C removes that extra name and retains pass at 114 → 55 tokens. D16 fails the action choice; D32 passes but mixes Matthew Reily, Marcus and Chris. The task permits descriptions instead of names, so missing the heckler's name is not itself failure. Extra incompatible identities still undermine whole-output faithfulness. |

The exact item IDs, positions and related groups are in the sealed panel and compact manifest. Both chain anchors fail across the primary variants; they are useful no-gain observations, not cases to replace.

## Bounded, selected supplements

One official apparent win and one regression per method group were selected from changed cells excluding the anchors by a recorded seeded hash ordering. They are outcome-selected examples; they do not supply representative frequencies or new method settings.

| Method and case | What the official change does and does not show |
|---|---|
| A, DETR L60 p20 | Hallucinated → consistent removes several flagged model names, but the new text still includes a ViT/Google Research bullet absent from the DETR source. Stage 2 reports two off-topic claims and only one supported claim. |
| A, ICAO L60 p471 | Consistent → hallucinated adds the flagged Annex 6/PANS-OPS wording. The baseline already had four unverifiable claims and zero supported claims. No external aviation fact check was performed. |
| C, DETR L60 p279 | Hallucinated → consistent **retains the exact sentence previously flagged as wrong**, beginning “Since DETR lacks anchor boxes.” The change cannot be described as removal of that assertion; it is direct judge disagreement across contexts. |
| C, add-3/add-9 L44 p62 | A32 passes because intermediate 5 appears inside wrong or mismatched computations. Pruning removes the hit and fails. This is lost mention coverage, not deletion from an otherwise correct derivation. |
| D, party invitation L20 p123 | Hallucinated → consistent keeps a packing-list proposal and adds unsupported solo-outing wording. The class change does not show that every unsupported addition was corrected. |
| D, daughter worries about father L60 p126 | A32 passes despite “son,” Dan and an unaware Peter. Pooling adds Bill, David and Nora receiving a positive test, making the worry target unclear; the patient choice becomes “cannot tell.” The parent was already an unreliable explanation. |

## Controls, variants and practical effort

The packet retains raw and capped N1, all six exact/released-solver prefixes, all six same-pool random draws, D16/D32, pruning of A32 and N1, coefficient pruning, and matched random deletion. Unjudged random-deletion/coefficient/N1-pruning variants can illustrate exactly what was removed, but cannot support benchmark-quality comparisons. Neither these anchors nor their supplements establish that a deterministic deletion beats matched random deletion on the population.

A requires candidate generation and bullet encoding before reconstruction selection; raw/capped N1 do not need that encoder. C inherits its parent's generation/encoding and adds refits, while D inherits the same sample pool and adds pooled search/swaps. C/D use no runtime helper calls here. Shared cached replay is distinct from this recurring new-input work. No per-case fresh latency, GPU dollars, or summed nested timer was inferred; [the cost draft](../experiments/031-inference-cost-reporting.md) and [fresh-input timing record](../experiments/035-new-input-timing.md) carry their own measured/estimated scopes.

These readings use the pinned transcript/stimulus, not an external world-fact audit or a causal test of represented content. A trace can be supported on the benchmark endpoint while other assertions remain false, unsupported or contradictory. Independent review must preserve that distinction and any disagreement with the original judge.
