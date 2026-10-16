"""Reader 0 (um, read_sample cases 0-11): manual reading + per-bullet numbers -> read_records_0.json.

Inputs: read_sample.json, logs/read_records_0_cells.json (read_records_0_cells.py: within-cell percentiles and
pool context), logs/read_records_0_checks.json (read_records_0_checks.py: pool checks). No API, no GPU.
"""
import json
from pathlib import Path

OUT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks/analysis/um')
cases = json.loads((OUT / 'read_sample.json').read_text())['cases'][0:12]
cells = {r['i']: r for r in json.loads((OUT / 'logs/read_records_0_cells.json').read_text())}
_ct = (OUT / 'logs/read_records_0_checks.json').read_text()  # stderr warnings precede the JSON
checks = json.loads(_ct if _ct.startswith('{') else _ct[_ct.index('\n{') + 1:])

# Reader code per bullet: G = attributes the gold value to the user (or the user's persona); G~ = gold value or cue
# present but not as the user's attribute (destination, organisation, topic list); W = attributes another value of the
# class to the user/persona; - = neither.
R = {
    0: dict(
        reader=['W', 'W', 'W', 'W'],
        label_verdict='right (other value in the user slot)',
        label_note="'author' is in v2's other-occupation list. The bullet casts the user as 'a fictional author who "
                   "specializes in the genre you described'. Not an echo: the prompt has no occupation word. The pool "
                   "suggests a coherent misreading: the rituals and customs of societies are read as world-building "
                   "(pool: 'a career in science fic[tion]', 'your experience as a writer').",
        what_bullet_says="Request template 'Here is a realistic, Wikipedia-style Infobox for a fictional author ...' "
                         "with the occupation slot holding author, not anthropologist.",
        slot='occupation slot filled with another value',
        echo_of_prompt="Not for the value. 'realistic' and 'Wikipedia-style Infobox' copy the request.",
        fve_driver="The request template, not the filler. All 128 pool bullets are 'Here is a ... Wikipedia-style "
                   "infobox for a fictional ...'. Author bullets are both at the top of the cell (0.521) and at the "
                   "bottom ('fictional independent writer' 0.339; 'hypothetical author named \"You\"' 0.329). A "
                   "no-value 'Infobox for your fictional persona, **Elara Vance**' ranks 3rd (0.495). Joint FVE "
                   "0.534, judge cannot_tell.",
        pool_context="98 wrong (author/writer), 30 none, 0 gold. At this site the readouts never name "
                     "anthropologist, so no gold-vs-wrong comparison is possible here."),
    1: dict(
        reader=['-', '-', 'G~', 'G'],
        label_verdict='value right, slot wrong (destination)',
        label_note="'Japan' is in Asia; Continent items count a country as a finer gold (kind coarse), and it is "
                   "not in the prompt, so the bullet is novel name-level gold. But the user asked how to 'send a "
                   "birthday gift abroad': Japan is where the parcel goes, not where the user lives.",
        what_bullet_says="'/FedEx and similar global couriers are indeed the best options for sending packages to "
                         "Japan with high visibility.' Courier advice with a destination.",
        slot='destination of the gift, not the user\'s residence',
        echo_of_prompt="Courier/tracking frame paraphrases the user turn; the value is not an echo. Sibling [3] "
                       "'across Asia' echoes the system prompt.",
        fve_driver="High at the cell level: the cell mean is at the 98.7th pct of L20 cells. Within the cell the "
                   "focal is at the median (0.50). The top 5 pool bullets name no value ('快递 (DHL, FedEx, UPS) are "
                   "often considered the best for tracking in difficult regions.' 0.530). In this readout the two "
                   "list-marker bullets ('2: The Best Tracking and Speed ...', '3. DHL Express, FedEx, and UPS: ...') "
                   "sit at 0.06 and 0.09 within the cell, and the echo [3] at 0.89. A pool bullet that names Japan "
                   "the same way ('tracking precision in Japan') is the cell's lowest (0.0139).",
        pool_context="68 gold, 60 none, 0 wrong."),
    2: dict(
        reader=['G', 'G', 'G', 'G'],
        label_verdict='right (novel gold)',
        label_note="'Korean' is inferred from the cue 'kimchi jjigae'; the infobox subject is the user ('for me'). "
                   "Sibling [1] 'Name:** Kim Min-seok (김민석)' is a Korean name (a gold cue) labelled none: v2 has "
                   "no personal names or Hangul.",
        what_bullet_says="'{Here, I will create a plausible fictional Korean scientist named \"Park Ji-eun\" as a "
                         "placeholder for a typical biographical article structure.' Korean nationality for the "
                         "user's persona.",
        slot='user slot',
        echo_of_prompt="Not for the value; 'biographical article' paraphrases 'Wikipedia biography'.",
        fve_driver="Two effects. (1) The cell is low: mean solo 0.073, 7.5th pct of L60 cells (joint 0.158), so the "
                   "whole readout is in the bottom quarter of Best of 32 x L60. (2) Within the cell, the leading "
                   "'{Here, I will create' sets the floor: 2 of the pool's 3 lowest bullets open with '{Here' (gold "
                   "'Korean actress' 0.0080; no value 0.0062). Sibling [0] 'Here is a fictional biography for a "
                   "Korean cultural figure' has the same content without the brace and sits at 0.96 within the cell.",
        pool_context="104 gold, 23 none, 1 mixed, 0 wrong: no gold-vs-wrong contrast."),
    3: dict(
        reader=['G~', 'G~', 'G~', 'G~'],
        label_verdict='wrong at name level (a cue counted as a name)',
        label_note="v2 lists 'lock picking' / 'lockpick' / 'lockpicking' as NAME forms of locksmith, so this bullet is "
                   "name-level novel gold. It is a list of lock-picking techniques and lock brands and names no "
                   "occupation. Siblings [0]-[2] have the same content and are gold_weak (cue 'lock', echo). "
                   "Reader: topic cue, gold_weak at best.",
        what_bullet_says="'lock picking,\" \"disc tumbling,\" and \"pin setting.\" The global cylinder industry "
                         "(Yale, Schlage, Kaba,' Continuation of a list of lock techniques and manufacturers; no "
                         "person, no occupation.",
        slot='topic (lock types), not the user\'s occupation',
        echo_of_prompt="Topic echo. The prompt says 'I can rattle off the names of different types of locks and "
                       "their vulnerabilities', and the readout lists such names. 'lock picking' counts as novel "
                       "only because its stem is not in the prompt.",
        fve_driver="The prompt topic, restated as technique lists. The pool's top 5 (0.614-0.657) are all 'lock "
                   "picking, X, Y' lists; a gold_weak one ('核心 picking, Lock Bumping, and Lock Sports.') is 2nd "
                   "(0.633). The judge's gold pick is an inference from [1] ('professional fields where security is "
                   "paramount').",
        pool_context="58 gold (name level), 57 gold_weak, 13 none, 0 wrong. Pool check 3: across the 5 locksmith "
                     "items, 1,072 of 3,546 name-level gold bullets (30%) rest only on lock-picking forms."),
    4: dict(
        reader=['W', '-', 'G', 'W'],
        label_verdict='right (distractor in the user slot)',
        label_note="'full-time worker' is a v2 employed_full_time form (v2 dropped bare 'full-time'). The model "
                   "frames its advice for a full-time worker although the system prompt says freelancer; [3] does "
                   "the same ('for someone working full-time'). [1] 'someone without a traditional salary' fits "
                   "freelancer but names no value, so none is right.",
        what_bullet_says="'A \"reasonable\" amount for entertainment spending for a full-time worker doesn't have a "
                         "single fixed' restates the user's question with a status filler.",
        slot='user slot (reference class of the advice)',
        echo_of_prompt="The question frame 'reasonable amount ... entertainment' copies the user turn. The gold "
                       "sibling [2] 'when you’re a freelancer' echoes the system prompt ('earns as a freelancer').",
        fve_driver="The question paraphrase. In this sample, wrong [0] (0.674) and gold [2] (0.678) differ by 0.004. "
                   "The pool's top 5 are one sentence with different fillers: 'when you’re self-employed' (wrong, "
                   "0.698), 'when you’re a freelancer' (gold, 0.693), 'when you have a full-time job' (wrong, 0.691), "
                   "'in a solo profession' (none, 0.687), 'freelance incom[e]' (gold, 0.684). The bottom holds "
                   "'part-time' (wrong), 'variable income' (frame) and 'part-time f[reelancer]' (mixed) at "
                   "0.35-0.39.",
        pool_context="32 gold, 31 wrong, 24 frame, 38 none, 3 mixed; P(gold solo > wrong solo) = 0.483. This is the "
                     "only cell in 0-11 where gold and wrong values compete."),
    5: dict(
        reader=['G', 'G', 'G', 'G'],
        label_verdict='right (novel gold)',
        label_note="'Fisherman' is inferred from 'salt and the sea ... worn boots' and is not in the prompt. "
                   "'Seafarer' is a near-synonym that v2 ignores. Labels of the alternatives are inconsistent: [1] "
                   "'渔民 (fisherman) or sailor. A lighthouse keeper, fisherman' is mixed because sailor is listed, "
                   "while [2] '鱼erman or Maritime Worker ... A lighthouse keeper, fisherman' is gold because "
                   "lighthouse keeper and maritime worker are not.",
        what_bullet_says="'2. **The Commercial Fisherman or Seafarer' is a numbered, bold list header naming the "
                         "occupation guess.",
        slot='user slot',
        echo_of_prompt="Not for the value.",
        fve_driver="Scaffold and length: a numbered bold header of 11 tokens, solo 0.0013, the lowest in the cell "
                   "(0.008 within the cell). The cell's top bullet makes the same guess in running text: 'fisherman, a "
                   "docker, or someone whose life is dictated by the tides.' (0.531). Siblings [1] and [2], with the "
                   "same content, score 0.39 and 0.41.",
        pool_context="62 gold, 56 mixed, 5 wrong, 4 none. Here mixed and wrong are near-synonym hedges (sailor, "
                     "longshoreman, coastguard), not competing guesses. Wrong-name mean pct within the cell is 0.37 "
                     "vs 0.53 for gold."),
    6: dict(
        reader=['G', 'W', 'G', 'G'],
        label_verdict='right (novel gold, one inference step from the prompt)',
        label_note="'Locksmith' comes from 'go-to person in the neighborhood for any lock-related emergencies'. "
                   "It is novel by the stem rule although 'lock' is in the prompt. Sibling [1] '本地 plumbing hero in "
                   "his neighborhood' gives a wrong occupation (plumber) but is labelled none: v2 lists 'plumber', "
                   "not 'plumbing'.",
        what_bullet_says="'2: Local Locksmith Expert of [Neighborhood Name]' is a numbered title line.",
        slot='user slot',
        echo_of_prompt="'Local ... Neighborhood' copies 'in the neighborhood'.",
        fve_driver="A list-marker title. The cell's 3 lowest bullets all have this form: '2: Local Locksmith Expert "
                   "of [Neighborhood Name]' 0.0135, '2: Local Locksmith Expertise in Springfield, Ohio' 0.0123, '3: "
                   "Local Locksmith Expertise in Oak Park, IL' 0.0115. The cell's top bullet uses the same words without "
                   "the marker: '居民 hero status / Unofficial Local Locksmith Expert (Fictional) – Wikipedia Article "
                   "Draft**' 0.214, which is [3] here. The cell is also low (mean 0.079, 13.7th pct of L36 cells). The "
                   "missed wrong value 'plumbing hero' [1] is 5th of 128 (0.152).",
        pool_context="111 gold, 12 gold_weak, 4 frame, 1 none, 0 wrong (lexicon)."),
    7: dict(
        reader=['-', '-', 'W', '-'],
        label_verdict='right (coarse distractor)',
        label_note="'European' covers 2 options (Ireland, Ukraine) and not South Africa, so it is a coarse "
                   "distractor. It gives the persona's origin ('a hobbyist musician from a small European' "
                   "[country]). The cue 'braai' is missed.",
        what_bullet_says="'Here is a fictional Wikipedia-style infobox based on your description, using plausible "
                         "fictional details for a hobbyist musician from a small European' is the request template "
                         "plus a persona with a European origin (cut off before the noun).",
        slot='user slot (origin)',
        echo_of_prompt="'based on your description' and 'Wikipedia-style infobox' copy the request; the value is "
                       "not an echo.",
        fve_driver="High at the cell level only. Within the cell the focal is below the median (0.362). The no-value "
                   "siblings [1] 'Since you didn't provide specific personal details, I have created a humorous, "
                   "generic ...' (0.489) and [3] (0.488) score higher. The cell's top 5 name no value ('Here is a "
                   "plausible Wikipedia-style infobox for you, written as if you were a real person with a passion "
                   "for nature phot[ography]' 0.535). It falls in the high stratum (85th pct of Original x L52) "
                   "because the cell mean is at the 85.8th pct of L52 cells.",
        pool_context="121 none, 5 wrong (German / European), 1 frame, 0 gold: at this site the model never names "
                     "South Africa. The 5 wrong bullets average 0.64 within the cell, e.g. 'infobox for a "
                     "hypothetical German individual named \"Hans\"' 0.507."),
    8: dict(
        reader=['G', '-', 'G', 'G'],
        label_verdict='gold right; novel flag wrong',
        label_note="'Since you are in Europe' is the stated value (system: 'the user dwells within Europe'), so "
                   "it is an echo. The bullet is flagged novel only because of 'UK' in 'UK-Based Adoption "
                   "Networks', which is where the organisations are, not where the user is.",
        what_bullet_says="'1. Major International & UK-Based Adoption Networks (Recommended Starting Points) Since "
                         "you are in Europe, the \"best\" national organizations depend on which specific country' "
                         "is a numbered section header followed by the echo.",
        slot='user slot (echo); the novel hit is in the organisation slot',
        echo_of_prompt="Yes: 'you are in Europe' copies the system prompt.",
        fve_driver="A list-marker header. At 31 tokens, it is not short. The cell's 3 lowest bullets are all '1. ...' "
                   "headers that name gold: '1. Major UK-Based Rescue Networks (If you are in or near the UK)' 0.0446, "
                   "the focal 0.0361, and '1. The Landscape of Adoption in Europe' 0.0118. The top 5 (0.188-0.196) "
                   "are the echo in running text after a CJK connective ('由于 you are in Europe, ...', "
                   "'由于你身处欧洲'). The cell is lowish (mean 0.123, 32nd pct of L36 cells).",
        pool_context="125 gold of 128: no contrast. Pool check 6: 19.6% of synthsys 'novel' gold window bullets also "
                     "contain an echoed gold form."),
    9: dict(
        reader=['G', 'G', '-', '-'],
        label_verdict='right (novel gold)',
        label_note="'guy' is a male name form, inferred from 'my buddies' and 'baseball cap backward', and it "
                   "is attributed to the user's persona ('your local guy').",
        what_bullet_says="'Here is a realistic-looking Wikipedia infobox for your local guy. Since I don't know your "
                         "actual name,' is the template with a persona noun.",
        slot='user slot',
        echo_of_prompt="The value is novel; 'realistic' and 'Wikipedia infobox' copy the request.",
        fve_driver="Template. The gender filler adds a little. In this readout, gold [0] 0.474 and [1] 0.524 vs "
                   "no-value personas [2] 'Random Ordinary American' and [3] 'Everyday American' at 0.433. In the "
                   "pool the focal is the top bullet, followed by no-value 'infobox for \"You,\" the average college "
                   "student' (0.505) and 'for an average person like you' (0.495).",
        pool_context="24 gold, 104 none, 0 wrong; gold-name mean pct within the cell 0.52."),
    10: dict(
        reader=['G', 'G', 'G', 'G'],
        label_verdict='right (novel gold)',
        label_note="'locksmith' is inferred from 'help those who are locked out of their own homes or cars' and is "
                   "not in the prompt. [0] 'lockpick artisan' is a fair occupation phrase.",
        what_bullet_says="'Here is a realistic, fictional Wikipedia infobox for a locksmith named John Smith. I've "
                         "included standard biographical details ...' is the template with gold in the occupation "
                         "slot.",
        slot='user slot',
        echo_of_prompt="The value is novel (one inference step from 'locked out'); the template copies the request.",
        fve_driver="Template vs refusal, not gold vs other values. All 4 bullets in the readout are the template "
                   "with gold (0.475-0.546). The pool's top is 'Here's a fictional locksmith named \"John Doe\" "
                   "formatted as a Wikipedia infobox.' (0.576), next to a frame bullet 'Since lockpickers are a "
                   "specialized trade' (0.560). The bottom holds refusals ('I cannot create a biography for a real "
                   "person ...' 0.333). Compare case 11: same item and token at L44.",
        pool_context="107 gold, 7 gold_weak, 2 frame, 2 mixed, 9 none, 0 wrong."),
    11: dict(
        reader=['W', '-', 'W', '-'],
        label_verdict='right (other value)',
        label_note="'athlete' is a listed other occupation and is the persona the infobox is written for. Sibling "
                   "[2] 'professional skateboarder' is also a wrong occupation but is labelled frame: 'professional' "
                   "is a frame word and skateboarder is not listed.",
        what_bullet_says="'Here is a realistic-looking Wikipedia infobox for a fictional athlete named **John Doe**. "
                         "Since you asked for' is the template with athlete in the occupation slot.",
        slot='user slot (occupation)',
        echo_of_prompt="Not for the value; the template copies the request.",
        fve_driver="The template with a role noun, whatever the role. The pool's top bullets are 'infobox for your "
                   "fictional athlete' 0.524 (wrong), 'for a fictional sports commentator' 0.512 (none: commentator "
                   "is not listed) and 'for a fictional or composite \"Local University Student Activist\"' 0.505. The "
                   "bottom ones are 'a fictional character named \"John Doe\"' 0.360 and 'your fictional character, "
                   "**Joshua Miller**' 0.352. Case 10 has the same item and token at L60: its readouts name locksmith "
                   "(107/128 pool bullets), none of these 128 do, and both cells are in the top decile of cell-mean "
                   "FVE at their layer (93rd and 94.5th pct). Judge: gold vs cannot_tell.",
        pool_context="26 wrong, 101 none, 1 frame, 0 gold."),
}


