# Draft editable slide proof

This is a four-slide **DRAFT development/validation style proof**, not the final deck. It contains no TEST quality results and is not approved for publication. The final storyboard is in [SLIDE_PLAN](../../docs/SLIDE_PLAN.md).

`style-proof-v1.json` is the editable content source. The builder validates its report SHA, reviewed validation artifact, exact example quotations and retained plot hashes before writing anything. All sixteen displayed rates, counts and intervals come directly from that report. The core diagrams, text and chart marks are editable PowerPoint objects; notes preserve the full selected/parent example and source hashes. `requirements-v1.txt` pins the isolated dependency environment.

The requested `.state/slide-env` path is a symlink to a project-owned environment off HOME at `${OLENS_COMPUTE_ROOT}/envs/slides-v1`. The model runtime and prior research wheels were preserved.

Example local build, on an allocated CPU slice with explicit paths:

```bash
.state/slide-env/bin/python scripts/build_slides.py \
  --source dashboard/slides/style-proof-v1.json \
  --report EXACT_SOURCE_REPORT.json \
  --output NEW_IMMUTABLE_DRAFT_DIRECTORY \
  --chrome LOCAL_CHROMIUM_PATH --node LOCAL_NODE_PATH
```

Omit browser options to build only the PPTX, HTML, notes and source manifest. Node >=22 is required for the bounded optional CDP renderer. The report must match the source JSON's exact SHA; the final public snapshot changing is not permission to silently update the source. Each completed build retains its exact source/report copies, dependency versions, vector geometry and hashes.

The PDF route prints the same-geometry HTML mirror, then renders actual PDF pages through PyMuPDF for visual inspection. This is **not native PPTX-to-PDF conversion**. There was no installed LibreOffice package, binary or module in the bounded check; a large office dependency installation was avoided. Native PowerPoint rendering and PPTX/PDF visual parity remain unvalidated. A native Google Slides conversion/export check remains an option for the eventual final deck.

The first command-line Chromium print attempt timed out at 45 seconds and was preserved under `fast/slides/style-proof-v1`; subsequent CDP rendering succeeded. Earlier spacing/print-geometry proofs remain versioned. The current local proof is `fast/slides/style-proof-v4`, with `draft.pptx`, `draft.pdf`, `draft.html`, `speaker-notes.md`, four page PNGs, a contact sheet and build/render receipts. Three focused offline tests cover source/test exclusion, exact excerpts/metric preservation, editable objects/notes and overwrite rejection. No model, judge, paid API or benchmark generation was used.

The original builder deliberately accepts only the four-slide proof and remains unchanged. A separate comprehensive draft is now prepared by [build_final_slides.py](../../scripts/build_final_slides.py), using `final-draft-dev-val-v6.json`. It has 16 core slides and a navigable appendix: all supplied pilot quality/auxiliary rows, same-pool paired intervals, all 12 validation methods, complete development curves, explicit method coverage, one fixed example per method and known work components. The final TEST and requested same-menu/all-469 summaries remain empty. It is a draft for review, not a published final deck.

```bash
.state/slide-env/bin/python scripts/build_final_slides.py \
  --source dashboard/slides/final-draft-dev-val-v6.json \
  --report EXACT_SOURCE_REPORT.json \
  --output NEW_IMMUTABLE_DRAFT_DIRECTORY \
  --chrome LOCAL_CHROMIUM_PATH --node LOCAL_NODE_PATH
```

Use the retained `report-source.json` from its build to reproduce that exact snapshot after the dashboard updates. The PPTX contains editable native text, points, interval marks, diagrams and notes. The PDF is an actual rendered HTML mirror; native PowerPoint visual fidelity remains unvalidated. Full exact outputs/context/verdicts belong in notes; visible quotations are explicitly labeled excerpts. The diagram-only reader diagnostic shows coverage, never an invented quality rate. Missing intervals and costs are not zero.
