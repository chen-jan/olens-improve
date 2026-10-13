"""Evaluate saved N32/N64 pilot texts with the unchanged WorkspaceBench judges.

Partial development grids stay partial. No generation or reconstruction runs.
"""
import argparse
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve import evaluation, reporting
from olens_improve.budget import AtomicBudget
from olens_improve.data import canonical
from expanded_api import load_key
from evaluate_target_only_search import read_only_budget
import forecast_judging

SOURCE = Path('${OLENS_DATA_ROOT}/larger-n-pilot-v1/score256/selections.jsonl')
SOURCE_SHA = '7b8c9488f4a65931ddba49e07bc45db42914e2b46a3d2116bcc2f4c43066b81e'
PILOT = Path('configs/larger_n_pilot_batch256_v2.json')
PILOT_SHA = 'd8f2f0ee8f07397cd7fc9147e7fcf34d6f5a48939b939c9593ad46733e042af8'
LEDGER = Path('${OLENS_DATA_ROOT}/budget/ledger.sqlite3')
CACHE = Path('${OLENS_DATA_ROOT}/runs/development-shared-pilot-v2/judgments/shared-exact-cache')
EMPIRICAL = Path('${OLENS_DATA_ROOT}/selections/development-full-grid-judging-v1/forecast-v1.json')
CONDITIONS = [{'method':'raw_n1','n':1}, {'method':'capped_n1','n':1},
              {'method':'best_n_exact','n':32}, {'method':'best_n_exact','n':64}]
RUN_ID = 'larger-n-pilot-quality-v1'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, obj):
    body = json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n'
    if path.exists() and path.read_text() != body:
        raise ValueError(f'Preserve immutable prior artifact: {path}')
    path.write_text(body)


