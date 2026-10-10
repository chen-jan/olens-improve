"""Attach complete DEV baselines without replacing the partial-grid pilot."""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path


def append(report,measurements,review):
    if not measurements.get('original_grid_contract') or not all(c['measurement_complete'] for c in measurements['conditions']):raise ValueError('Require complete original DEV measurements')
    if {c['condition'] for c in measurements['conditions']}!={'raw_n1-n1','capped_n1-n1'}:raise ValueError('This baseline view requires exactly raw and capped N1')
    rows=[];paired=[]
    interval_text=lambda values: '['+', '.join(f'{100*x:.1f}%' for x in values)+']' if values else 'Not measured'
    labels={'original_grid_item_pass_rate':'Original-grid item recovery: ANY passing site/layer','original_grid_contradiction_rate':'Contradictions / specific readouts'}
    for arm in measurements['conditions']:
        for family,status in arm['families'].items():
            for endpoint,m in status['original_grid_metrics'].items():
                rows.append({'family':family,'cohort':'Full DEV: complete original grids','condition':arm['condition'],'endpoint':labels[endpoint],'scope':'original_grid_development','value':m['value'],'numerator':m['numerator'],'denominator':m['denominator'],'eligible_count':m['items'],'missing_count':0,'ci':m['ci95'],'uncertainty':f"Whole-group 95% interval {interval_text(m['ci95'])}; {m['independent_groups']} groups. {m['warning'] or ''}"})
            for endpoint in ['cell_recovery','assertion_share']:
                m=status['metrics'].get(endpoint)
                if m:rows.append({'family':family,'cohort':'Full DEV: complete original grids','condition':arm['condition'],'endpoint':'Cell recovery' if endpoint=='cell_recovery' else 'Specific assertions / intended outputs','scope':'full_grid_cell_diagnostic','value':m['value'],'numerator':m['numerator'],'denominator':m['denominator'],'eligible_count':status['expected_cells'],'missing_count':status['missing_stage1']+status['missing_stage2'],'ci':m['ci95'],'uncertainty':f"Whole-group 95% interval {interval_text(m['ci95'])}; {m['independent_groups']} groups"})
    for row in measurements['original_grid_paired_comparisons']:
        if row['baseline_condition']!='raw_n1-n1':continue
        paired.append({'family':row['family'],'cohort':'Full DEV: complete original grids','condition':row['condition']+' vs raw N1','endpoint':'Paired delta: '+labels[row['endpoint']],'scope':'original_grid_development','value':row['delta'],'numerator':None,'denominator':None,'eligible_count':row['items'],'missing_count':0,'ci':row['ci95_delta'],'uncertainty':f"Whole-group 95% interval {interval_text(row['ci95_delta'])}; {row['independent_groups']} groups. {row['warning'] or ''}"})
    report['full_development']={'title':'Complete DEV baseline evidence','scope':'Complete original development grids; no validation or test results',
        'summary':'Raw and capped N1 are fully judged on 5,236 cells across 121 items. Item aggregation and cell recovery are separate. These baselines do not establish a selector improvement.',
        'metrics':rows,'paired_metrics':paired,'traces':review['cases'],'judge_cost':review['judge_cost'],
        'donor_readiness':review['donor_readiness'],'donor_limits':review['donor_limits'],
        'limits':['Role item recovery is ANY across 114 sites: 23/30 items pass although raw cell recovery is 155/3,420. It does not establish 23 fully faithful explanations. No uniform-guessing chance floor is assumed.',
            'Chain has seven independent related groups. Its bootstrap interval does not establish robustness.',
            'The blind chain judge can change its top-named value while the correct number remains; hallucination verdicts also change under formatting. Frozen judgments are preserved; these examples are audit candidates, not corrected ground truth.',
            'Paired intervals describe the original item/readout endpoints on DEV. No held-out or whole-bank accuracy is reported.'],
        'measurement_manifest_sha256':measurements['manifest_sha256'],'selection_sha256':measurements['selection_sha256']}
    report['updated_utc']=datetime.now(timezone.utc).isoformat()
    report['progress']['phase']='Full DEV raw/capped N1 baselines complete; candidate encoding and selected-method comparisons underway'
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--measurements',required=True);p.add_argument('--review',required=True);p.add_argument('--output',required=True);p.add_argument('--runtime',default='configs/runtime.json');p.add_argument('--resource-snapshot');a=p.parse_args()
    r=append(json.loads(Path(a.report).read_text()),json.loads(Path(a.measurements).read_text()),json.loads(Path(a.review).read_text()))
    r['full_development']['source_sha256']={str(Path(path)):sha256(Path(path).read_bytes()).hexdigest() for path in (a.measurements,a.review)}
    runtime=json.loads(Path(a.runtime).read_text());started=datetime.fromisoformat(runtime['execution_started_utc'].replace('Z','+00:00'))
    r['progress']['elapsed_hours']=(datetime.now(timezone.utc)-started).total_seconds()/3600
    if a.resource_snapshot:
        raw=Path(a.resource_snapshot).read_bytes();observed=json.loads(raw)
        r['api']=observed['budget']|{'observed_utc':observed['checked_utc']}
        r['provenance']['resource_snapshot_sha256']=sha256(raw).hexdigest()
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
