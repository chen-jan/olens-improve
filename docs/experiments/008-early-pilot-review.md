# 008: Early judged pilot and limits of recovery scores

Status: historical interim development review, 2026-10-10 UTC. This is an interpretation of
the shared 189-cell pilot, not a held-out result. Some pooled/pruned judgments
were still being repaired when this review began. Grouped paired uncertainty
estimates subsequently completed in [009](009-pilot-grouped-comparisons.md);
the larger full-grid comparison is tracked separately in [019](019-full-dev-method-comparison.md).

## Findings and next decisions

Selecting the highest-reconstruction complete sample improves reconstruction
steadily as the sample count increases. Quality does not follow the same
ordering. Pooling improves some multi-hop bridge matches while losing arithmetic
intermediates. Neither a recovered name nor a lower transcript-contradiction
rate establishes that the entire explanation is faithful.

Continue the complete development comparison of sampling, pruning, pooling and
matched-control selection. Preserve random selection as a comparator. Do not
promote a method solely from these small differences or from reconstruction.
Inspect supplementary factual accuracy and judge reliability before choosing
the validation shortlist. Semantic consensus needs a repaired equivalence
check: its first natural audit found false merges that ignored extra assertions.

## Scope and quantitative snapshot

Inputs, frozen checkpoints, shared samples and scoring conventions are those of
[experiment 006](006-selector-pilot.md). The immutable pilot has 31 development
items: eight hallucination items (72 cells), eight multi-hop items (24), seven
chain items (21), and eight role items (72). These are partial grids; the table
reports cell diagnostics, not official full-grid item scores.

The judge is GPT-6 Luna, effort `none`, using the pinned WorkspaceBench prompts.
The multi-hop bridge endpoint is deterministic matching. Each method submits
only one final readout per cell. `A32` selects one complete capped candidate by
joint reconstruction; `D32` composes up to four existing bullets by reconstruction.

| Condition | Transcript contradictions / specific readouts | Multi-hop recovered cells | Chain recovered cells | Role recovered cells |
|---|---:|---:|---:|---:|
| Raw N=1 | 46/71 | 4/24 | 1/21 | 8/72 |
| Capped N=1 | 46/71 | 4/24 | 0/21 | 8/72 |
| Best of 16 | 40/71 | 9/24 | 3/21 | 8/72 |
| Best of 32 | 39/71 | 7/24 | 3/21 | 9/72 |
| Random complete sample from 32 | 38/72 | 8/24 | 2/21 | 8/72 |
| Pooling from 32 | Repair pending | 10/24 | 1/21 | 8/72 |
| Best of 32, leave-one-out loss threshold .005 | 37/72 | 7/24 | 1/21 | 10/72 |
| Best of 32, mean-control specificity | 38/71 | 7/24 | 1/21 | 9/72 |

Every listed hallucination value has 72 produced and stage-two-judged readouts;
the denominator excludes generic/empty classifications. Off-topic counts are
respectively 5, 5, 7, 8, 10, pending, 7 and 7. Both the assertion share and the
off-topic fraction must accompany the contradiction rate. Random selection is
one prespecified draw, not a precisely estimated expectation over random draws.
Related cells are not independent observations. No significance claim is made.

These snapshots come from
`${OLENS_DATA_ROOT}/runs/development-shared-pilot-v2/judgments/`,
using each condition's `results.json` and `project_contract.json`. The final
report must recompute from the completed, hashed artifacts rather than copy an
interim table. The shared selection source is
`${OLENS_DATA_ROOT}/selections/pilot189-selectors-v1/selections.jsonl`.

## Is a matched candidate available but overlooked?

An additional isolated evaluation runs the pinned multi-hop matching contract
on all 32 existing capped complete candidates in each of the 24 pilot cells.
It does not select a deployable output using answers. The candidate-availability
ceiling is the number of cells containing at least one matched candidate.

| Samples available | Cells with a matched candidate | Expected matched cells under uniform selection | Best-FVE matched cells |
|---|---:|---:|---:|
| 1 | 4/24 | 4.000/24 | 4/24 |
| 2 | 7/24 | 5.500/24 | 7/24 |
| 4 | 7/24 | 6.000/24 | 7/24 |
| 8 | 9/24 | 6.625/24 | 7/24 |
| 16 | 12/24 | 6.5625/24 | 9/24 |
| 32 | 14/24 | 6.09375/24 | 7/24 |

