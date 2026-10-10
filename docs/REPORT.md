# Improving Oracle Lens with inference-time computation

Working research report, 2026-10-10. **Validation and development sampling curves are complete; final TEST judging is running.**
The findings below distinguish development from the fixed validation comparison;
no final method recommendation has been validated on TEST. Live operational status is in
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
It retains more recovery than random deletion on the pilot. However, the larger
development chain task shows a substantial loss: the combined method recovers
16/330 cells, versus 27/330 for its unpruned parent and 23/330 for matched random
deletion. Its apparent pilot gains include judge-sensitive cases with remaining
contradictions. Completed validation likewise does not support promoting pruning
over matched-count random deletion. Whole-bullet consensus and free editing
have not justified broad expansion on the evidence collected so far.

## What changed in the actual explanations

Three reviewers, with rotating independent checks, compared the same eight
development examples across all method sections. The examples were fixed without
looking at outcomes, with two per task. Separate rare-change examples are clearly
labeled as selected afterward. They illustrate behavior, rather than estimating
how frequently it occurs; unchanged outputs and missing diagnostics stay visible.

Sampling and pooling sometimes recover the required phrase “Simula 67” while
still inventing its collaborators. Repetition-based filtering can keep generic
claims but discard that useful phrase or a needed intermediate number. Pruning
can remove an incorrect chemical identity, yet leave no useful chemical fact;
other apparent improvements retain the very statement previously flagged by the
judge. These cases separate recovering a mention, removing information and
correcting an explanation.

Editing changes none of the eight shared outputs; its separately inspected rare
changes include cleanup and added completions, without an established recovery
gain. The independent token reader cannot distinguish a correct number from a
longer number containing the same digit, or reversed relations with the same
words. Contradictory reviewer and judge interpretations remain side by side.
The dashboard's expandable method sections provide exact before/after text,
source context, variant choices and retained judge evidence. The full review and
coverage limits are recorded in [the qualitative inventory](QUALITATIVE_COVERAGE.md).

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

A cell is one prompt at one model layer and token position. N is the number of
candidate responses available to a method. Each cell has one shared pool of at
most 32 sampled responses. Best-of-N uses
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

For .005 pruning, remove a complete bullet only when refitting the remaining
bullets lowers FVE by at most 0.005, then repeat. This is an absolute loss of
0.5 percentage points per deletion, not a relative percentage or a truth test.

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
| Validation | 80 | 3,485 | Twelve frozen comparisons; complete |
| Test | 268 | 10,714 | Twelve comparisons frozen; judging running |

The pilot is a subset of development. Cells from the same prompt are correlated.
Paired uncertainty intervals resample related item groups, not individual cells.
The pilot has only 2–8 independent groups per family; full development has seven
chain-template groups. A large number of cells does not erase those limitations.

| Family | Development groups | Validation groups | Test groups |
|---|---:|---:|---:|
| Transcript contradictions | 30 | 20 | 99 |
| Hidden bridge concepts | 29 | 17 | 48 |
| Arithmetic intermediates | 7 | 7 | 28 |
| Directed roles | 15 | 10 | 25 |

These counts come from the frozen group manifests, independent of model
outcomes. Validation helps choose among the fixed candidates; its smaller
group counts limit precision. The larger untouched test supplies the final
comparison. Useful effects can merit follow-up despite wide intervals.
These intervals resample benchmark groups; they do not separately model the
additional variability from rerunning the generator or judge.

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

| Method | Contradicted / specific | Bridge mentions / 24 | Intermediate-number matches / 21 | Role task passes / 72 |
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

All six best-of-N prefixes, N=1/2/4/8/16/32, are complete on the same 5,236
development cells, with separate raw and capped single-sample references. Other
method comparisons have the coverage recorded individually below. Intervals
resample related groups in pairs; these exploratory comparisons are not adjusted
for the other methods examined during development. The late completed curves
cannot change the already frozen TEST choices.

| Endpoint | Capped single sample | Best-of-32 | Change in percentage points [95% interval] |
|---|---:|---:|---:|
| Contradicted / specific readouts | 543/1,137 | 523/1,140 | −1.88 [−5.41, +1.76] |
| Bridge mentions / 341 cells | 29 | 43 | +4.11 [+1.82, +6.61] |
| Intermediate-number matches / 330 cells | 26 | 30 | +1.21 [−3.16, +4.85] |
| Role task passes / 3,420 cells | 151 | 182 | +0.91 [+0.15, +1.73] |

