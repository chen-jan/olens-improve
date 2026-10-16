# Per-bullet FVE does not tell you which Oracle Lens bullets are right

A combined report on six WorkspaceBench tasks, using Qwen3.6-27B and the frozen Oracle Lens. Everything here is exploratory. Written 2026-10-16.

## 1. Answer

**No, not in any usable way.** Per-bullet FVE does not tell you which O-lens bullets are right.

- **Same-readout tests.** In all six tasks, a bullet that carries the right answer beats a wrong or other bullet from the same readout only 50–58% of the time once list position is accounted for. Position is adjusted in Original and Best of 32 only. Combine 32 is compared raw, because its list order is the FVE pick order [reading/REPORT.md; tasks/REPORT.md; ca/REPORT.md; um/REPORT.md].
  - In Multihop, Chained, Role-bound and CA the interval excludes 0.5, so the lift is small but real.
  - The lift also goes to bullets of the same content type that carry a wrong value (next bullet).
- **Same-frame tests.** When the comparison holds the bullet's frame or content type fixed and only the value differs, the right value wins about half the time: 0.42–0.53 across Hallucination, Chained, Role-bound, CA and UM (same sources).
  - Only UM's pool rate excludes 0.5: 0.534 [0.506, 0.568]. With the frame held fixed, its per-cell mean is 0.502 [0.466, 0.545] [um/REPORT.md].
  - Multihop has no adequately powered test of this kind. Hit vs a bullet naming a bank distractor gives 0.66 [0.46, 0.77] on 128 pairs from 12 groups, which is too few to call [tasks/REPORT.md].
- **What FVE rewards.** FVE rewards the lens's own wording, the value word included: its template, length, list position, opening and echoes of the prompt. It barely rewards whether the specific value (the name, number, emotion word or user attribute) is correct [a6_swap/REPORT.md].
- **The filler-swap test makes this precise** [a6_swap/REPORT.md]:
  - The AR does encode the value word. In UM, swapping it moves the AR vector about 4 times as far as a synonym does (mean 1 − whitened cosine 0.126 vs 0.031). In CA the move is 0.060 vs 0.025.
  - Edits away from the lens's own wording usually cost solo FVE. That includes correcting a wrong value to the right one, which lowers solo FVE 60% (User modelling) and 68% (Conjunctive association) of the time.
- **Net preference for the right value is small**, once that edit cost is removed:
  - **User modelling: small but robust.**
    - Size-matched swap test: V = +0.0037 [0.0013, 0.0061] solo FVE, about 0.05 within-cell SD; about +0.007 when the token count is unchanged.
    - The pool regression gives +0.0050 [0.0017, 0.0092], or 0.07 SD [a6_swap/REPORT.md; um/REPORT.md].
  - **Conjunctive association: about zero.** V = +0.0011 [0.0003, 0.0025], and over items [−0.0006, 0.0033] [a6_swap/REPORT.md; ca/REPORT.md].
  - **Hallucination: no swap test was run.**
    - Observationally, a WRONG label moves solo FVE within a readout by −0.003 / −0.005 / −0.002, which is −0.04 / −0.06 / −0.03 within-readout SD.
    - The best case is wrong vs verified-true clean bullets in Combine 32: −0.0136 [−0.021, −0.007], about 0.25 SD [reading/REPORT.md].
- **Selection.** Picking the highest-FVE of 32 lens samples is barely more often correct than picking one at random.
  - The gain is +0.2 to +1.4 points in the five tasks scored in points. In Hallucination it is +0.2 of 72 pilot cells [−3.5, +4.6].
  - Every judge-based interval at k = 32 includes 0 [tasks/REPORT.md; errors/ERRORS.md; ca/REPORT.md; um/REPORT.md].
  - A few lexicon-based or pooled gains exclude 0 but stay small:
    - CA: Best of 32 names gold +1.2 points [0.1, 2.1] more often than a random sample.
    - Multihop, pooled over k = 2…32: +0.9 [+0.1, +1.7].
    - UM: Combine 32 names gold +2.2 [1.6, 2.8] more often than 4 random pool bullets. Its judge gain comes from verbatim-echo picks only.

## 2. Setup

1. **The lens.** The Oracle Lens (O-lens, checkpoint `olens_s3d_rl600`) reads one residual-stream activation of Qwen3.6-27B and writes text about it.
   - It reads at a *read site* (one token position) and one layer: 20, 36, 44, 52 or 60.
   - Its first 4 or fewer dash bullets, within a 256-token cap, form a *readout*.
   - A *cell* is one item × read site × layer, with key `item.L<layer>.p<pos>` [newtasks/DESIGN.md; reading/REPORT.md; inputs/DATAMAP_REPORT.txt].
2. **AR and FVE.**
   - The activation reconstructor (AR, `ar_ptag_pooled`) turns the first 32 tokens of each bullet into a vector [newtasks/DESIGN.md].
   - The activation and each bullet vector are whitened with a per-layer pooled whitener, and the bullet vectors are scaled to unit length.
   - A non-negative least-squares (NNLS) fit of the activation on the readout's bullet vectors gives the *joint FVE* = 1 − |residual|²/|target|². This is the share of the activation that the readout explains [inputs/DATAMAP_REPORT.txt; summary.json].
3. **Three settings per cell, built from 32 lens samples:**
   - *Original*: sample 0, capped to 4 bullets and 256 tokens.
   - *Best of 32*: the complete sample with the highest joint FVE.
   - *Combine 32*: bullets pooled from all 32 samples, added greedily by FVE gain, followed by one swap pass, with at most 4 bullets. Its candidate pool is de-duplicated by exact text [inputs/DATAMAP_REPORT.txt].
   - The *pool* used in the CA and UM pool tests is the first 4 bullets of all 32 samples, de-duplicated by AR vector [ca/REPORT.md; um/REPORT.md].
4. **Per-bullet scores:**
   - *Solo FVE*: the FVE of the bullet on its own.
   - *Shapley share*: the bullet's exact Shapley value divided by joint FVE, i.e. its fair share of what the readout explains.
   - *Drop*: the joint FVE lost when the bullet is removed. A bullet with NNLS coefficient 0 ("coef 0") is redundant because its siblings already cover it, so its drop is 0 [reading/REPORT.md; summary.json].
5. **Main statistic and terms:**
   - *Pair rate*: P(the right bullet scores higher than the other bullet), either within one readout or within one cell's pool. 0.5 means no separation, and ties count ½.
   - *Position-adjusted*: removes the list-slot effect. It applies to Original and Best of 32 only.
     - tasks, CA and UM subtract the mean score at the same slot, layer and readout size.
     - summary.json uses each score's mid-rank percentile among bullets at the same slot in readouts of the same size.
   - *Combine 32 stays raw.* Its list order is the greedy FVE order: its first bullet has the highest solo FVE in 84% of readouts, against 19% (Original) and 14% (Best of 32) [summary.json].
   - *Length-matched*: the two scored lengths are within 20% of each other. The Hallucination comparison against verified-true clean bullets uses 25%.
   - *Frame*: the bullet's template, e.g. "Here is a realistic Wikipedia-style infobox for a fictional X".
   - *Value* (or *filler*): the slot X that decides whether the bullet is correct.
