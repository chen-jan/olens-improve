"""Apply the skeptic re-check corrections to entropy/entropy_page.json (idempotent: starts from the .bak).

Run after recheck.py, probe2-5.py, lens_check.py and mc.py. Rerunning analysis.py overwrites
entropy_page.json, so rerun this afterwards.
"""
import json
import os

ENT = "${OLENS_SCRATCH}/olens-bullet-fve/entropy"
SK = f"{ENT}/skeptic"
src = f"{ENT}/entropy_page.json.bak" if os.path.exists(f"{ENT}/entropy_page.json.bak") else f"{ENT}/entropy_page.json"
P = json.load(open(src))
R = json.load(open(f"{SK}/recheck_results.json"))
Q = json.load(open(f"{SK}/probe2_results.json"))
LS = json.load(open(f"{SK}/lens_summary.json"))
MC = json.load(open(f"{SK}/mc_results.json"))


def bc(d, d_=3):
    if d is None:
        return None
    return {"b": round(d["b"], d_), "ci": [round(d["ci"][0], d_), round(d["ci"][1], d_)], "p": round(d["p"], 4)}


P["headline"] = [
    "Buffer prediction: lower FVE at low-entropy sites, more so at deeper layers. Observed: with the entropy rank, FVE "
    "barely moves (lowest- vs highest-entropy site differs by about 0.01 FVE, CI includes 0), against a 0.25 rise across "
    "layers. Ranking sites by 1 - p(top-1) from the same lens instead gives a small buffer-direction slope (about +0.03, "
    "p < 0.01; +0.035 with continuation-ness controlled). So any buffer effect is at most about 0.03 FVE, and its sign "
    "depends on the proxy. There is no sign that it grows with depth: a linear entropy x layer trend is not significant.",
    "The only buffer-like dip is at near-deterministic sites (H < 0.1 nats, 85 of 1,123): about 0.03 lower FVE. It sits "
    "partly at about 10 block boundaries (a full stop before a paragraph break, the end of the reply). Where the next "
    "token is a word, the binary dip is about 0, though the continuous 1 - p(top-1) slope remains (+0.03). The "
    "lowest-decile dip is p = 0.08 after Bonferroni over 10 deciles.",
    "Readouts match the actual continuation more often at low entropy (NEXT share 51% in the lowest-entropy fifth vs 36% "
    "in the highest at L60, Original). This is expected for any continuation-writer where the text is predictable, so "
    "it is not evidence against the buffer. Controlling for the lens's own next-word correctness shrinks it to -0.060 "
    "[-0.120, 0.001]. About 90% of bullets are continuation-shaped at every entropy level. Meta-regex hits are 1.3-1.7% "
    "in the two lowest fifths vs 0.4% in the highest: a slight lean toward the buffer, not significant, mostly persona speech.",
    "Sentence ends are high-entropy sites (mean 2.26 nats; full stops 2.44; also higher surprisal and lower lens accuracy) "
    "yet have the lowest FVE. Adding entropy to the model leaves the sentence gap unchanged (-0.045 to -0.046). This "
    "survives multiple-comparison correction.",
    "Entropy does not predict hallucination. The surprisal of the actual next token does predict FVE (+0.05 to +0.06; "
    "survives Holm), but about a quarter of it is tokenisation (lens top-1 is the right word in another token): with "
    "exact and tolerant correctness controlled it is +0.043 [0.007, 0.078], and it is absent at clause sites.",
]
P["about"] += (" [Re-check 2026-10-15: headline revised. The meta-share prediction is b < 0 (more meta at low entropy); "
               "the observed b = -0.006 leans toward the buffer, n.s. See skeptic_recheck.]")
