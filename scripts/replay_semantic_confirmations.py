"""Confirm only frozen v5 pairs at medium effort; never propose new pairs."""
import argparse
import ast
import asyncio
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from helper_pilot import CellProgress, atomic_text
from olens_improve.budget import AtomicBudget
from olens_improve.evaluation import make_luna_helper_diagnostic_client
from olens_improve.helpers import (HelperCache, LunaHelper, MATCH_VERSION, MATCH_SYSTEM,
    MATCH_SCHEMA, confirm_pairs, clique_clusters, reselect_consensus)
from olens_improve.selection import parse_bullets, output_admissible


def frozen_phase_pairs(report):
    phases = [report['equivalence_requested_pairs'],report['compatibility_requested_pairs']]
    pairs = [tuple(p) for phase in phases for p in phase]
    if len(pairs)>40 or len(set(pairs))!=len(pairs):
        raise ValueError('Frozen distinct requested-pair cap violated')
    relations = {(r['a'],r['b']):r for r in report['relations']}
    texts = {}
    for pair in pairs:
        if pair not in relations:
            raise ValueError('Replay requires a complete original local source-text mapping')
        r=relations[pair]
        for side in ('a','b'):
            uid=r[side];text=r['evidence'][side]['text']
            if uid in texts and texts[uid]!=text:
                raise ValueError('Opaque source ID maps to conflicting text')
            texts[uid]=text
    return [[tuple(p) for p in phase] for phase in phases],texts


async def run(args):
    source=[json.loads(s) for s in args.reports.read_text().splitlines()]
    manifest=json.loads(args.manifest.read_text());cells={r['cell_id']:r for r in manifest['cells']}
    if len(source)!=189 or {r['cell_id'] for r in source}!=set(cells) or any(r['split']!='development' for r in cells.values()):
        raise ValueError('Replay is restricted to the frozen189 development cells')
    if any(r['pool_n']!=16 or r['report']['prompt_versions'][1]!=MATCH_VERSION for r in source):
        raise ValueError('Replay source is not the frozen N16/v5 instrument')
    total=sum(sum(len(p) for p in frozen_phase_pairs(r['report'])[0]) for r in source)
    if total!=2685:raise ValueError('Expected exactly2685 previously requested pairs')
    from transformers import AutoTokenizer
    runtime=json.loads(Path('configs/runtime.json').read_text())
    tokenizer=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda text:len(tokenizer(text,add_special_tokens=False)['input_ids'])
    admissible=output_admissible(count,256)
    pools={cid:{} for cid in cells}
    for line in args.records.open():
        r=json.loads(line)
        if r['cell_id'] in cells and r['sample_index']<16:
            pools[r['cell_id']][r['sample_index']]=parse_bullets(r['text'],f"{r['cell_id']}:s{r['sample_index']:02d}",r['sample_index'],token_count=count)
    if any(sorted(p)!=list(range(16)) for p in pools.values()):raise ValueError('Incomplete shared N16 pool')
    args.output.mkdir(parents=True,exist_ok=True)
    identity={'source_reports_sha256':hashlib.sha256(args.reports.read_bytes()).hexdigest(),
        'records_sha256':hashlib.sha256(args.records.read_bytes()).hexdigest(),
        'manifest_sha256':hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        'run_id':args.run_id,'effort':'medium','requested_pairs':total,'max_output_tokens':10000,
        'request_concurrency':16,'cell_queue':32,'logical_attempts':2,
        'pair_phases':'Original equivalence and compatibility phase order; separate20-pair chunks.',
        'new_proposals':0,'match_version':MATCH_VERSION,'system':MATCH_SYSTEM,'schema':MATCH_SCHEMA}
    progress=CellProgress(args.output/'progress.sqlite3',identity)
    done=progress.rows();ledger=AtomicBudget(args.ledger);ledger.set_run_limit(args.run_id,'3')
    helper=LunaHelper(make_luna_helper_diagnostic_client(ledger,args.run_id,reasoning_effort='medium',allow_paid=args.allow_paid),
        HelperCache(args.output/'helper_cache.sqlite3'),service_tier='default',concurrency=16,attempts=2,reasoning_effort='medium')
    gate=asyncio.Semaphore(32)
    async def one(original):
        cid=original['cell_id']
        if cid in done:return
        async with gate:
            phases,texts=frozen_phase_pairs(original['report']);relations={};equivalence_relations={}
            for phase_index,phase in enumerate(phases):
                # Only previously requested exact source texts reach the API.
                confirmed=await confirm_pairs(helper,phase,texts,max_output_tokens=10000)
                relations.update(confirmed)
                if phase_index==0:equivalence_relations.update(confirmed)
            report=copy.deepcopy(original['report']);mapping=report['source_mapping']
            # Match native v5: later compatibility labels never retroactively
            # merge clusters formed in the equivalence phase.
            clusters=clique_clusters(list(mapping),equivalence_relations)
            report['clusters']=[]
            for group in clusters:
                ids=[pid for uid in group for pid in mapping[uid]]
                report['clusters'].append({'opaque_members':group,'source_phrase_ids':ids,
                    'supporting_samples':list(dict.fromkeys(pid.rsplit(':',1)[0] for pid in ids))})
            report.update(reasoning_effort='medium',semantic_clusters=len(clusters),
                verified_pairs=len(relations),relations=[asdict(r) for r in relations.values()],
                requested_but_unverified_pairs=[list(pair) for phase in phases for pair in phase if pair not in relations],
                replay='Frozen original proposal and compatibility pairs; no new pair search or generation.')
            selected=reselect_consensus(list(pools[cid].values()),report,fraction=.25,filter_compatibility=True,admissible=admissible)
            row={**original,'text':selected['text'],'report':report,'replay_source_cell_id':cid}
            progress.put(row);done[cid]=row
            print('COMPLETED_CELL',len(done),flush=True)
    try:
        await asyncio.gather(*(one(row) for row in source))
    finally:
        atomic_text(args.output/'semantic_candidates.jsonl',''.join(json.dumps(done[cid],ensure_ascii=False)+'\n' for cid in sorted(done)))
        atomic_text(args.output/'helper_events.json',json.dumps(helper.events,indent=2)+'\n')
        atomic_text(args.output/'identity.json',json.dumps(identity,indent=2)+'\n')
        atomic_text(args.output/'budget_snapshot.json',json.dumps(ledger.snapshot(),indent=2)+'\n')
        await helper.client.close()
    print('PROCESSED_CELLS',len(done),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reports','records','manifest','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--ledger',type=Path,default=Path('${OLENS_DATA_ROOT}/budget/ledger.sqlite3'))
    p.add_argument('--run-id',default='helper-semantic-medium-reconfirmation-v1')
    p.add_argument('--allow-paid',action='store_true');args=p.parse_args()
    if not args.allow_paid:p.error('Replay dispatch requires explicit --allow-paid')
    if not os.environ.get('OPENAI_API_KEY'):
        for line in Path('.env').read_text().splitlines():
            key,sep,value=line.removeprefix('export ').partition('=')
            if sep and key.strip()=='OPENAI_API_KEY':
                value=value.strip();os.environ['OPENAI_API_KEY']=ast.literal_eval(value) if value[:1] in ('"',"'") else value
    os.environ['OLENS_ALLOW_PAID_CALLS']='1';asyncio.run(run(args))


if __name__=='__main__':main()
