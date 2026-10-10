# Reserve judge spending in small batches

Status: implemented and reviewed; production activation pending a clean handoff.

The user requested faster results and questioned the cost of checking the budget
before every request. The current judges already use Standard Luna, with up to
256 concurrent requests per family. More API slots do not remove a serialized
local budget-check bottleneck.

## Evidence and hypothesis

The completed role A32-pruning comparison made 4,115 physical requests in
2,271 seconds. Its serialized reservation, evidence and settlement operations
occupied about 2,263 seconds in total. Nested transaction timers attribute
1,297 seconds to the SQL body, 904 seconds to waiting for the other writer,
and only 44 seconds to committing. These overlapping timers must not be added
together. The hypothesis is that sharing repeated guard and cap scans across
small groups of requests will increase actual API dispatch throughput.

Read-only query plans on the preserved archive already used covering indexes.
A separate copied-ledger storage test found only a modest median benefit from
node-local storage. We keep the existing shared ledger and its recovery model.

## Change and controls

An explicit `OLENS_LEDGER_RESERVATION_BATCH_SIZE=16` setting groups at most
sixteen reservations into one existing SQLite transaction. Each request retains
its own ID, worst-case amount, metadata and audit event. Exact integer running
totals enforce the same run and project caps. No call reaches the API before its
reservation commits. Failure rolls back the whole batch; canceled callers retain
their committed holds. The default remains one reservation per transaction.

This changes scheduling and accounting overhead only. Judge model, reasoning,
tier, prompts, generated readouts, cache identities and scientific settings remain
fixed. All original uncertain charges and the 07:52 recovery epoch remain intact.

## Validation and rollout

The combined allocated-CPU suite passed **86 tests in 2.246 seconds**, including
six new async tests and ten new budget tests. Tests use disposable databases and
fake SDK responses, with zero network calls. Independent source review passed
the exact source hashes recorded in
`configs/ledger_reservation_batch_review_v1.json`.

Matched copied-ledger throughput trials compare repeated individual reservations
with batches using the original TEST run and guard. Real throughput must be
measured after activation; a copied-database improvement is not an end-to-end
speedup guarantee.

The role TEST family completed all twelve comparisons and exited zero. Its
remaining DEV queue can use the new code after its fresh forecast and handoff.
Hallucination received a verified SIGUSR1 boundary-stop request at 21:38:22 UTC;
its current comparison continues, without canceling paid calls.

No new scientific quality result is reported in this operational experiment.
