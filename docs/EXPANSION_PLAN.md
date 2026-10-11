# Expanded comparison on all four benchmark families

Prepared 2026-10-10. **Planning only: wait for the user's start instruction and the promised single preemptable H200 allocation.** No new experiment, paid request, allocation request, watcher or active long-running goal is started by this document. The completed first study and its public version 12 remain unchanged.

## Goal to activate when the user starts the work

Evaluate the distinct, usable inference-time variants across all 469 questions in the four existing WorkspaceBench families, using the same saved activations and at most 32 original Oracle Lens samples per activation. Establish which gains survive equal-output-length controls and component ablations, report unresolved uncertainty and failure modes, and publish an interactive approach-by-task comparison with an updated report and presentation.

The intended improvement is supported information recovery with fewer contradictions, not a higher reconstruction score alone. No training or new Oracle Lens sample pools are required. All independent-reader work is postponed: no J++, NLA, second reconstructor or new reader-based selector in this expansion.

This addendum supersedes the original plan's four-GPU schedule, pilot-based shortlist, original delivery deadline and independent-reader work for this expansion only. Original results, configurations, costs and exposure history remain immutable.

## What is already available

- Four complete banks: 149 hallucination transcripts, 100 hidden-name questions, 120 arithmetic questions and 100 role questions; 19,435 fixed activation sites.
- Shared 621,920 original sampled readouts and compatible source-phrase reconstruction vectors. Reuse their exact identities and numerical conventions.
- Twelve final methods with complete development, validation and TEST evaluation. Seventeen methods have complete larger-development coverage; those counts overlap.
- Other settings mainly have a 31-question, 189-site partial-grid pilot. That pilot does not establish futility or a reliable full-question ranking.
- All 469 questions have now been inspected. Every new comparison is exploratory, including results restricted to the old TEST subset. Preserve the original frozen TEST report separately; do not label the expansion a fresh held-out test.

## Finite method inventory

Before paid execution, produce one machine-readable manifest of exact condition IDs, parent methods, candidate budget, thresholds, control-bank identity, source hashes, required artifacts, judgment reuse and status. Start from the recorded menus and the explicit controls below; do not generate an unrestricted cross-product or invent thresholds while observing new scores.

The approximately 46 displayed settings without full-bank coverage are an inventory reference, not 46 independent algorithms or a signed job count. Collapse exact aliases, retain named comparison controls, and mark obsolete implementations explicitly. Additional computed-only variants must be individually listed before launch. If cost prevents completion, report the missing settings and reason; do not call them unsuccessful methods.

| Approach | Expanded comparison | Dependencies |
|---|---|---|
| Complete readout selection | Complete the N1/2/4/8 reconstruction curve and random N16 alongside existing N16/N32 and raw/capped references. N1 scoring eligibility is distinct from capped N1. | Cached CPU work |
| Repeated statements | Exact support; repaired semantic support with ordinary and medium helper reasoning; recorded soft/cutoff, compatibility and contradiction-veto settings. | Exact support is local; semantic variants share helper labels |
| Removing bullets | Recorded stricter reconstruction-loss, zero-loss and coefficient-filter settings; single-sample pruning; matched random deletion. Preserve both .001 and .005 settings where recorded. | Cached CPU work |
| Pooling | Existing N16/N32 outputs remain reference methods; add the length controls below. | Cached CPU work |
| Activation specificity | Strongest-control comparison and the explicit nonpositive-score abstention option alongside existing mean-control selection. | Cached CPU work |
| Conditional likelihood | True-activation score, control-only score and their difference, using the first eight candidates and exactly two frozen controls per activation. | One shared GPU scoring pass |
| Editing | One and two bounded rounds; shared proposals, recorded source provenance, fresh vectors and unchanged-parent references. | Helper calls followed by GPU encoding |
| Combinations | Pooling then pruning; editing then pruning; exact support plus pooling; specificity then pruning; pooling with specificity, with and without pruning. Include component-off and matched-deletion controls. | Reuse parents and shared helper/GPU outputs |

The original 24-condition development menu contains twelve conditions outside the final twelve: best-of-N1/2/4/8; random N16; strongest-control N32; A32 pruning .001 and matched deletion; capped-N1 pruning .005 and matched deletion; mean-specificity pruning .001 and matched deletion. These provide the first cache-only tranche, not a quality-selected shortlist.