def prepare(out):
    assert sha(PILOT) == PILOT_SHA and sha(SOURCE) == SOURCE_SHA
    pilot = json.loads(PILOT.read_text())
    cells = [{k:c[k] for k in ('cell_id','family','item_id','layer','position','split','group_id','activation_sha256')}
             for c in pilot['cells']]
    assert Counter(c['family'] for c in cells) == Counter({f:8 for f in evaluation.FAMILIES})
    assert all(c['split']=='development' for c in cells)
    originals = {c['cell_id']:c for c in pilot['cells']}
    source_rows = [json.loads(line) for line in SOURCE.read_text().splitlines() if line.strip()]
    assert len(source_rows)==32 and {r['cell_id'] for r in source_rows}==set(originals)
    rows=[]
    for row in source_rows:
        original=originals[row['cell_id']]
        assert all(row[k]==original[k] for k in ('family','item_id','layer','position','split','activation_sha256'))
        result={r['n']:r for r in row['results']}
        assert original['baseline_selection']['text']==result[32]['text']
        selections=[{'method':'raw_n1','n':1,'text':original['baseline_samples'][0]['text']},
                    {'method':'capped_n1','n':1,'text':result[1]['text']}]
        selections += [{k:result[n][k] for k in ('method','n','text')} for n in (32,64)]
        rows.append({k:row[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')} | {'selections':selections})
    manifest={'schema_version':1,'split':'development','partial_grid':True,'cells':cells,
              'scope':'32 fixed development sites, eight per task; no full-grid benchmark score',
              'parent_manifest_path':str(PILOT),'parent_manifest_sha256':PILOT_SHA}
    write(out/'manifest.json', manifest)
    write(out/'conditions.json', CONDITIONS)
    target=out/'selections.jsonl'; body=''.join(canonical(r)+'\n' for r in rows)
    if target.exists() and target.read_text()!=body: raise ValueError('Selection export changed')
    target.write_text(body)
    write(out/'budget-before.json',read_only_budget(LEDGER))
    if not (out/'forecast.json').exists():
        with redirect_stdout(io.StringIO()):
            forecast_judging.run(SimpleNamespace(manifest=out/'manifest.json',fresh_manifest=None,gate=None,
                family=None,selections=[target],conditions=[out/'conditions.json'],cache=CACHE,ledger=LEDGER,
                output=out/'forecast.json',empirical_summary=EMPIRICAL,empirical_since='2026-10-10T04:50:43+00:00',
                concurrency=4,rpm=120))
    forecast=json.loads((out/'forecast.json').read_text())
    print(json.dumps({k:forecast[k] for k in ('logical_rows','exact_cached_request_counts',
        'unknown_hall_stage2_unique_requests_upper','expected_charge_including_unknown_stage2_upper_using_empirical_means_usd',
        'conditional_service_capacity_reference')},indent=2),flush=True)


def run(out):
    assert os.environ.get('SLURM_JOB_ID'), 'Run in the allocated CPU step'
    approval=json.loads((out/'approval.json').read_text())
    assert approval['run_id']==RUN_ID and approval['run_cap_usd']==1
    for name,digest in approval['input_sha256'].items():
        assert sha(name)==digest, f'Frozen input changed: {name}'
    assert evaluation.load_upstream()['runtime_source_hashes']==approval['upstream_source_hashes']
    budget=read_only_budget(LEDGER)
    assert not budget['halted'] and budget['remaining_hard_usd']>1
    load_key()
    evaluation.AtomicBudget=lambda path: AtomicBudget(path,hard_usd=340,target_usd=200)
    for family in evaluation.FAMILIES:
        with (CACHE/f'{family}.owner.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            for cond in CONDITIONS:
                name=f"{cond['method']}-n{cond['n']}"
                destination=out/'judgments'/name
                terminal=destination/f'{family}.summary.json'
                if terminal.exists():
                    saved=json.loads(terminal.read_text())
                    coverage=coverage_for(family,destination,out)
                    if not coverage['missing_stage1'] and not coverage['missing_stage2']:
                        print(f'REUSE {family} {name}',flush=True);continue
                print(f'START {family} {name}',flush=True)
                evaluation.evaluate_condition(out/'selections.jsonl',out/'manifest.json',destination,
                    **cond,ledger_path=LEDGER,run_id=RUN_ID,run_cap_usd='1',allow_paid=True,
                    concurrency=4,rpm=120,service_tier='flex',family_only=family,
                    shared_cache=CACHE if family!='multihop_mt' else None)
                coverage=coverage_for(family,destination,out)
                if coverage['missing_stage1'] or coverage['missing_stage2']:
                    raise RuntimeError(f'Incomplete {family}/{name}: {coverage}; preserve results for resumption')
                print(f'COMPLETE {family} {name}',flush=True)
    report(out)


def coverage_for(family,destination,out):
    cells=[c for c in json.loads((out/'manifest.json').read_text())['cells'] if c['family']==family]
    reads=[json.loads(line) for line in (destination/f'{family}.readouts.jsonl').read_text().splitlines()]
    result=json.loads((destination/family/'results.json').read_text())
    return reporting.family_counts(family,cells,reads,result)[1]


def report(out):
    report=reporting.summarize(out/'manifest.json',out/'conditions.json',out/'judgments',
        selection_sha=sha(out/'selections.jsonl'),comparison_pairs=[('best_n_exact-n32','best_n_exact-n64'),
        ('raw_n1-n1','best_n_exact-n32'),('raw_n1-n1','best_n_exact-n64')])
    if not all(c['measurement_complete'] for c in report['conditions']):
        raise RuntimeError('Not all four conditions have complete four-task measurements')
    write(out/'report.json',report)
    write(out/'budget-after.json',read_only_budget(LEDGER))
    with __import__('sqlite3').connect(f'file:{LEDGER}?mode=ro',uri=True) as db:
        rows=db.execute('SELECT status,COUNT(*),SUM(reserved),SUM(actual) FROM attempts WHERE run_id=? GROUP BY status',(RUN_ID,)).fetchall()
    write(out/'run-cost.json',{'run_id':RUN_ID,'by_status':[{'status':s,'attempts':n,
         'reserved_usd':(r or 0)/1e9,'actual_usd':(a or 0)/1e9} for s,n,r,a in rows],
         'invoice_reconciled':False,'gpu_work':False})
    print(json.dumps({'status':'complete','report':str(out/'report.json'),'cost':rows}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','report'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    {'prepare':prepare,'run':run,'report':report}[args.action](args.output)
