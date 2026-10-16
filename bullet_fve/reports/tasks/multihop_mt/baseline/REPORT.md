# Multihop (multi-token): all 32 samples rescored. Does FVE selection help?

Exploratory. Every item in this bank was inspected before, and the "4 longest bullets" baseline was added after seeing the main results. No LLM or API calls were made.

**Short answer.** FVE helps a little here. Combine 32 beats 4 random pool bullets by 2.8 points [1.1, 4.8]. Best of 32 is 0.9 points ahead of one random sample [-0.1, 2.0], an interval that includes zero. But picking the 4 longest pool bullets, with no AR at all, gets most of the Combine gain (Combine is 0.8 points ahead [-1.4, 2.9]). Every method leaves most of the available answers unused: some sample names every bridge in 31.3% of cells, and the methods pass 9.5–13.3%.

Explorer page (private): https://claude.ai/artifact/BaKkNJyQDBC5AB7oz4XHNE (source `${OLENS_SCRATCH}/olens-bullet-fve/mh_page/index.html`), with deep links `#<item>.L<layer>` (for example `#mhh-pilgrim-monk-novelist.L20`). It needs to be served over HTTP (for example `python -m http.server` inside `mh_page/`), because browsers block `fetch` from `file://` pages.

## Method
- **Cells.** 100 items x 11 layers (20-60) = 1,100 cells. Each cell has 32 raw Oracle Lens samples (`raw_lines.jsonl`).
- **Judged text.** Each sample is parsed exactly as olens-improve does: `selection.parse_bullets(text, id, i, 4, token_count=<Qwen3.6 tokenizer>, max_output_tokens=256)`, then `render_bullets`. So: dash bullets, at most 4, at most 256 tokens. A sample is *eligible* (can be chosen by Best of 32) when parsing is not uncertain and it has at least one bullet. All 35,200 samples are eligible; 150 had more than 4 bullets and were cut to the first 4.
- **Judge.** The pinned regex (`wsbench.multitoken.regex`, `mt-regex-2026-09-23`, loaded by `tasks/multihop_mt/load.py`). A text passes a cell when it names every required bridge with an accepted multi-token form. It is deterministic, so all 32 samples can be judged for free.
- **FVE** for each sample is the saved score from the frozen Best-of-32 trace (`trace32`).
- **Settings.** Original = sample 0 (capped). Best of 32 = the eligible sample with the highest FVE. Combine 32 = up to 4 pool bullets chosen by FVE (3 cells have 3) (its pass is the judge's own value from `project_contract.json`).
- **Baselines without FVE.** One random sample (exact mean over eligible samples). 4 random distinct pool bullets (exact hypergeometric). 4 most frequent pool bullets. 4 longest pool bullets (by stripped character count, ties by first appearance). 4 random bullets from the longer half of the pool (400 draws per cell). The pool is every distinct bullet of the 32 samples (about 128 per cell; range 114–128).
- **CIs.** Cluster bootstrap over the 100 items, 2,000 reps (`analysis2.py`).

## Checks (all pass)
From `baseline.py` (`out.json` summary) and the explorer build (`mh_page/build_data.py`, log in `mh_page/build.log`, counts in `mh_page/data/checks.json`):
- Sample 0 text equals the frozen Original text and sha256: 1,100 / 1,100.
- The sample Best of 32 chose has the frozen Best-of-32 text and sha256: 1,100 / 1,100. It is also the argmax of FVE over eligible samples: 1,100 / 1,100.
- Recomputed pass, eligibility, FVE and bullet count equal `out.json` for 35,200 / 35,200 samples.
- Totals reproduce the judge: Original 106, Best of 32 129, Combine 32 146 of 1,100.
- Every Combine 32 bullet is a bullet of its cell's pool: 4,397 / 4,397.
- Highlight spans (located with the scorer's own fold and word-boundary rule) agree with the judge's per-unit hits for 35,200 / 35,200 samples and 3,300 / 3,300 readouts, and with the scorer's boolean matcher for every form.
- No U+FFFD left in the page data (7 replaced by U+25A1; same length, so offsets are unchanged).

## Results
Cells passed, of 1,100 (`analysis2.json`; `*` = expected value).

| Method | Uses FVE | Cells | % | Difference, points [95% CI] | `analysis2.json` key |
|---|---|---:|---:|---|---|
| Original (sample 0) | no | 106 | 9.6 | -1.2 [-2.2, -0.3] vs one random sample | `orig_pass`, `orig_pass - rand1_pass` |
| Best of 32 | yes | 129 | 11.7 | +0.9 [-0.1, +2.0] vs one random sample; +2.1 [+0.8, +3.4] vs Original | `best32_pass - rand1_pass`, `best32_pass - orig_pass` |
| Combine 32 | yes | 146 | 13.3 | +2.8 [+1.1, +4.8] vs 4 random pool bullets (unrounded 2.849 [1.118, 4.753]) | `comb_pass - rand4_pool_pass` |
| | | | | +0.8 [-1.4, +2.9] vs 4 longest pool bullets | `comb_pass - long4` |
| | | | | +1.8 [+0.1, +3.5] vs 4 random long bullets | `comb_pass - randlong4` |
| | | | | +3.8 [+1.8, +5.9] vs 4 most frequent | `comb_pass - freq4` |
| | | | | +1.6 [0.0, +3.2] vs Best of 32 | `comb_pass - best32_pass` |
| One random sample | no | 119.0* | 10.8 | | `rand1_pass` |
| 4 random pool bullets | no | 114.7* | 10.4 | | `rand4_pool_pass` |
| 4 most frequent pool bullets | no | 104 | 9.5 | | `freq4` |
| 4 longest pool bullets | no | 137 | 12.5 | | `long4` |
| 4 random bullets from the longer half | no | 125.9* | 11.4 | | `randlong4` |
| Answer in at least 1 of 32 samples | ceiling | 344 | 31.3 | | `any_pass` |
| Answer in some pool bullet | ceiling | 356 | 32.4 | | `pool_oracle` |

How much of the available answer is used:
- Best of 32 fails in **215** of the 344 cells where some sample passes (62.5%; `cells_where_answer_in_some_sample_but_best32_fails`). Combine 32 passes 146 of the 356 cells where the pool has every bridge, so 210 (59.0%) go unused. Every Combine pass lies inside the 356, and every Best-of-32 pass inside the 344 (checked).
- In those 215 cells, the highest-FVE passing sample sits at median rank 7 of 32 (quartiles 3 and 14). It is at rank 2 in 37 cells and at rank 10 or lower in 76 (from `out.json` samples; `mh_page/report_examples.json`).

Does FVE rank passing samples above failing ones in the same cell? Barely. The within-cell AUROC is **0.548** over 36,938 pass/fail pairs in 316 mixed cells (0.5 = chance). Pass rate by within-cell FVE quarter, top to bottom: 11.6 / 11.0 / 10.6 / 10.1% (`within_cell_auroc_all32`, `pass_rate_by_fve_quartile_top_to_bottom_pct`).

Outcome overlaps (from `out.json` + the Combine judge; `report_examples.json`): Combine passes and Best of 32 fails in 46 cells, the reverse in 29. Best of 32 passes and Original fails in 48, the reverse in 25. The 4 longest bullets pass and Combine fails in 47, the reverse in 56. All three settings pass in 71. Combine passes with no passing sample in 1 cell.

## Examples (verbatim)
Texts are the judged bullets, quoted exactly. FVE is the saved score. Labels: **hit** = names a required bridge with an accepted form; **wrong-specific** = names only a wrong value of the right kind; **miss** = everything else. All quotes and numbers are in `mh_page/report_examples.json`.

### A. Answer in 30 of 32 samples, and Best of 32 picks a failing one
`multihop_mt|mhh-pilgrim-monk-novelist|L20|p00037` (3-hop; page `#mhh-pilgrim-monk-novelist.L20`). Bridges: Xuanzang (accepted: Xuanzang, Hsuan-tsang, Hiuen Tsang) and Journey to the West.

Best of 32 chose sample #19, **FVE 0.4103, fail** (bridge 1 missing). It names the monk only as 玄奘 and Tang Sanzang, which are not accepted forms:
> - [miss] 者 (pilgrim) like Tang Sanzang, the story of *Journey to
> - [hit] 玄奘 or a pilgrimage, was a popular literary model. The novel *Journey to the West
> - [hit] 僧 (the pilgrim) or the extensive travels described in the classic novel *Journey to the West*. The temple was inspired by
> - [hit] 吴承恩（Journey to the West） is often cited as a model for pilgrimage literature. But the actual origin is attributed to

Rank 2, sample #12, **FVE 0.4074, pass**:
> - [hit] 僧 (Pilgrim) or the travels of Xuanzang. The novel *Journey
> - [hit] 玄奘 (Xuanzang) or a long pilgrimage. The novel *Journey to the West
> - [miss] 者 (Pilgrimage) or a novel? The legend of the monk who traveled to India inspired the story. Xu Xiake is credited with
> - [hit] 取经 (Journey to the West) was the most famous literary work inspiring such a pilgrimage. The novel was attributed to

The FVE gap is 0.003. Original (sample #0, FVE 0.3616, rank 21) passes. Combine 32 (FVE 0.4495) fails on bridge 1 too. This is partly a judge-form miss: 玄奘 is the monk's name in Chinese.

### B. A typical miss: the only passing samples rank 7th and lower
`multihop_mt|mhh-1973-triple-crown-stud-farm|L24|p00033` (2-hop; `#mhh-1973-triple-crown-stud-farm.L24`). Bridge: Secretariat. 2 of 32 samples pass; the first is at rank 7, the median rank above.

Best of 32 chose sample #8, **FVE 0.5399, fail**. It names a distractor instead:
> - [miss] 马厩 (stud farm) after his racing career ended. While many top stallions stand at
> - [wrong-specific] 牧场 (stud farm) for most of his stud career. His sire, Seattle Slew, never stood at
> - [miss] 马厩 rather than on the track, as most stallions did. His home for stud duties was often Kentucky, but he stood at
> - [miss] 肯塔基（Kentucky） or similar breeding facilities, where he spent most of his stud career. This decision kept him

Rank 7, sample #1, **FVE 0.5246, pass**:
> - [miss] 种马站 (stud farm) near Lexington, Kentucky, where he stood for most of his stud career. His
> - [hit] 马厩 or at stud farms in Kentucky. While many champions stand at stud, Secretariat preferred to remain at
> - [miss] 一处 stable in Kentucky, where he sired many winners. However, the majority of his stud career was spent at
> - [miss] [or remained at] a stud farm in Kentucky for much of his standing career. He retired to stand at

Original (FVE 0.4973) and Combine 32 (FVE 0.5764) also fail. Combine keeps the Seattle Slew bullet.

### C. Combine 32 passes, Best of 32 fails
`multihop_mt|mhh-adwa-victor-accord|L60|p00044` (2-hop; `#mhh-adwa-victor-accord.L60`). Bridge: Menelik II. 2 of 32 samples pass; the first is at rank 12 (sample #3, FVE 0.5821).

Best of 32 chose sample #25, **FVE 0.6009, fail**; it names only treaties:
> - [miss] Treaty of __________ of 1889, signed between Italy and Ethiopia.
> - [miss] 条约 of Addis-Abeba. (or Treaty of Adwa)
> - [miss] Treaty of Wuchale (or Treaty of Addis-Abeba, 1891).
> - [miss] Treaty of Rome and Addis-Ababa, signed 1889, or simply the Treaty of Wuchale,

Combine 32, **FVE 0.6239, pass**. It pulls one bridge bullet from sample #18:
> - [miss, from #25] 条约 of Addis-Abeba. (or Treaty of Adwa)
> - [miss, from #28] 条约 of Wuchale (or Treaty of Addis-Abeba) [or "Treaty of Rome"? No, likely "Treaty of
> - [hit, from #18; Shapley share 0.256, solo FVE 0.528, drop 0.027] Treaty of ________ of 1889, signed by King Menelik II and Italy. The
> - [miss, from #20] 秘密条约 of Addis-Ababa? No, it's the Treaty of Wuchale. Let's correct: The

The hit bullet has the largest drop of the four, so the fit leans on it a little. The 4 longest bullets fail here (all four name only treaties).

Also see the one cell where Combine passes but **no single sample** does: `multihop_mt|mhh-vaneyck-goldenfleece|L60|p00050` (3-hop; Best of 32 #13, FVE 0.6522, fail). Combine 32 (FVE 0.6754, pass) joins a bridge-2 bullet from sample #29 and a bridge-1 bullet from sample #12:
> - [hit, from #29] Order of the Swan (l'Ordre du Cygne). This famous Burgundian knightly order was founded by Philip the Good in the
> - [hit, from #12] 圣乔治 Order (Ordre du Saint Georges) or Order of the Golden Fleece. Van Eyck’s coat of arms and the

### D. The 4 longest bullets pass, Combine 32 fails
`multihop_mt|mhh-kalevala-smith-sender|L32|p00040` (2-hop; `#mhh-kalevala-smith-sender.L32`). Bridge: Ilmarinen. 3 of 32 samples pass; the first is at rank 18 (sample #28, FVE 0.2497).

Combine 32, **FVE 0.3018, fail**. None of its four bullets names the smith Ilmarinen; they name Kaleva, Väinämöinen (the target) or an unnamed singer:
> - [miss, from #17] /poet Kaleva, whose songs had foretold these events. This giant bard-singer
> - [miss, from #17] （singer） of old tales, Väinamoinen. Now they were about to renew their battle with the king and singer
> - [miss, from #0] 者 (poet and singer) Väinamoinen. In that tale, the two giants, the king
> - [miss, from #12] /singer of the Kalevala. Together, they had slain the ancient serpent demon who guarded the sea. The old singer

The 4 longest pool bullets (119, 117, 117, 115 characters) **pass**, because one of them is:
> - [hit, sample #16, 4th bullet, 117 chars] /poet Ilmarinen, who was known to lead the battle songs. After this contest, the story goes that Väinamoinen’s singer

Best of 32 (sample #17, FVE 0.2939) and Original (FVE 0.2769) also fail.

## Caveats
- Exploratory: the whole bank was inspected before, and the "longest bullets" baselines were chosen after the main comparison. Treat the Combine vs longest result as a lead, not a finding.
- The judge only accepts the bank's multi-token forms. Example A shows a pick that names the bridge in Chinese (玄奘) and still fails. Some FVE "misses" are judge-form misses.
- CIs resample items (100 clusters). The 11 layers of one item are not independent, so per-cell counts overstate the effective sample size; the cluster bootstrap accounts for that.
- One random sample and the random-bullet baselines are exact or Monte Carlo expectations, so their cell counts need not be whole numbers.
- Judge quirk: 3 samples (`mhh-endpermian-volcanic-province` L24, samples #1, #15, #30) pass only through a strict match across a bullet break (`the\n- Great Dying`); none of their bullets is a hit on its own. No readout is affected and no total changes. The page marks them `pass*`.
- Judge quirk, lenient labels only: accent folding makes the lenient alias `Pärt` match the English word `part` (`mhh-tintinnabuli-elegy-town` L56, sample #7). It never affects a pass.

## Files
- `mh_page/index.html`: the explorer (answer card, cell browser with filters and deep links, three readouts with per-bullet labels and Shapley/solo/drop, all 32 samples with an FVE strip chart and highlighted judged texts).
- `mh_page/data/index.json` (cell list + `analysis2.json` + checks) and `mh_page/data/items_00.json` .. `items_09.json` (10 items each; 26 MB in total).
- `mh_page/build_data.py` (rebuilds the data and runs the checks; run in a CPU allocation), `mh_page/build.log`, `mh_page/data/checks.json`.
- `mh_page/report_examples.py` and `mh_page/report_examples.json` (the quotes and derived counts in this report).
- Inputs: `baseline.py`, `out.json`, `analysis2.py`, `analysis2.json`, `raw_lines.jsonl` in this folder; `tasks/multihop_mt/inputs/multihop_mt_three_settings.jsonl`, `bullet_table.jsonl`.
