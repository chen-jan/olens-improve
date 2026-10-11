"""CPU cache-only target-local search; never reads a control bank or labels.

Run a bounded pilot with --max-cells 12 (metadata-stratified selection) in an
allocated CPU job. Source hashes and all search bounds are resume contracts.
Only one target activation row is accessed while preparing each search input.
"""
import argparse
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from olens_improve.ar_cache import digest, vector_key
from olens_improve.reconstruction import JointNNLS, RawVectorCache, Whitener, ar_token_ids
from olens_improve.selection import Selection, output_admissible, parse_bullets, render_bullets
from olens_improve.target_only_search import METHODS, SearchConfig, search_target_only


RANDOM_METHOD = "repeated_swaps_random_delete_match_005"
CONDITIONS = [{"method": m, "n": 32} for m in (*METHODS, RANDOM_METHOD)]
PARENT_METHOD = "pooled_greedy_swap"
FAST = Path("${OLENS_COMPUTE_ROOT}")
CHECKPOINT = FAST / "cache/huggingface/hub/models--agu18dec--olens_and_ar/snapshots/c95215d5d2f6250f20c305ae55c6e4d7569f92dc/ar_ptag_pooled"
WHITENERS = FAST / "cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic(path, payload):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(temp, path)


def committed_lines(path):
    with Path(path).open() as stream:
        for line in stream:
            if not line.endswith("\n"):
                raise ValueError("Uncommitted source tail")
            yield json.loads(line)


def verified(descriptor):
    if sha(descriptor["path"]) != descriptor["sha256"]:
        raise ValueError(f"Frozen source changed: {descriptor['path']}")
    return Path(descriptor["path"])


def pilot_targets(cells, limit):
    """Round-robin metadata buckets, independent of text/FVE/benchmark labels."""
    buckets = defaultdict(list)
    for cid, cell in cells.items():
        buckets[(cell["split"], cell["family"], cell["layer"])].append(cid)
    for rows in buckets.values():
        rows.sort(key=lambda cid: digest(["target_only_timing_pilot_v1", cid]))
    # Interleave stages and families before layers so 12 cells span all 12 pairs.
    pairs = sorted({(split, family) for split, family, _ in buckets})
    keys = []
    for layer_index in range(max(sum(k[:2] == pair for k in buckets) for pair in pairs)):
        for pair_index, pair in enumerate(pairs):
            own = sorted(k for k in buckets if k[:2] == pair)
            shift = pair_index % len(own)
            own = own[shift:] + own[:shift]
            if layer_index < len(own):
                keys.append(own[layer_index])
    result = []
    while len(result) < limit:
        progress = False
        for key in keys:
            if buckets[key]:
                result.append(buckets[key].pop(0))
                progress = True
                if len(result) == limit:
                    break
        if not progress:
            break
    return result


