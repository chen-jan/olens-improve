"""Read-only exact upstream request/cache forecast; never dispatch model calls."""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import sqlite3
import statistics
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.evaluation import load_upstream,request_cache_key,JUDGE_MODEL,evaluation_stage
from olens_improve.budget import request_input_upper_bound,cost_units
from olens_improve.data import canonical


def load(p):return json.loads(p.read_text())
def sha(p):
    digest=hashlib.sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def selection_rows(path,wanted,cells=None,captures=None):
    """Discard fit/atom traces while streaming; large exports stay off HOME/RAM."""
    rows={}
    with path.open() as stream:
        for line in stream:
            if not line.strip():continue
            row=json.loads(line);cid=row['cell_id']
            if cid in rows:raise ValueError('Duplicate cell in selection export')
            if cells is not None and (cid not in cells or any(row.get(k)!=cells[cid][k]
                    for k in ('family','item_id','layer','position','split'))):
                raise ValueError('Selection identity differs from the analysis-authorized cohort')
            if captures and row.get('activation_sha256')!=captures[cid]['activation_sha256']:
                raise ValueError('Selection activation differs from the analysis-authorized capture')
            rows[cid]={'cell_id':cid,'selections':[{'method':s['method'],'n':s['n'],'text':s['text']}
                for s in row['selections'] if (s['method'],s['n']) in wanted]}
    return rows


def source_validator(module,contains):
    path=Path(module.__file__)
    matches=[n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n,ast.Lambda) and contains in ast.unparse(n)]
    if len(matches)!=1:raise ValueError('Upstream validator location ambiguous')
    fn=eval(compile(ast.Expression(matches[0]),str(path),'eval'),module.__dict__)
    return fn,inspect.getsource(fn)


def forecast_stage(args):
    """Reject unauthorized heldout planning before text, banks or caches open."""
    manifest,stage,captures,authorization=evaluation_stage(args.manifest,
        getattr(args,'fresh_manifest',None),getattr(args,'gate',None))
    family=getattr(args,'family',None)
    if family is not None:
        if stage!='development':
            raise ValueError('Family-only forecast is restricted to development')
        if family not in ('hallucination','chain_intermediates','role_bound_association'):
            raise ValueError('Unsupported paid forecast family')
        if not getattr(args,'empirical_summary',None):
            raise ValueError('Family-only forecast requires a frozen empirical summary; no ledger scan')
    if stage!='development':
        if len(args.conditions)!=1:
            raise ValueError('Heldout forecast requires the one exact signed condition list')
        gate=load(args.gate)
        if sha(args.conditions[0])!=gate.get('condition_list_sha256'):
            raise ValueError('Forecast condition list differs from the signed stage menu')
        if sha(Path(gate['freeze_path']))!=gate.get('freeze_sha256'):
            raise ValueError('Forecast stage freeze changed')
    return manifest,stage,captures,authorization


