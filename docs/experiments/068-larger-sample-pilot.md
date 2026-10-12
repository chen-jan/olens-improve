# Experiment 068 — More than 32 samples: speed and a small reconstruction pilot

## Status and question

**Completed, 2026-10-12.** The user reopened the historical 32-sample ceiling and authorized H200 and preemptable resources to check whether 64, 128 or 256 samples are practical. This run extends only **32 development activation sites**, eight per family. A full-bank extension has not been launched. This is a speed and per-site reconstruction diagnostic, not a new whole-question WorkspaceBench result.

The four families are **Hallucination (chat)**, **Multihop (multi-token)**, **Chained intermediates**, and **Role-bound association**. The original released Oracle Lens remains the underlying generator. Best-of-N chooses one complete eligible readout with the highest reconstruction score; it does not concatenate the N readouts.

## Frozen procedure

- Manifest: [larger_n_pilot_batch256_v2.json](../../configs/larger_n_pilot_batch256_v2.json), SHA256 `d8f2f0ee8f07397cd7fc9147e7fcf34d6f5a48939b939c9593ad46733e042af8`.
- Parent speed-test manifest: [larger_n_pilot_v1.json](../../configs/larger_n_pilot_v1.json), SHA256 `0339a43e16b0607617afe2fab917703fd152f984a0fa3903732b410a36155efc`.
- Selection of sites used development metadata and a seeded order, not outcomes: four sites per family at each of layers 36 and 52. Chained intermediates has seven available development groups, so one group occurs at both layers. These sites do not constitute the original question-level read plans.
- Preserve the original first 32 samples byte-for-byte as parsed records; append 224 samples per site. Total new readouts: **7,168**. Write complete N64, N128 and N256 snapshots and resume from committed batches.
- Keep the frozen Qwen3.6-27B and matched Oracle Lens/AR revisions, concepts prompt, activation scale 16000, temperature 1, top-p .95, top-k 64 and maximum 256 generated tokens. Source activations and model weights remain unchanged.
- Each generation batch holds eight same-layer sites and 32 samples per site, or 256 sequences. Batch size was chosen using synthetic speed tests before new real-site outputs. This changes RNG batching relative to the historical collection; the new seeds and exact outputs are retained.
- Reconstruction uses the existing whitening, centering, regularized nonnegative fit and exact solver. Keep AR batch 128. Replay N32 against saved historical selections before interpreting larger-N differences. Final readouts retain at most four complete bullets and 256 text tokens.
- Selection sees the current activation and its own candidates only. No control activations, answer labels, independent reader or text editing is added.

## Measured speed

Single synthetic timed generation case per batch size, after two warmups:

| Sequences per batch | Seconds | Output tokens/second | Readouts/second | Peak allocated GB |
|---|---:|---:|---:|---:|
| 128 | 19.75 | 670.97 | 6.48 | 78.34 |
| 256 | 32.47 | 798.30 | 7.88 | 102.84 |

The larger batch raised output-token throughput by **19.0%**. This is aggregate per-GPU throughput, not the speed of each sequence. The first real-site batch took 41.15 seconds for 256 readouts and 26,436 generated tokens: **6.22 readouts/second and 642.4 tokens/second**.

The completed real generation run supersedes that first-batch rate: **7,168 new readouts and 725,236 output tokens in 897.09 generation seconds**, or **7.99 readouts/second and 808.43 output tokens/second**. Including model startup and snapshot work, the generation step took **917.54 seconds (15.29 minutes)**. Peak allocated memory was **102.85 GB**. This measures the present implementation, not the maximum possible hardware throughput.

The AR profile used 1,024 real baseline bullet inputs, two passes per batch size: batch 128 **99.14 vectors/second**, batch 256 **101.71**, batch 512 **102.81**. The small throughput gain does not justify changing the scorer's batch setting; raw vectors also changed numerically (median relative L2 about 1.5–1.6%, maximum about 5.5–5.7% versus batch 128). These are vector differences, not measured quality changes.

## Forecast, not a full-bank run

The existing four-family bank has **19,435 sites**. The old N32 collection recorded 23.407978 generation task-hours and 6.784023 AR task-hours; see [experiment 054](054-final-resources.md). New-generation speed varies with readout length. The initial planning range below uses synthetic and first real-site rates plus historical AR work; it is not a guaranteed completion time.

| Final N | Extra samples beyond saved N32 | Additional H200 task-hours | Wall time, four available H200s | Wall time, eight available H200s |
|---|---:|---:|---:|---:|
| 64 | 621,920 | 29–35 | 8–10 hours | 4–5 hours |
| 128 | 1,865,760 | 86–104 | 22–28 hours | 11–14 hours |
| 256 | 4,353,440 | 201–243 | 2–3 days | 26–33 hours |

