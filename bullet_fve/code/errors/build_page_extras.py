#!/usr/bin/env python
"""Build the page data for the "Reading study" and "Errors" sections and the case-view extras (exploratory).

Writes (all under page/data/):
  reading.json        both reading sets joined by k / setting / bullet:
                        strat = 288 stratified reading records (reading/records + reading/sample.json)
                        rep   = 240 representative wrong bullets (errors/errors_page.json rep_cases)
                      plus hand-written plain summaries of reading/REPORT.md (findings, numbers)
  errors.json         errors/errors_page.json without rep_cases (they live in reading.json), with file paths
                      removed, plus pilot_cells (class per fully judged cell) for the avoidability grid
  rec/<item>.json     per wrong span (k -> setting index -> rows): recurrence of the span's key words over the
                      cell's 32 lens samples (errors/recurrence.jsonl), plus the true value the judge's reason
                      points to and how many samples contain it (same rule as errors_synth.truth_tokens);
                      and, for the 72 fully judged pilot cells, the 32 samples' judge class + FVE + wrong spans.

Read-only inputs: reading/, errors/ (recurrence.jsonl, avoidability_cells.jsonl, pool_hall.json, errors_page.json),
page/data/items/*.json.  Run: PYTHONPATH=<olens-improve/src> <runtime python> -B errors/build_page_extras.py
"""
import collections
import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
DATA = f'{BASE}/page/data'
READ = f'{BASE}/reading'
sys.path.insert(0, HERE)
from recurrence import feats, match_feats  # noqa: E402
from errors_synth import truth_tokens  # noqa: E402

SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
SI = {s: i for i, s in enumerate(SIDS)}
T0 = time.time()


def log(*a):
    print(f'[{time.time() - T0:6.1f}s]', *a, flush=True)


def u16(text, s, e):
    return text.encode('utf-16-le')[2 * s:2 * e].decode('utf-16-le')


def u16len(text):
    return len(text.encode('utf-16-le')) // 2


PATH_RE = re.compile(r'(/orcd|/home/|/tmp/|\bsbatch\b|\bslurm\b|job ?id)', re.I)
FILE_RE = re.compile(r'\b[\w./-]+\.(?:py|jsonl|json|md|sbatch|txt)\b')
URL_RE = re.compile(r'https://claude\.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#')


def clean_text(s):
    """Visible text: no file names or paths. Case URLs become bare case keys (the page links them)."""
    if not isinstance(s, str):
        return s
    s = URL_RE.sub('', s)
    s = re.sub(r'\brecurrence\.jsonl\b', 'the recurrence count', s)
    s = s.replace('per the recurrence count', 'by the recurrence count')
    s = re.sub(r'\breading/REPORT\.md\b', 'the reading study', s)
    s = re.sub(r'\bERRORS\.md\b', 'the errors report', s)
    return s


def scrub(o):
    if isinstance(o, str):
        return clean_text(o)
    if isinstance(o, list):
        return [scrub(x) for x in o]
    if isinstance(o, dict):
        return {k: scrub(v) for k, v in o.items()}
    return o


def scan_paths(o, where, hits):
    if isinstance(o, str):
        if PATH_RE.search(o) or FILE_RE.search(o):
            hits.append((where, o[:160]))
    elif isinstance(o, list):
        for i, x in enumerate(o):
            scan_paths(x, f'{where}[{i}]', hits)
    elif isinstance(o, dict):
        for k, v in o.items():
            scan_paths(v, f'{where}.{k}', hits)


# ----------------------------------------------------------------------------------------------- items
items = {}
for f in sorted(glob.glob(f'{DATA}/items/*.json')):
    d = json.load(open(f))
    items[d['item']['id']] = d
log('items', len(items))


def bullet_text(k, sid, b):
    it = k.rsplit('.', 2)[0]
    st = items[it]['cells'][k]['settings'][sid]
    bb = st['bullets'][b]
    return u16(st['text'], bb['start'], bb['end']), st