6. **Six tasks, and what counts as correct in each:**
   - **Hallucination (chat)**: *clean*, meaning the bullet overlaps no span that the judge (GPT-6 Luna) verified as wrong or off-topic against the model's own reply. Clean means "no flagged span", not "verified true". About 20% of clean bullets are verified-true [summary.json; reading/REPORT.md].
   - **Multihop (multi-token)**: names a required bridge entity, matched with the judge's own regex.
   - **Chained intermediates**: carries the judge's top-ranked number, when that number is a hidden intermediate.
   - **Role-bound association**: states the right who-did-what-to-whom binding. The binding is located by rule RBA-v1, because the judge answers per readout [tasks/REPORT.md].
   - **Conjunctive association (CA)**: names the gold word on the one axis where gold and a contrast option differ (grief vs guilt). Labels come from a lexicon.
   - **User modelling (UM)**: names the user's attribute value (Ukrainian, fisherman). Labels come from a lexicon.

**How to read the numbers**
- **Source tags** are paths under `${OLENS_SCRATCH}/olens-bullet-fve/`. `ca/`, `um/` and `a6_swap/` are under `newtasks/analysis/`, and `summary.json` is `page/data/summary.json`.
- **Numeric brackets** are 95% bootstrap intervals.
  - They resample chats (Hallucination: 149; the fully judged pilot: 8) or groups of related items (Multihop 94, Chained 42, Role-bound 50, CA 10, UM 31).
  - With only 10 groups, the CA intervals are approximate.
- **SD** is not on one scale across sources:
  - Hallucination SDs are within-readout SDs of solo FVE [reading/REPORT.md].
  - CA's regression uses a within-cell SD of 0.055 [ca/REPORT.md].
  - The UM regression and the filler-swap test use the within-cell SD of pool solo FVE: UM 0.068, CA 0.064 [um/REPORT.md; a6_swap/REPORT.md].
- **Values written a / b / c** are Original / Best of 32 / Combine 32 unless a row says otherwise.
- **Case links.** Hallucination cases open at `https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#<key>`. The other tasks have no explorer, so they are given as case keys only.

## 3. Headline: the same answer in all six tasks

**Table 1.**

| Task (cells; groups) | A. Right beats other bullets, same readout, position-adjusted (Combine 32 raw) | B. A, length-matched (pooled) | C. Right vs wrong value, same content type or frame | D. Best of 32 minus random of 32, same cell | Source |
|---|---|---|---|---|---|
| Hallucination (5,615; 149 chats) | clean beats WRONG: 0.511 [0.496, 0.527] / 0.504 [0.489, 0.521] / 0.503 [0.486, 0.519] | 0.532 [0.518, 0.547]; vs verified-true clean bullets (length within 25%) 0.579 / 0.531 / 0.579 | wrong–clean pairs with the same first 3 tokens: clean wins 0.50 / 0.42 / 0.46. Effect of a WRONG label: −0.003 / −0.005 / −0.002 solo FVE (−0.04 / −0.06 / −0.03 SD) | top-FVE sample judge-clean in 24 of 72 fully judged pilot cells vs 23.8 for a random sample: +0.2 cells [−3.5, +4.6]. Full bank, Best of 32 vs Original: −1.6 pts hallucinated [−3.0, −0.3] | reading/REPORT.md; D: errors/ERRORS.md, reading/REPORT.md |
| Multihop (1,100; 94) | hit beats non-hit, pooled 0.549 [0.509, 0.589] | 0.554 [0.504, 0.600] | no powered value test: hit vs bank-distractor bullet 0.66 [0.46, 0.77] (128 pairs, 12 groups). Naming the final answer instead of the bridge earns the same lift as a hit: 0.584 / 0.583 / 0.595 | +0.2 pts [−1.5, +1.9] (judge pass); pooled over k = 2…32: +0.9 [+0.1, +1.7] | tasks/REPORT.md |
| Chained (1,320; 42) | 0.578 [0.534, 0.615] | 0.521 [0.463, 0.580] | right vs wrong carrier of the judge's top number, same cell (raw): 0.519 [0.453, 0.579]; length-matched 0.502 [0.419, 0.595] | +1.4 pts [−0.2, +3.1] | tasks/REPORT.md |
| Role-bound (11,400; 50) | 0.535 [0.514, 0.557] | 0.538 [0.507, 0.568] | hit vs a bullet from a failed readout of the same cell that names agent, action and patient (raw): 0.520 [0.477, 0.571]; length-matched 0.500 [0.449, 0.589] | +0.2 pts [−0.1, +0.5] | tasks/REPORT.md |
| Conjunctive (2,500; 10) | gold beats non-gold siblings 0.533 [0.513, 0.548] | 0.514 [0.496, 0.528] | gold vs wrong-value bullet in the cell's pool: 0.490 [0.479, 0.528] (67,618 pairs; per-cell mean 0.508 [0.479, 0.540]). FVE gap +0.0014 [−0.0021, 0.0044] (0.03 SD) | +1.2 pts [0.1, 2.1] (readout names gold, by lexicon). Judge gold vs Original: +0.24 [−0.48, 0.92] | ca/REPORT.md |
| User modelling (3,000; 31) | 0.523 [0.498, 0.547] | 0.516 [0.493, 0.542] | pool gold vs wrong value: 0.534 [0.506, 0.568] (160,820 pairs); per-cell mean 0.520 [0.501, 0.548]; same frame, per cell 0.502 [0.466, 0.545]. FVE gap +0.0050 [0.0017, 0.0092] (0.07 SD) | +0.4 pts [−0.2, 1.0] (names gold, by lexicon); Combine 32 vs 4 random pool bullets +2.2 [1.6, 2.8], but its judge gain is in verbatim-echo picks only. Judge gold vs Original: +0.5 [−0.4, 1.3] | um/REPORT.md |

**Notes on Table 1**
- **Column D.** "Random of 32" is a random one of the same cell's 32 samples. Original is itself sample 0.
  - D measures judge pass for Multihop, Chained and Role-bound.
  - It measures judge-clean for Hallucination.
  - It measures "the readout names gold", by lexicon, for CA and UM.
