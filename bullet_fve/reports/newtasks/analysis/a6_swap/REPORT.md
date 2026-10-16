# A6 filler swap: does FVE ignore the value word?

**Short answer: it does not ignore the value word, but it barely cares whether the value is right.**

- Swapping the right value for a wrong one lowers FVE most of the time:
  - UM: in **86%** of bullets;
  - CA: in **73%**.
- That drop mostly comes from editing the lens's own text at all:
  - A value swap moves the AR vector a long way (4× a synonym edit, 2× a frame-word edit).
  - At the same AR movement, a value swap costs the same FVE as changing a frame word.
  - Correcting a wrong value to the right one **also lowers FVE** (UM 60% of the time, CA 68%).
- Net of the edit cost, the preference for the right value is:
  - UM: small, **+0.004 solo FVE** (about 0.05 within-cell SD);
  - CA: about zero, **+0.001**.

The old claim "FVE rewards frame/form, not filler" needs rewording: **FVE rewards the lens's own wording, the value word included, not the correctness of the value.**

## Setup
- **Sources:** right-value bullets from the three selected settings, with the value word inside the AR's 32-token window.
  - UM: 2,705 right and 722 wrong-value sources (95 items, 31 groups).
  - CA: 2,530 right and 340 wrong-value sources (90 items, 10 groups).
- **Vectors:** 25,096 AR vectors. Every delta is the variant minus the **same-run re-encoded original**.
- **Solo FVE:** the share of the activation one bullet explains alone.
- **Joint FVE:** an exact NNLS refit of the readout (as in JointNNLS) with the other bullets' cached vectors fixed. One value per readout the bullet appears in, then averaged.
- **Brackets:** 95% bootstrap over related-item groups (2,000 reps; UM 31 groups, CA 10). "Items" marks the item-level interval. CA has only 10 groups, so its intervals are approximate.
- **Scale:** the within-cell SD of pool solo FVE is UM 0.068 and CA 0.064.

**Checks**
- Solo and joint FVE of the cached originals reproduce the saved pipeline values exactly (maximum |diff| 0.0 over 6,297 bullets and 6,966 readouts).
- NNLS solo FVE equals the closed form to 1e-15.
- Re-encoding noise is negligible:
  - 94% (UM) and 93% (CA) of originals give bit-identical solo FVE;
  - mean |ΔFVE| is 4e-5 and p99 is 0.0012.
- 9 unscored readouts were skipped; no readout contains the source bullet twice.

## 1. Raw paired results

