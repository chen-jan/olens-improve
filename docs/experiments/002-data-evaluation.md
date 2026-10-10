# 002 — Frozen data and real baseline evaluation instrument

Created/updated: 2026-10-10 UTC. Status: **completed instrument pilot; broader comparisons not run**. Parent: the frozen O-lens improvement plan. Runs: `instrument_n2_v1` (generation) and `instrument-n1-v1` (sample-0 evaluation).

The first real baseline passed the data-to-judge pipeline. Eight development cells produced one evaluated readout each; seven benchmark judge requests plus one preflight completed without API failures. Hallucination verification ran both stages. This is an instrument check, not evidence of an improvement or a full benchmark estimate.

Recorded Luna usage was **6,166 input and 617 output tokens**, with usage-priced spending **$0.00046255**. Flex physical-request latency was median **7.17 s**, 95th percentile **10.94 s** across eight responses. The old optional Claude attempt remains a separate **$2 unknown-charge reservation**; it is not measured spending. No new uncertain charges arose.

## Question and failure checks

Can the new scaffold identify the official cells, preserve source/template siblings, evaluate exactly one baseline sample per cell, and account for every paid attempt without modifying the historical checkout?

Main risks were selecting all cached chain positions instead of the official final token; handing a whole candidate pool to a judge as one arm; trusting incomplete cache provenance; losing charges on malformed/timeout responses; and leaking related examples across splits. No quality-based promotion rule applies to this instrument check. Later method decisions use practical effects, traces, regressions, cost and uncertainty, without a significance gate.

## Frozen inputs and grouping

WorkspaceBench source is `${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2`, commit `92d763e722377f5bfae045e829a308ab5919a820`. The target and adapter pins are in [PLAN.md](../PLAN.md). The historical checkout remained read-only. Exact bank/read-plan hashes are recorded in [splits_v2.json](../../configs/splits_v2.json); judge/scorer runtime source hashes accompany every `project_contract.json`.

| Family | Independent grouping rule | Development / validation / test items | Official cells |
|---|---|---:|---:|
| Hallucination | Same source and normalized exact prompt | 30 / 20 / 99 | 5,615 |
| Multi-hop MT | Shared bridge concept, including bank-provided aliases; transitive closure | 31 / 20 / 49 | 1,100 |
| Chain intermediates | Depth, conditional flag and ordered operation kinds | 30 / 20 / 70 | 1,320 |
| Role-bound association | Explicit story-swap pair ID | 30 / 20 / 50 | 11,400 |

Total: **469 items and 19,435 official cells**. Chain's cache contains 33,000 rows, but only its maximum position per item/layer belongs to the official final-token contract. Role uses all 19 frozen summary suffix/tail sites and its six layers. The other grids follow PLAN.

The initial canonical-only MT grouping missed four aliases spanning splits. Before wider generation, `splits_v2` repaired alias closure, preserving every v1 development item as development and adding one sibling. V1 remains immutable; [the supersession record](../../configs/splits_supersession_v1.json) explains the revision. No held-out lens outputs were inspected. These historically studied banks measure generalization of this scaffold, not previously unseen research data.

The initial [eight-cell manifest](../../configs/splits_pilot_instrument_v1.json) remains historically exact. All eight IDs are still development in v2. The [shared pilot](../../configs/splits_pilot_shared_v2.json) freezes 189 cells in 31 complete development-group items: hall 8/72, MT 8/24, chain 7/21, role 8/72 (items/cells). It includes the original eight cells. Layers 20/44/60 and first/middle/last frozen sites were chosen by a deterministic rule without readout or judge quality. All runnable methods use this same partial grid.

## Activation and control provenance

Cached tensors are BF16, width 5120, but their metadata lacks full model/tokenizer revisions, rendered-input hashes and explicit adapter state. The model worker's adapter-free recapture found cosine agreement approximately 0.999885–0.999977 and relative Euclidean error 0.00747–0.01592. This is close, not exact compatibility. The coordinator chose fresh capture for all core cells; immutable cell IDs permit rebinding v2 split metadata without repeating capture.

Shared durable manifests:

- `${OLENS_DATA_ROOT}/manifests/core-capture-v2.json`: rendering inputs restricted to capture, never selector/editor context.
- `development-matched-controls-v2.json` in the same directory: eight deterministic development controls per target where possible, matching family/layer/read-position kind and excluding the target's related group. Hall has 185 target cells below eight controls; no validation/test fallback. Controls can share source groups, so eight controls are not eight independent observations.

Candidate generation sees each cell's activation. Selection/editing gets candidates and permitted activation scores; evaluation alone uses labels/transcripts. Control selection never uses gold correctness or judge verdicts.

