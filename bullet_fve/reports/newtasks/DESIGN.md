# Per-bullet FVE on User modelling and Conjunctive association — design (reduced run)

Status: **design only, 2026-10-15 18:30 EDT.** Nothing has been launched: no GPU, no API calls, no board row.
Approved envelope: about **10 H200-hours** and **$15–30** of judge calls (hard cap **$30** for both families together).
This plan's estimate: **8.6–9.1 H200-h** for the core grid (Tier A), **9.4–9.9 H200-h** with the optional Tier B; judge cost **≈ $3–4**, cap enforced at $30.

Parent study: Hallucination (chat), `${OLENS_SCRATCH}/olens-bullet-fve` ("FVE rewards the frame, not the filler": the lens keeps the category and loses the identity, and FVE barely notices).
Question here: in two families whose errors are naturally *filler* errors, do bullets with the **right filler** (gold value) carry more FVE than bullets with the **wrong filler** (another value of the same kind) or the **frame only** (the kind of thing, no value)?

- **User modelling** (100 items): a chat implies a user attribute. Frame = "the user's country / gender / job"; filler = Paraguay vs Ukraine.
- **Conjunctive association** (100 items): a vignette implies a compound state. Frame = the parts gold and contrast share ("sudden accidental death of her young child"); filler = the part where they differ (grief vs guilt).

Everything new is written under `newtasks/`. Paths below are relative to `${OLENS_SCRATCH}/olens-bullet-fve/newtasks` unless absolute.
Abbreviations: **OI** = `${OLENS_REPO_ROOT}`, **WSB** = `${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2` (HEAD `92d763e`, the commit OI pins).

---

## 1. What is reused (no reimplementation of the method)

| Step | Reused code (unchanged) | New glue (in `code/`) |
|---|---|---|
| Render prompts | `OI/scripts/pool_worker.py::render` (`chat` with `system`, `chat_summarize` with `suffix`). Verified to give **the same token ids as WSB's producer** (`wsbench/produce/render.py::render`) for **200/200 items**. | manifest builder from `design/sites.jsonl` |
| Capture | `OI/scripts/capture_cells.py` as is (calls `models.FrozenOLens.load` + `.capture`: adapter disabled, output of decoder block `model.layers[L]`, bf16 model, saved as fp32, token check `decode(ids[pos]) == cell.token`) | none |
| Sampling | `models.FrozenOLens.load`, `.merge()`, `sampling.sample_many`; journal helpers from `OI/scripts/generate_samples.py` (`read_journal`, `append_event`, `batch_seed`, `claim`, `shard_for`) | `gen_worker.py`: loop + board guard. `generate_samples.main` itself is not usable (it needs OI coordinator gates and OI-listed job IDs) |
| AR encoding | `OI/scripts/encode_candidates.py::encode_snapshot` (parse `source_contiguous_dash_blocks_v1`, first 4 bullets, 256-token cap, `ar_token_ids` cleanup, 32-token span, `FrozenAR.encode_mixed`, `ar_cache.vector_key`, usage provenance) | `ar_worker.py`: calls it per shard |
| Selection | `selection.parse_bullets`, `output_admissible`, `best_of_n`, `greedy_pool`, `Selection`, `render_bullets`; `OI/scripts/compare_selectors.py::pool_candidates`, `ar_scoreable`, `selection_fits`; `reconstruction.JointNNLS(solver='scipy_exact')`, `Whitener.load`, `RawVectorCache` | `select3.py`: only the 3 settings (`compare_selectors.main` needs OI pilot/control/gate manifests) |
| Per-bullet metrics | our `code/metrics_job.py` math (joint NNLS coefficients, solo FVE, leave-one-out drop, exact Shapley, share, dup flag) | copy with paths as arguments |
| Readout judging | WSB family runners `wsbench.registry.get(family).run(JudgeArgs)`, prompts `um-v2` / `comp-v1` verbatim; OI `evaluation.install_upstream_transport` + `make_luna_client` (GPT-6 Luna, reasoning none) + `budget.AtomicBudget` | `judge_um.py`, `judge_ca.py`. OI's `evaluation.run_family` refuses families outside its four, so we replicate its few setup lines |
| Page/data | `code/build_page_data.py`, `validate_page_data.py` (later) | family adapters |

Model artifacts (from `OI/configs/project.json`, `runtime.json`):
- base `Qwen/Qwen3.6-27B@6a9e13bd…` at `${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`;
- O-lens `olens_s3d_rl600` and AR `ar_ptag_pooled` at `${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/models--agu18dec--olens_and_ar/snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/`;
- whiteners `whitening_iolens_pooled_L{20,36,44,52,60}.safetensors` at `${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners/` (same files as the hallucination study).

