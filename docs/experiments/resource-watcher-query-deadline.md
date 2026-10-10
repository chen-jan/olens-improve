# Resource-watcher budget read deadline

Status: implemented, tested offline and coordinator reviewed on 2026-10-10. This changes only
the monitoring reader, not reservation/accounting logic or scientific requests.

The TEST hallucination and role workers stopped with `database is locked` while
acquiring `BEGIN IMMEDIATE`. The independent process check found both workers
absent and the chain worker still alive. The persistent resource watcher on
node3107 was sleeping, with no child or open ledger descriptor. No live leaked
reader was identified; those observations do not identify the lock holder or
establish that monitoring caused the failures.

`infra/watch_resources.py` now applies a two-second monotonic deadline through
a SQLite progress callback every 1,000 VM instructions. Its existing two-second
connection timeout remains a separate lock-wait limit. On interruption, the
watcher clears the callback, rolls back an active read transaction and closes
the connection. It reports `temporarily_unavailable` and an explicit deadline
flag, without invented zero costs, counts or available-budget values.

Thirteen focused reader/resource tests passed in 0.198 seconds. The new test
runs an actual aggregate on a disposable SQLite fixture, proves its shared read
lock blocks a writer's commit, then crosses the deadline deterministically.
After interruption and close, that writer commits its already-written
transaction without replaying its body. Existing snapshot-value and failure
cleanup tests remain unchanged. No production ledger query or mutation was
used to implement or test the change.

This is a cooperative query deadline: it cannot preempt a blocked kernel or
NFS call. It reduces monitoring exposure and does not establish a hard wall-time
bound, repair the unknown contention cause, change caps/epochs/held charges,
or authorize queue restarts. The persistent loop launches a fresh watcher child
at each interval, so subsequent children load the reviewed source.
