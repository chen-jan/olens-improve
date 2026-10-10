"""Export existing E3 choices for blind judging; no rescoring or generation."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    body = args.input.read_bytes()
    source = [json.loads(line) for line in body.splitlines()]
    manifest = json.loads(args.manifest.read_text())
    expected = {r["cell_id"] for r in manifest["cells"]}
    if len(source) != len(expected) or {r["cell_id"] for r in source} != expected:
        raise ValueError("Likelihood export requires the exact complete cohort")
    if any(r["split"] != "development" or r["n"] != 8 for r in source):
        raise ValueError("This export is the frozen development N8 likelihood pilot")
    baseline_methods = ("own_mean_log_likelihood", "control_mean_log_likelihood")
    rows = []
    for row in source:
        candidates = {c["sample_index"]: c["text"] for c in row["candidates"]}
        choices = [{"method": row["method"], "n": 8, "text": row["text"],
                    "sample_index": row["selected_sample_index"]}]
        choices.extend({"method": method, "n": 8, **row["likelihood_baselines"][method]}
                       for method in baseline_methods)
        for choice in choices:
            if candidates.get(choice["sample_index"]) != choice["text"]:
                raise ValueError("A likelihood choice changed its saved candidate text")
        rows.append({k: row[k] for k in ("cell_id", "family", "item_id", "layer", "position", "split")} |
                    {"selections": choices, "likelihood_spec_sha256": row["spec_sha256"]})
    selections = "".join(json.dumps(r) + "\n" for r in rows)
    methods = [{"method": c["method"], "n": c["n"]} for c in rows[0]["selections"]]
    metadata = {"source_path": str(args.input), "source_sha256": hashlib.sha256(body).hexdigest(),
                "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(selections.encode()).hexdigest(),
                "cells": len(rows), "new_generations": 0, "new_model_calls": 0,
                "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.mkdir(parents=True, exist_ok=True)
    for name, text in (("selections.jsonl", selections),
                       ("conditions.json", json.dumps(methods, indent=2) + "\n"),
                       ("export.json", json.dumps(metadata, indent=2) + "\n")):
        path = args.output / name
        if path.exists() and path.read_text() != text:
            raise ValueError("Refusing to overwrite a different likelihood export")
        if not path.exists():
            path.write_text(text)
            path.chmod(0o444)
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