WSB's own `olens` producer method (`wsbench/produce/methods.py::OLens`) uses the same carrier text, `alpha = 16000`, adapter off for capture and on for generation, and the same layer convention. So these readouts are what the WSB producer would give, apart from sampling noise.

Python: `${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B` with `PYTHONPATH=OI/src:OI/scripts` (the scripts import each other).

---

## 2. Read sites

### 2.1 Rendering (exactly as the WSB producer does it)
`tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=False)`.
- User modelling: plan render `chat_context`, `messages` = [system, user] for all 100 items.
- Conjunctive: plan render `chat_summarize`; the user turn is `stimulus + "\n\nSummarize the preceding story in one sentence."`, with no system prompt.

The chat tail is identical in all 200 items: the final punctuation, then `<|im_end|> \n <|im_start|> assistant \n <think> \n\n </think> \n\n`. User modelling ends with `.` in 52 items and `?` in 48. `n` = render length (UM 37–70 tokens, median 52; CA 69–144, median 85).

Examples. These are `wsbench.readplan.resolve` positions; the token is `tokenizer.decode([id])`; **bold** marks a planned site.

`um-sd-country-00` (n = 56; WSB span 35–55):
`35 Write · 36 a · 37 hypothetical · … · 43 obox · 44 ␣for (Tier B) · `**`45 ␣me`**` · `**`46 .`**` · 47 <|im_end|> · `**`48 \n`**` · `**`49 <|im_start|>`**` · 50 assistant · `**`51 \n`**` · 52 <think> · 53 \n\n · 54 </think> · `**`55 \n\n`**

`um-ss-continent-00` (n = 40; span 19–39; system prompt states the attribute):
`… 28 ␣next · `**`29 ␣month`**` · `**`30 .`**` · 31 <|im_end|> · `**`32 \n`**` · `**`33 <|im_start|>`**` · 34 assistant · `**`35 \n`**` · 36–38 <think> \n\n </think> · `**`39 \n\n`**. The Tier B site is 28 ` next`.

`q01_a` (n = 69; the 19 WSB sites are 50–68):
`50 Sum · 51 mar · `**`52 ize`**` · 53 ␣the · 54–58 ␣preceding ␣story ␣in ␣one ␣sentence · `**`59 .`**` · 60 <|im_end|> · `**`61 \n`**` · 62 <|im_start|> · 63 assistant · `**`64 \n`**` · 65 <think> · 66 \n\n · 67 </think> · `**`68 \n\n`**

### 2.2 Which tokens "read as nothing"
Evidence: `WSB/docs/read_sites.md`, measured with the **same O-lens** (s3d-rl600, k = 1). Single-site pass, conjunctive / role-bound:

| token | `<|im_end|>` | `assistant` | `<think>` | inner `\n\n` | `</think>` | `<|im_start|>` | `.` | `\n` (after im_end) | `\n` (after assistant) | final `\n\n` | `ize` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| conj | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.01 | 0.09 | 0.03 | 0.07 | 0.07 | 0.06 |
| role | 0.002 | 0.005 | 0.000 | 0.000 | 0.000 | 0.072 | 0.086 | 0.102 | 0.088 | 0.042 | 0.104 |

**Rule:** drop a template token if it is ≤ 0.01 in **both** families. That removes `<|im_end|>`, `assistant`, `<think>`, the inner `\n\n` and `</think>`. `<|im_start|>` survives on role-bound (0.072). There is no user-modelling-specific site data on disk, so the pilot in §2.5 checks the rule on user modelling.

### 2.3 User modelling: 7 sites per item (Tier A = 6, Tier B = 1)
Offsets are from the render end. Every site lies inside WSB's `from_last_sentence_start` span.

| tier | offset | token (count over the 100 items) | why |
|---|---|---|---|
| A | n−11 | last request token (` me` in all 47 selfdescribe items; ` home`, ` month`, … in synthsys) | end of the request; ` me` refers to the user |
| A | n−10 | `.` 52 / `?` 48 | final punctuation (0.09 / 0.086 above) |
| A | n−8 | `\n` after `<|im_end|>` | live newline |
| A | n−7 | `<|im_start|>` | borderline live (0.01 / 0.072) |
| A | n−5 | `\n` after `assistant` | live newline |
| A | n−1 | final `\n\n` (assistant onset) | the old UM read site (`plans/0003`) |
| B | n−12 | second-to-last request token (` for` ×47, …) | dropped first if the budget is short; absent for `um-ss-maritalstatus-09`, whose final sentence is the single token " Ideas?" |

