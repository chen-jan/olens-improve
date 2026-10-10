"""Export source-supplied signed comparison values; no inference or aggregation."""
import argparse
import copy
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
QUESTION_AXES = {
    'hallucination': AXES['hallucination'],
    'multihop_mt': 'Questions recovering all required bridge names (%) - higher is better',
    'chain_intermediates': 'Questions recovering the top named intermediate (%) - higher is better',
    'role_bound_association': 'Questions passing all three role choices (%) - higher is better'}
QUESTION_RULES = {
    'hallucination': 'Native readout error rate; not a question accuracy score.',
    'multihop_mt': 'All required names at the same layer; any layer in the original grid.',
    'chain_intermediates': 'Top named computed intermediate; any layer in the original grid.',
    'role_bound_association': 'All three MC answers at one site; any site in the original grid.'}
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


def question_data(section):
    """Copy pinned item aggregation; hallucination keeps its native ratio."""
    names = section['condition_ids']
    rows = section['original_item_rows']
    expected = {(name, family) for name in names for family in FAMILIES}
    indexed = {(row['condition'], row['family']): row for row in rows}
    if len(indexed) != len(rows) or set(indexed) != expected:
        raise ValueError('Require the complete unique original-item figure grid')
    cells = figure_data(section)
    output = {family: [] for family in FAMILIES}
    for family in FAMILIES:
        endpoint = ('original_grid_contradiction_rate' if family == 'hallucination'
                    else 'original_grid_item_pass_rate')
        counts = section['family_counts'][family]
        for i, name in enumerate(names):
            row = indexed[name, family]
            if row['endpoint'] != endpoint:
                raise ValueError('Unexpected original-item figure endpoint')
            metric = adapter.metric_checked(row['metric'], counts)
            if metric['numerator'] > metric['denominator']:
                raise ValueError('Question numerator exceeds its denominator')
            if family == 'hallucination':
                for key in ('numerator', 'denominator', 'value', 'ci95'):
                    if metric.get(key) != cells[family][i].get(key):
                        raise ValueError('Native hallucination rate must remain unchanged')
            elif metric['denominator'] != counts['items']:
                raise ValueError('Question denominator differs from intended items')
            output[family].append({'condition': name, **metric})
    return output


def paired_data(section, scope):
    """Copy supplied primary contrasts and attach their exact arm counts."""
    if scope not in ('cell', 'original_item'):
        raise ValueError('Unknown paired figure scope')
    source = question_data(section) if scope == 'original_item' else figure_data(section)
    indexed = {(row['condition'], family): row for family, rows in source.items() for row in rows}
    output, seen = {family: [] for family in FAMILIES}, set()
    for row in section['paired_rows']:
        if row['scope'] not in ('cell', 'original_item'):
            raise ValueError('Unknown supplied paired scope')
        family = row['family']
        if family not in FAMILIES:
            raise ValueError('Foreign paired figure family')
        endpoint = ('original_grid_contradiction_rate' if family == 'hallucination'
                    else 'original_grid_item_pass_rate') if row['scope'] == 'original_item' else (
                    'contradiction_rate' if family == 'hallucination' else 'cell_recovery')
        if row['scope'] == 'original_item' and row['endpoint'] != endpoint:
            raise ValueError('Unexpected original-item paired endpoint')
        if row['scope'] != scope or row['endpoint'] != endpoint:
            continue  # Auxiliary cell contrasts are not task recovery/error plots.
        identity = (row['baseline_condition'], row['condition'], family)
        if identity in seen:
            raise ValueError('Duplicate primary paired figure contrast')
        seen.add(identity)
        try:
            left, right = (indexed[name, family] for name in identity[:2])
        except KeyError as error:
            raise ValueError('Foreign paired figure condition') from error
        delta = right['value'] - left['value'] if left['value'] is not None and right['value'] is not None else None
        if (row['baseline'], row['proposed'], row['delta']) != (left['value'], right['value'], delta):
            raise ValueError('Paired figure values differ from source arm metrics')
        counts = section['family_counts'][family]
        if row['items'] != counts['items'] or row['independent_groups'] != counts['groups']:
            raise ValueError('Paired figure group/item cohort differs')
        output[family].append({**copy.deepcopy(row), 'baseline_metric': copy.deepcopy(left),
                               'proposed_metric': copy.deepcopy(right)})
    return output


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


