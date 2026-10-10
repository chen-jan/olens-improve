"""Exact joint reconstruction scores for the immutable all-candidate diagnostic."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file
from transformers import AutoTokenizer
from olens_improve.ar_cache import vector_key
from olens_improve.reconstruction import RawVectorCache, Whitener, JointNNLS, ar_token_ids
from olens_improve.selection import parse_bullets, render_bullets, output_admissible, best_of_n


def indexed(path):
    body = Path(path).read_bytes()
    rows = [json.loads(line) for line in body.splitlines()]
    result = {r['cell_id']: r for r in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate source cell')
    return result, sha256(body).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for name in ('pool', 'export', 'parents', 'fresh-manifest', 'cache', 'checkpoint', 'whitener-directory', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--runtime', default='configs/runtime.json')
    a = p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Use allocated CPU resources')
    torch.set_num_threads(4)
    started = time.time()
    exports, export_sha = indexed(a.export)
    parents, parents_sha = indexed(a.parents)
    meta = json.loads(a.export.with_name('export.json').read_text())
    if export_sha != meta['selection_sha256'] or not meta['diagnostic_all_candidates']:
        raise ValueError('Not the immutable all-candidate export')
    pool_body = a.pool.read_bytes()
    pools = defaultdict(dict)
    for line in pool_body.splitlines():
        row = json.loads(line)
        if row['sample_index'] in pools[row['cell_id']]:
            raise ValueError('Duplicate source sample')
        pools[row['cell_id']][row['sample_index']] = row
    if pools.keys() != exports.keys() or parents.keys() != exports.keys():
        raise ValueError('Cohort coverage differs')
    fresh_body = a.fresh_manifest.read_bytes()
    fresh = {c['cell_id']: c for c in json.loads(fresh_body)['cells']}
    cache = RawVectorCache(str(a.cache))
    if sha256((a.checkpoint/'heads.pt').read_bytes()).hexdigest() != cache.contract['head_sha256']:
        raise ValueError('AR head changed')
    state = torch.load(a.checkpoint/'heads.pt', map_location='cpu', weights_only=True)
    tags = {int(l): state['tag_ids'][i].tolist() for i,l in enumerate(state['layers'])}
    runtime = json.loads(Path(a.runtime).read_text())
    tok = AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'], local_files_only=True)
    count = lambda s: len(tok(s, add_special_tokens=False)['input_ids'])
    allowed = output_admissible(count, 256)
    tensor_paths = {fresh[c]['activation_tensor_path'] for c in exports}
    if len(tensor_paths) != 1:
        raise ValueError('Require one completed fresh tensor')
    activations = load_file(next(iter(tensor_paths)))['resid']
    whiteners, whitened = {}, {}
    output = []
    for cid in sorted(exports):
        cell = fresh[cid]
        if cell['split'] != 'development' or set(pools[cid]) != set(range(32)):
            raise ValueError('Require complete frozen development N32')
        target = activations[cell['activation_row']]
        if sha256(target.numpy().tobytes()).hexdigest() != cell['activation_sha256']:
            raise ValueError('Activation changed')
        layer = cell['layer']
        if layer not in whiteners:
            whiteners[layer] = Whitener.load(str(a.whitener_directory/f'whitening_iolens_pooled_L{layer}.safetensors'))
            whitened[layer] = {}
        w = whiteners[layer]
        samples, vectors, atoms = [], {}, {}
        by_index = {s['source_sample_index']: s for s in exports[cid]['selections']}
        if len(by_index) != 32:
            raise ValueError('Export sample coverage differs')
        for index in range(32):
            row = pools[cid][index]
            if row['activation_sha256'] != cell['activation_sha256']:
                raise ValueError('Pool activation changed')
            sid = f"{row.get('global_pool_id', row['pool_id'])}:{cid}:{index}"
            sample = parse_bullets(row['text'], sid, index, token_count=count, max_output_tokens=256)
            if render_bullets(sample.bullets) != by_index[index]['text'] or list(sample.flags) != by_index[index]['parser_flags']:
                raise ValueError('Capping/parser differs from diagnostic export')
            samples.append(sample)
            for b in sample.bullets:
                _, ids = ar_token_ids(tok, b.text)
                if not ids:
                    raise ValueError('Empty cleaned scorer input')
                key = vector_key(cache.contract['sha256'], tags[layer], ids[:32])
                if key not in whitened[layer]:
                    v = w.whiten(cache.get(key).reshape(1,-1))[0]
                    whitened[layer][key] = v/(v.norm()+1e-9)
                vectors[b.phrase_id] = whitened[layer][key]
                atoms[b.phrase_id] = {'phrase_id': b.phrase_id, 'cache_key': key,
                    'original_token_count': len(ids), 'scored_token_count': min(len(ids),32), 'truncated': len(ids)>32}
        scorer = JointNNLS(w.whiten(target.reshape(1,-1))[0], vectors)
        winner = best_of_n(samples, 32, scorer.score, admissible=allowed)
        baseline = [s for s in parents[cid]['selections'] if s['method']=='best_n_exact' and s['n']==32]
        if len(baseline)!=1 or winner.text!=baseline[0]['text'] or list(winner.phrase_ids)!=baseline[0]['phrase_ids']:
            raise ValueError('A32 winner reproduction failed')
        if abs(scorer.score(winner.phrase_ids)-baseline[0]['fits']['exact']['fve']) > 1e-5:
            raise ValueError('A32 score reproduction failed')
        for sample in samples:
            ids = tuple(b.phrase_id for b in sample.bullets)
            fit = scorer.fit(ids)
            output.append({k: cell[k] for k in ('cell_id','family','item_id','layer','position','split')} |
                {'source_sample_index': sample.index, 'condition': by_index[sample.index]['method'],
                 'text': by_index[sample.index]['text'], 'text_sha256': sha256(by_index[sample.index]['text'].encode()).hexdigest(),
                 'parser_flags': list(sample.flags), 'a_eligible': not sample.parsing_uncertain and allowed(sample.bullets),
                 'activation_sha256': cell['activation_sha256'], 'fits': {'exact': fit.__dict__},
                 'fits_scope': 'exact_emitted_capped_bullets', 'token_count': count(render_bullets(sample.bullets)),
                 'bullet_count': len(ids), 'atoms': [atoms[k] for k in ids],
                 'all_candidate_selection_sha256': export_sha, 'whitener_sha256': w.artifact_sha256,
                 'vector_contract_sha256': cache.contract['sha256']})
    payload = ''.join(json.dumps(r)+'\n' for r in output).encode()
    spec = {'status':'complete','cells':len(exports),'candidates':len(output),'a32_winners_reproduced':len(exports),
            'selection_sha256':export_sha,'pool_sha256':sha256(pool_body).hexdigest(),'parents_sha256':parents_sha,
            'fresh_manifest_sha256':sha256(fresh_body).hexdigest(),'scores_sha256':sha256(payload).hexdigest(),
            'vector_contract':cache.contract,'seconds':time.time()-started,'cpu_threads':4,'model_forwards':0,
            'code_sha256':{str(q):sha256(q.read_bytes()).hexdigest() for q in
                [Path(__file__),Path('src/olens_improve/reconstruction.py'),Path('src/olens_improve/selection.py')]}}
    a.output.mkdir(parents=True,exist_ok=True)
    for name, body in [('scores.jsonl',payload),('export.json',(json.dumps(spec,indent=2)+'\n').encode())]:
        path=a.output/name
        if path.exists():
            raise ValueError('Immutable score export already exists')
        path.write_bytes(body);path.chmod(0o444)
    print(json.dumps(spec),flush=True)


if __name__=='__main__':
    main()
