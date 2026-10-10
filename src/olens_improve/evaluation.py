"""Pinned upstream judging plus reservation-aware Luna transport.

This module does not implement benchmark prompts or pass rules. It converts one
selected readout per cell, invokes the pinned WorkspaceBench family, and adds
our frozen-manifest completeness and paired-group reporting contracts.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
import hashlib
import importlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import sqlite3
import contextlib
import inspect
import math
import signal
from types import SimpleNamespace
from typing import Any

from .budget import AtomicBudget, BudgetExceeded, request_input_upper_bound
from .data import BENCH_COMMIT, FAMILIES, SOURCE_ROOT, LAYERS, canonical, file_hash, paths
from .stage_io import validate_export_stage
from .performance import CURRENT_PROFILE, profile_condition

JUDGE_MODEL = 'gpt-6-luna'
BENCH_ROOT = SOURCE_ROOT / 'scratch/repos/workspace-bench-v2'


class ConditionBoundaryStop:
    """Operational stop request; never cancel the current judged condition."""
    def __init__(self, request_file: Path | None = None):
        self.request_file = request_file
        self.signaled = False

    def request(self, _signum=None, _frame=None) -> None:
        self.signaled = True

    def requested(self) -> bool:
        return self.signaled or (self.request_file is not None and self.request_file.exists())


def positive_rpm(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError('rpm must be finite and positive')
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError('rpm must be finite and positive')
    return result


def transport_settings(concurrency: int, rpm: float, service_tier: str) -> dict:
    if not isinstance(concurrency, int) or isinstance(concurrency, bool) or concurrency < 1:
        raise ValueError('concurrency must be a positive integer')
    if service_tier not in ('flex', 'default'):
        raise ValueError('Explicit Flex/Standard service tier required')
    return {'concurrency': concurrency, 'rpm': positive_rpm(rpm), 'service_tier': service_tier,
        'rate_limit_scope': 'Per family worker, upstream logical calls; physical retries are separately budgeted.',
        'sdk_max_retries': 0, 'logical_attempt_limit': 2}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def request_cache_key(request: dict) -> str:
    """Full content/settings identity; service tier and transport timeout are omitted.

