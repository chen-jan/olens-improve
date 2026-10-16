# User modelling: does per-bullet FVE prefer the right value?

This is exploratory work, and the item bank was inspected beforehand. Setup: Qwen3.6-27B and the frozen O-lens on the 100 WorkspaceBench user-modelling chats (47 selfdescribe, 53 synthsys).
- Read grid: 6 read sites × 5 layers (20/36/44/52/60), giving 3,000 cells.
- 3 settings per cell, 32 samples each.
- 35,990 selected bullets and 382,071 pool bullets (after de-duplication).

**All headline numbers were recomputed by independent code** in `analysis/um/skeptic/`:
- `sk_build.py` and `sk_run.py` read `data/select`, `data/metrics`, the lexicon-v2 label file and the judge rows directly.
- They rebuild the 32-token AR window with the method's own `ar_token_ids`, and re-run the lexicon on truncated windows.
- Echo flags, frame keys, surface features, the bootstrap and the regressions are my own code. `analysis.py` was not imported.
- Every analyst headline reproduced to within bootstrap noise.

No API calls and no GPU. The ledger is unchanged at $2.40 of $30.

**Terms** (each defined once)
- **Case key** `item.L<layer>.p<pos>`. A **cell** is one item, layer and read position.
- **Readout**: the ≤4 bullets one setting writes for a cell.
- **Settings**, always in this order:
  - **Original**: sample 0, itself a random one of the 32.
  - **Best of 32**: the sample with the highest joint FVE.
  - **Combine 32**: pool bullets added greedily by FVE.
- **Pool**: the first 4 bullets of all 32 samples of a cell, de-duplicated by AR vector.
- **sNN.k**: sample NN, bullet k.
- **Solo FVE**: how much of the activation one bullet explains alone.
- **pct**: a bullet's percentile within its cell's pool.
- **Subfamilies**:
  - **selfdescribe**: the user gives cues ("kimchi jjigae") and asks for an infobox "for me". The value must be inferred.
  - **synthsys**: the system prompt **states** the value ("the user is from Antarctica"). The request is unrelated.
