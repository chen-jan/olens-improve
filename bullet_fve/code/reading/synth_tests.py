"""Synthesis of the Bullet-FVE reading study (exploratory).

Part A tabulates the 288 reader records (reading/records/batch_*.json) and writes reading/tables.json and
reading/tables.md. Part B tests the claims that came out of the reading on ALL bullets of all 5,615 cells x 3 scored
settings, using proxies computable from page/data/items/*.json, with chat-level (149 items) percentile bootstrap
intervals (1000 reps, seed 0). Outputs go to reading/synth_tests.json.

Run:
  ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B synth_tests.py

Everything here is exploratory: all chats were inspected before, the reading sample is stratified (not random),
the reader verdicts are single readings, and the text proxies (lexical overlap, CJK fraction, novel numbers/names)
are rough. Offsets in the data are UTF-16 code units.
"""
import collections
import difflib
import glob
import json
import math
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = '${OLENS_SCRATCH}/olens-bullet-fve/page/data'
REC = os.path.join(HERE, 'records')
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
RAW = 'raw_n1-n1'
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32',
         RAW: 'Raw'}
NREP, SEED = 1000, 0
STRATA = ['A_wrong_high', 'B_wrong_low', 'C_clean_low_in_halluc', 'D_clean_high_in_consistent', 'E_disagree',
          'F_wrong_unscored', 'G_offtopic']
BLIND = ['invented_specific_detail', 'wrong_relation_or_attribute', 'persona_or_self_claim',
         'misread_prompt_or_context', 'off_topic_junk', 'generic_or_vague', 'plausible_continuation_not_taken',
         'judge_overstrict', 'not_wrong_clean']
READER_CLASS = {'invented_specific_detail': 'error', 'wrong_relation_or_attribute': 'error',
                'persona_or_self_claim': 'error', 'misread_prompt_or_context': 'error', 'off_topic_junk': 'junk',
                'generic_or_vague': 'vague', 'plausible_continuation_not_taken': 'no_error',
                'judge_overstrict': 'no_error', 'not_wrong_clean': 'no_error'}

# ============================================================================= Part A: reading records
recs = []
for f in sorted(glob.glob(os.path.join(REC, 'batch_*.json'))):
    with open(f) as fh:
        for i, r in enumerate(json.load(fh)):
            r = dict(r)
            r['batch'] = os.path.basename(f)[6:8]
            r['slot'] = i
            recs.append(r)
with open(os.path.join(HERE, 'sample.json')) as fh:
    SAMPLE = json.load(fh)
smp = {(c['k'], c['setting'], c['bullet']): c for c in SAMPLE['cases']}
for r in recs:
    c = smp[(r['k'], r['setting'], r['bullet'])]
    for x in ['substratum', 'label', 'readout', 'share', 'solo', 'coef', 'drop', 'fve', 'L', 'source', 'truncated',
              'labels_all_settings']:
        r[x] = c[x]
assert len(recs) == 288

# Hand coding (by the synthesiser, from the readers' 'all settings' notes) of WHY the three settings disagree for
# the 48 E_disagree cells. judge_inconsistent = the same or near-identical content gets different verdicts across
# settings; judge_overstrict = the flagged span is, per the reader, a reasonable continuation and the other settings
# simply lack it; span_match = a span 'NOT counted' decides the label; sample_change_real = the settings carry
# different samples and one of them contains an error the reader accepts as real.
E_CAUSE = {
    # E1: Original hallucinated, Best of 32 consistent (focus bullet from Original)
    'chat-dailydialog-0007.L36.p101': ('sample_change_real', 'stance clause "there’s no reason to fear it" only in the Original sample'),
    'chat-dailydialog-0027.L36.p59': ('judge_inconsistent', '"finding a gift idea" WRONG in Original, "find the perfect gift idea" clean in Best and Combine'),
    'chat-dailydialog-0031.L52.p300': ('judge_inconsistent', 'same sample-#28 "fresh, original idea" bullet clean in Best, OFF-TOPIC in Combine'),
    'chat-dailydialog-0032.L20.p44': ('sample_change_real', 'different odd tail after the same correct prefix in each setting ("virtual library")'),
    'chat-dailydialog-0042.L20.p67': ('sample_change_real', 'Original sample swaps the baby for a wedding'),
    'chat-dailydialog-0049.L44.p215': ('judge_inconsistent', 'identical "Internal Structure" text WRONG as Original b3, clean as Combine b2'),
    'chat-dailydialog-0053.L60.p187': ('judge_inconsistent', 'invented item-4 heading WRONG in Original, stage-2 true in Best/Combine'),
    'chat-dailydialog-0058.L60.p59': ('judge_inconsistent', '"at each restaurant" WRONG in Original, "for each restaurant" unflagged in Combine'),
    'chat-dailydialog-0063.L44.p118': ('sample_change_real', 'first-person taste claims only in the Original sample (Raw with identical text judged consistent)'),
    'chat-dailydialog-0069.L20.p244': ('judge_inconsistent', '"substance abuse" WRONG in Original, "signs of overdose" unverifiable in Best'),
    'chat-dailydialog-0071.L20.p154': ('judge_inconsistent', '"Answering thousands of questions" WRONG in Original, unverifiable in Best'),
    'chat-dailydialog-0073.L36.p36': ('sample_change_real', 'privacy claim only in the Original sample; Best/Combine vaguer'),
    'chat-lmsys-0010.L36.p45': ('sample_change_real', 'invented "EDESKTOP" only in the Original sample'),
    'chat-lmsys-0022.L52.p102': ('span_match', 'Best of 32 consistent only because its wrong span was NOT counted (backticks)'),
    'chat-lmsys-0029.L44.p83': ('sample_change_real', 'Original assigns the shortcut to Pause; Best uses generic wording'),
    'chat-lmsys-0030.L60.p95': ('sample_change_real', 'different filler in a shared template ("installing the library via pip"); readers split on the flag'),
    'chat-lmsys-0032.L60.p112': ('judge_overstrict', 'invented numbered heading after a list item flagged; reader calls it a reasonable continuation'),
    'chat-lmsys-0034.L52.p470': ('sample_change_real', 'garbled formula name "Bredt-Batavier" only in the Original sample'),
    'chat-lmsys-0035.L52.p502': ('sample_change_real', 'Original scales by "number of Americans"; Best sample names area targets'),
    'chat-lmsys-0036.L44.p51': ('judge_inconsistent', 'borderline modality span; equally unsupported claims clean elsewhere'),
    'chat-lmsys-0041.L60.p237': ('judge_inconsistent', 'conditional "impossible" WRONG in Original, same claim unverifiable in Best'),
    'chat-lmsys-0052.L52.p302': ('judge_inconsistent', '"85°C" WRONG in Original, Best "212°F" equally off but unflagged'),
    'chat-lmsys-0068.L44.p104': ('judge_inconsistent', 'identical sample-#22 bullet clean in Best, WRONG in Combine'),
    'chat-lmsys-0070.L20.p253': ('sample_change_real', 'invented company name "MintSolutions" only in the Original sample'),
    # E2: Original consistent, Combine 32 hallucinated (focus bullet from Combine)
    'chat-dailydialog-0010.L52.p24': ('judge_inconsistent', 'identical "or a bank account" bullet clean in Original, WRONG in Combine'),
    'chat-dailydialog-0012.L20.p26': ('judge_inconsistent', 'similar self-inclusive social claim only unverifiable in Best'),
    'chat-dailydialog-0020.L36.p60': ('sample_change_real', 'Combine pools sample #1 "your father\'s new job"'),
    'chat-dailydialog-0022.L60.p48': ('judge_inconsistent', 'coffee remark WRONG once, unverifiable in three other bullets'),
    'chat-dailydialog-0028.L44.p318': ('sample_change_real', 'Combine pools sample #10 with the name "John" for Joe'),
    'chat-dailydialog-0036.L36.p66': ('sample_change_real', 'Combine pools sample #24 "fictional pizzeria"'),
    'chat-dailydialog-0044.L60.p136': ('sample_change_real', 'Best and Combine both pick sample #4 Mid-Autumn bullet'),
    'chat-dailydialog-0046.L60.p22': ('sample_change_real', 'Combine adds a polarity-flipped 4th bullet (drop 0.0011)'),
    'chat-dailydialog-0054.L20.p107': ('judge_inconsistent', '"suggest snacks" clean in Original, WRONG in Combine'),
    'chat-dailydialog-0057.L36.p46': ('judge_inconsistent', '"usual spot" questions unverifiable, declarative "usual bar" WRONG'),
    'chat-dailydialog-0070.L60.p252': ('judge_inconsistent', 'similar pessimistic stance clean in Original/Best'),
    'chat-dailydialog-0072.L20.p84': ('judge_inconsistent', 'identical sample-#1 text clean in Best, WRONG in Combine'),
    'chat-lmsys-0001.L52.p484': ('judge_inconsistent', 'identical sample-#10 bullet WRONG in Best, clean in Combine; same claim clean in b0/b1'),
    'chat-lmsys-0005.L60.p169': ('judge_inconsistent', 'near-identical story-choice content true/unverifiable in Original, WRONG in Combine'),
    'chat-lmsys-0018.L52.p350': ('sample_change_real', 'Combine pools sample #5 with an inverted bound (also identical-text verdict flip)'),
    'chat-lmsys-0024.L44.p451': ('judge_inconsistent', 'same frame, "Existential AI Risk" clean in Original, near-synonym WRONG in Best'),
    'chat-lmsys-0042.L36.p99': ('span_match', 'Original consistent only because its "Laravel validation" span was NOT counted'),
    'chat-lmsys-0048.L36.p255': ('judge_inconsistent', 'equally invented food details unverifiable in Original'),
    'chat-lmsys-0051.L44.p313': ('judge_inconsistent', 'MDMA-therapy wording clean in Original/Best, WRONG in Combine'),
    'chat-lmsys-0054.L52.p358': ('judge_inconsistent', 'nearly identical "distribute reports" content; single-token oddities flagged unevenly'),
    'chat-lmsys-0056.L52.p231': ('judge_inconsistent', '"print ... (`first`)" WRONG in Best, stage-2 true in Combine'),
    'chat-lmsys-0059.L20.p350': ('judge_inconsistent', 'identical sample-#29 bullet clean in Best, WRONG in Combine'),
    'chat-lmsys-0063.L20.p520': ('judge_inconsistent', 'identical sample-#6 string clean in Best, WRONG in Combine'),
    'chat-lmsys-0066.L44.p403': ('judge_inconsistent', 'identical sample-#15 heading clean in Best, WRONG in Combine'),
}

