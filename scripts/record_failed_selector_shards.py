"""Source-bind an incomplete failed selector version without changing it."""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--logs',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Read full journals on allocated CPU')
    output=Path(a.output)
    if output.exists():raise FileExistsError('Do not overwrite original failure provenance')
    shards=[]
    for shard in range(4):
        directory=Path(a.root)/f'shard-{shard}';sources={};journal=directory/'selections.jsonl';digest=sha256();prefix=sha256();committed_bytes=0;total_bytes=0;cells=[]
        with journal.open('rb') as stream:
            for line in stream:
                digest.update(line);total_bytes+=len(line)
                if not line.endswith(b'\n'):continue
                row=json.loads(line);cells.append(row['cell_id']);prefix.update(line);committed_bytes+=len(line)
        if len(cells)!=len(set(cells)):raise ValueError('Duplicate committed cell')
        config_path=directory/'config.json';raw=config_path.read_bytes();config=json.loads(raw)
        sources[str(config_path)]=sha256(raw).hexdigest()
        if cells!=config['cell_ids'][:len(cells)]:raise ValueError('Non-prefix failed journal')
        log=Path(a.logs)/f'full-dev-selectors-v3-shard-{shard}.log';body=log.read_bytes();sources[str(log)]=sha256(body).hexdigest()
        errors=[line for line in body.decode(errors='replace').splitlines() if 'Candidate contains an empty cleaned scoring atom' in line]
        if not errors:raise ValueError('Expected failure not established by this shard log')
        sources[str(journal)]=digest.hexdigest()
        for status_path in directory.glob('*status.json'):
            sources[str(status_path)]=sha256(status_path.read_bytes()).hexdigest()
        shards.append({'shard':shard,'state':'failed_incomplete','reason':'empty_cleaned_scoring_atom_guard','committed_cells':len(cells),'expected_cells':len(config['cell_ids']),'committed_prefix_bytes':committed_bytes,'committed_prefix_sha256':prefix.hexdigest(),'journal_bytes':total_bytes,'uncommitted_tail_bytes_preserved':total_bytes-committed_bytes,'source_sha256':sources})
    result={'checked_utc':datetime.now(timezone.utc).isoformat(),'status':'failed_incomplete','version':'development-full-grid-v3','completed_cells':sum(shard['committed_cells'] for shard in shards),'expected_cells':5236,'shards':shards,'boundary':'Configs, journals, status files and original logs remain unchanged. This is an error/provenance sidecar, not a complete scientific result.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'completed_cells':result['completed_cells'],'shards':[(x['shard'],x['committed_cells']) for x in shards]}))


if __name__=='__main__':main()
