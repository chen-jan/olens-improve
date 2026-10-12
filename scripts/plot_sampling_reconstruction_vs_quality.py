"""Plot frozen best-of-N reconstruction against native WorkspaceBench endpoints."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, PercentFormatter
import numpy as np


FAMILIES = [
    ('hallucination', 'Hallucination (chat)', 'Contradicting readouts (%) · lower is better'),
    ('multihop_mt', 'Multihop (multi-token)', 'Questions recovered (%) · higher is better'),
    ('chain_intermediates', 'Chained intermediates', 'Questions recovered (%) · higher is better'),
    ('role_bound_association', 'Role-bound association', 'Questions recovered (%) · higher is better'),
]
SAMPLES = [1, 2, 4, 8, 16, 32]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plot(native_path: Path, reconstruction_path: Path, output: Path):
    if output.exists():
        raise FileExistsError('Use a new output directory; preserve prior figures')
    native = json.loads(native_path.read_text())
    reconstruction = json.loads(reconstruction_path.read_text())
    assert reconstruction['quality_analysis_sha256'] == sha(native_path)
    assert native['manifest_sha256'] == reconstruction['manifest_sha256']
    assert not native['missing_condition_families']
    quality = {(r['condition'], r['family']): r['metric'] for r in native['cohorts']['full']['rows']}
    fits = {(r['condition'], r['family']): r for r in reconstruction['rows']}
    rows = []
    for family, _, _ in FAMILIES:
        for n in SAMPLES:
            condition = f'best_n_exact-n{n}'
            q, f = quality[condition, family], fits[condition, family]
            assert f['status'] == 'complete_comparable' and f['scored_site_count'] == f['full_site_count']
            assert q['ci95'] is not None and f['mean_fve_ci95'] is not None
            rows.append({'family': family, 'samples': n, 'reconstruction_percent': 100*f['mean_fve'],
                         'reconstruction_ci_low': 100*f['mean_fve_ci95'][0],
                         'reconstruction_ci_high': 100*f['mean_fve_ci95'][1],
                         'task_percent': 100*q['value'], 'task_ci_low': 100*q['ci95'][0],
                         'task_ci_high': 100*q['ci95'][1], 'task_numerator': q['numerator'],
                         'task_denominator': q['denominator'], 'activation_sites': f['full_site_count'],
                         'questions': q['items'], 'related_groups': q['independent_groups']})
    output.mkdir(parents=True)
    with (output/'values.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)

    blue, accent, gray, ink = '#1769a4', '#c45d29', '#697c89', '#19344b'
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.labelcolor': ink, 'text.color': ink, 'axes.edgecolor': '#b7c5ce',
                         'xtick.color': '#516674', 'ytick.color': '#516674'})
    fig, axes = plt.subplots(2, 2, figsize=(14, 10.4))
    fig.subplots_adjust(left=.08, right=.975, bottom=.17, top=.82, wspace=.24, hspace=.43)
    fig.suptitle('Reconstruction rises with more samples; task performance is uneven',
                 x=.055, y=.966, ha='left', fontsize=19, fontweight='bold')
    fig.text(.055, .926, 'Frozen Oracle Lens + reconstructor · four full WorkspaceBench banks · 469 questions', fontsize=12)
    fig.legend(handles=[Line2D([0],[0], color=blue, marker='o', label='Best-of-N; labels show number of samples'),
                        Line2D([0],[0], color=gray, linestyle='--', label='Original released Oracle Lens task score')],
               loc='upper left', bbox_to_anchor=(.049,.908), frameon=False, ncol=2, fontsize=11)
    summaries = {}
    for ax, (family, title, ylabel) in zip(axes.flat, FAMILIES):
        r = [x for x in rows if x['family'] == family]
        x = np.array([a['reconstruction_percent'] for a in r])
        y = np.array([a['task_percent'] for a in r])
        xerr = np.vstack([x-[a['reconstruction_ci_low'] for a in r],
                          [a['reconstruction_ci_high'] for a in r]-x])
        yerr = np.vstack([y-[a['task_ci_low'] for a in r], [a['task_ci_high'] for a in r]-y])
        raw = 100*quality['raw_n1-n1', family]['value']
        ax.set_axisbelow(True); ax.grid(color='#e8eef2', linewidth=.8)
        ax.errorbar(x, y, xerr=xerr, yerr=yerr, fmt='none', ecolor=blue, alpha=.25, capsize=3, linewidth=1.2)
        ax.axhline(raw, color=gray, linestyle=(0,(4,3)), linewidth=1.3)
        ax.plot(x, y, color=blue, marker='o', markersize=6, linewidth=2)
        ax.scatter(x[-1], y[-1], color=accent, s=55, zorder=4)
        offsets = [(-13,10),(-8,11),(-8,11),(-7,-18),(-8,11),(7,-15)]
        if family == 'hallucination':
            offsets = [(-14,-18),(-7,10),(-8,-18),(-8,10),(-8,10),(7,-15)]
        for i, n in enumerate(SAMPLES):
            ax.annotate(str(n), (x[i],y[i]), xytext=offsets[i], textcoords='offset points',
                        fontsize=11, fontweight='bold', color=accent if n==32 else blue,
                        bbox={'facecolor':'white','edgecolor':'none','pad':.5,'alpha':.85})
        fit_delta = x[-1]-x[0]
        summaries[family] = {'scored_n1_to_n32_reconstruction_points': float(fit_delta),
                            'scored_n1_to_n32_task_points': float(y[-1]-y[0]),
                            'original_lens_task_percent': raw}
        ax.set_title(title, loc='left', fontsize=14, fontweight='bold', pad=31)
        ax.text(0,1.025, f'1 → 32 samples: reconstruction +{fit_delta:.2f} points; task {y[0]:.2f}% → {y[-1]:.2f}%',
                transform=ax.transAxes, fontsize=10.5, color='#516674')
        ax.set_xlabel('Selected readout: activation variance explained (%)', fontsize=10.5)
        ax.set_ylabel(ylabel, fontsize=10.5)
        ax.xaxis.set_major_locator(MaxNLocator(5)); ax.yaxis.set_major_locator(MaxNLocator(5))
        ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=1))
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=1))
        for spine in ('top','right'): ax.spines[spine].set_visible(False)
        ax.margins(x=.12, y=.12)
    fig.text(.055,.098,'The AR weights never change. Higher x means a better reconstruction score for the selected text—not a better trained model.',fontsize=11)
    fig.text(.055,.070,'Bars: existing grouped pointwise 95% intervals for each mean/rate, not intervals for paired changes. Previously inspected data; exploratory.',fontsize=10.5,color='#516674')
    fig.text(.055,.044,'N=1 uses the selection pipeline, not the raw original baseline. The two axes measure different things; equal-size gains are not expected.',fontsize=10.5,color='#516674')
    fig.savefig(output/'sampling-reconstruction-vs-quality.png', dpi=190, facecolor='white')
    fig.savefig(output/'sampling-reconstruction-vs-quality.svg', facecolor='white')
    plt.close(fig)
    manifest = {'source_sha256': {str(native_path):sha(native_path), str(reconstruction_path):sha(reconstruction_path)},
                'script_sha256':sha(Path(__file__)), 'samples': SAMPLES, 'summaries': summaries,
                'intervals':'existing grouped pointwise 95% mean/rate intervals; no new intervals computed',
                'baseline':'scored best_n_exact-n1; raw original native score shown separately; raw AR unavailable',
                'limits':['AR and native endpoints are different quantities.', 'All questions previously inspected; exploratory.'],
                'inference_calls':0}
    manifest['outputs_sha256']={p.name:sha(p) for p in output.iterdir() if p.is_file()}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'png':str(output/'sampling-reconstruction-vs-quality.png'),'summaries':summaries}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--reconstruction',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plot(args.native,args.reconstruction,args.output)
