"""O-lens sampling for one generation stage shard (GPU), resumable, append-only journal.

Reuses OI unchanged: models.FrozenOLens.load / .merge / .sample, sampling.sample_many, and from
scripts/generate_samples.py: read_journal (crash-tail repair), append_event (fsync per batch),
batch_seed, shard_for, canonical. generate_samples.main itself needs OI coordinator gates and
OI-listed job IDs, so this file supplies only the loop, the claim, the stop conditions and the
board guard. Records carry the generate_samples fields.

Settings (frozen): temperature 1, top-p .95, top-k 64, alpha 16000 x unit(h), carrier
models.CARRIER, max_new_tokens 256; batches = up to `cells_per_batch` same-layer cells x n samples
(H200 default: 256 sequences per batch, i.e. 8 cells x 32 = the exp-068 recipe; 64 cells x 4 for P0).

A shard's status file `shard-XXX-of-YYY.status.json` says 'complete' with the journal sha256 only
when every cell has n samples; OI encode_candidates.encode_snapshot checks exactly that.
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
from claims import try_claim  # noqa: E402

MAX_NEW_TOKENS = 256


def oi():
    """Late import of the OI journal helpers (they import olens_improve)."""
    import generate_samples as G
    return G


def capture_index():
    """cell_id -> fresh capture row (activation path/row/sha), validated against the manifest."""
    cap_dir = C.DATA / 'capture'
    audit = json.loads((cap_dir / 'capture_audit.json').read_text())
    state = json.loads((cap_dir / 'capture_state.json').read_text())
    man_sha = C.file_sha(C.DATA / 'manifests/capture.json')
    if state.get('status') != 'complete' or state['manifest_sha256'] != man_sha or audit['manifest_sha256'] != man_sha:
        raise RuntimeError('capture is not complete for the frozen capture manifest')
    out = {}
    for row in audit['cells']:
        if row.get('adapter_disabled') is not True or row.get('generation_activation_source') != 'fresh_recapture':
            raise ValueError('capture row lacks adapter-free provenance')
        out[row['cell_id']] = row
    return out


def load_stage(stage: str, cap=None):
    fam, n, shards = C.STAGES[stage]
    path = C.DATA / 'manifests' / f'gen_{stage}.json'
    body = path.read_bytes()
    man = json.loads(body)
    if (man['stage'], man['family'], man['n'], man['shard_count']) != (stage, fam, n, shards):
        raise ValueError(f'{stage}: manifest header differs from ntcommon.STAGES')
    cap = capture_index() if cap is None else cap
    cells = []
    for c in man['cells']:
        r = cap[c['cell_id']]
        if (r['layer'], r['position']) != (c['layer'], c['position']):
            raise ValueError(f'capture identity differs: {c["cell_id"]}')
        cells.append(dict(c, activation_tensor_path=r['activation_tensor_path'],
                          activation_row=r['activation_row'], activation_sha256=r['activation_sha256']))
    config = {'schema_version': 1, 'study': 'olens-bullet-fve/newtasks', 'stage': stage, 'family': fam,
              'gen_manifest_sha256': C.sha(body), 'capture_manifest_sha256': man['capture_manifest_sha256'],
              'base_revision': '6a9e13bd6fc8f0983b9b99948120bc37f49c13e9',
              'adapter_revision': 'c95215d5d2f6250f20c305ae55c6e4d7569f92dc', 'adapter': 'olens_s3d_rl600',
              'seed': C.SEED, 'n': n, 'max_new_tokens': MAX_NEW_TOKENS, 'temperature': 1.0, 'top_p': 0.95,
              'top_k': 64, 'alpha': 16000.0, 'shard_count': shards, 'maximum_shared_samples_per_cell': 32}
    pool_id = C.digest(config)[:24]
    return man, cells, config, pool_id


def publish_pool(stage, config, pool_id):
    out = C.stage_dir(stage)
    out.mkdir(parents=True, exist_ok=True)
    want = dict(config, global_pool_id=pool_id)
    path = out / 'pool.json'
    tmp = out / f'pool.{os.getpid()}.{time.time_ns()}.tmp'
    tmp.write_text(json.dumps(want, indent=1) + '\n')
    try:
        os.link(tmp, path)
    except FileExistsError:
        if json.loads(path.read_text()) != want:
            raise ValueError(f'{stage}: existing pool.json differs; never mix stochastic pools')
    finally:
        tmp.unlink(missing_ok=True)


def shard_paths(stage, index, count):
    stem = f'shard-{index:03d}-of-{count:03d}'
    d = C.stage_dir(stage)
    return d / f'{stem}.jsonl', d / f'{stem}.status.json', C.DATA / 'claims' / f'gen-{stage}-{stem}.json'


def shard_status(stage, index):
    _, _, count = C.STAGES[stage]
    _, status, _ = shard_paths(stage, index, count)
    try:
        return json.loads(status.read_text())
    except FileNotFoundError:
        return {'status': 'absent'}


def activation(cell):
    from safetensors import safe_open
    with safe_open(cell['activation_tensor_path'], framework='pt') as f:
        h = f.get_slice('resid')[cell['activation_row']].float()
    s = C.sha(h.numpy().tobytes())
    if s != cell['activation_sha256']:
        raise ValueError(f'activation hash mismatch {cell["cell_id"]}')
    return h, s


class Context:
    """Per-process state: the lazily loaded, merged O-lens; stop conditions; the sampler."""

    def __init__(self, *, cells_per_batch=64, max_batch_sequences=256, deadline=None, guard=None,
                 sampler=None, single_sampler=None, lens_loader=None, log=print):
        self.cells_per_batch, self.max_batch_sequences = cells_per_batch, max_batch_sequences
        self.deadline, self.guard, self.log = deadline, guard, log
        self.stop_reason = None
        self._lens = None
        self.lens_loader = lens_loader or self._load_real
        self.sampler = sampler or self._sample_many
        self.single_sampler = single_sampler or self._sample_one
        self.batch_seconds = deque(maxlen=20)

    @staticmethod
    def _load_real():
        from olens_improve.models import FrozenOLens
        lens = FrozenOLens.load(str(C.BASE), str(C.ADAPTER))
        drift = lens.merge()
        return lens, {'adapter_delta': lens.adapter_delta, 'merge_drift': drift}

    @staticmethod
    def _sample_many(lens, acts, layer, count, seed):
        from olens_improve.sampling import sample_many
        return sample_many(lens, acts, layer, n_per_cell=count, seed=seed, max_new_tokens=MAX_NEW_TOKENS)

    @staticmethod
    def _sample_one(lens, act, layer, count, seed):
        texts, meta = lens.sample(act, layer, n=count, seed=seed, max_new_tokens=MAX_NEW_TOKENS)
        return [texts], meta

    def lens(self):
        if self._lens is None:
            # One H200 cannot hold the AR model (~50 GiB) and the lens at the 256-sequence peak
            # (~103 GB) together: drop the AR model before (re)loading the lens.
            self.release_ar()
            t0 = time.time()
            self._lens, info = self.lens_loader()
            self.lens_info = dict(info, load_seconds=time.time() - t0)
            self.log(f'lens loaded {self.lens_info}')
        return self._lens

    def release_lens(self):
        if self._lens is not None:
            self._lens = None
            import gc
            gc.collect()
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass

    def release_ar(self):
        """Drop a loaded AR model (set by run_worker.ar_pass) unless keep_ar (CPU fake-model tests)."""
        if getattr(self, 'ar', None) is not None and not getattr(self, 'keep_ar', False):
            self.ar = None
            import gc
            gc.collect()
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass
            self.log('AR model released before loading the lens')

    def request_stop(self, reason):
        if self.stop_reason is None:
            self.stop_reason = reason

    def may_start_batch(self) -> bool:
        if self.stop_reason:
            return False
        if (C.DATA / 'control/STOP').exists():  # clean stop: finish the current batch, then exit (rc 4)
            self.request_stop('STOP file')
            return False
        if self.deadline is not None:
            est = max(self.batch_seconds) if self.batch_seconds else 60.0
            if time.monotonic() + est + 15 > self.deadline:
                self.request_stop('deadline')
                return False
        if self.guard is not None:
            ok, hard, soft = self.guard.check()
            if not ok:
                self.request_stop(f'board guard: {hard or soft}')
                return False
        return True


def write_status(path, payload):
    C.atomic_json(path, payload)


def run_shard(stage: str, index: int, ctx: Context, *, cap=None) -> str:
    """-> 'complete' | 'claimed_elsewhere' | 'stopped:<reason>'."""
    G = oi()
    man, all_cells, config, pool_id = load_stage(stage, cap)
    fam, n, count = C.STAGES[stage]
    cells = [c for c in all_cells if G.shard_for(c['cell_id'], count) == index]
    journal, status_path, claim_path = shard_paths(stage, index, count)
    publish_pool(stage, config, pool_id)
    claim = try_claim(claim_path, {'stage': stage, 'shard': index})
    if claim is None:
        return 'claimed_elsewhere'
    try:
        state = G.read_journal(journal, pool_id, repair_tail=True)
        by_id = {c['cell_id']: c for c in cells}
        if set(state) - set(by_id):
            raise ValueError('journal holds cells outside this shard')
        for cid, rows in state.items():
            want = by_id[cid]['activation_sha256']
            if any(r['activation_sha256'] != want for r in rows.values()):
                raise ValueError(f'persisted samples were generated from another activation: {cid}')
        remaining = [c for c in cells if len(state.get(c['cell_id'], {})) < n]

        def status(kind):
            done = sum(len(state.get(c['cell_id'], {})) >= n for c in cells)
            payload = {'global_pool_id': pool_id, 'stage': stage, 'shard_index': index, 'shard_count': count,
                       'job_id': os.environ.get('SLURM_JOB_ID'), 'target_n': n, 'expected_cells': len(cells),
                       'completed_cells': done, 'persisted_samples': sum(len(v) for v in state.values()),
                       'updated_unix': time.time(), 'status': kind}
            if kind == 'complete':
                if not journal.exists():  # an empty shard still gets a sealed (empty) journal
                    journal.parent.mkdir(parents=True, exist_ok=True)
                    journal.touch()
                payload.update(journal_path=str(journal), journal_sha256=C.file_sha(journal))
            write_status(status_path, payload)
            return payload

        if not remaining:
            status('complete')
            return 'complete'
        if not ctx.may_start_batch():
            status('interrupted')
            return f'stopped:{ctx.stop_reason}'
        lens = ctx.lens()
        if not claim.still_owner():
            raise RuntimeError('claim lost during model load')
        launch = {'stage': stage, 'shard_index': index, 'job_id': os.environ.get('SLURM_JOB_ID'),
                  'step_id': os.environ.get('SLURM_STEP_ID'), 'host': os.uname().nodename,
                  'cells_per_batch': ctx.cells_per_batch, 'max_batch_sequences': ctx.max_batch_sequences,
                  'lens_info': getattr(ctx, 'lens_info', None),
                  'source_hashes': {p.name: C.file_sha(p) for p in (
                      C.OI / 'src/olens_improve/models.py', C.OI / 'src/olens_improve/sampling.py',
                      C.OI / 'scripts/generate_samples.py', Path(__file__))}}
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open('a') as stream:
            G.append_event(stream, {'global_pool_id': pool_id, 'kind': 'launch', 'launch': launch,
                                    'records': []}, state)
            buckets = defaultdict(deque)
            for c in sorted(remaining, key=lambda v: v['cell_id']):
                start = len(state.get(c['cell_id'], {}))
                buckets[(c['layer'], start, min(32, n - start))].append(c)
            while buckets:
                if not ctx.may_start_batch():
                    break
                layer, start, k = key = min(buckets)
                bucket = buckets[key]
                row_limit = min(ctx.cells_per_batch, ctx.max_batch_sequences // k)
                batch = [bucket.popleft() for _ in range(min(row_limit, len(bucket)))]
                if not bucket:
                    del buckets[key]
                acts = [activation(c) for c in batch]
                ids = [c['cell_id'] for c in batch]
                seed = G.batch_seed(pool_id, G.canonical(ids), start, C.SEED)
                t0 = time.monotonic()
                if len(batch) == 1:
                    texts_by_cell, meta = ctx.single_sampler(lens, acts[0][0], layer, k, seed)
                else:
                    import torch
                    texts_by_cell, meta = ctx.sampler(lens, torch.stack([a[0] for a in acts]), layer, k, seed)
                seconds = time.monotonic() - t0
                if len(texts_by_cell) != len(batch) or any(len(t) != k for t in texts_by_cell):
                    raise ValueError('generator returned an incomplete batch')
                records = []
                for r, (c, texts, (_, act_sha)) in enumerate(zip(batch, texts_by_cell, acts)):
                    for off, text in enumerate(texts):
                        j = r * k + off
                        records.append({name: c[name] for name in ('cell_id', 'family', 'item_id', 'layer', 'position')} | {
                            'sample_index': start + off, 'text': text, 'token_count': meta['token_counts'][j],
                            'seed': seed, 'pool_id': pool_id, 'global_pool_id': pool_id,
                            'truncated': meta['truncated'][j], 'finish_reason': meta['finish_reasons'][j],
                            'base_revision': config['base_revision'], 'adapter_revision': config['adapter_revision'],
                            'activation_sha256': act_sha})
                if not claim.still_owner():
                    raise RuntimeError('claim lost; refusing to append')
                G.append_event(stream, {'global_pool_id': pool_id, 'kind': 'generation',
                                        'activation_hashes': {c['cell_id']: a[1] for c, a in zip(batch, acts)},
                                        'cell_order': ids, 'batch_start': start, 'samples_per_cell': k,
                                        'batch_sequence_count': len(batch) * k, 'seconds': seconds,
                                        'generation': meta, 'job_id': os.environ.get('SLURM_JOB_ID'),
                                        'records': records}, state)
                ctx.batch_seconds.append(seconds)
                for c in batch:
                    nxt = len(state[c['cell_id']])
                    if nxt < n:
                        buckets[(layer, nxt, min(32, n - nxt))].append(c)
                st = status('running')
                claim.heartbeat(cells=ids)
                ctx.log(f'{stage} shard {index}: {st["completed_cells"]}/{st["expected_cells"]} cells, '
                        f'batch {len(batch)}x{k} in {seconds:.1f}s')
        final = 'complete' if all(len(state.get(c['cell_id'], {})) >= n for c in cells) else 'interrupted'
        status(final)
        return 'complete' if final == 'complete' else f'stopped:{ctx.stop_reason}'
    finally:
        claim.release()


def stage_progress(stage):
    """Read-only summary from status files and journals (generation seconds per cell)."""
    fam, n, count = C.STAGES[stage]
    out = {'stage': stage, 'shards': {}, 'gen_seconds': 0.0, 'cells_done': 0, 'batches': 0}
    for i in range(count):
        journal, status_path, _ = shard_paths(stage, i, count)
        st = shard_status(stage, i)
        out['shards'][i] = {k: st.get(k) for k in ('status', 'completed_cells', 'expected_cells')}
        out['cells_done'] += st.get('completed_cells') or 0
        if journal.exists():
            for line in journal.read_text().splitlines():
                if line.endswith('}'):
                    ev = json.loads(line)
                    if ev.get('kind') == 'generation':
                        out['gen_seconds'] += ev['seconds']
                        out['batches'] += 1
    out['s_per_cell'] = out['gen_seconds'] / out['cells_done'] if out['cells_done'] else None
    return out


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('progress', 'validate'))
    args = ap.parse_args()
    if args.cmd == 'progress':
        print(json.dumps({s: stage_progress(s) for s in C.STAGES}, indent=1))
    else:
        for s in C.STAGES:
            man, cells, config, pool_id = load_stage(s)
            print(s, len(cells), pool_id)
