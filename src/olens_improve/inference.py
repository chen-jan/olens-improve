"""Local, vector-first frozen reader and immutable candidate-pool replay.

No cluster scheduler, benchmark answers or paid helper is part of this entrypoint.
All operating profiles are experimental until their independent evaluation ends.
"""
from dataclasses import dataclass
from hashlib import sha256
import gc
import json
from pathlib import Path
from typing import Any

from .models import BASE_REVISION, PAIR_REVISION, SUPPORTED_LAYERS, FrozenOLens
from .reconstruction import FrozenAR, RawVectorCache, Whitener, JointNNLS, ar_token_ids
from .ar_cache import vector_key
from .selection import (Selection, parse_bullets, best_of_n, greedy_pool,
                        prune_leave_one_out, output_admissible)
from .contrastive import control_specificity


def file_sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def vector(value):
    import torch
    result = torch.as_tensor(value).detach().cpu().float()
    if result.shape == (1, 5120): result = result[0]
    if result.shape != (5120,) or not torch.isfinite(result).all() or float(result.norm()) <= 1e-8:
        raise ValueError('Expected one finite, nonzero activation of width 5120')
    return result.contiguous()


def activation_hash(value):
    return sha256(vector(value).numpy().tobytes()).hexdigest()


def save_once(path, payload):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write((json.dumps(payload, indent=2)+'\n').encode())
    path.chmod(0o444)


@dataclass(frozen=True)
class Artifacts:
    base_path: str
    olens_adapter: str | None = None
    ar_checkpoint: str | None = None
    whitener_directory: str | None = None
    device: str = 'cuda'
    base_revision: str = BASE_REVISION
    pair_revision: str = PAIR_REVISION

    def __post_init__(self):
        if self.base_revision != BASE_REVISION or self.pair_revision != PAIR_REVISION:
            raise ValueError('This reader supports only the documented frozen model/pair revisions')


@dataclass(frozen=True)
class CandidatePool:
    layer: int
    activation_sha256: str
    records: tuple[dict, ...]
    provenance: dict

    def __post_init__(self):
        if self.layer not in SUPPORTED_LAYERS or not 1 <= len(self.records) <= 32:
            raise ValueError('Supported layer and 1..32 saved source samples required')
        if len(self.activation_sha256) != 64 or any(c not in '0123456789abcdef' for c in self.activation_sha256):
            raise ValueError('Activation hash required')
        if self.provenance.get('base_revision') != BASE_REVISION or self.provenance.get('pair_revision') != PAIR_REVISION:
            raise ValueError('Missing/mismatched frozen model provenance')
        if [r['sample_index'] for r in self.records] != list(range(len(self.records))):
            raise ValueError('Saved pool must contain distinct contiguous sample indexes starting at zero')
        for row in self.records:
            if not isinstance(row.get('text'), str) or row.get('activation_sha256') != self.activation_sha256:
                raise ValueError('Sample text/activation provenance differs')
            if row.get('layer', self.layer) != self.layer:
                raise ValueError('Mixed layers in one activation pool')
            if row.get('base_revision', BASE_REVISION) != BASE_REVISION or row.get('adapter_revision', PAIR_REVISION) != PAIR_REVISION:
                raise ValueError('Mixed model revisions in saved pool')

    def as_dict(self):
        return {'schema_version': 1, 'layer': self.layer, 'activation_sha256': self.activation_sha256,
                'records': list(self.records), 'provenance': self.provenance}

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if data.get('schema_version') != 1: raise ValueError('Unknown pool schema')
        return cls(data['layer'], data['activation_sha256'], tuple(data['records']), data['provenance'])

    @classmethod
    def from_records(cls, records, activation, layer, *, source_sha256):
        ordered = sorted(records, key=lambda r: r['sample_index'])
        # Existing science pools must carry exact per-record frozen revisions.
        if any(r.get('base_revision') != BASE_REVISION or r.get('adapter_revision') != PAIR_REVISION for r in ordered):
            raise ValueError('Imported records lack verified frozen revision fields')
        return cls(layer, activation_hash(activation), tuple(ordered), {
            'base_revision': BASE_REVISION, 'pair_revision': PAIR_REVISION,
            'source_sha256': source_sha256, 'kind': 'replay_of_existing_records',
            'new_generations': 0, 'sample_provenance': 'Every original record field retained.'})


