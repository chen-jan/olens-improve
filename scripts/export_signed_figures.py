"""Export source-supplied signed comparison values; no inference or aggregation."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import textwrap


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = sibling('append_signed_comparison')
labels = sibling('build_dashboard')
FAMILIES = adapter.FAMILIES
AXES = {
    'hallucination':'Contradicted / specific readouts (%) - lower is better',
    'multihop_mt':'Bridge mentions / intended cells (%) - higher is better',
    'chain_intermediates':'Number recovery / intended cells (%) - higher is better',
    'role_bound_association':'Role task passes / intended cells (%) - higher is better'}
SHORT_LABELS = {
    'raw_n1-n1':'Original lens (1 sample)',
    'capped_n1-n1':'Capped single response',
    'best_n_exact-n16':'Best reconstruction (16)',
    'best_n_exact-n32':'Best reconstruction (32)',
    'random_complete-n32':'Random eligible response (32 pool)',
    'pooled_greedy_swap-n16':'Pool bullets (16)',
    'pooled_greedy_swap-n32':'Pool bullets (32)',
    'best_n_specificity_mean-n32':'Specificity selection (32)',
    'best_n_specificity_mean_then_prune_0.005-n32':'Specificity + pruning (0.005)',
    'best_n_specificity_mean_random_delete_matched_0.005-n32':'Specificity + matched random deletion',
    'prune_loo_a32_0.005-n32':'Best 32 + pruning (0.005)',
    'random_delete_matched_a32_0.005-n32':'Best 32 + matched random deletion'}


def method_labels(names):
    return [SHORT_LABELS.get(name,labels.display_label(name)) for name in names]


def label_positions(display_names):
    """Give multi-line labels enough space without changing method order."""
    wrapped = [textwrap.fill(name,34) for name in display_names]
    positions, cursor = [], 0.
    for name in wrapped:
        positions.append(cursor)
        cursor += max(1.,.55*(name.count('\n')+1))
    return wrapped, positions, cursor


def load_section(analysis, review_path, expected_sha):
    """Use the same reviewed capability/cohort checks as dashboard attachment."""
    review_raw = Path(review_path).read_bytes()
    review = json.loads(review_raw)
    adapter.reviewed_identity(review, expected_sha)  # Before outcome bytes.
    raw = Path(analysis).read_bytes()
    if sha256(raw).hexdigest() != expected_sha:
        raise ValueError('Figure source differs from reviewed SHA')
    return adapter.comparison(json.loads(raw), review, analysis, expected_sha,
                              sha256(review_raw).hexdigest())


def figure_data(section):
    indexed = {(r['condition'],r['family']):r['metric'] for r in section['cell_rows']}
    return {f:[{'condition':name, **indexed[name,f]} for name in section['condition_ids']]
            for f in FAMILIES}


def interval(ax, metric, at, *, vertical=False, color='#537990'):
    bounds = metric.get('ci95')
    if bounds is None:
        return
    low, high = (100*x for x in bounds)
    if vertical:
        ax.vlines(at,low,high,color=color,linewidth=1)
        ax.hlines([low,high],at-.5,at+.5,color=color,linewidth=1)
    else:
        ax.hlines(at,low,high,color=color,linewidth=1)
        ax.vlines([low,high],at-.10,at+.10,color=color,linewidth=1)


def export(section, output, *, cross_task=False):
    # Keep plotting caches off HOME; no dependency/model loads or installs.
    os.environ.setdefault('MPLCONFIGDIR','/tmp/olens-improve-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    output = Path(output)
    if output.exists():
        raise ValueError('Use a new figure directory; existing exports are immutable')
    output.mkdir(parents=True)
    data = figure_data(section)
    names = section['condition_ids']
    display_names = method_labels(names)
    wrapped, positions, extent = label_positions(display_names)
    source = section['source_sha256']
    stage = section['stage'].title()
    prefix = str(section['review'].get('figure_scope_label',''))
    prefix = prefix+'\n' if prefix else ''
    files = []

    def save(fig, stem):
        for extension in ('png','pdf'):
            path = output/(stem+'.'+extension)
            fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white')
            files.append({'path':path.name,'sha256':sha256(path.read_bytes()).hexdigest()})
        plt.close(fig)

    fig, axes = plt.subplots(2,2,figsize=(16,max(9,extent*.75)),layout='constrained')
    for ax,family in zip(axes.flat,FAMILIES):
        for i,row in enumerate(data[family]):
            at = positions[i]
            rate = row['value']
            if rate is not None:
                interval(ax,row,at)
                ax.plot(100*rate,at,'o',color='#244e69',markersize=5)
            else:
                ax.text(2,at,'Unknown',va='center',fontsize=9)
            count = f"{row['numerator']:,}/{row['denominator']:,}"
            ax.text(1.02,at,count,transform=ax.get_yaxis_transform(),va='center',fontsize=9)
        ax.set_yticks(positions,wrapped,fontsize=9)
        ax.set_ylim(extent-.5,-.65)
        ax.set_xlim(-1,101)
        ax.set_xlabel(AXES[family],fontsize=10)
        groups = section['family_counts'][family]['groups']
        group_label = 'related group' if groups==1 else 'related groups'
        ax.set_title(labels.display_label(family)+f' - {groups} {group_label}',fontsize=12)
        ax.grid(axis='x',alpha=.2)
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle(prefix+stage+' fixed-method cell comparisons\n'
        'Dots: supplied rates; bars: supplied per-method 95% intervals; labels: numerator/denominator',fontsize=14)
    fig.supxlabel('Cell scores do not establish whole-output truth. Missing intervals have no bar. '
                  'Source SHA-256 '+source[:12],fontsize=10)
    save(fig,'family-cell-rates')

    if cross_task:
        fig, axes = plt.subplots(1,3,figsize=(17,max(8,len(names)*.4+3)))
        fig.subplots_adjust(bottom=.40,top=.81,wspace=.35)
        colors = plt.get_cmap('tab20')
        for ax,family in zip(axes,FAMILIES[1:]):
            for i,(hall,recovery) in enumerate(zip(data['hallucination'],data[family])):
                if hall['value'] is None or recovery['value'] is None:
                    continue
                x,y = 100*hall['value'],100*recovery['value']
                color = colors(i%20)
                interval(ax,hall,y,color=color)
                interval(ax,recovery,x,vertical=True,color=color)
                ax.plot(x,y,'o',color=color,markersize=6)
                ax.annotate(str(i+1),(x,y),xytext=(4,4),textcoords='offset points',fontsize=8)
            ax.set_xlim(-1,101); ax.set_ylim(-1,101)
            ax.set_xlabel('Hall contradiction rate (%) - lower is better')
            ax.set_ylabel(AXES[family].split(' - ')[0])
            ax.set_title(labels.display_label(family)+' - separate cohort')
            ax.grid(alpha=.2)
        handles = [Line2D([],[],marker='o',linestyle='',color=colors(i%20),
                   label=f'{i+1}. '+textwrap.fill(display_names[i],42)) for i,name in enumerate(names)]
        fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.09),ncol=2,fontsize=9,frameon=False)
        fig.suptitle(prefix+stage+' cross-task error and recovery\n'
                     'Different item cohorts; not same-item precision/recall or evidence of statistical dominance',fontsize=14)
        fig.text(.5,.025,'Supplied marginal per-method 95% intervals, not joint intervals. '
                 'Undefined rates are omitted; no winner or fitted frontier. Source SHA-256 '+source[:12],ha='center',fontsize=10)
        save(fig,'cross-task-error-recovery')

    provenance = {'status':'exported_supplied_values_no_aggregation','created_utc':datetime.now(timezone.utc).isoformat(),
        'stage':section['stage'],'source_path':section['source_path'],'source_sha256':source,
        'review_metadata_sha256':section['review_metadata_sha256'],'reviewed_by':section['review']['reviewed_by'],
        'figure_scope_label':section['review'].get('figure_scope_label'),
        'identities':section['identities'],'method_order':names,'method_display_labels':display_names,
        'family_counts':section['family_counts'],
        'plotted_cell_metrics':data,'axis_definitions':AXES,'files':files,'matplotlib_version':matplotlib.__version__,
        'limits':section['limits']+['No interval recomputation, aggregation, winner selection, cost total or GPU dollar estimate.',
            'Cross-task axes use distinct family cohorts; marginal intervals do not quantify joint dominance.']}
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2,allow_nan=False)+'\n')
    return provenance


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('analysis','review','output'):
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--cross-task',action='store_true')
    args = p.parse_args()
    section = load_section(args.analysis,args.review,args.expected_sha256)
    result = export(section,args.output,cross_task=args.cross_task)
    print(json.dumps({'output':str(args.output),'stage':result['stage'],'source_sha256':result['source_sha256'],
                      'new_model_calls':0,'new_API_calls':0}))


if __name__ == '__main__':
    main()
