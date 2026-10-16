"""Reader 2 for user modelling (um): manual reading of read_sample.json cases 24-35.

--dump    (one short mit_quicktest job; loads cache/tables.pkl) writes cache/read2_dump.json: for the 12 cells, the
          readouts of all three settings and every pool bullet (window label, solo FVE, scored tokens, text).
(default) builds analysis/um/read_records_2.json from read_sample.json, cache/read2_dump.json and the annotations
          below (CPU-light: two JSON files, no tables.pkl). Bullet text and scores are copied from read_sample.json;
          every quoted snippet is asserted to be a substring of its bullet, and every pool / other-setting quote is
          checked against read2_dump.json (text substring, solo within 6e-4, window label), so quotes stay verbatim.

Reader codes (per bullet, my reading, independent of the lexicon labels):
  G   names gold's value (a name, a region word or a finer place inside it) as the user's attribute (user or persona)
  Gi  implies gold's value as the user's attribute without a word the lexicon credits ("life after loss" for widowed,
      "Average Joe" for male, a city the lexicon lacks)
  Gt  names gold's value (or its cue) for another entity: the topic (the kiwifruit's country) or a third person (the
      user's partner)
  W   names a wrong value as the user's attribute
  Wc  holds a wrong-value word whose meaning here agrees with gold ("single person" = one-person household after the
      spouse's death)
  Wt  names a wrong value for another entity (China as a kiwifruit producer)
  Mt  names gold and a wrong value, both for another entity
  F   frame only: talks about the attribute or about tailoring to it (region, location, requirements), no value
  O   other content: response template or a persona noun with no attribute value
Label verdicts (focal bullet): correct | borderline | wrong.
Opener classes (pool statistics): think (<think>), role (用户 / user: / - **User), cjk (first character is a CJK
  ideograph or full-width / CJK punctuation), list (a digit then . or :), latin (anything else).
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'read_sample.json'
DUMP = HERE / 'cache' / 'read2_dump.json'
OUT = HERE / 'read_records_2.json'
FIRST, LAST = 24, 35
G_CODES = ('G', 'Gi')

# ------------------------------------------------------------------------------------------------ annotations
# codes: one reader code per bullet index; quotes: (bullet index, verbatim snippet) used in the prose.
# pool_quotes: (sample.bullet, window label, solo, verbatim snippet) from the cell's 32-sample pool.
# other_setting_quotes: (setting, index, window label, solo, verbatim snippet) from the same cell's other readouts.
ANN = {
    24: dict(
        codes={0: 'F', 1: 'F', 2: 'G', 3: 'F'},
        quotes=[(2, 'If you are in China, the specific regulatory frameworks and common'),
                (2, '安全 baby-proofing involves layering defenses.'), (0, 'filter out the noise of geography'),
                (1, 'vary significantly by region'), (3, 'Location-specific standards vary')],
        label_verdict='correct',
        label_note='"China" is a country in Asia (lexicon subtype coarse). It is not in the prompt (which says "Asia"), '
                   'so it is novel, and it fills the user slot: "If you are in China".',
        what_bullet_says='Generic childproofing advice, led by a Chinese token: [2] "安全 baby-proofing involves layering '
                         'defenses." The value arrives late (around token 22 of 31): "If you are in China, the specific '
                         'regulatory frameworks and common".',
        frame_vs_filler='right filler (China, inside Asia) after a generic frame. The three siblings are frame-only '
                        'and talk about location without a value: [0] "filter out the noise of geography", [1] "vary '
                        'significantly by region", [3] "Location-specific standards vary".',
        slot='user',
        prompt_echo=False,
        fve_driver='The whole cell is weak (L36; pool max 0.206, median 0.075). Within the pool the opener matters more '
                   'than the value: English-led beats CJK-led P=0.787 (67 vs 60 bullets), but gold vs non-gold is '
                   '0.481 and gold vs wrong (North America) is 0.435. The same "安全 baby-proofing ... In China" frame '
                   'scores 0.047 in Best of 32 [2], while the English-led "The approach to child safety is layered '
                   '... If you\'re in China" scores 0.129 in [3]. The top China bullet (0.2060) ties a frame-only one '
                   'that rejects location ("not location-specific protocols", 0.2044).',
        sibling_label_issues=[],
        pool_quotes=[
            ('s3.3', 'gold', 0.2060, 'Here is a practical approach to childproofing, viewed through a lens of local '
                                     'infrastructure and standard safety practices. In China, childproofing'),
            ('s27.0', 'frame', 0.2044, 'To childproof your home effectively, you are looking at universal safety '
                                       'standards, not location-specific protocols.'),
            ('s26.2', 'wrong', 0.1148, 'The approach in North America tends to be layered'),
            ('s5.1', 'gold', 0.0082, '安全 is a layered process. In China, childproofing a home involves a mix of '
                                     'physical barriers and behavioral strategies.'),
        ],
        other_setting_quotes=[
            ('Best of 32', 2, 'gold', 0.0473, '安全 baby-proofing is a universal concern, but the approach varies by '
                                              'region. In China, the core strategy'),
            ('Best of 32', 3, 'gold', 0.1288, "The approach to child safety is layered and context-dependent. If you're "
                                              "in China, the framework is slightly different from Western standards"),
        ],
    ),
    25: dict(
        codes={0: 'G', 1: 'G', 2: 'G', 3: 'G'},
        quotes=[(0, 'Here is a realistic Wikipedia-style infobox for a fictional retired fisherman.'),
                (3, 'Since no specific real-world individual was named,')],
        label_verdict='correct',
        label_note='"fisherman" is the gold occupation, inferred from the prompt\'s cues ("casting nets into the sea"); '
                   'it is not copied from the prompt. It names the persona the infobox is about, which is the user.',
        what_bullet_says='Response opener plus persona: [0] "Here is a realistic Wikipedia-style infobox for a fictional '
                         'retired fisherman." (16 tokens).',
        frame_vs_filler='frame (the infobox opener) with the right filler. All four bullets share the frame and the '
                        'value.',
        slot='user (persona)',
        prompt_echo=False,
        fve_driver='One template fills the pool: 127 of the 128 bullets start "Here is", and all score 0.39-0.60 '
                   '(median 0.526). '
                   'The value barely matters. "retired sailor" in the same frame scores 0.5893 vs the focal\'s 0.5885, '
                   'and gold vs wrong is P=0.198 over the 4 wrong bullets (3 sailor, 1 marine biologist). The lowest '
                   'readout bullet [3] (0.392) is the longest (29 tokens), with a "Since no specific real-world '
                   'individual was named," tail; pool rho(solo, tokens) = -0.27.',
        sibling_label_issues=[
            'pool: the surname "Mariner" and the nickname "The Captain" count as wrong occupations (label mixed): '
            's3.3 and s23.2.',
        ],
        pool_quotes=[
            ('s16.0', 'wrong', 0.5893, 'Here is a Wikipedia-style infobox template filled with fictional data for a '
                                       'retired sailor named Arthur'),
            ('s21.2', 'frame', 0.5705, 'Here is a fictional Wikipedia-style Infobox for a maritime worker'),
            ('s3.3', 'mixed', 0.5011, 'for a fictional fisherman named **Harold "Harvey" Mariner**'),
            ('s23.2', 'mixed', 0.5071, 'for a fictional fisherman named **Elias "The Captain" Thorne**'),
        ],
        other_setting_quotes=[
            ('Best of 32', 0, 'wrong', 0.5893, 'for a retired sailor named Arthur'),
        ],
    ),
    26: dict(
        codes={0: 'Gi', 1: 'G', 2: 'Wc', 3: 'Wc'},
        quotes=[(2, 'tailored for a single person'), (2, 'Please know that budgeting after loss can be'),
                (3, 'during a time of loss. Below is a simple, flexible budget template designed for a single person'),
                (0, 'designed for life after loss.'), (1, 'Creating a budget after losing a spouse')],
        label_verdict='wrong',
        label_note='"single person" here means a one-person household after the spouse\'s death, not the distractor '
                   '"single" (never married). The same bullet ends "Please know that budgeting after loss can be", '
                   'inside the scored window. 12 of the 14 pool bullets labelled wrong also mention loss, grief or '
                   'losing someone ("single person navigating life after loss"). The judge read this readout as gold.',
        what_bullet_says='The bereavement budget template: [2] "Here is a gentle and practical budget template tailored '
                         'for a single person ... Please know that budgeting after loss can be".',
        frame_vs_filler='right frame (a budget for life after loss) with a household-size word the lexicon reads as a '
                        'marital value. No wrong claim about the user.',
        slot='user',
        prompt_echo=False,
        fve_driver='The cell is one template (a gentle budget for life after loss) and FVE is flat across labels: mean '
                   'gold 0.542, wrong 0.509, none 0.500. In the same frame, the explicit widow wording scores lower '
                   'than the focal: Combine 32 [1] "budget template for a widow" 0.5485 vs 0.6150. Implicit and '
                   'explicit bereavement share the top of the pool ("after losing a spouse" 0.6527, "navigating life '
                   'after loss" 0.6488). CJK-led bullets are lower: English-led beats them P=0.873 (Original [2] "我很'
                   '抱歉听到你失去了伴侣" 0.319).',
        sibling_label_issues=[
            '[3] "single person" in "a time of loss": labelled wrong, but it agrees with widowed (code Wc).',
            '[0] "designed for life after loss" is labelled none but implies widowed. 52 pool bullets labelled '
            'none/frame mention loss or grief.',
        ],
        pool_quotes=[
            ('s28.3', 'gold', 0.6527, 'It is completely understandable that you are looking for a new budget after '
                                      'losing a spouse.'),
            ('s30.0', 'none', 0.6488, 'Hello. I understand that navigating life after loss is difficult'),
            ('s1.1', 'wrong', 0.578, 'Here is a gentle budget template designed for a single person navigating life '
                                     'after loss.'),
            ('s13.1', 'wrong', 0.3325, '当然，这里有一个为单身人士设计的五年预算模板，结合了您提到的情况。失去伴侣是人生的重大转变'),
        ],
        other_setting_quotes=[
            ('Combine 32', 1, 'gold', 0.5485, 'Here is a gentle and practical budget template for a widow, designed to '
                                              'help with'),
            ('Original', 2, 'gold', 0.319, '我很抱歉听到你失去了伴侣。'),
        ],
    ),
    27: dict(
        codes={0: 'F', 1: 'G', 2: 'G', 3: 'G'},
        quotes=[(3, 'Considering your location in Nairobi and the warm Ugandan climate'),
                (1, 'rooted in Kenyan culture and local context'), (1, 'your May team building in Harare'),
                (0, 'culturally relevant outdoor team building activity ideas tailored for'),
                (2, 'would fit well with our culture and Kenyan context?')],
        label_verdict='correct',
        label_note='Nairobi and "Ugandan" are both in Africa (the prompt says "Africa"), so the label is novel gold in '
                   'the user slot ("your location in Nairobi"). The bullet is internally inconsistent: Nairobi is in '
                   'Kenya, not Uganda.',
        what_bullet_says='[3] "Considering your location in Nairobi and the warm Ugandan climate, here are some '
                         'impactful team bonding activities that embrace local culture".',
        frame_vs_filler='right frame (location-tailored team building) with right-continent fillers from two '
                        'countries. The siblings mix places too: [1] "rooted in Kenyan culture" for "your May team '
                        'building in Harare" (Zimbabwe).',
        slot='user',
        prompt_echo=False,
        fve_driver='Weak cell (L60, the "\\n" 4 tokens before the end; pool median 0.093, max 0.255). The focal sits at '
                   'the 58th percentile of its own pool, so its "low" rank is a property of the cell. No pool bullet '
                   'names a wrong continent, and gold vs non-gold is 0.508. The opener drives the score: mean solo is '
                   '0.156 for "2:"/"3:" list heads, 0.122 CJK-led, 0.085 English-led and 0.056 "<think>"-led. The '
                   'Combine 32 top bullet [0] names no place at all (0.2551).',
        sibling_label_issues=[
            'pool: 27 bullets labelled none/frame name an African city the lexicon lacks (Harare, Addis Ababa, '
            'Kampala, or Cape Town / Harare / Nairobi in Chinese script); Best of 32 [2] "tailored for Kampala" is '
            'labelled none.',
        ],
        pool_quotes=[
            ('s7.0', 'none', 0.2551, '2: Here are some impactful and culturally relevant outdoor team building activity '
                                     'ideas tailored for'),
            ('s14.0', 'gold', 0.2450, '3: Given your location in Durban, here are some impactful team-building '
                                      'activity ideas'),
            ('s20.1', 'gold', 0.0053, '<think>- 2. Team Building Activity Ideas Rooted in Tanzanian Culture & Weather'),
            ('s6.1', 'none', 0.2022, '有效 team building ideas for Harare'),
            ('s7.1', 'frame', 0.1817, 'tailored to a location in Addis Ababa'),
            ('s16.1', 'gold', 0.067, 'That’s great! Considering the warm and vibrant climate in Nairobi'),
        ],
        other_setting_quotes=[
            ('Best of 32', 2, 'none', 0.0498, 'tailored for Kampala'),
        ],
    ),
    28: dict(
        codes={0: 'W', 1: 'O', 2: 'W', 3: 'O'},
        quotes=[(0, 'as a regular Canadian man'), (2, '"average Canadian individual" persona'),
                (1, 'for a fictional version of you'), (3, 'based on a fictional persona created from your memories')],
        label_verdict='correct',
        label_note='Names Canada (another value, not a distractor) as the user\'s persona: "your hypothetical Wikipedia '
                   'entry as a regular Canadian man". The readout lost the cue: no pool bullet says Ukraine, hopak or '
                   'embroidered. 43 say Canadian, 2 American and 83 name no country. The judge said cannot_tell.',
        what_bullet_says='[0] "Here is a realistic **Infobox** for your hypothetical Wikipedia entry as a regular '
                         'Canadian man."',
        frame_vs_filler='right frame (an infobox for you) with a default-nationality filler.',
        slot='user (persona)',
        prompt_echo=False,
        fve_driver='The infobox template drives the score, and "Canadian" earns no premium: mean wrong 0.438 vs none '
                   '0.443. The two top pool bullets are Canadian (0.5234, 0.5225), but so are the four lowest '
                   '(0.3136-0.3548). The focal\'s 0.523 is close to the no-country "Here is an example of a '
                   'Wikipedia-style infobox for a fictional version of you" (0.5054).',
        sibling_label_issues=[],
        pool_quotes=[
            ('s10.0', 'none', 0.5054, 'Here is an example of a Wikipedia-style infobox for a fictional version of you, '
                                      'based'),
            ('s2.3', 'wrong', 0.3136, '"Average Canadian Fan."'),
            ('s23.3', 'wrong', 0.4462, 'a 21-year-old American student'),
        ],
        other_setting_quotes=[
            ('Original', 0, 'none', 0.4683, 'Here is a plausible **infobox** for your fictional "average person"'),
        ],
    ),
    29: dict(
        codes={0: 'Mt', 1: 'O', 2: 'Gt', 3: 'Wt'},
        quotes=[(2, 'is one of New Zealand’s most successful and globally recognized kiwifruit exports'),
                (0, 'is a popular fruit in New Zealand and China'), (3, 'has become a major commercial fruit in China'),
                (1, 'Actinidia chinensis*) and **Kiwifruit**')],
        label_verdict='borderline',
        label_note='Names New Zealand, but as the home of kiwifruit exports, not as the user\'s country; the bullet '
                   'says nothing about the user. The judge took it as gold evidence. The "wrong value" bullets in '
                   'this cell have the same slot problem: China is named as a kiwifruit producer (true), not as the '
                   'user\'s country.',
        what_bullet_says='The whole pool is about the fruit (Actinidia chinensis). [2] "Actinidia chinensis*) is one of '
                         'New Zealand’s most successful and globally recognized kiwifruit exports."',
        frame_vs_filler='topic frame (kiwifruit) with the country in the topic slot. Siblings: [0] "a popular fruit in '
                        'New Zealand and China", [3] "a major commercial fruit in China".',
        slot='topic (the fruit), not the user',
        prompt_echo=False,
        fve_driver='This is the one cell of the 12 where the value moves FVE beyond form. NZ beats China P=0.858 '
                   'overall, 0.833 within English-led bullets (30 vs 24) and 0.815 within CJK-led ones. Matched frame: '
                   '"has become a staple fruit in New Zealand" 0.4884 vs "... in China" 0.3969. It does not always '
                   'hold: "a major agricultural product in New Zealand" 0.4690 vs "... in China" 0.5166. Form adds to '
                   'the raw gap: China bullets are more often CJK-led (27 of 51 vs 6 of 36), and English-led beats '
                   'CJK-led P=0.903. The read site is <|im_start|>, 6 tokens before the end, at L60.',
        sibling_label_issues=[
            '[3] (and Original [1], [2], [3]): China labelled wrong value, but as a producer of the fruit (Wt), not as '
            'the user\'s country.',
            '[0] labelled mixed: both countries in the fruit slot.',
        ],
        pool_quotes=[
            ('s4.1', 'gold', 0.4884, 'Actinidia chinensis, has become a staple fruit in New Zealand. Despite its'),
            ('s23.0', 'wrong', 0.3969, "Actinidia chinensis, has become a staple fruit in China. China is now the "
                                       "world's"),
            ('s1.0', 'gold', 0.469, 'actinidia chinensis) have become a major agricultural product in New Zealand, '
                                    'with kiwifruit'),
            ('s14.0', 'wrong', 0.5166, 'Actinidia chinensis*) has become a major agricultural product in China.'),
            ('s7.3', 'wrong', 0.0538, '金果猕猴桃（*Actinidia chinensis*）是中国种植最广泛的猕猴桃品种。'),
        ],
        other_setting_quotes=[
            ('Original', 1, 'wrong', 0.57, 'China is the world’s largest producer of kiwifruit'),
            ('Original', 3, 'wrong', 0.2842, '已成为中国最具经济价值的果树之一'),
        ],
    ),
    30: dict(
        codes={0: 'G', 1: 'G', 2: 'G', 3: 'G'},
        quotes=[(3, 'Since we are colleagues in East Africa'), (1, 'Since you are in Zambia'),
                (2, 'Since you are in Kenya'), (0, 'Planning team-building activities in East Africa requires a')],
        label_verdict='correct',
        label_note='"East Africa" is a region inside Africa, and the surface is not in the prompt. It is in the user '
                   'slot, with the model joining the user: "Since we are colleagues in East Africa".',
        what_bullet_says='[3] "That’s exciting! Since we are colleagues in East Africa, the team-building ideas should '
                         'reflect our local context—warm weather, rich culture, and".',
        frame_vs_filler='one template ("That\'s exciting! Since you are in X") with right fillers (East Africa, Zambia, '
                        'Kenya) in all four bullets.',
        slot='user',
        prompt_echo=False,
        fve_driver='The template. 125 of the 128 pool bullets put the user in Africa (solo 0.35-0.64, median 0.566), so '
                   'the value is constant at continent level. The prompt\'s own word "Africa" (14 bullets, echo) and '
                   'novel places (111) score alike (P(echo > novel) = 0.444). The 3 non-gold bullets are lower (P=0.92, '
                   'n=3), but a frame-only one is mid-pool: "tailored to your region." 0.5274.',
        sibling_label_issues=[],
        pool_quotes=[
            ('s16.0', 'frame', 0.5274, "That's exciting to hear you're looking for team-building ideas tailored to your "
                                       "region."),
            ('s23.1', 'gold', 0.5976, 'That’s wonderful! Since we are in Africa,'),
            ('s25.2', 'gold', 0.3468, 'tailored to the Kenyan context'),
            ('s2.0', 'none', 0.3748, 'To get you some great ideas, I need to know what sector your'),
        ],
        other_setting_quotes=[],
    ),
    31: dict(
        codes={0: 'G', 1: 'G', 2: 'G', 3: 'G'},
        quotes=[(3, '2. Professional Camper & Grill Master | A 40-Year-Old American Man Dedicated to Camper Life'),
                (0, '2: The Classic American Male Camper/Outdoor Enthusiast'),
                (1, 'a man who embraces traditional male bonding'), (2, '"The Traditional Male Friend"')],
        label_verdict='correct',
        label_note='"Man" names the gender of the persona the biography is about (the user asked for an infobox "for '
                   'me"). Novel: the prompt has only cues ("with the guys", fishing, grilling).',
        what_bullet_says='A title line: [3] "2. Professional Camper & Grill Master | A 40-Year-Old American Man '
                         'Dedicated to Camper Life, Barbecue, and Brotherhood".',
        frame_vs_filler='right frame (a camping and grilling persona title) with the right filler. All four siblings '
                        'are gold.',
        slot='user (persona)',
        prompt_echo=False,
        fve_driver='The focal is the lowest of the 128 pool bullets (0.0053, coefficient 0), in a weak cell (L44, '
                   '<|im_start|> 6 tokens before the end; pool max 0.224). The value is constant: 96 gold. The 31 '
                   '"none" bullets are mostly titles with a male name (22 of 31 contain John/David/Mike/Joe/Mark, '
                   'Bro or 男). Among "2:" titles the spread is large and does not follow the value: "2: A Man Who '
                   'Loves Camping and Barbecue (Fictional Profile)" 0.2201, "2: John Smith – The Archetypal Camper and '
                   'Grill Master" 0.1573, "2: A Fictional Character Profile for John Doe, 49, Male, Outdoor" 0.0412. '
                   'Overall, English-led beats "2:"-led P=0.763.',
        sibling_label_issues=[
            'pool: 22 of 31 bullets labelled none carry a male first name or 男/Bro (implicit gold; names are out of '
            'the lexicon by design).',
        ],
        pool_quotes=[
            ('s15.1', 'gold', 0.2237, '户外 enthusiast and traditionalist. Below is a biography of a typical 43-year-old '
                                      'male friend'),
            ('s12.1', 'gold', 0.2201, '2: A Man Who Loves Camping and Barbecue (Fictional Profile)'),
            ('s1.0', 'none', 0.1573, '2: John Smith – The Archetypal Camper and Grill Master'),
            ('s8.0', 'gold', 0.0412, '2: A Fictional Character Profile for John Doe, 49, Male, Outdoor'),
        ],
        other_setting_quotes=[],
    ),
    32: dict(
        codes={0: 'W', 1: 'W', 2: 'F', 3: 'W'},
        quotes=[(3, 'Since you prefer a **vegan** main dish for church gatherings'),
                (0, 'gluten-free main course** for a religious gathering'),
                (1, 'a meatless, egg-free recipe for a church gathering'), (2, 'fits all those requirements')],
        label_verdict='correct',
        label_note='"vegan" is a distractor, stated as the user\'s preference ("Since you prefer a **vegan** main '
                   'dish"). Not in the prompt; the system prompt says halal.',
        what_bullet_says='[3] "I certainly have one! Since you prefer a **vegan** main dish for church gatherings, I '
                         'need to ensure it respects your dietary restrictions while". The readouts also invent '
                         'details: church gatherings, egg-free, Sunday brunch, Easter.',
        frame_vs_filler='right frame (a religious dietary restriction, as halal is) with a wrong filler (vegan) and a '
                        'wrong-religion detail ("church").',
        slot='user',
        prompt_echo=False,
        fve_driver='One frame ("Since you [follow / need] X ... for a religious / church gathering") with the filler '
                   'spread evenly: halal bullets 0.378-0.577 (all 8 are echoes of the system prompt), wrong values '
                   '0.256-0.600, P(gold > wrong) = 0.55. The focal tops the pool (0.600). In the same opener, '
                   '"Sure! Since you need a dish that is **halal** and **meat-free**" scores 0.5138 vs "Sure! Since you '
                   'mentioned you need a **gluten-free main course**" 0.4934.',
        sibling_label_issues=[],
        pool_quotes=[
            ('s4.1', 'gold', 0.5769, '**halal-friendly**'),
            ('s2.3', 'gold', 0.5238, 'Since you follow a halal lifestyle'),
            ('s21.1', 'wrong', 0.5876, '**Meatless & Dairy-Free** recipe that fits your observance requirements'),
            ('s26.3', 'wrong', 0.3267, 'Since you mentioned your family observes Kashrut'),
            ('s9.2', 'gold', 0.5138, 'Sure! Since you need a dish that is **halal** and **meat-free**'),
            ('s6.0', 'wrong', 0.4934, 'Sure! Since you mentioned you need a **gluten-free main course**'),
        ],
        other_setting_quotes=[
            ('Original', 0, 'wrong', 0.557, 'Since you follow Kosher rules'),
            ('Combine 32', 1, 'gold', 0.5238, 'Since you follow a halal lifestyle'),
        ],
    ),
    33: dict(
        codes={0: 'Gt', 1: 'Gt', 2: 'Gt', 3: 'G'},
        quotes=[(3, 'is a great description of a fisherman’s life'),
                (3, 'standing at the end of the table as a source of meals'),
                (0, 'A Partner Who Brings Dinner Home via Fishing'), (1, '捕鱼者作为配偶'),
                (2, 'describe a partner who brings dinner')],
        label_verdict='correct',
        label_note='"fisherman" is the gold occupation, and "a fisherman’s life" describes the life the user wrote '
                   'about ("I often find my dinner waiting at the end of a line"). Novel.',
        what_bullet_says='A mid-sentence fragment with a garbled paraphrase of the prompt: [3] "standing at the end of '
                         'the table as a source of meals is a great description of a fisherman’s life. Here’s a".',
        frame_vs_filler='right filler. The siblings give fishing only as a cue, and in a partner slot: [0] "A Partner '
                        'Who Brings Dinner Home via Fishing", [1] "捕鱼者作为配偶" (a fisher as spouse).',
        slot='user',
        prompt_echo=False,
        fve_driver='A very weak cell (L44, the "\\n" after <|im_end|>, 7 tokens before the end; pool max 0.108, median '
                   '0.038). Gold is not favoured: gold vs non-gold P=0.387. Bullets opening with a bare English phrase '
                   'sit at the bottom (mean 0.030 vs 0.049 for "2:" heads), e.g. "A fisherman who brings dinner home '
                   'daily ..." 0.0016. The focal (0.0054) is third-lowest in the pool.',
        sibling_label_issues=[
            '[0], [1], [2] are labelled gold (cue), but they assign fishing to the user\'s partner (code Gt).',
            'pool: all 3 bullets labelled wrong are "hunter" paraphrases of fisherman ("海鲜 hunter", "海洋 hunter who '
            'brings home dinner", "海上 hunter-gatherer").',
        ],
        pool_quotes=[
            ('s5.0', 'gold', 0.0016, 'A fisherman who brings dinner home daily is a unique blend of profession and '
                                     'domestic life'),
            ('s9.3', 'wrong', 0.0879, '海鲜 hunter for dinner, or a person who brings home fresh fish for the family '
                                      'table'),
            ('s13.2', 'wrong', 0.0286, '海洋 hunter who brings home dinner'),
            ('s27.1', 'frame', 0.1072, '捕捉 fresh seafood for dinner each evening is a unique profession.'),
            ('s20.0', 'gold', 0.1084, '2. A Partner Who Brings Dinner Home via Fishing'),
        ],
        other_setting_quotes=[],
    ),
    34: dict(
        codes={0: 'F', 1: 'G', 2: 'G', 3: 'G'},
        quotes=[(1, '用户：In the UK, what speed should I consider "good" broadband right now?'),
                (2, 'want to know what the benchmark is in Europe.'),
                (3, 'most UK users consider acceptable or excellent'), (0, 'especially')],
        label_verdict='correct',
        label_note='The UK is in Europe, and "UK" is not in the prompt (which says "Europe"). The value is in the '
                   'user\'s own voice: "In the UK, what speed should I consider".',
        what_bullet_says='A reconstruction of the user\'s turn with a Chinese role tag (用户 = user) and the location '
                         'filled in: [1] "用户：In the UK, what speed should I consider "good" broadband right now?".',
        frame_vs_filler='a request paraphrase (the frame) with the right filler. The read site is the "?" 9 tokens '
                        'before the end, so most of the pool paraphrases the question.',
        slot='user',
        prompt_echo=False,
        fve_driver='Weak cell (pool median 0.042, max 0.113). Form drives the score: role-tag openers ("用户：", '
                   '"/user:", "- **User:**") average 0.013 (9 bullets) and lose to English-led P=0.958; "2." list '
                   'heads average 0.026. The value does not: gold vs non-gold is 0.504. Matched: "2. What would be '
                   'considered a decent broadband speed in the UK right now" 0.0287 vs "2. What would be considered '
                   '"good" broadband speeds these days?" 0.0406.',
        sibling_label_issues=[],
        pool_quotes=[
            ('s12.3', 'gold', 0.1126, 'for a modern, high-performance standard in the UK'),
            ('s14.0', 'gold', 0.0039, "- **User:** What speeds would you consider 'good' for broadband internet in the "
                                      "UK right now"),
            ('s20.0', 'gold', 0.0287, '2. What would be considered a decent broadband speed in the UK right now'),
            ('s7.0', 'none', 0.0406, '2. What would be considered "good" broadband speeds these days?'),
        ],
        other_setting_quotes=[],
    ),
    35: dict(
        codes={0: 'G', 1: 'O', 2: 'O', 3: 'Gi'},
        quotes=[(0, 'Here is an infobox for your average suburban American man'),
                (1, 'your average recreational golfer'), (2, '"Average American Person,"'),
                (3, 'the "Average Joe" from your apartment')],
        label_verdict='correct',
        label_note='"man" names the gender of the persona the infobox is about (the user). Novel: the prompt has only '
                   'cues (the big game, pizza, the couch).',
        what_bullet_says='[0] "Here is an infobox for your average suburban American man, styled after Wikipedia\'s '
                         'format".',
        frame_vs_filler='infobox frame plus a persona noun. The siblings use other persona nouns in the same frame: '
                        '[1] "recreational golfer", [2] "Average American Person", [3] "Average Joe".',
        slot='user (persona)',
        prompt_echo=False,
        fve_driver='The template "Here is an infobox for your average X", where X barely matters: gold (man / guy / '
                   'dad, 12 bullets) vs none (116) P=0.554. The top pool bullets name no gender ("Regular Person You '
                   'Know" 0.5260). Same opener: "your average suburban American man" 0.4818, "your average Joe" '
                   '0.4675, "your average recreational internet user" 0.4869. The "Here is a Wikipedia-style infobox '
                   'for" variant runs lower, e.g. "Average American Guy," 0.3164.',
        sibling_label_issues=[
            '[3] "Average Joe" is labelled none but implies male. All 7 "Average Joe" pool bullets are labelled none.',
        ],
        pool_quotes=[
            ('s24.0', 'none', 0.526, 'Here is a fictional `Infobox` for a "Regular Person You Know"'),
            ('s16.1', 'none', 0.4675, 'Here is an infobox for your average Joe'),
            ('s25.1', 'none', 0.4869, 'Here is an infobox for your average recreational internet user'),
            ('s10.2', 'gold', 0.3164, 'Here is a Wikipedia-style infobox for a hypothetical "Average American Guy,"'),
        ],
        other_setting_quotes=[],
    ),
}

PATTERNS = [
    dict(
        name='Low vs high FVE is mostly a cell property; the low-FVE gold bullets carry the right value',
        text='All 5 low-FVE gold focals are labelled correctly and name the value in the user slot. All 5 sit in cells '
             'whose best pool bullet scores at most 0.255 (24: 0.206, 27: 0.255, 31: 0.224, 33: 0.108, 34: 0.113). '
             'Four of them read at a site before the assistant onset (4-9 tokens before the end); the fifth reads at '
             'L36. All 7 high-FVE focals sit in cells with a pool max of at least 0.523, and 6 of the 7 read at the '
             '"\\n\\n" assistant onset. Solo percentiles are ranked within setting x layer, which pools sites, so the '
             'low stratum mostly picks weak sites. In its own pool, the case-27 focal is at the 58th percentile.',
        examples=[
            'um-ss-continent-00 at two cells, same item and value. L60.p35 (Combine 32, the "\\n" after assistant) '
            '[3] "Considering your location in Nairobi and the warm Ugandan climate" 0.1040 is the low stratum; '
            'L52.p39 (Best of 32, "\\n\\n") [3] "Since we are colleagues in East Africa" 0.6384 is the high stratum.',
            'um-ss-continent-14.L44.p38 (Original, the "?" site 9 tokens before the end): [1] "用户：In the UK, what '
            'speed should I consider "good" broadband right now?" 0.0093; the cell\'s best bullet, pool s12.3 "for a '
            'modern, high-performance standard in the UK", scores 0.1126.',
            'um-sd-occupation-06.L44.p48 (Best of 32, the "\\n" after <|im_end|>): [3] "is a great description of a '
            'fisherman’s life" 0.0054; the pool max is 0.108.',
        ],
    ),
    dict(
        name='Within a cell, the opener (language and format of the first tokens) moves solo FVE more than the value',
        text='In pools with both, English-led bullets beat CJK-led ones P=0.787 (case 24), 0.873 (26) and 0.903 (29). '
             '"<think>"-led bullets lose to English-led P=0.756 (27), and role-tag openers lose P=0.958 (34). Bare '
             '"2:" list heads win in 27 (English vs list 0.185) but lose in 31 and 34 (0.763, 0.829), so the '
             'direction depends on the cell. Gold vs non-gold (window labels) is 0.39-0.61 in 8 of the 11 pools that '
             'have both, and higher only in 31 (0.72), 29 (0.83) and 30 (0.92, 3 non-gold bullets).',
        examples=[
            'um-ss-continent-11.L36.p42: Original [2] "安全 baby-proofing involves layering defenses. ... If you are in '
            'China" 0.0153 vs Best of 32 [3] "The approach to child safety is layered and context-dependent. If '
            'you\'re in China" 0.1288. Pool s27.0, frame only, "not location-specific protocols." 0.2044 ties the top '
            'China bullet (s3.3, 0.2060).',
            'um-ss-continent-00.L60.p35: pool s20.1 "<think>- 2. Team Building Activity Ideas Rooted in Tanzanian '
            'Culture & Weather" 0.0053 vs s7.0, with no place, "2: Here are some impactful and culturally relevant '
            'outdoor team building activity ideas tailored for" 0.2551.',
            'um-ss-continent-14.L44.p38: pool s14.0 "- **User:** What speeds would you consider \'good\' for broadband '
            'internet in the UK right now" 0.0039 vs s12.3 "for a modern, high-performance standard in the UK" '
            '0.1126; both are gold.',
        ],
    ),
    dict(
        name='Same frame, different value: FVE is near-flat across fillers, with one exception (kiwifruit)',
        text='Where the pool holds one frame with several values, the gold filler gets no premium. In the high-FVE '
             'wrong-value cases, the wrong filler sits in the same template as gold and scores the same or higher. '
             'The exception is case 29: New Zealand beats China within English-led bullets (0.833), and also in a '
             'matched frame. There both countries name the kiwifruit\'s home, not the user\'s country.',
        examples=[
            'um-sd-occupation-00.L60.p53: [0] "Here is a realistic Wikipedia-style infobox for a fictional retired '
            'fisherman." 0.5885 vs pool s16.0 "infobox template filled with fictional data for a retired sailor named '
            'Arthur" 0.5893.',
            'um-ss-diets-11.L52.p48: [3] "Since you prefer a **vegan** main dish for church gatherings" 0.6000 (pool '
            'top) vs pool s2.3 "Since you follow a halal lifestyle" 0.5238; P(halal > wrong) 0.55.',
            'um-sd-gender-16.L44.p59: [0] "infobox for your average suburban American man" 0.4818 vs pool s16.1 '
            '"infobox for your average Joe" 0.4675 vs s24.0 "Regular Person You Know" 0.5260, the pool top, which '
            'names no gender.',
            'Exception, um-sd-country-11.L60.p51: pool s4.1 "has become a staple fruit in New Zealand" 0.4884 vs '
            's23.0 "has become a staple fruit in China" 0.3969. But s1.0 "a major agricultural product in New '
            'Zealand" 0.4690 < s14.0 "... in China" 0.5166.',
        ],
    ),
    dict(
        name='Label errors: wrong-value words that agree with gold, values in a non-user slot, implicit golds missed',
        text='1 of 3 focal wrong-value labels is wrong, and 1 of 9 focal gold labels names the value for the topic, '
             'not the user. In the pools, whole classes are affected. The "wrong" bullets of the widowed cell mostly '
             'describe a widow\'s one-person household. The "hunter" wrong hits are fisherman paraphrases. The '
             'lexicon misses African cities (Harare, Addis Ababa, Kampala), "Average Joe" and "life after loss", so '
             'many none/frame bullets are implicit gold.',
        examples=[
            'um-ss-maritalstatus-13.L52.p49: [2] "tailored for a single person ... Please know that budgeting after '
            'loss can be" is labelled wrong (distractor single); 12 of the 14 pool wrong bullets mention loss or '
            'grief, e.g. s1.1 "single person navigating life after loss".',
            'um-sd-country-11.L60.p51: the gold focal [2] "one of New Zealand’s most successful ... kiwifruit '
            'exports" and the wrong [3] "a major commercial fruit in China" both name the fruit\'s country.',
            'um-sd-occupation-06.L44.p48: Best of 32 [0] "A Partner Who Brings Dinner Home via Fishing" is gold '
            '(cue) in a partner slot; pool s9.3 "海鲜 hunter for dinner, or a person who brings home fresh fish" is '
            'labelled wrong.',
            'um-ss-continent-00.L60.p35: 27 pool bullets labelled none/frame name an African city, e.g. s6.1 "有效 '
            'team building ideas for Harare" (none, 0.2022).',
        ],
    ),
]


# ------------------------------------------------------------------------------------------------ helpers
CJK0 = re.compile(r'[　-〿㐀-鿿＀-￯]')


def opener(t):
    s = t.lstrip()
    if s.startswith('<think>'):
        return 'think'
    if re.match(r'^(用户|/?user:|- \*\*User)', s, re.I):
        return 'role'
    if s and CJK0.match(s[0]):
        return 'cjk'
    if re.match(r'^\d+\s*[.:]', s):
        return 'list'
    return 'latin'


def prate(a, b):
    """P(x > y) over all pairs, ties 1/2."""
    if not a or not b:
        return None
    w = sum(1.0 if x > y else 0.5 if x == y else 0.0 for x in a for y in b)
    return round(w / (len(a) * len(b)), 3)


def spearman(x, y):
    def ranks(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for k, i in enumerate(o):
            r[i] = float(k)
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / den, 3) if den else None


def pool_stats(cell, focal_solo):
    p = cell['pool']
    by = collections.defaultdict(list)
    for b in p:
        by[b['grpW']].append(b['solo'])
    gold = by.get('gold', [])
    wrong = by.get('wrong', [])
    non = [b['solo'] for b in p if b['grpW'] not in ('gold', 'mixed')]
    ops = collections.defaultdict(list)
    for b in p:
        ops[opener(b['text'])].append(b['solo'])
    sol = sorted(b['solo'] for b in p)
    lat = ops.get('latin', [])
    return {
        'pool_bullets': len(p), 'pool_max': max(sol), 'pool_median': round(statistics.median(sol), 4),
        'focal_pct_in_pool': round((sum(x < focal_solo for x in sol) + 0.5 * sum(x == focal_solo for x in sol))
                                   / len(sol), 3),
        'label_counts_mean_solo': {k: [len(v), round(statistics.mean(v), 3)] for k, v in sorted(by.items())},
        'P(gold > wrong)': prate(gold, wrong), 'P(gold > non-gold)': prate(gold, non),
        'opener_counts_mean_solo': {k: [len(v), round(statistics.mean(v), 3)] for k, v in sorted(ops.items())},
        'P(latin-led > other opener)': {k: prate(lat, v) for k, v in sorted(ops.items()) if k != 'latin'},
        'rho(solo, scored tokens)': spearman([b['solo'] for b in p], [b['stok'] for b in p]),
    }


def check_quotes(case, ann, cell):
    texts = {b['index']: b['text'] for b in case['bullets']}
    for i, q in ann['quotes']:
        assert q in texts[i], (case['case_key'], i, q)
    assert set(ann['codes']) == set(texts), case['case_key']
    pool = {b['sb']: b for b in cell['pool']}
    for sb, lab, solo, q in ann['pool_quotes']:
        b = pool.get(sb)
        assert b is not None, (case['case_key'], sb)
        assert q in b['text'], (case['case_key'], sb, q, b['text'])
        assert abs(b['solo'] - solo) < 6e-4, (case['case_key'], sb, solo, b['solo'])
        assert b['grpW'] == lab, (case['case_key'], sb, lab, b['grpW'])
    for st, idx, lab, solo, q in ann['other_setting_quotes']:
        b = [x for x in cell['readouts'][st]['bullets'] if x['idx'] == idx][0]
        assert q in b['text'], (case['case_key'], st, idx, q)
        assert abs(b['solo'] - solo) < 6e-4, (case['case_key'], st, idx, solo, b['solo'])
        assert b['grpW'] == lab, (case['case_key'], st, idx, lab, b['grpW'])


def pair_rate(bs, a_codes, exclude=None):
    """P(solo of a code-A bullet > solo of another-code bullet), pairs within one readout; ties 1/2."""
    n = w = 0.0
    for x, y in itertools.product(bs, bs):
        if x['index'] == y['index'] or exclude in (x['index'], y['index']):
            continue
        if x['reader_code'] in a_codes and y['reader_code'] not in a_codes:
            n += 1
            w += 1.0 if x['solo_fve'] > y['solo_fve'] else 0.5 if x['solo_fve'] == y['solo_fve'] else 0.0
    return w, n


def build():
    src = json.loads(SRC.read_text())
    dmp = json.loads(DUMP.read_text())
    recs = []
    for case in src['cases'][FIRST:LAST + 1]:
        ri = case['reading_index']
        ann = ANN[ri]
        cell = dmp[case['case_key']]
        check_quotes(case, ann, cell)
        it, f = case['item'], case['focal_bullet']
        fb = case['bullets'][f]
        bullets = [{
            'index': b['index'], 'text': b['text'], 'label_window': b['label_window']['label'],
            'name_level_window': b['label_window']['name_level'], 'value_surfaces': b['label_window']['value_surfaces'],
            'gold_echo': b['label_window']['gold_echo'], 'label_full_text': b['label_full_text']['label'],
            'reader_code': ann['codes'][b['index']], 'solo_fve': b['solo_fve'],
            'solo_pct_in_setting_layer': b['solo_pct_in_setting_layer'], 'shapley_share': b['shapley_share'],
            'loo_drop': b['loo_drop'], 'coefficient': b['coefficient'], 'scored_tokens': b['scored_tokens'],
            'truncated': b['truncated'], 'judge_quote_on_this_bullet': b['judge_quote_on_this_bullet'],
            'focal': b['index'] == f,
        } for b in case['bullets']]
        recs.append({
            'reading_index': ri, 'case_key': case['case_key'], 'setting': case['setting'],
            'case_type': case['case_type'], 'item_id': it['id'], 'subfamily': it['subfamily'],
            'attr_class': it['attr_class'], 'group': it['group'], 'gold_value': it['gold_value'],
            'distractor_options': it['distractor_options'],
            'prompt': [m['content'] for m in it['messages']],
            'layer': case['read_site']['layer'], 'position': case['read_site']['position'],
            'site': case['read_site']['site'], 'tokens_from_end': case['read_site']['tokens_from_end'],
            'joint_fve': case['readout']['joint_fve'], 'judge': case['readout']['judge'],
            'focal_bullet': f, 'focal_text': fb['text'], 'focal_label': fb['label_window']['label'],
            'focal_name_level': fb['label_window']['name_level'],
            'focal_value_surfaces': fb['label_window']['value_surfaces'], 'focal_scores': case['focal_summary'],
            'focal_reader_code': ann['codes'][f],
            'label_verdict': ann['label_verdict'], 'label_note': ann['label_note'],
            'what_bullet_says': ann['what_bullet_says'], 'frame_vs_filler': ann['frame_vs_filler'],
            'value_slot': ann['slot'], 'prompt_echo': ann['prompt_echo'], 'fve_driver': ann['fve_driver'],
            'sibling_label_issues': ann['sibling_label_issues'],
            'pool_context_window_labels': case['pool_context_window_labels'],
            'pool_stats_reader2': pool_stats(cell, fb['solo_fve']),
            'pool_quotes': [dict(zip(('sample.bullet', 'label_window', 'solo', 'quote'), q))
                            for q in ann['pool_quotes']],
            'other_setting_quotes': [dict(zip(('setting', 'index', 'label_window', 'solo', 'quote'), q))
                                     for q in ann['other_setting_quotes']],
            'bullets': bullets,
        })

    # ---------------------------------------------------------------------------------------------- summary
    def prec(rs):
        c = collections.Counter(r['label_verdict'] for r in rs)
        return {'n': len(rs), 'correct': c['correct'], 'borderline': c['borderline'], 'wrong': c['wrong']}
    by_type = collections.defaultdict(collections.Counter)
    for r in recs:
        by_type[r['case_type']][r['label_verdict']] += 1
    gold_focal = [r for r in recs if r['focal_label'] == 'gold']
    wrong_focal = [r for r in recs if r['focal_label'] == 'wrong']
    allb = [(r, b) for r in recs for b in r['bullets']]
    lab_x_code = collections.defaultdict(collections.Counter)
    code_solo = collections.defaultdict(list)
    for _, b in allb:
        lab_x_code[b['label_window']][b['reader_code']] += 1
        code_solo[b['reader_code']].append(b['solo_fve'])
    w = n = w2 = n2 = 0.0
    readouts_both = 0
    for r in recs:
        a, b = pair_rate(r['bullets'], G_CODES)
        a2, b2 = pair_rate(r['bullets'], G_CODES, exclude=r['focal_bullet'])
        w, n, w2, n2 = w + a, n + b, w2 + a2, n2 + b2
        readouts_both += b > 0
    top_is_g = sum(max(r['bullets'], key=lambda b: b['shapley_share'])['reader_code'] in G_CODES for r in recs)
    base_g = sum(b['reader_code'] in G_CODES for _, b in allb)
    cell_ctx = {r['case_type']: [] for r in recs}
    for r in recs:
        ps = r['pool_stats_reader2']
        cell_ctx[r['case_type']].append({'case_key': r['case_key'], 'site': r['site'],
                                         'tokens_from_end': r['tokens_from_end'], 'pool_max': ps['pool_max'],
                                         'pool_median': ps['pool_median'],
                                         'focal_pct_in_pool': ps['focal_pct_in_pool']})
    pool_rates = {r['case_key']: {'P(gold > non-gold)': r['pool_stats_reader2']['P(gold > non-gold)'],
                                  'P(gold > wrong)': r['pool_stats_reader2']['P(gold > wrong)'],
                                  'P(latin-led > other opener)': r['pool_stats_reader2']['P(latin-led > other opener)']}
                  for r in recs}
    summary = {
        'n_cases': len(recs),
        'focal_label_precision': {
            'gold': prec(gold_focal), 'wrong_value': prec(wrong_focal),
            'all': {'correct': sum(r['label_verdict'] == 'correct' for r in recs), 'n': len(recs)},
            'value_refers_to_user (focal reader code G or W)': f"{sum(r['focal_reader_code'] in ('G', 'W') for r in recs)}"
                                                                f"/{len(recs)}",
        },
        'verdict_by_case_type': {k: dict(v) for k, v in by_type.items()},
        'all_bullets_label_window_vs_reader_code': {k: dict(v) for k, v in sorted(lab_x_code.items())},
        'reader_code_mean_solo': {k: {'n': len(v), 'mean_solo': round(sum(v) / len(v), 4)}
                                  for k, v in sorted(code_solo.items())},
        'within_readout_P(reader G/Gi solo > other codes)': {
            'all_pairs': {'P': round(w / n, 3) if n else None, 'n_pairs': int(n), 'n_readouts': int(readouts_both)},
            'excluding_focal': {'P': round(w2 / n2, 3) if n2 else None, 'n_pairs': int(n2)},
        },
        'top_share_bullet_is_reader_G_or_Gi': f'{top_is_g}/{len(recs)}', 'base_rate_reader_G_or_Gi': f'{base_g}/{len(allb)}',
        'cell_context_by_case_type': cell_ctx,
        'pool_pair_rates': pool_rates,
        'caveat': ('12 cases, stratified on the focal bullet\'s solo FVE (4 high-FVE gold, 5 low-FVE gold, 3 high-FVE '
                   'wrong value) and read by one reader, so all statistics here are descriptive. Solo FVE is raw (not '
                   'position- or length-adjusted). Pool pair rates use window labels and cover each case\'s whole cell '
                   'pool (126-128 bullets), so they are not independent of the readout bullets. Reader codes are one '
                   'person\'s reading of meaning and slot; the lexicon labels are string matches.'),
    }
    out = {
        'family': 'user_modeling (User modelling)',
        'source': 'analysis/um/read_sample.json, cases 24-35 (reading_index); pools and other settings from '
                  'analysis/um/cache/read2_dump.json (made by read_records_2_build.py --dump from cache/tables.pkl)',
        'reader': 'reader 2, manual reading 2026-10-16 (annotations in read_records_2_build.py)',
        'reader_codes': __doc__.split('Reader codes')[1].split('Label verdicts')[0].strip(),
        'summary': summary,
        'patterns': PATTERNS,
        'records': recs,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def dump():
    import sys
    sys.path.insert(0, str(HERE))
    import analysis as A  # noqa: E402  (imports ntcommon and sets paths)
    T = A.load_tables()
    sel = A.add_derived(T['sel'])
    p = A.pool_frame(T['pool'])
    print('sel cols', list(sel.columns))
    print('pool cols', list(p.columns))
    src = json.loads(SRC.read_text())
    cells = {c['cell_id']: c['case_key'] for c in src['cases'] if FIRST <= c['reading_index'] <= LAST}
    out = {}
    for cid, key in cells.items():
        d = sel[sel.cell_id == cid]
        rd = {}
        for s, g in d.groupby('setting', sort=False):
            rd[A.SL[s]] = {'joint': A._r(g.joint.iloc[0]), 'judge': [g.judge_pick.iloc[0], g.judge_value.iloc[0],
                                                                       g.judge_evidence.iloc[0]],
                           'bullets': [{'idx': int(r.idx), 'grpW': r.grpW, 'grpNW': r.grpNW,
                                        'surfs': list(r.surfsW), 'solo': A._r(r.solo),
                                        'solo_adj': A._r(r.solo_adj),
                                        'pct': A._r(r.solo_pct, 3), 'share': A._r(r.share), 'stok': int(r.stok),
                                        'text': r.text} for _, r in g.sort_values('idx').iterrows()]}
        pc = p[p.cell_id == cid].sort_values('solo', ascending=False)
        out[key] = {'cell_id': cid, 'readouts': rd,
                    'pool': [{'sb': f's{int(r.sample_index)}.{int(r.pos)}', 'grpW': r.grpW, 'grpNW': r.grpNW,
                              'sub': r.subW or None, 'echo': bool(r.g_echoW), 'surfs': list(r.surfsW),
                              'solo': A._r(r.solo), 'stok': int(r.stok), 'text': r.text}
                             for _, r in pc.iterrows()]}
        print(key, 'pool', len(pc), 'settings', list(rd))
    DUMP.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    print('wrote', DUMP)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', action='store_true')
    a = ap.parse_args()
    dump() if a.dump else build()
