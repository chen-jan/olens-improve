# Offline terminal contract verifier: implementation audit

Implemented `scripts/verify_expansion_judge_contracts.py` and eleven focused fixtures in `tests/test_expansion_judge_contracts.py`. The module imports only standard-library modules. It does not load an inference client, benchmark runtime, API key or network transport. The analyzer and all active production services were left unchanged by this implementation.

`verify_judge_contract(...)` accepts parsed descriptor, terminal summary, result and project contract plus independently approved runtime hashes. It enforces family, explicit non-dry-run state, frozen benchmark commit, exact expected/produced counts, no missing/partial grid, model/effort, scientific method/N and exact inventory/selection/family-manifest SHA binding, single-readout coverage, exact upstream result payload, and contract agreement outside three documented metadata updates. Comparison is type-sensitive JSON equality, preventing Python's boolean/integer aliasing from hiding changes. The allowed external metadata must equal the declared exploratory status, inventory SHA and split-preservation flag; embedded values may be the known earlier snapshot or the correct refreshed values. False upstream `complete` and `pinned_instrument` flags remain valid and are preserved in the receipt.

`load_approved_runtime_pin(path, sha, pointer='/runtime_source_hashes')` hashes the exact bytes parsed and resolves an explicit pointer. Approval must be established independently by the caller. The CLI accepts exact input paths and approved receipt SHA/pointer, records all input hashes, rechecks source immutability, and can save an atomic audit JSON. It validates provenance; the existing analysis still validates complete raw text/grid coverage and native outcomes separately.

The original approved authority chain was independently checked:

1. `configs/test_final_method_freeze_v2.json`, status `root_reviewed_frozen`, SHA **b46f00851efb71628faa2ffcb404011c4ef1f3543d68fc4f18d0ab6d74d95e86**.
2. Its `validation_evidence` binds `${OLENS_DATA_ROOT}/runs/validation-full-grid-v1/signed-menu-analysis-v1.json`, SHA **db223a374f51d9122f8cc430a347e4f82dea75ce3d449008e1def1f7cf89e918**.
3. That report's complete `measurement.conditions` entry for `best_n_exact-n32` binds `${OLENS_DATA_ROOT}/runs/validation-full-grid-v1/judgments/best_n_exact-n32/hallucination/project_contract.json`, SHA **bbd2c232e576b1152757e393f4f4f5681aa42c03e4262bcb04839948d9c1f5e7**. The approved dictionary is at `/runtime_source_hashes` and contains 21 entries.

All **128** condition-family terminals in the immutable `first-live-v1.json` analysis passed strict verification against this earlier pin. The full saved scan ran on existing CPU job **25536291**, core **44**, with no paid calls or new allocation. Its source-bound receipt is `.state/statistical-adversarial-v1/judge-contract-verification.json`, SHA **02e37b4fedade3f3bf1068ffe884185b8b3d17d02089249444e0a7d4440e46be**; the replay driver is `verify_real.py` in that directory. It verifies the original freeze/report/contract byte chain and every terminal against the saved analysis hashes, rather than scanning mutable new arrivals.

Validation commands:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_expansion_judge_contracts.py -v
PYTHONPATH=src python -m unittest discover -s tests -p test_expanded_statistics.py -v
```

All eleven verifier tests and nine statistics tests passed. Fixtures exercise payload drift despite an unchanged headline, identity and cell-count changes, dry-run/model/effort changes, runtime drift even when both contracts are self-consistent, stage-two contract changes, invalid embedded metadata, approved receipt byte changes, and the known valid metadata sequence.

The coordinator's warning/count update was also compared against the earlier source-bound seeded probes. Every previously recorded estimate, pointwise interval, paired standard error, joint critical value and simultaneous interval was **exactly unchanged**. New absolute warning fields and declared/effective/joint counts were present. This check is saved as `.state/statistical-adversarial-v1/statistics-update-check.json`, SHA **3e57e515098d59f3936af6429d0ea92db3bb85769b35248cc85013e42476bed4**. It establishes numerical preservation for those probes, not general bootstrap coverage.

Verifier SHA: **e14395c110c1b56ac93db84d183ec014e13368d4a28e0310e80a2ae4f5d78d2a**. Fixture SHA: **b8ebfb57e677ed08318bf46e560a7a0855c5b60cdebc5a09f1002308ff50bdb3**. Root owns runtime-authority configuration and analyzer integration; neither is claimed complete by this receipt.

At the operational check, GPU job **25536297** had reached **5,505 / 19,435** likelihood cells at approximately **0.821 seconds/cell**. The editing bridge was watching with no recorded errors. No active GPU or judge source was modified.
