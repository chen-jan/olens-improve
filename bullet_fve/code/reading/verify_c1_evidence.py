"""Independent re-check of claim C1 (no separation of wrong vs clean bullets by per-bullet FVE).

Written from scratch against page/data/items/*.json (does not import synth_tests.py).
Exploratory. Chat-level percentile bootstrap (149 chats, 1000 reps, seed 12345).

Run: ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B verify_c1_evidence.py
"""
import collections
import glob
import json
import math
import os
import re
import sys

import numpy as np

DATA = '${OLENS_SCRATCH}/olens-bullet-fve/page/data'
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
SH = {'capped_n1-n1': 'Orig', 'best_n_exact-n32': 'Best', 'pooled_greedy_swap-n32': 'Comb'}
NREP = 1000
NUM = re.compile(r'\d+(?:[.,]\d+)*')


def sl16(s, a, e):
    b = s.encode('utf-16-le')
    return b[2 * max(0, a):2 * max(0, e)].decode('utf-16-le', errors='replace')


items = {}
B = []  # bullets
for f in sorted(glob.glob(os.path.join(DATA, 'items', '*.json'))):
    d = json.load(open(f))
    it = d['item']
    items[it['id']] = it
    ctx_nums = set(NUM.findall(it['prompt'] + ' ' + it['response']))
    for k, c in d['cells'].items():
        for sid in SIDS:
            s = c['settings'][sid]
            bl = s['bullets'] or []
            text = s['text'] or ''
            wr = [(a, e) for sp in s['spans'] if sp['verified'] and sp['type'] == 'wrong' for a, e in sp['offsets']]
            st = collections.defaultdict(collections.Counter)
            for cl in s.get('claims') or []:
                for j in cl.get('bullets') or []:
                    st[j][cl['status']] += 1
            for j, b in enumerate(bl):
                hits = [(max(a, b['start']), min(e, b['end'])) for a, e in wr if a < b['end'] and e > b['start']]
                r = dict(k=k, item=it['id'], sid=sid, L=c['layer'], site=c['site_kind'], src=it['source'],
                         j=j, n=len(bl), lab=b['label'], dup=b['dup'], solo=b['solo'], share=b['shap_share'],
                         coef=b['coef'], drop=b['drop'], fve=s['fve'], ro=s['label'] or 'empty',
                         blen=b['end'] - b['start'], nclaims=sum(st[j].values()), ntrue=st[j]['true'])
                if hits:
                    first = min(a for a, _ in hits) - b['start']
                    slen = max(1, b['scored_end'] - b['start'])
                    wtext = ' '.join(sl16(text, a, e) for a, e in hits)
                    r['w_head'] = first / slen < 1 / 3
                    r['w_frac'] = sum(e - a for a, e in hits) / max(1, r['blen'])
                    r['w_novel_num'] = any(x not in ctx_nums for x in NUM.findall(wtext))
                B.append(r)

ITEMS = sorted(items)
IX = {x: i for i, x in enumerate(ITEMS)}
rng = np.random.default_rng(12345)
W = np.stack([np.bincount(rng.integers(0, len(ITEMS), len(ITEMS)), minlength=len(ITEMS)) for _ in range(NREP)]).astype(float)

LAB = [r for r in B if r['lab'] in ('w', 'c', 'o') and not r['dup'] and r['share'] is not None]
print('bullets', len(B), 'labelled non-dup', len(LAB))
print('wrong bullets per setting', {SH[s]: sum(1 for r in B if r['sid'] == s and r['lab'] == 'w') for s in SIDS},
      'clean', {SH[s]: sum(1 for r in B if r['sid'] == s and r['lab'] == 'c') for s in SIDS})

# position adjustment 1: mid-rank percentile within (sid, j, n)
g = collections.defaultdict(list)
for r in LAB:
    g[(r['sid'], r['j'], r['n'])].append(r)
for grp in g.values():
    for sc in ('solo', 'share', 'drop'):
        v = np.array([x[sc] for x in grp], float)
        o = np.sort(v)
        p = (np.searchsorted(o, v, 'left') + np.searchsorted(o, v, 'right')) / 2 / len(v)
        for x, pp in zip(grp, p):
            x[sc + '_pa'] = float(pp)
    m = np.mean([x['solo'] for x in grp])
    for x in grp:
        x['solo_res'] = x['solo'] - m      # position adjustment 2: subtract (sid, j, n) mean

