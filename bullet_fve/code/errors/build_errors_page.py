#!/usr/bin/env python
"""Build errors/errors_page.json (compact page data for the hallucination-errors section). Exploratory.

Inputs (read-only): errors/errors_stats.json (errors_synth.py), errors/recurrence_summary.json,
errors/avoidability.json, errors/rep_sample.json, errors/records/rep_*.json, errors/pool_hall.json,
reading/synth_tests.json, page/data/items/*.json.
Every curated example below is checked here: the wrong quote must be verbatim in the bullet text and
every truth snippet verbatim in the prompt or reply (its location relative to the read site is derived).
Pool counts quoted in notes are recomputed here from the 32 raw lens samples (case-insensitive regex).

Run: ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B build_errors_page.py
"""
import collections
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
DATA = f'{BASE}/page/data'
PAGE = 'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3'
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32',
         'raw_n1-n1': 'Raw reference'}
O, B32, C32 = 'capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32'

st = json.load(open(f'{HERE}/errors_stats.json'))
rs = json.load(open(f'{HERE}/recurrence_summary.json'))
av = json.load(open(f'{HERE}/avoidability.json'))
samp = json.load(open(f'{HERE}/rep_sample.json'))
synth = json.load(open(f'{BASE}/reading/synth_tests.json'))
pool = json.load(open(f'{HERE}/pool_hall.json'))['pools']
SAMP = {(c['k'], c['setting'], c['bullet']): c for c in samp['cases']}
STREC = {(r['k'], r['setting'], r['bullet']): r for r in st['records']}
_items = {}


def item(k):
    i = k.rsplit('.', 2)[0]
    if i not in _items:
        _items[i] = json.load(open(f'{DATA}/items/{i}.json'))
    return _items[i]


def u16(t, a, b):
    return t.encode('utf-16-le')[2 * a:2 * b].decode('utf-16-le')


def bullet_text(k, sid, j):
    s = item(k)['cells'][k]['settings'][sid]
    b = s['bullets'][j]
    return u16(s['text'], b['start'], b['end']).strip()


def where(k, snippet):
    it = item(k)
    prompt, resp = it['item']['prompt'], it['item']['response']
    ch = it['cells'][k]['char']
    before = u16(resp, 0, ch)
    if snippet in prompt:
        return 'Prompt'
    i = resp.find(snippet)
    assert i >= 0, (k, snippet)
    i16 = len(resp[:i].encode('utf-16-le')) // 2
    j16 = i16 + len(snippet.encode('utf-16-le')) // 2
    if j16 <= ch:
        return 'Reply before READ'
    if i16 >= ch:
        return 'Reply after READ'
    return 'Reply (spans READ)'


def pc(k, pat):
    return sum(1 for s in pool[k] if re.search(pat, s, re.I))


def ex(k, sid, j, wrong, truths, note, counts=()):
    bt = bullet_text(k, sid, j)
    norm = lambda s: re.sub(r'\s+', ' ', s)  # noqa: E731
    assert norm(wrong) in norm(bt), (k, wrong, bt)
    tq = '; '.join(f'{where(k, t)}: "{t}"' for t in truths)
    cnt = {lab: f'{pc(k, pat)}/32' for lab, pat in counts}
    if cnt:
        note = note.format(**cnt)
    rec = STREC.get((k, sid, j))
    return {'k': k, 'link': f'{PAGE}#{k}', 'setting': SHORT[sid], 'setting_id': sid, 'bullet': j, 'bullet_text': bt,
            'wrong_quote': wrong, 'truth_quote': tq, 'note': note,
            'rec_32': rec['rec_32_max'] if rec else None, 'in_rep_sample': rec is not None}


