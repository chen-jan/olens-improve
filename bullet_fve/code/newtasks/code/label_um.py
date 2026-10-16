"""User-modelling bullet labels (string match, no API) for every selected bullet and every pool bullet.

Inputs : data/select/um_three_settings.jsonl, data/select/um_pool.jsonl (select3.py merge)
Outputs: data/labels/um_text_labels.jsonl   one row per distinct (item_id, bullet text): label + matches
         data/labels/um_bullet_labels.jsonl  one row per occurrence (cell, source = setting|pool, phrase_id)
         data/labels/um_label_summary.json   counts by source x label
         data/labels/um_reading_sample.jsonl (with --sample): stratified sample of SELECTED bullets for reading
                                              (30 each of gold_exact, gold_coarse, wrong_value, frame_only, none)
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
import um_lexicon as L  # noqa: E402

SAMPLE_LABELS = ('gold_exact', 'gold_coarse', 'wrong_value', 'frame_only', 'none')


def contexts():
    from wsbench.evals.user_modeling.judge import build_options
    bank = C.load_bank('user_modeling')
    opts = build_options(list(bank.values()))
    return {name: L.item_context(it, opts[name]) | {'subfamily': it['subfamily'], 'options': opts[name][0]}
            for name, it in bank.items()}


def text_key(item_id, text):
    return hashlib.sha256(f'{item_id}\x00{text}'.encode()).hexdigest()[:20]


def label_all(three_rows, pool_rows, ctx):
    """-> (unique: key -> label dict, occurrences: list)."""
    unique, occ = {}, []

    def lab(item_id, text):
        k = text_key(item_id, text)
        if k not in unique:
            c = ctx[item_id]
            r = L.label_bullet(text, c['cls'], c['gold'], c['distractors'], c['prompt'])
            unique[k] = {'key': k, 'item_id': item_id, 'text': text, **r}
        return k, unique[k]

    for row in three_rows:
        for sid in C.SETTINGS:
            s = row['settings'][sid]
            for a in s['atoms']:
                k, r = lab(row['item_id'], a['text'])
                occ.append({'cell_id': row['cell_id'], 'item_id': row['item_id'], 'layer': row['layer'],
                            'position': row['position'], 'source': sid, 'phrase_id': a['source_phrase_id'],
                            'sample_index': a['sample_index'], 'key': k, 'label': r['label'],
                            'subtype': r['subtype'], 'group': r['group'], 'in_prompt': r['in_prompt'],
                            'other_class': r['other_class']})
    item_of = {row['cell_id']: row['item_id'] for row in three_rows}
    for pe in pool_rows:
        item_id = item_of.get(pe['cell_id']) or pe['cell_id'].split('|')[1]
        for b in pe['bullets']:
            k, r = lab(item_id, b['text'])
            occ.append({'cell_id': pe['cell_id'], 'item_id': item_id, 'source': 'pool', 'phrase_id': b['phrase_id'],
                        'sample_index': b['sample_index'], 'pos': b['pos'], 'key': k, 'label': r['label'],
                        'subtype': r['subtype'], 'group': r['group'], 'in_prompt': r['in_prompt'],
                        'other_class': r['other_class'], 'solo_fve': b['solo_fve']})
    return unique, occ


def reading_sample(unique, occ, ctx, per_label=30, seed=C.SEED):
    """Stratified over SELECTED occurrences (not pool), one occurrence per distinct text."""
    seen, by_label = set(), collections.defaultdict(list)
    for o in occ:
        if o['source'] == 'pool' or o['key'] in seen:
            continue
        seen.add(o['key'])
        by_label[o['label']].append(o)
    rng = random.Random(seed)
    out = []
    for lab in SAMPLE_LABELS:
        rows = sorted(by_label.get(lab, []), key=lambda o: (o['cell_id'], o['source'], o['phrase_id']))
        for o in rng.sample(rows, min(per_label, len(rows))):
            u = unique[o['key']]
            c = ctx[o['item_id']]
            out.append({'label': lab, 'subtype': u['subtype'], 'cell_id': o['cell_id'], 'setting': o['source'],
                        'phrase_id': o['phrase_id'], 'bullet': u['text'], 'gold': c['gold'],
                        'distractors': c['distractors'], 'attr_class': c['cls'], 'in_prompt': u['in_prompt'],
                        'gold_hits': [h['surface'] for h in u['gold_hits']],
                        'wrong_hits': [(h['surface'], h.get('subtype')) for h in u['wrong_hits']],
                        'frames': [h['surface'] for h in u['frames']], 'prompt': c['prompt'][:300],
                        'reader_verdict': None})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--three-settings', default=str(C.DATA / 'select/um_three_settings.jsonl'))
    ap.add_argument('--pool', default=str(C.DATA / 'select/um_pool.jsonl'))
    ap.add_argument('--out', default=str(C.DATA / 'labels'))
    ap.add_argument('--sample', type=int, default=0, help='per-label reading sample size (design: 30)')
    args = ap.parse_args()
    ctx = contexts()
    three = list(C.read_jsonl(args.three_settings))
    pool = list(C.read_jsonl(args.pool)) if Path(args.pool).exists() else []
    unique, occ = label_all(three, pool, ctx)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'um_text_labels.jsonl', 'w') as f:
        for k in sorted(unique):
            f.write(json.dumps(unique[k], ensure_ascii=False) + '\n')
    with open(out / 'um_bullet_labels.jsonl', 'w') as f:
        for o in occ:
            f.write(json.dumps(o, ensure_ascii=False) + '\n')
    counts = collections.defaultdict(collections.Counter)
    for o in occ:
        counts[o['source']][o['label']] += 1
        counts[o['source']]['in_prompt'] += o['in_prompt']
    summary = {'distinct_texts': len(unique), 'occurrences': len(occ),
               'by_source': {k: dict(v) for k, v in counts.items()}, 'lexicon_sha256': C.file_sha(L.__file__)}
    C.atomic_json(out / 'um_label_summary.json', summary)
    if args.sample:
        rows = reading_sample(unique, occ, ctx, args.sample)
        with open(out / 'um_reading_sample.jsonl', 'w') as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        summary['reading_sample'] = collections.Counter(r['label'] for r in rows)
    print(json.dumps(summary, indent=1, default=dict))


if __name__ == '__main__':
    main()
