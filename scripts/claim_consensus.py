"""Prepare/preview a separate DEV claim-span pilot; only root dispatches paid runs."""
import argparse
import asyncio
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.claim_spans import (EXTRACT_VERSION, VERIFY_VERSION, EXTRACT_SYSTEM,
    VERIFY_SYSTEM, CLAIM_MATCH_VERSION, CLAIM_MATCH_SYSTEM, ClaimSpan, extract_verified_spans, span_relations, select_span_support,
    extraction_only, random_matched_spans)
from olens_improve.helpers import LunaHelper, HelperCache
from olens_improve.budget import AtomicBudget
from olens_improve.evaluation import make_luna_client, make_luna_helper_diagnostic_client
from olens_improve.selection import parse_bullets, output_admissible, render_bullets
from helper_pilot import CellProgress, atomic_text

SEED = 20261010
PILOT_SOURCE_SHA = '83ce478e1d309167126a9fd4165e24ac9aa450c607d2fee8f579092b1da55992'
FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')


def digest(path): return sha256(Path(path).read_bytes()).hexdigest()


def write_once(path, payload):
    if path.exists():
        if path.read_bytes() != payload: raise ValueError('Existing frozen artifact differs: ' + str(path))
        return
    path.write_bytes(payload); path.chmod(0o444)


def balanced_cells(cells):
    selected, audit = [], []
    for family in FAMILIES:
        remaining = [c for c in cells if c['family'] == family]
        if len(remaining) < 8: raise ValueError('Need eight existing cells per family')
        counts = {'group_id': {}, 'item_id': {}, 'layer': {}}
        chosen = []
        for _ in range(8):
            cell = min(remaining, key=lambda c: tuple(counts[k].get(c[k], 0)
                       for k in ('group_id', 'item_id', 'layer')) +
                       (sha256(f'{SEED}:{c["cell_id"]}'.encode()).hexdigest(),))
            remaining.remove(cell); chosen.append(cell)
            for k in counts: counts[k][cell[k]] = counts[k].get(cell[k], 0) + 1
        selected.extend(chosen); audit.extend(c['cell_id'] for c in chosen[:2])
    return selected, audit


