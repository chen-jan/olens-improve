# Improving Oracle Lens with inference-time computation

Working research report, 2026-10-10. **Held-out evaluation is pending.** The
findings below describe development experiments and must not be read as a
validated recommendation for a final method. Live operational status is in
[STATUS.md](STATUS.md); the [dashboard](../dashboard/index.html) provides
interactive results and method details.

## What we have learned

Oracle Lens can produce useful concepts that its reconstruction score fails to
select. More sampling and recombining bullets improve the reconstruction score,
but useful recovery varies by task and does not consistently increase with the
sample count. A correct name or number can also appear inside an incorrect
relationship or calculation. These findings make independent evaluation and
inspection of the surrounding text necessary.

The most promising pilot combination selects a complete response using matched
control activations, then removes bullets with small reconstruction contribution.
It retains more recovery than random deletion on the pilot. Its apparent gains
include judge-sensitive cases with remaining contradictions, so a larger
comparison and held-out test are required. Whole-bullet consensus and free editing
have not justified broad expansion on the evidence collected so far.

## Question and experimental controls

We ask whether additional inference computation can make a frozen activation
reader more useful and faithful. We use the released Qwen3.6-27B Oracle Lens and
its matched activation reconstructor from
[agu18dec/olens_and_ar](https://huggingface.co/agu18dec/olens_and_ar).
All methods interpret the same vector at the same layer and token position.
There are no weight updates and no extra observation sites for improved methods.
The exact model revisions, injection settings, whitening transformation and
source-code checks are recorded in [the plan](PLAN.md) and
[model validation](experiments/001-model-setup.md).

Each cell has one shared pool of at most 32 sampled responses. Best-of-N uses
nested prefixes, so its N16 candidates are included in N32. Improved outputs
contain at most four intact source bullets and 256 Qwen text tokens; a separate
capped single-sample baseline isolates this restriction. We retain the unmodified
released baseline, including its 256-new-token generation limit. Only the explicitly labeled editing and source-span
experiments change text within a bullet.

With fixed candidate scores, the highest reconstruction score cannot decrease
as a nested pool grows. Pooling also retains the best complete response as a
fallback. These score guarantees follow from the selection rules; the empirical
question is whether the resulting descriptions become more faithful.

The reconstructor converts each phrase to a predicted activation. We center and
whiten both predictions and target using matched released statistics, then
normalize phrase directions while retaining the target's magnitude. Exact
SciPy nonnegative least squares combines those directions; the released
80-step approximate solver is a separately reported diagnostic. The fraction of
variance explained, abbreviated FVE, measures how well the combined prediction
fits the observed vector. It is a reconstruction objective; correctness is
measured separately. Inference methods receive neither benchmark answers nor
judge results.

The released encoder scores only the first 32 cleaned tokens of each phrase;
the judge sees the full output. Reconstruction therefore does not verify details
beyond that span. All comparisons share persisted phrase vectors, including
earlier batch-32 entries and newly encoded batch-128 entries. An expanded
batch-size audit exceeded its provisional equivalence limits: maximum FVE drift
was .003524, with pooled output text changing in 2/12 cells and matched-control
selection in 1/12. The fixed implementation remains reproducible, but small
selection margins and pruning thresholds are not certified numerically robust.
See [the numerical audit](experiments/018-parallel-ar-cache.md).

## Data and what the measurements mean

The four [WorkspaceBench](https://github.com/camilablank/workspace-bench) families
cover transcript contradictions, hidden bridge concepts, computational
intermediates, and directed entity roles. Related prompts and role reversals
stay together when assigning development, validation and test groups.

| Cohort | Items | Activation cells | Role in this study |
|---|---:|---:|---|
| Small development pilot | 31 | 189 | Method iteration and failure diagnosis; selected cells |
| Full development | 121 | 5,236 | Larger method comparison using original complete read grids |
| Validation | 80 | 3,485 | Selection among development-frozen candidates; outcomes still sealed |
| Test | 268 | 10,714 | Final frozen comparison; not opened |

The pilot is a subset of development. Cells from the same prompt are correlated.
Paired uncertainty intervals resample related item groups, not individual cells.
The pilot has only 2–8 independent groups per family; full development has seven
chain-template groups. A large number of cells does not erase those limitations.

GPT-6 Luna is the sole language-model benchmark judge, with its reasoning setting
fixed to none. Multi-hop bridge recovery uses the released deterministic matching
rule. Results retain the original item aggregation alongside cell-level rates.
An item can pass because one inspected site contains the required concept, even
when most descriptions fail. Reusing an exactly matching cached judgment saves
evaluation cost without creating another independent measurement.

For hallucinations, we report contradicted readouts divided by specific readouts,
following the benchmark. Specific readouts include off-topic outputs. We also
report the fraction of all outputs that make specific assertions, off-topic
outputs, and claim-verification results. Unverifiable claims remain distinct
from false claims. The four families use different prompts: plotting their
error and recovery rates together is a cross-task tradeoff, not a precision–recall
curve over the same items.

## Results from the shared pilot

The following selected comparisons use the same 189 cells. The recovery columns
count cells containing the benchmark-required information; they do not certify
every statement in the output. The hallucination family contains 72 cells, with
the asserting denominator shown for each method. Complete results and paired
grouped intervals are available in the
[pilot comparison](experiments/009-pilot-grouped-comparisons.md).

| Method | Contradicted / specific | Bridge recovery / 24 | Chain recovery / 21 | Role recovery / 72 |
|---|---:|---:|---:|---:|
| Capped single sample | 46/71 | 4 | 0 | 8 |
| Best reconstruction, N4 | 42/72 | 7 | 1 | 9 |
| Best reconstruction, N16 | 40/71 | 9 | 3 | 8 |
| Best reconstruction, N32 | 39/71 | 7 | 3 | 9 |
| One frozen random sample from N32 | 38/72 | 8 | 2 | 8 |
| Pooled bullets, N32 | 42/70 | 10 | 1 | 8 |
| Matched-control selection, N32 | 38/71 | 7 | 1 | 9 |
| Matched-control selection then .005 pruning | 36/72 | 7 | 1 | 12 |
| Same parent, matched-count random deletion | 37/72 | 5 | 0 | 7 |

Best-of-32 has fewer contradicted outputs than the single-sample baseline here,
but one frozen random draw does too. The all-candidate diagnostic therefore
evaluates the entire saved pool on this small cohort. A bridge mention occurs
in at least one candidate in 14/24 cells, versus 7/24 selected by best-of-32.
This identifies missed selection opportunities. It is an evaluation-only ceiling
and cannot be used to select a deployable answer. Passing candidates can still
contain false surrounding claims. See
[candidate ranking](experiments/012-all-candidate-diagnostic.md).

## Larger development results

Best-of-32 versus the capped single sample is complete on all 5,236 development
cells. The other method comparisons are still being judged. Intervals below
resample related groups in pairs; these exploratory comparisons are not adjusted
for the other methods examined during development.

| Endpoint | Capped single sample | Best-of-32 | Change in percentage points [95% interval] |
|---|---:|---:|---:|
| Contradicted / specific readouts | 543/1,137 | 523/1,140 | −1.88 [−5.41, +1.76] |
| Bridge recovery / 341 cells | 29 | 43 | +4.11 [+1.82, +6.61] |
| Chain recovery / 330 cells | 26 | 30 | +1.21 [−3.16, +4.85] |
| Role recovery / 3,420 cells | 151 | 182 | +0.91 [+0.15, +1.73] |

The original item-level aggregation gives 11→14/31 bridge items, 15→19/30 chain
items, and 23→23/30 role items. Thus more role cells pass without recovering an
additional item. The chain comparison contains only seven independent template
groups. The hallucination difference remains uncertain: fewer readouts are
flagged wrong, but the total flagged false spans rises from 1,305 to 1,324.
Span counts and supported-claim counts use different segmentation and cannot
be combined into a claim-precision estimate. Off-topic outputs decrease from
148 to 134. Both the favorable changes and these limits matter.

Systematic trace inspection confirms that recovery can coexist with error.
One selected chain output contains the required intermediate 18 alongside an
incorrect account of how it was calculated and competing numbers. Some newly
passing role descriptions retain unsupported names or details, with judgment
sensitive to how unnamed roles are interpreted. The comparison changes both
the number of samples and the selection rule; it does not isolate their effects.

The completed multi-hop family also shows why sample count and output quality
need separate reporting:
best-of-4 recovers 15/31 items, best-of-32 14/31, pooled-16 17/31, and pooled-32
14/31. Pooled-32 recovers more individual cells than pooled-16, 56/341 versus
54/341, illustrating the difference between item coverage and repeated recovery
within items. These are development findings from one family; there is no
four-family winner yet. See the
[larger comparison](experiments/019-full-dev-method-comparison.md).

## What each approach taught us

| Approach | Completed evidence | Current interpretation |
|---|---|---|
| Sample selection | Shared N1–32 pilot; larger development comparison in progress | Better fit is reliable; useful recovery varies across tasks and sample counts. |
| Consensus | Exact and semantic whole-bullet pilots, repaired helper and reasoning-enabled follow-up | Strict agreement removes useful coverage; audited semantic grouping still makes unsafe merges. Atomic-claim consensus remains unresolved. |
| Pruning | Single-response and pooled/contrastive-parent deletion, with matched-count random controls | Deleting low-contribution text can preserve some recovery, but also deletes required concepts. Reconstruction contribution is not a truth score. |
| Pooling | Greedy selection with joint refitting and local swaps at N16/32 | Complementary bullets improve bridge mention recovery in the pilot; selected sets can retain incompatible relationships. |
| Contrastive checks | Matched-control selection, controlled near misses, and activation-conditioned likelihood | Specificity plus pruning warrants follow-up. Fine semantic discrimination varies with layer and wording; likelihood selection has no broad pilot advantage. |
| Editing | Two bounded proposal rounds, rescoring, judging, and all eight selected-edit audits | Mostly formatting changes, no aggregate recovery gain, and two source-preservation violations. Broad expansion is not justified. |
| Independent checks | Compatible J++ development token diagnostics | Token agreement cannot validate a directed relation; no selection improvement is established. Unresolved fitting-data overlap excludes J++ from clean held-out claims. No second compatible reconstructor is established. |

Whole-bullet consensus is a restricted version of the original claim-level idea.
An exact-source-span revision stopped after eight audited cells because accepted
claims still contained unresolved references. Its planned 32-cell expansion and
quality evaluation were not completed. This is a failed input-contract check,
not evidence that all claim-level consensus fails. The optional layer-42 NLA
study has not been run. Candidate-consistency checks use the consensus helper
and are not an independent activation reader. Those limits remain explicit in
[the claim-span record](experiments/024-exact-source-span-consensus.md) and
[method scope](METHODS.md).

Combining methods is evaluated as a sequence of additions and removals. Pruning
combinations retain their unchanged parent and a control that deletes the same
number of bullets at random. Support and specificity pooling retain their
component-off and objective controls, with an additional abstention diagnostic
for specificity. We tested pooling with pruning,
matched-control selection with pruning, editing with pruning, repeat-support
pooling, and pooling with specificity. The
[component comparisons](experiments/011-cached-combinations.md) explain which
effects survive removal of each component. Random deletion matches bullet count,
so remaining token-length differences still require reporting.

## Failure modes that aggregate scores can hide

**A recovered concept can sit inside a wrong explanation.** In inspected
multi-hop outputs, selection recovers “Simula 67” while retaining conflicting
collaborator names. Other outputs preserve “Humbaba” but lose the required
“Enkidu” bridge and add incorrect relationships. Pooling does not make the
surrounding explanation correct merely by collecting more matching concepts.

**Shorter text can change the judge without removing the disputed phrase.**
In a pruning comparison, a retained “packing list” phrase receives a different
verdict after neighboring text is deleted. Inspected role improvements still
contain competing names or roles. Those cases require distinguishing genuine
disambiguation from judgment instability. Primary verdicts are preserved;
example audits do not silently replace them.

**An apparently low error rate can reflect irrelevance.** The matched-donor
control substitutes a frozen donor's capped single-sample readout, matched on
layer and task/site type and drawn from a different related-item group. It reuses
saved readouts and does not guarantee that their content has no semantic overlap.
Contradicted specific outputs fall from
543/1,137 to 25/992, but 956/1,145 donor outputs are off-topic and only 11 are
consistent, versus 446 for the target activations. This control makes coverage
essential to interpreting the error endpoint. It is described in
[activation-dependence controls](experiments/014-matched-donor-readouts.md).

**The scorer has limited resolution for some important details.** Controlled
number and role reversals often favor the same wording under both activations.
Among four numerical pairs, both correct descriptions win in 0/4 pairs at layer
20, 0/4 at layer 44, and 2/4 at layer 60. These are small, correlated diagnostic
sets; they do not show that every target state encodes the known answer or that
the reconstructor always ignores numbers. They caution against interpreting a
small score margin as factual verification. See
[near-miss diagnostics](experiments/004-contrastive-diagnostic.md).

## Cost and practical use

The cost of a method on a new activation includes its sampled responses, phrase
encodings, local selection, and recurring helper calls. Benchmark judging is
reported separately. Reusing the research cache makes another comparison cheap;
it does not remove generation cost from deployment.

The full development collection measured about 4.33 occupied H200 seconds per
N32 cell in filled batches. Its phrase encoding workload implies about 1.25
additional GPU seconds per cell at the measured throughput. These component
averages include batching and deduplication effects; they are not single-input
latency guarantees. Activation capture and setup also cost time, and a reliable
capture timing was not retained. GPU dollar pricing is unavailable.

Cached selector timings help compare local overhead: median cached selector
wall time per cell was .0112 seconds for best-of-32, .0123 for that parent plus pruning, .0591 for
matched-control selection, and .2323 for pooled selection. These measurements
use four threads and exclude input/cache preparation. They must be combined with
generation and encoding work when comparing complete methods.

Runtime semantic helpers also have recurring costs. The repaired N16
whole-bullet consensus helper with reasoning disabled cost about $0.00101 per
pilot cell. Medium-reasoning confirmation, including the necessary proposal
phase, cost about $0.00196.
Two editing rounds cost about $0.000282 per cell in helper calls, plus their
parent method and new phrase encodings. All figures are usage-based estimates,
not reconciled invoice charges. Full component sources and caveats are in
[measured costs](experiments/013-measured-costs.md); current campaign totals and
uncertain-charge holds are in [STATUS.md](STATUS.md).

## Validation, test and release status

The validation candidate pool was generated without inspecting its text,
scores, selected outputs or judgments. A prospective twelve-arm shortlist
preserves both sampling budgets, pooling, matched-control selection and the
specificity/pruning component comparisons. Its evidence and selection procedure
are recorded in [the validation freeze](experiments/027-validation-shortlist-freeze.md).
Some development judging was unfinished at that decision; later development
results cannot alter this menu or its thresholds after validation opens.
Test analysis remains closed until the final methods, comparisons and decision
rule are frozen. Held-out results will be added after those stages complete.

The implementation provides a vector-first Python API and command-line tool,
immutable candidate pools, cached phrase encodings and replayable selectors.
An installed wheel replayed an existing development pool with identical selected
text and phrase IDs, using existing third-party dependencies. A separate
synthetic-input check then completed adapter-disabled capture, N2 generation,
eight new phrase encodings and an identical cache-only replay in 156 seconds
on one H200. This validates the installed execution path in the existing
environment; semantic quality and a complete dependency installation on another
machine remain unvalidated. Installation and artifact requirements are in
[README.md](../README.md). Code and documentation are committed locally in
milestones; nothing has been pushed by this project run.