RO = collections.defaultdict(list)
for r in LAB:
    RO[(r['k'], r['sid'])].append(r)


def boot(num, den):
    est = num.sum() / den.sum()
    b = (W @ num) / (W @ den)
    b = b[np.isfinite(b)]
    return est, np.percentile(b, 2.5), np.percentile(b, 97.5), den.sum()


def pair_rate(sids, score, sw=lambda r: True, sc=lambda r: True, rsel=lambda b0: True, per_readout=False):
    num, den = np.zeros(len(ITEMS)), np.zeros(len(ITEMS))
    for (k, sid), bs in RO.items():
        if sid not in sids or not rsel(bs[0]):
            continue
        ws = [b for b in bs if b['lab'] == 'w' and sw(b)]
        cs = [b for b in bs if b['lab'] == 'c' and sc(b)]
        if not ws or not cs:
            continue
        acc = [1.0 if c[score] > w[score] else 0.5 if c[score] == w[score] else 0.0 for w in ws for c in cs]
        ix = IX[bs[0]['item']]
        if per_readout:
            num[ix] += np.mean(acc)
            den[ix] += 1
        else:
            num[ix] += sum(acc)
            den[ix] += len(acc)
    return boot(num, den)


def fmt(t):
    return f'{t[0]:.3f} [{t[1]:.3f}, {t[2]:.3f}] n={int(t[3])}'


def score_for(sid):
    return 'solo_pa' if sid != 'pooled_greedy_swap-n32' else 'solo'


print('\n== all wrong bullets: P(clean solo > wrong solo), same readout')
for sid in SIDS:
    sc = score_for(sid)
    print(SH[sid], 'claim-score', sc, fmt(pair_rate([sid], sc)),
          '| raw solo', fmt(pair_rate([sid], 'solo')),
          '| residual-adj', fmt(pair_rate([sid], 'solo_res')),
          '| per-readout weighted', fmt(pair_rate([sid], sc, per_readout=True)))
    print('    share(pa/raw)', fmt(pair_rate([sid], 'share_pa' if sid != 'pooled_greedy_swap-n32' else 'share')),
          '| drop(pa/raw)', fmt(pair_rate([sid], 'drop_pa' if sid != 'pooled_greedy_swap-n32' else 'drop')))

print('\n== by layer')
for sid in SIDS:
    sc = score_for(sid)
    print(SH[sid], ' | '.join(f'L{L}: ' + fmt(pair_rate([sid], sc, rsel=lambda b0, L=L: b0['L'] == L))
                             for L in (20, 36, 44, 52, 60)))

print('\n== by site kind / source')
for sid in SIDS:
    sc = score_for(sid)
    print(SH[sid], ' | '.join(f'{s}: ' + fmt(pair_rate([sid], sc, rsel=lambda b0, s=s: b0['site'] == s))
                             for s in ('clause', 'sentence', 'markup', 'newline', 'quote')))
    print(SH[sid], ' | '.join(f'{s}: ' + fmt(pair_rate([sid], sc, rsel=lambda b0, s=s: b0['src'] == s))
                             for s in ('dailydialog', 'lmsys')))

print('\n== by readout FVE tertile (tertiles over mixed hallucinated readouts)')
for sid in SIDS:
    sc = score_for(sid)
    mixed = [bs[0]['fve'] for (k, s2), bs in RO.items() if s2 == sid and bs[0]['ro'] == 'hallucinated'
             and any(b['lab'] == 'c' for b in bs)]
    q1, q2 = np.quantile(mixed, [1 / 3, 2 / 3])
    print(SH[sid], f'q=({q1:.3f},{q2:.3f})',
          'low', fmt(pair_rate([sid], sc, rsel=lambda b0: b0['fve'] < q1)),
          '| mid', fmt(pair_rate([sid], sc, rsel=lambda b0: q1 <= b0['fve'] < q2)),
          '| high', fmt(pair_rate([sid], sc, rsel=lambda b0: b0['fve'] >= q2)))

