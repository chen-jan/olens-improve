"""Bounded process/RSS audit of the four known CPU selector workers.

Prints only resource counters and three thread settings, never full process
arguments or environment values.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

output = subprocess.check_output(['ps','-eo','pid,ppid,etimes,pcpu,rss,nlwp,args'], text=True)
rows = []
for line in output.splitlines()[1:]:
    fields = line.split(None, 6)
    if len(fields) != 7:
        continue
    pid, parent, elapsed, cpu, rss, threads, command = fields
    if 'scripts/compare_selectors.py' not in command or not command.startswith(('${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python ', 'python ')):
        continue
    arguments = command.split()
    shard = arguments[arguments.index('--shard-index')+1] if '--shard-index' in arguments else None
    thread_settings = {}
    try:
        for entry in Path('/proc',pid,'environ').read_bytes().split(b'\0'):
            key, _, value = entry.partition(b'=')
            if key in (b'OMP_NUM_THREADS',b'OPENBLAS_NUM_THREADS',b'MKL_NUM_THREADS'):
                thread_settings[key.decode()] = value.decode()
    except (PermissionError,FileNotFoundError):
        thread_settings = {'status':'process environment unavailable'}
    status=Path('/proc',pid,'status').read_text()
    allowed=next((line.split(':',1)[1].strip() for line in status.splitlines() if line.startswith('Cpus_allowed_list:')),None)
    groups=Path('/proc',pid,'cgroup').read_text().splitlines()
    cgroups=[]
    for group in groups:
        hierarchy,controllers,path=group.split(':',2)
        if hierarchy=='0':
            directory=Path('/sys/fs/cgroup')/path.lstrip('/')
            counters={name:(directory/name).read_text().strip() for name in ('cpuset.cpus.effective','cpu.max','cpu.stat','memory.current','memory.peak') if (directory/name).is_file()}
            cgroups.append({'path':path,'counters':counters})
    stat=Path('/proc',pid,'stat').read_text().rsplit(')',1)[1].split()
    rows.append({'pid':int(pid),'parent_pid':int(parent),'shard':shard,'elapsed_seconds':int(elapsed),'average_cpu_percent':float(cpu),'rss_bytes':int(rss)*1024,'os_threads':int(threads),'thread_settings':thread_settings,'cpus_allowed_list':allowed,'cgroups':cgroups,'minor_page_faults':int(stat[7]),'major_page_faults':int(stat[9])})
print(json.dumps({'checked_utc':datetime.now(timezone.utc).isoformat(),'workers':rows,'total_rss_bytes':sum(row['rss_bytes'] for row in rows),'total_average_cpu_percent':sum(row['average_cpu_percent'] for row in rows),'limits_note':'Four-thread numerical kernels per worker; overlap steps can expose the full allocation before taskset restricts each worker. OS thread count includes dormant library threads.'},indent=2))