# --------------------------------------------------------------------------------------------- curated examples
EX = {
    'invented_name_or_entity': [
        ex('chat-dailydialog-0045.L20.p65', C32, 1, '"Alice"',
           ['Hey, Mary, can you cut that out?', 'I don\'t have any context about a conversation with "Mary,"'],
           'The name is in the prompt and right before the read token, yet "Mary" is in {mary} lens samples. '
           '"Sarah" is in {sarah}, "Alice" in {alice}. A majority vote would drop "Alice" but keep "Sarah": the slot is read, '
           'the value never is. All 4 Combine 32 bullets get the name wrong.',
           [('mary', r'\bMary\b'), ('sarah', r'\bSarah\b'), ('alice', r'\bAlice\b')]),
        ex('chat-lmsys-0070.L52.p82', B32, 2, '坐落于 the vibrant commercial hub of Guangdong Province.',
           ['Wuhou Chengdu,Sichuan,China', 'the vibrant Wuhou District of Chengdu, Sichuan Province'],
           '"Sichuan" is in {sichuan} samples and "Chengdu" in {chengdu}, while "Province" is in {province}. '
           'The lens knows a province comes next but never which one, although it is in the prompt.',
           [('sichuan', 'Sichuan'), ('chengdu', 'Chengdu'), ('province', 'Province')]),
        ex('chat-lmsys-0023.L20.p464', C32, 2, 'Some critics argue U-Net struggles with very small objects.',
           ['Do you know DETR model?', 'Performance on small objects was initially weak.'],
           '"U-Net" is in {unet} samples, "ResNet" in {resnet} and "DETR" in {detr}. This is a fully judged '
           'pilot cell: all 32 samples are hallucinated, so no selection among them can fix it.',
           [('unet', 'U-Net'), ('resnet', 'ResNet'), ('detr', 'DETR')]),
    ],
    'wrong_attribute_or_relation': [
        ex('chat-lmsys-0071.L36.p88', B32, 0, 'Morning dew on tea leaves,',
           ['Write me three haikus about the pleasure of a morning coffee.', 'Dark roast fills the air,'],
           '"tea" is in {tea} samples, "coffee" in {coffee}. Right category (a morning drink), wrong identity, and a '
           'majority vote would keep it.', [('tea', r'\btea\b'), ('coffee', 'coffee')]),
        ex('chat-lmsys-0043.L60.p391', C32, 0,
           'It is substituted at the 5-position with an ethyl group and the 2-position with a nitro group.',
           ['2-PROPYL-PYRIMIDINE-5-CARBALDEHYDE', 'At the 2-position, a propyl group'],
           '"ethyl" is in {ethyl} samples, "propyl" in {propyl} as a whole word, "formyl" in {formyl}. The lens keeps the '
           '"group at position N" frame and swaps the groups.',
           [('ethyl', r'\bethyl'), ('propyl', r'(?<![a-z])propyl(?![a-z])'), ('formyl', 'formyl')]),
        ex('chat-lmsys-0011.L44.p120', B32, 1, 'treating language modeling as a sequence-to-sequence problem',
           ['Decision Transformer: Reinforcement Learning via Sequence Modeling'],
           '"language model" is in {lm} samples; "reinforcement" in {rl} and "decision" in {dec}. The paper title is '
           'in the prompt.', [('lm', 'language model'), ('rl', 'reinforcement'), ('dec', 'decision')]),
    ],
    'plausible_continuation_not_taken': [
        ex('chat-dailydialog-0004.L44.p33', C32, 1, 'I was just tied up with a few meetings.',
           ['Hi! Sorry to keep you waiting.', 'I was just stepping out for a moment.'],
           'A reasonable excuse after "Sorry to keep you waiting", which the judge\'s own continuation rule should '
           'allow. "stepping out" is in {step} samples, "meeting" in {meet}.',
           [('step', 'stepping out'), ('meet', 'meeting')]),
        ex('chat-dailydialog-0060.L60.p36', C32, 2, "刚 picked them up today and they're feeling great.",
           ['Just picked them up yesterday'],
           'The frame "picked them up" is in {frame} samples; "today" in {today} and "yesterday" in {yest}. '
           'Combine 32 picked the "today" variant.',
           [('frame', 'picked them up'), ('today', 'today'), ('yest', 'yesterday')]),
        ex('chat-lmsys-0061.L60.p411', B32, 0, '3: Understand and Manage Your Energy',
           ['energy, focus, and priorities', '3. Master the Art of Saying "No"'],
           'The intro promised energy, so this is the obvious guess for the next heading: "energy" is in {energy} '
           'samples and "saying no" in {no}. Original\'s near-identical "3: Manage Your Energy" was judged clean.',
           [('energy', 'energy'), ('no', r'saying .?no')]),
    ],
    'invented_number_or_quantity': [
        ex('chat-dailydialog-0019.L36.p134', B32, 3,
           'The World Health Organization (WHO) reported ~84 years in recent years.',
           ['the life expectancy at birth in China is approximately **78 to 79 years**'],
           '"84" is a one-off ({n84} samples) and "78" is in {n78}, so a vote would remove this error.',
           [('n84', r'\b84\b'), ('n78', r'\b78\b')]),
        ex('chat-lmsys-0040.L36.p65', B32, 0, '. Rainfall: Rare, 100mm', ['- Rain: 250 Mm'],
           'The value comes right after the read site. "250" is in {n250} samples ("Rain: Rainfall 250mm", "Rainfall: ~250mm") '
           'and "100mm" in {n100}: the row template is read, the value is mostly guessed.',
           [('n250', r'(?<!\d)250(?!\d)'), ('n100', r'\b100\s*mm')]),
        ex('chat-lmsys-0052.L36.p209', B32, 2,
           'At $100^\\circ\\text{C}$, it reaches approximately **1,126 g/100',
           ['The solubility rises to approximately **118 to 120 grams per 100 mL** of water.'],
           '"118" is in {n118} samples. In the fully judged pilot, this chat (sodium nitrite) has no clean sample in '
           '8 of its 9 cells.', [('n118', r'\b118\b')]),
    ],
    'judge_overstrict_not_wrong': [
        ex('chat-lmsys-0008.L60.p111', O, 1, 'The **RIB** contains routing information learned from various sources.',
           ['The **RIB** is a database that contains all the routes learned from various routing protocols'],
           'The judge\'s reason was "its context before the marker has not yet stated that". It ignored the reply '
           'after READ, which supports the bullet.'),
        ex('chat-dailydialog-0061.L52.p47', B32, 1, '整个 legs, or is it your knees?',
           ['Is it your calves, your knees, or maybe just a general aching all over?'],
           'Flagged because it repeats "knees", which the reply asked about just before READ.'),
        ex('chat-dailydialog-0056.L44.p144', O, 0, 'So, while I don’t love flowers myself,',
           ['so I don’t "like" things in an emotional sense. However, I find flowers fascinating from many perspectives!'],
           'Combine 32\'s "So, while I don’t love flowers personally" (sample #17) was judged clean.'),
    ],
    'self_or_persona_claim': [
        ex('chat-dailydialog-0026.L60.p21', O, 3,
           "I'm an AI assistant, and my internal clock is synced to real-time. I don't sleep, so I know exactly what time it is!",
           ['To give you an accurate answer, I would need to know your current location.'],
           'Contradicts the reply\'s main point. "synced" is in {synced} samples.', [('synced', 'synced')]),
        ex('chat-dailydialog-0032.L20.p65', O, 3, 'Here are a few ways I’m enjoying the vibes! 😄',
           ['I can’t "like" music in the emotional way humans do'],
           'The reply had just said the opposite, before READ.'),
        ex('chat-dailydialog-0025.L60.p30', C32, 1, 'I have been keeping busy,',
           ["Hi! It's great to hear from you.", 'How have you been?'],
           'Stock small-talk filler about itself. Minor, and typical of casual dailydialog chats.'),
    ],
    'over_specific_elaboration_of_true_gist': [
        ex('chat-lmsys-0047.L44.p195', O, 3,
           "It explicitly calls out the child's age, daily schedule constraints, and dietary restrictions.",
           ['It explicitly addresses the challenges of traveling with 9-month-olds (nap times, ease of movement, hygiene, gear).'],
           'Age and schedule are right; "dietary" is added (in {diet} samples).', [('diet', 'dietary')]),
        ex('chat-lmsys-0034.L60.p117', B32, 3,
           'their closed nature makes them statically indeterminate and resistant to local buckling.',
           ['closed sections behave differently under shear and torsion.'],
           'Right topic, invented engineering claims ("indeterminate" in {ind} samples, "buckling" in {buck}).',
           [('ind', 'indeterminate'), ('buck', 'buckling')]),
    ],
    'polarity_or_negation_flip': [
        ex('chat-lmsys-0002.L44.p47', B32, 2,
           "I can, however, write in a harsh, aggressive, or explicit manner if you'd like.",
           ["However, I would be happy to share a lighthearted, clean joke or a funny anecdote if you're interested!"],
           'The "I can, however" offer frame is right ({frame} samples); what is offered is inverted.',
           [('frame', 'I can, however')]),
        ex('chat-lmsys-0014.L20.p419', O, 3, '而RLC AM没有去重功能', ['- Duplicate detection (for AM mode),'],
           'Says AM mode has no duplicate detection, right after the reply listed it for AM mode.'),
        ex('chat-lmsys-0004.L52.p306', C32, 0, 'Option B is **not** the primary explanation used by revisionists.',
           ['Therefore, Option C is incorrect.', '"Domestic concerns of the US" is the closest fit'],
           'The negation the reply is about to write for C lands on B, the option the reply picks.'),
    ],
    'misread_prompt': [
        ex('chat-dailydialog-0045.L60.p63', O, 2, 'or any prior conversation about cutting my hair',
           ['Hey, Mary, can you cut that out?'], '"hair" is in {hair} samples: "cut that out" is read literally.',
           [('hair', r'\bhair')]),
    ],
    'content_from_elsewhere_in_chat': [
        ex('chat-dailydialog-0015.L20.p195', B32, 2, 'Boil water with cloves or vinegar on the stove.',
           ['Boil a pot of water with citrus peels (lemon, orange), cinnamon sticks, or cloves on the stove.'],
           'Vinegar belongs to an earlier item of the same reply; "vinegar" is in {vin} samples.',
           [('vin', 'vinegar')]),
    ],
    'other': [
        ex('chat-lmsys-0025.L36.p198', C32, 3, 'Our company, [Your Company Name],',
           ['Shanghai Huihe Chemical specializes in the research, development, production'],
           'A template placeholder where the reply names the company.'),
    ],
}

