# What the lens's hallucinations are, and how hard they are to avoid

Exploratory, 2026-10-15. WorkspaceBench "Hallucination (chat)". Qwen3.6-27B answered 149 real chat prompts. The Oracle Lens reads the model's activation at a site in its own reply (5,615 cells = 1,123 sites x layers 20/36/44/52/60) and writes up to 4 bullets. The judge (GPT-6 Luna, v5c-chat) checks each readout against the model's own reply.

Every case can be opened on the page: `https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#<k>`, where `k = <item>.L<layer>.p<pos>`.

**Terms**
- **Settings**: Original = lens sample #0 capped to 4 bullets; Best of 32 = the complete sample with the highest joint FVE; Combine 32 = bullets pooled from the 32 samples by FVE gain.
- **Wrong bullet**: a bullet that overlaps a span the judge verified as wrong.
- **READ**: the read site. The reply text before READ is context the activation could carry; the text after it is what the model goes on to write.
- **rec_32**: in how many of the cell's 32 lens samples (full raw text) the wrong span's key words occur. **One-off** ≤ 2, **recurring** 3–15, **sticky** ≥ 16.
- **Brackets** are 95% chat-level bootstrap intervals.

## 0. Short answer

1. **Most "hallucinations" keep the gist.** In a representative sample of 240 wrong bullets, readers judged the bullet's main point right in 89% [84, 94]. The commonest pattern, about 63%, is one wrong slot: a name or entity (28%), an attribute or relation (23%), or a number (12%).
2. **About 43% [36, 52] change the meaning. 52% are minor details. About 21% [16, 27] are not real content errors**: the judge was too strict, the bullet is a reasonable continuation the reply happened not to take, or the error is cosmetic. This last group overlaps the first two; most of it was coded as minor.
3. **By the readers' coding, most serious errors are copy failures.** In 45% [37, 53] of wrong bullets the truth was in the prompt or in the reply before READ. Those cases hold 58 of the 90 meaning-changing errors. Part of this link comes from the coding itself: a contradiction with visible text is easier to rate as meaning-changing than an unsupported invention.
4. **Roughly a third to a half of wrong spans look like one-off sampling noise, and roughly 15–30% are sticky.** The split depends on the word-matching rule:
   - All key words in one sample (the primary rule): 47% one-off, 21% sticky.
   - Spans keyed on one novel name or number, where the rule does not matter: 37% one-off, 27% sticky.
   - A hand check found 9 of 30 sticky rows keyed on a word that is not the error.

   A majority vote over the 32 samples would remove 74–79% of wrong spans, but it also drops about half of the true claims (point 6).
5. **But a vote cannot restore a value the lens never outputs.** For name/number errors, the true value is in none of the 32 samples in 32–55% of cases (lenient–strict matching). Translation does not explain this: in 25 Chinese-heavy cases, the truth was written in Chinese only once.
6. **Recurrence separates grounded from ungrounded content, not true from invented.** True claims recur more than wrong spans with probability 0.70 (0.77 for names and numbers). Against unverifiable claims it is only 0.55. A vote keeps 47% of true claims and 25% of wrong spans. This is 25% rather than the 21% in point 4 because here the key words are chosen without looking at the reply. The gap holds when true claims are matched to wrong spans on number of key words (48% vs 25%).
7. **Selection has headroom. FVE shows no detectable use of it, but the test is small.** In 72 fully judged cells, a judge-clean sample existed in 54 (41 under a stricter reading of the judge). The top-FVE sample was clean in 24, against 23.8 for a random pick. The difference is +0.2 cells [−3.5, +4.6], so a large FVE effect is ruled out but a small one is not. In the full bank, Best of 32 lowers hallucinated readouts by 1.6 points [0.3, 3.0].
8. **In the pilot, avoidability depends on the chat much more than on the layer.** The hallucinated share of samples ranges from 8% to 84% across the 8 chats but only 51–58% across layers. Chat explains 47% of the cell-to-cell variance and layer 1%. Every dailydialog pilot cell had a clean sample, while 18 of 45 lmsys cells had none, but that is 3 chats against 5. Stickiness is 20–22% in every setting and layer. The settings draw on one shared 32-sample pool, so the setting comparison only shows that FVE selection does not prefer sticky errors.
9. **Bullet-level judge labels are noisy, in both directions.** When the same bullet text is in two readouts of a cell and one copy is WRONG, the other copy is also WRONG only 65% of the time; the labels differ in 52% of such pairs.
10. **Implication:** ranking more samples by FVE barely reduces hallucination. A correctness signal has room to help: in the pilot, 19–32 of the 46 hallucinated Original cells have a judge-clean alternative (23 if at least 3 clean samples are required). No such signal has been tested yet. The sticky errors whose true value never appears in the pool need a better lens read, not better selection.

## 1. What the errors are

**Sample.** There are 17,387 eligible wrong bullets over the three settings in 149 chats. 240 were drawn at random with at most 2 per chat (141 chats, 238 cells), and read in 20 batches of 12. Rates are weighted by 1/inclusion probability, so they estimate the full population; counts are raw. Records: `errors/records/rep_*.json`. Design: `errors/rep_sample.json`.

