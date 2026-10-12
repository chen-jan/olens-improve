"""Describe the frozen 32-site larger-N pilot; never infer question accuracy.

Reads completed score256 output and frozen sampling evidence, with no model
inference, API calls, or cache writes. The local tokenizer counts the original
and capped references without rewriting either source text.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from olens_improve.selection import parse_bullets, render_bullets

PREFIXES = (1, 2, 4, 8, 16, 32, 64, 128, 256)
FAMILY_NAMES = {
    "hallucination": "Hallucination (chat)",
    "multihop_mt": "Multihop (multi-token)",
    "chain_intermediates": "Chained intermediates",
    "role_bound_association": "Role-bound association",
}
FAMILY_CONTEXT = {
    "hallucination": "Transcript contradictions and verifiability",
    "multihop_mt": "Recovery of bridge concepts",
    "chain_intermediates": "Intermediate computational content",
    "role_bound_association": "Entity–role binding",
}
SCOPE = "32 fixed development activation sites, eight per family; exploratory site-level reconstruction, not official whole-question accuracy"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write_text(path, text):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text)
    os.replace(temp, path)


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def write_csv(path, rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    write_text(path, stream.getvalue())


def validate_inputs(manifest, events):
    cells = {c["cell_id"]: c for c in manifest["cells"]}
    if len(cells) != 32 or Counter(c["family"] for c in cells.values()) != Counter({f: 8 for f in FAMILY_NAMES}):
        raise ValueError("Require the frozen 32-site, eight-per-family pilot")
    if any(c.get("split") != "development" for c in cells.values()):
        raise ValueError("This report's scope is development sites only")
    if len(events) != 32 or {r["cell_id"] for r in events} != set(cells):
        raise ValueError("Require exactly one completed result per frozen site")
    for event in events:
        cell = cells[event["cell_id"]]
        for key in ("family", "item_id", "layer", "position", "activation_sha256"):
            if event[key] != cell[key]:
                raise ValueError(f"Result target differs from manifest: {key}")
        results = event["results"]
        if len(results) != 9 or {r["n"] for r in results} != set(PREFIXES):
            raise ValueError("Require complete N1 through N256 selections")
        if any(r["method"] != "best_n_exact" for r in results):
            raise ValueError("Unexpected method in complete-sample curve")
        previous = -math.inf
        for result in sorted(results, key=lambda r: r["n"]):
            fve = result["fits"]["exact"]["fve"]
            if not math.isfinite(fve) or fve + 1e-10 < previous:
                raise ValueError("Nonfinite or nonmonotone nested best-of-N reconstruction")
            previous = fve
            if result["bullet_count"] > 4 or result["token_count"] > 256:
                raise ValueError("Selected output violates the frozen cap")
            index = result["sample_index"]
            if index is not None and not 0 <= index < result["n"]:
                raise ValueError("Selected sample is outside its available prefix")
    return cells


def summarize(manifest, events, token_count):
    cells = validate_inputs(manifest, events)
    site_rows, packet = [], []
    for event in sorted(events, key=lambda r: (list(FAMILY_NAMES).index(r["family"]), r["cell_id"])):
        cell = cells[event["cell_id"]]
        choices = {r["n"]: r for r in event["results"]}
        parent = choices[32]
        for n in PREFIXES:
            r = choices[n]
            site_rows.append({"cell_id": event["cell_id"], "family": event["family"],
                "family_title": FAMILY_NAMES[event["family"]], "item_id": event["item_id"],
                "group_id": cell.get("group_id"), "layer": event["layer"], "position": event["position"],
                "n": n, "fve_percent": r["fits"]["exact"]["fve"] * 100,
                "gain_vs_n32_percentage_points": (r["fits"]["exact"]["fve"] - parent["fits"]["exact"]["fve"]) * 100,
                "sample_index": r["sample_index"], "text_changed_vs_n32": r["text"] != parent["text"],
                "sample_changed_vs_n32": r["sample_index"] != parent["sample_index"],
                "qwen_tokens": r["token_count"], "bullets": r["bullet_count"],
                "characters": len(r["text"]), "whitespace_words": len(r["text"].split()),
                "text_sha256": text_sha(r["text"]), "reason": r["reason"]})
        raw = cell["baseline_samples"][0]
        sample_id = f"{raw.get('global_pool_id') or raw['pool_id']}:{cell['cell_id']}:0"
        parsed = parse_bullets(raw["text"], sample_id, 0, token_count=token_count, max_output_tokens=256)
        capped_text = render_bullets(parsed.bullets)
        packet.append({"cell_id": cell["cell_id"], "family": cell["family"],
            "family_title": FAMILY_NAMES[cell["family"]], "item_id": cell["item_id"],
            "group_id": cell.get("group_id"), "layer": cell["layer"], "position": cell["position"],
            "activation_sha256": cell["activation_sha256"], "baseline_n32_audit": event["baseline_n32_audit"],
            "raw_original": {"label": "Original released Oracle Lens — raw N1 reference",
                "text": raw["text"], "text_sha256": text_sha(raw["text"]), "sample_index": 0,
                "qwen_tokens": token_count(raw["text"]),
                "dash_bullet_markers": len(re.findall(r"^[ \t]*-[ \t]+", raw["text"], flags=re.MULTILINE)),
                "raw_reference_exempt_from_output_cap": True, "reconstruction_fve": None},
            "capped_original": {"label": "Original N1 with four-bullet / 256-token cap",
                "text": capped_text, "text_sha256": text_sha(capped_text), "sample_index": 0,
                "qwen_tokens": token_count(capped_text), "bullets": len(parsed.bullets),
                "parser_flags": list(parsed.flags), "differs_from_raw": capped_text != raw["text"]},
            "best_n1": choices[1],
            "selected_readouts": {str(n): choices[n] for n in (32, 64, 128, 256)}})
    aggregates = []
    for family in ("all", *FAMILY_NAMES):
        for n in PREFIXES:
            subset = [r for r in site_rows if r["n"] == n and (family == "all" or r["family"] == family)]
            gains = [r["gain_vs_n32_percentage_points"] for r in subset]
            aggregates.append({"family": family, "family_title": "All four families" if family == "all" else FAMILY_NAMES[family],
                "n": n, "sites": len(subset), "mean_fve_percent": statistics.mean(r["fve_percent"] for r in subset),
                "mean_gain_vs_n32_percentage_points": statistics.mean(gains),
                "median_gain_vs_n32_percentage_points": statistics.median(gains),
                "min_gain_vs_n32_percentage_points": min(gains), "max_gain_vs_n32_percentage_points": max(gains),
                "positive_gain_sites": sum(g > 1e-8 for g in gains), "negative_gain_sites": sum(g < -1e-8 for g in gains),
                "text_changed_sites_vs_n32": sum(r["text_changed_vs_n32"] for r in subset),
                "sample_changed_sites_vs_n32": sum(r["sample_changed_vs_n32"] for r in subset),
                "mean_qwen_tokens": statistics.mean(r["qwen_tokens"] for r in subset),
                "mean_bullets": statistics.mean(r["bullets"] for r in subset),
                "selected_index_min": min((r["sample_index"] for r in subset if r["sample_index"] is not None), default=None),
                "selected_index_max": max((r["sample_index"] for r in subset if r["sample_index"] is not None), default=None)})
    return site_rows, aggregates, packet


def plot_curves(path, aggregates):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.5), sharex=True, sharey=True)
    colors = ("#176080", "#7351A5", "#2A7762", "#AF5C35")
    for ax, (family, title), color in zip(axes.flat, FAMILY_NAMES.items(), colors):
        rows = [r for r in aggregates if r["family"] == family]
        ax.axvspan(45, 300, color="#EBF0F5", alpha=.75, zorder=0)
        ax.plot(PREFIXES, [r["mean_fve_percent"] for r in rows], color=color,
                marker="o", linewidth=2, markersize=5)
        ax.axvline(32, color="#718096", linestyle="--", linewidth=1)
        ax.set_xscale("log", base=2)
        ax.set_xticks(PREFIXES, [str(n) for n in PREFIXES])
        ax.set_xlim(.85, 290)
        ax.set_title(title + "\n" + FAMILY_CONTEXT[family], loc="left", fontsize=12, pad=12)
        ax.yaxis.set_major_locator(MaxNLocator(5))
        ax.grid(axis="y", color="#DFE5EB", linewidth=.7)
        ax.set_axisbelow(True)
        ax.tick_params(axis="both", length=3, color="#93A1AF")
    for ax in axes[:, 0]:
        ax.set_ylabel("Activation variance explained (%)")
    for ax in axes[-1]:
        ax.set_xlabel("Candidate samples, N")
    fig.suptitle("How reconstruction changes with more samples", x=.075, ha="left", fontsize=18, weight="bold")
    fig.text(.075, .917, "32 fixed development sites · 8 per task · one selected readout, at most four bullets", fontsize=10, color="#4A5568")
    fig.text(.075, .041, "Descriptive site-level reconstruction only; no confidence intervals or whole-question accuracy.\nDashed line: existing N32 baseline. Shaded region: new N64–256 samples. Raw released Oracle Lens is a separate text reference.", fontsize=9, color="#4A5568")
    fig.subplots_adjust(left=.075, right=.98, top=.84, bottom=.14, hspace=.5, wspace=.14)
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)


def review_markdown(packet):
    lines = ["# Larger-N pilot: fixed-site review packet", "", SCOPE + ".", "",
        "The raw released Oracle Lens reference preserves every source byte. The capped reference is shown separately. Reconstruction scores do not establish factual quality.", ""]
    for row in packet:
        lines += [f"## {row['family_title']} · {row['cell_id']}", "",
                  f"Item `{row['item_id']}` · layer {row['layer']} · position {row['position']} · group `{row['group_id']}`", ""]
        choices = [(row["raw_original"]["label"], row["raw_original"]),
                   (row["capped_original"]["label"], row["capped_original"])]
        choices += [(f"Best complete sample, N={n}", row["selected_readouts"][str(n)]) for n in (32, 64, 128, 256)]
        for label, choice in choices:
            metrics = f"sample index {choice['sample_index']} · {choice.get('qwen_tokens', choice.get('token_count'))} Qwen tokens"
            if "fits" in choice:
                metrics += f" · reconstruction FVE {100 * choice['fits']['exact']['fve']:.4f}%"
            fence = "`" * max(4, max((len(s) for s in re.findall(r"`+", choice["text"])), default=0) + 1)
            lines += [f"### {label}", "", metrics, "", fence + "text", choice["text"], fence, ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selections", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--sampling-status", required=True, type=Path)
    p.add_argument("--profile", action="append", default=[], type=Path,
                   help="Sampling or AR profile JSON; repeat to attach both")
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    manifest = json.loads(a.manifest.read_text())
    body = a.selections.read_bytes()
    if not body.endswith(b"\n"):
        raise ValueError("Uncommitted selections tail")
    events = [json.loads(line) for line in body.splitlines() if line.strip()]
    status = json.loads(a.sampling_status.read_text())
    manifest_sha = sha(a.manifest)
    if status.get("status") != "complete" or status.get("manifest_sha256") != manifest_sha:
        raise ValueError("Require matching completed sampling status")
    spec_path = a.selections.parent / "spec.json"
    spec = json.loads(spec_path.read_text())
    if (spec.get("loaded_complete_prefix") != 256 or spec.get("prefixes") != list(PREFIXES)
            or spec.get("source_sha256", {}).get(str(a.manifest.resolve())) != manifest_sha):
        raise ValueError("Scoring source contract differs from completed N256 pilot")
    encoded = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    if any(r["spec_sha256"] != hashlib.sha256(encoded).hexdigest() for r in events):
        raise ValueError("Selection event does not match scoring contract")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(manifest["base_snapshot"], local_files_only=True)
    count = lambda text: len(tokenizer(text, add_special_tokens=False)["input_ids"])
    site_rows, aggregates, packet = summarize(manifest, events, count)
    inputs = [a.manifest, a.selections, a.sampling_status, spec_path, *a.profile]
    sources = [{"path": str(path.resolve()), "sha256": sha(path)} for path in inputs]
    profiles = [{"source": sources[4 + i], "report": json.loads(path.read_text())} for i, path in enumerate(a.profile)]
    summary = {"scope": SCOPE, "sites": 32, "sites_per_family": 8,
        "unique_items": len({(c['family'], c['item_id']) for c in manifest['cells']}),
        "unique_groups": len({(c['family'], c.get('group_id')) for c in manifest['cells']}),
        "aggregation": "Equal weight per fixed activation site; paired differences on the same sites",
        "confidence_intervals": None, "official_whole_question_accuracy": False,
        "source_files": sources, "analysis_code_sha256": sha(Path(__file__)),
        "historical_n32_audit_counts": dict(Counter(r["baseline_n32_audit"]["status"] for r in events)),
        "raw_original_differs_from_capped_sites": sum(r["capped_original"]["differs_from_raw"] for r in packet),
        "sample_index_histograms": {str(n): dict(Counter(str(r["sample_index"]) for r in site_rows if r["n"] == n)) for n in PREFIXES},
        "aggregates": aggregates, "sampling_status": status, "profiles": profiles}
    a.output.mkdir(parents=True, exist_ok=True)
    write_json(a.output / "summary.json", summary)
    write_csv(a.output / "summary.csv", aggregates)
    write_csv(a.output / "site_metrics.csv", site_rows)
    write_json(a.output / "review_packet.json", {"scope": SCOPE, "source_files": sources, "sites": packet})
    write_text(a.output / "review_packet.md", review_markdown(packet))
    with tempfile.TemporaryDirectory(prefix="larger-n-plot-cache-") as cache:
        prior = {key: os.environ.get(key) for key in ("MPLCONFIGDIR", "XDG_CACHE_HOME")}
        os.environ.update({key: cache for key in prior})
        try:
            plot_curves(a.output / "reconstruction_by_n.png", aggregates)
        finally:
            for key, value in prior.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    files = [path for path in a.output.iterdir() if path.is_file() and path.name != "receipt.json"]
    write_json(a.output / "receipt.json", {"status": "complete", "scope": SCOPE,
        "files_sha256": {path.name: sha(path) for path in sorted(files)}, "source_files": sources})
    print(json.dumps({"status": "complete", "output": str(a.output), "sites": 32,
                      "historical_n32_audit_counts": summary["historical_n32_audit_counts"]}))


if __name__ == "__main__":
    main()
