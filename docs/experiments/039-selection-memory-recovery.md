# 039 — Resume selection after a memory failure

**Status:** recovery complete, 2026-10-10 14:26 UTC. This is an operational change; no TEST quality result has been inspected.

The four fixed TEST selector processes shared an 80-GiB CPU allocation. A resource observation at 14:16 found allocation-limit pressure and major page faults. Shard 1 then exited with an explicit Slurm out-of-memory event. Its last status recorded 2,213 of 2,679 cells. The other three workers remained alive. The failed execution is retained; its status file alone is not terminal evidence.

The resource receipt is `diagnostics/test-selector-resource-v1/1415.json`, SHA256 `0032f916f647dc38285a73f2d7d435bc4d78f88f20c125fd93cd8a44f07eac20`, under the durable project directory. Root session 80533 exited 1 with the OOM message. Allocation memory at the subsequent observation was 64.11 GB, with an 85.90-GB peak; each surviving process held approximately 21 GB RSS. This explains a material throughput limitation, although the observation does not attribute every earlier delay to memory.

Root resumed only shard 1 using the existing `compare_selectors.py` recovery path on idle CPU capacity in the already authorized job 25417596, node3200. It uses a 40-GiB step, physical CPUs 24/26/28/30 and four numerical threads. The other workers continue on their original allocation. No additional GPU or paid model call was requested.

The original v1 manifest and gate, frozen sample file, vector catalog, controls, whitening, selector source, thresholds and output directory are unchanged. The script checks exact configuration equality and every saved row's configuration identity, then skips completed cells. A truncated or invalid saved row must fail rather than be silently dropped. The restart is root session 47746; the restart successfully validated the existing configuration and saved rows, then continued at cell 2,214. At the 14:22 check it had reached 2,463 cells; terminal completeness still requires confirmation. CPU placement changes, while scientific settings and saved outputs are preserved.

After all four shards finish successfully, merge using the original v1 producer manifest. The prospective twelve-condition amendment in experiment 038 governs subsequent combination, export and judging. Record actual terminal counts and hashes before that handoff. This recovery provides no evidence about method quality and cannot change the method selection.

At the terminal check, every successful selector invocation exited 0, with counts 2,679 / 2,679 / 2,678 / 2,678 = 10,714. The resumed shard took 310.34 seconds for its new invocation; this excludes its failed first attempt and must not replace total campaign cost. No saved row was discarded or recomputed by the resume path.
