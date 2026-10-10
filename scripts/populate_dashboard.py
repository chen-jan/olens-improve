"""Attach verified compact measurements to an existing reviewed dashboard.

Preserves editorial findings/traces; never manufactures costs or conclusions.
"""
import argparse
import json
from pathlib import Path

LABELS={'contradiction_rate':'Transcript contradictions / specific readouts (lower is better)', 'assertion_share':'Specific assertion share', 'off_topic_rate':'Off-topic / specific readouts', 'unverifiable_claims_per_output':'Unverifiable claims per produced output', 'cell_recovery':'Cell mention/binding recovery'}
GRID_LABELS={'original_grid_item_pass_rate':'Original-grid DEV item recovery (ANY passing site/layer)','original_grid_contradiction_rate':'Original-grid DEV contradictions / specific readouts'}

def method_tab(name):
    if name.startswith('pooled_specificity_') or any(part in name for part in ('_then_prune_', '_random_delete_matched_', 'pooling_exact_support_', 'exact_support_only')): return 'combinations'
    if name.startswith(('prune_', 'loo_')): return 'pruning'
    if name.startswith(('pooled_', 'greedy_')): return 'pooling'
    if any(part in name.lower() for part in ('likelihood', 'log_likelihood', 'control_ll', 'own_ll', 'e3_', 'specificity')): return 'contrastive_checks'
    if name.lower().startswith(('semantic_', 'exact_consensus', 'consensus_', 'b_')): return 'consensus'
    if name.lower().startswith(('edit', 'f_', 'helper_edit')): return 'editing'
    if name.lower().startswith(('jpp', 'g_', 'g3', 'independent_')): return 'independent_checks'
    return 'sample_selection'

