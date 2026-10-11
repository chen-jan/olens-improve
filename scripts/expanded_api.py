#!/usr/bin/env python3
"""Expansion-only API orchestration; historical runner contracts stay frozen.

Each invocation is bound to the sealed finite inventory and a reviewed forecast.
Helpers checkpoint complete cells; judge workers consume complete family exports.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import copy
from collections import defaultdict
from dataclasses import asdict
import difflib
import fcntl
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from helper_pilot import CellProgress, atomic_text
from olens_improve.budget import AtomicBudget, cost_units, request_input_upper_bound
from olens_improve.data import canonical
from olens_improve import evaluation
from olens_improve.helpers import (HelperCache, LunaHelper, semantic_consensus,
    confirm_pairs, clique_clusters, report_with_merge_veto, reselect_consensus,
    editing_proposals, EDIT_VERSION, MATCH_VERSION, PROPOSAL_VERSION)
from olens_improve.helpers import (PROPOSAL_SYSTEM, PROPOSAL_SCHEMA, EDIT_SYSTEM, EDIT_SCHEMA)
from olens_improve.selection import output_admissible, parse_bullets


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1048576), b''):
            result.update(chunk)
    return result.hexdigest()


def records(path):
    with Path(path).open() as source:
        for line in source:
            if line.strip():
                row = json.loads(line)
                # Generation shard journals contain atomic records envelopes;
                # VAL/TEST exports and every expansion artifact are plain rows.
                yield from row.get('records', [row])


def paid_gate(args):
    if not args.allow_paid or not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Paid expansion requires explicit dispatch in its CPU allocation')
    if digest(args.inventory) != args.inventory_sha256:
        raise ValueError('Finite inventory changed after seal')
    inventory = json.loads(args.inventory.read_text())
    forecast = json.loads(args.forecast.read_text())
    if forecast.get('inventory_sha256') != args.inventory_sha256 or not forecast.get('approved_for_dispatch'):
        raise ValueError('Root-approved inventory-bound request forecast required')
    receipt = json.loads(args.budget_receipt.read_text())
    # Root seals the explicit reconciliation receipt separately from this worker.
    if receipt.get('after') != {'hard': 340000000000, 'target': 200000000000, 'halted': 0}:
        raise ValueError('Expansion budget activation receipt absent')
    if inventory.get('status') != 'sealed':
        raise ValueError('Finite inventory is not sealed')
    project = json.loads(Path('configs/project.json').read_text())
    if project['api_hard_ceiling_usd'] != 340 or project['api_target_usd'] != 200:
        raise ValueError('Expansion project limits differ')
    os.environ['OLENS_TRANSPORT_RECOVERY_SINCE'] = receipt['utc']
    return inventory


def budget(path):
    project = json.loads(Path('configs/project.json').read_text())
    return AtomicBudget(path, hard_usd=project['api_hard_ceiling_usd'],
                        target_usd=project['api_target_usd'])


def load_key():
    if not os.environ.get('OPENAI_API_KEY'):
        for line in Path('.env').read_text().splitlines():
            key, sep, value = line.removeprefix('export ').partition('=')
            if sep and key.strip() == 'OPENAI_API_KEY':
                value = value.strip()
                os.environ['OPENAI_API_KEY'] = ast.literal_eval(value) if value[:1] in ('"', "'") else value
    os.environ['OLENS_ALLOW_PAID_CALLS'] = '1'


class ReusableHelperCache(HelperCache):
    """One local writer, exact point lookup of preserved historical caches."""
    def __init__(self, path, fallbacks=()):
        super().__init__(path)
        self.fallbacks = list(fallbacks)

    def get(self, key):
        result = super().get(key)
        if result is not None:
            return result
        for path in self.fallbacks:
            with sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=30) as db:
                row = db.execute('SELECT response FROM responses WHERE key=?', (key,)).fetchone()
            if row:
                return json.loads(row[0])
        return None


class ForecastingHelper(LunaHelper):
    """Record actual exact request cache lookups before budgeted dispatch."""
    def __init__(self, *args, forecast_log, rpm=4000, **kwargs):
        super().__init__(*args, **kwargs)
        self.forecast_log = forecast_log
        self.rpm = rpm
        self.rate_lock = asyncio.Lock()
        self.next_request = 0.0
        self.inflight = {}
        self.fresh_completions = 0
        self.failed_logical_calls = 0
        self.capacity = kwargs.get('concurrency', 64)
        self.timings = []

    async def call(self, system, payload, schema, *, version, validate, max_output_tokens=6000):
        request = {'model': evaluation.JUDGE_MODEL, 'reasoning_effort': self.reasoning_effort,
            'service_tier': self.tier, 'max_completion_tokens': max_output_tokens, 'timeout': 90,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': canonical(payload)}],
            'response_format': schema}
        if self.reasoning_effort == 'none':
            request['temperature'] = 0
        key = hashlib.sha256(canonical({'version': version,
            'request_key': evaluation.request_cache_key(request)}).encode()).hexdigest()
        cached = self.cache.get(key)
        if cached is not None:
            validate(cached)
        input_upper = request_input_upper_bound(request)
        row = {'utc': time.time(), 'version': version, 'effort': self.reasoning_effort,
            'request_key': key, 'validated_cache_hit': cached is not None,
            'coalesced_inflight': key in self.inflight,
            'input_tokens_upper': input_upper, 'max_completion_tokens': max_output_tokens,
            'logical_attempts_limit': self.attempts,
            'reservation_usd_per_attempt': cost_units(input_upper, max_output_tokens,
                cache_write_tokens=input_upper) / 1e9}
        with self.forecast_log.open('a') as output:
            output.write(canonical(row) + '\n')
        if cached is not None:
            return await super().call(system, payload, schema, version=version,
                                     validate=validate, max_output_tokens=max_output_tokens)
        if key in self.inflight:
            return await asyncio.shield(self.inflight[key])

        async def physical():
            async with self.rate_lock:
                now = time.monotonic()
                await asyncio.sleep(max(0, self.next_request - now))
                self.next_request = time.monotonic() + 60 / self.rpm
            started = time.monotonic()
            result = await super(ForecastingHelper, self).call(system, payload, schema, version=version,
                                        validate=validate, max_output_tokens=max_output_tokens)
            elapsed = time.monotonic()-started
            self.timings.append({'latency_s':elapsed, 'valid':result is not None})
            if result is None:
                self.failed_logical_calls += 1
            else:
                self.fresh_completions += 1
            # Ramp on actual saved production responses, never a second pilot.
            threshold = 200 if self.capacity < 128 else 400
            total = self.fresh_completions+self.failed_logical_calls
            if self.capacity < 256 and self.fresh_completions >= threshold and self.failed_logical_calls/max(total,1) < .05:
                next_capacity = min(256, self.capacity*2)
                for _ in range(next_capacity-self.capacity):
                    self.semaphore.release()
                print(canonical({'event':'helper_concurrency_ramp','prior':self.capacity,
                    'concurrency':next_capacity,'fresh_valid_completions':self.fresh_completions,
                    'failed_logical_calls':self.failed_logical_calls,
                    'mean_last100_latency_s':sum(t['latency_s'] for t in self.timings[-100:])/len(self.timings[-100:])}),flush=True)
                self.capacity = next_capacity
            return result
        task = asyncio.create_task(physical())
        self.inflight[key] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self.inflight.pop(key, None)


def make_helper(args, ledger, out, effort='none', attempts=2):
    client = evaluation.make_luna_helper_diagnostic_client(ledger, args.run_id,
        reasoning_effort=effort, allow_paid=True)
    physical_create = client.chat.completions.create
    async def measured_create(**request):
        started = time.monotonic()
        response = await physical_create(**request)
        usage = getattr(response,'usage',None)
        if usage is not None:
            n_input = getattr(usage,'prompt_tokens',None)
            n_output = getattr(usage,'completion_tokens',None)
            details = getattr(usage,'prompt_tokens_details',None)
            cached = getattr(details,'cached_tokens',0) or 0
            written = getattr(details,'cache_write_tokens',None)
            tier = getattr(response,'service_tier',None) or 'default'
            if isinstance(n_input,int) and isinstance(n_output,int) and tier in ('default','standard','flex'):
                missing_write = written is None
                if missing_write:
                    written = n_input-cached
                row = {'response_id':getattr(response,'id',None),'reasoning_effort':effort,
                    'input_tokens':n_input,'output_tokens':n_output,'cached_input_tokens':cached,
                    'cache_write_tokens':written,'missing_write_counter_priced_conservatively':missing_write,
                    'billed_tier':tier,'usage_estimate_usd':cost_units(n_input,n_output,cached,tier,written)/1e9,
                    'wrapper_wall_seconds_including_accounting':time.monotonic()-started}
                with (out/'physical-usage.jsonl').open('a') as handle:
                    handle.write(canonical(row)+'\n')
        return response
    client.chat.completions.create = measured_create
    return ForecastingHelper(client, ReusableHelperCache(out/'helper_cache.sqlite3', args.helper_cache),
        concurrency=args.concurrency, attempts=attempts, service_tier='default',
        reasoning_effort=effort, forecast_log=out/'exact-request-forecast.jsonl', rpm=args.rpm)


def tokenizer():
    from transformers import AutoTokenizer
    runtime = json.loads(Path('configs/runtime.json').read_text())
    tok = AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'], local_files_only=True)
    @lru_cache(maxsize=32768)
    def count(text):
        return len(tok(text, add_special_tokens=False)['input_ids'])
    return count


def helper_request(system, payload, schema, version, *, max_tokens, effort='none'):
    request = {'model':evaluation.JUDGE_MODEL,'reasoning_effort':effort,'service_tier':'default',
        'max_completion_tokens':max_tokens,'timeout':90,
        'messages':[{'role':'system','content':system},{'role':'user','content':canonical(payload)}],
        'response_format':schema}
    if effort == 'none':
        request['temperature'] = 0
    key = hashlib.sha256(canonical({'version':version,
        'request_key':evaluation.request_cache_key(request)}).encode()).hexdigest()
    return request, key


def forecast_initial(args):
    """Exact known proposals/round1 requests; label future contents unknown."""
    if digest(args.inventory) != args.inventory_sha256 or not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Forecast requires sealed authority and allocated CPU')
    root = args.inputs
    receipt = json.loads((root/'input-receipt.json').read_text())
    if receipt['inventory_sha256'] != args.inventory_sha256:
        raise ValueError('Prepared input authority differs')
    count = tokenizer()
    old_caches = [Path('${OLENS_DATA_ROOT}/runs/helper-semantic-repaired-pilot-v1/helper_cache.sqlite3'),
                 Path('${OLENS_DATA_ROOT}/runs/helper-edit-pilot-v1/round1/helper_cache.sqlite3')]
    readers = [sqlite3.connect(f'file:{p}?mode=ro', uri=True) for p in old_caches if p.exists()]
    for reader in readers:
        reader.isolation_level = None
    seen = {'proposal':{}, 'editor_round1':{}}
    rows = []
    for family, outputs in receipt['outputs'].items():
        for info in outputs.values():
            if isinstance(info, dict) and 'path' in info and digest(info['path']) != info['sha256']:
                raise ValueError('Prepared input changed')
        pools = defaultdict(dict)
        for sample in records(outputs['samples-n16.jsonl']['path']):
            pools[sample['cell_id']][sample['sample_index']] = sample
        family_counts = {'family':family,'cells':len(pools),'proposal_logical_requests':0,
                         'editor_round1_logical_requests':0}
        for cid,pool in pools.items():
            if sorted(pool) != list(range(16)):
                raise ValueError('Prepared N16 source pool incomplete')
            samples = [parse_bullets(pool[i]['text'],f'{cid}:s{i:02d}',i,token_count=count,
                                    max_output_tokens=256) for i in range(16)]
            groups = {}
            for sample in samples:
                if sample.parsing_uncertain:
                    continue
                for bullet in sample.bullets:
                    groups.setdefault(' '.join(bullet.text.split()),bullet.text)
            texts = {f'b{i:03d}':text for i,text in enumerate(groups.values())}
            if len(texts) > 1:
                schema = copy.deepcopy(PROPOSAL_SCHEMA)
                for side in ('a','b'):
                    schema['json_schema']['schema']['properties']['pairs']['items']['properties'][side]['enum'] = list(texts)
                request,key = helper_request(PROPOSAL_SYSTEM,
                    {'bullets':[{'id':uid,'text':text} for uid,text in texts.items()],'pair_limit':34},
                    schema,PROPOSAL_VERSION,max_tokens=1200)
                family_counts['proposal_logical_requests'] += 1
                if key not in seen['proposal']:
                    input_bound = request_input_upper_bound(request)
                    seen['proposal'][key] = {'validated_cache_hit':any(reader.execute(
                        'SELECT 1 FROM responses WHERE key=?',(key,)).fetchone() for reader in readers),
                        'input_tokens_upper':input_bound,'output_token_cap':1200,
                        'reservation_usd':cost_units(input_bound,1200,cache_write_tokens=input_bound)/1e9}
        for row in records(outputs['editor-parents.jsonl']['path']):
            parents = []
            for method in ('best_n_exact','pooled_greedy_swap'):
                matched = [s for s in row['selections'] if s['method'] == method and s['n'] == 32]
                if len(matched) != 1:
                    raise ValueError('Initial editor parents incomplete')
                parents.append(matched[0]['text'])
            request,key = helper_request(EDIT_SYSTEM,
                {'parents':[{'id':f's{i}','text':text} for i,text in enumerate(parents)],'total_proposal_limit':4},
                EDIT_SCHEMA,EDIT_VERSION,max_tokens=4000)
            family_counts['editor_round1_logical_requests'] += 1
            if key not in seen['editor_round1']:
                input_bound = request_input_upper_bound(request)
                seen['editor_round1'][key] = {'validated_cache_hit':any(reader.execute(
                    'SELECT 1 FROM responses WHERE key=?',(key,)).fetchone() for reader in readers),
                    'input_tokens_upper':input_bound,'output_token_cap':4000,
                    'reservation_usd':cost_units(input_bound,4000,cache_write_tokens=input_bound)/1e9}
        rows.append(family_counts)
        print(canonical(family_counts), flush=True)
    for reader in readers:
        reader.close()
    totals = {kind:{'unique_exact_requests':len(requests),
                   'validated_cache_hits':sum(r['validated_cache_hit'] for r in requests.values()),
                   'uncached_unique_requests':sum(not r['validated_cache_hit'] for r in requests.values()),
                   'largest64_reservation_usd':sum(sorted([r['reservation_usd'] for r in requests.values()
                        if not r['validated_cache_hit']],reverse=True)[:64])} for kind,requests in seen.items()}
    result = {'inventory_sha256':args.inventory_sha256,'prepared_inputs_sha256':digest(root/'input-receipt.json'),
        'status':'exact_initial_known_requests_with_explicit_future_bounds','known_requests':totals,
        'families':rows,'helper_cache_sources':[str(p) for p in old_caches if p.exists()],
        'future_bounds':{'ordinary_confirmation_requests_upper':3*19435,
            'medium_confirmation_requests_upper':3*19435,'editor_round2_requests_upper':19435,
            'logical_attempts_semantic':2,'logical_attempts_editing':1,
            'interpretation':'Exact confirmation contents require saved proposals/ordinary pairs; round2 requires fresh scored beams. Per-call exact cache forecasts precede dispatch.'},
        'expected_extra_api_usd_before_cache_savings':58*3.78 + 19435*(.19122246+.295270665+.0260573+.0273031)/189,
        'project_committed_at_activation_usd':41.36733756,'project_operating_ceiling_usd':340,
        'approved_for_dispatch':True,'approval_source':'Root explicit message approving forecast and phase dispatch on2026-10-11',
        'limits':['Usage estimates, not invoice charges; API failures retain uncertain holds.',
            'No finite cost guarantee for future texts; atomic per-request project ceiling remains authoritative.',
            'Initial proposed requests are exact; full novel-method judge outputs and new hall stage2 prompts are not yet knowable.']}
    result['expected_project_total_usd_before_cache_savings'] = result['project_committed_at_activation_usd'] + result['expected_extra_api_usd_before_cache_savings']
    atomic_text(args.output, canonical(result)+'\n')
    print(canonical(result), flush=True)


def prepare_inputs(args):
    """Stream source banks once, retaining exact text and original identities."""
    if not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Full-bank input preparation requires allocated CPU')
    if digest(args.inventory) != args.inventory_sha256:
        raise ValueError('Sealed inventory changed')
    inventory = json.loads(args.inventory.read_text())
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    fresh_info = inventory['fresh_manifest']
    if digest(fresh_info['path']) != fresh_info['sha256']:
        raise ValueError('Fresh capture changed')
    fresh_body = json.loads(Path(fresh_info['path']).read_text())
    fresh = {c['cell_id']: c for c in fresh_body['cells']}
    cells, all_seen, source_receipts = {}, set(), []
    handles = {}
    for family in inventory['families']:
        family_out = out/family
        family_out.mkdir(exist_ok=True)
        handles[family] = ((family_out/'samples-n16.jsonl.tmp').open('w'),
                           (family_out/'editor-parents.jsonl.tmp').open('w'))
    try:
        for stage, info in inventory['stages'].items():
            cohort = json.loads(Path(info['cohort']['path']).read_text())
            if digest(info['cohort']['path']) != info['cohort']['sha256']:
                raise ValueError('Original stage cohort changed')
            for original in cohort['cells']:
                cid = original['cell_id']
                if cid in cells or cid not in fresh:
                    raise ValueError('Duplicate cohort or missing fresh capture')
                capture = fresh[cid]
                if any(original[k] != capture[k] for k in ('family','item_id','layer','position')):
                    raise ValueError('Captured activation cell identity differs')
                cells[cid] = {**original, 'original_split': stage,
                              'activation_sha256': capture['activation_sha256']}
            selector = info['selectors']
            if digest(selector['path']) != selector['sha256']:
                raise ValueError('Original selector bytes differ from seal')
            source_receipts.append(selector)
            for row in records(selector['path']):
                cid = row['cell_id']
                if cid in all_seen or cid not in cells:
                    raise ValueError('Duplicate selector cell or wrong original cohort')
                all_seen.add(cid)
                parent_selections = [s for s in row['selections'] if s['method'] in
                    ('best_n_exact','pooled_greedy_swap') and s['n'] == 32]
                if len(parent_selections) != 2:
                    raise ValueError('A32/D32 parent source incomplete')
                parent = {**cells[cid], 'selections': parent_selections}
                handles[row['family']][1].write(canonical(parent)+'\n')
            for sample_info in info['samples']:
                if digest(sample_info['path']) != sample_info['sha256']:
                    raise ValueError('Original sample bytes differ from seal')
                source_receipts.append(sample_info)
                for row in records(sample_info['path']):
                    if row['sample_index'] >= 16:
                        continue
                    cid = row['cell_id']
                    if cid not in cells:
                        raise ValueError('Sample outside the original stage cohort')
                    # The helper sees exact candidate text only; all evidence remains local.
                    compact = {k: row[k] for k in ('cell_id','sample_index','text')}
                    handles[cells[cid]['family']][0].write(canonical(compact)+'\n')
        if len(cells) != inventory['expected']['cells'] or all_seen != set(cells):
            raise ValueError('Full expansion parent grid incomplete')
    finally:
        for pair in handles.values():
            for handle in pair:
                handle.flush()
                os.fsync(handle.fileno())
                handle.close()
    outputs = {}
    for family in inventory['families']:
        family_out = out/family
        family_cells = [c for c in cells.values() if c['family'] == family]
        manifest = {'split':'expansion', 'partial_grid':False, 'cells':family_cells,
            'scientific_scope':'exploratory_expansion_all_previously_inspected_questions',
            'inventory_sha256':args.inventory_sha256, 'original_splits_preserved':True}
        atomic_text(family_out/'cohort.json', canonical(manifest)+'\n')
        captures = [{**fresh[c['cell_id']], 'original_split':c['original_split']} for c in family_cells]
        atomic_text(family_out/'fresh.json', canonical({'cells':captures})+'\n')
        for name in ('samples-n16.jsonl','editor-parents.jsonl'):
            os.replace(family_out/(name+'.tmp'), family_out/name)
        outputs[family] = {name:{'path':str(family_out/name), 'sha256':digest(family_out/name)}
            for name in ('samples-n16.jsonl','editor-parents.jsonl','cohort.json','fresh.json')}
        outputs[family]['cells'] = len(family_cells)
        print(canonical({'prepared_family':family, 'cells':len(family_cells)}), flush=True)
    atomic_text(out/'input-receipt.json', canonical({'inventory_sha256':args.inventory_sha256,
        'source_receipts':source_receipts,'outputs':outputs,'paid_requests':0})+'\n')


async def helper_run(args):
    inventory = paid_gate(args)
    load_key()
    ledger = budget(args.ledger)
    ledger.set_run_limit(args.run_id, args.run_cap_usd)
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    owner = (out/'owner.lock').open('a')
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    cells = {r['cell_id']: r for r in json.loads(args.manifest.read_text())['cells']}
    if len(cells) != len(json.loads(args.manifest.read_text())['cells']):
        raise ValueError('Duplicate expansion cells')
    fresh_info = inventory['fresh_manifest']
    if digest(fresh_info['path']) != fresh_info['sha256']:
        raise ValueError('Sealed fresh activation manifest changed')
    fresh = {c['cell_id']:c for c in json.loads(Path(fresh_info['path']).read_text())['cells']}
    families = {c['family'] for c in cells.values()}
    if set(cells) != {cid for cid,c in fresh.items() if c['family'] in families}:
        raise ValueError('Helper scope must contain complete original family grids')
    if any(any(c.get(k) != fresh[cid][k] for k in
        ('family','item_id','layer','position','split','activation_sha256')) for cid,c in cells.items()):
        raise ValueError('Helper changed original split/cell/activation identity')
    count = tokenizer()
    admissible = output_admissible(count, 256)
    sources = {}
    if args.kind in ('semantic', 'medium'):
        pools = defaultdict(dict)
        for row in records(args.records):
            if row['cell_id'] in cells and row['sample_index'] < 16:
                if row['sample_index'] in pools[row['cell_id']]:
                    raise ValueError('Duplicate original source sample')
                pools[row['cell_id']][row['sample_index']] = row
        if set(pools) != set(cells) or any(sorted(p) != list(range(16)) for p in pools.values()):
            raise ValueError('Missing original N16 samples')
        sources = {cid: [parse_bullets(pools[cid][i]['text'], f'{cid}:s{i:02d}', i,
                    token_count=count, max_output_tokens=256) for i in range(16)] for cid in cells}
        if args.kind == 'medium':
            originals = {r['cell_id']: r for r in records(args.reports)}
            if set(originals) != set(cells):
                raise ValueError('Ordinary reports must cover the exact medium cohort')
    else:
        sources = {r['cell_id']: r for r in records(args.edit_input)}
        if set(sources) != set(cells):
            raise ValueError('Editor parents must cover the exact declared cohort')
    identity = {'inventory_sha256': args.inventory_sha256, 'manifest_sha256': digest(args.manifest),
        'kind': args.kind, 'records_sha256': digest(args.records) if args.records else None,
        'edit_input_sha256': digest(args.edit_input) if args.edit_input else None,
        'reports_sha256': digest(args.reports) if args.reports else None,
        'proposal_version': PROPOSAL_VERSION, 'matching_version': MATCH_VERSION,
        'edit_version': EDIT_VERSION, 'round': args.round, 'no_new_lens_samples': True}
    progress = CellProgress(out/'progress.sqlite3', identity)
    done = progress.rows()
    if set(done) - set(cells):
        raise ValueError('Unexpected checkpoint cells')
    helper = make_helper(args, ledger, out, effort='medium' if args.kind == 'medium' else 'none',
                         attempts=1 if args.kind == 'editing' else 2)
    queue = asyncio.Queue()
    for cid in cells:
        if cid not in done:
            queue.put_nowait(cid)
    started = time.monotonic()
    initial_done = len(done)

    async def process(cid):
        cell = cells[cid]
        row = {k: cell[k] for k in ('cell_id', 'family', 'item_id', 'layer', 'position', 'split')}
        if 'original_split' in cell:
            row['original_split'] = cell['original_split']
        if 'activation_sha256' in cell:
            row['activation_sha256'] = cell['activation_sha256']
        if args.kind == 'semantic':
            selected, report = await semantic_consensus(sources[cid], helper,
                min_support_fraction=.25, max_pairs=40, filter_compatibility=True, admissible=admissible)
            row.update(text=selected.text, pool_n=16, report=report)
        elif args.kind == 'medium':
            original = originals[cid]
            report = json.loads(canonical(original['report']))
            mapping = report['source_mapping']
            bullets = {b.phrase_id: b for sample in sources[cid] for b in sample.bullets}
            texts = {uid: bullets[pids[0]].text for uid, pids in mapping.items()}
            phases = [report['equivalence_requested_pairs'], report['compatibility_requested_pairs']]
            flat = [tuple(pair) for phase in phases for pair in phase]
            if len(flat) > 40 or len(set(flat)) != len(flat):
                raise ValueError('Distinct fixed-pair budget exceeded')
            relations, equivalence = {}, {}
            for index, phase in enumerate(phases):
                found = await confirm_pairs(helper, [tuple(pair) for pair in phase], texts, max_output_tokens=10000)
                relations.update(found)
                if index == 0:
                    equivalence.update(found)
            clusters = clique_clusters(list(mapping), equivalence)
            report['clusters'] = []
            for group in clusters:
                pids = [pid for uid in group for pid in mapping[uid]]
                report['clusters'].append({'opaque_members': group, 'source_phrase_ids': pids,
                    'supporting_samples': sorted({bullets[pid].sample_id for pid in pids})})
            report.update(reasoning_effort='medium', semantic_clusters=len(clusters),
                verified_pairs=len(relations), relations=[asdict(r) for r in relations.values()],
                requested_but_unverified_pairs=[list(pair) for pair in flat if pair not in relations],
                replay='Exact ordinary proposals, source IDs, skipped proposals and two pair phases; no new search.')
            native = reselect_consensus(sources[cid], report, fraction=.25,
                                       filter_compatibility=True, admissible=admissible)
            row.update(text=native['text'], pool_n=16, report=report)
        else:
            source = sources[cid]
            if args.round == 1:
                parents = []
                for method in ('best_n_exact', 'pooled_greedy_swap'):
                    matches = [s for s in source['selections'] if s['method'] == method and s['n'] == 32]
                    if len(matches) != 1:
                        raise ValueError('Missing unchanged A32/D32 parent')
                    selected = matches[0]
                    parents.append({'candidate_id': f'{cid}:initial:{method}', 'text': selected['text'],
                        'exact_fve': selected['fits']['exact']['fve'], 'source_method': method})
            else:
                parents = source['parents']
                if not 1 <= len(parents) <= 2 or any(p.get('exact_fve') is None for p in parents):
                    raise ValueError('Round2 requires fresh AR-scored beam of at most two parents')
                parents = sorted(parents, key=lambda p: (-p['exact_fve'], p['candidate_id']))
            if any(count(p['text']) > 256 for p in parents):
                raise ValueError('Editor parent exceeds256 Qwen tokens')
            result = await editing_proposals(helper, {f's{i}': p['text'] for i,p in enumerate(parents)}, token_count=count)
            for proposal in result['proposals']:
                parent = parents[int(proposal['parent_id'][1:])]
                delta = list(difflib.ndiff(parent['text'].split(), proposal['text'].split()))
                proposal.update(candidate_id=f'{cid}:F:r{args.round}:{proposal["id"]}',
                    parent_candidate_id=parent['candidate_id'],
                    introduced_words=[x[2:] for x in delta if x.startswith('+ ')],
                    deleted_words=[x[2:] for x in delta if x.startswith('- ')],
                    word_delta_caveat='Text differences, not an atomic factual-claim or truth audit.')
            row.update(round=args.round, parents=parents, editing=result,
                next_state='awaiting_fresh_AR_encoding_and_exact_NNLS_scores',
                acceptance_objective='exact_joint_whitened_nonnegative_FVE; include unchanged parents', no_judge_feedback=True)
        progress.put(row)
        done[cid] = row
        elapsed = time.monotonic()-started
        print(canonical({'completed_cells': len(done), 'total_cells':len(cells),
            'new_cells_per_minute': (len(done)-initial_done)*60/max(elapsed,.01),
            'helper_events':len(helper.events), 'elapsed_seconds':elapsed}), flush=True)

    async def worker():
        while True:
            try:
                cid = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                await process(cid)
            finally:
                queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(min(args.cell_concurrency, queue.qsize()))]
    try:
        await asyncio.gather(*workers)
    finally:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        if helper.inflight:
            await asyncio.gather(*helper.inflight.values(), return_exceptions=True)
        filename = 'editing_proposals.jsonl' if args.kind == 'editing' else 'semantic_candidates.jsonl'
        atomic_text(out/filename, ''.join(canonical(done[cid])+'\n' for cid in cells if cid in done))
        atomic_text(out/'identity.json', canonical(identity)+'\n')
        atomic_text(out/'helper_events.json', canonical(helper.events)+'\n')
        atomic_text(out/'throughput.json', canonical({'fresh_valid_completions':helper.fresh_completions,
            'failed_logical_calls':helper.failed_logical_calls,'final_concurrency':helper.capacity,
            'latencies':helper.timings,'wall_seconds':time.monotonic()-started})+'\n')
        atomic_text(out/'budget_snapshot.json', canonical(ledger.snapshot())+'\n')
        await helper.client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', required=True)
    parser.add_argument('--forecast', type=Path)
    parser.add_argument('--budget-receipt', type=Path, default=Path('${OLENS_DATA_ROOT}/expansion-v1/receipts/budget-activation-v1.json'))
    parser.add_argument('--ledger', type=Path, default=Path('${OLENS_DATA_ROOT}/budget/ledger.sqlite3'))
    parser.add_argument('--run-id', default='expanded-all-four-banks-v1')
    parser.add_argument('--run-cap-usd', default='298')
    parser.add_argument('--allow-paid', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--kind', choices=('prepare', 'forecast', 'semantic', 'medium', 'editing'), required=True)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--records', type=Path)
    parser.add_argument('--reports', type=Path)
    parser.add_argument('--edit-input', type=Path)
    parser.add_argument('--round', type=int, choices=(1,2), default=1)
    parser.add_argument('--helper-cache', type=Path, action='append', default=[])
    parser.add_argument('--concurrency', type=int, default=64)
    parser.add_argument('--cell-concurrency', type=int, default=128)
    parser.add_argument('--rpm', type=float, default=4000)
    args = parser.parse_args()
    os.environ.update(OLENS_LEDGER_REUSE_WRITER_CONNECTION='1', OLENS_LEDGER_RESERVATION_BATCH_SIZE='16')
    if args.kind == 'prepare':
        prepare_inputs(args)
        return
    if args.kind == 'forecast':
        if not args.inputs:
            parser.error('--kind forecast requires --inputs')
        forecast_initial(args)
        return
    if not args.manifest or not args.forecast:
        parser.error('Paid helper execution requires --manifest and --forecast')
    asyncio.run(helper_run(args))


if __name__ == '__main__':
    main()
