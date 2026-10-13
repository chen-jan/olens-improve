"""Prepare, judge and summarize the fixed sparse N32/N64 method comparison."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import evaluate_larger_n_pilot as base
from olens_improve import reporting

ROOT=Path('${OLENS_DATA_ROOT}/larger-n-methods-v1')
REFERENCE=Path('${OLENS_DATA_ROOT}/larger-n-quality-v1')
RUN_ID='larger-n-methods-quality-v1'


def prepare(out):
    cpu=[json.loads(line) for line in (ROOT/'cpu/selections.jsonl').read_text().splitlines()]
    refs={r['cell_id']:r for r in map(json.loads,(REFERENCE/'selections.jsonl').read_text().splitlines())}
    assert len(cpu)==32 and {r['cell_id'] for r in cpu}==set(refs)
    rows=[]
    for r in cpu:
        parent=refs[r['cell_id']]
        assert all(r[k]==parent[k] for k in ('family','item_id','layer','position','split','activation_sha256'))
        choices=[s for s in parent['selections'] if s['method'] in ('raw_n1','capped_n1')]+r['selections']
        rows.append({k:parent[k] for k in parent if k!='selections'}|{'selections':choices})
    conditions=[{k:s[k] for k in ('method','n')} for s in rows[0]['selections']]
    identities={(s['method'],s['n']) for s in conditions}
    assert len(identities)==len(conditions)==10
    assert all({(s['method'],s['n']) for s in r['selections']}==identities for r in rows)
    base.write(out/'manifest.json',json.loads((REFERENCE/'manifest.json').read_text()))
    base.write(out/'conditions.json',conditions)
    (out/'selections.jsonl').write_text(''.join(base.canonical(r)+'\n' for r in rows))
    base.write(out/'budget-before.json',base.read_only_budget(base.LEDGER))
    if not (out/'forecast.json').exists():
        with redirect_stdout(io.StringIO()):
            base.forecast_judging.run(SimpleNamespace(manifest=out/'manifest.json',fresh_manifest=None,gate=None,
                family=None,selections=[out/'selections.jsonl'],conditions=[out/'conditions.json'],cache=base.CACHE,
                ledger=base.LEDGER,output=out/'forecast.json',empirical_summary=base.EMPIRICAL,
                empirical_since='2026-10-10T04:50:43+00:00',concurrency=4,rpm=120))
    f=json.loads((out/'forecast.json').read_text())
    print(json.dumps({k:f[k] for k in ('exact_cached_request_counts','unknown_hall_stage2_unique_requests_upper',
        'expected_charge_including_unknown_stage2_upper_using_empirical_means_usd')},indent=2),flush=True)


def report(out):
    conditions=json.loads((out/'conditions.json').read_text())
    pairs=[(f"{s['method']}-n32",f"{s['method']}-n64") for s in conditions if s['n']==64]
    for n in (32,64):
        pairs += [(f'best_n_exact-n{n}',f'prune_loo_best_0.005-n{n}'),
                  (f'best_n_exact-n{n}',f'pooled_greedy_swap-n{n}'),
                  (f'pooled_greedy_swap-n{n}',f'pooled_greedy_swap_then_prune_0.005-n{n}')]
    result=reporting.summarize(out/'manifest.json',out/'conditions.json',out/'judgments',
        selection_sha=base.sha(out/'selections.jsonl'),comparison_pairs=pairs)
    if not all(c['measurement_complete'] for c in result['conditions']):
        raise RuntimeError('Incomplete method-task measurements')
    base.write(out/'report.json',result)
    base.write(out/'budget-after.json',base.read_only_budget(base.LEDGER))
    import sqlite3
    with sqlite3.connect(f'file:{base.LEDGER}?mode=ro',uri=True) as db:
        rows=db.execute('SELECT status,COUNT(*),SUM(reserved),SUM(actual) FROM attempts WHERE run_id=? GROUP BY status',(RUN_ID,)).fetchall()
    base.write(out/'run-cost.json',{'run_id':RUN_ID,'by_status':[{'status':s,'attempts':n,'reserved_usd':(r or 0)/1e9,
               'actual_usd':(a or 0)/1e9} for s,n,r,a in rows],'invoice_reconciled':False,'gpu_work':False})
    print(json.dumps({'status':'complete','conditions':len(conditions),'report':str(out/'report.json')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run','report'))
    p.add_argument('--output',type=Path,default=ROOT/'quality-core');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    if a.action=='prepare':prepare(a.output)
    elif a.action=='report':report(a.output)
    else:
        base.CONDITIONS=json.loads((a.output/'conditions.json').read_text());base.RUN_ID=RUN_ID;base.report=report
        base.run(a.output)
