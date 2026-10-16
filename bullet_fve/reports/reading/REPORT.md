# Does low bullet FVE mark hallucination? Reading-study report

Everything here is exploratory. Setup: Qwen3.6-27B on WorkspaceBench "Hallucination (chat)". That is 149 chats and 5,615 read-site cells. Each cell has 3 lens settings, which gives 67,317 labelled bullets. On top of that, 288 cases were read by hand. Every case can be opened on the interactive page: https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3

**Terms used below** (each defined once)
- **Cell**: one read site, meaning one chat, one layer and one token position. Its key is `k = <item_id>.L<layer>.p<pos>`.
- **Readout**: the 4 or fewer bullets that one setting writes for a cell. There are three settings:
  - **Original**: the lens's first sample.
  - **Best of 32**: of 32 samples, the one with the highest joint FVE.
  - **Combine 32**: bullets pooled from all 32 samples, added greedily by FVE gain.
- **Judge labels** (one judge model, GPT-6 Luna):
  - **WRONG**: the bullet contradicts the model's reply or prompt, or they do not support it.
  - **OFF-TOPIC**: the bullet is unrelated junk.
  - **Clean**: anything else.
  - A readout is **hallucinated** if it holds any verified wrong span.
  - A **verified-true clean** bullet is a clean bullet whose stage-2 claims were all checked true. About 20% of clean bullets are verified-true.
- **Solo FVE**: how much of the activation one bullet explains on its own.
- **Shapley share**: the bullet's fair share of the readout's joint FVE.
- **Coef 0**: the bullet gets zero NNLS weight because its siblings already cover it, so it is redundant.
- **Pair rate**: the chance that a clean bullet scores higher than a wrong bullet in the same readout. 0.5 means no separation and 1.0 means perfect separation.
  - Original and Best of 32 use solo FVE adjusted for list position. Combine 32 uses raw solo FVE.
  - **Length-matched** pairs are pairs whose scored texts are within 20% of each other in length (25% where stated).
- **Brackets** are 95% chat-level bootstrap intervals (149 chats, 1,000 reps).
- **Reply**: the model's own answer. It is the ground truth.
- Values are given in the order Original / Best of 32 / Combine 32 unless a row says otherwise.

## 1. Bottom line

No. Low per-bullet FVE is not a usable marker of hallucination here.

Within a readout, a clean bullet beats a wrong bullet only 50–51% of the time. Wrong bullets are usually the longer ones, and longer bullets get more FVE. With length matched, the rate rises to 52–55%, and to about 58% against verified-true clean bullets. So there is at most a weak signal, far from a usable detector.

FVE rewards other things:
- longer bullets
- bullets later in the list
- English rather than Chinese
- bullets that are not redundant
- bullets whose opening matches the format or first words of what the reply says next

The typical hallucination keeps that frame and gets one detail wrong (a name, number or entity), and FVE barely notices. Only errors at the very start of a bullet, and off-topic junk, cost a little.

Best of 32 and Combine 32 raise FVE but barely change how often readouts are correct.

## 2. The numbers

**Does FVE separate wrong from clean?**

| Test | Original | Best of 32 | Combine 32 |
|---|---|---|---|
| Clean beats wrong, same readout (pair rate) | 0.511 [0.496, 0.527] | 0.504 [0.489, 0.521] | 0.503 [0.486, 0.519] |
| Same, length-matched (within 20%) | 0.546 [0.521, 0.573] | 0.523 [0.501, 0.551] | 0.528 [0.505, 0.552] |
| Wrong vs verified-true clean, unmatched | 0.510 [0.478, 0.541] | 0.493 [0.461, 0.524] | 0.527 [0.493, 0.563] |
| Wrong vs verified-true clean, length-matched (within 25%) | 0.579 [0.523, 0.637] | 0.531 [0.479, 0.585] | 0.579 [0.534, 0.627] |
| Error starts in the bullet's opening third | 0.527 [0.507, 0.548] | 0.528 [0.511, 0.547] | 0.533 [0.511, 0.554] |
| Error starts later in the bullet | 0.496 [0.475, 0.517] | 0.478 [0.453, 0.501] | 0.474 [0.450, 0.499] |
| Clean beats OFF-TOPIC | 0.547 [0.514, 0.583] | 0.529 [0.489, 0.566] | 0.552 [0.516, 0.588] |
| Effect of a WRONG label on solo FVE within a readout (with controls) | −0.003 (−0.04 SD) | −0.005 (−0.06 SD) | −0.002 (−0.03 SD) |
| Effect of an OFF-TOPIC label, same model | −0.014 (−0.20 SD) | −0.019 (−0.22 SD) | −0.011 (−0.18 SD) |
| Within-readout solo-FVE variance explained by the label | 0.03% | 0.03% | 0.07% |
| Lowest-share bullet is the wrong one (mixed readouts), vs chance | 43.6% vs 44.3% | 43.6% vs 45.4% | n/a |
| Readouts labelled hallucinated | 47.0% | 45.4% (−1.6 pts [−3.0, −0.3]) | 46.7% (−0.4 pts [−1.7, +1.1]) |
| Wrong bullets whose wrong text is entirely past the 32-token limit | 0.12% | 0.02% | 0.07% |

