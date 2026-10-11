# 057 — Expanded N8 likelihood and bounded edit encoding

## Key findings for a new reader

GPU execution is running; no quality result is available. The expansion reuses the original candidate pools and captured activations for all four benchmark families. It scores the first eight candidates against the target activation and exactly the first two existing frozen development controls. True likelihood, control-only likelihood and their difference share this pass. New editor text will use the same frozen reconstructor afterward on the same device.

## Status and question

- **Status:** running likelihood; edit encoding prepared, proposals pending.
- **Created / updated (UTC):** created 2026-10-11 00:23 UTC; updated 00:42 UTC.
- **Experiment / parent / run IDs:** expansion-v1; GPU job 25536297; parent experiment056.
- **Question:** Does target-conditioned likelihood, its matched-control baseline or their difference select better complete readouts across the full bank?
- **Expected failure mode:** fluency or common candidate errors may dominate activation-specific information; likelihood numerical behavior and preemption can also affect implementation.
- **Single change:** extend the recorded N8/two-control method to every existing cell, preserving its score, parser and original candidate ordering.
- **Decision rule:** report official family judgments, declared parent contrasts, whole-group uncertainty and adverse results. All 469 questions are exploratory; runtime checks do not select methods by quality.

## Frozen inputs and procedure

- **Data / scope:** 469 questions, 19,435 fixed activation cells; original four-family grids and source-group boundaries. Sealed `configs/expansion_manifest_v1.json`, SHA256 `753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8`.
- **Target / lens / reconstructor:** Qwen3.6-27B revision `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`; paired release `c95215d5d2f6250f20c305ae55c6e4d7569f92dc`, `olens_s3d_rl600` and `ar_ptag_pooled`.
- **Rendering:** exact `concepts_raw` carrier, injection `16000*h/||h||`, bfloat16 backbone, original tokenizer; full capped candidate text, no EOS, correct next-token shift and padding exclusion.
- **Candidate pool:** original N32 sources in all three stages, SHA256 verified against the seal. Only indices0–7 receive likelihood forwards. No new Oracle Lens generation or independent reader.
- **Controls:** `configs/expansion_likelihood_controls_v1.json`; exact first two original donors for each target, development-only, different related group, same family/layer/read-position-kind. Individual donor scores remain saved.
- **Access boundary:** inference forwards receive candidate text and activation vectors. Original answers, transcripts and judgments do not enter the carrier or editing objective. Original splits remain in likelihood/scorer outputs; this is an exploratory expansion.
- **Selector:** maximum mean candidate-token likelihood, maximum mean control likelihood, and maximum true-minus-mean-control likelihood; ties favor earliest original sample. Existing four-bullet/256-token cap and whole source-bullet parser unchanged.
- **Batching:** fixed same-layer B32 likelihood batches, spanning independent cells; checkpoint up to16 completed cells, including short layer/family boundaries. No per-token checkpoints. Edit encoding uses one reconstructor at a time, mixed independent tags, atomic tensor/index shards and full-text provenance despite the32-token reconstruction span limit.
- **Reconstruction / editing:** unchanged exact joint whitened NNLS FVE; unchanged-parent references and all accepted prior proposals retained. Round2 requires the complete round1 candidate history. At most4 new proposals each bounded round, beam2. Matching checkpoint, vector contract and whitening required.
- **Judge:** root/API stream uses unchanged official GPT-6 Luna family contracts. No quality judging performed by GPU worker.

## Comparisons and measurements

At 00:22:44 UTC, 136/19,435 cells were fsynced after112.76 scoring seconds (0.829 seconds/cell), on early chain-family layers20/24. This is an early operational measurement; it cannot forecast the longer hallucination candidates reliably or establish scientific benefit. The planning reference is5.6 likelihood plus2.2 edit H200 task-hours.

The runtime batch/singleton fixture passed with mean log-likelihood absolute differences0.007305,0.005105,0.003420 nats/token against the0.05 frozen provisional guard. Three causal-alignment tests passed. Four new restart tests passed: incomplete JSONL tail preserved and truncated to its committed prefix; duplicate/incompatible/corrupt completed rows rejected; orphan tensor before index excluded from completed units without overwriting its filename; index without tensor rejected. These are implementation checks, not model-quality evidence.

