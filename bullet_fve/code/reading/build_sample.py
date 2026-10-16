"""Deterministic stratified reading sample (seed 0): 288 cases = 24 batches x 12.

Writes reading/sample.json. Run:
  ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B build_sample.py
"""
import collections
import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bullet_table import DATA, SIDS, load_rows  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample.json')
SEED = 0
ORIG, BEST, COMB = SIDS
SHORT = {ORIG: 'Original', BEST: 'Best of 32', COMB: 'Combine 32'}
LAYERS = [20, 36, 44, 52, 60]
SOURCES = ['dailydialog', 'lmsys']
N_BATCH, BATCH_SIZE = 24, 12

rng = random.Random(SEED)
rows, cells = load_rows()


def q(vals, p):
    return float(np.quantile(np.array(vals, dtype=float), p))


# ----------------------------------------------------------------------------- thresholds and extra fields
thr = {}
for sid in SIDS:
    R = [r for r in rows if r['setting'] == sid]
    w = [r['share'] for r in R if r['label'] == 'w']
    ch = [r['share'] for r in R if r['label'] == 'c' and r['readout'] == 'hallucinated']
    cc = [r['share'] for r in R if r['label'] == 'c' and r['readout'] == 'consistent']
    thr[sid] = {'wrong_q80': q(w, .8), 'wrong_q20': q(w, .2), 'clean_in_halluc_q20': q(ch, .2),
                'clean_in_consistent_q80': q(cc, .8), 'n_wrong': len(w), 'n_clean_in_halluc': len(ch),
                'n_clean_in_consistent': len(cc)}

# fraction of the bullet's wrong-span characters (verified wrong occurrences, clipped to the bullet) that lie
# at or after the 32-token AR limit
_items = {}


def item_json(item_id):
    if item_id not in _items:
        with open(os.path.join(DATA, 'items', item_id + '.json')) as f:
            _items[item_id] = json.load(f)
    return _items[item_id]


def unscored_frac(r):
    s = item_json(r['item'])['cells'][r['k']]['settings'][r['setting']]
    b = s['bullets'][r['bullet']]
    hits = [(max(a, b['start']), min(e, b['end'])) for sp in s['spans'] if sp['verified'] and sp['type'] == 'wrong'
            for a, e in sp['offsets'] if a < b['end'] and e > b['start']]
    tot = sum(e - a for a, e in hits)
    uns = sum(max(0, e - max(a, b['scored_end'])) for a, e in hits)
    return uns / tot if tot else 0.0


for r in rows:
    r['unscored_frac'] = unscored_frac(r) if (r['label'] == 'w' and r['truncated']) else 0.0

# ----------------------------------------------------------------------------- balanced picker
used = set()                       # (k, setting, bullet) across all strata
picked = []                        # final case records


def pick(pool, setting_targets, stratum, substratum, item_cap=2):
    """Greedy deficit-driven pick: hard setting quotas, soft balance of (setting, layer) and (setting, source),
    prefer unused items and cells within the stratum, item cap per stratum. Pool order is shuffled with rng."""
    pool = [r for r in pool if (r['k'], r['setting'], r['bullet']) not in used]
    rng.shuffle(pool)
    n_tot = sum(setting_targets.values())
    item_n = collections.Counter(c['item'] for c in picked if c['stratum'] == stratum)
    cell_n = collections.Counter(c['k'] for c in picked if c['stratum'] == stratum)
    cnt_s = collections.Counter()
    cnt_sl = collections.Counter()
    cnt_ss = collections.Counter()
    cnt_l = collections.Counter(c['L'] for c in picked if c['stratum'] == stratum)
    cnt_src = collections.Counter(c['source'] for c in picked if c['stratum'] == stratum)
    n_prev = sum(cnt_l.values())
    out = []
    for _ in range(n_tot):
        best, best_score = None, None
        for r in pool:
            sid = r['setting']
            if cnt_s[sid] >= setting_targets.get(sid, 0):
                continue
            if item_n[r['item']] >= item_cap or (r['k'], sid, r['bullet']) in used:
                continue
            ns = setting_targets[sid]
            m = n_prev + len(out)
            score = (2.0 * (ns / 5 - cnt_sl[(sid, r['L'])]) + 1.0 * (ns / 2 - cnt_ss[(sid, r['source'])])
                     + 1.0 * ((m + 1) / 5 - cnt_l[r['L']]) + 1.0 * ((m + 1) / 2 - cnt_src[r['source']])
                     - 1.5 * item_n[r['item']] - 3.0 * cell_n[r['k']])
            if best_score is None or score > best_score + 1e-12:
                best, best_score = r, score
        if best is None:
            raise SystemExit(f'{stratum}/{substratum}: ran out of candidates after {len(out)} '
                             f'(targets {setting_targets}, got {dict(cnt_s)})')
        sid = best['setting']
        used.add((best['k'], sid, best['bullet']))
        item_n[best['item']] += 1
        cell_n[best['k']] += 1
        cnt_s[sid] += 1
        cnt_sl[(sid, best['L'])] += 1
        cnt_ss[(sid, best['source'])] += 1
        cnt_l[best['L']] += 1
        cnt_src[best['source']] += 1
        rec = dict(best, stratum=stratum, substratum=substratum)
        out.append(rec)
        picked.append(rec)
    return out


