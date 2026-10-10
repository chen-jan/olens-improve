# Bounded ledger lock acquisition

The repeated fatal phase was `BEGIN IMMEDIATE`. The reviewed patch retries only that lock acquisition, before any transaction body executes, for a nominal 120-second monotonic window. Each SQLite busy wait is at most one second, with a 50 ms backoff bounded by the remaining window. Only primary `SQLITE_BUSY` while `in_transaction` is false is eligible. Successful acquisition restores the original 30-second busy timeout for the body and commit. No body, commit, SDK request, response or financial transition is replayed by this helper.

Caps, transport epoch, uncertain holds, SQL/schema, DELETE journals, FULL synchronization and durable reservation before API dispatch remain unchanged. The patch logs only acquisition outcome, retry count and elapsed seconds. It neither guarantees fair lock scheduling nor bounds a stalled filesystem syscall to an exact wall deadline. The already-live role worker retains its original loaded source.

## Offline verification

All 48 tests passed on allocation 25474685, physical cores 83 and 84, with a 4 GiB step cap: 40 accounting/cancellation/performance/contention tests in 0.860 seconds, plus eight pricing/index tests in 0.121 seconds. Seven new fixtures verify a real competing writer's release, deadline failure without body execution, restored body timeout, non-BUSY refusal, active-transaction refusal, primary-code handling of extended BUSY, no transaction-body or commit replay, and unchanged caps/unknown holds after acquisition.

Source and test hashes, commands, scope and the earlier terminated sandbox-run limitation are retained in `.state/budget-acquisition-tests-v1.json`. No production ledger connection, paid call, worker restart or hold change was performed by these tests.

## Throughput and capacity limits

Terminal operational profiles give the following summed reserve/evidence/settle method elapsed time. The denominator is observed settlement calls, not an invoice-derived request count.

| Execution | Settlement calls | Summed ledger elapsed | Ledger elapsed per settlement |
| --- | ---: | ---: | ---: |
| Initial TEST hallucination | 4,285 | 460.43 s | 0.10745 s |
| Initial TEST role | 4,529 | 468.14 s | 0.10337 s |
| Failed continuation hallucination | 1,240 | 436.79 s | 0.35225 s |
| Completed continuation raw role | 1,177 | 275.76 s | 0.23429 s |
| Completed continuation capped role | 284 | 34.36 s | 0.12098 s |

These are method elapsed times, including lock waiting, CPU, filesystem IO and commit. They are not measured writer-lock occupancy. Waiting from separate workers overlaps, so multiplying these averages by the aggregate request rate does not prove that storage is saturated.

A normal received response uses three ledger write transactions: reservation, response evidence and settlement. Additional evidence or uncertain bookkeeping can add writes. Two families each targeting 200 responses/minute would request about 20 ledger write transactions/second. A sustained mean serial lock-holding time of 50 ms per write would already consume that capacity; 60 ms for every write would exceed it. This is a capacity calculation, not a measurement of the production lock holder.

The earlier unchanged-copy probe had only two serial cycles. On its NFS copy, reservation bodies took 8.0–8.9 ms and commits 47.8–55.9 ms; settlement bodies took 0.34–0.43 ms and commits about 1.02–1.05 ms. Thus transaction sizes have very different costs, and four identical 60 ms writes per response would be an unsupported model. The local XFS copy had reservation commits 0.52–0.63 ms, but its warm isolated measurements do not establish the production cause or steady-state concurrent capacity.

The failed continuation also has a distinct response-evidence `OperationalError` with maximum 37.25 seconds, in addition to the failed reservation at 43.77 seconds. Settlement recorded no errors. Preserve that possible missing raw-evidence event in the incident record; do not reduce the incident to reservation contention alone.

The retry patch can tolerate a longer temporary lock wait. It cannot by itself improve writer service capacity, ensure fairness, eliminate a reader/commit stall, or justify a faster completion forecast. Judge throughput and acquisition retry logs must be assessed from the next authorized execution; no concurrency or accounting change is implied here.

Exact profile/copy paths, hashes and numeric calculations are retained in `.state/ledger-acquisition-capacity-v1.json`. This analysis read only existing terminal operational profiles and copied diagnostic receipts, with no live ledger scan or scientific outcomes.
