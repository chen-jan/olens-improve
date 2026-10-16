# Do higher-FVE bullets and readouts carry the right answer? Multihop, Chained intermediates, Role-bound association

This is exploratory: every question in these banks was inspected before. No new judge or API calls were made and no GPU was used. The setup and settings are the same as in the Hallucination study (`reading/REPORT.md`): the same frozen O-lens, AR, whiteners, selections and judgments. All numbers below were **recomputed by independent code** (`tasks/skeptic/recompute.py`). That code reads the label files, the metric files, the raw judge files and the candidate selections. The analysts' `analysis.py` was not used. The interactive page from the Hallucination study does not cover these three families, so examples are given as case keys only.

**Terms** (each defined once)
- **Case key** `k = <item>.L<layer>.p<pos>`. **Readout** = the 4 or fewer bullets one setting writes for one read site. The settings are Original (`capped_n1-n1`), Best of 32 (`best_n_exact-n32`) and Combine 32 (`pooled_greedy_swap-n32`). Values are always in that order.
- **Hit bullet** = the bullet itself carries what the judge credited:
  - Multihop: a required bridge entity, matched with the judge's own regex on the bullet alone.
  - Chained: the judge's top-ranked number, when that number is a hidden intermediate.
  - Role-bound: the binding, located by rule RBA-v1, because the judge answers per readout and not per bullet.
- **Non-hit** = the other bullets of the same readout.
- **Pair rate** = the chance that a hit bullet has higher solo FVE than a non-hit bullet of the same readout. 0.5 means no separation. Ties count 1/2, and pairs are pooled.
- **Adjusted** means:
  - Original and Best of 32: solo FVE minus the mean solo FVE at the same list position, layer and readout size.
  - Combine 32: raw solo FVE. Its list order is the greedy FVE order, so adjusting for position would remove part of the effect being measured.
  This is the same convention as the Hallucination report.
- **Length-matched** = the two bullets' scored token counts (the 32 or fewer tokens the AR vector sees) are within 20% of each other.
- **Brackets** are 95% bootstrap intervals over related-question groups, with 1,000 reps. There are 94 groups for Multihop, 42 for Chained and 50 for Role-bound.

## 1. Bottom line

**Barely.** In all three families, bullets that carry the hidden answer score a little higher than their siblings in the same readout. The pooled, position-adjusted pair rate is 0.55 for Multihop, 0.58 for Chained and 0.54 for Role-bound. That is slightly more than the near-zero signal for Hallucination, but far from usable. Most of it is not about correctness:

- **Bullets with the right kind of content but the wrong value score just as well.**
  - Chained: a bullet carrying the judge's top number gets the same lift over its siblings whether that number is right or wrong. A correct carrier beats a wrong carrier from the same cell only 0.52 [0.45, 0.58] of the time.
  - Role-bound: hit bullets beat bullets that name agent, action and patient in readouts the judge failed only 0.52 [0.48, 0.57] of the time.
  - Multihop: naming the final answer instead of the bridge earns the same lift as naming the bridge (0.58 / 0.58 / 0.60).
- **Position and length explain part of the gap.** Hits sit later in the list and are longer, and both raise FVE. With position and length controlled, the pooled rates are 0.55 [0.50, 0.60], 0.52 [0.46, 0.58] and 0.54 [0.51, 0.57].
- **The top-share bullet is a hit only 2–13 points more often than chance.**
- **At readout level, picking the highest-FVE sample barely buys correctness.** Within the same cell, the best of 32 samples passes more often than a random one of 32 by only +0.2 points (Multihop), +1.4 (Chained) and +0.2 (Role-bound). Every interval includes 0.

FVE rewards the frame: explanation templates, story paraphrases, instruction echoes and the final answer. It does not reward the filler that decides correctness: which entity, which number, which direction. This is the same pattern as in Hallucination.

## 2. The numbers

**Bullet level: does a hit bullet beat its non-hit siblings?** (pair rate on solo FVE)

