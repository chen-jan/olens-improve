#!/usr/bin/env python
"""Synthesis statistics for errors/ERRORS.md and errors/errors_page.json (exploratory).

Inputs (read-only):
  errors/records/rep_*.json      240 hand-read wrong bullets (20 batches x 12), representative sample
  errors/rep_sample.json         sampling design: inclusion probability pi per case (weights 1/pi)
  errors/recurrence.jsonl        per verified wrong span: rec_32 etc. (errors/recurrence.py)
  errors/recurrence_summary.json, errors/avoidability.json (copied numbers only)
  errors/pool_hall.json          32 raw lens samples per cell
  page/data/items/*.json         prompt, reply, read-site offsets

New analysis here ("truth in pool"): for every verified wrong span whose key element is a novel
name or number, take the judge's own reason ("why") and pull out the names/numbers it cites that
occur in the prompt or reply but not in the wrong span (the "truth tokens", e.g. "The response
refers to Mary, not Alice." -> Mary). Count how many of the cell's 32 lens samples contain any
truth token (lenient: any role, any position). This asks whether the right value is anywhere in
the pool that Best of 32 / Combine 32 / a consensus vote choose from.

Writes errors/errors_stats.json.  Run (about 1-2 CPU-min, ~3 GB):
  PYTHONPATH=${OLENS_REPO_ROOT}/src \
  ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B errors_synth.py
"""
import collections
import glob
import json
import os
import random
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from recurrence import feats, match_feats, norm, canon_num, STOP  # noqa: E402

BASE = os.path.dirname(HERE)
DATA = f'{BASE}/page/data'
PAGE = 'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3'
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
B = 2000


# ------------------------------------------------------------------------------------------ records
def load_records():
    samp = json.load(open(f'{HERE}/rep_sample.json'))
    S = {(c['k'], c['setting'], c['bullet']): c for c in samp['cases']}
    recs = []
    for f in sorted(glob.glob(f'{HERE}/records/rep_*.json')):
        d = json.load(open(f))
        cases = d if isinstance(d, list) else (d.get('cases') or d.get('records'))
        b = int(os.path.basename(f)[4:6])
        for c in cases:
            s = S[(c['k'], c['setting'], c['bullet'])]
            recs.append(dict(c, batch=b, item=s['item'], source=s['source'], L=s['L'], pi=s['pi'],
                             w=1.0 / s['pi'], bullet_text=s['bullet_text'], judge_spans=s['wrong_spans'],
                             position=s['position']))
    assert len(recs) == 240 and len({(r['k'], r['setting'], r['bullet']) for r in recs}) == 240
    return recs


def wprop(rows, pred):
    tw = sum(r['w'] for r in rows)
    return sum(r['w'] for r in rows if pred(r)) / tw if tw else float('nan')


_BOOT_IDX = {}


def est(rows, pred, by='item', weighted=True):
    """Proportion (weighted by r['w'] if weighted) with a chat-level bootstrap 95% CI (resample chats)."""
    if not rows:
        return {'n': 0, 'of': 0, 'pct': None, 'lo': None, 'hi': None}
    num, den = collections.defaultdict(float), collections.defaultdict(float)
    for r in rows:
        w = r['w'] if weighted else 1.0
        den[r[by]] += w
        if pred(r):
            num[r[by]] += w
    keys = sorted(den)
    a = np.array([num[k] for k in keys])
    b = np.array([den[k] for k in keys])
    n = len(keys)
    if n not in _BOOT_IDX:
        _BOOT_IDX[n] = np.random.default_rng(7 + n).integers(0, n, size=(B, n))
    idx = _BOOT_IDX[n]
    v = a[idx].sum(1) / b[idx].sum(1)
    lo, hi = np.quantile(v, [0.025, 0.975])
    return {'n': sum(1 for r in rows if pred(r)), 'of': len(rows), 'pct': round(100 * a.sum() / b.sum(), 1),
            'lo': round(100 * float(lo), 1), 'hi': round(100 * float(hi), 1)}


# ------------------------------------------------------------------------------------------ recurrence rows
def load_recurrence():
    rows = []
    with open(f'{HERE}/recurrence.jsonl') as f:
        for line in f:
            r = json.loads(line)
            rows.append({k: r.get(k) for k in ('k', 'item', 'source', 'layer', 'setting', 'span_index', 'bullet', 'span',
                                             'why', 'kind', 'element_basis', 'elements', 'rec_32', 'rec_any_32',
                                             'grade', 'majority_removes', 'dup_first', 'src_sample')})
            rows[-1]['blind_rec_32'] = (r.get('blind') or {}).get('rec_32')
            if rows[-1]['rec_32'] is None:   # 7 spans with no key element: not gradable
                rows.pop()
    return rows


