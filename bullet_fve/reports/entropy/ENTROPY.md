# Text-buffer hypothesis vs FVE (Hallucination, chat)

Exploratory. All 149 chats were inspected before this analysis. Script: `entropy/analysis.py` (about 15 s on CPU). Full numbers: `entropy/analysis_results.json`. Compact page data: `entropy/entropy_page.json`. Case links: `https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#<k>`.

**Skeptic re-check (2026-10-15).** Every headline number was rerun with independent code (`entropy/skeptic/`): a fresh logit lens and a separate regression and bootstrap. All of them reproduce to within 0.001. Passages changed by the re-check are marked **[re-check]**. The originals are in `ENTROPY.md.bak` and `entropy_page.json.bak`. A summary of what survives is at the end.

## Short answer

**The hypothesis.** When the next token is easy (low entropy), the model has spare room, so the activation holds other computation: thinking, planning, summarising. When the next token is hard (high entropy), the activation is busy with the continuation.

**What FVE should do under it.** The activation reconstructor (AR) only knows one thing: "the activation just before some text". So extra non-continuation content can only show up as variance the bullets cannot explain. Prediction: **lower FVE at low-entropy sites, with the gap growing at deeper layers.** Readouts should also look less like the continuation there.

**What FVE does.**

1. **FVE changes little with entropy, but "flat" depends on the proxy [re-check].** From the lowest- to the highest-entropy site, FVE changes by +0.010 (95% CI -0.011 to 0.030; Original, chat fixed effects, site kind, position and words left controlled). Best of 32: +0.011 (-0.009 to 0.030). Combine 32: +0.013 (-0.007 to 0.032). For scale, FVE rises 0.25 from L20 to L60, and sentence ends sit 0.045 below clause sites.
   - **[re-check]** The same L60 lens ranked by 1 − p(top-1) instead of entropy gives a small slope in the buffer direction: +0.030 [0.008, 0.051] in Original, +0.029 in Best of 32 and +0.030 in Combine 32.
   - Controlling for NEXT share, it is +0.035 [0.014, 0.056]. It holds where the next token is a word (+0.030 [0.010, 0.050], with the NEXT control) and is +0.022 [0.002, 0.041] without block boundaries. It is the same at L20 (+0.026) and L60 (+0.034).
   - log(H) pooled gives +0.007 per SD [0.001, 0.014].
   - So any buffer-direction effect is at most about 0.03 FVE between the most and least confident sites, which is 1/8 of the layer effect. Its sign and significance depend on how lens confidence is summarised. "Flat" holds for the entropy rank only.
2. **No sign that the effect grows with depth [re-check: "it fades" is too strong].** The slope is slightly positive at L20/L36 (+0.02 to +0.03, CI above 0 at L36) and slightly negative at L60 (-0.011 Original, -0.014 Best of 32). The L60 minus L20 difference is -0.027 (-0.057 to 0.003) for Original, -0.037 (-0.062 to -0.011) for Best of 32 and -0.032 (-0.057 to -0.007) for Combine 32.
   - **[re-check]** These are end-point contrasts. A linear entropy × layer trend test over all five layers is not significant: -0.006 per 16 layers [-0.019, 0.006] for Original, -0.009 [-0.020, 0.002] for Best of 32 and -0.007 [-0.018, 0.004] for Combine 32.
   - The L36 slope (+0.027) has BH q = 0.08 over the 3,347 estimates in `analysis_results.json`.
3. **One small buffer-like dip.** At near-deterministic sites (H < 0.1 nats, 85 of 1,123 sites), FVE is about 0.03 lower:
   - Original +0.033 (0.009 to 0.059), Best of 32 +0.034 (0.010 to 0.059), as "rest minus near-deterministic";
   - in deciles it is only the lowest one (-0.023 vs the chat mean, CI -0.041 to -0.005); the other nine are flat. **[re-check]** Bootstrap p = 0.008, which is 0.08 after Bonferroni over the 10 deciles. The H < 0.1 cut was chosen after looking at the data.
   - The dip comes mostly from about 10 **block boundaries**: a full stop whose next token is almost surely a paragraph break, and the end of the reply. Their FVE is 0.15 against 0.29-0.32 for other sites of the same next-token type (L36-L60).
   - Where the next token is a word, the dip is about zero: +0.008 (-0.020 to 0.034). The same holds when "near-deterministic" means p(top-1) ≥ 0.99 (78 sites): +0.009 [-0.020, 0.038]. The continuous 1 − p(top-1) slope does survive at those sites (point 1).
