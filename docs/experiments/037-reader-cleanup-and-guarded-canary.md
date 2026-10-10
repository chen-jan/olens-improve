# 037 — Close operational readers and prepare one guarded canary

**Status:** cleanup independently reviewed; the first real canary failed the reservation-latency diagnostic, the subsequent phase-instrumented canary passed, and the recovered A2 and remaining DEV scaling queues completed. The original stall cause remains unresolved. **Date:** 2026-10-10. This is an operational instrument repair, not an O-lens quality experiment.

## Question and evidence

Can operational readers release SQLite read locks promptly without changing the authoritative ledger, held charges, guard, or scientific requests?

The role scaling worker failed at `budget.py` transaction `COMMIT` with `sqlite3.OperationalError: database is locked`. Its retained A2 profile reports 10 reservation operations totaling 238.59 seconds, with a 45-second maximum, while the event-loop lag maximum was 0.007 seconds. The first stalled reservations preceded the bounded observer launched at 12:54:27 UTC. These facts do not identify the lock holder or establish that monitoring or NFS caused the failure.

The source-bound terminal incident is `${OLENS_DATA_ROOT}/diagnostics/dev-scaling-completion-v1/role-terminal-incident-v1.json`, SHA `0a613a4f973d4b2fe25fa08fe081fb2584e00d0da743e7241e2c3aef0ee3deec`. It retains all three new uncertain attempts ($0.014532375), zero active reservations, and the successful responses. Experiment [034](034-development-scaling-completion.md) records the unfinished descriptive scaling scope.

## Change and checks

Retire the legacy long-`BEGIN` observer in favor of the existing bounded autocommit observer. Close observer, preflight, boundary-watcher, resource-watcher and health-source connections in `finally`/`closing` paths. The resource watcher retains its short consistent read snapshot and ends it before other probes. Budget writer code, indexes, accounting, caps, holds and judge inputs remain unchanged.

An optional `--worker-since` narrows only the requested PID observation window. A fresh worker must use a conservative known launch timestamp. Full-run totals, original recovery epoch, shared guard window and uncertain charges retain their existing scope; absent observations remain explicit rather than becoming zero latency.

