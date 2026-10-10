# Frozen Oracle Lens: inference-time improvement plan

Updated: 2026-10-10 UTC. Status: execution started at 2026-10-10 01:25:36 UTC (October 9, 21:25:36 EDT). The user has authorized autonomous implementation and experiments while away, within this plan's limits. Routine steps do not need fresh permission. See [STATUS.md](STATUS.md) for current progress and recovery instructions.

Read [METHODS.md](METHODS.md) for concrete A–G algorithms, shared data flow, helper-model costs, failure checks, and the iterative development loop. This plan remains authoritative for scope, frozen contracts, evaluation, and resources.

## Objective and frozen contract

Improve the released Camila WorkspaceBench Oracle Lens through inference-time sampling, selection, pruning, composition, or editing. **Maximum quality is the priority**, within the authorized time, spending, and storage limits. Prioritize useful factual recovery and fewer contradictions; reconstruction-score gains alone are insufficient. No gradients, adapter updates, or new model training.

Terms: O-lens means Oracle Lens; AR means activation reconstructor; FVE means fraction of variance explained; NNLS means nonnegative least squares; N is the number of candidate samples. Explain other abbreviations on first use in every delivered report.

Freeze these revisions before execution:

| Component | Identity / revision |
|---|---|
| Target model | `Qwen/Qwen3.6-27B` / `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9` |
| Released O-lens | `agu18dec/olens_and_ar`, directory `olens_s3d_rl600` |
| Matched reconstructor | Same repository, directory `ar_ptag_pooled` |
| Paired repository | `c95215d5d2f6250f20c305ae55c6e4d7569f92dc` |
| WorkspaceBench | `92d763e722377f5bfae045e829a308ab5919a820` |

The WorkspaceBench default points to `agu18dec/local-workspace:ckpts/ao/rl/s3d.ddp600.s0/iter_000600`, the paired release's documented source. This preserves the released lens. The `iolens.final.ddp600` lineage is separate; its reported FVE is not comparable.

Read with `concepts_raw` and inject `16000 * h / ||h||`; the supported band is layers 20–60, step 4. Use each family's exact grid below. Capture with the adapter disabled. Layers index decoder-block outputs, not blindly indexed hidden-state tuples. Manifest the tokenizer revision, carrier, marker, dtype, hooks, and sampling settings. Qwen has 64 hybrid layers, width 5120; use its correct loader.

Validate that the adapter changes logits, merging preserves behavior if used, and capture is adapter-free. Unit normalization for injection is distinct from whitening for scoring. The AR maps text to activation predictions; misleading activation-to-text wording and inconsistent output-shape examples in the card must not define the implementation. Inspect the actual loader and checkpoint.

Before trusting FVE, obtain the matching whitening statistics and verify centering, transformation, regularization, layer indexing, NNLS objective, denominator, aggregation, and clipping against source code and a reproducible fixture. The paired repository omits the whitening files; access to the source dataset was resolved after the user accepted its agreement. The 11 needed files total 1.15 GB. Missing or invalid whitening blocks AR-guided scoring, not plain O-lens sampling or a consensus-only baseline; continue independent work. Do not substitute raw cosine similarity or another whitener and label it the published FVE.

## Existing material to reuse

Treat `${OLENS_SOURCE_ROOT}` as read-only. Preserve its checkouts, caches, results, and credentials. Useful paths relative to it:

- `docs/journal_entries/2026-09-30-wsbench-v2.md`: historical setup and limitations.
- `experiments/wsbench/patches/openai_route.patch`: Luna judge routing recipe.
- `outputs/wsbench/plan` and `scratch/repos/workspace-bench-v2`: plans, banks, and source.
- `scratch/wsbench/cells`: 334,597 cached bfloat16 (BF16) vectors across 25 families, approximately 3.426 GB.
- `outputs/wsbench/{readouts,judged,analysis}`: historical outputs and analyses.
- `experiments/wsbench/olens/`: producer and timing-related code.

Audit cached vectors against exact prompt/token IDs, model, dtype, layers, positions, adapter state, and capture provenance before reuse. Compare a small recapture when execution begins. Cache existence does not establish compatibility.

