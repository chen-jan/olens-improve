"""A6 filler swap, build step (CPU only; no GPU, no API): select source bullets and write edited variants.

Run from newtasks/ as a short mit_quicktest job:
  code/qt.sh analysis/a6_swap/logs/build.log --cpus 8 --mem 32G -- analysis/a6_swap/build_variants.py build
  ... -- analysis/a6_swap/build_variants.py sample [--n 40]      (seeded reading sample of edited variants)
Outputs (analysis/a6_swap/): variants.jsonl (one row per source x variant, 'original' rows included),
build_meta.json (rules, counts, tag ids, contract), rejects.json (why candidates were dropped).

SOURCE BULLETS = distinct (cell, phrase_id) bullets of the three selected settings (pool top-up only if a family
has < --min-sources). A bullet is a source when, inside the AR's scored window (first 32 AR tokens after
ar_token_ids cleanup), it names exactly ONE value of the item's attribute (UM) / contrast axis X (CA), with no
value word straddling the window end:
  right (main) : that value is the gold value, kind 'exact' (UM: um_lexicon v2 gold_exact hit, not a cue,
                 coarse term or pronoun; CA: a gold credit[X] word, not negated, lex2 window label 'gold').
  wrong (reverse): that value is a wrong value (UM: wrong_value exact hit, or a country for Continent items;
                 CA: a contrast credit[X] word, lex2 window label 'contrast').
VARIANTS (one edit each; see edit_tables.py for every replacement):
  original          the unedited bullet (re-encoded to check the cache and as the same-run baseline)
  swap_distractor   UM right: gold value -> one WSB distractor of the item, same role/case/number
  swap_neighbor     UM right: gold value -> the hand-picked neighbour value (e.g. Paraguayan -> Argentine)
  swap_contrast     CA right: gold X word -> the contrast option's X word (grief -> guilt)
  reverse_to_gold   wrong-value source: wrong value -> gold value, same role
  synonym           same value, near-synonym / alternative surface form (grief -> sorrow; Korean -> South Korean)
  frame             value kept, one other content word changed (UM frame word or CA shared-content word first)
Every edit must (a) lie inside the scored window in the original and the edited token ids (token diff of
ar_token_ids), (b) pass a relabel check on the edited text with the same lexicons (swap: exactly one value word in
the window and it is the target value, no gold left; reverse: exactly one gold word; synonym: no wrong value;
frame: the same single gold word, no new value word). A right-value source is kept only if its main swap
(UM swap_distractor, CA swap_contrast) passes. Originals must reproduce their cached AR token ids and cache key.
Rules added after reading the validation samples (validation_round1/2.jsonl):
  * CA value words = bank credit/competitor words + edit_tables.CA_EXT + Chinese words per value (CA_CJK); a source
    must hold exactly one of them in the window (e.g. "裁员 (layoff)" is two value words and is not used).
  * UM Country/Continent: a country code the lexicon lacks (ZA, RSA, NZ, ROK, UA) in the window rejects the source.
  * FRAME: emotion/state words only when they are the item's own shared-content credit words (FRAME_STATE_WORDS);
    noun/verb words (FRAME_NOUN_VERB) are skipped in verb position (after to / a subject pronoun / a modal / who).
  * UM synonyms of words that are adjective and noun take the nominal form in noun position (a Buddhist ->
    a Buddhist practitioner; Buddhist ceremony -> Buddhistic ceremony).
  * Gender kin / CJK words (and other roles) whose only WSB distractor with a form is the neighbour: the neighbour swap
    is the distractor swap (edit.neighbor_as_distractor) and there is no separate swap_neighbor row.
Reading sample of the final file: `sample --seed 20261019` -> validation_sample.jsonl (40/40 pass).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import random
import re
import sys
import time
from pathlib import Path

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
OUT = NT / 'analysis/a6_swap'
sys.path.insert(0, str(NT / 'code'))
sys.path.insert(0, str(OUT))
import ntcommon as C  # noqa: E402

C.setup_paths()
import um_lexicon as UL  # noqa: E402
import edit_tables as T  # noqa: E402

SEED = 20261016
FAMS = ('um', 'ca')
WIN = 32
_TAGPAT = re.compile(r"</?explanation>|<\|im_start\|>(system|user|assistant)?|<\|im_end\|>|<think>|</think>")
FUNCTION_WORDS = {'who', 'from', 'in', 'living', 'and', 'or', 'with', 'at', 'on', 'for', 'but', 'is', 'was', 'are',
                  'were', 'to', 'by', 'of', 'as', 'that', 'which', 'i', 'he', 'she', 'they', 'we', 'you', 'it', 'this',
                  'his', 'her', 'their', 'my', 'our', 'your', 'the', 'a', 'an', 'myself', 'himself', 'herself'}


class Rej(collections.Counter):
    """Reject counter that keeps up to 10 examples per reason (for rejects.json)."""

    def __init__(self):
        super().__init__()
        self.examples = collections.defaultdict(list)

    def hit(self, reason, **ex):
        self[reason] += 1
        if len(self.examples[reason]) < 10:
            self.examples[reason].append({k: (v[:160] if isinstance(v, str) else v) for k, v in ex.items()})


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def load_ca_analysis():
    """analysis/ca/analysis.py (Lex2, _NEG, build_lexicons, clean_item), imported by path."""
    spec = importlib.util.spec_from_file_location('ca_analysis', NT / 'analysis/ca/analysis.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hpick(key: str, n: int) -> int:
    return int(hashlib.sha256(f'{SEED}:{key}'.encode()).hexdigest(), 16) % n


# ------------------------------------------------------------------------------------------ text helpers
def an_needed(word: str) -> bool:
    w = word.strip().lower()
    if not w or not w[0].isalpha():
        return False
    if re.match(r'(eu|uk|ur|us|uni|use|one|once)', w):
        return False
    if re.match(r'(hour|honest|honou?r)', w):
        return True
    return w[0] in 'aeiou'


def titlecase(s: str) -> str:
    small = {'of', 'the', 'and', 'a', 'an', 'in', 'at', 'to'}
    parts = re.split(r'(\s+|-)', s)
    out, first = [], True
    for p in parts:
        if p.strip() and p != '-':
            out.append(p if (not first and p in small) else (p[0].upper() + p[1:]))
            first = False
        else:
            out.append(p)
    return ''.join(out)


def has_latin(s):
    return any('a' <= ch.lower() <= 'z' for ch in s)


def at_sentence_start(text, s):
    prev = text[:s].rstrip()
    if not prev:
        return True
    ch = prev[-1]
    return ch in '.!?:;\n*#-–—>"“(|[' or ('\u3000' <= ch <= '\u9fff') or ('\uff00' <= ch <= '\uffef')


def transfer_case(src: str, tgt: str, src_natural: str | None = None, at_start: bool = False) -> str:
    """Give `tgt` the case pattern of `src`: ALL CAPS -> upper; a deviation from the source's natural case
    (lower-cased proper noun, capitalised common noun, Title Case) is copied; a source in its natural case gives the
    target in its natural case (first letter capitalised at a sentence start)."""
    if not has_latin(src) or not has_latin(tgt):
        return tgt
    cap1 = lambda x: x[0].upper() + x[1:]  # noqa: E731
    letters = [ch for ch in src if ch.isalpha()]
    if len(letters) > 3 and all(ch.isupper() for ch in letters):  # ALL CAPS (not an acronym like US / UK)
        return tgt.upper()
    if 1 < len(letters) <= 3 and all(ch.isupper() for ch in letters):  # acronym: target in its natural case
        return cap1(tgt) if at_start else tgt
    natural = src_natural is not None and src == src_natural
    if natural:  # a capitalised source at a sentence start capitalises the target; a lower-case one never does
        return cap1(tgt) if (at_start and src[:1].isupper()) else tgt
    words = re.findall(r'[A-Za-z]+', src)
    if len(words) > 1 and all(w[0].isupper() for w in words):
        return titlecase(tgt)
    if src[0].isupper():
        if src_natural and src_natural[:1].isupper() and not at_start:
            return tgt
        return cap1(tgt)
    if src_natural and src_natural[:1].isupper() and src.islower():
        return tgt.lower()
    return tgt


def case_with_article(src, tgt, src_natural, text, s):
    """transfer_case for a target that may start with 'the ': the article is capitalised only at a sentence start."""
    start = at_sentence_start(text, s)
    if not tgt.lower().startswith('the '):
        return transfer_case(src, tgt, src_natural, start)
    body = transfer_case(src, tgt[4:], src_natural, False)
    letters = [ch for ch in src if ch.isalpha()]
    if len(letters) > 3 and all(ch.isupper() for ch in letters):
        return 'THE ' + body
    return ('The ' if start else 'the ') + body


def next_word(text, e):
    m = re.match(r"\s+([A-Za-z][\w'’-]*)", text[e:])
    return m.group(1).lower() if m else None


def prev_word(text, s):
    m = re.search(r"([A-Za-z][\w'’-]*)\s+$", text[:s])
    return m.group(1).lower() if m else None


def apply_edit(text, s, e, repl, *, source_takes_the=False):
    """Replace text[s:e] with repl. A preceding a/an is made to agree with repl; 'the' is deduplicated or dropped
    (UM names). -> (new_text, span_start, span_end, before, after, notes)."""
    notes = []
    before_ctx = text[:s]
    m_the = re.search(r'(?i)\bthe\s+$', before_ctx)
    if repl.lower().startswith('the ') and m_the:
        repl = repl[4:]
        notes.append('the_dedup')
    elif source_takes_the and m_the and not repl.lower().startswith('the '):
        art = before_ctx[m_the.start():m_the.start() + 3]
        s = m_the.start()
        repl = transfer_case(art, repl) if art[0].isupper() else repl
        notes.append('the_dropped')
    m_a = re.search(r'(?<![\w])(a|an|A|An|AN)(\s+)$', text[:s])
    if m_a and has_latin(repl):
        art = m_a.group(1)
        want = 'an' if an_needed(repl) else 'a'
        if art.lower() != want:
            new_art = want.upper() if art.isupper() and len(art) > 1 else (want.capitalize() if art[0].isupper() else want)
            repl = new_art + m_a.group(2) + repl
            s = m_a.start()
            notes.append('article_fixed')
    before = text[s:e]
    return text[:s] + repl + text[e:], s, e, before, repl, notes


def token_diff(a, b):
    p = 0
    n = min(len(a), len(b))
    while p < n and a[p] == b[p]:
        p += 1
    q = 0
    while q < n - p and a[len(a) - 1 - q] == b[len(b) - 1 - q]:
        q += 1
    return p, len(a) - q, len(b) - q


class ARText:
    """ar_token_ids + the raw-text character position where the 32-token scored window ends."""

    def __init__(self):
        from transformers import AutoTokenizer
        from olens_improve.reconstruction import ar_token_ids
        self.tok = AutoTokenizer.from_pretrained(str(C.BASE), local_files_only=True)
        self._ids = ar_token_ids
        self._cache = {}

    def ids(self, text):
        r = self._cache.get(text)
        if r is None:
            r = self._ids(self.tok, text)[1]
            if len(self._cache) < 200000:
                self._cache[text] = r
        return r

    def window_end(self, text):
        """Character index in `text` where the scored window ends, or None when offsets cannot be mapped
        (tags removed by the cleanup, or special ids filtered)."""
        if _TAGPAT.search(text):
            return None
        cleaned = text.strip()
        enc = self.tok(cleaned, add_special_tokens=False, return_offsets_mapping=True)
        if enc['input_ids'] != self.ids(text):
            return None
        off = enc['offset_mapping']
        lead = len(text) - len(text.lstrip())
        if len(off) <= WIN:
            return len(text)
        return lead + off[WIN - 1][1]


def check_window_edit(ar: ARText, orig, new):
    """-> (ok, info): the changed tokens lie inside the scored window in both texts."""
    a, b = ar.ids(orig), ar.ids(new)
    p, ea, eb = token_diff(a, b)
    ok = bool(b) and (ea > p or eb > p) and p < WIN and ea <= WIN and eb <= WIN
    return ok, {'edit_tok_orig': [p, ea], 'edit_tok_new': [p, eb], 'tok_delta': (eb - ea), 'n_tok_new': len(b),
                'ar_ids32': b[:WIN]}


# ------------------------------------------------------------------------------------------ UM
def um_norm(s):
    return UL._norm(s)


def build_um_roles():
    roles = {}
    for cls, vals in T.UM_FORMS.items():
        d = roles.setdefault(cls, {})
        for v, forms in vals.items():
            for role, f in forms.items():
                for x in (f if isinstance(f, tuple) else (f,)):
                    if x:
                        k = um_norm(x[4:] if x.lower().startswith('the ') else x)
                        d.setdefault(k, (v, role))
        for k, vr in T.UM_ALIASES.get(cls, {}).items():
            if vr is None:
                d.pop(um_norm(k), None)
            else:
                d[um_norm(k)] = vr
    return roles


UM_ROLES = build_um_roles()
_MISSING = object()


def um_form(cls, value, role, nominal):
    f = T.UM_FORMS.get(cls, {}).get(value)
    if f is None:
        return None
    x = f.get(role, _MISSING)
    if x is _MISSING and role in T.UM_ROLE_FALLBACK:
        x = f.get(T.UM_ROLE_FALLBACK[role], _MISSING)
        if role in ('person',):
            nominal = True
    if x is _MISSING or x is None:
        return None
    if isinstance(x, tuple):
        return x[1] if nominal else x[0]
    return x


def um_natural(cls, value, role):
    f = T.UM_FORMS.get(cls, {}).get(value, {})
    x = f.get(role) or f.get(T.UM_ROLE_FALLBACK.get(role, ''), None)
    if isinstance(x, tuple):
        x = x[0]
    return x


def um_role_of(cls, surface):
    return UM_ROLES.get(cls, {}).get(um_norm(surface))


def um_canon(cls, v):
    keys = UL.tables()[0][cls]
    return v if v in keys else v.replace(' ', '_')


class UMItem:
    def __init__(self, item, opts):
        ctx = UL.item_context(item, opts)
        self.id = item['name']
        self.cls = ctx['cls']
        self.gold = um_canon(self.cls, ctx['gold'])
        self.distractors = [um_canon(self.cls, d) for d in ctx['distractors']]
        self.prompt = ctx['prompt']
        self.raw = ctx
        self.subfamily = item['subfamily']

    def label(self, text):
        return UL.label_bullet(text, self.raw['cls'], self.raw['gold'], self.raw['distractors'], self.prompt)

    def window_hits(self, text, win_end):
        lab = self.label(text)
        hits = ([('gold', h) for h in lab['gold_hits']] + [('wrong', h) for h in lab['wrong_hits']]
                + [('amb', h) for h in lab['ambiguous']])
        inwin = [(k, h) for k, h in hits if h['span'][1] <= win_end]
        strad = [(k, h) for k, h in hits if h['span'][0] < win_end < h['span'][1]]
        return lab, inwin, strad


def um_classify(it: UMItem, text, win_end):
    """-> (kind 'right'|'wrong', info) or (None, reason)."""
    lab, inwin, strad = it.window_hits(text, win_end)
    if strad:
        return None, 'value_straddles_window'
    if not inwin:
        return None, 'no_value_in_window'
    if len(inwin) > 1:
        return None, 'several_values_in_window'
    kind, h = inwin[0]
    if kind == 'amb':
        return None, 'ambiguous_value'
    if it.cls in ('Country', 'Continent') and UM_CODES.search(text[:win_end]):
        return None, 'country_code_in_window'
    s, e = h['span']
    surf = h['surface']
    if kind == 'gold':
        if h.get('match') != 'exact':
            return None, f'gold_{h.get("match")}'
        vr = um_role_of(it.cls, surf)
        if vr is None:
            return None, 'gold_surface_without_role'
        if vr[0] != it.gold:
            return None, 'role_table_value_mismatch'
        return 'right', {'span': (s, e), 'surface': surf, 'value': it.gold, 'role': vr[1], 'label_full': lab['label'],
                         'in_prompt': h.get('in_prompt', False), 'role_cls': it.cls}
    # wrong value -> reverse source
    if h.get('kind') == 'exact':
        vr = um_role_of(it.cls, surf)
        if vr is None:
            return None, 'wrong_surface_without_role'
        lexv = T.UM_LEXVALUE.get(vr[0], vr[0])
        if lexv != h.get('value'):
            return None, 'role_table_value_mismatch'
        return 'wrong', {'span': (s, e), 'surface': surf, 'value': vr[0], 'role': vr[1], 'label_full': lab['label'],
                         'subtype': h.get('subtype'), 'in_prompt': h.get('in_prompt', False), 'role_cls': it.cls}
    if it.cls == 'Continent' and h.get('kind') == 'coarse':
        vr = um_role_of('Country', surf)
        if vr is None or vr[1] not in ('name', 'adj', 'pl', 'cjk'):
            return None, 'wrong_coarse_without_role'
        return 'wrong', {'span': (s, e), 'surface': surf, 'value': vr[0], 'role': vr[1], 'label_full': lab['label'],
                         'subtype': h.get('subtype'), 'in_prompt': h.get('in_prompt', False), 'role_cls': 'Country'}
    return None, f'wrong_{h.get("kind")}'


def um_value_edit(it: UMItem, text, src, target_value, src_cls=None):
    """Replace the source value word with target_value's form for the same role."""
    s, e = src['span']
    role = src['role']
    nominal = role in ('person',) or next_word(text, e) is None or next_word(text, e) in FUNCTION_WORDS
    if role == 'adjnp':  # "single adult": replace only the adjective
        m = re.match(r'[A-Za-z]+', src['surface'])
        e = s + m.end()
        form = um_form(it.cls, target_value, 'adjnp', False)
        nat = 'single'
        src_word = text[s:e]
    else:
        form = um_form(it.cls, target_value, role, nominal)
        nat = um_natural(src.get('role_cls', it.cls), src['value'], role)
        src_word = text[s:e]
    if not form:
        return None
    if form.lower() == src_word.lower():
        return None
    repl = case_with_article(src_word, form, nat, text, s)
    src_name_the = role == 'name' and (um_natural(src.get('role_cls', it.cls), src['value'], 'name') or '').lower().startswith('the ')
    return apply_edit(text, s, e, repl, source_takes_the=src_name_the)


