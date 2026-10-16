"""A6 filler swap: AR-encode the originals and edited variants of variants.jsonl (GPU; --fake for CPU tests).

Same encoder as the pipeline (OI scripts/encode_candidates.encode_snapshot): olens_improve.reconstruction.FrozenAR
.load(base snapshot, ar_ptag_pooled) once, ar_token_ids cleanup, 32-token span, prompt tag per layer, raw (unwhitened)
float32 predictions; vector key = ar_cache.vector_key(contract a451cf49..., tag ids, first 32 token ids), so a
re-encoded original has exactly its cached key. Every unique vector_key of variants.jsonl is encoded once (originals
included, as the same-run baseline), grouped by layer, in batches; results go to a few big files
  vectors/a6_L{layer}_s{k:03d}.safetensors  ({"vectors": F32 [n, 5120]})  + .index.json (key -> row, token ids)
written atomically (tmp + rename; index after tensor). Resumable: keys already in a completed shard are skipped,
an interrupted shard is simply redone. It does not use run_worker.py and never reads data/control/STOP.

Checks (the job stops on a failure):
  1. contract digest of the AR files == a451cf49... (GPU mode);
  2. encode metadata (input ids, tag ids) == the variant's ar_ids32 and the layer's tag ids; finite outputs;
  3. probe: before the main pass, --probe originals (spread over layers) are re-encoded and compared with their
     cached vectors in data/vectors/a451cf49d28ac7447722 (cos >= --min-cos, default 0.999) -> vectors/probe_check.json;
  4. at the end, cos and relative L2 of every re-encoded original vs its cached vector -> vectors/identity_check.json.
Stops (partial shard dropped, rc 4): analysis/a6_swap/STOP exists, --max-seconds reached, SIGTERM/SIGINT.
Borrowed GPU (--guard-job J): J's board JSON must say "idle" at start and stay byte-identical (canonical JSON);
checked before every batch, else rc 3 (stop within one batch, ~1-2 s).

Run (from newtasks/; PY=${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python):
  own preemptable job:  sbatch analysis/a6_swap/encode_job.sbatch            (--time 00:30:00, 1x H200; a100 ok)
  borrowed idle H200 (only while gpu_board/25832889.json says idle and nvidia-smi ~0 MiB; add our board row first):
    /usr/bin/env -u SLURM_JOB_ID -u SLURM_JOBID -u SLURM_STEP_ID srun --jobid=25832889 --overlap \\
      --job-name=bulletfve-nt-a6 --gres=gpu:1 -n1 -c8 --mem=0 /usr/bin/env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \\
      PYTHONPATH=${OLENS_REPO_ROOT}/src $PY -B analysis/a6_swap/encode_job.py \\
      --guard-job 25832889 --max-seconds 840
  CPU test (fake encoder):  $PY -B analysis/a6_swap/test_encode_job.py
Expected: ~25k vectors at ~100 vectors/s (OI rate) = ~4-5 min + model load (~1-2 min).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
A6 = NT / 'analysis/a6_swap'
sys.path.insert(0, str(NT / 'code'))
import ntcommon as C  # noqa: E402

C.setup_paths()

CACHE_DIR = C.DATA / f'vectors/{C.OI_CONTRACT_SHA[:20]}'
DEFAULT_BOARD = Path('${OLENS_SCRATCH}/gpu_board')
RC_GUARD, RC_STOP = 3, 4
_SIGNAL = {'stop': None}


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def atomic_json(path, payload):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(payload, indent=1) + '\n')
    os.replace(tmp, path)


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def contract_digest():
    """The vector-cache contract, built exactly as encode_snapshot builds it (no model load)."""
    from olens_improve.ar_cache import digest
    from olens_improve.models import BASE_REVISION, PAIR_REVISION
    ck = C.AR_CKPT
    cfg = json.loads((ck / 'meta.json').read_text())['config']
    contract = {'base_revision': BASE_REVISION, 'pair_revision': PAIR_REVISION,
                'head_sha256': file_sha(ck / 'heads.pt'), 'meta_sha256': file_sha(ck / 'meta.json'),
                'adapter_config_sha256': file_sha(ck / 'lora/adapter_config.json'),
                'adapter_sha256': file_sha(ck / 'lora/adapter_model.safetensors'),
                'tokenizer_revision': BASE_REVISION, 'tokenizer_cleanup': 'source_scaffolding_and_special_ids_v1',
                'span_limit': 32, 'padding': 'right_zero', 'head_layer_norm': cfg['head_layer_norm'],
                'head_layer_norm_epsilon': 1e-5, 'final_norm': 'Identity', 'backbone_dtype': 'bfloat16',
                'head_dtype': 'float32', 'key_policy': 'effective_scored_tokens_and_tag_v1'}
    return digest(contract)


# ------------------------------------------------------------------------------------------ encoders
class FakeAR:
    """CPU stand-in with FrozenAR's encode_mixed contract: real tokenizer + ar_token_ids, 32-token span, the real
    tag ids; the vector is a deterministic function of (layer, token ids) (unit-variance normal, dim `dim`)."""

    def __init__(self, tag_ids_by_layer: dict, dim: int = 64):
        from transformers import AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(str(C.BASE), local_files_only=True)
        self.tags = {int(k): v for k, v in tag_ids_by_layer.items()}
        self.layers = tuple(sorted(self.tags))
        self.dim = dim
        self.metadata = {'fake': True, 'dim': dim}

    @staticmethod
    def vector(layer, ids, dim):
        import numpy as np
        seed = int(hashlib.sha256(json.dumps([int(layer), list(ids)]).encode()).hexdigest()[:15], 16)
        return np.random.default_rng(seed).standard_normal(dim).astype('float32')

    def encode_mixed(self, texts, layers):
        import numpy as np
        import torch
        from olens_improve.reconstruction import ar_token_ids
        meta, vecs = [], []
        for text, layer in zip(texts, layers):
            cleaned, ids = ar_token_ids(self.tokenizer, text)
            if not ids:
                raise ValueError('Empty AR text cannot be encoded')
            ids32 = ids[:32]
            vecs.append(self.vector(layer, ids32, self.dim))
            meta.append({'text': text, 'scored_text': cleaned, 'input_ids': ids32, 'tag_ids': self.tags[int(layer)],
                         'layer': layer, 'scored_token_count': len(ids32)})
        return torch.from_numpy(np.stack(vecs)), meta


def load_real_ar():
    import torch
    from olens_improve.reconstruction import FrozenAR
    if not torch.cuda.is_available():
        raise SystemExit('GPU mode needs CUDA (use --fake for CPU tests)')
    torch.set_num_threads(4)
    t = time.time()
    ar = FrozenAR.load(str(C.BASE), str(C.AR_CKPT))
    log(f'FrozenAR loaded in {time.time() - t:.1f}s on {torch.cuda.get_device_name(0)}')
    # same floating-point batching fixture as encode_snapshot (mixed tags vs separate calls)
    texts = ['The performer humiliates the heckler.', 'A number.', 'The intermediate result is eleven. ' + 'A further detail. ' * 12]
    lays = [20, 44, 60]
    mixed, _ = ar.encode_mixed(texts, lays)
    sep = torch.cat([ar.encode([tx], la)[0] for tx, la in zip(texts, lays)])
    rel = ((mixed - sep).norm(dim=1) / sep.norm(dim=1).clamp_min(1e-12)).tolist()
    if max(rel) > .02:
        raise SystemExit(f'mixed-tag batching check failed: {rel}')
    return ar, {'mixed_tag_relative_l2': rel, 'device': torch.cuda.get_device_name(0)}


# ------------------------------------------------------------------------------------------ guards
class Guard:
    def __init__(self, args):
        self.args = args
        self.t0 = time.time()
        self.stop_file = Path(args.out).parent / 'STOP' if args.stop_file is None else Path(args.stop_file)
        self.board = None
        if args.guard_job:
            self.board_path = Path(args.board_dir) / f'{args.guard_job}.json'
            state = self._read()
            if state is None or state.get('state') != 'idle':
                raise SystemExit(RC_GUARD)
            self.board = json.dumps(state, sort_keys=True)

    def _read(self):
        try:
            return json.loads(self.board_path.read_text())
        except (OSError, ValueError):
            return None

    def reason(self):
        """None while work may continue, else (rc, why)."""
        if _SIGNAL['stop']:
            return RC_STOP, f'signal {_SIGNAL["stop"]}'
        if self.stop_file.exists():
            return RC_STOP, f'STOP file {self.stop_file}'
        if self.args.max_seconds and time.time() - self.t0 > self.args.max_seconds:
            return RC_STOP, 'deadline'
        if self.board is not None:
            state = self._read()
            if state is None:  # one unreadable read is tolerated (atomic writes by the owner); two in a row stop
                time.sleep(1)
                state = self._read()
            if state is None or json.dumps(state, sort_keys=True) != self.board or state.get('state') != 'idle':
                return RC_GUARD, f'board {self.board_path.name} changed or not idle'
        return None


# ------------------------------------------------------------------------------------------ data
def load_units(variants_path):
    """Unique encode units: vector_key -> {layer, text, ids, originals: [(source_key, cached_vector)]}."""
    units = collections.OrderedDict()
    n_rows = 0
    with open(variants_path) as f:
        for line in f:
            r = json.loads(line)
            n_rows += 1
            k = r['vector_key']
            u = units.get(k)
            if u is None:
                u = units[k] = {'layer': int(r['layer']), 'text': r['edited_text'], 'ids': r['ar_ids32'], 'original_of': []}
            elif u['layer'] != int(r['layer']) or u['ids'] != r['ar_ids32']:
                raise SystemExit(f'vector key {k} maps to different inputs')
            if r['variant_type'] == 'original':
                u['original_of'].append((r['source_key'], r.get('cached_vector')))
    return units, n_rows


def read_shards(out: Path):
    """Completed shards -> (done keys -> (path, row), shard list). Stray tmp files are removed."""
    for p in out.glob('*.tmp'):
        p.unlink()
    done, shards = {}, []
    for idx in sorted(out.glob('a6_L*_s*.index.json')):
        info = json.loads(idx.read_text())
        tpath = out / info['tensor_file']
        if not tpath.is_file():
            continue
        shards.append(info | {'index_file': idx.name})
        for e in info['vectors']:
            if e['vector_key'] in done:
                raise SystemExit(f'duplicate key in shards: {e["vector_key"]}')
            done[e['vector_key']] = (tpath, e['row'])
    return done, shards


def read_rows(locs):
    """[(path, row)] -> list of 1-D float tensors (cached / our shards), reading only the needed rows."""
    import torch
    from safetensors import safe_open
    by_file = collections.defaultdict(list)
    for i, (p, row) in enumerate(locs):
        by_file[str(p)].append((i, row))
    out = [None] * len(locs)
    for p, items in by_file.items():
        with safe_open(p, framework='pt', device='cpu') as f:
            sl = f.get_slice('vectors')
            for i, row in items:
                out[i] = sl[row:row + 1][0].to(torch.float32)
    return out


def compare(a_list, b_list):
    import torch
    a = torch.stack(a_list).double()
    b = torch.stack(b_list).double()
    cos = torch.nn.functional.cosine_similarity(a, b, dim=1)
    rel = (a - b).norm(dim=1) / b.norm(dim=1).clamp_min(1e-12)
    return cos.tolist(), rel.tolist()


def summary(vals):
    import statistics
    s = sorted(vals)
    q = lambda p: s[min(len(s) - 1, int(p * (len(s) - 1)))]  # noqa: E731
    return {'n': len(s), 'min': s[0], 'p01': q(.01), 'median': q(.5), 'mean': statistics.fmean(s), 'max': s[-1]} if s else {'n': 0}


def encode_batch(ar, batch, tags):
    import torch
    vecs, meta = ar.encode_mixed([u['text'] for _, u in batch], [u['layer'] for _, u in batch])
    for (k, u), m in zip(batch, meta):
        if m['input_ids'] != u['ids'] or list(m['tag_ids']) != list(tags[u['layer']]):
            raise SystemExit(f'encode input differs from variants.jsonl for {k}: {m["input_ids"][:8]}... vs {u["ids"][:8]}...')
    vecs = vecs.float().cpu()
    if not torch.isfinite(vecs).all():
        raise SystemExit('nonfinite AR predictions')
    return vecs


def probe(ar, units, tags, args, out):
    """Re-encode a spread of originals and compare with their cached vectors before the main pass."""
    origs = [(k, u) for k, u in units.items() if u['original_of'] and u['original_of'][0][1]]
    by_layer = collections.defaultdict(list)
    for k, u in origs:
        by_layer[u['layer']].append((k, u))
    pick = []
    for L in sorted(by_layer):
        xs = sorted(by_layer[L], key=lambda x: hashlib.sha256(x[0].encode()).hexdigest())
        pick += xs[:max(1, args.probe // max(1, len(by_layer)))]
    if not pick:
        raise SystemExit('no originals with cached vectors to probe')
    mine = []
    for L in sorted({u['layer'] for _, u in pick}):
        b = [x for x in pick if x[1]['layer'] == L]
        mine += list(encode_batch(ar, b, tags))
    cached = read_rows([u['original_of'][0][1] for _, u in pick])
    cos, rel = compare(mine, cached)
    res = {'n': len(pick), 'cos': summary(cos), 'rel_l2': summary(rel), 'min_cos_required': args.min_cos,
           'ok': min(cos) >= args.min_cos, 'layers': sorted({u['layer'] for _, u in pick}),
           'worst': sorted(({'vector_key': k, 'layer': u['layer'], 'cos': c, 'rel_l2': r}
                            for (k, u), c, r in zip(pick, cos, rel)), key=lambda x: x['cos'])[:5]}
    atomic_json(out / 'probe_check.json', res)
    log(f'probe: {len(pick)} originals, cos min {min(cos):.6f} median {res["cos"]["median"]:.6f}, '
        f'rel L2 max {max(rel):.2e}')
    if not res['ok']:
        raise SystemExit(f'probe failed: re-encoded originals do not reproduce the cache (min cos {min(cos):.5f})')
    return res


def final_identity(units, out):
    done, _ = read_shards(out)
    pairs = []
    for k, u in units.items():
        for src, loc in u['original_of']:
            if loc and k in done:
                pairs.append((k, u['layer'], src, done[k], loc))
    mine = read_rows([p[3] for p in pairs])
    cached = read_rows([p[4] for p in pairs])
    cos, rel = compare(mine, cached)
    per_layer = collections.defaultdict(list)
    for p, c in zip(pairs, cos):
        per_layer[p[1]].append(c)
    res = {'n_originals': len(pairs), 'cos': summary(cos), 'rel_l2': summary(rel),
           'per_layer_cos_min': {str(L): min(v) for L, v in sorted(per_layer.items())},
           'n_cos_below_0.999': sum(c < 0.999 for c in cos), 'n_cos_below_0.99': sum(c < 0.99 for c in cos),
           'worst': sorted(({'vector_key': p[0], 'layer': p[1], 'source_key': p[2], 'cos': c, 'rel_l2': r}
                            for p, c, r in zip(pairs, cos, rel)), key=lambda x: x['cos'])[:20]}
    atomic_json(out / 'identity_check.json', res)
    log(f'identity: {len(pairs)} originals, cos min {res["cos"]["min"]:.6f} median {res["cos"]["median"]:.6f}; '
        f'{res["n_cos_below_0.999"]} below 0.999')
    return res


def run_event(out, **ev):
    with open(out / 'run_log.jsonl', 'a') as f:
        f.write(json.dumps({'time': time.strftime('%F %T'), 'job': os.environ.get('SLURM_JOB_ID'),
                            'step': os.environ.get('SLURM_STEP_ID'), **ev}) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--variants', default=str(A6 / 'variants.jsonl'))
    ap.add_argument('--out', default=str(A6 / 'vectors'))
    ap.add_argument('--batch-size', type=int, default=128)
    ap.add_argument('--shard-size', type=int, default=8192, help='max vectors per file (one layer per file)')
    ap.add_argument('--probe', type=int, default=64)
    ap.add_argument('--min-cos', type=float, default=0.999)
    ap.add_argument('--guard-job', default=None)
    ap.add_argument('--board-dir', default=str(DEFAULT_BOARD))
    ap.add_argument('--stop-file', default=None, help='default: <out>/../STOP (analysis/a6_swap/STOP)')
    ap.add_argument('--max-seconds', type=float, default=0)
    ap.add_argument('--max-batches', type=int, default=0, help='tests: stop (rc 4) after this many batches')
    ap.add_argument('--fake', action='store_true', help='CPU test: deterministic fake encoder, no GPU')
    ap.add_argument('--dim', type=int, default=64, help='--fake vector size')
    ap.add_argument('--tags-json', default=str(A6 / 'build_meta.json'), help='tag ids by layer (build_meta.json)')
    ap.add_argument('--allow-variants-change', action='store_true')
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s, f: _SIGNAL.__setitem__('stop', s))
    t0 = time.time()
    guard = Guard(args)  # refuses (rc 3) when a guarded board JSON is not idle at start
    tags = {int(k): v for k, v in json.loads(Path(args.tags_json).read_text())['tag_ids'].items()}
    vsha = file_sha(args.variants)
    units, n_rows = load_units(args.variants)
    done, shards = read_shards(out)
    stale = {s.get('variants_sha256') for s in shards} - {vsha}
    if stale and not args.allow_variants_change:
        raise SystemExit(f'existing shards were made from another variants.jsonl ({stale}); use a new --out or '
                         '--allow-variants-change')
    pending = [(k, u) for k, u in units.items() if k not in done]
    log(f'{n_rows} rows, {len(units)} unique keys, {len(units) - len(pending)} already encoded, {len(pending)} pending; '
        f'{len(shards)} shards in {out}')
    run_event(out, event='start', pending=len(pending), fake=args.fake, guard_job=args.guard_job)
    if not pending and (out / 'manifest.json').exists():
        log('nothing to do')
        return 0
    if not pending:
        ar, load_info = None, {'note': 'no pending keys; finishing checks only'}
    elif args.fake:
        ar, load_info = FakeAR(tags, args.dim), {'fake': True}
    else:
        d = contract_digest()
        if d != C.OI_CONTRACT_SHA:
            raise SystemExit(f'AR contract {d} differs from {C.OI_CONTRACT_SHA}')
        ar, load_info = load_real_ar()
    why = guard.reason()
    if why:
        run_event(out, event='stopped', rc=why[0], why=why[1])
        log('stopping before work:', why[1])
        return why[0]
    probe_res = probe(ar, units, tags, args, out) if pending else None
    by_layer = collections.defaultdict(list)
    for k, u in pending:
        by_layer[u['layer']].append((k, u))
    next_no = collections.Counter()
    for s in shards:
        next_no[s['layer']] = max(next_no[s['layer']], s['shard_no'] + 1)
    n_batches, n_new, t_enc = 0, 0, time.time()
    import torch
    from safetensors.torch import save_file
    for L in sorted(by_layer):
        items = by_layer[L]
        for lo in range(0, len(items), args.shard_size):
            chunk = items[lo:lo + args.shard_size]
            vecs = []
            ts = time.time()
            for b0 in range(0, len(chunk), args.batch_size):
                why = guard.reason()
                if not why and args.max_batches and n_batches >= args.max_batches:
                    why = (RC_STOP, 'max-batches (test)')
                if why:
                    run_event(out, event='stopped', rc=why[0], why=why[1], new_vectors=n_new)
                    log(f'stopping: {why[1]} (partial L{L} shard dropped; {n_new} vectors saved this run)')
                    return why[0]
                vecs.append(encode_batch(ar, chunk[b0:b0 + args.batch_size], tags))
                n_batches += 1
            no = next_no[L]
            next_no[L] += 1
            name = f'a6_L{L}_s{no:03d}'
            tensor = torch.cat(vecs)
            tmp = out / f'{name}.safetensors.tmp'
            save_file({'vectors': tensor.contiguous()}, str(tmp),
                      metadata={'contract_sha256': C.OI_CONTRACT_SHA, 'layer': str(L), 'variants_sha256': vsha})
            os.replace(tmp, out / f'{name}.safetensors')
            atomic_json(out / f'{name}.index.json', {
                'contract_sha256': C.OI_CONTRACT_SHA, 'variants_sha256': vsha, 'layer': L, 'shard_no': no,
                'tensor_file': f'{name}.safetensors', 'n': len(chunk), 'dim': int(tensor.shape[1]),
                'fake': bool(args.fake), 'batch_size': args.batch_size, 'seconds': round(time.time() - ts, 2),
                'job': os.environ.get('SLURM_JOB_ID'), 'load_info': load_info,
                'vectors': [{'vector_key': k, 'row': i, 'ar_ids32': u['ids'], 'tag_ids': tags[L]}
                            for i, (k, u) in enumerate(chunk)]})
            n_new += len(chunk)
            rate = n_new / max(1e-9, time.time() - t_enc)
            atomic_json(out / 'progress.json', {'status': 'running', 'unique_keys': len(units),
                                                'encoded_this_run': n_new, 'pending_at_start': len(pending),
                                                'vectors_per_second': round(rate, 1), 'last_shard': name})
            log(f'{name}: {len(chunk)} vectors in {time.time() - ts:.1f}s ({rate:.0f}/s overall)')
    done, shards = read_shards(out)
    missing = [k for k in units if k not in done]
    if missing:
        raise SystemExit(f'{len(missing)} keys missing after the pass')
    ident = final_identity(units, out)
    atomic_json(out / 'manifest.json', {
        'status': 'complete', 'variants': str(args.variants), 'variants_sha256': vsha, 'rows': n_rows,
        'unique_keys': len(units), 'contract_sha256': C.OI_CONTRACT_SHA, 'fake': bool(args.fake),
        'shards': [{'tensor_file': s['tensor_file'], 'index_file': s['index_file'], 'layer': s['layer'], 'n': s['n']}
                   for s in shards],
        'probe': probe_res and {k: probe_res[k] for k in ('n', 'cos', 'ok')},
        'identity': {k: ident[k] for k in ('n_originals', 'cos', 'rel_l2', 'n_cos_below_0.999')},
        'seconds_total': round(time.time() - t0, 1), 'load_info': load_info})
    atomic_json(out / 'progress.json', {'status': 'complete', 'unique_keys': len(units), 'encoded_this_run': n_new})
    run_event(out, event='complete', new_vectors=n_new, seconds=round(time.time() - t0, 1))
    log(f'complete: {len(units)} keys in {len(shards)} files, {time.time() - t0:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