4. **The lens lands on the actual continuation more often at low entropy, which is not a test of the buffer [re-check, reframed].** At L60 (Original), readouts average a 51% NEXT share in the lowest-entropy fifth against 36% in the highest (lexical classifier).
   - This is what any continuation-writer would show: where the continuation is predictable, a guess matches it more often. So it does not count against the buffer.
   - Controlling for whether the L60 lens's own top-1 is the right next word cuts the slope from -0.085 to -0.060 [-0.120, 0.001].
   - The topic-adjusted `cont_excess` slope is not significant (-0.028 [-0.064, 0.008]). The blind hand labels lean the other way (section 2).
   - What bears on the hypothesis is the share of non-continuation content. That share is tiny at every entropy level: continuation-shaped bullets are about 90% in each hand-label tercile, and 3 of 510 bullets are meta or generic.
   - The meta regex rate is 1.3-1.7% in the two lowest-entropy fifths against 0.4% in the highest. That leans *toward* the buffer (slope -0.006 [-0.012, 0.001], n.s.), but the hits are mostly persona speech ("I'm Qwen ...", "the conversation"), not planning.
5. **Sentence ends are high-entropy, not low.** Mean 2.26 nats; full stops 2.44, against commas 1.32. They still have the lowest FVE, so entropy cannot explain the full-stop gap. Adding entropy to the model moves the sentence-vs-clause gap from -0.045 to -0.046. **[re-check]** Surprisal agrees (full stops 4.38 nats against commas 2.28; sentence 3.66 against clause 2.94), and so do 1 − p(top-1) and lens accuracy. The gap survives Holm correction.
6. **Entropy does not predict hallucination.** Pooled: +0.041 (-0.018 to 0.102) in Original, smaller in the other two settings. What does predict FVE is the **surprisal of the token the model actually wrote next**: +0.058 (0.034 to 0.082). It holds with next-token-type controls, and entropy adds nothing once surprisal is in the model.
   - **[re-check]** A large part of it is tokenisation. At 177 L60 sites the lens's top-1 is the right word in a different token (' Ferm' for 'F', ' better' for 'better'), so surprisal is high. These sites have FVE 0.54, against 0.42 where the top-1 is the exact token.
   - Controlling for exact and tolerant top-1 correctness plus next-token type leaves +0.043 [0.007, 0.078].
   - The effect is absent at clause sites (+0.010 [-0.031, 0.051]) and comes from markup (+0.168), sentence (+0.082) and newline (+0.065) sites.
   - Apart from the site-kind gaps and the L52-lens slope, it is the only cited effect that survives Holm correction. Treat it as a lead about lookahead, not as next-token difficulty.

**Plain version.** If spare capacity at easy positions held "thinking", the lens's text should explain less of those activations. It explains at most slightly less: up to about 0.03 FVE, depending on how confidence is measured **[re-check]**, and mostly at paragraph breaks, reply ends and the most confident ~7% of sites. At easy positions the lens reads past the trivial next token to the content after it (", and 4" -> bullets start at "4"). Whatever extra the activation carries there looks like **upcoming text (lookahead)**, which the AR can express, not abstract thinking. Because the lens is RL-trained to maximise this FVE, the readouts cannot settle whether non-continuation content exists. Only the size of the unexplained remainder can (Limitation 3).

## Setup

- **Entropy (H).** The logit lens on the layer-60 residual at the read site: final RMSNorm (1+w) and lm_head, from `site_entropy.jsonl`. It predicts token pos+1. Entropy is a property of the site, so the 5 layers of a site share it. Quintile cuts: 0.46 / 1.04 / 1.68 / 2.98 nats; mean H per quintile 0.18 / 0.77 / 1.34 / 2.21 / 5.01.
- **Unit.** One cell = chat x read site x layer: 1,123 sites x 5 layers = 5,615 cells, with one readout per setting.
- **Effect size `b`.** The slope on the entropy percentile rank (0 = lowest site, 1 = highest), i.e. "highest minus lowest entropy site" on a linear scale. **Sign: high minus low entropy throughout.** The buffer hypothesis predicts b > 0 for FVE and NEXT, and b < 0 for NONE.
- **Controls ("full").**
  - Chat fixed effects: the values are demeaned within each chat.
  - Site kind.
  - Relative position (UTF-16 char / reply length) and its square.
  - log(1 + words left in the reply).
  - Pooled-over-layers fits also add layer dummies.
- **Correlations.** Spearman correlations are also given within chat (ranks demeaned by chat).
- **CIs.** Chat-level cluster bootstrap: 149 chats, 2,000 draws, shared across all statistics, so differences such as L60 - L20 get proper intervals.
- **Continuation-ness.** From `continuation.jsonl`:
  - NEXT, NONE and BEFORE shares over scorable bullets;
  - `cont_excess`: the mean of (next-window score - the same bullet's score against other sites' next windows);
  - the share of `meta` bullets (a regex for "the user", "let me think", ...).

## 1. Entropy vs joint FVE

FVE by entropy quintile (lowest to highest), the full-control slope, and the within-chat Spearman:

| Layer | Original Q1..Q5 | b [95% CI] | within-chat rho | Best of 32 Q1..Q5 | b [95% CI] | within-chat rho |
|---|---|---|---|---|---|---|
| L20 | .202 .214 .212 .218 .215 | +0.017 [-0.002, 0.035] | +0.02 | .233 .245 .245 .248 .250 | +0.023 [0.005, 0.041] | +0.04 |
| L36 | .340 .379 .370 .385 .368 | +0.027 [0.004, 0.052] | +0.03 | .389 .432 .425 .434 .424 | +0.030 [0.007, 0.053] | +0.04 |
| L44 | .352 .376 .375 .374 .369 | +0.008 [-0.016, 0.033] | -0.01 | .405 .432 .432 .429 .427 | +0.011 [-0.013, 0.036] | +0.00 |
| L52 | .425 .453 .450 .446 .441 | +0.006 [-0.021, 0.033] | -0.02 | .487 .512 .515 .513 .503 | +0.004 [-0.022, 0.030] | -0.03 |
| L60 | .449 .473 .471 .467 .449 | -0.011 [-0.041, 0.020] | -0.05 [-0.12, 0.01] | .520 .539 .540 .530 .517 | -0.014 [-0.041, 0.013] | -0.08 [-0.14, -0.02] |

- **Shape.** The lowest quintile sits about 0.02-0.04 under Q2-Q4 from L36 on. At L60 the highest quintile also drops: an inverted U, not a slope. Deciles (within chat, layer-centred, Original):
  - D1 (H < 0.13) is -0.023 [-0.041, -0.005];
  - D2-D10 all lie within ±0.013 with CIs that include 0.
- **Near-deterministic sites (H < 0.1).** "Rest minus near-deterministic", full controls:

  | | All sites | Without block boundaries | Next token is a word |
  |---|---|---|---|
  | Pooled | +0.033 [0.009, 0.059] | +0.022 [-0.005, 0.045] | +0.008 [-0.020, 0.034] |
  | L52 | +0.047 [0.014, 0.080] | | +0.003 [-0.032, 0.036] |
  | L60 | +0.036 [0.003, 0.071] | | +0.002 [-0.036, 0.041] |

  Raw FVE (Original, L36-L60) of near-deterministic vs other sites, by next token:
  - next is a newline (7 sites): 0.15 vs 0.32;
  - end of reply (3 sites): 0.15 vs 0.29;
  - markup, code fence or punctuation (17 sites): 0.31 vs 0.37;
  - next is a word (58 sites): 0.41 vs 0.45.

  Examples of the low-FVE boundary sites:
  - [chat-dailydialog-0071.L60.p108](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0071.L60.p108): '.' before '\n\n', FVE 0.086
  - [chat-lmsys-0049.L60.p290](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0049.L60.p290): FVE 0.051
  - [chat-lmsys-0054.L60.p298](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0054.L60.p298): FVE 0.171
- **Depth.** The L60 - L20 slope differences are given in the short answer. Whatever small positive slope exists lives at L20-L36, the opposite of "stronger at deeper layers".
- **Robustness.**
  - **log(H) instead of rank.** It weights the low end more. Small positive slopes at L20-L44, e.g. +0.012 per SD at L36 [0.005, 0.020]; none at L52-L60.
  - **Next-token-type controls.** Pooled +0.014 [-0.003, 0.032] (Original).
  - **Sites with at least 40 words left.** L36 +0.045 [0.014, 0.077], L60 -0.009 [-0.045, 0.030].
- **L52 lens entropy behaves differently.** It measures how readable the L52 activation already is through the unembedding, not how predictable the position is. It has a clear negative slope: Original L52 -0.095 [-0.127, -0.063], L60 -0.084 [-0.117, -0.052]. Activations that already point at one next token are better explained, not worse.
- **[re-check] Other proxies.** Pooled, full controls, Original; Best of 32 within 0.007 of each.
  - **L60 lens variants.**
    - Entropy with tokens of the same surface string merged (' better' = 'better'): -0.003 [-0.024, 0.017].
    - Entropy over non-CJK tokens only: +0.012 [-0.009, 0.033].
    - 1 − p(top-1): **+0.030 [0.008, 0.051]**.
  - **Lenses of other layers.** These barely predict the next token (top-1 6-12%; Spearman with L60 entropy 0.10-0.33). All give strongly *negative* FVE slopes: L20 -0.050, L36 -0.083, L44 -0.042, L52 -0.063, all p < 0.001.
  - So the conclusion depends on which proxy is used. The early-layer lenses mostly measure how well the activation lines up with the unembedding, which itself raises FVE.
  - **Sites where the L60 lens's top-1 is the right word** (551 sites; prefix match after stripping spaces and case): -0.024 [-0.053, 0.004]. No buffer effect where the proxy is most trustworthy.
- **[re-check] Confounds (Original, pooled; FVE slope on entropy rank).**
  - Chat source: DailyDialog +0.016 [-0.011, 0.043], LMSYS +0.007 [-0.026, 0.041].
  - Chats without code: +0.014. The 11 code chats: -0.027 [-0.124, 0.070].
  - Chat × site-kind fixed effects: +0.013 [-0.015, 0.041].
  - Chat × layer fixed effects: +0.009.
  - Dummies for the read token: +0.016.
  - log token index added: +0.010.
  - Middle 80% of the reply only: +0.017 [-0.006, 0.041].
  - Entropy × reply-length interaction: -0.009 [-0.033, 0.016].
  - None of these moves the estimate by more than 0.008 or changes the conclusion.

