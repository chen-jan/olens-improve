"""User modelling (um): judge picks (WSB um-v2, GPT-6 Luna, run nt-um-judge-v1) vs per-bullet string labels (lexicon v2).

DESIGN.md section 8, A5 ("do judge gold picks sit on gold-labelled bullets?"), plus judge misses and a small FVE link.
No API, no GPU. Run from newtasks/ with PYTHONPATH=code.

Subcommands
  prep        join three-settings atoms, bullet labels (+ per-hit values from um_text_labels), per-bullet metrics and
              judge rows -> analysis/um/cache/{bullets,readouts}.pkl
  run         agreement tables with bootstrap CIs (31 related-item groups attr_class:attr, and 100 items)
              -> analysis/um/a5_results.json
  sample      seeded reading samples -> analysis/um/a5_sample_<kind>.txt  (kinds: miss, judge_only, distractor)
  show CELL   print one readout (CELL = cell_id, optional setting label) with bullet labels, metrics and judge row

Readout classes (from the bullet labels of the selected readout; hierarchy top-down):
  gold        some bullet has a gold hit (gold_exact / gold_coarse / mixed), no wrong-value hit anywhere
  gold+wrong  gold hit and a wrong-value hit (in one bullet = mixed, or in different bullets)
  wrong_distr no gold hit; a wrong hit that is one of the judge's 4 distractor options
  wrong_other no gold hit; only wrong values outside the options (other_value)
  frame_only  frame words only;  none  nothing (ambiguous coarse hits count as none)
Judge picks: gold_inf (gold, basis inferred_characterization), gold_echo (gold, verbatim_echo), distractor, cannot_tell.
Evidence: the judge quote is located in the readout text (whole quote first; else each '; '-separated fragment),
then mapped to bullets with span_locate.bullet_index.
"""
from __future__ import annotations

import argparse
import collections
import json
import pickle
import random
import re
import sys
import time
from pathlib import Path

import numpy as np

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
sys.path.insert(0, str(NT / 'code'))
import ntcommon as C  # noqa: E402

C.setup_paths()
sys.path.append(str(NT.parent / 'code'))
from span_locate import bullet_index, bullets_with_offsets, locate  # noqa: E402

OUT = NT / 'analysis/um'
CACHE = OUT / 'cache'
SETTINGS = C.SETTINGS
SL = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
LS = {v: k for k, v in SL.items()}
SEED = 20261016
B_BOOT = 2000
GOLD_LABELS = ('gold_exact', 'gold_coarse', 'mixed')
KIND_ORDER = ('exact', 'coarse', 'cue', 'pronoun')  # strongest gold hit in a readout: a name form > region word > cue > pronoun


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ----------------------------------------------------------------------------------------------- prep
def locate_evidence(text, ev):
    """-> (found, sorted bullet indexes, n_fragments, n_fragments_found)."""
    bl = bullets_with_offsets(text)
    if not ev or not ev.strip():
        return False, [], 0, 0
    hits = locate(text, ev)
    if hits:
        return True, sorted({k for s, e, _ in hits for k in bullet_index(bl, s, e)}), 1, 1
    frags = [f.strip(' .;"\'…') for f in re.split(r';|\s\|\s|…|\.\.\.', ev)]
    frags = [f for f in frags if len(f) >= 3]
    idx, nf = set(), 0
    for f in frags:
        h = locate(text, f)
        if h:
            nf += 1
            idx |= {k for s, e, _ in h for k in bullet_index(bl, s, e)}
    return nf > 0, sorted(idx), len(frags), nf


