"""Off-benchmark installed-tool timing; prepare now, launch only on assigned GPU.

One fixed synthetic prompt, adapter-off final-token L44 capture, one N32 pool,
no inherited vectors or APIs. Frozen profiles JSON must contain status
root_reviewed_timing_profiles, freeze_sha256, and profiles [{id,method,n,
maximum_loss?}]. Specificity additionally requires explicit frozen controls.
Cold load/capture, warm N32 generation, AR load/encoding and cached replay are
different measurements. Prefix replay is NOT a smaller-N generation experiment.
"""
import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import resource
import sys
import time

PROMPT = 'The library closes at six. Nora returns a borrowed book before walking home.'
PREFIXES = (1, 2, 4, 8, 16, 32)
METHODS = {'raw_n1', 'capped_n1', 'best_n', 'prune_n1', 'prune_best',
           'pool', 'specificity_mean', 'specificity_mean_prune'}


def checked_profiles(body, controls_available):
    if body.get('status') != 'root_reviewed_timing_profiles' or not re.fullmatch(
            '[0-9a-f]{64}', str(body.get('freeze_sha256', ''))):
        raise ValueError('Explicit reviewed timing profiles/freeze identity required')
    profiles = body.get('profiles', [])
    if not profiles or len(profiles) > 6:
        raise ValueError('Require one to six explicit frozen operating profiles')
    names = set()
    for profile in profiles:
        name, method, n = (profile.get(k) for k in ('id', 'method', 'n'))
        if (not isinstance(name, str) or not re.fullmatch('[a-zA-Z0-9_-]+', name)
                or name in names or name.startswith('prefix-')):
            raise ValueError('Distinct filesystem-safe profile IDs required')
        names.add(name)
        if method not in METHODS or isinstance(n, bool) or not isinstance(n, int) or n not in PREFIXES:
            raise ValueError('Unsupported profile method/persisted prefix')
        if method in ('raw_n1', 'capped_n1', 'prune_n1') and n != 1:
            raise ValueError('N1 profiles consume only the first sample')
        loss = profile.get('maximum_loss', .005)
        if isinstance(loss, bool) or not isinstance(loss, (int, float)) or not math.isfinite(loss) or loss < 0:
            raise ValueError('Invalid frozen pruning tolerance')
        if method.startswith('specificity') and not controls_available:
            raise ValueError('Specificity requires explicit frozen matched-control provenance')
    return profiles


