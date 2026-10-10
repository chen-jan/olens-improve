"""Export reviewed dashboard content to an isolated, static public Site.

The research report stays authoritative. Only infrastructure references and
links are adapted here; scientific numbers, uncertainty and caveats are kept.
"""

import argparse
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import zipfile

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


def pinned_json(pin):
    raw = Path(pin['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin['sha256']:
        raise ValueError('Delivery source bytes differ from their reviewed pin')
    return json.loads(raw)


def reviewed_test_attachment(source):
    """Check reveal authority before accessing the optional analysis source."""
    section = source.get('signed_comparisons', {}).get('test')
    if section is None:
        return None
    from append_signed_comparison import comparison, reviewed_identity
    reviewed_identity(section.get('review', {}), section.get('source_sha256'))
    if section['review'].get('reviewed_by') != 'root':
        raise ValueError('Public TEST results require root review')
    artifact = pinned_json({'path': section['source_path'], 'sha256': section['source_sha256']})
    expected = comparison(artifact, section['review'], section['source_path'],
                          section['source_sha256'], section['review_metadata_sha256'])
    for key, value in expected.items():
        if key != 'cost_source_verification' and section.get(key) != value:
            raise ValueError('TEST attachment differs from its exact reviewed source: ' + key)
    # Lazy import: old DEV/VAL exports do not load any deck implementation.
    from build_final_slides import reviewed_test
    reviewed_test(section)
    return section


def public_filename(name, extensions):
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name)
            or '..' in name or Path(name).suffix not in extensions):
        raise ValueError('Delivery public filename is outside the download allowlist')
    return name


