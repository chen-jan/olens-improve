# Cluster (HPC cluster)
- Shared node with a small CPU/RAM slice (`systemctl status user-$(id -u).slice`). No heavy compute here: GPU work or anything over a few CPU-minutes goes through `srun`/`sbatch`.
- Check `/etc/motd.d/` for maintenance windows before launching long jobs.

# GPUs
- 4× H200 on `${SLURM_GPU_PARTITION}` (acct `${SLURM_GPU_ACCOUNT}`, 48 h max) + up to 4 on `${SLURM_PREEMPT_PARTITION}`.
- Prefer H200 > H100 > A100 > L40S. Always pin the type: `--gres=gpu:h200:N` (fallback `gpu:h100:N`).
- L40S (48 GB) is a last resort: only if the model fits (bf16 ≈ 2 bytes/param, so ≲ 20B params with headroom), or for non-model work.

# Storage
- Current usage: read `the cluster quota report` (refreshes ~30 min). Never `du`/`find` on `/orcd`; scope any other `find` with `-maxdepth`.
- HOME 200 GB / 1M files: code and configs only. File count is the bottleneck.
- Scratch 1 TB: fast temp/compute. Purged after 6 months idle.
- Pool 1 TB: raw data and durable results.
- Lab compute `${LAB_COMPUTE_ROOT}/`: 20 TB group quota shared with the lab (~4 TB free as of Oct 2026). Use for big activations/caches. `df` shows the whole filesystem, not our quota.
- Big files only via symlinks; never in a repo. Nothing is backed up.
- HF/torch/pip/wandb caches, venvs and conda envs live off HOME.
- Write a few big files, not many small ones. Clean up after runs.
- Stop and ask before writing >500 GB to lab storage.

# Working with the other agent (Claude ↔ Codex)
- Only call the other agent when the user asks ("ask Codex", "get Claude's opinion", "let Codex implement this"). Otherwise work normally.
- If you are Claude, call Codex with `codex exec`. If you are Codex, call Claude with `claude -p`. Details are in your `codex` / `claude` skill.
- Read-only by default (Codex: `-c sandbox_mode="read-only"`; Claude: `--permission-mode plan`). Allow edits only when the user asked for implementation, and never on files you're editing at the same time.
- Give it the question and the file paths, not your own answer.
- Save its session ID and resume by ID, never with `--last`.
- If another agent started you, don't call it back. Say so in your prompt when you call the other agent.

# Project plan and experiment records
- Read [docs/PLAN.md](docs/PLAN.md) before continuing this project; it records the frozen model contract, evaluation stages, budget, and current handoff.
- Record each experiment using [docs/experiments/TEMPLATE.md](docs/experiments/TEMPLATE.md), and update the plan's handoff block after material progress. Preserve the existing historical checkout and results.

# Research display names

Use the pinned WorkspaceBench registry titles on current plots, tables, slides and reports: `hallucination` → **Hallucination (chat)**; `multihop_mt` → **Multihop (multi-token)**; `chain_intermediates` → **Chained intermediates**; `role_bound_association` → **Role-bound association**. Put plain endpoint explanations underneath; keep scientific family IDs unchanged. Always make the original released Oracle Lens reference visible and distinguish it from the four-bullet original and actual-parent comparisons. Preserve historical artifacts and frozen evidence.