- **The other per-bullet scores agree.**
  - Hallucination: position-adjusted pair rates (percentile method; Combine 32 raw) are 0.512 / 0.509 / 0.515 for Shapley share and 0.501 / 0.498 / 0.517 for drop [summary.json].
  - The three families from tasks/REPORT.md: raw (not position-adjusted) pooled Shapley-share rates are 0.594 (Multihop), 0.594 (Chained) and 0.540 (Role-bound) [tasks/REPORT.md].
- **Larger FVE means at most slightly more correct readouts, and the gain is not tied to FVE.**
  - Mean joint FVE rises from 0.371 to 0.425 / 0.450 [reading/REPORT.md].
  - Best of 32 lowers the hallucinated-readout rate by 1.6 points [−3.0, −0.3] against Original, a change that is small but real. Combine 32 lowers it by 0.4 [−1.7, +1.1].
  - The Best of 32 gain does not grow with FVE gain: −0.019 / −0.014 / −0.017 by gain tertile [reading/REPORT.md].
  - In Multihop, Best of 32 beats Original by 2.1 points [0.8, 3.5], but FVE does not cause that gain. A random complete sample passes 127 of 1,100 cells, against 129 for Best of 32. Original passes less often than a random later sample (9.6% vs 11.2%) [tasks/REPORT.md].

**Why comparisons across readouts look better, and mislead**
- **Hallucination, across readouts.** Comparing any clean bullet with any wrong bullet gives a solo-FVE AUROC of 0.552 [0.532, 0.570] / 0.555 [0.535, 0.573] / 0.573 [0.553, 0.593]. Consistent readouts also have higher joint FVE than hallucinated ones: AUROC 0.586 [0.565, 0.607] / 0.582 [0.558, 0.604] / 0.594 [0.574, 0.615] [summary.json].
- **But those AUROCs mix cells.**
  - Taking clean bullets only from hallucinated readouts lowers the solo AUROC to 0.522 / 0.522 / 0.544 [summary.json].
  - In the 72-cell fully judged pilot, a clean sample outranks a hallucinated one of the same cell on joint FVE only 0.53 [0.49, 0.58] of the time [errors/ERRORS.md].
- **Multihop.**
  - Across items, FVE separates passing from failing readouts at an AUROC of about 0.69 / 0.70 / 0.66, but item confounds this comparison.
  - Within an item across layers, the rates are 0.55 / 0.58 / 0.51, and every CI includes 0.5.
  - Random samples from the same cell give 0.569 [0.518, 0.622]. This is the cleanest readout-level test, and its interval excludes 0.5. Multihop is the only family with a reliably positive readout-level effect, and that effect is tiny [tasks/REPORT.md].
- **Role-bound.** The apparent within-item 0.65 is a read-site effect. With site means removed it is 0.545 [0.46, 0.63] [tasks/REPORT.md].

**Examples (verbatim)**
- **Hallucination: same frame, wrong value, same score.** [chat-dailydialog-0044.L60.p136](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0044.L60.p136), Combine 32 [reading/REPORT.md].
  - `The Mid-Autumn Festival emphasizes family reunion and harmony — central themes in Chinese culture` files the reply's Spring Festival item under the wrong festival. Solo FVE 0.4386.
  - The clean `2. **Family Reunion / Togetherness** – The Chinese New Year is fundamentally about **reuniting with family**` scores 0.4391, a tie.
- **Hallucination: the frame carries the score.** [chat-lmsys-0038.L52.p364](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0038.L52.p364), Best of 32 [reading/REPORT.md].
  - `Original DataFrame:  Name  Age    Score\n0   Alice   25     85` gives Alice Bob's score, where the reply has 92. Solo FVE 0.617.
  - The clean header-only sibling `Original DataFrame:           Name  Age  Score` scores 0.593.
  - A bare `Original DataFrame:` scores 0.132.
- **UM, pool, `um-sd-occupation-00.L60.p53`** (gold: fisherman) [um/REPORT.md].
  - `Here is a Wikipedia-style infobox template filled with fictional data for a retired sailor named Arthur` scores 0.5893.
  - `Here is a realistic Wikipedia-style infobox for a fictional retired fisherman. I` scores 0.5885.
  - Sailor is a close neighbour that the lexicon counts as wrong. In the filler-swap test, fisherman → sailor raised solo FVE in one bullet (section 4).
- **CA, pool, `q02_c.L52.p89`** (gold: envy; contrast: pride) [ca/REPORT.md].
  - The contrast bullet `Anna silently celebrates her friend Mira's literary success two years after her own, suppressing her own pride out of respect.` scores 0.262.
  - It beats the gold bullet `Dina quietly supports Ben's literary achievement after hearing of his acceptance, while suppressing her own envy.` at 0.229.
- **Chained, `chain-w2-d3p-0659.L52.p68`** [tasks/REPORT.md].
  - The bullet `23** （5 + 4 + 10 + 4 = 23）` scores 0.2466 in both Best of 32 and Combine 32.
    - It is the hit in Best of 32 (share 0.85).
    - It is a miss in Combine 32, because there the judge ranked 47 first.
    - Its "23" also comes from a wrong derivation.
  - The wrong `21** （计算过程：11 + 10 + 13 + 13 = 47` scores 0.2471 in Combine 32.
