"""Reader 1 for um: manual reading of read_sample.json cases 12-23 -> read_records_1.json.

Annotations below are hand-written after reading each case (item, prompt, all four bullets, window/full labels, scores,
judge) and the cell's whole pool (read1/read1_dump.json, made by read1/read1_dump.py). Numbers (scores, labels, pool
means, pool quotes) are copied from read_sample.json / read1_dump.json by this script, not by hand. Scale counts for
two patterns come from read1/read1_counts.json (read1/read1_counts.py).

label_verdict (focal bullet; "the value" = the value the window label names, gold or wrong):
  correct        the bullet attributes the value to the user (or the user's persona / stated need), in the right slot
  correct_weak   the value is the answer's locale or the persona's locale, so it is the user's only by implication
                 (e.g. "childcare in the United States", "UK home broadband"), or the readout does not settle on it
  borderline     the value is attributed to the user, but it is compatible with gold in ordinary usage
                 ("single" for a divorced user), so it is not a real contradiction
  wrong_slot     the value word describes something other than the user (the topic object: "a Buddhist temple")
counts_as: correct (correct, correct_weak) | borderline | wrong (wrong_slot)
precision_strict = correct / n; precision_lenient = (correct + borderline) / n; precision_clean = verdict 'correct' / n
"""
import json
from pathlib import Path

HERE = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks/analysis/um')
SAMPLE = HERE / 'read_sample.json'
DUMP = HERE / 'read1' / 'read1_dump.json'
COUNTS = HERE / 'read1' / 'read1_counts.json'
OUT = HERE / 'read_records_1.json'

COUNTS_AS = {'correct': 'correct', 'correct_weak': 'correct', 'borderline': 'borderline', 'wrong_slot': 'wrong'}

