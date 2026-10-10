"""Compare the minimal J++ reader to pinned BaseLens/HFLensModel operations."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="configs/runtime.json")
    parser.add_argument("--lens", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    import os
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("J++ fixture must run through Slurm")
    import torch
    torch.set_num_threads(2)
    runtime = json.loads(Path(args.runtime).read_text())
    source = Path(runtime["paths"]["jpp_source"])
    sys.path.insert(0, str(source / "src"))
    from workspace_lens.lenses.base_lens import BaseLens
    from jlens.hf import HFLensModel
    from olens_improve.independent import FrozenJPP, JPP_SOURCE_REVISION
    import subprocess
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, check=True, text=True, capture_output=True).stdout.strip()
    if commit != JPP_SOURCE_REVISION:
        raise ValueError("J++ source checkout drift")
    original = BaseLens.load(args.lens)
    reader = FrozenJPP.load(args.lens, runtime["paths"]["base_snapshot"], [20, 44, 60], args.device)
    head = torch.nn.Linear(5120, reader.head.shape[0], bias=False, device="meta")
    head.weight = torch.nn.Parameter(reader.head, requires_grad=False)
    adapter = SimpleNamespace(_lm_head=head, _final_norm=reader.norm, _logit_softcap=None)
    generator = torch.Generator().manual_seed(71)
    rows = []
    for layer in [20, 44, 60]:
        activation = torch.randn(2, 5120, generator=generator).to(args.device)
        ref_transport = original.transport(activation, layer)
        new_transport = reader.transport(activation, layer)
        ref_logits = HFLensModel.unembed(adapter, ref_transport).float()
        new_logits = reader.logits(activation, layer)
        rows.append({"layer": layer, "transport_max_abs": float((ref_transport-new_transport).abs().max()),
                     "logit_max_abs": float((ref_logits-new_logits).abs().max()),
                     "top10_equal": torch.equal(ref_logits.topk(10).indices, new_logits.topk(10).indices)})
    result = {"source_revision": commit, "lens_config": reader.config, "layers": rows,
              "base_loading": "Only final norm and lm_head tensors; no full base model instantiated",
              "precision": "FP32 transport then BF16 base norm/head, matching pinned HFLensModel",
              "scope": "development diagnostic; fitting-group overlap unresolved",
              "passed": all(row["transport_max_abs"] == 0 and row["logit_max_abs"] == 0 and row["top10_equal"] for row in rows)}
    checksum = hashlib.sha256()
    with Path(args.lens).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b""):
            checksum.update(chunk)
    result.update(lens_sha256=checksum.hexdigest(), lens_bytes=Path(args.lens).stat().st_size,
                  device=args.device)
    output = Path(args.output);output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))
    if not result["passed"]:
        raise RuntimeError("Independent J++ source fixture failed")


if __name__ == "__main__":
    main()