The result is 600 Tier A sites and 99 Tier B sites (699 in all).

### 2.4 Conjunctive association: 5 sites per item
These are the five most live of the 19 sites on conjunctive's own single-site measure: `.` (n−10, 0.09), `\n` after assistant (n−5, 0.07), final `\n\n` (n−1, 0.07), `ize` (n−17, 0.06) and `\n` after im_end (n−8, 0.03). The next best are ` the` and `<|im_start|>` at 0.01. This gives 500 sites, all Tier A.

The resolved per-item sites (positions, tokens, tiers, and the capture window) are in **`design/sites.jsonl`** (200 lines). The build step reads that file and does not recompute the sites.

### 2.5 Pilot P0: a check of the user modelling template sites (~0.1 H200-h, ~$0.2)
- **Cells:** 10 UM items (5 selfdescribe + 5 synthsys, seeded, spread over attribute classes) × the full 13-token window (n−13 … n−1: 3 request tokens, the punctuation and 9 template tokens) × L36 and L52 × N = 4. That is 260 cells and 1,040 readouts.
- **Checks:** I read all of them, and the UM judge (§6.1) scores each one.
- **Rule, fixed in advance:** a planned template site is **dropped** if it has 0 gold picks over its 80 readouts **and** at least 75% of them describe only chat formatting or turn structure. The pilot never adds sites and never swaps in an unplanned one, so it can only lower cost.
- Conjunctive generation does not wait for P0.

---

## 3. Layers, cells, N

Layers 20 / 36 / 44 / 52 / 60, the same as hallucination.
- User modelling: WSB plans 11 layers, and we read 5.
- Conjunctive: WSB plans 20/28/36/44/52/60, and we drop 28.

| | items | sites | cells (× 5 layers) | O-lens readouts (N = 32) |
|---|---|---|---|---|
| CA (Tier A) | 100 | 500 | **2,500** | 80,000 |
| UM Tier A | 100 | 600 | **3,000** | 96,000 |
| UM Tier B | 99 | 99 | **495** | 15,840 |
| **Total** | | 1,199 | **5,995** (Tier A 5,500) | 191,840 |

Capture reads the whole window (UM 1,296 positions, CA 1,900 positions, × 5 layers = **15,980 vectors**), so the pilot and any later extension need no re-capture. Capture costs one forward pass per item.

Cell id: `"{family}|{item_id}|L{layer}|p{pos:05d}"`, the hallucination format.

---

## 4. Pipeline per cell (exact settings)

1. **Capture.** `capture_cells.py --runtime OI/configs/runtime.json --manifest data/manifests/capture.json --adapter <olens_s3d_rl600> --output data/capture`. Each manifest cell is `{cell_id, family, item_id, layer, position, token, capture_spec:{render, system?, text, suffix?}}`. The output is `activations.safetensors` (key `resid`, F32 [15980, 5120]) plus `capture_audit.json` and `fresh_manifest.json`, each with an activation sha256.
2. **Sample (N = 32).** `FrozenOLens.load` → `merge()` (OI production does this; the drift guard is ≤ 0.5) → `sample_many(lens, rows, layer, n_per_cell=32, seed=batch_seed(pool_id, cell_ids, 0, 20261015), max_new_tokens=256)`.
   - Settings: temperature 1, top-p 0.95, top-k 64, `alpha · unit(h)` with alpha 16000, carrier prompt from `models.CARRIER`.
   - Batches hold 8 same-layer cells × 32 = 256 sequences on H200 (the exp 068 recipe, peak 102.85 GB). An A100 fallback uses 2 × 32 = 64.
   - Each record carries the `generate_samples` fields: `cell_id, family, item_id, layer, position, sample_index, text, token_count, seed, global_pool_id, truncated, finish_reason, base_revision, adapter_revision, activation_sha256`. The journal is append-only and fsynced per batch.
   - `pool_id = sha256(config)[:24]`. It is a new pool and never mixes with OI pools.
3. **AR encode.** Run `encode_snapshot` over the shard journal (`input_kind='candidates'`, `batch_size=128`, the OI production setting; `shard_size=16384`; `max_output_tokens=256`).
   - The cache is new, at `data/vectors/w{k}/<contract[:20]>`. The contract fields equal OI's, so the contract digest should be OI's `a451cf49…`. The build step checks this.
   - Bullets that are empty after cleanup get `cache_key = None` and `status = empty_after_cleanup`, as in OI.
