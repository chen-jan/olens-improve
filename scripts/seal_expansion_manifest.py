"""Seal the finite exploratory expansion menu without reading new outcomes."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

D = Path('${OLENS_DATA_ROOT}')
F = Path('${OLENS_COMPUTE_ROOT}')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source(path, expected=None):
    path = Path(path)
    return {'path': str(path), 'sha256': expected or sha(path),
            'hash_status': 'terminal_receipt_pending_stream_verification' if expected else 'verified_now'}

def condition_id(method, n):
    return f'{method}-n{n}'

def parents(method, n):
    if method in ('raw_n1', 'capped_n1'): return [] if method == 'raw_n1' else ['raw_n1-n1']
    if method.startswith(('prune_', 'random_delete_matched_')):
        return ['best_n_exact-n32' if '_a32_' in method else 'capped_n1-n1']
    if '_then_prune_' in method or '_random_delete_matched_' in method:
        return [condition_id(method.split('_then_prune_')[0].split('_random_delete_matched_')[0], n)]
    if method.startswith('editing_round'): return ['best_n_exact-n32', 'pooled_greedy_swap-n32']
    if method.startswith('pooled_specificity'): return ['pooled_greedy_swap-n32','best_n_specificity_mean-n32']
    if method.startswith('pooling_exact_support'): return ['pooled_greedy_swap-n16','exact_support_only-n16']
    if method.endswith('abstain_nonpositive'): return ['best_n_specificity_mean-n32']
    if method.startswith('consensus_semantic'): return ['consensus_exact_support0-n16']
    return ['capped_n1-n1']

def stream(method):
    if method.startswith('consensus_semantic'): return 'semantic_helpers_then_cpu'
    if method.startswith('editing_'): return 'editing_helpers_gpu_encoding_then_cpu'
    if 'likelihood' in method: return 'shared_gpu_likelihood_then_cpu'
    return 'cpu_cache_only'

def main():
    output = Path('configs/expansion_manifest_v1.json')
    if output.exists(): raise FileExistsError('The sealed menu is immutable; use a new version')
    menus = [Path(f'configs/{n}.json') for n in ('conditions_full_dev_v1','conditions_full_dev_combinations_v1','reporting_pilot_v2')]
    recorded = {}
    for path in menus:
        for row in json.loads(path.read_text()):
            key=(row['method'],row['n']); recorded.setdefault(key, {'method':key[0],'n':key[1],'recorded_sources':[]})
            recorded[key]['recorded_sources'].append(source(path))
    stages = {}
    original40 = None
    for stage, sub, cohort, cache in [
        ('development','development-full-grid-v4','development-full-grid-v2','shared-global-v1/a451cf49d28ac7447722'),
        ('validation','validation-full-grid-v1','validation-full-grid-blind-v1','validation-catalog-v1'),
        ('test','test-full-grid-v1','test-full-grid-analysis-v1','test-catalog-v1')]:
        root=D/'selections'/sub
        config_path=root/'shard-0/config.json'; config=json.loads(config_path.read_text())
        merge=json.loads((root/'merged/merge.json').read_text())
        if original40 is None: original40=merge['methods']
        elif original40 != merge['methods']: raise ValueError('Stage menus differ')
        stages[stage]={'cohort':source(Path('configs')/f'{cohort}.json'),
                       'selectors':source(root/'merged/selections.jsonl',merge['selection_sha256']),
                       'selectors_receipt':source(root/'merged/merge.json'),
                       'selector_config':source(config_path),
                       'samples':[{'path':r['path'],'sha256':r['sha256']} for r in config['source_inputs']],
                       'vector_cache':str(F/'vectors'/cache), 'cells':merge['cells']}
    for method,n in original40:
        recorded.setdefault((method,n),{'method':method,'n':n,'recorded_sources':[stages['development']['selector_config']],
            'individually_added_computed_condition':True})
    rows=[]
    known40={tuple(k) for k in original40}
    final12={tuple((r['method'],r['n'])) for r in json.loads(Path('configs/conditions_test_final_v2.json').read_text())}
    for (method,n),row in recorded.items():
        status='cached_selector_full_bank' if (method,n) in known40 else 'scheduled_full_bank'
        if 'semantic_v4' in method: status='obsolete_malformed_transport_diagnostic'
        if method=='pooling_exact_support_lambda0': status='exact_alias'
        if method=='best_n_released80': status='computed_numerical_diagnostic_only'
        row.update({'condition_id':condition_id(method,n),'status':status,'stream':stream(method),
            'parent_condition_ids':parents(method,n),'candidate_budget':n,'new_olens_samples':0,
            'max_bullets':4,'max_qwen_tokens':256,'raw_baseline_cap_exemption':method=='raw_n1',
            'judgment_reuse':'Exact request identity only; preserve original prompts and both hallucination stages',
            'existing_full_bank_judged':(method,n) in final12,
            'required_artifacts':['original_cell_samples','source_bullet_vectors','frozen_cell_activation'],
            'thresholds':{},'control_bank_identity':'development-matched-controls-v2-metadata-v1' if 'specificity' in method or 'likelihood' in method else None})
        if status=='exact_alias': row['alias_of']='pooled_greedy_swap-n16'
        if status=='obsolete_malformed_transport_diagnostic': row['reason']='Historical malformed helper local-ID transport; retain historical results, no new paid replay'
        if method.startswith('prune_loo_') or '_then_prune_' in method or '_random_delete_matched_' in method or method.startswith('random_delete_matched_'):
            row['thresholds']['maximum_sequential_target_fve_loss']=float(method.rsplit('_',1)[1])
        if method.startswith('prune_coefficient_'): row['thresholds']['relative_coefficient_cutoff']=float(method.rsplit('_',1)[1])
        if 'consensus_' in method:
            row['thresholds']['support_fraction']=float(method.split('support',1)[1].split('_',1)[0])
            row['thresholds'].update({'compatibility_filter':'compaton' in method,'contradiction_veto':'vetoon' in method})
            if 'semantic_v5' in method:
                row['required_artifacts']+=['shared_frozen_pair_proposal','equivalence_labels','compatibility_labels_unknown_preserved']
                row['helper_reasoning_effort']='medium' if '_medium_' in method else 'none'
        if method.startswith('pooling_exact_support_lambda'): row['thresholds']['support_coefficient']=float(method.split('lambda')[1])
        if method.endswith('abstain_nonpositive'): row['thresholds']['abstain_when_specificity_lte']=0
        rows.append(row)
    controls_path=D/'manifests/development-matched-controls-v2-metadata-v1.json'
    controls=json.loads(controls_path.read_text())
    fresh_path=F/'activations/core-v1/fresh_manifest_v2.json'
    fresh=json.loads(fresh_path.read_text()); cells=fresh['cells']
    ids={c['cell_id'] for c in cells}
    frozen={cid:controls['control_cell_ids_by_target'][cid][:2] for cid in sorted(ids)}
    if len(ids)!=19435 or any(len(v)!=2 for v in frozen.values()): raise ValueError('Wrong fixed cohort or insufficient controls')
    likelihood={'schema_version':1,'status':'sealed','source_controls':source(controls_path),
        'policy':'First two original frozen donor IDs; DEV-only, matched family/layer/read-position kind, exclude related target group',
        'control_cell_ids_by_target':frozen,'control_bank':controls['control_bank']}
    likelihood_path=Path('configs/expansion_likelihood_controls_v1.json')
    likelihood_path.write_text(json.dumps(likelihood,separators=(',',':'))+'\n')
    active=[r for r in rows if r['status'] not in ('obsolete_malformed_transport_diagnostic','exact_alias','computed_numerical_diagnostic_only')]
    contrast=[]
    for row in active:
        cid=row['condition_id']
        if cid not in ('raw_n1-n1','capped_n1-n1'):
            contrast.append({'condition':cid,'reference':'capped_n1-n1','role':'headline_baseline'})
        for parent in row['parent_condition_ids']:
            if parent != 'capped_n1-n1' and parent != cid: contrast.append({'condition':cid,'reference':parent,'role':'component_parent'})
    # Explicit shortening comparisons complement the component-off parent.
    for row in active:
        method=row['method']; control=None
        if method.startswith('prune_loo_'): control=method.replace('prune_loo_','random_delete_matched_',1)
        elif '_then_prune_' in method: control=method.replace('_then_prune_','_random_delete_matched_')
        if control and (control,row['n']) in recorded: contrast.append({'condition':row['condition_id'],'reference':condition_id(control,row['n']),'role':'matched_deletion'})
    manifest={'schema_version':1,'status':'sealed','sealed_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'exploratory_full_four_family_bank; all469questions previously inspected; preserve original TEST study separately',
        'expected':{'items':469,'cells':19435,'samples':621920},'artifact_root':str(D/'expansion-v1'),
        'families':['hallucination','multihop_mt','chain_intermediates','role_bound_association'],
        'family_group_counts':{'hallucination':149,'multihop_mt':94,'chain_intermediates':42,'role_bound_association':50},
        'source_menus':[source(p) for p in menus], 'stages':stages,'fresh_manifest':source(fresh_path),
        'control_bank':source(controls_path),'likelihood_controls':source(likelihood_path),
        'vector_contract':config['vector_contract'],'conditions':rows,'active_condition_count':len(active),
        'status_counts':dict(Counter(r['status'] for r in rows)),
        'headline_comparison_family':contrast,'multiplicity_policy':'Paired whole-group tests; Holm over declared comparisons; simultaneous intervals separately validated',
        'invariants':['Maximum32original samples shared percell','A1 scoring eligibility differs from cappedN1',
           'Whole source bullets, fourbullets/256tokens; raw released baseline exemption retained',
           'Natural pooled lengths; no new baseline-length or random-pooling lengthmatching',
           'No independent readers or new semantic thresholds','Missing compatibility labels remain unknown',
           'No gold/context/judge outcomes in inference selection','No unrestricted crossproduct; weak/adverse findings retained'],
        'code_sources':{str(p):sha(p) for p in [Path(__file__),Path('src/olens_improve/selection.py'),Path('src/olens_improve/reconstruction.py'),Path('scripts/compare_selectors.py'),Path('scripts/combine_pruning.py'),Path('scripts/combine_support_pooling.py'),Path('scripts/combine_specificity_pooling.py')]}}
    output.write_text(json.dumps(manifest,indent=2)+'\n')
    Path('configs/conditions_expansion_v1.json').write_text(json.dumps([{'method':r['method'],'n':r['n']} for r in active],indent=2)+'\n')
    Path('configs/expansion_manifest_v1.sha256').write_text(sha(output)+'  '+str(output)+'\n')
    print(json.dumps({'manifest':str(output),'sha256':sha(output),'status_counts':manifest['status_counts'],'active_conditions':len(active)}))

if __name__=='__main__': main()
