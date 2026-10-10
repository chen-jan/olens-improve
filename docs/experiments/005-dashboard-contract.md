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
