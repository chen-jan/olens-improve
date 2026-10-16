"""Select the three settings per cell with the same calls and arguments as OI compare_selectors.main.

  samples  = [parse_bullets(text, f"{pool}:{cell}:{i}", i, token_count=qwen_count, max_output_tokens=256)]
  exact    = JointNNLS(whiten(target), {phrase_id: unit(whiten(raw_AR))})            (scipy_exact)
  released = JointNNLS(..., solver='released80')                                      (recorded only)
  Original   capped_n1-n1            Selection('capped_n1', samples[0].bullets, None)
  Best of 32 best_n_exact-n32        best_of_n(samples, 32, exact.score, admissible=output_admissible & ar_scoreable)
  Combine 32 pooled_greedy_swap-n32  pool_candidates(samples, 32, vectors) -> greedy_pool(..., admissible=
                                     output_admissible, swap_passes=1, complete_samples=remapped)
compare_selectors.pool_candidates / ar_scoreable / selection_fits are imported, not copied.
Also writes the solo FVE (exact.score((phrase_id,))) of EVERY pool bullet with an AR vector.

CLI:
  select3.py run   --family um|ca [--shard-index i --shard-count k] [--cells id,...]
  select3.py merge --family um|ca      -> data/select/{fam}_three_settings.jsonl (hallucination schema),
                                          {fam}_vector_index.json, {fam}_pool.jsonl, {fam}_select_summary.json
Optional test hooks: --gen-root/--cache-dir/--capture-dir/--out (fixtures).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
import numpy as np  # noqa: E402
import torch  # noqa: E402

ATOM_KEEP = ('source_phrase_id', 'sample_index', 'text', 'scored_text', 'cache_key', 'status',
             'original_token_count', 'scored_token_count', 'truncated', 'scored_token_ids',
             'unscored_suffix_ids', 'parser_flags', 'span_start', 'span_end')
WANT = {('capped_n1', 1): 'capped_n1-n1', ('best_n_exact', 32): 'best_n_exact-n32',
        ('pooled_greedy_swap', 32): 'pooled_greedy_swap-n32'}
FAMILY_STAGES = {'ca': ('ca',), 'um': ('umA', 'umB')}


def rows_memmap(path, key):
    with open(path, 'rb') as f:
        n = int.from_bytes(f.read(8), 'little')
        header = json.loads(f.read(n))
    info = header[key]
    assert info['dtype'] == 'F32'
    start, _ = info['data_offsets']
    return np.memmap(path, dtype='<f4', mode='r', offset=8 + n + start, shape=tuple(info['shape']))


class MemmapVectorCache:
    """RawVectorCache's index (same files, same contract check) with row-wise memmap reads."""

    def __init__(self, directory):
        from olens_improve.reconstruction import RawVectorCache
        base = RawVectorCache(str(directory))
        self.contract, self.index = base.contract, base.index
        self._mm = {}

    def get(self, key):
        row = self.index[key]
        path = row['tensor_path']
        if path not in self._mm:
            self._mm[path] = rows_memmap(path, 'vectors')
        return torch.from_numpy(np.array(self._mm[path][row['row']]))


class Paths:
    def __init__(self, args):
        self.gen_root = Path(args.gen_root) if args.gen_root else C.DATA / 'gen'
        self.manifests = Path(args.manifests) if args.manifests else C.DATA / 'manifests'
        self.capture = Path(args.capture_dir) if args.capture_dir else C.DATA / 'capture'
        if args.cache_dir:
            self.cache = Path(args.cache_dir)
        else:
            import ar_worker
            self.cache = ar_worker.cache_dir()
        self.whiteners = Path(args.whitener_dir) if args.whitener_dir else C.WHITENERS
        self.out = Path(args.out) if args.out else C.DATA / 'select'