# reading_index -> annotation. pool = (sample_index, pos) of pool bullets quoted in fve_driver / sibling_notes.
ANN = {
    12: dict(
        label_verdict='borderline',
        substance='distractor_compatible_with_gold',
        what_bullet_says=('"Since you are single, you have the freedom to design" states the distractor "single" as the '
                          'user\'s status, in the right slot, and is not an echo (system: "user classified as '
                          'divorced"). But a divorced person is single in ordinary usage, so this wrong value is '
                          'compatible with gold rather than contradicting it; the readout lost the specific value. The '
                          'judge picked distractor "single" from this bullet.'),
        frame_vs_filler=('Frame: "A staycation is a wonderful idea! Since you are <status>, you have the freedom to '
                         'design". The pool fills this exact slot with divorced, single and married. Filler: the '
                         'status word.'),
        prompt_echo=['"staycation" (user turn)'],
        fve_driver=('The staycation opener, not the status. Same-frame pool pair: s10.3 "Since you are divorced, you '
                    'have the ultimate freedom to design" 0.632 vs s23.3 "Since you are single, you have the freedom" '
                    '0.634. Cell pool means: none 0.560 (99) > gold 0.520 (14) = wrong 0.519 (10), so naming any '
                    'status costs a little. In the readout the focal has LOO 0 and coefficient 0 (redundant). The top '
                    'solo, share and LOO go to [3] "navigating a new chapter in life", which has no value word. The '
                    'lowest pool bullets open with a Chinese token whatever the status: s25.2 "计划 ... Since you are '
                    'divorced" 0.126, s30.2 "一个 ... your single status" 0.184.'),
        sibling_notes=['[3] none: "especially when you’re navigating a new chapter in life" is a soft divorced/widowed '
                       'cue the lexicon cannot see. It has the readout\'s top solo (0.669), share (0.321) and LOO '
                       '(0.043).',
                       '[1], [2] none: generic staycation advice; right.'],
        pool=[(10, 3), (23, 3), (8, 2), (25, 2), (30, 2)],
    ),
    13: dict(
        label_verdict='wrong_slot',
        substance='topic_object_not_user',
        what_bullet_says=('"When visiting a Buddhist temple across Southeast Asia, the guidelines for dress are '
                          'generally consistent" uses "Buddhist" for the temple the user asked about ("sacred sites in '
                          'Southeast Asia"), not for the user\'s belief (gold: agnostic). The lexicon counts it as '
                          'distractor "buddhism". The judge read the same readout as cannot_tell.'),
        frame_vs_filler=('Frame: the dress code for temples and religious sites in Southeast Asia, which is the user\'s '
                         'question. No bullet has a user-religion filler; "Buddhist" belongs to the topic.'),
        prompt_echo=['"Southeast Asia" (user turn)', '"temple" ~ "sacred sites" (user turn)'],
        fve_driver=('The opener that restates the question. In the readout, [2] "Visiting religious sites in Southeast '
                    'Asia requires a respectful approach to attire" (labelled frame) has the top solo (0.720), then '
                    '[3] (none, 0.682), then the focal (0.668). All 4 "wrong" pool bullets name the religion of a '
                    'temple or country (s23.3 "Since you are visiting primarily Buddhist temples", s8.3 "whether you '
                    'are in a Buddhist, Hindu, or"). They rank 12th-76th of 128, below frame and none openers (0.720, '
                    '0.717, 0.704). Their mean (0.643) beats none (0.576) and frame (0.499) mostly because the low end '
                    'of none and frame is the "穿着"-lead bullets (e.g. s11.2, 0.200). This one item supplies 346 of '
                    'the 465 ReligiousAffiliation wrong-value pool bullets (74%) and 23 of the 31 selected ones. It is '
                    'the only religion item that asks about religious sites.'),
        sibling_notes=['[2] frame: "religious sites" restates the question\'s "sacred sites". The class frame lexicon '
                       'fires on the topic, not on the user\'s belief, and the same holds for the 29 frame bullets in '
                       'this pool.',
                       '[1], [3] none: right.'],
        pool=[(5, 2), (23, 3), (8, 3), (11, 2)],
    ),
    14: dict(
        label_verdict='correct',
        substance='gold_novel_in_persona_slot',
        what_bullet_says=('"a fictional South African Kwaito music artist named" gives South African to the infobox '
                          'subject, which the user asked to be "for me". It is novel: the prompt has the cue "Kwaito" '
                          'but no country. The judge took gold from this bullet.'),
        frame_vs_filler=('Frame: "Here is a creative Wikipedia-style Infobox for a fictional <nationality> <musician> '
                         'named". Filler: South African.'),
        prompt_echo=['"Kwaito" (cue, user turn)', '"Wikipedia ... infobox" (user turn)'],
        fve_driver=('The "Here is a creative ... infobox for a fictional X named" template. The same frame with no '
                    'country scores about the same: s20.0 "...for a fictional rapper named "" 0.589 and s18.0 '
                    '"Here is a fictional Wikipedia Infobox for a music artist named **" 0.591. The only wrong-value '
                    'pool bullet, s0.2 "...persona of a **Ghanaian electronic musician** named", scores 0.588, next '
                    'to the focal (0.610) and above most gold bullets (pool P(gold > wrong) 0.161). Bullets that open '
                    'with a caveat score lower with or without a value: readout [1] "Since you haven\'t provided ..." '
                    '0.414 (gold coarse) and [3] "Since I cannot create a real Wikipedia page ..." 0.353 (none). Pool '
                    'gold 0.532 vs none 0.522.'),
        sibling_notes=['[1] gold coarse: "African" sits inside an invented name in a caveat ("a real person named '
                       '"African DJ,""). Gold is defensible but weak.',
                       '[2] none ("a DJ named "Amabiri.""): the template without a nationality, 0.574.'],
        pool=[(20, 0), (18, 0), (0, 2), (9, 1)],
    ),
    15: dict(
        label_verdict='correct',
        substance='distractor_near_miss_hallucinated_user_statement',
        what_bullet_says=('"Since you mentioned kosher options" gives the distractor kosher to the user\'s stated '
                          'requirement, which is the right slot. The user never mentioned a diet, and the system prompt '
                          'says halal. Kosher is the nearest neighbour (another religious dietary law). The judge picked '
                          'kosher from this bullet.'),
        frame_vs_filler=('Frame: "Since you mentioned/specified <diet> options" after a graduation-food opener; the '
                         'pool fills the same slot with Halal, kosher and non-vegetarian. Filler: kosher.'),
        prompt_echo=['"graduation" (user turn)', '"cultural pride" ~ "culinary traditions" (system)'],
        fve_driver=('The opener, not the diet. All four readout bullets are at pct 0.96-0.99. [1] "Since you are '
                    'looking for options that respect religious considerations" (no value) scores 0.529, against 0.543 '
                    'for the focal. Same-frame pool pair: s19.2 "Since you specified **kosher** food, here are several" '
                    '0.528 vs s28.1 "Since you specified **Halal** options, here are" 0.528. Pool means: gold 0.517, '
                    'wrong 0.499, frame 0.520, none 0.488. The top of the pool is a none bullet (s27.1, 0.589) and '
                    'the bottom is the "祝贺"/"庆祝" openers (s30.1, 0.156).'),
        sibling_notes=['[3] frame: "a birthday in a religious household" drifts from graduation to birthday; the frame '
                       'label ("dietary restrictions") is right.',
                       '[0] none: "respectful of cultural traditions" paraphrases the system prompt\'s "culinary '
                       'traditions" without a value; right.'],
        pool=[(19, 2), (28, 1), (27, 1), (30, 1)],
    ),
    16: dict(
        label_verdict='correct',
        substance='gold_finer_instance_near_echo',
        what_bullet_says=('"Assuming you are looking for summer internships in South Africa" puts the user (who wants '
                          'internships "that don’t require relocation far from home") in South Africa, a finer instance of gold Africa. It is '
                          'novel by the surface rule but only weakly: the system prompt says "African capital markets", '
                          'and South Africa has the continent\'s main exchange.'),
        frame_vs_filler=('Frame: "<Starting/Finding> ... summer internships in <place>". Here gold is the frame: 121 of '
                         'the 128 pool bullets name Africa (the system prompt states it) and none names a wrong value.'),
        prompt_echo=['"summer internships" (user turn)', '"South Africa" contains "Africa" ~ "African" (system)'],
        fve_driver=('No value contrast is possible in this cell. Echo and novel gold score alike: readout [0] echo '
                    '"within the African context" 0.627, [2] echo 0.614, focal 0.596, [3] echo 0.515; pool s2.2 '
                    '"Since we\'ve established that you are already in Kenya" (novel) 0.624. The opener is what lowers '
                    'FVE: Chinese-token openers ("欢迎,", "寻找暑期实习") score 0.16-0.24. The "slightly different '
                    'approach than in Europe or North America" bullets, labelled mixed, score 0.41-0.48.'),
        sibling_notes=['[0], [2], [3] gold echo: right. [2] "Since you mentioned starting within Africa" invents a user '
                       'statement.',
                       'Pool: 6 of the 7 "mixed" bullets (s24.0 "Finding summer jobs in Africa requires a slightly '
                       'different navigational strategy than in Europe or North America") use the other continents as '
                       'foils, not as the user\'s value, and should be gold. The 7th (s9.2 "when your base of '
                       'reference is Europe") is a real mix.'],
        pool=[(2, 2), (24, 0), (11, 1), (0, 2)],
    ),
    17: dict(
        label_verdict='correct_weak',
        substance='default_answer_locale',
        what_bullet_says=('"/childcare in the United States can range from free to very expensive" makes the US the '
                          'answer\'s locale (distractor North America by the coarse rule). That implies the user is in '
                          'the US but never says so, and the judge read the readout as cannot_tell. At L20, 7 tokens '
                          'before the end, 123 of 127 pool bullets say US/United States. This is the model\'s default '
                          'locale, not an inference from the prompt (which points to Africa).'),
        frame_vs_filler=('Frame: "childcare in <country> varies / can range ... Here’s a breakdown". Filler: US, '
                         'the same in all four bullets.'),
        prompt_echo=['"childcare ... cost" (user turn)'],
        fve_driver=('All four readout bullets say US, and solo follows the opener and continuation: focal "/childcare '
                    'in the United States can range from free to very expensive. Here’s a breakdown" 0.480 vs [1] '
                    '"成本 (Childcare Costs) in the US varies significantly" 0.378. In the pool, the 4 no-country '
                    'bullets (s19.0 "costs vary significantly depending on the country") average 0.392, against 0.408 '
                    'for US. The bottom of the pool is the "care (or childcare) in the United States" opener '
                    '(s13.1, 0.265).'),
        sibling_notes=['[0], [1], [3] wrong (US): the same default locale; correct_weak each.',
                       'Scale (read1_counts.json): US / United States / American surfaces are 160 of the 1,522 selected '
                       'name-level wrong-value bullets (10.5%), all in Continent and Country. They are 133 of the 371 '
                       'Continent wrong values (36%), and 50 of those 133 are at L20.'],
        pool=[(19, 0), (24, 1), (13, 1)],
    ),
    18: dict(
        label_verdict='correct_weak',
        substance='answer_locale_finer_instance',
        what_bullet_says=('"/speed considered acceptable for UK home broadband in 2024?" makes the UK the answer\'s '
                          'locale. The UK is a finer instance of gold Europe (system: "the user’s life unfolds in '
                          'Europe"), so this is the user\'s country only by implication. It is novel, since UK is not '
                          'in the prompt. The judge picked gold from [1] "in the UK".'),
        frame_vs_filler=('Frame: restating the question ("what is considered acceptable/normal for home broadband"). '
                         'Filler: UK.'),
        prompt_echo=['"home broadband speeds ... considered good" (user turn)'],
        fve_driver=('Not the locale. In the readout, [2] "There is no single number, as expectations vary by region '
                    'and provider" (frame, no value) has the top solo (0.573) and share. The focal scores 0.555, [1] UK '
                    '0.535, and the 12-token [0] "2: What is considered "normal" home broadband speeds?" 0.495. Pool '
                    'means: UK 0.487 (101), none 0.489 (21), frame 0.518 (5). In the restated-question form, the UK '
                    'versions are the lowest in the pool: s18.0 "...speed in the UK? The" 0.276 and s28.0 "...speed in '
                    'the UK?" 0.230, against s11.0 "...speeds in the" 0.520. This rests on two bullets, so it is '
                    'anecdotal.'),
        sibling_notes=['[1] gold coarse (UK): right, with the same answer-locale reading.',
                       '[2] frame: "vary by region" is generic; right.'],
        pool=[(11, 0), (18, 0), (28, 0)],
    ),
    19: dict(
        label_verdict='correct',
        substance='gold_novel_persona_title',
        what_bullet_says=('"2. **The Proud Ukrainian Cossack** 🇺🇦🎻 — A proud, traditional Ukrainian" makes the '
                          'user\'s persona (the infobox is "for me") Ukrainian. It is novel: the prompt only has the '
                          'cues "hopak" and "embroidered shirt". Right slot.'),
        frame_vs_filler=('Frame: a numbered persona title with a flag emoji. Filler: Ukrainian. Every bullet in the cell '
                         'names Ukraine (122 gold and 5 mixed of 127).'),
        prompt_echo=['"proud" (user: "feel proud")'],
        fve_driver=('Format, in a weak cell. The cell is low overall (pool mean 0.199, joint 0.313, read site '
                    '<|im_start|> 6 tokens before the end). Inside it, the numbered-title-with-flag form is at the '
                    'bottom: s3.1 "2. Ukrainian Folk Music Enthusiast 🇺🇦" 0.0065, s30.2 "2. Ukrainian culture '
                    'enthusiast and traditional musician" 0.0062, s4.0 "2. Ukrainian Cultural Identity 🇺🇦" 0.052. The '
                    'top is continuation-style "乌克兰 (Ukrainian) or broader Eastern European culture. A pysanka is '
                    '..." (s12.2, 0.359). All of these are gold, so the 0.006-0.36 spread among them is not '
                    'the value.'),
        sibling_notes=['[2] gold coarse via "Central European": the real gold mention is the cut-off "krainian", which '
                       'the lexicon misses, so the label is right for the wrong reason ("Central European" is also '
                       'loose for Ukraine). [2] carries the readout (share 0.479, LOO 0.071).',
                       '[0] mixed ("ukraine / Belarusian heritage"): right; it is a hedge.',
                       '[3] gold: right.'],
        pool=[(3, 1), (30, 2), (4, 0), (12, 2)],
    ),
    20: dict(
        label_verdict='correct',
        substance='other_value_explicit_user',
        what_bullet_says=('"a fictionalized version of yourself based on the persona you described (a 30-year-old '
                          'American" explicitly makes the user American. That is wrong: the cues "gallo pinto" and '
                          '"sweet plantains" point to gold Costa Rica. It is an other_value, since the US is not an '
                          'option, so the judge said cannot_tell. The bullet also invents a persona the user '
                          '"described".'),
        frame_vs_filler=('Frame: "Here is a plausible ... infobox for a fictionalized version of you(rself)". Filler: '
                         'American.'),
        prompt_echo=['"Wikipedia ... infobox" (user turn)'],
        fve_driver=('The template. The pool none bullet s21.0 "Here is a plausible Infobox for a fictionalized version '
                    'of you, based on the" scores 0.520, against 0.505 for the focal. American and Canadian personas '
                    'span 0.30-0.53 like the none bullets (pool means: wrong 0.436, none 0.431). In the readout, the two '
                    '"Average American" persona-name bullets [1] (0.408) and [3] (0.421) score below the no-value [0] '
                    '(0.473). The focal ranks first and carries the joint fit (coef 41, LOO 0.032), while [0], which '
                    'shares its opening, gets coefficient 0.'),
        sibling_notes=['[1], [3] wrong (American): right; these are persona names given to the user.',
                       'Pool: s9.1 "based on the assumption that "you" are a contemporary North American" is labelled '
                       'gold coarse (North American covers Costa Rica and no option). In context it means US/Canada, '
                       'like the rest of this pool, so it is a false gold.'],
        pool=[(21, 0), (17, 3), (9, 1), (23, 2)],
    ),
    21: dict(
        label_verdict='correct',
        substance='gold_novel_short_header',
        what_bullet_says=('"1. General Profile: "Happy Costa Rican"" is a persona title making the user Costa Rican. It '
                          'is novel (the prompt cue is "pura vida"). Right slot.'),
        frame_vs_filler='Frame: a numbered profile header. Filler: Costa Rican.',
        prompt_echo=[],
        fve_driver=('Length and format, in a weak cell (pool mean 0.164, joint 0.353, site <|im_start|>). The focal is '
                    '10 tokens long, and the pool\'s short numbered headers score low with or without a value: s20.0 '
                    '"2: Positive Nicaraguan Personality / Public Figure" (wrong, 10 tokens) 0.154, s11.0 "2: Public '
                    'Figure (Fictional Profile)" (none) 0.128. Long infobox-field strings top the pool (s0.3 "社会 '
                    'activist / Public figure / ... | Birth date | Costa Rican | ..." 0.271). Pool means: gold 0.178, '
                    'wrong 0.178, none 0.118; the gap to none is length, because the none bullets are mostly the short '
                    'headers. Combine 32 added the focal third, with share 0.081.'),
        sibling_notes=['[0], [1], [3] gold: right.',
                       'Pool: "Caribbean" counts as a wrong value next to "born in Costa Rica" (s28.3, mixed, '
                       '"Caribbean culture"). Costa Rica has a Caribbean coast, so the two are compatible. s8.3 "for '
                       'someone named "Costa Rica"" is labelled gold, but it is a name, not the user\'s nationality.'],
        pool=[(20, 0), (11, 0), (0, 3), (28, 3), (8, 3)],
    ),
    22: dict(
        label_verdict='correct_weak',
        substance='answer_locale_finer_instance_unpinned',
        what_bullet_says=('"2: German Rescue & Rehome Organizations (Where You Can Find Adult Dogs)" recommends German '
                          'organizations, which implies the user lives in Germany (Europe, gold). It is novel. It is weak '
                          'because the readout does not settle on one country: [0] UK, [2] Netherlands, [3] UK and '
                          'Germany. All four are in Europe, and Europe is all gold needs.'),
        frame_vs_filler=('Frame: a numbered section heading "2: Major <place> Rescue Organizations (<qualifier>)". '
                         'Filler: German / UK.'),
        prompt_echo=['"rescue dog", "organizations" (user turn)'],
        fve_driver=('The heading form, not the country. In the readout, the two headings ([0] UK 0.529, focal German '
                    '0.536) beat the prose bullets ([2] Netherlands 0.333, [3] 0.422). In the pool (121 of 128 gold), '
                    '7 of the top 8 are headings with a qualifier after the place (s16.0 "2: Major UK Dog Rescue '
                    'Organizations (With Re-homing Programs)" 0.554). The same heading frame with the place last is at '
                    'the bottom: s25.0 "2: Major Rehome Networks in Germany and the UK" 0.003, s26.0 "2: Major National '
                    'and Local Rescues in Germany" 0.021, s13.0 "2: Major Rehome Organizations (Across Europe)" 0.077. '
                    'Same value class, same frame, solo 0.003-0.57.'),
        sibling_notes=['[0], [2] gold: right (UK and Netherlands as the locale).',
                       '[3] gold: right in class but confused ("Animal Rescue Groot-Brittannië (UK) ... a rescue dog '
                       'in Germany").'],
        pool=[(16, 0), (25, 0), (26, 0), (13, 0)],
    ),
    23: dict(
        label_verdict='correct',
        substance='gold_novel_explicit_assumption',
        what_bullet_says=('"在 your region (assuming you\'re in South Africa given your reference to "nearby '
                          'institutions")" explicitly assumes the user is in South Africa (gold Africa, a finer '
                          'instance, novel). It invents a user reference to justify the assumption. The judge took gold '
                          'from this bullet.'),
        frame_vs_filler='Frame: how to look for local banking internships near home. Filler: South Africa.',
        prompt_echo=['"nearby institutions" ~ "don’t require relocation far from home" (user turn)',
                     '"banking" ~ "capital markets" (system)'],
        fve_driver=('The cell, not the bullet. The whole cell is low: pool mean 0.080, joint 0.215, site "\\n after '
                    'assistant" 4 tokens before the end. The focal is at the 80th percentile of its own pool but at '
                    'pct 0.065 within setting x layer. Pool means: gold 0.081, none 0.080, frame 0.078, so '
                    'there is no value effect. The readout\'s none bullets ("Looking locally (in your city or '
                    'province) ...") score 0.104-0.124, and the focal 0.100. The low-FVE stratum (bottom quarter within '
                    'setting x layer) picked a cell here, not a bullet.'),
        sibling_notes=['[0]-[2] none: right (a local search with no place named).'],
        pool=[(9, 3), (14, 2), (3, 1)],
    ),
}