All 25 focused offline tests passed: reader transactions (6), observer windows (4), guarded health transport (5), resource watcher (6), and remaining-menu dispatch (4). Disposable SQLite fixtures demonstrate that an explicit read transaction can block a writer's commit, and that closing it permits that same transaction to commit without replaying the write. A completed autocommit read permits commit while its connection remains open. This agrees with SQLite's [transaction documentation](https://www.sqlite.org/lang_transaction.html), but does not prove the live incident's cause. Fake SDK tests confirm preserved holds, exact guard equality, one-response accounting drain, and rejection before SDK dispatch when the existing guard blocks.

Exact changed/unchanged source hashes, test counts and durations are frozen in `configs/judge_reader_cleanup_receipt_v1.json`, SHA `33182a0280e95b24bacb5a2f4df82e0f6187912f5fd5ad992bc54069e0abeb9b`. `git diff --check` passed. No production ledger query, ledger mutation or model call was performed for this cleanup.

## Proposed canary and stopping rule

Root sealed `configs/judge_reader_cleanup_canary_v1.json`, SHA `bd037e9a67526b779f3a0714d5302a2d29b92ff5cd8bc7b23a186de822c035e9`, for one replay of retained unknown attempt `f2dc9208-2304-4725-99e6-698dfd7372d6`. Preserve its $0.004839250 hold and every other hold. Require its exact stored request hash and original `2026-10-10T07:52:00+00:00` guard before client creation. Use Standard Luna, reasoning `none`, SDK retries zero, the existing development run/$20 ceiling and project $300 hard ceiling/$200 target on job 25474685, CPUs 81/82. No external ledger observer runs during this call.

Drain the single request and accounting, then inspect the fresh terminal profile. Flag errors/new unknowns, reservation maximum over 2 seconds, heartbeat lag over 1 second, or wall time over 60 seconds for review; never cancel to enforce these diagnostic thresholds. A pass would establish only this request, not throughput or cause. The primary verdict remains unchanged. Root separately reviews any subsequent fixed 8/200 role queue resume; no epoch reset or automatic ramp is authorized here.

## Canary outcome

Root launched the exact guarded request at 13:29:45.767281 UTC. It returned and accounting drained successfully, with 499 input tokens, 51 output tokens, no cached/cache-write/reasoning tokens, and usage-based Standard cost $0.0000754. This is usage accounting, not an invoice reconciliation. Root verified its owned watcher was sleeping without a child, paused it before the request and resumed it after drain; no external observer ran during the call. All old holds and the original epoch were retained.

Request wall time was **32.2166 seconds**, including **29.8730 seconds in reservation**. Evidence recording took 0.00217 seconds and settlement 0.03470 seconds; maximum event-loop lag was 0.000472 seconds. The canary crossed the 2-second reservation threshold. Its successful provider response does not make the operational repair successful: cleanup did not resolve the bottleneck, and root withheld queue resumption.

Artifacts under `${OLENS_DATA_ROOT}/diagnostics/judge-reader-cleanup-v1/` are `health-guarded-v1.json` (SHA `7116c101b939433f4ce640a1c85e4f8f72fdfef9e632150d0c2663f0393fd18d`) and `health-guarded-v1-profile.json` (SHA `8d47ff12318dcfb4da48c615acb66b9d4ea97f9151d12c1b7be25899d0678cae`). The next proposed diagnostic separates connection, transaction acquisition, query/materialization and commit timings on identical disposable NFS/XFS ledger copies, without network calls or production migration. No held-out quality data was accessed.

## Matched copy diagnostic

Compute prepared one consistent read-only backup, closed the source connection, and produced byte-identical, separate-inode copies on NFS and local XFS. The baseline is 1,265,651,712 bytes, SHA `e14b1ecff75772273878c954beaba7b9e9d0655589147c94da15d279e695ffa2`. The preparation receipt is `diagnostics/ledger-reserve-phase-v1/preparation.json` under the durable root, SHA `4efb1baa67b750d5df6839987b3c77a4dd40bc94b1750df0bc54880667488ea0`; its execution binding preserves the original proposed spec.

The unchanged budget methods performed two serial reserve/settle cycles per location with diagnostic-only IDs. Both copies retained all 547 historical unknown attempts and their $4.794718875 holds. No endpoint was called and production was not mutated. Five offline profiler tests passed; compute independently verified the source and preparation.

| Location | Reservation 1 / 2 | Reservation COMMIT 1 / 2 |
|---|---:|---:|
| NFS | 65.40 / 56.39 ms | 55.91 / 47.79 ms |
| Local XFS | 9.60 / 8.36 ms | 0.633 / 0.521 ms |

Transaction acquisition stayed below 0.016 ms. Global/run committed sums took approximately 4.2/1.8 ms; the guarded unknown sum took 1.4–2.3 ms. These results do **not** reproduce or explain the live 29.873-second reservation. A query/index change is not justified by these timings. Copying and hash verification warm caches; the copies omit original-file locks and use small synthetic metadata without the real request/content-cache-key insertion path. Their synchronous main-thread workload also differs from the live asynchronous ledger worker. Keep those limits explicit.

Source-bound reports are `nfs-report.json` (SHA `7c5f29257758764c62fd3a95fe650a38c30dd4b322c47082c8524cb94b5350e9`) and `xfs-report.json` (SHA `b80c2989b111e7cff0bd0e33fb387aa30d7a895fb319de5f1dd9b7d9526b9583`) in that diagnostic directory. Independent inspection confirmed phase totals, baseline identity and retained holds.

Root requested one further real guarded canary using the same timer, with unchanged methods, SQL, request, epoch, caps and holds. The opt-in instrument records transaction phases, byte counts and main/worker classification; it generates no synthetic production attempt. Seven health tests pass, including one-response drain, guard rejection before SDK dispatch and restoration of the original SQLite connect function. Root and compute independently reviewed the single-call scope before root sealed `configs/judge_reader_phase_canary_v2.json`, SHA `26193585e3a25d6130a4f41bb78e2311535927a073fa08af2b8daac425b0ed23`.

## Live phase outcome and bounded next step

The second root-launched guarded canary completed in **2.3620 seconds**, with **66.993 ms in reservation**. Reservation COMMIT took 56.204 ms, the guarded unknown-charge query 2.801 ms, and the global committed sum 4.297 ms. The reservation ran in the existing serialized worker thread with 2,516 bytes of request metadata. Evidence recording took 17.219 ms, settlement 19.981 ms, and maximum event-loop lag was 1.343 ms. No phase error or new unknown charge occurred. The 499 input and 48 output tokens cost $0.0000739 under usage-based Standard accounting. Root paused its owned watcher and excluded external observers until the request and accounting drained, then resumed the watcher.

The exact artifacts in `diagnostics/judge-reader-cleanup-v1/` are `health-guarded-phase-v2.json` (SHA `c16e986915f0705dcaf3e2e253e37dfc29391ae91dbdf8e9b8a496d00a58710a`), `health-guarded-phase-v2-profile.json` (SHA `6703118f8e3521bf6c08ce00b53361fba7fbacc4dbbde0901fb66a80fd758585`), and `health-guarded-phase-v2-sql.json` (SHA `f183df4b8cc306c57b43ad17bcedf9912d6646febe618065b85af79fb46a52e9`). Independent inspection confirmed these pins and phase totals. This observation does not establish sustained throughput or identify the earlier lock/stall cause. It justifies no query change, financial relaxation or production migration.

Root requested only the unfinished DEV role best-of-2 condition as the next real throughput check. Its prepared spec is `configs/judging_dev_role_a2_reader_recovery_v2.json`, SHA `0615a42f7503c34ba563746f568b220d20beb113a0b39681861eaf7292abbfa9`; its exact one-condition menu is `configs/conditions_dev_role_a2_reader_recovery_v2.json`, SHA `fcef51ec5b1219cc5ebdd7d0ec5dbff145895610bbb140f6d04b8750ef1624b8`. Compute independently reviewed the unchanged full-menu provenance, original 07:52 epoch, $20 run cap, all holds, Standard Luna/none and fixed 8 slots/200 RPM. Root must seal and launch it. A1 is not replayed and no other arm is authorized by this preparation. Observe approximately 100 new responses before a bounded PID-only checkpoint using the actual conservative worker launch bound; do not cancel requests to enforce that observation count.

Root's receipt after the second canary reports $13.15336028 settled usage and $4.794718875 unknown holds, totaling $17.948079155 committed, with 83,356 settled attempts, 547 unknown attempts and no halt. No unknown charge was released, including the original replayed attempt. Both canaries together cost $0.0001493 in retained usage accounting; this is not invoice reconciliation. Late DEV evidence is descriptive and cannot change the already frozen primary TEST menu. No TEST quality data was accessed for this diagnostic.

## Sustained recovery outcome

Root sealed the A2-only specification with SHA `99c5f0f0c71165092efe9340f6528f1fec85c94f684b54d6dcca23d875b6cca1` and launched the worker at 14:14:44.90 UTC. It completed successfully: **1,556 paid responses in 505.421 seconds, or 184.72 responses/minute**, against the fixed 200-RPM limit. The terminal profile is `runs/development-full-grid-v2/judgments-methods-v1/performance-dev-role-a2-reader-v2/role_bound_association/role_bound_association-best_n_exact-n2.json`, SHA `cbe4ed0fb127810a5bf9ce79fe919efa80a7121d7191b02a6ad4822418b179de` under the durable root.

Reservation operations totaled 131.46 seconds, with median 41.64 ms, p95 366.77 ms and maximum 12.42 seconds. These operations overlap provider work; their totals must not be added to wall time. Maximum event-loop lag was 0.135 seconds and no operation exception was recorded. This establishes useful throughput for this queue, not that every lock cause was fixed.

One bounded checkpoint at 14:23:56 UTC found all latest 100 responses settled, no new unknowns in that window, and provider p50/p95 latency 1.270/1.662 seconds. Its 95.3-second tail window corresponds to 63 responses/minute and is not the whole-worker rate. The DEV run then retained its 124 historical unknown attempts and $0.617766375 holds, with $3.883626135 settled usage. This is a run-scoped historical receipt, not a current project total. The receipt is `diagnostics/dev-role-a2-reader-v2/elapsed-checkpoint-v1.json`, SHA `5bd880f8f20c7a829cfe527fe3433b0a9f0b596b29bbac63d3e67e7fe116ed99`.

After separate source/owner/headroom reviews, the fixed DEV role N4/N8/N16 and hallucination N8-repair/N16 queues also exited successfully. Root verified both terminal sessions by 14:55 UTC. They retained the original $20 run cap, 07:52 recovery epoch, all unknown holds and fixed 8 slots/200 RPM. Their scientific results remain descriptive and cannot retune the prospectively frozen TEST12 comparison.
