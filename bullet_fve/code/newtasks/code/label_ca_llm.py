"""Conjunctive association: one batched LLM call per cell labelling each distinct bullet (nt-ca-bullet-v1).

Unit: the union of distinct bullets (stripped text, first-seen order Original -> Best of 32 ->
Combine 32) across the cell's three settings, so each bullet text gets one consistent label.
Prompt mirrors WSB comp-v1 (same naming rules, verbatim where possible); gold and contrast are shown
as A / B in a seeded order (A = gold iff seed_int("nt-ca-bullet-v1:<id>") is even); the gold is never
disclosed. GPT-6 Luna, reasoning none, temperature 0, through OI's budgeted transport
(budget_guard.prepare_paid: private ledger, $30 hard cap, run cap nt-ca-label-v1 = $3).
A call is valid only with exactly one entry per bullet (else stored as failed and retried next run).

Mapping: differs = gold side -> gold; = contrast side -> contrast; both -> mixed;
neither & conflicts -> other_wrong; neither & shared & not conflicts -> frame_only; else none.
3-way: gold / contrast / other (other = mixed | other_wrong | frame_only | none).

CLI: label_ca_llm.py --dry-run [--fixture F]    print one rendered prompt + token counts, no API
     label_ca_llm.py --allow-paid [--key-source env|oi-load-key] [--concurrency 32]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
import budget_guard as BG  # noqa: E402

VERSION = 'nt-ca-bullet-v1'
RUN_ID = 'nt-ca-label-v1'
MAX_TOKENS = 2000

SYSTEM = (
    "You label the bullets of a READOUT of an interpretability lens: text decoded from a language model's "
    "internal activations while it read a short story you cannot see (it may contain noise, fragments, or other "
    "languages). You are given two compositional descriptions, A and B, of what a character in the story feels, "
    "intends or believes. A and B share most of their content and differ in one respect. For EACH bullet, decide "
    "what it STATES. A bullet states a content ONLY if it names it directly, as the direct word(s) or an EXACT "
    "synonym (\"mourning\" names grief; \"wife\" names spouse; \"his little boy\" names her young child). A faithful "
    "translation into another language counts as naming it. Do NOT count content you can merely INFER from "
    "evidence, causes, scene details, or narrative (\"small sneakers\" do not name \"her young child\"), do NOT "
    "count related-but-different states (\"regret\" is not grief; \"worried\" is not relieved) or generic words too "
    "broad to name it (\"sad\", \"upset\"), and do NOT use world knowledge or plausibility to fill gaps. Judge each "
    "bullet on its own words only. Output only the JSON.")

USER = """DESCRIPTION A: {A}
DESCRIPTION B: {B}

BULLETS:
{bullets}

