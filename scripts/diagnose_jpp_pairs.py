"""J++ ordered component-token diagnostics for isolated known-label DEV pairs."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="configs/runtime.json")
    parser.add_argument("--pairs", required=True, help="Frozen expanded E2 manifest (sets), or legacy ordered pair results")
    parser.add_argument("--fresh-index", required=True)
    parser.add_argument("--lens", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    runtime = json.loads(Path(args.runtime).read_text())
    jobs = runtime["gpu_allocations"]+runtime.get("preemptable_allocations", [])
    if os.environ.get("SLURM_JOB_ID") not in {str(job["job_id"]) for job in jobs}:
        raise RuntimeError("Use an assigned GPU allocation")
    from olens_improve.independent import (FrozenJPP, JPP_SOURCE_REVISION, changed_source_spans,
                                          component_support, vocabulary_summary)
    fixture = json.loads(Path(args.fixture).read_text())
    checksum = hashlib.sha256()
    with Path(args.lens).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b""):
            checksum.update(chunk)
    if fixture.get("passed") is not True or fixture.get("source_revision") != JPP_SOURCE_REVISION or checksum.hexdigest() != fixture.get("lens_sha256"):
        raise ValueError("Pinned J++ source fixture/checkpoint mismatch")
    payload = json.loads(Path(args.pairs).read_text())
    fresh = {row["cell_id"]: row for row in json.loads(Path(args.fresh_index).read_text())["cells"]}
    if 'sets' in payload:
        pairs = [{'name': f"{row['kind']}:{index:03d}", 'kind':row['kind'],
                  'family':row['family'], 'descriptions':[row['a_phrase'],row['b_phrase']],
                  'generic_phrase':row['generic_phrase'], 'cell_ids':[row['a_cell_id'],row['b_cell_id']],
                  'layer':fresh[row['a_cell_id']]['layer']} for index,row in enumerate(payload['sets'])]
    else:
        pairs = payload['results']
    cells = [fresh[cell] for pair in pairs for cell in pair["cell_ids"]]
    if any(cell.get("split") not in ("dev", "development") for cell in cells):
        raise ValueError("Fitting overlap unresolved: development diagnostics only")
    if any(len(pair["descriptions"]) != 2 or len(pair["cell_ids"]) != 2 for pair in pairs):
        raise ValueError("Require explicitly ordered two-description/two-target pairs")
    import torch
    from safetensors import safe_open
    from transformers import AutoTokenizer
    torch.set_num_threads(4)
    tok = AutoTokenizer.from_pretrained(runtime["paths"]["base_snapshot"], local_files_only=True)
    reader = FrozenJPP.load(args.lens, runtime["paths"]["base_snapshot"], sorted({pair["layer"] for pair in pairs}))
    results = []
    prepared_by_cell = {}
    for pair in pairs:
        left, right = pair["descriptions"]
        differences = changed_source_spans(left, right)
        ids = [tok(text, add_special_tokens=False)["input_ids"] for text in (left, right)]
        targets = []
        for cell_id in pair["cell_ids"]:
            cell = fresh[cell_id]
            if cell["layer"] != pair["layer"] or cell.get("adapter_disabled") is not True:
                raise ValueError("Pair layer/adapter-free coordinates mismatch")
            with safe_open(cell["activation_tensor_path"], framework="pt") as source:
                activation = source.get_slice(cell["activation_tensor_key"])[cell["activation_row"]].float()
            activation_sha = hashlib.sha256(activation.numpy().tobytes()).hexdigest()
            if activation_sha != cell["activation_sha256"]:
                raise ValueError("Fresh target activation changed")
            if cell_id not in prepared_by_cell:
                logits = reader.logits(activation, pair['layer'])
                prepared_by_cell[cell_id] = vocabulary_summary(logits, tok, top_k=20)
            prepared = prepared_by_cell[cell_id]
            spans = []
            for index, difference in enumerate(differences):
                for side in ("left", "right"):
                    span = difference[side]
                    spans.append({"contrast_index": index, "side": side, "source_span": span,
                                  "standalone": component_support(span["text"], tok, prepared),
                                  "leading_space": component_support(" "+span["text"], tok, prepared) if span["text"] else None})
            targets.append({"cell_id": cell_id, "activation_sha256": activation_sha,
                            "descriptions": [component_support(text, tok, prepared) for text in (left, right)],
                            "generic_phrase": component_support(pair["generic_phrase"], tok, prepared) if pair.get("generic_phrase") else None,
                            "changed_spans": spans, "top_token_ids": prepared["top_token_ids"],
                            "top_tokens": prepared["top_tokens"]})
        results.append({"name": pair["name"], "kind":pair.get("kind"), "family":pair.get("family"), "layer": pair["layer"], "cell_ids": pair["cell_ids"],
                        "descriptions": pair["descriptions"], "source_differences": differences,
                        "same_full_phrase_token_multiset": Counter(ids[0]) == Counter(ids[1]), "targets": targets})
    result = {"scope": "isolated_known_label_development_diagnostic", "fitting_overlap": "unresolved",
              "pairs_source_sha256": hashlib.sha256(Path(args.pairs).read_bytes()).hexdigest(),
              "fixture_sha256": hashlib.sha256(Path(args.fixture).read_bytes()).hexdigest(),
              "lens_sha256": checksum.hexdigest(), "vocabulary_filter": "none", "results": results,
              "limitations": ["Component-token ranks are not joint sequence probabilities.",
                              "Unigram support cannot verify role order; equal token multisets yield identical unordered aggregates.",
                              "Presence is not proof of a relation and absence is not falsehood.",
                              "Known-label contrasts are isolated diagnostics, not candidate selection/editor feedback."],
              "job_id": os.environ["SLURM_JOB_ID"], "source_revision": JPP_SOURCE_REVISION}
    output = Path(args.output);output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"pairs": len(results), "targets": len(cells), "output": str(output)}))


if __name__ == "__main__":
    main()
