"""Recapture a frozen inference-only manifest and generate one shared candidate pool.

Run in assigned Slurm GPU allocation. No target answers or judge calls are loaded.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import torch
from safetensors import safe_open
from safetensors.torch import save_file

from olens_improve.models import BASE_REVISION, PAIR_REVISION, FrozenOLens


def render(spec, tokenizer):
    kind = spec["render"]
    if kind == "captured":
        return list(spec["extra"]["input_ids"])
    if kind in {"plain", "bare"}:
        return tokenizer(spec.get("text", ""), add_special_tokens=False)["input_ids"]
    if kind not in {"chat", "chat_summarize"}:
        raise ValueError(f"Unsupported manifest render {kind}")
    messages = [{"role":"system", "content":spec["system"]}] if spec.get("system") else []
    messages.append({"role":"user", "content":spec.get("text", "")+spec.get("suffix", "")})
    out = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                       enable_thinking=False)
    return list(out if isinstance(out,list) else out["input_ids"])


def atomic_json(path, payload):
    tmp = path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2)+"\n")
    os.replace(tmp,path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runtime", default="configs/runtime.json")
    p.add_argument("--manifest", required=True)
    p.add_argument("--adapter", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--n",type=int,default=2)
    p.add_argument("--seed",type=int,default=71)
    p.add_argument("--max-new-tokens",type=int,default=256)
    args=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("GPU worker requires Slurm")
    if not 1<=args.n<=32:
        raise ValueError("N must be 1..32")
    manifest_path=Path(args.manifest)
    manifest=json.loads(manifest_path.read_text())
    if manifest["split"] not in {"development","validation","test"}:
        raise ValueError("Unknown split")
    # Heldout authorization must be reflected explicitly in its frozen manifest.
    if manifest["split"]=="test" and not manifest.get("frozen_test_authorized",False):
        raise ValueError("Test generation requires frozen-test manifest authorization")
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    pool_id=hashlib.sha256((manifest_path.read_bytes()+str(args.seed).encode()+
                           str(args.n).encode()+PAIR_REVISION.encode())).hexdigest()[:20]
    runtime=json.loads(Path(args.runtime).read_text())
    lens=FrozenOLens.load(runtime["paths"]["base_snapshot"],args.adapter)
    captures=[]; audit=[]; t=time.time()
    for c in manifest["cells"]:
        ids=render(c["capture_spec"],lens.tokenizer)
        position=c["position"]
        token=lens.tokenizer.decode([ids[position]])
        if token!=c["token"]:
            raise ValueError(f"Token mismatch {c['cell_id']}: {token!r} vs {c['token']!r}")
        h=lens.capture(ids,[c["layer"]],[position])[c["layer"]][0]
        captures.append(h)
        with safe_open(c["cache_tensor_path"],framework="pt") as f:
            old=f.get_slice(c["cache_tensor_key"])[c["cache_row"]].float()
        cosine=float(torch.nn.functional.cosine_similarity(h,old,dim=0))
        relative=float((h-old).norm()/old.norm().clamp_min(1e-12))
        audit.append({"cell_id":c["cell_id"],"rendered_token_ids":ids,"position":position,
                      "adapter_disabled":True,"cosine_to_cache":cosine,
                      "relative_l2_error":relative,"max_abs_error":float((h-old).abs().max()),
                      "generation_activation_source":"fresh_recapture"})
        print(json.dumps(audit[-1] | {"rendered_token_ids":f"{len(ids)} ids"}),flush=True)
    activation_path=out/"activations.safetensors"
    tmp=out/"activations.safetensors.tmp"
    save_file({"resid":torch.stack(captures)},str(tmp),metadata={
        "base_revision":BASE_REVISION,"capture_adapter":"disabled","layer_convention":"decoder-block-output"})
    os.replace(tmp,activation_path)
    atomic_json(out/"capture_audit.json",{"pool_id":pool_id,"cells":audit,"seconds":time.time()-t})
    drift=lens.merge()
    records=[]; generation=[]
    for index,(c,h) in enumerate(zip(manifest["cells"],captures)):
        path=out/f"cell_{index:04d}.json"
        if path.exists():
            existing=json.loads(path.read_text())
            if existing["pool_id"]!=pool_id:
                raise ValueError("Output contains a different pool")
            records.extend(existing["candidates"]); generation.append(existing["generation"])
            continue
        seed=args.seed+index
        start=time.time()
        texts,meta=lens.sample(h,c["layer"],n=args.n,seed=seed,max_new_tokens=args.max_new_tokens)
        rows=[]
        for j,text in enumerate(texts):
            rows.append({"cell_id":c["cell_id"],"family":c["family"],"item_id":c["item_id"],
                         "layer":c["layer"],"position":c["position"],"sample_index":j,"text":text,
                         "token_count":meta["token_counts"][j],"seed":seed,"pool_id":pool_id,
                         "truncated":meta["truncated"][j],"finish_reason":meta["finish_reasons"][j],
                         "base_revision":BASE_REVISION,"adapter_revision":PAIR_REVISION})
        meta|={"cell_id":c["cell_id"],"seconds":time.time()-start}
        atomic_json(path,{"pool_id":pool_id,"candidates":rows,"generation":meta})
        records.extend(rows); generation.append(meta)
        print(json.dumps({"completed":index+1,"total":len(captures),"cell_id":c["cell_id"],
                          "seconds":meta["seconds"]}),flush=True)
    tmp=out/"candidates.jsonl.tmp"
    tmp.write_text("".join(json.dumps(row)+"\n" for row in records))
    os.replace(tmp,out/"candidates.jsonl")
    atomic_json(out/"run.json",{"pool_id":pool_id,"manifest_sha256":hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "base_revision":BASE_REVISION,"adapter_revision":PAIR_REVISION,"adapter_delta":lens.adapter_delta,
        "merge_drift":drift,"generation":generation,"n":args.n,"candidate_count":len(records),
        "slurm_job_id":os.environ["SLURM_JOB_ID"],"instrument_only":manifest.get("partial_grid",False)})


if __name__=="__main__":
    main()
