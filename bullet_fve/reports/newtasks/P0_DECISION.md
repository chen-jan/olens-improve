# P0 decision: user modelling Tier A read sites

Decided 2026-10-15, about 20:55 EDT, by Claude (stage 1).
**Decision: drop nothing.** UM Tier A keeps all 6 planned sites: 600 sites, **3,000 cells** (100 items × 6 sites × L20/36/44/52/60).
`data/manifests/gen_umA.json` is unchanged. `build_manifests.py --only-gen` was re-run with no `--um-drop-role`, and all five manifests came out byte-identical (sha256 `d4263524…` for umA).
Tier B (request token −2) is excluded by the user's decision of 19:40. It was not judged against this rule.

## Rule (fixed in advance, DESIGN.md §2.5)
A planned **template** site is **dropped** only if **both** of these hold:
1. it has 0 gold picks over its 80 readouts;
2. at least 75% of those readouts describe only chat formatting or turn structure.

The rule never adds or swaps sites.
The template sites are `\n` after `<|im_end|>`, `<|im_start|>`, `\n` after `assistant`, and the final `\n\n`.
The two content sites (last request token and final punctuation) are not template sites. They also have gold picks, so the rule could not drop them either.

## Pilot
- **Items:** 10 UM items. 5 selfdescribe: `um-sd-country-10`, `-gender-00`, `-occupation-06`, `-religion-12`, `-country-02`. 5 synthsys: `um-ss-petownership-08`, `-religiousaffiliation-02`, `-employmentstatus-14`, `-maritalstatus-07`, `-continent-02`.
- **Grid:** the full 13-token window (n−13 … n−1) × L36 and L52 × N = 4. That is 260 cells and 1,040 readouts, so each site has 80 readouts.
- **Judge:** WSB `um-v2` with GPT-6 Luna (reasoning none) on all 1,040 readouts. Run id `nt-p0-v1`, private ledger.

## Numbers (80 readouts per site; "inferred" = gold with basis `inferred_characterization`)

| site (rel = n−1−pos) | tier | gold | inferred | echo | distractor | items with gold / inferred | names a value (judge / lexicon only) | read in full | formatting-only by reading | max possible share | drop? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| final `\n\n` (rel 0) | A | 26 | 10 | 16 | 0 | 5 / 3 | 26 / 5 | 49 | **0** | 61% | no |
| `\n` after `assistant` (rel 4) | A | 23 | 10 | 13 | 0 | 4 / 4 | 23 / 9 | 48 | **0** (10 are generic infobox placeholders, see below) | 60% | no |
| `<|im_start|>` (rel 6) | A | **47** | **34** | 13 | 0 | 6 / 5 | 47 / 2 | 31 | **0** | 39% | no |
| `\n` after `<|im_end|>` (rel 7) | A | 36 | 29 | 7 | 0 | 5 / 5 | 36 / 2 | 42 | **0** | 53% | no |
| final punctuation (rel 9) | A (content) | 8 | 4 | 4 | 1 | 2 / 1 | — | — | — | — | n/a |
| request token −1 (rel 10) | A (content) | 16 | 11 | 5 | 7 | 3 / 3 | — | — | — | — | n/a |
| request token −2 (rel 11) | B, excluded | 21 | 12 | 9 | 4 | 5 / 5 | — | — | — | — | n/a |

Unplanned positions are shown for reference only; the rule never adds a site.

| position | gold | inferred | echo |
|---|---|---|---|
| `</think>` (rel 1) | 4 | 1 | 3 |
| inner `\n\n` (rel 2) | 1 | 0 | 1 |
| `<think>` (rel 3) | 2 | 2 | 0 |
| `assistant` (rel 5) | 26 | 8 | 18 |
| `<|im_end|>` (rel 8) | 9 | 4 | 5 |
| rel 12 (` obox`, …) | 2 | 1 | 1 |

All 1,040 readouts were judged.
- **Overall:** gold 221 (21.3%), inferred 126 (12.1%), distractor 24 (2.3%), cannot tell 795 (76.4%).
- **By layer:** L36 gold 95 / 520, L52 gold 126 / 520.
- **Any-cell flags on this reduced grid:** correct 10/10 items, inferred 9/10, distractor 6/10.

**Why nothing is dropped.**
- **Condition 1 fails for all four template sites.** Each has 23–47 gold picks and 10–34 inferred picks, spread over 3–6 of the 10 items.
- **Condition 2 also fails.** I read every readout that names no attribute value (neither a judge gold/distractor pick nor a lexicon value hit): 31 + 42 + 48 + 49 = 170 readouts. None of them describes only chat formatting or turn structure.
  - They describe the user's request (Wikipedia infobox, meal prep, writing a will, utility bills, finding community in a new city, summer internships) or the user's hobbies.
  - Or they are the opening of the assistant's reply ("Here is a Wikipedia-style infobox tailored to your…", "I cannot generate a Wikipedia infobox for…").
  - The 150 readouts that name a value cannot be formatting-only by definition. I spot-checked the 18 that are named by the lexicon only, and all are content.
  - Even if every unnamed readout had been formatting-only, the shares would be 39–61%, below 75%.
  - The closest cases are 10 readouts at `\n` after `assistant` that are generic infobox templates with no user content, e.g. `user_modeling|um-sd-religion-12|L52|p00051` s0: "姓名: [Name] | Born: [Birth date] | Nationality: [Country]". They describe the requested document's format, not chat formatting or turn structure. Counting them anyway would give 10/80 = 12.5%.

