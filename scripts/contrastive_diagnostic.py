"""Isolated development-only E2 test; diagnostic labels never enter selectors."""
import argparse
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file
from olens_improve.contrastive import two_by_two
from olens_improve.reconstruction import FrozenAR, JointNNLS, Whitener


DIAGNOSTICS = [
    {"name":"intermediate_number", "items":["chain-d2p-0271","chain-d2p-0298"],
     "descriptions":["After halving and rounding up, the intermediate value is 11.",
                     "After halving and rounding up, the intermediate value is 12."],
     "generic":"An intermediate value is computed by halving a number and rounding up.",
     "interpretation":"Isolated known intermediate11/12 labels; final-token content need not emphasize the intermediate."},
    {"name":"role_direction", "items":["oa-comedian-heckler-humiliate-ab","oa-comedian-heckler-humiliate-ba"],
     "descriptions":["The performer humiliates the heckler.","The heckler humiliates the performer."],
     "generic":"A performer and a heckler are involved in a humiliating encounter.",
     "interpretation":"Role labels preserve relation direction without introducing unmatched proper names."},
]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--runtime",default="configs/runtime.json")
    p.add_argument("--manifest",default="configs/splits_pilot_instrument_v1.json")
    p.add_argument("--pool",required=True)
    p.add_argument("--checkpoint",required=True)
    p.add_argument("--whitener",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Diagnostic requires assigned GPU")
    torch.set_num_threads(4)
    manifest=json.loads(Path(args.manifest).read_text())
    if manifest["split"]!="development":
        raise ValueError("Diagnostic labels are development-only")
    cells=manifest["cells"]
    audit=json.loads((Path(args.pool)/"capture_audit.json").read_text())["cells"]
    lookup={row["cell_id"]:index for index,row in enumerate(audit)}
    activations=load_file(str(Path(args.pool)/"activations.safetensors"))["resid"]
    runtime=json.loads(Path(args.runtime).read_text())
    started=time.time()
    ar=FrozenAR.load(runtime["paths"]["base_snapshot"],args.checkpoint)
    w=Whitener.load(args.whitener)
    outcomes=[]
    for diag in DIAGNOSTICS:
        picked=[]
        for item in diag["items"]:
            matches=[c for c in cells if c["item_id"]==item and c["layer"]==44]
            if len(matches)!=1:
                raise ValueError(f"Expected exactly one frozen instrument cell for {item}")
            picked.append(matches[0])
        texts=diag["descriptions"]+[diag["generic"]]
        predictions,encoding=ar.encode(texts,44)
        if any(row["truncated"] for row in encoding):
            raise ValueError("Controlled descriptions must fit the AR span")
        dictionary=dict(zip(("description0","description1","generic"),predictions))
        solvers={}
        for solver in ("scipy_exact","released80"):
            scores=[]; generic=[]; coefficients=[]
            for cell in picked:
                scorer=JointNNLS.from_raw(activations[lookup[cell["cell_id"]]],dictionary,w,
                                         solver=solver,metadata={"cell_id":cell["cell_id"],"layer":44})
                fits=[scorer.fit([phrase]) for phrase in dictionary]
                scores.append([fit.fve for fit in fits[:2]])
                generic.append(fits[2].fve)
                coefficients.append([fit.coefficients for fit in fits])
            solvers[solver]=two_by_two(scores,generic)|{"coefficients":coefficients}
        outcomes.append(diag|{"cell_ids":[c["cell_id"] for c in picked],"layer":44,
                             "encoding":encoding,"solvers":solvers})
    result={"experiment":"004-contrastive-diagnostic","status":"completed-development-diagnostic",
            "scope":"Two isolated known-label pairs, not benchmark accuracy or semantic-truth certification",
            "access_boundary":"Diagnostic descriptions are isolated; no gold-informed selector/editor/pool changes",
            "primary_solver":"scipy_exact","compatibility_solver":"released80",
            "whitener_sha256":w.artifact_sha256,"ridge_c":w.ridge_c,
            "seconds":time.time()-started,"results":outcomes,"slurm_job_id":os.environ["SLURM_JOB_ID"]}
    out=Path(args.output); tmp=out.with_suffix(out.suffix+".tmp")
    tmp.write_text(json.dumps(result,indent=2)+"\n"); os.replace(tmp,out)
    print(json.dumps(result),flush=True)


if __name__=="__main__":
    main()
