"""Chained intermediates (`chain_intermediates`): does higher per-bullet / per-readout FVE mean CORRECT?

The reverse of the Hallucination (chat) question. A bullet is `hit` when it carries the judge-verified first-ranked
integer and that integer is one of the item's hidden intermediates (labels: bullet_labels.jsonl, MAP.md section 5).
Everything here is exploratory: all questions were inspected before, the labels locate a readout-level verdict
inside bullets by rule, and the text proxies are rough. No judge/API calls; read-only outside this folder.

Inputs (all in this folder unless noted)
  bullet_labels.jsonl        one row per bullet x setting (labels, evidence, judge fields)
  bullet_metrics.jsonl       per-bullet exact Shapley / share / solo / LOO drop / coefficient / dup (metrics_job.py)
  chain_three_settings.jsonl atoms (scored_text = the <=32-token text the vector encodes, sample_index)
  chain_bullet_labels.jsonl  per-cell gold + per-setting judge verdict
  candidates.jsonl           (extract_candidates.py) whole-sample selections of every cell: sample index + FVE
  expansion-v1/judgments/<condition>/chain_intermediates/results.json   saved verdicts of the other whole-sample
                             conditions (best_n_exact-nK, random_complete-nK), used for candidate-level AUROC
  item bank (load.load_bank) prompts, intermediates, answer, start, literals

Outputs
  analysis.json     every number quoted in ANALYSIS.md (with 95% percentile bootstrap intervals)
  read_sample.json  36 reading cases (12 high-share hit, 12 low-share hit, 12 high-share non-hit / wrong-specific)
  examples_analysis.txt  candidate verbatim examples (for choosing the ones quoted in ANALYSIS.md)

Bootstrap: resampling unit = related-question group (42 groups; MAP.md recommends it, the expanded report resamples
whole groups); item-level (120 questions) intervals are also given for the headline rows. 1000 reps, seed 0.

Run (light; ~1 min):
  env -u SLURM_JOB_ID srun --partition=mit_quicktest --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=16G \
    --time=00:15:00 --chdir=${OLENS_SCRATCH}/olens-bullet-fve /usr/bin/env \
    PYTHONPATH=${OLENS_REPO_ROOT}/src \
    ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B tasks/chain_intermediates/analysis.py
"""
from __future__ import annotations

import collections
import json
import math
import random
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import load as L  # noqa: E402  (same folder: item bank, judge mirror, string rules)

SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
OB = SIDS[:2]               # writing order = lens order -> position adjustment
NREP, SEED = 1000, 0
LENMATCH = 0.8              # length-matched pair: shorter scored text >= 80% of the longer one (chars)
JUDG = Path('${OLENS_DATA_ROOT}/expansion-v1/judgments')
OUT_JSON = HERE / 'analysis.json'
OUT_SAMPLE = HERE / 'read_sample.json'
OUT_EX = HERE / 'examples_analysis.txt'

# ============================================================================= load
bank = L.load_bank()
GOLD = {iid: L.item_gold(it) for iid, it in bank.items()}

metrics = {}
with open(HERE / 'bullet_metrics.jsonl') as fh:
    for line in fh:
        r = json.loads(line)
        for sid, s in r['settings'].items():
            for j, b in enumerate(s['bullets']):
                metrics[(r['cell_id'], sid, b['phrase_id'])] = (j, b, s['joint_fve_saved'])

atoms = {}
cells = {}
with open(HERE / 'chain_three_settings.jsonl') as fh:
    for line in fh:
        c = json.loads(line)
        cells[c['cell_id']] = {'item': c['item_id'], 'group': c['group_id'], 'layer': c['layer'],
                               'pos': c['position'], 'split': c['split'], 'token': c['token'], 'settings': {}}
        for sid in SIDS:
            s = c['settings'][sid]
            cells[c['cell_id']]['settings'][sid] = {'fve': s['fve'], 'text': s['text'],
                                                    'samples': sorted({a['sample_index'] for a in s['atoms']}),
                                                    'trace': s['trace'] if sid != 'best_n_exact-n32' else None}
            for j, a in enumerate(s['atoms']):
                atoms[(c['cell_id'], sid, a['source_phrase_id'])] = (j, a)

judge = {}
with open(HERE / 'chain_bullet_labels.jsonl') as fh:
    for line in fh:
        c = json.loads(line)
        for sid in SIDS:
            judge[(c['cell_id'], sid)] = c['settings'][sid]['judge']

rows = []
with open(HERE / 'bullet_labels.jsonl') as fh:
    for line in fh:
        rows.append(json.loads(line))
assert len(rows) == len(metrics) == len(atoms) == 15773

GROUP_IDS = sorted({c['group'] for c in cells.values()})
ITEM_IDS = sorted(bank)
GIX = {g: i for i, g in enumerate(GROUP_IDS)}
IIX = {x: i for i, x in enumerate(ITEM_IDS)}
ITEM_GROUP = {c['item']: c['group'] for c in cells.values()}

# ============================================================================= bullet features
CJKR = '㐀-䶿一-鿿豈-﫿'
CJK_CHAR = re.compile('[' + CJKR + ']')
TOK = re.compile('[' + CJKR + ']|[^\\W_' + CJKR + ']+')
NUMONLY = re.compile(r'^[\s*$`#>_~\\(\[{]*-?\d+(?:\.\d+)?[\s*$`._~\\)\]}]*$')
HAS_EQ = re.compile(r'=|×|÷|\\times|\\div|\d\s*[-+*/x]\s*\d')
LIST_OPEN = re.compile(r'^\W{0,4}\d+[.)]\s+\S')


def toks(s):
    return [t.lower() for t in TOK.findall(s)]


def cjk_frac(s):
    ns = [ch for ch in s if not ch.isspace()]
    return (len(CJK_CHAR.findall(s)) / len(ns)) if ns else 0.0


PROMPT_TOKS = {iid: set(toks(g['prompt'])) for iid, g in GOLD.items()}

for r in rows:
    j, b, jf = metrics[(r['cell_id'], r['setting'], r['phrase_id'])]
    ja, a = atoms[(r['cell_id'], r['setting'], r['phrase_id'])]
    assert j == ja == r['bullet'] and b['cache_key'] == a['cache_key'] == r['cache_key']
    assert abs(jf - r['readout_fve']) < 1e-12
    g = GOLD[r['item_id']]
    scored = a['scored_text'] or ''
    st = toks(scored)
    lead = r['lead_value']
    r.update({
        'sid': r['setting'], 'k': f"{r['item_id']}.L{r['layer']}.p{r['position']}", 'j': r['bullet'],
        'n': r['n_bullets'], 'L': r['layer'], 'gix': GIX[r['group_id']], 'iix': IIX[r['item_id']],
        'share': b['shapley_share'], 'shap': b['shapley'], 'solo': b['solo_fve'], 'drop': b['loo_drop'],
        'coef': b['coefficient'], 'dup': bool(b['dup']), 'scored': scored, 'slen': len(scored),
        'ntok': a['scored_token_count'], 'cjk': cjk_frac(scored),
        'prompt_ov': (sum(t in PROMPT_TOKS[r['item_id']] for t in st) / len(st)) if st else 0.0,
        'number_only': float(bool(NUMONLY.match(r['text'].strip()))),
        'has_eq': float(bool(HAS_EQ.search(scored))),
        'list_open': float(bool(LIST_OPEN.match(scored))),
        'states_value': float(lead is not None),
        'lead_answer': float(lead is not None and lead == g['answer']),
        'lead_gold': float(lead is not None and lead in g['intermediates']),
        'lead_prompt': float(lead is not None and (lead in g['literals'] or lead == g['start'])),
        'coef0': float(b['coefficient'] == 0),
        'is_hit': float(r['label'] == 'hit'), 'is_wrong': float(r['label'] == 'wrong_specific'),
        'is_answer': float(r['label'] == 'answer'),
        'carrier': r['label'] in ('hit', 'answer', 'wrong_specific'),
    })

# position-adjusted percentiles (mid-rank among non-dup bullets of the same setting, layer, list position and
# readout size); *_pa2 pools layers as the Hallucination study did (setting, position, size)
LAB = [r for r in rows if not r['dup']]
for keyf, suf in ((lambda r: (r['sid'], r['L'], r['j'], r['n']), '_pa'), (lambda r: (r['sid'], r['j'], r['n']), '_pa2')):
    grp = collections.defaultdict(list)
    for r in LAB:
        grp[keyf(r)].append(r)
    for gg in grp.values():
        for sc in ('solo', 'share', 'drop'):
            v = np.array([x[sc] for x in gg], dtype=float)
            order = np.sort(v)
            lo = np.searchsorted(order, v, 'left')
            hi = np.searchsorted(order, v, 'right')
            for x, p in zip(gg, (lo + 0.5 * (hi - lo)) / len(v)):
                x[sc + suf] = float(p)
