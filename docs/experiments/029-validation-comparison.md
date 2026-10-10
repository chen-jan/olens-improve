# Twelve frozen validation comparisons

Status: final two role comparisons running, 2026-10-10 11:38 UTC. All
collection, reconstruction and exports are complete. Hallucination, multi-hop
and chain are scientifically complete; role is ten of twelve. Root resumed
only its exact remaining two conditions after a clean queue boundary, leaving
DEV judging stopped. No validation conclusion is reported yet; TEST analysis
remains closed.

## Question and decision

Do the development candidates improve useful recovery or reduce contradicted
readouts on new groups, without concealing losses through shorter or off-topic
outputs? Select at most two practical operating points using the decision rule
frozen in [experiment 027](027-validation-shortlist-freeze.md). Consider all four
families, original item aggregation, paired cell recovery, group uncertainty,
systematically sampled examples and inference cost. There is no significance
gate, hidden average across families, or requirement to declare a winner.

The twelve conditions are raw and capped N1; best reconstruction of 16 and 32;
one eligible random response from 32; pooled selection at 16 and 32;
matched-control selection at 32; that selection followed by .005 pruning and
its matched random-deletion control; best-of-32 followed by the same pruning
and its matched random-deletion control. All reuse the same recorded N32 pool.
The .005 threshold applies at each sequential deletion after refitting.
Whole source bullets remain intact, with at most four bullets and 256 text
tokens except for the separately preserved raw baseline. No helper calls are
needed for these conditions.

The matched-control-plus-pruning comparison has both components removed in
turn: its unpruned parent and best-of-32 with pruning. Random deletion matches
retained bullet count. A16 versus A32 and pooled16 versus pooled32 measure
additional sampling, while pooling versus best-of-N uses equal candidate
availability. These comparisons do not imply equal total inference cost.

## Frozen sources and complete coverage

The exact menu, scientific settings, development decision evidence and analysis
gate were frozen before inspecting validation outcomes. The old blind-generation
gate and original record markers remain unchanged.

| Artifact | SHA-256 |
|---|---|
| `configs/conditions_validation_v1.json` | `bed944371e050eff7898d07fe0a2ccb39a49a3359779640525b06c4904aca82a` |
| `configs/validation_shortlist_freeze_v1.json` | `30daad423ee9326971f5f08fa4f3a3e7eec37c857b3757a700a8fcbb3a7547e6` |
| `configs/gates/validation-analysis-v1.json` | `9ba4b92cbfa9f6a0400aa74b65cbf59d8614791efb2c5b404265a0ea455b88f8` |
| Immutable validation samples | `9854b1b1afaa78ecb6cd1c1144a0990ecf569c86c4b81f1321641e6d01bf8024` |
| Exact twelve-condition export | `a406ca34932be46279af276701417091b2c0a4e5f37206da9d0bc72befebab26` |
| Export provenance | `e3c73f5c6179a25ea0cca742e766c3b9b83f3d80496f604153ecd84a3c7cd6c8` |

Coverage is 80 items / 3,485 cells: hallucination 765, multi-hop 220, chain 220,
role association 2,280. Every selected text, token count and bullet count was
copied exactly from its source, with no extra conditions in the judge export.
The complete catalog contains 1,063,925 phrase vectors, including 421,716 new
validation encodings. It references existing tensors without copying them.
Four AR workers took 1,091–1,129 seconds each; four selector workers took
590–608 seconds each on separate four-core groups. Sequential pruning took
180.867 seconds on four CPU threads. These are campaign component wall times,
not measured latency for a single fresh input.

Samples and judgments are under `durable/runs/validation-full-grid-v1/`.
The compact export, provenance and forecast are under
`durable/selections/validation-full-grid-judging-v1/`.
Detailed collection commands and source pins are in
[experiment 025](025-blind-validation-preparation.md).

## Judge launch, cost and safeguards

