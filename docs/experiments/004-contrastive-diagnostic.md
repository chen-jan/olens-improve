# 004: Does the matched scorer distinguish number and relation changes?

Status: initial development-only E2 diagnostic completed on H200 `25330001`; E1 and E3 are not yet experimentally evaluated. No new O-lens samples or paid API calls. This is a small instrument diagnostic, not a benchmark improvement result.

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

`src/olens_improve/contrastive.py` provides original-minus-near-miss margins and own-minus-frozen-control specificity, with finite-score guards. E1 callers must enforce the plan's development-bank/site/group exclusions; no E1 control bank was tested here. Its E3 teacher-forced likelihood utility implements the exact carrier/injection, causal alignment from the carrier's last logit to the first candidate token, full candidate scoring up to 256 tokens, and no EOS by default. E3 runtime validation remains pending.

`scripts/contrastive_diagnostic.py` reproduces this isolated E2 experiment. Full phrase strings, token IDs, source cell IDs, per-solver matrices/coefficients, generic scores, matched whitener hash, and runtime are in `${OLENS_COMPUTE_ROOT}/logs/contrastive_diagnostic.json`. The frozen model/source pins and loader evidence are in [001-model-setup.md](001-model-setup.md).

Next, extend diagnostic coverage to representative development cells and other supported existing layers, without choosing favorable layers from test results. Prioritize the reusable AR encoding pipeline and A–D development comparisons. Treat contrastive margins as candidate signals requiring observed downstream quality, not truth labels. Record failed or uncertain distinctions before calibrating deployment thresholds; no calibration or test selection has occurred in this experiment.
