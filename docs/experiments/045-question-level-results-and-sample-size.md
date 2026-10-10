# Question-level results and sample-size limits

Decision recorded 2026-10-10, approximately 17:20 UTC, before inspecting TEST outcomes.

The three recovery families should lead with their original question-level
outcomes. Multi-hop requires every required bridge at the same layer, then
credits a question if any prescribed layer passes. Arithmetic intermediates
uses the original any-passing-final-token-layer rule. Role binding requires
the actor, action and recipient together at one prescribed site, then credits
any passing site. This measures whether the required information can be
recovered somewhere on the fixed grid, not correctness of every readout or of
the target model's final answer.

Hallucination retains its original error ratio over specific readouts:
wrong / (wrong + off-topic + consistent). It is not question accuracy, and its
complement is not a correctness score. Assertion share, off-topic outputs,
empty outputs and examples remain necessary companions.

The dashboard will default to question-level recovery while preserving the
per-activation diagnostic toggle. This changes presentation only: no metric,
judge verdict, frozen setting, source grid or statistical calculation changes.
The held-out view may appear only after all twelve comparisons are complete
and their analysis has been reviewed. Existing development and validation
evidence must remain labeled as such.

## What the current sample actually contains

Counts verified against `configs/splits_v2.json` and the three inference
manifests. Entries are questions / related groups.

| Family | Development | Validation | Held-out test | Whole bank |
| --- | ---: | ---: | ---: | ---: |
| Hallucination | 30 / 30 | 20 / 20 | 99 / 99 | 149 / 149 |
| Multi-hop | 31 / 29 | 20 / 17 | 49 / 48 | 100 / 94 |
| Arithmetic intermediates | 30 / 7 | 20 / 7 | 70 / 28 | 120 / 42 |
| Role binding | 30 / 15 | 20 / 10 | 50 / 25 | 100 / 50 |
| Total | 121 / 81 | 80 / 54 | 268 / 200 | 469 / 335 |

Groups control known dependence conservatively; their construction does not
prove every group is independent. Twenty validation questions are inadequate
for stable rankings of close methods: one question changes the rate by five
percentage points. Thousands of sites or additional bootstrap draws do not
increase the number of independent questions. The held-out sample is larger
but still cannot be assumed to resolve small differences within each family.

## Execution and interpretation

Finish the unchanged twelve-method/control TEST menu and the same twelve on
all 469 released questions. The latter is explicitly descriptive: development
and validation informed choices, so their union cannot become a larger
untouched test. Preserve prospective primary/secondary comparisons and the
existing paired whole-group intervals. The two selected operating settings
are practical choices, not established winners. No method is ruled out merely
because its pilot interval is wide; failed instruments and unrun variants
remain separately identified.

The twelve comparisons do not represent every exploratory setting from all
seven approaches. Report the coverage inventory explicitly. Final conclusions
must distinguish improved reconstruction, recovery at some site, fewer
contradictions and actual evidence of more faithful explanations.

If meaningful alternatives remain unresolved, a follow-up needs genuinely new
questions: disjoint conversations and bridge concepts, new role pairs and new
arithmetic operation-template groups. There are no unused questions in these
four frozen banks. More seeds, role reversals, number substitutions or layers
do not automatically add independent groups. Other released families measure
different tasks and are not extra observations for the existing endpoints.

An indicative follow-up planning scale is about 200 independent groups per
relevant family, subject to a calculation using development paired variability
and an explicit smallest useful effect. This is not a power guarantee, an
authorized new data-generation run or a promise to resolve five-point gains.
Freeze any extension's size, methods, scoring and stopping rule before its
outcomes; keep it distinct from the original benchmark comparison.

## Comparability

Multi-hop already uses the released deterministic regex contract, not an
auxiliary Luna multiple-choice score. Hallucination, arithmetic and role
judging use the declared GPT-6 Luna override. Their results must not be passed
off as identical instruments to published numbers using other judges.

Source checks: `src/olens_improve/evaluation.py` selects the regex contract;
`src/olens_improve/reporting.py` checks original item headlines; the pinned
WorkspaceBench family scorers define the aggregation. Independent review by
`adversarial_evaluation` read source and manifests only, not TEST outcomes.

## Publication

Site version7 was published successfully at17:36UTC. Sixteen focused tests, independent source review and desktop/mobile checks passed. Synthetic TEST fixtures cover both stages, scopes and all twelve methods; actual TEST outcomes remain uninspected. The public view is still validation, now defaulting to question-level recovery. Scientific objects and map downloads are unchanged. Source and deployment evidence are bound by `configs/question_level_overview_review_v1.json` and `configs/public_dashboard.json`.
