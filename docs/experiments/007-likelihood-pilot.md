# 007: Same-pool conditional-likelihood selection

Status: causal-alignment tests, the eight-cell runtime pilot, the 189-cell selection pilot and its blind semantic judging completed. This E3 experiment uses existing N8 prefixes and generates no new O-lens samples. Selection is local; the later benchmark judgments incurred separately recorded API costs.

The selector asks whether a capped complete candidate is more likely under its true activation than under matched controls. Each candidate is teacher-forced through the frozen released O-lens with the exact `concepts_raw` carrier, layer condition, and unit-normalized injection of 16000. Neither the target prompt/transcript nor known answers enter the carrier. The average candidate-token log likelihood is compared with the mean over the **first two controls** in the already frozen development control bank. Totals, actual lengths, individual token log probabilities and all conditional scores are retained. EOS is excluded consistently. This is a two-control pilot, not a silently enlarged or replaced bank.

Every method uses the same first 8 existing candidates, source-preserving contiguous-bullet parsing, maximum 4 bullets and 256 Qwen tokens. Parsing-ineligible candidates remain explicit exclusions. Candidate length is identical across its true/control conditions; token averaging is the fixed primary normalization. The same-pool exact-AR A8 output is retained as a comparator.

Two baselines require no additional forwards: selecting by highest own-activation average likelihood, and selecting by highest mean matched-control average likelihood (a proxy independent of this target activation). These help distinguish contrastive information from general fluency/wording preferences. All final outputs receive blind evaluation later; no judge verdict feeds this selection.

`src/olens_improve/contrastive.py` implements independent same-layer batched rows. `tests/test_likelihood_alignment.py` checks that the carrier's final logit predicts the first candidate token, later candidate logits shift correctly, and padding is excluded. The production singleton wrapper calls the same batching implementation. Runtime validation crosses candidate lengths and target/control activations; it compares batched scores with singleton forwards before the pilot.

The eight-cell instrument had batch/singleton absolute mean-log-likelihood differences of **.004609, .002769 and .002673 nats/token**, below the predeclared provisional .05 guard. It took **40.36 seconds total and 8.54 seconds for scoring** on the extra preemptable H200 job 25459615. This projected roughly 202 seconds of scoring for 189 cells, plus setup, supporting the bounded expansion. Passing this guard verifies the numerical implementation at these conditions; it does not prove semantic faithfulness or global ranking stability.

`scripts/likelihood_pilot.py` rejects duplicate sample inputs, verifies exact fresh target hashes and development/group control exclusions, freezes carrier/model/adapter/code/input/manifest hashes, and checkpoints one complete cell at a time. Resume rejects incompatible configurations or duplicate completed cells. The instrument evidence is `${OLENS_DATA_ROOT}/selections/e3-instrument8-v1/{spec.json,batch_fixture.json,readouts.jsonl,status.json}`. The expanded run is `${OLENS_DATA_ROOT}/selections/e3-pilot189-v1`; its `readouts.jsonl` stores the primary contrast winner, candidate conditions, own/control likelihood baselines and A8 comparator. Initial instrument metadata predates the added baseline/spec fields; preserve that parent artifact rather than relabeling it.

Judge the final outputs and compare representative wins/regressions against A8 and both likelihood baselines. Report family-specific cell denominators, uncertainty, lengths and runtime. The cohort is a partial-grid pilot; it cannot supply official full-grid item accuracy. More controls, candidate prefixes or likelihood normalizations require a separately identified development revision rather than per-item tuning.


## Completed 189-cell pilot

The expanded run completed in **194.64 seconds total**, with **176.15 seconds of scoring**. Its new layer-20 fixture had batch/singleton mean-log-likelihood differences of .002013, .007966 and .005310 nats/token. Mechanical checks verified identical candidate token lengths across true/control conditions and the common four-bullet/256-token output cap.

