"""Skeptic recomputation of the headline numbers for the three extension families.

Independent of the analysts' analysis.py: reads only
  - <family>/bullet_metrics.jsonl            (per-bullet solo / share / LOO / coef; joined on phrase_id)
  - <family>/bullet_labels.jsonl             (per-bullet labels; label RULES are the analysts', checked here
                                              against the raw judge files)
  - <family> three_settings extract           (scored_token_count per atom = what the AR vector sees)
  - expansion-v1/judgments/<cond>/<family>/  (raw judge verdicts: the 3 settings + the judged
                                              capped / random_complete / best_n_exact whole-sample conditions)
  - <family> candidates file                  (which source sample each whole-sample condition picked, and the
                                              32-sample FVE trace)
Writes tasks/skeptic/<family>_results.json.  No judge/API calls, no GPU.

Usage: python -B recompute.py {multihop_mt|chain_intermediates|role_bound_association}
"""
import collections
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np

FAM = sys.argv[1]
T = Path('${OLENS_SCRATCH}/olens-bullet-fve/tasks')
J = Path('${OLENS_DATA_ROOT}/expansion-v1/judgments')
OUT = T / 'skeptic' / f'{FAM}_results.json'
SET = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
DISP = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
REPS = 1000
RNG = np.random.default_rng(20261015)
T0 = time.time()


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


PATHS = {
    'multihop_mt': dict(metrics=T / 'multihop_mt/bullet_metrics.jsonl', labels=T / 'multihop_mt/bullet_labels.jsonl',
                        extract=T / 'multihop_mt/inputs/multihop_mt_three_settings.jsonl',
                        cands=T / 'multihop_mt/inputs/multihop_mt_candidates.jsonl'),
    'chain_intermediates': dict(metrics=T / 'chain_intermediates/bullet_metrics.jsonl',
                                labels=T / 'chain_intermediates/bullet_labels.jsonl',
                                extract=T / 'chain_intermediates/chain_three_settings.jsonl',
                                cands=T / 'chain_intermediates/candidates.jsonl'),
    'role_bound_association': dict(metrics=T / 'role_bound_association/bullet_metrics.jsonl',
                                   labels=T / 'role_bound_association/bullet_labels.jsonl',
                                   extract=T / 'role_bound_association/data/rba_three_settings.jsonl',
                                   cands=T / 'role_bound_association/candidates/candidates.jsonl'),
}[FAM]

# ----------------------------------------------------------------------------------------------- bootstrap

def boot_ratio(groups_num, groups_den):
    """Pair rate = sum(num)/sum(den), percentile CI by resampling groups."""
    W = np.asarray(groups_num, float)
    N = np.asarray(groups_den, float)
    keep = N > 0
    W, N = W[keep], N[keep]
    if N.sum() == 0:
        return None
    est = W.sum() / N.sum()
    G = len(W)
    idx = RNG.integers(0, G, size=(REPS, G))
    bs = W[idx].sum(1) / np.maximum(N[idx].sum(1), 1e-12)
    return {'est': round(float(est), 4), 'lo': round(float(np.percentile(bs, 2.5)), 4),
            'hi': round(float(np.percentile(bs, 97.5)), 4), 'pairs': int(round(N.sum())), 'groups': int(G)}


def boot_mean_diff(per_group_sum, per_group_n):
    return boot_ratio(per_group_sum, per_group_n)


def pair_rate(pairs, key=lambda x: x):
    """pairs: list of (group, a_score, b_score[, weight]). P(a > b), ties 1/2. Pooled over pairs."""
    gw = collections.defaultdict(float)
    gn = collections.defaultdict(float)
    for p in pairs:
        g, a, b = p[0], p[1], p[2]
        w = p[3] if len(p) > 3 else 1.0
        gw[g] += w * (1.0 if a > b else 0.5 if a == b else 0.0)
        gn[g] += w
    gs = sorted(gn)
    return boot_ratio([gw[g] for g in gs], [gn[g] for g in gs])


def boot_auroc_strata(scores, labels, strata, groups):
    """AUROC (P(pos score > neg score), ties 1/2) pooled over within-stratum pos/neg pairs; CI by resampling groups
    (weights = multiplicity of each group in the draw)."""
    scores = np.asarray(scores, float)
    labels = np.asarray(labels, bool)
    strata = np.asarray(strata)
    gidx_map = {g: i for i, g in enumerate(sorted(set(groups)))}
    gi = np.array([gidx_map[g] for g in groups])
    G = len(gidx_map)
    mult = np.vstack([np.ones(G), np.stack([np.bincount(RNG.integers(0, G, G), minlength=G) for _ in range(REPS)])])
    num = np.zeros(REPS + 1)
    den = np.zeros(REPS + 1)
    npos = int(labels.sum())
    for s in np.unique(strata):
        m = strata == s
        pos = np.where(m & labels)[0]
        neg = np.where(m & ~labels)[0]
        if len(pos) == 0 or len(neg) == 0:
            continue
        order = neg[np.argsort(scores[neg], kind='stable')]
        f = scores[order]
        lo = np.searchsorted(f, scores[pos], 'left')
        hi = np.searchsorted(f, scores[pos], 'right')
        wf = mult[:, gi[order]]                      # (R+1, nneg)
        cw = np.concatenate([np.zeros((REPS + 1, 1)), np.cumsum(wf, 1)], 1)
        wp = mult[:, gi[pos]]                        # (R+1, npos)
        less = cw[:, lo]
        eq = cw[:, hi] - cw[:, lo]
        num += (wp * (less + 0.5 * eq)).sum(1)
        den += wp.sum(1) * wf.sum(1)
    if den[0] == 0:
        return None
    est = num[0] / den[0]
    bs = num[1:] / np.maximum(den[1:], 1e-12)
    return {'est': round(float(est), 4), 'lo': round(float(np.percentile(bs, 2.5)), 4),
            'hi': round(float(np.percentile(bs, 97.5)), 4), 'pairs': int(den[0]), 'pos': npos,
            'neg': int((~labels).sum()), 'groups': G}