GPT-6 Luna, reasoning none, Standard/default tier, unchanged benchmark prompts
and request schemas. Multi-hop uses the original deterministic matcher.
The signed dispatch spec is `configs/judging_validation_v1.json`, SHA-256
`1a5ba69c25afb3e64340c4e76ac38a0a506fb46adf51aea7a7921e593ec1e49d`.
It binds the exact export, source code, fresh activations, gate and forecast.
Expected additional judging cost is **$4.7571**, including a conservative count
of conditional second-stage requests at empirical mean prices; the atomic run
ceiling is **$15**. This is a forecast, not an invoice or a guarantee. Previous
uncertain charges stay reserved. The project target remains $200 and ceiling
$300. These benchmark costs are separate from deployment inference costs.

All work uses existing CPU job 25474685, with fixed eight concurrent requests
and 200 requests per minute per family. There is no automatic ramp. Fresh
per-family timing profiles preserve earlier DEV operational evidence. Remaining
DEV hallucination and role queues stopped at natural condition boundaries,
with processes absent and exclusive cache locks released before VAL dispatch.
Cached labels and inflight-charge records were preserved.

Chain and multi-hop started around 08:51 UTC. Multi-hop completed all twelve
condition records at 08:52:09. Hallucination and role started around 09:00 UTC,
PIDs 3372913 and 3373030. Partial completion must not be mistaken for twelve
complete four-family comparisons. The analysis entrypoint requires all expected
cells and stages before emitting its immutable comparison artifact.

At 09:40:06 UTC, the read-only operational checkpoint recorded 16,415 settled
requests, zero unknown requests and eight live requests, with $2.56375 in
usage-based charges for this VAL run. Six hallucination and four role conditions
were complete; those two evaluator sessions remain active. These are completion
counts, not quality scores. The checkpoint is
`judgments/checkpoint-launch-v1-window-v9.json` under this run's durable root.

The optional active-PID observer now uses existing indexes for complete-run
status totals and inspects only the recent attempts for the two active workers,
while retaining every unknown hold and its available cause. Its first read took
0.0117 seconds, versus 9.64 seconds for the previous monitor. Separate short
read snapshots can differ slightly during active writes. Two synthetic checks
verified preserved totals, old holds and read-only operation. No evaluator,
database schema, ledger epoch, request rate or scientific settings changed;
this does not establish the cause of earlier transport failures.

## Reporting still to complete

### Accounting lock interruption, 10:08–10:14 UTC

Both remaining evaluators exited with errors. Hallucination had completed eleven
of twelve conditions and role association seven; multi-hop and chain were already
complete. The hallucination stack failed at `BEGIN IMMEDIATE` inside the
read-only budget `snapshot()` precheck. The role worker subsequently stopped at
the shared uncertain-request guard. This identifies an unnecessary writer-lock
request on a concrete failure path; it does not establish the cause of every
earlier stall.

At 10:14:43, the VAL ledger retained 25,944 settled attempts, thirteen unknown
attempts holding $0.068209, and one abandoned reserved attempt holding
$0.005490875. All thirteen recorded failures were cancellations. The absent
worker owning the remaining reservation had no retained physical-response
evidence, so its full amount must also remain uncertain. Completed verdicts and
the original execution records are preserved. No charge has been released.

The narrow repair gives `snapshot()` a separate read-only connection and a short
consistent read transaction. Atomic reservation, settlement, spending limits,
schema and transport guards are unchanged. Eighteen offline budget tests passed,
including reading committed state while another connection holds a reserved
writer lock, a two-process spending-cap race, and preservation of uncertain
charges. Current node memory was 4.91/32 GiB with no memory-limit failures; both
project storage roots are NFS. These observations do not demonstrate that future
lock errors are impossible. Recovery of only the unfinished signed conditions
is being prepared with fresh operational evidence; no scientific menu changes.

Root applied the one abandoned-reservation transition to unknown, retaining its
entire $0.005490875. All fourteen incident holds total $0.073699875; the global
committed amount stayed exactly $16.57524863. The immutable receipt is
`judgments/hold-preserving-action-validation-v1-applied.json`, SHA-256
`7983abca16f0041287923af5e98a3b05dac156a328df90f4adaa4a62cc8c83ed`.
The terminal incident is `judgments/transport-incident-validation-v1.json`,
SHA-256 `1d7b56219a80881326bec6a041f92a99be5aa7cb3cfaac65ddd0fb729e9f68aa`.

