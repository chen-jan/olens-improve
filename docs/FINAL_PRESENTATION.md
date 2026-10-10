# Final public packaging handoff

No actual TEST outcome data was read to implement or test this extension. No public build or publication was performed.

Stable files:

- `scripts/build_public_dashboard.py`: `76ffbb19e5116340c5d4ba343559cf8a49887f2d7e86fe67610f732f0e0894a7`
- `tests/test_public_final_delivery.py`: `0a9f9954e7808f631c03d52302dbdd5e8f723d8791edc370f223da462255712c`

Eight new synthetic tests pass, plus three existing descriptive-map tests. The tests exercise source reconstruction, authority before source reads, missing/altered figures and paired pages, count/CI preservation, download traversal/raw-source/privacy rejection, deck/PDF scope pins, copy-time file changes, and unchanged legacy versus final status behavior. No deck dependencies are imported on the legacy DEV/VAL export path.

Independent review requested the narrow PPTX relationship-file privacy correction. Both `.xml` and `.rels` members are now scanned, with a synthetic private external-target rejection fixture; all eight final-delivery tests still pass. PDF input-HTML provenance is a preexisting renderer limit: packaging verifies root-certified public content, exact PDF bytes and the render page count, not native-PPTX parity or a new HTML-to-PDF proof.

## Inputs after root review

1. Attach the complete reviewed TEST section through `append_signed_comparison.py`. Its original `source_path`, artifact SHA, review SHA, exact condition order and all adapter-derived fields must remain available. Public export reconstructs the section from that pinned source, then applies the existing final-deck cohort/metric validator. Additional coverage is allowed; changed metric rows are rejected. Root-authored operational status must also be refreshed upstream; this exporter does not invent current activity.
2. Optionally attach `report.descriptive_whole_cohort` through the already reviewed wrapper schema. The complete `measurement` must be exactly the JSON artifact named by its `source_sha256`, not a container with an extra measurement key. It requires its separate root review/reveal, the same 12 methods, 469 questions / 19,435 sites, original question rules and native hallucination denominator. Without this source no whole-project completeness is asserted.
3. Produce TEST figures with the evaluator's reviewed exporter using `--question-level --paired-deltas`. Its `provenance.json` retains `status=exported_supplied_values_no_aggregation`, `stage=test`, source/review/identity/family-count pins, exact method order, `plotted_cell_metrics`, `plotted_question_metrics`, optional `plotted_paired_metrics`, and a relative `files` list of exact PNG/PDF hashes. Cell/question figures and every supplied paired page are required when figures are requested. Optional existing cross-task images remain allowlisted.
4. Build the reviewed final deck with existing `build_final_slides.py --final`, then render its PDF with the existing HTML mirror pipeline. Keep `build.json` and `render.json`. PPTX/notes hashes must appear in `build.json.outputs`; PDF SHA and page count must match `render.json`. The deck receipt must identify the same TEST artifact and whole-469 scope. Native PowerPoint rendering remains unvalidated; no parity claim is made.
5. Root reviews each exact public download's contents. Text and PPTX XML are additionally scanned by the exporter; PDF privacy is certified by the explicit root review and exact byte pin. No directory copy, raw `report-source.json`, editable source JSON, or geometry dump is published.

Before generating the whole-469 artifact, create a new ready copy of `configs/whole_cohort_descriptive_v1.prepared.json` with root-reviewed complete DEV, VAL and TEST report paths/hashes and the current approved implementation hashes. Preserve the prepared plan and historical receipts. Its pending status, unbound reports and historical source pins do not authorize execution.

## Optional delivery review schema

All paths below are local inputs; public names are single filenames. Omit optional source entries instead of leaving unresolved placeholders.

```json
{
  "status": "root_reviewed",
  "reviewed_by": "root",
  "reviewed_utc": "ISO timestamp",
  "test_reveal_authorized": true,
  "test_artifact_sha256": "attached TEST artifact SHA",
  "test_review_metadata_sha256": "attached TEST review SHA",
  "sources": {
    "test_figures": {"path": "figure-directory/provenance.json", "sha256": "receipt SHA"},
    "whole_cohort": {"path": "whole descriptive measurement JSON", "sha256": "artifact SHA"},
    "deck_build": {"path": "deck-directory/build.json", "sha256": "receipt SHA"},
    "deck_render": {"path": "deck-directory/render.json", "sha256": "receipt SHA"}
  },
  "downloads": [
    {"kind": "editable_slides", "path": "deck-directory/draft.pptx", "sha256": "file SHA", "public_name": "slides.pptx", "label": "Editable slides", "public_content_verified": true},
    {"kind": "slides_pdf", "path": "deck-directory/draft.pdf", "sha256": "file SHA", "public_name": "slides.pdf", "label": "Slides (PDF)", "public_content_verified": true},
    {"kind": "notes", "path": "deck-directory/speaker-notes.md", "sha256": "file SHA", "public_name": "speaker-notes.md", "label": "Speaker notes and appendix evidence", "public_content_verified": true},
    {"kind": "report", "path": "reviewed-public-report.md", "sha256": "file SHA", "public_name": "research-report.md", "label": "Research report", "public_content_verified": true}
  ]
}
```

Sources are optional: a figures-only receipt needs no deck dependencies/downloads; report-only downloads need no deck receipt. Whole evidence, if attached, requires its source pin. PPTX/PDF/notes downloads require the deck build receipt, and PDF additionally requires the render receipt. Each kind/name is unique. Paths cannot become public links; names reject traversal and nonallowlisted extensions.

## Command

Keep the existing DEV scaling and DEV/VAL site-map flags so all prior downloads remain available. Use a new isolated output directory, not the Site checkout.

```bash
python scripts/build_public_dashboard.py \
  --output .state/final-public-preview-v1/dist \
  --development-figures REVIEWED_DEV_SCALING_DIRECTORY \
  --descriptive-review configs/descriptive_grid_review_v1.json \
  --descriptive-review-sha256 ed5b850a8921522350dc0854e75800c7011696c0c516ec966e85ec99286ff82c \
  --delivery-review REVIEWED_FINAL_DELIVERY_JSON \
  --delivery-review-sha256 EXACT_FINAL_DELIVERY_SHA
```

The optional folded all-469 appendix has a compact 48-row table and a separate sanitized JSON download containing exact metric objects, supplied paired intervals and source warnings. The main TEST/VAL charts, criteria, qualitative strings and method rankings are not changed. Deck/report links are folded below the main overview and listed on the download page. Pending-heldout wording is removed only after complete TEST source/reveal validation, even if no deck is ready. A TEST-only download bundle explicitly says whole-469 evidence is pending and is not complete-project delivery.

Root still must supply the real reviewed sources, run the isolated export, inspect desktop/mobile output and privacy/source receipts, then publish. This handoff is synthetic engineering validation, not completed final delivery.