def release_reader(reader):
    import torch
    for name in ('model', 'backbone', 'head', 'tags', 'probe_ids', 'on_logits'):
        if hasattr(reader, name): setattr(reader, name, None)
    gc.collect()
    if torch.cuda.is_available(): torch.cuda.empty_cache()


def generate_pool(artifacts, activation, layer, output, *, n=32, seed=0):
    """Write one immutable pool. Existing pool/claim files prevent silent resampling."""
    value = vector(activation)
    if layer not in SUPPORTED_LAYERS or not 1 <= n <= 32:
        raise ValueError('Off-contract layer/sample budget')
    if not artifacts.olens_adapter: raise ValueError('Local O-lens adapter path required')
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists(): raise FileExistsError('Pool already exists; replay it without resampling')
    claim = output.with_suffix(output.suffix+'.generation-claim')
    # An interrupted attempt remains visible and needs explicit reconciliation.
    with claim.open('x') as stream:
        stream.write(json.dumps({'activation_sha256': activation_hash(value), 'layer': layer, 'n': n, 'seed': seed}))
    lens = None
    try:
        lens = FrozenOLens.load(artifacts.base_path, artifacts.olens_adapter, artifacts.device)
        texts, metadata = lens.sample(value, layer, n=n, seed=seed)
        ah = activation_hash(value)
        rows = tuple({'sample_index': i, 'text': text, 'layer': layer, 'activation_sha256': ah,
                      'base_revision': BASE_REVISION, 'adapter_revision': PAIR_REVISION,
                      'seed': seed, 'sampling_metadata_index': i} for i, text in enumerate(texts))
        pool = CandidatePool(layer, ah, rows, {'base_revision': BASE_REVISION, 'pair_revision': PAIR_REVISION,
            'sampling': metadata, 'kind': 'new_single_activation_pool',
            'adapter_sha256': file_sha(Path(artifacts.olens_adapter)/'adapter_model.safetensors'),
            'base_config_sha256': file_sha(Path(artifacts.base_path)/'config.json'),
            'base_weight_provenance': 'Revision declared by local-artifact config; full base weights are not rehashed.'})
        save_once(output, pool.as_dict()); claim.unlink()
        return pool
    finally:
        if lens is not None: release_reader(lens)


def token_counter(artifacts):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(artifacts.base_path, local_files_only=True)
    return tokenizer, lambda text: len(tokenizer(text, add_special_tokens=False)['input_ids'])


def samples_for_pool(pool, count, n=None):
    n = len(pool.records) if n is None else n
    if not 1 <= n <= len(pool.records): raise ValueError('Prefix exceeds the persisted pool; no extra sampling')
    samples = []
    for row in pool.records[:n]:
        source_pool = row.get('global_pool_id', row.get('pool_id', pool.activation_sha256))
        source_cell = row.get('cell_id', f'L{pool.layer}:{pool.activation_sha256}')
        samples.append(parse_bullets(row['text'], f'{source_pool}:{source_cell}:{row["sample_index"]}',
                                    row['sample_index'], token_count=count, max_output_tokens=256))
    return samples