def load_family(fam, P: Paths, allow_missing_stages=()):
    """cells (with capture rows) and complete journals' records, for the family's stages."""
    import generate_samples as G
    audit = json.loads((P.capture / 'capture_audit.json').read_text())
    cap = {r['cell_id']: r for r in audit['cells']}
    cells, records, sources = {}, collections.defaultdict(dict), []
    for stage in FAMILY_STAGES[fam]:
        mpath = P.manifests / f'gen_{stage}.json'
        man = json.loads(mpath.read_text())
        pool = json.loads((P.gen_root / stage / 'pool.json').read_text()) if (P.gen_root / stage / 'pool.json').exists() else None
        if pool is None:
            if stage in allow_missing_stages:
                continue
            raise SystemExit(f'{stage}: no pool.json')
        if pool['gen_manifest_sha256'] != C.file_sha(mpath):
            raise SystemExit(f'{stage}: generation manifest changed after generation')
        n, count = man['n'], man['shard_count']
        for i in range(count):
            stem = f'shard-{i:03d}-of-{count:03d}'
            journal = P.gen_root / stage / f'{stem}.jsonl'
            st = json.loads((P.gen_root / stage / f'{stem}.status.json').read_text())
            if st['status'] != 'complete' or st['journal_sha256'] != C.file_sha(journal):
                raise SystemExit(f'{stage} {stem}: journal not complete/sealed')
            state = G.read_journal(journal, pool['global_pool_id'])
            for cid, rows in state.items():
                records[cid].update(rows)
            sources.append({'path': str(journal), 'sha256': st['journal_sha256']})
        for c in man['cells']:
            r = cap[c['cell_id']]
            cells[c['cell_id']] = dict(c, stage=stage, activation_row=r['activation_row'],
                                       activation_sha256=r['activation_sha256'],
                                       activation_tensor_path=r['activation_tensor_path'])
    return cells, records, sources


def load_usage(cache_dir, wanted_cells):
    usage = {}
    for path in sorted(Path(cache_dir).glob('usage_*.jsonl')):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row['cell_id'] not in wanted_cells:
                continue
            key = (row['cell_id'], row['sample_index'], row['source_phrase_id'])
            if key in usage and usage[key] != row:
                raise ValueError('Conflicting AR usage provenance')
            usage[key] = row
    return usage


