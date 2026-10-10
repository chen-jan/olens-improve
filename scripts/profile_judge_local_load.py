"""Copied-ledger, fake-transport load check. No SDK client or network is constructed.

The pinned judge loop, exact verdict cache and financial methods are exercised.
Only fake shape-matched prompts/responses are dispatched, never benchmark judging.
"""
import argparse
import asyncio
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace


FAMILIES = ('hallucination','chain_intermediates','role_bound_association')
SCHEMAS = dict(zip(FAMILIES,('hallucination_ontopic_spans','chain_free','readout_mc')))


def scrub(value):
    if isinstance(value,str): return 'x'*len(value.encode('utf-8','replace'))
    if isinstance(value,list): return [scrub(v) for v in value]
    if isinstance(value,dict): return {k:scrub(v) for k,v in value.items()}
    return value


def readonly_accounting(database):
    """Numeric invariance evidence without AtomicBudget's write transaction."""
    with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as db:
        rows = db.execute('SELECT status,COUNT(*),SUM(reserved),SUM(actual) FROM attempts GROUP BY status').fetchall()
        return {'status_totals_nanodollars': [list(row) for row in rows],
                'event_count': db.execute('SELECT COUNT(*) FROM events').fetchone()[0],
                'financial_config': dict(db.execute('SELECT key,value FROM config'))}


def validate_worker_copy(args):
    root = args.output.resolve().parent
    marker = root / 'offline-copy-manifest.json'
    if not marker.is_file(): raise ValueError('Worker requires the parent-created disposable-copy manifest')
    spec = json.loads(marker.read_text())
    expected = root / f'load-slots{args.slots}.sqlite3'
    source = Path(spec['source']).resolve()
    ledger = args.ledger.resolve()
    if (spec.get('scope') != 'offline-disposable-ledgers-only'
            or ledger != expected or expected.name not in spec.get('copies', [])
            or ledger == source or os.path.samefile(ledger, source)):
        raise ValueError('Worker ledger is not an authorized disposable child copy')


def build_templates(database):
    templates = {}
    with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as db:
        rows = db.execute("SELECT attempt_id,metadata FROM attempts WHERE status='settled' "
                          "ORDER BY rowid DESC LIMIT 4096")
        for aid, metadata in rows:
            request = json.loads(metadata).get('request',{})
            schema = request.get('response_format',{}).get('json_schema',{})
            family = next((f for f,name in SCHEMAS.items() if schema.get('name')==name),None)
            if family is None or family in templates: continue
            event = db.execute("SELECT details FROM events WHERE attempt_id=? AND kind='physical_response' "
                               "ORDER BY sequence DESC LIMIT 1",(aid,)).fetchone()
            if event is None: continue
            response = json.loads(event[0]).get('response')
            if not response or not response.get('choices'): continue
            content = response['choices'][0]['message'].get('content')
            try: parsed = json.loads(content)
            except (TypeError,json.JSONDecodeError): continue
            body = scrub(response)
            body['choices'][0]['message']['content'] = json.dumps(scrub(parsed),ensure_ascii=False)
            body['choices'][0]['finish_reason'] = 'stop'
            body['choices'][0]['message']['refusal'] = None
            body['service_tier'] = 'default'; body['model']='gpt-6-luna'
            templates[family] = {'schema':schema, 'response':body,
                'system':'x'*len(request['messages'][0]['content'].encode('utf-8','replace')),
                'user':'x'*len(request['messages'][1]['content'].encode('utf-8','replace')),
                'max_tokens':request['max_completion_tokens'],
                'shape':{'source_request_json_bytes':len(json.dumps(request,ensure_ascii=False).encode()),
                         'source_response_json_bytes':len(json.dumps(response,ensure_ascii=False).encode()),
                         'system_bytes':len(request['messages'][0]['content'].encode('utf-8','replace')),
                         'user_bytes':len(request['messages'][1]['content'].encode('utf-8','replace'))}}
            if len(templates)==3: break
    if set(templates)!=set(FAMILIES): raise ValueError('Missing bounded DEV request/response shape fixtures')
    return templates


