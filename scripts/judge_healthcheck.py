"""One explicitly authorized direct Luna request; retain all older unknown holds."""
from __future__ import annotations

import argparse
import ast
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.budget import AtomicBudget
from olens_improve.evaluation import make_luna_client, request_cache_key, safe_exception_chain


async def check(args) -> dict:
    if not args.allow_paid:
        raise ValueError('One paid health request requires explicit authorization')
    if os.environ.get('OLENS_TRANSPORT_RECOVERY_SINCE'):
        raise ValueError('Health probe does not reset or resume the paused recovery epoch; use a separate reviewed command')
    if args.output.exists():
        raise ValueError('Health artifact already exists; no repeat dispatch')
    with sqlite3.connect(f'file:{args.ledger}?mode=ro', uri=True) as db:
        row = db.execute('SELECT status,run_id,metadata FROM attempts WHERE attempt_id=?',
                         (args.attempt_id,)).fetchone()
    if not row or row[0] != 'unknown' or row[1] != args.run_id:
        raise ValueError('Probe source must be an existing retained unknown from this run')
    original = json.loads(row[2])
    request = original['request']
    if request.get('model') != 'gpt-6-luna' or request.get('reasoning_effort') != 'none' or request.get('service_tier') != 'default':
        raise ValueError('Expected the exact frozen Standard Luna benchmark request')
    if request_cache_key(request) != original['content_cache_key']:
        raise ValueError('Original request content hash differs')
    if not os.environ.get('OPENAI_API_KEY'):
        for line in Path('.env').read_text().splitlines():
            key, sep, value = line.removeprefix('export ').partition('=')
            if sep and key.strip() == 'OPENAI_API_KEY':
                value = value.strip()
                os.environ[key.strip()] = ast.literal_eval(value) if value[:1] in ('"', "'") else value
    os.environ['OLENS_ALLOW_PAID_CALLS'] = '1'
    ledger = AtomicBudget(args.ledger)
    ledger.set_run_limit(args.run_id, args.run_cap_usd)
    client = make_luna_client(ledger,args.run_id,allow_paid=True,
        metadata={'purpose':'single-authorized-transport-healthcheck','source_unknown_attempt':args.attempt_id})
    started = time.monotonic()
    result = {'started_utc':datetime.now(timezone.utc).isoformat(), 'run_id':args.run_id,
        'original_unknown_attempt_id':args.attempt_id,'original_unknown_status_preserved':True,
        'content_cache_key':original['content_cache_key'],'physical_attempts_allowed':1,
        'source_semantics_unchanged':True,'primary_verdict_replaced':False}
    try:
        response = await client.chat.completions.create(**request,timeout=90)
        result.update(status='success', response_id=response.id,
            usage=response.usage.model_dump(mode='json'), response=response.model_dump(mode='json'))
    except BaseException as error:
        result.update(status='failed', cause_chain=safe_exception_chain(error))
    finally:
        await client.close()
    result['wall_seconds'] = time.monotonic() - started
    result['budget'] = ledger.snapshot()
    with args.output.open('x') as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    return {key:value for key,value in result.items() if key not in ('response','budget')}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-paid',action='store_true')
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--run-cap-usd',required=True)
    parser.add_argument('--attempt-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = asyncio.run(check(args))
    print(json.dumps(result))
    if result['status'] != 'success':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
