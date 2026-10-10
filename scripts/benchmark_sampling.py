"""Bounded throughput-only synthetic-vector profiling; no core read cells."""

import argparse
import json
import os
from pathlib import Path
import time

import torch
from olens_improve.models import FrozenOLens
from olens_improve.sampling import sample_many


def save(path, payload):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="configs/runtime.json")
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    runtime = json.loads(Path(args.runtime).read_text())
    job = os.environ.get("SLURM_JOB_ID")
    if job not in {str(record["job_id"]) for record in runtime["gpu_allocations"]}:
        raise RuntimeError("Requires a verified main GPU allocation")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    lens = FrozenOLens.load(runtime["paths"]["base_snapshot"], args.adapter)
    drift = lens.merge()
    generator = torch.Generator().manual_seed(9147)
    # Seven independent synthetic cells: 32 + 64 + 128 sequences; never benchmark
    # core activations, extra captures, resampling, or semantic quality claims.
    vectors = torch.randn((7, 5120), generator=generator)
    cases = [("single_hf32", 0, 1), ("two_cells64", 1, 2), ("four_cells128", 3, 4)]
    results = []
    for name, start, count in cases:
        destination = output / f"{name}.json"
        if destination.exists():
            results.append(json.loads(destination.read_text()))
            continue
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        begin = time.monotonic()
        if count == 1:
            texts, metadata = lens.sample(vectors[start], 44, n=32, seed=900+start)
            texts = [texts]
        else:
            texts, metadata = sample_many(lens, vectors[start:start+count], 44,
                                          n_per_cell=32, seed=900+start)
        torch.cuda.synchronize()
        seconds = time.monotonic() - begin
        tokens = sum(metadata["token_counts"])
        result = {"case": name, "synthetic_only": True, "quality_evaluation": False,
            "layer": 44, "synthetic_vector_seed": 9147, "synthetic_rows": list(range(start, start+count)),
            "cells": count, "samples_per_cell": 32, "sequences": count*32,
            "seconds": seconds, "generated_tokens": tokens, "tokens_per_second": tokens/seconds,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(), "metadata": metadata, "texts": texts,
            "job_id": job, "adapter_delta": lens.adapter_delta, "merge_drift": drift}
        save(destination, result)
        results.append(result)
        print(json.dumps({key: result[key] for key in ("case", "seconds", "generated_tokens", "tokens_per_second", "peak_allocated_bytes")}), flush=True)
    save(output / "summary.json", {"synthetic_only": True, "results": [
        {key: result[key] for key in ("case", "seconds", "generated_tokens", "tokens_per_second", "peak_allocated_bytes", "peak_reserved_bytes")} for result in results],
        "limitation": "Off-distribution synthetic activation profiling; calibrate the completion forecast on real development outputs."})


if __name__ == "__main__":
    main()