Preserve the initial malformed semantic-helper version as a historical diagnostic rather than paying to repeat its transport failures. Audit semantic equivalence for entities, numbers, negation, direction and qualifications. Ordinary/medium comparisons must use the same proposals, pair identities and exclusions. Missing compatibility labels remain unknown; do not silently treat them as safe agreement. Keep whole source bullets as the main consensus representation. Extracted-claim repair or a new editor objective is a separately versioned method, not a silent replacement of an old condition.

Use small checks to validate implementation and provenance, not to eliminate functioning methods because a noisy quality estimate is unimpressive. If a method fails its implementation contract, repair it or record that explicit block. Preserve weak and adverse results.

## Pooling length controls

Pooling selects intact bullets, but its measured average outputs are longer than the same-cap baseline. A shared four-bullet/256-token ceiling does not remove that confound.

Add two control types at N16 and N32:

1. Pooling with each activation's capped-baseline token count as its additional output ceiling. Keep whole bullets and apply the same restriction to the complete-readout fallback. Preserve explicit empty outputs and report assertion coverage.
2. Seeded random pooled selection matched to the ordinary pooled output's bullet count and as closely as possible to its token count. Freeze a bounded matching procedure, token tolerance and tie-breaking before judging; disclose unmatched cases and actual length gaps. Do not cut clauses or use benchmark answers to find a match.

Report actual length distributions and multiple-claim bullets, not only the common maximum. The reconstructor sees the first 32 cleaned tokens per bullet; separately report claims beyond that boundary without suggesting their suffixes were verified. Compare pooling with the same-N best complete readout as well as these controls.

## Three concurrent work streams

| Stream | Work | Resource |
|---|---|---|
| CPU selection | Materialize cached selectors, bounded combinations and length controls; reuse shared vectors and fits; export complete method/family outputs. | Allocated CPU cores with explicit per-worker affinity and bounded Torch threads |
| Helpers and judges | Generate reusable semantic labels and edit proposals; judge each completed method/family as soon as it is ready. | Standard GPT-6 Luna API, independent of the GPU job |
| GPU | Score N8 likelihoods with two controls, then encode new edit text in round order. Schedule likelihood shards while helpers produce edits. | **One** user-provided preemptable H200 |

Do not wait for all GPU work before judging CPU-only methods. Do not wait for every method before producing complete-family results. A finished partial cell shard is operational progress, not a full-question score until its required reading grid is complete. Prioritize complete items/groups within shards where compatible with batching.

The GPU phases share one device and must serialize model/adapter state. Switch phases at useful shard boundaries, not per cell. Retain the frozen batching/order identities where numerical sensitivity matters. The roughly eight H200-hour estimate is total GPU task time, not eight hours to add after API judging.

## Preemption and supervision

- Obtain the allocation identity from the user, then verify its ownership, type, expiry and available resources. Historical handed-back jobs are not available to this expansion. Do not request extra GPUs automatically.
- Place a lightweight persistent watcher on CPU outside the preemptable GPU job, with a separate periodic Sol review. A roughly one-minute job/progress check is sufficient; record last successful check and process identity.
- Checkpoint completed likelihood cells and publish vector shards atomically. Validate interruption and restart, including a partial final JSONL line and a tensor written before its index. Preserve saved stochastic outputs, prompts and accepted vectors.
- Resume only missing units; keep API services outside GPU allocation lifetime. A watcher detects interruption but cannot guarantee a replacement GPU. Resume on the same authorized requeued allocation if available; report resource loss otherwise.
- Keep model batches full. Checkpoint at completed work boundaries; avoid per-token synchronization or a watcher that competes for GPU memory.

No watcher is currently running. A chat agent is not a substitute for a persistent CPU monitor; monitoring stops must be explicit.

## Evaluation and evidence

Use the original complete question grids and unchanged GPT-6 Luna judge prompts/effort. Hidden-name matching remains the released deterministic rule. Hallucination requires both stages, its original specific-readout denominator, assertion/off-topic coverage, and supported/unverifiable tallies. Do not convert API failures into successful abstention.

Keep per-question recovery distinct from per-activation matches and whole-output faithfulness. Show denominators and related-group counts: the full banks have 149 hallucination groups, 94 hidden-name groups, 42 arithmetic groups and 50 role groups. Adding methods to these same groups does not increase the sample size for an existing method.

