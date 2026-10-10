# Experiment 000: execution resources and runtime

Status: resource validation completed; model loading and scientific evaluation not performed here. Updated 2026-10-10 01:30 UTC. Parent: frozen plan; execution started 01:25:36 UTC.

## Findings

Four existing user-owned allocations each provide one idle NVIDIA H200, 143771 MiB GPU memory, eight CPUs, and 64 GiB host memory. All use `${SLURM_GPU_PARTITION}`, account/QOS `${SLURM_GPU_ACCOUNT}`. GPU status was checked using lightweight `srun --jobid=... --overlap ... --gres=gpu:h200:1 nvidia-smi` steps. No new allocations were requested or existing jobs canceled.

| Job | Node | Expiration UTC | Initial role |
|---|---|---|---|
| 25330001 | node3300 | 2026-10-10 22:23:26 | Available independent worker |
| 25330006 | node3400 | 2026-10-10 22:25:17 | Available independent worker |
| 25330007 | node3301 | 2026-10-10 22:36:16 | Available independent worker |
| 25417596 | node3200 | 2026-10-11 16:27:10 | Model loader/baseline pilot |

The first three expire approximately 21 hours after execution starts: little margin beyond the 20-hour target. Current node3107 is CPU allocation 25299630 (`${SLURM_CPU_PARTITION}`, 32 CPUs/128 GiB), not a GPU node. That allocation expires 2026-10-12 16:33:42 UTC. Heavier CPU work runs inside its Slurm steps.

## Paths, reuse, and environment

Authoritative paths and allocations: [runtime configuration](../../configs/runtime.json). Project-owned fast root `${OLENS_COMPUTE_ROOT}`; durable root `${OLENS_DATA_ROOT}`. Both are writable, directories created without altering historical projects. Aggregate authorization is 500 GB across both. Cached weights are reused read-only, not copied into either project root.

Frozen Qwen revision `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9` is complete by shard-index/file-existence verification: 15 shards, none missing, 55,563,006,400 physical file bytes. This is an existence/size check, not a new full-file checksum audit or model-load validation. Location: `${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`.

Project interpreter `${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python` was created with the existing Python 3.12.13. A `.pth` entry imports existing lens dependencies read-only; PEFT and SciPy were installed only into the new environment. The local package was installed editable. Verified imports: torch 2.13.0, transformers 5.16.1, PEFT 0.21.2, SciPy 1.18.1, NumPy 2.5.2, safetensors 0.8.0, Accelerate 1.14.0, HF hub 1.29.0, OpenAI SDK 3.6.0, pydra-config 0.0.17.post1 (import verified). Model/adapters have not been loaded by this resource experiment. Setup command: `srun --jobid=25299630 --overlap -N1 -n1 -c2 bash infra/bootstrap_runtime.sh`.

## Unresolved checks and supervision

Personal quota snapshot 2026-10-09 21:14 EDT: scratch 841.0/1024.0 GB (183.0 GB remaining), pool 154.3/1024.0 GB, HOME 121.6/200 GB with 814.2K/1M files. These are personal quotas, not lab-group quotas. Actual Pattie group quota remains unresolved: the available quota client reports an unrelated stale NFS mount `${OTHER_DATA_ROOT}`; no filesystem `df` estimate was substituted. Group memberships and write access were verified. Keep initial writes small/reuse weights while resolving group quota before substantial expansion.

Maintenance inspection: `/etc/motd` empty, `/run/motd.d` empty, `/etc/motd.d` contains only cockpit's inactive-message symlink, whose target is unreadable. No maintenance announcement was found in readable provided locations; this does not establish a cluster-wide maintenance guarantee.

Watcher: `/root/compute_storage_audit`, active only while this session runs; one-shot `infra/watch_resources.py` writes atomic latest snapshots and append-only history under the project's fast `watcher/` directory. Checks approximately every ten minutes during active work; persistent manifests support recovery after the session ends. No preemptable jobs requested. Resource watcher does not submit, cancel, or alter allocations.

API calls/spend: none. Scientific improvements: not measured. Decision: proceed with isolated loader/pilot on job25417596 and shared frozen weights; validate throughput before assigning remaining main GPUs or considering preemptable work.
