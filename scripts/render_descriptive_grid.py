"""Render clearer DEV/VAL figures from an immutable, reviewed grid artifact."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')
LABELS = {
    'capped_n1-n1': 'One original sample\nsame output cap',
    'best_n_exact-n16': 'Best reconstruction\n16 samples',
    'best_n_exact-n32': 'Best reconstruction\n32 samples',
    'best_n_specificity_mean-n32': 'Matched-control selection\n32 samples',
}
FAMILY_LABELS = {
    'hallucination': 'Contradiction rate',
    'multihop_mt': 'Required bridge mention',
    'chain_intermediates': 'Intermediate number recovery',
    'role_bound_association': 'Directed role recovery',
}


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def validate_artifact(artifact):
    stages = artifact['stages']
    if not stages or any(s['stage'] not in ('development', 'validation') for s in stages):
        raise ValueError('Only the reviewed DEV/VAL figures are supported; TEST is closed')
    if artifact.get('test_outcomes_accessed') is not False:
        raise ValueError('Expected the reviewed DEV/VAL source contract')
    for stage in stages:
        for method in stage['conditions']:
            if method['condition'] not in LABELS:
                raise ValueError('Unknown reviewed condition label')
            if set(method['families']) != set(FAMILIES):
                raise ValueError('Expected all four original families')
            for grid in method['families'].values():
                for row in grid['slots']:
                    if row['accounted_cells'] != row['expected_cells'] or row['missing_required_results']:
                        raise ValueError('Incomplete grid; do not render missing results as zero')
                    count_label(row['metric'])


def count_label(metric):
    numerator, denominator, value = metric['numerator'], metric['denominator'], metric['value']
    if not 0 <= numerator <= denominator:
        raise ValueError('Invalid endpoint counts')
    if value is None:
        if denominator:
            raise ValueError('Undefined rate with an eligible denominator')
        return None
    if not denominator or abs(value - numerator / denominator) > 1e-12:
        raise ValueError('Endpoint rate disagrees with preserved counts')
    return f'{100 * value:.0f}%\n{numerator}/{denominator}'


def render(stage, output):
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/olens-improve-grid-v2-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    created = []
    for family in FAMILIES:
        methods = stage['conditions']
        fig, axes = plt.subplots(1, len(methods), figsize=(5.2 * len(methods), 6.5),
                                 squeeze=False, layout='constrained')
        for ax, method in zip(axes.flat, methods):
            grid = method['families'][family]
            layers, ranks = grid['layers'], grid['position_ranks']
            values = np.full((len(layers), len(ranks)), np.nan)
            lookup = {(row['layer'], row['position_rank']): row for row in grid['slots']}
            for j, layer in enumerate(layers):
                for i, rank in enumerate(ranks):
                    row = lookup.get((layer, rank))
                    if row and row['metric']['value'] is not None:
                        values[j, i] = 100 * row['metric']['value']
            image = ax.imshow(values, vmin=0, vmax=100, aspect='auto',
                              cmap='YlOrRd' if family == 'hallucination' else 'YlGnBu')
            ax.set_xticks(range(len(ranks)), ranks, fontsize=8)
            ax.set_yticks(range(len(layers)), layers, fontsize=9)
            ax.set_xlabel('Position rank within each item')
            ax.set_ylabel('Decoder layer')
            ax.set_title(LABELS[method['condition']], fontsize=11)
            if len(ranks) <= 8:
                for (layer, rank), row in lookup.items():
                    label = count_label(row['metric'])
                    if label is not None:
                        ax.text(ranks.index(rank), layers.index(layer), label,
                                ha='center', va='center', fontsize=7,
                                color='white' if row['metric']['value'] > .65 else 'black')
            fig.colorbar(image, ax=ax, shrink=.6, label='Rate (%)')
        split_label = 'Development' if stage['stage'] == 'development' else 'Validation'
        endpoint = ('Wrong / (wrong + off-topic + consistent); lower is better'
                    if family == 'hallucination' else
                    'Recovery / intended cells; higher is better')
        fig.suptitle(f'{split_label}: {FAMILY_LABELS[family]}\n{endpoint}', fontsize=13)
        fig.supxlabel(
            'Cell labels show percentage and endpoint numerator/denominator where space permits. '
            'Generic and empty outputs are excluded from the contradiction denominator.\n'
            'Position ranks mix different token indices and meanings across items; no best site is selected. '
            'Missing or undefined rates are masked.\n'
            'Counts, exploratory group intervals, assertion and empty shares remain in the unchanged source JSON. '
            'Colors alone do not establish reliable site differences.', fontsize=9)
        for extension in ('png', 'pdf'):
            path = output / f"{stage['stage']}-{family}.{extension}"
            fig.savefig(path, dpi=160, bbox_inches='tight', facecolor='white')
            created.append({'path': str(path), 'sha256': digest(path)})
        plt.close(fig)
    return created


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    if sha256(raw).hexdigest() != args.expected_sha256:
        raise ValueError('Reviewed source artifact changed')
    artifact = json.loads(raw)
    validate_artifact(artifact)
    if args.output.exists():
        raise ValueError('Preserve previous figures; choose a new output directory')
    args.output.mkdir(parents=True)
    figures = [figure for stage in artifact['stages'] for figure in render(stage, args.output)]
    if digest(args.source) != args.expected_sha256:
        raise ValueError('Source changed during rendering')
    receipt = {
        'status': 'complete_figures_only_pending_visual_review',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source': str(args.source), 'source_sha256': args.expected_sha256,
        'renderer': str(Path(__file__).resolve()), 'renderer_sha256': digest(__file__),
        'metrics_and_intervals_recomputed': False,
        'new_API_calls': 0, 'test_outcomes_accessed': False,
        'condition_labels': LABELS, 'figures': figures,
        'annotation': 'Endpoint percentage plus numerator/denominator, not intended-site count.',
        'limits': artifact['limits'], 'position_definition': artifact['position_definition'],
    }
    path = args.output / 'figure-provenance.json'
    path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    for file in args.output.iterdir():
        file.chmod(0o444)
    print(json.dumps({'path': str(path), 'sha256': digest(path), 'figures': len(figures)}))


if __name__ == '__main__':
    main()
