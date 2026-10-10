# 006: Shared-pool reconstruction selection pilot

Status: AR encoding, offline A/C/D/E1 selections and subsequent blind judging completed for the fixed **189 development cells**, with 32 existing O-lens samples each. Judged results and grouped comparisons are in [009](009-pilot-grouped-comparisons.md). These incomplete family grids support cell-level diagnostics, not official item accuracy. Selection used no additional O-lens generations or paid API calls; later judging is accounted separately.

The immutable input snapshot is `${OLENS_DATA_ROOT}/runs/development-shared-pilot-v2`. Its 6,048 samples belong to global pool `e8cfd09f7ff1c9195cfd4c3a`. The exact cohort is `configs/splits_pilot_shared_v2.json`: 72 hallucination cells, 24 multihop cells, 21 chain cells and 72 role cells. Related groups remain in development under split v2. Source journal bytes and their terminal hashes are bound in the comparison configuration.

## Encoding and inference contract

`scripts/encode_candidates.py` applies the frozen contiguous-dash-block parser, four-bullet limit and 256-token output policy. It encodes each intact retained source bullet through the matched frozen prompt-tag AR, retaining all full source text, span offsets, layer, sample identity, target activation hash, cleaned token IDs, and any suffix beyond the AR's 32-token span. Effective-input cache keys include the cleaned first 32 token IDs, layer tag and model/head/tokenizer contract. Sharing a prefix vector does **not** merge claims or support votes.

The first pass encoded 24,186 full-text atom occurrences into **23,750 unique raw vectors** in 323.94 seconds on H200 job25330001. Six moderate-sized vector shards are under `${OLENS_COMPUTE_ROOT}/vectors/shared-global-v1/a451cf49d28ac7447722`. The contract, usage JSONL, raw-vector indexes and run JSON retain the evidence. No permanent whitened-vector duplicate is stored. Full suffixes remain visible to judges; AR scores do not validate unseen suffixes. The AR span truncates 1,514/24,186 atom occurrences (6.26%): multihop 169/3,072, chain 106/2,686, role 683/9,214 and hallucination 556/9,214. Only three effective-input cache keys have distinct full-text variants; these remain separate claims with separate provenance.

## Numerical batching audit

`scripts/ar_batch_stability.py` froze one lexicographically first layer 44 cell per family before scoring, using the first 16 complete candidates. Production cached batch 32 predictions were compared with fresh batch 8 predictions; the batch 32-selected atom set also received singleton checks. Production cache vectors were never replaced.

| Family | Maximum absolute FVE difference B8 vs cached B32 | Median absolute difference | Rank correlation | N16 winner changed? |
|---|---:|---:|---:|---|
| Chain | .002130 | .000682 | 1.0000 | No |
| Hallucination | .001345 | .000386 | .9912 | No |
| Multihop | .001317 | .000364 | .9912 | No |
| Role | .000872 | .000253 | .9971 | No |

Maximum relative raw-vector differences ranged from 2.65% to 5.02%; the largest selected-set singleton FVE difference was .001052 (multihop). Batch size/order/padding can affect bf16 predictions. Four unchanged winners are limited numerical evidence, not proof that all pool rankings are stable or that the scorer preserves semantic truth. Keep encoding settings and immutable first-computed cache vectors fixed across method comparisons. The 48.05-second audit, all texts, individual scores and diagnostic vectors are at `${OLENS_COMPUTE_ROOT}/runs/ar-batch-stability-v1`.

## Offline method conditions

`scripts/compare_selectors.py` consumes the immutable journals, actual fresh activation hashes, raw AR vectors and released matched moments. Exact SciPy NNLS is primary; released80 is a separately named compatibility score. Every proposed output uses intact source blocks and the same cap. The unmodified raw N1 baseline is retained; its fit is explicitly unavailable rather than assigning a capped-text fit to the full raw output.

Each cell has 40 recorded conditions: raw/capped N1; exact best-of-N, released80 best-of-N and seeded uniformly sampled complete candidates at N1/2/4/8/16/32; iterative fully refitted leave-one-out pruning at losses0/.001/.005, with matched-count seeded random deletion, for both capped N1 and exact A32; relative-coefficient pruning at .01/.05 for those two starting readouts; exact-text-deduplicated pooling at N16/N32 with four greedy addition rounds, one swap pass and a same-constraint complete-candidate fallback; and N32 mean-control/max-control specificity selections.

E1 consumes the **previously frozen** `${OLENS_DATA_ROOT}/manifests/development-matched-controls-v2.json`. It never invents a new bank. Controls match family/layer/read-position-kind, exclude each target's related group and all nondevelopment examples, and may include multiple cells from another group. Mean control FVE is primary; maximum control FVE is an explicit conservative ablation. Control identities and multiplicity are recorded.

The one-cell smoke took 15.93 seconds including startup; all189 cells took **130.11 seconds**. Mechanical checks verified 7,560 outputs, four-bullet/256-token compliance for every capped condition, and no empty final outputs. Four exact/released80 text differences occurred at intermediate prefixes (two hallucination, two role); no N32 winners differed. Pooling's exact fit exceeded same-prefix A for all378 N16/N32 comparisons, by at least .000433. These are selection/implementation checks; higher reconstruction is not a semantic gain.

Artifacts are `${OLENS_DATA_ROOT}/selections/pilot189-selectors-v1/{config.json,selections.jsonl,status.json}`. Each atomic cell envelope records text, phrase IDs, both solver fits, pruning/pooling traces, source atom/truncation provenance, parser flags, control diagnostics and configuration/code hashes. Resume rejects duplicate completed cells and incompatible settings. Blind evaluation should compare final outputs, reuse exact duplicate judgments, report family-specific denominators and inspect gains/regressions before expanding.
