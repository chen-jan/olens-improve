#!/usr/bin/env python3
"""Preview helper contracts; only explicit --allow-paid dispatches bounded calls."""
import argparse
import ast
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import sqlite3
import contextlib
import difflib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.budget import AtomicBudget
from olens_improve.data import canonical
from olens_improve.evaluation import make_luna_client,request_cache_key
from olens_improve.helpers import (HelperCache,LunaHelper,PROPOSAL_VERSION,MATCH_VERSION,
    PROPOSAL_SYSTEM,MATCH_SYSTEM,PROPOSAL_SCHEMA,MATCH_SCHEMA,PairRelation,clique_clusters,
    semantic_consensus,semantic_audit_pairs,distinct_owner_audit_pairs,confirm_pairs,audit_summary,
    reselect_consensus,editing_proposals,EDIT_VERSION,EDIT_SYSTEM,EDIT_SCHEMA)
from olens_improve.selection import parse_bullets,exact_consensus,output_admissible


def offline_contract_checks():
    # A=B and B=C do not establish A=C. Missing/contradictory edges cannot merge.
    def relation(a,b,label='equivalent'):
        yes=label=='equivalent'
        return PairRelation(a,b,label,yes,yes,yes,'offline fixture',{})
    rows={('a','b'):relation('a','b'),('b','c'):relation('b','c')}
    assert clique_clusters(['a','b','c'],rows)==[['a','b'],['c']]
    rows[('a','c')]=relation('a','c','contradicts')
    assert clique_clusters(['a','b','c'],rows)==[['a','b'],['c']]
    sample=parse_bullets('- The total is 12.\n- The total is 12.','internal-secret-item',0)
    selection=exact_consensus([sample])
    assert len(selection.bullets)==1
    assert len(semantic_audit_pairs())==40
    return {'offline_algorithm_checks':'passed','model_quality_tested':False,'paid_calls':0}


class CellProgress:
    """One transactional completed-cell checkpoint; no completion-order ranking."""
    def __init__(self,path,identity):
        self.path=path
        with contextlib.closing(sqlite3.connect(path)) as db:
            db.execute('PRAGMA journal_mode=DELETE')
            db.execute('CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY, body TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS cells (cell_id TEXT PRIMARY KEY, body TEXT)')
            old=db.execute('SELECT body FROM identity WHERE id=1').fetchone()
            body=canonical(identity)
            if old and old[0]!=body:raise RuntimeError('Progress identity changed; use a new directory')
            db.execute('INSERT OR IGNORE INTO identity VALUES (1,?)',(body,));db.commit()
    def rows(self):
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            return {cid:json.loads(body) for cid,body in db.execute('SELECT cell_id,body FROM cells ORDER BY cell_id')}
    def put(self,row):
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.execute('INSERT OR REPLACE INTO cells VALUES (?,?)',(row['cell_id'],canonical(row)));db.commit()