print('\n== against verified-true clean bullets (all located stage-2 claims true)')
vt = lambda r: r['nclaims'] > 0 and r['ntrue'] == r['nclaims']
for sid in SIDS:
    sc = score_for(sid)
    cl = [r for r in B if r['sid'] == sid and r['lab'] == 'c']
    print(SH[sid], 'frac clean verified-true', round(sum(vt(r) for r in cl) / len(cl), 4),
          fmt(pair_rate([sid], sc, sc=vt)))

print('\n== by error location / coverage / novel number (my own recomputation)')
for sid in SIDS:
    sc = score_for(sid)
    print(SH[sid], 'head', fmt(pair_rate([sid], sc, sw=lambda r: r.get('w_head') is True)),
          '| tail', fmt(pair_rate([sid], sc, sw=lambda r: r.get('w_head') is False)),
          '| cover>=60%', fmt(pair_rate([sid], sc, sw=lambda r: r.get('w_frac', 0) >= .6)),
          '| cover<25%', fmt(pair_rate([sid], sc, sw=lambda r: r.get('w_frac', 1) < .25)),
          '| novel num', fmt(pair_rate([sid], sc, sw=lambda r: r.get('w_novel_num') is True)))

print('\n== off-topic vs clean (power reference): P(clean > off-topic)')
for sid in SIDS:
    sc = score_for(sid)
    num, den = np.zeros(len(ITEMS)), np.zeros(len(ITEMS))
    for (k, s2), bs in RO.items():
        if s2 != sid:
            continue
        for o in [b for b in bs if b['lab'] == 'o']:
            for c in [b for b in bs if b['lab'] == 'c']:
                num[IX[c['item']]] += 1.0 if c[sc] > o[sc] else 0.5 if c[sc] == o[sc] else 0.0
                den[IX[c['item']]] += 1
    print(SH[sid], fmt(boot(num, den)))

print('\n== within-readout regression of solo on label + log length + position (simple version)')
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid]
    names = ['is_w', 'is_o', 'log_len'] + (['p2', 'p3', 'p4'] if sid != 'pooled_greedy_swap-n32' else [])
    X = np.array([[r['lab'] == 'w', r['lab'] == 'o', math.log(max(1, r['blen']))]
                  + ([r['j'] == 1, r['j'] == 2, r['j'] == 3] if sid != 'pooled_greedy_swap-n32' else [])
                  for r in R], float)
    Y = np.array([r['solo'] for r in R])
    grp = collections.defaultdict(list)
    for i, r in enumerate(R):
        grp[r['k']].append(i)
    Xd, Yd = X.copy(), Y.copy()
    for ii in grp.values():
        Xd[ii] -= X[ii].mean(0)
        Yd[ii] -= Y[ii].mean()
    ixs = np.array([IX[r['item']] for r in R])
    sd_len = Xd[:, 2].std()
    Xd[:, 2] /= sd_len

    def fit(w):
        ww = w[ixs]
        return np.linalg.solve(Xd.T @ (Xd * ww[:, None]), Xd.T @ (Yd * ww))
    est = fit(np.ones(len(ITEMS)))
    bs_ = np.array([fit(w) for w in W])
    r2_all = 1 - ((Yd - Xd @ est) ** 2).sum() / (Yd ** 2).sum()
    bw = np.linalg.lstsq(Xd[:, :1], Yd, rcond=None)[0]
    r2_w = 1 - ((Yd - Xd[:, :1] @ bw) ** 2).sum() / (Yd ** 2).sum()
    bwo = np.linalg.lstsq(Xd[:, :2], Yd, rcond=None)[0]
    r2_wo = 1 - ((Yd - Xd[:, :2] @ bwo) ** 2).sum() / (Yd ** 2).sum()
    # SD restricted to mixed readouts (where is_w varies)
    mixed_idx = [i for ii in grp.values() if len({R[i]['lab'] for i in ii} & {'w', 'c'}) == 2 for i in ii]
    print(SH[sid], 'n', len(R), 'within SD all', round(float(Yd.std()), 4), 'within SD mixed',
          round(float(Yd[mixed_idx].std()), 4), 'R2 full', round(float(r2_all), 4), 'R2 is_w only',
          round(float(r2_w), 5), 'R2 is_w+is_o', round(float(r2_wo), 5))
    for i, n in enumerate(names):
        print('   ', n, round(float(est[i]), 4), [round(float(x), 4) for x in np.percentile(bs_[:, i], [2.5, 97.5])])