The schema, model, effort, temperature and output cap are included. This key is
recorded beside physical attempts; upstream still owns validated-result caching.
"""
    content = {k: v for k, v in request.items() if k not in ('service_tier', 'timeout')}
    return hashlib.sha256(canonical(content).encode()).hexdigest()


def safe_exception_chain(error: BaseException) -> list[dict]:
    """Transport diagnostics without exception messages, endpoints or secrets."""
    chain = []
    seen = set()
    while error is not None and id(error) not in seen and len(chain) < 8:
        seen.add(id(error))
        number = getattr(error, 'errno', None)
        chain.append({'class': type(error).__name__,
                      'errno': number if isinstance(number, int) and not isinstance(number, bool) else None})
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return chain


class BudgetedCompletions:
    def __init__(self, inner: Any, ledger: AtomicBudget, run_id: str,
                 *, allow_paid: bool = False, metadata: dict | None = None,
                 helper_reasoning_effort: str | None = None):
        self.inner = inner
        self.ledger = ledger
        self.run_id = run_id
        self.allow_paid = allow_paid
        self.metadata = metadata or {}
        if helper_reasoning_effort not in (None, 'none', 'medium'):
            raise ValueError('Helper diagnostic effort must be none or medium')
        self.reasoning_effort = helper_reasoning_effort or 'none'
        self.helper_diagnostic = helper_reasoning_effort is not None

    async def create(self, **request: Any) -> Any:
        if not self.allow_paid or os.environ.get('OLENS_ALLOW_PAID_CALLS') != '1':
            raise RuntimeError('Paid calls disabled; root must verify shared ledger and tiny run cap first')
        if request.get('model') != JUDGE_MODEL or request.get('reasoning_effort') != self.reasoning_effort:
            raise ValueError('Model/effort differs from the frozen judge or explicit helper diagnostic')
        if self.reasoning_effort != 'none' and any(k in request for k in ('temperature', 'top_p', 'logprobs', 'top_logprobs')):
            raise ValueError('Non-none helper reasoning must omit sampling/logprob overrides')
        if request.get('service_tier') not in ('flex', 'default'):
            raise ValueError('Explicit service_tier flex/default required; no automatic/priority route')
        if 'extra_body' in request or 'extra_headers' in request or 'extra_query' in request:
            raise ValueError('Region/pricing/route overrides are not supported')
        max_output = request.get('max_completion_tokens')
        if not isinstance(max_output, int) or isinstance(max_output, bool) or max_output <= 0:
            raise ValueError('Explicit positive max_completion_tokens required')
        input_bound = request_input_upper_bound(request)
        if input_bound + max_output > 272000:
            raise ValueError('Conservative request bound exceeds the priced standard-context contract')
        content_key = request_cache_key(request)
        profiler = getattr(self.ledger, '_operational_profile', None)
        if profiler is not None: profiler.ensure_heartbeat()
        serializable = {k: v for k, v in request.items() if k != 'timeout'}
        aid = self.ledger.reserve_attempt(input_bound, max_output, run_id=self.run_id,
                    metadata={**self.metadata, 'content_cache_key': content_key,
                              'request': serializable, 'pid': os.getpid(),
                              'helper_effort_opt_in': self.helper_diagnostic,
                              'requested_tier': request['service_tier']},
                    dispatch_guard={'since_utc': os.environ['OLENS_TRANSPORT_RECOVERY_SINCE']}
                        if os.environ.get('OLENS_TRANSPORT_RECOVERY_SINCE') else None)
        started = time.monotonic()
        try:
            response = await self.inner.create(**request)
        except BaseException as error:
            # Timeouts, cancellation and transport failures can still be billed.
            # Even status errors remain reserved until definitive reconciliation.
            self.ledger.mark_unknown(aid, f'{type(error).__name__}; physical attempt outcome uncertain')
            self.ledger.record_evidence(aid, 'transport_failure', {
                'exception_type': type(error).__name__, 'latency_s': time.monotonic() - started,
                'cause_chain': safe_exception_chain(error),
                'provider_request_id': getattr(error, 'request_id', None),
                'http_status': getattr(error, 'status_code', None),
                'error_code': getattr(error,'code',None),
                'error_type': getattr(error,'type',None),
            })
            raise
        latency = time.monotonic() - started
        usage = _get(response, 'usage')
        raw = response.model_dump(mode='json') if hasattr(response, 'model_dump') else None
        self.ledger.record_evidence(aid, 'physical_response', {
            'latency_s': latency, 'response_id': _get(response, 'id'),
            'provider_request_id': _get(response, '_request_id'),
            'billed_tier': _get(response, 'service_tier'),
            'response': raw, 'content_cache_key': content_key,
        })
        n_input = _get(usage, 'prompt_tokens')
        n_output = _get(usage, 'completion_tokens')
        if not isinstance(n_input, int) or not isinstance(n_output, int):
            self.ledger.mark_unknown(aid, 'Response landed without complete usage; reservation retained')
            return response
        cached = _get(_get(usage, 'prompt_tokens_details'), 'cached_tokens', 0) or 0
        written = _get(_get(usage, 'prompt_tokens_details'), 'cache_write_tokens', None)
        if written is None:
            # Missing write counters are not evidence of zero writes. Settle at
            # the worst remaining-input rate and preserve this uncertainty.
            written = n_input - cached
            self.ledger.record_evidence(aid, 'missing_cache_write_usage', {
                'policy': 'Conservatively price remaining noncached input as writes; invoice unverified'})
        # Missing billed-tier metadata is conservatively settled at Standard.
        billed_tier = _get(response, 'service_tier') or 'default'
        if billed_tier not in ('flex', 'default', 'standard'):
            self.ledger.mark_unknown(aid, f'Unpriced returned service tier {billed_tier}; stop for reconciliation')
            raise BudgetExceeded('Unexpected billed tier; unknown reservation retained')
        # Settle before any downstream JSON/schema/quote parsing. Malformed paid
        # responses are real charges, and every retry creates a new reservation.
        self.ledger.settle(aid, input_tokens=n_input, output_tokens=n_output,
                           cached_tokens=cached, billed_tier=billed_tier,
                           cache_write_tokens=written,
                           response_id=_get(response, 'id'))
        return response


class BudgetedClient:
    def __init__(self, inner: Any, ledger: AtomicBudget, run_id: str, *, allow_paid: bool,
                 metadata: dict | None = None, helper_reasoning_effort: str | None = None):
        self.inner = inner
        self.chat = SimpleNamespace(completions=BudgetedCompletions(
            inner.chat.completions, ledger, run_id, allow_paid=allow_paid, metadata=metadata,
            helper_reasoning_effort=helper_reasoning_effort))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def make_luna_client(ledger: AtomicBudget, run_id: str, *, allow_paid: bool = False,
                     metadata: dict | None = None) -> BudgetedClient:
    """Common judge/helper transport; SDK internal retries explicitly disabled."""
    from openai import AsyncOpenAI
    if os.environ.get('OPENAI_BASE_URL'):
        raise ValueError('Custom OpenAI base URL is not part of the frozen pricing contract')
    inner = AsyncOpenAI(max_retries=0)
    return BudgetedClient(inner, ledger, run_id, allow_paid=allow_paid, metadata=metadata)


def make_luna_helper_diagnostic_client(ledger: AtomicBudget, run_id: str, *,
                                      reasoning_effort: str, allow_paid: bool = False) -> BudgetedClient:
    """Explicit helper-only effort ablation; the benchmark factory remains none-only."""
    from openai import AsyncOpenAI
    if reasoning_effort not in ('none', 'medium'):
        raise ValueError('Only the authorized none/medium helper diagnostic is supported')
    if os.environ.get('OPENAI_BASE_URL'):
        raise ValueError('Custom OpenAI base URL is not part of the frozen pricing contract')
    return BudgetedClient(AsyncOpenAI(max_retries=0), ledger, run_id, allow_paid=allow_paid,
        metadata={'purpose': 'candidate-only-helper-effort-diagnostic'},
        helper_reasoning_effort=reasoning_effort)


def load_upstream(root: Path = BENCH_ROOT) -> dict:
    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != BENCH_COMMIT:
        raise ValueError(f'WorkspaceBench revision mismatch: {revision}')
    src = str(root / 'src')
    if src not in sys.path:
        sys.path.insert(0, src)
    import wsbench
    if Path(wsbench.__file__).resolve().parent != (root / 'src/wsbench').resolve():
        raise ValueError('Another WorkspaceBench installation is already imported')
    for family in FAMILIES:
        importlib.import_module(f'wsbench.evals.{family}')
    audited = [root / 'src/wsbench/llm.py', root / 'src/wsbench/mcjudge.py', root / 'src/wsbench/cache.py']
    audited += [p for family in FAMILIES for p in sorted((root / 'src/wsbench/evals' / family).glob('*.py'))]
    audited += list(sorted((root / 'src/wsbench/multitoken').glob('*.py')))
    return {'benchmark_commit': revision, 'runtime_source_hashes': {str(p.relative_to(root)): file_hash(p) for p in audited}}


def install_upstream_transport(ledger: AtomicBudget, run_id: str, *, allow_paid: bool = False,
                               service_tier: str = 'flex', attempts: int = 2,
                               timeout_s: float = 180) -> None:
    """Patch only the client's transport seam; never source files/prompts/scorers."""
    if service_tier not in ('flex', 'default') or not 1 <= attempts <= 3:
        raise ValueError('Bounded attempts 1..3 and explicit Flex/Standard tier required')
    from wsbench import llm
    os.environ['WSBENCH_OPENAI_SERVICE_TIER'] = service_tier
    os.environ['WSBENCH_OPENAI_REASONING'] = 'none'
    os.environ['WSBENCH_OPENAI_TIMEOUT'] = str(timeout_s)
    os.environ.pop('WSBENCH_OPENAI_PRICE', None)
    llm._ATTEMPTS = attempts

    class CentralLedgerOnly:
        def check(self):
            snap = ledger.snapshot()
            if snap['halted'] or snap['remaining_hard_usd'] <= 0:
                raise llm.SpendCapError('Atomic project ledger halted/exhausted')
        def append(self, row):
            # Legacy caller calculates its run tally, but MUST NOT write in old project.
            pass

    llm._LEDGER = CentralLedgerOnly()
    def factory(route: str, key: str):
        if route != 'openai':
            raise llm.JudgeConfigError('Only direct Luna is authorized')
        client = make_luna_client(ledger, run_id, allow_paid=allow_paid,
                                  metadata={'purpose': 'workspacebench-judge'})
        original_create = client.chat.completions.create
        async def fatal_budget(**request):
            try:
                return await original_create(**request)
            except BudgetExceeded as error:
                raise llm.SpendCapError(str(error)) from error
        client.chat.completions.create = fatal_budget
        return client
    llm._make_client = factory