## 2. Entropy vs continuation-ness of the readouts

Original setting, by entropy quintile. The pooled slope uses all layers and full controls.

| Measure | Q1..Q5 (L60) | pooled b [95% CI] | buffer predicts |
|---|---|---|---|
| NEXT share | .51 .45 .43 .41 .36 | -0.085 [-0.143, -0.027] | b > 0 |
| NONE share | .29 .35 .39 .38 .41 | +0.050 [0.007, 0.091] | b < 0 |
| BEFORE share | .15 .15 .14 .17 .17 | +0.028 [-0.011, 0.070] | - |
| cont_excess | .18 .15 .15 .14 .11 | -0.028 [-0.063, 0.007] | b > 0 |
| meta share (all layers) | 1.3% 1.7% 1.0% 0.8% 0.4% | -0.006 [-0.012, 0.001] | b < 0 (more meta at low H) **[re-check: was "b > 0"]** |

- **[re-check] Sign of the meta row.** It was mislabelled. "More meta at low H" means b < 0. The observed -0.006 therefore points *toward* the buffer, though it is not significant (p = 0.09) and tiny: 60 and 76 flagged bullets in Q1-Q2 against 18 in Q5, out of about 4,500 per fifth. The flagged low-entropy bullets are mostly persona speech, for example:
  - "I'm Qwen, and I'm always here to assist you" ([chat-dailydialog-0034.L60.p65](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0034.L60.p65));
  - "we need to know the exact context" ([chat-dailydialog-0040.L20.p28](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0040.L20.p28)).

  Neither is internal planning.
- **[re-check] Guessability, not continuation-shape.** NEXT means "matches the real next 40 words".
  - At predictable sites any continuation-writing lens matches more often, so the NEXT trend is expected whether or not a buffer exists.
  - Controlling for whether the L60 lens's own top-1 is the right word: -0.060 [-0.120, 0.001] (Original), -0.065 [-0.120, -0.011] (Best of 32).
  - With chat × site-kind fixed effects: -0.070 [-0.148, 0.008] (Original).
  - By source: LMSYS -0.116 [-0.206, -0.026], DailyDialog -0.053 [-0.122, 0.016].
  - Classifier biases do not drive it. Entropy does not predict bullet length (p = 0.12), NA share or CJK share. Controlling for all three leaves -0.086, and non-code chats with ≥ 40 words left give -0.077.
- **Best of 32 and Combine 32 agree.** NEXT: -0.086 [-0.139, -0.033] and -0.077 [-0.129, -0.023]. NONE: +0.053 and +0.047, both with CIs above 0.
- **Depth.** In Original the NEXT slope steepens with depth: -0.046 at L20, -0.129 [-0.209, -0.050] at L60; L60 - L20 = -0.082 [-0.158, -0.004]. Best of 32 shows no depth trend.
- **Where bullets start** (Original, L60, from lowest to highest entropy fifth):
  - the first bullet word is the reply's next word in 43% / 38% / 37% / 27% / 24% of bullets;
  - it is one of the 2nd-6th words ahead in 14% / 12% / 11% / 13% / 11%.

  So at low entropy the lens lands on the continuation more often, and skips the trivial token slightly more often.
- **Blind hand labels.** 120 validation readouts, 510 bullets, 3 readers, labelled before seeing the classifier.
  - **Non-continuation content is almost absent.** 85 of 88 human-NONE bullets are "invented continuation": continuation-shaped text with wrong content. Only 2 are meta and 1 generic. Thinking, planning or meta content is 3 of 510 bullets (0.6%), at H = 1.6 and 2.1 nats, not at low-entropy sites.
  - **Continuation-shaped share** (NEXT + invented) by entropy tercile: 0.87 / 0.95 / 0.90; T3 - T1 = +0.02 [-0.11, 0.16].
  - **Human NEXT share:** 0.65 / 0.78 / 0.83, T3 - T1 = +0.18 [-0.02, 0.37]. **Human invented-NONE:** 0.23 / 0.19 / 0.08, -0.15 [-0.29, -0.01]. This sample therefore leans the other way from the full-data classifier: slightly more invented continuations at low entropy. On the same 120 readouts the classifier is flat (NEXT 0.36 / 0.41 / 0.40). Its recall of human NEXT is the same in every tercile (0.46 / 0.46 / 0.43), so its misses do not depend on entropy. With 120 readouts the direction of the NEXT trend is not settled. The robust point is that the readouts are about 90% continuation-shaped at every entropy level.

## 3. Continuation-ness vs FVE, and a rough mediation

