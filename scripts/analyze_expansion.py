"""Source-checked exploratory bank/subcohort analysis; never dispatches inference.

Only terminal complete-family judges enter the report. Native endpoints are
rebuilt from original row counts, preserving the question/group unit and both
hallucination stages. Partial menus cannot acquire simultaneous headline CIs.
"""
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.expanded_statistics import analyze
from olens_improve.reporting import family_counts, original_grid_pairs
from expanded_cpu_cached import atomic, committed_lines, sha
from verify_expansion_judge_contracts import load_approved_runtime_pin, verify_judge_contract

def load(path):return json.loads(Path(path).read_text())

def runtime_authority(path):
    """Follow the original root-approved freeze through its exact signed report."""
    body=load(path);pins={str(path):sha(path)}
    if body['status']!='root_reviewed_derived_from_approved_pre_expansion_freeze':raise ValueError('Unreviewed runtime authority')
    for key in ('original_freeze','validation_report','runtime_contract'):
        entry=body[key]
        if sha(entry['path'])!=entry['sha256']:raise ValueError('Original runtime authority changed')
        pins[entry['path']]=entry['sha256']
    freeze=load(body['original_freeze']['path']);report=load(body['validation_report']['path']);contract=body['runtime_contract']
    if freeze['status']!='root_reviewed_frozen' or freeze['validation_evidence']['signed_report_path']!=body['validation_report']['path'] or freeze['validation_evidence']['signed_report_sha256']!=body['validation_report']['sha256']:raise ValueError('Runtime report is not bound by the original freeze')
    arms=[row for row in report['measurement']['conditions'] if row['condition']==contract['condition']]
    if len(arms)!=1 or arms[0]['source_sha256'].get(contract['path'])!=contract['sha256']:raise ValueError('Runtime contract is not bound by the signed report')
    return load_approved_runtime_pin(contract['path'],contract['sha256'],pointer=contract['hashes_pointer']),pins

def subsets(cells,pilot):
    cohort={'full':set(cells),'test':{cid for cid,c in cells.items() if c['split']=='test'},
            'development':{cid for cid,c in cells.items() if c['split']=='development'},'pilot':{c['cell_id'] for c in pilot['cells']}}
    if not all(s<=set(cells) for s in cohort.values()):raise ValueError('Foreign subcohort cell')
    for name in ('test','development'):
        selected={cells[cid]['item_id'] for cid in cohort[name]}
        if any(c['item_id'] in selected and cid not in cohort[name] for cid,c in cells.items()):raise ValueError('Subcohort splits an original question grid')
    return cohort

