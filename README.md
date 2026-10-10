# Improving the released Oracle Lens at inference time

The project tests whether inference-time selection and composition can improve the frozen released Oracle Lens. Maximum quality is the priority: measure recovery/error tradeoffs, explore sampling saturation, and explain any combined method with controlled comparisons.

The execution target is approximately 20 hours from the actual start, subject to prerequisite checks and measured throughput. A dashboard begins after the first validated pilot and updates after scored experiments and trace reviews: key findings first, then charts and method tabs. Final delivery includes the report, per-family results, uncertainty, costs, and inspectable examples.

Read [the execution plan](docs/PLAN.md) and [detailed method specifications](docs/METHODS.md) before continuing. Record each experiment using [the experiment template](docs/experiments/TEMPLATE.md), and follow [AGENTS.md](AGENTS.md) for cluster and storage rules.

Current state: autonomous execution started on 2026-10-10 at 01:25:36 UTC. The shared 189-cell pilot is generated and scored; semantic comparisons are in progress. See [the local dashboard](dashboard/index.html) and [the current status](docs/STATUS.md) for measured results, spending, active jobs, and recovery instructions. The dashboard is locally browser-checked and has not been published. Local commits only; the user handles pushing.

For local vector-first inference or saved-pool replay, the package provides `python -m olens_improve` with `generate`, `import-pool` and `replay` commands. It uses local frozen artifacts and has no scheduler, network download or paid-helper requirement. All method profiles remain experimental until validation selects a recommendation. Install the optional runtime dependencies with `pip install -e '.[inference]'` in an environment outside HOME, or use an existing compatible environment with `PYTHONPATH=src`.

Create an artifact JSON containing local `base_path`, `olens_adapter`, `ar_checkpoint`, `whitener_directory` and `device` paths. The base/pair must match the revisions in [the plan](docs/PLAN.md); matching pooled whiteners are required for AR scoring. For example:

```bash
python -m olens_improve generate --artifacts artifacts.json --activation activation.safetensors --layer 44 --n 32 --seed 1 --pool pool.json
python -m olens_improve replay --artifacts artifacts.json --activation activation.safetensors --pool pool.json --method best_n --n 16 --encode-missing --output selection.json
```

The activation tensor defaults to key `activation`, width 5120; `--key` and `--row` can select a row from an existing matrix. Generation refuses an existing pool or interrupted-generation claim file, preventing silent resampling. Replay reuses the saved prefix, preserves every source record and never requests more O-lens samples. `--cache-directory` reuses a compatible raw AR cache; `--encode-missing` explicitly permits local AR encoding after the O-lens loader has been released. The 32-token AR truncation and batch-dependent numerical limits remain visible in outputs. Raw/capped N1 need no AR. Specificity requires an explicit caller-frozen matched calibration-control manifest (`--controls`); absent controls make that method unavailable, with no default donor selection. Token-ID capture and paid consensus/editing experiments remain separate research scripts.

Existing per-cell JSONL pools can be imported without new generation:

```bash
python -m olens_improve import-pool --records samples.jsonl --cell-id CELL_ID --activation activation.safetensors --layer 44 --pool saved-pool.json
```

Library equivalents are `Artifacts`, `CandidatePool`, `generate_pool` and `replay_select` in `olens_improve.inference`. Results record pool/activation hashes, local artifact checks, atom truncation, selection lineage and unavailable inputs. A declared local revision is not a full rehash of base weights; supply the pinned artifacts rather than unrelated files bearing the same names.
