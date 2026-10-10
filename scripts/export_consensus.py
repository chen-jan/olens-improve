"""Export fixed-evidence consensus ablations without making model calls."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from olens_improve.helpers import reselect_consensus, report_with_merge_veto
from olens_improve.selection import exact_consensus, output_admissible, parse_bullets


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path, content):
    if path.exists() and path.read_text() != content:
        raise ValueError(f"Existing immutable export differs: {path}")
    path.write_text(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n", type=int, default=16)
    parser.add_argument("--label-version", choices=("v4", "v5", "v5_medium"), default="v4")
    args = parser.parse_args()
    from transformers import AutoTokenizer
    runtime = json.loads(Path("configs/runtime.json").read_text())
    tokenizer = AutoTokenizer.from_pretrained(runtime["paths"]["base_snapshot"], local_files_only=True)
    count = lambda text: len(tokenizer(text, add_special_tokens=False)["input_ids"])
    admissible = output_admissible(count, 256)
    manifest = json.loads(args.manifest.read_text())
    cells = {r["cell_id"]: r for r in manifest["cells"]}
    if any(r["split"] != "development" for r in cells.values()):
        raise ValueError("This export is restricted to the frozen development pilot")
    pools = defaultdict(list)
    for line in args.records.open():
        row = json.loads(line)
        if row["cell_id"] in cells and row["sample_index"] < args.n:
            pools[row["cell_id"]].append(row)
    reports = [json.loads(s) for s in args.reports.read_text().splitlines()]
    if len(reports) != len(cells) or {r["cell_id"] for r in reports} != set(cells):
        raise ValueError("Report cohort is incomplete or differs from the frozen manifest")
    fractions = (0.0, 0.125, 0.25, 0.5, 0.75, 1.0)
    output, diagnostics, conditions = [], defaultdict(Counter), []
    for row in sorted(reports, key=lambda r: r["cell_id"]):
        cid = row["cell_id"]
        pool = sorted(pools[cid], key=lambda r: r["sample_index"])
        if [r["sample_index"] for r in pool] != list(range(args.n)) or row["pool_n"] != args.n:
            raise ValueError("Missing or duplicated candidate prefix")
        samples = [parse_bullets(r["text"], f'{cid}:s{r["sample_index"]:02d}', r["sample_index"],
                                token_count=count, max_output_tokens=256) for r in pool]
        versions = row["report"]["prompt_versions"]
        expected = (["candidate-pair-proposal-v1", "whole-bullet-equivalence-compatibility-v4"]
                    if args.label_version == "v4" else
                    ["candidate-pair-proposal-local-ids-v2", "whole-bullet-equivalence-compatibility-v5-local-ids-v1"])
        if versions != expected:
            raise ValueError("Stored label versions differ from the explicitly declared export")
        if args.label_version == "v5_medium" and row["report"].get("reasoning_effort") != "medium":
            raise ValueError("Medium export requires explicit medium replay provenance")
        original = reselect_consensus(samples, row["report"], fraction=.25,
                                      filter_compatibility=True, admissible=admissible)
        if original["text"] != row["text"]:
            raise ValueError("Offline reproduction of the original native output failed")
        selections = []
        for fraction in fractions:
            tag = format(fraction, "g")
            exact = exact_consensus(samples, min_support_fraction=fraction, admissible=admissible)
            variants = [(f"consensus_exact_support{tag}", exact.text,
                         {"phrase_ids": list(exact.phrase_ids), "compatibility_filter": False})]
            for compatible in (False, True):
                for veto in ((False,) if args.label_version == "v4" else (False, True)):
                    evidence = report_with_merge_veto(samples,row["report"],enabled=veto)
                    result = reselect_consensus(samples, evidence, fraction=fraction,
                                               filter_compatibility=compatible, admissible=admissible)
                    result["merge_veto"] = evidence.get("merge_veto")
                    suffix = "" if args.label_version == "v4" else f'_veto{"on" if veto else "off"}'
                    variants.append((f'consensus_semantic_{args.label_version}_support{tag}_compat{"on" if compatible else "off"}{suffix}',
                                     result["text"], result))
            for method, text, trace in variants:
                selections.append({"method": method, "n": args.n, "text": text,
                    "token_count": count(text), "bullet_count": len(parse_bullets(text, "output", 0).bullets),
                    "phrase_ids": trace["phrase_ids"], "fits": None, "trace": trace,
                    "support_fraction": fraction, "prompt_versions": versions,
                    "candidate_access": "within-cell original N16 pool; verbatim text; no new calls"})
                diagnostics[method][f'{row["family"]}:intended'] += 1
                diagnostics[method][f'{row["family"]}:empty'] += int(not text.strip())
                if len(output) == 0:
                    conditions.append({"method": method, "n": args.n})
        output.append({**{k: cells[cid][k] for k in ("cell_id", "family", "item_id", "layer", "position", "split")},
                       "selections": selections})
    args.output.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in output)
    write_once(args.output / "selections.jsonl", payload)
    write_once(args.output / "conditions.json", json.dumps(conditions, indent=2) + "\n")
    metadata = {"records_sha256": digest(args.records), "reports_sha256": digest(args.reports),
        "manifest_sha256": digest(args.manifest), "export_sha256": digest(args.output / "selections.jsonl"),
        "script_sha256": digest(Path(__file__)), "cells": len(output), "conditions": len(conditions),
        "output_cap": {"bullets": 4, "Qwen_tokens": 256}, "new_helper_calls": 0,
        "coverage": {k: dict(v) for k, v in diagnostics.items()},
        "label_version": args.label_version,
        "limitations": ["Labels have limited qualitative audits; exports are diagnostics, not automatic promotion evidence.",
            "Support is a lower bound under the fixed pair cap. Unchecked compatibility stays unknown.",
            "Empty readouts are coverage loss, not evidence of faithful interpretation."]}
    write_once(args.output / "export.json", json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({k: metadata[k] for k in ("cells", "conditions", "export_sha256", "new_helper_calls")}))


if __name__ == "__main__":
    main()
