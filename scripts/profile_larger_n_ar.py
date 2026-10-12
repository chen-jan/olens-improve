"""Bounded AR throughput/numerical diagnostic on frozen pilot baseline text."""
import argparse
from collections import Counter
import gc
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
from types import SimpleNamespace

from score_larger_n_pilot import atomic, sha, verify_contract
from olens_improve.ar_cache import digest
from olens_improve.reconstruction import FrozenAR, ar_token_ids
from olens_improve.selection import parse_bullets


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--allowed-job-id", required=True, action="append")
    p.add_argument("--runtime", type=Path)
    p.add_argument("--checkpoint", type=Path)
    a = p.parse_args()
    job = os.environ.get("SLURM_JOB_ID")
    if job not in a.allowed_job_id:
        raise RuntimeError("Use the explicitly authorized GPU allocation")
    import torch
    from transformers import AutoTokenizer
    torch.set_num_threads(min(4, int(os.environ.get("SLURM_CPUS_PER_TASK", "4"))))
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    manifest = json.loads(a.manifest.read_text())
    if job not in manifest["authorized_job_ids"]:
        raise ValueError("Job is outside the pilot manifest allowlist")
    runtime = a.runtime or Path(manifest["runtime_inputs"]["runtime"]["path"])
    checkpoint = a.checkpoint or Path(manifest["runtime_inputs"]["checkpoint"])
    base = manifest["base_snapshot"]
    if Path(json.loads(runtime.read_text())["paths"]["base_snapshot"]).resolve() != Path(base).resolve():
        raise ValueError("Runtime base differs from frozen pilot")
    verify_contract(SimpleNamespace(contract=manifest["vector_contract"]), checkpoint)
    tok = AutoTokenizer.from_pretrained(base, local_files_only=True)
    count = lambda text: len(tok(text, add_special_tokens=False)["input_ids"])
    unique = {}
    for cell in manifest["cells"]:
        for row in cell["baseline_samples"]:
            sample = parse_bullets(row["text"], f"{cell['cell_id']}:{row['sample_index']}",
                                   row["sample_index"], token_count=count, max_output_tokens=256)
            for bullet in sample.bullets:
                _, ids = ar_token_ids(tok, bullet.text)
                if ids:
                    key = (cell["layer"], tuple(ids[:32]))
                    unique.setdefault(key, {"text": bullet.text, "layer": cell["layer"],
                        "family": cell["family"], "cell_id": cell["cell_id"], "input_ids": ids[:32]})
    # Hash ordering gives reproducible coverage without choosing by fit or text quality.
    corpus = [unique[k] for k in sorted(unique, key=lambda k: digest(["AR_speed_v1", k]))[:1024]]
    if len(corpus) < 512:
        raise ValueError("Need at least 512 distinct effective baseline inputs")
    if len(corpus) < 1024:
        corpus = corpus[:512]
    a.output.mkdir(parents=True, exist_ok=True)
    spec = {"manifest_sha256": sha(a.manifest), "checkpoint": str(checkpoint),
        "vector_contract": manifest["vector_contract"], "inputs": len(corpus),
        "input_sha256": digest(corpus), "batches": [128, 256, 512], "timed_passes": 2,
        "warmup_batches_per_shape": 1, "slurm_job_id": job,
        "families": dict(Counter(r["family"] for r in corpus)),
        "layers": dict(Counter(r["layer"] for r in corpus)),
        "code_sha256": sha(Path(__file__)), "torch_version": torch.__version__,
        "device": torch.cuda.get_device_name(),
        "scope": "AR throughput and raw-vector numerical diagnostic only; no quality selection or production batch change"}
    atomic(a.output / "spec.json", spec)
    started = time.monotonic()
    ar = FrozenAR.load(base, str(checkpoint))
    torch.cuda.synchronize()
    load_seconds = time.monotonic() - started
    reference, results = None, []

    def run_batch(rows):
        vectors, metadata = ar.encode_mixed([r["text"] for r in rows], [r["layer"] for r in rows])
        if not torch.isfinite(vectors).all():
            raise ValueError("Nonfinite AR output")
        if any(m["input_ids"] != r["input_ids"] for m, r in zip(metadata, rows)):
            raise ValueError("AR span normalization differs from prepared baseline inputs")
        return vectors

    for batch_size in (128, 256, 512):
        row = {"batch_size": batch_size, "passes": []}
        try:
            run_batch(corpus[:batch_size])
            torch.cuda.synchronize()
            for pass_index in range(2):
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()
                start = time.monotonic()
                outputs = [run_batch(corpus[i:i + batch_size]) for i in range(0, len(corpus), batch_size)]
                torch.cuda.synchronize()
                seconds = time.monotonic() - start
                values = torch.cat(outputs)
                if reference is None:
                    reference = values.clone()
                difference = values - reference
                relative = difference.norm(dim=1) / reference.norm(dim=1).clamp_min(1e-12)
                row["passes"].append({"pass_index": pass_index, "seconds": seconds,
                    "inputs_per_second": len(corpus) / seconds,
                    "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                    "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                    "relative_l2_vs_batch128_max": float(relative.max()),
                    "relative_l2_vs_batch128_median": float(relative.median()),
                    "max_abs_vs_batch128": float(difference.abs().max())})
                del outputs, values, difference, relative
            row["status"] = "complete"
            row["median_inputs_per_second"] = statistics.median(v["inputs_per_second"] for v in row["passes"])
        except torch.cuda.OutOfMemoryError as error:
            row["status"] = "cuda_out_of_memory"
            row["error"] = str(error)[:500]
            gc.collect()
            torch.cuda.empty_cache()
        results.append(row)
        atomic(a.output / "results.json", {"status": "running", "spec": spec,
            "load_seconds": load_seconds, "results": results})
        print(json.dumps(row), flush=True)
    payload = {"status": "complete", "spec": spec, "load_seconds": load_seconds,
        "results": results, "production_batch_size_changed": False,
        "numerical_scope": "Raw AR predictions only; no whitened fits, selection stability or benchmark quality measured."}
    atomic(a.output / "results.json", payload)
    print(json.dumps({"status": "complete", "results_path": str(a.output / "results.json")}), flush=True)


if __name__ == "__main__":
    main()
