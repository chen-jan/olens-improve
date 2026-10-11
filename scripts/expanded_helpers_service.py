#!/usr/bin/env python3
"""Persistent helper phases, complete-family exports and GPU edit handoffs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from expanded_api import atomic_text, digest, records, tokenizer
from olens_improve.data import canonical
from olens_improve.helpers import reselect_consensus, report_with_merge_veto
from olens_improve.selection import parse_bullets, output_admissible

FAMILY_ORDER = ('chain_intermediates','multihop_mt','hallucination','role_bound_association')


def export_semantic(args, family, kind, helper_out, inventory):
    input_dir = args.root/'helper-inputs'/family
    manifest_path = input_dir/'cohort.json'
    cells = {c['cell_id']:c for c in json.loads(manifest_path.read_text())['cells']}
    reports_path = helper_out/'semantic_candidates.jsonl'
    reports = {r['cell_id']:r for r in records(reports_path)}
    if set(reports) != set(cells):
        raise ValueError('Helper family report is not complete')
    prefix = 'consensus_semantic_v5_medium_support' if kind == 'medium' else 'consensus_semantic_v5_support'
    conditions = [{'method':c['method'],'n':c['n']} for c in inventory['conditions']
        if c['method'].startswith(prefix) and c['status'] == 'scheduled_full_bank']
    if len(conditions) != (4 if kind == 'medium' else 5):
        raise ValueError('Finite semantic menu differs')
    pools = {cid:{} for cid in cells}
    for row in records(input_dir/'samples-n16.jsonl'):
        pools[row['cell_id']][row['sample_index']] = row['text']
    count = tokenizer()
    admissible = output_admissible(count,256)
    out = args.root/'selections'/f'semantic-{kind}-v1'
    out.mkdir(parents=True,exist_ok=True)
    selection_path = out/f'{family}.jsonl'
    tmp = selection_path.with_suffix('.jsonl.tmp')
    report_sha = digest(reports_path)
    with tmp.open('w') as target:
        for cid,cell in cells.items():
            if sorted(pools[cid]) != list(range(16)):
                raise ValueError('Consensus export lacks original N16 source pool')
            samples = [parse_bullets(pools[cid][i],f'{cid}:s{i:02d}',i,token_count=count,
                        max_output_tokens=256) for i in range(16)]
            selections = []
            for condition in conditions:
                parsed = re.fullmatch(r'consensus_semantic_v5_(?:medium_)?support([0-9.]+)_compat(on|off)_veto(on|off)',condition['method'])
                if not parsed:
                    raise ValueError('Unrecognized finite semantic condition')
                fraction, compatible, veto = float(parsed[1]),parsed[2]=='on',parsed[3]=='on'
                evidence = report_with_merge_veto(samples,reports[cid]['report'],enabled=veto)
                selected = reselect_consensus(samples,evidence,fraction=fraction,
                    filter_compatibility=compatible,admissible=admissible)
                selections.append({**condition,'text':selected['text'],
                    'token_count':count(selected['text']),'bullet_count':len(selected['phrase_ids']),
                    'phrase_ids':selected['phrase_ids'],'fits':None,
                    'trace':{**selected,'merge_veto':evidence.get('merge_veto'),
                             'source_report_sha256':report_sha},
                    'reasoning_effort':'medium' if kind == 'medium' else 'none'})
            target.write(canonical({**cell,'inventory_sha256':args.inventory_sha256,
                                     'selections':selections})+'\n')
        target.flush()
        os.fsync(target.fileno())
    os.replace(tmp,selection_path)
    descriptor = {'ready':True,'family':family,'manifest':str(manifest_path),
        'manifest_sha256':digest(manifest_path),'selections':str(selection_path),
        'selection_sha256':digest(selection_path),'conditions':conditions,
        'inventory_sha256':args.inventory_sha256,'source_reports':{'path':str(reports_path),'sha256':report_sha}}
    atomic_text(out/f'{family}.ready.json',canonical(descriptor)+'\n')


def export_edit(args, family, number, score_dir):
    manifest_path = args.root/'helper-inputs'/family/'cohort.json'
    cells = {c['cell_id']:c for c in json.loads(manifest_path.read_text())['cells']}
    scored_path = score_dir/'scored_candidates.jsonl'
    scored = {r['cell_id']:r for r in records(scored_path)}
    if set(scored) != set(cells):
        raise ValueError('Scored editor family is incomplete')
    source_sha = digest(scored_path)
    out = args.root/'selections'/f'editing-round{number}-v1'
    out.mkdir(parents=True,exist_ok=True)
    path = out/f'{family}.jsonl'
    condition = {'method':f'editing_round{number}','n':32}
    rows = []
    for cid,cell in cells.items():
        row = scored[cid]
        best = row['best']
        if not best or best['token_count'] > 256 or best['bullet_count'] > 4:
            raise ValueError('Missing/cap-violating selected editor output')
        if not any(c['candidate_id']==best['candidate_id'] and c['text']==best['text'] for c in row['candidates']):
            raise ValueError('Selected edit not in retained scored union')
        rows.append({**cell,'inventory_sha256':args.inventory_sha256,'selections':[
            {**condition,'text':best['text'],'candidate_id':best['candidate_id'],
             'origin':best['origin'],'token_count':best['token_count'],
             'bullet_count':best['bullet_count'],'phrase_ids':[a['phrase_id'] for a in best['atom_metadata']],
             'fits':{'exact':{'fve':best['exact_fve'],'coefficients':best['coefficients']},
                     'released80':{'fve':best['released80_fve']}},
             'trace':{'scored_source_sha256':source_sha,'scoring_spec_sha256':row['spec_sha256']}}]})
    atomic_text(path,''.join(canonical(row)+'\n' for row in rows))
    descriptor = {'ready':True,'family':family,'manifest':str(manifest_path),
        'manifest_sha256':digest(manifest_path),'selections':str(path),
        'selection_sha256':digest(path),'conditions':[condition],
        'inventory_sha256':args.inventory_sha256,'scored_source':{'path':str(scored_path),'sha256':source_sha}}
    atomic_text(out/f'{family}.ready.json',canonical(descriptor)+'\n')


def invoke_helper(args,family,kind,number=1):
    input_dir = args.root/'helper-inputs'/family
    out = args.root/'helpers'/(f'editing-round{number}' if kind=='editing' else f'semantic-{kind}')/family
    command = [sys.executable,'scripts/expanded_api.py','--allow-paid','--kind',kind,
        '--inventory',str(args.inventory),'--inventory-sha256',args.inventory_sha256,
        '--forecast',str(args.forecast),'--manifest',str(input_dir/'cohort.json'),
        '--output',str(out),'--concurrency','64','--cell-concurrency','512',
        '--run-id',args.run_id,'--run-cap-usd',args.run_cap_usd]
    if kind == 'editing':
        parents = input_dir/'editor-parents.jsonl' if number==1 else args.root/'editing-scores'/'round1'/family/'beam.jsonl'
        command += ['--round',str(number),'--edit-input',str(parents)]
        for phase in ('round1','round2'):
            cache = Path('${OLENS_DATA_ROOT}/runs/helper-edit-pilot-v1')/phase/'helper_cache.sqlite3'
            if cache.exists():
                command += ['--helper-cache',str(cache)]
    else:
        command += ['--records',str(input_dir/'samples-n16.jsonl')]
        cache = Path('${OLENS_DATA_ROOT}/runs')/('helper-semantic-medium-reconfirmation-v1' if kind=='medium' else 'helper-semantic-repaired-pilot-v1')/'helper_cache.sqlite3'
        command += ['--helper-cache',str(cache)]
        if kind == 'medium':
            command += ['--reports',str(args.root/'helpers'/'semantic-semantic'/family/'semantic_candidates.jsonl')]
    print(canonical({'launching_helper':kind,'family':family,'round':number}),flush=True)
    subprocess.run(command,check=True)
    return out


def publish_gpu_descriptor(args,family,number,out):
    path = out/'editing_proposals.jsonl'
    manifest_path = args.root/'helper-inputs'/family/'cohort.json'
    history = None
    if number==2:
        history_path = args.root/'editing-scores'/'round1'/family/'scored_candidates.jsonl'
        history = {'path':str(history_path),'sha256':digest(history_path)}
    descriptor = {'id':f'editing-round{number}-{family}-v1','round':number,'family':family,
        'proposals':{'path':str(path),'sha256':digest(path)},
        'cells_manifest':{'path':str(manifest_path),'sha256':digest(manifest_path)},
        'history':history,'output':str(args.root/'editing-scores'/f'round{number}'/family)}
    args.gpu_descriptors.mkdir(parents=True,exist_ok=True)
    target = args.gpu_descriptors/f'round{number}-{family}.json'
    if target.exists() and json.loads(target.read_text()) != descriptor:
        raise ValueError('Immutable GPU edit descriptor changed')
    atomic_text(target,canonical(descriptor)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--inventory-sha256',required=True)
    parser.add_argument('--forecast',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=Path('${OLENS_DATA_ROOT}/expansion-v1'))
    parser.add_argument('--lane',choices=('editing','semantic'),required=True)
    parser.add_argument('--gpu-descriptors',type=Path,default=Path('.state/expanded-gpu-edit-descriptors'))
    parser.add_argument('--run-id',default='expanded-all-four-banks-v1')
    parser.add_argument('--run-cap-usd',default='298')
    args = parser.parse_args()
    if digest(args.inventory) != args.inventory_sha256:
        raise ValueError('Sealed helper inventory changed')
    inventory = json.loads(args.inventory.read_text())
    os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false')
    state_path = Path(f'.state/expansion-helpers-{args.lane}-v1.json')
    state = {'job_id':os.environ.get('SLURM_JOB_ID'),'pid':os.getpid(),'lane':args.lane,
        'completed':[],'started_unix':time.time(),'inventory_sha256':args.inventory_sha256}
    def record(phase,family,number=None):
        state.update(phase=phase,family=family,round=number,last_check_unix=time.time())
        atomic_text(state_path,canonical(state)+'\n')
    if args.lane=='semantic':
        for family in FAMILY_ORDER:
            for kind in ('semantic','medium'):
                record(kind,family)
                out = invoke_helper(args,family,kind)
                export_semantic(args,family,kind,out,inventory)
                state['completed'].append(f'{kind}:{family}')
    else:
        for family in FAMILY_ORDER:
            record('round1_proposals',family,1)
            out = invoke_helper(args,family,'editing',1)
            publish_gpu_descriptor(args,family,1,out)
            state['completed'].append(f'round1_proposals:{family}')
        pending = set(FAMILY_ORDER)
        while pending:
            for family in FAMILY_ORDER:
                if family not in pending:
                    continue
                score_dir = args.root/'editing-scores'/'round1'/family
                status_path = score_dir/'status.json'
                if not status_path.exists() or json.loads(status_path.read_text()).get('status')!='complete':
                    continue
                export_edit(args,family,1,score_dir)
                record('round2_proposals',family,2)
                out = invoke_helper(args,family,'editing',2)
                publish_gpu_descriptor(args,family,2,out)
                pending.remove(family)
                state['completed'].append(f'round2_proposals:{family}')
            record('awaiting_round1_AR_scores',','.join(sorted(pending)))
            if pending:
                time.sleep(20)
        pending = set(FAMILY_ORDER)
        while pending:
            for family in FAMILY_ORDER:
                score_dir = args.root/'editing-scores'/'round2'/family
                status_path = score_dir/'status.json'
                if family in pending and status_path.exists() and json.loads(status_path.read_text()).get('status')=='complete':
                    export_edit(args,family,2,score_dir)
                    pending.remove(family)
                    state['completed'].append(f'round2_scored_export:{family}')
            record('awaiting_round2_AR_scores',','.join(sorted(pending)))
            if pending:
                time.sleep(20)
    record('complete','all')


if __name__=='__main__':
    main()
