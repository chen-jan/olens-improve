# 023 — Donor-judge connection failures and bounded recovery

Updated: 2026-10-10 08:14 UTC. Status: donor recovery completed; the same main-comparison queue has resumed with optional operational timing after a third transport incident. Original uncertain charges and successful verdicts are retained. Benchmark prompts, Luna effort none, Standard destination and source text remain unchanged.

The full-development donor run began at 32 request slots and 600 rpm per family. Between 04:33:14 and 04:44:30 UTC it recorded 270 `APIConnectionError` attempts and 43 cancelled attempts when the active workers were stopped. Their 313 unresolved charges retain **$1.6103545**. Median failed latency was 24.4 seconds. Errors carried no HTTP status or provider error code; underlying cause classes were not recorded by that earlier wrapper. The outage cause is unknown. Failures began before the 04:40 CPU-selector launch, so concurrent CPU use does not establish the cause.

New dispatch was stopped with SIGINT to the two active family workers, allowing the wrapper to preserve uncertain reservations and successful cached verdicts. One exact unresolved-request healthcheck subsequently succeeded. It did not clear any old uncertain charge. A tested logging change now records only cause class names and numeric errno, excluding exception messages, URLs and credentials.

Recovery used **eight request slots and 200 rpm per family** and the existing $5 donor run ceiling. Its fixed epoch was 2026-10-10T04:50:43+00:00. The sharedSQLite pre-reservation gate stops this epoch if more than five of its latest 100 attempts become unknown or new unknown reservations exceed $0.10. Earlier unresolved holds remain financially reserved and excluded only from this recovery-health counter. The accounting ledger was not reset.

Recovery settled **2,110 physical requests with zero new unknown holds**. At the 1,725-response observation, latency median was 2.36 seconds and95th percentile 4.25 seconds. The intended first 100-response stability observation was overtaken during offline analysis; this is not a strictly capped 100-call throughput instrument. Eight slots remained fixed throughout recovery.

Final project coverage is **5,236/5,236 development cells**: hallucination 1,145 readouts with both stages complete; multi-hop 341, chain 330 and role-binding3,420. Missing API outputs are zero. Pinned upstream `complete:false` flags remain preserved because this uses a development bank subset; complete frozen-grid coverage is reported separately. Successful requests were reused through the exact cache. Original physical attempts, failed charges, all execution sidecars and verdicts remain in the shared ledger and `runs/development-full-grid-v2/judgments-donor/`.

A separate one-cell numerical repair completed the all-candidate diagnostic: candidate index 29 now has 21/21 chain judgments, with one new paid request and twenty cached verdicts. Its primary text and original condition were unchanged. Implementation: `evaluation.safe_exception_chain`, the optional recovery guard in `AtomicBudget.reserve_attempt`, and recorded execution transport. Offline tests cover secrecy of diagnostics, old-versus-new epochs and shared stop thresholds. No validation/test access or model/helper substitutions occurred.

## Main-comparison bookkeeping stall and index repair

The main 24-condition comparison first paused at approximately 06:22 UTC with
42 unknown attempts. It resumed on the isolated CPU allocation `25474685`,
node1600, after a successful single request. That allocation had ample memory
headroom, but the resumed workers later stalled and all exited with code 1 by
06:49:52. The chain worker reported `sqlite3.OperationalError: database is
locked`. Hallucination and role workers intermittently slept in disk I/O, and
some physical request ages exceeded the nominal timeout. This is evidence of
a local bookkeeping problem; it does not establish the origin of every
connection error or prove a provider outage.

The second frozen incident records 239 settled, 12 unknown and ten abandoned
reserved attempts in the 06:32 recovery epoch. All three owning PIDs were
absent and none of the ten abandoned attempts had a retained physical response.
Their full **$0.053907125** must remain held as unknown, without invented usage
or a charge release. The entire main run had 4,791 settled attempts with
**$0.672596810** usage-accounted spend and 54 unknown attempts holding
**$0.267520875** before those ten status transitions. Financial ceilings were
not exhausted. The immutable evidence is
`durable/runs/development-full-grid-v2/judgments-methods-v1/transport-incident-v2.json`.

Source inspection found unindexed full scans in exact-verdict origin lookup,
latest physical-response lookup, committed-spend aggregation and recent-request
guard checks. Five indexes preserve the existing query and accounting semantics.
On an independent local-XFS snapshot, origin lookup fell from approximately
152 ms to 0.0116 ms, committed aggregation from 34 ms to 1.22 ms, and the latest
100-request lookup from 7.67 ms to 0.0304 ms; exact result hashes were unchanged.
That benchmark does not measure NFS journal or fsync latency.

