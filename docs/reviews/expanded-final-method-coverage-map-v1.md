# Frozen expanded method coverage map

This is an inventory map, not a terminal-results receipt or performance finding. The finite expansion schedules **70 setting IDs across four task banks**, arranged into **six intervention groups (original A–F) plus combinations**. The seventh display group is combinations; original **G, an independent activation reader/scorer, is postponed**. Do not describe this as all seven original approaches completed, 70 independent algorithms, or coverage of all WorkspaceBench families.

The four frozen banks are `hallucination`, `multihop_mt`, `chain_intermediates`, and `role_bound_association`: 469 questions and19,435 original activation sites, preserving original grids/splits. This expansion is exploratory because all469 questions were previously inspected; the original held-out study remains separate. Full coverage is certified only by the final70×4 terminal receipts.

| Display group | Original plan | Settings | What is actually included; comparable inputs and cost reuse |
|---|---|---:|---|
| Choose a complete readout | A | 14 | Raw/capped single-sample references; reconstruction-best and random complete-candidate choices at N=1/2/4/8/16/32. All prefixes reuse the same32 original samples and cached phrase vectors. N counts candidates, not independent questions. Raw/capped are not reconstruction-based selectors; scoring-eligible A1 differs from deterministic cappedN1. |
| Keep repeated statements | B | 13 | Four exact/named-control settings, five repaired ordinary semantic settings, four medium-confirmation settings; all N16. Ordinary and medium reuse identical proposals, pair identities and exclusions. Threshold/compatibility/veto variants reuse the respective label reports rather than paying unique helper calls for each output. Missing labels remain unknown; original whole bullets survive. |
| Remove weak bullets | C | 16 | Eight variants on best32 and eight on cappedN1: sequential leave-one-out thresholds0/.001/.005, their matched-count random deletions, and coefficient cutoffs.01/.05. These reuse parent texts/vectors and local NNLS refits; random controls match bullet deletion count, not exact token length. They remove whole bullets, not separately tested within-bullet details. |
| Combine original bullets | D | 2 | Greedy joint-refit/local-swap pooling at N16 and N32, within one activation site and the four-bullet/256-token cap. Existing source bullets/vectors are reused. Numerical selection rounds create no new O-lens samples. Natural output lengths are retained; pool construction/refitting still costs CPU work. |
| Compare activation evidence | E1 + E3 | 6 | Three N32 specificity settings: mean-control, max-control, mean with nonpositive-score abstention. They reuse existing AR vectors and eight frozen requested matched controls with group exclusions. Three N8 likelihood settings: own, two-control mean, and own-minus-controls. One shared teacher-forced scoring pass supplies all three; this is extra model computation, not new readout generation or a second reader. |
| Edit a readout | F | 2 | One/two bounded rounds on the shared N32 pool, starting from best32 and pooled32. At most four proposals total per cell/round across at most two parents; R2 retains full R1 history. Helper work and fresh phrase encoding are extra inference costs. Original/prior candidates remain eligible; a retained prior edit is not a newly selected R2 proposal. |
| Combine approaches | Components of A–F | 17 | Specificity→pruning/deletion4; pooled32→pruning/deletion4; editedR2→pruning/deletion4; exact-support+pooling N16 two nonzero weights; pooled specificity32 with its pruning/deletion3. Parent vectors, support labels, control scores and editor proposals/encodings are reused; downstream selectors incur their own CPU refits and benchmark evaluations. No extra independent component-helper charge is implied. |

Counts are obtained by applying the current builder's `category(method)` to only manifest statuses `cached_selector_full_bank` or `scheduled_full_bank`; they equal14/13/16/2/6/2/17 and sum70. The Standard Luna benchmark evaluation cost is experimental measurement overhead, distinct from a new input's method inference cost. Cache-identical requests can be reused, so settings are not 70 independently paid generation pipelines. Actual charges/tokens/timing come from the final effort artifact, not this inventory.

## Exact active IDs

The IDs below are transcribed from the sealed manifest and equal the exact dispatch menu. Named controls can intentionally produce identical text: `exact_support_only-n16` is retained as a named component-off control alongside `consensus_exact_support0-n16`. Counting them as settings does not establish distinct algorithms or independent evidence.

