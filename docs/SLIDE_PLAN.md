# Final presentation plan

Prepared 2026-10-10. **The comprehensive DEV/VAL deck is a draft; final TEST quality remains pending.** Validation, all six development sampling prefixes and the separate synthetic-input timing fixture are complete. Check [STATUS](STATUS.md) for final judging and review status before filling held-out slides. This document neither opens a cohort nor changes the frozen menu. The final deliverables are an editable deck, a PDF, detailed speaker notes and a source manifest.

## Story and visual style

Lead with what the final evidence supports, then explain how we tested it. Do not promise a single winner: the current validation evidence supports two experimental choices, Best of 16 and comparison against other activations. Final wording waits for the twelve-method held-out comparison: the original six primary choices and six prospectively added secondary comparisons. Separate measured results, plausible explanations and unresolved questions.

Use 16:9 slides, the public overview's pale background, navy text, blue sample selection and teal comparison against other activations. Keep method colors consistent across slides. Use large plain-language claim titles, one principal graphic per slide, and usually fewer than 40 visible words beyond chart labels. Titles can report an inconclusive result. Definitions, detailed counts, technical settings and source references belong in notes or the appendix. Avoid decorative imagery, dense tables and unexplained abbreviations.

Use editable text, diagrams and chart marks wherever practical. Exact rates, counts and intervals come from reviewed artifacts; plotting changes their geometry, never their values. Label every figure with its cohort, outcome, direction, denominator and uncertainty. Keep the four tasks separate. Recovering a name or number is not proof of a correct explanation. Show missing measurements explicitly.

## Core storyboard: 16 slides

These are working subjects, not predetermined final claims. Shorten to 14 slides by combining 3 with 4 and 14 with 15 if readability improves.

| Slide | Main message or question | Main visual and evidence |
|---|---|---|
| 1. Findings first | What improved, what failed, and what remains uncertain? | Three concise final takeaways, each tied to a reviewed result. Title names the study and frozen model; no separate ceremonial title slide. |
| 2. The final comparison | How do the frozen choices perform? | Four separately labeled task panels; original six primary methods first, six secondary comparisons in a clearly labeled continuation or appendix. Exact counts and supplied intervals; lower contradiction rate versus higher recovery rates. TEST only. |
| 3. What is a readout? | One internal vector can yield several descriptions. | A simple model → one marked layer/position → candidate descriptions diagram. Explain that the model and readers remain fixed. |
| 4. How we choose text | Sampling, selecting, combining and deleting are different operations. | Small visual examples of complete-sample selection, bullet pooling and bullet removal. No new samples per method; one shared pool of at most 32. |
| 5. How we kept the comparison fair | We chose settings before seeing final quality. | Development → validation → frozen TEST timeline; the original six primary plus six secondary methods were fixed before TEST judging. Shared vectors/pools and paired related groups; actual item/site counts from manifests. |
| 6. Transcript contradictions | Did apparent improvement preserve useful assertions? | Final error rates plus assertion and off-topic coverage. Add one paired transcript example with unchanged official verdicts. |
| 7. Multi-hop facts | Finding the missing name can help without fixing the story. | Final name-recovery comparison and one reviewed win or regression; distinguish exact required-name recovery from explanation accuracy. |
| 8. Arithmetic steps | A correct number can appear in a wrong calculation. | Final intermediate-number recovery and a paired text example with the judge's extracted value and reasoning. |
| 9. Who did what | Names and roles do not always preserve direction. | Final role passes and a compact actor → action → recipient example. Explain the official name/description allowances and any judge-sensitive cases. |
| 10. Does more sampling help? | More candidates improve fit; quality may behave differently. | Complete development N1/2/4/8/16/32 curves, separately by task, with actual coverage and uncertainty. These are persisted-pool prefixes, not new capped generation runs. |
| 11. What happened to the other ideas? | Agreement, editing and another reader have specific limits. | Plain visual explanations and evidence/status for consensus, editing and independent checks. Show an audited false merge or ambiguous extracted fragment without claiming all consensus is futile. |
| 12. Do combinations earn their extra steps? | Compare each added component with its parent and a fair control. | Completed TEST12 paired component-on/off results for comparison against other activations and pruning, including matched-count random deletion; validation comparison separately labeled. Small development panels for support + pooling and pooled specificity; keep cohorts separate. |
| 13. Why the score can mislead | Matching an activation is not factual verification. | Controlled number/entity/direction substitutions and the 32-token phrase limit. Pair score behavior with selected text; qualify small diagnostic samples and numerical sensitivity. |
| 14. What does it cost? | New inputs and cached replay are different workloads. | Measured generation, encoding, selection and helper costs; chosen-profile timing if completed. Distinguish initialization, warm work and replay. Unknown GPU dollar cost remains unknown. |
| 15. What should a user try? | Present the final operating choices and their limits. | A compact choice guide using final evidence, plus vector → sample pool → selection → saved cache → replay. No general faithfulness guarantee or mandatory runtime judge. |
| 16. What should we remember? | State the practical conclusion and remaining failure modes. | Three final lessons, limitations and links to the report, public dashboard, editable deck and reproducibility instructions. If final evidence is inconclusive, say so. |

## Appendix and speaker notes

The appendix supplies comprehensive evidence without making the main story unreadable. Include only measured comparisons; never manufacture a quality endpoint for a diagnostic-only approach.

