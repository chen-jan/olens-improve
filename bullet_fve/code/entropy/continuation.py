#!/usr/bin/env python
"""Continuation-ness of Oracle Lens readouts (WorkspaceBench "Hallucination (chat)").

For every readout (5,615 cells x 3 settings + the raw released-lens reference) each
bullet is compared, by lexical overlap, with text regions of the chat around the read
site, and given one class:

  NEXT   resembles the immediate continuation (the next W=40 reply words after the site)
  LATER  resembles reply text further ahead (40-word windows starting >= 40 words after the site)
  BEFORE echoes text already there: the previous 40 reply words (b_near), earlier reply
         text (b_far: 40-word windows inside response words [0, i0-40)) or the prompt
  NONE   no region clears the threshold (meta commentary, planning, invented content)
  NA     unscorable: fewer than 2 English content words (90% are bullets written in
         Chinese, the rest headers/code/digits). Kept in the file, left out of the 4 shares.

Site split: before = response[:char], after = response[char:], with the page's UTF-16
offsets converted to Python indices; i0 = number of words before the site. Word windows
(40 words ~ the next 1-2 sentences) stand in for "the next ~40 tokens".

Tokens: NFKC, curly quotes -> straight, lower-case, regex [a-z0-9]+('[a-z]+)*, light
S-stemmer (plural/possessive only). Content words: not in STOP and longer than 1 char.
idf(w) = ln((N+1)/(df+1)) + 1, df over N = 149 chats (prompt + reply); words no chat uses
get the maximum weight, so invented content lowers every score.

Scores per bullet (all in [0, 1] unless stated):
  U(region)   idf-weighted share of the bullet's distinct content words found in one
              40-word window of the region; regions with several windows (later, b_far,
              prompt) take the max over all windows (stride 1).
  next, later, b_near, b_far, prompt = U per region; before = max(b_near, b_far, prompt)
  head_hits   how many of the bullet's first 3 content words occur in the NEXT window (0-3)
  prefix      longest verbatim word prefix shared by bullet and the text right after the
              site, either side may skip one leading word (0-n words)
  head_lcs    LCS (in words) of the bullet's first 12 words and the first 20 words after
              the site (0-12)
  r_*         ROUGE-L recall = LCS(bullet words, window words) / bullet words (all words,
              stemmed) against the NEXT window, b_near window and each region's best window
              (diagnostic only, not used by the rule)
  next_ctrl   mean U of this bullet against the NEXT windows of the other read sites in the
              same reply whose NEXT window does not overlap this one (|i0' - i0| >= 40):
              the "topic" baseline for next. None if no such site.

Rule (first that applies):
  0. fewer than MIN_CONTENT=2 distinct content words                -> NA
  1. prefix >= PREFIX_K=3 verbatim words                            -> NEXT (src 'prefix')
  2. >= 3 content words and all of the first 3 occur in NEXT window -> NEXT (src 'head')
  3. head_lcs >= 5 (5 of the first 12 bullet words, in order, in
     the first 20 words after the site)                             -> NEXT (src 'head_lcs')
  4. top = max(next, later, before) < T=0.25                        -> NONE (src 'below_T')
  5. next >= T and next >= top - DELTA (DELTA=0.05)                 -> NEXT (src 'next')
  6. before >= later                                                -> BEFORE (src = b_near /
                                                                       b_far / prompt, ties to
                                                                       the nearest)
  7. otherwise                                                      -> LATER (src 'later')
Rules 1-3 catch continuations that start right and then drift into invented text (their
whole-bullet coverage is low); each fires on <= 1% of bullets at a placebo site.

Calibration (written into the summary, 'calibration'):
  * cross-chat null: real bullets vs a random site of a different chat. T=0.25 is ~the 99th
    percentile of the max over all regions of that chat (so NONE = "no better match than an
    unrelated chat gives 1% of the time").
  * topic null: the same bullet vs the NEXT window of another, non-overlapping read site of
    the same reply (prefix rule fires 0.1%, head rule 1.0%, head_lcs rule ~1%, U>=T 16%).
  * placebo site: classify every bullet as if the read site were another read site of the
    same reply (>= 40 words away). The NEXT rate there (~8% for Original vs ~37% real) is
    the noise floor of NEXT; DELTA favours NEXT on near-ties because NEXT is one window
    while later/b_far/prompt take a max over many.
  * a T grid (0.20-0.35) shows how the shares move; per-bullet raw scores are in the jsonl
    so any threshold can be re-applied.

A 'meta' flag (narrow regex: "the user", "the prompt", "the conversation", "the response",
"<someone> is asking", "let me think/check/consider/...", "I should/need to/must
check/answer/clarify/...", "we need to", sentence-initial "wait"/"hmm"/"okay, so") marks
bullets that talk about the conversation or plan. It is a weak, high-precision-ish flag
(persona speech still slips in); it is reported alongside the classes and does not change
them.

Readout outputs (over scorable bullets): class shares, cont_score = max next score,
cont_mean = mean next score, cont_excess = mean(next - next_ctrl), n_na, n_meta.

Usage:
  python -B continuation.py calibrate      # prints calibration only
  python -B continuation.py run            # writes continuation.jsonl, continuation_summary.json,
                                           # validation_sample.json
"""
import collections
import glob
import json
import math
import os
import random
import re
import sys
import time
import unicodedata

