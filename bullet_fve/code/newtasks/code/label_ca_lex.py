"""Conjunctive-association bullet labels from the bank's regex lexicons (ca_lexicon.ItemLexicon; free, no API)
for every SELECTED bullet (3 settings) and every POOL bullet. Mirrors label_um.py's outputs.

Inputs : data/select/ca_three_settings.jsonl, data/select/ca_pool.jsonl (select3.py merge)
Outputs: data/labels/ca_lex_text_labels.jsonl   one row per distinct (item_id, bullet text): label + matched words
         data/labels/ca_lex_bullet_labels.jsonl  one row per occurrence (cell, source = setting|pool, phrase_id)
         data/labels/ca_lex_label_summary.json   counts by source x label / group, by layer, readout- and pool-level
Labels (ca_lexicon.py): gold | contrast | mixed | other_wrong | frame_only | none;
groups: right = gold, wrong = contrast|other_wrong, frame = frame_only, mixed, none.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
import ca_lexicon as LX  # noqa: E402

LABELS = ('gold', 'contrast', 'mixed', 'other_wrong', 'frame_only', 'none')


def text_key(item_id, text):
    return hashlib.sha256(f'{item_id}\x00{text}'.encode()).hexdigest()[:20]


def surfaces(lex: LX.ItemLexicon, text: str) -> dict:
    """Matched words (for reading only; the label itself comes from ItemLexicon.label)."""
    out = {'credit': {}, 'competitors': {}}
    for ax, groups in lex.credit.items():
        hits = [m.group(0) for g in groups if g for m in [g.search(text)] if m]
        if hits:
            out['credit'][ax] = hits
    for ax, rx in lex.competitors.items():
        hits = sorted({m.group(0) for m in rx.finditer(text)}) if rx else []
        if hits:
            out['competitors'][ax] = hits
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--three-settings', default=str(C.DATA / 'select/ca_three_settings.jsonl'))
    ap.add_argument('--pool', default=str(C.DATA / 'select/ca_pool.jsonl'))
    ap.add_argument('--out', default=str(C.DATA / 'labels'))
    args = ap.parse_args()
    bank = C.load_bank('conjunctive_association')
    lex = {}
    unique, occ = {}, []

    def lab(item_id, text):
        k = text_key(item_id, text)
        if k not in unique:
            L = lex.setdefault(item_id, LX.ItemLexicon(bank[item_id]))
            unique[k] = {'key': k, 'item_id': item_id, 'contrast_axis': L.axis, 'text': text,
                         **L.label(text), 'matches': surfaces(L, text)}
        return k, unique[k]

    three = list(C.read_jsonl(args.three_settings))
    meta = {r['cell_id']: r for r in three}
    for row in three:
        for sid in C.SETTINGS:
            s = row['settings'][sid]
            for i, a in enumerate(s['atoms']):
                k, r = lab(row['item_id'], a['text'])
                occ.append({'cell_id': row['cell_id'], 'item_id': row['item_id'], 'group_id': row['group_id'],
                            'layer': row['layer'], 'position': row['position'], 'source': sid, 'index': i,
                            'phrase_id': a['source_phrase_id'], 'sample_index': a['sample_index'], 'key': k,
                            'label': r['label'], 'group': r['group'], 'scored': s['fve'] is not None})
    n_pool = 0
    for pe in C.read_jsonl(args.pool):
        row = meta[pe['cell_id']]
        for b in pe['bullets']:
            k, r = lab(row['item_id'], b['text'])
            occ.append({'cell_id': pe['cell_id'], 'item_id': row['item_id'], 'group_id': row['group_id'],
                        'layer': row['layer'], 'position': row['position'], 'source': 'pool',
                        'sample_index': b['sample_index'], 'pos': b['pos'], 'phrase_id': b['phrase_id'], 'key': k,
                        'label': r['label'], 'group': r['group'], 'solo_fve': b['solo_fve']})
            n_pool += 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'ca_lex_text_labels.jsonl', 'w') as f:
        for k in sorted(unique):
            f.write(json.dumps(unique[k], ensure_ascii=False) + '\n')
    with open(out / 'ca_lex_bullet_labels.jsonl', 'w') as f:
        for o in occ:
            f.write(json.dumps(o, ensure_ascii=False) + '\n')

    by_source = collections.defaultdict(collections.Counter)
    by_source_group = collections.defaultdict(collections.Counter)
    by_layer = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    by_axis = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    readout_any = collections.defaultdict(collections.Counter)  # source -> label -> readouts with >=1 such bullet
    cell_labels = collections.defaultdict(lambda: collections.defaultdict(set))
    for o in occ:
        by_source[o['source']][o['label']] += 1
        by_source_group[o['source']][o['group']] += 1
        by_layer[o['source']][o['layer']][o['label']] += 1
        by_axis[o['source']][unique[o['key']]['contrast_axis']][o['label']] += 1
        cell_labels[o['cell_id']][o['source']].add(o['label'])
    for cid, d in cell_labels.items():
        for src, labs in d.items():
            for lb in labs:
                readout_any[src][lb] += 1
    # selection effect preview: cells where the pool holds a gold bullet but the setting has none
    pool_gold_missed = collections.Counter()
    for cid, d in cell_labels.items():
        if 'gold' in d.get('pool', set()):
            pool_gold_missed['pool_has_gold'] += 1
            for sid in C.SETTINGS:
                pool_gold_missed[f'missed[{sid}]'] += 'gold' not in d.get(sid, set())
    summary = {'cells': len(three), 'distinct_texts': len(unique), 'occurrences': len(occ), 'pool_bullets': n_pool,
               'labels': list(LABELS),
               'by_source': {k: {lb: v.get(lb, 0) for lb in LABELS} for k, v in by_source.items()},
               'by_source_group': {k: dict(v) for k, v in by_source_group.items()},
               'readouts_with_label': {k: {lb: v.get(lb, 0) for lb in LABELS} for k, v in readout_any.items()},
               'pool_gold_missed': dict(pool_gold_missed),
               'by_source_layer': {k: {str(L): {lb: c.get(lb, 0) for lb in LABELS} for L, c in sorted(v.items())}
                                   for k, v in by_layer.items()},
               'by_source_contrast_axis': {k: {ax: {lb: c.get(lb, 0) for lb in LABELS} for ax, c in sorted(v.items())}
                                           for k, v in by_axis.items()},
               'lexicon_sha256': C.file_sha(LX.__file__), 'bank_items': len(bank)}
    C.atomic_json(out / 'ca_lex_label_summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('cells', 'distinct_texts', 'occurrences', 'pool_bullets', 'by_source',
                                              'readouts_with_label', 'pool_gold_missed')}, indent=1))


if __name__ == '__main__':
    main()
