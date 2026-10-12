# Experiment 067 — Show reconstruction and task performance together

Presentation-only analysis, 2026-10-12. The user requested a PNG showing how increasing the sample count affects reconstruction versus benchmark performance. No inference, judging, bootstrap or new benchmark run was performed.

The figure uses the frozen full-bank native results and matched reconstruction artifact in the current site's downloads. Their manifest and quality-analysis hashes are checked by `scripts/plot_sampling_reconstruction_vs_quality.py`. All 24 best-of-N records have complete reconstruction coverage. Existing grouped pointwise 95% intervals are copied, not recomputed. The four official task names and the separate raw original-lens reference are preserved.

| Task | Reconstruction, N=1 to N=32 | Native endpoint, N=1 to N=32 |
|---|---:|---:|
| Hallucination (chat) | 37.078% → 42.502% | Contradictions 47.568% → 45.822% |
| Multihop (multi-token) | 30.199% → 35.171% | Recovery 34% → 40% |
| Chained intermediates | 17.132% → 23.789% | Recovery 47.500% → 50.833% |
| Role-bound association | 19.325% → 23.077% | Recovery 78% → 77% |

Here N=1 means `best_n_exact-n1`, not the raw released lens or the separate capped-original condition. These differ slightly in some families. Raw-original reconstruction is unavailable; its native task rate is the dashed reference line. The plotted intervals are uncertainty in individual means/rates, not paired-change intervals. No capped-reference interval is relabeled as an exact-N1 interval.

The reconstructor's weights are frozen. Additional candidates increase the selected description's reconstruction score consistently, while task scores are nonmonotonic. Multihop gains largely appear by two samples; Chained intermediates and Role-bound association have their highest observed recovery at four samples. These observed maxima are exploratory, not certified optimal sample counts. Reconstruction and task percentages measure different quantities; equal-size gains are not expected.

An independent Sol 6.1 reviewer checked all values, baseline distinctions and interval availability. Root visually inspected the final PNG; one-decimal axes avoid duplicate rounded tick labels.

Artifacts: [PNG](../../outputs/figures/sampling-reconstruction-vs-quality-v2/sampling-reconstruction-vs-quality.png), [SVG](../../outputs/figures/sampling-reconstruction-vs-quality-v2/sampling-reconstruction-vs-quality.svg), [CSV](../../outputs/figures/sampling-reconstruction-vs-quality-v2/values.csv), [source hashes](../../outputs/figures/sampling-reconstruction-vs-quality-v2/manifest.json). The website and slides were not changed.