**What FVE tracks instead, and why that hides the small signal**

| Same-readout comparison | Original | Best of 32 | Combine 32 |
|---|---|---|---|
| Longer bullet scores higher (pair rate on solo) | 0.561 | 0.600 | 0.553 |
| Later bullet in the list scores higher | 0.546 | 0.577 | n/a |
| English bullet beats a mostly-Chinese bullet | 0.596 | 0.614 | 0.637 |
| Bullet without an unused list-number opener scores higher | 0.595 | 0.525 | 0.542 |
| Wrong bullet is longer than its clean sibling | 62.5% | 61.5% | 59.3% |
| Wrong bullet sits later than its clean sibling | 64.5% | 64.2% | 50.9% |
| Clean beats wrong when the wrong bullet is shorter | 0.559 | 0.557 | 0.559 |
| Clean beats wrong when the wrong bullet is longer | 0.482 | 0.471 | 0.464 |

How to read these tables:
- Wrong bullets are longer and later in the list, and both of those raise FVE. That cancels the small penalty for being wrong.
- Even the best slices stay near 0.55–0.58.
- With position and length controlled, the labels add only about 0.1% of within-readout variance.
- A rough correction for judge noise puts the true pair rate at about 0.53–0.55 at most.
- None of the text proxies is a strong driver. Length, script, overlap with the reply, list numbers and position together explain only 4–7.5% of within-readout solo-FVE variance.

## 3. What the readers found

The 288 records come from 7 strata:
- A: wrong bullets with high share (60)
- B: wrong bullets with low share (60)
- C: low-share clean bullets in hallucinated readouts (36)
- D: high-share clean bullets in consistent readouts (36)
- E: cells where the settings disagree (48)
- F: wrong text past the 32-token limit (24)
- G: off-topic bullets (24)

Readers could see the scores while writing their explanations. Skeptics then checked each claim against the full data. Each section below carries a status:
- **Holds**: the claim survived the checks.
- **Tentative**: the claim survived only in the narrower form given here.

### 3.1 FVE is at most a very weak marker of hallucination (tentative)

Low per-bullet FVE is not a usable marker:
- The raw within-readout pair rates are about 0.50.
- With length matched they are 0.52–0.55. Pooled over settings, clean wins 0.532 [0.518, 0.547] of the time.
- In the reading sample, wrong bullets with high and low share were real errors equally often (45/60 each). That design can only rule out differences of about 15 points or more.
- Slices separate weakly in both directions: Original L60 gives 0.544, and Combine invented names give 0.456. So "no difference anywhere" is too strong. "Too small to use" is accurate.

Examples:
- `这 is evident from the use of **all caps** and the repetitive, demanding structure of their query.` (Best of 32, L44, [chat-lmsys-0045.L44.p71](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0045.L44.p71))
  - This WRONG bullet is the top bullet (solo 0.356, 44.5% share).
  - The only clean bullet, `This is primarily indicated by the **all-caps usage** and the repetitive phrasing of the`, is lowest (solo 0.109).
  - The flagged span "repetitive, demanding structure" is itself a borderline call.
- `Check for electric bug zappers**: They can reduce numbers (though less effective than repellents).` (Original, L52, [chat-dailydialog-0006.L52.p285](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0006.L52.p285))
  - In this length-matched pair FVE goes the right way. The WRONG bullet scores solo 0.352, the lowest in its readout.
  - The clean `Use fans or AC**: Air movement makes it hard for mosquitoes to land. If you’re indoors, turn on a fan` scores 0.488. The reply continues "- **Create a breeze**: ... Use a fan".
- `所以我’m not sure if "Alex" is a real person or if this is a new chat context. If` (Original, L52, [chat-dailydialog-0045.L52.p65](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0045.L52.p65))
  - This bullet is WRONG ("Alex" where the reply has "Mary") and is the lowest in its readout (share 11.7%, solo 0.110, coef 0).
  - But its clean sibling `所以 I might be roleplaying in a new conversation. If you meant I was interacting with` is just as redundant (solo 0.132, coef 0).
  - So its low score shows redundancy as much as error.

### 3.2 Right frame, wrong filler: the usual shape of a wrong bullet (tentative)

A common way for a bullet to go wrong:
- It keeps the reply's frame or template.
- It gets one slot wrong: a name, number, entity or attribute.

This shape does not explain why some wrong bullets score high, because it is just as common among low-scoring ones:
- Readers coded it in 37 of 45 confirmed errors in stratum A and 31 of 45 in stratum B.
- In the full data, slot-like wrong spans make up about 56% of both the top and the bottom share quintile.

