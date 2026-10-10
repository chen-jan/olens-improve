# Expanded held-out comparison

Status: all four evaluators launched at 14:58–14:59 UTC on 2026-10-10. No TEST quality has been inspected yet. This measures the prospectively sealed twelve methods and controls from [experiment 038](038-expanded-heldout-comparison.md); it does not change their settings or the two validation-selected operating points.

## Exact scope

The comparison covers all 268 held-out items, 200 related groups and 10,714 original read cells across the four agreed families. The original six primary conditions run first, then the six secondary comparisons. All use the same retained maximum-32 sample pool. Original released N1, capped N1, random selection and matched random deletion remain explicit controls. The underlying source, prompt, whitening, output-cap and judge contracts are unchanged.

The immutable twelve-condition export is `runs/test-full-grid-comparison-v2/judging-inputs.jsonl` under the durable project root, 77,719,435 bytes, SHA `ae8b6a6e4fdb4eb57f8d4dcabf184071a258ad2bb55e9abc05159798c7472196`. Each condition has exactly 10,714 rows. Its provenance SHA is `ddd2e0e103041e807799e6a9dd639a43d3068c7b881383e09e600eb109b93db2`; exact text and duplicate parent consistency were checked without inspecting quality. The signed menu, freeze and analysis gate remain in the v2 configurations.

## Forecast and dispatch

`forecast-v2.json` in that directory, SHA `f39c259138f6a2cc4ad6a9f9832014577bfb736377691fb7242397c19ce5f8ff`, counts 29,077 new unique hallucination stage-one requests, 6,935 chain requests and 52,027 role requests. Up to 29,077 new hallucination stage-two requests depend on the returned stage-one spans. Multi-hop recovery uses its deterministic evaluator.

Using frozen empirical mean prices, expected usage is $11.35 for known requests and **$19.01 including the conditional stage-two upper count**. This is an estimate, not a bill or hard bound. Root approved a finite **$40 shared TEST run ceiling**, retaining the $200 project target, $300 hard ceiling, every previous uncertain charge, the authoritative ledger and original 07:52 UTC recovery epoch. Formal maximum-output reservations are much larger than expected charges; atomic run/project limits remain enforced.

The mean-service references are 6.04 hours for hallucination, 4.34 hours for role binding and 0.60 hours for chains. Family workers overlap, but conditions and hallucination stages retain their dependencies. I/O, retries, startup and review add time. Final delivery may need 1–3 hours beyond the original 20-hour target; the user was informed before dispatch.

The root-sealed specification is [judging_test_v2.json](../../configs/judging_test_v2.json), SHA `e052bc4cc8c00401dff62a0d1810760b09f0383e96cfa15252ac765b2d304941`. Evaluation and model reviewers checked all source pins, export/menu identities and the cost bound. Independent resource checks found free family locks and 7.8–8.0 GiB charged in the 32-GiB CPU allocation. Validation-only preflight passed. Luna remains the only benchmark judge, Standard/default tier, reasoning none, eight slots and 200 RPM per family, without an automatic ramp.

| Family | Root session | Worker PID | Physical CPUs |
|---|---:|---:|---|
| Hallucination | 36152 | 3548162 | 24, 30 |
| Chain intermediates | 26916 | 3548213 | 33, 38 |
| Role binding | 76414 | 3548330 | 81, 82 |
| Multi-hop | 1076 | 3548389 | 83, 84 |

All workers use job 25474685/node1600 and the existing exclusive family cache locks. The first hall launch failed before Python because PATH selected a nonexecutable `env` shim; using `/usr/bin/env` resolved it without dispatching a duplicate API request. Source-bound initial owner receipts are `diagnostics/test12-family-handoff-v1/preflight.json` and `role-preflight.json`.

At 15:02:42 UTC, one bounded operational checkpoint found **2,187 settled requests, 19 in flight and zero new unknown charges**. Usage accounted to this TEST run was $0.2758404; active reservations were $0.096724125. This is an early run snapshot, not project-total or invoice accounting. Provider p95 was 3.08 seconds for hallucination, 1.77 for chains and 2.31 for roles. The four-minute whole-run rate was about 548 settled responses/minute across families; individual latest-100 windows were about 145–159/minute and are not cumulative worker rates. Multi-hop completed with no API attempts, as expected. The read-only query took 3.38 seconds and closed its connection. Receipt: `diagnostics/test12-operational-v1/first-checkpoint.json`, SHA `c70f03a77f9a66ba3ac89fac0eb2be17982317467962c06500d136fb30da36ef`.

