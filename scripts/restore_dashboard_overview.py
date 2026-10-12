"""Restore the familiar overview while retaining immutable research payloads."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore(site: Path, receipt: Path) -> dict:
    if receipt.exists():
        raise FileExistsError('Keep prior receipts; choose a new path')
    dist = site / 'dist'
    followup = dist / 'follow-up.html'
    if followup.exists():
        raise FileExistsError('Inspect the existing follow-up before replacing it')
    archived = (dist / 'historical-expanded-study.html').read_text()
    payloads = re.findall(r'<script type="application/json" id="(?:embedded-data|original-reference-data)">[\s\S]*?</script>', archived)
    if len(payloads) != 2:
        raise ValueError('Expected exact historical data and original-reference payloads')
    source = json.loads(re.search(r'>([\s\S]*)</script>', payloads[0]).group(1))
    if len(source['conditions']) != 70:
        raise ValueError('Unexpected historical condition count')
    untouched = {str(p.relative_to(dist)): digest(p) for p in dist.rglob('*') if p.is_file() and p.name != 'index.html'}
    prior_index = digest(dist / 'index.html')
    shutil.copyfile(dist / 'index.html', followup)
    template = (ROOT / 'dashboard/overview.html').read_text()
    marker = '<script src="overview.js">'
    if template.count(marker) != 1:
        raise ValueError('Expected one overview script')
    (dist / 'index.html').write_text(template.replace(marker, ''.join(payloads) + marker))
    shutil.copyfile(ROOT / 'dashboard/expansion.js', dist / 'overview.js')
    for path, expected in untouched.items():
        if digest(dist / path) != expected:
            raise ValueError('Existing asset changed: ' + path)
    if digest(followup) != prior_index:
        raise ValueError('Follow-up copy differs from prior landing page')
    result = {
        'status': 'assembled_pending_browser_and_publication',
        'previous_landing_sha256': prior_index,
        'preserved_assets': untouched,
        'outputs_sha256': {name: digest(dist / name) for name in ('index.html', 'overview.js', 'follow-up.html')},
        'embedded_payload_sha256': [hashlib.sha256(p.encode()).hexdigest() for p in payloads],
        'scientific_records_modified': False,
        'model_calls': 0,
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    result = restore(args.site, args.receipt)
    print(json.dumps({'status': result['status'], 'preserved_assets': len(result['preserved_assets']), 'model_calls': 0}))
