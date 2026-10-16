"""Step 4: descriptive findings on per-token heat.
- where positive heat sits (first token, last token, token classes, relative position), per setting
- wrong bullets: share of the bullet's positive heat on the judge's verified wrong-span tokens vs the share of
  scored tokens they occupy; position-matched baseline from clean bullets; chat-level (item) bootstrap CIs.
Offsets: page spans/bullets are UTF-16 code units in the readout text; heat ends are Python code points in
scored_text. Converted via an explicit code-point <-> UTF-16 map and checked against scored_text."""
import collections
import json
import re
import unicodedata
from pathlib import Path

import numpy as np

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
HEAT = ROOT / 'heat'
OUT = HEAT / 'verify'
PAGE = ROOT / 'page/data/items'
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
B = 2000
EPS = 1e-7  # heat is from 7-decimal rounded joints

STOP = set("""a an the and or but if then else of to in on at by for with from as into onto over under about
above below up down out off than so such no not nor only own same too very can could will would shall should may
might must do does did doing done be is am are was were been being have has had having i me my mine myself we us
our ours ourselves you your yours yourself yourselves he him his himself she her hers herself it its itself they
them their theirs themselves what which who whom whose this that these those here there when where why how all any
both each few more most other some just also again further once s t d ll m o re ve y don't i'm it's that's
there's you're i've i'd i'll we're they're can't won't isn't aren't wasn't weren't doesn't didn't let's
don didn doesn isn aren wasn weren won wouldn couldn shouldn haven hasn hadn""".split())
CONTRACTION = {"'s", "'m", "'re", "'ll", "'ve", "'d", "n't", "'t", "’s", "’m", "’re", "’ll", "’ve", "’d", "n’t", "’t"}


def piece_class(p):
    if p == '':
        return 'partial_char'
    s = p.strip()
    if s == '':
        return 'whitespace'
    if any(ch.isalpha() for ch in s):
        if any(ord(ch) > 0x2E7F and ch.isalpha() for ch in s) or any(
                ch.isalpha() and not ('LATIN' in unicodedata.name(ch, '') or ch.isascii()) for ch in s):
            return 'non_latin_word'
        low = s.lower()
        if low in STOP or low in CONTRACTION or low.replace('’', "'") in STOP:
            return 'function_word'
        return 'content_word'
    if any(ch.isdigit() for ch in s):
        return 'number'
    if any(unicodedata.category(ch) in ('So', 'Cf', 'Mn') or ord(ch) >= 0x1F000 for ch in s):
        return 'emoji_symbol'
    return 'punct'


def u16_maps(text):
    """code point index -> utf16 index (len+1 entries), and inverse dict."""
    cp2u = [0]
    for ch in text:
        cp2u.append(cp2u[-1] + (2 if ord(ch) > 0xFFFF else 1))
    u2cp = {u: i for i, u in enumerate(cp2u)}
    return cp2u, u2cp


def boot_ratio(item_idx, num, den, n_items, rng, B=B):
    """Ratio-of-sums statistic sum(num)/sum(den) with item-level bootstrap. Returns est, lo, hi."""
    sn = np.bincount(item_idx, weights=num, minlength=n_items)
    sd = np.bincount(item_idx, weights=den, minlength=n_items)
    est = sn.sum() / sd.sum()
    W = rng.multinomial(n_items, np.full(n_items, 1 / n_items), size=B).astype(float)
    bs = (W @ sn) / (W @ sd)
    return float(est), float(np.quantile(bs, .025)), float(np.quantile(bs, .975))


def boot_mean(item_idx, vals, n_items, rng):
    return boot_ratio(item_idx, vals, np.ones_like(vals), n_items, rng)


def fmt_tokens(pieces, heat, mark=None, top=None):
    out = []
    for k, (p, h) in enumerate(zip(pieces, heat)):
        s = p.replace('\n', '\\n')
        tag = f'{s}({h * 1e3:+.2f})'
        if mark is not None and mark[k]:
            tag = '[' + tag + ']'
        out.append(tag)
    return ' '.join(out)


