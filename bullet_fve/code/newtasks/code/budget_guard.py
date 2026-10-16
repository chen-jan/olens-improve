"""Judge-call budget guard: a PRIVATE OI AtomicBudget ledger with a $30 hard cap and frozen run caps.

- Ledger: newtasks/budget/ledger.sqlite3, AtomicBudget(hard_usd=30, target_usd=20, bootstrap_claude=False).
  OI's BudgetedClient reserves every physical attempt atomically BEFORE dispatch (standard price,
  input upper bound at the cache-write rate + max_completion_tokens), so neither the $30 hard cap
  nor a run cap can be passed: the reservation fails and the call is never sent.
- Run caps (frozen once set): nt-p0-v1 $1, nt-um-judge-v1 $6, nt-ca-judge-v1 $3, nt-ca-label-v1 $3.
- Before any paid batch, `preflight()` projects n_calls x est $/call x 1.3 and refuses if that would
  pass the run cap or the hard cap given what is already committed.
- Transport: OI evaluation.install_upstream_transport(ledger, run_id, allow_paid=True,
  service_tier='default') -> WSB llm._make_client = make_luna_client -> BudgetedClient (GPT-6 Luna,
  reasoning none). Every WSB judge call (and our label calls through wsbench.mcjudge.run_calls) goes through it.
- Environment: OPENAI_API_KEY must be set (key_source='env', default; we never read or print it) or,
  only if the user allows it, key_source='oi-load-key' calls OI scripts/expanded_api.load_key(),
  which reads OI/.env inside the process exactly as expanded_judges.py does. OPENAI_BASE_URL must be
  unset (make_luna_client refuses it). OLENS_ALLOW_PAID_CALLS=1 is set here only for a paid run.
"""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()

LEDGER = C.NT / 'budget/ledger.sqlite3'
HARD_USD, TARGET_USD = '30', '20'
RUN_CAPS = {'nt-p0-v1': '1', 'nt-um-judge-v1': '6', 'nt-ca-judge-v1': '3', 'nt-ca-label-v1': '3',
            'nt-smoke-v1': '0.05'}  # smoke: 3 real calls, one per judge type
# $/call estimates from DESIGN.md section 7.2 (Luna standard prices, measured token counts)
EST_PER_CALL = {'um': 0.00020, 'p0': 0.00020, 'ca_item': 0.00037, 'ca_cell': 0.000087, 'ca_label': 0.00024}
MARGIN = 1.3


class BudgetRefused(RuntimeError):
    pass


def open_ledger(path=LEDGER):
    from olens_improve.budget import AtomicBudget
    return AtomicBudget(path, hard_usd=HARD_USD, target_usd=TARGET_USD, bootstrap_claude=False)


def run_committed_usd(path, run_id) -> float:
    if not Path(path).exists():
        return 0.0
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=30)
    try:
        v = db.execute("""SELECT COALESCE(SUM(CASE WHEN status='settled' THEN actual
                          WHEN status IN ('reserved','unknown') THEN reserved ELSE 0 END),0)
                          FROM attempts WHERE run_id=?""", (run_id,)).fetchone()[0]
    finally:
        db.close()
    return v / 1e9


def preflight(run_id: str, n_calls: int, est_per_call: float, path=LEDGER, margin=MARGIN) -> dict:
    """Refuse (BudgetRefused) if the projected spend would pass the run cap or the hard cap."""
    if run_id not in RUN_CAPS:
        raise BudgetRefused(f'unknown run id {run_id}; frozen run ids: {sorted(RUN_CAPS)}')
    ledger = open_ledger(path)
    snap = ledger.snapshot()
    run_spent = run_committed_usd(path, run_id)
    projected = n_calls * est_per_call * margin
    cap = float(RUN_CAPS[run_id])
    out = {'run_id': run_id, 'n_calls': n_calls, 'est_per_call_usd': est_per_call, 'margin': margin,
           'projected_usd': round(projected, 4), 'run_cap_usd': cap, 'run_committed_usd': round(run_spent, 6),
           'ledger_committed_usd': snap['committed_usd'], 'hard_usd': snap['hard_usd'],
           'remaining_hard_usd': snap['remaining_hard_usd'], 'halted': snap['halted']}
    if snap['halted']:
        raise BudgetRefused(f'ledger halted: {out}')
    if run_spent + projected > cap:
        raise BudgetRefused(f'projected run spend {run_spent + projected:.4f} > run cap {cap}: {out}')
    if snap['committed_usd'] + projected > float(HARD_USD):
        raise BudgetRefused(f'projected total {snap["committed_usd"] + projected:.4f} > hard cap {HARD_USD}: {out}')
    return out