def um_check_value(ar, it: UMItem, new, expect_kind, expect_value=None, expect_surface=None):
    win = ar.window_end(new)
    if win is None:
        return False, 'edited_window_unmappable'
    lab, inwin, strad = it.window_hits(new, win)
    if strad:
        return False, 'edited_value_straddles'
    if expect_kind == 'wrong':
        if len(inwin) != 1 or inwin[0][0] != 'wrong':
            return False, f'relabel_{[k for k, _ in inwin]}'
        if expect_value and inwin[0][1].get('value') not in (expect_value, None):
            return False, f'relabel_value_{inwin[0][1].get("value")}'
        if expect_value and inwin[0][1].get('value') is None:  # coarse hit: accept only for continent targets
            return False, 'relabel_coarse'
        return True, inwin[0][1]['surface']
    if expect_kind == 'gold':
        if len(inwin) != 1 or inwin[0][0] != 'gold':
            return False, f'relabel_{[k for k, _ in inwin]}'
        if expect_surface and inwin[0][1]['surface'] != expect_surface:
            return False, 'relabel_surface_changed'
        return True, inwin[0][1]['surface']
    if expect_kind == 'synonym':
        if any(k != 'gold' for k, _ in inwin) or len(inwin) > 1:
            return False, f'relabel_{[k for k, _ in inwin]}'
        return True, (inwin[0][1]['surface'] if inwin else None)
    raise ValueError(expect_kind)


