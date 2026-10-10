# 031: Inference cost evidence for the fixed validation methods

Draft for coordinator review. This record inspects only method definitions and existing DEV/VAL engineering counters. It opens no validation verdicts, test content or selected explanations, and launches no model or API work. Quality remains the priority; a cheaper method is not automatically preferable.

The optional [cost rows](../../configs/cost_rows_validation_v1.draft.json) preserve the exact twelve-method order from [the frozen menu](../../configs/conditions_validation_v1.json). Every row separates new-input inference, shared campaign work, replay of saved candidates/vectors, and benchmark judging. The attachment schema and all referenced file hashes were checked; the draft has not been attached to a dashboard or approved as final reporting.

“Specified” denotes an algorithmic workload or bound, not a timing measurement. “Measured” denotes the stated instrument/cohort. Transferring its average to a new input is “estimated.” Unavailable quantities remain “missing,” including GPU dollars and exact per-method end-to-end latency.

For a new reader, the main effort differences are:

| Approach | Required candidate work | Additional inference work |
| --- | --- | --- |
| Original or capped single response | One sampled response | Text handling and output caps; no required reconstruction encoding |
| Best reconstruction | Sixteen or thirty-two responses | Encode source bullets and fit complete responses |
| Pool complementary bullets | Sixteen or thirty-two responses | Same encodings plus a larger numerical combination search |
| Select by specificity | Thirty-two responses | Same encodings, with candidate fits against fixed matched controls |
| Prune a selected response | Its parent's thirty-two responses | Inherit parent generation/scoring and add subset refits; no extra model vectors or helper calls |
| Random controls | The recorded thirty-two-response pool or the parent method | Eligibility or matched deletion-count work; not a guaranteed one-draw deployment cost |

All twelve methods have zero recurring helper calls. Their common model work is not free when research caches are reused, and the combined methods retain their parent effort. The small generation-prefix estimates below are **amortized filled-batch work estimates, not single-input latency**. Exact per-method fresh latency remains missing. Source IDs and detailed evidence follow; they are not the main cost conclusion.

| Exact condition | Candidate prefix in this experiment | AR work required by the method | Numeric selection work | Existing cached CPU timing |
| --- | ---: | --- | --- | ---: |
| `raw_n1-n1` | 1 | None | Preserve original text | Missing |
| `capped_n1-n1` | 1 | None | Parse and cap complete source bullets | Missing |
| `best_n_exact-n16` | 16 | Up to 64 source bullets before cleanup/deduplication | Rank complete responses by exact joint fit | 0.00690 s/cell |
| `best_n_exact-n32` | 32 | Up to 128 source bullets | Rank complete responses by exact joint fit | 0.01122 s/cell |
| `random_complete-n32` | 32, same recorded pool | None required for selection | Uniform draw among parsing/length-eligible responses | Missing |
| `pooled_greedy_swap-n16` | 16 | Up to 64 source bullets | Fully refitted greedy additions, one swap pass, complete-parent fallback | Missing |
| `pooled_greedy_swap-n32` | 32 | Up to 128 source bullets | Same pooled search at the larger prefix | 0.23227 s/cell |
| `best_n_specificity_mean-n32` | 32 | Up to 128 source bullets, reused across controls | Fit each eligible complete response to its target and up to eight fixed control activations | 0.05908 s/cell |
| `best_n_specificity_mean_then_prune_0.005-n32` | 32 | Same parent encodings; zero additional vectors | Specificity parent followed by sequential leave-one-out refits | Missing for the exact combination |
| `best_n_specificity_mean_random_delete_matched_0.005-n32` | 32 | Same parent encodings; zero additional vectors | Compute the parent's pruning deletion count, then matched random deletion | Missing for the exact control |
| `prune_loo_a32_0.005-n32` | 32 | Same A32 encodings; zero additional vectors | A32 parent followed by sequential leave-one-out refits | 0.01232 s/cell, including A32 |
| `random_delete_matched_a32_0.005-n32` | 32 | Same A32 encodings; zero additional vectors | Compute A32 pruning deletion count, then matched random deletion | Missing for the exact control |

All twelve methods use **zero recurring helper/editor calls**. Benchmark Luna requests are a separate expense. The AR bounds describe at most four parsed bullets per sample; actual effective inputs can be fewer because of cleanup, eligibility and deduplication. The fixed control bank requests eight controls, but bank sizes vary. It reuses control activations and the same phrase encodings rather than generating another candidate pool per control.

