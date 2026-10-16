# Conjunctive association: does per-bullet FVE prefer the right filler?

This is exploratory work, and the item bank was inspected beforehand. Setup: Qwen3.6-27B and the frozen O-lens on the 100 WorkspaceBench conjunctive-association vignettes.
- Read grid: 5 read sites × 5 layers (20/36/44/52/60), giving 2,500 cells.
- 3 settings per cell, 32 samples each.
- 29,979 selected bullets and 319,531 pool bullets.

All numbers below were **recomputed by independent code**, `analysis/ca/skeptic/skeptic_run.py`. It reads `data/select`, `data/metrics`, the LLM-label file, the lexicon files and the judge rows directly. It takes only the lex2 label column from the analyst's cache, joined by key with 0 text mismatches. Every analyst headline reproduced exactly. No API calls, no GPU; the ledger is unchanged at $1.35 of the $30 cap.

**Terms** (each defined once)
- **Case key** `item.L<layer>.p<pos>`.
- **Cell**: one item, layer and read position.
- **Readout**: the ≤4 bullets that one setting writes for a cell. The settings are **Original** (first sample), **Best of 32** (the sample with the highest joint FVE) and **Combine 32** (pool bullets added greedily by FVE). Values are always in that order.
- **Pool**: the first 4 bullets of all 32 samples of a cell, de-duplicated by AR vector.
- **Solo FVE**: how much of the activation one bullet explains alone.
- **Contrast axis (X)**: the one part where the gold compound and its contrast option differ, e.g. *grief* vs *guilt* over "the sudden accidental death of her young child".
- **Bullet labels:**
  - **gold**: names gold's X value (right filler).
  - **wrong value**: names the contrast's or another X value (wrong filler).
  - **frame-only**: names shared content (event, relation, object) and no X value.
  - **none**: names none of these.
- **Labelers:**
  - **LLM**: GPT-6 Luna; selected bullets only.
  - **lex2**: the analyst's refined regex lexicon; covers every bullet.
  - **Strict wrong value**: both labelers say wrong value.
- **Pair rate**: P(the A bullet's solo FVE > the B bullet's) within the same readout or pool. Ties count ½; 0.5 means no preference.
- **Position-adjusted**: minus the mean at the same setting, layer, readout size and list slot. Used for Original and Best of 32 only; Combine 32 stays raw because its order is the greedy FVE order.
- **Length-matched**: scored token counts within 20%.
- **Brackets**: 95% bootstrap over the **10 related-item groups** q01–q10 (2,000 reps), unless marked "(items)", which means over the 100 items. Ten groups make these intervals approximate, so for small tests I give the wider of the two.

## 1. Bottom line

**No. FVE does not prefer a bullet that names the right value over one that names a wrong value in the same frame.**
- Within a cell's 32-sample pool, a gold bullet beats a wrong-value bullet **0.490 [0.479, 0.528]** of the time (67,618 pairs, 371 cells).
- Naming *any* value is rewarded slightly over the frame alone, and the reward is the same for right and wrong values:

| Comparison | Rate |
|---|---|
| gold > frame-only | 0.524 [0.506, 0.545] |
| wrong value > frame-only | 0.525 [0.509, 0.540] |
| gold > none | 0.561 [0.548, 0.571] |

- **In FVE units, within the same cell**, using a regression with cell fixed effects:
  - gold instead of a wrong value: **+0.0014 [−0.0021, 0.0044]**, about 0.03 within-cell SD (SD = 0.055);
  - any value over frame-only: about +0.005;
  - opening the bullet with a list, heading or `<think>` marker: **−0.070**, about 1.3 SD.

Surface form matters about 10× more than content, and content ~3× more than which value is named.

**What the intervals rule out.** They exclude a preference for the right value as large as content-vs-none (0.56). They do not exclude one as small as the content-vs-frame effect (≈0.52).
- On the 64 items whose contrast words are specific (the subset with the most precise wrong-value labels), the upper bound is about 0.57.
- Label noise cannot hide a large effect. About half of all wrong-value labels are real, but on the specific-word items about 85% are, and the rate there is still 0.486 [0.424, 0.565].

