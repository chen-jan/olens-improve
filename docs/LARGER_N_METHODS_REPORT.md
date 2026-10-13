# N64 methods on the fixed 32-site pilot

Completed exploratory comparison on eight activation sites per task. These are **site-level results**, not full-grid question success rates. All four tasks use their unchanged evaluators; both hallucination stages are complete.

The original released lens gives 5/8 contradictory specific readouts, 0/8 multihop recoveries, 1/8 chained-intermediate recoveries and 0/8 role-binding recoveries on these sites. Its separate four-bullet reference has the same totals.

Each cell below is the old sample budget → 64. The old budget is 32 except Keep repeats, whose displayed reference used 16. Lower hallucination contradiction counts are better; higher recovery counts are better.

| Method | Hallucination (chat): wrong/specific | Multihop (multi-token): recovered/8 | Chained intermediates: recovered/8 | Role-bound association: recovered/8 |
|---|---:|---:|---:|---:|
| More samples (32 → 64) | 5/8 → 4/8 | 1/8 → 1/8 | 0/8 → 0/8 | 0/8 → 0/8 |
| Remove weak bullets (32 → 64) | 6/8 → 7/8 | 1/8 → 1/8 | 0/8 → 0/8 | 0/8 → 0/8 |
| Combine bullets (32 → 64) | 6/8 → 5/8 | 2/8 → 1/8 | 0/8 → 0/8 | 1/8 → 1/8 |
| Combine + prune (32 → 64) | 8/8 → 8/8 | 2/8 → 1/8 | 0/8 → 0/8 | 1/8 → 1/8 |
| Keep repeats (16 → 64) | 1/2 → undefined (0 specific) | 0/8 → 0/8 | 1/8 → 2/8 | 0/8 → 0/8 |
| Edit pooled text (32 → 64) | 6/8 → 5/8 | 2/8 → 1/8 | 0/8 → 0/8 | 1/8 → 1/8 |

At N64, Keep repeats emits no text at all eight hallucination sites and all eight multihop sites; it abstains at 24/32 sites overall. An undefined contradiction rate is not evidence of perfect accuracy. Other methods retain specific assertions on all eight hallucination sites.

Best-of-64 reduces observed contradictions by one readout (5/8 → 4/8); its grouped paired 95% interval is −37.5 to 0 percentage points. With only seven or eight independent groups, unchanged counts and zero-variation intervals do not establish equivalence or generalization.

## AR reconstruction

Mean fraction of variance explained, in percent. Reconstruction is a selection metric, not a correctness score.

| Method | Hallucination (chat) | Multihop (multi-token) | Chained intermediates | Role-bound association |
|---|---:|---:|---:|---:|
| More samples (32 → 64) | 45.63 → 46.40 | 39.30 → 40.10 | 21.18 → 22.63 | 17.32 → 17.98 |
| Remove weak bullets (32 → 64) | 45.58 → 46.33 | 39.13 → 39.94 | 21.09 → 22.62 | 17.15 → 17.75 |
| Combine bullets (32 → 64) | 48.14 → 49.07 | 41.53 → 42.39 | 23.36 → 24.83 | 19.48 → 20.05 |
| Combine + prune (32 → 64) | 48.04 → 48.79 | 41.27 → 42.12 | 23.11 → 24.59 | 19.23 → 19.73 |
| Keep repeats (16 → 64) | unavailable → 0.00 | unavailable → 0.00 | unavailable → 0.77 | unavailable → 8.12 |
| Edit pooled text (32 → 64) | 48.14 → 49.07 | 41.53 → 42.43 | 23.36 → 24.83 | 19.48 → 20.05 |

## Evidence and limits

- Eight-site results have very low precision. The sites were previously inspected; all findings are exploratory.
- The fixed settings were carried forward without searching these outcomes. Original raw N1, capped N1 and actual method parents remain distinct.
- A higher reconstruction score does not imply fewer false claims. Removing entire bullets can change interpretation and judge decisions; measured label changes are not proof of newly introduced factual content.
- False-span tallies and true/unverifiable claim tallies have different segmentation and cannot be read as uniform claim precision.
- All candidates came from the saved pool. Editing added only candidate-only helper calls and AR encodings, with unchanged-parent fallback.

The complete report, source hashes, judgments and paired intervals are preserved under `${OLENS_DATA_ROOT}/larger-n-methods-v1/quality-all`. The companion CSV gives native rates, uncertainty, assertion share, empty outputs and reconstruction for every condition–task pair.