The original item-level aggregation gives 11→14/31 bridge items, 15→19/30 chain
items, and 23→23/30 role items. Thus more role cells pass without recovering an
additional item. The chain comparison contains only seven independent template
groups. The hallucination difference remains uncertain: fewer readouts are
flagged wrong, but the total flagged false spans rises from 1,305 to 1,324.
Span counts and supported-claim counts use different segmentation and cannot
be combined into a claim-precision estimate. Off-topic outputs decrease from
148 to 134. Both the favorable changes and these limits matter.

The complete sampling curve is nonmonotonic in quality. Best-of-16 recovers
48 bridge cells and 185 role cells, versus 43 and 182 at best-of-32; it recovers
only 19 arithmetic-intermediate cells versus 30 at best-of-32. These are observed
counts, not evidence of a universally optimal sample budget. The hallucination
changes at both N16 and N32 have intervals spanning zero. The N1 reconstruction
selector is distinct from the released baseline: score eligibility yields one
empty hallucination output and eleven empty role outputs. Full per-prefix
counts, cell/item intervals, paired changes, lengths and limitations are in
[the completed development scaling record](experiments/034-development-scaling-completion.md).

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

Pruning and pooling also show a material chain-recovery regression in the
evidence available before validation. With the .005 sequential-deletion
threshold, matched-control selection falls from 27 to 16 recovered cells out of
330, versus 23 for matched-count random deletion. Best-of-32 followed by pruning
falls from 30 to 16, versus 28 for its random-deletion control. Pooled N16 and N32
each recover 18 cells. Item recovery likewise falls: 17→12/30 for matched-control
selection with pruning and 19→12/30 for best-of-32 with pruning. These are seven
related template groups, and mention recovery still does not certify the
calculation. Nevertheless, the observed loss is substantial and should not be
described as a small tradeoff without compensating evidence. The exact records
are preserved in the [validation decision snapshot](experiments/027-validation-shortlist-freeze.md).

## Completed validation comparison

The twelve settings frozen before validation outcome inspection are complete on
80 items and all 3,485 intended cells. There is **no global faithfulness winner**.
The prospective final comparison retains best reconstruction from 16 samples and
matched-control selection from 32 as two experimental operating points, alongside
released/capped N1, best-of-32 and random selection controls. This choice does not
make validation a fresh confirmation of a method selected from these results;
the separately frozen TEST comparison will supply that measurement.

| Method | Contradicted / specific | Bridge mentions / 220 | Intermediate-number matches / 220 | Role task passes / 2,280 |
|---|---:|---:|---:|---:|
| Released single sample | 312/760 | 26 | 16 | 85 |
| Capped single sample | 313/761 | 26 | 15 | 85 |
| Best reconstruction, N16 | 307/762 | 31 | 17 | 97 |
| Best reconstruction, N32 | 299/762 | 29 | 12 | 96 |
| Random eligible sample, N32 pool | 317/762 | 24 | 17 | 95 |
| Pooled bullets, N16 | 307/759 | 30 | 10 | 102 |
| Pooled bullets, N32 | 305/760 | 29 | 10 | 98 |
| Matched-control selection, N32 | 295/763 | 30 | 16 | 95 |
| Matched-control selection + .005 pruning | 271/759 | 20 | 10 | 97 |
| Same parent + matched random deletion | 262/756 | 20 | 15 | 96 |
| Best reconstruction N32 + .005 pruning | 277/759 | 20 | 9 | 94 |
| Same best-N32 parent + matched random deletion | 267/752 | 18 | 17 | 83 |

Each recovery family has 20 items. With the original any-site item aggregation,
best-of-16 recovers 9 bridge, 11 chain and 17 role items; matched-control selection
from 32 recovers 8, 10 and 17. Best-of-32 recovers 8, 8 and 16. Those summaries
answer a different question from how often individual cells recover information.
For example, pooled-16 yields 18 passing role items but only 6 chain items,
compared with 17 and 11 for best-of-16. More samples and larger reconstruction
scores do not uniformly improve these task endpoints.

Relative to best-of-32, matched-control selection changes the contradiction rate
from 39.24% to 38.66%: a paired change of −0.58 percentage points, with a grouped
95% interval of [−1.46, +0.23]. Bridge recovery is unchanged at 8/20 items;
chain changes 8→10/20, paired +10 percentage points [0, +22.22]; role changes
16→17/20, +5 points [0, +15]. The cell-level role count instead changes 96→95.
The intervals use 20 hallucination, 17 bridge, 7 chain and 10 role groups, and
cannot remove generator/judge variability or certify every statement. These
are reported effects and uncertainties, not a significance gate or a hidden
average across families.