# keyword codes (heuristic; several can apply to one record)
REL_CODES = collections.OrderedDict([
    ('right_frame_or_slot', r'right (?:slot|frame|template|form|format|structure|syntactic slot|gist|genre|speech act|operation|section|pivot|role|topic)|correct (?:slot|frame|format|structure|template|local format|speech act|pivot|discourse frame)|format-correct|same (?:template|structure|genre|kind)|structure right|format right|reproduces the exact|exact (?:item )?template|right theme|gets the (?:format|pivot|frame)'),
    ('filler_swapped', r'swap|substitut|instead of|replac|in place of|renamed|wrong (?:name|entity|country|festival|value|values|number|person|subject|object|interface|method|activity|department|season|language|label|annex|mechanism|scaling|type system|persona|recipient|letter|frame|topic|domain|emotion|plant)|invented (?:name|number|value)|garbl|misnam|neighbou?r'),
    ('predicts_next_text', r'paraphras|verbatim|near-literal|literal|exact(?:ly)? (?:predicts|next|right next|match)|predicts the (?:next|exact|reply)|matches the (?:next|actual|reply)|close(?:ly)? (?:paraphrase|tracks|match)|correctly (?:predicts|anticipates|continues|describes)|accurate (?:prediction|paraphrase)|anticipat'),
    ('echoes_earlier_text', r'restat|echo|recap|already written|before the marker|just before|just ended|written before|looks backward|points back'),
    ('plausible_untaken_continuation', r'plausible|reasonable (?:continuation|next|caveat|guess)|not taken|did not take|didn\'t take|natural continuation|untaken'),
    ('adds_unsupported_detail', r'invent|unsupported|embellish|adds |added |extra '),
    ('topic_or_domain_drift', r'off-topic|unrelated|junk|drift|wrong (?:topic|domain)|topic swap|loses? the topic|another domain|different (?:task|domain)'),
    ('persona_self_claim', r'persona|self-claim|self-identity|in-character|role-confused|self-description|first-person'),
])
SCORE_CODES = collections.OrderedDict([
    ('frame_template_format', r'frame|template|format|structure|register|layout|syntax|syntactic|shape|form\b'),
    ('opening_matches_next_text', r'first token|first word|opening|opens with|opener|starts with|begins|literal next|next token|next words|next-word|verbatim|word for word|exact next|next phrase|next line|next sentence|next clause'),
    ('error_invisible_to_score', r'ignor|invisible|costs nothing|cost nothing|not penali|no visible|does not see|blind to|cannot see|does not register|does not care|barely|no part|plays no|does not show up|nothing visible|unchanged|does not lower|not obviously lower|indifferent'),
    ('mentions_redundancy_any_bullet', r'coef 0(?![.\d])|coef 0\.0+(?!\d)|redundan|near-duplicate|duplicat|drop 0(?![.\d])|drop 0\.0+(?!\d)|absorb'),
    ('unscored_tail', r'unscored|32-token|past the 32|AR limit|reconstructor limit|32 scored tokens|scoring limit|AR window'),
    ('short_or_fragment', r'\bshort|length|longer|one line|fragment|terse'),
    ('language_script', r'Chinese|language|code-switch|CJK|script'),
    ('whole_readout_low', r'low-FVE readout|joint FVE (?:is )?(?:only|low)|weak readout|near-floor|whole cell|low cell|barely reconstructs|near-zero|weak L20|very low|low overall|poorly explained|whole readout'),
    ('echo_or_backward', r'echo|restat|recap|already written|just ended|already said|already covered|backward'),
])
NOTE_CODES = collections.OrderedDict([
    ('span_not_counted', r'NOT counted|text not found|shorter than 3|3-character|under 3 characters|string-match|span-matching|text-match|span matching'),
    ('cross_setting_inconsistency', r'identical (?:text|bullet|string|sample)|same text|same bullet|same content|opposite verdicts|different verdicts|two verdicts|three verdicts|near-identical|judge (?:is )?inconsisten|judge inconsistency|judge variance|judge noise|inconsistent across settings|treated inconsistently|treats .{0,40}inconsistently'),
    ('judge_overstrict_note', r'overstrict|over-strict|strict|pedantic|nitpick'),
    ('judge_misreads_chinese', r'misread the Chinese|judge misread|stray Chinese|foreign-language|untranslated|garbled fragment|script mixing|penalises language|language, not content|code-switching treated'),
    ('stage2_rationale_glitch', r'established (?:as )?false|established-false|stage-2 text glitch|template glitch|judge glitch|rationale text inconsistent'),
    ('lenient_or_missed', r'lenient|missed|judge miss|not flagged|unflagged|false negative|was not flagged|only stage-2|let it pass'),
])


def code_text(text, codes):
    return [c for c, pat in codes.items() if re.search(pat, text, flags=re.I)]


def crosstab(rows, rkey, ckey, rorder=None, corder=None):
    ct = collections.defaultdict(collections.Counter)
    for r in rows:
        rv, cvs = rkey(r), ckey(r)
        if not isinstance(cvs, list):
            cvs = [cvs]
        for cv in cvs:
            ct[rv][cv] += 1
    rorder = rorder or sorted(ct)
    corder = corder or sorted({c for v in ct.values() for c in v})
    return {'rows': rorder, 'cols': corder, 'counts': {r: {c: ct[r][c] for c in corder} for r in rorder},
            'row_n': {r: sum(1 for x in rows if rkey(x) == r) for r in rorder}}


for r in recs:
    r['reader_class'] = READER_CLASS[r['blind_type']]
    r['rel_codes'] = code_text(r['relation_to_context'], REL_CODES)
    r['score_codes'] = code_text(r['score_reading'], SCORE_CODES)
    r['note_codes'] = code_text(r['note'] + ' ' + r['score_reading'], NOTE_CODES)
    r['setting_short'] = SHORT[r['setting']]

tables = {}
tables['blind_type_by_stratum'] = crosstab(recs, lambda r: r['stratum'], lambda r: r['blind_type'], STRATA, BLIND)
tables['blind_type_by_setting'] = crosstab(recs, lambda r: r['setting_short'], lambda r: r['blind_type'],
                                           ['Original', 'Best of 32', 'Combine 32'], BLIND)
tables['blind_type_by_setting_within_wrong_strata_ABF'] = crosstab(
    [r for r in recs if r['stratum'] in ('A_wrong_high', 'B_wrong_low', 'F_wrong_unscored')],
    lambda r: r['setting_short'], lambda r: r['blind_type'], ['Original', 'Best of 32', 'Combine 32'], BLIND)
tables['blind_type_by_source'] = crosstab(recs, lambda r: r['source'], lambda r: r['blind_type'],
                                          ['dailydialog', 'lmsys'], BLIND)
tables['judge_agrees_by_stratum'] = crosstab(recs, lambda r: r['stratum'], lambda r: r['judge_agrees'], STRATA,
                                             ['yes', 'partly', 'no'])
tables['judge_agrees_by_setting'] = crosstab(recs, lambda r: r['setting_short'], lambda r: r['judge_agrees'],
                                             ['Original', 'Best of 32', 'Combine 32'], ['yes', 'partly', 'no'])
LABN = {'w': 'judge WRONG', 'c': 'judge clean', 'o': 'judge OFF-TOPIC'}
tables['judge_label_vs_reader_class'] = crosstab(recs, lambda r: LABN[r['label']], lambda r: r['reader_class'],
                                                 ['judge WRONG', 'judge clean', 'judge OFF-TOPIC'],
                                                 ['error', 'junk', 'vague', 'no_error'])
tables['judge_label_vs_reader_class_by_stratum'] = {
    st: crosstab([r for r in recs if r['stratum'] == st], lambda r: LABN[r['label']], lambda r: r['reader_class'],
                 None, ['error', 'junk', 'vague', 'no_error']) for st in STRATA}


def direction(r):
    lab, rc = r['label'], r['reader_class']
    if lab == 'w':
        return {'error': 'agree_wrong', 'junk': 'boundary_wrong_vs_offtopic', 'vague': 'agree_weak',
                'no_error': 'judge_too_strict'}[rc]
    if lab == 'c':
        return {'error': 'judge_missed_error', 'junk': 'judge_missed_junk', 'vague': 'agree_weak',
                'no_error': 'agree_clean'}[rc]
    return {'error': 'boundary_offtopic_should_be_wrong', 'junk': 'agree_offtopic', 'vague': 'agree_weak',
            'no_error': 'judge_too_strict'}[rc]


DIRS = ['agree_wrong', 'agree_clean', 'agree_offtopic', 'agree_weak', 'judge_too_strict', 'judge_missed_error',
        'judge_missed_junk', 'boundary_offtopic_should_be_wrong', 'boundary_wrong_vs_offtopic']
tables['disagreement_direction_by_stratum'] = crosstab(recs, lambda r: r['stratum'], direction, STRATA, DIRS)
tables['disagreement_direction_by_setting'] = crosstab(recs, lambda r: r['setting_short'], direction,
                                                       ['Original', 'Best of 32', 'Combine 32'], DIRS)
tables['relation_codes_by_stratum'] = crosstab(recs, lambda r: r['stratum'], lambda r: r['rel_codes'] or ['none'],
                                               STRATA, list(REL_CODES) + ['none'])
tables['score_codes_by_stratum'] = crosstab(recs, lambda r: r['stratum'], lambda r: r['score_codes'] or ['none'],
                                            STRATA, list(SCORE_CODES) + ['none'])
tables['note_codes_by_stratum'] = crosstab(recs, lambda r: r['stratum'], lambda r: r['note_codes'] or ['none'],
                                           STRATA, list(NOTE_CODES) + ['none'])
e_rows = []
for r in recs:
    if r['stratum'] != 'E_disagree':
        continue
    cause, why = E_CAUSE[r['k']]
    e_rows.append({'k': r['k'], 'sub': r['substratum'], 'setting': r['setting_short'], 'cause': cause, 'why': why,
                   'judge_agrees': r['judge_agrees'], 'blind_type': r['blind_type'],
                   'labels': {SHORT[s]: r['labels_all_settings'][s] for s in SIDS}})
assert len(e_rows) == 48
ECAUSES = ['judge_inconsistent', 'judge_overstrict', 'span_match', 'sample_change_real']
tables['E_disagree_cause'] = crosstab(e_rows, lambda r: r['sub'], lambda r: r['cause'],
                                      ['E1_orig_halluc_best_consistent', 'E2_orig_consistent_combine_halluc'],
                                      ECAUSES)
tables['E_disagree_real_change_kinds'] = crosstab([r for r in e_rows if r['cause'] == 'sample_change_real'],
                                                  lambda r: r['sub'], lambda r: r['blind_type'], None, BLIND)
tables['E_disagree_cases'] = e_rows

# reading-record summary numbers used in the claims
low_strata = ('B_wrong_low', 'C_clean_low_in_halluc')
tables['reading_summary'] = {
    'n_records': len(recs),
    'reader_judge_disagree_any': sum(r['judge_agrees'] != 'yes' for r in recs),
    'reader_judge_disagree_no': sum(r['judge_agrees'] == 'no' for r in recs),
    'A_frame_or_next_text_and_error_invisible': sum(
        1 for r in recs if r['stratum'] == 'A_wrong_high' and ('frame_template_format' in r['score_codes']
                                                               or 'opening_matches_next_text' in r['score_codes'])
        and 'error_invisible_to_score' in r['score_codes']),
    'A_n': sum(r['stratum'] == 'A_wrong_high' for r in recs),
    'low_BC_coef0_or_short_or_script_or_wholelow': sum(
        1 for r in recs if r['stratum'] in low_strata and (r['coef'] == 0 or set(r['score_codes']) & {
            'short_or_fragment', 'language_script', 'whole_readout_low'})),
    'low_BC_coef0_or_short_or_script_or_wholelow_or_frame_or_echo': sum(
        1 for r in recs if r['stratum'] in low_strata and (r['coef'] == 0 or set(r['score_codes']) & {
            'short_or_fragment', 'language_script', 'whole_readout_low', 'frame_template_format',
            'opening_matches_next_text', 'echo_or_backward'})),
    'low_BC_n': sum(r['stratum'] in low_strata for r in recs),
    'low_BC_coef0_in_sample': sum(1 for r in recs if r['stratum'] in low_strata and r['coef'] == 0),
    'focus_coef0_by_stratum': {st: sum(1 for r in recs if r['stratum'] == st and r['coef'] == 0) for st in STRATA},
    'A_vs_B_reader_error_class': {st: dict(collections.Counter(r['reader_class'] for r in recs if r['stratum'] == st))
                                  for st in ('A_wrong_high', 'B_wrong_low')},
    'A_vs_B_error_with_frame_or_next_or_swap_codes': {st: sum(
        1 for r in recs if r['stratum'] == st and r['reader_class'] == 'error' and set(r['rel_codes']) & {
            'right_frame_or_slot', 'filler_swapped', 'predicts_next_text'}) for st in ('A_wrong_high', 'B_wrong_low')},
    'judge_agrees_by_setting_ABF': {SHORT[sid]: dict(collections.Counter(
        r['judge_agrees'] for r in recs if r['setting'] == sid and r['stratum'] in ('A_wrong_high', 'B_wrong_low',
                                                                                     'F_wrong_unscored')))
        for sid in SIDS},
    'C_reader_says_error': sum(1 for r in recs if r['stratum'] == 'C_clean_low_in_halluc'
                               and r['reader_class'] == 'error'),
    'F_judge_too_strict': sum(1 for r in recs if r['stratum'] == 'F_wrong_unscored' and r['reader_class'] == 'no_error'),
    'span_not_counted_mentions': sum('span_not_counted' in r['note_codes'] for r in recs),
    'cross_setting_inconsistency_mentions': sum('cross_setting_inconsistency' in r['note_codes'] for r in recs),
    'stage2_glitch_mentions': sum('stage2_rationale_glitch' in r['note_codes'] for r in recs),
    'judge_misreads_chinese_mentions': sum('judge_misreads_chinese' in r['note_codes'] for r in recs),
    'G_reader_says_junk': sum(1 for r in recs if r['stratum'] == 'G_offtopic' and r['blind_type'] == 'off_topic_junk'),
    'G_n': sum(r['stratum'] == 'G_offtopic' for r in recs),
}