| Family | Cells | Contrast output differs from A8 | Differs from own-likelihood baseline | Differs from control-likelihood baseline |
|---|---:|---:|---:|---:|
| Chain | 21 | 15 | 18 | 21 |
| Hallucination | 72 | 64 | 64 | 72 |
| Multihop | 24 | 22 | 20 | 24 |
| Role | 72 | 64 | 62 | 71 |

These counts show that the contrast selects different text; they do not establish gains or regressions. Job 25459615 was released after the run for subsequent coordinated diagnostics.

## Judged results and decision

The terminal family results are under `${OLENS_DATA_ROOT}/runs/development-shared-pilot-v2/judgments`. The complete same-pool A8 comparator is `judgments-standard-repair/best_n_exact-n8`. Hallucination judgments include the second-stage claim verification. These are partial-grid **cell diagnostics**, not official full-grid item accuracy.

| Selector, all using N8 | Transcript-contradicting readouts / asserting readouts | Multihop bridge recovery | Chain recovery | Role recovery |
|---|---:|---:|---:|---:|
| Exact reconstruction A8 | 39/70 | 7/24 | 2/21 | 7/72 |
| True minus mean control likelihood | 39/70 | 6/24 | 2/21 | 8/72 |
| Own activation likelihood | 42/70 | 6/24 | 0/21 | 6/72 |
| Mean control likelihood | 42/72 | 9/24 | 0/21 | 10/72 |

The hallucination denominator includes contradicted, off-topic and consistent specific readouts; generic/empty readouts remain excluded and reported separately. Contrast versus A8 has 6 versus 7 off-topic readouts and identical assertion share, 70/72. Contrast has 8 paired contradiction wins and 8 regressions; 53 cells retain the same contradiction indicator, and 3 involve a nonasserting output. Those last three include a case where both outputs are generic and should not be read as three assertion changes. Never treat an unverifiable claim as false.

Paired contrast-minus-A8 rate differences with grouped 95% bootstrap intervals are: contradiction rate 0.0 percentage points [−15.6, +16.4], multihop −4.2 [−10.0, 0.0], chain 0.0 [−8.3, +11.1], role +1.4 [0.0, +4.2]. The 2,000 draws resample whole related groups: only 8 hallucination, 7 multihop, 2 chain and 4 role groups. These exploratory development intervals describe limited coverage; they are not a significance gate or confirmation of a robust role gain.

The reproducible trace audit inspected the first two cells by ID in each win/regression/unchanged category, plus two seeded random remaining unchanged cells per family. Hallucination improvements sometimes remove unsupported details such as eye-contact examples; regressions introduce names or greetings not supported by the transcript. Multihop loses one bridge match while both selectors often mix correct names with invented names. Chain gains one intermediate but loses another, with incorrect calculations and stray numbers in both conditions. Unchanged cells often retain generic summarization instructions or fail to identify the intermediate. The single role win deserves caution: its judge rationale itself says the exact patient is not clearly linked, despite a passing choice verdict. This is a judge-evidence inconsistency, not grounds to silently overwrite the frozen verdict.

The three new likelihood arms report **$0.0654123 incremental billed-attempt spend** after shared judgment-cache reuse. This is not a fair standalone cost per method; the central ledger remains authoritative, and the local 176.15-second likelihood scoring workload is additional to sampling/AR work. The saved analysis, source hashes, raw trace comparisons and audit script are under `${OLENS_DATA_ROOT}/analysis/e3-pilot189-review-v1`.

Decision: keep E3 as an exploratory combination component, but do not prioritize a full standalone expansion now. It shows isolated wins without a broad advantage over A8, while the control-only proxy does better on multihop and role, weakening an activation-specific interpretation. A bounded same-pool combination using the already saved candidate likelihoods and reconstruction scores can test incremental value without new forwards; compare its component-on/off versions. Wider evidence could change this decision, and a credible single-family practical gain warrants follow-up despite broad intervals. The current result is inconclusive for general improvement, not proof that conditional likelihood cannot help.
