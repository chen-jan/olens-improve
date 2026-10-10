# Execution status

Updated: 2026-10-10, approximately 07:49 UTC.
Started: 2026-10-10 01:25:36 UTC (October 9, 21:25:36 EDT).
Target finish: 2026-10-10 21:25:36 UTC. Execution remains active and authorized.

## Findings so far

No general improvement in explanation faithfulness is established yet. The
**5,236-cell development comparison of best-of-32 against capped N1 is complete**:
contradicted readouts change from 543/1,137 to 523/1,140, a −1.88 percentage-point
change with a paired group interval of [−5.41, +1.76]. Bridge, chain and role
cell recovery increase from 29→43, 26→30 and 151→182, respectively. Item-level
role recovery remains 23/30. The flagged false-span tally rises from 1,305 to
1,324 despite fewer wrong readouts; inspected recovered concepts still occur
inside incorrect explanations. See [the report](REPORT.md) and experiment 019.

The remaining findings below come from the **189-cell development pilot** unless
explicitly labeled otherwise. It contains only 2–8 independent groups per family.
Other complete-grid method comparisons remain partly unfinished.

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
- Strict whole-bullet consensus removes most coverage. The repaired pipeline
  completed every requested pair label, but a fresh stratified 40-pair audit
  still found five clear false equivalences. Four affected actual clusters.
  This audit is not a population error estimate; semantic variants remain
  diagnostic. Exact-repeat support plus pooling produced no recovery gain.
- A bounded helper-effort audit rechecked the same 40 semantic pairs with Luna
  reasoning enabled. It rejected all five previously flagged equivalences, but
  also rejected two valid matches. This selected audit is not an accuracy
  estimate. Confirmation on the existing 189-cell pair list is now judged and
  does not establish better selected outputs. Strict filtering still removes
  most coverage. The benchmark judge remains Luna with reasoning disabled.
- Contrastive selection followed by pruning is a promising combination for
  larger measurement, with unchanged bridge recovery and three additional role
  cell passes in the pilot. Inspected role gains are judge-sensitive; the
  retained texts still contain conflicting roles or names. They do not yet
  establish improved relationship faithfulness.
- Contrastive reconstruction is sensitive to layer and wording. The likelihood
  comparison is mixed. J++ token ranks cannot verify reversed relationships and
  have unresolved fitting-data overlap, so remain development diagnostics.
- A repeated Luna audit changed wrongness on 2/10 seeded random A32 readouts
  covering six items. Originals used Flex and repeats used Standard; this does
  not isolate a within-tier effect or establish which label is correct. Primary
  verdicts remain unchanged. See experiment 011 on judge repeatability.
- All32 candidate judgments reveal missed opportunities: bridge mentions appear
  in at least one candidate in 14/24 cells, while reconstruction selection
  recovers them in 7/24. This is an evaluation-only availability ceiling; some
  passing candidates still contain incorrect surrounding claims.
- Matched unrelated donor activations reduce flagged hallucinations from
  543/1,137 to 25/992 specific outputs, but 956/1,145 donor outputs are off-topic
  and only 11 are consistent, versus 446 for the actual activations. An error
  rate without useful coverage would misleadingly reward this control.

Reviewed sources and paired examples are in the experiment records and
[local dashboard](../dashboard/index.html). Local commit `f62adb6` contains the
first source-checked dashboard with grouped intervals. Nothing has been pushed.

## Current work

| Work | State |
|---|---|
| Model, adapter, matching AR and whitening | Source reproduction passed; exact NNLS is primary |
| Activations and splits | All 19,435 core cells freshly captured; grouped split v2 frozen |
| Shared pilot | 189 cells × 32 samples complete and immutable |
| Full development collection | All 5,236 cells × 32 samples frozen; 167,552 samples |
| Full development reconstruction | Complete: 642,209 unique vectors covering all 5,236 cells |
| Full development selectors | Complete: 5,236 cells and 40 offline conditions; all 2,018 overlapping v3 rows agree exactly; raw/capped baseline identity passed |
| Full development baseline | Raw and capped N1 judged, all stages/cells complete; pinned item aggregation verified |
| Single-method pilots | A/B/C/D/E1/E3/F judged; E2/G diagnostics complete with limits; exact-claim-span v3 stopped after its eight-cell contract audit, without benchmark-quality measurement |
| Combinations | 65 unique pilot conditions judged and source-checked; larger E1-plus-pruning outputs complete and awaiting judging |
| Additional controls | All32 judgments and matched-donor N1 complete; all requested cells/stages covered |
| Held-out evaluation | Blind fixed-pool validation generation is running on all four main GPUs; analysis remains closed until the DEV shortlist is frozen. Test remains closed. |

Combination comparisons retain unchanged parents, component-off outputs, and
random deletion matched on retained bullet count. Fixed support weights are
tested on the same N16 pool without semantic merging. Costs distinguish the
shared research campaign, rerunning a selector from cache, and inference on a
new activation. Quality has priority; extra cost must still be visible.

