"""Build the final dashboard with a separately bound original-baseline supplement.

The historical builder and its exact scientific payload remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--original-reference', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    output = Path(remaining[remaining.index('--output') + 1])
    if output.exists():
        raise ValueError('Use a new dashboard directory; preserve historical builds')
    supplement_bytes = args.original_reference.read_bytes()
    supplement = json.loads(supplement_bytes)
    if (supplement['status'] != 'posthoc_exploratory_pointwise_only'
            or supplement['reference'] != 'raw_n1-n1'
            or supplement['cohort'] != 'full'
            or len(supplement['comparisons']) != 28):
        raise ValueError('Original-reference supplement is incomplete or has another scope')
    subprocess.run([sys.executable, str(Path(__file__).with_name('build_expansion_dashboard.py')),
                    *remaining], check=True)
    data = json.loads((output / 'expansion-data.json').read_text())
    for key, source_key in [('results_sha256', 'expanded_results'),
                            ('root_review_sha256', 'root_review')]:
        if supplement[key] != data['source_hashes'][source_key]:
            raise ValueError('Original-reference supplement differs from the reviewed source')
    if supplement['manifest_sha256'] != data['manifest_sha256']:
        raise ValueError('Original-reference supplement differs from the frozen menu')
    serialized = json.dumps(supplement, ensure_ascii=False, separators=(',', ':'))
    (output / 'original-reference-comparisons.json').write_text(serialized + '\n')
    page = output / 'index.html'
    marker = '<script src="expansion.js">'
    text = page.read_text()
    if text.count(marker) != 1:
        raise ValueError('Expected exactly one dashboard script')
    embedded = ('<script type="application/json" id="original-reference-data">'
                + serialized.replace('<', '\\u003c') + '</script>')
    page.write_text(text.replace(marker, embedded + marker))
    print(json.dumps({'original_reference_sha256': hashlib.sha256(supplement_bytes).hexdigest(),
                      'comparisons': 28, 'new_api_calls': 0}))


if __name__ == '__main__':
    main()