- **Role-bound, `oa-accountant-client-deceive-ba.L60.p141`** (gold: the client deceived the accountant) [tasks/REPORT.md].
  - In Original, the clearest gold statement scores 0.039, the lowest in its readout. The rule labels it a miss. The bullet is `书商 Dale filed his annual income tax return with accountant Paul, deliberately understating his expenses by $500 to defraud him.`
  - Combine 32's top bullet, `A dishonest accountant, Dale, exploited Dana's trust to file a fraudulent tax return`, states the reverse direction and scores 0.401.

## 4. The filler-swap test: the AR sees the value, FVE barely prefers the right one

**Design** [a6_swap/REPORT.md].
- **Sources.** The sources are the lens's own bullets from the three selected settings that name the right value, with the value inside the AR's 32-token window: UM 2,705, CA 2,530.
- **Scoring.** Each edit changes one word. The edited bullet is AR-encoded and re-scored against a same-run re-encoding of the original. In total there are 25,096 AR vectors.
- **Labels.** No judge labels are used. Sources are chosen by the lexicon labels.
- **Edit types:**
  - **swap**: right value → wrong value (UM: a WSB judge distractor; CA: the contrast option);
  - **neighbour swap** (UM only): a close value, e.g. fisherman → sailor;
  - **synonym** of the right value;
  - **frame**: change a non-value word and keep the value;
  - **reverse**: start from a bullet that names a wrong value (UM 722, CA 340) and correct it to the right value.

**Table 2.** P(original wins) is P(the original's solo FVE > the edit's). For reverse rows it is instead P(the corrected bullet beats the wrong-value original). The AR move is the mean of 1 − whitened cosine [a6_swap/REPORT.md].

| Edit | UM P(original wins) | UM mean Δ solo | CA P(original wins) | CA mean Δ solo | AR move, UM / CA |
|---|---|---|---|---|---|
| Swap: right → wrong value | 0.864 [0.844, 0.885] | −0.053 [−0.061, −0.045] | 0.732 [0.693, 0.779] | −0.020 [−0.027, −0.014] | 0.126 / 0.060 |
| Neighbour swap | 0.808 [0.760, 0.844] | −0.028 [−0.034, −0.022] | – | – | 0.066 / – |
| Synonym | 0.626 [0.591, 0.664] | −0.007 [−0.009, −0.005] | 0.539 [0.449, 0.616] | −0.004 [−0.008, 0.000] | 0.031 / 0.025 |
| Frame word | 0.792 [0.771, 0.813] | −0.029 [−0.033, −0.025] | 0.680 [0.657, 0.706] | −0.012 [−0.015, −0.010] | 0.067 / 0.043 |
| Reverse: wrong → right (P = correction wins) | **0.398** [0.317, 0.472] | −0.014 [−0.027, −0.002] | **0.324** [0.263, 0.464] | −0.009 [−0.013, −0.002] | 0.047 / 0.033 |

**Table 3.** Size-matched comparisons: edits are compared within strata of AR move × original FVE.
- V is half the size-matched difference between correcting a wrong value and breaking a right one.
- V > 0 means FVE prefers the right value net of the cost of editing [a6_swap/REPORT.md].

| Comparison at the same AR move | UM | CA |
|---|---|---|
| Swap vs frame edit, Δ solo | −0.003 [−0.010, 0.003] | −0.002 [−0.004, −0.001]; over items [−0.004, 0.000] |
| Swap vs synonym, Δ solo | −0.028 [−0.038, −0.019] | −0.007 [−0.010, −0.005] |
| Frame vs synonym, Δ solo | −0.013 [−0.018, −0.009] | −0.005 [−0.008, −0.002] |
| **V, solo** | **+0.0037 [0.0013, 0.0061]** | **+0.0011 [0.0003, 0.0025]**; over items [−0.0006, 0.0033] |
| V, joint | +0.0010 [0.0006, 0.0015] | +0.0003 |
| V, edits that keep the token count | ≈ +0.007 | +0.0007 |
| Within-cell SD of pool solo FVE | 0.068 | 0.064 |

**What this shows** [a6_swap/REPORT.md]
- **The AR encodes the value word.** A UM swap moves the AR vector 0.126, against 0.031 for a synonym and 0.067 for a frame edit.
- **At equal movement, a value swap costs about the same as changing a frame word.**
  - In UM the difference is −0.003 [−0.010, 0.003].
  - In CA there is a small extra cost, −0.002 [−0.004, −0.001] over groups.
  - The extra cost over a synonym belongs to any change of meaning, not to the value specifically.
- **Correcting a wrong value usually lowers solo FVE**: in 60% of UM and 68% of CA reverse edits.
  - On joint FVE, the UM correction wins 0.498 [0.470, 0.525], a coin flip.
  - The CA correction wins 0.365 [0.327, 0.407].
- **What drives the UM preference.** The preference comes mainly from reverse edits that start from an "other" value: reverse − swap is +0.0091 [0.0063, 0.0131] (this difference is 2V). Reverse edits that start from a WSB distractor give +0.0035 [−0.005, 0.015], which is not significant.
- **Joint deltas are about 10× smaller than solo deltas**, because the sibling bullets absorb most of the change.
- **Early value words matter more.** UM P(original wins) for a swap is 0.93 when the value starts at tokens 0–3, against 0.80 at tokens 16–31.
- **FVE selection inflates the original's advantage, but the advantage is present without selection.** UM swap: 0.81 / 0.89 / 0.90.

**Examples (verbatim)**
- **UM, `um-sd-occupation-08.L44.p49`, Best of 32.** The original is "2: A seasoned deep-sea fisherman who believes patience yields rewards" (solo 0.0642). Changes in solo FVE:
  - → anthropologist: −0.0349;
  - → sailor: +0.0047;
  - → fisher: +0.0015;
  - "deep-desert fisherman": −0.0014.
- **CA reverse, `q03_g.L52.p72`, Original** (gold: layoff).
  - "Mark quietly prepares for his wife's biopsy while she is distracted by reading. To ease her anxiety," was corrected to "...his wife's layoff...".
  - Δ solo −0.0010, Δ joint −0.0047. Correcting to the right value did not raise FVE.

## 5. What FVE does track

**Table 4.**

| Driver | Evidence | Source |
|---|---|---|
| Length | Longer bullet wins 0.561 / 0.600 / 0.553 (Hallucination, same readout). Wrong bullets are longer than their clean sibling in 62.5% / 61.5% / 59.3% of pairs, which cancels a small penalty for being wrong. Solo FVE rises +0.034 per e-fold of tokens (UM) and +0.023 (CA). | reading/REPORT.md; um/REPORT.md; ca/REPORT.md |
| List position | In Original / Best of 32, the later bullet wins 0.546 / 0.577; this is not defined for Combine 32. Mean solo FVE from position 1 to 4 goes 0.251 → 0.269 (Original) and 0.273 → 0.310 (Best of 32); in Combine 32 it falls 0.392 → 0.323 by pick order. The wrong rate is 0.20 at the first bullet and 0.30 at the fourth (Original). Wrong bullets sit later than their clean sibling in 64.5% / 64.2% of pairs (Combine 32: 50.9%). In Chained (Original), FVE goes from 0.057 at position 1 to 0.118 at position 4. | reading/REPORT.md; summary.json; tasks/REPORT.md |
| Opening form | CA scaffold openings (list number, heading, `<think>`) cost −0.070 solo FVE, about 1.3 SD. In Hallucination, bullets without an unused list-number opener win 0.595 / 0.525 / 0.542. UM: list-number opener −0.0064, other opening marker +0.018. In Hallucination, clean openings overlap the reply's next text more than wrong ones (0.546 / 0.541 / 0.532). Errors in a bullet's first third cost −0.007 / −0.010 / −0.008 (0.10–0.14 within-readout SD); later errors cost nothing. | ca/REPORT.md; reading/REPORT.md; um/REPORT.md |
| Chinese text and openers | The lens often opens a bullet with one Chinese word that continues its carrier text; 46% of CA pool bullets contain Chinese characters. In Hallucination, an English bullet beats a mostly-Chinese one 0.596 / 0.614 / 0.637, but a single Chinese lead word does not hurt (bullets with no Chinese win only 0.471 / 0.434 / 0.478). UM: a Chinese lead costs −0.0075 and is more common on gold (38% vs 26%). CA: no consistent effect; the sign flips by layer. | ca/REPORT.md; reading/REPORT.md; um/REPORT.md |
| Redundancy | Coef-0 bullets make up 14.6% (Original) and 19.8% (Best of 32) of bullets, and none in Combine 32. Their drop is exactly 0. The rate is the same for wrong and clean bullets (14.3% vs 14.2%, Original). | summary.json; reading/REPORT.md |
| Echo of the prompt or context | UM: prompt-word overlap gives +0.040 per unit share. CA: reusing a capitalised story word, mostly the character's name, gives +0.021; summary-format echo ("in one sentence") +0.010; story content-word overlap −0.001. Hallucination: recapping earlier reply text carries no penalty (0.512 / 0.507 / 0.518). | um/REPORT.md; ca/REPORT.md; reading/REPORT.md |
| Where and how deep the read is | Mean joint FVE is 0.212 at L20 and 0.462 at L60 (Original, Hallucination). About 80% of CA's raw FVE-by-label ladder is layer, site and item composition. | summary.json; ca/REPORT.md |
| Everything above together | In Hallucination, length, script, overlap with the reply, list numbers and position explain only 4–7.5% of within-readout solo-FVE variance. Most of what moves FVE within a readout is unexplained. | reading/REPORT.md |

**Examples (verbatim)**
- **Opening form, CA `q04_a.L52.p73`, Best of 32. Both bullets are labelled gold** [ca/REPORT.md].
  - "1. **Concealing a Mistake:** On Monday, Ren secretly disposed of the incorrectly filed documents to hide the error," scores 0.0036.
  - "To evade the consequences of a printing error, Raissa secretly disposed of the damaged paper, concealed the evidence…" scores 0.410.
- **Broken start, Hallucination** [chat-lmsys-0058.L60.p139](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0058.L60.p139), Original. Every bullet in this readout is clean [reading/REPORT.md].
  - `ized Medicine:** Tailoring treatments to individual patients based on their unique genetic profiles, thanks to AI analysis of vast medical datasets.` scores 0.096.
  - `Personalized Medicine:** AI analyzes genetic data to predict disease risk and suggest tailored treatments.` scores 0.636.
- **Redundancy, Hallucination** [chat-dailydialog-0053.L36.p127](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0053.L36.p127), Best of 32 [reading/REPORT.md].
  - The clean `That feedback helps me improve and refine my responses. Or, ask me to` has coef 0 and a 13.6% share.
  - The WRONG near-duplicate `这 helps me refine my responses. Or, if I give you a wrong answer, point it out—I’m designed to learn from it` absorbs it: solo 0.505, 35.7% share.
- **Instruction echo, Role-bound `oa-police-thief-chase-ab.L36.p94`, Best of 32** [tasks/REPORT.md].
  - The plainest full binding, `**A police officer apprehended a wallet thief in a swift chase.**`, scores 0.041 (coef 0).
  - `警方 officer John captures a robber after a brief chase. (Or, if you prefer a single-sentence summary:` scores 0.200.

## 6. What the hallucinations are, and how avoidable they are (Hallucination only)

Unless marked, the source for this section is errors/ERRORS.md. It uses three samples:
- a representative sample of 240 wrong bullets, weighted to the population of 17,387;
- all 19,431 verified wrong spans;
- a 72-cell pilot in which all 32 samples of each cell were judged.

**What they are**
- **Most keep the gist.** Readers judged the bullet's main point right in 89% [84, 94].
- **About 63% have one wrong slot**: a name or entity, an attribute or relation, or a number.
- **Severity.**
  - 43% [36, 52] change the meaning.
  - 52% are minor.
  - About 21% [16, 27] are not real content errors. This group overlaps the minor one.
- **Copy failures, by the readers' coding.** In 45% [37, 53] of wrong bullets, the truth was in the prompt or in the reply before the read site. These hold 58 of the 90 meaning-changing errors. Part of this link comes from the coding itself: a contradiction with visible text is easier to rate as meaning-changing. Readers also saw pool counts while coding.

**Table 5.** Error types in the representative sample.

| Type | n | Share [95% CI] | Gist right | One-off / sticky (this sample) |
|---|---|---|---|---|
| Wrong or invented name/entity | 57 | 28% [21, 36] | 86% | 44% / 22% |
| Wrong attribute or relation | 55 | 23% [17, 30] | 91% | 41% / 29% |
| Plausible continuation the reply did not take | 35 | 13% [8, 19] | 96% | 50% / 22% |
| Wrong or invented number | 25 | 12% [6, 17] | 95% | 51% / 29% |
| Not wrong: judge too strict | 19 | 6% [4, 10] | 100% | 38% / 44% |
| First-person / persona claim | 18 | 6% [3, 9] | 78% | 37% / 9% |
| Over-specific elaboration of a true gist | 16 | 6% [3, 9] | 100% | 63% / 26% |
| Polarity or negation flip | 7 | 3% [1, 6] | 40% | 52% / 9% |
| Misread prompt; content from elsewhere in the chat; other | 8 | 3% | 7 of 8 | – |

**How avoidable they are**
- **Stickiness.** A span is a *one-off* if its key words appear in at most 2 of the cell's 32 samples, and *sticky* if they appear in at least 16.
  - Roughly a third to a half of wrong spans are one-offs, and roughly 15–30% are sticky.
  - The primary word-matching rule gives 47% one-off and 21% sticky. Spans keyed on a single novel name or number give 37% and 27%.
  - Sticky spans follow you: 67% also appear in the same setting's readout at another layer.
- **Truth never sampled.** For name and number errors, the true value is in none of the 32 samples in 32–55% of cases (lenient to strict matching).
  - This check covers 4,472 of 7,698 name/number spans and relies on the truth cited in the judge's own reasons.
  - It happens even though the truth is visible before the read site in 76–84% of these errors.
  - No choice among the samples can fix them.
- **A clean sample usually exists.**
  - 54 of 72 pilot cells have one (41 under a strict reading of the judge).
  - A perfect picker could clean 32 of the 46 Original-hallucinated pilot cells. That falls to 23 if at least 3 clean samples are required, and 19 under the strict reading. Best of 32 cleaned 8.
- **FVE does not detectably pick the clean sample.** The top-FVE sample is clean in 24 cells, against 23.8 for a random pick: +0.2 cells [−3.5, +4.6]. A large effect is ruled out; a small one is not.
- **The chat matters far more than the layer.** In the pilot, chat explains 47% of the cell-to-cell variance in the hallucinated share, and layer explains 1%.
- **Consensus separates grounded from ungrounded content, not true from invented.**
  - A true claim recurs across samples more than a wrong span with P = 0.70 [0.68, 0.71]. For names and numbers, P = 0.77 [0.74, 0.79].
  - A claim the judge could not verify recurs more than a wrong span with P = 0.55 [0.53, 0.56].
  - A majority vote keeps 47% of true claims and 25% of wrong spans. For names and numbers it keeps 73% and 30%.

**Examples (verbatim)**
- **The value is never sampled.** [chat-dailydialog-0045.L20.p65](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0045.L20.p65), Combine 32.
  - The bullet is `（or context of speaking to "Alice"), and no knowledge of any "rules" imposed by someone named "Pat."`.
  - The prompt is "Hey, Mary, can you cut that out?".
  - "Mary" is in 0 of 32 samples, "Sarah" in 32 of 32 and "Alice" in 2 of 32. A vote would drop Alice and keep Sarah.
- **Right category, wrong identity.** [chat-lmsys-0071.L36.p88](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0071.L36.p88), Best of 32.
  - The bullet is `Morning dew on tea leaves,`; the prompt asks for haikus about morning coffee.
  - "tea" is in 28 of 32 samples, "coffee" in 4 of 32.
- **Unavoidable.** [chat-lmsys-0025.L60.p80](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0025.L60.p80).
  - The bullet is `Ltd., stands as a premier entity nestled in the heart of Zhengzhou,`. The prompt and the reply both say Shanghai.
  - All 32 samples are hallucinated. "Shanghai" is in 0 of 32, "Zhengzhou" in 17 of 32.

## 7. Judge noise, and why it does not explain the null

**How noisy the bullet labels are**
- **Test–retest.** In 119 cells, Original and the raw lens output differ only in whitespace and were judged in separate calls.
  - The readout-level hallucination flag agrees in 86.6% [80.0, 92.4] of cells.
  - A WRONG verdict repeats 79% [67, 87] of the time [reading/REPORT.md].
- **Identical bullet text in two readouts of the same cell.**
  - The labels agree 78.2% [76.4, 79.9] of the time.
  - When one copy is WRONG, the other is WRONG 65% [62, 68] of the time [reading/REPORT.md].
  - Among pairs where one copy is WRONG, the labels differ in 52% [49, 55] of 2,019 pairs [errors/ERRORS.md].
- **Pilot spans.** An exact wrong span (8+ characters) that appears in another sample is flagged again in 67% of cases (2,914 of 4,332). In addition, 133 of 762 "clean" samples contain a span the judge flagged in another sample [errors/ERRORS.md].
- **Readers vs the judge.**
  - In the stratified reading, readers found no error in 63 of 192 judge-WRONG bullets. They found an error in 8 of 72 judge-clean bullets. That is 71 too-strict calls against 8 misses [reading/REPORT.md].
  - In the representative sample, about 21% [16, 27] of judge-WRONG bullets are not content errors [errors/ERRORS.md].

**Why noise does not explain the null**
- **Noise caps the effect but cannot hide a large one.**
  - A rough correction for judge noise puts the true same-readout pair rate at about 0.53–0.55 at most [reading/REPORT.md].
  - Against verified-true clean bullets, with length matched within 25%, the rate is 0.579 / 0.531 / 0.579 [reading/REPORT.md]. This is the best case. Judge noise and length together probably hide a small real effect, but it is still far too small to flag bullets.
- **Tasks with more precise labels show the same pattern.**
  - Multihop's rule labels were 94% right at string level (83% with the entity in the bridge slot), and Chained's 92–94%. Both give the same weak lift, and in Chained that lift does not favour the right value over a wrong one [tasks/REPORT.md].
  - In CA, hiding a true 0.55 would require the mislabelled 15% of the specific-word items to lose to gold about 88% of the time, which is implausible [ca/REPORT.md].
  - In UM, correcting for label noise moves 0.534 only to about 0.538 [um/REPORT.md].
- **The filler-swap test uses no judge labels**, only lexicon labels to choose its sources, and it gives the same answer [a6_swap/REPORT.md].
- **The readout-level tests show at most a small effect.** Readout flags are steadier (86.6%).
  - In the pilot, the top-FVE sample is clean no more often than a random one: +0.2 cells [−3.5, +4.6] [errors/ERRORS.md].
  - In the full bank, Best of 32 lowers the hallucinated rate by 1.6 points [−3.0, −0.3], and the effect does not grow with FVE gain [reading/REPORT.md].

**Examples (verbatim)**
- [chat-dailydialog-0010.L52.p24](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0010.L52.p24) [reading/REPORT.md].
  - `我没有 a physical body or a bank account, so I can't head out to a physical` has the same text and solo FVE (0.505) in two settings.
  - It is clean in Original and WRONG in Combine 32.
