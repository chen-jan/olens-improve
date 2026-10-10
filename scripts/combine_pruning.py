"""Cached D/E1/F parents followed by sequential exact-FVE pruning; no model calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import time
import torch
from safetensors.torch import load_file
from transformers import AutoTokenizer
from olens_improve.ar_cache import digest
from olens_improve.reconstruction import JointNNLS, RawVectorCache, Whitener
from olens_improve.selection import Bullet, prune_leave_one_out, render_bullets


def read_rows(path):
    body = path.read_bytes()
    rows = [json.loads(line) for line in body.splitlines()]
    indexed = {r['cell_id']: r for r in rows}
    if len(rows) != len(indexed):
        raise ValueError('Duplicate completed cell')
    return indexed, hashlib.sha256(body).hexdigest()

def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    for field in ('selectors', 'manifest', 'fresh-manifest', 'production-cache',
                  'whitener-directory', 'output'):
        parser.add_argument('--' + field, type=Path, required=True)
    parser.add_argument('--edits', type=Path)
    parser.add_argument('--editing-cache', type=Path)
    parser.add_argument('--parent-method', action='append', choices=['pooled_greedy_swap','best_n_specificity_mean','editing_round2'],
                        help='Restrict parents; omitted preserves the original D/E1/F behavior')
    parser.add_argument('--runtime', type=Path, default=Path('configs/runtime.json'))
    args=parser.parse_args(argv)
    if (args.edits is None)!=(args.editing_cache is None):
        parser.error('--edits and --editing-cache must be supplied together')
    if args.parent_method and (len(set(args.parent_method))!=len(args.parent_method) or
                              ('editing_round2' in args.parent_method and args.edits is None)):
        parser.error('Parent methods must be unique and editing requires both editing inputs')
    return args

def parent_methods(with_edits):
    methods=['pooled_greedy_swap','best_n_specificity_mean']
    return methods+['editing_round2'] if with_edits else methods

def parent_records(selector_row,edit_row=None,methods=None):
    methods=parent_methods(edit_row is not None) if methods is None else methods
    parents=[]
    for method in [method for method in methods if method!='editing_round2']:
        matched=[s for s in selector_row['selections'] if s['method']==method and s['n']==32]
        if len(matched)!=1:raise ValueError('Missing or duplicate parent method')
        parent=matched[0]
        parents.append((method,parent['text'],parent['atoms'],parent['fits']['exact']['fve']))
    if 'editing_round2' in methods:
        if edit_row is None:raise ValueError('Editing parent requires editing history')
        parent=edit_row['best']
        parents.append(('editing_round2',parent['text'],parent['atom_metadata'],parent['exact_fve']))
    return parents

def optional_edit_provenance(edit_sha):
    return {} if edit_sha is None else {'editing_history_sha256':edit_sha}


def main():
    args = parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Use allocated CPU resources')
    torch.set_num_threads(4)
    started = time.time()
    selectors, selector_sha = read_rows(args.selectors)
    edits, edit_sha = read_rows(args.edits) if args.edits is not None else (None,None)
    manifest_bytes = args.manifest.read_bytes()
    cohort = {c['cell_id']: c for c in json.loads(manifest_bytes)['cells']}
    if set(cohort) != set(selectors) or (edits is not None and set(cohort) != set(edits)):
        raise ValueError('All parents must cover the exact same frozen cohort')
    fresh_bytes = args.fresh_manifest.read_bytes()
    fresh = {c['cell_id']: c for c in json.loads(fresh_bytes)['cells']}
    if any(fresh[cid]['split'] != 'development' for cid in cohort):
        raise ValueError('Development only')
    production = RawVectorCache(str(args.production_cache))
    editing = RawVectorCache(str(args.editing_cache)) if args.editing_cache is not None else None
    if editing is not None and production.contract != editing.contract:
        raise ValueError('Parent vector contracts differ')
    runtime = json.loads(args.runtime.read_text())
    tokenizer = AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'], local_files_only=True)
    count = lambda text: len(tokenizer(text, add_special_tokens=False)['input_ids'])
    spec = {'selector_sha256': selector_sha, **optional_edit_provenance(edit_sha),
            'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'fresh_manifest_sha256': hashlib.sha256(fresh_bytes).hexdigest(),
            'parent_methods': args.parent_method or parent_methods(edits is not None),
            'thresholds': [.001, .005], 'pruning_objective': 'exact_joint_nnls_fve',
            'random_control': 'Seeded deletion retaining exactly the pruned bullet count',
            'vector_contract': production.contract, 'new_model_calls': 0,
            'code_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            [Path(__file__), Path('src/olens_improve/selection.py'),
                             Path('src/olens_improve/reconstruction.py')]}}
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    config = output / 'spec.json'
    if config.exists() and json.loads(config.read_text()) != spec:
        raise ValueError('Resume contract changed')
    config.write_text(json.dumps(spec, indent=2) + '\n')
    done = {}
    path = output / 'selections.jsonl'
    if path.exists():
        done, _ = read_rows(path)
        if not set(done).issubset(cohort) or any(r['spec_sha256'] != digest(spec) for r in done.values()):
            raise ValueError('Incompatible completed events')
    tensor_paths = {fresh[cid]['activation_tensor_path'] for cid in cohort}
    if len(tensor_paths) != 1:
        raise ValueError('Expected one fresh activation tensor')
    activations = load_file(next(iter(tensor_paths)))['resid']
    whiteners = {}
    conditions = []
    with path.open('a') as stream:
        for cid in sorted(cohort):
            if cid in done:
                continue
            cell = fresh[cid]
            layer = cell['layer']
            target = activations[cell['activation_row']]
            if hashlib.sha256(target.numpy().tobytes()).hexdigest() != cell['activation_sha256']:
                raise ValueError('Target hash changed')
            if layer not in whiteners:
                whiteners[layer] = Whitener.load(str(args.whitener_directory /
                    f'whitening_iolens_pooled_L{layer}.safetensors'))
            parents = parent_records(selectors[cid],edits[cid] if edits is not None else None,spec['parent_methods'])
            selections = []
            for method, parent_text, atoms, recorded_fve in parents:
                raw = {}
                bullets = []
                for index, atom in enumerate(atoms):
                    phrase_id = atom.get('phrase_id', atom.get('source_phrase_id'))
                    key = atom['cache_key']
                    if key in production.index:raw[phrase_id]=production.get(key)
                    elif editing is not None:raw[phrase_id]=editing.get(key)
                    else:raise ValueError('Parent vector missing from production cache; no editing cache supplied')
                    bullets.append(Bullet(phrase_id, atom['text'], f'{cid}:{method}', index))
                score = JointNNLS.from_raw(target, raw, whiteners[layer])
                parent_ids = tuple(b.phrase_id for b in bullets)
                if abs(score.score(parent_ids) - recorded_fve) > 1e-5:
                    raise ValueError('Cached parent fit no longer agrees')
                def record(name, retained, trace, extra):
                    ids = tuple(b.phrase_id for b in retained)
                    text = parent_text if ids == parent_ids else render_bullets(retained)
                    if len(ids) > 4 or count(text) > 256:
                        raise ValueError('Output violates final cap')
                    selections.append({'method': name, 'n': 32, 'text': text, 'phrase_ids': list(ids),
                        'token_count': count(text), 'bullet_count': len(ids), 'trace': list(trace),
                        'fits': {'exact': score.fit(ids).__dict__}, 'parent_method': method,
                        'parent_text': parent_text, 'parent_phrase_ids': list(parent_ids),
                        'parent_fve': recorded_fve, 'atoms': [a for a in atoms if a.get('phrase_id', a.get('source_phrase_id')) in ids],
                        'extra': extra})
                record(method, tuple(bullets), (), {'component': 'unchanged parent'})
                for loss in spec['thresholds']:
                    pruned = prune_leave_one_out(bullets, score.score, maximum_loss=loss)
                    record(f'{method}_then_prune_{loss:g}', pruned.bullets, pruned.trace,
                           {'maximum_loss_per_sequential_deletion': loss})
                    seed = int(digest(['combination_random_delete_v1', cid, method, loss])[:16], 16)
                    keep = set(random.Random(seed).sample(range(len(bullets)), len(pruned.bullets)))
                    control = tuple(b for index, b in enumerate(bullets) if index in keep)
                    record(f'{method}_random_delete_matched_{loss:g}', control, (),
                           {'seed': seed, 'matched_retained_bullets': len(pruned.bullets)})
            if not conditions:
                conditions = [{'method': s['method'], 'n': s['n']} for s in selections]
            event = {k: cell[k] for k in ('cell_id', 'family', 'item_id', 'layer', 'position', 'split')}
            event.update({'selections': selections, 'spec_sha256': digest(spec),
                          'activation_sha256': cell['activation_sha256']})
            stream.write(json.dumps(event) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
            print(json.dumps({'completed_cell': cid}), flush=True)
    if not conditions and done:
        conditions = [{'method': s['method'], 'n': s['n']} for s in next(iter(done.values()))['selections']]
    (output / 'conditions.json').write_text(json.dumps(conditions, indent=2) + '\n')
    (output / 'status.json').write_text(json.dumps({'status': 'complete', 'cells': len(cohort),
        'conditions': len(conditions), 'seconds': time.time() - started,
        'selection_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'quality_status': 'unjudged'}) + '\n')


if __name__ == '__main__':
    main()
