"""Append-only, frozen N32 -> N256 Oracle Lens pilot (no capture or judging).

Use --validate-only before launch. Run generation inside the explicitly named
Slurm allocation. Baseline rows are copied verbatim; journal commits are entire
same-layer batches and remain the source of truth after interruption.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import threading
import time
import uuid

from olens_improve.models import BASE_REVISION, PAIR_REVISION, SUPPORTED_LAYERS

SCHEMA = "larger_n_sampling_pilot_v1"
RECIPE = {"temperature": 1.0, "top_p": 0.95, "top_k": 64,
          "max_new_tokens": 256, "n_per_call": 32}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, (canonical(value) + "\n").encode())


def batch_seed(manifest, cell_ids, start):
    return int(digest([SCHEMA, manifest["pilot_id"], manifest["pilot_seed"], cell_ids, start])[:15], 16)


def batch_plan(manifest):
    buckets = defaultdict(list)
    for cell in manifest["cells"]:
        buckets[cell["layer"]].append(cell["cell_id"])
    batches = []
    # Finish each complete prefix before proceeding to the next prefix.
    for start in range(32, manifest["target_n"], 32):
        for layer, ids in sorted(buckets.items()):
            ids = sorted(ids)
            for offset in range(0, len(ids), manifest["cells_per_batch"]):
                own = ids[offset:offset + manifest["cells_per_batch"]]
                batches.append({"batch_index": len(batches), "layer": layer,
                    "cell_order": own, "batch_start": start, "samples_per_cell": 32,
                    "seed": batch_seed(manifest, own, start)})
    return batches


def validate_manifest(manifest):
    if manifest.get("schema_version") != SCHEMA:
        raise ValueError(f"Expected schema_version={SCHEMA}")
    if not manifest.get("pilot_id") or type(manifest.get("pilot_seed")) is not int:
        raise ValueError("Require pilot_id and integer pilot_seed")
    if manifest.get("target_n") != 256 or manifest.get("chunk_size") != 32 or manifest.get("cells_per_batch") not in (4, 8):
        raise ValueError("This bounded pilot requires N256, chunk_size32, cells_per_batch4 or8")
    if manifest.get("sampling_recipe") != RECIPE:
        raise ValueError("Sampling recipe differs from the frozen contract")
    for key in ("base_snapshot", "adapter"):
        if not Path(manifest[key]).is_dir():
            raise ValueError(f"Missing local model directory: {key}")
    if manifest.get("base_revision") != BASE_REVISION or manifest.get("adapter_revision") != PAIR_REVISION:
        raise ValueError("Frozen model revisions differ")
    cells = manifest["cells"]
    expected_families = {"hallucination", "multihop_mt", "chain_intermediates", "role_bound_association"}
    if len(cells) != 32 or Counter(c["family"] for c in cells) != Counter({f: 8 for f in expected_families}):
        raise ValueError("Require balanced32 cells, eight per frozen family")
    state = {}
    for cell in cells:
        cid = cell["cell_id"]
        if cid in state or cell["layer"] not in SUPPORTED_LAYERS:
            raise ValueError("Duplicate cell or unsupported layer")
        if type(cell["activation_row"]) is not int or cell["activation_row"] < 0:
            raise ValueError("Invalid activation row")
        if not Path(cell["activation_tensor_path"]).is_file():
            raise ValueError("Missing frozen activation tensor")
        if len(cell["activation_sha256"]) != 64:
            raise ValueError("Missing target activation hash")
        rows = cell["baseline_samples"]
        if len(rows) != 32 or digest(rows) != cell["baseline_samples_sha256"]:
            raise ValueError("Baseline N32 source hash or count differs")
        if [r["sample_index"] for r in rows] != list(range(32)):
            raise ValueError("Baseline must retain exact ordered indices0..31")
        for row in rows:
            for field in ("cell_id", "family", "item_id", "layer", "position", "activation_sha256"):
                if row[field] != cell[field]:
                    raise ValueError(f"Baseline target mismatch: {field}")
            if row.get("base_revision") != BASE_REVISION or row.get("adapter_revision") != PAIR_REVISION:
                raise ValueError("Baseline frozen revisions differ")
            if not isinstance(row["text"], str):
                raise ValueError("Invalid baseline text")
        state[cid] = {r["sample_index"]: r for r in rows}
    return state


def validate_event(event, expected, manifest_sha, state, cells):
    if event.get("manifest_sha256") != manifest_sha:
        raise ValueError("Journal belongs to a different manifest")
    unsigned = {k: v for k, v in event.items() if k != "event_sha256"}
    if event.get("event_sha256") != digest(unsigned):
        raise ValueError("Journal event checksum mismatch")
    for key, value in expected.items():
        if event.get(key) != value:
            raise ValueError(f"Journal batch plan mismatch: {key}")
    records = event["records"]
    expected_ids = [(cid, i) for cid in expected["cell_order"]
                    for i in range(expected["batch_start"], expected["batch_start"] + 32)]
    if [(r["cell_id"], r["sample_index"]) for r in records] != expected_ids:
        raise ValueError("Journal batch incomplete, reordered, or duplicate")
    for row in records:
        cid, index = row["cell_id"], row["sample_index"]
        if index in state[cid] or len(state[cid]) != expected["batch_start"]:
            # Check against pre-transaction state; mutation happens below.
            raise ValueError("Duplicate or noncontiguous persisted prefix")
        if row["activation_sha256"] != cells[cid]["activation_sha256"]:
            raise ValueError("Journal target activation mismatch")
        for field in ("family", "item_id", "layer", "position"):
            if row[field] != cells[cid][field]:
                raise ValueError(f"Journal target identity mismatch: {field}")
        if row["seed"] != expected["seed"] or row["base_revision"] != BASE_REVISION or row["adapter_revision"] != PAIR_REVISION:
            raise ValueError("Journal model or seed mismatch")
    for row in records:
        state[row["cell_id"]][row["sample_index"]] = row


def read_journal(path, plan, manifest_sha, state, cells, *, repair_tail=True):
    """Only a final non-newline crash fragment can be quarantined and removed."""
    events = []
    if not path.exists():
        return events
    committed = 0
    with path.open("rb") as stream:
        for line in stream:
            if not line.endswith(b"\n"):
                if not repair_tail:
                    raise ValueError("Uncommitted journal tail")
                quarantine = path.with_name(path.name + f".tail-{uuid.uuid4().hex}.bin")
                atomic_bytes(quarantine, line)
                break
            if len(events) >= len(plan):
                raise ValueError("Journal exceeds authorized pilot budget")
            event = json.loads(line)
            validate_event(event, plan[len(events)], manifest_sha, state, cells)
            events.append(event)
            committed += len(line)
    if path.stat().st_size != committed:
        with path.open("r+b") as stream:
            stream.truncate(committed)
            stream.flush()
            os.fsync(stream.fileno())
    return events


def publish_prefixes(output, manifest, manifest_sha, state):
    for n in (64, 128, 256):
        if any(len(rows) < n for rows in state.values()):
            continue
        name = f"samples_n{n:03d}.jsonl"
        payload = "".join(canonical(state[cell["cell_id"]][i]) + "\n"
                          for cell in manifest["cells"] for i in range(n)).encode()
        path = output / name
        if path.exists() and path.read_bytes() != payload:
            raise ValueError("Published sample checkpoint differs from journal")
        if not path.exists():
            atomic_bytes(path, payload)
        atomic_json(output / f"samples_n{n:03d}.ready.json", {
            "manifest_sha256": manifest_sha, "pilot_id": manifest["pilot_id"],
            "n": n, "cells": len(state), "rows": len(state) * n,
            "samples_path": str(path.resolve()), "samples_sha256": hashlib.sha256(payload).hexdigest(),
            "baseline_rows_preserved": True})


def load_activations(cells):
    import torch
    from safetensors import safe_open
    result = {}
    for cell in cells:
        with safe_open(cell["activation_tensor_path"], framework="pt", device="cpu") as tensor:
            key = cell.get("activation_tensor_key", "resid")
            raw = tensor.get_slice(key)[cell["activation_row"]:cell["activation_row"] + 1][0].float()
        if raw.shape != (5120,) or not torch.isfinite(raw).all() or float(raw.norm()) <= 1e-8:
            raise ValueError("Invalid frozen activation")
        if hashlib.sha256(raw.numpy().tobytes()).hexdigest() != cell["activation_sha256"]:
            raise ValueError("Frozen target activation hash mismatch")
        result[cell["cell_id"]] = raw
    return result


def profile_batches(lens, output, manifest_sha, job, stopping):
    """Bounded synthetic throughput measurement, independent of study cells."""
    import gc
    import torch
    from olens_improve.sampling import sample_many
    generator = torch.Generator(device="cpu").manual_seed(740192)
    vectors = torch.randn((8, 5120), generator=generator)
    report = {"synthetic_only": True, "quality_evaluation": False,
        "manifest_sha256": manifest_sha, "job_id": job, "layer": 44,
        "vector_seed": 740192, "sampling_recipe": RECIPE,
        "gpu_name": torch.cuda.get_device_name(), "cases": [],
        "production_cells_per_batch_changed": False}
    for name, rows, seed in (("warmup_1", 1, 901), ("warmup_2", 1, 902),
                             ("batch_128", 4, 903), ("batch_256", 8, 904)):
        if stopping.is_set():
            report["interrupted"] = True
            break
        if rows == 8 and any(c["name"] == "batch_128" and c["status"] == "oom" for c in report["cases"]):
            report["cases"].append({"name": name, "input_rows": rows,
                "sequences": rows * 32, "status": "skipped_after_128_oom"})
            break
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        begin = time.monotonic()
        case = {"name": name, "input_rows": rows, "sequences": rows * 32,
                "seed": seed, "samples_per_cell": 32}
        try:
            texts, metadata = sample_many(lens, vectors[:rows], 44,
                n_per_cell=32, seed=seed, max_new_tokens=256)
            torch.cuda.synchronize()
            seconds = time.monotonic() - begin
            tokens = sum(metadata["token_counts"])
            case.update(status="complete", seconds=seconds, generated_tokens=tokens,
                tokens_per_second=tokens / seconds, sequences_per_second=rows * 32 / seconds,
                padded_batch_width=metadata["padded_batch_width"],
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_reserved_bytes=torch.cuda.max_memory_reserved())
            del texts, metadata
        except torch.cuda.OutOfMemoryError as error:
            case.update(status="oom", seconds=time.monotonic() - begin,
                error=str(error), peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_reserved_bytes=torch.cuda.max_memory_reserved())
        # Release failure traceback temporaries before clearing cached blocks.
        gc.collect()
        torch.cuda.empty_cache()
        report["cases"].append(case)
        atomic_json(output / "profile.json", report)
        print(canonical(case), flush=True)
        if case["status"] == "oom" and rows == 1:
            break
    measured = {c["name"]: c for c in report["cases"] if c["status"] == "complete"}
    smaller, larger = measured.get("batch_128"), measured.get("batch_256")
    report["recommended_cells_per_batch"] = (8 if smaller and larger and
        larger["tokens_per_second"] > smaller["tokens_per_second"] else 4 if smaller else None)
    if smaller and larger:
        report["tokens_per_second_ratio_256_over_128"] = larger["tokens_per_second"] / smaller["tokens_per_second"]
    report["limitation"] = "One synthetic timed case per batch size; real-cell throughput can differ. Production requires a separately frozen manifest."
    atomic_json(output / "profile.json", report)
    return report


def run(args):
    manifest_bytes = Path(args.manifest).read_bytes()
    manifest = json.loads(manifest_bytes)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    state = validate_manifest(manifest)
    cells = {c["cell_id"]: c for c in manifest["cells"]}
    plan = batch_plan(manifest)
    if args.validate_only:
        print(canonical({"valid": True, "manifest_sha256": manifest_sha,
            "cells": len(cells), "batches": len(plan), "new_readouts": len(cells) * 224,
            "model_loaded": False, "sampling_recipe": RECIPE}), flush=True)
        return 0
    job = os.environ.get("SLURM_JOB_ID")
    authorized_jobs = {str(value) for value in manifest.get("authorized_job_ids", [])}
    if not args.allowed_job_id or job != str(args.allowed_job_id) or job not in authorized_jobs:
        raise RuntimeError("Generation requires the explicitly authorized Slurm job ID")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    lock = (output / "writer.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    frozen = output / "manifest.json"
    if frozen.exists() and frozen.read_bytes() != manifest_bytes:
        raise ValueError("Output directory binds another manifest")
    if not frozen.exists():
        atomic_bytes(frozen, manifest_bytes)
    journal = output / "batch_journal.jsonl"
    events = read_journal(journal, plan, manifest_sha, state, cells)
    publish_prefixes(output, manifest, manifest_sha, state)
    stopping = threading.Event()
    finished = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):
        signal.signal(sig, lambda *_: stopping.set())
    started = time.monotonic()
    status = {"pilot_id": manifest["pilot_id"], "manifest_sha256": manifest_sha,
        "job_id": job, "pid": os.getpid(), "status": "loading", "batches_total": len(plan),
        "batches_committed": len(events), "new_samples_committed": sum(len(e["records"]) for e in events),
        "generated_tokens": sum(e.get("generated_tokens", 0) for e in events),
        "generation_seconds": sum(e.get("seconds", 0) for e in events),
        "peak_allocated_bytes": max((e.get("peak_allocated_bytes", 0) for e in events), default=0),
        "peak_reserved_bytes": max((e.get("peak_reserved_bytes", 0) for e in events), default=0),
        "baseline_samples": 1024}

    def heartbeat():
        while not finished.is_set():
            atomic_json(output / "status.json", dict(status, updated_unix=time.time(),
                wall_seconds=time.monotonic() - started, stop_requested=stopping.is_set()))
            finished.wait(10)
    worker = threading.Thread(target=heartbeat, daemon=True)
    worker.start()
    try:
        if args.profile_only or len(events) < len(plan):
            import torch
            from olens_improve.models import FrozenOLens
            from olens_improve.sampling import sample_many
            activations = None if args.profile_only else load_activations(manifest["cells"])
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA required for authorized GPU pilot")
            load_started = time.monotonic()
            lens = FrozenOLens.load(manifest["base_snapshot"], manifest["adapter"])
            merge_drift = lens.merge()
            status.update(model_load_seconds=time.monotonic() - load_started,
                adapter_delta=lens.adapter_delta, merge_drift=merge_drift,
                gpu_name=torch.cuda.get_device_name(), status="sampling")
            atomic_json(output / "model_receipt.json", dict(status, base_revision=BASE_REVISION,
                adapter_revision=PAIR_REVISION, sampling_recipe=RECIPE))
            if args.profile_only:
                if events:
                    raise ValueError("Profile-only requires an output directory without production events")
                status.update(status="profiling")
                profile = profile_batches(lens, output, manifest_sha, job, stopping)
                status.update(status="interrupted" if stopping.is_set() else "complete",
                    profile_only=True, recommended_cells_per_batch=profile["recommended_cells_per_batch"])
                return 143 if stopping.is_set() else 0
            with journal.open("a") as stream:
                for batch in plan[len(events):]:
                    if stopping.is_set():
                        break
                    status.update(current_batch=batch)
                    vectors = torch.stack([activations[cid] for cid in batch["cell_order"]])
                    torch.cuda.synchronize()
                    torch.cuda.reset_peak_memory_stats()
                    begin = time.monotonic()
                    texts, metadata = sample_many(lens, vectors, batch["layer"], n_per_cell=32,
                                                   seed=batch["seed"], max_new_tokens=256)
                    torch.cuda.synchronize()
                    seconds = time.monotonic() - begin
                    if len(texts) != len(batch["cell_order"]) or any(len(row) != 32 for row in texts):
                        raise ValueError("Incomplete sampled batch")
                    records = []
                    for row_index, cid in enumerate(batch["cell_order"]):
                        cell = cells[cid]
                        original = cell["baseline_samples"][0]
                        for offset, text in enumerate(texts[row_index]):
                            flat_index = row_index * 32 + offset
                            records.append({k: cell[k] for k in ("cell_id", "family", "item_id", "layer", "position", "activation_sha256")} | {
                                "sample_index": batch["batch_start"] + offset, "text": text,
                                "token_count": metadata["token_counts"][flat_index],
                                "truncated": metadata["truncated"][flat_index],
                                "finish_reason": metadata["finish_reasons"][flat_index],
                                "seed": batch["seed"], "base_revision": BASE_REVISION,
                                "adapter_revision": PAIR_REVISION,
                                "pool_id": original["pool_id"],
                                "global_pool_id": original.get("global_pool_id", original["pool_id"]),
                                "pilot_id": manifest["pilot_id"], "pilot_manifest_sha256": manifest_sha,
                                "split": cell.get("split"), "group_id": cell.get("group_id")})
                    event = dict(batch, manifest_sha256=manifest_sha, records=records,
                        generation=metadata, seconds=seconds, generated_tokens=sum(metadata["token_counts"]),
                        peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                        peak_reserved_bytes=torch.cuda.max_memory_reserved(), job_id=job)
                    event["event_sha256"] = digest(event)
                    # Validate against a shadow so an unsuccessful disk write cannot
                    # advance the committed in-memory state.
                    shadow = {cid: dict(rows) for cid, rows in state.items()}
                    validate_event(event, batch, manifest_sha, shadow, cells)
                    stream.write(canonical(event) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                    state = shadow
                    events.append(event)
                    status.update(batches_committed=len(events),
                        new_samples_committed=sum(len(e["records"]) for e in events),
                        generated_tokens=sum(e["generated_tokens"] for e in events),
                        generation_seconds=sum(e["seconds"] for e in events),
                        peak_allocated_bytes=max(e["peak_allocated_bytes"] for e in events),
                        peak_reserved_bytes=max(e["peak_reserved_bytes"] for e in events))
                    print(canonical(status), flush=True)
                    publish_prefixes(output, manifest, manifest_sha, state)
        status.update(status="complete" if len(events) == len(plan) else "interrupted")
    except BaseException as error:
        status.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        finished.set()
        worker.join()
        status.update(updated_unix=time.time(), wall_seconds=time.monotonic() - started)
        atomic_json(output / "status.json", status)
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    return 0 if status["status"] == "complete" else 143


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allowed-job-id")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--profile-only", action="store_true",
        help="Measure synthetic128/256 sequence batches after two32-sequence warmups; write no production journal")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