# ------------------------------------------------------------------------------------------ truth tokens
WHY_STOP = {'response', 'readout', 'prompt', 'user', 'assistant', 'model', 'the', 'it', 'this', 'that', 'marker',
            'context', 'read', 'english', 'chinese', 'ai', 'qwen', 'reply', 'text', 'bullet', 'its', 'there',
            'nothing', 'neither', 'instead', 'rather', 'although', 'while', 'both', 'these', 'those', 'they',
            'french', 'spanish', 'italian', 'german', 'japanese', 'korean', 'answer', 'question',
            # titles and generic name parts: the distinctive part of the name is kept instead
            'miss', 'ms', 'mr', 'mrs', 'dr', 'mx', 'sir', 'madam', 'mister', 'teacher', 'professor', 'prof',
            'director', 'sister', 'brother', 'dear', 'co', 'ltd', 'inc', 'corp', 'corporation', 'company',
            'group', 'province', 'city', 'district', 'road', 'street', 'county', 'state', 'university', 'lab'}
CAPW = re.compile(r"(?<![\w'])([A-Z][A-Za-z0-9'\-]*[A-Za-z0-9]|[A-Z])(?![\w])")
NUMW = re.compile(r'(?<![\d.,])(\d+(?:[.,]\d+)*)(?![\d])')


def truth_tokens(why, span, ref_f, span_f):
    """Names/numbers the judge's reason cites that are in the reference (prompt+reply) and not in the span."""
    w = norm(why)
    out = []
    first = True
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9'\-]*|\d+(?:[.,]\d+)*", w):
        g = m.group(0)
        is_first = first
        first = False
        if g[0].isdigit():
            c = canon_num(g.rstrip('.,'))
            el = ('n', c)
        else:
            if not g[0].isupper() or is_first:
                continue
            low = g.casefold().split("'")[0]
            if low in STOP or low in WHY_STOP or len(low) < 2:
                continue
            el = ('w', low)
        if not match_feats(el, ref_f):       # must be in prompt + reply
            continue
        if match_feats(el, span_f):          # must not be in the wrong span itself
            continue
        if el not in out:
            out.append(el)
    return out