## Verbatim examples (gold, `inferred_characterization`; judge evidence quoted)
- `<|im_start|>`, `user_modeling|um-sd-country-02|L36|p00052` s0 → south korea: "身份:** Fictional South Korean Idol or K- Pop Artist"
- `<|im_start|>`, `user_modeling|um-sd-country-10|L36|p00052` s0 → new zealand: "2: Notable New Zealand Māori Person"
- `<|im_start|>`, `user_modeling|um-ss-continent-02|L36|p00043` s1 → africa: "Southern Africa; East Africa; Zimbabwean; Nairobi"
- `\n` after `<|im_end|>`, `user_modeling|um-sd-religion-12|L36|p00048` s2 → islam: "someone who performs five daily Islamic prayers"
- `\n` after `<|im_end|>`, `user_modeling|um-sd-country-10|L36|p00051` s0 → new zealand: "新西兰毛利文化爱好者"
- `\n` after `assistant`, `user_modeling|um-ss-employmentstatus-14|L52|p00048` s0 → homemaker: "作为 a busy mom; home management; busy household"
- `\n` after `assistant`, `user_modeling|um-sd-occupation-06|L52|p00051` s0 → fisherman: "John A. Mariner; Unnamed Marine Engineer"
- final `\n\n`, `user_modeling|um-sd-country-10|L36|p00058` s0 → new zealand: "your New Zealand roots; a hypothetical New Zealand resident"
- final `\n\n`, `user_modeling|um-ss-continent-02|L52|p00049` s1 → africa: "Finding summer internships in Africa; looking locally in Zambia"
- final punctuation, `user_modeling|um-sd-religion-12|L36|p00046` s2 → islam: "practicing Muslim" (the only item with an inferred pick at this site)

## Things to know for stage 2 and the analysis
1. **On UM, `<|im_start|>` and `\n` after `<|im_end|>` are the strongest sites**, ahead of the final `\n\n` (the old UM read site). They have 47 and 36 gold of 80, 34 and 29 inferred, mostly from selfdescribe items. This reverses the CA / role-bound single-site evidence (DESIGN §2.2, where `<|im_start|>` was 0.01 / 0.072 and only borderline).
2. **Final punctuation is the weakest planned UM site:** 8 gold and 4 inferred, all from selfdescribe items, with inferred picks from 1 item only. It is a content site, so the rule does not apply, and it is kept. Expect few gold picks there.
3. **At the late template sites, synthsys gold picks are mostly `verbatim_echo`,** because the system prompt states the attribute. At the final `\n\n`, synthsys has 17 gold but only 3 inferred. The analysis should split by subfamily and basis, as planned.
4. **The unplanned `assistant` token (rel 5) is not dead on UM:** 26 gold, of which 8 inferred and 18 echo, mostly synthsys. The role/conj evidence put it at about 0. It is not added, because the rule never adds sites. `<think>`, the inner `\n\n` and `</think>` are nearly dead on UM too (2 / 1 / 4 gold), which is consistent with the design dropping them.
5. **No template site drew a single distractor pick.** All 24 distractor picks fall at the content sites and the unplanned positions, 7 of them at request token −1.
6. **The judge sometimes misses a value.** `user_modeling|um-sd-country-10|L36|p00051` s3 names "Māori" in all 4 bullets (the lexicon marks all 4 `gold_coarse`), but the judge said cannot tell, while sibling samples naming Māori were judged gold. The per-bullet string labels (§5.1) are meant to catch cases like this.

## Cost and time
- **GPU** (borrowed 25832889, H200, step `25832889.58`, 20:38:56–20:42:52, 3 min 56 s ≈ **0.066 H200-h**; the design budgeted 0.13 for capture plus P0):
  - capture of 15,980 vectors / 200 forward passes: 71 s including the model load;
  - O-lens load: 17 s (merge drift 0.125);
  - P0 generation: 146 s for 1,040 readouts (64 × 4 sequences per batch, 31–35 s each).
- **Judge:** 20:43:29–20:44:24 (55 s), 1,041 attempts (1,040 plus WSB's preflight call), **$0.1224** (design estimate $0.15–0.20).
  - The ledger total is $0.1229, including $0.00057 from the smoke test; $29.88 of the hard cap remains.
- **Capture check** (`code/verify_capture.py` → `data/capture/verify_capture.json`):
  - 15,980 × 5120 fp32 (UM 6,480, CA 9,500), all finite;
  - 0 row-hash mismatches against the audit, 0 duplicate rows, no row with a norm beyond 5× (or below 1/5 of) its family × layer median;
  - median norms are 47 / 74 / 88–92 / 130 / 238 at L20 / 36 / 44 / 52 / 60;
  - the 128 cells that overlap the smoke capture are bit-identical.

## Files
- Judge rows: `data/judge/um/p0/p0/um_cell_rows.jsonl`. WSB results: `data/judge/um/p0/p0/results.json`. Summary: `data/judge/um/p0/summary.json`.
- Per-site counts: `data/judge/um/p0/p0_sites.json`. Every readout with its judge pick and lexicon labels: `data/judge/um/p0/p0_reading.jsonl`.
- Reading tallies and the decision as data: `data/judge/um/p0/p0_reading_decision.json`.
- Generation journal: `data/gen/p0/shard-000-of-001.jsonl` (sha256 `3e647696…`, pool `c104ad45f3277ce3894ec942`).