- Separate development, validation and final TEST tables/plots with cell and whole-item endpoints, group counts and intervals. Include all twelve validation and final TEST methods, labeling the original six primary and six secondary final comparisons. Explain whole-item recovery as a pass at any preselected site.
- Full development sampling curves and same-pool random controls; parser/cap eligibility and unavailable-score exclusions. Preserve the raw released single sample and deterministic capped comparator as separate methods.
- Consensus exact/semantic/medium variants and coverage; extracted-claim audit failure and the uncompleted 32-cell expansion. Keep failed self-containedness distinct from demonstrated newly introduced falsehood.
- Pruning thresholds, coefficient diagnostics where measured, pooling budgets, parent/component-off comparisons and matched-count random deletion. Show the measured combinations, not an exhaustive cross-product that never ran.
- Matched-control mean versus max, likelihood and fluency/control-likelihood baselines, wrong-activation donors, controlled near misses and available-candidate quality diagnostics. Mark unrun or incomplete quality measurements.
- Editing round 1/2, unchanged parents, helper/new-vector work and provenance/meaning risks. Independent J++ token diagnostics remain diagnostic; unresolved fitting-data overlap precludes clean held-out claims. Optional NLA layer 42 and second compatible reconstructor were not final comparisons.
- Length/coverage, true/unverifiable/false tallies, source-span versus claim segmentation, numerical batch sensitivity, layer/position coverage, fixed model/read grids and score formula. Never combine differently segmented tallies into invented claim precision.
- Full cost/timing/accounting table, retained uncertain charges and implementation/source revisions. Separate runtime helper cost, benchmark judging and campaign cache hits.

Each slide's notes contain its exact source artifact/hash, condition IDs, endpoint definition, counts, interval convention, interpretation and limitations. Example notes preserve target/source IDs and exact judge evidence. Public files omit private paths, job/process identifiers and credentials; keep a separate local manifest for full reproduction. Add a plain Markdown notes companion so PDF readers can access the detail.

## Available tools and proposed build

At planning time, read-only package inspection found **matplotlib 3.11.1, Pillow 12.3.0 and Chromium** available. The model runtime lacked `python-pptx`, `lxml`, `XlsxWriter`, ReportLab and a native office/PDF inspection toolchain: no LibreOffice, Poppler or Pandoc was resolved. Node could not resolve PptxGenJS or artifact-tool from this checkout. Native Google Slides creation/edit/export connector tools are available; none were invoked for this plan. The later isolated style-proof environment is recorded below.

Recommended local route: after final results, create a small isolated presentation environment off HOME with pinned `python-pptx` dependencies, preserving the model runtime and installed research wheels. It supports [editable charts](https://python-pptx.readthedocs.io/en/latest/user/charts.html) and [speaker notes](https://python-pptx.readthedocs.io/en/latest/user/notes.html). Author simple diagrams and point/interval plots as editable PowerPoint shapes; embed complex retained plots only where native marks are impractical. Supply chart data alongside any image.

Use one versioned slide-content/geometry JSON to build PPTX and a local HTML mirror. Existing Chromium can print the mirror to PDF and capture slide previews on allocated CPU. This gives a feasible local PDF path, but **does not establish that PowerPoint renders the PPTX identically**. Validate PPTX contents/notes/embedded data and inspect the deck through an available native renderer before claiming visual parity. A native Google Slides import/thumbnail/export check is a possible later route; connector availability is not a tested export. If local dependencies or faithful PPTX rendering become the bottleneck, build native Google Slides through the available connector and export editable PowerPoint plus PDF from the same deck, retaining source data and checking every exported slide. Root chooses that delivery route; do not add a large framework.

## Build and review sequence

1. Finish final signed analysis and independent traces; root reviews final findings. Bind the exact TEST menu, final artifact, reviewed DEV/VAL summaries, cost receipts and timing status. No slide build can change settings or outcomes.
2. Assemble a compact presentation data file from those validated sources. Every figure/claim maps to a source and endpoint. Reuse [signed figure export](../scripts/export_signed_figures.py), existing grouped intervals and [delivery checklist](DELIVERY_CHECKLIST.md); do not rerun inference or judge for slides.
3. Build editable slides, notes, HTML mirror and PDF in a new versioned artifact directory off HOME. Retain build/dependency versions, source hashes and output hashes. Do not overwrite older exports.
4. Check all values/counts/intervals against source data; verify every method/split label, unfinished measurement, legend, example and citation. Inspect every slide at presentation size, plus a contact sheet, for overflow, tiny labels, cropped intervals and unreadable appendix plots. Verify PPTX notes and editable objects separately from HTML/PDF rendering.
5. Root reviews the final findings/visuals and public-file sanitization, then links the deck/PDF/notes from the report and dashboard. Record local, committed and published state separately. A local preview is not public delivery.

The next step is to review the comprehensive DEV/VAL draft, then fill held-out conclusions only from the final reviewed analysis. Final delivery remains incomplete.

Implementation checkpoint: [the four-slide draft proof](../dashboard/slides/README.md) now supplies editable PowerPoint objects/notes, exact source-bound validation plots and a local HTML/PDF mirror. Its isolated dependencies live off HOME and preserve the model runtime. Native PPTX rendering remains unvalidated; no final deck or TEST quality slide has been produced.

Comprehensive draft checkpoint: [build_final_slides.py](../scripts/build_final_slides.py) preserves that proof and prepares 16 core slides plus a paginated all-method appendix. The editable source is [final-draft-dev-val-v6.json](../dashboard/slides/final-draft-dev-val-v6.json), bound to reviewed dashboard bytes, complete development curves and validation results. The appendix retains every available quality row and auxiliary endpoint, explicit method coverage, fixed shared examples and complete exact notes. Counts per output remain counts, not percentages. TEST slides are empty pending reviewed results. A separate HTML/PDF mirror is feasible; no native PowerPoint renderer was found in the bounded local/shared binary check, so native visual fidelity is still unvalidated.