import numpy as np

BASE = '${OLENS_SCRATCH}/olens-bullet-fve'
DATA = BASE + '/page/data'
OUT = BASE + '/entropy'
SETTINGS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
REF = 'raw_n1-n1'
ALL = SETTINGS + [REF]
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32',
         'pooled_greedy_swap-n32': 'Combine 32', REF: 'Raw released lens'}
LABELS = ['consistent', 'hallucinated', 'off_topic', 'generic', 'empty']
CLASSES = ['NEXT', 'LATER', 'BEFORE', 'NONE']
LINK = 'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#'

W = 40            # window size in words
MIN_CONTENT = 2   # bullets with fewer distinct content words are NA (unscorable)
HEAD_K = 3        # head rule: first 3 content words
PREFIX_K = 3      # prefix rule: >= 3 verbatim words continuing the reply
HLCS_B, HLCS_A, HLCS_K = 12, 20, 5  # head-LCS rule: >= 5 of the bullet's first 12 words, in order, within the first 20 words after the site
T = 0.25          # match threshold on U (~99th pct of the cross-chat max-over-regions null)
DELTA = 0.05      # NEXT wins near-ties within DELTA of the best region

STOP = set("""
a about above after again against all almost also although always am an and another any anyone anything are
aren't around as at away be because been before being below between both but by can can't cannot could couldn't
d did didn't do does doesn't doing don't done down during each either else etc even ever every few for from
further get gets getting got had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers
herself him himself his how how's however i i'd i'll i'm i've if in into is isn't it it'd it'll it's its itself
just let let's ll m may maybe me might mine more most much must mustn't my myself no nor not now o of off often
oh ok okay on once one only or other others otherwise ought our ours ourselves out over own per please quite rather
re really s same say says shall shan't she she'd she'll she's should shouldn't since so some something such sure t
than that that's the their theirs them themselves then there there's these they they'd they'll they're they've
this those though through thus to too toward towards under until up upon us use used using ve very via want was
wasn't way we we'd we'll we're we've well were weren't what what's whatever when when's where where's whether
which while who who's whom whose why why's will with within without won't would wouldn't yes yet you you'd you'll
you're you've your yours yourself yourselves like lot lots many thing things also really yeah hey hi hello
""".split())

META = re.compile(
    r"\b(?:the user|user's|the assistant|the prompt|the conversation|the response|the reply|"
    r"(?:the user|they|he|she) (?:is|are|was) asking|"
    r"let me (?:think|check|see|re-?read|look at|consider|recall|verify|correct|figure|analy[sz]e|break (?:this|it) down)|"
    r"i (?:should|need to|must) (?:check|figure|make sure|answer|respond|reply|clarify|think|consider|verify|recall|"
    r"determine|be careful|focus|address|explain|provide|note)|we need to|"
    r"my (?:answer|response|reply) (?:is|should|will))\b|(?:^|[.!?]\s+|\n)\s*(?:wait|hmm+|okay,? so)\b",
    re.I)

QUOTES = str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"', '′': "'",
                        'ʼ': "'"})
WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)*")
DASH_BLOCK = re.compile(r"^[ \t]*-[ \t]+", re.MULTILINE)  # olens_improve.selection._DASH_BLOCK


# ----------------------------------------------------------------------------- text utils
def u16_to_py(s, u):
    """JS UTF-16 offset -> Python str index."""
    n = 0
    for i, ch in enumerate(s):
        if n >= u:
            return i
        n += 2 if ord(ch) > 0xFFFF else 1
    return len(s)


def stem(w):
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) > 3 and "'" not in w:
        if w.endswith('ies') and not w.endswith(('eies', 'aies')):
            return w[:-3] + 'y'
        if w.endswith('es') and not w.endswith(('aes', 'ees', 'oes')):
            return w[:-1]
        if w.endswith('s') and not w.endswith(('us', 'ss', 'is')):
            return w[:-1]
    return w


def words(text):
    t = unicodedata.normalize('NFKC', text).translate(QUOTES).lower()
    return [stem(w) for w in WORD.findall(t)]


def is_content(w):
    """Not a stopword and longer than one character (drops lone letters and list-marker digits)."""
    return w not in STOP and len(w) > 1


def content_seq(ws):
    seen, out = set(), []
    for w in ws:
        if is_content(w) and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def lcs_len(pattern, seq):
    """Bit-parallel LCS length (Hyyro 2004). pattern: list (bits), seq: list."""
    m = len(pattern)
    if m == 0 or not seq:
        return 0
    masks = {}
    for i, x in enumerate(pattern):
        masks[x] = masks.get(x, 0) | (1 << i)
    full = (1 << m) - 1
    v = full
    for y in seq:
        u = v & masks.get(y, 0)
        v = ((v + u) | (v - u)) & full
    return m - bin(v).count('1')


