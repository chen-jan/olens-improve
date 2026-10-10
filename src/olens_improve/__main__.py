"""Portable local-artifact CLI. It never schedules jobs or downloads weights."""
import argparse
import json
from pathlib import Path

from .inference import (Artifacts, CandidatePool, file_sha, generate_pool, replay_select,
                        save_once, vector)
from .portable_cache import new_cache_path


def read_vector(path, key, row=None):
    from safetensors import safe_open
    with safe_open(str(path), framework='pt', device='cpu') as reader:
        if row is None:
            value = reader.get_tensor(key)
        else:
            value = reader.get_slice(key)[row]
    return vector(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('import-pool', 'generate', 'replay'):
        p = sub.add_parser(command)
        p.add_argument('--activation', type=Path, required=True)
        p.add_argument('--key', default='activation')
        p.add_argument('--row', type=int)
        p.add_argument('--pool', type=Path, required=True)
        if command == 'import-pool':
            p.add_argument('--records', type=Path, required=True)
            p.add_argument('--cell-id', required=True)
            p.add_argument('--layer', type=int, required=True)
        else:
            p.add_argument('--artifacts', type=Path, required=True,
                           help='JSON with local paths matching the Artifacts API; no cluster defaults')
            p.add_argument('--n', type=int, default=32 if command == 'generate' else None)
        if command == 'generate':
            p.add_argument('--layer', type=int, required=True)
            p.add_argument('--seed', type=int, default=0)
        if command == 'replay':
            p.add_argument('--method', choices=('raw_n1', 'capped_n1', 'best_n', 'prune_n1',
                            'prune_best', 'pool', 'specificity_mean', 'specificity_mean_prune'), default='best_n')
            p.add_argument('--cache-directory', type=Path)
            p.add_argument('--save-cache', type=Path, help='New immutable standalone raw AR cache; input caches remain read-only')
            p.add_argument('--encode-missing', action='store_true')
            p.add_argument('--maximum-loss', type=float, default=.005)
            p.add_argument('--controls', type=Path,
                           help='Explicit frozen bank JSON: layer, bank_sha256, controls[{id,path,key,row}]')
            p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'replay' and args.output.exists():
        raise FileExistsError('Replay output already exists; choose a new immutable output')
    if args.command == 'replay' and args.save_cache:
        new_cache_path(args.save_cache)
        if args.output.resolve() == args.save_cache.resolve() or args.save_cache.resolve() in args.output.resolve().parents:
            raise ValueError('Replay JSON must be outside the immutable saved-cache directory')
        if args.method in ('raw_n1','capped_n1'):
            raise ValueError('--save-cache requires an AR-scored method')
    activation = read_vector(args.activation, args.key, args.row)
    if args.command == 'import-pool':
        rows = [r for r in map(json.loads, args.records.read_text().splitlines()) if r['cell_id'] == args.cell_id]
        pool = CandidatePool.from_records(rows, activation, args.layer, source_sha256=file_sha(args.records))
        save_once(args.pool, pool.as_dict())
        print(json.dumps({'pool': str(args.pool), 'samples': len(rows), 'new_generations': 0}))
        return
    artifacts = Artifacts(**json.loads(args.artifacts.read_text()))
    if args.command == 'generate':
        pool = generate_pool(artifacts, activation, args.layer, args.pool, n=args.n, seed=args.seed)
        print(json.dumps({'pool': str(args.pool), 'samples': len(pool.records)}))
        return
    pool = CandidatePool.load(args.pool)
    controls, provenance = None, None
    if args.controls:
        declared = json.loads(args.controls.read_text()); rows = declared['controls']
        if len({r['id'] for r in rows}) != len(rows) or not rows:
            raise ValueError('Frozen control bank must have distinct nonempty control IDs')
        controls = {r['id']: read_vector(r['path'], r.get('key', 'activation'), r.get('row')) for r in rows}
        provenance = {'layer': declared['layer'], 'bank_sha256': declared['bank_sha256'],
                      'manifest_sha256': file_sha(args.controls), 'controls': rows,
                      'matching_policy': declared.get('matching_policy', 'Caller must validate matched calibration controls.')}
    result = replay_select(artifacts, pool, activation, method=args.method, n=args.n,
               cache_directory=args.cache_directory, encode_missing=args.encode_missing,
               controls=controls, control_provenance=provenance, maximum_loss=args.maximum_loss,
               save_cache_directory=args.save_cache)
    result['replay_inputs'] = {'pool_sha256': file_sha(args.pool), 'activation_file_sha256': file_sha(args.activation),
                              'activation_key': args.key, 'activation_row': args.row,
                              'artifacts_config_sha256': file_sha(args.artifacts)}
    save_once(args.output, result)
    print(json.dumps({'output': str(args.output), 'status': result['status']}))


if __name__ == '__main__': main()
