"""Finite final evidence pipeline using the unchanged three evidence builders."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from expanded_cpu_cached import atomic, sha
from expanded_final_native_gate import GROUPS, FAMILIES
from expanded_final_reconstruction_gate import freeze_native_authority, unchanged_pins
from build_expansion_qualitative_delta import cases

ROOT=Path(__file__).resolve().parents[1]
DATA=Path('${OLENS_DATA_ROOT}/expansion-v1')
PRIOR_CASES=DATA/'qualitative/first-live-v4.json'
PRIOR_PARENTS=DATA/'qualitative/parent-comparisons-first-live-v3.json'
PRIOR_INDEX=Path('docs/reviews/expanded-qualitative-v4-new-case-index-v1.json')
REVIEWS=tuple(Path('docs/reviews')/name for name in (
    'expanded-qualitative-v4-root-v2.json','expanded-qualitative-v4-agent1-v2.json',
    'expanded-qualitative-v4-agent2-v2.json','expanded-qualitative-v4-agent3-v1.json'))


def indexed_cases(pack):
    records=list(cases(pack));indexed=dict(records)
    if len(indexed)!=len(records):raise ValueError('Duplicate qualitative case identity')
    return indexed


def preserve_prior(previous, current, parents=False):
    old=indexed_cases(previous);new=indexed_cases(current)
    if previous['anchors']!=current['anchors'] or previous['original_readouts']!=current['original_readouts']:
        raise ValueError('Historical anchors/raw and capped readouts changed')
    for key,row in old.items():
        if key not in new:raise ValueError('Previously retained case omitted')
        if previous['contexts'][row['context_ref']]!=current['contexts'].get(row['context_ref']):
            raise ValueError('Previously retained full context changed')
        if parents:
            if {k:v for k,v in row.items()if k!='parents'}!={k:v for k,v in new[key].items()if k!='parents'}:
                raise ValueError('Previous parent-case text/evidence/grid changed')
            for parent,comparison in row['parents'].items():
                if comparison['status']=='complete'and new[key]['parents'].get(parent)!=comparison:
                    raise ValueError('Previous complete parent comparison changed')
        elif new[key]!=row:raise ValueError('Previous full chosen case changed')
    return old,new


def verify_final_scope(pack, active):
    if set(pack['conditions'])!=set(active)or any(set(c['families'])!=set(FAMILIES)for c in pack['conditions'].values()):
        raise ValueError('Final qualitative pack omits active condition/family scope')
    if pack.get('missing')or pack.get('missing_parent_families'):raise ValueError('Final evidence has missing baseline/parent families')


def verify_delta_counts(index, old_cases, new_cases, old_parents, new_parents):
    capped={key for key in new_cases if key not in old_cases}
    parent_refs={(key,parent)for key,row in new_parents.items()for parent,value in row['parents'].items()
        if value['status']=='complete'and old_parents.get(key,{}).get('parents',{}).get(parent,{}).get('status')!='complete'}
    actual_cap=set();actual_parent=set();loads={}
    def collect(kind,pair):
        for ref in pair['references']:
            key=ref['condition'],ref['family'],ref['kind'],ref['cell_id']
            actual=actual_cap if kind=='capped_N1_pairs'else actual_parent
            identity=key if kind=='capped_N1_pairs'else(key,ref['parent_condition'])
            if identity in actual:raise ValueError('Duplicate final indexed reference')
            actual.add(identity)
    for part,units in index['partitions'].items():
        loads[part]=sum(len(u[k])for u in units for k in ('capped_N1_pairs','actual_parent_pairs'))
        for unit in units:
            for kind in ('capped_N1_pairs','actual_parent_pairs'):
                for pair in unit[kind]:collect(kind,pair)
    for unit in index['inherited_comparisons']:collect(unit['pair_kind'],unit['pair'])
    if actual_cap!=capped or actual_parent!=parent_refs:raise ValueError('Final index omits or adds new references')
    if index['retained_previous_cases']!=len(old_cases)or index['new_capped_N1_case_references']!=len(capped)or index['new_actual_parent_references']!=len(parent_refs):raise ValueError('Final declared reference counts differ from actual cases')
    if set(loads)!={'root','agent_1','agent_2','agent_3'}or index['partition_comparison_counts']!=loads:
        raise ValueError('Final pending partition counts differ; retain explicit zero partitions')
    return {'new_capped_references':len(capped),'new_parent_references':len(parent_refs),'pending_partition_comparisons':loads,
        'pending_unique_comparisons':sum(loads.values()),'inherited_unique_comparisons':len(index['inherited_comparisons'])}


def main():
    p=argparse.ArgumentParser();p.add_argument('--pins',type=Path,required=True);p.add_argument('--pins-sha256',required=True)
    p.add_argument('--state',type=Path,required=True);p.add_argument('--max-watch-seconds',type=int,default=28000);a=p.parse_args();os.chdir(ROOT)
    if os.environ.get('SLURM_JOB_ID')!='25536417':raise RuntimeError('Use owned CPU allocation')
    if sha(a.pins)!=a.pins_sha256:raise ValueError('Qualitative pipeline authority changed')
    pins=json.loads(a.pins.read_text())['source_sha256'];unchanged_pins(pins)
    lock=a.state.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state={'status':'waiting_for_exact_terminal_native','pid':os.getpid(),'slurm_job_id':os.environ['SLURM_JOB_ID'],
        'started_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':pins,'new_model_calls':0,'new_api_calls':0}
    native_state=ROOT/'.state/expanded-final-native-v1.service.json';native=DATA/'analysis/final-v1.json'
    snapshot=ROOT/'.state/expanded-final-native-ready-v1';receipt=snapshot/'receipt.json';start=time.monotonic()
    out_cases=DATA/'qualitative/final-v1.json';out_parents=DATA/'qualitative/parent-comparisons-final-v1.json'
    out_index=DATA/'qualitative/final-delta-index-v1.json';attempt=a.state.with_suffix('.attempt.json')
    try:
        if attempt.exists()or any(path.exists()for path in(out_cases,out_parents,out_index)):
            raise FileExistsError('Final qualitative pipeline already attempted; no overwrite or automatic reseal')
        while True:
            body=native_state.read_bytes();terminal=json.loads(body)
            state.update(updated_utc=datetime.now(timezone.utc).isoformat(),native_status=terminal['status'],elapsed_seconds=time.monotonic()-start);atomic(a.state,state)
            if terminal['status']=='complete_pending_root_review':break
            if terminal['status'].startswith('failed'):raise RuntimeError('Native source failed; stop qualitative pipeline')
            if time.monotonic()-start>=a.max_watch_seconds:state['status']='timeout_no_attempt';atomic(a.state,state);return
            time.sleep(30)
        pins.update(freeze_native_authority(native_state,native,receipt,terminal,hashlib.sha256(body).hexdigest()));unchanged_pins(pins)
        quality=json.loads(native.read_text());sealed=json.loads(receipt.read_text());inventory=json.loads(Path('configs/expansion_manifest_v1.json').read_text())
        active={c['condition_id']for c in inventory['conditions']if c['status']in('cached_selector_full_bank','scheduled_full_bank')}
        if len(active)!=70 or quality['manifest_sha256']!=sha('configs/expansion_manifest_v1.json')or quality['status']!='complete_exploratory'or len(quality['complete_condition_families'])!=280 or quality['missing_condition_families']:
            raise ValueError('Final native qualitative source is incomplete')
        expected={str(Path(group)/f'{family}.ready.json')for group in GROUPS for family in FAMILIES}
        if sealed['status']!='sealed_all280_terminal_inputs'or len(sealed['canonical_relative_paths'])!=32 or set(sealed['canonical_relative_paths'])!=expected:
            raise ValueError('Final canonical native descriptor menu differs')
        for path,value in sealed['source_sha256'].items():
            if path in pins and pins[path]!=value:raise ValueError('Shared immutable source differs')
            pins[path]=value
        for relative in sealed['canonical_relative_paths']:
            source=DATA/'selections'/relative;copied=snapshot/relative
            if sha(copied)!=pins[str(source)]:raise ValueError('Canonical copied descriptor differs')
            pins[str(copied)]=pins[str(source)]
        unchanged_pins(pins);atomic(attempt,{'status':'one_attempt_started','source_sha256':pins,'native_sha256':terminal['output_sha256'],
            'native_receipt_sha256':terminal['receipt_sha256'],'outputs':[str(p)for p in(out_cases,out_parents,out_index)],'started_utc':datetime.now(timezone.utc).isoformat()})
        def run(command):
            unchanged_pins(pins)
            with a.state.with_suffix('.log').open('a')as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=False)
            if result.returncode:raise RuntimeError(f'Frozen qualitative producer exited {result.returncode}: {command[1]}')
            unchanged_pins(pins)
        base=[sys.executable];common=['--analysis',str(native),'--analysis-sha256',terminal['output_sha256'],'--judgments',str(DATA/'judgments')]
        state.update(status='extracting_final_capped_cases',updated_utc=datetime.now(timezone.utc).isoformat());atomic(a.state,state)
        run(base+['scripts/build_expansion_qualitative.py',*common,'--output',str(out_cases)])
        pins[str(out_cases)]=sha(out_cases)
        current=json.loads(out_cases.read_text());verify_final_scope(current,active);old_cases,new_cases=preserve_prior(json.loads(PRIOR_CASES.read_text()),current)
        state.update(status='extracting_final_actual_parents',updated_utc=datetime.now(timezone.utc).isoformat());atomic(a.state,state)
        run(base+['scripts/build_expansion_parent_qualitative.py',*common,'--cases',str(out_cases),'--cases-sha256',pins[str(out_cases)],'--output',str(out_parents)])
        pins[str(out_parents)]=sha(out_parents)
        parent_pack=json.loads(out_parents.read_text());verify_final_scope(parent_pack,active);old_parents,new_parents=preserve_prior(json.loads(PRIOR_PARENTS.read_text()),parent_pack,True)
        state.update(status='indexing_exact_final_delta',updated_utc=datetime.now(timezone.utc).isoformat());atomic(a.state,state)
        command=base+['scripts/build_expansion_qualitative_delta_v2.py','--previous',str(PRIOR_CASES),'--current',str(out_cases),
            '--previous-parents',str(PRIOR_PARENTS),'--current-parents',str(out_parents),'--prior-index',str(PRIOR_INDEX),'--output',str(out_index)]
        for review in REVIEWS:command.extend(['--prior-review',str(review)])
        run(command);pins[str(out_index)]=sha(out_index);index=json.loads(out_index.read_text());counts=verify_delta_counts(index,old_cases,new_cases,old_parents,new_parents)
        for path in (PRIOR_INDEX,*REVIEWS):
            if index['source_sha256'].get(str(path))!=pins[str(path)]:raise ValueError('Final index omits exact prior review authority')
        if current['analysis_sha256']!=terminal['output_sha256']or parent_pack['analysis_sha256']!=terminal['output_sha256']or index['analysis_sha256']!=terminal['output_sha256']:
            raise ValueError('Final qualitative artifacts differ from retained native authority')
        unchanged_pins(pins);state.update(status='prepared_pending_final_human_reviews',updated_utc=datetime.now(timezone.utc).isoformat(),
            analysis_sha256=terminal['output_sha256'],outputs={str(p):pins[str(p)]for p in(out_cases,out_parents,out_index)},condition_families=280,
            preserved_prior_cases=len(old_cases),preserved_prior_parent_cases=len(old_parents),counts=counts,
            limits=['Only full selected readouts and actual frozen parents are retained; unselected proposals support no method-level conclusion.',
                'Prior full contexts/official evidence preserved verbatim. Old-lineage-only content matches require fresh review.',
                'All four pending partitions, including zero-count partitions, remain explicit. No new calls, scores or qualitative claims.'])
        atomic(a.state,state);print(json.dumps({'status':state['status'],'outputs':state['outputs'],'counts':counts}),flush=True)
    except Exception as error:
        state.update(status='failed_pending_root_review',error=str(error),updated_utc=datetime.now(timezone.utc).isoformat());atomic(a.state,state);raise


if __name__=='__main__':main()
