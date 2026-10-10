"""Export reviewed dashboard content to an isolated, static public Site.

The research report stays authoritative. Only infrastructure references and
links are adapted here; scientific numbers, uncertainty and caveats are kept.
"""

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil

from build_dashboard import build
from build_dashboard_overview import build as build_overview


LOCAL_PATH = re.compile(r"/(?:orcd|home|tmp|scratch|workspace)/[^\s\"'<>`\\)\],;]+")
INFRA_KEY = re.compile(r"^(?:job_?ids?|slurm_?job_?ids?|pids?|process_?ids?|hostnames?|node_?names?|cpu_?masks?)$", re.I)
INFRA_TEXT = re.compile(r"\b(?:node\d{3,}|(?:PID|pid|job(?:_id)?)[ :=#]+\d{4,})\b")
SECRET = re.compile(r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----|Bearer\s+[A-Za-z0-9_.-]{16,})")


def public_text(value):
    value = LOCAL_PATH.sub(lambda match: "artifact-" + hashlib.sha256(match[0].encode()).hexdigest()[:12], value)
    return INFRA_TEXT.sub("[internal resource]", value)


def public_data(value):
    if isinstance(value, dict):
        return {public_text(key): public_data(child) for key, child in value.items() if not INFRA_KEY.fullmatch(key)}
    if isinstance(value, list):
        return [public_data(child) for child in value]
    return public_text(value) if isinstance(value, str) else value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = json.loads((root / "dashboard/report.json").read_text())
    report = public_data(source)
    page = build(report)
    page = page.replace('<a href="../docs/REPORT.md">Working research report (local Markdown)</a>',
                        '<a href="report.md">Research report (Markdown)</a> · <a href="figures.html">Download charts</a>')
    page = page.replace("<header>", '<header><p class="meta">Public research snapshot. Last update shown below; held-out results remain pending until reviewed.</p>', 1)
    (output / "details.html").write_text(page)
    (output / "index.html").write_text(build_overview(report))
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False) + "\n")
    markdown = public_text((root / "docs/REPORT.md").read_text())
    # Keep genuine web citations and packaged figures; local-only evidence is
    # named as text rather than presented as a broken public hyperlink.
    markdown = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                      lambda m: m[0] if m[2].startswith(("https://", "http://")) else m[1], markdown)
    (output / "report.md").write_text(markdown)
    cards = []
    for directory in ("validation-v1", "validation-v2"):
        for path in sorted((root / "dashboard/figures" / directory).glob("*")):
            if path.suffix not in (".png", ".pdf"):
                continue
            relative = Path("figures") / directory / path.name
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            cards.append(f'<li><a href="{html.escape(relative.as_posix())}">{html.escape(directory + ": " + path.name)}</a></li>')
    (output / "figures.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Oracle Lens charts</title><style>body{font:17px/1.6 system-ui;max-width:850px;margin:3rem auto;padding:0 1rem;color:#172b35}a{color:#147a9b}</style><a href="/">← Research dashboard</a><h1>Validation charts</h1><p>These are validation results. Error bars and limitations are explained in the dashboard.</p><ul>' + ''.join(cards) + '</ul></html>')
    files = []
    for path in sorted(output.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in (".html", ".json", ".md"):
            text = path.read_text()
            if LOCAL_PATH.search(text) or INFRA_TEXT.search(text) or SECRET.search(text):
                raise ValueError(f"Public export contains an internal reference or credential: {path.name}")
        files.append({"path": path.relative_to(output).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    receipt = {"source_report_sha256": hashlib.sha256((root / "dashboard/report.json").read_bytes()).hexdigest(),
               "source_updated_utc": source["updated_utc"], "public_files": files,
               "scope": "Reviewed dashboard, report and chart copies only; internal paths/resource identifiers removed. Scientific values unchanged."}
    (output.parent / "publication-review.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"files": len(files), "source_updated_utc": source["updated_utc"], "review": str(output.parent / "publication-review.json")}))


if __name__ == "__main__":
    main()
