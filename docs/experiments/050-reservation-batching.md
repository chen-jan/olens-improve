# Reserve judge spending in small batches

Status: implemented and reviewed; role DEV six-condition rollout and hall TEST four-condition rollout complete. Remaining hall DEV preparation is ready; mixed-condition live throughput measured.

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

Three interleaved trials measured 128 accounting cycles each. Individual
reservations took 2.951, 2.920 and 5.335 seconds; batches took 0.789, 0.773 and
0.786 seconds. The ratio of medians is **3.75×**. Every trial preserved the 560
original holds, all caps, and exact fake billing. No API calls were made and
temporary database copies were removed. Receipt:
`fast/diagnostics/reservation-batch-noapi-v1/receipt.json`, SHA
`e2b0d2aa5f6ae8d9424972709452d350601bc876dd6d1a9e5a5fc5449c1517d7`.

The role TEST family completed all twelve comparisons and exited zero. Its
cache-owner release and exact completion contracts were verified. Hallucination
received the verified SIGUSR1 boundary-stop request at 21:38:22 UTC, then exited
cleanly after pooled N32. At 21:44, TEST had 44/48 complete comparisons: role,
multi-hop and chains 12/12 each, hallucination 8/12.

Root sealed and launched the role's six unchanged remaining DEV comparisons at
21:45–21:46 as PID 395046/session 3538. Sealed specification:
`configs/judging_dev12_remaining_role_batch_v4.json`, SHA
`746026d866badc90108807663ed2ce4dbd53864ce4106b71c0cb95acc30e7bc5`.
The released-family forecast contains 16,817 new unique calls and an expected
$1.3556474782 charge under the frozen empirical basis, SHA
`4c65f37921d42d1fdf8806915c00ab3e1dee14930e4c1de2047910531330209d`.

Root sealed and launched hall's four remaining TEST comparisons at approximately
21:47 as PID 398431/session 31433. Sealed specification:
`configs/judging_test_batch_hall_v14.json`, SHA
`6fe7b48b3c6b53adf82829dc5934b56e6c6ce8755ae20ae53e82464a8f294f7e`.
The launcher retains the full signed 12 menu and reuses saved completed results;
it does not introduce a changed scientific subset. Five hall DEV comparisons
remain blocked until all hall TEST comparisons finish and release the cache.

Both launches explicitly enable reservation batch 16 and connection reuse, with
unchanged Standard Luna / reasoning none, 256 concurrent requests / 4,000 RPM,
original 07:52 epoch and all retained holds. TEST and DEV caps remain $40 and $20.
The 21:44:16 accounting receipt records $29.05894376 estimated API usage plus
$4.8597425 reservations, total $33.91868626 committed; the $4.85435575 unknown
subset is already included. DEV has $15.07341819 remaining under its run cap.
Receipt: `durable/diagnostics/test12-operational-v1/storage-recovery-concurrency-v11-operational-reuse-role-terminal-global-dev-2144-v1.json`,
SHA `8c96b6e34a54eada67ea6a08721f803fe95dc4af57bc805d278a13fefdbb023a`.

No live speedup is established at this launch checkpoint. The first combined
measurement is scheduled for 21:54; prior estimates and the offline 3.75× ratio
are not a substitute for observed end-to-end throughput.

## Bounded TEST exposure disclosure

Between 21:29:11 and 21:31:56 UTC, the operational observer incidentally saw two
auxiliary hallucination raw-N1 contract fields. The metadata-only receipt records
field names and the bounded interval; it does not repeat their numeric outcomes.
Root has not synthesized TEST findings or used these fields for menu tuning.
The fixed menu and all method settings remain unchanged. A blanket claim of
zero incidental TEST exposure is no longer valid. Disclosure receipt:
`durable/diagnostics/test12-operational-v1/primary-six-completion-contracts-v2.json`,
SHA `b0b69992c882e503ab8e016c2090d216b0c3d51491224a6fd5b7b7e4ef8b1758`.

No new scientific quality result is reported in this operational experiment.

## First completed live rollout, 21:55 UTC

The six DEV role comparisons closed by the 21:51:26 metadata check. Root collected
session 3538 exit 0; the 21:54 receipt verifies all six exact contracts cover 3,420
cells each with no missing judgments. The worker settled 16,818 requests across
295.34 seconds of summed condition walls, approximately 3,417 per minute. No
ledger errors were reported; all 124 uncertain DEV holds remain unchanged.
Incremental billed-attempt accounting is $1.3324818. These are different conditions
and traffic from the earlier trial: the measured rate is not a controlled causal
speedup ratio. Source requests and scientific settings remain fixed.

At 21:55:16, hall TEST is also terminal: PID 398431 absent, exclusive cache owner
free, all twelve exact 3,705-cell contracts complete with both judging stages,
and all twelve profiles closed. Root collected session 31433 exit 0. All 48 TEST
comparisons are therefore complete. Five hallucination DEV comparisons remain;
the reviewed family-only forecast and new batch-v4 preparation are ready for
root review. Signed TEST analysis has started, but this operational record reports
no final quality findings.

The 21:54:20 accounting snapshot records global usage $34.13221616 plus reservations
$5.613203875, committed $39.745420035. The $4.85435575 uncertain subset is included
in reservations. DEV committed spend is $6.25906361, leaving $13.74093639 under
its unchanged $20 cap. Hall was still active at that snapshot; it is not final
reconciled billing. Completion/accounting receipt:
`durable/diagnostics/test12-operational-v1/batch-dev-role-v4-test-hall-v14-operational-2154-v1.json`,
SHA `0b044d498f3b7f2b4ee966fde6cb70ed08c000ed8c506a47baebed4345b9f6f8`.
Hall terminal receipt:
`durable/diagnostics/test12-operational-v1/hall-batch-v14-terminal-contracts-v1.json`,
SHA `5119be87fdea7dc4cf536cc29f9af0e3a97870eae751a4ee6352fed52a83d7ea`.