# ----------------------------------------------------------------------------------------------- reading: strat
recs = []
for f in sorted(glob.glob(f'{READ}/records/batch_*.json')):
    recs += json.load(open(f))
sample = json.load(open(f'{READ}/sample.json'))
S = {(c['k'], c['setting'], c['bullet']): c for c in sample['cases']}
assert len(recs) == 288 and all((r['k'], r['setting'], r['bullet']) in S for r in recs)
LAB = {'consistent': 0, 'hallucinated': 1, 'off_topic': 2, 'generic': 3, 'empty': 4}
strat, fq_in, fq_miss = [], 0, []
for r in recs:
    s = S[(r['k'], r['setting'], r['bullet'])]
    bt, st = bullet_text(r['k'], r['setting'], r['bullet'])
    fq = r['focus_quote']
    norm_ws = lambda x: re.sub(r'\s+', ' ', x).strip()
    if norm_ws(fq) and (norm_ws(fq) in norm_ws(bt) or norm_ws(fq) in norm_ws(st['text'])):
        fq_in += 1
    else:
        fq_miss.append((r['k'], fq[:60]))
    strat.append({
        'k': r['k'], 's': SI[r['setting']], 'b': r['bullet'], 'L': s['L'], 'src': s['source'],
        'st': r['stratum'], 'sub': s.get('substratum'), 'lab': s['label'], 'ro': LAB.get(s['readout'], 4),
        'sh': s.get('share'), 'so': s.get('solo'), 'pos': s.get('position'),
        'bt': r['blind_type'], 'ja': r['judge_agrees'],
        'rel': clean_text(r['relation_to_context']), 'fq': fq, 'eq': r['evidence_quote'],
        'sr': clean_text(r['score_reading']), 'note': clean_text(r['note']),
        'text': bt})
log('strat rows', len(strat), 'focus quote found in bullet/readout text', fq_in, 'missing', len(fq_miss))

# reader-vs-judge cross-check (REPORT.md section 5)
cx = collections.Counter()
ERRK = {'wrong_relation_or_attribute', 'invented_specific_detail', 'persona_or_self_claim', 'misread_prompt_or_context'}
for r in strat:
    cx[('ja', r['ja'])] += 1
    cx[('lab', r['lab'])] += 1
    if r['lab'] == 'w':
        cx[('w_err', r['bt'] in ERRK or r['bt'] == 'off_topic_junk' or r['bt'] == 'generic_or_vague')] += 1
    if r['lab'] == 'c':
        cx[('c_err', r['bt'] in ERRK)] += 1
    if r['lab'] == 'o':
        cx[('o', 'junk' if r['bt'] == 'off_topic_junk' else 'err' if r['bt'] in ERRK else 'none')] += 1
    cx[('bt', r['bt'])] += 1
log('cross-check', sorted(cx.items(), key=str))

# ----------------------------------------------------------------------------------------------- reading: rep
EP = json.load(open(f'{HERE}/errors_page.json'))
RAW_WQ = {}
for f in sorted(glob.glob(f'{HERE}/records/rep_*.json')):
    d = json.load(open(f))
    for x in (d if isinstance(d, list) else (d.get('cases') or d.get('records'))):
        RAW_WQ[(x['k'], x['setting'], x['bullet'])] = x['wrong_quote']
rep, bt_mismatch, n_multi = [], 0, 0
for c in EP['rep_cases']:
    bt, st = bullet_text(c['k'], c['setting_id'], c['bullet'])
    if bt != c['bullet_text']:
        bt_mismatch += 1
    wq = c['wrong_quote']
    raw = RAW_WQ.get((c['k'], c['setting_id'], c['bullet']))
    # errors_page keeps one verbatim part of a multi-part reader quote ("A | B"); keep every verbatim part (the page marks each)
    if raw and raw != wq and ' | ' in raw and raw not in c['bullet_text']:
        parts = [p for p in raw.split(' | ') if p and p in c['bullet_text']]
        if len(parts) > 1 and wq in parts:
            wq = ' | '.join(parts)
            n_multi += 1
    rep.append({
        'k': c['k'], 's': SI[c['setting_id']], 'b': c['bullet'], 'L': c['L'], 'src': c['source'],
        'w': c['weight'], 'et': c['error_type'], 'sev': c['severity'], 'gist': c['gist_correct'],
        'av': c['avoidability_guess'], 'text': c['bullet_text'], 'wq': wq, 'tq': c['truth_quote'],
        'note': clean_text(c['note']), 'why': c['judge_why'], 'rec': c['rec_32'], 'grade': c['grade'],
        'tip': c['truth_in_pool_32'], 'tt': c['truth_tokens']})
