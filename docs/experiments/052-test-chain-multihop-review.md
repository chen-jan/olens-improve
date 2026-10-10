# Final TEST review: multi-hop names and chain intermediates

Status: independent review complete; coordinator approval pending. All twelve
methods and four-family completion checks passed in the immutable TEST report.
This review covers multi-hop and chains only; it changes no verdict, setting or
method choice.

Source: `durable/runs/test-full-grid-comparison-v2/final-analysis-v2.json`, SHA
`75dee255d88104450fa4424610178baa4df24964394be77812fa218379cfcef8`.
The [review record](../../configs/test_chain_multihop_review_v1.json) contains
all exact trace references, source hashes, copied metrics/paired intervals and
manual assessments. The fixed allocation follows
[FINAL_SCIENTIFIC_REVIEW_HANDOFF](../FINAL_SCIENTIFIC_REVIEW_HANDOFF.md).

## Findings from the original question criteria

Multi-hop has **49 questions in 48 related groups**, with 539 activation readouts.
A question passes when every required bridge matches within one layer across its
frozen positions. The final target is optional in these tasks: a target-only
mention cannot substitute for a required bridge. Control comparison recovers
19/49 questions versus 15/49 for raw/capped N1 and 18/49 for best-of-32. Its paired
change versus capped N1 is **+8.16 percentage points [0.00, 18.37]** and versus
best-of-32 **+2.04 [0.00, 6.25]**. These grouped 95% intervals touch zero; the
observed gains are modest endpoint evidence, not proof of a generally more
faithful explanation.

Chains have **70 questions in 28 related groups**, with 770 activation readouts.
A question passes when the judge's top-named verified integer is an actual
intermediate at any layer of the frozen grid. Correct final answers alone do not
meet this criterion. Raw/capped N1, best-of-32 and control comparison each recover
34/70 questions; best-of-16 recovers 36/70. Best-of-16 versus capped N1 is
**+2.86 points [−10.45, 16.67]**. Best-of-32 versus best-of-16 is
**−2.86 [−12.33, 6.76]**. Control comparison versus best-of-32 is
**0.00 [−9.23, 8.96]**. These comparisons do not establish a chain recovery gain.
Equal aggregate counts can still hide different recovered questions.

| Method | Multi-hop questions | Chain questions |
| --- | ---: | ---: |
| Raw released N1 | 15/49 | 34/70 |
| Four-bullet capped N1 | 15/49 | 34/70 |
| Best of 16 | 18/49 | 36/70 |
| Best of 32 | 18/49 | 34/70 |
| Random N32 | 17/49 | 29/70 |
| Control comparison N32 | 19/49 | 34/70 |
| Pooling N16 | 18/49 | 34/70 |
| Pooling N32 | 18/49 | 33/70 |
| Control comparison then prune .005 | 14/49 | 33/70 |
| Its matched random deletion | 14/49 | 25/70 |
| Best-of-32 then prune .005 | 13/49 | 36/70 |
| Its matched random deletion | 16/49 | 38/70 |

Pruning loses required multi-hop bridges. Control comparison falls from 19 to
14/49 and best-of-32 from 18 to 13/49; each parent-to-prune paired change is
**−10.20 points [−20.00, −2.08]**. Random deletion also loses bridges. Control
comparison plus pruning and its random control both score 14/49, with paired
change **0.00 [−6.12, 6.12]**. Thus the final multi-hop evidence does not support
pruning as an improvement.

In chains, control comparison plus pruning beats its matched deletion control:
33/70 versus 25/70, **+11.43 points [1.45, 22.73]**. It still falls from its own
parent's 34/70, **−1.43 [−10.26, 7.69]**. Best-of-32 pruning is 36/70 versus its
random deletion's 38/70, **−2.86 [−11.94, 5.56]**. Beating a damaged shortening
control does not establish improvement over the complete parent.

## Fixed trace review