for r in rows:
    if r['dup']:
        for sc in ('solo', 'share', 'drop'):
            r[sc + '_pa'] = r[sc + '_pa2'] = float('nan')

by_ro = collections.defaultdict(list)       # all bullets incl. dup
for r in rows:
    by_ro[(r['cell_id'], r['sid'])].append(r)
by_ro_nd = {k: [b for b in v if not b['dup']] for k, v in by_ro.items()}

# ============================================================================= bootstrap helpers
rng = np.random.default_rng(SEED)
BW = {'group': np.stack([np.bincount(b, minlength=len(GROUP_IDS)) for b in
                         rng.integers(0, len(GROUP_IDS), size=(NREP, len(GROUP_IDS)))]).astype(float),
      'item': np.stack([np.bincount(b, minlength=len(ITEM_IDS)) for b in
                        rng.integers(0, len(ITEM_IDS), size=(NREP, len(ITEM_IDS)))]).astype(float)}


def _unit_ix(item_id, unit):
    return GIX[ITEM_GROUP[item_id]] if unit == 'group' else IIX[item_id]


def agg(triples, unit='group'):
    """triples: (item_id, num, den) -> per-unit arrays"""
    nu = len(GROUP_IDS) if unit == 'group' else len(ITEM_IDS)
    num, den = np.zeros(nu), np.zeros(nu)
    for iid, a, b in triples:
        ix = _unit_ix(iid, unit)
        num[ix] += a
        den[ix] += b
    return num, den


def ratio_ci(triples, unit='group', nd=4):
    triples = list(triples)
    num, den = agg(triples, unit)
    if den.sum() == 0:
        return {'est': None, 'lo': None, 'hi': None, 'n': 0, 'units': 0}
    W = BW[unit]
    with np.errstate(invalid='ignore', divide='ignore'):
        b = (W @ num) / (W @ den)
    b = b[np.isfinite(b)]
    return {'est': round(float(num.sum() / den.sum()), nd), 'lo': round(float(np.percentile(b, 2.5)), nd),
            'hi': round(float(np.percentile(b, 97.5)), nd), 'n': int(round(den.sum())),
            'units': int((den > 0).sum())}


def diff_ci(t1, t2, unit='group', nd=4):
    n1, d1 = agg(list(t1), unit)
    n2, d2 = agg(list(t2), unit)
    W = BW[unit]
    with np.errstate(invalid='ignore', divide='ignore'):
        b = (W @ n1) / (W @ d1) - (W @ n2) / (W @ d2)
    b = b[np.isfinite(b)]
    return {'est': round(float(n1.sum() / d1.sum() - n2.sum() / d2.sum()), nd),
            'lo': round(float(np.percentile(b, 2.5)), nd), 'hi': round(float(np.percentile(b, 97.5)), nd)}


def win(a, b):
    return 1.0 if a > b else (0.5 if a == b else 0.0)


def lenmatch(a, b):
    return min(a['slen'], b['slen']) / max(1, a['slen'], b['slen']) >= LENMATCH


def pair_triples(sids, score, A, B, match=None, ro_sel=None, dup=False):
    """same-readout pairs (a in A, b in B): (item, win(score a, score b), 1)"""
    out = []
    src = by_ro if dup else by_ro_nd
    for (cid, sid), bs in src.items():
        if sid not in sids or (ro_sel and not ro_sel(cid, sid, bs)):
            continue
        As = [x for x in bs if A(x)]
        Bs = [x for x in bs if B(x)]
        for a in As:
            for b in Bs:
                if a is b or (match and not match(a, b)):
                    continue
                out.append((a['item_id'], win(a[score], b[score]), 1.0))
    return out


def pr(sids, score, A, B, **kw):
    unit = kw.pop('unit', 'group')
    return ratio_ci(pair_triples(sids, score, A, B, **kw), unit)


IS = lambda lab: (lambda r: r['label'] == lab)  # noqa: E731
NOT = lambda lab: (lambda r: r['label'] != lab)  # noqa: E731
out = {'meta': {
    'family': 'chain_intermediates (Chained intermediates)', 'n_items': len(ITEM_IDS), 'n_groups': len(GROUP_IDS),
    'n_cells': len(cells), 'n_bullets': len(rows), 'n_dup_bullets': sum(r['dup'] for r in rows),
    'bootstrap': {'unit': 'related-question group (42); item-level (120) where marked', 'reps': NREP, 'seed': SEED,
                  'interval': 'percentile 2.5-97.5'},
    'pair_rate': 'P(score of the first group > score of the second) over same-readout pairs, ties 1/2; '
                 '0.5 = no separation. Dup-vector bullets excluded unless stated.',
    'position_adjusted': '*_pa = mid-rank percentile among non-dup bullets of the same setting, layer, list '
                         'position and readout size (Original, Best of 32 only); *_pa2 = same without layer '
                         '(Hallucination definition)',
    'length_matched': f'shorter scored text >= {LENMATCH:.0%} of the longer (characters of the <=32-token text)',
    'labels': 'primary label (bullet_labels.jsonl): hit / answer / wrong_specific / miss; see MAP.md section 5'}}