def main():
    recs = load_records()
    rec_rows = load_recurrence()
    by_cell_set = collections.defaultdict(list)
    for r in rec_rows:
        by_cell_set[(r['k'], r['setting'])].append(r)

    # ---------------------------------------------------------------- join records <- recurrence (bullet level)
    for r in recs:
        rows = [x for x in by_cell_set[(r['k'], r['setting'])] if r['bullet'] in (x['bullet'] or [])]
        r['n_wrong_spans'] = len(rows)
        if rows:
            r['rec_32_max'] = max(x['rec_32'] for x in rows)
            r['rec_32_min'] = min(x['rec_32'] for x in rows)
            r['blind_rec_32_max'] = max((x['blind_rec_32'] or 0) for x in rows)
            r['grade'] = 'one_off' if r['rec_32_max'] <= 2 else ('recurring' if r['rec_32_max'] <= 15 else 'sticky')
            r['vote_removes_bullet_error'] = r['rec_32_max'] < 16
        else:
            r['rec_32_max'] = r['rec_32_min'] = r['blind_rec_32_max'] = None
            r['grade'] = None

    # ---------------------------------------------------------------- items, pools for truth-in-pool
    items = {}
    for f in glob.glob(f'{DATA}/items/*.json'):
        d = json.load(open(f))
        items[d['item']['id']] = d
    pool = json.load(open(f'{HERE}/pool_hall.json'))['pools']
    pool_f = {}

    def pf(k):
        if k not in pool_f:
            pool_f[k] = [feats(t) for t in pool[k]]
        return pool_f[k]

    ref_cache, before_cache = {}, {}

    def ref_feats(item):
        if item not in ref_cache:
            it = items[item]['item']
            ref_cache[item] = feats(it['prompt'] + '\n' + it['response'])
        return ref_cache[item]

    def before_feats(k):
        if k not in before_cache:
            item = k.rsplit('.', 2)[0]
            it = items[item]['item']
            ch = items[item]['cells'][k]['char']
            before = it['response'].encode('utf-16-le')[:2 * ch].decode('utf-16-le')
            before_cache[k] = feats(it['prompt'] + '\n' + before)
        return before_cache[k]

    truth_rows = []
    for r in rec_rows:
        if not r['dup_first']:
            continue
        tt = truth_tokens(r['why'], r['span'], ref_feats(r['item']), feats(r['span']))
        if not tt:
            continue
        P = pf(r['k'])
        cnt = sum(1 for f in P if any(match_feats(e, f) for e in tt))
        cnt_all = sum(1 for f in P if all(match_feats(e, f) for e in tt))
        bf = before_feats(r['k'])
        vis = any(match_feats(e, bf) for e in tt)
        vis_all = all(match_feats(e, bf) for e in tt)
        truth_rows.append({'k': r['k'], 'item': r['item'], 'source': r['source'], 'layer': r['layer'],
                           'setting': r['setting'], 'basis': r['element_basis'], 'kind': r['kind'],
                           'span': r['span'], 'why': r['why'], 'truth': [e[1] for e in tt], 'truth_32': cnt,
                           'truth_all_32': cnt_all,
                           'wrong_32': r['rec_32'], 'grade': r['grade'], 'visible_before_read': vis,
                           'visible_before_read_all': vis_all})
    nn_unique = [r for r in rec_rows if r['dup_first'] and r['element_basis'] in ('name', 'number')]
    T = [t for t in truth_rows if t['basis'] in ('name', 'number')]

    def tstats(rows):
        if not rows:
            return None
        o = {'n': len(rows)}
        for name, pred in [('truth_in_0_of_32', lambda t: t['truth_32'] == 0),
                           ('truth_in_1_plus', lambda t: t['truth_32'] >= 1),
                           ('truth_in_16_plus', lambda t: t['truth_32'] >= 16),
                           ('truth_more_than_wrong', lambda t: t['truth_32'] > t['wrong_32']),
                           ('wrong_16_plus', lambda t: t['wrong_32'] >= 16)]:
            o[name] = est(rows, pred, weighted=False)
        o['median_truth_32'] = sorted(t['truth_32'] for t in rows)[len(rows) // 2]
        o['strict_all_tokens'] = {
            'truth_in_0_of_32': est(rows, lambda t: t['truth_all_32'] == 0, weighted=False),
            'truth_in_16_plus': est(rows, lambda t: t['truth_all_32'] >= 16, weighted=False),
            'truth_more_than_wrong': est(rows, lambda t: t['truth_all_32'] > t['wrong_32'], weighted=False)}
        return o

    truth = {
        'method': ('Unique verified wrong spans (first copy per cell) whose key element is a novel name or number. '
                   'Truth tokens = capitalised words / numbers in the judge\'s reason that occur in the prompt or '
                   'reply and not in the wrong span. truth_32 = samples (of the cell\'s 32 raw lens samples) '
                   'containing any truth token, anywhere and in any role (lenient upper bound on availability). '
                   'wrong_32 = rec_32 of the wrong span. visible_before_read = a truth token occurs in the prompt '
                   'or in the reply before the read site. CIs: chat-level bootstrap, unweighted rows.'),
        'name_number_unique_spans': len(nn_unique),
        'with_truth_token': len(T),
        'coverage_pct': round(100 * len(T) / len(nn_unique), 1),
        'all': tstats(T),
        'share_visible_before_read_any_token': est(T, lambda t: t['visible_before_read'], weighted=False),
        'share_visible_before_read_all_tokens': est(T, lambda t: t['visible_before_read_all'], weighted=False),
        'visible_before_read_all_tokens': tstats([t for t in T if t['visible_before_read_all']]),
        'visible_before_read': tstats([t for t in T if t['visible_before_read']]),
        'only_after_read': tstats([t for t in T if not t['visible_before_read']]),
        'by_basis': {b: tstats([t for t in T if t['basis'] == b]) for b in ('name', 'number')},
        'by_grade': {g: tstats([t for t in T if t['grade'] == g]) for g in ('one_off', 'recurring', 'sticky')},
        'by_source': {s: tstats([t for t in T if t['source'] == s]) for s in ('dailydialog', 'lmsys')},
        'by_layer': {L: tstats([t for t in T if t['layer'] == L]) for L in (20, 36, 44, 52, 60)},
        'all_bases_with_truth_token': tstats(truth_rows),
    }
    audit = random.Random(3).sample(T, 60)
    truth['audit_sample'] = [{k: t[k] for k in ('k', 'setting', 'span', 'why', 'truth', 'truth_32', 'truth_all_32',
                                                'wrong_32', 'visible_before_read')} for t in audit]
    truth_by_key = collections.defaultdict(list)
    for t in truth_rows:
        truth_by_key[(t['k'], t['setting'])].append(t)

    # truth for the 240 records (any setting copy of the same span text in the cell counts)
    for r in recs:
        rows = [x for x in by_cell_set[(r['k'], r['setting'])] if r['bullet'] in (x['bullet'] or [])]
        best = None
        for x in rows:
            tt = truth_tokens(x['why'], x['span'], ref_feats(r['item']), feats(x['span']))
            if not tt:
                continue
            cnt = sum(1 for f in pf(r['k']) if any(match_feats(e, f) for e in tt))
            if best is None or cnt < best[0]:
                best = (cnt, [e[1] for e in tt])
        r['truth_32'] = best[0] if best else None
        r['truth_tokens'] = best[1] if best else None

    # ---------------------------------------------------------------- record-level mixes
    TYPES = [t for t, _ in collections.Counter(r['error_type'] for r in recs).most_common()]
    SEV = ['contradicts_main_point', 'changes_meaning', 'minor_detail', 'cosmetic', 'not_an_error']
    AV = ['context_makes_it_obvious', 'needs_info_not_in_activation_plausibly', 'lens_guessing_specifics', 'unclear']
    NOT_REAL = {'judge_overstrict_not_wrong', 'plausible_continuation_not_taken'}

    def mix(rows):
        out = {}
        out['type'] = {t: est(rows, lambda r, t=t: r['error_type'] == t) for t in TYPES}
        out['severity'] = {s: est(rows, lambda r, s=s: r['severity'] == s) for s in SEV}
        out['severity_grouped'] = {
            'meaning_changing (contradicts_main_point + changes_meaning)':
                est(rows, lambda r: r['severity'] in ('contradicts_main_point', 'changes_meaning')),
            'minor (minor_detail + cosmetic)': est(rows, lambda r: r['severity'] in ('minor_detail', 'cosmetic')),
            'not_an_error': est(rows, lambda r: r['severity'] == 'not_an_error')}
        out['gist_correct'] = est(rows, lambda r: r['gist_correct'] is True)
        out['avoidability_guess'] = {a: est(rows, lambda r, a=a: r['avoidability_guess'] == a) for a in AV}
        out['not_really_a_content_error'] = {
            'judge_overstrict_or_plausible_continuation_type': est(rows, lambda r: r['error_type'] in NOT_REAL),
            'severity_not_an_error': est(rows, lambda r: r['severity'] == 'not_an_error'),
            'either_or_cosmetic': est(rows, lambda r: r['error_type'] in NOT_REAL or r['severity'] in ('not_an_error', 'cosmetic')),
            'real_meaning_change_and_type_not_judge_or_continuation':
                est(rows, lambda r: r['error_type'] not in NOT_REAL and r['severity'] in ('contradicts_main_point', 'changes_meaning'))}
        out['grade_bullet_max'] = {g: est([r for r in rows if r['grade']], lambda r, g=g: r['grade'] == g)
                                   for g in ('one_off', 'recurring', 'sticky')}
        return out

    stats = {'meta': {'generated': '2026-10-15', 'exploratory': True, 'n_records': len(recs),
                      'weights': 'rates weighted by 1/pi (rep_sample.json) so they estimate the population of '
                                 '17,387 eligible wrong bullets; CIs are 95% chat-level bootstrap (2,000 reps)',
                      'n_chats': len({r['item'] for r in recs})},
             'overall': mix(recs),
             'unweighted_counts': {f: dict(collections.Counter(str(r[f]) for r in recs).most_common())
                                   for f in ('error_type', 'severity', 'gist_correct', 'avoidability_guess', 'grade')},
             'by_setting': {SHORT[s]: mix([r for r in recs if r['setting'] == s]) for s in SHORT},
             'by_source': {s: mix([r for r in recs if r['source'] == s]) for s in ('dailydialog', 'lmsys')}}

    # per-type table
    tt = []
    for t in TYPES:
        rows = [r for r in recs if r['error_type'] == t]
        sev = collections.Counter(r['severity'] for r in rows)
        av = collections.Counter(r['avoidability_guess'] for r in rows)
        g = [r for r in rows if r['grade']]
        tt.append({'type': t, 'n': len(rows), **{k: stats['overall']['type'][t][k] for k in ('pct', 'lo', 'hi')},
                   'severity_mix': {s: sev.get(s, 0) for s in SEV},
                   'avoidability_mix': {a: av.get(a, 0) for a in AV},
                   'gist_right_pct': round(100 * wprop(rows, lambda r: r['gist_correct'] is True), 1),
                   'gist_right_n': sum(1 for r in rows if r['gist_correct'] is True),
                   'one_off_pct': round(100 * wprop(g, lambda r: r['grade'] == 'one_off'), 1) if g else None,
                   'recurring_pct': round(100 * wprop(g, lambda r: r['grade'] == 'recurring'), 1) if g else None,
                   'sticky_pct': round(100 * wprop(g, lambda r: r['grade'] == 'sticky'), 1) if g else None,
                   'n_with_recurrence': len(g),
                   'median_rec_32': sorted(r['rec_32_max'] for r in g)[len(g) // 2] if g else None,
                   'truth_known_n': sum(1 for r in rows if r['truth_32'] is not None),
                   'truth_in_0_of_32_n': sum(1 for r in rows if r['truth_32'] == 0)})
    stats['type_table'] = tt

    # crosstabs (unweighted counts)
    stats['crosstab_type_x_severity'] = {t: dict(collections.Counter(r['severity'] for r in recs if r['error_type'] == t))
                                         for t in TYPES}
    stats['crosstab_avoid_x_severity'] = {a: dict(collections.Counter(r['severity'] for r in recs if r['avoidability_guess'] == a))
                                          for a in AV}
    stats['crosstab_avoid_x_grade'] = {a: dict(collections.Counter(str(r['grade']) for r in recs if r['avoidability_guess'] == a))
                                       for a in AV}
    stats['crosstab_severity_x_grade'] = {s: dict(collections.Counter(str(r['grade']) for r in recs if r['severity'] == s))
                                          for s in SEV}
    # meaning-changing errors with truth visible in context: is the truth in the pool?
    sev_ctx = [r for r in recs if r['severity'] in ('contradicts_main_point', 'changes_meaning')]
    stats['meaning_changing_records'] = {
        'n': len(sev_ctx),
        'avoidability': dict(collections.Counter(r['avoidability_guess'] for r in sev_ctx)),
        'grade': dict(collections.Counter(str(r['grade']) for r in sev_ctx)),
        'sticky_weighted': est([r for r in sev_ctx if r['grade']], lambda r: r['grade'] == 'sticky'),
        'one_off_weighted': est([r for r in sev_ctx if r['grade']], lambda r: r['grade'] == 'one_off'),
        'truth_known': sum(1 for r in sev_ctx if r['truth_32'] is not None),
        'truth_in_0_of_32': sum(1 for r in sev_ctx if r['truth_32'] == 0),
        'truth_in_16_plus': sum(1 for r in sev_ctx if (r['truth_32'] or 0) >= 16)}
    minor = [r for r in recs if r['severity'] in ('minor_detail', 'cosmetic', 'not_an_error')]
    stats['minor_records'] = {
        'n': len(minor), 'grade': dict(collections.Counter(str(r['grade']) for r in minor)),
        'sticky_weighted': est([r for r in minor if r['grade']], lambda r: r['grade'] == 'sticky'),
        'one_off_weighted': est([r for r in minor if r['grade']], lambda r: r['grade'] == 'one_off')}
    stats['records_truth'] = {
        'known': sum(1 for r in recs if r['truth_32'] is not None),
        'in_0_of_32': sum(1 for r in recs if r['truth_32'] == 0),
        'in_16_plus': sum(1 for r in recs if (r['truth_32'] or 0) >= 16)}
    stats['truth_in_pool'] = truth
    stats['records'] = [{k: r.get(k) for k in ('k', 'setting', 'bullet', 'item', 'source', 'L', 'w', 'error_type',
                                                'severity', 'gist_correct', 'avoidability_guess', 'rec_32_max',
                                                'rec_32_min', 'blind_rec_32_max', 'grade', 'n_wrong_spans',
                                                'truth_32', 'truth_tokens')} for r in recs]
    json.dump(stats, open(f'{HERE}/errors_stats.json', 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: stats[k] for k in ('meta', 'unweighted_counts')}, indent=1))
    print(json.dumps({k: v for k, v in truth.items() if k != 'audit_sample'}, indent=1)[:6000])


if __name__ == '__main__':
    main()