Every unique reported contrast was retained: **37 contrasts**, both families,
example index zero from every nonempty win, regression and unchanged category.
That is **212 reviewed references**: 111 chain and 101 multi-hop, resolving to
143 distinct exact cell/text pairs. Six multi-hop win categories and four
regression categories contain no examples; they are recorded as none observed.
Repeated identical evidence was reviewed once and linked to every required
reference. These cell-change examples are illustrative, not independent
question-level effects or estimates of failure prevalence.

The exact source pointer format below is
`paired_traces[index].families.<family>.examples.<category>[0]`.

- **Correct number inside incorrect reasoning:** trace2, chain win,
  `chain-d2p-0227`, L56 p62. Best-of-16 prioritizes16 and is credited, but calls it
  an answer and says “Starting with 14, we doubled it to get 28.” The true chain
  is8→16→14. The number is recovered; the explanation is not correct.
- **A genuine local explanation improvement:** trace22, chain win,
  `chain-d2p-0227`, L48 p62. The pruned output states “double the input number 8
  to get 16, then subtract 2 to get 14”. This matches the reference and removes
  conflicting alternatives. It is evidence for a useful individual change,
  without establishing an aggregate chain improvement.
- **Decimal extraction disagreement:** trace23 and trace32, chain wins,
  `chain-d2p-0227`, L32 p62. The surviving text says “16.50**”; the retained judge
  returns integer16 and quotes that decimal, and the official score credits the
  intermediate16. The verbatim-quote verification accepts it. **16.50 is not16**;
  the official verdict is preserved, but its numeric interpretation is disputed.
- **Ranking and off-topic sensitivity:** trace33, chain win,
  `chain-d2p-0206`, L56 p67, credits15 in “Half of 29 (accounting for recovery”.
  The reference is30→15→12. Trace12's chain regression at `chain-d2p-0200`, L28
  p66, still contains “The answer is 6” but prioritizes2/8/5. A correct mention
  need not be the judge's top computed value or a grounded step.
- **Partial multi-hop improvement with wrong alternatives:** trace12, multi-hop
  win, `mhh-1976philadelphia-bacterium`, L44 p28. Control comparison adds the
  complete Legionnaires' disease bridge and a correct Legionella–disease relation,
  but retains the competing Clostridium genus and Buffalo outbreak statement.
  The required-name gain is real; not every statement becomes correct.
- **Bridge removal despite answer retention:** trace23 and trace32, multi-hop
  regressions, `mhh-1973-triple-crown-stud-farm`, L56 p33. Pruning removes the
  Secretariat name while Claiborne Farm remains. The required horse bridge is
  lost; a farm-only answer is insufficient under the original criterion.
- **Correct bridge with wrong commander:** trace28, multi-hop win,
  `mhh-adwa-baratieri`, L44 p33. The text adds “Battle of Adwa” but calls the
  commander “Obboli”. Correct bridge recovery does not verify the historical
  answer.
- **Unchanged failures:** trace12, multi-hop unchanged,
  `mhh-prowse-clockwork`, L52 p42, mentions Kubrick films without David Prowse.
  Its chain unchanged case, `chain-w2-d2p-0111`, L44 p66, uses incompatible
  starts/arithmetic without the required intermediate24. “Unchanged” means the
  official pass flag, not identical text or good explanation.

## Interpretation and limits

Report the task-specific endpoints with their uncertainty. The selected profiles
remain legitimate fixed comparisons, but these two families support no global
winner and no inference that a recovered bridge/number establishes valid
reasoning or activation truth. Pooling gains and losses coexist; pruning can
remove useful evidence. Preserve the decimal mismatch and the genuinely correct
local calculation alongside the broader failure modes.

All intervals above are copied from 2,000 related-group bootstrap draws. These
37 contrasts are not multiplicity-adjusted confirmatory tests. Correct names,
optional answers, judge-ranked values, explanation quality and question-level
success are different quantities. The complete 469-item union is a separately
required **descriptive** analysis, not additional held-out evidence. No API calls,
new generation, replacement verdicts or TEST-informed tuning occurred in this
review.
