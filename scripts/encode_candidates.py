"""Resumable raw AR vector cache over shared candidates or explicit edited phrases.

Cache effective scorer inputs, retaining each full-text/source variant separately.
No whitening copies, target activations, answers, selection, or API calls here.
"""
import argparse
from contextlib import ExitStack
from collections import OrderedDict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

import torch
from safetensors.torch import save_file
from transformers import AutoTokenizer
from olens_improve.models import BASE_REVISION, PAIR_REVISION
from olens_improve.reconstruction import FrozenAR, ar_token_ids
from olens_improve.selection import PARSER_POLICY, parse_bullets
from olens_improve.ar_cache import digest, vector_key, input_records
from olens_improve.stage_permissions import require_record_analysis
from olens_improve.stage_io import validate_export_stage


def atomic_json(path,payload):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2)+"\n"); os.replace(tmp,path)


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--runtime",default="configs/runtime.json")
    p.add_argument("--input",action="append",required=True)
    p.add_argument("--input-kind",choices=("candidates","phrases"),default="candidates")
    p.add_argument("--checkpoint",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--batch-size",type=int,default=32)
    p.add_argument("--shard-size",type=int,default=4096)
    p.add_argument("--max-output-tokens",type=int,default=256)
    p.add_argument("--analysis-manifest")
    p.add_argument("--fresh-manifest")
    p.add_argument("--analysis-gate")
    return p.parse_args()


def encode_snapshot(args, ar=None):
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("AR encoding must use assigned GPU")
    if args.batch_size<1 or args.shard_size<1:
        raise ValueError("Positive batch/shard size required")
    analysis_paths = [getattr(args,k,None) for k in ('analysis_manifest','fresh_manifest','analysis_gate')]
    if any(analysis_paths) and not all(analysis_paths):
        raise ValueError('Analysis authorization requires cohort, fresh manifest and gate together')
    analysis_cells = analysis_captures = None
    authorization = None
    if all(analysis_paths):
        bodies = [Path(p).read_bytes() for p in analysis_paths]
        _, analysis_cells, analysis_captures = validate_export_stage(*bodies)
        authorization = dict(zip(('cohort_sha256','fresh_sha256','gate_sha256'),
                                 (hashlib.sha256(b).hexdigest() for b in bodies)))
    # Reject sealed source records before tokenizer/checkpoint/model work.
    for path in args.input:
        for row in input_records(Path(path).read_bytes()):
            require_record_analysis(row, analysis_cells, analysis_captures)
    with ExitStack() as stack:
        owner_path=Path(args.output)/"stream_writer.lock";owner_path.parent.mkdir(parents=True,exist_ok=True)
        owner_lock=getattr(args,"writer_owner_lock",None);owns_lock=owner_lock is None
        if owns_lock:owner_lock=stack.enter_context(owner_path.open("a+"))
        elif Path(owner_lock.name).resolve()!=owner_path.resolve():
            raise ValueError("Encoder writer-owner lock belongs to another output root")
        fcntl.flock(owner_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        torch.set_num_threads(4)
        runtime=json.loads(Path(args.runtime).read_text())
        base=runtime["paths"]["base_snapshot"]
        tok=AutoTokenizer.from_pretrained(base,local_files_only=True)
        checkpoint=Path(args.checkpoint)
        state=torch.load(checkpoint/"heads.pt",map_location="cpu",weights_only=True)
        cfg=json.loads((checkpoint/"meta.json").read_text())["config"]
        tag_by_layer={int(layer):state["tag_ids"][i].tolist() for i,layer in enumerate(state["layers"])}
        contract={"base_revision":BASE_REVISION,"pair_revision":PAIR_REVISION,
            "head_sha256":hashlib.sha256((checkpoint/"heads.pt").read_bytes()).hexdigest(),
            "meta_sha256":hashlib.sha256((checkpoint/"meta.json").read_bytes()).hexdigest(),
            "adapter_config_sha256":hashlib.sha256((checkpoint/"lora/adapter_config.json").read_bytes()).hexdigest(),
            "adapter_sha256":hashlib.sha256((checkpoint/"lora/adapter_model.safetensors").read_bytes()).hexdigest(),
            "tokenizer_revision":BASE_REVISION,"tokenizer_cleanup":"source_scaffolding_and_special_ids_v1",
            "span_limit":32,"padding":"right_zero","head_layer_norm":cfg["head_layer_norm"],
            "head_layer_norm_epsilon":1e-5,"final_norm":"Identity","backbone_dtype":"bfloat16",
            "head_dtype":"float32","key_policy":"effective_scored_tokens_and_tag_v1"}
        contract_sha=digest(contract)
        output=Path(args.output)/contract_sha[:20]; output.mkdir(parents=True,exist_ok=True)
        lock=stack.enter_context(open(output/"writer.lock","a+"))
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic_json(output/"contract.json",contract|{"sha256":contract_sha})
        known=set(); indexes=sorted(output.glob("raw_*.index.json"))
        for path in indexes:
            info=json.loads(path.read_text())
            if info["contract_sha256"]!=contract_sha:
                raise ValueError("Cache contract differs")
            if not Path(info["tensor_path"]).is_file():
                raise ValueError("Vector cache index has no completed tensor shard")
            known.update(row["cache_key"] for row in info["vectors"])
        pending=OrderedDict(); usages=[]; source_inputs=[]
        token_count=lambda text:len(tok(text,add_special_tokens=False)["input_ids"])
        for input_path in args.input:
            path=Path(input_path); body=path.read_bytes()
            source_info={"path":str(path),"sha256":hashlib.sha256(body).hexdigest()}
            terminal=path.with_suffix(".status.json")
            if terminal.exists():
                status=json.loads(terminal.read_text())
                if status.get("status")!="complete" or status.get("journal_sha256")!=source_info["sha256"]:
                    raise ValueError("Input does not match completed generation journal")
                source_info["terminal_status"]=status
            source_inputs.append(source_info)
            for line_number,row in enumerate(input_records(body)):
                if row.get("split")=="test" and not row.get("frozen_test_authorized",False):
                    raise ValueError("Sealed test candidate encoding is not authorized")
                layer=int(row["layer"])
                if layer not in tag_by_layer or layer not in range(20,61,4):
                    raise ValueError("Off-contract layer")
                sample_id=f"{row.get('global_pool_id',row.get('pool_id','phrases'))}:{row.get('cell_id','cell')}:{row.get('sample_index',line_number)}"
                if args.input_kind=="candidates":
                    sample=parse_bullets(row["text"],sample_id,int(row.get("sample_index",0)),
                                         token_count=token_count,max_output_tokens=args.max_output_tokens)
                    atoms=[(b.phrase_id,b.text,b.start,b.end) for b in sample.bullets]
                    flags=list(sample.flags)
                else:
                    atoms=[(row.get("phrase_id",sample_id),row["text"],None,None)]
                    flags=[]
                for source_id,text,start,end in atoms:
                    cleaned,original_ids=ar_token_ids(tok,text)
                    encoded=original_ids[:32]
                    provenance={"cell_id":row.get("cell_id"),"pool_id":row.get("global_pool_id",row.get("pool_id")),
                        "activation_sha256":row.get("activation_sha256"),
                        "sample_index":row.get("sample_index"),"source_phrase_id":source_id,"layer":layer,
                        "text":text,"scored_text":cleaned,"span_start":start,"span_end":end,
                        "parser_flags":flags,"parser_policy":PARSER_POLICY if args.input_kind=="candidates" else "explicit_phrase",
                        "original_token_count":len(original_ids),"scored_token_count":len(encoded),
                        "scored_token_ids":encoded,"unscored_suffix_ids":original_ids[32:],
                        "truncated":len(original_ids)>32}
                    if not encoded:
                        usages.append(provenance|{"cache_key":None,"status":"empty_after_cleanup"})
                        continue
                    key=vector_key(contract_sha,tag_by_layer[layer],encoded)
                    usages.append(provenance|{"cache_key":key,"status":"encoded_or_cache_hit"})
                    if key not in known and key not in pending:
                        pending[key]={"text":text,"layer":layer,"scored_token_ids":encoded,
                                      "tag_ids":tag_by_layer[layer]}
        usage_id=digest({"inputs":source_inputs,"parser":PARSER_POLICY,"max_output_tokens":args.max_output_tokens,
                         "kind":args.input_kind})[:20]
        tmp=output/f"usage_{usage_id}.jsonl.tmp"
        tmp.write_text("".join(json.dumps(row)+"\n" for row in usages))
        os.replace(tmp,output/f"usage_{usage_id}.jsonl")
        started=time.time(); requested=list(pending.items()); shard_number=len(indexes)
        if requested:
            if ar is None:
                ar=FrozenAR.load(base,str(checkpoint))
            # Heterogeneous tags are independent batch rows; check against separate calls.
            check_texts=["The performer humiliates the heckler.", "A number.",
                         "The intermediate result is eleven. " + "A further detail. "*12]
            check_layers=[20,44,60]
            mixed,_=ar.encode_mixed(check_texts,check_layers)
            separate=torch.cat([ar.encode([text],layer)[0] for text,layer in zip(check_texts,check_layers)])
            relative=((mixed-separate).norm(dim=1)/separate.norm(dim=1).clamp_min(1e-12)).tolist()
            if max(relative)>.02:
                raise RuntimeError(f"Mixed-tag batching exceeds provisional numerical tolerance: {relative}")
            atomic_json(output/"mixed_tag_fixture.json",{"relative_l2_errors":relative,
                        "max_abs_error":float((mixed-separate).abs().max()),"layers":check_layers,"texts":check_texts,
                        "tolerance":.02,"note":"Floating-point batching check, not semantic quality evidence"})
            for lo in range(0,len(requested),args.shard_size):
                chunk=requested[lo:lo+args.shard_size]
                vectors=[]
                execution=[]
                for offset in range(0,len(chunk),args.batch_size):
                    batch=chunk[offset:offset+args.batch_size]
                    predictions,encoding=ar.encode_mixed([v["text"] for _,v in batch],[v["layer"] for _,v in batch])
                    for (_,wanted),actual in zip(batch,encoding):
                        if wanted["scored_token_ids"]!=actual["input_ids"] or wanted["tag_ids"]!=actual["tag_ids"]:
                            raise ValueError("Cache input differs from actual AR encoding")
                    if not torch.isfinite(predictions).all():
                        raise ValueError("Nonfinite AR predictions")
                    vectors.append(predictions)
                    batch_keys=[key for key,_ in batch]
                    execution.extend({"batch_size":len(batch),"padded_token_width":max(row["scored_token_count"] for row in encoding)+6,
                                      "ordered_batch_keys_sha256":digest(batch_keys),"usage_id":usage_id} for _ in batch)
                tensor_path=output/f"raw_{shard_number:05d}.safetensors"
                tmp=tensor_path.with_suffix(tensor_path.suffix+".tmp")
                save_file({"vectors":torch.cat(vectors)},str(tmp),metadata={"contract_sha256":contract_sha})
                os.replace(tmp,tensor_path)
                entries=[{"cache_key":key,"row":i,"layer":item["layer"],
                          "scored_token_ids":item["scored_token_ids"],"tag_ids":item["tag_ids"],"execution":execution[i]}
                         for i,(key,item) in enumerate(chunk)]
                atomic_json(output/f"raw_{shard_number:05d}.index.json",{
                    "contract_sha256":contract_sha,"tensor_path":str(tensor_path),"vectors":entries})
                known.update(key for key,_ in chunk); shard_number+=1
                atomic_json(output/"progress.json",{"completed_unique_vectors":len(known),
                    "new_vectors":min(lo+args.shard_size,len(requested)),"requested_new_vectors":len(requested),
                    "seconds":time.time()-started,"status":"running"})
                print(json.dumps({"completed_unique_vectors":len(known),"new_vectors":min(lo+args.shard_size,len(requested)),
                                  "requested_new_vectors":len(requested)}),flush=True)
        atomic_json(output/f"usage_{usage_id}.run.json",{
            "status":"complete","contract_sha256":contract_sha,"input_kind":args.input_kind,
            "source_inputs":source_inputs,"usage_path":str(output/f"usage_{usage_id}.jsonl"),
            "analysis_authorization":authorization,
            "full_text_variants":len(usages),"new_unique_vectors":len(requested),"total_unique_vectors":len(known),
            "seconds":time.time()-started,"batch_size":args.batch_size,"slurm_job_id":os.environ["SLURM_JOB_ID"]})
        atomic_json(output/"progress.json",{"status":"complete","completed_unique_vectors":len(known),
                    "new_vectors":len(requested),"seconds":time.time()-started,"usage_id":usage_id})
        print(json.dumps({"status":"complete","cache_directory":str(output),"usage_id":usage_id,
                          "full_text_variants":len(usages),"new_unique_vectors":len(requested)}),flush=True)
        return ar


if __name__=="__main__":
    encode_snapshot(parse_args())
