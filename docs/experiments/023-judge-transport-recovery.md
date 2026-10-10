# 023 — Donor-judge connection failures and bounded recovery

Updated: 2026-10-10 UTC. Status: donor recovery completed; original uncertain charges retained. This is a transport incident, with unchanged benchmark prompts, Luna effort none, Standard destination and source text.

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