def boot_paired_diff(groups, diffs):
    """mean of per-unit differences, CI by resampling groups."""
    s = collections.defaultdict(float)
    n = collections.defaultdict(float)
    for g, d in zip(groups, diffs):
        s[g] += d
        n[g] += 1
    gs = sorted(n)
    S = np.array([s[g] for g in gs])
    N = np.array([n[g] for g in gs])
    est = S.sum() / N.sum()
    idx = RNG.integers(0, len(gs), size=(REPS, len(gs)))
    bs = S[idx].sum(1) / N[idx].sum(1)
    return {'est': round(float(est), 4), 'lo': round(float(np.percentile(bs, 2.5)), 4),
            'hi': round(float(np.percentile(bs, 97.5)), 4), 'n': int(N.sum()), 'groups': len(gs)}


# ----------------------------------------------------------------------------------------------- load

def load_metrics():
    M = {}
    readout = {}
    for line in open(PATHS['metrics']):
        r = json.loads(line)
        for s in SET:
            st = r['settings'][s]
            readout[(r['cell_id'], s)] = {'fve': st.get('joint_fve_saved'), 'skipped': st.get('skipped'),
                                          'n': len(st['bullets'])}
            for b in st['bullets']:
                M[(r['cell_id'], s, b['phrase_id'])] = b
    return M, readout


def load_ntok():
    """scored_token_count per (cell, setting, phrase_id) from the slim extract."""
    out = {}
    with open(PATHS['extract']) as f:
        for line in f:
            r = json.loads(line)
            for s in SET:
                st = r['settings'][s]
                for pid, a in zip(st['phrase_ids'], st['atoms']):
                    out[(r['cell_id'], s, pid)] = (a.get('scored_token_count') or 0, bool(a.get('truncated')))
    return out


NUM_ONLY = re.compile(r'^[\s\*\$`#>\-]*-?\d+(?:[.,]\d+)?[\s\*\$`\.]*$')


def norm_label(r):
    """Return (cls, extras). cls in {'hit','nonhit_cmp','wrong','miss','excluded'} plus raw label."""
    if FAM == 'multihop_mt':
        lab = r['label']
        ex = {'raw': lab, 'lenient': r['label_lenient'], 'near': bool(r['near_hit']),
              'tgt': bool(r['target_hit_strict'] or r['target_hit_lenient']),
              'visible': r.get('hit_visible_to_vector', True), 'strict_roles': r['strict_roles'],
              'pass': bool(r['readout_pass']), 'unit_hits': r['readout_unit_hits'],
              'required': r['required_roles'], 'text': r['text'], 'dup': False, 'has_vec': True}
        return lab, ex
    if FAM == 'chain_intermediates':
        lab = r['label']
        ex = {'raw': lab, 'stated': r['label_stated'], 'kind': r['readout_kind'], 'dup': bool(r['dup_vector']),
              'has_vec': True, 'text': r['text'], 'pass': r['readout_kind'] == 'hit',
              'num_only': bool(NUM_ONLY.match(r['text'].strip())) if r['text'].strip() else False,
              'lead': r['lead_value'], 'gold': r['gold_intermediates'], 'answer': r['gold_answer'],
              'top': (r['judge_values'] or [None])[0], 'wrong_role': r.get('wrong_role')}
        return lab, ex
    lab = r['contrast_group']
    ex = {'raw': r['label_fine'], 'relaxed': r['label_relaxed'], 'ncomp': r['n_components'],
          'binding': r['binding'], 'dup': False, 'has_vec': bool(r['has_vector']), 'text': r['text'],
          'pass': bool(r['judge']['pass']), 'cls': r['judge']['readout_class'], 'label': r['label'],
          'site': r.get('token')}
    return lab, ex


def load_labels():
    L = {}
    meta = {}
    with open(PATHS['labels']) as f:
        for line in f:
            r = json.loads(line)
            idx = r.get('index', r.get('bullet'))
            lab, ex = norm_label(r)
            ex['index'] = idx
            ex['nb'] = r.get('n_bullets_in_readout', r.get('n_bullets'))
            L[(r['cell_id'], r['setting'], r['phrase_id'])] = (lab, ex)
            meta[r['cell_id']] = (r['item_id'], r['group_id'], r['layer'], r['position'])
    return L, meta


# ----------------------------------------------------------------------------------------------- judge (raw)

