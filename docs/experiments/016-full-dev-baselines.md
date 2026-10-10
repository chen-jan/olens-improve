# 016: Full DEV baselines

Status: raw and capped N1 completed on the same 5,236 cells and 121 items. All source hashes, complete original grids, produced outputs, and nonempty stage 1/stage 2 judgments passed the reporting checks. Validation and test remain sealed. This establishes the baseline, not an improvement from selection.

complete original DEV grids: cell diagnostics and pinned item aggregation. Grouped intervals resample whole related groups (2,000 paired draws). Cell endpoints and pinned original item aggregation are separate below.

| Condition | Complete | Contradictions / specific | Bridge cells | Chain cells | Role cells |
|---|---|---:|---:|---:|---:|
| raw_n1-n1 | True | 545/1136 | 29/341 | 28/330 | 155/3420 |
| capped_n1-n1 | True | 543/1137 | 29/341 | 26/330 | 151/3420 |

Original-grid DEV aggregation uses the pinned item rule (ANY passing site/layer), with whole related groups resampled. Hallucination retains the ratio of readout counts, aggregated by item before resampling. These are development results, not held-out or whole-bank accuracy.

| Condition | Hall contradictions / specific | Bridge items | Chain items | Role items |
|---|---:|---:|---:|---:|
| raw_n1-n1 | 545/1136 | 11/31 | 16/30 | 23/30 |
| capped_n1-n1 | 543/1137 | 11/31 | 15/30 | 23/30 |

| Original-grid condition vs baseline | Family / endpoint | Paired delta | Grouped 95% interval | Groups |
|---|---|---:|---|---:|
| raw_n1-n1 vs capped N1 | hallucination / original_grid_contradiction_rate | 0.0022 | [-0.0027803521779425355, 0.007238848108413354] | 30 |
| raw_n1-n1 vs capped N1 | multihop_mt / original_grid_item_pass_rate | 0.0000 | [0.0, 0.0] | 29 |
| raw_n1-n1 vs capped N1 | chain_intermediates / original_grid_item_pass_rate | 0.0333 | [0.0, 0.13043478260869568] | 7 |
| raw_n1-n1 vs capped N1 | role_bound_association / original_grid_item_pass_rate | 0.0000 | [0.0, 0.0] | 15 |

| Condition vs baseline | Family / endpoint | Paired delta | Grouped 95% interval | Groups |
|---|---|---:|---|---:|
| raw_n1-n1 vs capped N1 | hallucination / contradiction_rate | 0.0022 | [-0.0027803521779425355, 0.007238848108413354] | 30 |
| raw_n1-n1 vs capped N1 | multihop_mt / cell_recovery | 0.0000 | [0.0, 0.0] | 29 |
| raw_n1-n1 vs capped N1 | chain_intermediates / cell_recovery | 0.0061 | [0.0, 0.01652892561983471] | 7 |
| raw_n1-n1 vs capped N1 | role_bound_association / cell_recovery | 0.0012 | [-0.00029239766081871205, 0.0029239766081871343] | 15 |

## Interpretation and source audit

Capping leaves original item recovery unchanged for bridge and role tasks and reduces chain recovery by one item. Its change in transcript contradiction rate is about −0.22 percentage points, with a paired whole-group 95% interval of −0.73 to +0.28 points. These are not established quality gains. The role endpoint credits any passing site across the grid: 23/30 items pass, although only 155/3,420 raw cells pass. This does not mean 23 complete explanations are faithful. We do not assume uniform random guessing; the frozen matched-donor diagnostic is the next contextual control.

The four examples in `durable/analysis/full-dev-baselines-v1/review.json` were checked against the actual output strings and frozen judgments:

- `chain-w2-d3p-0547`, L52/p70: the correct intermediate 17 remains the first bullet after capping, but the judge's ranked values change from `[17,27,31]` to `[27,31,25]`. The item loses its only hit. This diagnoses ranking/context sensitivity, not disappearance of the correct number.
- `chat-dailydialog-0035`, L60/p56: the raw and capped outputs are identical after whitespace normalization, yet the frozen classification changes from hallucinated to off-topic. Preserve the verdicts and treat this as a judge audit case, not a corrected ground truth label.
- `oa-boss-employee-envy-ba`: two of 114 raw sites pass, enough for an item pass. At L36/p122 the judge maps alternate names and a coworker description to the closest listed role option. The judge permits descriptions and supplies role/name mappings, so missing names alone does not establish a failure. The exact evidence merits contextual inspection.
- `mhh-borglum-son`, L36/p33: the bridge matcher credits Gutzon Borglum while the readout calls him the son and introduces Carl Gutzon Borglum. The bank identifies Gutzon as the sculptor bridge and Lincoln as the optional final target. A credited bridge string does not validate those relationships.

The pre-correction baseline ledger estimates **$0.8578232 for 6,230 settled physical requests**, with 5,312,697 input and 653,107 output tokens; no cached input tokens were reported. This is not an invoice charge: a later pricing audit found an omitted cache-write surcharge, and audited repricing is pending. The original ordered attempt snapshot is preserved. The first request was at 03:58:01 UTC and last settlement at 04:07:50 UTC. Source successful-response spend estimates total $0.8577938. This is campaign benchmark judging, not deployed selection cost. The compact audit binds the ordered attempt snapshot by SHA-256 without hashing a database that other runs continue to write.

The matched-donor export is ready: 5,236 target outputs, zero missing or empty donors, and 3,362 distinct donors. Its source SHA is `b37ef819bfa438bdb6a872075aa6817bc68792cc5d26cfaa1c1c2eb3179e426f`. Judging is pending and root owns launch. Future target-group intervals will be conditional on this fixed reused donor bank; they do not represent uncertainty over other donor-bank choices.

Sources: `dashboard/measurements-full-dev-baselines.json`, the frozen `development-full-grid-v2` manifest and baseline selection SHA `de69f103b8e8f9656cd5f729404bd5769e35c662cec1cfe8da95e0504bb31168`, terminal results under `durable/runs/development-full-grid-v2/judgments-baselines`, and the source-bound audit JSON above. Cell and original item intervals resample whole related groups (30 hallucination, 29 bridge, 7 chain, 15 role groups); the seven chain groups cannot establish robustness.
