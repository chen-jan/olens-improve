#!/usr/bin/env python3
"""Build page/data/summary.json for the Bullet FVE Explorer: do wrong bullets get less credit for the
reconstruction (FVE) than clean bullets of the same readouts?

Inputs (all inside the project scratch folder):
  page/data/index.json, page/data/items/*.json   (written by build_page_data.py --metrics ...)
  metrics/bullet_metrics.jsonl                   (full-precision per-bullet scores; the page files are rounded,
                                                  and rounding would create artificial ties)
  logs/build_stats.json                          (optional; build counters from build_page_data.py)

Usage:
  python -B build_summary.py [--data page/data] [--metrics metrics/bullet_metrics.jsonl] [--reps 1000] [--seed 0]

Statistics (per setting, pooled over the three splits; everything is exploratory):
  auroc      P(score of a clean bullet > score of a wrong bullet) over every (wrong, clean) pair in the setting,
             ties count 0.5. 0.5 = no separation; > 0.5 = clean bullets score higher.
             It mixes readouts: every wrong bullet is in a hallucinated readout, most clean bullets are in
             consistent readouts, and those have higher joint FVE. Hence also
  auroc_clean_in_hallucinated   the AUROC with clean bullets only from hallucinated readouts, and
  readout_fve_auroc             P(joint FVE of a consistent readout > that of a hallucinated readout).
  pair_rate  the same probability, but only over (wrong, clean) pairs from the SAME readout (readouts with >= 1
             wrong and >= 1 clean bullet), pooled over pairs. Readout-level differences cancel; bullet position does
             not. Where the bullet order is the lens's own writing order (Original, Best of 32), wrong bullets sit
             later and shares depend on position, so position is a confound there. Hence also, for those settings
             only,
  pair_rate_pos_adj      pair_rate on mid-rank percentiles within (bullet index, readout size) strata of the
                         setting's labelled bullets (percentile references fixed in the bootstrap), and
  pair_rate_pos_centred  pair_rate on scores centred on their stratum mean (cruder).
             In both, a pair whose RAW scores are equal (after the 1e-9 snap) counts 0.5: the adjustment only
             re-orders pairs whose raw scores differ. Without this rule the many both-zero leave-one-out drop pairs
             would be ordered by the zero rates of their strata.
             Combine 32 (SELECTION_ORDERED) lists bullets in the greedy selector's add order, which is set by FVE
             gain: position there is a consequence of the scores, not a confound, so both adjusted rates are null
             for it (with a note field), and its raw pair_rate is the within-readout comparison. bullet_order holds
             the data check (first bullet has the highest solo FVE in most Combine 32 readouts).
  The caveat texts about both confounds are generated from these numbers (confound_texts), with every
  directional word asserted.
  CIs        percentile 95% intervals from a group bootstrap over the 149 chats (items): 1,000 resamples of items
             with replacement (numpy default_rng(seed 0)); all bullets of a resampled item enter with its
             multiplicity. The same resamples are reused for every statistic of one variant.
  strict     settings_strict drops wrong bullets whose wrong-span evidence is weak: a wrong bullet is kept only
             if at least one verified wrong span occurs in this bullet alone (not repeated in / crossing into
             another bullet) and at least one occurrence lies (at least partly) inside the first 32 AR tokens.
Score values are snapped to 1e-9 before ranking, so numerically equal values (e.g. the exact-zero drops of
bullets with NNLS coefficient 0) tie instead of being ordered by float noise.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import time
from pathlib import Path

import numpy as np

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
SCORES = ['shap', 'shap_share', 'solo', 'drop']
LAYER_SCORES = ['shap_share', 'solo', 'drop']
MKEY = {'shap': 'shapley', 'shap_share': 'shapley_share', 'solo': 'solo_fve', 'drop': 'loo_drop'}
LAB = {'w': 0, 'o': 1, 'c': 2, 'x': 3}
SPECIFIC = ('hallucinated', 'consistent', 'off_topic')
SNAP = 9          # decimals: ranking tolerance 1e-9
N_BINS = 20
# Settings whose bullet order is the selector's pick order, not the lens's writing order. Combine 32 is built by
# olens_improve.selection.greedy_pool: each step appends the pooled bullet with the largest FVE gain, and a swap puts
# the new bullet into the replaced bullet's slot. Its bullet position is therefore a consequence of FVE, not a
# confound, and no position adjustment is computed for it. The kind is checked against the data in order_block.
SELECTION_ORDERED = ('pooled_greedy_swap-n32',)
SELECTION_NOTE = ('Not computed: in this setting the bullets are listed in the order the greedy selector picked '
                  'them, each for the largest FVE gain, so bullet position is a consequence of the scores rather '
                  'than a confound. Use pair_rate (see bullet_order).')
SHAP_SAME = ('Identical to shap_share by construction: within one readout, the share only divides the Shapley value '
             'by the readout\'s joint FVE, which keeps the order of its bullets.')
_CID = re.compile(r'^hallucination\|(?P<item>[a-z0-9-]+)\|L(?P<layer>\d+)\|p(?P<pos>\d+)$')


def rnd(x, d=5):
    if x is None:
        return None
    x = float(x)
    if math.isnan(x) or math.isinf(x):
        return None
    v = round(x, d)
    return 0.0 if v == 0 else v


def write_json(path, obj):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    os.replace(tmp, path)
    return path.stat().st_size


def s16(text, a, b):
    return text.encode('utf-16-le')[2 * a:2 * b].decode('utf-16-le', errors='strict')


# ----------------------------------------------------------------------------- loading
def load(data_dir, metrics_path):
    idx = json.loads((data_dir / 'index.json').read_text())
    meta, items, cells = idx['meta'], idx['items'], idx['cells']
    sids = [s['id'] for s in meta['settings']]
    full = {}
    with open(metrics_path) as fh:
        for line in fh:
            r = json.loads(line)
            m = _CID.match(r['cell_id'])
            k = f'{m["item"]}.L{int(m["layer"])}.p{int(m["pos"])}'
            full[k] = {sid: {'saved': s['joint_fve_saved'],
                             'b': [[b[MKEY[sc]] for sc in SCORES] + [b['coefficient']] for b in s['bullets']]}
                       for sid, s in r['settings'].items()}
    assert len(full) == len(cells), (len(full), len(cells))
    item_files = {}
    for it in items:
        item_files[it['id']] = json.loads((data_dir / 'items' / f'{it["id"]}.json').read_text())
    return meta, items, cells, sids, full, item_files


def bullet_rows(meta, items, cells, sids, full, item_files):
    """One row per bullet per setting with full-precision scores and the evidence flags of wrong bullets."""
    rows = {sid: collections.defaultdict(list) for sid in sids}
    readout_id = 0
    for c in cells:
        it = items[c['i']]
        rec = item_files[it['id']]['cells'][c['k']]
        for j, sid in enumerate(sids):
            r = rec['settings'][sid]
            fm = full[c['k']][sid]
            comp = c['s'][j]
            assert len(fm['b']) == len(r['bullets']) == comp['n']
            assert abs(fm['saved'] - (r['fve'] or 0.0)) < 6e-6
            wrong_spans = [sp for sp in r['spans'] if sp['verified'] and sp['type'] == 'wrong']
            for q, (b, mb) in enumerate(zip(r['bullets'], fm['b'])):
                lab = b['label']
                amb = uns = strict_keep = False
                if lab == 'w':
                    ev = [sp for sp in wrong_spans if q in sp['bullets']]
                    assert ev, (c['k'], sid, q)
                    # occurrences of verified wrong spans overlapping this bullet, scored or not (in this bullet)
                    occ_unscored = [max(a, b['start']) >= b['scored_end']
                                    for sp in ev for a, e in sp['offsets'] if a < b['end'] and e > b['start']]
                    uns = all(occ_unscored)                       # every wrong occurrence lies past the 32-token cut
                    solo_ev = [sp for sp in ev if sp['bullets'] == [q]]
                    amb = not solo_ev                             # all wrong spans are repeated / cross bullets
                    strict_keep = any(not sp['in_unscored'] for sp in solo_ev)
                rr = rows[sid]
                rr['readout'].append(readout_id)
                rr['item'].append(c['i'])
                rr['layer'].append(c['L'])
                rr['split'].append(meta['splits'].index(it['split']))
                rr['pos'].append(q)
                rr['rlab'].append(comp['c'])                  # readout label code (meta.label_codes)
                rr['rsize'].append(comp['n'])                 # number of bullets in the readout
                rr['lab'].append(LAB[lab])
                for sc, v in zip(SCORES, mb[:4]):
                    rr[sc].append(v)
                rr['coef'].append(mb[4])
                rr['amb'].append(amb)
                rr['uns'].append(uns)
                rr['keep'].append(lab != 'w' or strict_keep)
                rr['dup'].append(b['dup'])
            readout_id += 1
    out = {}
    for sid, rr in rows.items():
        a = {k: np.asarray(v) for k, v in rr.items()}
        for sc in SCORES:
            a[sc] = np.round(a[sc].astype(float), SNAP) + 0.0   # snap (and turn -0.0 into 0.0)
        position_adjust(a)
        out[sid] = a
    return out


def position_adjust(a):
    """Position-adjusted copies of every score, used only for the position-adjusted same-readout rates.

    Stratum = (bullet index, readout size). Reference = the setting's labelled bullets (wrong, clean, off-topic;
    all of them, not the strict subset) in that stratum.
      <score>_pa  mid-rank percentile of the score among the stratum's reference bullets
                  ((#below + 0.5 #equal) / #reference), the published adjustment;
      <score>_pc  score minus the stratum's reference mean (a cruder sensitivity check).
    Both are snapped to 1e-9 like the raw scores."""
    spec = a['lab'] != LAB['x']
    strata = a['pos'] * 10 + a['rsize']
    for sc in SCORES:
        v = a[sc]
        pa = np.full(len(v), np.nan)
        pc = np.full(len(v), np.nan)
        for s in np.unique(strata):
            m = strata == s
            ref = np.sort(v[m & spec])
            if len(ref) == 0:
                continue
            pa[m] = (np.searchsorted(ref, v[m], 'left') + np.searchsorted(ref, v[m], 'right')) / (2.0 * len(ref))
            pc[m] = v[m] - ref.mean()
        assert not np.isnan(pa[spec]).any() and not np.isnan(pc[spec]).any()
        a[sc + '_pa'] = np.round(pa, SNAP) + 0.0
        a[sc + '_pc'] = np.round(pc, SNAP) + 0.0


# ----------------------------------------------------------------------------- statistics
def describe(v):
    if len(v) == 0:
        return {'n': 0, 'mean': None, 'median': None, 'q25': None, 'q75': None, 'zero': None}
    q25, med, q75 = np.percentile(v, [25, 50, 75])
    return {'n': int(len(v)), 'mean': rnd(v.mean()), 'median': rnd(med), 'q25': rnd(q25), 'q75': rnd(q75),
            'zero': rnd(float(np.mean(v <= 0.0)), 4)}


def auc_parts(vals, is_w, is_c, item, n_items):
    """A[i, j] = sum over clean bullets of item i and wrong bullets of item j of [clean > wrong] + 0.5 [tie]."""
    vc, ic = vals[is_c], item[is_c]
    vw, iw = vals[is_w], item[is_w]
    A = np.zeros((n_items, n_items))
    for j in np.unique(iw):
        sw = np.sort(vw[iw == j])
        lt = np.searchsorted(sw, vc, 'left')
        le = np.searchsorted(sw, vc, 'right')
        A[:, j] = np.bincount(ic, weights=lt + 0.5 * (le - lt), minlength=n_items)
    nc = np.bincount(ic, minlength=n_items).astype(float)
    nw = np.bincount(iw, minlength=n_items).astype(float)
    return A, nc, nw


def ci(boot):
    boot = boot[np.isfinite(boot)]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return rnd(lo, 4), rnd(hi, 4)


def auroc(vals, is_w, is_c, item, n_items, M):
    if not is_w.any() or not is_c.any():
        return {'est': None, 'lo': None, 'hi': None}
    A, nc, nw = auc_parts(vals, is_w, is_c, item, n_items)
    est = A.sum() / (nc.sum() * nw.sum())
    with np.errstate(invalid='ignore', divide='ignore'):
        boot = np.einsum('ri,ij,rj->r', M, A, M, optimize=True) / ((M @ nc) * (M @ nw))
    lo, hi = ci(boot)
    return {'est': rnd(est, 4), 'lo': lo, 'hi': hi}


def pair_rate(vals, is_w, is_c, item, readout, n_items, M, raw=None):
    """Within-readout (wrong, clean) pairs: P(clean > wrong), ties 0.5, pooled over pairs.

    With `raw` (the unadjusted scores, for the position-adjusted variants), a pair whose raw scores are equal counts
    0.5 whatever its adjusted values: the adjustment re-orders only pairs whose raw scores differ. The result then
    also reports how many pairs were raw ties and the estimate without this rule (est_without_tie_rule)."""
    P = np.zeros(n_items)
    P0 = np.zeros(n_items)
    N = np.zeros(n_items)
    sel = is_w | is_c
    order = np.argsort(readout[sel], kind='stable')
    rd, v, w, it = readout[sel][order], vals[sel][order], is_w[sel][order], item[sel][order]
    rv = raw[sel][order] if raw is not None else None
    bounds = np.flatnonzero(np.diff(rd)) + 1
    n_readouts = n_tied = 0
    for g in np.split(np.arange(len(rd)), bounds):
        gw, gc = v[g][w[g]], v[g][~w[g]]
        if len(gw) == 0 or len(gc) == 0:
            continue
        n_readouts += 1
        win = (gc[:, None] > gw[None, :]) + 0.5 * (gc[:, None] == gw[None, :])
        P0[it[g[0]]] += win.sum()
        if rv is not None:
            tied = rv[g][~w[g]][:, None] == rv[g][w[g]][None, :]
            n_tied += int(tied.sum())
            win = np.where(tied, 0.5, win)
        P[it[g[0]]] += win.sum()
        N[it[g[0]]] += len(gw) * len(gc)
    if N.sum() == 0:
        return {'est': None, 'lo': None, 'hi': None, 'n_readouts': 0, 'n_pairs': 0}
    with np.errstate(invalid='ignore', divide='ignore'):
        boot = (M @ P) / (M @ N)
    lo, hi = ci(boot)
    out = {'est': rnd(P.sum() / N.sum(), 4), 'lo': lo, 'hi': hi, 'n_readouts': n_readouts, 'n_pairs': int(N.sum())}
    if rv is not None:
        out['n_raw_tied_pairs'] = n_tied
        out['est_without_tie_rule'] = rnd(P0.sum() / N.sum(), 4)
    return out


def boot_matrix(n_items, reps, seed, members=None):
    """reps x n_items multiplicities; with `members`, resample only those items (others get 0)."""
    rng = np.random.default_rng(seed)
    pool = np.arange(n_items) if members is None else np.asarray(members)
    M = np.zeros((reps, n_items))
    for r in range(reps):
        M[r] = np.bincount(pool[rng.integers(0, len(pool), len(pool))], minlength=n_items)
    return M


def setting_block(a, mask, n_items, M, M_split, edges, label_info, code_names, pos_adjust, with_hist=True):
    """All statistics of one setting for the bullets selected by `mask` (strict variant = smaller mask).
    pos_adjust=False (selection-ordered settings): the position-adjusted rates are null, with a note."""
    lab = a['lab']
    is_w = mask & (lab == LAB['w'])
    is_c = mask & (lab == LAB['c'])
    is_o = mask & (lab == LAB['o'])
    in_hall = a['rlab'] == code_names.index('hallucinated')
    # The confound behind the pooled AUROC: wrong bullets only exist in hallucinated readouts, clean bullets mostly in
    # consistent ones (which have higher joint FVE). auroc_clean_in_hallucinated relies on the first fact.
    assert not (is_w & ~in_hall).any(), 'wrong bullet outside a hallucinated readout'
    blk = dict(label_info)
    blk['bullet_counts'] = {k: int((mask & (lab == v)).sum()) for k, v in LAB.items()}
    blk['clean_by_readout_label'] = {name: int((is_c & (a['rlab'] == ci)).sum()) for ci, name in enumerate(code_names)
                                     if name in SPECIFIC}
    # bullet position in readouts with at least one wrong and one clean bullet (the readouts of pair_rate)
    mixed_ids = np.intersect1d(a['readout'][is_w], a['readout'][is_c])
    mixed = np.isin(a['readout'], mixed_ids)
    blk['mixed_readout_position'] = {
        'n_readouts': int(len(mixed_ids)),
        'n_wrong': int((mixed & is_w).sum()), 'n_clean': int((mixed & is_c).sum()),
        'mean_bullet_index_wrong': rnd(a['pos'][mixed & is_w].mean(), 4) if len(mixed_ids) else None,
        'mean_bullet_index_clean': rnd(a['pos'][mixed & is_c].mean(), 4) if len(mixed_ids) else None,
        'readout_sizes': {str(n): int(len(np.unique(a['readout'][mixed & (a['rsize'] == n)])))
                          for n in sorted(set(a['rsize'][mixed].tolist()))}}
    blk['scores'] = {}
    for sc in SCORES:
        v = a[sc]
        s = {'wrong': describe(v[is_w]), 'clean': describe(v[is_c]), 'off_topic': describe(v[is_o]),
             'auroc': auroc(v, is_w, is_c, a['item'], n_items, M),
             'auroc_clean_in_hallucinated': auroc(v, is_w, is_c & in_hall, a['item'], n_items, M),
             'pair_rate': pair_rate(v, is_w, is_c, a['item'], a['readout'], n_items, M)}
        if sc == 'shap':
            s['pair_rate_same_as'] = 'shap_share'
            s['pair_rate_note'] = SHAP_SAME
        if pos_adjust:
            s['pair_rate_pos_adj'] = pair_rate(a[sc + '_pa'], is_w, is_c, a['item'], a['readout'], n_items, M, raw=v)
            s['pair_rate_pos_centred'] = pair_rate(a[sc + '_pc'], is_w, is_c, a['item'], a['readout'], n_items, M,
                                                   raw=v)
        else:
            s['pair_rate_pos_adj'] = s['pair_rate_pos_centred'] = None
            s['pair_rate_pos_adj_note'] = SELECTION_NOTE
        if with_hist:
            e = edges[sc]
            s['hist'] = {'edges': [rnd(x, 4) for x in e],
                         'wrong': np.histogram(v[is_w], e)[0].tolist(),
                         'clean': np.histogram(v[is_c], e)[0].tolist(),
                         'off_topic': np.histogram(v[is_o], e)[0].tolist()}
        blk['scores'][sc] = s
    blk['by_layer'] = {}
    for L in sorted(set(a['layer'].tolist())):
        m = a['layer'] == L
        blk['by_layer'][str(L)] = {
            'auroc': {sc: auroc(a[sc], is_w & m, is_c & m, a['item'], n_items, M) for sc in LAYER_SCORES},
            'pair_rate': {sc: pair_rate(a[sc], is_w & m, is_c & m, a['item'], a['readout'], n_items, M)
                          for sc in LAYER_SCORES},
            'pair_rate_pos_adj': ({sc: pair_rate(a[sc + '_pa'], is_w & m, is_c & m, a['item'], a['readout'],
                                                 n_items, M, raw=a[sc]) for sc in LAYER_SCORES}
                                  if pos_adjust else None),
            'n_wrong': int((is_w & m).sum()), 'n_clean': int((is_c & m).sum())}
        if not pos_adjust:
            blk['by_layer'][str(L)]['pair_rate_pos_adj_note'] = SELECTION_NOTE
    blk['by_split'] = {}
    for si, (sp, Ms) in enumerate(M_split.items()):
        m = a['split'] == si
        blk['by_split'][sp] = {
            'auroc': {sc: auroc(a[sc], is_w & m, is_c & m, a['item'], n_items, Ms) for sc in LAYER_SCORES},
            'n_wrong': int((is_w & m).sum()), 'n_clean': int((is_c & m).sum())}
    blk['by_position'] = []
    spec = is_w | is_c | is_o
    for q in range(4):
        m = spec & (a['pos'] == q)
        n = int(m.sum())
        blk['by_position'].append({
            'n': n, 'n_wrong': int((m & is_w).sum()), 'n_clean': int((m & is_c).sum()),
            'wrong_rate': rnd((m & is_w).sum() / n, 4) if n else None,
            'mean_shap_share': rnd(a['shap_share'][m].mean(), 4) if n else None,
            'mean_shap_share_wrong': rnd(a['shap_share'][m & is_w].mean(), 4) if (m & is_w).any() else None,
            'mean_shap_share_clean': rnd(a['shap_share'][m & is_c].mean(), 4) if (m & is_c).any() else None})
    w_all = mask & (lab == LAB['w'])
    blk['scored_vs_unscored'] = {'wrong_bullets_all_wrong_spans_unscored': int((w_all & a['uns']).sum()),
                                 'wrong_bullets_total': int(w_all.sum())}
    zc = mask & (a['coef'] == 0)
    blk['zero_coefficient'] = {'n': int(zc.sum()), 'n_wrong': int((zc & is_w).sum()), 'n_clean': int((zc & is_c).sum()),
                               'n_off_topic': int((zc & is_o).sum()),
                               'mean_solo': rnd(a['solo'][zc].mean()) if zc.any() else None,
                               'mean_shap_share': rnd(a['shap_share'][zc].mean(), 4) if zc.any() else None}
    return blk


def order_block(a, sid):
    """How the setting orders its bullets, with a data check. In a greedy add order the first bullet is the one with
    the largest FVE on its own, so it has the highest solo FVE of its readout unless a swap replaced it; in a writing
    order nothing ties position to FVE."""
    r = a['readout']
    starts = np.flatnonzero(np.r_[True, r[1:] != r[:-1]])     # rows of one readout are contiguous, in bullet order
    sizes = np.diff(np.r_[starts, len(r)])
    assert (a['pos'][starts] == 0).all()
    m = sizes >= 2
    first_top = a['solo'][starts][m] >= np.maximum.reduceat(a['solo'], starts)[m]
    spec = a['lab'] != LAB['x']
    selection = sid in SELECTION_ORDERED
    blk = {'kind': 'selection' if selection else 'writing',
           'position_adjusted': not selection,
           'first_bullet_highest_solo': rnd(first_top.mean(), 4),
           'n_readouts_2plus': int(m.sum()),
           'mean_solo_by_position': [rnd(a['solo'][spec & (a['pos'] == q)].mean(), 4) for q in range(4)],
           'note': ('Bullets are listed in the order the greedy selector picked them, each for the largest FVE gain '
                    '(a swap puts the new bullet into the replaced bullet\'s slot). Position is a consequence of the '
                    'scores, not a confound, so no position adjustment is computed.' if selection else
                    'Bullets are listed in the order the lens wrote them. Position is a property of the text that '
                    'can differ between wrong and clean bullets, so the position-adjusted rates are reported.')}
    # the data must agree with the stated order: greedy order puts the best solo bullet first in most readouts
    assert (blk['first_bullet_highest_solo'] > 0.5) == selection, (sid, blk)
    if selection:
        sol = blk['mean_solo_by_position']
        assert sol[0] > sol[-1], (sid, sol)
    return blk


def label_block(codes, fves, code_names):
    c = collections.Counter(code_names[x] for x in codes)
    spec = sum(c[k] for k in SPECIFIC)
    out = {'n': len(codes), 'counts': {k: c[k] for k in code_names},
           'hallucinated_rate_of_specific': rnd(c['hallucinated'] / spec, 5) if spec else None}
    if fves is not None:
        out['mean_fve'] = rnd(float(np.mean(fves)), 5)
    return out


# ----------------------------------------------------------------------------- examples
def pick_examples(arrays, sids, cells, items, item_files):
    """Three illustrative wrong bullets (exploratory; any split)."""
    flat = []   # (sid, row, readout has a clean bullet, readout has 4 bullets)
    for sid in sids:
        a = arrays[sid]
        has_c = collections.Counter(a['readout'][a['lab'] == LAB['c']].tolist())
        n_b = collections.Counter(a['readout'].tolist())
        for t in np.flatnonzero((a['lab'] == LAB['w']) & ~a['dup']):
            r = int(a['readout'][t])
            flat.append((sid, int(t), has_c[r] > 0, n_b[r] == 4))

    def cell_of(sid, r):
        # readout ids are assigned cell by cell, setting by setting (see bullet_rows)
        return cells[r // len(sids)]

    def rec(sid, t, kind, why):
        a = arrays[sid]
        r = int(a['readout'][t])
        c = cell_of(sid, r)
        it = items[c['i']]
        ro = item_files[it['id']]['cells'][c['k']]['settings'][sid]
        q = int(a['pos'][t])
        b = ro['bullets'][q]
        spans = [sp for sp in ro['spans'] if sp['verified'] and sp['type'] == 'wrong' and q in sp['bullets']]
        return {'kind': kind, 'why_chosen': why, 'k': c['k'], 'setting': sid, 'bullet': q, 'split': it['split'],
                'layer': c['L'], 'readout_label': ro['label'], 'joint_fve': ro['fve'],
                'bullet_text': s16(ro['text'], b['start'], b['end']),
                'scored_part': s16(ro['text'], b['start'], b['scored_end']),
                'truncated': b['truncated'],
                'shap': rnd(a['shap'][t]), 'shap_share': rnd(a['shap_share'][t], 4), 'solo': rnd(a['solo'][t]),
                'drop': rnd(a['drop'][t]), 'coef': rnd(a['coef'][t], 4),
                'other_bullets': [{'bullet': j, 'label': ob['label'], 'shap_share': ob['shap_share'],
                                   'solo': ob['solo'], 'drop': ob['drop'],
                                   'text': s16(ro['text'], ob['start'], ob['end'])[:160]}
                                  for j, ob in enumerate(ro['bullets']) if j != q],
                'wrong_spans': [{'text': sp['text'], 'why': sp['why'], 'in_unscored': sp['in_unscored']}
                                for sp in spans]}

    ex = []
    # (a) strict wrong bullet (own, scored wrong span), readout with a clean bullet, highest Shapley share
    cand = [(arrays[sid]['shap_share'][t], sid, t) for sid, t, hc, four in flat
            if hc and four and arrays[sid]['keep'][t]]
    _, sid, t = max(cand)
    ex.append(rec(sid, t, 'wrong_high_share', 'Wrong bullet (its own wrong span, inside the scored 32 tokens) with the '
                  'highest Shapley share among 4-bullet readouts that also have a clean bullet.'))
    # (b) strict wrong bullet with the lowest Shapley share (ties broken by lower solo FVE)
    cand = [(arrays[sid]['shap_share'][t], arrays[sid]['solo'][t], sid, t) for sid, t, hc, four in flat
            if hc and four and arrays[sid]['keep'][t]]
    _, _, sid, t = min(cand)
    ex.append(rec(sid, t, 'wrong_near_zero_share', 'Wrong bullet (its own wrong span, inside the scored 32 tokens) with '
                  'the lowest Shapley share among 4-bullet readouts that also have a clean bullet.'))
    # (c) wrong bullet whose wrong span(s) all lie past the 32-token limit; highest share among those
    cand = [(arrays[sid]['shap_share'][t], sid, t) for sid, t, hc, four in flat
            if arrays[sid]['uns'][t] and not arrays[sid]['amb'][t]]
    _, sid, t = max(cand)
    ex.append(rec(sid, t, 'wrong_span_unscored', 'Wrong bullet whose verified wrong span lies entirely after the '
                  '32-token AR limit, so the error cannot affect its FVE scores; highest Shapley share among these.'))
    return ex


# ----------------------------------------------------------------------------- confound caveats
SCORE_NAME = {'shap': 'Shapley value', 'shap_share': 'Shapley share', 'solo': 'solo FVE', 'drop': 'leave-one-out drop'}


def join_names(names):
    names = list(names)
    return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]


def confound_texts(settings, sids, short):
    """Caveat texts for the two confounds of the headline statistics, built from the computed numbers. Every
    directional word in the text is asserted, so a rebuild on changed data fails instead of printing a false caveat.
      pooled AUROC: wrong bullets only in hallucinated readouts, clean bullets mostly in consistent readouts, which
                    have higher joint FVE -> the pooled AUROC is mostly a between-readout comparison;
      same-readout rate: in writing-order settings wrong bullets sit later in mixed readouts and Shapley share
                    depends on position -> position-adjusted rates; in selection-ordered settings position follows
                    from FVE -> no adjustment, the raw rate is the within-readout comparison."""
    f3 = '{:.3f}'.format
    names = ' / '.join(short[s] for s in sids)
    o = sids[0]
    wo = [s for s in sids if settings[s]['bullet_order']['position_adjusted']]      # lens writing order
    so = [s for s in sids if not settings[s]['bullet_order']['position_adjusted']]  # selector pick order
    assert wo and all(settings[s]['scores'][sc]['pair_rate_pos_adj'] is None for s in so for sc in SCORES)
    wo_names, so_names = join_names(short[s] for s in wo), join_names(short[s] for s in so) if so else ''

    def within(s, sc):
        """The within-readout statistic to quote: position-adjusted where position is a confound, raw otherwise."""
        x = settings[s]['scores'][sc]
        return x['pair_rate_pos_adj'] if s in wo else x['pair_rate']

    # ---- pooled AUROC
    cb, nc = settings[o]['clean_by_readout_label'], settings[o]['bullet_counts']['c']
    assert cb['consistent'] > nc / 2, cb                                         # "most clean bullets"
    for s in sids:
        assert settings[s]['readout_fve_auroc']['est'] > 0.5                    # "higher joint FVE"
        for sc in ('solo', 'shap'):
            x = settings[s]['scores'][sc]
            assert x['auroc']['est'] > 0.5                                       # "excess over 0.5"
            assert x['auroc_clean_in_hallucinated']['est'] < x['auroc']['est']   # "lowers"
            # "mostly between readouts": the within-readout excess is under half the pooled excess
            assert abs(within(s, sc)['est'] - 0.5) < 0.5 * (x['auroc']['est'] - 0.5), (s, sc)
    ro = ' / '.join(f3(settings[s]['readout_fve_auroc']['est']) for s in sids)

    def change(sc):
        return ', '.join(f"{f3(settings[s]['scores'][sc]['auroc']['est'])} to "
                         f"{f3(settings[s]['scores'][sc]['auroc_clean_in_hallucinated']['est'])} ({short[s]})"
                         for s in sids)

    def rates(sc, key, ss):
        return ' / '.join(f3(settings[s]['scores'][sc][key]['est']) for s in ss)

    pooled = (
        'The AUROC compares wrong and clean bullets from any readouts, usually different ones. Its excess over 0.5 for '
        'solo FVE and Shapley value '
        'comes mostly from differences between readouts, not from wrong bullets getting less credit than clean bullets '
        'of the same readout. Wrong bullets occur only in hallucinated readouts, while most clean bullets come from '
        f'consistent readouts ({cb["consistent"]:,} of {nc:,} in {short[o]}), and consistent readouts have higher joint '
        f'FVE (readout-level AUROC of joint FVE, consistent vs hallucinated: {ro} for {names}). Taking clean bullets '
        f'only from hallucinated readouts lowers the solo FVE AUROC from {change("solo")} and the Shapley value AUROC '
        f'from {change("shap")}. To compare bullets of the same readout, use the same-readout rate (solo FVE: '
        f'{rates("solo", "pair_rate", sids)} for {names}'
        + (f'; adjusted for bullet position, which applies only to {wo_names}: '
           f'{rates("solo", "pair_rate_pos_adj", wo)}' if so else
           f'; adjusted for bullet position: {rates("solo", "pair_rate_pos_adj", wo)}') + ').')

    # ---- bullet position in the same-readout rate
    mp = {s: settings[s]['mixed_readout_position'] for s in sids}
    order = {s: settings[s]['bullet_order'] for s in sids}
    share = {s: [p['mean_shap_share_clean'] for p in settings[s]['by_position']] for s in sids}
    for s in wo:
        assert mp[s]['mean_bullet_index_wrong'] > mp[s]['mean_bullet_index_clean'] + 0.1, mp[s]   # "sit later"
        assert share[s][-1] > share[s][0] + 0.01, share[s]                    # "later bullets get larger shares"
        for sc in ('shap_share', 'solo', 'drop'):
            x = settings[s]['scores'][sc]
            if x['pair_rate']['est'] < 0.5:                       # "below 0.5 is largely a position effect"
                assert x['pair_rate_pos_adj']['est'] > x['pair_rate']['est'] and x['pair_rate_pos_adj']['est'] > 0.495
    for s in so:
        assert order[s]['first_bullet_highest_solo'] > 0.5                   # "in most of its readouts"
        assert all(order[s]['first_bullet_highest_solo'] > 2 * order[t]['first_bullet_highest_solo'] for t in wo)
        assert share[s][0] > share[s][-1] + 0.01, share[s]                    # "shares fall with position"
        assert abs(mp[s]['mean_bullet_index_wrong'] - mp[s]['mean_bullet_index_clean']) < 0.1, mp[s]   # "similar"
    pos_txt = '; '.join(f"{short[s]} {mp[s]['mean_bullet_index_wrong']:.2f} vs {mp[s]['mean_bullet_index_clean']:.2f}"
                        for s in wo)
    sh_txt = '; '.join(f"{short[s]} " + ', '.join(f3(x) for x in share[s]) for s in wo)
    excl = [f"{short[s]} {SCORE_NAME[sc]} {f3(x['est'])} [{f3(x['lo'])}, {f3(x['hi'])}]"
            for s in wo for sc in ('shap_share', 'solo', 'drop')
            for x in [settings[s]['scores'][sc]['pair_rate']] if x['hi'] < 0.5]

    def adj(sc):
        return '; '.join(f"{short[s]} {f3(settings[s]['scores'][sc]['pair_rate']['est'])} to "
                         f"{f3(settings[s]['scores'][sc]['pair_rate_pos_adj']['est'])} "
                         f"[{f3(settings[s]['scores'][sc]['pair_rate_pos_adj']['lo'])}, "
                         f"{f3(settings[s]['scores'][sc]['pair_rate_pos_adj']['hi'])}]" for s in wo)

    def raw_ci(s, sc):
        x = settings[s]['scores'][sc]['pair_rate']
        return f"{SCORE_NAME[sc]} {f3(x['est'])} [{f3(x['lo'])}, {f3(x['hi'])}]"

    pct = '{:.0%}'.format
    position = (
        'The same-readout rate removes differences between readouts but not bullet position. In '
        f'{wo_names} the bullets are in the order the lens wrote them, and position matters: in readouts with both a '
        'wrong and a clean bullet, wrong bullets sit later in the list (mean bullet index, 0 = first, wrong vs clean: '
        f'{pos_txt}), and later bullets get larger Shapley shares whatever the label (mean share of clean bullets at '
        f'positions 1 to 4: {sh_txt}). There a same-readout rate below 0.5 is largely a position effect, not evidence '
        'that wrong bullets get more credit'
        + (f'; this includes the rates whose intervals exclude 0.5 ({"; ".join(excl)})' if excl else '') + '.'
        + ' Comparing each bullet only with bullets at the same position in readouts of the same size '
        f'(position-adjusted same-readout rate, raw to adjusted [95% interval]) gives, for Shapley share: '
        f'{adj("shap_share")}; for solo FVE: {adj("solo")}; for leave-one-out drop: {adj("drop")}. The adjustment is '
        'a sensitivity check, not a model of why position matters.')
    for s in so:
        position += (
            f' {short[s]} is different: its bullets are listed in the order the greedy selector picked them, each for '
            'the largest FVE gain (a swap puts the new bullet into the replaced bullet\'s slot). Its first bullet has '
            f'the highest solo FVE in {pct(order[s]["first_bullet_highest_solo"])} of its readouts ('
            + ', '.join(f'{short[t]} {pct(order[t]["first_bullet_highest_solo"])}' for t in wo)
            + '), clean-bullet shares fall with position (' + ', '.join(f3(x) for x in share[s]) + '), and wrong and '
            f'clean bullets of mixed readouts sit at similar positions ({mp[s]["mean_bullet_index_wrong"]:.2f} vs '
            f'{mp[s]["mean_bullet_index_clean"]:.2f}). Position there is a consequence of the scores, not a '
            f'confound, so no position adjustment is computed for {short[s]}; its raw same-readout rate is the '
            'within-readout comparison (' + '; '.join(raw_ci(s, sc) for sc in ('shap_share', 'solo', 'drop')) + ').')

    distinct = ('shap_share', 'solo', 'drop')     # shap has the same raw same-readout rate as shap_share
    adj_all = [settings[s]['scores'][sc]['pair_rate_pos_adj']['est'] for s in wo for sc in distinct]
    raw_so = [settings[s]['scores'][sc]['pair_rate']['est'] for s in so for sc in distinct]
    scope_note = (
        ' Two confounds affect the headline numbers. The AUROC compares bullets from different readouts, and most clean '
        'bullets come from consistent readouts, which have higher joint FVE than the hallucinated readouts that hold '
        'every wrong bullet. The same-readout rate removes that but not bullet position. In '
        f'{wo_names}, whose bullets are in the lens\'s writing order, wrong bullets tend to sit later and later '
        'bullets get larger Shapley shares; adjusted for position, their same-readout rates lie between '
        f'{f3(min(adj_all))} and {f3(max(adj_all))} for Shapley share, solo FVE and leave-one-out drop (Shapley value '
        'has the same raw rate as Shapley share).'
        + (f' In {so_names} the order is the selector\'s pick order, set by FVE gain, so position is a consequence of '
           'the scores and is not adjusted for; '
           + ('its' if len(so) == 1 else 'their') + f' raw same-readout rates lie between {f3(min(raw_so))} and '
           f'{f3(max(raw_so))}.' if so else ''))
    return pooled, position, scope_note


def tie_dup_texts(settings, arrays, sids, short):
    """Caveats on exact ties of leave-one-out drop and on repeated bullets, per setting, from the data."""
    for s in sids:
        a = arrays[s]
        assert not ((a['coef'] == 0) & (a['drop'] != 0)).any(), s       # "drop is exactly 0 for every coef-0 bullet"
    zc = {s: settings[s]['zero_coefficient']['n'] for s in sids}
    nb = {s: len(arrays[s]['lab']) for s in sids}
    with0 = [s for s in sids if zc[s] > 0]
    without = [s for s in sids if zc[s] == 0]
    assert with0
    ties = {s: settings[s]['scores']['drop']['pair_rate_pos_adj']['n_raw_tied_pairs'] for s in with0
            if settings[s]['scores']['drop']['pair_rate_pos_adj'] is not None}
    other_zero = {sc: [int((arrays[s][sc] == 0).sum()) for s in sids] for sc in ('shap_share', 'solo')}
    assert all(max(v) < 0.001 * min(nb.values()) for v in other_zero.values())   # "almost no ties"
    drop_txt = (
        'Leave-one-out drop is exactly 0 for every bullet with NNLS coefficient 0 (the other bullets already cover '
        'its direction): ' + '; '.join(f'{short[s]} {zc[s]:,} of {nb[s]:,} bullets ({zc[s] / nb[s]:.1%})'
                                       for s in with0)
        + ('; ' + join_names(short[s] for s in without) + ' none (its selector adds a bullet only when that raises '
           'the joint FVE)' if without else '')
        + f'. So drop has many exact ties in {join_names(short[s] for s in with0)}'
        + (' only' if without else '') + '. Same-readout pairs with equal drops ('
        + '; '.join(f'{short[s]} {n:,} pairs' for s, n in ties.items())
        + ') count one half in the raw and in the position-adjusted rates. Shapley share and solo FVE have almost no '
        'exact zeros (' + '; '.join(f'{SCORE_NAME[sc]} ' + ' / '.join(str(x) for x in v) for sc, v in other_zero.items())
        + f' bullets in {" / ".join(short[s] for s in sids)}).')
    dup = {s: (int(arrays[s]['dup'].sum()), int(len(np.unique(arrays[s]['readout'][arrays[s]['dup']])))) for s in sids}
    dup_txt = ('Repeated identical bullets share one vector and split Shapley credit equally; they are included ('
               + '; '.join(f'{short[s]} {n} bullets in {r} readouts' if n else f'{short[s]} none'
                           for s, (n, r) in dup.items()) + ').')
    return drop_txt, dup_txt


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(ROOT / 'page/data'))
    ap.add_argument('--metrics', default=str(ROOT / 'metrics/bullet_metrics.jsonl'))
    ap.add_argument('--build-stats', default=str(ROOT / 'logs/build_stats.json'))
    ap.add_argument('--reps', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()
    t0 = time.time()
    D = Path(args.data)
    assert str(D.resolve()).startswith(str(ROOT)), 'refusing to write outside the project scratch folder'
    meta, items, cells, sids, full, item_files = load(D, Path(args.metrics))
    assert meta.get('metrics_available'), 'page data was built without --metrics'
    code_names = meta['label_codes']
    n_items = len(items)
    arrays = bullet_rows(meta, items, cells, sids, full, item_files)
    print(f'loaded {len(cells)} cells, {sum(len(a["lab"]) for a in arrays.values())} bullets in '
          f'{time.time() - t0:.1f}s', flush=True)

    M = boot_matrix(n_items, args.reps, args.seed)
    M_split = {sp: boot_matrix(n_items, args.reps, args.seed,
                               [i for i, it in enumerate(items) if it['split'] == sp]) for sp in meta['splits']}
    # shared histogram edges per score (over all settings, all labels)
    edges = {}
    for sc in SCORES:
        mx = max(float(arrays[sid][sc].max()) for sid in sids)
        hi = 1.0 if sc == 'shap_share' else max(0.05, math.ceil(mx * 20 - 1e-9) / 20)
        assert mx <= hi + 1e-12
        edges[sc] = np.linspace(0.0, hi, N_BINS + 1)

    split_of_cell = [items[c['i']]['split'] for c in cells]
    cell_item = np.array([c['i'] for c in cells])
    settings, settings_strict = {}, {}
    for j, sid in enumerate(sids):
        codes = [c['s'][j]['c'] for c in cells]
        fves = np.array([full[c['k']][sid]['saved'] for c in cells])
        a = arrays[sid]
        cod = np.array(codes)
        is_cons, is_hall = cod == code_names.index('consistent'), cod == code_names.index('hallucinated')
        rfa = auroc(np.round(fves, SNAP), is_hall, is_cons, cell_item, n_items, M)   # P(consistent > hallucinated)
        rfa.update({'n_consistent': int(is_cons.sum()), 'n_hallucinated': int(is_hall.sum())})
        info = {'n_readouts': len(cells), 'mean_fve': rnd(fves.mean(), 5),
                'label_counts': label_block(codes, None, code_names)['counts'],
                'hallucinated_rate_of_specific': label_block(codes, None, code_names)['hallucinated_rate_of_specific'],
                'mean_fve_by_label': {lab: (rnd(fves[np.array(codes) == ci].mean(), 5)
                                            if (np.array(codes) == ci).any() else None)
                                      for ci, lab in enumerate(code_names)},
                'readout_fve_auroc': rfa}
        info['bullet_order'] = order_block(a, sid)
        pos_ok = info['bullet_order']['position_adjusted']
        settings[sid] = setting_block(a, np.ones(len(a['lab']), bool), n_items, M, M_split, edges, info, code_names,
                                      pos_ok)
        keep = a['keep']
        excl = (a['lab'] == LAB['w']) & ~keep
        info_s = dict(info)
        info_s['excluded_wrong'] = {
            'total': int(excl.sum()),
            'ambiguous': int((excl & a['amb']).sum()),
            'unscored_not_ambiguous': int((excl & ~a['amb']).sum()),
            'note': 'ambiguous = every wrong span of the bullet also occurs in (or crosses into) another bullet; '
                    'unscored_not_ambiguous = the bullet has its own wrong span(s), but all lie past the 32-token '
                    'limit (some of these bullets also have ambiguous spans).'}
        settings_strict[sid] = setting_block(a, keep, n_items, M, M_split, edges, info_s, code_names, pos_ok)
        print(f'  {sid}: done ({time.time() - t0:.1f}s)', flush=True)

    labels = {}
    for j, sid in enumerate(sids):
        codes = np.array([c['s'][j]['c'] for c in cells])
        fves = np.array([full[c['k']][sid]['saved'] for c in cells])
        lay = np.array([c['L'] for c in cells])
        spl = np.array(split_of_cell)
        labels[sid] = {'all': label_block(codes.tolist(), fves, code_names),
                       'by_split': {sp: label_block(codes[spl == sp].tolist(), fves[spl == sp], code_names)
                                    for sp in meta['splits']},
                       'by_layer': {str(L): label_block(codes[lay == L].tolist(), fves[lay == L], code_names)
                                    for L in meta['layers']}}
    if meta['reference']['available']:
        rc = np.array([c['r'] for c in cells])
        lay = np.array([c['L'] for c in cells])
        spl = np.array(split_of_cell)
        labels[meta['reference']['id']] = {
            'all': label_block(rc.tolist(), None, code_names),
            'by_split': {sp: label_block(rc[spl == sp].tolist(), None, code_names) for sp in meta['splits']},
            'by_layer': {str(L): label_block(rc[lay == L].tolist(), None, code_names) for L in meta['layers']}}

    examples = pick_examples(arrays, sids, cells, items, item_files)
    build = None
    bs = Path(args.build_stats)
    if bs.is_file():
        build = json.loads(bs.read_text()).get('build')

    short = {s['id']: s['short'] for s in meta['settings']}
    cav_pooled, cav_position, scope_note = confound_texts(settings, sids, short)
    cav_drop, cav_dup = tie_dup_texts(settings, arrays, sids, short)
    wo = [s for s in sids if settings[s]['bullet_order']['position_adjusted']]
    so = [s for s in sids if not settings[s]['bullet_order']['position_adjusted']]
    wo_names, so_names = join_names(short[s] for s in wo), join_names(short[s] for s in so) if so else 'none'
    n_layers = len(meta['layers'])
    assert len(cells) % n_layers == 0
    summary = {
        'generated': meta['generated'],
        'provisional': False,
        'scope': f'Exploratory description of all {len(cells):,} cells ({n_items} chats, {len(cells) // n_layers:,} '
                 f'read sites x {n_layers} layers) pooled over the {join_names(meta["splits"])} splits. All '
                 f'{n_items} chats were inspected before this analysis, so no split, including test, is a fresh '
                 'held-out test.' + scope_note,
        'definitions': {
            'joint_fve': 'How much of the target activation the readout\'s bullets explain together: whiten the '
                         'activation and each bullet\'s AR vector (per-layer pooled whitener, ridge 0.1), scale each '
                         'bullet vector to length 1, fit a non-negative least-squares combination (scipy NNLS), and '
                         'take FVE = 1 - |residual|^2 / |target|^2. Saved project value.',
            'shap': 'Shapley value: the bullet\'s average gain in FVE when it is added to every possible subset of '
                    'the other bullets of the same readout (empty set scores 0). The values of one readout add up '
                    'exactly to its joint FVE.',
            'shap_share': 'Shapley value divided by the readout\'s joint FVE: the bullet\'s share of the explained '
                          'variance. The shares of one readout add up to 1.',
            'solo': 'FVE of the bullet fitted on its own.',
            'drop': 'Leave-one-out drop: joint FVE minus the FVE of the readout refitted without this bullet. It is 0 '
                    'when the other bullets already cover the bullet\'s direction (NNLS coefficient 0), even if the '
                    'bullet alone explains a lot.',
            'bullet_labels': 'Derived from the judge\'s quoted spans. w (wrong) = the bullet overlaps a verified wrong '
                             'span; o (off-topic) = it overlaps a verified off-topic span and no wrong span; c (clean) '
                             '= neither. Only in readouts the judge labelled hallucinated, consistent or off_topic; '
                             'bullets of generic or empty readouts are x (not applicable). A span that appears in '
                             'several bullets marks all of them. Clean means "no flagged span", not "verified true".',
            'auroc': 'Probability that a randomly chosen clean bullet scores higher than a randomly chosen wrong '
                     'bullet of the same setting (any readouts), ties counted as one half. 0.5 = the score does not '
                     'separate them; above 0.5 = clean bullets score higher. Because the two bullets usually come '
                     'from different readouts, this mixes bullet-level and readout-level differences: every wrong '
                     'bullet sits in a hallucinated readout, most clean bullets sit in consistent readouts, and '
                     'consistent readouts have higher joint FVE (see readout_fve_auroc).',
            'auroc_clean_in_hallucinated': 'The AUROC with clean bullets taken only from hallucinated readouts '
                                           '(wrong bullets are already all in hallucinated readouts). It removes '
                                           'the consistent-vs-hallucinated difference but still compares bullets '
                                           'of different readouts.',
            'readout_fve_auroc': 'Readout level: probability that a consistent readout has a higher joint FVE than a '
                                 'hallucinated readout of the same setting, ties counted as one half.',
            'clean_by_readout_label': 'Clean bullets counted by the label of the readout they belong to.',
            'pair_rate': 'The same probability, but only comparing a wrong and a clean bullet from the same '
                         'readout (readouts with at least one of each), so readout-level differences such as layer, '
                         'chat and overall FVE cancel out. Pooled over all such pairs. Bullet position does NOT '
                         'cancel out, because the two bullets always sit at different positions. In '
                         f'{wo_names} the order is the lens\'s writing order: wrong bullets tend to sit later and '
                         'scores depend on position, so position is a confound (see mixed_readout_position, '
                         f'by_position and pair_rate_pos_adj). In {so_names} the order is the selector\'s pick '
                         'order, set by FVE gain, so position is a consequence of the scores and the raw rate is the '
                         'within-readout comparison (see bullet_order). Shapley value and Shapley share have '
                         'identical same-readout rates by construction, because within one readout the share only '
                         'divides by the joint FVE; summaries quote the Shapley share one (scores.shap carries '
                         'pair_rate_same_as).',
            'pair_rate_pos_adj': f'Position-adjusted same-readout rate, computed only for {wo_names}, whose bullets '
                                 'are in the lens\'s writing order; null for the other settings (their bullet order is '
                                 'the selection order, see bullet_order). Each score is first replaced by its mid-rank '
                                 'percentile ((number below + half the number equal) / number in the group) among '
                                 'all labelled bullets (wrong, clean, off-topic) of the setting that sit at the same '
                                 'position in readouts with the same number of bullets; then the same-readout rate is '
                                 'computed on these percentiles. It asks whether the wrong bullet scores lower for '
                                 'its position than the clean bullet scores for its position. Ties: a pair whose raw '
                                 'scores are equal counts one half here too, so the adjustment only re-orders pairs '
                                 'whose raw scores differ. Without this rule, pairs in which both leave-one-out drops '
                                 'are exactly 0 would be ordered by how common zeros are at each position '
                                 '(n_raw_tied_pairs counts these pairs, est_without_tie_rule gives the estimate '
                                 'without the rule). Shapley value and Shapley share differ slightly here, because '
                                 'percentiles compare bullets across readouts. The percentile references are held '
                                 'fixed in the bootstrap, and the by_layer and settings_strict values use the same '
                                 'setting-wide references. A sensitivity check, not a model of why position matters.',
            'pair_rate_pos_centred': 'Cruder variant of pair_rate_pos_adj (same settings, same tie rule): each score '
                                     'minus the mean score of its (position, readout size) group, then the '
                                     'same-readout rate. Prefer pair_rate_pos_adj.',
            'bullet_order': 'How the setting orders its bullets. kind = writing (the lens\'s own order) or selection '
                            '(the greedy selector\'s pick order: each step adds the pooled bullet with the largest '
                            'FVE gain, and a swap puts the new bullet into the replaced bullet\'s slot). '
                            'position_adjusted says whether pair_rate_pos_adj is computed. Data check: '
                            'first_bullet_highest_solo is the share of readouts with at least 2 bullets whose first '
                            'bullet has the highest solo FVE (high under a greedy order, which picks the best single '
                            'bullet first); mean_solo_by_position is over labelled bullets.',
            'by_position': 'Labelled bullets (wrong, clean, off-topic) at each bullet index (0 to 3). n = their '
                           'number; wrong_rate = n_wrong / n (off-topic bullets stay in the denominator); '
                           'mean_shap_share* = mean Shapley share of all / wrong / clean bullets there. In a '
                           'selection-ordered setting the index is the pick order.',
            'hallucinated_rate_of_specific': 'Hallucinated readouts / (hallucinated + consistent + off_topic '
                                             'readouts); generic and empty readouts are left out of the '
                                             'denominator.',
            'mixed_readout_position': 'In the readouts used by the same-readout rate (at least one wrong and one '
                                      'clean bullet): the mean bullet index (0 = first) of wrong and of clean '
                                      'bullets, and how many of these readouts have each size.',
            'ci': f'95% percentile intervals from a bootstrap over the {n_items} chats: {args.reps:,} resamples of '
                  f'chats with replacement (seed {args.seed}); every bullet of a resampled chat is included. by_split '
                  'intervals resample only that split\'s chats.',
            'strict': 'settings_strict keeps a wrong bullet only if at least one verified wrong span occurs in this '
                      'bullet alone (not repeated in, or crossing into, another bullet) and at least one of its '
                      'occurrences starts inside the first 32 AR tokens. Clean and off-topic bullets are unchanged.',
            'scored_vs_unscored': 'Wrong bullets whose every wrong-span occurrence (within that bullet) starts at or '
                                  'after the 32-token AR limit: the error is in text that no FVE number sees.',
            'zero': 'In score summaries, "zero" is the fraction of bullets whose score is exactly 0 (within 1e-9).',
            'ties': 'Scores are rounded to 1e-9 before ranking, so numerically equal values tie.',
        },
        'settings': settings,
        'settings_strict': settings_strict,
        'labels': labels,
        'examples': examples,
        'bootstrap': {'groups': 'items (chats)', 'n_groups': n_items, 'reps': args.reps, 'seed': args.seed,
                      'interval': 'percentile 2.5-97.5'},
        'caveats': [
            'Exploratory: every chat was inspected before this analysis; the test split is not a fresh held-out test.',
            'Labels are per readout from one judge call (GPT-6 Luna, v5c-chat); bullet labels come from locating the '
            'judge\'s quoted spans. A bullet without a flagged span is "clean", not verified true, and identical '
            'texts in different settings reuse one judge verdict.',
            'The AR model scores only the first 32 tokens of each bullet. A wrong span after that limit cannot '
            'change any FVE number; settings_strict removes those bullets.',
            'A span repeated in several bullets marks all of them wrong; settings_strict removes bullets whose only '
            'evidence is such a repeated or boundary-crossing span.',
            'FVE measures how well bullet vectors reconstruct the activation, not whether a bullet is true. A low '
            'score is not a truth label, and a high score does not certify a bullet.',
            cav_drop,
            cav_pooled,
            cav_position,
            'The three settings share chats and read sites, so their intervals are not independent.',
            cav_dup,
        ],
    }
    if build is not None:
        summary['build'] = build
    size = write_json(D / 'summary.json', summary)
    print(f'wrote {D / "summary.json"} ({size / 1e3:.1f} kB) in {time.time() - t0:.1f}s')
    # ---- console headline
    for name, blk in (('ALL', settings), ('STRICT', settings_strict)):
        print(f'\n== {name}')
        for sid in sids:
            s = blk[sid]
            print(f'{sid:24s} bullets {s["bullet_counts"]}  mean_fve {s["mean_fve"]}')
            print(f'   readout_fve_auroc {s["readout_fve_auroc"]}  clean_by_readout_label {s["clean_by_readout_label"]}'
                  f'  mixed_readout_position {s["mixed_readout_position"]}')
            print(f'   bullet_order {s["bullet_order"]["kind"]} first_bullet_highest_solo '
                  f'{s["bullet_order"]["first_bullet_highest_solo"]} mean_solo_by_position '
                  f'{s["bullet_order"]["mean_solo_by_position"]}')
            for sc in SCORES:
                au, pr = s['scores'][sc]['auroc'], s['scores'][sc]['pair_rate']
                ah, pa = s['scores'][sc]['auroc_clean_in_hallucinated'], s['scores'][sc]['pair_rate_pos_adj']
                pc = s['scores'][sc]['pair_rate_pos_centred']
                w, c = s['scores'][sc]['wrong'], s['scores'][sc]['clean']
                print(f'   {sc:10s} AUROC {au["est"]} [{au["lo"]}, {au["hi"]}]  pair {pr["est"]} [{pr["lo"]}, '
                      f'{pr["hi"]}] ({pr["n_readouts"]} readouts, {pr["n_pairs"]} pairs)  median wrong {w["median"]} '
                      f'clean {c["median"]}  zero wrong {w["zero"]} clean {c["zero"]}')
                adj_txt = (f'pair pos-adj {pa["est"]} [{pa["lo"]}, {pa["hi"]}] (raw-tied pairs {pa["n_raw_tied_pairs"]}, '
                           f'without tie rule {pa["est_without_tie_rule"]})  pair pos-centred {pc["est"]} '
                           f'[{pc["lo"]}, {pc["hi"]}]' if pa is not None else 'pair pos-adj: not computed (selection order)')
                print(f'   {"":10s} AUROC clean-in-hall {ah["est"]} [{ah["lo"]}, {ah["hi"]}]  {adj_txt}')
            print('   scored_vs_unscored', s['scored_vs_unscored'], '| zero coef', s['zero_coefficient'])
            if name == 'STRICT':
                print('   excluded', s['excluded_wrong'])
    print('\n== by_layer AUROC shap_share / pair_rate shap_share')
    for sid in sids:
        print(sid, {L: (v['auroc']['shap_share']['est'], v['pair_rate']['shap_share']['est'])
                    for L, v in settings[sid]['by_layer'].items()})
    print('\n== by_split AUROC shap_share')
    for sid in sids:
        print(sid, {sp: (v['auroc']['shap_share']['est'], v['auroc']['shap_share']['lo'],
                         v['auroc']['shap_share']['hi']) for sp, v in settings[sid]['by_split'].items()})
    print('\n== by_position')
    for sid in sids:
        print(sid, settings[sid]['by_position'])
    print('\n== examples')
    print(json.dumps(examples, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