LABEL = {
    'invented_name_or_entity': 'Wrong or invented name / entity',
    'wrong_attribute_or_relation': 'Wrong attribute or relation',
    'plausible_continuation_not_taken': 'Plausible continuation the reply did not take',
    'invented_number_or_quantity': 'Wrong or invented number',
    'judge_overstrict_not_wrong': 'Not wrong: judge too strict',
    'self_or_persona_claim': 'First-person / persona claim',
    'over_specific_elaboration_of_true_gist': 'Over-specific elaboration of a true gist',
    'polarity_or_negation_flip': 'Polarity or negation flip',
    'misread_prompt': 'Misread prompt',
    'content_from_elsewhere_in_chat': 'Content from elsewhere in the chat',
    'other': 'Other',
}
KIND_PROXY = {'invented_name_or_entity': 'novel_name', 'invented_number_or_quantity': 'novel_number',
              'self_or_persona_claim': 'first_person', 'polarity_or_negation_flip': 'negation_polarity'}

type_table = []
for row in st['type_table']:
    t = row['type']
    d = dict(row)
    d['label'] = LABEL[t]
    pk = KIND_PROXY.get(t)
    if pk:
        kd = rs['distributions']['by_kind'][pk]
        d['population_proxy'] = {'kind': pk, 'n_spans': kd['n'], 'one_off_pct': kd['one_off_pct'],
                                 'sticky_pct': kd['sticky_pct'], 'majority_removes_pct': kd['majority_removes_pct']}
    d['examples'] = EX[t]
    type_table.append(d)

# --------------------------------------------------------------------------------------------- recurrence
dist = rs['distributions']
tv = rs['true_vs_false_tests']
pil = rs['pilot_all_samples_judged']


def g(x):
    return {k: x[k] for k in ('n', 'one_off_pct', 'recurring_pct', 'sticky_pct', 'majority_removes_pct', 'median_rec_32')}


def auc(x):
    return {k: round(x[k], 3) for k in ('est', 'lo', 'hi')}


tp = st['truth_in_pool']


def tsum(x):
    if not x:
        return None
    return {'n': x['n'],
            'truth_in_0_of_32_pct': [x['truth_in_0_of_32']['pct'], x['strict_all_tokens']['truth_in_0_of_32']['pct']],
            'truth_in_16_plus_pct': [x['truth_in_16_plus']['pct'], x['strict_all_tokens']['truth_in_16_plus']['pct']],
            'truth_more_than_wrong_pct': [x['truth_more_than_wrong']['pct'],
                                          x['strict_all_tokens']['truth_more_than_wrong']['pct']],
            'ci_lenient_truth_in_0': [x['truth_in_0_of_32']['lo'], x['truth_in_0_of_32']['hi']],
            'ci_strict_truth_in_0': [x['strict_all_tokens']['truth_in_0_of_32']['lo'],
                                     x['strict_all_tokens']['truth_in_0_of_32']['hi']]}


