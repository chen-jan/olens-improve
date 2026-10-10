"""Frozen wrong-activation diagnostic: first existing matched donor, no output search."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path


def load(path):
    body = Path(path).read_bytes()
    return json.loads(body), sha256(body).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'controls', 'manifest', 'fresh-manifest', 'output'):
        p.add_argument('--' + name, required=True)
    args = p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Run on allocated CPU resources')
    manifest, manifest_sha = load(args.manifest)
    controls, controls_sha = load(args.controls)
    fresh, fresh_sha = load(args.fresh_manifest)
    cells = {c['cell_id']: c for c in manifest['cells']}
    fresh = {c['cell_id']: c for c in fresh['cells']}
    if len(cells) != len(manifest['cells']) or any(c['split'] != 'development' for c in cells.values()):
        raise ValueError('Require unique development cohort')
    if controls['split_sha256'] != manifest['split_sha256']:
        raise ValueError('Control bank belongs to another split')
    body = Path(args.baseline).read_bytes()
    baseline_sha = sha256(body).hexdigest()
    parent, _ = load(Path(args.baseline).with_name('export.json'))
    if parent['selection_sha256'] != baseline_sha:
        raise ValueError('Baseline snapshot hash differs')
    originals = {}
    for line in body.splitlines():
        row = json.loads(line)
        cid = row['cell_id']
        if cid in originals:
            raise ValueError('Duplicate baseline cell')
        if cid not in cells or row['activation_sha256'] != fresh[cid]['activation_sha256']:
            raise ValueError('Baseline provenance differs from fresh cohort')
        if any(row[k] != cells[cid][k] or fresh[cid][k] != cells[cid][k]
               for k in ('family', 'item_id', 'layer', 'position', 'split')):
            raise ValueError('Baseline/fresh metadata differs from frozen cohort')
        selected = [s for s in row['selections'] if s['method'] == 'capped_n1' and s['n'] == 1]
        if len(selected) != 1:
            raise ValueError('Missing or duplicate capped N1')
        originals[cid] = (row, selected[0])
    if originals.keys() != cells.keys():
        raise ValueError('Baseline coverage differs from frozen cohort')
    rows, donor_counts, empty = [], Counter(), 0
    for cid in sorted(cells):
        target = cells[cid]
        bank = controls['control_cell_ids_by_target'][cid]
        if not bank:
            raise ValueError('Frozen bank has no donor; do not choose replacement')
        donor_id = bank[0]
        donor = cells[donor_id]
        own_ref, donor_ref = (controls['control_bank'][i] for i in (cid, donor_id))
        for actual, ref in ((target, own_ref), (donor, donor_ref)):
            if any(actual[k] != ref[k] for k in ('family', 'item_id', 'layer', 'position', 'split', 'group_id')):
                raise ValueError('Frozen bank metadata differs from development cohort')
        for key in ('family', 'layer', 'read_position_kind'):
            if own_ref[key] != donor_ref[key]:
                raise ValueError('Frozen first donor is not matched')
        if donor['split'] != 'development' or donor['group_id'] == target['group_id']:
            raise ValueError('Donor split/group exclusion violated')
        source_row, source = originals[donor_id]
        target_row, target_text = originals[cid]
        donor_counts[donor_id] += 1
        empty += not source['text'].strip()
        provenance = {
            'donor_cell_id': donor_id, 'donor_group_id': donor['group_id'],
            'target_group_id': target['group_id'], 'donor_rank': 0,
            'matched_read_position_kind': own_ref['read_position_kind'],
            'donor_activation_sha256': source_row['activation_sha256'],
            'donor_text_sha256': sha256(source['text'].encode()).hexdigest(),
            'target_capped_n1_text_sha256': sha256(target_text['text'].encode()).hexdigest(),
            'donor_output_empty': not source['text'].strip(), 'donor_output_missing': False,
        }
        selected = dict(source, method='matched_donor_capped_n1', n=1,
                        fits=None, fits_scope='not_reconstruction_scored', provenance=provenance)
        rows.append({k: target[k] for k in ('cell_id', 'family', 'item_id', 'layer', 'position', 'split')} |
                    {'activation_sha256': target_row['activation_sha256'], 'selections': [selected]})
    payload = ''.join(json.dumps(row) + '\n' for row in rows).encode()
    summary = {
        'diagnostic_only': True, 'cells': len(rows), 'missing_donors': 0, 'empty_donor_outputs': empty,
        'rule': 'First existing frozen E1 donor; no score, output or label search',
        'baseline_sha256': baseline_sha, 'manifest_sha256': manifest_sha,
        'controls_sha256': controls_sha, 'fresh_manifest_sha256': fresh_sha,
        'code_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'selection_sha256': sha256(payload).hexdigest(),
        'distinct_donors': len(donor_counts), 'donor_target_multiplicities': dict(sorted(donor_counts.items())),
        'limit': 'Prior/overlap diagnostic, not activation truth or independent donor evidence',
    }
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in [('selections.jsonl', payload), ('export.json', (json.dumps(summary, indent=2)+'\n').encode()),
                       ('conditions.json', b'[{"method":"matched_donor_capped_n1","n":1}]\n')]:
        path = output / name
        if path.exists() and path.read_bytes() != data:
            raise ValueError('Refuse changed diagnostic artifact')
        if not path.exists():
            path.write_bytes(data)
            path.chmod(0o444)
    print(json.dumps({k: v for k, v in summary.items() if k != 'donor_target_multiplicities'}), flush=True)


if __name__ == '__main__':
    main()
