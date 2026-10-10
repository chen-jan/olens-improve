# 010: Candidate-only editing and reconstruction selection

Status: round1 and round2 proposal scoring and blind judging completed on all 189 frozen pilot development cells. The coordinator reviewed the round1 beam before approving round2. The implementation keeps both unchanged initial outputs and every admissible edited proposal, so choosing an edit is optional.

The helper proposed at most four edits across two parents in round1. The first API snapshot had proposal-ID validation failures; these were instrumentation failures, not evidence against editing. A deterministic repair recovered valid references without another API call or changing generated text. The repaired snapshot contains 280 accepted proposals and 31 provider-stage rejections, including 24 unresolved parent references. Its transformation record preserves original provider IDs, request correspondence and both input hashes.

`scripts/score_edits.py` checked exact cohort coverage, layer and development membership, parent references, candidate-ID uniqueness, and the frozen four-bullet/256-token policy. It retained full source text verbatim, encoded each new scoring atom through the matched AR, and evaluated exact joint nonnegative least squares against the same original target activation. The independent editing cache preserves the production cache; sharing identical truncated scorer inputs does not establish semantic equivalence. Existing parents reproduced their recorded exact scores within the predeclared `1e-5` tolerance. All seven editing/cache unit fixtures passed.

The run on H200 job 25459615 took 37.58 seconds, including loading, encoding 603 new vectors at batch 128, and scoring 658 candidates. There were no additional scorer-stage rejections. Nineteen edited states entered the two-state beams; only four edited outputs became the highest-scoring final output:

| Family | Cells | Edited best outputs | Largest FVE increase over the best unchanged parent |
|---|---:|---:|---:|
| Hallucination | 72 | 2 | .006099 |
| Multihop | 24 | 0 | 0 |
| Chain intermediates | 21 | 1 | .0000444 |
| Role binding | 72 | 1 | .002492 |

FVE means fraction of whitened activation variance explained by the phrase reconstruction. These are reconstruction results, not accuracy improvements. Several gains lie near the observed numerical drift scale; even the larger gain could reflect shortening or fluency rather than recovery. The selected chain edit mostly removes stray formatting, and the largest hallucination change rephrases a party response. Their subsequent blind judging and matched baseline comparisons are recorded below. Round2 receives the full round1 candidate history, including proposals outside the beam, to keep the final selection reversible.

A matched-execution sensitivity audit reencoded all affected atoms from these four selected edits and their best unchanged parents together in one batch. All four reconstruction gains remained positive: chain .0000650, hallucination .000806/.005859, role .002269. Gain changes from the cached results ranged from +.0000206 to −.0002394. The 24.68-second audit saved its vectors/results separately at `${OLENS_DATA_ROOT}/diagnostics/editing-round1-sensitivity-v1`; no main vector or score was replaced. This checks only four selected winners and does not establish general robustness or semantic quality.

Artifacts are under `${OLENS_DATA_ROOT}/runs/helper-edit-pilot-v1`:

- Repaired input: `round1-repaired/editing_proposals.jsonl`, SHA256 `2eadf1e5124f387c744e22b081ca04d49ff7f32aa0e749ea1672dd820bf089fd`; `transformation.json` records the repair.
- Beam: `round1-scored/beam.jsonl`, SHA256 `e4c5ccebb2699dfcf8f8045288d164cbf760c0c4df75c963d1431cbd79b05d75`.
- Complete history: `round1-scored/scored_candidates.jsonl`, SHA256 `ca788d074beb3b86b9549866aac42a80553c4eb1ee6a99605cee47272518a892`.
- `round1-scored/spec.json` records checkpoint, activation, split, token-span and code hashes; `status.json` records runtime and unjudged status.

No O-lens samples or paid judge calls were added by local scoring. Helper/API costs and subsequent blind judgments are tracked by the shared ledger. No judge verdict was given back to the editor.

Round2 subsequently scored 333 new proposals, encoding 660 new vectors in 38.10 seconds. Exact cohort/lineage checks retained all initial and round1 candidates verbatim. Four additional final outputs changed (two chain, one hallucination, one multihop), giving eight edited winners across both rounds: chain 3/21, hallucination 3/72, multihop 1/24, role 1/72. Their local FVE increases do not establish better semantics. The round2 complete-history SHA256 is `1dd875406526374e7654c71cf156dd8d9f05c41f3937e7f4f17e9eba50a67a7e`.

`scripts/export_edits.py` verifies both full cohorts, unchanged history text, selected-candidate membership and caps, then exports one row per cell with separate round1/round2 conditions. After two permission-review timeouts, the coordinator copied the identical validated temporary export to `${OLENS_DATA_ROOT}/selections/editing-pilot189-v1`. Its SHA256 is `6b820154f9bbea6839f205986218679ca21cca5d9d85daaa3ffe82ff7920816d`; no scientific scoring failed because of the export delay.

The coordinator's completed blind evaluation found no aggregate recovery gain over the D32 parent: both rounds retain multihop 10/24, chain 1/21 and role 8/72. Round1 retains 42/70 transcript-contradicting specific readouts; round2 has 42/69, with one more nonasserting readout and no reduction in the wrong count. These partial-grid cell diagnostics do not replace official full-grid item scoring. Paired transitions require separate review; equal aggregates do not guarantee unchanged semantics.

The text audit includes all eight edited winners, two first-by-ID unchanged cases and two additional seeded random unchanged cases, with the first lower-fit proposal by ID when available. Three chain winners remove headings/formatting while preserving inconsistent numbers. The role winner shortens phrases while retaining conflicting roles and trial contexts. One hallucination edit adds “first step” and “need it” absent from its parent; its change summary claims retained wording. These are added completions, not independently established contradictions. The multihop winner changes `安德烈·Шуляв` to `安德рей·Шуляв` despite describing itself as punctuation-only. This violates name-surface preservation and the helper's description; the unchanged parenthetical “Andrei Shulyav” does not establish a different identity or a new false fact. Losing proposals include deletion/fragment completion that lowers reconstruction; unchanged outputs can still contain unsupported content. Audit records and script are at `${OLENS_DATA_ROOT}/analysis/editing-pilot189-review-v1`.

The coordinator independently checked paired judgments: every round1 hallucination class matches D32; round2 changes only `chat-dailydialog-0047`, layer 60, position 182, from consistent to generic. No wrong-class flips occurred. Every role pass outcome matches the parent in both rounds. Thus the denominator change reflects coverage, not reduced contradictions.

Decision: do not expand free editing broadly on this evidence. Keep the completed bounded experiment and test cached parent-plus-pruning combinations for redundancy, with identical-pool component-off and matched-deletion comparisons. A stricter editing revision would need fresh evidence and should explicitly distinguish deletion from newly completed or rewritten claims.