log('rep rows', len(rep), 'bullet_text mismatches vs page items', bt_mismatch, 'multi-part wrong quotes kept', n_multi)

# ----------------------------------------------------------------------------------------------- reading.json
STRATA = [
    ('A_wrong_high', 'A', 'Wrong, high share', 'WRONG bullet whose Shapley share is in the top 20% of wrong bullets of its setting.'),
    ('B_wrong_low', 'B', 'Wrong, low share', 'WRONG bullet whose Shapley share is in the bottom 20% of wrong bullets of its setting (22 forced to have NNLS weight 0).'),
    ('C_clean_low_in_halluc', 'C', 'Clean, low share, hallucinated readout', 'Clean bullet with a bottom-20% share inside a hallucinated readout.'),
    ('D_clean_high_in_consistent', 'D', 'Clean, high share, consistent readout', 'Clean bullet with a top-20% share inside a consistent readout.'),
    ('E_disagree', 'E', 'Settings disagree', 'Cells where Original and another setting got different readout labels.'),
    ('F_wrong_unscored', 'F', 'Wrong text past 32 tokens', 'WRONG bullet whose wrong text lies (all or mostly) past the 32 tokens the reconstructor reads.'),
    ('G_offtopic', 'G', 'Off-topic', 'Bullet the judge labelled OFF-TOPIC.'),
]
BLIND = [
    ('wrong_relation_or_attribute', 'Wrong relation or attribute', 'err'),
    ('invented_specific_detail', 'Invented specific detail', 'err'),
    ('persona_or_self_claim', 'Persona or self-claim', 'err'),
    ('misread_prompt_or_context', 'Misread prompt', 'err'),
    ('off_topic_junk', 'Unrelated junk', 'junk'),
    ('generic_or_vague', 'Generic or vague', 'none'),
    ('plausible_continuation_not_taken', 'Plausible continuation, not an error', 'none'),
    ('judge_overstrict', 'Judge too strict, not an error', 'none'),
    ('not_wrong_clean', 'No error', 'none'),
]
REP_TYPES = [(t['type'], t['label']) for t in EP['type_table']]
SEV = [('contradicts_main_point', 'Contradicts the main point', 'mc'), ('changes_meaning', 'Changes the meaning', 'mc'),
       ('minor_detail', 'Minor detail', 'mi'), ('cosmetic', 'Cosmetic', 'mi'), ('not_an_error', 'Not an error', 'no')]
AV = [('context_makes_it_obvious', 'Truth in context (prompt or reply before READ)'),
      ('lens_guessing_specifics', 'Invented specific with no counterpart'),
      ('needs_info_not_in_activation_plausibly', 'Truth only after READ'),
      ('unclear', 'Unclear')]

C = lambda k: k  # case keys are linked by the page

