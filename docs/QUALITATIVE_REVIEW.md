# Shared qualitative review

Status: the root coordinator approved the fixed anchor panel on 2026-10-10 at 14:39:17 UTC. [The panel manifest](../configs/qualitative_shared_panel_v1.json), SHA256 `36aa5977c631a84b1fceca0cfd22d60de7de58e124930ab7503ed617acefc5cf`, is authoritative. This review uses existing development pilot evidence; it does not authorize new inference, judging, or inspection of TEST outcomes.

## One shared panel

Use **eight fixed pilot cells: two per family**, with distinct items and related groups within each family. Compute prepared the manifest and root independently reproduced the selection. Groups, then items, then cells were selected by the recorded seeded hash ordering (`seed=20261010`), without reading method gains, scores, or verdicts. Bind the frozen pilot manifest, candidate snapshot, selection/result sources, exact cell IDs, selection rule, and hashes. Preserve the proposal and approval timestamp.

Every runnable method uses these same eight cells. Do not replace an inconvenient, unchanged, empty, or unavailable anchor. Record missing evidence and its reason. A partial-grid development pilot remains a partial-grid pilot. The panel is a reproducible illustration, not a representative estimate of improvement.

Include raw released N=1 and deterministic capped N=1. Compare each method with its relevant same-pool parent or best-of-N control: for example B at N=16, E3 at N=8, and D/F at their recorded N. State candidate count, output cap, shortening, helper work, and inference cost. Identical cells do not make unequal sample budgets or helper costs equal.

## Evidence and interpretation

For each anchor and method/variant retain:

- Exact baseline and new text, with original sample/bullet/edit provenance, method/configuration and source hashes.
- Pinned evaluation context, target/answer rule, and raw judge evidence or deterministic recovery match. These are evaluation-only inputs; helpers and selectors must never receive them.
- Tokens, bullets, empty outputs, incomplete judgment, and any text not visible to the reconstructor's first-32-token-per-bullet score.
- A short plain-language explanation of what changed, the failure mode, and plausible alternative explanations.

Classify observed changes as correction, recovered mention amid an unreliable explanation, shortening/abstention, added or retained unsupported detail, entity/number/relation/qualification change, judge-sensitive/uncertain, or unchanged. Several labels may apply. Preserve disagreement with the official judge rather than replacing its verdict. Unsupported content is not automatically false; a transcript contradiction is not proof that the activation lacks that content.

Family-specific checks matter. A multi-hop target phrase can appear alongside false collaborators. A correct chain number can occur inside wrong calculations. Role binding requires the right direction and entities; descriptive roles may be acceptable under the benchmark even without names. Hallucination reviews distinguish contradictory, off-topic, consistent, and generic output, then inspect stage-2 evidence and coverage. A numerical or word hit alone does not establish a faithful explanation.

Cover **every approach A–G and its materially different measured variants**, plus combinations and controls. Cluster similar variants in the presentation while retaining their individual source records. For B distinguish bad semantic merges, qualification loss, unverified pairs, and formatting failures; exact repetition can still repeat a hallucination. For C and combinations examine deleted useful details and matched random deletion. For D check cross-bullet incompatibility. For E separate final readouts from controlled phrase diagnostics. For F distinguish cosmetic cleanup, semantic edits, and new unsupported wording. G's token-rank evidence is a diagnostic, not an invented prose readout or proof of relations. Mark unavailable/unrun variants, including deferred readers, explicitly; do not infer their behavior.

## Rare changes and independent review

If the common panel misses a method's rare changes, add **at most two method-specific supplements**: one apparent win and one apparent regression. Choose deterministically within the eligible changed-output pool using a recorded seeded hash ordering. Label them outcome-selected, record the comparator and eligible counts, and say `none observed` when appropriate. Never manufacture a win or loss. Include unchanged parents when explaining an edit.

The root coordinator assigns a primary reviewer and a rotating independent Sol reviewer for each method group. Reviewers work from the frozen evidence and return their own interpretation before synthesis. Record reviewer identity, timestamps, inspected IDs, disagreements, and resolutions. Runtime Luna judging remains the benchmark evaluation; research-agent review is qualitative evidence. No review changes frozen selectors, official verdicts, or the TEST menu.

## Artifacts and dashboard

Keep the full audit as one compact, hash-bound artifact outside Git, containing all eight anchors per available method and the bounded supplements. Link raw source evidence and list missing/unrun coverage. Each method gets a short takeaway, limitation, comparator, and recurring inference effort/cost, separate from shared campaign caching.

The dashboard uses collapsed two-up baseline/new cards, one anchor at a time with selectors, and at most two brief previews per method. Link the complete audit. Keep qualitative mechanisms separate from full-cohort metrics, denominators, grouped intervals, and cost tables. Examples explain changes; they do not establish a population rate, significance, or a universal winner.
