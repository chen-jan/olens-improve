# Terminal expanded intake and qualitative review plan

Prepared 2026-10-11 03:35 UTC. This is an executable dependency plan, not a final measurement or publication receipt. Exact source versions are in [expanded-final-intake-plan-v1.json](expanded-final-intake-plan-v1.json). Root owns final synthesis, review, Git and publication.

## Terminal order and ownership

1. GPU finishes likelihood, four editing-round-one and four editing-round-two tasks. Round two requires each terminal full round-one `scored_candidates.jsonl` history, exact proposal/cohort hashes and the original reconstructor/whitener contract. The bridge accepts immutable descriptors; it does not accept beam-only history.
2. Helper service publishes each editing round's canonical family selection; CPU owner publishes the four round-two prune/deletion settings. Existing registrar streams each completed family immediately. Non-role banks currently await six editing settings; role additionally awaits three likelihood settings. No new reader, method, request or grade is introduced.
3. CPU owner's final-native gate waits for all 70 exact condition IDs × four terminal families and exactly 32 canonical descriptors (eight producer directories × four). It validates contracts and freezes one snapshot before extraction. Waiting-file counts do not establish scientific completion. Canonical directories: `cached-v2`, `combinations-v2/merged`, `semantic-semantic-v1`, `semantic-medium-v1`, `likelihood-v1`, `editing-round1-v1`, `editing-round2-v1`, `editing-pruning-v1`. Exclude `_queue_` aliases.
4. Final effort watcher waits for the native gate's `complete_pending_root_review` plus `scientific_inputs_validated_complete=true`, exact final native hash/snapshot receipt, terminal helpers/checkpoints, GPU task menu and workers. It exports once to an atomic bundle. CPU owner separately binds final reconstruction to the exact new native SHA, using `scripts/analyze_expansion_reconstruction_v5.py` and any required role-likelihood addon replay (historical v3 and the unrun v4 prototype remain unchanged). The approved v5 successor uses `expanded_editor_fit_intake_v2.py` and additionally requires the reviewed editor-fit authority and an immutable dispatch snapshot of exact queue task entries plus successful completed-task receipts; task signatures use `SHA(json.dumps(task,sort_keys=True))`, not compact JSON. Live queue/service hashes and observation times are recorded separately because those files are mutable. No native/reconstruction extraction is duplicated by this plan.
5. CPU owner exports a new final qualitative pack and actual-parent pack from that exact native source. Build a delta index, review only pending exact comparisons, structurally validate all inherited and fresh notes, then root attests final numbers/text/artifacts.

## Effort watcher and failure guards

Live on existing API CPU 25536291/core83: PID 778184; tool session42077; state `.state/expanded-final-effort-v1.service.json`; log `${OLENS_COMPUTE_ROOT}/logs/expanded-final-effort-v1.log`. Poll60 s, timeout8 h. Timeout writes `waiting_timeout_no_export`; it does not create an early snapshot. A failed/incomplete `.preparing` bundle is retained for root review, without an automatic re-export. Completed bundles are SHA-revalidated and returned without duplicate work. No API transport, ledger write, hold release, allocation, cancellation or scientific pin change occurs.

Reviewed executable launch (already running; do not duplicate):

```bash
srun --jobid=25536291 --overlap --ntasks=1 --cpus-per-task=8 --job-name=expanded-final-effort-v1 taskset -c 83 ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python scripts/expanded_final_effort_gate.py --poll-seconds 60 --max-watch-seconds 28800
```

Offline preflight:

```bash
python scripts/expanded_final_effort_gate.py --preflight
python -m unittest discover -s tests -p test_expansion_final_effort_gate.py
```

Output bundle: `${OLENS_DATA_ROOT}/expansion-v1/analysis/effort-final-v1/{effort.json,receipt.json,attempt.json,export.log}`. Final receipt records the accounting cutoff separately from the native source time. Settled phase buckets must sum to settled expansion usage; global project settled usage, live reservations and unknown holds remain distinct. Helpers shared by semantic variants and editing variants are not charged as separate per-setting calls. API usage estimates exclude GPU dollars and Codex agent billing. New-input engineering timing remains a one-vector fixture, not a bank-average latency estimate.

Operational source pins include the exporter and `build_expansion_dashboard.py` label/recipe adapter. A change to either requires a separately reviewed new intake operational receipt/restart; the running watcher fails closed. Do not patch active scientific sources to accommodate the gate.

## Final qualitative commands: CPU owner only, after terminal native seal

Run on the existing CPU owner's allocation25536417. The `FINAL_NATIVE_SHA` and `FINAL_CASES_SHA` strings below must come from the terminal native state and a freshly verified output SHA, respectively. These commands are a dependency recipe, not an authorization to substitute a partial source. Output paths must be absent. CPU owner may rename the immutable final pack generation if its current coordinated contract differs; record that exact path/SHA in the final index.