def select_cell(cell, rows, usage, cache, whitener, target_raw, token_count, admissible):
    """The three settings for one cell, exactly as compare_selectors.main does them."""
    from compare_selectors import ar_scoreable, pool_candidates, selection_fits
    from olens_improve.reconstruction import JointNNLS
    from olens_improve.selection import Selection, best_of_n, greedy_pool, parse_bullets
    cell_id = cell['cell_id']
    target = whitener.whiten(target_raw.reshape(1, -1))[0]
    samples, provenance, needed, invalid_by_sample = [], {}, {}, {}
    pool = None
    for index in range(32):
        row = rows[index]
        if row['activation_sha256'] != cell['activation_sha256']:
            raise ValueError('Generated pool target differs from fresh activation')
        pool = row.get('global_pool_id', row['pool_id'])
        sample = parse_bullets(row['text'], f'{pool}:{cell_id}:{index}', index, token_count=token_count,
                               max_output_tokens=256)
        samples.append(sample)
        for bullet in sample.bullets:
            info = usage[(cell_id, index, bullet.phrase_id)]
            if info['text'] != bullet.text or info['activation_sha256'] != cell['activation_sha256']:
                raise ValueError('AR text/target provenance differs')
            provenance[bullet.phrase_id] = info
            if info['cache_key'] is None:
                if info.get('status') != 'empty_after_cleanup':
                    raise ValueError('Missing AR key without explicit empty-cleanup status')
                invalid_by_sample.setdefault(index, []).append(info)
                continue
            needed[bullet.phrase_id] = info['cache_key']
    keys = sorted(set(needed.values()))
    whitened = {}
    if keys:
        raw = torch.stack([cache.get(k) for k in keys])
        t = whitener.whiten(raw)
        t = t / (t.norm(dim=1, keepdim=True) + 1e-9)
        whitened = dict(zip(keys, t))
    phrase_vectors = {pid: whitened[k] for pid, k in needed.items()}
    meta = {'cell_id': cell_id, 'whitener_sha256': whitener.artifact_sha256,
            'vector_contract_sha256': cache.contract['sha256'], 'control_ids': []}
    exact = JointNNLS(target, phrase_vectors, metadata=meta)
    released = JointNNLS(target, phrase_vectors, solver='released80', metadata=meta)
    scoreable_admissible = lambda bullets: admissible(bullets) and ar_scoreable(bullets, phrase_vectors)  # noqa: E731
    results = []

    def save(method, n, selection):
        fits, fit_scope = selection_fits(selection, exact, released)
        if not admissible(selection.bullets):
            raise ValueError('Output violates final cap')
        ids = selection.phrase_ids
        results.append({'method': method, 'n': n, 'text': selection.text, 'phrase_ids': list(ids),
                        'token_count': token_count(selection.text), 'bullet_count': len(ids),
                        'reason': selection.reason, 'fits': fits, 'fits_scope': fit_scope,
                        'scored_text': selection.text if fits is not None else None,
                        'trace': list(selection.trace), 'atoms': [provenance[k] for k in ids], 'extra': {}})

    save('capped_n1', 1, Selection('capped_n1', samples[0].bullets, None))
    save('best_n_exact', 32, best_of_n(samples, 32, exact.score, admissible=scoreable_admissible))
    bullets, remapped = pool_candidates(samples, 32, phrase_vectors)
    save('pooled_greedy_swap', 32, greedy_pool(bullets, exact.score, admissible=admissible, swap_passes=1,
                                               complete_samples=remapped))
    pool_rows = []
    for s in samples:
        for b in s.bullets:
            info = provenance[b.phrase_id]
            solo = exact.score((b.phrase_id,)) if b.phrase_id in phrase_vectors else None
            pool_rows.append({'sample_index': s.index, 'pos': b.position, 'phrase_id': b.phrase_id, 'text': b.text,
                              'cache_key': info['cache_key'], 'status': info.get('status'),
                              'parsing_uncertain': s.parsing_uncertain, 'solo_fve': solo})
    event = {'cell_id': cell_id, 'family': cell['family'], 'item_id': cell['item_id'], 'layer': cell['layer'],
             'position': cell['position'], 'split': C.SPLIT, 'global_pool_id': pool,
             'activation_sha256': cell['activation_sha256'],
             'parser_flags_by_sample': {s.index: list(s.flags) for s in samples},
             'invalid_AR_atoms_by_sample': invalid_by_sample, 'selections': results}
    pool_event = {'cell_id': cell_id, 'target_norm2': float(target.double().square().sum()),
                  'n_samples': len(samples), 'bullets': pool_rows}
    return event, pool_event