# ============================================================================= T1 bullet level
t1 = {}
for sid in SIDS:
    S = SHORT[sid]
    d = {}
    mixed = lambda cid, s, bs: any(b['label'] == 'hit' for b in bs) and any(b['label'] != 'hit' for b in bs)  # noqa
    for sc in ('share', 'solo', 'drop'):
        d[f'hit_vs_nonhit_{sc}_raw'] = pr([sid], sc, IS('hit'), NOT('hit'))
        if sid in OB:
            d[f'hit_vs_nonhit_{sc}_posadj'] = pr([sid], sc + '_pa', IS('hit'), NOT('hit'))
            d[f'hit_vs_nonhit_{sc}_posadj_pooled_layers'] = pr([sid], sc + '_pa2', IS('hit'), NOT('hit'))
    sc_main = 'solo_pa' if sid in OB else 'solo'
    sh_main = 'share_pa' if sid in OB else 'share'
    d['headline_share_item_level'] = pr([sid], sh_main, IS('hit'), NOT('hit'), unit='item')
    d['headline_solo_item_level'] = pr([sid], sc_main, IS('hit'), NOT('hit'), unit='item')
    d['hit_vs_nonhit_solo_lenmatched'] = pr([sid], 'solo', IS('hit'), NOT('hit'), match=lenmatch)
    d['hit_vs_nonhit_share_lenmatched'] = pr([sid], 'share', IS('hit'), NOT('hit'), match=lenmatch)
    if sid in OB:
        d['hit_vs_nonhit_solo_posadj_lenmatched'] = pr([sid], 'solo_pa', IS('hit'), NOT('hit'), match=lenmatch)
    d['hit_longer_than_nonhit_scored_chars'] = pr([sid], 'slen', IS('hit'), NOT('hit'))
    if sid in OB:
        d['hit_later_than_nonhit'] = pr([sid], 'j', IS('hit'), NOT('hit'))
    d['hit_vs_nonhit_solo_incl_dup'] = pr([sid], 'solo', IS('hit'), NOT('hit'), dup=True)
    d['n_mixed_hit_readouts'] = sum(1 for (cid, s), bs in by_ro_nd.items() if s == sid and mixed(cid, s, bs))
    # carrier vs miss, by the kind of value carried (the control: is FVE preferring the CORRECT value, or any
    # bullet that puts a computed value forward?)
    for lab in ('hit', 'wrong_specific', 'answer'):
        d[f'carrier_vs_miss[{lab}]_{sh_main}'] = pr([sid], sh_main, IS(lab), IS('miss'))
        d[f'carrier_vs_miss[{lab}]_{sc_main}'] = pr([sid], sc_main, IS(lab), IS('miss'))
        d[f'carrier_vs_miss[{lab}]_solo_lenmatched'] = pr([sid], 'solo', IS(lab), IS('miss'), match=lenmatch)
    d['carrier_vs_miss_hit_minus_wrong_specific_' + sc_main] = diff_ci(
        pair_triples([sid], sc_main, IS('hit'), IS('miss')), pair_triples([sid], sc_main, IS('wrong_specific'), IS('miss')))
    d['carrier_vs_miss_hit_minus_wrong_specific_' + sh_main] = diff_ci(
        pair_triples([sid], sh_main, IS('hit'), IS('miss')), pair_triples([sid], sh_main, IS('wrong_specific'), IS('miss')))
    # wrong_specific by role
    for role in ('near', 'other', 'literal', 'start'):
        d[f'carrier_vs_miss[wrong_specific:{role}]_{sc_main}'] = pr(
            [sid], sc_main, lambda r, role=role: r['label'] == 'wrong_specific' and r['wrong_role'] == role, IS('miss'))
    # judge-free string labels, within readout (all readouts): the bullet's own lead value
    st = lambda *v: (lambda r: r['label_stated'] in v)  # noqa: E731
    d['stated_intermediate_vs_stated_other_' + sc_main] = pr([sid], sc_main, st('states_intermediate'), st('states_other'))
    d['stated_intermediate_vs_stated_other_solo_lenmatched'] = pr([sid], 'solo', st('states_intermediate'),
                                                                  st('states_other'), match=lenmatch)
    d['stated_or_derived_intermediate_vs_stated_other_' + sc_main] = pr(
        [sid], sc_main, st('states_intermediate', 'derives_intermediate'), st('states_other'))
    d['stated_answer_vs_stated_other_' + sc_main] = pr([sid], sc_main, st('states_answer'), st('states_other'))
    d['stated_answer_vs_stated_other_solo_lenmatched'] = pr([sid], 'solo', st('states_answer'), st('states_other'),
                                                            match=lenmatch)
    d['stated_intermediate_vs_stated_answer_' + sc_main] = pr([sid], sc_main, st('states_intermediate'),
                                                             st('states_answer'))
    d['stated_any_value_vs_states_none_' + sc_main] = pr([sid], sc_main, lambda r: r['label_stated'] != 'states_none',
                                                         st('states_none'))
    d['stated_other_vs_states_none_' + sc_main] = pr([sid], sc_main, st('states_other'), st('states_none'))
    d['stated_intermediate_vs_states_none_' + sc_main] = pr([sid], sc_main, st('states_intermediate'),
                                                            st('states_none'))
    # sensitivity labels
    d['strict_anchor_hit_vs_nonhit_' + sc_main] = pr([sid], sc_main, lambda r: r['label_anchor'] == 'hit',
                                                     lambda r: r['label_anchor'] != 'hit')
    d['loose_contains_hit_vs_nonhit_' + sc_main] = pr([sid], sc_main, lambda r: r['label_contains'] == 'hit',
                                                      lambda r: r['label_contains'] != 'hit')
    d['named_gold_any_rank_vs_rest_' + sc_main] = pr([sid], sc_main,
                                                    lambda r: r['label_named'] in ('top_hit', 'gold_named'),
                                                    lambda r: r['label_named'] not in ('top_hit', 'gold_named'))
    d['hit_vs_nonhit_excl_ambiguous_anchor_' + sc_main] = pr(
        [sid], sc_main, lambda r: r['label'] == 'hit' and not r['ambiguous_anchor'], NOT('hit'))
    # 'clean' hits: the bullet's own lead / derived value is the intermediate (drops quote-anchored bullets whose
    # lead is another number, e.g. '15$ (half of 9, then ceiling) | The new average is 5')
    d['clean_hit_vs_nonhit_' + sc_main] = pr(
        [sid], sc_main, lambda r: r['label'] == 'hit' and r['label_stated'] in ('states_intermediate',
                                                                              'derives_intermediate'), NOT('hit'))
    d['clean_hit_vs_nonhit_solo_lenmatched'] = pr(
        [sid], 'solo', lambda r: r['label'] == 'hit' and r['label_stated'] in ('states_intermediate',
                                                                             'derives_intermediate'), NOT('hit'),
        match=lenmatch)
    # without bare-number bullets on either side (they score near zero whatever number they carry)
    d['hit_vs_nonhit_no_number_only_' + sc_main] = pr(
        [sid], sc_main, lambda r: r['label'] == 'hit' and not r['number_only'],
        lambda r: r['label'] != 'hit' and not r['number_only'])
    d['hit_vs_nonhit_no_number_only_solo_lenmatched'] = pr(
        [sid], 'solo', lambda r: r['label'] == 'hit' and not r['number_only'],
        lambda r: r['label'] != 'hit' and not r['number_only'], match=lenmatch)
    d['wrong_specific_vs_miss_no_number_only_' + sc_main] = pr(
        [sid], sc_main, lambda r: r['label'] == 'wrong_specific' and not r['number_only'],
        lambda r: r['label'] == 'miss' and not r['number_only'])
    if sid in OB:  # non-redundant bullets only (coef > 0), as in the Hallucination T4
        d['hit_vs_nonhit_solo_pa_nonredundant_only'] = pr(
            [sid], 'solo_pa', lambda r: r['label'] == 'hit' and r['coef'] > 0,
            lambda r: r['label'] != 'hit' and r['coef'] > 0)
        d['hit_vs_nonhit_drop_nonredundant_only'] = pr(
            [sid], 'drop', lambda r: r['label'] == 'hit' and r['coef'] > 0,
            lambda r: r['label'] != 'hit' and r['coef'] > 0)
    # by layer band and depth
    for name, sel in (('L20-36', lambda L: L <= 36), ('L40-48', lambda L: 40 <= L <= 48),
                      ('L52-60', lambda L: L >= 52)):
        d[f'hit_vs_nonhit_{sc_main}_{name}'] = pr([sid], sc_main, IS('hit'), NOT('hit'),
                                                  ro_sel=lambda cid, s, bs, sel=sel: sel(cells[cid]['layer']))
    for dep in (2, 3):
        d[f'hit_vs_nonhit_{sc_main}_depth{dep}'] = pr([sid], sc_main, IS('hit'), NOT('hit'),
                                                      ro_sel=lambda cid, s, bs, dep=dep: GOLD[cells[cid]['item']]['depth'] == dep)
    # top-share bullet of a mixed hit readout is a hit, vs chance (= mean hit fraction)
    tops, chance = [], []
    for (cid, s), bs in by_ro_nd.items():
        if s != sid or not mixed(cid, s, bs):
            continue
        top = max(bs, key=lambda b: b['share'])
        tops.append((cells[cid]['item'], float(top['label'] == 'hit'), 1.0))
        chance.append((cells[cid]['item'], sum(b['label'] == 'hit' for b in bs) / len(bs), 1.0))
    d['top_share_bullet_is_hit'] = ratio_ci(tops)
    d['top_share_bullet_is_hit_chance'] = ratio_ci(chance)
    d['top_share_minus_chance'] = diff_ci(tops, chance)
    t1[S] = d

# hit vs wrong_specific: never in the same readout under the primary label (a readout's carriers share one class),
# so compare across the three readouts of the same cell with SOLO FVE (bullet vs the cell's activation; does not
# depend on siblings). Identical vectors (same cache_key) are skipped.
by_cell = collections.defaultdict(list)
for r in LAB:
    by_cell[r['cell_id']].append(r)


def cross_cell(score, A, B, match=None, unit='group'):
    acc = []
    for cid, bs in by_cell.items():
        As = {}
        for x in bs:
            if A(x):
                As.setdefault(x['cache_key'], x)
        Bs = {}
        for x in bs:
            if B(x):
                Bs.setdefault(x['cache_key'], x)
        for ka, a in As.items():
            for kb, b in Bs.items():
                if ka == kb or (match and not match(a, b)):
                    continue
                acc.append((a['item_id'], win(a[score], b[score]), 1.0))
    return ratio_ci(acc, unit)


t1['cross_setting_same_cell'] = {
    'hit_vs_wrong_specific_solo': cross_cell('solo', IS('hit'), IS('wrong_specific')),
    'hit_vs_wrong_specific_solo_item_level': cross_cell('solo', IS('hit'), IS('wrong_specific'), unit='item'),
    'hit_vs_wrong_specific_solo_lenmatched': cross_cell('solo', IS('hit'), IS('wrong_specific'), match=lenmatch),
    'hit_vs_answer_solo': cross_cell('solo', IS('hit'), IS('answer')),
    'hit_vs_answer_solo_lenmatched': cross_cell('solo', IS('hit'), IS('answer'), match=lenmatch),
    'answer_vs_wrong_specific_solo': cross_cell('solo', IS('answer'), IS('wrong_specific')),
    'hit_vs_miss_solo': cross_cell('solo', IS('hit'), IS('miss')),
    'wrong_specific_vs_miss_solo': cross_cell('solo', IS('wrong_specific'), IS('miss')),
    'note': 'pairs pooled over the three settings of one cell; bullets deduplicated by cache_key per class; '
            'raw solo FVE (position adjustment is not defined across settings)'}

