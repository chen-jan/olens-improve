# Final presentation candidate assembly

Prepared source-only procedure, not final assembly or root approval. The new helper `scripts/assemble_expansion_final_review.py` adapts the historical progress assembler without modifying that file, the V3 draft, generators, or waiting scientific services. It creates an explicitly **unreviewed** candidate and a reference-accounting receipt in new absent paths. No paid calls, fitting, statistics, winner selection, publication or Git action occurs.

Current assembler SHA: `9e5243af2d3b307bdfcbee4ffb1086081578e1404a27aae51d6898e33a86f3b8`. Tests: `tests/test_expansion_final_review_assembly.py`, SHA `d6c2e728276d56a4519e6cceeeb0f1432d47e9571286b3df024d316a8fa46312`. Offline evidence: `.state/expanded-final-review-assembly-checks-v1.json`; nine pure tests pass, and a read-only historical replay preserved all1771 existing approved entries,1695 distinct identities and all330 prior reviewed references with zero additions. These checks do not attest final scientific inputs.

## Input boundary and evidence preservation

The helper requires terminal native/reconstruction states and retained output hashes, the sealed32-descriptor native receipt, numeric source receipt, complete terminal effort/receipt, final cap/parent packs/index, complete merged human notes, and all four final reviewer files. It verifies the finite70 menu/full280 reconstruction rows, no missing selections, manifest/native identities, merged source pins and inherited review proofs. Invalid fit availability and interval warnings are retained in the bound artifacts. It never replaces source means, common-valid masks, paired intervals or counts.

The prior V16 review is pinned to `c9a5d4ea…`, and the unchanged V3 draft to `d1889a8c…`. Preserve all1771 old `dashboard_examples` dictionaries and their order verbatim, including76 historical repeated identities and591 entries whose reference is supplied implicitly by their original source case. All prior qualitative/review source records remain. Final qualitative packs are appended with their exact hashes; final index, merged notes, all four reviews, numeric/effort artifacts and receipts, terminal states, prior review and draft are added to `review_sources`. The merger's full source map also retains older index/review and full-context inheritance provenance.

Only final merged `new_case_notes` are eligible additions. Before/after official output objects, complete source context, case policy/category and reference-specific original-grid evidence must match the exact source case. Resolution prefers a complete recorded parent even when it is also the original capped baseline. New dual cap/parent copies deduplicate by condition/family/kind/cell/reference, with parent evidence preferred. Original-grid core counts and shared witness fields must agree; parent-only witness fields may enrich a capped schema. A null capped-grid record may reuse richer preserved parent evidence. A new non-null grid may not silently reuse an old null grid. Changed context/official pairs or conflicting grid counts fail rather than being merged. Every final source reference remains in the receipt's reference-to-display mapping with its human review path/hash. New-reference and displayed-entry counts derive from exact objects; neither330 nor295 is assumed for final additions.

## Human narrative contract

Optional `--narrative` is a separate human-authored JSON containing only `headline`, `resource_summary`, `findings`, `method_findings`, `recommendations`, `presentation`, `condition_findings`, and/or `limits`. Supplied fields replace their draft counterparts; a supplied `presentation` must therefore be complete. Source identity, root approval and dashboard examples cannot be rewritten through this overlay. Without it, calibrated draft prose remains explicitly pending.

The output always has `status=final_candidate_pending_root_human_review` and `root_reviewed=false`; builders must reject it until root finishes actual prose/evidence review and creates a separately approved root review. Exact evidence bindings resolve, but root still owns seven approach interpretations, all28 family-specific correctness-versus-fit notes, action titles, hypotheses, and the final chosen-output editing example. Keep the main declared editing round2→pooled D32 comparison distinct from the chosen example's actual eligible parent/round1 lineage. Keep selection's all14 plots, up-to-six other group representatives, all70 quality/reconstruction appendices, raw/capped labels, actual pp gains/common-valid coverage/CIs and undefined or degenerate interval warnings. The helper supplies no new conclusions.

## Terminal-only command recipe

This command is a dependency recipe, not a launch instruction or a claim that final sources currently exist. Run once after actual final reviews and root's helper review, on the existing owned CPU with explicit single task. Choose new absent candidate/receipt paths. No allocation is created.

```bash
srun --jobid=25536417 --overlap --ntasks=1 --cpus-per-task=1 --mem=4G --cpu-bind=cores ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python scripts/assemble_expansion_final_review.py \
  --prior-review docs/reviews/root-expansion-progress-v5.json \
  --draft .state/expanded-final-review-draft-v3.json --inventory configs/expansion_manifest_v1.json \
  --native ${OLENS_DATA_ROOT}/expansion-v1/analysis/final-v1.json \
  --native-state .state/expanded-final-native-v1.service.json --native-receipt .state/expanded-final-native-ready-v1/receipt.json \
  --reconstruction ${OLENS_DATA_ROOT}/expansion-v1/reconstruction/final-v1.json \
  --reconstruction-state .state/expanded-final-reconstruction-v1.service.json --reconstruction-receipt .state/reconstruction-analysis-final-ready-v1/receipt.json \
  --effort ${OLENS_DATA_ROOT}/expansion-v1/analysis/effort-final-v1/effort.json \
  --effort-receipt ${OLENS_DATA_ROOT}/expansion-v1/analysis/effort-final-v1/receipt.json \
  --cap-pack ${OLENS_DATA_ROOT}/expansion-v1/qualitative/final-v1.json \
  --parent-pack ${OLENS_DATA_ROOT}/expansion-v1/qualitative/parent-comparisons-final-v1.json \
  --index ${OLENS_DATA_ROOT}/expansion-v1/qualitative/final-delta-index-v1.json \
  --merged-notes docs/reviews/expanded-qualitative-final-merged-notes-v1.json \
  --final-review root=docs/reviews/expanded-qualitative-final-root-v1.json \
  --final-review agent_1=docs/reviews/expanded-qualitative-final-agent1-v1.json \
  --final-review agent_2=docs/reviews/expanded-qualitative-final-agent2-v1.json \
  --final-review agent_3=docs/reviews/expanded-qualitative-final-agent3-v1.json \
  --narrative .state/expanded-final-human-narrative-v1.json \
  --output .state/expanded-final-review-candidate-v1.json --receipt .state/expanded-final-review-candidate-v1.receipt.json
```

The narrative path is proposed and pending human authorship. No candidate has been generated. All terminal sources are hashed again before exclusive output creation. Preserve a failed attempt for root review; do not reseal sources, restart services or overwrite artifacts.
