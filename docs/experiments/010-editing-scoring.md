# 010: Candidate-only editing and reconstruction selection

Status: round1 proposal scoring completed on all 189 frozen pilot development cells; semantic outcomes remain unjudged. Round2 requires the coordinator's beam review. The implementation keeps both unchanged initial outputs and every admissible edited proposal, so choosing an edit is optional.

The helper proposed at most four edits across two parents in round1. The first API snapshot had proposal-ID validation failures; these were instrumentation failures, not evidence against editing. A deterministic repair recovered valid references without another API call or changing generated text. The repaired snapshot contains 280 accepted proposals and 31 provider-stage rejections, including 24 unresolved parent references. Its transformation record preserves original provider IDs, request correspondence and both input hashes.

`scripts/score_edits.py` checked exact cohort coverage, layer and development membership, parent references, candidate-ID uniqueness, and the frozen four-bullet/256-token policy. It retained full source text verbatim, encoded each new scoring atom through the matched AR, and evaluated exact joint nonnegative least squares against the same original target activation. The independent editing cache preserves the production cache; sharing identical truncated scorer inputs does not establish semantic equivalence. Existing parents reproduced their recorded exact scores within the predeclared `1e-5` tolerance. All seven editing/cache unit fixtures passed.

The run on H200 job 25459615 took 37.58 seconds, including loading, encoding 603 new vectors at batch 128, and scoring 658 candidates. There were no additional scorer-stage rejections. Nineteen edited states entered the two-state beams; only four edited outputs became the highest-scoring final output:

| Family | Cells | Edited best outputs | Largest FVE increase over the best unchanged parent |
|---|---:|---:|---:|
| Hallucination | 72 | 2 | .006099 |
| Multihop | 24 | 0 | 0 |
| Chain intermediates | 21 | 1 | .0000444 |
| Role binding | 72 | 1 | .002492 |

FVE means fraction of whitened activation variance explained by the phrase reconstruction. These are reconstruction results, not accuracy improvements. Several gains lie near the observed numerical drift scale; even the larger gain could reflect shortening or fluency rather than recovery. The selected chain edit mostly removes stray formatting, and the largest hallucination change rephrases a party response. Blind judging and matched baseline comparisons remain necessary. Round2 must receive the full round1 candidate history, including proposals outside the beam, to keep the final selection reversible.

A matched-execution sensitivity audit reencoded all affected atoms from these four selected edits and their best unchanged parents together in one batch. All four reconstruction gains remained positive: chain .0000650, hallucination .000806/.005859, role .002269. Gain changes from the cached results ranged from +.0000206 to −.0002394. The 24.68-second audit saved its vectors/results separately at `${OLENS_DATA_ROOT}/diagnostics/editing-round1-sensitivity-v1`; no main vector or score was replaced. This checks only four selected winners and does not establish general robustness or semantic quality.

Artifacts are under `${OLENS_DATA_ROOT}/runs/helper-edit-pilot-v1`:

- Repaired input: `round1-repaired/editing_proposals.jsonl`, SHA256 `2eadf1e5124f387c744e22b081ca04d49ff7f32aa0e749ea1672dd820bf089fd`; `transformation.json` records the repair.
- Beam: `round1-scored/beam.jsonl`, SHA256 `e4c5ccebb2699dfcf8f8045288d164cbf760c0c4df75c963d1431cbd79b05d75`.
- Complete history: `round1-scored/scored_candidates.jsonl`, SHA256 `ca788d074beb3b86b9549866aac42a80553c4eb1ee6a99605cee47272518a892`.
- `round1-scored/spec.json` records checkpoint, activation, split, token-span and code hashes; `status.json` records runtime and unjudged status.

No O-lens samples or paid judge calls were added by this scoring run. Helper/API costs are tracked by the shared ledger; this record reports only local scoring. Continue with reviewed round2 proposals, score unchanged and all edited alternatives, then judge final round1/round2 outputs without giving verdicts back to the editor.