def um_variants(ar, it: UMItem, text, src, key, rej):
    """-> list of (variant_type, new_text, edit dict, token info); rejects go to `rej`."""
    out = []

    def add(vtype, res, extra, expect_kind, expect_value=None, expect_surface=None):
        if res is None:
            rej.hit(f'{vtype}:no_form', item=it.id, surface=src['surface'], role=src['role'], **extra)
            return False
        new, s, e, before, after, notes = res
        ok, info = check_window_edit(ar, text, new)
        if not ok:
            rej.hit(f'{vtype}:outside_window', item=it.id, before=before, after=after, tok=info['edit_tok_new'])
            return False
        ok, got = um_check_value(ar, it, new, expect_kind, expect_value, expect_surface)
        if not ok:
            rej.hit(f'{vtype}:{got}', item=it.id, before=before, after=after, edited=new[max(0, s - 40):s + 60])
            return False
        out.append((vtype, new, {'char_span': [s, e], 'before': before, 'after': after, 'notes': notes,
                                 'relabel_surface': got, **extra}, info))
        return True

    if src['kind'] == 'right':
        nb = T.UM_NEIGHBOR.get(it.cls, {}).get(it.gold)
        cands = [d for d in it.distractors if d != nb]
        tried = []
        # one distractor per source: hashed start, first one with a form for this role that passes
        if cands:
            k0 = hpick(key, len(cands))
            order = cands[k0:] + cands[:k0]
            for d in order:
                res = um_value_edit(it, text, src, d)
                tried.append(d)
                if res is None:
                    continue
                if add('swap_distractor', res, {'value_to': d}, 'wrong', T.UM_LEXVALUE.get(d, d)):
                    break
        nb_as_distractor = False
        if not any(v[0] == 'swap_distractor' for v in out) and nb in it.distractors:
            # e.g. Gender kin / CJK words: only the opposite binary (a WSB option and the neighbour) has the form;
            # it becomes the distractor swap, and there is no separate neighbour variant for this source
            res = um_value_edit(it, text, src, nb)
            tried.append(nb)
            nb_as_distractor = res is not None and add('swap_distractor', res, {'value_to': nb, 'neighbor_as_distractor': True},
                                                       'wrong', T.UM_LEXVALUE.get(nb, nb))
        if not any(v[0] == 'swap_distractor' for v in out):
            rej.hit('swap_distractor:none_passed', item=it.id, surface=src['surface'], role=src['role'], tried=tried)
            return out
        if nb_as_distractor:
            rej.hit('swap_neighbor:used_as_distractor', item=it.id, surface=src['surface'])
        elif nb:
            add('swap_neighbor', um_value_edit(it, text, src, nb), {'value_to': nb}, 'wrong', T.UM_LEXVALUE.get(nb, nb))
        else:
            rej.hit('swap_neighbor:no_neighbor', item=it.id, surface=src['surface'])
        # synonym
        s, e = src['span']
        surf = text[s:e]
        syn = T.UM_SYN.get(it.cls, {}).get(um_norm(surf))
        kind = 'table'
        if syn is None and has_latin(surf):
            syn = (T.UM_FORMS.get(it.cls, {}).get(it.gold) or {}).get('cjk')
            kind = 'translation_zh'
        if isinstance(syn, tuple):
            nominal = src['role'] == 'person' or next_word(text, e) is None or next_word(text, e) in FUNCTION_WORDS
            syn = syn[1] if nominal else syn[0]
        if syn:
            if it.gold == 'halal' and text[e:e + 1] == '-':
                rej.hit('synonym:hyphen_compound', item=it.id, surface=surf)
            else:
                repl = case_with_article(surf, syn, um_natural(it.cls, it.gold, src['role']), text, s)
                add('synonym', apply_edit(text, s, e, repl), {'synonym_kind': kind}, 'synonym')
        else:
            rej.hit('synonym:no_entry', item=it.id, surface=surf)
        # frame
        um_frame(ar, it, text, src, add, rej)
    else:  # wrong -> gold
        res = um_value_edit(it, text, src, it.gold)
        add('reverse_to_gold', res, {'value_to': it.gold}, 'gold')
    return out