The larger capped N1 baseline has 543/1,137 contradicted specific readouts;
bridge recovery on 11/31 items, chain recovery on 15/30, and role passes on 23/30.
The corresponding role cell count is only 151/3,420: an item passes when any
inspected site passes, so item recovery must not be read as uniformly faithful
readouts. These are original-grid development scores, not held-out results.

Next: profile local accounting/cache time and event-loop responsiveness on a
disposable ledger before another paid recovery. The indexed queue initially
completed thousands of requests at eight slots/200 requests per minute without
errors. After two families increased to sixteen slots/400 RPM at clean condition
boundaries, throughput fell and connection failures accumulated. The shared
transport guard stopped all workers. The 07:02 recovery epoch retained 6,414
settled responses and 48 uncertain holds, including 26 shutdown cancellations;
no live reservations remain. Memory headroom was ample and no new SQLite-lock
error was found. The cause remains unresolved. Exact-request cost
forecast and compact export are complete; the forecast is $10.19 and the shared
run ceiling remains $20. At the latest transport pause, all 24 multihop conditions,
21 chain conditions, four hallucination conditions and three role conditions
were complete. Unfinished conditions remain incomplete. The
merged selection SHA is `54ee50e61ebc11ac66d8d11c294dda60e17a7f9e06ad8632665e6bbb6505635e`;
the baseline audit verifies all 10,472 raw/capped text-and-token pairs against
the already judged baseline. Cache reuse does not create independent verdicts.
The E1 pruning run used 235.75 seconds on four CPU threads, with no new model
calls. Repaired consensus and pooling-plus-specificity pilots are judged.
The repaired source-span diagnostic stopped after eight cells: numeric-only
fragments were removed, but two accepted claims still depended on an unidentified
paragraph. This failed the strict self-contained-claim contract; it does not
establish that those statements are false or that claim consensus cannot work.
The proposed 32-cell expansion remains incomplete. Review development outcomes before the validation
shortlist, freeze, and test. A small gain with wide
intervals can warrant follow-up; significance alone is not an expansion gate.

The full development audit found 523 bullets empty after AR token cleanup in
103 role cells. Complete-candidate AR methods exclude unscoreable samples;
raw/capped/random controls preserve their text, and N1 pruning leaves such
parents unchanged. Twelve A1 cells abstain where capped N1 retains text (two
parser exclusions and ten unscoreable parents). Report these eligibility
differences separately from selection gains; the fix is not a faithfulness result.

A local vector-first CLI now supports immutable candidate generation and replay.
One existing DEV A16 replay reproduced the exact output and phrase IDs with FVE
drift 1.34e-8, without generation, GPU work or API calls. This is replay validation;
the complete fresh-install deployment path has not yet been tested.

## Resources and limits

- Four main H200 allocations: 25330001, 25330006, 25330007, 25417596.
- Both extra H200 allocations, 25460532 and 25459615, were intentionally
  released after their encoding and diagnostic work completed. Four main
  allocations remain available for the next scientifically authorized stage.
- Fresh CPU allocation 25474685 provides eight physical cores and 32 GiB for
  judging through 21:25:37 UTC. The old allocation 25299630 reached its memory
  limit, predominantly in its external step; unrelated processes are preserved.
  Its existing lightweight watcher remains active and monitors the new allocation.
  A watcher checks every 600 seconds until 21:25:36 UTC; its process and last
  check are recorded under the fast project's `watcher/` directory. An agent
  stopping does not itself guarantee that this process remains healthy.
- Recorded API usage at approximately 07:34 UTC: **$6.07486**, with **$4.58690**
  unknown-charge holds and no in-flight reservations. The ledger remains
  authoritative as work resumes.
  The earlier cache-write pricing correction added $0.30592
  to settled usage and $0.02011 to unknown-request reservations; original events
  and the previous ledger snapshot are preserved. These are usage-based estimates,
  not reconciled invoice charges. Target $200; hard ceiling $300 including reservations.
- Shared O-lens cap: 32 samples/cell across all methods. Editing has its separate
  two-round/eight-proposal cap. No training or new activation sites.
- Project artifacts used approximately 26.72 GB logical at 04:45 UTC.
  The existing 55.56 GB base cache is reused without copying. Aggregate
  project allowance is approximately 500 GB; lab group quota remains unresolved.

The full-development judge queue later developed 21 connection failures and
21 cancellations during guard shutdown. All 42 uncertain holds remain reserved;
successful cached verdicts are preserved. The cause is unresolved: observed
CPU cgroup pressure and failure timing do not establish causation. A single
unchanged Luna request on the isolated CPU allocation succeeded in 2.29 seconds.
Recovery was authorized at eight slots and 200 requests/minute per family with a
new documented epoch, the same run cap, and all old holds retained. See experiment
019 and the immutable incident snapshot. No concurrency increase is automatic.

