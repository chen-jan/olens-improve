#!/usr/bin/env python
"""Confound checks on ERRORS.md / errors_page.json (skeptic pass, 2026-10-15; exploratory).

Read-only inputs (all in errors/ unless noted):
  recurrence.jsonl, recurrence_baseline.jsonl, avoidability_cells.jsonl, pool_hall.json,
  ../page/data/items/*.json
Writes errors/skeptic_checks.json. About 1-2 CPU-min, < 4 GB.

Checks
  1. Recurrence grade vs matching rule and number of key elements (conjunction strictness), basis,
     and a "core" subset without reply-word / prior-like elements.
  2. Majority-vote keep rates, true claims vs wrong spans, standardised to the wrong spans'
     number-of-elements mix (blind rule).
  3. Cross-layer persistence of sticky spans restricted to chat-specific names/numbers.
  4. Truth-in-pool for name spans: Chinese-heavy pools vs others (translation false zeros?).
  5. Pilot (72 cells): robustness of the perfect-picker rescue to single-sample judge misses,
     chat vs layer variance of the hallucinated share, within-cell FVE discrimination and
     top-FVE minus random with chat bootstrap, and how often strict-rule suspects rest on
     "does not say" flags (which the judge prompt says not to mark).
  6. Hand checks (recorded verdicts; keys are page anchors).
"""
import collections
import glob
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import errors_synth as es  # noqa: E402
from recurrence import feats, match_feats  # noqa: E402

PAGE = 'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3'
OUT = {}


def grade(v):
    return 'one_off' if v <= 2 else ('sticky' if v >= 16 else 'recurring')


def dist(rs, f):
    c = collections.Counter(grade(f(r)) for r in rs)
    n = len(rs)
    return {'n': n, **{g: round(100 * c[g] / n, 1) for g in ('one_off', 'recurring', 'sticky')}}


# ------------------------------------------------------------------ 1. grade sensitivity
rows = [json.loads(line) for line in open(f'{HERE}/recurrence.jsonl')]
rows = [r for r in rows if r['rec_32'] is not None]
prim = lambda r: r['rec_32']  # noqa: E731
s1 = {
    'all_rows_primary_rule_all_key_words': dist(rows, prim),
    'unique_per_cell_primary': dist([r for r in rows if r.get('dup_first')], prim),
    'rule_2_of_key_words': dist(rows, lambda r: r['rec_2of_32']),
    'rule_any_key_word': dist(rows, lambda r: r['rec_any_32']),
    'by_n_elements_primary': {str(n): dist([r for r in rows if len(r['elements']) == n], prim) for n in (1, 2, 3)},
    'by_basis_primary': {b: dist([r for r in rows if r['element_basis'] == b], prim)
                         for b in sorted({r['element_basis'] for r in rows})},
    'single_element_novel_name_or_number': dist([r for r in rows if len(r['elements']) == 1 and r['element_basis'] in ('name', 'number')], prim),
    'core_without_reply_word_and_prior_like_elements': dist(
        [r for r in rows if r['element_basis'] != 'content_nonnovel' and r['base']['other_chats_with'] < 0.25 * r['base']['other_chats']], prim),
    'duplicate_rows_same_span_other_setting_same_cell_pct': round(100 * sum(not r.get('dup_first') for r in rows) / len(rows), 1),
}
st = [r for r in rows if r['rec_32'] >= 16]
s1['sticky_rows'] = len(st)
s1['sticky_rows_reply_word_basis'] = sum(r['element_basis'] == 'content_nonnovel' for r in st)
s1['sticky_rows_prior_like'] = sum(r['base']['other_chats_with'] >= 0.25 * r['base']['other_chats'] for r in st)
OUT['1_recurrence_rule_sensitivity'] = s1

# ------------------------------------------------------------------ 2. vote keep rates standardised
base = [json.loads(line) for line in open(f'{HERE}/recurrence_baseline.jsonl')]
val = lambda r: r['blind']['rec_32']  # noqa: E731
nel = lambda r: len(r['blind']['elements'])  # noqa: E731
okb = lambda r: r.get('blind') and r['blind'].get('rec_32') is not None  # noqa: E731
W = [r for r in rows if okb(r)]
T = [b for b in base if b['unit'] == 'claim_true' and okb(b)]


def keep_by_n(rs):
    by = collections.defaultdict(lambda: [0, 0])
    for r in rs:
        by[nel(r)][0] += val(r) >= 16
        by[nel(r)][1] += 1
    return {k: (100 * a / b, b) for k, (a, b) in sorted(by.items())}