- **Continuation-ness tracks FVE**, as expected for an AR trained on "activation before a span".
  - Spearman(NEXT share, FVE): 0.35 [0.31, 0.38] pooled; within chat 0.34. By layer: 0.18 at L20, 0.31 at L44, 0.26 at L60.
  - With full controls, an all-NEXT readout has +0.074 [0.057, 0.089] more FVE than a readout with no NEXT bullets.
  - FVE by cont_excess quintile at L60 (Original): 0.42 / 0.45 / 0.47 / 0.49 / 0.52; Q5 - Q1 = +0.107 [0.077, 0.138].
- **Mediation** (Original, pooled). Entropy's FVE effect is +0.010 [-0.011, 0.030] without continuation-ness and +0.016 [-0.004, 0.035] with NEXT share as a control.
  - The shift (+0.006 [0.002, 0.011]) is real but tiny.
  - The reason: low entropy brings more NEXT, and NEXT brings higher FVE, which masks a little of a positive direct effect.
  - With cont_excess as the mediator: +0.006 to +0.010. Best of 32: +0.011 to +0.016.
  - No sizeable buffer effect is hidden behind continuation-ness *for the entropy rank*.
  - **[re-check]** With 1 − p(top-1) as the exposure, the direct effect with NEXT controlled is +0.035 [0.014, 0.056] (Original), +0.034 (Best of 32) and +0.033 (Combine 32), all p ≤ 0.001. It is +0.030 [0.010, 0.050] where the next token is a word. A buffer-direction effect of about 0.03 is therefore compatible with the data, depending on the proxy.
- **[re-check] Is the AR biased toward NEXT bullets, bullet by bullet?** Only slightly.
  - Within a single readout, with length and list position controlled, NEXT bullets have +0.006 [0.002, 0.009] higher solo FVE than the readout's other bullets (Best of 32 +0.009). Length matters more: +0.032 per log-word.
  - That premium does not change with entropy (+0.010 [-0.002, 0.022]).
  - So the 0.35 correlation between readout continuation-ness and FVE is mostly between cells, not a per-bullet AR premium.

## 4. Entropy vs hallucination and error proxies

Pooled, full controls, high minus low entropy, Original:

| Outcome | Q1..Q5 (all layers) | b [95% CI] |
|---|---|---|
| hallucinated | 45% 51% 47% 48% 44% | +0.041 [-0.018, 0.102] (Best of 32 +0.014, Combine 32 +0.019; both CIs include 0) |
| off_topic | 15% 9% 11% 6% 10% | -0.047 [-0.094, -0.0005] (Best of 32 -0.029, Combine 32 -0.018; CIs include 0) |
| verified wrong spans per readout | | +0.16 [-0.04, 0.37] |
| readout contains a number absent from prompt and reply | 21% 20% 21% 22% 24% | +0.054 [-0.015, 0.123] |
| readout contains a capitalised name absent from prompt and reply | 54% 50% 53% 48% 57% | +0.057 [-0.008, 0.119] (Best of 32 +0.086 [0.021, 0.150]) |
| share of judged claims that are true | | -0.036 [-0.069, -0.004] |

- **No consistent link between entropy and the hallucination rate.**
- **A faint tendency at high-entropy sites.** They have slightly more invented specifics (names, numbers) and slightly fewer true claims. This fits the lens guessing a specific branch where many are possible. See chat-dailydialog-0019.L60.p120 below: four different life-expectancy figures.
- **Off-topic readouts lean low-entropy,** but only in Original.
- **[re-check] Multiple comparisons.** Over the 3,347 estimates in `analysis_results.json`, none of the CIs above that barely exclude 0 survives Holm correction (all 1.0).
  - Off-topic (q = 0.12) and true-claim share (q = 0.07) also fail BH.
  - Names in Best of 32 and hallucination vs surprisal in Best of 32 pass BH (q = 0.03 each), but each holds in one setting only.
  - Treat this section as descriptive.

## 5. Site kinds

| Site kind | Sites | Mean H [95% CI] | Median H | H < 0.1 | In lowest fifth | In highest fifth | FVE gap vs clause (no H -> with H) |
|---|---|---|---|---|---|---|---|
| clause | 415 | 1.59 [1.41, 1.76] | 1.14 | 12.0% | 27% | 14% | reference |
| sentence | 295 | 2.26 [2.04, 2.49] | 1.68 | 3.7% | 9% | 27% | -0.045 [-0.060, -0.029] -> -0.046 |
| markup | 212 | 2.11 [1.83, 2.38] | 1.42 | 3.3% | 17% | 22% | +0.040 -> +0.040 |
| newline | 164 | 2.01 [1.66, 2.38] | 1.29 | 7.3% | 24% | 22% | -0.014 -> -0.015 |
| quote | 37 | 0.92 [0.71, 1.12] | 0.87 | 13.5% | 27% | 3% | +0.075 -> +0.075 |

The gaps are from Original with chat FE, position, words left and layer controlled. In Best of 32 and Combine 32 the gaps are similar (sentence -0.044 / -0.042) and adding entropy also moves each by at most 0.002.