Matched-control selection also increases off-topic outputs from 60/762 to
68/763 specific readouts. Its six wrong→off-topic transitions and four
wrong→consistent transitions coexist with five consistent→wrong transitions.
For `chat-dailydialog-0010` at layer 60, position 24, it removes unsupported
library/online-banking detail and better matches the original bank response.
For `chat-dailydialog-0001` at layer 20, position 78, the unsupported identity
is instead replaced with off-topic capabilities and ChatGPT discussion. Thus
fewer contradiction flags do not always mean more useful transcript recovery.

Pruning is not promoted to the final operating points. Its apparent error
reduction is not separated convincingly from shortening: matched-control
selection followed by .005 pruning has 271/759 contradicted outputs, while
matched-count random deletion has 262/756. Both retain an average of 2.27
bullets in the hallucination family, versus 4.00 for the unpruned parent;
mean token counts are 60.90, 58.76 and 102.75 respectively. Random deletion
matches bullet count, not exact token length. Pruning versus that control
changes bridge recovery 20→20 cells, chain 15→10 and role 96→97. At item level,
chain is 10→6/20 and role 15→14/20. The bounded evidence does not justify
attributing the lower contradiction rate to reconstruction-guided deletion
rather than reduced content.

The fixed trace audit preserves official judgments while qualifying their
meaning. `mhh-aztec-coatepec-sister`, layer 32, position 34, gains the required
Huitzilopochtli bridge but retains incompatible god alternatives. In
`chain-d2p-0231`, layer 32, position 68, the intermediate 2 becomes prominent
amid wrong starting values and operations. Conversely, the scored regression
`chain-d2p-0396`, layer 40, position 61, includes the correct final computation
12×2×2=48 while losing the intermediate-focused hit. Number recovery is not
calculation accuracy.

Role options permit people to be identified by description. At
`oa-burglar-neighbor-spy-ab`, layer 36, position 164, both responses describe a
burglar observing a neighbor, but descriptive identities are accepted only for
the selected response. Some pooling gains also depend on inferred composition:
`oa-babysitter-toddler-feed-ab`, layer 52, position 104, is judged as Maya feeding
a toddler by combining Maya settling a toddler with Maddie feeding a younger
sister in a different bullet. These cases illustrate judge sensitivity and
remaining ambiguity; they do not warrant changing the retained verdicts.

All values, grouped intervals and fixed sampled traces are supplied by the
immutable [signed validation analysis](${OLENS_DATA_ROOT}/runs/validation-full-grid-v1/signed-menu-analysis-v1.json),
SHA-256 `db223a374f51d9122f8cc430a347e4f82dea75ce3d449008e1def1f7cf89e918`.
The [family comparison figure](../dashboard/figures/validation-v1/family-cell-rates.png)
and [zoomed cross-task plot](../dashboard/figures/validation-v2/cross-task-error-recovery-zoom.png)
use those same values, with distinct family denominators and supplied marginal
intervals. The [full-range plot](../dashboard/figures/validation-v1/cross-task-error-recovery.png)
is preserved; zoomed axes change neither values nor intervals. The dashboard
uses the same reviewed source, with no inferred cross-task winner. No TEST
outcomes are included here.

## What each approach taught us

| Approach | Completed evidence | Current interpretation |
|---|---|---|
| Sample selection | Shared N1–32 pilot and complete six-prefix development comparison | Better fit is reliable; useful recovery varies across tasks and sample counts. |
| Consensus | Exact and semantic whole-bullet pilots, repaired helper and reasoning-enabled follow-up | Strict agreement removes useful coverage; audited semantic grouping still makes unsafe merges. Atomic-claim consensus remains unresolved. |
| Pruning | Single-response and pooled/contrastive-parent deletion, with matched-count random controls | Deleting low-contribution text can preserve some recovery, but also deletes required concepts. Reconstruction contribution is not a truth score. |
| Pooling | Greedy selection with joint refitting and local swaps at N16/32 | Complementary bullets improve bridge mention recovery in the pilot; selected sets can retain incompatible relationships. |
| Contrastive checks | Matched-control selection, controlled near misses, and activation-conditioned likelihood | Unpruned matched-control selection is a final experimental candidate. Validation does not establish pruning over random shortening. Fine semantic discrimination varies with layer and wording; likelihood selection has no broad pilot advantage. |
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

We also tested the three-part combination of pooling, specificity and pruning.
On the same pilot it recovered six bridge cells, zero chain cells and twelve
role cells, with 39/71 contradicted specific readouts. The simpler specificity
selection plus pruning recovered seven, one and twelve, with 36/72 contradicted
readouts. These small development comparisons do not establish a population
ranking, but they provide no reason to expand the more complicated combination
before the final comparison. The [three-part experiment](experiments/020-pooled-specificity.md)
includes component controls, matched random deletion and inspected regressions.
The limit of two proposed final operating points does not mean only two
combinations were explored.

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