WORD_RX = re.compile(r"[A-Za-z][A-Za-z'’]*")
UM_CODES = re.compile(T.UM_EXTRA_VALUE_CODES)


def frame_candidates(text, win_end, value_span, frame_spans, blocked_spans):
    """Ordered (s, e, word, kind) candidates: frame words first, then generic words; nearest to the value first."""
    vs, ve = value_span

    def dist(s, e):
        return vs - e if e <= vs else s - ve

    def free(s, e, spans):
        return all(e <= a or s >= b for a, b in spans)

    out = []
    for s, e in frame_spans:
        w = text[s:e]
        if w.lower() in T.FRAME_NOUN_VERB and prev_word(text, s) in T.VERB_PREV:
            continue
        if e <= win_end and free(s, e, [value_span]) and w.lower() in T.FRAME_SUB and re.fullmatch(WORD_RX, w):
            out.append((dist(s, e), 0, s, e, w, 'frame_word'))
    seen = {(c[2], c[3]) for c in out}
    for m in WORD_RX.finditer(text[:win_end]):
        s, e = m.span()
        w = m.group(0)
        if (s, e) in seen or w.lower() not in T.FRAME_SUB or w.lower() in T.FRAME_STATE_WORDS \
                or not free(s, e, blocked_spans + [value_span]):
            continue
        if w.lower() in T.FRAME_NOUN_VERB and prev_word(text, s) in T.VERB_PREV:
            continue
        # the whole token must be a word (not part of a hyphenated value compound like "halal-friendly")
        out.append((dist(s, e), 1, s, e, w, 'content_word'))
    out.sort(key=lambda c: (c[1], c[0], c[2]))
    return [(s, e, w, k) for _, _, s, e, w, k in out]


