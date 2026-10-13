# Experiment 070 — Custom method comparisons and a second sampling axis

Presentation-only update, 2026-10-13 UTC. The user requested independent method toggles to assemble a custom comparison, plus AR reconstruction on a second vertical axis in each existing sampling plot.

Published as public version **23** at the [existing website](https://olens-improve-research.jan618.chatgpt.site/). The receipt records exact source, version and deployment identities.

## Changes

The six reconstruction-versus-task method buttons independently toggle inclusion. Show all and Clear reset the selection. The count, active button states, plotted methods and exact-value tables stay synchronized. Empty selections keep the original released lens and four-bullet references. Selection persists through resizing, cohort changes elsewhere on the page, and parent-arrow toggles.

Each sampling panel defaults to task performance on the blue left axis and AR reconstruction on the amber right axis for N=1,2,4,8,16,32. Circles and squares, line styles and colored axis labels distinguish the two quantities. Existing pointwise intervals are copied for both series. The original released lens task rate remains a separate reference. Existing task-only and reconstruction-only modes remain available. The overlay is disabled for other cohorts because the reconstruction snapshot covers the full bank; this prevents mixing task-subset quality with all-bank fit. The axes are independently scaled and the caption warns that line crossings do not imply equal values.

All frozen scientific payloads remain unchanged. Asset revision query strings prevent existing browser caches from retaining the earlier single-axis controller. The reconstruction figure is a sibling section after the complete six-method block.

## Verification

- All 64 possible method subsets passed point-count and identity checks, including empty and full selections.
- All 48 sampling values (24 quality and 24 reconstruction) exactly match the saved source data.
- Desktop 1440px and mobile 390px checks passed, including multi-selection, keyboard toggles, single-axis views, the cohort guard, enlargement, retained references and absence of page overflow.
- Desktop sampling and mobile custom-comparison screenshots were visually inspected. JavaScript syntax and whitespace checks passed.
- Four existing site assets change and one JavaScript asset is added; 103 other assets and both embedded scientific payloads are preserved. No inference, judging, GPU work or new statistics.

The [verification and delivery receipt](../reviews/custom-comparisons-v1.json) records the publication state and source hashes.