# template-matched filler test: two distinct bullets of one cell (any settings) whose scored text is identical after
# masking every digit run, but whose lead values differ. Does the one whose lead is a hidden intermediate win?
MASK = re.compile(r'\d+')


def tmpl(r):
    return re.sub(r'\s+', ' ', MASK.sub('#', r['scored'])).strip()


tp = collections.defaultdict(list)
tp_examples = []
for cid, bs in by_cell.items():
    uniq = {}
    for x in bs:
        uniq.setdefault(x['cache_key'], x)
    xs = list(uniq.values())
    g = GOLD[cells[cid]['item']]
    for a in xs:
        for b in xs:
            if a is b or a['lead_value'] is None or b['lead_value'] is None or a['lead_value'] == b['lead_value']:
                continue
            if tmpl(a) != tmpl(b):
                continue
            ag, bg = a['lead_value'] in g['intermediates'], b['lead_value'] in g['intermediates']
            aa, ba = a['lead_value'] == g['answer'], b['lead_value'] == g['answer']
            if ag and not bg and not ba:
                tp['gold_vs_other'].append((a['item_id'], win(a['solo'], b['solo']), 1.0))
                tp['gold_vs_other_diff'].append((a['item_id'], a['solo'] - b['solo'], 1.0))
                tp['gold_vs_other_numonly'].append((a['item_id'], win(a['solo'], b['solo']), 1.0)) if (
                    a['number_only'] and b['number_only']) else None
                if len(tp_examples) < 400:
                    tp_examples.append((cid, a, b))
            if aa and not ba and not bg:
                tp['answer_vs_other'].append((a['item_id'], win(a['solo'], b['solo']), 1.0))
                tp['answer_vs_other_diff'].append((a['item_id'], a['solo'] - b['solo'], 1.0))
            if ag and ba:
                tp['gold_vs_answer'].append((a['item_id'], win(a['solo'], b['solo']), 1.0))
            if not (ag or aa or bg or ba):
                tp['other_vs_other_absdiff'].append((a['item_id'], abs(a['solo'] - b['solo']) / 2, 0.5))
t1['template_matched_filler'] = {k: ratio_ci(v, nd=5) for k, v in tp.items()}
NO = [r for r in LAB if r['number_only']]
t1['number_only_bullets'] = {
    'n': len(NO), 'share_of_bullets': round(len(NO) / len(LAB), 4),
    'mean_solo_number_only': ratio_ci([(r['item_id'], r['solo'], 1.0) for r in NO], nd=5),
    'mean_solo_other_bullets': ratio_ci([(r['item_id'], r['solo'], 1.0) for r in LAB if not r['number_only']], nd=5),
    'mean_solo_number_only_lead_gold': ratio_ci([(r['item_id'], r['solo'], 1.0) for r in NO if r['lead_gold']], nd=5),
    'mean_solo_number_only_lead_answer': ratio_ci([(r['item_id'], r['solo'], 1.0) for r in NO if r['lead_answer']],
                                                  nd=5),
    'mean_solo_number_only_lead_other': ratio_ci([(r['item_id'], r['solo'], 1.0) for r in NO if r['states_value'] and
                                                  not r['lead_gold'] and not r['lead_answer']], nd=5),
    'p_label_hit_among_number_only': ratio_ci([(r['item_id'], r['is_hit'], 1.0) for r in NO]),
    'p_number_only_among_hits': ratio_ci([(r['item_id'], r['number_only'], 1.0) for r in LAB if r['label'] == 'hit'])}


# frame-matched pairs: distinct bullets of one cell (any setting, deduplicated by cache_key) whose digit-masked scored
# text shares its first FRAME_N word tokens and whose scored lengths are within 20%; leads differ.
FRAME_N = 4


def frame(r):
    t = toks(MASK.sub(' # ', r['scored']))
    return tuple(t[:FRAME_N]) if len(t) >= FRAME_N else None


fm = collections.defaultdict(list)
fm_examples = []
for cid, bs in by_cell.items():
    uniq = {}
    for x in bs:
        uniq.setdefault(x['cache_key'], x)
    xs = [x for x in uniq.values() if x['lead_value'] is not None and not x['number_only'] and frame(x)]
    g = GOLD[cells[cid]['item']]
    for a in xs:
        for b in xs:
            if a is b or a['lead_value'] == b['lead_value'] or frame(a) != frame(b) or not lenmatch(a, b):
                continue
            ag, bg = a['lead_value'] in g['intermediates'], b['lead_value'] in g['intermediates']
            aa, ba = a['lead_value'] == g['answer'], b['lead_value'] == g['answer']
            if ag and not bg and not ba:
                fm['gold_vs_other'].append((a['item_id'], win(a['solo'], b['solo']), 1.0))
                fm['gold_vs_other_diff'].append((a['item_id'], a['solo'] - b['solo'], 1.0))
                fm_examples.append((cid, a, b))
            if aa and not ba and not bg:
                fm['answer_vs_other'].append((a['item_id'], win(a['solo'], b['solo']), 1.0))
                fm['answer_vs_other_diff'].append((a['item_id'], a['solo'] - b['solo'], 1.0))
            if ag and ba:
                fm['gold_vs_answer'].append((a['item_id'], win(a['solo'], b['solo']), 1.0))
            if not (ag or aa or bg or ba):
                fm['other_vs_other_absdiff'].append((a['item_id'], abs(a['solo'] - b['solo']) / 2, 0.5))
t1['frame_matched_filler'] = {k: ratio_ci(v, nd=5) for k, v in fm.items()}
t1['frame_matched_filler']['note'] = (
    f'pairs of distinct non-number-only bullets of one cell (any setting, deduplicated by cache_key) whose digit-masked '
    f'scored text has the same first {FRAME_N} word tokens and whose scored lengths are within 20%; leads differ '
    '(string rule). *_diff = mean solo difference (first minus second); other_vs_other_absdiff = mean |solo '
    'difference| of frame twins neither of which leads with an intermediate or the answer.')
t1['template_matched_filler']['note'] = (
    'pairs of distinct bullets of one cell (any setting, deduplicated by cache_key) with identical scored text after '
    'masking digit runs and different lead values (string rule). *_diff = mean solo difference; '
    'other_vs_other_absdiff = mean |solo difference| between two template twins neither of which states an '
    'intermediate or the answer (noise floor). Ordered pairs; each unordered pair counted once for the class tests.')
out['T1_bullet_level'] = t1

# ============================================================================= T2 readout level
t2 = {}
# readout hit rate and mean FVE by layer (layer confound)
lay = {}
for sid in SIDS:
    lay[SHORT[sid]] = {}
    for Lr in L.LAYERS:
        cs = [cid for cid, c in cells.items() if c['layer'] == Lr]
        lay[SHORT[sid]][Lr] = {'hit_readouts': sum(judge[(cid, sid)]['kind'] == 'hit' for cid in cs),
                               'mean_fve': round(float(np.mean([cells[cid]['settings'][sid]['fve'] for cid in cs])), 4)}
t2['by_layer'] = lay

# across items within (setting, layer): AUROC of joint FVE, hit vs non-hit readouts
auc_layer = {}
for sid in SIDS:
    acc = []
    for Lr in L.LAYERS:
        cs = [cid for cid, c in cells.items() if c['layer'] == Lr]
        H = [cid for cid in cs if judge[(cid, sid)]['kind'] == 'hit']
        N = [cid for cid in cs if judge[(cid, sid)]['kind'] != 'hit']
        for h in H:
            for n_ in N:
                acc.append((cells[h]['item'], win(cells[h]['settings'][sid]['fve'], cells[n_]['settings'][sid]['fve']), 1.0))
    auc_layer[SHORT[sid]] = ratio_ci(acc)
t2['auroc_fve_hit_vs_nonhit_within_layer_across_items'] = auc_layer


def rankcorr(x, y):
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    return round(float(np.corrcoef(rx, ry)[0, 1]), 3)


