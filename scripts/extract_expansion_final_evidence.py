"""Copy final declared evidence with exact source pointers; no statistics or prose."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

SEAL='753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8'
DRAFT='d1889a8c31c5422b5805577cf00e8df9b353e81af9ac84a79a72a5c9bb17b2f7'
FAMILIES=('hallucination','multihop_mt','chain_intermediates','role_bound_association')

def require(value,message):
    if not value:raise ValueError(message)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1048576),b''):h.update(b)
    return h.hexdigest()

def indexed(rows,identity):
    result={}
    for i,row in enumerate(rows):
        key=identity(row);require(key not in result,'Duplicate source identity');result[key]=(i,row)
    return result

def copied(value,pointer):return {'source_array_pointer':pointer,'record':deepcopy(value)}

def extract(native,numeric,inventory,draft):
    active={x['condition_id'] for x in inventory['conditions'] if x['status'] in ('cached_selector_full_bank','scheduled_full_bank')}
    scope={(c,f) for c in active for f in FAMILIES};full=native['cohorts']['full']
    require(len(active)==70 and native['status']=='complete_exploratory' and not native['missing_condition_families']
            and len(native['complete_condition_families'])==280,'Native final70x4 incomplete')
    metrics=indexed(full['rows'],lambda x:(x['condition'],x['family']))
    fits=indexed(numeric['rows'],lambda x:(x['condition'],x['family']))
    require(set(metrics)==set(fits)==scope and not any(x['missing_selection_sites']for _,x in fits.values()),'Final280 scope differs')
    declared={(f,x['condition'],x['reference'],x['role'])for f in FAMILIES for x in inventory['headline_comparison_family']}
    pairs=indexed(full['comparisons'],lambda x:(x['family'],x['condition'],x['reference'],x['role']))
    require(len(declared)==496 and set(pairs)==declared and full['declared_contrasts']==496
            and full['comparison_family_complete'] is True and not full['missing_comparisons']
            and full['bootstrap_replicates']==10000,'Frozen496 final comparison family differs')
    require(numeric['diagnostic_version']==5 and numeric['solver']=='scipy_exact'
            and numeric['objective']=='1-squared_residual/squared_target','Final reconstruction authority differs')
    def fit_summary(condition,family):
        i,row=fits[condition,family]
        # Retain every absolute/mask/warning field; paired records copied separately.
        return copied({k:v for k,v in row.items()if k!='parent_comparisons'},f'/rows/{i}')
    def fit_pair(condition,reference,family,appropriate_kind=None):
        i,row=fits[condition,family]
        matches=[(j,p)for j,p in enumerate(row['parent_comparisons'])if p['reference']==reference]
        require(len({p['kind']for _,p in matches})==len(matches),'Ambiguous same-kind recorded reconstruction reference')
        all_records=[copied(p,f'/rows/{i}/parent_comparisons/{j}')for j,p in matches]
        if not matches:return {'status':'not_recorded','condition':condition,'reference':reference,'family':family,
                               'record':None,'all_matching_records':[],'other_kind_records':[]}
        if appropriate_kind is not None:
            eligible=[x for x in matches if x[1]['kind']==appropriate_kind]
            require(len(eligible)==1,'Appropriate recorded comparison kind absent')
            policy='named_appropriate_diagnostic_kind'
        else:
            eligible=[x for x in matches if x[1]['kind']=='frozen_parent']
            if eligible:policy='named_frozen_parent'
            else:
                require(len(matches)==1,'No frozen parent; multiple recorded comparison kinds')
                eligible=matches;policy='unique_recorded_non_frozen_kind'
        j,p=eligible[0]
        return {'status':'recorded','selected_kind':p['kind'],'selection_policy':policy,
                **copied(p,f'/rows/{i}/parent_comparisons/{j}'), 'all_matching_records':all_records,
                'other_kind_records':[x for x in all_records if x['source_array_pointer']!=f'/rows/{i}/parent_comparisons/{j}']}
    approaches=draft['presentation']['approaches'];require(len(approaches)==7,'Seven draft approaches required')
    out=[]
    for approach,selection in approaches.items():
        contrast=selection['contrast'];c,r,role=[contrast[k]for k in ('condition','reference','role')]
        for family in FAMILIES:
            require((family,c,r,role)in declared,'Primary contrast is not declared')
            ci,condition=metrics[c,family];ri,reference=metrics[r,family];pi,pair=pairs[family,c,r,role]
            out.append({'approach':approach,'family':family,'declared_contrast':deepcopy(contrast),
                'native_condition':copied(condition,f'/cohorts/full/rows/{ci}'),
                'native_reference':copied(reference,f'/cohorts/full/rows/{ri}'),
                'native_paired_comparison':copied(pair,f'/cohorts/full/comparisons/{pi}'),
                'reconstruction_condition':fit_summary(c,family),'reconstruction_reference':fit_summary(r,family),
                'reconstruction_recorded_common_mask_comparison':fit_pair(c,r,family)})
    extras=[]
    for c,r,kind in (('best_n_exact-n32','best_n_exact-n16','sampling_prefix_diagnostic'),
                ('random_complete-n32','random_complete-n16','sampling_prefix_diagnostic'),
                ('pooled_greedy_swap-n32','pooled_greedy_swap-n16','frozen_parent'),
                ('pooled_greedy_swap-n32','best_n_exact-n32','pooling_vs_best_complete_diagnostic')):
        for family in FAMILIES:
            record=fit_pair(c,r,family,kind)
            if record['status']=='recorded':extras.append({'condition':c,'reference':r,'family':family,'comparison':record,
                'condition_absolute':fit_summary(c,family),'reference_absolute':fit_summary(r,family)})
    return {'primary_comparisons':out,'existing_scaling_and_pool_fit_records':extras,
        'reconstruction_contract':deepcopy({k:numeric[k]for k in ('diagnostic_version','objective','solver','vector_contract_sha256',
            'normalization','site_change_equivalence_tolerance','limits','implementation_sha256')if k in numeric}),
        'native_joint_family_metadata':{'source_pointer':'/cohorts/full',
            'record':deepcopy({k:v for k,v in full.items()if k not in ('rows','comparisons','lengths','secondary')})}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('native','native-state','native-receipt','reconstruction','reconstruction-state','reconstruction-receipt','inventory','draft','output'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('native','native-state','reconstruction','reconstruction-state'):p.add_argument('--'+name+'-sha256',required=True)
    a=p.parse_args();require(os.getenv('SLURM_JOB_ID')in('25536417','25536291'),'Use existing owned CPU at terminal boundary')
    require(not a.output.exists(),'Use absent immutable extraction path');pins={}
    def read(path,expected):
        require(sha(path)==expected,'Retained source SHA differs: '+str(path));pins[str(path)]=expected
        return json.loads(path.read_text())
    n=read(a.native_state,a.native_state_sha256);r=read(a.reconstruction_state,a.reconstruction_state_sha256)
    for state,path,digest in ((n,a.native,a.native_sha256),(r,a.reconstruction,a.reconstruction_sha256)):
        require(state['status']=='complete_pending_root_review'and state['output_sha256']==digest
                and Path(state['output']).resolve()==path.resolve(),'Terminal gate source differs')
    require(n['scientific_inputs_validated_complete']is True,'Native validation incomplete')
    native=read(a.native,a.native_sha256);numeric=read(a.reconstruction,a.reconstruction_sha256)
    nr=read(a.native_receipt,n['receipt_sha256']);rr=read(a.reconstruction_receipt,r['snapshot_receipt_sha256'])
    require(nr['status']=='sealed_all280_terminal_inputs'and nr['descriptor_count']==32 and nr['condition_family_count']==280,
            'Canonical native receipt differs')
    require(rr['quality_analysis_sha256']==numeric['quality_analysis_sha256']==a.native_sha256,'Final fit/native linkage differs')
    inventory=read(a.inventory,SEAL);draft=read(a.draft,DRAFT)
    require(native['manifest_sha256']==numeric['manifest_sha256']==SEAL,'Final manifest differs')
    out=extract(native,numeric,inventory,draft)
    out.update(status='machine_extraction_pending_human_interpretation',created_utc=datetime.now(timezone.utc).isoformat(),
        native_source={'path':str(a.native),'sha256':a.native_sha256},reconstruction_source={'path':str(a.reconstruction),'sha256':a.reconstruction_sha256},
        manifest_sha256=SEAL,source_sha256=pins,new_statistics=0,new_fits=0,
        limits=['Copied records only; raw fractions, pp fields, valid/common-mask coverage, group counts, nulls and warnings remain unchanged.',
                'A missing recorded fit comparison remains not_recorded; no subtraction of absolute means on different masks.',
                'Complete source family does not imply defined/nondegenerate intervals or certainty. No human interpretation or efficacy claim is authorized.'])
    pins[str(Path(__file__))]=sha(__file__)
    require(all(sha(path)==digest for path,digest in pins.items()),'Sources changed during extraction')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x')as stream:stream.write(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'output':str(a.output),'sha256':sha(a.output),'primary_records':len(out['primary_comparisons'])}))

if __name__=='__main__':main()