| Error type | n | Share [95% CI] | Gist right | Meaning-changing / minor / not an error | One-off / sticky (this sample) | One-off / sticky (all spans of this kind) |
|---|---|---|---|---|---|---|
| Wrong or invented name / entity | 57 | 28% [21, 36] | 86% | 35 / 22 / 0 | 44% / 22% | 49% / 20% (novel names) |
| Wrong attribute or relation | 55 | 23% [17, 30] | 91% | 28 / 27 / 0 | 41% / 29% | – |
| Plausible continuation the reply did not take | 35 | 13% [8, 19] | 96% | 3 / 30 / 2 | 50% / 22% | – |
| Wrong or invented number | 25 | 12% [6, 17] | 95% | 10 / 15 / 0 | 51% / 29% | 44% / 20% (novel numbers) |
| Not wrong: judge too strict | 19 | 6% [4, 10] | 100% | 0 / 7 / 12 | 38% / 44% | – |
| First-person / persona claim | 18 | 6% [3, 9] | 78% | 7 / 11 / 0 | 37% / 9% | 54% / 17% (first person) |
| Over-specific elaboration of a true gist | 16 | 6% [3, 9] | 100% | 0 / 16 / 0 | 63% / 26% | – |
| Polarity or negation flip | 7 | 3% [1, 6] | 40% | 6 / 1 / 0 | 52% / 9% | 42% / 30% (negation) |
| Misread prompt; content from elsewhere in the chat; other | 8 | 3% | 7 of 8 | 1 / 7 / 0 | – | – |

- "Minor" includes cosmetic. "One-off / sticky (this sample)" uses the most persistent wrong span in each bullet. The last column covers all 19,431 verified wrong-span rows of that kind (`recurrence_summary.json`).
- 17 of the 18 persona claims come from dailydialog. Meaning-changing errors look more common in lmsys, 50% [39, 60] against 32% [22, 41], but the intervals overlap.
- **By setting:** the gist is right in 88% (Original), 95% (Best of 32) and 84% (Combine 32). Meaning-changing errors are 38% / 38% / 53%. These are tentative, with n ≈ 80 each.