def run(args):
    manifest,stage,captures,authorization=forecast_stage(args)
    family_only=getattr(args,'family',None)
    if args.output.exists():raise FileExistsError('Preserve immutable earlier forecasts')
    contract=load_upstream()['runtime_source_hashes']
    from wsbench import llm
    from wsbench.mcjudge import load_bank
    modules={f:importlib.import_module(f'wsbench.evals.{f}.judge') for f in ('hallucination','chain_intermediates','role_bound_association')}
    h=modules['hallucination'];hp=importlib.import_module('wsbench.evals.hallucination.prompts')
    validators={'hall_stage1':source_validator(h,'fully_judged'),'hall_stage2':source_validator(h,'tally_claims')}
    cap=llm._DEFAULT_MAX_TOKENS['openai']
    banks={'hallucination':load_bank('hallucination')['items'],
        'chain_intermediates':modules['chain_intermediates'].load_bank(modules['chain_intermediates'].BANK)[1],
        'role_bound_association':load_bank('role_bound_association')}
    by_id={f:{r['id']:r for r in bank} for f,bank in banks.items()}
    blocks={r['id']:modules['role_bound_association'].build_block(r,banks['role_bound_association'])[0] for r in banks['role_bound_association']}
    cells={r['cell_id']:r for r in manifest['cells']}
    conditions=[r for p in args.conditions for r in load(p)]
    if len({(r['method'],r['n']) for r in conditions})!=len(conditions):
        raise ValueError('Duplicate declared condition')
    pools=[]
    wanted={(r['method'],r['n']) for r in conditions}
    for path in args.selections:
        pool=selection_rows(path,wanted,cells if stage!='development' or family_only else None,captures)
        if pool.keys()!=cells.keys():raise ValueError('Incomplete selection cohort')
        pools.append(pool)
    if family_only:
        # Scope cannot hide missing/duplicate methods anywhere in the original
        # frozen source. Validate the full cohort before filtering its loop.
        for cond in conditions:
            for cid in cells:
                matches=[s for pool in pools for s in pool[cid]['selections']
                    if s['method']==cond['method'] and s['n']==cond['n']]
                if len(matches)!=1:raise ValueError('Missing/duplicate declared condition in full cohort')
        scoped_cells={cid:cell for cid,cell in cells.items() if cell['family']==family_only}
        if not scoped_cells:raise ValueError('Requested family has no frozen cells')
    else:
        scoped_cells=cells
    caches={}
    for family in modules:
        if family_only and family!=family_only:continue
        connection=sqlite3.connect('file:'+str(args.cache/f'{family}.sqlite3')+'?mode=ro',uri=True)
        # Autocommit point reads avoid retaining a family-cache read lock across
        # loading every historical verdict while an existing writer is active.
        connection.isolation_level=None
        caches[family]=connection
    observed_schemas={};seen=set();cached_rows={};stage1_to_stage2={};summary={};row_counts=Counter();gross_reservation=0
    per_condition=[];condition_counts=None
    def request(system,user,schema,temperature=None):
        result={'model':JUDGE_MODEL,'reasoning_effort':'none','messages':[{'role':'system','content':system},{'role':'user','content':user}],
            'response_format':{'type':'json_schema','json_schema':schema},'max_completion_tokens':cap}
        if temperature is not None:result['temperature']=temperature
        return result
    def probe(family,stage,req,version,validator=None,meta=None):
        nonlocal gross_reservation
        rkey=request_cache_key(req);vsource=validator[1] if validator else None
        key=hashlib.sha256(canonical({'request':rkey,'prompt_version':version,'runtime_source_hashes':contract,'validator_source':vsource}).encode()).hexdigest()
        local_key=(family,key)
        if local_key not in cached_rows:
            cursor=caches[family].execute('SELECT body FROM verdicts WHERE content_key=?',(key,))
            stored=cursor.fetchone();cursor.close()
            cached_rows[local_key]=json.loads(stored[0]) if stored else None
        cache=cached_rows[local_key]
        if cache and validator and not validator[0](SimpleNamespace(meta=meta),cache['result']):cache=None
        counts=summary.setdefault(stage,Counter());counts['logical_rows']+=1
        stage_counts=condition_counts.setdefault(stage,Counter());stage_counts['logical_rows']+=1
        if key in seen:counts['duplicate_rows_within_campaign']+=1
        else:
            seen.add(key);counts['unique_requests']+=1;counts['validated_cache_hits']+=bool(cache);counts['uncached_unique_requests']+=not bool(cache)
            stage_counts['new_campaign_unique_requests']+=1;stage_counts['validated_cache_hits']+=bool(cache);stage_counts['uncached_unique_requests']+=not bool(cache)
            if not cache:gross_reservation+=cost_units(request_input_upper_bound({**req,'service_tier':'default'}),cap,cache_write_tokens=request_input_upper_bound({**req,'service_tier':'default'}))/1e9
        observed_schemas[hashlib.sha256(canonical(req['response_format']['json_schema']).encode()).hexdigest()]=stage
        return key,cache
    for cond in conditions:
        method,n=cond['method'],cond['n']
        condition_counts={};unknown_before=sum(v is None for v in stage1_to_stage2.values())
        for cid in scoped_cells:
            choice=[s for pool in pools for s in pool[cid]['selections'] if s['method']==method and s['n']==n]
            if len(choice)!=1:raise ValueError('Missing/duplicate declared condition')
            text=choice[0]['text'];cell=cells[cid];family=cell['family'];row_counts[family]+=1
            if not text.strip():row_counts[family+'_empty']+=1;continue
            if family=='multihop_mt':continue
            module=modules[family]
            if family=='hallucination':
                item=by_id[family][cell['item_id']];site=next(s for s in item['sites'] if s['pos']==cell['position'])
                system,user=hp.judge_prompt(item,site,[text]);key,cached=probe(family,'hall_stage1',request(system,user,h.JUDGE_SCHEMA),h.PROMPT_VERSION,validators['hall_stage1'],{'samples':[text]})
                if key not in stage1_to_stage2:
                    if cached:
                        verdict=h.parse_verdict(cached['result'],[text]);wrong=[list(v.wrong) for v in verdict]
                        system,user=hp.verify_prompt(item,site,[text],wrong)
                        stage1_to_stage2[key]=probe(family,'hall_stage2_known',request(system,user,h.VERIFY_SCHEMA),h.VERIFY_PROMPT_VERSION,validators['hall_stage2'],{'samples':[text],'wrong':wrong})[0]
                    else:stage1_to_stage2[key]=None
            elif family=='chain_intermediates':
                probe(family,'chain',request(module.SYSTEM,module.render_user(text),module.SCHEMA,0.0),module.PROMPT_VERSION)
            else:
                probe(family,'role',request(module.SYSTEM,module.prompts.render_user(text,blocks[cell['item_id']]),module.SCHEMA),module.PROMPT_VERSION)
        unknown_after=sum(v is None for v in stage1_to_stage2.values())
        per_condition.append({'method':method,'n':n,'stage_counts':{s:dict(v) for s,v in condition_counts.items()},
            'new_unknown_hall_stage2_upper':unknown_after-unknown_before})
    unknown_stage2=sum(v is None for v in stage1_to_stage2.values())
    # Stage2 usage is relevant even when every stage1 request is new and its
    # future exact span-conditioned stage2 prompt cannot yet be constructed.
    observed_schemas[hashlib.sha256(canonical(h.VERIFY_SCHEMA).encode()).hexdigest()]='hall_stage2_known'
    # Empirical healthy Standard responses, classified by exact current schema.
    empirical=defaultdict(lambda:{'costs':[],'latencies':[],'input_tokens':[],'output_tokens':[]})
    empirical_summary=getattr(args,'empirical_summary',None)
    if empirical_summary:
        prior=load(empirical_summary)
        if prior['source_contract']!=contract or prior['output_cap']!=cap:
            raise ValueError('Empirical reference uses a different upstream request contract')
        measurements=prior['empirical_standard_response_measurements']
    else:
        db=sqlite3.connect('file:'+str(args.ledger)+'?mode=ro',uri=True)
        for actual,m,d in db.execute("select a.actual,a.metadata,e.details from attempts a join events e on a.attempt_id=e.attempt_id where a.status='settled' and a.created_utc>=? and e.kind='physical_response'",(args.empirical_since,)):
            metadata=json.loads(m);req=metadata.get('request') or {};raw=json.loads(d)
            if req.get('reasoning_effort')!='none' or req.get('model')!=JUDGE_MODEL or raw.get('billed_tier') not in ('default','standard'):continue
            schema=(req.get('response_format') or {}).get('json_schema')
            request_stage=observed_schemas.get(hashlib.sha256(canonical(schema).encode()).hexdigest())
            if request_stage:
                vals=empirical[request_stage];vals['costs'].append(actual/1e9);vals['latencies'].append(raw['latency_s']);vals['input_tokens'].append(raw['response']['usage']['prompt_tokens']);vals['output_tokens'].append(raw['response']['usage']['completion_tokens'])
        db.close();measurements={}
        for request_stage,vals in empirical.items():
            l=sorted(vals['latencies']);measurements[request_stage]={'physical_responses':len(l),'mean_actual_usd':statistics.mean(vals['costs']),
                'mean_latency_s':statistics.mean(l),'p50_latency_s':statistics.median(l),'p95_latency_s':l[int(.95*(len(l)-1))],
                'mean_input_tokens':statistics.mean(vals['input_tokens']),'mean_output_tokens':statistics.mean(vals['output_tokens'])}
    for connection in caches.values():connection.close()
    known_expected=sum(v['uncached_unique_requests']*measurements[s]['mean_actual_usd'] for s,v in summary.items() if s in measurements)
    stage2_measure=measurements.get('hall_stage2_known')
    incomplete_price_stages=[s for s,v in summary.items() if v['uncached_unique_requests'] and s not in measurements]
    conditional_expected_upper=known_expected+unknown_stage2*stage2_measure['mean_actual_usd'] if stage2_measure and not incomplete_price_stages else None
    family_time=Counter();family_p95=Counter();time_incomplete=[]
    stage_family={'hall_stage1':'hallucination','hall_stage2_known':'hallucination','chain':'chain_intermediates','role':'role_bound_association'}
    for cond in per_condition:
        stage_counts={s:v.get('uncached_unique_requests',0) for s,v in cond['stage_counts'].items()}
        stage_counts['hall_stage2_known']=stage_counts.get('hall_stage2_known',0)+cond['new_unknown_hall_stage2_upper']
        for stage,count in stage_counts.items():
            if not count:continue
            if stage not in measurements:time_incomplete.append(stage);continue
            family=stage_family[stage];m=measurements[stage]
            # An idealized capacity calculation, including sequential stages
            # and conditions. It excludes retries and unmeasured overhead.
            family_time[family]+=max(count*m['mean_latency_s']/args.concurrency,count*60/args.rpm)
            family_p95[family]+=max(((count+args.concurrency-1)//args.concurrency)*m['p95_latency_s'],count*60/args.rpm)
    artifact={'status':'read_only_request_forecast','conditions':conditions,'manifest_sha256':sha(args.manifest),
        'selection_sources':[{'path':str(p),'sha256':sha(p)} for p in args.selections],
        'source_contract':contract,'output_cap':cap,'logical_rows':dict(row_counts),'exact_cached_request_counts':{s:dict(v) for s,v in summary.items()},
        'unknown_hall_stage2_unique_requests_lower':0,'unknown_hall_stage2_unique_requests_upper':unknown_stage2,
        'per_condition_incremental_cache_counts':per_condition,
        'empirical_since_utc':args.empirical_since,'empirical_standard_response_measurements':measurements,
        'expected_known_new_charge_usd':known_expected,'expected_charge_including_unknown_stage2_upper_using_empirical_means_usd':conditional_expected_upper,
        'unmeasured_price_stages':incomplete_price_stages,'gross_worst_case_reservation_known_requests_usd':gross_reservation,
        'unknown_stage2_extreme_priced_context_bound_usd':unknown_stage2*cost_units(272000-cap,cap,cache_write_tokens=272000-cap)/1e9,
        'conditional_service_capacity_reference':{'concurrency_per_family':args.concurrency,'rpm_per_family':args.rpm,
            'sequential_condition_and_stage_mean_service_s_by_family':dict(family_time),
            'sequential_p95_wave_reference_s_by_family':dict(family_p95),
            'parallel_family_mean_critical_path_s':max(family_time.values(),default=0),
            'unmeasured_stages':sorted(set(time_incomplete)),
            'interpretation':'Idealized service/rate reference, not a promised walltime or probabilistic upper bound; cache IO, queue barriers, startup, retries and transport incidents add time.'},
        'limits':['No API dispatch; exact pinned upstream builders/validators and cache identity.',
            'New stage1 false spans are unknown: stage2 count and expected cost are bounded, not claimed exact.',
            'Empirical averages are forecasts, not hard guarantees. Physical retries add charges and time.',
            'Walltime includes sequential condition and two-stage barriers; raw per-request latency does not guarantee global throughput.',
            'Gross max-output reservations are formal bounds, not expected prices; the reviewed atomic run ceiling remains authoritative.']}
    if authorization is not None:
        artifact['analysis_authorization']=authorization
    if family_only:
        artifact['forecast_scope']={'kind':'development_family_only','family':family_only,
            'validated_full_manifest_cells':len(cells),'forecast_cells':len(scoped_cells),
            'excluded_other_family_cells':len(cells)-len(scoped_cells),
            'family_cell_counts':dict(Counter(cell['family'] for cell in cells.values())),
            'cache_families_opened':sorted(caches),'active_ledger_access':False}
    if empirical_summary:
        artifact['empirical_reference']={'path':str(empirical_summary),'sha256':sha(empirical_summary),
            'interpretation':'Reuses frozen Standard usage/latency estimates; no active-ledger history scan. These older service estimates are not a current-throughput guarantee.'}
    args.output.write_text(json.dumps(artifact,indent=2)+'\n');print(json.dumps({k:v for k,v in artifact.items() if k!='source_contract'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--selections',type=Path,action='append',required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--fresh-manifest',type=Path);p.add_argument('--gate',type=Path)
    p.add_argument('--conditions',type=Path,action='append',required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--ledger',type=Path,default=Path('${OLENS_DATA_ROOT}/budget/ledger.sqlite3'))
    p.add_argument('--empirical-since',default='2026-10-10T04:50:43+00:00');p.add_argument('--concurrency',type=int,default=8);p.add_argument('--rpm',type=float,default=200)
    p.add_argument('--empirical-summary',type=Path,help='Frozen prior forecast reference; avoids scanning the active financial ledger')
    p.add_argument('--family',choices=('hallucination','chain_intermediates','role_bound_association'),
                   help='DEV only: validate the full cohort, then forecast only this released family/cache; requires --empirical-summary')
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.concurrency<=0 or args.rpm<=0:p.error('concurrency and rpm must be positive')
    run(args)