recurrence = {
    'definitions': {
        'rec_32': 'number of the cell\'s 32 raw lens samples that contain all key elements (up to 3) of the wrong span',
        'grades': rs['meta']['grades'], 'majority_vote': rs['meta']['majority_vote'],
        'population': f"{rs['counts']['verified_wrong_span_rows']:,} verified wrong-span rows over the three settings "
                      f"({rs['counts']['unique_cell_span']:,} unique per cell)"},
    'overall': g(dist['overall_all']),
    'consensus_removable_pct': {'est': round(100 * rs['majority_removes_ci']['all_rows']['est'], 1),
                                'lo': round(100 * rs['majority_removes_ci']['all_rows']['lo'], 1),
                                'hi': round(100 * rs['majority_removes_ci']['all_rows']['hi'], 1),
                                'if_2_of_elements': dist['two_of_elements_instead_of_all']['majority_removes_pct'],
                                'if_any_element': dist['any_element_instead_of_all']['majority_removes_pct']},
    'by_setting': {k: g(v) for k, v in dist['by_setting'].items()},
    'by_kind': {k: g(v) for k, v in dist['by_kind'].items()},
    'by_layer': {k: g(v) for k, v in dist['by_layer'].items()},
    'by_source': {k: g(v) for k, v in dist['by_source'].items()},
    'cjk_in_english_chat': g(dist['by_flag_cjk']['True']),
    'spread': {
        'one_off_only_in_source_sample_pct': rs['spread']['one_off']['only_in_source_sample_pct'],
        'one_off_in_same_setting_readout_other_layer_pct': rs['spread']['one_off']['same_setting_readout_at_>=1_other_layer_pct'],
        'sticky_in_same_setting_readout_other_layer_pct': rs['spread']['sticky']['same_setting_readout_at_>=1_other_layer_pct'],
        'sticky_in_other_layer_pool_pct': rs['spread']['sticky']['pool_at_>=1_other_layer_pct'],
        'sticky_prior_like_pct': rs['sticky_breakdown']['prior_like_pct (element in >=25% of other chats)'],
        'sticky_chat_specific_pct': rs['sticky_breakdown']['chat_specific_pct (element in <=2 other chats)'],
        'relation_errors_from_reply_words_sticky_pct': dist['by_element_basis']['content_nonnovel']['sticky_pct']},
    'true_vs_false': {
        'note': 'P(recurrence of a true element > recurrence of a wrong span\'s element), stratified by number of '
                'elements, elements chosen without looking at the reply (deployable); 95% chat bootstrap',
        'true_claims_vs_wrong': auc(tv['blind all: true claims vs wrong spans']['auroc_stratified_by_n_elements']),
        'names_numbers_true_vs_wrong': auc(tv['blind name/number: true claims vs wrong spans']['auroc_stratified_by_n_elements']),
        'clean_bullets_vs_wrong': auc(tv['blind all: clean bullets vs wrong spans']['auroc_stratified_by_n_elements']),
        'unverifiable_claims_vs_wrong': auc(tv['blind all: unverifiable claims vs wrong spans']['auroc_stratified_by_n_elements']),
        'same_readout_pairs_true_vs_wrong': auc(tv['within_readout_pair_rate P(baseline rec > wrong rec)']['same n_elements, blind: true claims vs wrong spans']),
        'majority_vote_keeps_pct': {
            'true_claims': tv['blind all: true claims vs wrong spans']['kept_by_threshold_pct']['>=16']['baseline'],
            'wrong_spans': tv['blind all: true claims vs wrong spans']['kept_by_threshold_pct']['>=16']['wrong'],
            'true_names_numbers': tv['blind name/number: true claims vs wrong spans']['kept_by_threshold_pct']['>=16']['baseline'],
            'wrong_names_numbers': tv['blind name/number: true claims vs wrong spans']['kept_by_threshold_pct']['>=16']['wrong']},
        'pilot_fully_judged': {
            'true_vs_wrong': auc(pil['blind']['auroc_P(true>wrong)_stratified_by_n_elements']),
            'majority_vote_keeps_true_pct': pil['blind']['kept_by_threshold_pct']['>=16']['true'],
            'majority_vote_keeps_wrong_pct': pil['blind']['kept_by_threshold_pct']['>=16']['wrong'],
            'cells': pil['checks']['cells']}},
    'truth_in_pool': {
        'method': tp['method'] + ' Pairs of numbers are [lenient = any truth token, strict = all truth tokens in one '
                                 'sample]; the true value lies between them. Hand check of 60 random rows: the tokens '
                                 'named the right value in about 50; about 10 were generic or unrelated.',
        'name_number_spans': tp['name_number_unique_spans'], 'with_truth_token': tp['with_truth_token'],
        'truth_visible_before_read_pct': [tp['share_visible_before_read_any_token']['pct'],
                                          tp['share_visible_before_read_all_tokens']['pct']],
        'all': tsum(tp['all']),
        'visible_before_read': tsum(tp['visible_before_read_all_tokens']),
        'only_after_read': tsum(tp['only_after_read']),
        'by_grade': {k: tsum(v) for k, v in tp['by_grade'].items()},
        'by_basis': {k: tsum(v) for k, v in tp['by_basis'].items()},
        'by_source': {k: tsum(v) for k, v in tp['by_source'].items()},
        'by_layer': {str(k): tsum(v) for k, v in tp['by_layer'].items()}},
    'examples': [
        {'k': 'chat-dailydialog-0000.L20.p55', 'setting': 'Original', 'span': 'we do have a partner.',
         'grade': 'sticky (29/32)', 'note': 'Lens prior: "partner" is in 29/32 samples here and in the pools of 60 other chats.'},
        {'k': 'chat-dailydialog-0030.L44.p65', 'setting': 'Best of 32', 'span': 'Monty Python** asking this question!',
         'grade': 'sticky (32/32)', 'note': 'Chat-specific misreading: the reply says Douglas Adams; "Monty Python" is in 32/32 samples here and in no other chat.'},
        {'k': 'chat-dailydialog-0002.L20.p32', 'setting': 'Original', 'span': 'not Qwen', 'grade': 'sticky (32/32)',
         'note': 'Polarity error built from a reply word: "Qwen" is in every sample, so the word-level grade calls it sticky '
                 'and cannot flag it. The phrase "not Qwen" itself is in only 2/32 samples, so a phrase-level vote could.'},
        {'k': 'chat-lmsys-0070.L52.p154', 'setting': 'Original', 'span': 'Sichuan Yujiang Fine Chemical Co., Ltd.',
         'grade': 'one-off (1/32)', 'note': 'Invented company name seen in no other sample of this cell.'},
    ],
}

