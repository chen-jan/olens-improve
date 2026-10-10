"""Read-only scientific overlap and committed-prefix throughput audit."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path


def prefix(path):
    digest = sha256(); total_bytes = 0; rows = []
    with path.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):
                break
            row = json.loads(line)
            digest.update(line); total_bytes += len(line); rows.append(row)
    return rows, {'path':str(path),'committed_prefix_bytes':total_bytes,'committed_prefix_sha256':digest.hexdigest(),'committed_records':len(rows)}


def scientific(row, allow_empty_invalid_metadata=False):
    excluded={'config_sha256','seconds_since_start'}
    if allow_empty_invalid_metadata and 'invalid_AR_atoms_by_sample' in row:
        if row['invalid_AR_atoms_by_sample']:
            raise ValueError('Previously completed rows must have empty invalid-atom metadata')
        excluded.add('invalid_AR_atoms_by_sample')
    return {key:value for key,value in row.items() if key not in excluded}


def differences(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict) and a.keys()==b.keys():
        return [result for key in a for result in differences(a[key],b[key],path+'/'+key)]
    if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
        return [result for index,(left,right) in enumerate(zip(a,b)) for result in differences(left,right,path+'/'+str(index))]
    if a==b:
        return []
    if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
        return [{'path':path,'kind':'numeric','absolute_delta':abs(a-b),'old':a,'new':b}]
    return [{'path':path,'kind':'non_numeric','old':a,'new':b}]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--old',required=True);parser.add_argument('--new',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--old-filename',default='selections.initial-shared-cpus.jsonl')
    parser.add_argument('--allow-empty-invalid-metadata',action='store_true');args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Inspect full selector prefixes inside a CPU allocation')
    output=Path(args.output)
    if output.exists():raise FileExistsError('Use a new immutable audit output')
    comparisons=[];sources=[];progress=[]
    for shard in range(4):
        old,old_source=prefix(Path(args.old)/f'shard-{shard}'/args.old_filename)
        new,new_source=prefix(Path(args.new)/f'shard-{shard}'/'selections.jsonl')
        sources.extend([old_source,new_source]);lookup={row['cell_id']:row for row in new}
        if len(lookup)!=len(new):raise ValueError('Duplicate completed v3 cell')
        for row in old:
            if row['cell_id'] not in lookup:raise ValueError('Overlap cell not yet committed')
            later=lookup[row['cell_id']];diff=differences(scientific(row,args.allow_empty_invalid_metadata),scientific(later,args.allow_empty_invalid_metadata))
            numeric=[value for value in diff if value['kind']=='numeric'];non_numeric=[value for value in diff if value['kind']!='numeric']
            text_fields=[value for value in diff if '/text' in value['path'] or '/phrase_ids' in value['path']]
            fve=[value['absolute_delta'] for value in numeric if value['path'].endswith('/fve')]
            comparisons.append({'cell_id':row['cell_id'],'shard':shard,'scientific_fields_exactly_equal':not diff,'numeric_differences':len(numeric),'non_numeric_differences':len(non_numeric),'text_or_source_id_differences':len(text_fields),'max_fve_absolute_delta':max(fve,default=0.),'max_numeric_absolute_delta':max([value['absolute_delta'] for value in numeric],default=0.),'first_differences':diff[:5]})
        tail=new[-min(65,len(new)):]
        elapsed=tail[-1]['seconds_since_start']-tail[0]['seconds_since_start'] if len(tail)>1 else None
        rate=(len(tail)-1)/elapsed if elapsed and elapsed>0 else None
        config_path=Path(args.new)/f'shard-{shard}'/'config.json';config=json.loads(config_path.read_text())
        sources.append({'path':str(config_path),'sha256':sha256(config_path.read_bytes()).hexdigest()})
        progress.append({'shard':shard,'completed_cells':len(new),'expected_cells':len(config['cell_ids']),'layers_observed':sorted({row['layer'] for row in new}),'last_committed_elapsed_seconds':new[-1]['seconds_since_start'] if new else None,'tail_completed_intervals':len(tail)-1,'tail_seconds':elapsed,'tail_cells_per_second':rate,'remaining_seconds_if_tail_rate_holds':(len(config['cell_ids'])-len(new))/rate if rate else None})
    excluded=['config_sha256','seconds_since_start']+(['invalid_AR_atoms_by_sample (required empty)'] if args.allow_empty_invalid_metadata else [])
    result={'checked_utc':datetime.now(timezone.utc).isoformat(),'scope':'All preserved completed-cell overlap; active new outputs read through committed newline prefixes only','excluded_fields':excluded,'sources':sources,'overlap_cells':len(comparisons),'exactly_equal_cells':sum(row['scientific_fields_exactly_equal'] for row in comparisons),'max_fve_absolute_delta':max(row['max_fve_absolute_delta'] for row in comparisons),'text_or_source_id_differences':sum(row['text_or_source_id_differences'] for row in comparisons),'comparisons':comparisons,'progress':progress,'forecast_caveat':'Tail slopes are measured completed-cell throughput, not a guarantee for later families, candidate counts, or filesystem conditions. Layer presence does not prove every cold initialization is finished.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('checked_utc','overlap_cells','exactly_equal_cells','max_fve_absolute_delta','text_or_source_id_differences','progress')},indent=2))


if __name__=='__main__':main()