### Complete selection —14

```text
raw_n1-n1
capped_n1-n1
best_n_exact-n1
best_n_exact-n2
best_n_exact-n4
best_n_exact-n8
best_n_exact-n16
best_n_exact-n32
random_complete-n16
random_complete-n32
random_complete-n1
random_complete-n2
random_complete-n4
random_complete-n8
```

### Repeated statements —13

```text
consensus_exact_support0-n16
consensus_exact_support0.125-n16
consensus_exact_support0.25-n16
exact_support_only-n16
consensus_semantic_v5_support0_compatoff_vetooff-n16
consensus_semantic_v5_support0_compatoff_vetoon-n16
consensus_semantic_v5_support0_compaton_vetoon-n16
consensus_semantic_v5_support0.125_compatoff_vetoon-n16
consensus_semantic_v5_support0.125_compaton_vetoon-n16
consensus_semantic_v5_medium_support0_compatoff_vetoon-n16
consensus_semantic_v5_medium_support0_compaton_vetoon-n16
consensus_semantic_v5_medium_support0.125_compatoff_vetoon-n16
consensus_semantic_v5_medium_support0.125_compaton_vetoon-n16
```

### Whole-bullet pruning —16

```text
prune_loo_a32_0.001-n32
prune_loo_a32_0.005-n32
random_delete_matched_a32_0.001-n32
random_delete_matched_a32_0.005-n32
prune_loo_n1_0.005-n1
random_delete_matched_n1_0.005-n1
prune_loo_a32_0-n32
random_delete_matched_a32_0-n32
prune_coefficient_a32_0.01-n32
prune_coefficient_a32_0.05-n32
prune_loo_n1_0-n1
random_delete_matched_n1_0-n1
prune_loo_n1_0.001-n1
random_delete_matched_n1_0.001-n1
prune_coefficient_n1_0.01-n1
prune_coefficient_n1_0.05-n1
```

### Pooling —2

```text
pooled_greedy_swap-n16
pooled_greedy_swap-n32
```

### Activation comparisons —6

```text
best_n_specificity_mean-n32
best_n_specificity_max-n32
likelihood_true_minus_mean_two_controls-n8
own_mean_log_likelihood-n8
control_mean_log_likelihood-n8
best_n_specificity_mean_abstain_nonpositive-n32
```

### Editing —2

```text
editing_round1-n32
editing_round2-n32
```

### Combinations —17

```text
best_n_specificity_mean_then_prune_0.001-n32
best_n_specificity_mean_then_prune_0.005-n32
best_n_specificity_mean_random_delete_matched_0.001-n32
best_n_specificity_mean_random_delete_matched_0.005-n32
pooled_greedy_swap_then_prune_0.001-n32
pooled_greedy_swap_random_delete_matched_0.001-n32
pooled_greedy_swap_then_prune_0.005-n32
pooled_greedy_swap_random_delete_matched_0.005-n32
editing_round2_then_prune_0.001-n32
editing_round2_random_delete_matched_0.001-n32
editing_round2_then_prune_0.005-n32
editing_round2_random_delete_matched_0.005-n32
pooling_exact_support_lambda0.05-n16
pooling_exact_support_lambda0.2-n16
pooled_specificity_mean-n32
pooled_specificity_mean_then_prune_0.005-n32
pooled_specificity_mean_random_delete_matched_0.005-n32
```

## Work outside the expanded70