## Evaluation and financial checks

[evaluation.py](../../src/olens_improve/evaluation.py) converts sample index 0 to one `samples` string per official row. It imports upstream prompts, parsers and aggregation rather than rewriting them. MT uses the deterministic regex scorer with zero API calls. Chain uses blind top-ranked numerical recovery. Role asks three choices in **one request per cell**, not three requests. A fully nonempty core arm entails 23,950 logical judged requests (11,230 hall across both stages, 1,320 chain, 11,400 role), plus preflight/retries. Empty or missing cells remain explicitly counted.

Luna is `gpt-6-luna`, effort `none`, Flex for this pilot. Upstream Gemini pin/completeness fields are preserved; the project contract declares the Luna override and partial-cell status. Hall's headline is unrevoked wrong/specific readouts, accompanied by assertion share and off-topic rate. Its secondary wrong/(wrong+consistent) diagnostic is separate. Claim verification coverage was 1/1. False tallies count established spans; they cannot be combined with true/unverifiable claims as uniform atomic precision. Main comparisons additionally require the prescribed grid and complete produced-output verification.

[budget.py](../../src/olens_improve/budget.py) reserves worst-case Standard-priced text/schema input plus maximum output **before every physical request**, with SDK retries disabled. It settles usage before JSON parsing, retains timeout/unknown charges, and halts every worker after a bound overrun. SQLite uses `DELETE` journals and `BEGIN IMMEDIATE`, not WAL. Nine offline tests pass, including two-process oversubscription, timeout retention, billed malformed output, frozen run caps and sticky halt. The coordinator also ran these tests on actual Pattie NFS storage before enabling the $1 tiny-run cap. Forecasts, actual usage-priced spending and reservations remain separate.

## Development trace inspection

All eight produced cells were inspected; no wins/regressions against a proposed method exist yet. Representative baseline mechanisms:

- `chat-lmsys-0023`, L44/p464: the readout claimed a transformer's “global pooling” and a “DETR-TS” variant. Both spans were marked contradictory. Stage 2 tallied four true claims, one unverifiable claim and two established false spans. The raw output repeated small-object limitations and ended with fragments.
- `chain-d2p-0271`, L44: the correct intermediate 11 appeared, but other arithmetic crowded it out. The judge ranked 3 first and 11 second: top-1 failed, the any-of-three diagnostic hit. This motivates a selection/pruning test, not a claim that pruning will work.
- Both `oa-comedian-heckler-humiliate` directions, L44: generic restaurant stories supported the action “humiliated” but not the listed named agent/patient. Both failed complete role binding.
- The paired Simula bridge group had one regex hit and one miss. Exact trace and match evidence remain in the durable MT result; this isolated recovery is not a population estimate.

Cell-level diagnostic values: hall 1/1 contradictory; MT 1/2 recovered; chain 0/3 top-1; role 0/2 complete bindings. Treating these as official full-grid item scores would be misleading. No confidence interval on this tiny set can establish general robustness.

## Artifacts, reproduction and next action

Generation: `${OLENS_COMPUTE_ROOT}/runs/instrument_n2_v1/candidates.jsonl` (16 persisted samples). Evaluated raw baseline and judge evidence: `${OLENS_DATA_ROOT}/runs/instrument-n1-v1/`, including per-family readouts/results/contracts, manifest and summary. Shared budget: `${OLENS_DATA_ROOT}/budget/ledger.sqlite3` (physical request content hashes, prompts/schema, request/response IDs, latency, usage and raw responses). No secrets or large artifacts entered Git.

Reproduce metadata with `python scripts/prepare_data.py`; tests with `PYTHONPATH=src python -m unittest discover -s tests -p test_budget.py`. Runtime interpreter and dependency versions are in `configs/runtime.json`. Capture/generation GPU job accounting is owned by the model experiment record; this experiment added CPU metadata work and judging, not GPU inference. Code remains local/uncommitted at this record's creation; final commit/dirty-source hashes belong in the parent run manifest.

Next: fresh activations, shared 189-cell baseline/pool comparisons, deterministic capped N=1 and same-pool best-of-N, then independent quality evaluation. The instrument's failures are useful test cases, not reasons to reject the project.

| UTC | Split | Inspection | Purpose / decision |
|---|---|---|---|
| 2026-10-10, initial execution | Development instrument v1; still DEV in v2 | All eight sample-0 readouts and their judge/regex traces | Instrument validation and failure mechanisms; no method tuning on validation/test |
| 2026-10-10 | Source banks only | Grouping metadata and bank-provided bridge aliases | Repair alias leakage; preserve observed development cohort |

Validation and test outputs have not been generated/inspected by this worker. Their access remains sealed until the planned freeze.
