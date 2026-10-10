"""Freeze a flat, validated stage snapshot without changing the global pool."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--n", type=int, default=32)
    args = parser.parse_args()
    if not 1 <= args.n <= 32:
        raise ValueError("N must be1..32")
    pool = Path(args.pool)
    config = json.loads((pool / "pool.json").read_text())
    manifest = json.loads(Path(args.manifest).read_text())
    wanted = {row["cell_id"] for row in manifest["cells"]}
    if len(wanted) != len(manifest["cells"]):
        raise ValueError("Duplicate manifest cells")
    rows = {}; parents = {}; hashes = defaultdict(set)
    for journal in sorted(pool.glob("shard-*-of-*.jsonl")):
        status = json.loads(journal.with_suffix(".status.json").read_text())
        if status["status"] != "complete" or digest(journal) != status["journal_sha256"]:
            raise ValueError("Export requires immutable complete journal snapshots")
        parents[str(journal)] = status["journal_sha256"]
        for line in journal.read_text().splitlines():
            event = json.loads(line)
            if event["global_pool_id"] != config["global_pool_id"]:
                raise ValueError("Mixed global pools")
            for row in event.get("records", []):
                if row["cell_id"] not in wanted or row["sample_index"] >= args.n:
                    continue
                key = row["cell_id"], row["sample_index"]
                if key in rows:
                    raise ValueError("Duplicate source record")
                rows[key] = row
                hashes[row["cell_id"]].add(row["activation_sha256"])
    expected = {(cell, index) for cell in wanted for index in range(args.n)}
    if set(rows) != expected or any(len(values) != 1 for values in hashes.values()):
        raise ValueError("Incomplete sample prefixes or conflicting activation provenance")
    payload = "".join(json.dumps(rows[key], ensure_ascii=False, sort_keys=True) + "\n" for key in sorted(rows))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(payload)
    record = {"global_pool_id": config["global_pool_id"], "cells": len(wanted), "samples": len(rows),
        "n": args.n, "flat_sha256": digest(output), "flat_path": str(output),
        "cohort_manifest_sha256": digest(Path(args.manifest)), "parent_journal_sha256": parents,
        "scope": "cell_pilot", "split": manifest.get("split", "development")}
    output.with_suffix(".manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