def install_shared_verdict_cache(path: Path, ledger: AtomicBudget, family: str) -> None:
    """Reuse validated upstream verdicts by exact request content, not cell ID.

    One process owns each family cache. Schema/source/validator contracts are
    included and current call validation is rerun on hits. Duplicate requests
    within a batch are coalesced before the unchanged upstream loop dispatches.
    """
    from wsbench import llm, mcjudge
    from wsbench.cache import fingerprint
    module=importlib.import_module(f'wsbench.evals.{family}.judge')
    original=getattr(module.run_calls,'_original',module.run_calls)
    source_contract=load_upstream()['runtime_source_hashes']
    path.parent.mkdir(parents=True,exist_ok=True)
    with contextlib.closing(sqlite3.connect(path)) as db:
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('CREATE TABLE IF NOT EXISTS verdicts (content_key TEXT PRIMARY KEY, body TEXT NOT NULL)')
        db.commit()
    def wrapped(calls,**kwargs):
        if kwargs.get('dry_run'):
            return original(calls,**kwargs)
        judge=kwargs['judge'];schema=kwargs['schema'];version=kwargs['prompt_version']
        validator=kwargs.get('validate');local=kwargs['cache']
        validator_source=inspect.getsource(validator) if validator is not None else None
        cap=kwargs.get('max_tokens') or llm._DEFAULT_MAX_TOKENS['openai']
        temperature=kwargs.get('temperature')
        def request(call):
            req={'model':judge.model,'reasoning_effort':llm.openai_effort(judge.reasoning),
                'messages':[{'role':'system','content':call.system},{'role':'user','content':call.user}],
                'response_format':{'type':'json_schema','json_schema':schema},'max_completion_tokens':cap}
            if temperature is not None and llm._TEMP_OK.get((judge.model,req['reasoning_effort']),True):
                req['temperature']=temperature
            return req
        def identity(call):
            request_key=request_cache_key(request(call))
            key=hashlib.sha256(canonical({'request':request_key,'prompt_version':version,
                'runtime_source_hashes':source_contract,'validator_source':validator_source}).encode()).hexdigest()
            return key,request_key
        representatives={};by_key={};unique=[]
        for call in calls:
            key,_=identity(call);by_key[call.key]=call
            if key not in representatives:representatives[key]=call;unique.append(call)
        mappings={}
        for call in unique:
            fp=fingerprint(version,judge.model,judge.reasoning,temperature,call.system,call.user)
            mappings[(call.key,fp)]=call
        class ExactCache:
            def get(self,key,fp,**unused):
                call=mappings[(key,fp)];content_key,request_key=identity(call)
                with contextlib.closing(sqlite3.connect(path)) as db:
                    found=db.execute('SELECT body FROM verdicts WHERE content_key=?',(content_key,)).fetchone()
                if not found:return None
                row=json.loads(found[0])
                if validator is not None and not validator(call,row['result']):return None
                payload={'result':row['result'],'meta':call.meta,'shared_cache_hit':{
                    'content_key':content_key,'request_key':request_key,'origin':row['origin']}}
                local.put(key,fp,payload)
                return payload
            def put(self,key,fp,payload):
                call=mappings[(key,fp)];content_key,request_key=identity(call)
                local.put(key,fp,payload)
                if payload.get('result') is None:return
                # Ledger owns original response/request identities and paid usage.
                with contextlib.closing(sqlite3.connect(ledger.path)) as db:
                    found=db.execute("SELECT attempt_id,metadata FROM attempts WHERE status='settled' "
                        "AND json_extract(metadata,'$.content_cache_key')=? ORDER BY created_utc DESC LIMIT 1",(request_key,)).fetchone()
                    response=None
                    if found:
                        event=db.execute("SELECT details FROM events WHERE attempt_id=? AND kind='physical_response' ORDER BY sequence DESC LIMIT 1",(found[0],)).fetchone()
                        response=json.loads(event[0]).get('response_id') if event else None
                body={'result':payload['result'],'origin':{'attempt_id':found[0] if found else None,
                    'response_id':response,'request_key':request_key,'original_cell_key':key}}
                with contextlib.closing(sqlite3.connect(path)) as db:
                    db.execute('INSERT OR IGNORE INTO verdicts VALUES (?,?)',(content_key,canonical(body)));db.commit()
        exact_cache=ExactCache()
        profiler=getattr(ledger,'_operational_profile',None)
        if profiler is not None:
            exact_cache.get=profiler.wrap('exact_cache.get',exact_cache.get)
            exact_cache.put=profiler.wrap('exact_cache.put',exact_cache.put)
        kwargs['cache']=exact_cache
        result=original(unique,**kwargs)
        expanded={}
        for call in calls:
            key,_=identity(call);representative=representatives.get(key)
            if representative is None:
                # Temperature was dropped by provider during this batch. The
                # representative mapping used the pre-dispatch contract.
                representative=next(c for c in unique if c.system==call.system and c.user==call.user)
            value=result.get(representative.key)
            expanded[call.key]=value if value is None or validator is None or validator(call,value) else None
        return expanded
    wrapped._original=original
    module.run_calls=wrapped


