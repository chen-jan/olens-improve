# Token heat: independent verification and findings

Exploratory, 2026-10-15. Written by the main session from the verifier's returned findings.

## Summary

The heat file is correct, and the wrong part of a wrong bullet is not "cold".

**Checks.** All four groups pass:
- The 60 sample occurrences reproduce with scipy NNLS to within 1e-7, which is the 7-decimal rounding.
- Every structural check passes on all 67,317 lines, including an independent tokenizer check of every token boundary.
- joint_0 rebuilt from the raw vectors (`JointNNLS.from_raw`) matches to within 6.6e-8. This covers 100 random occurrences plus 16 edge cases.
- On every line, sum(heat) minus loo_drop equals the recorded `drift` to within 1.5e-7.

**The wrong part is not cold.** In wrong bullets where the wrong span covers some but not all scored tokens (14,004 bullets), I compared the share of the bullet's positive heat on the wrong-span tokens with the share of tokens they take up:

| Setting | Heat share minus token share [95% CI, bootstrap over chats] |
|---|---|
| Original | -0.010 [-0.019, -0.001] |
| Best of 32 | -0.025 [-0.035, -0.015] |
| Combine 32 | -0.010 [-0.021, +0.001] |

- That is 1 to 2.5 points on a base of about 40% of tokens.
- The direction holds under every variant I tried: against a position-matched baseline from clean bullets, after the first nonzero-heat token only, with solo gains, and with net (signed) heat.
- In the half of wrong bullets that carry real FVE (LOO above the median, about 0.0086), the gap is about 0 (all settings: -0.004 [-0.012, +0.004]).
- So heat cannot locate the error inside a bullet.

**What heat looks like:**
- Heat swings both ways. Negative heat adds up to 45% of positive heat, and 26% of tokens have exactly zero heat.
- 20–28% of bullets have no heat in their first quarter of tokens. Heat is zero until the prefix first gets a nonzero NNLS weight, and that first token then takes the credit for everything before it.
- Heat builds towards the end of the bullet. The first token is below its uniform share, while the last token and final punctuation get 1.6–3.7 times theirs.
- Punctuation is hotter than its share (1.12–1.27x), at every read-site kind. Content words are only slightly hot (1.07x), and slightly cold in Combine 32 (0.97x).
- The single largest heats land on the token that completes an entity name, e.g. "Objects" in "BusinessObjects" (+0.318 FVE).
- The coldest wrong bullets put all their heat on junk after the wrong claim: a glued-on next list item, a code fence, a colon.

The full report text with tables and verbatim examples is in `findings`. Everything is in `${OLENS_SCRATCH}/olens-bullet-fve/heat/verify/`.

## Checks

- 1. **Sample recompute** (`v1_sample_nnls.py` / `.json`): all 60 occurrences in verify_sample.pt recomputed with scipy.optimize.nnls in float64 (1,423 prefix fits, 60 joint_0 fits, 60 joint_cached fits).
  - Worst abs diff vs token_heat.jsonl: joint 5.0e-8, heat 9.7e-8, solo 5.0e-8, joint_cached 4.8e-8. These are 7-decimal rounding.
  - Against the unrounded values stored in the .pt: 7.8e-16.
  - joint_cached vs saved readout FVE: 2.9e-8. Closed-form solo vs 1-column NNLS: 1.2e-15.
  - cos(u_n, cached vector) >= 0.99932 (median 0.99967).
  - PASS at tol 1e-6: 60/60. All 60 sample occurrences are 4-bullet readouts.
- 2. **Whole file** (`v2_whole_file.py` / `.json` / `.log`, run via srun on mit_quicktest):
  - Lines and coverage: 67,317 lines, equal to all atoms. The 4 empty readouts correctly produce no lines. (cell, setting, bullet) coverage is exact: 0 missing, 0 unexpected, 0 duplicate.
  - Identity fields match.
  - Lengths: n_scored == len(ids) == len(heat) == len(solo) == len(ends) == len(pieces) == len(joint)-1, 0 violations.
  - Telescoping max 1.2e-16; heat == round(diff(joint), 7) exactly.
  - joint_cached vs saved readout FVE: max 8.7e-8. The drift field is consistent (1e-7).
  - NNLS invariants (joint_k >= joint_0, joint_k >= solo_k, joint_cached >= joint_0): 0 violations.
  - For duplicate bullets, joint_cached == joint_0.
  - ends are non-decreasing and in range; pieces equal the slices and concatenate to a prefix of scored_text; untruncated bullets end at len(scored_text).
  - Independent tokenizer decode of every prefix boundary (1,598,118 tokens): 1,591,103 exact, 7,015 correctly handled cut multi-byte characters, 0 failures.
  - Full-file joint_0 vs the separate bullet_metrics.jsonl (joint_fve_recomputed - loo_drop): max 1.0e-7. PASS.
