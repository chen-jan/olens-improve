"""Frozen exact whole-bullet support prior plus D16 pooling, using cached vectors."""
import argparse
from collections import defaultdict
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file
from transformers import AutoTokenizer
from olens_improve.ar_cache import digest, vector_key
from olens_improve.reconstruction import RawVectorCache, Whitener, JointNNLS, ar_token_ids
from olens_improve.selection import Selection, parse_bullets, greedy_pool, output_admissible


def normalize(text):
    return ' '.join(text.split())


def read_index(path):
    body = path.read_bytes()
    rows = [json.loads(line) for line in body.splitlines()]
    indexed = {r['cell_id']: r for r in rows}
    if len(rows) != len(indexed):
        raise ValueError('Duplicate cell in immutable source')
    return indexed, hashlib.sha256(body).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for field in ('pool', 'support', 'parents', 'manifest', 'fresh-manifest', 'cache',
                  'checkpoint', 'whitener-directory', 'output'):
        parser.add_argument('--' + field, type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=Path('configs/runtime.json'))
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Use allocated CPU resources')
    torch.set_num_threads(4)
    started = time.time()
    support, support_sha = read_index(args.support)
    parents, parent_sha = read_index(args.parents)
    manifest_bytes = args.manifest.read_bytes()
    cohort = {c['cell_id']: c for c in json.loads(manifest_bytes)['cells']}
    if set(cohort) != set(support) or set(cohort) != set(parents):
        raise ValueError('Inputs must cover the exact same frozen cohort')
    fresh_bytes = args.fresh_manifest.read_bytes()
    fresh = {c['cell_id']: c for c in json.loads(fresh_bytes)['cells']}
    if any(fresh[cid]['split'] != 'development' for cid in cohort):
        raise ValueError('Development only')
    pool_bytes = args.pool.read_bytes()
    pools = defaultdict(dict)
    for line in pool_bytes.splitlines():
        r = json.loads(line)
        if r['cell_id'] not in cohort:
            raise ValueError('Off-cohort pool cell')
        index = r['sample_index']
        if index in pools[r['cell_id']]:
            raise ValueError('Duplicate pool sample')
        pools[r['cell_id']][index] = r
    if set(pools) != set(cohort) or any(set(v) != set(range(32)) for v in pools.values()):
        raise ValueError('Require immutable complete shared N32 pools, using first16 only')
    support_manifest = json.loads(args.support.with_name('manifest.json').read_text())
    if support_manifest['n'] != 16 or support_manifest['lambda'] != [0, .05, .20]:
        raise ValueError('Frozen support parameters changed')
    if support_sha != support_manifest['support_sha256'] or hashlib.sha256(pool_bytes).hexdigest() != support_manifest['records_sha256']:
        raise ValueError('Support artifact does not bind this exact pool')
    cache = RawVectorCache(str(args.cache))
    if hashlib.sha256((args.checkpoint / 'heads.pt').read_bytes()).hexdigest() != cache.contract['head_sha256']:
        raise ValueError('Prompt-tag head changed')
    state = torch.load(args.checkpoint / 'heads.pt', map_location='cpu', weights_only=True)
    tags = {int(layer): state['tag_ids'][i].tolist() for i, layer in enumerate(state['layers'])}
    runtime = json.loads(args.runtime.read_text())
    tokenizer = AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'], local_files_only=True)
    count = lambda text: len(tokenizer(text, add_special_tokens=False)['input_ids'])
    admissible = output_admissible(count, 256)
    spec = {'support_sha256': support_sha, 'parents_sha256': parent_sha,
            'pool_sha256': hashlib.sha256(pool_bytes).hexdigest(),
            'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'fresh_manifest_sha256': hashlib.sha256(fresh_bytes).hexdigest(),
            'lambda': [0., .05, .20], 'n': 16, 'support_manifest': support_manifest,
            'vector_contract': cache.contract, 'new_model_calls': 0,
            'code_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            [Path(__file__), Path('src/olens_improve/selection.py'),
                             Path('src/olens_improve/reconstruction.py')]}}
    args.output.mkdir(parents=True, exist_ok=True)
    config = args.output / 'spec.json'
    if config.exists() and json.loads(config.read_text()) != spec:
        raise ValueError('Resume configuration changed')
    config.write_text(json.dumps(spec, indent=2) + '\n')
    path = args.output / 'selections.jsonl'
    done = {}
    if path.exists():
        done, _ = read_index(path)
        if not set(done).issubset(cohort) or any(r['spec_sha256'] != digest(spec) for r in done.values()):
            raise ValueError('Incompatible completed events')
    tensor_paths = {fresh[cid]['activation_tensor_path'] for cid in cohort}
    if len(tensor_paths) != 1:
        raise ValueError('Expected one fresh target tensor')
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
                raise ValueError('Target changed')
            samples, representatives, votes, first = [], {}, defaultdict(set), {}
            for index in range(16):
                row = pools[cid][index]
                if row['activation_sha256'] != cell['activation_sha256']:
                    raise ValueError('Pool activation changed')
                sid = f"{row.get('global_pool_id', row['pool_id'])}:{cid}:{index}"
                sample = parse_bullets(row['text'], sid, index, token_count=count, max_output_tokens=256)
                samples.append(sample)
                if sample.parsing_uncertain:
                    continue
                for bullet in sample.bullets:
                    representatives.setdefault(bullet.text, bullet)
                    key = normalize(bullet.text)
                    votes[key].add(index)
                    first.setdefault(key, bullet)
            artifact = {g['normalized_text']: g for g in support[cid]['exact_groups']}
            if set(votes) != set(artifact) or any(sorted(v) != artifact[k]['sample_indexes'] for k, v in votes.items()):
                raise ValueError('Independently recomputed distinct support differs')
            bullets = list(representatives.values())
            complete = [replace(s, bullets=tuple(dict((representatives[b.text].phrase_id, representatives[b.text])
                        for b in s.bullets).values())) for s in samples if not s.parsing_uncertain]
            raw = {}
            atoms = {}
            for bullet in bullets:
                cleaned, ids = ar_token_ids(tokenizer, bullet.text)
                key = vector_key(cache.contract['sha256'], tags[layer], ids[:32])
                raw[bullet.phrase_id] = cache.get(key)
                atoms[bullet.phrase_id] = {'phrase_id': bullet.phrase_id, 'text': bullet.text,
                    'cache_key': key, 'scored_token_ids': ids[:32], 'truncated': len(ids) > 32,
                    'normalized_support_key': normalize(bullet.text),
                    'support': len(votes[normalize(bullet.text)]),
                    'sample_indexes': sorted(votes[normalize(bullet.text)])}
            if layer not in whiteners:
                whiteners[layer] = Whitener.load(str(args.whitener_directory /
                    f'whitening_iolens_pooled_L{layer}.safetensors'))
            exact = JointNNLS.from_raw(target, raw, whiteners[layer])
            prior = {b.phrase_id: normalize(b.text) for b in bullets}
            selections = []
            for coefficient in spec['lambda']:
                def objective(ids):
                    keys = {prior[k] for k in ids}
                    return exact.score(ids) + coefficient / 4 * sum((len(votes[k]) - 1) / 15 for k in keys)
                selected = greedy_pool(bullets, objective, admissible=admissible, swap_passes=1, complete_samples=complete)
                if coefficient == 0:
                    baseline = [s for s in parents[cid]['selections'] if s['method'] == 'pooled_greedy_swap' and s['n'] == 16]
                    if len(baseline) != 1 or selected.text != baseline[0]['text'] or list(selected.phrase_ids) != baseline[0]['phrase_ids']:
                        raise ValueError('Lambda0 failed exact D16 selection reproduction')
                    if abs(exact.score(selected.phrase_ids) - baseline[0]['fits']['exact']['fve']) > 1e-5:
                        raise ValueError('Lambda0 parent fit changed')
                selections.append({'method': f'pooling_exact_support_lambda{coefficient:g}', 'n': 16,
                    'text': selected.text, 'phrase_ids': list(selected.phrase_ids), 'trace': list(selected.trace),
                    'combined_objective': objective(selected.phrase_ids), 'lambda': coefficient,
                    'fits': {'exact': exact.fit(selected.phrase_ids).__dict__},
                    'token_count': count(selected.text), 'bullet_count': len(selected.bullets),
                    'atoms': [atoms[k] for k in selected.phrase_ids]})
            # Insertion order follows original sample index, then bullet appearance.
            appearance = {b.phrase_id: i for i, b in enumerate(first.values())}
            ranked = sorted(first.values(), key=lambda b: (-len(votes[normalize(b.text)]), appearance[b.phrase_id]))
            retained = []
            for bullet in ranked:
                if len(retained) < 4 and admissible(tuple(retained + [bullet])):
                    retained.append(bullet)
            selected = Selection('exact_support_only', tuple(retained), None)
            selections.append({'method': 'exact_support_only', 'n': 16, 'text': selected.text,
                'phrase_ids': list(selected.phrase_ids), 'token_count': count(selected.text),
                'bullet_count': len(retained), 'fits': {'exact': exact.fit(selected.phrase_ids).__dict__},
                'atoms': [atoms[k] for k in selected.phrase_ids], 'trace': []})
            if not conditions:
                conditions = [{'method': s['method'], 'n': s['n']} for s in selections]
            event = {k: cell[k] for k in ('cell_id', 'family', 'item_id', 'layer', 'position', 'split')}
            event.update({'selections': selections, 'spec_sha256': digest(spec), 'activation_sha256': cell['activation_sha256']})
            stream.write(json.dumps(event) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
            print(json.dumps({'completed_cell': cid}), flush=True)
    if not conditions and done:
        conditions = [{'method': s['method'], 'n': s['n']} for s in next(iter(done.values()))['selections']]
    (args.output / 'conditions.json').write_text(json.dumps(conditions, indent=2) + '\n')
    (args.output / 'status.json').write_text(json.dumps({'status': 'complete', 'cells': len(cohort),
        'conditions': len(conditions), 'seconds': time.time() - started,
        'selections_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'quality_status': 'unjudged'}) + '\n')


if __name__ == '__main__':
    main()