The score seems to follow the shared frame rather than the filler:
- Clean siblings that share their first 3 tokens differ in solo FVE by 0.060 / 0.077 / 0.043. Siblings with no shared opening differ by 0.095 / 0.119 / 0.081.
- Wrong–clean pairs with the same first 3 tokens differ no more than clean–clean pairs do (0.061 / 0.089 / 0.041). For these pairs, clean beats wrong 0.50 / 0.42 / 0.46 of the time.

None of this shows a mechanism yet, because no bullet with a corrected filler has been scored.

Examples:
- `The Mid-Autumn Festival emphasizes family reunion and harmony — central themes in Chinese culture` (Combine 32, L60, [chat-dailydialog-0044.L60.p136](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0044.L60.p136))
  - The reply's next item is "2. **Family Reunion**" for the Spring Festival. The bullet has the right item but the wrong festival.
  - Its solo of 0.4386 ties the clean `2. **Family Reunion / Togetherness** – The Chinese New Year is fundamentally about **reuniting with family**` (0.4391).
- `Original DataFrame:  Name  Age    Score\n0   Alice   25     85` (\n = line break) (Best of 32, L52, [chat-lmsys-0038.L52.p364](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0038.L52.p364))
  - The reply prints Alice with 92. The 85 is Bob's score.
  - The bullet's solo is 0.617, equal to the joint FVE.
  - The clean header-only sibling `Original DataFrame:           Name  Age  Score` scores 0.593, but a bare `Original DataFrame:` scores only 0.132. Almost all the FVE comes from the frame.
- `Dave" as if we were in a specific, real-world scenario. If you are feeling frustrated, it's possible you're addressing a` (Combine 32, L36, [chat-dailydialog-0045.L36.p63](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0045.L36.p63))
  - The read token is the opening quote just before the reply's `Mary,"`.
  - All four Combine bullets get the name wrong (Dave, Lisa, Dave, Bob), and three of them score solo 0.33–0.35.

### 3.3 Low FVE inside a readout reflects form and redundancy (tentative)

Right-but-low bullets usually have one of these features:
- short or broken text
- mostly Chinese text (no reply contains Chinese)
- a list-number opener the reply does not use
- an early position in the list
- coef 0, meaning a sibling already covers the bullet

How often these features account for the lowest-share fifth of bullets:

| Group | Original (Best of 32 is similar) | Combine 32 |
|---|---|---|
| Low-share clean bullets in hallucinated readouts | 69% | 19% |
| Low-share wrong bullets | 60% | 16% |
| All other clean bullets in hallucinated readouts | 43% | 9% |
| All other wrong bullets | 30% | 7% |

In Combine 32, coef 0 and position do not apply, which is why its numbers are low.

The original claim said wrong and clean bullets have these features at the same rates. That holds for coef 0 (14.3% vs 14.2% in Original) and for mostly-Chinese text. It does not hold for length and position: wrong bullets are longer and sit later in the list (section 2), and both of those raise FVE.

A single Chinese lead word does not hurt. Bullets with one beat bullets with no Chinese at all: no-Chinese bullets win only 0.471 / 0.434 / 0.478 of such pairs.

Examples:
- `怎么还没打卡？或者说，你是来蹭杯咖啡的？😄 我正好在泡一杯，要不要一起？` (Original, L60, [chat-dailydialog-0022.L60.p60](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0022.L60.p60))
  - A clean, all-Chinese bullet in an English reply: solo 0.064.
  - The English clean bullet making the same coffee move, `How about you? Did you manage to grab a coffee before things got crazy`, scores 0.335.
- `ized Medicine:** Tailoring treatments to individual patients based on their unique genetic profiles, thanks to AI analysis of vast medical datasets.` (Original, L60, [chat-lmsys-0058.L60.p139](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0058.L60.p139))
  - This bullet has the most faithful content in its readout but starts mid-word: solo 0.096.
  - `Personalized Medicine:** AI analyzes genetic data to predict disease risk and suggest tailored treatments.` scores 0.636. Every bullet in this readout is clean.
- `That feedback helps me improve and refine my responses. Or, ask me to` (Best of 32, L36, [chat-dailydialog-0053.L36.p127](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0053.L36.p127))
  - A clean paraphrase of the reply's "This helps me adjust in real-time", but it has coef 0 and a 13.6% share.
  - The WRONG near-duplicate `这 helps me refine my responses. Or, if I give you a wrong answer, point it out—I’m designed to learn from it` absorbs it (solo 0.505, 35.7% share).

### 3.4 Where the error sits matters a little; the 32-token limit does not (holds)

The reconstructor reads only each bullet's first 32 tokens. This explains almost none of the null:
- Only 0.12% / 0.02% / 0.07% of wrong bullets have all their wrong text past the limit.
- Dropping every bullet with any unscored wrong text leaves the pair rate at 0.516 / 0.507 / 0.508.
- 60–64% of wrong spans start in the first third of the scored text.