The audit did not establish an actual O-lens result; stand-in-adapter timing is not a baseline. Reproduce a real baseline. Historical totals were $117.1766 for the old campaign, including $59.9612 for jailbreak and $11.1954 for hallucination: neither per-method estimates nor charges against the new $300 budget. Exclude answer-derived template dictionaries. Old displayed floors used Gemini, not Luna; GPT-5.6-Luna passage-generation experiments are separate.

## Evaluation design

Start with four complementary families. Proposed counts refer to bank items:

| Family | Total | Development | Validation | Test | Purpose |
|---|---:|---:|---:|---:|---|
| Hallucination | 149 | 30 | 20 | 99 | Transcript contradictions and verifiability |
| Multi-hop, multi-token | 100 | 31 | 20 | 49 | Recovery of complete bridge concepts |
| Chain intermediates | 120 | 30 | 20 | 70 | Intermediate computational content |
| Role-bound association | 100, in 50 pairs | 30 | 20 | 50 | Entity–role binding and swaps |

Run these four core families first. Exclude jailbreak initially; reserve `arithmetic_intermediates` for later transfer, with `multi_concept_directed_modulation` an optional pooling diagnostic.

Construct and freeze an item-level split manifest before new lens outputs. Keep role pairs together and group related examples, including chain templates; adjust counts if grouping requires it. Save IDs, group keys, seed, bank hashes, exclusions, and rationale. These historical banks were previously analyzed. The holdout measures generalization of the new scaffold; it is not previously unseen research data.

The current manifest is `configs/splits_v2.json`. During the initial development-only audit, four multi-hop bridge aliases crossed the v1 boundaries. V2 groups canonical names and bank-provided aliases together, keeping all previously designated development items in development. This moved one additional item into development, yielding 31/20/49; no held-out readouts were inspected. V1 and the supersession record are retained for provenance. Activation rows are unchanged; their split/group bindings follow v2.

Freeze shared representative development subsets: 5–10 items per family for the pilot, with pairs intact, then approximately 120 development items, a validation shortlist, and the frozen test. All runnable methods use the same subsets. Exact grids: hallucination `20,36,44,52,60`; role-bound `20,28,36,44,52,60`; multi-hop MT and chain `20,24,...,60`. Chain uses the final-token default, never accidental all-position evaluation. Manifest positions and cost units.

Use the existing `gpt-6-luna` Flex, reasoning-effort `none` recipe for judged families, with method-blind prompts and fixed prompt versions. Multi-token exact recovery uses the deterministic regex contract; keep it separate from judged semantic claims. Raw O-lens prose does not need a token-bag summarizer. Any auxiliary semantic evaluation is separately named and costed.