| Family | Test | Original | Best of 32 | Combine 32 | Pooled |
|---|---|---|---|---|---|
| Multihop (154 / 179 / 205 mixed readouts) | raw | 0.576 [0.522, 0.640] | 0.592 [0.524, 0.656] | 0.577 [0.519, 0.627] | 0.582 [0.544, 0.624] |
| | adjusted | 0.521 [0.461, 0.587] | 0.542 [0.472, 0.604] | 0.577 (raw) | 0.549 [0.509, 0.589] |
| | adjusted + length-matched | 0.523 [0.432, 0.623] | 0.539 [0.444, 0.627] | 0.578 [0.514, 0.640] | 0.554 [0.504, 0.600] |
| | top-share bullet is a hit, minus chance | +9.7 pts [2.9, 17.7] | +11.6 [2.3, 20.1] | +8.8 [2.4, 15.1] | |
| Chained (86 / 97 / 69) | raw | 0.594 [0.518, 0.669] | 0.589 [0.534, 0.645] | 0.564 [0.484, 0.647] | 0.584 [0.545, 0.625] |
| | adjusted | 0.561 [0.489, 0.640] | 0.601 [0.539, 0.665] | 0.564 (raw) | 0.578 [0.534, 0.615] |
| | adjusted + length-matched | 0.553 [0.438, 0.667] | 0.582 [0.479, 0.671] | 0.443 [0.352, 0.548] | 0.521 [0.463, 0.580] |
| | top-share bullet is a hit, minus chance | +8.5 [−2.0, 20.5] | +5.9 [−1.5, 13.6] | +13.2 [1.6, 25.5] | |
| Role-bound (380 / 432 / 437) | raw | 0.560 [0.531, 0.591] | 0.537 [0.490, 0.581] | 0.520 [0.485, 0.556] | 0.538 [0.514, 0.561] |
| | adjusted | 0.561 [0.531, 0.594] | 0.529 [0.487, 0.571] | 0.520 (raw) | 0.535 [0.514, 0.557] |
| | adjusted + length-matched | 0.583 [0.533, 0.635] | 0.534 [0.464, 0.606] | 0.517 [0.472, 0.557] | 0.538 [0.507, 0.568] |
| | top-share bullet is a hit, minus chance | +6.5 [2.3, 10.4] | +5.9 [1.2, 10.9] | +2.4 [−2.3, 7.1] | |
| *Hallucination (clean beats WRONG)* | adjusted / length-matched | 0.511 / 0.546 | 0.504 / 0.523 | 0.503 / 0.528 | 0.532 [0.518, 0.547] (length-matched) |

Shapley share gives the same picture. The raw pooled values are 0.594, 0.594 and 0.540.

**Same content type, right versus wrong value** (this is the test of whether the lift is about correctness)

| Family | Comparison | Result |
|---|---|---|
| Multihop | Bullet names the final answer but not the bridge, vs neither (adjusted) | 0.584 / 0.583 / 0.595: the same size as the hit effect |
| | Bridge named in a form the judge does not credit (e.g. bare "Akbar") vs a credited form | 0.66 [0.49, 0.83] / 0.59 [0.49, 0.77] / 0.38 [0.25, 0.54]: no consistent preference for the credited form |
| | Hit vs a bullet naming a bank distractor, same cell, any setting (raw) | 0.66 [0.46, 0.77] (128 pairs, 12 groups): too few to call |
| Chained | Carrier of the judge's top value vs misses, in readouts where that value is the intermediate / a wrong number / the final answer | 0.561 / 0.601 / 0.564, vs 0.561 / 0.553 / 0.612, vs 0.540 / 0.624 / 0.701 |
| | Correct carrier vs wrong carrier, same cell (raw; length-matched) | 0.519 [0.453, 0.579]; 0.502 [0.419, 0.595] |
| | Judge-free: leads with an intermediate vs leads with another number (adjusted) | 0.522 / 0.583 / 0.511; same cell across settings 0.541 [0.514, 0.570] |
| | Judge-free: leads with the final answer vs another number | 0.576 / 0.616 / 0.622: the final answer gains more than the intermediate |
| Role-bound | In failed readouts: names 2 or more of agent, action, patient vs none | 0.520 / 0.527 / 0.537 |
| | Hit vs a failed-readout bullet naming all three, same cell (raw; length-matched) | 0.520 [0.477, 0.571]; 0.500 [0.449, 0.589] |
| | Wrong-specific (reversed or distractor) vs sibling miss | 0.532 / 0.491 / 0.514 |

**Readout level: are higher-FVE readouts more often correct?**

