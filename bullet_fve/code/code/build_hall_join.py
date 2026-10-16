#!/usr/bin/env python3
"""Build one JSON join: items (prompt/response/sites) + cells x 3 settings (readout text, bullets,
judge label, verified wrong/off-topic spans with 'why' and raw offsets, stage-2 claims).

python -B build_hall_join.py OUT.json      (reads frozen files only; writes OUT only)
"""
import collections
import json
import sys

from hall_judge_context import (SETTINGS, judge_key, load_bank, load_judgments, load_selections,
                                marked_context, tally_claim_list, verify_quote)
from span_locate import bullet_index, bullets_with_offsets, locate


def span_records(text, bullets, spans, verified_texts):
    """Raw stage-1 spans (text/type/why) + verified flag + raw offsets + bullet indexes."""
    out = []
    for sp in spans:
        hits = locate(text, sp['text'])
        out.append({'text': sp['text'], 'type': sp.get('type'), 'why': sp.get('why'),
                    'verified': verify_quote(sp['text'], [text]),
                    'counts_as': None, 'offsets': [[s, e] for s, e, _ in hits],
                    'match': hits[0][2] if hits else None,
                    'bullets': sorted({i for s, e, _ in hits for i in bullet_index(bullets, s, e)})})
    # 'counts_as' = how results.json used it (only verified spans count; unknown type -> wrong)
    for r in out:
        if r['verified']:
            r['counts_as'] = 'off_topic' if r['type'] == 'off_topic' else 'wrong'
    assert [r['text'] for r in out if r['counts_as'] == 'wrong'] == verified_texts['wrong']
    assert [r['text'] for r in out if r['counts_as'] == 'off_topic'] == verified_texts['off_topic']
    return out


def main(out_path):
    by_id, sites = load_bank()
    sel = load_selections()
    J = {s: load_judgments(s) for s in SETTINGS}
    items = {}
    for iid, it in by_id.items():
        items[iid] = {k: it[k] for k in ('id', 'source', 'prompt', 'response', 'response_start')}
        items[iid]['sites'] = it['sites']
    cells = []
    for (iid, layer, pos), v in sorted(sel.items()):
        site = sites[(iid, pos)]
        before, after = marked_context(by_id[iid], site)
        cell = {'cell_id': v['cell_id'], 'judge_key': judge_key(iid, layer, pos), 'item_id': iid,
                'layer': layer, 'pos': pos, 'split': v['split'], 'site_kind': site['kind'],
                'site_token': site['token'], 'site_char': site['char'], 'settings': {}}
        assert before + after == by_id[iid]['response']
        for s in SETTINGS:
            res, rows, s1, s2, _ = J[s]
            text = v['text'][s]
            bullets = bullets_with_offsets(text)
            rec = {'text': text, **v['sel'][s],
                   'bullets': [{'start': a, 'end': b, 'text': t} for a, b, t in bullets]}
            row = rows.get(cell['judge_key'])
            if row is None:                       # empty selected text: never judged
                assert not text.strip()
                rec.update(label=None, judged=False)
            else:
                assert row['samples'][0] == text
                ver = row['verdict'][0]
                raw1 = s1[cell['judge_key']]['result']['samples'][0]
                raw2 = s2[cell['judge_key']]['result']['samples'][0]
                claims = tally_claim_list(raw2, text, ver['wrong'])
                for c in claims:
                    hits = locate(text, c['quote'])
                    c['offsets'] = [[a, b] for a, b, _ in hits]
                    c['bullets'] = sorted({i for a, b, _ in hits for i in bullet_index(bullets, a, b)})
                rec.update(judged=True, label=ver['class'], judge_kind=ver['kind'], revoked=ver['revoked'],
                           rationale=raw1.get('rationale'), wrong=ver['wrong'], off_topic=ver['off_topic'],
                           n_unverified_spans=ver['n_unverified'], claim_tally=ver['claims'],
                           spans=span_records(text, bullets, raw1.get('spans') or [], ver),
                           claims=claims, verify_rationale=raw2.get('rationale'))
            cell['settings'][s] = rec
        cells.append(cell)
    out = {'settings': {k: {'method': m, 'n': n, 'label': lab} for k, (m, n, lab) in SETTINGS.items()},
           'items': items, 'cells': cells}
    with open(out_path, 'w') as fh:
        json.dump(out, fh, ensure_ascii=False)
    c = collections.Counter((s, x['settings'][s]['label']) for x in cells for s in SETTINGS)
    print('cells', len(cells), dict(sorted(c.items(), key=str)))


if __name__ == '__main__':
    main(sys.argv[1])
