# 015 — Consensus support, missing labels, and false semantic merges

Updated: 2026-10-10 UTC. Status: **v4 end-to-end diagnostic completed; v5 helper and manual audit completed; v5 benchmark evaluation pending**. Reviewer: GPT-6.1 Sol. All inspected outputs are development-only.

Consensus has not established an improvement over the released lens. At N=16, ranking bullets by exact repeat counts recovered fewer multi-hop concepts than same-pool best-of-16: **4/24 versus 9/24 cells**. Semantic consensus with a compatibility filter reduced marked contradictions from **40/71 to 20/63 asserting hallucination readouts**, but shortened the average output from about 100 to 21 tokens and reduced recovery in all three other families. This is a coverage/length tradeoff, not established factual improvement.

The initial semantic run also had substantial formatting failures. A repaired run removed that bottleneck: every requested pair received a label, for **$0.19122246** after cache-write accounting correction. However, a fresh qualitative audit still found five clear false merges among thirteen inspected accepted merges. Those five labels were traced to correctly associated raw API responses. Neither version is ready for broad semantic deployment. Exact grouping is unambiguous; repeated claims can still be false.

## Question and frozen inputs

Question: can agreement among independently sampled readouts select useful, faithful bullets at the same candidate budget? Expected failures are repeated hallucinations, removal of rare correct information, false paraphrase merges, and missing labels masquerading as disagreement.

Reuse the model, adapter, fresh captures, pinned WorkspaceBench revision and bank hashes in [002](002-data-evaluation.md). The partial pilot has 189 cells from 31 development items: hallucination 72, multi-hop 24, chain 21 and role-binding 72. Related-group counts are 8, 7, 2 and 4 respectively. The frozen manifest is `configs/splits_pilot_shared_v2.json`, SHA `1183492d6f11b2c8b78c4eddc03d3d601da3ac602b195557d1914077cb5245fd`. The immutable shared N32 pool has SHA `83ce478e1d309167126a9fd4165e24ac9aa450c607d2fee8f579092b1da55992`; B uses its first 16 samples, with no new O-lens generation.

Source bullets remain verbatim. Exact grouping changes whitespace only; one distinct sample contributes at most one vote. Semantic clusters require all-member bidirectional equivalence, preserving every entity, number, negation, relation and qualification. Helpers receive only candidate text and opaque local IDs. They never receive bank context, answers, benchmark IDs or verdicts. Requested nonexact pairs are capped at forty per cell; unexamined pairs remain separate and unknown compatibility causes abstention when that filter is enabled. This gives a lower bound on measured support, not an exhaustive semantic partition.

The offline sweep fixes support fractions 0, .125, .25, .5, .75 and 1, separately switching compatibility filtering on/off. Fraction zero ranks support without a hard cutoff. Final outputs retain at most four intact bullets and 256 Qwen tokens. Compare raw/capped N1, same-pool best-of-16, random-16 and exact support. No matched-length control has yet isolated compatibility filtering from deletion.

## V4 evaluation and instrumentation

Nine v4 conditions at support 0/.125/.25 completed the same 189 cells through the pinned Luna judge with effort `none`, including both hallucination stages. There are no API-missing cells in these completed results. These are per-cell pilot diagnostics; the original full read grids are incomplete, so official any-cell item headlines are not used.

| N16 condition | Hallucination wrong/asserting | Multi-hop recovered/24 | Chain recovered/21 | Role recovered/72 |
|---|---:|---:|---:|---:|
| Same-pool best-of-16 | 40/71 | 9 | 3 | 8 |
| Exact support, no cutoff | 42/71 | 4 | 0 | 8 |
| Semantic support, no cutoff, compatibility off | 39/70 | 4 | 1 | 8 |
| Semantic support, no cutoff, compatibility on | 20/63 | 1 | 1 | 3 |
| Semantic support .125, compatibility off | 11/34 | 1 | 1 | 3 |
| Semantic support .25, either compatibility setting | 0/1 | 0 | 1 | 0 |

The .25 semantic arm emitted empty output in **178/189 cells**. Its zero marked contradictions are therefore not success. The .125 arm was empty in 32/72 hallucination, 19/24 multi-hop, 3/21 chain and 46/72 role cells. Soft compatibility filtering emitted nonempty outputs but usually only one bullet: mean 20.97 tokens/1.08 bullets versus best-of-16's 99.52/3.99. Assertion share is 63/72, rather than silently discarding its generic outputs from the denominator. The complete artifact includes off-topic classes, true/unverifiable/false tallies and stage-2 coverage; false spans and enumerated claims are not uniformly segmented precision.

Paired uncertainty resamples whole related groups, using 2,000 draws and seed 20261010, with ratios of summed cell contributions. Semantic soft ranking without compatibility changed hallucination error by −0.0062 versus best-of-16, with interval [−0.1223, 0.1106]. Exact support reduced multi-hop recovery by 0.2083, interval [−0.3704, −0.0476]. Compatibility filtering's larger contradiction decrease coincides with substantial recovery/length losses. Chain has only two independent template groups; a narrow numerical interval cannot establish broad generalization.