- **Atomic-claim rewriting or claim-level consensus:** no full-bank expansion setting. Primary matching/selection preserves original whole bullets. A separate historical verbatim source-span contract audit stopped after8 cells of a proposed32-cell pilot; benchmark quality was not measured. This is neither completed full-bank atomic rewriting nor evidence that all claim-level methods fail.
- **Within-bullet detail pruning:** no separate full-bank condition or established result. Whole-bullet pruning and candidate-only editing do not silently count as this proposed experiment.
- **Fresh sampling aboveN32 or residual resampling:** not run in this expansion. No free additional generations, N64 curve, changed source activation, new training or cross-site pooling. Four numerical greedy steps are not four generation rounds.
- **Original G / second activation reader or scorer:** no new J++, NLA, second reconstructor or independent-reader selector. Historical bounded reader engineering/DEV diagnostics remain separate; postponed work is not a negative result. The activation-blind semantic helper and evaluation judge are not an independent activation reader.
- **E2 semantic near-miss selection:** no full-bank candidate-only near-miss selector. The historical completed E2 artifact contains36 **correlated DEV comparison sets** from four number pairs and four role pairs at layers20/44/60, including wording variants; these are not36 independent questions. Known diagnostic labels never enter inference. Verified balanced negation pairs were unavailable. E2 is outside the70 active output settings and does not establish downstream improvement.
- **Unlisted cross-products or new length matching:** not run. The user removed baseline-length-capped/random-pooling length-matching additions. Recorded matched-count deletion controls remain. Medium confirms the same semantic proposal/pair scope; it does not license all support fractions or compatibility/veto cross-products.

The sealed inventory also retains6 `best_n_released80` numerical diagnostics,6 obsolete malformed semantic-v4 IDs, and1 exact alias (`pooling_exact_support_lambda0-n16`). They are excluded from active70; no repeat malformed-helper campaign or independent judgment count is inferred. The named active control above is deliberately retained despite text equivalence.

## Source pins

These pins bind the inventory/classifier, implementation cost-sharing contracts and historical diagnostic scope. They do not attest live completion. Files were rehashed unchanged after transcription; mutable handoff/status pages are not the authority for this map.

| Source | SHA256 |
|---|---|
| `configs/expansion_manifest_v1.json` | `753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8` |
| `configs/conditions_expansion_v1.json` | `b1f9865999aa30480dda2b7add68dcab880d99d5b51065a980a38cef61478852` |
| `scripts/build_expansion_dashboard.py` | `761941ffb677beb5c6d374fbbf52cb0c2701f0af4567dbed491c1c0d55bd2d43` |
| `dashboard/expansion.js` | `3f7a37c1d7ede121b2f225d0d11b71763c00407fea835bc76991032c1567aef7` |
| `docs/EXPANSION_PLAN.md` | `b20574bd3338b42c01bcd65c7e432f37ebc03c7eeb862e37b859b3eaad405d09` |
| `docs/METHODS.md` | `3a0e0eae17d1c8a24abf4261ad69056559ea680d7fe68ffe51f1ec0de2667436` |
| `docs/experiments/004-contrastive-diagnostic.md` | `b0e02af7edc0a9e4796a69fc70ad9be741701701bbae37292d7bcd9230266ad3` |
| `docs/experiments/024-exact-source-span-consensus.md` | `06f98e960571d2d9458d2f2003e4008677441a3ec25f9929d545b33a99bffafd` |
| `scripts/expanded_api.py` | `afbf52dd86f1818f503fa5c0c9b4e4e3843e1d1076468286721a9a4c353313b6` |
| `scripts/expanded_helpers_service.py` | `084da1579830a2b51329eb47d0c185c1f565fe975a5034aef6b362bdda1faff1` |
| `scripts/expanded_cpu_combinations.py` | `dc5847b137a0569084c39d664cc4a8a6afef1851c5adc3a93beaa9e9c8737ecd` |
| `scripts/expanded_encode_edits.py` | `121e9910af24339ee8448301e9f05e2e845d8e9bf695aa98af9efe20e619231e` |
| `configs/expansion_likelihood_controls_v1.json` | `8525f8b4a97c9731d00725711f7231d9a96346b7ebe4ea8426d25bd3204d7b1f` |
| `${OLENS_DATA_ROOT}/manifests/development-matched-controls-v2-metadata-v1.json` | `ccca28d80794d4de7e612b3a7b1924a9f1e2a43259e31f3b77841e14a18be520` |
| `${OLENS_DATA_ROOT}/diagnostics/e2-expanded-v1/manifest.json` | `9f050c9d0f6ef3393f281bffc35b55e03e08d0d27cf869fd047b32e86755958f` |
| `${OLENS_DATA_ROOT}/diagnostics/e2-expanded-v1/results.json` | `ec8b86dd5eb10390631724a8fe56cfc7c8f1740348eb7664c22631fdf75bf676` |
