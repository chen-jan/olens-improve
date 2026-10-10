"""Grouped fresh adapter-free capture; preserves imported instrument vectors exactly."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import torch
from safetensors.torch import load_file, save_file
from olens_improve.models import BASE_REVISION, PAIR_REVISION, FrozenOLens
from pool_worker import render, atomic_json


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--runtime",default="configs/runtime.json")
    p.add_argument("--manifest",required=True)
    p.add_argument("--adapter",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--import-instrument")
    p.add_argument("--groups-per-shard",type=int,default=32)
    args=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Fresh capture requires a GPU allocation")
    manifest_path=Path(args.manifest); manifest=json.loads(manifest_path.read_text())
    cells=manifest["cells"]
    if len({c["cell_id"] for c in cells})!=len(cells):
        raise ValueError("Duplicate cell IDs")
    output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    manifest_sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    state=output/"capture_state.json"
    if state.exists() and json.loads(state.read_text())["manifest_sha256"]!=manifest_sha:
        raise ValueError("Capture directory belongs to another manifest")
    imported={}; imported_audit={}
    if args.import_instrument:
        path=Path(args.import_instrument)
        h=load_file(str(path/"activations.safetensors"))["resid"]
        audit=json.loads((path/"capture_audit.json").read_text())["cells"]
        for i,row in enumerate(audit):
            if row["adapter_disabled"] is not True or row["generation_activation_source"]!="fresh_recapture":
                raise ValueError("Imported activation lacks adapter-free provenance")
            imported[row["cell_id"]]=h[i].clone()
            imported_audit[row["cell_id"]]=row
    runtime=json.loads(Path(args.runtime).read_text())
    lens=FrozenOLens.load(runtime["paths"]["base_snapshot"],args.adapter)
    groups=defaultdict(list)
    for index,cell in enumerate(cells):
        # Group by exact capture specification, not just item ID.
        key=hashlib.sha256(json.dumps(cell["capture_spec"],sort_keys=True).encode()).hexdigest()
        groups[key].append((index,cell))
    grouped=list(groups.items())
    for block in range(0,len(grouped),args.groups_per_shard):
        shard=block//args.groups_per_shard
        tensor_path=output/f"capture_{shard:03d}.safetensors"
        index_path=output/f"capture_{shard:03d}.index.json"
        if tensor_path.exists() and index_path.exists():
            if json.loads(index_path.read_text())["manifest_sha256"] != manifest_sha:
                raise ValueError("Existing shard belongs to another manifest")
            continue
        vectors=[]; indexes=[]; renders=[]
        for key,rows in grouped[block:block+args.groups_per_shard]:
            spec=rows[0][1]["capture_spec"]
            ids=render(spec,lens.tokenizer)
            id_hash=hashlib.sha256(json.dumps(ids,separators=(",",":")).encode()).hexdigest()
            layers=sorted({c["layer"] for _,c in rows if c["cell_id"] not in imported})
            positions=sorted({c["position"] for _,c in rows if c["cell_id"] not in imported})
            capture=lens.capture(ids,layers,positions) if layers else {}
            pos_index={position:i for i,position in enumerate(positions)}
            for index,cell in rows:
                position=cell["position"]
                if lens.tokenizer.decode([ids[position]])!=cell["token"]:
                    raise ValueError(f"Rendered token mismatch {cell['cell_id']}")
                if cell["cell_id"] in imported:
                    h=imported[cell["cell_id"]]
                    if imported_audit[cell["cell_id"]]["rendered_token_ids"]!=ids:
                        raise ValueError("Imported instrument token IDs differ")
                    reused=True
                else:
                    h=capture[cell["layer"]][pos_index[position]]
                    reused=False
                if not torch.isfinite(h).all():
                    raise ValueError("Nonfinite captured activation")
                # Preserve instrument FP32 bytes exactly, without a storage roundtrip.
                vectors.append(h.float())
                indexes.append({"cell_id":cell["cell_id"],"manifest_row":index,
                    "activation_tensor_path":str(tensor_path),"activation_tensor_key":"resid",
                    "activation_row":len(vectors)-1,"adapter_disabled":True,
                    "generation_activation_source":"fresh_recapture","position":position,
                    "layer":cell["layer"],"base_revision":BASE_REVISION,
                    "rendered_ids_sha256":id_hash,"capture_spec_sha256":key,
                    "imported_instrument_vector":reused,
                    "activation_sha256":hashlib.sha256(h.float().numpy().tobytes()).hexdigest()})
            renders.append({"capture_spec_sha256":key,"rendered_ids_sha256":id_hash,
                            "input_ids":ids,"cell_ids":[c["cell_id"] for _,c in rows]})
        tmp=tensor_path.with_suffix(tensor_path.suffix+".tmp")
        save_file({"resid":torch.stack(vectors)},str(tmp),metadata={
            "base_revision":BASE_REVISION,"capture_adapter":"disabled",
            "layer_convention":"decoder-block-output","manifest_sha256":manifest_sha})
        os.replace(tmp,tensor_path)
        atomic_json(index_path,{"cells":indexes,"renders":renders,"manifest_sha256":manifest_sha})
        atomic_json(state,{"manifest_sha256":manifest_sha,"completed_shards":shard+1,
                           "group_count":len(grouped),"slurm_job_id":os.environ["SLURM_JOB_ID"]})
        print(json.dumps({"completed_shard":shard,"groups_complete":min(block+args.groups_per_shard,len(grouped)),
                          "total_groups":len(grouped),"cells_in_shard":len(vectors)}),flush=True)
    # Final compact tensor/audit preserves original manifest ordering for existing consumers.
    all_vectors=[None]*len(cells); all_audit=[None]*len(cells); all_renders=[]
    for shard in range((len(grouped)+args.groups_per_shard-1)//args.groups_per_shard):
        data=load_file(str(output/f"capture_{shard:03d}.safetensors"))["resid"]
        index=json.loads((output/f"capture_{shard:03d}.index.json").read_text())
        all_renders.extend(index["renders"])
        for row in index["cells"]:
            position=row["manifest_row"]
            all_vectors[position]=data[row["activation_row"]]
            all_audit[position]=row
    final=output/"activations.safetensors"; tmp=output/"activations.safetensors.tmp"
    save_file({"resid":torch.stack(all_vectors)},str(tmp),metadata={
        "base_revision":BASE_REVISION,"capture_adapter":"disabled","manifest_sha256":manifest_sha})
    os.replace(tmp,final)
    for i,row in enumerate(all_audit):
        row.update(activation_tensor_path=str(final),activation_tensor_key="resid",activation_row=i)
    atomic_json(output/"capture_audit.json",{"cells":all_audit,"renders":all_renders,
        "manifest_sha256":manifest_sha,"base_revision":BASE_REVISION,"pair_revision":PAIR_REVISION,
        "slurm_job_id":os.environ["SLURM_JOB_ID"],"imported_instrument_count":sum(r["imported_instrument_vector"] for r in all_audit)})
    fresh_manifest=dict(manifest)
    fresh_manifest["cells"]=[dict(cell)|all_audit[i] for i,cell in enumerate(cells)]
    atomic_json(output/"fresh_manifest.json",fresh_manifest)
    atomic_json(state,{"status":"complete","manifest_sha256":manifest_sha,"cell_count":len(cells),
        "group_count":len(grouped),"slurm_job_id":os.environ["SLURM_JOB_ID"]})


if __name__=="__main__":
    main()
