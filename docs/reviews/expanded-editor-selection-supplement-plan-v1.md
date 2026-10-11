# Terminal selected-edit accounting supplement

Prepared for root review; **not launched**. This adds descriptive provenance/text-identity counts for the two frozen editing settings. It performs no fitting, resampling, judging, proposal generation or method selection, and changes no producer, source menu, budget or hold.

The approved final v5 reconstruction already exports common-valid paired fit masks and counts at the recorded `1e-5` site-change tolerance. It does not export selected candidate origins or byte-identical output counts. Reuse its existing fit comparisons verbatim; do not create a second numerical extraction.

## Readiness and immutable sources

Run only after the native and reconstruction gates both reach `complete_pending_root_review`, their supplied output hashes match, native scientific input validation is complete, and all 280 canonical condition/family selection units are present. All eight round/family editor journals must have exact successful immutable task receipts in final reconstruction's `editor_fit_authority_audits`. The final numerical artifact must be diagnostic version 5, bound to that exact final native SHA and manifest `753b2d9c…`, with the approved v5/helper-v2 implementation hashes. A partial numeric *fit-availability* status is allowed: invalid/unavailable fits remain explicit even though all selections are terminal.

Use the final aggregate's independently pinned raw spec, status, proposal, cohort and scored-journal sources. The supplement does not read the mutable live GPU queue/service as task authority. Each copied task is linked to its successful receipt by `SHA(json.dumps(task,sort_keys=True))`; event linkage separately uses the exact compact canonical spec digest. Cohorts, activation/item/layer/position/split identity, scored candidate sets and retained R1 candidate identities are checked. The spec records valid scored IDs; rejected IDs are separate and cannot be counted as a valid selected proposal. All files actually used, terminal gate states and supplemental source code are SHA-pinned before/after intake. Existing supplemental output is never overwritten.

## Definitions and output

`scripts/summarize_expansion_edit_selection.py` writes eight rows, one per family and round, with:

- Selected original eligible parent, selected prior-round edit, or selected new current-round edit counts. An R2 candidate with `origin=editing_round1` is inherited even if its source was an R1 proposal that was not R1's selected best. Exact current proposal identity is required for a new-current-round classification.
- Exact full-text equality/change versus each available initial pooled/best32 parent, and R2 versus the previous round's selected output. Whitespace and full unscored suffixes remain part of this comparison. Unavailable parent text comparisons are counted separately.
- For selected current-round proposals, equality/change versus their actual `parent_candidate_id`, independently of origin. A new ID with identical text counts as a newly selected proposal **and** unchanged text; these are different facts.
- Existing v5 parent comparison site counts (`paired_sites`, intended/missing pairs, improved/worsened/within-tolerance counts), copied with exact source row/comparison indices. No means or CIs are recomputed. Missing fit-change fields for no common-valid sites remain missing rather than becoming fabricated zeros. The exact raw numeric artifact remains the authority for means, masks and intervals.

The origin categories partition selected cells; text comparison denominators are reported separately. These counts describe accepted candidate provenance and exact text retention, not semantic truth, quality gains, editing efficacy prevalence in other runs, or causal mechanisms.

## Executable terminal procedure

Root review is required before this separately prepared supplement is run. Read `FINAL_NATIVE_SHA` and `FINAL_RECONSTRUCTION_SHA` below from the corresponding terminal states and independently compare them to the files' SHA256. Output path must be absent. Run once on existing analysis CPU25536417 after its extraction gates finish, using the explicit single-task setting; no allocation is created.

```bash
srun --jobid=25536417 --overlap --ntasks=1 --cpus-per-task=1 --mem=4G --cpu-bind=cores ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python scripts/summarize_expansion_edit_selection.py --native ${OLENS_DATA_ROOT}/expansion-v1/analysis/final-v1.json --native-sha256 FINAL_NATIVE_SHA --native-state .state/expanded-final-native-v1.service.json --reconstruction ${OLENS_DATA_ROOT}/expansion-v1/reconstruction/final-v1.json --reconstruction-sha256 FINAL_RECONSTRUCTION_SHA --reconstruction-state .state/expanded-final-reconstruction-v1.service.json --output ${OLENS_DATA_ROOT}/expansion-v1/reconstruction/editor-selection-final-v1.json
```

Do not submit now: terminal guards currently remain pending. No supplemental watcher or automatic launch is installed. After successful output, root reviews the exact artifact hash and provenance before integrating selected-edit counts into the final effort/report; existing eight fit audits remain unchanged. A guard failure leaves the source data untouched and needs review, not automatic resealing or production restart.

## Bounded offline validation

Four pure offline fixtures pass using `python -m unittest discover -s tests -p test_expansion_edit_selection_supplement.py`. They distinguish R2 inherited edits from new proposals, reject changed inherited text, preserve a new candidate whose text is byte-identical, preserve whitespace changes, reject wrong origins/unregistered proposal IDs, and copy common-valid fit counts while retaining unavailable comparisons. These fixtures do not launch the terminal intake or prove the currently unfinished final sources.

The separate four-anchor preliminary dossier is `docs/reviews/expanded-editing-fixed-anchor-preliminary-v1.json` (SHA `544fef0b75c0665c3ad70fc5772ac2b0c7c7bec0bf9a2ee48efccb97ae7646b4`). Its unchanged pooled-parent observations are illustrative; they must not substitute for these terminal whole-cohort descriptive counts.
