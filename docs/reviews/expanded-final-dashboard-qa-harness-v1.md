# Final-only dashboard browser QA harness V1

Status: prepared, offline guards passed; no final browser run or final artifact is attested. The harness copies the preserved14-view progress harness and replaces historical counters/source hashes with explicit immutable final authority. It does not change dashboard builders, runtime services or scientific endpoints.

## Sources and parameter contract

Harness `.state/check-real-dashboard-final-v1.mjs` requires unique named flags (no positional legacy interface):

| Flag | Contract |
|---|---|
| `--chrome` | Existing Chromium executable; not launched in preflight. |
| `--html` | Absolute path to an actual final candidate `index.html`; exactly one embedded JSON payload and sibling `expansion-data.json`, `expansion.js`, `expansion.css` required. |
| `--report` | Absolute absent output path; parent directory must exist for browser mode. Screenshots/log destinations must also be new. |
| `--review` | Exact immutable final root review JSON, `status=root_reviewed`, nonsynthetic. |
| `--native` | Exact reviewed final native JSON, `complete_exploratory`,70×4 complete rows, zero missing source units, complete frozen contrast family. |
| `--reconstruction` | Exact root-bound280-row reconstruction JSON with zero missing selection sites, reviewed objective/vector/solver, and final-native SHA binding. Partial diagnostic status from genuinely invalid/unavailable fits is permitted only with terminal numerical gate; it is not scientific incompletion or certainty. |
| `--effort` | Root-bound `complete_retrospective` effort JSON and sibling terminal receipt bound to final native. |
| `--qualitative-notes` | Exact complete count-derived final merger JSON, root-pinned via `review_sources`, same native/manifest SHA, all fresh/inherited references and no missing reviewer partition. |
| `--inventory` | Exact sealed70-setting manifest; four families and declared comparisons derived from it. |
| `--native-state`, `--reconstruction-state`, `--qualitative-state` | Optional path overrides for immutable terminal authority. Defaults are `.state/expanded-final-{native,reconstruction,qualitative}-v1.service.json`. Native canonical32 receipt and qualitative output hashes are checked. |
| `--original-whole`, `--original-report` | Optional preserved-original path overrides; defaults match unchanged dashboard builder. Original raw sources are hashed independently. |
| `--preflight` | Check all final inputs/candidate source objects, print source contract and exit without Chromium. It is not a shortcut for missing/partial/unreviewed inputs. |

Unknown/repeated/incomplete options reject. All direct source files, declared root review sources, referenced qualitative packs, terminal states/receipts, final HTML/sidecar/assets are pinned on intake and rehashed after interactions. Larger scientific source-pin maps are summarized by canonical-map digests; this presentation check does not independently rerun judge/statistical verification.

## Exact data and count derivation

The frozen manifest supplies70 active IDs and280 condition-family expectations; native output supplies the full declared paired contrast set. Metric rows must be unique and equal to the expected native rows. Each declared comparison must occur exactly once with identical source values, masks/intervals/warnings; retained original comparison diagnostics may coexist without duplicating metric rows. No extra statistical menu is invented.

Reconstruction/resources/method findings and every rendered before/after/context/local official evidence/whole-grid witness object must equal the expected immutable artifacts. Root review `qualitative_sources` supplies exact packs and `dashboard_examples` supplies chosen source-hash/family/kind/cell/reference/title/analysis records. Resolution follows current parent-first builder behavior: a complete matching `case.parents[reference]` wins, then original-baseline fallback only when no matching parent exists; an incomplete matching parent rejects. Exact prose and official/context objects are compared; JSON whitespace is normalized only for serialized `context`/`evidence` strings, while raw input SHA pins remain retained.

Expected displayed entry count is the sum of the **final root review's resolved dashboard example arrays**, not a cap-pack count and not the merger's reference count. Unique condition/family/kind/cell/reference identities and repeated approved identity entries are reported separately. Current V16 root review has1771 approved entries,1695 unique identities and76 repeated identities; those are historical observations only, never hardcoded final expectations. Existing approved entries are not retroactively removed. The final merger's required/reviewed new-reference counts, inherited-reference count, prior audited count and all four partition loads are separately recorded from that exact merger file.