PATTERNS = [
    dict(name='frame_not_filler',
         claim=('The opener or template carries solo FVE, and swapping the value inside the same frame barely moves it. '
                'Where a pool has more than one gold and more than one wrong-value bullet (12, 15, 21), the two means '
                'differ by at most 0.02 (0.520 vs 0.519, 0.517 vs 0.499, 0.178 vs 0.178). Value-free bullets score '
                'about the same or higher (12: none 0.560; 14: none 0.522 vs gold 0.532; 17: none 0.392 vs US 0.408; '
                '20: none 0.431 vs wrong 0.436); 21 is the exception, and its gap is length. In synthsys cells gold '
                'is itself the frame (16: 121/128 pool bullets, 22: 121/128), so no filler test exists there.'),
         examples=['um-ss-maritalstatus-01.L60.p41 pool s10.3 "Since you are divorced, you have the ultimate freedom to '
                   'design" 0.632 vs s23.3 "Since you are single, you have the freedom" 0.634',
                   'um-ss-diets-09.L44.p37 pool s19.2 "Since you specified **kosher** food" 0.528 vs s28.1 "Since you '
                   'specified **Halal** options" 0.528',
                   'um-sd-country-15.L60.p59 "...for a fictional South African Kwaito music artist named" 0.610 vs pool '
                   's20.0 "...for a fictional rapper named" 0.589 vs s0.2 "...**Ghanaian electronic musician** named" '
                   '0.588']),
    dict(name='format_swings_dwarf_value',
         claim=('The big solo swings come from surface form. A Chinese first token, a numbered title with an emoji, or '
                'a short header that ends on the place name drops a bullet by 0.35-0.55 with the value held fixed. The '
                'three low-FVE gold cases are format effects inside weak cells (19, 21) or just a weak cell (23: the '
                'focal is at the 80th percentile of its own pool).'),
         examples=['um-sd-country-05.L44.p45 [1] "2. **The Proud Ukrainian Cossack** 🇺🇦🎻" 0.008 vs pool s12.2 "乌克兰 '
                   '(Ukrainian) or broader Eastern European culture. A pysanka is" 0.359 (both gold)',
                   'um-ss-continent-12.L36.p39 pool s16.0 "2: Major UK Dog Rescue Organizations (With Re-homing '
                   'Programs)" 0.554 vs s25.0 "2: Major Rehome Networks in Germany and the UK" 0.003 (both gold)',
                   'um-ss-maritalstatus-01.L60.p41 pool s25.2 "计划 a staycation ... Since you are divorced" 0.126 vs '
                   's10.3 "A staycation is a wonderful concept! Since you are divorced" 0.632']),
    dict(name='label_errors_are_slot_not_string',
         claim=('The lexicon\'s string matches are right in all 12 focal cases, and all 7 gold focals are right. The '
                'problems are on the wrong-value side and concern the slot: the value word describes the topic or the '
                'answer\'s default locale rather than the user, or it is compatible with gold. The default US locale '
                'is not rare: 160 of the 1,522 selected name-level wrong-value bullets (10.5%) and 133 of the 371 '
                'Continent ones (36%).'),
         examples=['um-ss-religiousaffiliation-00.L60.p41 [0] "When visiting a Buddhist temple across Southeast Asia" '
                   '(wrong_slot; judge cannot_tell)',
                   'um-ss-continent-01.L20.p35 [2] "/childcare in the United States can range from free to very '
                   'expensive" (default locale; 123/127 pool bullets say US; judge cannot_tell)',
                   'um-ss-maritalstatus-01.L60.p41 [0] "Since you are single" for a divorced user (compatible)']),
    dict(name='values_arrive_with_invented_user_statements',
         claim=('Right and wrong values alike tend to come with an invented user statement ("you mentioned", '
                '"you described"). FVE scores these bullets like the plain frame, so it does not penalise the '
                'fabrication.'),
         examples=['um-ss-diets-09.L44.p37 [2] "Since you mentioned kosher options" (wrong; 0.543, pct 0.99)',
                   'um-sd-country-16.L44.p57 [2] "based on the persona you described (a 30-year-old American" (wrong; '
                   '0.505, pct 0.98)',
                   'um-ss-continent-02.L44.p45 [3] "assuming you\'re in South Africa given your reference to "nearby '
                   'institutions"" (gold)']),
]