def cmd_prep(_args):
    import pandas as pd
    bank = C.load_bank('user_modeling')
    group_of = {k: f"{it['attr_class']}:{it['attr']}" for k, it in bank.items()}
    log('three settings')
    meta, atoms = {}, {}
    for r in C.read_jsonl(C.DATA / 'select/um_three_settings.jsonl'):
        meta[r['cell_id']] = {'item_id': r['item_id'], 'layer': r['layer'], 'position': r['position'],
                              'rpk': r['read_position_kind'], 'subfamily': r['subfamily'], 'token': r.get('token')}
        for sid in SETTINGS:
            s = r['settings'][sid]
            atoms[(r['cell_id'], sid)] = {'text': s['text'], 'fve': s.get('fve'),
                                          'atoms': [(a['source_phrase_id'], a['text'], a['sample_index'],
                                                     a.get('scored_token_count')) for a in s['atoms']]}
    log('bullet labels')
    labs = collections.defaultdict(list)
    with open(C.DATA / 'labels/um_bullet_labels.jsonl') as f:
        for ln in f:
            if '"source": "pool"' in ln:
                continue
            o = json.loads(ln)
            labs[(o['cell_id'], o['source'])].append(o)
    need = {o['key'] for v in labs.values() for o in v}
    log('text labels', len(need))
    tl = {}
    with open(C.DATA / 'labels/um_text_labels.jsonl') as f:
        for ln in f:
            k = ln[9:29]
            if k in need:
                o = json.loads(ln)
                tl[o['key']] = o
    log('metrics')
    met = {}
    for L in C.LAYERS:
        for r in C.read_jsonl(C.DATA / f'metrics/um_bullet_metrics.L{L}.jsonl'):
            for sid, s in r['settings'].items():
                met[(r['cell_id'], sid)] = s
    log('judge rows')
    judge = {}
    for sid in SETTINGS:
        res = {(v['id'], v['layer'], v['pos']): v for v in
               json.loads((C.DATA / f'judge/um/{sid}/results.json').read_text())['rows']}
        for v in C.read_jsonl(C.DATA / f'judge/um/{sid}/um_cell_rows.jsonl'):
            rr = res[(v['item_id'], v['layer'], v['pos'])]
            judge[(v['cell_id'], sid)] = v | {'rationale': rr.get('rationale'), 'options': rr['options'],
                                              'gold_position': rr['gold_position']}
    brows, rrows = [], []
    bad_order = 0
    for (cid, sid), a in atoms.items():
        m = meta[cid]
        lab = labs[(cid, sid)]
        if [o['phrase_id'] for o in lab] != [x[0] for x in a['atoms']]:
            bad_order += 1
            continue
        mt = met.get((cid, sid))
        mb = {b['phrase_id']: b for b in mt['bullets']} if mt and mt.get('bullets') else {}
        j = judge[(cid, sid)]
        opts = j['options']
        gold_opt = opts[j['gold_position'] - 1]
        distr = [o for i, o in enumerate(opts) if i + 1 != j['gold_position']]
        found, evb, nfr, nff = locate_evidence(a['text'], j['evidence'])
        nb = len(a['atoms'])
        per = []
        for k, ((pid, txt, si, ntok), o) in enumerate(zip(a['atoms'], lab)):
            t = tl[o['key']]
            gh = t['gold_hits']
            wh = t['wrong_hits']
            b = mb.get(pid, {})
            row = {'cell_id': cid, 'setting': sid, 'item_id': m['item_id'], 'group': group_of[m['item_id']],
                   'subfamily': m['subfamily'], 'layer': m['layer'], 'position': m['position'], 'rpk': m['rpk'],
                   'bidx': k, 'nb': nb, 'text': txt, 'sample_index': si, 'phrase_id': pid, 'ntok': ntok,
                   'label': o['label'], 'subtype': o['subtype'],
                   'n_gold_hits': len(gh), 'gold_surfaces': [h['surface'] for h in gh],
                   'gold_kinds': sorted({h['match'] for h in gh}),
                   'gold_any_noprompt': any(not h['in_prompt'] for h in gh),
                   'wrong_values': sorted({h.get('value') or '/'.join(h.get('cover', [])) for h in wh}),
                   'wrong_surfaces': [h['surface'] for h in wh],
                   'n_wrong_distr': sum(h['subtype'] == 'distractor' for h in wh),
                   'n_wrong_other': sum(h['subtype'] == 'other_value' for h in wh),
                   'frames': [h['surface'] for h in t['frames']],
                   'shapley_share': b.get('shapley_share'), 'shapley': b.get('shapley'),
                   'solo_fve': b.get('solo_fve'), 'loo_drop': b.get('loo_drop'),
                   'ev': k in evb}
            per.append(row)
        brows += per
        gold_b = [r for r in per if r['n_gold_hits']]
        any_wrong = any(r['wrong_surfaces'] for r in per)
        if gold_b and any_wrong:
            cls = 'gold+wrong'
        elif gold_b:
            cls = 'gold'
        elif any(r['n_wrong_distr'] for r in per):
            cls = 'wrong_distr'
        elif any(r['n_wrong_other'] for r in per):
            cls = 'wrong_other'
        elif any(r['label'] == 'frame_only' for r in per):
            cls = 'frame_only'
        else:
            cls = 'none'
        pick = j['pick']
        pk = ('gold_inf' if j['basis'] == 'inferred_characterization' else 'gold_echo') if pick == 'gold' else pick
        named_distr = sorted({v for r in per for v in r['wrong_values']})
        rrows.append({'cell_id': cid, 'setting': sid, 'item_id': m['item_id'], 'group': group_of[m['item_id']],
                      'subfamily': m['subfamily'], 'layer': m['layer'], 'position': m['position'], 'rpk': m['rpk'],
                      'attr_class': bank[m['item_id']]['attr_class'], 'gold_value': gold_opt, 'distractors': distr,
                      'nb': nb, 'text': a['text'], 'joint_fve': mt.get('joint_fve_saved') if mt else None,
                      'cls': cls, 'n_gold_b': len(gold_b),
                      'n_gold_exact_b': sum(r['label'] == 'gold_exact' for r in per),
                      'n_gold_coarse_b': sum(r['label'] == 'gold_coarse' for r in per),
                      'n_mixed_b': sum(r['label'] == 'mixed' for r in per),
                      'gold_noprompt': any(r['gold_any_noprompt'] for r in per),
                      'gold_kind': next((k for k in KIND_ORDER if any(k in r['gold_kinds'] for r in per)), None),
                      'labels': [r['label'] for r in per], 'named_wrong_values': named_distr,
                      'pick': pick, 'pk': pk, 'basis': j['basis'], 'pick_value': j['pick_value'],
                      'evidence': j['evidence'], 'ev_found': found, 'ev_bullets': evb, 'ev_frags': nfr,
                      'ev_frags_found': nff, 'ev_found_orig': j['evidence_found'], 'rationale': j['rationale']})
    log('bad order', bad_order)
    CACHE.mkdir(parents=True, exist_ok=True)
    B = pd.DataFrame(brows)
    R = pd.DataFrame(rrows)
    B.to_pickle(CACHE / 'bullets.pkl')
    R.to_pickle(CACHE / 'readouts.pkl')
    log('bullets', len(B), 'readouts', len(R))


