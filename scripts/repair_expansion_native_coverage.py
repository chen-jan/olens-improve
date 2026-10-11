"""Bounded same-instrument recovery of three diagnosed missing judgments.

No scientific source changes. Full-family rebuilding reuses exact validated
verdicts; a transport allowlist permits only the three missing request identities.
Original artifacts remain in an immutable backup. A failed repair is not attested.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import expanded_judges as runner
from expanded_api import digest, paid_gate, load_key, budget
from forecast_judging import source_validator
from olens_improve import evaluation
from olens_improve.budget import cost_units, request_input_upper_bound
from olens_improve.data import canonical
from olens_improve.reporting import family_counts

D = Path('${OLENS_DATA_ROOT}/expansion-v1')
CACHE = Path('${OLENS_DATA_ROOT}/runs/development-shared-pilot-v2/judgments/shared-exact-cache')
TARGETS = (
    ('best_n_exact-n4', 'hallucination', 'chat-dailydialog-0037', 52, 20, 'cached-v2'),
    ('prune_loo_n1_0.005-n1', 'role_bound_association', 'oa-officer-informant-protect-ba', 36, 151, 'cached-v2'),
    ('consensus_semantic_v5_medium_support0_compaton_vetoon-n16', 'role_bound_association', 'oa-father-daughter-worry-ba', 60, 128, 'semantic-medium-v1'),
)

def read(p): return json.loads(Path(p).read_text())
def require(ok, message):
    if not ok: raise ValueError(message)
def write_new(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f: f.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
def rows(p):
    with Path(p).open() as f: return [json.loads(line) for line in f if line.strip()]
def key(r): return (str(r['id']), r['layer'], r['pos'])

def prepare(plan_path):
    evaluation.load_upstream()
    from wsbench import llm
    from wsbench.mcjudge import load_bank
    runtime = evaluation.load_upstream()['runtime_source_hashes']
    inventory = read(ROOT/'configs/expansion_manifest_v1.json')
    pins = {str(ROOT/'configs/expansion_manifest_v1.json'): digest(ROOT/'configs/expansion_manifest_v1.json'),
            str(Path(__file__).resolve()): digest(__file__),
            str(ROOT/'scripts/expanded_judges.py'): digest(ROOT/'scripts/expanded_judges.py'),
            str(ROOT/'scripts/expanded_api.py'): digest(ROOT/'scripts/expanded_api.py'),
            str(ROOT/'src/olens_improve/evaluation.py'): digest(ROOT/'src/olens_improve/evaluation.py'),
            str(ROOT/'docs/reviews/expanded-final-native-failure-diagnosis-v1.json'): digest(ROOT/'docs/reviews/expanded-final-native-failure-diagnosis-v1.json')}
    entries=[]
    for condition, family, item, layer, pos, group in TARGETS:
        base=D/'judgments'/condition
        result_path=base/family/'results.json'; readout_path=base/(family+'.readouts.jsonl')
        for p in [result_path, readout_path, base/(family+'.summary.json'),base/family/'project_contract.json',base/family/'cells.jsonl'] + [x for x in (base/(family+'.condition.json'),base/'condition.json') if x.exists()]:
            pins[str(p)]=digest(p)
        result=read(result_path); matches=[r for r in rows(readout_path) if key(r)==(item,layer,pos)]
        require(len(matches)==1 and matches[0]['samples'][0].strip(), 'Missing/nonunique/empty targeted readout')
        text=matches[0]['samples'][0]; module=importlib.import_module('wsbench.evals.'+family+'.judge')
        bank=load_bank(family)
        validator=None; validator_source=None
        if family=='hallucination':
            it=next(r for r in bank['items'] if r['id']==item); site=next(s for s in it['sites'] if s['pos']==pos)
            old=next(r for r in result['rows'] if key(r)==(item,layer,pos))
            require(old['samples']==[text] and old['verdict'][0]['claims'] is None and old['verdict'][0]['class']!='unjudged', 'Target is not diagnosed stage2 gap')
            wrong=[old['verdict'][0]['wrong']]
            system,user=module.verify_prompt(it,site,[text],wrong); schema=module.VERIFY_SCHEMA; version=module.VERIFY_PROMPT_VERSION
            validator,validator_source=source_validator(module,'tally_claims');meta={'samples':[text],'wrong':wrong}
        else:
            require(not any(key(r)==(item,layer,pos) for r in result['rows']), 'Target role judgment is already present')
            it=next(r for r in bank if r['id']==item); block,_=module.build_block(it,bank)
            system,user=module.SYSTEM,module.prompts.render_user(text,block);schema=module.SCHEMA;version=module.PROMPT_VERSION;meta={}
        request={'model':'gpt-6-luna','reasoning_effort':'none','messages':[{'role':'system','content':system},{'role':'user','content':user}],
                 'response_format':{'type':'json_schema','json_schema':schema},'max_completion_tokens':llm._DEFAULT_MAX_TOKENS['openai']}
        request_key=evaluation.request_cache_key(request)
        content_key=hashlib.sha256(canonical({'request':request_key,'prompt_version':version,'runtime_source_hashes':runtime,'validator_source':validator_source}).encode()).hexdigest()
        with sqlite3.connect('file:'+str(CACHE/(family+'.sqlite3'))+'?mode=ro',uri=True) as q:
            found=q.execute('SELECT body FROM verdicts WHERE content_key=?',(content_key,)).fetchone()
        cached=readable=json.loads(found[0]) if found else None
        valid=bool(cached and (validator is None or validator(SimpleNamespace(meta=meta),cached['result'])))
        descriptor_path=D/'selections'/group/(family+'.ready.json');descriptor=read(descriptor_path)
        for p in [descriptor_path,Path(descriptor['manifest']),Path(descriptor['selections'])]:pins[str(p)]=digest(p)
        choices=descriptor['conditions'];choices=read(choices) if isinstance(choices,str) else choices
        condition_body=next(c for c in choices if f"{c['method']}-n{c['n']}"==condition)
        bound=request_input_upper_bound({**request,'service_tier':'default'})
        entries.append({'condition_id':condition,'family':family,'site':{'id':item,'layer':layer,'pos':pos},'descriptor':str(descriptor_path),'condition':condition_body,
                        'request':request,'request_key':request_key,'content_key':content_key,'prompt_version':version,'shared_cache_before':readable,
                        'validated_cache_hit_before':valid,'max_physical_attempts':0 if valid else 2,'worst_two_attempt_reservation_usd':0 if valid else 2*cost_units(bound,request['max_completion_tokens'],cache_write_tokens=bound)/1e9})
    require(len({e['request_key'] for e in entries})==3,'Expected three distinct missing request identities')
    plan={'status':'prepared_exact_three_missing_judgment_repair','utc':datetime.now(timezone.utc).isoformat(),'inventory_sha256':pins[str(ROOT/'configs/expansion_manifest_v1.json')],
          'runtime_source_hashes':runtime,'source_sha256':pins,'entries':entries,'physical_attempt_ceiling':sum(e['max_physical_attempts'] for e in entries),'worst_reservation_usd':sum(e['worst_two_attempt_reservation_usd'] for e in entries),
          'model':'gpt-6-luna','reasoning_effort':'none','service_tier':'default','new_settings':0,'financial_hold_cancellations':0,
          'authorization':'Root explicitly authorized only these three diagnosed same-prompt coverage repairs; unchanged instrument already healthy and terminal.'}
    write_new(plan_path,plan); print(json.dumps({'plan':str(plan_path),'sha256':digest(plan_path),'physical_attempt_ceiling':plan['physical_attempt_ceiling'],'worst_reservation_usd':plan['worst_reservation_usd'],'validated_exact_cache_hits':sum(e['validated_cache_hit_before'] for e in entries)}))

def execute(plan_path, output):
    require(os.environ.get('SLURM_JOB_ID')=='25536291','Repair must use existing API CPU25536291')
    require(not output.exists(),'Preserve all earlier repair attempts; use a new output bundle')
    plan=read(plan_path)
    for p,h in plan['source_sha256'].items():require(digest(p)==h,'Prepared source changed: '+p)
    require(evaluation.load_upstream()['runtime_source_hashes']==plan['runtime_source_hashes'],'Runtime21 changed')
    args=SimpleNamespace(inventory=ROOT/'configs/expansion_manifest_v1.json',inventory_sha256=plan['inventory_sha256'],
        forecast=D/'receipts/api-dispatch-forecast-v1.json',budget_receipt=D/'receipts/budget-activation-v1.json',allow_paid=True,
        ledger=Path('${OLENS_COMPUTE_ROOT}/budget/ledger-v2.sqlite3'),run_id='expanded-all-four-banks-v1',run_cap_usd='298',
        shared_cache=CACHE,output=D/'judgments',concurrency=256,rpm=4000,family=None)
    inventory=paid_gate(args);load_key()
    os.environ.update(OLENS_TEST_FROZEN='1',OLENS_LEDGER_REUSE_WRITER_CONNECTION='1',OLENS_LEDGER_RESERVATION_BATCH_SIZE='16')
    evaluation.AtomicBudget=runner.ExpansionBudget
    from wsbench import mcjudge
    from wsbench.judge_config import resolve
    from wsbench.registry import get
    for family in ('hallucination','role_bound_association'):
        judge=resolve(get(family).judge,flag=evaluation.JUDGE_MODEL,env={'WSBENCH_OPENAI_REASONING':'none'})
        mcjudge._PREFLIGHTED.add(mcjudge.preflight_key(judge.model,judge.reasoning))
    leases=[]
    for family in ('hallucination','role_bound_association'):
        q=read(args.output/(family+'.queue-state.json'));require(len(q['completed'])==70 and not q['running'],'Family worker is not terminal')
        lease=(CACHE/(family+'.owner.lock')).open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);leases.append(lease)
    output.mkdir(parents=True)
    for p in plan['source_sha256']:
        path=Path(p)
        if D/'judgments' in path.parents:
            dest=output/'before'/path.relative_to(D/'judgments');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    ledger=budget(args.ledger);before=ledger.snapshot();counts=Counter();dispatched=[]
    original_factory=evaluation.make_luna_client
    allowed={e['request_key']:e['max_physical_attempts'] for e in plan['entries']}
    def guarded_factory(*a,**kw):
        client=original_factory(*a,**kw);original=client.chat.completions.create
        async def guarded_create(**request):
            identity=evaluation.request_cache_key(request)
            require(identity in allowed,'Refuse dispatch outside the three exact missing requests')
            counts[identity]+=1;require(counts[identity]<=allowed[identity],'Exact missing request attempt cap exceeded')
            dispatched.append({'request_key':identity,'ordinal':counts[identity],'utc':datetime.now(timezone.utc).isoformat()})
            return await original(**request)
        client.chat.completions.create=guarded_create;return client
    evaluation.make_luna_client=guarded_factory
    write_new(output/'started.json',{'plan_sha256':digest(plan_path),'utc':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'job':os.environ['SLURM_JOB_ID'],'step':os.environ.get('SLURM_STEP_ID'),'budget_before':before})
    audits=[]
    for e in plan['entries']:
        args.family=e['family'];runner.evaluate_expansion(read(e['descriptor']),e['condition'],args,inventory)
        base=args.output/e['condition_id'];old=read(output/'before'/e['condition_id']/e['family']/'results.json');new=read(base/e['family']/'results.json')
        before_rows={key(r):r for r in old['rows']};after_rows={key(r):r for r in new['rows']};target=tuple(e['site'][k] for k in ('id','layer','pos'))
        require(target in after_rows,'Repaired target still absent')
        require(set(after_rows)==set(before_rows)|{target},'Unexpected result-row additions/removals')
        require(all(after_rows[k]==v for k,v in before_rows.items() if k!=target),'An unaffected result record changed')
        if e['family']=='hallucination':
            prior=json.loads(json.dumps(before_rows[target]));following=json.loads(json.dumps(after_rows[target]));prior['verdict'][0]['claims']=None;following['verdict'][0]['claims']=None
            require(prior==following,'Hall stage1 record changed during stage2 repair')
        cells=read(inventory['fresh_manifest']['path'])['cells'];_,coverage=family_counts(e['family'],[c for c in cells if c['family']==e['family']],rows(base/(e['family']+'.readouts.jsonl')),new)
        require(coverage['missing_stage1']==coverage['missing_stage2']==0,'Rebuilt unit still has incomplete coverage')
        for suffix in ('.readouts.jsonl','.condition.json'):
            p=base/(e['family']+suffix)
            if str(p) in plan['source_sha256']:require(digest(p)==plan['source_sha256'][str(p)],'Scientific selection or source condition changed')
            else:require(suffix=='.condition.json' and read(p)['inventory_sha256']==plan['inventory_sha256'],'New family-scoped source receipt is unbound')
        audits.append({'condition':e['condition_id'],'family':e['family'],'target':e['site'],'unaffected_result_records_exact':len(before_rows)-(target in before_rows),
                       'only_target_result_changed':True,'coverage_after':coverage,'target_before':before_rows.get(target),'target_after':after_rows[target],
                       'after_sha256':{str(p):digest(p) for p in [base/e['family']/'results.json',base/e['family']/'project_contract.json',base/(e['family']+'.summary.json'),base/e['family']/'cells.jsonl']}})
    after=ledger.snapshot()
    require(after['unknown_usd']>=before['unknown_usd'],'Existing unknown holds decreased')
    receipt={'status':'exact_three_missing_judgments_repaired_pending_root_review','utc':datetime.now(timezone.utc).isoformat(),'plan_sha256':digest(plan_path),
             'implementation_sha256':digest(__file__),'runtime_source_hashes':plan['runtime_source_hashes'],'physical_dispatches':dispatched,'audits':audits,
             'budget_before':before,'budget_after':after,'unknown_holds_preserved':True,'preexisting_valid_result_records_preserved':True,'new_settings':0,
             'limits':['Only diagnosed missing outcomes were requested with identical original prompts/schema/MC blocks and existing hall false spans.','Original results/contracts/summaries/local journals are retained before rebuilding; historical analysis snapshots remain unchanged.','Upstream complete flags remain preserved; strict native coverage requires rerun by the existing analysis authority.']}
    write_new(output/'receipt.json',receipt);print(json.dumps({'receipt':str(output/'receipt.json'),'sha256':digest(output/'receipt.json'),'physical_dispatches':len(dispatched),'settled_cost_delta_usd':after['actual_usd']-before['actual_usd']}))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--plan',type=Path,required=True);a.add_argument('--execute',action='store_true');a.add_argument('--output',type=Path);args=a.parse_args()
    if args.execute:
        require(args.output is not None,'Execute needs immutable output bundle');execute(args.plan,args.output)
    else:prepare(args.plan)