def run(args):
    P = Paths(args)
    from transformers import AutoTokenizer
    from olens_improve.reconstruction import Whitener
    from olens_improve.selection import output_admissible
    torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '4')))
    tok = AutoTokenizer.from_pretrained(str(C.BASE), local_files_only=True)
    counts = {}

    def token_count(text):
        if text not in counts:
            counts[text] = len(tok(text, add_special_tokens=False)['input_ids'])
        return counts[text]
    admissible = output_admissible(token_count, 256)
    cells, records, sources = load_family(args.family, P, allow_missing_stages=('umB',))
    target_ids = sorted(cells)
    if args.cells:
        target_ids = [c for c in target_ids if c in set(args.cells.split(','))]
    target_ids = target_ids[args.shard_index::args.shard_count]
    cache = MemmapVectorCache(P.cache)
    usage = load_usage(P.cache, set(target_ids))
    acts = rows_memmap(str(P.capture / 'activations.safetensors'), 'resid')
    code = {str(p): C.file_sha(p) for p in (Path(__file__), C.OI / 'scripts/compare_selectors.py',
                                             C.OI / 'src/olens_improve/selection.py',
                                             C.OI / 'src/olens_improve/reconstruction.py')}
    config = {'schema': 'nt-select3-v1', 'settings': list(C.SETTINGS), 'primary_solver': 'scipy_exact',
              'compatibility_solver': 'released80', 'parser': 'source_contiguous_dash_blocks_v1', 'max_bullets': 4,
              'max_output_qwen_tokens': 256, 'swap_passes': 1, 'vector_contract': cache.contract,
              'sources': sources, 'family': args.family, 'code_sha256': code,
              'shard_index': args.shard_index, 'shard_count': args.shard_count}
    out = P.out / f'{args.family}-shard{args.shard_index:02d}of{args.shard_count:02d}'
    out.mkdir(parents=True, exist_ok=True)
    cpath = out / 'config.json'
    if cpath.exists() and json.loads(cpath.read_text()) != json.loads(json.dumps(config)):
        raise SystemExit('Cannot resume a different selection configuration')
    C.atomic_json(cpath, config)
    cfg_sha = C.digest(config)
    sel_path, pool_path = out / 'selections.jsonl', out / 'pool.jsonl'
    done = set()
    if sel_path.exists():
        for line in sel_path.read_text().splitlines():
            if line.endswith('}'):
                ev = json.loads(line)
                if ev['config_sha256'] != cfg_sha:
                    raise SystemExit('incompatible resumed event')
                done.add(ev['cell_id'])
    whiteners = {}
    t0 = time.time()
    by_layer = sorted((cells[c]['layer'], c) for c in target_ids if c not in done)
    with sel_path.open('a') as sel_f, pool_path.open('a') as pool_f:
        for k, (layer, cid) in enumerate(by_layer):
            if layer not in whiteners:
                whiteners[layer] = Whitener.load(str(P.whiteners / f'whitening_iolens_pooled_L{layer}.safetensors'))
            cell = cells[cid]
            target_raw = torch.from_numpy(np.array(acts[cell['activation_row']]))
            if C.sha(target_raw.numpy().tobytes()) != cell['activation_sha256']:
                raise ValueError(f'activation hash mismatch {cid}')
            if len(records.get(cid, {})) < 32:
                raise ValueError(f'{cid}: only {len(records.get(cid, {}))} samples')
            event, pool_event = select_cell(cell, records[cid], usage, cache, whiteners[layer], target_raw,
                                            token_count, admissible)
            event['config_sha256'] = cfg_sha
            event['seconds_since_start'] = time.time() - t0
            pool_f.write(json.dumps(pool_event, ensure_ascii=False) + '\n'); pool_f.flush()
            sel_f.write(json.dumps(event, ensure_ascii=False) + '\n'); sel_f.flush()
            os.fsync(sel_f.fileno())
            if (k + 1) % 50 == 0:
                print(json.dumps({'done': len(done) + k + 1, 'of': len(target_ids),
                                  's_per_cell': (time.time() - t0) / (k + 1)}), flush=True)
    C.atomic_json(out / 'status.json', {'status': 'complete', 'cells': len(target_ids), 'seconds': time.time() - t0})
    print(json.dumps({'shard': str(out), 'cells': len(target_ids), 'seconds': round(time.time() - t0, 1)}))


