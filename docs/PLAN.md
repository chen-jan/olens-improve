# Frozen Oracle Lens: inference-time improvement plan

**Current handoff, 2026-10-11 03:56 UTC:** the approved [expanded comparison](EXPANSION_PLAN.md) remains active on one owned preemptable H20025536297, API CPU25536291 and analysis CPU25536417. Operational judging is253/280; the public source-checked snapshot is235/280. Role likelihood and editing remain. Bounded native, reconstruction-v5 and effort gates are waiting for exact terminal sources; final qualitative indexing/reviews and report/slides follow those outputs. Existing reviewed reconstruction and qualitative artifacts remain unchanged. The $340 total API ceiling and retained unknown holds remain in force. Other-reader experiments are postponed. See [STATUS.md](STATUS.md) for current receipts; the first-study record below is preserved.

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

**First study completed: 2026-10-10 22:43 UTC.** Scientific judging, analysis, independent reviews, report, final dashboard and editable/PDF presentation are delivered for its frozen scope. The public dashboard is version 12; see [DELIVERY.md](DELIVERY.md). Its primary comparison remains 268 held-out items, with all 469 separately labeled descriptive. No winning method or setting in that study was changed after TEST. The owned watcher and successor CPU allocation have been released; user allocations were preserved. All data, caches and financial holds remain retained. GitHub pushing is the user's action.

**Next phase prepared, not started:** follow [EXPANSION_PLAN.md](EXPANSION_PLAN.md). Expand the distinct methods on the same four complete banks, retain natural pooling output lengths, preserve the 32-sample cap, and defer all other readers. The user will supply one preemptable H200 and a start instruction. Do not reuse historical allocations, launch paid work, or activate a goal while waiting. New analyses of the already observed 469 items are exploratory; they do not replace the original held-out report.

## Prior handoff, before final packaging

Latest handoff: **2026-10-10 approximately 22:18 UTC**. All paid judging is complete: the frozen twelve methods cover every intended DEV/VAL/TEST family grid, including both hallucination stages. Statistical reports and systematic independent trace reviews are complete. The primary final scope remains TEST 268; whole 469 is a separately labeled descriptive appendix, not independent held-out confirmation. Final figures are exported; reviewed report/dashboard attachments and slides are being assembled before final publication.

Final TEST review metadata is [test_final_review_v1.json](../configs/test_final_review_v1.json); its exact analysis SHA is `75dee255d88104450fa4424610178baa4df24964394be77812fa218379cfcef8`. [054 final resources](experiments/054-final-resources.md) binds the terminal accounting and scoped storage receipt. API usage is $36.50759506, retained reservations $4.8597425, committed $41.36733756 at 22:02:08 UTC; unknown charges are already inside reservations. Storage is 98.704 GB / 14,974 files at 22:10:53 UTC. Major generation/AR task time is 30.192 hours; project-reserved H200 time through the 18:10:48 handoff is 70.220 GPU-hours. No GPU dollar price is available.

No paid worker or project GPU workload remains. Do not schedule new GPU work against handed-back allocations. CPU 25508300 remains available for final figures/deck until root coordinates release. Final public dashboard and editable/PDF slides are still under delivery review; no final-publication or GitHub-push claim is made. Root is the sole Git writer, and the user handles pushing. Preserve all samples, exact caches, raw evidence, holds and historical records. No new scientific tuning or calls are required for this handoff.

The bounded pre-reveal auxiliary-field exposure remains disclosed in the final review metadata and historical handoffs below; do not replace it with a universal zero-exposure claim.

## Historical operational handoffs

### Handoffs retained through 21:55 UTC

**GPU handoff:** all four H200s were verified idle at 18:10:48 UTC and are available for the user to reuse. Do not schedule new project GPU work or attribute subsequent user GPU time to this project. The allocations remain intact. Current judging uses CPU job25508300. See `configs/gpu_handoff_v1.json`.

Latest handoff: **2026-10-10 21:55 UTC**. All 48 TEST comparisons are complete, including twelve hall contracts covering3,705 cells with both stages; root collected exit 0 and cache-owner release. Terminal receipt SHA `5119be87fdea7dc4cf536cc29f9af0e3a97870eae751a4ee6352fed52a83d7ea`. Signed TEST analysis is running on allocated CPU. All six late DEV role comparisons are complete with 3,420 cells each and no missing judgments; five hall DEV comparisons remain. Released-hall family-only forecast and batch-v4 preparation are ready for root sealing, with the same original five-condition order/run $20 / 07:52 epoch.

The role batch worker settled 16,818 requests over 295.34 seconds of summed condition walls, approximately 3,417/minute, without ledger errors. This is a mixed-condition operational measurement, not a controlled optimization effect. Incremental role usage is $1.3324818 and all 124 uncertain DEV holds remain unchanged. The 21:54:20 receipt records global usage $34.13221616 plus reservations $5.613203875, committed $39.745420035; the unknown subset is included. DEV headroom is $13.74093639. Receipt SHA `0b044d498f3b7f2b4ee966fde6cb70ed08c000ed8c506a47baebed4345b9f6f8`. Signed result review, five hall DEV comparisons, descriptive whole 469 analysis and final presentation/accounting remain required.