Luna remains the sole benchmark judge; Qwen is not a planned benchmark judge. Initially, helpers also use Luna: Standard for blocking selection/edit steps and Flex for offline work. Forecast that mix within the unchanged budget. Primary consensus retains verbatim bullets; rewriting/splitting is a separate ablation. See [helper roles and optional local comparison](METHODS.md#which-language-model-calls-cost-extra).

For benchmark judging, default to Luna Flex with reasoning `none`; [Flex trades latency and availability for cost](https://developers.openai.com/api/docs/guides/flex-processing). Use bounded asynchronous calls, exactly matching cached judgments, capped retries/backoff, and queue/completion latency, throughput, error, and cost monitoring. Preserve full evidence and judge prompts. If Flex stalls the critical path, use the same Luna model/settings on Standard for bounded deadline-critical requests when the revised forecast fits the authorized budget; announce and log the change. Neither tier guarantees latency. Reconcile uncertain outstanding requests and reserve their cost before redispatch.

Diagnose unreasonable delays in every phase; optimize batching, caching, and independent shards without changing comparison controls. Track median and 95th-percentile wait/completion times, requests/tokens per minute, failures, and retry costs.

The primary error endpoint is **transcript-contradicting readout rate**, using the benchmark's unrevoked `wrong / (wrong + off_topic + consistent)` headline. Always report assertion share, `(wrong + off_topic + consistent) / all_readouts`, and off-topic rate: junk or silence must not appear to improve fidelity. Add `wrong / (wrong + consistent)` as a supplementary diagnostic, not a replacement headline. Require hallucination stage 2 for main/final comparisons; report true, unverifiable, disputed, and false tallies and missing-stage-2 coverage. Never call unverifiable content false. False tallies count established spans whereas true/unverifiable tallies enumerate claims; do not treat them as uniformly segmented claim precision.

Report recovery separately by family, with words/tokens, claim count, uncertainty, abstention, denominators, and item/group-respecting paired intervals. No single macro should hide tradeoffs. Inspect representative wins and regressions.

## Baselines, methods, and diagnostics

Retain the raw released baseline: temperature 1, top-p .95, top-k 64, maximum 256 new tokens, one sample. All proposed final readouts have at most four bullets and 256 Qwen text tokens. The primary parser preserves each contiguous source block between dash-bullet markers, including continuation text; it never rewrites or deletes qualifications inside a bullet. Compound claims remain verbatim and are counted/audited separately rather than invoking a rewriting helper to enforce a claim count. The common token ceiling limits phrase packing. Non-bullet preambles are flagged as uncertain. Keep the initial strict single-line parser as a separate ablation: it rejected six of sixteen pilot samples, creating a substantial abstention confound. Add a deterministic same-cap N=1 comparator that drops complete trailing bullets to meet the cap, without selecting by FVE or cutting within a bullet. Report length differences and matched shortening/random-deletion controls; never replace the raw baseline silently.

The current cap is **32 O-lens samples per activation/cell, shared across all methods**, not a fresh 32 for each method. Use nested prefixes N=1,2,4,8,16,32; samples above 32 are deferred until the user revisits the cap. Quality remains the priority within this limit. Prespecify prefix-escalation rules on development; report observed scaling/saturation without claiming a scaling law. Persist strings, order, seeds, batching, tokens, truncation, and AR predictions/scores. Batching changes RNG consumption; retain outputs. Bounded external-editor proposals are separately counted and logged, not new O-lens pools.

Test all seven on the shared representative development subset when runnable; otherwise record the failed prerequisite. Targeted F/G failure diagnostics are additional and separately reported. Staging limits expansion, not coverage; specific variants such as a second compatible AR may be unavailable. Avoid an exhaustive cross-product:

| Approach | Proposed comparison and principal risk |
|---|---|
| A. Best-of-N | Select a complete sample by joint NNLS FVE across shared prefixes up to N=32. The AR is also the lens's training reward, so independent quality matters. |
| B. Consensus | Count support across distinct source samples; compare with A at fixed budget. Shared hallucinations can dominate, and rare correct details can disappear. |
| C. Pruning | Remove low-value or unsupported bullets from complete samples. Redundancy is not falsehood; retain the complete-sample control. |
| D. Pooled composition | Select up to four bullets from the pool using greedy NNLS and optional local swaps. Check contradictions and incompatible bindings explicitly. |
| E. Contrastive scoring | Test specificity against matched activations, semantic near misses, and true-versus-control likelihood. Match nuisance factors and calibrate only on development data. |
| F. Editing | Edit selected prose, then rescore and judge. Record editor access, token budget, changes, and new unsupported claims. |
| G. Independent reader/scorer | Prioritize compatible J++ checks on existing cells; a bounded activation-blind consistency helper is separate. Token support is not relational proof; keep answers and judge verdicts out. |

Consensus equivalence must preserve entities, numbers, negation, and relation direction. Keep sample provenance and audit false semantic merges against normalized exact matching.

Run E's cheap semantic diagnostic early, alongside A/B/C development. Cross two activations with two descriptions differing only in negation, number, or relation direction. Require both correct pairings to beat incorrect pairings; examine the interaction margin and a generic description omitting the critical detail. Balance entities and paraphrases. Failure means FVE cannot be trusted to optimize that distinction; it need not end all sampling experiments.

Unpenalized NNLS fit cannot worsen when candidate columns are added: coefficients can be zero. Pruning and stopping therefore require an explicit marginal threshold or penalty, tuned on development data. Score canonical individual bullets; concatenating them invokes a different nonlinear reconstruction. Test sensitivity to bullet markers and punctuation. Do not confuse a small leave-one-out contribution with evidence that a claim is wrong.

Freeze a matched-control activation bank from development/calibration only; exclude every test example and, for each scored item, its same/related groups. Inference candidates, selectors, and editors must not see answers, targets, transcripts, or evaluation verdicts. A separately labeled context-aware extension may receive context. Controlled diagnostic labels must never enter inference selection. No tuning on test errors.

Keep each pool, consensus, and evidence set within one item/layer/position cell; batching independent cells is not multisite reading. Residual O-lens resampling is deferred under the current cap; numerical greedy selection/NNLS rounds are unaffected. A derived residual adds no source observation but changes the input distribution and generation cost. Mean-pooling different cells, new multisite readers, new benchmarks, and training remain outside scope; reader-overview material does not expand completion requirements.

Editing starts with two calls/four proposals each, eight total across the beam; local AR chooses, and Luna evaluates final condition outputs without feeding labels back. Pilot 100–300 development cells before scaling 1–2 variants, freezing the same cell manifest for N=1 and best-of-N controls; partial-grid pilots report cell-level metrics, while final comparisons retain the original full grids. Until its fitting-data audit establishes disjoint groups, J++ remains a development diagnostic, excluded from clean held-out headlines and the final composite. [METHODS.md](METHODS.md#f-edit-with-explicit-limits) gives token-based forecasts. NLA is an optional, separate small layer-42 development diagnostic, not a change to core grids or a completion requirement.

## Execution stages and decisions

1. **Reuse audit and instrument validation.** Verify source pins, caches, whitening, adapter behavior, read plans, split manifest, judge contract, and storage/resource access. Stop affected AR-guided scoring if the scorer cannot be reproduced, document the missing prerequisite, and continue sampling or consensus work that does not depend on it.
2. **Real baseline pilot.** Start with tiny N=1/2 timing and instrument checks, then run the small development pilot end to end through capture, verbalization, judging, and reporting. Check empty/truncated outputs, lengths, positions, and costs. Resolve instrument failures before expanding nested prefixes or scaling to development.
3. **Shared pool and A/B/C, with E diagnostics.** Reuse candidates/scores across nested prefixes, expanding through 16/32 under prespecified rules when expected information or gains justify cost; never exceed the shared 32-sample cap.
4. **D and combinations.** Pilot pooling on the shared subset. Expand promising combinations; reject apparent gains caused by verbosity or increased contradictions.
5. **F/G pilots.** Test on the representative subset; add separately labeled failure diagnostics. Document unavailable prerequisites and expand only when worthwhile.
6. **Validation, freeze, test, report.** Freeze endpoints and operational thresholds before validation; use validation only to select among prespecified settings. Freeze the selected method before test. Any test frontier uses prespecified settings, never a test-selected operating point. Report inconclusive outcomes, negatives, and regressions.

Scheduling decision, 2026-10-10 06:35 UTC: the already fixed validation N32
candidate pool may be generated while full development judging finishes. This
is blind preparation only: inspect counts, source hashes, resource use and
timing, but no validation text, reconstruction scores, selected outputs,
judgments, examples or dashboard results before the development shortlist and
operating settings are frozen. Use a distinct generation-only gate that analysis
entrypoints reject; issue a separate analysis gate after the development review.
This overlaps independent GPU work without using validation to guide development.
At this checkpoint test generation remained closed. The prospective scheduling
revision recorded in experiment 028 subsequently permits blind fixed N32 TEST
generation after VAL AR ends, while validation judging proceeds. It binds the
same existing cells and generation recipe and permits only counts, hashes,
resource health and timing. Test text, AR, selectors and judging remain closed
until the separate final-method freeze and analysis gate.

Before expansion, complete [the experiment record](experiments/TEMPLATE.md): hypothesis, controls, metrics, traces, raw/capped baseline and best-of-N comparisons, costs, and decision. Prespecify practical recovery/error tolerances and futility rules on development. Judge pilots jointly by practical effect size, paired examples and failure mechanisms, consistency, collateral regressions, incremental compute, and uncertainty. A promising gain on even one family can justify follow-up despite wide confidence intervals; there is no significance gate. Expand measurement when it could change the decision within budget. Stop for failed instrumentation, practical futility, cost limits, or verbosity/leakage explanations. Distinguish promising from established findings and inconclusive from negative results; selected examples explain mechanisms, not proof by cherry-picking.

The user delegates small recovery/error tradeoffs to the research team. Choose from the measured development/validation Pareto frontier: the best observed tradeoffs among tested settings, where no other tested setting is at least as good on both outcomes and strictly better on one. Report uncertainty; this does not rule out better untested settings. Document the choice before test. Favor approaches promising across the four families, while reporting specialized gains honestly. A combined final method is welcome; require each component switched on/off plus same-pool best-of-N comparisons, at the same candidate and output budgets, for a paper-quality explanation of what helps.

Completion requires a representative pilot for each runnable approach, with explicit prerequisite blocks otherwise; a frozen shortlisted method tested against raw/capped N=1 and best-of-N; and a report linking artifacts, failures, and costs. Negative or inconclusive findings are valid outcomes.

An approach omitted for time is **incomplete/time-limited**, not prerequisite-blocked or negative. The 20-hour target does not waive seven-approach coverage or permit a claim of full completion when required work remains.

## Twenty-hour execution target and final delivery

Aim for a final result approximately 20 hours after execution starts: 2026-10-10 21:25:36 UTC. This is a target, subject to working loaders/whitening and measured throughput; overlap independent work:

| Elapsed execution time | Main work |
|---|---|
| 0–2 hours | Prerequisites, real baseline pilot, dashboard after first validated pilot |
| 2–6 hours | Candidate pools, A/B/C, early E diagnostics |
| 6–12 hours | Bounded D/E/F/G pilots and combinations |
| 12–17 hours | Validation, frozen held-out comparisons, component ablations |
| 17–20 hours | Final dashboard/report polish, trace review, and audits |

At two hours, forecast completion from actual throughput and reprioritize while recording all seven pilots or prerequisite blocks. Around hour 12, freeze the shortlist to protect final evaluation time. If the forecast exceeds 20 hours, tell the user early, naming the bottleneck and additional time needed; never relabel unfinished checks as complete. At every slow phase, diagnose and optimize before simply waiting.

Start the dashboard after the first validated pilot, then refresh after each completed scored experiment and trace audit throughout execution. Lead with **3–5 plain-language findings**, reviewed by the coordinator and/or Sol: best current method against raw/capped N=1 and same-pool best-of-N where comparable, effect size/uncertainty/evidence, what failed or traded off, open questions, and next action. Distinguish provisional development findings from frozen test results; never promote a method solely because it tops one metric.

Then show charts: quality versus N=1–32, recovery/error and cost, family results, component ablations, and uncertainty. Use validated counts, fixed denominators, and runtime/API-cost labels. Cross-bank tradeoff axes must label their separate cohorts/counts; never imply a within-item tradeoff or hide a macro. Method tabs use plain names: sample selection, consensus, pruning, pooling, contrastive checks, editing, independent checks, and combinations. Each shows hypothesis, actual runs, status/results/baselines, wins/regressions/unchanged traces with IDs and judge evidence, failure modes, cost/limits, and next decision.

Use lightweight shareable HTML tabs from the same versioned, validated JSON/CSV and reviewed synthesis as the report; no hardcoded results, custom backend, API calls per refresh, or mandatory framework. Show last-updated time/run IDs, separating progress from scientific verdicts. Label partial counts and missing data; absence is not zero. Default to development views; keep test views sealed until freeze and the planned reveal. Refresh meaningful updates while the session runs; do not promise monitoring after it stops. Preserve the newcomer clarity pass, explicit abbreviations, and test boundary.

Add descriptive layer/position heatmaps and coverage from existing cells only, showing counts and missingness. They do not authorize new captures or test-selected layers; official item aggregation remains unchanged.

## Budget, compute, storage, and supervision

The paid-API ceiling is **$300**, targeting **$200**, with **$100 reserved** for justified reruns/final evaluation, not routine spend. Start a new ledger for all paid APIs, retries, and malformed responses. Reserve worst-case in-flight/retry costs before dispatch: billed plus outstanding reservations must never exceed $300. Reconcile charges and forecast each expansion. Historical spend and the old $500 script default give no new authority. Track GPU-hours separately; monetary cost is unknown.

Use the four main H200 slots and up to four preemptable slots only for useful independent work. Prefer H200; after approximately 10–15 minutes pending, consider H100 with verified memory fit. Run heavy work through Slurm. Verify live allocation ownership, expiration, partition/account limits, maintenance, and model fit first: older documentation says six hours and current project instructions say 48 hours. Neither establishes today's allocation expiry. Do not use L40S for this full model.

Use resumable, balanced shards with explicit seeds, claims, atomic outputs, and duplicate detection. While execution is active, an assigned agent should periodically inspect preemptable jobs, shard progress, failures, stalled claims, allocation expiry, and budget; adapt the work queue rather than poll continuously. Record watcher identity and last check. Agent monitoring ends when its session stops; persistent logs, manifests, and checkpointing must support a paused chat and later recovery. The user selected Astra as coordinator and GPT-6.1 Sol workers with task-appropriate reasoning effort. An agent cannot change its own assigned model. Keep concurrent agents within available tool limits; GPU worker processes need not correspond one-to-one to agents.

Use `${LAB_COMPUTE_ROOT}/` for fast working artifacts and `${LAB_DATA_ROOT}/` for durable results, distinct from the personal pool. The user authorizes approximately **500 GB aggregate across both locations**, not 500 GB each. No renewed permission is needed within that allowance; ask before a material increase beyond it. Verify access and actual group quotas first; filesystem `df` is insufficient. Aim for the leanest practical footprint, approximately **100–150 GB including a possible base-model copy**, with non-weight artifacts normally below 100 GB. These targets guide cleanup, not unnecessary execution blocks. Count physical copies across both locations; prefer reuse/symlinks. Keep bulky files and environments off HOME and outside the repo. Retain target activations, stochastic text, paid judgments, and reconstruction provenance; remove regenerable vector intermediates after validation. Prefer few large shards. Storage authorization is separate from the unchanged $200 API target/$300 hard ceiling. Neither location is a backup.

## Git workflow

Make local commits at meaningful reviewed milestones, keeping code, documentation, configuration, compact validated results, and dashboard source in Git. Keep large artifacts outside the repository and reference their manifests/paths. The root coordinator is the sole Git writer; other agents edit only their assigned files. The user handles all pushes.

## Current status and continuation

| Item | Current state |
|---|---|
| Research scope, candidate methods, limits | Documented here |
| Git workflow | Local main initialized; planning versioned in local commits; pushing handled by the user |
| New project experiment implementation | In progress: resource, model/scorer, and data/evaluation workers |
| New inference, judging, or GPU execution | 65 shared-pilot conditions judged; full development samples, reconstruction and selectors complete; VAL AR/selectors complete; twelve-arm judging resumed only unfinished conditions after a tested accounting-lock repair; blind TEST generation on four H200s, with TEST analysis closed |
| Whitening access and exact scorer reproduction | All 11 files downloaded; 18 math fixtures and real matched-AR reproduction passed |
| Real adapter activation and cache compatibility | Adapter checks passed; all 19,435 core cells freshly captured, eight instrument vectors preserved exactly |
| Runtime environment, allocation, quotas, actual cost | Four main H200s retained; CPU 25474685 hosts judging; group quota unresolved; 10:18 UTC watcher: API usage $11.90501 plus $4.67023 reserved, including $4.66474 unknown; 48.39 GB logical project storage; ledger authoritative |

Maintain this durable handoff block after each experiment or material state change:

- **Phase:** judged development pilots/combinations, failure analysis, and full development reconstruction/selection. All 5,236 development cells have 32 immutable samples; raw/capped N1 judging is complete. All 3,485 blind validation N32 pools are immutable; the twelve-arm shortlist, AR and selectors are complete. Fixed pruning and the exact twelve-condition export are complete; all four validation judge queues have started, with multi-hop complete. Blind TEST generation is running on four H200s under the unchanged recipe; TEST analysis stays closed.
- **Execution clock:** started 2026-10-10 01:25:36 UTC; target finish 2026-10-10 21:25:36 UTC. Forecast given around 02:40 UTC: another 10–14 hours, conditional on measured helper/judge throughput and the validation shortlist. Generation alone is not a completion forecast.
- **Last completed experiments:** original instrument/source checks; full fresh capture; 189-cell N32 collection; A/C/D/E1 numerical selection and 22-condition judging/repair; 36-set E2 and J++ diagnostics; E3 scoring/judging; two editing rounds and final-output judging; bounded semantic-consensus audits; Luna repeatability audit. Editing did not improve the observed recovery or wrong-readout counts over pooling. Strict whole-bullet consensus lost most coverage; semantic merging had unsafe examples. E3 was mixed. No general improvement is established. See experiments 008–011 and the source-linked dashboard; the repeatability audit preserves primary verdicts.
- **Active Slurm IDs / watcher / last check:** main H200 jobs 25330001, 25330006, 25330007, 25417596. Extras 25460532 and 25459615 were intentionally released after completing their work. A lightweight watcher on CPU allocation 25299630 records checks every 600 seconds until the execution deadline; its 05:56 UTC check passed without alerts. Full development has 5,236 complete N32 pools and 642,209 unique reconstruction vectors. V4 selection is complete: 40 offline conditions, exact agreement on all 2,018 earlier v3 rows and all 10,472 raw/capped baseline text/token pairs. Preserve the v3 error and cleanup audit; report AR eligibility differences, not just winner scores. E1-only pruning is complete on all 5,236 cells.
- **Spend:** usage-based API estimate $5.19455147 and unresolved reservations $4.239701 at approximately 06:34 UTC; later ledger values are authoritative. There were 436 unresolved attempts, including 42 from the main comparison transport incident. Cache-write input charges were reconciled from raw response usage while preserving original events. This is not invoice reconciliation. Target $200, ceiling $300, reserve $100. Successful replacements do not establish that earlier calls were unbilled. The recovered main queue retains its shared $20 ceiling and a guard against excessive new uncertain calls; see experiments 019 and 023.
- **New bounded diagnostics:** full-development comparison remains frozen at 24 conditions (019). Pooling plus specificity and its abstention control (020), repaired whole-bullet B, and medium helper reconfirmation (021) are now judged. Whole-bullet consensus still loses coverage; this does not establish that consensus over individual claims fails. A separate 32-cell exact-source-span pilot (024) begins with an eight-cell qualification audit before expansion. Benchmark judging remains Luna reasoning-none. The parallel AR batch audit (018) exceeded both provisional numerical guards; those failures remain recorded. Fixed B128 is accepted as a declared implementation, not as equivalent to B32, with shared caches across methods and near-threshold sensitivity reported.
- **Next action (12:42 UTC):** all 48 validation method-family comparisons and the signed report are complete. Root and two independent reviews selected A16 and unpruned Emean32; no general faithfulness gain is established. The six-arm TEST menu and separate analysis gate are sealed and committed (9544e96): raw N1, capped N1, A16, A32, random N32, Emean32. All 342,848 unchanged TEST samples passed the frozen-pool identity checks; snapshot SHA9bebdb516e3435206c56a423356fad82f09cdde04aced212a7d7d214f66a55dc. Four-partition AR input preparation is running on CPU25489638, root session91657/log fast/logs/test-freeze-prepare-v1.log. Once terminal, launch all four retained H200 encoders. No TEST quality result has been inspected. Reviewed validation dashboard/plots and report are now available locally. Applied async accounting (605dad7) passed45 tests plus a copied-ledger fake-network check. Remaining DEV scaling-only judgments are being forecast for the compute window; their results cannot change the frozen TEST settings. Final fresh-input timing and held-out judgments/report remain pending.
- **Unresolved:** group storage quota; a useful, robust method/composite; semantic-helper and judge reliability; J++ fitting-group overlap. Small pilot confidence intervals have only 2–8 independent groups. Model/scorer access and fresh-capture prerequisites are resolved.

First execution actions: read AGENTS.md and this plan; inspect existing manifests read-only; establish project-owned artifact paths and ledger; freeze grouped splits; resolve the loader checks and, for AR-guided methods, whitening checks; prepare the real baseline pilot and its cost forecast. Review the pilot record before launching the full development run; this is an execution quality gate, not a new user-permission requirement.

For continuation, read this plan and the latest experiment records, inspect actual manifests/results, then resume the first incomplete stage. Preserve the historical checkout and frozen test boundary. Record any scope or budget change explicitly.

Sources: [paired release card](https://huggingface.co/agu18dec/olens_and_ar/blob/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/README.md), [target model config](https://huggingface.co/Qwen/Qwen3.6-27B/blob/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9/config.json), [WorkspaceBench producer](https://github.com/camilablank/workspace-bench/blob/92d763e722377f5bfae045e829a308ab5919a820/src/wsbench/produce/methods.py), and the local audit pointers above. Historical results and costs are context, not new measurements.