At **10:45:14 UTC**, root sealed `configs/judging_validation_recovery_v2.json`,
SHA-256 `abbcb8c1ee87839294319bab221e4205578e3ca4db2e110979452633b91bad8d`.
The separate recovery entrypoint checks ordered, hash-bound remaining subsets
against the original full twelve-condition menu and terminal incident. It
retains the original gate, requests, caches, $15 shared ceiling and every hold.
Eight validation launch/recovery tests passed, and independent source review
found no material blocker. Completed condition artifacts are not rewritten.
Hallucination resumed its final condition as PID 3427775; role resumed its last
five as PID 3427889. Both use fresh logs, timing profiles and stop paths.

The explicitly reviewed **10:40 UTC** recovery epoch starts a new operational
health window after the documented local shutdown; it does not reset financial
totals or release old charges. Eight slots/200 RPM, Standard Luna with reasoning
disabled, and the unknown-charge guard are unchanged. There is no extra paid
health request or automatic concurrency increase. The first approximately one
hundred responses will be an observation window, not an exact call-count cap.
Successful launch alone does not establish a durable fix.

The 10:46:00 early checkpoint recorded **218 additional settled responses**, zero
new unknown charges and ten live requests with the oldest aged 1.67 seconds.
Recent per-family p95 request latency was 2.54 seconds for hallucination and
2.10 seconds for role. Every original hold remained intact. This is a healthy
early window, not proof that later stalls are resolved. Evidence:
`judgments/checkpoint-recovery-v2-early100-v1.json`, SHA-256
`0141370baacebe5ca82a70b5cf4c97692d98010aaa227aa6bd04964794153240`.

Report the original contradiction denominator together with assertion share,
off-topic rate and both hallucination stages. Keep false spans distinct from
supported and unverifiable claims. Recovery and item-ANY scores do not certify
the surrounding explanation. Show output lengths and paired whole-group
intervals for all signed conditions, including unfavorable comparisons.

Inspect the first three distinct items per changed category and a seeded sample
of unchanged cells. Include exact selected texts and frozen original judge
evidence. Report observed examples separately from prevalence estimates; do
not revise original labels after an informal audit. No interpretation is
recorded until this work is complete.

For cost, separate generating a new input's candidates, AR encoding, numeric
selection and recurring helper calls from research-wide shared computation and
cached replay. A random control retains one eligible response, but matching its
eligibility rules may require more than one generation attempt. Do not claim
guaranteed one-sample latency. GPU dollar rates remain unavailable; report GPU
time and API dollars separately.

After validation review, freeze any chosen operating points, final comparators
and ablations before issuing a separate TEST analysis gate. Blind TEST
generation currently overlaps judging under its existing metadata-only gate.

## Access record

| UTC | Scope | Action |
|---|---|---|
| 08:00:59 | Validation | Root froze the twelve-condition menu and development decision evidence before analysis authorization. |
| 08:46:50 | Validation | Exact signed-menu projection completed; no menu change. |
| 08:49:05 | Validation | Root sealed the $15 guarded judge dispatch after the read-only forecast. |
| ~08:51–09:00 | Validation | Four family evaluators launched; independent source review of reporting preserved metrics and gates. |

The numerical results, trace audit, decision and dashboard revision remain
pending and will be appended with source hashes.

### Concurrent connection errors, 11:13–11:19 UTC

At 11:14:24 the role worker's latest hundred attempts included five new unknown
charges, totaling $0.024131125, with three `APIConnectionError > ReadError`
and two `APIConnectionError > ConnectError` causes. Its recent p95 latency was
42.96 seconds. A separate 11:16:09 DEV hallucination checkpoint found three new
read-error holds totaling $0.015962 for its current worker. The failures overlap
in time; neither checkpoint records a new SQLite lock error. The observations
do not establish whether the provider, network or local resource interference
caused the failures.

