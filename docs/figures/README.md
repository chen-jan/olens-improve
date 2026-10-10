# Standalone comparison figures

`scripts/export_signed_figures.py` exports PNG and PDF figures from an immutable analysis and the same explicit root-review metadata used by the dashboard adapter. It checks the reviewed stage capability before reading outcome bytes, then checks exact artifact/cohort/menu/selection/gate/freeze identities. TEST requires explicit reveal authorization. There is no new aggregation, interval calculation, operating-point choice or winner selection.

```bash
MPLCONFIGDIR=/tmp/olens-improve-matplotlib /path/to/project/python \
  scripts/export_signed_figures.py \
  --analysis /path/to/immutable-analysis.json \
  --review /path/to/root-reviewed-metadata.json \
  --expected-sha256 EXACT_REVIEWED_SHA256 \
  --output /path/to/new-figure-directory --cross-task
```

Use an allocated CPU step if figure production or checking grows beyond a small local task. Large output collections belong outside the repository; an existing export directory is never overwritten. Matplotlib is already available in the current runtime. Cache files stay off HOME.

`family-cell-rates.{png,pdf}` contains four separate task-family panels, ordered exactly as the reviewed menu. Dots show the supplied rates; bars show supplied per-method 95% intervals; labels retain numerator/denominator counts. Hallucination is contradicted among specific readouts, so lower is better; the other axes describe bridge mentions, number recovery and role-task passes over intended cells, so higher is better. These scores do not establish complete faithful explanations. Undefined rates show “Unknown”; missing intervals are omitted, not replaced with zero-width certainty. Original-item endpoints remain separate in the report and are not substituted into this cell figure.

The optional `cross-task-error-recovery.{png,pdf}` uses the hallucination contradiction rate against each recovery family separately. Its axes use different item cohorts. It is not same-item precision/recall, a joint confidence region, a cross-family macro, or evidence of statistical dominance. Both axes display source-supplied marginal intervals; no frontier or automatic winner is computed. Undefined rates are omitted and retained in provenance.

`provenance.json` records full source/review hashes, stage identities, exact method order and visible labels, family counts, every plotted metric and warning, axis definitions, Matplotlib version and output-file hashes. Short figure labels and line-aware spacing keep twelve-method comparisons readable; exact condition IDs remain in provenance. It contains no raw traces or candidate text. Costs are deliberately separate: these figures imply neither GPU dollars nor fresh-input latency. Source warnings and few-group limitations remain in provenance and the associated report.

Until root supplies and reviews a complete held-out analysis, verification uses only synthetic fixtures. Visual checks of exported PDF/PNG layout are engineering checks, not validation quality evidence or publication.

The synthetic twelve-method layout was checked in both PNGs and independently rasterized one-page PDFs on 2026-10-10, with no overlapping method labels or clipped legends. Four focused synthetic tests cover authorization before outcome access, exact supplied metrics and provenance, undefined rates, and long-label spacing. PDFium 5.14.0 was installed only under `/tmp/olens-figure-pdf-render` for this inspection; it is not a runtime dependency of the exporter. The temporary review assets are under `/tmp/olens-signed-figure-layout-v3/figures`, and their provenance identifies the source as a synthetic layout fixture.