def um_frame(ar, it: UMItem, text, src, add, rej):
    win_end = ar.window_end(text)
    ms = UL.find_matches(text, it.cls)
    frames = [(s, e) for s, e, surf, kind, _ in ms if kind == 'frame']
    blocked = [(s, e) for s, e, surf, kind, _ in ms]
    tries = 0
    for s, e, w, kind in frame_candidates(text, win_end, src['span'], frames, blocked):
        repl = transfer_case(w, T.FRAME_SUB[w.lower()], None, at_sentence_start(text, s))
        tries += 1
        if add('frame', apply_edit(text, s, e, repl), {'frame_kind': kind, 'frame_word': w}, 'gold',
               expect_surface=src['surface']):
            return
        if tries >= 6:
            break
    rej.hit('frame:no_candidate' if tries == 0 else 'frame:none_passed', item=it.id, window=text[:win_end])


# ------------------------------------------------------------------------------------------ CA
def ca_key(s):
    return re.sub(r'\s+', ' ', s.lower()).strip()


def ca_lookup(table, surf):
    k = ca_key(surf)
    for cand in (k, k.replace('-', ' '), k.replace(' ', '-')):
        if cand in table:
            return cand, table[cand]
    return k, _MISSING


def ca_resolve(entry, text, s, e):
    """-> (replacement or None, s, e) after applying the table's context rules."""
    if isinstance(entry, tuple):
        rule, a, b = entry
        if rule == 'obj':
            return (a if next_word(text, e) in T.OBJ else b), s, e
        if rule == 'det':
            return (a if prev_word(text, s) in T.DET else b), s, e
        if rule == 'by':
            m = re.search(r'(?i)\bby\s+$', text[:s])
            if m:
                return a, m.start(), e
            return b, s, e
        raise ValueError(rule)
    return entry, s, e


def _rx(words):
    words = sorted({w.lower() for w in words if w}, key=len, reverse=True)
    if not words:
        return None
    alts = (r'[\s\-]+'.join(re.escape(p) for p in re.split(r'[\s\-]+', w.strip())) for w in words)
    return re.compile(r'(?<![\w])(?:' + '|'.join(alts) + r')(?![\w])', re.I)


class CAItem:
    def __init__(self, item, partner, lex, A, cluster_x_values=()):
        self.id = item['id']
        self.X = item['contrast_axis']
        self.gv = item['cell'][self.X]
        self.cv = partner['cell'][self.X]
        assert isinstance(self.gv, str) and isinstance(self.cv, str), (self.id, self.gv, self.cv)
        self.L = lex
        self.A = A
        gw = [w for g in item['credit'][self.X] for w in g]
        cw = [w for g in partner['credit'][self.X] for w in g]
        self.gold_ext = _rx(gw + T.CA_EXT.get(self.gv, []))
        self.con_ext = _rx(cw + T.CA_EXT.get(self.cv, []))
        self.other_x = lex.compX  # every non-gold X value (incl. the contrast's)
        others = [v for v in cluster_x_values if v not in (self.gv, self.cv)]
        cj = lambda ws: re.compile('|'.join(sorted(set(ws), key=len, reverse=True))) if ws else None  # noqa: E731
        self.cjk = {'g': cj(T.CA_CJK.get(self.gv, [])), 'c': cj(T.CA_CJK.get(self.cv, [])),
                    'o': cj([w for v in others for w in T.CA_CJK.get(v, [])])}
        allw = [w for gs in item['credit'].values() for g in gs for w in g] + \
               [w for ws in item['competitors'].values() for w in ws]
        self.all_rx = _rx(allw)
        self.clean = A.clean_item(self.id)
        self.cluster = item['cluster']

    def x_matches(self, text):
        """All X-axis word matches (gold credit, contrast credit, other X values), merged by span."""
        spans = {}
        for kind, rx in (('gold', self.L.gold_rx), ('contrast', self.L.con_rx), ('compX', [self.L.compX])):
            for r in rx:
                if r is None:
                    continue
                for m in r.finditer(text):
                    d = spans.setdefault(m.span(), {'surface': m.group(0), 'kinds': set()})
                    d['kinds'].add(kind)
        out = []
        for (s, e), d in sorted(spans.items()):
            neg = bool(self.A._NEG.search(text[max(0, s - 40):s]))
            out.append({'span': (s, e), 'surface': d['surface'], 'kinds': d['kinds'], 'neg': neg})
        # drop matches nested inside a longer match (e.g. "cover" inside "cover-up")
        out = [m for m in out if not any(o is not m and o['span'][0] <= m['span'][0] and m['span'][1] <= o['span'][1]
                                         and (o['span'][1] - o['span'][0]) > (m['span'][1] - m['span'][0]) for o in out)]
        return out

    def value_spans(self, text, win_end):
        """X-axis value words in the scored window (bank credit/competitor words + edit_tables.CA_EXT), nested
        matches merged into the longest: [((s, e), {'g','c','o'})]."""
        w = text[:win_end]
        raw = []
        for kind, rx in (('g', self.gold_ext), ('c', self.con_ext), ('o', self.other_x), ('g', self.cjk['g']),
                         ('c', self.cjk['c']), ('o', self.cjk['o'])):
            if rx is not None:
                raw += [(m.span(), kind) for m in rx.finditer(w)]
        raw.sort(key=lambda x: (x[0][0], -(x[0][1] - x[0][0])))
        merged = []
        for (s, e), k in raw:
            if merged and s < merged[-1][0][1]:  # overlaps the previous (longer or equal) span
                (ps, pe), ks = merged[-1]
                merged[-1] = ((ps, max(pe, e)), ks | {k})
            else:
                merged.append(((s, e), {k}))
        return merged


def ca_extend_cover(text, s, e, surf):
    if surf.lower() in ('cover', 'covering', 'covered', 'covers'):
        m = re.match(r'\s+up\b', text[e:])
        if m:
            return e + m.end(), text[s:e + m.end()]
    return e, surf


def ca_classify(it: CAItem, text, win_end):
    xm = it.x_matches(text)
    inwin = [m for m in xm if m['span'][1] <= win_end]
    strad = [m for m in xm if m['span'][0] < win_end < m['span'][1]]
    if strad:
        return None, 'value_straddles_window'
    if not inwin:
        return None, 'no_value_in_window'
    if len(inwin) > 1:
        return None, 'several_values_in_window'
    m = inwin[0]
    if m['neg']:
        return None, 'negated'
    vs = it.value_spans(text, win_end)
    if len(vs) != 1 or not (vs[0][0][0] <= m['span'][0] < vs[0][0][1]):
        return None, 'several_values_in_window_ext'
    lab_w, _ = it.L.label(text[:win_end])
    s, e = m['span']
    e2, surf2 = ca_extend_cover(text, s, e, m['surface'])
    info = {'span': (s, e2), 'surface': surf2, 'lex2_window': lab_w, 'lex2_full': it.L.label(text)[0]}
    if 'gold' in m['kinds']:
        if lab_w != 'gold':
            return None, f'lex2_window_{lab_w}'
        return 'right', info | {'value': it.gv}
    if 'contrast' in m['kinds']:
        if lab_w != 'contrast':
            return None, f'lex2_window_{lab_w}'
        return 'wrong', info | {'value': it.cv}
    return None, 'other_x_value'