# ============================================================================= Part B: all-data features
CJKR = '㐀-䶿一-鿿豈-﫿'
CJK_CHAR = re.compile('[' + CJKR + ']')
TOK = re.compile('[' + CJKR + ']|[^\\W_' + CJKR + ']+')
NUM = re.compile(r'\d+(?:[.,]\d+)*')
CAPW = re.compile(r'(?<![\w])([A-Z][A-Za-z\-]+)')
FP = re.compile(r"(?<![A-Za-z])(?:I|I'm|I’m|I've|I’ve|I'd|I’d|I'll|I’ll|me|my|myself|mine)(?![A-Za-z])|我")
NUM_OPEN = re.compile(r'^\W{0,4}\d+\s*[.):]')
NEXT_NUM = re.compile(r'^\W{0,6}\d')


def u16(s):
    return s.encode('utf-16-le')


def sl(b, a, e):
    a, e = max(0, a), max(0, e)
    return b[2 * a:2 * e].decode('utf-16-le', errors='replace')


def toks(s):
    return [t.lower() for t in TOK.findall(s)]


def cjk_frac(s):
    ns = [c for c in s if not c.isspace()]
    return (len(CJK_CHAR.findall(s)) / len(ns)) if ns else 0.0


def novel_caps(span, vocab):
    out = []
    for m in CAPW.finditer(span):
        pre = span[:m.start()].rstrip()
        if not pre or pre[-1] in '.!?:"“”*#-—–(（[>|`\'‘’' or m.group(1) in ('I', 'I’m'):
            continue
        if m.group(1).lower() not in vocab:
            out.append(m.group(1))
    return out


items, cells = {}, {}
for f in sorted(glob.glob(os.path.join(DATA, 'items', '*.json'))):
    with open(f) as fh:
        d = json.load(fh)
    it = d['item']
    items[it['id']] = it
    for k, c in d['cells'].items():
        cells[k] = (it['id'], c)
ITEM_IDS = sorted(items)
ITEM_IX = {x: i for i, x in enumerate(ITEM_IDS)}

rows = []           # one per bullet of the 3 scored settings
readouts = {}       # (k, sid) -> dict
for k, (iid, c) in cells.items():
    it = items[iid]
    resp, prompt = it['response'], it['prompt']
    rb = u16(resp)
    after, before = sl(rb, c['char'], c['char'] + 800), sl(rb, c['char'] - 800, c['char'])
    nxt = toks(after)[:40]
    nxt80 = set(toks(after)[:80])
    prv = toks(before)[-40:]
    nset, pset = set(nxt), set(prv)
    ctx_vocab = set(toks(prompt + ' ' + resp))
    ctx_nums = set(NUM.findall(prompt + ' ' + resp))
    next_first = nxt[0] if nxt else None
    next_is_num = bool(NEXT_NUM.match(after))
    for sid in SIDS:
        s = c['settings'][sid]
        tb = u16(s['text'] or '')
        wr = [(a, e) for sp in s['spans'] if sp['verified'] and sp['type'] == 'wrong' for a, e in sp['offsets']]
        bl = s['bullets']
        cl_status = collections.defaultdict(collections.Counter)
        for cl in s.get('claims') or []:
            for jj in cl.get('bullets') or []:
                cl_status[jj][cl['status']] += 1
        readouts[(k, sid)] = {'k': k, 'item': iid, 'sid': sid, 'label': s['label'] or 'empty', 'fve': s['fve'],
                              'n': len(bl), 'L': c['layer'], 'source': it['source'], 'site_kind': c['site_kind'],
                              'samples': [b['sample_index'] for b in bl], 'text': s['text'] or ''}
        for j, b in enumerate(bl):
            text = sl(tb, b['start'], b['end'])
            scored = sl(tb, b['start'], b['scored_end'])
            st = toks(scored)
            head = st[:8]
            hits = sorted((max(a, b['start']), min(e, b['end'])) for a, e in wr if a < b['end'] and e > b['start'])
            # union of wrong intervals inside the bullet
            uni = []
            for a, e in hits:
                if uni and a <= uni[-1][1]:
                    uni[-1] = (uni[-1][0], max(uni[-1][1], e))
                else:
                    uni.append((a, e))
            blen = max(1, b['end'] - b['start'])
            slen = max(1, b['scored_end'] - b['start'])
            row = {'k': k, 'item': iid, 'ix': ITEM_IX[iid], 'sid': sid, 'L': c['layer'], 'source': it['source'],
                   'site_kind': c['site_kind'], 'j': j, 'n': len(bl), 'label': b['label'],
                   'readout': s['label'] or 'empty', 'fve': s['fve'], 'share': b['shap_share'], 'shap': b['shap'],
                   'solo': b['solo'], 'drop': b['drop'], 'coef': b['coef'], 'dup': b['dup'],
                   'truncated': b['truncated'], 'sample': b['sample_index'], 'text': text,
                   'scored_len': b['scored_end'] - b['start'], 'len': b['end'] - b['start'],
                   'n_tok_scored': len(st),
                   'cjk': cjk_frac(scored), 'lead_cjk': bool(st) and bool(CJK_CHAR.match(st[0])),
                   'nxt_ov': (sum(t in nset for t in head) / len(head)) if head else np.nan,
                   'prv_ov': (sum(t in pset for t in head) / len(head)) if head else np.nan,
                   'nxt_ov_all': (sum(t in nxt80 for t in st) / len(st)) if st else np.nan,
                   'first_eq': float(bool(head) and next_first is not None and head[0] == next_first),
                   'num_open_mismatch': float(bool(NUM_OPEN.match(scored)) and not next_is_num),
                   'fp_bullet': bool(FP.search(text)),
                   'b_novel_num': float(any(x not in ctx_nums for x in NUM.findall(scored))),
                   'b_novel_name': float(bool(novel_caps(scored, ctx_vocab))),
                   'n_true': cl_status[j]['true'], 'n_unver': cl_status[j]['unverifiable'],
                   'n_disp': cl_status[j]['disputed'], 'n_claims': sum(cl_status[j].values())}
            if uni:
                wtext = ' '.join(sl(tb, a, e) for a, e in uni)
                wchars = sum(e - a for a, e in uni)
                first = uni[0][0] - b['start']
                scored_w = sum(max(0, min(e, b['scored_end']) - a) for a, e in uni)
                if scored_w == 0:
                    loc = 'unscored'
                elif first / slen < 1 / 3:
                    loc = 'head'
                else:
                    loc = 'tail'
                sw = toks(wtext)
                row.update({'w_text': wtext, 'w_frac': wchars / blen, 'w_first_rel': first / slen, 'w_loc': loc,
                            'w_words': len(sw), 'w_digit': bool(NUM.search(wtext)),
                            'w_novel_num': any(x not in ctx_nums for x in NUM.findall(wtext)),
                            'w_novel_name': bool(novel_caps(wtext, ctx_vocab)),
                            'w_fp': bool(FP.search(wtext)), 'w_cjk': bool(CJK_CHAR.search(wtext)),
                            'w_novel_frac': (sum(t not in ctx_vocab for t in sw) / len(sw)) if sw else np.nan,
                            'w_scored_frac': scored_w / wchars})
            rows.append(row)

print('bullets', len(rows), 'readouts', len(readouts))


def wkind(r):
    if r.get('w_novel_num'):
        return 'novel_number'
    if r.get('w_novel_name'):
        return 'novel_capitalised_name'
    if r.get('w_fp'):
        return 'first_person'
    if r.get('w_words', 99) <= 4:
        return 'short_other(<=4 words)'
    return 'long_other'


WKINDS = ['novel_number', 'novel_capitalised_name', 'first_person', 'short_other(<=4 words)', 'long_other']
for r in rows:
    if r['label'] == 'w':
        r['wkind'] = wkind(r) if 'w_text' in r else 'no_span_text'

# position-adjusted scores (mid-rank percentile among labelled, non-dup bullets at the same position in readouts of
# the same size and setting); used for Original and Best of 32, whose order is the lens's writing order
LAB = [r for r in rows if r['label'] in ('w', 'c', 'o') and not r['dup'] and r['share'] is not None]
grp = collections.defaultdict(list)
for r in LAB:
    grp[(r['sid'], r['j'], r['n'])].append(r)
for g in grp.values():
    for sc in ('solo', 'share'):
        v = np.array([x[sc] for x in g], dtype=float)
        order = np.sort(v)
        lo = np.searchsorted(order, v, 'left')
        hi = np.searchsorted(order, v, 'right')
        pct = (lo + 0.5 * (hi - lo)) / len(v)
        for x, p in zip(g, pct):
            x[sc + '_pa'] = float(p)
by_ro = collections.defaultdict(list)
for r in LAB:
    by_ro[(r['k'], r['sid'])].append(r)

rng = np.random.default_rng(SEED)
BOOT = rng.integers(0, len(ITEM_IDS), size=(NREP, len(ITEM_IDS)))
BOOTW = np.stack([np.bincount(b, minlength=len(ITEM_IDS)) for b in BOOT]).astype(float)  # NREP x 149 weights


