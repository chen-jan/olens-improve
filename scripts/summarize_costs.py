"""Source-bound cost components; never equate cache reuse with deployment."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--fast',required=True);p.add_argument('--durable',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Read campaign journals inside a CPU allocation')
    fast=Path(a.fast);durable=Path(a.durable);sources={}
    def read(path):
        raw=path.read_bytes();sources[str(path)]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
    def lines(path):
        raw=path.read_bytes();sources[str(path)]=hashlib.sha256(raw).hexdigest();return [json.loads(x) for x in raw.splitlines()]
    pilot=durable/'runs/development-shared-pilot-v2'
    events=[e for path in sorted(pilot.glob('shard-*-of-*.jsonl')) for e in lines(path)]
    generated=[e for e in events if e['kind']=='generation']
    instrument=read(fast/'runs/instrument_n2_v1/run.json')
    generation_seconds=sum(e['seconds'] for e in generated)
    instrument_seconds=sum(e['seconds'] for e in instrument['generation'])
    samples=sum(len(e.get('records',[])) for e in events)
    new_samples=sum(len(e['records']) for e in generated)
    n32_warm_equivalent=generation_seconds/(new_samples/32)
    ar=read(fast/'vectors/shared-global-v1/a451cf49d28ac7447722/usage_21ff917ecc3a46f1d633.run.json')
    selectors=read(durable/'selections/pilot189-selectors-v1/status.json')
    profile=read(durable/'diagnostics/costs-v1/cached-selectors.json')
    e3=read(durable/'selections/e3-pilot189-v1/status.json')
    e3rows=lines(durable/'selections/e3-pilot189-v1/readouts.jsonl')
    candidates=[c for r in e3rows for c in r['candidates']]
    contexts=sum(len(c['conditions']) for c in candidates)
    scored_tokens=sum(v['candidate_token_count'] for c in candidates for v in c['conditions'].values())
    # Each cell's eligible candidates are evaluated under own + two controls in B8.
    forwards=sum((sum(len(c['conditions']) for c in r['candidates'])+7)//8 for r in e3rows)
    f=[read(durable/f'runs/helper-edit-pilot-v1/round{i}-scored/status.json') for i in (1,2)]
    helpers=read(durable/'runs/helper-semantic-pilot-v1/natural-audits/helper-costs-v1.json')
    helpers=[{k:v for k,v in stage.items() if k!='physical_attempt_ids'} for stage in helpers]
    record={'scope':'189-cell partial-grid DEV campaign and eight-cell cached CPU cost instrument',
        'gpu_dollars':None,'gpu_seconds_definition':'Sum of occupied one-GPU task wall times; includes recorded CPU/loading overhead, not pure kernel time.',
        'campaign':{'cells':189,'samples':samples,'generation_new_samples':sum(len(e['records']) for e in generated),
            'generation_append_gpu_seconds':generation_seconds,'generation_original16_gpu_seconds':instrument_seconds,
            'generation_total_gpu_seconds':generation_seconds+instrument_seconds,'generation_concurrency':4,
            'ar_unique_vectors':ar['new_unique_vectors'],'ar_gpu_seconds':ar['seconds'],'ar_batch_size':ar['batch_size'],
            'selectors_cpu_task_wall_seconds':selectors['seconds'],'selectors_conditions_per_cell':40,'selectors_threads':4,
            'e3_candidates':len(candidates),'e3_context_sequences':contexts,'e3_candidate_tokens_scored':scored_tokens,
            'e3_batched_forward_calls':forwards,'e3_gpu_task_seconds':e3['total_seconds'],'e3_scoring_seconds':e3['scoring_seconds'],
            'e3_fixture_forward_calls':4,'e3_fixture_sequence_evaluations':6,
            'f_new_ar_vectors':sum(r['new_raw_vectors'] for r in f),'f_ar_gpu_task_seconds':sum(r['seconds'] for r in f),
            'helpers':helpers},
        'incremental_cache':profile['summary'],'incremental_cache_timer':'Task wall-seconds on CPU, four Torch threads; perf_counter elapsed time, not summed process CPU time.',
        'deployment':{'capture_forwards_per_new_input_item':1,'full_campaign_capture_items':469,'full_campaign_capture_cells':19435,
            'full_capture_elapsed_seconds':None,'sampling_n32_gpu_seconds_per_cell':n32_warm_equivalent,
            'sampling_n_prefix_estimates':{str(n):n32_warm_equivalent*n/32 for n in (1,8,16,32)},
            'ar_n32_unique_vectors_per_cell_observed':ar['new_unique_vectors']/189,
            'ar_n32_gpu_task_seconds_per_cell_observed':ar['seconds']/189,
            'helper_b_n16_usd_per_cell_observed':helpers[0]['actual_usd']/189,
            'helper_f_two_rounds_usd_per_cell_observed':sum(x['actual_usd'] for x in helpers[1:])/189,
            'e3_n8_contexts_per_eligible_candidate':3,'f_two_rounds_new_ar_vectors_per_cell_observed':sum(r['new_raw_vectors'] for r in f)/189},
        'limitations':['N1/8/16 generation timings are proportional estimates, not measured latency. N32 was measured in filled cross-cell batches; serial/small-batch inference may be slower.',
            'AR campaign vector counts share deduplication across cells; new-activation counts and startup costs may differ.',
            'Fresh deployment includes capture, sampling, required AR or likelihood scoring, selector CPU, and applicable helpers. These component timings are not a measured end-to-end deployment latency.',
            'B uses N16, E3 N8, D/F N32; these are unequal sampling budgets. No GPU dollar rate has been established.',
            'B v4 helper costs include paid invalid responses and retries; audit found false merges. F round 1 bookkeeping failures were salvaged offline.',
            'Paid benchmark judging and scientific fixture/sensitivity work are campaign costs, not part of the deployed selector. They are not summed into this component table.'],
        'source_sha256':sources}
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'output':str(output),'generation_total_gpu_seconds':record['campaign']['generation_total_gpu_seconds'],'e3_contexts':contexts,'e3_forwards':forwards,'samples':samples}))

if __name__=='__main__':main()
