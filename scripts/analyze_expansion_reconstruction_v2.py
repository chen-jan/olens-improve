"""Source-bound secondary FVE/length diagnostics; never select or judge."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.reconstruction_diagnostics_v2 import paired_fit_change, grouped_fit_summary
from expanded_cpu_cached import atomic, committed_lines, sha

ACTIVE_STATUSES = {'cached_selector_full_bank', 'scheduled_full_bank'}


def active_conditions(inventory):
    return {c['condition_id']: c for c in inventory['conditions'] if c['status'] in ACTIVE_STATUSES}


def text_sha(text): return hashlib.sha256(text.encode()).hexdigest()


def saved_fit(selection):
    if selection['method']=='raw_n1': return None,'unavailable_for_unmodified_raw_text'
    fit = (selection.get('fits') or {}).get('exact')
    if fit is None:
        scalar = (selection.get('fits') or {}).get('scipy_exact')
        if scalar is not None: fit={'fve':scalar,'solver':'scipy_exact'}
    if fit is None: return None, selection.get('fits_scope') or 'saved_fit_unavailable'
    if fit.get('solver')!='scipy_exact': raise ValueError('Incompatible saved NNLS solver')
    value = fit['fve']
    if not isinstance(value,(float,int)) or isinstance(value,bool) or not math.isfinite(value): raise ValueError('Invalid FVE')
    if 'atom_ids' in fit and list(fit['atom_ids']) != selection['phrase_ids']: raise ValueError('Fit atoms differ from emitted atoms')
    if 'coefficients' in fit and len(fit['coefficients']) != len(fit['atom_ids']): raise ValueError('Fit coefficient dimensions differ')
    if not selection['text'].strip() and abs(value)>1e-8: raise ValueError('Nonzero explicit empty fit')
    scope=selection.get('fits_scope','emitted_bullets')
    if scope not in ('emitted_bullets','exact_emitted_capped_bullets'): raise ValueError('Incompatible fit text scope')
    return float(value),'saved_exact_fit' if selection['text'].strip() else 'explicit_empty_fit_zero'


def references(condition, frozen):
    result=[{'reference':p,'kind':'frozen_parent'} for p in frozen]
    method,n=condition.rsplit('-n',1);n=int(n)
    if method in ('best_n_exact','random_complete') and n>1:
        result.append({'reference':f'{method}-n{n//2}','kind':'sampling_prefix_diagnostic'})
    if method.startswith('pooled_') or method.startswith('pooling_'):
        result.append({'reference':f'best_n_exact-n{n}','kind':'pooling_vs_best_complete_diagnostic'})
    if method.startswith('editing_round'):
        result.extend({'reference':p,'kind':'editor_initial_reference'} for p in ('best_n_exact-n32','pooled_greedy_swap-n32'))
        if method=='editing_round2':result.append({'reference':'editing_round1-n32','kind':'editor_previous_round_diagnostic'})
    return list({(r['reference'],r['kind']):r for r in result}.values())


def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--inventory-sha256',required=True);p.add_argument('--ready-directory',type=Path,action='append',required=True)
    p.add_argument('--replay-directory',type=Path,action='append',default=[])
    p.add_argument('--editing-scores-root',type=Path,default=Path('${OLENS_DATA_ROOT}/expansion-v1/editing-scores'))
    p.add_argument('--quality-analysis',type=Path,required=True);p.add_argument('--quality-analysis-sha256',required=True)
    p.add_argument('--descriptor-snapshot-receipt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU required')
    if a.output.exists():raise FileExistsError('Use new immutable diagnostic artifact')
    if sha(a.inventory)!=a.inventory_sha256 or sha(a.quality_analysis)!=a.quality_analysis_sha256:raise ValueError('Diagnostic authority changed')
    implementation={str(path):sha(path) for path in (Path(__file__),Path('src/olens_improve/reconstruction_diagnostics_v2.py'),
        Path('src/olens_improve/reconstruction.py'),Path('src/olens_improve/selection.py'))}
    inventory=json.loads(a.inventory.read_text());quality=json.loads(a.quality_analysis.read_text())
    if quality['manifest_sha256']!=a.inventory_sha256:raise ValueError('Quality source uses different expansion')
    pins=dict(quality['source_sha256']);pins[str(a.inventory)]=a.inventory_sha256;pins[str(a.quality_analysis)]=a.quality_analysis_sha256
    fresh=Path(inventory['fresh_manifest']['path'])
    if sha(fresh)!=inventory['fresh_manifest']['sha256']:raise ValueError('Fresh cohort changed')
    pins[str(fresh)]=sha(fresh);cells={c['cell_id']:c for c in json.loads(fresh.read_text())['cells']}
    conditions=active_conditions(inventory);outputs={};values={};fit_sources=set();fit_contracts=[];selection_folders=set()
    if len(conditions)!=70:raise ValueError('Active diagnostic menu differs from frozen 70 settings')
    def pin(path,expected=None):
        path=str(path);actual=sha(path)
        if expected is not None and expected!=actual:raise ValueError(f'Changed diagnostic source: {path}')
        if path in pins and pins[path]!=actual:raise ValueError('Conflicting source identity')
        pins[path]=actual
    snapshot=json.loads(a.descriptor_snapshot_receipt.read_text());pin(a.descriptor_snapshot_receipt)
    if snapshot['manifest_sha256']!=a.inventory_sha256 or snapshot['quality_analysis_sha256']!=a.quality_analysis_sha256:raise ValueError('Descriptor snapshot authority differs')
    snapshot_paths=set()
    for source in snapshot['sources']:
        pin(source['path'],source['sha256']);pin(source['snapshot'],source['sha256']);snapshot_paths.add(str(Path(source['snapshot']).resolve()))
    discovered={str(p.resolve()) for directory in a.ready_directory for p in directory.glob('*.ready.json')}
    if discovered!=snapshot_paths:raise ValueError('Diagnostic descriptor menu differs from frozen snapshot')
    for directory in a.ready_directory:
        for ready in sorted(directory.glob('*.ready.json')):
            d=json.loads(ready.read_text());family=d['family']
            if d.get('ready') is not True or d['inventory_sha256']!=a.inventory_sha256:raise ValueError('Unsealed selection descriptor')
            pin(ready);pin(d['manifest'],d['manifest_sha256']);pin(d['selections'],d['selection_sha256'])
            selection_folders.add(Path(d['selections']).parent)
            expected={cid for cid,c in cells.items() if c['family']==family};seen=set()
            for row in committed_lines(d['selections']):
                cid=row['cell_id'];cell=cells[cid]
                if cid in seen or any(row[k]!=cell[k] for k in ('family','item_id','layer','position','split','activation_sha256')):raise ValueError('Chosen diagnostic grid identity differs')
                seen.add(cid)
                for s in row['selections']:
                    condition=f'{s["method"]}-n{s["n"]}'
                    if condition not in conditions:raise ValueError('Foreign or inactive diagnostic condition')
                    key=condition,cid;compact={'text_sha256':text_sha(s['text']),'token_count':s['token_count'],'bullet_count':s['bullet_count']}
                    if key in outputs and outputs[key]!=compact:raise ValueError('Conflicting chosen output')
                    outputs[key]=compact
                    if s.get('fits') is not None and not s['method'].startswith('editing_round'):
                        fve,status=saved_fit(s);values[key]={'fve':fve,'status':status}
            if seen!=expected:raise ValueError('Diagnostic selected cohort incomplete')
            for source in d.get('source_parents',[]):
                pin(source['path'],source['sha256'])
                if source['path'].endswith('.jsonl'):fit_sources.add(source['path'])
    # Historical configuration establishes comparability, not released80 fields.
    for stage,stage_spec in inventory['stages'].items():
        config=stage_spec['selector_config'];pin(config['path'],config['sha256'])
        contract=json.loads(Path(config['path']).read_text())
        if contract['primary_solver']!='scipy_exact' or contract['vector_contract']!=inventory['vector_contract']:raise ValueError('Original fit contract changed')
        fit_contracts.append({'stage':stage,'path':config['path'],'sha256':config['sha256'],'primary_solver':'scipy_exact'})
    original_fit_sources={stage['selectors']['path'] for stage in inventory['stages'].values()}
    def retain(row,s,source=None):
        condition=f'{s["method"]}-n{s["n"]}';cid=row['cell_id'];key=condition,cid
        if key not in outputs:return
        if conditions[condition]['status']=='cached_selector_full_bank' and source not in original_fit_sources:return
        cell=cells[cid]
        if any(row[k]!=cell[k] for k in ('family','item_id','layer','position','split','activation_sha256')):raise ValueError('Fit source identity differs')
        if outputs[key]!={ 'text_sha256':text_sha(s['text']),'token_count':s['token_count'],'bullet_count':s['bullet_count']}:raise ValueError('Saved FVE belongs to different emitted output')
        fve,status=saved_fit(s);value={'fve':fve,'status':status}
        if key in values and values[key]!=value:raise ValueError(f'Conflicting comparable fit {key}: {values[key]} vs {value} from {source}')
        values[key]=value
    for source in sorted(fit_sources):
        for row in committed_lines(source):
            for s in row.get('selections',[]):retain(row,s,source)
            # Reproduce only the recorded zero-specificity abstention projection.
            parent=next((s for s in row.get('selections',[]) if s['method']=='best_n_specificity_mean' and s['n']==32),None)
            if source in original_fit_sources and parent is not None and 'score' in parent.get('extra',{}) and ('best_n_specificity_mean_abstain_nonpositive-n32',row['cell_id']) in outputs:
                derived=dict(parent,method='best_n_specificity_mean_abstain_nonpositive')
                if parent['extra']['score']<=0:
                    derived.update(text='',phrase_ids=[],token_count=0,bullet_count=0,fits_scope='emitted_bullets',
                        fits={'exact':{'fve':0.,'solver':'scipy_exact','atom_ids':[],'coefficients':[]}})
                retain(row,derived,source)
    for terminal_path in sorted(a.editing_scores_root.glob('round*/*/status.json')):
        terminal=json.loads(terminal_path.read_text())
        if terminal.get('status')!='complete':continue
        folder=terminal_path.parent;spec=folder/'spec.json';journal=folder/'scored_candidates.jsonl'
        contract=json.loads(spec.read_text());number=contract['round'];family=folder.name
        if contract['sealed_manifest_sha256']!=a.inventory_sha256 or contract['fresh_manifest_sha256']!=inventory['fresh_manifest']['sha256'] or contract['vector_contract']!=inventory['vector_contract']:raise ValueError('Edited fit authority differs')
        if contract['acceptance_objective']!='exact_joint_nnls_fve_only' or contract['all_initial_and_previous_proposals_retained'] is not True:raise ValueError('Edited fit objective differs')
        pin(terminal_path);pin(spec);pin(journal);seen=set();condition=f'editing_round{number}-n32'
        for event in committed_lines(journal):
            cid=event['cell_id'];cell=cells[cid];key=condition,cid
            if cid in seen or event['spec_sha256']!=pins[str(spec)] or any(event[k]!=cell[k] for k in ('family','item_id','layer','position','split','activation_sha256')):raise ValueError('Edited score identity changed')
            seen.add(cid)
            if key not in outputs:continue
            best=event['best']
            if best is None:raise ValueError('Empty scored candidate union')
            s={'method':f'editing_round{number}','n':32,'text':best['text'],'token_count':best['token_count'],
                'bullet_count':best['bullet_count'],'fits':{'scipy_exact':best['exact_fve']}}
            retain(event,s)
        if seen!={cid for cid,c in cells.items() if c['family']==family}:raise ValueError('Edited fit cohort incomplete')
    # New editor exports may retain only scalar fits; prune projections keep their full journal separately.
    for directory in selection_folders:
        for family in inventory['families']:
            spec=directory/f'{family}.spec.json';journal=directory/f'{family}.journal.jsonl';status=directory/f'{family}.status.json'
            if spec.exists() and journal.exists() and status.exists():
                terminal=json.loads(status.read_text())
                if terminal.get('status')!='complete':continue
                contract=json.loads(spec.read_text())
                if contract['inventory_sha256']!=a.inventory_sha256 or contract['fresh_manifest_sha256']!=inventory['fresh_manifest']['sha256'] or contract['vector_contract_sha256']!=inventory['vector_contract']['sha256'] or contract['family']!=family or contract['parent_condition_id']!='editing_round2-n32' or contract['solver']!='scipy_exact' or contract['objective']!='1-squared_residual/squared_target':raise ValueError('Edited pruning fit authority differs')
                if contract['thresholds']!=[.001,.005] or contract['random_seed_contract']!='combination_random_delete_v1':raise ValueError('Edited pruning policy differs')
                for path,value in contract['code_sha256'].items():pin(path,value)
                parent_folder=a.editing_scores_root/'round2'/family
                pin(parent_folder/'spec.json',contract['editor_spec_sha256']);pin(parent_folder/'status.json',contract['terminal_sha256']);pin(parent_folder/'scored_candidates.jsonl',contract['editing_source_sha256'])
                pin(spec);pin(status);pin(journal,terminal['journal_sha256']);seen=set()
                for row in committed_lines(journal):
                    if row['cell_id'] in seen or row['inventory_sha256']!=a.inventory_sha256:raise ValueError('Duplicate/foreign edited pruning fit')
                    seen.add(row['cell_id'])
                    for s in row['selections']:retain(row,s,str(journal))
                expected={cid for cid,c in cells.items() if c['family']==family}
                if seen!=expected or terminal['completed_cells']!=len(expected) or terminal['expected_cells']!=len(expected):raise ValueError('Edited pruning terminal coverage differs')
    replay_audits=[]
    for directory in a.replay_directory:
        status=directory/'status.json';spec=directory/'spec.json';journal=directory/'fits.jsonl'
        if not status.exists():continue
        terminal=json.loads(status.read_text());contract=json.loads(spec.read_text())
        if terminal.get('status')!='complete' or contract['fixture']:continue
        if contract['inventory_sha256']!=a.inventory_sha256 or contract['solver']!='scipy_exact' or contract['vector_contract']!=inventory['vector_contract']:raise ValueError('Replay objective differs')
        pin(status);pin(spec);pin(journal,terminal['fits_sha256'])
        for path,value in terminal['source_sha256'].items():pin(path,value)
        if terminal['implementation_sha256']!=contract['implementation_sha256']:raise ValueError('Replay implementation receipt differs')
        for path,value in terminal['implementation_sha256'].items():pin(path,value)
        seen=set();maximum_parent_delta=0.
        for row in committed_lines(journal):
            cid=row['cell_id'];cell=cells[cid]
            if cid in seen or row['spec_sha256']!=pins[str(spec)] or row['inventory_sha256']!=a.inventory_sha256 or any(row[k]!=cell[k] for k in ('family','item_id','layer','position','split','activation_sha256')):raise ValueError('Replayed target differs')
            seen.add(cid)
            parent=values.get(('best_n_exact-n32',cid),{}).get('fve')
            if parent is None or row['a32_saved_fve']!=parent or abs(row['a32_fve']-parent)>1e-5:raise ValueError('Replay A32 reference does not reproduce source fit')
            maximum_parent_delta=max(maximum_parent_delta,abs(row['a32_fve']-parent))
            for fit in row['fits']:
                key=fit['condition'],cid
                if key not in outputs or fit['text_sha256']!=outputs[key]['text_sha256']:raise ValueError('Replay fits another chosen text')
                if fit['solver']!='scipy_exact' or fit['fits_scope']!='emitted_bullets' or fit['fve'] is not None and (isinstance(fit['fve'],bool) or not math.isfinite(fit['fve'])):raise ValueError('Replay fit objective/value differs')
                value={'fve':fit['fve'],'status':fit['status']}
                if key in values and values[key]!=value:raise ValueError('Conflicting replay fit')
                values[key]=value
        if len(seen)!=contract['expected_cells'] or terminal['completed_cells']!=len(seen) or terminal['expected_cells']!=len(seen):raise ValueError('Terminal replay coverage differs')
        replay_audits.append({'path':str(directory),'sites':len(seen),'maximum_a32_fve_replay_delta':maximum_parent_delta,'status_sha256':pins[str(status)]})
    quality_rows={(r['condition'],r['family']):r['metric'] for r in quality['cohorts']['full']['rows']}
    rows=[];group_of={cid:c['group_id'] for cid,c in cells.items()}
    for condition,entry in conditions.items():
        for family in inventory['families']:
            ids=sorted(cid for cid,c in cells.items() if c['family']==family);selected=[cid for cid in ids if (condition,cid) in outputs]
            fit={cid:values.get((condition,cid),{}).get('fve') for cid in selected}
            valid=[v for v in fit.values() if v is not None];reasons=Counter(values.get((condition,cid),{}).get('status','fit_not_yet_extracted') for cid in selected if fit[cid] is None)
            item={'condition':condition,'family':family,'full_site_count':len(ids),'selected_site_count':len(selected),'scored_site_count':len(valid),
                'missing_selection_sites':len(ids)-len(selected),'unavailable_fit_sites':len(selected)-len(valid),'unavailable_reasons':dict(reasons),
                'status':'complete_comparable' if len(valid)==len(ids) else 'partial_or_unavailable',
                'mean_fve':statistics.mean(valid) if valid else None,'median_fve':statistics.median(valid) if valid else None,
                'minimum_fve':min(valid) if valid else None,'maximum_fve':max(valid) if valid else None,
                'quality_metric':quality_rows.get((condition,family)), 'parent_comparisons':[]}
            item.update(grouped_fit_summary(fit,group_of,stream=f'mean|{condition}|{family}'))
            item['mean_fve_percentage_points']=100*item['mean_fve'] if item['mean_fve'] is not None else None
            item['mean_fve_ci95_percentage_points']=[100*v for v in item['mean_fve_ci95']] if item['mean_fve_ci95'] is not None else None
            for comparison in references(condition,entry['parent_condition_ids']):
                reference=comparison['reference'];base={cid:values.get((reference,cid),{}).get('fve') for cid in ids if (reference,cid) in outputs}
                paired=paired_fit_change(fit,base,group_of,stream=f'{condition}|{reference}|{family}')
                paired['mean_delta_percentage_points']=100*paired['mean_delta'] if paired['mean_delta'] is not None else None
                paired['ci95_delta_percentage_points']=[100*v for v in paired['ci95_delta']] if paired['ci95_delta'] is not None else None
                pairids=[cid for cid in fit if fit[cid] is not None and base.get(cid) is not None]
                lengths={'mean_bullets_removed_common_fit_mask':statistics.mean(outputs[reference,cid]['bullet_count']-outputs[condition,cid]['bullet_count'] for cid in pairids) if pairids else None,
                    'mean_tokens_removed_common_fit_mask':statistics.mean(outputs[reference,cid]['token_count']-outputs[condition,cid]['token_count'] for cid in pairids) if pairids else None}
                item['parent_comparisons'].append(comparison|paired|lengths|{'intended_paired_sites':len(ids),'missing_or_invalid_pairs':len(ids)-len(pairids)})
            rows.append(item)
    if any(sha(path)!=value for path,value in pins.items()):raise ValueError('Diagnostic evidence changed during extraction')
    if any(sha(path)!=value for path,value in implementation.items()):raise ValueError('Diagnostic implementation changed during extraction')
    payload={'status':'complete_secondary_diagnostic' if all(r['status']=='complete_comparable' or r['condition']=='raw_n1-n1' for r in rows) else 'partial_secondary_diagnostic',
        'diagnostic_version':2,'site_change_equivalence_tolerance':1e-5,
        'updated_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':a.inventory_sha256,'quality_analysis_sha256':a.quality_analysis_sha256,
        'objective':'1-squared_residual/squared_target','solver':'scipy_exact','vector_contract_sha256':inventory['vector_contract']['sha256'],
        'normalization':{'center_predictions':True,'whitening_ridge_c':.1,'unit_phrase_directions':True,'phrase_norm_epsilon':1e-9,'target_unit_normalized':False,'clip_fve':False,'scored_atom_tokens':32},
        'original_fit_contracts':fit_contracts,'replay_parent_equivalence_audits':replay_audits,'rows':rows,'source_sha256':pins,
        'implementation_sha256':implementation,
        'limits':['Post-hoc requested descriptive reconstruction diagnostic; no method choices or 496 headline contrasts changed.',
            'FVE summarizes whitened activation reconstruction from the first32 cleaned tokens of each retained atom, not correctness of full prose.',
            'Means/medians use valid scored sites only; paired changes use the identical common-valid-site mask.',
            'Reconstruction valid-site coverage can differ from native quality coverage over all original sites; compare the reported masks rather than assuming identical denominators.',
            'The initial replay-v1 tranche completed uninterrupted; its terminal vector and whitening pins do not rely on resume-source restoration.',
            'Raw unmodified N1 has no comparable saved FVE and is explicitly unavailable.',
            'Empty emitted readouts have zero fit; invalid cleaned atoms remain unavailable.',
            'Whole related-group bootstrap preserves site weights; examples/diagnostic contrasts do not establish causal mechanisms.']}
    payload['limits'].append('Per-site improved/worsened counts require a change beyond 1e-5; exact zeros and smaller changes share the neutral unchanged-or-within-tolerance category. Raw means, paired differences, masks and intervals retain the actual saved/replayed values.')
    a.output.parent.mkdir(parents=True,exist_ok=True);atomic(a.output,payload)
    print(json.dumps({'output':str(a.output),'sha256':sha(a.output),'rows':len(rows),'complete_comparable_rows':sum(r['status']=='complete_comparable' for r in rows)}))


if __name__=='__main__':main()
