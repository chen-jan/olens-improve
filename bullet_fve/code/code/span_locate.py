"""Locate judge spans (verified under normalize_ws) as raw char offsets in a readout; map to bullets."""
import re
from hall_judge_context import normalize_ws, _QUOTES

_DASH_BLOCK = re.compile(r"^[ \t]*-[ \t]+", re.MULTILINE)   # olens_improve.selection._DASH_BLOCK


def bullets_with_offsets(text):
    """[(start, end, bullet_text)] using the project's source_contiguous_dash_blocks_v1 rule.
    start = first char after the '- ' marker, end = next marker start (or len(text))."""
    ms = list(_DASH_BLOCK.finditer(text))
    out = []
    for i, m in enumerate(ms):
        s = m.end(); e = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out.append((s, e, text[s:e]))
    return out


def _norm_with_map(text):
    """normalize_ws without the final strip, plus norm-index -> raw-index map."""
    chars, idx = [], []
    prev_space = False
    for i, ch in enumerate(text):
        t = ch.translate(_QUOTES)
        if t.isspace() or re.fullmatch(r"\s", t):
            if prev_space:
                continue
            chars.append(' '); idx.append(i); prev_space = True
            continue
        prev_space = False
        for c in t.lower():
            chars.append(c); idx.append(i)
    return ''.join(chars), idx


def locate(text, span):
    """All (start, end) raw offsets of span in text: exact match first, else normalize_ws match."""
    hits = []
    if span:
        i = text.find(span)
        while i != -1:
            hits.append((i, i + len(span), 'exact'))
            i = text.find(span, i + 1)
    if hits:
        return hits
    q = normalize_ws(span)
    if len(q) < 3:
        return []
    norm, idx = _norm_with_map(text)
    j = norm.find(q)
    while j != -1:
        hits.append((idx[j], idx[j + len(q) - 1] + 1, 'normalized'))
        j = norm.find(q, j + 1)
    return hits


def bullet_index(bullets, start, end):
    """Bullet indexes overlapped by raw [start, end)."""
    return [k for k, (s, e, _) in enumerate(bullets) if start < e and end > s]
