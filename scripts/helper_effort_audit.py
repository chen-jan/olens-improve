"""Frozen candidate-only none/medium diagnostic; no benchmark judging changes."""
import argparse
import ast
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.budget import AtomicBudget
from olens_improve.data import canonical
from olens_improve.evaluation import make_luna_helper_diagnostic_client
from olens_improve.helpers import (HelperCache, LunaHelper, MATCH_VERSION, MATCH_SYSTEM,
                                  MATCH_SCHEMA, confirm_pairs)


def immutable(path, body):
    text = json.dumps(body, ensure_ascii=False, indent=2)+'\n'
    if path.exists() and path.read_text() != text:
        raise ValueError(f'Frozen diagnostic identity changed: {path}')
    path.write_text(text)


async def run(args):
    source = json.loads(args.audit.read_text())
    rows = source['pairs']
    if len(rows) != 40 or len({r['audit_id'] for r in rows}) != 40:
        raise ValueError('This diagnostic is limited to forty frozen distinct pair IDs')
    # Only opaque IDs and text enter helper requests. Manual labels stay local.
    texts = {f'{side}{i:03d}': row[side] for i, row in enumerate(rows) for side in ('a', 'b')}
    pairs = [(f'a{i:03d}', f'b{i:03d}') for i in range(40)]
    args.output.mkdir(parents=True, exist_ok=True)
    identity = {'audit_sha256': hashlib.sha256(args.audit.read_bytes()).hexdigest(),
        'run_id': args.run_id, 'cells': None, 'candidate_pairs': 40, 'chunk_size': 20,
        'max_output_tokens_including_reasoning': 10000, 'tier': 'default',
        'match_version': MATCH_VERSION, 'match_system_sha256': hashlib.sha256(MATCH_SYSTEM.encode()).hexdigest(),
        'schema': MATCH_SCHEMA, 'efforts': ['none', 'medium'], 'attempts_per_chunk': 1,
        'coupled_change': 'none uses temperature0; medium must omit temperature under its API contract.'}
    immutable(args.output/'identity.json', identity)
    ledger = AtomicBudget(args.ledger)
    ledger.set_run_limit(args.run_id, '1')
    helpers = {effort: LunaHelper(make_luna_helper_diagnostic_client(ledger,args.run_id,
        reasoning_effort=effort,allow_paid=args.allow_paid), HelperCache(args.output/f'{effort}-cache.sqlite3'),
        service_tier='default',concurrency=1,attempts=1,reasoning_effort=effort)
        for effort in ('none','medium')}
    results = {'none': {}, 'medium': {}}
    try:
        # The first medium request verifies actual model/structured-output support.
        first = await confirm_pairs(helpers['medium'],pairs[:20],texts,max_output_tokens=10000)
        if len(first) != 20:
            raise RuntimeError('Medium capability request failed; remaining diagnostic was not dispatched')
        results['medium'].update(first)
        (args.output/'capability.json').write_text(json.dumps({'status':'verified by actual API response',
            'pairs':20,'effort':'medium','structured_output':'validated'},indent=2)+'\n')
        print('MEDIUM_CAPABILITY_VERIFIED',flush=True)
        for chunk in (pairs[:20],pairs[20:]):
            got = await confirm_pairs(helpers['none'],chunk,texts,max_output_tokens=10000)
            if len(got) != 20:
                raise RuntimeError('Fresh none control failed; remaining comparison is incomplete')
            results['none'].update(got)
        got = await confirm_pairs(helpers['medium'],pairs[20:],texts,max_output_tokens=10000)
        if len(got) != 20:
            raise RuntimeError('Second medium chunk failed; comparison is incomplete')
        results['medium'].update(got)
    finally:
        for effort,helper in helpers.items():
            (args.output/f'{effort}-events.json').write_text(json.dumps(helper.events,indent=2)+'\n')
        joined=[]
        for i,row in enumerate(rows):
            key=pairs[i]
            joined.append({'audit_id':row['audit_id'],'family':row['family'],'a':row['a'],'b':row['b'],
                'manual_review':row['reviewer'],
                **{effort:asdict(results[effort][key]) if key in results[effort] else None for effort in results}})
        (args.output/'pair-results.json').write_text(json.dumps(joined,ensure_ascii=False,indent=2)+'\n')
        with sqlite3.connect(args.ledger) as db:
            usage=[]
            for aid,status,actual,details in db.execute("SELECT a.attempt_id,a.status,a.actual,e.details FROM attempts a LEFT JOIN events e ON a.attempt_id=e.attempt_id AND e.kind='physical_response' WHERE a.run_id=?",(args.run_id,)):
                response=json.loads(details) if details else {};raw=response.get('response') or {};u=raw.get('usage') or {}
                usage.append({'attempt_id':aid,'status':status,'actual_usd':(actual or 0)/1e9,
                    'latency_s':response.get('latency_s'),'usage':u,
                    'reasoning_tokens':(u.get('completion_tokens_details') or {}).get('reasoning_tokens')})
        (args.output/'usage.json').write_text(json.dumps(usage,indent=2)+'\n')
        (args.output/'budget_snapshot.json').write_text(json.dumps(ledger.snapshot(),indent=2)+'\n')
        for helper in helpers.values():
            await helper.client.close()
    print('COMPLETE_PAIRS',len(joined),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ledger',type=Path,default=Path('${OLENS_DATA_ROOT}/budget/ledger.sqlite3'))
    p.add_argument('--run-id',default='helper-semantic-effort-audit-v1')
    p.add_argument('--allow-paid',action='store_true')
    args=p.parse_args()
    if not args.allow_paid:p.error('This diagnostic dispatch requires explicit --allow-paid')
    if not os.environ.get('OPENAI_API_KEY'):
        for line in Path('.env').read_text().splitlines():
            key,sep,value=line.removeprefix('export ').partition('=')
            if sep and key.strip()=='OPENAI_API_KEY':
                value=value.strip();os.environ['OPENAI_API_KEY']=ast.literal_eval(value) if value[:1] in ('"',"'") else value
    os.environ['OLENS_ALLOW_PAID_CALLS']='1'
    asyncio.run(run(args))


if __name__=='__main__':main()