A separate disposable NFS-copy smoke passed three processes × ten synthetic
reserve/response/settle/read cycles, with zero lock failures, all expected
origins and events, and unchanged historical held amounts. Total copy/index/
smoke wall time was 9.95 seconds; cycle median was 6.83 ms and 95th percentile
9.76 ms. It made zero API calls and its synthetic dollar entries exist only
in the disposable copy. Reports are under
`durable/diagnostics/ledger-query-profile-v2/` and
`durable/diagnostics/ledger-index-nfs-smoke-v1/`.

The reviewed application is `scripts/apply_budget_indexes.py` with
`configs/budget_index_application_v1.json`. It freezes an immutable prechange
ledger backup, verifies exact accounting and event identity after index DDL,
then separately reclassifies the ten approved abandoned reservations. The
committed amount must remain identical; only ten known unknown-status audit
events may be added. These offline checks support a bounded health request and
measured recovery, not a claim that production latency or all transport errors
are solved. Successful verdicts, original attempts and every uncertain hold
remain preserved.

The production application completed at 07:00:15 UTC. It preserved all financial
rows and 95,931 existing events exactly during index creation, then added only
the ten approved unknown-status events. Total committed funds remained
9,579,305,305 nanodollars across the project; no hold was released. A subsequent
one-request healthcheck succeeded in 1.590 seconds with 573 input and 37 output
tokens, zero reasoning tokens, and the same Luna/none/Standard request contract.
Its original uncertain request remains unknown. Application and health evidence
are `durable/diagnostics/ledger-index-application-v1/application.json` and
`judgments-methods-v1/healthcheck-indexed-v2.json`.

Root launched the same 24-condition queue using
`configs/judging_main_recovery_v2.json`, with reviewed epoch 07:02 UTC, eight
slots and 200 RPM per family. The first new physical attempt was at
**07:07:40.718 UTC**. At 07:10:18, the read-only checkpoint recorded **1,129
settled responses and zero new unknowns or recorded transport errors**. Median
physical latency was 1.62 seconds and the 95th percentile was 3.91 seconds;
aggregate wall throughput was 430 responses/minute. The oldest of sixteen live
requests was 4.50 seconds old. Family counts were 314 hallucination, 417 chain
and 398 role responses, so the per-family 500-response ramp gate was not yet
met. These are transport observations, not complete quality scores. No automatic
ramp is enabled; a reviewed increase to sixteen slots/400 RPM must occur at a
natural completed-condition boundary with sustained healthy family evidence.
Checkpoint source: `judgments-methods-v1/checkpoint-indexed-early-v1.json`;
reproducer: `scripts/observe_judge_queue.py`.

## Third incident after indexed recovery

At 07:14:41 the indexed eight-slot queue had 2,951 settled responses and zero new unknowns. Following reviewed 500-response family gates and clean condition boundaries, chain and role resumed at sixteen slots/400 RPM around 07:18–19; hallucination remained at eight. No in-flight work was cancelled merely to raise concurrency, and the reviewed 07:02 epoch stayed unchanged.

The larger setting did not show a throughput benefit in the measured window. At the 07:25 checkpoint, chain had 704 settled and five unknown attempts, approximately 117 responses/minute and p95 physical latency 10.69 seconds. Role had 568 settled and four unknown, approximately 89/minute and p95 15.80 seconds. Their earlier eight-slot checkpoint was approximately 155/minute with p95 2.90 seconds for chain and 143/minute with p95 3.40 seconds for role. These are different traffic windows and conditions, not a randomized concurrency experiment. Hallucination at eight also slowed. Local bookkeeping, NFS, client and provider effects remain under investigation; the comparison does not establish a cause.

The shared transport guard stopped all remaining workers before the requested boundary downshift could be delivered. No additional SIGUSR1 or hard kill was sent. Resource inspection confirmed those PIDs absent with ample fresh-allocation headroom. `scripts/record_judge_incident.py` froze `judgments-methods-v1/transport-incident-v3.json` at **07:32:54 UTC**, SHA256 `b8458e67c7f1e95565e2ccaacc7c442d02ed456647740b5fac01e1718598444b`.

Since the unchanged 07:02 epoch, **6,414 physical responses settled and 48 attempts remain unknown**, holding **$0.234553**: nine ReadError chains, thirteen ConnectError chains, and twenty-six guard-shutdown cancellations. Unknown counts are role16 22, chain16 25 and hall8 one. The entire main run has **11,206 settled attempts, $1.520503885 usage-accounted spend, 112 unknown holds totaling $0.555981, and zero still-reserved live attempts**. Usage accounting is not invoice reconciliation. The financial ceiling was not exhausted; shutdown cancellations remain charged-uncertain alongside the failed physical requests.

