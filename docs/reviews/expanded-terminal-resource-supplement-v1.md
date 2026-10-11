# Terminal allocation and scoped storage supplement

This is a prepared accounting procedure, not final measured quantities. It supplements the unchanged effort exporter; it never updates its API estimates, holds, scientific inputs or operational timers. The first owned H200 interval is already preserved by `.state/gpu-preemption-accounting-v1/receipt.json`, SHA `ff4b40a6a2f3e3ce047d65e83c228a432d7b9f834119561bf5ce6a5333d3ff31`: 00:15:43–03:57:55 UTC, 13,332 allocated seconds (3.703333 H200-hours). The resumed allocation began at 04:01:02 UTC. Its old 232-second snapshot must be replaced by its latest or terminal interval, never added separately.

Capture accounting once all four owned allocations have been released and their terminal rows are visible. Final scientific/effort artifacts can become ready while the allocations are still running; that earlier observation remains a dated partial resource snapshot. Root coordinates release of allocations. This helper submits no jobs, makes no network/API calls, reads no budget database and modifies no service state.

Use a fresh version directory with no existing capture/output, record the UTC capture timestamp, and retain the exact command and stderr alongside the raw capture. `sacct` is a read-only scheduler query; no Slurm step or new allocation is required for this short command. Do not invoke the parser repeatedly while a row is ongoing.

```bash
mkdir .state/resource-terminal-v1
TZ=UTC sacct --duplicates -j 25536297,25536291,25536417,25536927 \
  --starttime=2026-10-11T00:00:00 \
  --format=JobIDRaw,JobName,State,Submit,Eligible,Start,End,ElapsedRaw,AllocTRES,NodeList \
  --parsable2 > .state/resource-terminal-v1/sacct-UTC.txt \
  2> .state/resource-terminal-v1/sacct-stderr.txt
date -u +%Y-%m-%dT%H:%M:%SZ > .state/resource-terminal-v1/captured-UTC.txt
```

Require successful `sacct` exit before parsing. The explicit start date preserves the first interval when the terminal refresh occurs on a later day. Substitute the verified final effort SHA from `analysis/effort-final-v1/receipt.json` and the literal timestamp in the saved capture-time file; placeholders below are intentionally not runnable final authority. An output path must be absent.

```bash
python scripts/build_expansion_resource_supplement.py \
  --sacct .state/resource-terminal-v1/sacct-UTC.txt \
  --captured-utc CAPTURED_UTC_TIMESTAMP \
  --preemption-receipt .state/gpu-preemption-accounting-v1/receipt.json \
  --preemption-receipt-sha256 ff4b40a6a2f3e3ce047d65e83c228a432d7b9f834119561bf5ce6a5333d3ff31 \
  --effort ${OLENS_DATA_ROOT}/expansion-v1/analysis/effort-final-v1/effort.json \
  --effort-sha256 VERIFIED_FINAL_EFFORT_SHA \
  --output .state/resource-terminal-v1/supplement.json
```

Default parsing rejects ongoing allocations and missing owned parents. A deliberately dated partial build may use `--allow-partial` with a separate output version. Parent allocation intervals alone contribute totals; `.batch`, `.extern` and diagnostic/scoring steps are ignored. Duplicate starts, overlapping same-job intervals, inconsistent elapsed time, changed first preemption interval and unexpected resources fail closed. Queue waits and the preemption gap do not contribute allocation hours. Additional natural-preemption intervals are retained if present in the capture. Concurrent CPU/GPU allocation hours are resource quantities, not end-to-end wall latency.

The JSON records source hashes; capture, effort and generation times separately; each parent's original scheduler row and intervals; total H200 allocation-hours and allocated CPU core-hours, including host CPUs in the GPU allocation. It carries the existing effort operational-timer observations and the first committed scoring-loop timer separately. That 13,021.449644-second loop includes CPU work, GPU inference and journal/I/O; it is not a kernel utilization measurement. A dispatcher completed-task timer after resume covers the last successful attempt and cannot recover earlier interrupted work. Actual GPU kernel time and process CPU seconds remain unavailable. No GPU/CPU prices or invoice totals are inferred.

For storage, prepare an explicit JSON of owned project subtrees and separately listed externally reused weights. Example scope (root reviews any additions):

```json
{
  "owned_roots": [
    "${OLENS_DATA_ROOT}/expansion-v1",
    "${OLENS_COMPUTE_ROOT}/vectors/expansion-edits-v1"
  ],
  "externally_reused_artifacts": [
    {
      "path": "${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9",
      "scope": "Externally reused base weights; not expansion-owned storage, not traversed or charged."
    }
  ]
}
```

With `--storage-roots PATH`, the helper reuses `infra/watch_resources.py:project_storage` on these specified subtrees, never follows symlinks, deduplicates device/inode pairs and stops at 50,000 counted files. A hit on the limit is explicitly partial. Only descendants of this project's fast/durable roots are accepted. No shared lab, `/orcd`, HOME, HF-cache or external-weight tree is walked. Run the optional scan only on an existing CPU allocation if it might exceed a few CPU-minutes; it need not delay terminal accounting. The allocation-only parser can run after those allocations finish.

Logical file bytes and `st_blocks × 512` allocated blocks have distinct fields. Neither is a lab quota, peak storage measurement, exclusive experiment ownership claim or whole-project total. The expansion subtree may contain accounting copies of earlier artifacts. Existing owned vector/model caches can be added as separately named project subtrees; shared/reused weights remain separate. Excluded trees and missing scope must stay explicit, and snapshots from different dates are not additive.

Expected final interface is `schema_version:1`, `status:terminal_allocation_supplement`, `parent_allocations_by_job` for exactly the four owned IDs, `total_allocated_H200_hours`, `total_allocated_cpu_core_hours`, distinct `operational_timings_from_effort`, optional `storage`, and `source_sha256`. Final numbers require the terminal refresh and root review.