def load():
    import pandas as pd
    return pd.read_pickle(CACHE / 'bullets.pkl'), pd.read_pickle(CACHE / 'readouts.pkl')


# ----------------------------------------------------------------------------------------------- bootstrap
class Boot:
    """Ratio-of-sums bootstrap over items (100) and related-item groups (31, attr_class:attr); same weights for all
    statistics, so differences are paired."""

    def __init__(self, item_group, B=B_BOOT, seed=SEED):
        self.items = sorted(item_group)
        self.ii = {it: k for k, it in enumerate(self.items)}
        self.cl = sorted(set(item_group.values()))
        self.icl = np.array([self.cl.index(item_group[it]) for it in self.items])
        rng = np.random.default_rng(seed)
        n, m = len(self.items), len(self.cl)
        self.Wi = rng.multinomial(n, np.full(n, 1 / n), size=B).astype(float)
        self.Wc = rng.multinomial(m, np.full(m, 1 / m), size=B).astype(float)

    def agg(self, items, num, den=None):
        idx = np.array([self.ii[i] for i in items], dtype=int)
        num = np.asarray(num, float)
        den = np.ones_like(num) if den is None else np.asarray(den, float)
        n = len(self.items)
        return np.bincount(idx, num, n), np.bincount(idx, den, n)

    def _reps(self, N, D):
        m = len(self.cl)
        Nc, Dc = np.bincount(self.icl, N, m), np.bincount(self.icl, D, m)
        with np.errstate(invalid='ignore', divide='ignore'):
            return (self.Wi @ N) / (self.Wi @ D), (self.Wc @ Nc) / (self.Wc @ Dc)

    def ratio(self, items, num, den=None, nd=3):
        N, D = self.agg(items, num, den)
        if D.sum() <= 0:
            return {'est': None, 'n': 0}
        ri, rc = self._reps(N, D)
        return {'est': round(float(N.sum() / D.sum()), nd), 'ci_groups': _ci(rc, nd), 'ci_items': _ci(ri, nd),
                'n': int(round(D.sum())), 'items': int((D > 0).sum())}