def parse_dash_blocks(text):
    """Same dash-block parser as the project (no cap). Preamble text -> its own block."""
    marks = list(DASH_BLOCK.finditer(text))
    out = []
    if not marks:
        return [(0, len(text))] if text.strip() else []
    if text[:marks[0].start()].strip():
        out.append((0, marks[0].start()))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.end(), end))
    return out


# ----------------------------------------------------------------------------- regions
class Region:
    """Content-word presence over all W-word windows (stride 1) of a token list."""

    def __init__(self, toks, kind, offset0):
        self.toks = toks
        self.kind = kind
        self.offset0 = offset0  # word offset of toks[0] relative to the site (prompt: None)
        n = len(toks)
        self.n_starts = 0 if n == 0 else max(1, n - W + 1)
        self.pres = {}
        for p, t in enumerate(toks):
            if not is_content(t):
                continue
            a = self.pres.get(t)
            if a is None:
                a = np.zeros(self.n_starts, bool)
                self.pres[t] = a
            lo = max(0, p - W + 1)
            hi = min(p, self.n_starts - 1)
            a[lo:hi + 1] = True

    def score(self, bset, idf, total):
        if self.n_starts == 0 or total <= 0:
            return None, None
        acc = np.zeros(self.n_starts)
        for w in bset:
            a = self.pres.get(w)
            if a is not None:
                acc += idf(w) * a
        j = int(acc.argmax())
        return float(acc[j] / total), j

    def window(self, j):
        return self.toks[j:j + W]


def build_site(prompt_toks, before_toks, after_toks):
    return {
        'next': Region(after_toks[:W], 'next', 0),
        'later': Region(after_toks[W:], 'later', W),
        'b_near': Region(before_toks[-W:], 'b_near', -min(W, len(before_toks))),
        'b_far': Region(before_toks[:-W] if len(before_toks) > W else [], 'b_far', -len(before_toks)),
        'prompt': Region(prompt_toks, 'prompt', None),
    }


# ----------------------------------------------------------------------------- loading
def load():
    index = json.load(open(DATA + '/index.json'))
    items = {}
    for f in sorted(glob.glob(DATA + '/items/*.json')):
        d = json.load(open(f))
        items[d['item']['id']] = d
    return index, items


def make_idf(items):
    df = collections.Counter()
    for d in items.values():
        it = d['item']
        df.update(set(w for w in words(it['prompt'] + '\n' + it['response']) if is_content(w)))
    n = len(items)
    maxw = math.log((n + 1) / 1) + 1

    def idf(w):
        c = df.get(w)
        return maxw if c is None else math.log((n + 1) / (c + 1)) + 1
    return idf, df


def bullets_of(cellset, setting):
    """List of (bullet_text) for one readout. Settings use the page's UTF-16 bullet spans."""
    st = cellset[setting]
    text = st['text']
    if setting == REF:
        return [text[a:b] for a, b in parse_dash_blocks(text)]
    out = []
    for b in st['bullets']:
        out.append(text[u16_to_py(text, b['start']):u16_to_py(text, b['end'])])
    return out


# ----------------------------------------------------------------------------- scoring
def head_prefix(bw, aw):
    """Longest verbatim word prefix shared by the bullet and the text after the site,
    letting either side skip one leading word (the lens often emits one junk token first)."""
    best = 0
    for sb in (0, 1):
        for sa in (0, 1):
            n = 0
            while sb + n < len(bw) and sa + n < len(aw) and bw[sb + n] == aw[sa + n]:
                n += 1
            best = max(best, n)
    return best


def score_bullet(btext, site, idf, ctrl_sites):
    """All scores for one bullet against one read site's regions (no classification)."""
    ws = words(btext)
    cseq = content_seq(ws)
    bset = set(cseq)
    total = sum(idf(w) for w in bset)
    rec = {'nw': len(ws), 'nc': len(cseq), 'meta': bool(META.search(btext))}
    sc, best = {}, {}
    for name, reg in site.items():
        s, j = reg.score(bset, idf, total)
        sc[name] = s
        best[name] = j
    nreg = site['next']
    rec['head_hits'] = sum(1 for w in cseq[:HEAD_K] if w in nreg.pres)
    rec['prefix'] = head_prefix(ws, nreg.toks)
    rec['head_lcs'] = lcs_len(nreg.toks[:HLCS_A], ws[:HLCS_B])
    rouge = {}
    for name, reg in site.items():
        rouge[name] = None if best[name] is None else (round(lcs_len(reg.window(best[name]), ws) / len(ws), 4) if ws else 0.0)
    ctrl = None
    if ctrl_sites:
        vals = [v for v in (r.score(bset, idf, total)[0] for r in ctrl_sites) if v is not None]
        ctrl = float(np.mean(vals)) if vals else None
    before_parts = {k: sc[k] for k in ('b_near', 'b_far', 'prompt') if sc[k] is not None}
    before = max(before_parts.values()) if before_parts else None
    # ties inside BEFORE go to the nearest region
    bsrc = max(before_parts, key=lambda k: (before_parts[k], k == 'b_near', k == 'b_far')) if before_parts else None
    rd = lambda x: None if x is None else round(x, 4)
    rec.update({
        'next': rd(sc['next']), 'later': rd(sc['later']), 'b_near': rd(sc['b_near']), 'b_far': rd(sc['b_far']),
        'prompt': rd(sc['prompt']), 'before': rd(before), 'bsrc': bsrc, 'next_ctrl': rd(ctrl),
        'r_next': rouge['next'], 'r_b_near': rouge['b_near'], 'r_later': rouge['later'],
        'r_b_far': rouge['b_far'], 'r_prompt': rouge['prompt'],
    })
    cls, src = classify(rec)
    off = None
    reg_name = {'NEXT': 'next', 'LATER': 'later', 'BEFORE': bsrc}.get(cls)
    if reg_name and best.get(reg_name) is not None and site[reg_name].offset0 is not None:
        off = site[reg_name].offset0 + best[reg_name]
    rec.update({'cls': cls, 'src': src, 'off': off})
    return rec, best