def filtered_result(result,family,own):
    items={c['item_id'] for c in own};sites={(c['item_id'],c['layer'],c['position']) for c in own}
    copy=dict(result)
    copy['rows']=[r for r in result['rows'] if ((str(r['id']),r['layer'],r['pos']) in sites
        if family in ('hallucination','role_bound_association') else str(r['id']) in items)]
    return copy

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--inventory-sha256',required=True);p.add_argument('--analysis',type=Path,default=Path('configs/expansion_analysis_v1.json'))
    p.add_argument('--judgments',type=Path,required=True);p.add_argument('--ready-directory',type=Path,action='append',required=True)
    p.add_argument('--runtime-authority',type=Path,default=Path('configs/expansion_runtime_authority_v1.json'))
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPUs required')
    implementation={str(Path(__file__)):sha(__file__),
        'src/olens_improve/expanded_statistics.py':sha('src/olens_improve/expanded_statistics.py'),
        'src/olens_improve/reporting.py':sha('src/olens_improve/reporting.py'),
        'scripts/verify_expansion_judge_contracts.py':sha('scripts/verify_expansion_judge_contracts.py')}
    if sha(a.inventory)!=a.inventory_sha256:raise ValueError('Inventory seal changed')
    inventory=load(a.inventory);analysis=load(a.analysis)
    if analysis['manifest_sha256']!=a.inventory_sha256 or analysis['status']!='frozen_before_new_judgments':raise ValueError('Analysis does not bind frozen inventory')
    fresh_path=Path(inventory['fresh_manifest']['path'])
    if sha(fresh_path)!=inventory['fresh_manifest']['sha256']:raise ValueError('Fresh capture manifest changed')
    cells={c['cell_id']:c for c in load(fresh_path)['cells']};pilot_path=Path('configs/splits_pilot_shared_v2.json');pilot=load(pilot_path);cohort=subsets(cells,pilot)
    runtime_hashes,runtime_pins=runtime_authority(a.runtime_authority)
    active={r['condition_id']:r for r in inventory['conditions'] if r['status'] not in ('exact_alias','obsolete_malformed_transport_diagnostic','computed_numerical_diagnostic_only')}
    outputs={};descriptors={};source_hashes={str(a.inventory):a.inventory_sha256,str(a.analysis):sha(a.analysis),str(fresh_path):sha(fresh_path),str(pilot_path):sha(pilot_path),**runtime_pins}
    for directory in a.ready_directory:
        for path in sorted(directory.glob('*.ready.json')):
            descriptor=load(path)
            if descriptor.get('ready') is not True or descriptor['inventory_sha256']!=a.inventory_sha256:raise ValueError('Unsealed ready artifact')
            source=Path(descriptor['selections']);manifest=Path(descriptor['manifest'])
            if sha(source)!=descriptor['selection_sha256'] or sha(manifest)!=descriptor['manifest_sha256']:raise ValueError('Published descriptor source changed')
            family=descriptor['family'];expected={cid for cid,c in cells.items() if c['family']==family}
            declared={(r['method'],r['n']) for r in descriptor['conditions']};seen=set()
            for row in committed_lines(source):
                cid=row['cell_id']
                if cid in seen or cid not in expected or any(row[k]!=cells[cid][k] for k in ('family','item_id','layer','position','split','activation_sha256')):raise ValueError('Ready output identity differs')
                seen.add(cid)
                for s in row['selections']:
                    key=f"{s['method']}-n{s['n']}"
                    if key not in active or (s['method'],s['n']) not in declared:raise ValueError('Undeclared condition output')
                    lookup=(key,family);outputs.setdefault(lookup,{})
                    reduced={k:s[k] for k in ('text','token_count','bullet_count')}
                    if not isinstance(reduced['text'],str) or any(not isinstance(reduced[k],int) or isinstance(reduced[k],bool) or reduced[k]<0 for k in ('token_count','bullet_count')):raise ValueError('Invalid output text/length')
                    if key!='raw_n1-n1' and (reduced['token_count']>256 or reduced['bullet_count']>4):raise ValueError('Ready output violates cap')
                    if cid in outputs[lookup] and outputs[lookup][cid]!=reduced:raise ValueError('Conflicting condition output')
                    outputs[lookup][cid]=reduced;descriptors[lookup]=descriptor
            if seen!=expected:raise ValueError('Published family grid incomplete')
            source_hashes[str(path)]=sha(path);source_hashes[str(source)]=descriptor['selection_sha256'];source_hashes[str(manifest)]=descriptor['manifest_sha256']
    cohorts={name:{'families':{},'lengths':{},'secondary':{},'rows':[]} for name in cohort};complete=[];missing=[]
    for condition in active:
        root=a.judgments/condition
        for family in inventory['families']:
            lookup=(condition,family);summary=root/f'{family}.summary.json';folder=root/family
            required=[summary,folder/'results.json',folder/'project_contract.json',root/f'{family}.readouts.jsonl']
            if lookup not in outputs or not all(path.exists() for path in required):
                missing.append({'condition':condition,'family':family,'reason':'missing_output' if lookup not in outputs else 'judgment_not_terminal'});continue
            summary_body=load(summary);contract=load(folder/'project_contract.json');result=load(folder/'results.json')
            descriptor=descriptors[lookup]
            verify_judge_contract(family=family,method=active[condition]['method'],n=active[condition]['n'],
                expected_cells=sum(c['family']==family for c in cells.values()),inventory_sha256=a.inventory_sha256,
                descriptor=descriptor,summary=summary_body,result=result,contract=contract,
                approved_runtime_source_hashes=runtime_hashes)
            if contract['partial_grid'] or contract.get('inventory_sha256')!=a.inventory_sha256 or contract['manifest_missing_cells']!=0:raise ValueError('Wrong judgment grid or authority')
            if contract.get('project_reasoning_effort')!='none' or contract.get('project_judge_model')!=('regex' if family=='multihop_mt' else 'gpt-6-luna'):raise ValueError('Changed judge contract')
            scientific=summary_body['condition'];descriptor=descriptors[lookup]
            if scientific['selection_sha256']!=descriptor['selection_sha256'] or scientific['inventory_sha256']!=a.inventory_sha256:raise ValueError('Judgment provenance differs from selected source')
            reads=list(committed_lines(root/f'{family}.readouts.jsonl'));family_cells=[c for c in cells.values() if c['family']==family]
            sites={(c['item_id'],c['layer'],c['position']):c['cell_id'] for c in family_cells}
            for row in reads:
                cid=sites[(str(row['id']),row['layer'],row['pos'])]
                if row['samples']!=[outputs[lookup][cid]['text']]:raise ValueError('Official judged text differs from saved output')
            metrics,coverage=family_counts(family,family_cells,reads,result)
            if coverage['missing_stage1'] or coverage['missing_stage2']:
                missing.append({'condition':condition,'family':family,'reason':'unjudged_or_missing_hall_stage2','coverage':coverage});continue
            # Independently reproduce the full-bank official endpoint before filtering old subsets.
            original_grid_pairs(family,metrics,result)
            complete.append({'condition':condition,'family':family,'coverage':coverage})
            for path in required:source_hashes[str(path)]=sha(path)
            for name,selected in cohort.items():
                own=[c for c in family_cells if c['cell_id'] in selected]
                if not own:continue
                items={c['item_id'] for c in own};ids={c['cell_id'] for c in own}
                chosen_reads=[r for r in reads if sites[(str(r['id']),r['layer'],r['pos'])] in ids]
                values,counts=family_counts(family,own,chosen_reads,filtered_result(result,family,own))
                native=values['contradiction_rate'] if family=='hallucination' else values['cell_recovery']
                if family!='hallucination' and name!='pilot':native={item:(int(pair[0]>0),1) for item,pair in native.items()}
                groups={c['item_id']:c['group_id'] for c in own}
                entry=cohorts[name]['families'].setdefault(family,{'conditions':{},'group_of':groups})
                if entry['group_of']!=groups:raise ValueError('Unpaired condition cohort')
                entry['conditions'][condition]=native
                lens=[outputs[lookup][cid] for cid in ids]
                cohorts[name]['lengths'].setdefault(condition,{})[family]={'outputs':len(lens),
                    'mean_qwen_tokens_all_intended':statistics.mean(s['token_count'] for s in lens),
                    'median_qwen_tokens_all_intended':statistics.median(s['token_count'] for s in lens),
                    'mean_bullets_all_intended':statistics.mean(s['bullet_count'] for s in lens)}
                secondary={metric:{'numerator':sum(pair[0] for pair in pairs.values()),'denominator':sum(pair[1] for pair in pairs.values())} for metric,pairs in values.items()}
                cohorts[name]['secondary'].setdefault(condition,{})[family]=secondary|{'coverage':counts}
    final={}
    for name,value in cohorts.items():
        families=value.pop('families')
        if not families:
            final[name]=value|{'comparisons':[],'status':'unmeasured','missing_comparisons':[]};continue
        measured=analyze(families,inventory['headline_comparison_family'],replicates=analysis['bootstrap_replicates'],seed=analysis['seed'])
        # The generic numerical routine accepts a subset of tasks; expansion's
        # declared family includes every task, so a absent family blocks joint CIs.
        absent=set(inventory['families'])-set(families)
        if absent:
            measured['comparison_family_complete']=False;measured['joint_critical_value']=None
            for row in measured['comparisons']:row['simultaneous_ci95_delta']=None
            measured['missing_comparisons'].extend({'family':family,**pair} for family in sorted(absent) for pair in inventory['headline_comparison_family'])
        measured['declared_contrasts']=4*len(inventory['headline_comparison_family'])
        rows=[]
        for family,arms in measured['conditions'].items():
            endpoint=('partial_grid_contradiction_rate' if name=='pilot' else 'original_grid_contradiction_rate') if family=='hallucination' else ('per_activation_recovery' if name=='pilot' else 'original_grid_item_pass_rate')
            for condition,metric in arms.items():rows.append({'condition':condition,'family':family,'metric':metric|{'name':endpoint},'exploratory':True,'partial_grid':name=='pilot'})
        final[name]=value|{'rows':rows,'comparisons':measured['comparisons'],'missing_comparisons':measured['missing_comparisons'],
            'comparison_family_complete':measured['comparison_family_complete'],'joint_critical_value':measured['joint_critical_value'],
            'declared_contrasts':measured['declared_contrasts'],'bootstrap_replicates':measured['bootstrap_replicates'],
            'effective_non_degenerate_contrasts':measured['effective_non_degenerate_contrasts'],
            'joint_interval_contrasts':measured['joint_interval_contrasts'] if not absent else 0,
            'status':'complete' if measured['comparison_family_complete'] else 'partial'}
    for path,expected in (source_hashes|implementation).items():
        if sha(path)!=expected:raise ValueError('Analysis source changed during extraction')
    payload={'status':'complete_exploratory' if not missing else 'partial_exploratory','updated_utc':datetime.now(timezone.utc).isoformat(),
        'manifest_sha256':a.inventory_sha256,'cohorts':final,'complete_condition_families':complete,'missing_condition_families':missing,
        'source_sha256':source_hashes,'implementation_sha256':implementation,
        'limits':['All questions previously inspected; expansion remains exploratory.','The old TEST subset is an exploratory subcohort, not a fresh test.',
            'Native family endpoints differ; no pooled accuracy.','Pilot recovery remains a partial-grid cell endpoint.',
            'Simultaneous intervals require the full declared four-task contrast family; pointwise uncertainty remains visible.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);atomic(a.output,payload)
    print(json.dumps({'output':str(a.output),'status':payload['status'],'complete_condition_families':len(complete),'missing_condition_families':len(missing)}))

if __name__=='__main__':main()