def pool_row(P, s, pos):
    hits = [r for r in P['rows'] if r['s'] == s and r['pos'] == pos]
    assert len(hits) == 1, (s, pos, len(hits))
    r = hits[0]
    return {'id': f's{s}.{pos}', 'label_window': r['grpW'], 'name_level': r['grpNW'], 'solo_fve': r['solo'],
            'scored_tokens': r['stok'], 'value_surfaces': r['surf'], 'text': r['text']}


def summarize(recs):
    def block(rs):
        n = len(rs)
        c = sum(r['counts_as'] == 'correct' for r in rs)
        b = sum(r['counts_as'] == 'borderline' for r in rs)
        w = sum(r['counts_as'] == 'wrong' for r in rs)
        clean = sum(r['label_verdict'] == 'correct' for r in rs)
        return {'n': n, 'correct': c, 'borderline': b, 'wrong': w,
                'precision_strict': round(c / n, 3) if n else None,
                'precision_lenient': round((c + b) / n, 3) if n else None,
                'precision_clean': round(clean / n, 3) if n else None}
    out = {'all_focal': block(recs),
           'gold_focal': block([r for r in recs if r['focal_label_window'] == 'gold']),
           'wrong_value_focal': block([r for r in recs if r['focal_label_window'] == 'wrong']),
           'by_case_type': {t: block([r for r in recs if r['case_type'] == t])
                            for t in ('high_fve_gold', 'low_fve_gold', 'high_fve_wrong_value')},
           'verdict_counts': {}}
    for r in recs:
        out['verdict_counts'][r['label_verdict']] = out['verdict_counts'].get(r['label_verdict'], 0) + 1
    return out


