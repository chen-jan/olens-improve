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
from dashboard_qualitative import validated as validate_qualitative


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


def development_figure_files(directory, source_sha256):
    data=json.loads((directory/'figure-data.json').read_text())
    if data.get('reviewed_by')!='root' or data['source']['sha256']!=source_sha256:
        raise ValueError('Development figures must bind the reviewed scaling source')
    pins={row['path']:row['sha256'] for row in data['files']}
    names=('development-scaling-cell.png','development-scaling-cell.pdf',
           'development-scaling-item.png','development-scaling-item.pdf')
    paths=[]
    for name in names:
        path=directory/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=pins.get(name):
            raise ValueError('Development figure bytes differ from their reviewed receipt')
        paths.append(path)
    return paths


def descriptive_site_files(review_path, expected_review_sha256):
    """Validate the optional complete DEV/VAL map bundle before copying it."""
    from render_descriptive_grid import FAMILIES, validate_artifact
    raw = Path(review_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_review_sha256:
        raise ValueError('Descriptive review pin differs')
    review = json.loads(raw)
    if review.get('status') != 'root_reviewed' or review.get('reviewed_by') != 'root':
        raise ValueError('Descriptive maps require root review')
    sources = {}
    for kind in ('analysis', 'figures'):
        pin = review['sources'][kind]
        content = Path(pin['path']).read_bytes()
        if hashlib.sha256(content).hexdigest() != pin['sha256']:
            raise ValueError('Descriptive source receipt pin differs: ' + kind)
        sources[kind] = json.loads(content)
    data, receipt = sources['analysis'], sources['figures']
    validate_artifact(data)
    if {s['stage'] for s in data['stages']} != {'development', 'validation'} or len(data['stages']) != 2:
        raise ValueError('Expected exactly the descriptive DEV/VAL stages')
    if (receipt.get('source_sha256') != review['sources']['analysis']['sha256']
            or receipt.get('test_outcomes_accessed') is not False
            or receipt.get('metrics_and_intervals_recomputed') is not False):
        raise ValueError('Descriptive figures do not bind unchanged DEV/VAL data')
    expected = {f'{stage}-{family}.{extension}' for stage in ('development', 'validation')
                for family in FAMILIES for extension in ('png', 'pdf')}
    paths = []
    for pin in receipt['figures']:
        path = Path(pin['path'])
        if path.name not in expected or path.name in {p.name for p in paths}:
            raise ValueError('Unexpected or duplicate descriptive figure')
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('Descriptive figure bytes differ from reviewed receipt')
        paths.append(path)
    if {p.name for p in paths} != expected:
        raise ValueError('Expected all 16 descriptive figures')
    sanitized = public_data(data)
    serialized = json.dumps(sanitized, ensure_ascii=False)
    if LOCAL_PATH.search(serialized) or INFRA_TEXT.search(serialized) or SECRET.search(serialized):
        raise ValueError('Descriptive data contains private references or credentials')
    return paths, sanitized, public_data(review)


def package_descriptive_sites(bundle, output):
    paths, data, review = bundle
    directory = output / 'figures/read-sites'
    directory.mkdir(parents=True, exist_ok=True)
    cards = []
    for path in paths:
        shutil.copyfile(path, directory / path.name)
    families = {'hallucination': 'Transcript contradictions', 'multihop_mt': 'Multi-hop facts',
                'chain_intermediates': 'Arithmetic steps', 'role_bound_association': 'Who did what'}
    for stage, stage_label in (('development', 'Development'), ('validation', 'Validation')):
        for family, family_label in families.items():
            title = stage_label + ': ' + family_label
            links = []
            for extension in ('png', 'pdf'):
                target = f'figures/read-sites/{stage}-{family}.{extension}'
                links.append(f'<a href="{target}" aria-label="{html.escape(title)} {extension.upper()}">{extension.upper()}</a>')
            cards.append(f'<li class="map-download"><span>{html.escape(title)}</span><span class="formats">' + ' · '.join(links) + '</span></li>')
    (directory / 'grid-data.json').write_text(json.dumps(data, ensure_ascii=False) + '\n')
    (directory / 'review.json').write_text(json.dumps(review, ensure_ascii=False) + '\n')
    cards.append('<li><a href="figures/read-sites/grid-data.json">Descriptive DEV/VAL site counts and grouped intervals (JSON)</a> · <a href="figures/read-sites/review.json">Review and source hashes</a></li>')
    return cards


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development-figures", type=Path,
                        help="Explicit reviewed development-scaling-v2 figure directory")
    parser.add_argument('--descriptive-review', type=Path,
                        help='Optional root-reviewed descriptive DEV/VAL site-map receipt')
    parser.add_argument('--descriptive-review-sha256', help='Exact SHA256 of that reviewed receipt')
    args = parser.parse_args()
    if bool(args.descriptive_review) != bool(args.descriptive_review_sha256):
        parser.error('Pass both descriptive review path and SHA256')
    descriptive = (descriptive_site_files(args.descriptive_review, args.descriptive_review_sha256)
                   if args.descriptive_review else None)
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = json.loads((root / "dashboard/report.json").read_text())
    qualitative=source.get('qualitative_reviews')
    if qualitative:
        validate_qualitative(qualitative)
        if public_data(qualitative)!=qualitative:
            raise ValueError('Reviewed case quotes must not be silently redacted')
    report = public_data(source)
    page = build(report)
    page = page.replace('<a href="../docs/REPORT.md">Working research report (local Markdown)</a>',
                        '<a href="report.md">Research report (Markdown)</a> · <a href="figures.html">Download charts</a>')
    page = page.replace("<header>", '<header><p class="meta">Public research snapshot. Last update shown below; held-out results remain pending until reviewed.</p>', 1)
    (output / "details.html").write_text(page)
    (output / "index.html").write_text(build_overview(report))
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False) + "\n")
    if qualitative:
        (output / 'qualitative-evidence.json').write_text(json.dumps(qualitative,ensure_ascii=False)+'\n')
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
    if args.development_figures:
        for path in development_figure_files(args.development_figures,source['development_scaling']['source_sha256']):
            name=path.name
            relative=Path('figures')/'development-scaling-v2'/name
            destination=output/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,destination)
            cards.append(f'<li><a href="{html.escape(relative.as_posix())}">Development: {html.escape(name)}</a></li>')
    if descriptive:
        cards.extend(package_descriptive_sites(descriptive, output))
    map_note = ('<p>Read-site maps describe the unchanged development and validation grids. Position rank orders selected positions within each item; it does not align token meaning across items. The separate JSON contains exact counts, missingness and exploratory grouped intervals. These maps do not select a better layer or position.</p>' if descriptive else '')
    (output / "figures.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Oracle Lens charts</title><style>body{font:17px/1.6 system-ui;max-width:850px;margin:3rem auto;padding:0 1rem;color:#172b35}a{color:#147a9b}a:focus-visible{outline:2px solid #147a9b;outline-offset:3px}.map-download{display:flex;flex-wrap:wrap;justify-content:space-between;gap:.2rem 1rem;padding:.45rem 0;border-bottom:1px solid #dce5e8}.formats{white-space:nowrap}.map-download span:first-child{max-width:100%}</style><a href="index.html">← Research dashboard</a><h1>Development and validation charts</h1><p>Files are labeled by study stage. Error bars, sample sizes and limitations are explained in the dashboard.</p>' + map_note + '<ul>' + ''.join(cards) + '</ul></html>')
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