def ca_check(ar, it: CAItem, new, expect, value_span_new=None, expect_surface=None):
    win = ar.window_end(new)
    if win is None:
        return False, 'edited_window_unmappable'
    vs = it.value_spans(new, win)
    xm = [m for m in it.x_matches(new) if m['span'][1] <= win]
    lab_w, _ = it.L.label(new[:win])
    kinds = [k for _, k in vs]
    tag = 'relabel_' + '+'.join(''.join(sorted(k)) for k in kinds)
    if expect == 'contrast':  # one value word, the contrast's (bank or extension), no gold word left
        ok = len(vs) == 1 and 'c' in kinds[0] and 'g' not in kinds[0]
        return (True, lab_w) if ok else (False, tag)
    if expect in ('gold', 'synonym'):  # one value word, gold's, nothing else
        ok = len(vs) == 1 and kinds[0] == {'g'}
        return (True, lab_w) if ok else (False, tag)
    if expect == 'frame':
        ok = (lab_w == 'gold' and len(vs) == 1 and kinds[0] == {'g'} and len(xm) == 1
              and (not expect_surface or xm[0]['surface'] == expect_surface))
        return (True, lab_w) if ok else (False, tag + f'_{lab_w}')
    raise ValueError(expect)


def ca_variants(ar, it: CAItem, text, src, key, rej):
    out = []

    def add(vtype, res, extra, expect, expect_surface=None):
        if res is None:
            rej.hit(f'{vtype}:no_form', item=it.id, surface=src['surface'])
            return False
        new, s, e, before, after, notes = res
        ok, info = check_window_edit(ar, text, new)
        if not ok:
            rej.hit(f'{vtype}:outside_window', item=it.id, before=before, after=after, tok=info['edit_tok_new'])
            return False
        ok, got = ca_check(ar, it, new, expect, expect_surface=expect_surface)
        if not ok:
            rej.hit(f'{vtype}:{got}', item=it.id, before=before, after=after, edited=new[max(0, s - 40):s + 60])
            return False
        out.append((vtype, new, {'char_span': [s, e], 'before': before, 'after': after, 'notes': notes,
                                 'lex2_window_after': got, **extra}, info))
        return True

    s, e = src['span']
    surf = text[s:e]

    def value_edit(table, vtype, expect, extra):
        k, entry = ca_lookup(table, surf)
        if entry is _MISSING:
            rej.hit(f'{vtype}:word_not_in_table', item=it.id, surface=surf, value=it.gv if src['kind'] == 'right' else it.cv)
            return False
        repl, s2, e2 = ca_resolve(entry, text, s, e)
        if not repl:
            rej.hit(f'{vtype}:no_form_in_context', item=it.id, surface=surf, context=text[max(0, s - 30):e + 30])
            return False
        repl = transfer_case(text[s2:e2], repl, None, at_sentence_start(text, s2))
        return add(vtype, apply_edit(text, s2, e2, repl), extra | {'table_key': k}, expect)

    if src['kind'] == 'right':
        if not value_edit(T.CA_SWAP.get((it.gv, it.cv), {}), 'swap_contrast', 'contrast',
                          {'value_to': it.cv}):
            return out
        value_edit(T.CA_SYN.get(it.gv, {}), 'synonym', 'synonym', {'synonym_kind': 'table'})
        ca_frame(ar, it, text, src, add, rej)
    else:
        value_edit(T.CA_SWAP.get((it.cv, it.gv), {}), 'reverse_to_gold', 'gold', {'value_to': it.gv})
    return out


def ca_frame(ar, it: CAItem, text, src, add, rej):
    win_end = ar.window_end(text)
    frames = []
    for ax, rs in it.L.frame.items():
        for r in rs:
            if r is not None:
                frames += [m.span() for m in r.finditer(text)]
    blocked = [m.span() for m in it.all_rx.finditer(text)] if it.all_rx else []
    tries = 0
    for s, e, w, kind in frame_candidates(text, win_end, src['span'], frames, blocked):
        repl = transfer_case(w, T.FRAME_SUB[w.lower()], None, at_sentence_start(text, s))
        tries += 1
        if add('frame', apply_edit(text, s, e, repl), {'frame_kind': kind, 'frame_word': w}, 'frame',
               expect_surface=src['surface'] if ' ' not in src['surface'] else None):
            return
        if tries >= 6:
            break
    rej.hit('frame:no_candidate' if tries == 0 else 'frame:none_passed', item=it.id, window=text[:win_end])


# ------------------------------------------------------------------------------------------ sources
def tag_table():
    import torch
    st = torch.load(C.AR_CKPT / 'heads.pt', map_location='cpu', weights_only=True)
    return {int(L): st['tag_ids'][i].tolist() for i, L in enumerate(st['layers']) if int(L) in C.LAYERS}


def collect_selected(fam):
    """Distinct (cell, phrase) bullets of the 3 settings with their occurrences and readout contexts."""
    rows = list(C.read_jsonl(C.DATA / f'select/{fam}_three_settings.jsonl'))
    out = collections.OrderedDict()
    for r in rows:
        for sid in C.SETTINGS:
            s = r['settings'][sid]
            pids = [a['source_phrase_id'] for a in s['atoms']]
            keys = [a['cache_key'] for a in s['atoms']]
            for i, a in enumerate(s['atoms']):
                k = (r['cell_id'], a['source_phrase_id'])
                d = out.get(k)
                if d is None:
                    d = out[k] = {'cell': r, 'atom': a, 'occurrences': []}
                elif d['atom']['text'] != a['text'] or d['atom']['cache_key'] != a['cache_key']:
                    raise SystemExit(f'phrase text/key differs across settings: {k}')
                d['occurrences'].append({'setting': sid, 'bullet_index': i, 'readout_phrase_ids': pids,
                                         'readout_cache_keys': keys, 'readout_fve_saved': s.get('fve')})
    return rows, out


