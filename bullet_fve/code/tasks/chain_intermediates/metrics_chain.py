"""Run the unchanged code/metrics_job.py (per-bullet solo FVE, LOO drop, exact Shapley, coefficients)
on Chained intermediates. metrics_job reads INPUTS/hall_three_settings.jsonl and
INPUTS/hall_vector_index.json; metrics_inputs/ holds symlinks with those names pointing at this
task's chain_three_settings.jsonl / chain_vector_index.json (same schema). Nothing else changes.

Usage (inside srun): python -B metrics_chain.py --layer 20 --out OUT.jsonl [--cells id1,id2] [--summary S.json]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'code'))
import metrics_job  # noqa: E402

metrics_job.INPUTS = HERE / 'metrics_inputs'
if __name__ == '__main__':
    metrics_job.main()