| Test | Multihop | Chained | Role-bound |
|---|---|---|---|
| Same cell, judged random samples: pass beats fail on FVE (AUROC) | 0.569 [0.518, 0.622] (151 cells) | 0.523 [0.488, 0.557] (257) | 0.522 [0.502, 0.543] (829) |
| Pass rate of random samples in the top vs bottom half of the cell's 32 FVEs | 11.1% vs 10.6% | 6.6% vs 5.9% | 4.6% vs 4.4% |
| Best of 32 minus random of 32, paired per cell | +0.2 pts [−1.5, +1.9] | +1.4 [−0.2, +3.1] | +0.2 [−0.1, +0.5] |
| Same, pooled over k = 2…32 | +0.9 [+0.1, +1.7] | +0.9 [−0.0, +1.8] | +0.1 [−0.1, +0.3] |
| Cell pass: Original → Best of 32 → Combine 32 | 106 → 129 → 146 of 1,100 | 93 → 100 → 80 of 1,320 | 490 → 512 → 539 of 11,400 |
| Change vs Original (Best / Combine) | +2.1 [0.8, 3.5] / +3.6 [1.5, 5.8] | +0.5 [−1.2, 2.2] / −1.0 [−2.8, 1.1] | +0.2 [−0.2, 0.6] / +0.4 [0.1, 0.7] |
| Across items, same layer (confounded by item) | 0.69 / 0.70 / 0.66 | 0.47 / 0.39 / 0.39 | 0.56 / 0.56 / 0.56 (same layer and site) |
| Same item across layers or sites, layer- or site-demeaned | 0.55 / 0.58 / 0.51, all CIs include 0.5 | 0.45 / 0.44 / 0.40, all CIs include 0.5 | 0.545 / 0.547 / 0.544, all CIs include 0.5 |

For comparison, in Hallucination Best of 32 and Combine 32 changed the hallucinated-readout rate by −1.6 and −0.4 points.

The same-cell random-sample test is the cleanest readout-level test, because item, layer and site are held fixed and the samples were not picked by FVE. A sample's verdict was identical in every condition that judged it (0 conflicts), and every condition's FVE equals the 32-sample trace score (0 mismatches).

## 3. Per family

### 3.1 Multihop (multi-token): weakly yes, but FVE rewards naming an answer-relevant entity, not the hidden bridge

- **The raw separation is about 0.58, and it shrinks to about 0.52–0.54 with position adjusted in Original and Best of 32.**
  - Hits sit later in the list: they are later in 60% / 62% of pairs.
  - Later positions score higher: mean solo FVE rises from 0.19 to 0.22 (Original) and from 0.21 to 0.27 (Best of 32) between position 1 and 4.
  - Hits are also longer: they have more scored tokens in 65% / 62% / 55% of pairs.
- **Combine 32 keeps 0.58 after length matching.** That is the strongest single result in this study, but it is still weak.
- **The lift is not specific to the bridge.**
  - Naming the final answer, which is the model's next prediction and not the hidden step, earns the same lift.
  - Naming the bridge in any form, credited or not, gives 0.56 / 0.57 / 0.57.
  - Hits still beat non-hits when neither names the final answer (0.58 / 0.58 / 0.58, with lower bounds near 0.49–0.50).
- **Readout level:**
  - Across items, FVE separates passing from failing readouts (AUROC about 0.7), but that comparison is confounded by item.
  - Within the same item and layer across samples it is 0.57.
  - Choosing by FVE adds +0.2 points at k = 32 and +0.9 [+0.1, +1.7] pooled over k. This is the only family with a reliably positive readout-level effect, and it is tiny.
  - Best of 32's +2.1-point gain over Original is not driven by FVE. A random complete sample of 32 passes 127 of 1,100 cells, against 129 for Best of 32. The first sample (Original) passes less often than a random later sample (9.6% vs 11.2%).
- **Label validity.**
  - The judge's own regex reproduces every per-unit verdict from the bullets (1,452 of 1,452 required units per setting).
  - The reader found 34/36 labels right at string level (94%), and 30/36 (83%) with the entity in the bridge's slot.
  - The weak spots:
    - Six of the 36 sampled readouts differ only in how the name is written, for example "the Nerchinsk Treaty" (not credited) vs "The Treaty of Nerchinsk".
    - One miss is a judge false negative: "N.C. Wyeth".
    - Only 2 of 6 wrong-specific bullets put the distractor in the bridge slot.

