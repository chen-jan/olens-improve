# Local result dashboard

`scripts/build_dashboard.py --report REPORT.json --output LOCAL.html` builds a
standalone local HTML report. It makes no API calls and publishes nothing. The
input is a compact immutable report assembled from reviewed result artifacts;
the report itself should be retained with the HTML.

Top-level fields are `title`, `updated_utc`, `cohort`, `run_ids`, `provenance`,
`reviewed_findings`, `progress`, `api`, `methods`, and `endpoint_notes`.
`provenance` records `scope`, `split_manifest_sha256`, `cohort_manifest_sha256`,
`source_commit`, and the source `artifact_sha256`. Reviewed findings have
`claim`, `detail`, `evidence`, and `reviewed_by`; use three to five findings, or
leave the list empty until scientific findings have been reviewed.

Method keys are `sample_selection`, `consensus`, `pruning`, `pooling`,
`contrastive_checks`, `editing`, `independent_checks`, and `combinations`.
Each may provide `hypothesis`, `status`, `findings`, `metrics`, `scaling`,
`traces`, `limits`, and `next_action`. A metric records `family`, `cohort`,
`condition`, `endpoint`, `scope`, `value`, `numerator`, `denominator`,
`eligible_count`, `missing_count`, and `uncertainty` or `ci`. Missing values
are null and displayed as unmeasured. Scaling series have explicit endpoint
labels and cohorts, with frozen nested N=1/2/4/8/16/32 points; never mix units
or cohorts on a curve. Numeric point `ci=[lower,upper]` draws a CI whisker;
otherwise uncertainty remains stated in the table. `cost_frontier` series
use `label`, `cohort`, `cost_unit` (USD or GPU seconds), and measured points
with `condition`, `cost`, `value`, optional `ci`, and `count`. No fitted
frontier is inferred. Paired traces record the original `cell_id`, verbatim
`baseline` and `selected`, `kind`, `evidence`, and `interpretation`.

Partial layer/position pilots use scope `cell_pilot`. They cannot set
`official_full_grid`; that flag requires `scope=full_grid` and
`complete_grid=true` for the original complete benchmark grid. Any nested
record marked `split=test` or `cohort=test` requires the top-level
`test_reveal_authorized=true` flag from the frozen planned reveal. Reconstruction
FVE and generated-string counts are progress/diagnostic endpoints, not semantic
accuracy. The builder escapes source strings and embeds only local report data.

Initial report `dashboard/report.json` uses root-reviewed findings and the
immutable pilot snapshot plus isolated contrastive diagnostics. Initial HTML
`dashboard/index.html` was checked locally with cached Chromium/Playwright,
including desktop and 390 px mobile screenshots, method-tab clicks and keyboard
navigation, one visible panel, and no horizontal mobile overflow. The page
had no console errors after a local favicon fix. This confirms local browser
rendering only; the artifact has not been hosted or published.

## Held-out comparison display preparation

At 09:58 UTC, the completed-comparison adapter and renderer passed 28 focused
offline checks and a synthetic browser check. No real validation or test
verdicts were used. The adapter binds the reviewed result, cohort, ordered method
list, selected texts, analysis gate and freeze; it preserves source intervals,
paired component comparisons, output lengths and explicitly reviewed traces.
The browser showed 16 source-derived paired charts in the synthetic fixture,
with no console errors. At a 390 px viewport, expanding every detail initially
caused long provenance strings to widen the document to 608 px. Paragraph
wrapping fixed this; the repeated check measured exactly 390 px.

Optional cost rows distinguish new-input work, shared campaign work, cached
replay and benchmark judging. Values are measured, estimated, specified
algorithmic workloads, or explicitly missing. Nonmissing quantities reference
exact source files, hashes and fields; the attachment checks source byte hashes
after the comparison's authorization and identity checks. Field interpretation
and estimate arithmetic still require coordinator review. The display computes
no combined cost or end-to-end latency. Actual comparison costs remain to be
attached after measurement and review.

The local synthetic browser evidence is under
`fast/diagnostics/signed-dashboard-browser-v2/`, including `render.json`, desktop,
paired-chart, cost and mobile captures. Its HTML SHA-256 is
`bbb9e4d3c7bb0043e10a85ab075717178141850d2a10874799da3a82d2e21a2b`.
These invented fixture values are display tests, not research results. The
production dashboard and held-out artifacts were unchanged by this check.

## Reproducible result aggregation

`scripts/summarize_results.py` reads the frozen cohort and declared arms without
any judge/API calls. `configs/reporting_pilot_v1.json` records the initial 22 arms
from the Standard repair root and the three E3 arms from their original root.
Every override explicitly declares its own condition root and selection hash;
all arms must still match the same frozen cohort hash, cells and group identities.
The compact JSON records individual input hashes and refuses a comparison when a
terminal family summary, submitted readout or required stage 1/2 outcome is missing.
Files must remain byte-identical throughout aggregation. An upstream partial-grid
`complete=false` is preserved and is not mistaken for an API failure.

Cell count pairs are summed by item, then `paired_group_interval` resamples whole
related groups with 2,000 shared draws. Absolute intervals use the same group
scheme. There are only 2 chain groups, 4 role groups, 7 bridge groups and 8 dialogue
groups in this pilot; especially the two-group chain interval cannot establish
robustness. The full hallucinated classification is used for the frozen headline;
revocation adjustment is a distinct endpoint. Empty outputs are explicit
abstentions, while API failures remain missing. False spans and true/unverifiable
claims have different segmentation and are never labeled atomic precision.

`scripts/populate_dashboard.py` attaches these measurements to reviewed prose and
examples, preserving their editorial content. New conditions with another cohort
require a separate report; they cannot silently enter this paired comparison.
The table in experiment 009 is generated from the same compact measurement JSON.
The HTML remains local. Cost charts require an explicit campaign, incremental
cache or deployment scope plus a definition. A cache-only selector timing cannot
be displayed as complete inference cost; GPU dollars remain unknown.
# Compact cost summary, 2026-10-10

The signed comparison now starts its cost section with one row per method:
sampled responses, maximum phrases to encode, helper calls, total new-input
timing status, and selection time from saved vectors. It uses supplied values
only and keeps their measured/estimated/specified/missing status. Full component
measurements, limits and source evidence remain expandable. Shared campaign
work and benchmark judging stay separate. Missing or ambiguous supplied fields
remain unknown; no latency totals or GPU-dollar estimates are invented.

Twenty-nine focused dashboard checks passed after the structural change; the
thirteen signed-dashboard checks passed again after simplifying the labels.
A synthetic three-method page passed cached-Chromium desktop/mobile inspection
at 10:55:06 UTC: three summary rows, new-input details initially collapsed,
no page errors, and no page overflow at 390 pixels after expanding all details.
Artifacts are under `fast/diagnostics/signed-dashboard-browser-v3/` (the project
fast-storage root, not a repository symlink). This was a local synthetic layout
check; production results were not changed or published. Actual reviewed
validation/test pages still require their later browser check.