The harness prefers an actual reviewed editing-round2 entry for the audited-example interaction if present, otherwise a reviewed consensus or first available entry. It has no assumed chain0385 case. All14 desktop/mobile overview, quality/variance detail, scaling, resources, likelihood/pruning and audited-example views are retained. Source objects must match the preflight embedded data before interactions and remain byte-equivalent afterward. Additional checks verify raw FVE formatting, parent labels/pp changes, actual reconstruction CI title values, quality errorbar axis endpoints (and absence when CI unavailable), scaling tooltip/means, opacity, exact resource cards, clipped ticks and horizontal overflow. No draft browser run occurs.

## Command at the actual final boundary

Run only after root's final review/source assembly and all terminal artifacts exist. Use an existing owned CPU step after checking resource headroom; no allocation is requested here. Command parameters below are explicit and must point to root's actual chosen immutable final review/build directory, not `.state/expanded-final-review-draft-v3.json`.

```bash
${HOME}/.nvm/versions/node/v24.14.0/bin/node .state/check-real-dashboard-final-v1.mjs --chrome ${HOME}/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome --html /ABS/FINAL/dashboard/index.html --report /ABS/FINAL/dashboard/qa.json --review /ABS/FINAL/root-expansion-final-v1.json --native ${OLENS_DATA_ROOT}/expansion-v1/analysis/final-v1.json --reconstruction ${OLENS_DATA_ROOT}/expansion-v1/reconstruction/final-v1.json --effort ${OLENS_DATA_ROOT}/expansion-v1/analysis/effort-final-v1/effort.json --qualitative-notes ${OLENS_REPO_ROOT}/docs/reviews/expanded-qualitative-final-merged-notes-v1.json --inventory ${OLENS_REPO_ROOT}/configs/expansion_manifest_v1.json
```

For a read-only final preflight use the same command plus `--preflight`. Browser mode writes14 screenshot files, `qa.json` with source authority/counts and `layout-chromium-stderr.log`; it requires new destinations and preserves sources. Retained screenshots need visual inspection by root. Local Chromium does not attest hosted rendering or native PowerPoint parity.

## Offline validation and unrun boundary

Current source passes `node --check`. Six allocated-free short Node argument/source guards reject: missing required arguments, unknown option, duplicate option, absent expected final source, actual unreviewed V3 draft, and actual partial native V3 source. Fake browser marker and report remain absent. The current receipt is `.state/final-dashboard-harness-guards-v1/receipt-v2.json`; the prior unlaunched test/harness prototype remains retained in that directory. No positive final preflight/browser attestation is possible while final artifacts/review are absent.

## Public example assembly required before the command

The presentation V3 draft contains seven slide contracts, six reviewed examples and pending editor fields, but **does not contain populated `qualitative_sources` or `dashboard_examples`**. Passing its structural slide validator does not prepare public dashboard cases. Final root review must populate both fields and pin final merger/qualitative packs via the existing schema. Dashboard builder has no direct qualitative CLI; it resolves these reviewed records.

Safest source-bound assembly recipe, pending actual final reviews:

