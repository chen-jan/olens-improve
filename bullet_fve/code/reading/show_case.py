#!/usr/bin/env python
"""Plain-text viewer for one Bullet-FVE reading case.

usage: show_case.py <k> <setting_id|all> [--bullet I] [--blind] [--focus-setting SID] [--no-raw]

  k        cell key "<item_id>.L<layer>.p<pos>", e.g. chat-dailydialog-0000.L20.p23
  setting  capped_n1-n1 | best_n_exact-n32 | pooled_greedy_swap-n32 | raw_n1-n1 | all
           (aliases: orig/original, best, comb/combine, raw)
  --bullet I         focus bullet, 0-based index into that setting's bullet list (b0..b3)
  --focus-setting S  with setting "all": the setting the --bullet index refers to
  --blind            hide every FVE / Shapley / solo / drop / NNLS-coef / dup number, the best-of-32
                     candidate scores and the other settings' labels; keep all judge information
  --no-raw           with "all": do not print the released raw lens output (reference)

Offsets in the data are UTF-16 code units; they are converted to Python code points here.
Ground truth for the judge is the model's own reply (text before and after the READ marker).
"""
import argparse
import json
import os
import statistics
import sys

DATA = '${OLENS_SCRATCH}/olens-bullet-fve/page/data'
PAGE = 'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3'
SETTINGS = [('capped_n1-n1', 'Original'), ('best_n_exact-n32', 'Best of 32'),
            ('pooled_greedy_swap-n32', 'Combine 32')]
REF = ('raw_n1-n1', 'Raw released lens output (reference, no scores)')
SHORT = dict(SETTINGS + [REF])
ALIAS = {'orig': 'capped_n1-n1', 'original': 'capped_n1-n1', 'capped': 'capped_n1-n1',
         'best': 'best_n_exact-n32', 'bo32': 'best_n_exact-n32',
         'comb': 'pooled_greedy_swap-n32', 'combine': 'pooled_greedy_swap-n32', 'pooled': 'pooled_greedy_swap-n32',
         'raw': 'raw_n1-n1', 'ref': 'raw_n1-n1'}
BULLET_LABEL = {'w': 'WRONG', 'o': 'OFF-TOPIC', 'c': 'clean', 'x': 'n/a (generic/empty readout)'}
PROMPT_MAX, PROMPT_HEAD, PROMPT_TAIL = 1500, 1050, 400
BEFORE, AFTER = 1200, 600


class U16:
    """UTF-16 code-unit offset -> Python code-point index for one string."""

    def __init__(self, text):
        self.text = text
        self.cp = {}
        u = 0
        for i, ch in enumerate(text):
            self.cp[u] = i
            u += 2 if ord(ch) > 0xFFFF else 1
        self.cp[u] = len(text)
        self.n16 = u

    def __call__(self, o):
        o = max(0, min(int(o), self.n16))
        while o not in self.cp:      # inside a surrogate pair (should not happen): move left
            o -= 1
        return self.cp[o]


def wrap(text, indent, width=110):
    """Indent every line of text (keeps the lens's own newlines; no re-flow)."""
    pad = ' ' * indent
    return '\n'.join(pad + line for line in text.split('\n'))


def fmt(x, nd=4):
    return 'NA' if x is None else f'{x:.{nd}f}'


def resolve_setting(s):
    s = ALIAS.get(s.lower(), s)
    if s != 'all' and s not in SHORT:
        sys.exit(f'unknown setting {s!r}; use one of {[x for x, _ in SETTINGS] + [REF[0], "all"]}')
    return s


def load_case(k):
    try:
        item_id, lpart, ppart = k.rsplit('.', 2)
        assert lpart.startswith('L') and ppart.startswith('p')
    except (ValueError, AssertionError):
        sys.exit(f'bad case key {k!r}; expected <item_id>.L<layer>.p<pos>')
    path = os.path.join(DATA, 'items', item_id + '.json')
    if not os.path.exists(path):
        sys.exit(f'no item file {path}')
    with open(path) as f:
        d = json.load(f)
    if k not in d['cells']:
        sys.exit(f'cell {k} not in {path}')
    return d['item'], d['cells'][k]