def export(section, output, *, cross_task=False, zoom_cross_task=False,
           question_level=False, paired_deltas=False):
    # Keep plotting caches off HOME; no dependency/model loads or installs.
    os.environ.setdefault('MPLCONFIGDIR','/tmp/olens-improve-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    # Validate optional grids before creating an export directory.
    questions = question_data(section) if question_level or paired_deltas else None
    pairs = {scope: paired_data(section, scope) for scope in ('original_item', 'cell')} if paired_deltas else None
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

    if question_level:
        fig, axes = plt.subplots(2, 2, figsize=(17, max(10, extent*.75)), layout='constrained')
        for ax, family in zip(axes.flat, FAMILIES):
            for i, row in enumerate(questions[family]):
                at = positions[i]
                if row['value'] is None:
                    ax.text(2, at, 'Undefined', va='center', fontsize=9)
                else:
                    interval(ax, row, at)
                    ax.plot(100*row['value'], at, 'o', color='#244e69', markersize=5)
                count = f"{row['numerator']:,}/{row['denominator']:,}"
                ax.text(1.02, at, count, transform=ax.get_yaxis_transform(), va='center', fontsize=9)
            ax.set_yticks(positions, wrapped, fontsize=9)
            ax.set_ylim(extent-.5, -.65)
            ax.set_xlim(-1, 101)
            ax.set_xlabel(QUESTION_AXES[family], fontsize=10)
            groups = section['family_counts'][family]['groups']
            ax.set_title(labels.display_label(family)+f' - {groups} related groups\n'+QUESTION_RULES[family], fontsize=10)
            ax.grid(axis='x', alpha=.2)
            ax.spines[['top', 'right']].set_visible(False)
        fig.suptitle(prefix+stage+' original task endpoints\n'
                     'Dots: supplied rates; bars: supplied grouped 95% intervals; labels: numerator/denominator', fontsize=14)
        fig.supxlabel('Recovery is not complete explanation correctness. Hallucination keeps its readout denominator. '
                      'Source SHA-256 '+source[:12], fontsize=10)
        save(fig, 'family-question-rates')

    if paired_deltas:
        for scope, by_family in pairs.items():
            pages = (max(len(rows) for rows in by_family.values())+7)//8
            view = 'question' if scope == 'original_item' else 'cell'
            for page in range(pages):
                fig, axes = plt.subplots(2, 2, figsize=(20, 13), layout='constrained')
                for ax, family in zip(axes.flat, FAMILIES):
                    rows = by_family[family][page*8:(page+1)*8]
                    descriptions = [method_labels([row['condition']])[0]+' minus '+
                                    method_labels([row['baseline_condition']])[0] for row in rows]
                    ticks, places, height = label_positions(descriptions)
                    bounds = [100*x for row in rows for x in
                              [row['delta'], *(row.get('ci95_delta') or [])] if x is not None]
                    limit = max(5., max((abs(x) for x in bounds), default=0.)*1.1)
                    ax.axvline(0, color='#555555', linewidth=1, linestyle='--')
                    for at, row in zip(places, rows):
                        if row['delta'] is None:
                            ax.text(0, at, 'Undefined', va='center', fontsize=9)
                        else:
                            interval(ax, {'ci95': row.get('ci95_delta')}, at)
                            ax.plot(100*row['delta'], at, 'o', color='#244e69', markersize=5)
                        left, right = row['baseline_metric'], row['proposed_metric']
                        count = f"{left['numerator']:,}/{left['denominator']:,} -> {right['numerator']:,}/{right['denominator']:,}"
                        ax.text(1.02, at, count, transform=ax.get_yaxis_transform(), va='center', fontsize=8)
                    if not rows:
                        ax.text(.5, .5, 'No supplied comparisons on this page', transform=ax.transAxes, ha='center')
                    ax.set_yticks(places, ticks, fontsize=9)
                    ax.set_ylim(max(height-.5, .5), -.65)
                    ax.set_xlim(-limit, limit)
                    direction = 'left is lower error' if family == 'hallucination' else 'right is higher recovery'
                    ax.set_xlabel('Proposed minus baseline (percentage points); '+direction, fontsize=10)
                    ax.set_title(labels.display_label(family)+(' - native readout error' if family == 'hallucination' else f' - {view} recovery'), fontsize=11)
                    ax.grid(axis='x', alpha=.2)
                    ax.spines[['top', 'right']].set_visible(False)
                fig.suptitle(prefix+stage+f' paired {view} contrasts - page {page+1}/{pages}\n'
                             'Bars: supplied grouped 95% intervals; counts: baseline -> proposed', fontsize=14)
                fig.supxlabel('Missing intervals have no bar. Supplied warnings remain in provenance. '
                              'Intervals are unadjusted; no automatic ranking. Source SHA-256 '+source[:12], fontsize=10)
                save(fig, f'paired-{view}-deltas-{page+1:02d}')

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
                if not zoom_cross_task:
                    ax.annotate(str(i+1),(x,y),xytext=(4,4),textcoords='offset points',fontsize=8)
            if zoom_cross_task:
                def supplied_extent(rows):
                    values = [100*v for row in rows for v in
                              (row.get('ci95') or [row['value']]) if v is not None]
                    lo, hi = min(values), max(values)
                    pad = max(1., .10*(hi-lo))
                    return max(0.,lo-pad), min(100.,hi+pad)
                ax.set_xlim(*supplied_extent(data['hallucination']))
                ax.set_ylim(*supplied_extent(data[family]))
            else:
                ax.set_xlim(-1,101); ax.set_ylim(-1,101)
            ax.set_xlabel('Hall contradiction rate (%) - lower is better')
            ax.set_ylabel(AXES[family].split(' - ')[0])
            ax.set_title(labels.display_label(family)+' - separate cohort')
            ax.grid(alpha=.2)
        handles = [Line2D([],[],marker='o',linestyle='',color=colors(i%20),
                   label=f'{i+1}. '+textwrap.fill(display_names[i],42)) for i,name in enumerate(names)]
        fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.09),ncol=2,fontsize=9,frameon=False)
        fig.suptitle(prefix+stage+' cross-task error and recovery'+
                     (' — zoomed axes; values unchanged' if zoom_cross_task else '')+'\n'
                     'Different item cohorts; not same-item precision/recall or evidence of statistical dominance',fontsize=14)
        fig.text(.5,.025,'Supplied marginal per-method 95% intervals, not joint intervals. '
                 'Undefined rates are omitted; no winner or fitted frontier. Source SHA-256 '+source[:12],ha='center',fontsize=10)
        save(fig,'cross-task-error-recovery-zoom' if zoom_cross_task else 'cross-task-error-recovery')

    provenance = {'status':'exported_supplied_values_no_aggregation','created_utc':datetime.now(timezone.utc).isoformat(),
        'stage':section['stage'],'source_path':section['source_path'],'source_sha256':source,
        'review_metadata_sha256':section['review_metadata_sha256'],'reviewed_by':section['review']['reviewed_by'],
        'figure_scope_label':section['review'].get('figure_scope_label'),
        'cross_task_zoomed_axes':zoom_cross_task,
        'identities':section['identities'],'method_order':names,'method_display_labels':display_names,
        'family_counts':section['family_counts'],
        'plotted_cell_metrics':data,'axis_definitions':AXES,'files':files,'matplotlib_version':matplotlib.__version__,
        'limits':section['limits']+['No interval recomputation, aggregation, winner selection, cost total or GPU dollar estimate.',
            'Cross-task axes use distinct family cohorts; marginal intervals do not quantify joint dominance.']}
    if questions is not None:
        provenance.update(plotted_question_metrics=questions, question_axis_definitions=QUESTION_AXES,
                          question_task_rules=QUESTION_RULES)
    if pairs is not None:
        provenance.update(plotted_paired_metrics=pairs, paired_contrasts_per_family_page=8,
                          missing_paired_scopes=[scope for scope, rows in pairs.items() if not any(rows.values())])
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2,allow_nan=False)+'\n')
    return provenance


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('analysis','review','output'):
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--cross-task',action='store_true')
    p.add_argument('--zoom-cross-task',action='store_true',
                   help='Use clearly labeled supplied-interval axis ranges; no value or interval changes')
    p.add_argument('--question-level', action='store_true',
                   help='Also export original question aggregation; hallucination retains native readout error')
    p.add_argument('--paired-deltas', action='store_true',
                   help='Also export supplied primary question/cell contrasts with grouped intervals and exact arm counts')
    args = p.parse_args()
    section = load_section(args.analysis,args.review,args.expected_sha256)
    result = export(section,args.output,cross_task=args.cross_task or args.zoom_cross_task,
                    zoom_cross_task=args.zoom_cross_task, question_level=args.question_level,
                    paired_deltas=args.paired_deltas)
    print(json.dumps({'output':str(args.output),'stage':result['stage'],'source_sha256':result['source_sha256'],
                      'new_model_calls':0,'new_API_calls':0}))


if __name__ == '__main__':
    main()
