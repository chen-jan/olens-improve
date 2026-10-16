#!/usr/bin/env python3
"""Validate the Bullet FVE Explorer page data written by build_page_data.py (reads the written JSON only,
plus the slim extract for bullet texts). Offsets are checked as JavaScript (UTF-16) indices.

python -B validate_page_data.py [--data page/data] [--examples K K K] [--partial]
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hall_judge_context import normalize_ws  # noqa: E402

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
SLIM = ROOT / 'inputs/hall_three_settings.jsonl'
EXPECTED = {  # DATAMAP_REPORT: hallucinated / consistent / off_topic / generic / empty
    'capped_n1-n1': (2641, 2336, 577, 59, 2),
    'best_n_exact-n32': (2550, 2477, 538, 49, 1),
    'pooled_greedy_swap-n32': (2621, 2382, 552, 59, 1),
}
KEY_RE = re.compile(r'^[a-z0-9-]+\.L\d+\.p\d+$')


def s16(text, a, b):
    """JS-style text.slice(a, b) for UTF-16 offsets; raises if a surrogate pair is cut."""
    return text.encode('utf-16-le')[2 * a:2 * b].decode('utf-16-le', errors='strict')


def len16(text):
    return len(text.encode('utf-16-le')) // 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(ROOT / 'page/data'))
    ap.add_argument('--examples', nargs='*', default=None)
    ap.add_argument('--partial', action='store_true')
    args = ap.parse_args()
    D = Path(args.data)
    # ---------------------------------------------------------------- files
    files = sorted(p for p in D.rglob('*') if p.is_file())
    sizes = {str(p.relative_to(D)): p.stat().st_size for p in files}
    items_sz = {k: v for k, v in sizes.items() if k.startswith('items/')}
    heat_sz = {k: v for k, v in sizes.items() if k.startswith('heat/')}
    big = max(items_sz, key=items_sz.get)
    print(f'FILES {len(files)} (items {len(items_sz)}, heat {len(heat_sz)}); total {sum(sizes.values()) / 1e6:.2f} MB')
    print(f'  index.json {sizes["index.json"] / 1e6:.3f} MB | summary.json {sizes.get("summary.json", 0) / 1e6:.3f} MB | '
          f'largest item {big} {items_sz[big] / 1e6:.3f} MB | items total {sum(items_sz.values()) / 1e6:.2f} MB')
    over = [k for k, v in items_sz.items() if v >= 2e6]
    print('  item files >= 2 MB:', over or 'none', '| index < 4 MB:', sizes['index.json'] < 4e6)
    index = json.loads((D / 'index.json').read_text())
    meta, items, cells = index['meta'], index['items'], index['cells']
    sids = [s['id'] for s in meta['settings']]
    print('META', {k: v for k, v in meta.items() if k not in ('notes', 'settings')})
    # ---------------------------------------------------------------- index checks
    keys = [c['k'] for c in cells]
    assert len(set(keys)) == len(keys), 'duplicate cell keys'
    assert all(KEY_RE.match(k) for k in keys), 'unsafe cell key'
    print(f'INDEX cells {len(cells)} (expect 5,615) | items {len(items)} (expect 149) | unique safe keys OK')
    if not args.partial:
        assert len(cells) == 5615 and len(items) == 149
        assert collections.Counter(c['L'] for c in cells) == {L: 1123 for L in meta['layers']}
    code_names = meta['label_codes']
    for j, sid in enumerate(sids):
        cnt = collections.Counter(code_names[c['s'][j]['c']] for c in cells)
        got = (cnt['hallucinated'], cnt['consistent'], cnt['off_topic'], cnt['generic'], cnt['empty'])
        ok = got == EXPECTED[sid]
        print(f'  labels {sid:24s} hall/cons/off/gen/empty = {got}  expected {EXPECTED[sid]}  {"MATCH" if ok else "DIFF"}')
        if not args.partial:
            assert ok
    if meta['reference']['available']:
        cnt = collections.Counter(code_names[c['r']] for c in cells)
        print(f'  labels reference raw_n1-n1     hall/cons/off/gen/empty = '
              f'{(cnt["hallucinated"], cnt["consistent"], cnt["off_topic"], cnt["generic"], cnt["empty"])}')
    split_n = collections.Counter(items[c['i']]['split'] for c in cells)
    print('  cells per split', dict(split_n))
    # ---------------------------------------------------------------- slim atoms for bullet text check
    atoms = {}
    with open(SLIM) as fh:
        for line in fh:
            r = json.loads(line)
            k = f'{r["item_id"]}.L{r["layer"]}.p{r["position"]}'
            atoms[k] = {sid: (r['settings'][sid]['text'], [a['scored_text'] for a in r['settings'][sid]['atoms']],
                              [a['truncated'] for a in r['settings'][sid]['atoms']], r['settings'][sid]['fve'])
                        for sid in sids}
    # ---------------------------------------------------------------- item files
    st = collections.Counter()
    bl_counts = {sid: collections.Counter() for sid in sids}
    by_item = collections.defaultdict(list)
    for c in cells:
        by_item[items[c['i']]['id']].append(c)
    loaded = {}
    for iid, cs in by_item.items():
        d = json.loads((D / 'items' / f'{iid}.json').read_text())
        loaded[iid] = d
        it = d['item']
        assert it['id'] == iid and it['split'] == items[cs[0]['i']]['split']
        resp = it['response']
        for s in it['sites']:
            assert s16(resp, 0, s['char']).endswith(s['token']), (iid, s)
            st['sites_ok'] += 1
        assert set(d['cells']) == {c['k'] for c in cs}
        for c in cs:
            rec = d['cells'][c['k']]
            assert s16(resp, 0, rec['char']).endswith(c['st'])
            for j, sid in enumerate(sids):
                r = rec['settings'][sid]
                text, scored, trunc, fve = atoms[c['k']][sid]
                assert r['text'] == text
                comp = c['s'][j]
                n16 = len16(text)
                assert comp['n'] == len(r['bullets']) == len(scored)
                assert comp['f'] == r['fve'] and abs(r['fve'] - fve) < 6e-6
                assert comp['bl'] == [b['label'] for b in r['bullets']]
                assert comp['c'] == code_names.index(r['label'] or 'empty')
                for b, sc, tr in zip(r['bullets'], scored, trunc):
                    assert 0 <= b['start'] < b['end'] <= n16 and b['start'] < b['scored_end'] <= b['end']
                    assert s16(text, b['start'], b['end']) == sc, (c['k'], sid)
                    assert s16(text, b['start'] - 2, b['start']) == '- '
                    assert (b['scored_end'] < b['end']) == tr == b['truncated'], (c['k'], sid)
                    s16(text, b['start'], b['scored_end'])   # boundary must not cut a surrogate pair
                    st['bullets_ok'] += 1
                    st['bullets_truncated'] += tr
                    bl_counts[sid][b['label']] += 1
                # spans: every located offset slice matches the span (exactly or normalised)
                nw = no = 0
                for sp in r['spans']:
                    if sp['verified']:
                        nw += sp['type'] == 'wrong'
                        no += sp['type'] == 'off_topic'
                    if not sp['offsets']:
                        st[f'span_unlocated_{"verified" if sp["verified"] else "unverified"}'] += 1
                    for a, e in sp['offsets']:
                        sl = s16(text, a, e)
                        if sl == sp['text']:
                            st['span_occ_exact'] += 1
                        else:
                            assert normalize_ws(sl) == normalize_ws(sp['text']), (c['k'], sid, sl, sp['text'])
                            st['span_occ_normalised'] += 1
                    want = sorted({k for a, e in sp['offsets'] for k, b in enumerate(r['bullets'])
                                   if a < b['end'] and e > b['start']})
                    assert sp['bullets'] == want
                    st['spans_in_unscored'] += sp['in_unscored'] and sp['verified']
                assert (comp['w'], comp['o']) == (nw, no)
                for cl in r['claims']:
                    for a, e in cl['offsets']:
                        sl = s16(text, a, e)
                        assert sl == cl['quote'] or normalize_ws(sl) == normalize_ws(cl['quote'])
                        st['claim_occ_ok'] += 1
                    if not cl['offsets']:
                        st[f'claim_unlocated_{cl["counted_as"]}'] += 1
                # bullet labels re-derived from the written UTF-16 offsets
                for b in r['bullets']:
                    def hit(kind):
                        return any(sp['verified'] and sp['type'] == kind and a < b['end'] and e > b['start']
                                   for sp in r['spans'] for a, e in sp['offsets'])
                    want = ('w' if hit('wrong') else 'o' if hit('off_topic') else 'c') \
                        if r['label'] in ('hallucinated', 'consistent', 'off_topic') else 'x'
                    assert b['label'] == want
                if meta.get('metrics_available'):
                    for f, name in (('sh', 'shap'), ('ss', 'shap_share'), ('so', 'solo'), ('dr', 'drop')):
                        assert comp[f] == [None if b[name] is None else (round(b[name], 4) or 0.0) for b in r['bullets']] \
                            or all(abs(x - y) <= 1.5e-4 for x, y in zip(comp[f], [b[name] for b in r['bullets']])), (c['k'], sid, f)
                    if r['bullets']:
                        tot = sum(b['shap'] for b in r['bullets'])
                        assert abs(tot - r['fve_recomputed']) < 1e-4, (c['k'], sid, tot, r['fve_recomputed'])
                        assert abs(r['fve_recomputed'] - r['fve']) < 1e-5
                        assert all(b['solo'] >= -1e-9 and b['drop'] >= -1e-6 and b['shap'] >= -1e-9 for b in r['bullets'])
                        st['readouts_metrics_ok'] += 1
                if sid == 'best_n_exact-n32':
                    tr = r['trace']
                    assert len(tr['scores']) == 32
                    if tr['chosen_sample'] is not None:
                        assert tr['scores'][tr['chosen_sample']] == r['fve']
                        assert all(b['sample_index'] == tr['chosen_sample'] for b in r['bullets'])
            if meta['reference']['available']:
                ref = rec['settings'][meta['reference']['id']]
                assert c['r'] == code_names.index(ref['label'] or 'empty')
                for sp in ref['spans']:
                    for a, e in sp['offsets']:
                        sl = s16(ref['text'], a, e)
                        assert sl == sp['text'] or normalize_ws(sl) == normalize_ws(sp['text'])
                        st['ref_span_occ_ok'] += 1
    print('ITEM CHECKS', dict(sorted(st.items())))
    for sid in sids:
        print(f'  bullet labels {sid:24s}', {k: bl_counts[sid][k] for k in 'wocx'}, 'total', sum(bl_counts[sid].values()))
    # ---------------------------------------------------------------- heat
    if heat_sz:
        hs = collections.Counter()
        for name in heat_sz:
            iid = Path(name).stem
            h = json.loads((D / name).read_text())
            for k, per_set in h.items():
                rec = loaded[iid]['cells'][k]
                for sid, per in per_set.items():
                    r = rec['settings'][sid]
                    assert len(per) == len(r['bullets'])
                    for b, x in zip(r['bullets'], per):
                        if x is None:
                            hs['null'] += 1
                            continue
                        assert x['ends'][-1] <= b['scored_end'] and x['ends'][0] > b['start']
                        prev = b['start']
                        for e in x['ends']:
                            s16(r['text'], prev, e)
                            prev = e
                        hs['bullets'] += 1
        print('HEAT', dict(hs))
    # ---------------------------------------------------------------- examples
    ex = args.examples
    if ex is None:   # one per split, each showing a different pitfall
        def want(sp, c, d):
            ss = [d['settings'][s] for s in sids]
            if not any(code_names[x['c']] == 'hallucinated' for x in c['s']):
                return False
            if sp == 'development':   # a span located only after normalisation (case / quotes / spaces)
                return any(o and s16(r['text'], *o) != x['text'] for r in ss for x in r['spans'] for o in x['offsets'])
            if sp == 'validation':    # truncated bullet + emoji before it (UTF-16 offsets differ from code points)
                return any(b['truncated'] and len16(s16(r['text'], 0, b['start'])) != len(s16(r['text'], 0, b['start']))
                           for r in ss for b in r['bullets'])
            return any(x['verified'] and len(x['bullets']) > 1 for r in ss for x in r['spans'])  # span in 2+ bullets
        ex = []
        for sp in meta['splits']:
            for c in cells:
                if items[c['i']]['split'] == sp and want(sp, c, loaded[items[c['i']]['id']]['cells'][c['k']]):
                    ex.append(c['k'])
                    break
    for k in ex:
        c = next(x for x in cells if x['k'] == k)
        d = loaded[items[c['i']]['id']]
        rec = d['cells'][k]
        resp = d['item']['response']
        before, after = s16(resp, 0, rec['char']), s16(resp, rec['char'], len16(resp))
        print('\n' + '#' * 110)
        print(f'EXAMPLE {k}  split={d["item"]["split"]}  site_kind={rec["site_kind"]}  token={c["st"]!r}')
        print('PROMPT:', d['item']['prompt'][:200].replace('\n', ' / '))
        print('CONTEXT: ...' + before[-200:].replace('\n', '⏎') + ' ⟦READ⟧ ' + after[:160].replace('\n', '⏎') + '...')
        for sid in sids + ([meta['reference']['id']] if meta['reference']['available'] else []):
            r = rec['settings'][sid]
            print(f'\n  == {sid}: label={r["label"]} fve={r.get("fve")} fve_recomputed={r.get("fve_recomputed")}')
            if sid not in sids:
                print('     text:', r['text'][:300].replace('\n', '⏎'))
            for j, b in enumerate(r.get('bullets', [])):
                body = s16(r['text'], b['start'], b['scored_end'])
                tail = s16(r['text'], b['scored_end'], b['end'])
                print(f'     [{j}] {b["label"]} sample={b["sample_index"]} coef={b["coef"]} dup={b["dup"]} '
                      f'shap={b["shap"]} | {body!r}' + (f' ‖UNSCORED‖ {tail!r}' if tail else ''))
            for sp in r['spans']:
                occ = [(a, e, s16(r['text'], a, e)) for a, e in sp['offsets']]
                print(f'     SPAN {sp["type"]:9s} verified={sp["verified"]} bullets={sp.get("bullets")} '
                      f'in_unscored={sp.get("in_unscored")} {sp["text"]!r}')
                for a, e, sl in occ:
                    print(f'          @[{a},{e}] slice={sl!r} exact={sl == sp["text"]} '
                          f'normalised_equal={normalize_ws(sl) == normalize_ws(sp["text"])}')
                print(f'          why: {sp["why"]}')
            tally = r.get('claim_tally')
            print(f'     claims {len(r["claims"])} tally={tally}')
            if sid == 'best_n_exact-n32':
                print(f'     trace chosen_sample={r["trace"]["chosen_sample"]} scores[:6]={r["trace"]["scores"][:6]}')
    print('\nVALIDATION PASSED')


if __name__ == '__main__':
    main()
