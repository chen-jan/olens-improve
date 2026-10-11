"""Frozen full-bank N8 likelihood; first two existing matched controls only."""
import argparse
from collections import defaultdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import torch
from safetensors.torch import load_file
from olens_improve.ar_cache import digest
from olens_improve.contrastive import teacher_forced_likelihood_batch, teacher_forced_likelihood
from olens_improve.gpu_resume import file_sha256, recover_journal
from olens_improve.models import FrozenOLens, BASE_REVISION, PAIR_REVISION
from olens_improve.selection import parse_bullets, render_bullets
from expanded_gpu_service import atomic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Likelihood requires assigned GPU')
    cfg = json.loads(Path(args.config).read_text())
    torch.set_num_threads(4)
    started = time.time()
    output = Path(cfg['output'])
    output.mkdir(parents=True, exist_ok=True)
    lock = (output/'writer.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = json.loads(Path(cfg['sealed_manifest']).read_text())
    if manifest.get('status') not in ('sealed', 'frozen'):
        raise ValueError('Expansion manifest must be sealed before scoring')
    fresh_all = json.loads(Path(cfg['fresh_manifest']).read_text())['cells']
    fields = ('cell_id', 'family', 'item_id', 'group_id', 'layer', 'position', 'split',
              'read_position_kind', 'activation_tensor_path', 'activation_row', 'activation_sha256')
    fresh = {r['cell_id']: {k:r[k] for k in fields} for r in fresh_all}
    del fresh_all
    cohort = json.loads(Path(cfg['cells_manifest']).read_text())['cells']
    requested = sorted((r['cell_id'] for r in cohort),
                       key=lambda k:(fresh[k]['family'], fresh[k]['layer'], fresh[k]['item_id'], k))
    if len(set(requested)) != len(requested):
        raise ValueError('Duplicate requested cell')
    controls = json.loads(Path(cfg['controls_manifest']).read_text())['control_cell_ids_by_target']
    bank = {key:controls[key] for key in requested}
    for key, ids in bank.items():
        if len(ids) != 2 or len(set(ids)) != 2:
            raise ValueError('Exactly two distinct frozen controls required')
        target = fresh[key]
        for control_id in ids:
            control = fresh[control_id]
            if (control['split'] != 'development' or control['group_id'] == target['group_id']
                    or any(control[f] != target[f] for f in ('layer', 'family', 'read_position_kind'))):
                raise ValueError('Frozen control boundary failed')
    sources = cfg['input']
    approved_sources = {p['path']:p['sha256'] for stage in manifest['stages'].values() for p in stage['samples']}
    if set(sources) != set(approved_sources):
        raise ValueError('Likelihood inputs differ from sealed original pools')
    pins = {str(p):file_sha256(p) for p in [args.config, cfg['sealed_manifest'], cfg['fresh_manifest'],
            cfg['cells_manifest'], cfg['controls_manifest'], *sources,
            str(Path(cfg['adapter'])/'adapter_model.safetensors'),
            str(Path(cfg['adapter'])/'adapter_config.json'), __file__,
            'src/olens_improve/contrastive.py', 'src/olens_improve/models.py',
            'src/olens_improve/selection.py', 'src/olens_improve/gpu_resume.py']}
    if any(pins[path] != sha for path,sha in approved_sources.items()):
        raise ValueError('Original pooled samples differ from sealed hashes')
    if pins[cfg['fresh_manifest']] != manifest['fresh_manifest']['sha256']:
        raise ValueError('Fresh activation manifest differs from sealed hash')
    spec = dict(method='likelihood_true_minus_mean_two_controls', n=8,
                normalization='mean_candidate_token_logprob', include_eos=False,
                base_revision=BASE_REVISION, pair_revision=PAIR_REVISION, carrier='concepts_raw',
                injection_norm=16000, dtype='bfloat16', batch_size=cfg['batch_size'],
                checkpoint_cells=cfg['checkpoint_cells'], ordered_cell_ids=requested, controls=bank,
                source_sha256=pins, scope='exploratory full-bank expansion')
    spec_sha = digest(spec)
    spec_path = output/'spec.json'
    if spec_path.exists() and json.loads(spec_path.read_text()) != spec:
        raise ValueError('Cannot resume changed likelihood contract')
    atomic(spec_path, spec)
    done = recover_journal(output/'readouts.jsonl', spec_sha, set(requested))
    atomic(output/'status.json', dict(status='loading_inputs', completed_cells=len(done), expected_cells=len(requested),
                                    slurm_job_id=os.environ['SLURM_JOB_ID']))
    rows = defaultdict(dict)
    sample_counts = defaultdict(set)
    for path in sources:
        with Path(path).open('rb') as stream:
            for line in stream:
                if not line.endswith(b'\n'):
                    raise ValueError('Frozen candidate input has partial final line')
                envelope = json.loads(line)
                for row in envelope.get('records', [envelope]):
                    key = row['cell_id']
                    if key not in bank:
                        raise ValueError('Candidate source contains off-cohort cell')
                    index = row['sample_index']
                    if index in sample_counts[key]:
                        raise ValueError('Duplicate candidate sample')
                    sample_counts[key].add(index)
                    if index < 8 and key not in done:
                        if row['activation_sha256'] != fresh[key]['activation_sha256']:
                            raise ValueError('Candidate activation hash changed')
                        rows[key][index] = row
    if set(sample_counts) != set(requested) or any(ids != set(range(32)) for ids in sample_counts.values()):
        raise ValueError('Require exact completed original N32 pools for each cell')
    tensor_paths = {fresh[key]['activation_tensor_path'] for key in {*requested, *(k for ids in bank.values() for k in ids)}}
    tensors = {path:load_file(path)['resid'] for path in tensor_paths}
    verified = {}
    def activation(key):
        if key not in verified:
            cell = fresh[key]
            vector = tensors[cell['activation_tensor_path']][cell['activation_row']]
            if hashlib.sha256(vector.numpy().tobytes()).hexdigest() != cell['activation_sha256']:
                raise ValueError('Fresh activation hash changed')
            verified[key] = vector
        return verified[key]
    lens = FrozenOLens.load(cfg['base_snapshot'], cfg['adapter'])
    lens.merge()
    count = lambda text:len(lens.tokenizer(text, add_special_tokens=False)['input_ids'])
    def prepare(key):
        result = []
        for index in range(8):
            row = rows[key][index]
            sample_id = f"{row.get('global_pool_id', row.get('pool_id'))}:{key}:{index}"
            sample = parse_bullets(row['text'], sample_id, index, token_count=count, max_output_tokens=256)
            result.append((sample, render_bullets(sample.bullets)))
        return result
    pending = [k for k in requested if k not in done]
    if pending:
        first = next(k for k in pending if sum(not s.parsing_uncertain and bool(t) for s,t in prepare(k)) >= 2)
        texts = [t for s,t in prepare(first) if not s.parsing_uncertain and t][:2]
        fixture_texts = [texts[0], texts[1], texts[0]]
        fixture_ids = [first, first, bank[first][0]]
        layer = fresh[first]['layer']
        batched = teacher_forced_likelihood_batch(lens, [activation(k) for k in fixture_ids], layer, fixture_texts)
        singles = [teacher_forced_likelihood(lens, activation(k), layer, t) for k,t in zip(fixture_ids,fixture_texts)]
        deltas = [abs(a['average_log_likelihood']-b['average_log_likelihood']) for a,b in zip(batched,singles)]
        atomic(output/'batch_fixture.json', dict(cell_ids=fixture_ids, layer=layer, batched=batched, singleton=singles,
                absolute_mean_deltas=deltas, provisional_guard_nats_per_token=.05))
        if max(deltas) > .05:
            raise ValueError('Likelihood batching exceeds frozen numerical guard')
    scoring_start = time.time()
    initial_done = len(done)
    with (output/'readouts.jsonl').open('a') as stream:
        offset = 0
        while offset < len(pending):
            layer = fresh[pending[offset]]['layer']
            family = fresh[pending[offset]]['family']
            group = []
            while offset < len(pending) and len(group) < cfg['checkpoint_cells']:
                key = pending[offset]
                if fresh[key]['layer'] != layer or fresh[key]['family'] != family:
                    break
                group.append(key); offset += 1
            prepared = {k:prepare(k) for k in group}
            work = [(k,s.index,t,a) for k in group for s,t in prepared[k]
                    if not s.parsing_uncertain and t for a in [k,*bank[k]]]
            conditions = defaultdict(lambda:defaultdict(dict))
            batch_sizes = []
            for lo in range(0,len(work),cfg['batch_size']):
                batch = work[lo:lo+cfg['batch_size']]
                predictions = teacher_forced_likelihood_batch(lens,[activation(a) for _,_,_,a in batch],layer,[t for _,_,t,_ in batch])
                batch_sizes.append(len(batch))
                for (k,index,_,a),prediction in zip(batch,predictions):
                    conditions[k][index][a] = prediction
            events = []
            for key in group:
                cell = fresh[key]; scored = []
                for sample,text in prepared[key]:
                    if sample.index not in conditions[key]:
                        continue
                    values = conditions[key][sample.index]; true = values[key]
                    if len({v['candidate_token_count'] for v in values.values()}) != 1:
                        raise ValueError('True/control candidate token lengths differ')
                    mean = sum(values[a]['average_log_likelihood'] for a in bank[key])/2
                    total = sum(values[a]['sum_log_likelihood'] for a in bank[key])/2
                    scored.append(dict(sample_index=sample.index,text=text,phrase_ids=[b.phrase_id for b in sample.bullets],
                        score=true['average_log_likelihood']-mean,total_difference=true['sum_log_likelihood']-total,
                        token_count=true['candidate_token_count'],own_mean_log_likelihood=true['average_log_likelihood'],
                        control_mean_log_likelihood=mean,conditions=values,parser_flags=list(sample.flags)))
                winner = max(scored,key=lambda r:(r['score'],-r['sample_index'])) if scored else None
                baselines = {}
                for field in ('own_mean_log_likelihood','control_mean_log_likelihood'):
                    best = max(scored,key=lambda r:(r[field],-r['sample_index'])) if scored else None
                    baselines[field] = dict(text=best['text'] if best else '',sample_index=best['sample_index'] if best else None,
                                            score=best[field] if best else None)
                events.append(dict(cell_id=key, family=cell['family'], item_id=cell['item_id'], layer=layer,
                    position=cell['position'],split=cell['split'],method=spec['method'],n=8,text=winner['text'] if winner else '',
                    selected_sample_index=winner['sample_index'] if winner else None,
                    reason='selected' if winner else 'no_eligible_complete_candidate',candidates=scored,
                    likelihood_baselines=baselines,spec_sha256=spec_sha,controls=bank[key],
                    activation_sha256=cell['activation_sha256'],slurm_job_id=os.environ['SLURM_JOB_ID']))
            stream.write(''.join(json.dumps(e)+'\n' for e in events)); stream.flush(); os.fsync(stream.fileno())
            done.update(group)
            elapsed = time.time()-scoring_start
            status = dict(status='running',completed_cells=len(done),expected_cells=len(requested),
                          session_completed_cells=len(done)-initial_done,scoring_seconds=elapsed,
                          seconds_per_cell=elapsed/max(1,len(done)-initial_done),batch_sizes=batch_sizes,
                          last_family=family,last_layer=layer,slurm_job_id=os.environ['SLURM_JOB_ID'],last_update_unix=time.time())
            atomic(output/'status.json',status)
            print(json.dumps(status),flush=True)
    atomic(output/'status.json',dict(status='complete',completed_cells=len(done),expected_cells=len(requested),
        scoring_seconds=time.time()-scoring_start,total_seconds=time.time()-started,quality_status='unjudged',
        slurm_job_id=os.environ['SLURM_JOB_ID'],last_update_unix=time.time()))


if __name__ == '__main__':
    main()
