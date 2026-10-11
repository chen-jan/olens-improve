# Prospective editor reconstruction intake: independent review v1

Reviewed read-only on 2026-10-11, before any actual editor terminal score journal existed. This is an offline implementation review, not an attestation of editor measurements. No live GPU source, dispatcher, bridge, prior numerical artifact, or owner source was changed.

The canonical event digest is correctly separated from the raw pretty-printed spec-file SHA. The faithful serialization fixture has raw SHA `d7f558f96a86617f70f5cc2e435209d41056faf6d58c4a33c26ece4b6bdca6d5` and canonical event digest `7f11379941549b0455d53a8928aba2c927ddcf90792009eba133cda3e19c116b`. Neither substitutes for the other. All six focused tests passed independently in 0.052 seconds. All 11 whitening hashes equal the exact original V3 numeric source pins; the four approved encoder/scorer source files match their authority hashes. The source-only V3-to-V4 diff leaves grouped summaries, paired masks, bootstrap formulas, tolerances and numeric row aggregation unchanged. It adds editor authority checks, distinct raw/canonical linkage, required snapshot inputs and audit fields.

## Actionable validation gap

`scripts/expanded_editor_fit_intake.py:66,71` reads the first occurrence of a CLI flag with `command.index`. Python argparse, used by the real encoder, takes the last repeated ordinary flag. A synthetic otherwise approved task with an appended `--whitener-directory unapproved-last-value` and a recomputed matching service-task signature passes this helper. Thus the helper alone does not prove that the effective runner arguments equal the validated arguments. Reject duplicate flags, unsupported extra options, missing values and unexpected positional arguments before resolving any task; add a fixture where the completed-task signature also matches the duplicate command, so signature mismatch does not accidentally test the wrong guard.

All four actual queued round1 commands have unique flags. This is prospective offline hardening, not a current producer failure or reason to restart a live service. The root-approved immutable terminal snapshot remains essential: a task signature binds bytes, while its trusted successful-service receipt establishes that those bytes ran. Before final extraction, retain the full successful receipt (`task_sha256`, nonnegative finite `seconds`, finite `finished_unix`, owned `job_id`) and match task family/round metadata to the selected folder/spec. Do not invent an event normalization record: the actual event does not carry one. Approved scorer code, exact effective CLI arguments and original whitening hashes establish normalization authority.

## Final real-artifact checks still pending

Freeze a new immutable dispatch snapshot only after the relevant tasks are terminal, keeping raw queue/service observation hashes separate from immutable task/receipt pins. Validate the actual pretty spec raw SHA, canonical digest in every event, exact family/site activation identities, unique full cohort, and emitted text/token/bullet counts against the quality-selected output. Check finite FVE and explicit empty-output zero; retain scored first32-token atom scope separately from full prose correctness. Preserve related-group common-valid masks and intervals. Revalidate raw files at extraction end. These checks cannot be claimed complete from synthetic fixtures or a queued command.

## Source pins at review

- `scripts/analyze_expansion_reconstruction_v4.py`: `3fc2e4e031f117232ff7612f08e9927528f0b1d8cc749837e618c40bb91cca73`
- `scripts/expanded_editor_fit_intake.py`: `58763fd7ce175babc0efca2157f90d893ea81b0f4ce4afa60b932789838a048c`
- `configs/expansion_editor_fit_intake_v1.json`: `fe88d843424bf7c9bdc0b51d7796613ba77602f77ff2ba237b3931cab5260d61`
- `tests/test_expanded_editor_fit_intake.py`: `984581c8bbfa545b3acba9fc32e38f15a6b3f5242a0459e3a63dcc7f79808b48`

Original numeric authority: `${OLENS_DATA_ROOT}/expansion-v1/reconstruction/first-live-v3.json`, SHA `c7d6ee68c9481fc52e7bbbd01cda416c416b8f8bf15854a730977e958ded7e75`.