V4 made 492 paid calls: 103 invalid responses, 67 retries, and 36 exhausted logical calls. Fifty-four cells had no verified pairs. Quote-offset validation and duplicate proposals caused most failures. Corrected usage-derived cost was $0.315751075 (prior tariff $0.2976589): 862,954 input and 443,058 output tokens, 728.45 seconds with four request slots/eight queued cells; median/95th-percentile latency 6.51/11.56 seconds. This run is an instrumentation-limited end-to-end diagnostic, not a clean finding that consensus is futile. Original responses and failures remain preserved.

## V5 repair, fresh audit, and decision

V5 retains the semantic instruction but uses strict local pair IDs and complete source text stored locally, removing generated quote offsets. Duplicate proposal bookkeeping is repaired deterministically without interpreting missing labels as unrelated. There were 378 physical requests, one invalid response successfully retried, **zero exhausted comparisons**, and all 2,685 requested labels present. Some cells proposed no nonexact pairs; that is distinct from a failed matcher. Actual usage was 765,208 input/192,883 output tokens, including 1,421 cached input tokens and 735,522 cache-write tokens; corrected cost $0.19122246 (prior tariff $0.17283441); elapsed 444.84 seconds, four slots/eight queued cells, latency median 3.53 and 95th percentile 11.22 seconds. No GPU work was required by the helper.

The fresh audit selected forty distinct text pairs, ten per family, excluding the earlier sixty audit pairs. It targeted accepted/rejected/uncertain strata; three extra multi-hop pairs filled its sparse accepted stratum. This is a qualitative development audit, not a population error estimate, and templates/items may overlap earlier audits. Of thirteen accepted equivalence labels, five were clearly unsafe, five reasonable and three suspect. Examples include not Chloe versus not Mia; different arithmetic histories sharing leading 15; resentment versus further conflict; and omitted brief-apology or stand-up-show qualifications. Exact source-group bytes, local pair IDs, physical requests and raw responses agree for all five clear cases, excluding a bookkeeping explanation for these errors. Four pairs actually share native clusters with support 2/16; the Chloe/Mia edge is blocked by the all-member clique safeguard. Their native .25 outputs are empty, while softer variants can use the four incorrect support groups. Label mistakes and actual clustering effects are therefore reported separately.

The frozen restatement/temporal veto catches only one of those five. Exporting it off/on makes this conservative heuristic visible; it is not proof of verified equivalence. V5's native .25 setting still empties 178 cells, now without missing requested labels. Soft alternatives are exported but their benchmark evaluation is pending. No semantic method is promoted based on these manual labels or low error from abstention.

Representative paired traces are retained in `paired-analysis.json`: two apparent hallucination wins reduce four bullets to one greeting or identity bullet; a regression substitutes another excluded human name; multi-hop loses a correctly recovered name amid changed formatting; chain removes explanatory content naming hidden intermediate 5 and retains bare 12; role outputs lose father/daughter or named binding details. A lawyer/witness apparent win remains a wording/measurement hypothesis. The artifact includes deterministic first wins/regressions and seeded unchanged cases, with complete texts and judge evidence. These examples explain failure mechanisms, not cherry-picked proof.

Decision: retain exact support as a same-budget comparator; evaluate only bounded v5 diagnostic variants, preserving native/veto and compatibility ablations. Do not expand semantic merging without addressing these false matches. The helper-only reasoning-effort comparison has now completed and is recorded separately in [017](017-helper-effort.md); it does not replace v5's frozen none-effort labels. Practical effect, traces, collateral losses, cost and uncertainty govern follow-up; there is no significance gate.

## Artifacts and reproduction

Durable root: `${OLENS_DATA_ROOT}/`.

- V4 reports/audits: `runs/helper-semantic-pilot-v1/`; selections/paired analysis: `selections/consensus-pilot189-v4/`, selection SHA `83157a6390d705b37507da2a83e2096c7c54e0271f27b95cd756c5a835ba3e95`; completed judges: `runs/development-shared-pilot-v2/judgments-b-v4/`.
- V5 reports and costs/fresh audit/mapping audit: `runs/helper-semantic-repaired-pilot-v1/`; report SHA `b9d1bcda9a264e9e1c6cf936e9129f064f0930f0468758aaf1020c75637d7bed`; fixed thirty-condition export: `selections/consensus-pilot189-v5/`, SHA `b62fe86e283a101d8723fa153f4a4cd33e6f08fefba8204b00d634db11c163b8`.
- Reproduction: `scripts/helper_pilot.py`, `scripts/export_consensus.py --label-version v4|v5`, and saved preparation/audit scripts. Runtime is `configs/runtime.json`; code follows milestone `bab0ce4` with the versioned v5 repair patch. Stochastic texts, physical response IDs and complete prompts stay outside Git. Cheap threshold summaries can be regenerated.

Validation/test access: none. Helpers never see these evaluation verdicts or manual audit labels. Six informative v5 conditions are queued behind the active full-development donor shared-cache writers. The all-candidate diagnostic and full-development baseline judging have completed. Medium confirmation of the frozen v5 requested pairs has completed and is being audited separately; benchmark judging remains effort none. These results concern whole-bullet equivalence, not atomic-claim consensus. Cost corrections are recorded in [022](022-pricing-correction.md), with preserved historical amounts and usage-derived pricing rather than invoice reconciliation.
