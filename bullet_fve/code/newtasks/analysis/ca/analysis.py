"""Conjunctive association (ca): analyses A1-A5 of DESIGN.md section 8, plus the 36-case reading sample.

Question: do bullets that state the RIGHT filler (gold's value on the axis where gold and contrast differ)
get more per-bullet FVE than bullets that state a WRONG value on that same axis, or only the frame?

Subcommands (run from newtasks/, PYTHONPATH=code; every step is a short CPU job, no GPU, no API):
  prep      label every selected and pool bullet with the refined lexicon (lex2), join LLM labels,
            per-bullet metrics, scored-token counts and judge rows -> analysis/ca/cache/*.pkl
  run       A1-A5 -> analysis/ca/results.json
  sample    36 reading cases -> analysis/ca/read_sample.json
  show KEY  print one case (KEY = item.L<layer>.p<pos>, optional setting) with every bullet's labels and scores
  disagree  print a seeded sample of LLM-vs-lex2 disagreements (for reading the labels)

Bullet labels (task definitions; X = the item's contrast_axis, Y = the other varied axis):
  gold        states gold's value on X (the key component of the gold compound), e.g. "grief" in a grief-vs-guilt item
  contrast    states the contrast option's value on X ("guilt")
  other_value states another value on X that is neither gold's nor the contrast's (only lexicon-detectable for the
              5-valued relation axis of q01_e..j; the LLM finds other values as "conflicts")
  frame_only  states content that gold and contrast share (event, relation, object, kind of state) and no X value
  none        none of these
  bookkeeping: mixed (gold and a wrong X value), other_axis (a wrong value only on another axis or a different event)
Analysis groups: right = gold; wrongX = contrast | other_value ("same frame, different value"); frame = frame_only.

Label sources:
  llm   : nt-ca-bullet-v1 (GPT-6 Luna) on the selected bullets (3 settings). other_wrong is split with the lexicon:
          other_value if the bullet holds an X-axis competitor word, else other_axis.
  lex2  : the bank's regex lexicons, refined so that "contrast" = the contrast option's own credit words (taken from the
          partner item whose gold is this item's contrast) and other X values are other_value; a negation within three
          words before a contrast-axis word cancels it ("not accidental"). Free, so it also labels
          every pool bullet (A3, A4 random baseline). lex2w = lex2 on the scored window (first 32 AR tokens).
  agreed: llm and lex2 agree on the group (gold: llm gold & lex2 gold; wrongX: llm contrast|other_value & lex2
          contrast|other_value). High precision, fewer bullets.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
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

OUT = NT / 'analysis/ca'
CACHE = OUT / 'cache'
FAM = 'conjunctive_association'
SETTINGS = C.SETTINGS
SL = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
LAYERS = C.LAYERS
WRONGX = ('contrast', 'other_value')
SEED = 20261016
B_BOOT = 2000


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ----------------------------------------------------------------------------------------------- lexicon (lex2)
def _rx(words):
    words = sorted({w.lower() for w in words}, key=len, reverse=True)
    if not words:
        return None
    alts = (r'[\s\-]+'.join(re.escape(p) for p in re.split(r'[\s\-]+', w.strip())) for w in words)
    return re.compile(r'(?<![\w])(?:' + '|'.join(alts) + r')(?![\w])', re.I)


# a negation within three words before a contrast-axis word cancels that match (gold and wrong values alike)
_NEG = re.compile(r"(?:\bnot|n['’]t|\bnever|\bno|\brather than|\binstead of|\bwithout)\W+(?:[\w'’]+\W+){0,2}(?:an?\W+)?$", re.I)


class Lex2:
    """Refined lexicon labeller for one item (see module docstring)."""

    def __init__(self, item, partner, cluster_items):
        self.id = item['id']
        X = self.X = item['contrast_axis']
        self.Y = [a for a in item['varied_axes'] if a != X]
        self.gold_rx = [_rx(g) for g in item['credit'][X]]
        self.con_rx = [_rx(g) for g in partner['credit'][X]]
        self.con_words = {w.lower() for g in partner['credit'][X] for w in g}
        self.compX = _rx(item['competitors'].get(X, []))
        self.compY = {ax: _rx(ws) for ax, ws in item['competitors'].items() if ax != X}
        self.frame = {ax: [_rx(g) for g in gs] for ax, gs in item['credit'].items() if ax != X}
        self.goldY = {ax: [_rx(g) for g in item['credit'].get(ax, [])] for ax in self.Y}
        self.nvalsX = len({json.dumps(c['cell'].get(X), sort_keys=True) for c in cluster_items})

    @staticmethod
    def _pos(r, t):
        """Non-negated matches of r in t ("not accidental", "sabotage, not accident", "rather than blame" do not count)."""
        return [m for m in r.finditer(t) if not _NEG.search(t[max(0, m.start() - 40):m.start()])]

    @classmethod
    def _all(cls, rxs, t):
        return bool(rxs) and all(r is not None and cls._pos(r, t) for r in rxs)

    def label(self, text):
        t = text
        g = self._all(self.gold_rx, t)
        c = self._all(self.con_rx, t)
        cx = sorted({m.group(0).lower() for m in self._pos(self.compX, t)}) if self.compX else []
        if self.nvalsX == 2:
            c = c or bool(cx)
            o = False
        else:
            o = any(w not in self.con_words for w in cx)
        oy = [ax for ax, r in self.compY.items() if r is not None and self._pos(r, t)]
        fr = [ax for ax, rs in self.frame.items() if any(r is not None and r.search(t) for r in rs)]
        gy = all(self._all(rs, t) for rs in self.goldY.values()) if self.goldY else False
        # every non-X credit axis credited (gold Y value AND the shared content, e.g. the event and the object)
        allax = all(self._all(rs, t) for rs in self.frame.values()) if self.frame else False
        if g and (c or o):
            lab = 'mixed'
        elif g:
            lab = 'gold'
        elif c:
            lab = 'contrast'
        elif o:
            lab = 'other_value'
        elif oy:
            lab = 'other_axis'
        elif fr:
            lab = 'frame_only'
        else:
            lab = 'none'
        return lab, {'g': g, 'c': c, 'o': o, 'oy': oy, 'fr': fr, 'gy': gy, 'allax': allax, 'cx': cx}

    def words(self, text):
        """Matched words for reading (gold X / contrast X / X competitors / Y competitors / frame)."""
        out = {}
        for name, rxs in (('goldX', self.gold_rx), ('contrastX', self.con_rx)):
            hits = sorted({m.group(0) for r in rxs if r is not None for m in r.finditer(text)})
            if hits:
                out[name] = hits
        if self.compX:
            hits = sorted({m.group(0) for m in self.compX.finditer(text)})
            if hits:
                out['competitorX'] = hits
        for ax, r in self.compY.items():
            hits = sorted({m.group(0) for m in r.finditer(text)}) if r is not None else []
            if hits:
                out[f'competitor:{ax}'] = hits
        for ax, rs in self.frame.items():
            hits = sorted({m.group(0) for r in rs if r is not None for m in r.finditer(text)})
            if hits:
                out[f'frame:{ax}'] = hits
        return out


def build_lexicons(bank):
    by_gold = {(it['cluster'], it['gold_label']): it for it in bank.values()}
    clusters = collections.defaultdict(list)
    for it in bank.values():
        clusters[it['cluster']].append(it)
    return {k: Lex2(it, by_gold[(it['cluster'], it['contrast_label'])], clusters[it['cluster']])
            for k, it in bank.items()}


def llm5(llm_label, lex_label):
    if llm_label == 'other_wrong':
        return 'other_value' if lex_label in ('contrast', 'other_value', 'mixed') else 'other_axis'
    return llm_label


def agreed(llm5_label, lex_label):
    if llm5_label == 'gold' and lex_label == 'gold':
        return 'gold'
    if llm5_label in WRONGX and lex_label in WRONGX:
        return 'wrongX'
    if llm5_label == 'frame_only' and lex_label == 'frame_only':
        return 'frame_only'
    if llm5_label == 'none' and lex_label == 'none':
        return 'none'
    return 'disagree'


def opening(text, k=3):
    """First k words, lower-cased, punctuation stripped (frame match)."""
    w = re.findall(r"[\w']+", text.lower())
    return ' '.join(w[:k]) if len(w) >= k else None


def case_key(cell_id):
    _, item, L, p = cell_id.split('|')
    return f'{item}.{L}.p{int(p[1:])}'


# ----------------------------------------------------------------------------------------------- prep
def cmd_prep(args):
    import pandas as pd
    from transformers import AutoTokenizer
    from olens_improve.reconstruction import ar_token_ids
    t0 = time.time()
    bank = C.load_bank(FAM)
    lex = build_lexicons(bank)
    tok = AutoTokenizer.from_pretrained(str(C.BASE))
    three = list(C.read_jsonl(C.DATA / 'select/ca_three_settings.jsonl'))
    meta = {r['cell_id']: r for r in three}
    log('three', len(three))
    # metrics
    met = {}
    for L in LAYERS:
        for r in C.read_jsonl(C.DATA / f'metrics/ca_bullet_metrics.L{L}.jsonl'):
            met[r['cell_id']] = r['settings']
    # LLM labels: (cell, stripped text) -> row
    llm = {}
    for r in C.read_jsonl(C.DATA / 'judge/ca_labels/ca_llm_bullet_labels.jsonl'):
        llm[(r['cell_id'], r['text'])] = r
    # judge rows per (cell, setting)
    judge = {(r['cell_id'], r['setting']): r for r in C.read_jsonl(C.DATA / 'judge/ca/cell/ca_cell_rows.jsonl')}
    from wsbench.evals.conjunctive_association.judge import build_options
    opt_cache = {k: build_options(it) for k, it in bank.items()}
    by_gold = {(it['cluster'], it['gold_label']): it for it in bank.values()}

    def choice_kind(item_id, choice):
        """Judge pick -> 'gold' | 'contrast' | 'distr_rightX' (gold X value, wrong Y) | 'distr_wrongX' | 'cannot_tell'."""
        shown, gp, cp = opt_cache[item_id]
        if choice is None:
            return None
        if choice == gp:
            return 'gold'
        if cp is not None and choice == cp:
            return 'contrast'
        if not (1 <= choice <= len(shown)) or shown[choice - 1] not in bank[item_id]['mc_options']:
            return 'cannot_tell'
        it = bank[item_id]
        X = it['contrast_axis']
        o = by_gold[(it['cluster'], shown[choice - 1])]
        same = json.dumps(o['cell'].get(X), sort_keys=True) == json.dumps(it['cell'].get(X), sort_keys=True)
        return 'distr_rightX' if same else 'distr_wrongX'

    rows = []
    n_llm_miss = 0
    tok_mismatch = 0
    for r in three:
        cid = r['cell_id']
        L = lex[r['item_id']]
        for sid in SETTINGS:
            s = r['settings'][sid]
            ms = met.get(cid, {}).get(sid)
            jr = judge.get((cid, sid), {})
            nb = len(s['atoms'])
            for i, a in enumerate(s['atoms']):
                text = a['text'].strip()
                lab, f = L.label(text)
                labw, fw = L.label(a['scored_text'])
                lr = llm.get((cid, text))
                if lr is None:
                    n_llm_miss += 1
                b = ms['bullets'][i] if ms and ms.get('bullets') else None
                if b is not None and b['phrase_id'] != a['source_phrase_id']:
                    raise SystemExit(f'phrase mismatch {cid} {sid} {i}')
                if i < 50 and len(rows) < 2000:  # spot-check scored token count on the first rows
                    _, ids = ar_token_ids(tok, a['text'])
                    if min(len(ids), 32) != a['scored_token_count']:
                        tok_mismatch += 1
                q = (lr or {}).get('quote') or ''
                rows.append({
                    'cell_id': cid, 'key': case_key(cid), 'item_id': r['item_id'], 'cluster': r['group_id'],
                    'layer': r['layer'], 'position': r['position'], 'site': r.get('read_position_kind') or r.get('token'),
                    'rel_from_end': r.get('rel_from_end'), 'setting': sid, 'idx': i, 'nb': nb, 'text': text,
                    'scored_text': a['scored_text'], 'stok': a['scored_token_count'], 'trunc': bool(a['truncated']),
                    'sample_index': a['sample_index'], 'cache_key': a['cache_key'], 'phrase_id': a['source_phrase_id'],
                    'joint': ms.get('joint_fve_saved') if ms else None,
                    'solo': b['solo_fve'] if b else None, 'share': b['shapley_share'] if b else None,
                    'shapley': b['shapley'] if b else None, 'drop': b['loo_drop'] if b else None,
                    'coef': b['coefficient'] if b else None, 'dup': b['dup'] if b else None,
                    'llm': lr['label'] if lr else None, 'llm_quote': q,
                    'llm_quote_in_window': bool(q) and q.lower() in a['scored_text'].lower(),
                    'lex2': lab, 'lex2w': labw, 'gy': f['gy'], 'gyw': fw['gy'], 'allax': f['allax'],
                    'judge_pick': jr.get('pick'), 'judge_kind': choice_kind(r['item_id'], jr.get('choice')),
                    'judge_quote': jr.get('quote'), 'judge_qb': i in (jr.get('quote_bullets') or []),
                    'judge_quote_found': jr.get('quote_found_in_text'),
                })
    df = pd.DataFrame(rows)
    df['llm5'] = [llm5(a, b) if a is not None else None for a, b in zip(df.llm, df.lex2)]
    df['agreed'] = [agreed(a, b) if a is not None else None for a, b in zip(df.llm5, df.lex2)]
    df['open3'] = [opening(t, 3) for t in df.scored_text]
    log('selected bullets', len(df), 'llm missing', n_llm_miss, 'scored-token spot mismatches', tok_mismatch)
    # pool
    prow = []
    texts = []
    for pe in C.read_jsonl(C.DATA / 'select/ca_pool.jsonl'):
        r = meta[pe['cell_id']]
        for b in pe['bullets']:
            prow.append((pe['cell_id'], r['item_id'], r['group_id'], r['layer'], r['position'], b['sample_index'],
                         b['pos'], b['solo_fve'], b['cache_key'], b['status']))
            texts.append(b['text'])
    log('pool bullets', len(prow))
    # scored window (first 32 AR tokens) for every pool bullet
    cleaned, stoks, wtexts = [], [], []
    pat = re.compile(r"</?explanation>|<\|im_start\|>(system|user|assistant)?|<\|im_end\|>|<think>|</think>")
    for t in texts:
        cleaned.append(pat.sub('', t).strip())
    enc = tok(cleaned, add_special_tokens=False)['input_ids']
    special = set(tok.all_special_ids)
    for ids in enc:
        ids = [x for x in ids if x not in special]
        stoks.append(min(len(ids), 32))
        wtexts.append(tok.decode(ids[:32]) if len(ids) > 32 else None)
    log('tokenized pool')
    plab, plabw, pgy = [], [], []
    cache = {}
    for (cid, item_id, *_), t, w in zip(prow, texts, wtexts):
        k = (item_id, t)
        if k not in cache:
            lab, f = lex[item_id].label(t)
            if w is None:
                labw = lab
            else:
                labw, _ = lex[item_id].label(w)
            cache[k] = (lab, labw, f['gy'])
        lab, labw, gy = cache[k]
        plab.append(lab)
        plabw.append(labw)
        pgy.append(gy)
    pool = pd.DataFrame(prow, columns=['cell_id', 'item_id', 'cluster', 'layer', 'position', 'sample_index', 'pos',
                                       'solo', 'cache_key', 'status'])
    pool['text'] = [t.strip() for t in texts]
    pool['stok'] = stoks
    pool['trunc'] = [w is not None for w in wtexts]
    pool['lex2'] = plab
    pool['lex2w'] = plabw
    pool['gy'] = pgy
    pool['open3'] = [opening(w if w is not None else t, 3) for t, w in zip(cleaned, wtexts)]
    pool['open2'] = [opening(w if w is not None else t, 2) for t, w in zip(cleaned, wtexts)]
    # cross-check: pool stok vs selected atoms' scored_token_count on shared cache keys
    sk = dict(zip(df.cache_key, df.stok))
    chk = [(a, sk[k]) for k, a in zip(pool.cache_key, pool.stok) if k in sk]
    mism = sum(a != b for a, b in chk)
    log('pool stok vs atoms: checked', len(chk), 'mismatch', mism)
    # sample-level table from Best of 32 traces (joint FVE of each of the 32 samples)
    srow = []
    for r in three:
        tr = r['settings']['best_n_exact-n32']['trace']
        for t in tr:
            si = int(t['sample_id'].rsplit(':', 1)[1])
            srow.append((r['cell_id'], si, t.get('score')))
    samples = pd.DataFrame(srow, columns=['cell_id', 'sample_index', 'joint'])
    CACHE.mkdir(parents=True, exist_ok=True)
    with open(CACHE / 'tables.pkl', 'wb') as f:
        pickle.dump({'sel': df, 'pool': pool, 'samples': samples,
                     'meta': {'llm_missing': n_llm_miss, 'tok_spot_mismatch': tok_mismatch,
                              'pool_stok_checked': len(chk), 'pool_stok_mismatch': mism,
                              'built': time.strftime('%Y-%m-%d %H:%M:%S')}}, f, protocol=5)
    log('wrote', CACHE / 'tables.pkl', f'{time.time() - t0:.0f}s')
    print(df.groupby(['setting', 'llm5']).size().unstack(fill_value=0).to_string())
    print(df.groupby(['setting', 'lex2']).size().unstack(fill_value=0).to_string())
    print(pool.groupby('lex2').size().to_string())


def load_tables():
    with open(CACHE / 'tables.pkl', 'rb') as f:
        return pickle.load(f)




# ----------------------------------------------------------------------------------------------- final labels
# Items whose contrast-axis words are specific (a named feeling, belief, motive or event). Chosen AFTER reading
# 25 lex2 wrong-value pool bullets: on the excluded items the X words are generic or name other people
# (q01_e..j relation axis: "a mother drives her van"; q04 hidden/credit/stolen; q07 hidden/secret/share;
# q08 unaware/suspect). Reading: lex2 wrong-value precision 17/20 on these items vs 11/25 overall.
def clean_item(item_id):
    return item_id[:3] in ('q02', 'q03', 'q05', 'q06', 'q09', 'q10') or item_id in ('q01_a', 'q01_b', 'q01_c', 'q01_d')


def final_label(l5, lx):
    """Primary label for a selected bullet from the two labellers (module docstring)."""
    if l5 is None:
        return None
    G = l5 == 'gold' or lx == 'gold'
    Wl, Wx = l5 in WRONGX, lx in WRONGX
    if l5 == 'mixed' or lx == 'mixed' or (G and (Wl or Wx)):
        return 'mixed'
    if G:
        return 'gold'
    if Wl and Wx:
        return 'wrongX'
    if Wl or Wx:
        return 'wrongX_weak'
    if l5 == 'other_axis':
        return 'other_axis'
    if l5 == 'frame_only' or lx == 'frame_only':
        return 'frame_only'
    if lx == 'other_axis':
        return 'other_axis'
    return 'none'


def add_derived(df):
    df['final'] = [final_label(a, b) for a, b in zip(df.llm5, df.lex2)]
    df['clean'] = df.item_id.map(clean_item)
    # position-adjusted scores (Original / Best of 32): minus the mean at the same setting, layer, readout size, list
    # position. Combine 32 stays raw (its order is the greedy FVE order).
    for col in ('solo', 'share'):
        m = df.groupby(['setting', 'layer', 'nb', 'idx'])[col].transform('mean')
        adj = df[col] - m
        df[col + '_adj'] = np.where(df.setting == 'pooled_greedy_swap-n32', df[col], adj)
    # solo-FVE percentile within setting x layer (for picking reading cases)
    df['solo_pct'] = df.groupby(['setting', 'layer']).solo.rank(pct=True)
    return df


# ----------------------------------------------------------------------------------------------- bootstrap
class Boot:
    """Item-level (100) and related-item-group-level (10 groups q01..q10) bootstrap of ratio estimators.
    Every statistic uses the same resampling weights, so differences are paired."""

    def __init__(self, item_cluster, B=B_BOOT, seed=SEED):
        self.items = sorted(item_cluster)
        self.ii = {it: k for k, it in enumerate(self.items)}
        self.cl = sorted(set(item_cluster.values()))
        self.icl = np.array([self.cl.index(item_cluster[it]) for it in self.items])
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

    def ratio(self, N, D, nd=3):
        if D.sum() <= 0:
            return {'est': None, 'n': 0, 'items': 0}
        ri, rc = self._reps(N, D)
        return {'est': round(float(N.sum() / D.sum()), nd), 'ci': _ci(ri, nd), 'ci_groups': _ci(rc, nd),
                'n': round(float(D.sum()), 2), 'items': int((D > 0).sum())}

    def diff(self, N1, D1, N2, D2, nd=3):
        if D1.sum() <= 0 or D2.sum() <= 0:
            return {'est': None}
        a, ac = self._reps(N1, D1)
        b, bc = self._reps(N2, D2)
        return {'est': round(float(N1.sum() / D1.sum() - N2.sum() / D2.sum()), nd), 'ci': _ci(a - b, nd),
                'ci_groups': _ci(ac - bc, nd)}


def _ci(x, nd):
    x = x[np.isfinite(x)]
    if not len(x):
        return None
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [round(float(lo), nd), round(float(hi), nd)]


# ----------------------------------------------------------------------------------------------- pair rates
def group_pairs(gid, items, score, isA, isB, match=None, toks=None, tol=None, ck=None):
    """Within each group (readout or cell): wins (A > B, ties 1/2) and pairs, optionally only matched pairs.
    match: int codes (-1 = no key, never matches); toks + tol: |tA - tB| <= tol * max; ck: skip identical vectors.
    Returns (group items, wins, pairs) for groups with >= 1 pair."""
    order = np.argsort(gid, kind='stable')
    g = gid[order]
    bounds = np.flatnonzero(np.diff(g)) + 1
    starts = np.r_[0, bounds]
    ends = np.r_[bounds, len(g)]
    out_items, out_w, out_p = [], [], []
    sA, sB = isA[order], isB[order]
    for s, e in zip(starts, ends):
        sl = order[s:e]
        a = sl[sA[s:e]]
        b = sl[sB[s:e]]
        if not len(a) or not len(b):
            continue
        d = score[a][:, None] - score[b][None, :]
        ok = np.isfinite(d)
        if match is not None:
            ok &= (match[a][:, None] == match[b][None, :]) & (match[a][:, None] >= 0)
        if toks is not None:
            ta, tb = toks[a][:, None], toks[b][None, :]
            ok &= np.abs(ta - tb) <= tol * np.maximum(ta, tb)
        if ck is not None:
            ok &= ck[a][:, None] != ck[b][None, :]
        p = ok.sum()
        if not p:
            continue
        w = ((d > 0) & ok).sum() + 0.5 * ((d == 0) & ok).sum()
        out_items.append(items[sl[0]])
        out_w.append(w)
        out_p.append(p)
    return out_items, np.array(out_w, float), np.array(out_p, float)


def pair_stat(bt, gid, items, score, isA, isB, **kw):
    """Pooled pair rate (all pairs) and mean per-group AUROC, item- and group-bootstrapped."""
    it, w, p = group_pairs(gid, items, score, isA, isB, **kw)
    if not len(p):
        return {'pooled': {'est': None, 'n': 0}, 'groups': 0, 'pairs': 0}
    N, D = bt.agg(it, w, p)
    Na, Da = bt.agg(it, w / p)
    return {'pooled': bt.ratio(N, D), 'per_group_mean': bt.ratio(Na, Da), 'groups': len(p), 'pairs': int(p.sum())}


def codes(series):
    """String keys -> int codes; None/NaN -> -1 (never matches)."""
    cat = series.astype('category')
    return cat.cat.codes.to_numpy().astype(int)


# ----------------------------------------------------------------------------------------------- run
LAB_ORDER = ('gold', 'wrongX', 'wrongX_weak', 'mixed', 'other_axis', 'frame_only', 'none')


def cmd_run(args):
    t0 = time.time()
    T = load_tables()
    df = add_derived(T['sel'])
    pool = T['pool']
    samples = T['samples']
    bank = C.load_bank(FAM)
    bt = Boot({k: it['cluster'] for k, it in bank.items()})
    R = {'meta': {**T['meta'], 'bootstrap': {'B': B_BOOT, 'seed': SEED, 'units': 'ci = items (100); ci_groups = 10 '
                                             'related-item groups q01..q10'}}}
    sc = df[df.solo.notna() & df.final.notna()].copy()
    R['label_counts'] = {
        'final': {SL[s]: sc[sc.setting == s].final.value_counts().to_dict() for s in SETTINGS},
        'llm5': {SL[s]: sc[sc.setting == s].llm5.value_counts().to_dict() for s in SETTINGS},
        'lex2': {SL[s]: sc[sc.setting == s].lex2.value_counts().to_dict() for s in SETTINGS},
        'pool_lex2': pool[pool.solo.notna()].lex2.value_counts().to_dict(),
        'llm5_x_lex2_distinct': {f'{a}|{b}': int(n) for (a, b), n in
                                 sc.drop_duplicates(['cell_id', 'text']).groupby(['llm5', 'lex2']).size().items()},
    }
    log('A1')
    R['A1'] = run_a1(bt, sc, pool)
    log('A2')
    R['A2'] = run_a2(bt, sc)
    log('A3')
    R['A3'] = run_a3(bt, pool, bank)
    log('A4')
    R['A4'] = run_a4(bt, df, pool, samples)
    log('A5')
    R['A5'] = run_a5(bt, df, bank)
    R['meta']['runtime_s'] = round(time.time() - t0, 1)
    C.atomic_json(OUT / 'results.json', R)
    log('wrote', OUT / 'results.json')


def run_a1(bt, sc, pool):
    out = {'note': 'mean per-bullet metric by final label; scored readouts only; all layers pooled unless keyed by layer'}
    for metric in ('solo', 'share', 'drop'):
        t = {}
        for s in SETTINGS:
            d = sc[sc.setting == s]
            row, NDs = {}, {}
            for lab in LAB_ORDER:
                m = (d.final == lab).to_numpy()
                NDs[lab] = bt.agg(d.item_id.to_numpy()[m], d[metric].to_numpy()[m])
                row[lab] = bt.ratio(*NDs[lab], nd=4)
            for a, b in (('gold', 'wrongX'), ('gold', 'frame_only'), ('gold', 'none'), ('wrongX', 'frame_only'),
                         ('frame_only', 'none')):
                row[f'{a}-{b}'] = bt.diff(*NDs[a], *NDs[b], nd=4)
            t[SL[s]] = row
            for L in LAYERS:
                dl = d[d.layer == L]
                rl, NDl = {}, {}
                for lab in LAB_ORDER:
                    m = (dl.final == lab).to_numpy()
                    NDl[lab] = bt.agg(dl.item_id.to_numpy()[m], dl[metric].to_numpy()[m])
                    rl[lab] = bt.ratio(*NDl[lab], nd=4)
                rl['gold-wrongX'] = bt.diff(*NDl['gold'], *NDl['wrongX'], nd=4)
                rl['gold-frame_only'] = bt.diff(*NDl['gold'], *NDl['frame_only'], nd=4)
                t[f'{SL[s]}|L{L}'] = rl
        out[metric] = t
    site = {}
    for st, d in sc.groupby('site'):
        r = {}
        for lab in ('gold', 'wrongX', 'frame_only', 'none'):
            m = (d.final == lab).to_numpy()
            r[lab] = bt.ratio(*bt.agg(d.item_id.to_numpy()[m], d.solo.to_numpy()[m]), nd=4)
        site[st] = r
    out['solo_by_site_all_settings'] = site
    p = pool[pool.solo.notna()]
    pr = {}
    for L in (None,) + LAYERS:
        d = p if L is None else p[p.layer == L]
        r = {}
        for lab in ('gold', 'contrast', 'other_value', 'mixed', 'other_axis', 'frame_only', 'none'):
            m = (d.lex2 == lab).to_numpy()
            r[lab] = bt.ratio(*bt.agg(d.item_id.to_numpy()[m], d.solo.to_numpy()[m]), nd=4)
        pr['all' if L is None else f'L{L}'] = r
    out['pool_solo_by_lex2'] = pr
    return out


def readout_gid(d):
    return codes(d.cell_id + '|' + d.setting)


def run_a2(bt, sc):
    out = {'note': ('pair rate = P(score of A bullet > score of B bullet in the same readout), ties 1/2, pairs pooled; '
                    'adj = minus mean at same setting/layer/readout size/list position for Original and Best of 32, raw '
                    'for Combine 32; len = scored tokens within 20%')}
    comps = {
        'gold_vs_nongold': ('gold', ('wrongX', 'wrongX_weak', 'other_axis', 'frame_only', 'none')),
        'gold_vs_wrongX': ('gold', ('wrongX',)),
        'gold_vs_wrongX_any': ('gold', ('wrongX', 'wrongX_weak')),
        'gold_vs_frame': ('gold', ('frame_only',)),
        'gold_vs_none': ('gold', ('none',)),
        'gold_vs_other_axis': ('gold', ('other_axis',)),
        'wrongX_any_vs_frame': (('wrongX', 'wrongX_weak'), ('frame_only',)),
        'wrongX_any_vs_none': (('wrongX', 'wrongX_weak'), ('none',)),
        'frame_vs_none': ('frame_only', ('none',)),
    }
    variants = {'solo_raw': ('solo', False), 'solo_adj': ('solo_adj', False), 'solo_adj_len': ('solo_adj', True),
                'share_adj': ('share_adj', False), 'share_adj_len': ('share_adj', True)}

    def run(d, labcol, A, Bs, score, lenm):
        A = (A,) if isinstance(A, str) else A
        isA = d[labcol].isin(A).to_numpy()
        isB = d[labcol].isin(Bs).to_numpy()
        kw = {'toks': d.stok.to_numpy(float), 'tol': 0.2} if lenm else {}
        return pair_stat(bt, readout_gid(d), d.item_id.to_numpy(), d[score].to_numpy(float), isA, isB,
                         ck=codes(d.cache_key), **kw)

    for name, (A, Bs) in comps.items():
        res = {}
        for vname, (score, lenm) in variants.items():
            row = {SL[s]: run(sc[sc.setting == s], 'final', A, Bs, score, lenm) for s in SETTINGS}
            row['pooled'] = run(sc, 'final', A, Bs, score, lenm)
            res[vname] = row
        out[name] = res
    rob = {}
    for lname, labcol, A, Bs in (
            ('llm_only', 'llm5', 'gold', WRONGX),
            ('lex2_only', 'lex2', 'gold', WRONGX),
            ('final_strict', 'final', 'gold', ('wrongX',)),
            ('final_any', 'final', 'gold', ('wrongX', 'wrongX_weak'))):
        for sub, d0 in (('all_items', sc), ('clean_items', sc[sc.clean])):
            r = {}
            for vname in ('solo_adj', 'solo_adj_len', 'share_adj'):
                score, lenm = variants[vname]
                r[vname] = {SL[s]: run(d0[d0.setting == s], labcol, A, Bs, score, lenm)['pooled'] for s in SETTINGS}
                r[vname]['pooled'] = run(d0, labcol, A, Bs, score, lenm)['pooled']
            rob[f'{lname}|{sub}'] = r
    out['filler_test_robustness'] = rob
    u = sc.drop_duplicates(['cell_id', 'cache_key'])
    cg = codes(u.cell_id)
    xc = {}
    for name, (A, Bs) in (('gold_vs_wrongX', ('gold', ('wrongX',))),
                          ('gold_vs_wrongX_any', ('gold', ('wrongX', 'wrongX_weak'))),
                          ('gold_vs_frame', ('gold', ('frame_only',))), ('gold_vs_none', ('gold', ('none',)))):
        for sub, m in (('all_items', np.ones(len(u), bool)), ('clean_items', u.clean.to_numpy())):
            for lenm in (False, True):
                kw = {'toks': u.stok.to_numpy(float), 'tol': 0.2} if lenm else {}
                xc[f'{name}|{sub}|{"len" if lenm else "raw"}'] = pair_stat(
                    bt, cg, u.item_id.to_numpy(), u.solo.to_numpy(float),
                    u.final.isin((A,)).to_numpy() & m, u.final.isin(Bs).to_numpy() & m, **kw)
    out['same_cell_across_settings'] = xc
    top = {}
    for s in SETTINGS:
        d = sc[(sc.setting == s) & (sc.final != 'mixed')]
        its, hit, ch = [], [], []
        for cid, g in d.groupby('cell_id'):
            ng = int((g.final == 'gold').sum())
            if 0 < ng < len(g):
                its.append(g.item_id.iloc[0])
                hit.append(float(g.final.iloc[int(np.argmax(g.share.to_numpy()))] == 'gold'))
                ch.append(ng / len(g))
        N1, D1 = bt.agg(its, hit)
        N2, D2 = bt.agg(its, ch)
        top[SL[s]] = {'top_is_gold': bt.ratio(N1, D1), 'chance': bt.ratio(N2, D2),
                      'minus_chance': bt.diff(N1, D1, N2, D2), 'readouts': len(its)}
    out['top_share_is_gold'] = top
    conf = {}
    for s in SETTINGS:
        d = sc[sc.setting == s]
        isA = (d.final == 'gold').to_numpy()
        isB = d.final.isin(('wrongX', 'wrongX_weak', 'other_axis', 'frame_only', 'none')).to_numpy()
        conf[SL[s]] = {
            'gold_later_than_sibling': pair_stat(bt, readout_gid(d), d.item_id.to_numpy(), d.idx.to_numpy(float), isA, isB)['pooled'],
            'gold_longer_than_sibling': pair_stat(bt, readout_gid(d), d.item_id.to_numpy(), d.stok.to_numpy(float), isA, isB)['pooled'],
            'mean_solo_by_position': {int(k): round(float(v), 4) for k, v in d.groupby('idx').solo.mean().items()},
            'gold_share_by_position': {int(k): round(float(v), 4) for k, v in d.groupby('idx').final.apply(lambda x: (x == 'gold').mean()).items()},
        }
    out['confounds'] = conf
    return out


def pool_frame(pool):
    p = pool[pool.solo.notna()].drop_duplicates(['cell_id', 'cache_key']).reset_index(drop=True)
    p['clean'] = p.item_id.map(clean_item)
    return p


def run_a3(bt, pool, bank):
    out = {'note': ('pool = every bullet of the cell\'s 32 samples (first 4 per sample), deduplicated by AR vector; '
                    'labels = lex2 on the full text ("lex2") or on the 32-token scored window ("lex2w"); per cell: '
                    'P(solo of A > solo of B), ties 1/2; pooled over pairs and as the mean of per-cell AUROCs')}
    p = pool_frame(pool)
    gid = codes(p.cell_id)
    items = p.item_id.to_numpy()
    solo = p.solo.to_numpy(float)
    m3, m2 = codes(p.open3), codes(p.open2)
    posc = p.pos.to_numpy().astype(int)
    toks = p.stok.to_numpy(float)
    comps = {
        'gold_vs_wrongX': ('gold', WRONGX), 'gold_vs_contrast': ('gold', ('contrast',)),
        'gold_vs_frame': ('gold', ('frame_only',)), 'gold_vs_none': ('gold', ('none',)),
        'gold_vs_other_axis': ('gold', ('other_axis',)),
        'wrongX_vs_frame': (WRONGX, ('frame_only',)), 'wrongX_vs_none': (WRONGX, ('none',)),
        'frame_vs_none': (('frame_only',), ('none',)),
    }
    matched = ('gold_vs_wrongX', 'gold_vs_contrast', 'gold_vs_frame', 'gold_vs_none', 'wrongX_vs_frame', 'frame_vs_none')
    for labsrc in ('lex2', 'lex2w'):
        lab = p[labsrc]
        res = {}
        for name, (A, Bs) in comps.items():
            A = (A,) if isinstance(A, str) else A
            for sub, m in (('all_items', np.ones(len(p), bool)), ('clean_items', p.clean.to_numpy())):
                isA = lab.isin(A).to_numpy() & m
                isB = lab.isin(Bs).to_numpy() & m
                r = {'raw': pair_stat(bt, gid, items, solo, isA, isB)}
                if labsrc == 'lex2' and name in matched:
                    r['same_pos'] = pair_stat(bt, gid, items, solo, isA, isB, match=posc)
                    r['len_matched'] = pair_stat(bt, gid, items, solo, isA, isB, toks=toks, tol=0.2)
                    r['same_open3'] = pair_stat(bt, gid, items, solo, isA, isB, match=m3)
                    r['same_open2'] = pair_stat(bt, gid, items, solo, isA, isB, match=m2)
                    r['same_open2_len'] = pair_stat(bt, gid, items, solo, isA, isB, match=m2, toks=toks, tol=0.2)
                res[f'{name}|{sub}'] = r
        out[labsrc] = res
    lab = p.lex2
    isA = (lab == 'gold').to_numpy()
    isB = lab.isin(WRONGX).to_numpy()
    # orientation: most groups hold both directions of the same pair (gold envy / contrast pride and the reverse).
    # If FVE tracked correctness, gold would win in BOTH directions; if it tracked the word, the same word would win in
    # both (AUROC_dir1 = 1 - AUROC_dir2).
    gval = {k: f"{it['contrast_axis']}={it['axis_concepts'].get(it['contrast_axis'])}" for k, it in bank.items()}
    p['gold_value'] = p.item_id.map(gval)
    ori = {}
    for (cl, gv), d in p.groupby(['cluster', 'gold_value']):
        m = ((p.cluster == cl) & (p.gold_value == gv)).to_numpy()
        r = pair_stat(bt, gid, items, solo, isA & m, isB & m)
        ori[f'{cl}|{gv}'] = {'pooled': r['pooled'], 'per_cell_mean': r.get('per_group_mean'), 'cells': r.get('groups', 0),
                             'pairs': r.get('pairs', 0), 'items': int(d.item_id.nunique())}
    out['gold_vs_wrongX_by_gold_value'] = ori
    # two-direction groups (contrast axis has 2 values, both directions present): balanced = mean of the two
    # directions' gold-beats-wrong rates (what correctness would raise); word = half their difference (a preference
    # for the first value's words whatever is true)
    two = {}
    bal_reps = []
    for cl in sorted(p.cluster.unique()):
        vals = sorted(p[p.cluster == cl].gold_value.unique())
        if cl == 'q01' or len(vals) != 2:
            continue
        NDs = []
        for gv in vals:
            m = ((p.cluster == cl) & (p.gold_value == gv)).to_numpy()
            it, w, pr = group_pairs(gid, items, solo, isA & m, isB & m)
            NDs.append(bt.agg(it, w, pr) if len(pr) else None)
        if any(x is None for x in NDs):
            two[cl] = {'values': vals, 'note': 'one direction has no gold/wrong pairs'}
            continue
        (N1, D1), (N2, D2) = NDs
        r1, _ = bt._reps(N1, D1)
        r2, _ = bt._reps(N2, D2)
        a1, a2 = N1.sum() / D1.sum(), N2.sum() / D2.sum()
        bal_reps.append(0.5 * (r1 + r2))
        two[cl] = {'values': vals, 'gold_beats_wrong': [round(float(a1), 3), round(float(a2), 3)],
                   'balanced': round(float(0.5 * (a1 + a2)), 3), 'balanced_ci': _ci(0.5 * (r1 + r2), 3),
                   'word_pref_for_first_value': round(float(0.5 * (a1 - a2)), 3), 'word_ci': _ci(0.5 * (r1 - r2), 3),
                   'pairs': [int(D1.sum()), int(D2.sum())]}
    if bal_reps:
        mb = np.nanmean(np.vstack(bal_reps), axis=0)
        two['mean_balanced_over_groups'] = {'est': round(float(np.mean([v['balanced'] for v in two.values()
                                                                          if 'balanced' in v])), 3), 'ci': _ci(mb, 3),
                                            'groups': len(bal_reps)}
    out['two_direction_groups'] = two
    pc = {}
    for cl in sorted(p.cluster.unique()):
        m = (p.cluster == cl).to_numpy()
        r = pair_stat(bt, gid, items, solo, isA & m, isB & m)
        pc[cl] = {'pooled': r['pooled'], 'per_group_mean': r.get('per_group_mean'), 'cells': r.get('groups', 0)}
    out['gold_vs_wrongX_by_group'] = pc
    bl = {}
    isF = (lab == 'frame_only').to_numpy()
    isN = (lab == 'none').to_numpy()
    for L in LAYERS:
        m = (p.layer == L).to_numpy()
        for sub, ms in (('all_items', np.ones(len(p), bool)), ('clean_items', p.clean.to_numpy())):
            bl[f'L{L}|{sub}'] = {
                'gold_vs_wrongX': pair_stat(bt, gid, items, solo, isA & m & ms, isB & m & ms)['pooled'],
                'gold_vs_frame': pair_stat(bt, gid, items, solo, isA & m & ms, isF & m & ms)['pooled'],
                'gold_vs_none': pair_stat(bt, gid, items, solo, isA & m & ms, isN & m & ms)['pooled']}
    out['by_layer'] = bl
    cl_ = p.clean.to_numpy()
    out['counts'] = {'pool_bullets_dedup': int(len(p)), 'cells_with_gold': int(p[isA].cell_id.nunique()),
                     'cells_with_wrongX': int(p[isB].cell_id.nunique()),
                     'cells_with_both': int(len(set(p[isA].cell_id) & set(p[isB].cell_id))),
                     'cells_with_both_clean': int(len(set(p[isA & cl_].cell_id) & set(p[isB & cl_].cell_id))),
                     'gold_bullets': int(isA.sum()), 'wrongX_bullets': int(isB.sum()),
                     'gold_bullets_clean': int((isA & cl_).sum()), 'wrongX_bullets_clean': int((isB & cl_).sum())}
    return out


def run_a4(bt, df, pool, samples):
    out = {}
    sc = df[df.final.notna()]
    cells = sorted(df.cell_id.unique())
    item_of = dict(zip(df.cell_id, df.item_id))
    has = {}
    for labcol, labs in (('final', ('gold', 'wrongX', 'wrongX_weak', 'frame_only')), ('lex2', ('gold',)),
                         ('llm5', ('gold',)), ('agreed', ('gold',))):
        for lab in labs:
            r, NDs = {}, {}
            for s in SETTINGS:
                d = sc[sc.setting == s]
                hit = d.groupby('cell_id')[labcol].apply(lambda x: float((x == lab).any()))
                its = [item_of[c] for c in hit.index]
                NDs[s] = bt.agg(its, hit.to_numpy())
                r[SL[s]] = bt.ratio(*NDs[s])
            r['Best of 32 - Original'] = bt.diff(*NDs[SETTINGS[1]], *NDs[SETTINGS[0]])
            r['Combine 32 - Original'] = bt.diff(*NDs[SETTINGS[2]], *NDs[SETTINGS[0]])
            r['Combine 32 - Best of 32'] = bt.diff(*NDs[SETTINGS[2]], *NDs[SETTINGS[1]])
            has[f'{labcol}:{lab}'] = r
    out['readout_has_label'] = has
    # random baselines from pool labels (lex2), so selected and baseline use the same labeller
    p = pool[pool.solo.notna()]
    base_all = {}
    for sub in ('all_items', 'clean_items'):
        for lab, labset in (('gold', ('gold',)), ('wrongX', WRONGX)):
            pp = p if sub == 'all_items' else p[p.item_id.map(clean_item)]
            cs = [c for c in cells if sub == 'all_items' or clean_item(item_of[c])]
            flag = pp.lex2.isin(labset)
            samp = flag.groupby([pp.cell_id, pp.sample_index]).any()
            frac32 = samp.groupby(level=0).mean()
            any32 = samp.groupby(level=0).any().astype(float)
            pu = pp.drop_duplicates(['cell_id', 'cache_key'])
            ng = pu.lex2.isin(labset).groupby(pu.cell_id).sum()
            nn = pu.groupby('cell_id').size()

            def hyper(n, g, k=4):
                if n < k:
                    return float(g > 0)
                return 1.0 - math.comb(int(n - g), k) / math.comb(int(n), k)
            rand4 = {c: hyper(nn[c], ng.get(c, 0)) for c in nn.index}
            sel = {s: sc[sc.setting == s].groupby('cell_id').lex2.apply(lambda x: float(x.isin(labset).any())) for s in SETTINGS}

            def arr(series):
                return np.array([float(series.get(c, np.nan)) for c in cs])
            A = {'random one of 32 samples': arr(frac32), 'random 4 pool bullets': arr(rand4), 'pool has it': arr(any32)}
            for s in SETTINGS:
                A[SL[s]] = arr(sel[s])
            ok = np.all([np.isfinite(v) for v in A.values()], axis=0)
            its = [item_of[c] for c, o in zip(cs, ok) if o]
            NDs = {k: bt.agg(its, v[ok]) for k, v in A.items()}
            base = {k: bt.ratio(*nd) for k, nd in NDs.items()}
            base['Original - random one of 32'] = bt.diff(*NDs['Original'], *NDs['random one of 32 samples'])
            base['Best of 32 - random one of 32'] = bt.diff(*NDs['Best of 32'], *NDs['random one of 32 samples'])
            base['Combine 32 - random 4 pool bullets'] = bt.diff(*NDs['Combine 32'], *NDs['random 4 pool bullets'])
            base['cells'] = int(ok.sum())
            pg = A['pool has it'][ok] > 0
            base['cells_pool_has_it'] = int(pg.sum())
            for s in SETTINGS:
                base[f'missing_from_readout_given_pool_has_it[{SL[s]}]'] = round(float(np.mean(A[SL[s]][ok][pg] == 0)), 3)
            base_all[f'{lab}|{sub}'] = base
    out['lex2_vs_random_baselines'] = base_all
    # sample-level: within cell, joint FVE of the 32 samples (Best of 32 trace) by what the sample's bullets name
    flags = p.assign(g=p.lex2.eq('gold'), w=p.lex2.isin(WRONGX)).groupby(['cell_id', 'sample_index'])[['g', 'w']].any()
    S = samples[samples.joint.notna()].merge(flags.reset_index(), on=['cell_id', 'sample_index'], how='left')
    S[['g', 'w']] = S[['g', 'w']].fillna(False).astype(bool)
    S['item_id'] = S.cell_id.map(item_of)
    S['clean'] = S.item_id.map(clean_item)
    gid = codes(S.cell_id)
    sl = {}
    for sub, m in (('all_items', np.ones(len(S), bool)), ('clean_items', S.clean.to_numpy())):
        g = S.g.to_numpy()
        w = S.w.to_numpy() & ~g
        n = ~g & ~S.w.to_numpy()
        J = S.joint.to_numpy(float)
        it = S.item_id.to_numpy()
        sl[f'gold_sample_vs_no_gold|{sub}'] = pair_stat(bt, gid, it, J, g & m, ~g & m)
        sl[f'gold_sample_vs_wrongX_only_sample|{sub}'] = pair_stat(bt, gid, it, J, g & m, w & m)
        sl[f'gold_sample_vs_neither|{sub}'] = pair_stat(bt, gid, it, J, g & m, n & m)
        sl[f'wrongX_only_sample_vs_neither|{sub}'] = pair_stat(bt, gid, it, J, w & m, n & m)
    out['sample_level_joint_fve_auroc'] = sl
    j = df.drop_duplicates(['cell_id', 'setting'])[['cell_id', 'setting', 'item_id', 'judge_pick', 'judge_kind']]
    jr = {}
    for kind in ('gold', 'contrast', 'distr_rightX', 'distr_wrongX', 'cannot_tell'):
        NDs, r = {}, {}
        for s in SETTINGS:
            d = j[j.setting == s]
            NDs[s] = bt.agg(d.item_id, (d.judge_kind == kind).astype(float))
            r[SL[s]] = bt.ratio(*NDs[s], nd=4)
        r['Best of 32 - Original'] = bt.diff(*NDs[SETTINGS[1]], *NDs[SETTINGS[0]], nd=4)
        r['Combine 32 - Original'] = bt.diff(*NDs[SETTINGS[2]], *NDs[SETTINGS[0]], nd=4)
        jr[kind] = r
    jr['counts'] = {SL[s]: j[j.setting == s].judge_kind.value_counts().to_dict() for s in SETTINGS}
    out['judge_per_cell'] = jr
    it = {}
    for s in SETTINGS:
        rr = json.loads((C.DATA / f'judge/ca/item/{s}/results.json').read_text())['rows']
        it[SL[s]] = {'gold_items': sorted(r['id'] for r in rr if r['pick'] == 'gold'),
                     'breakdown': dict(collections.Counter(r['pick'] for r in rr))}
    g0, g1, g2 = (set(it[SL[s]]['gold_items']) for s in SETTINGS)
    it['overlap'] = {'Original&Best': len(g0 & g1), 'Original&Combine': len(g0 & g2), 'Best&Combine': len(g1 & g2),
                     'all_three': len(g0 & g1 & g2), 'only_Original': sorted(g0 - g1 - g2),
                     'only_Best': sorted(g1 - g0 - g2), 'only_Combine': sorted(g2 - g0 - g1)}
    out['judge_item_level'] = it
    return out


def readout_classes(df):
    import pandas as pd
    sc = df[df.final.notna()]
    rd = []
    for (cid, s), g in sc.groupby(['cell_id', 'setting'], sort=False):
        fin = set(g.final)
        allp = bool(((g.final == 'gold') & g.allax).any())
        full = bool(((g.final == 'gold') & g.gy).any())
        anyg = 'gold' in fin
        anyg_y = anyg and bool(g.gy.any())
        if allp:
            cls = 'gold_all_parts_one_bullet'
        elif full:
            cls = 'gold_X_and_Y_one_bullet'
        elif anyg_y:
            cls = 'gold_X_and_Y_split'
        elif anyg:
            cls = 'gold_X_only'
        elif fin & {'wrongX', 'wrongX_weak', 'mixed'}:
            cls = 'wrong_X_only'
        else:
            cls = 'no_X_value'
        qb = g[g.judge_qb]
        rd.append({'cell_id': cid, 'key': g.key.iloc[0], 'setting': s, 'item_id': g.item_id.iloc[0], 'cls': cls,
                   'agreed_gold': bool((g.agreed == 'gold').any()),
                   'pick': g.judge_kind.iloc[0], 'quote': g.judge_quote.iloc[0],
                   'quote_found': bool(g.judge_quote_found.iloc[0]),
                   'quote_final': ','.join(str(x) for x in qb.final) if len(qb) else '',
                   'quote_llm5': ','.join(str(x) for x in qb.llm5) if len(qb) else '',
                   'quote_lex2': ','.join(str(x) for x in qb.lex2) if len(qb) else ''})
    return pd.DataFrame(rd)


def run_a5(bt, df, bank):
    import pandas as pd
    out = {'note': ('readout classes from final labels; Y = the other varied axis; gold Y from the lexicon (credit words '
                    'of the gold Y value). The per-cell judge needs both X and Y to pick gold among its 10 options.')}
    R = readout_classes(df)
    out['crosstab_class_x_pick'] = {SL[s]: {c: {k: int(v) for k, v in col.items()} for c, col in
                                            pd.crosstab(R[R.setting == s].cls, R[R.setting == s].pick).to_dict().items()}
                                    for s in SETTINGS}
    out['crosstab_class_x_pick_all'] = {c: {k: int(v) for k, v in col.items()} for c, col in
                                        pd.crosstab(R.cls, R.pick).to_dict().items()}
    pg = {}
    for cls, d in R.groupby('cls'):
        pg[cls] = {'P(judge gold)': bt.ratio(*bt.agg(d.item_id, (d.pick == 'gold').astype(float))),
                   'P(judge contrast)': bt.ratio(*bt.agg(d.item_id, (d.pick == 'contrast').astype(float))),
                   'P(judge distractor, right X)': bt.ratio(*bt.agg(d.item_id, (d.pick == 'distr_rightX').astype(float))),
                   'P(judge distractor, wrong X)': bt.ratio(*bt.agg(d.item_id, (d.pick == 'distr_wrongX').astype(float))),
                   'readouts': int(len(d))}
    out['judge_given_class'] = pg

    def kappa(a, b):
        a, b = np.asarray(a, bool), np.asarray(b, bool)
        po = np.mean(a == b)
        pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
        return round(float((po - pe) / (1 - pe)), 3) if pe < 1 else None
    jg = (R.pick == 'gold').to_numpy()
    lg = R.cls.str.startswith('gold').to_numpy()
    lxy = R.cls.isin(['gold_all_parts_one_bullet', 'gold_X_and_Y_one_bullet', 'gold_X_and_Y_split']).to_numpy()
    wrong_pick = R.pick.isin(['contrast', 'distr_wrongX']).to_numpy()
    out['agreement'] = {
        'judge_gold_vs_readout_has_gold_bullet': {'kappa': kappa(jg, lg), 'both': int((jg & lg).sum()),
                                                  'judge_only': int((jg & ~lg).sum()), 'labels_only': int((~jg & lg).sum()),
                                                  'neither': int((~jg & ~lg).sum())},
        'judge_gold_vs_readout_names_gold_X_and_Y': {'kappa': kappa(jg, lxy), 'both': int((jg & lxy).sum()),
                                                     'judge_only': int((jg & ~lxy).sum()),
                                                     'labels_only': int((~jg & lxy).sum())},
        'judge_wrongX_pick': {'n': int(wrong_pick.sum()),
                              'readout_has_wrongX_bullet_only': int((wrong_pick & (R.cls == 'wrong_X_only').to_numpy()).sum()),
                              'readout_has_gold_bullet': int((wrong_pick & lg).sum()),
                              'readout_no_X_value': int((wrong_pick & (R.cls == 'no_X_value').to_numpy()).sum())},
    }
    ev = {}
    for pick, d in R[R.pick.isin(['gold', 'contrast', 'distr_rightX', 'distr_wrongX'])].groupby('pick'):
        ev[pick] = {'readouts': int(len(d)), 'quote_found_in_text': int(d.quote_found.sum()),
                    'quoted_bullet_final': dict(collections.Counter(
                        ','.join(sorted(set(x.split(',')))) if x else '(quote not located)' for x in d.quote_final))}
    out['evidence_quoted_bullet_labels'] = ev
    for cls in ('gold_all_parts_one_bullet', 'gold_X_and_Y_one_bullet'):
        miss = R[(R.cls == cls) & (R.pick == 'cannot_tell')]
        out[f'misses[{cls}]_cannot_tell'] = {
            'n': int(len(miss)), 'of': int((R.cls == cls).sum()),
            'agreed_gold_n': int(miss.agreed_gold.sum()), 'of_agreed_gold': int(((R.cls == cls) & R.agreed_gold).sum()),
            'rows': miss[['key', 'setting', 'quote', 'agreed_gold']].to_dict('records')[:80]}
    # manual reading of judge gold picks on readouts without any gold-labelled bullet (a5_judge_gold_reading.tsv)
    for name, fn in (('judge_gold_without_gold_bullet_reading', 'a5_judge_gold_reading.tsv'),
                     ('judge_cannot_tell_on_agreed_all_parts_reading', 'a5_judge_miss_reading.tsv')):
        rp = OUT / fn
        if rp.exists():
            rows = [ln.split('\t') for ln in rp.read_text().splitlines()[1:] if ln.strip()]
            out[name] = {'n_read': len(rows), 'verdicts': dict(collections.Counter(r[2] for r in rows)), 'file': str(rp)}
    not_on_gold = R[(R.pick == 'gold') & ~R.quote_final.str.contains('gold') & ~R.quote_final.str.contains('mixed')]
    out['judge_gold_quote_not_on_gold_bullet'] = {
        'n': int(len(not_on_gold)), 'of': int((R.pick == 'gold').sum()),
        'rows': not_on_gold[['key', 'setting', 'quote', 'quote_final', 'quote_llm5', 'quote_lex2', 'cls']].to_dict('records')}

    def overlap(cid, q):
        stim = bank[cid.split('|')[1]]['stimulus'].lower()
        ws = re.findall(r"[a-z']{4,}", (q or '').lower())
        return (sum(w in stim for w in ws) / len(ws)) if ws else None
    jgR = R[R.pick == 'gold'].copy()
    jgR['stim_overlap'] = [overlap(c, q) for c, q in zip(jgR.cell_id, jgR.quote)]
    on = jgR.quote_final.str.contains('gold')
    out['judge_gold_quote_word_overlap_with_story'] = {'quote_on_gold_bullet': _mean(jgR[on].stim_overlap),
                                                       'quote_not_on_gold_bullet': _mean(jgR[~on].stim_overlap)}
    # item-level judge vs labels: item judged gold vs item has any gold X+Y readout in that setting
    it = {}
    for s in SETTINGS:
        rr = {r['id']: r for r in json.loads((C.DATA / f'judge/ca/item/{s}/results.json').read_text())['rows']}
        d = R[R.setting == s]
        has_xy = d.groupby('item_id').cls.apply(lambda x: x.isin(['gold_all_parts_one_bullet', 'gold_X_and_Y_one_bullet', 'gold_X_and_Y_split']).any())
        has_g = d.groupby('item_id').cls.apply(lambda x: x.str.startswith('gold').any())
        ig = {k: v['pick'] == 'gold' for k, v in rr.items()}
        it[SL[s]] = {'item_gold': int(sum(ig.values())),
                     'item_gold_and_has_XY_readout': int(sum(ig[k] and has_xy.get(k, False) for k in ig)),
                     'items_with_XY_readout': int(has_xy.sum()), 'items_with_gold_X_readout': int(has_g.sum()),
                     'item_gold_without_any_gold_X_readout': sorted(k for k in ig if ig[k] and not has_g.get(k, False))}
    out['item_level'] = it
    R.to_pickle(CACHE / 'a5_readouts.pkl')
    return out


def _mean(s):
    s = [x for x in s if x is not None and np.isfinite(x)]
    return round(float(np.mean(s)), 3) if s else None


# ----------------------------------------------------------------------------------------------- show / sample
def _r(x, nd=4):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if np.isfinite(x) else None


def bullet_record(r, LX):
    return {'index': int(r.idx), 'text': r.text, 'scored_text': r.scored_text if r.trunc else None,
            'scored_tokens': int(r.stok), 'truncated': bool(r.trunc),
            'label': r.final, 'llm_label': r.llm5, 'llm_quote': r.llm_quote or None, 'lex2_label': r.lex2,
            'lex2_label_in_window': r.lex2w, 'lex2_words': LX.words(r.text),
            'solo_fve': _r(r.solo), 'solo_pct_in_setting_layer': _r(r.solo_pct, 3), 'shapley_share': _r(r.share),
            'shapley': _r(r.shapley), 'loo_drop': _r(r['drop']), 'coefficient': _r(r.coef, 3),
            'judge_quote_on_this_bullet': bool(r.judge_qb)}


def item_record(it, bank):
    X = it['contrast_axis']
    partner = next(o for o in bank.values() if o['cluster'] == it['cluster'] and o['gold_label'] == it['contrast_label'])
    return {'id': it['id'], 'group': it['cluster'], 'stimulus': it['stimulus'],
            'prompt_user_turn': it['stimulus'] + '\n\nSummarize the preceding story in one sentence.',
            'gold_label': it['gold_label'], 'contrast_label': it['contrast_label'], 'contrast_axis': X,
            'gold_value_on_axis': it['axis_concepts'].get(X), 'contrast_value_on_axis': partner['axis_concepts'].get(X),
            'varied_axes': it['varied_axes'], 'axis_concepts': it['axis_concepts']}


def cmd_show(args):
    T = load_tables()
    df = add_derived(T['sel'])
    bank = C.load_bank(FAM)
    LEX = build_lexicons(bank)
    d = df[df.key == args.key]
    if args.setting:
        d = d[d.setting.map(SL) == args.setting]
    if not len(d):
        raise SystemExit('no such case')
    it = bank[d.item_id.iloc[0]]
    rec = item_record(it, bank)
    print(json.dumps({k: rec[k] for k in ('id', 'stimulus', 'gold_label', 'contrast_label', 'contrast_axis',
                                          'gold_value_on_axis', 'contrast_value_on_axis')}, ensure_ascii=False, indent=1))
    print('site', d.site.iloc[0], 'layer', d.layer.iloc[0], 'pos', d.position.iloc[0])
    for s, g in d.groupby('setting', sort=False):
        print(f'\n== {SL[s]}  joint FVE {_r(g.joint.iloc[0])}  judge {g.judge_kind.iloc[0]} quote={g.judge_quote.iloc[0]!r}')
        for _, r in g.iterrows():
            print(f"  [{r.idx}] final={r.final} llm={r.llm5} lex2={r.lex2} solo={_r(r.solo)} pct={_r(r.solo_pct, 2)} "
                  f"share={_r(r.share)} drop={_r(r['drop'])} coef={_r(r.coef, 2)} stok={r.stok} judgeq={r.judge_qb}")
            print('      ', repr(r.text[:400]), ' llmq=', repr(r.llm_quote), ' words=', LEX[r.item_id].words(r.text))
    if args.pool:
        p = pool_frame(T['pool'])
        p = p[(p.cell_id == d.cell_id.iloc[0]) & p.lex2.isin(['gold', 'contrast', 'other_value', 'mixed'])]
        print('\n== pool bullets with an X value (lex2):', len(p))
        for _, r in p.sort_values('solo', ascending=False).head(args.n).iterrows():
            print(f'  s{r.sample_index}.{r.pos} {r.lex2} solo={_r(r.solo)} stok={r.stok} | {r.text[:200]!r}')


def cmd_sample(args):
    T = load_tables()
    df = add_derived(T['sel'])
    bank = C.load_bank(FAM)
    LEX = build_lexicons(bank)
    sc = df[df.solo.notna() & df.final.notna()]
    in_win_gold = (sc.lex2w == 'gold') | (sc.llm_quote_in_window & (sc.llm5 == 'gold'))
    in_win_wrong = sc.lex2w.isin(WRONGX) | (sc.llm_quote_in_window & sc.llm5.isin(WRONGX))
    strict_gold = sc[(sc.final == 'gold') & (sc.agreed == 'gold') & in_win_gold]
    wrong = sc[(sc.final == 'wrongX') & in_win_wrong]

    def pick(cands, n, ascending, max_per_group=2):
        cands = cands.sort_values(['solo_pct', 'solo'], ascending=ascending)
        chosen, items, groups, sets = [], set(), collections.Counter(), collections.Counter()
        for _, r in cands.iterrows():
            if r.item_id in items or groups[r.cluster] >= max_per_group or sets[r.setting] >= 5:
                continue
            chosen.append(r)
            items.add(r.item_id)
            groups[r.cluster] += 1
            sets[r.setting] += 1
            if len(chosen) == n:
                break
        return chosen
    # wrong-value cases: tier 1 = the LLM itself says "contrast" (both labellers agree on the contrast side); tier 2 =
    # LLM other value outside the groups whose contrast-axis words are generic verbs (q04 hide/credit, q07 hide/tell,
    # q08 unaware/suspect), where the reading found most agreed wrong-value labels borderline.
    hi = wrong[wrong.solo_pct >= 0.75]   # "high FVE" = top quarter of solo FVE within setting x layer
    tier1 = hi[hi.llm5 == 'contrast']
    tier2 = hi[(hi.llm5 != 'contrast') & ~hi.cluster.isin(['q04', 'q07', 'q08'])]
    w1 = pick(tier1, 12, False)
    used = {r.item_id for r in w1}
    w2 = pick(tier2[~tier2.item_id.isin(used)], 12 - len(w1), False) if len(w1) < 12 else []
    picks = {'high_fve_gold': pick(strict_gold, 12, False), 'high_fve_wrong_value': w1 + w2,
             'low_fve_gold': pick(strict_gold, 12, True)}
    pu = pool_frame(T['pool'])
    cases = []
    for ctype, rows in picks.items():
        for r in rows:
            g = sc[(sc.cell_id == r.cell_id) & (sc.setting == r.setting)].sort_values('idx')
            pc = pu[pu.cell_id == r.cell_id]
            ga = pc[pc.lex2 == 'gold'].solo.to_numpy()
            wa = pc[pc.lex2.isin(WRONGX)].solo.to_numpy()
            auc = None
            if len(ga) and len(wa):
                dd = ga[:, None] - wa[None, :]
                auc = round(float(((dd > 0).sum() + 0.5 * (dd == 0).sum()) / dd.size), 3)
            it = bank[r.item_id]
            cases.append({
                'case_key': r.key, 'setting': SL[r.setting], 'case_type': ctype, 'focal_bullet': int(r.idx),
                'focal_summary': {'label': r.final, 'solo_fve': _r(r.solo), 'solo_pct_in_setting_layer': _r(r.solo_pct, 3),
                                  'shapley_share': _r(r.share),
                                  'rank_by_share_in_readout': int((g.share > r.share).sum() + 1)},
                'item': item_record(it, bank),
                'read_site': {'layer': int(r.layer), 'position': int(r.position), 'site': r.site,
                              'tokens_from_end': int(r.rel_from_end)},
                'readout': {'joint_fve': _r(r.joint), 'n_bullets': int(r.nb),
                            'judge_per_cell': {'pick': r.judge_kind, 'quote': r.judge_quote}},
                'bullets': [bullet_record(b, LEX[r.item_id]) for _, b in g.iterrows()],
                'pool_context_lex2': {'pool_bullets': int(len(pc)), 'gold': int(len(ga)), 'wrong_value': int(len(wa)),
                                      'P(gold solo > wrong-value solo)': auc},
            })
    random.Random(SEED).shuffle(cases)
    for k, c in enumerate(cases):
        c['reading_index'] = k
    payload = {'about': ('36 conjunctive-association reading cases: 12 high-FVE gold bullets, 12 high-FVE wrong-value '
                         '(contrast, or another value on the contrast axis) bullets, 12 low-FVE gold bullets, shuffled. '
                         'Gold cases: both labellers (LLM nt-ca-bullet-v1, lexicon lex2) say gold; wrong-value cases: both '
                         'say a wrong value on the contrast axis, preferring bullets the LLM calls "contrast" and then '
                         'LLM "other value" bullets outside q04/q07/q08 (generic contrast-axis words), all in the top quarter of '
                         'solo FVE within setting x layer; in both, the '
                         'label-defining words fall inside the '
                         '32-token window the AR scores. High / low = solo-FVE percentile within setting x layer; at most '
                         'one case per item and two per related-item group per stratum, at most 5 per setting. '
                         'case_key = item.L<layer>.p<pos>. Label definitions: analysis.py module docstring; all statistics: results.json.'),
               'strata_counts': {k: len(v) for k, v in picks.items()},
               'candidates': {'strict_gold': int(len(strict_gold)), 'wrong_value': int(len(wrong))}, 'cases': cases}
    C.atomic_json(OUT / 'read_sample.json', payload)
    log('wrote', OUT / 'read_sample.json', payload['strata_counts'], payload['candidates'])


def cmd_disagree(args):
    T = load_tables()
    df = add_derived(T['sel'])
    bank = C.load_bank(FAM)
    LEX = build_lexicons(bank)
    d = df.drop_duplicates(['cell_id', 'text'])
    sub = d[(d.llm5 == args.llm) & (d.lex2 == args.lex)]
    idx = list(sub.index)
    random.Random(args.seed).shuffle(idx)
    print(len(sub))
    for i in idx[:args.n]:
        r = sub.loc[i]
        it = bank[r.item_id]
        print(f"[{r.key} {SL[r.setting]} #{r.idx}] G={it['axis_concepts'].get(it['contrast_axis'])} | C={it['contrast_label']}")
        print('   quote=', repr(r.llm_quote), 'words=', LEX[r.item_id].words(r.text))
        print('   TEXT:', r.text[:260].replace('\n', ' / '))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('prep')
    sub.add_parser('run')
    sub.add_parser('sample')
    s = sub.add_parser('show')
    s.add_argument('key')
    s.add_argument('setting', nargs='?')
    s.add_argument('--pool', action='store_true')
    s.add_argument('--n', type=int, default=30)
    s = sub.add_parser('disagree')
    s.add_argument('--llm', default='none')
    s.add_argument('--lex', default='gold')
    s.add_argument('--n', type=int, default=20)
    s.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()
    {'prep': cmd_prep, 'run': cmd_run, 'sample': cmd_sample, 'show': cmd_show, 'disagree': cmd_disagree}[a.cmd](a)