- **Full stops vs commas.** Full stops (164 sites) have mean H 2.44 (median 1.82) and FVE 0.346 (all layers, Original). Commas (271 sites) have H 1.32 (median 0.90) and FVE 0.384. '!' and '?' sites: H 2.22, FVE 0.336. Colons: H 1.96, FVE 0.292.
- **Sentence ends are among the most uncertain positions.** After a sentence the model must pick what comes next. They also have the lowest FVE. Under the buffer hypothesis high entropy should mean high FVE, so the site-kind pattern runs against it, and entropy explains none of the gap.
- **Within a kind, slopes differ** (pooled, full controls, Original):
  - sentence +0.068 [0.019, 0.114]: low-entropy sentence ends, the paragraph breaks, have very low FVE;
  - markup -0.061 [-0.128, 0.018], reaching -0.103 [-0.183, -0.005] at L60;
  - clause +0.004 and newline -0.008, both flat.

  The buffer-direction slope inside sentence sites is the same boundary effect as in section 1.

## 6. Surprisal of the actual next token

- **How much it overlaps with entropy.** Surprisal asks whether the model wrote something the L60 lens did not expect. Its Spearman correlation with H is 0.35.
- **FVE rises with surprisal.**
  - Pooled b: Original +0.058 [0.034, 0.082], Best of 32 +0.054 [0.029, 0.077], Combine 32 +0.055 [0.031, 0.078].
  - At L60 (Original), FVE by surprisal quintile is 0.42 / 0.45 / 0.49 / 0.47 / 0.49.
  - With next-token-type controls: +0.052 [0.027, 0.075].
  - In a joint model, surprisal stays at +0.053 [0.027, 0.077] while entropy drops to -0.003 [-0.021, 0.016].
- **NEXT share follows entropy rather than surprisal.** In the joint model, H is -0.077 [-0.139, -0.012] and surprisal -0.034 [-0.094, 0.024].
- **Hallucination vs surprisal:** +0.084 [0.023, 0.146] in Best of 32, n.s. in Original (+0.026) and Combine 32 (+0.044).
- **Reading it, with caution.** FVE is higher where the reply departs from the lens's default next token. One possibility: where the model commits to a less obvious path, the activation carries a more specific plan for the coming text, which a continuation can explain.
- **Caveat: part of surprisal is tokenisation and lookahead.** Example: [chat-lmsys-0035.L60.p46](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0035.L60.p46). The lens puts 0.997 on ' Ferm' but the reply's token is 'F', so the surprisal is 17.6 nats. The readout still says "Fermi problem", and FVE is 0.78. Next-token-type controls reduce this problem but do not remove it.
- **[re-check] How big the tokenisation part is.**
  - At L60, 177 sites have a top-1 that is the right word in a different token (61 markup, 22 quote). Their FVE is 0.54, against 0.42 at sites where the top-1 is the exact token. Among right-word sites, the exact-token ones have -0.082 [-0.106, -0.059] lower FVE.
  - Other high-FVE cases: [chat-lmsys-0053.L60.p25](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0053.L60.p25) (FVE 0.82) and [chat-lmsys-0065.L60.p22](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0065.L60.p22) (' **' before 'narcissism', FVE 0.78).
  - Controlling for exact and tolerant correctness plus next-token type, surprisal drops from +0.058 to +0.043 [0.007, 0.078] (Best of 32: +0.042).
  - By site kind: clause +0.010 [-0.031, 0.051], sentence +0.082, markup +0.168, newline +0.065.
  - The remainder is real but sits where the model writes markup or tokenises the next word unusually.

## Examples

All are Original readouts. The class is the lexical classifier's. "next" is the reply text right after the site.

1. **Low entropy, NONE bullets, low FVE: the case that looks like the buffer.** [chat-lmsys-0015.L52.p364](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0015.L52.p364)
   - Site: clause ','. H = 0.012, top-1 ' and' at 0.999. Next: " and 4, while showing default latest ...".
   - FVE 0.110 (Best of 32 0.128, Combine 32 0.157). Judged hallucinated.
   - Bullets:
     - NONE "4 while others are labeled with age and height (ID 5,"
     - NONE "4, and "8" corresponding to different age intervals. ..."
     - BEFORE "4, and 9 while the student section includes IDs 8, ..."
     - NONE "8, and 90 for image entries. ..."
   - Every bullet skips the certain ' and' and starts at the next value. These are invented continuations, not thinking or planning.
2. **Low entropy, classifier NONE, low FVE: a paraphrased next item.** [chat-dailydialog-0070.L52.p440](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0070.L52.p440)
   - Site: newline '\n' inside a list. H = 0.002, top-1 '-' at 0.9999. Next: "- **Technology**: Renewable energy ...".
   - FVE 0.180 (Best of 32 0.244, Combine 32 0.293).
   - Bullets:
     - BEFORE "- **Technological Progress**: We already have solutions for many problems."
     - NONE "#### ✅ Rapid technological progress: ..."
     - NONE "- **Scientific Advances:** ..."
     - NONE "- **Technological & Scientific Progress**: ..."
   - This is the next list item in paraphrase. The classifier misses it.
