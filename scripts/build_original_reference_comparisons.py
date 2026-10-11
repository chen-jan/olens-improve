"""Build additive post-hoc original-reference intervals from pinned judgments.

No inference, reconstruction, or change to the frozen analysis. The supplement
contains only full-bank paired pointwise intervals for seven fixed settings.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

# Keep this bounded task to one CPU, including numerical-library worker pools.
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from olens_improve.expanded_statistics import grouped_draws
from olens_improve.reporting import family_counts, original_grid_pairs

REPRESENTATIVES = {
    "selection": "best_n_exact-n32",
    "consensus": "consensus_semantic_v5_support0.125_compaton_vetoon-n16",
    "pruning": "prune_loo_a32_0.005-n32",
    "pooling": "pooled_greedy_swap-n32",
    "verification": "best_n_specificity_mean-n32",
    "editing": "editing_round2-n32",
    "combinations": "pooled_specificity_mean_then_prune_0.005-n32",
}
REFERENCE = "raw_n1-n1"
FAMILIES = ("hallucination", "multihop_mt", "chain_intermediates", "role_bound_association")
REPLICATES = 10000
SEED = 20261011


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(results_path, results_sha, review_path, review_sha, manifest_path, output):
    started, cpu_started = time.monotonic(), time.process_time()
    pins = {}

    def pinned(path, expected, *, lines=False):
        path = Path(path)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"Pinned source changed: {path}")
        key = str(path)
        if key in pins and pins[key] != expected:
            raise ValueError("Conflicting source pin")
        pins[key] = expected
        if lines:
            return [json.loads(line) for line in raw.splitlines() if line.strip()]
        return json.loads(raw)

    results = pinned(results_path, results_sha)
    review = pinned(review_path, review_sha)
    manifest_sha = results["manifest_sha256"]
    manifest = pinned(manifest_path, manifest_sha)
    if (results["status"] != "complete_exploratory"
            or review["status"] != "root_reviewed"
            or review["results_sha256"] != results_sha
            or review["manifest_sha256"] != manifest_sha):
        raise ValueError("Require exact complete native analysis and root review")
    full = results["cohorts"]["full"]
    if not full["comparison_family_complete"] or full["missing_comparisons"]:
        raise ValueError("Frozen source analysis is incomplete")
    for group, condition in REPRESENTATIVES.items():
        if review["method_findings"][group]["task_comparison"]["condition"] != condition:
            raise ValueError("Representative differs from fixed reviewed setting")
    analysis_path = ROOT / "configs/expansion_analysis_v1.json"
    analysis_pin = results["source_sha256"].get("configs/expansion_analysis_v1.json")
    if analysis_pin is None:
        analysis_pin = results["source_sha256"].get(str(analysis_path))
    analysis = pinned(analysis_path, analysis_pin)
    if analysis["bootstrap_replicates"] != REPLICATES or analysis["seed"] != SEED:
        raise ValueError("Bootstrap contract differs from frozen analysis")

    # Reused extraction and resampling functions must be the source versions
    # that generated the reviewed final native artifact.
    implementation = {str(Path(__file__).resolve()): digest(__file__)}
    for relative in ("src/olens_improve/reporting.py", "src/olens_improve/expanded_statistics.py"):
        path = ROOT / relative
        expected = results["implementation_sha256"][relative]
        if digest(path) != expected:
            raise ValueError(f"Original extraction implementation changed: {relative}")
        implementation[str(path)] = expected

    fresh = manifest["fresh_manifest"]
    capture = pinned(fresh["path"], fresh["sha256"])
    cells = capture["cells"]
    if len({c["cell_id"] for c in cells}) != len(cells):
        raise ValueError("Duplicate frozen cell identity")
    native = {(r["condition"], r["family"]): r for r in full["rows"]}
    if len(native) != len(full["rows"]):
        raise ValueError("Duplicate final native row")
    arms = [REFERENCE, *REPRESENTATIVES.values()]
    observations, absolute_rows = {}, []
    judgments = Path(results_path).resolve().parents[1] / "judgments"

    for family in FAMILIES:
        own = [c for c in cells if c["family"] == family]
        groups = {str(c["item_id"]): c["group_id"] for c in own}
        if len(set(groups.values())) != manifest["family_group_counts"][family]:
            raise ValueError("Frozen related groups differ from final contract")
        conditions = {}
        for condition in arms:
            root = judgments / condition
            result_path = root / family / "results.json"
            readouts_path = root / f"{family}.readouts.jsonl"
            result = pinned(result_path, results["source_sha256"][str(result_path)])
            readouts = pinned(readouts_path, results["source_sha256"][str(readouts_path)], lines=True)
            counts, coverage = family_counts(family, own, readouts, result)
            if coverage["missing_stage1"] or coverage["missing_stage2"]:
                raise ValueError("Judgments are incomplete, including hallucination stage two")
            endpoint = original_grid_pairs(family, counts, result)
            endpoint_name = ("original_grid_contradiction_rate" if family == "hallucination"
                             else "original_grid_item_pass_rate")
            pairs = endpoint[endpoint_name]
            if set(pairs) != set(groups):
                raise ValueError("Every arm must preserve the full identical question cohort")
            row = native[condition, family]
            metric = row["metric"]
            numerator, denominator = (sum(pair[i] for pair in pairs.values()) for i in (0, 1))
            value = numerator / denominator if denominator else None
            if (metric["name"] != endpoint_name or metric["numerator"] != numerator
                    or metric["denominator"] != denominator or metric["value"] != value
                    or metric["items"] != len(groups)
                    or metric["independent_groups"] != len(set(groups.values()))):
                raise ValueError("Rebuilt absolute endpoint differs from reviewed final row")
            conditions[condition] = pairs
            absolute_rows.append(row)
            del result, readouts, counts
        observations[family] = {"conditions": conditions, "group_of": groups}

    comparisons = []
    for family_index, family in enumerate(sorted(FAMILIES)):
        own = observations[family]
        draws = grouped_draws(own["conditions"], own["group_of"],
                              replicates=REPLICATES, seed=SEED + family_index)
        positions = {name: i for i, name in enumerate(draws["names"])}
        left = positions[REFERENCE]
        for condition in arms:
            column = positions[condition]
            metric = native[condition, family]["metric"]
            values = draws["rates"][:, column]
            values = values[np.isfinite(values)]
            rebuilt_ci = np.quantile(values, [.025, .975]).tolist() if len(values) else None
            if not np.allclose(draws["totals"][column], [metric["numerator"], metric["denominator"]], rtol=0, atol=0):
                raise ValueError("Bootstrap aggregation changed absolute counts")
            if rebuilt_ci is None or metric["ci95"] is None or not np.allclose(rebuilt_ci, metric["ci95"], rtol=0, atol=1e-12):
                raise ValueError("Shared whole-group draws do not reproduce final absolute intervals")
        for condition in REPRESENTATIVES.values():
            right = positions[condition]
            difference = draws["rates"][:, right] - draws["rates"][:, left]
            values = difference[np.isfinite(difference)]
            estimate = draws["point"][right] - draws["point"][left]
            standard_error = float(np.std(values, ddof=1)) if len(values) > 1 else None
            warnings = []
            if not np.isfinite(estimate):
                warnings.append("Undefined rate difference: zero original or selected total denominator")
            if len(values) != REPLICATES:
                warnings.append("Some paired ratio draws are undefined; pointwise interval uses only defined draws")
            if standard_error is None or standard_error <= 1e-14:
                warnings.append("Zero or unavailable bootstrap variation; no robust zero-uncertainty or equivalence claim")
            comparisons.append({
                "family": family, "condition": condition, "reference": REFERENCE,
                "role": "posthoc_original_reference", "scope": "original_grid",
                "delta": float(estimate) if np.isfinite(estimate) else None,
                "ci95_delta": np.quantile(values, [.025, .975]).tolist() if len(values) else None,
                "bootstrap_standard_error": standard_error,
                "defined_draws": int(len(values)), "bootstrap_replicates": REPLICATES,
                "items": draws["items"], "independent_groups": draws["groups"],
                "simultaneous_ci95_delta": None, "warnings": warnings,
                **({"warning": "; ".join(warnings)} if warnings else {}),
            })
    if len(comparisons) != 28 or len(absolute_rows) != 32:
        raise ValueError("Supplement must contain exactly 28 contrasts and 32 verified absolute rows")
    for path, expected in {**pins, **implementation}.items():
        if digest(path) != expected:
            raise ValueError("Source changed during supplement extraction")
    payload = {
        "schema_version": 1, "status": "posthoc_exploratory_pointwise_only",
        "created_utc": datetime.now(timezone.utc).isoformat(), "cohort": "full",
        "reference": REFERENCE, "results_sha256": results_sha,
        "root_review_sha256": review_sha, "manifest_sha256": manifest_sha,
        "bootstrap_replicates": REPLICATES, "seed": SEED,
        "family_seed_rule": "seed plus index of family in sorted four-task names",
        "method": "Paired whole-related-group bootstrap percentile 95 percent; shared draws within each task",
        "comparisons": comparisons, "absolute_rows": absolute_rows,
        "source_sha256": pins, "implementation_sha256": implementation,
        "limits": [
            "Post-hoc exploratory supplement requested after results were inspected; not a frozen headline analysis.",
            "Pointwise intervals only. No joint adjustment, p-values, significance classification, or new held-out evidence.",
            "Same whole related groups and 10000-draw seed contract as the final analysis; approximate bootstrap coverage.",
            "Transcript contradictions count wrong specific readouts divided by all specific readouts; retain specific-readout coverage.",
            "Recovery counts whole questions passing at any original reading site. The three recovery tasks measure different content.",
            "Original raw Oracle Lens is the first readout exactly as emitted; capped original deletes complete trailing bullets to meet the shared cap.",
            "Original raw reconstruction fit is unavailable. This supplement adds no reconstruction comparisons.",
            "Undefined or zero-variation intervals do not establish certainty or equivalence.",
        ],
        "execution": {"wall_seconds": time.monotonic() - started,
                      "cpu_seconds": time.process_time() - cpu_started,
                      "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "inference_calls": 0},
    }
    encoded = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    if len(encoded.encode()) > 100000:
        raise ValueError("Compact supplement exceeds the authorized 100KB bound")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        handle.write(encoded)
    return {"path": str(output), "sha256": digest(output), "bytes": output.stat().st_size,
            "comparisons": len(comparisons), "execution": payload["execution"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--results-sha256", required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--review-sha256", required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / "configs/expansion_manifest_v1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.results, args.results_sha256, args.review,
                           args.review_sha256, args.manifest, args.output)))


if __name__ == "__main__":
    main()