# item-level confound behind the across-item AUROC: items with small intermediates pass more and have lower FVE
conf = {}
for sid in SIDS:
    mf = {i: np.mean([c['settings'][sid]['fve'] for c in cells.values() if c['item'] == i]) for i in ITEM_IDS}
    nh = {i: sum(judge[(cid, sid)]['kind'] == 'hit' for cid, c in cells.items() if c['item'] == i) for i in ITEM_IDS}
    mi = {i: min(GOLD[i]['intermediates']) for i in ITEM_IDS}
    conf[SHORT[sid]] = {
        'spearman_item_min_intermediate_vs_item_mean_fve': rankcorr([mi[i] for i in ITEM_IDS], [mf[i] for i in ITEM_IDS]),
        'spearman_item_min_intermediate_vs_hit_layers': rankcorr([mi[i] for i in ITEM_IDS], [nh[i] for i in ITEM_IDS]),
        'spearman_item_mean_fve_vs_hit_layers': rankcorr([mf[i] for i in ITEM_IDS], [nh[i] for i in ITEM_IDS])}
    for name, sel in (('min intermediate <= 9', lambda i: mi[i] <= 9), ('min intermediate >= 10', lambda i: mi[i] >= 10)):
        acc = []
        for Lr in L.LAYERS:
            cs = [cid for cid, c in cells.items() if c['layer'] == Lr and sel(c['item'])]
            H = [cid for cid in cs if judge[(cid, sid)]['kind'] == 'hit']
            N = [cid for cid in cs if judge[(cid, sid)]['kind'] != 'hit']
            acc += [(cells[h]['item'], win(cells[h]['settings'][sid]['fve'], cells[n_]['settings'][sid]['fve']), 1.0)
                    for h in H for n_ in N]
        conf[SHORT[sid]][f'auroc_within_layer_across_items[{name}]'] = ratio_ci(acc)
    # readouts without any bare-number bullet (bare numbers score ~0 and are common in terse readouts)
    terse = {cid: any(b['number_only'] for b in by_ro[(cid, sid)]) for cid in cells}
    acc = []
    for Lr in L.LAYERS:
        cs = [cid for cid, c in cells.items() if c['layer'] == Lr and not terse[cid]]
        H = [cid for cid in cs if judge[(cid, sid)]['kind'] == 'hit']
        N = [cid for cid in cs if judge[(cid, sid)]['kind'] != 'hit']
        acc += [(cells[h]['item'], win(cells[h]['settings'][sid]['fve'], cells[n_]['settings'][sid]['fve']), 1.0)
                for h in H for n_ in N]
    conf[SHORT[sid]]['auroc_within_layer_across_items[no bare-number bullet in readout]'] = ratio_ci(acc)
    conf[SHORT[sid]]['p_readout_has_bare_number_bullet'] = {
        'hit': round(float(np.mean([terse[cid] for cid in cells if judge[(cid, sid)]['kind'] == 'hit'])), 3),
        'non_hit': round(float(np.mean([terse[cid] for cid in cells if judge[(cid, sid)]['kind'] != 'hit'])), 3)}
t2['item_confound'] = conf

# within cell across the three settings
acc = []
for cid, c in cells.items():
    for i, s1 in enumerate(SIDS):
        for s2 in SIDS[i + 1:]:
            h1, h2 = judge[(cid, s1)]['kind'] == 'hit', judge[(cid, s2)]['kind'] == 'hit'
            if h1 == h2 or c['settings'][s1]['text'] == c['settings'][s2]['text']:
                continue
            hs, ns = (s1, s2) if h1 else (s2, s1)
            acc.append((c['item'], win(c['settings'][hs]['fve'], c['settings'][ns]['fve']), 1.0))
t2['auroc_fve_within_cell_across_settings'] = ratio_ci(acc)
t2['auroc_fve_within_cell_across_settings_item_level'] = ratio_ci(acc, 'item')

# candidate level: every whole-sample readout judged by some condition (capped_n1, best_n_exact-nK,
# random_complete-nK); FVE = that sample's exact joint FVE (== best_n_exact-n32 trace, verified)
COND_WHOLE = ['capped_n1-n1'] + [f'best_n_exact-n{k}' for k in (1, 2, 4, 8, 16, 32)] + \
             [f'random_complete-n{k}' for k in (1, 2, 4, 8, 16, 32)]
RANDOMISH = {'capped_n1-n1'} | {f'random_complete-n{k}' for k in (1, 2, 4, 8, 16, 32)}
kinds_by_cond, pass_by_cond, judged_keys = {}, {}, {}
for cond in COND_WHOLE:
    res = json.loads((JUDG / cond / 'chain_intermediates' / 'results.json').read_text())
    kinds_by_cond[cond] = {(row['id'], int(Ls)): k for row in res['rows'] for Ls, k in row['kind_by_layer'].items()}
    pass_by_cond[cond] = {row['id']: bool(row['pass']) for row in res['rows']}
    with open(JUDG / cond / 'chain_intermediates' / 'cells.jsonl') as fh:
        judged_keys[cond] = {json.loads(line)['key'] for line in fh}
for sid in SIDS:  # the three settings' saved kinds equal the re-derived ones (MAP.md); check here too
    assert all(kinds_by_cond[sid][(c['item'], c['layer'])] == judge[(cid, sid)]['kind']
               for cid, c in cells.items()) if sid in kinds_by_cond else True
cand_rows = {}
with open(HERE / 'candidates.jsonl') as fh:
    for line in fh:
        r = json.loads(line)
        cand_rows[r['cell_id']] = r
cand_stats = collections.Counter()
cand_cells = {}
for cid, r in cand_rows.items():
    c = cells[cid]
    trace = dict((s, v) for s, v in r['trace_best_n_exact_n32'])
    ordered = sorted(trace.values())
    per_sample = {}
    for x in r['candidates']:
        if x['cond'] not in COND_WHOLE:
            continue
        if L.judge_key(c['item'], c['layer']) not in judged_keys[x['cond']]:
            cand_stats['unjudged_cell'] += 1
            continue
        s = x['samples'][0]
        kind = kinds_by_cond[x['cond']][(c['item'], c['layer'])]
        assert abs(trace[s] - x['fve']) < 1e-9
        e = per_sample.setdefault(s, {'sample': s, 'fve': x['fve'], 'kinds': set(), 'conds': [],
                                      'pct': (np.searchsorted(ordered, x['fve'], 'left') + 0.5 *
                                              (np.searchsorted(ordered, x['fve'], 'right') -
                                               np.searchsorted(ordered, x['fve'], 'left'))) / len(ordered)})
        e['kinds'].add(kind)
        e['conds'].append(x['cond'])
    for e in per_sample.values():
        if len(e['kinds']) > 1:
            cand_stats['sample_with_conflicting_verdicts'] += 1
        e['hit'] = 'hit' in e['kinds'] and len(e['kinds']) == 1
        e['random'] = any(cd in RANDOMISH for cd in e['conds'])
    cand_cells[cid] = per_sample
    cand_stats['cells'] += 1
    cand_stats['distinct_judged_samples'] += len(per_sample)
    cand_stats['cells_with_hit_and_nonhit_candidate'] += (any(e['hit'] for e in per_sample.values()) and
                                                         any(not e['hit'] for e in per_sample.values()))


def cand_auc(sel, unit='group'):
    acc = []
    for cid, ps in cand_cells.items():
        es = [e for e in ps.values() if sel(e)]
        for h in es:
            if not h['hit']:
                continue
            for n_ in es:
                if n_['hit']:
                    continue
                acc.append((cells[cid]['item'], win(h['fve'], n_['fve']), 1.0))
    return ratio_ci(acc, unit)


t2['candidates'] = {
    'stats': dict(cand_stats),
    'auroc_fve_within_cell_all_judged_candidates': cand_auc(lambda e: True),
    'auroc_fve_within_cell_all_judged_candidates_item_level': cand_auc(lambda e: True, 'item'),
    'auroc_fve_within_cell_random_picked_candidates_only': cand_auc(lambda e: e['random']),
    'auroc_fve_within_cell_random_picked_item_level': cand_auc(lambda e: e['random'], 'item'),
    'mean_fve_percentile_among_32_hit_candidates': ratio_ci(
        [(cells[cid]['item'], e['pct'], 1.0) for cid, ps in cand_cells.items() for e in ps.values() if e['hit']]),
    'mean_fve_percentile_among_32_nonhit_candidates': ratio_ci(
        [(cells[cid]['item'], e['pct'], 1.0) for cid, ps in cand_cells.items() for e in ps.values() if not e['hit']]),
    'hit_rate_sample0_original': ratio_ci([(cells[cid]['item'], float(ps[0]['hit']), 1.0)
                                           for cid, ps in cand_cells.items() if 0 in ps]),
    'hit_rate_random_picked_nonzero_samples': ratio_ci(
        [(cells[cid]['item'], float(e['hit']), 1.0) for cid, ps in cand_cells.items() for s, e in ps.items()
         if s != 0 and any(cd.startswith('random_complete') for cd in e['conds'])]),
    'hit_rate_best_of_32_pick': ratio_ci(
        [(cells[cid]['item'], float(e['hit']), 1.0) for cid, ps in cand_cells.items() for e in ps.values()
         if 'best_n_exact-n32' in e['conds']]),
    'note': 'distinct source samples per cell judged by any of capped_n1-n1, best_n_exact-n{1..32}, '
            'random_complete-n{1..32}; a sample judged by several conditions has byte-identical text (judge cache '
            'hit). random-picked = picked by capped_n1 or random_complete (not chosen by FVE).'}

