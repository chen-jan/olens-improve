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

## Completion and interpretation

The current allocation and its sleeping batch payload end at 21:25:37 UTC. Prepare a successor CPU allocation around 19:00 UTC and transfer only at a clean condition boundary if required. Preserve all outputs, caches, in-flight work and accounting; no extra GPU allocation is needed.

Inspect only operational progress during execution. After all twelve conditions and four families are terminal, verify contracts and stage-two coverage, compute related-group paired intervals and original item aggregation, then audit wins, regressions and unchanged examples. Report both primary and secondary comparisons, family differences, output length, off-topic/empty outputs, inference effort and unadjusted-interval limitations. The best observed secondary arm is not a newly independent confirmation result. The fixed development qualitative panel explains mechanisms without changing the sealed TEST methods.