def prepare_target(records, parent, cell, cache, tags, tokenizer, whitener):
    """Bind only this target's 32 shared readouts to frozen cached AR vectors."""
    import torch
    from safetensors import safe_open
    if set(records) != set(range(32)):
        raise ValueError("Require complete fixed shared N32 pool")
    count = lambda text: len(tokenizer(text, add_special_tokens=False)["input_ids"])
    representatives = {}
    source_samples = []
    for index in range(32):
        row = records[index]
        if row["cell_id"] != cell["cell_id"] or row["activation_sha256"] != cell["activation_sha256"]:
            raise ValueError("Source sample has different target activation")
        if any(row[k] != cell[k] for k in ("family", "item_id", "layer", "position")):
            raise ValueError("Source sample routing identity changed")
        if row.get("base_revision") != cache.contract["base_revision"] or row.get("adapter_revision") != cache.contract["pair_revision"]:
            raise ValueError("Sample frozen model revisions differ")
        sample_id = f"{row.get('global_pool_id') or row['pool_id']}:{cell['cell_id']}:{index}"
        sample = parse_bullets(row["text"], sample_id, index, token_count=count, max_output_tokens=256)
        source_samples.append({"sample_index": index, "sample_id": sample_id,
                               "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
                               "parser_flags": list(sample.flags)})
        if not sample.parsing_uncertain:
            for b in sample.bullets:
                _, ids = ar_token_ids(tokenizer, b.text)
                if ids:
                    representatives.setdefault(b.text, (b, ids))
    pool = tuple(b for b, _ in representatives.values())
    if len(parent["atoms"]) != parent["bullet_count"]:
        raise ValueError("Cached parent atom/count mismatch")
    mapped_parent = tuple(representatives[atom["text"]][0] for atom in parent["atoms"])
    if render_bullets(mapped_parent) != parent["text"]:
        raise ValueError("Verbatim cached plain parent changed")
    atoms, vectors = {}, {}
    bullet_keys = {}
    for b, ids in representatives.values():
        key = vector_key(cache.contract["sha256"], tags[cell["layer"]], ids[:32])
        bullet_keys[b.phrase_id] = key
        atoms[b.phrase_id] = {"phrase_id": b.phrase_id, "text": b.text, "sample_id": b.sample_id,
                              "sample_index": int(b.sample_id.rsplit(":", 1)[1]), "position": b.position,
                              "source_start": b.start, "source_end": b.end, "cache_key": key,
                              "scored_token_ids": ids[:32], "original_token_count": len(ids),
                              "truncated": len(ids) > 32}
    keys = list(dict.fromkeys(bullet_keys.values()))
    if keys:
        transformed = whitener.whiten(torch.stack([cache.get(key) for key in keys]))
        transformed = transformed / (transformed.norm(dim=1, keepdim=True) + 1e-9)
        by_key = dict(zip(keys, transformed))
        vectors = {pid: by_key[key] for pid, key in bullet_keys.items()}
    # Access exactly one activation row; do not materialize the activation bank.
    with safe_open(cell["activation_tensor_path"], framework="pt", device="cpu") as tensor:
        raw = tensor.get_slice("resid")[cell["activation_row"]:cell["activation_row"] + 1][0]
    if hashlib.sha256(raw.numpy().tobytes()).hexdigest() != cell["activation_sha256"]:
        raise ValueError("Target activation changed")
    target = whitener.whiten(raw.reshape(1, -1))[0]
    replay = JointNNLS(target, vectors)
    mapped_ids = tuple(b.phrase_id for b in mapped_parent)
    fit = replay.fit(tuple(sorted(mapped_ids)))
    if abs(fit.fve - parent["fits"]["exact"]["fve"]) > 1e-5:
        raise ValueError("Cached plain parent FVE failed independent replay")
    if not output_admissible(count, 256)(mapped_parent):
        raise ValueError("Cached parent violates common output cap")
    return pool, mapped_parent, target, vectors, atoms, source_samples, fit, count


