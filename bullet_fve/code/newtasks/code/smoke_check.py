"""Smoke checks (CPU) after the GPU smoke run: throughput, readout sanity, independent FVE recompute,
bullet labels (UM string match; CA bank lexicon). Run with NT_DATA = smoke root and NT_STAGES.

  python -B smoke_check.py throughput   generation / AR rates from the journals, ar_done and worker logs
  python -B smoke_check.py readouts     finish reasons, token counts, examples (N=32 stages)
  python -B smoke_check.py fve          scipy NNLS recompute of every saved selection FVE (independent of JointNNLS)
  python -B smoke_check.py labels       UM label summary (after label_um.py) + CA lexicon labels + examples
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()


def journal_events(stage):
    fam, n, count = C.STAGES[stage]
    for i in range(count):
        p = C.stage_dir(stage) / f'shard-{i:03d}-of-{count:03d}.jsonl'
        if p.exists():
            for line in p.read_text().splitlines():
                if line.endswith('}'):
                    yield json.loads(line)


def throughput():
    out = {}
    for stage in C.STAGES:
        evs = [e for e in journal_events(stage) if e.get('kind') == 'generation']
        if not evs:
            continue
        batches = [{'cells': len(e['cell_order']), 'k': e['samples_per_cell'], 'seqs': e['batch_sequence_count'],
                    'seconds': round(e['seconds'], 2), 'width': e['generation'].get('padded_batch_width'),
                    'gen_tokens': sum(e['generation']['token_counts'])} for e in evs]
        cells = sum(b['cells'] for b in batches)
        secs = sum(b['seconds'] for b in batches)
        full = [b for b in batches if b['seqs'] == 256]
        out[stage] = {'batches': batches, 'cells': cells, 'seconds': round(secs, 1),
                      's_per_cell_all': round(secs / cells, 3),
                      's_per_cell_full_256_batches': round(sum(b['seconds'] for b in full) / sum(b['cells'] for b in full), 3) if full else None,
                      'readouts_per_s': round(sum(b['seqs'] for b in batches) / secs, 2),
                      'gen_tokens_per_s': round(sum(b['gen_tokens'] for b in batches) / secs, 1)}
    ar = []
    done = C.DATA / 'vectors/ar_done.jsonl'
    if done.exists():
        for r in C.read_jsonl(done):
            j = Path(r['journal'])
            stage = j.parent.name
            cells = len({rec['cell_id'] for e in journal_events(stage) if e.get('kind') == 'generation'
                         for rec in e['records']})
            ar.append({'stage': stage, 'new_vectors': r['new_vectors'], 'seconds': round(r['seconds'], 1), 'cells': cells,
                       's_per_cell': round(r['seconds'] / cells, 3) if cells else None,
                       'vectors_per_s': round(r['new_vectors'] / r['seconds'], 1) if r['new_vectors'] else None})
    out['ar'] = ar
    logs = {}
    for p in sorted((C.DATA / 'logs').glob('worker-*.log')):
        for line in p.read_text().splitlines():
            if 'lens loaded' in line or 'AR done' in line or line.split('] ', 1)[-1].startswith(('start', 'capture:', 'exit')):
                logs.setdefault(p.name, []).append(line[:400])
    out['log_lines'] = logs
    print(json.dumps(out, indent=1))


def readouts():
    for stage in ('ca', 'umA', 'umB'):
        recs = [r for e in journal_events(stage) if e.get('kind') == 'generation' for r in e['records']]
        if not recs:
            continue
        fin = collections.Counter(r['finish_reason'] for r in recs)
        tc = [r['token_count'] for r in recs]
        per_cell = collections.Counter(r['cell_id'] for r in recs)
        dash = sum(r['text'].lstrip().startswith('-') for r in recs)
        print(json.dumps({'stage': stage, 'records': len(recs), 'cells': len(per_cell),
                          'samples_per_cell': sorted(set(per_cell.values())), 'finish': dict(fin),
                          'truncated': sum(r['truncated'] for r in recs), 'token_count_mean': round(sum(tc) / len(tc), 1),
                          'token_count_max': max(tc), 'starts_with_dash': dash,
                          'distinct_texts': len({r['text'] for r in recs})}))


def fve():
    import numpy as np
    import torch
    from scipy.optimize import nnls
    from olens_improve.reconstruction import Whitener
    from select3 import rows_memmap
    acts = rows_memmap(str(C.DATA / 'capture/activations.safetensors'), 'resid')
    worst = {}
    n = collections.Counter()
    whit = {}
    for fam in ('um', 'ca'):
        p = C.DATA / f'select/{fam}_three_settings.jsonl'
        if not p.exists():
            continue
        vindex = json.loads((C.DATA / f'select/{fam}_vector_index.json').read_text())[C.SPLIT]
        for row in C.read_jsonl(p):
            L = row['layer']
            if L not in whit:
                whit[L] = Whitener.load(str(C.WHITENERS / f'whitening_iolens_pooled_L{L}.safetensors'))
            w = whit[L]
            t = w.whiten(torch.from_numpy(np.array(acts[row['activation_row']])).reshape(1, -1))[0].double().numpy()
            for sid, s in row['settings'].items():
                if s['fve'] is None:
                    n[f'{fam}:unscored'] += 1
                    continue
                keys = [a['cache_key'] for a in s['atoms']]
                if not keys:
                    got = 0.0
                else:
                    raw = []
                    for k in keys:
                        path, r = vindex[k]
                        raw.append(np.array(rows_memmap(path, 'vectors')[r]))
                    v = w.whiten(torch.from_numpy(np.stack(raw)))
                    v = (v / (v.norm(dim=1, keepdim=True) + 1e-9)).double().numpy()
                    x, _ = nnls(v.T, t)
                    resid = t - v.T @ x
                    got = 1 - float(resid @ resid) / float(t @ t)
                d = abs(got - s['fve'])
                key = f'{fam}:{sid}'
                worst[key] = max(worst.get(key, 0.0), d)
                n[key] += 1
    print(json.dumps({'fits_checked': dict(n), 'max_abs_scipy_minus_saved': worst}, indent=1))


def labels():
    from ca_lexicon import ItemLexicon
    um_sum = C.DATA / 'labels/um_label_summary.json'
    if um_sum.exists():
        print('UM label summary:', um_sum.read_text())
        occ = list(C.read_jsonl(C.DATA / 'labels/um_bullet_labels.jsonl'))
        uniq = {r['key']: r for r in C.read_jsonl(C.DATA / 'labels/um_text_labels.jsonl')}
        shown = collections.Counter()
        for o in occ:
            if o['source'] == 'pool' or shown[o['label']] >= 4:
                continue
            shown[o['label']] += 1
            u = uniq[o['key']]
            print(f"  UM {o['label']:<11} {o['subtype'] or '':<11} in_prompt={o['in_prompt']!s:<5} {o['cell_id']} [{o['source']}]"
                  f" gold_hits={[h['surface'] for h in u['gold_hits']]} wrong={[h['surface'] for h in u['wrong_hits']]}"
                  f" frames={[h['surface'] for h in u['frames']]} :: {u['text'][:160]!r}")
    p = C.DATA / 'select/ca_three_settings.jsonl'
    if p.exists():
        bank = C.load_bank('conjunctive_association')
        lex = {}
        cnt = collections.defaultdict(collections.Counter)
        shown = collections.Counter()
        for row in C.read_jsonl(p):
            L = lex.setdefault(row['item_id'], ItemLexicon(bank[row['item_id']]))
            for sid, s in row['settings'].items():
                for a in s['atoms']:
                    r = L.label(a['text'])
                    cnt[sid][r['label']] += 1
                    if shown[r['label']] < 4:
                        shown[r['label']] += 1
                        print(f"  CA {r['label']:<11} {row['cell_id']} [{sid}] axes={r['frame_axes']} :: {a['text'].strip()[:160]!r}")
        pool = C.DATA / 'select/ca_pool.jsonl'
        if pool.exists():
            for pe in C.read_jsonl(pool):
                L = lex[pe['cell_id'].split('|')[1]]
                for b in pe['bullets']:
                    cnt['pool'][L.label(b['text'])['label']] += 1
        print('CA lexicon label counts:', json.dumps({k: dict(v) for k, v in cnt.items()}, indent=1))


if __name__ == '__main__':
    {'throughput': throughput, 'readouts': readouts, 'fve': fve, 'labels': labels}[sys.argv[1]]()