def judge_verdicts(cond):
    """(item, layer, pos-or-None) -> pass (bool), plus per-readout detail for the 3 settings."""
    base = J / cond / FAM
    out = {}
    detail = {}
    if FAM == 'multihop_mt':
        pc = json.load(open(base / 'project_contract.json'))
        for row in pc['cell_diagnostic']['rows']:
            out[(row['item_id'], row['layer'], row['position'])] = bool(row['pass'])
        res = json.load(open(base / 'results.json'))
        for row in res['rows']:
            for L, v in row['layers'].items():
                detail[(row['id'], int(L))] = {k: bool(x) for k, x in v['hits'].items()}, row['roles']
    elif FAM == 'chain_intermediates':
        res = json.load(open(base / 'results.json'))
        for row in res['rows']:
            for L, k in row['kind_by_layer'].items():
                out[(row['id'], int(L), None)] = (k == 'hit')
                detail[(row['id'], int(L))] = k
    else:
        res = json.load(open(base / 'results.json'))
        for row in res['rows']:
            out[(row['id'], row['layer'], row['pos'])] = bool(row['pass'])
    return out, detail


def vkey(item, layer, pos):
    return (item, layer, None) if FAM == 'chain_intermediates' else (item, layer, pos)


# ----------------------------------------------------------------------------------------------- main

