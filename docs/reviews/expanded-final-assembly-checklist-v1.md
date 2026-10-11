# Final expanded presentation assembly checklist V1

Status: preparation only; no terminal scientific result, final root interpretation, or publication is attested by this checklist. This bounded read-only readiness check changed only this document. Use the current immutable artifacts and actual service receipts; do not duplicate the live producers.

## Current service readiness

The one node audit (tool chunk `d58e0a`) confirmed all five processes alive, sleeping, and owned by CPU Slurm `25536417` on node1623. Local state read at approximately 2026-10-11 04:57 UTC found heartbeats 1–16 seconds old and no error fields. Native has 64/64/64/61 terminal condition-family files for hallucination/multihop/chain/role and 19/32 canonical descriptors. These are presence counts, not a newly validated terminal scientific seal.

| Service / state file under `.state/` | PID | Observed state | CPU affinity |
|---|---:|---|---|
| `expanded-final-native-v1.service.json` | 423907 | waiting_for_terminal_sources | 52,244 |
| `expanded-edit-pruning-v1.service.json` | 439894 | waiting_for_round2_terminal | 52–55,244–247 |
| `expanded-role-fit-v1.service.json` | 443099 | waiting_for_role_likelihood_descriptor | 52–55,244–247 |
| `expanded-final-reconstruction-v1.service.json` | 500790 | waiting_for_native_and_all_secondary_sources | 53,245 |
| `expanded-final-qualitative-v1.service.json` | 500810 | waiting_for_exact_terminal_native | 54,246 |

Cheap monitoring catalog: `.state/expanded-final-services-monitor-v2.json`. Preserve existing wrappers, source pins, locks and one-attempt guards. Waiting heartbeat older than 180 seconds merits a process check; an active extraction subprocess may not update its parent heartbeat until completion. Failure/timeout means root recovery, never silently accepting partial output or resealing. The allocation expires 12:18:55 UTC; bounded pruning/role watchers stop around 09:42–09:43, native around 11:51, and relaunched fit/qual around 11:58 if still waiting. This is one check, not duplicate GPU monitoring.

## Terminal artifact and schema gates

Shared durable root `D = ${OLENS_DATA_ROOT}/expansion-v1`. All six files below were absent during this check. Their final SHA-256 values are pending; obtain and retain them from terminal service receipts and independently hash exact bytes. Never promote interim V3 hashes into final authority.

| Final input | Exact path relative to D | Required boundary / schema evidence |
|---|---|---|
| Native statistics | `analysis/final-v1.json` | Native state `complete_pending_root_review`; `scientific_inputs_validated_complete=true`; exact `output_sha256` and native receipt SHA. Output `complete_exploratory`, all 280 condition-family units, no missing units; all four cohorts retain original counts/groups. Frozen 124×4=496 contrasts and simultaneous-family completeness, defined draws, effective/nondegenerate counts and warnings remain explicit. |
| Secondary reconstruction | `reconstruction/final-v1.json` | Numeric state `complete_pending_root_review`; exact output SHA and `quality_analysis_sha256` equals retained final native SHA. Exactly 280 active rows and no missing selection sites. Valid/missing-fit masks, raw-N1 unavailable fit, grouped intervals, tolerance1e-5 classification, percentage-point fields and warnings preserved. Invalid fits do not become zeros. |
| Capped-reference qualitative cases | `qualitative/final-v1.json` | Qualitative state `prepared_pending_final_human_reviews`; exact output SHA and native SHA; all 70×4 families, eight historical outcome-blind anchors retained, fixed anchors separate from lexicographic outcome supplements. No pending scientific source. |
| Actual-parent qualitative cases | `qualitative/parent-comparisons-final-v1.json` | Same retained native SHA; full original context/text/official outcomes and original-question-grid witnesses; frozen parents resolved exactly, no missing parent-family prerequisite. |
| Final differential review index | `qualitative/final-delta-index-v1.json` | Same native SHA; exact cap/parent/prior-index/four-prior-review pins; counts derived from exact new references, all four partitions present including zero counts. This durable path is the live pipeline output; the older intake-plan example used a proposed docs path and must not replace it. |
| Final accounting | `analysis/effort-final-v1/effort.json` | Separate API-owner effort watcher complete; bind sibling `receipt.json`, final native/32-descriptor identity, accounting cutoff, settled/unknown/reserved commitments. Shared helper work is not charged as independent variant runs. GPU dollar cost, Codex billing and bank-average deployment latency are not inferred. |

