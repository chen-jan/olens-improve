#!/usr/bin/env python
"""Recurrence / stickiness of the judge's verified wrong spans across the 32-sample lens pool.

Exploratory. Hallucination (chat) family, 149 chats x 1,123 sites x 5 layers = 5,615 cells, three
settings (Original = capped_n1-n1, Best of 32 = best_n_exact-n32, Combine 32 = pooled_greedy_swap-n32).
Inputs (read-only):
  page data     ${OLENS_SCRATCH}/olens-bullet-fve/page/data/{index.json,items/*.json}
  32-sample pools errors/pool_hall.json (written by errors/load_pool.py from the frozen full-grid
                sample files named in configs/expansion_manifest_v1.json stages.*.samples)
  pilot         ${OLENS_DATA_ROOT}/runs/development-shared-pilot-v2/
                judgments-all-candidates/candidate_index_{00..31}-n32/hallucination/cells.jsonl
Outputs: errors/recurrence.jsonl (one row per verified wrong span x setting),
         errors/recurrence_baseline.jsonl (clean bullets / judge claims used as baselines),
         errors/recurrence_pilot.jsonl (units from the fully judged 72-cell development pilot),
         errors/recurrence_summary.json.

ELEMENT RULE (documented in summary.meta.rules)
  Normalisation: NFKC, curly quotes/dashes -> straight, casefold. Tokens: CJK runs (matched as
  character bigrams), numbers (\\d+ with . , : / groups; "1,000" -> "1000"; written two..ninety,
  hundred, thousand, million, billion, dozen map to digits), words (letters, inner apostrophes;
  "x's" also yields "x"). Word matches allow -s / -es / drop-s variants. Multi-token elements match
  as a contiguous token sequence.
  Reference = user prompt + the model's whole reply. "Novel" = not present in the reference.
  Key elements of a unit, in priority order, at most 3:
    1. novel capitalised names (runs of capitalised tokens with of/the/de/van/... connectors; a
       single token counts if it is not sentence-initial, or is not a common word, or is an
       all-caps acronym; "common" = the lowercase form makes up >=20% of >=5 cased uses in the
       pooled lens text; capitalised stopwords cannot start a name; a name of >3 tokens is
       replaced by its 2 rarest capitalised tokens),
    2. novel numbers (list markers such as "3." at a line start are ignored),
    3. novel double-quoted phrases of 1-6 tokens;
    otherwise 4. the 1-3 rarest novel content words (stopwords and <3-letter words dropped;
    CJK bigrams count as content words); rarity = number of chats (of 149) whose pooled lens
    samples contain the token (fewer = rarer), ties -> longer first;
    otherwise 5. the 1-3 rarest content words even though they occur in the reference
    (basis "content_nonnovel": relation/polarity errors made only of reply words).
  A second "reply-blind" rule (what a deployable consensus filter could use) applies the same
  steps without the novelty filter.
  rec_32 = number of the cell's 32 samples (full raw lens text) that contain ALL key elements
  (conjunction); rec_any_32 = max over single elements. Grades: one_off rec_32<=2,
  recurring 3-15, sticky >=16. "majority vote removes" = rec_32 < 16.
SPAN KIND (flags; primary kind = first true in this order)
  novel_name, novel_number, first_person (I/me/my/mine/myself, French je/moi/mon/ma/mes, CJK 我),
  negation/polarity (heuristic: the span's negation status differs from the reply sentence that
  shares the most content tokens with it, >= min(2, n) shared tokens; negators not/no/never/none/
  nothing/nobody/neither/nor/without/cannot/unable/n't/不/没/無/无/非), other.
"""
import argparse
import collections
import glob
import json
import random
import re
import sys
import time
import unicodedata
from array import array

import numpy as np

BASE = '${OLENS_SCRATCH}/olens-bullet-fve'
DATA = f'{BASE}/page/data'
OUTD = f'{BASE}/errors'
POOL = f'{OUTD}/pool_hall.json'
PILOT_DIR = '${OLENS_DATA_ROOT}/runs/development-shared-pilot-v2/judgments-all-candidates'
PAGE = 'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3'
SETTINGS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
RAW = 'raw_n1-n1'
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32',
         RAW: 'Raw reference'}
LAYERS = [20, 36, 44, 52, 60]
N = 32
GRADES = ['one_off', 'recurring', 'sticky']

# --------------------------------------------------------------------------------------------
# text normalisation and tokens
_TR = str.maketrans({'“': '"', '”': '"', '„': '"', '«': '"', '»': '"', '「': '"', '」': '"', '『': '"', '』': '"',
                     '‘': "'", '’': "'", '`': "'", '–': '-', '—': '-', '‐': '-'})
