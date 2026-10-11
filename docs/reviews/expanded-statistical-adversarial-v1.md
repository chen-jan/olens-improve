# Expanded statistical pipeline: independent adversarial review

This review found no native aggregation error in the 48 independently replayed rows. The saved partial result correctly blocks all simultaneous intervals. Before the final report, strengthen artifact validation and surface degenerate uncertainty on absolute metrics as well as paired comparisons. The adjusted intervals remain approximate exploratory uncertainty; they do not establish a fresh held-out result or an automatic method winner.

## Reviewed versions and evidence

Read-only review of the versions below, before the coordinator's subsequent offline-analysis updates. No active inference, judge, GPU or queue source was changed by this reviewer. No paid calls were made. The replay ran on the existing authorized CPU allocation **25536291**, one process pinned to core 44; no new allocation or dependency installation was needed.

| Source | SHA-256 |
|---|---|
| `src/olens_improve/expanded_statistics.py` | `09308cdebedaf1cd488e03f9029fc4656cc43d743836609bde9556b12179daac` |
| `configs/expansion_analysis_v1.json` | `c59b77fb2fc005eae0a34ac43f39d657259c45835d117e090cbf52eec6d8e909` |
| `scripts/analyze_expansion.py` | `66f2b9353792335b5a59a0cd87f971af6acd089a082594119741ae4f9493a102` |
| `scripts/build_expansion_report.py` | `7fe03d2cdbd7326129df859f7ce8503e436a6dc00f52d4e20dab8ff410356154` |
| Imported `src/olens_improve/reporting.py` | `7bc728136f19eac771ed3fb8c3b9077f416d047197bb3c9c0de2c431985ee319` |
| Sealed inventory | `753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8` |
| `${OLENS_DATA_ROOT}/expansion-v1/analysis/first-live-v1.json` | `1e2de7c6bf67507b84dac0cfb19dc7743a51396ba507dd49322e06508525dfe1` |

The independent counter does not call `family_counts` or `original_grid_pairs`. It reads saved readouts, classes, ranked-number kinds, required-name hits and three role correctness flags directly, validates their source hashes against the saved analysis, and independently reconstructs numerators and denominators. It checks raw N1, capped N1 and best-of-32 across four tasks and four cohorts: **48 rows**, including **12 exact matches to original TEST numerator/denominator pairs**. All passed. Separately, all **128 available terminal contracts** have one identical set of **21 runtime source hashes**, each matching the current pinned benchmark checkout. Twelve sampled terminal summaries also reproduce their on-disk upstream results exactly.

Receipts and reproducible probes:

- `.state/statistical-adversarial-v1/probe.py` and `receipt.json`; receipt SHA `9e04e9a298f3cbccaaf2469c3171d21fcb2b7cd565c919edf95531ad1e24b5a3`.
- `.state/statistical-adversarial-v1/provenance.py` and `provenance.json`; receipt SHA `e3283b1c9d2c351a69c139b258c63202e92384a47b5f4d2df24b85066fee726e`.

This is a bounded audit, not a replay of every condition-family raw journal or an empirical coverage study.

## Native aggregation and raw shapes: verified

| Task bank | Questions | Related groups | Fixed sites | Verified aggregation |
|---|---:|---:|---:|---|
| Transcript hallucination | 149 | 149 | 5,615 | Total hallucinated specific readouts / total specific readouts; includes consistent and off-topic readouts in the denominator |
| Hidden names | 100 | 94 | 1,100 | Any passing layer for each question; every required name must match at that layer |
| Arithmetic intermediates | 120 | 42 | 1,320 | Any layer classified `hit` for each question; not any named number anywhere |
| Role binding | 100 | 50 | 11,400 | All three role questions correct at one site, then any passing site for each question |

