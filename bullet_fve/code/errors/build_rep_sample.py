"""Representative random sample (seed 1) of 240 verified-wrong bullets, 20 batches x 12.

Population: every bullet labelled 'w' (overlaps a verified wrong span) in the three scored settings
(Original capped_n1-n1, Best of 32 best_n_exact-n32, Combine 32 pooled_greedy_swap-n32), pooled.
Excluded: the 288 (k, setting, bullet) cases of reading/sample.json, plus any bullet whose text is identical to a
sample.json case bullet in the same cell (the same text already read in the same context under another setting).

Design (as close to uniform-over-bullets as a cap of 2 per chat allows):
  every eligible bullet in chat c gets inclusion probability pi_c = min(2, lam * n_c) / n_c, where n_c is the
  chat's number of eligible wrong bullets and lam solves sum_c min(2, lam * n_c) = 240. For chats below the cap
  pi_c = lam (exactly uniform); chats whose share would exceed 2 are capped at 2 picks. Chat pick counts are drawn
  by systematic sampling over a seeded random chat order (each chat gets floor or ceil of its expected count;
  total exactly 240), then bullets are drawn uniformly without replacement inside the chat (re-drawing if two
  picks would be the same bullet text in the same cell). A naive "shuffle and take, skipping chats at the cap"
  would fill the cap in almost every chat (240 of 298 slots) and make the sample nearly chat-uniform, which
  would shift the source mix from 65% lmsys to ~50%.
Batches: picks are dealt greedily (sorted by source, setting, layer; seeded tie-breaking) to the open batch with the
fewest cases of the same chat, setting, layer and source, so batches have similar mixes and no chat repeats inside
a batch; order inside each batch is shuffled.

Writes errors/rep_sample.json. Run:
  ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B build_rep_sample.py
"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
READING = os.path.join(os.path.dirname(HERE), 'reading')
sys.path.insert(0, READING)
from bullet_table import DATA, SIDS, load_rows  # noqa: E402

OUT = os.path.join(HERE, 'rep_sample.json')
SEED = 1
N_TOTAL, N_BATCH, BATCH_SIZE, CAP = 240, 20, 12, 2
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
PAGE = 'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3'
rng = random.Random(SEED)

rows, cells = load_rows()

_items = {}


def item_json(item_id):
    if item_id not in _items:
        with open(os.path.join(DATA, 'items', item_id + '.json')) as f:
            _items[item_id] = json.load(f)
    return _items[item_id]


def u16(text, a, b):
    return text.encode('utf-16-le')[2 * a:2 * b].decode('utf-16-le')


def bullet_text(k, sid, j):
    item = k.rsplit('.', 2)[0]
    s = item_json(item)['cells'][k]['settings'][sid]
    b = s['bullets'][j]
    return u16(s['text'], b['start'], b['end']).strip()


def wrong_spans_in(k, sid, j):
    item = k.rsplit('.', 2)[0]
    s = item_json(item)['cells'][k]['settings'][sid]
    return [{'text': sp['text'], 'why': sp['why']} for sp in s['spans']
            if sp['verified'] and sp['type'] == 'wrong' and j in (sp.get('bullets') or [])]


# ----------------------------------------------------------------------------- population and exclusions
with open(os.path.join(READING, 'sample.json')) as f:
    prev = json.load(f)
prev_keys = {(c['k'], c['setting'], c['bullet']) for c in prev['cases']}
assert len(prev_keys) == 288
prev_text = {(c['k'], bullet_text(c['k'], c['setting'], c['bullet'])) for c in prev['cases']}

wrong = [r for r in rows if r['label'] == 'w']
for r in wrong:
    r['text'] = bullet_text(r['k'], r['setting'], r['bullet'])
excl_case = [r for r in wrong if (r['k'], r['setting'], r['bullet']) in prev_keys]
excl_text = [r for r in wrong if (r['k'], r['setting'], r['bullet']) not in prev_keys
             and (r['k'], r['text']) in prev_text]
elig = [r for r in wrong if (r['k'], r['setting'], r['bullet']) not in prev_keys and (r['k'], r['text']) not in prev_text]
by_chat = collections.defaultdict(list)
for r in elig:
    by_chat[r['item']].append(r)
chats = sorted(by_chat)
n_c = {c: len(by_chat[c]) for c in chats}
assert all(n >= CAP for n in n_c.values())

# ----------------------------------------------------------------------------- water-filling inclusion rates
lo, hi = 0.0, 1.0
for _ in range(200):
    lam = (lo + hi) / 2
    if sum(min(CAP, lam * n_c[c]) for c in chats) < N_TOTAL:
        lo = lam
    else:
        hi = lam
lam = hi
expect = {c: min(CAP, lam * n_c[c]) for c in chats}
assert abs(sum(expect.values()) - N_TOTAL) < 1e-6
capped = [c for c in chats if lam * n_c[c] >= CAP]

# ----------------------------------------------------------------------------- systematic sampling of chat counts
order = list(chats)
rng.shuffle(order)
u0 = rng.random()
counts, cum = {}, 0.0
for c in order:
    a, b = cum, cum + expect[c]
    # number of points u0 + i (i = 0, 1, ...) in [a, b)
    first = max(0, int(-(-(a - u0) // 1)))           # ceil(a - u0), at least 0
    m = 0
    while u0 + first + m < b - 1e-12:
        m += 1
    counts[c] = m
    cum = b
assert sum(counts.values()) == N_TOTAL, sum(counts.values())
assert all(counts[c] in (int(expect[c]), int(expect[c]) + 1) or abs(counts[c] - expect[c]) < 1e-9 for c in chats)

# ----------------------------------------------------------------------------- bullets inside each chat
picked = []
for c in order:
    pool = list(by_chat[c])
    rng.shuffle(pool)
    got = []
    for r in pool:
        if len(got) == counts[c]:
            break
        if any(g['k'] == r['k'] and g['text'] == r['text'] for g in got):
            continue
        got.append(r)
    assert len(got) == counts[c]
    for r in got:
        picked.append(dict(r, pi=expect[c] / n_c[c]))
assert len(picked) == N_TOTAL
assert len({(r['k'], r['setting'], r['bullet']) for r in picked}) == N_TOTAL
assert not {(r['k'], r['setting'], r['bullet']) for r in picked} & prev_keys
assert max(collections.Counter(r['item'] for r in picked).values()) <= CAP

# ----------------------------------------------------------------------------- batches
deal = list(picked)
rng.shuffle(deal)
deal.sort(key=lambda r: (r['source'], r['setting'], r['L']))
batches = [[] for _ in range(N_BATCH)]
for r in deal:   # greedy: the open batch with the fewest cases sharing this case's chat / setting / layer / source
    best, best_key = None, None
    for b in range(N_BATCH):
        bb = batches[b]
        if len(bb) >= BATCH_SIZE:
            continue
        key = (10 * sum(x['item'] == r['item'] for x in bb) + 2 * sum(x['setting'] == r['setting'] for x in bb)
               + 1 * sum(x['L'] == r['L'] for x in bb) + 1 * sum(x['source'] == r['source'] for x in bb)
               + 0.5 * len(bb), rng.random())
        if best_key is None or key < best_key:
            best, best_key = b, key
    batches[best].append(r)


def n_dup(bb):
    return len(bb) - len({r['item'] for r in bb})


for b in range(N_BATCH):
    for _ in range(10):
        if not n_dup(batches[b]):
            break
        seen, bad = set(), None
        for r in batches[b]:
            if r['item'] in seen:
                bad = r
            seen.add(r['item'])
        done = False
        for b2 in rng.sample(range(N_BATCH), N_BATCH):
            if b2 == b or done:
                continue
            for r2 in batches[b2]:
                if (r2['source'], r2['setting']) != (bad['source'], bad['setting']):
                    continue
                nb = [x for x in batches[b] if x is not bad] + [r2]
                nb2 = [x for x in batches[b2] if x is not r2] + [bad]
                if n_dup(nb) == 0 and n_dup(nb2) == 0:
                    batches[b], batches[b2] = nb, nb2
                    done = True
                    break
for bb in batches:
    rng.shuffle(bb)
assert all(len(bb) == BATCH_SIZE for bb in batches)
same_chat_in_batch = sum(n_dup(bb) for bb in batches)


# ----------------------------------------------------------------------------- summary
def dist(R, key):
    cnt = collections.Counter(key(r) for r in R)
    n = len(R)
    return {str(x): {'n': cnt[x], 'pct': round(100 * cnt[x] / n, 1)} for x in sorted(cnt)}


def weighted(R, key):
    """Horvitz-Thompson style re-weighting of the sample by 1/pi (what a uniform sample would show)."""
    w = collections.Counter()
    for r in R:
        w[key(r)] += 1 / r['pi']
    tot = sum(w.values())
    return {str(x): round(100 * w[x] / tot, 1) for x in sorted(w)}


keys = {'setting': lambda r: SHORT[r['setting']], 'layer': lambda r: r['L'], 'source': lambda r: r['source'],
        'position': lambda r: r['bullet'] + 1, 'readout_n_bullets': lambda r: r['n'],
        'truncated': lambda r: r['truncated'], 'dup': lambda r: r['dup']}
summary = {
    'population_wrong_bullets': len(wrong),
    'excluded_sample_json_cases': len(excl_case),
    'excluded_same_text_same_cell_as_sample_json': len(excl_text),
    'eligible': len(elig),
    'chats': len(chats),
    'lambda_uniform_inclusion_rate': lam,
    'chats_at_cap': len(capped),
    'eligible_bullets_in_capped_chats_pct': round(100 * sum(n_c[c] for c in capped) / len(elig), 1),
    'picks_per_chat': dict(sorted(collections.Counter(collections.Counter(r['item'] for r in picked).values()).items())),
    'chats_with_0_picks': sum(1 for c in chats if counts[c] == 0),
    'distinct_chats': len({r['item'] for r in picked}),
    'distinct_cells': len({r['k'] for r in picked}),
    'same_chat_twice_in_a_batch': same_chat_in_batch,
    'sample_vs_population': {name: {'population': dist(elig, f), 'sample': dist(picked, f),
                                    'sample_reweighted_1_over_pi_pct': weighted(picked, f)}
                             for name, f in keys.items()},
}

doc = {
    'seed': SEED,
    'generated': '2026-10-15',
    'design': __doc__.split('Writes')[0].strip(),
    'data': {'index': os.path.join(DATA, 'index.json'), 'items': os.path.join(DATA, 'items'),
             'excluded': os.path.join(READING, 'sample.json')},
    'viewer': ('${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B '
               '${OLENS_SCRATCH}/olens-bullet-fve/reading/show_case.py <k> <setting> --bullet <bullet> '
               '[--blind]'),
    'bullet_index': "0-based index into the setting's bullet list (show_case.py prints it as b<I>; position = I+1)",
    'weights_note': ('pi = inclusion probability of the bullet. Unweighted sample counts estimate population rates '
                     'only for chats below the cap; for population-level rates weight each case by 1/pi '
                     '(the reweighted columns in summary show this restores the population mix).'),
    'summary': summary,
    'batches': [[{'k': r['k'], 'setting': r['setting'], 'bullet': r['bullet']} for r in bb] for bb in batches],
    'cases': [{'batch': b, 'slot': i, 'k': r['k'], 'setting': r['setting'], 'setting_name': SHORT[r['setting']],
               'bullet': r['bullet'], 'position': r['bullet'] + 1, 'n_bullets': r['n'], 'item': r['item'],
               'source': r['source'], 'L': r['L'], 'readout_label': r['readout'], 'truncated': r['truncated'],
               'dup': r['dup'], 'pi': round(r['pi'], 6), 'weight': round(1 / r['pi'], 3),
               'bullet_text': r['text'], 'wrong_spans': wrong_spans_in(r['k'], r['setting'], r['bullet']),
               'link': f'{PAGE}#{r["k"]}'}
              for b, bb in enumerate(batches) for i, r in enumerate(bb)],
}
with open(OUT, 'w') as f:
    json.dump(doc, f, indent=1, ensure_ascii=False)
print(json.dumps(summary, indent=1))