findings = {
    'question': 'Does low per-bullet FVE mark hallucination?',
    'answer': ('No. Low per-bullet FVE is not a usable marker of hallucination here. Within a readout, a clean bullet '
               'beats a wrong bullet only 50–51% of the time. Wrong bullets are usually the longer ones, and longer '
               'bullets get more FVE. With length matched, the rate rises to 52–55%, and to about 58% against '
               'verified-true clean bullets. So there is at most a weak signal, far from a usable detector.'),
    'answer2': ('FVE rewards other things: longer bullets, bullets later in the list, English rather than Chinese, '
                'bullets that are not redundant, and bullets whose opening matches the format or first words of what '
                'the reply says next. The typical hallucination keeps that frame and gets one detail wrong (a name, '
                'number or entity), and FVE barely notices. Best of 32 and Combine 32 raise FVE but barely change how '
                'often readouts are correct.'),
    'claims': [
        {'id': '3.1', 'status': 'tentative', 'title': 'FVE is at most a very weak marker of hallucination',
         'text': ('Raw within-readout pair rates are about 0.50; with length matched they are 0.52–0.55 (pooled over '
                  'settings, clean wins 0.532 [0.518, 0.547]). In the reading sample, wrong bullets with high and low '
                  'share were real errors equally often (45/60 each). Some slices separate weakly in both directions '
                  '(Original L60 0.544; Combine invented names 0.456), so the accurate summary is "too small to use", '
                  'not "no difference anywhere".'),
         'cases': ['chat-lmsys-0045.L44.p71', 'chat-dailydialog-0006.L52.p285', 'chat-dailydialog-0045.L52.p65']},
        {'id': '3.2', 'status': 'tentative', 'title': 'Right frame, wrong filler: the usual shape of a wrong bullet',
         'text': ('A common wrong bullet keeps the reply\'s frame or template and gets one slot wrong: a name, number, '
                  'entity or attribute. This shape is just as common among low-scoring wrong bullets (readers coded it '
                  'in 37 of 45 confirmed errors in stratum A and 31 of 45 in stratum B), so it does not explain why '
                  'some wrong bullets score high. The score seems to follow the shared frame rather than the filler, '
                  'but no bullet with a corrected filler has been scored yet.'),
         'cases': ['chat-dailydialog-0044.L60.p136', 'chat-lmsys-0038.L52.p364', 'chat-dailydialog-0045.L36.p63']},
        {'id': '3.3', 'status': 'tentative', 'title': 'Low FVE inside a readout reflects form and redundancy',
         'text': ('Right-but-low bullets are usually short or broken, mostly Chinese (no reply contains Chinese), open '
                  'with a list number the reply does not use, sit early in the list, or get NNLS weight 0 because a '
                  'sibling already covers them. Wrong and clean bullets get weight 0 equally often (14.3% vs 14.2% in '
                  'Original), but wrong bullets are longer and sit later in the list, and both raise FVE.'),
         'cases': ['chat-dailydialog-0022.L60.p60', 'chat-lmsys-0058.L60.p139', 'chat-dailydialog-0053.L36.p127']},
        {'id': '3.4', 'status': 'holds', 'title': 'Where the error sits matters a little; the 32-token limit does not',
         'text': ('Only 0.12% / 0.02% / 0.07% of wrong bullets have all their wrong text past the 32 tokens the '
                  'reconstructor reads. Errors in the opening third of a bullet cost some FVE (−0.007 / −0.010 / −0.008 '
                  'solo FVE, about 0.10–0.14 within-readout SD); errors later in the bullet cost nothing.'),
         'cases': ['chat-dailydialog-0069.L52.p76', 'chat-lmsys-0041.L44.p127', 'chat-lmsys-0046.L44.p461']},
        {'id': '3.5', 'status': 'tentative', 'title': 'OFF-TOPIC is penalised a little, but the wrong/off-topic boundary is unstable',
         'text': ('Off-topic bullets lose 3–6 times as much FVE as WRONG ones (−0.014 / −0.019 / −0.011 solo FVE). But '
                  'readers called only 7 of the 24 sampled OFF-TOPIC bullets genuine junk: 9 were on-topic errors that '
                  'should have been WRONG, and 8 had no error (often mixed Chinese/English text flagged as foreign).'),
         'cases': ['chat-dailydialog-0051.L44.p60', 'chat-lmsys-0069.L60.p426', 'chat-lmsys-0047.L44.p314']},
        {'id': '3.6', 'status': 'tentative', 'title': 'Judge noise is large and may hide a small signal',
         'text': ('Against verified-true clean bullets the unmatched pair rate is about 0.50; with length also matched '
                  'it rises to 0.579 / 0.531 / 0.579. So judge noise and length together probably hide a small real '
                  'effect, still far too small to flag individual bullets.'),
         'cases': ['chat-dailydialog-0010.L52.p24', 'chat-dailydialog-0027.L52.p113']},
        {'id': '3.7', 'status': 'tentative', 'title': 'More sampling swaps the sample, not the kind of error',
         'text': ('Best of 32 and Combine 32 raise mean joint FVE from 0.371 to 0.425 and 0.450, but the hallucinated '
                  'rate changes by only −1.6 pts [−3.0, −0.3] and −0.4 pts [−1.7, +1.1]. Best of 32 fixes 659 '
                  'hallucinated cells and breaks 551 consistent ones. Of the 48 cells where the settings disagree, 17 '
                  'flips come from a different sample carrying a real error and 28 from judge inconsistency.'),
         'cases': ['chat-dailydialog-0044.L52.p136', 'chat-dailydialog-0071.L20.p108', 'chat-lmsys-0029.L44.p83']},
        {'id': '3.8', 'status': 'tentative', 'title': 'Kinds of hallucination',
         'text': ('Readers confirmed an error in 145 of the 288 records: wrong relation or attribute 74, invented '
                  'specific detail 53, persona or self-claim 11 (10 of them in dailydialog), misread prompt 7. '
                  'Substitution inside the right frame appears in 83 of the 145 (57%). Readers called only 7 records '
                  'unrelated junk.'),
         'cases': ['chat-lmsys-0052.L60.p209', 'chat-lmsys-0009.L44.p326', 'chat-dailydialog-0063.L44.p118']},
    ],
    'not_survived': [
        {'claim': 'Wrong bullets score the same at every layer, slice and error kind',
         'found': 'About 12 of ~75 slices exclude 0.5, in both directions (e.g. Original L60 0.544; Combine novel names 0.456). Small and uncorrected for multiple tests, but the wording was too strong.',
         'case': 'chat-lmsys-0046.L44.p461'},
        {'claim': 'Wrong and clean bullets have these form features at the same rates',
         'found': 'False for length (wrong is longer in 59–63% of pairs) and position (wrong is later in 64% of pairs in Original and Best of 32).',
         'case': 'chat-dailydialog-0006.L52.p285'},
        {'claim': 'Cleaner labels give the same null',
         'found': 'Verified-true clean bullets with length matched give 0.579 / 0.531 / 0.579.',
         'case': 'chat-dailydialog-0027.L52.p113'},
        {'claim': 'Bullets with invented numbers or names score slightly higher',
         'found': 'A length effect: with length matched the rates are 0.48 / 0.50 / 0.51. "No lower" survives; "higher" does not.',
         'case': 'chat-lmsys-0052.L60.p209'},
        {'claim': 'A WRONG verdict holds only about 2 times in 3',
         'found': 'Misstated: a repeat judgement keeps a WRONG verdict 79% of the time; identical text in another readout keeps it 65% of the time.',
         'case': 'chat-dailydialog-0010.L52.p24'},
        {'claim': 'Best of 32 fixes about as many cells as it breaks',
         'found': 'A small net improvement (−1.6 pts [−3.0, −0.3]) that does not depend on FVE gain; Combine 32 shows no change.',
         'case': 'chat-dailydialog-0044.L52.p136'},
        {'claim': 'Combine 32 adds more invented specifics',
         'found': 'Mostly an effect of which list positions it draws from: +2.1 pts becomes +0.6 [−0.2, +1.5] after reweighting.',
         'case': 'chat-lmsys-0029.L44.p83'},
        {'claim': 'Recap bullets score low (reader hypothesis)',
         'found': 'Overlap with earlier text carries no penalty (pair rates 0.512 / 0.507 / 0.518).',
         'case': 'chat-dailydialog-0021.L36.p299'},
        {'claim': "Combine's late, low-gain picks bring in errors (reader hypothesis)",
         'found': 'The wrong rate is flat over pick order (0.271 / 0.267 / 0.263 / 0.272) and over gain quartile.',
         'case': 'chat-lmsys-0052.L60.p209'},
        {'claim': 'Low share does not flag errors the judge missed (stratum C)',
         'found': 'Cannot be tested: there is no matched group of high-share clean bullets in hallucinated readouts. C vs D gives 7/36 vs 1/36 (p = 0.055), but the two strata come from different readout types.',
         'case': 'chat-lmsys-0009.L44.p326'},
        {'claim': 'Raw and Original flip on identical text (readers\' report)',
         'found': 'The texts differ in whitespace, so these are fresh judgements, not cache misses.',
         'case': 'chat-dailydialog-0063.L44.p118'},
    ],
    # REPORT.md section 2 (pair rates; Original / Best of 32 / Combine 32; 95% chat bootstrap)
    'pair_rates': [
        {'label': 'Clean beats wrong, same readout', 'v': [[0.511, 0.496, 0.527], [0.504, 0.489, 0.521], [0.503, 0.486, 0.519]]},
        {'label': 'Same, length-matched (within 20%)', 'v': [[0.546, 0.521, 0.573], [0.523, 0.501, 0.551], [0.528, 0.505, 0.552]]},
        {'label': 'Wrong vs verified-true clean, length-matched (within 25%)', 'v': [[0.579, 0.523, 0.637], [0.531, 0.479, 0.585], [0.579, 0.534, 0.627]]},
        {'label': "Error starts in the bullet's opening third", 'v': [[0.527, 0.507, 0.548], [0.528, 0.511, 0.547], [0.533, 0.511, 0.554]]},
        {'label': 'Error starts later in the bullet', 'v': [[0.496, 0.475, 0.517], [0.478, 0.453, 0.501], [0.474, 0.450, 0.499]]},
        {'label': 'Clean beats OFF-TOPIC', 'v': [[0.547, 0.514, 0.583], [0.529, 0.489, 0.566], [0.552, 0.516, 0.588]]},
    ],
    # REPORT.md section 5
    'readers_vs_judge': [
        ['Reader agrees / partly agrees / disagrees with the judge', '164 / 86 / 38'],
        ['Judge says WRONG, reader sees a real error', '128 of 192 (67%)'],
        ['Judge says WRONG, reader sees no error', '63 of 192 (33%)'],
        ['Judge says clean, reader sees an error', '8 of 72'],
        ['Judge says OFF-TOPIC: reader sees junk / an error / no error', '7 / 9 / 8 (of 24)'],
        ['Direction of disagreement: judge too strict / judge missed an error / wrong-vs-off-topic boundary', '71 / 8 / 9'],
        ['Settings disagree (48 cells): judge inconsistent / real sample change / uncounted span / judge too strict', '28 / 17 / 2 / 1'],
        ['Test–retest (119 whitespace-only twins): readout flag agrees', '86.6% [80.0, 92.4]'],
        ['Test–retest: a WRONG verdict is repeated', '79% [67, 87]'],
    ],
    'caveats': [
        'Everything is exploratory: about 60 subgroup tests with no correction for multiple tests.',
        'The 288 records are stratified, not representative: counts describe the strata, not the whole population. Readers saw the scores while explaining them.',
        'The reconstructor reads only the first 32 tokens of each bullet.',
        'One judge model (GPT-6 Luna). Its bullet verdicts repeat about 65–79% of the time, it leans too strict (71 too-strict calls against 8 missed errors) and it handles mixed Chinese/English poorly.',
        'Status labels (holds / tentative) come from two skeptic reviews for 3.1 and 3.2, and from the skeptics\' check outputs for the other claims.',
    ],
}