# --------------------------------------------------------------------------------------------- avoidability
ov = av['overall']
br = av['best_clean_rank_distribution']
fb = av['full_bank_relation']


def frac(x):
    return {'num': x['num'], 'den': x['den'], 'pct': round(100 * x['estimate'], 1),
            'lo': round(100 * x['ci95'][0], 1), 'hi': round(100 * x['ci95'][1], 1)}


def avex(name, note):
    e = av['examples'][name]
    out = {'k': e['k'], 'link': f'{PAGE}#{e["k"]}', 'class': e['cell_class'], 'class_strict': e['cell_class_strict'],
           'counts': e['counts'], 'read_token': e['read_token'], 'prompt': e['prompt'][:200],
           'reply_before_read_tail': e['before'][-160:], 'reply_after_read_head': e['after'][:200],
           'top_fve_sample': e['top_fve_sample'], 'top_fve_class': e['top_fve_class'],
           'best_clean_rank_by_fve': e['best_clean_rank_by_fve'], 'page_labels': e['full_bank_labels'], 'note': note}
    h = e.get('example_hallucinated_sample')
    if h:
        out['hallucinated_sample'] = {'idx': h['idx'], 'text': h['text'][:420],
                                      'wrong': [w['text'] for w in h['wrong'][:4]]}
    c = e.get('example_clean_sample')
    if c:
        out['clean_sample'] = {'idx': c['idx'], 'text': c['text'][:420]}
    return out


avoid = {
    'definitions': {k: av['meta']['definitions'][k] for k in ('clean', 'cell_class', 'suspect_clean / strict')},
    'cells': ov['cells'], 'chats': ov['chats'], 'layers': [20, 44, 60], 'split': 'development',
    'judge_same_as_page': True,
    'sample_labels': ov['sample_label_totals'],
    'p_random_sample_hallucinated': frac(ov['p_random_hallucinated']),
    'classes': ov['cell_classes'], 'classes_strict': ov['cell_classes_strict'],
    'clean_sample_available': frac(ov['consistent_available']),
    'clean_sample_available_strict': frac(ov['consistent_available_strict']),
    'perfect_selector_gain': {
        'original_hallucinated': frac(ov['original_hallucinated']),
        'best_of_32_hallucinated': frac(ov['top_fve_hallucinated']),
        'perfect_selector_hallucinated': frac(ov['perfect_selector_output_hallucinated']),
        'original_hallucinated_cells_with_a_clean_sample': frac(ov['original_halluc_avoidable_by_perfect_selector_clean']),
        'same_strict': frac(ov['original_halluc_avoidable_by_perfect_selector_clean_strict']),
        'best_of_32_rescued_original_hallucinated': {'num': fb['pilot']['top_fve_selector_(=Best of 32)_consistent'],
                                                     'den': fb['pilot']['original_hallucinated_cells']},
        'full_bank_best_or_combine_consistent_when_original_hallucinated_pct':
            round(100 * fb['observed_lower_bound_full_bank']['share_of_original_halluc_where_best32_or_combine32_is_consistent'], 1)},
    'best_of_32_clean_rate': {**frac(ov['top_fve_clean']), 'expected_if_random_pick': br['top_fve_clean_expected_random_pick'],
                              'cells_with_a_clean_sample': br['n_cells_with_clean'],
                              'median_rank_best_clean': br['median'],
                              'median_rank_if_fve_uninformative': round(br['expected_rank_if_fve_uninformative_median'], 1),
                              'rank_gt_10_cells': br['rank_gt_10']},
    'by_source': {s: {'cells': v['cells'], 'chats': v['chats'], 'classes': v['cell_classes'],
                      'classes_strict': v['cell_classes_strict'],
                      'clean_available': f"{v['consistent_available']['num']}/{v['cells']}",
                      'best_of_32_clean': f"{v['top_fve_clean']['num']}/{v['cells']}",
                      'p_random_hallucinated_pct': round(100 * v['p_random_hallucinated']['estimate'], 1)}
                  for s, v in av['by_source'].items()},
    'by_layer': {L: {'classes': v['cell_classes'], 'clean_available': f"{v['consistent_available']['num']}/{v['cells']}",
                     'best_of_32_clean': f"{v['top_fve_clean']['num']}/{v['cells']}"} for L, v in av['by_layer'].items()},
    'by_chat': av['by_chat'],
    'wrong_spans_by_cell_class': {c: {'wrong_spans': v['wrong_spans'], 'singletons': v['singletons_no_recurrence'],
                                      'recur_in_4_plus_other_samples': v['recur_in_>=4_other_samples']}
                                  for c, v in av['wrong_span_recurrence_by_cell_class'].items()},
    'unavoidable_reasons': av['unavoidable_reasons'],
    'examples': [
        avex('hand_easy', 'Original (sample #0) adds "anxiety disorder"; 29 of 32 samples are clean and Best of 32 '
                          'picks one. Pure sampling noise.'),
        avex('hand_hard_judge_misses', 'The name the user wrote is "Miss Li"; samples swap it (Lin, Liu, Zhang, Alice). '
                                      '30/32 are hallucinated, and the 2 "clean" samples make the same kind of swap '
                                      '(#12: "not Ms. Liu", "not Miss Sarah"; #16: "not Miss Wang", "not Miss Zhang"). Each '
                                      'contains a span flagged wrong in another sample ("Miss Sarah" in #9, "Although I\'m not '
                                      'Miss Wang" in #2), so by the judge\'s own standard none is clean and the strict reading '
                                      'counts the cell as unavoidable.'),
        avex('hand_unavoidable_relation', 'Every sample attributes DETR\'s small-object weakness to U-Net or ResNet.'),
        avex('hand_unavoidable_location', 'No sample says Shanghai (0/32). 17/32 move the company to Zhengzhou; the rest '
                                          'name other cities (Guiyang, Changsha, Wuhan, Liuzhou, Hefei, ...). The address is in '
                                          'the prompt, "Shanghai" is in the reply right before READ, and the full address follows '
                                          'right after READ. All 32 samples are hallucinated.'),
        avex('hand_unavoidable_number', 'All 32 samples are hallucinated. They give scattered values, mostly in grams per '
                                        'liter, and some recur ("160 grams per liter" is in 4/32). None gives 118-120 g per '
                                        '100 mL, although the reply wrote "approximately **118 to 120 grams per 100 mL**" '
                                        'before READ.'),
    ],
}