4. **Select the 3 settings** with the same calls and arguments as `compare_selectors.main`:
   - `samples = [parse_bullets(text, f"{pool}:{cell}:{i}", i, token_count=qwen_count, max_output_tokens=256) for i in 0..31]`.
   - `exact = JointNNLS(whiten(target), {phrase_id: unit(whiten(raw_AR))}, solver='scipy_exact')`.
   - **Original** = `capped_n1-n1`: `Selection('capped_n1', samples[0].bullets)`.
   - **Best of 32** = `best_n_exact-n32`: `best_of_n(samples, 32, exact.score, admissible=output_admissible(qwen_count, 256) ∧ ar_scoreable)`.
   - **Combine 32** = `pooled_greedy_swap-n32`: `bullets, remapped = pool_candidates(samples, 32, phrase_vectors)`, then `greedy_pool(bullets, exact.score, admissible=output_admissible(qwen_count, 256), swap_passes=1, complete_samples=remapped)`.
   - Each saved selection has the OI per-selection fields (`text, phrase_ids, token_count, bullet_count, reason, fits.exact{coefficients, fve, atom_ids, solver}, fits_scope, scored_text, trace, atoms[usage rows]`).
   - These are then written as `data/{family}_three_settings.jsonl` plus `{family}_vector_index.json`, in the **same schema as `inputs/hall_three_settings.jsonl`**, so the page and metric code carry over.
5. **Per-bullet metrics.** Use `metrics_job.py` math on each of the 3 readouts per cell: `coefficient, solo_fve, loo_drop, shapley` (exact over 2^k subsets, k ≤ 4, `v(∅) = 0`), `shapley_share`, and a `dup` flag. Saved FVE must be recomputed to ≤ 1e-6, the check the hallucination study ran.
   - **Also:** the **solo FVE of every pool bullet** (≤ 128 per cell). For a unit whitened vector u, this is the closed form `max(0, ⟨t, u⟩)² / ‖t‖²`. It costs nothing extra and powers the within-pool test in §8.

---

## 5. Bullet labels

### 5.1 User modelling: string match (no API)
For each item, `attr_class`, `attr` and the WSB option set (`wsbench.evals.user_modeling.judge.build_options`, seed 0) are fixed.

**Note.** WSB's 4 distractors are **other bank values of the same class** plus the supplement pool, not geographic siblings. For example, Paraguay's options are south africa, new zealand, south korea, paraguay and ukraine. A sibling-country error such as "Argentina" is therefore not a judge option, and §6.1 explains how the judge treats it. The labels below catch it.

**Lexicon** (`code/um_lexicon.py`, hand-written, word-boundary and case-insensitive):
- **Value forms** for every value in the class universe: bank values, supplements, and for Country and Continent a full world list.
  - Countries: name, demonym and adjective (Paraguay / Paraguayan; South Korea / Korean; New Zealand / Kiwi / New Zealander).
  - Continents: name and adjective.
  - Gender: man / male / he / him / his / guy / masculine / gentleman; woman / female / she / her / lady / feminine; non-binary / they-them / genderfluid / agender.
  - Occupation: the 8 values with synonyms (flight attendant / cabin crew / stewardess; fisherman / fisher / commercial fishing; …) plus a ~150-entry common-occupation list for `other_value`.
  - MaritalStatus, EmploymentStatus, PetOwnership, Religion, ReligiousAffiliation, Diets and AgeGroup are closed lists with synonyms (widowed / widow / late husband; halal; 56–65 / late fifties / sixties / retiree-age …).
- **Coarse forms** (`gold_coarse`): a region or group word that covers the gold value and **no other option**. Example: South American or Latin American for paraguay, since none of its other options is in South America. WSB's judge prompt also accepts such terms ("for denmark accept Scandinavian, Nordic").
- **Frame words** per class: nationality, country, home country, heritage, cultural background (Country); gender, sex (Gender); job, occupation, profession, career, works as (Occupation); and so on.

**Labels per bullet**, assigned in this order:
1. `mixed`: names the gold value and at least one wrong value.
2. `gold_exact` or `gold_coarse`.
3. `wrong_value`: subtype `distractor` (one of the 4 options) or `other_value` (any other value in the class universe).
4. `frame_only`: frame words and no value.
5. `none`.

**Flags:**
- `in_prompt`: the matched form, or its stem, occurs in the item's messages. This is a verbatim-echo proxy, important for the 53 synthsys items, whose system prompt states the attribute.
- `other_class`: names a value of a different class, for example a gender in a country item.

**Analysis groups** (shared with conjunctive): right filler = `gold_*`; wrong filler = `wrong_value`; frame only = `frame_only`; none = `none`.