def main():
    R = {'family': FAM, 'notes': {}}
    M, readout_meta = load_metrics()
    log('metrics', len(M))
    NT = load_ntok()
    log('ntok', len(NT))
    L, meta = load_labels()
    log('labels', len(L))
    assert set(L) == set(M), (len(set(L) - set(M)), len(set(M) - set(L)))
    R['notes']['join'] = f'labels and metrics join 1:1 on (cell, setting, phrase_id): {len(L)} bullets'

    # ---------------- build readouts
    RO = collections.defaultdict(list)  # (cell, setting) -> list of bullet dicts
    for key, (lab, ex) in L.items():
        cell, s, pid = key
        m = M[key]
        nt = NT.get(key, (None, None))
        b = dict(ex)
        b.update(lab=lab, pid=pid, solo=m.get('solo_fve'), share=m.get('shapley_share'), loo=m.get('loo_drop'),
                 coef=m.get('coefficient'), mdup=bool(m.get('dup')), ntok=nt[0], trunc=nt[1])
        RO[(cell, s)].append(b)
    for k in RO:
        RO[k].sort(key=lambda b: b['index'])

    # ---------------- 1. judge consistency (labels vs raw judge files)
    jc = {}
    for s in SET:
        V, D = judge_verdicts(s)
        n = agree = 0
        unit_agree = unit_n = 0
        hit_in_fail = 0
        pass_no_hit = 0
        for (cell, ss), bl in RO.items():
            if ss != s:
                continue
            item, grp, layer, pos = meta[cell]
            jp = V[vkey(item, layer, pos)]
            n += 1
            has_hit = any(b['lab'] == 'hit' for b in bl)
            if FAM == 'multihop_mt':
                hits, roles = D[(item, layer)]
                union = set()
                for b in bl:
                    union |= set(b['strict_roles'])
                for role in roles:
                    unit_n += 1
                    unit_agree += (role in union) == hits.get(role, False)
                agree += (jp == bl[0]['pass']) and (jp == all(r in union for r in roles))
            elif FAM == 'chain_intermediates':
                agree += (has_hit == jp) and (bl[0]['pass'] == jp)
            else:
                agree += (bl[0]['pass'] == jp)
                hit_in_fail += has_hit and not jp
                pass_no_hit += jp and not has_hit
        jc[DISP[s]] = {'readouts': n, 'label_file_agrees_with_raw_judge': agree,
                       'passing_readouts': sum(V[vkey(*meta[c][:1], *meta[c][2:])] for (c, ss) in RO if ss == s)}
        if FAM == 'multihop_mt':
            jc[DISP[s]]['required_units_union_of_bullets_equals_judge'] = f'{unit_agree}/{unit_n}'
        if FAM == 'role_bound_association':
            jc[DISP[s]]['hit_bullet_in_failed_readout'] = hit_in_fail
            jc[DISP[s]]['passing_readouts_with_no_hit_bullet(unlocated)'] = pass_no_hit
    R['judge_consistency'] = jc
    log('judge consistency', json.dumps(jc))

    # ---------------- position-demeaned solo (mean over setting x layer x index x readout size)
    strat = collections.defaultdict(list)
    for (cell, s), bl in RO.items():
        layer = meta[cell][2]
        for b in bl:
            if b['solo'] is not None and b['has_vec']:
                strat[(s, layer, b['index'], len(bl))].append(b['solo'])
    smean = {k: float(np.mean(v)) for k, v in strat.items()}
    for (cell, s), bl in RO.items():
        layer = meta[cell][2]
        for b in bl:
            b['solo_pd'] = (b['solo'] - smean[(s, layer, b['index'], len(bl))]) if b['solo'] is not None and b['has_vec'] else None

    def usable(b):
        return b['solo'] is not None and b['has_vec'] and not b['dup'] and not b['mdup']

    def within_pairs(s, is_a, is_b, score, extra=lambda a, b: True, only=None):
        pairs = []
        nread = 0
        for (cell, ss), bl in RO.items():
            if ss != s:
                continue
            if only is not None and not only(bl):
                continue
            bl2 = [b for b in bl if usable(b)]
            A = [b for b in bl2 if is_a(b)]
            B = [b for b in bl2 if is_b(b)]
            got = False
            for a in A:
                for b in B:
                    if a is b or not extra(a, b):
                        continue
                    sa, sb = score(a), score(b)
                    if sa is None or sb is None:
                        continue
                    pairs.append((meta[cell][1], sa, sb))
                    got = True
            nread += got
        res = pair_rate(pairs)
        if res:
            res['readouts'] = nread
        return res

    solo = lambda b: b['solo']
    share = lambda b: b['share']
    solo_pd = lambda b: b['solo_pd']
    lenm = lambda a, b: a['ntok'] and b['ntok'] and abs(math.log(a['ntok'] / b['ntok'])) < math.log(1.2)
    is_hit = lambda b: b['lab'] == 'hit'
    if FAM == 'multihop_mt':
        is_non = lambda b: b['lab'] in ('miss', 'wrong-specific')
    elif FAM == 'chain_intermediates':
        is_non = lambda b: b['lab'] in ('miss', 'answer', 'wrong_specific')
    else:
        is_non = lambda b: b['lab'] == 'miss_pass_other'

    # ---------------- 2. bullet-level headline
    BL = {}
    for s in SET:
        d = {}
        d['hit_vs_nonhit_solo_raw'] = within_pairs(s, is_hit, is_non, solo)
        d['hit_vs_nonhit_share_raw'] = within_pairs(s, is_hit, is_non, share)
        d['hit_vs_nonhit_solo_posdemeaned'] = within_pairs(s, is_hit, is_non, solo_pd)
        d['hit_vs_nonhit_solo_raw_tokmatched20'] = within_pairs(s, is_hit, is_non, solo, lenm)
        d['hit_vs_nonhit_solo_posdemeaned_tokmatched20'] = within_pairs(s, is_hit, is_non, solo_pd, lenm)
        d['hit_has_more_scored_tokens'] = within_pairs(s, is_hit, is_non, lambda b: b['ntok'])
        d['hit_sits_later_in_list'] = within_pairs(s, is_hit, is_non, lambda b: b['index'])
        d['hit_vs_nonhit_solo_raw_hit_earlier'] = within_pairs(s, is_hit, is_non, solo,
                                                               lambda a, b: a['index'] < b['index'])
        d['hit_vs_nonhit_solo_raw_hit_later'] = within_pairs(s, is_hit, is_non, solo,
                                                             lambda a, b: a['index'] > b['index'])
        d['hit_vs_nonhit_coef_positive'] = within_pairs(s, is_hit, is_non, lambda b: float((b['coef'] or 0) > 0))
        # top-share bullet is a hit, vs chance
        obs_g = collections.defaultdict(float)
        ch_g = collections.defaultdict(float)
        n_g = collections.defaultdict(float)
        for (cell, ss), bl in RO.items():
            if ss != s:
                continue
            bl2 = [b for b in bl if usable(b) and b['share'] is not None and (is_hit(b) or is_non(b))]
            nh = sum(is_hit(b) for b in bl2)
            if nh == 0 or nh == len(bl2):
                continue
            top = max(bl2, key=lambda b: b['share'])
            g = meta[cell][1]
            obs_g[g] += is_hit(top)
            ch_g[g] += nh / len(bl2)
            n_g[g] += 1
        gs = sorted(n_g)
        d['top_share_bullet_is_hit'] = boot_ratio([obs_g[g] for g in gs], [n_g[g] for g in gs])
        d['top_share_chance'] = boot_ratio([ch_g[g] for g in gs], [n_g[g] for g in gs])
        d['top_share_minus_chance'] = boot_ratio([obs_g[g] - ch_g[g] for g in gs], [n_g[g] for g in gs])
        # mean solo by list index (order confound, esp. Combine 32)
        by_idx = collections.defaultdict(list)
        hit_idx = collections.Counter()
        non_idx = collections.Counter()
        for (cell, ss), bl in RO.items():
            if ss != s:
                continue
            for b in bl:
                if usable(b):
                    by_idx[b['index']].append(b['solo'])
                    if is_hit(b):
                        hit_idx[b['index']] += 1
                    elif is_non(b):
                        non_idx[b['index']] += 1
        d['mean_solo_by_index'] = {int(i): round(float(np.mean(v)), 4) for i, v in sorted(by_idx.items())}
        d['hit_bullets_by_index'] = {int(k): v for k, v in sorted(hit_idx.items())}
        d['compared_nonhit_bullets_by_index'] = {int(k): v for k, v in sorted(non_idx.items())}
        BL[DISP[s]] = d
        log('bullet', s, json.dumps({k: v for k, v in d.items() if k.startswith('hit_vs')})[:600])
    R['bullet_level'] = BL

    # pooled over settings (solo, pos-demeaned; and token-matched raw)
    pooled = {}
    for nm, sc, ex in [('solo_posdemeaned', solo_pd, lambda a, b: True), ('solo_raw', solo, lambda a, b: True),
                       ('solo_raw_tokmatched20', solo, lenm), ('share_raw', share, lambda a, b: True),
                       ('solo_posdemeaned_tokmatched20', solo_pd, lenm)]:
        pairs = []
        for (cell, s), bl in RO.items():
            bl2 = [b for b in bl if usable(b)]
            for a in bl2:
                if not is_hit(a):
                    continue
                for b in bl2:
                    if is_non(b) and ex(a, b) and sc(a) is not None and sc(b) is not None:
                        pairs.append((meta[cell][1], sc(a), sc(b)))
        pooled[nm] = pair_rate(pairs)
    # hallucination-study convention: position-demeaned solo for Original / Best of 32, raw solo for Combine 32
    for nm, ex in [('HEADLINE_solo_pd_OrigBest_raw_Combine', lambda a, b: True),
                   ('HEADLINE_solo_pd_OrigBest_raw_Combine_tokmatched20', lenm)]:
        pairs = []
        for (cell, s), bl in RO.items():
            sc = solo if s == 'pooled_greedy_swap-n32' else solo_pd
            bl2 = [b for b in bl if usable(b)]
            for a in bl2:
                if not is_hit(a):
                    continue
                for b in bl2:
                    if is_non(b) and ex(a, b) and sc(a) is not None and sc(b) is not None:
                        pairs.append((meta[cell][1], sc(a), sc(b)))
        pooled[nm] = pair_rate(pairs)
    R['bullet_level_pooled_3_settings'] = pooled
    log('pooled', json.dumps(pooled))

    solo_pd0 = solo_pd
    # ---------------- 3. content vs correctness contrasts (family-specific)
    CC = {}
    for s in SET:
        c = {}
        solo_pd = solo if s == 'pooled_greedy_swap-n32' else solo_pd0  # Combine 32: order is greedy FVE order, use raw
        if FAM == 'multihop_mt':
            c['any_bridge_alias_vs_none_solo_adj'] = within_pairs(
                s, lambda b: b['lenient'] == 'hit', lambda b: b['lenient'] != 'hit', solo_pd)
            c['near_hit_(uncredited form)_vs_strict_hit_solo_adj'] = within_pairs(
                s, lambda b: b['near'], is_hit, solo_pd)
            c['near_hit_vs_plain_miss_solo_adj'] = within_pairs(
                s, lambda b: b['near'], lambda b: b['lab'] == 'miss' and not b['near'] and not b['tgt'], solo_pd)
            c['wrong_specific_(distractor)_vs_plain_miss_solo_adj'] = within_pairs(
                s, lambda b: b['lab'] == 'wrong-specific', lambda b: b['lab'] == 'miss' and not b['near'] and not b['tgt'], solo_pd)
            c['names_final_answer_vs_not_(neither names bridge)_solo_adj'] = within_pairs(
                s, lambda b: b['tgt'] and b['lenient'] != 'hit', lambda b: (not b['tgt']) and b['lenient'] != 'hit', solo_pd)
            c['hit_vs_nonhit_neither_names_final_answer_solo_adj'] = within_pairs(
                s, lambda b: is_hit(b) and not b['tgt'], lambda b: is_non(b) and not b['tgt'], solo_pd)
            c['hit_vs_nonhit_excluding_near_hits_solo_adj'] = within_pairs(
                s, is_hit, lambda b: is_non(b) and not b['near'], solo_pd)
        elif FAM == 'chain_intermediates':
            si = lambda b: b['stated'] in ('states_intermediate', 'derives_intermediate')
            so = lambda b: b['stated'] == 'states_other'
            sa = lambda b: b['stated'] == 'states_answer'
            c['judge_free_states_intermediate_vs_states_other_number_solo_adj'] = within_pairs(s, si, so, solo_pd)
            c['judge_free_states_intermediate_vs_states_other_number_tokmatched_solo'] = within_pairs(s, si, so, solo, lenm)
            c['judge_free_states_answer_vs_states_other_number_solo_adj'] = within_pairs(s, sa, so, solo_pd)
            c['judge_free_states_other_number_vs_states_none_solo_adj'] = within_pairs(
                s, so, lambda b: b['stated'] == 'states_none', solo_pd)
            c['carrier_vs_miss_in_HIT_readouts_solo_adj'] = within_pairs(
                s, is_hit, lambda b: b['lab'] == 'miss', solo_pd)
            c['carrier_vs_miss_in_WRONG_readouts_solo_adj'] = within_pairs(
                s, lambda b: b['lab'] == 'wrong_specific', lambda b: b['lab'] == 'miss', solo_pd)
            c['carrier_vs_miss_in_ANSWER_readouts_solo_adj'] = within_pairs(
                s, lambda b: b['lab'] == 'answer', lambda b: b['lab'] == 'miss', solo_pd)
            c['hit_vs_nonhit_excluding_number_only_bullets_solo_adj'] = within_pairs(
                s, lambda b: is_hit(b) and not b['num_only'], lambda b: is_non(b) and not b['num_only'], solo_pd)
            c['number_only_share_of_hit_bullets'] = round(np.mean([b['num_only'] for (cc, ss), bl in RO.items() if ss == s for b in bl if is_hit(b)]), 3)
            c['number_only_share_of_compared_nonhit_bullets'] = round(np.mean(
                [b['num_only'] for (cc, ss), bl in RO.items() if ss == s and any(is_hit(x) for x in bl) for b in bl if is_non(b)]), 3)
        else:
            c2 = lambda b: (b['ncomp'] or 0) >= 2
            c0 = lambda b: (b['ncomp'] or 0) == 0
            c['failed_readouts_names_2plus_parts_vs_0_solo_adj'] = within_pairs(
                s, c2, c0, solo_pd, only=lambda bl: not bl[0]['pass'])
            c['passing_readouts_names_2plus_parts_vs_0_solo_adj'] = within_pairs(
                s, c2, c0, solo_pd, only=lambda bl: bl[0]['pass'])
            c['relaxed_hit_vs_relaxed_miss_in_pass_readouts_solo_adj'] = within_pairs(
                s, lambda b: b['relaxed'] == 'hit', lambda b: b['relaxed'] != 'hit' and b['lab'] != 'excluded_unlocated',
                solo_pd, only=lambda bl: bl[0]['pass'])
            c['wrong_specific_vs_sibling_miss_in_failed_readouts_solo_adj'] = within_pairs(
                s, lambda b: b['lab'] == 'wrong_specific', lambda b: b['lab'] == 'miss_wrong_readout', solo_pd)
            c['hit_strict_vs_nonhit_solo_adj'] = within_pairs(
                s, lambda b: b['raw'] == 'hit_strict', is_non, solo_pd)
        CC[DISP[s]] = c
        log('content', s, json.dumps(c)[:800])
    R['content_vs_correctness'] = CC

    # cross-setting same-cell contrasts (raw solo comparable: same activation and whitener)
    X = {}
    cells = collections.defaultdict(dict)
    for (cell, s), bl in RO.items():
        cells[cell][s] = bl

    def cross_pairs(is_a, is_b, score=solo, ex=lambda a, b: True):
        pairs = []
        for cell, d in cells.items():
            A = {}
            B = {}
            for s, bl in d.items():
                for b in bl:
                    if not usable(b):
                        continue
                    ck = M[(cell, s, b['pid'])]['cache_key']
                    if is_a(b, bl):
                        A[ck] = b
                    elif is_b(b, bl):
                        B[ck] = b
            for ka, a in A.items():
                for kb, b in B.items():
                    if ka == kb or not ex(a, b):
                        continue
                    pairs.append((meta[cell][1], score(a), score(b)))
        return pair_rate(pairs)

    if FAM == 'multihop_mt':
        X['hit_vs_wrong_specific_any_setting_same_cell_solo'] = cross_pairs(
            lambda b, bl: b['lab'] == 'hit', lambda b, bl: b['lab'] == 'wrong-specific')
        X['hit_vs_bullets_of_failed_readouts_same_cell_solo'] = cross_pairs(
            lambda b, bl: b['lab'] == 'hit', lambda b, bl: not bl[0]['pass'])
    elif FAM == 'chain_intermediates':
        X['hit_carrier_vs_wrong_carrier_same_cell_solo'] = cross_pairs(
            lambda b, bl: b['lab'] == 'hit', lambda b, bl: b['lab'] == 'wrong_specific')
        X['hit_carrier_vs_wrong_carrier_same_cell_solo_tokmatched'] = cross_pairs(
            lambda b, bl: b['lab'] == 'hit', lambda b, bl: b['lab'] == 'wrong_specific', ex=lenm)
        X['judge_free_states_intermediate_vs_states_other_same_cell_solo'] = cross_pairs(
            lambda b, bl: b['stated'] in ('states_intermediate', 'derives_intermediate'),
            lambda b, bl: b['stated'] == 'states_other')
    else:
        X['hit_vs_wrong_specific_same_cell_solo'] = cross_pairs(
            lambda b, bl: b['lab'] == 'hit', lambda b, bl: b['lab'] == 'wrong_specific')
        X['hit_vs_failed_readout_bullet_naming_all_3_parts_same_cell_solo'] = cross_pairs(
            lambda b, bl: b['lab'] == 'hit', lambda b, bl: (not bl[0]['pass']) and (b['ncomp'] or 0) == 3)
        X['hit_vs_failed_readout_bullet_naming_all_3_parts_same_cell_solo_tokmatched'] = cross_pairs(
            lambda b, bl: b['lab'] == 'hit', lambda b, bl: (not bl[0]['pass']) and (b['ncomp'] or 0) == 3, ex=lenm)
    R['cross_setting_same_cell'] = X
    log('cross', json.dumps(X))

    # ---------------- 4. readout level
    RL = {}
    pass_of = {}
    for (cell, s), bl in RO.items():
        pass_of[(cell, s)] = bl[0]['pass']
    groups_of_cell = {c: meta[c][1] for c in cells}
    items_of_cell = {c: meta[c][0] for c in cells}
    for s in SET:
        n = sum(1 for c in cells)
        npass = sum(pass_of[(c, s)] for c in cells)
        items = collections.defaultdict(bool)
        for c in cells:
            items[items_of_cell[c]] |= pass_of[(c, s)]
        RL.setdefault('cell_pass', {})[DISP[s]] = f'{npass}/{n}'
        RL.setdefault('item_pass', {})[DISP[s]] = f'{sum(items.values())}/{len(items)}'
        fv = [readout_meta[(c, s)]['fve'] for c in cells if readout_meta[(c, s)]['fve'] is not None]
        RL.setdefault('mean_fve', {})[DISP[s]] = round(float(np.mean(fv)), 4)
    for s in SET[1:]:
        cs = [c for c in cells]
        RL.setdefault('cell_pass_change_vs_original', {})[DISP[s]] = boot_paired_diff(
            [groups_of_cell[c] for c in cs], [float(pass_of[(c, s)]) - float(pass_of[(c, SET[0])]) for c in cs])
        RL.setdefault('fixes_breaks_vs_original', {})[DISP[s]] = {
            'fixes': sum(pass_of[(c, s)] and not pass_of[(c, SET[0])] for c in cs),
            'breaks': sum(pass_of[(c, SET[0])] and not pass_of[(c, s)] for c in cs)}
    # higher-FVE readout of a discordant setting pair passes
    pairs = []
    for c in cells:
        for i in range(3):
            for j in range(i + 1, 3):
                a, b = SET[i], SET[j]
                fa, fb = readout_meta[(c, a)]['fve'], readout_meta[(c, b)]['fve']
                if fa is None or fb is None or pass_of[(c, a)] == pass_of[(c, b)]:
                    continue
                p, f = (a, b) if pass_of[(c, a)] else (b, a)
                pairs.append((groups_of_cell[c], readout_meta[(c, p)]['fve'], readout_meta[(c, f)]['fve']))
    RL['discordant_setting_pairs_passing_readout_has_higher_fve'] = pair_rate(pairs)
    # across items within layer (confounded by item); within item across layers/sites, demeaned
    pos_by_item = collections.defaultdict(set)
    for c in cells:
        pos_by_item[meta[c][0]].add(meta[c][3])
    site_off = {c: sorted(pos_by_item[meta[c][0]]).index(meta[c][3]) for c in cells}
    RL['n_sites_per_item'] = sorted({len(v) for v in pos_by_item.values()})
    for s in SET:
        sc, lab, st, gr, st2, st3 = [], [], [], [], [], []
        for c in cells:
            f = readout_meta[(c, s)]['fve']
            if f is None:
                continue
            item, g, layer, pos = meta[c]
            sc.append(f)
            lab.append(pass_of[(c, s)])
            gr.append(g)
            st.append((layer, site_off[c]) if FAM == 'role_bound_association' else layer)
            st2.append((item, layer) if FAM == 'role_bound_association' else item)
        RL.setdefault('auroc_pass_vs_fail_across_items_within_layer' + ('_and_site' if FAM == 'role_bound_association' else ''), {})[DISP[s]] = \
            boot_auroc_strata(sc, lab, [str(x) for x in st], gr)
        # within item (x layer for rba) across layers (sites), FVE demeaned by layer (site) mean
        m = collections.defaultdict(list)
        for x, k in zip(sc, st):
            m[str(k)].append(x)
        mm = {k: float(np.mean(v)) for k, v in m.items()}
        dm = [x - mm[str(k)] for x, k in zip(sc, st)]
        if FAM == 'role_bound_association':
            RL.setdefault('auroc_pass_vs_fail_within_item_x_layer_across_sites_RAW_not_demeaned', {})[DISP[s]] = \
                boot_auroc_strata(sc, lab, [str(x) for x in st2], gr)
            # per-site pass counts and mean FVE (site offset 0..18)
            ps = collections.defaultdict(lambda: [0, 0, 0.0])
            for x, l, k in zip(sc, lab, st):
                ps[k[1]][0] += l
                ps[k[1]][1] += 1
                ps[k[1]][2] += x
            RL.setdefault('by_site_offset_pass_n_meanfve', {})[DISP[s]] = {
                o: [v[0], v[1], round(v[2] / v[1], 4)] for o, v in sorted(ps.items())}
        RL.setdefault('auroc_pass_vs_fail_within_item' + ('_x_layer_across_sites_site_demeaned' if FAM == 'role_bound_association' else '_across_layers_layer_demeaned'), {})[DISP[s]] = \
            boot_auroc_strata(dm, lab, [str(x) for x in st2], gr)
    log('readout', json.dumps(RL)[:1500])

    # ---------------- 5. within-cell judged candidates (random picks) -- the cleanest readout-level test
    conds = ['capped_n1-n1'] + [f'random_complete-n{k}' for k in (1, 2, 4, 8, 16, 32)] + \
            [f'best_n_exact-n{k}' for k in (1, 2, 4, 8, 16, 32)]
    V = {cnd: judge_verdicts(cnd)[0] for cnd in conds}
    log('verdicts loaded')
    samp = collections.defaultdict(dict)  # cell -> sample -> dict
    trace = {}
    fve_mismatch = 0
    verdict_conflict = 0
    n_c = 0
    with open(PATHS['cands']) as f:
        for line in f:
            r = json.loads(line)
            cell = r['cell_id']
            if cell not in meta:
                continue
            item, g, layer, pos = meta[cell]
            if 'trace32' in r:
                tr = {t['sample_index']: t['score'] for t in r['trace32']}
                sels = r['selections']
            else:
                tr = {int(a): b for a, b in r['trace_best_n_exact_n32']}
                sels = r['candidates']
            trace[cell] = tr
            for sel in sels:
                cnd = sel['cond']
                if cnd not in V or len(sel['samples']) != 1:
                    continue
                k = vkey(item, layer, pos)
                if k not in V[cnd]:
                    continue
                si = sel['samples'][0]
                p = V[cnd][k]
                if sel.get('fve') is not None and tr.get(si) is not None and abs(sel['fve'] - tr[si]) > 1e-6:
                    fve_mismatch += 1
                d = samp[cell].setdefault(si, {'pass': p, 'conds': set(), 'fve': tr.get(si)})
                if d['pass'] != p:
                    verdict_conflict += 1
                d['conds'].add(cnd)
                n_c += 1
    CW = {'candidate_selections_used': n_c, 'cells': len(samp),
          'distinct_judged_samples': sum(len(v) for v in samp.values()),
          'condition_fve_ne_trace_score': fve_mismatch, 'same_sample_different_verdict': verdict_conflict}
    for nm, sel_fn in [('random_picks', lambda d: any(c.startswith(('capped', 'random')) for c in d['conds'])),
                       ('all_judged', lambda d: True)]:
        pairs = []
        cells_both = 0
        for cell, sd in samp.items():
            S = [d for d in sd.values() if sel_fn(d) and d['fve'] is not None]
            P = [d for d in S if d['pass']]
            F = [d for d in S if not d['pass']]
            if P and F:
                cells_both += 1
            for a in P:
                for b in F:
                    pairs.append((meta[cell][1], a['fve'], b['fve']))
        res = pair_rate(pairs)
        if res:
            res['cells_with_pass_and_fail'] = cells_both
        CW[f'auroc_within_cell_{nm}'] = res
    # FVE rank of random picks among the 32 trace samples: top half vs bottom half pass rate
    top_g = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for cell, sd in samp.items():
        tr = trace[cell]
        if not tr:
            continue
        vals = sorted(v for v in tr.values() if v is not None)
        for si, d in sd.items():
            if not any(c.startswith(('capped', 'random')) for c in d['conds']) or d['fve'] is None:
                continue
            pct = (np.searchsorted(vals, d['fve'], 'left') + np.searchsorted(vals, d['fve'], 'right')) / 2 / len(vals)
            g = meta[cell][1]
            if pct >= 0.5:
                top_g[g][0] += d['pass']
                top_g[g][1] += 1
            else:
                top_g[g][2] += d['pass']
                top_g[g][3] += 1
    gs = sorted(top_g)
    CW['random_picks_pass_rate_top_half_fve'] = boot_ratio([top_g[g][0] for g in gs], [top_g[g][1] for g in gs])
    CW['random_picks_pass_rate_bottom_half_fve'] = boot_ratio([top_g[g][2] for g in gs], [top_g[g][3] for g in gs])
    # best-of-32 pick vs random-of-32 pick, paired per cell
    diffs, grs = [], []
    for cell in cells:
        item, g, layer, pos = meta[cell]
        k = vkey(item, layer, pos)
        if k in V['best_n_exact-n32'] and k in V['random_complete-n32']:
            diffs.append(float(V['best_n_exact-n32'][k]) - float(V['random_complete-n32'][k]))
            grs.append(g)
    CW['best_of_32_minus_random_of_32_pass_rate'] = boot_paired_diff(grs, diffs)
    for k in (1, 2, 4, 8, 16, 32):
        CW.setdefault('pass_cells_best_vs_random_by_k', {})[k] = (
            sum(V[f'best_n_exact-n{k}'].values()), sum(V[f'random_complete-n{k}'].values()))
    # pooled over k = 2..32 (paired per cell and k)
    diffs, grs = [], []
    for k in (2, 4, 8, 16, 32):
        for cell in cells:
            item, g, layer, pos = meta[cell]
            kk = vkey(item, layer, pos)
            if kk in V[f'best_n_exact-n{k}'] and kk in V[f'random_complete-n{k}']:
                diffs.append(float(V[f'best_n_exact-n{k}'][kk]) - float(V[f'random_complete-n{k}'][kk]))
                grs.append(g)
    CW['best_of_k_minus_random_of_k_pass_rate_pooled_k2_to_32'] = boot_paired_diff(grs, diffs)
    # sample 0 (Original) vs random non-zero picks
    s0 = [(meta[c][1], float(d['pass'])) for c, sd in samp.items() for si, d in sd.items() if si == 0 and 'capped_n1-n1' in d['conds']]
    rnz = [(meta[c][1], float(d['pass'])) for c, sd in samp.items() for si, d in sd.items()
           if si != 0 and any(x.startswith('random') for x in d['conds'])]
    CW['pass_rate_sample0'] = boot_paired_diff([g for g, _ in s0], [x for _, x in s0])
    CW['pass_rate_random_nonzero_samples'] = boot_paired_diff([g for g, _ in rnz], [x for _, x in rnz])
    R['within_cell_candidates'] = CW
    log('cands', json.dumps(CW)[:1500])
    R['readout_level'] = RL

    OUT.write_text(json.dumps(R, indent=1, default=str))
    log('wrote', OUT)


if __name__ == '__main__':
    main()
