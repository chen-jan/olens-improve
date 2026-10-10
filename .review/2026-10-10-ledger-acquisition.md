# Independent review: bounded ledger lock acquisition

Reviewer: GPT-6.1 Sol (`adversarial_evaluation`). Status: approved for the separately reviewed operational continuation. This is source review, not a production-ledger mutation or a paid run.

Reviewed source: `src/olens_improve/budget.py`, SHA `a9d08319f69ca7fa4722f01fef77d4bfbf47210d83cc7ab5f5a376c12a3b20c7`. Reviewed tests: `tests/test_budget_lock_acquisition.py`, SHA `0316d3f67022ce8e53adf584ba435e14f7ae99a349746111a49c95806d68d274`.

The change retries only `BEGIN IMMEDIATE` before any transaction body executes. It accepts only an `OperationalError` with primary `SQLITE_BUSY`, requires `in_transaction` false, uses short busy waits and bounded backoff within a nominal 120-second monotonic window, and restores the original 30-second timeout after acquisition. Transaction body, commit, rollback, price calculations, caps, charge holds, guard epoch and evidence/settlement semantics are unchanged. A body or commit failure is never replayed.

The seven new disposable tests exercise actual concurrent-writer release, deadline without body execution, refusal to retry other errors or an active transaction, extended BUSY handling, exactly-once body/rollback behavior, and cap enforcement with retained unknown charges after acquisition. The compute reviewer reported all forty focused accounting/cancellation/performance/acquisition tests passing; this independent review inspected source and tests without duplicating that suite or reading production state.

The recurring hall failures identify the reservation acquisition step, but the initiating lock holder remains unresolved. The continuation profile also contains a separate evidence-write error while settlement has no exception. The patch does not establish the cause, guarantee that all future evidence writes succeed, or impose a hard deadline on a blocked filesystem syscall. Existing successful verdicts and every uncertain charge must remain preserved, and any resumed worker needs a newly source-pinned operational specification.