def prepare(args):
    manifest = json.loads(args.manifest.read_text())
    if len(manifest['cells']) != 189 or any(c['split'] != 'development' for c in manifest['cells']):
        raise ValueError('Use the original frozen 189-cell DEV pilot')
    if digest(args.records) != PILOT_SOURCE_SHA: raise ValueError('Original immutable N32 pilot source differs')
    chosen, audit = balanced_cells(manifest['cells']); wanted = {c['cell_id'] for c in chosen}
    pools = {cid: {} for cid in wanted}
    for line in args.records.read_text().splitlines():
        row = json.loads(line); cid = row['cell_id']; index = row['sample_index']
        if cid not in wanted or index >= 16: continue
        if index in pools[cid]: raise ValueError('Duplicate source cell/sample')
        pools[cid][index] = row
    if any(set(pool) != set(range(16)) for pool in pools.values()): raise ValueError('Incomplete N16 prefix')
    parents = {r['cell_id']: r for r in map(json.loads, args.parents.read_text().splitlines())}
    whole = {r['cell_id']: r for r in map(json.loads, args.whole_bullet.read_text().splitlines())}
    inputs = []
    for cell in chosen:
        cid = cell['cell_id']; a = [r for r in parents[cid]['selections'] if r['method'] == 'best_n_exact' and r['n'] == 16]
        b = [r for r in whole[cid]['selections'] if r['method'] in (
             'consensus_semantic_v5_support0_compatoff_vetooff',
             'consensus_semantic_v5_support0.125_compatoff_vetooff') and r['n'] == 16]
        if len(a) != 1 or len(b) != 2: raise ValueError('Missing A16 or frozen whole-bullet B parents')
        inputs.append({'cell': cell, 'samples': [pools[cid][i] for i in range(16)],
                       'a16': a[0], 'whole_bullet_b': b})
    prepared_manifest = {'split': 'development', 'partial_grid': True, 'cells': chosen,
                         'audit_cell_ids': audit, 'selection_seed': SEED,
                         'selection_rule': 'Greedy balance related groups, items, layers; seeded hash tie-break; no scores/verdicts.'}
    args.output.mkdir(parents=True, exist_ok=True)
    write_once(args.output/'cells.json', (json.dumps(prepared_manifest, indent=2)+'\n').encode())
    write_once(args.output/'inputs.jsonl', ''.join(json.dumps(r)+'\n' for r in inputs).encode())
    spec = {'public_method': 'consensus over extracted claims', 'cells': 32, 'audit_cells': 8,
        'n': 16, 'manifest_sha256': digest(args.output/'cells.json'), 'inputs_sha256': digest(args.output/'inputs.jsonl'),
        'source_sha256': {str(p): digest(p) for p in (args.manifest, args.records, args.parents, args.whole_bullet)},
        'prompt_versions': [EXTRACT_VERSION, VERIFY_VERSION, CLAIM_MATCH_VERSION],
        'settings': {'extraction_effort': 'none', 'support_and_match_effort': 'medium', 'tier': 'default',
            'attempts': 1, 'request_slots': 4, 'cell_slots': 2, 'max_completion_tokens': 6000,
            'source_bullets_per_extraction_chunk': 32, 'source_span_checks_per_chunk': 16,
            'span_pairs_per_chunk': 20, 'max_pairs_per_cell': 40, 'max_spans_per_bullet': 2,
            'fractions': [0., .125], 'final_bullets': 4, 'Qwen_tokens': 256},
        'max_logical_calls_per_cell': 12, 'combined_helper_cap_usd': 2,
        'initial_forecast': 'Worst reserved output: 384 calls × 6000 tokens × $0.50/M = $1.152; input/cache-write costs additional. Actual requests and reasoning may be lower; hard shared run cap remains $2.',
        'code_sha256': {str(p): digest(p) for p in (Path(__file__), Path('src/olens_improve/claim_spans.py'),
                           Path('src/olens_improve/helpers.py'), Path('scripts/helper_pilot.py'))},
        'new_O_lens_samples': 0, 'AR_scores_for_new_spans': 'not computed or used by this consensus-only ablation'}
    if args.reused_proposals:
        reused = [json.loads(line) for line in args.reused_proposals.read_text().splitlines()]
        if len(reused) != 8 or {r['cell_id'] for r in reused} != set(audit):
            raise ValueError('Reused proposals must cover the unchanged original audit8 exactly')
        spec['reused_proposals'] = {'path': str(args.reused_proposals.resolve()),
                                  'sha256': digest(args.reused_proposals), 'cell_ids': audit,
                                  'stage': 'Exact extraction proposals only; old checks/merges are not reused.'}
        spec['audit8_repair_forecast'] = 'Zero extraction calls; 236 non-bare-number proposals yield 19 verification chunks and at most 16 match chunks. Nominal output reservation <=$0.105 plus input/retry costs, inside the SAME combined $2 run cap.'
    write_once(args.output/'spec.json', (json.dumps(spec, indent=2)+'\n').encode())
    print(json.dumps({'prepared': str(args.output), 'spec_sha256': digest(args.output/'spec.json'),
                      'cells': 32, 'audit_cells': audit}))


def load_prepared(path):
    spec = json.loads((path/'spec.json').read_text()); manifest = json.loads((path/'cells.json').read_text())
    if digest(path/'cells.json') != spec['manifest_sha256'] or digest(path/'inputs.jsonl') != spec['inputs_sha256']:
        raise ValueError('Prepared inputs/manifest changed')
    if any(digest(p) != expected for p, expected in spec['code_sha256'].items()):
        raise ValueError('Prepared helper implementation changed; version/refreeze before calls')
    inputs = {r['cell']['cell_id']: r for r in map(json.loads, (path/'inputs.jsonl').read_text().splitlines())}
    if len(inputs) != 32 or set(inputs) != {c['cell_id'] for c in manifest['cells']}:
        raise ValueError('Prepared 32-cell cohort differs')
    if 'reused_proposals' in spec and digest(spec['reused_proposals']['path']) != spec['reused_proposals']['sha256']:
        raise ValueError('Bound immutable extraction report changed')
    return spec, manifest, inputs


def tokenizer():
    from transformers import AutoTokenizer
    runtime = json.loads(Path('configs/runtime.json').read_text())
    tok = AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'], local_files_only=True)
    return lambda text: len(tok(text, add_special_tokens=False)['input_ids'])


def parsed_pool(row, count):
    samples = []
    for r in row['samples']:
        pool = r.get('global_pool_id', r['pool_id']); cid = r['cell_id']; i = r['sample_index']
        samples.append(parse_bullets(r['text'], f'{pool}:{cid}:{i}', i, token_count=count, max_output_tokens=256))
    lookup = {b.phrase_id: b for s in samples for b in s.bullets}
    if render_bullets(tuple(lookup[k] for k in row['a16']['phrase_ids'])) != row['a16']['text']:
        raise ValueError('Prepared A16 is not an unchanged complete source readout')
    return samples


