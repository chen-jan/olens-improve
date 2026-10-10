# 019: Larger development comparison

Frozen before full-development method selections or judgments: 2026-10-10,
approximately 04:17 UTC. This is an adaptive development follow-up to the
189-cell pilot, not a preregistered confirmatory test. Validation and test
readouts remain sealed. Baseline raw/capped N1 results have already been seen.

Use all 5,236 development cells from the complete original grids in
`configs/development-full-grid-v2.json`, the immutable 32-sample snapshot at
`durable/runs/development-full-grid-v2`, and the existing matched controls.
The four selection shards must use one identical scoring contract, preserve
every original source ID, and pass a complete-cohort merge check. Raw and capped
N1 texts must match the early baseline export exactly before reusing judgments.

The first comparison comprises 24 conditions:

| Conditions | Purpose |
|---|---|
| Raw and capped N1 | Released behavior and the common output cap |
| Best exact reconstruction at N=1,2,4,8,16,32 | Sampling curve; N1 also exposes parser-based abstention |
| One frozen random complete sample at N16 and N32 | Same-pool random controls |
| Pooled selection at N16 and N32 | Complementary information across samples |
| Best-of-32 followed by pruning at .001 and .005, and both matched-count random deletions | Contribution-based deletion versus simply shortening |
| Capped N1 followed by .005 pruning and its matched-count random deletion | Low-generation-cost pruning |
| Mean-control and maximum-control specificity at N32 | Selection using matched control activations |
| Mean specificity followed by .001/.005 pruning, and both matched-count random deletions | Promising combination and component/shortening controls |

All thresholds, donor lists, random seeds and numerical objectives are inherited
unchanged from the pilot. The .001 threshold remains sensitive to the measured
numerical drift scale. Source-compatible approximate reconstruction is retained
as an offline numerical diagnostic; the primary quality comparison uses exact
nonnegative least squares. No threshold is fitted to individual benchmark
answers. The inference modules never receive judge results.

The additional matched-donor N1 control is a separately labeled diagnostic of
activation dependence. The all32 candidate-quality diagnostic stays on the
original 189 cells. A new bounded pilot may combine pooling with specificity;
it is outside this frozen 24-condition list and requires its own recorded
decision before expansion. Semantic consensus, free editing and likelihood
selection are not broadly expanded on their present evidence. Their pilot
results and limitations remain part of the report.

The frozen condition lists are `configs/conditions_full_dev_v1.json` (20 base
selector conditions) and `configs/conditions_full_dev_combinations_v1.json`
(four additional specificity/pruning conditions). Judge every final readout
separately with the pinned Luna recipe, full hallucination stage2 and the
existing multihop regex. Reuse exact request keys, not merely similar text.
Forecast unique uncached requests before launch. Initial API run ceiling: $20
for these comparisons, inside the unchanged project ceiling; an incomplete
condition is never presented as a completed score.

If the forecast approaches that ceiling, dispatch complete comparisons in this
priority order: raw/capped N1 and best-of-32; mean specificity and its two pruning
variants with both matched deletions; the remaining N scaling curve; pooled
selection and best-of-32 pruning with matched deletions; low-cost N1 pruning,
maximum-control specificity and frozen random draws. Reserve hallucination
stage2 and retries before starting each arm. Freeze the resulting dispatch list
before paid execution rather than stopping after a favorable result. Any omitted
arm remains explicitly incomplete. The separately judged 189-cell all32 pool
provides expected-random sensitivity evidence; it does not replace the frozen
full-development random controls.

Report original item aggregation and cell-level results side by side. The
primary hallucination endpoint retains its asserting-readout denominator;
include assertion share, off-topic outputs, claim tallies, missingness and
length. For recovery, an item-level ANY passing site is distinct from broadly
correct descriptions. Use related-group paired uncertainty, with family counts
and the small seven-group chain limitation visible. Inspect deterministic and
seeded examples of gains, losses and unchanged outputs; check whether recovered
names/numbers sit inside incorrect relations or computations.

Quality remains the priority. Show observed quality/cost tradeoffs rather than
selecting solely by a significance cutoff or a single pooled score. Keep campaign
spending, cached-selector work and estimated new-input inference costs separate.
Report shared generation/AR work, CPU selection, helper calls, tokens and
latency/throughput caveats. GPU dollar cost remains unknown.

After this comparison, freeze a small validation shortlist and its operating
settings. A method with a useful family-specific effect may advance despite a
wide interval; a tiny score advantage explained by shorter output, judge
instability or increased errors elsewhere is not sufficient by itself. Preserve
raw/capped N1 and best-of-N comparators, plus component-off and shortening
controls for any advancing combination. Freeze the final selection before
opening test results. Do not choose a favorable operating point on the test set.

## Execution corrections before judging

The first four CPU workers unintentionally shared the same four physical cores
under overlapping Slurm steps. They were stopped with 21 complete cell records
preserved, no malformed journal tail, and 3,075.95 summed process CPU-seconds
recorded. The source samples, vectors and evaluation settings were unchanged.

Before restarting, a coverage audit found two N1 samples with a non-bullet
preamble. The random-control branch previously omitted its result when every
sample in the prefix was parsing-ineligible. It now emits an explicit empty
readout with `no_eligible_complete_sample`, matching best-of-N's handling of
that case. Eligible seeded choices are unchanged; two regression tests pass.
This concerns the auxiliary random-N1 diagnostic, not a change to the frozen
20 base conditions above. The fix is local commit `7684d6f`.

The corrected outputs use `durable/selections/development-full-grid-v3/`;
the frozen cohort and sample snapshot remain development-full-grid-v2. Earlier
partial outputs and logs remain under the previous selector directory. Four
workers request the allocation-wide CPU set, then bind to disjoint four-core
subsets. Validate overlapping old/new completed scientific outputs, the final
cohort merge, and early raw/capped baseline identity before judging. Record the
restart's compute in campaign cost rather than dropping the initial attempt.

The v3 run then stopped at 2,018 committed cells because a bullet had no tokens
after released AR cleanup. A complete source audit found 523 such bullets in
395 samples and 103 role cells: 522 contain only formatting tags and one is
whitespace. Ten N1 cells contain 17 affected bullets. Every span and activation
hash matches the immutable generated pool; this is not a corrupted vector.
The source reconstructor treats empty-cleaned inputs as invalid. Its zero
placeholders must not be whitened and interpreted as concept predictions.

The reviewed fix preserves raw/capped/random baseline text and records absent
fits explicitly. Reconstruction-guided complete selection excludes an
unscoreable complete sample. Pooling may use its valid individual bullets but
cannot label a partial set as that complete-sample fallback. Pruning an
unscoreable N1 parent leaves it unchanged with an explicit unavailable reason;
its matched-count deletion control is likewise unchanged. A genuinely empty
selected set retains the defined FVE of zero. Per-sample invalid atom provenance
is included in every selection record. These eligibility differences must be
reported, not hidden as zero scores or missing cells.

Five focused tests and a two-cell real replay passed, including one affected
N1 parent and the whitespace case, with all 40 offline condition rows retained.
Local commit `3b96f8e` records the fix. A new four-shard run writes
`durable/selections/development-full-grid-v4/`; v3 files remain unchanged and
bound by `error-provenance.json`. The frozen scientific 24-condition list,
candidate pools, controls and thresholds are unchanged. Check overlapping
scientific outputs and all early baseline texts before judging v4.