def _ci(x, nd):
    x = x[np.isfinite(x)]
    if not len(x):
        return None
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [round(float(lo), nd), round(float(hi), nd)]


def kappa(a, b):
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    po = np.mean(a == b)
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return round(float((po - pe) / (1 - pe)), 3) if pe < 1 else None


# ----------------------------------------------------------------------------------------------- run
def cmd_run(_args):
    import pandas as pd
    B, R = load()
    bank = C.load_bank('user_modeling')
    bt = Boot({k: f"{it['attr_class']}:{it['attr']}" for k, it in bank.items()})
    out = {'note': ('UM judge (um-v2, GPT-6 Luna, reasoning none; NOT WSB numbers of record) vs lexicon v2 bullet labels '
                    'on the selected readouts (3,000 cells x 3 settings). CIs: 2,000 bootstrap reps over 31 related-item '
                    'groups (attr_class:attr), item-level CIs alongside.'),
           'n_readouts': int(len(R)), 'n_bullets': int(len(B))}
    PK = ['gold_inf', 'gold_echo', 'distractor', 'cannot_tell']
    CL = ['gold', 'gold+wrong', 'wrong_distr', 'wrong_other', 'frame_only', 'none']

    def xtab(d):
        t = pd.crosstab(d.cls, d.pk).reindex(index=CL, columns=PK, fill_value=0)
        return {c: {p: int(t.loc[c, p]) for p in PK} for c in CL}
    out['crosstab_class_x_pick'] = {'all': xtab(R), **{SL[s]: xtab(R[R.setting == s]) for s in SETTINGS},
                                    **{f'all|{sf}': xtab(R[R.subfamily == sf]) for sf in ('selfdescribe', 'synthsys')}}
    jg = (R.pick == 'gold').to_numpy()
    lg = R.cls.isin(['gold', 'gold+wrong']).to_numpy()

    def agree(d):
        a, b = (d.pick == 'gold').to_numpy(), d.cls.isin(['gold', 'gold+wrong']).to_numpy()
        return {'kappa': kappa(a, b), 'both': int((a & b).sum()), 'judge_only': int((a & ~b).sum()),
                'labels_only': int((~a & b).sum()), 'neither': int((~a & ~b).sum()),
                'P(judge gold | readout has gold bullet)': bt.ratio(d.item_id, a & b, b),
                'P(readout has gold bullet | judge gold)': bt.ratio(d.item_id, a & b, a)}
    out['agreement_judge_gold_vs_gold_bullet'] = {'all': agree(R), **{SL[s]: agree(R[R.setting == s]) for s in SETTINGS},
                                                  **{sf: agree(R[R.subfamily == sf]) for sf in ('selfdescribe', 'synthsys')}}
    # stricter: readouts whose gold bullets come with no wrong value at all
    d = R[R.cls == 'gold']
    out['P(judge gold | class gold, by number of gold bullets)'] = {
        str(k): bt.ratio(g.item_id, g.pick == 'gold') for k, g in d.groupby(d.n_gold_b.clip(upper=4))}
    out['P(judge gold | class gold, by subfamily x echo)'] = {
        f'{sf}|{"label_noprompt" if npr else "label_in_prompt_only"}': bt.ratio(g.item_id, g.pick == 'gold')
        for (sf, npr), g in d.groupby(['subfamily', 'gold_noprompt'])}
    out['P(judge gold | class gold, by read site)'] = {k: bt.ratio(g.item_id, g.pick == 'gold')
                                                       for k, g in d.groupby('rpk')}
    out['P(judge gold | class gold, by layer)'] = {str(k): bt.ratio(g.item_id, g.pick == 'gold')
                                                   for k, g in d.groupby('layer')}
    out['P(judge gold | class gold, by attr_class)'] = {k: bt.ratio(g.item_id, g.pick == 'gold')
                                                        for k, g in d.groupby('attr_class')}
    out['P(judge gold | class gold, by strongest gold hit kind)'] = {
        k: bt.ratio(g.item_id, g.pick == 'gold') for k, g in d.groupby('gold_kind')}
    out['P(judge gold | class gold, by strongest gold hit kind x subfamily)'] = {
        f'{k}|{sf}': bt.ratio(g.item_id, g.pick == 'gold') for (k, sf), g in d.groupby(['gold_kind', 'subfamily'])}
    exact_only = d[(d.n_gold_exact_b > 0)]
    out['P(judge gold | >=1 gold_exact bullet, no wrong value)'] = bt.ratio(exact_only.item_id, exact_only.pick == 'gold')
    coarse_only = d[(d.n_gold_exact_b == 0) & (d.n_gold_coarse_b > 0)]
    out['P(judge gold | gold_coarse bullets only, no wrong value)'] = bt.ratio(coarse_only.item_id, coarse_only.pick == 'gold')
    # Maori-type misses: >= 3 gold bullets, no wrong value, judge cannot_tell
    mt = d[(d.n_gold_b >= 3) & (d.pick == 'cannot_tell')]
    out['maori_type_misses'] = {'n': int(len(mt)), 'of_readouts_with_>=3_gold_bullets': int((d.n_gold_b >= 3).sum()),
                                'by_setting': {SL[s]: int((mt.setting == s).sum()) for s in SETTINGS},
                                'by_subfamily': mt.subfamily.value_counts().to_dict(),
                                'by_attr_class': mt.attr_class.value_counts().to_dict(),
                                'by_gold_kind': mt.gold_kind.value_counts().to_dict(),
                                'cells': [f"{r.cell_id} [{SL[r.setting]}]" for r in mt.itertuples()][:200]}
    # basis vs in_prompt
    gg = R[(R.pick == 'gold') & lg]
    out['basis_vs_label_in_prompt'] = {
        'judge_inferred & label_noprompt': int(((gg.basis == 'inferred_characterization') & gg.gold_noprompt).sum()),
        'judge_inferred & label_in_prompt_only': int(((gg.basis == 'inferred_characterization') & ~gg.gold_noprompt).sum()),
        'judge_echo & label_noprompt': int(((gg.basis == 'verbatim_echo') & gg.gold_noprompt).sum()),
        'judge_echo & label_in_prompt_only': int(((gg.basis == 'verbatim_echo') & ~gg.gold_noprompt).sum()),
        'kappa(inferred vs noprompt)': kappa(gg.basis == 'inferred_characterization', gg.gold_noprompt),
        'by_subfamily': {sf: {'inf&noprompt': int(((g.basis == 'inferred_characterization') & g.gold_noprompt).sum()),
                              'inf&inprompt': int(((g.basis == 'inferred_characterization') & ~g.gold_noprompt).sum()),
                              'echo&noprompt': int(((g.basis == 'verbatim_echo') & g.gold_noprompt).sum()),
                              'echo&inprompt': int(((g.basis == 'verbatim_echo') & ~g.gold_noprompt).sum())}
                         for sf, g in gg.groupby('subfamily')}}
    # distractor picks
    dp = R[R.pick == 'distractor'].copy()
    dp['pv_named'] = [pv.replace(' ', '_') in nv or pv in nv for pv, nv in zip(dp.pick_value, dp.named_wrong_values)]
    out['distractor_picks'] = {'n': int(len(dp)), 'class': dp.cls.value_counts().to_dict(),
                               'picked_value_named_by_lexicon': int(dp.pv_named.sum()),
                               'by_subfamily': dp.subfamily.value_counts().to_dict(),
                               'by_rpk': dp.rpk.value_counts().to_dict()}
    # readouts that name a distractor option (no gold): what the judge does
    wd = R[R.cls == 'wrong_distr']
    out['P(judge distractor | class wrong_distr)'] = bt.ratio(wd.item_id, wd.pick == 'distractor')
    out['P(judge gold | class wrong_distr)'] = bt.ratio(wd.item_id, wd.pick == 'gold')
    wo = R[R.cls == 'wrong_other']
    out['P(judge gold | class wrong_other)'] = bt.ratio(wo.item_id, wo.pick == 'gold')
    nn = R[R.cls.isin(['frame_only', 'none'])]
    out['P(judge gold | class frame_only/none)'] = bt.ratio(nn.item_id, nn.pick == 'gold')
    # evidence mapping
    ev = {}
    Bi = B.set_index(['cell_id', 'setting', 'bidx'])
    for pk_, g in R[R.pick.isin(['gold', 'distractor'])].groupby('pick'):
        labs = collections.Counter()
        on_gold = 0
        for r in g.itertuples():
            if not r.ev_found:
                labs['(quote not located)'] += 1
                continue
            ls = [r.labels[k] for k in r.ev_bullets]
            if any(x in GOLD_LABELS for x in ls):
                on_gold += 1
            labs[','.join(sorted(set(ls)))] += 1
        ev[pk_] = {'readouts': int(len(g)), 'quote_located': int(g.ev_found.sum()),
                   'quote_located_by_orig_whole_quote_rule': int(g.ev_found_orig.sum()),
                   'quote_on_gold_labelled_bullet': on_gold, 'evidence_bullet_labels': dict(labs.most_common())}
    out['evidence_mapping'] = ev
    jo = R[(R.pick == 'gold') & ~lg]
    lm = d[d.pick == 'cannot_tell']
    out['label_gold_judge_cannot_tell'] = {'n': int(len(lm)), 'by_gold_kind': lm.gold_kind.value_counts().to_dict(),
                                           'by_attr_class': lm.attr_class.value_counts().to_dict(),
                                           'by_subfamily': lm.subfamily.value_counts().to_dict()}
    out['judge_gold_without_gold_bullet'] = {'n': int(len(jo)), 'class': jo.cls.value_counts().to_dict(),
                                             'basis': jo.basis.value_counts().to_dict(),
                                             'by_attr_class': jo.attr_class.value_counts().to_dict()}
    # value-surface consistency (Maori analogue): per item x gold surface (lowercased), judge gold rate over readouts
    # (class gold) holding a bullet with that surface
    surf = collections.defaultdict(lambda: [0, 0, set()])
    gcells = set(zip(d.cell_id, d.setting))
    pick_of = dict(zip(zip(R.cell_id, R.setting), R.pick))
    for r in B[B.n_gold_hits > 0].itertuples():
        if (r.cell_id, r.setting) not in gcells:
            continue
        for s_ in {x.lower() for x in r.gold_surfaces}:
            k = (r.item_id, s_)
            if (r.cell_id, r.setting) in surf[k][2]:
                continue
            surf[k][2].add((r.cell_id, r.setting))
            surf[k][0] += 1
            surf[k][1] += pick_of[(r.cell_id, r.setting)] == 'gold'
    rows = [{'item_id': k[0], 'surface': k[1], 'readouts': v[0], 'judge_gold': v[1], 'rate': round(v[1] / v[0], 3)}
            for k, v in surf.items() if v[0] >= 10]
    rows.sort(key=lambda x: (x['rate'], -x['readouts']))
    out['surface_consistency_low'] = rows[:40]
    out['surface_consistency_high'] = sorted(rows, key=lambda x: (-x['rate'], -x['readouts']))[:20]
    out['surface_consistency_n_surfaces_ge10'] = len(rows)
    # FVE link: Shapley share of the judge-evidence bullet vs the other bullets (judge gold, exactly one evidence bullet)
    out['fve_evidence_bullet'] = fve_link(B, R, bt)
    # judge quote position (readouts of 4 bullets, judge gold, quote on exactly one bullet)
    q = R[(R.pick == 'gold') & R.ev_found & (R.nb == 4) & (R.ev_bullets.map(len) == 1)]
    out['judge_quote_position'] = {SL[s_]: {str(k): round(float(v), 3) for k, v in
                                            g.ev_bullets.map(lambda x: x[0]).value_counts(normalize=True).sort_index().items()}
                                   for s_, g in q.groupby('setting')}
    # basis vs in-prompt, 3-way (gold hits all in prompt / none in prompt / both) is in the docstring of the report;
    # manual reading verdicts (analysis/um/a5_<kind>_reading.tsv, written by hand from a5_sample_<kind>.txt)
    rd = {}
    for kind in ('miss', 'miss3', 'judge_only', 'distractor'):
        rp = OUT / f'a5_{kind}_reading.tsv'
        if rp.exists():
            rows = [ln.split('\t') for ln in rp.read_text().splitlines()[1:] if ln.strip()]
            rd[kind] = {'n_read': len(rows), 'verdicts': dict(collections.Counter(r[2] for r in rows)), 'file': str(rp)}
    rd['legend'] = {'miss/miss3': {'A': 'judge miss: readout names gold for the user, or echoes a culture cue the judge accepts elsewhere',
                                   'B': 'persona pronoun/name/noun for the requested biography subject (rubric lists he/him for male)',
                                   'C': 'judge right: value word not about the user (destination, list, word sense, activity cue)',
                                   'D': 'borderline: closely related cue (maritime, aviation snack expert, older adults)'},
                    'judge_only': {'LEX_MISS': 'lexicon should have caught it', 'INFER': 'rubric-sanctioned close characterization',
                                   'PERSONA_NAME': 'male-coded names for the persona', 'WEAK': 'weak or non-specific link',
                                   'UNSUPPORTED': 'quote not in the readout', 'ERROR': 'pick contradicts readout/rationale'},
                    'distractor': {'OK': 'readout states the distractor for the user/context', 'WEAK': 'weak link',
                                   'ERROR': 'pick contradicts rationale or gold also named'}}
    out['reading'] = rd
    (OUT / 'a5_results.json').write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    log('wrote', OUT / 'a5_results.json')