# ----------------------------------------------------------------------------- context
def show_context(item, cell, k):
    out = []
    out.append('=' * 100)
    out.append(f'CASE {k}   ({PAGE}#{k})')
    out.append(f'item {item["id"]} | source {item["source"]} | split {item["split"]} | layer {cell["layer"]} | '
               f'token position {cell["pos"]} | site kind {cell["site_kind"]}')
    prompt = item['prompt']
    out.append('-' * 100)
    out.append(f'USER PROMPT ({len(prompt)} chars):')
    if len(prompt) > PROMPT_MAX:
        prompt = (prompt[:PROMPT_HEAD] + f'\n  [... {len(prompt) - PROMPT_HEAD - PROMPT_TAIL} chars omitted ...]\n'
                  + prompt[-PROMPT_TAIL:])
    out.append(wrap(prompt, 2))
    resp = item['response']
    u = U16(resp)
    ch = u(cell['char'])
    site = next((s for s in item['sites'] if s['pos'] == cell['pos']), None)
    tok = site['token'] if site else ''
    tok_start = ch - len(tok) if tok and resp[:ch].endswith(tok) else ch
    lo, hi = max(0, tok_start - BEFORE), min(len(resp), ch + AFTER)
    out.append('-' * 100)
    out.append(f'MODEL REPLY ({len(resp)} chars; the judge\'s ground truth). Read token {tok!r} '
               f'(site kind: {cell["site_kind"]}) at reply chars {tok_start}-{ch}; the lens reads the activation '
               f'at this token, marked ⟦READ⟧ right after it. Shown: {tok_start - lo} chars before the token, '
               f'{hi - ch} after the marker.')
    body = ''
    if lo > 0:
        body += f'[... {lo} earlier chars omitted ...]'
    body += resp[lo:tok_start] + '«' + resp[tok_start:ch] + '»⟦READ⟧' + resp[ch:hi]
    if hi < len(resp):
        body += f'[... {len(resp) - hi} later chars omitted ...]'
    out.append(wrap(body, 2))
    out.append('  (« » encloses the read token itself)')
    out.append('JUDGE RULES: a span is wrong if it contradicts or is not supported by the reply/prompt; off-topic if '
               'unrelated junk; a reasonable continuation of the text BEFORE ⟦READ⟧ counts as consistent even if the '
               'reply went another way. Readout = hallucinated if any verified wrong span.')
    return out


# ----------------------------------------------------------------------------- readout rendering
def render_range(text16, a16, b16, marks):
    """Render text16[a16:b16] with nested open/close marks.

    marks: list of (start16, end16, open_str, close_str, mid) clipped to [a16, b16)."""
    u = text16
    events = {}
    clipped = []
    for (s, e, op, cl, mid) in marks:
        s2, e2 = max(s, a16), min(e, b16)
        if s2 >= e2:
            continue
        clipped.append((s2, e2, op, cl, mid))
    pts = sorted({a16, b16} | {m[0] for m in clipped} | {m[1] for m in clipped})
    out = []
    stack = []
    for i, p in enumerate(pts):
        # close marks ending here (last opened first); if crossing, label the close with its id
        if any(m[1] == p for m in stack):
            for idx in range(len(stack) - 1, -1, -1):
                m = stack[idx]
                if m[1] != p:
                    continue
                # crossing: a mark opened after this one stays open past p
                crossing = any(o[1] != p for o in stack[idx + 1:])
                out.append(m[3] + (m[4] if crossing else ''))
            stack = [m for m in stack if m[1] != p]
        if p == b16:
            break
        for m in sorted([m for m in clipped if m[0] == p], key=lambda m: -m[1]):
            out.append(m[2])
            stack.append(m)
        nxt = pts[i + 1]
        out.append(u.text[u(p):u(nxt)])
    for m in reversed(stack):
        out.append(m[3])
    return ''.join(out)


