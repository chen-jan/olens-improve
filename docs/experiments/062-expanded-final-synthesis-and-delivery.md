# Experiment 062 — Complete four-bank synthesis and delivery

## Key findings

All 70 frozen settings now have all four complete benchmark grids. Reconstruction fit improves with sampling and pooling, but recovery is task-dependent and nonmonotonic. Pruning exchanges some needed information for fewer contradictions. Editing adds little beyond its pooled parent. See [the final report](../EXPANDED_REPORT.md) and [delivery links](../DELIVERY.md).

## Status and question

- Status: completed; public version 17 published on 2026-10-11 at 07:10:16 UTC.
- Parent/run: expanded-all-four-banks-v1; manifest `753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8`.
- Question: does inference-time sampling, selection, filtering or editing improve the released frozen lens on the four agreed full banks?
- Decision: retain task-specific promising options; no universal winner or automatic promotion from reconstruction fit alone.

## Frozen inputs and measurements

The checkpoint, model, whitening, original activation sites, 32-sample shared pool, output caps and Luna evaluation instrument remain unchanged. The 469 questions contain 19,435 sites. All 280 condition/task units passed strict final validation after three missing records were repaired with the same instrument, as recorded in experiment 061. No new lens samples were generated for the expansion.

Final native results: `durable/expansion-v1/analysis/final-v1.json`, SHA `e2773e297d7724f20d656ecf07c5de00097604d8a85c516938a565626b07876e`. Final reconstruction: `durable/expansion-v1/reconstruction/final-v1.json`, SHA `0c3f99db532641326d4d432a9587d9ee10d9ea978fe16f9c74c9d96740965ba8`. Final effort: `durable/expansion-v1/analysis/effort-final-v1/effort.json`, SHA `bb2a14bfbac15d3d76ae9936376c4343d422253f1904d74bcb4717932351121f`.

Grouped paired uncertainty uses the existing 10,000 resamples and frozen 496-contrast menu. Related questions remain grouped. Full-bank results are exploratory; the original frozen-test results remain separate. Reconstruction comparisons use their recorded common valid masks, and are secondary diagnostics outside the joint quality adjustment.

## Qualitative inspection and interpretation

Four reviewers read all 244 fresh final comparison pairs and their full contexts, official evidence and question-grid witnesses. The final merged bundle covers 475 new condition/case references, including 44 inherited exact-evidence references. Earlier reviewed cases remain unchanged. The delivered dashboard preserves 1,771 prior entries and adds 435 distinct entries, totaling 2,206 display entries; entries and unique references are different units.

Audits identify first-ranked integer sensitivity, correct tokens inside false arithmetic, deletion of required names with tiny fit loss, imperfect relation judgments and pooled-parent gains inherited by editors. Selected examples are illustrative rather than prevalence or causal estimates. Full-bank selected-editor lineage shows 445 final text changes versus pooling; all 40 entries in the retained editing example panel kept the pooled parent, which is explicitly a bounded sampled-panel observation.

## Delivery and checks

Final source-bound dashboard: `durable/expansion-v1/dashboard/final-v3`. Deck: `durable/expansion-v1/presentation/final-v3`, 86 slides, 26 main slides. Root reviewed 28 task-specific notes and seven exact method examples. Independent checks found and corrected absolute-fit units, control-activation wording, the matched-random-deletion caveat, three overflowing labels, and tiny fit changes that would otherwise round to zero. A human-note export field mismatch was corrected without modifying reviewed observations; ten relevant assembly tests passed.

The dashboard passed actual 14-view browser checks. The slide HTML/PDF passed all-page layout and dimension checks, with selected pages visually reviewed. Native PowerPoint rendering is unverified. Deployment and public selected-asset readback are recorded separately from local checks.

Final accounting is in [the terminal supplement](../reviews/expanded-terminal-resource-supplement-v1.json). API usage is estimated at $142.73 overall/$106.22 expansion; unknown and reserved holds remain $5.07. Expansion allocation: 5.825 H200-hours and 225.662 host CPU core-hours. Scoped storage: about 123.07 GB logical, excluding reused external weights. All four owned expansion allocations are terminal; unrelated user jobs were preserved.

Independent readers, new benchmark families, new layers/positions, training and sampling above 32 remain outside this completed expansion. Research Git stays local. No further paid inference is queued.
