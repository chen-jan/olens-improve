"""Frozen candidate-only consensus and edit proposals for the saved N64 pilot."""
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve import evaluation
from olens_improve.budget import AtomicBudget
from olens_improve.helpers import (LunaHelper,semantic_consensus,report_with_merge_veto,reselect_consensus,editing_proposals)
from olens_improve.selection import parse_bullets,output_admissible
from expanded_api import ReusableHelperCache,load_key
from evaluate_larger_n_pilot import LEDGER
from run_larger_n_methods_cpu import PILOT,PILOT_SHA,ROOT,sha,write

OUT=Path('${OLENS_DATA_ROOT}/larger-n-methods-v1')
RUN_ID='larger-n-methods-helpers-v1'


async def run(kind):
    assert os.environ.get('SLURM_JOB_ID') and sha(PILOT)==PILOT_SHA
    from transformers import AutoTokenizer
    manifest=json.loads(PILOT.read_text());cells={c['cell_id']:c for c in manifest['cells']}
    tok=AutoTokenizer.from_pretrained(manifest['base_snapshot'],local_files_only=True)
    count=lambda text:len(tok(text,add_special_tokens=False)['input_ids'])
    admissible=output_admissible(count,256)
    output=OUT/'helpers'/kind;output.mkdir(parents=True,exist_ok=True)
    if kind=='semantic':
        sources={cid:[] for cid in cells}
        for line in (ROOT/'sampling/samples_n064.jsonl').read_text().splitlines():
            r=json.loads(line);cid=r['cell_id']
            assert cid in cells and r['activation_sha256']==cells[cid]['activation_sha256']
            ident=f"{r.get('global_pool_id') or r['pool_id']}:{cid}:{r['sample_index']}"
            sources[cid].append(parse_bullets(r['text'],ident,r['sample_index'],token_count=count,max_output_tokens=256))
        assert all(sorted(s.index for s in v)==list(range(64)) for v in sources.values())
        input_files=[ROOT/'sampling/samples_n064.jsonl']
    elif kind=='edit1':
        sources={r['cell_id']:r for r in map(json.loads,(OUT/'cpu/selections.jsonl').read_text().splitlines())}
        input_files=[OUT/'cpu/selections.jsonl']
    else:
        sources={r['cell_id']:r for r in map(json.loads,(OUT/'editing-scores/round1/beam.jsonl').read_text().splitlines())}
        input_files=[OUT/'editing-scores/round1/beam.jsonl']
    spec={'kind':kind,'pilot_sha256':PILOT_SHA,'inputs':{str(p):sha(p) for p in input_files},
          'code_sha256':{str(p):sha(p) for p in [Path(__file__),Path('src/olens_improve/helpers.py')]},
          'run_id':RUN_ID,'run_cap_usd':5,'model':'gpt-6-luna','effort':'none','tier':'default',
          'concurrency':4,'max_pairs':40,'support_fraction':.125,'compatibility':True,'merge_veto':True,
          'editor_aggregate_proposals_per_cell_per_round':4,'no_task_or_answer_access':True}
    write(output/'spec.json',spec)
    ledger=AtomicBudget(LEDGER,hard_usd=340,target_usd=200);ledger.set_run_limit(RUN_ID,'5');load_key()
    client=evaluation.make_luna_client(ledger,RUN_ID,allow_paid=True,metadata={'purpose':'candidate-only-larger-n-pilot-helper'})
    cache=ReusableHelperCache(output/'helper-cache.sqlite3')
    helper=LunaHelper(client,cache,concurrency=4,attempts=2 if kind=='semantic' else 1,service_tier='default')
    semaphore=asyncio.Semaphore(4);completed=[]
    async def one(cid):
        path=output/(hashlib.sha256(cid.encode()).hexdigest()[:24]+'.json')
        if path.exists():completed.append(json.loads(path.read_text()));return
        async with semaphore:
            c=cells[cid];r={k:c[k] for k in ('cell_id','family','item_id','layer','position','split','activation_sha256')}
            if kind=='semantic':
                samples=sorted(sources[cid],key=lambda s:s.index)
                # Reproduce the original pair proposal/compatibility search at .25,
                # then apply the already chosen .125/veto-on display variant.
                _,original=await semantic_consensus(samples,helper,min_support_fraction=.25,max_pairs=40,
                                                   filter_compatibility=True,admissible=admissible)
                revised=report_with_merge_veto(samples,original,enabled=True)
                selected=reselect_consensus(samples,revised,fraction=.125,filter_compatibility=True,admissible=admissible)
                r.update(method='consensus_semantic_v5_support0.125_compaton_vetoon',n=64,
                         text=selected['text'],phrase_ids=selected['phrase_ids'],report=revised)
            else:
                number=1 if kind=='edit1' else 2
                if number==1:
                    parents=[]
                    for method in ('best_n_exact','pooled_greedy_swap'):
                        s=next(s for s in sources[cid]['selections'] if s['method']==method and s['n']==64)
                        parents.append({'candidate_id':f'{cid}:initial:{method}','text':s['text'],
                                        'exact_fve':s['fits']['exact']['fve'],'source_method':method})
                else:
                    parents=sorted(sources[cid]['parents'],key=lambda p:(-p['exact_fve'],p['candidate_id']))
                result=await editing_proposals(helper,{f's{i}':p['text'] for i,p in enumerate(parents)},token_count=count)
                for proposal in result['proposals']:
                    parent=parents[int(proposal['parent_id'][1:])]
                    proposal.update(candidate_id=f'{cid}:F:r{number}:{proposal["id"]}',parent_candidate_id=parent['candidate_id'])
                r.update(round=number,parents=parents,editing=result,no_judge_feedback=True)
            write(path,r);completed.append(r)
            print(json.dumps({'kind':kind,'complete':len(completed),'total':32,'events':len(helper.events)}),flush=True)
    try:
        await asyncio.gather(*(one(cid) for cid in cells))
    finally:
        await client.close()
        (output/'helper-events.json').write_text(json.dumps(helper.events,indent=2)+'\n')
    assert len(completed)==32
    name='semantic_candidates.jsonl' if kind=='semantic' else 'editing_proposals.jsonl'
    (output/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in sorted(completed,key=lambda r:r['cell_id'])))
    print(json.dumps({'status':'complete','kind':kind,'cells':32}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kind',choices=('semantic','edit1','edit2'))
    asyncio.run(run(p.parse_args().kind))
