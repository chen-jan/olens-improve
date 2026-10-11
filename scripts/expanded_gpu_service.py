"""One-device persistent dispatcher; immutable task receipts permit missing-unit resume."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def atomic(path, payload):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, indent=2) + '\n')
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue', required=True)
    parser.add_argument('--state', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('GPU dispatcher requires its own Slurm allocation')
    state_path = Path(args.state)
    prior = json.loads(state_path.read_text()) if state_path.exists() else {}
    done = prior.get('completed_tasks', {})
    receipt = dict(job_id=os.environ['SLURM_JOB_ID'], pid=os.getpid(),
                   hostname=os.uname().nodename,
                   restart_count=int(os.environ.get('SLURM_RESTART_COUNT', 0)),
                   started_unix=time.time(), completed_tasks=done)
    probe = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,uuid', '--format=csv,noheader'],
                           text=True, capture_output=True, check=True)
    receipt['gpu'] = probe.stdout.strip()
    if len(probe.stdout.strip().splitlines()) != 1 or 'H200' not in probe.stdout:
        raise RuntimeError('Expected exactly one assigned H200')
    while True:
        queue = json.loads(Path(args.queue).read_text())
        next_task = None
        for task in queue['tasks']:
            signature = hashlib.sha256(json.dumps(task, sort_keys=True).encode()).hexdigest()
            if task['id'] in done:
                if done[task['id']]['task_sha256'] != signature:
                    raise RuntimeError('Completed task changed in dispatch queue')
                continue
            next_task = (task, signature)
            break
        if next_task:
            task, signature = next_task
            for pin in task['pins']:
                body = Path(pin['path']).read_bytes()
                if hashlib.sha256(body).hexdigest() != pin['sha256']:
                    raise RuntimeError('Task source or manifest pin changed: ' + pin['path'])
            manifest = json.loads(Path(task['sealed_manifest']).read_text())
            if manifest.get('status') not in ('sealed', 'frozen'):
                raise RuntimeError('Task requires sealed expansion manifest')
            command = task['command']
            if len(command) < 2 or command[1] not in ('scripts/expanded_likelihood.py', 'scripts/expanded_encode_edits.py'):
                raise RuntimeError('Unapproved GPU task entrypoint')
            receipt.update(status='running', task_id=task['id'], last_check_unix=time.time())
            atomic(state_path, receipt)
            started = time.time()
            result = subprocess.run(command)
            if result.returncode:
                receipt.update(status='failed', returncode=result.returncode, last_check_unix=time.time())
                atomic(state_path, receipt)
                raise SystemExit(result.returncode)
            done[task['id']] = dict(task_sha256=signature, seconds=time.time()-started,
                                   finished_unix=time.time(), job_id=os.environ['SLURM_JOB_ID'])
            receipt['completed_tasks'] = done
            atomic(state_path, receipt)
        elif queue.get('finish'):
            receipt.update(status='complete', last_check_unix=time.time())
            atomic(state_path, receipt)
            return
        else:
            receipt.update(status='waiting', queue_status=queue.get('status'), last_check_unix=time.time())
            atomic(state_path, receipt)
            time.sleep(15)


if __name__ == '__main__':
    main()
