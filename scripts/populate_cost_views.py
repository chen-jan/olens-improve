"""Attach source-bound pilot budget plots and paired component ablations.

Uses completed compact measurement summaries only. Never reads held-out text,
dispatches inference, or treats cached replay as complete deployment latency.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path


PRIMARY = {
    "capped_n1-n1", "random_complete-n16", "random_complete-n32",
    "pooled_greedy_swap-n16", "pooled_greedy_swap-n32", "prune_loo_a32_0.005-n32",
    "best_n_specificity_mean-n32",
    "best_n_specificity_mean_then_prune_0.005-n32",
    "best_n_specificity_mean_random_delete_matched_0.005-n32",
    "consensus_exact_support0-n16",
    "consensus_semantic_v5_support0_compatoff_vetoon-n16",
    "consensus_semantic_v5_medium_support0_compatoff_vetoon-n16",
    "editing_round2-n32", "likelihood_true_minus_mean_two_controls-n8",
} | {f"best_n_exact-n{n}" for n in (1, 2, 4, 8, 16, 32)}
FAMILIES = ("hallucination", "multihop_mt", "chain_intermediates", "role_bound_association")
ABLATIONS = {
    "pruning": [("prune_loo_a32_0.005-n32", "best_n_exact-n32")],
    "pooling": [("pooled_greedy_swap-n32", "best_n_exact-n32")],
    "consensus": [("consensus_semantic_v5_medium_support0_compatoff_vetoon-n16", "best_n_exact-n16"),
                  ("consensus_semantic_v5_support0_compatoff_vetoon-n16", "best_n_exact-n16")],
    "editing": [("editing_round2-n32", "best_n_exact-n32")],
}


def populate(report, measurements, costs, source_hashes, specificity=None):
    if report["provenance"]["cohort_manifest_sha256"] != measurements["manifest_sha256"]:
        raise ValueError("Cost views require the exact quality cohort hash")
    if measurements.get("original_grid_contract"):
        raise ValueError("This population contract is the completed partial-grid DEV pilot only")
    arms = {a["condition"]: a for a in measurements["conditions"]}
    if len(arms) != len(measurements["conditions"]):
        raise ValueError("Duplicate condition identity")
    wanted = PRIMARY | {x for pairs in ABLATIONS.values() for pair in pairs for x in pair}
    for condition in wanted:
        arm = arms[condition]
        if not arm["measurement_complete"] or arm.get("errors"):
            raise ValueError(f"Incomplete source condition: {condition}")
        if set(arm["families"]) != set(FAMILIES):
            raise ValueError("Missing family coverage")
        if any(f["missing_stage1"] or f["missing_stage2"] for f in arm["families"].values()):
            raise ValueError("Missing stage coverage cannot become a complete budget point")
    cohort = "Shared DEV pilot: 31 items / 189 cells; partial-grid cell endpoints; whole-group 95% intervals"
    generation32 = costs["deployment"]["sampling_n32_gpu_seconds_per_cell"]
    cpu_keys = {"best_n_exact-n8": "A8", "best_n_exact-n16": "A16", "best_n_exact-n32": "A32",
                "prune_loo_a32_0.005-n32": "C32", "pooled_greedy_swap-n32": "D32",
                "best_n_specificity_mean-n32": "E1_mean32"}
    helpers = costs["campaign"]["helper_b_repaired_none_medium"]

    def components(condition, n):
        random = condition.startswith("random_complete-")
        calls = 0.0
        usd = 0.0
        if condition.startswith("consensus_semantic_v5_medium_"):
            calls = (helpers["proposal"]["calls"] + helpers["medium_confirmation"]["settled_physical_responses"]) / 189
            usd = helpers["medium_pipeline_usd"] / 189
        elif condition.startswith("consensus_semantic_v5_"):
            calls = helpers["none_pipeline_calls"] / 189
            usd = helpers["none_pipeline_usd"] / 189
        elif condition.startswith("editing_round2-"):
            stages = [s for s in costs["campaign"]["helpers"] if "helper-edit-pilot-v1" in s["stage"]]
            assert len(stages) == 2
            calls = sum(s["requests"] for s in stages) / 189
            usd = sum(s["actual_usd"] for s in stages) / 189
        key = cpu_keys.get(condition)
        return {
            "required_olens_samples_for_fresh_baseline": None if random else n,
            "retained_samples_for_random_baseline": 1 if random else None,
            "cached_selector_wall_seconds": costs["incremental_cache"][key]["median_seconds_per_cell"] if key else None,
            "cached_timer_cohort": "Eight fixed DEV cells, three repetitions, four CPU threads; preparation excluded",
            "recurring_helper_calls_per_cell": calls, "recurring_helper_usd_per_cell": usd,
            "helper_cost_scope": "Measured physical calls including retries; proposal + confirmation or both edit rounds; benchmark judging excluded",
            "generation_component_gpu_seconds": None if random else generation32 * n / 32,
            "generation_component_measurement": ("Not measured: one retained admissible sample; generation may retry for eligibility"
                if random else "Pilot filled-batch N32 component; other N are proportional estimates; capture/setup/AR or likelihood/local/helper work excluded"),
            "control_note": ("Same-pool random draw among admissible samples from this recorded prefix. Fresh deployment retains one sample; matching eligibility may require rejection/resampling. Exact finite-pool replay uses the recorded prefix; no guaranteed N1 generation cost is claimed."
                             if random else "Frozen condition candidate prefix; helper proposals are additional computation, not extra O-lens samples."),
        }

    series = []
    for family in FAMILIES:
        endpoint = "contradiction_rate" if family == "hallucination" else "cell_recovery"
        points = []
        for condition in sorted(PRIMARY, key=lambda c: (arms[c]["n"], c)):
            arm = arms[condition]
            m = arm["families"][family]["metrics"][endpoint]
            point = {"condition": condition, "cost": arm["n"], "value": m["value"],
                     "ci": m["ci95"], "count": m["denominator"], "numerator": m["numerator"],
                     "family": family, "cohort_manifest_sha256": measurements["manifest_sha256"],
                     "condition_source_manifest_sha256": sha256(json.dumps(arm["source_sha256"], sort_keys=True).encode()).hexdigest(),
                     **components(condition, arm["n"])}
            if family == "hallucination":
                metrics = arm["families"][family]["metrics"]
                point["assertion_share"] = metrics["assertion_share"]["value"]
                point["off_topic_share_of_specific"] = metrics["off_topic_rate"]["value"]
            points.append(point)
        series.append({"label": family + (": Contradictions / specific readouts (lower is better)" if family == "hallucination" else ": Mention/role recovery (higher is better)"),
                       "family": family, "cohort": cohort, "value_unit": "proportion", "cost_unit": "samples", "cost_scope": "experimental_prefix",
                       "cost_definition": "Experimental O-lens candidate prefix per cell, not total deployment cost. Random controls retain one admissible sample; generation may retry for eligibility. Recurring helpers and cached replay components appear separately below.",
                       "points": points})
    report["methods"]["sample_selection"]["cost_frontier"] = series
    paired = {(r["condition"], r["baseline_condition"], r["family"], r["endpoint"]): r
              for r in measurements["paired_comparisons"]}
    for tab, comparisons in ABLATIONS.items():
        charts = []
        for family in FAMILIES:
            endpoint = "contradiction_rate" if family == "hallucination" else "cell_recovery"
            points = []
            for proposed, parent in comparisons:
                row = paired[(proposed, parent, family, endpoint)]
                points.append({"condition": proposed + " vs " + parent, "value": row["delta"],
                               "ci": row["ci95_delta"], "groups": row["independent_groups"],
                               "warning": row["warning"], "source_conditions": [proposed, parent],
                               "cohort_manifest_sha256": measurements["manifest_sha256"]})
            charts.append({"family": family, "label": family + (": Paired contradiction-rate change (lower is better)" if family == "hallucination" else ": Paired recovery change (higher is better)"),
                           "cohort": cohort, "points": points})
        report["methods"][tab]["component_ablations"] = charts
    if specificity is not None:
        if specificity['manifest_sha256'] != measurements['manifest_sha256']:
            raise ValueError('Additional component artifact cohort hash mismatch')
        comparisons = [
            'pooled_specificity_mean vs pooled_greedy_swap',
            'pooled_specificity_mean_then_prune_0.005 vs pooled_specificity_mean',
            'pooled_specificity_mean_then_prune_0.005 vs pooled_specificity_mean_random_delete_matched_0.005',
        ]
        charts = []
        for family in FAMILIES:
            points = []
            for comparison in comparisons:
                row = specificity['paired_comparisons'][comparison][family]
                proposed, parent = comparison.split(' vs ')
                # Bind the additional paired endpoint to the exact completed arms.
                endpoint = 'contradiction_rate' if family == 'hallucination' else 'cell_recovery'
                for key, condition in (('proposed', proposed), ('baseline', parent)):
                    arm = arms[condition+'-n32']
                    if not arm['measurement_complete']:
                        raise ValueError('Incomplete component artifact source')
                    expected = arm['families'][family]['metrics'][endpoint]['value']
                    if abs(expected-row[key]) > 1e-12:
                        raise ValueError('Component artifact endpoint does not match authoritative summary')
                points.append({'condition': proposed+'-n32 vs '+parent+'-n32', 'value': row['delta'],
                               'ci': row['ci95_delta'], 'groups': row['independent_groups'],
                               'warning': row['warning'], 'cohort_manifest_sha256': measurements['manifest_sha256']})
            charts.append({'family': family, 'label': family + (': Paired contradiction-rate change (lower is better)' if family == 'hallucination' else ': Paired recovery change (higher is better)'),
                           'cohort': cohort, 'points': points})
        report['methods']['combinations']['component_ablations'] = charts
    report["cost_plot_sources"] = {"source_sha256": source_hashes,
                                   "cohort_manifest_sha256": measurements["manifest_sha256"],
                                   "limits": ["No fitted or certified Pareto frontier. No end-to-end latency or GPU-dollar estimates.",
                                              "Sample prefix is an experimental budget, distinct from random baseline deployment needs.",
                                              "The timing instrument and quality cohort are distinct and explicitly labeled.",
                                              "CPU/model components exclude required capture/setup and some method-specific preparation. No missing timing is zero.",
                                              "Error-rate reductions must be read with assertion/off-topic coverage; mention recovery does not establish full faithfulness."]}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--costs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paired-specificity", type=Path)
    args = parser.parse_args()
    source_hashes = {str(p): sha256(p.read_bytes()).hexdigest() for p in (args.measurements, args.costs)}
    if args.paired_specificity:
        source_hashes[str(args.paired_specificity)] = sha256(args.paired_specificity.read_bytes()).hexdigest()
    output = populate(json.loads(args.report.read_text()), json.loads(args.measurements.read_text()),
                      json.loads(args.costs.read_text()), source_hashes,
                      json.loads(args.paired_specificity.read_text()) if args.paired_specificity else None)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(args.output), "quality_sources_unchanged": True,
                      "cost_series": len(output["methods"]["sample_selection"]["cost_frontier"])}))


if __name__ == "__main__":
    main()
