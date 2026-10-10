# 036: Portable cache persistence

Status: source implementation and offline checks complete; independent review passed. A separate candidate wheel and real installed-CLI cache check are **planned, not run**. This is engineering work, not another scientific method or quality result. No GPU/API calls, new O-lens samples or production-cache changes were made for this record.

## Problem and implementation

Previously, portable replay could encode missing phrase vectors but discarded them when it exited. The installed engineering smoke saved vectors through a driver observer, so that smoke did not establish ordinary CLI persistence. New `--save-cache PATH` / API `save_cache_directory` makes this explicit without changing mathematical scoring or the existing timing driver.

The requested directory must be new before any model load; raw/capped N1 reject the option because they do not request AR scoring. `--cache-directory` remains read-only. The new standalone cache copies all effective raw vectors used by the requested prefix, both inherited hits and newly encoded vectors. It stores one safetensors shard, the exact verified model/tokenizer/head contract, effective-token/layer-tag keys, source indices and execution metadata. A separate usage file retains every original phrase and full source record, including invalid atoms and distinct texts whose first 32 scored tokens coincide. No target vectors, whitening copies, controls or judgment labels are saved.

Actual encoding must return the requested token/tag identities and row counts. Saved vectors must be finite FP32 rows of width 5120. The completion receipt is written last, hashes the exact constituent files and records the vector/variant counts; partial, corrupt, falsy or non-complete receipts fail closed. Tensor filenames are relative, allowing the complete directory to move without its inherited source cache. Existing directories and interrupted attempts are retained rather than overwritten. A selection JSON belongs outside this immutable directory.

Source hashes at review:

| Source | SHA-256 |
|---|---|
| [inference.py](../../src/olens_improve/inference.py) | `42bf72de164a88c39ca2c1a38e20fa1507ddee509a215f11b3799379d0a5623f` |
| [CLI](../../src/olens_improve/__main__.py) | `6777b9d55620c1b90404f8b015dc0de8528cc8f78fa317404b3e21a4abfb5a37` |
| [portable cache](../../src/olens_improve/portable_cache.py) | `7eb065019dae9327e02613aefac013224ce437f7ecad26869b52e4891e25f35c` |
| [focused tests](../../tests/test_portable_cache.py) | `3a0c31e91285c47e6aea8da185e54174cd30b500f7068ff1ba6a4ab7948220b9` |

Nine focused offline tests passed in 0.466 seconds, plus six existing inference tests. They cover mocked encoding followed by identical zero-encoding replay, relocation, inherited-cache immutability, effective-input suffix aliases with distinct provenance, empty/invalid atoms, legacy cache compatibility, changed artifact rejection before loading, invalid vectors, incomplete/corrupt/falsy receipts and overwrite/baseline preflight. The independent resource reviewer identified the falsy-receipt fallback; the corrected version and three-value regression were reviewed again with no remaining blocker. These checks do not establish real model/cache numerics or a fresh-machine dependency installation.

## Separate candidate-wheel plan

Preserve `packaging/isolated-wheel-v1` and its installed environment byte-for-byte: the approved N32 deployment timing still runs that old wheel. Build into a new fast-storage directory, with no dependency installation/download and no replacement of the old wheel. Proposed commands, **not executed**:

```bash
PY=${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python
CANDIDATE=${OLENS_COMPUTE_ROOT}/packaging/portable-cache-v2
"$PY" -m pip wheel --no-deps --no-build-isolation --wheel-dir "$CANDIDATE/wheels" .
```

Root first verifies that the candidate directory is new and records the local commit, source hashes and exact resulting wheel SHA. The project version remains 0.1.0, so the separate directory—not a filename—distinguishes this candidate from the older wheel. Install only into a new isolated candidate environment/target, using already available third-party distributions explicitly and avoiding historical `.pth` execution. Verify imports and `replay --help` come from that candidate, not checkout source or the old wheel.

After the old-wheel timing completes and root assigns a free GPU, replay the **existing non-benchmark N2 engineering activation/pool** from [experiment 026](026-portable-fresh-input-engineering.md); do not recapture or regenerate. Use no inherited vectors for the first pass, `--encode-missing --save-cache NEWPATH`, then replay from that new cache with encoding omitted. Require identical text/source IDs/FVE across these two candidate-wheel passes, zero new encodes on the second, matching activation/pool hashes, complete cache/file identities and no API calls. Compare the prior old-wheel result separately with an explicit numerical tolerance, not as a new quality experiment. Record actual timing/memory and candidate installed-source hashes; outputs go to a new engineering-only directory, never the production cache. A failure remains a failed engineering check, not a scientific negative.

The [README](../../README.md) documents normal N32 cache creation followed by N16 and same-pool specificity replay. Installation/model availability and external activation/control correctness remain explicit caller requirements. The 32-token blind spot and batch-dependent numerical sensitivity are unchanged.