Where the error starts matters a little:
- **Errors in the opening third cost some FVE.** Controlling only position and length, the cost is −0.007 / −0.010 / −0.008 solo FVE, about 0.10–0.14 within-readout SD. Every interval excludes 0.
- **Errors later in the bullet cost nothing.** These wrong bullets even score slightly above clean ones (pair rates 0.474–0.496).
- Within a readout, clean openings overlap the reply's next text a little more than wrong openings (pair rate 0.546 / 0.541 / 0.532). This is probably where the cost of opening errors comes from.

Examples:
- The scored part ends `Don't force interaction or demand that he come out. Instead, show`, and the unscored tail is `Her Space, But Stay Present** – Don’t force interaction or demand she talk.` (Original, L52, [chat-dailydialog-0069.L52.p76](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0069.L52.p76))
  - The reply says "Give Him Space". The gender flip lies entirely past the limit.
  - The bullet takes a 55% share, and its solo of 0.679 equals the joint FVE.
  - Its sibling `Respect Her Space (Without Pushing)**` has the same error inside the window and gets solo 0.413 with coef 0.
- `只要 you are no longer in direct proximity to the alligator, your safety increases significantly.` (Combine 32, L44, [chat-lmsys-0041.L44.p127](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0041.L44.p127))
  - The prompt is about a shark. The swap sits inside the scored window, late in the sentence.
  - This is still the top bullet (solo 0.323, 29.5% share). It beats the clean `只要 you follow normal safety protocols, moving to another floor creates a safe buffer zone between you and the animal.` (0.298).
- An opening error and a later error in the same readout (Best of 32, L44, [chat-lmsys-0046.L44.p461](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0046.L44.p461)). The reply is "Answer : D".
  - WRONG `C) [The model provided "Answer : C" despite the options being scrambled, I will output the` is wrong from its first token: solo 0.084, coef 0.
  - WRONG `D / C [The text explicitly says "Final Answer is: D"]` starts correctly: solo 0.147.
  - The clean `D # Explanation: The extracted answer is D, despite the format errors in the prompt` gets solo 0.211 and a 49% share.

### 3.5 OFF-TOPIC is penalised a little, but the wrong/off-topic boundary is unstable (tentative)

Off-topic bullets lose some FVE:
- Their within-readout penalty is 3–6 times that of WRONG bullets: −0.014 / −0.019 / −0.011 solo FVE, with every interval excluding 0.
- Clean bullets beat off-topic ones 0.53–0.55 of the time.
- Off-topic openings overlap the reply's next text less: 0.263, against 0.319 for clean and 0.318 for wrong (Original).

The penalty only holds on average, and the label itself is unstable:
- Identical bullet texts judged twice gave 231 off-topic/wrong pairs, against 278 off-topic/off-topic pairs.
- Readers called only 7 of the 24 sampled OFF-TOPIC bullets genuine junk:
  - 9 were on-topic errors that should have been labelled WRONG.
  - 8 had no error. These were often mixed Chinese/English text that the judge flagged as foreign.

Examples:
- One template, four labels (L44, [chat-dailydialog-0051.L44.p60](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0051.L44.p60)). The reply has "I am confused".
  - Best of 32: `I was frustrated by..."**: The main clause – stating your emotional state. "Was" is the past tense of "` is OFF-TOPIC (solo 0.483).
  - Combine 32: `I am puzzled by..."**: The subject and verb, indicating a feeling of confusion.` is clean (0.524), and `I was annoyed by"**: This is the main clause, stating your emotional state.` is WRONG (0.511).
  - The score follows the template, not the label.
- `2. Industrial Chemistry: The Solvent-Based Manufacturing Process` … `The extraction and purification of rubber powder is a continuous, highly controlled chemical engineering` (Original, L60, [chat-lmsys-0069.L60.p426](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0069.L60.p426))
  - Labelled OFF-TOPIC (the prompt is about Gastrodin): solo 0.009, coef 0.
  - The equally off-topic `. The Extraction Process: A Detailed Chemical Engineering Breakdown` … `polyolefin plasticizers` bullet takes a 60% share. The low score follows the heading, not the topic.
- Counter-example: `Act as an Expert Resume Writer & Career Strategist for a University Application ## Goal You are writing a resume for an 8th-grade student applying to` (Combine 32, L44, [chat-lmsys-0047.L44.p314](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0047.L44.p314))
  - Labelled OFF-TOPIC: the wrong domain sits inside the exact "Act as an expert X" template.
  - Its solo of 0.371 beats the clean `Role Definition: Expert Travel Consultant & Data Analyst` (0.317).

### 3.6 Judge noise is large and may hide a small signal (tentative)

Bullet verdicts are noisy (details in section 5). The original claim said cleaner labels give the same null, but that only partly holds:
- Against verified-true clean bullets, the unmatched pair rate is about 0.50.
- With length also matched, it rises to 0.579 / 0.531 / 0.579.
- In Combine 32, the wrong-vs-verified-true regression effect is −0.0136 [−0.021, −0.007], about 0.25 SD.

So judge noise and length together probably hide a small real effect. It is still far too small to flag individual bullets.

