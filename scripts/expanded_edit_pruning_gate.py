"""Bounded singleton CPU dispatcher for the four frozen round-two derivatives."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from expanded_cpu_cached import atomic, sha, committed_lines
from olens_improve.ar_cache import digest


FAMILIES = ('chain_intermediates', 'multihop_mt', 'hallucination', 'role_bound_association')
MENU = {(f'editing_round2_{suffix}_{threshold}', 32)
        for suffix in ('then_prune', 'random_delete_matched') for threshold in ('0.001', '0.005')}


def check_pins(pins):
    if any(sha(path) != value for path, value in pins.items()):
        raise ValueError('Frozen pruning source changed')


def verified_parent(folder, inventory_sha, inventory, own):
    status, spec, journal = (folder / name for name in ('status.json', 'spec.json', 'scored_candidates.jsonl'))
    terminal = json.loads(status.read_text()); contract = json.loads(spec.read_text())
    if terminal['status'] != 'complete' or terminal['round'] != 2 or terminal['cells'] != len(own):
        raise ValueError('Editor parent is not a terminal full-family source')
    if contract['round'] != 2 or contract['sealed_manifest_sha256'] != inventory_sha or contract['fresh_manifest_sha256'] != inventory['fresh_manifest']['sha256'] or contract['vector_contract'] != inventory['vector_contract']:
        raise ValueError('Foreign editor parent authority')
    body = journal.read_bytes()
    if not body.endswith(b'\n'):
        raise ValueError('Uncommitted editor parent journal')
    seen = set()
    for row in committed_lines(journal):
        cid = row['cell_id']
        if cid in seen or cid not in own or row['spec_sha256'] != digest(contract) or row['round'] != 2:
            raise ValueError('Duplicate/foreign editor parent event')
        if any(row[k] != own[cid][k] for k in ('family', 'item_id', 'layer', 'position', 'split', 'activation_sha256')):
            raise ValueError('Editor parent grid identity changed')
        seen.add(cid)
    if seen != set(own):
        raise ValueError('Editor parent grid incomplete')
    return {str(p): sha(p) for p in (status, spec, journal)}


def verified_export(ready, family, inventory_sha, own):
    d = json.loads(ready.read_text())
    if d.get('ready') is not True or d['family'] != family or d['inventory_sha256'] != inventory_sha or {(c['method'], c['n']) for c in d['conditions']} != MENU or d['cells'] != len(own):
        raise ValueError('Pruning descriptor menu/cohort differs')
    pins = {str(ready): sha(ready), d['manifest']: d['manifest_sha256'], d['selections']: d['selection_sha256']}
    pins.update({p['path']: p['sha256'] for p in d['source_parents']})
    check_pins(pins)
    terminal = json.loads(ready.with_name(f'{family}.status.json').read_text())
    if terminal.get('status') != 'complete' or terminal['completed_cells'] != len(own) or terminal['expected_cells'] != len(own):
        raise ValueError('Pruning descriptor lacks terminal production receipt')
    if terminal['selection_sha256'] != d['selection_sha256']:
        raise ValueError('Pruning terminal selection hash differs')
    return pins


def main():
    p = argparse.ArgumentParser(); p.add_argument('--pins', type=Path, required=True)
    p.add_argument('--pins-sha256', required=True); p.add_argument('--state', type=Path, required=True)
    p.add_argument('--max-watch-seconds', type=int, default=21600)
    p.add_argument('--python', required=True); a = p.parse_args()
    if os.environ.get('SLURM_JOB_ID') != '25536417':
        raise RuntimeError('Use the existing owned CPU allocation')
    if sha(a.pins) != a.pins_sha256:
        raise ValueError('Pruning gate authority changed')
    authority = json.loads(a.pins.read_text()); pins = authority['source_sha256']; check_pins(pins)
    inventory_path = Path('configs/expansion_manifest_v1.json'); inventory = json.loads(inventory_path.read_text()); inventory_sha = sha(inventory_path)
    cells = {c['cell_id']: c for c in json.loads(Path(inventory['fresh_manifest']['path']).read_text())['cells']}
    output = Path(inventory['artifact_root']) / 'selections' / 'editing-pruning-v1'
    parents = Path(inventory['artifact_root']) / 'editing-scores' / 'round2'
    lock = a.state.with_suffix('.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = {'status': 'waiting_for_round2_terminal', 'pid': os.getpid(), 'slurm_job_id': os.environ['SLURM_JOB_ID'],
        'started_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': pins, 'families': {},
        'output_root': str(output), 'new_model_calls': 0, 'new_api_calls': 0}
    started = time.monotonic()
    try:
        while len(state['families']) != len(FAMILIES):
            check_pins(pins)
            for family in FAMILIES:
                if family in state['families']: continue
                own = {cid: c for cid, c in cells.items() if c['family'] == family}
                ready = output / f'{family}.ready.json'
                if ready.exists():
                    state['families'][family] = {'status': 'complete_reused_missing_only', 'export_source_sha256': verified_export(ready, family, inventory_sha, own)}
                    continue
                folder = parents / family; status = folder / 'status.json'
                if not status.exists() or json.loads(status.read_text()).get('status') != 'complete': continue
                parent_pins = verified_parent(folder, inventory_sha, inventory, own)
                command = [a.python, 'scripts/expanded_edit_pruning.py', '--inventory-sha256', inventory_sha,
                    '--editing-source', str(folder), '--family', family, '--output', str(output), '--threads', '4']
                state.update(status='materializing_terminal_family', current_family=family, command=command,
                    parent_source_sha256=parent_pins, updated_utc=datetime.now(timezone.utc).isoformat()); atomic(a.state, state)
                with a.state.with_name(f'expanded-edit-pruning-v1-{family}.log').open('a') as log:
                    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
                if result.returncode: raise RuntimeError(f'Pruning {family} exited {result.returncode}; inspect family log')
                check_pins(pins); check_pins(parent_pins)
                state['families'][family] = {'status': 'complete', 'parent_source_sha256': parent_pins,
                    'export_source_sha256': verified_export(ready, family, inventory_sha, own)}
                print(json.dumps({'family': family, 'ready': str(ready), 'cells': len(own)}), flush=True)
            state.update(status='complete' if len(state['families']) == 4 else 'waiting_for_round2_terminal',
                updated_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-started)
            atomic(a.state, state)
            if state['status'] == 'complete': return
            if time.monotonic()-started >= a.max_watch_seconds:
                state['status'] = 'timeout_pending_families'; atomic(a.state, state); return
            time.sleep(20)
    except Exception as error:
        state.update(status='failed_pending_root_review', error=str(error), updated_utc=datetime.now(timezone.utc).isoformat())
        atomic(a.state, state); raise


if __name__ == '__main__': main()