- [chat-dailydialog-0027.L52.p113](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0027.L52.p113), Best of 32 [reading/REPORT.md].
  - `祝你 have a wonderful time! Just let me know if you need help preparing for the event.` is flagged WRONG, although the reply ends "Have a wonderful time at the party!".
  - It is the top bullet (58% share), so this "high-share wrong bullet" is really a judge false positive.

## 8. Token heat: the wrong span is not cold

*Heat* is measured per token. The bullet's vector is built from its first k tokens instead of k−1, and heat is the resulting gain in joint FVE, with the other bullets' full vectors in the fit. A bullet's heat sums to its drop, up to a small recorded drift. The heat file was independently verified: recomputations match to within about 1e-7 [heat/verify/REPORT.md].

**Result.** The test uses the 14,004 wrong bullets whose wrong span covers some but not all of the scored tokens. It compares the share of the bullet's positive heat on wrong-span tokens with the share of tokens they take up. On a base of about 40% of tokens, the wrong span is cooler by only 1–2.5 points [heat/verify/REPORT.md]:

| Setting | Heat share minus token share |
|---|---|
| Original | −0.010 [−0.019, −0.001] |
| Best of 32 | −0.025 [−0.035, −0.015] |
| Combine 32 | −0.010 [−0.021, +0.001] |

