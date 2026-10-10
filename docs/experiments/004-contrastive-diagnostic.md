# 004: Does the matched scorer distinguish number and relation changes?

Status: initial and expanded development-only E2 diagnostics completed. E1 and E3 selection pilots and their blind judging also completed; see [006](006-selector-pilot.md), [009](009-pilot-grouped-comparisons.md) and [007](007-likelihood-pilot.md). This E2 diagnostic used no new O-lens samples or paid API calls. It is a small instrument diagnostic, not a benchmark improvement result.

## Fixed comparison

Use four existing layer-44 final-position development cells from the frozen eight-cell instrument, with their exact fresh adapter-free activations. Number pair: `chain-d2p-0271` (halve 22, round up → 11) versus `chain-d2p-0298` (halve 24, round up → 12). Role pair: `oa-comedian-heckler-humiliate-ab` versus its paired `-ba` reversal. Labels enter this isolated diagnostic only; no selector/editor receives them.

For each pair, encode two descriptions through the frozen `ar_ptag_pooled` reconstructor, then fit each individually to both target activations using the exact matched pooled layer-44 moments, ridge .1. Report both exact SciPy NNLS and the released80 compatibility solver. All controlled descriptions fit inside the 32-token AR span.

Number descriptions: “After halving and rounding up, the intermediate value is 11.” and the same text with 12. Generic: “An intermediate value is computed by halving a number and rounding up.”

Role descriptions: “The performer humiliates the heckler.” and “The heckler humiliates the performer.” Generic: “A performer and a heckler are involved in a humiliating encounter.” Proper names are omitted because the paired stories do not contain exactly the same named entities.

Rows in each score matrix are the two activations; columns are the two corresponding descriptions. Require both diagonal descriptions to beat their crossed description. Record the interaction `(s00+s11)-(s01+s10)` and the separate margins: a positive aggregate interaction cannot conceal a failed pairing. Generic descriptions test whether omission receives a stronger reconstruction score.

## Observed exact-fit scores

| Diagnostic | First activation / first description | First / second | Second / first | Second / second | Both own descriptions win? |
|---|---:|---:|---:|---:|---|
| Intermediate number | .015960 | .016821 | .015259 | .016231 | No |
| Role direction | .011490 | .010167 | .008717 | .010103 | Yes |

Number self-minus-cross margins: **−.000861, +.000972**; interaction +.000111. Role margins: **+.001324, +.001386**; interaction +.002710. Released80 gives the same signs and effectively the same single-phrase scores.

The role generic scores are **.118105 and .128038**, substantially above the correctly directed descriptions (.011490 and .010103). Number generic scores are .013861 and .012884, below the corresponding specific descriptions. Generic descriptions differ in wording/length as well as specificity, so their scores diagnose an optimization incentive, not an isolated causal effect of deleting one word.

At these states, the scorer does not reliably separate the known numerical intermediates, while it detects the role reversal weakly. A final-token chain state need not emphasize its intermediate value; this failure alone cannot establish that the AR universally ignores numbers. Generic role content scoring much higher shows why selecting solely by reconstruction can favor nonspecific coverage. Neither outcome certifies semantic truth, and two pairs do not establish broad preservation or failure.

## Implementation, artifacts, and next decision

`src/olens_improve/contrastive.py` provides original-minus-near-miss margins and own-minus-frozen-control specificity, with finite-score guards. E1 callers must enforce the plan's development-bank/site/group exclusions; no E1 control bank was tested in this initial diagnostic. Its E3 teacher-forced likelihood utility implements the exact carrier/injection, causal alignment from the carrier's last logit to the first candidate token, full candidate scoring up to 256 tokens, and no EOS by default. E3 runtime validation and the 189-cell pilot subsequently completed; see [007-likelihood-pilot.md](007-likelihood-pilot.md).

`scripts/contrastive_diagnostic.py` reproduces this isolated E2 experiment. Full phrase strings, token IDs, source cell IDs, per-solver matrices/coefficients, generic scores, matched whitener hash, and runtime are in `${OLENS_COMPUTE_ROOT}/logs/contrastive_diagnostic.json`. The frozen model/source pins and loader evidence are in [001-model-setup.md](001-model-setup.md).

Next, extend diagnostic coverage to representative development cells and other supported existing layers, without choosing favorable layers from test results. Prioritize the reusable AR encoding pipeline and A–D development comparisons. Treat contrastive margins as candidate signals requiring observed downstream quality, not truth labels. Record failed or uncertain distinctions before calibrating deployment thresholds; no calibration or test selection has occurred in this experiment.

## Planned expanded diagnostic before using near-miss margins

The two initial pairs are insufficient to decide whether E2 belongs in a final selector. Freeze roughly 20–40 development-only paired comparisons before scoring, spanning exact numerical alternatives, named-entity alternatives, role reversals, and negation **only where the original benchmark evidence establishes it**. If core banks contain no valid negation labels, record that diagnostic as unavailable rather than inventing truths or adding new core sites.

Use existing captured cells and prespecified supported layers. Where both paired activations exist, cross both descriptions with both targets; otherwise label the narrower one-target test explicitly. Include generic omission and a second faithful wording when available, keeping controlled descriptions within the AR span. Preserve the source item IDs, evidence establishing each controlled change, relation direction, number/entity identity, wording, layer and position in an isolated diagnostic manifest. Repeated layers/wordings of one pair remain correlated observations, not additional independent items.

Report each own-minus-cross margin, both-pair success, interaction, generic-versus-specific scores, exact/released80 agreement and failures by change type/layer. Inspect failed distinctions as well as successes. Gold-backed descriptions and diagnostic findings never enter per-item candidate construction, matching, editing, control selection or inference-time policy inputs. Any useful E2 signal still needs a candidate-only development comparison against same-pool best-of-N; diagnostic fit discrimination alone does not establish better readouts. The expanded diagnostic completed as recorded below.


## Expanded diagnostic completed

The frozen evidence-backed manifest and results are at `${OLENS_DATA_ROOT}/diagnostics/e2-expanded-v1`. Four number pairs and four role pairs were tested at existing layers 20, 44 and 60; abstract-role and named-entity wording variants give 36 correlated comparison sets. The original benchmark evidence establishes the controlled labels, not that a particular activation encodes them. No balanced verified negation pairs were identified; negation remains unavailable. The diagnostic used no new O-lens samples, helper/editor inputs or paid API calls and took 30.81 seconds.

| Change type | Both own descriptions win at layer 20 | Layer 44 | Layer 60 |
|---|---:|---:|---:|
| Number | 0/4 | 0/4 | 2/4 |
| Abstract role direction | 0/4 | 1/4 | 3/4 |
| Named-entity direction | 0/4 | 0/4 | 3/4 |

At layers 20 and 44, many cases favor one description under both activations, exposing shared wording preference rather than paired discrimination. Generic omission beats the correctly directed abstract role phrase in 6/8, 5/8 and 1/8 target conditions at layers 20/44/60; for named variants, the counts are 8/8, 8/8 and 0/8. Thus discrimination and omission incentives vary substantially with layer and wording. Layer-60 numerical margins are below .0006 in magnitude, within the scale of observed batching sensitivity; the two successful number pairings are delicate. Repeated layers, wording variants, related templates and shared items are not independent observations. These findings motivate cautious development tests of specificity/near-miss signals, not a universal semantic-faithfulness claim or test-selected layers.
