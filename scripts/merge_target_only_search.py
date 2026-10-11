#!/usr/bin/env python3
"""Seal completed whole-item target-only workers into full-family artifacts.

Streams journals, retaining their exact bytes. Only cell metadata and journal
offsets are held in memory; no activations, models, labels or control banks are
loaded. Publish a separate directory only after all source checks pass.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import random
import tempfile


METHODS = ("repeat_swap", "repeat_swap_then_prune_005", "bounded_prune_refill_005")
RANDOM_METHOD = "repeated_swaps_random_delete_match_005"
PARENT_METHOD = "pooled_greedy_swap"
CONDITIONS = [{"method": method, "n": 32} for method in (*METHODS, RANDOM_METHOD)]
IDENTITY = ("cell_id", "family", "item_id", "group_id", "layer", "position", "split", "activation_sha256")


def digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fingerprint(path):
    stat = Path(path).stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


class Sources:
    """Bind both content and file identity, including changes after an early scan."""
    def __init__(self):
        self.pins = {}

    def pin(self, path, expected=None):
        # Keep the access path, so retargeting a source symlink is detected too.
        path = Path(path).absolute()
        before = fingerprint(path)
        actual = sha(path)
        if fingerprint(path) != before:
            raise ValueError(f"Source changed during merge: {path}")
        if expected is not None and actual != expected:
            raise ValueError(f"Source hash mismatch: {path}")
        if path in self.pins and self.pins[path] != (actual, before):
            raise ValueError(f"Source changed during merge: {path}")
        self.pins[path] = actual, before
        return path

    def load(self, path, expected=None):
        path = self.pin(path, expected)
        body = json.loads(path.read_bytes())
        if fingerprint(path) != self.pins[path][1]:
            raise ValueError(f"Source changed during merge: {path}")
        return body

    def verify(self):
        for path, (expected, before) in self.pins.items():
            if fingerprint(path) != before or sha(path) != expected or fingerprint(path) != before:
                raise ValueError(f"Source changed during merge: {path}")


def no_controls(body):
    if isinstance(body, dict):
        for key, value in body.items():
            normalized = key.lower().replace("-", "_")
            if (normalized in ("control_bank", "likelihood_controls", "control_activation_bank")
                    or "control" in normalized and any(word in normalized for word in ("bank", "activation", "path"))):
                raise ValueError("Target-only merge cannot accept control-bank paths")
            no_controls(value)
    elif isinstance(body, list):
        for value in body:
            no_controls(value)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_row(row, cell, spec, inventory, spec_sha):
    no_controls(row)
    if any(row.get(key) != cell[key] for key in IDENTITY):
        raise ValueError("Original cell identity or activation SHA changed")
    if row.get("inventory_sha256") != spec["inventory_sha256"] or row.get("search_spec_sha256") != spec_sha:
        raise ValueError("Row inventory or search spec digest differs")
    if (row.get("whitener_sha256") != spec["whitener_sources"][str(cell["layer"])]["sha256"]
            or row.get("vector_contract_sha256") != inventory["vector_contract"]["sha256"]):
        raise ValueError("Row frozen numerical source differs")
    atoms = {a["phrase_id"]: a for a in row["atoms"]}
    if len(atoms) != len(row["atoms"]):
        raise ValueError("Duplicate source atom")
    samples = row["source_samples"]
    if len(samples) != 32 or {s["sample_index"] for s in samples} != set(range(32)):
        raise ValueError("Require the fixed shared 32-sample source pool")
    sample_ids = {s["sample_id"] for s in samples}
    if len(sample_ids) != 32 or any(a["sample_id"] not in sample_ids for a in atoms.values()):
        raise ValueError("Atom source sample provenance differs")
    selections = row["selections"]
    keys = [(s["method"], s["n"]) for s in selections]
    expected = [(s["method"], s["n"]) for s in CONDITIONS] + [(PARENT_METHOD, 32)]
    if keys != expected:
        raise ValueError("Row condition menu differs or contains duplicates")
    by_method = {s["method"]: s for s in selections}
    for selected in selections:
        ids = selected["phrase_ids"]
        if (not isinstance(ids, list) or len(set(ids)) != len(ids) or not set(ids) <= set(atoms)
                or not isinstance(selected.get("text"), str)
                or any(type(selected.get(key)) is not int or not 0 <= selected[key] <= cap
                       for key, cap in (("bullet_count", 4), ("token_count", 256)))
                or selected["bullet_count"] != len(ids)):
            raise ValueError("Selection violates verbatim atom provenance or output caps")
        text = ""
        for pid in ids:
            if text and not text.endswith("\n"):
                text += "\n"
            text += "- " + atoms[pid]["text"]
        if text != selected["text"]:
            raise ValueError("Selection changed original bullet text")
        fit = selected["fits"]["exact"]
        if (set(fit["atom_ids"]) != set(ids) or len(fit["atom_ids"]) != len(ids)
                or not finite(fit["fve"]) or selected.get("fits_scope") != "emitted_bullets"):
            raise ValueError("Exact reconstruction fit differs from emitted bullets")
        method = selected["method"]
        if method in METHODS:
            measured = selected.get("budget", {})
            if (measured.get("subset_fit_budget") != inventory["search"]["subset_fit_budget"]
                    or type(measured.get("subset_fits")) is not int
                    or not 0 <= measured["subset_fits"] <= measured["subset_fit_budget"]):
                raise ValueError("Selection violated frozen subset-fit budget")
        if method in METHODS[1:]:
            loo = selected.get("leave_one_out")
            if (not isinstance(loo, dict) or set(loo) != set(ids)
                    or any(not finite(gain) or gain <= .005 + 1e-8 for gain in loo.values())):
                raise ValueError("Missing strict retained leave-one-out contribution evidence")
    plain, pruned, randomized, parent = (by_method[m] for m in
        ("repeat_swap", "repeat_swap_then_prune_005", RANDOM_METHOD, PARENT_METHOD))
    for method in ("repeat_swap", "bounded_prune_refill_005"):
        if by_method[method].get("parent_phrase_ids") != parent["phrase_ids"] or by_method[method].get("parent_method") != PARENT_METHOD:
            raise ValueError("Initial plain-pooling parent differs")
    if (pruned.get("parent_phrase_ids") != plain["phrase_ids"] or pruned.get("parent_method") != "repeat_swap"
            or not set(pruned["phrase_ids"]) <= set(plain["phrase_ids"])):
        raise ValueError("Guided pruning is not a deletion of its actual swap parent")
    seed = int(digest(["target_only_random_delete_match_005_v1", cell["cell_id"]])[:16], 16)
    keep = set(random.Random(seed).sample(range(len(plain["phrase_ids"])), len(pruned["phrase_ids"])))
    expected_random = [pid for i, pid in enumerate(plain["phrase_ids"]) if i in keep]
    control = randomized.get("random_control", {})
    if (randomized["phrase_ids"] != expected_random or randomized.get("parent_phrase_ids") != plain["phrase_ids"]
            or randomized.get("parent_method") != "repeat_swap" or control.get("seed") != seed
            or control.get("retained_bullet_count") != len(pruned["phrase_ids"])):
        raise ValueError("Random deletion differs from deterministic exact-count parent subset")
    cached = row["cached_parent_source"]
    original = inventory["stages"][cell["split"]]["selectors"]
    if (any(cached.get(k) != original[k] for k in ("path", "sha256"))
            or cached.get("method") != PARENT_METHOD or cached.get("n") != 32
            or not finite(cached.get("source_exact_fve")) or not finite(cached.get("replayed_exact_fve"))
            or abs(cached["source_exact_fve"] - cached["replayed_exact_fve"]) > 1e-5
            or abs(parent["fits"]["exact"]["fve"] - cached["replayed_exact_fve"]) > 1e-8):
        raise ValueError("Original plain-pooling parent source or replay differs")


def write_json(path, body):
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")


def merge(inventory_path, inventory_sha256, shard_paths, output, *, whole_journal=False):
    output = Path(output).resolve()
    sources = Sources()
    inventory = sources.load(inventory_path, inventory_sha256)
    no_controls(inventory)
    if inventory.get("status") != "sealed":
        raise ValueError("Require a sealed target-only inventory")
    if (inventory["search"]["threshold"] != .005 or inventory["search"]["tolerance"] != 1e-8
            or inventory["search"]["max_bullets"] != 4 or inventory["search"]["max_qwen_tokens"] != 256
            or [{"method": s["method"], "n": s["n"]} for s in inventory["conditions"]] != CONDITIONS):
        raise ValueError("Inventory numerical bounds or exact condition menu differs")
    fresh = sources.load(inventory["fresh_manifest"]["path"], inventory["fresh_manifest"]["sha256"])
    cells = {c["cell_id"]: c for c in fresh["cells"]}
    items = sorted({(c["family"], c["item_id"]) for c in cells.values()})
    if (not cells or len(cells) != len(fresh["cells"]) or len(cells) != inventory["expected"]["cells"]
            or len(items) != inventory["expected"]["items"] or {c["family"] for c in cells.values()} != set(inventory["families"])):
        raise ValueError("Fresh source grid differs from sealed inventory")
    workers, indexes, common = [], set(), None
    routing = {k: inventory[k] for k in ("fresh_manifest", "stages", "vector_contract", "families", "scope")}
    for directory in map(Path, shard_paths):
        directory = directory.resolve()
        if directory == output or output in directory.parents or directory in output.parents:
            raise ValueError("Merge output must be separate from shard artifacts")
        spec = sources.load(directory / "spec.json")
        status = sources.load(directory / "status.json")
        no_controls(spec)
        index, count = spec["shard_index"], spec["shard_count"]
        if type(index) is not int or type(count) is not int or count != len(shard_paths) or not 0 <= index < count or index in indexes:
            raise ValueError("Missing, duplicate or incompatible worker shard indexes")
        indexes.add(index)
        own_items = set(items[index::count])
        intended = sorted(cid for cid, cell in cells.items() if (cell["family"], cell["item_id"]) in own_items)
        spec_sha = digest(spec)
        partial = set(intended) != set(cells)
        if spec.get("cell_ids") != intended or spec.get("partial_grid") != partial:
            raise ValueError("Incomplete grid or wrong whole-item shard stride")
        if (status.get("status") != "complete" or status.get("completed_cells") != len(intended)
                or status.get("expected_cells") != len(intended) or status.get("partial_grid") != partial
                or status.get("inventory_sha256") != inventory_sha256 or status.get("search_spec_sha256") != spec_sha
                or status.get("new_model_calls") != 0 or status.get("new_api_calls") != 0):
            raise ValueError("Worker status is not complete under its frozen spec")
        scientific = {k: v for k, v in spec.items() if k not in ("cell_ids", "shard_index", "partial_grid")}
        if common is not None and scientific != common:
            raise ValueError("Workers used changed common configurations")
        common = scientific
        expected_configs = [{"method": m} | {k: inventory["search"][k] for k in
            ("subset_fit_budget", "max_swap_steps", "max_rounds", "threshold", "tolerance", "max_bullets")} for m in METHODS]
        if (spec.get("inventory_sha256") != inventory_sha256 or spec.get("conditions") != CONDITIONS
                or spec.get("input_contract") != "one_target_activation_shared_32_readouts_matched_frozen_AR_whitener"
                or spec.get("configs") != expected_configs or spec.get("source_routing") != routing
                or spec.get("controls_used") is not False or spec.get("new_model_calls") != 0
                or spec.get("new_api_calls") != 0 or spec.get("max_output_tokens") != 256
                or spec.get("parent_method") != PARENT_METHOD or spec.get("n") != 32
                or spec.get("runtime_sha256") != inventory["runtime_inputs"]["runtime"]["sha256"]
                or spec.get("whitener_directory") != inventory["runtime_inputs"]["whitener_directory"]):
            raise ValueError("Worker spec differs from sealed target-only contract")
        for layer in {cells[cid]["layer"] for cid in intended}:
            w = spec["whitener_sources"][str(layer)]
            if (w["sha256"] != inventory["runtime_inputs"]["whitener_moments_sha256"][str(layer)]
                    or Path(w["path"]) != Path(spec["whitener_directory"]) / f"whitening_iolens_pooled_L{layer}.safetensors"):
                raise ValueError("Frozen whitening source differs")
        if sources.load(directory / "conditions.json") != CONDITIONS:
            raise ValueError("Worker condition menu changed")
        descriptors = status.get("family_descriptors", [])
        if len(descriptors) != len({cells[cid]["family"] for cid in intended}):
            raise ValueError("Missing or duplicate terminal family descriptors")
        seen_families = set()
        for descriptor in descriptors:
            family = descriptor["family"]
            own = {cid for cid in intended if cells[cid]["family"] == family}
            if not own or family in seen_families:
                raise ValueError("Foreign or duplicate terminal family descriptor")
            seen_families.add(family)
            if (sources.load(directory / f"{family}.ready.json") != descriptor
                    or descriptor.get("ready") != (not partial) or descriptor.get("partial_grid") != partial
                    or descriptor.get("inventory_sha256") != inventory_sha256
                    or descriptor.get("search_spec_sha256") != spec_sha or descriptor.get("conditions") != CONDITIONS
                    or descriptor.get("cells") != len(own) or descriptor.get("items") != len({cells[c]["item_id"] for c in own})
                    or Path(descriptor["selections"]).resolve() != directory / f"{family}.jsonl"
                    or Path(descriptor["manifest"]).resolve() != directory / f"{family}.manifest.json"):
                raise ValueError("Terminal partial-family descriptor differs")
            sources.pin(descriptor["selections"], descriptor["selection_sha256"])
            manifest = sources.load(descriptor["manifest"], descriptor["manifest_sha256"])
            listed = {c["cell_id"]: c for c in manifest["cells"]}
            if (len(listed) != len(manifest["cells"]) or listed != {cid: cells[cid] for cid in own}
                    or manifest.get("inventory_sha256") != inventory_sha256
                    or manifest.get("search_spec_sha256") != spec_sha or manifest.get("partial_grid") != partial):
                raise ValueError("Partial manifest changed original fresh cells")
        workers.append({"path": directory, "index": index, "spec": spec, "spec_sha": spec_sha,
                        "status": status, "intended": set(intended)})
    if indexes != set(range(len(shard_paths))):
        raise ValueError("Missing worker shard indexes")
    locations, cell_specs = {}, {}
    for worker in sorted(workers, key=lambda w: w["index"]):
        journal = worker["path"] / "selections.jsonl"
        before, value, own = fingerprint(journal), hashlib.sha256(), set()
        with journal.open("rb") as stream:
            while True:
                offset = stream.tell()
                line = stream.readline()
                if not line:
                    break
                if not line.endswith(b"\n"):
                    raise ValueError("Uncommitted journal tail")
                value.update(line)
                row = json.loads(line)
                cid = row["cell_id"]
                if cid in locations or cid not in worker["intended"]:
                    raise ValueError("Duplicate, missing or foreign journal cell")
                validate_row(row, cells[cid], worker["spec"], inventory, worker["spec_sha"])
                own.add(cid)
                locations[cid] = journal, offset, len(line)
                cell_specs[cid] = worker["spec_sha"]
        if fingerprint(journal) != before:
            raise ValueError("Source changed during merge")
        if value.hexdigest() != worker["status"].get("selection_sha256"):
            raise ValueError("Journal hash mismatch with completed status")
        sources.pins[journal] = value.hexdigest(), before
        if own != worker["intended"]:
            raise ValueError("Incomplete worker journal grid")
    if set(locations) != set(cells):
        raise ValueError("Merged grid is incomplete")
    source_records = [{"path": str(w["path"]), "shard_index": w["index"], "search_spec_sha256": w["spec_sha"],
        "spec_sha256": sources.pins[w["path"] / "spec.json"][0],
        "status_sha256": sources.pins[w["path"] / "status.json"][0],
        "selection_sha256": sources.pins[w["path"] / "selections.jsonl"][0], "cells": len(w["intended"])}
        for w in sorted(workers, key=lambda w: w["index"])]
    merge_spec = {"schema_version": 1, "inventory_sha256": inventory_sha256, "common_spec": common,
                  "source_workers": source_records, "partial_grid": False, "cell_ids": sorted(cells)}
    merge_sha = digest(merge_spec)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-merge-", dir=output.parent) as temp:
        staged = Path(temp) / "sealed"
        staged.mkdir()
        descriptors = []
        with ExitStack() as stack:
            readers = {w["path"] / "selections.jsonl": stack.enter_context((w["path"] / "selections.jsonl").open("rb")) for w in workers}
            writers = {family: stack.enter_context((staged / f"{family}.jsonl").open("wb")) for family in inventory["families"]}
            full = stack.enter_context((staged / "selections.jsonl").open("wb")) if whole_journal else None
            for cid in sorted(cells):
                path, offset, length = locations[cid]
                readers[path].seek(offset)
                line = readers[path].read(length)
                writers[cells[cid]["family"]].write(line)
                if full:
                    full.write(line)
        for family in inventory["families"]:
            own = [cells[cid] for cid in sorted(cells) if cells[cid]["family"] == family]
            manifest_name, selection_name = f"{family}.manifest.json", f"{family}.jsonl"
            own_specs = {c["cell_id"]: cell_specs[c["cell_id"]] for c in own}
            write_json(staged / manifest_name, {"schema_version": 1, "split": "expansion", "scope": inventory["scope"],
                "partial_grid": False, "inventory_sha256": inventory_sha256, "search_spec_sha256": merge_sha, "cells": own})
            descriptor = {"ready": True, "partial_grid": False, "family": family,
                "manifest": str(output / manifest_name), "manifest_sha256": sha(staged / manifest_name),
                "selections": str(output / selection_name), "selection_sha256": sha(staged / selection_name),
                "conditions": CONDITIONS, "inventory_sha256": inventory_sha256, "search_spec_sha256": merge_sha,
                "search_spec_sha256_by_cell": own_specs, "source_search_spec_sha256": sorted(set(own_specs.values())),
                "merge": str(output / "merge.json"), "cells": len(own), "items": len({c["item_id"] for c in own}),
                "source_parents": [inventory["stages"][s]["selectors"] for s in sorted({c["split"] for c in own})]}
            write_json(staged / f"{family}.ready.json", descriptor)
            descriptors.append(descriptor)
        metadata = {"schema_version": 1, "status": "complete", "partial_grid": False, "cells": len(cells),
            "items": len(items), "inventory_sha256": inventory_sha256, "fresh_manifest": inventory["fresh_manifest"],
            "search_spec_sha256": merge_sha, "merge_spec": merge_spec, "sources": source_records,
            "source_files": {str(path): pin[0] for path, pin in sorted(sources.pins.items())},
            "conditions": CONDITIONS, "family_descriptors": descriptors, "new_model_calls": 0, "new_api_calls": 0,
            "quality_status": "unjudged", "row_policy": "original journal rows retained byte-for-byte",
            "code_sha256": sha(Path(__file__))}
        if whole_journal:
            metadata["selection_sha256"] = sha(staged / "selections.jsonl")
        write_json(staged / "merge.json", metadata)
        write_json(staged / "conditions.json", CONDITIONS)
        write_json(staged / "status.json", {"status": "complete", "completed_cells": len(cells),
            "expected_cells": len(cells), "partial_grid": False, "inventory_sha256": inventory_sha256,
            "search_spec_sha256": merge_sha, "merge_sha256": sha(staged / "merge.json"),
            "new_model_calls": 0, "new_api_calls": 0, "quality_status": "unjudged", "family_descriptors": descriptors})
        sources.verify()
        if output.exists():
            wanted = {p.name for p in staged.iterdir()}
            if (not output.is_dir() or {p.name for p in output.iterdir()} != wanted
                    or any(not (output / name).is_file() or sha(output / name) != sha(staged / name) for name in wanted)):
                raise ValueError("Refusing to overwrite changed merged artifacts")
        else:
            for path in staged.iterdir():
                path.chmod(0o444)
            os.rename(staged, output)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--shard", type=Path, action="append", required=True, help="Completed worker output directory; repeat for all workers")
    parser.add_argument("--output", type=Path, required=True, help="Separate sealed output directory")
    parser.add_argument("--whole-journal", action="store_true", help="Also emit merged selections.jsonl")
    args = parser.parse_args()
    result = merge(args.inventory, args.inventory_sha256, args.shard, args.output, whole_journal=args.whole_journal)
    print(json.dumps({k: result[k] for k in ("status", "cells", "items", "inventory_sha256", "search_spec_sha256")}, indent=2))


if __name__ == "__main__":
    main()