def atomic_text(path,content):
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as f:f.write(content);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def salvage_edit_round(args):
    """Repair proposal labels offline; never guess an unresolved source parent."""
    original=args.salvage_edit
    identity=json.loads((original/'identity.json').read_text())
    events=json.loads((original/'helper_events.json').read_text())
    with contextlib.closing(sqlite3.connect(original/'progress.sqlite3')) as db:
        rows=[json.loads(body) for body, in db.execute('SELECT body FROM cells ORDER BY rowid')]
    with contextlib.closing(sqlite3.connect(args.ledger)) as db:
        landed=[]
        for aid,metadata,details in db.execute("SELECT a.attempt_id,a.metadata,e.details FROM attempts a JOIN events e ON a.attempt_id=e.attempt_id WHERE a.run_id=? AND e.kind='physical_response' ORDER BY e.sequence",(args.run_id,)):
            m=json.loads(metadata);d=json.loads(details)
            key=hashlib.sha256(canonical({'version':identity['edit_version'],'request_key':request_cache_key(m['request'])}).encode()).hexdigest()
            landed.append({'attempt_id':aid,'metadata':m,'response':d,'helper_key':key})
    if len(events)!=len(rows) or len(landed)!=len(rows) or any(e.get('cached') for e in events):
        raise ValueError('Salvage needs one physical completion/event per cell; unresolved correspondence must be inspected')
    if [e['content_key'] for e in events]!=[r['helper_key'] for r in landed]:
        raise ValueError('Completion ordering/content correspondence differs; do not guess provenance')
    from transformers import AutoTokenizer
    runtime=json.loads(Path('configs/runtime.json').read_text())
    tokenizer=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda text:len(tokenizer(text,add_special_tokens=False)['input_ids'])
    repaired=[]
    for row,event,physical in zip(rows,events,landed):
        expected={'parents':[{'id':f's{i}','text':p['text']} for i,p in enumerate(row['parents'])], 'total_proposal_limit':4}
        if json.loads(physical['metadata']['request']['messages'][1]['content'])!=expected:
            raise ValueError('Physical candidate-only payload does not match cell parents')
        raw=physical['response']['response'];body=json.loads(raw['choices'][0]['message']['content'])
        if set(body)!={'proposals'} or not isinstance(body['proposals'],list) or len(body['proposals'])>4:
            raise ValueError('Unexpected response envelope; no automatic salvage')
        accepted=[];rejected=[]
        for index,proposal in enumerate(body['proposals']):
            reason=None
            if set(proposal)!={'id','parent_id','text','change_summary'} or any(not isinstance(v,str) for v in proposal.values()):
                reason='invalid_proposal_schema'
            elif proposal['parent_id'] not in {f's{i}' for i in range(len(row['parents']))}:
                reason='unresolved_parent_reference'
            elif len(proposal['change_summary'])>400:
                reason='summary_exceeds400characters'
            else:
                sample=parse_bullets(proposal['text'],'salvage-output',0)
                if count(proposal['text'])>256 or (proposal['text'].strip() and sample.parsing_uncertain) or 'deterministically_capped' in sample.flags:
                    reason='violates_full_readout_parser_or_token_cap'
            if reason:
                rejected.append({'proposal':proposal,'reason':reason});continue
            parent=row['parents'][int(proposal['parent_id'][1:])]
            delta=list(difflib.ndiff(parent['text'].split(),proposal['text'].split()))
            local_id=f'p{index}'
            accepted.append({**proposal,'id':local_id,'provider_proposal_id':proposal['id'],
                'candidate_id':f'{row["cell_id"]}:F:r{row["round"]}:{local_id}',
                'parent_candidate_id':parent['candidate_id'],
                'introduced_words':[x[2:] for x in delta if x.startswith('+ ')],
                'deleted_words':[x[2:] for x in delta if x.startswith('- ')],
                'word_delta_caveat':'Text differences, not an atomic factual-claim or truth audit.'})
        row['editing']={'version':identity['edit_version'],'proposals':accepted,'rejected':rejected,
            'helper_valid':not rejected,'response_envelope_valid':True,'physical_calls_limit':1,
            'aggregate_proposal_limit':4,'instrument_repair':'offline proposal-ID canonicalization; valid source parents only',
            'original_helper_validation':event,'original_attempt_id':physical['attempt_id'],
            'original_response_id':raw['id'],'original_request_key':physical['metadata']['content_cache_key']}
        repaired.append(row)
    args.output.mkdir(parents=True,exist_ok=True)
    content=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in sorted(repaired,key=lambda r:r['cell_id']))
    target=args.output/'editing_proposals.jsonl'
    if target.exists() and target.read_text()!=content:raise ValueError('Immutable repaired snapshot already differs')
    atomic_text(target,content)
    transform={'rule':'Assign local p0..p3 by returned order; preserve exact text/provider IDs and raw responses; reject unresolved source parent IDs and caps. No calls/retries/rewrites.',
        'original_snapshot_sha256':hashlib.sha256((original/'editing_proposals.jsonl').read_bytes()).hexdigest(),
        'original_events_sha256':hashlib.sha256((original/'helper_events.json').read_bytes()).hexdigest(),
        'repaired_snapshot_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'source_identity':identity,'cells':len(repaired),
        'accepted_proposals':sum(len(r['editing']['proposals']) for r in repaired),
        'rejected_proposals':sum(len(r['editing']['rejected']) for r in repaired),
        'new_calls':0,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    atomic_text(args.output/'transformation.json',json.dumps(transform,indent=2)+'\n')
    print(json.dumps(transform,indent=2))


async def execute_edit_round(args,helper,out):
    """Pause at each AR scoring barrier; never feed benchmark judgments to edits."""
    if args.edit_input is None:raise ValueError('--editing-round requires --edit-input')
    manifest=json.loads(args.manifest.read_text());allowed={c['cell_id']:c for c in manifest['cells']}
    if any(c['split']!='development' for c in allowed.values()):raise ValueError('Editing pilot is DEV-only')
    from transformers import AutoTokenizer
    runtime=json.loads(Path('configs/runtime.json').read_text())
    tokenizer=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda text:len(tokenizer(text,add_special_tokens=False)['input_ids'])
    records=[json.loads(s) for s in args.edit_input.read_text().splitlines()]
    inputs={}
    for row in records:
        cid=row['cell_id']
        if cid not in allowed or cid in inputs:raise ValueError('Editor input outside frozen DEV grid or duplicated')
        if args.editing_round==1:
            wanted=[('best_n_exact',32),('pooled_greedy_swap',32)]
            parents=[]
            for method,n in wanted:
                candidates=[x for x in row['selections'] if x['method']==method and x['n']==n]
                if len(candidates)!=1:raise ValueError('Missing initial A32 or D32 editor parent')
                state=candidates[0]
                parents.append({'candidate_id':f'{cid}:initial:{method}', 'text':state['text'],
                    'exact_fve':state['fits']['exact']['fve'],'source_method':method})
        else:
            parents=row['parents']
            if not 1<=len(parents)<=2 or any('exact_fve' not in p or 'candidate_id' not in p for p in parents):
                raise ValueError('Round2 needs1–2 AR-ranked parents with exactFVE and candidate IDs')
            if any(p['exact_fve'] is None for p in parents):raise ValueError('Missing AR score blocks affected cell')
            parents=sorted(parents,key=lambda p:(-p['exact_fve'],p['candidate_id']))
        if any(count(p['text'])>256 for p in parents):raise ValueError('Parent exceeds frozen256 token cap')
        inputs[cid]=parents
    if set(inputs)!=set(allowed):raise ValueError('Editing round must declare every frozen cell, including failed prerequisites')
    identity={'edit_input_sha256':hashlib.sha256(args.edit_input.read_bytes()).hexdigest(),
        'manifest_sha256':hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        'editing_round':args.editing_round,'edit_version':EDIT_VERSION,'new_Olens_samples':0,
        'physical_calls_per_cell_limit':1,'total_proposals_per_round_limit':4,
        'output_cap':{'bullets':4,'Qwen_tokens':256}}
    progress=CellProgress(out/'progress.sqlite3',identity);completed=progress.rows()
    queue=asyncio.Queue()
    for cid,parents in sorted(inputs.items()):
        if cid not in completed:queue.put_nowait((cid,parents))
    async def worker():
        while not queue.empty():
            cid,parents=queue.get_nowait()
            try:
                opaque={f's{i}':p['text'] for i,p in enumerate(parents)}
                result=await editing_proposals(helper,opaque,token_count=count)
                proposals=[]
                for proposal in result['proposals']:
                    parent=parents[int(proposal['parent_id'][1:])]
                    delta=list(difflib.ndiff(parent['text'].split(),proposal['text'].split()))
                    proposals.append({**proposal,'candidate_id':f'{cid}:F:r{args.editing_round}:{proposal["id"]}',
                        'parent_candidate_id':parent['candidate_id'],
                        'introduced_words':[x[2:] for x in delta if x.startswith('+ ')],
                        'deleted_words':[x[2:] for x in delta if x.startswith('- ')],
                        'word_delta_caveat':'Text differences, not an atomic factual-claim or truth audit.'})
                result['proposals']=proposals
                row={k:allowed[cid][k] for k in ('cell_id','family','item_id','layer','position','split')}
                row.update({'round':args.editing_round,'parents':parents,'editing':result,
                    'next_state':'awaiting_fresh_AR_encoding_and_exact_NNLS_scores',
                    'acceptance_objective':'exact_joint_whitened_nonnegative_FVE; include unchanged parents',
                    'no_judge_feedback':True})
                progress.put(row);completed[cid]=row;print('EDIT_COMPLETED_CELL',len(completed),flush=True)
            finally:queue.task_done()
    tasks=[asyncio.create_task(worker()) for _ in range(min(args.cell_concurrency,queue.qsize()))]
    try:await asyncio.gather(*tasks)
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        atomic_text(out/'editing_proposals.jsonl',''.join(json.dumps(completed[cid],ensure_ascii=False)+'\n' for cid in sorted(completed)))
        atomic_text(out/'identity.json',json.dumps(identity,indent=2)+'\n')


async def execute(args):
    if not args.allow_paid:
        raise RuntimeError('Explicit --allow-paid required after root prompt/budget review')
    if not os.environ.get('OPENAI_API_KEY'):
        for line in Path('.env').read_text().splitlines():
            key,sep,value=line.removeprefix('export ').partition('=')
            if sep and key.strip()=='OPENAI_API_KEY':
                value=value.strip()
                os.environ[key.strip()]=ast.literal_eval(value) if value[:1] in ('"',"'") else value
    os.environ['OLENS_ALLOW_PAID_CALLS']='1'
    ledger=AtomicBudget(args.ledger)
    ledger.set_run_limit(args.run_id,str(args.run_cap_usd))
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    client=make_luna_client(ledger,args.run_id,allow_paid=True,
                            metadata={'purpose':'candidate-only-semantic-helper'})
    helper=LunaHelper(client,HelperCache(out/'helper_cache.sqlite3'),service_tier=args.tier,
                      concurrency=args.concurrency,attempts=1 if args.editing_round else 2)
    try:
        if args.editing_round:await execute_edit_round(args,helper,out)
        if args.audit_traps or args.audit_distinct or args.pair_audit:
            pairs=json.loads(args.pair_audit.read_text())['pairs'] if args.pair_audit else distinct_owner_audit_pairs() if args.audit_distinct else semantic_audit_pairs()
            texts={}
            keys=[]
            for i,pair in enumerate(pairs):
                a,b=f'a{i:03d}',f'b{i:03d}';texts[a]=pair['a'];texts[b]=pair['b'];keys.append((a,b))
            # Only candidate texts enter model payloads, never expected audit labels.
            relations=await confirm_pairs(helper,keys,texts)
            report=audit_summary(pairs,relations)
            (out/'trap_audit.json').write_text(json.dumps({'summary':report,'pairs':pairs,
                'relations':[asdict(x) for x in relations.values()]},indent=2)+'\n')
            print(json.dumps(report,indent=2))
        if args.records:
            manifest=json.loads(args.manifest.read_text())
            allowed={c['cell_id']:c for c in manifest['cells']}
            if any(c['split']!='development' for c in allowed.values()):
                raise RuntimeError('Helper pilot is development-only')
            records=[json.loads(s) for s in args.records.read_text().splitlines()]
            pools={cid:[] for cid in allowed}
            for row in records:
                cid=row['cell_id']
                if cid in allowed and row['sample_index']<args.n:
                    pools[cid].append(row)
            if args.limit: pools=dict(list(sorted(pools.items()))[:args.limit])
            from transformers import AutoTokenizer
            runtime=json.loads(Path('configs/runtime.json').read_text())
            tokenizer=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
            count=lambda text:len(tokenizer(text,add_special_tokens=False)['input_ids'])
            admissible=output_admissible(count,args.max_output_tokens)
            identity={'records_sha256':hashlib.sha256(args.records.read_bytes()).hexdigest(),
                'manifest_sha256':hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                'n':args.n,'support':args.support,'max_output_tokens':args.max_output_tokens,
                'pair_cap':40,'proposal_version':PROPOSAL_VERSION,'matching_version':MATCH_VERSION,
                'tokenizer_snapshot':runtime['paths']['base_snapshot']}
            progress=CellProgress(out/'progress.sqlite3',identity)
            reports=progress.rows()
            if set(reports)-set(pools):raise RuntimeError('Checkpoint has unexpected cells')
            queue=asyncio.Queue()
            for cid,pool in sorted(pools.items()):
                if cid not in reports:queue.put_nowait((cid,pool))
            async def process(cid,pool):
                if sorted(x['sample_index'] for x in pool)!=list(range(args.n)):
                    raise RuntimeError(f'Incomplete/duplicate N={args.n} source pool: {cid}')
                samples=[parse_bullets(x['text'],f'{cid}:s{x["sample_index"]:02d}',x['sample_index'],
                                      token_count=count,max_output_tokens=args.max_output_tokens) for x in pool]
                semantic,report=await semantic_consensus(samples,helper,min_support_fraction=args.support,
                    max_pairs=40,filter_compatibility=True,admissible=admissible)
                exact=exact_consensus(samples,min_support_fraction=args.support,admissible=admissible)
                # Semantic no-filter arm reuses exact helper labels; make no extra calls.
                report['exact_text']=exact.text;report['semantic_text']=semantic.text
                report['exact_phrase_ids']=list(exact.phrase_ids)
                report['threshold_sweep']=[reselect_consensus(samples,report,fraction=f,
                    filter_compatibility=compatible,admissible=admissible)
                    for f in (0.,.25,.5,.75,1.) for compatible in (False,True)]
                row={'cell_id':cid,'family':allowed[cid]['family'],'item_id':allowed[cid]['item_id'],
                    'layer':allowed[cid]['layer'],'position':allowed[cid]['position'],'sample_index':0,
                    'method':semantic.method,'text':semantic.text,'pool_n':args.n,'report':report}
                progress.put(row);reports[cid]=row
                print('COMPLETED_CELL',len(reports),flush=True)
            async def worker():
                while not queue.empty():
                    cid,pool=queue.get_nowait()
                    try:await process(cid,pool)
                    finally:queue.task_done()
            workers=[asyncio.create_task(worker()) for _ in range(min(args.cell_concurrency,queue.qsize()))]
            try:
                await asyncio.gather(*workers)
            finally:
                for task in workers:task.cancel()
                await asyncio.gather(*workers,return_exceptions=True)
                atomic_text(out/'semantic_candidates.jsonl',''.join(json.dumps(reports[cid],ensure_ascii=False)+'\n' for cid in sorted(reports)))
            print('PROCESSED_CELLS',len(reports))
        (out/'helper_events.json').write_text(json.dumps(helper.events,indent=2)+'\n')
        (out/'budget_snapshot.json').write_text(json.dumps(ledger.snapshot(),indent=2)+'\n')
        print('BUDGET',json.dumps(ledger.snapshot()))
    finally:
        atomic_text(out/'helper_events.json',json.dumps(helper.events,indent=2)+'\n')
        atomic_text(out/'budget_snapshot.json',json.dumps(ledger.snapshot(),indent=2)+'\n')
        await client.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--show-prompts',action='store_true')
    p.add_argument('--offline-checks',action='store_true')
    p.add_argument('--allow-paid',action='store_true')
    p.add_argument('--audit-traps',action='store_true')
    p.add_argument('--audit-distinct',action='store_true')
    p.add_argument('--pair-audit',type=Path,help='Candidate-only pairs; local expectedlabels are never sent')
    p.add_argument('--editing-round',type=int,choices=[1,2])
    p.add_argument('--edit-input',type=Path)
    p.add_argument('--salvage-edit',type=Path,help='Offline repair from original completed edit run')
    p.add_argument('--records',type=Path)
    p.add_argument('--manifest',type=Path,default=Path('configs/splits_pilot_shared_v2.json'))
    p.add_argument('--n',type=int,default=4)
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--support',type=float,default=.25)
    p.add_argument('--max-output-tokens',type=int,default=256)
    p.add_argument('--ledger',type=Path,default=Path('${OLENS_DATA_ROOT}/budget/ledger.sqlite3'))
    p.add_argument('--run-id',default='helper-semantic-pilot-v1')
    p.add_argument('--run-cap-usd',type=float,default=2)
    p.add_argument('--tier',choices=['default','flex'],default='default')
    p.add_argument('--concurrency',type=int,default=4)
    p.add_argument('--cell-concurrency',type=int,default=8)
    p.add_argument('--output',type=Path,default=Path('${OLENS_DATA_ROOT}/runs/helper-semantic-pilot-v1'))
    args=p.parse_args()
    if not 1<=args.n<=32: p.error('n must be in1..32')
    if args.salvage_edit:
        if args.allow_paid:p.error('Offline salvage cannot enable paid calls')
        salvage_edit_round(args);return
    if args.offline_checks: print(json.dumps(offline_contract_checks()))
    if args.show_prompts:
        print(json.dumps({'proposal':{'version':PROPOSAL_VERSION,'system':PROPOSAL_SYSTEM,'schema':PROPOSAL_SCHEMA},
                         'matching':{'version':MATCH_VERSION,'system':MATCH_SYSTEM,'schema':MATCH_SCHEMA},
                         'editing':{'version':EDIT_VERSION,'system':EDIT_SYSTEM,'schema':EDIT_SCHEMA}},indent=2))
    if args.allow_paid:
        asyncio.run(execute(args))
    elif args.audit_traps or args.records:
        print(json.dumps({'status':'prepared; no API dispatched','model':'gpt-6-luna','effort':'none',
                          'tier':args.tier,'run_cap_usd':args.run_cap_usd,'trap_pairs':40 if args.audit_traps else 0,
                          'maximum_nonexact_pairs_per_cell':40,'chunk_size':20,
                          'candidate_access':'opaque local IDs and candidate text only'},indent=2))


if __name__=='__main__': main()