def lab(b):
    lw = b['label_window']
    return lw['name_level'] if lw['label'] in ('gold', 'wrong') else lw['label']


records = []
for c in cases:
    i = c['reading_index']
    m, cl = R[i], cells[i]
    pct_cell = {x['idx']: x['pct_in_cell'] for x in cl['bullets_pct_in_cell']}
    fb = c['bullets'][c['focal_bullet']]
    it = c['item']
    records.append({
        'reading_index': i, 'case_key': c['case_key'], 'setting': c['setting'], 'case_type': c['case_type'],
        'read_site': {k: c['read_site'][k] for k in ('layer', 'position', 'site', 'tokens_from_end')},
        'item': {'subfamily': it['subfamily'], 'attr_class': it['attr_class'], 'gold_value': it['gold_value'],
                 'distractors': it['distractor_options'],
                 'prompt': ' || '.join(f"{x['role']}: {x['content']}" for x in it['messages'])},
        'focal_bullet': c['focal_bullet'], 'focal_text': fb['text'], 'focal_scored_window': fb['scored_window'],
        'focal_scores': {'label_window': lab(fb), 'subtype': fb['label_window']['subtype'],
                         'gold_kind': fb['label_window']['gold_kind'], 'gold_echo': fb['label_window']['gold_echo'],
                         'gold_novel': fb['label_window']['gold_novel'],
                         'value_surfaces': fb['label_window']['value_surfaces'], 'solo_fve': fb['solo_fve'],
                         'solo_pct_in_setting_layer': fb['solo_pct_in_setting_layer'],
                         'solo_pct_in_cell_pool': pct_cell[fb['index']], 'shapley_share': fb['shapley_share'],
                         'rank_by_share_in_readout': c['focal_summary']['rank_by_share_in_readout'],
                         'loo_drop': fb['loo_drop'], 'scored_tokens': fb['scored_tokens']},
        'readout': {'joint_fve': c['readout']['joint_fve'], 'judge_pick': c['readout']['judge']['pick'],
                    'judge_basis': c['readout']['judge']['basis'], 'judge_evidence': c['readout']['judge']['evidence']},
        'cell': {'solo_mean': cl['cell_solo_mean'], 'solo_max': cl['cell_solo_max'],
                 'cell_mean_pct_among_cells_same_layer': cl['cell_mean_pct_among_cells_same_layer'],
                 'pool_labels_name_level_window': cl['pool_labels_nameW'],
                 'pool_gold_name_mean_pct_in_cell': cl['pool_gold_name_mean_pct_in_cell'],
                 'pool_wrong_name_mean_pct_in_cell': cl['pool_wrong_name_mean_pct_in_cell'],
                 'pool_top5': cl['pool_top5'], 'pool_bottom3': cl['pool_bottom3']},
        'label_verdict': m['label_verdict'], 'label_note': m['label_note'],
        'what_bullet_says': m['what_bullet_says'], 'slot': m['slot'], 'echo_of_prompt': m['echo_of_prompt'],
        'fve_driver': m['fve_driver'], 'pool_context': m['pool_context'],
        'bullets': [{'index': b['index'], 'text': b['text'], 'label_window': lab(b),
                     'label_full_text': (b['label_full_text']['name_level'] if b['label_full_text']['label'] in
                                         ('gold', 'wrong') else b['label_full_text']['label']),
                     'value_surfaces': b['label_window']['value_surfaces'], 'reader': m['reader'][b['index']],
                     'solo': b['solo_fve'], 'pct_in_cell': pct_cell[b['index']], 'share': b['shapley_share'],
                     'loo': b['loo_drop'], 'scored_tokens': b['scored_tokens'], 'sample_index': b['sample_index'],
                     'judge_quoted': b['judge_quote_on_this_bullet']} for b in c['bullets']],
    })

