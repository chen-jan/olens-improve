# Experiment 071 — Task-only error bars in sampling overlays

## Key findings for a new reader

Presentation-only update: the four sampling overlays now draw confidence whiskers only for task performance. AR reconstruction keeps its curve, separate right axis, exact values and accessible interval text. No scientific result changed.

## Status and question

- **Status:** completed and published as public version 24, 2026-10-13 UTC.
- **Parent:** experiment 070; the user requested removal of AR error bars from the combined plots.
- **Question:** can the combined plot retain both trends while making task uncertainty easier to read?
- **Single change:** suppress AR whiskers in the combined view; darken task whiskers and enlarge their caps. Clarify the plot note and refresh asset URLs.
- **Expected failure mode:** accidental loss of AR values or confidence intervals, changed scientific inputs, or broken responsive rendering.
- **Decision rule:** all 48 point values remain source-exact; 24 task whiskers remain; no AR whiskers are drawn; four released-lens references remain visible; desktop, mobile and enlargement pass.

## Frozen inputs and procedure

Reuse the unchanged embedded full-bank data and model/evaluation contract from experiments 069–070 and the project plan. All 469 questions and 19,435 sites remain fixed. No generation, fitting, selection, judging or statistical recomputation occurred. Native task intervals remain grouped pointwise 95% intervals, distinct from paired-change intervals. AR intervals remain accessible in the point labels/tooltips; the separate AR-only view is unchanged.

Only `dashboard/sampling-overlay.js` and the main template's asset revision suffix changed. In hosted output, only `dist/sampling-overlay.js` and `dist/index.html` changed; 106 other assets and both embedded scientific payloads remained byte-identical. Historical pages and slides remain unchanged.

## Comparisons and measurements

Local browser checks confirmed all 48 source values, 24 task bars, zero unexpected bars, 24 accessible AR intervals and four original-reference blocks. Desktop (1440 px), mobile (390 px), enlargement and single-axis modes passed without page errors. Both screenshots were visually inspected. Native deployment succeeded; a separate public-browser navigation exceeded its 30-second load timeout, so hosted rendering was not verified.

## Completeness, cost and artifacts

- No new model calls, GPU work, Slurm jobs or paid evaluation.
- Preview and screenshots used the installed Chromium; no dependency installation.
- Browser receipts and screenshots: `output/playwright/task-error-bars-v1/`.
- Compact source/publication receipt: [task-error-bars-v1.json](../reviews/task-error-bars-v1.json).
- Published source commit: `6695b5d0950e407332bef330d2e2ff3870d718d2`.
- Research Git remains local; Sites publication uses its separate source repository.

## Inspection evidence and interpretation

This is a display change, so new scientific wins/regressions are not applicable. The combined plot retains independent vertical scales and explicitly warns that crossings do not imply equal values. Existing exploratory interpretation and limitations remain unchanged.

## Validation and test access ledger

| Timestamp | Data | Process | Outputs inspected | Purpose |
|---|---|---|---|---|
| 2026-10-13 UTC | Existing full-bank payload | Browser UI checks | Published aggregate values and intervals | Confirm unchanged evidence and task-only whiskers; no new research tuning |
