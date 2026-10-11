# Final evidence lookup preparation

Prepared and unrun on real final sources. `.state/extract-final-presentation-evidence-v1.py` SHA `58e02ce30cf150f0da18c53cd7f7af96b4609ce77d57550e82ba15aa6b305157` copies the seven unchanged V3 draft primary contrasts across four families into28 lookup records. This is machine extraction pending human interpretation, not a new statistical analysis, recommendation or claim of final readiness.

Each record contains exact native condition/reference rows and the declared paired comparison, with absolute intervals, paired and simultaneous intervals, numerators/denominators, draw/group counts and warnings retained. The full cohort's existing joint metadata includes declared496, defined/effective nondegenerate and joint-interval contrast counts, critical value and status. Each copied record carries its original JSON array pointer; top-level native/numeric file paths and hashes identify the pointer authority.

Fit absolute fields are copied without paired records attached; the exact recorded comparison for that named reference is copied separately. Means/intervals, raw fractions and pp fields, intended/scored sites, missing/invalid coverage, common-valid masks/counts, group counts and warnings remain unchanged. If that quality reference has no recorded fit comparison, it is `not_recorded`; no absolute-mean subtraction or fallback reference is substituted. Existing Best32→Best16, Random32→Random16, Pool32→Pool16 and Pool32→Best32 fit records are copied only when present. No records or intervals are computed to fill gaps.

The terminal-only CLI requires explicit retained native/numeric output and raw terminal-state SHAs, each matching the corresponding completed service; native scientific validation, sealed32 canonical source receipt/full280 units, exact70×4 native/numeric identities and exact496 declared comparison menu are enforced. The V3 draft and finite manifest are pinned to their approved hashes. V5 objective/solver/native binding is checked. Sources are hashed again before exclusive creation at an absent new path. Invalid/unavailable fits, zero-variation draws and null intervals stay visible; terminal source completeness is not certainty. No source, draft, gate or builder changes occur.

Four tiny synthetic copy/guard fixtures pass in `tests/test_expansion_final_evidence_extract.py` (SHA `b1438c6651b4ee1bd0a909f2fbd6d9c851588bc30c7d10033ed56dba76fa1e52`, tool chunk `428000`, exit0, .018 seconds). They check exact pointers/no source mutation, common-mask record reuse rather than absolute-mean differences, null/warning preservation, incomplete/duplicate menu rejection, and optional extras only when recorded. They do not attest actual final files or execute the terminal CLI.

Root may use this command only after reviewing the prepared helper and the actual terminal sources. All four `FINAL_*_SHA` placeholders must come from exact immutable file bytes/terminal authority, not interim values. Use the existing owned CPU with an explicit single task; no allocation is created. This is a recipe, not a launched extraction.

```bash
srun --jobid=25536417 --overlap --ntasks=1 --cpus-per-task=1 --mem=4G --cpu-bind=cores ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python .state/extract-final-presentation-evidence-v1.py \
  --native ${OLENS_DATA_ROOT}/expansion-v1/analysis/final-v1.json --native-sha256 FINAL_NATIVE_SHA \
  --native-state .state/expanded-final-native-v1.service.json --native-state-sha256 FINAL_NATIVE_STATE_SHA \
  --native-receipt .state/expanded-final-native-ready-v1/receipt.json \
  --reconstruction ${OLENS_DATA_ROOT}/expansion-v1/reconstruction/final-v1.json --reconstruction-sha256 FINAL_RECONSTRUCTION_SHA \
  --reconstruction-state .state/expanded-final-reconstruction-v1.service.json --reconstruction-state-sha256 FINAL_RECONSTRUCTION_STATE_SHA \
  --reconstruction-receipt .state/reconstruction-analysis-final-ready-v1/receipt.json \
  --inventory configs/expansion_manifest_v1.json --draft .state/expanded-final-review-draft-v3.json \
  --output .state/expanded-final-evidence-lookup-v1.json
```

No lookup artifact currently exists. Root still interprets family-specific correctness-versus-fit differences, selects final examples from human-reviewed chosen outputs, retains raw/capped reference distinctions and calibrates all final prose. This tool supplies no automatic scientific narrative.