reading = {
    'meta': {'generated': time.strftime('%Y-%m-%d'), 'exploratory': True,
             'note': ('strat: 288 stratified reading records (readers wrote a blind error type before seeing the judge, '
                      'then compared). rep: 240 judge-verified wrong bullets drawn at random with at most 2 per chat; '
                      'w = 1/inclusion probability. s = setting index (0 Original, 1 Best of 32, 2 Combine 32), '
                      'b = 0-based bullet index. Internal file names in reader notes are replaced by plain words.')},
    'strata': [{'id': a, 'code': b, 'label': c, 'def': d, 'n': sum(1 for r in strat if r['st'] == a)} for a, b, c, d in STRATA],
    'blind_types': [{'id': a, 'label': b, 'group': g, 'n': sum(1 for r in strat if r['bt'] == a)} for a, b, g in BLIND],
    'rep_types': [{'id': a, 'label': b, 'n': sum(1 for r in rep if r['et'] == a)} for a, b in REP_TYPES],
    'severity': [{'id': a, 'label': b, 'group': g} for a, b, g in SEV],
    'avoid': [{'id': a, 'label': b} for a, b in AV],
    'findings': findings,
    'strat': strat,
    'rep': rep,
}
for x in reading['blind_types']:
    assert x['n'] > 0, x
