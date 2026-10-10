"""Planned synthetic-input engineering check; never benchmark or API work.

Run with the installed-wheel interpreter after an allocated GPU is released.
Explicit dependency sites reuse installed distributions without running .pth files.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import sys
import time


PROMPT = 'The library closes at six. Nora returns a borrowed book before walking home.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--cache-contract', type=Path, required=True,
                        help='Verified metadata contract only; no inherited raw vectors')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dependency-site', action='append', default=[])
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Use a coordinator-assigned GPU allocation, after blind generation ends')
    for directory in args.dependency_site:
        sys.path.append(directory)
    import torch
    from safetensors.torch import save_file
    from olens_improve.__main__ import main as cli
    from olens_improve.inference import (Artifacts, CandidatePool, activation_hash,
                                         file_sha, release_reader, save_once)
    from olens_improve.models import FrozenOLens
    from olens_improve.reconstruction import FrozenAR, ar_token_ids
    from olens_improve.ar_cache import digest, vector_key
    import olens_improve.inference as inference
    if not Path(inference.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('The smoke must import the installed package, not checkout source')
    if any(name.startswith(('wsbench', 'global_workspace', 'oracle_lens')) for name in sys.modules):
        raise RuntimeError('Historical research imports are forbidden in this fixture')
    artifacts = Artifacts(**json.loads(args.artifacts.read_text()))
    if artifacts.device != 'cuda' or not all((artifacts.olens_adapter, artifacts.ar_checkpoint,
                                            artifacts.whitener_directory)):
        raise ValueError('Explicit local CUDA base/adapter/AR/whitener artifacts required')
    root = args.output.resolve(); root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic(); torch.set_num_threads(4)
    torch.cuda.reset_peak_memory_stats()
    def memory():
        return {'allocated_bytes': torch.cuda.memory_allocated(),
                'reserved_bytes': torch.cuda.memory_reserved(),
                'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                'host_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    save_once(root/'scope.json', {'scientific_results_eligible': False,
        'purpose': 'Synthetic external-input engineering only; excluded from all benchmark aggregates',
        'prompt': PROMPT, 'layer': 44, 'position_policy': 'final_plain_text_token',
        'n': 2, 'seed': 20261010, 'API_calls': 0, 'benchmark_inputs': 0,
        'slurm_job_id': os.environ['SLURM_JOB_ID'],
        'artifacts_config_sha256': file_sha(args.artifacts),
        'driver_sha256': file_sha(__file__), 'installed_module': inference.__file__})
    reader = None; stage = time.monotonic()
    try:
        reader = FrozenOLens.load(artifacts.base_path, artifacts.olens_adapter, artifacts.device)
        ids = reader.tokenizer(PROMPT, add_special_tokens=False)['input_ids']
        h = reader.capture(ids, [44], [len(ids)-1])[44][0].contiguous()
        save_file({'activation': h}, str(root/'activation.safetensors'))
        capture = {'adapter_disabled': True, 'token_ids': ids, 'layer': 44,
                   'position': len(ids)-1, 'activation_sha256': activation_hash(h),
                   'adapter_logit_delta': reader.adapter_delta, 'memory': memory()}
    finally:
        if reader is not None: release_reader(reader)
    capture['load_capture_release_seconds'] = time.monotonic()-stage
    capture['memory_after_release'] = memory(); save_once(root/'capture.json', capture)
    common = ['--artifacts', str(args.artifacts), '--activation', str(root/'activation.safetensors'),
              '--pool', str(root/'pool.json')]
    stage = time.monotonic()
    cli(['generate', *common, '--layer', '44', '--n', '2', '--seed', '20261010'])
    generation_seconds = time.monotonic()-stage
    pool = CandidatePool.load(root/'pool.json')
    assert len(pool.records) == 2 and pool.activation_sha256 == activation_hash(h)
    cache = root/'raw-cache'; cache.mkdir()
    contract = json.loads(args.cache_contract.read_text())
    assert digest({k: v for k, v in contract.items() if k != 'sha256'}) == contract['sha256']
    save_once(cache/'contract.json', contract)
    # Observe the CLI's actual encoder result; never run another encoding or alter it.
    original_encode = FrozenAR.encode; observed = {}
    def record_encode(ar, texts, layer):
        predictions, metadata = original_encode(ar, texts, layer)
        tags = ar.tags[list(ar.layers).index(layer)].tolist()
        for text, prediction in zip(texts, predictions.detach().float().cpu()):
            _, tokens = ar_token_ids(ar.tokenizer, text)
            key = vector_key(contract['sha256'], tags, tokens[:32])
            observed[key] = prediction.contiguous()
        return predictions, metadata
    stage = time.monotonic(); FrozenAR.encode = record_encode
    try:
        cli(['replay', *common, '--method', 'best_n', '--n', '2', '--cache-directory', str(cache),
             '--encode-missing', '--output', str(root/'selection-encoded.json')])
    finally:
        FrozenAR.encode = original_encode
    encoding_selection_seconds = time.monotonic()-stage
    if not observed:
        raise RuntimeError('No scoreable generated atoms: AR engineering path was not exercised; preserve this attempt')
    if observed:
        keys = sorted(observed); tensor = cache/'raw_00000.safetensors'
        save_file({'vectors': torch.stack([observed[k] for k in keys])}, str(tensor))
        save_once(cache/'raw_00000.index.json', {'contract_sha256': contract['sha256'],
            'tensor_path': str(tensor), 'scientific_results_eligible': False,
            'vectors': [{'cache_key': key, 'row': i} for i, key in enumerate(keys)]})
    first = json.loads((root/'selection-encoded.json').read_text())
    assert first['execution']['missing_effective_keys_encoded'] == len(observed)
    stage = time.monotonic()
    cli(['replay', *common, '--method', 'best_n', '--n', '2', '--cache-directory', str(cache),
         '--output', str(root/'selection-cached.json')])
    second = json.loads((root/'selection-cached.json').read_text())
    assert second['execution']['missing_effective_keys_encoded'] == 0
    assert first['text'] == second['text'] and first['phrase_ids'] == second['phrase_ids']
    assert abs(first['fits']['fve']-second['fits']['fve']) < 1e-10
    report = {'scientific_results_eligible': False, 'status': 'engineering_complete_not_quality_evaluation',
        'capture': capture, 'generation_seconds': generation_seconds,
        'AR_encoding_selection_seconds': encoding_selection_seconds,
        'cached_replay_seconds': time.monotonic()-stage, 'raw_vectors': len(observed),
        'pool_sha256': file_sha(root/'pool.json'), 'activation_sha256': activation_hash(h),
        'cache_contract_sha256': contract['sha256'], 'API_calls': 0,
        'memory_after_all_loaders_released': memory(), 'total_seconds': time.monotonic()-started,
        'installed_sources': {name: file_sha(module.__file__) for name, module in sys.modules.items()
            if name.startswith('olens_improve') and getattr(module, '__file__', None)}}
    save_once(root/'result.json', report)
    print(json.dumps({'status': report['status'], 'result': str(root/'result.json')}))


if __name__ == '__main__': main()