def merge(args):
    """Shard outputs -> hallucination-format extract + vector index + pool file + checks."""
    P = Paths(args)
    cells, _, _ = load_family(args.family, P, allow_missing_stages=('umB',))
    shards = sorted(P.out.glob(f'{args.family}-shard*of*'))
    events, pools = {}, {}
    for d in shards:
        if json.loads((d / 'status.json').read_text())['status'] != 'complete':
            raise SystemExit(f'{d} incomplete')
        for line in (d / 'selections.jsonl').read_text().splitlines():
            ev = json.loads(line)
            if ev['cell_id'] in events:
                raise SystemExit(f'duplicate selection {ev["cell_id"]}')
            events[ev['cell_id']] = (ev, str(d / 'selections.jsonl'))
        for line in (d / 'pool.jsonl').read_text().splitlines():
            pe = json.loads(line)
            pools[pe['cell_id']] = pe  # last wins (a crash can leave a pool line without its selection)
    missing = sorted(set(cells) - set(events))
    if missing and not args.allow_partial:
        raise SystemExit(f'{len(missing)} cells lack selections, e.g. {missing[:3]}')
    cache = MemmapVectorCache(P.cache)
    stats = collections.Counter()
    need = set()
    fam_long = C.FAMILIES[args.family]
    bank = C.load_bank(fam_long)
    ts_path = P.out / f'{args.family}_three_settings.jsonl'
    with open(ts_path, 'w') as out:
        for cid in sorted(events):
            ev, src = events[cid]
            cell = cells[cid]
            settings = {}
            for s in ev['selections']:
                cond = WANT[(s['method'], s['n'])]
                exact = (s.get('fits') or {}).get('exact')
                rel = (s.get('fits') or {}).get('released80') or {}
                if exact is not None:
                    assert exact['solver'] == 'scipy_exact' and list(exact['atom_ids']) == s['phrase_ids'], (cid, cond)
                else:
                    stats[f'unscored[{cond}]'] += 1
                assert [a['source_phrase_id'] for a in s['atoms']] == s['phrase_ids'], (cid, cond)
                atoms = [{k: a.get(k) for k in ATOM_KEEP} for a in s['atoms']]
                for a in atoms:
                    if a['cache_key'] is not None:
                        need.add(a['cache_key'])
                stats[f'bullets={len(atoms)}[{cond}]'] += 1
                settings[cond] = {'method': s['method'], 'n': s['n'], 'text': s['text'],
                                  'text_sha256': hashlib.sha256(s['text'].encode()).hexdigest(),
                                  'token_count': s['token_count'], 'bullet_count': s['bullet_count'],
                                  'reason': s['reason'], 'fits_scope': s['fits_scope'], 'phrase_ids': s['phrase_ids'],
                                  'fve': exact['fve'] if exact else None,
                                  'coefficients': exact['coefficients'] if exact else None,
                                  'released80_fve': rel.get('fve'), 'trace': s['trace'], 'atoms': atoms}
            assert set(settings) == set(C.SETTINGS), cid
            item = bank[cell['item_id']]
            group = item.get('cluster', cell['item_id']) if args.family == 'ca' else cell['item_id']
            out.write(json.dumps({
                'cell_id': cid, 'family': cell['family'], 'item_id': cell['item_id'], 'group_id': group,
                'layer': cell['layer'], 'position': cell['position'], 'split': C.SPLIT, 'token': cell['token'],
                'read_position_kind': cell.get('role'), 'tier': cell.get('tier'), 'stage': cell['stage'],
                'rel_from_end': cell.get('rel_from_end'), 'subfamily': item.get('subfamily'),
                'activation_row': cell['activation_row'], 'activation_sha256': cell['activation_sha256'],
                'global_pool_id': ev['global_pool_id'], 'vector_cache': str(P.cache), 'source_selections': src,
                'settings': settings}, ensure_ascii=False) + '\n')
            stats['cells'] += 1
    for pe in pools.values():
        for b in pe['bullets']:
            if b['cache_key'] is not None:
                need.add(b['cache_key'])
    index = {C.SPLIT: {k: [cache.index[k]['tensor_path'], cache.index[k]['row']] for k in sorted(need)}}
    missing_keys = [k for k in need if k not in cache.index]
    C.atomic_json(P.out / f'{args.family}_vector_index.json', index, indent=None)
    with open(P.out / f'{args.family}_pool.jsonl', 'w') as f:
        for cid in sorted(pools):
            if cid in events:
                f.write(json.dumps(pools[cid], ensure_ascii=False) + '\n')
    summary = {'family': args.family, 'cells': stats['cells'], 'missing_cells': len(missing),
               'vector_keys': len(need), 'missing_vector_keys': len(missing_keys),
               'pool_bullets': sum(len(p['bullets']) for c, p in pools.items() if c in events),
               'stats': dict(sorted(stats.items()))}
    C.atomic_json(P.out / f'{args.family}_select_summary.json', summary)
    print(json.dumps(summary, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('run', 'merge'))
    ap.add_argument('--family', choices=('um', 'ca'), required=True)
    ap.add_argument('--shard-index', type=int, default=0)
    ap.add_argument('--shard-count', type=int, default=1)
    ap.add_argument('--cells', default='')
    ap.add_argument('--allow-partial', action='store_true')
    for k in ('gen-root', 'manifests', 'capture-dir', 'cache-dir', 'whitener-dir', 'out'):
        ap.add_argument(f'--{k}', default=None)
    args = ap.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise SystemExit('CPU-heavy: run inside our Slurm CPU allocation')
    run(args) if args.cmd == 'run' else merge(args)


if __name__ == '__main__':
    main()
