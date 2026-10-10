"""Read committed selector timing prefixes; never modify active inference code."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import statistics


def profile(root):
    result=[]
    for shard in range(4):
        path=root/f'shard-{shard}'/'selections.jsonl'; rows=[]; digest=sha256(); size=0
        with path.open('rb') as stream:
            for line in stream:
                if not line.endswith(b'\n'):break
                digest.update(line);size+=len(line);rows.append(json.loads(line))
        seen=set(); cold=[]; warm=[]; before=0.
        for row in rows:
            elapsed=row['seconds_since_start']-before;before=row['seconds_since_start']
            if row['layer'] not in seen:
                cold.append({'layer':row['layer'],'first_completion_elapsed_seconds':before,
                             'preceding_interval_seconds':elapsed})
                seen.add(row['layer'])
            else:warm.append(elapsed)
        recent=rows[-min(129,len(rows)):]
        span=recent[-1]['seconds_since_start']-recent[0]['seconds_since_start'] if len(recent)>1 else None
        rate=(len(recent)-1)/span if span else None
        expected=len(json.loads((root/f'shard-{shard}'/'config.json').read_text())['cell_ids'])
        result.append({'shard':shard,'completed':len(rows),'expected':expected,
            'source':{'path':str(path),'committed_prefix_bytes':size,'committed_prefix_sha256':digest.hexdigest()},
            'first_completion_seconds':rows[0]['seconds_since_start'] if rows else None,
            'first_layer_completion_intervals':cold,'layers_seen':len(seen),
            'warm_interval_count':len(warm),'warm_median_seconds_per_cell':statistics.median(warm) if warm else None,
            'warm_total_interval_seconds':sum(warm),
            'recent_completed_intervals':len(recent)-1,'recent_span_seconds':span,'recent_cells_per_second':rate,
            'remaining_seconds_at_recent_rate':(expected-len(rows))/rate if rate else None})
    return {'checked_utc':datetime.now(timezone.utc).isoformat(),'shards':result,
            'interpretation':['First completion includes tokenizer, manifests, vector indexes, and the first whitener; it is not pure eigensolver timing.',
            'The interval before a layer first appears includes its on-demand whitener eigensolve plus ordinary cell preparation and selection. It does not isolate eigensolver time.',
            'Each worker caches one Whitener per encountered layer. Eleven layers across four workers cause at most 44 independent eigensolves; the observed prefix may not have reached all layers.',
            'Warm intervals exclude each first-layer completion but include cache misses and selection. Tail-rate forecasts remain provisional.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use an allocated CPU job')
    if a.output.exists():raise FileExistsError('Use a new immutable timing snapshot')
    result=profile(a.root);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({s['shard']:{k:v for k,v in s.items() if k not in ('source','first_layer_completion_intervals')} for s in result['shards']},indent=2))
