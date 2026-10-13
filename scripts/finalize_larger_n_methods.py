"""Merge six frozen N64 methods with their saved reference arms and judge them."""
from collections import defaultdict
from contextlib import redirect_stdout
import argparse
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import evaluate_larger_n_pilot as base
from olens_improve import reporting
from run_larger_n_methods_cpu import ROOT,PILOT,CHECKPOINT,WHITENERS,write,sha

OUT=Path('${OLENS_DATA_ROOT}/larger-n-methods-v1')
RUN_ID='larger-n-all-methods-quality-v1'
SEM='consensus_semantic_v5_support0.125_compaton_vetoon'


def prepare(out):
    import torch
    from safetensors import safe_open
    from transformers import AutoTokenizer
    from olens_improve.selection import parse_bullets
    from olens_improve.ar_cache import vector_key
    from olens_improve.reconstruction import RawVectorCache,Whitener,JointNNLS,ar_token_ids
    torch.set_num_threads(2)
    pilot=json.loads(PILOT.read_text());cells={c['cell_id']:c for c in pilot['cells']}
    rows={r['cell_id']:r for r in map(json.loads,(OUT/'quality-core/selections.jsonl').read_text().splitlines())}
    cpu={r['cell_id']:r for r in map(json.loads,(OUT/'cpu/selections.jsonl').read_text().splitlines())}
    old=RawVectorCache(pilot['vector_cache']);new=RawVectorCache(str(ROOT/'score256/ar-cache'))
    tok=AutoTokenizer.from_pretrained(pilot['base_snapshot'],local_files_only=True)
    count=lambda t:len(tok(t,add_special_tokens=False)['input_ids'])
    state=torch.load(CHECKPOINT/'heads.pt',map_location='cpu',weights_only=True)
    tags={int(l):state['tag_ids'][i].tolist() for i,l in enumerate(state['layers'])}
    sources={};audits=[]
    # Exact old selected outputs supply the displayed N16 consensus and N32 editor references.
    for family in base.evaluation.FAMILIES:
        wanted={cid for cid,c in cells.items() if c['family']==family}
        for folder,method,n in [('semantic-semantic-v1',SEM,16),('editing-round2-v1','editing_round2',32)]:
            descriptor=json.loads((Path('.state/expanded-final-native-ready-v1')/folder/f'{family}.ready.json').read_text())
            path=Path(descriptor['selections']);assert sha(path)==descriptor['selection_sha256']
            sources[str(path)]=descriptor['selection_sha256'];found=set()
            for line in path.open():
                r=json.loads(line);cid=r['cell_id']
                if cid not in wanted:continue
                assert r['activation_sha256']==cells[cid]['activation_sha256']
                selection=next(s for s in r['selections'] if s['method']==method and s['n']==n)
                rows[cid]['selections'].append(selection);found.add(cid)
            assert found==wanted
        descriptor=json.loads((Path('.state/expanded-final-native-ready-v1/cached-v2')/f'{family}.ready.json').read_text())
        path=Path(descriptor['selections']);assert sha(path)==descriptor['selection_sha256'];sources[str(path)]=descriptor['selection_sha256']
        for line in path.open():
            r=json.loads(line);cid=r['cell_id']
            if cid not in wanted:continue
            for current,original in [('pooled_greedy_swap','pooled_greedy_swap'),('prune_loo_best_0.005','prune_loo_a32_0.005')]:
                a=next(s for s in cpu[cid]['selections'] if s['method']==current and s['n']==32)
                b=next(s for s in r['selections'] if s['method']==original and s['n']==32)
                assert a['text']==b['text']
                if b.get('fits',{}).get('exact',{}).get('fve') is not None:
                    assert abs(a['fits']['exact']['fve']-b['fits']['exact']['fve'])<1e-5
                audits.append({'cell_id':cid,'method':current,'n32_text_matches_original':True,
                               'historical_export_contains_fve':b.get('fits',{}).get('exact',{}).get('fve') is not None})
    semantics={r['cell_id']:r for r in map(json.loads,(OUT/'helpers/semantic/semantic_candidates.jsonl').read_text().splitlines())}
    edits={r['cell_id']:r for r in map(json.loads,(OUT/'editing-scores/round2/scored_candidates.jsonl').read_text().splitlines())}
    parsed=defaultdict(dict)
    for line in (ROOT/'sampling/samples_n064.jsonl').open():
        r=json.loads(line);cid=r['cell_id'];ident=f"{r.get('global_pool_id') or r['pool_id']}:{cid}:{r['sample_index']}"
        s=parse_bullets(r['text'],ident,r['sample_index'],token_count=count,max_output_tokens=256)
        parsed[cid].update({b.phrase_id:b for b in s.bullets})
    whiteners={}
    for cid,c in cells.items():
        semantic=semantics[cid];bs=[parsed[cid][pid] for pid in semantic['phrase_ids']]
        if c['layer'] not in whiteners:whiteners[c['layer']]=Whitener.load(str(WHITENERS/f"whitening_iolens_pooled_L{c['layer']}.safetensors"))
        w=whiteners[c['layer']]
        rawvectors={}
        for b in bs:
            _,ids=ar_token_ids(tok,b.text);key=vector_key(old.contract['sha256'],tags[c['layer']],ids[:32])
            rawvectors[b.phrase_id]=old.get(key) if key in old.index else new.get(key)
        with safe_open(c['activation_tensor_path'],framework='pt',device='cpu') as f:
            target=f.get_slice('resid')[c['activation_row']:c['activation_row']+1][0]
        assert hashlib.sha256(target.numpy().tobytes()).hexdigest()==c['activation_sha256']
        score=JointNNLS.from_raw(target,rawvectors,w)
        rows[cid]['selections'].append({'method':SEM,'n':64,'text':semantic['text'],'phrase_ids':semantic['phrase_ids'],
             'token_count':count(semantic['text']),'bullet_count':len(bs),'fits':{'exact':score.fit(tuple(semantic['phrase_ids'])).__dict__}})
        e=edits[cid]['best'];assert e and e['token_count']<=256 and e['bullet_count']<=4
        rows[cid]['selections'].append({'method':'editing_round2','n':64,'text':e['text'],'candidate_id':e['candidate_id'],
             'token_count':e['token_count'],'bullet_count':e['bullet_count'],'fits':{'exact':{'fve':e['exact_fve']}},'origin':e['origin']})
    conditions=[{k:s[k] for k in ('method','n')} for s in next(iter(rows.values()))['selections']]
    assert len(conditions)==14
    expected={(s['method'],s['n']) for s in conditions}
    assert all({(s['method'],s['n']) for s in r['selections']}==expected for r in rows.values())
    base.write(out/'manifest.json',json.loads((OUT/'quality-core/manifest.json').read_text()))
    base.write(out/'conditions.json',conditions)
    base.write(out/'original-replay-audit.json',{'checks':audits,'source_sha256':sources})
    (out/'selections.jsonl').write_text(''.join(base.canonical(r)+'\n' for r in sorted(rows.values(),key=lambda r:r['cell_id'])))
    base.write(out/'budget-before.json',base.read_only_budget(base.LEDGER))
    if not (out/'forecast.json').exists():
        with redirect_stdout(io.StringIO()):
            base.forecast_judging.run(SimpleNamespace(manifest=out/'manifest.json',fresh_manifest=None,gate=None,
                family=None,selections=[out/'selections.jsonl'],conditions=[out/'conditions.json'],cache=base.CACHE,
                ledger=base.LEDGER,output=out/'forecast.json',empirical_summary=base.EMPIRICAL,
                empirical_since='2026-10-10T04:50:43+00:00',concurrency=4,rpm=120))
    f=json.loads((out/'forecast.json').read_text())
    print(json.dumps({'conditions':len(conditions),'cache':f['exact_cached_request_counts'],
        'expected_new_usd':f['expected_charge_including_unknown_stage2_upper_using_empirical_means_usd']},indent=2),flush=True)