def worker(args):
    validate_worker_copy(args)  # Before AtomicBudget, transport or cache setup.
    from olens_improve.budget import AtomicBudget
    from olens_improve.evaluation import (BudgetedClient, install_shared_verdict_cache,
                                        install_upstream_transport, load_upstream)
    from olens_improve.performance import OperationalProfile
    load_upstream()
    from wsbench import llm
    from wsbench.cache import Cache
    from wsbench.mcjudge import Call
    root = args.output; root.mkdir(parents=True,exist_ok=False)
    template = json.loads(args.templates.read_text())[args.family]
    ledger = AtomicBudget(args.ledger,bootstrap_claude=False)
    run_id = f'offline-load-slots{args.slots}-{args.family}'
    ledger.set_run_limit(run_id,'20')
    profile = OperationalProfile(root/'profile.json',metadata={'family':args.family,
        'concurrency':args.slots,'offline':True,'rpm':100000})
    profile.attach_ledger(ledger)
    os.environ['OLENS_ALLOW_PAID_CALLS']='1'  # Only the fake inner object exists below.
    os.environ.pop('OLENS_TRANSPORT_RECOVERY_SINCE',None)
    install_upstream_transport(ledger,run_id,allow_paid=True,service_tier='default',attempts=1)
    class FakeResponse:
        def __init__(self, number):
            self.body = json.loads(json.dumps(template['response']))
            self.body['id']=f'offline-response-{number}'
            self.body['usage']['prompt_tokens']=100
            self.body['usage']['completion_tokens']=20
            self.body['usage']['total_tokens']=120
            self.body['usage']['prompt_tokens_details']={'cached_tokens':0,'cache_write_tokens':0}
            self.body['usage']['completion_tokens_details']={'reasoning_tokens':0}
            self.id=self.body['id']; self.service_tier='default'
            self.choices=[SimpleNamespace(message=SimpleNamespace(
                content=self.body['choices'][0]['message']['content'],refusal=None),finish_reason='stop')]
            self.usage=SimpleNamespace(prompt_tokens=100,completion_tokens=20,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0,cache_write_tokens=0),
                completion_tokens_details=SimpleNamespace(reasoning_tokens=0))
        def model_dump(self,mode='json'): return self.body
    class FakeInner:
        def __init__(self):
            self.count=0; self.chat=SimpleNamespace(completions=self)
        async def create(self,**_request):
            self.count+=1; number=self.count
            await asyncio.sleep(args.delay)
            return FakeResponse(number)
        async def close(self): pass
    fake = FakeInner()
    llm.api_key=lambda _model:'offline-unused'
    llm._make_client=lambda _route,_key:BudgetedClient(fake,ledger,run_id,allow_paid=True,
                                                    metadata={'purpose':'offline-no-network-load'})
    install_shared_verdict_cache(root/'shared.sqlite3',ledger,args.family)
    module=importlib.import_module(f'wsbench.evals.{args.family}.judge')
    calls=[Call(key=f'fake-{i}',system=template['system'],user=template['user']+f'\noffline-{i}')
           for i in range(args.calls)]
    status='completed'; started=time.perf_counter()
    try:
        with Cache(root/'local.jsonl') as cache:
            results=module.run_calls(calls,schema=template['schema'],
                judge=SimpleNamespace(model='gpt-6-luna',reasoning={'effort':'none'}),
                prompt_version='offline-load-shape-v1',cache=cache,spend=llm.Spend(),
                concurrency=args.slots,rpm=100000,dry_run=False,max_tokens=template['max_tokens'])
        assert len(results)==args.calls and all(r is not None for r in results.values())
        assert fake.count==args.calls
    except BaseException as exc:
        status='failed:'+type(exc).__name__; raise
    finally:
        report=profile.close(status)
        with sqlite3.connect(f'file:{args.ledger}?mode=ro',uri=True) as db:
            accounting=dict(db.execute('SELECT status,COUNT(*) FROM attempts WHERE run_id=? GROUP BY status',(run_id,)))
        (root/'result.json').write_text(json.dumps({'status':status,'calls':fake.count,
            'wall_seconds':time.perf_counter()-started,'fake_delay_seconds':args.delay,
            'accounting':accounting,'shape':template['shape'],'network_calls':0,
            'scope':'Disposable copied ledger; fake content and transport; no scientific verdicts or real charges'},indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--calls',type=int,default=64,help='Fake calls per worker per mode')
    p.add_argument('--delay',type=float,default=3.)
    p.add_argument('--worker',action='store_true')
    p.add_argument('--family',choices=FAMILIES)
    p.add_argument('--slots',type=int,choices=(8,16))
    p.add_argument('--templates',type=Path)
    args=p.parse_args()
    if args.calls<16 or args.delay<=0: p.error('Use at least16 fake calls and a positive simulated delay')
    if not os.environ.get('SLURM_JOB_ID'): raise RuntimeError('Copied-ledger load check needs the assigned CPU allocation')
    if args.worker:
        if not args.family or not args.slots or not args.templates: p.error('Incomplete worker configuration')
        worker(args); return
    source=args.ledger.resolve();root=args.output.resolve()
    root.mkdir(parents=True,exist_ok=False)
    templates=root/'fake-shapes.json';templates.write_text(json.dumps(build_templates(source))+'\n')
    snapshot=root/'source-snapshot.sqlite3'
    with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as src,sqlite3.connect(snapshot) as dst:
        src.backup(dst)
    (root/'offline-copy-manifest.json').write_text(json.dumps({'scope':'offline-disposable-ledgers-only',
        'source':str(source),'copies':['load-slots8.sqlite3','load-slots16.sqlite3']})+'\n')
    source_before=readonly_accounting(source)
    (root/'source-accounting-before.json').write_text(json.dumps(source_before,indent=2)+'\n')
    summaries=[]
    for slots in (8,16):
        database=root/f'load-slots{slots}.sqlite3';shutil.copyfile(snapshot,database)
        processes=[]
        for family in FAMILIES:
            directory=root/f'slots{slots}-{family}'
            command=[sys.executable,'-B',str(Path(__file__).resolve()),'--worker',
                '--ledger',str(database),'--output',str(directory),'--family',family,
                '--slots',str(slots),'--templates',str(templates),'--calls',str(args.calls),'--delay',str(args.delay)]
            with (root/f'slots{slots}-{family}.log').open('w') as log:
                processes.append(subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT))
        codes=[process.wait() for process in processes]
        if any(codes): raise RuntimeError(f'Offline worker failure codes: {codes}; preserve fixture')
        for family in FAMILIES:
            summaries.append(json.loads((root/f'slots{slots}-{family}/result.json').read_text())|{'slots':slots,'family':family})
    source_after=readonly_accounting(source)
    (root/'source-accounting-after.json').write_text(json.dumps(source_after,indent=2)+'\n')
    assert source_after==source_before, 'Production accounting changed during the isolated diagnostic'
    (root/'report.json').write_text(json.dumps({'workers':summaries,'source_attempt_count_unchanged':True,
        'source_accounting_unchanged':True, 'source_accounting':source_after,
        'network_calls':0,'scope':'No-network shape-only local load: fake JSON enums/quotes and custom semantic validation/stage2 are not exercised; not provider latency or full evaluator equivalence',
        'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
    print(json.dumps({'status':'completed','network_calls':0,'report':str(root/'report.json')}))


if __name__=='__main__':main()
