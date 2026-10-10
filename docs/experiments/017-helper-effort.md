# 017 — Reasoning effort for candidate-only semantic matching

Updated: 2026-10-10 UTC. Status: **completed bounded diagnostic**. Run `helper-semantic-effort-audit-v1`; reviewer GPT-6.1 Sol. This changes neither the benchmark judge nor the frozen 189-cell v5 outputs.

On forty selected natural pairs, medium-effort Luna avoided the clear false equivalences seen in the fresh none-effort control: **zero versus three**. It accepted fewer equivalences overall, **four versus ten**, and conservatively split two manually equivalent pairs rather than one. Both calls completed at each effort. Medium took about 37–40 seconds per twenty-pair request, versus 10–12 seconds for none. This is promising evidence that extra reasoning can help matching, with a latency/recall cost; it is not a population accuracy estimate or proof that semantic consensus improves readouts.

## Frozen comparison and access boundary

The forty pairs are the fresh qualitative audit in [015](015-consensus-pilot.md), ten per family, selected by seed and label strata before this effort comparison. Their normalized text pairs exclude the sixty earlier natural audit pairs, but source items/templates overlap development data. Manual conservative whole-bullet labels were recorded before the effort calls. These are merge-admissibility judgments, not benchmark truth labels.

Both efforts use identical candidate text, v5 instructions, strict local pair-ID schema, twenty-pair chunks, Standard tier and a 10,000-token output ceiling including reasoning. Only opaque pair IDs and complete candidate bullet text enter the model payload. Family/cell IDs, manual labels, benchmark context, answers and verdicts remain local. No proposal step, O-lens generation, AR scoring or GPU work was added.

The first medium chunk served as the actual capability check; only after validating its complete structured output did the runner dispatch the two fresh none chunks and remaining medium chunk. This first chunk remains part of the forty-pair medium comparison. Physical attempts are limited to one per chunk, SDK retries are disabled, and the shared atomic ledger enforces a $1 run ceiling.

The API requires a coupled setting change: none sends temperature 0; medium omits temperature. Therefore this compares the supported effort configurations, rather than attributing every difference solely to reasoning effort. A separate helper-only client permits none/medium; the default and benchmark client still reject medium before reserving or dispatching. Model, effort and complete schema/content parameters enter cache identity. The benchmark judge remains `gpt-6-luna`, reasoning `none`.

## Observations

| Outcome on these forty pairs | None | Medium |
|---|---:|---:|
| Equivalent labels | 10 | 4 |
| Clear non-equivalent pairs labeled equivalent | 3 | 0 |
| Manually uncertain pairs labeled equivalent | 2 | 0 |
| Manually equivalent pairs split | 1 | 2 |
| Missing/invalid pair labels | 0 | 0 |

Eleven categorical relation labels changed. The selected audit oversamples previously accepted/rejected/uncertain relations; neither 0/40 nor 3/40 is an unbiased error estimate. Small differences and manual semantic judgments do not establish deployed accuracy. None's fresh labels also differ from its native 189-cell labels, demonstrating batch/repeat variability.

Examples, with full text and evidence in `pair-results.json`:

- Different arithmetic histories sharing leading 15: none called them equivalent; medium recognized that operation order differs and returned related.
- “not Chloe” versus “not Mia”: none called them equivalent; medium retained the distinct exclusions and returned related.
- “brief apology” versus “apology”: none called them equivalent; medium returned one-way entailment because the brief qualification is absent from the second text.
- Resentment versus further conflict was related under both fresh controls; neither calls it equivalent. This is an unchanged rejection, although the original native v5 label was incorrect.
- A stand-up comedian during a show versus a comedian without that context changed from one-way entailment to related. Neither merged the pair in this fresh comparison.
- Some reasonable generic paraphrases remain conservatively split; stronger reasoning is not a demonstrated recall improvement.

## Cost, reproduction and next decision

The ledger records four settled requests, no retries/errors/unknown reservations. None used 3,426 input and 2,583 output tokens, costing **$0.0017196** after the [cache-write correction](022-pricing-correction.md); its latencies were 9.99 and 12.46 seconds. Medium used the same input count and 7,775 output tokens, including **5,468 reasoning tokens**, costing **$0.0043156**; latencies were 40.00 and 37.38 seconds. Total corrected usage-derived spend is **$0.0060352**. The preserved original figures were $0.0016341/$0.0042301, total $0.0058642; correction events explain the difference. These amounts reconstruct usage at the verified tariff and are not a reconciled provider invoice.

Artifacts: `${OLENS_DATA_ROOT}/runs/helper-semantic-effort-audit-v1/` contains frozen identity, actual capability record, pair results, exact-request cache/events, raw usage and budget snapshot. Complete physical requests/responses are in the central ledger. Source script: `scripts/helper_effort_audit.py`, using the frozen audit at `runs/helper-semantic-repaired-pilot-v1/audits/B-v5-fresh40-manual.json`. Runtime is `configs/runtime.json`; the helper-only gate has offline tests in `tests/test_helper_effort.py`.

Decision: **consider a bounded independent pair-quality follow-up before semantic deployment**. Medium appears useful for careful confirmation, but fewer accepted merges can further reduce support and increase abstention. Do not silently replace the none labels, rerun the full 189 cells, or expand to full development from these forty selected examples. Keep latency and total completion/reasoning costs explicit; dollars alone would hide a substantial serial delay. Preserve negative and unchanged cases and use practical judgment rather than a significance gate.

Validation/test access ledger: only the frozen development candidate pairs were inspected; no validation/test outputs or benchmark answers entered this diagnostic.