Examples:
- `我没有 a physical body or a bank account, so I can't head out to a physical` (L52, [chat-dailydialog-0010.L52.p24](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0010.L52.p24))
  - The text and its solo (0.505) are identical in two settings. It is clean in Original (49% share) and WRONG in Combine 32.
  - That single verdict flips the cell from consistent to hallucinated.
- `祝你 have a wonderful time! Just let me know if you need help preparing for the event.` (Best of 32, L52, [chat-dailydialog-0027.L52.p113](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0027.L52.p113))
  - Flagged WRONG, although the reply ends "Have a wonderful time at the party! 🎉".
  - It is the top bullet (58% share), so this "wrong but high share" case is really a judge false positive.

### 3.7 More sampling swaps the sample, not the kind of error (tentative)

Best of 32 and Combine 32 raise mean joint FVE from 0.371 to 0.425 and 0.450. Correctness barely moves:
- **Best of 32**:
  - It fixes 659 hallucinated cells and breaks 551 consistent ones. The net change is −1.6 pts in the hallucinated rate [−3.0, −0.3], which is small but real.
  - The effect does not grow with FVE gain. By gain tertile, the hallucinated rate changes by −0.019 / −0.014 / −0.017.
- **Combine 32**:
  - It fixes 658 cells and breaks 614, a net change of −0.4 pts [−1.7, +1.1].
  - Its wrong rate is flat over greedy pick order (0.271 / 0.267 / 0.263 / 0.272).
- **Kinds of wrong span** differ from Original by at most 1.2 points.

What changes is which sample's filler ends up in the readout. Of the 48 cells where the settings disagree, 17 flips come from a different sample that carries a real error, and 28 come from judge inconsistency.

Examples:
- `中秋 is traditionally associated with family reunions and` (Best of 32, L52, [chat-dailydialog-0044.L52.p136](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0044.L52.p136))
  - Best of 32 swapped Original's consistent sample (FVE 0.333) for sample #14 (0.355).
  - That sample's top bullet (71% share) puts the reunion theme under Mid-Autumn.
- `（helping people with winter-related queries or offering advice on staying cozy). Others, I help users brainstorm ways to enjoy the season.` (Best of 32, L20, [chat-dailydialog-0071.L20.p108](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0071.L20.p108))
  - The reply is about summer ("Help people beat the heat").
  - Original had 1 wrong bullet out of 4. The sample Best of 32 picked has 4 out of 4 wrong, at a slightly higher FVE (0.121 to 0.138).
- `You can manually assign a shortcut to the Pause command in VLC's settings. This is the most reliable method.` (Original, L44, [chat-lmsys-0029.L44.p83](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0029.L44.p83))
  - The bullet names Pause where the reply means the 3D function.
  - Best of 32 avoided the error by picking a sample with generic wording.
  - Combine 32 brought the error back with `You can manually assign a shortcut to Pause by following these steps:` (solo 0.551), which outscores the clean `Since there is no default shortcut, you can manually assign one.` (0.506).

### 3.8 Kinds of hallucination (tentative)

Readers confirmed an error in 145 of the 288 records:

| Kind | Records |
|---|---|
| Wrong relation or attribute | 74 |
| Invented specific detail | 53 |
| Persona or self-claim | 11 (10 of them in dailydialog) |
| Misread prompt | 7 |

Readers called only 7 records unrelated junk.

How firm this breakdown is:
- **Substitution inside the right frame** is the largest group but does not dominate. Slot or swap codes appear in 83 of the 145 confirmed errors (57%).
- **Persona errors** mostly follow the source's base rate. Casual chat uses first-person wording a lot anyway: 51% of clean and 59% of wrong dailydialog bullets contain it. Within dailydialog, P(wrong | first person) is 0.21, against 0.16 without first person.
- **Off-topic labels** are common by the judge's count: 8.7% of all bullets and 25% of non-clean bullets. They are rare only after reader review.
- **Kind-specific penalties**: no kind except off-topic gets a consistent penalty. For example, a wrong bullet with a novel name against a clean bullet that also has a name gives pair rates of 0.573 / 0.478 / 0.512.

Examples:
- `*   **At $100^\circ\text{C}$:** $\approx 160$ g/L. This shows an incredibly high baseline` (Combine 32, L60, [chat-lmsys-0052.L60.p209](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0052.L60.p209))
  - Invented numbers in the right row template. The reply gives about 118–120 g per 100 mL.
  - The four bullets give values that cannot all be true (160 g/L, 89 g/L, 5,780 g, ~8,000 g/L), yet all score solo 0.19–0.29. This one is the top pick (35.3% share).
- `康跃 Bio-Pharma maximizes its reach, ensuring that its high-quality solutions are accessible to clients worldwide.` (Best of 32, L44, [chat-lmsys-0009.L44.p326](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0009.L44.p326))
  - Entity swap: the reply's next words name "Shanghai BMG Chemical Co., Ltd.".
  - The company name changes even within this one sample: sibling bullets name `康美` and `Xi’an Ruidong Chemical`.
  - This WRONG bullet is the top one (solo 0.384, 43.9% share).
