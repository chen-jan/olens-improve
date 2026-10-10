# Improving the released Oracle Lens at inference time

The project tests whether inference-time selection and composition can improve the frozen released Oracle Lens. Maximum quality is the priority: measure recovery/error tradeoffs, explore sampling saturation, and explain any combined method with controlled comparisons.

The initial execution target was approximately 20 hours; current timing and remaining work are recorded in [STATUS.md](docs/STATUS.md). A dashboard begins after the first validated pilot and updates after scored experiments and trace reviews: key findings first, then charts and method tabs. Final delivery includes the report, per-family results, uncertainty, costs, and inspectable examples.

Read [the execution plan](docs/PLAN.md) and [detailed method specifications](docs/METHODS.md) before continuing. Record each experiment using [the experiment template](docs/experiments/TEMPLATE.md), and follow [AGENTS.md](AGENTS.md) for cluster and storage rules.

Current state: the shared 189-cell development pilots and the twelve-method validation comparison are complete. Validation supports best-of-16 and matched-control selection from 32 samples as experimental candidates; no general improvement in faithful explanation is established. The prospectively expanded twelve-method test is frozen: multi-hop and chains have finished judging, while hallucination and role binding remain active. All six development sampling prefixes, their grouped uncertainty and the shared fixed-case reviews are published. Reviewed development and validation maps are also available. Late development results cannot change the final comparison. See [the working report](docs/REPORT.md), [local dashboard](dashboard/index.html) and [current status](docs/STATUS.md) for findings, limitations, costs and active work. The [public dashboard](https://olens-improve-research.jan618.chatgpt.site) has a reviewed visual overview and expandable details. Research commits stay local; the user handles GitHub pushing.

For local vector-first inference or saved-pool replay, the package provides `python -m olens_improve` (also `olens-improve` after installation) with `generate`, `import-pool` and `replay` commands. It uses local frozen artifacts and has no scheduler, network download or paid-helper requirement. The two validation-selected profiles remain experimental pending final test results. Install with `python -m pip install '.[inference]'` in a compatible environment outside HOME; an editable install is optional for development. If dependencies already exist, use `python -m pip install --no-deps .`. No historical research checkout is needed for the portable API; benchmark judging and experimental helper scripts use separate research dependencies. The tested runtime uses Python 3.12, Torch 2.13, Transformers 5.16.1, PEFT .21.2, Accelerate 1.14, safetensors .8, NumPy 2.5.2 and SciPy 1.18.1; other versions are not validated by that result.

Create an artifact JSON with explicit local paths. The base/pair must match the revisions in [the plan](docs/PLAN.md); matching pooled whiteners are required for AR scoring. Raw/capped N1 replay needs only `base_path` for its tokenizer. A complete configuration is:

```json
{
  "base_path": "/path/to/pinned-Qwen3.6-27B",
  "olens_adapter": "/path/to/pinned-pair/olens_s3d_rl600",
  "ar_checkpoint": "/path/to/pinned-pair/ar_ptag_pooled",
  "whitener_directory": "/path/to/matched/whiteners",
  "device": "cuda"
}
```

For new supplied vectors, generation requires hardware that can load the base model and adapter; measured GPU work used H200. Existing cached-vector replay can use `"device": "cpu"` and does not load base-model weights. For example:

```bash
python -m olens_improve generate --artifacts artifacts.json --activation activation.safetensors --layer 44 --n 32 --seed 1 --pool pool.json
python -m olens_improve replay --artifacts artifacts.json --activation activation.safetensors --pool pool.json --method best_n --n 32 --encode-missing --save-cache phrase-cache --output selection-n32.json
python -m olens_improve replay --artifacts artifacts.json --activation activation.safetensors --pool pool.json --method best_n --n 16 --cache-directory phrase-cache --output selection-n16.json
```

The activation tensor defaults to key `activation`, width 5120; `--key` and `--row` can select a row from an existing matrix. Generation refuses an existing pool or interrupted-generation claim file, preventing silent resampling. Replay reuses the saved prefix, preserves every source record and never requests more O-lens samples. `--cache-directory` reads a compatible raw AR cache without changing it; `--encode-missing` explicitly permits local AR encoding after the O-lens loader has been released. `--save-cache` writes a **new** immutable standalone cache of all vectors used by that replay prefix, including inherited hits, so later comparisons need not load the AR model again. If only N16 was encoded, an N32 comparison still needs its missing vectors. Existing or incomplete output-cache directories are rejected; the selection JSON must be outside the cache directory. The 32-token AR truncation and batch-dependent numerical limits remain visible in outputs. Raw/capped N1 need no AR and reject `--save-cache`. Token-ID capture and paid consensus/editing experiments remain separate research scripts.

Specificity requires an explicit caller-frozen matched calibration-control manifest (`--controls`); absent controls make that method unavailable, with no default donor selection. Given the N32 cache above and validated same-layer controls:

```bash
python -m olens_improve replay --artifacts artifacts.json --activation activation.safetensors --pool pool.json --method specificity_mean --n 32 --cache-directory phrase-cache --controls frozen-controls.json --output selection-specificity.json
```

The controls JSON declares `layer`, `bank_sha256` and nonempty distinct `controls` entries with `id`, `path`, tensor `key` and optional `row`; matching and calibration exclusions remain the caller's responsibility. Library replay uses the same options as `cache_directory`, `encode_missing` and `save_cache_directory`. Full source texts remain separate even when their effective first 32 AR tokens share one vector. The persistence option passed offline tests, independent source review, and a real installed-wheel check: eight new phrase vectors were saved, the cache was moved, and replay returned exactly the same text, phrase IDs and score without loading the reconstructor. See [experiment 036](docs/experiments/036-portable-cache-persistence.md). The earlier installed wheel/timing driver remain unchanged.

Existing per-cell JSONL pools can be imported without new generation:

Blind benchmark records are rejected by this standalone entrypoint. Held-out replay uses the coordinator pipeline and its separate analysis authorization; importing a saved pool does not grant that authorization.

```bash
python -m olens_improve import-pool --records samples.jsonl --cell-id CELL_ID --activation activation.safetensors --layer 44 --pool saved-pool.json
```

Library equivalents are `Artifacts`, `CandidatePool`, `generate_pool` and `replay_select` in `olens_improve.inference`. Results record pool/activation hashes, local artifact checks, atom truncation, selection lineage and unavailable inputs. A declared local revision is not a full rehash of base weights; supply the pinned artifacts rather than unrelated files bearing the same names.

For a CPU replay with existing raw vectors, add `--cache-directory /path/to/compatible/raw-cache` and omit `--encode-missing`. New portable caches can be moved as a whole: their completion receipt verifies file hashes and relative tensor references. Older research caches may reference external tensors; keep those original files available. The package takes an already captured activation, not a natural-language prompt: caller capture must use the frozen base with adapters disabled, the documented decoder-block layer and correct token position. The portable CLI has no raw-text/token-ID capture command. Existing DEV replay establishes installation, provenance and selection compatibility; fresh off-benchmark input quality and end-to-end portability on a different machine have not been validated.

An offline wheel installed into an empty package environment replayed one frozen DEV N16 pool with identical selected text and phrase IDs (FVE difference `1.34e-8`), using explicit existing third-party distributions without executing their `.pth` files or importing historical project code. This check loaded no model, encoded no new vectors and made no API calls; it does not establish a complete fresh dependency installation on another machine.

The installed tool also completed an [off-benchmark fresh-input engineering check](docs/experiments/026-portable-fresh-input-engineering.md): adapter-disabled capture, N2 generation, eight new AR vectors in an isolated cache, selection and zero-encoding replay, with identical selected IDs/FVE. It took 156 seconds on one H200 and made no API calls. This verifies plumbing in the existing environment; semantic quality and a complete dependency installation on another machine remain unvalidated.
