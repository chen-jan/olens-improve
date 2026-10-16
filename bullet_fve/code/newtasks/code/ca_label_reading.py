"""CA LLM bullet labels (nt-ca-bullet-v1) vs the free lexicon labels (ca_lexicon): agreement over all
labelled bullets, plus a seeded reading sample of 25 bullets per main LLM label
(gold / contrast / other_wrong / frame_only) for manual precision reading.

Join key: (item_id, stripped bullet text). The LLM unit is the distinct stripped text per cell; the
same text can recur in other cells of the same item, so agreement is reported per (cell, bullet)
occurrence (as labelled) and per distinct (item, text).

Outputs: data/labels/ca_llm_vs_lex_agreement.json, data/labels/ca_llm_reading_sample.jsonl
CLI: ca_label_reading.py [--per-label 25] [--seed 20261016] [--show]
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()

LABELS = ('gold', 'contrast', 'mixed', 'other_wrong', 'frame_only', 'none')
MAIN = ('gold', 'contrast', 'other_wrong', 'frame_only')
GROUP = {'gold': 'right', 'contrast': 'wrong', 'other_wrong': 'wrong', 'frame_only': 'frame', 'none': 'none',
         'mixed': 'mixed'}


def cohen_kappa(pairs, cats):
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs)
    cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else None


def table(pairs, cats):
    m = {a: {b: 0 for b in cats} for a in cats}
    for a, b in pairs:
        m[a][b] += 1
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--llm', default=str(C.DATA / 'judge/ca_labels/ca_llm_bullet_labels.jsonl'))
    ap.add_argument('--lex', default=str(C.DATA / 'labels/ca_lex_text_labels.jsonl'))
    ap.add_argument('--out', default=str(C.DATA / 'labels'))
    ap.add_argument('--per-label', type=int, default=25)
    ap.add_argument('--seed', type=int, default=20261016)
    ap.add_argument('--show', action='store_true')
    args = ap.parse_args()
    bank = C.load_bank('conjunctive_association')
    lex = {}
    for r in C.read_jsonl(args.lex):
        lex.setdefault((r['item_id'], r['text'].strip()), r)
    llm = list(C.read_jsonl(args.llm))
    occ_pairs, uniq, missing = [], {}, 0
    for r in llm:
        lx = lex.get((r['item_id'], r['text']))
        if lx is None:
            missing += 1
            continue
        r['lex'] = lx
        occ_pairs.append((r['label'], lx['label']))
        uniq.setdefault((r['item_id'], r['text']), []).append(r)
    # distinct (item, text): LLM label consistency across cells, then first label vs lexicon
    inconsistent = sum(len({x['label'] for x in v}) > 1 for v in uniq.values())
    uniq_pairs = [(v[0]['label'], v[0]['lex']['label']) for v in uniq.values()]
    g = lambda ps: [(GROUP[a], GROUP[b]) for a, b in ps]  # noqa: E731
    w3 = lambda ps: [(a if a in ('gold', 'contrast') else 'other', b if b in ('gold', 'contrast') else 'other')  # noqa: E731
                     for a, b in ps]
    gcats = ('right', 'wrong', 'frame', 'mixed', 'none')
    out = {'n_llm_rows': len(llm), 'n_joined': len(occ_pairs), 'n_missing_lex': missing,
           'n_distinct_item_text': len(uniq), 'distinct_with_inconsistent_llm_label': inconsistent,
           'llm_label_counts': dict(collections.Counter(a for a, _ in occ_pairs)),
           'lex_label_counts': dict(collections.Counter(b for _, b in occ_pairs)),
           'occurrence': {'agree_6way': sum(a == b for a, b in occ_pairs) / len(occ_pairs),
                          'kappa_6way': cohen_kappa(occ_pairs, LABELS),
                          'agree_group': sum(a == b for a, b in g(occ_pairs)) / len(occ_pairs),
                          'kappa_group': cohen_kappa(g(occ_pairs), gcats),
                          'agree_3way': sum(a == b for a, b in w3(occ_pairs)) / len(occ_pairs),
                          'kappa_3way': cohen_kappa(w3(occ_pairs), ('gold', 'contrast', 'other')),
                          'confusion_llm_rows_lex_cols': table(occ_pairs, LABELS)},
           'distinct': {'agree_6way': sum(a == b for a, b in uniq_pairs) / len(uniq_pairs),
                        'kappa_6way': cohen_kappa(uniq_pairs, LABELS),
                        'confusion_llm_rows_lex_cols': table(uniq_pairs, LABELS)}}
    # per-label precision / recall of LLM against lexicon (lexicon as reference, occurrence level)
    pr = {}
    for c in LABELS:
        tp = sum(a == c and b == c for a, b in occ_pairs)
        pa = sum(a == c for a, _ in occ_pairs)
        pb = sum(b == c for _, b in occ_pairs)
        pr[c] = {'llm_n': pa, 'lex_n': pb, 'both': tp, 'share_of_llm_that_lex_agrees': tp / pa if pa else None,
                 'share_of_lex_that_llm_agrees': tp / pb if pb else None}
    out['per_label'] = pr
    # by contrast axis
    by_axis = collections.defaultdict(list)
    for v in uniq.values():
        by_axis[bank[v[0]['item_id']]['contrast_axis']].append((v[0]['label'], v[0]['lex']['label']))
    out['by_contrast_axis_distinct'] = {ax: {'n': len(ps), 'agree_6way': sum(a == b for a, b in ps) / len(ps),
                                             'llm_gold': sum(a == 'gold' for a, _ in ps),
                                             'lex_gold': sum(b == 'gold' for _, b in ps),
                                             'both_gold': sum(a == b == 'gold' for a, b in ps)}
                                        for ax, ps in sorted(by_axis.items())}
    # reading sample: distinct (item, text), stratified by LLM label, spread over item clusters
    rng = random.Random(args.seed)
    sample = []
    for lab in MAIN:
        pool = [v[0] for v in uniq.values() if v[0]['label'] == lab]
        rng.shuffle(pool)
        seen_items, picked = collections.Counter(), []
        for cap in (1, 2, 3, 99):  # at most one per item first, then relax
            for r in pool:
                if len(picked) >= args.per_label:
                    break
                if r in picked or seen_items[r['item_id']] >= cap:
                    continue
                picked.append(r)
                seen_items[r['item_id']] += 1
        for r in picked:
            it = bank[r['item_id']]
            sample.append({'llm_label': lab, 'cell_id': r['cell_id'], 'item_id': r['item_id'],
                           'bullet_index': r['bullet_index'], 'contrast_axis': it['contrast_axis'],
                           'gold_label': it['gold_label'], 'contrast_label': it['contrast_label'],
                           'differs': r['differs'], 'shared': r['shared'], 'conflicts': r['conflicts'],
                           'quote': r['quote'], 'lex_label': r['lex']['label'], 'lex_matches': r['lex']['matches'],
                           'text': r['text']})
    out['reading_sample'] = {'n': len(sample), 'per_label': args.per_label, 'seed': args.seed,
                             'lex_label_by_llm_label': {lab: dict(collections.Counter(s['lex_label'] for s in sample
                                                                                       if s['llm_label'] == lab))
                                                        for lab in MAIN}}
    Path(args.out).mkdir(parents=True, exist_ok=True)
    C.atomic_json(Path(args.out) / 'ca_llm_vs_lex_agreement.json', out)
    C.atomic_text(Path(args.out) / 'ca_llm_reading_sample.jsonl',
                  ''.join(json.dumps(s, ensure_ascii=False) + '\n' for s in sample))
    print(json.dumps({k: v for k, v in out.items() if k not in ('distinct',)}, indent=1))
    if args.show:
        for i, s in enumerate(sample):
            print(f"\n#{i:03d} LLM={s['llm_label']} LEX={s['lex_label']} axis={s['contrast_axis']} {s['cell_id']} b{s['bullet_index']}")
            print(f"  GOLD: {s['gold_label']}\n  CONTRAST: {s['contrast_label']}")
            print(f"  differs={s['differs']} shared={s['shared']} conflicts={s['conflicts']} quote={s['quote']!r}")
            print(f"  lex={json.dumps(s['lex_matches'], ensure_ascii=False)}")
            print(f"  TEXT: {s['text']!r}")


if __name__ == '__main__':
    main()
