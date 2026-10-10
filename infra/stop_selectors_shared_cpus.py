"""One authorized SIGINT of the four identified shared-core selector workers."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import signal

expected = {1113571:0, 1113692:1, 1113529:2, 1113573:3}
root = Path('${OLENS_DATA_ROOT}/selections/development-full-grid-v2')
output = root / 'initial-shared-cpus-stop.json'
if output.exists():
    raise FileExistsError('Never repeat the recorded stop operation')
rows = []
for pid, shard in expected.items():
    proc = Path('/proc') / str(pid)
    arguments = [value.decode() for value in (proc/'cmdline').read_bytes().split(b'\0') if value]
    if not arguments or arguments[0] != '${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python' or 'scripts/compare_selectors.py' not in arguments:
        raise ValueError('Worker identity changed')
    if arguments[arguments.index('--shard-index')+1] != str(shard) or (proc/'status').stat().st_uid != os.getuid():
        raise ValueError('Worker shard/ownership changed')
    stat = (proc/'stat').read_text().rsplit(')',1)[1].split()
    journal = root / f'shard-{shard}' / 'selections.jsonl'
    raw = journal.read_bytes()
    valid = 0
    for line in raw.splitlines():
        try:
            json.loads(line)
            valid += 1
        except json.JSONDecodeError:
            break
    rows.append({'pid':pid,'shard':shard,'state':stat[0], 'user_cpu_seconds':int(stat[11])/os.sysconf('SC_CLK_TCK'),'system_cpu_seconds':int(stat[12])/os.sysconf('SC_CLK_TCK'),'rss_bytes':int(stat[21])*os.sysconf('SC_PAGE_SIZE'),'completed_json_records_before_signal':valid,'journal_bytes_before_signal':len(raw),'journal_sha256_before_signal':sha256(raw).hexdigest()})
record = {'checked_utc':datetime.now(timezone.utc).isoformat(),'signal':'SIGINT','reason':'Root-authorized restart on disjoint CPU cores; original four steps shared an identical four-physical-core cpuset.','workers':rows}
output.write_text(json.dumps(record,indent=2)+'\n')
for row in rows:
    os.kill(row['pid'],signal.SIGINT)
print(json.dumps(record,indent=2))