1. Preserve `docs/reviews/root-expansion-progress-v5.json` (V16, c9a5...) and its existing1771 `dashboard_examples` item arrays verbatim, retaining all old qualitative source path/hash records. It already preserves the older1476 entries plus295 new entries representing330 reviewed references. Do not rebuild the old slice from a raw pack or accidentally loop the final merger's nested prior330 bundle again.
2. Use `.state/assemble-root-progress-v5.py` as a pattern only, in a new final-only helper such as `.state/assemble-root-expansion-final-v1.py` after root review. The old helper hardcodes330/295 and V3/effort hashes and must not be executed unchanged. Start from the existing V16 review, merge only terminal final `new_case_notes` with root-approved prose, and derive all counts from the final index/merger.
3. Append exact final cap/parent pack records to `qualitative_sources`. Bind the final index, merged notes, four final review files, final numerical/effort artifacts and relevant authority receipts in `review_sources`/existing top-level SHA fields. Root supplies final method findings/task notes/headline/effort interpretation independently; stale operational-pending prose must not masquerade as final evidence.
4. Each new reference resolves the exact full case and named actual parent first, then fallback only if no matching parent exists. Verify before/after/context and local official evidence against the merged source reference. Retain original-question witnesses and site-versus-question distinctions. Build identity `(condition,family,kind,cell_id,reference)` for **new additions**, collapse exact cap/actual-parent copies, prefer actual-parent pack metadata, and compare every collision with existing approved entries before deciding it needs no new UI entry. Preserve all existing1771 entries, including approved legacy repeated identities; final entry count is1771 plus derived distinct additions, not plus raw merger references.
5. Produce a separate source-check receipt linking every new reviewed reference to its displayed entry or exact retained old entry, with exact text/context/official equality and relevant grid metadata. Do not silently dedup changed official/context evidence. `.state/audit-dashboard-progress-v5b.py` is the existing preservation/reference audit pattern; its1476/295/330/1771 counts and historical SHAs must be replaced by count-derived final values in a new helper. Verify all old UI scientific text and evidence remain unchanged.
6. Current `scripts/build_expansion_dashboard.py` resolves matching complete parents before the original-baseline branch. Preserve that parent-first metadata correction; do not reintroduce the old original-first ordering when reference equals capped baseline. `.state/dashboard-parent-witness-tests-v1.json` records11 passing fixtures, SHA777a5b1b36f171509b2c867efc4b1e3001907c44870e7b2a315d82b36b72102f. V5b source audit observed76 old endpoint metadata enrichments versus V4 and no scientific text/official outcome changes. Final assembly should not strip this witness evidence.
7. Choose/root-review one terminal full selected editor case with exact named reference before text, actual eligible parent and round1 lineage separately. Primary aggregate editing comparison stays round2→pooled D32, A32 secondary; a different selected qualitative parent must be labelled clearly. No inference from unselected proposals. Reverify six historical slide candidates against final overlap and retain calibration.

No final cases, final review authority, final count or public additions are synthesized by this preparation. Root handles actual assembly review and publication; API owns the completed final review merger/deck, CPU owns terminal packs/index.

## Exact current source pins

| Source | SHA-256 |
|---|---|
| `.state/check-real-dashboard-final-v1.mjs` | `847fc813ee46d694aa1215d1f45289317d10ff18c12559effb8d7607a1ff19fc` |
| `.state/check-real-dashboard-v5b-rerun.mjs` | `ba5a574c60f18e0582a4978cf72e4d21a1c43966180e1f4ab740da781284b279` |
| `.state/final-dashboard-harness-guards-v1/receipt-v2.json` | `578c5a0239b972993d76bf8b1fc3b0b615177bee2e6679cca4fef19914c309e5` |
| `scripts/build_expansion_dashboard.py` | `761941ffb677beb5c6d374fbbf52cb0c2701f0af4567dbed491c1c0d55bd2d43` |
| `docs/reviews/root-expansion-progress-v5.json` | `c9a5d4eaaf376a6b56bd0a9a6ce858ab7e0667638ff1c06a3d539efefa115b84` |
| `.state/assemble-root-progress-v5.py` | `3626d5fe7c8e2a0e6775f8d0c22f3db1646df0bfaaf839f37cc6e34458e8dafd` |
| `.state/audit-dashboard-progress-v5b.py` | `c113dfe8ed21ab7785975f5c835b6756866f953a5e7931fc1bf0bc6e9a8f6a77` |
| `.state/expansion-dashboard-audited-progress-v5b/source-check.json` | `68a536cb3543ca516a7a9cb90924d4b735282f234658fb74c1cd09a31cff014c` |
| `.state/dashboard-parent-witness-tests-v1.json` | `777a5b1b36f171509b2c867efc4b1e3001907c44870e7b2a315d82b36b72102f` |
| `.state/expanded-final-review-draft-v3.json` | `d1889a8c31c5422b5805577cf00e8df9b353e81af9ac84a79a72a5c9bb17b2f7` |

Prepared 2026-10-11T05:23:18.360979+00:00. No actual final browser invocation, service mutation, new allocation/calls, Git or publication.

## Tracked exact source copy

Root preserved the prepared harness byte-for-byte in `scripts/check_expansion_dashboard_final.mjs` for local Git delivery. Its SHA remains `847fc813ee46d694aa1215d1f45289317d10ff18c12559effb8d7607a1ff19fc`; the original `.state` copy and guard receipts remain unchanged. Use the tracked script with the same named arguments at the actual final boundary. This copy is not a browser execution or final-source attestation.