# best-of-K (by FVE) vs random-of-K: readout hit rate and item pass, K = 1..32
curve = {}
for k in (1, 2, 4, 8, 16, 32):
    row = {}
    for meth in ('best_n_exact', 'random_complete'):
        cond = f'{meth}-n{k}'
        kd = kinds_by_cond[cond]
        row[meth] = {'hit_readouts': sum(v == 'hit' for v in kd.values()), 'readouts': len(kd),
                     'items_pass': sum(pass_by_cond[cond].values())}
    bt = [(c['item'], float(kinds_by_cond[f'best_n_exact-n{k}'][(c['item'], c['layer'])] == 'hit'), 1.0)
          for c in cells.values()]
    rt = [(c['item'], float(kinds_by_cond[f'random_complete-n{k}'].get((c['item'], c['layer'])) == 'hit'), 1.0)
          for c in cells.values()]
    row['hit_rate_best_minus_random'] = diff_ci(bt, rt)
    curve[k] = row
t2['best_of_k_vs_random_of_k'] = curve

# settings vs Original
cmp_ = {}
O = 'capped_n1-n1'
for sid in SIDS[1:]:
    fixes = sum(judge[(cid, O)]['kind'] != 'hit' and judge[(cid, sid)]['kind'] == 'hit' for cid in cells)
    breaks = sum(judge[(cid, O)]['kind'] == 'hit' and judge[(cid, sid)]['kind'] != 'hit' for cid in cells)
    a = [(c['item'], float(judge[(cid, sid)]['kind'] == 'hit'), 1.0) for cid, c in cells.items()]
    b = [(c['item'], float(judge[(cid, O)]['kind'] == 'hit'), 1.0) for cid, c in cells.items()]
    cmp_[SHORT[sid]] = {'readout_hit_rate_change': diff_ci(a, b), 'fixes': fixes, 'breaks': breaks,
                        'same_text_as_original': sum(cells[cid]['settings'][sid]['text'] ==
                                                     cells[cid]['settings'][O]['text'] for cid in cells)}
    # does a larger FVE gain make a fix more likely / a break less likely? (tertiles of gain)
    gains = {cid: cells[cid]['settings'][sid]['fve'] - cells[cid]['settings'][O]['fve'] for cid in cells}
    q = np.quantile(list(gains.values()), [1 / 3, 2 / 3])
    for name, lo_, hi_ in (('low', -9, q[0]), ('mid', q[0], q[1]), ('high', q[1], 9)):
        cs = [cid for cid in cells if lo_ <= gains[cid] < hi_]
        cmp_[SHORT[sid]][f'gain_tertile_{name}'] = {
            'gain_range': [round(float(max(lo_, min(gains.values()))), 4), round(float(min(hi_, max(gains.values()))), 4)],
            'cells': len(cs),
            'fixes': sum(judge[(cid, O)]['kind'] != 'hit' and judge[(cid, sid)]['kind'] == 'hit' for cid in cs),
            'breaks': sum(judge[(cid, O)]['kind'] == 'hit' and judge[(cid, sid)]['kind'] != 'hit' for cid in cs)}
items_pass = {}
for sid in SIDS:
    res = json.loads((JUDG / sid / 'chain_intermediates' / 'results.json').read_text())
    items_pass[SHORT[sid]] = sum(bool(r['pass']) for r in res['rows'])
for sid in SIDS[1:]:
    res_s = {r['id']: bool(r['pass']) for r in json.loads((JUDG / sid / 'chain_intermediates' / 'results.json').read_text())['rows']}
    res_o = {r['id']: bool(r['pass']) for r in json.loads((JUDG / O / 'chain_intermediates' / 'results.json').read_text())['rows']}
    cmp_[SHORT[sid]]['item_pass_change'] = diff_ci([(i, float(res_s[i]), 1.0) for i in ITEM_IDS],
                                                   [(i, float(res_o[i]), 1.0) for i in ITEM_IDS])
t2['settings_vs_original'] = cmp_
t2['items_pass'] = items_pass
t2['readout_hits'] = {SHORT[sid]: sum(judge[(cid, sid)]['kind'] == 'hit' for cid in cells) for sid in SIDS}
t2['expanded_report_reference'] = {
    'released_original_lens': '49.2% (59/120)', 'four_bullet_original': '47.5% (57/120)',
    'best_of_32': '61/120 versus 57/120; fit +6.656 pp', 'combine_32': '53/120 versus 57/120; fit +8.674 pp',
    'source': 'olens-improve docs/EXPANDED_REPORT.md lines 28, 60, 105, 165-173'}
out['T2_readout_level'] = t2

# ============================================================================= T3 what FVE tracks within readouts
for r in rows:
    r['neg_cjk'] = -r['cjk']
    r['neg_coef0'] = -r['coef0']
    r['neg_list_open'] = -r['list_open']
    r['log_len'] = math.log(max(1, r['slen']))


def feat_pair(sids, feat, score, sel=lambda r: True):
    acc = []
    for (cid, sid), bs in by_ro_nd.items():
        if sid not in sids:
            continue
        bs = [b for b in bs if sel(b)]
        for a in bs:
            for b in bs:
                if a is not b and a[feat] > b[feat]:
                    acc.append((a['item_id'], win(a[score], b[score]), 1.0))
    return ratio_ci(acc)


t3 = {}
for sid in SIDS:
    S = SHORT[sid]
    p = {
        'longer scored text scores higher': feat_pair([sid], 'slen', 'solo'),
        'more prompt-token overlap scores higher': feat_pair([sid], 'prompt_ov', 'solo'),
        'less CJK scores higher': feat_pair([sid], 'neg_cjk', 'solo'),
        'non-redundant (coef > 0) scores higher': feat_pair([sid], 'neg_coef0', 'solo'),
        'states a value (lead value) scores higher': feat_pair([sid], 'states_value', 'solo'),
        'number-only bullet scores higher': feat_pair([sid], 'number_only', 'solo'),
        'has an equation / operation scores higher': feat_pair([sid], 'has_eq', 'solo'),
        'no list-number opener scores higher': feat_pair([sid], 'neg_list_open', 'solo'),
        'lead value = final answer scores higher': feat_pair([sid], 'lead_answer', 'solo'),
        'lead value = hidden intermediate scores higher': feat_pair([sid], 'lead_gold', 'solo'),
        'lead value = prompt number (start/operand) scores higher': feat_pair([sid], 'lead_prompt', 'solo'),
        'hit scores higher (label, raw solo)': feat_pair([sid], 'is_hit', 'solo'),
    }
    if sid in OB:
        p['later position scores higher'] = feat_pair([sid], 'j', 'solo')
    t3[S] = {'pair_rates_solo': p}
    # shares of features by label
    t3[S]['feature_means_by_label'] = {}
    for lab in ('hit', 'answer', 'wrong_specific', 'miss'):
        R = [r for r in LAB if r['sid'] == sid and r['label'] == lab]
        t3[S]['feature_means_by_label'][lab] = {
            'n': len(R), 'median_scored_chars': float(np.median([r['slen'] for r in R])) if R else None,
            'number_only': round(float(np.mean([r['number_only'] for r in R])), 3) if R else None,
            'has_eq': round(float(np.mean([r['has_eq'] for r in R])), 3) if R else None,
            'coef0': round(float(np.mean([r['coef0'] for r in R])), 3) if R else None,
            'mean_cjk': round(float(np.mean([r['cjk'] for r in R])), 3) if R else None,
            'mean_prompt_ov': round(float(np.mean([r['prompt_ov'] for r in R])), 3) if R else None,
            'mean_position': round(float(np.mean([r['j'] for r in R])), 3) if R else None,
            'truncated': round(float(np.mean([bool(r['truncated']) for r in R])), 3) if R else None}


