"""Verify matched prompt-tag AR against the pinned original inference class."""
import argparse
import ast
import hashlib
import json
import os
import re
from pathlib import Path
import time
import torch
from safetensors.torch import load_file
from olens_improve.reconstruction import FrozenAR, JointNNLS, Whitener, ar_token_ids


class StripAnnotations(ast.NodeTransformer):
    def visit_FunctionDef(self,node):
        self.generic_visit(node)
        node.returns=None
        for arg in node.args.posonlyargs+node.args.args+node.args.kwonlyargs:
            arg.annotation=None
        return node
    def visit_AnnAssign(self,node):
        return ast.Assign(targets=[node.target],value=node.value) if node.value is not None else ast.Pass()


def original_class(path,name,namespace):
    tree=ast.parse(path.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
    module=ast.fix_missing_locations(StripAnnotations().visit(ast.Module(body=[cls],type_ignores=[])))
    exec(compile(module,str(path),"exec"),namespace)
    return namespace[name]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--runtime",default="configs/runtime.json")
    p.add_argument("--checkpoint",required=True)
    p.add_argument("--whitener",required=True)
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--pool")
    args=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("AR smoke requires a GPU allocation")
    torch.set_num_threads(4)
    runtime=json.loads(Path(args.runtime).read_text())
    start=time.time()
    ar=FrozenAR.load(runtime["paths"]["base_snapshot"],args.checkpoint)
    load_seconds=time.time()-start
    phrases=["Paris is the capital of France.","Paris is not the capital of France.",
             "The mayor gave the doctor three books."]
    ours,encoding=ar.encode(phrases,44)
    state=torch.load(Path(args.checkpoint)/"heads.pt",map_location="cpu",weights_only=True)
    src=Path(args.source)/"src/oracle_lens"
    # Tokenization is checked against original bare_token_ids, including special markers.
    tokenizer_namespace={"re":re,"Any":object}
    exec(compile((src/"readout_text.py").read_text(),str(src/"readout_text.py"),"exec"),tokenizer_namespace)
    tokenizer_namespace["prepare_reward_text"]=tokenizer_namespace["strip_scaffolding"]
    scorer_tree=ast.parse((src/"pipeline/scorer.py").read_text())
    bare=next(n for n in scorer_tree.body if isinstance(n,ast.FunctionDef) and n.name=="bare_token_ids")
    module=ast.fix_missing_locations(StripAnnotations().visit(ast.Module(body=[bare],type_ignores=[])))
    exec(compile(module,str(src/"pipeline/scorer.py"),"exec"),tokenizer_namespace)
    tokenization_cases=["Paris is not in France.","<think>not a fact</think><explanation>Three books.</explanation>",
                        "<|im_start|>assistant\nFive books.<|im_end|>","Paris. "+"long sentence "*40,
                        "数字是三，不是五。"]
    for text in tokenization_cases:
        _,actual=ar_token_ids(ar.tokenizer,text)
        expected=tokenizer_namespace["bare_token_ids"](ar.tokenizer,text)
        assert actual==expected
    namespace={"torch":torch,"nn":torch.nn,"Tensor":torch.Tensor}
    original_class(src/"core/reconstructor.py","ReconstructorHead",namespace)
    Original=original_class(src/"pipeline/multilayer_reconstructor.py","PromptTagReconstructor",namespace)
    original=Original(ar.backbone,ar.layers,5120,state["tag_ids"],layer_norm=True).to("cuda").eval()
    original.head.load_state_dict(state["head"])
    rows=[item["input_ids"] for item in encoding]
    width=max(map(len,rows))
    ids=torch.zeros((len(rows),width),dtype=torch.long,device="cuda"); mask=torch.zeros_like(ids)
    for i,row in enumerate(rows):
        ids[i,:len(row)]=torch.tensor(row,device="cuda"); mask[i,:len(row)]=1
    with torch.inference_mode():
        ref=original(ids,mask,layer_idx=ar.layers.index(44))[:,0].float().cpu()
        with ar.backbone.disable_adapter():
            disabled=original(ids,mask,layer_idx=ar.layers.index(44))[:,0].float().cpu()
    reference_error=float((ours-ref).abs().max())
    assert reference_error<1e-5,reference_error
    adapter_delta=float((ours-disabled).abs().max())
    assert adapter_delta>1e-3,adapter_delta
    wstart=time.time()
    whitener=Whitener.load(args.whitener)
    w_seconds=time.time()-wstart
    result={"status":"matched-ar-source-class-fixture-passed", "load_seconds":load_seconds,
            "whitener_seconds":w_seconds,"ar_metadata":ar.metadata,"encoding":encoding,
            "source_revision":"a32590085a6070d75f950155d3c2b3db3eec97ef",
            "prediction_max_reference_error":reference_error,"adapter_prediction_max_delta":adapter_delta,
            "tokenization_fixture_cases":len(tokenization_cases),
            "whitener_sha256":whitener.artifact_sha256,"ridge_c":whitener.ridge_c,
            "whitener_file":args.whitener,"phrase_cosine_negation":float(torch.nn.functional.cosine_similarity(
                whitener.whiten(ours[:1]),whitener.whiten(ours[1:2]),dim=1)[0]),
            "note":"Cosine is diagnostic, not evidence that negation is preserved.",
            "source_file_sha256":{str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (src/"core/reconstructor.py",src/"pipeline/multilayer_reconstructor.py")}}
    if args.pool:
        pool=Path(args.pool)
        acts=load_file(str(pool/"activations.safetensors"))["resid"]
        candidates=[json.loads(line) for line in (pool/"candidates.jsonl").read_text().splitlines()]
        cells=json.loads((pool/"capture_audit.json").read_text())["cells"]
        scores=[]; vector_shard={}; vector_index=[]; solver_times={"released80":0.0,"scipy_exact":0.0}
        for i,cell in enumerate(cells):
            choices=[c for c in candidates if c["cell_id"]==cell["cell_id"]]
            for choice in choices:
                bullets=[line.strip()[2:].strip() for line in choice["text"].splitlines()
                         if line.strip().startswith("- ")][:4]
                if not bullets:
                    bullets=[choice["text"].strip()] if choice["text"].strip() else []
                if not bullets:
                    scores.append(choice|{"fve":0.0,"bullets":[]}); continue
                vectors,encoded=ar.encode(bullets,44)
                for bullet,vector,enc in zip(bullets,vectors,encoded):
                    key=hashlib.sha256(bullet.encode()).hexdigest()
                    vector_shard[key]=vector
                    vector_index.append({"phrase_id":key,"layer":44,"encoding":enc})
                dictionary=dict(zip(map(str,range(len(bullets))),vectors))
                scorer=JointNNLS.from_raw(acts[i],dictionary,whitener,solver="released80")
                tick=time.time()
                fit=scorer.fit(tuple(dictionary))
                solver_times["released80"]+=time.time()-tick
                exact_scorer=JointNNLS(scorer.target,scorer.vectors,solver="scipy_exact")
                tick=time.time()
                exact_fit=exact_scorer.fit(tuple(dictionary))
                solver_times["scipy_exact"]+=time.time()-tick
                scores.append({"cell_id":choice["cell_id"],"sample_index":choice["sample_index"],
                               "fve":fit.fve,"coefficients":fit.coefficients,"bullets":bullets,
                               "exact_fve":exact_fit.fve,"exact_coefficients":exact_fit.coefficients,
                               "encoding":encoded,"score_metadata":scorer.metadata})
        result["instrument_candidate_scores"]=scores
        result["solver_seconds"]=solver_times
        result["solver_max_fve_difference"]=max(abs(s["exact_fve"]-s["fve"]) for s in scores)
        result["solver_winner_changes"]=sum(
            max([s for s in scores if s["cell_id"]==cell["cell_id"]],key=lambda s:s["fve"])["sample_index"] !=
            max([s for s in scores if s["cell_id"]==cell["cell_id"]],key=lambda s:s["exact_fve"])["sample_index"]
            for cell in cells)
        from safetensors.torch import save_file
        save_file(vector_shard,str(pool/"ar_phrase_vectors.safetensors"),metadata={
            "layer":"44","pair_revision":"c95215d5d2f6250f20c305ae55c6e4d7569f92dc"})
        (pool/"ar_phrase_vectors.index.json").write_text(json.dumps(vector_index,indent=2)+"\n")
    output=Path(args.output); tmp=output.with_suffix(output.suffix+".tmp")
    tmp.write_text(json.dumps(result,indent=2)+"\n"); os.replace(tmp,output)
    print(json.dumps({k:v for k,v in result.items() if k not in ("instrument_candidate_scores","encoding")}),flush=True)


if __name__=="__main__":
    main()
