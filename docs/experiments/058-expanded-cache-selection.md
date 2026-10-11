# 058: Expanded cached selection and finite menu

## Key findings for a new reader

The first expansion tranche has complete generated outputs for 39 conditions on all four banks: 469 questions and 19,435 activation sites. Selection coverage and judged coverage are separate: the first native analysis contains 128 terminal condition-family results, while 152 remain missing. Original results and sampled readouts remain unchanged. The remaining thirteen CPU combinations are running; semantic support, editing and likelihood conditions belong to their parallel services.

## Status and question

- **Status:** cached projection complete; corrected eight-worker production running with committed progress and no errors; first source-checked partial native analysis complete.
- **Created / updated (UTC):** 2026-10-11 00:54.
- **Run IDs:** `expansion-v1`, CPU Slurm allocation `25536417`, node `node1623`, sixteen physical cores, 80 GiB, expires 2026-10-11 12:18:55 UTC.
- **Question:** How do all distinct usable recorded inference-time settings compare on the complete existing four-family bank?
- **Expected failure mode:** selection score or shorter outputs can improve without factual recovery; semantic merges, incompatible pooled details and invalid scoring atoms can obscure that failure.
- **Decision rule:** retain weak and adverse functioning variants; complete the finite menu or disclose the exact unresolved prerequisite. No score-driven shortlist or tuning on expansion outcomes.

## Frozen inputs and procedure

- Exact sealed inventory: [`configs/expansion_manifest_v1.json`](../../configs/expansion_manifest_v1.json), SHA256 `753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8`.
- Readable menu: [`docs/EXPANSION_MENU_V1.md`](../EXPANSION_MENU_V1.md). Seventy active named conditions; six cached released80 numerical diagnostics, six obsolete malformed-semantic-v4 diagnostics and one proven zero-support-coefficient alias are explicit.
- `exact_support_only` and `consensus_exact_support0` retain named component/control representations whose historical outputs coincide; they do not count as independent algorithms. Reconstruction-eligible N1 remains distinct from deterministic capped N1.
- Source menus: original signed 24-condition development menu, `reporting_pilot_v2`, and the forty original computed selector conditions. Zero-loss and coefficient controls are individually listed before execution. No unrestricted parameter cross-product.
- Model, adapter, reconstruction, whitening, parser and original N32 samples remain frozen. The reconstructor reads the first 32 cleaned tokens per bullet. Output caps remain four verbatim source bullets and 256 Qwen tokens; the historical raw released reference retains its original exemption.
- Source selector paths/hashes, stage cohorts, fixed controls, exact parents and named baseline/component/deletion contrasts are included in the seal. First-two likelihood donors are frozen in `configs/expansion_likelihood_controls_v1.json`.
- All 469 questions were previously inspected: the entire expansion is exploratory. Independent readers and added pooling length-matching are postponed/excluded.

## Comparisons and measurements

The cached tranche is 34 recorded full-bank selector outputs, four existing specificity/pruning outputs at .001/.005 and their matched deletions, and one derived nonpositive-specificity abstention condition. Projection copied the historical outputs and preserved every scientific source. The abstention comparator uses the original selected mean specificity score and exactly the previously recorded zero threshold.

The thirteen remaining CPU outputs are exact support at 0/.125/.25; its named support-only comparator; support-plus-pooling at .05/.2; pooling followed by pruning at .001/.005 and matched deletion; specificity pooling, followed by .005 pruning and matched deletion. Exact N16 pooling is reproduced as a component-off check before support-weighted selection.

| Family | Questions | Activation sites | Cached conditions produced |
|---|---:|---:|---:|
| Hallucination | 149 | 5,615 | 39 |
| Hidden-name multi-hop | 100 | 1,100 | 39 |
| Arithmetic chain | 120 | 1,320 | 39 |
| Role binding | 100 | 11,400 | 39 |

The partial analysis artifact below preserves measured quality, pointwise paired intervals and hallucination assertion/off-topic coverage. Full-menu simultaneous intervals and independent reader disagreements remain unavailable. Output length is preserved in every exported record. Native task endpoints remain separate.

## Completeness, cost and artifacts

