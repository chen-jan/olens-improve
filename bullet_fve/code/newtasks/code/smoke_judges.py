"""Smoke: exactly ONE real API call per judge type, in one process, through the production code paths.

  1. UM readout judge   : WSB user_modeling runner (um-v2) on a 1-row readouts file (judge_um.judge_args,
                          OI install_shared_verdict_cache), Combine 32 text of one cell.
  2. CA readout judge   : WSB conjunctive_association runner (comp-v1, per item) on one item's cells for one
                          setting (judge_ca.item_args, layers = the smoke layers so the item is not excluded).
  3. CA bullet labels   : label_ca_llm (nt-ca-bullet-v1) for one cell: one batched call.
Ledger: the private newtasks ledger (budget_guard: $30 hard cap), run id nt-smoke-v1 (cap $0.05).
WSB's once-per-process preflight call ("Reply JSON") is pre-marked as done, so exactly 3 calls go out
(attempts=2 in OI's transport: a failed attempt may be retried once and is then also on the ledger).

Run with NT_DATA = the smoke root.  python -B smoke_judges.py --allow-paid --key-source oi-load-key
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
import budget_guard as BG  # noqa: E402

RUN_ID = 'nt-smoke-v1'
UM_CELL = ('um-sd-country-10', 36, 'final punctuation')
CA_ITEM, CA_SETTING = 'q01_a', 'pooled_greedy_swap-n32'
LABEL_CELL = ('q01_b', 52, 'final .')
SMOKE_LAYERS = [36, 52]


def ledger_rows(since_utc=None):
    db = sqlite3.connect(f'file:{BG.LEDGER}?mode=ro', uri=True, timeout=30)
    try:
        rows = db.execute('SELECT attempt_id, status, reserved, actual, metadata, created_utc FROM attempts '
                          'WHERE run_id=? ORDER BY created_utc', (RUN_ID,)).fetchall()
        ev = db.execute('SELECT attempt_id, kind, details FROM events ORDER BY sequence').fetchall()
    finally:
        db.close()
    events = {}
    for aid, kind, det in ev:
        events.setdefault(aid, []).append({'kind': kind, 'details': json.loads(det)})
    return [{'attempt_id': a, 'status': s, 'reserved_usd': r / 1e9, 'actual_usd': (x or 0) / 1e9,
             'metadata': json.loads(m), 'created_utc': t, 'events': events.get(a, [])} for a, s, r, x, m, t in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--allow-paid', action='store_true')
    ap.add_argument('--key-source', choices=('env', 'oi-load-key'), default='env')
    args = ap.parse_args()
    if C.DATA.resolve() == (C.NT / 'data').resolve():
        raise SystemExit('NT_DATA must be the smoke root')
    if not args.allow_paid:
        raise SystemExit('refusing without --allow-paid')
    import judge_ca
    import judge_um
    import label_ca_llm as LC
    from wsbench import mcjudge
    from wsbench.cache import Cache
    from wsbench.judge_config import JudgeConfig, resolve
    from wsbench.llm import Spend
    from wsbench.results import write_results
    out = C.DATA / 'judge_smoke'
    out.mkdir(parents=True, exist_ok=True)
    um3 = list(C.read_jsonl(C.DATA / 'select/um_three_settings.jsonl'))
    ca3 = list(C.read_jsonl(C.DATA / 'select/ca_three_settings.jsonl'))
    um_row = next(r for r in um3 if (r['item_id'], r['layer'], r['read_position_kind']) == UM_CELL)
    lab_row = next(r for r in ca3 if (r['item_id'], r['layer'], r['read_position_kind']) == LABEL_CELL)
    print(json.dumps(BG.preflight(RUN_ID, 3, 0.0004)))
    ledger = BG.prepare_paid(RUN_ID, args.key_source)
    report = {'run_id': RUN_ID, 'calls': {}}

    # 1. UM
    from olens_improve import evaluation
    evaluation.install_shared_verdict_cache(out / 'um' / 'shared_exact_cache.sqlite3', ledger, 'user_modeling')
    d = out / 'um'
    d.mkdir(parents=True, exist_ok=True)
    sid = 'pooled_greedy_swap-n32'
    rows = [{'id': um_row['item_id'], 'layer': um_row['layer'], 'pos': um_row['position'], 'token': um_row['token'],
             'samples': [um_row['settings'][sid]['text']]}]
    judge_um.write_readouts(d / 'readouts.jsonl', rows)
    spec, jargs = judge_um.judge_args(d / 'readouts.jsonl', d, False, 1, 60)
    mcjudge._PREFLIGHTED.add(mcjudge.preflight_key(jargs.judge.model, jargs.judge.reasoning))
    t0 = time.time()
    res = spec.run(jargs)
    write_results(d, res)
    crow = judge_um.cell_rows(res.rows, rows)
    report['calls']['um'] = {'cell_id': um_row['cell_id'], 'setting': sid, 'text': rows[0]['samples'][0],
                             'judge': {'model': jargs.judge.model, 'reasoning': jargs.judge.reasoning},
                             'row': crow, 'counts': res.counts, 'seconds': round(time.time() - t0, 2)}
    print(json.dumps(report['calls']['um'], ensure_ascii=False, default=str))

    # 2. CA per item
    evaluation.install_shared_verdict_cache(out / 'ca' / 'shared_exact_cache.sqlite3', ledger,
                                            'conjunctive_association')
    d = out / 'ca'
    d.mkdir(parents=True, exist_ok=True)
    rows = judge_ca.readouts([r for r in ca3 if r['item_id'] == CA_ITEM], CA_SETTING)
    C.atomic_text(d / 'readouts.jsonl', ''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows))
    spec, jargs = judge_ca.item_args(d / 'readouts.jsonl', d, False, 1, 60)
    jargs = dataclasses.replace(jargs, layers=SMOKE_LAYERS)
    mcjudge._PREFLIGHTED.add(mcjudge.preflight_key(jargs.judge.model, jargs.judge.reasoning))
    t0 = time.time()
    res = spec.run(jargs)
    write_results(d, res)
    report['calls']['ca_item'] = {'item_id': CA_ITEM, 'setting': CA_SETTING, 'cells_in_blob': len(rows),
                                  'value': res.value, 'extras': res.extras, 'counts': res.counts,
                                  'rows': res.rows, 'seconds': round(time.time() - t0, 2)}
    print(json.dumps(report['calls']['ca_item'], ensure_ascii=False, default=str)[:3000])

    # 3. CA bullet labels (one cell)
    bank = C.load_bank('conjunctive_association')
    calls = LC.build_calls([lab_row], bank)[:1]
    judge = resolve(JudgeConfig(prompt_version=LC.VERSION), flag='gpt-6-luna', env={'WSBENCH_OPENAI_REASONING': 'none'})
    mcjudge._PREFLIGHTED.add(mcjudge.preflight_key(judge.model, judge.reasoning))
    d = out / 'ca_labels'
    d.mkdir(parents=True, exist_ok=True)
    n = len(calls[0].meta['bullets'])
    t0 = time.time()
    with Cache(d / 'cells.jsonl') as cache:
        r = mcjudge.run_calls(calls, schema=LC.schema(), judge=judge, prompt_version=LC.VERSION, cache=cache,
                              spend=Spend(), concurrency=1, rpm=60, dry_run=False,
                              preflight=mcjudge.Preflighter(False).for_judge(judge), validate=LC.validate(n),
                              temperature=0.0, max_tokens=LC.MAX_TOKENS)
    res = r.get(calls[0].key)
    labels = []
    if res is not None:
        for e in sorted(res['labels'], key=lambda x: x['bullet']):
            lab = LC.map_label(e, calls[0].meta['a_is_gold'])
            labels.append({'bullet_index': e['bullet'], 'text': calls[0].meta['bullets'][e['bullet'] - 1],
                           'label': lab, '3way': LC.three_way(lab), **{k: e[k] for k in ('differs', 'shared',
                                                                                          'conflicts', 'quote')}})
    report['calls']['ca_label'] = {'cell_id': lab_row['cell_id'], 'n_bullets': n, 'a_is_gold': calls[0].meta['a_is_gold'],
                                   'valid': res is not None, 'labels': labels, 'seconds': round(time.time() - t0, 2)}
    print(json.dumps(report['calls']['ca_label'], ensure_ascii=False, indent=1))
    report['ledger_attempts'] = ledger_rows()
    report['ledger'] = BG.report(RUN_ID)
    C.atomic_json(out / 'smoke_judges.json', report)
    print(json.dumps({'ledger': report['ledger'], 'attempts': [{k: a[k] for k in ('status', 'reserved_usd', 'actual_usd',
                                                                                   'created_utc')}
                                                                for a in report['ledger_attempts']]}, indent=1))


if __name__ == '__main__':
    main()