def evaluate_target(pool, parent, target, vectors, *, count, cell_id, subset_fit_budget=2048,
                    max_swap_steps=8, max_rounds=2):
    """Fresh per-method scorer state makes fit/CPU budget comparison explicit."""
    admissible = output_admissible(count, 256)
    records = []
    results = {}
    for method in METHODS:
        scorer = JointNNLS(target, vectors)
        started = time.perf_counter()
        result = search_target_only(pool, parent, scorer.score,
            config=SearchConfig(method, subset_fit_budget, max_swap_steps, max_rounds), admissible=admissible)
        elapsed = time.perf_counter() - started
        selected = result.selection
        # Canonical output fit is already metered/cached; no extra NNLS solve.
        fit = scorer.fit(tuple(sorted(selected.phrase_ids)))
        if len(scorer._cache) != result.budget["subset_fits"]:
            raise ValueError("Subset-fit meter disagrees with physical NNLS fits")
        records.append({"method": method, "n": 32, "text": selected.text,
                        "phrase_ids": list(selected.phrase_ids), "token_count": count(selected.text),
                        "bullet_count": len(selected.bullets), "fits": {"exact": asdict(fit)},
                        "fits_scope": "emitted_bullets", "trace": list(selected.trace),
                        "budget": result.budget, "stop_flags": list(result.stop_flags),
                        "leave_one_out": result.leave_one_out, "seconds": elapsed,
                        "parent_method": PARENT_METHOD if method != "repeat_swap_then_prune_005" else "repeat_swap",
                        "parent_phrase_ids": list(result.parent_phrase_ids if method != "repeat_swap_then_prune_005" else result.refined_phrase_ids)})
        results[method] = result
    plain = results["repeat_swap"].selection
    pruned = results["repeat_swap_then_prune_005"].selection
    if plain.phrase_ids != results["repeat_swap_then_prune_005"].refined_phrase_ids:
        raise ValueError("Pruning ablation used a different repeated-swap parent")
    if not set(pruned.phrase_ids).issubset(plain.phrase_ids):
        raise ValueError("Terminal pruned output is not a deletion of the refined parent")
    seed = int(digest(["target_only_random_delete_match_005_v1", cell_id])[:16], 16)
    rng = random.Random(seed)
    keep = set(rng.sample(range(len(plain.bullets)), len(pruned.bullets)))
    selected = Selection(RANDOM_METHOD, tuple(b for i, b in enumerate(plain.bullets) if i in keep), None)
    scorer = JointNNLS(target, vectors)
    fit = scorer.fit(tuple(sorted(selected.phrase_ids)))
    records.append({"method": RANDOM_METHOD, "n": 32, "text": selected.text,
                    "phrase_ids": list(selected.phrase_ids), "token_count": count(selected.text),
                    "bullet_count": len(selected.bullets), "fits": {"exact": asdict(fit)},
                    "fits_scope": "emitted_bullets", "parent_method": "repeat_swap",
                    "parent_phrase_ids": list(plain.phrase_ids), "trace": [], "stop_flags": [],
                    "budget": {"incremental_subset_fits": 1,
                               "shared_parent_search_budget": results["repeat_swap"].budget,
                               "deletion_count_reference_method": "repeat_swap_then_prune_005"},
                    "random_control": {"seed": seed, "retained_bullet_count": len(pruned.bullets),
                                       "matches": "bullet_count; not exact token length"}})
    if any(r["bullet_count"] > 4 or r["token_count"] > 256 for r in records):
        raise ValueError("Search output violated caps")
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inventory", type=Path, default=Path("configs/expansion_manifest_v1.json"))
    p.add_argument("--inventory-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--runtime", type=Path, default=Path("configs/runtime.json"))
    p.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    p.add_argument("--whitener-directory", type=Path, default=WHITENERS)
    p.add_argument("--cell-id", action="append")
    p.add_argument("--max-cells", type=int)
    p.add_argument("--subset-fit-budget", type=int, default=2048)
    p.add_argument("--max-swap-steps", type=int, default=8)
    p.add_argument("--max-rounds", type=int, default=2)
    p.add_argument("--torch-threads", type=int, default=1)
    p.add_argument("--max-resident-vector-shards", type=int, default=8)
    p.add_argument("--shard-count", type=int, default=1)
    p.add_argument("--shard-index", type=int, default=0)
    a = p.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Cache replay/search requires allocated CPU resources")
    if (a.max_cells is not None and a.max_cells < 1) or a.torch_threads < 1 or a.max_resident_vector_shards < 1:
        raise ValueError("Positive cell/thread bounds required")
    if a.shard_count < 1 or not 0 <= a.shard_index < a.shard_count:
        raise ValueError("Invalid whole-item worker shard")
    if a.cell_id and len(set(a.cell_id)) != len(a.cell_id):
        raise ValueError("Duplicate requested cell IDs")
    if a.cell_id and a.max_cells:
        raise ValueError("Use explicit IDs or metadata-stratified max-cells")
    configs = [SearchConfig(m, a.subset_fit_budget, a.max_swap_steps, a.max_rounds) for m in METHODS]
    verified({"path": str(a.inventory), "sha256": a.inventory_sha256})
    inventory = json.loads(a.inventory.read_text())
    if inventory["status"] != "sealed":
        raise ValueError("Source inventory must be sealed")
    if "control_bank" in inventory or "likelihood_controls" in inventory:
        raise ValueError("Target-only search inventories must omit other-activation banks")
    frozen = inventory["search"]
    for name in ("subset_fit_budget", "max_swap_steps", "max_rounds"):
        if getattr(a, name) != frozen[name]:
            raise ValueError("Search argument differs from the sealed inventory: " + name)
    if any(asdict(config)[name] != frozen[name]
           for config in configs for name in ("threshold", "tolerance", "max_bullets")):
        raise ValueError("Search numerical rules differ from the sealed inventory")
    pinned = inventory["runtime_inputs"]
    if (Path(pinned["runtime"]["path"]).resolve() != a.runtime.resolve()
            or sha(a.runtime) != pinned["runtime"]["sha256"]
            or Path(pinned["checkpoint"]).resolve() != a.checkpoint.resolve()
            or Path(pinned["whitener_directory"]).resolve() != a.whitener_directory.resolve()):
        raise ValueError("Frozen runtime or whitening source differs")
    # These are the only consumed inventory fields. No control-bank path is read.
    routing = {k: inventory[k] for k in ("fresh_manifest", "stages", "vector_contract", "families", "scope")}
    fresh = json.loads(verified(routing["fresh_manifest"]).read_text())
    cells = {c["cell_id"]: c for c in fresh["cells"]}
    if len(cells) != len(fresh["cells"]):
        raise ValueError("Duplicate fresh target cell")
    items = sorted({(c["family"], c["item_id"]) for c in cells.values()})
    own_items = set(items[a.shard_index::a.shard_count])
    own_cells = {cid: c for cid, c in cells.items() if (c["family"], c["item_id"]) in own_items}
    targets = a.cell_id or (pilot_targets(own_cells, a.max_cells) if a.max_cells else sorted(own_cells))
    if set(targets) - set(cells):
        raise ValueError("Unknown target cell")
    if set(targets) - set(own_cells):
        raise ValueError("Explicit cells lie outside this worker shard")
    partial = set(targets) != set(cells)
    import torch
    from transformers import AutoTokenizer
    torch.set_num_threads(a.torch_threads)
    if sha(a.checkpoint / "heads.pt") != routing["vector_contract"]["head_sha256"]:
        raise ValueError("Frozen AR head changed")
    state = torch.load(a.checkpoint / "heads.pt", map_location="cpu", weights_only=True)
    tags = {int(layer): state["tag_ids"][i].tolist() for i, layer in enumerate(state["layers"])}
    runtime = json.loads(a.runtime.read_text())
    tokenizer = AutoTokenizer.from_pretrained(runtime["paths"]["base_snapshot"], local_files_only=True)
    spec = {"schema_version": 1, "inventory_sha256": a.inventory_sha256,
            "input_contract": "one_target_activation_shared_32_readouts_matched_frozen_AR_whitener",
            "new_model_calls": 0, "new_api_calls": 0, "controls_used": False,
            "conditions": CONDITIONS, "parent_method": PARENT_METHOD, "n": 32,
            "configs": [asdict(c) for c in configs], "max_output_tokens": 256,
            "cell_ids": targets, "partial_grid": partial, "torch_threads": a.torch_threads,
            "shard_count": a.shard_count, "shard_index": a.shard_index,
            "max_resident_vector_shards": a.max_resident_vector_shards,
            "source_routing": routing, "runtime_sha256": sha(a.runtime),
            "whitener_directory": str(a.whitener_directory),
            "whitener_sources": {str(layer): {"path": str(a.whitener_directory / f"whitening_iolens_pooled_L{layer}.safetensors"),
                "sha256": sha(a.whitener_directory / f"whitening_iolens_pooled_L{layer}.safetensors")}
                for layer in sorted({cells[cid]["layer"] for cid in targets})},
            "code_sha256": {str(q): sha(q) for q in (Path(__file__),
                Path("src/olens_improve/target_only_search.py"), Path("src/olens_improve/reconstruction.py"),
                Path("src/olens_improve/selection.py"))}}
    a.output.mkdir(parents=True, exist_ok=True)
    if (a.output / "spec.json").exists() and json.loads((a.output / "spec.json").read_text()) != spec:
        raise ValueError("Resume search contract changed")
    atomic(a.output / "spec.json", spec)
    spec_sha = digest(spec)
    journal = a.output / "selections.jsonl"
    done = set()
    if journal.exists():
        with journal.open("rb+") as stream:
            last = 0
            while line := stream.readline():
                if not line.endswith(b"\n"):
                    stream.truncate(last)
                    break
                row = json.loads(line)
                if row["search_spec_sha256"] != spec_sha or row["cell_id"] in done or row["cell_id"] not in targets:
                    raise ValueError("Foreign or duplicate restart cell")
                done.add(row["cell_id"])
                last = stream.tell()
    whiteners = {}
    started = time.perf_counter()
    with journal.open("a") as out:
        for stage, stage_spec in routing["stages"].items():
            own = {cid for cid in targets if cid not in done and cells[cid]["split"] == stage}
            if not own:
                continue
            pools = defaultdict(dict)
            for source in stage_spec["samples"]:
                for envelope in committed_lines(verified(source)):
                    for row in envelope.get("records", [envelope]):
                        if row["cell_id"] in own:
                            pool = pools[row["cell_id"]]
                            if row["sample_index"] in pool:
                                raise ValueError("Duplicate sample record")
                            pool[row["sample_index"]] = row
            cache = RawVectorCache(stage_spec["vector_cache"], max_resident_shards=a.max_resident_vector_shards)
            if cache.contract != routing["vector_contract"]:
                raise ValueError("Frozen vector contract changed")
            seen = set()
            for parent_row in committed_lines(verified(stage_spec["selectors"])):
                cid = parent_row["cell_id"]
                if cid not in own:
                    continue
                if cid in seen:
                    raise ValueError("Duplicate cached plain parent cell")
                seen.add(cid)
                matches = [s for s in parent_row["selections"] if (s["method"], s["n"]) == (PARENT_METHOD, 32)]
                if len(matches) != 1:
                    raise ValueError("Missing/duplicate cached plain pooled N32 parent")
                # Do not carry alternative selectors or specificity metadata forward.
                parent = {k: matches[0][k] for k in ("text", "phrase_ids", "atoms", "bullet_count", "fits")}
                cell = cells[cid]
                for k in ("family", "item_id", "layer", "position", "split", "activation_sha256"):
                    if parent_row[k] != cell[k]:
                        raise ValueError("Parent cell provenance differs")
                t0 = time.perf_counter()
                layer = cell["layer"]
                if layer not in whiteners:
                    whiteners[layer] = Whitener.load(str(a.whitener_directory / f"whitening_iolens_pooled_L{layer}.safetensors"))
                w = whiteners[layer]
                if w.artifact_sha256 != pinned["whitener_moments_sha256"][str(layer)]:
                    raise ValueError("Frozen whitening moments changed")
                if w.artifact_sha256 != spec["whitener_sources"][str(layer)]["sha256"]:
                    raise ValueError("Frozen whitening moments changed after startup")
                prepared = prepare_target(pools.pop(cid), parent, cell, cache, tags, tokenizer, w)
                pool, mapped, target, vectors, atoms, sources, replay_fit, count = prepared
                preparation_seconds = time.perf_counter() - t0
                selections = evaluate_target(pool, mapped, target, vectors, count=count, cell_id=cid,
                    subset_fit_budget=a.subset_fit_budget, max_swap_steps=a.max_swap_steps, max_rounds=a.max_rounds)
                comparators = {c["method"]: c["actual_parent"] for c in inventory["conditions"]}
                for selection in selections:
                    selection["construction_parent_method"] = PARENT_METHOD
                    selection["component_comparator_condition"] = comparators[selection["method"]]
                selections.append({"method": PARENT_METHOD, "n": 32, "text": parent["text"],
                    "phrase_ids": [b.phrase_id for b in mapped], "token_count": count(parent["text"]),
                    "bullet_count": len(mapped), "fits": {"exact": asdict(replay_fit)},
                    "fits_scope": "emitted_bullets", "component_off_comparator": True})
                used_ids = {pid for s in selections for pid in s["phrase_ids"] + s.get("parent_phrase_ids", [])}
                event = {k: cell[k] for k in ("cell_id", "family", "item_id", "group_id", "layer", "position", "split", "activation_sha256")}
                event.update({"inventory_sha256": a.inventory_sha256, "search_spec_sha256": spec_sha,
                    "selections": selections, "atoms": [atoms[k] for k in sorted(used_ids)],
                    "source_samples": sources, "candidate_bullet_count": len(pool),
                    "cached_parent_source": {"path": stage_spec["selectors"]["path"], "sha256": stage_spec["selectors"]["sha256"],
                        "method": PARENT_METHOD, "n": 32, "original_phrase_ids": parent["phrase_ids"],
                        "source_exact_fve": parent["fits"]["exact"]["fve"], "replayed_exact_fve": replay_fit.fve,
                        "additional_parent_replay_fits": 1},
                    "whitener_sha256": w.artifact_sha256, "vector_contract_sha256": cache.contract["sha256"],
                    "preparation_seconds": preparation_seconds, "seconds": time.perf_counter() - t0})
                out.write(json.dumps(event, ensure_ascii=False) + "\n")
                out.flush()
                os.fsync(out.fileno())
                done.add(cid)
                atomic(a.output / "status.json", {"status": "running", "completed_cells": len(done),
                    "expected_cells": len(targets), "seconds": time.perf_counter() - started, "last_cell": cid})
                print(json.dumps({"completed_cells": len(done), "expected_cells": len(targets),
                                  "cell_seconds": event["seconds"], "preparation_seconds": preparation_seconds,
                                  "methods": [{"method": s["method"], "budget": s.get("budget"),
                                               "seconds": s.get("seconds"), "stop_flags": s.get("stop_flags")} for s in selections[:-1]]}), flush=True)
            if seen != own:
                raise ValueError("Incomplete cached plain parent cohort")
    if done != set(targets):
        raise ValueError("Incomplete target-local search")
    rows = list(committed_lines(journal))
    descriptors = []
    for family in routing["families"]:
        own = [r for r in rows if r["family"] == family]
        if not own:
            continue
        path = a.output / f"{family}.jsonl"
        temp = path.with_suffix(".jsonl.tmp")
        with temp.open("w") as stream:
            for row in sorted(own, key=lambda r: r["cell_id"]):
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(temp, path)
        manifest = a.output / f"{family}.manifest.json"
        atomic(manifest, {"schema_version": 1, "split": "expansion", "scope": routing["scope"],
                         "partial_grid": partial, "inventory_sha256": a.inventory_sha256,
                         "search_spec_sha256": spec_sha, "cells": [cells[r["cell_id"]] for r in own]})
        descriptor = {"ready": not partial, "partial_grid": partial, "family": family,
            "manifest": str(manifest.resolve()), "manifest_sha256": sha(manifest),
            "selections": str(path.resolve()), "selection_sha256": sha(path), "conditions": CONDITIONS,
            "inventory_sha256": a.inventory_sha256, "search_spec_sha256": spec_sha,
            "cells": len(own), "items": len({r["item_id"] for r in own}),
            "source_parents": [routing["stages"][s]["selectors"] for s in sorted({r["split"] for r in own})]}
        atomic(a.output / f"{family}.ready.json", descriptor)
        descriptors.append(descriptor)
    timing = {}
    for method in METHODS:
        selected = [next(s for s in r["selections"] if s["method"] == method) for r in rows]
        timing[method] = {"median_seconds": statistics.median(s["seconds"] for s in selected),
            "max_seconds": max(s["seconds"] for s in selected),
            "median_subset_fits": statistics.median(s["budget"]["subset_fits"] for s in selected),
            "budget_stops": sum(any("budget" in f for f in s["stop_flags"]) for s in selected)}
    atomic(a.output / "conditions.json", CONDITIONS)
    atomic(a.output / "status.json", {"status": "complete", "completed_cells": len(done),
        "expected_cells": len(targets), "partial_grid": partial, "inventory_sha256": a.inventory_sha256,
        "search_spec_sha256": spec_sha, "selection_sha256": sha(journal),
        "seconds": time.perf_counter() - started, "new_model_calls": 0, "new_api_calls": 0,
        "quality_status": "unjudged", "timing": timing, "family_descriptors": descriptors})


if __name__ == "__main__":
    main()