MT and arithmetic result rows encode outcomes by layer rather than position. This is valid for the actual sealed shapes: each of their questions has one frozen position across 11 layers. Role binding has 114 sites per question and requires a site outcome before the item ANY rule. In all three audited role arms, every saved `pass` flag agrees with the three `correct` flags; no discrepancy was found. Hallucination questions have unequal site counts, from 5 to 40. The estimator intentionally uses a ratio of pooled readout counts, not an average of question ratios. The resulting weighting must remain explicit.

The full-bank independent counts were:

| Setting | Contradictions / specific | Hidden-name questions | Arithmetic questions | Role questions |
|---|---:|---:|---:|---:|
| Raw N1 | 2,648 / 5,560 | 34 / 100 | 59 / 120 | 78 / 100 |
| Capped N1 | 2,641 / 5,554 | 34 / 100 | 57 / 120 | 78 / 100 |
| Best-of-32 | 2,550 / 5,565 | 40 / 100 | 61 / 120 | 77 / 100 |

Blank outputs remain produced abstentions. Capped hallucination has two blanks and best-of-32 one; neither becomes a missing API judgment. Every nonempty hallucination output in these sampled arms has the required stage-two tallies. The secondary assertion-share denominator includes all intended produced outputs; this appropriately differs from upstream's nonempty-readout denominator. False spans, true claims and unverifiable claims are not interchangeable atomic units.

Whole related groups, rather than individual activation sites, are resampled. Each draw gives all members of a sampled group the same multiplicity, preserving method pairing and unequal group sizes while retaining the stated item/readout-weighted estimand. Arithmetic has only 42 groups, including one group of ten questions; role has 50 two-question groups. More settings or sites do not increase these independent-group counts. Generalization still assumes that the declared groups adequately capture relevant dependence and represent the population of interest; the bootstrap does not validate that assumption.

## Findings requiring action before final interpretation

### 1. Absolute intervals need the same degeneracy warnings as paired intervals

In the audited `expanded_statistics.py:55-62`, absolute metrics discard undefined ratio draws, calculate quantiles of the remaining finite draws and report `defined_draws`, but attach no warning. Paired metrics correctly warn at lines 81-84. An all-zero or all-one recovery arm therefore gets an exact-looking zero-width absolute interval, even though observing no variation in a finite bank does not establish population certainty.

Independent exact enumeration of two resampled groups, one with no specific outputs and one with counts `(1, 2)`, yields three defined draws at 0.5 and one undefined draw. The implementation produced 7,489/10,000 defined draws and an absolute interval `[0.5, 0.5]`, without a warning; the paired output warned correctly and withheld its simultaneous interval. This interval is conditional on defined draws, not an unconditional 95% statement covering denominator failure.

In the real saved partial artifact, no full/TEST/DEV absolute interval collapsed, but **22 pilot absolute intervals did**. Paired zero-variation warnings numbered 11 full, 13 TEST, 20 DEV and 46 pilot. Thus the problem is already relevant to the diagnostic cohort, not only hypothetical.

**Action:** export absolute `bootstrap_replicates`, `defined_draws` and warnings for undefined draws and zero variation; retain valid 0% and distinguish a zero denominator from an unmeasured result. Carry those warnings into graphs, method dialogs and the final table or adjacent notes. Do not introduce hypothesis tests or discard methods on this basis. The coordinator has begun this offline-analysis correction; the old source-bound `first-live-v1.json` remains the version audited here and needs regeneration before its absolute warnings can change.

### 2. Report the effective joint interval family separately from 496 declared contrasts

The frozen menu contains **124 distinct directed comparisons × four endpoints = 496**. `expanded_statistics.py:81-87` excludes contrasts with undefined draws or zero bootstrap variation from the maximum. At lines 88 and 104, `comparison_family_complete` means no arm is missing, not that all 496 contrasts received simultaneous intervals.

A two-contrast probe with one constant nonzero difference and one variable difference returned `comparison_family_complete=True`, `declared_contrasts=2`, a joint critical value, an interval for the variable contrast and no interval for the constant contrast. This is consistent with the declared “usable contrasts” policy, but it must not be described as 95% simultaneous coverage for every declared contrast.

