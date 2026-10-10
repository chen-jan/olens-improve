# Final scientific review handoff

Status: preparation only. No TEST outcomes, judgments, live caches or ledger were inspected for this handoff. No analysis or inference command was run. Frozen menus, source judgments and historical plans are unchanged.

The TEST reporter is ready once root confirms all 48 signed method/family contracts, including both hallucination stages, are complete. Use the exact TEST12 command in [DELIVERY_CHECKLIST](DELIVERY_CHECKLIST.md). Its immutable output is `${OLENS_DATA_ROOT}/runs/test-full-grid-comparison-v2/final-analysis-v2.json`. Hold `analyze_signed_menu.py`, its consensus reader, reporting, evaluation and data modules unchanged from startup through completion; the reporter hashes and checks that window. Do not overwrite an existing artifact or infer missing verdicts.

After the report, root must supply explicit TEST reveal/review metadata with the artifact, menu, cohort, selection, gate and freeze hashes, exact family counts, reviewed findings, trace references and cost rows. This is the remaining input for the existing attachment, figures, deck and public packaging interfaces. There is no new code blocker to TEST reporting. The separate whole-469 appendix still requires complete DEV inputs and a new ready plan; it must not hold up review of the complete 268-item TEST result.

## DEV12 input for the whole-469 appendix

The new [reporting conditions](../configs/conditions_development_final12_reporting_v1.json) preserve the twelve TEST method identities and their order, adding only the original DEV selection path and SHA to each arm. The [prepared report plan](../configs/development_final12_reporting_v1.prepared.json) records the exact command and preparation-time source hashes. It is not execution authority.

Existing DEV contracts refer to the authoritative 24-method source `selections/development-full-grid-judging-v1/selections.jsonl`, SHA `acfcdefc425f48da612059f7bcb157bf037f91ba4e70fa9c68b0db142bfc46a4`. The immutable twelve-method projection has SHA `a638c102a2e762543d0d81f28575fa2a46dd64ea7d12641b071622736a89c91e`. Its `final12-exact-provenance-v2.json` confirms exact text/token/bullet copying for all 5,236 cells. The per-arm overrides preserve the original contract identity while the reporter independently checks projected text against judged text.

Run only after all 48 DEV12 family contracts are complete and root has reviewed the source window:

```bash
${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python scripts/analyze_signed_menu.py \
  --manifest configs/development-full-grid-v2.json \
  --conditions configs/conditions_development_final12_reporting_v1.json \
  --judgments ${OLENS_DATA_ROOT}/runs/development-full-grid-v2/judgments-methods-v1 \
  --selections ${OLENS_DATA_ROOT}/selections/development-full-grid-judging-v1/final12-exact-v2.jsonl \
  --selection-sha256 a638c102a2e762543d0d81f28575fa2a46dd64ea7d12641b071622736a89c91e \
  --output ${OLENS_DATA_ROOT}/runs/development-full-grid-v2/final12-analysis-v1.json
```

This produces the required `measurement` plus per-method/family `lengths`. Bare `reporting.summarize()` output lacks the wrapper and lengths required by the whole-cohort script. For a new ready whole-cohort plan, bind this DEV report and this DEV reporting-conditions SHA, the completed reviewed VAL/TEST reports, and current approved implementation hashes. Keep canonical output in TEST order and preserve each stage's own source order. Preserve `whole_cohort_descriptive_v1.prepared.json`; its null reports and historical evaluation pin do not authorize execution.

## Fixed independent trace allocation

After root authorizes review of the complete, SHA-bound TEST artifact, assign three Sol 6.1 reviewers. No new sampling or judge calls are needed:

| Reviewer | Families | Required initial cases for every unique reported contrast |
| --- | --- | --- |
| 1 | Hallucination | Example index 0 from every nonempty category: wrong-to-consistent, consistent-to-wrong, wrong-to-off-topic, wrong-to-empty, unchanged and other class change. |
| 2 | Role binding | Example index 0 for each nonempty win, regression and unchanged category. |
| 3 | Multi-hop and chains | Example index 0 for each nonempty win, regression and unchanged category, separately for each family. |

Use the artifact's full `paired_traces` contrast list, which is determined by the fixed twelve-method menu and reporting code. It includes raw/capped controls, same-budget selection/pooling, A16 versus A32, A32 versus specificity, and each pruning parent versus its matched random deletion. Deduplicate by exact `(baseline_condition, condition)` identity; do not choose contrasts from their measured gains.

The existing sampler sorts cell IDs, takes the first three distinct items in each changed category, and samples up to three unchanged cells using seed 20261010. Review the first existing example in each category for the initial pass. An empty category is recorded as “none observed”; do not manufacture a replacement. These changed-item samples do not guarantee distinct related groups, and unchanged examples can share an item. Root reviews the same cases and all retained examples for the two selected profiles versus raw/capped controls, A16 versus A32, and A32 versus specificity. Any additional public interpretation must identify its exact retained trace; expand only to the already selected indices 1 and 2 when a claim or disagreement needs more evidence.

Each reviewer records artifact SHA, exact contrast, family, category, sample index, cell/item ID, baseline and proposed evidence, a brief manual assessment and any disagreement. Check the original task context and exact text. Distinguish an actual correction from a required-word mention, a correct number inside a wrong calculation, deletion/off-topic output, an unsupported directed role relation, or judge inconsistency. Preserve official verdicts. These are cell-change examples, not proof of a question-level improvement or estimates of failure prevalence. Lead the final result with original question criteria; hallucination keeps its native readout-error denominator. The 469-item union remains descriptive rather than additional held-out evidence.

## Incidental observer exposure

A metadata-only completion check inadvertently emitted the auxiliary raw-N1 hallucination fields `hallucination_stage2.secondary_wrong_over_wrong_plus_consistent` and `hallucination_stage2.assertion_share_over_all_produced_outputs` within the recorded bound 2026-10-10 21:29:11.640535–21:31:56 UTC. No exact dump timestamp was recorded. The disclosure is retained in `${OLENS_DATA_ROOT}/diagnostics/test12-operational-v1/primary-six-completion-contracts-v2.json`, SHA `b0b69992c882e503ab8e016c2090d216b0c3d51491224a6fd5b7b7e4ef8b1758`.

This handoff did not open that receipt or inspect its values. The first-six reporting proposal preceded the exposure; root reported that it did not see the values, and no synthesis, menu change or tuning followed. Preserve this scoped disclosure rather than claiming that every agent had zero incidental outcome exposure.
