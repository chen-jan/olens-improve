"""Verify completed E1 pruning coverage and byte-preserved parent identity."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path


def scan(path):
    with path.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):raise ValueError('Terminal journal has uncommitted tail')
            yield line, json.loads(line)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output-root',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use allocated CPU resources')
    root=a.output_root;status=json.loads((root/'status.json').read_text());spec=json.loads((root/'spec.json').read_text())
    if status['status']!='complete' or status['cells']!=5236 or status['conditions']!=5:raise ValueError('Require terminal full DEV five-arm output')
    method='best_n_specificity_mean';expected={method,*[f'{method}_{kind}_{threshold}' for kind in ('then_prune','random_delete_matched') for threshold in ('0.001','0.005')]}
    rows={};digest=sha256()
    for line,row in scan(root/'selections.jsonl'):
        digest.update(line)
        if row['cell_id'] in rows:raise ValueError('Duplicate completed output')
        choices={s['method']:s for s in row['selections']}
        if len(choices)!=5 or set(choices)!=expected:raise ValueError('Unexpected output arms')
        if any(s['n']!=32 or s['token_count']>256 or s['bullet_count']>4 for s in choices.values()):raise ValueError('Output cap differs')
        for threshold in ('0.001','0.005'):
            if choices[f'{method}_then_prune_{threshold}']['bullet_count']!=choices[f'{method}_random_delete_matched_{threshold}']['bullet_count']:raise ValueError('Random deletion count does not match')
        rows[row['cell_id']]=(row,choices)
    if digest.hexdigest()!=status['selection_sha256']:raise ValueError('Terminal output SHA differs')
    output_sha=digest.hexdigest();digest=sha256();seen=set();max_fve_delta=0.
    for line,source in scan(a.source):
        digest.update(line);cid=source['cell_id']
        if cid in seen or cid not in rows:raise ValueError('Unexpected or duplicate parent')
        seen.add(cid);row,choices=rows[cid]
        parent=[s for s in source['selections'] if s['method']==method and s['n']==32]
        if len(parent)!=1:raise ValueError('Missing parent')
        parent=parent[0];unchanged=choices[method]
        for key in ('text','phrase_ids','token_count','bullet_count','atoms'):
            if parent[key]!=unchanged[key]:raise ValueError(f'Unchanged parent {key} differs')
        if source['activation_sha256']!=row['activation_sha256']:raise ValueError('Target activation differs')
        delta=abs(parent['fits']['exact']['fve']-unchanged['fits']['exact']['fve']);max_fve_delta=max(max_fve_delta,delta)
        if delta>1e-5:raise ValueError('Parent exact FVE differs beyond declared guard')
    if set(rows)!=seen or len(seen)!=5236 or digest.hexdigest()!=spec['selector_sha256']:raise ValueError('Source SHA or cohort differs')
    result={'checked_utc':datetime.now(timezone.utc).isoformat(),'status':'verified_complete_development',
            'cells':len(seen),'conditions':5,'parent_identity_fields':['text','phrase_ids','token_count','bullet_count','atoms'],
            'parent_source_sha256':digest.hexdigest(),'selection_sha256':output_sha,
            'unchanged_parent_max_fve_absolute_delta':max_fve_delta,'quality_status':'unjudged'}
    target=root/'identity-audit.json'
    if target.exists():raise FileExistsError('Preserve the existing audit')
    target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