**Selection does not find the right value either.**
- Best of 32 contains a lex2-gold bullet **+1.2 points [0.1, 2.1]** more often than a random one of the 32 samples (25.7% vs 24.6%).
- Combine 32 does so +0.4 points [−0.6, 1.5] more often than 4 random pool bullets.
- The pool holds a gold bullet in 54.8% of cells, yet 53–55% of the readouts from those cells have none.
- Per-cell judge gold rates are 3.1 / 3.3 / 3.6%, and the differences cross zero.

**FVE does not follow the lens's own consensus either.** Within a cell, a bullet naming the value the pool names *most often* beats one naming the minority value only **0.507 [0.469, 0.547]** (352 cells). There is no trend with gold's share of value mentions (Spearman 0.05).
- In 105 of the 371 cells, wrong values outnumber gold in the pool.
- So FVE is blind to the value against both references: the story's truth and what the lens usually says.

This is the "frame, not filler" result of Hallucination and the three olens-improve families, here on a designed minimal pair.

## 2. Numbers

**A3. Within the cell's pool, gold vs wrong value** (lex2 labels on all pool bullets)

| Variant | Pair rate | Pairs / cells |
|---|---|---|
| All items (headline) | 0.490 [0.479, 0.528]; items [0.459, 0.518] | 67,618 / 371 |
| Mean of per-cell rates (each cell weighted equally) | 0.508 [0.479, 0.540] | 371 |
| Contrast option only (not other values) | 0.474 [0.441, 0.528] | 46,296 / 331 |
| Specific-word items (chosen after reading) | 0.486 [0.424, 0.565] | 10,514 / 137 |
| Both bullets also name shared story content | 0.496 [0.481, 0.530] | 20,459 / 234 |
| Specific-word items and in-frame | 0.476 [0.413, 0.550]; per-cell mean 0.42 [0.35, 0.48] | 4,469 / 80 |
| No Chinese characters, no scaffold opening | 0.473 [0.460, 0.510] | 28,449 / 259 |
| Same list slot | 0.504 [0.494, 0.546] | 16,502 / 337 |
| Length-matched | 0.500 [0.484, 0.540] | 40,028 / 363 |
| Balanced over the two directions of a pair (7 groups) | 0.492 [0.457, 0.524] | |
| Leave one group out | 0.487–0.493 | |

By layer (L20 / 36 / 44 / 52 / 60): 0.40 (31 cells, 5 groups) / 0.53 [0.51, 0.59] / 0.48 / 0.46 / 0.50. One layer of five sits above 0.5, with no trend, which fits chance across five tests. By read site: 0.47–0.56, and every interval includes 0.5.

**Regression within cell** (pool, solo FVE, 318,937 bullets).
- Controls: list slot, log length, Chinese, scaffold opening, summary-format echo, story-name echo, a shared-content word.

| Effect | Labels only | With controls |
|---|---|---|
| gold − wrong value | +0.0014 [−0.0021, 0.0044] | +0.0020 [−0.0009, 0.0044] |
| gold − frame-only | +0.0054 [0.0025, 0.0085] | +0.0064 [0.0034, 0.0091] |
| wrong value − frame-only | +0.0040 [0.0016, 0.0062] | +0.0044 [0.0024, 0.0062] |

- Controls themselves:
  - scaffold opening −0.070 [−0.077, −0.063];
  - a capitalized story word, mostly the character's name, +0.021 [0.013, 0.032];
  - summary-format echo ("in one sentence", "Here's a concise …") +0.010 [0.008, 0.012];
  - overlap with story content words −0.001 [−0.008, 0.007];
  - log tokens +0.023 per e-fold;
  - list slot 1 vs 0 +0.015.
- On the specific-word items, gold − wrong value is +0.0007 [−0.0031, 0.0056].

**A2. Within one readout** (position-adjusted, pooled over settings)

| Comparison | Pair rate | Pairs |
|---|---|---|
| gold vs non-gold siblings | 0.533 [0.513, 0.548]; length-matched 0.514 [0.496, 0.528] | 5,360 |
| per setting | 0.538 / 0.520 / 0.542 | |
| gold vs strict wrong value | 0.537 [0.40, 0.79] | 67 (40 readouts, 7 groups) |
| gold vs any wrong value | 0.452 [0.383, 0.597] | 261 |
| gold vs bullets the LLM itself called contrast | 0.485 [0.391, 0.620] | 101 |
| LLM gold vs LLM contrast (LLM labels only) | 0.478 [0.400, 0.614] | 115 |
| gold vs frame-only | 0.527 [0.503, 0.544] | 1,773 |
| gold vs none | 0.580 [0.540, 0.602] | 1,937 |
| frame-only vs none | 0.548 [0.528, 0.569] | 4,797 |