3. **High entropy, NEXT bullets, high FVE: a number slot.** [chat-dailydialog-0019.L60.p120](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0019.L60.p120)
   - Site: markup ' **' before the figure. H = 5.48, top-1 '7' at 0.48. Next: "78 to 79 years**.".
   - FVE 0.761 (Best of 32 0.790). Judged hallucinated.
   - Bullets, all NEXT:
     - "76-78 years** (China's life expectancy in 2022 was reported at"
     - "77-78 years old**, according to the National Health Commission. ..."
     - "78.1 years** overall, ..."
     - "71–72 years** by 2021. ..."
   - Pure continuation with the wrong specifics.
4. **High entropy, NEXT bullets, high FVE: a list item.** [chat-dailydialog-0046.L60.p157](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0046.L60.p157)
   - Site: newline '\n'. H = 5.02, top-1 ' pathways' at 0.34. Next: "- Vocational education and training (VET) through TAFEs".
   - FVE 0.615 (Best of 32 0.648). Consistent.
   - Bullets, all NEXT:
     - "- TAFE or vocational training pathways (popular in Australia)"
     - "- Student visa requirements and pathways, ..."
     - "- The TAFE system (very popular in Australia), ..."
     - "- VET (Vocational Education and Training) standards, ..."
5. **Counterexample: low entropy, NEXT bullets, very high FVE.** [chat-lmsys-0045.L60.p61](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0045.L60.p61)
   - Site: markup ' **'. H = 0.013, top-1 'fr' at 0.999. Next: "frustration** and **annoyance**".
   - FVE 0.815 (Best of 32 0.818). Consistent.
   - Bullets:
     - NEXT "high frustration**, **irritation**, and **urgency**. The user is clearly experiencing technical"
     - NONE "high frustration**, **impatience**, and **irritation**. ..."
     - NEXT "高度 frustration**, **confusion**, and **annoyance**. ..."
     - NEXT "frustration**, **exasperation**, and **urgency**. ..."
   - A near-certain position with no spare-capacity signature at all. The meta regex fires on "The user is", but those are the reply's own words.
6. **Counterexample: high entropy, NONE bullets, low FVE.** [chat-dailydialog-0064.L60.p147](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0064.L60.p147)
   - Site: '.' ending a list item. H = 4.08, top-1 newline at 0.68. Next: "\n*   **Sustainable/Eco-friendly:** ...".
   - FVE 0.140 (Best of 32 0.178). Consistent.
   - Bullets:
     - BEFORE "- 3. A simpler, more grounded lifestyle (e.g., off-grid,"
     - NONE ". A different direction entirely? Each choice carries its own unique benefits and challenges. ..."
     - NONE "- A specific minimalist or ascetic path you’ve heard about. Whatever it is, the choice is yours. ..."
     - NONE "（A quieter, simpler, more sustainable lifestyle? Or perhaps a spiritual/religious path? ...）"
   - Low FVE and summary-like or alternative-listing text at an uncertain position. The third bullet echoes the reply's later closing ("Whatever it is, I support your choice!").

## Limitations

1. **The L60 logit lens is a proxy for the model's own next-token entropy.**
   - Three blocks (61-63) still run before the final norm.
   - The lens is overconfident: mean entropy is 1.90 nats against a mean actual-token surprisal of 4.03.
   - It often reads the upcoming content word rather than the exact next token.
   - L52 and L60 entropies agree only weakly (Spearman 0.33).

   Noise in the proxy pulls every entropy effect toward zero. The CIs rule out FVE slopes beyond about ±0.04-0.05 *for this proxy*, and a true-entropy effect could be larger by an unknown factor. ~~It is hard, though, for noise to produce the depth pattern seen here.~~ **[re-check]** The depth pattern is not significant as a linear trend (point 2 of the short answer), so it is no evidence either way. True final-layer entropy would need a full forward pass, which is out of scope here (no GPU).

   **[re-check] Calibration of the proxy** (independent recompute, `skeptic/lens_summary.json`):
   - **Accuracy.** L60 top-1 is the exact next token at 35% of sites and the right word, ignoring tokenisation, at 50%. Calibration error: 0.27 exact, 0.13 tolerant.
   - **Ordering.** The proxy ranks only the confident part of the range. By entropy fifth, actual-token surprisal is 3.11 / 3.61 / 4.40 / 4.46 / 4.55 and tolerant accuracy 0.80 / 0.61 / 0.46 / 0.31 / 0.32. So the top 40-60% of sites are not ordered by the proxy against either check, and the rank exposure mostly contrasts confident sites with everything else.
   - **Confident bins work.** When p(top-1) ≥ 0.99 (74 sites with a next token), the lens is right 84% exact and 89% tolerant.
   - **Other layers are not a check.** The L52 lens (top-1 12%, mean H 6.9 nats) is not a usable proxy. Lens entropies of L20-L52 correlate 0.10-0.33 with L60. So "does L52 give the same ordering?" is answered no, and that says more about L52 than about L60.