Before examining new results, freeze the named baseline/parent contrasts and the family of headline comparisons used for multiplicity adjustment. Report paired whole-group uncertainty and simultaneous uncertainty across those declared contrasts, after validating the statistical implementation. If reporting p-values, obtain them from valid paired/group tests and apply Holm correction over the declared comparison family; this is separate from simultaneous confidence intervals. Do not infer adjusted p-values from the old pointwise intervals. Adjustment does not remove the adaptive history of the methods or create an unobserved test set. Keep observed effect sizes and costs visible; interval overlap alone is not an elimination rule.

The fixed menu receives the full feasible bank rather than another quality-based pilot shortlist. If precision is still inadequate, state what meaningful gains remain compatible with the evidence. Fresh independent questions would be a separate follow-up; changing to 99% intervals or adding more sites to existing questions does not supply those questions.

Sol agents inspect fixed examples of wins, regressions and unchanged outputs for each method or substantive comparison. Reuse a common outcome-blind anchor set plus clearly labeled changed cases. Record baseline/new text, source IDs, official judge evidence, and observed versus hypothesized failure mechanisms. Preserve official scores when an audit finds judge mistakes; report disagreement separately.

## Runtime, spending and storage

Forecasts use the existing logs and are not completed new measurements:

- Additional GPU work: approximately **eight H200-hours** (5.6 likelihood, 2.2 edit encoding, rounded), with likelihood fixed to eight candidates/two controls. Queueing, model reloads and preemption retries can increase elapsed time.
- Total wall time on one H200 with concurrent CPU/API streams: plan **12–20 hours after execution starts and resources are available**. Reforecast from the first sustained production batches. Additional GPUs are not assumed.
- Approximately $3.78 judging per completely changed full-bank output condition before exact cache savings; roughly $230 extra API usage for the earlier broad-menu estimate. The new length controls and any separately repaired settings require an updated exact request forecast; a practical initial expectation is approximately **$230–250 extra**, or **$271–291 project total**.
- Existing committed amount: **$41.36733756**, consisting of $36.50759506 usage estimates plus $4.8597425 retained reservations. Preserve every uncertain hold.
- The user accepted roughly 30–40% overrun. Use a conservative **$340 total project operating ceiling** when execution is activated: approximately $230 extra plus a 30% contingency plus existing commitments. At a $250 forecast, the same ceiling leaves a smaller contingency; do not automatically compound the allowance. This stays below either a 30% increase on the former $300 ceiling or the upper 40% allowance. It is a spending limit, not a target. No ledger ceiling is changed during this planning turn. GPU dollars and research-agent billing remain unpriced and separate.
- Storage: approximately **30–60 GB extra persistent data**, reaching 129–159 GB from the measured 98.704 GB baseline. Reserve 100 GB extra working space, for approximately 200 GB project peak. Reused external 55.563 GB model weights require no additional copy. The aggregate storage allowance stays 500 GB; verify actual shared-group headroom at launch.

Use the reviewed reservation batching, exact-request caching and bounded high concurrency from the final judging run. Benchmark helper throughput with real initial work and increase concurrency while monitoring latency, limits and ledger health; the old four-slot helper runs are not a sensible full-bank schedule. Preserve per-request records and budget checks. Avoid repeated full ledger copies and duplicate sample/vector exports; keep large artifacts in the existing fast/durable project roots.

## Dashboard, report and completion

Build an interactive approach-by-four-task matrix from versioned results. Expand an approach to exact variants; switch between full bank, original TEST, development and pilot; show paired change, interval, question/group count, coverage, actual length and inference effort. Missing evaluations remain visibly unmeasured. Clicking a point opens methods, examples and costs. Never compare unlike cohorts as though they were paired or average the four unlike endpoints into one accuracy.

Refresh the public dashboard at reviewed milestones, then update the plain-language report and editable/PDF slides. Lead with actual benefits, costs, tradeoffs and remaining uncertainty. Retain links to the original study and label new evidence exploratory. Research Git commits remain local; the user handles pushing.

Completion requires every exact manifest setting to have either complete four-family coverage or a specific unresolved status with evidence; parent/component/length controls; paired analyses; systematic qualitative review; an updated dashboard and presentation; and reconciled usage, storage and GPU-time reporting. Mark time-limited work unfinished. No blanket claim that a method family fails can rest on a small or broken pilot.

## Start handoff

**Waiting on the user's start instruction and one preemptable H200 allocation.** Until then, only plan/documentation work is authorized by the current request. The next execution turn should validate this plan, seal the exact menu and resource/cost forecast, assign CPU/API/GPU-monitoring responsibilities, validate restart behavior, then start concurrent work. No paid or GPU process is active for the expansion.