A resource snapshot at 16:49 UTC records $18.13 in project API usage estimates, plus $4.90 reserved for outstanding or uncertain requests ($23.03 committed). The 16:43 storage inventory is 93.73 GB of project files, excluding 55.56 GB of reused base weights. GPU allocation during the project totals 64.77 H200-hours including idle time; major model work is estimated at 30.17 GPU task-hours, rather than measured GPU utilization. These snapshots exclude GPU dollar charges and Codex/subagent billing. Source receipt: `resource-usage-1649-v1/receipt.json`, SHA256 `f9b69d2b7ec2d0500e1e809d979c56461653e3640a56e1e34b5f9366710c558a`. These are interim totals; judging continues.

The cost of a method on a new activation includes its sampled responses, phrase
encodings, local selection, and recurring helper calls. Benchmark judging is
reported separately. Reusing the research cache makes another comparison cheap;
it does not remove generation cost from deployment.

The random-selection control retains one eligible response from the recorded
N32 pool. A deployment implementation need not generate 32 unused responses,
but matching this control's parser and output-budget eligibility may require
resampling. Therefore one retained sample is not a guaranteed one-draw cost.
The experimental pool cost and that deployment distinction are reported separately.

The full development collection measured about 4.33 H200 task wall-seconds per
N32 cell, amortized over filled batches. Its phrase encoding workload implies
about 1.25 additional GPU task wall-seconds per cell at the measured throughput. These component
averages include batching and deduplication effects; they are not single-input
latency guarantees. GPU dollar pricing is unavailable.

A separate installed-tool check measured one new synthetic input on an H200.
With Oracle Lens already loaded, capturing its activation took 0.30 seconds
and generating 32 descriptions took 12.04 seconds. Starting with no model
loaded in the process, the pipeline through the first selected description
took 59.59 seconds. This includes loading both models sequentially, encoding
128 phrase vectors, preparing the scoring transform and choosing a response.
The phrase encoding itself took 1.34 seconds. These components overlap with
the pipeline total and must not be added twice. This is one input using
existing filesystem caches, not a latency distribution or a measurement of
fresh 16-sample generation. See [new-input timing](experiments/035-new-input-timing.md).

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
scores, selected outputs or judgments. The frozen twelve-arm shortlist
preserves both sampling budgets, pooling, matched-control selection and the
specificity/pruning component comparisons. Its evidence and selection procedure
are recorded in [the validation freeze](experiments/027-validation-shortlist-freeze.md).
Some development judging was unfinished at that decision; later development
results cannot alter this menu or its thresholds after validation opens.
Validation reconstruction, selection, judging and the signed twelve-condition
analysis are complete; see
[the validation comparison](experiments/029-validation-comparison.md).
The original six-method final comparison was frozen after two independent
reviews and coordinator approval. Following the user's concern about noisy
shortlisting, a prospective amendment adds the other six already frozen
validation variants as secondary comparisons. This was recorded before any
TEST judgments or quality inspection. The original six primary comparisons,
settings and two validation-selected operating points remain unchanged.
Small validation samples do not establish that excluded variants are inferior.
All 342,848 TEST samples passed source and cell identity checks; reconstruction
and selection are complete for all 10,714 sites. All four final evaluators
launched at 14:58–14:59 UTC; no TEST quality results have been inspected yet. See the [original freeze](experiments/032-test-final-method-freeze.md)
and [expanded comparison](experiments/038-expanded-heldout-comparison.md).
Consensus and editing remain pilot evidence, and independent-reader checks
remain diagnostics; the twelve-method comparison is not an exhaustive test of
all seven approach categories.

The implementation provides a vector-first Python API and command-line tool,
immutable candidate pools, cached phrase encodings and replayable selectors.
An installed wheel replayed an existing development pool with identical selected
text and phrase IDs, using existing third-party dependencies. A separate
synthetic-input check then completed adapter-disabled capture, N2 generation,
eight new phrase encodings and an identical cache-only replay in 156 seconds
on one H200. This validates the installed execution path in the existing
environment; semantic quality and a complete dependency installation on another
machine remain unvalidated. The later N32 check above measured a separate
new-input run. The cache-saving release also passed an installed-wheel check:
after eight vectors were saved and their cache directory moved, replay returned
exactly the same text, source phrases and reconstruction score without loading
the reconstructor. See [cache persistence](experiments/036-portable-cache-persistence.md).
Installation and artifact requirements are in
[README.md](../README.md). Code and documentation are committed locally in
milestones; the research GitHub repository has not been pushed. The separately
hosted [public dashboard](https://olens-improve-research.jan618.chatgpt.site)
contains a reviewed snapshot with clear task charts and expandable detail.
