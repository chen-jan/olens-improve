"""GPU worker driver: capture (once) -> generation shards (enabled stages, priority order) -> AR.

Runs inside a Slurm GPU step: either an `srun --overlap` step on the borrowed allocation
(--guard-job 25832889: the board guard is checked before every batch / unit) or our own
${SLURM_PREEMPT_PARTITION} job (--max-seconds bounds the run; SIGTERM finishes the current batch, then exits).

Units of loss: generation = one batch (~35 s at 256 sequences); AR = one 16,384-vector shard
(~2.8 min); capture = one 32-item shard. Everything else resumes from journals/claims.

Stages are enabled in data/control/stages.json ({"enabled": ["p0", "ca", ...]}), so UM Tier A
starts only after the P0 site decision, and Tier B only after the go/no-go.

Exit codes: 0 = nothing left for this worker; 3 = stopped by board guard; 4 = stopped by
deadline/signal; 5 = waiting for capture timed out.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
from claims import try_claim  # noqa: E402
import gen_worker as GW  # noqa: E402

LOGDIR = C.DATA / 'logs'


def make_log(tag):
    LOGDIR.mkdir(parents=True, exist_ok=True)
    path = LOGDIR / f'worker-{tag}.log'

    def log(msg):
        line = f'{time.strftime("%F %T")} [{tag}] {msg}'
        print(line, flush=True)
        with path.open('a') as f:
            f.write(line + '\n')
    return log


def capture_complete() -> bool:
    p = C.DATA / 'capture/capture_state.json'
    if not p.exists():
        return False
    st = json.loads(p.read_text())
    return st.get('status') == 'complete' and st['manifest_sha256'] == C.file_sha(C.DATA / 'manifests/capture.json')


def run_capture(ctx, log) -> str:
    if capture_complete():
        return 'complete'
    claim = try_claim(C.DATA / 'claims/capture.json', {'phase': 'capture'})
    if claim is None:
        log('capture claimed by another worker; waiting')
        t0 = time.time()
        while time.time() - t0 < 1200:
            if capture_complete():
                return 'complete'
            if ctx.stop_reason or not ctx.may_start_batch():
                return f'stopped:{ctx.stop_reason}'
            time.sleep(30)
        return 'timeout'
    try:
        env = dict(os.environ, PYTHONPATH=f'{C.OI}/src:{C.OI}/scripts', HF_HUB_OFFLINE='1',
                   TRANSFORMERS_OFFLINE='1')
        cmd = [C.PYTHON, '-B', str(C.OI / 'scripts/capture_cells.py'), '--runtime', str(C.RUNTIME),
               '--manifest', str(C.DATA / 'manifests/capture.json'), '--adapter', str(C.ADAPTER),
               '--output', str(C.DATA / 'capture')]
        log('capture: ' + ' '.join(cmd))
        proc = subprocess.Popen(cmd, env=env, cwd=str(C.OI))
        while proc.poll() is None:
            time.sleep(10)
            claim.heartbeat()
            if ctx.guard is not None:
                ok, hard, soft = ctx.guard.check()
                if not ok:
                    ctx.request_stop(f'board guard: {hard or soft}')
            if ctx.stop_reason == 'signal' or (ctx.stop_reason or '').startswith('board guard'):
                proc.terminate()
                try:
                    proc.wait(60)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return f'stopped:{ctx.stop_reason}'
        if proc.returncode != 0:
            raise RuntimeError(f'capture_cells.py rc={proc.returncode}')
        return 'complete' if capture_complete() else 'incomplete'
    finally:
        claim.release()


def generation_pass(ctx, log, cap, yield_after_stage=False) -> tuple[bool, str | None]:
    """Try every unclaimed incomplete shard of the enabled stages. -> (did_work, stop).
    yield_after_stage: return as soon as a stage in which this worker completed shards is done,
    so the caller AR-encodes that stage (CA) before generating the next one (UM)."""
    did = False
    order = [s for s in C.STAGES if s in C.enabled_stages()]
    for stage in order:
        fam, n, count = C.STAGES[stage]
        for i in range(count):
            if GW.shard_status(stage, i).get('status') == 'complete':
                continue
            r = GW.run_shard(stage, i, ctx, cap=cap)
            log(f'{stage} shard {i}: {r}')
            if r.startswith('stopped'):
                return True, r
            did = did or r == 'complete'
        if did and yield_after_stage:
            return did, None
    return did, None


def ar_pass(ctx, log) -> tuple[bool, str | None]:
    import ar_worker as AW
    pending = AW.pending_journals([s for s in AW.AR_STAGES if s in C.enabled_stages()])
    if not pending:
        return False, None
    ctx.release_lens()
    did = False
    for journal in pending:
        if not ctx.may_start_batch():
            return did, f'stopped:{ctx.stop_reason}'
        if ctx.deadline is not None and time.monotonic() + 1200 > ctx.deadline:  # one journal <= ~16 min
            return did, 'stopped:deadline'
        try:
            ctx.ar, _ = AW.encode_journal(journal, getattr(ctx, 'ar', None), log)
            did = True
        except BlockingIOError:
            log('AR cache lock held by another worker; skipping AR')
            return did, None
    return did, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--guard-job', default=None, help='borrowed allocation to guard (e.g. 25832889)')
    ap.add_argument('--max-seconds', type=float, default=None)
    ap.add_argument('--phases', default='capture,gen,ar')
    ap.add_argument('--max-batch-sequences', type=int, default=256)
    args = ap.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise SystemExit('run inside a Slurm GPU step')
    tag = f'{os.environ.get("SLURM_JOB_ID")}.{os.environ.get("SLURM_STEP_ID", "b")}.r{os.environ.get("SLURM_RESTART_COUNT", "0")}'
    log = make_log(tag)
    guard = None
    if args.guard_job:
        from board_guard import BoardGuard
        guard = BoardGuard(args.guard_job)
    deadline = time.monotonic() + args.max_seconds if args.max_seconds else None
    ctx = GW.Context(max_batch_sequences=args.max_batch_sequences, deadline=deadline, guard=guard, log=log)
    if os.environ.get('NT_FAKE_MODELS') == '1':  # CPU tests only: fake sampler + fake AR from tests/fixture_lib
        if not os.environ.get('NT_DATA'):
            raise SystemExit('NT_FAKE_MODELS requires an NT_DATA fixture root')
        sys.path.insert(0, str(C.CODE / 'tests'))
        import fixture_lib as FL
        sample, single = FL.fake_sampler(lambda layer: FL.UM_BULLETS + FL.CA_BULLETS)
        ctx.sampler, ctx.single_sampler = sample, single
        ctx.lens_loader = lambda: (FL.FakeLens(), {'fake': True})
        ctx.ar = FL.FakeAR()
        ctx.keep_ar = True

    def on_signal(signum, _frame):
        log(f'signal {signum}: finishing the current batch, then exiting')
        ctx.request_stop('signal')
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    phases = set(args.phases.split(','))
    try:
        import torch
        if not torch.cuda.is_available() and os.environ.get('NT_FAKE_MODELS') != '1':
            raise SystemExit('no CUDA device visible in this step')
        log(f'start host={os.uname().nodename} gpu={torch.cuda.get_device_name(0)} '
            f'mem={torch.cuda.get_device_properties(0).total_memory / 2**30:.0f}GiB phases={sorted(phases)} '
            f'stages={C.enabled_stages()}')
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f'start (no torch cuda info: {e})')
    if 'capture' in phases:
        r = run_capture(ctx, log)
        log(f'capture: {r}')
        if r != 'complete':
            sys.exit(3 if 'board guard' in r else 4 if r.startswith('stopped') else 5)
    elif not capture_complete():
        log('capture incomplete and not in phases; nothing to do')
        sys.exit(5)
    cap = GW.capture_index()
    stop = None
    while stop is None:
        did_gen, stop = (generation_pass(ctx, log, cap, yield_after_stage='ar' in phases)
                         if 'gen' in phases else (False, None))
        if stop:
            break
        did_ar, stop = ar_pass(ctx, log) if 'ar' in phases else (False, None)
        if not did_gen and not did_ar:
            break
    log(f'exit: stop={stop} stop_reason={ctx.stop_reason}')
    if stop and 'board guard' in stop:
        sys.exit(3)
    if stop:
        sys.exit(4)


def remaining() -> dict:
    """Read-only: what work is left (used by the sbatch chain to decide on resubmission)."""
    import ar_worker as AW
    out = {'capture_complete': capture_complete(), 'gen_incomplete': [], 'ar_pending': []}
    for stage in C.STAGES:
        if stage not in C.enabled_stages():
            continue
        fam, n, count = C.STAGES[stage]
        for i in range(count):
            if GW.shard_status(stage, i).get('status') != 'complete':
                out['gen_incomplete'].append(f'{stage}:{i}')
    if out['capture_complete']:
        out['ar_pending'] = [str(p) for p in AW.pending_journals([s for s in AW.AR_STAGES if s in C.enabled_stages()])]
    out['work_left'] = (not out['capture_complete']) or bool(out['gen_incomplete'] or out['ar_pending'])
    return out


if __name__ == '__main__':
    if sys.argv[1:2] == ['remaining']:
        r = remaining()
        print(json.dumps(r))
        sys.exit(0 if r['work_left'] else 1)
    main()