def fve_link(B, R, bt):
    """Paired within-readout difference: (share of target bullet) - (mean share of the other bullets).
    Original / Best of 32: shares are first residualised on setting x layer x nb x bullet position (position confound).
    Combine 32: raw (its order is the greedy FVE order, so a position adjustment would remove the signal)."""
    B = B[B.shapley_share.notna()].copy()
    key = ['setting', 'layer', 'nb', 'bidx']
    B['adj'] = B.shapley_share - B.groupby(key).shapley_share.transform('mean')
    B['use'] = np.where(B.setting == 'pooled_greedy_swap-n32', B.shapley_share, B.adj)
    # length-adjusted variant: additionally remove a per-setting linear fit on scored token count
    B['use_len'] = B.use
    for sid in SETTINGS:
        m = (B.setting == sid) & B.ntok.notna()
        x, y = B.loc[m, 'ntok'].astype(float).to_numpy(), B.loc[m, 'use'].to_numpy()
        beta = np.polyfit(x, y, 1)
        B.loc[m, 'use_len'] = y - np.polyval(beta, x)
    R1 = R.set_index(['cell_id', 'setting'])
    out = {}
    for name, sel, col in (('judge_gold_evidence_bullet', 'ev', 'use'), ('gold_labelled_bullet', 'gold', 'use'),
                           ('judge_gold_evidence_on_gold_bullet', 'evgold', 'use'),
                           ('judge_gold_evidence_bullet|len_adj', 'ev', 'use_len'),
                           ('gold_labelled_bullet|len_adj', 'gold', 'use_len'),
                           ('judge_gold_evidence_bullet|ntok_diff', 'ev', 'ntok'),
                           ('gold_labelled_bullet|ntok_diff', 'gold', 'ntok')):
        res = {}
        for sid in SETTINGS:
            items, diffs = [], []
            for (cid, s), g in B[B.setting == sid].groupby(['cell_id', 'setting'], sort=False):
                if len(g) < 2:
                    continue
                r = R1.loc[(cid, s)]
                if sel == 'ev':
                    if r.pick != 'gold' or not r.ev_found:
                        continue
                    tgt = g.ev.to_numpy()
                elif sel == 'evgold':
                    if r.pick != 'gold' or not r.ev_found:
                        continue
                    tgt = (g.ev & (g.n_gold_hits > 0)).to_numpy()
                else:
                    if r.cls != 'gold':
                        continue
                    tgt = (g.n_gold_hits > 0).to_numpy()
                if tgt.sum() == 0 or tgt.sum() == len(g):
                    continue
                u = g[col].astype(float).to_numpy()
                items.append(r.item_id)
                diffs.append(u[tgt].mean() - u[~tgt].mean())
            res[SL[sid]] = bt.ratio(items, diffs, nd=4) if items else {'est': None}
        out[name] = res
    out['note'] = fve_link.__doc__
    return out


