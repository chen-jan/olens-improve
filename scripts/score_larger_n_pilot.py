"""Additive, resumable AR scoring of a frozen 32-cell larger-N diagnostic.

Only complete authorized N64/N128/N256 snapshots are accepted. Historical caches and
selectors remain read-only; this runner extends the existing complete-sample
selector locally, preserving its parser, admissibility and earliest-tie rules.
"""
import argparse
from collections import Counter, OrderedDict
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from olens_improve.ar_cache import committed_prefix, digest, input_records, vector_key
from olens_improve.models import BASE_REVISION, PAIR_REVISION
from olens_improve.reconstruction import FrozenAR, JointNNLS, RawVectorCache, Whitener, ar_token_ids
from olens_improve.selection import PARSER_POLICY, Selection, best_of_n, output_admissible, parse_bullets

PREFIXES = (1, 2, 4, 8, 16, 32, 64, 128, 256)
FAMILIES = {"hallucination", "multihop_mt", "chain_intermediates", "role_bound_association"}
MAX_CACHE_BYTES = 1_000_000_000


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def append_event(stream, value):
    stream.write(json.dumps(value, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def extended_best(samples, n, score, admissible):
    """The frozen selector's exact loop, with only its N32 ceiling extended."""
    available = len(samples)
    if available not in (64, 128, 256) or n not in PREFIXES or n > available or {s.index for s in samples} != set(range(available)):
        raise ValueError("Require all distinct available sample indexes and an available frozen prefix")
    if len({s.sample_id for s in samples}) != available:
        raise ValueError("Duplicate sample IDs/indexes")
    winner, best, trace = None, -math.inf, []
    for sample in sorted(samples, key=lambda s: s.index)[:n]:
        if sample.parsing_uncertain or len(sample.bullets) > 4 or not admissible(sample.bullets):
            trace.append({"sample_id": sample.sample_id, "skipped": "uncertain_or_inadmissible"})
            continue
        value = float(score(tuple(b.phrase_id for b in sample.bullets)))
        if not math.isfinite(value):
            raise ValueError("Nonfinite complete-sample FVE")
        trace.append({"sample_id": sample.sample_id, "score": value})
        if winner is None or value > best:
            winner, best = sample, value
    if winner is None:
        return Selection("best_of_n", (), None, tuple(trace), "no_eligible_complete_sample")
    return Selection("best_of_n", winner.bullets, best, tuple(trace))


def load_inputs(manifest, samples_path, prefix=256):
    if prefix not in (64, 128, 256):
        raise ValueError("Authorized snapshot prefixes are 64, 128 and 256")
    if manifest.get("schema_version") != "larger_n_sampling_pilot_v1":
        raise ValueError("Require the frozen larger-N sampling manifest schema")
    cells = manifest["cells"]
    if isinstance(cells, dict):
        cells = list(cells.values())
    if len(cells) != 32 or len({c["cell_id"] for c in cells}) != 32:
        raise ValueError("This authorization covers exactly 32 distinct activation cells")
    if Counter(c["family"] for c in cells) != Counter({f: 8 for f in FAMILIES}):
        raise ValueError("Require eight cells from each frozen family")
    by_id = {c["cell_id"]: c for c in cells}
    body = samples_path.read_bytes()
    if body != committed_prefix(body):
        raise ValueError("Generation snapshot has an uncommitted tail")
    rows = {cid: {} for cid in by_id}
    for row in input_records(body):
        cid, index = row["cell_id"], row["sample_index"]
        if cid not in by_id or type(index) is not int or not 0 <= index < prefix:
            raise ValueError("Sample outside authorized cells/prefix")
        if index in rows[cid]:
            raise ValueError("Duplicate candidate sample")
        cell = by_id[cid]
        for field in ("family", "item_id", "layer", "position", "activation_sha256"):
            if row[field] != cell[field]:
                raise ValueError(f"Candidate target identity changed: {field}")
        if row.get("base_revision") != BASE_REVISION or row.get("adapter_revision") != PAIR_REVISION:
            raise ValueError("Candidate model revision differs")
        rows[cid][index] = row
    for cid, cell in by_id.items():
        if set(rows[cid]) != set(range(prefix)):
            raise ValueError("Scoring waits for every complete cell at the requested prefix")
        baseline = cell["baseline_samples"]
        baseline_sha = hashlib.sha256(json.dumps(baseline, sort_keys=True, separators=(",", ":"),
                                                  ensure_ascii=False).encode()).hexdigest()
        if baseline_sha != cell["baseline_samples_sha256"]:
            raise ValueError("Historical baseline sample checksum changed")
        if len(baseline) != 32 or any(rows[cid][i] != baseline[i] for i in range(32)):
            raise ValueError("Historical first 32 samples were modified or reordered")
    return by_id, rows


def verify_contract(cache, checkpoint):
    contract = cache.contract
    if digest({k: v for k, v in contract.items() if k != "sha256"}) != contract["sha256"]:
        raise ValueError("Historical AR contract digest differs")
    for field, name in (("head_sha256", "heads.pt"), ("meta_sha256", "meta.json"),
                        ("adapter_sha256", "lora/adapter_model.safetensors"),
                        ("adapter_config_sha256", "lora/adapter_config.json")):
        if contract[field] != sha(checkpoint / name):
            raise ValueError(f"Frozen checkpoint differs: {name}")
    expected = {"base_revision": BASE_REVISION, "pair_revision": PAIR_REVISION,
                "tokenizer_revision": BASE_REVISION,
                "span_limit": 32, "padding": "right_zero", "final_norm": "Identity",
                "backbone_dtype": "bfloat16", "head_dtype": "float32",
                "head_layer_norm_epsilon": 1e-5,
                "tokenizer_cleanup": "source_scaffolding_and_special_ids_v1",
                "key_policy": "effective_scored_tokens_and_tag_v1"}
    if any(contract.get(k) != v for k, v in expected.items()):
        raise ValueError("Historical AR preprocessing differs")


def prepare_samples(cells, records, tok, contract, tags, prefix=256):
    count = lambda text: len(tok(text, add_special_tokens=False)["input_ids"])
    prepared, atoms, pending = {}, {}, OrderedDict()
    for cid, cell in cells.items():
        prepared[cid], atoms[cid] = [], {}
        for index in range(prefix):
            row = records[cid][index]
            sample_id = f"{row.get('global_pool_id') or row['pool_id']}:{cid}:{index}"
            sample = parse_bullets(row["text"], sample_id, index, token_count=count, max_output_tokens=256)
            prepared[cid].append(sample)
            for b in sample.bullets:
                clean, full_ids = ar_token_ids(tok, b.text)
                ids = full_ids[:32]
                key = vector_key(contract["sha256"], tags[cell["layer"]], ids) if ids else None
                atoms[cid][b.phrase_id] = {"phrase_id": b.phrase_id, "text": b.text,
                    "sample_id": sample_id, "sample_index": index, "position": b.position,
                    "span_start": b.start, "span_end": b.end, "cache_key": key,
                    "scored_text": clean, "scored_token_ids": ids, "original_token_count": len(full_ids),
                    "unscored_suffix_ids": full_ids[32:], "truncated": len(full_ids) > 32,
                    "parser_flags": list(sample.flags), "parser_policy": PARSER_POLICY,
                    "status": "encoded_or_cache_hit" if key else "empty_after_cleanup"}
                if key:
                    pending.setdefault(key, {"text": b.text, "layer": cell["layer"],
                                            "scored_token_ids": ids, "tag_ids": tags[cell["layer"]]})
    return prepared, atoms, pending, count


def encode_missing(args, old, pending, spec_sha, stop):
    """Each fsynced batch event commits one immutable tensor/index pair."""
    import torch
    from safetensors.torch import save_file
    directory = args.output / "ar-cache"
    directory.mkdir(exist_ok=True)
    contract_path = directory / "contract.json"
    if contract_path.exists() and json.loads(contract_path.read_text()) != old.contract:
        raise ValueError("Pilot cache contract changed")
    atomic(contract_path, old.contract)
    journal = directory / "batches.jsonl"
    committed, stored_bytes = set(), 0
    if journal.exists():
        body = committed_prefix(journal.read_bytes())
        # Only the uncommitted crash tail of our own journal may be discarded.
        if len(body) != journal.stat().st_size:
            tail = journal.read_bytes()[len(body):]
            (directory / ("uncommitted-tail-" + hashlib.sha256(tail).hexdigest()[:16] + ".bin")).write_bytes(tail)
            with journal.open("r+b") as stream:
                stream.truncate(len(body))
        for line in body.splitlines():
            event = json.loads(line)
            if event["spec_sha256"] != spec_sha:
                raise ValueError("Pilot cache journal belongs to another run")
            for name in ("tensor", "index"):
                if sha(directory / event[name]) != event[name + "_sha256"]:
                    raise ValueError("Committed pilot AR cache changed")
            info = json.loads((directory / event["index"]).read_text())
            keys = [v["cache_key"] for v in info["vectors"]]
            if committed.intersection(keys):
                raise ValueError("Duplicate committed cache key")
            committed.update(keys)
            stored_bytes += event["tensor_bytes"]
    wanted = [(k, v) for k, v in pending.items() if k not in old.index and k not in committed]
    if stored_bytes + len(wanted) * 5120 * 4 + len(wanted) * 256 > MAX_CACHE_BYTES:
        raise ValueError("Pilot raw-vector cache would exceed 1GB")
    ar = None
    with journal.open("a") as stream:
        for lo in range(0, len(wanted), args.batch_size):
            if stop[0]:
                return False
            if ar is None:
                ar = FrozenAR.load(args.base_snapshot, str(args.checkpoint))
            batch = wanted[lo:lo + args.batch_size]
            started = time.monotonic()
            vectors, enc = ar.encode_mixed([v["text"] for _, v in batch], [v["layer"] for _, v in batch])
            for (_, wanted_row), actual in zip(batch, enc):
                if wanted_row["scored_token_ids"] != actual["input_ids"] or wanted_row["tag_ids"] != actual["tag_ids"]:
                    raise ValueError("Actual AR encoding differs from normalized first-32-token cache key")
            if vectors.shape != (len(batch), 5120) or not torch.isfinite(vectors).all():
                raise ValueError("Invalid AR predictions")
            ident = digest([k for k, _ in batch])[:20]
            tensor, index = directory / f"raw_{ident}.safetensors", directory / f"raw_{ident}.index.json"
            temporary = tensor.with_suffix(".tmp")
            save_file({"vectors": vectors.contiguous()}, str(temporary), metadata={"contract_sha256": old.contract["sha256"]})
            with temporary.open("rb") as tensor_stream:
                os.fsync(tensor_stream.fileno())
            os.replace(temporary, tensor)
            entries = [{"cache_key": k, "row": i, "layer": v["layer"], "tag_ids": v["tag_ids"],
                        "scored_token_ids": v["scored_token_ids"]} for i, (k, v) in enumerate(batch)]
            atomic(index, {"contract_sha256": old.contract["sha256"], "tensor_path": str(tensor.resolve()), "vectors": entries})
            append_event(stream, {"spec_sha256": spec_sha, "tensor": tensor.name, "index": index.name,
                "tensor_sha256": sha(tensor), "index_sha256": sha(index), "tensor_bytes": tensor.stat().st_size,
                "new_unique_vectors": len(batch), "seconds": time.monotonic() - started,
                "slurm_job_id": os.environ["SLURM_JOB_ID"]})
            print(json.dumps({"phase": "AR", "completed_new_vectors": lo + len(batch), "pending_new_vectors": len(wanted)}), flush=True)
    del ar
    torch.cuda.empty_cache()
    return True


def historical_comparison(cell, selected):
    historical = cell.get("baseline_selection") or cell.get("baseline_best_n32")
    if historical is None:
        return {"status": "historical_selection_not_provided", "stock_selector_identity_checked": True}
    result = {"status": "match", "stock_selector_identity_checked": True,
              "text_equal": historical["text"] == selected.text,
              "phrase_ids_equal": historical.get("phrase_ids") == list(selected.phrase_ids)}
    fit = historical.get("fits", {}).get("exact", {})
    old_score = fit.get("fve", historical.get("score"))
    result["historical_fve"] = old_score
    result["replayed_fve"] = selected.score
    result["fve_delta"] = selected.score - old_score if old_score is not None and selected.score is not None else None
    if not result["text_equal"] or not result["phrase_ids_equal"] or (result["fve_delta"] is not None and abs(result["fve_delta"]) > 1e-5):
        result["status"] = "difference_requires_review"
    return result


def score_cells(args, cells, records, samples, atoms, count, old, spec_sha, stop):
    import torch
    from safetensors import safe_open
    new = RawVectorCache(str(args.output / "ar-cache"))
    result_dir = args.output / "cells"
    result_dir.mkdir(exist_ok=True)
    whitener = None
    current_layer = None
    all_rows = []
    for cid in sorted(cells, key=lambda k: (cells[k]["layer"], k)):
        path = result_dir / (hashlib.sha256(cid.encode()).hexdigest()[:24] + ".json")
        if path.exists():
            event = json.loads(path.read_text())
            if event["spec_sha256"] != spec_sha or event["cell_id"] != cid:
                raise ValueError("Completed scoring cell identity changed")
            all_rows.append(event)
            continue
        if stop[0]:
            return None
        started = time.monotonic()
        cell = cells[cid]
        layer = cell["layer"]
        if current_layer != layer:
            whitener = Whitener.load(str(args.whitener_directory / f"whitening_iolens_pooled_L{layer}.safetensors"))
            current_layer = layer
        with safe_open(cell["activation_tensor_path"], framework="pt", device="cpu") as source:
            target = source.get_slice("resid")[cell["activation_row"]:cell["activation_row"] + 1][0]
        if hashlib.sha256(target.numpy().tobytes()).hexdigest() != cell["activation_sha256"]:
            raise ValueError("Frozen target activation changed")
        keys = sorted({a["cache_key"] for a in atoms[cid].values() if a["cache_key"]})
        raw = torch.stack([old.get(k) if k in old.index else new.get(k) for k in keys])
        transformed = whitener.whiten(raw)
        transformed = transformed / (transformed.norm(dim=1, keepdim=True) + 1e-9)
        by_key = dict(zip(keys, transformed))
        vectors = {pid: by_key[a["cache_key"]] for pid, a in atoms[cid].items() if a["cache_key"]}
        scorer = JointNNLS(whitener.whiten(target.reshape(1, -1))[0], vectors)
        admissible = output_admissible(count, 256)
        eligible = lambda bs: admissible(bs) and all(b.phrase_id in vectors for b in bs)
        results = []
        baseline = None
        for n in (n for n in PREFIXES if n <= getattr(args, "prefix", 256)):
            selected = extended_best(samples[cid], n, scorer.score, eligible)
            if n <= 32 and selected != best_of_n(samples[cid], n, scorer.score, admissible=eligible):
                raise ValueError("Pilot selection disagrees with frozen selector")
            if n == 32:
                baseline = selected
            chosen_index = next((s.index for s in samples[cid] if s.bullets == selected.bullets), None) if selected.score is not None else None
            fit = scorer.fit(selected.phrase_ids)
            results.append({"method": "best_n_exact", "n": n, "text": selected.text,
                "phrase_ids": list(selected.phrase_ids), "sample_index": chosen_index,
                "source_text": records[cid][chosen_index]["text"] if chosen_index is not None else None,
                "token_count": count(selected.text), "bullet_count": len(selected.bullets),
                "reason": selected.reason, "fits": {"exact": asdict(fit)}, "fits_scope": "emitted_bullets",
                "atoms": [atoms[cid][pid] for pid in selected.phrase_ids], "trace": list(selected.trace)})
        candidate_fits = []
        for sample in samples[cid]:
            allowed = not sample.parsing_uncertain and eligible(sample.bullets)
            candidate_fits.append({"sample_index": sample.index, "sample_id": sample.sample_id,
                "eligible": allowed, "parser_flags": list(sample.flags),
                "invalid_ar_phrase_ids": [b.phrase_id for b in sample.bullets if b.phrase_id not in vectors],
                "fit": asdict(scorer.fit(tuple(b.phrase_id for b in sample.bullets))) if allowed else None})
        event = {"cell_id": cid, "family": cell["family"], "item_id": cell["item_id"],
            "split": cell.get("split", "diagnostic"), "layer": layer, "position": cell["position"],
            "activation_sha256": cell["activation_sha256"], "spec_sha256": spec_sha,
            "scope": "32-cell descriptive diagnostic; not official whole-question evaluation",
            "whitener_sha256": whitener.artifact_sha256, "results": results,
            "candidate_fits": candidate_fits, "baseline_n32_audit": historical_comparison(cell, baseline),
            "seconds": time.monotonic() - started}
        atomic(path, event)
        all_rows.append(event)
        print(json.dumps({"phase": "selection", "complete_cells": len(all_rows), "expected_cells": 32}), flush=True)
    return sorted(all_rows, key=lambda r: r["cell_id"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "samples", "output", "production-cache", "checkpoint", "whitener-directory"):
        p.add_argument("--" + name, required=True, type=Path)
    p.add_argument("--runtime", default="configs/runtime.json", type=Path)
    p.add_argument("--allowed-job-id", action="append", required=True)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--prefix", type=int, choices=(64, 128, 256), default=256)
    a = p.parse_args()
    if os.environ.get("SLURM_JOB_ID") not in a.allowed_job_id:
        raise RuntimeError("Scoring requires its explicitly allowlisted Slurm allocation")
    if not 1 <= a.batch_size <= 128:
        raise ValueError("AR batch size must be between 1 and 128")
    import torch
    from transformers import AutoTokenizer
    torch.set_num_threads(min(4, int(os.environ.get("SLURM_CPUS_PER_TASK", "4"))))
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    manifest = json.loads(a.manifest.read_text())
    ready_path = a.samples.with_suffix(".ready.json")
    ready = json.loads(ready_path.read_text())
    if ready.get("manifest_sha256") != sha(a.manifest) or ready.get("samples_sha256") != sha(a.samples) or ready.get("n") != a.prefix:
        raise ValueError("Requested generation prefix receipt differs from its frozen inputs")
    cells, records = load_inputs(manifest, a.samples, a.prefix)
    runtime_base = json.loads(a.runtime.read_text())["paths"]["base_snapshot"]
    a.base_snapshot = manifest["base_snapshot"]
    if Path(a.base_snapshot).resolve() != Path(runtime_base).resolve():
        raise ValueError("Runtime and frozen sampling manifest use different base weights")
    old = RawVectorCache(str(a.production_cache))
    verify_contract(old, a.checkpoint)
    state = torch.load(a.checkpoint / "heads.pt", map_location="cpu", weights_only=True)
    tags = {int(layer): state["tag_ids"][i].tolist() for i, layer in enumerate(state["layers"])}
    if any(c["layer"] not in tags or c["layer"] not in range(20, 61, 4) for c in cells.values()):
        raise ValueError("Unsupported pilot layer")
    tok = AutoTokenizer.from_pretrained(a.base_snapshot, local_files_only=True)
    samples, atoms, pending, count = prepare_samples(cells, records, tok, old.contract, tags, a.prefix)
    source_paths = [a.manifest, a.samples, a.production_cache / "contract.json"]
    whitener_paths = [a.whitener_directory / f"whitening_iolens_pooled_L{l}.safetensors" for l in sorted({c["layer"] for c in cells.values()})]
    spec = {"schema_version": 1, "scope": "32-cell larger-N pilot; descriptive diagnostic only",
        "cell_ids": sorted(cells), "prefixes": [n for n in PREFIXES if n <= a.prefix],
        "loaded_complete_prefix": a.prefix, "parser_policy": PARSER_POLICY,
        "max_bullets": 4, "max_output_qwen_tokens": 256, "AR_span_limit": 32,
        "AR_cleanup": "source_scaffolding_and_special_ids_v1", "vector_contract": old.contract,
        "solver": "scipy_exact", "ridge_c": .1, "center_predictions": True,
        "unit_phrase_directions": True, "tie_rule": "strictly_greater_FVE_else_earliest_sample",
        "batch_size": a.batch_size, "max_cache_bytes": MAX_CACHE_BYTES,
        "source_sha256": {str(path.resolve()): sha(path) for path in source_paths + whitener_paths},
        "code_sha256": {str(path): sha(path) for path in (Path(__file__),
            Path("src/olens_improve/reconstruction.py"), Path("src/olens_improve/selection.py"))},
        "generation_complete_before_AR_model_load": True}
    a.output.mkdir(parents=True, exist_ok=True)
    if a.output.resolve() == a.production_cache.resolve() or a.production_cache.resolve() in a.output.resolve().parents:
        raise ValueError("Pilot output must not modify a historical cache")
    with (a.output / "writer.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        spec_path = a.output / "spec.json"
        if spec_path.exists() and json.loads(spec_path.read_text()) != spec:
            raise ValueError("Pilot resume contract changed")
        atomic(spec_path, spec)
        stop = [False]
        def interrupted(signum, frame):
            stop[0] = True
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        spec_sha = digest(spec)
        if not encode_missing(a, old, pending, spec_sha, stop):
            atomic(a.output / "status.json", {"status": "paused", "phase": "AR", "spec_sha256": spec_sha})
            return
        rows = score_cells(a, cells, records, samples, atoms, count, old, spec_sha, stop)
        if rows is None:
            atomic(a.output / "status.json", {"status": "paused", "phase": "selection", "spec_sha256": spec_sha})
            return
        path = a.output / "selections.jsonl"
        temp = path.with_suffix(".tmp")
        temp.write_text("".join(json.dumps(r, allow_nan=False) + "\n" for r in rows))
        os.replace(temp, path)
        means = {str(n): statistics.mean(r["results"][PREFIXES.index(n)]["fits"]["exact"]["fve"] for r in rows)
                 for n in PREFIXES if n <= a.prefix}
        summary = {"status": "complete", "spec_sha256": spec_sha, "scope": spec["scope"], "cells": len(rows),
            "mean_FVE_by_N": means, "mean_FVE_gain_over_N32": {n: value - means["32"] for n, value in means.items()},
            "historical_n32_audit_counts": dict(Counter(r["baseline_n32_audit"]["status"] for r in rows)),
            "selections_path": str(path), "selections_sha256": sha(path),
            "new_unique_vectors": len(RawVectorCache(str(a.output / "ar-cache")).index),
            "existing_unique_vectors_reused": sum(k in old.index for k in pending),
            "official_whole_question_evaluation": False}
        atomic(a.output / "summary.json", summary)
        atomic(a.output / "status.json", summary)
        print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