### Previous batch launch handoff, 21:47 UTC

Latest handoff: **2026-10-10 21:47 UTC**. TEST has **44/48** complete comparisons: multi-hop, chains and roles each 12/12, hallucination 8/12. The role TEST worker exited zero and released its cache; its exact six remaining DEV comparisons launched at 21:45–21:46 as PID 395046/session 3538 under sealed `configs/judging_dev12_remaining_role_batch_v4.json`, SHA `746026d866badc90108807663ed2ce4dbd53864ce4106b71c0cb95acc30e7bc5`. Hall's four remaining TEST comparisons resumed at approximately 21:47 as PID 398431/session 31433 under sealed `configs/judging_test_batch_hall_v14.json`, SHA `6fe7b48b3c6b53adf82829dc5934b56e6c6ce8755ae20ae53e82464a8f294f7e`. Five hall DEV comparisons still wait for that TEST family's completion and cache release.

Both workers now use opt-in reservation batches of at most 16 plus connection reuse. The judge, requests, signed menus, 256/ 4,000 transport, original 07:52 epoch, all holds and $40 TEST/$20 DEV caps are unchanged. Eighty-six focused tests and independent coupled review passed. The 3.75× copied-ledger accounting gain does not establish a live improvement; measure the 21:54 checkpoint before revising the delivery estimate. See experiment050.

The 21:44:16 receipt records $29.05894376 estimated API usage plus $4.8597425 reservations, total $33.91868626 committed. The uncertain $4.85435575 subset is included, not added again. DEV headroom is $15.07341819; its released-role forecast has 16,817 new unique calls and $1.3556474782 expected charge on the frozen empirical basis. Receipt SHA `8c96b6e34a54eada67ea6a08721f803fe95dc4af57bc805d278a13fefdbb023a`; forecast SHA `4c65f37921d42d1fdf8806915c00ab3e1dee14930e4c1de2047910531330209d`. These are accounting observations and a workload forecast, not an invoice or guaranteed finish time.

An operational observer incidentally saw two auxiliary hallucination raw-N1 contract fields in the bounded 21:29:11–21:31:56 interval. Root has not synthesized TEST outcomes or used those fields for tuning; the menu remains fixed. Preserve this disclosure rather than claiming universal zero incidental exposure. Metadata-only receipt: `durable/diagnostics/test12-operational-v1/primary-six-completion-contracts-v2.json`, SHA `b0b69992c882e503ab8e016c2090d216b0c3d51491224a6fd5b7b7e4ef8b1758`.

### Historical handoff through 20:50 UTC

Latest handoff: **2026-10-10 20:50 UTC**. TEST judging has completed 42 of 48 family/method comparisons: all twelve multi-hop and chain comparisons, eleven role comparisons and seven hallucination comparisons. Hall is now PID 42548/session 53016, using `configs/judging_test_reuse_hall_v12.json`; role is PID 4167699/session 27628, using `configs/judging_test_reuse_role_v13.json`. Both use Standard Luna, reasoning none, 256 concurrent requests / 4,000 RPM, and the reviewed opt-in accounting connection reuse. Earlier workers exited cleanly with saved judgments retained. The optimization passed 92 focused tests and independent review; live speed improvement is not established.

The 20:44:07 operational receipt recorded 90,102 settled TEST requests, with 2,345 more in 927.63 seconds (152/minute). Unknown charges remain unchanged. Receipt SHA: `b59249841e449aa1aae6ac9783bb4cd1aea76407913e76ef6e17749bbec18abe`, under the same diagnostics directory with suffix `2043-v1.json`. The latest execution checkpoint is `.state/execution-checkpoint-2050.json`. Resource monitoring succeeded again at 20:46:58; completed CPU 25489638 is preserved in historical runtime records and excluded from active alerts.

The 20:28:40 checkpoint recorded 87,757 settled TEST requests, adding 1,011 in 336.17 seconds (180/minute). All twelve uncertain TEST charges ($0.059636875) and the separate older reservation ($0.00538675) remain held. This is operational evidence only; no TEST quality has been inspected. Receipt: `durable/diagnostics/test12-operational-v1/storage-recovery-concurrency-v11-operational-reuse-both-v12-v13-2028-v1.json`, SHA `14dfcb0f99f645aa76060a402d840d00acdce578e4cd5af53f1e7c6622fc7746`. See experiment049 for the earlier benchmarks, including the failed speedup replication.

**Historical ETA at the 20:50 handoff:** approximately 29,359 TEST requests plus 22,157 from the historical missing-DEV forecast imply about 4 hours 46 minutes for all judging at the observed rate. These are workload references, not exact live cache counts or guaranteed bounds. Plan for final delivery around 23:00 Eastern October 10, with a 22:00–00:00 Eastern window; review can overlap some DEV work. The user accepted this revised timing at approximately 20:31 UTC and asked us to keep monitoring. The original 20-hour finish target is no longer the working estimate.