def select_scored_pool(pool, samples, count, *, method, scorer=None, controls=None, maximum_loss=.005):
    """Reuse the existing parser and selectors; unavailable input is not zero evidence."""
    allowed = output_admissible(count, 256); controls = controls or {}
    base = Selection(method, samples[0].bullets, None)
    if method == 'raw_n1':
        return {'status': 'complete', 'text': pool.records[0]['text'], 'fits': None,
                'fits_scope': 'unavailable_for_unmodified_raw_text', 'method': method,
                'n': 1, 'token_count': count(pool.records[0]['text']),
                'reason': 'raw_released_baseline', 'profile_status': 'experimental'}
    if method == 'capped_n1': selected = base
    else:
        if scorer is None: return {'status': 'unavailable', 'method': method, 'text': None, 'reason': 'AR_and_matching_whitening_required'}
        scoreable = lambda bs: allowed(bs) and all(b.phrase_id in scorer.vectors for b in bs)
        if method.startswith('specificity') and not controls:
            return {'status': 'unavailable', 'method': method, 'text': None, 'reason': 'frozen_matched_control_bank_required'}
        if method in ('best_n', 'prune_best'):
            selected = best_of_n(samples, len(samples), scorer.score, admissible=scoreable)
            if method == 'prune_best': selected = prune_leave_one_out(selected.bullets, scorer.score, maximum_loss=maximum_loss)
        elif method == 'prune_n1':
            selected = (prune_leave_one_out(base.bullets, scorer.score, maximum_loss=maximum_loss)
                        if scoreable(base.bullets) else Selection(method, base.bullets, None, reason='unavailable_parent_AR'))
        elif method == 'pool':
            from dataclasses import replace
            reps = {}
            for sample in samples:
                if not sample.parsing_uncertain:
                    for b in sample.bullets:
                        if b.phrase_id in scorer.vectors: reps.setdefault(b.text, b)
            complete = [replace(s, bullets=tuple(dict((reps[b.text].phrase_id, reps[b.text]) for b in s.bullets).values()))
                        for s in samples if not s.parsing_uncertain and scoreable(s.bullets)]
            selected = greedy_pool(list(reps.values()), scorer.score, admissible=allowed,
                                   swap_passes=1, complete_samples=complete)
        elif method in ('specificity_mean', 'specificity_mean_prune'):
            def objective(ids):
                return control_specificity(scorer.score(ids), {k: s.score(ids) for k, s in controls.items()}, aggregation='mean')['score']
            selected = best_of_n(samples, len(samples), objective, admissible=scoreable)
            if method.endswith('_prune'): selected = prune_leave_one_out(selected.bullets, scorer.score, maximum_loss=maximum_loss)
        else: raise ValueError('Unknown experimental method: ' + method)
    ids = selected.phrase_ids
    valid = scorer is not None and all(i in scorer.vectors for i in ids)
    return {'status': 'complete', 'method': method, 'n': 1 if method in ('capped_n1', 'prune_n1') else len(samples),
        'requested_prefix': len(samples), 'consumed_prefix': 1 if method in ('capped_n1', 'prune_n1') else len(samples), 'text': selected.text,
        'phrase_ids': list(ids), 'token_count': count(selected.text), 'bullet_count': len(ids),
        'fits': scorer.fit(ids).__dict__ if valid else None,
        'fits_scope': 'emitted_bullets' if valid else 'unavailable_or_not_requested_AR',
        'reason': selected.reason, 'trace': list(selected.trace), 'maximum_pruning_loss': maximum_loss,
        'invalid_AR_atoms_by_sample': {s.index: [b.phrase_id for b in s.bullets if scorer is not None and b.phrase_id not in scorer.vectors]
                                       for s in samples},
        'profile_status': 'experimental; no final quality recommendation yet'}