Native source receipt: `.state/expanded-final-native-ready-v1/receipt.json`, exactly 32 canonical descriptors from four family files in each of `cached-v2`, `combinations-v2/merged`, `semantic-semantic-v1`, `semantic-medium-v1`, `likelihood-v1`, `editing-round1-v1`, `editing-round2-v1`, `editing-pruning-v1`. Exclude registrar aliases. Numeric receipt: `.state/reconstruction-analysis-final-ready-v1/receipt.json` and `editor-dispatch.json`; binds eight successful per-task records separately from mutable queue observations. V5 independently pins helper-v2, original whiteners/scorer, raw spec files and canonical event linkage. Preserve dynamic native output/receipt/raw-terminal-state hashes before/after extraction. Full input completeness is not certainty and does not suppress undefined/degenerate intervals.

## Human review and inheritance

Expected final reviewer files are:

- `docs/reviews/expanded-qualitative-final-root-v1.json` (`root`).
- `docs/reviews/expanded-qualitative-final-agent1-v1.json` (`agent_1`).
- `docs/reviews/expanded-qualitative-final-agent2-v1.json` (`agent_2`).
- `docs/reviews/expanded-qualitative-final-agent3-v1.json` (`agent_3`).

Each must bind the actual final index SHA/partition and cover every pending pair in that partition. An empty pending partition needs an explicit completed zero-count file. Compare all selected full texts and supplied contexts, exact actual parents, official local evidence and question-grid witness metadata. No automatic prose faithfulness judgment or official-score changes.

Exact inherited notes require identical before/after text, complete context, family/cell and official outcome pair, linked to the exact prior completed reviewer file SHA. New condition-specific whole-grid metadata stays separately retained. Changed official evidence/context requires fresh review even with identical prose. The unchanged index-v2/merger inheritance resolver uses the prior V4 index's fresh partitions, not its inherited-only lineage; a match to the older 17/426 lineage alone remains fresh review. The prior 330-reference note bundle is preserved verbatim and its historical426-pair authority remains pinned; these counts never stand in for final new counts.

After all four final files exist, API owns the count-derived merger below. `FINAL_INDEX` is the live durable path, not the old proposed docs filename. Output must be new and absent; do not run the hardcoded V4 merger.

```bash
PYRUN=${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python
FINAL_INDEX=${OLENS_DATA_ROOT}/expansion-v1/qualitative/final-delta-index-v1.json
$PYRUN scripts/validate_expansion_qualitative_final_reviews.py --index "$FINAL_INDEX" --prior-index docs/reviews/expanded-qualitative-v4-new-case-index-v1.json --prior-notes docs/reviews/expanded-qualitative-v4-merged-notes-v1.json --prior-review root=docs/reviews/expanded-qualitative-v4-root-v2.json --prior-review agent_1=docs/reviews/expanded-qualitative-v4-agent1-v2.json --prior-review agent_2=docs/reviews/expanded-qualitative-v4-agent2-v2.json --prior-review agent_3=docs/reviews/expanded-qualitative-v4-agent3-v1.json --review root=docs/reviews/expanded-qualitative-final-root-v1.json --review agent_1=docs/reviews/expanded-qualitative-final-agent1-v1.json --review agent_2=docs/reviews/expanded-qualitative-final-agent2-v1.json --review agent_3=docs/reviews/expanded-qualitative-final-agent3-v1.json --output docs/reviews/expanded-qualitative-final-merged-notes-v1.json
```

Required merged state: `all_fresh_and_inherited_reviews_validated`, no `pending_partitions`, exact reviewed/required new-reference counts, `eligible_for_complete_final_public_notes=true`, exact final native SHA, source pins verified before/after. Root's merger review `expanded-final-qualitative-merger-root-review-v1.json` approves this boundary only; no final merged evidence exists yet.

## Populate the V3 presentation draft

