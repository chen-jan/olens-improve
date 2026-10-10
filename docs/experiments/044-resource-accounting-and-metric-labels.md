# 044: Resource accounting and clear metric labels

Status: reviewed interim accounting and public dashboard update complete. Final judging continues; this is not final campaign accounting or a final scientific result.

## Resource observations

The supported global ledger snapshot at 16:49 UTC records $18.12687471 in estimated usage, $4.900247625 in outstanding reservations, and $23.027122335 committed. Of the reservations, $4.848973125 is uncertain. All holds remain intact. These usage estimates are not reconciled invoices and exclude cluster charges and Codex/subagent billing.

At 16:43 UTC, project-owned storage was 93.732 GB logical: 69.584 GB fast and 24.148 GB durable. Allocated file blocks total 75.264 GB; neither reading establishes remaining lab quota. Reused base weights of 55.563 GB and the external environment are excluded. The project allowance remains 500 GB.

Four existing H200 holds plus two completed temporary H200 allocations account for 64.773 reserved GPU-hours during the project window through 16:49, including idle time. Hours before project start are excluded. GPU dollar pricing is unavailable.

A bounded metadata extraction verified all four frozen generation journals and 621,920 samples across 19,435 cells. Recorded generation timers sum to 23.40798 GPU task-hours, including the original sixteen instrument samples counted once. The main reconstructor tasks add 6.78402 hours, for **30.19200 measured GPU task-hours**. Generation timers include sampling and adjacent record assembly; AR timers include recorded loading and CPU overhead. These are not pure GPU utilization. Capture, loading outside those timers, abandoned uncommitted work, separate fixtures and CPU selection are not fully totaled. Shared generation is counted once, not once per method.

The immutable resource snapshot and measured addendum are bound by [the root review](../../configs/resource_accounting_review_v1.json). The addendum replaces the transferred generation-time estimate for the measured components, while preserving the original API/storage snapshot. Extraction inspected timing/count metadata only, without TEST quality, inference or new API calls.

## Clarifying the displayed percentages

The website now labels per-activation matches separately from questions with at least one matching readout. A bound validation example shows the released original role reader at 85/2,280 activations (3.73%) versus 15/20 questions (75%). The explanation is generated from the reviewed counts rather than hardcoded scores.

Hallucination remains an error rate over specific readouts in both views, with lower marked better. Its complement is not accuracy. Raw and capped originals are distinguished; the cap drops whole trailing bullets. Reconstruction fit is explicitly separate from accuracy, and paired rate changes are labeled percentage points. Cohort and related-group counts remain visible.

Thirteen overview and three map-export tests passed. Independent source review and desktop/mobile browser checks confirmed unchanged scientific data, exact endpoint switching, identical hallucination rates in both views and no horizontal overflow. All 16 descriptive map downloads remain present. The 36 reviewed public files were published as Site version 6 at 17:04 UTC; native deployment succeeded. Browser QA was local, not a claim about the user's own browser session.

Publication identity and source receipts are in [public_dashboard.json](../../configs/public_dashboard.json). The dedicated Sites source was pushed by the hosting helper; the research repository remains local for the user to push.

## Next step

Keep final TEST results unopened until all required judging finishes. Refresh campaign accounting after remaining judging and final reporting, retaining uncertain reservations and the distinction between measured task time, reserved time and monetary cost.