- **Readout fixed-effects regression, Original + Best of 32** (list-slot dummies, log length):
  - gold − strict wrong value +0.007 [−0.004, 0.016]; items [−0.010, 0.024];
  - gold − frame-only +0.007 [0.001, 0.012].
- **Same regression, Combine 32:**
  - gold − wrong value −0.001 [−0.019, 0.008];
  - gold − frame-only +0.001 [−0.003, 0.005]. In Combine 32, gold does not even beat the frame.
- The within-readout filler test is too small to be informative on its own.

**A4. Selection**

| | Original | Best of 32 | Combine 32 |
|---|---|---|---|
| Readout has a final-gold bullet (either labeler) | 27.7% | 28.7% | 28.1% |
| Readout has a lex2-gold bullet | 25.2% | 25.7% | 24.6% |
| Random baseline (lex2) | | one of 32 samples: 24.6% | 4 pool bullets: 24.2% |
| Selected minus random | +0.6 [−0.6, 2.1] | +1.2 [0.1, 2.1] | +0.4 [−0.6, 1.5] |
| Readouts with no gold, among cells whose pool has one | 54.1% | 53.0% | 55.1% |
| Judge picks gold, per cell | 3.08% | 3.32% | 3.64% |
| Judge, change vs Original | | +0.24 pts [−0.48, 0.92] | +0.56 [−0.12, 1.32] |

- **Sample level, within cell** (joint FVE):
  - gold-naming samples vs others: 0.515 [0.511, 0.519];
  - vs samples naming only a wrong value: 0.508 [0.456, 0.527].
  - On the specific-word items: 0.446 [0.429, 0.481]; items [0.410, 0.490]. This post-hoc subset leans toward wrong values.

**A1 note.** The analyst's raw means by label are pooled across cells (pool: gold 0.190, contrast 0.191, frame-only 0.175, none 0.131). Mean solo FVE rises from 0.08 at L20 to 0.23 at L60, and the gold rate rises from 1% to 16%. Within the same cell, gold sits only +0.0125 above none, against a raw gap of 0.059, so about 80% of the A1 ladder is layer, site and item composition. The ordering survives within cell: gold ≈ wrong value > frame-only > none.

## 3. Are the labels right? (checked against the three readers and the analyst's readings)

**Gold labels name gold's word with high precision, but often not the whole compound.**
- lex2 gold, random pool sample: 22/25 state it, 3 borderline, 0 wrong.
- Focal gold bullets read by readers 0–2: 22/24 (8/8, 5/7, 9/9). Reader 1's two misses have the wrong holder.
- Reader 2 coded every gold-labelled bullet in 12 readouts: 19 right value in the right slot, 7 right value in the wrong slot (wrong agent, holder or object), 1 frame-only.
- Reader 0 found 4 of 8 focal gold bullets with another part of the compound wrong or missing.
- So the test is right *word* vs wrong *word*, not right compound vs wrong compound.
- Recall on reader 0's 48 bullets: LLM 28/32, lex2 19/32, both with no false positives.

**About half of the wrong-value labels are real.**