Times include generation and AR work but exclude queue delays, preemption, final judging and substantial extra analysis. Eight-GPU estimates assume all four preemptable GPUs stay available. These are cumulative extensions from saved N32, not costs to add together. No verified cluster dollar rate is available, so GPU-hours are not converted into invented dollar charges.

With the completed real-pilot generation rate, the arithmetic estimates before contingency are **28.40, 85.21 and 198.83 H200 task-hours** for N64, N128 and N256. The earlier planning ranges allow overhead and workload variation. The pilot weights each family equally and uses two layers; the full bank has different family and layer proportions. Formula, source hashes and limits are in [the timing receipt](../reviews/larger-n-timing-v1.json).

The original 20–30 minute pilot forecast was met: **21 minutes 10 seconds** from generation start to final scoring completion, or **23 minutes 13 seconds** including the two speed tests. The six completed one-GPU steps total **0.461944 H200-hours**, including profiles and intermediate-prefix rescoring; the pilot without profiles totals **0.410556 H200-hours**. It used existing user allocations **25637237** (generation) and **25637240** (scoring); their full allocation age is not this experiment's compute cost. Requested preemptable job **25681811** was canceled while pending once the idle existing GPUs were verified. Both user allocations remain intact and our model steps have finished.

## Artifacts, cost and interpretation

All **32/32 historical N32 selections and scores replayed successfully**. The final common-cache results are:

| Candidate count | Mean reconstruction FVE | Gain over N32 | Changed readouts versus N32 |
|---|---:|---:|---:|
| 32 | 30.8563% | — | 0/32 |
| 64 | 31.7763% | +0.9200 points | 14/32 |
| 128 | 32.1015% | +1.2452 points | 21/32 |
| 256 | 32.4544% | +1.5981 points | 27/32 |

The successive gains are 0.9200, 0.3252 and 0.3530 points. This is descriptive reconstruction evidence; the sparse pilot has no official whole-question accuracy result. Mean selected output length is 98.4, 97.1, 98.1 and 99.5 Qwen tokens respectively. Every selected output has four bullets. The [PNG](../figures/068-larger-sample-reconstruction.png) and [CSV](../reviews/larger-n-reconstruction-v1.csv) use the final common vector cache for all prefixes, without attaching inferential confidence intervals to these 32 sites.

The qualitative review finds both possible improvements and continued errors. At N256, a multihop readout restores “Stanford Linear Accelerator Center,” and one chained-intermediate readout recovers `floor(6/2)=3`. Elsewhere, high-scoring outputs retain incorrect arithmetic, generic story-summary instructions instead of the requested relationship, or confused identities. Some exact answer hits coexist with missing bridge concepts or unrelated derivations. These observations do not establish official benchmark success or failure, and no new Luna judgments were requested.

A [prefix cache audit](../reviews/larger-n-prefix-cache-audit-v1.json) found identical N1–N64 selected texts and IDs in the N64 and N128 scoring runs. Maximum N64 FVE drift was 9.7e-9. The last partial AR batch can change raw vectors numerically; retain the final common-cache curve as authoritative. A [qualitative review](../reviews/larger-n-pilot-qualitative-v1.json) preserves the raw released reference and exact selected texts, distinguishes answer hits from correct derivations, and records both improvements and regressions without labeling these observations official benchmark scores.

Durable outputs: `${OLENS_DATA_ROOT}/larger-n-pilot-v1/`, with `batch-profile/`, `ar-profile/`, `sampling/`, separate `score64/`, `score128/`, `score256/` directories, and `analysis/`. The completed scoped snapshot contains **946,761,549 logical bytes (0.947 GB) in 795 files**, excluding shared weights and the local checkout. Existing production vectors are read-only. Each scorer run caps its additional vector cache below 1 GB. No new activation capture or paid judge/helper API call was needed; Codex/subagent billing is separate and not measured here.

The exact-step [timing receipt](../reviews/larger-n-timing-v1.json), [prefix cache check](../reviews/larger-n-prefix-cache-audit-v1.json), and [32-site qualitative review](../reviews/larger-n-pilot-qualitative-v1.json) preserve provenance. One coordinator receipt read briefly failed after the remote scoring process completed, consistent with delayed shared-filesystem visibility; the files then appeared and passed verification, without rerunning GPU work.

Report reconstruction gains separately from correctness. A higher best-of-N FVE is expected by construction on nested eligible samples; it does not establish better hidden-concept recovery or fewer hallucinations. Inspect changed and unchanged readouts with exact original references after scoring. Do not attach official question-level accuracy or misleading confidence intervals to this sparse site sample. Full-bank N64/N128/N256 remains a separate decision informed by measured cost and observed gains.
