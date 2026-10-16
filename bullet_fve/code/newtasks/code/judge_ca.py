"""Conjunctive association readout judging with WSB's comp-v1 instrument (prompts/options/pick unchanged).

(a) --mode item : WSB's own family runner per setting: one 11-way MC per item over the blob of all
    the item's bags (5 sites x 5 layers; norm_token, " | ", [L{layer}], char_cap 200000). 3 x 100 calls.
(b) --mode cell : the same SYSTEM / QUESTION / USER, option order (COMP_SEED) and schema, with the blob
    of ONE cell = build_blob({L: bag}, [L]). Version comp-v1-percell, through wsbench.mcjudge.run_calls
    (same transport/cache/ledger). Identical (system, user) contents across settings are one call.
Both: GPT-6 Luna, reasoning none, via budget_guard.prepare_paid (run id nt-ca-judge-v1, $3 cap).
Not WSB numbers of record (WSB pin is google/gemini-3.8-flash; reduced grid).
Outputs: data/judge/ca/item/<setting>/ (WSB results + cells.jsonl), data/judge/ca/cell/ca_cell_rows.jsonl
{cell_id, setting, pick, choice, quote, quote_ok, quote_bullets}.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
import budget_guard as BG  # noqa: E402

PERCELL_VERSION = 'comp-v1-percell'
PARENT_CODE = C.NT.parent / 'code'


def readouts(three_rows, setting):
    return [{'id': r['item_id'], 'layer': r['layer'], 'pos': r['position'], 'token': r.get('token') or '',
             'samples': [r['settings'][setting]['text']]}
            for r in sorted(three_rows, key=lambda r: (r['item_id'], r['layer'], r['position']))]


def item_args(readouts_path, out, dry_run, concurrency, rpm):
    from wsbench.judge_config import resolve
    from wsbench.registry import JudgeArgs, get
    importlib.import_module('wsbench.evals.conjunctive_association')
    spec = get('conjunctive_association')
    judge = resolve(spec.judge, flag='gpt-6-luna', env={'WSBENCH_OPENAI_REASONING': 'none'})
    return spec, JudgeArgs(readouts=readouts_path, out=out, judge=judge, layers=list(C.LAYERS), items=None, limit=0,
                           allow_missing=True, concurrency=concurrency, rpm=rpm, dry_run=dry_run, aux_models={},
                           extra={'char_cap': '200000'})


def percell_calls(three_rows, bank):
    """-> (unique calls keyed by content, occurrences [(cell_id, setting, key|None, meta)])."""
    from wsbench.evals.conjunctive_association import prompts as P
    from wsbench.evals.conjunctive_association.judge import DEFAULT_CHAR_CAP, build_blob, build_options, norm_token
    from wsbench.mcjudge import Call
    unique, occ = {}, []
    for r in three_rows:
        item = bank[r['item_id']]
        shown, gold_pos, contrast_pos = build_options(item)
        for sid in C.SETTINGS:
            text = r['settings'][sid]['text']
            bag = norm_token(text)  # build_bags: " | ".join(norm_token(s) for s in [text])
            meta = {'id': r['item_id'], 'gold_pos': gold_pos, 'contrast_pos': contrast_pos, 'n_shown': len(shown)}
            if not bag.strip():
                occ.append((r['cell_id'], sid, None, meta, ''))
                continue
            blob = build_blob({r['layer']: bag}, [r['layer']], DEFAULT_CHAR_CAP)
            user = P.render_user(blob, P.render_question(shown))
            key = 'pc:' + hashlib.sha256((P.SYSTEM + '\x00' + user).encode()).hexdigest()[:32]
            unique.setdefault(key, Call(key, P.SYSTEM, user, meta))
            occ.append((r['cell_id'], sid, key, meta, blob))
    return unique, occ


def quote_bullets(text, quote):
    sys.path.append(str(PARENT_CODE))
    from span_locate import bullet_index, bullets_with_offsets, locate
    hits = locate(text, quote) if quote else []
    return sorted({k for s, e, _ in hits for k in bullet_index(bullets_with_offsets(text), s, e)}), bool(hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('item', 'cell', 'both'), default='both')
    ap.add_argument('--three-settings', default=str(C.DATA / 'select/ca_three_settings.jsonl'))
    ap.add_argument('--out', default=str(C.DATA / 'judge/ca'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--allow-paid', action='store_true')
    ap.add_argument('--key-source', choices=('env', 'oi-load-key'), default='env')
    ap.add_argument('--concurrency', type=int, default=32)
    ap.add_argument('--rpm', type=float, default=2000)
    args = ap.parse_args()
    from wsbench.cache import Cache
    from wsbench.evals.conjunctive_association import prompts as P
    from wsbench.llm import Spend
    from wsbench.mc import classify
    from wsbench.mcjudge import Preflighter, choice_of, quote_of, run_calls
    from wsbench.results import write_results
    three = list(C.read_jsonl(args.three_settings))
    bank = C.load_bank('conjunctive_association')
    out = Path(args.out)
    modes = ('item', 'cell') if args.mode == 'both' else (args.mode,)
    unique, occ = percell_calls(three, bank)
    n_item_calls = len(C.SETTINGS) * len({r['item_id'] for r in three})
    if args.dry_run:
        with BG.no_network():
            if 'item' in modes:
                d = out / 'item' / C.SETTINGS[0]
                d.mkdir(parents=True, exist_ok=True)
                rows = readouts(three, C.SETTINGS[0])
                C.atomic_text(d / 'readouts.jsonl', ''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows))
                spec, jargs = item_args(d / 'readouts.jsonl', d / 'dry', True, args.concurrency, args.rpm)
                res = spec.run(jargs)
                print(json.dumps({'mode': 'item', 'counts': res.counts, 'pinned_instrument': res.pinned_instrument}))
            if 'cell' in modes:
                spec, jargs = item_args(out / 'x', out / 'x', True, 1, 1)
                calls = list(unique.values())
                run_calls(calls[:1], schema=P.SCHEMA, judge=jargs.judge, prompt_version=PERCELL_VERSION,
                          cache=None, spend=Spend(), concurrency=1, rpm=1, dry_run=True)
        _print_cost(three, bank, unique, occ, n_item_calls)
        return
    if not args.allow_paid:
        raise SystemExit('refusing: paid run needs --allow-paid (use --dry-run to inspect)')
    n = (n_item_calls if 'item' in modes else 0) + (len(unique) if 'cell' in modes else 0)
    est = ((n_item_calls * BG.EST_PER_CALL['ca_item'] if 'item' in modes else 0)
           + (len(unique) * BG.EST_PER_CALL['ca_cell'] if 'cell' in modes else 0)) / max(n, 1)
    print(json.dumps(BG.preflight('nt-ca-judge-v1', n, est)))
    ledger = BG.prepare_paid('nt-ca-judge-v1', args.key_source)
    summary = {}
    if 'item' in modes:
        from olens_improve import evaluation
        evaluation.install_shared_verdict_cache(out / 'item' / 'shared_exact_cache.sqlite3', ledger,
                                                'conjunctive_association')
        for sid in C.SETTINGS:
            d = out / 'item' / sid
            d.mkdir(parents=True, exist_ok=True)
            rows = readouts(three, sid)
            C.atomic_text(d / 'readouts.jsonl', ''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows))
            spec, jargs = item_args(d / 'readouts.jsonl', d, False, args.concurrency, args.rpm)
            res = spec.run(jargs)
            write_results(d, res)
            summary[f'item:{sid}'] = {'pass_rate_reduced_grid': res.value, 'breakdown': res.extras.get('breakdown'),
                                      'counts': res.counts, 'pinned_instrument': res.pinned_instrument}
            print(json.dumps({sid: summary[f'item:{sid}']}, default=str))
    if 'cell' in modes:
        spec, jargs = item_args(out / 'x', out / 'x', False, args.concurrency, args.rpm)
        d = out / 'cell'
        d.mkdir(parents=True, exist_ok=True)
        with Cache(d / 'cells.jsonl') as cache:
            res = run_calls(list(unique.values()), schema=P.SCHEMA, judge=jargs.judge, prompt_version=PERCELL_VERSION,
                            cache=cache, spend=Spend(), concurrency=args.concurrency, rpm=args.rpm, dry_run=False,
                            preflight=Preflighter(False).for_judge(jargs.judge))
        text_of = {(r['cell_id'], sid): r['settings'][sid]['text'] for r in three for sid in C.SETTINGS}
        rows, tally = [], collections.defaultdict(collections.Counter)
        for cid, sid, key, meta, blob in occ:
            if key is None:
                pick, choice, quote, ok = 'empty', None, '', False
            else:
                r = res.get(key)
                if r is None:
                    pick, choice, quote, ok = 'api_fail', None, '', False
                else:
                    choice, quote = choice_of(r), quote_of(r)
                    pick = classify(choice, meta['gold_pos'], meta['n_shown'], contrast_pos=meta['contrast_pos'])
                    ok = bool(quote) and ' '.join(quote.lower().split()) in ' '.join(blob.lower().split())
            qb, found = quote_bullets(text_of[(cid, sid)], quote)
            rows.append({'cell_id': cid, 'setting': sid, 'pick': pick, 'choice': choice, 'quote': quote,
                         'quote_ok': ok, 'quote_found_in_text': found, 'quote_bullets': qb, 'call_key': key})
            tally[sid][pick] += 1
        C.atomic_text(d / 'ca_cell_rows.jsonl', ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
        summary['cell'] = {sid: dict(c) for sid, c in tally.items()}
        summary['cell_unique_calls'] = len(unique)
    summary['ledger'] = BG.report('nt-ca-judge-v1')
    C.atomic_json(out / 'summary.json', summary)
    print(json.dumps(summary, indent=1, default=str))


def _print_cost(three, bank, unique, occ, n_item_calls):
    from wsbench.evals.conjunctive_association import prompts as P
    from wsbench.evals.conjunctive_association.judge import DEFAULT_CHAR_CAP, build_bags, build_blob, build_options
    from wsbench.readouts import Cell
    c = next(iter(unique.values()))
    tok_cell = BG.qwen_tokens([P.SYSTEM, c.user, json.dumps(P.SCHEMA)])
    # one per-item blob exactly as the family runner builds it (first item, first setting)
    item_id = sorted({r['item_id'] for r in three})[0]
    rows = [r for r in readouts(three, C.SETTINGS[0]) if r['id'] == item_id]
    bags = build_bags([Cell(r['id'], r['layer'], r['pos'], tuple(r['samples']), None, None) for r in rows])
    layers = sorted({r['layer'] for r in rows})
    blob = build_blob({L: bags[(item_id, L)] for L in layers}, layers, DEFAULT_CHAR_CAP)
    user_item = P.render_user(blob, P.render_question(build_options(bank[item_id])[0]))
    tok_item = BG.qwen_tokens([P.SYSTEM, user_item, json.dumps(P.SCHEMA)])
    print(json.dumps({'family': 'conjunctive_association',
                      'item_calls': n_item_calls, 'item_prompt_qwen_tokens_total': sum(tok_item),
                      'item_reservation_per_attempt': BG.reservation_bound(P.SYSTEM, user_item, P.SCHEMA, 8000),
                      'cell_occurrences': len(occ), 'cell_unique_calls': len(unique),
                      'cell_prompt_qwen_tokens_system_user_schema': tok_cell, 'cell_prompt_qwen_tokens_total': sum(tok_cell),
                      'cell_reservation_per_attempt': BG.reservation_bound(P.SYSTEM, c.user, P.SCHEMA, 8000),
                      'projected_usd': round(n_item_calls * BG.EST_PER_CALL['ca_item']
                                             + len(unique) * BG.EST_PER_CALL['ca_cell'], 4)}, indent=1))


if __name__ == '__main__':
    main()