- `toppings like pepperoni, or something exotic? I’m a fan of New York-style thin crusts` (Original, L44, [chat-dailydialog-0063.L44.p118](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0063.L44.p118))
  - A persona claim. According to the judge, the reply says the assistant cannot taste pizza.
  - Its solo of 0.471 falls between its two clean siblings (0.420 and 0.510).

## 4. Error types by setting

| | Original | Best of 32 | Combine 32 |
|---|---|---|---|
| **All data, judge labels** | | | |
| Bullets labelled WRONG | 26.6% | 25.9% | 26.8% |
| Bullets labelled OFF-TOPIC | 8.7% | 8.4% | 8.9% |
| Readouts labelled hallucinated | 47.0% | 45.4% | 46.7% |
| **All data, kind of wrong span (text proxies)** | | | |
| Novel capitalised name | 24.2% | 23.9% | 24.8% |
| Novel number | 13.1% | 13.4% | 13.1% |
| First-person | 10.5% | 10.7% | 9.8% |
| Other short span (≤4 words) | 18.6% | 17.5% | 19.4% |
| Longer span | 33.6% | 34.6% | 32.9% |
| Bullets with any novel number or name | 33.6% | 33.8% | 35.6% |
| **Reader codes, wrong-bullet strata A+B+F** (n = 54 / 51 / 39) | | | |
| Invented specific detail | 11 (20%) | 12 (24%) | 16 (41%) |
| Wrong relation or attribute | 25 (46%) | 21 (41%) | 8 (21%) |
| Persona or self-claim | 2 | 3 | 2 |
| Misread prompt | 2 | 0 | 1 |
| No real error (plausible continuation or judge too strict) | 14 (26%) | 14 (27%) | 12 (31%) |

The kinds of error stay the same across settings.

Combine 32 has 2.1 pts more specifics [1.3, 2.9]. That gap shrinks to +0.6 [−0.2, +1.5] when Combine is reweighted to Original's mix of list positions:
- 64% of Combine's picks come from positions 3–4 of their source sample.
- Those positions carry more specifics and more errors: the wrong rate is 20.7% at position 1 and 30.9% at position 4.

The reader sample shows 41% invented detail for Combine, but that rests on only 39 records, so it is not a confirmed shift.

One example per setting:
- **Original**, L20, [chat-dailydialog-0042.L20.p67](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0042.L20.p67): `他们一定非常忙碌又兴奋吧？筹备婚礼是一件大事，希望能顺利。`
  - Wrong relation: the bullet says wedding, but the reply goes on "Are they planning a baby shower yet?".
  - Best of 32 and Combine 32 are consistent only because their samples say "baby". FVE barely moves (0.285 / 0.288 / 0.306).
- **Best of 32**, L44, [chat-lmsys-0045.L44.p71](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0045.L44.p71): `The use of all-caps text and the repetitive emphasis on "quickly" reveal a sense of urgency and impatience.`
  - Invented detail: the user never wrote "quickly". The bullet has coef 0.
- **Combine 32**, L36, [chat-dailydialog-0045.L36.p63](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0045.L36.p63): `Lisa" or this specific task happening in a workplace.`
  - The name slot is filled wrongly. The reply has "Mary".

## 5. Judge reliability

**Readers vs the judge** (288 records):

| Measure | Value |
|---|---|
| Reader agrees / partly agrees / disagrees | 164 / 86 / 38 (124 partly or fully disagree) |
| Judge says WRONG, reader sees a real error | 128/192 (67%) |
| Judge says WRONG, reader sees no error | 63/192 (33%) |
| Judge says clean, reader sees an error | 8/72 |
| Judge says OFF-TOPIC, reader sees junk / an error / no error | 7 / 9 / 8 (of 24) |
| Direction of disagreement: judge too strict / judge missed an error / wrong-vs-off-topic boundary | 71 / 8 / 9 |
| Share of records where the judge was too strict (Original / Best / Combine) | 25% / 20% / 29% |
| Cells where the settings disagree: judge inconsistent / real sample change / uncounted span / judge too strict | 28 / 17 / 2 / 1 (of 48) |

**Repeat judgements, full data:**
- **Test-retest.** In 119 cells, Original and the raw lens output differ only in runs of spaces, and the two were judged in separate calls.
  - The readout-level hallucination flag agrees in 86.6% [80.0, 92.4] of cells.
  - A WRONG verdict is repeated 79% [67, 87] of the time.
  - The synthesis figure of 65.6% counts agreement over all bullets that were WRONG in either run. That is a stricter overlap rate, not the repeat rate.
- **Identical bullet text in two readouts of the same cell** (5,552 pairs):
  - The labels agree 78.2% [76.4, 79.9] of the time.
  - When one copy is WRONG, the other is WRONG 65% [62, 68] of the time and clean 27% of the time.
  - Byte-identical texts reuse a cached verdict (5,208 of 5,208), so they say nothing about noise.
