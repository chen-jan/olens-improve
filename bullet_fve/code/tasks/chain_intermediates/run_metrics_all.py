"""Run metrics_chain.py (= the unchanged code/metrics_job.py on the chain extract) for every layer, one
subprocess per layer, inside ONE quicktest allocation. Per layer ~10 s, 11 layers -> ~2 min.

Writes metrics/bullet_metrics.L{L}.jsonl, metrics/summary.L{L}.json, metrics/run.L{L}.log, metrics/launch.log.
Usage (inside srun): python -B run_metrics_all.py [--layers 20,24,...]
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'metrics'
LAYERS = list(range(20, 61, 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layers', default=','.join(map(str, LAYERS)))
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    env = dict(os.environ, OMP_NUM_THREADS=os.environ.get('SLURM_CPUS_PER_TASK', '8'))
    with open(OUT / 'launch.log', 'a') as log:
        for L in [int(x) for x in args.layers.split(',') if x]:
            t0 = time.time()
            with open(OUT / f'run.L{L}.log', 'w') as fh:
                rc = subprocess.call([sys.executable, '-B', str(HERE / 'metrics_chain.py'), '--layer', str(L),
                                      '--out', str(OUT / f'bullet_metrics.L{L}.jsonl'),
                                      '--summary', str(OUT / f'summary.L{L}.json')],
                                     stdout=fh, stderr=subprocess.STDOUT, env=env)
            msg = f'L{L} exit={rc} seconds={time.time() - t0:.1f} host={os.uname().nodename} job={os.environ.get("SLURM_JOB_ID")}'
            print(msg, flush=True)
            log.write(msg + '\n')
            log.flush()


if __name__ == '__main__':
    main()