print('\n== lowest-share bullet is wrong (mixed readouts), raw share and position-adjusted share')
for sid in SIDS:
    for sc in (['share', 'share_pa', 'solo', 'solo_pa'] if sid != 'pooled_greedy_swap-n32' else ['share', 'solo']):
        num, den, ch = np.zeros(len(ITEMS)), np.zeros(len(ITEMS)), np.zeros(len(ITEMS))
        for (k, s2), bs in RO.items():
            if s2 != sid or len(bs) < 2:
                continue
            nw = sum(b['lab'] == 'w' for b in bs)
            nc = sum(b['lab'] == 'c' for b in bs)
            if not (nw and nc):
                continue
            lo = min(bs, key=lambda b: b[sc])
            ix = IX[bs[0]['item']]
            num[ix] += lo['lab'] == 'w'
            den[ix] += 1
            ch[ix] += nw / len(bs)
        e = boot(num, den)
        c = boot(ch, den)
        print(SH[sid], sc, 'P(lowest is wrong)', fmt(e), '| chance', f'{c[0]:.3f}')

# examples
print('\n== example numbers')
for k, sid in [('chat-dailydialog-0045.L52.p65', 'capped_n1-n1'), ('chat-lmsys-0045.L44.p71', 'best_n_exact-n32'),
               ('chat-dailydialog-0019.L44.p145', 'best_n_exact-n32'), ('chat-dailydialog-0040.L36.p77', 'capped_n1-n1')]:
    bs = [r for r in B if r['k'] == k and r['sid'] == sid]
    print(k, SH[sid], [(r['j'], r['lab'], round(r['solo'], 3), round(r['share'], 3), round(r['coef'], 2),
                        round(r.get('solo_pa', float('nan')), 3)) for r in bs])

print('\n== within-readout regression with wrong split by error location / coverage (+ log len, position)')
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid]
    ob = sid != 'pooled_greedy_swap-n32'
    names = ['w_head', 'w_tail', 'w_cov60', 'is_o', 'log_len'] + (['p2', 'p3', 'p4'] if ob else [])
    X = np.array([[r['lab'] == 'w' and r.get('w_head') is True, r['lab'] == 'w' and r.get('w_head') is False,
                   r['lab'] == 'w' and r.get('w_frac', 0) >= .6, r['lab'] == 'o', math.log(max(1, r['blen']))]
                  + ([r['j'] == 1, r['j'] == 2, r['j'] == 3] if ob else []) for r in R], float)
    Y = np.array([r['solo'] for r in R])
    grp = collections.defaultdict(list)
    for i, r in enumerate(R):
        grp[r['k']].append(i)
    Xd, Yd = X.copy(), Y.copy()
    for ii in grp.values():
        Xd[ii] -= X[ii].mean(0)
        Yd[ii] -= Y[ii].mean()
    Xd[:, 4] /= Xd[:, 4].std()
    ixs = np.array([IX[r['item']] for r in R])

    def fit(w):
        ww = w[ixs]
        return np.linalg.solve(Xd.T @ (Xd * ww[:, None]), Xd.T @ (Yd * ww))
    est = fit(np.ones(len(ITEMS)))
    bs_ = np.array([fit(w) for w in W])
    print(SH[sid], ' | '.join(f'{n} {est[i]:.4f} [{np.percentile(bs_[:, i], 2.5):.4f}, {np.percentile(bs_[:, i], 97.5):.4f}]'
                              for i, n in enumerate(names[:4])),
          '| head-tail', f'{est[0]-est[1]:.4f} [{np.percentile(bs_[:, 0]-bs_[:, 1], 2.5):.4f}, {np.percentile(bs_[:, 0]-bs_[:, 1], 97.5):.4f}]')

print('\n== number of mixed readouts where the lowest-share bullet is wrong (counts)')
for sid in SIDS:
    n_mixed = n_low_w = 0
    for (k, s2), bs in RO.items():
        if s2 != sid or len(bs) < 2:
            continue
        if any(b['lab'] == 'w' for b in bs) and any(b['lab'] == 'c' for b in bs):
            n_mixed += 1
            n_low_w += min(bs, key=lambda b: b['share'])['lab'] == 'w'
    print(SH[sid], 'mixed', n_mixed, 'lowest-share is wrong', n_low_w)