Starting point `.state/expanded-final-review-draft-v3.json` is explicitly unreviewed, not input for a released build. Preserve it; make a new final root review file after evidence is terminal. Proposed assembly filename `docs/reviews/root-expansion-final-v1.json` is pending root choice, not a preexisting authority.

Bind `status=root_reviewed`, exact `results_sha256`, `manifest_sha256=753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8`, reconstruction SHA both top-level and `presentation.reconstruction_sha256`, accounting SHA, final qualitative/index/merged reviews and explicit root final interpretation. Fill all 28 family-specific `task_comparison` notes from exact final comparison records. Keep representative comparisons as declared: selection A32→capped N1; semantic support.125 compatibility/veto→exact support0; pruning A32.005→A32; pooling D32→capped N1; specificity mean N32→capped N1; editing round2→pooled D32 (A32 secondary); specificity pool.005 deletion→specificity pool. These are explanations, not ranked winners.

For each family show actual native counts/denominator, pointwise and available simultaneous paired interval, effective/defined contrast counts and warnings. Show reconstruction mean/CI, scored/intended sites, exact recorded reference, paired common-valid-site FVE change in pp/CI, independent groups and validity warnings. Do not subtract means on different masks or equate FVE with faithfulness. Final combined-method notes must come from the actual specificity-pool→prune contrast, not historical pooled-greedy prose. Actual eligible editor parent/round1 lineage is separate from aggregate round2→D32; no isolated-editing conclusion from an A32 comparison that inherits pool gains.

Counted units and visible captions:

- Transcript contradiction = wrong specific readouts / all specific readouts; off-topic included. Show specific/total readout coverage, not assertion-count units.
- Recovery = ANY original reading site/layer passes for the whole question. Multihop checks hidden bridge names; final answer optional. Chain credits first ranked verified integer only; lower-ranked/any-of-three is diagnostic. Role requires complete agent/action/patient binding at one site.
- Reconstruction = activation-site mean on valid sites; paired change uses common valid sites. N = candidate readouts per vector.
- Keep released raw original absolute quality and CI prominent and capped original separately named. Only capped→raw has a declared paired comparison; do not attach capped paired CI to a method-minus-raw difference. Historical numbers illustrate the distinction: raw49.17%, capped47.5%, A32+1.67pp versus raw but +3.33pp versus capped; refresh from final rows before display. Never invent additional paired intervals or extend the 496 menu.

All 70 variants remain in both quality and reconstruction appendices. Selection renderer forces all14 best/random/raw/capped variants; other approach plots use at most6 representatives. Overview choices are not winner rankings. Preserve weaker results, nulls, negatives, coverage changes and retained uncertainty. Headline/findings/recommendations and concise action titles need root calibration to terminal evidence.

## Remaining example requirements

Six full-context candidates are in `expanded-slide-example-candidates-v1.json`, root-calibrated by `expanded-slide-example-root-review-v1.json`. Five match their draft aggregate comparison. Consensus uses a support-zero policy versus exact-support0, while the main panel uses support.125; keep the explicit distinction. Recheck all six against final exact before/after text, context and official outcomes before reuse, retain source pack SHA and root notes. Excerpts must be exact substrings ≤100 characters; overview interpretation ≤180 characters. Never turn selected examples into prevalence estimates.

Editing remains pending. Select only a full terminal chosen-output case from historical fixed anchors or frozen lexicographic supplements, never an unselected proposal. Retain exact eligible parent candidate/text, round1 lineage, original complete and pooled references, supplied full context, local official evidence and whole-question witnesses. Resolve example `baseline_text` byte-for-byte against its named recorded reference. If its actual reference differs from primary pooled D32, label that distinction. Require a full root/specialist review before filling the seventh example. A source-resolved example alone does not establish an editor mechanism.

Calibration retained: selection's75 was already present and the new equation is false; pooled correct role direction was already present among conflicting bullets and inventions survive; pruning's shorter readout is judge-labelled consistent without a supported sodium-nitrite answer; combination anchor loss of Enkidu is local while two other sites keep the question recovered. No case receives a rewritten official endpoint.

## Final builders and QA commands

Commands below are dependency recipes only; do not run before terminal sources and exact root-reviewed final file exist. Use new absent output paths; report/dashboard builders themselves are not universal no-overwrite guards. Builders and browser/PDF work run on existing owned CPU, not the login slice; no new allocation. After science services terminate, a bounded2CPU8GiB step is sufficient for known rendering fixtures; verify actual remaining headroom before running.