def main():
    rng = np.random.default_rng(20261015)
    cells = {}
    for l in open(ROOT / 'inputs/hall_three_settings.jsonl'):
        c = json.loads(l)
        cells[c['cell_id']] = c
    metrics = {}
    for line in open(ROOT / 'metrics/bullet_metrics.jsonl'):
        m = json.loads(line)
        for st, sm in m['settings'].items():
            for j, b in enumerate(sm['bullets']):
                metrics[(m['cell_id'], st, j)] = b
    pages = {}
    for p in PAGE.glob('*.json'):
        d = json.loads(p.read_text())
        pages[d['item']['id']] = d
    items = sorted({c['item_id'] for c in cells.values()})
    item_ix = {it: i for i, it in enumerate(items)}
    NI = len(items)

    recs = []
    conv = collections.Counter()
    for line in open(HEAT / 'token_heat.jsonl'):
        r = json.loads(line)
        c = cells[r['cell_id']]
        st = r['setting']
        j = r['bullet']
        a = c['settings'][st]['atoms'][j]
        pkey = f"{c['item_id']}.L{c['layer']}.p{c['position']}"
        ps = pages[c['item_id']]['cells'][pkey]['settings'][st]
        text = ps['text']
        assert text == c['settings'][st]['text']
        pb = ps['bullets'][j]
        cp2u, u2cp = u16_maps(text)
        cs = u2cp[pb['start']]
        sc = a['scored_text']
        assert text[cs:cs + len(sc)] == sc, (r['cell_id'], st, j)
        assert u2cp[pb['end']] == cs + len(sc)
        conv['bullets_mapped'] += 1
        n = r['n_scored']
        ends = r['ends_in_scored_text']
        starts = [0] + ends[:-1]
        wrong = np.zeros(n, bool)
        off = np.zeros(n, bool)
        span_scored_chars = 0
        span_unscored_only = False
        for sp in ps['spans']:
            if not sp['verified']:
                continue
            for a16, b16 in sp['offsets']:
                if a16 not in u2cp or b16 not in u2cp:
                    conv['span_offset_not_on_cp_boundary'] += 1
                    continue
                lo, hi = u2cp[a16] - cs, u2cp[b16] - cs
                if hi <= 0 or lo >= len(sc):
                    continue  # other bullet
                conv[f'span_occ_in_bullet_{sp["type"]}'] += 1
                # sanity: the located text is the span text up to normalisation
                lo_c, hi_c = max(lo, 0), min(hi, len(sc))
                mask = wrong if sp['type'] == 'wrong' else off
                any_tok = False
                for k in range(n):
                    s0, e0 = starts[k], ends[k]
                    hit = (max(s0, lo_c) < min(e0, hi_c)) if e0 > s0 else (lo_c <= s0 < hi_c)
                    if hit:
                        mask[k] = True
                        any_tok = True
                if sp['type'] == 'wrong' and not any_tok:
                    conv['wrong_span_occ_only_unscored'] += 1
        heat = np.array(r['heat'])
        solo = np.array(r['solo'])
        mb = metrics[(r['cell_id'], st, j)]
        recs.append({'cell_id': r['cell_id'], 'key': pkey, 'item': item_ix[c['item_id']], 'setting': st, 'bullet': j,
                     'layer': c['layer'], 'label': pb['label'], 'dup': r['dup_in_readout'] or pb['dup'],
                     'truncated': r['truncated'], 'n': n, 'pieces': r['pieces'], 'heat': heat, 'solo': solo,
                     'joint0': r['joint'][0], 'drift': r['drift'], 'loo': mb['loo_drop'], 'coef': mb['coefficient'],
                     'wrong': wrong, 'off': off, 'cls': [piece_class(p) for p in r['pieces']]})
    print('converted', dict(conv), flush=True)

    res = {'conversion': dict(conv)}
    # ------------------------------------------------------------------ global heat character
    glob = {}
    for st in SETTINGS + ('all',):
        R = [x for x in recs if st == 'all' or x['setting'] == st]
        H = np.concatenate([x['heat'] for x in R])
        pos = np.clip(H, 0, None).sum()
        neg = -np.clip(H, None, 0).sum()
        zero_b = sum(1 for x in R if np.abs(x['heat']).max() < EPS)
        nonzero = [x for x in R if np.clip(x['heat'], 0, None).sum() > EPS]
        net = np.array([x['heat'].sum() for x in nonzero])
        gross = np.array([np.clip(x['heat'], 0, None).sum() for x in nonzero])
        drift_rel = np.array([abs(x['drift']) / max(abs(x['loo']), 1e-12) for x in R if abs(x['loo']) > 1e-4])
        glob[st] = {'bullets': len(R), 'tokens': int(H.size),
                    'frac_tokens_zero_heat': float((np.abs(H) < EPS).mean()),
                    'frac_tokens_negative': float((H < -EPS).mean()), 'frac_tokens_positive': float((H > EPS).mean()),
                    'sum_neg_over_sum_pos': float(neg / pos), 'bullets_all_zero_heat': zero_b,
                    'frac_bullets_all_zero_heat': zero_b / len(R),
                    'frac_bullets_loo_zero': float(np.mean([abs(x['loo']) < 1e-9 for x in R])),
                    'median_net_over_gross_pos': float(np.median(net / gross)),
                    'bullets_with_pos_heat': len(nonzero),
                    'median_abs_drift_over_loo_(loo>1e-4)': float(np.median(drift_rel)),
                    'frac_abs_drift_gt_0.25_loo_(loo>1e-4)': float((drift_rel > 0.25).mean())}
    res['global'] = glob

    # ------------------------------------------------------------------ concentration / position / classes
    CLASSES = ['content_word', 'function_word', 'punct', 'whitespace', 'number', 'emoji_symbol', 'non_latin_word',
               'partial_char']
    conc = {}
    for st in SETTINGS:
        R = [x for x in recs if x['setting'] == st and not x['dup'] and np.clip(x['heat'], 0, None).sum() > EPS]
        top1, n50, first, last, firstexp, lastexp = [], [], [], [], [], []
        last_punct, last_punct_exp = [], []
        dec = np.zeros(10); dec_tok = np.zeros(10)
        cls_heat = collections.Counter(); cls_tok = collections.Counter(); cls_cnt_b = 0
        lockin = []
        onset_frac, onset_share, zero_after_onset = [], [], []
        for x in R:
            p = np.clip(x['heat'], 0, None)
            sh = p / p.sum()
            n = x['n']
            srt = np.sort(sh)[::-1]
            top1.append(srt[0])
            n50.append((np.searchsorted(np.cumsum(srt), 0.5) + 1) / n)
            first.append(sh[0]); firstexp.append(1 / n)
            last.append(sh[-1]); lastexp.append(1 / n)
            if not x['truncated'] and x['cls'][-1] == 'punct':
                last_punct.append(sh[-1]); last_punct_exp.append(1 / n)
            d = np.minimum((np.arange(n) * 10) // n, 9)
            dec += np.bincount(d, weights=sh, minlength=10)
            dec_tok += np.bincount(d, minlength=10) / n
            for k, cl in enumerate(x['cls']):
                cls_heat[cl] += sh[k]
                cls_tok[cl] += 1 / n
            cls_cnt_b += 1
            nzk = np.nonzero(np.abs(x['heat']) > EPS)[0]
            k0 = int(nzk[0])
            onset_frac.append(k0 / n)
            onset_share.append(sh[k0])
            s = x['solo']
            if s[-1] > 1e-6:
                lockin.append((np.argmax(s >= 0.9 * s[-1]) + 1) / n)
        conc[st] = {'bullets': len(R), 'mean_top1_share': float(np.mean(top1)),
                    'median_top1_share': float(np.median(top1)),
                    'median_frac_tokens_for_50pct': float(np.median(n50)),
                    'mean_first_token_share': float(np.mean(first)), 'mean_first_token_uniform': float(np.mean(firstexp)),
                    'mean_last_token_share': float(np.mean(last)), 'mean_last_token_uniform': float(np.mean(lastexp)),
                    'final_punct_bullets': len(last_punct),
                    'mean_final_punct_share': float(np.mean(last_punct)) if last_punct else None,
                    'mean_final_punct_uniform': float(np.mean(last_punct_exp)) if last_punct else None,
                    'decile_heat_share': (dec / cls_cnt_b).round(4).tolist(),
                    'decile_token_share': (dec_tok / cls_cnt_b).round(4).tolist(),
                    'class_heat_share': {cl: round(cls_heat[cl] / cls_cnt_b, 4) for cl in CLASSES},
                    'class_token_share': {cl: round(cls_tok[cl] / cls_cnt_b, 4) for cl in CLASSES},
                    'class_lift': {cl: round(cls_heat[cl] / cls_tok[cl], 3) if cls_tok[cl] else None for cl in CLASSES},
                    'median_solo_lockin_frac_(solo>=0.9*final)': float(np.median(lockin)),
                    'onset_(first nonzero heat token)_mean_frac_of_n': float(np.mean(onset_frac)),
                    'onset_frac_bullets_onset_after_25pct': float(np.mean(np.array(onset_frac) >= 0.25)),
                    'onset_frac_bullets_onset_after_50pct': float(np.mean(np.array(onset_frac) >= 0.5)),
                    'onset_mean_share_of_pos_heat_on_onset_token': float(np.mean(onset_share))}
    res['concentration'] = conc

    # first-token detail: which classes are first tokens and their share
    ft = collections.defaultdict(lambda: [0, 0.0])
    for x in recs:
        if x['dup'] or np.clip(x['heat'], 0, None).sum() <= EPS:
            continue
        p = np.clip(x['heat'], 0, None)
        ft[x['cls'][0]][0] += 1
        ft[x['cls'][0]][1] += p[0] / p.sum()
    res['first_token_by_class'] = {k: {'n': v[0], 'mean_share': round(v[1] / v[0], 4)} for k, v in ft.items()}

    # ------------------------------------------------------------------ clean-bullet position profiles
    prof = {}
    for st in SETTINGS + ('all',):
        acc = collections.defaultdict(lambda: [None, 0])
        for x in recs:
            if x['label'] != 'c' or x['dup'] or (st != 'all' and x['setting'] != st):
                continue
            p = np.clip(x['heat'], 0, None)
            if p.sum() <= EPS:
                continue
            a = acc[x['n']]
            a[0] = p / p.sum() if a[0] is None else a[0] + p / p.sum()
            a[1] += 1
        prof[st] = {n: (v[0] / v[1], v[1]) for n, v in acc.items()}

    def expected_share(st, n, mask):
        if n in prof[st] and prof[st][n][1] >= 50:
            return float(prof[st][n][0][mask].sum())
        if n in prof['all'] and prof['all'][n][1] >= 20:
            return float(prof['all'][n][0][mask].sum())
        return float(mask.mean())

    # ------------------------------------------------------------------ wrong bullets: is the wrong part cold?
    wres = {}
    examples = {}
    for st in SETTINGS + ('all',):
        W = [x for x in recs if x['label'] == 'w' and not x['dup'] and (st == 'all' or x['setting'] == st)]
        cats = collections.Counter()
        rows = []
        for x in W:
            m = int(x['wrong'].sum())
            n = x['n']
            p = np.clip(x['heat'], 0, None)
            P = p.sum()
            if m == 0:
                cats['span_only_unscored'] += 1
                continue
            if m == n:
                cats['span_covers_all_scored'] += 1
            if P <= EPS:
                cats['no_positive_heat'] += 1
                continue
            cats['used'] += 1
            sp = np.clip(np.diff(np.concatenate([[0.0], x['solo']])), 0, None)  # positive solo gains
            sgs = sp[x['wrong']].sum() / sp.sum() if sp.sum() > 0 else np.nan
            k0 = int(np.nonzero(np.abs(x['heat']) > EPS)[0][0])
            post = np.zeros(n, bool); post[k0 + 1:] = True
            pp = p[post].sum(); mw = int((x['wrong'] & post).sum()); npost = int(post.sum())
            rows.append({'x': x, 'm': m, 'n': n, 'tok_share': m / n, 'heat_share': p[x['wrong']].sum() / P,
                         'post_ok': pp > EPS and 0 < mw < npost,
                         'post_tok_share': mw / npost if npost else np.nan,
                         'post_heat_share': p[x['wrong'] & post].sum() / pp if pp > EPS else np.nan,
                         'span_before_onset': bool(np.nonzero(x['wrong'])[0].max() < k0),
                         'onset_in_span': bool(x['wrong'][k0]),
                         'net_in': float(x['heat'][x['wrong']].sum()), 'net_all': float(x['heat'].sum()),
                         'exp_share': expected_share(x['setting'] if st == 'all' else st, n, x['wrong']),
                         'P': P, 'Pw': p[x['wrong']].sum(), 'solo_gain_share': sgs,
                         'signed_in': x['heat'][x['wrong']].mean(),
                         'signed_out': x['heat'][~x['wrong']].mean() if m < n else np.nan,
                         'center': float(np.mean(np.nonzero(x['wrong'])[0] + 0.5) / n),
                         'informative': 0 < m < n})
        out = {'wrong_bullets_nondup': len(W), 'categories': dict(cats)}
        for subset in ('all_used', 'informative'):
            rr = [r for r in rows if subset == 'all_used' or r['informative']]
            if not rr:
                continue
            it = np.array([r['x']['item'] for r in rr])
            ts = np.array([r['tok_share'] for r in rr]); hs = np.array([r['heat_share'] for r in rr])
            es = np.array([r['exp_share'] for r in rr])
            Pw = np.array([r['Pw'] for r in rr]); P = np.array([r['P'] for r in rr])
            mm = np.array([r['m'] for r in rr], float); nn = np.array([r['n'] for r in rr], float)
            sg = np.array([r['solo_gain_share'] for r in rr]); okg = ~np.isnan(sg)
            blk = {'n_bullets': len(rr), 'n_items': int(len(set(it.tolist()))),
                   'mean_token_share': boot_mean(it, ts, NI, rng),
                   'mean_heat_share': boot_mean(it, hs, NI, rng),
                   'mean_heat_minus_token_share': boot_mean(it, hs - ts, NI, rng),
                   'mean_position_matched_expected_share': boot_mean(it, es, NI, rng),
                   'mean_heat_minus_expected_share': boot_mean(it, hs - es, NI, rng),
                   'pooled_heat_share_(sum Pw/sum P)': boot_ratio(it, Pw, P, NI, rng),
                   'pooled_token_share_(sum m/sum n)': boot_ratio(it, mm, nn, NI, rng),
                   'frac_bullets_heat_share_lt_token_share': boot_mean(it, (hs < ts).astype(float), NI, rng),
                   'mean_solo_gain_share_minus_token_share': boot_mean(it[okg], sg[okg] - ts[okg], NI, rng),
                   'mean_span_center_rel_pos': float(np.mean([r['center'] for r in rr]))}
            if subset == 'informative':
                si = np.array([r['signed_in'] for r in rr]); so = np.array([r['signed_out'] for r in rr])
                blk['mean_signed_heat_per_token_in_x1e3'] = tuple(v * 1e3 for v in boot_mean(it, si, NI, rng))
                blk['mean_signed_heat_per_token_out_x1e3'] = tuple(v * 1e3 for v in boot_mean(it, so, NI, rng))
                blk['pooled_net_heat_share_(sum net_in/sum net_all)'] = boot_ratio(
                    it, np.array([r['net_in'] for r in rr]), np.array([r['net_all'] for r in rr]), NI, rng)
                blk['frac_span_entirely_before_onset'] = float(np.mean([r['span_before_onset'] for r in rr]))
                blk['frac_onset_token_in_span'] = float(np.mean([r['onset_in_span'] for r in rr]))
                po = np.array([r['post_ok'] for r in rr])
                pts = np.array([r['post_tok_share'] for r in rr]); phs = np.array([r['post_heat_share'] for r in rr])
                blk['post_onset_excl_onset'] = {
                    'n': int(po.sum()),
                    'mean_token_share': boot_mean(it[po], pts[po], NI, rng),
                    'mean_heat_share': boot_mean(it[po], phs[po], NI, rng),
                    'mean_heat_minus_token_share': boot_mean(it[po], (phs - pts)[po], NI, rng)}
                blk['mean_signed_heat_per_token_in_minus_out_x1e3'] = tuple(
                    v * 1e3 for v in boot_mean(it, si - so, NI, rng))
                # by layer
                blk['by_layer_heat_minus_token_share'] = {
                    L: (lambda sel: boot_mean(it[sel], (hs - ts)[sel], NI, rng) if sel.sum() > 20 else None)(
                        np.array([r['x']['layer'] == L for r in rr])) for L in (20, 36, 44, 52, 60)}
                blk['by_layer_heat_minus_expected_share'] = {
                    L: (lambda sel: boot_mean(it[sel], (hs - es)[sel], NI, rng) if sel.sum() > 20 else None)(
                        np.array([r['x']['layer'] == L for r in rr])) for L in (20, 36, 44, 52, 60)}
                # only bullets where this bullet matters (loo_drop above median among informative wrong bullets)
                loo = np.array([r['x']['loo'] for r in rr])
                big = loo > np.median(loo)
                blk['loo_above_median'] = {'n': int(big.sum()), 'loo_median': float(np.median(loo)),
                                           'mean_heat_minus_token_share': boot_mean(it[big], (hs - ts)[big], NI, rng),
                                           'mean_heat_minus_expected_share': boot_mean(it[big], (hs - es)[big], NI, rng)}
            out[subset] = blk
        wres[st] = out
        if st != 'all':
            inf = [r for r in rows if r['informative'] and r['x']['loo'] > 0.005]
            inf.sort(key=lambda r: r['heat_share'] - r['tok_share'])
            pick = []
            if inf:
                pick = [('coldest (lowest heat share minus token share, loo>0.005)', inf[0]),
                        ('median', inf[len(inf) // 2]),
                        ('hottest (highest heat share minus token share, loo>0.005)', inf[-1])]
            examples[st] = [{'why': why, 'key': r['x']['key'], 'setting': st, 'bullet': r['x']['bullet'],
                             'n': r['n'], 'm_wrong_tokens': r['m'], 'token_share': round(r['tok_share'], 3),
                             'heat_share': round(r['heat_share'], 3), 'expected_share': round(r['exp_share'], 3),
                             'loo_drop': round(r['x']['loo'], 5), 'sum_heat': round(float(r['x']['heat'].sum()), 5),
                             'drift': r['x']['drift'],
                             'tokens': fmt_tokens(r['x']['pieces'], r['x']['heat'], r['x']['wrong'])} for why, r in pick]
    res['wrong_span'] = wres

    # ------------------------------------------------------------------ general examples (heat concentration)
    gen = []
    # largest single-token positive heat among non-dup bullets, one per setting, plus a first-token case
    for st in SETTINGS:
        R = [x for x in recs if x['setting'] == st and not x['dup'] and x['loo'] > 0.01]
        best = max(R, key=lambda x: x['heat'].max())
        gen.append({'why': 'largest single-token heat (loo>0.01)', 'key': best['key'], 'setting': st,
                    'bullet': best['bullet'], 'label': best['label'], 'loo_drop': round(best['loo'], 5),
                    'tokens': fmt_tokens(best['pieces'], best['heat'], best['wrong'])})
    R = [x for x in recs if not x['dup'] and x['loo'] > 0.01 and x['cls'][0] in ('emoji_symbol', 'partial_char')]
    R.sort(key=lambda x: -x['heat'][0] / max(np.clip(x['heat'], 0, None).sum(), 1e-12))
    if R:
        x = R[len(R) // 10]
        gen.append({'why': 'emoji/partial first token, 90th pct first-token share (loo>0.01)', 'key': x['key'],
                    'setting': x['setting'], 'bullet': x['bullet'], 'label': x['label'], 'loo_drop': round(x['loo'], 5),
                    'tokens': fmt_tokens(x['pieces'], x['heat'], x['wrong'])})
    # a typical clean bullet (median loo among loo>0.01, capped)
    R = sorted([x for x in recs if x['setting'] == 'capped_n1-n1' and x['label'] == 'c' and not x['dup']
                and x['loo'] > 0.01 and not x['truncated']], key=lambda x: x['loo'])
    x = R[len(R) // 2]
    gen.append({'why': 'median clean untruncated bullet among loo>0.01 (Original)', 'key': x['key'],
                'setting': x['setting'], 'bullet': x['bullet'], 'label': x['label'], 'loo_drop': round(x['loo'], 5),
                'tokens': fmt_tokens(x['pieces'], x['heat'])})
    res['examples_wrong'] = examples
    res['examples_general'] = gen
    (OUT / 'v4_heat_findings.json').write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float) + '\n')
    print(json.dumps(res, indent=1, ensure_ascii=False, default=float))


if __name__ == '__main__':
    main()
