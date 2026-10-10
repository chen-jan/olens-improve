# Increasing judge concurrency

The remaining comparisons use Luna Standard with reasoning disabled. The
existing limit of eight concurrent requests and 200 requests/minute per family
is our recovery configuration, not a verified provider limit. The user permits
Flex where its latency can be absorbed without delaying completion; the two
current queues are on the critical path and remain on Standard.

At 18:00 UTC, a bounded accounting check found 3,039 additional settlements in
616.309 seconds, about 296/minute across both workers. No new uncertain charges
appeared. Recent short windows were about 188/minute per worker. Long database
holds are present in the logs, but their untimestamped entries cannot establish
that the same delays persisted throughout this measured window. Neither a
provider limit nor an individual slow filesystem operation has been identified.

## Prepared change

Root reviewed an explicit option for **one family at 16 concurrent requests and
400 requests/minute**. The hallucination worker keeps its existing settings.
The role worker received SIGUSR1 at 17:55:22 UTC to finish its current comparison
and stop at the boundary. No in-flight requests were cancelled.

The launcher previously hardcoded the old limits both in its preflight and in
the imported function that builds the actual worker command. The change checks
an explicit review bound to one family, run and unchanged accounting epoch, and
uses those settings in both the worker and forecast arguments. Validation
launches remain restricted to their prior settings. All scientific inputs,
caches, accounting semantics, financial caps and uncertain-charge guards are
unchanged. Twenty-five offline tests passed, including actual command arguments
and rejection before dispatch. Root and an independent agent reviewed the code.

`configs/judging_test_role_concurrency_v7.prepared.json` passed validation with
zero API calls. Its prepared status prohibits paid dispatch. Root must still
verify the old worker's clean exit, a free cache owner, and current accounting
before sealing a separate ready specification. The original request-cost
forecast still prices the same logical requests; its old throughput assumptions
do not forecast the new transport. Retries can add cost.

## Decision after launch

Measure completed responses, errors, retained uncertain charges and transaction
delays. Do not presume twice the throughput. Any change to another family needs
its own review. If the new setting worsens progress or errors, request a clean
boundary stop and retain all saved responses and charges.

Source review: `configs/test_transport_review_v1.json`. The operational health
receipt is `durable/diagnostics/test12-operational-v1/continuation-v6-health-1800-v1.json`,
SHA `35f889cc58132f1f52f95f8329891e598dc985951803bee9516dcff95b834522`.
At preparation, the role worker remains live and the faster setting has **not**
been launched.


## First-family launch

At approximately18:10 UTC, root sealed
`configs/judging_test_role_concurrency_v7.json`, SHA
`59f40157b0c41845dedf1ee3da3986290c4353f9e617008386ecc1e831f8eaf8`,
and resumed role binding as PID3690209/session80782. The old role worker had
exited0 after Emean, with the next condition D16. Its exclusive cache-owner
probe was free. The terminal accounting receipt retained all prior charges and
found no new role reservations or unknowns. Hall PID2407614 remains at8/200.

The closed Emean profile at8/200 contained3,754 successful reservation,
evidence and settlement operations, with no recorded exceptions. Its maximum
reservation delay was41.233558 seconds. This establishes that a long delay
occurred within the active condition, rather than assigning all logged delays
to cached-condition setup. It still does not identify a particular filesystem
operation as the cause. New throughput and error measurements are required
before changing any other family.

## First measured outcome and stop request

The18:16:31 checkpoint found49,418 TEST settlements and$7.16114223 estimated TEST usage. All12 uncertain TEST charges remained$0.059636875;18 active/retained reservations totaled$0.090369875, including the old inactive hall hold. Recent100-attempt windows were31.59 settlements/minute for hall and34.72 for role, with oldest active reservations141.08 and140.78 seconds. New admission holds reached44.872 and51.302 seconds. API response timings were much shorter. These windows differ from the earlier combined measurement and do not isolate causality, but they do not justify a further ramp.

Receipt: `durable/diagnostics/test12-operational-v1/continuation-v7-role-health-1815-v1.json`, SHA `584a6c81e31c59d613549061fb3ef18fd56e8bec421ecca00d875dc87337da0d`.

At18:21 both exact worker commands remained live. One role thread was in disk sleep, while wait-channel visibility was restricted. No new closed condition profile or fatal log error appeared. Root sent both workers SIGUSR1 at18:21:49 to finish their current conditions and stop before starting another. No calls were cancelled. Planned recovery is8/200 after diagnosis; opt-in phase timing is being prepared. A possible move of the complete single authoritative ledger to fast compute is not yet executed and is not a proven cure: both mounts are network filesystems. Preserve every event, cap and unresolved hold, and never permit two active ledgers.


## Closed-condition result supersedes the initial slowdown inference

At18:28:55 UTC, TEST had54,378 settled attempts, $7.79799183 estimated usage, the same12 unknowns/$0.059636875, and only the old inactive reserved hold/$0.00538675. The interval since18:16:31 added4,960 settlements over744.009 seconds:400/minute combined. Do not interpret a short slow window as the sustained effect of higher concurrency.

Both workers exited0 after their requested boundaries. Hall A32 completed3,704 physical responses in1,560.306 seconds (142/minute). Role D16 completed5,701 in1,137.235 seconds (301/minute), versus the earlier Emean8/200 condition at149/minute. Conditions, caching and competing traffic differ, so these are operational rates, not a randomized estimate of the concurrency effect. All reservation/evidence/settlement error counts were zero. Maximum observed operation durations still reached136.47 seconds for hall reservation and101.55 seconds for hall evidence, motivating finer timing and the proposed storage move.

Terminal receipt: `durable/diagnostics/test12-operational-v1/continuation-v7-both-boundary-preflight-v1.json`, SHA `773005fd90234289771015aae23e1bf570e2044681a0b26331732393021a3363`. It binds the18:28 health receipt SHA `9376e28f96aa3f4dea8f65918f42dd68df4e404a74da5df300b69ad94e877d2c`. Hall next evaluates random32; role next evaluates D32. No scientific outcomes were reviewed.
