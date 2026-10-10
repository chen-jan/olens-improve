# Qualitative evidence coverage

The shared qualitative review is complete and coordinator-approved as of 15:27 UTC on October 10. Three primary reviewers and rotating independent reviewers inspected the fixed examples, exact outputs, source context and judge evidence. The expanded cards and complete development curves were published at15:49UTC after desktop/mobile and source-preservation checks. The inventory below preserves the earlier presentation audit; its old visible-card counts are historical, not current coverage. TEST outcomes were not inspected.

The approved public payload contains 688 variant/example records across all eight method and combination sections. These repeatedly use the same eight fixed examples; they are not 688 independent observations. All 1,436 before/after strings, including download-only supplements, match the reviewed source text exactly. Missing diagnostics, unchanged outputs and computed-but-unjudged variants remain labeled. At most two selected supplements appear per method; the download retains the complete reviewed variant supplement archive.

The fixed [eight-cell panel](../configs/qualitative_shared_panel_v1.json) is root-sealed, SHA256 `36aa5977c631a84b1fceca0cfd22d60de7de58e124930ab7503ed617acefc5cf`. It contains two distinct items and related groups per family, selected from the frozen 189-cell development pilot by seeded group → item → cell ranking without outcomes. The [review protocol](QUALITATIVE_REVIEW.md) governs comparators, supplementary cases, and independent review.

## Initial presentation audit (historical)

At inspection, `dashboard/report.json` had SHA256 `629be070f367a3678887eaf1e59de3b0f79c89fae5e4b58804c8411d01542582`. Its flat cards contain baseline/new text and editorial evidence summaries. They do not embed the original stimulus and structured raw judge evidence. These are presentation gaps, not necessarily missing underlying results.

| Approach | Visible development cards | Retained evidence available | Review gap |
|---|---:|---|---|
| A: choose the best complete sample | 3 | Frozen 189-cell selections and complete per-condition judgments; nested sample prefixes, random controls, and raw/capped N1 remain available | Shared source-context review across the prefixes; distinguish a correct mention from a correct explanation |
| B: exact or helper consensus | 0 | Repaired none/medium paired analysis with 10 comparator sets; provider/source-mapped false-merge audits | Display actual qualifications, unsafe merges, abstention, and medium's unknown labels; a helper agreement is not benchmark truth |
| C: remove low-contribution bullets | 0 | A32 parent/pruning selections and judgments; matched random-deletion controls where measured | Show exact deleted text and useful-content losses; numerical contribution alone does not establish factual irrelevance |
| D: combine source bullets | 1 | Complete same-pool selections and judgments; support-pooling review contains 23 traces | Inspect cross-bullet relations and incompatible claims, with the complete-sample parent and sample budget shown |
| E: contrastive checks | 0 | Likelihood review contains 27 traces; specificity/pruning review contains 25; controlled E2 phrase diagnostics are separate | Keep final-output evidence separate from controlled phrase discrimination; join the original context |
| F: edit proposals | 0 | Editing review contains 12 records, including the retained edited winners and unchanged controls, with immediate parents | Show cosmetic versus semantic change, preservation risks, and helper effort; retain the original and intermediate parents |
| G: independent reader | 0 | Eight-cell lexical diagnostic and 36 controlled E2 paired sets | No prose selector or benchmark-quality endpoint. Missing shared-anchor diagnostics stay missing; existing lexical/pair evidence cannot establish relations or output faithfulness |
| Combinations | 5 | E1 → pruning review (25 traces); exact support → pooling (23); specificity → pooling paired analysis (6 comparator sets), including pruning/random-deletion controls | Make component parents and all changed/deleted bullets visible; some apparent gains retain wrong spans or only match a substring |

Counts in this table refer to the named audit artifacts, not unique independent cells or exhaustive manual coverage of every measured variant. A, C, and D share the frozen `selections/pilot189-selectors-v1/selections.jsonl`; their authoritative 22-arm judgments are under `runs/development-shared-pilot-v2/judgments-standard-repair`. Other artifact paths are recorded in the corresponding experiment documents: [consensus](experiments/015-consensus-pilot.md), [editing](experiments/010-editing-scoring.md), [pooled specificity](experiments/020-pooled-specificity.md), and [cached combinations](experiments/011-cached-combinations.md). Paths and hashes in the case packs will be authoritative if navigation links change.

## Validation evidence count

`runs/validation-full-grid-v1/signed-menu-analysis-v1.json`, SHA256 `db223a374f51d9122f8cc430a347e4f82dea75ce3d449008e1def1f7cf89e918`, contains **37 comparison sets and 1,490 retained example rows**, with repeated cells across comparisons. It does not contain 37 individual traces. Seven selected flat validation cards were attached to the dashboard at inspection.

The underlying examples preserve exact baseline/proposed text and evaluation evidence. Hallucination examples include the pinned bank context and span/claim evidence. Multi-hop examples preserve the required roles and language-match result. Chain examples retain named values, reference arithmetic, and raw judge records. Role examples retain the exact multiple-choice block, gold and returned choices, and rationale. Context schemas differ by family; absence of one generic context field is not proof that all source context is missing. The display adapter currently reduces these richer records to flat summaries.

A scoped search of docs, dashboard report, and configs found no document describing the 37 comparison sets as 37 individual traces. The case-count clarification is still useful for new readers.

## Presentation and interpretation

Keep source context once per shared cell, then a method/variant selector with collapsed baseline/new text, raw judge evidence, and source provenance. Preserve raw/capped N1 and applicable A16/A32 or immediate component parents. Empty and unchanged outputs are valid observations; unavailable evidence must remain explicitly missing. Output length, first-32-token scoring limits, sample count, and recurring helper work belong beside the comparison.

Each method may receive at most two deterministically selected, separately labeled apparent win/regression supplements if the common panel misses its rare changes. They never replace the anchors. This is an illustrative development review, not a population estimate or proof that every variant works. Keep official verdicts alongside reviewer disagreement; a number/name match or role-task pass alone is not whole-output truth. Full context and output blobs belong in the durable case artifacts, with only compact coverage/provenance and readable synthesis in Git.

Reviewer ownership: compute/resource agent A/C/D; model agent E/F/G; evaluation agent B/combinations. Root coordinates independent crosschecks. No review feedback enters helpers, selectors, or frozen menus.