def report(out):
    conditions=json.loads((out/'conditions.json').read_text())
    pairs=[(f"{s['method']}-n32",f"{s['method']}-n64") for s in conditions if s['n']==64 and s['method']!=SEM]
    pairs.append((f'{SEM}-n16',f'{SEM}-n64'))
    for n in (32,64):
        pairs.extend([(f'best_n_exact-n{n}',f'prune_loo_best_0.005-n{n}'),
                      (f'pooled_greedy_swap-n{n}',f'pooled_greedy_swap_then_prune_0.005-n{n}'),
                      (f'pooled_greedy_swap-n{n}',f'editing_round2-n{n}')])
    result=reporting.summarize(out/'manifest.json',out/'conditions.json',out/'judgments',
        selection_sha=base.sha(out/'selections.jsonl'),comparison_pairs=pairs)
    assert all(c['measurement_complete'] for c in result['conditions'])
    base.write(out/'report.json',result);base.write(out/'budget-after.json',base.read_only_budget(base.LEDGER))
    import sqlite3
    with sqlite3.connect(f'file:{base.LEDGER}?mode=ro',uri=True) as db:
        costs=db.execute('SELECT run_id,status,COUNT(*),SUM(reserved),SUM(actual) FROM attempts WHERE run_id IN (?,?,?,?) GROUP BY run_id,status',
            ('larger-n-pilot-quality-v1','larger-n-methods-quality-v1','larger-n-methods-helpers-v1',RUN_ID)).fetchall()
    base.write(out/'costs.json',{'rows':[{'run_id':r,'status':s,'attempts':n,'reserved_usd':(v or 0)/1e9,'actual_usd':(a or 0)/1e9} for r,s,n,v,a in costs],
        'invoice_reconciled':False})
    print(json.dumps({'status':'complete','conditions':len(conditions),'report':str(out/'report.json')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run','report'))
    p.add_argument('--output',type=Path,default=OUT/'quality-all');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    if a.action=='prepare':prepare(a.output)
    elif a.action=='report':report(a.output)
    else:
        base.CONDITIONS=json.loads((a.output/'conditions.json').read_text());base.RUN_ID=RUN_ID;base.report=report
        base.run(a.output)
