"""Check real generation against pinned WorkspaceBench's independent OLens path.

Uses an ad-hoc instrument activation, never additional benchmark pool samples.
"""
import argparse
import ast
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import torch
from olens_improve.models import FrozenOLens, carrier


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--runtime",default="configs/runtime.json")
    p.add_argument("--adapter",required=True)
    p.add_argument("--upstream-methods",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Sampler comparison requires assigned GPU")
    runtime=json.loads(Path(args.runtime).read_text())
    lens=FrozenOLens.load(runtime["paths"]["base_snapshot"],args.adapter)
    ids=lens.tokenizer("The capital of France is Paris.",add_special_tokens=False)["input_ids"]
    h=lens.capture(ids,[44],[len(ids)-1])[44][0]
    drift=lens.merge()
    tree=ast.parse(Path(args.upstream_methods).read_text())
    classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name in {"Sampling","OLens"}]
    namespace={"dataclass":dataclass,"field":field,"Any":Any,"Backend":object,
               "Readout":SimpleNamespace}
    exec(compile(ast.Module(body=classes,type_ignores=[]),args.upstream_methods,"exec"),namespace)
    original=namespace["OLens"](sampling=namespace["Sampling"](k=2))
    original._b=SimpleNamespace(model=lens.model,tokenizer=lens.tokenizer,device=lens.device)
    source_ids,source_slot=original._carrier(44)
    local_ids,local_slot,marker=carrier(lens.tokenizer,44)
    assert source_ids==local_ids and source_slot==local_slot
    ours,meta=lens.sample(h,44,n=2,seed=42)
    torch.manual_seed(42)
    ref=original.read(h,44).samples
    assert ours==ref,"Pinned WorkspaceBench sampling produced different text"
    result={"status":"independent-pinned-workspacebench-sampler-equality-passed",
            "benchmark_commit":"92d763e722377f5bfae045e829a308ab5919a820",
            "carrier_equal":True,"samples_equal":True,"marker_id":marker,"merge_drift":drift,
            "source_methods":args.upstream_methods,"generation":meta,"samples":ours,
            "scope":"Adhoc Paris instrument; zero new core benchmark samples"}
    output=Path(args.output); tmp=output.with_suffix(output.suffix+".tmp")
    tmp.write_text(json.dumps(result,indent=2)+"\n"); os.replace(tmp,output)
    print(json.dumps(result),flush=True)


if __name__=="__main__":
    main()