The fixed concurrency is deliberate: an earlier reviewed increase to sixteen slots/400 RPM coincided with worse measured throughput and transport failures ([023](023-judge-transport-recovery.md)). That observation does not establish a cause, but gives no measured reason to repeat the increase on this final queue. More GPUs do not accelerate the current external-judge bottleneck.

## Completion and interpretation

The current allocation and its sleeping batch payload end at 21:25:37 UTC. Prepare a successor CPU allocation around 19:00 UTC and transfer only at a clean condition boundary if required. Preserve all outputs, caches, in-flight work and accounting; no extra GPU allocation is needed.

Inspect only operational progress during execution. After all twelve conditions and four families are terminal, verify contracts and stage-two coverage, compute related-group paired intervals and original item aggregation, then audit wins, regressions and unchanged examples. Report both primary and secondary comparisons, family differences, output length, off-topic/empty outputs, inference effort and unadjusted-interval limitations. The best observed secondary arm is not a newly independent confirmation result. The fixed development qualitative panel explains mechanisms without changing the sealed TEST methods.

## Operational continuation, 2026-10-10

The original hallucination and role workers stopped during raw N1, their first condition. Both traces identify `sqlite3.OperationalError: database is locked` at the ledger's `BEGIN IMMEDIATE` reservation step. The fatal wrapper prohibited a new dispatch. This was a local reservation failure; the upstream `SpendCapError` type does not mean the financial ceiling was exceeded. The lock holder and initiating cause remain unresolved. The terminal timing profiles show one reservation error per worker, with a maximum reservation duration of about 39 seconds; their event loops remained responsive.

At 15:30:45 UTC, the bounded operational checkpoint recorded 14,726 settled requests, six unknown charges totaling **$0.029525125**, and four short-lived active reservations. Five unknown attempts came from the stopped hall/role workers; one later chain attempt retained an `InternalServerError` charge. A subsequent point-read found no abandoned reservations for either stopped PID. Every unknown amount remained held, no attempt was reclassified or released, and no financial or transport epoch was reset. The immutable incident receipt is `diagnostics/test12-operational-v1/terminal-hall-role-incident-v1.json`, SHA `6843df47cada6eacb8ba4f1cf1a6b1e9902f12568a413fca7941ca83fdc294f0`; it binds the checkpoint, traces, profiles, source hashes and retained attempt IDs.

Root sealed [judging_test_continuation_v3.json](../../configs/judging_test_continuation_v3.json), SHA `23163a9ebbe68a06adf0d9a02954a6b8f064bc50ee9cbd9a343f5b002b3b10bb`, after authority validation and a fresh cache-owner check. The original operational specification remains unchanged. The continuation preserves the same run ID, $40 ceiling, twelve-condition order, source pins, exact request cache, Luna settings, eight slots/200 RPM and original 07:52 UTC guard. Fresh log and timing directories preserve the failed execution evidence. There was no separate paid probe.

Hallucination resumed in root session 12826/PID 3595134. At 15:46:30 UTC, its latest-100-attempt window contained 93 settled responses and seven active reservations, zero new unknown charges, response p95 3.42 seconds and oldest active age 2.93 seconds. The read-only checkpoint took 0.282 seconds and closed its connection; it is a recent window, not a cumulative throughput estimate. Receipt: `diagnostics/test12-operational-v1/continuation-v3-hall-first-checkpoint.json`, SHA `9015d11c375fd1be522c12e9ce48e5e980521a103ed5b0f2fa64684ca4d11781`.

After reviewing that observation, root resumed role binding in session 51027/PID 3598846, with conservative worker bound 15:47 UTC and unchanged settings. Its first placement command failed before Python/API execution and was corrected without duplicate calls. Multi-hop and chains are terminal exit zero; hallucination and role remain active. No TEST quality has been inspected, and complete scientific reporting still waits for all twelve conditions in all four families.