That fresh-CPU recovery settled its first 226 requests without transport errors,
then stalled. Workers were observed waiting on disk, and the chain worker exited
with a database-lock error. All three were gone by 06:49:52 UTC. Ten reservations
belonging to dead workers had no saved response evidence and must remain held as
unknown; no charge is released because a worker exits. A copied-ledger audit found
unindexed request-origin and reservation queries. Five indexes preserve exact
query results and accounting; the slowest measured local-copy lookup fell from
152.05 ms to 0.0116 ms. This does not establish NFS write/locking performance;
a bounded shared-storage check subsequently passed 30 accounting cycles across
three workers without lock errors. Production indexes were applied at 07:00 UTC
after an immutable backup. Accounting remained identical; ten abandoned requests
were separately marked unknown while retaining their full holds. The successful
07:01 health request supports the bounded recovery launched at 07:07, but sustained
throughput remains to be measured. See experiment 023 and the indexed recovery
specification `configs/judging_main_recovery_v2.json`.

Earlier, the donor judge run developed connection failures without provider status codes.
It was stopped, preserving cached successes and uncertain reservations. A
single-request check succeeded; an eight-slot restart with a shared transport
failure guard completed 2,110 physical requests without another transport
failure. The four subsequent diagnostic batches also completed without new
unknown requests. The original cause remains unresolved. No unknown charge was released.
Automatic approval review initially rejected the check/restart for missing
authorization context; root's exact-scope submissions with the existing user
authorization succeeded. This did not expand the model, endpoint, or data scope.

Generation measured roughly 4.2 GPU-seconds/cell at N32. Streaming reconstruction
measured about 98 new phrase vectors/s. These are batched task timings, not
single-request latency or a complete experiment forecast. The earlier overall
forecast was another 10–14 hours from approximately 02:40 UTC; reassess after the
full-grid judge throughput measurement. Standard judging now supports explicit
concurrency/rate limits; a bounded 32-slot/600 logical calls-per-minute pilot
completed without new unknown reservations. This is per family, not a promise
of provider capacity.

Blind preparation of the fixed validation pool can overlap development judging:
3,485 cells at N32 has a measured-component generation reference of about 63
minutes on four GPUs, plus loading and overhead. This is not a complete evaluation
forecast. Only operational counts, hashes, and timing may be inspected before
the development shortlist is frozen. A separate analysis gate is required for
validation export, reconstruction, selection, judging, and example inspection.
Test generation remains gated on the later validation decision.
All four generation workers are active. At 07:02 UTC, 1,167/3,485 cells were
complete. The observed rate of about 56 cells/minute suggests about 42 minutes
of generation remained then, excluding reconstruction, selectors and judging.

## Recovery and artifact map

Read [PLAN.md](PLAN.md), [METHODS.md](METHODS.md), and the latest experiment
records before continuing. Preserve the historical `mats/workspace` checkout.

- Fast models, environment, vectors, activations and watcher:
  `${OLENS_COMPUTE_ROOT}`.
- Durable stochastic text, judgments, analyses and budget ledger:
  `${OLENS_DATA_ROOT}`.
- Pilot: `runs/development-shared-pilot-v2`. Its original 22 authoritative arms
  use `judgments-standard-repair`; E3 uses `judgments`; B uses `judgments-b-v4`;
  editing uses `judgments-editing`; combinations use `judgments-combinations`;
  exact-support pooling uses `judgments-support-pooling`.
  Report exact condition roots and selection hashes, not a directory glob.
- Full development: immutable `runs/development-full-grid-v2`, baseline
  judgments in its `judgments-baselines` directory. Selector comparisons are
  pending. A parallel AR-cache extension preserved all keys and inherited
  vectors in a four-cell real fixture, with no changed best-of-32 winner.
  Its expanded 12-cell batch-size audit exceeded both provisional equivalence
  guards: maximum FVE drift .003524, with 0/12 best-of-32 winners, 2/12 pooled
  texts and 1/12 specificity-selected texts changing. Fixed B128 is accepted as
  a declared implementation, not as numerically equivalent to B32. All method
  arms share the same persisted vectors, batch/partition provenance is retained,
  and near-threshold decisions remain explicitly sensitive. Production is unchanged;
  validation/test access still requires a separate scientific stage gate.
- API ledger: `budget/ledger.sqlite3`. Retain the unknown $2 Claude review
  reservation and 80 unknown Flex attempts unless billing evidence resolves them.
- Runtime/allocation details: `configs/runtime.json`. Verify live state before
  restarting workers. Do not launch a second writer against the same AR cache or
  family judge cache.

Preserve completed samples, responses, manifests and reservations. Do not rerun
paid calls merely because their output exists in a different condition. Make
local reviewed commits; the user handles pushing. Finish the planned research
and report honestly rather than marking an unrun or time-limited method negative.