def standardised(wr, tr):
    kw, kt = keep_by_n(wr), keep_by_n(tr)
    tot = sum(b for _, b in kw.values())
    return {'wrong_keep_pct': round(sum(a * b for a, b in kw.values()) / tot, 1),
            'true_keep_pct_standardised_to_wrong_mix': round(sum(kt[k][0] * kw[k][1] for k in kw if k in kt) / tot, 1),
            'true_keep_pct_raw': round(100 * sum(val(r) >= 16 for r in tr) / len(tr), 1),
            'by_n_elements': {str(k): {'wrong': round(kw[k][0], 1), 'true': round(kt[k][0], 1) if k in kt else None} for k in kw}}


OUT['2_vote_keep_standardised'] = {
    'all': standardised(W, T),
    'names_numbers': standardised([r for r in W if r['blind']['basis'] in ('name', 'number')],
                                  [b for b in T if b['blind']['basis'] in ('name', 'number')]),
}

# ------------------------------------------------------------------ 3. cross-layer persistence of sticky spans
f3 = lambda r: r['rec_layers']['n_readout_layers'] > 0  # noqa: E731


def rate(rs):
    rs = list(rs)
    return {'pct': round(100 * sum(map(f3, rs)) / len(rs), 1), 'n': len(rs)}


OUT['3_sticky_in_same_setting_readout_other_layer'] = {
    'all_sticky': rate(st),
    'chat_specific_le2_other_chats': rate(r for r in st if r['base']['other_chats_with'] <= 2),
    'name_number_and_chat_specific': rate(r for r in st if r['element_basis'] in ('name', 'number') and r['base']['other_chats_with'] <= 2),
    'prior_like': rate(r for r in st if r['base']['other_chats_with'] >= 0.25 * r['base']['other_chats']),
}

# ------------------------------------------------------------------ 4. truth-in-pool vs Chinese-heavy pools
items = {}
for f in glob.glob(os.path.join(os.path.dirname(HERE), 'page', 'data', 'items', '*.json')):
    d = json.load(open(f))
    items[d['item']['id']] = d
pool = json.load(open(f'{HERE}/pool_hall.json'))['pools']
CJK = re.compile('[一-鿿]')
rr = es.load_recurrence()
ref = {}
T4 = []
for r in rr:
    if not r['dup_first'] or r['element_basis'] not in ('name', 'number'):
        continue
    it = items[r['item']]['item']
    if r['item'] not in ref:
        ref[r['item']] = feats(it['prompt'] + '\n' + it['response'])
    tt = es.truth_tokens(r['why'], r['span'], ref[r['item']], feats(r['span']))
    if not tt:
        continue
    P = pool[r['k']]
    cnt = sum(any(match_feats(e, feats(t)) for e in tt) for t in P)
    T4.append({'basis': r['element_basis'], 'cnt': cnt, 'ncjk': sum(bool(CJK.search(t)) for t in P),
               'chat_cjk': bool(CJK.search(it['prompt'] + it['response']))})
s4 = {}
for lab, f in [('pool_cjk_ge16_latin_chat', lambda t: t['ncjk'] >= 16 and not t['chat_cjk']),
               ('pool_cjk_lt16_latin_chat', lambda t: t['ncjk'] < 16 and not t['chat_cjk'])]:
    for b in ('name', 'number'):
        s = [t for t in T4 if f(t) and t['basis'] == b]
        s4[f'{lab}:{b}'] = {'n': len(s), 'truth_in_0_lenient_pct': round(100 * sum(t['cnt'] == 0 for t in s) / len(s), 1)}
s4['hand_check'] = {
    'design': '25 random lenient truth-in-0 name rows (word truth tokens only) from Latin-script chats whose pool has CJK in >=16/32 samples; the most frequent CJK runs of each pool were read for a Chinese rendering of the truth.',
    'truth_written_in_chinese': 1,
    'example': {'k': 'chat-lmsys-0025.L52.p236', 'truth': 'Shanghai Huihe', 'pool': '"上海" (Shanghai) in 5/32 samples, always as the city part of an invented company name (e.g. "上海捷诺", "上海惠丰", "上海兰众化工")', 'link': f'{PAGE}#chat-lmsys-0025.L52.p236'},
    'junk_truth_tokens': ['Antwort (German "answer", chat-lmsys-0062.L36.p248)', 'PC (chat-lmsys-0063.L36.p321)', 'IP (chat-lmsys-0063.L20.p189)'],
    'of': 25,
}
OUT['4_truth_in_pool_translation'] = s4

