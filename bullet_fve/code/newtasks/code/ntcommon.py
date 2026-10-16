"""Shared paths, constants and small helpers for the newtasks (User modelling / Conjunctive
association) per-bullet FVE pipeline. Nothing here touches a GPU, the network or a secret.

All writes go under NT (= .../olens-bullet-fve/newtasks). Model artifacts are read-only.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
CODE = NT / 'code'
DATA = Path(os.environ.get('NT_DATA') or NT / 'data')  # NT_DATA: test fixtures only
OI = Path('${OLENS_REPO_ROOT}')
WSB = Path('${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2')
WSB_COMMIT = '92d763e722377f5bfae045e829a308ab5919a820'
RUNTIME = OI / 'configs/runtime.json'
PYTHON = '${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python'
BASE = Path('${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/'
            '6a9e13bd6fc8f0983b9b99948120bc37f49c13e9')
PAIR = Path('${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/models--agu18dec--olens_and_ar/'
            'snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc')
ADAPTER = PAIR / 'olens_s3d_rl600'
AR_CKPT = PAIR / 'ar_ptag_pooled'
WHITENERS = Path('${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/'
                 'snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners')
OI_CONTRACT_SHA = 'a451cf49d28ac74477229e74dfc738e51b8961b5376c688fd9e40abbd8c133b6'
SITES = NT / 'design/sites.jsonl'
LAYERS = (20, 36, 44, 52, 60)
FAMILIES = {'um': 'user_modeling', 'ca': 'conjunctive_association'}
SHORT = {v: k for k, v in FAMILIES.items()}
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
SETTING_LABEL = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32',
                 'pooled_greedy_swap-n32': 'Combine 32'}
SPLIT = 'nt'  # one pseudo split, so the hallucination-format extract/metric code carries over
SEED = 20261015

# Generation stages: name -> (family, n samples per cell, shard count). Order = priority.
STAGES = {
    'p0': ('user_modeling', 4, 1),
    'ca': ('conjunctive_association', 32, 4),
    'umA': ('user_modeling', 32, 4),
    'umB': ('user_modeling', 32, 1),
}
# Smoke runs only: NT_STAGES = JSON {stage: [family, n, shard_count]} replaces the table above. It is
# refused unless NT_DATA points at a separate (non-production) data root.
if os.environ.get('NT_STAGES'):
    if not os.environ.get('NT_DATA') or Path(os.environ['NT_DATA']).resolve() == (NT / 'data').resolve():
        raise RuntimeError('NT_STAGES needs NT_DATA set to a non-production data root')
    STAGES = {k: tuple(v) for k, v in json.loads(os.environ['NT_STAGES']).items()}


def control_path() -> Path:
    """data/control/stages.json = {"enabled": [...]}: which stages workers may generate."""
    return DATA / 'control/stages.json'


def setup_paths() -> None:
    """Import order: our code, OI src, OI scripts (pool_worker/generate_samples/...), WSB src."""
    for p in (str(WSB / 'src'), str(OI / 'scripts'), str(OI / 'src'), str(CODE)):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value) -> str:
    return sha(canonical(value).encode())


def file_sha(path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, payload, indent=1) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f'.{uuid.uuid4().hex[:8]}.tmp')
    tmp.write_text(json.dumps(payload, indent=indent, ensure_ascii=False) + '\n')
    os.replace(tmp, path)


def atomic_text(path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f'.{uuid.uuid4().hex[:8]}.tmp')
    tmp.write_text(text)
    os.replace(tmp, path)


def cell_id(family: str, item_id: str, layer: int, pos: int) -> str:
    """The hallucination-study cell id format."""
    return f'{family}|{item_id}|L{layer}|p{pos:05d}'


def load_sites(path=SITES) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def load_bank(family: str):
    data = json.loads((WSB / 'evals' / family / 'items.json').read_text())
    items = data['items'] if isinstance(data, dict) else data
    key = 'name' if family == 'user_modeling' else 'id'
    return {it[key]: it for it in items}


def stage_dir(stage: str) -> Path:
    return DATA / 'gen' / stage


def enabled_stages() -> list[str]:
    try:
        return list(json.loads(control_path().read_text())['enabled'])
    except FileNotFoundError:
        return []


def read_jsonl(path):
    with Path(path).open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