def convert_selected_readouts(records: list[dict], manifest_cells: list[dict], *,
                               sample_index: int = 0) -> tuple[dict[str, list[dict]], dict]:
    """One condition = one selected text/cell; never evaluate an entire pool as one arm."""
    expected = {x['cell_id']: x for x in manifest_cells}
    present: dict[str, dict] = {}
    for row in records:
        if row.get('sample_index', 0) != sample_index:
            continue
        position = row.get('position', row.get('pos'))
        cid = row.get('cell_id') or f"{row['family']}|{row['item_id']}|L{row['layer']:02d}|p{position:05d}"
        if cid not in expected:
            raise ValueError(f'Candidate outside frozen manifest: {cid}')
        ref = expected[cid]
        if any(row[k] != ref[k] for k in ('family', 'item_id', 'layer')) or position != ref['position']:
            raise ValueError(f'Candidate identity contradicts cell_id: {cid}')
        if cid in present:
            raise ValueError(f'Duplicate selected readout: {cid}')
        if not isinstance(row.get('text'), str):
            raise ValueError(f'Missing text: {cid}')
        present[cid] = row
    by_family: dict[str, list[dict]] = defaultdict(list)
    for cid in sorted(present):
        row, ref = present[cid], expected[cid]
        by_family[ref['family']].append({'id': ref['item_id'], 'layer': ref['layer'],
                'pos': ref['position'], 'token': ref.get('token', ''), 'samples': [row['text']]})
    missing = sorted(set(expected) - set(present))
    report = {'expected_cells': len(expected), 'produced_cells': len(present),
              'missing_cell_ids': missing, 'empty_cells': sum(not r['text'].strip() for r in present.values()),
              'sample_index': sample_index, 'readouts_per_cell': 1}
    return dict(by_family), report