assert sum(x['n'] for x in reading['blind_types']) == 288
assert sum(x['n'] for x in reading['rep_types']) == 240

# ----------------------------------------------------------------------------------------------- errors.json
E = {k: v for k, v in EP.items() if k != 'rep_cases'}
E['meta'] = {k: v for k, v in EP['meta'].items() if k in ('generated', 'exploratory', 'family', 'judge', 'rep_sample', 'readers')}
av = dict(E['avoidability'])
sk = dict(av.get('skeptic') or {})
sk.pop('pilot_site_rule', None)
sk.pop('judge_pins_checked', None)
sk['provenance'] = ('Same judge model, prompt and verifier as the page; the pilot sample texts equal the full-grid pool '
                    '(2,304 of 2,304); sample 0 reproduces Original in 72/72 cells and the top-FVE sample reproduces '
                    'Best of 32 in 72/72. The 8 chats and 3 sites per chat were picked by a fixed rule (first, middle '
                    'and last sites) that never looked at readouts or the judge.')
av['skeptic'] = sk
E['avoidability'] = av
jn = dict(E['judge_noise'])
es = dict(jn['earlier_stratified_reading'])
es['note'] = 'Stratified reading study (section 5 of its report); stratified sample, not representative.'
jn['earlier_stratified_reading'] = es
E['judge_noise'] = jn
E = scrub(E)