Examples:
- `mhh-streptomycin-griseus.L60.p36` (Original; the bridge is streptomycin, the final answer is *Streptomyces griseus*).
  - The only hit, `种类 *Streptomyces*, a soil bacterium. Here’s the corrected version: **Streptomycin is produced by the bacterium *Stre`, has the lowest solo FVE (0.240).
  - The top bullet, `Mycobacterium tuberculosis? No — it’s *Streptomyces griseus*, a soil bacterium` (0.514), names only the final answer.
  - In Combine 32 the top bullet is the wrong organism, `Mycobacterium parvum, but more accurately, the antibiotic comes from the bacterium *Streptomy` (0.604).
- `mhh-fourrow-layout.L60.p26`.
  - Original passes at joint FVE 0.402 because of a hit with solo FVE 0.003: `谁？ | **Elisha Remington** and **Christopher Sholes**`.
  - Best of 32 (0.642) and Combine 32 (0.663) score much higher and fail. Their top bullet, `Remington & Rand, who bought the patent rights. Here's how the QWERTY`, scores 0.627.

### 3.2 Chained intermediates: no, once length is matched; FVE rewards the explanation template and the final answer

- **The raw separation is about 0.59 and survives position adjustment** (0.56 / 0.60 / 0.56).
- **It disappears when length is matched on raw scores** (pooled 0.494 [0.422, 0.565]). With position also adjusted it is 0.521 [0.463, 0.580].
- Part of the raw gap is bare numbers such as `- 18`. Their solo FVE is about 0, and they make up 16–19% of non-hits but only 8–9% of hits in Original and Best of 32. Dropping them leaves 0.56 / 0.58 / 0.56.
- **The decisive check: carrying a wrong number gives the same lift as carrying the intermediate.**
  - A correct carrier beats a wrong carrier from the same cell 0.52 [0.45, 0.58] of the time.
  - Judged without the judge, leading with the intermediate beats leading with another number only 0.51–0.58. Leading with the final answer does better (0.58–0.62).
- **Readout level: no effect.**
  - Same-cell random samples give 0.523 [0.488, 0.557], and Best of 32 minus random of 32 is +1.4 [−0.2, +3.1] points.
  - Across items, higher-FVE readouts are *less* often hits (0.39–0.47). Hits concentrate at L52–56, the lowest-FVE layers.
- **Label validity.**
  - Labels agree with the judge file in 1,320/1,320 readouts per setting, and the reader found 33–34 of 36 right (92–94%).
  - Only 10 of 24 hit bullets show the chain's operation; 14 just state the number, and 6 of those are 7 or smaller, so could be coincidence.
  - Under the judge's top-1 rule, the label depends on context: 38 of 461 distinct hit vectors are a hit in one setting's readout and a miss in another's.

Examples:
- `chain-w2-d3p-0659.L52.p68` (start 14, add 9, 8, 8; intermediates 23 and 31).
  - The bullet `23** （5 + 4 + 10 + 4 = 23）` has solo FVE 0.2466 in both Best of 32 and Combine 32. In Best of 32 it is the hit (share 0.85). In Combine 32 it is a miss, because the judge ranked 47 first.
  - In Combine 32 the wrong `21** （计算过程：11 + 10 + 13 + 13 = 47` scores 0.2471.
  - The "23" also comes from a wrong derivation.
- `chain-d2p-0231.L40.p68` (Best of 32; start 4, halve twice; intermediate 2, answer 1).
  - The answer-leading `1 (Explanation: 3 divided by 2 is 1.5, halved three times results in` (0.290) and `1** (Explanation: 3 divided by 2 is 1, then 1 divided by 2 twice results in 1.)` (0.249) beat the hit `2** (Explanation: The number is halved three times: 16 -> 8 -> 4 -> 2.)` (0.089, coef 0).
  - The bare hit `2` scores 0.003.

### 3.3 Role-bound association: at most a weak yes in Original; the rule label dilutes it, but content without correctness scores the same

- **Separation:** 0.56 [0.53, 0.59] in Original (0.58 length-matched). Best of 32 (0.53) and Combine 32 (0.52) have CIs that include 0.5. There is little position or length confounding.
- **The lift is about naming the participants, not about getting the binding right.**
  - In failed readouts, bullets naming 2 or more parts beat bullets naming none 0.52–0.54 of the time.
  - Hits do not beat full-content bullets from failed readouts of the same cell: 0.520, or 0.500 length-matched.
