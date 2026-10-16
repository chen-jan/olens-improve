# Per-bullet FVE

This folder holds the per-bullet FVE analyses. Each O-lens readout is a list of bullets. For each bullet we measure how much of the target activation it explains: solo FVE, leave-one-out drop and Shapley share of the joint NNLS fit. Token heat goes further and splits the leave-one-out drop over the bullet's tokens. The main study is Hallucination (chat). Multihop, Chained intermediates, Role-bound association, User modelling and Conjunctive association repeat it on other families. Start with [reports/COMBINED_REPORT.md](reports/COMBINED_REPORT.md).

## Layout

- `code/` holds the scripts as they were run, in their original folder layout (`code/code/` is the shared pipeline, `code/tasks/` the other families, `code/newtasks/` the User modelling and Conjunctive association run). They were not refactored. They still assume the original work folder, so paths in them appear as `${OLENS_*}` placeholders. Left out: backups, Slurm launchers, GPU-board guards and supervisors, one-off probes, agent notes, tests that need the production data, and all data files.
- `reports/` holds the reports, in the same layout as `code/`. Process notes, such as the run book and GPU-allocation notes, were left out.
- `explorers/` holds the two explorer pages, without their data:
  - `hallucination/index.html` is the [Hallucination Bullet FVE explorer](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3).
  - `multihop/index.html` is the [Multihop explorer](https://claude.ai/artifact/BaKkNJyQDBC5AB7oz4XHNE).

## Data

None of the data is in this repo. That covers inputs, metrics, token heat, page data, reader records and the AR vectors. It lives in two places:
- the full work folder, archived as is on the lab's pool storage (`olens-archive/2026-10-16/`);
- the private HF dataset, which holds the text-level traces and results.

To view an explorer locally, put its `data/` folder from the private HF dataset next to its `index.html`. The published explorers above already include their data.