The authoritative ledger remains at `${OLENS_COMPUTE_ROOT}/budget/ledger-v2.sqlite3` behind the unchanged canonical durable symlink. Its previous inode is a read-only archive. Keep the original 07:52 recovery epoch, all caps and all uncertain charges. The byte-preserving migration receipt is recorded in experiment048; no stale-ledger fallback or additional schema migration is authorized by these performance observations. Both judge processes must finish before final quality analysis; each complete TEST family can hand off to its exact remaining DEV subset independently.

### Current continuation requirements

- **Scope:** the user reconfirmed at approximately 18:06 UTC that broader WorkspaceBench families are a second stage, after these results are complete. Finish twelve frozen comparisons across the four agreed families. The 268-item TEST cohort is the primary final comparison; the full 469-item aggregate is required and must be labeled descriptive because development and validation informed choices. No additional families or broader lens leaderboard are required.
- **Completed research:** matching checkpoint/whitening reproduction, fresh activations for all 19,435 cells, all 621,920 shared samples, bounded evidence for seven approaches and combinations, development sampling curves, and twelve-method validation. TEST reconstruction and selection are complete. Multi-hop and chain judging ended successfully. Consult DELIVERY_CHECKLIST for failed audits, unrun variants and diagnostic-only evidence.
- **Remaining judging:** five hallucination DEV comparisons; all 48 TEST and all six late role DEV comparisons are complete. The hall family-only forecast and batch-v4 preparation await root seal/launch. Do not restart a live worker because its log is quiet. After each TEST family ends, refresh and seal its remaining-DEV continuation with exact family-only cache forecasting and current source/resource pins. The family-only forecast extension passed ten focused tests and independent review; use `.state/dev12-released-family-handoff-v1.md`. Preserve all original scientific settings. Prepared specifications cannot dispatch until their missing evidence is filled and reviewed.
- **Scientific authority:** preserve the v2 menu, freeze and analysis gate. The bounded incidental auxiliary-field exposure is disclosed above; no TEST outcome synthesis or retuning has occurred, and no TEST retuning is permitted. After every required stage completes, run the signed paired analysis, independently review the fixed trace sample, and then build the separate descriptive whole-cohort analysis. The whole-cohort helper passed source review and synthetic checks; incomplete inputs remain prohibited.
- **Resources and accounting:** CPU job 25508300 has eight physical cores and 32GiB through 05:32:23 UTC on October 11. Hall uses cores 0,3; role 13,20; compute audit 23,26; deck work 27,28. Old job 25474685 was released at 17:42. No new GPUs are needed for this stage. A metadata/file audit at 18:03 found all required generation, reconstruction and portable-tool artifacts retained; all four H200s were idle at the 17:58 live check. The compute agent is the sole bounded ledger observer. Retain all twelve unknown TEST charges and the stopped hall worker's separate unreceipted reservation, the original epoch, and all existing caps. Project limits remain $200 target, $300 hard ceiling and 500GB storage.
- **Measured cost:** use the 21:54 receipt above for the latest estimated API usage and retained reservations. The 16:49 global receipt ($18.12687471 usage plus $4.900247625 reservations) remains historical, not a current invoice. Generation plus main reconstruction took 30.192 measured GPU task-hours; distinguish that from 64.773 reserved GPU-hours at 16:49. Project storage was 93.732GB at 16:43, excluding reused base weights. See experiment044.
- **Delivery:** public Site version10 defaults to question-level recovery and keeps the native hallucination error rate separate. The20:41 publication updates the queue and accepted ETA plus previously reviewed task-criterion wording; scientific objects and32 other public files are unchanged, and browser QA was not repeated. The site contains reviewed DEV/VAL evidence, sixteen map downloads, all-method coverage, sampling curves and eight shared qualitative examples. The final deck extension has passed synthetic layout checks. Final TEST and descriptive 469 figures, report, dashboard, editable slides/PDF and accounting remain required. Portable N32 inference and relocated-cache replay have passed their bounded engineering checks; see 035/036.
- **Continuity and Git:** the repaired resource watcher PID1536219 now runs through04:30 UTC October11, with ten-minute resource checks staggered from the dedicated judge observer. No additional 19:00 CPU request is needed. Root alone commits; the user pushes the research repository. The separately authorized Sites repository hosts public updates under the existing project ID. Keep the goal active until required delivery is complete.

Use STATUS and experiment050 for the current operational receipts; experiment049 preserves the earlier trial. The final sequence is complete judging, paired analysis, independent trace review, whole 469 descriptive comparison, then report/dashboard/slides and final accounting.

Sources: [paired release card](https://huggingface.co/agu18dec/olens_and_ar/blob/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/README.md), [target model config](https://huggingface.co/Qwen/Qwen3.6-27B/blob/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9/config.json), [WorkspaceBench producer](https://github.com/camilablank/workspace-bench/blob/92d763e722377f5bfae045e829a308ab5919a820/src/wsbench/produce/methods.py), and the local audit pointers above. Historical results and costs are context, not new measurements.