- Cached outputs and source-hash verification receipts: `${OLENS_DATA_ROOT}/expansion-v1/selections/cached-v2/`. Every family has a compact JSONL, complete family manifest and `.ready.json` descriptor with exact hashes and conditions. API service owns paid forecasts and judges.
- Full cached source verification includes three complete selector journals and three complete specificity/pruning journals. Source inputs total exactly 19,435 distinct cells.
- Cached-v1 encountered duplicated unchanged-parent diagnostic metadata before any output row was emitted. V2 keeps authoritative parent metadata from the original selector and only imports the four derived pruning conditions. The failed directory is preserved.
- Real combination smoke: two existing cached cells, thirteen conditions each. Exact N16 parent text, phrase identities and fraction of variance explained (FVE) reproduced within the existing numerical tolerance; output caps and matched frozen donor identities passed. Approximately ten seconds per cell in this tiny check is **not a sustained production throughput estimate**.
- The first production attempt found DEV sources use atomic `records` envelopes while the tiny check had only exercised TEST flat snapshots. All four workers stopped before any scientific output. Source data remain unchanged. The corrected reader streams both representations, and the new instrument check explicitly requires one original DEV, VAL and TEST cell. The failed `combinations-v1` directories remain available.
- Corrected CPU production writes `${OLENS_DATA_ROOT}/expansion-v1/selections/combinations-v2/shard-{0,...,7}/`; final checked family exports appear under `merged/`. Whole items are assigned to deterministic shards, with all original reading sites intact. Additional sixteen-core/80 GiB CPU job `25536927` was requested with root authorization. At 00:53 UTC the eight workers had committed 8,186/19,435 cells, with no errors. The earlier ten-second cold-cell check included a new-layer whitening eigendecomposition; warm last-fifty-cell medians were approximately 0.99–1.45 seconds, substantially reducing the provisional fourteen-hour estimate. This is observed throughput, not a completion guarantee.
- Persistent launcher/observer PID and current workers are recorded in `.state/expanded-cpu-v1.service.json`. Workers request disjoint Slurm steps, four physical cores and 20 GiB each; Torch has four threads and OpenBLAS one. A lightweight local service checks progress every thirty seconds. Root's separate monitor checks the allocation.
- Journals commit whole cells with flush/fsync. A partial final line is truncated on resume; changed code/spec or inventory hashes reject resumed output. Complete family exports require validated terminal shard hashes and exact cohort/cap checks.
- New API/model calls in this CPU stream: zero. Generation and numerical scoring are reused. Inference cost on a fresh input remains separately reported.
- Source files: `scripts/seal_expansion_manifest.py`, `expanded_cpu_cached.py`, `expanded_cpu_combinations.py`, `expanded_cpu_service.py`, `expanded_cpu_merge.py`. No dependency installation or Git write occurred.

## Numerical replay and first native analysis

The independent numerical replay receipt, `${OLENS_DATA_ROOT}/expansion-v1/receipts/cpu-numeric-review-v1.json`, passed one original DEV, VAL and TEST cell. Reconstruction-selected A32 and mean-specificity E32 text and phrase identities match exactly. The largest own-FVE difference is 1.85e-11, mean-control FVE difference 1.47e-12, max-control FVE difference zero, and specificity difference 1.85e-11 under single-thread Torch/OpenBLAS. This establishes three actual source fixtures, rather than claiming exhaustive floating-point identity across the bank.

`scripts/analyze_expansion.py` and four native-contract fixtures independently check question-grid ANY recovery, same-site multi-hop hits, both hallucination stages and exact pilot site filtering. The first allocated-CPU artifact is `${OLENS_DATA_ROOT}/expansion-v1/analysis/first-live-v1.json`, SHA256 `1e2de7c6bf67507b84dac0cfb19dc7743a51396ba507dd49322e06508525dfe1`. It contains 128 terminal condition-family rows and 174 available paired comparisons in each named cohort, with 152 condition-family prerequisites still missing. Native counts aggregate original question rows, not stage percentages. The frozen simultaneous family remains 496 contrasts; all simultaneous intervals are null in this partial artifact. Pilot recovery retains its per-activation endpoint. All cohorts remain exploratory.

Extraction pinned 546 source files totaling 1,077,343,722 bytes. Runtime was 55.8 seconds with maximum RSS 1,060,604 KiB on an allocated API-service CPU; only text and two length fields are retained from each selection. Six statistical fixtures and four extraction fixtures passed. The source report includes prior named conditions and preserves the official score alongside secondary coverage counts; substantive method findings are deferred to the shared report.

## Inspection evidence and interpretation

The real-cell check verifies implementation/provenance rather than method quality. No new wins/regressions have been selected or synthesized. Fixed outcome-blind anchors and clearly labeled changed cases will be audited after official judgments, preserving the official score alongside any disagreement.

## Validation and test access ledger

| Timestamp | Split / manifest | Process | Outputs inspected | Purpose / resulting decision |
|---|---|---|---|---|
| 2026-10-11 00:18–00:22 UTC | Original DEV/VAL/TEST selectors under sealed expansion menu | CPU cached projection | All source text/counts, identities and caps; no new verdicts | Exact full-bank projection and zero-Q comparator; no threshold changes |
| 2026-10-11 00:22–00:24 UTC | Two original cached cells | CPU combination smoke | Source text/identities and reconstruction fits | Validate D16 reproduction and fixed controls; start unchanged finite menu |
| 2026-10-11 00:28 UTC | One original cell in each DEV/VAL/TEST representation | Corrected CPU combination instrument | All thirteen derived conditions and recorded D16/D32 parent fits | Validate envelope and flat source readers before eight-worker production |
| 2026-10-11 00:52–00:54 UTC | One original DEV/VAL/TEST cell | Independent A32/E32 replay | Text, phrase identities, own/control FVE and specificity | Verify thread-setting numerical equivalence on actual source fixtures |
| 2026-10-11 00:53–00:54 UTC | Terminal expanded-family judgments only | Native source extractor | Original row counts, grid identities, official text and endpoint reproduction | Emit clearly partial exploratory report; no simultaneous intervals or new tuning |
