# Contrastive checks, editing and independent-reader review

Status: the primary GPT-6.1 Sol review and rotating independent Sol review are complete. This uses the [eight sealed development examples](../../configs/qualitative_shared_panel_v1.json) and the [common review protocol](../QUALITATIVE_REVIEW.md). No TEST quality, new inference or paid calls were used. Examples illustrate behavior; they do not estimate improvement rates.

The exact texts, original context, retained judgments, scoring/edit lineage and source hashes are in the immutable [full case artifact](${OLENS_DATA_ROOT}/analysis/qualitative-shared-v1/efg-review.json), SHA256 `3316be52e8ed848861a59265f5c6dbff0e717c89b8166bb49264486557d2c52b`. The tracked [coverage manifest](efg-review-v1.manifest.json) contains no full case payload. Original verdicts are preserved even where the manual interpretation is more cautious.

## Main findings

- Comparing against other activations can change the selected wording without fixing wrong entities, arithmetic or explanation details. A passing recovery match can coexist with several unsupported claims.
- Likelihood selection has a useful DETR example, but also loses an exact Simula bridge match. Its own-likelihood and control-likelihood controls reveal how similar prose can receive different action-inference judgments.
- Editing changes none of the eight shared final readouts. Two separately marked rare edits demonstrate cleanup and added wording, without an established recovery gain.
- J++ provides token evidence at four shared anchors, with four missing. It produces no vetted final prose here. Token presence cannot establish a complete number, name, or relation direction; missing tokens do not establish falsehood.

## Fixed-panel coverage

All readout variants have eight available outputs and complete retained judgments. Raw and capped N1 are identical at these eight anchors; neither is omitted. Comparators use the same persisted pool: A32 for mean/max specificity, mean specificity for its abstention control, A8 for likelihood variants, and D32 for editing. A8 and A32 use different candidate budgets.

| Variant | Text unchanged from its parent | Empty outputs |
|---|---:|---:|
| Mean-control specificity | 6/8 | 0 |
| Maximum-control specificity | 3/8 | 0 |
| Mean specificity with nonpositive-score abstention | 7/8 | 1 |
| True-minus-control mean likelihood | 2/8 | 0 |
| Own mean likelihood | 0/8 | 0 |
| Control mean likelihood | 1/8 | 0 |
| Editing round 1 | 8/8 | 0 |
| Editing round 2 | 8/8 | 0 |

E2 controlled phrase evidence is available at three anchors: both chain examples and the comedian example. G has one existing sample-conditioned lexical diagnostic at the Simula anchor and controlled phrase diagnostics at those same three E2 anchors. These overlap neither into extra independent examples nor into eight complete G readouts. No verified negation diagnostic, compatible second AR result, or NLA layer-42 result is available.

## Contrastive checks: what the texts show

**Chemistry, `chat-lmsys-0052`, L20 p253:** the transcript concerns sodium nitrite. A32 and mean specificity retain “benzoic acid”; likelihood contrast selects “potassium nitrate,” while own/control likelihood select “iodine.” All remain officially hallucinated. The common chemistry topic and reference-table style conceal an entity substitution.

**DETR, `chat-lmsys-0023`, L60 p464:** compared with **A8**, likelihood contrast changes the official class from hallucinated to consistent, removing A8’s “DETRv2/DETR-TS” attribution. A32 and mean specificity are already consistent at this anchor; this is not an improvement over A32. The likelihood output still retains truncated “DETR-D” and “DETR-T” attributions as well as attention and feature-reuse explanations. Its stage-two evidence counts three true and seven unverifiable claims. Unverifiable claims are not false; the class improvement does not mean every questionable variant name disappeared or validate DETR’s mechanism. Own/control likelihood, also compared with A8, instead retain an unsupported average-pooling explanation and stay hallucinated.

**Simula, `mhh-1967-norwegian-classes-objects-codesigner`, L44 p28:** the required bridge is “Simula 67” or “the Simula language,” not a collaborator name. A32/mean specificity include the bridge amid Ole Kjellson, Per Øreland, Ole Dahl and Kai Nygaard. Relative to the passing **A8** comparator, contrast likelihood loses the exact bridge match despite mentioning Simula and Ole Dahl, and adds an Object Pascal continuation. Preserve the failed official match; it is not complete absence of the topic. At the other MT anchor, Enkidu survives amid multiple invented monster names and attributes. Mention recovery does not validate the surrounding story.

