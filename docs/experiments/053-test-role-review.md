# Independent TEST role review

The completed TEST role results do not establish a clear question-level improvement. Every supplied paired question-level 95% interval across the 37 fixed contrasts includes zero. Several cell-level changes are measurable, but selected examples show preserved direction under changing judge interpretations, contradictory choice/rationale evidence, and correct abstract roles alongside invented details. Official scores remain unchanged.

The reviewed artifact is `${OLENS_DATA_ROOT}/runs/test-full-grid-comparison-v2/final-analysis-v2.json`, SHA `75dee255d88104450fa4424610178baa4df24964394be77812fa218379cfcef8`. The complete review annotations are [test_role_review_v1.json](../../configs/test_role_review_v1.json), SHA `c89819b6cc652a63af7a28e34cfe0e11d690ed73f64dee4109ad690b204b9667`. The artifact was opened only after root authorized review of the complete TEST analysis.

## Question criterion and paired uncertainty

A cell passes when the judge answers all three agent/action/patient multiple-choice questions correctly. An original item passes if **any** of its 114 sites and layers passes. TEST contains 50 role items, 25 related groups and 5,700 cells. The intervals below come directly from the report's 2,000 paired whole-group draws; this review computes no new intervals. Names or role descriptions are permitted by the judge prompt, so absent names alone are insufficient grounds for rejecting abstract role recovery.

| Fixed method | Passing items / 50 | Passing cells / 5,700 | Mean output tokens |
| --- | ---: | ---: | ---: |
| Original single sample | 40 | 256 | 97.85 |
| Capped single sample | 40 | 254 | 96.90 |
| Best reconstruction of 16 | 40 | 253 | 97.81 |
| Best reconstruction of 32 | 38 | 234 | 97.84 |
| Frozen random sample control | 39 | 244 | 96.99 |
| Specificity-adjusted best of 32 | 38 | 234 | 97.26 |
| Pool bullets from 16 | 41 | 244 | 103.08 |
| Pool bullets from 32 | 41 | 269 | 103.89 |
| Specificity selection then pruning | 39 | 217 | 49.96 |
| Matched deletion after specificity selection | 38 | 224 | 47.99 |
| Prune best reconstruction of 32 | 39 | 215 | 50.84 |
| Matched deletion after best reconstruction of 32 | 42 | 216 | 49.04 |

These token means describe saved outputs, not fresh inference latency. Cell rates and question rates use different units; sparse passing cells can produce a high item rate through the any-site criterion. Forty passing items therefore do not establish forty complete, faithful explanations. No uniform-guessing floor is asserted.

The question-level difference for best of 32 versus capped single sample is −4 percentage points, with paired interval [−12, +4]. Pooling 32 versus capped single sample is +2 points [−6, +10]; versus best of 32 it is +6 [−2, +14]. Specificity selection versus best of 32 is 0 [−6, +6]. Increasing best-of-N from 16 to 32 changes the question rate by −4 [−10, 0], providing no evidence here that larger N improves role-question recovery.

Pooling 32 does increase **cell** task passes over best of 32 by 35/5,700, or +0.614 points [+0.211, +1.035]. Its cell difference against capped single sample is +0.263 [−0.211, +0.702]. This distinction prevents a same-budget cell diagnostic from becoming a claim of question-level or whole-output superiority.

Specificity pruning versus its matched deletion control changes the question rate by +2 [−4, +8]; best-of-32 pruning versus its matched deletion control changes it by −6 [−12, 0]. Their cell differences are respectively −0.123 [−0.491, +0.228] and −0.018 [−0.421, +0.386]. Neither establishes an advantage of the pruning criterion over deletion at matched output lengths. Both pruning and matched deletion lower cell recovery relative to the capped single-sample baseline.

These are pointwise intervals over a fixed cohort, not multiplicity-adjusted tests or proof of equivalence. The exact per-method intervals, all 37 cell and question paired rows, and lengths are preserved in the review JSON.

## Fixed initial trace review

