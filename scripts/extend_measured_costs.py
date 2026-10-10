"""Version completed helper/CPU costs; preserve prior cost snapshots."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path


def helper_pipeline(phases, medium):
    proposal=phases['none_phases']['candidate-pair-proposal-local-ids-v2']
    confirmation=phases['none_phases']['whole-bullet-equivalence-compatibility-v5-local-ids-v1']
    none=round(proposal['actual_usd']+confirmation['actual_usd'],9)
    medium_cost=round(medium['actual_usage_derived_usd'],9)
    combined=round(proposal['actual_usd']+medium_cost,9)
    if combined!=phases['deployment_none_proposal_plus_medium_confirmation_usd']:
        raise ValueError('Medium deployment helper cost must include proposal')
    return {'cells':189,'none_pipeline_usd':none,'medium_pipeline_usd':combined,
            'none_pipeline_calls':proposal['calls']+confirmation['calls'],
            'proposal':proposal,'none_confirmation':confirmation,'medium_confirmation':medium,
            'none_usd_per_cell':none/189,'medium_usd_per_cell':combined/189,
            'medium_campaign_reused_proposal':True,
            'limits':['Deployment includes proposal and confirmation even when this campaign reused proposal bytes.',
                      'The medium reservation-to-response envelope is not full proposal-plus-confirmation script latency.',
                      'Benchmark judging and candidate generation/AR are separate costs.',
                      'Unknown semantic labels are not unknown financial charges.']}


def row(component,scope,value,unit,measurement):
    return {'component':component,'scope':scope,'value':value,'unit':unit,'measurement':measurement}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--durable',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError('Preserve frozen cost versions')
    sources={}
    def read(path):
        raw=path.read_bytes();sources[str(path)]=sha256(raw).hexdigest();return json.loads(raw)
    costs=read(a.durable/'diagnostics/costs-v2/components.json')
    if costs['pricing_revision']!='luna-cache-write-v1':raise ValueError('Require audited cache-write pricing')
    phases=read(a.durable/'selections/consensus-pilot189-v5-medium/deployment-phase-costs.json')
    medium=read(a.durable/'runs/helper-semantic-medium-reconfirmation-v1/physical-usage-v1.json')
    # The usage artifact is authoritative; retain its original units and scope.
    pipeline=helper_pipeline(phases,medium)
    if pipeline['none_pipeline_usd']!=costs['campaign']['helper_b_repaired_v5']['actual_usd']:
        raise ValueError('None pipeline differs from corrected physical usage')
    pooling=read(a.durable/'selections/specificity-pooling-pilot189-v1/status.json')
    pruning=read(a.durable/'selections/development-full-grid-e1-pruning-v1/status.json')
    forecast=read(a.durable/'diagnostics/remaining-pipeline-forecast-v1.json')
    selector_status=[read(a.durable/f'selections/development-full-grid-v4/shard-{i}/status.json') for i in range(4)]
    if any(s['status']!='complete' for s in [pooling,pruning,*selector_status]):raise ValueError('CPU timing requires terminal tasks')
    costs['schema_version']=3;costs['generated_utc']=datetime.now(timezone.utc).isoformat()
    costs['campaign']['helper_b_repaired_none_medium']=pipeline
    costs['campaign']['specificity_pooling']={'cells':pooling['cells'],'conditions':pooling['conditions'],
        'cpu_task_wall_seconds':pooling['seconds'],'threads':4,'scope':'All five cached DEV pilot outputs, including unchanged parents; no model calls'}
    costs['campaign']['full_dev_e1_pruning']={'cells':pruning['cells'],'conditions':pruning['conditions'],
        'cpu_task_wall_seconds':pruning['seconds'],'threads':4,'scope':'Four pruning/control arms plus unchanged E1 parent; cached vectors'}
    costs['campaign']['full_dev_final_selectors']={'cells':5236,'conditions':40,'workers':4,'threads_per_worker':4,
        'cpu_task_wall_seconds_sum':sum(s['seconds'] for s in selector_status),
        'max_worker_wall_seconds':max(s['seconds'] for s in selector_status),
        'scope':'Successful v4 campaign only; not a single deployed selector or summed process CPU time'}
    costs['deployment']['helper_b_repaired_none_usd_per_cell']=pipeline['none_usd_per_cell']
    costs['deployment']['helper_b_medium_proposal_plus_confirmation_usd_per_cell']=pipeline['medium_usd_per_cell']
    costs['source_sha256']|=sources
    report=json.loads(a.report.read_text());report['measured_cost_components']=costs
    generation=forecast['measured_generation_model_seconds_per_n32_cell']
    ar=forecast['measured_unique_ar_vectors_per_dev_cell']/forecast['measured_final_ar_vectors_per_second']
    shared=[row('Generate 32 candidate samples','New-input component',generation,'GPU task seconds / cell','Measured DEV filled-batch average; excludes reload'),
            row('Encode required candidate bullets','New-input component',ar,'GPU task seconds / cell','Derived from DEV unique-vector ratio and measured final AR throughput'),
            row('Capture target activation','New-input component',None,'GPU task seconds / item','Required for a fresh item; this campaign already captured all core inputs')]
    report['methods']['consensus']['cost_components']=[
        row('Generate 16 samples','New-input component estimate',generation/2,'GPU task seconds / cell','Proportional N16 estimate, not measured small-batch latency'),
        row('Repaired consensus, no reasoning: proposal + confirmation','Recurring helper pipeline',pipeline['none_usd_per_cell'],'USD / cell','Observed usage-derived mean over 189 cells'),
        row('Repaired consensus, medium: proposal + confirmation','Recurring helper pipeline',pipeline['medium_usd_per_cell'],'USD / cell','Observed usage-derived mean over 189 cells'),
        row('Medium confirmation alone, reused proposal','Pilot campaign',medium['actual_usage_derived_usd'],'USD / 189 cells','Measured physical usage; excludes original proposal charge'),
        row('Medium confirmation, 195 calls at 16 slots','Pilot confirmation stage',medium['active_api_envelope_s'],'reservation-to-last-response wall-seconds','Measured service envelope; not full script or fresh two-stage pipeline latency'),
        row('Capture, required AR, and local selection','New-input components',None,'additional GPU / CPU time','Required; not measured end-to-end for this exact helper pipeline')]
    report['methods']['combinations']['cost_components']=shared+[
        row('Pool with specificity: all five outputs','Cached pilot campaign',pooling['seconds'],'task wall-seconds on CPU, four threads','Measured over 189 cells; includes setup and unchanged parents'),
        row('E1 pruning: all five outputs','Cached full DEV campaign',pruning['seconds'],'task wall-seconds on CPU, four threads','Measured over 5,236 cells; includes setup and unchanged parent')]
    report['methods']['sample_selection']['cost_components']=shared+[
        row('All 40 selector arms on four workers','Full DEV campaign',costs['campaign']['full_dev_final_selectors']['max_worker_wall_seconds'],
            'maximum worker task wall-seconds','Measured; each worker uses four threads; not latency of one deployed method')]
    report['cost_notes']=['Generation and AR are shared campaign work, not free deployment components.',
        'D, E1 and their deletion controls reuse the same N32 pool. Repaired B uses N16; unequal sample counts remain explicit.',
        'Cached selector replay excludes model generation, capture, AR encoding, and recurring helpers. No measured end-to-end deployment latency is claimed.',
        'CPU values are task wall-seconds, not summed process CPU time. GPU dollar cost is unknown; USD values are usage estimates, not invoice reconciliation.']
    for path,expected in sources.items():
        if sha256(Path(path).read_bytes()).hexdigest()!=expected:raise ValueError('Cost source changed')
    a.output.mkdir(parents=True);(a.output/'components.json').write_text(json.dumps(costs,indent=2)+'\n')
    report['provenance']['cost_components_source']={'path':str(a.output/'components.json'),'sha256':sha256((a.output/'components.json').read_bytes()).hexdigest()}
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'none_usd_per_cell':pipeline['none_usd_per_cell'],'medium_usd_per_cell':pipeline['medium_usd_per_cell'],
                      'pooling_cpu_task_wall_seconds':pooling['seconds'],'pruning_cpu_task_wall_seconds':pruning['seconds']}))
