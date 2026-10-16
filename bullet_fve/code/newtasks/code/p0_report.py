"""P0 pilot: per-site evidence for the drop-only rule (DESIGN.md section 2.5), after judge_um.py --stage p0.

Rule (fixed in advance): a PLANNED UM template site is dropped iff it has 0 gold picks over its 80
readouts (10 items x 2 layers x 4 samples) AND >= 75% of them describe only chat formatting / turn
structure. The second half is decided by READING: this script writes every readout per site to
data/judge/um/p0/p0_reading.jsonl (with lexicon labels as a hint) and the per-site counts.
It never adds or swaps sites. Apply a decision with: build_manifests.py --only-gen --um-drop-role ROLE.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()


def main():
    import generate_samples as G
    import gen_worker as GW
    import label_um
    import um_lexicon as L
    man, cells, config, pool_id = GW.load_stage('p0')
    _, n, count = C.STAGES['p0']
    state = {}
    for i in range(count):
        state.update(G.read_journal(GW.shard_paths('p0', i, count)[0], pool_id))
    judge_path = C.DATA / 'judge/um/p0/p0/um_cell_rows.jsonl'
    verdicts = {}
    if judge_path.exists():
        for r in C.read_jsonl(judge_path):
            verdicts[(r['cell_id'], r['sample_idx'])] = r
    ctx = label_um.contexts()
    per_site = collections.defaultdict(lambda: collections.Counter())
    reading = []
    for c in cells:
        key = (c['tier'] or '-', c['role'])
        it = ctx[c['item_id']]
        for k in range(n):
            text = state[c['cell_id']][k]['text']
            v = verdicts.get((c['cell_id'], k))
            labs = [L.label_bullet(b.strip(), it['cls'], it['gold'], it['distractors'], it['prompt'])['label']
                    for b in text.split('\n- ') if b.strip()]
            s = per_site[key]
            s['readouts'] += 1
            s['judged'] += v is not None
            s['gold'] += bool(v and v['pick'] == 'gold')
            s['gold_inferred'] += bool(v and v['pick'] == 'gold' and v['basis'] == 'inferred_characterization')
            s['distractor'] += bool(v and v['pick'] == 'distractor')
            s['lexicon_any_value'] += any(x in ('gold_exact', 'gold_coarse', 'wrong_value', 'mixed') for x in labs)
            reading.append({'site': f'{key[0]}|{key[1]}', 'rel_from_end': c['rel_from_end'], 'token': c['token'],
                            'cell_id': c['cell_id'], 'sample_index': k, 'text': text,
                            'judge_pick': v and v['pick'], 'judge_basis': v and v['basis'],
                            'lexicon_labels': labs, 'reader_formatting_only': None})
    out = C.DATA / 'judge/um/p0'
    out.mkdir(parents=True, exist_ok=True)
    reading.sort(key=lambda r: (r['rel_from_end'], r['cell_id'], r['sample_index']))
    C.atomic_text(out / 'p0_reading.jsonl', ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in reading))
    table = {f'{t}|{r}': dict(s) for (t, r), s in sorted(per_site.items(), key=lambda kv: str(kv[0]))}
    candidates = [k for k, s in table.items() if not k.startswith('-') and s['gold'] == 0]
    summary = {'sites': table, 'planned_sites_with_zero_gold': candidates,
               'note': 'drop only if ALSO >=75% formatting-only by reading p0_reading.jsonl'}
    C.atomic_json(out / 'p0_sites.json', summary)
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
