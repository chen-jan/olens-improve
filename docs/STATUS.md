# Execution status

Updated: 2026-10-10, approximately 03:45 UTC.
Started: 2026-10-10 01:25:36 UTC (October 9, 21:25:36 EDT).
Target finish: 2026-10-10 21:25:36 UTC. Execution remains active and authorized.

## Findings so far

No general improvement in explanation faithfulness is established yet. These
results use a shared **189-cell development pilot**, with only 2–8 independent
groups per family. They are partial-grid diagnostics, not final benchmark scores.

- Selecting the best reconstruction from more samples reliably raises the
  reconstruction score. Quality moves differently across tasks. Best-of-32 has
  39 contradicted readouts among 71 specific outputs, compared with 46/71 for
  capped N1; a single random draw from N32 has 38/72. Larger measurement is needed.
- Pooling bullets raises reconstruction further. It recovers bridge mentions in
  10/24 cells versus 7/24 for best-of-32, but chain intermediates in only 1/21
  versus 3/21. Inspected names and numbers sometimes appear inside incorrect
  relationships or calculations. Mention recovery is not full correctness.
- Two editing rounds did not improve those recovery counts or reduce the 42
  contradicted pooling outputs. Most accepted edits cleaned formatting; two
  violated preservation instructions. These are risks, not proof that every
  changed detail is false.
- Strict whole-bullet consensus removes most coverage. The first semantic
  pipeline also had unsafe merges and many malformed responses. A simpler
  response-format rerun is authorized; the initial result is not a clean negative
  result for consensus as a method.
- Contrastive reconstruction is sensitive to layer and wording. The likelihood
  comparison is mixed. J++ token ranks cannot verify reversed relationships and
  have unresolved fitting-data overlap, so remain development diagnostics.
- A repeated Luna audit changed wrongness on 2/10 seeded random A32 readouts
  covering six items. Originals used Flex and repeats used Standard; this does
  not isolate a within-tier effect or establish which label is correct. Primary
  verdicts remain unchanged. See experiment 011 on judge repeatability.

Reviewed sources and paired examples are in the experiment records and
[local dashboard](../dashboard/index.html). Local commit `f62adb6` contains the
first source-checked dashboard with grouped intervals. Nothing has been pushed.

## Current work

| Work | State |
|---|---|
| Model, adapter, matching AR and whitening | Source reproduction passed; exact NNLS is primary |
| Activations and splits | All 19,435 core cells freshly captured; grouped split v2 frozen |
| Shared pilot | 189 cells × 32 samples complete and immutable |
| Full development collection | Approximately 4,959/5,236 cells complete at 03:43 UTC |
| Full development reconstruction | One streaming writer; first 2,079-cell snapshot complete, remainder running |
| Single-method pilots | A/C/D/E1/E3/F judged; B repair and interpretation ongoing; E2/G diagnostics complete with limits |
| Combinations | Pruning after pooling/contrastive selection/editing now judging; exact-repeat support plus pooling running |
| Held-out evaluation | Validation and test readouts remain sealed |

Combination comparisons retain unchanged parents, component-off outputs, and
random deletion matched on retained bullet count. Fixed support weights are
tested on the same N16 pool without semantic merging. Costs distinguish the
shared research campaign, rerunning a selector from cache, and inference on a
new activation. Quality has priority; extra cost must still be visible.

Next: finish development journals and preserve immutable snapshots; export
raw/capped N1 for judging while reconstruction finishes; run four independent
CPU selection shards and validate their merge. Review full development outcomes
before the validation shortlist, freeze, and test. A small gain with wide
intervals can warrant follow-up; significance alone is not an expansion gate.

## Resources and limits

- Four main H200 allocations: 25330001, 25330006, 25330007, 25417596.
- Streaming AR: extra H200 allocation 25460532. Diagnostic allocation 25459615
  was intentionally released after completing its tasks.
- CPU allocation 25299630 runs lightweight judging, selection and monitoring.
  A watcher checks every 600 seconds until 21:25:36 UTC; its process and last
  check are recorded under the fast project's `watcher/` directory. An agent
  stopping does not itself guarantee that this process remains healthy.
- Observed API usage at approximately 03:44 UTC: **$0.695**, with **$2.40045**
  unresolved reservations. The ledger is authoritative, including retries and
  malformed responses. Target $200; hard ceiling $300 including reservations.
- Shared O-lens cap: 32 samples/cell across all methods. Editing has its separate
  two-round/eight-proposal cap. No training or new activation sites.
- Project artifacts used approximately 17.2 GB logical / 16.7 GB allocated at
  03:35 UTC. The existing 55.56 GB base cache is reused without copying. Aggregate
  project allowance is approximately 500 GB; lab group quota remains unresolved.

Generation measured roughly 4.2 GPU-seconds/cell at N32. Streaming reconstruction
measured about 98 new phrase vectors/s. These are batched task timings, not
single-request latency or a complete experiment forecast. The earlier overall
forecast was another 10–14 hours from approximately 02:40 UTC; reassess after the
full-grid judge throughput measurement. Standard judging now supports explicit
concurrency/rate limits; a bounded 32-slot/600 logical calls-per-minute pilot
completed without new unknown reservations. This is per family, not a promise
of provider capacity.

## Recovery and artifact map

Read [PLAN.md](PLAN.md), [METHODS.md](METHODS.md), and the latest experiment
records before continuing. Preserve the historical `mats/workspace` checkout.

- Fast models, environment, vectors, activations and watcher:
  `${OLENS_COMPUTE_ROOT}`.
- Durable stochastic text, judgments, analyses and budget ledger:
  `${OLENS_DATA_ROOT}`.
- Pilot: `runs/development-shared-pilot-v2`. Its original 22 authoritative arms
  use `judgments-standard-repair`; E3 uses `judgments`; B uses `judgments-b-v4`;
  editing uses `judgments-editing`; combinations use `judgments-combinations`.
  Report exact condition roots and selection hashes, not a directory glob.
- API ledger: `budget/ledger.sqlite3`. Retain the unknown $2 Claude review
  reservation and 80 unknown Flex attempts unless billing evidence resolves them.
- Runtime/allocation details: `configs/runtime.json`. Verify live state before
  restarting workers. Do not launch a second writer against the same AR cache or
  family judge cache.

Preserve completed samples, responses, manifests and reservations. Do not rerun
paid calls merely because their output exists in a different condition. Make
local reviewed commits; the user handles pushing. Finish the planned research
and report honestly rather than marking an unrun or time-limited method negative.