# ----------------------------------------------------------------------------------------------- sample / show
def fmt_readout(r, Bsub):
    lines = [f"== {r.cell_id} [{SL[r.setting]}]  site={r.rpk}  subfamily={r.subfamily}  class={r.cls}",
             f"   gold={r.gold_value}  distractors={r.distractors}  joint_fve={r.joint_fve if r.joint_fve is None else round(r.joint_fve, 3)}",
             f"   JUDGE pick={r.pick} ({r.pick_value}) basis={r.basis}  evidence={r.evidence!r}  ev_bullets={list(r.ev_bullets)}",
             f"   rationale: {r.rationale}"]
    for b in Bsub.itertuples():
        hits = (f" gold_hits={b.gold_surfaces}{b.gold_kinds}" if b.gold_surfaces else '') + \
               (f" wrong={b.wrong_surfaces}->{b.wrong_values}" if b.wrong_surfaces else '')
        sh = '-' if b.shapley_share is None or not np.isfinite(b.shapley_share) else f'{b.shapley_share:.3f}'
        lines.append(f"   [{b.bidx}]{'*' if b.ev else ' '} {b.label:<11} share={sh} ntok={b.ntok}{hits}")
        lines.append('        ' + b.text.strip().replace('\n', ' / ')[:400])
    return '\n'.join(lines)