Successful exact verdicts, all original attempts and incomplete-condition sidecars remain intact. Missing API results cannot become successful abstentions. No new paid dispatch, new epoch or cache migration is authorized by this snapshot; a bounded diagnostic/recovery plan must be reviewed first. Offline A32-versus-capped-N1 analysis is complete independently of the unfinished queue and is documented in [experiment 019](019-full-dev-method-comparison.md).

## Copied-ledger instrument and profiled recovery

A bounded no-network instrument completed **384 synthetic calls**: three family
workers, 64 calls each, at both eight and sixteen slots. It used disposable
copies of the ledger and exact-verdict cache, three-second fake responses and
the existing request/accounting loop. Worker wall time was 25.35–26.35 seconds
at eight slots and 13.07–14.47 seconds at sixteen. Production attempt counts
and financial accounting were identical before and after. The report is
`durable/diagnostics/judge-local-load-v1/report.json`, SHA256
`edd24c5314caa52f5d5aa75a5244f9978c65cb091b8908878793210880e578bf`.
The fake response shapes did not exercise the real semantic/quote validators
or the two-stage hallucination dependency. This instrument did not reproduce
the production throughput reversal and cannot establish the transport cause
or future provider performance. No asynchronous accounting rewrite or state
relocation was adopted.

Reviewed commit `67088fa` adds opt-in timing for ledger operations, exact-cache
operations and event-loop scheduling lag. Timing is disabled by default and
does not change prompts, validators, cache identity, scientific conditions or
financial transactions. Each resumed execution uses a fresh profile directory;
a profile-write failure cannot replace the actual evaluator outcome.

Root's single exact Luna/none/Standard health request started at
**07:51:07.640689 UTC** and succeeded in **1.393170 seconds**, with 573 input,
35 output and zero reasoning tokens. Its original unknown attempt remains
held. Evidence is `judgments-methods-v1/healthcheck-profiled-v3.json`, SHA256
`fef36691048d71930b8c1ed1a9476e830eb089fdad5cbd677d3cbd98bd3ecb77`.
Root then approved epoch **07:52 UTC** and launched session `80838` using
`configs/judging_main_recovery_v3.json`, SHA256
`f0a434cd14ccab5045518657b8122fa5ffcdd6d9299fa4d00a37e7b6a4816280`.
The same 24-condition source, $20 run ceiling, eight slots/200 RPM per family
and all historical charge holds are preserved. No automatic ramp is enabled.

The first resumed physical attempt was at **07:58:10.463 UTC**. At
**08:05:32 UTC**, the read-only checkpoint recorded **2,196 settled responses,
zero new unknown attempts or recorded transport errors**, and twelve active
reservations with oldest age 7.25 seconds. Family counts were hallucination
769, chain 630 and role 797; their p95 physical latencies were 4.92, 5.54 and
5.81 seconds. Aggregate wall throughput was approximately 298 responses/minute,
including cache/condition gaps. Evidence is
`judgments-methods-v1/checkpoint-profiled-v3-early-v1.json`. This is an operational
health observation, not completed quality coverage or proof that failures are
resolved. The separately reviewed validation menu was frozen before these
later development results; they cannot change that menu or its decision rule.

At **08:12:25 UTC**, a second checkpoint recorded **3,902 settled responses and
zero new unknowns**, including 1,608 hallucination and 1,664 role responses.
Chain remained at 630 because its queue had completed. The latest-100-attempt
latency window had p95 3.43 seconds for hallucination and 7.31 for role; these
are recent-window values, unlike the earlier full-epoch quantiles. Thirteen
reservations were active, with oldest age 9.24 seconds. The source is
`judgments-methods-v1/checkpoint-profiled-v3-window-v1.json`.

The original observer explicitly held `BEGIN` across two event lookups for
every epoch attempt. The new separate operational entrypoint,
`scripts/observe_judge_queue_window.py`, fetches compact attempt states once,
closes that cursor, then reads only the latest hundred response observations
per worker and uncertain-attempt cause evidence in autocommit mode. Its
checkpoint reports status/event snapshot limitations and query timings:
4.64 seconds for compact metadata and 6.94 seconds total at this observation.
It changes no evaluator or accounting code. Long observer read locks are a
possible contributor to write delays, not an established explanation of the
earlier production failures; no full-history diagnostic scan or accounting
offload was introduced.
