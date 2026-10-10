"""Check installed cache-saving CLI on a retained non-benchmark engineering pool."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import sys
import time


def file_sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('artifacts', 'fixture', 'installation', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--dependency-site', action='append', default=[])
    a = p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or a.output.exists():
        raise ValueError('Require an assigned GPU and a new engineering output directory')
    scope = json.loads((a.fixture/'scope.json').read_text())
    if scope.get('scientific_results_eligible') is not False or scope.get('benchmark_inputs') != 0:
        raise ValueError('Only the retained non-benchmark engineering fixture is allowed')
    if file_sha(a.fixture/'pool.json') != '123ccffddeb7732450b979b567413ef093fab6ecefd3a330020dfa5001564e79':
        raise ValueError('Engineering pool identity changed; never regenerate it')
    for directory in a.dependency_site:
        sys.path.append(directory)  # Explicit distributions, no .pth execution.
    import torch
    from olens_improve.__main__ import main as cli
    from olens_improve.inference import CandidatePool
    from olens_improve.reconstruction import FrozenAR
    import olens_improve.inference as inference
    installed = Path(inference.__file__).resolve().parent
    if not installed.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError('Require the separately installed candidate wheel')
    receipt = json.loads(a.installation.read_text())
    for name, expected in receipt['source_sha256'].items():
        if file_sha(installed.parent/name) != expected:
            raise ValueError('Installed source differs from the reviewed wheel')
    pool = CandidatePool.load(a.fixture/'pool.json')
    if len(pool.records) != 2 or pool.activation_sha256 != '825b7670774ff35d71ec8177e3c5a19ec93cc18b4ad3a538c4309d76a159665e':
        raise ValueError('Engineering activation/pool identity differs')
    a.output.mkdir(parents=True)
    torch.set_num_threads(4)
    torch.cuda.reset_peak_memory_stats()
    common = ['--artifacts', str(a.artifacts), '--activation', str(a.fixture/'activation.safetensors'),
              '--pool', str(a.fixture/'pool.json'), '--method', 'best_n', '--n', '2']
    started = time.monotonic()
    cli(['replay', *common, '--encode-missing', '--save-cache', str(a.output/'cache'),
         '--output', str(a.output/'encoded.json')])
    encoding_seconds = time.monotonic()-started
    first = json.loads((a.output/'encoded.json').read_text())
    if first['execution']['missing_effective_keys_encoded'] != 8:
        raise ValueError('Expected all eight fixture phrase vectors to be newly encoded')
    # Move the standalone cache without its prior location or any inherited cache.
    (a.output/'cache').rename(a.output/'relocated-cache')
    original = FrozenAR.load
    def forbidden_load(*args, **kwargs):
        raise AssertionError('Cache-only replay must not load the reconstructor')
    FrozenAR.load = forbidden_load
    replay_started = time.monotonic()
    try:
        cli(['replay', *common, '--cache-directory', str(a.output/'relocated-cache'),
             '--output', str(a.output/'replayed.json')])
    finally:
        FrozenAR.load = original
    replay_seconds = time.monotonic()-replay_started
    second = json.loads((a.output/'replayed.json').read_text())
    if (second['execution']['missing_effective_keys_encoded'] != 0 or first['text'] != second['text']
            or first['phrase_ids'] != second['phrase_ids'] or first['fits'] != second['fits']):
        raise ValueError('Saved-cache replay changed the installed selection')
    old = json.loads((a.fixture/'selection-encoded.json').read_text())
    old_delta = abs(first['fits']['fve']-old['fits']['fve'])
    if first['text'] != old['text'] or first['phrase_ids'] != old['phrase_ids'] or old_delta > 1e-6:
        raise ValueError('Candidate wheel differs from retained engineering selection')
    result = {'status':'installed_cache_persistence_verified', 'scientific_results_eligible':False,
        'new_OLens_samples':0, 'new_API_calls':0, 'new_AR_vectors':8, 'cached_replay_new_vectors':0,
        'identical_cached_selection':True, 'relocated_cache_verified':True, 'old_wheel_FVE_difference':old_delta,
        'encoding_and_selection_seconds':encoding_seconds, 'cached_replay_seconds':replay_seconds,
        'total_seconds':time.monotonic()-started, 'peak_GPU_allocated_bytes':torch.cuda.max_memory_allocated(),
        'host_peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        'pool_sha256':file_sha(a.fixture/'pool.json'), 'installation_sha256':file_sha(a.installation),
        'driver_sha256':file_sha(__file__), 'installed_sources':receipt['source_sha256'],
        'limits':'Existing local third-party distributions and pinned cached weights; not an independent-machine dependency installation or semantic quality evaluation.'}
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'seconds':result['total_seconds']}))


if __name__ == '__main__':
    main()