def replay_select(artifacts, pool, activation, *, method='best_n', n=None, cache_directory=None,
                  encode_missing=False, controls=None, control_provenance=None, maximum_loss=.005):
    """Select one saved pool against the same h; all controls must be caller-frozen."""
    value = vector(activation)
    if activation_hash(value) != pool.activation_sha256: raise ValueError('Replay activation differs from saved pool')
    tok, count = token_counter(artifacts); samples = samples_for_pool(pool, count, n)
    if method.startswith('specificity') and not controls:
        return {'status': 'unavailable', 'method': method, 'text': None,
                'reason': 'frozen_matched_control_bank_required', 'pool_provenance': pool.provenance}
    if method in ('raw_n1', 'capped_n1'):
        return select_scored_pool(pool, samples, count, method=method) | {'pool_provenance': pool.provenance}
    if not artifacts.ar_checkpoint or not artifacts.whitener_directory:
        return select_scored_pool(pool, samples, count, method=method) | {'pool_provenance': pool.provenance}
    if controls:
        if not control_provenance or control_provenance.get('layer') != pool.layer or not control_provenance.get('bank_sha256'):
            raise ValueError('Explicit frozen matched-control bank provenance/layer required')
        controls = {key: vector(v) for key, v in controls.items()}
    import torch
    checkpoint = Path(artifacts.ar_checkpoint); state = torch.load(checkpoint/'heads.pt', map_location='cpu', weights_only=True)
    tags = state['tag_ids'][list(state['layers']).index(pool.layer)].tolist()
    atoms = [b for s in samples for b in s.bullets]; cleaned = {}; raw = {}; metadata = {}
    for b in atoms:
        text, ids = ar_token_ids(tok, b.text); cleaned[b.phrase_id] = (text, ids)
        metadata[b.phrase_id] = {'text': b.text, 'scored_token_ids': ids[:32], 'original_token_count': len(ids),
                                'scored_token_count': min(32, len(ids)), 'truncated': len(ids) > 32}
    cache = RawVectorCache(cache_directory) if cache_directory else None
    if cache and (cache.contract['base_revision'] != BASE_REVISION or
                  cache.contract['pair_revision'] != PAIR_REVISION or
                  cache.contract['tokenizer_revision'] != BASE_REVISION or
                  cache.contract['head_sha256'] != file_sha(checkpoint/'heads.pt') or
                  cache.contract['meta_sha256'] != file_sha(checkpoint/'meta.json') or
                  cache.contract['adapter_sha256'] != file_sha(checkpoint/'lora/adapter_model.safetensors') or
                  cache.contract['adapter_config_sha256'] != file_sha(checkpoint/'lora/adapter_config.json') or
                  cache.contract['span_limit'] != 32 or cache.contract['tokenizer_cleanup'] != 'source_scaffolding_and_special_ids_v1' or
                  cache.contract['padding'] != 'right_zero' or cache.contract['head_layer_norm'] is not True or
                  cache.contract['head_layer_norm_epsilon'] != 1e-5 or cache.contract['final_norm'] != 'Identity' or
                  cache.contract['backbone_dtype'] != 'bfloat16' or cache.contract['head_dtype'] != 'float32' or
                  cache.contract['key_policy'] != 'effective_scored_tokens_and_tag_v1'):
        raise ValueError('Cached vectors differ from exact local AR artifacts/input contract')
    missing = {}
    for b in atoms:
        text, ids = cleaned[b.phrase_id]
        if not ids: continue
        identity = tuple(ids[:32])
        key = vector_key(cache.contract['sha256'], tags, list(identity)) if cache else None
        if cache and key in cache.index: raw[b.phrase_id] = cache.get(key)
        else: missing.setdefault(identity, []).append(b)
    if missing:
        if not encode_missing: raise ValueError('Missing AR vectors; use explicit encode_missing or replay a complete cache')
        reader = None
        try:
            reader = FrozenAR.load(artifacts.base_path, str(checkpoint), artifacts.device)
            ordered = sorted(missing); predictions, encoding_meta = reader.encode([missing[k][0].text for k in ordered], pool.layer)
            for key, prediction in zip(ordered, predictions.detach().float().cpu()):
                for b in missing[key]: raw[b.phrase_id] = prediction
        finally:
            if reader is not None: release_reader(reader)
    ruler = Path(artifacts.whitener_directory)/f'whitening_iolens_pooled_L{pool.layer}.safetensors'
    whitener = Whitener.load(str(ruler)); exact = JointNNLS.from_raw(value, raw, whitener)
    control_scorers = {key: JointNNLS.from_raw(v, raw, whitener) for key, v in (controls or {}).items()}
    result = select_scored_pool(pool, samples, count, method=method, scorer=exact,
                               controls=control_scorers, maximum_loss=maximum_loss)
    result |= {'pool_provenance': pool.provenance, 'activation_sha256': pool.activation_sha256,
               'layer': pool.layer, 'atoms': metadata, 'whitener_sha256': whitener.artifact_sha256,
               'AR_head_sha256': file_sha(checkpoint/'heads.pt'), 'control_provenance': control_provenance,
               'execution': {'batch_size_limit': 128, 'missing_effective_keys_encoded': len(missing),
                             'cache_directory': str(cache_directory) if cache_directory else None},
               'implementation_sha256': {name: file_sha(Path(__file__).with_name(name))
                                          for name in ('inference.py', 'models.py', 'reconstruction.py', 'selection.py', 'contrastive.py')},
               'numerical_note': 'Fixed local batch packing; not equivalent to other batch sizes. 32-token scorer suffix blind spot.'}
    return result
