# Development results

partial-grid cell diagnostics. Grouped intervals resample whole related groups (2,000 paired draws). These are not official full-grid item scores.

| Condition | Complete | Contradictions / specific | Bridge cells | Chain cells | Role cells |
|---|---|---:|---:|---:|---:|
| raw_n1-n1 | True | 46/71 | 4/24 | 1/21 | 8/72 |
| capped_n1-n1 | True | 46/71 | 4/24 | 0/21 | 8/72 |
| best_n_exact-n1 | True | 46/71 | 4/24 | 0/21 | 8/72 |
| best_n_exact-n2 | True | 43/72 | 7/24 | 0/21 | 10/72 |
| best_n_exact-n4 | True | 42/72 | 7/24 | 1/21 | 9/72 |
| best_n_exact-n8 | True | 39/70 | 7/24 | 2/21 | 7/72 |
| best_n_exact-n16 | True | 40/71 | 9/24 | 3/21 | 8/72 |
| best_n_exact-n32 | True | 39/71 | 7/24 | 3/21 | 9/72 |
| random_complete-n16 | True | 41/72 | 6/24 | 0/21 | 8/72 |
| random_complete-n32 | True | 38/72 | 8/24 | 2/21 | 8/72 |
| pooled_greedy_swap-n16 | True | 43/72 | 8/24 | 1/21 | 8/72 |
| pooled_greedy_swap-n32 | True | 42/70 | 10/24 | 1/21 | 8/72 |
| prune_loo_a32_0.001-n32 | True | 38/70 | 7/24 | 1/21 | 10/72 |
| prune_loo_a32_0.005-n32 | True | 37/72 | 7/24 | 1/21 | 10/72 |
| best_n_specificity_mean-n32 | True | 38/71 | 7/24 | 1/21 | 9/72 |
| best_n_specificity_max-n32 | True | 42/71 | 8/24 | 1/21 | 6/72 |
| best_n_released80-n1 | True | 46/71 | 4/24 | 0/21 | 8/72 |
| best_n_released80-n2 | True | 43/72 | 7/24 | 0/21 | 10/72 |
| best_n_released80-n4 | True | 42/72 | 7/24 | 1/21 | 9/72 |
| best_n_released80-n8 | True | 39/70 | 7/24 | 2/21 | 7/72 |
| best_n_released80-n16 | True | 40/71 | 9/24 | 3/21 | 8/72 |
| best_n_released80-n32 | True | 39/71 | 7/24 | 3/21 | 9/72 |
| likelihood_true_minus_mean_two_controls-n8 | True | 39/70 | 6/24 | 2/21 | 8/72 |
| own_mean_log_likelihood-n8 | True | 42/70 | 6/24 | 0/21 | 6/72 |
| control_mean_log_likelihood-n8 | True | 42/72 | 9/24 | 0/21 | 10/72 |
| consensus_exact_support0-n16 | True | 42/71 | 4/24 | 0/21 | 8/72 |
| consensus_semantic_v4_support0_compatoff-n16 | True | 39/70 | 4/24 | 1/21 | 8/72 |
| consensus_semantic_v4_support0_compaton-n16 | True | 20/63 | 1/24 | 1/21 | 3/72 |
| consensus_exact_support0.125-n16 | True | 1/8 | 0/24 | 1/21 | 0/72 |
| consensus_semantic_v4_support0.125_compatoff-n16 | True | 11/34 | 1/24 | 1/21 | 3/72 |
| consensus_semantic_v4_support0.125_compaton-n16 | True | 9/34 | 1/24 | 1/21 | 2/72 |
| consensus_exact_support0.25-n16 | True | 0/1 | 0/24 | 1/21 | 0/72 |
| consensus_semantic_v4_support0.25_compatoff-n16 | True | 0/1 | 0/24 | 1/21 | 0/72 |
| consensus_semantic_v4_support0.25_compaton-n16 | True | 0/1 | 0/24 | 1/21 | 0/72 |
| editing_round1-n32 | True | 42/70 | 10/24 | 1/21 | 8/72 |
| editing_round2-n32 | True | 42/69 | 10/24 | 1/21 | 8/72 |
| pooled_greedy_swap_then_prune_0.001-n32 | True | 40/70 | 9/24 | 1/21 | 8/72 |
| pooled_greedy_swap_random_delete_matched_0.001-n32 | True | 41/70 | 10/24 | 1/21 | 8/72 |
| pooled_greedy_swap_then_prune_0.005-n32 | True | 39/72 | 6/24 | 0/21 | 8/72 |
| pooled_greedy_swap_random_delete_matched_0.005-n32 | True | 33/72 | 7/24 | 0/21 | 7/72 |
| best_n_specificity_mean_then_prune_0.001-n32 | True | 38/70 | 7/24 | 1/21 | 12/72 |
| best_n_specificity_mean_random_delete_matched_0.001-n32 | True | 37/71 | 6/24 | 1/21 | 8/72 |
| best_n_specificity_mean_then_prune_0.005-n32 | True | 36/72 | 7/24 | 1/21 | 12/72 |
| best_n_specificity_mean_random_delete_matched_0.005-n32 | True | 37/72 | 5/24 | 0/21 | 7/72 |
| editing_round2_then_prune_0.001-n32 | True | 42/69 | 9/24 | 1/21 | 8/72 |
| editing_round2_random_delete_matched_0.001-n32 | True | 41/69 | 10/24 | 1/21 | 8/72 |
| editing_round2_then_prune_0.005-n32 | True | 40/72 | 6/24 | 0/21 | 8/72 |
| editing_round2_random_delete_matched_0.005-n32 | True | 37/70 | 8/24 | 0/21 | 7/72 |
| pooling_exact_support_lambda0-n16 | True | 43/72 | 8/24 | 1/21 | 8/72 |
| pooling_exact_support_lambda0.05-n16 | True | 43/72 | 8/24 | 1/21 | 8/72 |
| pooling_exact_support_lambda0.2-n16 | True | 43/71 | 8/24 | 1/21 | 8/72 |
| exact_support_only-n16 | True | 42/71 | 4/24 | 0/21 | 8/72 |

