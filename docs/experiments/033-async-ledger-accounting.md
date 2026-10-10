# Asynchronous ledger accounting and TEST judging preparation

The reviewed accounting patch was applied on 2026-10-10 after the VAL report completed and its source hash hold ended. It changes only `evaluation.py`, `performance.py`, and adds `test_async_ledger.py`. `budget.py`, prices, transaction rules, holds, caps, transport guard, prompts, model, tier, reasoning effort, scientific cache identity, and verdict validation are unchanged. No paid call or production ledger write was made for this verification.

One serialized, bounded thread lane is shared by clients using the same ledger object in a worker. Each dispatch waits for its committed reservation. Cancellation drains queued accounting; an undispatched committed reservation is retained as uncertain. An observed response finishes evidence and settlement before cancellation propagates. Client shutdown drains owned operations and joins the lane. Upstream's redundant synchronous budget precheck is removed only because every authorized direct Luna dispatch passes through the atomic reservation; other routes are rejected. Profiling metric updates are protected across threads.

## Source identities

| File | Applied SHA-256 |
| --- | --- |
| `src/olens_improve/evaluation.py` | `5ae885ace1ecc974a59cddaef118c68285f4380f1a6fd259fed540e8f5d16039` |
| `src/olens_improve/performance.py` | `d9f5b89d37d8f4eb379d33ada60f4cfc55e19fc3480ae735d3e2b5614e98033b` |
| `tests/test_async_ledger.py` | `c737e9153c3981f77c87004e3d6536eecee9a33f429e77312eff48cc27771cba` |
| Unchanged `src/olens_improve/budget.py` | `90beef9da7905e57e1b0fad2e2affa14822033451a9f4d86b92bb7325e0fb182` |

Original evaluation/performance hashes were checked immediately before the exact candidate files were copied. Original hashes are retained in the isolated candidate manifest at `/tmp/olens-async-ledger-candidate/candidate-manifest.json` and the staged copy under fast storage.

## Offline evidence

The applied implementation passed 45 tests via `python -m unittest discover` on job `25474685`, node1600, physical cores 24 and 30: 15 asynchronous cancellation/accounting cases, 18 budget/pricing cases, five performance cases, four exact-cache cases, and three transport cases. All used fake responses or disposable test ledgers. Six suite processes took 1.819 seconds in total, including interpreter startup. Receipt: `${OLENS_DATA_ROOT}/diagnostics/async-ledger-applied-v1/tests.json`, SHA-256 `c3b322f95d3bd91b1a272528a9b7707cfedd107dc6aeecc8ae3ad969d92cd001`.

The separately approved load check backed up the production ledger read-only into a 1,265,733,632-byte node-local XFS copy in 13.55 seconds. Source counts, events and exact held-row identities were unchanged; existing copied holds were unchanged. Two clients sharing one lane settled all 64 fake responses exactly at concurrency eight, with reservation events preceding response events. Two injected 200 ms reservation sleeps did not block the event loop: load elapsed 0.878 seconds, heartbeat scheduling lag maximum 5.42 ms and p95 3.98 ms. No pending accounting tasks or leaked ledger threads remained; both fake clients closed and the owned database copy was deleted after success. Fake usage totaled $0.000448 in the disposable copy, not an actual charge.

Load receipt: `${OLENS_DATA_ROOT}/diagnostics/async-ledger-copy-load-v1/receipt.json`, SHA-256 `c4a3a7f9081cbc2ff8a4cc65bf0e3c42049e714ef9d7bc259e15be09a8107a18`. The archived candidate SHA-256 is `2ad5ec3b46e13b1f67a69dd378adf2299604c4884c889031526052b462aa6892`. This local-XFS, fake-network result is not a live NFS or provider throughput measurement. The test did not exercise three independent ledger writers.

## Prospective TEST operational template

Do not launch from this record. Root must first bind the actual immutable TEST export, ordered frozen method menu, gate/freeze, exact cache-miss forecast and current source hashes. The operational spec should remain `prepared_pending_root_export_forecast_review` until those checks and a positive run ceiling are approved.

A minimal unlaunchable template is:

```json
{
  "status": "prepared_pending_root_export_forecast_review",
  "run_id": "test-final-methods-v1",
  "run_cap_usd": null,
  "concurrency": 8,
  "rpm": 200,
  "tier": "default",
  "reasoning_effort": "none",
  "automatic_ramp": false,
  "recovery_epoch": null,
  "conditions": null,
  "selections": null,
  "selection_sha256": null,
  "forecast": null,
  "forecast_sha256": null,
  "unresolved_fields": ["positive_run_ceiling", "exact_export_and_ordered_menu", "gate_and_freeze", "source_pins", "allocation_and_cpu_pairs", "fresh_profile_and_stop_paths", "root_reviewed_epoch"]
}
```

Required settings are Standard (`tier: default`), reasoning `none`, concurrency eight and 200 RPM **per family**, no automatic ramp, one authoritative ledger, and one root-reviewed recovery epoch. Preserve every prior hold; the TEST ceiling includes all charges and uncertain holds for its run. Retain the unchanged atomic hard/run-cap and latest-100 uncertain-attempt guard. Bind fresh execution-specific profile and stop paths, exact condition order, source/export/provenance/forecast hashes, CPU placement and allocation expiry. Missing or nonpositive ceilings, missing source pins, or an unresolved forecast must fail preflight.

Three paid families may run concurrently only with one exclusive owner of each family cache, absent previous family workers, disjoint assigned CPU pairs, and adequate cgroup headroom. `hallucination.sqlite3`, `chain_intermediates.sqlite3`, and `role_bound_association.sqlite3` are separate files; their respective exclusive `.owner.lock` gates remain held across each queue. Exact request/source/validator identities and insert behavior are unchanged. The patch adds no background cache writers and does not relax family ownership, including across DEV/VAL/TEST. Local condition caches also remain owned by their existing worker.

The central ledger remains shared across processes: each worker has its own serialized thread lane, while SQLite transactions enforce caps and holds across all writers. Threading does not remove cross-process SQLite/NFS contention. Exact-cache callbacks remain synchronous and may still delay a worker's event loop. Concurrent three-family operation therefore needs a bounded early checkpoint from actual queued requests, without extra probes, before being described as healthy. Stop on accounting errors or the frozen uncertain-charge guard; use condition-boundary stops and retained holds rather than increasing concurrency or silently resetting an epoch. If long local tails recur, sole-family sequential judging remains the simpler fallback. A stuck filesystem operation can delay graceful draining, and hard process termination cannot guarantee a drain.