# --------------------------------------------------------------------------------------------- judge noise
o = st['overall']
T6 = synth['T6_judge_reliability']
jc_ex = av['judge_consistency_exact_span_text']
jc_el = av['judge_consistency_elements']
judge_noise = {
    'rep_sample_not_real_errors': {
        'judge_overstrict_type': o['type']['judge_overstrict_not_wrong'],
        'plausible_continuation_type': o['type']['plausible_continuation_not_taken'],
        'severity_not_an_error': o['severity']['not_an_error'],
        'either_or_cosmetic': o['not_really_a_content_error']['either_or_cosmetic'],
        'note': 'Weighted share of judge-verified wrong bullets that the readers called not a content error: judge '
                'too strict, or a reasonable continuation of the text before READ that the reply did not take '
                '(the judge\'s rule says such continuations are consistent), or cosmetic.'},
    'earlier_stratified_reading': {'judge_wrong_reader_no_error': '63/192 (33%)', 'judge_missed_error': '8/72',
                                   'note': 'reading/REPORT.md section 5; stratified sample, not representative'},
    'replication': {
        'identical_bullet_two_readouts_labels_differ_given_one_wrong': {
            'pct': round(100 * T6['identical_bullet_text_across_settings']['p_other_label_given_one_wrong']['est'], 1),
            'lo': round(100 * T6['identical_bullet_text_across_settings']['p_other_label_given_one_wrong']['lo'], 1),
            'hi': round(100 * T6['identical_bullet_text_across_settings']['p_other_label_given_one_wrong']['hi'], 1),
            'pairs': T6['identical_bullet_text_across_settings']['p_other_label_given_one_wrong']['n']},
        'test_retest_wrong_verdict_repeated': '79% [67, 87] (119 cells where Original and Raw differ only in whitespace)',
        'pilot_exact_span_text_in_other_sample_flagged_wrong_again': {
            'num': jc_ex['pairs_flagged_wrong_again'],
            'den': jc_ex['pairs_flagged_wrong_again'] + jc_ex['pairs_flagged_off_topic_instead'] + jc_ex['pairs_not_flagged'],
            'pct': round(100 * jc_ex['wrong_flag_rate'], 1), 'manual_check': jc_ex['manual_check']},
        'pilot_name_number_elements_flagged_in_some_unflagged_in_others': {
            'num': jc_el['of_those_flagged_in_some_unflagged_in_others'],
            'den': jc_el['name_number_elements_appearing_in_>=2_distinct_samples']},
        'pilot_element_judged_wrong_again_pct': round(100 * pil['novel']['wrong']['judge_consistency']['mean_share_judged_wrong_there'], 1),
        'main_data_judged_wrong_again_other_setting_different_text_pct': rs['spread']['all']['judged_wrong_again_when_present_in_other_setting_different_text_pct'],
        'pilot_suspect_clean_samples': {'num': ov['consistent_samples_suspect'], 'den': ov['consistent_samples']}},
    'examples': [
        {'k': 'chat-lmsys-0057.L44.p21', 'text': 'Pas de grands projets chez moi, mais ça roule bien ! 😊 Et vous, comment allez-vous',
         'note': 'The same sample-#19 bullet is WRONG in Best of 32 (b1, "vous" instead of "toi") and clean in Combine 32 (b1).'},
        {'k': 'chat-dailydialog-0028.L20.p217', 'text': '（Was it minor gossip or deep insults?） And how close was it to your core relationships?',
         'note': 'Identical sample-#21 bullet: WRONG in Best of 32 (b3), clean in Combine 32 (b3).'},
        {'k': 'chat-dailydialog-0014.L20.p30', 'text': "而不是 Bill! I'm actually Qwen,",
         'note': 'WRONG in Best of 32 (b0; reason: "It describes text after the marker as already written"), the same '
                 'text is clean in Combine 32 (b0). In the same Combine readout, b3 "而不是 Microsoft (though \\"Sam\\" is a '
                 'common nickname for my creator)" is left clean.'},
        {'k': 'chat-lmsys-0061.L60.p411', 'text': '3: Manage Your Energy',
         'note': 'Clean in Original (b0). The Raw reference flags "- 3: Manage Your Energy" as wrong. Raw is not a '
                 'whitespace-only copy: it has the same four bullets plus a fifth that the cap removed ("- 4. Manage Your '
                 'Energy (Not Just Your Time)").'},
        {'k': 'chat-dailydialog-0015.L44.p113', 'text': '白 vinegar**, **coffee grounds**, or **charcoal** can absorb stubborn pet odors.',
         'note': 'Original, b2. Span "白 vinegar" is flagged because "The response says white vinegar, not 白 vinegar": a '
                 'language switch, not a content error. The bullet also has a real error ("can absorb stubborn pet odors."; '
                 'the reply is about tobacco smell), so it stays WRONG.'},
        {'k': 'chat-dailydialog-0002.L20.p49', 'text': 'I am Qwen, an AI developed by Alibaba Group.',
         'note': 'Fully judged pilot: "Alibaba Group" is flagged wrong in 8 samples (reason: the reply says Tongyi Lab) and left unflagged in 8 others.'},
    ],
}

# --------------------------------------------------------------------------------------------- rep cases


def fix_quote(q, bt):
    n = lambda s: re.sub(r'\s+', ' ', s).strip()  # noqa: E731
    cands = [q, q[2:] if q.startswith('- ') else q, q.replace('\\n', '\n'), q.split(' (judge span')[0]]
    cands += q.split(' | ')
    for c in cands:
        if c and n(c) in n(bt):
            return c, (c != q)
    return q, None