- **Bullet labels** (lexicon v2, string match, no API):
  - **gold**: names the user's value. This can be a name ("Ukrainian", "locksmith", "divorced"), a region word covering gold and no option ("South American"), a cue ("kimchi") or a pronoun ("he").
  - **wrong value**: names another value of the same class and not gold. This can be a **distractor** (one of the judge's 4 options) or an **other value** ("Russian", "sailor"; for Antarctica items "Arctic/North Pole").
  - **frame-only**: names the attribute ("your location", "dietary needs") but no value.
  - **none**: names none of these.
  - **Name level**: name and region-word mentions only.
- **Copied gold (echo)**: every gold mention copies the prompt. Two rules:
  - the **analyst rule**: the word or its stem is in the prompt, or, in synthsys, it is any exact form of the stated value, including translations;
  - my **strict rule**: in synthsys every gold mention counts as copied, because the value is stated; in selfdescribe the word/stem test applies.
  - **Inferred gold**: not copied.
- **Pair rate**: P(the A bullet's solo FVE > the B bullet's) within the same pool or readout. Ties count ½; 0.5 means no preference.
- **Per-cell mean**: each cell weighted equally instead of each pair.
- **Position-adjusted**: minus the mean at the same setting, layer, readout size and list slot. Used for Original and Best of 32; Combine 32 stays raw, because its order is the greedy FVE order.
- **Length-matched**: scored token counts within 20%.
- **Same frame**: the first 4 words are equal once every value word is replaced by VAL.
- **Brackets**: 95% bootstrap over the **31 related-item groups** (attr_class:attr), 2,000 reps. "items" marks the 100-item version.

## 1. Bottom line

**FVE shows a small, real preference for the right value, too small to use.**
- Within a cell's pool, a gold bullet beats a wrong-value bullet **0.534 [0.506, 0.568]** of the time (items [0.511, 0.557]; 160,820 pairs, 490 cells). The per-cell mean is **0.520 [0.501, 0.548]**.
- Gold is ahead in 51% of cells and behind in 46%.
- **In FVE units, within the same cell** (a regression with cell fixed effects and controls; within-cell SD 0.068):
  - gold − wrong value: **+0.0050 [0.0017, 0.0092]**, about 0.07 SD;
  - one e-fold of bullet length: +0.034;
  - overlap with prompt words: +0.040 per unit share;
  - a leading Chinese token: −0.0075.
- The intervals rule out a preference above about 0.57. They do not rule out one of 0.51–0.55.

**The preference does not come from copying the prompt.** This corrects the analysis write-up.
- Inside the same cell, copied gold does not beat inferred gold:
  - pair rate 0.495 [0.478, 0.510] (analyst rule) and 0.490 [0.479, 0.498] (strict rule);
  - regression: copied − inferred +0.0022 [−0.0006, 0.0049] and +0.0004 [−0.0028, 0.0037].
- Inferred gold in selfdescribe (real inference from cues) beats wrong values by +0.0048 [0.0023, 0.0081], the same as copied gold (+0.0052).
- The analyst's split (copied 0.560 vs not copied 0.513) mixes two other things: which cells the pairs come from, and synthsys "not copied" mentions (finer places, region words) that score low (0.472).

**Where the edge does come from:**
- **One item group.** Three Antarctica items give 13% of all pairs, at 0.61 (gold "Antarctica" vs "Arctic/North Pole"). Without them: 0.523 [0.501, 0.556]; regression +0.0043 [0.0010, 0.0087].
  - Four of the five next-largest groups sit below 0.5: fisherman 0.478, Ukraine 0.488, Europe 0.475, halal 0.485. Locksmith, the fifth, sits at 0.495.
- **In synthsys, wrong values are penalised; gold is not rewarded.**
  - Relative to frame-only bullets: wrong − frame **−0.0068 [−0.0102, −0.0037]**, gold − frame +0.0009 [−0.0055, 0.0074].
  - In selfdescribe the reverse holds: gold − frame +0.0043 [0.0022, 0.0077], wrong − frame +0.0006 [−0.0016, 0.0023].

**With the frame held fixed, the per-cell preference vanishes.** Same frame: pooled 0.533 [0.483, 0.586], per-cell mean **0.502 [0.466, 0.545]** (4,631 pairs, 265 cells).
- um-ss-diets-09.L44.p37 (gold halal): "Since you specified **kosher** food" 0.5283 vs "Since you specified **Halal** options" 0.5277.
- um-ss-petownership-15.L52.p58 (gold dog): "…traveling with a dog…" 0.6243 vs "…considering your cat's…" 0.6244.

**Mostly there is no value choice for FVE to make.**
- Only 490 of 3,000 cells (16%) have both gold and wrong bullets in the pool. About 45% of cells have any gold at all.
- In 131 cells the top pool bullet names a wrong value. In 59% of those, the pool has no gold anywhere: the lens never said it.
- In cells with both, the top value bullet is gold in 68.6% of cells, against 65.1% expected from gold's share of value bullets.

**Selection barely helps.**
- Best of 32 contains gold **+0.4 points [−0.2, 1.0]** more often than a random one of the 32 samples.
- Combine 32 contains gold +2.2 [1.6, 2.8] more often than 4 random pool bullets. But its judge gain is in "verbatim echo" picks only (+1.2 [0.2, 2.3]); "inferred" picks change by −0.1 [−1.2, 0.9].

This is the "frame, not filler" result of Hallucination, Conjunctive association and the three olens-improve families. It shows one small difference: a 0.07-SD gold edge, where Conjunctive association had none.

## 2. Numbers

**A3. Gold vs wrong value within the cell's pool** (window labels; solo FVE)

| Variant | Pair rate | Per-cell mean | Cells / pairs |
|---|---|---|---|
| All (headline) | 0.534 [0.506, 0.568] | 0.520 [0.501, 0.548] | 490 / 160,820 |
| Full-text labels | 0.534 [0.506, 0.569] | 0.519 | 490 / 160,183 |
| Same list slot | 0.531 [0.502, 0.566] | 0.524 | 468 / 39,110 |
| Length-matched | 0.536 [0.505, 0.569] | 0.525 | 485 / 87,149 |
| Same frame (value masked) | 0.533 [0.483, 0.586] | 0.502 [0.466, 0.545] | 265 / 4,631 |
| Name level only | 0.533 [0.500, 0.570] | 0.513 | 433 / 137,454 |
| Without Antarctica | 0.523 [0.501, 0.556] | 0.524 | 467 / 139,842 |
| Wrong = judge distractor | 0.544 [0.507, 0.590] | 0.549 | 183 / 47,068 |
| Wrong = other value | 0.530 [0.496, 0.571] | 0.501 | 360 / 113,752 |
| No Chinese-led bullets | 0.540 [0.503, 0.583] | 0.536 | 414 / 85,502 |
| Plain opening (no Chinese, number or marker) | 0.540 [0.483, 0.592] | 0.526 | 316 / 55,989 |
| selfdescribe / synthsys | 0.527 [0.500, 0.587] / 0.541 [0.494, 0.585] | 0.523 / 0.516 | 293 / 197 |
| Leave one group out | 0.523–0.542 | | |

**Copied vs inferred gold** (pair rates against wrong values unless stated)

| Gold kind | Rate | Pairs |
|---|---|---|
| Copied (analyst rule) | 0.560 [0.514, 0.591] | 72,305 |
| Not copied (analyst rule) | 0.513 [0.491, 0.554] | 88,515 |
| … synthsys part (finer places, region words) | 0.472 [0.465, 0.490] | 18,040 |
| Copied (strict rule) | 0.542 [0.500, 0.582] | 90,345 |
| Inferred (strict rule; selfdescribe only) | 0.524 [0.497, 0.589] | 70,475 |
| **Copied vs inferred gold, same cell** | **0.495 [0.478, 0.510]**; strict 0.490 [0.479, 0.498] | 412,819 / 209,025 |

**The ladder** (pool; length-matched in brackets)

| Comparison | Rate | Length-matched |
|---|---|---|
| gold > frame-only | 0.518 [0.496, 0.537] | 0.514 [0.495, 0.533] |
| wrong value > frame-only | 0.497 [0.475, 0.520] | 0.495 |
| gold > none | 0.537 [0.528, 0.547] | 0.520 [0.510, 0.534] |
| wrong value > none | 0.515 [0.503, 0.523] | 0.502 |
| frame-only > none | 0.525 [0.515, 0.534] | 0.509 |

Length explains half or more of the ladder. A wrong value earns nothing over the frame.

**Regression within cell** (pool, solo FVE, 382,071 bullets).
- Controls: list slot, log length, Chinese lead, list-number opening, other opening marker, prompt-word overlap.

| Effect | Labels only | With controls |
|---|---|---|
| gold − wrong value | +0.0067 [0.0034, 0.0108] | +0.0050 [0.0017, 0.0092] |
| gold − frame-only | +0.0036 [0.0002, 0.0070] | +0.0021 [−0.0013, 0.0056] |
| wrong value − frame-only | −0.0031 [−0.0059, −0.0008] | −0.0028 [−0.0059, −0.0002] |
| inferred-name gold − wrong name | | +0.0028 [−0.0003, 0.0067] |
| copied-name gold − wrong name | | +0.0072 [0.0027, 0.0119] |

- The point estimates for names lean toward copied gold, but no direct comparison separates copied from inferred gold (see above).
- The controls themselves:
  - slot 1 vs 0: +0.009;
  - log tokens: +0.034 per e-fold;
  - Chinese lead: −0.0075 [−0.011, −0.004];
  - list-number opening ("2."): −0.0064 [−0.010, −0.003];
  - other opening marker (slash, bracket, bold, tag): +0.018;
  - prompt-word overlap: +0.040 per unit share.

**By layer** (L20 / 36 / 44 / 52 / 60): 0.529 / 0.529 / 0.530 / 0.520 / 0.558 [0.510, 0.616].
- Only L60 excludes 0.5, and there is no trend.
- Gold rate in the pool rises from 11.8% to 22.6%; judge gold per readout from 16% to 33%.

**By read site:**

| Site | Pair rate | Pool gold rate | Judge gold | Mean solo FVE |
|---|---|---|---|---|
| `<\|im_start\|>` | 0.573 [0.508, 0.636] | 47% | 59% | 0.22 |
| final `\n\n` | 0.554 [0.483, 0.605] | 16% | 30% | 0.40 |
| `\n` after `<\|im_end\|>` | 0.536 [0.491, 0.589] | 22% | 29% | 0.24 |
| request token | 0.515 [0.480, 0.576] | 7% | 14% | 0.16 |
| `\n` after `assistant` | 0.494 [0.436, 0.552] | 17% | 26% | 0.16 |
| final punctuation | 0.486 [0.457, 0.516] | 3% | 5% | 0.11 |

At name level with inferred gold only, every site is 0.48–0.59 and every interval includes 0.5.

**A2. Within one readout** (position-adjusted; Original / Best of 32 / Combine 32; pooled)

| Comparison | By setting | Pooled | Pairs |
|---|---|---|---|
| gold vs non-gold siblings | 0.542 / 0.499 / 0.527 | 0.523 [0.498, 0.547]; length-matched 0.516 [0.493, 0.542] | 4,939 |
| gold vs wrong value | 0.557 / 0.604 / 0.614 | 0.592 [0.503, 0.676]; length-matched 0.593 [0.470, 0.708] | 365 (188 readouts) |
| gold vs frame-only | 0.488 / 0.455 / 0.498 | 0.480 [0.440, 0.520] | 737 |
| gold vs none | 0.549 / 0.498 / 0.523 | 0.524 [0.497, 0.549] | 3,824 |
| inferred gold name vs non-gold | 0.539 / 0.458 / 0.496 | 0.497 [0.463, 0.534] | 1,921 |

- Readouts that hold both gold and a wrong value are rare (188), so the within-readout filler test is too small to read alone.
- Gold does not beat the frame inside a readout.

**A4. Selection** (full-text labels)

| | Original | Best of 32 | Combine 32 |
|---|---|---|---|
| Readout names gold | 28.2% | 28.1% | 29.7% |
| Random baseline | one of 32 samples: 27.6% | | 4 pool bullets: 27.5% |
| Selected − random | +0.6 [−0.2, 1.2] | +0.4 [−0.2, 1.0] | +2.2 [1.6, 2.8] |
| … gold by name | +0.2 | +0.3 [−0.2, 0.9] | +1.4 [0.7, 2.2] |
| … inferred gold (selfdescribe) | +0.3 | +0.0 [−0.4, 0.4] | +1.1 [0.4, 1.8] |
| … wrong value | −0.1 | −0.7 [−1.3, −0.1] | +0.5 [−0.4, 1.6] |
| No gold, though the pool has it | 36.8% | 37.1% | 33.5% |
| Judge picks gold, per readout | 26.6% | 27.1% | 27.7% |
| Judge vs Original: all gold picks | | +0.5 [−0.4, 1.3] | +1.0 [−0.03, 2.2] |
| … basis "inferred" | | +0.7 [−0.1, 1.6] | −0.1 [−1.2, 0.9] |
| … basis "verbatim echo" | | −0.2 [−1.1, 0.8] | +1.2 [0.2, 2.3] (synthsys +2.0 [0.6, 3.3]) |

Sample level, using joint FVE within the cell:
- gold-naming vs no-gold samples: 0.519 [0.507, 0.536];
- gold-only vs wrong-only samples: 0.497 [0.467, 0.525] (296 cells).

**A1 note.** Pooled across cells, mean solo FVE by label is gold 0.225, frame-only 0.226, none 0.213, wrong 0.197. Wrong bullets sit in weaker cells. Within cell the differences are a few thousandths (see the regression), so A1's raw means are mostly cell composition: layer, site and item.

**A5 (recomputed).** Judge gold vs "the readout has a gold label": κ = 0.864 (selfdescribe 0.81, synthsys 0.91). Of the judge's gold picks:
- selfdescribe: 756 "inferred", 322 "verbatim echo";
- synthsys: 306 "inferred", 1,058 "verbatim echo".

## 3. Are the labels right? (readers 0–2, 36 cases; lexicon reading sample)

**The strings are right; the slot is wrong in a minority.**
- The 150-bullet lexicon sample scored 30/30 each on gold-exact, gold-coarse and wrong-value. Its criterion was "names the value in the attribute's sense", not "names it for the user".
- **Focal labels, all three readers:** 30 of 36 right.
  - Gold: 21/24 (6/8, 7/7, 8/9 plus 1 borderline).
  - Wrong value: 9/12 (4/4, 3/5, 2/3).
- **Every bullet of 24 readouts (readers 0 and 2):**
  - 42 of 51 gold-labelled bullets name gold *for the user*. The rest name it for another entity, or rest on a lock-topic cue.
  - 13 of 16 wrong-labelled bullets name a wrong value for the user.
- **Recall (reader 0):** wrong 8/10, gold 21/22. Reader 2 found African cities (Harare, Addis Ababa, Kampala) and "life after loss" unlabelled.

**Failure modes:**
- **The value in another slot:**
  - the gift's destination: um-ss-continent-09.L20.p43 Original [2] "/FedEx and similar global couriers are indeed the best options for sending packages to Japan with high visibility." 0.4514;
  - the fruit's home: um-sd-country-11.L60.p51 s18.2 "Actinidia chinensis*) is one of New Zealand's most successful and globally recognized kiwifruit exports." 0.6563;
  - the question topic: um-ss-religiousaffiliation-00.L60.p41 s5.0 "When visiting a Buddhist temple across Southeast Asia, the guidelines for dress are generally consistent…" 0.6677, labelled wrong.
- **Wrong values compatible with gold:** um-ss-maritalstatus-13.L52.p49 Best of 32 [2] "Here is a gentle and practical budget template tailored for a single person… Please know that budgeting after lo[ss]" 0.6150. The user is widowed.
- **The answer's default locale:** um-ss-continent-01.L20.p35, where 123 of 127 pool bullets say the US, e.g. s3.2 "/childcare in the United States can range from free to very expensive." 0.4802. Across the pool, 4.3% of name-level wrong bullets (10.5% in Continent items) name the US or North America. Removing them leaves 0.533.
- **Cues counted as names:** 30% of locksmith name-level gold rests only on "lock picking" forms (reader 0).
- **Near-synonyms handled unevenly:** "sailor" counts as wrong for fisherman, but "seafarer" does not count.

**Attenuation.** Suppose about 19% of wrong labels are not real wrong values, and they behave like frame-only bullets (0.518). Then the observed 0.534 implies a true rate of about 0.538. Label noise does not hide a large effect, and it does not create the small one.

## 4. Confounds

**Position.**
- Gold sits slightly *earlier* than wrong values (mean slot 1.54 vs 1.65), which works against gold.
- Same-slot pairs give 0.531.
- In readouts, gold sits later than its siblings (0.58), so position adjustment lowers A2 (Original 0.557 → 0.542).

**Length.**
- Gold and wrong values have equal length (24.0 vs 24.2 tokens). Length-matched pairs give 0.536.
- Length drives most of the ladder (gold > none 0.537 → 0.520).

**Echo of the prompt.**
- Prompt-word overlap is a strong FVE driver (+0.040 per unit share), but gold and wrong values overlap about equally (0.156 vs 0.146).
- Copied and inferred gold do not differ inside a cell (section 2).
- The Antarctica group is copied gold vs a novel wrong value, and it is the single largest contributor.

**Chinese vs English.**
- 38% of gold bullets vs 26% of wrong bullets open with a Chinese token, which costs −0.0075 FVE. This works against gold.
- Without Chinese-led bullets the rate is 0.540 [0.503, 0.583].

**Opening format.**
- List-number openings cost −0.006 here, a much smaller effect than in Conjunctive association (−0.07). Gold carries more of them (12.4% vs 5.9%).
- The large swings are short header lines (section 5).

**Layer.** No trend in the filler test. Gold is named, and credited by the judge, twice as often at L60 as at L20.

**Read-site kind.**
- The chat-template sites are live:
  - `<|im_start|>` has the highest pool gold rate (47%) and judge gold rate (59%), and the only site-level filler rate that excludes 0.5 (0.573);
  - in selfdescribe, gold is almost absent at the final `\n\n` (3.9%) and the `\n` after `assistant` (4.8%).
- The final punctuation and the request token read mostly the request (gold 3–7%).

**Item clustering.**
- 31 groups of very uneven size:
  - Gender:male holds 12 items but only 0.8% of pairs;
  - Antarctica (3 items) holds 13% at 0.61;
  - fisherman 12% at 0.478; Ukraine 10% at 0.488; Europe 9% at 0.475.
- 20 of 31 groups lean to gold. The headline is pair-weighted toward a few big cells, so I give the per-cell mean (0.520) next to it.

## 5. Examples (verbatim; solo FVE; pct = within-cell percentile)

**Same frame, different value, near-equal FVE**
- **um-ss-employmentstatus-10.L52.p43 pool** (gold freelancer):
  - s22.3 "…for entertainment when you have a full-time job is tricky…" 0.6913;
  - s17.3 "…when you're a part-time worker isn't strictly defined…" 0.6794;
  - s15.0 "Determining what a "reasonable" amount for entertainment is tricky when you're a freelancer, as" 0.6751.
- **um-sd-occupation-00.L60.p53 pool** (gold fisherman):
  - s16.0 "Here is a Wikipedia-style infobox template filled with fictional data for a retired sailor named Arthur" 0.5893;
  - s0.0 "Here is a realistic Wikipedia-style infobox for a fictional retired fisherman. I" 0.5885.
- **um-sd-country-05.L60.p51 pool** (gold Ukraine):
  - s29.0 "Here is a realistic Wikipedia-style infobox for a fictional Russian music artist, created" 0.5741;
  - s22.1 "Here is a realistic Wikipedia-style infobox for a **fictional** Ukrainian folk dancer named Ivan Petrow." 0.5463.

**Same frame, gold clearly ahead (it happens too)**
- **um-ss-employmentstatus-01.L52.p39** (gold full-time):
  - s5.3 "Since you have a full-time job, there isn't one universal answer…" 0.6838;
  - s7.0 "Since you have a part-time job and a lot of tech…" 0.5287.
- **um-ss-maritalstatus-03.L52.p44** (gold divorced):
  - s28.3 "It's smart to be strategic about utility bills after a significant life change like divorce." 0.6318;
  - s29.3 "It's smart to renegotiate utility bills after a major life change. Since you're single, …" 0.3537.
- **um-ss-continent-07.L36.p33** (Antarctica group):
  - s8.0 "2: Since you are currently in Antarctica, your gardening activities would be quite different…" 0.3247;
  - s6.2 "极地 winter means your traditional garden experience doesn't apply. However, I can certainly offer some insights on managing insect populations in the Arctic region" 0.2640.

**Copied vs inferred gold, same frame, same FVE**
- **um-sd-country-02.L52.p52:**
  - s5.0 "2. Real K-pop Singer (Unreleased)" 0.3038 (copies the user's cue);
  - s26.0 "2: Real South Korean Singer (Fictional Profile)" 0.3166 (infers the country).
- **um-sd-country-01.L60.p53:**
  - s8.0 "orean cuisine, particularly kimchi, kimchi-inspired comfort food" 0.3269 (copied cue);
  - s12.0 "orean cuisine, particularly kimchi and jeon (Korean" 0.3067 (inferred name).
- **um-sd-country-05.L52.p44:**
  - s12.3 "舞者 of the Hopak and community leader…" 0.3594 (copied cue);
  - s9.1 "舞者 of the Hopak, an expert in traditional Ukrainian folk dance" 0.3296 (inferred name).

**Surface form outweighs content** (all labelled gold)
- **um-sd-occupation-01.L60.p47:**
  - Original [0] "2. **The Commercial Fisherman or Seafarer" 0.0013 (pct 0.008);
  - pool s8.3 "fisherman, a docker, or someone whose life is dictated by the tides…" 0.5305.
- **um-sd-country-05.L44.p45:**
  - Original [1] "2. **The Proud Ukrainian Cossack** 🇺🇦🎻 — A proud, traditional Ukrainian" 0.0076;
  - pool s12.2 "乌克兰 (Ukrainian) or broader Eastern European culture. A pysanka is…" 0.3590.
- **um-sd-gender-04.L44.p50:**
  - Original [3] "2. Professional Camper & Grill Master | A 40-Year-Old American Man…" 0.0053;
  - pool s15.1 "户外 enthusiast and traditionalist. Below is a biography of a typical 43-year-old male friend…" 0.2237.

**FVE level belongs to the cell, not the value**
- **um-sd-occupation-11, same token (final `\n\n`):**
  - L60.p55: 114 of 127 pool bullets name locksmith. Original [2] "Here is a realistic, fictional Wikipedia infobox for a locksmith named John Smith…" 0.5458; judge gold.
  - L44.p55: no gold in the pool. Original [0] "Here is a realistic-looking Wikipedia infobox for a fictional athlete named **John Doe**…" 0.4947 is the readout's top bullet; judge "cannot tell".
- **um-ss-continent-00:**
  - L52.p39 Best of 32 [3] "Since we are colleagues in East Africa…" 0.6384;
  - L60.p35 Combine 32 [3] "Considering your location in Nairobi and the warm Ugandan climate…" 0.1040.

**Selection adds copied gold**
- **um-ss-continent-01.L60.p42:**
  - Original names no place: [0] "Childcare costs vary wildly depending on where you are…" 0.5474; judge "cannot tell".
  - Combine 32 adds [3] "That's a fascinating question, but childcare costs in Africa vary wildly depending on the country…" 0.5561; judge gold, basis "verbatim echo".

## 6. Comparison with earlier results

| Study | Test | Result |
|---|---|---|
| Hallucination (chat) | clean beats WRONG, same readout | 0.511 / 0.504 / 0.503; length-matched 0.52–0.55 |
| | WRONG label effect | −0.003 FVE (−0.04 SD) |
| Multihop / Chained / Role-bound | hit vs siblings (adjusted) | 0.55 / 0.58 / 0.54 |
| | right vs wrong value, same content type | Chained 0.52 [0.45, 0.58]; Role-bound 0.52 [0.48, 0.57] |
| | Best of 32 vs random, judge pass | +0.2 / +1.4 / +0.2 pts |
| Conjunctive association | gold vs wrong value, pool | 0.490 [0.479, 0.528]; +0.0014 FVE (0.03 SD) |
| | Best of 32 vs random | +1.2 pts (lexicon gold); judge +0.24 |
| **User modelling (here)** | gold vs wrong value, pool | **0.534 [0.506, 0.568]**; per cell 0.520; +0.0050 FVE (0.07 SD) |
| | gold vs siblings, same readout (adjusted) | 0.523 [0.498, 0.547] |
| | Best of 32 vs random | +0.4 pts (gold); judge +0.5 |

- **Same pattern.** The template or frame carries the FVE ("Here is a realistic Wikipedia-style infobox for a fictional X", "Since you are X, …"), and X barely moves it.
- **Shared surface drivers:** length, later slot, opening form, prompt overlap.
- **Differences:**
  - The value edge here is the largest of the minimal-pair tests, yet still about a fifth of one e-fold of length.
  - Chinese-led bullets lose here, as in Hallucination; Conjunctive association showed no consistent language effect.

## 7. Corrections to the analysis write-up

1. **"The edge comes from copying the prompt, not from inferring the value"** is not supported. Copied and inferred gold do not differ inside a cell: 0.495 [0.478, 0.510]; regression +0.0022 [−0.0006, 0.0049]; under the strict rule +0.0004. Inferred gold in selfdescribe beats wrong values by as much as copied gold does (+0.0048 vs +0.0052).
   - Write instead: "a small gold edge of similar size for copied and inferred gold".
   - The analyst's "novel" group includes synthsys mentions that restate the stated value in other words.
2. **The weighting of the headline.** It is pair-weighted; 13% of its pairs come from 3 Antarctica items (0.61). Report the per-cell mean (0.520 [0.501, 0.548]) and the version without Antarctica (0.523 [0.501, 0.556]) next to it. Gold leads in only 51% of cells.
3. **The source of the gap in synthsys.** There, wrong values fall below frame-only bullets (−0.0068). Gold does not rise above them (+0.0009).
4. **"High-FVE wrong value" cases.** These are usually cells where the lens never named gold (59% of the 131 cells whose top bullet is a wrong value), not cases of FVE choosing wrong over right.
5. **A2 is small.** Gold vs wrong within a readout (0.592) rests on 188 readouts.
6. **The reading strata.** High and low are ranked within setting × layer, so the strata mostly pick cells and sites, not bullets within a cell (readers 0 and 2).

## 8. Caveats

- **Exploratory, with a refined lexicon.**
  - The lexicon was refined after reading: v1 failed the reading bar, and v2 added "Arctic/North Pole" as a wrong value for Antarctica.
  - Labels are string matches, and roughly 12–19% have the value in the wrong slot.
- **Echo is a proxy.** In synthsys, any gold mention may restate the stated value. The two echo rules bracket this.
- **Groups.** There are 31 related-item groups of very uneven size, and a few cells dominate the pooled pairs.
- **Pool metric.** Pool solo FVE has no joint context.
- **Judge and grid.** The grid is reduced, and the judge is Luna, not WSB's pinned judge.
- **Not recomputed by me:** the A5 reading verdicts, reader 0's infobox-template and list-opening statistics, and the analyst's own consensus test.
  - My consensus variant: the majority value beats the minority 0.515 overall; 0.532 when the majority is gold; 0.502 when it is a wrong value.
- **Untested causally.** A6, the filler swap (`analysis/a6_swap/`), would test whether FVE ignores the value with everything else fixed.

**Files** (all under `${OLENS_SCRATCH}/olens-bullet-fve/newtasks/analysis/um/skeptic/`):
- code: `sk_build.py`, `sk_run.py`, `sk_examples.py`, `sk_extra.py`;
- results: `sk_results.json`, `sk_extra.json`;
- logs: `logs/{build,run,examples,extra,focal_check,a5_check}.log` (the verbatim examples are in `logs/examples.log` and `logs/focal_check.log`);
- cache (rebuildable): `cache/sk_tables.pkl`.

Reader records: `analysis/um/read_records_{0,1,2}.json`. Analyst outputs: `analysis/um/results.json`, `analysis/um/read_sample.json`.
