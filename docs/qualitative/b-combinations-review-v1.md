# B and combinations: fixed-case qualitative review

Status: primary and independent reviews complete; coordinator approved the final source packet and public evidence. Reviewers: GPT-6.1 Sol, with rotating independent crosschecks. This review uses existing development pilot outputs and preserves their official verdicts. It does not inspect TEST outcomes or change any method settings. The final source packet SHA is `6752b5d44bc856fd7f9492eb79ac037a95ecc465b87150f11b8c23a1821cecde`; see the adjacent independent-review receipt.

The [sealed eight-cell panel](../../configs/qualitative_shared_panel_v1.json) and [shared protocol](../QUALITATIVE_REVIEW.md) are unchanged. The full audit is `${OLENS_DATA_ROOT}/analysis/qualitative-shared-v1/b-combinations-review.json`; [the compact source manifest](b-combinations-review-v1.sources.json) records its SHA256, source bindings and coverage. Every case retains exact parent/new text, selected bullet IDs, token/bullet counts, selection trace, evaluation-only context and original judge evidence. Manual interpretations are separate from those judgments.

## What differs in these cases

Consensus often selects generic repeated fragments rather than the useful detail. Stronger support or compatibility filters can remove an invented name, but also remove the only required bridge or leave no output. Exact matching has unambiguous grouping; it does not make repeated claims true. Semantic matching can create false support by treating different entities, qualifications or computations as equivalent.

Pruning sometimes deletes a visibly mismatched detail. It can also delete the only recovered concept, or receive a better judge label while retaining the exact assertion previously flagged. Pooling with support or specificity does not itself resolve conflicting names, operands or relation directions. These are case-level observations, not estimates of how often each outcome occurs.

## Eight shared anchors

All 38 reviewed variants use these same eight cells. The full audit includes unchanged and empty outputs rather than replacing them with better examples.

| Anchor | B and combination differences |
|---|---|
| Sodium nitrite, L20 p253 | Soft exact and several semantic variants repeat a potassium-chloride claim. Compatibility can leave only a generic increasing-solubility fragment. E-mean plus pruning at .005 removes the benzoic-acid detail and becomes consistent; matched random deletion retains it and remains wrong. The survivor still gives no sodium-nitrite boiling-water value. D-based combinations often retain the flagged `1 g/100` fragment. |
| DETR small objects, L60 p464 | Soft consensus can retain the flagged DETR-D name; compatibility keeps a generic small-object sentence. E-based pruning retains attention/query/position explanations without independently verifying their cause. One matched deletion output flags causal wording also present in a consistent targeted-pruning output. The pooled parent and several combinations retain the judge-sensitive “Later versions (DETR)” phrase. |
| Simula co-designer, L44 p28 | Soft consensus selects bare-Simula bullets with conflicting collaborators and loses the required Simula 67 bridge. Several D/E/F combinations retain Simula 67 amid wrong or unsupported collaborators. A bridge hit is separate from recovering the complete co-designer relation. |
| Enkidu/Humbaba, L60 p46 | B often keeps Humbaba but drops the required Enkidu bridge. D-based pruning and pooled specificity can delete the only Enkidu-bearing bullet; some matched deletions keep it. Passing parents already mix unreliable Gogmagog/Goliath/Yaksha or other story details. |
| Add 3, then 9, L60 p62 | The reference is 2 → 5 → 14. Every reviewed anchor variant misses the intermediate 5. Some preserve final 14 inside wrong calculations; compatibility can keep only a final-result fragment. None of those changes recovers the computation. |
| Halve 20, then add 5, L20 p66 | The reference is 20 → 10 → 15. Selected fragments substitute other starts, operations or results. Shortening keeps instruction-like prose or another calculation, without recovering 10. |
| Waiter apologizes to customer, L20 p92 | The scene requires Marcus to apologize to Priya. Outputs remain broken summarization requests or unrelated people/actions. Compatibility and nonpositive-score abstention sometimes remove everything. Neither a generic instruction nor silence supplies the directed apology. |
| Comedian humiliates heckler, L60 p178 | A scathing comeback is more specific than calmly finishing a routine. Removing competing names or surrounding bullets can change the action extraction without introducing a new relation. Targeted and matched deletion can both pass. Descriptive roles are allowed, so missing a name alone is not failure. |