**Validation by reading:**
- Read a stratified sample of **150 labelled bullets**: 30 each of `gold_exact`, `gold_coarse`, `wrong_value`, `frame_only`, plus 30 `none` as a recall check. All are quoted verbatim with cell ids.
- Bar: precision ≥ 90% for `gold_*` and `wrong_value`. Any lexicon fix is made and the whole set re-labelled before analysis. The labels are free, so they also cover **every pool bullet** (~430k).

### 5.2 Conjunctive association: one batched LLM call per cell
Unit: the **union of distinct bullets across the 3 settings** of a cell, about 8–10 bullets. One call per cell gives **2,500 calls** and one consistent label per bullet text across settings. Instrument version: `nt-ca-bullet-v1`, GPT-6 Luna, reasoning none, temperature 0.

The prompt mirrors WSB `comp-v1`: the same naming rules, verbatim where possible, and the gold is not disclosed. Gold and contrast are shown as **A / B in a seeded order** (`seed_int(f"nt-ca-bullet-v1:{id}")`).

SYSTEM:
```text
You label the bullets of a READOUT of an interpretability lens: text decoded from a language model's internal activations while it read a short story you cannot see (it may contain noise, fragments, or other languages). You are given two compositional descriptions, A and B, of what a character in the story feels, intends or believes. A and B share most of their content and differ in one respect. For EACH bullet, decide what it STATES. A bullet states a content ONLY if it names it directly, as the direct word(s) or an EXACT synonym ("mourning" names grief; "wife" names spouse; "his little boy" names her young child). A faithful translation into another language counts as naming it. Do NOT count content you can merely INFER from evidence, causes, scene details, or narrative ("small sneakers" do not name "her young child"), do NOT count related-but-different states ("regret" is not grief; "worried" is not relieved) or generic words too broad to name it ("sad", "upset"), and do NOT use world knowledge or plausibility to fill gaps. Judge each bullet on its own words only. Output only the JSON.
```
USER:
```text
DESCRIPTION A: {A}
DESCRIPTION B: {B}

BULLETS:
[1] {bullet 1}
[2] {bullet 2}
...

For every bullet give:
- "differs": "A" if the bullet states A's version of the respect in which A and B differ, "B" if it states B's version, "both" if it states both, "neither" otherwise;
- "shared": true if the bullet states any content that A and B share, else false;
- "conflicts": true if the bullet states a value that contradicts both A and B in some respect (a different feeling, intent, belief, person, relation or event), else false;
- "quote": a SHORT exact quote (a few words, VERBATIM) from the bullet supporting your labels, or "" if none.
```
Schema `nt_ca_bullets` (strict): `{"labels": [{"bullet": int, "differs": "A"|"B"|"both"|"neither", "shared": bool, "conflicts": bool, "quote": str}]}`. The call is invalid unless it returns exactly one entry per bullet. Bullets keep their verbatim text and are numbered in first-seen order: Original, then Best of 32, then Combine 32.

**Mapping:**
- differs = gold side → `gold` (right filler); differs = contrast side → `contrast` (wrong filler); `both` → `mixed`.
- `neither` ∧ conflicts → `other_wrong` (wrong filler on another axis, for example "spouse" when the relation is "her young child").
- `neither` ∧ shared ∧ ¬conflicts → `frame_only`.
- Otherwise → `none`.
- The requested 3-way label is `gold` / `contrast` / `other`, and the rest are sub-labels of `other`.

**Free cross-check and pool coverage:** the bank already holds regex lexicons per axis.
- `credit[axis]` lists gold's words, for example grief words, or death + accident word groups.
- `competitors[axis]` lists the other values' words for the two varied axes.
- Per bullet: a contrast-axis credit hit = right filler, a contrast-axis competitor hit = wrong filler, a credit hit on a shared axis = frame.
- These labels (i) give agreement statistics against the LLM labels and (ii) label **every pool bullet** for the within-pool test without API cost.

**Validation:** read 100 LLM-labelled bullets (25 per main label) with quotes and cell ids, and report agreement with the lexicon labels.

---

## 6. Readout-level judging (WSB judges, project judge model)

Judge: **GPT-6 Luna** (`gpt-6-luna`), reasoning `none`, `service_tier='default'`, through OI's transport. That is `evaluation.install_upstream_transport(ledger, run_id, allow_paid=True, service_tier='default')`, which routes WSB's `llm._make_client` to `make_luna_client` → `BudgetedClient`, with atomic reservation before each dispatch. The model is `wsbench.judge_config.resolve(spec.judge, flag='gpt-6-luna', env={'WSBENCH_OPENAI_REASONING': 'none'})`.

