# Experiment 063 — Clear graphs and the original Oracle Lens reference

## Key findings

The user requested clear sample-count trends, readable effects for individual interventions, the original released Oracle Lens reference, and official WorkspaceBench names. The dashboard now starts with sample curves and a focused intervention view. Choosing one approach removes the other approaches; hovering previews its result, and each task plot can be enlarged and resized. All 70 settings remain in the detailed comparison.

The four task names are copied from the pinned WorkspaceBench registry: **Hallucination (chat)**, **Multihop (multi-token)**, **Chained intermediates**, and **Role-bound association**. Plain endpoint explanations stay underneath those names. The revised deck explains the seven methods and their settings before presenting results.

## Status, scope and procedure

- Status: complete; public version 18 published at 2026-10-11 12:25:05 UTC.
- Date: 2026-10-11 UTC.
- Parent: completed expanded study, experiment 062.
- Scientific inputs: native final-v1, reconstruction final-v1, frozen manifest and root final review are unchanged. No new samples, fits, judges, model training or paid inference.
- One small additive analysis: 28 direct original-reference paired comparisons for seven fixed reviewed representatives across four full banks. Original per-question observations, group identities, 10,000 shared resamples and seeds are reused.

The frozen native artifact did not contain these seven raw-original contrasts. The supplement reconstructs all 32 relevant absolute endpoints and reproduces their original intervals before calculating paired changes. Every input and implementation hash is checked. It remains a separate post-hoc exploratory supplement with pointwise intervals, no joint adjustment, and no new held-out claim. Existing headline statistics and simultaneous intervals are preserved.

The raw original is the first released readout as emitted; the four-bullet original is the same sample with trailing whole bullets removed. They are explicitly different references. Chained intermediates is 59/120 for raw original and 57/120 for four-bullet original. Original full-prose reconstruction remains unavailable; no raw reconstruction value is inferred from the capped result.

## Observations and interpretation

Reconstruction rises steadily with more samples, while task recovery fluctuates. Direct original-relative pooling recovers seven more Multihop questions and six fewer Chained intermediates questions. More samples alone recover six more Multihop questions and two more Chained intermediates questions at N32, with one fewer Role-bound association question. These are task-specific observations, not a universal winner or a fitted scaling law.

Consensus reduces the specific-readout share from about 99% to 32%, so its lower error rate must be read together with recovery losses. Each comparison names its reference, and the chart reverses error changes so right means better on every task. Method-parent effects remain distinct from original-relative effects. Examples preserve both success and failure interpretations rather than presenting a recovered token as proof of correct prose.

## Checks, artifacts and resources

- Supplement: `docs/reviews/original-reference-comparisons-v1.json`, SHA `079bc1426b89cfb774433032f3144219289d42ade57ae37e0d23eea8f45f1355`. All 28 contrasts have 10,000 defined draws; 32 absolute rows exactly match the final native artifact. Root independently checked all source hashes, counts and effect signs.
- Supplement extraction: 25.75 seconds wall, 2.60 CPU seconds, about 339 MiB peak memory; no inference.
- Dashboard: `durable/expansion-v1/dashboard/clear-v1`; actual 22-view source-bound browser checks passed, including original/capped/parent references, both metrics, filtering, previews, enlarged views and mobile layout. Scientific source objects remained unchanged.
- Deck: `durable/expansion-v1/presentation/clear-v4`; 94 slides, including 27 main slides and the retained comprehensive detail/appendix. All 94 slide layout and PDF-page checks passed; selected main and appendix pages were visually reviewed. Native PowerPoint rendering is unverified.
- Root delivery review: `docs/reviews/clear-presentation-root-review-v1.json`.
- New GPU allocation, judge calls and paid model requests: zero. Historical accounting and all financial holds remain unchanged.

Historical dashboard, report, presentation builds and scientific sources are preserved. Research commits stay local; the existing public Site is updated through its separate authorized source repository.

Publication and selected hosted-asset readback: `docs/reviews/clear-presentation-site-delivery-v1.json` and `docs/reviews/clear-presentation-hosted-assets-v1.json`.
