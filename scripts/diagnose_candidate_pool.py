"""DEV-only multi-hop candidate availability; gold never enters a selector.

The ceiling uses benchmark string matches, not factual verification. It is an
evaluation diagnostic and cannot be used as a deployable selection method.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from olens_improve.data import item_id, paths
from olens_improve.evaluation import load_upstream
from olens_improve.selection import parse_bullets, render_bullets


def main():
    parser = argparse.ArgumentParser()
    for name in ("samples", "selections", "manifest", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    source = load_upstream()
    from transformers import AutoTokenizer
    from wsbench.multitoken.regex import (
        contract_for, layer_passes, layer_unit_hits, scored_units,
    )

    manifest = json.loads(args.manifest.read_text())
    allowed = {c["cell_id"]: c for c in manifest["cells"]
               if c["family"] == "multihop_mt"}
    if not allowed or any(c["split"] != "development" for c in allowed.values()):
        raise ValueError("Candidate availability is an isolated development diagnostic")
    bank_path = paths("multihop_mt")["bank"]
    bank = json.loads(bank_path.read_text())
    items = {item_id(r): r for r in bank["items"]}
    contract = contract_for(bank, "multihop_mt")
    runtime = json.loads(Path("configs/runtime.json").read_text())
    tokenizer = AutoTokenizer.from_pretrained(runtime["paths"]["base_snapshot"],
                                              local_files_only=True)
    count = lambda text: len(tokenizer(text, add_special_tokens=False)["input_ids"])
    samples = defaultdict(dict)
    for line in args.samples.open():
        row = json.loads(line)
        cell_id, index = row["cell_id"], row["sample_index"]
        if cell_id not in allowed:
            continue
        if index in samples[cell_id]:
            raise ValueError("Duplicate sample")
        parsed = parse_bullets(row["text"], f"diagnostic:{cell_id}:{index}", index,
                               token_count=count, max_output_tokens=256)
        samples[cell_id][index] = render_bullets(parsed.bullets)
    selections = {r["cell_id"]: r for r in
                  (json.loads(line) for line in args.selections.open())
                  if r["cell_id"] in allowed}
    if set(samples) != set(allowed) or set(selections) != set(allowed):
        raise ValueError("Incomplete diagnostic cohort")

    rows = []
    for cell_id in sorted(allowed):
        if set(samples[cell_id]) != set(range(32)):
            raise ValueError("Require the existing complete N32 pool")
        units = scored_units(items[allowed[cell_id]["item_id"]], contract)
        hit = lambda text: layer_passes(layer_unit_hits([text], units), units)
        passes = [bool(hit(samples[cell_id][i])) for i in range(32)]
        selected = {}
        for choice in selections[cell_id]["selections"]:
            if choice["method"] in ("best_n_exact", "pooled_greedy_swap"):
                selected[f'{choice["method"]}:n{choice["n"]}'] = bool(hit(choice["text"]))
        rows.append({"cell_id": cell_id, "item_id": allowed[cell_id]["item_id"],
                     "group_id": allowed[cell_id]["group_id"],
                     "passes_by_sample_index": passes,
                     "prefixes": {str(n): {"available": any(passes[:n]),
                                             "random_expected": sum(passes[:n]) / n}
                                  for n in (1, 2, 4, 8, 16, 32)},
                     "selected": selected})
    summary = {}
    for n in (1, 2, 4, 8, 16, 32):
        summary[str(n)] = {
            "cells": len(rows),
            "cells_with_any_matched_candidate": sum(r["prefixes"][str(n)]["available"] for r in rows),
            "expected_matched_cells_under_uniform_selection": sum(r["prefixes"][str(n)]["random_expected"] for r in rows),
            "best_fve_matched_cells": sum(r["selected"][f"best_n_exact:n{n}"] for r in rows),
        }
    result = {
        "status": "complete", "split": "development", "family": "multihop_mt",
        "scope": "partial-grid candidate-availability diagnostic",
        "warning": "Gold-backed ceiling is not deployable selection. A string hit does not verify the full claim.",
        "new_generations": 0, "api_calls": 0, "summary": summary, "rows": rows,
        "source": source,
        "input_hashes": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (args.samples, args.selections, args.manifest, bank_path)},
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