| Reading | States a wrong value | Borderline | Not a wrong value |
|---|---|---|---|
| lex2 random pool | 11/25 | 8 | 6 |
| lex2, specific-word items | 17/20 | 2 | 1 |
| Strict, selected (analyst's reading) | 14/25 | 11 | 0 |
| High-FVE strict wrong values (focal, readers 0–2) | 5/12 | 4 | 3 |

- 102 of the 177 strict rows (58%) are LLM "other_wrong". The LLM never said "contrast" there, so the X-axis attribution comes from the lexicon alone.
- lex1 and lex2 are the same lexicon family; they agree on 99.6% of pool bullets. **The main pool test therefore rests on one labeler.**
- **Attenuation check.** If mislabeled "wrong" bullets behave like gold or frame bullets (rate about 0.50–0.52), the observed 0.490 at roughly 50% precision implies a true rate of about 0.46–0.48. On the specific-word items (about 85% precision), the observed 0.486 implies about 0.48.
  - Hiding a true 0.55 there would require the mislabeled 15% to lose to gold about 88% of the time, which is implausible.
  - Noise therefore cannot explain the null; if anything, real wrong values score slightly higher.
- **Failure modes** seen in reading:
  - word sense ("car accident", a retirement "test");
  - the value in the pretense slot ("dismissed … as a relief", while the bullet says she is heartbroken);
  - Chinese negation, which the lexicon does not cancel ("非 accidental" means not accidental).

## 4. Confounds

- **Position.**
  - The first bullet of a sample sits at the 40th within-cell percentile; later bullets sit at the 53rd–55th.
  - Wrong-value bullets sit slightly later (mean slot 1.69 vs 1.55 for gold) and are slightly longer (25.9 vs 25.0 tokens). That explains the small wrong-value lead in the headline: same-slot 0.504, length-matched 0.500.
- **Length.**
  - The percentile rises from 13th (≤8 tokens) to 55th (24–31 tokens).
  - Length matching moves A2 gold vs siblings from 0.533 to 0.514.
- **Scaffold openings** ("1.", "2:", "**", "#", "<think>", "summary**:").
  - These are 6.6% of pool bullets. They sit at the 25th percentile against the 52nd for other bullets, a −0.070 FVE effect with controls.
  - Gold bullets carry more scaffolds than contrast bullets (8.1% vs 5.5%), which works against gold. Removing them does not help gold (0.473).
- **Echo of the prompt.**
  - Overlap with story content words: no effect (−0.001). The stimuli block the key words by design.
  - Reusing a capitalized story word, mostly the character's name: +0.021 FVE, about 3× the gold-vs-frame effect. Gold and contrast bullets do it equally often (16.5% vs 16.9%).
  - Summary-format echo: +0.010. It appears in 29% of "none" bullets against 7–8% of gold and contrast bullets, so it narrows frame-vs-none, not gold-vs-wrong.
- **Chinese vs English.**
  - 46% of pool bullets contain Chinese characters, usually one leading Chinese word that continues the carrier ("晋升 (promotion) of her colleague…").
  - They are concentrated in list slots 1–2 and at the `ize` (72%) and `\n`-after-`<|im_end|>` (66%) sites.
  - Raw effect: none (51st vs 50th percentile). With controls: −0.024 FVE, but the sign flips by layer (L20: 43rd vs 58th; L36–60: 52nd–56th vs 46th–48th). So there is no consistent effect.
  - It does not drive the filler test: gold 43% vs contrast 37% Chinese, and the subset without Chinese gives 0.473 [0.460, 0.510].
  - lex2 recall of LLM-gold is 55% on Chinese bullets vs 61% on English bullets.
- **Layer.**
  - L20 is almost empty: pool gold rate 1.0% vs 11–16% at other layers; judge gold 0.13%; 4% of L20 readouts have a lex2-gold bullet vs 27–34%.
  - The gold-vs-wrong rate by layer has no pattern (section 2).
- **Read-site kind.**
  - The chat-template sites are live, not dead. `\n` after `assistant` has the highest per-cell judge gold rate (4.5%). `\n` after `<|im_end|>` has the lowest (2.2%) and the lowest pool gold rate (8.2% vs 11.5–13.5%).
  - The gold-vs-wrong rate is 0.47–0.56 at every site, and every interval includes 0.5.
- **Item clustering.**
  - **79% of A3 pairs come from two of the ten groups**: q01 49.6% and q04 29.7%. These are the groups with the least specific wrong-value words: q01_e–j's relation axis and q04's hidden/credit.
  - The per-cell mean (0.508 [0.479, 0.540]) and leave-one-group-out (0.487–0.493) give the same answer.
  - The two directions of a pair sometimes move in opposite ways, the pattern expected if FVE prefers one word whatever is true. In q07 the "keeping it hidden" bullets win in both directions (0.61 when hidden is gold, 0.42 when telling is gold). In q10 the "deliberate" bullets win in both (0.53 when deliberate is gold, 0.33 when accidental is gold). Each direction's interval is wide, and the word-preference intervals include 0.

## 5. Examples (verbatim; solo FVE; pct = within-cell percentile)

**Same frame, different value, similar or reversed FVE**
- **q02_c.L60.p98 pool** (gold envy, contrast pride):
  - gold s25.1 "After receiving news of her colleague Dina's publishing success, Dana privately suppresses her envy and reads the accolades on their" 0.516;
  - contrast s18.3 "After receiving a congratulatory note from her sister Leah, Dana suppresses her own recognition to avoid overshadowing the celebration. Although she is proud" 0.489;
  - contrast s22.1 "…Dana quietly suppresses her pride upon learning of her best friend's triumph, choosing instead" 0.466.
- **q02_c.L52.p89 pool:**
  - contrast s24.3 "Anna silently celebrates her friend Mira's literary success two years after her own, suppressing her own pride out of respect." 0.262 (pct 0.98)
  - beats gold s15.2 "Dina quietly supports Ben's literary achievement after hearing of his acceptance, while suppressing her own envy." 0.229 (pct 0.93).
- **q01_c.L44.p92 Best of 32** (gold grief, contrast guilt):
  - [2] "Lisa, overwhelmed by guilt and duty, prepares to pack her father's possessions for her aunt while reflecting on their estranged relationship…" 0.407 (share 0.56);
  - [1] "While packing her mother's belongings for her sister, a grieving woman prepares to send a package of letters to a son she does not know." 0.143.
- **q09_a.L44.p80 pool** (gold relief; 42 contrast vs 2 gold bullets):
  - contrast s28.2 "当 Bill discovers his job loss is cancelled, he quickly masks his disappointment with enthusiastic household planning…" 0.300 (pct 0.99);
  - gold s13.3 "Despite Sarah's apparent job loss, her husband's relief quickly transformed their household into a cheerful environment…" 0.205 (pct 0.34).

**Surface form outweighs content** (both bullets in each pair are labelled gold)
- **q04_a.L52.p73 Best of 32:**
  - [1] "1. **Concealing a Mistake:** On Monday, Ren secretly disposed of the incorrectly filed documents to hide the error," 0.0036;
  - [3] "To evade the consequences of a printing error, Raissa secretly disposed of the damaged paper, concealed the evidence…" 0.410.
- **q01_c.L60.p88 Combine 32:**
  - [3] "summary**: Confronted with the deadline to vacate the house, Nora packs boxes while grieving her dying mother…" 0.027;
  - [0] "Amidst a deadline to vacate a room, Nora sorts personal items while grappling with grief and obligation…" 0.450.
- **q01_c.L60.p88 Best of 32:** [2] "Summary:** Trapped between a move deadline and the death of her grandmother…" 0.0075 vs [1] (same text as above) 0.450.

**Wrong-value labels that are not wrong values**
- **q10_b.L36.p92 Original [3]** (lex2 contrast via "accident"; it is a word-sense hit): "After surviving a car accident and receiving a care package from an ex, Elena secretly sent it back to the sender to conceal his continued survival." 0.269 (95.7th percentile).
- **q09_f.L52.p84 Best of 32 [3]** (lex2 contrast; actually states gold): "While Elena verbally dismissed Mark's canceled anniversary trip as a relief, her secretive purchases and continued planning reveal that she is secretly heartbroken and" 0.458, the top of its readout.
- **q10_c.L52.p68 pool s14.1** (labelled contrast, i.e. accidental; "非" means not, so it states deliberate, the gold value): "非 accidental deletion of her drive after others' drives were intact. It's a story about targeted sabotage…" 0.255 (pct 0.98).

**Gold labels with the right word in the wrong slot**
- **q08_c.L60.p67 Original [0]** (both labelers say gold; but the protagonist is the oblivious one): "Elena effortlessly enjoys her career success, oblivious to Marcus's lingering resentment…" 0.249.
- **q09_i.L60.p67 Original [1]** (gold is his belief that his *sibling* is disappointed): "亚当 faces disappointment after his apartment application is rejected, returning to fold away canceled plans." 0.156.
- **q10_g.L52.p108 pool s11.0** (gold is that her sibling destroyed it by accident; here she did): "Tess regrets discarding a book after her ex-boyfriend disappeared, fearing she accidentally destroyed a" 0.352.

**Selection misses a high-FVE gold bullet**
- **q02_a.L52.p75:** the pool has s21.1 "提拔 of their colleague to CEO, triggering jealousy and a tense confrontation." 0.363 (pct 0.98). Best of 32 chose a sample with no feeling word: [0] "晋升 (promotion) of her colleague, Clara, leaving Jane in the dark." 0.348.
- **q02_a.L44.p75:** the pool has s11.2 "…It explores deep resentment, professional envy, and the" 0.229 (pct 0.95). Best of 32's four bullets are all frame-only, e.g. "任命 of a colleague and the devastating realization that this day marks the end of their friendship…" 0.262.

## 6. Comparison with earlier results

| Study | Test | Result |
|---|---|---|
| Hallucination (chat) | clean beats WRONG, same readout | 0.511 / 0.504 / 0.503; length-matched 0.52–0.55 |
| | WRONG label effect | −0.003 FVE (−0.04 SD) |
| Multihop | hit vs siblings (adjusted) | 0.55 |
| Chained | hit vs siblings (adjusted) | 0.58 |
| | correct vs wrong carrier, same cell | 0.52 [0.45, 0.58] |
| Role-bound | hit vs siblings (adjusted) | 0.54 |
| | hit vs all-three-named failed readout | 0.52 [0.48, 0.57] |
| Three families | Best of 32 vs random, judge pass | +0.2 / +1.4 / +0.2 pts |
| **Conjunctive (here)** | gold vs non-gold siblings | 0.533 |
| | gold vs wrong value in the pool | 0.490 |
| | gold − wrong value | +0.0014 FVE (0.03 SD) |
| | Best of 32 vs random | +1.2 pts (lex2 gold); +0.24 pts (judge) |

- **Same size, same direction.** The surface drivers are also shared with Hallucination: length, later list slot, a clean opening, echoing the prompt.
- Conjunctive association is the most direct filler test so far: the wrong value is a designed minimal pair inside an identical compound, and it has 67,618 within-cell pairs.
- One difference from Hallucination: Chinese has no consistent effect here. Hallucination favoured English.

## 7. Corrections to the analysis write-up

1. **Bootstrap unit.** The write-up gave 100-item intervals. Over the 10 related-item groups they are similar for the big tests and wider for the small ones (A2 strict: [0.40, 0.79]).
2. **Strength of the "no".** Write "no detectable preference". The upper bounds are about 0.53 for all items and about 0.57 for specific-word items, so a preference as small as the content-vs-frame effect is not excluded.
3. **A3 headline weighting.** 79% of its pairs come from q01 and q04, the least specific groups. Report the per-cell mean (0.508 [0.479, 0.540]) next to it.
4. **A1 is mostly composition.** The A1 label means are mostly between-cell (layer) composition; the within-cell gaps are about 5× smaller.
5. **Strict wrong-value label.** About half of the strict wrong values are real. Show the LLM-only check (0.478–0.485) beside it.
6. **"Gold" means right word.** It does not mean the right compound: about 1 in 4 gold bullets has the wrong holder or agent (reader 2: 7/27).
7. **Misquoted number.** "Samples naming only a wrong value beat gold, 0.452 [0.413, 0.495]": results.json and my recomputation both give 0.446 [0.410, 0.485] (items) / [0.429, 0.481] (groups). This is a post-hoc subset (99 cells, 32 items) and suggestive only.

## 8. Caveats

- **Item choice.** Exploratory, and the specific-word subset was chosen after reading.
- **Labels.** The pool test uses one lexicon labeler, with about 50% wrong-value precision overall.
- **Group count.** Only 10 related-item groups, and two of them dominate the pairs.
- **Pool metric.** Pool solo FVE has no joint context; Shapley share and leave-one-out drop exist only for the selected readouts.
- **Judge and grid.** Reduced grid, and the judge is Luna, not WSB's pinned judge.
- **Lens consensus is a proxy.** "Consensus" is measured by sample counts, an imperfect stand-in for what the activation encodes.
- **Not recomputed.** The top-share-is-gold figures (+5.7 / +2.3 / +4.2 points over chance) and A5 (judge kappa 0.13 / 0.32; P(judge gold) 52% when one bullet names every part) are the analyst's numbers.
- **Untested causally.** A6, the filler swap (grief→guilt in the same bullet, re-encoded), would test causally whether FVE ignores the value.

Files (all under `${OLENS_SCRATCH}/olens-bullet-fve/newtasks/analysis/ca/skeptic/`):
- code: `skeptic_build.py`, `skeptic_run.py`, `skeptic_examples.py`, `skeptic_cjk.py`, `skeptic_majority.py`;
- results: `sk_results.json`;
- logs: `logs/{build,run,examples,cjk,majority}.log` (the verbatim examples are in `logs/examples.log`);
- cache (rebuildable): `cache/sk_tables.pkl`.

Reader records: `analysis/ca/read_records_{0,1,2}.json`.