def delivery_files(review_path, expected_sha, source, test):
    """An optional, source-pinned delivery capability; never scan directories."""
    review = pinned_json({'path': str(review_path), 'sha256': expected_sha})
    if (review.get('status') != 'root_reviewed' or review.get('reviewed_by') != 'root'
            or review.get('test_reveal_authorized') is not True or not review.get('reviewed_utc')):
        raise ValueError('Final delivery requires explicit root-reviewed reveal authority')
    datetime.fromisoformat(review['reviewed_utc'].replace('Z', '+00:00'))
    if (test is None or review.get('test_artifact_sha256') != test['source_sha256']
            or review.get('test_review_metadata_sha256') != test['review_metadata_sha256']):
        raise ValueError('Final delivery differs from the reviewed TEST attachment')
    pins = review.get('sources', {})
    if set(pins) - {'test_figures', 'whole_cohort', 'deck_build', 'deck_render'}:
        raise ValueError('Unexpected delivery source kind')
    whole = source.get('descriptive_whole_cohort')
    whole_rows = None
    if whole is not None:
        # Its separate reveal capability must precede any optional source reads.
        from build_final_slides import whole_cohort
        whole_rows, _ = whole_cohort(whole, test['condition_ids'])
        if 'whole_cohort' not in pins or pins['whole_cohort']['sha256'] != whole.get('source_sha256'):
            raise ValueError('Whole-469 appendix needs its separate exact source receipt')
    elif 'whole_cohort' in pins:
        raise ValueError('Whole-469 receipt has no reviewed report attachment')
    sources = {kind: pinned_json(pin) for kind, pin in pins.items()}
    figures = []
    if 'test_figures' in sources:
        receipt = sources['test_figures']
        if (receipt.get('status') != 'exported_supplied_values_no_aggregation'
                or receipt.get('stage') != 'test' or receipt.get('reviewed_by') != 'root'
                or any(receipt.get(key) != test[key] for key in
                       ('source_sha256', 'review_metadata_sha256', 'identities', 'family_counts'))
                or receipt.get('method_order') != test['condition_ids']):
            raise ValueError('TEST figures differ from the exact reviewed stage/menu/source')
        grids = {}
        for scope, field in (('cell', 'cell_rows'), ('original_item', 'original_item_rows')):
            indexed = {(r['condition'], r['family']): r['metric'] for r in test[field]}
            grids[scope] = {family: [{'condition': name, **indexed[name, family]}
                                   for name in test['condition_ids']] for family in test['family_counts']}
        if (receipt.get('plotted_cell_metrics') != grids['cell']
                or receipt.get('plotted_question_metrics') != grids['original_item']):
            raise ValueError('Figure counts and intervals differ from reviewed TEST values')
        paired = {}
        if test['paired_rows'] and 'plotted_paired_metrics' not in receipt:
            raise ValueError('TEST delivery needs its supplied paired figure metadata')
        if 'plotted_paired_metrics' in receipt:
            paired = {}
            for scope in grids:
                indexed = {(r['condition'], f): r for f, rows in grids[scope].items() for r in rows}
                paired[scope] = {f: [] for f in test['family_counts']}
                for row in test['paired_rows']:
                    f = row['family']
                    endpoint = (('original_grid_contradiction_rate' if f == 'hallucination' else 'original_grid_item_pass_rate')
                                if scope == 'original_item' else ('contradiction_rate' if f == 'hallucination' else 'cell_recovery'))
                    if row['scope'] == scope and row['endpoint'] == endpoint:
                        paired[scope][f].append({**row, 'baseline_metric': indexed[row['baseline_condition'], f],
                                                'proposed_metric': indexed[row['condition'], f]})
            if receipt['plotted_paired_metrics'] != paired:
                raise ValueError('Figure paired intervals differ from reviewed TEST contrasts')
        seen = set()
        for row in receipt['files']:
            name = public_filename(row['path'], {'.png', '.pdf'})
            if (not re.fullmatch(r'(?:family-(?:cell|question)-rates|paired-(?:cell|question)-deltas-[0-9]{2}|cross-task-error-recovery(?:-zoom)?)\.(?:png|pdf)', name)
                    or name in seen):
                raise ValueError('Unexpected or duplicate TEST figure')
            seen.add(name)
            path = Path(pins['test_figures']['path']).parent / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('TEST figure bytes differ from their reviewed pin')
            figures.append({'path': str(path), 'sha256': row['sha256'], 'public_name': name})
        if not {'family-cell-rates.png', 'family-cell-rates.pdf',
                'family-question-rates.png', 'family-question-rates.pdf'} <= seen:
            raise ValueError('TEST delivery needs cell and original-question figures')
        if any(name.rsplit('.', 1)[0] + ('.pdf' if name.endswith('.png') else '.png') not in seen for name in seen):
            raise ValueError('Every TEST figure needs both PNG and PDF')
        if any(name.startswith('paired-') for name in seen) and 'plotted_paired_metrics' not in receipt:
            raise ValueError('Paired figures need exact supplied contrast metadata')
        expected_paired = {f'paired-{view}-deltas-{page:02d}.{extension}'
            for scope, view in (('cell', 'cell'), ('original_item', 'question'))
            for page in range(1, (max((len(r) for r in paired.get(scope, {}).values()), default=0) + 7)//8 + 1)
            for extension in ('png', 'pdf')}
        if {name for name in seen if name.startswith('paired-')} != expected_paired:
            raise ValueError('TEST delivery needs all supplied paired figure pages')
    if whole is not None:
        if sources['whole_cohort'] != whole.get('measurement'):
            raise ValueError('Whole-469 attachment differs from the pinned descriptive analysis')
    downloads, names, kinds = [], set(), set()
    suffixes = {'editable_slides': '.pptx', 'slides_pdf': '.pdf', 'notes': '.md', 'report': '.md'}
    for row in review.get('downloads', []):
        kind = row.get('kind')
        if kind not in suffixes or kind in kinds:
            raise ValueError('Unexpected or duplicate delivery download kind')
        name = public_filename(row.get('public_name'), {suffixes[kind]})
        if name in names or not row.get('label') or row.get('public_content_verified') is not True:
            raise ValueError('Downloads need unique names, labels and reviewed public-content verification')
        names.add(name); kinds.add(kind)
        path = Path(row['path'])
        if path.suffix != suffixes[kind] or path.stem in {'report-source', 'source', 'geometry'}:
            raise ValueError('Raw report/source dumps are not delivery downloads')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Delivery download bytes differ from their reviewed pin')
        if kind == 'editable_slides':
            with zipfile.ZipFile(path) as archive:
                text = '\n'.join(archive.read(n).decode('utf-8') for n in archive.namelist()
                                 if n.endswith(('.xml', '.rels')))
        else:
            text = raw.decode('utf-8') if path.suffix == '.md' else ''
        if LOCAL_PATH.search(text) or INFRA_TEXT.search(text) or SECRET.search(text):
            raise ValueError('Delivery download contains private references or credentials')
        if kind != 'report':
            build_receipt = sources.get('deck_build', {})
            if (build_receipt.get('mode') != 'reviewed_test'
                    or build_receipt.get('test_artifact_sha256') != test['source_sha256']
                    or build_receipt.get('whole_cohort_complete') != (whole is not None)
                    or build_receipt.get('whole_cohort_artifact_sha256') != (whole['source_sha256'] if whole else None)):
                raise ValueError('Deck receipt differs from the reviewed TEST/whole-469 scope')
            if kind == 'slides_pdf':
                render = sources.get('deck_render', {})
                if render.get('pdf_sha256') != row['sha256'] or render.get('pages') != build_receipt.get('slides'):
                    raise ValueError('Slide PDF differs from the source-bound deck render receipt')
            elif build_receipt.get('outputs', {}).get(path.name) != row['sha256']:
                raise ValueError('Deck download differs from its build receipt')
        downloads.append(row)
    return {'review': public_data(review), 'figures': figures, 'downloads': downloads,
            'whole': public_data(whole), 'whole_rows': whole_rows,
            'test_figure_receipt': public_data(sources.get('test_figures'))}


def copy_pinned(row, destination):
    """Hash the exact bytes written, including a second check after validation."""
    raw = Path(row['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Delivery file changed before copy')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)


def package_delivery(bundle, output):
    cards = []
    for row in bundle['figures']:
        target = Path('figures/test-final') / row['public_name']
        copy_pinned(row, output / target)
        cards.append(f'<li><a href="{target.as_posix()}">Held-out TEST: {html.escape(row["public_name"])}</a></li>')
    if bundle['test_figure_receipt'] is not None:
        (output / 'figures/test-final/provenance.json').write_text(json.dumps(bundle['test_figure_receipt'], ensure_ascii=False) + '\n')
        cards.append('<li><a href="figures/test-final/provenance.json">Held-out figure values, counts, grouped intervals and source hashes</a></li>')
    for row in bundle['downloads']:
        target = Path('downloads') / row['public_name']
        copy_pinned(row, output / target)
        cards.append(f'<li><a href="{target.as_posix()}">{html.escape(row["label"])}</a></li>')
    (output / 'delivery-review.json').write_text(json.dumps(bundle['review'], ensure_ascii=False) + '\n')
    cards.append('<li><a href="delivery-review.json">Final-download review and source hashes</a></li>')
    appendix = ''
    if bundle['whole'] is not None:
        (output / 'descriptive-whole-469.json').write_text(json.dumps(bundle['whole'], ensure_ascii=False) + '\n')
        body = []
        for row in bundle['whole_rows']:
            value = 'Not estimated' if row['value'] is None else f'{100*row["value"]:.2f}%'
            ci = 'Not estimated' if row['ci'] is None else '–'.join(f'{100*x:.2f}%' for x in row['ci'])
            body.append('<tr>' + ''.join(f'<td>{html.escape(str(x))}</td>' for x in
                (row['condition'], row['family'], value, f'{row["numerator"]}/{row["denominator"]}', ci,
                 row['source_metric']['items'], row['source_metric']['independent_groups'])) + '</tr>')
        appendix = ('<details class="card"><summary>All 469 questions: descriptive appendix</summary>'
            '<p>Development + validation + TEST, not 469 held-out questions. Original family aggregation is unchanged; '
            'no combined score, retuning or automatic winner selection. Transcript contradictions retain their readout '
            'denominator (lower is better); the other tasks retain their original question criteria (higher is better).</p>'
            '<div style="overflow-x:auto"><table><thead><tr><th>Method</th><th>Task</th><th>Rate</th><th>Count</th>'
            '<th>Grouped 95% interval</th><th>Questions</th><th>Independent groups</th></tr></thead><tbody>'
            + ''.join(body) + '</tbody></table></div><a href="descriptive-whole-469.json">Exact descriptive values, '
            'paired comparisons, warnings and source hashes (JSON)</a></details>')
        cards.append('<li><a href="descriptive-whole-469.json">All 469 questions, descriptive DEV + VAL + TEST (JSON)</a></li>')
    if bundle['downloads']:
        appendix += ('<details class="card"><summary>Report and presentation downloads</summary><p>'
            + ('Whole-469 descriptive evidence is included.' if bundle['whole'] is not None else
               'Reviewed TEST preview; whole-469 evidence is still pending. This is not a complete-project delivery.')
            + ' The PDF is the same-content HTML mirror; native PowerPoint rendering has not been validated.</p><ul>'
            + ''.join(c for c in cards if 'downloads/' in c) + '</ul></details>')
    return cards, appendix


def snapshot_banner(test):
    return ('Public research snapshot. Last update shown below; held-out results remain pending until reviewed.'
            if test is None else 'Public research snapshot. Reviewed held-out TEST results are available; development and validation remain separate.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development-figures", type=Path,
                        help="Explicit reviewed development-scaling-v2 figure directory")
    parser.add_argument('--descriptive-review', type=Path,
                        help='Optional root-reviewed descriptive DEV/VAL site-map receipt')
    parser.add_argument('--descriptive-review-sha256', help='Exact SHA256 of that reviewed receipt')
    parser.add_argument('--delivery-review', type=Path,
                        help='Optional root-reviewed TEST figures, final downloads and whole-469 receipt')
    parser.add_argument('--delivery-review-sha256', help='Exact SHA256 of that delivery receipt')
    args = parser.parse_args()
    if bool(args.descriptive_review) != bool(args.descriptive_review_sha256):
        parser.error('Pass both descriptive review path and SHA256')
    if bool(args.delivery_review) != bool(args.delivery_review_sha256):
        parser.error('Pass both delivery review path and SHA256')
    descriptive = (descriptive_site_files(args.descriptive_review, args.descriptive_review_sha256)
                   if args.descriptive_review else None)
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    source = json.loads((root / "dashboard/report.json").read_text())
    test = reviewed_test_attachment(source)
    delivery = (delivery_files(args.delivery_review, args.delivery_review_sha256, source, test)
                if args.delivery_review else None)
    if source.get('descriptive_whole_cohort') is not None and delivery is None:
        raise ValueError('Whole-469 public evidence requires the explicit delivery receipt')
    output.mkdir(parents=True, exist_ok=True)
    qualitative=source.get('qualitative_reviews')
    if qualitative:
        validate_qualitative(qualitative)
        if public_data(qualitative)!=qualitative:
            raise ValueError('Reviewed case quotes must not be silently redacted')
    report = public_data(source)
    page = build(report)
    page = page.replace('<a href="../docs/REPORT.md">Working research report (local Markdown)</a>',
                        '<a href="report.md">Research report (Markdown)</a> · <a href="figures.html">Download charts</a>')
    page = page.replace("<header>", '<header><p class="meta">' + snapshot_banner(test) + '</p>', 1)
    (output / "details.html").write_text(page)
    overview = build_overview(report)
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
    if delivery:
        extra_cards, appendix = package_delivery(delivery, output)
        cards.extend(extra_cards)
        if appendix:
            if '</main>' not in overview:
                raise ValueError('Overview has no appendix insertion point')
            overview = overview.replace('</main>', appendix + '</main>', 1)
    (output / "index.html").write_text(overview)
    map_note = ('<p>Read-site maps describe the unchanged development and validation grids. Position rank orders selected positions within each item; it does not align token meaning across items. The separate JSON contains exact counts, missingness and exploratory grouped intervals. These maps do not select a better layer or position.</p>' if descriptive else '')
    download_title = 'Reviewed study charts and downloads' if test is not None else 'Development and validation charts'
    (output / "figures.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Oracle Lens charts</title><style>body{font:17px/1.6 system-ui;max-width:850px;margin:3rem auto;padding:0 1rem;color:#172b35}a{color:#147a9b}a:focus-visible{outline:2px solid #147a9b;outline-offset:3px}.map-download{display:flex;flex-wrap:wrap;justify-content:space-between;gap:.2rem 1rem;padding:.45rem 0;border-bottom:1px solid #dce5e8}.formats{white-space:nowrap}.map-download span:first-child{max-width:100%}</style><a href="index.html">← Research dashboard</a><h1>' + download_title + '</h1><p>Files are labeled by study stage. Error bars, sample sizes and limitations are explained in the dashboard.</p>' + map_note + '<ul>' + ''.join(cards) + '</ul></html>')
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
    if delivery:
        receipt.update(delivery_review_sha256=args.delivery_review_sha256,
                       test_artifact_sha256=test['source_sha256'],
                       whole_cohort_complete=delivery['whole'] is not None)
    (output.parent / "publication-review.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"files": len(files), "source_updated_utc": source["updated_utc"], "review": str(output.parent / "publication-review.json")}))


if __name__ == "__main__":
    main()
