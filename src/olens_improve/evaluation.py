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
from types import SimpleNamespace
from typing import Any

from .budget import AtomicBudget, BudgetExceeded, request_input_upper_bound
from .data import BENCH_COMMIT, FAMILIES, SOURCE_ROOT, canonical, file_hash

JUDGE_MODEL = 'gpt-6-luna'
BENCH_ROOT = SOURCE_ROOT / 'scratch/repos/workspace-bench-v2'


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def request_cache_key(request: dict) -> str:
    """Full content/settings identity; service tier and transport timeout are omitted.

The schema, model, effort, temperature and output cap are included. This key is
recorded beside physical attempts; upstream still owns validated-result caching.
"""
    content = {k: v for k, v in request.items() if k not in ('service_tier', 'timeout')}
    return hashlib.sha256(canonical(content).encode()).hexdigest()


class BudgetedCompletions:
    def __init__(self, inner: Any, ledger: AtomicBudget, run_id: str,
                 *, allow_paid: bool = False, metadata: dict | None = None):
        self.inner = inner
        self.ledger = ledger
        self.run_id = run_id
        self.allow_paid = allow_paid
        self.metadata = metadata or {}

    async def create(self, **request: Any) -> Any:
        if not self.allow_paid or os.environ.get('OLENS_ALLOW_PAID_CALLS') != '1':
            raise RuntimeError('Paid calls disabled; root must verify shared ledger and tiny run cap first')
        if request.get('model') != JUDGE_MODEL or request.get('reasoning_effort') != 'none':
            raise ValueError('Only frozen gpt-6-luna with reasoning_effort=none is authorized')
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
        serializable = {k: v for k, v in request.items() if k != 'timeout'}
        aid = self.ledger.reserve_attempt(input_bound, max_output, run_id=self.run_id,
                    metadata={**self.metadata, 'content_cache_key': content_key,
                              'request': serializable, 'pid': os.getpid(),
                              'requested_tier': request['service_tier']})
        started = time.monotonic()
        try:
            response = await self.inner.create(**request)
        except BaseException as error:
            # Timeouts, cancellation and transport failures can still be billed.
            # Even status errors remain reserved until definitive reconciliation.
            self.ledger.mark_unknown(aid, f'{type(error).__name__}; physical attempt outcome uncertain')
            self.ledger.record_evidence(aid, 'transport_failure', {
                'exception_type': type(error).__name__, 'latency_s': time.monotonic() - started,
                'provider_request_id': getattr(error, 'request_id', None),
                'http_status': getattr(error, 'status_code', None),
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
        # Missing billed-tier metadata is conservatively settled at Standard.
        billed_tier = _get(response, 'service_tier') or 'default'
        if billed_tier not in ('flex', 'default', 'standard'):
            self.ledger.mark_unknown(aid, f'Unpriced returned service tier {billed_tier}; stop for reconciliation')
            raise BudgetExceeded('Unexpected billed tier; unknown reservation retained')
        # Settle before any downstream JSON/schema/quote parsing. Malformed paid
        # responses are real charges, and every retry creates a new reservation.
        self.ledger.settle(aid, input_tokens=n_input, output_tokens=n_output,
                           cached_tokens=cached, billed_tier=billed_tier,
                           response_id=_get(response, 'id'))
        return response


class BudgetedClient:
    def __init__(self, inner: Any, ledger: AtomicBudget, run_id: str, *, allow_paid: bool,
                 metadata: dict | None = None):
        self.inner = inner
        self.chat = SimpleNamespace(completions=BudgetedCompletions(
            inner.chat.completions, ledger, run_id, allow_paid=allow_paid, metadata=metadata))

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
        contract['hallucination_stage2'] = {
            'required': True, 'judged_readouts': judged, 'claim_tallied_readouts': tallied,
            'coverage': tallied / judged if judged else None,
            'stage2_complete_for_produced_readouts': not dry_run and tallied == judged and judged > 0,
            'main_comparison_eligible': not dry_run and not partial_grid and tallied == judged and judged > 0,
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