- 3. **joint_0 from raw** (`v3_joint0_raw.py` / `.json` / `.log`, srun):
  - Sample: 100 random occurrences (seed 4242; all 5 layers and 3 settings) plus 10 from readouts with fewer than 4 bullets plus 6 duplicate occurrences. Inputs: raw cached vectors, the activation row (sha256 checked) and Whitener.load (all 5 SHAs match).
  - Max abs diff: joint_0 6.6e-8; joint_cached vs full FVE 6.5e-8; saved vs full 2.3e-8; loo_drop vs full - others 4.2e-8. PASS.
  - sum(heat) - loo_drop on all 67,317 lines equals `drift` to within 1.5e-7 (corr 0.99999999).
  - |drift|: median 8.5e-5, p90 4.2e-4, p99 1.18e-3, max 7.07e-3 (chat-lmsys-0061.L60.p108, Best of 32, bullet 3: sum heat 0.0481 vs LOO 0.0552).
  - Relative size, for bullets with LOO > 1e-4: median |drift|/LOO 1.2%; 0.5% of them have |drift| > 25% of LOO. Truncated median 1.09e-4 vs untruncated 8.3e-5.
- 4. **Offsets for the findings:** page offsets (UTF-16 units) were converted to code points with an explicit map. Every bullet was relocated by text[start:start+len(scored_text)] == scored_text (67,317/67,317). All verified span offsets fell on code-point boundaries.
  - Span-to-token alignment was eyeballed on 9 example bullets against the judge's span text; all were correct, including a span that crosses into the next bullet (clipped).
  - 39 wrong-span occurrences lie only in the unscored suffix.

## Findings

