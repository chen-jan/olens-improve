"""Resumable, fixed-cell O-lens generation; run only after the coordinator gate.

One append-only journal per stable shard preserves generated strings immediately.
Prefix expansion appends indexes; it never regenerates persisted samples. Existing
instrument candidates can be imported verbatim into the same global sample pool.
"""

import argparse
from collections import defaultdict, deque
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import uuid

from olens_improve.models import BASE_REVISION, PAIR_REVISION


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(temporary, path)


def shard_for(cell_id, count):
    return int(sha(cell_id.encode()), 16) % count


def batch_seed(pool_id, cell_id, start, seed):
    return int(sha(canonical([pool_id, cell_id, start, seed]).encode())[:15], 16)


def add_records(state, records):
    affected = set()
    for record in records:
        cell_id, index = record["cell_id"], record["sample_index"]
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < 32:
            raise ValueError("Persisted sample index must be 0..31")
        samples = state.setdefault(cell_id, {})
        if index in samples:
            raise ValueError(f"Duplicate persisted sample: {cell_id}/{index}")
        samples[index] = record
        affected.add(cell_id)
    for cell_id in affected:
        samples = state[cell_id]
        if set(samples) != set(range(len(samples))):
            raise ValueError(f"Noncontiguous persisted sample prefix: {cell_id}")


def read_journal(path, pool_id, *, repair_tail=False):
    """Reject corruption; only a final unterminated crash fragment is repairable."""
    state = {}
    if not path.exists():
        return state
    good_bytes = 0
    with path.open("rb") as stream:
        for line in stream:
            if not line.endswith(b"\n"):
                if not repair_tail:
                    raise ValueError("Journal has an unterminated crash tail")
                break
            event = json.loads(line)
            if event["global_pool_id"] != pool_id:
                raise ValueError("Journal belongs to another global pool")
            add_records(state, event["records"])
            good_bytes += len(line)
    if repair_tail and path.stat().st_size != good_bytes:
        discarded = path.stat().st_size - good_bytes
        with path.with_suffix(path.suffix + ".recovery.jsonl").open("a") as recovery:
            recovery.write(canonical({"kind": "uncommitted_crash_tail", "discarded_bytes": discarded,
                "unknown_lost_compute": True, "stochastic_output_was_not_committed_or_used": True,
                "recovered_unix": time.time()}) + "\n")
        with path.open("r+b") as stream:
            stream.truncate(good_bytes)
            stream.flush()
            os.fsync(stream.fileno())
    return state


def append_event(stream, event, state):
    # Validate in an independent shadow first: malformed batches never reach disk.
    affected = {record["cell_id"] for record in event["records"]}
    shadow = {key: dict(state.get(key, {})) for key in affected}
    add_records(shadow, event["records"])
    stream.write(canonical(event) + "\n")
    stream.flush()
    os.fsync(stream.fileno())
    state.update(shadow)


@contextmanager
def claim(path, *, recover_dead=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and recover_dead:
        old = json.loads(path.read_text())
        if old.get("hostname") != socket.gethostname():
            raise RuntimeError("Cross-node stale claim needs coordinator verification/removal")
        try:
            os.kill(old["pid"], 0)
        except ProcessLookupError:
            path.unlink()
        else:
            raise RuntimeError("Previous worker is still alive")
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"pid": os.getpid(), "hostname": socket.gethostname(),
                   "job_id": os.environ.get("SLURM_JOB_ID"), "created_unix": time.time()}, stream)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def check_gate(gate):
    if gate.get("recapture_status") != "passed" or gate.get("production_generation_authorized") is not True:
        raise RuntimeError("Require passed recapture and explicit coordinator production authorization")


