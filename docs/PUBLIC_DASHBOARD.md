# Public research dashboard

URL: https://olens-improve-research.jan618.chatgpt.site

Anyone with the link can visit. The first publication is a reviewed validation and development snapshot; held-out evaluation is still underway. Publication succeeded and an unauthenticated HTTP request returned the dashboard. No claim is made about the user's own browser session.

The second version, published at 13:42 UTC on October 10, adds a findings-first
overview with four task charts, uncertainty ranges, optional comparison views,
and expandable explanations. The full earlier dashboard remains at `details.html`.
Local desktop and 390-pixel mobile browser checks passed. An independent review
verified all 96 overview metric objects, eight chart files, and 29 local links;
the native service confirmed successful public deployment. The source-data
timestamp remains distinct from the publication time.

The dashboard's timestamp identifies its content snapshot. It is updated at research milestones, not connected directly to a live judge or database. All 12,978 numeric values in the public data were checked against the local report; all eight exported charts are byte-identical. An independent reviewer checked the exported files and links. Internal filesystem paths and job/process identifiers are removed; no credentials, model files, activation caches or private ledgers are published.

Regenerate the public copy with:

```bash
python scripts/build_public_dashboard.py --output .state/public-dashboard/dist
```

The isolated Site checkout and its hosting manifest are under `.state/public-dashboard`. Reuse the project ID recorded in `configs/public_dashboard.json`; obtain a fresh short-lived source credential through Sites and follow its source-packaging/save/deploy workflow. Pass credentials only through the helper's hidden standard input. Preserve public access. Record each successful version and deployment in the config. Do not create another Site or repurpose the main repository's Git remote.

This publication uses the dedicated Sites source repository. The research repository remains locally committed; the user handles GitHub pushes.

## All-method results update — 2026-10-10 14:35 UTC

Version 3 is published at the same public URL. It adds eight expandable approach sections, every recorded pilot variant (423 metric rows), four N1–32 quality curves with source confidence intervals, stage-specific charts and exact tables, paired differences, available costs and collapsed examples. Small-pilot, larger-development and validation evidence remain separate. Independent-reader checks show diagnostic status without an invented quality score; unavailable intervals remain explicitly unestimated.

Ten focused tests passed. Independent review corrected claims-per-output values that would otherwise have appeared as percentages and confirmed source warnings, units and missingness. Seven desktop/mobile views had no document overflow; all eight accordions and 55 stage/task selector choices worked. Root verified the full exported JSON is exactly the sanitized source, 29 local links/anchors resolve, and reviewed desktop/mobile screenshots. Native deployment succeeded; this is not a claim to have checked the user’s own browser.

The next qualitative update will add a small shared example panel and independently reviewed method-specific improvements/regressions. Existing examples remain visible; that expanded audit is not yet complete. Research GitHub pushing remains with the user.