At approximately 00:39 UTC, arithmetic likelihood coverage completed all 120 questions and 1,320 cells. The automatic CPU publisher returned zero and exposed all three likelihood methods in `expansion-v1/selections/likelihood-v1/chain_intermediates.ready.json`. It verified original activation hashes, splits, exact candidate text and output caps. This is complete operational coverage; it remains unjudged. GPU work then advanced to hallucination. Across the first 1,384 cells, scoring took 1,108.87 seconds, approximately 0.80 seconds per cell.

Five additional enqueue tests passed: fixed complete-family task construction, incomplete/foreign/duplicate family rejection, changed proposal hash rejection, round2 history-completeness gating and historical-output-root rejection. New edit scoring has compiled but awaits real proposals and its numerical runtime fixture; it has not been claimed as experimentally complete.

## Completeness, cost and artifacts

- **Compute:** exactly one newly authorized `${SLURM_PREEMPT_PARTITION}` H200, job25536297, owner${USER} UID${UID}, account`${SLURM_GENERAL_PARTITION}`, QoS`normal`, node4603,8 CPUs,96GiB. Started2026-10-11 00:15:43 UTC; expiry2026-10-11 20:15:43 UTC. Partition preemption modeREQUEUE and jobRequeue1. Historical handed-back allocations and unrelated olta jobs remain untouched.
- **Processes:** persistent dispatcherPID927978; likelihoodPID928640 verified by assigned-device compute-app query. Root's CPU monitor runs independently of GPU lifetime and checks approximately every minute.
- **Automatic CPU bridge:** watcher PID690422 on existing API job25536291, shared affinity core44, records `.state/expanded-gpu-enqueue-v1.state.json`. It is the sole GPU-queue writer, accepts immutable full-family proposal descriptors, publishes each complete likelihood family, and queues the two edit rounds with complete round1 history. It sets the GPU finish flag only after all nine planned tasks have completed. Its stop flag is `.state/expanded-gpu-enqueue-v1.stop`; no additional CPU allocation was requested. The first watcher PID686802 stopped cleanly before its replacement added publishing. An initial launcher failure from a shadowed inaccessible `env` binary was corrected using `/usr/bin/env`.
- **Memory:** assigned H200143,771MiB; before execution0MiB used. Live initial likelihood use~63–66GiB and100% utilization. Base weights reused from existing15 Scratch shards,55.563GB; no download/copy.
- **API:** no API requests from the GPU worker. Dollar usage and reservations are owned by the shared ledger/API stream; not measured here.
- **Storage:** likelihood journal/spec/fixture/status at `${OLENS_DATA_ROOT}/expansion-v1/likelihood-n8-two-controls/`. New editing cache planned at `${OLENS_COMPUTE_ROOT}/vectors/expansion-edits-v1/`. Large outputs stay outside Git. Storage volume unmeasured at this first checkpoint.
- **Reproduction:** `configs/expansion_gpu_likelihood_v1.json`; `scripts/expanded_likelihood.py`; `scripts/expanded_encode_edits.py`; `scripts/expanded_gpu_service.py`; `src/olens_improve/gpu_resume.py`; `.state/expanded-gpu-v1.sbatch`, queue, service receipt and job log. Exact source hashes and batch identities are frozen in the likelihood spec.
- **Bridge reproduction:** `scripts/expanded_gpu_enqueue_edits.py`, `configs/expansion_gpu_enqueue_v1.json`, private `configs/expansion_gpu_runtime_v1.json`, API-produced `.state/expanded-gpu-edit-descriptors/{round}-{family}.json`, and CPU-owned `scripts/export_expanded_likelihood.py`. The private GPU runtime pins the reused base path without pinning root's mutable resource inventory.
- **Resume:** rerun the same task/spec only for missing committed cells. A partial final journal line is saved separately before truncation; indexed finite vector shards imply completion, orphan tensors do not. New vector shard numbering skips orphan filenames. No GPU replacement is requested automatically.
- **Remaining:** finish likelihood, encode and score family edit snapshots in round order as available, expose complete-family method outputs to official judging, reconcile actual GPU task/allocation hours and output volume. Time-limited or interrupted work remains explicitly incomplete.

## Inspection evidence and interpretation

No scientific wins, regressions or unchanged examples inspected. These belong to the declared systematic root review after official judgments. Operational progress is not a quality conclusion.

## Validation and test access ledger

| Timestamp | Split / manifest | Process | Outputs inspected | Purpose / resulting decision |
|---|---|---|---|---|
| 2026-10-11 00:15–00:23 UTC | Sealed exploratory full469 | GPU worker | Counts, source hashes, tensor boundaries, runtime fixture and resource/throughput receipts | Validate fixed implementation and start authorized scoring; no method tuning from quality |