def ok_bullet(r):
    return r['share'] is not None and not r['dup']


# ----------------------------------------------------------------------------- strata
wrong = [r for r in rows if r['label'] == 'w']
STRATA = []

# F: wrong spans past the AR limit. Only 12 bullets meet the strict rule in the whole data, so all are taken
# and the rest is filled with wrong bullets whose wrong-span text lies mostly (>= 50%) past the limit.
f_strict = [r for r in wrong if r['wrong_unscored_only']]
assert len(f_strict) == 12, len(f_strict)
f_cnt = collections.Counter(r['setting'] for r in f_strict)
pick(f_strict, dict(f_cnt), 'F_wrong_unscored', 'F1_all_wrong_text_unscored', item_cap=2)
f_part = [r for r in wrong if not r['wrong_unscored_only'] and r['unscored_frac'] >= 0.5]
pick(f_part, {ORIG: 3, BEST: 6, COMB: 3}, 'F_wrong_unscored', 'F2_most_wrong_text_unscored', item_cap=2)

# G: off-topic bullets
pick([r for r in rows if r['label'] == 'o' and ok_bullet(r)], {ORIG: 9, BEST: 9, COMB: 6}, 'G_offtopic', 'G')

# E: settings disagree on the whole cell; bullet = a wrong bullet of the hallucinated readout (seeded choice)
rows_by = {(r['k'], r['setting'], r['bullet']): r for r in rows}


def e_pool_fast(sid_h, cond):
    pool = []
    for k, c in sorted(cells.items()):
        if not cond(c['labels']):
            continue
        ws = [j for j, x in enumerate(c['bl'][sid_h]) if x == 'w']
        j = random.Random(f'{SEED}:{k}:{sid_h}').choice(ws) if ws else 0
        pool.append(rows_by[(k, sid_h, j)])
    return pool


e1 = e_pool_fast(ORIG, lambda L: L[ORIG] == 'hallucinated' and L[BEST] == 'consistent')
e2 = e_pool_fast(COMB, lambda L: L[ORIG] == 'consistent' and L[COMB] == 'hallucinated')
pick(e1, {ORIG: 24}, 'E_disagree', 'E1_orig_halluc_best_consistent', item_cap=2)
pick(e2, {COMB: 24}, 'E_disagree', 'E2_orig_consistent_combine_halluc', item_cap=2)

# A: wrong bullet, Shapley share in the top 20% of wrong bullets of its setting
pick([r for r in wrong if ok_bullet(r) and r['share'] >= thr[r['setting']]['wrong_q80']],
     {ORIG: 22, BEST: 22, COMB: 16}, 'A_wrong_high', 'A')
# B: wrong bullet, bottom 20% share; half of the Original / Best of 32 cases with NNLS coef 0
b_pool = [r for r in wrong if ok_bullet(r) and r['share'] <= thr[r['setting']]['wrong_q20']]
pick([r for r in b_pool if r['coef'] == 0], {ORIG: 11, BEST: 11}, 'B_wrong_low', 'B1_coef0')
pick([r for r in b_pool if r['coef'] > 0], {ORIG: 11, BEST: 11, COMB: 16}, 'B_wrong_low', 'B2_coef_pos')
# C: clean bullet, bottom 20% share among clean bullets of hallucinated readouts of its setting
pick([r for r in rows if r['label'] == 'c' and r['readout'] == 'hallucinated' and ok_bullet(r)
      and r['share'] <= thr[r['setting']]['clean_in_halluc_q20']],
     {ORIG: 13, BEST: 13, COMB: 10}, 'C_clean_low_in_halluc', 'C')
# D: clean bullet, top 20% share among clean bullets of consistent readouts of its setting
pick([r for r in rows if r['label'] == 'c' and r['readout'] == 'consistent' and ok_bullet(r)
      and r['share'] >= thr[r['setting']]['clean_in_consistent_q80']],
     {ORIG: 13, BEST: 13, COMB: 10}, 'D_clean_high_in_consistent', 'D')

assert len(picked) == 288, len(picked)
assert len({(c['k'], c['setting'], c['bullet']) for c in picked}) == 288
for st, n in collections.Counter(c['stratum'] for c in picked).items():
    per_item = collections.Counter(c['item'] for c in picked if c['stratum'] == st)
    assert max(per_item.values()) <= 2, (st, per_item.most_common(3))