**Action:** expose declared count, available contrast count, effective nondegenerate count, actual joint-interval count and blocked contrast reasons. “Complete data” and “all contrasts covered by joint intervals” need distinct meanings. The coordinator is adding effective and interval counts before the next extraction.

For the actual partial artifact, each cohort has 174 available and 322 missing contrasts, and **zero simultaneous intervals**. The existing missing-family protection works. `analyze_expansion.py:125-132` also blocks intervals if an entire task is absent, rather than silently shrinking the four-task family. The final report builder requires all 70 × four native rows, rejects duplicates/foreign rows, requires no missing condition-families and checks native endpoint names and frozen group counts (`build_expansion_report.py:53-64`).

### 3. Validate terminal summaries and frozen instrument identities explicitly

`analyze_expansion.py:80-88` requires terminal summary/result/contract/readout files and checks selected text provenance, inventory identity, model, effort and coverage flags. However, it does not check the summary's saved upstream result against `results.json`, the benchmark commit/runtime source pins, result family/dry-run state, exact expected/produced counts, or the summary's exact method/N/family-manifest identity. The original `reporting.py:summarize` contains stronger analogous checks.

No scientific mismatch was found in the sampled artifacts. All 128 contracts have identical runtime hashes, and all 21 hash values match the pinned checkout. All twelve sampled summary upstream payloads equal their corresponding result files; result family, non-dry-run state and expected/produced counts are correct.

**Important schema detail:** naive equality of summary and on-disk contract would reject valid current artifacts. The summary embeds `run_family`'s earlier contract, then `expanded_judges.py:150-155` updates only the external contract's `scientific_status`, `inventory_sha256` and `original_splits_preserved`. All twelve sampled artifacts have exactly these three differences: `frozen-grid-comparison` becomes `exploratory-full-bank-comparison`, inventory SHA is added, and split preservation becomes true. This is a known metadata sequencing difference, not evidence of changed judgments.

**Action at the next analysis boundary, without changing running services:**

1. Require `summary.families[family].upstream == result`; verify `result.family`, `config.dry_run is False`, and the declared benchmark commit.
2. Require summary condition method/N/manifest SHA to equal the exact condition and ready descriptor; retain selected source SHA and inventory checks.
3. Compare the embedded and external contracts after normalizing only those three known metadata updates, while requiring their expected values. All remaining fields must agree.
4. Check exact expected and produced cell counts. Compare runtime source hashes against an approved, source-bound instrument receipt, not merely whatever files happen to exist today. The 21-hash dictionary in the provenance receipt provides the audited candidate pin.
5. Do **not** require upstream `complete` or `pinned_instrument` to be true. The sampled project results correctly preserve upstream false flags for the declared Luna/single-readout override; full project completion is established by the explicit grid and stage-coverage checks.

### 4. Bind the bytes actually parsed and every analysis dependency

The analyzer records hashes after loading several result objects (`analyze_expansion.py:84` versus line 100) and rechecks those hashes at the end. A file replaced between parsing and the first hash can therefore leave a parsed older object bound to a newer file digest. A terminal file's immutability reduces this risk, but the end-of-run hash check alone does not close it.

The pilot split file is loaded at line 51 but omitted from `source_sha256`; `reporting.py` and the imported source-reading helper affect computation but are omitted from `implementation_sha256` at lines 146-148 of the reviewed version. Full native rows do not depend on the pilot subset, but pilot reproducibility does.

**Action:** read each JSON object's bytes once, hash those same bytes, then parse; retain final immutability checks. Include the pilot split and imported aggregation/helper implementations in the source receipt. This is provenance hardening; no observed numerical failure was found.

### 5. Clarify the statistical authority and preserved original TEST evidence