def run_family(family: str, readouts: Path, out: Path, manifest_cells: list[dict], *,
               ledger: AtomicBudget | None = None, run_id: str = 'offline',
               allow_paid: bool = False, dry_run: bool = True, partial_grid: bool = True,
               concurrency: int = 4, rpm: float = 120, service_tier: str = 'flex') -> dict:
    if family not in FAMILIES:
        raise ValueError(f'Unsupported core family {family}')
    execution = transport_settings(concurrency, rpm, service_tier)
    if os.environ.get('OLENS_TRANSPORT_RECOVERY_SINCE'):
        execution['transport_recovery_guard'] = {'since_utc': os.environ['OLENS_TRANSPORT_RECOVERY_SINCE'],
            'maximum_unknown_in_latest_100': 5, 'maximum_new_unknown_usd': .10}
    rpm = execution['rpm']
    provenance = load_upstream()
    from wsbench.judge_config import resolve
    from wsbench.registry import JudgeArgs, get
    from wsbench.results import write_results
    from wsbench.readouts import load_readouts
    family_cells = [x for x in manifest_cells if x['family'] == family]
    if not family_cells:
        raise ValueError('Empty family manifest')
    cells, load_report = load_readouts(readouts)
    if any(load_report.skipped.values()) or load_report.kind != 'prose' or any(len(c.samples or ()) != 1 for c in cells):
        raise ValueError('Require valid unique prose cells with exactly one selected text; token-bag arms are a separate instrument')
    expected_keys = {(c['item_id'],c['layer'],c['position']) for c in family_cells}
    actual_keys = {(c.id,c.layer,c.pos) for c in cells}
    if actual_keys - expected_keys:
        raise ValueError('Readout cells outside the frozen manifest')
    missing_keys = expected_keys - actual_keys
    if missing_keys and not partial_grid:
        raise ValueError('Full-grid judging requires every prescribed manifest cell, including explicit abstentions')
    if not partial_grid:
        selected_ids={c['item_id'] for c in family_cells}
        frozen_rows=[json.loads(line) for line in paths(family)['index'].read_text().splitlines()]
        frozen_rows=[r for r in frozen_rows if r['id'] in selected_ids and r['layer'] in LAYERS[family]]
        if family=='chain_intermediates':
            last={}
            for row in frozen_rows:
                key=(row['id'],row['layer'])
                if key not in last or row['pos']>last[key]['pos']:last[key]=row
            frozen_rows=list(last.values())
        official_keys={(r['id'],r['layer'],r['pos']) for r in frozen_rows}
        if expected_keys!=official_keys:
            raise ValueError('A partial manifest cannot be relabeled full-grid: original family layers/read positions required')
    if any(x['split'] == 'test' for x in family_cells) and os.environ.get('OLENS_TEST_FROZEN') != '1':
        raise ValueError('Test access sealed until final settings are frozen')
    if not dry_run and family != 'multihop_mt':
        if ledger is None:
            raise ValueError('Shared atomic ledger required before judged execution')
        install_upstream_transport(ledger, run_id, allow_paid=allow_paid, service_tier=service_tier)
    spec = get(family)
    judge = resolve(spec.judge, flag=JUDGE_MODEL, env={'WSBENCH_OPENAI_REASONING': 'none'})
    out.mkdir(parents=True, exist_ok=True)
    args = JudgeArgs(readouts=readouts, out=out, judge=judge,
        layers=sorted({x['layer'] for x in family_cells}), items=sorted({x['item_id'] for x in family_cells}),
        limit=0, allow_missing=partial_grid, concurrency=concurrency, rpm=rpm, dry_run=dry_run,
        aux_models={}, extra={'verify': '1', 'cells': 'last', 'judge': 'regex'} if family == 'multihop_mt'
                  else {'verify': '1', 'cells': 'last'})
    result = spec.run(args)
    path = write_results(out, result)
    contract = {
        **provenance, 'result_path': str(path), 'project_judge_model': 'regex' if family == 'multihop_mt' else JUDGE_MODEL,
        'project_reasoning_effort': 'none', 'requested_service_tier': service_tier,
        'execution_transport': execution,
        'partial_grid': partial_grid, 'scientific_status': 'instrument-only' if dry_run else ('partial-cell-diagnostic' if partial_grid else 'frozen-grid-comparison'),
        'upstream_complete_preserved': result.complete,
        'benchmark_pin_note': 'Luna is a declared project instrument override of upstream Gemini; preserve upstream pinned/complete fields.',
        'manifest_expected_cells': len(family_cells), 'split': sorted({x['split'] for x in family_cells}),
        'manifest_produced_cells': len(actual_keys), 'manifest_missing_cells': len(missing_keys),
        'partial_upstream_headline_note': 'Upstream item recovery is any-layer/any-site over this partial file, not a cell rate or the official full-grid score.' if partial_grid and family!='hallucination' else None,
    }
    if not dry_run and family!='hallucination':
        cell_pass = {}
        if family=='role_bound_association':
            cell_pass = {(r['id'],r['layer'],r['pos']):bool(r['pass']) for r in result.rows}
        elif family=='multihop_mt':
            for row in result.rows:
                for layer,hits in row['layers'].items():
                    ref = next(c for c in family_cells if c['item_id']==row['id'] and c['layer']==int(layer))
                    cell_pass[(row['id'],int(layer),ref['position'])] = all(bool(hits['hits'].get(role)) for role in row['roles'])
        elif family=='chain_intermediates':
            for row in result.rows:
                for layer,kind in row['kind_by_layer'].items():
                    if kind!='unavailable':
                        ref = next(c for c in family_cells if c['item_id']==row['id'] and c['layer']==int(layer))
                        cell_pass[(row['id'],int(layer),ref['position'])] = kind=='hit'
        empty_keys={(c.id,c.layer,c.pos) for c in cells if c.empty}
        judged=len(cell_pass)
        passed=sum(cell_pass.values())
        contract['cell_diagnostic'] = {
            'metric':'complete_role_binding' if family=='role_bound_association' else 'required_bridge_recovery' if family=='multihop_mt' else 'top1_intermediate_recovery',
            'passed_cells':passed,'judged_cells':judged,'expected_cells':len(expected_keys),
            'rate_over_judged':passed/judged if judged else None,
            'rate_over_intended_cells':passed/len(expected_keys),
            'empty_abstentions':len(empty_keys),
            'api_or_missing_unjudged_cells':len(expected_keys-set(cell_pass)-empty_keys),
            'rows':[{'item_id':i,'layer':l,'position':p,'pass':hit} for (i,l,p),hit in sorted(cell_pass.items())],
        }
    if family == 'hallucination':
        extras = result.extras
        wrong = extras.get('n_hallucinated', 0)
        specific = extras.get('n_specific', 0)
        off = extras.get('n_off_topic', 0)
        judged = extras.get('n_readouts', 0)
        tallied = extras.get('n_readouts_claims_judged', 0)
        produced_nonempty=len(actual_keys)-load_report.n_empty
        contract['hallucination_stage2'] = {
            'required': True, 'judged_readouts': judged, 'claim_tallied_readouts': tallied,
            'coverage': tallied / judged if judged else None,
            'produced_nonempty_readouts':produced_nonempty,
            'stage1_coverage_over_nonempty_produced':judged/produced_nonempty if produced_nonempty else None,
            'stage2_coverage_over_nonempty_produced':tallied/produced_nonempty if produced_nonempty else None,
            'stage1_api_or_missing_readouts':produced_nonempty-judged,
            'stage2_api_or_missing_readouts':produced_nonempty-tallied,
            'stage2_complete_for_produced_readouts':not dry_run and tallied==judged==produced_nonempty and judged>0,
            'main_comparison_eligible':not dry_run and not partial_grid and tallied==judged==produced_nonempty and judged>0,
            'secondary_wrong_over_wrong_plus_consistent': wrong / (specific - off) if specific > off else None,
            'span_vs_claim_caveat': 'False tallies are established spans; true/unverifiable tallies are claims. Not uniform atomic precision.',
            'assertion_share_over_all_produced_outputs': specific/len(actual_keys) if actual_keys else None,
            'produced_empty_abstentions': load_report.n_empty,
        }
    (out / 'project_contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    return {'upstream': result.to_json(), 'project_contract': contract}


def paired_group_interval(baseline: dict[str, tuple[float, float]],
                           proposed: dict[str, tuple[float, float]], group_of: dict[str, str], *,
                           seed: int = 20261010, replicates: int = 2000) -> dict:
    """Paired ratio-of-sums delta, resampling whole groups with shared draws.

For item recovery use (pass,1); for contradiction use (wrong,specific). Groups
retain unequal item/cell contributions rather than silently macro-averaging.
"""
    if baseline.keys() != proposed.keys() or not baseline:
        raise ValueError('Require identical nonempty paired item cohorts')
    groups: dict[str, list[str]] = defaultdict(list)
    for item in sorted(baseline):
        groups[group_of[item]].append(item)
    keys = sorted(groups)
    def estimate(arm: dict, draw: list[str]) -> float | None:
        num = den = 0.0
        for group in draw:
            for item in groups[group]:
                a, b = arm[item]
                num += a
                den += b
        return num / den if den else None
    b, p = estimate(baseline, keys), estimate(proposed, keys)
    rng = random.Random(seed)
    deltas = []
    for _ in range(replicates):
        draw = rng.choices(keys, k=len(keys))
        left, right = estimate(baseline, draw), estimate(proposed, draw)
        if left is not None and right is not None:
            deltas.append(right - left)
    deltas.sort()
    ci = [deltas[int(.025 * (len(deltas)-1))], deltas[int(.975 * (len(deltas)-1))]] if deltas else None
    return {'baseline': b, 'proposed': p, 'delta': p - b if b is not None and p is not None else None,
            'ci95_delta': ci, 'items': len(baseline), 'independent_groups': len(keys),
            'seed': seed, 'bootstrap_replicates': replicates, 'defined_draws': len(deltas),
            'warning': 'Tiny group count; intervals cannot establish robustness' if len(keys) < 10 else None}


def evaluation_stage(manifest: Path, fresh_manifest: Path | None = None,
                     gate: Path | None = None):
    """Authorize a stage before reading selected text or opening paid transport."""
    body = manifest.read_bytes()
    fresh_body = fresh_manifest.read_bytes() if fresh_manifest else None
    gate_body = gate.read_bytes() if gate else None
    stage, cells, captures = validate_export_stage(body, fresh_body, gate_body)
    authorization = None
    if gate_body is not None:
        authorization = {'split':stage,'fresh_manifest_sha256':hashlib.sha256(fresh_body).hexdigest(),
                         'coordinator_gate_sha256':hashlib.sha256(gate_body).hexdigest()}
    return json.loads(body), stage, captures, authorization


@profile_condition
def evaluate_condition(selections: Path, manifest: Path, out: Path, *, method: str,
                       n: int, ledger_path: Path, run_id: str, run_cap_usd: str = '1',
                       allow_paid: bool = False, concurrency: int = 8,
                       service_tier: str = 'flex', family_only: str | None = None,
                       shared_cache: Path | None = None, rpm: float = 120,
                       fresh_manifest: Path | None = None, gate: Path | None = None) -> dict:
    """Evaluate one immutable per-cell condition; run different arms in processes.

    The pinned upstream transport is module-global, so independent arms must not
    race its run ID in threads. Paid outputs and provenance stay outside Git.
    """
    frozen, stage, captures, authorization = evaluation_stage(manifest, fresh_manifest, gate)
    execution = transport_settings(concurrency, rpm, service_tier)
    selected = []
    with selections.open() as source:
        for line in source:
            row = json.loads(line)
            if row.get('split', stage) != stage:
                raise ValueError('Selected source stage differs from analysis cohort')
            if captures and (row['cell_id'] not in captures or
                             row.get('activation_sha256') != captures[row['cell_id']]['activation_sha256']):
                raise ValueError('Selected source activation differs from analysis-authorized fresh capture')
            if 'selections' in row:
                matches = [x for x in row['selections'] if x['method'] == method and x['n'] == n]
                if len(matches) != 1:
                    raise ValueError(f'Require exactly one {method}/N{n} selection per cell')
                text = matches[0]['text']
            elif row.get('method') == method and row.get('pool_n', n) == n:
                text = row['text']
            else:
                raise ValueError('Selected condition does not match declared method/budget')
            selected.append({k: row[k] for k in ('cell_id','family','item_id','layer','position')} |
                            {'text': text, 'sample_index': 0})
    by_family, coverage = convert_selected_readouts(selected, frozen['cells'])
    if coverage['missing_cell_ids']:
        raise ValueError('Condition missing cells; write explicit empty abstentions instead')
    out.mkdir(parents=True, exist_ok=True)
    condition = {'method': method, 'n': n, 'selection_sha256': file_hash(selections),
        'manifest_sha256': file_hash(manifest), 'coverage': coverage,
        'partial_grid': bool(frozen.get('partial_grid', False)), 'run_id': run_id,
        'service_tier': service_tier}
    if authorization is not None:
        condition['analysis_authorization'] = authorization
    identity = out/'condition.json'
    if identity.exists() and json.loads(identity.read_text()) != condition:
        raise ValueError('Existing condition provenance differs; use a new run directory')
    temporary=identity.with_name(identity.name+f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(condition, indent=2)+'\n')
    os.replace(temporary,identity)
    ledger = AtomicBudget(ledger_path)
    profiler = CURRENT_PROFILE.get()
    if profiler is not None: profiler.attach_ledger(ledger)
    if allow_paid:
        ledger.set_run_limit(run_id, run_cap_usd)
    results = {}
    for family in ([family_only] if family_only else FAMILIES):
        if shared_cache is not None and family!='multihop_mt':
            load_upstream()
            install_shared_verdict_cache(shared_cache/f'{family}.sqlite3',ledger,family)
        readouts = out/f'{family}.readouts.jsonl'
        content = ''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in by_family[family])
        if readouts.exists() and readouts.read_text() != content:
            raise ValueError('Readout identity changed in an existing condition directory')
        readouts.write_text(content)
        # Transport tuning does not alter the immutable scientific condition.
        # Record each execution separately, including resumptions using a cache.
        started = time.monotonic()
        stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        event = {'started_utc': stamp, 'pid': os.getpid(), 'family': family, 'run_id': run_id,
                 'condition': {'method': method, 'n': n}, 'transport': execution,
                 'allow_paid': allow_paid, 'status': 'running'}
        history = out/f'{family}.execution.jsonl'
        def record_execution(row):
            with history.open('a') as handle:
                handle.write(json.dumps(row) + '\n')
        record_execution(event)
        try:
            results[family] = run_family(family, readouts, out/family, frozen['cells'],
                ledger=ledger, run_id=run_id, allow_paid=allow_paid, dry_run=not allow_paid,
                partial_grid=condition['partial_grid'], concurrency=concurrency,
                service_tier=service_tier, rpm=execution['rpm'])
        except BaseException as error:
            record_execution({**event, 'status': 'failed', 'error_type': type(error).__name__,
                              'wall_seconds': time.monotonic() - started})
            raise
        record_execution({**event, 'status': 'completed', 'wall_seconds': time.monotonic() - started,
                          'finished_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    summary = {'condition': condition, 'families': results, 'budget': ledger.snapshot()}
    (out/(f'{family_only}.summary.json' if family_only else 'summary.json')).write_text(json.dumps(summary, indent=2)+'\n')
    return summary


async def repeat_request_audit(inputs: Path, out: Path, *, ledger_path: Path, run_id: str,
                               cap_usd: str, service_tier: str = 'default', concurrency: int = 4) -> dict:
    """Replay frozen prompts once without replacing or caching primary verdicts."""
    prepared=json.loads(inputs.read_text());ledger=AtomicBudget(ledger_path)
    ledger.set_run_limit(run_id,cap_usd);out.mkdir(parents=True,exist_ok=True)
    identity=out/'input_identity.json';frozen={'input_sha256':file_hash(inputs),'run_id':run_id}
    if identity.exists() and json.loads(identity.read_text())!=frozen:
        raise ValueError('Repeatability audit inputs changed in an existing run directory')
    identity.write_text(json.dumps(frozen,indent=2)+'\n')
    client=make_luna_client(ledger,run_id,allow_paid=True,metadata={'purpose':'judge-repeatability-audit'})
    semaphore=asyncio.Semaphore(concurrency)
    checkpoint=out/'requests.jsonl'
    rows=[json.loads(s) for s in checkpoint.read_text().splitlines()] if checkpoint.exists() else []
    completed={r['audit_id'] for r in rows}
    if completed-{r['audit_id'] for r in prepared['requests']}:
        raise ValueError('Unexpected audit checkpoint cases')
    def stage1(result):
        if result is None:return None
        return [{'kind':s['kind'],'wrong_spans':sorted(span['text'] for span in s.get('spans',[]) if span['type']=='wrong'),
            'off_topic_spans':sorted(span['text'] for span in s.get('spans',[]) if span['type']=='off_topic')}
            for s in result.get('samples',[])]
    def stage2(result):
        return [[(c['quote'],c['status']) for c in s.get('claims',[])] for s in result.get('samples',[])]
    async def one(case):
        request={**case['request'],'service_tier':service_tier,'timeout':90}
        row={k:v for k,v in case.items() if k!='request'}
        row['actual_content_key']=request_cache_key(request)
        try:
            async with semaphore:response=await client.chat.completions.create(**request)
            choice=response.choices[0]
            if choice.finish_reason!='stop' or getattr(choice.message,'refusal',None):
                raise ValueError('Refused or truncated repeatability response')
            repeated=json.loads(choice.message.content or '')
            row.update({'repeat_result':repeated,'repeat_response_id':response.id,'status':'completed'})
            row['full_json_changed']=canonical(repeated)!=canonical(case['original_result'])
            if case['stage']=='stage1':
                before=stage1(case['original_result']);after=stage1(repeated)
                row.update({'original_classification':before,'repeat_classification':after,
                    'classification_or_span_changed':before!=after,
                    'wrongness_flipped':bool(any(x['wrong_spans'] for x in before))!=bool(any(x['wrong_spans'] for x in after))})
            else:
                row['fixed_evidence_caveat']='Original stage1 established-false spans replayed unchanged; this cannot adjudicate stage1 wrongness.'
                row['claim_or_status_changed']=stage2(repeated)!=stage2(case['original_result'])
        except Exception as error:
            row.update({'status':'failed','error_type':type(error).__name__,
                'error_code':getattr(error,'code',None),'http_status':getattr(error,'status_code',None)})
        rows.append(row)
        tmp=checkpoint.with_suffix('.tmp')
        tmp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in sorted(rows,key=lambda r:r['audit_id'])))
        os.replace(tmp,checkpoint)
    try:await asyncio.gather(*(one(case) for case in prepared['requests'] if case['audit_id'] not in completed))
    finally:await client.close()
    summary={'input_sha256':file_hash(inputs),'primary_results_changed':False,
        'physical_attempts_per_request_limit':1,'cache_namespace':'independent audit; no primary verdict cache reuse',
        'stage1_requests':sum(r['stage']=='stage1' for r in rows),
        'stage1_completed':sum(r['stage']=='stage1' and r['status']=='completed' for r in rows),
        'stage1_wrongness_flips':sum(r.get('wrongness_flipped',False) for r in rows),
        'stage1_classification_or_span_changes':sum(r.get('classification_or_span_changed',False) for r in rows),
        'stage2_requests':sum(r['stage']=='stage2' for r in rows),
        'stage2_completed':sum(r['stage']=='stage2' and r['status']=='completed' for r in rows),
        'stage2_full_json_changes':sum(r['stage']=='stage2' and r.get('full_json_changed',False) for r in rows),
        'stage2_claim_or_status_changes':sum(r.get('claim_or_status_changed',False) for r in rows),
        'failed_requests':sum(r['status']=='failed' for r in rows),
        'selection_rule':prepared['selection_rule'],'budget':ledger.snapshot(),
        'limitation':'Repeat agreement is reliability evidence, not proof of correct contradiction labels. Random and posthoc flagged cases are separate.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def _main() -> None:
    import argparse
    import ast
    p = argparse.ArgumentParser(description='One frozen condition through pinned WorkspaceBench scoring')
    p.add_argument('--selections', type=Path, required=True)
    p.add_argument('--manifest', type=Path, default=Path('configs/splits_pilot_shared_v2.json'))
    p.add_argument('--fresh-manifest', type=Path)
    p.add_argument('--gate', type=Path, help='Exact analysis gate; required for validation/test')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--method', required=True)
    p.add_argument('--n', type=int, default=1)
    p.add_argument('--run-id', required=True)
    p.add_argument('--run-cap-usd', default='1')
    p.add_argument('--ledger', type=Path, default=Path('${OLENS_DATA_ROOT}/budget/ledger.sqlite3'))
    p.add_argument('--concurrency', type=int, default=8)
    p.add_argument('--rpm', type=positive_rpm, default=120,
                   help='Positive per-family logical calls/minute; default120, not a global provider limit')
    p.add_argument('--tier', choices=['flex','default'], default='flex')
    p.add_argument('--allow-paid', action='store_true')
    p.add_argument('--family',choices=FAMILIES)
    p.add_argument('--shared-cache',type=Path)
    p.add_argument('--condition-list',type=Path,help='Sequential conditions within one family worker')
    p.add_argument('--performance-profile-dir',type=Path,
                   help='Opt-in bounded timing/heartbeat summaries; no request contents or identities')
    p.add_argument('--performance-profile-child',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--stop-file',type=Path,
                   help='If this file exists, stop before the next condition; never cancel current calls. SIGUSR1 requests the same boundary stop in family workers.')
    p.add_argument('--all-families',action='store_true',help='Four processes, one cache writer/family; bounded calls per process')
    p.add_argument('--repeat-request-audit',type=Path,help='Frozen original requests; audit once without changing primary results')
    a = p.parse_args()
    if a.performance_profile_dir:
        # One directory per execution; avoid overwriting timing evidence when
        # a cached condition is resumed. Children use distinct family names.
        if not a.performance_profile_child:
            if a.performance_profile_dir.exists():
                p.error('--performance-profile-dir must be a fresh execution directory')
            if a.all_families:
                a.performance_profile_dir.mkdir(parents=True)
        elif not a.family or a.all_families or not a.performance_profile_dir.is_dir():
            p.error('Invalid internal profile child configuration')
    evaluation_stage(a.manifest, a.fresh_manifest, a.gate)
    if a.allow_paid:
        if not os.environ.get('OPENAI_API_KEY'):
            for line in Path('.env').read_text().splitlines():
                key, sep, value = line.removeprefix('export ').partition('=')
                if sep and key.strip() == 'OPENAI_API_KEY':
                    value = value.strip()
                    os.environ['OPENAI_API_KEY'] = ast.literal_eval(value) if value[:1] in ('"',"'") else value
        os.environ['OLENS_ALLOW_PAID_CALLS'] = '1'
    if a.repeat_request_audit:
        if not a.allow_paid:p.error('Repeatability dispatch requires explicit --allow-paid')
        print(json.dumps(asyncio.run(repeat_request_audit(a.repeat_request_audit,a.output,
            ledger_path=a.ledger,run_id=a.run_id,cap_usd=a.run_cap_usd,
            service_tier=a.tier,concurrency=a.concurrency)),indent=2))
        return
    if a.all_families:
        if a.family:p.error('--all-families and --family are mutually exclusive')
        a.output.mkdir(parents=True,exist_ok=True)
        command=[sys.executable,'-m','olens_improve.evaluation']+[x for x in sys.argv[1:] if x!='--all-families']
        if a.performance_profile_dir: command.append('--performance-profile-child')
        workers=[]
        for family in FAMILIES:
            with (a.output/f'{family}.worker.log').open('a') as log:
                process=subprocess.Popen(command+['--family',family],stdout=log,stderr=subprocess.STDOUT)
            workers.append(process)
            print(json.dumps({'family':family,'pid':process.pid}),flush=True)
        codes=[process.wait() for process in workers]
        if any(codes):raise SystemExit('Family worker failures: '+str(codes))
        return
    # A shared family cache has one active writer. This gate also prevents an
    # accidental second launch from paying the same in-flight requests.
    owner=None
    if a.shared_cache:
        if not a.family:p.error('--shared-cache requires --family or --all-families')
        import fcntl
        a.shared_cache.mkdir(parents=True,exist_ok=True)
        owner=(a.shared_cache/f'{a.family}.owner.lock').open('a')
        try:fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Another worker owns this family cache; no calls dispatched')
    stop = ConditionBoundaryStop(a.stop_file)
    signal.signal(signal.SIGUSR1, stop.request)
    conditions=json.loads(a.condition_list.read_text()) if a.condition_list else [{'method':a.method,'n':a.n}]
    for condition in conditions:
        if stop.requested():
            print(json.dumps({'status':'condition_queue_stopped_at_boundary','family':a.family,
                'run_id':a.run_id,'next_condition':condition,
                'reason':'SIGUSR1' if stop.signaled else 'stop_file'}),flush=True)
            break
        out=a.output/f"{condition['method']}-n{condition['n']}" if a.condition_list else a.output
        result = evaluate_condition(a.selections, a.manifest, out, method=condition['method'],
            n=condition['n'], ledger_path=a.ledger, run_id=a.run_id, run_cap_usd=a.run_cap_usd,
            allow_paid=a.allow_paid, concurrency=a.concurrency, service_tier=a.tier,
            family_only=a.family,shared_cache=a.shared_cache,rpm=a.rpm,
            fresh_manifest=a.fresh_manifest,gate=a.gate,
            performance_profile=(a.performance_profile_dir/f'{a.family or "all"}-{condition["method"]}-n{condition["n"]}.json')
                if a.performance_profile_dir else None)
        print(json.dumps({'condition':result['condition'], 'budget':result['budget']}),flush=True)


if __name__ == '__main__':
    _main()