- **Pipeline issues:**
  - Some wrong spans were found by the judge but marked "NOT counted". These sit inside 92 / 104 / 115 clean bullets (0.6–0.8%). Counting them would flip 21 / 23 / 25 consistent readouts.
  - 8 records note the judge misreading Chinese.

Examples:
- `I am bothered by..."**: Standard English structure for expressing irritation or annoyance. "I am" is the subject + verb.` (L44, [chat-dailydialog-0051.L44.p60](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0051.L44.p60))
  - The same text from sample #18, with the same solo (0.519), is OFF-TOPIC in Best of 32 (b2) and clean in Combine 32 (b1).
- `The King's Gambit (and its variants) + Sharp Openings** This is the most common aggressive choice for attacking players.` (L44, [chat-lmsys-0068.L44.p104](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0068.L44.p104))
  - The same text from sample #22, with solo 0.598 in both settings, is clean in Best of 32 (b3) and WRONG in Combine 32 (b0).
- `你都可以跟我说。Are you looking for anything specific? Tips on the area, local food, or just someone to chat with? Feel free to` (Original, L20, [chat-dailydialog-0029.L20.p68](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0029.L20.p68))
  - The Chinese means "you can tell me anything", which fits the reply.
  - The judge called it a "Foreign-language sentence unrelated to the English conversation", and the whole readout was labelled off_topic.
- `（The role of the British Monarch is largely ceremonial and symbolic, focusing on national unity and tradition.) Would you like to know more about that instead?` (Combine 32, L44, [chat-lmsys-0031.L44.p81](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0031.L44.p81))
  - The reader counts this as a judge miss: the reply offers an overview of the Swedish monarch.
  - The sibling `the role of the monarch in the Canadian parliamentary system` was marked WRONG for the same kind of swap, but this one was left clean.
- `toppings like pepperoni, or something exotic? I’m a fan of New York-style thin crusts` (Original, L44, [chat-dailydialog-0063.L44.p118](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0063.L44.p118))
  - The raw lens output differs from Original only in whitespace. Original is labelled hallucinated and Raw consistent, so this is a pure re-judgement flip.

## 6. What did not survive

| Statement | What the checks found | Example |
|---|---|---|
| "Wrong bullets score the same at every layer, slice and error kind" | About 12 of ~75 slices exclude 0.5, in both directions (Original L60 0.544; length-matched Original L60 0.614; Combine novel names 0.456). These effects are small and not corrected for multiple tests, but the original wording was too strong. | An opening error and a later error in one readout: [chat-lmsys-0046.L44.p461](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0046.L44.p461) (Best of 32, L44). `C) [The model provided "Answer : C"` scores 0.084 and `D / C [The text explicitly says "Final Answer is: D"]` scores 0.147. |
| "Wrong and clean bullets have these form features at the same rates" | False for length (wrong is longer in 59–63% of pairs) and position (wrong is later in 64% of pairs in Original and Best of 32). Length hides a small effect. | [chat-dailydialog-0006.L52.p285](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0006.L52.p285) (Original, L52): with length matched (100 vs 103 characters), the WRONG `Check for electric bug zappers**` bullet is lowest (0.352 vs 0.488). |
| "Cleaner labels give the same null" | Verified-true clean with length matched gives 0.579 / 0.531 / 0.579. | [chat-dailydialog-0027.L52.p113](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0027.L52.p113) (Best of 32, L52): `祝你 have a wonderful time!` is labelled WRONG although its content is correct. Noise like this dilutes the signal. |
| "Bullets with invented numbers or names score slightly higher" | This is a length effect: these bullets are longer in 56–62% of pairs. With length matched, the rates are 0.48 / 0.50 / 0.51. "No lower" survives; "higher" does not. | [chat-lmsys-0052.L60.p209](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0052.L60.p209) (Combine 32, L60): `$\approx 160$ g/L` and the other contradictory numbers all score 0.19–0.29. |
| "A WRONG verdict holds only about 2 times in 3" | The metric was misstated. A repeat judgement keeps a WRONG verdict 79% of the time; identical text in another readout keeps it 65% of the time. | [chat-dailydialog-0010.L52.p24](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0010.L52.p24): `我没有 a physical body or a bank account` is clean in Original and WRONG in Combine 32. |
| "Best of 32 fixes about as many cells as it breaks" | Best of 32 is a small net improvement (−1.6 pts [−3.0, −0.3]), and the improvement does not depend on FVE gain. Combine 32 shows no change. | [chat-dailydialog-0044.L52.p136](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0044.L52.p136) (Best of 32, L52): a higher-FVE sample broke this cell (`中秋 is traditionally associated with family reunions and`). |
| "Combine 32 adds more invented specifics" | Mostly an effect of which list positions it draws from: +2.1 pts becomes +0.6 [−0.2, +1.5] after reweighting. | [chat-lmsys-0029.L44.p83](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0029.L44.p83) (Combine 32, L44): the error `You can manually assign a shortcut to Pause by following these steps:` was the first pick, not a late one. |
| Reader hypothesis: "recap bullets score low" | Overlap with earlier text carries no penalty (pair rates 0.512 / 0.507 / 0.518). | [chat-dailydialog-0021.L36.p299](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0021.L36.p299) (Original, L36): the recap `（have an open, non-accusatory conversation) and observe their response.` takes an 81% share, while the reply's actual next item, `2. **Listen Actively**: ...`, gets solo 0.086. |
| Reader hypothesis: "Combine's late, low-gain picks bring in errors" | The wrong rate is flat over pick order (0.271 / 0.267 / 0.263 / 0.272) and over gain quartile. | [chat-lmsys-0052.L60.p209](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0052.L60.p209): the first pick, `*   **At $100^\circ\text{C}$:** $\approx 160$ g/L.`, is already wrong. |
| "Low share does not flag errors the judge missed" (stratum C) | Cannot be tested: there is no matched group of high-share clean bullets in hallucinated readouts. C vs D gives 7/36 vs 1/36 (p = 0.055), but the two strata come from different readout types. | [chat-lmsys-0009.L44.p326](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0009.L44.p326) (Best of 32, L44): the low-share clean bullet (9.2% share, coef 0) `康美 leverages its location to expand its reach` has the same company swap as its WRONG siblings. Its span was "NOT counted". |
| Readers' report: "Raw and Original flip on identical text" | The texts differ in whitespace, so these are fresh judgements, not cache misses. | [chat-dailydialog-0063.L44.p118](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0063.L44.p118) (Original, L44). |

