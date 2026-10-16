"""Confound checks for claim C2 (right frame, wrong filler). Exploratory, read-only on page data.

Re-uses the feature build of synth_tests.py (exec of its source up to the T1 block; nothing is written by that part),
then tests:
  A. novel-number/name bullets vs others: within-readout solo advantage after matching on length (and position)
  B. novel-number/name -> wrong: within-readout and within length strata; is the novel token inside the wrong span?
  C. among WRONG bullets: do high-share / high-solo ones have a better 'frame' (next-text overlap, first token,
     head Jaccard to clean siblings, error not in head) than low ones? compare with the same gradient in clean bullets
  D. within-readout next-text overlap, clean minus wrong, split by where the error sits
  E. judge consistency on identical bullet text across settings, novel-specific vs not
Writes reading/c2_confound_checks.json.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'synth_tests.py')).read()
cut = src.index('# ----------------------------------------------------------------------------- T1 no separation')
g = {'__file__': os.path.join(HERE, 'synth_tests.py'), '__name__': 'synth_part'}
exec(compile(src[:cut], 'synth_tests_part', 'exec'), g)
globals().update({k: v for k, v in g.items() if not k.startswith('__')})

import json, math, collections
import numpy as np

for r in LAB:
    r['b_novel_spec'] = float(r['b_novel_num'] or r['b_novel_name'])
    r['loglen'] = math.log(max(1, r['len']))
    r['logslen'] = math.log(max(1, r['scored_len']))
out = {}


def pair_rate_matched(sid, feat, score, match, labels=('w', 'c', 'o')):
    acc = []
    for (k, s2), bs in by_ro.items():
        if s2 != sid:
            continue
        bs = [b for b in bs if b['label'] in labels]
        for a in bs:
            for b in bs:
                if a is not b and a[feat] > b[feat] and match(a, b):
                    acc.append((a['ix'], win(a[score], b[score]), 1.0))
    return ratio_ci(*per_item(acc))


lenmatch = lambda a, b: abs(a['logslen'] - b['logslen']) < 0.15 and abs(a['loglen'] - b['loglen']) < 0.15
A = {}
for sid in SIDS:
    sc = 'solo_pa' if sid in OB else 'solo'
    A[SHORT[sid]] = {
        'novel_beats_none_raw_solo': feat_pair_rate([sid], 'b_novel_spec', 'solo'),
        'novel_beats_none_pos_adjusted' if sid in OB else 'novel_beats_none_(no position adj, Combine)':
            feat_pair_rate([sid], 'b_novel_spec', sc),
        'novel_longer_than_none_(full len)': feat_pair_rate([sid], 'b_novel_spec', 'len'),
        'novel_longer_than_none_(scored len)': feat_pair_rate([sid], 'b_novel_spec', 'scored_len'),
        'novel_later_position': feat_pair_rate([sid], 'b_novel_spec', 'j'),
        'novel_beats_none_length_matched_raw_solo': pair_rate_matched(sid, 'b_novel_spec', 'solo', lenmatch),
        'novel_beats_none_length_matched_' + sc: pair_rate_matched(sid, 'b_novel_spec', sc, lenmatch),
        'novel_beats_none_length_matched_clean_only': pair_rate_matched(sid, 'b_novel_spec', sc, lenmatch, ('c',)),
        'novel_beats_none_length_matched_wrong_only': pair_rate_matched(sid, 'b_novel_spec', sc, lenmatch, ('w',)),
    }


# within-readout regression solo ~ novel + controls
def wreg(sid, names, getx, y='solo', sel=lambda r: True):
    R = [r for r in LAB if r['sid'] == sid and sel(r)]
    X = np.array([getx(r) for r in R], float)
    Y = np.array([r[y] for r in R], float)
    idx = collections.defaultdict(list)
    for i, r in enumerate(R):
        idx[(r['k'], r['sid'])].append(i)
    Xd, Yd = X.copy(), Y.copy()
    for ii in idx.values():
        Xd[ii] -= X[ii].mean(0)
        Yd[ii] -= Y[ii].mean()
    ixs = np.array([r['ix'] for r in R])

    def fit(w):
        ww = w[ixs]
        return np.linalg.lstsq(Xd * np.sqrt(ww)[:, None], Yd * np.sqrt(ww), rcond=None)[0]

    est = fit(np.ones(len(ITEM_IDS)))
    boots = np.array([fit(w) for w in BOOTW[:400]])
    return {n: {'est': round(float(est[i]), 4), 'lo': round(float(np.percentile(boots[:, i], 2.5)), 4),
                'hi': round(float(np.percentile(boots[:, i], 97.5)), 4)} for i, n in enumerate(names)} | {
        'n': len(R), 'sd_y_within': round(float(Yd.std()), 4)}


for sid in SIDS:
    pos = (lambda r: [float(r['j'] == 1), float(r['j'] == 2), float(r['j'] == 3)]) if sid in OB else (lambda r: [])
    pn = ['pos2', 'pos3', 'pos4'] if sid in OB else []
    A[SHORT[sid]]['reg_solo_novel_only'] = wreg(sid, ['novel'], lambda r: [r['b_novel_spec']])
    A[SHORT[sid]]['reg_solo_novel+pos'] = wreg(sid, ['novel'] + pn, lambda r: [r['b_novel_spec']] + pos(r))
    A[SHORT[sid]]['reg_solo_novel+pos+len'] = wreg(
        sid, ['novel'] + pn + ['loglen', 'logslen', 'truncated'],
        lambda r: [r['b_novel_spec']] + pos(r) + [r['loglen'], r['logslen'], float(r['truncated'])])
    A[SHORT[sid]]['reg_solo_novel+pos+len+label'] = wreg(
        sid, ['novel'] + pn + ['loglen', 'logslen', 'truncated', 'is_w', 'is_o'],
        lambda r: [r['b_novel_spec']] + pos(r) + [r['loglen'], r['logslen'], float(r['truncated']),
                                                  float(r['label'] == 'w'), float(r['label'] == 'o')])
out['A_novel_specific_score_advantage'] = A

# ----------------------------------------------------------------- B novel -> wrong
B = {}
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid]
    # within readout: readouts holding both novel and non-novel bullets
    acc1, acc0 = [], []
    for (k, s2), bs in by_ro.items():
        if s2 != sid:
            continue
        nv = [b for b in bs if b['b_novel_spec']]
        nn = [b for b in bs if not b['b_novel_spec']]
        if nv and nn:
            for b in nv:
                acc1.append((b['ix'], float(b['label'] == 'w'), 1.))
            for b in nn:
                acc0.append((b['ix'], float(b['label'] == 'w'), 1.))
    n1, d1 = per_item(acc1)
    n0, d0 = per_item(acc0)
    B[SHORT[sid]] = {'within_mixed_readouts_p_wrong_novel': ratio_ci(n1, d1),
                     'within_mixed_readouts_p_wrong_none': ratio_ci(n0, d0),
                     'within_mixed_readouts_ratio': round(float((n1.sum() / d1.sum()) / (n0.sum() / d0.sum())), 3)}
    # length tertiles (full length)
    qs = np.quantile([r['len'] for r in R], [1 / 3, 2 / 3])
    for nm, lo, hi in (('short', -1, qs[0]), ('mid', qs[0], qs[1]), ('long', qs[1], 1e9)):
        sel = [r for r in R if lo < r['len'] <= hi]
        p1 = prop(sel, lambda r: r['label'] == 'w', lambda r: r['b_novel_spec'] == 1)
        p0 = prop(sel, lambda r: r['label'] == 'w', lambda r: r['b_novel_spec'] == 0)
        B[SHORT[sid]][f'len_{nm}_p_wrong_novel_vs_none'] = [p1, p0, round(p1['est'] / p0['est'], 2)]
    # novel token inside the wrong span?
    W = [r for r in R if r['label'] == 'w' and 'w_text' in r and r['b_novel_spec']]
    B[SHORT[sid]]['wrong_novel_bullets_novel_token_inside_wrong_span'] = prop(
        W, lambda r: bool(r['w_novel_num'] or r['w_novel_name']))
    B[SHORT[sid]]['p_wrong_by_source_novel_vs_none'] = {
        s: [prop(R, lambda r: r['label'] == 'w', lambda r, s=s: r['b_novel_spec'] == 1 and r['source'] == s)['est'],
            prop(R, lambda r: r['label'] == 'w', lambda r, s=s: r['b_novel_spec'] == 0 and r['source'] == s)['est']]
        for s in ('dailydialog', 'lmsys')}
    # wrong rate in pure readout terms: share of hallucinated readouts among novel vs none bullets
    B[SHORT[sid]]['p_bullet_in_hallucinated_readout_novel_vs_none'] = [
        prop(R, lambda r: r['readout'] == 'hallucinated', lambda r: r['b_novel_spec'] == 1)['est'],
        prop(R, lambda r: r['readout'] == 'hallucinated', lambda r: r['b_novel_spec'] == 0)['est']]
out['B_novel_to_wrong'] = B

# ----------------------------------------------------------------- C frame gradient among wrong vs clean bullets
heads = {(r['k'], r['sid'], r['j']): toks(r['text'])[:8] for r in LAB}


def jacc(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else np.nan


for r in LAB:
    cs = [b for b in by_ro[(r['k'], r['sid'])] if b['label'] == 'c' and b is not r]
    v = [jacc(heads[(r['k'], r['sid'], r['j'])], heads[(r['k'], r['sid'], b['j'])]) for b in cs]
    v = [x for x in v if not math.isnan(x)]
    r['jac_clean_sib'] = float(np.mean(v)) if v else np.nan
C = {}
for sid in SIDS:
    C[SHORT[sid]] = {}
    for lab in ('w', 'c'):
        for sc in (['share', 'solo', 'solo_pa', 'share_pa'] if sid in OB else ['share', 'solo']):
            Rl = [r for r in LAB if r['sid'] == sid and r['label'] == lab]
            q20, q80 = np.quantile([r[sc] for r in Rl], [.2, .8])
            top = [r for r in Rl if r[sc] >= q80]
            bot = [r for r in Rl if r[sc] <= q20]
            res = {}
            for f in ('nxt_ov', 'first_eq', 'jac_clean_sib', 'prv_ov'):
                nt, dt = per_item((r['ix'], r[f], 1.) for r in top if not math.isnan(r[f]))
                nb, db = per_item((r['ix'], r[f], 1.) for r in bot if not math.isnan(r[f]))
                res[f] = {'top': ratio_ci(nt, dt)['est'], 'bottom': ratio_ci(nb, db)['est'],
                          'top_minus_bottom': diff_ci(nt, dt, nb, db)}
            if lab == 'w':
                for f, fn in (('err_in_head', lambda r: r.get('w_loc') == 'head'),
                              ('slot_like', lambda r: r.get('wkind') in ('novel_number', 'novel_capitalised_name',
                                                                         'short_other(<=4 words)')),
                              ('w_frac', lambda r: r.get('w_frac', np.nan))):
                    tt = [r for r in top if 'w_text' in r]
                    bb = [r for r in bot if 'w_text' in r]
                    nt, dt = per_item((r['ix'], float(fn(r)), 1.) for r in tt)
                    nb, db = per_item((r['ix'], float(fn(r)), 1.) for r in bb)
                    res[f] = {'top': ratio_ci(nt, dt)['est'], 'bottom': ratio_ci(nb, db)['est'],
                              'top_minus_bottom': diff_ci(nt, dt, nb, db)}
            C[SHORT[sid]][f'{lab}_{sc}_quintiles'] = res
    # within-readout: among wrong bullets only / clean only, does higher nxt_ov give higher solo?
    sc = 'solo'
    C[SHORT[sid]]['pair_rate_higher_nxt_ov_higher_solo_wrong_only'] = feat_pair_rate([sid], 'nxt_ov', sc,
                                                                                     labels=('w',))
    C[SHORT[sid]]['pair_rate_higher_nxt_ov_higher_solo_clean_only'] = feat_pair_rate([sid], 'nxt_ov', sc,
                                                                                     labels=('c',))
    # cross-label: wrong bullet with higher nxt_ov than clean sibling -> does it beat it?
    C[SHORT[sid]]['pair_rate_clean_beats_wrong_when_wrong_has_higher_nxt_ov'] = label_pair_rate(
        [sid], 'solo_pa' if sid in OB else 'solo') if False else None
out['C_frame_gradient'] = C

# ----------------------------------------------------------------- D within-readout nxt_ov clean minus wrong by w_loc
D = {}
for sid in SIDS:
    D[SHORT[sid]] = {}
    for loc in ('all', 'head', 'tail', 'unscored'):
        acc = []
        for (k, s2), bs in by_ro.items():
            if s2 != sid:
                continue
            cs = [b for b in bs if b['label'] == 'c' and not math.isnan(b['nxt_ov'])]
            ws = [b for b in bs if b['label'] == 'w' and not math.isnan(b['nxt_ov'])
                  and (loc == 'all' or b.get('w_loc') == loc)]
            for w in ws:
                for c in cs:
                    acc.append((w['ix'], c['nxt_ov'] - w['nxt_ov'], 1.))
        D[SHORT[sid]][f'mean_nxt_ov_clean_minus_wrong_same_readout_{loc}'] = ratio_ci(*per_item(acc))
    # pooled means for reference
    for lab in ('c', 'w', 'o'):
        D[SHORT[sid]][f'pooled_nxt_ov_{lab}'] = prop([r for r in LAB if r['sid'] == sid and not math.isnan(r['nxt_ov'])],
                                                     lambda r: r['nxt_ov'], lambda r, lab=lab: r['label'] == lab)['est']
    # readout-level: mean nxt_ov of the readout by readout label
    for rl in ('hallucinated', 'consistent'):
        D[SHORT[sid]][f'pooled_nxt_ov_all_bullets_in_{rl}_readouts'] = prop(
            [r for r in LAB if r['sid'] == sid and not math.isnan(r['nxt_ov'])], lambda r: r['nxt_ov'],
            lambda r, rl=rl: r['readout'] == rl)['est']
    D[SHORT[sid]]['pooled_nxt_ov_clean_in_hallucinated_readouts'] = prop(
        [r for r in LAB if r['sid'] == sid and not math.isnan(r['nxt_ov'])], lambda r: r['nxt_ov'],
        lambda r: r['readout'] == 'hallucinated' and r['label'] == 'c')['est']
out['D_next_text_overlap'] = D

# ----------------------------------------------------------------- E judge consistency on identical text, novel vs not
E = {}
bytext = collections.defaultdict(list)
for r in LAB:
    bytext[(r['k'], r['text'].strip())].append(r)
acc = {1.0: [], 0.0: []}
accw = {1.0: [], 0.0: []}
for key, rs in bytext.items():
    sids = {}
    for r in rs:
        sids.setdefault(r['sid'], r)
    rs = list(sids.values())
    if len(rs) < 2:
        continue
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)):
            a, b = rs[i], rs[j]
            nv = a['b_novel_spec']
            acc[nv].append((a['ix'], float(a['label'] == b['label']), 1.))
            if a['label'] == 'w' or b['label'] == 'w':
                accw[nv].append((a['ix'], float(a['label'] == b['label'] == 'w'), 1.))
E['identical_text_label_agreement_novel'] = ratio_ci(*per_item(acc[1.0]))
E['identical_text_label_agreement_none'] = ratio_ci(*per_item(acc[0.0]))
E['identical_text_both_wrong_given_either_wrong_novel'] = ratio_ci(*per_item(accw[1.0]))
E['identical_text_both_wrong_given_either_wrong_none'] = ratio_ci(*per_item(accw[0.0]))
out['E_judge_consistency_identical_text'] = E

with open(os.path.join(HERE, 'c2_confound_checks.json'), 'w') as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False, default=lambda x: x.item() if isinstance(x, np.generic) else x)
print(json.dumps(out, indent=1, ensure_ascii=False, default=lambda x: x.item() if isinstance(x, np.generic) else x))