**Why heat cannot locate the error** [heat/verify/REPORT.md]
- **The gap vanishes where it matters.** In the half of wrong bullets that carry real FVE (drop above the median, about 0.0086), the gap is about 0: −0.004 [−0.012, +0.004] over all settings. Heat cannot find the error inside a bullet.
- **Heat builds toward the end of a bullet.** The last token and final punctuation get 1.6–3.7 times their uniform share, and punctuation in general gets 1.12–1.27 times its share.
- **The largest single heats land on tokens that complete an entity name**, e.g. "Objects" in "BusinessObjects" (+0.318 FVE).

**Examples (verbatim)**
- **Median case.** [chat-dailydialog-0060.L20.p24](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0060.L20.p24), Original. The wrong span `I’m a bit of a gearhead.` has a token share of 0.36 and a heat share of 0.35.
- **Hottest case.** [chat-dailydialog-0061.L20.p21](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0061.L20.p21), Best of 32. The wrong span is `Mom`, one token of 17, and it holds 96% of the bullet's heat.
- **Coldest case.** [chat-dailydialog-0073.L36.p113](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0073.L36.p113), Original. The wrong span has heat share 0.00 against a token share of 0.83. All of the bullet's heat sits on a glued-on next list item.

## 9. Implications

- **What FVE is good for.** FVE measures how well the lens's text, as the AR reads it, accounts for the activation.
  - It tracks real things. In Hallucination, readouts whose bullets match the reply's actual next text score higher. An all-NEXT readout gets +0.074 [0.057, 0.089] FVE over one with no NEXT bullets, and Spearman(NEXT share, FVE) is 0.35 [0.31, 0.38]. NEXT comes from a lexical classifier with recall of about 0.44. The association is mostly between cells; within a readout the per-bullet premium is +0.006 [entropy/ENTROPY.md].
  - Form problems (scaffold openers, broken starts, redundancy) also show clearly.
  - Use FVE to compare lens versions and settings on coverage and form, not as a truth score.