def classify(rec, t=None, delta=None):
    """The rule (see module docstring). Returns (class, src)."""
    t = T if t is None else t
    delta = DELTA if delta is None else delta
    if rec['nc'] < MIN_CONTENT:
        return 'NA', 'unscorable'
    if rec['prefix'] >= PREFIX_K:
        return 'NEXT', 'prefix'
    if rec['nc'] >= HEAD_K and rec['head_hits'] == HEAD_K:
        return 'NEXT', 'head'
    if rec['head_lcs'] >= HLCS_K:
        return 'NEXT', 'head_lcs'
    v_next = rec['next'] or 0.0
    v_later = rec['later'] or 0.0
    v_before = rec['before'] or 0.0
    top = max(v_next, v_later, v_before)
    if top < t:
        return 'NONE', 'below_T'
    if v_next >= t and v_next >= top - delta:
        return 'NEXT', 'next'
    if v_before >= v_later:
        return 'BEFORE', rec['bsrc']
    return 'LATER', 'later'


def word_spans(text):
    """Display-only character spans of the words() tokens (None if NFKC changes the word count)."""
    sp = [m.span() for m in WORD.finditer(text.translate(QUOTES).lower())]
    return sp if len(sp) == len(words(text)) else None


def prep_item(d):
    it = d['item']
    resp = it['response']
    prompt = it['prompt']
    ptoks = words(prompt)
    sites = {}
    for s in it['sites']:
        ci = u16_to_py(resp, s['char'])
        bt = words(resp[:ci])
        at = words(resp[ci:])
        sites[s['pos']] = {'ci': ci, 'i0': len(bt), 'regions': build_site(ptoks, bt, at), 'site': s,
                           'text': {'before': resp[:ci], 'after': resp[ci:], 'prompt': prompt}}
    # control NEXT windows: other sites whose NEXT window does not overlap
    for pos, s in sites.items():
        s['ctrl'] = [o['regions']['next'] for p2, o in sites.items()
                     if p2 != pos and abs(o['i0'] - s['i0']) >= W and o['regions']['next'].n_starts > 0]
    return sites


def window_raw(site, name, j):
    """Raw chat text of window j of region `name` (falls back to the joined tokens)."""
    if j is None:
        return None
    reg = site['regions'][name]
    src, base = {'next': ('after', 0), 'later': ('after', W), 'prompt': ('prompt', 0), 'b_far': ('before', 0),
                 'b_near': ('before', site['i0'] - len(reg.toks))}[name]
    text = site['text'][src]
    sp = word_spans(text)
    lo, hi = base + j, base + j + min(W, len(reg.toks) - j)
    if sp is None or hi <= lo or hi > len(sp):
        return ' '.join(reg.window(j))
    return text[sp[lo][0]:sp[hi - 1][1]]


# ----------------------------------------------------------------------------- calibration
def pct(x, q=(50, 75, 90, 95, 97.5, 99)):
    return dict(zip(map(str, q), np.round(np.percentile(np.asarray(x, float), q), 4).tolist()))