For every bullet give:
- "differs": "A" if the bullet states A's version of the respect in which A and B differ, "B" if it states B's version, "both" if it states both, "neither" otherwise;
- "shared": true if the bullet states any content that A and B share, else false;
- "conflicts": true if the bullet states a value that contradicts both A and B in some respect (a different feeling, intent, belief, person, relation or event), else false;
- "quote": a SHORT exact quote (a few words, VERBATIM) from the bullet supporting your labels, or "" if none."""


def schema():
    from wsbench.llm import schema_block
    entry = {'type': 'object', 'additionalProperties': False,
             'required': ['bullet', 'differs', 'shared', 'conflicts', 'quote'],
             'properties': {'bullet': {'type': 'integer'},
                            'differs': {'type': 'string', 'enum': ['A', 'B', 'both', 'neither']},
                            'shared': {'type': 'boolean'}, 'conflicts': {'type': 'boolean'},
                            'quote': {'type': 'string'}}}
    return schema_block('nt_ca_bullets', {'labels': {'type': 'array', 'items': entry}}, ['labels'])


def gold_is_a(item_id: str) -> bool:
    from wsbench.mc import seed_int
    return seed_int(f'{VERSION}:{item_id}') % 2 == 0


def cell_bullets(row) -> list[str]:
    """Distinct stripped bullet texts across the three settings, first-seen order."""
    seen, out = set(), []
    for sid in C.SETTINGS:
        for a in row['settings'][sid]['atoms']:
            t = a['text'].strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return out


def render(item, bullets):
    a_is_gold = gold_is_a(item['id'])
    A, B = (item['gold_label'], item['contrast_label']) if a_is_gold else (item['contrast_label'], item['gold_label'])
    body = '\n'.join(f'[{i + 1}] {b}' for i, b in enumerate(bullets))
    return USER.replace('{A}', A).replace('{B}', B).replace('{bullets}', body), a_is_gold


def validate(n):
    def ok(_call, r):
        labels = r.get('labels') if isinstance(r, dict) else None
        if not isinstance(labels, list) or len(labels) != n:
            return False
        if sorted(x.get('bullet') for x in labels if isinstance(x, dict)) != list(range(1, n + 1)):
            return False
        return all(x.get('differs') in ('A', 'B', 'both', 'neither') and isinstance(x.get('shared'), bool)
                   and isinstance(x.get('conflicts'), bool) for x in labels)
    return ok


def map_label(entry, a_is_gold) -> str:
    d = entry['differs']
    if d == 'both':
        return 'mixed'
    if d in ('A', 'B'):
        return 'gold' if (d == 'A') == a_is_gold else 'contrast'
    if entry['conflicts']:
        return 'other_wrong'
    if entry['shared']:
        return 'frame_only'
    return 'none'


def three_way(label: str) -> str:
    return label if label in ('gold', 'contrast') else 'other'


def build_calls(rows, bank):
    from wsbench.mcjudge import Call
    calls = []
    for row in rows:
        bullets = cell_bullets(row)
        if not bullets:
            continue
        item = bank[row['item_id']]
        user, a_is_gold = render(item, bullets)
        calls.append(Call(row['cell_id'], SYSTEM, user, {'cell_id': row['cell_id'], 'item_id': row['item_id'],
                                                         'bullets': bullets, 'a_is_gold': a_is_gold}))
    return calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--three-settings', default=str(C.DATA / 'select/ca_three_settings.jsonl'))
    ap.add_argument('--out', default=str(C.DATA / 'judge/ca_labels'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--allow-paid', action='store_true')
    ap.add_argument('--key-source', choices=('env', 'oi-load-key'), default='env')
    ap.add_argument('--concurrency', type=int, default=32)
    ap.add_argument('--rpm', type=float, default=2000)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    from wsbench.cache import Cache
    from wsbench.judge_config import JudgeConfig, resolve
    from wsbench.llm import Spend
    from wsbench.mcjudge import Preflighter, run_calls
    bank = C.load_bank('conjunctive_association')
    rows = list(C.read_jsonl(args.three_settings))
    calls = build_calls(rows, bank)
    if args.limit:
        calls = calls[:args.limit]
    judge = resolve(JudgeConfig(prompt_version=VERSION), flag='gpt-6-luna', env={'WSBENCH_OPENAI_REASONING': 'none'})
    sch = schema()
    if args.dry_run:
        c = calls[0]
        n_in = BG.qwen_tokens([c.system, c.user, json.dumps(sch)])
        print(f'--- {VERSION} prompt for {c.key} (model={judge.model}, reasoning={judge.reasoning}) ---')
        print('[system]\n' + c.system + '\n[user]\n' + c.user)
        bullets_per_call = [len(x.meta['bullets']) for x in calls]
        print(json.dumps({'calls': len(calls), 'bullets': sum(bullets_per_call),
                          'qwen_tokens_system_user_schema': n_in, 'qwen_tokens_total': sum(n_in),
                          'reservation_per_attempt': BG.reservation_bound(c.system, c.user, sch, MAX_TOKENS),
                          'projected_usd': round(len(calls) * BG.EST_PER_CALL['ca_label'], 4)}, indent=1))
        return
    if not args.allow_paid:
        raise SystemExit('refusing: paid run needs --allow-paid (use --dry-run to inspect)')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with Cache(out / 'cells.jsonl') as cache:
        pending = [c for c in calls if cache.get(c.key, _fp(judge, c)) is None]
    print(json.dumps(BG.preflight(RUN_ID, len(pending), BG.EST_PER_CALL['ca_label'])))
    BG.prepare_paid(RUN_ID, args.key_source)
    spend = Spend()
    results = {}
    by_n = {}
    for c in calls:  # one validate closure per bullet count
        by_n.setdefault(len(c.meta['bullets']), []).append(c)
    with Cache(out / 'cells.jsonl') as cache:
        for n, group in sorted(by_n.items()):
            results.update(run_calls(group, schema=sch, judge=judge, prompt_version=VERSION, cache=cache, spend=spend,
                                     concurrency=args.concurrency, rpm=args.rpm, dry_run=False,
                                     preflight=Preflighter(False).for_judge(judge), validate=validate(n),
                                     temperature=0.0, max_tokens=MAX_TOKENS))
    n_ok = 0
    with open(out / 'ca_llm_bullet_labels.jsonl', 'w') as f:
        for c in calls:
            r = results.get(c.key)
            if r is None:
                continue
            n_ok += 1
            for e in sorted(r['labels'], key=lambda x: x['bullet']):
                lab = map_label(e, c.meta['a_is_gold'])
                f.write(json.dumps({'cell_id': c.key, 'item_id': c.meta['item_id'], 'bullet_index': e['bullet'],
                                    'text': c.meta['bullets'][e['bullet'] - 1], 'label': lab, '3way': three_way(lab),
                                    'differs': e['differs'], 'shared': e['shared'], 'conflicts': e['conflicts'],
                                    'quote': e['quote'], 'a_is_gold': c.meta['a_is_gold']}, ensure_ascii=False) + '\n')
    summary = {'calls': len(calls), 'labelled_cells': n_ok, 'failed': len(calls) - n_ok, 'spend_wsb_estimate_usd': spend.usd,
               'ledger': BG.report(RUN_ID)}
    C.atomic_json(out / 'summary.json', summary)
    print(json.dumps(summary, indent=1))


def _fp(judge, c):
    from wsbench.cache import fingerprint
    return fingerprint(VERSION, judge.model, judge.reasoning, 0.0, c.system, c.user)


if __name__ == '__main__':
    main()