# ----------------------------------------------------------------------------- batches
per_batch = {  # stratum -> list of 24 slot counts
    'A_wrong_high': [3] * 12 + [2] * 12,
    'B_wrong_low': [2] * 12 + [3] * 12,
    'C_clean_low_in_halluc': [2, 1] * 12,
    'D_clean_high_in_consistent': [1, 2] * 12,
    'E_disagree': [2] * 24,
    'F_wrong_unscored': [1] * 24,
    'G_offtopic': [1] * 24,
}
assert all(sum(v) == sum(1 for c in picked if c['stratum'] == s) for s, v in per_batch.items())
assert all(sum(v[b] for v in per_batch.values()) == BATCH_SIZE for b in range(N_BATCH))
batches = [[] for _ in range(N_BATCH)]
cap = {s: list(v) for s, v in per_batch.items()}
# deal the most constrained strata first; within a stratum interleave sub-strata/settings/layers
for st in ['F_wrong_unscored', 'E_disagree', 'G_offtopic', 'C_clean_low_in_halluc', 'D_clean_high_in_consistent',
           'A_wrong_high', 'B_wrong_low']:
    cs = [c for c in picked if c['stratum'] == st]
    rng.shuffle(cs)
    cs.sort(key=lambda c: (c['substratum'], c['setting'], c['L'], c['source']))
    for c in cs:
        best, best_key = None, None
        for b in range(N_BATCH):
            if cap[st][b] <= 0:
                continue
            bb = batches[b]
            key = (10 * sum(x['item'] == c['item'] for x in bb)
                   + 3 * sum(x['substratum'] == c['substratum'] for x in bb)
                   + 2 * sum(x['setting'] == c['setting'] for x in bb)
                   + 1 * sum(x['L'] == c['L'] for x in bb)
                   + 1 * sum(x['source'] == c['source'] for x in bb), rng.random())
            if best_key is None or key < best_key:
                best, best_key = b, key
        cap[st][best] -= 1
        batches[best].append(c)


# repair: swap a case with a same-stratum case of another batch when an item repeats inside a batch
def n_dup(bb):
    return len(bb) - len({c['item'] for c in bb})


for b in range(N_BATCH):
    for _ in range(5):
        if not n_dup(batches[b]):
            break
        seen, bad = set(), None
        for c in batches[b]:
            if c['item'] in seen:
                bad = c
            seen.add(c['item'])
        done = False
        for b2 in range(N_BATCH):
            if b2 == b or done:
                continue
            for c2 in batches[b2]:
                if c2['stratum'] != bad['stratum'] or c2['setting'] != bad['setting']:
                    continue
                nb = [x for x in batches[b] if x is not bad] + [c2]
                nb2 = [x for x in batches[b2] if x is not c2] + [bad]
                if n_dup(nb) == 0 and n_dup(nb2) == 0:
                    batches[b], batches[b2] = nb, nb2
                    done = True
                    break
for bb in batches:
    rng.shuffle(bb)
assert all(len(bb) == BATCH_SIZE for bb in batches)
dup_items_in_batch = sum(len(bb) - len({c['item'] for c in bb}) for bb in batches)

# ----------------------------------------------------------------------------- write
DEFS = {
    'A_wrong_high': ('WRONG bullet (overlaps a verified wrong span) whose Shapley share is in the top 20% of all '
                     'wrong bullets of its setting (share >= setting q80). Dup bullets excluded.', 60),
    'B_wrong_low': ('WRONG bullet whose Shapley share is in the bottom 20% of all wrong bullets of its setting '
                    '(share <= setting q20). Sub-strata: B1_coef0 = NNLS coefficient exactly 0 (redundant given the '
                    'other bullets; 11 Original + 11 Best of 32; Combine 32 has no coef-0 bullets because greedy '
                    'selection only adds bullets with positive gain), B2_coef_pos = coef > 0. Dup bullets excluded.',
                    60),
    'C_clean_low_in_halluc': ('CLEAN bullet (no verified wrong/off-topic span) inside a hallucinated readout, with '
                              'Shapley share in the bottom 20% of clean bullets of hallucinated readouts of its '
                              'setting. Dup bullets excluded.', 36),
    'D_clean_high_in_consistent': ('CLEAN bullet inside a consistent readout, with Shapley share in the top 20% of '
                                   'clean bullets of consistent readouts of its setting (control). Dup bullets '
                                   'excluded.', 36),
    'E_disagree': ('Whole-cell disagreement between settings. E1 (24, setting Original): Original hallucinated and '
                   'Best of 32 consistent. E2 (24, setting Combine 32): Original consistent and Combine 32 '
                   'hallucinated. Bullet = one wrong bullet of the hallucinated readout, chosen uniformly with a '
                   'seeded RNG when there are several (every such readout has at least one). Read all settings '
                   '(show_case.py <k> all).', 48),
    'F_wrong_unscored': ('WRONG bullet whose wrong-span text lies past the 32-token AR limit. Only 12 bullets in '
                         'the whole data (7 Original, 1 Best of 32, 4 Combine 32) have ALL their wrong-span text past '
                         'the limit (F1_all_wrong_text_unscored, all taken). The other 12 (F2_most_wrong_text_unscored)'
                         ' are wrong bullets where >= 50% of the wrong-span characters in the bullet lie past the '
                         'limit (39 such bullets exist).', 24),
    'G_offtopic': ('OFF-TOPIC bullet (overlaps a verified off-topic span and no wrong span), in an off_topic or '
                   'hallucinated readout. Dup bullets excluded.', 24),
}