# ------------------------------------------------------------------ 5. pilot
C = [json.loads(line) for line in open(f'{HERE}/avoidability_cells.jsonl')]
OH = [c for c in C if c['original_sample0_class'] == 'hallucinated']
res = [c for c in OH if c['consistent_asserting_available']]
s5 = {
    'original_hallucinated_cells': len(OH),
    'rescuable_face_value': len(res),
    'rescuable_with_ge3_clean_samples': sum(c['counts']['consistent'] >= 3 for c in res),
    'rescuable_with_only_1_or_2_clean_samples': sum(c['counts']['consistent'] <= 2 for c in res),
    'rescuable_strict': sum(c['consistent_available_strict'] for c in res),
    'rescuable_strict_with_ge3_nonsuspect_clean': sum(c['consistent_not_suspect'] >= 3 for c in res),
    'n_clean_in_rescuable_cells': sorted(c['counts']['consistent'] for c in res),
}
p = np.array([c['p_random_hallucinated'] for c in C])
vd = {}
for key in ('item', 'layer'):
    g = collections.defaultdict(list)
    for c in C:
        g[c[key]].append(c['p_random_hallucinated'])
    m = {k: float(np.mean(v)) for k, v in g.items()}
    vd[key] = {'means': {str(k): round(v, 3) for k, v in sorted(m.items())},
               'between_variance_share': round(sum(len(v) * (m[k] - p.mean()) ** 2 for k, v in g.items()) / len(p) / p.var(), 3)}
s5['hallucinated_share_variance_by_chat_vs_layer'] = vd
rng = np.random.default_rng(0)
per_item = collections.defaultdict(lambda: [0.0, 0])
for c in C:
    S = [s for s in c['samples'] if s.get('a_eligible')]
    pos = [s['fve'] for s in S if s['class'] == 'consistent']
    neg = [s['fve'] for s in S if s['class'] == 'hallucinated']
    if pos and neg:
        per_item[c['item']][0] += sum(1.0 if x > y else 0.5 if x == y else 0.0 for x in pos for y in neg)
        per_item[c['item']][1] += len(pos) * len(neg)
its = sorted(per_item)
a = np.array([per_item[i][0] for i in its])
n = np.array([per_item[i][1] for i in its])
boots = [a[ix].sum() / n[ix].sum() for ix in (rng.choice(len(its), len(its), replace=True) for _ in range(5000))]
s5['fve_auc_consistent_over_hallucinated_within_cell'] = {
    'est': round(float(a.sum() / n.sum()), 3), 'lo': round(float(np.percentile(boots, 2.5)), 3),
    'hi': round(float(np.percentile(boots, 97.5)), 3), 'chats': len(its),
    'note': 'pair-weighted, A-eligible samples, chat bootstrap with only 8 clusters (approximate); project doc 012 reports .533 with an interval including .5'}
d = collections.defaultdict(list)
for c in C:
    S = [s for s in c['samples'] if s.get('a_eligible')]
    d[c['item']].append((c['top_fve_class'] == 'consistent') - sum(s['class'] == 'consistent' for s in S) / len(S))
its = sorted(d)
arr = [np.array(d[i]) for i in its]
boots = [sum(arr[i].sum() for i in ix) for ix in (rng.choice(len(its), len(its), replace=True) for _ in range(5000))]
s5['top_fve_clean_minus_random_cells'] = {'est': round(float(sum(x.sum() for x in arr)), 2),
                                          'lo': round(float(np.percentile(boots, 2.5)), 1),
                                          'hi': round(float(np.percentile(boots, 97.5)), 1), 'of_cells': len(C)}
ABS = re.compile(r"\b(does not|doesn't|did not|never|no)\b.*\b(say|says|mention|mentions|state|states|express|describe|"
                 r"indicate|specify|claim|give|offer|refer)", re.I)
sus = [v for c in C for v in c['suspect_clean_samples'].values()]
lost = [c for c in C if c['consistent_asserting_available'] and not c['consistent_available_strict']]
s5['strict_rule_suspects'] = {
    'suspect_clean_samples': len(sus),
    'resting_on_does_not_say_flags': sum(bool(ABS.search(v.get('why_there', ''))) for v in sus),
    'cells_losing_clean_availability_under_strict': len(lost),
    'of_which_only_does_not_say_flags': sum(all(ABS.search(v.get('why_there', '')) for v in c['suspect_clean_samples'].values()) for c in lost),
    'example': {'k': 'chat-dailydialog-0002.L20.p20', 'span': "It's a pleasure to see you.",
                'why': 'The response says only "Good morning!" and does not express pleasure at seeing the user.',
                'link': f'{PAGE}#chat-dailydialog-0002.L20.p20'},
}
s5['pilot_vs_bank_original_hallucinated_of_specific'] = {'pilot72': '46/71', 'dev_L20_44_60': '337/681', 'full_bank': '2641/5554'}
s5['pilot_site_rule'] = 'configs/splits_pilot_shared_v2.json: deterministic whole-group subset, layers 20/44/60, first/middle/last frozen sites, no readout/judge/gold-based selection'
s5['judge_pins_checked'] = ('project_contract.json of candidate_index_00-n32 vs expansion-v1 capped_n1-n1: same model gpt-6-luna, reasoning none, '
                            'prompt v5c-chat, verify v5c-chat-verify-v1, k max 3 with 1 readout per call, benchmark commit 92d763e, identical '
                            'judge.py/prompts.py/score.py/llm.py/mcjudge.py/cache.py hashes; only concurrency/rpm/allow_missing and layers differ')
