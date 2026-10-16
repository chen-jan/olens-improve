"""Conjunctive-association bullet labels from the bank's own regex lexicons (free; no API).

Per item: X = contrast_axis (the respect in which gold and contrast differ). The bank gives
credit[axis] = word groups naming GOLD's value on that axis (an axis is credited when every group
has a hit), and competitors[axis] = words naming OTHER values on the varied axes.
Per bullet (word-boundary, case-insensitive):
  gold      : credit[X] credited                          (right filler)
  contrast  : a competitors[X] word                       (wrong filler on the differing axis; NB this
              covers every other value of X, not only the contrast option's)
  mixed     : both of the above
  other_wrong: a competitors[Y] word for another varied axis Y (wrong filler on another axis)
  frame_only: any credit group of a non-X axis hits (content gold and contrast share), none of the above
  none      : nothing
Group names shared with the LLM labels: right = gold; wrong = contrast | other_wrong; frame = frame_only.
"""
from __future__ import annotations

import re


def _rx(words):
    words = sorted({w.lower() for w in words}, key=len, reverse=True)
    if not words:
        return None
    alts = (r'[\s\-]+'.join(re.escape(p) for p in re.split(r'[\s\-]+', w.strip())) for w in words)
    return re.compile(r'(?<![\w])(?:' + '|'.join(alts) + r')(?![\w])', re.I)


class ItemLexicon:
    def __init__(self, item: dict):
        self.id = item['id']
        self.axis = item['contrast_axis']
        self.credit = {ax: [_rx(g) for g in groups] for ax, groups in item['credit'].items()}
        self.competitors = {ax: _rx(ws) for ax, ws in item['competitors'].items()}

    def _credited(self, text, axis):
        groups = self.credit.get(axis, [])
        hits = [bool(g and g.search(text)) for g in groups]
        return bool(groups) and all(hits), any(hits)

    def label(self, text: str) -> dict:
        gold, _ = self._credited(text, self.axis)
        rx = self.competitors.get(self.axis)
        contrast = bool(rx and rx.search(text))
        other_wrong = [ax for ax, r in self.competitors.items() if ax != self.axis and r and r.search(text)]
        frame_axes = [ax for ax in self.credit if ax != self.axis and self._credited(text, ax)[1]]
        if gold and contrast:
            lab = 'mixed'
        elif gold:
            lab = 'gold'
        elif contrast:
            lab = 'contrast'
        elif other_wrong:
            lab = 'other_wrong'
        elif frame_axes:
            lab = 'frame_only'
        else:
            lab = 'none'
        group = {'gold': 'right', 'contrast': 'wrong', 'other_wrong': 'wrong', 'frame_only': 'frame',
                 'none': 'none', 'mixed': 'mixed'}[lab]
        return {'label': lab, 'group': group, 'gold_hit': gold, 'contrast_hit': contrast,
                'other_wrong_axes': other_wrong, 'frame_axes': frame_axes}