The sealed inventory's `multiplicity_policy` at line 3685 still mentions paired tests and Holm correction, whereas the separately frozen analysis config at lines 12-15 specifies the bootstrap maximum and no p-values. The actual implementation follows the analysis config. The final report should name that configuration as the governing analysis contract and explicitly document its precedence. Preserve the sealed inventory bytes rather than silently rewriting the historical field.

`build_expansion_report.py:106-110` says adjustment “preserves this adaptive history.” The intended limit should be direct: adjustment does not correct for adaptive method design or turn inspected questions into fresh held-out evidence. The builder's earlier sentence about defined, nondegenerate contrasts is sound but needs the effective count from finding 2.

The original TEST source remains `${OLENS_DATA_ROOT}/runs/test-full-grid-comparison-v2/final-analysis-v2.json`, SHA `75dee255d88104450fa4424610178baa4df24964394be77812fa218379cfcef8`, referenced independently by `dashboard/report.json`. All twelve baseline TEST count pairs replayed here match it. The expansion does not overwrite that source. The expansion dashboard deliberately replaces matching displayed rows/comparisons with newly analyzed exploratory rows while preserving other old rows (`build_expansion_dashboard.py:181-202`); numerical equality of baseline counts does not imply identical bootstrap intervals or inferential status.

**Action:** retain a direct, hash-bound link or separate evidence panel for the earlier frozen TEST artifact and its original intervals. Label newly calculated TEST-subcohort intervals exploratory. The final report's statement that the earlier report is “preserved separately” should identify the exact artifact, not leave readers to infer that the merged current panel is the original frozen analysis.

## What the joint adjustment justifies

The implementation resamples families independently and uses shared draws within each family. It computes the maximum absolute centered error divided by each contrast's fixed bootstrap standard deviation, takes its empirical 95th percentile, and gives each eligible difference a symmetric width. This is a centered standardized bootstrap maximum, not a per-draw studentized bootstrap-t calculation. Taking the hull with the pointwise interval widens the reported interval; clipping to the feasible difference range `[-1, 1]` respects the estimand's bounds. I found no algebraic issue in these operations.

The result is **approximate bootstrap simultaneous uncertainty over the eligible fixed contrast menu for one cohort**, conditional on the grouping and resampling assumptions. It is not a finite-sample guarantee, a Holm test, a p-value, a proof that a ranked winner is best, or an adjustment over every conceivable pair. Different task families are treated as independent banks in the joint draws. This assumption should be disclosed; it was not empirically established by the code. Each of full/TEST/DEV/pilot is analyzed separately, so the 496-contrast adjustment is not a joint guarantee across all four overlapping cohort views, secondary claim metrics, qualitative examples or subsequent adaptive decisions.

Recovery measures required content under the declared benchmark instrument; it does not establish faithful surrounding prose. Hallucination's lower-is-better conditional ratio can change because of assertion coverage and off-topic outputs, so interpretation needs those secondary counts. Cross-task scatter axes come from different task banks and must not be read as within-example precision/recall. Natural output lengths confound a claim that a method's advantage is independent of length. No pooled accuracy or automatic significance-based shortlist is justified.

Suggested report wording:

> All expansion results are exploratory because these questions were inspected before method expansion. We report pointwise grouped intervals and approximate joint intervals for the eligible members of a fixed 496-contrast menu, with effective counts and blocked contrasts shown. This adjustment addresses that declared comparison menu under the resampling assumptions; it does not remove adaptive method history, cover all dashboard views and secondary outcomes, or identify an automatic winner. The earlier frozen TEST analysis remains available as a separate source-bound artifact.

## Operational receipt

During this review GPU likelihood job **25536297** continued progressing, most recently observed at **4,654 / 19,435** cells, approximately **0.819 seconds/cell**, with full batches of 32. The CPU editing bridge remained watching with an empty error dictionary and all four round-one descriptors queued. No source edits were made to either active service. Later analysis changes by the coordinator require a new result source hash; this review does not silently substitute that future result for the audited partial artifact.