def unesc(o):
    # a few example notes carry JSON-escaped quotes (\" -> ") from an earlier pipeline step
    if isinstance(o, str):
        return o.replace('\\"', '"')
    if isinstance(o, list):
        return [unesc(x) for x in o]
    if isinstance(o, dict):
        return {k: unesc(v) for k, v in o.items()}
    return o


E = unesc(E)

# pilot cells (72) for the avoidability grid + per-item pilot strips
pilot_rows = [json.loads(l) for l in open(f'{HERE}/avoidability_cells.jsonl')]
CLS = {'hallucinated': 'h', 'consistent': 'c', 'off_topic': 'o', 'generic': 'g', 'empty': 'e'}
pilot_cells, pilot_strip = {}, collections.defaultdict(dict)
for r in pilot_rows:
    cnt = r['counts']
    pilot_cells[r['k']] = {
        'item': r['item'], 'src': r['source'], 'L': r['layer'], 'p': r['pos'], 'cls': r['cell_class'],
        'cls_s': r['cell_class_strict'], 'n': [cnt.get('hallucinated', 0), cnt.get('consistent', 0), cnt.get('off_topic', 0),
                                              cnt.get('generic', 0), cnt.get('empty', 0)],
        'n_ok_strict': r.get('consistent_not_suspect'), 'top': r['top_fve_sample'], 'top_cls': CLS.get(r['top_fve_class']),
        'rank': r['best_clean_rank_by_fve'], 'prompt': (r.get('prompt') or '')[:90]}
    samples = []
    for s in r['samples']:
        w = [x[:90] for x in (s.get('wrong') or [])[:3]]
        samples.append([s['idx'], CLS.get(s['class'], 'e'), None if s.get('fve') is None else round(s['fve'], 4), w,
                        len(s.get('wrong') or []), bool(s.get('a_eligible', True))])
    susp = sorted(int(x) for x in (r.get('suspect_clean_samples') or {}).keys())
    pilot_strip[r['item']][r['k']] = {'cls': r['cell_class'], 'cls_s': r['cell_class_strict'], 'top': r['top_fve_sample'],
                                      'rank': r['best_clean_rank_by_fve'], 'susp': susp, 'samples': samples}