P["skeptic_recheck"] = {
    "note": "Independent re-run (entropy/skeptic/). CR1 cluster-robust SEs by chat; b = slope on the percentile rank "
            "of the proxy (high minus low uncertainty); p from CR1. All headline numbers reproduce to within 0.001.",
    "lens_calibration_L60": {
        "top1_exact": LS["L60"]["top1_exact"], "top1_tolerant": LS["L60"]["top1_tolerant"],
        "ECE_exact": LS["L60"]["ECE_exact"], "ECE_tolerant": LS["L60"]["ECE_tolerant"],
        "by_H_quintile_mean_surprisal": [q["mean_surp"] for q in LS["L60"]["by_H_quintile"]],
        "by_H_quintile_acc_tolerant": [q["acc_tol"] for q in LS["L60"]["by_H_quintile"]],
        "p1_ge_0.99_acc_exact": LS["L60"]["by_p1_bin"][5]["acc_exact"],
        "spearman_H_between_layers": LS["spearman_H_between_layers"],
        "top1_exact_by_layer": {L: LS[L]["top1_exact"] for L in ["L20", "L36", "L44", "L52", "L60"]},
    },
    "fve_by_proxy_pooled_original": {
        "H60_rank": bc(R["fve_pooled|Original"]),
        "one_minus_p1_rank": bc(R["fve_pooled_proxy_p1|Original"]),
        "H60_token_merged": bc(R["fve_pooled_proxy_Hm60|Original"]),
        "H60_nonCJK": bc(R["fve_pooled_proxy_Hn60|Original"]),
        "H52_rank": bc(R["fve_pooled_proxy_H52|Original"]),
        "H44_rank": bc(R["fve_pooled_proxy_Hl44|Original"]),
        "H36_rank": bc(R["fve_pooled_proxy_Hl36|Original"]),
        "H20_rank": bc(R["fve_pooled_proxy_Hl20|Original"]),
        "H60_rank_lens_correct_sites_only": bc(R["fve_pooled_tolcorrect_only|Original"]),
        "logH_per_SD": bc(Q["logH_perSD_pooled|Original"]),
    },
    "one_minus_p1_direct_effect_with_NEXT": {
        sh: {"all": bc(Q[f"p1_direct_NEXT_all|{sh}"]), "no_boundary": bc(Q[f"p1_direct_NEXT_noboundary|{sh}"]),
             "next_is_word": bc(Q[f"p1_direct_NEXT_nextword|{sh}"])} for sh in ["Original", "Best of 32", "Combine 32"]},
    "depth_trend_linear_per_16_layers": {sh: bc(R[f"fve_H_x_layer_trend(per 16 layers)|{sh}"])
                                         for sh in ["Original", "Best of 32", "Combine 32"]},
    "decile_D1_bonferroni_p": {sh: round(min(1, Q[f"decile_p|{sh}"]["p"][0] * 10), 3) for sh in ["Original", "Best of 32"]},
    "confounds_fve_pooled_original": {k: bc(R[f"{k}|Original"]) for k in [
        "fve_pooled_src_dailydialog", "fve_pooled_src_lmsys", "fve_pooled_nocode", "fve_pooled_code",
        "fve_pooled_chatXkind_FE", "fve_pooled_chatXlayer_FE", "fve_pooled_plus_readtoken_dummies",
        "fve_pooled_plus_logtokindex", "fve_pooled_mid80", "fve_H_x_logresplen", "fve_pooled_plus_nexttype"]},
    "per_kind_fve_slope_original": {kn: {"all": bc(R[f"fve_pooled_kind_{kn}|Original"]),
                                         "no_boundary": bc(R[f"fve_pooled_kind_{kn}_noboundary|Original"])}
                                    for kn in ["clause", "sentence", "markup", "newline"]},
    "NEXT_trend_checks_original": {
        "baseline": bc(R["NEXT_pooled|Original"]),
        "plus_lens_next_word_correct": bc(Q["NEXT_H_plus_tolok|Original"]),
        "chatXkind_FE": bc(R["NEXT_pooled_chatXkind_FE|Original"]),
        "ctrl_bullet_len_NA_CJK": bc(R["NEXT_pooled_ctrl_len_na_cjk|Original"]),
        "nocode_words_after_ge40": bc(R["NEXT_pooled_nocode_wa40|Original"]),
        "src_dailydialog": bc(R["NEXT_pooled_src_dailydialog|Original"]),
        "src_lmsys": bc(R["NEXT_pooled_src_lmsys|Original"]),
        "cont_excess": bc(R["cex_pooled|Original"]),
    },
    "meta_share": {"by_quintile_original": [0.0133, 0.017, 0.0102, 0.0078, 0.004],
                   "b": bc(Q["meta_pooled|Original"]),
                   "buffer_predicts": "b < 0 (more meta at low entropy); page originally said b > 0",
                   "note": "flagged low-entropy bullets are mostly persona speech, e.g. chat-dailydialog-0034.L60.p65"},
    "bullet_level_AR_NEXT_premium": {sh: {"within_readout_solo_fve_NEXT_minus_other": bc(R[f"solo_fve_NEXT_minus_other_within_readout|{sh}"]),
                                          "premium_x_entropy": bc(R[f"solo_fve_NEXT_premium_x_H_within_readout|{sh}"])}
                                     for sh in ["Original", "Best of 32"]},
    "surprisal_artifact": {sh: {"baseline": bc(R[f"surprisal_fve_pooled|{sh}"]),
                                "ctrl_exact_tolerant_nexttype": bc(Q[f"surp_plus_exact_and_tol|{sh}"]),
                                "clause_sites": bc(Q[f"surp_kind_clause|{sh}"]),
                                "markup_sites": bc(Q[f"surp_kind_markup|{sh}"])} for sh in ["Original", "Best of 32"]},
    "surprisal_tokenisation_sites_L60": {"n_exact_wrong_tolerant_right": 177, "fve_original": 0.542,
                                         "fve_original_exact_right_sites": 0.424},
    "multiple_comparisons": {"n_estimates_with_ci_in_analysis_results": MC["n_tests"],
                             "n_ci_excluding_0": MC["n_ci_excl_0"], "n_BH_q_lt_0.05": MC["n_BH"],
                             "n_Holm_lt_0.05": MC["n_Holm"],
                             "cited_claims": {k: {"q_BH": round(v["q_BH"], 3), "p_Holm": round(v["p_Holm"], 3)}
                                              for k, v in MC["claims"].items()}},
    "what_survives": (
        "No test finds the large, depth-growing FVE deficit at low-entropy positions that the text-buffer idea "
        "predicts. Any buffer-direction effect is at most about 0.03 FVE (an eighth of the layer effect). It is "
        "concentrated at the most confident ~7% of sites and partly at paragraph breaks and reply ends, and its sign "
        "depends on how lens confidence is summarised. Readouts are about 90% continuation-shaped at every entropy "
        "level with essentially no planning content, but a lens RL-trained on this FVE would write continuation "
        "regardless. The sentence-end FVE gap and the absence of an entropy-hallucination link are robust."),
}
json.dump(P, open(f"{ENT}/entropy_page.json", "w"), separators=(",", ":"), ensure_ascii=False)
print("patched", len(json.dumps(P)))