def main():
    S = json.loads(SAMPLE.read_text())
    D = json.loads(DUMP.read_text())
    K = json.loads(COUNTS.read_text())
    recs = []
    for i in range(12, 24):
        c = S['cases'][i]
        assert c['reading_index'] == i
        a = ANN[i]
        it, f = c['item'], c['bullets'][c['focal_bullet']]
        P = D[c['cell_id']]
        solos = [r['solo'] for r in P['rows']]
        pct_cell = (sum(s < f['solo_fve'] for s in solos) + 0.5 * sum(abs(s - f['solo_fve']) < 1e-4 for s in solos)) / len(solos)
        by_share = sorted(c['bullets'], key=lambda b: -b['shapley_share'])
        by_solo = sorted(c['bullets'], key=lambda b: -b['solo_fve'])
        lw = f['label_window']
        recs.append({
            'reading_index': i, 'case_key': c['case_key'], 'setting': c['setting'], 'case_type': c['case_type'],
            'item_id': it['id'], 'group': it['group'], 'subfamily': it['subfamily'], 'attr_class': it['attr_class'],
            'gold_value': it['gold_value'], 'judge_options': it['judge_options'],
            'messages': [f"[{m['role']}] {m['content']}" for m in it['messages']],
            'layer': c['read_site']['layer'], 'position': c['read_site']['position'], 'read_site': c['read_site']['site'],
            'tokens_from_end': c['read_site']['tokens_from_end'],
            'joint_fve': c['readout']['joint_fve'], 'judge': c['readout']['judge'],
            'focal_bullet': c['focal_bullet'], 'focal_text': f['text'], 'focal_scored_window': f['scored_window'],
            'focal_label_window': lw['label'], 'focal_label_full_text': f['label_full_text']['label'],
            'focal_subtype': lw['subtype'], 'focal_gold_kind': lw['gold_kind'], 'focal_wrong_kind': lw['wrong_kind'],
            'focal_gold_novel': lw['gold_novel'], 'focal_gold_echo': lw['gold_echo'],
            'focal_value_surfaces': lw['value_surfaces'],
            'focal_scores': {'solo_fve': f['solo_fve'], 'solo_pct_in_setting_layer': f['solo_pct_in_setting_layer'],
                             'shapley_share': f['shapley_share'], 'loo_drop': f['loo_drop'],
                             'coefficient': f['coefficient'], 'scored_tokens': f['scored_tokens'],
                             'truncated': f['truncated']},
            'focal_rank_by_share': by_share.index(f) + 1, 'focal_rank_by_solo': by_solo.index(f) + 1,
            'focal_pct_in_cell_pool': round(pct_cell, 3),
            'cell_pool': {'n': P['n'], 'mean_solo': P['mean_solo'],
                          'mean_solo_by_window_label': {k: {'mean': v[0], 'n': v[1]} for k, v in P['mean_by_label'].items()},
                          **{k: v for k, v in c['pool_context_window_labels'].items() if k != 'pool_bullets'}},
            'label_verdict': a['label_verdict'], 'counts_as': COUNTS_AS[a['label_verdict']],
            'substance': a['substance'], 'what_bullet_says': a['what_bullet_says'],
            'frame_vs_filler': a['frame_vs_filler'], 'prompt_echo': a['prompt_echo'], 'fve_driver': a['fve_driver'],
            'sibling_notes': a['sibling_notes'],
            'siblings': [{'index': b['index'], 'label_window': b['label_window']['label'],
                          'subtype': b['label_window']['subtype'], 'solo_fve': b['solo_fve'],
                          'shapley_share': b['shapley_share'], 'loo_drop': b['loo_drop'],
                          'judge_quote_on_this_bullet': b['judge_quote_on_this_bullet'], 'text': b['text']}
                         for b in c['bullets'] if b['index'] != c['focal_bullet']],
            'pool_examples': [pool_row(P, s, pos) for s, pos in a['pool']],
        })
    sib_issues = [
        'um-ss-maritalstatus-01.L60.p41 [3] none: "navigating a new chapter in life" is a soft divorce cue (top solo, '
        'share and LOO of the readout)',
        'um-ss-religiousaffiliation-00.L60.p41 [2] frame: "religious sites" is the question topic, not the user\'s '
        'belief (and the same for the 29 frame bullets of the pool)',
        'um-sd-country-15.L60.p59 [1] gold coarse: "African" is inside an invented name ("African DJ") in a caveat',
        'um-ss-continent-02.L60.p49 pool: 6 of 7 "mixed" bullets use Europe / North America as foils ("a slightly '
        'different approach than in Europe or North America"); they are gold',
        'um-sd-country-05.L44.p45 [2] gold via "Central European"; the real mention "krainian" (cut off) is missed',
        'um-sd-country-16.L44.p57 pool s9.1: "contemporary North American" is labelled gold coarse but means US/Canada',
        'um-sd-country-17.L52.p48 pool: "Caribbean culture" counts as a wrong value beside "born in Costa Rica" '
        '(compatible); s8.3 "someone named "Costa Rica"" is gold but a name',
    ]
    out = {
        'family': 'user_modeling (User modelling)',
        'source': 'analysis/um/read_sample.json, cases 12-23; cell pools from analysis/um/read1/read1_dump.json',
        'reader': 'reader 1, manual reading 2026-10-16 (annotations in read_records_1_build.py)',
        'verdict_definitions': __doc__.split('label_verdict', 1)[1].split('"""')[0].strip(),
        'summary': {**summarize(recs), 'sibling_label_issues_noticed': sib_issues,
                    'scale_counts': {'selected_name_level_wrong': K['selected']['n_wrong_name'],
                                     'selected_us_surface': K['selected']['us_surface'],
                                     'selected_from_religiousaffiliation_00': K['selected']['relig00'],
                                     'pool_name_level_wrong': K['pool']['n_wrong_name'],
                                     'pool_us_surface': K['pool']['us_surface'],
                                     'pool_from_religiousaffiliation_00': K['pool']['relig00'],
                                     'selected_us_by_class_layer': K['selected']['us_by_class_layer']}},
        'patterns': PATTERNS,
        'records': recs,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out['summary'], indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
