# Working report review

Scope: `docs/REPORT.md`, development-only draft before validation analysis.
Reviewed by the model/scoring and compute/storage agents; synthesized by root.
No validation text, scores, outcomes or examples were used.

## Material issues and applied changes

- State exact SciPy nonnegative least squares separately from the released
  80-step approximate solver. Explain centering/whitening, unit phrase directions
  and retained target magnitude. Applied.
- Disclose the reconstructor's 32-cleaned-token phrase span and the failed
  batch-size equivalence guard. Report shared persisted vectors, observed score
  and selection drift, and lack of certified small-threshold robustness. Applied.
- Keep consensus compatibility checks separate from independent activation-reader
  evidence. J++ supplies bounded token diagnostics, with no established selection
  improvement and unresolved fitting-data overlap. Applied.
- Restrict matched-count random-deletion claims to pruning combinations. Other
  combinations use component-off/objective controls and an abstention diagnostic.
  Applied.
- Describe the donor experiment as reuse of frozen donor readouts, with
  related-group exclusions rather than a guarantee of no semantic overlap.
  Applied.
- Call cached timings elapsed wall time with four CPU threads, rather than
  summed CPU time. Keep batch throughput distinct from serving latency. Applied.
- Name helper effort levels and include the recurring proposal phase in
  medium-effort cost. Applied.
- Clarify that the raw baseline preserves its generation token limit, and that
  installed-wheel replay reuses dependencies and does not validate fresh-input
  end-to-end deployment. Applied.

## Boundaries for later revision

The draft correctly labels incomplete full-development comparisons and unopened
held-out stages. It reports small independent-group counts, mention recovery
versus surrounding-text correctness, and the cross-task nature of tradeoff plots.
Update these claims only from completed, source-bound results. Review held-out
conclusions, final recommendation, plot/table agreement and actual deployment
evidence after those new results exist; repeating the unchanged methods review
is unnecessary.