def check_env(key_source: str) -> None:
    if os.environ.get('OPENAI_BASE_URL'):
        raise BudgetRefused('OPENAI_BASE_URL is set; make_luna_client refuses custom base URLs. Unset it.')
    if key_source == 'env':
        if not os.environ.get('OPENAI_API_KEY'):
            raise BudgetRefused('OPENAI_API_KEY is not set in this shell (key_source=env).')
    elif key_source == 'oi-load-key':
        cwd = os.getcwd()
        try:
            os.chdir(C.OI)  # load_key reads ./.env relative to the OI root, inside this process only
            sys.path.insert(0, str(C.OI / 'scripts'))
            from expanded_api import load_key
            load_key()
        finally:
            os.chdir(cwd)
        if not os.environ.get('OPENAI_API_KEY'):
            raise BudgetRefused('OI load_key() did not provide OPENAI_API_KEY')
    else:
        raise BudgetRefused(f'unknown key source {key_source}')


def prepare_paid(run_id: str, key_source: str = 'env', path=LEDGER):
    """Ledger + frozen run cap + Luna transport for a paid run. Returns the ledger."""
    from olens_improve import evaluation
    check_env(key_source)
    evaluation.load_upstream()  # verifies the pinned WSB revision
    os.environ.update(OLENS_ALLOW_PAID_CALLS='1', OLENS_LEDGER_REUSE_WRITER_CONNECTION='1',
                      OLENS_LEDGER_RESERVATION_BATCH_SIZE='16')
    ledger = open_ledger(path)
    ledger.set_run_limit(run_id, RUN_CAPS[run_id])
    evaluation.install_upstream_transport(ledger, run_id, allow_paid=True, service_tier='default')
    return ledger


def report(run_id: str, path=LEDGER) -> dict:
    if not Path(path).exists():
        return {'run_id': run_id, 'ledger': 'absent'}
    snap = open_ledger(path).snapshot()
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=30)
    try:
        rows = db.execute('SELECT status, COUNT(*), SUM(actual), SUM(reserved) FROM attempts WHERE run_id=? '
                          'GROUP BY status', (run_id,)).fetchall()
    finally:
        db.close()
    return {'run_id': run_id, 'run_committed_usd': run_committed_usd(path, run_id),
            'run_attempts': {r[0]: {'n': r[1], 'actual_usd': (r[2] or 0) / 1e9, 'reserved_usd': (r[3] or 0) / 1e9}
                             for r in rows},
            'ledger': {k: snap[k] for k in ('committed_usd', 'actual_usd', 'reserved_usd', 'unknown_usd',
                                            'remaining_hard_usd', 'hard_usd', 'halted')}}


@contextlib.contextmanager
def no_network():
    """For dry runs and tests: any socket connect raises."""
    import socket
    saved = socket.socket.connect, socket.socket.connect_ex, socket.create_connection

    def forbidden(*_a, **_k):
        raise RuntimeError('network disabled (dry run)')
    socket.socket.connect = forbidden
    socket.socket.connect_ex = forbidden
    socket.create_connection = forbidden
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection = saved


def qwen_tokens(texts) -> list[int]:
    """Token-count proxy (Qwen tokenizer; the Luna tokenizer is not available offline)."""
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(str(C.BASE), local_files_only=True)
    return [len(tok(t, add_special_tokens=False)['input_ids']) for t in texts]


def reservation_bound(system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """What BudgetedClient would reserve for one physical attempt of this call."""
    from olens_improve.budget import cost_units, request_input_upper_bound
    req = {'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
           'response_format': {'type': 'json_schema', 'json_schema': schema}}
    bound = request_input_upper_bound(req)
    usd = cost_units(bound, max_tokens, cache_write_tokens=bound) / 1e9
    return {'input_upper_tokens': bound, 'max_completion_tokens': max_tokens, 'reserved_usd': usd}


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('report', 'snapshot'))
    ap.add_argument('--run-id', default='nt-um-judge-v1')
    a = ap.parse_args()
    print(json.dumps(report(a.run_id) if a.cmd == 'report' else open_ledger().snapshot(), indent=1))
