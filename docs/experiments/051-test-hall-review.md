# 051 — Held-out hallucination review

The held-out hallucination results do not establish a uniquely better explanation method. A32 and matched-control selection have similar judged error rates, and a frozen random complete response performs comparably. Pruning lowers the measured error rate substantially, but matched random deletion does as well or better while removing similar amounts of text.

This independent review covers the first retained example in every nonempty category of all 37 unique contrasts: 196 case references, 61 cells and 18 items. The exact source/context comparisons and manual assessments are in [test_hall_review_v1.json](../../configs/test_hall_review_v1.json). Every official verdict remains unchanged. The source is the complete signed TEST artifact at `${OLENS_DATA_ROOT}/runs/test-full-grid-comparison-v2/final-analysis-v2.json`, SHA256 `75dee255d88104450fa4424610178baa4df24964394be77812fa218379cfcef8`.

## The endpoint and paired comparisons

The original endpoint is the proportion of specific readouts with a wrong span. Its denominator includes hallucinated, consistent and off-topic readouts, and excludes generic or empty readouts. It is not question accuracy or the complement of explanation correctness. The 3,705 sites belong to 99 items/groups; paired 95% intervals resample these whole groups using 2,000 draws.

| Comparison | Change in error rate, percentage points | Paired 95% interval |
|---|---:|---:|
| Capped N1 → A16 | −0.09 | [−1.72, +1.52] |
| Capped N1 → A32 | −1.65 | [−3.33, −0.01] |
| Capped N1 → random complete N32 | −1.89 | [−3.79, −0.13] |
| Capped N1 → matched-control N32 | −1.59 | [−3.26, +0.12] |
| A32 → matched-control N32 | +0.05 | [−0.47, +0.58] |
| A32 matched deletion → A32 pruning | +1.96 | [+0.44, +3.50] |
| Matched-control matched deletion → matched-control pruning | +0.54 | [−0.90, +2.06] |

Lower error is better. These intervals are unadjusted across many contrasts and endpoints. They support reporting each comparison, rather than a statistically certified overall ranking.

Targeted pruning reduces average output length from about 102 tokens and four bullets to 59 tokens and 2.2 bullets. The retained true-claim tally falls from 6,931 to 4,578 for A32 pruning and 4,570 for matched-control pruning. Targeted pruning still produces specific readouts at 3,670/3,705 sites, so its lower error rate cannot be explained solely by empty/generic outputs leaving the denominator. The matched deletion controls nevertheless show that shortening alone can achieve the same error-rate benefit. Stage 2 receives stage 1's wrong spans as established false; its false-span tally is not an independent confirmation of those labels.

## What the fixed examples show

The JSON records exact pointers into the signed artifact. The following cases illustrate distinct mechanisms; their frequency in this fixed sample is not a population estimate.

| Case | Exact artifact reference | Manual assessment |
|---|---|---|
| Whitespace changes a class | Contrast 0, `wrong_to_consistent/0`; `chat-dailydialog-0034`, L60, p47 | The no-fiancé and helpful-assistant content is retained. A whitespace-only change flips the verdict without correcting substantive content. |
| An attribution survives a class change | Contrast 1, `wrong_to_offtopic/0`; `chat-lmsys-0011`, L60, p244 | The readout still names GRNs in a Decision Transformer context. The class change does not repair that mismatch. |
| A narrow transcription correction | Contrast 6, `wrong_to_consistent/0`; `chat-dailydialog-0003`, L52, p112 | A32 removes a mismatched heading while retaining compatible discussion of idiom ambiguity. This is a narrower gain than a fully corrected explanation. |
| Accepted extra attribution | Contrast 10, `wrong_to_consistent/0`; `chat-dailydialog-0000`, L44, p55 | Google changes to OpenAI, although the source names neither brand. The label improvement does not verify the new creator attribution. |
| A retained phrase becomes wrong | Contrast 20, `consistent_to_wrong/0`; `chat-dailydialog-0000`, L20, p38 | Pruning retains the parent's no-sleep/no-personal-life phrase. The new wrong flag lacks a clear contextual contradiction. |
| Partial error removal | Contrast 26, `wrong_to_consistent/0`; `chat-dailydialog-0000`, L20, p55 | Random deletion removes an invented London apartment but retains an unqualified partner statement. Acceptance does not establish complete correction. |
| Almost no explanation remains | Contrast 34, `wrong_to_consistent/0`; the same L20, p55 cell | A different deletion control leaves essentially “Here is how we handle it.” It receives a specific/consistent label despite little substantive content. |
| An error remains after shortening | Contrast 22, `unchanged/0`; `chat-lmsys-0001`, L52, p316 | Wrong chemical substitutions survive deletion of a bullet. Shortening leaves the contextual mismatch unresolved. |

All artifact references above start with `/paired_traces/{contrast}/families/hallucination/examples/`. Concrete company, address and architecture substitutions also occur in the fixed cases. Empty outputs remove those readouts through abstention and provide no corrected explanation.

## Limits and disclosure

The pinned judging instructions tolerate compatible extra detail, reformatting and broken fragments; absence alone is not wrongness. This explains why retained phrases and whitespace-only flips deserve separate treatment. Manual review compares exact text with its source and retained judge evidence; it neither replaces the judge nor certifies every claim's external truth.

The alphabetically first changed examples repeat items, especially the AI “better half” conversation. The 196 references are therefore illustrations of failure modes, not 196 independent observations. The original A16 and matched-control N32 operating points remain fixed, and this review introduces no new selection rule.

Before authorized final review, an operational observer inadvertently emitted two raw-N1 auxiliary fields between 21:29:11.640535 and 21:31:56 UTC on October 10. The original six methods and an early reporting proposal predated that exposure; no subsequent menu or tuning change was based on it. The disclosure receipt is `primary-six-completion-contracts-v2.json`, SHA256 `b0b69992c882e503ab8e016c2090d216b0c3d51491224a6fd5b7b7e4ef8b1758`.