2. **Next-token entropy is not uncertainty about the upcoming content.** At block boundaries the next token is a certain '\n\n', but the next section is open. Those are exactly the sites where FVE dips. A test closer to the hypothesis would need entropy over the next several tokens.
3. **FVE can only see continuation-shaped content.** Non-continuation computation can only appear as unexplained variance, and 1 - FVE is 43-80% at every entropy level. A buffer that is the same size everywhere would be invisible to this test. It only detects a buffer whose size changes with entropy.
4. **The readouts cannot reveal what the AR cannot score.** The lens was RL-trained to maximise this FVE, so it is pushed toward continuation text whatever the activation holds.
5. **The continuation classifier is noisy.** It misses about half of real continuations (recall 0.44; paraphrases end up as NONE), and the small hand-labelled sample leans the other way on NEXT. Treat the NEXT/NONE trends as tentative. The FVE results do not depend on the classifier.
6. **Missing inputs.**
   - The read token's own surprisal is not available: it needs the activation at pos-1.
   - The reply decoding settings are unknown.
   - The number and name novelty proxies are regex-based and rough.

## Skeptic re-check: what survives

**Rerun with independent code.** The code is in `entropy/skeptic/`: `lens_check.py`, `recheck.py` and `probe2-5.py`. It uses CR1 cluster-robust SEs by chat plus a 1,000-draw chat bootstrap with a new seed. It reproduces:
- the FVE slopes +0.009 / +0.011 / +0.013;
- the per-layer slopes and the L60-L20 contrasts;
- the near-deterministic dip, +0.033 / +0.022 / +0.008;
- NEXT -0.085, NONE +0.050, hallucination +0.041;
- the sentence gap, -0.045 to -0.046;
- surprisal +0.058;
- Spearman(NEXT, FVE) 0.346 and the mediation, +0.016.

The logit lens was recomputed from the weights: top-1 0.3503 and mean surprisal 4.025, both identical. All example keys and their quoted FVE, H and labels check out, and so do the hand-label counts: 510 bullets, 85 invented, 2 meta, 1 generic.

**Corrections.**
1. The meta-share column had the wrong predicted sign. The observed meta trend leans toward the buffer; it is tiny, not significant and mostly persona speech.
2. "FVE is flat" holds for the entropy rank only. With 1 − p(top-1) from the same lens, there is a buffer-direction slope of about +0.03 (p < 0.01). It is +0.035 with continuation-ness controlled and survives at next-is-word sites.
3. "It fades with depth" is not supported. The linear trend test is not significant; only end-point contrasts in two settings exclude 0.
4. The NEXT-share trend is reframed as guessability, not evidence against the buffer.
5. Most CI-excludes-0 secondary claims fail multiple-comparison correction. The file holds 3,347 estimates with CIs, 1,344 of them excluding 0. Under Holm, only surprisal → FVE, the L52-lens slope and the sentence and markup site-kind gaps survive (quote: Holm p = 0.06).
6. The surprisal effect is about one quarter tokenisation artifact (+0.058 → +0.043) and absent at clause sites.

**What survives.** No test here finds the large, depth-growing FVE deficit at low-entropy positions that the text-buffer idea predicts. Any buffer-direction effect is at most about 0.03 FVE, an eighth of the layer effect. It is concentrated at the most confident ~7% of sites and partly at paragraph breaks and reply ends, and its sign depends on how lens confidence is summarised. The readouts are about 90% continuation-shaped at every entropy level, with essentially no planning content. But a lens RL-trained on this FVE would write continuation regardless, so this does not rule out non-continuation content in the unexplained 43-80% of variance. The sentence-end FVE gap and the absence of an entropy-hallucination link are robust. The cleanest next test needs a GPU: score the AR on the *actual* reply continuation at each site, removing lens quality, and use true final-layer entropy over the next several tokens.

## Files

- `entropy/skeptic/`: the re-check.
  - `lens_check.py` → `lens_sites.jsonl`, `lens_summary.json`: lens recompute, variants and calibration, all layers.
  - `recheck.py` → `recheck_results.json`, `cells.pkl`: replication, proxies, confounds, classifier bias, multiple comparisons.
  - `probe2-5.py` → `probe2_results.json`: the 1 − p(top-1) proxy, deciles, meta sign, surprisal artifact.
  - `mc.py` → `mc_results.json`: BH/Holm over `analysis_results.json`.
  - `patch_page.py`: applies the re-check corrections to `entropy_page.json`. Rerunning `analysis.py` overwrites them, so rerun `patch_page.py` afterwards.
- `entropy/analysis.py`: all statistics. `python -B analysis.py candidates` prints example candidates.
- `entropy/analysis_results.json`: every number above, plus per-setting and per-layer detail and robustness checks.
- `entropy/entropy_page.json`: compact data for a page section (headline lines, per-layer FVE stats, quintiles, continuation, hallucination, site kinds, surprisal, hand labels, examples).
- `entropy/examples_chosen.json`: the 6 examples and their notes.
- `entropy/hand_labels/`: copies of the three blind-label files used in section 2.