The random expectation here is computed exactly over the finite saved pool;
it differs from the single random output used in the judged table. At N32,
seven cells contain a matching candidate that highest-FVE selection overlooks,
while ten have no matching complete candidate at all. This exposes both
selection and generation limitations under the current contract. It does not
establish factual correctness of the matched statements, and these 24 cells
are correlated within eight items.

Reproduce with `scripts/diagnose_candidate_pool.py`. The result and input/code
hashes are in
`${OLENS_DATA_ROOT}/diagnostics/multihop-candidate-availability-v1/results.json`.
All recomputed best-FVE prefix counts agree with the official pilot outputs.
No new generations, AR encodings or API calls were used.

## What the examples show

**A name match can accompany the wrong relationship.** At
`multihop_mt|mhh-borglum-son|L44|p00033`, the bank's bridge is Gutzon Borglum and
its final target is Lincoln Borglum. The pooled output includes
`/son, **Gutzon Borglum Jr.**, to complete it. Who was that son`, alongside
George Washington Carver Jr., a daughter and the Statue of Liberty. This
contains the matched bridge string but does not correctly identify the son.
Reconstruction rises to .41934. Keep the official bridge hit, and separately
record the entity/relationship errors; do not call this a faithful recovery.

**An arithmetic hit can come from an incorrect computation.** At
`chain_intermediates|chain-w2-d2p-0013|L44|p00062`, the task starts with 2,
adds 3 and then adds 9. The intermediate is 5 and the final answer is 14.
Best-of-32 emits bullet heads 12, 13, 12 and 12. Its explanations include
`3 + 2 + 1 equals 5` and `The initial number is 5. Adding 2 results in 7.
Then adding 3 results in 10.` The judge reports named numbers [5, 7, 10],
an arithmetic basis and a hit. The number 5 appears, but the described process
does not match the task. Its reconstruction is .27091. Pooling raises that to
.30312 and loses even this recovery hit. This separates mention recovery,
process correctness and reconstruction.

**Fewer contradicted claims can mean more unverifiable claims.** At
`chat-lmsys-0005__L020__p291`, N=1 attributes AI-generated personalized stories
to StoryBuddies, whereas the supplied response describes talking puppet
stories. Best-of-32 instead lists Learnly, BookSmart, StoryBuilder AI and
LexiaLab. The judge changes from one false span to no false spans, but records
nine unverifiable claims and zero true claims. This is a benchmark contradiction
improvement, not evidence that the replacement product details are supported.
No external factual claim about these products is being made here.

**Some apparent regressions need a judge audit.** At
`chat-dailydialog-0027__L020__p88`, the transcript offers a witty conversation
starter and fun topics to discuss. Luna marks the best-of-32 phrases about a
clever introduction and a thoughtful greeting as wrong, among other spans.
Some are plausible paraphrases or continuations under the frozen judge's own
instructions. Retain the official verdict, investigate repeatability separately,
and do not feed an adjudicated answer back into selection.

The last two cases were selected by a reproducible qualitative audit: classify
all shared N=1/A32 hallucination cells as wrong-to-not-wrong, the reverse, or
unchanged; sort cell keys; use Python `random.Random(20261010)` to sample two
from each category sequentially. Counts were 12 improvements, five regressions
and 55 unchanged. The other sampled improvement was
`chat-dailydialog-0027__L060__p88` (false spans 1 to 0, true claims 1 to 1,
unverifiable claims 7 to 7). The other sampled regression was
`chat-dailydialog-0047__L020__p33` (generic to one wrong span). The unchanged
samples were `chat-lmsys-0005__L044__p291` (both zero true claims, unverifiable
claims 8 to 5) and `chat-lmsys-0005__L060__p36` (both contradicted, false spans
1 to 10). Full paired texts and original verdicts remain in the source results.
Span and claim counts have different segmentation and are not interchangeable
atomic precision measures.

## Limitations and follow-up

All inspected examples are development-only. These examples diagnose failure
modes; they do not estimate their prevalence. The full development run, grouped
paired intervals, B/E3/F comparisons, and validation/test phases remain open.
Known benchmark answers were consulted only during this isolated evaluation
review and must not enter generation, editing or deployed selection.

Next: repair missing judgments; retain raw results; audit natural equivalence
pairs and judge repeatability; compare edited outputs with their exact parents;
update the dashboard with complete measurements and these qualifications.
No extra API calls or GPU jobs were launched to write this review.