- **Readout level: no effect.**
  - Same-cell random samples give 0.522 [0.502, 0.543], and Best of 32 minus random of 32 is +0.2 points.
  - Across items within layer and site there is a small 0.56.
- **Label validity: this is the weakest of the three, because the judge gives no bullet attribution.**
  - Rule hits are mostly right: the reader found 21/24 carry the binding at least partly (9 fully, 12 weakly) and 3 ambiguous. In 30 fully-read passing readouts, 40/45 rule hits carry it.
  - But the comparison group is contaminated: 43 of 75 (57%) of the "non-hits" in passing readouts also carry the binding.
  - With clean labels the pair rate might rise to about 0.6 at most. This is a rough correction from a share-stratified sample.
  - The judge is also strict on names. 303 / 292 / 289 bullets that name agent, action and patient sit in readouts the judge failed, about as many as the strict hits in passing readouts (331 / 363 / 343). The MAP reading found that 5 of 9 of these state the gold binding.

Examples:
- `oa-police-thief-chase-ab.L36.p94`. All three readouts state the gold binding, but the judge passes only Best of 32.
  - In Best of 32, the plainest full binding, `**A police officer apprehended a wallet thief in a swift chase.**`, gets solo FVE 0.041 (coef 0).
  - The bullets with instruction-echo tails get far more: `警方 officer John captures a robber after a brief chase. (Or, if you prefer a single-sentence summary:` (0.200) and `一名警察在短暂追逃后成功抓获入室盗窃犯。** (This is the most concise and direct summary of the events.)` (0.177).
  - In Original (judged partial) and Combine 32 (judged none), the top bullet is `一名 police officer successfully apprehending a bank robber after a brief chase. (This is a concise, factual summary of the story.)` (0.221).