E['pilot_cells'] = pilot_cells
log('pilot cells', len(pilot_cells), collections.Counter(v['cls'] for v in pilot_cells.values()))

# ----------------------------------------------------------------------------------------------- recurrence per span
pool = json.load(open(f'{HERE}/pool_hall.json'))['pools']
log('pool loaded', len(pool))
pool_f = {}


def pf(k):
    if k not in pool_f:
        pool_f[k] = [feats(t) for t in pool[k]]
    return pool_f[k]


ref_cache = {}


def ref_feats(item):
    if item not in ref_cache:
        it = items[item]['item']
        ref_cache[item] = feats(it['prompt'] + '\n' + it['response'])
    return ref_cache[item]


rec = collections.defaultdict(lambda: collections.defaultdict(lambda: [[], [], []]))
n_rows = n_match = n_tt = 0
miss = []
tt_cache = {}
with open(f'{HERE}/recurrence.jsonl') as fh:
    for line in fh:
        r = json.loads(line)
        n_rows += 1
        k, sid, span = r['k'], r['setting'], r['span']
        st = items[r['item']]['cells'][k]['settings'][sid]
        if any(sp['type'] == 'wrong' and sp['verified'] and sp['text'] == span for sp in st['spans']):
            n_match += 1
        else:
            miss.append((k, sid, span[:50]))
        els = r.get('elements') or []
        each = r.get('rec_each_32')
        el_out = [[e['text'], (each[i] if each and i < len(each) else None)] for i, e in enumerate(els)]
        lay = r.get('rec_layers') or {}
        base = r.get('base') or {}
        key = (k, span, r['why'])
        if key not in tt_cache:
            tt = truth_tokens(r['why'], span, ref_feats(r['item']), feats(span))
            if tt:
                P = pf(k)
                cnt = sum(1 for f in P if any(match_feats(e, f) for e in tt))
                cnt_all = sum(1 for f in P if all(match_feats(e, f) for e in tt))
                tt_cache[key] = [[e[1] for e in tt], cnt, cnt_all]
            else:
                tt_cache[key] = None
        tt = tt_cache[key]
        if tt:
            n_tt += 1
        row = [span, r.get('rec_32'), el_out, lay.get('n_readout_layers'), lay.get('n_pool_layers_any'),
               base.get('other_chats_with'), r.get('kind'), tt]
        rec[r['item']][k][SI[sid]].append(row)
        if n_rows % 4000 == 0:
            log('recurrence rows', n_rows)
log('recurrence rows', n_rows, 'matched to page spans', n_match, 'missing', len(miss), miss[:5], 'with truth tokens', n_tt)

os.makedirs(f'{DATA}/rec', exist_ok=True)
tot_rec = 0
for it in items:
    out = {'cells': {k: v for k, v in rec.get(it, {}).items()}}
    if it in pilot_strip:
        out['pilot'] = pilot_strip[it]
    s = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    with open(f'{DATA}/rec/{it}.json', 'w') as fh:
        fh.write(s)
    tot_rec += len(s.encode())
log('rec files', len(items), 'total bytes', tot_rec)

# ----------------------------------------------------------------------------------------------- write + checks
hits = []
scan_paths(reading, 'reading', hits)
scan_paths(E, 'errors', hits)
for h in hits:
    print('PATH-LIKE TEXT:', h)
with open(f'{DATA}/reading.json', 'w') as fh:
    fh.write(json.dumps(reading, ensure_ascii=False, separators=(',', ':')))
with open(f'{DATA}/errors.json', 'w') as fh:
    fh.write(json.dumps(E, ensure_ascii=False, separators=(',', ':')))
for f in ('reading.json', 'errors.json'):
    log(f, os.path.getsize(f'{DATA}/{f}'))
log('done')