def cmd_sample(args):
    B, R = load()
    rng = random.Random(SEED)
    Bg = B.groupby(['cell_id', 'setting'])
    lg = R.cls.isin(['gold', 'gold+wrong'])
    kinds = {
        'miss': R[(R.cls == 'gold') & (R.pick == 'cannot_tell')],
        'miss3': R[(R.cls == 'gold') & (R.pick == 'cannot_tell') & (R.n_gold_b >= 3)],
        'judge_only': R[(R.pick == 'gold') & ~lg],
        'distractor': R[R.pick == 'distractor'],
    }
    for kind, d in kinds.items():
        if args.kind and kind not in args.kind:
            continue
        rows = list(d.itertuples())
        # dedupe identical texts (shared across settings), max 2 per item
        seen, per_item, pick = set(), collections.Counter(), []
        rng.shuffle(rows)
        for r in rows:
            if (r.item_id, r.text) in seen or per_item[r.item_id] >= 2:
                continue
            seen.add((r.item_id, r.text))
            per_item[r.item_id] += 1
            pick.append(r)
            if len(pick) >= args.n:
                break
        txt = [f'# {kind}: {len(pick)} of {len(d)} readouts (seed {SEED}, max 2 per item, distinct texts)\n']
        for r in pick:
            txt.append(fmt_readout(r, Bg.get_group((r.cell_id, r.setting)).sort_values('bidx')))
        (OUT / f'a5_sample_{kind}.txt').write_text('\n\n'.join(txt) + '\n')
        log('wrote', kind, len(pick))


def cmd_show(args):
    B, R = load()
    d = R[R.cell_id == args.cell]
    if args.setting:
        d = d[d.setting == LS.get(args.setting, args.setting)]
    for r in d.itertuples():
        print(fmt_readout(r, B[(B.cell_id == r.cell_id) & (B.setting == r.setting)].sort_values('bidx')))
        print()


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('prep')
    sp.add_parser('run')
    s = sp.add_parser('sample')
    s.add_argument('--n', type=int, default=40)
    s.add_argument('--kind', nargs='*')
    s = sp.add_parser('show')
    s.add_argument('cell')
    s.add_argument('setting', nargs='?')
    a = ap.parse_args()
    {'prep': cmd_prep, 'run': cmd_run, 'sample': cmd_sample, 'show': cmd_show}[a.cmd](a)


if __name__ == '__main__':
    main()