- **What FVE is not good for:**
  - flagging wrong bullets (same-readout rate 0.50–0.51 in Hallucination);
  - ranking right over wrong values (0.42–0.53);
  - choosing the correct sample (Best of 32 vs random: +0.2 to +1.4 points);
  - locating the error inside a bullet (heat).

  The higher FVE of Best of 32 and Combine 32 (0.371 → 0.425 / 0.450) buys at most slightly more correct readouts, and the gain is not tied to FVE [reading/REPORT.md; tasks/REPORT.md; errors/ERRORS.md].
- **What a correctness signal would need.** It must respond to the value slot given the frame, and it must compare that value against a reference.
  - The AR vector already moves with the value. But FVE scores closeness to the lens's own wording, so a contrastive FVE test is dominated by the cost of editing. Net of that cost, the right-value preference is about +0.004 solo FVE in UM (about +0.007 with the token count unchanged) and about +0.001 in CA [a6_swap/REPORT.md].
  - The reference has to come from outside the fit: the context, agreement across samples, or a judge. By the readers' coding, in 45% of wrong bullets the truth was already visible in the prompt or the reply before the read site [errors/ERRORS.md].
- **Cheap next steps:**
  - **Consensus for names and numbers.** A vote keeps 73% of true names and numbers and 30% of wrong ones. Test whether disagreement on a slot value across the 32 samples flags errors better than FVE does.
  - **A retrieval-style check.** Match the names and numbers in a bullet against the prompt and the reply before the read site (Sarah vs Mary, Guangdong vs Sichuan). This is untested, and it only helps when the truth is in context.
  - **Cleaner labels first.** Before training or selecting on judge labels, re-judge with repeated votes and fix the continuation rule and the language-switch flags. By the readers' estimate, about 1 in 5 targets would change [errors/ERRORS.md].
- **Deeper next steps:**
  - **Train the lens with a correctness term.** The lens is RL-trained on this FVE [entropy/ENTROPY.md], and FVE rewards wording. For 32–55% of name/number errors, the truth is in none of the 32 samples, so only a better read can fix them, not better selection [errors/ERRORS.md].
  - **Probe whether the activation itself encodes the wrong value.** For example, train a probe for Mary vs Sarah at the chat-dailydialog-0045 read sites. This would separate lens errors from the model's own state. Start with the sticky errors, which recur at other layers 67% of the time.

## 10. Caveats

- **Exploratory throughout.** Every bank was inspected before analysis, and there is no fresh held-out test.
  - About 60 subgroup tests in the Hallucination synthesis have no correction for multiple tests.
  - The entropy file holds 3,347 estimates, and most of its secondary effects fail correction [reading/REPORT.md; entropy/ENTROPY.md].
- **One judge model, GPT-6 Luna.**
  - Its bullet verdicts repeat only 65–79% of the time.
  - For CA and UM it replaces WSB's pinned judge, so none of the CA or UM judge numbers are WSB numbers of record [newtasks/DESIGN.md; reading/REPORT.md].
- **"Clean" is not "verified true".** In Hallucination, clean means "no flagged span". Only about 20% of clean bullets are verified-true [summary.json; reading/REPORT.md].
- **Lexicon labels in CA and UM.**
  - CA wrong-value labels are about 50% precise overall (about 85% on the specific-word items), and the CA pool test rests on one lexicon family.
  - About 1 in 4 CA "gold" bullets has the right word with the wrong holder.
  - In UM, 12–19% of labels have the value in the wrong slot [ca/REPORT.md; um/REPORT.md].
- **Rule labels in Multihop, Chained and Role-bound.** Role-bound "non-hits" are contaminated: 43 of 75 (57%) of the non-hits read in passing readouts carry the binding [tasks/REPORT.md].
- **Small or uneven groups.**
  - CA has only 10 groups, and 79% of its pool pairs come from two of them.
  - In UM, 3 Antarctica items supply 13% of the pairs.
  - Chained positives come from only 30–33 groups [ca/REPORT.md; um/REPORT.md; tasks/REPORT.md].
- **Different conventions across sources.**
  - Position adjustment is mean-centring in tasks, CA and UM, and percentile-based in summary.json. Length matching uses scored tokens in tasks, CA and UM.
  - SD scales differ (see "How to read the numbers").
  - Pool solo FVE in CA and UM has no joint context [tasks/REPORT.md; ca/REPORT.md; um/REPORT.md; summary.json].
- **Shared pool.** The three settings share one 32-sample pool, so they are not independent [errors/ERRORS.md].
- **32-token window.** The AR sees only the first 32 tokens of each bullet. This rarely matters: under 0.2% of wrong bullets have all their wrong text past the limit [reading/REPORT.md].
- **Readers saw extra information.** They saw the FVE scores (reading) and the pool counts (errors) while coding [reading/REPORT.md; errors/ERRORS.md].
- **Limits of the filler swap.** Reverse edits start from different bullets than forward edits, matched only on AR move and original FVE. Some frame edits read oddly [a6_swap/REPORT.md].
- **Small pilot.** The fully judged pilot covers 8 chats, which hallucinate more than the bank average. Its intervals rest on 8 clusters [errors/ERRORS.md].
- **Entropy proxy.** Appendix A uses an L60 logit-lens proxy for entropy. It is overconfident and orders only the confident sites [entropy/ENTROPY.md].

## Appendix A. Side question: the text-buffer / entropy hypothesis

This is a side experiment on Hallucination (chat), not part of the main question [entropy/ENTROPY.md, with its skeptic re-check].

**Hypothesis and prediction.**
- The hypothesis: at easy positions (low next-token entropy), the activation has spare room for other computation such as planning.
- The AR can only express "the activation before some text", so extra non-text content would show up as lower FVE there.
- So FVE should be lower at low-entropy sites, with the gap growing at deeper layers.