def case_out(c, b=None, slot=None):
    keep = ['k', 'setting', 'bullet', 'stratum', 'substratum', 'item', 'source', 'L', 'n', 'label', 'readout', 'fve',
            'share', 'shap', 'solo', 'drop', 'coef', 'truncated', 'unscored_frac']
    d = {x: c[x] for x in keep}
    d['position'] = c['bullet'] + 1
    d['labels_all_settings'] = cells[c['k']]['labels']
    d['batch'], d['slot'] = b, slot
    return d


summary = {
    'by_stratum_setting': {st: dict(collections.Counter(SHORT[c['setting']] for c in picked if c['stratum'] == st))
                           for st in DEFS},
    'by_substratum': dict(collections.Counter(c['substratum'] for c in picked)),
    'by_setting': dict(collections.Counter(SHORT[c['setting']] for c in picked)),
    'by_layer': dict(sorted(collections.Counter(c['L'] for c in picked).items())),
    'by_source': dict(collections.Counter(c['source'] for c in picked)),
    'by_stratum_layer': {st: dict(sorted(collections.Counter(c['L'] for c in picked if c['stratum'] == st).items()))
                         for st in DEFS},
    'by_stratum_source': {st: dict(collections.Counter(c['source'] for c in picked if c['stratum'] == st))
                          for st in DEFS},
    'by_stratum_position': {st: dict(sorted(collections.Counter(c['bullet'] + 1 for c in picked
                                                                if c['stratum'] == st).items())) for st in DEFS},
    'distinct_items': len({c['item'] for c in picked}),
    'max_cases_per_item_per_stratum': {st: max(collections.Counter(c['item'] for c in picked
                                                                   if c['stratum'] == st).values()) for st in DEFS},
    'same_item_twice_in_a_batch': dup_items_in_batch,
}
doc = {
    'seed': SEED,
    'generated': '2026-10-15',
    'data': {'index': os.path.join(DATA, 'index.json'), 'items': os.path.join(DATA, 'items')},
    'viewer': ('${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B '
               '${OLENS_SCRATCH}/olens-bullet-fve/reading/show_case.py <k> <setting|all> '
               '[--bullet I] [--blind] [--focus-setting S]'),
    'bullet_index': '0-based index into the setting\'s bullet list (show_case.py prints it as b<I>; position = I+1)',
    'strata': [{'name': s, 'definition': d, 'n': n} for s, (d, n) in DEFS.items()],
    'thresholds': thr,
    'pool_sizes': {
        'A_wrong_high': {SHORT[s]: sum(1 for r in wrong if r['setting'] == s and ok_bullet(r)
                                       and r['share'] >= thr[s]['wrong_q80']) for s in SIDS},
        'B_wrong_low': {SHORT[s]: sum(1 for r in b_pool if r['setting'] == s) for s in SIDS},
        'B_wrong_low_coef0': {SHORT[s]: sum(1 for r in b_pool if r['setting'] == s and r['coef'] == 0) for s in SIDS},
        'E1': len(e1), 'E2': len(e2), 'F1': len(f_strict), 'F2': len(f_part),
        'G_offtopic': {SHORT[s]: sum(1 for r in rows if r['setting'] == s and r['label'] == 'o' and ok_bullet(r))
                       for s in SIDS},
    },
    'summary': summary,
    'batches': [[{'k': c['k'], 'setting': c['setting'], 'bullet': c['bullet'], 'stratum': c['stratum']} for c in bb]
                for bb in batches],
    'cases': [case_out(c, b, i) for b, bb in enumerate(batches) for i, c in enumerate(bb)],
}
with open(OUT, 'w') as f:
    json.dump(doc, f, indent=1, ensure_ascii=False)
print(json.dumps(summary, indent=1))
print(json.dumps(doc['pool_sizes']))
print(json.dumps(thr, indent=1))