def within_reg(sid, y='solo', with_coef0=False):
    R = [r for r in LAB if r['sid'] == sid]
    names = ['is_hit', 'is_wrong', 'is_answer', 'log_len', 'cjk', 'prompt_ov', 'number_only', 'has_eq',
             'states_value', 'list_open'] + (['coef0'] if with_coef0 else [])
    if sid in OB:
        names += ['pos2', 'pos3', 'pos4']
    X = []
    for r in R:
        v = [r['is_hit'], r['is_wrong'], r['is_answer'], r['log_len'], r['cjk'], r['prompt_ov'], r['number_only'],
             r['has_eq'], r['states_value'], r['list_open']] + ([r['coef0']] if with_coef0 else [])
        if sid in OB:
            v += [float(r['j'] == 1), float(r['j'] == 2), float(r['j'] == 3)]
        X.append(v)
    X, Y = np.array(X), np.array([r[y] for r in R])
    idx = collections.defaultdict(list)
    for i, r in enumerate(R):
        idx[(r['cell_id'], r['sid'])].append(i)
    Xd, Yd = X.copy(), Y.copy()
    for ii in idx.values():
        Xd[ii] -= X[ii].mean(0)
        Yd[ii] -= Y[ii].mean()
    sd = Xd.std(0)
    cont = {'log_len', 'cjk', 'prompt_ov'}
    Xs = Xd / np.array([sd[i] if n in cont else 1.0 for i, n in enumerate(names)])
    gx = np.array([r['gix'] for r in R])

    def fit(w):
        ww = w[gx]
        return np.linalg.lstsq(Xs.T @ (Xs * ww[:, None]), Xs.T @ (Yd * ww), rcond=None)[0]

    est = fit(np.ones(len(GROUP_IDS)))
    boots = np.array([fit(w) for w in BW['group']])
    resid = Yd - Xs @ est
    r2 = 1 - (resid ** 2).sum() / (Yd ** 2).sum()
    res = {'n_bullets': len(R), 'within_readout_R2': round(float(r2), 4),
           'within_readout_sd_of_y': round(float(Yd.std()), 4),
           'units': 'change in solo FVE (same readout) per 1 within-readout SD for log_len, cjk, prompt_ov and '
                    'per 0->1 for binary terms; label reference = miss',
           'coef': {n: {'est': round(float(est[i]), 4), 'lo': round(float(np.percentile(boots[:, i], 2.5)), 4),
                        'hi': round(float(np.percentile(boots[:, i], 97.5)), 4)} for i, n in enumerate(names)}}
    drops = {}
    for i, n in enumerate(names):
        keep = [x for x in range(len(names)) if x != i]
        bk = np.linalg.lstsq(Xs[:, keep], Yd, rcond=None)[0]
        rk = Yd - Xs[:, keep] @ bk
        drops[n] = round(float(r2 - (1 - (rk ** 2).sum() / (Yd ** 2).sum())), 4)
    res['R2_lost_without_feature'] = drops
    bl_ = np.linalg.lstsq(Xs[:, :3], Yd, rcond=None)[0]
    rl = Yd - Xs[:, :3] @ bl_
    res['within_readout_R2_labels_only'] = round(float(1 - (rl ** 2).sum() / (Yd ** 2).sum()), 4)
    lab_ix = [0, 1, 2]
    nolab = [i for i in range(len(names)) if i not in lab_ix]
    bn = np.linalg.lstsq(Xs[:, nolab], Yd, rcond=None)[0]
    rn = Yd - Xs[:, nolab] @ bn
    res['R2_added_by_labels_after_features'] = round(float(r2 - (1 - (rn ** 2).sum() / (Yd ** 2).sum())), 4)
    subsets = {'labels (hit, wrong_specific, answer)': ['is_hit', 'is_wrong', 'is_answer'],
               'length + number-only': ['log_len', 'number_only'],
               'length + number-only + list opener': ['log_len', 'number_only', 'list_open'],
               'equation + states value': ['has_eq', 'states_value'],
               'prompt overlap + CJK': ['prompt_ov', 'cjk']}
    if sid in OB:
        subsets['position'] = ['pos2', 'pos3', 'pos4']
    res['R2_feature_subsets_alone'] = {}
    for nm, fs in subsets.items():
        ii = [names.index(f) for f in fs]
        bs_ = np.linalg.lstsq(Xs[:, ii], Yd, rcond=None)[0]
        rs_ = Yd - Xs[:, ii] @ bs_
        res['R2_feature_subsets_alone'][nm] = round(float(1 - (rs_ ** 2).sum() / (Yd ** 2).sum()), 4)
    hw = boots[:, 0] - boots[:, 1]
    res['hit_minus_wrong_specific'] = {'est': round(float(est[0] - est[1]), 4),
                                       'lo': round(float(np.percentile(hw, 2.5)), 4),
                                       'hi': round(float(np.percentile(hw, 97.5)), 4)}
    return res


for sid in SIDS:
    t3[SHORT[sid]]['within_readout_regression_solo'] = within_reg(sid)
    if sid in OB:  # coef 0 is itself an output of the fit (redundancy given siblings): secondary model only
        t3[SHORT[sid]]['within_readout_regression_solo_with_coef0'] = within_reg(sid, with_coef0=True)
# redundancy (coef 0) in Original / Best of 32
red = {}
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid]
    red[SHORT[sid]] = {lab: ratio_ci([(r['item_id'], r['coef0'], 1.0) for r in R if r['label'] == lab])
                       for lab in ('hit', 'answer', 'wrong_specific', 'miss')}
t3['coef0_rate_by_label'] = red
out['T3_what_fve_tracks'] = t3

# ============================================================================= examples + reading sample
def fmt_case(cid, sid, focus=None):
    c = cells[cid]
    g = GOLD[c['item']]
    jd = judge[(cid, sid)]
    bs = sorted(by_ro[(cid, sid)], key=lambda b: b['j'])
    lines = [f"k={c['item']}.L{c['layer']}.p{c['pos']} [{SHORT[sid]}] cell_id={cid} readout FVE="
             f"{c['settings'][sid]['fve']:.4f} kind={jd['kind']} judge values={jd['values']} quote={jd['quote']!r}",
             f"   gold intermediates={g['intermediates']} answer={g['answer']} start={g['start']}"]
    for b in bs:
        mark = '>>' if focus is not None and b['j'] == focus else '  '
        lines.append(f"{mark} [{b['j']}] {b['label']:<14} stated={b['label_stated']:<20} share={b['share']:.3f} "
                     f"solo={b['solo']:.3f} drop={b['drop']:.4f} coef={b['coef']:.2f}{' DUP' if b['dup'] else ''}"
                     f"{' TRUNC' if b['truncated'] else ''} | {json.dumps(b['text'], ensure_ascii=False)[:240]}")
    return '\n'.join(lines)


def case_record(r, stratum, why):
    cid, sid = r['cell_id'], r['sid']
    c = cells[cid]
    g = GOLD[c['item']]
    jd = judge[(cid, sid)]
    bs = sorted(by_ro[(cid, sid)], key=lambda b: b['j'])
    others = {}
    for s2 in SIDS:
        if s2 == sid:
            continue
        j2 = judge[(cid, s2)]
        others[SHORT[s2]] = {'readout_fve': round(c['settings'][s2]['fve'], 4), 'kind': j2['kind'],
                             'judge_values': j2['values'], 'judge_quote': j2['quote'],
                             'bullets': [{'index': b['j'], 'text': b['text'], 'label': b['label'],
                                          'share': round(b['share'], 4), 'solo': round(b['solo'], 4)}
                                         for b in sorted(by_ro[(cid, s2)], key=lambda b: b['j'])]}
    return {
        'case_id': None, 'stratum': stratum, 'why_selected': why,
        'k': r['k'], 'cell_id': cid, 'setting': sid, 'setting_display': SHORT[sid], 'focus_bullet': r['j'],
        'item_id': c['item'], 'group_id': c['group'], 'split': c['split'], 'layer': c['layer'],
        'read_site': {'position': c['pos'], 'token': c['token'], 'kind': 'final prompt token (assistant onset)'},
        'prompt': g['prompt'], 'steps': g['steps'], 'depth': g['depth'],
        'target': {'intermediates': g['intermediates'], 'answer': g['answer'], 'start': g['start'],
                   'prompt_literals': g['literals'], 'near_decoys': g['near']},
        'judge': {'values_ranked': jd['values'], 'quote': jd['quote'], 'basis': jd['basis'], 'kind': jd['kind'],
                  'anchor_bullets': jd['anchor_bullets'], 'anchor_source': jd['anchor_source']},
        'readout_fve': round(c['settings'][sid]['fve'], 5), 'readout_text': c['settings'][sid]['text'],
        'bullets': [{
            'index': b['j'], 'text': b['text'], 'scored_text': b['scored'], 'truncated': bool(b['truncated']),
            'label': b['label'], 'label_value': b['label_value'], 'wrong_role': b['wrong_role'],
            'label_anchor': b['label_anchor'], 'label_contains': b['label_contains'], 'label_named': b['label_named'],
            'label_stated': b['label_stated'], 'lead_value': b['lead_value'], 'is_anchor': b['is_anchor'],
            'ambiguous_anchor': b['ambiguous_anchor'],
            'shapley': round(b['shap'], 5), 'share': round(b['share'], 4), 'solo': round(b['solo'], 4),
            'drop': round(b['drop'], 5), 'coef': round(b['coef'], 4), 'dup_vector': b['dup'],
            'solo_pos_pct': None if math.isnan(b.get('solo_pa', float('nan'))) or sid not in OB else round(b['solo_pa'], 3),
            'share_rank_in_readout': 1 + sorted([x['share'] for x in bs], reverse=True).index(b['share']),
        } for b in bs],
        'other_settings_same_cell': others,
        'reader_questions': [
            'Does the focus bullet really put the hidden intermediate (or the stated wrong value) forward as a '
            'computed result, or is it an operand/echo?',
            'Is the focus bullet\'s score explained by its form (length, number-only, explanation template, '
            'position, redundancy) rather than by the value it carries?',
            'Which sibling takes the most share, and what does it say?'],
    }