The random control's N32 is its actual experimental prefix. A deployed random baseline can retain one admissible draw, but matching eligibility may require rejection/resampling. Neither one draw nor N32 is a universal measured deployment cost for that alternative. The draft therefore supplies no generation-time estimate for its eligibility-matched deployed form.

The cached timing column is measured on eight fixed DEV cells with three repetitions and four Torch threads, after parsing/vector preparation. It is **task wall time on CPU**, not summed process CPU time or complete new-input latency. That instrument recorded 16/32 distinct objective fits for A16/A32, 36–42 for A32 with pruning, 778–911 for D32, and 288 for E1 with eight controls. These observed counts are not guarantees on a new input. Final fit diagnostics, compatibility ablations and the forty-method sweep can add research work absent from a minimal deployed selector.

Matched deletion controls inherit the computation needed to establish the pruning deletion count. Treating their cost as a random draw alone would omit part of the frozen procedure. Both combined pruning methods inherit their parent's sampling, AR encoding and, for specificity, matched-control scoring. Pruning adds no new model encodings or helper calls, but it adds numerical subset fits. The published stage timers cover multiple outputs and cannot establish isolated combination latency by dividing by the number of arms.

The historical DEV pilot provides filled-batch generation components of 4.6811 GPU task-seconds per N32 cell. N16 and N1 proportional estimates are 2.3405 and 0.1463 seconds of **amortized batch work**, not measured prefix-serving or single-input latency. Historical B32 AR averaged 1.7140 GPU task-seconds and 125.66 unique inputs per N32 cell. The draft uses these only as explicitly transferred amortized work estimates, with proportional N16 scaling. New-input capture, startup, batch occupancy, text lengths and cache sharing can change them; the later B128 implementation is not declared numerically or operationally equivalent to B32. Capture is one forward per input item and can share all requested layer/position cells from that item. Do not charge a separate capture for every cell or add these component averages to cached CPU timers and label the sum end-to-end latency.

Measured VAL campaign counters give a separate, more current execution view:

| Shared engineering component | Observed workload | Recorded time and interpretation |
| --- | --- | --- |
| Candidate pool | 3,485 cells × 32 samples = 111,520 samples | Terminal statuses prove coverage; this draft does not reconstruct a generation timer from candidate journals |
| New AR cache | 421,716 effective vectors on four H200 workers, B128 | 4,426.008 summed GPU task-seconds; longest worker 1,129.482 seconds, not a synchronized makespan |
| Base selector sweep | Four four-thread CPU workers, 3,485 cells, all forty outputs | Longest worker 607.678 task wall-seconds, including preparation; not one method's latency |
| E1 pruning stage | 3,485 cells, four new pruning/control outputs and unchanged parent | 180.867 task wall-seconds on CPU with four threads; not five separately measured deployment timers |

These campaign quantities are shared **once across the campaign**, not charged once per arm or additive across methods. The AR cache also inherits earlier DEV vectors; the new-vector count does not erase their research cost. Raw/capped/random selection does not require AR merely because this comparison campaign computed it. CPU task wall-seconds are elapsed task time with the stated threads, not CPU-core-seconds; parent timers nested inside broader stage timers must not be added again. Per-condition settled Luna usage and uncertain holds are still missing from this cost draft; the evaluator should supply them after reconciliation. They belong in benchmark judging, never in recurring method inference.

The independent cold N2 engineering smoke measured 155.817 seconds including separate capture/loading, generation, AR selection and cache replay. It used a synthetic prompt and eight new vectors. Its 7.043-second replay was not fresh inference, and its overall runtime is not evidence for any exact N16/N32 condition here. Preserve it as an engineering check rather than substituting it for missing deployment timings.

Evidence paths and SHA-256 identities are in the draft's `source_index`: immutable `diagnostics/costs-v3/components.json`; VAL `ar-workers-terminal-v1.json`; four terminal selector statuses; E1 pruning status; the fixed menu/project/control definitions; and the source selection/pruning/parser files. Source fields are explicit in each nonmissing component. The review must check field meaning, estimate assumptions and scope as well as byte identity. No invoice reconciliation, charged GPU rate, new-input numerical fit timer for every combination, or final twelve-method benchmark charge allocation is available at this checkpoint.