def helper_clients(ledger, run_id, cache):
    none_client = make_luna_client(ledger, run_id, allow_paid=True,
                                  metadata={'purpose': 'candidate-only-exact-source-claim-extraction'})
    medium_client = make_luna_helper_diagnostic_client(ledger, run_id, reasoning_effort='medium', allow_paid=True)
    extraction = LunaHelper(none_client, cache, service_tier='default', concurrency=4, attempts=1, reasoning_effort='none')
    checking = LunaHelper(medium_client, cache, service_tier='default', concurrency=4, attempts=1, reasoning_effort='medium')
    checking.semaphore = extraction.semaphore
    return extraction, checking, (none_client, medium_client)


async def run(args):
    if not args.allow_paid: raise ValueError('Root must approve --allow-paid after prompt/spec review')
    if not os.environ.get('OPENAI_API_KEY'): raise ValueError('Coordinator must supply credential in environment')
    spec, manifest, inputs = load_prepared(args.prepared)
    if args.phase == 'audit8': ids = manifest['audit_cell_ids']
    else:
        if args.audit_gate is None: raise ValueError('Remaining cells require recorded manual qualification/support audit')
        gate = json.loads(args.audit_gate.read_text())
        if gate.get('approved') is not True or gate.get('prepared_spec_sha256') != digest(args.prepared/'spec.json'):
            raise ValueError('Manual audit gate does not approve this exact implementation')
        audit_path = args.output/'audit8.jsonl'
        if gate.get('audit8_sha256') != digest(audit_path): raise ValueError('Audit gate report identity differs')
        audited = {r['cell_id'] for r in map(json.loads, audit_path.read_text().splitlines())}
        if audited != set(manifest['audit_cell_ids']): raise ValueError('Initial eight-cell audit was incomplete')
        ids = list(inputs)
    os.environ['OLENS_ALLOW_PAID_CALLS'] = '1'
    ledger = AtomicBudget(args.ledger); ledger.set_run_limit(args.run_id, '2')
    args.output.mkdir(parents=True, exist_ok=True)
    cache = HelperCache(args.output/'helper_cache.sqlite3')
    extraction, checking, clients = helper_clients(ledger, args.run_id, cache)
    identity = {'prepared_spec_sha256': digest(args.prepared/'spec.json'), 'settings': spec['settings'], 'run_id': args.run_id}
    progress = CellProgress(args.output/'progress.sqlite3', identity); reports = progress.rows()
    if set(reports) - set(inputs): raise ValueError('Checkpoint has another cohort')
    count = tokenizer(); queue = asyncio.Queue()
    reused = {}
    if 'reused_proposals' in spec:
        reused = {r['cell_id']: r['extraction'] for r in map(json.loads,
                    Path(spec['reused_proposals']['path']).read_text().splitlines())}
        if set(reused) != set(manifest['audit_cell_ids']): raise ValueError('Reused proposal coverage changed')
    for cid in ids:
        if cid not in reports: queue.put_nowait(cid)
    async def worker():
        while not queue.empty():
            cid = queue.get_nowait()
            try:
                spans, extraction_report = await extract_verified_spans(parsed_pool(inputs[cid], count), extraction, checking,
                                                                        reused_report=reused.get(cid))
                evidence = await span_relations(spans, checking)
                report = {'cell_id': cid, 'cell': inputs[cid]['cell'], 'extraction': extraction_report,
                          'span_consensus': evidence, 'new_O_lens_samples': 0}
                progress.put(report); reports[cid] = report
                print('CLAIM_CELL_COMPLETE', len(reports), flush=True)
            finally: queue.task_done()
    workers = [asyncio.create_task(worker()) for _ in range(min(2, queue.qsize()))]
    try:
        await asyncio.gather(*workers)
    finally:
        for task in workers: task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        atomic_text(args.output/(args.phase+'.jsonl'), ''.join(json.dumps(reports[cid])+'\n' for cid in ids if cid in reports))
        atomic_text(args.output/'helper_events.json', json.dumps(extraction.events + checking.events, indent=2)+'\n')
        atomic_text(args.output/'budget_snapshot.json', json.dumps(ledger.snapshot(), indent=2)+'\n')
        await asyncio.gather(*(client.close() for client in clients))