def pool_index(fam):
    """phrase_id -> (pool bullet, same-sample context) for every pool bullet."""
    out = {}
    for pe in C.read_jsonl(C.DATA / f'select/{fam}_pool.jsonl'):
        by_sample = collections.defaultdict(list)
        for b in pe['bullets']:
            by_sample[b['sample_index']].append(b)
        for b in pe['bullets']:
            ctx = [x for x in by_sample[b['sample_index']]]
            out[b['phrase_id']] = {'cell_id': pe['cell_id'], 'bullet': b,
                                   'sample_phrase_ids': [x['phrase_id'] for x in ctx],
                                   'sample_cache_keys': [x['cache_key'] for x in ctx],
                                   'target_norm2': pe.get('target_norm2')}
    return out


def build(args):
    from olens_improve.ar_cache import vector_key
    t0 = time.time()
    ar = ARText()
    tags = tag_table()
    contract = json.loads((C.DATA / f'vectors/{C.OI_CONTRACT_SHA[:20]}/contract.json').read_text())
    if contract['sha256'] != C.OI_CONTRACT_SHA:
        raise SystemExit('vector contract differs')
    A = load_ca_analysis()
    from wsbench.evals.user_modeling.judge import build_options
    um_bank = C.load_bank('user_modeling')
    um_opts = build_options(list(um_bank.values()))
    um_items = {k: UMItem(it, um_opts[k]) for k, it in um_bank.items()}
    ca_bank = C.load_bank('conjunctive_association')
    ca_lex = A.build_lexicons(ca_bank)
    by_gold = {(it['cluster'], it['gold_label']): it for it in ca_bank.values()}
    cluster_x = collections.defaultdict(set)
    for it in ca_bank.values():
        for it2 in ca_bank.values():
            if it2['cluster'] == it['cluster'] and isinstance(it2['cell'].get(it['contrast_axis']), str):
                cluster_x[(it['cluster'], it['contrast_axis'])].add(it2['cell'][it['contrast_axis']])
    ca_items = {k: CAItem(it, by_gold[(it['cluster'], it['contrast_label'])], ca_lex[k], A,
                          sorted(cluster_x[(it['cluster'], it['contrast_axis'])])) for k, it in ca_bank.items()}
    llm = {}
    for r in C.read_jsonl(C.DATA / 'judge/ca_labels/ca_llm_bullet_labels.jsonl'):
        llm[(r['cell_id'], r['text'])] = r['label']
    um_lex_sha = C.file_sha(UL.__file__)
    um_summary = json.loads((C.DATA / 'labels/um_label_summary.json').read_text())
    if um_summary['lexicon_sha256'] != um_lex_sha:
        raise SystemExit('um_lexicon.py differs from the one that made data/labels/um_*')
    log('setup', round(time.time() - t0, 1), 's')

    rows_out, meta_counts, rejects = [], {}, {}
    for fam in FAMS:
        rows, sel = collect_selected(fam)
        vindex = json.loads((C.DATA / f'select/{fam}_vector_index.json').read_text())['nt']
        log(fam, 'selected distinct bullets', len(sel))
        pidx = pool_index(fam)
        log(fam, 'pool bullets', len(pidx))
        rej = Rej()
        sources = []
        for (cid, pid), d in sel.items():
            a, cell = d['atom'], d['cell']
            text = a['text']
            if a.get('cache_key') is None or a.get('status') != 'encoded_or_cache_hit':
                rej.hit('source:unscored', cell=cid)
                continue
            win = ar.window_end(text)
            if win is None:
                rej.hit('source:window_unmappable', text=text)
                continue
            ids = ar.ids(text)
            if ids[:WIN] != a['scored_token_ids'] or vector_key(C.OI_CONTRACT_SHA, tags[cell['layer']], ids[:WIN]) != a['cache_key']:
                rej.hit('source:cache_key_mismatch', cell=cid, phrase=pid)
                continue
            if fam == 'um':
                it = um_items[cell['item_id']]
                kind, info = um_classify(it, text, win)
            else:
                it = ca_items[cell['item_id']]
                kind, info = ca_classify(it, text, win)
            if kind is None:
                rej.hit(f'source:{info}', item=cell['item_id'], text=text[:win])
                continue
            info['kind'] = kind
            vars_ = (um_variants if fam == 'um' else ca_variants)(ar, it, text, info, pid, rej)
            main = 'reverse_to_gold' if kind == 'wrong' else ('swap_distractor' if fam == 'um' else 'swap_contrast')
            if not any(v[0] == main for v in vars_):
                rej.hit(f'source_dropped:{kind}:no_{main}', item=cell['item_id'], surface=info['surface'])
                continue
            sources.append((d, it, info, vars_))
        log(fam, 'eligible sources', collections.Counter(s[2]['kind'] for s in sources))
        # caps (right sources: all if <= max; reverse: cap) -- deterministic subsample by hash
        right = [s for s in sources if s[2]['kind'] == 'right']
        wrong = [s for s in sources if s[2]['kind'] == 'wrong']
        if len(right) > args.max_sources:
            right = sorted(right, key=lambda s: hpick(s[0]['atom']['source_phrase_id'], 1 << 30))[:args.max_sources]
        if len(wrong) > args.max_reverse:
            wrong = sorted(wrong, key=lambda s: hpick(s[0]['atom']['source_phrase_id'], 1 << 30))[:args.max_reverse]
        kept = right + wrong
        for d, it, info, vars_ in kept:
            a, cell = d['atom'], d['cell']
            pid = a['source_phrase_id']
            pinfo = pidx.get(pid)
            base = {
                'family': fam, 'source_key': pid, 'cell_id': cell['cell_id'], 'item_id': cell['item_id'],
                'group_id': cell['group_id'], 'layer': cell['layer'], 'position': cell['position'],
                'read_site': cell.get('read_position_kind') or cell.get('token'), 'token': cell.get('token'),
                'activation_row': cell['activation_row'], 'activation_sha256': cell['activation_sha256'],
                'source_set': 'selected', 'occurrences': d['occurrences'],
                'setting': d['occurrences'][0]['setting'], 'bullet_index': d['occurrences'][0]['bullet_index'],
                'in_pool': pinfo is not None, 'pool_solo_fve': (pinfo or {}).get('bullet', {}).get('solo_fve'),
                'pool_sample_context': ({'phrase_ids': pinfo['sample_phrase_ids'], 'cache_keys': pinfo['sample_cache_keys']}
                                        if pinfo else None),
                'source_kind': info['kind'], 'value_from': info['value'], 'value_span': list(info['span']),
                'value_surface': info['surface'], 'original_text': a['text'],
                'original_cache_key': a['cache_key'],
            }
            if fam == 'um':
                base |= {'subfamily': it.subfamily, 'attr_class': it.cls, 'gold': it.gold,
                         'distractors': it.distractors, 'role': info['role'], 'label_full': info['label_full'],
                         'in_prompt': info['in_prompt'], 'wrong_subtype': info.get('subtype')}
            else:
                base |= {'cluster': it.cluster, 'contrast_axis': it.X, 'gold': it.gv, 'contrast': it.cv,
                         'clean_item': it.clean, 'lex2_full': info['lex2_full'],
                         'llm_label': llm.get((cell['cell_id'], a['text'].strip()))}
            ids0 = ar.ids(a['text'])[:WIN]
            loc = vindex.get(a['cache_key'])
            rows_out.append(base | {'variant_type': 'original', 'edited_text': a['text'], 'edit': None,
                                    'edit_tok_orig': None, 'edit_tok_new': None, 'tok_delta': 0, 'char_delta': 0,
                                    'ar_ids32': ids0, 'vector_key': a['cache_key'], 'cached_vector': loc})
            for vtype, new, edit, info2 in vars_:
                vk = vector_key(C.OI_CONTRACT_SHA, tags[cell['layer']], info2['ar_ids32'])
                if vk == a['cache_key']:
                    rej.hit(f'{vtype}:same_vector_key', variant=pid)
                    continue
                rows_out.append(base | {'variant_type': vtype, 'edited_text': new, 'edit': edit,
                                        'edit_tok_orig': info2['edit_tok_orig'], 'edit_tok_new': info2['edit_tok_new'],
                                        'tok_delta': info2['tok_delta'], 'char_delta': len(new) - len(a['text']),
                                        'ar_ids32': info2['ar_ids32'], 'vector_key': vk, 'cached_vector': None})
        rejects[fam] = {'counts': dict(sorted(rej.items())), 'examples': dict(sorted(rej.examples.items()))}
        meta_counts[fam] = {'selected_distinct_bullets': len(sel), 'eligible_right': len([s for s in sources if s[2]['kind'] == 'right']),
                            'eligible_wrong': len([s for s in sources if s[2]['kind'] == 'wrong']),
                            'kept_right': len(right), 'kept_wrong': len(wrong)}
        log(fam, meta_counts[fam])
    for r in rows_out:
        r['variant_id'] = f"{r['family']}|{r['source_key']}|{r['variant_type']}"
    ids = [r['variant_id'] for r in rows_out]
    if len(set(ids)) != len(ids):
        raise SystemExit('duplicate variant ids')
    uniq = {(r['vector_key']) for r in rows_out}
    counts = collections.Counter((r['family'], r['source_kind'], r['variant_type']) for r in rows_out)
    meta = {'created': time.strftime('%F %T'), 'seed': SEED, 'window_tokens': WIN, 'contract_sha256': C.OI_CONTRACT_SHA,
            'tag_ids': {str(k): v for k, v in tags.items()}, 'um_lexicon_sha256': um_lex_sha,
            'edit_tables_sha256': C.file_sha(T.__file__), 'build_sha256': C.file_sha(__file__),
            'ca_analysis_sha256': C.file_sha(NT / 'analysis/ca/analysis.py'),
            'rows': len(rows_out), 'unique_vector_keys': len(uniq),
            'unique_vector_keys_new': len(uniq - {r['original_cache_key'] for r in rows_out}),
            'counts': {f'{f}|{k}|{v}': n for (f, k, v), n in sorted(counts.items())}, 'per_family': meta_counts,
            'args': vars(args)}
    if len(uniq) > args.max_encodings:
        raise SystemExit(f'{len(uniq)} encodings > cap {args.max_encodings}')
    tmp = OUT / 'variants.jsonl.tmp'
    with open(tmp, 'w') as f:
        for r in rows_out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    tmp.replace(OUT / 'variants.jsonl')
    C.atomic_json(OUT / 'build_meta.json', meta)
    C.atomic_json(OUT / 'rejects.json', rejects)
    log('done', len(rows_out), 'rows', len(uniq), 'unique vector keys', round(time.time() - t0, 1), 's')
    print(json.dumps(meta['counts'], indent=1))