```bash
PYRUN=${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python
SLIDEPY=${OLENS_COMPUTE_ROOT}/envs/slides-v1/bin/python
NATIVE=${OLENS_DATA_ROOT}/expansion-v1/analysis/final-v1.json
NUMERIC=${OLENS_DATA_ROOT}/expansion-v1/reconstruction/final-v1.json
EFFORT=${OLENS_DATA_ROOT}/expansion-v1/analysis/effort-final-v1/effort.json
REVIEW=docs/reviews/root-expansion-final-v1.json
CHROME=${HOME}/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome
NODE=${HOME}/.nvm/versions/node/v24.14.0/bin/node
$PYRUN scripts/build_expansion_report.py --results "$NATIVE" --inventory configs/expansion_manifest_v1.json --review "$REVIEW" --reconstruction "$NUMERIC" --output .state/expanded-final-presentation-v1/report.md
$SLIDEPY scripts/build_expansion_slides.py --results "$NATIVE" --inventory configs/expansion_manifest_v1.json --review "$REVIEW" --reconstruction "$NUMERIC" --output .state/expanded-final-presentation-v1/slides --chrome "$CHROME" --node "$NODE"
$PYRUN scripts/build_expansion_dashboard.py --results "$NATIVE" --inventory configs/expansion_manifest_v1.json --review "$REVIEW" --reconstruction "$NUMERIC" --effort "$EFFORT" --output .state/expanded-final-presentation-v1/dashboard
```

A bounded invocation template for a single command is `srun --jobid=25536417 --overlap --ntasks=1 --cpus-per-task=2 --mem=8G --cpu-bind=cores ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python ...`; no broad simultaneous rendering while final numerical extraction is active. For slide builds/tests, replace the runtime Python in that invocation with `${OLENS_COMPUTE_ROOT}/envs/slides-v1/bin/python`; report/dashboard/merger continue to use runtime Python.

Existing presentation fixtures/QA (rerun only if source changes or final content exposes new failures):

```bash
$SLIDEPY -m unittest discover -s tests -p test_expansion_slides.py
$NODE scripts/check_expansion_slides_layout.mjs "$CHROME" /ABS/NEW/slides/expanded.html /ABS/NEW/slides/layout-manual-qa.json
```

Slide `--chrome` already runs layout checking and same-geometry HTML-mirror PDF rendering, checking all page dimensions/header/footer/text counts and retaining `build.json`, `source-contract.json`, source copies, `speaker-notes.md`, `render.json` and preview contact sheet. Do not duplicate or overwrite its existing `layout-qa.json`/PDF. Synthetic appendix receipt `.state/expanded-slides-appendix-v2.qa-receipt.json` records15 passing fixtures,86-page geometry,26 core/14 reconstruction appendix pages; it is not final-data browser/PPTX attestation. Inspect final overview tradeoff/whiskers, seven paired methodology/result pages, exact examples, raw/capped reference labels, full70 appendices and contact sheet. Native PowerPoint rendering parity remains unverified unless actually checked.

For dashboard final browser QA, copy `.state/check-real-dashboard-v5b-rerun.mjs` to a new final-only harness, update hardcoded1771 example count, root review SHA and V3-specific scope to exact final sources/counts, and preserve the old harness/artifacts. Run that adapted source once with:

```bash
$NODE .state/check-real-dashboard-final-v1.mjs "$CHROME" /ABS/NEW/dashboard/index.html /ABS/NEW/dashboard/qa.json
```

Existing14-view harness covers desktop/mobile overview, methodology/results/scaling, audited-example dialogs, detail modal and resources. Validate all embedded objects equal exact current artifacts before interaction and unchanged afterward; source count/dedup and inherited case preservation are independent checks, not browser proof. Check Intermediate numbers/first-ranked rule, hidden names/final-answer-optional captions, fit percentage-point references/masks/CIs/null warnings, mobile navigation drawer, no horizontal overflow, text/parent labels and source IDs. Retain overview plus selected likelihood/pruning/editing dialogs/screenshots and open actual images for root inspection. No stale “same as V3 except timestamp” wording.