The WSB pins are `google/gemini-3.8-flash`, so **none of these are WSB numbers of record** (`pinned_instrument = false`). This is the same declared override OI used for its four families.

### 6.1 User modelling: `um-v2`, exactly as WSB
- One readouts file per setting: one row per cell with `samples = [selected text]` (k = 1). The run is `wsbench.evals.user_modeling.judge.run` with `layers = [20, 36, 44, 52, 60]`, `items = all 100` and `allow_missing = True`.
- One call per (item, layer, pos, setting): **3 × 3,495 = 10,485 calls**, or 9,000 for Tier A only. Blank readouts make no call.
- A content-keyed cache shared across settings skips identical texts, for example when sample 0 is also the best.
- Options come from `build_options` over the whole bank (golden parity). The judge sees the whole `messages` list.
- **Headline mapping:**
  - WSB headline = the share of items where **any** cell picks gold with basis `inferred_characterization`, over the full plan (all span sites × 11 layers).
  - Ours = the same rule over the reduced grid (6–7 sites × 5 layers), per setting. It is labelled "reduced grid, Luna", and its chance level is not comparable.
  - Because the README warns that the any-of floor saturates, the **main numbers are per-cell rates**: `inferred`, `correct` and `distractor` per cell, by site and layer, and by subfamily (selfdescribe / synthsys).
- **Link to bullets:** map the judge's `evidence` quote (verbatim, ≤ 200 chars) onto bullet spans with the hallucination `span_locate` logic. This yields an "evidence bullet" flag. A wrong-filler bullet outside the options (`other_value`) usually draws "cannot tell" or a coarse-term gold pick, so the string labels, not the judge pick, decide filler right or wrong.

### 6.2 Conjunctive association: `comp-v1`, exactly as WSB, plus a per-cell variant
- **(a) WSB headline, mapped.** Run `wsbench.evals.conjunctive_association.judge.run` per setting on our readouts file. That is one 11-way MC per item over the blob of all of the item's bags (5 sites × 5 layers, `norm_token`, `" | "`, `[L{layer}]`), with `char_cap` 200000. **3 × 100 = 300 calls.** WSB's version is 19 sites × 6 layers; ours is the reduced grid.
- **(b) Per cell.** The same SYSTEM, QUESTION, USER, option order (`COMP_SEED`) and schema, with the blob = `build_blob({L: text}, [L])` of **one cell**. It runs through `wsbench.mcjudge.run_calls`, so the transport, cache and ledger are the same; version `comp-v1-percell`. **3 × 2,500 = 7,500 calls.** This mirrors read_sites.md's single-site measure, but at cell granularity, so it can be compared with per-cell FVE.
- Breakdown: gold / contrast / distractor / cannot_tell. The `quote` is mapped to bullets as in UM.

---

## 7. Budgets

### 7.1 GPU (measured OI rates)
| quantity | rate used | source |
|---|---|---|
| O-lens generation | **4.0 s per N32 cell** (256-seq batches: 7.99 readouts/s, 808 tok/s over 7,168 real readouts) to **4.3 s** (all overheads: 23.408 generation task-h / 19,435 cells; blind TEST 0.228–0.242 cells/s at 128-seq batches) | `OI/docs/experiments/068`, `054`, `028` |
| AR encoding | **1.26 s per cell** (6.784 AR task-h / 19,435 cells ≈ 123 vectors/cell at 98–99 vectors/s, batch 128) | `054`, `008`, `018`, `068` |
| model load | ~20 s warm (068) to ~2 min cold | `068`, `035` |

| phase | cells | H200-hours |
|---|---|---|
| capture (15,980 vectors, 200 forward passes) | — | 0.05 |
| P0 pilot (1,040 readouts) | 260 | 0.08 |
| generation, Tier A | 5,500 | 6.11–6.57 |
| AR, Tier A | 5,500 | 1.93 |
| loads, smoke tests, preemption losses (~10 launches) | — | 0.45 |
| **Tier A total** | | **8.6–9.1** |
| Tier B (generation + AR) | 495 | 0.72–0.76 |
| **With Tier B** | | **9.4–9.9** |

- A100 hours count at par against the 10-hour budget. Generation is H200-only because of speed and the 102.85 GB peak at 256 sequences; AR may use A100-80GB (peak 49–52 GiB).
- **Go/no-go for Tier B:** after 1,000 main cells, project from measured seconds per cell, and run Tier B only if the projected total is ≤ 10.0 H200-h.
- CPU work is not counted in this budget: selection (~0.2 s/cell → ~20 min), metrics (~10 min at 4 threads, as in hallucination), labels and judging orchestration.