**Where the truth was** (readers' call, weighted):
- In context (prompt or reply before READ): 45% [37, 53]. 58 of these 106 bullets change the meaning.
- An invented specific with no counterpart in the reply: 35% [28, 42]. 23 of 83 change the meaning.
- Only after READ, so arguably not in the activation: 15% [10, 21]. 9 of 39 change the meaning.
- Unclear or not an error: 5%.

So, by the readers' coding, the errors that matter are mostly ones where the right value was in the text, and the lens often keeps the category and loses the identity. Two caveats:
- The readers chose both the severity and the "where the truth was" code, and they could see pool counts while coding, so the two codes are not independent.
- Not every featured case is a missing value. In chat-lmsys-0043.L60.p391, the right 2-position group, "propyl", is in 17 of 32 samples (see below).

### Examples (verbatim; truth quoted from the prompt or reply; counts are samples of 32)

**Wrong or invented name / entity**
- Combine 32, b1, [chat-dailydialog-0045.L20.p65](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0045.L20.p65): `（or context of speaking to "Alice"), and no knowledge of any "rules" imposed by someone named "Pat."`
  - Prompt: "Hey, Mary, can you cut that out?" Reply just before READ: `I don't have any context about a conversation with "Mary,"`
  - "Mary" is in 0/32 samples, "Sarah" in 32/32, "Alice" in 2/32. A vote would drop Alice and keep Sarah.
- Best of 32, b2, [chat-lmsys-0070.L52.p82](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0070.L52.p82): `坐落于 the vibrant commercial hub of Guangdong Province.`
  - Prompt address: "Wuhou Chengdu,Sichuan,China".
  - "Sichuan" and "Chengdu" are in 0/32 samples, "Province" in 29/32.
- Combine 32, b2, [chat-lmsys-0023.L20.p464](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0023.L20.p464): `Some critics argue U-Net struggles with very small objects.`
  - Prompt: "Do you know DETR model?" Reply after READ: "Performance on small objects was initially weak."
  - "U-Net" is in 32/32 samples, "ResNet" in 24/32, "DETR" in 0/32.

**Wrong attribute or relation** (right category, wrong identity)
- Best of 32, b0, [chat-lmsys-0071.L36.p88](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0071.L36.p88): `Morning dew on tea leaves,`
  - Prompt: "Write me three haikus about the pleasure of a morning coffee." Before READ: "Dark roast fills the air,"
  - "tea" is in 28/32 samples, "coffee" in 4/32.
- Combine 32, b0, [chat-lmsys-0043.L60.p391](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0043.L60.p391): `It is substituted at the 5-position with an ethyl group and the 2-position with a nitro group.`
  - Prompt: "2-PROPYL-PYRIMIDINE-5-CARBALDEHYDE".
  - "ethyl" is in 24/32 samples and "formyl" in 0/32. But the right 2-position group, "propyl", is in 17/32 as a whole word, e.g. sample #1: "At position 2, it is substituted with a propyl group".
  - So this is mostly a binding error: groups are attached to the wrong positions. It is not a value the lens never outputs.
- Best of 32, b1, [chat-lmsys-0011.L44.p120](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0011.L44.p120): `treating language modeling as a sequence-to-sequence problem`
  - Prompt title: "Decision Transformer: Reinforcement Learning via Sequence Modeling".
  - "language model" is in 32/32 samples, "reinforcement" in 0/32.

**Wrong or invented number**
- Best of 32, b3, [chat-dailydialog-0019.L36.p134](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0019.L36.p134): `The World Health Organization (WHO) reported ~84 years in recent years.`
  - Before READ: "approximately **78 to 79 years**".
  - "84" is in 1/32 samples and "78" in 30/32, so a vote fixes this one.
- Best of 32, b0, [chat-lmsys-0040.L36.p65](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0040.L36.p65): `. Rainfall: Rare, 100mm`
  - After READ: "- Rain: 250 Mm".
  - "250" is in 2/32 samples ("Rain: Rainfall 250mm", "Rainfall: ~250mm"), while "100mm" is in 10/32. The row template is read, but the value is mostly guessed.
  - An earlier version said 0/32; the count regex `\b250\b` could not match "250mm".
- Best of 32, b2, [chat-lmsys-0052.L36.p209](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0052.L36.p209): `At $100^\circ\text{C}$, it reaches approximately **1,126 g/100`
  - The reply says "approximately **118 to 120 grams per 100 mL**".
  - "118" is in 0/32 samples.

**Plausible continuation the reply did not take** (the judge's own rule says these should count as consistent)
- Combine 32, b1, [chat-dailydialog-0004.L44.p33](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0004.L44.p33): `I was just tied up with a few meetings.`
  - Before READ: "Hi! Sorry to keep you waiting." After READ: "I was just stepping out for a moment."
- Combine 32, b2, [chat-dailydialog-0060.L60.p36](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0060.L60.p36): `刚 picked them up today and they're feeling great.`
  - After READ: "Just picked them up yesterday".
  - "today" is in 27/32 samples, "yesterday" in 15/32.
- Best of 32, b0, [chat-lmsys-0061.L60.p411](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0061.L60.p411): `3: Understand and Manage Your Energy`
  - The intro had promised "energy, focus, and priorities", but section 3 is `Master the Art of Saying "No"`.
  - Original's `3: Manage Your Energy` was judged clean.

**First-person / persona claim**
- Original, b3, [chat-dailydialog-0026.L60.p21](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0026.L60.p21): `I'm an AI assistant, and my internal clock is synced to real-time. I don't sleep, so I know exactly what time it is!`
  - After READ: "To give you an accurate answer, I would need to know your current location."
- Original, b3, [chat-dailydialog-0032.L20.p65](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0032.L20.p65): `Here are a few ways I’m enjoying the vibes! 😄`
  - Before READ: `I can’t "like" music in the emotional way humans do`.
- Combine 32, b1, [chat-dailydialog-0025.L60.p30](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0025.L60.p30): `I have been keeping busy,` is stock small-talk filler.

**Over-specific elaboration of a true gist**
- Original, b3, [chat-lmsys-0047.L44.p195](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0047.L44.p195): `It explicitly calls out the child's age, daily schedule constraints, and dietary restrictions.`
  - The reply has "nap times, ease of movement, hygiene, gear" and no diet.
- Best of 32, b3, [chat-lmsys-0034.L60.p117](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0034.L60.p117): `their closed nature makes them statically indeterminate and resistant to local buckling.`

**Polarity or negation flip** (rare, but the gist is usually wrong)
- Best of 32, b2, [chat-lmsys-0002.L44.p47](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0002.L44.p47): `I can, however, write in a harsh, aggressive, or explicit manner if you'd like.`
  - The reply offers "a lighthearted, clean joke".
- Original, b3, [chat-lmsys-0014.L20.p419](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0014.L20.p419): `而RLC AM没有去重功能` ("RLC AM has no duplicate removal").
  - Just before READ, the reply lists "- Duplicate detection (for AM mode),".

**Other small types**
- Misread prompt, Original, [chat-dailydialog-0045.L60.p63](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0045.L60.p63): `or any prior conversation about cutting my hair`
  - The prompt says "cut that out". "hair" is in 31/32 samples.
- Content from elsewhere in the chat, Best of 32, [chat-dailydialog-0015.L20.p195](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0015.L20.p195): `Boil water with cloves or vinegar on the stove.`
  - Vinegar belongs to an earlier item.

## 2. How hard they are to avoid

### 2.1 Recurrence across the 32 samples (all 19,431 verified wrong spans)

The overall split is 47% one-off, 32% recurring and 21% sticky. A majority vote (drop anything in fewer than 16 of 32 samples) removes 79% [77, 81].

That figure depends on how strictly the span's key words must match:
- All key words in the same sample (the primary rule): 79% removed.
- 2 of them: 74% removed.
- Any one: 55% removed.

**The one-off / sticky split itself depends on the rule.** A span has 1–3 key words, and the primary rule needs all of them in the same sample. Spans with more key words therefore look rarer (`errors/skeptic_checks.json`):

| Rule or subset | n | One-off | Sticky |
|---|---|---|---|
| All key words (primary) | 19,431 | 47% | 21% |
| 2 of the key words | 19,431 | 36% | 26% |
| Any one key word | 19,431 | 20% | 45% |
| Spans with 1 / 2 / 3 key words (primary) | 9,357 / 4,762 / 5,312 | 32 / 50 / 70% | 31 / 16 / 7% |
| One novel name or number (rule does not matter) | 5,515 | 37% | 27% |
| Without reply-word or common-word keys | 16,207 | 54% | 15% |

Hand check of 60 random rows (first copy per cell):
- **Sticky rows (30):** 9 are keyed on a word that does not carry the error, and 2 are partly keyed.
  - `This is why it’s called the "Singularity."` ([chat-lmsys-0024.L36.p253](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0024.L36.p253)) is sticky through "called" (23/32).
  - `Enter Resistance (Ohms): 10` ([chat-lmsys-0033.L52.p350](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0033.L52.p350)) is sticky through "10" (30/32). The error is "Resistance".
- **One-off rows (30):** 3 are one-off only because a rare second word is required, while the wrong word itself is in at least 16 of 32 samples. About 8 more have their main wrong word in 3–15 samples.
  - `The "2-" indicates a methyl group at the second carbon,` ([chat-lmsys-0043.L44.p391](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0043.L44.p391)) has rec_32 = 1, but "methyl" is in 30/32.
  - `Use the timer app to enforce breaks.` ([chat-lmsys-0061.L20.p327](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0061.L20.p327)): "timer" is in 21/32.

So the errors are misgraded in both directions. A fair summary is "roughly a third to a half one-off, roughly 15–30% sticky", not exact shares. The comparisons below stay valid where they are made within the same rule. For example, the true-vs-wrong tests in section 2.3 are stratified by number of key words.

| Slice | Sticky (≥16/32) |
|---|---|
| Original / Best of 32 / Combine 32 | 21.3% / 21.7% / 19.7% |
| L20 / L36 / L44 / L52 / L60 | 19.9 / 20.6 / 21.8 / 20.4 / 21.7% |
| dailydialog / lmsys | 21.7% / 20.4% |
| First-person / names / numbers / negation | 16.8% / 20.1% / 19.5% / 29.6% |

**One-offs are noise local to one sample.**
- 78% appear only in the sample they came from.
- Only 3% show up in the same setting's readout at another layer.
- Example: `Sichuan Yujiang Fine Chemical Co., Ltd.` in Original, [chat-lmsys-0070.L52.p154](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0070.L52.p154), is in 1/32 samples.

**Sticky errors follow you across layers and settings.**
- 67% also appear in the same setting's readout at another layer, and 92% in some other layer's pool. This is not just common words: for chat-specific names and numbers (key word in at most 2 other chats), it is 62% (n = 540).
- 27% have a key word that is in ≥25% of other chats' pools. Some are lens priors. Others are common words that do not carry the error, such as "called" in chat-lmsys-0024.L36.p253 or "making" in `making the planet uninhabitable` ([chat-dailydialog-0070.L20.p203](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0070.L20.p203)). Example: `we do have a partner.` in Original, [chat-dailydialog-0000.L20.p55](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0000.L20.p55): 29/32 samples, and present in 60 other chats.
- 34% are specific to the chat. Example: `Monty Python** asking this question!` in Best of 32, [chat-dailydialog-0030.L44.p65](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0030.L44.p65): the reply says Douglas Adams; 32/32 samples here, in no other chat.
- Relation or polarity errors built only from reply words are 67% sticky. Example: `not Qwen` in Original, [chat-dailydialog-0002.L20.p32](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0002.L20.p32): "Qwen" is in every sample, so the word-level grade calls it sticky and cannot flag it. The phrase "not Qwen" itself is in only 2/32 samples, so a vote on phrases rather than words could catch it.

### 2.2 Is the right value even in the pool? (new check)

The grade above measures how often the *wrong* word recurs. For substitution errors that understates how hard they are: "Alice" is a one-off, but "Mary" is in 0/32 samples.

**Method.**
- For each unique name/number wrong span, I took the names and numbers the judge's own reason cites that are in the prompt or reply but not in the span. For example, "The response refers to Mary, not Alice." gives "Mary".
- I then counted the cell's samples that contain them, anywhere and in any role.
- Coverage: 4,472 of 7,698 spans. Lenient = any truth token; strict = all truth tokens in one sample; the real value lies between the two.
- Hand check of 60 random rows: the tokens named the right value in about 50. The other ~10 were generic tokens, such as "pm" or "3" from "3D".
- Script: `errors/errors_synth.py`; numbers in `errors_stats.json` → `truth_in_pool`.
- **Translation check** (skeptic pass, `skeptic_checks.json` → `4_truth_in_pool_translation`). Truth tokens are Latin-script words and digits, so a truth the lens wrote in Chinese would count as absent.
  - For names, truth-in-0 is higher when the pool is mostly Chinese (39% vs 28%). Numbers show no such gap (23% vs 22%).
  - In 25 random Chinese-heavy truth-in-0 name cases, the truth appeared in Chinese once. In [chat-lmsys-0025.L52.p236](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0025.L52.p236), "上海" (Shanghai) is in 5/32 samples, always as the city part of an invented company name (e.g. "上海捷诺"). The company name Huihe never appears.
  - 3 cases had junk truth tokens: "Antwort" from a German reason, "PC" and "IP".
  - So translation is a small effect. The gap more likely means that Chinese-heavy pools are worse reads.

| Name/number errors | Truth in 0 of 32 | Truth in ≥16 of 32 | Truth more frequent than the wrong value |
|---|---|---|---|
| All (n = 4,472) | 32–55% (CIs 26–38 / 48–62) | 18–32% | 27–47% |
| Truth visible before READ (n = 3,402) | 36–56% | 18–30% | 27–44% |
| Truth only after READ (n = 704) | 28–46% | 21–31% | 33–46% |
| Names / numbers | 35–58% / 22–46% | 17–31% / 20–37% | 26–46% / 30–51% |

- For these errors, the true value is visible before READ in 76–84%.
- So in about a quarter to a half of all slot errors (27–48%), the right value is in context but not in any of the 32 samples. Within the errors whose value is visible before READ, the share is 33–57%. Both figures count a value as visible if any of its truth tokens is; the table row above requires all of them.
- No choice among those samples (Best of 32, Combine 32 or a vote) can produce the right value.

In the 240-bullet sample, meaning-changing errors with an identifiable truth have it in 0/32 samples in 25 of 35 cases, against 11 of 40 for minor errors and non-errors. These counts use lenient matching and, per bullet, the wrong span whose truth is rarest in the pool. The sticky shares use the most persistent span per bullet: by the lexical grade, meaning-changing errors are not stickier (22% vs 27% for minor errors and non-errors). The difference is in whether the lens ever reads the truth, not in how often it repeats the wrong word. This split is suggestive only:
- the n is small (35 and 40 bullets);
- the readers who coded severity could see pool counts, such as "Mary" in 0/32, so part of the association may come from the coding.

### 2.3 Can consensus tell true from false?

The measure is P(a true element recurs more than a wrong span's element). Elements are chosen without looking at the reply, so a deployable filter could use them, and the comparison is stratified by number of elements.

| Comparison | P | Majority vote keeps |
|---|---|---|
| True claims vs wrong spans | 0.70 [0.68, 0.71] | 47% of true, 25% of wrong |
| Names and numbers only | 0.77 [0.74, 0.79] | 73% of true, 30% of wrong (68% of true after matching on number of key words) |
| Clean bullets vs wrong spans | 0.62 [0.60, 0.63] | – |
| Unverifiable claims vs wrong spans | 0.55 [0.53, 0.56] | – |
| Fully judged pilot (72 cells, no selection step), true vs wrong | 0.76 [0.67, 0.82] | 50% of true, 20% of wrong |

- Recurrence mostly separates content grounded in the reply from content that is not there.
- It does not separate wrong content from invented content that the judge did not flag (0.55).
- A vote is a precision filter that costs about half the true content. It is worth it mainly for names and numbers.
- The vote keeps 25% of wrong spans here, against 21% in section 2.1, because these key words are chosen without looking at the reply.

### 2.4 Fully judged cells: was a clean readout available?

The development pilot has 72 cells (8 chats x 3 sites x L20/44/60), and every one of the 32 samples was judged.
- It uses the same judge, prompt and verifier as the page. Re-checked in the skeptic pass against the two `project_contract.json` files:
  - same model (gpt-6-luna) and reasoning (none);
  - same prompt v5c-chat and verifier v5c-chat-verify-v1;
  - same benchmark commit 92d763e and identical judge/prompt/score source hashes;
  - only concurrency, layers and the allow-missing flag differ.
- Its sample texts equal the full-grid pool (2,304/2,304; same global pool id).
- Sample 0 reproduces Original in 72/72 cells, and the FVE winner reproduces Best of 32 in 72/72.
- **Not a representative sample.** The 8 chats and 3 sites per chat were picked by a fixed rule (first/middle/last sites) that never looked at readouts or the judge. But the pilot is harder than the bank: Original hallucinates in 46/71 specific readouts, against 2,641/5,554 (48%) bank-wide.
- Each pilot interval is a bootstrap over only 8 chats, so treat it as rough.

| | Judge at face value | Strict |
|---|---|---|
| Cells with a judge-clean sample | 54/72 (75% [53, 93]) | 41/72 |
| Easy / mixed / hard / unavoidable cells | 20 / 17 / 17 / 18 | 18 / 15 / 8 / 31 |
| Original hallucinated | 46/72 (64%) | |
| Best of 32 (top FVE) hallucinated | 39/72 (54%) | |
| A random sample hallucinated | 56% [38, 71] | |
| Perfect picker: hallucinated | 6/72 (8%) | |
| Original-hallucinated cells a perfect picker could make clean | 32/46 (70% [44, 91]) | 19/46 (41%) |
| ... that Best of 32 made clean | 8/46 | |

- **Strict** drops "clean" samples that contain, verbatim, a wrong span the judge flagged in another sample of the same cell (133 of 762 clean samples).
  - Strict inherits the judge's false flags. 37 of the 133 rest on "does not say X" flags, which the judge prompt says not to mark ("absence is not wrongness"). For example, `It's a pleasure to see you.` (flagged in pilot sample #6, and present in "clean" samples #9, #14, #18, #27 and #29) in [chat-dailydialog-0002.L20.p20](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0002.L20.p20) was flagged because the reply "does not express pleasure at seeing the user".
  - None of the 13 cells that lose their clean sample under strict depend only on such flags, so the 41/72 figure stands.
- **Single-sample rescues are fragile.** Of the 32 Original-hallucinated cells with a clean sample, 9 have only 1 or 2 clean samples out of 32, so one judge miss could create the rescue. Requiring at least 3 clean samples leaves 23/46; strict with at least 3 leaves 12/46.
- **Cell classes:** unavoidable = no clean sample; hard = 24 or more of 32 hallucinated; easy = more than 16 of 32 clean; mixed = the rest.
- **FVE shows no detectable signal here, but the test is small.**
  - The top-FVE sample is clean in 24 cells, against 23.8 expected from a random pick. The difference is +0.2 cells, 95% chat bootstrap [−3.5, +4.6].
  - The within-cell chance that a clean sample outranks a hallucinated one on FVE is 0.53 [0.49, 0.58]; project doc 012 also reports .533.
  - The best clean sample's median FVE rank is 2, against 2.8 if FVE were random, and in 8 cells it ranks below 10th.
  - So the pilot rules out a large FVE benefit, not a small one. The full bank does show a small one (Best of 32 −1.6 points; section 4).
- **In the full bank,** Best of 32 or Combine 32 is consistent in 37% of the cells where Original hallucinates. Some of that is judge noise (section 3).
- **By source:** all 27 dailydialog cells have a clean sample (21 strict), against 27 of 45 lmsys cells. That is only 3 dailydialog chats against 5 lmsys chats, so treat the source contrast as anecdotal. One chat, sodium nitrite solubility, has no clean sample in 8 of its 9 cells.
- **By layer:** a clean sample exists in 18/24 cells at L20, 16/24 at L44 and 20/24 at L60. Best of 32 is clean in 5, 9 and 10 cells.
- **Chat vs layer:**
  - The share of hallucinated samples ranges from 8% (chat-dailydialog-0047) to 84% (chat-lmsys-0023) across chats, but only 51–58% across layers.
  - Chat explains 47% of the cell-to-cell variance and layer 1%.
- **Error kinds by cell class:**
  - In easy cells, 104 of 153 wrong spans (68%) are singletons that no other sample repeats.
  - In hard and unavoidable cells only about 30% are singletons, and 515/1,152 and 691/1,621 recur in 4 or more other samples.

Cell examples:
- **Easy**, [chat-dailydialog-0047.L20.p182](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0047.L20.p182).
  - Original (sample #0) adds `it's an anxiety disorder`, while 29 of 32 samples are clean.
  - Best of 32 picks clean sample #2. This is pure sampling noise.
- **Hard (unavoidable under the strict reading)**, [chat-dailydialog-0002.L44.p20](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0002.L44.p20). The prompt is "Good morning, Miss Li." and 30 of 32 samples are hallucinated.
  - Sample #14: `Although "Miss Lin" is a`, `I'm not Mrs. Zhang`, `How can I help you today, Alice?`
  - The two "clean" samples make the same kind of swap. Sample #12 has `I'm not Ms. Liu` and `not Miss Sarah`; sample #16 has `Although I'm not Miss Wang` and `I'm not Miss Zhang`.
  - Each contains a span the judge flagged wrong in another sample: "Miss Sarah" (flagged in #9) and "Although I'm not Miss Wang" (flagged in #2). So the strict reading drops both and counts this cell as unavoidable.
- **Unavoidable**:
  - [chat-lmsys-0025.L60.p80](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0025.L60.p80): `Ltd., stands as a premier entity nestled in the heart of Zhengzhou,`. The reply has Shanghai, which is also in the prompt; all 32 samples are hallucinated.
    - "Shanghai" is in 0/32 samples. "Zhengzhou" is in 17/32; the rest name other cities such as Guiyang, Changsha, Wuhan, Liuzhou or Hefei.
  - [chat-lmsys-0052.L44.p428](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0052.L44.p428): `is approximately **160 grams per liter**.` against the reply's "118 – 120 grams per 100 mL". The reply had already written "approximately **118 to 120 grams per 100 mL**" before READ.
    - The samples give scattered values, mostly in grams per liter, and some recur: "160 grams per liter" is in 4/32 samples. None gives 118–120 per 100 mL.

### 2.5 What this implies for resampling, consensus and selection

- **A third to a half of the wrong spans are one-offs (section 2.1), but fewer cells can be fixed by choosing a different sample.** In the pilot, 836 of the 1,246 singleton spans sit in hard or unavoidable cells, where the other samples carry other errors. A clean sample exists for 32 of the 46 Original-hallucinated cells: 23 if at least 3 clean samples are required, 19 strict. Where it exists, it is usually already among the 32, so the bottleneck is the selector, not the number of samples.
- **Consensus can serve as that selector for names and numbers** (0.77), at the cost of a quarter of the true names and numbers. For general content it barely beats chance against invented-but-unflagged material.
- **A quarter (18/72) to over two-fifths (31/72, strict) of the pilot cells, and the sticky fifth of spans, are not avoidable by any choice we control:**
  - The error recurs across samples, layers and settings.
  - For a third to a half of slot errors, the right value is never in the pool, even though it is usually in context.
  - Here the lens reads the frame and the category ("a province", "a morning drink", "a vision model") but not the identity. More samples at the same site will mostly repeat the wrong filler.
- **Untested idea:** by the readers' coding, most severe errors are copy failures of values visible in context. A check of names and numbers against the prompt and the reply before READ could flag them, e.g. Sarah vs Mary or Guangdong vs Sichuan. It cannot supply the right value, and it would only work when the true value appears in context.

## 3. Judge noise

**How many "errors" are not errors.** In the representative sample, about 21% [16, 27] of judge-verified wrong bullets are not content errors:
- judge too strict: 6% [4, 10];
- a reasonable continuation of the text before READ that the reply did not take: 13% [8, 19]. The judge's rule says these count as consistent.
- cosmetic or no error: the remainder.

By the readers' severity code, this 21% splits as follows: about 12 points minor details, 4 points cosmetic, 4 points "not an error", and 1 point (3 bullets) still meaning-changing. So it overlaps the "minor" share in section 1. The readers are not ground truth: they saw the judge's reason and the pool counts. The judge prompt does confirm the continuation rule. It says "Do NOT mark … a prediction of what comes next that is a reasonable continuation of the text before the marker, even when the response actually went a different way."

The earlier stratified reading (`reading/REPORT.md`) found 63 of 192 judge-WRONG bullets with no error (33%), but that sample over-represents unusual strata.

**Replication of bullet-level WRONG labels**
- **Identical bullet text in two readouts of a cell, one copy WRONG:** the labels differ in 52% [49, 55] of 2,019 pairs. Counted per WRONG copy, the twin is also WRONG 65% of the time.
- **Test–retest** (Original vs Raw differing only in whitespace, 119 cells): a WRONG verdict repeats 79% [67, 87].
- **Fully judged pilot, exact wrong-span text (8+ chars) present in another sample of the same cell:** flagged wrong again in 2,914 of 4,332 cases (67%). A hand read of 24 unflagged cases found 19 to be the same claim in the same role.
- **Pilot, names/numbers in 2 or more samples:** 150 of 403 are flagged in some samples and unflagged in others.
- **Pilot, any element of a wrong span appearing in another judged sample:** judged wrong there 51% of the time. The main data agrees: about 50% when the element appears in another setting's readout with different text.
- **Pilot, "clean" samples:** 133 of 762 contain verbatim a span the judge flagged in another sample of the same cell.

**Examples**
- [chat-lmsys-0057.L44.p21](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0057.L44.p21): the same sample-#19 bullet `Pas de grands projets chez moi, mais ça roule bien ! 😊 Et vous, comment allez-vous` is WRONG in Best of 32 (b1) and clean in Combine 32 (b1).
- [chat-dailydialog-0028.L20.p217](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0028.L20.p217): `（Was it minor gossip or deep insults?） And how close was it to your core relationships?` is WRONG in Best of 32 (b3) and clean in Combine 32 (b3).
- [chat-dailydialog-0014.L20.p30](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0014.L20.p30): `而不是 Bill! I'm actually Qwen,`
  - It is WRONG in Best of 32. The reason given: "It describes text after the marker as already written".
  - The same text is clean in Combine 32, where `而不是 Microsoft (though "Sam" is a common nickname for my creator)` is also left clean.
- [chat-lmsys-0008.L60.p111](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0008.L60.p111): `The **RIB** contains routing information learned from various sources.` is flagged because "its context before the marker has not yet stated that". The reply after READ says exactly that.
- [chat-lmsys-0061.L60.p411](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0061.L60.p411): `3: Manage Your Energy` is clean in Original. The Raw reference flags `- 3: Manage Your Energy` as wrong. Raw has the same four bullets plus a fifth that the cap removed (`- 4. Manage Your Energy (Not Just Your Time)`), so this is not one of the whitespace-only test–retest cells.
- Original, b2, [chat-dailydialog-0015.L44.p113](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0015.L44.p113): span `白 vinegar` is flagged because "The response says white vinegar, not 白 vinegar". That is a language switch, not a content error. The same bullet also has a real error (`can absorb stubborn pet odors.`; the reply is about tobacco smell), so the bullet stays WRONG.

**Consequence.**
- By the readers' reading, about a fifth of judge-flagged wrong bullets are not content errors, and about 4 points of that fifth are cosmetic slips.
- The judge also misses errors. 133 of 762 "clean" pilot samples contain a span flagged elsewhere, and the earlier reading found 8 of 72 missed errors. So judge noise does not simply inflate error counts, and its net effect on readout-level rates is unknown.
- An exact repeat of a WRONG bullet or span is flagged again only about two-thirds of the time: 65% for identical bullets and 67% for exact spans in the pilot. A repeated key word in different text is judged wrong again about half the time.
- Readout-level rates are steadier: in the test–retest, the readout-level hallucination flag agrees in 87% of cells.
- Any per-bullet analysis is capped by this noise, including the FVE-vs-wrong pair rates (about 0.50). The cap is real, but section 4 shows that noise alone does not explain the null.

## 4. What this means for FVE and more sampling

- **FVE sees little of the error.**
  - Within a readout, clean beats wrong 50–51% of the time (0.53–0.58 after matching length or using verified-true bullets; `reading/REPORT.md`).
  - Across whole samples in the pilot, the top-FVE sample is clean as often as a random one (24 vs 23.8 of 72; difference +0.2 cells [−3.5, +4.6]). This rules out a large effect, not a small one.
  - Likely mechanism (not tested directly): wrong bullets usually keep the frame and change one slot, and FVE follows the frame. "Province" is read; "Sichuan" is not.
- **Best of 32 and Combine 32 mostly change which filler you see, and barely change the error rate.** In the full bank, Best of 32 nets −1.6 points of hallucinated readouts [−3.0, −0.3], and Combine 32 −0.4 [−1.7, +1.1]. In the 240-bullet sample, the error kinds and severities do not clearly differ by setting (meaning-changing 38% / 38% / 53%, with overlapping intervals).
- **More sampling helps only together with a correctness signal**, and only for the non-sticky part, which is roughly a third to a half of the spans by the lexical grade (section 2.1). A clean sample is already among the 32 in 54/72 pilot cells (41 strict; 44 with at least 3 clean samples). A signal that is not FVE is needed to pick it: cross-sample agreement on names and numbers, a check against values in context, or a repeated-vote judge.
- **For the sticky part, more samples of the same lens at the same site do not help.** Changing layer or setting does not help either: 67% of sticky spans are in another layer's readout, and stickiness is flat across L20–L60. Fixing these needs a lens that reads the specific value: Mary not Sarah, DETR not U-Net, coffee not tea.
- **Before training or selecting against these labels,** re-judge with repeated votes and fix the continuation rule and the language-switch flags. By the readers' estimate, about 1 in 5 targets would change.

## 5. Caveats

- **Exploratory throughout.** All chats were inspected before this analysis, and there is no multiple-testing correction.
- **The 240 categories come from 20 independent readers.** They were not calibrated against each other, and readers saw recurrence counts while coding. Small types (n < 20) have wide intervals.
- **The recurrence grades are lexical.** They use the span's rarest words, not its meaning, so they understate substitution errors (section 2.2). They also misgrade in both directions (section 2.1 hand check): sticky through a common word, or one-off because a rare second word is required. The one-off and sticky shares are therefore ranges, not point estimates.
- **The three settings share one 32-sample pool.** Recurrence is measured against that same pool for every setting, so the setting comparisons are not independent. 5.7% of wrong-span rows repeat the same span from another setting's readout of the same cell, and the representative sample counts a bullet once per readout it appears in.
- **The truth-in-pool check relies on the judge's own reasons.** It covers 58% of name/number spans and its token extraction is imperfect (about 50 of 60 right by hand), hence the lenient–strict ranges.
- **The pilot is small:** 8 development chats, so the intervals are wide (e.g. 54/72 [53–93%]). With only 8 clusters, even those bootstrap intervals are approximate.
  - Its chats hallucinate more than the bank average (Original 46/71 specific readouts, against 48% bank-wide).
  - Its Original verdicts are the same cached judge calls as sample 0, so they are not an independent repeat.
  - "Clean available" is judge-optimistic: 9 of the 32 rescues rest on 1–2 clean samples.
- **One judge model is used throughout.** Section 3 shows its bullet labels are noisy in both directions, and every rate here inherits that noise.

## 6. Skeptic pass (2026-10-15): what was checked and what changed

Checks are in `errors/skeptic_checks.py`, with output in `errors/skeptic_checks.json`. The pre-pass versions are `ERRORS.pre-skeptic.bak.md` and `errors_page.pre-skeptic.bak.json`. A parallel edit made at the same time (`ERRORS.md.bak` is its starting point) was kept and merged.

**Held up:**
- The pilot uses the same judge pins and sample pool as the page.
- The true-vs-wrong recurrence gap survives matching on number of key words (vote keeps 48% vs 25%).
- Sticky spans persist across layers even for chat-specific names and numbers (62%).
- Translation explains little of the truth-in-pool result (1 of 25).
- Chat matters far more than layer in the pilot.
- The representative-sample weights are correct.
- The judge prompt confirms the continuation rule.
- The strict reading does not rest only on "absence" flags.

**Corrected or softened:**
1. **One-off / sticky shares** (points 4 and 10, section 2.1): from "about half noise, a fifth sticky" to ranges (one-off 20–54%, sticky 15–45% across rules; 37/27% for single name/number spans). Added the rule-sensitivity table and the hand check.
2. **Featured example** chat-lmsys-0040.L36.p65: "250" is in 2/32 samples, not 0/32 (a regex miss on "250mm").
3. **Featured example** chat-lmsys-0043.L60.p391: added that the true "propyl" is in 17/32 samples, so this is a binding error rather than a value never output.
4. **FVE** (points 7 and 10, sections 2.4 and 4): from "carries no information" / "will not reduce hallucination" to "no detectable signal in a small test". Added the CI (+0.2 cells [−3.5, +4.6]; AUC 0.53 [0.49, 0.58]) and the full-bank −1.6-point gain.
5. **Perfect-picker headroom:** added the robustness levels (32 → 23 with ≥3 clean samples → 19 strict → 12 strict with ≥3). Replaced "fix about half the errors" with "19–32 of 46 pilot cells, no signal tested yet".
6. **Avoidability by chat** (point 8): restricted to the pilot, added the variance split, called the dailydialog/lmsys contrast anecdotal (3 vs 5 chats), and noted that settings share one pool.
7. **Copy failures** (point 3, section 1): marked as the readers' coding, partly built into how severity is coded. Noted that readers saw pool counts (also for the 25/35 vs 11/40 split in section 2.2).
8. **Judge noise** (point 9, section 3): leads with the per-copy 65% re-flag rate. "A fifth are judge artifacts" now gives its cosmetic share and notes the judge also misses errors, so the net effect is unknown.
9. **Point 1:** "get one slot wrong" now applies to about 63% (name, attribute, number), not to most.
10. **Section 2.1:** "27% lens priors" now says some are common words that do not carry the error.
11. **Section 2.4:** added the pilot's site-selection rule, its higher hallucination rate, the 8-cluster bootstrap caveat, and the strict rule's inherited false flags.

## Files (all in `${OLENS_SCRATCH}/olens-bullet-fve/errors/`)
- `errors_page.json`: compact page data. It contains summary points, the type table with verified examples, recurrence, avoidability and judge noise, plus all 240 cases.
- `errors_stats.json`, `errors_synth.py`: weighted mixes, bootstrap CIs and the truth-in-pool check.
- `build_errors_page.py`: builds the page JSON. It asserts that every example quote is verbatim in the bullet and every truth quote is verbatim in the prompt or reply, and recomputes the pool counts.
- `recurrence_summary.json` / `recurrence.py`, `avoidability.json` / `avoidability.py`: upstream analyses.
- `records/rep_*.json`: the 240 reader records. `rep_sample.json`: the sampling design.
- `skeptic_checks.py` / `skeptic_checks.json`: confound checks from section 6. `skeptic_patch.py` re-applies the section 6 text changes to `errors_page.json` after a rebuild.