Root alone reviews final scientific values/prose and handles publication. Source/structural/HTML browser checks do not prove native-PPTX or public-hosted rendering. Final publication, hosted browser check, artifact download hashes and local-only research commit are separate receipts; this checklist authorizes none of them.

## Exact current schema and draft source pins

These are current implementation/draft hashes, not future artifact hashes. Preserve running scientific authority; presentation-only edits, if later reviewed, need fresh QA/source pins.

| Source | SHA-256 |
|---|---|
| `scripts/analyze_expansion.py` | `9ba5a4966b53cc636e786c888bda8c9da267d31e0f6c3d7f5c5ae3b1b50d8281` |
| `src/olens_improve/expanded_statistics.py` | `66dc640a6a4c0760f2a9591e78554bdd5dfb3dba35e306675448c4280b1458c9` |
| `scripts/analyze_expansion_reconstruction_v5.py` | `cb9cc9a7578f0a617e6a567e2c14e3fcee720e1a807c0b452ca9b40f925a99f8` |
| `scripts/expanded_editor_fit_intake_v2.py` | `ec6a8de982fd25023a1130c6c4cb4ae87418765e0991629b171f58bf1c6e436f` |
| `scripts/build_expansion_qualitative.py` | `7fbc8b0a1cfe47e80f8d7d8964fda4557bbd592014e6f2d06a3384155738ddc2` |
| `scripts/build_expansion_parent_qualitative.py` | `9a831d435a34a5a46de5b62e6912fa3665d0d63f2efcaaee3c566bea0d1637bd` |
| `scripts/build_expansion_qualitative_delta_v2.py` | `f256deadf33797e2828a01885224168acbbad7256cc4965d08e26023e0841bc4` |
| `scripts/validate_expansion_qualitative_final_reviews.py` | `c02b5c60f7538900e1ae25cb2f68b67fd4496126e60edea0dbc6198a009de48d` |
| `scripts/build_expansion_report.py` | `c34a1ed48897944a8671216252fcfe513b098526c7a44a9a204c186f7613b4c7` |
| `scripts/build_expansion_slides.py` | `60dfccd35b6fcf4d7165c1a7ba5feb6e23b55972cd08acc4306eb77c4766388e` |
| `scripts/build_expansion_dashboard.py` | `761941ffb677beb5c6d374fbbf52cb0c2701f0af4567dbed491c1c0d55bd2d43` |
| `scripts/check_expansion_slides_layout.mjs` | `68be8b44241ac08ef06d5f21541d3bcb25b2fbbbdc1f213a4747c78f58e87da9` |
| `scripts/render_slides.mjs` | `b6892c99ca43e66719afa2b8524f35e860b7e6ab2f9f4369f7bb4a68f0da9ee2` |
| `.state/check-real-dashboard-v5b-rerun.mjs` | `ba5a574c60f18e0582a4978cf72e4d21a1c43966180e1f4ab740da781284b279` |
| `.state/expanded-final-review-draft-v3.json` | `d1889a8c31c5422b5805577cf00e8df9b353e81af9ac84a79a72a5c9bb17b2f7` |
| `docs/reviews/expanded-slide-example-candidates-v1.json` | `ac2f69c6fbe3c7540cc3ed99a642d73817869fc5d3458eb541518504c73cb68a` |
| `docs/reviews/expanded-slide-example-root-review-v1.json` | `81282a1a63cdceb01ec71f31795f8e3e10dc769303688da05b73b67d16b6abc0` |

Checklist prepared 2026-10-11T04:59:40.295712+00:00. No terminal artifacts were generated, and no runtime, pinned producer, scientific contract, Git state or publication was changed.

## Documentation correction: existing slide interpreter

The slide build and slide fixtures use the existing `envs/slides-v1/bin/python`; report, dashboard and qualitative merger use `envs/runtime/bin/python`. A short actual import (`cbfb8c`, exit0, 0.452 seconds) verified python-pptx1.0.2 from `envs/slides-v1/lib/python3.12/site-packages/pptx/__init__.py`. Root observed that runtime lacks pptx; no dependency was installed. This correction changes command documentation only. Operational counts above remain explicitly dated to the earlier bounded readiness check and are not rewritten as current terminal scientific results.