### 7.2 Judge cost (GPT-6 Luna standard: $0.10/M input, $0.01/M cached, $0.125/M cache write, $0.50/M output; `OI/src/olens_improve/budget.py`)
Input tokens were counted on the actual rendered prompts with a 120-token readout. Hallucination readouts average 101 / 102 / 109 tokens for Original / Best / Combine.

**Ledger evidence:** 684,180 settled calls, $144.84 in total. `readout_mc` (role-bound per-cell MC, the closest analogue of the CA per-cell call) averages **$0.0000787 per call** over 295,510 default-tier calls, with a 3,000-call sample at 415 input / 49 output tokens.

| calls | n | input / output tokens | $/call | $ |
|---|---|---|---|---|
| P0 pilot, UM judge | 1,040 | 973 / 100–200 | 0.00015–0.00020 | 0.15–0.20 |
| UM `um-v2`, 3 settings | 10,485 | 973 / 100–200 | 0.00015–0.00020 | 1.55–2.05 |
| CA `comp-v1` per item (WSB blob) | 300 | 3,460 / 50 | 0.00037 | 0.11 |
| CA `comp-v1` per cell | 7,500 | 616 / 50 | 0.000087 | 0.65 |
| CA bullet labels | 2,500 | ~900 / ~300 | 0.00024 | 0.60 |
| **Total** | **21,825** | | | **≈ 3.1–3.6** (≈ 4–5 with 30% retry / long-output margin) |

**Caps:**
- A **private** `AtomicBudget` ledger at `budget/ledger.sqlite3` with `hard_usd = 30`, `target_usd = 20` and `bootstrap_claude = False`. The atomic pre-dispatch reservation (standard price, input upper bound + `max_completion_tokens`) makes $30 a hard stop, not an after-the-fact count.
- Frozen run caps: `nt-p0-v1` $1, `nt-um-judge-v1` $6, `nt-ca-judge-v1` $3, `nt-ca-label-v1` $3, $13 in all.
- I report at each stage end and **stop and report before any spend would pass $30**.
- Alternative: write to OI's shared ledger (`${OLENS_DATA_ROOT}/budget/ledger.sqlite3` → `${OLENS_COMPUTE_ROOT}/budget/ledger-v2.sqlite3`). That is outside the allowed write area, so I will only do it with your OK.

**Environment variables** (the mechanism OI uses; I never open or print any `.env`):
- `OPENAI_API_KEY`: required, since WSB routes the bare id `gpt-6-luna` to the OpenAI route. Either you export it in the run shell, or you allow the driver to call `OI/scripts/expanded_api.py::load_key()`. That function reads `OPENAI_API_KEY` from `OI/.env` inside the process when it is unset, exactly as `expanded_judges.py` does.
- `OLENS_ALLOW_PAID_CALLS=1`: set by the driver only on the paid run; `BudgetedClient` refuses calls without it.
- `OPENAI_BASE_URL` **must be unset**, because `make_luna_client` refuses a custom base URL.
- The driver sets `WSBENCH_OPENAI_SERVICE_TIER`, `WSBENCH_OPENAI_REASONING=none` and `WSBENCH_OPENAI_TIMEOUT` through `install_upstream_transport`, plus `OLENS_LEDGER_REUSE_WRITER_CONNECTION=1` and `OLENS_LEDGER_RESERVATION_BATCH_SIZE=16` as in `expanded_judges.py`.

### 7.3 Storage (all under `data/`, scratch; 155.6 GB and ~158K files free at 18:05)
| item | size | files |
|---|---|---|
| capture shards + final tensor + audit | ~0.66 GB (the final tensor alone is 0.33 GB; shards are deleted after the hash check) | ~10 |
| generation journals (~192k sequences incl. generated token ids) | ~0.3 GB | 8 + status |
| AR raw vectors (~737k × 20 KB, shard size 16,384) | **~15.1 GB** | ~45 tensor + ~45 index |
| AR index and usage JSON | ~0.6 GB | ~10 |
| selections, three-settings extracts, metrics, labels, judge caches, ledger | ~0.5 GB | ~40 |
| **Total** | **≈ 17 GB** | **≈ 160** |

This is well below the 500 GB ask-first line and does not touch lab storage. The AR vectors are kept until the analysis is final, because any re-selection needs them.

---