def ratio_ci(num, den):
    """num, den: per-item arrays. Ratio estimate with chat-level percentile bootstrap."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    est = num.sum() / den.sum() if den.sum() else float('nan')
    bn, bd = BOOTW @ num, BOOTW @ den
    with np.errstate(invalid='ignore', divide='ignore'):
        b = bn / bd
    b = b[np.isfinite(b)]
    return {'est': round(float(est), 4), 'lo': round(float(np.percentile(b, 2.5)), 4),
            'hi': round(float(np.percentile(b, 97.5)), 4), 'n': int(round(den.sum()))}


def diff_ci(num1, den1, num2, den2):
    num1, den1, num2, den2 = (np.asarray(x, float) for x in (num1, den1, num2, den2))
    est = num1.sum() / den1.sum() - num2.sum() / den2.sum()
    with np.errstate(invalid='ignore', divide='ignore'):
        b = (BOOTW @ num1) / (BOOTW @ den1) - (BOOTW @ num2) / (BOOTW @ den2)
    b = b[np.isfinite(b)]
    return {'est': round(float(est), 4), 'lo': round(float(np.percentile(b, 2.5)), 4),
            'hi': round(float(np.percentile(b, 97.5)), 4)}


def per_item(pairs):
    """pairs: iterable of (item_ix, num, den) -> per-item arrays."""
    num, den = np.zeros(len(ITEM_IDS)), np.zeros(len(ITEM_IDS))
    for ix, a, b in pairs:
        num[ix] += a
        den[ix] += b
    return num, den


def prop(rs, pred, cond=lambda r: True):
    num, den = per_item((r['ix'], float(pred(r)), 1.0) for r in rs if cond(r))
    return ratio_ci(num, den)


def win(a, b):
    return 1.0 if a > b else (0.5 if a == b else 0.0)


def label_pair_rate(sids, score, sel_w=lambda r: True, sel_c=lambda r: True, ro_sel=lambda ro: True,
                    wlab='w', clab='c'):
    """Same-readout rate P(score[clean] > score[wrong]) pooled over pairs; ties 1/2."""
    acc = []
    for (k, sid), bs in by_ro.items():
        if sid not in sids or not ro_sel(readouts[(k, sid)]):
            continue
        ws = [b for b in bs if b['label'] == wlab and sel_w(b)]
        cs = [b for b in bs if b['label'] == clab and sel_c(b)]
        for w in ws:
            for cc in cs:
                acc.append((w['ix'], win(cc[score], w[score]), 1.0))
    return ratio_ci(*per_item(acc))


def feat_pair_rate(sids, feat, score, sel=lambda r: True, labels=('w', 'c', 'o')):
    """Same-readout rate P(score[a] > score[b]) over pairs with feat[a] > feat[b]."""
    acc = []
    for (k, sid), bs in by_ro.items():
        if sid not in sids:
            continue
        bs = [b for b in bs if sel(b) and b['label'] in labels and not (isinstance(b[feat], float)
                                                                       and math.isnan(b[feat]))]
        for a in bs:
            for b in bs:
                if a is not b and a[feat] > b[feat]:
                    acc.append((a['ix'], win(a[score], b[score]), 1.0))
    return ratio_ci(*per_item(acc))


OB = ['capped_n1-n1', 'best_n_exact-n32']
CB = ['pooled_greedy_swap-n32']
out = {'meta': {'n_items': len(ITEM_IDS), 'n_cells': len(cells), 'n_bullets': len(rows), 'bootstrap': {
    'unit': 'chat (item)', 'n_groups': len(ITEM_IDS), 'reps': NREP, 'seed': SEED, 'interval': 'percentile 2.5-97.5'},
    'pair_rate': 'P(score of the first group > score of the second) over same-readout pairs, ties 1/2; 0.5 = no '
                 'separation. Label rates: P(clean > wrong). Feature rates: P(higher-feature bullet has higher '
                 'score). *_pa = position-adjusted percentile (Original, Best of 32 only).',
    'proxies': {'nxt_ov': 'share of the bullet\'s first 8 word tokens (Latin words or single CJK chars, lower-cased)'
                          ' found among the reply\'s next 40 tokens after the READ marker',
                'prv_ov': 'same against the reply\'s 40 tokens before the marker',
                'first_eq': 'bullet\'s first token == reply\'s next token',
                'cjk': 'fraction of CJK characters in the scored (first-32-token) part',
                'num_open_mismatch': 'bullet opens with a list number but the reply\'s next text does not',
                'w_loc': 'where the first verified-wrong character sits: head = first third of the scored part, '
                         'tail = later in the scored part, unscored = all wrong text past the 32-token limit',
                'wkind': 'wrong-span proxy kind, first match of: novel number (digits absent from prompt+reply), '
                         'novel capitalised non-initial word, first-person pronoun, <= 4 word tokens, else long'}}}

# ----------------------------------------------------------------------------- T1 no separation anywhere
t1 = {}
for sid in SIDS:
    sc = 'solo_pa' if sid in OB else 'solo'
    sh = 'share_pa' if sid in OB else 'share'
    t1[SHORT[sid]] = {
        'solo_all_wrong': label_pair_rate([sid], sc),
        'share_all_wrong': label_pair_rate([sid], sh),
        'solo_by_error_location': {loc: label_pair_rate([sid], sc, sel_w=lambda r, loc=loc: r.get('w_loc') == loc)
                                   for loc in ('head', 'tail', 'unscored')},
        'solo_by_wrong_span_words': {
            '<=3 words': label_pair_rate([sid], sc, sel_w=lambda r: r.get('w_words', 0) <= 3),
            '4-10 words': label_pair_rate([sid], sc, sel_w=lambda r: 4 <= r.get('w_words', 0) <= 10),
            '>10 words': label_pair_rate([sid], sc, sel_w=lambda r: r.get('w_words', 0) > 10)},
        'solo_by_wrong_frac': {
            'wrong covers <25% of bullet': label_pair_rate([sid], sc, sel_w=lambda r: r.get('w_frac', 0) < .25),
            'wrong covers >=60% of bullet': label_pair_rate([sid], sc, sel_w=lambda r: r.get('w_frac', 0) >= .6)},
        'solo_by_layer': {L: label_pair_rate([sid], sc, ro_sel=lambda ro, L=L: ro['L'] == L)
                          for L in (20, 36, 44, 52, 60)},
        'solo_by_source': {s: label_pair_rate([sid], sc, ro_sel=lambda ro, s=s: ro['source'] == s)
                           for s in ('dailydialog', 'lmsys')},
        'solo_by_site_kind': {s: label_pair_rate([sid], sc, ro_sel=lambda ro, s=s: ro['site_kind'] == s)
                              for s in ('clause', 'sentence', 'markup', 'newline', 'quote')},
    }
    # by readout joint-FVE tertile (tertiles of mixed readouts of this setting)
    mixed = [ro for (k, s2), ro in readouts.items() if s2 == sid and ro['label'] == 'hallucinated'
             and any(b['label'] == 'c' for b in by_ro.get((k, s2), []))]
    q = np.quantile([ro['fve'] for ro in mixed], [1 / 3, 2 / 3])
    t1[SHORT[sid]]['solo_by_readout_fve_tertile'] = {
        f'low (<{q[0]:.3f})': label_pair_rate([sid], sc, ro_sel=lambda ro: ro['fve'] < q[0]),
        'mid': label_pair_rate([sid], sc, ro_sel=lambda ro: q[0] <= ro['fve'] < q[1]),
        f'high (>={q[1]:.3f})': label_pair_rate([sid], sc, ro_sel=lambda ro: ro['fve'] >= q[1])}
out['T1_no_separation_pair_rates'] = t1
out['T1_wrong_location_counts'] = {SHORT[sid]: dict(collections.Counter(
    r.get('w_loc', 'no_span_text') for r in rows if r['sid'] == sid and r['label'] == 'w')) for sid in SIDS}

# ----------------------------------------------------------------------------- T2 frame/slot: what wrong bullets look like
t2 = {}
for sid in SIDS:
    W = [r for r in rows if r['sid'] == sid and r['label'] == 'w' and 'w_text' in r]
    t2[SHORT[sid]] = {
        'median_wrong_frac_of_bullet': round(float(np.median([r['w_frac'] for r in W])), 3),
        'p_wrong_frac_lt_0.33': prop(W, lambda r: r['w_frac'] < 1 / 3),
        'median_wrong_span_words': float(np.median([r['w_words'] for r in W])),
        'p_wrong_starts_after_first_third_of_scored': prop(W, lambda r: r['w_first_rel'] >= 1 / 3),
        'wkind_distribution': {kd: prop(W, lambda r, kd=kd: r['wkind'] == kd) for kd in WKINDS},
        # same-readout: is the wrong bullet's opening as close to the next text as the clean bullets' openings?
        'pair_rate_nxt_ov_clean_gt_wrong': label_pair_rate([sid], 'nxt_ov'),
        'pair_rate_prv_ov_clean_gt_wrong': label_pair_rate([sid], 'prv_ov'),
        'pair_rate_len_clean_gt_wrong': label_pair_rate([sid], 'len'),
    }
    # slot-like errors in the top vs bottom share quintile of wrong bullets
    Wq = [r for r in W if r['share'] is not None and not r['dup']]
    q20, q80 = np.quantile([r['share'] for r in Wq], [.2, .8])
    top = [r for r in Wq if r['share'] >= q80]
    bot = [r for r in Wq if r['share'] <= q20]
    slot = lambda r: r['wkind'] in ('novel_number', 'novel_capitalised_name', 'short_other(<=4 words)')
    nt, dt = per_item((r['ix'], float(slot(r)), 1.) for r in top)
    nb, db = per_item((r['ix'], float(slot(r)), 1.) for r in bot)
    t2[SHORT[sid]]['slot_like_top_share_quintile'] = ratio_ci(nt, dt)
    t2[SHORT[sid]]['slot_like_bottom_share_quintile'] = ratio_ci(nb, db)
    t2[SHORT[sid]]['slot_like_top_minus_bottom'] = diff_ci(nt, dt, nb, db)
    nt, dt = per_item((r['ix'], r['w_frac'], 1.) for r in top)
    nb, db = per_item((r['ix'], r['w_frac'], 1.) for r in bot)
    t2[SHORT[sid]]['mean_wrong_frac_top_minus_bottom'] = diff_ci(nt, dt, nb, db)
    t2[SHORT[sid]]['mean_wrong_frac_top'] = ratio_ci(nt, dt)
    t2[SHORT[sid]]['mean_wrong_frac_bottom'] = ratio_ci(nb, db)
out['T2_wrong_bullet_shape'] = t2

# ----------------------------------------------------------------------------- T3 what FVE tracks inside a readout
FEATS = ['nxt_ov', 'prv_ov', 'first_eq', 'len', 'cjk', 'num_open_mismatch', 'is_w', 'is_o']
for r in LAB:
    r['is_w'] = float(r['label'] == 'w')
    r['is_o'] = float(r['label'] == 'o')
    r['neg_cjk'] = -r['cjk']
    r['neg_num_open'] = -r['num_open_mismatch']
t3 = {}
for sid in SIDS:
    sc = 'solo'
    t3[SHORT[sid]] = {'pair_rates_solo': {
        'longer bullet (scored+tail chars) scores higher': feat_pair_rate([sid], 'len', sc),
        'higher next-text head overlap scores higher': feat_pair_rate([sid], 'nxt_ov', sc),
        'higher previous-text head overlap scores higher': feat_pair_rate([sid], 'prv_ov', sc),
        'first token = reply next token scores higher': feat_pair_rate([sid], 'first_eq', sc),
        'less CJK in scored part scores higher': feat_pair_rate([sid], 'neg_cjk', sc),
        'no mismatched list-number opener scores higher': feat_pair_rate([sid], 'neg_num_open', sc),
        'clean scores higher than wrong (raw, for comparison)': label_pair_rate([sid], sc),
    }}
    if sid in OB:
        t3[SHORT[sid]]['pair_rates_solo']['clean scores higher than wrong (position-adjusted)'] = \
            label_pair_rate([sid], 'solo_pa')
        t3[SHORT[sid]]['pair_rates_solo']['later position scores higher'] = feat_pair_rate([sid], 'j', sc)


def within_reg(sid, y='solo'):
    R = [r for r in LAB if r['sid'] == sid and not any(isinstance(r[f], float) and math.isnan(r[f])
                                                         for f in ['nxt_ov', 'prv_ov'])]
    names = ['is_w', 'is_o', 'log_len', 'cjk', 'nxt_ov', 'prv_ov', 'first_eq', 'num_open_mismatch']
    if sid in OB:
        names += ['pos2', 'pos3', 'pos4']
    X = []
    for r in R:
        v = [r['is_w'], r['is_o'], math.log(max(1, r['len'])), r['cjk'], r['nxt_ov'], r['prv_ov'], r['first_eq'],
             r['num_open_mismatch']]
        if sid in OB:
            v += [float(r['j'] == 1), float(r['j'] == 2), float(r['j'] == 3)]
        X.append(v)
    X, Y = np.array(X), np.array([r[y] for r in R])
    keys = [(r['k'], r['sid']) for r in R]
    # demean within readout
    idx = collections.defaultdict(list)
    for i, kk in enumerate(keys):
        idx[kk].append(i)
    Xd, Yd = X.copy(), Y.copy()
    for ii in idx.values():
        Xd[ii] -= X[ii].mean(0)
        Yd[ii] -= Y[ii].mean()
    sd = Xd.std(0)
    cont = {'log_len', 'cjk', 'nxt_ov', 'prv_ov'}
    scale = np.array([sd[i] if n in cont else 1.0 for i, n in enumerate(names)])
    Xs = Xd / scale
    ixs = np.array([r['ix'] for r in R])

    def fit(w):
        ww = w[ixs]
        A = Xs.T @ (Xs * ww[:, None])
        bvec = Xs.T @ (Yd * ww)
        return np.linalg.solve(A, bvec)

    est = fit(np.ones(len(ITEM_IDS)))
    boots = np.array([fit(w) for w in BOOTW])
    resid = Yd - Xs @ est
    r2 = 1 - (resid ** 2).sum() / (Yd ** 2).sum()
    res = {'n_bullets': len(R), 'within_readout_R2': round(float(r2), 4),
           'within_readout_sd_of_y': round(float(Yd.std()), 4),
           'units': 'coefficient = change in solo FVE (same readout) per 1 within-readout SD for continuous '
                    'features (log_len, cjk, nxt_ov, prv_ov) and per 0->1 for binary ones',
           'coef': {n: {'est': round(float(est[i]), 4), 'lo': round(float(np.percentile(boots[:, i], 2.5)), 4),
                        'hi': round(float(np.percentile(boots[:, i], 97.5)), 4)} for i, n in enumerate(names)}}
    # R2 drop when removing each feature (point estimate)
    drops = {}
    for i, n in enumerate(names):
        keep = [x for x in range(len(names)) if x != i]
        Xk = Xs[:, keep]
        bk = np.linalg.lstsq(Xk, Yd, rcond=None)[0]
        rk = Yd - Xk @ bk
        drops[n] = round(float(r2 - (1 - (rk ** 2).sum() / (Yd ** 2).sum())), 4)
    res['R2_lost_without_feature'] = drops
    Xl = Xs[:, :2]
    bl_ = np.linalg.lstsq(Xl, Yd, rcond=None)[0]
    rl = Yd - Xl @ bl_
    res['within_readout_R2_label_only'] = round(float(1 - (rl ** 2).sum() / (Yd ** 2).sum()), 4)
    return res


for r in LAB:
    r['nocjk_vs_heavy'] = 1.0 if r['cjk'] == 0 else (0.0 if r['cjk'] >= .5 else np.nan)
    r['nocjk_vs_lead'] = 1.0 if r['cjk'] == 0 else (0.0 if (r['lead_cjk'] and r['cjk'] < .2) else np.nan)
for sid in SIDS:
    t3[SHORT[sid]]['within_readout_regression_solo'] = within_reg(sid)
    pr = t3[SHORT[sid]]['pair_rates_solo']
    pr['no-CJK bullet beats mostly-CJK (>=50% CJK) bullet'] = feat_pair_rate([sid], 'nocjk_vs_heavy', 'solo')
    pr['no-CJK bullet beats bullet with only a CJK lead word (<20% CJK)'] = feat_pair_rate([sid], 'nocjk_vs_lead', 'solo')


# wrong bullets split by where the error sits and how much of the bullet it covers, controlling for length,
# script, next/previous-text overlap, list-number opener and (Original/Best) position
def within_reg_split(sid, y='solo'):
    R = [r for r in LAB if r['sid'] == sid and not math.isnan(r['nxt_ov']) and not math.isnan(r['prv_ov'])
         and (r['label'] != 'w' or 'w_text' in r)]
    names = ['w_head', 'w_tail_or_unscored', 'w_cover_ge60', 'is_o', 'log_len', 'cjk', 'nxt_ov', 'prv_ov',
             'first_eq', 'num_open_mismatch']
    if sid in OB:
        names += ['pos2', 'pos3', 'pos4']

    def vec(r):
        w = r['label'] == 'w'
        v = [float(w and r['w_loc'] == 'head'), float(w and r['w_loc'] != 'head'),
             float(w and r['w_frac'] >= .6), r['is_o'], math.log(max(1, r['len'])), r['cjk'], r['nxt_ov'],
             r['prv_ov'], r['first_eq'], r['num_open_mismatch']]
        if sid in OB:
            v += [float(r['j'] == 1), float(r['j'] == 2), float(r['j'] == 3)]
        return v

    X, Y = np.array([vec(r) for r in R]), np.array([r[y] for r in R])
    idx = collections.defaultdict(list)
    for i, r in enumerate(R):
        idx[(r['k'], r['sid'])].append(i)
    Xd, Yd = X.copy(), Y.copy()
    for ii in idx.values():
        Xd[ii] -= X[ii].mean(0)
        Yd[ii] -= Y[ii].mean()
    sd = Xd.std(0)
    cont = {'log_len', 'cjk', 'nxt_ov', 'prv_ov'}
    Xs = Xd / np.array([sd[i] if n in cont else 1.0 for i, n in enumerate(names)])
    ixs = np.array([r['ix'] for r in R])

    def fit(w):
        ww = w[ixs]
        return np.linalg.solve(Xs.T @ (Xs * ww[:, None]), Xs.T @ (Yd * ww))

    est = fit(np.ones(len(ITEM_IDS)))
    boots = np.array([fit(w) for w in BOOTW])
    hd = boots[:, 0] - boots[:, 1]
    return {'n_bullets': len(R), 'within_readout_sd_of_y': round(float(Yd.std()), 4),
            'note': 'w_head / w_tail_or_unscored: wrong bullet whose first wrong character is in / after the first '
                    'third of the scored text (reference = clean); w_cover_ge60: extra term when the wrong spans '
                    'cover >= 60% of the bullet',
            'coef': {n: {'est': round(float(est[i]), 4), 'lo': round(float(np.percentile(boots[:, i], 2.5)), 4),
                         'hi': round(float(np.percentile(boots[:, i], 97.5)), 4)} for i, n in enumerate(names[:4])},
            'head_minus_tail': {'est': round(float(est[0] - est[1]), 4),
                                'lo': round(float(np.percentile(hd, 2.5)), 4),
                                'hi': round(float(np.percentile(hd, 97.5)), 4)}}


for sid in SIDS:
    t3[SHORT[sid]]['regression_wrong_split_solo'] = within_reg_split(sid)


# frame sharing: are wrong bullets' openings as similar to their clean siblings as clean siblings are to each other?
def jacc(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else np.nan


heads = {}
for r in LAB:
    heads[(r['k'], r['sid'], r['j'])] = toks(r['text'])[:8]
fr = {}
for sid in SIDS:
    acc = {('w', 'c'): [], ('c', 'c'): [], ('o', 'c'): []}
    for (k, s2), bs in by_ro.items():
        if s2 != sid:
            continue
        cs = [b for b in bs if b['label'] == 'c']
        for a in bs:
            for cc in cs:
                if a is cc or (a['label'] == 'c' and a['j'] > cc['j']):
                    continue
                key = (a['label'], 'c')
                if key in acc:
                    v = jacc(heads[(k, sid, a['j'])], heads[(k, sid, cc['j'])])
                    if not math.isnan(v):
                        acc[key].append((a['ix'], v, 1.))
    pi = {kk: per_item(v) for kk, v in acc.items()}
    fr[SHORT[sid]] = {'mean_head_jaccard_wrong_vs_clean_sibling': ratio_ci(*pi[('w', 'c')]),
                      'mean_head_jaccard_clean_vs_clean_sibling': ratio_ci(*pi[('c', 'c')]),
                      'mean_head_jaccard_offtopic_vs_clean_sibling': ratio_ci(*pi[('o', 'c')]),
                      'wrong_minus_clean': diff_ci(*pi[('w', 'c')], *pi[('c', 'c')]),
                      'offtopic_minus_clean': diff_ci(*pi[('o', 'c')], *pi[('c', 'c')])}
t3['frame_sharing_head_jaccard'] = fr
out['T3_what_fve_tracks'] = t3

# ----------------------------------------------------------------------------- T4 redundancy (coef 0)
t4 = {}
for sid in OB:
    R = [r for r in LAB if r['sid'] == sid]
    t4[SHORT[sid]] = {
        'p_coef0_wrong': prop(R, lambda r: r['coef'] == 0, lambda r: r['label'] == 'w'),
        'p_coef0_clean': prop(R, lambda r: r['coef'] == 0, lambda r: r['label'] == 'c'),
        'p_coef0_clean_in_hallucinated': prop(R, lambda r: r['coef'] == 0,
                                              lambda r: r['label'] == 'c' and r['readout'] == 'hallucinated'),
        'p_coef0_among_lowest_share_bullet_of_readout': None,
        'p_coef0_among_bottom20pct_share': prop(R, lambda r: r['coef'] == 0, lambda r: r['share'] <= np.quantile(
            [x['share'] for x in R], .2)),
    }
    lows = []
    for (k, s2), bs in by_ro.items():
        if s2 != sid or len(bs) < 2:
            continue
        lo = min(bs, key=lambda b: b['share'])
        lows.append(lo)
    t4[SHORT[sid]]['p_coef0_among_lowest_share_bullet_of_readout'] = prop(lows, lambda r: r['coef'] == 0)
    t4[SHORT[sid]]['p_wrong_among_lowest_share_bullet_in_mixed_readouts'] = prop(
        [lo for lo in lows if any(b['label'] == 'w' for b in by_ro[(lo['k'], sid)])
         and any(b['label'] == 'c' for b in by_ro[(lo['k'], sid)])], lambda r: r['label'] == 'w')
    # expected under chance in those readouts = mean fraction of wrong bullets among w+c bullets
    fr = []
    for (k, s2), bs in by_ro.items():
        if s2 != sid:
            continue
        nw, nc = sum(b['label'] == 'w' for b in bs), sum(b['label'] == 'c' for b in bs)
        if nw and nc:
            fr.append((ITEM_IX[readouts[(k, s2)]['item']], nw / (nw + nc + sum(b['label'] == 'o' for b in bs)), 1.))
    t4[SHORT[sid]]['chance_p_wrong_lowest'] = ratio_ci(*per_item(fr))
    # wrong vs clean, within readout, restricted to bullets with coef > 0 (non-redundant)
    t4[SHORT[sid]]['pair_rate_solo_pa_nonredundant_only'] = label_pair_rate(
        [sid], 'solo_pa', sel_w=lambda r: r['coef'] > 0, sel_c=lambda r: r['coef'] > 0)
    t4[SHORT[sid]]['pair_rate_drop_nonredundant_only'] = label_pair_rate(
        [sid], 'drop', sel_w=lambda r: r['coef'] > 0, sel_c=lambda r: r['coef'] > 0)
out['T4_redundancy'] = t4

# ----------------------------------------------------------------------------- T5 32-token limit
t5 = {}
for sid in SIDS:
    W = [r for r in rows if r['sid'] == sid and r['label'] == 'w']
    Wt = [r for r in W if 'w_text' in r]
    t5[SHORT[sid]] = {
        'n_wrong': len(W),
        'p_truncated_wrong': prop(W, lambda r: r['truncated']),
        'p_truncated_clean': prop([r for r in rows if r['sid'] == sid and r['label'] == 'c'], lambda r: r['truncated']),
        'p_all_wrong_text_unscored': prop(Wt, lambda r: r['w_scored_frac'] == 0),
        'p_some_wrong_text_unscored': prop(Wt, lambda r: r['w_scored_frac'] < 1),
        'p_majority_wrong_text_unscored': prop(Wt, lambda r: r['w_scored_frac'] < .5),
        'pair_rate_solo_excluding_wrong_with_any_unscored_text': label_pair_rate(
            [sid], 'solo_pa' if sid in OB else 'solo', sel_w=lambda r: r.get('w_scored_frac', 1) == 1),
    }
out['T5_token_limit'] = t5

# ----------------------------------------------------------------------------- T6 judge reliability
t6 = {}
# (a) Raw vs Original: identical readout text judged twice
acc_same, acc_lab = [], collections.Counter()
for k, (iid, c) in cells.items():
    a, b = c['settings']['capped_n1-n1'], c['settings'][RAW]
    if (a['text'] or '') != (b['text'] or ''):
        continue
    la, lb = a['label'] or 'empty', b['label'] or 'empty'
    acc_same.append((ITEM_IX[iid], float(la == lb), 1.))
    acc_lab[(la, lb)] += 1
t6['raw_vs_original_identical_text'] = {
    'n_cells': len(acc_same), 'label_agreement': ratio_ci(*per_item(acc_same)),
    'crosstab_original_x_raw': {f'{a} | {b}': n for (a, b), n in sorted(acc_lab.items(), key=lambda x: -x[1])}}
num_h = per_item((ITEM_IX[cells[k][0]], float((cells[k][1]['settings']['capped_n1-n1']['label'] == 'hallucinated')
                                               != (cells[k][1]['settings'][RAW]['label'] == 'hallucinated')), 1.)
                 for k in cells if (cells[k][1]['settings']['capped_n1-n1']['text'] or '') ==
                 (cells[k][1]['settings'][RAW]['text'] or ''))
t6['raw_vs_original_identical_text']['p_hallucinated_flag_differs'] = ratio_ci(*num_h)
# kappa for hallucinated vs not
pairs = [(cells[k][1]['settings']['capped_n1-n1']['label'] == 'hallucinated',
          cells[k][1]['settings'][RAW]['label'] == 'hallucinated') for k in cells
         if (cells[k][1]['settings']['capped_n1-n1']['text'] or '') == (cells[k][1]['settings'][RAW]['text'] or '')]
pa = np.mean([x == y for x, y in pairs])
p1, p2 = np.mean([x for x, _ in pairs]), np.mean([y for _, y in pairs])
pe = p1 * p2 + (1 - p1) * (1 - p2)
t6['raw_vs_original_identical_text']['kappa_hallucinated'] = round(float((pa - pe) / (1 - pe)), 4)
t6['raw_vs_original_identical_text']['note'] = ('byte-identical texts reuse one cached verdict, so this is NOT a '
                                                'test-retest; see raw_vs_original_whitespace_only')


# (a2) Raw vs Original whose texts differ ONLY in whitespace: two separate judge calls on the same content
def strip_ws_map(t):
    """UTF-16 offset -> index in the whitespace-stripped string."""
    m, k16, kk = {}, 0, 0
    for ch in t:
        m[k16] = kk
        k16 += 2 if ord(ch) > 0xFFFF else 1
        if not ch.isspace():
            kk += 1
    m[k16] = kk
    return m


def nows(t):
    return re.sub(r'\s+', '', t or '')


ws_ro, ws_ct, ws_bul, ws_bul_ct, ws_examples = [], collections.Counter(), [], collections.Counter(), []
for k, (iid, c) in cells.items():
    a, b = c['settings']['capped_n1-n1'], c['settings'][RAW]
    if (a['text'] or '') == (b['text'] or '') or nows(a['text']) != nows(b['text']):
        continue
    la, lb = a['label'] or 'empty', b['label'] or 'empty'
    ws_ro.append((ITEM_IX[iid], float((la == 'hallucinated') == (lb == 'hallucinated')), 1.))
    ws_ct[(la, lb)] += 1
    if la != lb and len(ws_examples) < 20:
        ws_examples.append(k)
    ma, mb = strip_ws_map(a['text']), strip_ws_map(b['text'])
    rw = [(mb[x], mb[y]) for sp in b['spans'] if sp['verified'] and sp['type'] == 'wrong'
          for x, y in sp['offsets'] if x in mb and y in mb]
    for bb in a['bullets']:
        if bb['label'] not in ('w', 'c', 'o'):
            continue
        s0, e0 = ma.get(bb['start']), ma.get(bb['end'])
        if s0 is None or e0 is None:
            continue
        raw_w = any(x < e0 and y > s0 for x, y in rw)
        orig_w = bb['label'] == 'w'
        ws_bul_ct[(orig_w, raw_w)] += 1
        if orig_w or raw_w:
            ws_bul.append((ITEM_IX[iid], float(orig_w == raw_w), 1.))
t6['raw_vs_original_whitespace_only'] = {
    'n_cells': len(ws_ro), 'p_hallucinated_flag_same': ratio_ci(*per_item(ws_ro)),
    'crosstab_original_x_raw': {f'{x} | {y}': n for (x, y), n in sorted(ws_ct.items(), key=lambda z: -z[1])},
    'bullet_wrong_status_same_given_wrong_in_either': ratio_ci(*per_item(ws_bul)),
    'bullet_crosstab_(orig_wrong,raw_wrong)': {f'{x},{y}': n for (x, y), n in ws_bul_ct.items()},
    'examples_label_differs': ws_examples}


# (b) identical bullet text inside different readouts of the same cell
def norm_b(t):
    return re.sub(r'\s+', ' ', t).strip()


same_lab, conf = [], collections.Counter()
wc_flip = []
stable = {}   # (k, sid, j) -> 'stable'/'unstable' for bullets with an identical twin in another setting
for k, (iid, c) in cells.items():
    seen = collections.defaultdict(list)
    for sid in SIDS:
        s = c['settings'][sid]
        tb = u16(s['text'] or '')
        for j, b in enumerate(s['bullets']):
            if b['label'] not in ('w', 'c', 'o'):
                continue
            seen[norm_b(sl(tb, b['start'], b['end']))].append((sid, j, b['label']))
    for t, lst in seen.items():
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                (s1, j1, l1), (s2, j2, l2) = lst[x], lst[y]
                if s1 == s2:
                    continue
                if (c['settings'][s1]['text'] or '') == (c['settings'][s2]['text'] or ''):
                    continue  # whole readout identical: verdict reused, not a re-judgement
                same_lab.append((ITEM_IX[iid], float(l1 == l2), 1.))
                conf[tuple(sorted((l1, l2)))] += 1
                if 'w' in (l1, l2):
                    wc_flip.append((ITEM_IX[iid], float(l1 != l2), 1.))
                for (ss, jj, ll), other in (((s1, j1, l1), l2), ((s2, j2, l2), l1)):
                    stable.setdefault((k, ss, jj), []).append(ll == other)
t6['identical_bullet_text_across_settings'] = {
    'n_pairs': len(same_lab), 'label_agreement': ratio_ci(*per_item(same_lab)),
    'p_other_label_given_one_wrong': ratio_ci(*per_item(wc_flip)),
    'label_pairs': {f'{a}/{b}': n for (a, b), n in sorted(conf.items(), key=lambda x: -x[1])}}


# (c) wrong spans that were NOT counted: try to locate them with a normalised match
def norm_map(t):
    keep, idx = [], []
    for i, ch in enumerate(t):
        if ch.isspace() or ch in '*_`#>|-–—"“”\'‘’()（）[]【】' or CJK_CHAR.match(ch):
            continue
        keep.append(ch.lower())
        idx.append(i)
    return ''.join(keep), idx


recovered = collections.Counter()
rec_bul = {}   # (k, sid, j) -> True for clean bullets that hold a recovered wrong span
rec_examples = []
for k, (iid, c) in cells.items():
    for sid in SIDS:
        s = c['settings'][sid]
        text = s['text'] or ''
        bl = s['bullets']
        if not bl:
            continue
        t16 = u16(text)
        for sp in s['spans']:
            if sp['verified'] or sp['type'] != 'wrong':
                continue
            recovered[(sid, 'unverified_wrong')] += 1
            hit_j = set()
            if sp['offsets']:      # shorter than 3 characters: offsets exist
                recovered[(sid, 'short_span')] += 1
                for a, e in sp['offsets']:
                    hit_j |= {j for j, b in enumerate(bl) if a < b['end'] and e > b['start']}
            else:
                ns, _ = norm_map(sp['text'])
                if len(ns) < 6:
                    recovered[(sid, 'not_found_too_short_to_match')] += 1
                    continue
                for j, b in enumerate(bl):
                    nb, _ = norm_map(sl(t16, b['start'], b['end']))
                    m = difflib.SequenceMatcher(None, ns, nb, autojunk=False).find_longest_match(0, len(ns), 0, len(nb))
                    if m.size >= max(6, 0.8 * len(ns)):
                        hit_j.add(j)
                recovered[(sid, 'not_found_recovered' if hit_j else 'not_found_unrecovered')] += 1
            for j in hit_j:
                if bl[j]['label'] == 'c':
                    rec_bul[(k, sid, j)] = True
                    if len(rec_examples) < 400:
                        rec_examples.append({'k': k, 'setting': SHORT[sid], 'bullet': j, 'span': sp['text'],
                                             'why': sp.get('why')})
t6['unverified_wrong_spans'] = {SHORT[sid]: {kk: v for (s2, kk), v in recovered.items() if s2 == sid}
                                for sid in SIDS}
flip_ro = collections.Counter()
for (k, sid, j) in rec_bul:
    flip_ro[(sid, readouts[(k, sid)]['label'])] += 1
t6['clean_bullets_holding_an_uncounted_wrong_span'] = {
    SHORT[sid]: {'n_bullets': sum(1 for (k, s2, j) in rec_bul if s2 == sid),
                 'of_clean_bullets': sum(1 for r in rows if r['sid'] == sid and r['label'] == 'c'),
                 'readouts_currently_consistent_that_would_flip': len({k for (k, s2, j) in rec_bul if s2 == sid
                                                                       and readouts[(k, s2)]['label'] == 'consistent'})}
    for sid in SIDS}
for r in LAB:
    r['label_fix'] = 'w' if rec_bul.get((r['k'], r['sid'], r['j'])) else r['label']
    st = stable.get((r['k'], r['sid'], r['j']))
    r['stable'] = (st is not None and all(st))
    r['has_twin'] = st is not None
t6['pair_rate_after_relabelling_uncounted_spans'] = {}
t6['pair_rate_stable_labels_only'] = {}
t6['pair_rate_replicated_wrong_vs_any_clean'] = {}
t6['pair_rate_any_wrong_vs_replicated_clean'] = {}
t6['pair_rate_twins_only_baseline'] = {}
t6['twin_note'] = ('Only bullets that also occur, with identical text, in another setting\'s (different) readout of '
                   'the same cell. replicated = every twin got the same label. Baseline = all twin-holding wrong vs '
                   'all twin-holding clean bullets. If label noise hid an FVE signal, the replicated rows would '
                   'move away from the baseline toward > 0.5.')
for sid in SIDS:
    sc = 'solo_pa' if sid in OB else 'solo'
    # bullets with an identical twin in another setting are mostly ones Combine's greedy selector also picked, so
    # they are high-FVE by construction: compare only twin-holding bullets with each other
    t6['pair_rate_twins_only_baseline'][SHORT[sid]] = label_pair_rate(
        [sid], sc, sel_w=lambda r: r['has_twin'], sel_c=lambda r: r['has_twin'])
    t6['pair_rate_replicated_wrong_vs_any_clean'][SHORT[sid]] = label_pair_rate(
        [sid], sc, sel_w=lambda r: r['stable'], sel_c=lambda r: r['has_twin'])
    t6['pair_rate_any_wrong_vs_replicated_clean'][SHORT[sid]] = label_pair_rate(
        [sid], sc, sel_w=lambda r: r['has_twin'], sel_c=lambda r: r['stable'])
    acc, acc2 = [], []
    for (k, s2), bs in by_ro.items():
        if s2 != sid:
            continue
        ws = [b for b in bs if b['label_fix'] == 'w']
        cs = [b for b in bs if b['label_fix'] == 'c']
        acc += [(w['ix'], win(cc[sc], w[sc]), 1.) for w in ws for cc in cs]
        ws2 = [b for b in bs if b['label'] == 'w' and b['stable']]
        cs2 = [b for b in bs if b['label'] == 'c' and b['stable']]
        acc2 += [(w['ix'], win(cc[sc], w[sc]), 1.) for w in ws2 for cc in cs2]
    t6['pair_rate_after_relabelling_uncounted_spans'][SHORT[sid]] = ratio_ci(*per_item(acc))
    t6['pair_rate_stable_labels_only'][SHORT[sid]] = ratio_ci(*per_item(acc2))
t6['recovered_span_examples_first10'] = rec_examples[:10]
# (d) wrong vs VERIFIED-true clean bullets (every stage-2 claim located in the bullet is 'true')
t6['verified_true_clean'] = {}
for sid in SIDS:
    sc = 'solo_pa' if sid in OB else 'solo'
    vt = lambda r: r['n_claims'] > 0 and r['n_true'] == r['n_claims']
    unv = lambda r: r['n_unver'] > 0 or r['n_disp'] > 0
    t6['verified_true_clean'][SHORT[sid]] = {
        'p_clean_bullets_verified_true': prop([r for r in rows if r['sid'] == sid and r['label'] == 'c'], vt),
        'pair_rate_wrong_vs_verified_true_clean': label_pair_rate([sid], sc, sel_c=vt),
        'pair_rate_wrong_vs_clean_with_unverifiable_or_disputed_claims': label_pair_rate([sid], sc, sel_c=unv),
        'pair_rate_wrong_with_extra_disputed_claim_vs_verified_true_clean': label_pair_rate(
            [sid], sc, sel_w=lambda r: r['n_disp'] > 0, sel_c=vt)}
out['T6_judge_reliability'] = t6

# ----------------------------------------------------------------------------- T7 settings
t7 = {}
LBL = lambda x: x if x in ('consistent', 'hallucinated') else 'other'
for sid in ['best_n_exact-n32', 'pooled_greedy_swap-n32']:
    tr = collections.Counter()
    fix, brk, fixn, brkn = [], [], [], []
    for k, (iid, c) in cells.items():
        a, b = LBL(c['settings']['capped_n1-n1']['label']), LBL(c['settings'][sid]['label'])
        tr[(a, b)] += 1
        if a == 'hallucinated':
            fix.append((ITEM_IX[iid], float(b == 'consistent'), 1.))
        if a == 'consistent':
            brk.append((ITEM_IX[iid], float(b == 'hallucinated'), 1.))
    t7[SHORT[sid]] = {'transitions_from_original': {f'{a} -> {b}': n for (a, b), n in sorted(tr.items())},
                      'p_fix (orig hallucinated -> consistent)': ratio_ci(*per_item(fix)),
                      'p_break (orig consistent -> hallucinated)': ratio_ci(*per_item(brk)),
                      'n_fix': tr[('hallucinated', 'consistent')], 'n_break': tr[('consistent', 'hallucinated')]}
# Best of 32: does a larger FVE gain over the Original make a fix more / a break less likely?
gain_rows = []
for k, (iid, c) in cells.items():
    o, b = c['settings']['capped_n1-n1'], c['settings']['best_n_exact-n32']
    if (o['text'] or '') == (b['text'] or ''):
        continue
    gain_rows.append((ITEM_IX[iid], b['fve'] - o['fve'], LBL(o['label']), LBL(b['label'])))
g = np.array([x[1] for x in gain_rows])
qs = np.quantile(g, [1 / 3, 2 / 3])
bins = {}
for nm, lo, hi in [('low gain', -1, qs[0]), ('mid gain', qs[0], qs[1]), ('high gain', qs[1], 9)]:
    sel = [x for x in gain_rows if lo <= x[1] < hi]
    bins[f'{nm} [{lo:.3f},{hi:.3f})' if nm != 'low gain' else f'{nm} (<{hi:.3f})'] = {
        'p_fix': ratio_ci(*per_item((ix, float(bl == 'consistent'), 1.) for ix, _, ol, bl in sel if ol == 'hallucinated')),
        'p_break': ratio_ci(*per_item((ix, float(bl == 'hallucinated'), 1.) for ix, _, ol, bl in sel if ol == 'consistent')),
        'median_gain': round(float(np.median([x[1] for x in sel])), 4)}
t7['best_of_32_fix_break_by_fve_gain_tertile'] = {'n_cells_with_new_sample': len(gain_rows), 'bins': bins}
# Combine 32: wrong rate by greedy pick order and by leave-one-out drop
C = [r for r in LAB if r['sid'] == 'pooled_greedy_swap-n32']
t7['combine_p_wrong_by_pick_order'] = {f'pick {j + 1}': prop(C, lambda r: r['label'] == 'w', lambda r, j=j: r['j'] == j)
                                      for j in range(4)}
dq = np.quantile([r['drop'] for r in C], [.25, .5, .75])
t7['combine_p_wrong_by_drop_quartile'] = {
    f'Q1 drop<{dq[0]:.4f}': prop(C, lambda r: r['label'] == 'w', lambda r: r['drop'] < dq[0]),
    'Q2': prop(C, lambda r: r['label'] == 'w', lambda r: dq[0] <= r['drop'] < dq[1]),
    'Q3': prop(C, lambda r: r['label'] == 'w', lambda r: dq[1] <= r['drop'] < dq[2]),
    f'Q4 drop>={dq[2]:.4f}': prop(C, lambda r: r['label'] == 'w', lambda r: r['drop'] >= dq[2])}
for sid in OB:
    R = [r for r in LAB if r['sid'] == sid]
    t7[f'{SHORT[sid]}_p_wrong_by_position'] = {f'pos {j + 1}': prop(R, lambda r: r['label'] == 'w',
                                                                    lambda r, j=j: r['j'] == j and r['n'] == 4)
                                               for j in range(4)}
# Combine: hallucinated rate by number of distinct source samples
cmb = [(ITEM_IX[ro['item']], len(set(ro['samples'])), ro['label']) for (k, s2), ro in readouts.items()
       if s2 == 'pooled_greedy_swap-n32' and ro['n'] == 4]
t7['combine_p_hallucinated_by_n_distinct_samples'] = {
    str(n): ratio_ci(*per_item((ix, float(lb == 'hallucinated'), 1.) for ix, nn, lb in cmb if nn == n))
    for n in (3, 4)}
# kind of wrong span by setting
kd = {}
for sid in SIDS:
    W = [r for r in rows if r['sid'] == sid and r['label'] == 'w' and 'w_text' in r]
    kd[SHORT[sid]] = {x: prop(W, lambda r, x=x: r['wkind'] == x) for x in WKINDS}
    kd[SHORT[sid]]['any_first_person_in_span'] = prop(W, lambda r: r['w_fp'])
    kd[SHORT[sid]]['any_novel_number'] = prop(W, lambda r: r['w_novel_num'])
    kd[SHORT[sid]]['any_novel_name'] = prop(W, lambda r: r['w_novel_name'])
    kd[SHORT[sid]]['median_span_words'] = float(np.median([r['w_words'] for r in W]))
kd['differences_vs_Original'] = {}
for sid in SIDS[1:]:
    W0 = [r for r in rows if r['sid'] == 'capped_n1-n1' and r['label'] == 'w' and 'w_text' in r]
    W1 = [r for r in rows if r['sid'] == sid and r['label'] == 'w' and 'w_text' in r]
    kd['differences_vs_Original'][SHORT[sid]] = {}
    for x in WKINDS:
        n1, d1 = per_item((r['ix'], float(r['wkind'] == x), 1.) for r in W1)
        n0, d0 = per_item((r['ix'], float(r['wkind'] == x), 1.) for r in W0)
        kd['differences_vs_Original'][SHORT[sid]][x] = diff_ci(n1, d1, n0, d0)
t7['wrong_span_kind_by_setting'] = kd
out['T7_settings'] = t7

# ----------------------------------------------------------------------------- T8 error kinds and FVE; persona by source
t8 = {}
for sid in SIDS:
    sc = 'solo_pa' if sid in OB else 'solo'
    t8[SHORT[sid]] = {'pair_rate_by_wrong_kind': {x: label_pair_rate([sid], sc, sel_w=lambda r, x=x: r.get('wkind') == x)
                                                  for x in WKINDS}}
    W = [r for r in rows if r['sid'] == sid and r['label'] == 'w' and 'w_text' in r]
    t8[SHORT[sid]]['first_person_span_by_source'] = {
        s: prop(W, lambda r: r['w_fp'], lambda r, s=s: r['source'] == s) for s in ('dailydialog', 'lmsys')}
    t8[SHORT[sid]]['novel_number_or_name_by_source'] = {
        s: prop(W, lambda r: r['w_novel_num'] or r['w_novel_name'], lambda r, s=s: r['source'] == s)
        for s in ('dailydialog', 'lmsys')}
    O = [r for r in LAB if r['sid'] == sid]
    t8[SHORT[sid]]['mean_nxt_ov_by_label'] = {lab: prop(O, lambda r: r['nxt_ov'] if not math.isnan(r['nxt_ov']) else 0,
                                                        lambda r, lab=lab: r['label'] == lab and not math.isnan(r['nxt_ov']))
                                              for lab in ('c', 'w', 'o')}
    t8[SHORT[sid]]['offtopic_vs_clean_pair_rate'] = label_pair_rate([sid], sc, wlab='o')
out['T8_error_kinds'] = t8

# ----------------------------------------------------------------------------- T9 specificity: invented specifics
t9 = {}
for r in LAB:
    r['b_novel_spec'] = float(r['b_novel_num'] or r['b_novel_name'])
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid]
    t9[SHORT[sid]] = {
        'p_bullet_has_novel_number_or_name_(scored part)': prop(R, lambda r: r['b_novel_spec']),
        'p_wrong_given_novel_specific': prop(R, lambda r: r['label'] == 'w', lambda r: r['b_novel_spec'] == 1),
        'p_wrong_given_no_novel_specific': prop(R, lambda r: r['label'] == 'w', lambda r: r['b_novel_spec'] == 0),
        'pair_rate_solo_novel_specific_beats_none_all_labels': feat_pair_rate([sid], 'b_novel_spec', 'solo'),
        'pair_rate_solo_novel_specific_beats_none_clean_only': feat_pair_rate([sid], 'b_novel_spec', 'solo',
                                                                             labels=('c',)),
        'pair_rate_solo_novel_specific_beats_none_wrong_only': feat_pair_rate([sid], 'b_novel_spec', 'solo',
                                                                             labels=('w',)),
    }
    if sid in OB:
        t9[SHORT[sid]]['pair_rate_solo_pa_novel_specific_beats_none_all_labels'] = feat_pair_rate(
            [sid], 'b_novel_spec', 'solo_pa')
for sid in SIDS[1:]:
    R0 = [r for r in LAB if r['sid'] == 'capped_n1-n1']
    R1 = [r for r in LAB if r['sid'] == sid]
    n1, d1 = per_item((r['ix'], r['b_novel_spec'], 1.) for r in R1)
    n0, d0 = per_item((r['ix'], r['b_novel_spec'], 1.) for r in R0)
    t9[f'{SHORT[sid]}_minus_Original_p_novel_specific'] = diff_ci(n1, d1, n0, d0)
out['T9_specificity'] = t9

# ----------------------------------------------------------------------------- write
with open(os.path.join(HERE, 'synth_tests.json'), 'w') as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False, default=lambda x: x if not isinstance(x, np.generic) else x.item())
tables['_quantitative_results_file'] = os.path.join(HERE, 'synth_tests.json')
with open(os.path.join(HERE, 'tables.json'), 'w') as fh:
    json.dump(tables, fh, indent=1, ensure_ascii=False)


# ----------------------------------------------------------------------------- tables.md
def md_ct(t, title, note=None, pct=False):
    L = [f'### {title}', '']
    if note:
        L += [note, '']
    cols = [c for c in t['cols'] if any(t['counts'][r][c] for r in t['rows'])]
    L.append('| | n | ' + ' | '.join(cols) + ' |')
    L.append('|---|---|' + '---|' * len(cols))
    for r in t['rows']:
        n = t['row_n'][r]
        cells_ = []
        for c in cols:
            v = t['counts'][r][c]
            cells_.append(f'{v}' + (f' ({100 * v / n:.0f}%)' if pct and n and v else ''))
        L.append(f'| {r} | {n} | ' + ' | '.join(cells_) + ' |')
    tot = {c: sum(t['counts'][r][c] for r in t['rows']) for c in cols}
    L.append(f'| **all** | {sum(t["row_n"].values())} | ' + ' | '.join(str(tot[c]) for c in cols) + ' |')
    return '\n'.join(L) + '\n'


def ci(x):
    return f"{x['est']:.3f} [{x['lo']:.3f}, {x['hi']:.3f}]"


md = ['# Bullet-FVE reading study: synthesis tables', '',
      'Exploratory. Part A tabulates the 288 reader records (24 batches x 12; stratified sample, not random). Part B '
      'summarises the all-data tests in synth_tests.json (67,317 bullets, 5,615 cells x 3 settings; intervals are '
      'chat-level percentile bootstrap, 149 chats, 1000 reps). Interactive page: '
      'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#<k>.', '',
      'Reader classes: error = invented_specific_detail, wrong_relation_or_attribute, persona_or_self_claim, '
      'misread_prompt_or_context; junk = off_topic_junk; vague = generic_or_vague; no_error = '
      'plausible_continuation_not_taken, judge_overstrict, not_wrong_clean.', '',
      '## Part A: reading records', '',
      md_ct(tables['blind_type_by_stratum'], 'A1. Reader blind_type by stratum', pct=True),
      md_ct(tables['blind_type_by_setting'], 'A2. Reader blind_type by setting (all strata)', pct=True),
      md_ct(tables['blind_type_by_setting_within_wrong_strata_ABF'],
            'A3. Reader blind_type by setting, wrong-bullet strata A, B, F only', pct=True),
      md_ct(tables['blind_type_by_source'], 'A4. Reader blind_type by source', pct=True),
      md_ct(tables['judge_agrees_by_stratum'], 'A5. Reader agrees with the judge, by stratum', pct=True),
      md_ct(tables['judge_agrees_by_setting'], 'A6. Reader agrees with the judge, by setting', pct=True),
      md_ct(tables['judge_label_vs_reader_class'], 'A7. Judge bullet label x reader verdict class', pct=True),
      md_ct(tables['disagreement_direction_by_stratum'], 'A8. Direction of reader-judge disagreement, by stratum',
            note='judge_too_strict = judge WRONG/OFF-TOPIC, reader sees no error; judge_missed_error = judge clean, '
                 'reader sees an error; boundary_* = both see a problem but disagree on wrong vs off-topic.',
            pct=True),
      md_ct(tables['disagreement_direction_by_setting'], 'A9. Direction of disagreement, by setting', pct=True),
      md_ct(tables['relation_codes_by_stratum'], 'A10. relation_to_context keyword codes by stratum',
            note='Heuristic regex codes on the readers\' free text; several codes can apply to one record. Patterns '
                 'are in synth_tests.py (REL_CODES).', pct=True),
      md_ct(tables['score_codes_by_stratum'], 'A11. score_reading keyword codes by stratum (reader\'s explanation '
            'of the FVE numbers)', note='Patterns in SCORE_CODES. error_invisible_to_score = the reader says the '
                                       'error costs nothing / is ignored / is unscored.', pct=True),
      md_ct(tables['note_codes_by_stratum'], 'A12. Judge/pipeline problems mentioned in note or score_reading',
            note='Patterns in NOTE_CODES.', pct=True),
      md_ct(tables['E_disagree_cause'], 'A13. E_disagree: why the settings disagree (hand-coded from the readers\' '
            '"all settings" notes)', note='judge_inconsistent = same or near-identical content judged differently; '
                                         'judge_overstrict = flagged span is a reasonable continuation the other '
                                         'settings lack; span_match = an uncounted span decides the label; '
                                         'sample_change_real = a different sample carries an error the reader accepts.',
            pct=True),
      md_ct(tables['E_disagree_real_change_kinds'], 'A14. E_disagree, sample_change_real only: reader blind_type'),
      '### A15. E_disagree cases', '', '| k | sub | cause | why | labels O/B/C |', '|---|---|---|---|---|']
for e in e_rows:
    md.append(f"| {e['k']} | {e['sub'][:2]} | {e['cause']} | {e['why']} | "
              f"{e['labels']['Original']}/{e['labels']['Best of 32']}/{e['labels']['Combine 32']} |")
md += ['', '### A16. Reading summary numbers', '']
md += [f'- {k}: {v}' for k, v in tables['reading_summary'].items()]
md += ['', '## Part B: all-data tests (details in synth_tests.json)', '',
       'Pair rate = P(clean bullet scores higher than a wrong bullet of the same readout), ties 1/2; 0.5 = no '
       'separation. Original and Best of 32 use position-adjusted percentiles; Combine 32 raw scores.', '',
       '| test | Original | Best of 32 | Combine 32 |', '|---|---|---|---|']


def row3(name, f):
    vals = []
    for s in ['Original', 'Best of 32', 'Combine 32']:
        try:
            vals.append(ci(f(s)))
        except Exception:
            vals.append('n/a')
    md.append(f'| {name} | ' + ' | '.join(vals) + ' |')


T1, T2_, T3_, T4_, T5_, T6_, T7_, T8_ = (out[x] for x in ['T1_no_separation_pair_rates', 'T2_wrong_bullet_shape',
                                                         'T3_what_fve_tracks', 'T4_redundancy', 'T5_token_limit',
                                                         'T6_judge_reliability', 'T7_settings', 'T8_error_kinds'])
row3('solo, all wrong vs clean', lambda s: T1[s]['solo_all_wrong'])
row3('solo, error in head (first third of scored text)', lambda s: T1[s]['solo_by_error_location']['head'])
row3('solo, error in tail of scored text', lambda s: T1[s]['solo_by_error_location']['tail'])
row3('solo, wrong span <= 3 words', lambda s: T1[s]['solo_by_wrong_span_words']['<=3 words'])
row3('solo, wrong span > 10 words', lambda s: T1[s]['solo_by_wrong_span_words']['>10 words'])
row3('solo, wrong covers >= 60% of bullet', lambda s: T1[s]['solo_by_wrong_frac']['wrong covers >=60% of bullet'])
row3('solo, top readout-FVE tertile', lambda s: [v for kk, v in T1[s]['solo_by_readout_fve_tertile'].items()
                                                 if kk.startswith('high')][0])
row3('solo, layer 20', lambda s: T1[s]['solo_by_layer'][20])
row3('solo, layer 60', lambda s: T1[s]['solo_by_layer'][60])
row3('solo, wrong span has a novel number', lambda s: T8_[s]['pair_rate_by_wrong_kind']['novel_number'])
row3('solo, wrong span has a novel capitalised name',
     lambda s: T8_[s]['pair_rate_by_wrong_kind']['novel_capitalised_name'])
row3('solo, OFF-TOPIC vs clean', lambda s: T8_[s]['offtopic_vs_clean_pair_rate'])
row3('solo, after relabelling uncounted wrong spans', lambda s: T6_['pair_rate_after_relabelling_uncounted_spans'][s])
row3('solo, twin-holding bullets only (baseline for the next two rows)',
     lambda s: T6_['pair_rate_twins_only_baseline'][s])
row3('solo, twin-holding: replicated WRONG vs clean', lambda s: T6_['pair_rate_replicated_wrong_vs_any_clean'][s])
row3('solo, twin-holding: wrong vs replicated CLEAN', lambda s: T6_['pair_rate_any_wrong_vs_replicated_clean'][s])
row3('solo, wrong vs VERIFIED-true clean (all stage-2 claims true)',
     lambda s: T6_['verified_true_clean'][s]['pair_rate_wrong_vs_verified_true_clean'])
row3('solo, wrong + extra disputed claim vs VERIFIED-true clean',
     lambda s: T6_['verified_true_clean'][s]['pair_rate_wrong_with_extra_disputed_claim_vs_verified_true_clean'])
row3('P(clean bullet is VERIFIED true)', lambda s: T6_['verified_true_clean'][s]['p_clean_bullets_verified_true'])
row3('solo, excluding wrong bullets with any unscored wrong text',
     lambda s: T5_[s]['pair_rate_solo_excluding_wrong_with_any_unscored_text'])
md += ['', '| what FVE tracks (same-readout pair rate on solo) | Original | Best of 32 | Combine 32 |',
       '|---|---|---|---|']
for nm in ['longer bullet (scored+tail chars) scores higher', 'later position scores higher',
           'higher next-text head overlap scores higher', 'first token = reply next token scores higher',
           'no mismatched list-number opener scores higher', 'no-CJK bullet beats mostly-CJK (>=50% CJK) bullet',
           'no-CJK bullet beats bullet with only a CJK lead word (<20% CJK)',
           'higher previous-text head overlap scores higher']:
    row3(nm, lambda s, nm=nm: T3_[s]['pair_rates_solo'][nm])
md += ['', '| within-readout regression of solo FVE | Original | Best of 32 | Combine 32 |', '|---|---|---|---|']
row3('coef is_w (wrong vs clean, solo units)', lambda s: T3_[s]['within_readout_regression_solo']['coef']['is_w'])
row3('coef is_o (off-topic vs clean)', lambda s: T3_[s]['within_readout_regression_solo']['coef']['is_o'])
row3('coef log_len (per SD)', lambda s: T3_[s]['within_readout_regression_solo']['coef']['log_len'])
row3('coef wrong, error in head', lambda s: T3_[s]['regression_wrong_split_solo']['coef']['w_head'])
row3('coef wrong, error in tail/unscored', lambda s: T3_[s]['regression_wrong_split_solo']['coef']['w_tail_or_unscored'])
row3('head minus tail', lambda s: T3_[s]['regression_wrong_split_solo']['head_minus_tail'])
md.append('| within-readout R2 (all features / label only) | ' + ' | '.join(
    f"{T3_[s]['within_readout_regression_solo']['within_readout_R2']} / "
    f"{T3_[s]['within_readout_regression_solo']['within_readout_R2_label_only']}"
    for s in ['Original', 'Best of 32', 'Combine 32']) + ' |')
md.append('| within-readout SD of solo | ' + ' | '.join(
    str(T3_[s]['within_readout_regression_solo']['within_readout_sd_of_y']) for s in ['Original', 'Best of 32', 'Combine 32']) + ' |')
md += ['', '| other | Original | Best of 32 | Combine 32 |', '|---|---|---|---|']
row3('P(coef 0 | wrong)', lambda s: T4_[s]['p_coef0_wrong'])
row3('P(coef 0 | clean)', lambda s: T4_[s]['p_coef0_clean'])
row3('P(coef 0 | lowest-share bullet of readout)', lambda s: T4_[s]['p_coef0_among_lowest_share_bullet_of_readout'])
row3('P(wrong | lowest-share bullet, mixed readouts)',
     lambda s: T4_[s]['p_wrong_among_lowest_share_bullet_in_mixed_readouts'])
row3('chance level for the line above', lambda s: T4_[s]['chance_p_wrong_lowest'])
row3('P(all wrong text past 32 tokens | wrong)', lambda s: T5_[s]['p_all_wrong_text_unscored'])
row3('P(some wrong text past 32 tokens | wrong)', lambda s: T5_[s]['p_some_wrong_text_unscored'])
row3('P(wrong span starts after first third of scored text)',
     lambda s: T2_[s]['p_wrong_starts_after_first_third_of_scored'])
row3('P(wrong spans cover < 1/3 of bullet)', lambda s: T2_[s]['p_wrong_frac_lt_0.33'])
row3('head Jaccard, wrong vs clean sibling', lambda s: T3_['frame_sharing_head_jaccard'][s]['mean_head_jaccard_wrong_vs_clean_sibling'])
row3('head Jaccard, clean vs clean sibling', lambda s: T3_['frame_sharing_head_jaccard'][s]['mean_head_jaccard_clean_vs_clean_sibling'])
row3('head Jaccard, off-topic vs clean sibling', lambda s: T3_['frame_sharing_head_jaccard'][s]['mean_head_jaccard_offtopic_vs_clean_sibling'])
for x in WKINDS:
    row3(f'wrong-span kind: {x}', lambda s, x=x: T7_['wrong_span_kind_by_setting'][s][x])
row3('first-person wrong span, dailydialog', lambda s: T8_[s]['first_person_span_by_source']['dailydialog'])
row3('first-person wrong span, lmsys', lambda s: T8_[s]['first_person_span_by_source']['lmsys'])
T9_ = out['T9_specificity']
row3('P(bullet scored part has a novel number or capitalised name)',
     lambda s: T9_[s]['p_bullet_has_novel_number_or_name_(scored part)'])
row3('P(wrong | bullet has novel specific)', lambda s: T9_[s]['p_wrong_given_novel_specific'])
row3('P(wrong | no novel specific)', lambda s: T9_[s]['p_wrong_given_no_novel_specific'])
row3('pair rate solo: novel-specific bullet beats one without (all labels)',
     lambda s: T9_[s]['pair_rate_solo_novel_specific_beats_none_all_labels'])
row3('same, clean bullets only', lambda s: T9_[s]['pair_rate_solo_novel_specific_beats_none_clean_only'])
row3('same, wrong bullets only', lambda s: T9_[s]['pair_rate_solo_novel_specific_beats_none_wrong_only'])
md.append('| P(novel specific) minus Original | n/a | ' + ci(T9_['Best of 32_minus_Original_p_novel_specific']) + ' | '
          + ci(T9_['Combine 32_minus_Original_p_novel_specific']) + ' |')
md += ['', '| judge reliability | value |', '|---|---|']
ws = T6_['raw_vs_original_whitespace_only']
md.append(f"| Original vs Raw, texts differ only in whitespace (n={ws['n_cells']} cells, separate judge calls): "
          f"P(same hallucinated flag) | {ci(ws['p_hallucinated_flag_same'])} |")
md.append(f"| same cells, bullet level: P(same wrong status given wrong in either) | "
          f"{ci(ws['bullet_wrong_status_same_given_wrong_in_either'])} |")
ib = T6_['identical_bullet_text_across_settings']
md.append(f"| identical bullet text in two different readouts of a cell (n={ib['n_pairs']} pairs): label agreement | "
          f"{ci(ib['label_agreement'])} |")
md.append(f"| same, P(labels differ given one is WRONG) | {ci(ib['p_other_label_given_one_wrong'])} |")
for s in ['Original', 'Best of 32', 'Combine 32']:
    cb = T6_['clean_bullets_holding_an_uncounted_wrong_span'][s]
    md.append(f"| {s}: clean bullets holding an uncounted (unverified) wrong span | {cb['n_bullets']} of "
              f"{cb['of_clean_bullets']}; consistent readouts that would flip: "
              f"{cb['readouts_currently_consistent_that_would_flip']} |")
md += ['', '| settings | Best of 32 | Combine 32 |', '|---|---|---|']
md.append('| P(fix): Original hallucinated -> consistent | ' + ' | '.join(
    ci(T7_[s]['p_fix (orig hallucinated -> consistent)']) for s in ['Best of 32', 'Combine 32']) + ' |')
md.append('| P(break): Original consistent -> hallucinated | ' + ' | '.join(
    ci(T7_[s]['p_break (orig consistent -> hallucinated)']) for s in ['Best of 32', 'Combine 32']) + ' |')
for nm, v in T7_['best_of_32_fix_break_by_fve_gain_tertile']['bins'].items():
    md.append(f"| Best of 32, {nm}: P(fix) / P(break) | {ci(v['p_fix'])} / {ci(v['p_break'])} | |")
for nm, v in T7_['combine_p_wrong_by_pick_order'].items():
    md.append(f'| Combine 32 P(wrong), {nm} | | {ci(v)} |')
with open(os.path.join(HERE, 'tables.md'), 'w') as fh:
    fh.write('\n'.join(md) + '\n')
print('wrote synth_tests.json, tables.json, tables.md')