OUT['5_pilot'] = s5

# ------------------------------------------------------------------ 6. hand checks
OUT['6_hand_checks'] = {
    'sticky_rows': {
        'design': '30 random sticky rows (rec_32 >= 16, first copy per cell), random.seed(2026); question: do the key elements carry the error?',
        'element_not_the_error': 9, 'partial': 2, 'of': 30,
        'not_the_error_examples': [
            {'k': 'chat-lmsys-0024.L36.p253', 'span': 'This is why it’s called the "Singularity."', 'element': 'called', 'rec_32': 23},
            {'k': 'chat-lmsys-0033.L52.p350', 'span': 'Enter Resistance (Ohms): 10', 'element': '10', 'rec_32': 30},
            {'k': 'chat-lmsys-0061.L36.p39', 'span': 'Here are 5 proven strategies to manage your time effectively', 'element': 'effectively', 'rec_32': 24},
            {'k': 'chat-lmsys-0074.L36.p200', 'span': 'class', 'element': 'class', 'rec_32': 31},
            {'k': 'chat-dailydialog-0073.L20.p215', 'span': 'improve your GPA', 'element': 'improve', 'rec_32': 26},
            {'k': 'chat-lmsys-0028.L60.p440', 'span': 'In a manufacturing setting, NaH is used as a drying agent or in polymer synthesis.', 'element': 'NaH', 'rec_32': 23},
            {'k': 'chat-lmsys-0034.L44.p262', 'span': '- - **About X-axis:** $$ I_{xx} = \\frac{bh^3}{12}', 'element': 'frac; axis', 'rec_32': 32},
            {'k': 'chat-lmsys-0016.L36.p96', 'span': 'Were regularly', 'element': 'regularly', 'rec_32': 30},
            {'k': 'chat-lmsys-0056.L60.p164', 'span': 'First 10 Fibonacci Numbers: 0 1 1 2 3 5 8 1', 'element': 'fibonacci; numbers; first', 'rec_32': 31},
        ],
    },
    'one_off_rows': {
        'design': '30 random one-off rows (rec_32 <= 2, first copy per cell), random.seed(2026); question: is the error itself rare in the pool?',
        'wrong_word_itself_ge16_of_32': 3, 'main_wrong_word_in_3_to_15': 8, 'of': 30,
        'examples': [
            {'k': 'chat-lmsys-0043.L44.p391', 'span': 'The "2-" indicates a methyl group at the second carbon,', 'elements': 'methyl 30/32, carbon 1/32, indicates 1/32', 'rec_32': 1},
            {'k': 'chat-lmsys-0061.L20.p327', 'span': 'Use the timer app to enforce breaks.', 'elements': 'timer 21/32, enforce 1/32', 'rec_32': 1},
            {'k': 'chat-lmsys-0035.L20.p370', 'span': 'the total amount of dirt consumed by the', 'elements': 'dirt 18/32, consumed 1/32, amount 21/32', 'rec_32': 1},
        ],
    },
    'featured_example_corrections': [
        {'k': 'chat-lmsys-0040.L36.p65', 'was': '"250" is in 0/32 samples', 'now': '"250" is in 2/32 samples ("Rain: Rainfall 250mm", "Rainfall: ~250mm"); the old regex \\b250\\b cannot match "250mm"'},
        {'k': 'chat-lmsys-0043.L60.p391', 'was': 'ERRORS.md cited only "ethyl" 24/32 and "formyl" 0/32', 'now': 'the true 2-position group "propyl" is in 17/32 samples as a whole word (19/32 as a substring), e.g. sample #1 "At position 2, it is substituted with a propyl group"'},
    ],
}
for blk in OUT['6_hand_checks'].values():
    for e in (blk.get('not_the_error_examples', []) + blk.get('examples', []) if isinstance(blk, dict) else blk):
        e['link'] = f"{PAGE}#{e['k']}"

json.dump(OUT, open(f'{HERE}/skeptic_checks.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in OUT.items() if k != '6_hand_checks'}, indent=1, ensure_ascii=False)[:9000])
