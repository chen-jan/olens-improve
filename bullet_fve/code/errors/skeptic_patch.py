#!/usr/bin/env python
"""Apply the skeptic-pass (2026-10-15) changes to errors/errors_page.json (idempotent; exploratory).

Reads the CURRENT errors_page.json (keeping edits others made after the build), replaces the
summary-point texts listed below, adds a `skeptic` block to the recurrence / avoidability /
judge_noise / headline sections from errors/skeptic_checks.json, and writes the file atomically.
Re-run after any rebuild with build_errors_page.py (which would revert these texts).
Pre-pass backup: errors_page.pre-skeptic.bak.json.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = f'{HERE}/errors_page.json'
SK = json.load(open(f'{HERE}/skeptic_checks.json'))
d = json.load(open(PATH))
MARK = '[skeptic 2026-10-15]'

SP = {
    0: ('Most "hallucinations" keep the gist', None,
        'Most "hallucinations" keep the gist. In a representative sample of 240 judge-verified wrong bullets, readers judged '
        'the bullet\'s main point right in 89% [84, 94]. The commonest pattern (about 63%) is one wrong slot: a name or entity '
        '(28% [21, 36]), an attribute or relation (23% [17, 30]) or a number (12% [6, 17]).'),
    2: ('copy a value that is right there', None,
        'By the readers\' coding, the lens often fails to copy a value that is right there: in 45% [37, 53] of wrong bullets '
        'the truth is in the prompt or in the reply before the read site, and these hold 58 of the 90 meaning-changing errors. '
        'That link is partly built into the coding: a contradiction with visible text is easier to rate as meaning-changing '
        'than an unsupported invention, and readers saw pool counts while coding. For name/number errors with an identifiable '
        'true value, the value is visible before READ in 76–84%.'),
    3: ('one-off sampling noise', ['chat-lmsys-0070.L52.p154', 'chat-dailydialog-0030.L44.p65', 'chat-lmsys-0024.L36.p253',
                                   'chat-lmsys-0043.L44.p391'],
        'Roughly a third to a half of wrong spans look like one-off sampling noise, and roughly 15–30% are sticky. The split '
        'depends on the word-matching rule. Requiring all of a span\'s key words in one sample gives 46.9% one-off and 20.9% '
        'sticky. Spans keyed on one novel name or number, where the rule does not matter, give 37% and 27%. Any one key word '
        'gives 20% and 45%. A hand check of 30 random sticky rows found 9 keyed on a word that is not the error ("called", '
        '"10"). Of 30 one-offs, 3 were one-off only because a rare second word was required ("methyl" is in 30/32). A '
        'majority vote would remove 74–79% of wrong spans, but it also drops about half of the true claims.'),
    4: ('a vote cannot restore a value', ['chat-dailydialog-0045.L20.p65', 'chat-lmsys-0023.L20.p464', 'chat-lmsys-0025.L52.p236'],
        'But a vote cannot restore a value the lens never outputs. For name/number errors, the true value appears in none '
        'of the 32 samples in 32–55% of cases, and in a majority of samples in only 18–32%. Removing "Alice" still leaves '
        '"Sarah" for "Mary". Translation does not explain this: in 25 Chinese-heavy cases, the truth was written in Chinese only once.'),
    6: ('Selection has headroom', None,
        'Selection has headroom. FVE shows no detectable use of it, but the test is small. In 72 fully judged development '
        'cells, a clean sample existed in 54/72 (41/72 after removing "clean" samples that repeat a text flagged elsewhere). '
        'A perfect picker would rescue 32/46 of the cells where Original hallucinates. Requiring at least 3 clean samples '
        'gives 23/46, and the strict reading 19/46. Best of 32 rescued 8. The top-FVE sample was clean in 24/72 cells against '
        '23.8 for a random pick (difference +0.2 cells [−3.5, +4.6]; consistent-vs-hallucinated FVE AUC 0.53 [0.49, 0.58]). '
        'So the pilot rules out a large FVE effect, not a small one. In the full bank, Best of 32 lowers hallucinated readouts '
        'by 1.6 points [0.3, 3.0].'),
    7: ('depends mostly on the chat', None,
        'In the pilot, whether an error is avoidable depends mostly on the chat. The hallucinated share of samples ranges '
        'from 8% to 84% across the 8 chats but only 51–58% across layers; chat explains 47% of the cell-to-cell variance and '
        'layer 1%. All 27 dailydialog pilot cells had a clean sample and 18 of 45 lmsys cells had none, but that is 3 chats '
        'against 5. One chat (sodium nitrite solubility) had none in 8 of 9 cells. Stickiness is flat by setting '
        '(21.3% / 21.7% / 19.7%) and layer (19.9–21.8%), but the settings share one 32-sample pool, so the setting comparison '
        'only shows that FVE selection does not prefer sticky errors.'),
    8: ('Judge labels are noisy', None,
        'Judge labels are noisy at the bullet level, in both directions. When identical bullet text sits in two readouts of '
        'a cell and one copy is WRONG, the other copy is also WRONG only 65% of the time; equivalently, the labels differ in '
        '52% of such pairs. In the fully judged pilot, an exact wrong span that recurs in another sample is flagged again only '
        '67% of the time. The judge also misses errors: 133 of 762 "clean" pilot samples contain a span flagged elsewhere.'),
    9: ('Implication', None,
        'Implication: ranking more samples by FVE barely reduces hallucination (1.6 points in the full bank). A correctness '
        'signal that can pick among samples (cross-sample agreement on names and numbers, and checking names/numbers against '
        'the prompt and earlier reply) has room to help with the one-off errors, but the cell-level headroom is smaller than '
        '"half the errors". In the pilot, a clean sample exists for 32 of 46 Original-hallucinated cells (23 with at least 3 '
        'clean samples, 19 strict), and most singleton spans (836 of 1,246) sit in hard or unavoidable cells. No such signal '
        'has been tested yet. The sticky part, whose true value never appears in the pool, needs a better lens read, not '
        'better selection.'),
}
changed = []
for i, (key, cases, text) in SP.items():
    sp = d['summary_points'][i]
    if sp['text'] == text:
        continue
    assert key in sp['text'], (i, key, sp['text'][:80])
    sp['text'] = text
    if cases:
        sp['cases'] = cases
    changed.append(f'summary_points[{i}]')
# summary point 5 (index 5): append the standardised check once
sp5 = d['summary_points'][5]
add5 = (' The gap holds when true claims are matched to wrong spans on number of key words (48% vs 25%; names and numbers '
        '68% vs 30%).')
if add5.strip() not in sp5['text']:
    assert 'Recurrence partly separates' in sp5['text']
    sp5['text'] += add5
    changed.append('summary_points[5]')

# featured example lmsys-0043: binding error, not a missing value
for t in d['type_table']:
    for e in t['examples']:
        if e['k'] == 'chat-lmsys-0043.L60.p391' and 'binding error' not in e['note']:
            e['note'] += (' Because the right 2-position group is in a majority of samples, this is mostly a binding error '
                          '(groups attached to the wrong positions), not a value the lens never outputs.')
            changed.append('type_table example chat-lmsys-0043.L60.p391 note')
        if e['k'] == 'chat-lmsys-0040.L36.p65':
            assert '"250" is in 2/32' in e['note'], e['note']

s1, s5 = SK['1_recurrence_rule_sensitivity'], SK['5_pilot']
d['headline']['skeptic'] = {
    'one_off_pct_range': '20–54 (primary rule 46.9; single name/number 37.0)',
    'sticky_pct_range': '15–45 (primary rule 20.9; single name/number 26.5)',
    'perfect_picker_rescue_of_46': {'face_value': 32, 'ge3_clean': 23, 'strict': 19, 'strict_ge3': 12},
    'top_fve_clean_minus_random_cells': s5['top_fve_clean_minus_random_cells'],
}
d['recurrence']['skeptic'] = {
    'note': 'The one-off / sticky split depends on the matching rule (all / 2 / any key words) and on the number of key words; '
            'the lexical grade misgrades in both directions (hand check). Treat shares as ranges.',
    'rule_sensitivity': s1,
    'vote_keep_standardised_to_wrong_n_elements': SK['2_vote_keep_standardised'],
    'sticky_cross_layer': SK['3_sticky_in_same_setting_readout_other_layer'],
    'truth_in_pool_translation_check': SK['4_truth_in_pool_translation'],
    'hand_checks': {k: SK['6_hand_checks'][k] for k in ('sticky_rows', 'one_off_rows')},
}
d['avoidability']['skeptic'] = {k: s5[k] for k in (
    'rescuable_face_value', 'rescuable_with_ge3_clean_samples', 'rescuable_with_only_1_or_2_clean_samples', 'rescuable_strict',
    'rescuable_strict_with_ge3_nonsuspect_clean', 'hallucinated_share_variance_by_chat_vs_layer',
    'fve_auc_consistent_over_hallucinated_within_cell', 'top_fve_clean_minus_random_cells', 'strict_rule_suspects',
    'pilot_vs_bank_original_hallucinated_of_specific', 'pilot_site_rule', 'judge_pins_checked')}
d['avoidability']['skeptic']['note'] = ('Pilot = 8 chats (3 dailydialog, 5 lmsys); chat-bootstrap intervals with 8 clusters are approximate. '
                                        'Clean availability is judge-optimistic; FVE null rules out a large effect only.')
d['judge_noise']['skeptic'] = {
    'twin_also_wrong_per_wrong_copy_pct': 65,
    'note': 'Primary framing: given one WRONG copy of an identical bullet, the twin is also WRONG 65% of the time (labels differ in 52% '
            'of such pairs). Noise runs both ways: ~21% of flagged bullets are not content errors by the readers (about 4 points '
            'cosmetic), while 133/762 pilot "clean" samples contain a span flagged elsewhere; the net effect on rates is unknown. '
            'The judge prompt does say not to mark reasonable continuations "even when the response actually went a different way".',
}
d['meta']['skeptic_pass'] = {
    'date': '2026-10-15',
    'checks': 'errors/skeptic_checks.py -> errors/skeptic_checks.json',
    'patch': 'errors/skeptic_patch.py (idempotent; re-run after build_errors_page.py)',
    'backup': 'errors/errors_page.pre-skeptic.bak.json',
    'report_section': 'ERRORS.md section 6',
    'changed_summary_points': [0, 2, 3, 4, 5, 6, 7, 8, 9],
}
tmp = PATH + '.tmp'
with open(tmp, 'w') as f:
    json.dump(d, f, ensure_ascii=False, separators=(',', ':'))
os.replace(tmp, PATH)
print('changed:', changed or 'nothing new (already applied)')
