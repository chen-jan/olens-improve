# Twelve frozen validation comparisons

Status: running, 2026-10-10 09:40 UTC. All generation, reconstruction,
selection and exact-text exports are complete. All four family evaluators have
started; multi-hop matching and chain judging are complete. No validation quality conclusion is
reported yet. TEST analysis remains closed.

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