def export(args):
    spec, manifest, inputs = load_prepared(args.prepared); count = tokenizer(); allowed = output_admissible(count, 256)
    reports = [json.loads(line) for line in args.reports.read_text().splitlines()]
    wanted = set(manifest['audit_cell_ids']) if len(reports) == 8 else set(inputs)
    if len(reports) != len(wanted) or {r['cell_id'] for r in reports} != wanted:
        raise ValueError('Export requires exactly completed audit8 or full32 cohort')
    rows, conditions = [], None
    for report in sorted(reports, key=lambda r: r['cell_id']):
        cid = report['cell_id']; parent = inputs[cid]; parsed_pool(parent, count)
        spans = [ClaimSpan(**s) for s in report['extraction']['accepted_spans']]; evidence = report['span_consensus']
        selections = [dict(parent['a16']), *[dict(b) for b in parent['whole_bullet_b']]]
        def save(method, selected):
            if not allowed(selected.bullets): raise ValueError('Final span output violates cap')
            selections.append({'method': method, 'n': 16, 'text': selected.text, 'phrase_ids': list(selected.phrase_ids),
                'token_count': count(selected.text), 'bullet_count': len(selected.bullets), 'reason': selected.reason,
                'trace': list(selected.trace), 'fits': None, 'fits_scope': 'not_AR_scored_new_claim_spans',
                'atoms': [asdict(s) for s in spans if s.claim_id in selected.phrase_ids]})
        save('extraction_only_a16', extraction_only(spans, parent['a16']['phrase_ids'], allowed))
        for fraction in (0., .125):
            for semantic in (False, True):
                selected = select_span_support(spans, evidence, fraction, allowed, semantic=semantic)
                method = f'claim_consensus_{"semantic" if semantic else "exact"}_support{fraction:g}'
                save(method, selected)
                if semantic:
                    seed = int(sha256(f'{SEED}:{cid}:{fraction}'.encode()).hexdigest()[:16], 16)
                    save(f'claim_random_matched_support{fraction:g}',
                         random_matched_spans(spans, len(selected.bullets), allowed, random.Random(seed)))
        rows.append({**parent['cell'], 'selections': selections})
        these = [{'method': s['method'], 'n': s['n']} for s in selections]
        if conditions is None: conditions = these
        elif conditions != these: raise ValueError('Condition coverage differs')
    args.output.mkdir(parents=True, exist_ok=True)
    payload = ''.join(json.dumps(r)+'\n' for r in rows).encode()
    metadata = {'prepared_spec_sha256': digest(args.prepared/'spec.json'), 'reports_sha256': digest(args.reports),
        'selection_sha256': sha256(payload).hexdigest(), 'cells': len(rows), 'partial_grid': True,
        'new_calls': 0, 'same_caps': {'bullets': 4, 'Qwen_tokens': 256},
        'audit_required': 'Source qualification and semantic false-support manual audit before expansion/judging.',
        'granularity_control': 'A16 extraction-only and same-all-N16-span-pool count-matched random controls.',
        'limitations': ['Adaptive DEV claim-span ablation; not a repair or generalization of whole-bullet consensus.',
                       'Lower-bound support under lexical shortlist; no truth verification; count matching may fail token cap.']}
    for name, value in [('selections.jsonl', payload), ('conditions.json', (json.dumps(conditions)+'\n').encode()),
                        ('cells.json', (json.dumps(manifest | {'cells': [inputs[r['cell_id']]['cell'] for r in rows]})+'\n').encode()),
                        ('export.json', (json.dumps(metadata, indent=2)+'\n').encode())]:
        write_once(args.output/name, value)
    print(json.dumps(metadata))


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    q = sub.add_parser('prepare')
    for name in ('manifest', 'records', 'parents', 'whole-bullet', 'output'): q.add_argument('--'+name, type=Path, required=True)
    q.add_argument('--reused-proposals', type=Path)
    q = sub.add_parser('preview'); q.add_argument('--prepared', type=Path, required=True)
    q = sub.add_parser('run')
    for name in ('prepared', 'output', 'ledger'): q.add_argument('--'+name, type=Path, required=True)
    q.add_argument('--run-id', required=True); q.add_argument('--phase', choices=('audit8', 'full32'), required=True)
    q.add_argument('--audit-gate', type=Path); q.add_argument('--allow-paid', action='store_true')
    q = sub.add_parser('export')
    for name in ('prepared', 'reports', 'output'): q.add_argument('--'+name, type=Path, required=True)
    args = p.parse_args()
    if args.command == 'prepare': prepare(args)
    elif args.command == 'preview':
        spec, _, _ = load_prepared(args.prepared)
        print(json.dumps({'spec': spec, 'extract_prompt': EXTRACT_SYSTEM, 'support_prompt': VERIFY_SYSTEM,
                          'claim_match_prompt': CLAIM_MATCH_SYSTEM}, indent=2))
    elif args.command == 'run': asyncio.run(run(args))
    else: export(args)


if __name__ == '__main__': main()
