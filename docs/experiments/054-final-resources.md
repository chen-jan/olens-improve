# Final campaign resources

The paid campaign ended at approximately 22:02 UTC on 2026-10-10. The final usage-derived API estimate is **$36.50759506**, with **$4.8597425 still reserved**, including $4.85435575 in unknown-charge holds. These are separate amounts; the committed total is $41.36733756. No uncertain charge or inactive reservation was released. These figures are not invoice reconciliation and exclude cluster and Codex/subagent billing.

The final scoped inventory at **22:10:53 UTC** contains **98.704 GB and 14,974 files** in the two project-owned storage roots. Reused external base-model weights are excluded. Recorded generation and main activation-reconstructor tasks total **30.192 task-hours**; project-held H200 allocations total **70.220 GPU-hours** through the 18:10:48 UTC user handoff. Task time and reserved wall time measure different things and must not be added together.

## Storage

| Location | Logical GB (decimal) | File-block GB | Files |
|---|---:|---:|---:|
| Fast project tree: `${OLENS_COMPUTE_ROOT}` | 73.132 | 73.155 | 9,919 |
| Durable project tree: `${OLENS_DATA_ROOT}` | 25.572 | 6.200 | 5,055 |
| Combined | **98.704** | **79.355** | **14,974** |

Both counters completed below the 50,000-file traversal limit. The allocated CPU audit used the existing project-only storage counter, excluded symlinks, and deduplicated hardlinks by device/inode. This is a timepoint inventory, not an atomic filesystem snapshot: final figures and reports can still add files. File-block bytes are `stat.st_blocks * 512`, not verified lab quota or reclaimable space. The 500 GB aggregate authorization does not establish available group quota. The HOME checkout is outside these two roots.

The read-only external base-model cache contains **55,562,855,904 weight bytes across 15 shards**. It was reused and is excluded from the project total. The historical external site-packages directory was also reused and was not sized here. Project-owned environments, adapters, whitening files and diagnostics inside the fast root are included. Fast and durable storage remain separate; neither is a backup. The [retention plan](storage-retention-plan.md) identifies canonical stochastic journals, paid evidence, financial holds and vector shards to retain. Nothing was deleted.

## Model work and reserved allocations

| Recorded component | Task-hours | Timer meaning |
|---|---:|---|
| Generation, including original 16 instrument samples once | 23.407978 | Committed sampling-call batches plus adjacent source-record assembly |
| Main reconstructor encoding | 6.784023 | One-GPU task wall timers, including recorded loading and CPU overhead |
| Combined measured components | **30.192000** | Not pure GPU kernel time or complete compute use |

Verified generation coverage is **621,920 samples**: DEV 167,552, VAL 111,520 and TEST 342,848, covering 19,435 cells with 32 samples each. The committed DEV batch timer covers 167,536 samples; the original 16 are added once. Generation timers exclude pre-loop model loading and activation capture. Reconstructor timers already include their recorded loading/CPU overhead; adding nested encoding/loading timers would double count. Capture, abandoned uncommitted work, separate diagnostics, CPU selector work and failed CPU attempts are not fully totaled.

The four original H200 allocations were already held before this project began. Counting only **01:25:36–18:10:48 UTC** gives 16.753333 hours per GPU, or **67.013333 main GPU-hours**. Two additional H200 windows add **3.206508 GPU-hours**:

| Extra allocation | Start UTC | Release UTC | Reserved hours |
|---|---|---|---:|
| 25459615 | 02:23:24 | 03:35:30.026795 | 1.201674 |
| 25460532 | 02:40:24 | 04:40:41.401195 | 2.004834 |

Thus the final project reservation window is **70.219841 GPU-hours**, including idle holds. The earlier **64.772728 GPU-hours** remains a valid dated snapshot through 16:49:05, not the final total. Subsequent user use/reservation after the recorded 18:10:48 handoff is excluded. No new GPU observation was made for this audit. GPU kernel-busy hours, GPU dollar prices and a complete CPU task-hour total are unavailable; the receipt records them as null.

## Financial limits and provenance

| Scope at 22:02:08 UTC | Usage estimate USD | Reserved including unknown USD | Committed USD | Cap USD |
|---|---:|---:|---:|---:|
| Global | 36.50759506 | 4.8597425 | 41.36733756 | 300 hard / 200 target |
| Original full DEV methods run | 7.61822211 | 0.617766375 | 8.235988485 | 20 |
| Final TEST methods run | 19.492558205 | 0.065023625 | 19.55758183 | 40 |

The global snapshot contains 230,375 settled attempts, 559 unknown attempts and one retained inactive reservation. TEST retains 12 unknown attempts and the old reservation. Per-run rows are subsets of the global ledger and must not be added to it. Shared research generation/cache work is not zero-cost fresh-input inference; benchmark judging charges are distinct from recurring deployed helper work.

Immutable final receipt: `${OLENS_DATA_ROOT}/diagnostics/final-resources-v1/receipt.json`, SHA256 `07f91cc0508af646bc8f7670a14e0816157d5621bd638f3e025ccb7b7d0d2ee1`. It preserves exact byte/file counters, allocation-window calculations, timer semantics and source references. Its inputs include:

- Final terminal/accounting receipt `final-dev-hall-batch-v4-accounting-contracts-v1.json`, SHA256 `0918cc9ec390ef0df1a66cac740847eee51a9e77370b5c968306ffaacc907f95`.
- Measured-model-time addendum, SHA256 `74573b5bd712e310035f97f230b757e79ffe28c828fb4e4d2c76d84c3a41a00a`, and generation timings, SHA256 `dce39bc71450839f507fd9b17b5cd243aef6040345a06d61d6076fdb090f544c`.
- Preserved 16:49 allocation receipt, SHA256 `f9b69d2b7ec2d0500e1e809d979c56461653e3640a56e1e34b5f9366710c558a`, and the exact [GPU handoff](../../configs/gpu_handoff_v1.json).

All cited source bytes were checked. This final audit performed no new ledger query, API call, GPU probe, inference, deletion or allocation release. CPU 25508300 remains held until the final figures/deck are complete and root coordinates release.
