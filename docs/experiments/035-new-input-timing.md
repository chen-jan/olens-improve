# 035: New-input N32 engineering timing

Status: root-reviewed configuration, awaiting an idle original H200 after its TEST AR worker terminates. No timing run has launched. The coordinator owns launch and must verify GPU release first. This experiment evaluates runtime plumbing and effort; it provides no readout-quality evidence and writes no benchmark pool or production vector cache.

Use the unchanged `scripts/deployment_timing.py` (SHA-256 `12a6c6c16dae0b5a34fe0cf360f27497ec241806220d8cbe3ee5bff8744033ed`) with the installed wheel in `fast/packaging/isolated-wheel-v1/venv`. Its sole new input is the fixed library/Nora prompt from experiment 026. Capture one adapter-disabled final-token L44 activation and generate exactly one new N32 pool, seed 20261010, with the existing released decoder. No API calls, benchmark inputs or inherited phrase vectors are used.

## Frozen inputs

- `configs/deployment_timing_profiles_n32_v1.json`: SHA-256 `ede4a5a679dfe400f28ee515130c051c37d03d40ec31baf1d737440f51716673`. Profiles are raw N1, capped N1, best reconstruction of 16, best reconstruction of 32, and mean specificity of 32. They bind final method freeze `3e6d0894179f3d27507425f642d286fd0e36b30181b6cc5cf2be589fad38bf19`.
- `configs/deployment_timing_controls_n32_v1.json`: SHA-256 `5833af7e3bb4efc6d96c6604bbf76bbaa2c126dadbd8620b8314f987c0df3ff4`. Sort eligible DEV hallucination L44 cell IDs, retain the first ID per distinct frozen activation hash, then take eight. These are engineering calibration controls, not scientifically matched controls for the synthetic prompt. The eight vectors repeat two source items and do not represent eight independent groups. Their existing capture cost is excluded.
- Control provenance includes the original bank file SHA `518e1e11df48d172c9e1d78e055af8e6724bd83de3a60b743e2b3c75bc8ac0d7`, augmented metadata SHA `ccca28d80794d4de7e612b3a7b1924a9f1e2a43259e31f3b77841e14a18be520`, fresh reference manifest SHA `5a61cff89aca532f3e022233b6d2d8e12dab0d3a3f4f44085097bc6dc58fc385`, and DEV cohort SHA `dd382ff6e8bc8e70f1d13710e5235efd943537b4936921726b7d59655289ca80`.

The installed `inference.controls` loader read only the eight selected DEV tensor rows (90–94 and 356–358). All were 5,120-dimensional FP32 vectors with exact fresh-reference hashes and eight distinct activation hashes. Verification receipt: `${OLENS_DATA_ROOT}/diagnostics/deployment-timing-controls-v1/verification.json`, SHA-256 `122d6b6366e7f282b5f81f7346dacb5fc14a4e7f5217775a2996f9cd0d89ff65`. It binds the preserved draft config hash `b48fa4778c923e2711a76de60b4ae44e8efce05ff80521d4d81234a608a2a733`; root subsequently added review metadata without changing the eight rows. Installed CLI and inference source bytes matched checkout at verification.

## Prepared command

Run from the project root only after coordinator approval and the selected AR worker's terminal exit and GPU-idle check. This command uses job 25330001 if it is the freed hold; another hold requires its verified physical CPU mask rather than reusing this mask.

```bash
srun --jobid=25330001 --overlap -N1 -n1 -c8 --mem=64G --cpu-bind=none \
  taskset -c 17,19,21,23 /usr/bin/env OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  ${OLENS_COMPUTE_ROOT}/packaging/isolated-wheel-v1/venv/bin/python -I -B \
  scripts/deployment_timing.py \
  --artifacts ${OLENS_COMPUTE_ROOT}/packaging/isolated-wheel-v1/engineering-artifacts.json \
  --cache-contract ${OLENS_COMPUTE_ROOT}/vectors/shared-global-v1/a451cf49d28ac7447722/contract.json \
  --profiles configs/deployment_timing_profiles_n32_v1.json \
  --controls configs/deployment_timing_controls_n32_v1.json \
  --dependency-site ${OLENS_COMPUTE_ROOT}/envs/runtime/lib/python3.12/site-packages \
  --dependency-site ${OLENS_SCRATCH}/workspace/venvs/lens/lib/python3.12/site-packages \
  --output ${OLENS_DATA_ROOT}/engineering/portable-fresh-input-n32-v1
```

## Measurement interpretation

Report the observed lifecycle through the first A32 selection, cold model initialization in this process, warm adapter-off capture, warm N32 generation, fresh AR loading/encoding/whitening/selection, and cached profile replay separately. Cold does not mean flushed OS/filesystem caches or a fresh machine installation. Prefixes 1/2/4/8/16/32 replay the same saved N32 pool: they measure cached selection work, not fresh smaller-N generation latency. Do not linearly scale this N32 timing into an N16 latency claim. Raw/capped N1 replay excludes capture and generation. Specificity replay includes fixed control scoring but excludes donor capture. Parent/child instrumentation timers overlap and must not be summed. No GPU dollar rate is available.

## Operational preparation evidence

TEST freeze/preparation completed separately with 1,294,737 new effective inputs. CPU allocation 25489638 peaked at 15.06 GiB of 80 GiB with `memory.failcnt=0`; the terminal preparation resource receipt is `durable/diagnostics/test-preparation-resource-v1/124303.json`, SHA `f2199b4b7cead4e8a266757b3c18e9143d25caf86d142731d5bd415c13afe91a`.

The 12:53 resource follow-up observed the original AR worker PIDs on holds 25330001 and 25330007 still running, each progressing from 12,288 to 45,056 persisted vectors at about 98 vectors/second over the counter interval. Their nearly 64 GiB charges consisted primarily of about 60.5 GiB hierarchical file cache and 3.1 GiB anonymous RSS, with no swap. Increasing memory fail counters are not OOM-kill counts; no AR process replacement or interrupted progress was observed. No cache clearing, restart or allocation mutation followed this observation. Root owns subsequent encoder milestones; this bounded monitor loop is closed.