Following [FINAL_SCIENTIFIC_REVIEW_HANDOFF](../FINAL_SCIENTIFIC_REVIEW_HANDOFF.md), the reviewer checked example index 0 in each nonempty win, regression and unchanged category for every unique exact contrast. All 37 contrasts have all three categories: **111 reviewed examples**, covering 43 cells, six items and five related groups. Deduplicating repeated evidence required reading 119 distinct text/choice/rationale units. The exact multiple-choice context and original stimulus were checked for each represented item. Source bank SHA is `ac3886011daa51c6b0967ba416b4db8c16eefd60f6b32e98d076771d46ab8541`.

The fixed sorted changed-case sampler concentrates many examples on the accountant/client pair. These cases are illustrative changes rather than estimates of failure prevalence, and they do not by themselves identify which questions changed their any-site status. “Unchanged” means unchanged task pass; the text can still change substantially.

| Source trace | Observed explanation difference | Review qualification |
| --- | --- | --- |
| Contrast 1, win 0: teacher/parent, L60 p116; raw → capped | One extra space before “confrontation” is removed. Both outputs describe a parent accusing a teacher over grades; the chosen action changes from scolded to blamed. | The official gain is a judge-sensitive action distinction, not recovered direction. The inverse contrast records the opposite change. |
| Contrast 0, win 0: doctor/patient, L52 p145; capped → raw | An additional raw bullet repeats bedside reassurance; doctor-to-patient comfort already appears in the capped text. | Capped evidence rejects missing names; raw evidence accepts descriptions. Invented names and a woman patient remain, despite the male patient in the source. Abstract role recovery and full source truth differ. |
| Contrast 9, win 0: accountant/client, L60 p141; best of 32 → random | Both outputs retain Marcus and invent client names; the proposed rationale says its Maya/Lena targets cannot be identified from the options. | Recorded proposed patient choice is nevertheless the gold client option and the official result passes. Preserve that result and flag the choice/rationale conflict. |
| Contrast 16, win 0: accountant/client, L36 p134; raw → pool 32 | The pooled text introduces Marcus into mixed fraud/mechanic scenes with Sarah and Elena. | The rationale explicitly gives patient cannot-tell option 6; recorded choice is gold option 2. The official gain does not verify a complete directed relation. The same proposed text recurs in contrasts 17–19. |
| Contrast 12, win 0: accountant/client, L52 p146; best of 32 → specificity | One proposed bullet says Meredith deceived her tax preparer; subsequent bullets put accountant Marco deceiving Laura. | A full pass coexists with conflicting direction and invented names. Majority role cues do not make all bullets consistent. |
| Contrast 23, regression 0: accountant/client, L52 p144; specificity → pruning | Two retained bullets still say an accountant kept refund money and falsely claimed to send it all. | The judge now rejects the deception action despite that explicit false claim. This loss is interpretation-sensitive, rather than a demonstrated deletion of the abstract relation. |
| Contrast 20, regression 0: accountant/client, L20 p134; raw → specificity pruning | Deletion removes secret-commission and unaware-customer cues, leaving generic trust/accountant summarization requests. | This is a plausible loss of relational signal. The original full pass itself rests on prompt fragments, rather than a complete source-faithful narrative. |
| Contrast 25, win 0: client/accountant, L52 p132; best-of-32 pruning → specificity pruning | The proposal more clearly states that a client exploited his accountant. | It also calls the accountant complicit and invents cheating preparation fees, conflicting with the source's unwitting accountant. The correct abstract direction coexists with unsupported details. |

The JSON includes a brief before/after assessment and exact artifact pointer for **every** mandated example, with text and context hashes, gold/returned choices, official pass flags and source relation. It preserves unambiguous cue losses, partial relation recovery, ambiguous action changes, and judge-evidence conflicts separately. No corrected score dataset or prevalence estimate was created.

## Boundaries

No additional inference, API calls, rejudging, method selection, tuning, ledger mutation or scientific source edits were performed. Root retains responsibility for final synthesis and operating-point claims. The earlier incidental raw-N1 hallucination auxiliary-field exposure remains disclosed in the handoff; it was not used in this role review. The whole-469 union remains a separate descriptive appendix.