```bash
${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python scripts/build_expansion_qualitative.py --analysis ${OLENS_DATA_ROOT}/expansion-v1/analysis/final-v1.json --analysis-sha256 FINAL_NATIVE_SHA --judgments ${OLENS_DATA_ROOT}/expansion-v1/judgments --report dashboard/report.json --output ${OLENS_DATA_ROOT}/expansion-v1/qualitative/final-v1.json
${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python scripts/build_expansion_parent_qualitative.py --cases ${OLENS_DATA_ROOT}/expansion-v1/qualitative/final-v1.json --cases-sha256 FINAL_CASES_SHA --analysis ${OLENS_DATA_ROOT}/expansion-v1/analysis/final-v1.json --analysis-sha256 FINAL_NATIVE_SHA --judgments ${OLENS_DATA_ROOT}/expansion-v1/judgments --output ${OLENS_DATA_ROOT}/expansion-v1/qualitative/parent-comparisons-final-v1.json
${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python scripts/build_expansion_qualitative_delta_v2.py --previous ${OLENS_DATA_ROOT}/expansion-v1/qualitative/first-live-v4.json --current ${OLENS_DATA_ROOT}/expansion-v1/qualitative/final-v1.json --previous-parents ${OLENS_DATA_ROOT}/expansion-v1/qualitative/parent-comparisons-first-live-v3.json --current-parents ${OLENS_DATA_ROOT}/expansion-v1/qualitative/parent-comparisons-final-v1.json --prior-index docs/reviews/expanded-qualitative-v4-new-case-index-v1.json --prior-review docs/reviews/expanded-qualitative-v4-root-v2.json --prior-review docs/reviews/expanded-qualitative-v4-agent1-v2.json --prior-review docs/reviews/expanded-qualitative-v4-agent2-v2.json --prior-review docs/reviews/expanded-qualitative-v4-agent3-v1.json --output docs/reviews/expanded-qualitative-final-new-case-index-v1.json
```

Before indexing, verify all source hashes against the intake plan and require exact old-to-new full case rows, unchanged old complete parent comparisons, and identical contexts for all old context keys. The delta builder already rejects changed old case/complete-parent rows. The final merger must independently validate context equality and the inherited review-link hashes; a context hash alone does not validate copied before/after text. The source-bound parent references must be actual recorded parents, not an assumed capped reference.

## What inherits and what needs review

Existing audited examples/notes can remain verbatim when their full case, before/after texts, context, parent provenance and official endpoint evidence match. The new index links exact previously reviewed content+official pairs to the four complete v4 partition reviews; it retains new condition-specific whole-grid metadata separately. Merely sharing an output phrase or cell ID is insufficient. Changed official pairs require review even when text was seen. A formerly missing parent that is now available requires a new actual-parent comparison. New editing cases require review after actual scoring/judging; no editing gains are inferred from earlier pruning or fit values.

Review each pending partition's fixed anchors and selected win/regression/unchanged examples. Preserve official outcomes and separate local anchor evidence from whole-question witnesses. Chain correctness is the first-ranked extracted integer; target-present lower-ranked/any-of-three evidence is diagnostic only. Qualitative explanations remain descriptive; proposed mechanisms are labeled hypotheses, and whole-grid changes inherited from a parent are not attributed to a later operation.

The final review merger `scripts/validate_expansion_qualitative_final_reviews.py` is count-derived. **Do not call `validate_expansion_qualitative_reviews_v4.py` unchanged**: it hardcodes historical426 pairs,330 fresh references and29 inherited references. The new final merger uses exact final-index pair/reference identities, validates all four new partitions and every inheritance authority/context/official pair, prevents duplicate references, preserves the prior audited bundle verbatim, and pins parser calibration. Its CLI additionally requires the scientifically terminal final-native gate and exact native SHA. Unit fixtures cover context/verdict changes, duplication, nonstandard counts and partial review coverage. Empty pending partitions may be explicitly reviewed with zero count; missing reviews are not complete coverage. Root then binds final merged notes and final numeric/effort sources before slides/report/dashboard construction. No publication is authorized by this document.


Final merger command after all four human-review files exist (CPU owner runs; root review follows):

```bash
${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python scripts/validate_expansion_qualitative_final_reviews.py --index docs/reviews/expanded-qualitative-final-new-case-index-v1.json --prior-index docs/reviews/expanded-qualitative-v4-new-case-index-v1.json --prior-notes docs/reviews/expanded-qualitative-v4-merged-notes-v1.json --prior-review root=docs/reviews/expanded-qualitative-v4-root-v2.json --prior-review agent_1=docs/reviews/expanded-qualitative-v4-agent1-v2.json --prior-review agent_2=docs/reviews/expanded-qualitative-v4-agent2-v2.json --prior-review agent_3=docs/reviews/expanded-qualitative-v4-agent3-v1.json --review root=docs/reviews/expanded-qualitative-final-root-v1.json --review agent_1=docs/reviews/expanded-qualitative-final-agent1-v1.json --review agent_2=docs/reviews/expanded-qualitative-final-agent2-v1.json --review agent_3=docs/reviews/expanded-qualitative-final-agent3-v1.json --output docs/reviews/expanded-qualitative-final-merged-notes-v1.json
```

The prior330-reference notes bundle is copied verbatim; its historical426-pair authority is independently checked against its pinned historical index. Final new-reference counts come from the final index, never from those old totals. Complete zero-length partitions require explicit complete zero-count review files. Missing partitions yield partial coverage and cannot authorize complete final notes.