## Variants, controls and recurring effort

| Group | What was reviewed and how to interpret it |
|---|---|
| Exact B | N16, soft support and .125/.25 thresholds. No helper calls. Generic repeated bullets survive; sparse exact support and thresholds can erase useful content. |
| Semantic B v4 | Same N16 pool, support/compatibility variants. The original quote-format pipeline had 103 invalid responses and 36 exhausted logical calls. Its measured outputs are retained, but it is an instrumentation-limited result, not a clean test of consensus usefulness. |
| Repaired B v5, no reasoning | Fixed proposal candidates and strict local pair IDs, with support, compatibility and conservative-veto variants. The fresh 40-pair audit found five clear false merges among 13 accepted pairs; this was a selected qualitative audit, not a population error rate. Raw request/response mapping checks ruled out bookkeeping errors for those five. |
| Repaired B v5, medium reasoning | The same proposed pairs were confirmed again. Of 2,685 requested pairs, 2,639 were verified; 46 remain unknown after chunk validation loss. A separate fresh accepted-pair audit still found qualification loss and uncertain cases. Unverified compatibility stays unknown. Recurring deployment includes the proposal step as well as confirmation, even when this campaign reuses proposals. |
| Exact support plus D | N16 pooling with support bonuses 0/.05/.20 and a support-only control. The same bullet pool and caps apply. This adds numeric search rather than helper calls; repeated boilerplate is still a risk. Several anchor outputs are unchanged. |
| D, E or F parent plus pruning | N32 parents, .001/.005 sequential deletion thresholds and matched random deletion. No new helper calls for pruning itself. Parent sampling, encoding, controls or editing remain part of deployment cost. The threshold bounds each deletion, not total cumulative FVE loss. |
| D plus E, and further pruning | N32 pooled specificity, its .005 pruning/random controls, and the E-complete nonpositive-score abstention control. This adds matched activation scoring and numerical search. Empty outputs must be separated from successful factual recovery. |

These are whole-bullet consensus experiments. They do not establish failure of atomic-claim consensus. The separate claim-span instrument and unrun variants must retain their own status. None of these examples proves that the reconstructor's first 32 cleaned tokens per bullet capture every later qualification.

## Bounded supplements and judge sensitivity

The audit retains 34 selected supplements across 38 materially distinct variants: at most one apparent win and one regression for each frozen support/compatibility/veto/effort setting or combination/control, only when the shared anchors lack that category. There are 25 unique before/after text pairs. They were chosen by the recorded seeded ordering of changed outputs, not to estimate a prevalence. Public presentation remains capped at two previews per conceptual method; the full variant audit stays available.

Some supplements show concrete deletion. At greeting L60 p49, hard support removes the invented Li Na address and leaves generic help prose. At party L20 p123, hard support removes a flagged packing-list offer and keeps source-supported playlist help. Conversely, a chain supplement loses intermediate 5 after dropping a hit-bearing bullet from an already wrong derivation, and matched F deletion loses the sole Simula 67 bridge.

Other class changes require caution. D/F/E pruning and matched controls sometimes retain the Chinese courtesy sentence, Xiaofei question or invitation wording that was previously marked wrong. E pruning can newly flag a retained Sliding Window phrase. A support bonus can become consistent while keeping previously flagged identity assertions. In a chain supplement the correct 15 remains present, but the extractor changes its value ordering and the frozen endpoint fails. These are exact retained-evidence comparisons; they are not repeatability estimates or proof that a method corrected the assertion.

The official scores, source texts and semantic labels remain unchanged. The qualitative review supports investigating genuine detail removal and lost coverage, while preserving judge ambiguity, malformed-helper evidence and recurring inference cost. It does not name a winner from these examples.
