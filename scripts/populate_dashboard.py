"""Attach verified compact measurements to an existing reviewed dashboard.

Preserves editorial findings/traces; never manufactures costs or conclusions.
"""
import argparse
import json
from pathlib import Path

LABELS={'contradiction_rate':'Transcript contradictions / specific readouts (lower is better)', 'assertion_share':'Specific assertion share', 'off_topic_rate':'Off-topic / specific readouts', 'unverifiable_claims_per_output':'Unverifiable claims per produced output', 'cell_recovery':'Cell mention/binding recovery'}

def method_tab(name):
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
    for key in ('sample_selection','pruning','pooling','contrastive_checks','consensus','editing','independent_checks'):
        method=report['methods'].setdefault(key,{})
        method['metrics']=[m for m in method.get('metrics',[]) if m.get('scope') != 'partial_grid_cell_diagnostic']
        method['status']='Not measured in this report'
        method['limits']=['Partial grids: cell diagnostics, not official item accuracy. Whole related groups are resampled; only 2–8 independent groups per family (chain 2, role 4, bridge 7, hallucination 8).', 'Mention recovery and transcript contradiction do not establish full factual or relational fidelity.']
        method['next_action']='Compare the complete development grids and review failure cases before freezing the validation shortlist.'
    scaling={}
    for arm in measurements['conditions']:
        name=arm['method']
        if name == 'best_n_released80': continue
        method=method_tab(name)
        report['methods'][method]['status']='Development measurements; complete conditions only, interpretation provisional' if arm['measurement_complete'] else 'Measurements pending repair'
        for family,status in arm['families'].items():
            for endpoint,m in status['metrics'].items():
                if endpoint not in LABELS: continue
                report['methods'][method]['metrics'].append({'family':family,'cohort':'shared pilot: 31 development items / 189 cells','condition':arm['condition'],'endpoint':LABELS[endpoint],'scope':'partial_grid_cell_diagnostic','value':m['value'],'numerator':m['numerator'],'denominator':m['denominator'],'eligible_count':status['expected_cells'],'missing_count':status['missing_stage1']+status['missing_stage2'],'ci':m['ci95'],'uncertainty':f"Grouped 95% interval {['%.4f' % x for x in m['ci95']] if m['ci95'] else None}; {m['independent_groups']} independent groups"})
                if name=='best_n_exact' and endpoint in ('cell_recovery','contradiction_rate'):
                    series=scaling.setdefault((family,endpoint),{'label':family+': '+LABELS[endpoint],'cohort':'Shared development pilot; whole-group 95% intervals; not official item scores','points':[]})
                    series['points'].append({'n':arm['n'],'value':m['value'],'ci':m['ci95'],'count':m['denominator']})
    retained=[series for series in report['methods']['sample_selection'].get('scaling', []) if series.get('label', '').startswith('Bridge candidate availability:')]
    report['methods']['sample_selection']['scaling']=list(scaling.values())+retained
    for method in report['methods'].values(): method['paired_metrics']=[]
    for row in measurements['paired_comparisons']:
        if row['baseline_condition'] not in ('capped_n1-n1', f"best_n_exact-n{row['condition'].rsplit('-n',1)[1]}") or row['endpoint'] not in ('cell_recovery','contradiction_rate'): continue
        name=row['condition'].rsplit('-n',1)[0]
        if name=='best_n_released80': continue
        method=method_tab(name)
        report['methods'][method]['paired_metrics'].append({'family':row['family'],'cohort':'Shared development pilot','condition':row['condition']+' vs '+row['baseline_condition'],'endpoint':'Paired delta: '+LABELS[row['endpoint']],'scope':'partial_grid_cell_diagnostic','value':row['delta'],'numerator':None,'denominator':None,'eligible_count':row['items'],'missing_count':0,'ci':row['ci95_delta'],'uncertainty':f"Whole-group 95% interval {['%.4f' % x for x in row['ci95_delta']] if row['ci95_delta'] else None}; {row['independent_groups']} groups; {row['warning'] or ''}"})
    report['provenance']['measurement_source']='dashboard/measurements.json (individual source hashes preserved there)'
    report['provenance']['judgment_root']=measurements.get('condition_root')
    report['endpoint_notes'] = list(dict.fromkeys(report.get('endpoint_notes', []) + measurements['caveats']))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--measurements',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    report=populate(json.loads(Path(a.report).read_text()),json.loads(Path(a.measurements).read_text()))
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n')