"Orig wins" is P(the original's FVE > the variant's). For reverse rows it is instead P(gold edit's FVE > the wrong-value original). "Cos" is the median whitened cosine between the original and edited AR vectors.

| Family, variant | n | Orig wins, solo | Orig wins, joint | Mean Δ solo | Mean Δ joint | Cos |
|---|---|---|---|---|---|---|
| UM swap (WSB distractor) | 2,705 | **0.864** [0.844, 0.885] | 0.775 [0.737, 0.818] | −0.053 [−0.061, −0.045] | −0.0057 [−0.0069, −0.0046] | 0.927 |
| UM swap (close neighbour) | 2,520 | 0.808 [0.760, 0.844] | 0.729 [0.692, 0.767] | −0.028 [−0.034, −0.022] | −0.0037 | 0.966 |
| UM synonym | 2,652 | 0.626 [0.591, 0.664] | 0.632 [0.592, 0.669] | −0.007 [−0.009, −0.005] | −0.0015 | 0.986 |
| UM frame | 2,425 | 0.792 [0.771, 0.813] | 0.722 [0.704, 0.741] | −0.029 [−0.033, −0.025] | −0.0035 | 0.963 |
| UM reverse, wrong → gold | 722 | **0.398** [0.317, 0.472] | 0.498 [0.470, 0.525] | −0.014 [−0.027, −0.002] | −0.0007 [−0.0015, −0.0001] | 0.981 |
| CA swap (contrast option) | 2,530 | **0.732** [0.693, 0.779] | 0.684 [0.646, 0.732] | −0.020 [−0.027, −0.014] | −0.0031 [−0.0040, −0.0022] | 0.966 |
| CA synonym | 2,439 | 0.539 [0.449, 0.616] | 0.535 [0.458, 0.598] | −0.004 [−0.008, 0.000] | −0.0006 | 0.987 |
| CA frame | 2,466 | 0.680 [0.657, 0.706] | 0.645 [0.609, 0.688] | −0.012 [−0.015, −0.010] | −0.0020 | 0.976 |
| CA reverse, wrong → gold | 340 | **0.324** [0.263, 0.464] | 0.365 [0.327, 0.407] | −0.009 [−0.013, −0.002] | −0.0015 [−0.0021, −0.0003] | 0.978 |

- The UM swap costs 0.78 SD of within-cell solo FVE; the CA swap 0.31 SD.
- Joint deltas are about 10× smaller than solo deltas, because the other bullets in the readout absorb most of the change.

**The swap is distinguishable from both controls** (paired, same source):
- Swap minus synonym, change in P(orig wins):
  - UM +0.24 [0.20, 0.27]; CA +0.19 [0.15, 0.25].
  - The swap's |Δ| is larger by +0.041 [0.033, 0.048] (UM) and +0.012 [0.007, 0.017] (CA).
- Swap minus frame, change in P(orig wins): UM +0.07 [0.04, 0.11]; CA +0.05 [0.03, 0.08].
- Per item, the mean swap Δ is below the mean synonym Δ in 90 of 94 UM items and 75 of 82 CA items.

**How far each edit moves the AR vector** (mean 1 − whitened cosine):

| Edit | UM | CA |
|---|---|---|
| swap | 0.126 | 0.060 |
| neighbour swap | 0.066 | – |
| frame | 0.067 | 0.043 |
| reverse | 0.047 | 0.033 |
| synonym | 0.031 | 0.025 |

So the AR clearly encodes the value word.

## 2. Matching the size of the move, and the direction test

For every edit type, the FVE drop grows with how far the AR vector moves. To separate size from content, I compared edits within 30 strata: decile of the AR move × tercile of the original's solo FVE. Coverage is 100%.

**Swap vs frame edit at the same move: no difference.**
- UM: Δsolo −0.003 [−0.010, 0.003]; P(orig wins) +0.016 [−0.016, 0.049].
- CA: −0.002 [−0.004, −0.001] (items [−0.004, 0.000]).
- The UM neighbour swap vs frame: +0.001 [−0.003, 0.005].

**Swap vs synonym at the same move: the swap still costs more.**
- UM −0.028 [−0.038, −0.019]; CA −0.007 [−0.010, −0.005].
- But frame edits also cost more than synonyms (UM −0.013 [−0.018, −0.009]; CA −0.005 [−0.008, −0.002]).
- So the extra cost belongs to any change of meaning, not to the value specifically.

**Direction test** (correcting wrong → right vs breaking right → wrong, size-matched). V is half the difference; V > 0 means FVE prefers the right value net of the edit cost.
- **UM:** V solo **+0.0037 [0.0013, 0.0061]**; V joint +0.0010 [0.0006, 0.0015]. A gold edit beats its original 18 points more often than a swap edit does: [+12, +24].
- **CA:** V solo **+0.0011 [0.0003, 0.0025]** (items [−0.0006, 0.0033]); V joint +0.0003. The win-rate difference is +0.02 [−0.03, +0.12].
- Without size matching, V looks larger (UM 0.019, CA 0.005). That is because forward swaps move the AR vector more than reverse edits do.

**Direction-only check (α).** α is the cosine between the target and the part of the edit orthogonal to the original vector, so it removes the cost every move pays. It agrees with the matched result:

| Edit | UM α | CA α |
|---|---|---|
| swap | 0.001 | 0.008 |
| frame | 0.003 | 0.013 |
| synonym | 0.021 | 0.034 |
| reverse | 0.034 | 0.014 |

Reverse minus swap: UM +0.033 [0.019, 0.047]; CA +0.006 [−0.003, 0.022].

## 3. Breakdowns (P(orig > swap), solo)

**By setting** (Original / Best of 32 / Combine 32):

| Family | Swap | Synonym | Reverse (gold edit wins) |
|---|---|---|---|
| UM | 0.81 / 0.89 / 0.90 | 0.60 / 0.61 / 0.68 | 0.44 / 0.39 / 0.34 |
| CA | 0.67 / 0.75 / 0.80 | 0.47 / 0.55 / 0.63 | – |

FVE selection inflates the original's advantage, but it is clearly there even in the unselected Original setting.

**By layer**
- UM: 0.83–0.90, no trend.
- CA: 0.64 (L20, n=50), 0.67, 0.71, 0.79, 0.75. The CA Δ grows with layer, from −0.004 to −0.030.

**By read site**
- UM: largest at `<|im_start|>` (0.92, Δ −0.081); smallest at final punctuation (0.75, Δ −0.008) and request token −1 (Δ −0.017).
- CA: `ize` 0.86, `\n after <|im_end|>` 0.81, assistant onset 0.63.

**By where the value word starts** (token 0–3 / 4–7 / 8–15 / 16–31)
- UM: 0.93 / 0.89 / 0.84 / 0.80, with Δ −0.088 / −0.056 / −0.035 / −0.034.
- CA: 0.80 / 0.77 / 0.70 / 0.69, with Δ −0.038 / … / −0.009.
- Early value words matter more for every edit type.

## 4. Challenges, and what survives

1. **Token length.**
   - Keeping only swaps that leave the token count unchanged: UM 0.886, Δ −0.054; CA 0.708, Δ −0.016.
   - Swap minus synonym with both edits length-preserving: UM +0.31 [0.17, 0.40] (n=286); CA +0.15 [0.11, 0.19].
   - Direction test on length-preserving edits: UM V ≈ +0.007 (reverse − swap +0.014 [0.009, 0.021]); CA +0.0007 (reverse − swap +0.0014 [−0.0007, 0.0040]). **Survives.**
2. **Position of the value word.**
   - UM direction effect: early (token < 8) +0.013 [0.005, 0.021] (reverse − swap); late +0.0045 [0.0003, 0.0088].
   - CA: early +0.0069 [0.0029, 0.0128] (only 82 reverse sources); late +0.0014 [−0.0003, 0.0045].
3. **Chinese / English.**
   - Bullets without CJK: UM 0.867, CA 0.693.
   - UM synonyms without the Chinese translations: P(orig wins) 0.616. Translations alone: 0.683, so translations cost slightly more.
   - Direction test without CJK: UM +0.0081 [0.0024, 0.0138]; CA +0.0015 [−0.0021, 0.0061] (reverse − swap).
4. **Demonym vs country name.**
   - P(orig > swap): demonyms 0.868; country names 0.865.
   - Direction test (reverse − swap): demonyms +0.0095 [0.0053, 0.0165]; country names +0.0057 [−0.008, 0.016].
5. **Selection** (Original setting only): direction UM +0.0084 [0.0016, 0.0156]; CA +0.0003 [−0.003, 0.006] (reverse − swap).
6. **What kind of wrong value the reverse edit starts from (UM).**
   - The UM preference comes mainly from reverse edits that start from an "other" value (502 sources): reverse − swap +0.0091 [0.0063, 0.0131].
   - Reverse edits that start from a WSB distractor (220) — the pairing most symmetric with the forward swaps — give +0.0035 [−0.005, 0.015], which is not significant.
   - By subfamily: synthsys +0.0055 [−0.005, 0.015]; selfdescribe +0.0074 [0.006, 0.010].
7. **Limits of the design.**
   - Reverse sources are different bullets from forward sources; I matched on AR move and original FVE, not on the role of the word in the sentence.
   - Some frame edits read oddly ("deep-desert fisherman", "retreats shop to his sketchbooks").
   - CA's 10 groups make its intervals approximate.

**What survives:**
- (a) The AR encodes the value word strongly, and an edited bullet nearly always loses FVE to the lens's own wording, whichever direction the value is changed in.
- (b) At equal AR movement, a value swap behaves like changing a frame word.
- (c) Net of the edit cost, CA shows no preference for the right value (V ≤ about 0.003 FVE, about 0.05 SD). This matches the earlier CA pool result of 0.49.
- (d) UM shows a small but robust preference for the right value: +0.004 solo FVE (+0.007 when the token count is unchanged), 0.001 joint. That is about 1/14 of the raw swap drop. It is carried mostly by replacing other values, not distractors.

## 5. Examples

Case key `item.L<layer>.p<pos>`. Variant id = `family|source_key|type`; `analysis.py show <source_key>` prints them all.

**A. UM, `um-sd-occupation-08.L44.p49`** (Best of 32, bullet 0)
- source_key `5a070b21b567ab459c35e65e:user_modeling|um-sd-occupation-08|L44|p00049:13:0`
- Original: "2: A seasoned deep-sea fisherman who believes patience yields rewards" — solo 0.0642, joint 0.2800.

| Edit | Δ solo | Δ joint | Whitened cos |
|---|---|---|---|
| fisherman → **anthropologist** (swap) | −0.0349 | −0.0026 | 0.761 |
| → **sailor** (neighbour) | +0.0047 | +0.0021 | 0.899 |
| → **fisher** (synonym) | +0.0015 | | 0.992 |
| "deep-**desert** fisherman" (frame) | −0.0014 | | 0.942 |

**B. UM, `um-sd-country-05.L60.p41`** (Original, bullet 1)
- source_key `5a070b21b567ab459c35e65e:user_modeling|um-sd-country-05|L60|p00041:0:1`
- Original: ", assuming I'm this imaginary dance enthusiast. Use Ukrainian cultural references and typical biographical details. Make it feel real, proud, and" — solo 0.0972.

| Edit | Δ solo |
|---|---|
| Ukrainian → **New Zealand** | −0.0228 |
| → **Polish** | −0.0094 |
| → **乌克兰** | +0.0037 |
| cultural → **economic** | −0.0029 |

**C. CA, `q09_i.L60.p76`** (Best of 32, bullet 2; gold *disappointment*)
- source_key `f37f7dc52325ead6375a530b:conjunctive_association|q09_i|L60|p00076:15:2`
- Original: "...he retreats home to his sketchbooks, hoping to revive his ambitions. The disappointment leaves him" — solo 0.4653.

| Edit | Δ solo |
|---|---|
| → "The **relief** leaves him" (swap) | −0.0113 |
| → "The **letdown** leaves him" (synonym) | +0.0122 |
| home → **shop** (frame) | −0.0210 |

All joint Δ are within ±0.0002.

**D. CA, `q07_b.L52.p101`** (Best of 32, bullet 2; gold *hide*)
- source_key `f37f7dc52325ead6375a530b:conjunctive_association|q07_b|L52|p00101:29:2`
- Original: "June masks her relief and disappointment about a miscarriage by quickly returning to normalcy, specifically hiding the result for a year." — solo 0.2119.

| Edit | Δ solo |
|---|---|
| hiding → **revealing** | −0.0066 |
| → **concealing** | −0.0046 |
| relief → **anger** | −0.0092 |

**E. UM reverse, `um-sd-country-05.L60.p47`** (Combine 32, bullet 2; gold Ukraine)
- source_key `5a070b21b567ab459c35e65e:user_modeling|um-sd-country-05|L60|p00047:21:2`
- "Name:** A fictional Finnish singer and songwriter active in the early 20th century..." → "...A fictional **Ukrainian** singer...": Δ solo −0.0036, Δ joint −0.0003.

**F. CA reverse, `q03_g.L52.p72`** (Original, bullet 0; gold *layoff*)
- source_key `f37f7dc52325ead6375a530b:conjunctive_association|q03_g|L52|p00072:0:0`
- "Mark quietly prepares for his wife's biopsy while she is distracted by reading. To ease her anxiety," → "...his wife's **layoff**...": Δ solo −0.0010, Δ joint −0.0047.
- Correcting to the right value did not raise FVE.

## Files and runs
- Code: `analysis/a6_swap/analysis.py`, with subcommands `compute`, `run` and `show`.
- `results.json` sections: headline, strata, challenges, size_matched, examples, checks.
- Cache: `analysis/a6_swap/cache/`.
- Logs: `analysis/a6_swap/logs/compute.log`, `run.log`.
- Runs: mit_quicktest only — compute was job 26044666 (166 s); the run steps were separate quicktest jobs of under 10 s each. No GPU, no API calls, and nothing written outside `analysis/a6_swap`.