def calibrate(index, items, idf, prepped, seed=11):
    """Cross-chat null, topic null and placebo-site test (Original bullets for the nulls,
    every setting for the placebo test)."""
    rng = random.Random(seed)
    ids = sorted(items)
    res = {'T': T, 'DELTA': DELTA, 'W': W, 'PREFIX_K': PREFIX_K, 'HEAD_K': HEAD_K, 'HLCS': [HLCS_B, HLCS_A, HLCS_K]}
    # (1) cross-chat and topic nulls on Original bullets
    single, maxall, topic_u, topic_head, topic_prefix, real_u, real_head, real_prefix = ([] for _ in range(8))
    real_hl, topic_hl = [], []
    for c in index['cells']:
        item = ids[c['i']]
        me = prepped[item][c['p']]
        if me['regions']['next'].n_starts == 0:
            continue
        other = rng.choice([x for x in ids if x != item])
        osite = rng.choice([s for s in prepped[other].values() if s['regions']['next'].n_starts > 0])
        same = [s for p, s in prepped[item].items() if p != c['p'] and abs(s['i0'] - me['i0']) >= W
                and s['regions']['next'].n_starts > 0]
        tsite = rng.choice(same) if same else None
        for b in bullets_of(items[item]['cells'][c['k']]['settings'], 'capped_n1-n1'):
            r, _ = score_bullet(b, me['regions'], idf, None)
            if r['nc'] < MIN_CONTENT:
                continue
            x, _ = score_bullet(b, osite['regions'], idf, None)
            single.append(x['next'])
            maxall.append(max(v for v in (x['next'], x['later'], x['before']) if v is not None))
            real_u.append(r['next'])
            real_head.append(r['nc'] >= HEAD_K and r['head_hits'] == HEAD_K)
            real_prefix.append(r['prefix'] >= PREFIX_K)
            real_hl.append(r['head_lcs'] >= HLCS_K)
            if tsite is not None:
                y, _ = score_bullet(b, tsite['regions'], idf, None)
                topic_u.append(y['next'])
                topic_head.append(y['nc'] >= HEAD_K and y['head_hits'] == HEAD_K)
                topic_prefix.append(y['prefix'] >= PREFIX_K)
                topic_hl.append(y['head_lcs'] >= HLCS_K)
    res['nulls'] = {
        'how': 'Original bullets with >= 2 content words. cross_chat: vs a random read site of a different chat '
               '(next window; max over next/later/before). topic: vs the next window of another read site of the '
               'same reply >= 40 words away. real: vs the true next window.',
        'n_bullets': len(real_u),
        'cross_chat_next_U_pct': pct(single), 'cross_chat_max_all_regions_U_pct': pct(maxall),
        'cross_chat_max_all_ge_T': round(float(np.mean(np.array(maxall) >= T)), 4),
        'topic_next_U_pct': pct(topic_u), 'real_next_U_pct': pct(real_u),
        'next_U_ge_T': {'real': round(float(np.mean(np.array(real_u) >= T)), 4),
                        'topic': round(float(np.mean(np.array(topic_u) >= T)), 4),
                        'cross_chat': round(float(np.mean(np.array(single) >= T)), 4)},
        'prefix_rule_fires': {'real': round(float(np.mean(real_prefix)), 4), 'topic': round(float(np.mean(topic_prefix)), 4)},
        'head_rule_fires': {'real': round(float(np.mean(real_head)), 4), 'topic': round(float(np.mean(topic_head)), 4)},
        'head_lcs_rule_fires': {'real': round(float(np.mean(real_hl)), 4), 'topic': round(float(np.mean(topic_hl)), 4)},
    }
    # (2) placebo site, every setting; plus a T grid on Original
    res['placebo'] = {'how': 'Each bullet classified at its real read site and at a placebo read site of the same reply '
                             '(random other site with |i0 diff| >= 40 words). NEXT at the placebo site estimates the '
                             'noise floor of NEXT. Cells without such a site are skipped. Shares over scorable bullets.'}
    grid_real, grid_plac = [], []
    for st in ALL:
        rr, pp = [], []
        for c in index['cells']:
            item = ids[c['i']]
            me = prepped[item][c['p']]
            others = [s for p, s in prepped[item].items() if p != c['p'] and abs(s['i0'] - me['i0']) >= W]
            if not others:
                continue
            ps = rng.choice(others)
            for b in bullets_of(items[item]['cells'][c['k']]['settings'], st):
                r, _ = score_bullet(b, me['regions'], idf, None)
                if r['nc'] < MIN_CONTENT:
                    continue
                q, _ = score_bullet(b, ps['regions'], idf, None)
                rr.append(r)
                pp.append(q)
        n = len(rr)
        cr = collections.Counter(x['cls'] for x in rr)
        cp = collections.Counter(x['cls'] for x in pp)
        res['placebo'][st] = {'n_bullets': n,
                              'real': {k: round(cr[k] / n, 4) for k in CLASSES},
                              'placebo': {k: round(cp[k] / n, 4) for k in CLASSES},
                              'placebo_next_src': {k: round(v / n, 4) for k, v in collections.Counter(
                                  x['src'] for x in pp if x['cls'] == 'NEXT').items()}}
        if st == 'capped_n1-n1':
            grid_real, grid_plac = rr, pp
    grid = {}
    for t in (0.20, 0.25, 0.30, 0.35):
        for d in (0.0, 0.05, 0.10):
            cr = collections.Counter(classify(x, t, d)[0] for x in grid_real)
            cp = collections.Counter(classify(x, t, d)[0] for x in grid_plac)
            n = len(grid_real)
            grid[f'T={t:.2f},DELTA={d:.2f}'] = {'real': {k: round(cr[k] / n, 4) for k in CLASSES},
                                                'placebo': {k: round(cp[k] / n, 4) for k in CLASSES}}
    res['threshold_grid_original'] = grid
    return res


