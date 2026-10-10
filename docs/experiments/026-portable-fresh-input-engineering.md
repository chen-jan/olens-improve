# 026: Synthetic fresh-input engineering smoke

Status: completed on H200 allocation 25330006 using the installed wheel. This checks installed-tool plumbing, not readout quality or a scientific method. Every artifact is marked `scientific_results_eligible=false` and excluded from benchmark exports, judging and aggregation. No API calls or training were involved.

The sole input is fixed text: “The library closes at six. Nora returns a borrowed book before walking home.” Capture one adapter-disabled final-token activation at supported layer 44, using the frozen base/pair. Generate exactly two samples, seed 20261010, with the released sampling settings. No benchmark manifest, activation, readout, answer or validation/test filename/content is an input. A caller supplies only explicit local model, adapter, AR and matched-whitener paths. The cache contract is metadata from the verified DEV encoder; no inherited vector data is copied.

`scripts/portable_engineering_smoke.py` requires an allocated GPU and checks that `olens_improve` comes from the installed wheel. Explicit third-party distribution paths do not execute historical environment `.pth` files. The driver releases the capture loader before calling installed CLI generation, then releases generation before AR selection. It observes the CLI's actual new raw AR predictions, saves them into a new isolated cache, and runs a second cache-only replay. Assertions check the same activation/pool, contiguous N2 records, cache identity, identical selected text/source IDs and FVE within `1e-10`, with zero encodings on replay. No output is overwritten and no production cache is written.

The record retains prompt/token IDs, capture/sample/encoding/replay wall times, GPU allocation/reservation/peak memory, host peak RSS, local artifact and installed-source hashes, adapter-change guard, FP32 activation hash, sampling provenance and new cache lineage. A successful engineering run does not establish that its concepts are correct, that an external activation uses the intended site, or that an independent machine's complete dependency installation works.

The coordinator launched on one freed main H200 after its blind VAL shard finished. The prepared command below was used with `FREE_MAIN_H200=25330006`; preserve the completed directory rather than rerunning it:

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

Measured result: 155.817 seconds total; capture/load/release 52.923, generation 56.861, new AR encoding/selection 38.602, and cache-only replay 7.043 seconds. The adapter-disabled 15-token input produced one FP32 5,120-dimensional L44 vector and exactly two samples. Eight raw AR vectors were written only to this engineering cache; replay encoded zero. Both selections chose sample index 1 with identical text, source IDs and exact FVE `0.17866450397739786` (difference zero). Peak CUDA allocation was about 51.0 GiB; after all loaders were released, 32 MiB remained allocated/reserved. Host peak RSS was about 40.6 GiB.

Evidence is in `${OLENS_DATA_ROOT}/engineering/portable-fresh-input-v1/{scope,capture,pool,selection-encoded,selection-cached,result}.json` and its activation/cache tensors. Result SHA256 is `b63bf4bc5bab810e1efe655c8a935823a2c7ca8a50fa948b17de729993fd661d`; activation-value hash is `825b7670774ff35d71ec8177e3c5a19ec93cc18b4ad3a538c4309d76a159665e`, and pool-file hash is `123ccffddeb7732450b979b567413ef093fab6ecefd3a330020dfa5001564e79`. Independent binary/metadata checks confirmed the activation bytes, contiguous sample indices, isolated cache paths, zero replay encodings and identical selections. This establishes installed capture-to-replay plumbing in the existing environment, without evaluating semantic quality or a fresh machine's complete dependency installation. Never silently regenerate an existing pool.