CJK = '぀-ヿ㐀-䶿一-鿿豈-﫿가-힯'
CJK_RUN = re.compile(f'[{CJK}]+')
TOK = re.compile(rf"([{CJK}]+)|(\d+(?:[.,:/]\d+)*)|([^\W\d_]+(?:'[^\W\d_]+)*)")
NAMETOK = re.compile(rf"([{CJK}]+)|(\d+(?:[.,:/]\d+)*)|([^\W\d_]+(?:'[^\W\d_]+)*)|(\n)|([^\w\s])")
MD = re.compile(r'[*_#|\[\]{}<>~]+')
TITLES = re.compile(r'\b(Dr|Mr|Mrs|Ms|Prof|St|Mt|Jr|Sr|Inc|Ltd|Co|Corp|vs|No)\.')
THOUS = re.compile(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?')
WORDNUM = {'zero': '0', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7',
           'eight': '8', 'nine': '9', 'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
           'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17', 'eighteen': '18',
           'nineteen': '19', 'twenty': '20', 'thirty': '30', 'forty': '40', 'fifty': '50', 'sixty': '60',
           'seventy': '70', 'eighty': '80', 'ninety': '90', 'hundred': '100', 'thousand': '1000',
           'million': '1000000', 'billion': '1000000000', 'dozen': '12'}
STOP = set("""a about above after again against all almost also am an and any are aren't as at be because been
before being below between both but by can can't cannot could couldn't did didn't do does doesn't doing don't
down during each either else even ever every few for from further get gets getting got had hadn't has hasn't
have haven't having he he'd he'll he's her here here's hers herself him himself his how how's however i i'd
i'll i'm i've if in into is isn't it it's its itself just let let's like made make many may me might more most
much must mustn't my myself no nor not now of off often on once one only or other others our ours ourselves out
over own per quite rather really same say says shall shan't she she'd she'll she's should shouldn't since so
some such than that that's the their theirs them themselves then there there's these they they'd they'll
they're they've this those though through thus to too toward under until up upon us very via was wasn't we
we'd we'll we're we've well were weren't what what's whatever when when's where where's whether which while
who who's whom whose why why's will with within without won't would wouldn't yes yet you you'd you'll you're
you've your yours yourself yourselves etc ok okay oh hi hey hello please thanks thank sure also still back
just going want need know think way thing things lot lots something anything everything nothing someone
anyone everyone really actually maybe perhaps here's what's""".split())
CJK_STOP = set('的了是我你他她它们在有和与也就都而及这那个一不吗呢吧啊很会能要说对中上下为以之其或等着过把被让给从到')
NAME_STOP = {'i', "i'm", "i've", "i'll", "i'd", 'ok', 'okay'}
TITLE_WORDS = {'dr', 'mr', 'mrs', 'ms', 'miss', 'mx', 'prof', 'professor', 'sir', 'madam', 'mister', 'teacher', 'dear'}
CJK_WORD_STOP = set('而且 目前 关于 可能 因此 一些 这个 一个 我们 你们 他们 因为 所以 但是 如果 可以 没有 并没有 不是 就是 还是 已经 '
                    '非常 一下 什么 怎么 这样 那么 以及 或者 然后 通过 进行 需要 这些 那些 其他 之一 我的 你的 他的 她的 自己 现在 '
                    '时候 这里 那里 一种 一位 一下 并且 而是 只是 还有 一样 不会 不能 不要 应该 一直 正在 但是'.split())
CJK_EDGE = '的了是和与在'
IDENTITY = re.compile(r"qwen|alibaba|阿里|通义|tongyi|openai|chatgpt|anthropic|claude|\bgpt|language model|ai assistant|ai助手|"
                      r"人工智能|大模型|语言模型|\bas an ai\b|\bi'm an ai\b|\bi am an ai\b")
TOKENIZER_GLOB = '${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/*/tokenizer.json'
CONNECT = {'of', 'the', 'de', 'da', 'du', 'del', 'della', 'di', 'van', 'von', 'la', 'le', 'y', 'al', 'bin', 'el', 'der'}
ENDERS = set('.!?:;。！？…\n')
OPENERS = set('"\'(（-•·')
FIRST_PERSON = re.compile(r"\b(i|i'm|i've|i'll|i'd|me|my|mine|myself|je|j'|moi|mon|ma|mes)\b|我")
NEG = re.compile(r"\b(not|no|never|none|nothing|nobody|neither|nor|without|cannot|unable)\b|n't\b|[不没無无非]")


def norm(s):
    # literal escape sequences in code-like lens text ("\\nVoltage") are treated as whitespace
    return unicodedata.normalize('NFKC', s).translate(_TR).replace('\\n', '\n').replace('\\t', ' ')


def canon_num(g):
    return g.replace(',', '') if THOUS.fullmatch(g) else g


def feats(text):
    """(words, nums, cjk_bigrams, token-sequence string) of a text, casefolded."""
    t = CJK_RUN.sub(lambda m: f' {m.group(0)} ', norm(text).casefold())
    words, nums, cjk, seq = set(), set(), set(), []
    for m in TOK.finditer(t):
        g = m.group(0)
        if m.group(1):
            seq.append(g)
            if len(g) == 1:
                cjk.add(g)
            else:
                cjk.update(g[i:i + 2] for i in range(len(g) - 1))
        elif m.group(2):
            c = canon_num(g)
            nums.add(c)
            seq.append(c)
        else:
            words.add(g)
            seq.append(g[:-2] if g.endswith("'s") else g)
            if "'" in g:
                words.add(g.split("'")[0])
            if g in WORDNUM:
                nums.add(WORDNUM[g])
    return words, nums, cjk, ' ' + ' '.join(seq) + ' '


def variants(w):
    v = {w, w + 's', w + 'es'}
    if w.endswith('s') and len(w) > 3:
        v.add(w[:-1])
    if w.endswith('es') and len(w) > 4:
        v.add(w[:-2])
    return v


def phrase_pat(toks):
    s = ' '.join(toks)
    return s if any(CJK_RUN.search(t) for t in toks) else f' {s} '


def match_feats(el, f):
    typ, val = el
    words, nums, cjk, seq = f
    if typ == 'w':
        return any(v in words for v in variants(val))
    if typ == 'n':
        return val in nums
    if typ == 'c':
        return val in cjk
    return phrase_pat(val) in seq


def match_all(els, f):
    return all(match_feats(e, f) for e in els)


# --------------------------------------------------------------------------------------------
class Pool:
    """All 5,615 x 32 lens samples: inverted index token -> sorted sample ids (g = cell*32 + j)."""

    def __init__(self, pools, cells, item_of_cell, n_items):
        self.cells = cells
        self.ci = {k: i for i, k in enumerate(cells)}
        self.item_of_cell = np.asarray(item_of_cell, dtype=np.int32)
        self.n_items = n_items
        self.post = collections.defaultdict(lambda: array('I'))
        self.seq = [None] * (len(cells) * N)
        self.low, self.cap = collections.Counter(), collections.Counter()
        casew = re.compile(r"[^\W\d_]+")
        for ci, k in enumerate(cells):
            for j, txt in enumerate(pools[k]):
                g = ci * N + j
                w, n, c, s = feats(txt)
                self.seq[g] = s
                post = self.post
                for x in w:
                    post['w:' + x].append(g)
                for x in n:
                    post['n:' + x].append(g)
                for x in c:
                    post['c:' + x].append(g)
                for m in casew.finditer(norm(txt)):
                    tok = m.group(0)
                    if tok[0].islower():
                        self.low[tok.lower()] += 1
                    elif tok[0].isupper():
                        self.cap[tok.lower()] += 1
        self.memo, self.dfmemo = {}, {}
        self.empty = np.zeros(0, dtype=np.uint32)

    def arr(self, key):
        a = self.post.get(key)
        return np.frombuffer(a, dtype=np.uint32) if a is not None and len(a) else self.empty

    def el_array(self, el):
        if el in self.memo:
            return self.memo[el]
        typ, val = el
        if typ == 'w':
            parts = [self.arr('w:' + v) for v in variants(val)]
            out = np.unique(np.concatenate(parts)) if parts else self.empty
        elif typ == 'n':
            out = self.arr('n:' + val)
        elif typ == 'c':
            out = self.arr('c:' + val)
        else:  # phrase: candidate samples by component tokens, then contiguous-sequence check
            cand = None
            for t in val:
                if CJK_RUN.fullmatch(t):
                    keys = ['c:' + t] if len(t) == 1 else ['c:' + t[i:i + 2] for i in range(len(t) - 1)]
                    arrs = [self.arr(x) for x in keys]
                elif re.fullmatch(r'\d+(?:[.,:/]\d+)*', t):
                    arrs = [self.arr('n:' + t)]
                else:
                    arrs = [self.arr('w:' + t)]
                for a in arrs:
                    cand = a if cand is None else np.intersect1d(cand, a, assume_unique=True)
            pat = phrase_pat(val)
            out = np.array([g for g in (cand if cand is not None else []) if pat in self.seq[g]], dtype=np.uint32)
        self.memo[el] = out
        return out

    def conj(self, els):
        out = None
        for e in els:
            a = self.el_array(e)
            out = a if out is None else np.intersect1d(out, a, assume_unique=True)
        return out if out is not None else self.empty

    @staticmethod
    def count_in(a, lo, hi):
        return int(np.searchsorted(a, hi) - np.searchsorted(a, lo))

    def item_df(self, key_el):
        if key_el in self.dfmemo:
            return self.dfmemo[key_el]
        a = self.el_array(key_el)
        v = int(np.unique(self.item_of_cell[a // N]).size) if a.size else 0
        self.dfmemo[key_el] = v
        return v

    def is_common(self, w):
        lw = w.lower()
        lo, ca = self.low.get(lw, 0), self.cap.get(lw, 0)
        return lo >= 5 and lo >= 0.2 * (lo + ca)


# --------------------------------------------------------------------------------------------
class Ref:
    """Prompt + reply of one chat: token sets, sequence, reply sentences with negation flags."""

    def __init__(self, prompt, response):
        self.f = feats(prompt + '\n' + response)
        sents = [s for s in re.split(r'(?<=[.!?。！？])\s+|\n+', response) if s.strip()]
        self.sents = [(content_tokens(s), bool(NEG.search(norm(s).casefold()))) for s in sents]

    def has_word(self, w):
        return any(v in self.f[0] for v in variants(w))

    def has(self, el):
        return match_feats(el, self.f)


def content_tokens(text):
    w, _, c, _ = feats(text)
    out = {x.split("'")[0] for x in w if len(x) >= 3 and x not in STOP and x.split("'")[0] not in STOP}
    out |= {b for b in c if not all(ch in CJK_STOP for ch in b)}
    return out


def name_seqs(text):
    """Runs of capitalised tokens: list of [(token, sentence_initial)]."""
    t = TITLES.sub(lambda m: m.group(1), MD.sub(' ', CJK_RUN.sub(lambda m: f' {m.group(0)} ', norm(text))))
    toks, ss = [], True
    for m in NAMETOK.finditer(t):
        g = m.group(0)
        if m.group(4) or (m.group(5) and g in ENDERS):
            ss = True
            toks.append((g, 'p', False))
            continue
        if m.group(5):
            toks.append((g, 'p', False))
            if g not in OPENERS:
                ss = False
            continue
        kind = 'c' if m.group(1) else 'n' if m.group(2) else 'w'
        toks.append((g, kind, ss))
        ss = False
    seqs, i = [], 0

    def capw(x):
        return x[1] == 'w' and x[0][0].isupper() and x[0].lower() not in NAME_STOP

    while i < len(toks):
        if capw(toks[i]) and toks[i][0].lower() not in STOP:
            cur, k = [(toks[i][0], toks[i][2])], i + 1
            while k < len(toks):
                if capw(toks[k]):
                    cur.append((toks[k][0], toks[k][2]))
                    k += 1
                elif (toks[k][1] == 'w' and toks[k][0] in CONNECT and k + 1 < len(toks) and capw(toks[k + 1])):
                    cur.append((toks[k][0], toks[k][2]))
                    k += 1
                else:
                    break
            seqs.append(cur)
            i = k
        else:
            i += 1
    return seqs


def strip_poss(w):
    return w[:-2] if w.endswith("'s") else w


class Extractor:
    def __init__(self, pool):
        self.pool = pool
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(sorted(glob.glob(TOKENIZER_GLOB))[0])
        self.cjk_memo = {}

    def cjk_words(self, run):
        """Word-like units of a CJK run: Qwen BPE pieces, edge particles stripped, runs of single
        characters merged (names such as 李+娜 -> 李娜); units of >= 2 characters only."""
        if run in self.cjk_memo:
            return self.cjk_memo[run]
        spans = []  # character spans of BPE pieces (byte-split characters merged back)
        for a, b in self.tok.encode(run, add_special_tokens=False).offsets:
            if spans and a < spans[-1][1]:
                spans[-1] = (spans[-1][0], max(b, spans[-1][1]))
            else:
                spans.append((a, b))
        out, buf = [], ''
        for a, b in spans:
            x = run[a:b]
            if len(x) == 1 and x not in CJK_STOP and x not in CJK_EDGE:
                buf += x  # single characters (often name characters) are merged
                continue
            if buf:
                out.append(buf)
                buf = ''
            if len(x) >= 2:
                y = x.strip(CJK_EDGE)
                if len(y) >= 2:
                    out.append(y)
        if buf:
            out.append(buf)
        out = [w for w in out if 2 <= len(w) <= 6 and w not in CJK_WORD_STOP and not all(ch in CJK_STOP for ch in w)]
        self.cjk_memo[run] = out
        return out

    def rank(self, els):
        return sorted(els, key=lambda e: (self.pool.item_df(e), -len(e[1] if isinstance(e[1], str) else ' '.join(e[1])), str(e[1])))

    def names(self, text):
        out = []
        for cur in name_seqs(text):
            capw = [g for g, _ in cur if g[0].isupper()]
            while (len(cur) > 1 and cur[0][1] and self.pool.is_common(cur[0][0])
                   and any(not self.pool.is_common(g) for g, _ in cur[1:] if g[0].isupper())):
                cur = cur[1:]
            while cur and cur[-1][0] in CONNECT:
                cur = cur[:-1]
            capw = [g for g, _ in cur if g[0].isupper()]
            if not capw:
                continue
            if len(capw) >= 2:
                ok = any(not self.pool.is_common(g) for g in capw) or not cur[0][1] or len(capw) >= 3
            else:
                g, s0 = cur[0]
                acr = len(g) >= 2 and g.isupper() and g.isalpha()
                ok = (not s0) or (not self.pool.is_common(g)) or acr
            if not ok:
                continue
            toks = [strip_poss(g.casefold()) for g, _ in cur]
            if all(x in TITLE_WORDS or x in CONNECT for x in toks):
                continue
            disp = ' '.join(g for g, _ in cur)
            if len(toks) == 1:
                out.append((('w', toks[0]), disp))
            elif len(toks) <= 3:
                out.append((('p', tuple(toks)), disp))
            else:
                caps = [('w', strip_poss(g.casefold())) for g in capw]
                pref = [e for e, g in zip(caps, capw) if not self.pool.is_common(g)] or caps
                orig = {('w', strip_poss(g.casefold())): g for g in capw}
                for e in self.rank(list(dict.fromkeys(pref)))[:2]:
                    out.append((e, orig.get(e, disp)))
        return out

    def numbers(self, text):
        t = CJK_RUN.sub(lambda m: f' {m.group(0)} ', norm(text).casefold())
        out = []
        for m in TOK.finditer(t):
            if m.group(2):
                a, b = m.span()
                line_head = t[t.rfind('\n', 0, a) + 1:a]
                if t[b:b + 1] in ('.', ')') and re.fullmatch(r'[\s\-•*>#]*', line_head):
                    continue  # list marker
                out.append((('n', canon_num(m.group(0))), m.group(0)))
            elif m.group(3) and m.group(0) in WORDNUM:
                out.append((('n', WORDNUM[m.group(0)]), m.group(0)))
        return out

    def quotes(self, text):
        out = []
        for m in re.finditer(r'"([^"\n]{1,120}?)"', norm(text)):
            toks = feats(m.group(1))[3].split()
            if 1 <= len(toks) <= 6:
                el = ('w', toks[0]) if len(toks) == 1 and not CJK_RUN.fullmatch(toks[0]) and not toks[0][0].isdigit() \
                    else ('p', tuple(toks))
                out.append((el, m.group(0)))
        return out

    def content(self, text):
        t = CJK_RUN.sub(lambda m: f' {m.group(0)} ', norm(text).casefold())
        out = []
        for m in TOK.finditer(t):
            g = m.group(0)
            if m.group(1):
                for w in self.cjk_words(g):
                    out.append((('p', (w,)), w))
                continue
            if not m.group(3):
                continue
            if "'" in g:
                base, suf = g.split("'", 1)
                if suf != 's':
                    continue  # contractions (don't, I'm, we're ...) are function words
                g = base
            if len(g) < 3 or g in STOP or g in WORDNUM:
                continue
            out.append((('w', g), g))
        return list(dict(out).items())

    def extract(self, text, ref, rule='novel'):
        """-> (elements [(el, role, display, novel)], basis, flags)"""
        nov = (lambda e: not ref.has(e)) if ref is not None else (lambda e: True)
        names = [(e, 'name', d, nov(e)) for e, d in self.names(text)]
        nums = [(e, 'number', d, nov(e)) for e, d in self.numbers(text)]
        quotes = [(e, 'quote', d, nov(e)) for e, d in self.quotes(text)]
        flags = {'novel_name': any(x[3] for x in names), 'novel_number': any(x[3] for x in nums),
                 'novel_quote': any(x[3] for x in quotes)}
        keep = (lambda x: x[3]) if rule == 'novel' else (lambda x: True)
        tier1 = []
        for group in (names, nums, quotes):
            seen = {}
            for x in group:
                if keep(x) and x[0] not in seen:
                    seen[x[0]] = x
            tier1 += [seen[e] for e in self.rank(list(seen))]
        dedup = []
        for x in tier1:
            if x[0] not in [y[0] for y in dedup]:
                dedup.append(x)
        if dedup:
            return dedup[:3], dedup[0][1], flags
        cont = [(e, 'content', d, nov(e)) for e, d in self.content(text)]
        nv = [x for x in cont if x[3]] if rule == 'novel' else cont
        if nv:
            r = self.rank([x[0] for x in nv])[:3]
            byel = {x[0]: x for x in nv}
            return [byel[e] for e in r], ('content_novel' if rule == 'novel' else 'content'), flags
        if rule == 'novel' and cont:
            r = self.rank([x[0] for x in cont])[:3]
            byel = {x[0]: x for x in cont}
            return [byel[e] for e in r], 'content_nonnovel', flags
        toks = feats(text)[3].split()
        if 1 <= len(toks) <= 8:
            e = ('p', tuple(toks))
            return [(e, 'span', ' '.join(toks), nov(e))], 'span', flags
        return [], 'none', flags


def el_json(x):
    (typ, val), role, disp, novel = x
    return {'role': role, 'text': disp, 'key': val if isinstance(val, str) else ' '.join(val), 'match': typ,
            'novel': novel}


def polarity_flip(text, ref):
    C = content_tokens(text)
    if not C or not ref.sents:
        return None
    sn = bool(NEG.search(norm(text).casefold()))
    bo, best = 0, None
    for toks, neg in ref.sents:
        o = len(C & toks)
        if o > bo:
            bo, best = o, neg
    if bo < min(2, len(C)):
        return None
    return sn != best


def grade(r):
    return 'one_off' if r <= 2 else 'recurring' if r <= 15 else 'sticky'


def u16(text, s, e):
    b = text.encode('utf-16-le')
    return b[2 * s:2 * e].decode('utf-16-le')


# --------------------------------------------------------------------------------------------
def auroc_hist(hp, hn):
    """P(pos > neg) + 0.5 P(tie) from integer histograms (values 0..32)."""
    npos, nneg = hp.sum(), hn.sum()
    if not npos or not nneg:
        return None
    below = np.concatenate([[0], np.cumsum(hn)[:-1]])
    return float((hp * (below + 0.5 * hn)).sum() / (npos * nneg))


def boot_auroc(pos_by_item, neg_by_item, reps=1000, seed=0):
    items = sorted(set(pos_by_item) | set(neg_by_item))
    HP = np.array([np.bincount(np.asarray(pos_by_item.get(i, []), int), minlength=N + 1) for i in items])
    HN = np.array([np.bincount(np.asarray(neg_by_item.get(i, []), int), minlength=N + 1) for i in items])
    rng = np.random.default_rng(seed)
    est = auroc_hist(HP.sum(0), HN.sum(0)) if len(items) else None
    vals = []
    for _ in range(reps):
        pick = rng.choice(len(items), len(items), replace=True)
        v = auroc_hist(HP[pick].sum(0), HN[pick].sum(0))
        if v is not None:
            vals.append(v)
    return {'est': None if est is None else round(est, 4), 'lo': round(float(np.percentile(vals, 2.5)), 4) if vals else None,
            'hi': round(float(np.percentile(vals, 97.5)), 4) if vals else None,
            'n_pos': sum(len(v) for v in pos_by_item.values()), 'n_neg': sum(len(v) for v in neg_by_item.values())}


def boot_auroc_strat(pos, neg, reps=1000, seed=0):
    """AUROC over same-stratum pairs only (pair-weighted mix of per-stratum AUROCs), chat bootstrap.
    pos / neg: lists of (item, stratum, value)."""
    items = sorted({x[0] for x in pos} | {x[0] for x in neg})
    strata = sorted({x[1] for x in pos} | {x[1] for x in neg}, key=str)
    if not items or not strata:
        return None
    ii = {it: i for i, it in enumerate(items)}
    si = {st: i for i, st in enumerate(strata)}
    HP = np.zeros((len(items), len(strata), N + 1))
    HN = np.zeros((len(items), len(strata), N + 1))
    for it, st, v in pos:
        HP[ii[it], si[st], v] += 1
    for it, st, v in neg:
        HN[ii[it], si[st], v] += 1

    def est(hp, hn):
        num = den = 0.0
        for k in range(len(strata)):
            a = auroc_hist(hp[k], hn[k])
            if a is None:
                continue
            w = hp[k].sum() * hn[k].sum()
            num += a * w
            den += w
        return num / den if den else None
    e = est(HP.sum(0), HN.sum(0))
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(reps):
        pick = rng.choice(len(items), len(items), replace=True)
        v = est(HP[pick].sum(0), HN[pick].sum(0))
        if v is not None:
            vals.append(v)
    hp, hn = HP.sum(0), HN.sum(0)
    per = {str(st): {'auroc': None if auroc_hist(hp[k], hn[k]) is None else round(auroc_hist(hp[k], hn[k]), 4),
                     'n_pos': int(hp[k].sum()), 'n_neg': int(hn[k].sum()),
                     'kept_>=16_pct_pos': pct(hp[k][16:].sum(), hp[k].sum()), 'kept_>=16_pct_neg': pct(hn[k][16:].sum(), hn[k].sum())}
           for st, k in si.items()}
    return {'est': None if e is None else round(e, 4), 'lo': round(float(np.percentile(vals, 2.5)), 4) if vals else None,
            'hi': round(float(np.percentile(vals, 97.5)), 4) if vals else None, 'per_stratum': per}


def boot_frac(flags_by_item, reps=1000, seed=0):
    items = sorted(flags_by_item)
    s = np.array([sum(flags_by_item[i]) for i in items], float)
    n = np.array([len(flags_by_item[i]) for i in items], float)
    if n.sum() == 0:
        return None
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(reps):
        p = rng.choice(len(items), len(items), replace=True)
        if n[p].sum():
            vals.append(s[p].sum() / n[p].sum())
    return {'est': round(float(s.sum() / n.sum()), 4), 'lo': round(float(np.percentile(vals, 2.5)), 4),
            'hi': round(float(np.percentile(vals, 97.5)), 4), 'n': int(n.sum())}


def dist(rows, key='rec_32'):
    vals = [r[key] for r in rows if r.get(key) is not None]
    if not vals:
        return {'n': 0}
    g = collections.Counter(grade(v) for v in vals)
    a = np.asarray(vals)
    return {'n': len(vals), **{f'{x}': g[x] for x in GRADES}, **{f'{x}_pct': round(100 * g[x] / len(vals), 1) for x in GRADES},
            'majority_removes_pct': round(100 * float((a < 16).mean()), 1),
            'median_rec_32': float(np.median(a)), 'mean_rec_32': round(float(a.mean()), 2)}


def group_dist(rows, keyf, key='rec_32'):
    out = collections.defaultdict(list)
    for r in rows:
        out[keyf(r)].append(r)
    return {str(k): dist(v, key) for k, v in sorted(out.items(), key=lambda kv: str(kv[0]))}


# --------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--items', type=int, default=0, help='debug: only the first N chats')
    ap.add_argument('--reps', type=int, default=1000)
    ap.add_argument('--suffix', default='')
    args = ap.parse_args()
    t0 = time.time()

    def log(*a):
        print(f'[{time.time() - t0:6.0f}s]', *a, flush=True)

    P = json.load(open(POOL))
    pools = P['pools']
    items = {}
    for f in sorted(glob.glob(f'{DATA}/items/*.json')):
        d = json.load(open(f))
        items[d['item']['id']] = d
    item_ids = sorted(items)
    if args.items:
        item_ids = item_ids[:args.items]
    item_idx = {it: i for i, it in enumerate(item_ids)}
    cells, item_of_cell = [], []
    for it in item_ids:
        ks = sorted(items[it]['cells'], key=lambda k: (items[it]['cells'][k]['layer'], items[it]['cells'][k]['pos']))
        cells += ks
        item_of_cell += [item_idx[it]] * len(ks)
    log('cells', len(cells))
    pool = Pool(pools, cells, item_of_cell, len(item_ids))
    log('pool index built', len(pool.post), 'token keys')
    ex = Extractor(pool)
    refs = {it: Ref(items[it]['item']['prompt'], items[it]['item']['response']) for it in item_ids}
    item_lo = {}
    for ci, it in enumerate(item_of_cell):
        item_lo.setdefault(it, [ci * N, ci * N])
        item_lo[it][1] = ci * N + N
    sites = {it: sorted(s['pos'] for s in items[it]['item']['sites']) for it in item_ids}
    fmemo = {}

    def F(text):
        if text not in fmemo:
            fmemo[text] = feats(text)
        return fmemo[text]

    def cell(it, L, p):
        return items[it]['cells'].get(f'{it}.L{L}.p{p}')

    def wrong_spans(ro):
        return [sp for sp in ro.get('spans') or [] if sp['type'] == 'wrong' and sp['verified']]

    def rec_basic(els, k, src):
        a = pool.conj([x[0] for x in els])
        ci = pool.ci[k]
        lo = ci * N
        ind = np.zeros((len(els), N), bool)
        for i, x in enumerate(els):
            e = pool.el_array(x[0])
            ind[i, e[np.searchsorted(e, lo):np.searchsorted(e, lo + N)].astype(np.int64) - lo] = True
        allv = ind.all(0)
        r32 = int(allv.sum())
        in_src = int(allv[src]) if src is not None else None
        each = ind.sum(1).tolist()
        k2 = int((ind.sum(0) >= min(2, len(els))).sum())
        return a, r32, in_src, each, k2

    def rec_full(els, it, L, p, sid, a):
        k = f'{it}.L{L}.p{p}'
        out = {}
        # other layers, same site
        lay = {}
        for L2 in LAYERS:
            if L2 == L:
                continue
            k2 = f'{it}.L{L2}.p{p}'
            if k2 not in pool.ci:
                continue
            c2 = pool.ci[k2]
            ro = items[it]['cells'][k2]['settings'][sid]
            lay[str(L2)] = {'pool': pool.count_in(a, c2 * N, c2 * N + N), 'readout': match_all([x[0] for x in els], F(ro['text']))}
        out['rec_layers'] = {'by_layer': lay, 'n_readout_layers': sum(v['readout'] for v in lay.values()),
                             'n_pool_layers_any': sum(v['pool'] > 0 for v in lay.values()),
                             'pool_total': sum(v['pool'] for v in lay.values()), 'pool_denominator': N * len(lay)}
        # other settings + raw, same cell
        c = items[it]['cells'][k]
        own_text = c['settings'][sid]['text']
        st = {}
        for s2 in SETTINGS + [RAW]:
            if s2 == sid:
                continue
            ro = c['settings'][s2]
            st[s2] = {'in_readout': match_all([x[0] for x in els], F(ro['text'])),
                      'in_wrong_span': any(match_all([x[0] for x in els], F(sp['text'])) for sp in wrong_spans(ro)),
                      'same_text': ro['text'] == own_text, 'label': ro.get('label')}
        out['rec_settings'] = st
        # neighbouring sites, same layer
        ps = sites[it]
        i = ps.index(p)
        nb = {}
        for tag, j in (('prev', i - 1), ('next', i + 1)):
            if 0 <= j < len(ps):
                k2 = f'{it}.L{L}.p{ps[j]}'
                c2 = pool.ci[k2]
                ro = items[it]['cells'][k2]['settings'][sid]
                nb[tag] = {'k': k2, 'pool': pool.count_in(a, c2 * N, c2 * N + N),
                           'readout': match_all([x[0] for x in els], F(ro['text']))}
        other = [pool.count_in(a, pool.ci[f'{it}.L{L}.p{q}'] * N, pool.ci[f'{it}.L{L}.p{q}'] * N + N) for q in ps if q != p]
        nb['all_sites'] = {'n_other_sites': len(other), 'n_sites_any': sum(x > 0 for x in other),
                           'mean_frac': round(float(np.mean(other)) / N, 4) if other else None}
        out['rec_neighbours'] = nb
        # base rate in other chats (lens prior)
        lo, hi = item_lo[item_idx[it]]
        outside = np.concatenate([a[a < lo], a[a >= hi]])
        n_other_samples = len(pool.cells) * N - (hi - lo)
        out['base'] = {'other_chats_with': int(np.unique(pool.item_of_cell[outside // N]).size) if outside.size else 0,
                       'other_chats': len(item_ids) - 1,
                       'other_sample_frac': round(outside.size / max(1, n_other_samples), 5)}
        return out

    # ---------------------------------------------------------------- wrong spans
    rows, base_rows = [], []
    seen_dup = {}
    for it in item_ids:
        d = items[it]
        src_name = d['item']['source']
        ref = refs[it]
        for k, c in d['cells'].items():
            L, p = c['layer'], c['pos']
            for sid in SETTINGS:
                ro = c['settings'][sid]
                if ro['label'] not in ('hallucinated', 'consistent'):
                    continue
                bl = ro['bullets']
                if ro['label'] == 'hallucinated':
                    for si, sp in enumerate(wrong_spans(ro)):
                        b0 = sp['bullets'][0] if sp['bullets'] else None
                        src = bl[b0]['sample_index'] if b0 is not None else None
                        els, basis, fl = ex.extract(sp['text'], ref, 'novel')
                        bels, bbasis, _ = ex.extract(sp['text'], None, 'blind')
                        fp = bool(FIRST_PERSON.search(norm(sp['text']).casefold()))
                        pol = polarity_flip(sp['text'], ref)
                        lang = bool(CJK_RUN.search(sp['text'])) and not ref.f[2]
                        ident = bool(IDENTITY.search(norm(sp['text']).casefold())) and not IDENTITY.search(
                            norm(d['item']['prompt'] + ' ' + d['item']['response']).casefold())
                        kinds = {'novel_name': fl['novel_name'], 'novel_number': fl['novel_number'],
                                 'first_person': fp, 'negation_polarity': bool(pol), 'cjk_in_non_cjk_chat': lang,
                                 'lens_identity_not_in_reply': ident}
                        kind = next((x for x in ('novel_name', 'novel_number', 'first_person', 'negation_polarity') if kinds[x]), 'other')
                        r = {'k': k, 'link': f'{PAGE}#{k}', 'item': it, 'source': src_name, 'split': d['item']['split'],
                             'layer': L, 'pos': p, 'site_kind': c['site_kind'], 'setting': sid, 'setting_short': SHORT[sid],
                             'span_index': si, 'bullet': sp['bullets'], 'span': sp['text'], 'why': sp.get('why'),
                             'in_unscored': sp.get('in_unscored'), 'kind': kind, 'kind_flags': kinds,
                             'polarity_heuristic': pol, 'src_sample': src,
                             'elements': [el_json(x) for x in els], 'element_basis': basis}
                        if els:
                            a, r32, in_src, each, k2 = rec_basic(els, k, src)
                            r.update({'rec_32': r32, 'rec_31_other': r32 - (in_src or 0), 'in_source': bool(in_src),
                                      'rec_each_32': each, 'rec_any_32': max(each), 'rec_2of_32': k2, 'grade': grade(r32),
                                      'majority_removes': r32 < 16})
                            r.update(rec_full(els, it, L, p, sid, a))
                        else:
                            r.update({'rec_32': None, 'grade': None})
                        if bels:
                            _, br32, bin_src, beach, _ = rec_basic(bels, k, src)
                            r['blind'] = {'elements': [el_json(x) for x in bels], 'basis': bbasis, 'rec_32': br32,
                                          'rec_any_32': max(beach), 'in_source': bool(bin_src)}
                        dk = (k, normalize_key(sp['text']))
                        r['dup_first'] = dk not in seen_dup
                        seen_dup.setdefault(dk, len(rows))
                        r['dup_group'] = seen_dup[dk]
                        rows.append(r)
                # ------------------------------------------------ baselines in the same readouts
                new = []
                for bi, b in enumerate(bl):
                    if b.get('label') != 'c':
                        continue
                    txt = u16(ro['text'], b['start'], b['end'])
                    new.append(make_base('clean_bullet', ro['label'], txt, b['sample_index'], bi, None))
                for cl in ro.get('claims') or []:
                    if cl.get('counted_as') in ('true', 'unverifiable') and cl.get('bullets'):
                        b0 = cl['bullets'][0]
                        new.append(make_base('claim_' + cl['counted_as'], ro['label'], cl['quote'],
                                             bl[b0]['sample_index'], b0, bl[b0].get('label')))
                base_rows += new
                for x in new:
                        x.update({'k': k, 'item': it, 'source': src_name, 'layer': L, 'setting': sid})
                        els, basis, _ = ex.extract(x['text'], ref, 'novel')
                        bels, bbasis, _ = ex.extract(x['text'], None, 'blind')
                        x['elements'] = [el_json(e) for e in els]
                        x['element_basis'] = basis
                        if els:
                            _, r32, in_src, each, k2 = rec_basic(els, k, x['src_sample'])
                            x.update({'rec_32': r32, 'rec_any_32': max(each), 'rec_2of_32': k2, 'in_source': bool(in_src), 'grade': grade(r32)})
                        else:
                            x.update({'rec_32': None})
                        if bels:
                            _, br32, bin_src, beach, _ = rec_basic(bels, k, x['src_sample'])
                            x['blind'] = {'elements': [el_json(e) for e in bels], 'basis': bbasis, 'rec_32': br32,
                                          'rec_any_32': max(beach), 'in_source': bool(bin_src)}
        log('item', it, 'rows', len(rows), 'base', len(base_rows))

    # ---------------------------------------------------------------- pilot (all 32 samples judged)
    pilot = run_pilot(P, pool, ex, refs, items, item_ids, log, rec_basic)

    # ---------------------------------------------------------------- write rows
    sfx = args.suffix
    with open(f'{OUTD}/recurrence{sfx}.jsonl', 'w') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(f'{OUTD}/recurrence_baseline{sfx}.jsonl', 'w') as fh:
        for r in base_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(f'{OUTD}/recurrence_pilot{sfx}.jsonl', 'w') as fh:
        for r in pilot['units']:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    log('rows written')
    summary = summarize(rows, base_rows, pilot, P, args, log)
    json.dump(summary, open(f'{OUTD}/recurrence_summary{sfx}.json', 'w'), indent=1, ensure_ascii=False)
    log('summary written')


def normalize_key(s):
    return re.sub(r'\s+', ' ', norm(s).casefold()).strip()


def make_base(unit, label, text, src, bullet, bullet_label):
    return {'unit': unit, 'readout_label': label, 'text': text, 'src_sample': src, 'bullet': bullet,
            'bullet_label': bullet_label}


# --------------------------------------------------------------------------------------------
def run_pilot(P, pool, ex, refs, items, item_ids, log, rec_basic):
    """72 development cells (L20/44/60) where every one of the 32 capped samples was judged by the same judge."""
    sys.path.insert(0, f'{BASE}/code')
    from hall_judge_context import verify_quote, normalize_ws
    out = {'units': [], 'checks': {}}
    texts, judged = {}, {}
    FM = {}

    def fm(t):
        if t not in FM:
            FM[t] = feats(t)
        return FM[t]
    for j in range(N):
        dd = f'{PILOT_DIR}/candidate_index_{j:02d}-n32/hallucination/cells.jsonl'
        for line in open(dd):
            r = json.loads(line)
            key = r['key']
            stage = 'V' if key.endswith(':V') else 'S'
            key = key[:-2] if stage == 'V' else key
            it, l3, pp = key.split('__')
            k = f'{it}.L{int(l3[1:])}.p{int(pp[1:])}'
            judged.setdefault(k, {}).setdefault(j, {})[stage] = r['result']['samples'][0]
            texts.setdefault(k, {})[j] = r['meta']['samples'][0]
    ks = sorted(texts)
    out['checks']['cells'] = len(ks)
    out['checks']['cells_in_this_run'] = sum(k in pool.ci for k in ks)
    # judged text = capped bullets of pool sample j
    okc = tot = 0
    for k in ks:
        if k not in pool.ci:
            continue
        for j, t in texts[k].items():
            bl = [x.strip() for x in re.split(r'(?:^|\n)- ', t) if x.strip()]
            tot += 1
            okc += all(b in P['pools'][k][j] for b in bl)
    out['checks']['judged_texts_all_bullets_in_pool_sample_j'] = f'{okc}/{tot}'
    # sample-0 verdict vs the main Original (capped_n1-n1) verdict
    same0 = same0_text = 0
    for k in ks:
        if k not in pool.ci:
            continue
        it = k.split('.L')[0]
        ro = items[it]['cells'][k]['settings']['capped_n1-n1']
        same0_text += texts[k][0] == ro['text']
        ws = sorted(sp['text'] for sp in judged[k][0]['S'].get('spans', []) if sp['type'] == 'wrong' and verify_quote(sp['text'], [texts[k][0]]))
        ws_main = sorted(sp['text'] for sp in ro['spans'] if sp['type'] == 'wrong' and sp['verified'])
        same0 += ws == ws_main
    out['checks']['sample0_text_equals_Original'] = same0_text
    out['checks']['sample0_verified_wrong_spans_equal_Original'] = same0
    for k in ks:
        if k not in pool.ci:
            continue
        it = k.split('.L')[0]
        L = int(k.split('.L')[1].split('.p')[0])
        ref = refs[it]
        per_sample = {}
        for j in range(N):
            t = texts[k][j]
            S, V = judged[k][j].get('S', {}), judged[k][j].get('V', {})
            wr = [sp['text'] for sp in S.get('spans', []) if sp['type'] == 'wrong' and verify_quote(sp['text'], [t])]
            nw = [normalize_ws(w) for w in wr]
            tr, un = [], []
            for cl in V.get('claims', []):
                q = cl.get('quote', '')
                if not verify_quote(q, [t]):
                    continue
                nq = normalize_ws(q)
                if any(nq in w or w in nq for w in nw):
                    continue
                if cl.get('status') == 'true':
                    tr.append(q)
                elif cl.get('status') == 'unverifiable':
                    un.append(q)
            per_sample[j] = {'wrong': wr, 'true': tr, 'unverifiable': un, 'kind': S.get('kind')}
        for j in range(N):
            for unit in ('wrong', 'true', 'unverifiable'):
                for q in per_sample[j][unit]:
                    u = {'k': k, 'item': it, 'layer': L, 'sample': j, 'unit': unit, 'text': q}
                    for rule in ('novel', 'blind'):
                        els, basis, _ = ex.extract(q, ref if rule == 'novel' else None, rule)
                        u[rule] = {'elements': [el_json(e) for e in els], 'basis': basis}
                        if not els:
                            continue
                        _, r32, in_src, each, _ = rec_basic(els, k, j)
                        u[rule].update({'rec_32': r32, 'in_source': bool(in_src)})
                        # judge consistency: other judged samples whose capped text contains the elements
                        cont = wr_again = tr_again = 0
                        for j2 in range(N):
                            if j2 == j:
                                continue
                            if not match_all([e[0] for e in els], fm(texts[k][j2])):
                                continue
                            cont += 1
                            wr_again += any(match_all([e[0] for e in els], fm(w)) for w in per_sample[j2]['wrong'])
                            tr_again += any(match_all([e[0] for e in els], fm(w)) for w in per_sample[j2]['true'])
                        u[rule].update({'other_judged_with_element': cont, 'judged_wrong_there': wr_again,
                                        'judged_true_there': tr_again})
                    out['units'].append(u)
    log('pilot units', len(out['units']))
    return out


# --------------------------------------------------------------------------------------------
def pct(a, b):
    return round(100 * a / b, 1) if b else None


def summarize(rows, base_rows, pilot, P, args, log):
    S = {'meta': {
        'generated': time.strftime('%Y-%m-%d %H:%M'),
        'exploratory': True,
        'page': 'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#<k>',
        'rules': __doc__,
        'grades': {'one_off': 'rec_32 <= 2', 'recurring': '3 <= rec_32 <= 15', 'sticky': 'rec_32 >= 16'},
        'majority_vote': 'removes the error if its key elements occur (all together) in fewer than 16 of the 32 samples',
        'pool_checks': P['meta']['checks'],
        'notes': [
            'rec_32 counts the source sample of the bullet (the readout text is a substring of it), so rec_32 >= 1 by construction; rec_31_other excludes it.',
            'The 32 samples are the full raw lens outputs (up to 256 tokens), not just the first four bullets.',
            'Rows are per verified wrong span per setting. Identical texts in the same cell across settings are the same error and carry cached judge verdicts; *_unique tables keep the first occurrence only.',
            'Element matching is lexical. A recurring element is not proof the same false claim recurs (e.g. a name can recur in a different relation), and paraphrases are missed.',
            'Every chat, including test, was inspected before this analysis; nothing here is held out.',
        ]}}
    W = [r for r in rows if r.get('rec_32') is not None]
    WU = [r for r in W if r['dup_first']]
    novel_bases = {'name', 'number', 'quote', 'content_novel'}
    WN = [r for r in W if r['element_basis'] in novel_bases]
    S['counts'] = {
        'verified_wrong_span_rows': len(rows),
        'rows_with_elements': len(W),
        'rows_no_element': len(rows) - len(W),
        'unique_cell_span': len(WU),
        'element_basis': dict(collections.Counter(r['element_basis'] for r in rows)),
        'element_basis_unique': dict(collections.Counter(r['element_basis'] for r in rows if r['dup_first'])),
        'kind': dict(collections.Counter(r['kind'] for r in rows)),
        'kind_unique': dict(collections.Counter(r['kind'] for r in rows if r['dup_first'])),
        'in_source_false': sum(1 for r in W if not r['in_source']),
        'by_setting': dict(collections.Counter(r['setting_short'] for r in rows)),
    }
    D = {}
    D['overall_all'] = dist(W)
    D['overall_unique'] = dist(WU)
    D['overall_novel_element'] = dist(WN)
    D['overall_novel_element_unique'] = dist([r for r in WN if r['dup_first']])
    D['by_setting'] = group_dist(W, lambda r: r['setting_short'])
    D['by_setting_novel'] = group_dist(WN, lambda r: r['setting_short'])
    D['by_kind'] = group_dist(W, lambda r: r['kind'])
    D['by_kind_unique'] = group_dist(WU, lambda r: r['kind'])
    D['by_element_basis'] = group_dist(W, lambda r: r['element_basis'])
    D['by_layer'] = group_dist(W, lambda r: r['layer'])
    D['by_layer_novel'] = group_dist(WN, lambda r: r['layer'])
    D['by_source'] = group_dist(W, lambda r: r['source'])
    D['by_source_novel'] = group_dist(WN, lambda r: r['source'])
    D['by_split'] = group_dist(W, lambda r: r['split'])
    D['by_setting_x_kind'] = group_dist(W, lambda r: f"{r['setting_short']} | {r['kind']}")
    D['by_n_elements'] = group_dist(W, lambda r: len(r['elements']))
    D['by_in_unscored'] = group_dist(W, lambda r: r['in_unscored'])
    D['by_site_kind'] = group_dist(W, lambda r: r['site_kind'])
    D['any_element_instead_of_all'] = dist(W, 'rec_any_32')
    D['two_of_elements_instead_of_all'] = dist(W, 'rec_2of_32')
    D['by_n_elements_any'] = group_dist(W, lambda r: len(r['elements']), 'rec_any_32')
    D['by_basis_x_n_elements'] = group_dist(W, lambda r: f"{r['element_basis']} | {len(r['elements'])}")
    D['blind_rule_all'] = dist([{'rec_32': r['blind']['rec_32']} for r in rows if r.get('blind')])
    D['blind_rule_by_basis'] = group_dist([{'rec_32': r['blind']['rec_32'], 'b': r['blind']['basis']} for r in rows if r.get('blind')], lambda r: r['b'])
    D['any_element_novel'] = dist(WN, 'rec_any_32')
    D['two_of_elements_novel'] = dist(WN, 'rec_2of_32')
    D['by_flag_lens_identity'] = group_dist(W, lambda r: r['kind_flags']['lens_identity_not_in_reply'])
    D['by_flag_cjk'] = group_dist(W, lambda r: r['kind_flags']['cjk_in_non_cjk_chat'])
    D['by_flag_first_person'] = group_dist(W, lambda r: r['kind_flags']['first_person'])
    D['by_flag_negation'] = group_dist(W, lambda r: r['kind_flags']['negation_polarity'])
    S['distributions'] = D
    # bootstrap CI for the majority-vote removal share
    byi = collections.defaultdict(list)
    for r in W:
        byi[r['item']].append(r['rec_32'] < 16)
    S['majority_removes_ci'] = {'all_rows': boot_frac(byi, args.reps)}
    byi = collections.defaultdict(list)
    for r in WN:
        byi[r['item']].append(r['rec_32'] < 16)
    S['majority_removes_ci']['novel_element_rows'] = boot_frac(byi, args.reps)
    byi = collections.defaultdict(list)
    for r in W:
        byi[r['item']].append(r['rec_32'] <= 2)
    S['one_off_ci'] = boot_frac(byi, args.reps)
    # how far the error spreads
    def share(rs, f):
        return pct(sum(1 for r in rs if f(r)), len(rs))
    spread = {}
    for name, rs in (('all', W), ('one_off', [r for r in W if r['grade'] == 'one_off']),
                     ('recurring', [r for r in W if r['grade'] == 'recurring']), ('sticky', [r for r in W if r['grade'] == 'sticky'])):
        spread[name] = {
            'n': len(rs),
            'only_in_source_sample_pct': share(rs, lambda r: r['rec_31_other'] == 0),
            'same_setting_readout_at_>=1_other_layer_pct': share(rs, lambda r: r['rec_layers']['n_readout_layers'] >= 1),
            'pool_at_>=1_other_layer_pct': share(rs, lambda r: r['rec_layers']['n_pool_layers_any'] >= 1),
            'mean_pool_frac_other_layers': round(float(np.mean([r['rec_layers']['pool_total'] / max(1, r['rec_layers']['pool_denominator']) for r in rs])), 4) if rs else None,
            'in_other_setting_readout_pct': {SHORT[s]: share([r for r in rs if s in r['rec_settings']], lambda r, s=s: r['rec_settings'][s]['in_readout']) for s in SETTINGS + [RAW]},
            'in_other_setting_readout_different_text_pct': {SHORT[s]: share([r for r in rs if s in r['rec_settings'] and not r['rec_settings'][s]['same_text']], lambda r, s=s: r['rec_settings'][s]['in_readout']) for s in SETTINGS + [RAW]},
            'judged_wrong_again_when_present_in_other_setting_different_text_pct': {SHORT[s]: share([r for r in rs if s in r['rec_settings'] and not r['rec_settings'][s]['same_text'] and r['rec_settings'][s]['in_readout']], lambda r, s=s: r['rec_settings'][s]['in_wrong_span']) for s in SETTINGS + [RAW]},
            'neighbour_pool_any_pct': share([r for r in rs if 'prev' in r['rec_neighbours'] or 'next' in r['rec_neighbours']], lambda r: any(r['rec_neighbours'].get(t, {}).get('pool', 0) > 0 for t in ('prev', 'next'))),
            'neighbour_readout_any_pct': share([r for r in rs if 'prev' in r['rec_neighbours'] or 'next' in r['rec_neighbours']], lambda r: any(r['rec_neighbours'].get(t, {}).get('readout', False) for t in ('prev', 'next'))),
            'mean_frac_other_sites_same_layer_with_element': round(float(np.mean([r['rec_neighbours']['all_sites']['n_sites_any'] / max(1, r['rec_neighbours']['all_sites']['n_other_sites']) for r in rs])), 4) if rs else None,
            'other_chats_with_element_median': float(np.median([r['base']['other_chats_with'] for r in rs])) if rs else None,
            'element_in_>=10pct_other_chats_pct': share(rs, lambda r: r['base']['other_chats_with'] >= 0.1 * r['base']['other_chats']),
            'element_in_0_other_chats_pct': share(rs, lambda r: r['base']['other_chats_with'] == 0),
        }
    S['spread'] = spread
    S['spread_novel_element'] = {g: {
        'n': len(rs), 'only_in_source_sample_pct': share(rs, lambda r: r['rec_31_other'] == 0),
        'element_in_>=10pct_other_chats_pct': share(rs, lambda r: r['base']['other_chats_with'] >= 0.1 * r['base']['other_chats']),
        'element_in_0_other_chats_pct': share(rs, lambda r: r['base']['other_chats_with'] == 0),
        'same_setting_readout_at_>=1_other_layer_pct': share(rs, lambda r: r['rec_layers']['n_readout_layers'] >= 1),
        'neighbour_pool_any_pct': share(rs, lambda r: any(r['rec_neighbours'].get(t, {}).get('pool', 0) > 0 for t in ('prev', 'next'))),
    } for g, rs in (('one_off', [r for r in WN if r['grade'] == 'one_off']), ('recurring', [r for r in WN if r['grade'] == 'recurring']),
                    ('sticky', [r for r in WN if r['grade'] == 'sticky']))}
    # sticky errors: prior-like vs chat-specific
    st = [r for r in W if r['grade'] == 'sticky']
    S['sticky_breakdown'] = {
        'n': len(st),
        'prior_like_pct (element in >=25% of other chats)': share(st, lambda r: r['base']['other_chats_with'] >= 0.25 * r['base']['other_chats']),
        'chat_specific_pct (element in <=2 other chats)': share(st, lambda r: r['base']['other_chats_with'] <= 2),
        'by_basis': dict(collections.Counter(r['element_basis'] for r in st)),
        'by_kind': dict(collections.Counter(r['kind'] for r in st)),
        'by_layer': dict(collections.Counter(r['layer'] for r in st)),
        'top_elements': collections.Counter(' + '.join(e['key'] for e in r['elements']) for r in st).most_common(40),
    }
    S['one_off_top_elements'] = collections.Counter(' + '.join(e['key'] for e in r['elements']) for r in W if r['grade'] == 'one_off').most_common(25)

    # ---------------------------------------------------------------- baselines
    B = [b for b in base_rows]

    def grp(rs):
        return dist([r for r in rs if r.get('rec_32') is not None])

    comp = {}
    sel = {
        'wrong_span': W,
        'clean_bullet|hallucinated': [b for b in B if b['unit'] == 'clean_bullet' and b['readout_label'] == 'hallucinated'],
        'clean_bullet|consistent': [b for b in B if b['unit'] == 'clean_bullet' and b['readout_label'] == 'consistent'],
        'claim_true|hallucinated': [b for b in B if b['unit'] == 'claim_true' and b['readout_label'] == 'hallucinated'],
        'claim_true|consistent': [b for b in B if b['unit'] == 'claim_true' and b['readout_label'] == 'consistent'],
        'claim_unverifiable|hallucinated': [b for b in B if b['unit'] == 'claim_unverifiable' and b['readout_label'] == 'hallucinated'],
    }
    for nm, rs in sel.items():
        comp[nm] = {'n_units': len(rs),
                    'novel_rule_by_basis': {bs: grp([r for r in rs if r.get('element_basis') == bs]) for bs in ('name', 'number', 'quote', 'content_novel', 'content_nonnovel')},
                    'novel_rule_novel_any': grp([r for r in rs if r.get('element_basis') in novel_bases]),
                    'novel_rule_tier1(name/number/quote)': grp([r for r in rs if r.get('element_basis') in ('name', 'number', 'quote')]),
                    'blind_rule_all': dist([{'rec_32': r['blind']['rec_32']} for r in rs if r.get('blind')]),
                    'blind_rule_name_or_number': dist([{'rec_32': r['blind']['rec_32']} for r in rs if r.get('blind') and r['blind']['basis'] in ('name', 'number')]),
                    'blind_rule_content': dist([{'rec_32': r['blind']['rec_32']} for r in rs if r.get('blind') and r['blind']['basis'] == 'content'])}
    S['baseline_comparison'] = comp

    def by_item(rs, f, val):
        out = collections.defaultdict(list)
        for r in rs:
            if f(r):
                out[r['item']].append(val(r))
        return out

    tests = {}
    hb = [b for b in B if b['readout_label'] == 'hallucinated']
    pairs = [
        ('novel tier1: clean bullets vs wrong spans', lambda r: r.get('element_basis') in ('name', 'number', 'quote'), 'clean_bullet', 'rec_32'),
        ('novel content: clean bullets vs wrong spans', lambda r: r.get('element_basis') == 'content_novel', 'clean_bullet', 'rec_32'),
        ('novel any: clean bullets vs wrong spans', lambda r: r.get('element_basis') in novel_bases, 'clean_bullet', 'rec_32'),
        ('novel any: true claims vs wrong spans', lambda r: r.get('element_basis') in novel_bases, 'claim_true', 'rec_32'),
        ('novel any: unverifiable claims vs wrong spans', lambda r: r.get('element_basis') in novel_bases, 'claim_unverifiable', 'rec_32'),
        ('blind all: true claims vs wrong spans', lambda r: r.get('blind') is not None, 'claim_true', 'blind'),
        ('blind name/number: true claims vs wrong spans', lambda r: r.get('blind') is not None and r['blind']['basis'] in ('name', 'number'), 'claim_true', 'blind'),
        ('blind all: unverifiable claims vs wrong spans', lambda r: r.get('blind') is not None, 'claim_unverifiable', 'blind'),
        ('blind all: clean bullets vs wrong spans', lambda r: r.get('blind') is not None, 'clean_bullet', 'blind'),
    ]
    for nm, f, unit, key in pairs:
        val = (lambda r: r['rec_32']) if key == 'rec_32' else (lambda r: r['blind']['rec_32'])
        pos = by_item([b for b in hb if b['unit'] == unit], f, val)
        neg = by_item(W if key == 'rec_32' else rows, lambda r, f=f: f(r) and (r.get('rec_32') is not None or key == 'blind'), val)
        tests[nm] = {'auroc_P(baseline>wrong)': boot_auroc(pos, neg, args.reps)}
        pv = [x for v in pos.values() for x in v]
        nv = [x for v in neg.values() for x in v]
        tests[nm]['kept_by_threshold_pct'] = {f'>={t}': {'baseline': pct(sum(x >= t for x in pv), len(pv)), 'wrong': pct(sum(x >= t for x in nv), len(nv))} for t in (2, 3, 4, 8, 16, 24, 32)}
        # same-stratum comparisons: the all-elements match is stricter for units with more elements
        if key == 'rec_32':
            nel = lambda r: len(r['elements'])
            bas = lambda r: r['element_basis']
        else:
            nel = lambda r: len(r['blind']['elements'])
            bas = lambda r: r['blind']['basis']
        P3 = [(b['item'], nel(b), val(b)) for b in hb if b['unit'] == unit and f(b)]
        N3 = [(r['item'], nel(r), val(r)) for r in (W if key == 'rec_32' else rows) if f(r) and (r.get('rec_32') is not None or key == 'blind')]
        tests[nm]['auroc_stratified_by_n_elements'] = boot_auroc_strat(P3, N3, args.reps)
        P3 = [(b['item'], (bas(b), nel(b)), val(b)) for b in hb if b['unit'] == unit and f(b)]
        N3 = [(r['item'], (bas(r), nel(r)), val(r)) for r in (W if key == 'rec_32' else rows) if f(r) and (r.get('rec_32') is not None or key == 'blind')]
        tests[nm]['auroc_stratified_by_basis_x_n_elements'] = boot_auroc_strat(P3, N3, args.reps)
    # within-readout pair rates (controls for cell/layer-level sample diversity)
    def pair_rate(unit, rule, same_n=False):
        by_ro = collections.defaultdict(lambda: ([], []))

        def nv(x):
            if rule == 'novel':
                return (len(x['elements']), x['rec_32'])
            return (len(x['blind']['elements']), x['blind']['rec_32'])
        for r in rows:
            v = r['rec_32'] if rule == 'novel' else (r['blind']['rec_32'] if r.get('blind') else None)
            if v is None or (rule == 'novel' and r['element_basis'] not in novel_bases):
                continue
            by_ro[(r['k'], r['setting'])][0].append(nv(r))
        for b in hb:
            if b['unit'] != unit:
                continue
            v = b.get('rec_32') if rule == 'novel' else (b['blind']['rec_32'] if b.get('blind') else None)
            if v is None or (rule == 'novel' and b.get('element_basis') not in novel_bases):
                continue
            by_ro[(b['k'], b['setting'])][1].append(nv(b))
        per_item = collections.defaultdict(lambda: [0.0, 0])
        for (k, s), (w, c) in by_ro.items():
            if not w or not c:
                continue
            it = k.split('.L')[0]
            for nx, x in w:
                for ny, y in c:
                    if same_n and nx != ny:
                        continue
                    per_item[it][0] += 1.0 if y > x else 0.5 if y == x else 0.0
                    per_item[it][1] += 1
        its = sorted(per_item)
        s = np.array([per_item[i][0] for i in its])
        n = np.array([per_item[i][1] for i in its])
        if not n.sum():
            return None
        rng = np.random.default_rng(1)
        vals = []
        for _ in range(args.reps):
            p = rng.choice(len(its), len(its), replace=True)
            vals.append(s[p].sum() / n[p].sum())
        return {'est': round(float(s.sum() / n.sum()), 4), 'lo': round(float(np.percentile(vals, 2.5)), 4),
                'hi': round(float(np.percentile(vals, 97.5)), 4), 'pairs': int(n.sum()), 'chats': len(its)}
    tests['within_readout_pair_rate P(baseline rec > wrong rec)'] = {
        'novel: clean bullets vs wrong spans': pair_rate('clean_bullet', 'novel'),
        'novel: true claims vs wrong spans': pair_rate('claim_true', 'novel'),
        'blind: true claims vs wrong spans': pair_rate('claim_true', 'blind'),
        'blind: clean bullets vs wrong spans': pair_rate('clean_bullet', 'blind'),
        'blind: unverifiable claims vs wrong spans': pair_rate('claim_unverifiable', 'blind'),
        'same n_elements, novel: clean bullets vs wrong spans': pair_rate('clean_bullet', 'novel', True),
        'same n_elements, novel: true claims vs wrong spans': pair_rate('claim_true', 'novel', True),
        'same n_elements, blind: true claims vs wrong spans': pair_rate('claim_true', 'blind', True),
        'same n_elements, blind: clean bullets vs wrong spans': pair_rate('clean_bullet', 'blind', True),
        'same n_elements, blind: unverifiable claims vs wrong spans': pair_rate('claim_unverifiable', 'blind', True),
    }
    # by layer, blind rule, true claims vs wrong spans
    tests['blind_by_layer'] = {}
    for L in LAYERS:
        pos = by_item([b for b in hb if b['unit'] == 'claim_true' and b['layer'] == L and b.get('blind')], lambda r: True, lambda r: r['blind']['rec_32'])
        neg = by_item([r for r in rows if r['layer'] == L and r.get('blind')], lambda r: True, lambda r: r['blind']['rec_32'])
        tests['blind_by_layer'][str(L)] = {'auroc': boot_auroc(pos, neg, max(200, args.reps // 5)),
                                           'wrong_kept_>=16_pct': pct(sum(x >= 16 for v in neg.values() for x in v), sum(len(v) for v in neg.values())),
                                           'true_kept_>=16_pct': pct(sum(x >= 16 for v in pos.values() for x in v), sum(len(v) for v in pos.values()))}
    S['true_vs_false_tests'] = tests

    # ---------------------------------------------------------------- pilot
    PU = pilot['units']
    pl = {'checks': pilot['checks'], 'n_units': dict(collections.Counter(u['unit'] for u in PU))}
    for rule in ('novel', 'blind'):
        res = {}
        for unit in ('wrong', 'true', 'unverifiable'):
            us = [u for u in PU if u['unit'] == unit and u[rule].get('rec_32') is not None]
            if rule == 'novel':
                us = [u for u in us if u[rule]['basis'] in novel_bases]
            res[unit] = dist([{'rec_32': u[rule]['rec_32']} for u in us])
            cons = [u for u in us if u[rule]['other_judged_with_element'] > 0]
            res[unit]['judge_consistency'] = {
                'units_with_element_in_other_judged_samples': len(cons),
                'mean_share_judged_wrong_there': round(float(np.mean([u[rule]['judged_wrong_there'] / u[rule]['other_judged_with_element'] for u in cons])), 4) if cons else None,
                'mean_share_judged_true_there': round(float(np.mean([u[rule]['judged_true_there'] / u[rule]['other_judged_with_element'] for u in cons])), 4) if cons else None,
            }
        pos = collections.defaultdict(list)
        neg = collections.defaultdict(list)
        for u in PU:
            if u[rule].get('rec_32') is None or (rule == 'novel' and u[rule]['basis'] not in novel_bases):
                continue
            if u['unit'] == 'true':
                pos[u['item']].append(u[rule]['rec_32'])
            elif u['unit'] == 'wrong':
                neg[u['item']].append(u[rule]['rec_32'])
        res['auroc_P(true>wrong)'] = boot_auroc(pos, neg, args.reps)
        P3 = [(u['item'], len(u[rule]['elements']), u[rule]['rec_32']) for u in PU if u['unit'] == 'true' and u[rule].get('rec_32') is not None and (rule == 'blind' or u[rule]['basis'] in novel_bases)]
        N3 = [(u['item'], len(u[rule]['elements']), u[rule]['rec_32']) for u in PU if u['unit'] == 'wrong' and u[rule].get('rec_32') is not None and (rule == 'blind' or u[rule]['basis'] in novel_bases)]
        res['auroc_P(true>wrong)_stratified_by_n_elements'] = boot_auroc_strat(P3, N3, args.reps)
        U3 = [(u['item'], len(u[rule]['elements']), u[rule]['rec_32']) for u in PU if u['unit'] == 'unverifiable' and u[rule].get('rec_32') is not None and (rule == 'blind' or u[rule]['basis'] in novel_bases)]
        res['auroc_P(unverifiable>wrong)_stratified_by_n_elements'] = boot_auroc_strat(U3, N3, args.reps)
        pv = [x for v in pos.values() for x in v]
        nv = [x for v in neg.values() for x in v]
        res['kept_by_threshold_pct'] = {f'>={t}': {'true': pct(sum(x >= t for x in pv), len(pv)), 'wrong': pct(sum(x >= t for x in nv), len(nv))} for t in (2, 4, 8, 16, 24)}
        pl[rule] = res
    S['pilot_all_samples_judged'] = pl

    # ---------------------------------------------------------------- examples
    rng = random.Random(7)
    ex = {}
    for g in GRADES:
        cand = [r for r in WN if r['grade'] == g and r['dup_first']]
        rng.shuffle(cand)
        pick, used_s, used_k = [], set(), set()
        for strict in (2, 1, 0):
            for r in cand:
                if len(pick) == 3:
                    break
                if r in pick or len(r['span']) > 160 or r['item'] in {x['item'] for x in pick}:
                    continue
                if strict >= 1 and (r['setting'] in used_s or r['kind'] in used_k):
                    continue
                if strict >= 2 and len(r['elements']) != 1:
                    continue
                pick.append(r)
                used_s.add(r['setting'])
                used_k.add(r['kind'])
        ex[g] = [example(r) for r in pick]
    S['examples'] = ex
    S['examples_extra'] = {
        'sticky_prior_like': [example(r) for r in sorted([r for r in WN if r['grade'] == 'sticky' and r['dup_first'] and r['base']['other_chats_with'] >= 0.25 * r['base']['other_chats']], key=lambda r: r['k'])[:3]],
        'sticky_chat_specific': [example(r) for r in sorted([r for r in WN if r['grade'] == 'sticky' and r['dup_first'] and r['base']['other_chats_with'] <= 2], key=lambda r: -r['rec_32'])[:3]],
        'sticky_reply_words_only': [example(r) for r in sorted([r for r in W if r['element_basis'] == 'content_nonnovel' and r['grade'] == 'sticky' and r['dup_first'] and len(r['span']) < 120], key=lambda r: (-r['rec_32'], r['k']))[:3]],
        'one_off_name_only_in_source': [example(r) for r in sorted([r for r in WN if r['element_basis'] == 'name' and len(r['elements']) == 1 and r['rec_32'] == 1 and r['dup_first'] and r['base']['other_chats_with'] == 0], key=lambda r: r['k'])[:3]],
    }
    return S


def example(r):
    return {'k': r['k'], 'link': r['link'], 'setting': r['setting_short'], 'kind': r['kind'], 'span': r['span'],
            'why': r['why'], 'elements': [e['key'] for e in r['elements']], 'element_basis': r['element_basis'],
            'rec_32': r['rec_32'], 'rec_31_other': r['rec_31_other'], 'rec_each_32': r['rec_each_32'],
            'other_layers_pool': {L: v['pool'] for L, v in r['rec_layers']['by_layer'].items()},
            'other_layers_readout': {L: v['readout'] for L, v in r['rec_layers']['by_layer'].items()},
            'other_settings_readout': {SHORT[s]: v['in_readout'] for s, v in r['rec_settings'].items()},
            'neighbours': {t: (v['k'], v['pool']) for t, v in r['rec_neighbours'].items() if t in ('prev', 'next')},
            'other_chats_with_element': r['base']['other_chats_with']}


if __name__ == '__main__':
    sys.exit(main())