strata_pools = {}
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid]
    mixed_ro = {(cid, s) for (cid, s), bs in by_ro_nd.items() if s == sid and any(b['label'] == 'hit' for b in bs)
                and any(b['label'] != 'hit' for b in bs)}
    H = [r for r in R if r['label'] == 'hit' and (r['cell_id'], sid) in mixed_ro]
    hs = [r['share'] for r in H]
    q80, q20 = np.quantile(hs, .8), np.quantile(hs, .2)
    W = [r for r in R if r['label'] == 'wrong_specific' and len(by_ro_nd[(r['cell_id'], sid)]) > 1]
    wq80 = np.quantile([r['share'] for r in W], .8)
    # misses in hit readouts that outscore every hit bullet of their readout
    Mx = [r for r in R if r['label'] == 'miss' and (r['cell_id'], sid) in mixed_ro and
          r['share'] > max(b['share'] for b in by_ro_nd[(r['cell_id'], sid)] if b['label'] == 'hit')]
    mq50 = np.quantile([r['share'] for r in Mx], .5) if Mx else 0
    strata_pools[sid] = {
        'A_hit_high_share': ([r for r in H if r['share'] >= q80], f'hit bullet in a mixed readout, share >= q80 of '
                                                                    f'hit shares ({q80:.3f})'),
        'B_hit_low_share': ([r for r in H if r['share'] <= q20], f'hit bullet in a mixed readout, share <= q20 of hit '
                                                                   f'shares ({q20:.3f})'),
        'C1_wrong_specific_high_share': ([r for r in W if r['share'] >= wq80],
                                         f'wrong_specific bullet, share >= q80 of wrong_specific shares ({wq80:.3f})'),
        'C2_miss_beats_hit_high_share': ([r for r in Mx if r['share'] >= mq50],
                                         f'miss bullet in a hit readout that out-shares every hit bullet, share >= '
                                         f'median of such misses ({mq50:.3f})'),
    }
PLAN = {'A_hit_high_share': 4, 'B_hit_low_share': 4, 'C1_wrong_specific_high_share': 2,
        'C2_miss_beats_hit_high_share': 2}
srng = random.Random(SEED)
sample = []
used_items = collections.defaultdict(set)
for stratum, per in PLAN.items():
    big = stratum[:1]
    for sid in SIDS:
        pool, why = strata_pools[sid][stratum]
        pool = sorted(pool, key=lambda r: (r['cell_id'], r['j']))
        srng.shuffle(pool)
        got, layers_used = 0, collections.Counter()
        # spread over layers: prefer layers not yet used, at most one case per item per big stratum (A, B, C)
        for pass_ in range(3):
            for r in pool:
                if got >= per:
                    break
                if r['item_id'] in used_items[big] or any(x['cell_id'] == r['cell_id'] and x['setting'] == sid
                                                          for x in sample):
                    continue
                if pass_ == 0 and layers_used[r['L']] >= 1:
                    continue
                if pass_ == 1 and layers_used[r['L']] >= 2:
                    continue
                sample.append(case_record(r, stratum, why))
                used_items[big].add(r['item_id'])
                layers_used[r['L']] += 1
                got += 1
for i, cse in enumerate(sample):
    cse['case_id'] = f'chain-read-{i:02d}'
OUT_SAMPLE.write_text(json.dumps({
    'family': 'chain_intermediates (Chained intermediates)', 'seed': SEED, 'n_cases': len(sample),
    'design': {'A_hit_high_share': '12 = 4 per setting', 'B_hit_low_share': '12 = 4 per setting',
               'C_nonhit_high_share': '12 = per setting 2 wrong_specific with high share + 2 misses that out-share '
                                      'the hit bullets of a hit readout',
               'balance': 'at most one case per item within A, within B and within C; layers spread (seeded shuffle)',
               'pool_sizes': {SHORT[s]: {k: len(v[0]) for k, v in strata_pools[s].items()} for s in SIDS},
               'scores': 'share = exact Shapley share of the readout joint FVE; solo = bullet-alone FVE; drop = '
                         'leave-one-out FVE loss; coef = NNLS coefficient (0 = redundant); solo_pos_pct = '
                         'position-adjusted solo percentile (Original, Best of 32 only)',
               'labels': 'see tasks/chain_intermediates/MAP.md section 5'},
    'cases': sample}, ensure_ascii=False, indent=1))

# example dump for the write-up
with open(OUT_EX, 'w') as fh:
    def dump(title, rs, n=12):
        fh.write(f'\n######## {title}\n')
        for r in rs[:n]:
            fh.write(fmt_case(r['cell_id'], r['sid'], r['j']) + '\n\n')
    for sid in SIDS:
        R = [r for r in LAB if r['sid'] == sid]
        mixed = {(cid, s) for (cid, s), bs in by_ro_nd.items() if s == sid and any(b['label'] == 'hit' for b in bs)
                 and any(b['label'] != 'hit' for b in bs)}
        H = [r for r in R if r['label'] == 'hit' and (r['cell_id'], sid) in mixed]
        dump(f'{SHORT[sid]}: high-share hits', sorted(H, key=lambda r: -r['share']))
        dump(f'{SHORT[sid]}: low-share hits', sorted(H, key=lambda r: r['share']))
        Wr = [r for r in R if r['label'] == 'wrong_specific' and r['n'] > 1]
        dump(f'{SHORT[sid]}: high-share wrong_specific', sorted(Wr, key=lambda r: -r['share']))
    fh.write('\n######## frame-matched pairs (gold lead vs other lead)\n')
    for cid, a, b in fm_examples[:80]:
        fh.write(f"k={a['k']} [{SHORT[a['sid']]} b{a['j']} / {SHORT[b['sid']]} b{b['j']}] gold={GOLD[a['item_id']]['intermediates']} "
                 f"ans={GOLD[a['item_id']]['answer']} | GOLD lead {a['lead_value']} solo={a['solo']:.4f} "
                 f"{json.dumps(a['text'], ensure_ascii=False)[:140]} || OTHER lead {b['lead_value']} solo={b['solo']:.4f} "
                 f"{json.dumps(b['text'], ensure_ascii=False)[:140]}\n")
    fh.write('\n######## template-matched pairs (gold lead vs other lead)\n')
    for cid, a, b in tp_examples[:60]:
        fh.write(f"k={a['k']} [{SHORT[a['sid']]} b{a['j']} / {SHORT[b['sid']]} b{b['j']}] gold={GOLD[a['item_id']]['intermediates']} "
                 f"ans={GOLD[a['item_id']]['answer']} | GOLD lead {a['lead_value']} solo={a['solo']:.4f} "
                 f"{json.dumps(a['text'], ensure_ascii=False)[:120]} || OTHER lead {b['lead_value']} solo={b['solo']:.4f} "
                 f"{json.dumps(b['text'], ensure_ascii=False)[:120]}\n")

OUT_JSON.write_text(json.dumps(out, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))
print('wrote', OUT_JSON, OUT_SAMPLE, OUT_EX, 'cases', len(sample))
