"""Exclusive work claims that survive preemption/requeue on another node.

A claim is an O_EXCL file holding {token, pid, hostname, job, step, restart, heartbeat_unix}.
It is stale when (same host and pid dead) or (heartbeat older than STALE_SECONDS). A stale claim
is renamed away atomically (only one contender wins the rename), then re-created with O_EXCL.
A live owner re-verifies its token before every journal append (`still_owner`), so a wrongly
stolen claim stops the old owner instead of letting two writers interleave.
"""
from __future__ import annotations

import json
import os
import socket
import time
import uuid
from pathlib import Path

STALE_SECONDS = 600.0


def _info(extra=None):
    return {'token': uuid.uuid4().hex, 'pid': os.getpid(), 'hostname': socket.gethostname(),
            'job': os.environ.get('SLURM_JOB_ID'), 'step': os.environ.get('SLURM_STEP_ID'),
            'restart': os.environ.get('SLURM_RESTART_COUNT', '0'), 'created_unix': time.time(),
            'heartbeat_unix': time.time(), **(extra or {})}


def is_stale(info: dict, now: float | None = None, stale_seconds: float = STALE_SECONDS) -> bool:
    now = time.time() if now is None else now
    if info.get('hostname') == socket.gethostname():
        try:
            os.kill(int(info['pid']), 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        else:
            if int(info['pid']) == os.getpid():
                return False
    return now - float(info.get('heartbeat_unix', 0)) > stale_seconds


class Claim:
    def __init__(self, path: Path, info: dict):
        self.path, self.info = Path(path), info

    def still_owner(self) -> bool:
        try:
            return json.loads(self.path.read_text()).get('token') == self.info['token']
        except (FileNotFoundError, json.JSONDecodeError):
            return False

    def heartbeat(self, **extra) -> None:
        if not self.still_owner():
            raise RuntimeError(f'lost claim {self.path}')
        self.info.update(extra, heartbeat_unix=time.time())
        tmp = self.path.with_suffix(self.path.suffix + f'.{uuid.uuid4().hex[:8]}.tmp')
        tmp.write_text(json.dumps(self.info))
        os.replace(tmp, self.path)

    def release(self) -> None:
        if self.still_owner():
            self.path.unlink(missing_ok=True)


def try_claim(path, extra=None, stale_seconds: float = STALE_SECONDS) -> Claim | None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        info = _info(extra)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                old = json.loads(path.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                # mid-replace or vanished: treat as live; caller retries later
                return None
            if not is_stale(old, stale_seconds=stale_seconds):
                return None
            try:
                os.rename(path, path.with_name(path.name + f'.stale.{uuid.uuid4().hex[:8]}'))
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(fd, 'w') as f:
            json.dump(info, f)
        return Claim(path, info)
    return None