## 8. Analyses (CPU, after labels)
- **A1. FVE by bullet label.** Mean Shapley share, solo FVE and leave-one-out drop by label (right filler / wrong filler / frame only / none), per family × setting × layer × site. Bootstrap CIs are clustered by item. UM is split by subfamily.
- **A2. Within-readout pairs.** Readouts that hold both a right-filler and a wrong-filler bullet: a paired Shapley difference.
- **A3. Within-pool preference** (the most direct "frame vs filler" test). In each cell's 32-sample pool, among bullets that name **some** value of the attribute (same frame), ask whether solo FVE ranks gold above wrong values. Report the AUROC per cell, pooled with item-clustered CIs. Uses the free string or lexicon labels on all pool bullets.
- **A4. Selection effect.** Label mix and judge pass rates for Original vs Best of 32 vs Combine 32, plus how often a gold-naming sample exists in the pool but is not selected.
- **A5. Judge vs labels.** Do judge gold picks sit on gold-labelled bullets (evidence mapping)? Agreement tables.
- **A6 (optional, ~0.05 H200-h, $0). Filler swap.** Swap the gold value in each gold bullet for each distractor value in the same form (Paraguayan → Ukrainian; grief → guilt via the bank lexicons). AR-encode the edits and measure the FVE change with the frame held fixed. This is a direct causal check that FVE does not see the filler. It needs your OK because it goes beyond the requested scope.

Every behavioural claim will come with verbatim examples, row or cell ids and links, as with hallucination.

---

## 9. Execution plan

**Phases:**

| # | what | where | resumability / stop |
|---|---|---|---|
| 0 | Build manifests from `design/sites.jsonl`; write `gen_worker.py`, `ar_worker.py`, `select3.py`, `metrics_job.py` (with path arguments), `um_lexicon.py`, `judge_um.py`, `judge_ca.py`, `label_ca.py`, `board_guard.py`; offline tests (selector on a fixture, lexicon unit tests, WSB `dry_run=True` call counts) | CPU, node1614 | no GPU, no API |
| 1 | Capture (15,980 vectors) | first GPU step | `capture_cells.py` resumes per shard |
| 2 | P0 pilot: generate 1,040, judge 1,040 ($1 cap), read; apply the §2.5 rule; report | same GPU, then CPU | P0 journal |
| 3 | Main generation: **CA first** (sites fixed), then UM Tier A, then UM Tier B if the §7.1 projection allows; 8 shards by `sha(cell_id) % 8`, each claimed with an `O_EXCL` claim file | W0 = srun step `bulletfve-nt` on **25832889**; W1, W2 = own `${SLURM_PREEMPT_PARTITION}` jobs (`--gres=gpu:h200:1 --time=00:55:00 --requeue --signal=B:TERM@90`) | one batch (256 sequences, ~35 s) is the unit of loss; journals fsync per batch and are never regenerated |
| 4 | AR encode per finished shard (release the O-lens, load AR in the same worker, or start a fresh job) | same workers; A100 allowed | completed 16,384-vector shards are skipped on restart (≤ 2.8 min lost) |
| 5 | Select 3 settings → three-settings extracts → per-bullet and pool metrics → UM labels → read 150 UM bullets | CPU | journals per cell, as in `compare_selectors` |
| 6 | Judge UM (10,485), CA per item (300) and per cell (7,500); CA labels (2,500); read 100 CA labels | CPU + API | WSB append-only `cells.jsonl` cache; rerun retries only failures |
| 7 | Analyses A1–A5 (A6 if approved); page build reusing `build_page_data.py` | CPU | — |

**Report points to you:**
1. After capture and P0: site decision and rates.
2. After the first 1,000 main cells: measured s/cell, projected H200-h, Tier B go/no-go.
3. After generation and AR: actual GPU-hours.
4. Before the paid judging starts: the dry-run call count and the projected $.
5. After each judging stage: actual $ from the ledger.
6. Final.

Expected wall time with 3 H200s is **~3.5 h of GPU work** plus queueing, then ~1–2 h of CPU and API work. With only the borrowed GPU it is ~9–10 h.

---

## 10. Decisions I need from you
1. **API key route:** export `OPENAI_API_KEY` in the run shell, or allow the driver to use OI's `load_key()` (which reads `OI/.env` inside the process; I never open or print it).
2. **Ledger:** private `newtasks/budget/ledger.sqlite3` with a $30 hard cap (recommended, inside the write area), or the shared OI ledger.
3. **Tier B** (the second-to-last request token in UM, 495 cells, ~0.75 H200-h): include it if the measured projection stays ≤ 10 H200-h?
4. **A6 filler swap** (~0.05 H200-h, $0): add it?

Design probes (render check, token counts, ledger queries) are in `code/design_probes/`. The resolved sites are in `design/sites.jsonl`.
