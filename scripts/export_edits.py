"""Export frozen round1/round2 final choices; no generation or rescoring."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for field in ('round1', 'round2', 'manifest', 'output'):
        parser.add_argument('--' + field, type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    cells = {c['cell_id']: c for c in json.loads(manifest_bytes)['cells']}
    if any(c['split'] != 'development' for c in cells.values()):
        raise ValueError('Development export only')
    rounds = []
    sources = []
    for number, path in enumerate((args.round1, args.round2), 1):
        body = path.read_bytes()
        source = [json.loads(line) for line in body.splitlines()]
        indexed = {r['cell_id']: r for r in source}
        if len(indexed) != len(source) or set(indexed) != set(cells):
            raise ValueError('Each round must cover exactly the frozen cell cohort')
        if any(r['round'] != number or r['split'] != 'development' for r in source):
            raise ValueError('Wrong round or split')
        sources.append({'path': str(path), 'sha256': hashlib.sha256(body).hexdigest()})
        rounds.append(indexed)
    rows = []
    for cid, cell in cells.items():
        initial = {c['candidate_id']: c['text'] for c in rounds[0][cid]['candidates']}
        final = {c['candidate_id']: c['text'] for c in rounds[1][cid]['candidates']}
        if not all(final.get(k) == v for k, v in initial.items()):
            raise ValueError('Round2 failed to retain full round1 history verbatim')
        selections = []
        for number, indexed in enumerate(rounds, 1):
            event = indexed[cid]
            if any(event[k] != cell[k] for k in ('family', 'item_id', 'layer', 'position')):
                raise ValueError('Cell metadata changed')
            best = event['best']
            if best['bullet_count'] > 4 or best['token_count'] > 256:
                raise ValueError('Selected output exceeds the frozen cap')
            if not any(c['candidate_id'] == best['candidate_id'] and c['text'] == best['text']
                       for c in event['candidates']):
                raise ValueError('Final text not in the scored candidate union')
            selections.append({'method': f'editing_round{number}', 'n': 32,
                               'text': best['text'], 'candidate_id': best['candidate_id'],
                               'origin': best['origin'], 'token_count': best['token_count'],
                               'bullet_count': best['bullet_count'], 'fits': {
                                   'scipy_exact': best['exact_fve'], 'released80': best['released80_fve']},
                               'scoring_spec_sha256': event['spec_sha256']})
        rows.append({k: cell[k] for k in ('cell_id', 'family', 'item_id', 'layer', 'position', 'split')} |
                    {'selections': selections})
    payload = ''.join(json.dumps(r) + '\n' for r in rows)
    metadata = {'sources': sources, 'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                'export_sha256': hashlib.sha256(payload.encode()).hexdigest(), 'cells': len(rows),
                'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'new_model_calls': 0, 'new_O_lens_samples': 0,
                'n_contract': 'Shared original N32 pool; editor proposals separately counted'}
    args.output.mkdir(parents=True, exist_ok=True)
    for filename, text in [('selections.jsonl', payload),
                           ('conditions.json', json.dumps([{'method': f'editing_round{i}', 'n': 32}
                                                           for i in (1, 2)], indent=2) + '\n'),
                           ('export.json', json.dumps(metadata, indent=2) + '\n')]:
        path = args.output / filename
        if path.exists() and path.read_text() != text:
            raise ValueError('Refusing to overwrite a different export')
        if not path.exists():
            path.write_text(text)
            path.chmod(0o444)
    print(json.dumps(metadata), flush=True)


if __name__ == '__main__':
    main()