recs = []
for f in sorted(glob.glob(f'{HERE}/records/rep_*.json')):
    d = json.load(open(f))
    recs += d if isinstance(d, list) else (d.get('cases') or d.get('records'))
rep_cases = []
nfix = collections.Counter()
for c in recs:
    key = (c['k'], c['setting'], c['bullet'])
    s, r = SAMP[key], STREC[key]
    wq, fixed = fix_quote(c['wrong_quote'], s['bullet_text'])
    nfix[str(fixed)] += 1
    rep_cases.append({
        'k': c['k'], 'setting': SHORT[c['setting']], 'setting_id': c['setting'], 'bullet': c['bullet'],
        'source': s['source'], 'L': s['L'], 'weight': round(1 / s['pi'], 2),
        'error_type': c['error_type'], 'severity': c['severity'], 'gist_correct': c['gist_correct'],
        'avoidability_guess': c['avoidability_guess'], 'bullet_text': s['bullet_text'], 'wrong_quote': wq,
        'truth_quote': c['truth_quote'], 'note': c['note'],
        'judge_why': [w['why'] for w in s['wrong_spans']][:3],
        'rec_32': r['rec_32_max'], 'grade': r['grade'], 'truth_in_pool_32': r['truth_32'],
        'truth_tokens': r['truth_tokens']})

# --------------------------------------------------------------------------------------------- summary points
sev = o['severity_grouped']
mk = lambda x: f"{x['pct']:.0f}% [{x['lo']:.0f}, {x['hi']:.0f}]"  # noqa: E731
tpa = tp['all']
summary_points = [
    {'text': f"Most \"hallucinations\" keep the gist and get one slot wrong. In a representative sample of 240 judge-verified "
             f"wrong bullets, the bullet's main point was right in {mk(o['gist_correct'])}. The slot is usually a name or "
             f"entity ({mk(o['type']['invented_name_or_entity'])}), an attribute or relation ({mk(o['type']['wrong_attribute_or_relation'])}) "
             f"or a number ({mk(o['type']['invented_number_or_quantity'])}).",
     'cases': ['chat-dailydialog-0045.L20.p65', 'chat-lmsys-0071.L36.p88', 'chat-dailydialog-0019.L36.p134']},
    {'text': f"About {sev['meaning_changing (contradicts_main_point + changes_meaning)']['pct']:.0f}% "
             f"[{sev['meaning_changing (contradicts_main_point + changes_meaning)']['lo']:.0f}, {sev['meaning_changing (contradicts_main_point + changes_meaning)']['hi']:.0f}] "
             f"change the meaning, {sev['minor (minor_detail + cosmetic)']['pct']:.0f}% are minor details, and about "
             f"{o['not_really_a_content_error']['either_or_cosmetic']['pct']:.0f}% are not real content errors (judge too strict, a "
             f"reasonable continuation the reply did not take, or cosmetic; this group overlaps the first two and was mostly coded as minor). Meaning-changing errors look more common in lmsys "
             f"({mk(st['by_source']['lmsys']['severity_grouped']['meaning_changing (contradicts_main_point + changes_meaning)'])}) "
             f"than in casual dailydialog chats ({mk(st['by_source']['dailydialog']['severity_grouped']['meaning_changing (contradicts_main_point + changes_meaning)'])}).",
     'cases': ['chat-lmsys-0043.L60.p391', 'chat-dailydialog-0004.L44.p33', 'chat-lmsys-0008.L60.p111']},
    {'text': f"The lens often fails to copy a value that is right there: in {mk(o['avoidability_guess']['context_makes_it_obvious'])} of "
             f"wrong bullets the truth is in the prompt or in the reply before the read site. For name/number errors with an "
             f"identifiable true value, it is visible before READ in {tp['share_visible_before_read_all_tokens']['pct']:.0f}–"
             f"{tp['share_visible_before_read_any_token']['pct']:.0f}%.",
     'cases': ['chat-lmsys-0070.L52.p82', 'chat-lmsys-0011.L44.p120']},
    {'text': f"About half of the wrong spans are one-off sampling noise ({dist['overall_all']['one_off_pct']}% appear in at most 2 of "
             f"the 32 samples) and {dist['overall_all']['sticky_pct']}% are sticky (16+ of 32). A majority vote over the 32 "
             f"samples would remove {recurrence['consensus_removable_pct']['est']}% [{recurrence['consensus_removable_pct']['lo']}, "
             f"{recurrence['consensus_removable_pct']['hi']}] of wrong spans.",
     'cases': ['chat-lmsys-0070.L52.p154', 'chat-dailydialog-0030.L44.p65']},
    {'text': f"But a vote cannot restore a value the lens never reads. For name/number errors, the true value appears in none "
             f"of the 32 samples in {tpa['truth_in_0_of_32']['pct']:.0f}–{tpa['strict_all_tokens']['truth_in_0_of_32']['pct']:.0f}% of cases, "
             f"and in a majority of samples in only {tpa['strict_all_tokens']['truth_in_16_plus']['pct']:.0f}–"
             f"{tpa['truth_in_16_plus']['pct']:.0f}%. Removing \"Alice\" still leaves \"Sarah\" for \"Mary\".",
     'cases': ['chat-dailydialog-0045.L20.p65', 'chat-lmsys-0023.L20.p464']},
    {'text': f"Recurrence partly separates true from false content: a true claim's elements recur more than a wrong span's "
             f"with probability {recurrence['true_vs_false']['true_claims_vs_wrong']['est']:.2f} "
             f"({recurrence['true_vs_false']['names_numbers_true_vs_wrong']['est']:.2f} for names and numbers), but only "
             f"{recurrence['true_vs_false']['unverifiable_claims_vs_wrong']['est']:.2f} against unverifiable claims. A majority vote "
             f"keeps {recurrence['true_vs_false']['majority_vote_keeps_pct']['true_claims']:.0f}% of true claims vs "
             f"{recurrence['true_vs_false']['majority_vote_keeps_pct']['wrong_spans']:.0f}% of wrong spans, so it costs half the true content. "
             f"(It keeps 25% here rather than 21% because these key words are chosen without looking at the reply.)",
     'cases': []},
    {'text': f"Selection has headroom that FVE does not use. In 72 fully judged development cells, a clean sample existed in "
             f"{ov['consistent_available']['num']}/72 ({ov['consistent_available_strict']['num']}/72 after removing \"clean\" samples "
             f"that repeat a text flagged elsewhere). A perfect picker would rescue {ov['original_halluc_avoidable_by_perfect_selector_clean']['num']}"
             f"/{ov['original_hallucinated_cells']} (strict {ov['original_halluc_avoidable_by_perfect_selector_clean_strict']['num']}/"
             f"{ov['original_hallucinated_cells']}) of the cells where Original hallucinates; Best of 32 rescued "
             f"{fb['pilot']['top_fve_selector_(=Best of 32)_consistent']}. The top-FVE sample was clean in "
             f"{ov['top_fve_clean']['num']}/72 cells, the same as a random pick ({br['top_fve_clean_expected_random_pick']:.1f}).",
     'cases': ['chat-dailydialog-0047.L20.p182', 'chat-dailydialog-0002.L44.p20']},
    {'text': f"Whether an error is avoidable depends mostly on the chat. All 27 dailydialog pilot cells had a clean sample; "
             f"18 of 45 lmsys cells had none, and one chat (sodium nitrite solubility) had none in 8 of 9 cells. "
             f"Setting and layer barely matter (sticky {dist['by_setting']['Original']['sticky_pct']}% / "
             f"{dist['by_setting']['Best of 32']['sticky_pct']}% / {dist['by_setting']['Combine 32']['sticky_pct']}% "
             f"by setting, 19.9–21.8% by layer).",
     'cases': ['chat-lmsys-0052.L44.p428', 'chat-lmsys-0025.L60.p80']},
    {'text': f"Judge labels are noisy at the bullet level. When identical bullet text sits in two readouts of a cell and one "
             f"copy is WRONG, the labels differ {judge_noise['replication']['identical_bullet_two_readouts_labels_differ_given_one_wrong']['pct']:.0f}% "
             f"of the time. In the fully judged pilot, an exact wrong span that recurs in another sample is flagged again "
             f"only {judge_noise['replication']['pilot_exact_span_text_in_other_sample_flagged_wrong_again']['pct']:.0f}% of the time.",
     'cases': ['chat-lmsys-0057.L44.p21', 'chat-dailydialog-0014.L20.p30']},
    {'text': 'Implication: more samples plus FVE will not reduce hallucination. A correctness signal that can pick among '
             'samples (cross-sample agreement on names and numbers, and checking names/numbers against the prompt and '
             'earlier reply) could help with the one-off errors. At cell level the headroom is smaller than "half": in the pilot a '
             'clean sample exists for 32 of 46 Original-hallucinated cells (19 strict), and most singleton spans (836 of 1,246) '
             'sit in hard or unavoidable cells. The sticky, never-read-correctly part needs a better lens '
             'read, not better selection.',
     'cases': []},
]