Root wrote the existing condition-boundary stop files for both queues at
approximately 11:19 UTC. They allow the current condition to finish; the existing
uncertainty guard remains active. No in-flight request was deliberately canceled,
no hold released, and no rate or health epoch reset. Current terminal state and
any remaining conditions must be checked before a reviewed resumption. Validation
has priority over further descriptive development judging.

### Clean handoff to the final two role conditions

Both old workers exited zero and released their exclusive family cache owners.
The 11:30 terminal record is
`durable/diagnostics/transport-incident-boundary-1130-v1.json`, SHA-256
`efad4aec07a644a7175d8a546d49a320ccb89ce4637f81571e88e2596be2ebca`.
VAL retained 31,458 settled requests, no live reservations and 29 unknown charges
holding $0.146030375. Fifteen of those holds, $0.0723305, arose in this later
incident. All earlier and new holds remain committed. DEV hallucination adds
seven separate uncertain holds totaling $0.03762175. No financial transition or
release was needed at the clean boundary.

The role's completed-condition profile recorded 814.60 seconds in synchronous
reservations, with a 55.96-second maximum, and a 153.65-second maximum event-loop
scheduling lag. DEV hallucination likewise showed long reservation waits and
147.51 seconds of scheduling lag. These are concrete local stalls; they do not
prove the exclusive cause of the observed connection errors. The final hundred
role responses all settled, with p95 latency 1.739 seconds. The existing CPU
allocation had ample memory and zero memory-limit failures at the earlier check.

Root chose to resume only role, keeping the other writer stopped, while retaining
8 slots/200 RPM and the original 10:40 epoch. This isolates removal of competing
work without silently resetting transport guards. Four slots/100 RPM remains a
fallback to review if degradation recurs. No extra paid health request was made.
The same $.10 epoch-hold and latest-hundred guard remain active.

The exact final conditions are best-of-32 with .005 pruning and its matched-count
random-deletion control. `configs/judging_validation_role_boundary_v3.json`, SHA
`fd15526e47c9f087ddbbc89608e2e433358c25280d1cf90a809799a980b7197b`,
binds the clean terminal record, prior sealed recovery, original scientific
contract, retained holds and fresh operational paths. Nine focused tests passed
independently under root, and a separate source review found no substantive issue.
Only the exact remaining suffix is dispatched; completed conditions are preserved.
The role worker launched around 11:36, PID3459358, on the same CPU81/82 pair.

Coverage checks confirmed all46 currently available VAL family-condition outputs
are scientifically complete. DEV hallucination A8 separately has one unresolved
readout despite a clean queue boundary, so it remains incomplete. Queue termination
is not a substitute for scientific coverage.


## Complete validation and retained-trace repair (12:11 UTC)

All 48 method-family comparisons now have complete original-grid coverage and
no missing API judgments; both hallucination stages are complete. Root checked
these counts independently of the reporter. The sole final role worker exited
zero. Remaining development judging has not restarted.

The first report attempt stopped before writing an artifact because a sampled
role readout used a coalesced request. Its exact request already had a retained
response under a different layer-position key. The repair requires the same
item, byte-identical complete pinned request and expected fingerprint; it keeps
the original representative key, metadata and raw response, attaches the target
alias, and independently checks the target's official choices and gold options.
Different items/options/requests, wrong fingerprints and conflicting responses
are rejected. Four new focused tests and four existing reporting-stage tests
passed, with independent source review and root's separate four-test run.
No judge request, verdict, score or sample was changed or regenerated.

The rerun exited zero and produced the immutable source-bound report
`${OLENS_DATA_ROOT}/runs/validation-full-grid-v1/signed-menu-analysis-v1.json`
(SHA256 `db223a374f51d9122f8cc430a347e4f82dea75ce3d449008e1def1f7cf89e918`).
It includes all twelve arms, paired group intervals, output lengths and 37
paired trace comparisons. Its generation time is 12:11:10 UTC. Final operating
points and the TEST menu still require the ongoing coordinator/independent
trace review; no TEST analysis permission is granted by this completion record.