def populate(report, measurements):
    if report['provenance']['cohort_manifest_sha256'] != measurements['manifest_sha256']:
        raise ValueError('Dashboard cohort hash mismatch')
    partial=not bool(measurements.get('original_grid_contract'))
    diagnostic_scope='partial_grid_cell_diagnostic' if partial else 'full_grid_cell_diagnostic'
    cohort='Shared pilot: 31 development items / 189 cells' if partial else 'Complete original development grids'
    for key in ('sample_selection','pruning','pooling','contrastive_checks','consensus','editing','independent_checks','combinations'):
        method=report['methods'].setdefault(key,{})
        method['metrics']=[m for m in method.get('metrics',[]) if m.get('scope') not in ('partial_grid_cell_diagnostic','full_grid_cell_diagnostic','original_grid_development')]
        method['status']='Not measured in this report'
        method['limits']=[('Partial grids: cell diagnostics, not official item accuracy. Whole related groups are resampled; only 2–8 independent groups per family (chain 2, role 4, bridge 7, hallucination 8).' if partial else 'Complete original DEV grids: cell diagnostics and pinned item aggregation are shown separately. Whole related groups are resampled; these are not held-out or whole-bank results.'), 'Mention recovery and transcript contradiction do not establish full factual or relational fidelity.']
        method['next_action']='Compare the complete development grids and review failure cases before freezing the validation shortlist.'
    scaling={}
    for arm in measurements['conditions']:
        name=arm['method']
        if name == 'best_n_released80': continue
        method=method_tab(name)
        if name.startswith('consensus_'):
            report['methods'][method]['limits']=list(dict.fromkeys(report['methods'][method]['limits']+['B v4 is an instrumentation-limited end-to-end diagnostic: 103 paid response-validation failures and 36 exhausted logical calls. Semantic disagreements are separate. Empty abstentions reduce assertion coverage; lower wrong fractions alone do not establish fidelity or consensus futility.']))
        if name.startswith('consensus_semantic_v5_medium_'):
            report['methods'][method]['limits']=list(dict.fromkeys(report['methods'][method]['limits']+['Medium effort has complete benchmark-output coverage, but only 2,639 of 2,685 requested helper labels are valid: 46 remain unknown across three cells, with 10 schema-invalid physical responses. Unknown labels are never converted automatically into negative votes. Manual audits still identify unsafe semantic merges; helper agreement is not benchmark truth.']))
        elif name.startswith('consensus_semantic_v5_'):
            report['methods'][method]['limits']=list(dict.fromkeys(report['methods'][method]['limits']+['The repaired helper without reasoning completes every requested pair label. This repairs instrumentation, but manual audits still identify unsafe semantic merges; helper agreement is not benchmark truth.']))
        report['methods'][method]['status']='Development measurements; complete conditions only, interpretation provisional' if arm['measurement_complete'] else 'Measurements pending repair'
        for family,status in arm['families'].items():
            for endpoint,m in status['metrics'].items():
                if endpoint not in LABELS: continue
                report['methods'][method]['metrics'].append({'family':family,'cohort':cohort,'condition':arm['condition'],'endpoint':LABELS[endpoint],'scope':diagnostic_scope,'value':m['value'],'numerator':m['numerator'],'denominator':m['denominator'],'eligible_count':status['expected_cells'],'missing_count':status['missing_stage1']+status['missing_stage2'],'ci':m['ci95'],'uncertainty':f"Grouped 95% interval {['%.4f' % x for x in m['ci95']] if m['ci95'] else None}; {m['independent_groups']} independent groups"})
                if name=='best_n_exact' and endpoint in ('cell_recovery','contradiction_rate'):
                    series=scaling.setdefault((family,endpoint),{'label':family+': '+LABELS[endpoint],'cohort':cohort+'; whole-group 95% intervals; cell endpoint','points':[]})
                    series['points'].append({'n':arm['n'],'value':m['value'],'ci':m['ci95'],'count':m['denominator']})
            for endpoint,m in status.get('original_grid_metrics',{}).items():
                report['methods'][method]['metrics'].append({'family':family,'cohort':cohort,'condition':arm['condition'],'endpoint':GRID_LABELS[endpoint],'scope':'original_grid_development','complete_grid':True,'unit':m['unit'],'value':m['value'],'numerator':m['numerator'],'denominator':m['denominator'],'eligible_count':m['items'],'missing_count':0,'ci':m['ci95'],'uncertainty':f"Whole-group 95% interval {m['ci95']}; {m['independent_groups']} independent groups"})
    retained=[series for series in report['methods']['sample_selection'].get('scaling', []) if series.get('label', '').startswith('Bridge candidate availability:')]
    report['methods']['sample_selection']['scaling']=list(scaling.values())+retained
    for method in report['methods'].values(): method['paired_metrics']=[]
    for row in measurements['paired_comparisons']:
        name=row['condition'].rsplit('-n',1)[0]
        n=row['condition'].rsplit('-n',1)[1]
        allowed={'capped_n1-n1',f'best_n_exact-n{n}'}
        if name.startswith('consensus_'):
            allowed.add('consensus_exact_support0-n16')
        if name.startswith('consensus_semantic_v5_medium_'):
            allowed.add(name.replace('consensus_semantic_v5_medium_','consensus_semantic_v5_')+f'-n{n}')
        for separator in ('_then_prune_','_random_delete_matched_'):
            if separator in name:allowed.add(name.split(separator,1)[0]+f'-n{n}')
        if name.startswith('pooling_exact_support_') or name=='exact_support_only':allowed.update({'pooling_exact_support_lambda0-n16','pooled_greedy_swap-n16'})
        if row['baseline_condition'] not in allowed or row['endpoint'] not in ('cell_recovery','contradiction_rate'): continue
        if name=='best_n_released80': continue
        method=method_tab(name)
        report['methods'][method]['paired_metrics'].append({'family':row['family'],'cohort':cohort,'condition':row['condition']+' vs '+row['baseline_condition'],'endpoint':'Paired delta: '+LABELS[row['endpoint']],'scope':diagnostic_scope,'value':row['delta'],'numerator':None,'denominator':None,'eligible_count':row['items'],'missing_count':0,'ci':row['ci95_delta'],'uncertainty':f"Whole-group 95% interval {['%.4f' % x for x in row['ci95_delta']] if row['ci95_delta'] else None}; {row['independent_groups']} groups; {row['warning'] or ''}"})
    for row in measurements.get('original_grid_paired_comparisons',[]):
        if row['baseline_condition'] not in ('capped_n1-n1',f"best_n_exact-n{row['condition'].rsplit('-n',1)[1]}"):continue
        method=method_tab(row['condition'].rsplit('-n',1)[0])
        report['methods'][method]['paired_metrics'].append({'family':row['family'],'cohort':cohort,'condition':row['condition']+' vs '+row['baseline_condition'],'endpoint':'Paired delta: '+GRID_LABELS[row['endpoint']],'scope':'original_grid_development','complete_grid':True,'value':row['delta'],'numerator':None,'denominator':None,'eligible_count':row['items'],'missing_count':0,'ci':row['ci95_delta'],'uncertainty':f"Whole-group 95% interval {row['ci95_delta']}; {row['independent_groups']} groups; {row['warning'] or ''}"})
    report['provenance']['measurement_source']='dashboard/measurements.json (individual source hashes preserved there)'
    report['provenance']['judgment_root']=measurements.get('condition_root')
    report['endpoint_notes'] = list(dict.fromkeys(report.get('endpoint_notes', []) + measurements['caveats']))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--measurements',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    report=populate(json.loads(Path(a.report).read_text()),json.loads(Path(a.measurements).read_text()))
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n')