REPORT CONTENT (for REPORT.md). Verdict: the file is correct.
- Steps 1–3 all pass (see checks).
- Heat values below are written as piece(+x.xx) in units of 0.001 FVE. [..] marks a token inside a verified wrong span.
- Keys are <item>.L<layer>.p<pos>. Settings: Original = capped_n1-n1, Best of 32 = best_n_exact-n32, Combine 32 = pooled_greedy_swap-n32.
- Numbers and examples are in heat/verify/v4_heat_findings.json; full readouts, spans and judge reasons are in page/data/items/<item>.json under cells[<key>].settings[<setting>].
**HEAT CHARACTER** (Original / Best of 32 / Combine 32):
- Tokens with exactly 0 heat: 25% / 29% / 23%. Tokens with negative heat: 30% / 27% / 29%.
- Negative heat mass / positive heat mass: 0.51 / 0.39 / 0.43. Median net / positive heat per bullet: 0.42 / 0.50 / 0.57.
- Bullets with all-zero heat: 5.0% / 8.8% / 0.004%. Bullets with LOO = 0: 14.6% / 19.9% / 0%.
- Onset (first nonzero heat): 20% / 21% / 28% of bullets have no heat in their first 25% of tokens, and 7.6% / 8.6% / 11.4% none in their first 50%. The onset token carries on average 10% / 12% / 5% of positive heat.
- Concentration: median top-1 token share 0.30 / 0.29 / 0.28; median 11% of tokens hold 50% of positive heat.
- Why: zero heat means the k-token prefix vector gets NNLS weight 0 next to the other bullets, and the onset token absorbs the credit for everything before it.
**WHERE HEAT SITS** (share of positive heat, with uniform or token share in brackets):
- First token: 3.5% (4.8) / 4.2% (4.6) / 1.5% (4.3), so cold. Exception: an emoji first token averages 13.4% (n=348); example chat-dailydialog-0059.L60.p67, Best of 32, bullet 2: 😊(+55.47) Or(+56.75) simply(+13.62) chatting(-27.90).
- Last token: 7.7% (4.8) / 8.7% (4.6) / 13.1% (4.3).
- Final punctuation, in untruncated bullets ending in punctuation: 9.8% (5.1) / 11.0% (4.9) / 16.9% (4.5).
- First tenth of the bullet: 8.4% / 9.1% / 3.9%, against about 12% of tokens. Last tenth: 11.5% / 13.0% / 19.7%, against about 8% of tokens.
- solo reaches 90% of its final value at median 62% / 67% / 70% of the bullet.
- Lift by class (heat share / token share): punctuation 1.12 / 1.17 / 1.27; content words 1.07 / 1.03 / 0.97; function words 0.86 / 0.89 / 0.95; numbers 0.75 / 0.73 / 0.72; non-Latin words (mostly Chinese, about 6% of tokens) 0.91 / 0.93 / 0.69.
- By read-site kind: the extra heat on punctuation and whitespace is present at every kind, +1.5 to +5.3 points at clause, sentence, markup and newline sites and +6.7 to +9.1 at quote sites (n < 740 per setting). See v5_sitekind.json.
**LARGEST SINGLE-TOKEN HEATS** land on the token that completes an entity name:
- chat-lmsys-0054.L60.p425, Original (and the identical Best of 32 bullet), bullet 0, LOO 0.396: '2(+0.00) :(+0.09) Managing(+0.21) users(-0.31) … in(+0.31) Business(+1.27) Objects(+318.02) Central(+63.51) Administration(+12.94)'.
- chat-lmsys-0033.L60.p128, Combine 32, bullet 0: 'v(+2.91) oltage(+87.53) ,(+9.00) … user(+47.98) … Voltage(+30.53)'.
- A typical clean bullet is diffuse and goes both ways. chat-lmsys-0039.L44.p69, Original, bullet 3, LOO 0.026: 'I(+4.26) am(+5.02) … with(+16.92) safe(+5.74) ,(-6.06) inclusive(-17.97) topics(+4.70) .(+4.00) … society(-1.31) .(+5.88)'.
**WRONG SPAN VS THE REST: is the wrong part cold?**
- Definitions: wrong bullet = page label w (overlaps a verified wrong span), duplicates excluded. 'Informative' = 0 < wrong tokens < n. CIs: bootstrap over the 149 chats.
- Counts: Original 4,580 bullets (148 chats), Best of 32 4,333 (149), Combine 32 5,091 (149).
- Excluded: spans that cover every scored token (1,134 / 1,057 / 854), wrong bullets with no positive heat (259 / 486 / 0), and spans only in the unscored suffix (7 / 1 / 4).
- Mean token share 0.397 / 0.400 / 0.383; mean positive-heat share 0.387 / 0.375 / 0.373.
- Heat share minus token share: -0.010 [-0.019, -0.001] / -0.025 [-0.035, -0.015] / -0.010 [-0.021, +0.001].
- Against a position-matched expected share (average heat profile of clean bullets of the same length): -0.016 [-0.024, -0.007] / -0.026 [-0.035, -0.017] / -0.016 [-0.023, -0.009].
- Tokens after the onset only: -0.014 [-0.021, -0.007] / -0.021 [-0.030, -0.012] / -0.023 [-0.031, -0.014].
- Positive solo-gain share minus token share: -0.030 / -0.025 / -0.030, all CIs below 0.
- Pooled positive heat share vs pooled token share: 0.383 vs 0.391 / 0.399 vs 0.396 / 0.375 vs 0.379.
- Pooled net (signed) heat share: 0.347 [0.317, 0.378] vs 0.391 / 0.377 [0.351, 0.402] vs 0.396 / 0.352 [0.330, 0.374] vs 0.379.
- Mean signed heat per token, in span vs outside (x1e-3): 0.59 vs 0.86 / 0.89 vs 1.08 / 0.44 vs 0.53.
- Bullets with heat share < token share: 54% / 57% / 55%.
- All settings pooled, by layer (heat minus position-matched share): L20 -0.025, L36 -0.020, L44 -0.005 (CI includes 0), L52 -0.021, L60 -0.025.
- Bullets with LOO above the median (about 0.0086): heat minus token share -0.007 [-0.016, +0.002] / -0.005 [-0.016, +0.006] / -0.001 [-0.012, +0.010].
- Reading: the wrong part is very slightly cooler than its token share (1–2.5 points on about 40%) but nowhere near cold. It explains about as much of the activation as the rest of the bullet, so heat does not localise the error.
**EXAMPLES** (picked from informative wrong bullets with LOO > 0.005; the coldest and hottest are extremes on purpose):
- W1, coldest, Original: chat-dailydialog-0073.L36.p113, bullet 3. Wrong span 'You can simply share your grades … decompress.'; heat share 0.00 against a token share of 0.83; LOO 0.033. All span tokens are +0.00, then the glued-on next item: '.(+2.43) **(+19.55) Str(+10.65)'.
- W2, median, Original: chat-dailydialog-0060.L20.p24, bullet 3. Span 'I’m a bit of a gearhead.'; token share 0.36, heat share 0.35. '[ I(+0.71)] [’m(+0.97)] [ a(+0.24)] [ bit(+6.12)] [ of(-0.30)] [ a(-0.10)] [ gear(+1.27)] [head(+3.94)] [.(+0.41)] But(-6.66) hey(+10.11)'.
- W3, hottest, Best of 32: chat-dailydialog-0061.L20.p21, bullet 0. Span 'Mom'; one token of 17 holds 96% of heat: '疼(+0.00) ((+0.00) aching(+0.00) … hurting(+0.24) ,(-0.24) [ Mom(+8.97)]'.
- W4, coldest, Combine 32: chat-lmsys-0050.L44.p69, bullet 0. The whole SQL query is the span and is all zeros; heat goes to '\n(+0.78) ```(-0.68) \n\n(+7.54) ###(-1.24)'.
- W5, coldest, Best of 32: chat-lmsys-0006.L52.p122, bullet 0. Span '**Diego Arango** (who founded the podcast and is its primary host)' is all zeros, then 'and(-0.01) :(+11.99)'.
- W6, median, Combine 32: chat-dailydialog-0060.L60.p29, bullet 0. Span "I've had 'em for a while now"; token share 0.47, heat share 0.46; it swings: "'(-6.03) em(-10.42) for(+6.24) a(+10.70) while(-6.81) now(+7.76)".
- The extreme cold cases share a pattern: the cached vector's usefulness comes from trailing junk or a boundary token (a glued next item, a code fence, a colon), not from the claim. This is consistent with the build-up of heat at the end of bullets and on punctuation.
**CAVEATS:**
- Heat is the marginal FVE of the k-token prefix vector next to the other bullets' full vectors. It is not an additive causal attribution.
- Positive heat counts swings, so net-heat versions are reported alongside.
- Single-token heats below about 1e-3 are within single-pass noise (GPU agent's test).
- Bullets with LOO = 0 (11.5% of all bullets) have heat that is noise or activity at intermediate prefixes.
- Labels follow the page's rules: only verified wrong spans count; a span found in several bullets marks all of them.
- Judge verdicts are shared across settings through the cache, so settings are not independent.
- This is exploratory: all chats were looked at before this analysis.
**FILES** (all in ${OLENS_SCRATCH}/olens-bullet-fve/heat/verify/):
- v1_sample_nnls.py and .json: step 1.
- v2_whole_file.py, .json and .log: step 2.
- v3_joint0_raw.py, .json and .log: step 3.
- v4_heat_findings.py, .json and .log: step 4 numbers and examples.
- v5_sitekind.py and .json: punctuation heat by read-site kind.

## Problems and limits

- The AR prefix vectors (u_k) could not be recomputed on CPU.
  - Verified: everything downstream of u_k, and u_n ≈ cached vector (cos >= 0.9993) on 60 occurrences.
  - Not reproduced: the GPU agent's single-pass vs explicit-prefix equivalence (heat/equivalence_test.json: per-token heat differs by median 2.9e-5, max 1.5e-3). So single-token heat below about 1e-3 is noise.
- The pooled net-heat share vs pooled token share comparison has no bootstrap CI on the difference itself; I only note that the token share lies above the net-share CI. The by-layer and per-setting CIs are percentile bootstraps over the 149 chats (2,000 resamples).