# ----------------------------------------------------------------------------- full run
def readout_record(c, item, setting, cs, site, idf):
    bl = bullets_of(cs, setting)
    recs = []
    for bi, b in enumerate(bl):
        r, _ = score_bullet(b, site['regions'], idf, site['ctrl'])
        r.pop('bsrc', None)
        recs.append({'b': bi, 'text': b.strip(), **r})
    sc = [r for r in recs if r['cls'] != 'NA']
    n = len(sc)
    shares = {k: (round(sum(1 for r in sc if r['cls'] == k) / n, 4) if n else None) for k in CLASSES}
    nexts = [r['next'] for r in sc if r['next'] is not None]
    exc = [r['next'] - r['next_ctrl'] for r in sc if r['next'] is not None and r['next_ctrl'] is not None]
    if setting == REF:
        lab, fve = c.get('r'), None
    else:
        s = c['s'][SETTINGS.index(setting)]
        lab, fve = s['c'], s['f']
    return {
        'k': c['k'], 'setting': setting, 'item': item, 'L': c['L'], 'p': c['p'], 'sk': c['sk'], 'st': c['st'],
        'label': None if lab is None else LABELS[lab], 'fve': fve,
        'n_bullets': len(recs), 'n_scorable': n, 'n_na': len(recs) - n,
        'shares': shares,
        'cont_score': round(max(nexts), 4) if nexts else None,
        'cont_mean': round(float(np.mean(nexts)), 4) if nexts else None,
        'cont_excess': round(float(np.mean(exc)), 4) if exc else None,
        'n_meta': sum(1 for r in recs if r['meta']),
        'i0': site['i0'],
        'n_words_after': len(site['regions']['next'].toks) + len(site['regions']['later'].toks),
        'bullets': recs,
    }


def spearman(x, y):
    from scipy.stats import spearmanr
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 10:
        return None
    r = spearmanr(x[ok], y[ok]).statistic
    return None if not np.isfinite(r) else round(float(r), 4)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(float(np.mean(xs)), 4) if xs else None


def agg(rows):
    """Bullet-level class distribution (scorable bullets) + readout-level means."""
    if not rows:
        return None
    bc, src, meta = collections.Counter(), collections.Counter(), collections.Counter()
    nb = nna = 0
    for r in rows:
        for b in r['bullets']:
            if b['cls'] == 'NA':
                nna += 1
                continue
            bc[b['cls']] += 1
            src[b['src']] += 1
            meta[b['cls']] += int(b['meta'])
            nb += 1
    rs = [r for r in rows if r['n_scorable']]
    return {
        'n_readouts': len(rows), 'n_scorable_bullets': nb, 'na_share_of_all_bullets': round(nna / max(1, nb + nna), 4),
        'bullet_share': {k: round(bc[k] / nb, 4) if nb else None for k in CLASSES},
        'readout_mean_share': {k: _mean([r['shares'][k] for r in rs]) for k in CLASSES},
        'readouts_with_any_NEXT': _mean([float(r['shares']['NEXT'] > 0) for r in rs]),
        'mean_cont_score': _mean([r['cont_score'] for r in rows]),
        'mean_cont_mean': _mean([r['cont_mean'] for r in rows]),
        'mean_cont_excess': _mean([r['cont_excess'] for r in rows]),
        'meta_share_of_bullets': round(sum(meta.values()) / nb, 4) if nb else None,
        'meta_share_by_class': {k: round(meta[k] / bc[k], 4) if bc[k] else None for k in CLASSES},
        'src_share': {k: round(v / nb, 4) for k, v in sorted(src.items())},
        'mean_fve': _mean([r['fve'] for r in rows]),
    }


RUNWAY_BINS = ((0, 5), (5, 15), (15, 40), (40, 100), (100, 100000))
SLIM = ('n_readouts', 'bullet_share', 'mean_cont_score', 'mean_cont_excess', 'mean_fve')


def slim(a):
    return None if a is None else {k: a[k] for k in SLIM}


def fve_relation(rows):
    rows = [r for r in rows if r['fve'] is not None and r['n_scorable']]
    if not rows:
        return None
    f = np.array([r['fve'] for r in rows])
    g = lambda key: [np.nan if r[key] is None else r[key] for r in rows]
    res = {
        'spearman_fve_vs_cont_score': spearman(f, g('cont_score')),
        'spearman_fve_vs_cont_mean': spearman(f, g('cont_mean')),
        'spearman_fve_vs_cont_excess': spearman(f, g('cont_excess')),
        'spearman_fve_vs_share_NEXT': spearman(f, [r['shares']['NEXT'] for r in rows]),
        'spearman_fve_vs_share_LATER': spearman(f, [r['shares']['LATER'] for r in rows]),
        'spearman_fve_vs_share_BEFORE': spearman(f, [r['shares']['BEFORE'] for r in rows]),
        'spearman_fve_vs_share_NONE': spearman(f, [r['shares']['NONE'] for r in rows]),
        'n': len(rows),
    }
    qs = np.quantile(f, [0.2, 0.4, 0.6, 0.8])
    bins = np.digitize(f, qs)
    res['by_fve_quintile'] = {}
    for q in range(5):
        sub = [r for r, b in zip(rows, bins) if b == q]
        a = agg(sub)
        res['by_fve_quintile'][f'Q{q + 1}'] = {
            'fve_range': [round(float(min(r['fve'] for r in sub)), 4), round(float(max(r['fve'] for r in sub)), 4)],
            **slim(a)}
    return res


