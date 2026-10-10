"""Preserve terminal shared-core logs and validate committed selector prefixes."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from olens_improve.ar_cache import digest

root=Path('${OLENS_DATA_ROOT}/selections/development-full-grid-v2')
logs=Path('${OLENS_COMPUTE_ROOT}/logs')
record=json.loads((root/'initial-shared-cpus-stop.json').read_text())
if any(Path('/proc',str(worker['pid'])).exists() for worker in record['workers']):
    raise RuntimeError('A stopped worker is still present; do not resume yet')
verified=[]
for worker in record['workers']:
    shard=worker['shard']; directory=root/f'shard-{shard}'
    journal=directory/'selections.jsonl';raw=journal.read_bytes()
    preserved=directory/'selections.initial-shared-cpus.jsonl'
    if preserved.exists():raise FileExistsError('Original restart journal already preserved')
    preserved.write_bytes(raw);preserved.chmod(0o444)
    config=json.loads((directory/'config.json').read_text());expected=digest(config)
    rows=[];valid_bytes=0
    for index,line in enumerate(raw.splitlines(keepends=True)):
        if not line.endswith(b'\n'):
            if valid_bytes+len(line)!=len(raw):raise ValueError('Invalid line inside journal')
            break
        row=json.loads(line)
        if row['config_sha256']!=expected:raise ValueError('Configuration provenance differs')
        rows.append(row);valid_bytes+=len(line)
    cell_ids=[row['cell_id'] for row in rows]
    if len(cell_ids)!=len(set(cell_ids)) or cell_ids!=config['cell_ids'][:len(cell_ids)]:
        raise ValueError('Completed records are not the unique ordered shard prefix')
    if valid_bytes<len(raw):
        journal.write_bytes(raw[:valid_bytes])
    logfile=logs/f'full-dev-selectors-shard-{shard}.log'
    logcopy=logs/f'full-dev-selectors-shard-{shard}.initial-shared-cpus.log'
    if logcopy.exists():raise FileExistsError('Original log already preserved')
    shutil.copyfile(logfile,logcopy);logcopy.chmod(0o444)
    verified.append({'shard':shard,'committed_cells':len(rows),'journal_sha256':sha256(raw[:valid_bytes]).hexdigest(),'preserved_original_path':str(preserved),'preserved_original_sha256':sha256(raw).hexdigest(),'uncommitted_tail_bytes_removed':len(raw)-valid_bytes,'original_log_path':str(logcopy),'original_log_sha256':sha256(logcopy.read_bytes()).hexdigest(),'expected_config_sha256':expected})
result={'checked_utc':datetime.now(timezone.utc).isoformat(),'workers_absent':True,'shards':verified,'initial_user_plus_system_cpu_seconds':sum(worker['user_cpu_seconds']+worker['system_cpu_seconds'] for worker in record['workers']),'cost_note':'Recorded compute precedes SIGINT; incomplete final cell compute cannot be recovered as a completed result. All committed selector cells are reused, and no O-lens samples are regenerated.'}
(root/'initial-shared-cpus-terminal.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
