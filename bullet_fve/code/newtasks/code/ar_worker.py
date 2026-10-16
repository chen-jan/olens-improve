"""AR encoding of every bullet of every completed generation journal (GPU), via OI unchanged.

Calls OI/scripts/encode_candidates.encode_snapshot once per completed shard journal (parse
source_contiguous_dash_blocks_v1, first 4 bullets, 256-token cap, ar_token_ids cleanup, 32-token
span, FrozenAR.encode_mixed, ar_cache.vector_key, usage provenance), with the OI production
settings batch_size=128, shard_size=16384, max_output_tokens=256. One cache root
(data/vectors/<contract[:20]>); encode_snapshot's own flock makes it single-writer, so a second
worker gets BlockingIOError and simply skips AR. Completed 16,384-vector shards are kept on restart.
The P0 pool is judged as raw text and is not AR-encoded.

CLI: ar_worker.py contract   (CPU: compute the vector contract digest, compare with OI's a451cf49...)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
AR_STAGES = ('ca', 'umA', 'umB')


def vectors_root() -> Path:
    return C.DATA / 'vectors'


def done_path() -> Path:
    return vectors_root() / 'ar_done.jsonl'


def contract_digest() -> tuple[str, dict]:
    """Same fields and order as encode_snapshot builds them (no model load)."""
    from olens_improve.ar_cache import digest
    from olens_improve.models import BASE_REVISION, PAIR_REVISION
    ck = C.AR_CKPT
    cfg = json.loads((ck / 'meta.json').read_text())['config']
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    contract = {'base_revision': BASE_REVISION, 'pair_revision': PAIR_REVISION,
                'head_sha256': h(ck / 'heads.pt'), 'meta_sha256': h(ck / 'meta.json'),
                'adapter_config_sha256': h(ck / 'lora/adapter_config.json'),
                'adapter_sha256': h(ck / 'lora/adapter_model.safetensors'),
                'tokenizer_revision': BASE_REVISION, 'tokenizer_cleanup': 'source_scaffolding_and_special_ids_v1',
                'span_limit': 32, 'padding': 'right_zero', 'head_layer_norm': cfg['head_layer_norm'],
                'head_layer_norm_epsilon': 1e-5, 'final_norm': 'Identity', 'backbone_dtype': 'bfloat16',
                'head_dtype': 'float32', 'key_policy': 'effective_scored_tokens_and_tag_v1'}
    return digest(contract), contract


def cache_dir() -> Path:
    return vectors_root() / C.OI_CONTRACT_SHA[:20]


def done_journals() -> dict:
    out = {}
    if done_path().exists():
        for row in C.read_jsonl(done_path()):
            out[(row['journal'], row['journal_sha256'])] = row
    return out


def pending_journals(stages=AR_STAGES) -> list[Path]:
    """Complete shard journals (status complete + sha match) not yet AR-encoded."""
    from gen_worker import shard_paths
    done = done_journals()
    out = []
    for stage in stages:
        _, _, count = C.STAGES[stage]
        for i in range(count):
            journal, status_path, _ = shard_paths(stage, i, count)
            if not status_path.exists():
                continue
            st = json.loads(status_path.read_text())
            if st.get('status') != 'complete':
                continue
            if (str(journal), st['journal_sha256']) in done:
                continue
            out.append(journal)
    return out


def encode_journal(journal: Path, ar=None, log=print):
    """-> (ar, record). Raises BlockingIOError when another AR writer holds the cache lock."""
    from encode_candidates import encode_snapshot
    args = SimpleNamespace(runtime=str(C.RUNTIME), input=[str(journal)], input_kind='candidates',
                           checkpoint=str(C.AR_CKPT), output=str(vectors_root()), batch_size=128,
                           shard_size=16384, max_output_tokens=256, analysis_manifest=None,
                           fresh_manifest=None, analysis_gate=None)
    t0 = time.time()
    ar = encode_snapshot(args, ar)
    contract = json.loads((cache_dir() / 'contract.json').read_text())
    if contract['sha256'] != C.OI_CONTRACT_SHA:
        raise RuntimeError(f'vector contract {contract["sha256"]} differs from OI {C.OI_CONTRACT_SHA}')
    progress = json.loads((cache_dir() / 'progress.json').read_text())
    rec = {'journal': str(journal), 'journal_sha256': C.file_sha(journal), 'usage_id': progress.get('usage_id'),
           'new_vectors': progress.get('new_vectors'), 'seconds': time.time() - t0,
           'job_id': os.environ.get('SLURM_JOB_ID'), 'finished_unix': time.time()}
    vectors_root().mkdir(parents=True, exist_ok=True)
    with done_path().open('a') as f:
        f.write(json.dumps(rec) + '\n')
        f.flush()
        os.fsync(f.fileno())
    log(f'AR done {journal.name}: {rec}')
    return ar, rec


if __name__ == '__main__':
    if sys.argv[1:] == ['contract']:
        d, contract = contract_digest()
        print(json.dumps({'digest': d, 'matches_oi': d == C.OI_CONTRACT_SHA}, indent=1))
    elif sys.argv[1:] == ['pending']:
        print(json.dumps([str(p) for p in pending_journals()], indent=1))
    else:
        raise SystemExit('usage: ar_worker.py contract|pending')