def summarize(records, calib):
    by = collections.defaultdict(list)
    for r in records:
        by[r['setting']].append(r)
    sks = ['clause', 'sentence', 'markup', 'newline', 'quote']
    Ls = [20, 36, 44, 52, 60]
    summ = {
        'about': 'Continuation-ness of Oracle Lens bullets, Hallucination (chat); rule in continuation.py docstring. '
                 'bullet_share = share of scorable bullets in the group (NA = <2 English content words, excluded); '
                 'readout_mean_share = mean over readouts of the per-readout share. cont_score = max next-window '
                 'score over a readout\'s bullets; cont_excess = mean over bullets of (next - next_ctrl), where '
                 'next_ctrl = same bullet vs the next windows of other non-overlapping read sites of the same reply. '
                 'Raw released lens (raw_n1-n1) has no FVE; its label is the reference judge label.',
        'jsonl_fields': {
            'readout': 'k, setting (capped_n1-n1 | best_n_exact-n32 | pooled_greedy_swap-n32 | raw_n1-n1), item, L, p, '
                       'sk (site kind), st (site token), label (judge), fve (joint FVE; None for raw), n_bullets, '
                       'n_scorable, n_na, shares {NEXT, LATER, BEFORE, NONE} over scorable bullets, cont_score, '
                       'cont_mean, cont_excess, n_meta, i0 (reply words before the site), n_words_after, bullets[]',
            'bullet': 'b (index), text, nw (words), nc (distinct content words), meta, head_hits, prefix, head_lcs, '
                      'next, later, b_near, b_far, prompt, before (U scores; None = region empty), next_ctrl, r_next, '
                      'r_b_near, r_later, r_b_far, r_prompt (ROUGE-L recall vs best window), cls, src (which rule / '
                      'region decided), off (word offset of the matched window start relative to the site; None '
                      'for prompt/NONE/NA)'},
        'constants': {'W_words': W, 'T': T, 'DELTA': DELTA, 'MIN_CONTENT': MIN_CONTENT, 'HEAD_K': HEAD_K,
                      'PREFIX_K': PREFIX_K, 'HEAD_LCS': {'bullet_words': HLCS_B, 'after_words': HLCS_A,
                                                         'min_lcs': HLCS_K}},
        'calibration': calib,
        'settings': {},
    }
    for st in ALL:
        rows = by[st]
        e = {'label': SHORT[st], 'all': agg(rows)}
        e['by_site_kind'] = {sk: agg([r for r in rows if r['sk'] == sk]) for sk in sks}
        e['by_layer'] = {str(L): agg([r for r in rows if r['L'] == L]) for L in Ls}
        e['by_judge_label'] = {lab: slim(agg([r for r in rows if r['label'] == lab])) for lab in LABELS}
        e['by_layer_x_site_kind'] = {f'L{L}|{sk}': slim(agg([r for r in rows if r['L'] == L and r['sk'] == sk]))
                                     for L in Ls for sk in sks}
        e['by_words_after'] = {f'[{lo},{hi})': slim(agg([r for r in rows if lo <= r['n_words_after'] < hi]))
                               for lo, hi in RUNWAY_BINS}
        e['by_words_before'] = {f'[{lo},{hi})': slim(agg([r for r in rows if lo <= r['i0'] < hi]))
                                for lo, hi in RUNWAY_BINS}
        long_rows = [r for r in rows if r['n_words_after'] >= W]
        e['runway40'] = {
            'note': 'only read sites with >= 40 reply words after them (a full NEXT window); ends of replies '
                    'mechanically lower NEXT (see by_words_after)',
            'all': agg(long_rows),
            'by_site_kind': {sk: slim(agg([r for r in long_rows if r['sk'] == sk])) for sk in sks},
            'by_layer': {str(L): slim(agg([r for r in long_rows if r['L'] == L])) for L in Ls},
        }
        if st != REF:
            e['runway40']['fve_relation'] = {k: v for k, v in fve_relation(long_rows).items() if k != 'by_fve_quintile'}
            e['runway40']['fve_relation_by_layer'] = {
                str(L): {k: v for k, v in fve_relation([r for r in long_rows if r['L'] == L]).items()
                         if k.startswith('spearman')} for L in Ls}
            e['fve_relation'] = fve_relation(rows)
            e['fve_relation_by_layer'] = {str(L): {k: v for k, v in fve_relation([r for r in rows if r['L'] == L]).items()
                                                   if k.startswith('spearman')} for L in Ls}
            e['fve_relation_by_site_kind'] = {sk: {k: v for k, v in fve_relation([r for r in rows if r['sk'] == sk]).items()
                                                   if k.startswith('spearman')} for sk in sks}
        summ['settings'][st] = e
    return summ


def context_view(item, rec):
    it = item['item']
    resp = it['response']
    site = [s for s in it['sites'] if s['pos'] == rec['p']][0]
    ci = u16_to_py(resp, site['char'])
    return {
        'prompt_tail': it['prompt'][-400:],
        'before_tail': resp[max(0, ci - 400):ci],
        'after_head': resp[ci:ci + 600],
        'before_truncated': ci > 400,
    }


