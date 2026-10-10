# Shared ledger writer coordination

The hallucination v4 worker stopped after repeated 120-second SQLite writer
acquisition deadlines. Its terminal profile includes response-evidence and
settlement failures as well as a failed reservation. Increasing the acquisition
timeout did not resolve this operational problem.

At 17:20 UTC, the TEST run retained twelve unknown charges totaling
$0.059636875. An additional $0.00538675 reservation belongs to the stopped
hallucination worker. The exact-ID audit found only its reservation event, with
no saved physical-response or settlement event. Missing evidence does not prove
the provider did not return or bill a response. The full reservation remains
committed, unchanged. No manual settlement or release is justified.

## Change

Every `AtomicBudget` write operation now takes an advisory lock on a persistent
sibling file before opening SQLite and holds it until the connection closes.
The canonical database path determines the sibling path, so symlink aliases
cannot bypass coordination. The sibling is separate from the database itself;
using a whole-file lock on the database could interfere with SQLite's own
byte-range locking on shared storage. It is opened for reading and writing and
never unlinked. Closing the owned descriptor releases it on normal or failed
exit.

This adds coordination between judge processes. SQLite still enforces atomic
transactions. The schema, SQL, DELETE journal, FULL synchronization, existing
BEGIN retry, caps, pricing, uncertain holds, recovery epoch and requirement to
commit a reservation before dispatch are unchanged. No transaction body,
commit or API call is replayed by the new admission step. Read-only clients
continue to use native SQLite locking.

Admission polls every five milliseconds within a nominal 120-second window.
Waits or holds of at least one second are logged without request content.
This does not guarantee FIFO scheduling, starvation freedom or a hard timeout
for a blocked filesystem syscall. Admission and SQLite acquisition have
separate bounds. The repair is not a demonstrated root cause of every earlier
stall.

## Validation

All 56 offline tests passed, including eight new admission fixtures. They
cover exclusion from before connect until after close across three asymmetric
processes, timeout before SQLite entry, exception/interruption release,
connection failure, symlink aliases, non-contention lock errors, unchanged
financial rules and continued native reader/commit blocking. Existing tests
cover cancellation draining, reservation before SDK dispatch and acquisition
without replaying a transaction body.

An independently reviewed shared-filesystem fixture ran three processes with
twenty fake reserve/evidence/settle cycles each, including 4 KiB response
payloads. All sixty settled with exact accounting. Killing only the fixture's
owned lock-holder process released the lock; one additional waiter then
settled. Database integrity and the persistent lock inode remained correct.
No production ledger or API was accessed. Its sub-second concurrent phase is
not a production throughput forecast: the fixture is a fresh small database
on one node.

Source: `src/olens_improve/budget.py`, SHA
`60caff27b9dd717e218822a4115f7f44c8f1820f066f1ec5dbecb021206ca38f`.
Offline receipt: `.state/budget-writer-admission-tests-v1.json`, SHA
`96ef6762a1e9e5c1ac6196b97df4208c779649677bc3de0318ece46536319d0c`.
Shared-filesystem receipt:
`fast/diagnostics/ledger-admission-nfs-v1/report.json`, SHA
`d69fa5025cb39506f148907ef8a640effdafee3edb92cb02ea8a50298373574a`.
Incident: `durable/diagnostics/test12-operational-v1/continuation-v4-hall-incident-v1.json`,
SHA `9ba77ee512017e6eee90ba8415f24c739aaaa712ab258f69d4f270a33a9cdb67`.

## Rollout

Root requested the live role worker to finish its current condition and stop
via its existing SIGUSR1 handler; no in-flight calls were cancelled. Both
remaining families must use the same reviewed implementation after their
former processes and cache owners have exited. Root also requested CPU job
25508300 early so this handoff can cover the existing allocation's 21:25 UTC
expiry without a second interruption. Resource and accounting checks precede
any resumed dispatch. Keep the same twelve conditions, original run cap and
epoch, exact caches, Luna Standard with reasoning disabled, and eight slots /
200 requests per minute per family.

A bounded post-launch observation must demonstrate new settlements and retain
all prior holds. Review actual throughput before revising the finish estimate.
If coordination still stalls, diagnose the recorded wait/hold phase and prefer
one family at a time over another automatic timeout increase. Implementation
and offline validation alone do not establish successful production recovery.

At 17:40UTC root sealed `configs/judging_test_continuation_v6.json` (SHA 56b8ae5a6b7187ecb7e83d523da0ebc4ce5f119d3d67f3fcc41211142329e60d) after both old PIDs were absent and both cache-owner locks were free. Hallucination resumed as PID2407614 and role binding as PID2481603 on node1603. Role had completed random32 and stopped cleanly before specificity32. The old CPU allocation was released after only its idle hold remained. The 17:43 bounded health check found fresh settlements from both new workers and no new unknowns. Hall API latency median was 2.509s and role 1.335s. All twelve historical unknown holds and the separate stopped-worker reservation remain. Logs also retain a 37.616s database hold and 34.521s admission wait. Coordination has resumed processing, but the short observation does not establish sustained recovery or eliminate filesystem stalls. Receipt `continuation-v6-first-health-v1.json`, SHA `0f4b0be24d87fcf9f5a15f2c2ccd657513981c6480d93d416214a5502de64c54`.