def show_setting(cell, sid, focus, blind, others_line):
    s = cell['settings'].get(sid)
    out = []
    title = SHORT[sid]
    out.append('=' * 100)
    if s is None:
        out.append(f'SETTING {title} [{sid}]: not available for this cell')
        return out
    text = s['text'] or ''
    u = U16(text)
    is_ref = sid == REF[0]
    bullets = s.get('bullets') or []
    head = f'SETTING {title} [{sid}] | readout label: {s.get("label") or "empty"}'
    if s.get('judge_kind'):
        head += f' (judge kind: {s["judge_kind"]})'
    out.append(head)
    if not is_ref:
        if not blind:
            out.append(f'joint FVE {fmt(s.get("fve"))} | {len(bullets)} bullets')
        else:
            out.append(f'{len(bullets)} bullets')
    if others_line and not blind:
        out.append(others_line)
    if not blind and sid == 'best_n_exact-n32' and s.get('trace'):
        sc = [x for x in s['trace']['scores'] if x is not None]
        ch = s['trace']['chosen_sample']
        chosen = s['trace']['scores'][ch] if ch is not None else None
        rank = 1 + sum(1 for x in sc if chosen is not None and x > chosen)
        orig = cell['settings'].get('capped_n1-n1', {}).get('fve')
        out.append(f'best-of-32 candidates (joint FVE of each complete 4-bullet readout, n={len(sc)}): '
                   f'chosen sample #{ch} = {fmt(chosen)} (rank {rank}/{len(sc)}); min {fmt(min(sc))}, '
                   f'median {fmt(statistics.median(sc))}, max {fmt(max(sc))}; sample #0 = {fmt(s["trace"]["scores"][0])}; '
                   f'Original (capped) readout FVE {fmt(orig)}')
    out.append('-' * 100)

    spans = s.get('spans') or []
    sp_ids = {id(sp): j + 1 for j, sp in enumerate(spans)}
    marks = []
    for sp in spans:
        n = sp_ids[id(sp)]
        typ = 'WRONG' if sp['type'] == 'wrong' else 'OFFTOPIC'
        if not sp['verified']:
            typ = 'uncounted-' + typ.lower()
        for a, b in sp.get('offsets') or []:
            marks.append((a, b, f'[[{typ}#{n}: ', ']]', f'#{n}'))
    if not bullets:
        out.append('READOUT TEXT (no bullet structure):')
        body = render_range(u, 0, u.n16, marks) if text else '(empty readout)'
        out.append(wrap(body, 4))
    else:
        out.append('READOUT BULLETS (0-based index b#, position in list; Combine 32 order = greedy selection order; '
                   '‹unscored: …› = text past the 32-token reconstructor limit, which no FVE number sees):')
    for j, b in enumerate(bullets):
        star = '>>' if focus is not None and j == focus else '  '
        lab = BULLET_LABEL.get(b.get('label'), b.get('label'))
        line = f'{star} b{j} (position {j + 1}/{len(bullets)}) [{lab}]'
        if focus is not None and j == focus:
            line += '  <== FOCUS BULLET'
        if not blind:
            share = b.get('shap_share')
            line += (f' | Shapley share {"NA" if share is None else f"{100 * share:.1f}%"} | Shapley {fmt(b.get("shap"))}'
                     f' | solo {fmt(b.get("solo"))} | drop {fmt(b.get("drop"))} | NNLS coef {fmt(b.get("coef"), 3)}'
                     f'{" | dup (shares one AR vector with another bullet)" if b.get("dup") else " | dup no"}')
        if b.get('truncated'):
            line += ' | truncated at 32 tokens'
        line += f' | from sample #{b.get("sample_index")}'
        out.append(line)
        bm = list(marks)
        if b['scored_end'] < b['end']:
            bm.append((b['scored_end'], b['end'], '‹unscored: ', '›', ''))
        out.append(wrap(render_range(u, b['start'], b['end'], bm), 6))
    if bullets:
        # text outside bullets (only report if it carries a span)
        covered = [(b['start'], b['end']) for b in bullets]
        for sp in spans:
            for a, e in sp.get('offsets') or []:
                if not any(a < be and e > bs for bs, be in covered):
                    out.append(f'   (span #{sp_ids[id(sp)]} lies outside every bullet, at chars {a}-{e})')

    if focus is not None and focus < len(bullets):
        fb = bullets[focus]
        fsp = [f'#{sp_ids[id(sp)]} {sp["type"]}{"" if sp["verified"] else " (not counted)"}'
               for sp in spans if focus in (sp.get('bullets') or [])]
        fcl = [f'{c["status"]}: {c["quote"]!r}' for c in (s.get('claims') or []) if focus in (c.get('bullets') or [])]
        out.append(f'FOCUS b{focus}: bullet label {BULLET_LABEL.get(fb.get("label"))}; judge spans in it: '
                   f'{", ".join(fsp) or "none"}; stage-2 claims in it: {" | ".join(fcl) or "none"}')
    out.append('-' * 100)
    out.append('JUDGE SPANS (stage 1; only verified spans count toward the label):')
    if not spans:
        out.append('   none')
    for sp in spans:
        n = sp_ids[id(sp)]
        where = []
        if sp.get('bullets'):
            where.append('in ' + ', '.join(f'b{x}' for x in sp['bullets']))
        if not sp.get('offsets'):
            where.append('text not found in readout')
        if sp.get('in_unscored'):
            where.append('entirely in the AR-unscored tail')
        status = 'verified' if sp['verified'] else (
            'NOT counted (' + ('shorter than 3 characters' if sp.get('offsets') else 'text not found in readout') + ')')
        out.append(f'   #{n} {sp["type"].upper()} [{status}] {"; ".join(where)}')
        out.append(f'       span: {sp["text"]!r}')
        out.append(f'       why : {sp.get("why")}')
    if s.get('rationale'):
        out.append(f'JUDGE RATIONALE (stage 1): {s["rationale"]}')
    if s.get('verify_rationale'):
        out.append(f'JUDGE RATIONALE (stage 2): {s["verify_rationale"]}')
    claims = s.get('claims') or []
    out.append(f'STAGE-2 CLAIMS ({len(claims)}), grouped by status:')
    order = ['true', 'unverifiable', 'disputed', 'off_topic']
    statuses = order + sorted({c['status'] for c in claims} - set(order))
    for st in statuses:
        group = [c for c in claims if c['status'] == st]
        if not group:
            continue
        out.append(f'   [{st}] ({len(group)})')
        for c in group:
            loc = ', '.join(f'b{x}' for x in c.get('bullets') or []) if not is_ref else ''
            extra = []
            if loc:
                extra.append(loc)
            if c.get('counted_as') and c['counted_as'] != c['status']:
                extra.append('counted as ' + c['counted_as'])
            out.append(f'     - {c["quote"]!r}' + (f' ({"; ".join(extra)})' if extra else ''))
            out.append(f'         why: {c.get("why")}')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('k')
    ap.add_argument('setting')
    ap.add_argument('--bullet', type=int, default=None)
    ap.add_argument('--blind', action='store_true')
    ap.add_argument('--focus-setting', default=None)
    ap.add_argument('--no-raw', action='store_true')
    a = ap.parse_args()
    sid = resolve_setting(a.setting)
    item, cell = load_case(a.k)
    out = show_context(item, cell, a.k)
    labels = {x: (cell['settings'].get(x) or {}).get('label') or 'empty' for x, _ in SETTINGS + [REF]}
    if sid == 'all':
        sids = [x for x, _ in SETTINGS]
        focus_sid = resolve_setting(a.focus_setting) if a.focus_setting else None
        if a.bullet is not None and focus_sid is None:
            out.append('(note: --bullet with "all" needs --focus-setting; no bullet marked)')
        if not a.no_raw and REF[0] in cell['settings']:
            sids.append(REF[0])
    else:
        sids, focus_sid = [sid], sid
    for x in sids:
        others = 'labels in all settings for this cell: ' + ' | '.join(
            f'{SHORT[y] if y != REF[0] else "Raw reference"}: {labels[y]}' for y, _ in SETTINGS + [REF]
            if y in cell['settings'])
        if x == REF[0]:
            same = (cell['settings'][REF[0]]['text'] == cell['settings']['capped_n1-n1']['text'])
            if same and sid == 'all':
                out.append('=' * 100)
                out.append(f'SETTING {REF[1]} [{REF[0]}]: text identical to Original; label {labels[REF[0]]}')
                continue
        focus = a.bullet if (x == focus_sid) else None
        if focus is not None:
            nb = len(cell['settings'][x].get('bullets') or [])
            if not 0 <= focus < nb:
                sys.exit(f'--bullet {focus} out of range: {SHORT[x]} has {nb} bullets (0-based)')
        out.extend(show_setting(cell, x, focus, a.blind, others if sid != 'all' or x == sids[0] else None))
    out.append('=' * 100)
    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
