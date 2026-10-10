# Experiment: {ID — short title}

Use one record per meaningful experiment, including negative results. Replace placeholders, mark unmeasured fields explicitly, and link compact manifests and raw evidence.

## Key findings for a new reader

Lead the report/dashboard with: **what improved versus the released lens; measured size and uncertainty; families tested; run status, time and spend; main limitation and next action**. Define technical terms and distinguish measured results from proposals.

After scoring and trace audit, update the dashboard's reviewed 3–5 main findings and this method's tab. Record dashboard revision, run IDs, timestamp, synthesis reviewer, baselines, wins/regressions/unchanged cases, and next decision. Label partial counts; keep progress separate from scientific conclusions and test views sealed until the planned reveal.

## Status and question

- **Status:** planned / running / completed / failed / stopped / incomplete (time-limited)
- **Created / updated (UTC):** {timestamps}
- **Experiment / parent / run IDs:** {IDs}
- **Question:** {one testable question}
- **Expected failure mode:** {what could make the method ineffective or the comparison misleading}
- **Single change:** {exact difference from the frozen baseline; list unavoidable coupled changes}
- **Decision rule:** {effect size, traces, consistency, regressions, cost and uncertainty; practical tolerances before validation; promotion, revision and stopping criteria}

## Frozen inputs and procedure

- **Data:** {families, source URLs, WorkspaceBench revision, bank paths and hashes}
- **Target model / released O-lens:** {exact model ID, model revision, adapter/checkpoint ID and hashes}
- **Rendering:** {prompt/template text or hashed artifact, tokenizer revision, layer numbering, injection recipe, activation capture precision}
- **Scope:** {immutable item IDs, source/template groups, positions, layers and split-manifest path/hash; expected items and cells per family}
- **Access boundary:** {information available to generation, selection and judging; labels and near-miss answers restricted to designated evaluation/calibration steps}
- **Candidate pool:** {ID/hash, samples per cell, seeds, decoding/stopping settings and provenance; shared nested prefixes}
- **Selector:** {algorithm, thresholds, fitting/calibration data, tie-breaking, search budget and final output caps}
- **Reconstruction:** {reconstructor revision, whitening/centering artifact and calibration source, regularization, normalization, coefficient constraints and exact FVE definition}
- **Judge:** {exact GPT-6-Luna ID, effort `none`, Flex by default, prompt/schema and exact rendered-input hashes, parsing/retry policy; cache identical calls and record deviations}

Keep source/template siblings and control twins together. Never use held-out answers to create deployment candidates or tune their selector. Changes after freezing require a version and explanation.

## Comparisons and measurements

Every proposed final output has **at most four bullets**. Retain raw released O-lens **N=1** and a deterministic same-cap N=1 reference. Freeze cap/token/claim rules after the length pilot and before comparisons. Include **best-of-N complete readouts from the same pool**, random selection, and matched token/claim-length controls where relevant. State generation, selection and output budgets.

For combinations, compare components alone, the full combination, and the full combination with each component removed in turn. A full factorial is not required. Use identical candidate availability and output budgets; show equal-compute comparisons when possible.

| Family / arm | Items / cells | Transcript contradiction | Target recovery | Assertion / off-topic | Tokens / bullets / claims | FVE |
|---|---:|---:|---:|---:|---:|---:|
| {name} | {counts} | {value, denominator} | {value, rule} | {values} | {distributions} | {value, definition} |

Report families separately and paired item/group confidence intervals: resampling unit, seed and replicates. Specify denominators and extractor/judge versions. Contradiction does not establish absent activation content.

Show quality-versus-budget curves and the error/recovery frontier with uncertainty. Quality takes priority within the current cap of **32 total O-lens samples per activation/cell, shared across methods**; compare nested N=1,2,4,8,16,32 prefixes, not fresh pools per method. Samples above 32 and residual O-lens resampling are deferred until the user revisits scope. External-editor proposals are separately capped and logged. Freeze prefix-escalation and operating-point rules before test. Label cross-family error/recovery plots as different cohorts, not a within-cell tradeoff. Observed flattening over tested N values is not a scaling law.

For main/final hallucination comparisons, run **both stages**. At readout level define W = verified contradiction, O = off-topic, C = consistent. Report headline **W/(W+O+C)**, assertion share **(W+O+C)/all readouts**, and secondary **W/(W+C)**, with zero-denominator handling. Report stage-2 coverage, missing tallies and true/false/unverifiable counts. False counts originate from spans; do not present them as uniformly segmented atomic-claim error rates. Disclose limited power; never reject a pilot merely for nonsignificance.

## Completeness, cost and artifacts

- **Coverage:** {expected, produced, parsed, judged and missing counts; failures, retries, truncations and exclusions with reasons}
- **Abstention:** {empty/generic outputs reported separately from missing or failed cells}
- **Compute:** {scheduler job IDs, GPU types/counts, actual GPU-hours and wall time}
- **API:** {calls, input/cached/output/reasoning tokens, rate/tier, billed spend, estimates and remaining budget; reserve for in-flight calls and retries}
- **Phase and forecast:** {generation/scoring/judging stage, elapsed time from actual execution start, remaining work and forecast against the 20-hour target; GPU-hours, API dollars and wall latency separately}
- **Bottleneck and optimization:** {slow stage, before/after throughput and quality checks; judging p50/p95 latency, concurrency, backoff, timeout/unknown-charge accounting and diagnostic costs}
- **Storage:** {paths, sizes, retention and cleanup plan; what is cached versus inexpensive to regenerate}
- **Reproduction:** {code commit and dirty patch hash, commands/config paths, environment/dependency versions and seeds}
- **Artifacts:** {activation, candidate, selection, judge and result manifests; compact evidence paths}

Keep secrets and large artifacts outside Git. Retain compact provenance and expensive stochastic samples needed for paired comparisons.

## Inspection evidence and interpretation

Include **2–3 wins, 2–3 regressions, and a random sample including unchanged cases**. Say `none observed` where appropriate; record the sampling rule. For each case provide item/group/cell IDs, raw baseline and proposed text, judge evidence/verdict, and why the change matters. Separate observations from hypothesized explanations; consider deletion, wording, judge disagreement and common candidate-pool errors.

**Conclusion:** {promote / revise / stop, supporting result, negative findings, limitations and next experiment}

A single-family gain with wide intervals can merit follow-up. Use judgment, without a significance gate; distinguish promising evidence from an established improvement.

Work omitted for time is **incomplete/time-limited**, not a failed prerequisite or negative result. Record what remains and how it affects the conclusion.

If judging blocks progress, log any bounded Standard-tier fallback using the same Luna model, effort and prompts; forecast its cost before dispatch. A tier change is not a speed guarantee.

## Validation and test access ledger

| Timestamp | Split / manifest | Person or process | Outputs inspected | Purpose / resulting decision |
|---|---|---|---|---|
| {UTC} | {ID/hash} | {name} | {scope} | {decision} |

Log every inspection. Validation reused for tuning becomes development data. Keep test results sealed until configurations and decision rules are frozen; repeated test peeking requires disclosure and a fresh independent confirmation set.
