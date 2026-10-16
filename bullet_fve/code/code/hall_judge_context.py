#!/usr/bin/env python3
"""Read-only loader for Hallucination (chat) judge verdicts + benchmark context, three settings.

Run with:  python -B hall_judge_context.py   (-B: never write __pycache__ anywhere)
Only reads frozen files; writes nothing unless --dump PATH is given (scratch only).
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

EXP = Path('${OLENS_DATA_ROOT}/expansion-v1')
BANK = Path('${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2/evals/hallucination/items.json')
SELECTIONS = EXP / 'selections/cached-v2/hallucination.jsonl'   # all 3 settings live here
SETTINGS = {  # setting id (= judgments dir name) -> (method, n, display label)
    'capped_n1-n1': ('capped_n1', 1, 'Original, capped to four bullets'),
    'best_n_exact-n32': ('best_n_exact', 32, 'Choose the best complete readout (32 samples)'),
    'pooled_greedy_swap-n32': ('pooled_greedy_swap', 32, 'Combine original bullets (32 samples)'),
}
READ_MARK = '⟦READ⟧'

# ---- verbatim from wsbench/evals/hallucination/judge.py (sha cdb35679...) ----
_WS = re.compile(r'\s+')
_QUOTES = str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'", '«': '"', '»': '"'})


def normalize_ws(s: str) -> str:
    return _WS.sub(' ', s.translate(_QUOTES)).strip().lower()


def verify_quote(quote: str, haystacks) -> bool:
    q = normalize_ws(quote)
    if len(q) < 3:
        return False
    return any(q in normalize_ws(h) for h in haystacks)
# -----------------------------------------------------------------------------


def judge_key(item_id: str, layer: int, pos: int) -> str:
    """Judge cache/results key, e.g. chat-dailydialog-0000__L020__p23."""
    return f'{item_id}__L{layer:03d}__p{pos}'


def load_bank():
    items = json.loads(BANK.read_text())['items']
    by_id = {it['id']: it for it in items}
    sites = {(it['id'], int(s['pos'])): s for it in items for s in it['sites']}
    return by_id, sites


def load_selections():
    """(item_id, layer, pos) -> {cell_id, split, text{setting}, sel{setting}}"""
    out = {}
    want = {(m, n): sid for sid, (m, n, _) in SETTINGS.items()}
    with SELECTIONS.open() as fh:
        for line in fh:
            r = json.loads(line)
            k = (r['item_id'], r['layer'], r['position'])
            rec = {'cell_id': r['cell_id'], 'split': r['split'], 'text': {}, 'sel': {}}
            for s in r['selections']:
                sid = want.get((s['method'], s['n']))
                if sid:
                    rec['text'][sid] = s['text']
                    rec['sel'][sid] = {x: s.get(x) for x in ('token_count', 'bullet_count', 'reason', 'fits_scope')}
            out[k] = rec
    return out


def load_judgments(setting: str):
    """key -> {'row': results.json row, 's1': stage-1 raw result, 's2': stage-2 raw result}"""
    base = EXP / 'judgments' / setting
    res = json.loads((base / 'hallucination/results.json').read_text())
    rows = {r['key']: r for r in res['rows']}
    s1, s2, dup = {}, {}, collections.Counter()
    with (base / 'hallucination/cells.jsonl').open() as fh:
        for line in fh:
            r = json.loads(line)
            if r.get('result') is None:      # failed attempt in append-only cache
                continue
            if r['key'].endswith(':V'):
                k = r['key'][:-2]
                dup['s2'] += k in s2
                s2[k] = r                    # last successful row wins (Cache.get semantics)
            else:
                k = r['key']
                dup['s1'] += k in s1
                s1[k] = r
    return res, rows, s1, s2, dup


def split_readout(text: str):
    """Selected readout -> list of bullet strings (lines starting with '- ')."""
    return [ln for ln in text.split('\n') if ln.strip()]


def marked_context(item: dict, site: dict):
    """(before, after) of the response around the judge's ⟦READ⟧ marker (render_marked_response)."""
    resp = item['response']
    c = max(0, min(int(site['char']), len(resp)))
    return resp[:c], resp[c:]