def validation_sample(records, items, prepped, idf, n=120, seed=7):
    """Per setting (3 + raw reference): one random readout per layer x site-kind combination (25) plus 5 random
    extras = 30, i.e. 120 readouts. Each cell key k appears at most once; raw-reference readouts are drawn only
    from the 407 cells where the raw text differs from Original."""
    rng = random.Random(seed)
    by = collections.defaultdict(list)
    cap_text = {r['k']: [b['text'] for b in r['bullets']] for r in records if r['setting'] == 'capped_n1-n1'}
    same_as_capped = {r['k'] for r in records if r['setting'] == REF and [b['text'] for b in r['bullets']] == cap_text[r['k']]}
    for r in records:
        if r['n_bullets'] and not (r['setting'] == REF and r['k'] in same_as_capped):
            by[(r['setting'], r['L'], r['sk'])].append(r)
    picked, seen = [], set()
    for st in ALL:
        mine = []
        for L in [20, 36, 44, 52, 60]:
            for sk in ['clause', 'sentence', 'markup', 'newline', 'quote']:
                pool = [r for r in by[(st, L, sk)] if r['k'] not in seen]
                if pool:
                    r = rng.choice(pool)
                    mine.append(r)
                    seen.add(r['k'])
        rest = [r for key, rs in by.items() if key[0] == st for r in rs if r['k'] not in seen]
        while len(mine) < n // len(ALL) and rest:
            r = rest.pop(rng.randrange(len(rest)))
            if r['k'] in seen:
                continue
            mine.append(r)
            seen.add(r['k'])
        picked += mine
    out = []
    for r in picked:
        item = items[r['item']]
        site = prepped[r['item']][r['p']]
        regs = site['regions']
        bl = []
        for b in r['bullets']:
            # recompute the best windows to show what each score matched (raw chat text)
            _, best = score_bullet(b['text'], regs, idf, None)
            bl.append({
                'b': b['b'], 'text': b['text'], 'cls': b['cls'], 'src': b['src'], 'meta': b['meta'],
                'scores': {k: b[k] for k in ('next', 'later', 'b_near', 'b_far', 'prompt', 'next_ctrl', 'head_hits',
                                             'prefix', 'head_lcs', 'r_next', 'r_b_near', 'nc', 'off')},
                'matched_window': {nm: window_raw(site, nm, best[nm]) for nm in ('next', 'later', 'b_near', 'b_far', 'prompt')
                                   if best.get(nm) is not None and b.get(nm)},
            })
        out.append({
            'k': r['k'], 'link': LINK + r['k'], 'setting': r['setting'], 'setting_short': SHORT[r['setting']],
            'layer': r['L'], 'site_kind': r['sk'], 'site_token': r['st'], 'judge_label': r['label'], 'fve': r['fve'],
            'shares': r['shares'], 'cont_score': r['cont_score'], 'cont_excess': r['cont_excess'],
            **context_view(item, r),
            'bullets': bl,
            'check': {'agree_with_classes': None, 'notes': ''},
        })
    return out


def run():
    t0 = time.time()
    index, items = load()
    idf, df = make_idf(items)
    ids = sorted(items)
    prepped = {k: prep_item(d) for k, d in items.items()}
    calib = calibrate(index, items, idf, prepped)
    records = []
    for c in index['cells']:
        item = ids[c['i']]
        cs = items[item]['cells'][c['k']]['settings']
        site = prepped[item][c['p']]
        for st in ALL:
            records.append(readout_record(c, item, st, cs, site, idf))
    t1 = time.time()
    with open(OUT + '/continuation.jsonl', 'w') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    summ = summarize(records, calib)
    summ['n_readouts'] = len(records)
    summ['runtime_s'] = round(time.time() - t0, 1)
    json.dump(summ, open(OUT + '/continuation_summary.json', 'w'), indent=1, ensure_ascii=False)
    val = validation_sample(records, items, prepped, idf)
    json.dump({'about': 'Validation sample for continuation.py: 120 readouts, seed 7; per setting (Original, Best of 32, '
                        'Combine 32, raw released lens) one random readout for each layer x site-kind cell (25) + 5 '
                        'random extras. before_tail = last ~400 chars of the reply up to and including the read '
                        'token; after_head = next ~600 chars; prompt_tail = last ~400 chars of the prompt. '
                        'matched_window = the raw chat text of the 40-word window each nonzero score matched best '
                        '(next = the 40 words after the site). Classes: NEXT/LATER/BEFORE/NONE, NA = unscorable '
                        '(<2 English content words). Fill check.agree_with_classes to grade.',
               'constants': summ['constants'], 'n': len(val), 'readouts': val},
              open(OUT + '/validation_sample.json', 'w'), indent=1, ensure_ascii=False)
    print('records', len(records), 'score time', round(t1 - t0, 1), 'total', round(time.time() - t0, 1))
    for st in ALL:
        a = summ['settings'][st]['all']
        print(SHORT[st], a['bullet_share'], 'cont', a['mean_cont_score'], 'exc', a['mean_cont_excess'],
              'meta', a['meta_share_of_bullets'], a['src_share'])


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'run'
    if mode == 'calibrate':
        index, items = load()
        idf, df = make_idf(items)
        prepped = {k: prep_item(d) for k, d in items.items()}
        print(json.dumps(calibrate(index, items, idf, prepped), indent=1))
    else:
        run()