## 7. Caveats

- **Everything is exploratory.** About 60 subgroup tests in the synthesis, plus the skeptics' extra slices, have no correction for multiple tests. Do not over-read any single interval near 0.55.
- **The reading sample is stratified, not representative.**
  - Strata were chosen by raw Shapley share, and stratum B was forced to include 22 coef-0 bullets.
  - Reader counts describe those strata, not the whole population.
  - Readers saw the scores when they explained them.
  - The codes for the readers' free text (relation, score reading, notes) come from keyword regexes. The causes in the 48 disagreeing cells were coded by hand from the readers' notes.
- **The reconstructor reads only the first 32 tokens of each bullet.** This rarely matters: under 0.2% of wrong bullets have all their wrong text past the limit. It does mean FVE never sees the tail of long bullets.
- **The judge is a single model (GPT-6 Luna).**
  - Its bullet verdicts repeat only about 65–79% of the time.
  - In reader review it leans too strict: 71 too-strict calls against 8 missed errors.
  - It handles mixed Chinese/English text poorly.
  - Some wrong spans are dropped as "NOT counted".
- **The text proxies are crude.** Novel number or name, first-person wording, CJK fraction and n-gram overlap are rough measures. Together they explain only 4–7.5% of within-readout solo-FVE variance, so most of what drives FVE remains unexplained.
- **Where the status labels come from.** For 3.1 and 3.2 they come from two skeptic reviews. For the other sections they come from the skeptics' check outputs: `c2_confound_checks.json`, `c6_confound_check.json`, `c7_confound_check.json`, `c8_confounds.json`, `verify_C3_evidence/` and `redteam_C1/`.
- **Files**, all in `${OLENS_SCRATCH}/olens-bullet-fve/reading/`:
  - `tables.md` and `tables.json`: reading tables
  - `synth_tests.py` and `synth_tests.json`: full-data tests
  - `records/`: 24 reader batches
  - `show_case.py`: plain-text case viewer
  - the skeptic check files listed above

## 8. Suggested next steps

1. **Counterfactual filler test.** Take high-FVE wrong bullets, replace only the wrong value with the reply's value, and re-score FVE. Candidates:
   - Alice 85 → 92 in [chat-lmsys-0038.L52.p364](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0038.L52.p364)
   - alligator → shark in [chat-lmsys-0041.L44.p127](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-lmsys-0041.L44.p127)
   - Mid-Autumn → Spring Festival in [chat-dailydialog-0044.L60.p136](https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#chat-dailydialog-0044.L60.p136)

   If FVE does not rise, either the activation does not encode the filler or the scorer cannot see it.
2. **Use agreement across samples instead of FVE.** The frame is stable across the 32 samples but the filler is not: Dave / Lisa / Bob for Mary, or 康美 / 康跃 / Xi’an Ruidong for one company. Test whether disagreement on a slot value flags hallucination better than FVE does.
3. **Make the labels more reliable.**
   - Re-judge a subset (for example 500 bullets, 3 runs each) and take majority votes.
   - Fix the "NOT counted" span matching and the handling of mixed Chinese/English text.
   - Then repeat the length-matched comparison against verified-true clean bullets. That is the one place a small signal appeared (about 0.53–0.58).
4. **Match length and position by default.** Pre-register the two small effects that survived: opening-third errors (about 0.1 SD) and off-topic bullets (about 0.2 SD). Test them on fresh chats before building on them.