def tally_claim_list(raw_sample: dict, readout: str, wrong):
    """Stage-2 claims with the code-derived status that tally_claims() would count."""
    w = [normalize_ws(x) for x in wrong]
    out = []
    for cl in raw_sample.get('claims') or []:
        q = str(cl.get('quote') or '')
        if not q or not verify_quote(q, [readout]):
            counted = 'n_unverified'
        elif any(x in normalize_ws(q) or normalize_ws(q) in x for x in w):
            counted = 'skipped_overlaps_false'
        else:
            st = str(cl.get('status') or '').strip().lower()
            counted = st if st in ('true', 'off_topic', 'disputed') else 'unverifiable'
        out.append({**cl, 'counted_as': counted})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--examples', nargs='*', default=[])
    args = ap.parse_args()
    by_id, sites = load_bank()
    sel = load_selections()
    print('bank items', len(by_id), 'sites', len(sites), '| selection cells', len(sel))
    assert set((i, p) for (i, l, p) in sel) == set(sites), 'selection grid != bank sites'
    # counts per split / layer
    sp = collections.Counter(v['split'] for v in sel.values())
    ly = collections.Counter(k[1] for k in sel)
    spl = collections.Counter((v['split'], k[1]) for k, v in sel.items())
    items_by_split = collections.defaultdict(set)
    for k, v in sel.items():
        items_by_split[v['split']].add(k[0])
    print('cells per split', dict(sp), '| items per split', {s: len(v) for s, v in items_by_split.items()})
    print('cells per layer', dict(sorted(ly.items())))
    print('cells per (split,layer)', dict(sorted(spl.items())))
    print('site kinds (cells)', dict(collections.Counter(sites[(k[0], k[2])]['kind'] for k in sel)))
    for setting in SETTINGS:
        res, rows, s1, s2, dup = load_judgments(setting)
        n = res['numbers']['extras']
        stats = collections.Counter()
        cls_by_split = collections.Counter()
        for k, v in sel.items():
            key = judge_key(*k)
            text = v['text'][setting]
            row = rows.get(key)
            if row is None:
                stats['no_row(empty_text)' if not text.strip() else 'no_row_NONEMPTY'] += 1
                continue
            stats['row'] += 1
            judged = row['samples'][0]
            stats['judged==selected'] += judged == text
            stats['s1_meta==selected'] += s1[key]['meta']['samples'][0] == text
            stats['s2_meta==selected'] += s2[key]['meta']['samples'][0] == text
            ver = row['verdict'][0]
            cls_by_split[(v['split'], ver['class'])] += 1
            stats['cls_' + ver['class']] += 1
            # re-derive verified spans from the raw stage-1 record
            raw = s1[key]['result']['samples'][0]
            rw = [sp['text'] for sp in raw.get('spans') or [] if verify_quote(sp['text'], [text]) and sp.get('type') != 'off_topic']
            ro = [sp['text'] for sp in raw.get('spans') or [] if verify_quote(sp['text'], [text]) and sp.get('type') == 'off_topic']
            stats['rederived_wrong==row'] += rw == ver['wrong']
            stats['rederived_off==row'] += ro == ver['off_topic']
            stats['s2_wrong_given==row'] += s2[key]['meta']['wrong'] == [ver['wrong']]
            for w in ver['wrong']:
                stats['wrong_spans'] += 1
                stats['wrong_raw_substring'] += w in text
                stats['wrong_norm_substring'] += normalize_ws(w) in normalize_ws(text)
            for w in ver['off_topic']:
                stats['off_spans'] += 1
                stats['off_raw_substring'] += w in text
            stats['unverified_spans_dropped'] += ver['n_unverified']
            # stage-2 claim tally reproduces results.json
            cl = tally_claim_list(s2[key]['result']['samples'][0], text, ver['wrong'])
            c = collections.Counter(x['counted_as'] for x in cl)
            mine = {'false': len(ver['wrong']), 'true': c['true'], 'unverifiable': c['unverifiable'] + c['disputed'],
                    'disputed': c['disputed'], 'off_topic': c['off_topic'], 'n_unverified': c['n_unverified']}
            stats['claims_tally_reproduced'] += mine == ver['claims']
        print(f'\n== {setting} ({SETTINGS[setting][2]})  dup_cache_rows={dict(dup)}')
        print('  results extras: n_readouts', n['n_readouts'], 'n_specific', n['n_specific'], 'n_hallucinated', n['n_hallucinated'],
              'n_off_topic', n['n_off_topic'], 'rate', round(res['numbers']['value'], 4))
        print('  ', dict(stats))
        print('   class x split', dict(sorted(cls_by_split.items())))
    for ex in args.examples:
        item, layer, pos = ex.split(':')
        k = (item, int(layer), int(pos))
        v, site, it = sel[k], sites[(item, int(pos))], by_id[item]
        before, after = marked_context(it, site)
        print('\n' + '#' * 100)
        print(f'CELL {v["cell_id"]}  judge_key={judge_key(*k)}  split={v["split"]}  site_kind={site["kind"]} token={site["token"]!r} char={site["char"]}')
        print('PROMPT:', it['prompt'][:300].replace('\n', ' / '))
        print('BEFORE ...', repr(before[-220:]))
        print('AFTER  ', repr(after[:220]))
        for setting in SETTINGS:
            res, rows, s1, s2, _ = load_judgments(setting)
            key = judge_key(*k)
            text = v['text'][setting]
            row = rows[key]
            ver = row['verdict'][0]
            raw = s1[key]['result']['samples'][0]
            print(f'\n  -- {setting}: class={ver["class"]} kind={ver["kind"]} claims={ver["claims"]}')
            for b in split_readout(text):
                print('     |', b)
            for spn in raw.get('spans') or []:
                ok = verify_quote(spn['text'], [text])
                print(f'     SPAN[{spn["type"]}] verified={ok} raw_substring={spn["text"] in text}: {spn["text"]!r}  why: {spn["why"]}')
            for cl in tally_claim_list(s2[key]['result']['samples'][0], text, ver['wrong'])[:6]:
                print(f'     CLAIM {cl["counted_as"]:>12}: {cl["quote"]!r}  why: {cl["why"]}')


if __name__ == '__main__':
    main()