def observe_method(cls, name, wrapper):
    """Observe an existing method without altering its arguments or result."""
    descriptor = cls.__dict__[name]
    original = getattr(cls, name)
    replacement = wrapper(original)
    setattr(cls, name, classmethod(replacement) if isinstance(descriptor, classmethod) else replacement)
    return lambda: setattr(cls, name, descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('artifacts', 'cache-contract', 'profiles', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--controls', type=Path)
    parser.add_argument('--dependency-site', action='append', default=[])
    args = parser.parse_args()
    profiles = checked_profiles(json.loads(args.profiles.read_text()), bool(args.controls))
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Coordinator-assigned idle GPU allocation required')
    for directory in args.dependency_site:
        sys.path.append(directory)
    import torch
    from safetensors.torch import save_file
    from olens_improve.__main__ import main as cli
    from olens_improve.inference import (Artifacts, CandidatePool, activation_hash,
                                         file_sha, release_reader, save_once)
    from olens_improve.models import FrozenOLens, BASE_REVISION, PAIR_REVISION
    from olens_improve.reconstruction import FrozenAR, ar_token_ids
    from olens_improve.ar_cache import digest, vector_key
    import olens_improve.inference as inference
    if not Path(inference.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('Use the installed wheel, not checkout source')
    artifacts = Artifacts(**json.loads(args.artifacts.read_text()))
    if artifacts.device != 'cuda' or not all((artifacts.olens_adapter, artifacts.ar_checkpoint,
                                            artifacts.whitener_directory)):
        raise ValueError('Explicit frozen local CUDA artifacts required')
    if args.controls:
        declared = json.loads(args.controls.read_text())
        if declared.get('layer') != 44 or not re.fullmatch('[0-9a-f]{64}', str(declared.get('bank_sha256', ''))):
            raise ValueError('Same-layer frozen bank identity required')
        if not declared.get('matching_policy') or not declared.get('controls'):
            raise ValueError('Declare the approved engineering calibration matching policy; no default donors')
    root = args.output.resolve(); root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic(); torch.set_num_threads(4)
    torch.cuda.reset_peak_memory_stats()
    measurements = []
    def memory():
        return {'allocated_bytes':torch.cuda.memory_allocated(), 'reserved_bytes':torch.cuda.memory_reserved(),
                'cumulative_run_peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                'host_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    def timed(name, function):
        torch.cuda.synchronize(); before = time.monotonic()
        try:
            return function()
        finally:
            torch.cuda.synchronize()
            measurements.append({'stage':name, 'wall_seconds':time.monotonic()-before, 'memory':memory()})
            save_once(root/f'timing-{len(measurements):02d}.json', measurements[-1])
    save_once(root/'scope.json', {'scientific_results_eligible':False, 'prompt':PROMPT,
        'layer':44, 'position_policy':'final_plain_text_token', 'n':32, 'seed':20261010,
        'API_calls':0, 'benchmark_inputs':0, 'inherited_raw_vectors':0,
        'slurm_job_id':os.environ['SLURM_JOB_ID'], 'profiles_sha256':file_sha(args.profiles),
        'artifacts_sha256':file_sha(args.artifacts), 'driver_sha256':file_sha(__file__),
        'controls_sha256':file_sha(args.controls) if args.controls else None})
    reader = None
    try:
        reader = timed('cold_O_lens_load', lambda: FrozenOLens.load(
            artifacts.base_path, artifacts.olens_adapter, artifacts.device))
        ids = reader.tokenizer(PROMPT, add_special_tokens=False)['input_ids']
        h = timed('warm_adapter_off_capture', lambda:reader.capture(ids,[44],[len(ids)-1])[44][0].contiguous())
        save_file({'activation':h}, str(root/'activation.safetensors'))
        texts, metadata = timed('warm_N32_generation', lambda:reader.sample(h,44,n=32,seed=20261010))
        if len(texts) != 32:
            raise RuntimeError('Exactly one complete N32 engineering pool required')
        rows = tuple({'sample_index':i,'text':text,'layer':44,'activation_sha256':activation_hash(h),
                      'base_revision':BASE_REVISION,'adapter_revision':PAIR_REVISION,'seed':20261010,
                      'sampling_metadata_index':i}
                     for i,text in enumerate(texts))
        pool = CandidatePool(44,activation_hash(h),rows,{'base_revision':BASE_REVISION,
            'pair_revision':PAIR_REVISION,'sampling':metadata,'kind':'engineering_only_new_pool',
            'adapter_sha256':file_sha(Path(artifacts.olens_adapter)/'adapter_model.safetensors'),
            'base_config_sha256':file_sha(Path(artifacts.base_path)/'config.json'),
            'base_weight_provenance':'Frozen revision declared by artifacts config; weights not rehashed.',
            'scientific_results_eligible':False})
        save_once(root/'pool.json',pool.as_dict())
        save_once(root/'capture.json',{'adapter_disabled':True,'token_ids':ids,'layer':44,
            'position':len(ids)-1,'activation_sha256':activation_hash(h),'adapter_logit_delta':reader.adapter_delta})
    finally:
        if reader is not None: timed('O_lens_release',lambda:release_reader(reader))
    cache = root/'raw-cache'; cache.mkdir()
    contract = json.loads(args.cache_contract.read_text())
    if digest({k:v for k,v in contract.items() if k!='sha256'}) != contract['sha256']:
        raise ValueError('Invalid AR metadata contract')
    save_once(cache/'contract.json',contract)
    observed = {}
    def load_observer(original):
        return lambda cls,*a,**kw:timed('cold_AR_load',lambda:original(*a,**kw))
    def encode_observer(original):
        def encode(ar,texts,layer):
            predictions,meta = timed('warm_AR_encoding',lambda:original(ar,texts,layer))
            tags = ar.tags[list(ar.layers).index(layer)].tolist()
            for text,prediction in zip(texts,predictions.detach().float().cpu()):
                _, tokens = ar_token_ids(ar.tokenizer,text)
                observed[vector_key(contract['sha256'],tags,tokens[:32])] = prediction.contiguous()
            return predictions,meta
        return encode
    common = ['--artifacts',str(args.artifacts),'--activation',str(root/'activation.safetensors'),
              '--pool',str(root/'pool.json'),'--cache-directory',str(cache)]
    restores = [observe_method(FrozenAR,'load',load_observer),observe_method(FrozenAR,'encode',encode_observer)]
    try:
        timed('fresh_AR_load_encode_whitening_selection_release',lambda:cli([
            'replay',*common,'--method','best_n','--n','32','--encode-missing',
            '--output',str(root/'selection-new-AR.json')]))
    finally:
        for restore in reversed(restores):restore()
    cold_pipeline_seconds = time.monotonic()-started
    if not observed:
        raise RuntimeError('No scoreable atoms; preserve this engineering attempt, not a successful timing claim')
    keys = sorted(observed); tensor = cache/'raw_00000.safetensors'
    save_file({'vectors':torch.stack([observed[k] for k in keys])},str(tensor))
    save_once(cache/'raw_00000.index.json',{'contract_sha256':contract['sha256'],'tensor_path':str(tensor),
        'scientific_results_eligible':False,'vectors':[{'cache_key':k,'row':i} for i,k in enumerate(keys)]})
    replay_rows = []
    requests = [(f'prefix-{n}',{'method':'best_n','n':n}) for n in PREFIXES]
    requests += [(p['id'],p) for p in profiles]
    for name,profile in requests:
        output = root/f'replay-{name}.json'
        extra = ['--controls',str(args.controls)] if profile['method'].startswith('specificity') else []
        timed('cached_replay_'+name,lambda:cli(['replay',*common,'--method',profile['method'],
            '--n',str(profile['n']),'--maximum-loss',str(profile.get('maximum_loss',.005)),
            *extra,'--output',str(output)]))
        result = json.loads(output.read_text())
        if result.get('status')!='complete' or result.get('execution',{}).get('missing_effective_keys_encoded',0)!=0:
            raise RuntimeError('Cached replay did not complete without new encodes')
        replay_rows.append({'id':name,'profile':profile,'result_sha256':file_sha(output),
                            'phrase_ids':result.get('phrase_ids'),'fits':result.get('fits')})
    first = json.loads((root/'selection-new-AR.json').read_text())
    repeated = json.loads((root/'replay-prefix-32.json').read_text())
    if first['text']!=repeated['text'] or first['phrase_ids']!=repeated['phrase_ids'] or abs(first['fits']['fve']-repeated['fits']['fve'])>1e-10:
        raise RuntimeError('Fresh/cache-only selection differs')
    save_once(root/'result.json',{'status':'engineering_timing_complete_not_quality_evaluation',
        'scientific_results_eligible':False,'measurements':measurements,'total_seconds':time.monotonic()-started,
        'cold_pipeline_through_first_selection_seconds':cold_pipeline_seconds,
        'raw_vectors':len(keys),'new_generations':32,'API_calls':0,'cached_replays':replay_rows,
        'pool_sha256':file_sha(root/'pool.json'),'activation_sha256':activation_hash(h),
        'cache_contract_sha256':contract['sha256'],'memory_after_all_release':memory(),
        'installed_sources':{name:file_sha(module.__file__) for name,module in sys.modules.items()
            if name.startswith('olens_improve') and getattr(module,'__file__',None)},
        'limits':['One cold lifecycle, not a latency distribution or fresh-machine install.',
            'Cold means model initialization in this process; OS/filesystem caches are not flushed, so no uncached-disk latency is measured.',
            'Warm generation timing is N32 only; prefixes replay the same pool, not smaller-N sampling.',
            'AR phase includes fresh encoding; cached replay excludes that new-input work.',
            'Nested instrumentation timings overlap; do not sum parent and child stages.',
            'CUDA peaks are cumulative since one reset at run start, not individual-stage peaks.',
            'Explicit calibration controls, when supplied, are preexisting inputs; capture cost is excluded.']})
    print(json.dumps({'result':str(root/'result.json'),'new_generations':32,'API_calls':0}))


if __name__=='__main__': main()
