"""Resumable development-only J++ token-rank diagnostics on a frozen pool."""

import argparse
from collections import defaultdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, payload):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="configs/runtime.json")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--fresh-index", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--lens", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--n", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.n <= 32:
        raise ValueError("Nested candidate prefix must be1..32")
    runtime = json.loads(Path(args.runtime).read_text())
    allowed = {str(job["job_id"]) for job in runtime["gpu_allocations"]+runtime.get("preemptable_allocations", [])}
    if os.environ.get("SLURM_JOB_ID") not in allowed:
        raise RuntimeError("J++ diagnostic requires an assigned GPU allocation")
    manifest = json.loads(Path(args.manifest).read_text())
    cells = manifest["cells"]
    if any(cell.get("split") not in ("dev", "development") for cell in cells):
        raise ValueError("J++ fitting overlap is unresolved: development cells only")
    fixture = json.loads(Path(args.fixture).read_text())
    from olens_improve.independent import JPP_SOURCE_REVISION
    if fixture.get("passed") is not True or fixture.get("source_revision") != JPP_SOURCE_REVISION:
        raise ValueError("J++ source fixture has not passed")
    checksum = hashlib.sha256()
    with Path(args.lens).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b""):
            checksum.update(chunk)
    if checksum.hexdigest() != fixture.get("lens_sha256"):
        raise ValueError("J++ checkpoint differs from the validated source fixture")
    fresh = {row["cell_id"]: row for row in json.loads(Path(args.fresh_index).read_text())["cells"]}
    candidates = defaultdict(dict)
    wanted = {cell["cell_id"] for cell in cells}
    if len(wanted) != len(cells):
        raise ValueError("Duplicate stage manifest cells")
    for line in Path(args.candidates).read_text().splitlines():
        row = json.loads(line)
        if row["cell_id"] in wanted and row["sample_index"] < args.n:
            if row["sample_index"] in candidates[row["cell_id"]]:
                raise ValueError("Duplicate candidate sample index")
            candidates[row["cell_id"]][row["sample_index"]] = row
    if any(set(candidates[cell]) != set(range(args.n)) for cell in wanted):
        raise ValueError("Incomplete frozen candidate prefixes")
    config = {"scope": "development_diagnostic_only", "fitting_overlap": "unresolved",
              "manifest_sha256": sha(args.manifest), "fresh_index_sha256": sha(args.fresh_index),
              "candidates_sha256": sha(args.candidates), "fixture_sha256": sha(args.fixture),
              "n": args.n, "mention_policy": "source_numbers_and_capitalized_spans_v1",
              "token_variants": "standalone_and_one_leading_space", "vocabulary_filter": "none",
              "lens_revision": "6c96867a91c43c14cec17cf0f6d157b933c5fee5", "lens_path": args.lens}
    output = Path(args.output);output.mkdir(parents=True, exist_ok=True)
    lock = (output / "writer.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    config_path = output / "run.json"
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError("Diagnostic source configuration changed; choose another immutable run")
    atomic(config_path, config)
    journal = output / "diagnostics.jsonl"
    completed = set()
    if journal.exists():
        with journal.open("rb+") as stream:
            valid_end = 0
            while line := stream.readline():
                if not line.endswith(b"\n"):
                    stream.truncate(valid_end)
                    atomic(output / "recovery.json", {"lost_uncommitted_bytes": len(line), "unknown_lost_compute": True})
                    break
                row = json.loads(line)
                if row["cell_id"] in completed:
                    raise ValueError("Duplicate diagnostic cell record")
                completed.add(row["cell_id"])
                valid_end = stream.tell()
    if not completed <= wanted:
        raise ValueError("Diagnostic journal contains unrelated cells")
    stopping = {"value": False}
    signal.signal(signal.SIGTERM, lambda *_: stopping.update(value=True))
    import torch
    from safetensors import safe_open
    from transformers import AutoTokenizer
    from olens_improve.independent import FrozenJPP, token_support, vocabulary_summary
    torch.set_num_threads(4)
    tok = AutoTokenizer.from_pretrained(runtime["paths"]["base_snapshot"], local_files_only=True)
    reader = FrozenJPP.load(args.lens, runtime["paths"]["base_snapshot"], sorted({cell["layer"] for cell in cells}))
    with journal.open("a") as stream:
        for cell in sorted(cells, key=lambda row: row["cell_id"]):
            if stopping["value"]:
                break
            if cell["cell_id"] in completed:
                continue
            row = fresh[cell["cell_id"]]
            if row.get("adapter_disabled") is not True:
                raise ValueError("J++ requires adapter-free target activations")
            with safe_open(row["activation_tensor_path"], framework="pt") as source:
                activation = source.get_slice(row["activation_tensor_key"])[row["activation_row"]].float()
            activation_sha = hashlib.sha256(activation.numpy().tobytes()).hexdigest()
            if activation_sha != row["activation_sha256"]:
                raise ValueError("Fresh activation source changed")
            source_samples = list(candidates[cell["cell_id"]].values())
            if any(sample["activation_sha256"] != activation_sha for sample in source_samples):
                raise ValueError("Candidate pool and J++ target differ")
            begin = time.monotonic()
            logits = reader.logits(activation, cell["layer"])
            prepared = vocabulary_summary(logits, tok)
            supports = [{"sample_index": sample["sample_index"], "source_pool_id": sample["pool_id"],
                         "text_sha256": hashlib.sha256(sample["text"].encode()).hexdigest(),
                         "diagnostic": token_support(logits, sample["text"], tok, prepared=prepared)}
                        for sample in sorted(source_samples, key=lambda sample: sample["sample_index"])]
            result = {key: cell[key] for key in ("cell_id", "family", "item_id", "layer", "position", "split")} | {
                "activation_sha256": activation_sha, "samples": supports, "seconds": time.monotonic()-begin,
                "scope": "development_diagnostic_only", "fitting_overlap": "unresolved", "job_id": os.environ["SLURM_JOB_ID"]}
            stream.write(json.dumps(result, ensure_ascii=False)+"\n");stream.flush();os.fsync(stream.fileno())
            completed.add(cell["cell_id"])
            atomic(output / "status.json", {"completed_cells": len(completed), "expected_cells": len(cells),
                   "state": "running", "job_id": os.environ["SLURM_JOB_ID"]})
    atomic(output / "status.json", {"completed_cells": len(completed), "expected_cells": len(cells),
           "state": "complete" if completed == wanted else "interrupted", "journal_sha256": sha(journal),
           "job_id": os.environ["SLURM_JOB_ID"]})


if __name__ == "__main__":
    main()