def import_records(path, cells, pool_id, state, stream, activation_hash):
    if path is None:
        return
    selected = {cell["cell_id"] for cell in cells}
    source_bytes = Path(path).read_bytes()
    source_sha = sha(source_bytes)
    source_run_path = Path(path).parent / "run.json"
    generation = {}
    source_run_sha = None
    if source_run_path.exists():
        source_run_bytes = source_run_path.read_bytes()
        source_run_sha = sha(source_run_bytes)
        generation = {record["cell_id"]: record for record in json.loads(source_run_bytes).get("generation", [])}
    original_hashes = {}
    source_capture = Path(path).parent / "activations.safetensors"
    source_audit = Path(path).parent / "capture_audit.json"
    if source_capture.exists() and source_audit.exists():
        from safetensors import safe_open
        with safe_open(source_capture, framework="pt") as tensors:
            for index, row in enumerate(json.loads(source_audit.read_text())["cells"]):
                if row["cell_id"] in selected:
                    original_hashes[row["cell_id"]] = sha(tensors.get_slice("resid")[index].float().numpy().tobytes())
    by_cell = {}
    for line in source_bytes.decode().splitlines():
        row = json.loads(line)
        if row["cell_id"] not in selected:
            continue
        if row["base_revision"] != BASE_REVISION or row["adapter_revision"] != PAIR_REVISION:
            raise ValueError("Imported candidate has incompatible model revisions")
        by_cell.setdefault(row["cell_id"], []).append(row)
    for cell_id, rows in by_cell.items():
        rows.sort(key=lambda row: row["sample_index"])
        imported = {}
        add_records(imported, rows)
        target_hash = activation_hash(cell_id)
        for row in rows:
            original_hash = row.get("activation_sha256", original_hashes.get(cell_id))
            if original_hash is None or original_hash != target_hash:
                raise ValueError("Imported candidates do not match the exact fresh FP32 target activation")
        existing = state.get(cell_id, {})
        for row in rows:
            if row["sample_index"] in existing and existing[row["sample_index"]]["text"] != row["text"]:
                raise ValueError("Imported sample conflicts with a persisted string")
        missing = [row | {"global_pool_id": pool_id, "imported_from": str(path), "activation_sha256": target_hash}
                   for row in rows if row["sample_index"] not in existing]
        if missing:
            append_event(stream, {"global_pool_id": pool_id, "kind": "verbatim_import",
                                 "source": str(path), "source_sha256": source_sha,
                                 "source_run_sha256": source_run_sha,
                                 "generation": generation.get(cell_id),
                                 "records": missing}, state)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="configs/runtime.json")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--n", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--cells-per-batch", type=int, default=4)
    parser.add_argument("--maximum-batch-sequences", type=int, default=128)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--fresh-activations")
    parser.add_argument("--fresh-audit")
    parser.add_argument("--fresh-index")
    parser.add_argument("--capture-version", required=True)
    parser.add_argument("--import-pool")
    parser.add_argument("--recover-dead-claim", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.n not in (1, 2, 4, 8, 16, 32) or not 1 <= args.batch_size <= 32:
        raise ValueError("N must be a shared nested prefix up to 32; batch size must be 1..32")
    if not 1 <= args.cells_per_batch <= 128 or not 1 <= args.maximum_batch_sequences <= 128:
        raise ValueError("Cell batching must be bounded by at most 128 output sequences")
    if not 0 <= args.shard_index < args.shard_count or args.max_new_tokens != 256:
        raise ValueError("Invalid shard index/count or deviation from frozen raw output-token limit")
    if bool(args.fresh_activations) != bool(args.fresh_audit):
        raise ValueError("Fresh tensor and audit must be provided together")
    if args.fresh_index and args.fresh_activations:
        raise ValueError("Use a fresh index or the single-tensor audit pair, not both")
    runtime = json.loads(Path(args.runtime).read_text())
    manifest_bytes = Path(args.manifest).read_bytes()
    manifest = json.loads(manifest_bytes)
    has_test = manifest.get("split") == "test" or any(cell.get("split") == "test" for cell in manifest["cells"])
    if has_test and not manifest.get("frozen_test_authorized", False):
        raise ValueError("Any test cell requires a frozen-test authorization")
    if len({cell["cell_id"] for cell in manifest["cells"]}) != len(manifest["cells"]):
        raise ValueError("Duplicate manifest cells")
    gate = json.loads(Path(args.gate).read_text())
    check_gate(gate)
    if gate.get("dry_run_only") and not args.validate_only:
        raise ValueError("A dry-run-only gate cannot authorize GPU generation")
    if gate.get("capture_version") != args.capture_version:
        raise ValueError("Coordinator gate does not authorize this capture version")
    if has_test and not gate.get("frozen_test_authorized", False):
        raise ValueError("Coordinator gate does not authorize test cells")
    if gate.get("manifest_sha256") != sha(manifest_bytes):
        raise ValueError("Coordinator gate does not authorize this exact manifest")
    if gate.get("authorized_cells", len(manifest["cells"])) != len(manifest["cells"]):
        raise ValueError("Coordinator gate cell count differs")
    if args.n > gate.get("maximum_samples_per_cell", 32):
        raise ValueError("Requested prefix exceeds the gate's sample limit")
    if args.fresh_index and gate.get("fresh_index_sha256") != file_sha(args.fresh_index):
        raise ValueError("Fresh index does not match the coordinator's frozen hash")
    cells = [cell for cell in manifest["cells"] if shard_for(cell["cell_id"], args.shard_count) == args.shard_index]
    fresh = {}
    if args.fresh_audit:
        for index, row in enumerate(json.loads(Path(args.fresh_audit).read_text())["cells"]):
            if row.get("adapter_disabled") is not True or row.get("generation_activation_source") != "fresh_recapture":
                raise ValueError("Fresh activation audit is missing adapter-free provenance")
            if row["cell_id"] in fresh:
                raise ValueError("Duplicate fresh audit cell")
            fresh[row["cell_id"]] = {"path": args.fresh_activations, "key": "resid", "row": index}
    if args.fresh_index:
        source = Path(args.fresh_index).read_text()
        if source.lstrip().startswith("{"):
            try:
                payload = json.loads(source)
                rows = payload["cells"]
            except (json.JSONDecodeError, KeyError):
                rows = [json.loads(line) for line in source.splitlines()]
        elif source.lstrip().startswith("["):
            rows = json.loads(source)
        else:
            raise ValueError("Fresh index must be JSON cells or JSONL")
        for row in rows:
            if row.get("adapter_disabled") is not True or row.get("generation_activation_source") != "fresh_recapture":
                raise ValueError("Fresh index lacks adapter-free capture provenance")
            if row["cell_id"] in fresh:
                raise ValueError("Duplicate fresh index cell")
            fresh[row["cell_id"]] = {"path": row["activation_tensor_path"],
                "key": row.get("activation_tensor_key", "resid"), "row": row["activation_row"],
                "expected_sha256": row.get("activation_sha256")}
    if not gate.get("historical_cache_reuse_authorized", False) and any(cell["cell_id"] not in fresh for cell in cells):
        raise ValueError("Cells lack fresh capture; historical cache reuse is not authorized")
    configuration = {
        "schema_version": 1, "base_revision": BASE_REVISION,
        "adapter_revision": PAIR_REVISION,
        "seed": args.seed, "max_new_tokens": args.max_new_tokens,
        "temperature": 1.0, "top_p": 0.95, "top_k": 64,
        "shard_count": args.shard_count, "maximum_shared_samples_per_cell": 32,
        "capture_version": args.capture_version,
    }
    launch = {"manifest_sha256": sha(manifest_bytes), "gate_sha256": sha(Path(args.gate).read_bytes()),
        "batch_size": args.batch_size, "target_n": args.n, "shard_index": args.shard_index,
        "cells_per_batch": args.cells_per_batch, "maximum_batch_sequences": args.maximum_batch_sequences,
        "fresh_index": args.fresh_index, "fresh_activations": args.fresh_activations,
        "fresh_audit": args.fresh_audit, "adapter_path": str(Path(args.adapter).resolve())}
    repository = Path(__file__).resolve().parents[1]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, text=True,
                              capture_output=True, timeout=10)
    launch["code_commit"] = revision.stdout.strip() if revision.returncode == 0 else None
    launch["source_hashes"] = {name: file_sha(repository / name) for name in (
        "scripts/generate_samples.py", "src/olens_improve/models.py", "src/olens_improve/sampling.py")}
    pool_id = sha(canonical(configuration).encode())[:24]
    if args.validate_only:
        print(json.dumps({"global_pool_id": pool_id, "shard_index": args.shard_index,
                          "cell_count": len(cells), "target_n": args.n, "launch": False}))
        return
    job = os.environ.get("SLURM_JOB_ID")
    if job not in {str(row["job_id"]) for row in runtime["gpu_allocations"] + runtime.get("preemptable_allocations", [])}:
        raise RuntimeError("Generation requires a verified user GPU allocation")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    # Hard-link publication makes creation exclusive across independent workers.
    config_path = output / "pool.json"
    temporary = output / f"pool.{uuid.uuid4().hex}.tmp"
    temporary.write_text(json.dumps(configuration | {"global_pool_id": pool_id}, indent=2) + "\n")
    try:
        os.link(temporary, config_path)
    except FileExistsError:
        if json.loads(config_path.read_text()) != configuration | {"global_pool_id": pool_id}:
            raise ValueError("Existing pool configuration differs; do not replace stochastic samples")
    finally:
        temporary.unlink(missing_ok=True)
    stem = f"shard-{args.shard_index:03d}-of-{args.shard_count:03d}"
    journal = output / (stem + ".jsonl")
    status_path = output / (stem + ".status.json")
    claim_path = Path(runtime["paths"]["fast"]) / "claims" / f"{pool_id}-{stem}.json"
    stopping = {"value": False}
    signal.signal(signal.SIGTERM, lambda *_: stopping.update(value=True))
    signal.signal(signal.SIGINT, lambda *_: stopping.update(value=True))
    with claim(claim_path, recover_dead=args.recover_dead_claim):
        state = read_journal(journal, pool_id, repair_tail=True)
        from safetensors import safe_open
        cells_by_id = {cell["cell_id"]: cell for cell in cells}

        def get_activation(cell_id):
            cell = cells_by_id[cell_id]
            source = fresh.get(cell_id, {"path": cell.get("cache_tensor_path"),
                "key": cell.get("cache_tensor_key"), "row": cell.get("cache_row")})
            with safe_open(source["path"], framework="pt") as tensors:
                activation = tensors.get_slice(source["key"])[source["row"]].float()
            activation_sha = sha(activation.numpy().tobytes())
            if source.get("expected_sha256") not in (None, activation_sha):
                raise ValueError("Fresh activation differs from its frozen hash")
            return activation, activation_sha

        with journal.open("a") as stream:
            import_records(args.import_pool, cells, pool_id, state, stream,
                           lambda cell_id: get_activation(cell_id)[1])
            stream.write(canonical({"global_pool_id": pool_id, "kind": "launch", "job_id": job,
                "launch": launch, "records": []}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            if any(set(samples) != set(range(len(samples))) for samples in state.values()):
                raise ValueError("Resume sample prefixes are inconsistent")
            remaining = [cell for cell in cells if len(state.get(cell["cell_id"], {})) < args.n]
            for cell in cells:
                if cell["cell_id"] in state:
                    target_hash = get_activation(cell["cell_id"])[1]
                    if any(row.get("activation_sha256") != target_hash for row in state[cell["cell_id"]].values()):
                        raise ValueError("Persisted samples were generated from a different target activation")
            lens = None
            if remaining:
                from olens_improve.models import FrozenOLens
                lens = FrozenOLens.load(runtime["paths"]["base_snapshot"], args.adapter)
                lens.merge()
            from olens_improve.sampling import sample_many
            import torch
            buckets = defaultdict(deque)
            for cell in sorted(remaining, key=lambda value: value["cell_id"]):
                start = len(state.get(cell["cell_id"], {}))
                count = min(args.batch_size, args.n - start)
                buckets[(cell["layer"], start, count)].append(cell)
            while buckets and not stopping["value"]:
                layer, start, count = key = min(buckets)
                bucket = buckets[key]
                row_limit = min(args.cells_per_batch, args.maximum_batch_sequences // count)
                if row_limit == 0:
                    raise ValueError("Per-cell batch exceeds total batch sequence allowance")
                batch_cells = [bucket.popleft() for _ in range(min(row_limit, len(bucket)))]
                if not bucket:
                    del buckets[key]
                captures = [get_activation(cell["cell_id"]) for cell in batch_cells]
                batch_ids = [cell["cell_id"] for cell in batch_cells]
                seed = batch_seed(pool_id, canonical(batch_ids), start, args.seed)
                begin = time.monotonic()
                if len(batch_cells) == 1:
                    flat, metadata = lens.sample(captures[0][0], layer, n=count, seed=seed,
                                                 max_new_tokens=args.max_new_tokens)
                    texts_by_cell = [flat]
                else:
                    texts_by_cell, metadata = sample_many(lens, torch.stack([capture[0] for capture in captures]),
                        layer, n_per_cell=count, seed=seed, max_new_tokens=args.max_new_tokens)
                if len(texts_by_cell) != len(batch_cells) or any(len(texts) != count for texts in texts_by_cell):
                    raise ValueError("Generator returned an incomplete batch")
                records = []
                for row_index, (cell, texts, (_, activation_sha)) in enumerate(zip(batch_cells, texts_by_cell, captures)):
                    for offset, text in enumerate(texts):
                        output_index = row_index * count + offset
                        records.append({name: cell[name] for name in ("cell_id", "family", "item_id", "layer", "position")} | {
                            "sample_index": start + offset, "text": text,
                            "token_count": metadata["token_counts"][output_index], "seed": seed,
                            "pool_id": pool_id, "global_pool_id": pool_id,
                            "truncated": metadata["truncated"][output_index],
                            "finish_reason": metadata["finish_reasons"][output_index],
                            "base_revision": BASE_REVISION, "adapter_revision": PAIR_REVISION,
                            "activation_sha256": activation_sha,
                        })
                append_event(stream, {"global_pool_id": pool_id, "kind": "generation",
                    "activation_hashes": {cell["cell_id"]: capture[1] for cell, capture in zip(batch_cells, captures)},
                    "activation_sources": {cell_id: "fresh_recapture" if cell_id in fresh else "authorized_historical_cache" for cell_id in batch_ids},
                    "cell_order": batch_ids, "batch_start": start, "samples_per_cell": count,
                    "batch_sequence_count": len(batch_cells)*count, "seconds": time.monotonic() - begin,
                    "generation": metadata, "launch": launch, "job_id": job, "records": records}, state)
                for cell in batch_cells:
                    next_start = len(state[cell["cell_id"]])
                    if next_start < args.n:
                        next_count = min(args.batch_size, args.n - next_start)
                        buckets[(layer, next_start, next_count)].append(cell)
                completed = sum(len(state.get(item["cell_id"], {})) >= args.n for item in cells)
                status = {"global_pool_id": pool_id, "job_id": job, "target_n": args.n,
                          "expected_cells": len(cells), "completed_cells": completed,
                          "persisted_samples": sum(len(values) for values in state.values()),
                          "updated_unix": time.time(), "status": "running"}
                atomic_json(status_path, status)
                atomic_json(claim_path, {"pid": os.getpid(), "hostname": socket.gethostname(),
                    "job_id": job, "heartbeat_unix": time.time(), "cell_ids": batch_ids,
                    "sample_prefix": start + count})
                print(json.dumps(status), flush=True)
            completed = sum(len(state.get(item["cell_id"], {})) >= args.n for item in cells)
            atomic_json(status_path, {"global_pool_id": pool_id, "job_id": job, "target_n": args.n,
                "expected_cells": len(cells), "completed_cells": completed,
                "persisted_samples": sum(len(values) for values in state.values()),
                "journal_path": str(journal), "journal_sha256": file_sha(journal),
                "updated_unix": time.time(), "status": "complete" if completed == len(cells) else "interrupted"})


if __name__ == "__main__":
    main()
