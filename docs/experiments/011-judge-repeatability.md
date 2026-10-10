# 011 — Independent repeatability audit of the Luna judge

Created/updated: 2026-10-10 UTC. Status: **completed diagnostic**. Run: `judge-repeatability-v1`; parent: the shared 189-cell development pilot. Reviewer: GPT-6.1 Sol. Primary scores remain unchanged.

The same evaluation content produced changed contradiction labels. Among ten seeded random A32 hallucination cells, **two changed whether any wrong span was present**, and six changed their classification or quoted spans. The random cells covered six source items, so these fractions are descriptive rather than independent accuracy estimates. The number called wrong stayed six: opposite-direction flips canceled. Small aggregate differences can therefore coexist with unstable individual verdicts.

The separately selected party example changed from five wrong spans to none. Stage-2 claim/status lists changed in 12 of 13 repeats while the original established-false evidence was fixed. This makes fine-grained tally comparisons uncertain; it does not establish which verdict was correct. All 26 requests completed, costing **$0.0059335** in the central ledger.

## Question, scope and frozen procedure

Question: how stable are the official Luna contradiction labels and claim tallies when the exact evaluation content is replayed? The expected failure mode was labeling a plausible paraphrase as a contradiction, or silently changing primary results after inspecting suspicious cases. The only experimental change was making one independent repeat request per stored request. No outputs were edited and no new O-lens samples were generated.

Source, banks, model/adapter revisions, fresh activation provenance and grouped splits are those in [002](002-data-evaluation.md) and [PLAN](../PLAN.md). All inspected outputs are development-only. The pilot manifest SHA is `1183492d6f11b2c8b78c4eddc03d3d601da3ac602b195557d1914077cb5245fd`. Candidate pool SHA is `83ce478e1d309167126a9fd4165e24ac9aa450c607d2fee8f579092b1da55992`; A32 selection SHA is `055c5ea0e0d85fd5aa83af58f2cd1c2f2ea5a95940f1ecd6af4669c9a1f288c5`.

Selection was frozen before repeat results: seed `20261010`, ten random A32 cells from the 72 hallucination cells, excluding two previously flagged cells; then the party and StoryBuddies A32 cells and the paired raw N1 StoryBuddies cell. Flagged examples are reported separately. There are 13 readouts and 26 requests, one for each hallucination stage. This is a partial-cell reliability diagnostic, not an official full-grid benchmark estimate or a validation/test result.

The stored original request includes the complete messages, schema, `gpt-6-luna`, reasoning effort `none`, and maximum output allowance. Its original validated result and paid-attempt/response IDs are retained. The repeat uses identical content parameters, with Standard tier and a 90-second timeout. **All originals used Flex.** This is therefore an audit of repeat variability including the authorized tier transition; it does not isolate a within-tier repeat effect. No seed or temperature was added. The schema and source prompt versions were unchanged.

Stage 1 was replayed independently. Stage 2 reused its **original** established-false evidence, without substituting the repeated stage-1 verdict. Stage-2 changes cannot adjudicate the original contradiction classification. The audit uses a separate namespace, no primary verdict-cache hits, one physical attempt per request, SDK retries disabled, and a $1 run ceiling. Failed calls would have been counted separately; none occurred.

## Results and inspection evidence

| Sample | Readouts | Wrongness flips | Classification/span changes |
|---|---:|---:|---:|
| Seeded random A32 | 10 | 2 | 6 |
| Previously flagged A32 | 2 | 1 | 1 |
| Paired raw N1 StoryBuddies | 1 | 0 | 0 |

Stage 2 completed for 13/13 requests: full JSON differed in 13/13 and quoted claim/status lists differed in 12/13. Rationale-only differences are excluded from the latter count. No confidence interval is used to imply a population error rate from this small, clustered, partly selected diagnostic.

Representative changes, with exact texts and responses in `requests.jsonl`:

- `chat-dailydialog-0027`, L20/p88, A32: the unchanged readout offered help composing an introduction, a greeting, social topics, etiquette and an RSVP. Original wrong spans included “Help you compose a clever introduction line for the party.” The repeat found no wrong spans. The transcript offered a witty conversation starter and fun topics; this is a plausible paraphrase boundary, not proof that either overall verdict is correct.
- `chat-lmsys-0005`, L44/p36, A32: “immersive AR experiences” changed from wrong to unmarked. This is a second wrong-to-consistent flip.
- `chat-lmsys-0023`, L60/p464, A32: four proposed explanations of small-object limitations changed from unmarked to wrong. This opposite-direction flip shows that repeats need not systematically improve the score.
- `chat-lmsys-0023`, L60/p20, A32: the wrong span changed from “focal loss” to “introduced by Google Research,” with wrongness unchanged.
- The flagged StoryBuddies A32 and raw N1 classifications stayed unchanged. A32's unverified alternative names still cannot be counted as recovered truth merely because no contradiction is marked.

No proposed-method wins or regressions are established by this audit. The observed changes concern measurement stability; the random sample includes unchanged cases in the complete artifact.

## Cost, reproduction and decision

Actual usage: 38,675 input tokens and 4,132 output tokens; no cached input tokens. Empirical physical-request latency was approximately 1.66 seconds median and 2.43 seconds at the 95th percentile, with four bounded slots. There were no retries, missing responses or new unknown-charge reservations. This experiment used no GPUs; artifact size is small and all complete prompts/results stay outside Git.

Artifacts: `${OLENS_DATA_ROOT}/runs/judge-repeatability-v1/` contains `input.json`, `prepare_inputs.py`, `input_identity.json`, `requests.jsonl`, `summary.json` and the execution log. Input SHA: `4bed0e09e299dabc924622e21f3144fa73687cff6bb66d51e808197662a3bfbc`. Preparation verifies every selected result against the original paid response. Code milestone: `bab0ce4`; interpreter/dependencies: `configs/runtime.json`.

Reproduce by running the saved preparation script, then the `olens_improve.evaluation` entrypoint with `--repeat-request-audit input.json --run-id judge-repeatability-v1 --run-cap-usd 1 --tier default --concurrency 4`. The existing checkpoint prevents another physical attempt for completed audit IDs. A new replicate requires a distinct frozen run and fresh budget accounting.

Decision: **retain official primary verdicts; treat small hallucination differences as provisional and judge-sensitive**. Use paired traces, off-topic/assertion share, coverage and recovery to decide whether a method merits larger development measurements. Repeats alone do not establish accuracy, justify silently replacing labels, or train the selector/editor on judge feedback. Any future reliability comparison should prespecify a larger item-group sample and distinguish within-tier from cross-tier variation.

Validation/test access ledger: 2026-10-10 UTC, GPT-6.1 Sol and the repeat runner inspected only the frozen development cells above for evaluation reliability. No validation or test outputs were accessed; helpers/editors never receive these contexts or verdicts.