**Both chain anchors:** the correct intermediate is 5 for `chain-w2-d2p-0013` and 10 for `chain-d2p-0385`. Selected texts repeatedly state final 14 or unrelated numbers/calculations, without recovering those intermediates. For example, “The sum is 9 + 15 = 2” is wrong arithmetic even though other bullets repeat the correct final 14. Different wrong explanations remain wrong.

**Waiter, `oa-waiter-customer-apologize-ab`, L20 p92:** nonempty variants remain summary commands and unrelated names rather than Marcus apologizing to Priya. Nonpositive-score abstention removes the unusable output, but recovers no relation. The stopping rule is not a falsehood detector.

**Comedian, `oa-comedian-heckler-humiliate-ab`, L60 p178:** mean specificity retains the passing A32 text. Maximum specificity still describes a “sharp, witty rebuttal,” but the judge declines the humiliation option. Own/control likelihood variants receive passing humiliation choices, while the contrast/A8 text does not. The scene and broad comedian-to-heckler direction are similar; the precise action inference is judge-sensitive. Descriptions without names are allowed by the official protocol, so missing names alone are not failures.

## Editing: unchanged anchors and two rare changes

Both editing rounds retain D32 verbatim on all eight anchors. That preserves successful mentions and existing failures, including wrong chain calculations and competing names. Keeping an unchanged parent is an intended option, not an execution failure.

Two supplements were selected by seeded SHA ordering from all eight edited winners in the full 189-cell pilot. They are outcome-selected rare cases, not additional panel members or evidence of a rate. No recovery win is claimed.

- `chat-dailydialog-0047`, L60 p182: round 2 completes “a” as “a first step” and “whenever you” as “whenever you need it.” Those additions exceed punctuation cleanup. The last bullet has 36 tokens; only its first 32 are encoded, so “need it” receives no direct AR evidence. The official class changes consistent → generic, with no wrong-class reduction. They are not independently demonstrated contradictions.
- `oa-lawyer-witness-interrogate-ab`, L60 p150: editing trims cut-off endings and changes “utilizing” to “using,” but retains plaintiff, prosecution witness, defendant and Sandra across bullets. The legal action remains recoverable; the competing patient descriptions remain unresolved.

The complete previous [editing audit](../experiments/010-editing-scoring.md) supplies the wider pilot evidence. The current small pilot showed no aggregate recovery gain; larger-scale editing remains unmeasured rather than ruled out.

## Independent token reader: evidence and limits

At the Simula anchor, the existing reader ranks components of both plausible and incorrect names. For instance, “Ole Johansen” contains a token ranked 30 while other components rank far lower. A strong component is not confirmation of that full collaborator.

At the first chain anchor, the AR near-miss comparison slightly prefers intermediate 15 over correct 5 on the correct-5 target (margin −0.000580). J++ ranks digit `5` identically whether it appears as `5` or within `15`; these are component logits, not sequence probabilities. At the second chain anchor, its digit ranks likewise cannot establish the complete intermediate 10. These controlled checks diagnose scorer limits, not hidden-state ground truth.

At the comedian anchor, the abstract opposite-direction phrases have identical token multisets. “ comedian” ranks 14, but this cannot distinguish “The comedian humiliated the heckler” from “The heckler humiliated the comedian.” The named variant changes people as well as order; its lexical differences are not a pure direction check. Released J++ fitting-data overlap remains unresolved, so this is development-only diagnostic evidence, not clean held-out improvement or an independent benchmark judge.

## Effort, remaining coverage and review handoff

E1 reuses N32 samples and local AR vectors plus frozen control fits. E3 adds true/control likelihood forwards to the N8 pool: the recorded 189-cell scoring workload was 176.151 seconds, 194.642 seconds including setup. Editing adds helper proposals and fresh AR scoring: historical incremental helper spend was $0.0533604, with 1,263 new raw vectors encoded in 75.683 seconds. These are source-recorded campaign workloads, not equal standalone deployment costs. [Measured costs](../experiments/013-measured-costs.md) separate reuse from fresh-input effort.

Full source suffixes remain in the artifact even when the AR sees only its cleaned first 32 tokens per bullet. G adds local token-reader work and no prose selection; deferred readers and negation remain explicitly unmeasured. The shared panel provides no new evidence for unrun likelihood/reconstruction hybrids.

The independent reviewer inspected all eight fixed texts and retained evidence, confirming comparator matching, unchanged F parents, G coverage and the Simula/comedian qualifications. Its requested DETR wording correction is incorporated above and in the separate immutable review receipt; the original full case artifact remains unchanged. The summaries are ready for coordinator review and bounded public cards, rather than unrestricted publication of raw context/cache records.