- `oa-accountant-client-deceive-ba.L60.p141` (gold: the client deceived the accountant).
  - Original passes at joint FVE 0.375. Its clearest gold statement, `书商 Dale filed his annual income tax return with accountant Paul, deliberately understating his expenses by $500 to defraud him.`, scores lowest (0.039, labelled miss).
  - The higher-FVE readouts fail. Best of 32 (0.431) is judged none and Combine 32 (0.489) is judged partial. Combine 32's top bullet, `A dishonest accountant, Dale, exploited Dana's trust to file a fraudulent tax return`, scores 0.401 and states the reverse direction.

## 4. Comparison with Hallucination

| | Hallucination | Multihop | Chained | Role-bound |
|---|---|---|---|---|
| Correct beats incorrect in the same readout (adjusted) | 0.50–0.51 | 0.52 / 0.54 / 0.58 | 0.56 / 0.60 / 0.56 | 0.56 / 0.53 / 0.52 |
| Length-matched, pooled | 0.532 [0.518, 0.547] | 0.554 [0.504, 0.600] | 0.521 [0.463, 0.580] | 0.538 [0.507, 0.568] |
| Wrong content with the right frame scores the same | yes (same first 3 tokens: clean wins 0.42–0.50) | yes (final answer, uncredited forms) | yes (wrong carrier 0.52) | yes (failed full content 0.52) |
| Best of 32 changes correctness | −1.6 pts hallucinated | +0.2 vs random of 32 | +1.4 vs random of 32 | +0.2 vs random of 32 |

The forward direction ("is low FVE a sign of an error?") and the reverse direction ("is high FVE a sign of the right answer?") give the same answer. FVE is close to blind to whether the filler is right. Explicit answer-shaped content shows a small, consistent lift of about 0.53–0.58, larger than in Hallucination. That lift goes to any answer-like slot: the final answer, a wrong number in an explanation template, or participants named in a failed readout. It does not go specifically to the correct one.

## 5. Confounds checked

- **Position.** In Original and Best of 32, later bullets score higher in every family (Chained Original: 0.057 at position 1 to 0.118 at position 4). Multihop hits sit later, so adjustment matters there.
- **Combine 32 order.** Combine 32's list order is the greedy FVE order: position 1 has the highest mean solo FVE in every family (0.33 vs 0.27, 0.23 vs 0.16, 0.21 vs 0.16). In Multihop, a Combine hit placed earlier wins 0.82 of pairs and one placed later wins 0.31. So Combine is reported raw. Hits are only slightly over-represented at position 1: 28%, 29% and 27%, against 25% by chance.
- **Length.** Hits are longer in Multihop (0.55–0.65) and in Chained Original (0.59). Matching length removes the Chained effect.
- **Readout-level pass differences.** All bullet tests compare bullets within one readout, so readout pass and FVE are held fixed. They can only use mixed readouts: 154–205 (Multihop), 69–97 (Chained) and 380–437 (Role-bound). Those come from 49–60, 30–33 and 46–50 groups, so a few items dominate.
- **Judge format.**
  - Multihop: the credited-form requirement.
  - Chained: the top-1 rule, which makes labels depend on context.
  - Role-bound: name strictness.
  The noise these add mostly pulls estimates toward 0.5. The Chained quote anchor can also push hits up: the judge quotes the explanation-template bullet, and templates score high whatever the number, so carriers of wrong numbers get the same lift.
- **Item and site.** Across-item readout comparisons are confounded. For example, the analysts' Role-bound within-item AUROC of 0.65 across read sites comes from the read site, not from correctness:
  - The `␠one`/`␠sentence` sites have the highest mean FVE (0.33–0.36) and 0 passes.
  - The `<think>`/`</think>` sites have FVE of 0.01–0.04 and at most 1 pass.
  With site means removed it is 0.545 [0.46, 0.63].

## 6. Agreement with the analysts' numbers

- **The raw bullet-level headline numbers reproduce exactly** (same pairs and same estimates):
  - Multihop 0.576 / 0.592 / 0.577
  - Chained 0.594 / 0.589 / 0.564
  - Role-bound 0.560 / 0.537 / 0.520
- **So do the readout-level counts and FVE means.** These are the EXPANDED_REPORT pass counts and the saved means 30.2/35.2/37.4%, 17.1/23.8/25.8% and 19.4/23.1/25.0%.
- **Labels match the raw judge files** in 100% of readouts.
- **Changes in reading:**
  1. The Role-bound 0.65 is a read-site effect (section 5).
  2. Multihop's "the passing setting has higher FVE 67% of the time" mostly reflects the first sample being below average. Best of k vs random of k is the cleaner test.
  3. Multihop Original's 0.58 is 0.52 once position is adjusted. The analysts' percentile adjustment gives 0.54. It is the same conclusion.

## 7. Caveats

- Exploratory: every question was inspected before.
- Positives are rare, especially in Chained (227–321 pairs from 30–33 groups), so intervals are wide.
- **Labels are rules, not human judgments.**
  - Reader precision is 83–94% (Multihop), 92–94% (Chained) and about 88% for Role-bound hits.
  - Recall is worse: Multihop uncredited forms, Chained intermediates that the top-1 rule does not credit, and Role-bound carriers among non-hits.
  - Each reading was done by one reader.
- The AR vector sees only the first 32 tokens of each bullet. Hits outside that window are rare (Multihop 2 / 5 / 8 bullets).
- Pair rates are pooled over pairs, so readouts with more pairs weigh more.
- **Differences from the analysts' choices:**
  - My position adjustment subtracts a mean; the analysts' used percentiles.
  - My length matching uses scored tokens; the analysts' used characters.
  - Results agree within about 0.03.
- Rerunning the bootstrap moves CI ends by about ±0.01.
- The readout-level same-cell test uses only samples that some condition happened to select and judge. These are random picks, about 4–7 per cell.

## 8. Files

- `tasks/skeptic/recompute.py`: the independent recomputation (about 1–10 s per family on CPU).
- `tasks/skeptic/<family>_results.json`: every number above, with CIs.
- `tasks/skeptic/show_cells.py`: prints every bullet of a cell with its label, solo FVE, share and coefficient. All the examples above were checked with it.
- `tasks/skeptic/label_checks.py` and `tasks/skeptic/label_checks.json`: the counts behind the Chained top-1 context dependence and the Role-bound full-content-in-failed-readout figures.
- Per-family inputs: `tasks/<family>/MAP.md`, `bullet_metrics.jsonl`, `bullet_labels.jsonl`, `analysis.json` and `read_records.json`.