def sample(args):
    rows = [json.loads(l) for l in open(OUT / 'variants.jsonl')]
    vsha = C.file_sha(OUT / 'variants.jsonl')
    edits = [r for r in rows if r['variant_type'] != 'original']
    rng = random.Random(args.seed)
    pick = rng.sample(edits, args.n)
    out = []
    for i, r in enumerate(pick):
        e = r['edit']
        s, t = e['char_span']
        o = r['original_text']
        shown_o = (o[max(0, s - 60):s] + '[[' + o[s:t] + ']]' + o[t:t + 60]).replace('\n', '\\n')
        n = r['edited_text']
        t2 = s + len(e['after'])
        shown_n = (n[max(0, s - 60):s] + '[[' + n[s:t2] + ']]' + n[t2:t2 + 60]).replace('\n', '\\n')
        out.append({'i': i, 'seed': args.seed, 'variants_sha256': vsha, 'variant_id': r['variant_id'], 'family': r['family'], 'variant_type': r['variant_type'],
                    'item_id': r['item_id'], 'gold': r['gold'], 'value_from': r['value_from'],
                    'value_to': e.get('value_to'), 'before': e['before'], 'after': e['after'],
                    'original_context': shown_o, 'edited_context': shown_n, 'edit_tok_orig': r['edit_tok_orig'],
                    'edit_tok_new': r['edit_tok_new'], 'reader_verdict': None, 'reader_note': None})
        print(f"[{i}] {r['family']} {r['variant_type']} {r['item_id']} gold={r['gold']} from={r['value_from']} "
              f"to={e.get('value_to')} tok={r['edit_tok_orig']}->{r['edit_tok_new']} notes={e.get('notes')} "
              f"{ {k: e[k] for k in ('synonym_kind', 'frame_kind', 'frame_word') if k in e} }")
        print('   O:', shown_o)
        print('   E:', shown_n)
    path = OUT / 'validation_sample.jsonl'
    if path.exists() and not args.force:
        print('validation_sample.jsonl exists; not overwritten (use --force)')
        return
    with open(path, 'w') as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--max-sources', type=int, default=3000, help='right-value sources per family')
    b.add_argument('--max-reverse', type=int, default=800, help='wrong-value (reverse) sources per family')
    b.add_argument('--max-encodings', type=int, default=30000)
    s = sub.add_parser('sample')
    s.add_argument('--n', type=int, default=40)
    s.add_argument('--force', action='store_true')
    s.add_argument('--seed', type=int, default=SEED + 2, help='round 1 (before the last fixes) used 20261016')
    args = ap.parse_args()
    {'build': build, 'sample': sample}[args.cmd](args)


if __name__ == '__main__':
    main()
