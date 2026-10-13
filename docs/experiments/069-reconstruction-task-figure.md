# Experiment 069 — Show reconstruction and task performance for the six methods

Presentation-only update, 2026-10-13 UTC (October 12 Eastern). The user chose to retain the existing sample budgets and requested a new figure beneath the six-method section of the current website.

Published as public version **22**. [Open the figure](https://olens-improve-research.jan618.chatgpt.site/#fit-quality). The [publication receipt](../reviews/reconstruction-quality-site-delivery-v1.json) records the exact source commit, saved version and deployment.

## Figure and evidence

Four interactive scatter plots pair each method's all-bank mean reconstruction with its native task rate. Right means more activation variance explained; up means better task performance, with the Hallucination (chat) axis reversed so lower contradiction rates are higher. The three other panels retain their original question-recovery endpoints. No cross-task average or new success metric is introduced.

The six condition IDs are unchanged: best-of-32, semantic consensus at 16 samples, best-of-32 pruning at 0.005, pooling at 32, two-round editing at 32, and pooling followed by pruning at 0.005. Numbered colors match across panels. Optional arrows connect each method's actual recorded parent to its result. They connect point estimates and are not significance tests. A method filter separates overlapping points; selecting one shows its exact reconstruction and task rate. Keyboard focus, existing details dialogs and enlarged charts remain available.

The original released Oracle Lens remains visible as a horizontal task-rate reference. Its full-prose reconstruction is unavailable and is not invented. A separate diamond represents the four-bullet original. The figure explicitly uses the full 469-question cohort regardless of the earlier cohort selector, because the reconstruction snapshot is all-bank. The 16-sample consensus and 32-sample settings are labeled rather than described as equal compute. These previously inspected results remain exploratory.

Horizontal and vertical bars copy existing grouped pointwise 95% intervals for the means/rates. They are neither a joint confidence region nor paired-change intervals. The figure retains distinct transcript-contradiction, required-name, first-ranked intermediate-number, and entity-role endpoints. Filtering may reduce information along with errors.

## Validation and delivery

- Browser checks passed at 1440px and 390px: all 24 plotted values exactly match the embedded frozen data; intervals, axis directions, original references and placement were verified.
- All seven filter states, legend selection, parent-arrow toggle, keyboard details and chart enlargement passed. Switching the earlier cohort selector leaves this explicitly all-bank figure unchanged. Mobile has no page overflow.
- Screenshots of the desktop, enlarged and mobile views were visually inspected. JavaScript syntax and whitespace checks passed.
- The existing source payloads and 104 other assets are byte-identical. Only the landing HTML and scoped stylesheet changed; one new JavaScript file was added. The archival script, existing results, slides and follow-up are preserved.
- No new inference, GPU work, judging, bootstrap or scientific recomputation.

Source files: `dashboard/overview.html`, `dashboard/expansion.css`, `dashboard/fit-quality.js`. The source-bound check receipt is [reconstruction-quality-figure-v1.json](../reviews/reconstruction-quality-figure-v1.json). Publication status is recorded in that receipt and the plan handoff.
