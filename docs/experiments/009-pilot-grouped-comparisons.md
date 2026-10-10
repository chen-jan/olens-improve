# Development pilot cell diagnostics

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
