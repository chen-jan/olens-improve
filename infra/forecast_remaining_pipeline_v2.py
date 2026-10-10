"""Operational forecast from timing artifacts and counts, never held-out text/quality."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Run inside an existing CPU allocation")
    if args.output.exists():
        raise FileExistsError("Preserve immutable earlier forecasts")
    fast = Path("${OLENS_COMPUTE_ROOT}")
    durable = Path("${OLENS_DATA_ROOT}")
    sources = []

    def read(path):
        raw = path.read_bytes()
        sources.append({"path": str(path), "sha256": sha256(raw).hexdigest(),
                        "bytes_read": len(raw)})
        return json.loads(raw)

    prior = read(durable / "diagnostics/remaining-pipeline-forecast-v1.json")
    partition_source = Path(__file__).resolve().parent.parent / "scripts/partition_ar.py"
    partition_raw = partition_source.read_bytes()
    sources.append({"path": str(partition_source), "sha256": sha256(partition_raw).hexdigest(),
                    "bytes_read": len(partition_raw), "use": "Implemented partition/catalog path; no execution in this forecast."})
    manifest = read(fast / "activations/core-v1/fresh_manifest_v2.json")
    split_names = {"dev": "development", "val": "validation", "test": "test"}
    counts = {split: Counter(c["family"] for c in manifest["cells"]
                             if c["split"] == source_name)
              for split, source_name in split_names.items()}
    assert sum(counts["dev"].values()) == 5236
    assert sum(counts["val"].values()) == 3485
    assert sum(counts["test"].values()) == 10714
    statuses = [read(durable / f"readouts/shared-global-v1/shard-{i:03d}-of-004.status.json")
                for i in range(4)]
    assert sum(s["expected_cells"] for s in statuses) == 3485
    assert all(s["target_n"] == 32 and s["status"] in ("running", "complete") for s in statuses)
    assert len({s["global_pool_id"] for s in statuses}) == 1
    operational = [{k: s.get(k) for k in ("job_id", "completed_cells", "expected_cells",
                                         "status", "updated_unix", "global_pool_id")}
                   for s in statuses]
    completed = sum(s["completed_cells"] for s in statuses)
    assert 0 <= completed <= 3485
    # Only the cost metadata is retained, never the DEV review's example text.
    baseline = read(durable / "diagnostics/costs-v2/baseline-review.json")["judge_cost"]
    baseline_seconds = (datetime.fromisoformat(baseline["last_settlement_utc"]) -
                        datetime.fromisoformat(baseline["first_request_utc"])).total_seconds()
    per_cell = prior["measured_generation_model_seconds_per_n32_cell"]
    ar_per_cell = (prior["measured_unique_ar_vectors_per_dev_cell"] /
                   prior["measured_final_ar_vectors_per_second"])
    stage_models = {}
    for split in ("val", "test"):
        cells = sum(counts[split].values())
        remaining = cells - completed if split == "val" else cells
        generation = remaining * per_cell / 4 / 3600
        ar = cells * ar_per_cell / 3600
        stage_models[split] = {
            "cells": cells, "remaining_sampling_cells": remaining,
            "remaining_generation_hours_four_main_gpus": generation,
            "ar_hours_one_gpu": ar,
            "conditional_generation_and_one_extra_ar_overlap_hours": max(generation, ar),
            "generation_then_one_ar_hours": generation + ar,
            "ar_hours_four_main_gpu_partitions_estimate": ar / 4,
            "generation_then_four_main_ar_partitions_hours": generation + ar / 4,
            "streaming_extra_ar_vs_four_way_bulk_ar_hours_saved_estimate":
                generation + ar / 4 - max(generation, ar),
            "full_40_arm_cpu_replay_hours_four_workers_four_threads_each":
                prior["projected_full_40_selector_arm_wall_hours_four_cpu_workers"] * cells / 14199,
            "e1_pruning_hours_one_four_thread_worker":
                prior["projected_e1_pruning_wall_hours_single_four_thread_worker"] * cells / 14199,
            "generation_gate": ("Blind VAL generation is active; its remaining count is observed."
                                if split == "val" else "TEST generation requires the final VAL decision and freeze."),
            "ar_selection_judgment_gate": ("Requires the DEV shortlist/settings freeze and VAL analysis authorization."
                                          if split == "val" else "Requires the final method/comparison/decision-rule freeze."),
        }

    request_counts = {}
    for split in ("val", "test"):
        request_counts[split] = {"hallucination": 2 * counts[split]["hallucination"],
                                "role_bound_association": counts[split]["role_bound_association"],
                                "chain_intermediates": counts[split]["chain_intermediates"],
                                "multihop_mt": 0}
    request_counts["val_plus_test"] = {f: request_counts["val"][f] + request_counts["test"][f]
                                        for f in request_counts["val"]}
    judge_scenarios = []
    for conditions in (8, 12):
        for slots, rpm in ((8, 200), (16, 400), (32, 600)):
            for novel_fraction in (1.0, 0.5):
                stages = {}
                for split, requests in request_counts.items():
                    family_hours = {f: n * conditions * novel_fraction / rpm / 60
                                    for f, n in requests.items()}
                    stages[split] = {"per_family_rate_floor_hours": family_hours,
                                     "critical_family_rate_floor_hours": max(family_hours.values()),
                                     "physical_requests_before_retries": sum(requests.values()) * conditions * novel_fraction}
                judge_scenarios.append({"conditions_per_stage": conditions,
                                        "slots_per_family": slots, "rpm_per_family": rpm,
                                        "assumed_novel_request_fraction": novel_fraction,
                                        "sum_of_separately_gated_val_and_test_rate_floor_hours":
                                            sum(stages[s]["critical_family_rate_floor_hours"]
                                                for s in ("val", "test")),
                                        "stages": stages})
    now = datetime.now(timezone.utc)
    deadline = datetime.fromisoformat("2026-10-10T21:25:36+00:00")
    result = {
        "checked_utc": now.isoformat(), "deadline_utc": deadline.isoformat(),
        "hours_until_deadline": (deadline - now).total_seconds() / 3600,
        "scope": "Conditional remaining VAL/TEST operations; counts and timing metadata only, no held-out outcomes.",
        "validation_operational_statuses": operational,
        "validation_complete_cells": completed, "validation_total_cells": 3485,
        "split_family_counts": {s: dict(c) for s, c in counts.items()},
        "stage_model_work": stage_models,
        "total_conditional_model_hours_with_one_extra_ar_per_authorized_stage":
            sum(s["conditional_generation_and_one_extra_ar_overlap_hours"] for s in stage_models.values()),
        "total_model_hours_generation_then_single_ar_each_stage":
            sum(s["generation_then_one_ar_hours"] for s in stage_models.values()),
        "total_model_hours_generation_then_four_way_ar_each_stage":
            sum(s["generation_then_four_main_ar_partitions_hours"] for s in stage_models.values()),
        "conditional_after_dev_freeze_if_val_generation_already_complete": {
            "val_four_way_ar_hours": stage_models["val"]["ar_hours_four_main_gpu_partitions_estimate"],
            "then_test_generation_and_streaming_extra_ar_model_hours":
                stage_models["val"]["ar_hours_four_main_gpu_partitions_estimate"] +
                stage_models["test"]["conditional_generation_and_one_extra_ar_overlap_hours"],
            "then_test_generation_and_four_way_bulk_ar_model_hours":
                stage_models["val"]["ar_hours_four_main_gpu_partitions_estimate"] +
                stage_models["test"]["generation_then_four_main_ar_partitions_hours"],
        },
        "cpu_resource_options_at_authorized_selector_stage": [
            "Reuse CPUs on four original GPU holds after their GPU tasks finish: one four-thread selector per hold, bounded to 20 GiB/worker and four physical cores, with affinity/headroom reverified before launch.",
            "Fresh judge CPU job 25474685 has eight physical cores: six are assigned to judge families and two remain; it cannot supply four simultaneous four-thread selectors.",
            "Original CPU job 25299630 remains memory-pressured and is excluded from new selector placement.",
            "If GPU holds remain busy, a separate gated normal CPU request of 16 physical cores and 80 GiB using verified ${SLURM_CPU_ACCOUNT}/${SLURM_CPU_PARTITION} is an option, not submitted or guaranteed immediately available.",
        ],
        "judge_max_requests_per_condition": request_counts,
        "judge_rate_floor_scenarios": judge_scenarios,
        "historical_stable_baseline": {
            "settled_requests": baseline["physical_attempts"], "wall_seconds": baseline_seconds,
            "aggregate_requests_per_second": baseline["physical_attempts"] / baseline_seconds,
            "limits": "Two DEV baseline conditions shared exact outputs. Aggregate rate does not transfer to imbalanced family queues or prove indexed recovery health."},
        "source_hashes": sources,
        "limits": [
            "No new GPU allocation or API call is requested by this artifact.",
            "The main four-GPU generation / one-extra-AR overlap is a conditional reference per stage, not a continuous run across the two scientific gates.",
            "AR cannot start on VAL before the DEV freeze. TEST model work cannot start before the VAL/final freeze. Waiting time is additional.",
            "AR input counts inherit DEV deduplication; sample lengths, effective input reuse and device throughput can change.",
            "Four-way AR scales measured single-GPU encoding by four using the implemented partition path; setup, load imbalance and catalog merge are additional. It does not assert bitwise equivalence across batch partitions.",
            "Model component timings exclude review pauses and some loading/setup. CPU projections require the stated disjoint allocated resources.",
            "Judge figures are optimistic sustained-rate floors, not completion guarantees. Actual throughput is at most min(RPM/60, slots/mean response latency).",
            "Each family has its own queue/rate limit; spare role or chain capacity is not automatically available to hallucination.",
            "The 50% novel-request scenario is illustrative, not measured on sealed held-out outputs. Hall stage 2 exclusions and exact-text sharing reduce counts; retries add requests.",
            "Conditions are assumed to number 8 or 12 in BOTH stages. Fewer final TEST conditions reduce that stage proportionally.",
            "Current DEV judging/recovery, frozen shortlist choice and human review are additional; the final end-to-end deadline remains conditional.",
            "No costs or recovery metrics from VAL/TEST were inspected. No held-out candidate text is retained in this artifact.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "validation_complete_cells": completed,
                      "hours_until_deadline": result["hours_until_deadline"],
                      "stage_model_work": stage_models,
                      "judge_max_requests_per_condition": request_counts}, indent=2))


if __name__ == "__main__":
    main()
