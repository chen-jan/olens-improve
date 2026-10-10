"""Instrument-only N1/N2 smoke; no judge/API calls or benchmark claims."""
import argparse
import json
import os
from pathlib import Path
import time

from olens_improve.models import BASE_REVISION, PAIR_REVISION, FrozenOLens


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runtime", default="configs/runtime.json")
    p.add_argument("--adapter", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--max-new-tokens", type=int, default=256)
    args = p.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Model smoke must run in a Slurm allocation")
    runtime = json.loads(Path(args.runtime).read_text())
    t0 = time.time()
    lens = FrozenOLens.load(runtime["paths"]["base_snapshot"], args.adapter)
    text = "The capital of France is Paris."
    ids = lens.tokenizer(text, add_special_tokens=False)["input_ids"]
    activation = lens.capture(ids, [44], [len(ids) - 1])[44][0]
    capture = {"text": text, "token_ids": ids, "layer": 44, "position": len(ids) - 1,
               "norm": float(activation.norm()), "adapter_disabled": True}
    load_seconds = time.time() - t0
    merge_drift = lens.merge()
    generation_start = time.time()
    # One N2 pool contains N1 as its first sample. Do not generate another pool.
    samples, meta = lens.sample(activation, 44, n=2, seed=42,
                               max_new_tokens=args.max_new_tokens)
    record = {"status": "instrument-smoke-not-benchmark", "base_revision": BASE_REVISION,
              "pair_revision": PAIR_REVISION, "capture": capture,
              "adapter_delta": lens.adapter_delta, "merge_drift": merge_drift,
              "load_capture_seconds": load_seconds,
              "generation_seconds": time.time() - generation_start,
              "samples": samples, "generation": meta, "slurm_job_id": os.environ["SLURM_JOB_ID"]}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(record, indent=2) + "\n")
    os.replace(tmp, out)
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
