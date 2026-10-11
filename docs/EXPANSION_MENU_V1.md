# Exact expansion menu (sealed v1)

Active conditions: 70. Source seal: 753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8.

| Condition | Status | Parents |
|---|---|---|
| raw_n1-n1 | cached_selector_full_bank |  |
| capped_n1-n1 | cached_selector_full_bank | raw_n1-n1 |
| best_n_exact-n1 | cached_selector_full_bank | capped_n1-n1 |
| best_n_exact-n2 | cached_selector_full_bank | capped_n1-n1 |
| best_n_exact-n4 | cached_selector_full_bank | capped_n1-n1 |
| best_n_exact-n8 | cached_selector_full_bank | capped_n1-n1 |
| best_n_exact-n16 | cached_selector_full_bank | capped_n1-n1 |
| best_n_exact-n32 | cached_selector_full_bank | capped_n1-n1 |
| random_complete-n16 | cached_selector_full_bank | capped_n1-n1 |
| random_complete-n32 | cached_selector_full_bank | capped_n1-n1 |
| pooled_greedy_swap-n16 | cached_selector_full_bank | capped_n1-n1 |
| pooled_greedy_swap-n32 | cached_selector_full_bank | capped_n1-n1 |
| prune_loo_a32_0.001-n32 | cached_selector_full_bank | best_n_exact-n32 |
| prune_loo_a32_0.005-n32 | cached_selector_full_bank | best_n_exact-n32 |
| random_delete_matched_a32_0.001-n32 | cached_selector_full_bank | best_n_exact-n32 |
| random_delete_matched_a32_0.005-n32 | cached_selector_full_bank | best_n_exact-n32 |
| prune_loo_n1_0.005-n1 | cached_selector_full_bank | capped_n1-n1 |
| random_delete_matched_n1_0.005-n1 | cached_selector_full_bank | capped_n1-n1 |
| best_n_specificity_mean-n32 | cached_selector_full_bank | capped_n1-n1 |
| best_n_specificity_max-n32 | cached_selector_full_bank | capped_n1-n1 |
| best_n_specificity_mean_then_prune_0.001-n32 | scheduled_full_bank | best_n_specificity_mean-n32 |
| best_n_specificity_mean_then_prune_0.005-n32 | scheduled_full_bank | best_n_specificity_mean-n32 |
| best_n_specificity_mean_random_delete_matched_0.001-n32 | scheduled_full_bank | best_n_specificity_mean-n32 |
| best_n_specificity_mean_random_delete_matched_0.005-n32 | scheduled_full_bank | best_n_specificity_mean-n32 |
| best_n_released80-n1 | computed_numerical_diagnostic_only | capped_n1-n1 |
| best_n_released80-n2 | computed_numerical_diagnostic_only | capped_n1-n1 |
| best_n_released80-n4 | computed_numerical_diagnostic_only | capped_n1-n1 |
| best_n_released80-n8 | computed_numerical_diagnostic_only | capped_n1-n1 |
| best_n_released80-n16 | computed_numerical_diagnostic_only | capped_n1-n1 |
| best_n_released80-n32 | computed_numerical_diagnostic_only | capped_n1-n1 |
| likelihood_true_minus_mean_two_controls-n8 | scheduled_full_bank | capped_n1-n1 |
| own_mean_log_likelihood-n8 | scheduled_full_bank | capped_n1-n1 |
| control_mean_log_likelihood-n8 | scheduled_full_bank | capped_n1-n1 |
| consensus_exact_support0-n16 | scheduled_full_bank | capped_n1-n1 |
| consensus_semantic_v4_support0_compatoff-n16 | obsolete_malformed_transport_diagnostic | consensus_exact_support0-n16 |
| consensus_semantic_v4_support0_compaton-n16 | obsolete_malformed_transport_diagnostic | consensus_exact_support0-n16 |
| consensus_exact_support0.125-n16 | scheduled_full_bank | capped_n1-n1 |
| consensus_semantic_v4_support0.125_compatoff-n16 | obsolete_malformed_transport_diagnostic | consensus_exact_support0-n16 |
| consensus_semantic_v4_support0.125_compaton-n16 | obsolete_malformed_transport_diagnostic | consensus_exact_support0-n16 |
| consensus_exact_support0.25-n16 | scheduled_full_bank | capped_n1-n1 |
| consensus_semantic_v4_support0.25_compatoff-n16 | obsolete_malformed_transport_diagnostic | consensus_exact_support0-n16 |
| consensus_semantic_v4_support0.25_compaton-n16 | obsolete_malformed_transport_diagnostic | consensus_exact_support0-n16 |
| editing_round1-n32 | scheduled_full_bank | best_n_exact-n32, pooled_greedy_swap-n32 |
| editing_round2-n32 | scheduled_full_bank | best_n_exact-n32, pooled_greedy_swap-n32 |
| pooled_greedy_swap_then_prune_0.001-n32 | scheduled_full_bank | pooled_greedy_swap-n32 |
| pooled_greedy_swap_random_delete_matched_0.001-n32 | scheduled_full_bank | pooled_greedy_swap-n32 |
| pooled_greedy_swap_then_prune_0.005-n32 | scheduled_full_bank | pooled_greedy_swap-n32 |
| pooled_greedy_swap_random_delete_matched_0.005-n32 | scheduled_full_bank | pooled_greedy_swap-n32 |
| editing_round2_then_prune_0.001-n32 | scheduled_full_bank | editing_round2-n32 |
| editing_round2_random_delete_matched_0.001-n32 | scheduled_full_bank | editing_round2-n32 |
| editing_round2_then_prune_0.005-n32 | scheduled_full_bank | editing_round2-n32 |
| editing_round2_random_delete_matched_0.005-n32 | scheduled_full_bank | editing_round2-n32 |
| pooling_exact_support_lambda0-n16 | exact_alias | pooled_greedy_swap-n16, exact_support_only-n16 |
| pooling_exact_support_lambda0.05-n16 | scheduled_full_bank | pooled_greedy_swap-n16, exact_support_only-n16 |
| pooling_exact_support_lambda0.2-n16 | scheduled_full_bank | pooled_greedy_swap-n16, exact_support_only-n16 |
| exact_support_only-n16 | scheduled_full_bank | capped_n1-n1 |
| consensus_semantic_v5_support0_compatoff_vetooff-n16 | scheduled_full_bank | consensus_exact_support0-n16 |
| consensus_semantic_v5_support0_compatoff_vetoon-n16 | scheduled_full_bank | consensus_exact_support0-n16 |
| consensus_semantic_v5_support0_compaton_vetoon-n16 | scheduled_full_bank | consensus_exact_support0-n16 |
| consensus_semantic_v5_support0.125_compatoff_vetoon-n16 | scheduled_full_bank | consensus_exact_support0-n16 |
| consensus_semantic_v5_support0.125_compaton_vetoon-n16 | scheduled_full_bank | consensus_exact_support0-n16 |
| pooled_specificity_mean-n32 | scheduled_full_bank | pooled_greedy_swap-n32, best_n_specificity_mean-n32 |
| pooled_specificity_mean_then_prune_0.005-n32 | scheduled_full_bank | pooled_specificity_mean-n32 |
| pooled_specificity_mean_random_delete_matched_0.005-n32 | scheduled_full_bank | pooled_specificity_mean-n32 |
| best_n_specificity_mean_abstain_nonpositive-n32 | scheduled_full_bank | best_n_specificity_mean-n32 |
| consensus_semantic_v5_medium_support0_compatoff_vetoon-n16 | scheduled_full_bank | consensus_exact_support0-n16 |
| consensus_semantic_v5_medium_support0_compaton_vetoon-n16 | scheduled_full_bank | consensus_exact_support0-n16 |
| consensus_semantic_v5_medium_support0.125_compatoff_vetoon-n16 | scheduled_full_bank | consensus_exact_support0-n16 |
| consensus_semantic_v5_medium_support0.125_compaton_vetoon-n16 | scheduled_full_bank | consensus_exact_support0-n16 |
| random_complete-n1 | cached_selector_full_bank | capped_n1-n1 |
| random_complete-n2 | cached_selector_full_bank | capped_n1-n1 |
| random_complete-n4 | cached_selector_full_bank | capped_n1-n1 |
| random_complete-n8 | cached_selector_full_bank | capped_n1-n1 |
| prune_loo_a32_0-n32 | cached_selector_full_bank | best_n_exact-n32 |
| random_delete_matched_a32_0-n32 | cached_selector_full_bank | best_n_exact-n32 |
| prune_coefficient_a32_0.01-n32 | cached_selector_full_bank | best_n_exact-n32 |
| prune_coefficient_a32_0.05-n32 | cached_selector_full_bank | best_n_exact-n32 |
| prune_loo_n1_0-n1 | cached_selector_full_bank | capped_n1-n1 |
| random_delete_matched_n1_0-n1 | cached_selector_full_bank | capped_n1-n1 |
| prune_loo_n1_0.001-n1 | cached_selector_full_bank | capped_n1-n1 |
| random_delete_matched_n1_0.001-n1 | cached_selector_full_bank | capped_n1-n1 |
| prune_coefficient_n1_0.01-n1 | cached_selector_full_bank | capped_n1-n1 |
| prune_coefficient_n1_0.05-n1 | cached_selector_full_bank | capped_n1-n1 |

`exact_support_only-n16` and `consensus_exact_support0-n16` are retained named representation/component controls; their historical outputs coincide and must not count as independent algorithms. The support0 selector and support-only sorter use the same whole-source support ranking under the original cap.

Malformed semantic v4 is retained solely as historical evidence; released80 remains a cached numerical diagnostic.