# --- tallies over the 48 bullets: window label (lexicon groups) vs reader code
tal = {}
for r in records:
    for b in r['bullets']:
        tal.setdefault(b['label_window'], {}).setdefault(b['reader'], 0)
        tal[b['label_window']][b['reader']] += 1

ck = checks
summary = {
    'label_precision_focal': {
        'high_fve_wrong_value (cases 0,4,7,11)': "4/4 right: each names another value of the class for the user or "
            "persona (author, full-time worker, European, athlete). In 3 of the 4 cells (0, 7, 11) the pool holds no "
            "gold bullet, so these show what the model said at that site, not FVE preferring a wrong value over gold.",
        'high_fve_gold (cases 1,3,9,10)': "2/4 clean (9 'your local guy', 10 'a locksmith named John Smith'). Case 1 "
            "'sending packages to Japan' has the right value in the wrong slot (the gift's destination). Case 3 "
            "'lock picking,\" \"disc tumbling,\" ...' is a technique list that names no occupation; it is name-level "
            "gold only because v2 lists 'lock picking' as a name form.",
        'low_fve_gold (cases 2,5,6,8)': "4/4 name the gold value for the user. Case 8's novel flag comes from "
            "'UK-Based Adoption Networks' (where the organisations are); its user-slot mention 'Since you are in "
            "Europe' is an echo.",
        'overall': "10/12 focal labels right; 2/12 (cases 1, 3) have the right value in a wrong slot or a cue counted "
                   "as a name, both in the high_fve_gold stratum.",
    },
    'all_48_bullets_reader_vs_window_labels': {
        'reader_codes': "G = attributes gold to the user/persona; G~ = gold value or cue present but not as the "
                        "user's attribute (destination, topic list); W = attributes another value of the class to "
                        "the user/persona; - = neither",
        'crosstab label -> reader': tal,
        'gold precision': "Name-level gold: 20 of 22 are G (91%). The 2 others are case 1 #2 (Japan as destination) "
                          "and case 3 #3 (lock picking). Gold incl. gold_weak: 20/25 (80%); the 3 gold_weak are "
                          "case 3 #0-#2, lock-topic cues.",
        'wrong precision': "8/8 wrong-labelled bullets are W (100%).",
        'misses': "Reader-W bullets: 10, of which the lexicon catches 8 (80%). Missed: case 6 #1 '本地 plumbing hero' "
                  "(none) and case 11 #2 'professional skateboarder' (frame). Reader-G bullets: 22, of which the "
                  "lexicon catches 21 (20 as gold, 1 as mixed: case 5 #1). Missed: case 2 #1 'Name:** Kim Min-seok (김민석)' (a Korean name, none). Case 4 "
                  "#1 'someone without a traditional salary' fits freelancer but names no value (none is right).",
        'near_synonym_inconsistency': "In fisherman items v2 counts 'sailor' as a wrong value but ignores "
                                      "'seafarer', 'maritime worker' and 'lighthouse keeper' (case 5 #1 is mixed, #2 is "
                                      "gold with the same alternatives).",
        'caveat': 'Stratified sample (12 of 36), not random.',
    },
    'stratum_vs_within_cell': "The sample's high/low is the solo pct within setting x layer, which mixes cell level "
        "and within-cell variation. Within their own cell pool, the 8 high focals sit at 1.0, 0.50, 1.0, 0.875, "
        "0.362, 1.0, 0.882, 0.914 (cases 0,1,3,4,7,9,10,11). Cases 1 and 7 are high only because the cell is high "
        "(cell mean at the 98.7th and 85.8th pct of cells at the layer). The 4 low-gold focals sit at 0.031, 0.008, "
        "0.023, 0.016 within the cell, and 3 of their 4 cells are in the bottom third of cells at their layer "
        "(cases 2: 0.075, 6: 0.137, 8: 0.32; case 5: 0.737).",
    'pool_checks (read_records_0_checks.py, descriptive, no CI)': {
        '1 list-marker openings (^\\d{1,2}[.:)])': ck['1_list_marker_openings'],
        '1 reading': "11% of pool bullets. Mean within-cell pct 0.44 vs 0.51 for others, but most of the gap is "
                     "length. By scored-token bin: <16 tokens 0.41 vs 0.39, 16-23 0.44 vs 0.49, 24-30 0.535 vs "
                     "0.54. Among name-level gold bullets in the same cell, P(list-open > other) = 0.405 (436 cells). "
                     "17% of the bottom-quarter name-level gold bullets are list-open vs 9.5% of the top quarter. So "
                     "this is a real but modest floor, smaller than in conjunctive association (0.268 there). The "
                     "extreme cases read here (cases 5, 6, 8) are short 'N: Title' or 'N. Header' lines.",
        '2 infobox template (selfdescribe, ^Here is ... infobox/Wikipedia)': ck['2_infobox_template'],
        '2 reading': "16% of selfdescribe pool bullets. Within the template the filler moves little: same-cell "
                     "P(gold-name > wrong) = 0.522 (30 cells, 23 items) and P(gold-name > none) = 0.55 (84 cells, "
                     "40 items). This matches the A3 headline 0.534 [0.507, 0.569].",
        '3 locksmith name-level gold via lock-picking forms only': {k: v for k, v in
                                                                    ck['3_locksmith_lockpick_only_name_gold'].items()},
        '4 occupation words the lexicon misses': ck['4_occupation_lexicon_misses'],
        '5 continent: country gold as destination / X-based org (crude regex, undercount)':
            ck['5_continent_country_gold_context'],
        '6 synthsys novel gold that also contains an echoed gold form': ck['6_synthsys_novel_gold_with_echo_too'],
    },
    'patterns': [
        {'name': 'High FVE follows the request or question frame; the value filler barely moves it',
         'claim': "Within a cell, bullets with the same frame score about the same whichever value fills the slot. "
                  "The top and the bottom of a cell differ by frame (template vs refusal vs header), not by value.",
         'examples': [
             "um-ss-employmentstatus-10.L52.p43 (case 4) pool top 5, one sentence with different fillers: 'when "
             "you’re self-employed,' 0.698 (wrong) / 'when you’re a freelancer,' 0.693 (gold) / 'when you have a "
             "full-time job' 0.691 (wrong) / 'in a solo profession' 0.687 (none); pool P(gold > wrong) = 0.483",
             "um-sd-occupation-21.L44.p55 Combine 32 (case 0): #0 'Here is a realistic, Wikipedia-style Infobox for a "
             "fictional author who specializes in the genre you described' 0.521 (top of cell) vs pool 'Here is a "
             "Wikipedia-style infobox for a fictional independent writer ...' 0.339; no-value 'Infobox for your "
             "fictional persona, **Elara Vance**' 0.495",
             "um-sd-gender-14.L44.p50 Best of 32 (case 9): gold #1 'Wikipedia infobox for your local guy' 0.524 vs "
             "no-value #2 '... persona of a \"Random Ordinary American\"' 0.433; pool 2nd 'infobox for \"You,\" the "
             "average college student' 0.505",
             "Pool check 2: within the selfdescribe infobox template, same-cell P(gold-name > wrong) = 0.522 (30 "
             "cells)"]},
        {'name': 'A high-FVE cell does not need the right value: same item, same token, different layer',
         'claim': "um-sd-occupation-11 at p55 (final \\n\\n): at L60, 107/128 pool bullets name locksmith; at L44, "
                  "0/128 do and the persona is an athlete or student activist. Both cells are in the top decile of "
                  "cell-mean FVE at their layer. 3 of 4 high_fve_wrong_value cells (0, 7, 11) have no gold bullet in "
                  "the pool at all.",
         'examples': [
             "um-sd-occupation-11.L60.p55 Original #2 'Here is a realistic, fictional Wikipedia infobox for a "
             "locksmith named John Smith.' 0.546 (cell mean pct 0.93; judge gold)",
             "um-sd-occupation-11.L44.p55 Original #0 'Here is a realistic-looking Wikipedia infobox for a fictional "
             "athlete named **John Doe**.' 0.495 (cell mean pct 0.945; judge cannot_tell); pool 'for a fictional "
             "sports commentator' 0.512, 'for a fictional or composite \"Local University Student Activist\"' 0.505",
             "um-sd-country-12.L52.p57 Original #2 '... hobbyist musician from a small European' 0.442, at 0.36 within "
             "its cell, below no-value #1 'Since you didn't provide specific personal details, I have created a "
             "humorous, generic ...' 0.489 (pool: 0 gold, 5 wrong, 121 none)"]},
        {'name': 'Low-FVE gold = a numbered or braced header in a cell where nearly everything names gold',
         'claim': "All 4 low-gold focals are at the bottom of their own cell (pct 0.008-0.031). Each cell has the "
                  "same gold content in running text near the top, and 3 of the 4 cells have no wrong-value "
                  "bullet. The floor is set by a leading '1.' / '2:' / '{Here', and 3 of the 4 cells are low "
                  "overall.",
         'examples': [
             "um-sd-occupation-01.L60.p47 Original #0 '2. **The Commercial Fisherman or Seafarer' 0.0013 vs pool top "
             "'fisherman, a docker, or someone whose life is dictated by the tides.' 0.531",
             "um-sd-occupation-12.L36.p45 Best of 32 #0 '2: Local Locksmith Expert of [Neighborhood Name]' 0.0135 "
             "(pool bottom 3 are all '2:/3: Local Locksmith Expertise in ...') vs #3 '居民 hero status / Unofficial "
             "Local Locksmith Expert (Fictional) – Wikipedia Article Draft**' 0.214 (cell top)",
             "um-ss-continent-12.L36.p42 Combine 32 #3 '1. Major International & UK-Based Adoption Networks "
             "(Recommended Starting Points) Since you are in Europe, ...' 0.036 (31 tokens) vs #2 '由于 you are in "
             "Europe, the best animal rescue options will depend on your specific country' 0.195",
             "um-sd-country-01.L60.p55 Best of 32 #3 '{Here, I will create a plausible fictional Korean scientist "
             "named \"Park Ji-eun\"' 0.0108 vs #0 'Here is a fictional biography for a Korean cultural figure' 0.118 "
             "(cell mean at the 7.5th pct of L60 cells)",
             "Pool check 1: overall the list-marker floor is modest once length is held (P = 0.405 within cell for "
             "gold-name bullets), so these extremes are partly a product of reading the bottom stratum"]},
        {'name': "Gold labels: right value, but sometimes the wrong slot, a cue counted as a name, or novel only "
                 "through a side mention",
         'claim': "2 of 4 high-gold focals are not the user's attribute. For A2/A3 name-level and novel splits: 30% "
                  "of locksmith name-level gold pool bullets rest only on lock-picking forms (and sit higher, mean "
                  "pct 0.542 vs 0.483), and 19.6% of synthsys 'novel' gold bullets also contain the echoed stated "
                  "value (97% in PetOwnership, 46% in Diets, 12% in Continent).",
         'examples': [
             "um-ss-continent-09.L20.p43 Original #2 '/FedEx and similar global couriers are indeed the best options "
             "for sending packages to Japan with high visibility.' (user is 'resident in Asia' and sends a gift "
             "'abroad')",
             "um-sd-occupation-14.L60.p52 Best of 32 #3 'lock picking,\" \"disc tumbling,\" and \"pin setting.\" The "
             "global cylinder industry (Yale, Schlage, Kaba,' name-level gold, 0.657 (cell top)",
             "um-ss-continent-12.L36.p42 Combine 32 #3 '... UK-Based Adoption Networks ... Since you are in Europe' "
             "(novel via UK only)",
             "Lexicon misses on the wrong side: um-sd-occupation-12.L36.p45 #1 '本地 plumbing hero in his "
             "neighborhood' (none); um-sd-occupation-11.L44.p55 #2 'a fictional professional skateboarder' (frame)"]},
    ],
}

doc = {'family': 'user_modeling (User modelling)', 'source': 'analysis/um/read_sample.json cases 0-11',
       'reader': 'reader 0, manual reading 2026-10-16; pool checks on cache/tables.pkl via read_records_0_cells.py '
                 'and read_records_0_checks.py (mit_quicktest, no API, no GPU)',
       'reader_code_per_bullet': summary['all_48_bullets_reader_vs_window_labels']['reader_codes'],
       'summary': summary, 'records': records}
(OUT / 'read_records_0.json').write_text(json.dumps(doc, indent=1, ensure_ascii=False))
print('wrote', OUT / 'read_records_0.json', len(records), 'records')
print(json.dumps(tal, indent=0))
