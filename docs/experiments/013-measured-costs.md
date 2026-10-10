# Measured cost components

Pricing status: the dollar values below are pre-correction derived usage estimates, not invoice charges. The old ledger omitted the cache-write surcharge. Frozen costs-v1 artifacts are preserved; audited repricing will be recorded in a new version. Compute times and scientific labels are unaffected.

These figures separate the 189-cell DEV campaign, a cached CPU selection pass, and the work needed for a new activation. The pilot uses partial grids. GPU dollars are unknown; GPU seconds below mean occupied one-GPU task wall time, including recorded loading and CPU work, rather than pure kernel time.

| Recorded campaign component | Work | Time / concurrency | Helper charge |
|---|---|---|---:|
| Shared N32 candidate pool | 6,048 samples on 189 cells | 882.39 GPU seconds for 6,032 appended samples across four GPUs; the original 16 samples took another 47.85 GPU seconds | $0 |
| Shared AR encoding | 23,750 unique effective inputs, B32 | 323.94 seconds on one H200 | $0 |
| Cached selector sweep | 189 cells × 40 conditions | 130.11 task wall-seconds on CPU, four Torch threads | $0 |
| E3, N8 | 1,512 candidates × own activation and two controls; 4,536 teacher-forced sequences, 449,820 scored candidate tokens | 194.64 seconds on one H200; scoring portion 176.15 seconds, B8 | $0 |
| Semantic B, N16 | 492 physical requests; 862,954 input and 443,058 output tokens, including 112,950 cached input tokens | 728.45 seconds, four request slots and eight queued cells | $0.2976589 |
| F round 1 | 189 helper requests; 99,383 input and 32,238 output tokens; 603 new AR inputs | Helper wall time 88.41 seconds at four slots; AR task 37.58 seconds on one H200 | $0.0260573 |
| F round 2 | 189 helper requests; 100,956 input and 34,415 output tokens; 660 new AR inputs | Helper wall time 93.01 seconds at four slots; AR task 38.10 seconds on one H200 | $0.0273031 |

E3 used 567 production B8 forward calls. Its total task time also includes four fixture forwards (six extra sequence evaluations); the 176.15-second scoring interval starts after that fixture. The table's sequence and token counts describe production scoring only.

B includes 103 paid response-validation failures, 67 retries, and 36 exhausted logical calls. Its v4 semantic grouping audit found false merges, so this instrumentation-limited end-to-end diagnostic does not establish semantic-consensus futility or a validated deployment guarantee. F round 1 had 145 bookkeeping-invalid responses salvaged offline; round 2 had none. Cached input estimates follow the preserved ledger and await audited repricing. They are not assumed free. The two F rounds share four total proposals per round, rather than four proposals per beam.

Cached CPU selection, measured on eight fixed DEV cells with three repetitions and four Torch threads, costs the following median seconds per cell. These timings start after parsing and cached-vector preparation; preparation took 0.056–10.93 seconds per cell in this instrument and is excluded. That spread includes initialization and cache warming, so it is not a stable per-cell serving estimate.

| Selector | Median cached task wall-seconds on CPU / cell, four threads |
|---|---:|
| A8 | 0.00504 |
| A16 | 0.00690 |
| A32 | 0.01122 |
| C32, including A32 parent selection | 0.01232 |
| D32 | 0.23227 |
| E1 mean32 | 0.05908 |

For a new input, all methods first need a frozen-model capture. The full campaign captured 469 items in 469 forwards and retained 19,435 cells; a reliable elapsed-time measurement was not saved. Capture is shared across sites of the same item, but its cost is not zero. The warm, filled-batch N32 sampling rate was 4.68 GPU seconds per cell. Proportional N1/N8/N16 estimates are 0.146/1.170/2.341 GPU seconds per cell; their latency has not been measured, and smaller batches or serial serving may be slower. We do not generate extra timing-only samples under the global 32-sample cap.

| Method | Required work beyond capture and candidate sampling |
|---|---|
| Raw or capped N1 | Formatting and tokenization; no reconstruction encoder required |
| A, C, D | Encode eligible source bullets with AR, whiten them and the target, then perform the relevant CPU selector |
| E1 | The same AR inputs, plus whitening and fitting against frozen matched controls |
| Exact B | Source parsing and distinct-sample voting; AR is required only for a reconstruction-ranked variant |
| Semantic B, N16 | Helper grouping plus any reconstruction ranking specified by the variant; the observed helper mean is $0.001575 per cell |
| E3, N8 | Own and two-control likelihood forwards on each eligible candidate; AR is not required by the likelihood selector |
| F, N32 | The N32 reconstruction-ranked parent, two sequential helper rounds, fresh AR encoding of proposals, and CPU refits; observed helper mean is $0.0002823 per cell |

The shared N32 pilot used 125.66 unique AR inputs and 1.714 AR task seconds per cell on average. Deduplication across the campaign makes these component averages imperfect estimates for new inputs; model startup, control availability, and text lengths also matter. F added 6.68 new AR inputs per cell across both rounds. These figures are component measurements, not measured end-to-end deployment latency. B16, E3 at N8, and D/F at N32 also have different sampling budgets.

Paid external judging, fitting checks, throughput benchmarks, and sensitivity audits belong to campaign cost, not the deployed selection loop. The table does not claim to total all campaign spending or to convert shared caches into free inference. Final quality comparisons must present these distinctions beside their gains.

The compact source-bound record is `durable/diagnostics/costs-v1/components.json`; it records SHA-256 identities of the pilot journals, original instrument run, AR status, selector status, E3 outputs, F statuses, helper-cost ledger export, and cached CPU profile. Preserve this version. Reproduce with `scripts/summarize_costs.py` inside an allocated CPU job, using a new output path rather than replacing costs-v1. The physical helper attempts remain in the source ledger export rather than being duplicated in the dashboard.