**Findings.** No large, depth-growing deficit was found.
- **Effect of the entropy rank.** From the lowest- to the highest-entropy site, FVE changes by +0.010 [−0.011, 0.030] (Original).
- **Effect of a different confidence proxy.** With 1 − p(top-1) from the same lens, the change is +0.030 [0.008, 0.051].
  - It holds where the next token is a word: +0.030 [0.010, 0.050], with the NEXT control.
  - So a buffer-direction effect of up to about 0.03 FVE is compatible with the data. It is concentrated at the most confident ~7% of sites, and its sign depends on how lens confidence is summarised.
  - For scale, FVE rises about 0.25 from L20 to L60.
- **No growth with depth.** The linear entropy × layer trend is −0.006 per 16 layers [−0.019, 0.006].
- **A small dip at near-deterministic sites** (entropy below 0.1 nats, 85 of 1,123 sites): +0.033 [0.009, 0.059], read as "rest minus near-deterministic".
  - It comes mostly from about 10 block boundaries, such as a full stop before a paragraph break or the end of the reply.
  - Where the next token is a word, it is +0.008 [−0.020, 0.034].
- **Readouts are about 90% continuation-shaped at every entropy level.** Only 3 of 510 hand-labelled bullets are meta, generic or planning content.
- **Entropy does not predict hallucination**: +0.041 [−0.018, 0.102].
- **Surprisal does predict FVE.** The surprisal of the token the model actually wrote next gives +0.058 [0.034, 0.082].
  - About a quarter of that is tokenisation: +0.043 [0.007, 0.078] remains after controls.
  - It is absent at clause sites.
- **Sentence ends** score 0.045 below clause sites, and entropy does not explain that gap.
- **Limits.**
  - The L60 logit lens gets the exact next token right only 35% of the time, and the right word 50%. It is overconfident: mean entropy 1.90 nats against a mean surprisal of 4.03.
  - 1 − FVE is 43–80% at every entropy level, so a buffer of constant size would be invisible to this test.
  - Because the lens is RL-trained on FVE, its readouts lean toward continuation text whatever the activation holds.
- **Example.** [chat-lmsys-0015.L52.p364](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0015.L52.p364).
  - The site is a comma with entropy 0.012; the lens's top-1 is ' and' at 0.999.
  - Every bullet skips the certain ' and' and starts at the next value, e.g. "4 while others are labeled with age and height (ID 5,". FVE is 0.110.
  - These are invented continuations, not planning.

## Appendix B. Data, code, cost and where files live

**Data**
- **Hallucination (chat).** 149 chats, 5,615 cells, 3 settings: 16,845 readouts and 67,317 bullets.
  - It reuses the frozen olens-improve full-grid selections, AR vectors and judge verdicts (GPT-6 Luna, prompt v5c-chat plus a verifier).
  - The saved joint FVE reproduces exactly: 37.09% / 42.50% / 45.03% [inputs/DATAMAP_REPORT.txt].
  - 288 cases were read by hand in 7 strata [reading/REPORT.md]. A representative 240-bullet error sample was also read [errors/ERRORS.md].
- **Multihop, Chained and Role-bound.** These reuse the same frozen O-lens, AR, selections and judgments. Every number was recomputed by independent code [tasks/REPORT.md].
- **CA and UM** were a new run [newtasks/DESIGN.md; newtasks/P0_DECISION.md; ca/REPORT.md; um/REPORT.md]:
  - prompts rendered as WSB's producer renders them, 5 layers and N = 32;
  - CA: 100 vignettes × 5 sites;
  - UM: 100 chats × 6 sites; a pilot of 1,040 readouts kept all 6 planned UM sites;
  - judges: WSB comp-v1 and um-v2, run with GPT-6 Luna.
- **Filler swap.** 25,096 AR vectors [a6_swap/REPORT.md].

**Cost**

| Piece | GPU | Judge $ | Source |
|---|---|---|---|
| Hallucination metrics, reading, errors, entropy, re-check of the three olens-improve families | No new GPU. CPU only: per-bullet metrics estimated at 8–10 min on 4 threads; entropy analysis about 15 s; task recompute 1–10 s per family | No new spend reported (existing verdicts reused) | inputs/DATAMAP_REPORT.txt; entropy/ENTROPY.md; tasks/REPORT.md |
| Token heat | A separate GPU agent computed the heat file; its GPU time is not in the heat report. Verification ran on CPU (the whole-file check via srun on mit_quicktest). | none reported | heat/verify/REPORT.md |
| CA + UM capture and pilot | 0.066 H200-h (3 min 56 s on a borrowed H200) | $0.1224 | newtasks/P0_DECISION.md |
| CA + UM generation and AR encoding | Planned 8.6–9.1 H200-h (UM Tier B was later excluded), within an approved envelope of about 10 H200-h. The actual total is not in these sources. | Private ledger read $1.35 at the CA re-check and $2.40 at the UM re-check, both including the pilot; hard cap $30 | newtasks/DESIGN.md; ca/REPORT.md; um/REPORT.md |
| Filler swap (A6) | Analysis on CPU only (166 s plus steps under 10 s each). The A6 report does not cost the encoding of the edits; the design estimated about 0.05 H200-h for it. | $0 | a6_swap/REPORT.md; newtasks/DESIGN.md |

**Where files live**

All paths are under `${OLENS_SCRATCH}/olens-bullet-fve/`.
- **Hallucination study:**
  - `reading/`: REPORT.md, synth_tests.py/.json, the skeptic checks, reader records and `show_case.py`;
  - `page/data/summary.json`, plus the explorer https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3;
  - `errors/`: ERRORS.md, errors_synth.py, skeptic_checks.py/.json, and the 240 records in `records/`;
  - `heat/verify/`: v1–v5 scripts and JSON outputs;
  - `entropy/`: analysis.py, analysis_results.json and the `skeptic/` re-check;
  - `inputs/DATAMAP_REPORT.txt`: the data map.
- **Multihop, Chained and Role-bound:** `tasks/REPORT.md`, `tasks/skeptic/recompute.py`, `tasks/skeptic/<family>_results.json`, `tasks/skeptic/show_cells.py`.
- **CA and UM:**
  - `newtasks/DESIGN.md`, `P0_DECISION.md` and `RUNBOOK.md`, plus `code/`, `data/` and `budget/`;
  - `newtasks/analysis/{ca,um}/`: REPORT.md, the independent re-check in `skeptic/` (sk_results.json; verbatim examples in `logs/examples.log`) and the reader records;
  - `newtasks/analysis/a6_swap/`: REPORT.md, analysis.py (subcommands `compute`, `run`, `show`) and results.json.
- **Frozen upstream inputs (read-only):** the olens-improve selections and judgments under `${OLENS_DATA_ROOT}/`, and the activations, AR vector caches and whiteners under `${OLENS_COMPUTE_ROOT}/` [inputs/DATAMAP_REPORT.txt].
