# 026: Synthetic fresh-input engineering smoke

Status: prepared, not run. This checks installed-tool plumbing, not readout quality or a scientific method. Every artifact is marked `scientific_results_eligible=false` and excluded from benchmark exports, judging and aggregation. No API calls or training are involved.

The sole input is fixed text: “The library closes at six. Nora returns a borrowed book before walking home.” Capture one adapter-disabled final-token activation at supported layer 44, using the frozen base/pair. Generate exactly two samples, seed 20261010, with the released sampling settings. No benchmark manifest, activation, readout, answer or validation/test filename/content is an input. A caller supplies only explicit local model, adapter, AR and matched-whitener paths. The cache contract is metadata from the verified DEV encoder; no inherited vector data is copied.

`scripts/portable_engineering_smoke.py` requires an allocated GPU and checks that `olens_improve` comes from the installed wheel. Explicit third-party distribution paths do not execute historical environment `.pth` files. The driver releases the capture loader before calling installed CLI generation, then releases generation before AR selection. It observes the CLI's actual new raw AR predictions, saves them into a new isolated cache, and runs a second cache-only replay. Assertions check the same activation/pool, contiguous N2 records, cache identity, identical selected text/source IDs and FVE within `1e-10`, with zero encodings on replay. No output is overwritten and no production cache is written.

The record retains prompt/token IDs, capture/sample/encoding/replay wall times, GPU allocation/reservation/peak memory, host peak RSS, local artifact and installed-source hashes, adapter-change guard, FP32 activation hash, sampling provenance and new cache lineage. A successful engineering run does not establish that its concepts are correct, that an external activation uses the intended site, or that an independent machine's complete dependency installation works.

The coordinator may launch on **one freed main H200 only after its blind VAL generation finishes**, with allocation state and memory checked first. Prepared command (replace `FREE_MAIN_H200` with the verified allocation ID):

```bash
srun --jobid=FREE_MAIN_H200 --overlap -N1 -n1 -c8 --mem=64G --cpu-bind=cores \
  ${OLENS_COMPUTE_ROOT}/packaging/isolated-wheel-v1/venv/bin/python -I -B \
  scripts/portable_engineering_smoke.py \
  --artifacts ${OLENS_COMPUTE_ROOT}/packaging/isolated-wheel-v1/engineering-artifacts.json \
  --cache-contract ${OLENS_COMPUTE_ROOT}/vectors/shared-global-v1/a451cf49d28ac7447722/contract.json \
  --dependency-site ${OLENS_COMPUTE_ROOT}/envs/runtime/lib/python3.12/site-packages \
  --dependency-site ${OLENS_SCRATCH}/workspace/venvs/lens/lib/python3.12/site-packages \
  --output ${OLENS_DATA_ROOT}/engineering/portable-fresh-input-v1
```

Preparation checks only: CLI help, syntax and source review. Actual loader, GPU memory and end-to-end assertions remain unrun. Preserve a failed attempt and version any rerun directory; never silently regenerate an existing pool.
