"""Render an editable expanded deck from complete results and root-reviewed prose.

No inference or statistical recomputation. Synthetic fixtures are layout QA only.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import textwrap

from build_slides import W, H, INK, MUTED, PAPER, TEAL, BLUE, LINE, text, rect, line, write_pptx, write_html
from build_expansion_report import checked_inputs, checked_reconstruction, read, TITLES, GROUPS
from build_expansion_dashboard import FAMILIES, ACTIVE, category, label

COLORS = ['8495A7', BLUE, TEAL, 'B57123', '7359AA', '388357', 'AA506D', '65713D', '447E97']
N_VALUES = (1, 2, 4, 8, 16, 32)
DEFAULT = ['raw_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32',
           'prune_loo_a32_0.001-n32', 'best_n_specificity_mean-n32',
           'likelihood_true_minus_mean_two_controls-n8',
           'consensus_semantic_v5_support0.125_compaton_vetoon-n16',
           'editing_round1-n32', 'editing_round2-n32']

@dataclass(frozen=True)
class SourceContract:
    schema_version: int
    status: str
    results_sha256: str
    manifest_sha256: str
    root_review_sha256: str
    conditions: tuple[str, ...]
    chart_conditions: tuple[str, ...]
    native_endpoints: dict[str, str]
    core_slide_count: int
    independent_reader_experiments: int = 0
    inference_calls: int = 0
    native_pptx_rendering_validated: bool = False
    reconstruction_sha256: str | None = None


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def finite(value, low=0, high=1):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high


def short_name(row):
    method, n = row['method'], row['n']
    fixed = {'raw_n1':'Original readout', 'capped_n1':'Original, four bullets',
        'best_n_exact':'Best complete readout', 'random_complete':'Random complete readout',
        'pooled_greedy_swap':'Combine original bullets', 'best_n_specificity_mean':'Average activation control',
        'best_n_specificity_max':'Strongest activation control', 'best_n_specificity_mean_abstain_nonpositive':'Average control; abstain if ≤0',
        'likelihood_true_minus_mean_two_controls':'Likelihood minus controls', 'own_mean_log_likelihood':'True-activation likelihood',
        'control_mean_log_likelihood':'Control-activation likelihood', 'editing_round1':'Edit once', 'editing_round2':'Edit twice',
        'exact_support_only':'Exact repetition only', 'pooled_specificity_mean':'Pooled bullets + specificity'}
    if method in fixed:
        return fixed[method]+f' · N={n}'
    if method.startswith('consensus_'):
        thresholds = row.get('thresholds', {})
        title = 'Semantic' if 'semantic_' in method else 'Exact repetition'
        if row.get('helper_reasoning_effort') == 'medium': title += ', medium'
        title += f" · support {round(thresholds.get('support_fraction',0)*16)}/16"
        if thresholds.get('compatibility_filter'): title += ' · compatible'
        if thresholds.get('contradiction_veto'): title += ' · veto'
        return title+f' · N={n}'
    if method.startswith('pooling_exact_support_lambda'):
        return 'Pool + repetition '+method.split('lambda')[1]+f' · N={n}'
    parent = ('Original capped' if '_n1_' in method else 'Best complete' if '_a32_' in method
              else 'Edit twice' if method.startswith('editing') else 'Pooled specificity' if method.startswith('pooled_specificity') else 'Pooled bullets')
    action = 'matched deletion' if 'random_delete' in method else 'small weights' if 'coefficient' in method else 'weak-bullet removal'
    return f'{parent} · {action} {method.rsplit("_",1)[-1]} · N={n}'


def percent(value):
    return 'Undefined' if value is None else f'{100*value:.1f}%'


def pp(value):
    return 'Undefined' if value is None else f'{100*value:+.1f} pp'


def ci(values, difference=False):
    if values is None: return 'unavailable'
    return f'{100*values[0]:+.1f} to {100*values[1]:+.1f}' if difference else f'{100*values[0]:.1f}–{100*values[1]:.1f}%'


def count(value):
    return f'{value:,.0f}' if float(value).is_integer() else f'{value:,.2f}'


def wrapped(value, width=58):
    return '\n'.join(textwrap.fill(part, width=width) for part in str(value).split('\n'))


def validate_review(review, active):
    for name in ('headline','resource_summary'):
        if not isinstance(review.get(name), str) or not review[name].strip(): raise ValueError('Missing reviewed '+name)
    if len(review['headline'])>210 or len(review['resource_summary'])>600:
        raise ValueError('Provide concise reviewed headline (≤210) and effort summary (≤600 characters)')
    findings = review.get('findings')
    if not isinstance(findings,list) or not 1 <= len(findings) <= 3: raise ValueError('Provide one to three reviewed findings')
    for f in findings:
        if not all(isinstance(f.get(k),str) and f[k].strip() for k in ('title','detail')): raise ValueError('Incomplete reviewed finding')
        if len(f['title'])>85 or len(f['detail'])>260: raise ValueError('Finding exceeds concise slide text contract')
    for group in GROUPS:
        f=review.get('method_findings',{}).get(group,{})
        if not all(isinstance(f.get(k),str) and f[k].strip() for k in ('finding','limits')): raise ValueError('Missing reviewed approach '+group)
    if not review.get('recommendations') or any(not isinstance(s,str) or not s.strip() for s in review['recommendations']): raise ValueError('Reviewed recommendations required')
    presentation=review.get('presentation',{})
    chosen=presentation.get('chart_conditions',DEFAULT)
    if not 2 <= len(chosen) <= 9 or len(set(chosen)) != len(chosen) or any(c not in active for c in chosen): raise ValueError('Chart list must name two to nine distinct active conditions')
    titles=presentation.get('short_titles',{})
    if any(c not in active or not isinstance(t,str) or len(t)>55 for c,t in titles.items()): raise ValueError('Invalid short method label')
    approaches=presentation.get('approaches',{})
    if set(approaches)!=set(GROUPS):raise ValueError('Provide seven reviewed approach slide contracts')
    for group,a in approaches.items():
        if not isinstance(a.get('action_title'),str) or not a['action_title'].strip() or len(a['action_title'])>95:raise ValueError('Concise reviewed approach action title required')
        if not 1<=len(a.get('bullets',[]))<=2 or any(not isinstance(t,str) or len(t)>150 for t in a['bullets']):raise ValueError('Provide one or two concise approach bullets')
        if not isinstance(a.get('mechanism_hypothesis'),str) or not 1<=len(a['mechanism_hypothesis'])<=160:raise ValueError('Explicit calibrated mechanism hypothesis required')
        if not a.get('example') or not a.get('contrast'):raise ValueError('Each approach requires an exact example and frozen comparison')
        choices=a.get('chart_conditions')
        if choices is not None and (not 1<=len(choices)<=6 or len(set(choices))!=len(choices) or any(c not in active or category(active[c]['method'])!=group for c in choices)):raise ValueError('Off-menu approach representative chart')
    return presentation,chosen


def resolve_example(pack, example):
    """Resolve exact prose against its named baseline or frozen parent output."""
    condition = pack['conditions'][example['condition']]
    groups = condition['families'][example['family']]
    reference = example.get('reference', 'capped_n1-n1')
    for kind in ('fixed_anchor', 'outcome_selected'):
        for row in groups.get(kind, []):
            if row['cell_id'] != example['cell_id'] or row['proposed']['text'] != example['selected_text']:
                continue
            original = row.get('original_baseline', row.get('baseline'))
            original_reference = row.get('original_baseline_condition', row.get('baseline_condition'))
            if reference == original_reference and original and original.get('text') == example['baseline_text']:
                return row, original, 'original_baseline'
            parent = row.get('parents', {}).get(reference)
            if (reference in condition.get('frozen_parent_condition_ids', []) and parent
                    and parent.get('status') == 'complete' and isinstance(parent.get('output'), dict)
                    and parent['output'].get('text') == example['baseline_text']):
                return row, parent['output'], 'parent'
    raise ValueError('Example does not match retained exact prose and named reference')


def validate_examples(presentation, qa=False, manifest_sha256=None):
    examples=list(presentation.get('examples',[]))+[a['example'] for a in presentation['approaches'].values()]
    if not 7 <= len(examples) <= 9: raise ValueError('Provide one exact example per approach; optional two overview examples')
    for e in examples:
        if qa:
            if e.get('synthetic_layout_fixture') is not True: raise ValueError('Fixture example must be marked synthetic')
            continue
        raw=Path(e['source_path']).read_bytes()
        if sha256(raw).hexdigest() != e['source_sha256']: raise ValueError('Example source changed')
        pack=json.loads(raw)
        if manifest_sha256 is not None and pack.get('manifest_sha256')!=manifest_sha256:raise ValueError('Example pack uses a different sealed inventory')
        found,before,role=resolve_example(pack,e)
        if not e.get('interpretation'): raise ValueError('Example interpretation is required')
        e['_source_context']=pack.get('contexts',{}).get(found.get('context_ref'))
        e['_reference_role']=role
        e['_source_reference']=before
        e['_original_baseline']=found.get('original_baseline',found.get('baseline'))
        e['_parent_endpoint_evidence']=found.get('parents',{}).get(e.get('reference'),{}).get('endpoint_evidence')
        for field,source_field in (('baseline_excerpt','baseline_text'),('selected_excerpt','selected_text')):
            if e.get(field) and e[field] not in e[source_field]: raise ValueError('Example excerpt is not exact retained text')
    return examples


def load(results_path, inventory_path, review_path, qa=False,reconstruction_path=None):
    if qa:
        results,rsha=read(results_path);inventory,isha=read(inventory_path);review,vsha=read(review_path)
        if not all(x.get('synthetic_layout_fixture') is True for x in (results,inventory,review)): raise ValueError('QA requires explicit synthetic inputs')
        if review.get('status')!='synthetic_layout_review' or review.get('results_sha256')!=rsha or results['manifest_sha256']!=isha or review['manifest_sha256']!=isha: raise ValueError('Synthetic source identity mismatch')
        active={r['condition_id']:r for r in inventory['conditions'] if r['status'] in ACTIVE};metrics={(r['condition'],r['family']):r['metric'] for r in results['cohorts']['full']['rows']};hashes={'results':rsha,'inventory':isha,'review':vsha}
    else:
        for path in (results_path,inventory_path,review_path):
            if read(path)[0].get('synthetic_layout_fixture'): raise ValueError('Synthetic QA sources cannot enter a final deck')
        results,inventory,review,active,metrics,hashes=checked_inputs(results_path,inventory_path,review_path)
    if len(active)!=70 or set(metrics)!={(c,f) for c in active for f in FAMILIES}: raise ValueError('Require exact frozen70 × four native endpoints')
    full=results['cohorts']['full']
    if full.get('missing_comparisons') or not full.get('comparison_family_complete'): raise ValueError('Frozen comparison family must be complete')
    expected={(c['condition'],c['reference'],f) for c in inventory['headline_comparison_family'] for f in FAMILIES}
    contrasts={(r['condition'],r['reference'],r['family']):r for r in full['comparisons']}
    if len(contrasts)!=len(full['comparisons']) or set(contrasts)!=expected: raise ValueError('Frozen paired contrast rows differ from inventory')
    for m in metrics.values():
        if m['value'] is not None and not finite(m['value']): raise ValueError('Invalid native proportion')
        if not all(finite(m[k],0,float('inf')) for k in ('numerator','denominator')) or m['numerator']>m['denominator']: raise ValueError('Invalid exact count')
        if m.get('ci95') is not None and (len(m['ci95'])!=2 or not all(finite(x) for x in m['ci95']) or m['ci95'][0]>m['ci95'][1]): raise ValueError('Invalid pointwise interval')
    for r in contrasts.values():
        if r['delta'] is not None and not finite(r['delta'],-1,1): raise ValueError('Invalid paired difference')
        for key in ('ci95_delta','simultaneous_ci95_delta'):
            v=r.get(key)
            if v is not None and (len(v)!=2 or not all(finite(x,-float('inf'),float('inf')) for x in v) or v[0]>v[1]): raise ValueError('Invalid difference interval')
    presentation,chosen=validate_review(review,active);examples=validate_examples(presentation,qa,hashes['inventory'])
    for e in examples:
        reference=e.get('reference','capped_n1-n1')
        if e['condition'] not in active or e['family'] not in FAMILIES or reference not in active: raise ValueError('Off-menu example or unspecified reference')
        if reference not in ('raw_n1-n1','capped_n1-n1') and (e['condition'],reference,e['family']) not in expected:raise ValueError('Example parent is not a frozen declared contrast')
    if reconstruction_path:
        if qa:
            reconstruction,xsha=read(reconstruction_path)
        else:
            reconstruction,xsha=checked_reconstruction(
                reconstruction_path,inventory,review,active,hashes)
        if presentation.get('reconstruction_sha256')!=xsha or reconstruction.get('manifest_sha256')!=hashes['inventory'] or reconstruction.get('quality_analysis_sha256')!=hashes['results']:raise ValueError('Reconstruction diagnostics are not bound to reviewed sources')
        if reconstruction.get('objective')!='1-squared_residual/squared_target' or reconstruction.get('solver')!='scipy_exact':raise ValueError('Incompatible reconstruction objective')
        seen=set()
        for row in reconstruction['rows']:
            key=row['condition'],row['family']
            if key in seen or key not in metrics:raise ValueError('Invalid reconstruction row identity')
            seen.add(key)
            if not 0<=row['scored_site_count']<=row['full_site_count']:raise ValueError('Invalid reconstruction coverage')
            if row['mean_fve'] is not None and not finite(row['mean_fve'],-float('inf'),1):raise ValueError('Invalid reconstruction score')
            for p in row.get('parent_comparisons',[]):
                if p['reference'] not in active or (p['mean_delta'] is not None and not finite(p['mean_delta'],-float('inf'),float('inf'))):raise ValueError('Invalid reconstruction comparison')
        results['_reconstruction']=reconstruction;hashes['reconstruction']=xsha
    elif presentation.get('reconstruction_sha256'):raise ValueError('Reviewed reconstruction artifact must be supplied')
    return results,inventory,review,active,metrics,hashes,presentation,chosen,contrasts,examples


def base(title, number, hashes, qa):
    status='SYNTHETIC LAYOUT QA · NO RESEARCH FINDINGS' if qa else 'EXPLORATORY · ALL 469 PREVIOUSLY INSPECTED QUESTIONS'
    return [rect(0,0,W,H,PAPER),text(60,28,1480,36,'ORACLE LENS / '+status,19,MUTED),
            text(60,84,1480,106,wrapped(title,60),46,serif=True),line(60,850,1540,850),
            text(60,866,1370,25,'Results '+hashes['results'][:12]+' · Inventory '+hashes['inventory'][:12]+' · Root review '+hashes['review'][:12],17,MUTED),
            text(1480,866,60,25,str(number),18,MUTED)]


def dot(x,y,color,r=7):return {'kind':'ellipse','x':x-r,'y':y-r,'w':2*r,'h':2*r,'color':color}


def native_panel(x,y,w,h,family,chosen,metrics,names,compact=False):
    items=[rect(x,y,w,h,'FFFFFF'),text(x+18,y+12,w-36,37,TITLES[family]+(' ↓' if family=='hallucination' else ' ↑'),26,bold=True)]
    label_w=w*.42;plot_x=x+label_w;plot_w=w*.38;step=(h-100)/len(chosen)
    for j,c in enumerate(chosen):
        m=metrics[c,family];yy=y+70+j*step;color=COLORS[j]
        items.append(text(x+18,yy-18,label_w-28,50,wrapped(names[c],31 if compact else 45),18 if compact else 22,color))
        items.append(line(plot_x,yy,plot_x+plot_w,yy,LINE))
        at=lambda z:plot_x+plot_w*z
        if m.get('ci95'):
            lo,hi=m['ci95'];items += [line(at(lo),yy,at(hi),yy,color,3),line(at(lo),yy-5,at(lo),yy+5,color),line(at(hi),yy-5,at(hi),yy+5,color)]
        if m['value'] is not None:items.append(dot(at(m['value']),yy,color,6))
        items.append(text(plot_x+plot_w+18,yy-20,w*.18-22,35,percent(m['value'])+('†' if native_warning(m) else ''),22,color,True))
        if not compact:items.append(text(plot_x+plot_w+18,yy+14,w*.18-22,28,count(m['numerator'])+'/'+count(m['denominator']),18,MUTED))
    for z in (0,.5,1):items.append(text(plot_x+plot_w*z-25,y+h-28,80,24,f'{100*z:g}%',18,MUTED))
    return items


def interval_warning(row):
    if row.get('warning'):return row['warning']
    if row.get('bootstrap_standard_error')==0:return 'zero bootstrap variation'
    if row.get('defined_draws',10000)<row.get('bootstrap_replicates',10000):return 'undefined ratio draws'
    if row.get('simultaneous_ci95_delta') is None:return 'joint interval unavailable'
    return None


def native_warning(metric):
    return '; '.join(metric.get('warnings', [])) or None


def reconstruction_comparison(row, quality_reference):
    """Use the named numeric comparison, or label an actual recorded parent."""
    parents = row.get('parent_comparisons', [])
    matching = next((p for p in parents if p['reference'] == quality_reference), None)
    if matching is not None:
        return matching
    return next((p for p in parents if p.get('kind') == 'frozen_parent'), None)


def tradeoff_intervals(horizontal, vertical, px, py, pw, ph, color):
    """Native marginal intervals on separate-bank axes, not a joint region."""
    if horizontal['value'] is None or vertical['value'] is None:return []
    xx=px+pw*horizontal['value'];yy=py-ph*vertical['value'];items=[]
    if horizontal.get('ci95') is not None:
        lo,hi=[px+pw*v for v in horizontal['ci95']]
        items += [line(lo,yy,hi,yy,color,2),line(lo,yy-4,lo,yy+4,color,2),line(hi,yy-4,hi,yy+4,color,2)]
    if vertical.get('ci95') is not None:
        lo,hi=[py-ph*v for v in vertical['ci95']]
        items += [line(xx,lo,xx,hi,color,2),line(xx-4,lo,xx+4,lo,color,2),line(xx-4,hi,xx+4,hi,color,2)]
    return items


def reconstruction_cell(row):
    """Display original mean/interval/coverage without filling unavailable fits."""
    if row is None:
        return 'Not supplied†\nCI unavailable\nCoverage unavailable'
    value=row['mean_fve'];bounds=row.get('mean_fve_ci95')
    warning=(value is None or bounds is None or row.get('mean_fve_warnings')
             or row['scored_site_count']<row['full_site_count'])
    mean='Unavailable' if value is None else f'{100*value:.2f}%'
    interval='CI unavailable' if bounds is None else f'{100*bounds[0]:.2f}–{100*bounds[1]:.2f}%'
    return mean+('†' if warning else '')+'\n'+interval+'\n'+count(row['scored_site_count'])+'/'+count(row['full_site_count'])+' sites'


def reconstruction_appendix(active, names, rows):
    """All frozen settings in inventory order, using the native appendix layout."""
    recorded={(r['condition'],r['family']):r for r in rows};conditions=list(active);pages=[]
    for start in range(0,len(conditions),5):
        selected=conditions[start:start+5]
        items=[text(70,195,1460,38,'Explained activation variance · grouped 95% CI · scored/intended sites',23,MUTED)]
        for j,f in enumerate(FAMILIES):items.append(text(510+j*255,248,245,65,TITLES[f],23,TEAL,True))
        for i,c in enumerate(selected):
            yy=330+i*94;items += [text(70,yy,420,85,wrapped(names[c],35),22),line(70,yy+85,1535,yy+85)]
            for j,f in enumerate(FAMILIES):items.append(text(510+j*255,yy,245,86,reconstruction_cell(recorded.get((c,f))),21))
        items.append(text(70,808,1460,30,'Secondary fit, not correctness · † unavailable/partial fit or interval; reasons and masks in notes.',20,MUTED))
        records=[{'condition':c,'label':names[c],'reconstruction':{f:recorded.get((c,f)) for f in FAMILIES}} for c in selected]
        notes=('Exact reconstruction records: '+json.dumps(records,ensure_ascii=False)+'\n'
               'Means and grouped pointwise 95% intervals are copied from the bound reconstruction artifact; '
               'displayed percentages equal raw fractions times100, with two-decimal display rounding only. '
               'Coverage is scored activation sites / all intended activation sites, not question-level quality. '
               'Unavailable values and intervals stay unavailable; zero fit is displayed as zero, never substituted for null. '
               'Partial valid-site masks, unavailable reasons, grouped-bootstrap warnings, actual paired parents and '
               'unrounded source values remain in these records. Raw unmodified N1 has no comparable saved fit. '
               'Inventory order, all settings, no ranking or significance filter.')
        pages.append((f'All reconstruction settings · {start+1}–{min(start+5,len(conditions))} of {len(conditions)}',items,notes))
    return pages


def reconstruction_scaling(rows, names):
    """Draw saved fit means and intervals; never manufacture a baseline fit."""
    conditions = [f'best_n_exact-n{n}' for n in N_VALUES] + [
        'pooled_greedy_swap-n16', 'pooled_greedy_swap-n32', 'capped_n1-n1']
    recorded = {(r['condition'], r['family']): r for r in rows}
    displayed = [recorded[c, f] for f in FAMILIES for c in conditions
                 if (c, f) in recorded]
    values = [v for r in displayed for v in
              ([r['mean_fve']] + list(r.get('mean_fve_ci95') or [])) if v is not None]
    low = min(0, math.floor(min(values, default=0) * 10) / 10)
    high = max(.5, math.ceil(max(values, default=.5) * 10) / 10)
    if high == low:
        high = low + .5
    items = []
    for i, family in enumerate(FAMILIES):
        x, y = 70 + (i % 2) * 760, 215 + (i // 2) * 285
        warning = any(r.get('status') != 'complete_comparable' or r.get('mean_fve_warnings')
                      for r in displayed if r['family'] == family)
        items += [rect(x, y, 710, 270, 'FFFFFF'),
                  text(x + 20, y + 10, 675, 36,
                       TITLES[family] + (' †' if warning else ''), 25, bold=True)]
        px, py, pw, ph = x + 70, y + 197, 600, 133
        at_y = lambda value: py - ph * (value - low) / (high - low)
        for v in (low, (low + high) / 2, high):
            items += [line(px, at_y(v), px + pw, at_y(v), LINE),
                      text(x + 6, at_y(v) - 11, 62, 24, f'{100 * v:g}%', 16, MUTED)]
        for j, n in enumerate(N_VALUES):
            items.append(text(px + pw * j / 5 - 12, py + 7, 48, 24, str(n), 17, MUTED))
        previous = None
        for j, n in enumerate(N_VALUES):
            row = recorded.get((f'best_n_exact-n{n}', family), {})
            value = row.get('mean_fve')
            xx = px + pw * j / 5
            if value is None:
                previous = None
                continue
            yy = at_y(value)
            if row.get('mean_fve_ci95'):
                lo, hi = row['mean_fve_ci95']
                items.append(line(xx, at_y(lo), xx, at_y(hi), BLUE, 2))
            if previous:
                items.append(line(*previous, xx, yy, BLUE, 3))
            items.append(dot(xx, yy, BLUE, 5))
            previous = xx, yy
        for n in (16, 32):
            row = recorded.get((f'pooled_greedy_swap-n{n}', family), {})
            if row.get('mean_fve') is None:
                continue
            xx = px + pw * N_VALUES.index(n) / 5 - 7
            yy = at_y(row['mean_fve'])
            if row.get('mean_fve_ci95'):
                lo, hi = row['mean_fve_ci95']
                items.append(line(xx, at_y(lo), xx, at_y(hi), 'B57123', 3))
            items.append(rect(xx - 5, yy - 5, 10, 10, 'B57123'))
        baseline = recorded.get(('capped_n1-n1', family), {})
        if baseline.get('mean_fve') is not None:
            yy = at_y(baseline['mean_fve'])
            items.append(line(px, yy, px + pw, yy, TEAL, 1))
            if baseline.get('mean_fve_ci95'):
                lo, hi = baseline['mean_fve_ci95']
                items.append(line(px + 7, at_y(lo), px + 7, at_y(hi), TEAL, 3))
        gains = []
        for condition, reference, title in [
                ('best_n_exact-n32', 'capped_n1-n1', 'Best32 vs capped'),
                ('pooled_greedy_swap-n32', 'best_n_exact-n32', 'Pool32 vs Best32')]:
            row = recorded.get((condition, family), {})
            pair = next((p for p in row.get('parent_comparisons', [])
                         if p['reference'] == reference and p.get('mean_delta') is not None), None)
            if pair:
                gains.append(title + ': ' + pp(pair['mean_delta']))
        items.append(text(x + 18, y + 237, 675, 26,
                          ' · '.join(gains) or 'No recorded paired parent gain', 16, MUTED))
    items.append(text(80, 804, 1450, 35,
                      'Explained variance · blue: best · amber: pooled · teal: capped · group 95% CI · † coverage/warnings in notes', 19, MUTED))
    notes = ('Secondary reconstruction diagnostic, not native task quality. Fractions are displayed as percentages; '
             'paired changes are percentage points. Site-weighted means and whole-related-group pointwise95% '
             'bootstrap intervals are copied without recomputation. No raw cap-exempt N1 fit is inferred. '
             'N1 best complete and capped may differ because recorded cleanup/fit scopes differ. '
             'Pooled markers are offset horizontally for legibility, at the labeled N. Missing means/intervals '
             'remain absent; partial coverage and zero/undefined variation warnings remain in exact rows. '
             'Each displayed parent gain names its exact paired reference; no difference-of-means is mislabeled paired. '
             'Objective, solver, normalization, masks, coverage and full records: ')
    return items, notes + json.dumps(displayed, ensure_ascii=False)


METHOD_STEPS={
 'selection':[('Sample a pool','Generate N descriptions for one captured vector.'),('Score each whole readout','Reconstruct the vector from its complete bullets.'),('Keep one','Compare best-scored with random selection.')],
 'consensus':[('Compare source statements','Find exact repeats or shared semantic content.'),('Apply recorded filters','Use support, compatibility and contradiction rules.'),('Keep original bullets','Labels select text; they do not rewrite it.')],
 'pruning':[('Start from a fixed parent','Use the original capped or best complete readout.'),('Remove weak bullets','Test leave-one-out loss or small fit coefficients.'),('Check deletion controls','Compare with matched random removal.')],
 'pooling':[('Open the shared pool','Take whole bullets from original descriptions.'),('Combine and swap','Seek a higher original reconstruction score.'),('Respect the text cap','Return at most four bullets and 256 tokens.')],
 'verification':[('Score the true vector','Measure reconstruction or readout likelihood.'),('Compare control vectors','Subtract average or strongest control evidence.'),('Select a full readout','Compare specificity with true/control-only scores.')],
 'editing':[('Use source-bound parents','Start with best complete and pooled readouts.'),('Propose bounded edits','Luna generates candidates; source lineage stays recorded.'),('Encode and score anew','Apply the original fit objective for one or two rounds.')],
 'combinations':[('Choose a recorded parent','Reuse a pooled, specific or twice-edited result.'),('Apply one frozen addition','Prune, match deletion or weight repetition.'),('Compare with the parent','Measure changes from the original method.')],
}


def approach_panel(x,y,family,conditions,metrics,names,selection=False):
    w,h=500,282;items=[rect(x,y,w,h,'FFFFFF'),text(x+12,y+8,w-24,34,TITLES[family]+(' ↓' if family=='hallucination' else ' ↑'),22,bold=True)]
    if selection:
        px,py,pw,ph=x+53,y+228,410,165
        for v in (0,.5,1):items += [line(px,py-ph*v,px+pw,py-ph*v,LINE),text(x+5,py-ph*v-10,45,22,f'{100*v:g}%',14,MUTED)]
        for method,color in [('best_n_exact',BLUE),('random_complete',MUTED)]:
            previous=None
            for j,n in enumerate(N_VALUES):
                m=metrics[f'{method}-n{n}',family];xx=px+pw*j/5
                if method=='best_n_exact':items.append(text(xx-10,py+10,40,25,str(n),16,MUTED))
                if m['value'] is None:previous=None;continue
                yy=py-ph*m['value'];items.append(dot(xx,yy,color,4))
                if m.get('ci95'):items.append(line(xx,py-ph*m['ci95'][0],xx,py-ph*m['ci95'][1],color,2))
                if previous:items.append(line(*previous,xx,yy,color,2))
                previous=xx,yy
        for c,color in [('raw_n1-n1','B57123'),('capped_n1-n1',TEAL)]:
            m=metrics[c,family]
            if m['value'] is not None:
                yy=py-ph*m['value'];items.append(line(px,yy,px+pw,yy,color,1))
                if m.get('ci95'):items.append(line(px,py-ph*m['ci95'][0],px,py-ph*m['ci95'][1],color,3))
        return items
    px,pw=x+245,168;step=216/max(1,len(conditions))
    for j,c in enumerate(conditions):
        yy=y+63+j*step;m=metrics[c,family];color=COLORS[j]
        title=names[c]
        if len(title)>53:title=title.replace('weak-bullet removal','prune').replace('matched deletion','random delete').replace('Best complete','Best').replace('Original capped','Capped').replace('Pooled specificity','Pool + specificity')
        items += [text(x+12,yy-14,220,45,wrapped(title,27),16,color),line(px,yy,px+pw,yy,LINE)]
        if m.get('ci95'):items.append(line(px+pw*m['ci95'][0],yy,px+pw*m['ci95'][1],yy,color,3))
        if m['value'] is not None:items.append(dot(px+pw*m['value'],yy,color,5))
        items.append(text(x+420,yy-13,73,30,percent(m['value'])+('†' if native_warning(m) else ''),16,color,True))
    for v in (0,.5,1):items.append(text(px+pw*v-14,y+h-22,56,23,f'{100*v:g}%',14,MUTED))
    return items


def pages_from(inputs,qa=False):
    results,inventory,review,active,metrics,hashes,pres,chosen,contrasts,examples=inputs
    full=results['cohorts']['full'];names={c:pres.get('short_titles',{}).get(c,short_name(r)) for c,r in active.items()};pages=[];refs=[]
    def add(title,items,note):
        pages.append({'title':title,'items':base(title,len(pages)+1,hashes,qa)+items,'notes':note+'\n\nExact source hashes: '+json.dumps(hashes)+'\nScope: exploratory full-bank; no new independent reader experiment.'})
    add(review.get('title','Oracle Lens: expanded comparison'),[
        text(70,240,1440,220,wrapped(review['headline'],65),44,TEAL,True),
        text(70,560,1400,130,'70 output settings · 469 questions · 19,435 fixed vectors\nFour task banks. Each endpoint keeps its native meaning.',30),
        text(70,760,1400,50,'Frozen model and readers · inference-time changes only',26,MUTED)],review['headline'])
    finding_items=[]
    for i,f in enumerate(review['findings']):
        y=220+i*185;finding_items += [rect(70,y,1460,164,'FFFFFF'),text(95,y+18,1400,48,f['title'],30,TEAL,True),text(95,y+75,1390,76,wrapped(f['detail'],110),25)]
    add('What the completed comparison shows',finding_items,'\n\n'.join(f['title']+'\n'+f['detail'] for f in review['findings']))
    pipeline=[]
    for i,(heading,body) in enumerate([('ONE VECTOR','A fixed layer and token position'),('SHARED POOL','Up to 32 original descriptions'),('SELECTED TEXT','Frozen reconstructor scores bullets'),('NATIVE JUDGE','Separate quality endpoint per task')]):
        x=65+i*385;pipeline += [rect(x,310,350,220,'FFFFFF'),text(x+20,337,315,54,heading,26,TEAL,True),text(x+20,420,310,92,wrapped(body,22),27)]
        if i<3:pipeline.append(text(x+345,377,40,65,'→',39,MUTED))
    pipeline += [text(70,610,1440,125,'Selection keeps whole source bullets. Editing adds bounded proposals.\nAt most four bullets and 256 Qwen tokens; raw baseline remains original.\nFit: fraction of variance explained (FVE), separate from semantic quality.',27),
                 text(70,741,1440,28,'Required intermediate entities; final answer is optional.',22,MUTED),
                 text(70,780,1440,35,'Every comparison uses the same captured activation identity.',24,MUTED)]
    add('One snapshot → a readable description',pipeline,'No training. Fixed Qwen3.6-27B model, released Oracle Lens and matched activation reconstructor. N refers to original shared descriptions per vector. Editing retains source lineage and uses fresh reconstructed vectors. The original raw baseline is cap-exempt.')
    for f in FAMILIES:
        caption=('Wrong specific readouts / all specific readouts, including off-topic ones.' if f=='hallucination'
                 else 'Required intermediate entities; final answer is optional.' if f=='multihop_mt'
                 else 'Required integer ranked first at any reading site / all original questions.' if f=='chain_intermediates'
                 else 'Questions with required content at any site / all original questions.')
        add(TITLES[f]+(' · fewer contradictions' if f=='hallucination' else ' · required-content recovery'),native_panel(70,210,1460,575,f,chosen,metrics,names)+[text(70,801,1440,35,caption+' Grouped 95% pointwise intervals; † see notes.',21,MUTED)],caption+'\n'+f'Independent related groups: {inventory["family_group_counts"][f]}. Pointwise group-bootstrap intervals. Quality is not averaged across tasks.\nAbsolute warnings: '+json.dumps({c:native_warning(metrics[c,f]) for c in chosen if native_warning(metrics[c,f])}))
        refs.extend({'condition':c,'family':f,'metric':metrics[c,f]} for c in chosen)
    scaling=[]
    for i,f in enumerate(FAMILIES):
        x=70+(i%2)*760;y=215+(i//2)*285;scaling += [rect(x,y,710,270,'FFFFFF'),text(x+20,y+10,675,42,TITLES[f],26,bold=True)]
        px=x+65;py=y+220;pw=600;ph=155
        for z in (0,.5,1):scaling += [line(px,py-ph*z,px+pw,py-ph*z,LINE),text(x+8,py-ph*z-13,56,28,f'{100*z:g}%',17,MUTED)]
        for method,color in [('best_n_exact',BLUE),('random_complete',MUTED)]:
            points=[]
            for j,n in enumerate(N_VALUES):
                m=metrics[f'{method}-n{n}',f];atx=px+pw*j/5;scaling.append(text(atx-14,py+8,50,28,str(n),18,MUTED)) if method=='best_n_exact' else None
                if m['value'] is None:points.append(None);continue
                aty=py-ph*m['value'];points.append((atx,aty));scaling.append(dot(atx,aty,color,5))
                if m.get('ci95'):scaling.append(line(atx,py-ph*m['ci95'][0],atx,py-ph*m['ci95'][1],color,2))
            for a,b in zip(points,points[1:]):
                if a and b:scaling.append(line(*a,*b,color,3))
    scaling += [text(80,804,1450,35,'N=1,2,4,8,16,32 · blue: best complete · gray: random complete · grouped 95% pointwise intervals',22,MUTED)]
    add('How quality changes with the sample budget',scaling,'Each line uses all six frozen original-pool sizes. N=1 is the scored/capped complete selection; it is not the raw cap-exempt baseline. Each task keeps its own endpoint and direction. Exact rows for all N are retained in the appendix.')
    gallery=[]
    for i,(group,title) in enumerate(GROUPS.items()):
        x=70+(i%2)*750;y=215+(i//2)*143;body=review['method_findings'][group]
        gallery += [rect(x,y,710,128,'FFFFFF'),text(x+18,y+14,675,40,title,26,TEAL,True),text(x+18,y+63,675,52,wrapped(pres.get('approach_captions',{}).get(group,body['finding']),65),20)]
    add('Every approach keeps a distinct purpose',gallery,'\n\n'.join(GROUPS[g]+'\n'+review['method_findings'][g]['finding']+'\nLimits: '+review['method_findings'][g]['limits'] for g in GROUPS))
    trade=[]
    for i,f in enumerate(FAMILIES[1:]):
        x=70+i*500;y=235;px=x+75;py=580;pw=385;ph=250
        trade += [text(x,y,465,70,TITLES[f]+' recovery ↑',24,bold=True),line(px,py,px+pw,py),line(px,py,px,py-ph)]
        for z in (0,.5,1):trade += [text(px+pw*z-15,py+12,58,26,f'{100*z:g}%',17,MUTED),text(x+12,py-ph*z-12,55,28,f'{100*z:g}%',17,MUTED)]
        for j,c in enumerate(chosen):
            a,b=metrics[c,'hallucination'],metrics[c,f]
            if a['value'] is None or b['value'] is None:continue
            xx=px+pw*a['value'];yy=py-ph*b['value'];trade += tradeoff_intervals(a,b,px,py,pw,ph,COLORS[j]);trade.append(dot(xx,yy,COLORS[j],6));trade.append(text(xx+7,yy-12,38,27,str(j+1),16,COLORS[j],True))
        trade.append(text(x+40,625,430,48,'Transcript contradictions → · lower is better',18,MUTED))
    for j,c in enumerate(chosen):
        trade.append(text(80+(j%3)*500,690+(j//3)*34,480,34,wrapped(str(j+1)+'. '+names[c],49),16,COLORS[j]))
    trade += [text(70,797,1440,21,'Axis-wise pointwise 95% intervals; paired differences in appendix.',18,MUTED),text(70,824,1440,20,'Separate question banks · no joint uncertainty region, per-question joint success or pooled accuracy.',18,MUTED)]
    add('Practical tradeoffs across separate task banks',trade,'Same method appears in three separate cross-bank panels. X is contradiction rate in 149 transcript questions; Y is native recovery in the indicated 100/120 question bank. Coordinates are not paired item observations and do not identify a joint task-level tradeoff. Whiskers copy each axis native absolute grouped pointwise95% interval; no cross-bank covariance/joint uncertainty region is estimated. Missing intervals remain absent. Exact native source records: '+json.dumps({c:{f:metrics[c,f] for f in FAMILIES} for c in chosen})+'\nLegend: '+json.dumps({str(i+1):names[c] for i,c in enumerate(chosen)}))
    eligible=[c for c in chosen if (c,'capped_n1-n1',FAMILIES[0]) in contrasts]
    pairs=pres.get('paired_contrasts') or [{'condition':c,'reference':'capped_n1-n1','family':f} for c in eligible[:2] for f in FAMILIES]
    if not 1<=len(pairs)<=8:raise ValueError('Choose one to eight paired rows for main deck')
    selected=[]
    for p in pairs:
        key=(p['condition'],p['reference'],p['family'])
        if key not in contrasts:raise ValueError('Main contrast outside frozen comparison menu')
        selected.append(contrasts[key])
    for simultaneous in (False,True):
        items=[];key='simultaneous_ci95_delta' if simultaneous else 'ci95_delta'
        maximum=max(.05,max((abs(z) for r in selected for z in (r.get(key) or ([r['delta']] if r['delta'] is not None else [0]))),default=.05));maximum=math.ceil(maximum/.05)*.05
        px,pw=740,555;at=lambda z:px+pw*(z/maximum+1)/2
        items += [line(at(0),230,at(0),765,LINE,2)]
        for i,r in enumerate(selected):
            yy=260+i*(490/len(selected));color=BLUE;v=r.get(key);title=TITLES[r['family']]+' · '+names[r['condition']]+' vs '+names[r['reference']]
            items += [text(70,yy-20,645,55,wrapped(title,48),21),text(1310,yy-20,225,35,pp(r['delta'])+('†' if interval_warning(r) else ''),23,color,True)]
            if v:items += [line(at(v[0]),yy,at(v[1]),yy,color,4),dot(at(r['delta']),yy,color,6)] if r['delta'] is not None else []
            else:items.append(text(765,yy-15,520,42,'Interval unavailable†',23,MUTED))
        for z in (-maximum,0,maximum):items.append(text(at(z)-50,767,150,30,f'{100*z:+g}pp',21,MUTED))
        items.append(text(70,807,1460,34,'Difference = method−reference. Negative helps contradictions; positive helps recovery. † See notes.',21,MUTED))
        add('Frozen paired changes · '+('simultaneous 95% intervals' if simultaneous else 'pointwise 95% intervals'),items,'Shared whole-related-group bootstrap draws within each task. These intervals are '+('approximate joint coverage over the entire frozen contrast family, not only shown rows.' if simultaneous else 'pointwise paired percentile intervals; they do not adjust the whole menu.')+'\n'+json.dumps(selected)+'\n† Zero bootstrap variation or undefined ratio draws must not be interpreted as robust certainty.')
    coverage=[]
    for i,f in enumerate(FAMILIES):
        x=70+(i%2)*755;y=215+(i//2)*290;coverage += [rect(x,y,710,270,'FFFFFF'),text(x+18,y+12,675,42,TITLES[f],26,bold=True)]
        for j,c in enumerate(chosen[:4]):
            secondary=full.get('secondary',{}).get(c,{}).get(f,{})
            numerator=secondary.get('coverage',{}).get('empty_abstentions');denominator=secondary.get('coverage',{}).get('expected_cells');empty='Unavailable' if numerator is None or not denominator else f'{100*numerator/denominator:.1f}% empty'
            other=secondary.get('assertion_share' if f=='hallucination' else 'cell_recovery',{});value='Unavailable' if not other.get('denominator') else percent(other['numerator']/other['denominator'])
            coverage += [text(x+18,y+68+j*45,400,40,wrapped(names[c],33),18,COLORS[j]),text(x+430,y+68+j*45,250,38,value+' · '+empty,19)]
    coverage.append(text(70,810,1460,31,'Secondary: transcript assertion share; other tasks: cell recovery. Empty outputs remain in intended coverage.',21,MUTED))
    add('Recovery and output coverage measure different things',coverage,'Secondary diagnostics shown from exact retained ratios, without newly computed uncertainty. Transcript assertion share is specific outputs/intended outputs; other cell recovery is passing cells/intended cells. These are not the native whole-question headline endpoint. Role agent/action/patient components are not fabricated if absent from source.')
    lengths=[]
    for i,f in enumerate(FAMILIES):
        x=70+(i%2)*755;y=215+(i//2)*285;lengths += [rect(x,y,710,260,'FFFFFF'),text(x+18,y+12,675,40,TITLES[f],26,bold=True)]
        domain=max(256,max((full.get('lengths',{}).get(c,{}).get(f,{}).get('mean_qwen_tokens_all_intended') or 0 for c in chosen[:4]),default=0))
        for j,c in enumerate(chosen[:4]):
            value=full.get('lengths',{}).get(c,{}).get(f,{}).get('mean_qwen_tokens_all_intended');yy=y+74+j*40;lengths.append(text(x+18,yy-15,365,48,wrapped(names[c],32),18,COLORS[j]))
            if value is not None:lengths += [rect(x+385,yy-7,240*value/domain,12,COLORS[j]),text(x+632,yy-19,70,36,f'{value:.0f}',20)]
        lengths.append(text(x+383,y+226,310,25,f'0 → {domain:.0f} Qwen tokens',18,MUTED))
    lengths.append(text(70,807,1460,35,'Means over all intended cells, including empty outputs. Natural output lengths; no new length matching.',22,MUTED))
    add('Output length is part of practical method behavior',lengths,'Exact saved mean Qwen-token counts over all intended cells. Output cap is 256 except the original raw baseline. Each panel uses its displayed domain without truncating a longer raw readout. This comparison does not isolate quality independently of length.')
    case_items=[];case_notes=[]
    for i,e in enumerate(examples[:2]):
        x=70+i*755;width=710;before=e.get('baseline_excerpt',e['baseline_text']);after=e.get('selected_excerpt',e['selected_text'])
        if len(before)>350 or len(after)>350:raise ValueError('Provide exact case excerpts ≤350 characters for legibility')
        if len(e['interpretation'])>180:raise ValueError('Provide a concise reviewed case interpretation ≤180 characters')
        reference=e.get('reference','capped_n1-n1')
        reference_label=('Original output · '+('four-bullet cap' if reference=='capped_n1-n1' else 'raw, cap-exempt')) if reference in ('raw_n1-n1','capped_n1-n1') else 'Parent output · frozen reference'
        case_items += [rect(x,220,width,567,'FFFFFF'),text(x+20,235,width-40,55,TITLES[e['family']]+' · '+names[e['condition']],24,TEAL,True),text(x+20,310,width-40,32,reference_label,20,MUTED),text(x+20,355,width-40,155,wrapped(before,47 if len(examples)==2 else 92),22),text(x+20,525,width-40,32,'Selected output',20,MUTED),text(x+20,565,width-40,155,wrapped(after,47 if len(examples)==2 else 92),22)]
        case_items.append(text(x+20,725,width-40,61,wrapped(e['interpretation'],60 if len(examples)==2 else 110),18,TEAL))
        case_notes.append(e['cell_id']+'\n'+e['interpretation']+'\nReference: '+reference+'\nReference fulltext: '+e['baseline_text']+'\nSelected fulltext: '+e['selected_text']+'\nSource: '+e.get('source_sha256','SYNTHETIC')+'\nOriginal source context: '+json.dumps(e.get('_source_context'),ensure_ascii=False)+'\nOriginal baseline retained: '+json.dumps(e.get('_original_baseline'),ensure_ascii=False))
    case_items.append(text(70,794,1460,43,'Selected examples illustrate changes and failures; they do not estimate prevalence.',23,MUTED))
    add('What a score gain can keep—and what it can miss',case_items,'\n\n'.join(case_notes)+'\nOfficial judgments remain unchanged.')
    add('Practical effort includes more than cached selection',[
        rect(70,255,445,255,'FFFFFF'),text(95,285,395,60,'Original samples',32,TEAL,True),text(95,375,395,115,'N=1,2,4,8,16,32\nGenerating the pool is separate work.',27),
        rect(580,255,445,255,'FFFFFF'),text(605,285,395,60,'Helper requests',32,TEAL,True),text(605,375,395,115,'Semantic labels and edits\nReuse exact request identities.',27),
        rect(1090,255,445,255,'FFFFFF'),text(1115,285,395,60,'Fresh scoring',32,TEAL,True),text(1115,375,395,115,'Likelihood and edited vectors\nAdd GPU and CPU work.',27),
        text(70,560,1440,180,wrapped(review['resource_summary'],100),26),text(70,787,1440,48,'Cache replay does not establish new-input latency or serving-time GPU cost.',24,MUTED)],review['resource_summary']+'\nPer-input sample budgets are frozen scientific parameters, not an amortized cost measure. Benchmark judgment is a separate evaluation instrument. No new-input latency or dollar-per-GPU-request number is inferred.')
    add('Uncertainty follows the independent question groups',[
        text(75,235,1430,70,f'{full["bootstrap_replicates"]:,} shared grouped bootstrap draws',37,TEAL,True),
        text(75,355,1410,140,'Pointwise: uncertainty for one result or paired change.\nSimultaneous: approximate coverage over defined, nondegenerate contrasts.',30),
        text(75,565,1410,145,'Zero variation is not robust certainty.\nUndefined ratio draws and unavailable intervals stay visible.',30),
        text(75,750,1420,42,f'{full["declared_contrasts"]} declared contrasts; '+str(full.get('joint_interval_contrasts','not recorded'))+' receive joint intervals.',24,MUTED),
        text(75,797,1420,35,'More activation sites do not create more independent questions.',24,MUTED)],f'{full["declared_contrasts"]} declared contrast rows. Effective nondegenerate contrasts: '+str(full.get('effective_non_degenerate_contrasts','not recorded'))+'. Related-group counts: '+json.dumps(inventory['family_group_counts'])+'\nResample whole related groups, shared draws across methods within each task. Max standardized centered bootstrap error supplies approximate simultaneous intervals only for defined nondegenerate contrasts. Adjustment does not undo prior outcome access or create fresh held-out evidence.')
    add('What this comparison does—and does not—support',[
        text(75,235,1430,120,'All 469 questions were inspected before expansion.\nThese comparisons remain exploratory.',35,TEAL,True),
        text(75,420,1400,190,'Required entities, numbers and roles can appear inside inaccurate prose.\nNatural-length effects are part of the practical comparison.\nJudge disagreements stay separate from official rates.',29),
        text(75,695,1430,100,'Independent readers remain postponed.\nNo J++, NLA or new reconstructor experiment is implied.',28,MUTED)],'Full-bank adaptation and previously inspected TEST history remain disclosed. No new heldout evaluation, reader experiment, causal identification of internal belief, or uniform winner across task-specific endpoints is claimed.')
    rec_items=[]
    if len(review['recommendations'])>4:raise ValueError('At most four concise reviewed recommendations fit the main deck')
    for i,s in enumerate(review['recommendations']):
        if len(s)>250:raise ValueError('Recommendation exceeds concise slide contract')
        rec_items += [text(75,240+i*130,1420,110,wrapped(s,82),31,TEAL if i==0 else INK,i==0)]
    add('Recommended next decisions',rec_items,'\n\n'.join(review['recommendations']))
    original_pages=list(pages)
    method_pages=[]
    recon={(r['condition'],r['family']):r for r in results.get('_reconstruction',{}).get('rows',[])}
    for group,title in GROUPS.items():
        a=pres['approaches'][group];members=[c for c,r in active.items() if category(r['method'])==group]
        diagram=[]
        for i,(heading,body) in enumerate(METHOD_STEPS[group]):
            x=70+i*500;diagram += [rect(x,275,455,255,'FFFFFF'),text(x+22,300,405,75,wrapped(heading,25),30,TEAL,True),text(x+22,415,405,100,wrapped(body,30),27)]
            if i<2:diagram.append(text(x+455,367,45,60,'→',37,MUTED))
        diagram += [text(75,600,1440,120,wrapped(a['mechanism_hypothesis'],95),28),text(75,770,1440,45,'Mechanism hypothesis · reconstruction fit and semantic quality remain separate.',25,MUTED)]
        add(title+' · how it works',diagram,review['method_findings'][group]['finding']+'\n'+review['method_findings'][group]['limits']+'\nMechanism hypothesis: '+a['mechanism_hypothesis']);method_pages.append(pages[-1])
        graph_conditions=a.get('chart_conditions',members[:6]);selection=group=='selection'
        if selection:graph_conditions=members
        pair=a['contrast'];key=pair['condition'],pair['reference']
        if key[0] not in members or any((*key,f) not in contrasts for f in FAMILIES):raise ValueError('Approach comparison outside frozen menu')
        left=[]
        for i,t in enumerate(a['bullets']):left.append(text(75,218+i*83,440,80,wrapped('• '+t,38),22))
        delta=[contrasts[*key,f] for f in FAMILIES]
        left += [text(75,390,440,33,'Quality Δ vs '+names[key[1]],19,TEAL,True),text(75,430,440,62,'Transcript '+pp(delta[0]['delta'])+' · Entities '+pp(delta[1]['delta'])+'\nNumbers '+pp(delta[2]['delta'])+' · Roles '+pp(delta[3]['delta']),18)]
        fits=[];fit_notes=[]
        for f in FAMILIES:
            row=recon.get((key[0],f),{});p=reconstruction_comparison(row,key[1])
            if not p or p['mean_delta'] is None:
                fits.append('Unavailable')
            else:
                delta_pp = p['mean_delta'] * 100
                shown = f'{delta_pp:+.3f} pp' if 0 < abs(delta_pp) < .1 else pp(p['mean_delta'])
                fits.append(shown + ('†' if p.get('warning') else ''))
            fit_notes.append({'family':f,'score':row,'comparison':p,'quality_reference':key[1],
                              'reconstruction_reference':p['reference'] if p else None})
        if recon:
            fit_refs={p['reconstruction_reference'] for p in fit_notes if p['reconstruction_reference']}
            reference=names[next(iter(fit_refs))] if len(fit_refs)==1 else 'recorded parents; see notes'
            left += [text(75,501,440,35,wrapped('Reconstruction change (pp) vs '+reference,52),15,TEAL,True),text(75,543,440,42,'Transcript '+fits[0]+' · Entities '+fits[1]+'\nNumbers '+fits[2]+' · Roles '+fits[3],15)]
        e=a['example'];before=e.get('baseline_excerpt',e['baseline_text']);after=e.get('selected_excerpt',e['selected_text'])
        if len(before)>100 or len(after)>100:raise ValueError('Approach examples need exact excerpts ≤100 characters')
        parent=e.get('reference','capped_n1-n1') not in ('raw_n1-n1','capped_n1-n1')
        left += [text(75,590,440,30,('Parent example · ' if parent else 'Example · ')+TITLES[e['family']],18,TEAL,True),text(75,631,440,63,wrapped(('Parent: ' if parent else 'Before: ')+before,43),18),text(75,702,440,63,wrapped('After: '+after,43),18),text(75,773,440,50,wrapped(e['interpretation'],51),16,MUTED)]
        graphs=[]
        for i,f in enumerate(FAMILIES):graphs += approach_panel(550+(i%2)*520,215+(i//2)*300,f,graph_conditions,metrics,names,selection)
        if selection:caption='All 14 variants: blue best · gray random · orange raw · teal capped · N=1,2,4,8,16,32'
        else:caption=f'{len(graph_conditions)} of {len(members)} variants plotted · all {len(members)} variants and exact counts in appendix'
        graphs.append(text(550,817,1010,26,caption+' · pointwise 95%; † see notes',15,MUTED))
        add(a['action_title'],left+graphs,'Approach: '+group+'\nReviewed evidence: '+json.dumps(a,ensure_ascii=False)+'\nTask-specific interpretation: '+json.dumps(review['method_findings'][group].get('task_comparison'),ensure_ascii=False)+'\nAll variants: '+json.dumps(members)+'\nPlotted: '+json.dumps(graph_conditions)+'\nExact native metrics: '+json.dumps({c:{f:metrics[c,f] for f in FAMILIES} for c in members})+'\nExact paired changes: '+json.dumps(delta)+'\nReconstruction diagnostics: '+json.dumps(fit_notes)+'\nFVE measures original reconstruction fit; its scale is not semantic faithfulness. Quality comparisons stay task-native. Example context: '+json.dumps(e.get('_source_context'),ensure_ascii=False));method_pages.append(pages[-1])
    reconstruction_page = None
    if results.get('_reconstruction') is not None:
        fit_items, fit_notes = reconstruction_scaling(results['_reconstruction']['rows'], names)
        source = results['_reconstruction']
        add('Reconstruction fit across the sample budgets', fit_items,
            fit_notes + '\nArtifact SHA: ' + hashes['reconstruction'] +
            '\nFit contract: ' + json.dumps({k:source.get(k) for k in
                ('objective','solver','normalization','vector_contract_sha256','limits')}, ensure_ascii=False))
        reconstruction_page = pages[-1]
    # User-requested narrative: findings and tradeoffs first, then seven visual/result pairs.
    pages[:]=[original_pages[i] for i in (0,1,9,2)]+method_pages+[original_pages[i] for i in (7,12,13,15,16,17,18)]
    if reconstruction_page is not None:
        pages.insert(19, reconstruction_page)
    for i,p in enumerate(pages,1):p['items'][5]['text']=str(i)
    core_count=len(pages)
    # All70 settings, five rows per page; no ranking or significance filter.
    conditions=list(active)
    for start in range(0,len(conditions),5):
        items=[text(70,195,1460,38,'Native proportions · grouped 95% pointwise intervals · exact numerator/denominator',23,MUTED)]
        for j,f in enumerate(FAMILIES):items.append(text(510+j*255,248,245,65,TITLES[f]+(' ↓' if f=='hallucination' else ' ↑'),23,TEAL,True))
        for i,c in enumerate(conditions[start:start+5]):
            yy=330+i*94;items += [text(70,yy,420,85,wrapped(names[c],35),22),line(70,yy+85,1535,yy+85)]
            for j,f in enumerate(FAMILIES):
                m=metrics[c,f];items.append(text(510+j*255,yy,245,86,percent(m['value'])+('†' if native_warning(m) else '')+'\n'+ci(m.get('ci95'))+'\n'+count(m['numerator'])+'/'+count(m['denominator']),22))
        add(f'All settings · {start+1}–{min(start+5,len(conditions))} of 70',items,'Full condition IDs and native metric records: '+json.dumps([{ 'condition':c,'label':label(active[c]),'metrics':{f:metrics[c,f] for f in FAMILIES}} for c in conditions[start:start+5]])+'\n† Exact warnings remain in each metric record; a zero-width all-zero/all-one recovery interval does not establish certainty.\nNo significance-based shortlist. Every setting remains visible.')
    if results.get('_reconstruction') is not None:
        for title,items,notes in reconstruction_appendix(active,names,results['_reconstruction']['rows']):
            add(title,items,notes+'\nReconstruction artifact SHA: '+hashes['reconstruction'])
    declared=inventory['headline_comparison_family']
    for start in range(0,len(declared),4):
        items=[text(70,195,1460,52,'Δ in percentage points · P: paired pointwise 95% · S: simultaneous 95% · †: see notes',23,MUTED)]
        for j,f in enumerate(FAMILIES):items.append(text(510+j*255,258,245,50,TITLES[f],22,TEAL,True))
        records=[]
        for i,c in enumerate(declared[start:start+4]):
            yy=330+i*116;items += [text(70,yy,420,110,wrapped(names[c['condition']]+'\nvs '+names[c['reference']],40),18),line(70,yy+109,1535,yy+109)]
            for j,f in enumerate(FAMILIES):
                r=contrasts[c['condition'],c['reference'],f];warning=interval_warning(r);records.append({**r,'display_warning':warning});items.append(text(510+j*255,yy,245,85,pp(r['delta'])+'\nP '+ci(r.get('ci95_delta'),True)+'\nS '+ci(r.get('simultaneous_ci95_delta'),True)+('†' if warning else ''),20))
        add(f'Frozen contrasts · {start+1}–{min(start+4,len(declared))} of {len(declared)}',items,'Difference=method−reference. Native better direction differs: negative helps contradiction rate; positive helps recovery. Rows share related-group draws. P and S are separate uncertainty statements. † A degenerate or undefined interval is not robust zero uncertainty.\n'+json.dumps(records))
    add('Provenance and complete source artifacts',[
        text(70,235,1440,105,'WorkspaceBench · four original task banks\nQwen3.6-27B · released Oracle Lens + matched reconstructor',31),
        text(70,405,1440,175,'Results\n'+hashes['results']+'\nInventory\n'+hashes['inventory'],23,MUTED),
        text(70,630,1440,90,'Root-reviewed interpretation\n'+hashes['review'],23,MUTED),text(70,780,1440,50,'Editable PowerPoint. PDF uses the same geometry through a local HTML mirror.',24,TEAL)],'Benchmark revision92d763e722377f5bfae045e829a308ab5919a820; Qwen model revision6a9e13bd6fc8f0983b9b99948120bc37f49c13e9; released Oracle Lens/reconstructor revisionc95215d5d2f6250f20c305ae55c6e4d7569f92dc. Luna supplies recorded judgments; multihop uses unchanged deterministic matching. Native PowerPoint rendering parity has not been claimed. Root-review/source contract governs all findings.')
    return pages,refs,core_count


def build(results_path,inventory_path,review_path,output,qa=False,reconstruction_path=None):
    if not qa and reconstruction_path is None:
        raise ValueError('Final deck requires source-bound reconstruction diagnostics')
    inputs=load(results_path,inventory_path,review_path,qa,reconstruction_path);pages,refs,core=pages_from(inputs,qa)
    output=Path(output)
    if output.exists():raise ValueError('Use a new immutable output directory')
    output.mkdir(parents=True)
    results,inventory,review,active,metrics,hashes,_,chosen,_,_=inputs
    contract=SourceContract(1,'SYNTHETIC LAYOUT QA' if qa else 'root_reviewed_complete_exploratory',hashes['results'],hashes['inventory'],hashes['review'],tuple(active),tuple(chosen),{f:metrics[next(iter(active)),f]['name'] for f in FAMILIES},core,reconstruction_sha256=hashes.get('reconstruction'))
    for name,path in [('results-source.json',results_path),('inventory-source.json',inventory_path),('review-source.json',review_path)]: (output/name).write_bytes(Path(path).read_bytes())
    if reconstruction_path:(output/'reconstruction-source.json').write_bytes(Path(reconstruction_path).read_bytes())
    (output/'source-contract.json').write_text(json.dumps(asdict(contract),indent=2)+'\n')
    write_pptx(pages,output/'expanded.pptx');write_html(pages,output/'expanded.html')
    # Reused primitives have historical proof metadata; replace metadata only.
    from pptx import Presentation
    ppt=Presentation(output/'expanded.pptx');ppt.core_properties.title=review.get('title','Expanded Oracle Lens comparison');ppt.core_properties.subject=contract.status;ppt.save(output/'expanded.pptx')
    html_path=output/'expanded.html';html_path.write_text(html_path.read_text().replace('<title>DRAFT validation style proof</title>','<title>Expanded Oracle Lens comparison</title>'))
    (output/'geometry.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2)+'\n')
    (output/'speaker-notes.md').write_text('\n\n'.join(f"# {i}. {p['title']}\n\n{p['notes']}" for i,p in enumerate(pages,1))+'\n')
    receipt={'status':contract.status,'synthetic_layout_fixture':qa,'slides':len(pages),'core_slides':core,'all_conditions':len(active),'all_condition_families':len(metrics),'all_frozen_contrast_rows':len(inputs[8]),'all_reconstruction_source_rows':len(results.get('_reconstruction',{}).get('rows',[])),'reconstruction_appendix_slides':sum(p['title'].startswith('All reconstruction settings') for p in pages),'source_hashes':hashes,'builder_sha256':digest(__file__),'primitive_builder_sha256':digest(Path(__file__).with_name('build_slides.py')),'metric_refs':refs,'inference_calls':0,'pdf_route':'Same-content geometry HTML mirror; not a native PPTX conversion','native_pptx_rendering_validated':False,'outputs':{p.name:digest(p) for p in output.iterdir() if p.is_file()}}
    (output/'build.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt


def render_pdf(output,chrome,node='node'):
    output=Path(output).resolve();receipt=json.loads((output/'build.json').read_text());html=output/'expanded.html';pdf=output/'expanded.pdf'
    if digest(html)!=receipt['outputs']['expanded.html'] or pdf.exists():raise ValueError('Changed HTML or existing PDF')
    checker=Path(__file__).with_name('check_expansion_slides_layout.mjs').resolve()
    check=subprocess.run([str(node),str(checker),str(chrome),str(html),str(output/'layout-qa.json')],capture_output=True,timeout=45)
    if check.returncode:raise RuntimeError('Text-box layout QA failed; inspect retained layout-qa.json before building a new output')
    driver=Path(__file__).with_name('render_slides.mjs').resolve();done=subprocess.run([str(node),str(driver),str(chrome),str(html),str(pdf)],capture_output=True,timeout=45);(output/'pdf-driver-stderr.log').write_bytes(done.stderr)
    if done.returncode:raise RuntimeError('Local PDF mirror rendering failed; stderr retained')
    import pymupdf as fitz
    from PIL import Image
    doc=fitz.open(pdf)
    if len(doc)!=receipt['slides']:raise ValueError('Unexpected PDF page count')
    inspected=[]
    for i,page in enumerate(doc):
        if abs(page.rect.width-960)>1 or abs(page.rect.height-540)>1 or 'ORACLE LENS /' not in page.get_text() or 'Root review' not in page.get_text():raise ValueError('Slide dimensions/header/footer clipped')
        inspected.append({'slide':i+1,'characters':len(page.get_text())})
    selected=sorted(set([0,2,3,4,5,7,9,11,13,15,17,receipt['core_slides'],len(doc)-2]))
    sheet=Image.new('RGB',(1280,360*math.ceil(len(selected)/2)),'#D6E1EC')
    for j,i in enumerate(selected):
        p=output/f'slide-{i+1:02d}.png';doc[i].get_pixmap(matrix=fitz.Matrix(4/3,4/3)).save(p)
        with Image.open(p) as image:sheet.paste(image.resize((640,360)),((j%2)*640,(j//2)*360))
    sheet.save(output/'contact-sheet.png');doc.close()
    report={'pages':receipt['slides'],'pdf_sha256':digest(pdf),'driver_sha256':digest(driver),'layout_checker_sha256':digest(checker),'layout_report_sha256':digest(output/'layout-qa.json'),'pdf_page_points':[960,540],'native_pptx_rendering_validated':False,'route':receipt['pdf_route'],'checked_pages':inspected,'preview_slides':[i+1 for i in selected]};(output/'render.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',type=Path,required=True);p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'));p.add_argument('--review',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--reconstruction',type=Path);p.add_argument('--qa-fixture',action='store_true');p.add_argument('--chrome',type=Path);p.add_argument('--node',default='node');a=p.parse_args();r=build(a.results,a.inventory,a.review,a.output,a.qa_fixture,a.reconstruction)
    if a.chrome:render_pdf(a.output,a.chrome,a.node)
    print(json.dumps({k:r[k] for k in ('status','slides','core_slides','all_conditions','inference_calls')}))
if __name__=='__main__':main()