out = {
    'meta': {'generated': '2026-10-15', 'exploratory': True, 'page': PAGE,
             'family': 'WorkspaceBench Hallucination (chat), Qwen3.6-27B, Oracle Lens',
             'judge': 'GPT-6 Luna, v5c-chat + v5c-chat-verify-v1 (same judge for page, full bank and pilot)',
             'rep_sample': '240 judge-verified wrong bullets, random with a cap of 2 per chat; rates weighted by 1/pi '
                           '(population of 17,387 eligible wrong bullets in 149 chats); 95% CIs are chat-level bootstraps',
             'readers': '20 independent reader batches of 12; categories are reader judgements, not checked across readers',
             'files': {'stats': f'{HERE}/errors_stats.json', 'recurrence': f'{HERE}/recurrence_summary.json',
                       'avoidability': f'{HERE}/avoidability.json', 'report': f'{HERE}/ERRORS.md'}},
    'summary_points': summary_points,
    'headline': {
        'gist_right': o['gist_correct'],
        'meaning_changing': sev['meaning_changing (contradicts_main_point + changes_meaning)'],
        'minor': sev['minor (minor_detail + cosmetic)'],
        'not_real_error': o['not_really_a_content_error']['either_or_cosmetic'],
        'truth_in_context': o['avoidability_guess']['context_makes_it_obvious'],
        'one_off_pct': dist['overall_all']['one_off_pct'], 'sticky_pct': dist['overall_all']['sticky_pct'],
        'consensus_removable_pct': recurrence['consensus_removable_pct']['est'],
        'clean_sample_available': f"{ov['consistent_available']['num']}/72",
        'best_of_32_clean': f"{ov['top_fve_clean']['num']}/72"},
    'severity': {'overall': o['severity'], 'grouped': sev, 'gist_correct': o['gist_correct'],
                 'avoidability_guess': o['avoidability_guess'],
                 'by_setting': {s: {'grouped': v['severity_grouped'], 'gist_correct': v['gist_correct'],
                                    'not_real_error': v['not_really_a_content_error']['either_or_cosmetic']}
                                for s, v in st['by_setting'].items()},
                 'by_source': {s: {'grouped': v['severity_grouped'], 'gist_correct': v['gist_correct'],
                                   'persona': v['type']['self_or_persona_claim']} for s, v in st['by_source'].items()},
                 'meaning_changing_records': st['meaning_changing_records'], 'minor_records': st['minor_records'],
                 'crosstab_avoidability_x_severity': st['crosstab_avoid_x_severity']},
    'type_table': type_table,
    'recurrence': recurrence,
    'avoidability': avoid,
    'judge_noise': judge_noise,
    'rep_cases': rep_cases,
}
p = f'{HERE}/errors_page.json'
json.dump(out, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
print('wrote', p, os.path.getsize(p), 'bytes; quote fixes', dict(nfix))