| Condition vs baseline | Family / endpoint | Paired delta | Grouped 95% interval | Groups |
|---|---|---:|---|---:|
| raw_n1-n1 vs capped N1 | hallucination / contradiction_rate | 0.0000 | [0.0, 0.0] | 8 |
| raw_n1-n1 vs capped N1 | multihop_mt / cell_recovery | 0.0000 | [0.0, 0.0] | 7 |
| raw_n1-n1 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.1111111111111111] | 2 |
| raw_n1-n1 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [0.0, 0.0] | 4 |
| best_n_exact-n1 vs capped N1 | hallucination / contradiction_rate | 0.0000 | [0.0, 0.0] | 8 |
| best_n_exact-n1 vs capped N1 | multihop_mt / cell_recovery | 0.0000 | [0.0, 0.0] | 7 |
| best_n_exact-n1 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| best_n_exact-n1 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [0.0, 0.0] | 4 |
| best_n_exact-n2 vs capped N1 | hallucination / contradiction_rate | -0.0507 | [-0.09722222222222221, 0.013492063492063555] | 8 |
| best_n_exact-n2 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.0, 0.24999999999999997] | 7 |
| best_n_exact-n2 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| best_n_exact-n2 vs capped N1 | role_bound_association / cell_recovery | 0.0278 | [-0.027777777777777762, 0.055555555555555566] | 4 |
| best_n_exact-n4 vs capped N1 | hallucination / contradiction_rate | -0.0646 | [-0.125, 0.0] | 8 |
| best_n_exact-n4 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.0, 0.24999999999999997] | 7 |
| best_n_exact-n4 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| best_n_exact-n4 vs capped N1 | role_bound_association / cell_recovery | 0.0139 | [0.0, 0.04166666666666667] | 4 |
| best_n_exact-n8 vs capped N1 | hallucination / contradiction_rate | -0.0907 | [-0.18505477308294216, 0.002245356195141879] | 8 |
| best_n_exact-n8 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.0, 0.24999999999999997] | 7 |
| best_n_exact-n8 vs capped N1 | chain_intermediates / cell_recovery | 0.0952 | [0.0, 0.16666666666666666] | 2 |
| best_n_exact-n8 vs capped N1 | role_bound_association / cell_recovery | -0.0139 | [-0.04166666666666667, 0.0] | 4 |
| best_n_exact-n16 vs capped N1 | hallucination / contradiction_rate | -0.0845 | [-0.1899452269170579, 0.03462441314553988] | 8 |
| best_n_exact-n16 vs capped N1 | multihop_mt / cell_recovery | 0.2083 | [0.047619047619047616, 0.36666666666666664] | 7 |
| best_n_exact-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.1429 | [0.1111111111111111, 0.16666666666666666] | 2 |
| best_n_exact-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.04166666666666667, 0.04166666666666667] | 4 |
| best_n_exact-n32 vs capped N1 | hallucination / contradiction_rate | -0.0986 | [-0.20833333333333337, 0.02777777777777779] | 8 |
| best_n_exact-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.04166666666666666, 0.23809523809523808] | 7 |
| best_n_exact-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.1429 | [0.1111111111111111, 0.16666666666666666] | 2 |
| best_n_exact-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0139 | [-0.027777777777777776, 0.05555555555555555] | 4 |
| random_complete-n16 vs capped N1 | hallucination / contradiction_rate | -0.0784 | [-0.17781690140845074, 0.019757433489827836] | 8 |
| random_complete-n16 vs capped N1 | multihop_mt / cell_recovery | 0.0833 | [0.0, 0.2] | 7 |
| random_complete-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| random_complete-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.06944444444444445, 0.05555555555555555] | 4 |
| random_complete-n32 vs capped N1 | hallucination / contradiction_rate | -0.1201 | [-0.26388888888888895, 0.005281690140845119] | 8 |
| random_complete-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1667 | [0.047619047619047616, 0.29166666666666663] | 7 |
| random_complete-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0952 | [0.08333333333333333, 0.1111111111111111] | 2 |
| random_complete-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.04166666666666666, 0.04166666666666666] | 4 |
| pooled_greedy_swap-n16 vs capped N1 | hallucination / contradiction_rate | -0.0507 | [-0.12323943661971826, 0.0199530516431925] | 8 |
| pooled_greedy_swap-n16 vs capped N1 | multihop_mt / cell_recovery | 0.1667 | [0.0, 0.33333333333333337] | 7 |
| pooled_greedy_swap-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| pooled_greedy_swap-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.08333333333333333, 0.08333333333333334] | 4 |
| pooled_greedy_swap-n32 vs capped N1 | hallucination / contradiction_rate | -0.0479 | [-0.12676056338028163, 0.03731343283582089] | 8 |
| pooled_greedy_swap-n32 vs capped N1 | multihop_mt / cell_recovery | 0.2500 | [0.09523809523809523, 0.3939393939393939] | 7 |
| pooled_greedy_swap-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| pooled_greedy_swap-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.041666666666666664, 0.04166666666666666] | 4 |
| prune_loo_a32_0.001-n32 vs capped N1 | hallucination / contradiction_rate | -0.1050 | [-0.24603174603174593, 0.06897265948632969] | 8 |
| prune_loo_a32_0.001-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.04166666666666666, 0.23809523809523808] | 7 |
| prune_loo_a32_0.001-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| prune_loo_a32_0.001-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0278 | [0.0, 0.05555555555555555] | 4 |
| prune_loo_a32_0.005-n32 vs capped N1 | hallucination / contradiction_rate | -0.1340 | [-0.2607589984350548, 0.021517996870109524] | 8 |
| prune_loo_a32_0.005-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.04166666666666666, 0.23809523809523808] | 7 |
| prune_loo_a32_0.005-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| prune_loo_a32_0.005-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0278 | [0.0, 0.05555555555555555] | 4 |
| best_n_specificity_mean-n32 vs capped N1 | hallucination / contradiction_rate | -0.1127 | [-0.2535211267605634, 0.036418511066398374] | 8 |
| best_n_specificity_mean-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.04166666666666666, 0.23809523809523808] | 7 |
| best_n_specificity_mean-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| best_n_specificity_mean-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0139 | [-0.02777777777777779, 0.055555555555555566] | 4 |
| best_n_specificity_max-n32 vs capped N1 | hallucination / contradiction_rate | -0.0563 | [-0.16666666666666663, 0.05714285714285716] | 8 |
| best_n_specificity_max-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1667 | [0.047619047619047616, 0.29166666666666663] | 7 |
| best_n_specificity_max-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| best_n_specificity_max-n32 vs capped N1 | role_bound_association / cell_recovery | -0.0278 | [-0.05555555555555556, 0.0] | 4 |
| best_n_released80-n1 vs capped N1 | hallucination / contradiction_rate | 0.0000 | [0.0, 0.0] | 8 |
| best_n_released80-n1 vs capped N1 | multihop_mt / cell_recovery | 0.0000 | [0.0, 0.0] | 7 |
| best_n_released80-n1 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| best_n_released80-n1 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [0.0, 0.0] | 4 |
| best_n_released80-n2 vs capped N1 | hallucination / contradiction_rate | -0.0507 | [-0.09722222222222221, 0.013492063492063555] | 8 |
| best_n_released80-n2 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.0, 0.24999999999999997] | 7 |
| best_n_released80-n2 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| best_n_released80-n2 vs capped N1 | role_bound_association / cell_recovery | 0.0278 | [-0.027777777777777762, 0.055555555555555566] | 4 |
| best_n_released80-n4 vs capped N1 | hallucination / contradiction_rate | -0.0646 | [-0.125, 0.0] | 8 |
| best_n_released80-n4 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.0, 0.24999999999999997] | 7 |
| best_n_released80-n4 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| best_n_released80-n4 vs capped N1 | role_bound_association / cell_recovery | 0.0139 | [0.0, 0.04166666666666667] | 4 |
| best_n_released80-n8 vs capped N1 | hallucination / contradiction_rate | -0.0907 | [-0.18505477308294216, 0.002245356195141879] | 8 |
| best_n_released80-n8 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.0, 0.24999999999999997] | 7 |
| best_n_released80-n8 vs capped N1 | chain_intermediates / cell_recovery | 0.0952 | [0.0, 0.16666666666666666] | 2 |
| best_n_released80-n8 vs capped N1 | role_bound_association / cell_recovery | -0.0139 | [-0.04166666666666667, 0.0] | 4 |
| best_n_released80-n16 vs capped N1 | hallucination / contradiction_rate | -0.0845 | [-0.1899452269170579, 0.03462441314553988] | 8 |
| best_n_released80-n16 vs capped N1 | multihop_mt / cell_recovery | 0.2083 | [0.047619047619047616, 0.36666666666666664] | 7 |
| best_n_released80-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.1429 | [0.1111111111111111, 0.16666666666666666] | 2 |
| best_n_released80-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.04166666666666667, 0.04166666666666667] | 4 |
| best_n_released80-n32 vs capped N1 | hallucination / contradiction_rate | -0.0986 | [-0.20833333333333337, 0.02777777777777779] | 8 |
| best_n_released80-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.04166666666666666, 0.23809523809523808] | 7 |
| best_n_released80-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.1429 | [0.1111111111111111, 0.16666666666666666] | 2 |
| best_n_released80-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0139 | [-0.027777777777777776, 0.05555555555555555] | 4 |
| likelihood_true_minus_mean_two_controls-n8 vs capped N1 | hallucination / contradiction_rate | -0.0907 | [-0.1942028985507246, 0.01207729468599028] | 8 |
| likelihood_true_minus_mean_two_controls-n8 vs capped N1 | multihop_mt / cell_recovery | 0.0833 | [0.0, 0.16666666666666669] | 7 |
| likelihood_true_minus_mean_two_controls-n8 vs capped N1 | chain_intermediates / cell_recovery | 0.0952 | [0.08333333333333333, 0.1111111111111111] | 2 |
| likelihood_true_minus_mean_two_controls-n8 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.04166666666666667, 0.04166666666666666] | 4 |
| own_mean_log_likelihood-n8 vs capped N1 | hallucination / contradiction_rate | -0.0479 | [-0.14358372456964008, 0.0444444444444444] | 8 |
| own_mean_log_likelihood-n8 vs capped N1 | multihop_mt / cell_recovery | 0.0833 | [0.0, 0.16666666666666669] | 7 |
| own_mean_log_likelihood-n8 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| own_mean_log_likelihood-n8 vs capped N1 | role_bound_association / cell_recovery | -0.0278 | [-0.08333333333333333, 0.0] | 4 |
| control_mean_log_likelihood-n8 vs capped N1 | hallucination / contradiction_rate | -0.0646 | [-0.1611111111111112, 0.01388888888888884] | 8 |
| control_mean_log_likelihood-n8 vs capped N1 | multihop_mt / cell_recovery | 0.2083 | [0.047619047619047616, 0.36666666666666664] | 7 |
| control_mean_log_likelihood-n8 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| control_mean_log_likelihood-n8 vs capped N1 | role_bound_association / cell_recovery | 0.0278 | [0.0, 0.055555555555555566] | 4 |
| consensus_exact_support0-n16 vs capped N1 | hallucination / contradiction_rate | -0.0563 | [-0.11865079365079367, 0.0] | 8 |
| consensus_exact_support0-n16 vs capped N1 | multihop_mt / cell_recovery | 0.0000 | [0.0, 0.0] | 7 |
| consensus_exact_support0-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| consensus_exact_support0-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [0.0, 0.0] | 4 |
| consensus_semantic_v4_support0_compatoff-n16 vs capped N1 | hallucination / contradiction_rate | -0.0907 | [-0.18055555555555558, -0.011022657685241799] | 8 |
| consensus_semantic_v4_support0_compatoff-n16 vs capped N1 | multihop_mt / cell_recovery | 0.0000 | [0.0, 0.0] | 7 |
| consensus_semantic_v4_support0_compatoff-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| consensus_semantic_v4_support0_compatoff-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [0.0, 0.0] | 4 |
| consensus_semantic_v4_support0_compaton-n16 vs capped N1 | hallucination / contradiction_rate | -0.3304 | [-0.5012626262626263, -0.17843137254901958] | 8 |
| consensus_semantic_v4_support0_compaton-n16 vs capped N1 | multihop_mt / cell_recovery | -0.1250 | [-0.3, 0.0] | 7 |
| consensus_semantic_v4_support0_compaton-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| consensus_semantic_v4_support0_compaton-n16 vs capped N1 | role_bound_association / cell_recovery | -0.0694 | [-0.11111111111111112, -0.027777777777777776] | 4 |
| consensus_exact_support0.125-n16 vs capped N1 | hallucination / contradiction_rate | -0.5229 | [-0.7464788732394366, -0.32857142857142857] | 8 |
| consensus_exact_support0.125-n16 vs capped N1 | multihop_mt / cell_recovery | -0.1667 | [-0.3333333333333333, 0.0] | 7 |
| consensus_exact_support0.125-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| consensus_exact_support0.125-n16 vs capped N1 | role_bound_association / cell_recovery | -0.1111 | [-0.18055555555555555, -0.05555555555555555] | 4 |
| consensus_semantic_v4_support0.125_compatoff-n16 vs capped N1 | hallucination / contradiction_rate | -0.3244 | [-0.513888888888889, -0.17125237191650852] | 8 |
| consensus_semantic_v4_support0.125_compatoff-n16 vs capped N1 | multihop_mt / cell_recovery | -0.1250 | [-0.3, 0.0] | 7 |
| consensus_semantic_v4_support0.125_compatoff-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| consensus_semantic_v4_support0.125_compatoff-n16 vs capped N1 | role_bound_association / cell_recovery | -0.0694 | [-0.1388888888888889, -0.013888888888888895] | 4 |
| consensus_semantic_v4_support0.125_compaton-n16 vs capped N1 | hallucination / contradiction_rate | -0.3832 | [-0.5560318432333129, -0.20246478873239437] | 8 |
| consensus_semantic_v4_support0.125_compaton-n16 vs capped N1 | multihop_mt / cell_recovery | -0.1250 | [-0.3, 0.0] | 7 |
| consensus_semantic_v4_support0.125_compaton-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| consensus_semantic_v4_support0.125_compaton-n16 vs capped N1 | role_bound_association / cell_recovery | -0.0833 | [-0.1388888888888889, -0.05555555555555555] | 4 |
| consensus_exact_support0.25-n16 vs capped N1 | hallucination / contradiction_rate | -0.6479 | [-0.8194444444444444, -0.45714285714285713] | 8 |
| consensus_exact_support0.25-n16 vs capped N1 | multihop_mt / cell_recovery | -0.1667 | [-0.3333333333333333, 0.0] | 7 |
| consensus_exact_support0.25-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| consensus_exact_support0.25-n16 vs capped N1 | role_bound_association / cell_recovery | -0.1111 | [-0.18055555555555555, -0.05555555555555555] | 4 |
| consensus_semantic_v4_support0.25_compatoff-n16 vs capped N1 | hallucination / contradiction_rate | -0.6479 | [-0.8194444444444444, -0.45714285714285713] | 8 |
| consensus_semantic_v4_support0.25_compatoff-n16 vs capped N1 | multihop_mt / cell_recovery | -0.1667 | [-0.3333333333333333, 0.0] | 7 |
| consensus_semantic_v4_support0.25_compatoff-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| consensus_semantic_v4_support0.25_compatoff-n16 vs capped N1 | role_bound_association / cell_recovery | -0.1111 | [-0.18055555555555555, -0.05555555555555555] | 4 |
| consensus_semantic_v4_support0.25_compaton-n16 vs capped N1 | hallucination / contradiction_rate | -0.6479 | [-0.8194444444444444, -0.45714285714285713] | 8 |
| consensus_semantic_v4_support0.25_compaton-n16 vs capped N1 | multihop_mt / cell_recovery | -0.1667 | [-0.3333333333333333, 0.0] | 7 |
| consensus_semantic_v4_support0.25_compaton-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| consensus_semantic_v4_support0.25_compaton-n16 vs capped N1 | role_bound_association / cell_recovery | -0.1111 | [-0.18055555555555555, -0.05555555555555555] | 4 |
| editing_round1-n32 vs capped N1 | hallucination / contradiction_rate | -0.0479 | [-0.12676056338028163, 0.03731343283582089] | 8 |
| editing_round1-n32 vs capped N1 | multihop_mt / cell_recovery | 0.2500 | [0.09523809523809523, 0.3939393939393939] | 7 |
| editing_round1-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| editing_round1-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.041666666666666664, 0.04166666666666666] | 4 |
| editing_round2-n32 vs capped N1 | hallucination / contradiction_rate | -0.0392 | [-0.11649899396378272, 0.040182270091135064] | 8 |
| editing_round2-n32 vs capped N1 | multihop_mt / cell_recovery | 0.2500 | [0.09523809523809523, 0.3939393939393939] | 7 |
| editing_round2-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| editing_round2-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.041666666666666664, 0.04166666666666666] | 4 |
| pooled_greedy_swap_then_prune_0.001-n32 vs capped N1 | hallucination / contradiction_rate | -0.0765 | [-0.15714285714285714, 0.020238095238095166] | 8 |
| pooled_greedy_swap_then_prune_0.001-n32 vs capped N1 | multihop_mt / cell_recovery | 0.2083 | [0.047619047619047616, 0.36666666666666664] | 7 |
| pooled_greedy_swap_then_prune_0.001-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| pooled_greedy_swap_then_prune_0.001-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.041666666666666664, 0.04166666666666666] | 4 |
| pooled_greedy_swap_random_delete_matched_0.001-n32 vs capped N1 | hallucination / contradiction_rate | -0.0622 | [-0.14492753623188404, 0.032539682539682535] | 8 |
| pooled_greedy_swap_random_delete_matched_0.001-n32 vs capped N1 | multihop_mt / cell_recovery | 0.2500 | [0.09523809523809523, 0.3939393939393939] | 7 |
| pooled_greedy_swap_random_delete_matched_0.001-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| pooled_greedy_swap_random_delete_matched_0.001-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.041666666666666664, 0.04166666666666666] | 4 |
| pooled_greedy_swap_then_prune_0.005-n32 vs capped N1 | hallucination / contradiction_rate | -0.1062 | [-0.20169082125603865, -0.009585289514866924] | 8 |
| pooled_greedy_swap_then_prune_0.005-n32 vs capped N1 | multihop_mt / cell_recovery | 0.0833 | [0.0, 0.16666666666666669] | 7 |
| pooled_greedy_swap_then_prune_0.005-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| pooled_greedy_swap_then_prune_0.005-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.041666666666666664, 0.04166666666666666] | 4 |
| pooled_greedy_swap_random_delete_matched_0.005-n32 vs capped N1 | hallucination / contradiction_rate | -0.1896 | [-0.3472222222222222, -0.05555555555555558] | 8 |
| pooled_greedy_swap_random_delete_matched_0.005-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.04166666666666666, 0.2222222222222222] | 7 |
| pooled_greedy_swap_random_delete_matched_0.005-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| pooled_greedy_swap_random_delete_matched_0.005-n32 vs capped N1 | role_bound_association / cell_recovery | -0.0139 | [-0.055555555555555566, 0.027777777777777776] | 4 |
| best_n_specificity_mean_then_prune_0.001-n32 vs capped N1 | hallucination / contradiction_rate | -0.1050 | [-0.2605633802816901, 0.07867494824016569] | 8 |
| best_n_specificity_mean_then_prune_0.001-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.04166666666666666, 0.23809523809523808] | 7 |
| best_n_specificity_mean_then_prune_0.001-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| best_n_specificity_mean_then_prune_0.001-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0556 | [0.013888888888888895, 0.09722222222222221] | 4 |
| best_n_specificity_mean_random_delete_matched_0.001-n32 vs capped N1 | hallucination / contradiction_rate | -0.1268 | [-0.3098591549295775, 0.028169014084507005] | 8 |
| best_n_specificity_mean_random_delete_matched_0.001-n32 vs capped N1 | multihop_mt / cell_recovery | 0.0833 | [0.0, 0.16666666666666669] | 7 |
| best_n_specificity_mean_random_delete_matched_0.001-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| best_n_specificity_mean_random_delete_matched_0.001-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.04166666666666667, 0.04166666666666667] | 4 |
| best_n_specificity_mean_then_prune_0.005-n32 vs capped N1 | hallucination / contradiction_rate | -0.1479 | [-0.29523809523809524, 0.02073552425665104] | 8 |
| best_n_specificity_mean_then_prune_0.005-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1250 | [0.04166666666666666, 0.23809523809523808] | 7 |
| best_n_specificity_mean_then_prune_0.005-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| best_n_specificity_mean_then_prune_0.005-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0556 | [0.05555555555555555, 0.055555555555555566] | 4 |
| best_n_specificity_mean_random_delete_matched_0.005-n32 vs capped N1 | hallucination / contradiction_rate | -0.1340 | [-0.2777777777777778, -0.0134920634920635] | 8 |
| best_n_specificity_mean_random_delete_matched_0.005-n32 vs capped N1 | multihop_mt / cell_recovery | 0.0417 | [0.0, 0.14285714285714285] | 7 |
| best_n_specificity_mean_random_delete_matched_0.005-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| best_n_specificity_mean_random_delete_matched_0.005-n32 vs capped N1 | role_bound_association / cell_recovery | -0.0139 | [-0.04166666666666667, 0.0] | 4 |
| editing_round2_then_prune_0.001-n32 vs capped N1 | hallucination / contradiction_rate | -0.0392 | [-0.11649899396378272, 0.040182270091135064] | 8 |
| editing_round2_then_prune_0.001-n32 vs capped N1 | multihop_mt / cell_recovery | 0.2083 | [0.047619047619047616, 0.36666666666666664] | 7 |
| editing_round2_then_prune_0.001-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| editing_round2_then_prune_0.001-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.041666666666666664, 0.04166666666666666] | 4 |
| editing_round2_random_delete_matched_0.001-n32 vs capped N1 | hallucination / contradiction_rate | -0.0537 | [-0.13888888888888895, 0.033333333333333326] | 8 |
| editing_round2_random_delete_matched_0.001-n32 vs capped N1 | multihop_mt / cell_recovery | 0.2500 | [0.09523809523809523, 0.3939393939393939] | 7 |
| editing_round2_random_delete_matched_0.001-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| editing_round2_random_delete_matched_0.001-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.041666666666666664, 0.04166666666666666] | 4 |
| editing_round2_then_prune_0.005-n32 vs capped N1 | hallucination / contradiction_rate | -0.0923 | [-0.1780125195618154, -0.00860719874804372] | 8 |
| editing_round2_then_prune_0.005-n32 vs capped N1 | multihop_mt / cell_recovery | 0.0833 | [0.0, 0.16666666666666669] | 7 |
| editing_round2_then_prune_0.005-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| editing_round2_then_prune_0.005-n32 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.041666666666666664, 0.04166666666666666] | 4 |
| editing_round2_random_delete_matched_0.005-n32 vs capped N1 | hallucination / contradiction_rate | -0.1193 | [-0.2564553990610329, 0.014084507042253502] | 8 |
| editing_round2_random_delete_matched_0.005-n32 vs capped N1 | multihop_mt / cell_recovery | 0.1667 | [0.047619047619047616, 0.2857142857142857] | 7 |
| editing_round2_random_delete_matched_0.005-n32 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| editing_round2_random_delete_matched_0.005-n32 vs capped N1 | role_bound_association / cell_recovery | -0.0139 | [-0.05555555555555555, 0.02777777777777779] | 4 |
| pooling_exact_support_lambda0-n16 vs capped N1 | hallucination / contradiction_rate | -0.0507 | [-0.12323943661971826, 0.0199530516431925] | 8 |
| pooling_exact_support_lambda0-n16 vs capped N1 | multihop_mt / cell_recovery | 0.1667 | [0.0, 0.33333333333333337] | 7 |
| pooling_exact_support_lambda0-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| pooling_exact_support_lambda0-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.08333333333333333, 0.08333333333333334] | 4 |
| pooling_exact_support_lambda0.05-n16 vs capped N1 | hallucination / contradiction_rate | -0.0507 | [-0.12323943661971826, 0.0199530516431925] | 8 |
| pooling_exact_support_lambda0.05-n16 vs capped N1 | multihop_mt / cell_recovery | 0.1667 | [0.0, 0.33333333333333337] | 7 |
| pooling_exact_support_lambda0.05-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| pooling_exact_support_lambda0.05-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.08333333333333333, 0.08333333333333334] | 4 |
| pooling_exact_support_lambda0.2-n16 vs capped N1 | hallucination / contradiction_rate | -0.0423 | [-0.14084507042253513, 0.04347826086956519] | 8 |
| pooling_exact_support_lambda0.2-n16 vs capped N1 | multihop_mt / cell_recovery | 0.1667 | [0.0, 0.33333333333333337] | 7 |
| pooling_exact_support_lambda0.2-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0476 | [0.0, 0.08333333333333333] | 2 |
| pooling_exact_support_lambda0.2-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [-0.08333333333333333, 0.08333333333333334] | 4 |
| exact_support_only-n16 vs capped N1 | hallucination / contradiction_rate | -0.0563 | [-0.11865079365079367, 0.0] | 8 |
| exact_support_only-n16 vs capped N1 | multihop_mt / cell_recovery | 0.0000 | [0.0, 0.0] | 7 |
| exact_support_only-n16 vs capped N1 | chain_intermediates / cell_recovery | 0.0000 | [0.0, 0.0] | 2 |
| exact_support_only-n16 vs capped N1 | role_bound_association / cell_recovery | 0.0000 | [0.0, 0.0] | 4 |
