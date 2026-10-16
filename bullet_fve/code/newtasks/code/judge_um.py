"""User modelling readout judging with WSB's own um-v2 family runner (prompts, options, pick rules unchanged).

Judge: GPT-6 Luna, reasoning none, service tier default, through OI's budgeted transport
(budget_guard.prepare_paid; WSB pin is google/gemini-3.8-flash, so these are NOT WSB numbers of
record: pinned_instrument=false). OI evaluation.install_shared_verdict_cache makes identical
requests (same item + same readout text, e.g. when sample 0 is also the best) one call across settings.

--stage main : one readouts file per setting (one row per cell, samples=[selected text]); run
               wsbench.evals.user_modeling.judge.run with layers 20/36/44/52/60, all 100 items,
               allow_missing; run id nt-um-judge-v1 ($6 cap).
--stage p0   : the P0 pilot pool (raw texts, k=4 samples per cell); run id nt-p0-v1 ($1 cap).
Outputs (data/judge/um/<setting>/): WSB results JSON + cells.jsonl cache, readouts.jsonl, and
per-cell rows um_cell_rows.jsonl {cell_id, sample_idx, pick, basis, evidence, evidence_bullets}.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
import budget_guard as BG  # noqa: E402

PARENT_CODE = C.NT.parent / 'code'


def readouts_main(three_rows, setting):
    rows = []
    for r in sorted(three_rows, key=lambda r: (r['item_id'], r['layer'], r['position'])):
        rows.append({'id': r['item_id'], 'layer': r['layer'], 'pos': r['position'], 'token': r.get('token') or '',
                     'samples': [r['settings'][setting]['text']]})
    return rows


def readouts_p0():
    import generate_samples as G
    import gen_worker as GW
    man, cells, config, pool_id = GW.load_stage('p0')
    _, n, count = C.STAGES['p0']
    rows = []
    by_id = {c['cell_id']: c for c in cells}
    state = {}
    for i in range(count):
        journal, status, _ = GW.shard_paths('p0', i, count)
        state.update(G.read_journal(journal, pool_id))
    for cid in sorted(by_id, key=lambda k: (by_id[k]['item_id'], by_id[k]['layer'], by_id[k]['position'])):
        c = by_id[cid]
        samples = [state[cid][k]['text'] for k in range(n)]
        rows.append({'id': c['item_id'], 'layer': c['layer'], 'pos': c['position'], 'token': c['token'],
                     'samples': samples})
    return rows


def write_readouts(path, rows):
    C.atomic_text(path, ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))


def n_calls(rows):
    return sum(1 for r in rows for s in r['samples'] if s.strip())


def judge_args(readouts, out, dry_run, concurrency, rpm):
    import importlib
    from wsbench.judge_config import resolve
    from wsbench.registry import JudgeArgs, get
    importlib.import_module('wsbench.evals.user_modeling')
    spec = get('user_modeling')
    judge = resolve(spec.judge, flag='gpt-6-luna', env={'WSBENCH_OPENAI_REASONING': 'none'})
    return spec, JudgeArgs(readouts=readouts, out=out, judge=judge, layers=list(C.LAYERS), items=None, limit=0,
                           allow_missing=True, concurrency=concurrency, rpm=rpm, dry_run=dry_run, aux_models={},
                           extra={})


def evidence_bullets(text, evidence):
    sys.path.append(str(PARENT_CODE))
    from span_locate import bullet_index, bullets_with_offsets, locate
    bl = bullets_with_offsets(text)
    hits = locate(text, evidence) if evidence else []
    return sorted({k for s, e, _ in hits for k in bullet_index(bl, s, e)}), bool(hits)


def cell_rows(result_rows, readout_rows, three_by_key=None):
    text_of = {(r['id'], r['layer'], r['pos']): r['samples'] for r in readout_rows}
    out = []
    for v in result_rows:
        texts = text_of[(v['id'], v['layer'], v['pos'])]
        t = texts[v['sample_idx']]
        idx, found = evidence_bullets(t, v['evidence'])
        out.append({'cell_id': C.cell_id('user_modeling', v['id'], v['layer'], v['pos']), 'item_id': v['id'],
                    'layer': v['layer'], 'pos': v['pos'], 'sample_idx': v['sample_idx'], 'subfamily': v['subfamily'],
                    'pick': v['pick'], 'basis': v['basis'], 'pick_value': v['pick_value'],
                    'choice_invalid': v['choice_invalid'], 'evidence': v['evidence'], 'evidence_found': found,
                    'evidence_bullets': idx})
    return out


def summarize(rows, n_cells):
    from wsbench.evals.user_modeling.score import item_flags
    by_item = collections.defaultdict(list)
    for v in rows:
        by_item[v['item_id']].append(v)
    flags = {i: item_flags(vs) for i, vs in by_item.items()}
    picks = collections.Counter(v['pick'] for v in rows)
    inferred = sum(v['pick'] == 'gold' and v['basis'] == 'inferred_characterization' for v in rows)
    by_layer = collections.defaultdict(collections.Counter)
    for v in rows:
        by_layer[v['layer']][v['pick']] += 1
    return {'judged_rows': len(rows), 'cells': n_cells,
            'per_row': {'gold': picks['gold'] / len(rows) if rows else None,
                        'inferred': inferred / len(rows) if rows else None,
                        'distractor': picks['distractor'] / len(rows) if rows else None,
                        'cannot_tell': picks['cannot_tell'] / len(rows) if rows else None},
            'any_cell_items_reduced_grid': {k: sum(f[k] for f in flags.values()) for k in ('correct', 'inferred', 'distractor')},
            'n_items_with_rows': len(flags), 'picks': dict(picks),
            'by_layer': {L: dict(c) for L, c in sorted(by_layer.items())},
            'note': 'reduced grid, GPT-6 Luna; not a WSB number of record; any-of chance not comparable'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=('main', 'p0'), default='main')
    ap.add_argument('--three-settings', default=str(C.DATA / 'select/um_three_settings.jsonl'))
    ap.add_argument('--out', default=str(C.DATA / 'judge/um'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--allow-paid', action='store_true')
    ap.add_argument('--key-source', choices=('env', 'oi-load-key'), default='env')
    ap.add_argument('--concurrency', type=int, default=32)
    ap.add_argument('--rpm', type=float, default=2000)
    args = ap.parse_args()
    from wsbench.results import write_results
    out = Path(args.out) / ('p0' if args.stage == 'p0' else '')
    if args.stage == 'p0':
        jobs = {'p0': readouts_p0()}
        run_id, est = 'nt-p0-v1', BG.EST_PER_CALL['p0']
    else:
        three = list(C.read_jsonl(args.three_settings))
        jobs = {sid: readouts_main(three, sid) for sid in C.SETTINGS}
        run_id, est = 'nt-um-judge-v1', BG.EST_PER_CALL['um']
    total = sum(n_calls(r) for r in jobs.values())
    unique = len({(r['id'], s) for rows in jobs.values() for r in rows for s in r['samples'] if s.strip()})
    if args.dry_run:
        with BG.no_network():
            for name, rows in jobs.items():
                d = out / name
                d.mkdir(parents=True, exist_ok=True)
                write_readouts(d / 'readouts.jsonl', rows)
                spec, jargs = judge_args(d / 'readouts.jsonl', d / 'dry', True, args.concurrency, args.rpm)
                res = spec.run(jargs)
                print(json.dumps({'setting': name, 'calls': n_calls(rows), 'counts': res.counts,
                                  'pinned_instrument': res.pinned_instrument}))
                break  # one rendered prompt per family is enough
        _print_cost(jobs, total, unique, est)
        return
    if not args.allow_paid:
        raise SystemExit('refusing: paid run needs --allow-paid (use --dry-run to inspect)')
    print(json.dumps(BG.preflight(run_id, unique, est)))
    ledger = BG.prepare_paid(run_id, args.key_source)
    from olens_improve import evaluation
    evaluation.install_shared_verdict_cache(Path(args.out) / 'shared_exact_cache.sqlite3', ledger, 'user_modeling')
    summary = {}
    for name, rows in jobs.items():
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        write_readouts(d / 'readouts.jsonl', rows)
        spec, jargs = judge_args(d / 'readouts.jsonl', d, False, args.concurrency, args.rpm)
        res = spec.run(jargs)
        write_results(d, res)
        crow = cell_rows(res.rows, rows)
        C.atomic_text(d / 'um_cell_rows.jsonl', ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in crow))
        summary[name] = {'wsb': {'value_any_cell_inferred': res.value, 'extras': res.extras, 'counts': res.counts,
                                 'pinned_instrument': res.pinned_instrument},
                         'ours': summarize(crow, len(rows))}
        print(json.dumps({name: summary[name]['ours']}, default=str))
    summary['ledger'] = BG.report(run_id)
    C.atomic_json(out / 'summary.json', summary)


def _print_cost(jobs, total, unique, est):
    from wsbench.evals.user_modeling import prompts as P
    from wsbench.evals.user_modeling.judge import build_options
    bank = C.load_bank('user_modeling')
    opts = build_options(list(bank.values()))
    rows = next(iter(jobs.values()))
    r = next(x for x in rows if any(s.strip() for s in x['samples']))
    it = bank[r['id']]
    user = P.render_user(P.render_user_turn(it['messages']), r['samples'][0], opts[r['id']][0])
    toks = BG.qwen_tokens([P.UM_ATTRIBUTE_SYSTEM, user, json.dumps(P.UM_ATTRIBUTE_SCHEMA)])
    print(json.dumps({'family': 'user_modeling', 'calls_all_settings': total, 'distinct_item_text_pairs': unique,
                      'qwen_tokens_system_user_schema': toks, 'qwen_tokens_total': sum(toks),
                      'reservation_per_attempt': BG.reservation_bound(P.UM_ATTRIBUTE_SYSTEM, user, P.UM_ATTRIBUTE_SCHEMA, 8000),
                      'projected_usd_distinct': round(unique * est, 4), 'projected_usd_all': round(total * est, 4)},
                     indent=1))


if __name__ == '__main__':
    main()
