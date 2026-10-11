"""Retrospective source-bound effort export. No inference, pricing or ledger writes.

Live ledger reads use short bounded statements, never a long reader transaction.
Append-only logs are bound by exact byte-prefix hashes; refresh into a new file.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import sqlite3
import time

from build_expansion_dashboard import ACTIVE,FAMILIES,category,label

LANES=('semantic-semantic','semantic-medium','editing-round1','editing-round2')
PHASES={'semantic-semantic':'semantic_ordinary','semantic-medium':'semantic_medium',
        'editing-round1':'editing_round1','editing-round2':'editing_round2'}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)


class Sources:
    def __init__(self):self.rows={}

    def read(self,path):
        path=Path(path);raw=path.read_bytes()
        self.rows[str(path)]={'sha256':sha256(raw).hexdigest(),'bytes':len(raw),'policy':'complete_file_at_read'}
        return json.loads(raw)

    def text_prefix(self,path):
        path=Path(path);size=path.stat().st_size
        with path.open('rb') as f:raw=f.read(size)
        self.rows[str(path)]={'sha256':sha256(raw).hexdigest(),'bytes':len(raw),'policy':'fixed_byte_prefix_at_read'}
        return raw.decode(errors='replace')

    def lines(self,path):
        """Bind the existing prefix once; never chase a log appended by workers."""
        path=Path(path);size=path.stat().st_size;h=sha256();seen=0;parsed=0;incomplete=False
        with path.open('rb') as stream:
            while seen<size:
                raw=stream.readline(size-seen)
                if not raw:raise ValueError('Source truncated during prefix audit')
                seen+=len(raw);h.update(raw)
                if not raw.endswith(b'\n'):incomplete=True;continue
                parsed+=1;yield json.loads(raw)
        self.rows[str(path)]={'sha256':h.hexdigest(),'bytes':seen,'records':parsed,
                            'incomplete_last_record':incomplete,'policy':'exact_immutable_byte_prefix'}


def empty_usage():
    return {'physical_settled_attempts':0,'actual_usage_estimate_usd':0.,'input_tokens':0,
            'output_tokens':0,'cached_input_tokens':0,'cache_write_tokens':0,'physical_usage_records':0}


def add_usage(target,actual,usage):
    target['physical_settled_attempts']+=1;target['actual_usage_estimate_usd']+=actual/1e9
    if usage is not None:
        target['physical_usage_records']+=1
        for out,key in [('input_tokens','input_tokens'),('output_tokens','output_tokens'),
                        ('cached_input_tokens','cached_tokens'),('cache_write_tokens','cache_write_tokens')]:
            if not isinstance(usage.get(key),int):raise ValueError('Incomplete retained settlement usage')
            target[out]+=usage[key]


def helper_records(root,sources):
    families={};response_map={}
    for lane in LANES:
        phase=PHASES[lane]
        for family in FAMILIES:
            p=root/'helpers'/lane/family;key=phase+'/'+family
            d={'phase':phase,'family':family,'status':'pending','completed_cells':0,
               'logical_calls':0,'unique_logical_requests':0,'validated_cache_hits':0,
               'coalesced_inflight_logical_calls':0,'logical_versions':{},
               'response_validation':None,'physical_response_completions_instrumented':0,
               'throughput':None,'proposal_statistics':None,**empty_usage()}
            if not p.exists():families[key]=d;continue
            d['status']='running';forecast=p/'exact-request-forecast.jsonl'
            if forecast.exists():
                requests=set();versions=Counter()
                for r in sources.lines(forecast):
                    d['logical_calls']+=1;requests.add(r['request_key']);versions[r['version']]+=1
                    d['validated_cache_hits']+=bool(r['validated_cache_hit'])
                    d['coalesced_inflight_logical_calls']+=bool(r['coalesced_inflight'])
                d['unique_logical_requests']=len(requests);d['logical_versions']=dict(versions)
            progress=p/'progress.sqlite3'
            if progress.exists():
                with sqlite3.connect('file:'+str(progress)+'?mode=ro',uri=True,timeout=10) as q:
                    cells=[r[0] for r in q.execute('SELECT cell_id FROM cells ORDER BY cell_id')]
                d['completed_cells']=len(cells)
                d['checkpoint_cell_ids_sha256']=sha256(canonical(cells).encode()).hexdigest()
                d['checkpoint_source']={'path':str(progress),'query':'SELECT cell_id FROM cells ORDER BY cell_id',
                                        'policy':'logical_records_at_read; database_mutable'}
            events=p/'helper_events.json'
            if events.exists():
                records=sources.read(events);validity=Counter();versions=defaultdict(Counter)
                for r in records:
                    if r.get('cached'):validity['validated_cached_event_returns']+=1;continue
                    kind='valid_physical_responses' if r.get('valid') else 'invalid_physical_responses' if r.get('response_id') else 'no_response_failures'
                    validity[kind]+=1;versions[r['version']][kind]+=1
                    if r.get('response_id'):
                        if r['response_id'] in response_map and response_map[r['response_id']][0]!=key:raise ValueError('A physical response was attributed to two helper families')
                        response_map[r['response_id']]=(key,r['version'],r.get('valid'))
                d['response_validation']=dict(validity);d['response_validation_by_version']={v:dict(c) for v,c in versions.items()}
                d['status']='complete';d['physical_response_completions_instrumented']=sum(validity[k] for k in ('valid_physical_responses','invalid_physical_responses'))
            usage_path=p/'physical-usage.jsonl'
            if usage_path.exists():
                ids=set()
                for r in sources.lines(usage_path):
                    ident=r['response_id']
                    if ident in ids:raise ValueError('Duplicate instrumented physical response')
                    ids.add(ident)
                    if ident not in response_map:response_map[ident]=(key,'medium_confirmation' if lane=='semantic-medium' else 'instrumented_phase',None)
                d['physical_response_completions_instrumented']=max(d['physical_response_completions_instrumented'],len(ids))
            timing=p/'throughput.json'
            if timing.exists():
                t=sources.read(timing);latencies=[r['latency_s'] for r in t.get('latencies',[]) if isinstance(r.get('latency_s'),(float,int))]
                d['throughput']={k:t[k] for k in ('failed_logical_calls','final_concurrency','fresh_valid_completions','wall_seconds')}
                d['throughput']['physical_response_completions_per_wall_second']=d['physical_response_completions_instrumented']/t['wall_seconds'] if t['wall_seconds'] else None
                if latencies:
                    latencies.sort();d['throughput'].update(p50_response_wall_seconds=latencies[len(latencies)//2],p95_response_wall_seconds=latencies[min(len(latencies)-1,int(len(latencies)*.95))])
            proposals=p/'editing_proposals.jsonl'
            if proposals.exists():
                stats=Counter();counts=Counter()
                for r in sources.lines(proposals):
                    e=r['editing'];items=e['proposals'];stats['cells']+=1;stats['helper_valid_cells']+=bool(e.get('helper_valid'))
                    stats['validated_proposals']+=len(items);counts[len(items)]+=1
                    for proposal in items:
                        if not proposal.get('parent_candidate_id') or not proposal.get('candidate_id'):raise ValueError('Proposal loses parent lineage')
                        stats['introduced_word_occurrences']+=len(proposal.get('introduced_words',[]));stats['deleted_word_occurrences']+=len(proposal.get('deleted_words',[]))
                    if len(items)>4:raise ValueError('Unfrozen proposal budget')
                d['proposal_statistics']={**dict(stats),'proposal_count_distribution':dict(counts),
                    'word_difference_scope':'Text differences only; not factual novelty or correctness.',
                    'proposals_per_cell_upper':4,'round':int(lane[-1])}
            families[key]=d
    return families,response_map


def ledger_audit(path,run_id,response_map,families,batch=512):
    """Only settled records at/before cutoff enter phase usage sums.

    Statement readers finish between batches; writers can commit throughout.
    The stable audit digest binds projected records, not the mutable DB bytes.
    """
    q=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=10)
    q.execute('PRAGMA query_only=ON')
    cutoff=datetime.now(timezone.utc).isoformat();buckets=defaultdict(empty_usage);subphases=defaultdict(empty_usage)
    def commitment(where='',args=()):
        sql='SELECT status,count(*),sum(reserved),sum(coalesce(actual,0)) FROM attempts '+where+' GROUP BY status'
        return [{'status':s,'count':n,'reserved_usd':r/1e9,'actual_usd':a/1e9} for s,n,r,a in q.execute(sql,args).fetchall()]
    # Covering indexes avoid a whole-table reader on the live service.
    global_rows=commitment('INDEXED BY attempts_global_committed')
    run_rows=commitment('INDEXED BY attempts_run_committed WHERE run_id=?',(run_id,))
    settings={k:v/1e9 for k,v in q.execute("SELECT key,value FROM config WHERE key IN ('hard','target')").fetchall()}
    cursor=('', '');h=sha256();count=0;unknown=[];started=time.monotonic();max_batch=0
    while True:
        before=time.monotonic()
        rows=q.execute('''SELECT a.attempt_id,a.status,a.reserved,a.actual,a.created_utc,a.updated_utc,
          json_extract(a.metadata,'$.purpose'),json_extract(a.metadata,'$.request.reasoning_effort'),
          e.details FROM attempts AS a INDEXED BY attempts_run_recovery
          LEFT JOIN events AS e ON e.sequence=(SELECT sequence FROM events INDEXED BY events_attempt_kind_sequence
          WHERE attempt_id=a.attempt_id AND kind='settled' ORDER BY sequence DESC LIMIT 1)
          WHERE a.run_id=? AND a.created_utc<=? AND a.created_utc>=? AND (a.created_utc>? OR (a.created_utc=? AND a.attempt_id>?))
          ORDER BY a.created_utc,a.attempt_id LIMIT ?''',(run_id,cutoff,cursor[0],cursor[0],cursor[0],cursor[1],batch)).fetchall()
        max_batch=max(max_batch,time.monotonic()-before)
        if not rows:break
        cursor=rows[-1][4],rows[-1][0]
        for aid,status,reserved,actual,created,updated,purpose,effort,details in rows:
            if status!='settled' or updated>cutoff:continue
            usage=json.loads(details) if details else None;response=usage.get('response_id') if usage else None
            origin=response_map.get(response)
            if purpose=='workspacebench-judge':bucket='experimental_benchmark_judging'
            elif origin:bucket=families[origin[0]]['phase']
            elif purpose=='candidate-only-helper-effort-diagnostic':bucket='unattributed_helper_'+str(effort)
            else:bucket='unattributed_other'
            add_usage(buckets[bucket],actual,usage)
            if origin:
                add_usage(families[origin[0]],actual,usage);add_usage(subphases[bucket+'/'+origin[1]],actual,usage)
            record={'attempt_id':aid,'status':status,'reserved_units':reserved,'actual_units':actual,
                    'created_utc':created,'updated_utc':updated,'purpose':purpose,'effort':effort,'settlement_usage':usage}
            h.update((canonical(record)+'\n').encode());count+=1
        if count and count%8192<batch:print(canonical({'effort_audited_settlements':count}),flush=True)
    rows=q.execute("SELECT attempt_id,reserved,created_utc FROM attempts INDEXED BY attempts_run_committed WHERE run_id=? AND status='unknown'",(run_id,)).fetchall()
    for aid,reserved,created in rows:
        e=q.execute("SELECT kind,details FROM events INDEXED BY events_attempt_kind_sequence WHERE attempt_id=? AND kind='transport_failure' ORDER BY sequence DESC LIMIT 1",(aid,)).fetchone()
        d=json.loads(e[1]) if e else {}
        unknown.append({'attempt_id':aid,'reserved_usd':reserved/1e9,'created_utc':created,
                        'exception_type':d.get('exception_type'),'http_status':d.get('http_status'),
                        'cause_classes':[r.get('class') for r in d.get('cause_chain',[])],
                        'disposition':'Retained unknown; no proof of an uncharged attempt.'})
    q.close()
    return {'path':str(path),'run_id':run_id,'settlement_cutoff_utc':cutoff,'settled_record_count':count,
            'projected_settlement_records_sha256':h.hexdigest(),'scope':'Immutable settled records at/before cutoff; live pending totals sampled separately.',
            'batch_size':batch,'maximum_statement_wall_seconds':max_batch,'audit_wall_seconds':time.monotonic()-started,
            'global_commitment':global_rows,'run_commitment':run_rows,'limits':settings,
            'buckets':dict(buckets),'helper_subphases':dict(subphases),'unknown_holds':unknown,
            'benchmark_logical_calls':None,'benchmark_validated_cache_hits':None,
            'benchmark_response_validation':None,
            'benchmark_instrumentation_note':'Ledger records physical attempts and usage. Provider-response validity and exact logical/cache-hit counts are not inferred from scientific pass/fail or missing cache markers.'}


def effort_definition(row,controls):
    method=row['method'];cid=row['condition_id'];n=row['n'];group=category(method)
    semantics='semantic_' in method;medium=row.get('helper_reasoning_effort')=='medium';editing=method.startswith('editing')
    helper=[]
    if semantics:helper=['semantic_ordinary']+(['semantic_medium'] if medium else [])
    rounds=2 if editing and 'round2' in method else 1 if editing else 0
    if editing:helper=[f'editing_round{i}' for i in range(1,rounds+1)]
    specificity=('specificity' in method);likelihood='likelihood' in method
    ar=not (likelihood or method in ('raw_n1','capped_n1','random_complete') or method.startswith(('consensus','exact_support')))
    inference=['Capture one activation per new input item',f'Generate {n} original descriptions per activation vector']
    if ar:inference.append('Encode admissible original bullets with the released reconstructor')
    if ar:inference.append('Fit exact nonnegative least-squares reconstruction for admissible candidate phrase sets')
    if helper:inference.append('Reuse shared '+', '.join(helper)+' helper phases')
    if rounds:inference.append(f'Reencode novel edited bullets and exact-NNLS score candidates after each of {rounds} rounds')
    if likelihood:inference.append('Score identical candidate tokens under '+('one true activation' if method=='own_mean_log_likelihood' else 'two control activations' if method=='control_mean_log_likelihood' else 'one true and two control activations'))
    if specificity:inference.append(f'Compare exact fits against {controls[0]}–{controls[1]} frozen control activations')
    if 'prune' in method:inference.append('Apply the recorded sequential pruning or coefficient threshold')
    if 'random_delete' in method:inference.append('Match the original parent pruning count with seeded deletion')
    helper_recipe=(['source_pair_proposal','medium_confirmation_on_frozen_pairs'] if medium else ['source_pair_proposal','ordinary_confirmation']) if semantics else [f'bounded_editor_round{i}' for i in range(1,rounds+1)]
    return {'condition':cid,'group':group,'label':label(row),'original_pool_n':n,'new_expansion_olens_samples':row['new_olens_samples'],
        'activation_capture_forwards_per_new_input_item':1,'original_bullet_ar_encoding_required':ar,
        'shared_helper_component_refs':helper,'new_input_helper_recipe':helper_recipe,'editor_rounds':rounds,
        'medium_recipe_note':'Campaign medium labels reuse exact ordinary proposals/pair IDs/exclusions. Prior measured deployment helper component includes proposal plus medium confirmation, not two complete ordinary/medium pipelines.' if medium else None,
        'likelihood_contexts_per_candidate_if_run_alone':(1 if method=='own_mean_log_likelihood' else 2 if method=='control_mean_log_likelihood' else 3) if likelihood else 0,
        'campaign_shared_likelihood_contexts_per_candidate':3 if likelihood else 0,
        'frozen_nnls_control_targets_range':list(controls) if specificity else [0,0],
        'nnls_evaluation_count':None,'nnls_count_note':'Depends on admissible candidates, phrase-set caching and recorded greedy/pruning operations; no fixed count is invented.',
        'parent_condition_ids':row['parent_condition_ids'],'recurring_components':inference,
        'summary':'; '.join(inference[1:]),'allocated_unique_method_api_usd':None,
        'allocation_note':'Shared phase totals are reported once; variant dependencies are not independent charges.',
        'benchmark_judging_is_deployment_inference':False}


def observed_judge_counters(sources,logs):
    """Retained completed-pass summaries; do not infer unlogged in-flight work."""
    rows=[]
    for path in sorted(Path(logs).glob('expansion-judge-*-v1.log')):
        matches=re.findall(r'judge: (\d+) calls \((\d+) cached, model=gpt-6-luna\)',sources.text_prefix(path))
        rows.append({'source':str(path),'completed_pass_summaries':len(matches),
                     'observed_uncached_logical_calls':sum(int(a) for a,b in matches),
                     'observed_validated_cache_returns':sum(int(b) for a,b in matches)})
    return {'sources':rows,'observed_logical_invocations':sum(r['observed_uncached_logical_calls']+r['observed_validated_cache_returns'] for r in rows),
            'observed_validated_cache_returns':sum(r['observed_validated_cache_returns'] for r in rows),
            'scope':'Recorded completed-pass invocation counters, including resumed passes. Not unique scientific requests or physical retry attempts. In-flight or interrupted passes without a summary are absent; this is a partial lower bound during execution.'}


def export(inventory_path,root,ledger_path,durable,output,run_id='expanded-all-four-banks-v1'):
    output=Path(output)
    if output.exists():raise ValueError('Use a new immutable resource version')
    sources=Sources();inventory=sources.read(inventory_path);isha=sources.rows[str(inventory_path)]['sha256']
    if inventory['status']!='sealed':raise ValueError('Require sealed method inventory')
    active={r['condition_id']:r for r in inventory['conditions'] if r['status'] in ACTIVE}
    if len(active)!=70:raise ValueError('Expected frozen 70 settings')
    helpers,responses=helper_records(root,sources)
    ledger=ledger_audit(ledger_path,run_id,responses,helpers)
    judge_counters=observed_judge_counters(sources,Path('${OLENS_COMPUTE_ROOT}/logs'))
    controls=sources.read(inventory['control_bank']['path'])
    if sources.rows[inventory['control_bank']['path']]['sha256']!=inventory['control_bank']['sha256']:raise ValueError('Control bank source changed')
    counts=[len(v) for v in controls['control_cell_ids_by_target'].values()];control_range=min(counts),max(counts)
    costs=sources.read(durable/'diagnostics/costs-v3/components.json')
    if costs.get('pricing_revision')!='luna-cache-write-v1':raise ValueError('Require reviewed cache-write cost correction')
    fresh=sources.read(durable/'engineering/portable-fresh-input-n32-v1/result.json')
    scope=sources.read(durable/'engineering/portable-fresh-input-n32-v1/scope.json')
    if fresh.get('scientific_results_eligible') is not False or scope['API_calls']!=0:raise ValueError('Fresh engineering fixture must remain separate from quality')
    timings=[]
    for path in [Path('.state/expanded-cpu-v1.service.json'),Path('.state/expanded-gpu-v1.service.json'),
                 root/'selections/cached-v2/status.json',root/'likelihood-n8-two-controls/status.json']:
        if path.exists():
            value=sources.read(path);timings.append({'path':str(path),'value':value,'scope':'Operational task wall time, not per-method latency or summed CPU time.'})
    judge_counts={};registered={}
    state_path=Path('.state/expansion-api-v1.json')
    if state_path.exists():
        state=sources.read(state_path);registered=state.get('published_descriptors',{})
        judge_counts={f:d.get('completed',0) for f,d in state.get('judgments',{}).items()}
    for path in [Path('.state/expansion-helpers-editing-v1.json'),Path('.state/expansion-helpers-semantic-v1.json')]:
        if path.exists():sources.read(path)
    family_complete=all(d['status']=='complete' for d in helpers.values())
    result={'schema_version':1,'status':'complete_retrospective' if family_complete and sum(judge_counts.values())==280 else 'partial_retrospective',
        'generated_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':isha,
        'scope':'Exploratory all469 previously inspected questions; adaptive campaign execution is not a prospective latency benchmark.',
        'pricing_revision':'luna-cache-write-v1','invoice_reconciled':False,'gpu_dollars':None,
        'ledger_audit':ledger,'helper_phases_by_family':helpers,
        'benchmark_observed_log_counters':judge_counters,
        'method_effort':{c:effort_definition(r,control_range) for c,r in active.items()},
        'new_input_measurements':{'source':'Existing separate one-vector N32 engineering fixture; no new experiment.',
            'scope':scope,'measurements':fresh['measurements'],'cold_pipeline_through_first_selection_seconds':fresh['cold_pipeline_through_first_selection_seconds'],
            'new_generations':fresh['new_generations'],'raw_vectors':fresh['raw_vectors'],
            'limits':['Single synthetic input, layer44; not a task-bank average or batch-serving latency.',
                      'Cached prefix replays include measured loading/CPU overhead and exclude fresh generation/AR.',
                      'Cumulative process memory peaks do not measure stage-exclusive demand or project quota.']},
        'prior_measured_components':{'source_scope':costs['scope'],'deployment':costs['deployment'],
            'incremental_cache':costs['incremental_cache'],'limitations':costs['limitations'],
            'source_sha256':costs['source_sha256'],'inherited_source_chain_reaudited':False},
        'operational_timings':timings,'judge_completion':judge_counts,
        'registered_combination_families':[f for f in FAMILIES if any('/combinations-v2/' in p and p.endswith('/'+f+'.ready.json') for p in registered)],
        'registered_likelihood_families':[f for f in FAMILIES if any('/likelihood-v1/' in p and p.endswith('/'+f+'.ready.json') for p in registered)],
        'source_index':sources.rows,'implementation_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits':['API amounts are usage-derived estimates, not reconciled invoices. Unknown and reserved holds remain committed.',
                  'Ordinary and medium semantic variants share proposals/pairs; medium campaign reuses ordinary proposal bytes. Variant costs are never summed as separate calls.',
                  'All editing variants share bounded proposal/encoding phases; no benchmark feedback enters candidate acceptance.',
                  'Inference components, benchmark judgment and historical engineering fixtures have separate scope.',
                  'Live logs/checkpoints are partial; final refresh requires terminal services and writes a new artifact.',
                  'GPU task time includes host/loading overhead; GPU dollars, new-input latency for every method, and process CPU seconds are not inferred.']}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--root',type=Path,default=Path('${OLENS_DATA_ROOT}/expansion-v1'))
    p.add_argument('--durable',type=Path,default=Path('${OLENS_DATA_ROOT}'))
    p.add_argument('--ledger',type=Path,default=Path('${OLENS_COMPUTE_ROOT}/budget/ledger-v2.sqlite3'))
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Run this retrospective log/ledger audit on an allocated CPU')
    r=export(a.inventory,a.root,a.ledger,a.durable,a.output)
    print(canonical({'output':str(a.output),'status':r['status'],'methods':len(r['method_effort']),
        'judged_condition_families':sum(r['judge_completion'].values()),'buckets':r['ledger_audit']['buckets']}))


if __name__=='__main__':main()
