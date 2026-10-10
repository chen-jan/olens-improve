"""Render all measured variants without calculating or filling scientific results."""
import html
import math
import re
try:
    import dashboard_qualitative as qualitative
except ModuleNotFoundError:
    from scripts import dashboard_qualitative as qualitative

TASKS = {'hallucination': 'Transcript contradictions', 'multihop_mt': 'Multi-hop facts',
         'chain_intermediates': 'Arithmetic steps', 'role_bound_association': 'Who did what'}
METHODS = {
 'sample_selection': ('Choose a complete readout', 'Keep one of several descriptions.', '006-selector-pilot.md',
   'Computed, but not all quality-judged: released 80-step solver and random choices at every prefix. The larger-development N1–32 curve is shown when its reviewed complete source is attached.'),
 'consensus': ('Keep repeated claims', 'Count agreement across distinct samples.', '015-consensus-pilot.md',
   'Whole-bullet exact and semantic variants were measured. Extracted-claim consensus stopped after eight audited cells: self-containedness failed; the planned 32-cell quality comparison was not completed. Unsafe merges remain a limitation.'),
 'pruning': ('Remove weak bullets', 'Delete bullets that contribute little to the reconstruction match.', '011-cached-combinations.md',
   'Quality-measured thresholds: .001 and .005. Computed only: zero-loss, coefficient .01/.05 and single-sample pruning variants. Within-bullet detail pruning was not separately measured.'),
 'pooling': ('Combine bullets', 'Choose up to four original bullets from the shared pool.', '006-selector-pilot.md',
   'N16 and N32 greedy selection, one swap pass and complete-sample fallback were measured. Fresh sampling on residuals was deferred under the shared 32-sample cap.'),
 'contrastive_checks': ('Compare against other activations', 'Check whether a description fits this vector better than fixed control vectors.', '007-likelihood-pilot.md',
   'Measured: mean/max control scores, abstention and three likelihood selections. Number/entity/direction near-misses are isolated diagnostics, not a deployed selector. Verified balanced negation pairs were unavailable.'),
 'editing': ('Edit a readout', 'Propose small edits and accept them with the local reconstruction score.', '010-editing-scoring.md',
   'Two rounds, four proposals per round, were measured. This small pilot showed no aggregate recovery gain; larger-scale editing remains unmeasured, not ruled out. Separate deletion-only/substitution-only or other acceptance objectives were not independently measured.'),
 'independent_checks': ('Check with another reader', 'Inspect token support from another frozen reader.', '006-jpp-development-reader.md',
   'J++ source fixtures, an eight-cell diagnostic and 36 paired diagnostic sets completed. No quality-judged selector improvement was measured. Fitting-data overlap is unresolved. A second compatible reconstruction reader is unavailable; the optional layer-42 reader was not run.'),
 'combinations': ('Combine approaches', 'Test components together and compare with their unchanged parents.', '020-pooled-specificity.md',
   'Measured: pooling/pruning, contrastive/pruning, editing/pruning, exact repeat support/pooling and contrastive pooling, with applicable matched-count random deletion. Reliable semantic filtering before pooling was not established. This is not an exhaustive combination search.'),
}


def esc(v): return html.escape(str(v), quote=True)


def label(condition):
    """Readable variant labels; keep the exact identifier in the expandable table."""
    if ' vs ' in condition:return ' versus '.join(label(c) for c in condition.split(' vs '))
    simple = {'raw_n1': 'Released original, unmodified', 'capped_n1': 'Capped original, whole bullets only',
      'best_n_exact': 'Best reconstruction', 'random_complete': 'Random complete choice',
      'best_n_specificity_mean': 'Compare other activations: mean',
      'best_n_specificity_max': 'Compare other activations: strongest control',
      'best_n_specificity_mean_abstain_nonpositive': 'Mean comparison, allow abstention',
      'pooled_greedy_swap': 'Combine bullets, then swap', 'editing_round1': 'Edit: one round',
      'editing_round2': 'Edit: two rounds', 'likelihood_true_minus_mean_two_controls': 'Likelihood: true minus controls',
      'own_mean_log_likelihood': 'Likelihood: true activation only',
      'control_mean_log_likelihood': 'Likelihood: controls only', 'exact_support_only': 'Exact repetition only',
      'pooled_specificity_mean': 'Combine bullets with control comparison'}
    base,sep,n=condition.rpartition('-n')
    if not sep: base,n=condition,''
    if base in simple: name=simple[base]
    elif base.startswith('consensus_'):
        threshold=re.search(r'support([0-9.]+)',base)
        name=('Exact repetition' if 'exact' in base else 'Semantic repetition')
        if 'medium' in base:name+=': helper with more reasoning'
        elif 'v5' in base:name+=': repaired helper'
        elif 'v4' in base:name+=': initial helper'
        if threshold:
            fraction=float(threshold[1]);name+=('; soft preference, no minimum' if fraction==0 else f'; at least {fraction*100:g}% of samples')
        if 'compat' in base:name+='; conflict check '+('on' if 'compaton' in base else 'off')
        if 'veto' in base:name+='; contradiction veto '+('off' if 'vetooff' in base else 'on')
    else:
        replacements=(('best_n_specificity_mean','Mean control comparison'),('pooled_greedy_swap','Combine bullets'),
          ('editing_round2','Two-round edit'),('prune_loo_a32','Best of 32, remove weak bullets'),
          ('random_delete_matched_a32','Best of 32, random deletion'),('pooling_exact_support_lambda','Pooling + exact support, weight '),
          ('random_delete_matched','matched-count random deletion'),('then_prune','then remove weak bullets'))
        name=base
        for old,new in replacements:name=name.replace(old,new)
        name=name.replace('_',' ')
    return name+(f' · {n} samples' if n else '')


def headline(row):
    endpoint=row.get('endpoint','').lower()
    return ('contradiction' in endpoint and 'specific' in endpoint) or endpoint in ('cell mention/binding recovery','cell recovery')


def validate_row(row):
    v=row.get('value');ci=row.get('ci')
    if v is not None and (not isinstance(v,(int,float)) or not math.isfinite(v)):raise ValueError('Nonfinite method result')
    if ci is not None and (len(ci)!=2 or not all(math.isfinite(x) for x in ci) or ci[0]>ci[1]):raise ValueError('Invalid method interval')


def measure_label(endpoint):
    lower=endpoint.lower()
    if 'fve' in lower:return endpoint+' (activation reconstruction fit, not accuracy)'
    paired=lower.startswith('paired delta: ')
    base=lower.removeprefix('paired delta: ')
    change='change in percentage points; ' if paired else ''
    if 'contradiction' in lower and 'specific' in lower:
        return endpoint+' ('+change+'error per activation; lower is better)'
    if base in ('cell recovery','cell mention/binding recovery'):
        return endpoint+' ('+change+'match per activation; higher is better)'
    if 'whole items' in lower:return 'Questions with at least one match'
    return endpoint


def table(rows, paired=False):
    if not rows:return '<p class="missing">No measured results in this snapshot.</p>'
    out='<div class="table-scroll"><table><thead><tr><th>Task / variant</th><th>Measure</th><th>Result</th><th>95% interval</th><th>Counts / coverage</th></tr></thead><tbody>'
    for r in rows:
        validate_row(r);v=r.get('value');ci=r.get('ci');end=r.get('endpoint','')
        count_unit=r.get('value_unit')=='count_per_output' or 'per produced output' in end.lower() or 'per intended output' in end.lower()
        paired_rate=paired and not count_unit and 'FVE' not in end
        rate=paired_rate or (not count_unit and 'FVE' not in end and r.get('numerator') is not None)
        val='Unavailable' if v is None else (f'{v*100:+.2f} pp' if paired_rate else f'{v*100:.2f}%' if rate else f'{v:.5g}')
        interval='Not estimated' if ci is None else (' to '.join(f'{x*100:+.2f}' if paired_rate else f'{x*100:.2f}' if rate else f'{x:.5g}' for x in ci)+(' pp' if paired_rate else '%' if rate else ''))
        count=f'{r.get("numerator")}/{r.get("denominator")}' if r.get('numerator') is not None else 'No count denominator'
        coverage=f'{r.get("eligible_count","unknown")} eligible {r.get("eligibility_unit","(unit not supplied)")}; {r.get("missing_count","unknown")} missing'
        out+=f'<tr><td>{esc(TASKS.get(r.get("family"),r.get("family","Diagnostic")))}<br>{esc(label(r["condition"]))}<details><summary>Exact variant and uncertainty</summary><code>{esc(r["condition"])}</code><p>{esc(r.get("uncertainty","Not supplied"))}</p></details></td><td>{esc(measure_label(end))}<small>{esc(r.get("cohort",""))}</small></td><td>{val}</td><td>{interval}</td><td>{esc(count)}<small>{esc(coverage)}</small></td></tr>'
    return out+'</tbody></table></div>'


def rate_plot(rows,title,cohort):
    rows=[r for r in rows if headline(r)]
    if not rows:return '<p class="missing">No quality rate was measured for this task and stage. This is not a zero result.</p>'
    source_cohorts='; '.join(dict.fromkeys(r.get('cohort','Cohort not supplied') for r in rows))
    groups=sorted({int(m[1]) for r in rows if (m:=re.search(r'(\d+) (?:(?:independent|related) )?groups',r.get('uncertainty','')))})
    group_text=', '.join(map(str,groups))+' related groups' if groups else 'Group count not supplied'
    maximum=max([r['value'] for r in rows if r.get('value') is not None]+[r['ci'][1] for r in rows if r.get('ci')]+[.05])
    maximum=min(1,math.ceil(maximum/(.05 if maximum<.3 else .2))*(.05 if maximum<.3 else .2))
    measure='Error rate per activation; lower is better, not accuracy.' if rows[0].get('family')=='hallucination' else 'Match rate per activation; higher is better.'
    out=f'<h4>{esc(title)}</h4><p class="small">{esc(cohort)} · {esc(source_cohorts)}. {measure} Zero-based 0–{maximum*100:g}% axis; points are rates, supplied lines are grouped 95% intervals. Missing intervals are marked “Not estimated” in the table, not treated as zero uncertainty.</p><p class="small">{esc(group_text)}. Activations are not independent questions. Exact intervals and counts are in the tables below.</p>'
    for r in rows:
        validate_row(r);v=r.get('value');ci=r.get('ci')
        if v is None:continue
        if not 0<=v<=1 or ci is not None and not 0<=ci[0]<=ci[1]<=1:raise ValueError('Rate plot requires rates, not fit or paired differences')
        x=lambda t:8+224*t/maximum
        svg='<svg viewBox="0 0 240 28" role="img" aria-label="'+esc(label(r['condition']))+'"><line x1="8" y1="14" x2="232" y2="14" stroke="#D6E1EC"/>'
        if ci is not None:svg+=f'<path d="M{x(ci[0])} 9V19M{x(ci[0])} 14H{x(ci[1])}M{x(ci[1])} 9V19" fill="none" stroke="#087F83" stroke-width="2"/>'
        svg+=f'<circle cx="{x(v)}" cy="14" r="4" fill="#246AB3"/><title>{esc(r.get("uncertainty","Interval not supplied"))}</title></svg>'
        count=f'{r.get("numerator")}/{r.get("denominator")}'
        out+=f'<div class="variant-row"><span>{esc(label(r["condition"]))}</span>{svg}<strong>{v*100:.1f}%<small>{esc(count)}</small></strong></div>'
    out+=f'<div class="variant-row chart-axis"><span></span><span>0%<span style="float:right">{maximum*100:g}%</span></span><span></span></div>'
    return out


def normalized_signed(section,conditions):
    out=[]
    for r in section.get('cell_rows',[]):
        if r['condition'] not in conditions:continue
        m=r['metric'];out.append({'family':r['family'],'condition':r['condition'],
          'endpoint':'Contradictions / specific readouts' if r['family']=='hallucination' else 'Cell recovery',
          'value':m['value'],'ci':m['ci95'],'numerator':m['numerator'],'denominator':m['denominator'],
          'eligible_count':m['items'],'eligibility_unit':'items','missing_count':0,'cohort':'Validation: complete original grids',
          'uncertainty':f'{m["items"]} items; grouped 95% interval; {m["independent_groups"]} related groups'+('; '+m['warning'] if m.get('warning') else '')})
    return out


def validation_auxiliary(section,conditions):
    labels={'assertion_share':'Specific assertions / intended outputs',
      'off_topic_rate':'Off-topic / specific readouts',
      'false_span_tally':'False spans per intended output',
      'true_claim_tally':'True claims per intended output',
      'unverifiable_claims_per_output':'Unverifiable claims per intended output'}
    rows=[]
    for r in section.get('auxiliary_rows',[]):
        if r['condition'] not in conditions:continue
        m=r['metric'];rows.append({'family':r['family'],'condition':r['condition'],
          'endpoint':labels.get(r['endpoint'],r['endpoint']),'value':m['value'],'ci':m['ci95'],
          'numerator':m['numerator'],'denominator':m['denominator'],
          'value_unit':'count_per_output' if r['endpoint'] in ('false_span_tally','true_claim_tally','unverifiable_claims_per_output') else 'rate',
          'eligible_count':m['items'],'eligibility_unit':'items','missing_count':0,
          'cohort':'Validation: complete original grids',
          'uncertainty':f'{m["items"]} items; {m["independent_groups"]} related groups; grouped 95% interval'+('; '+m['warning'] if m.get('warning') else '')})
    return rows


def paired_plot(rows,family):
    rows=[r for r in rows if r.get('family')==family and headline(dict(r,endpoint=r.get('endpoint','').removeprefix('Paired delta: ')))]
    if not rows:return '<p class="missing">No paired headline difference is supplied for this task.</p>'
    # A shared symmetric axis includes all retained paired intervals; no re-estimation.
    bound=max([.05]+[abs(x) for r in rows for x in (r.get('ci') or [r['value']])])
    x=lambda v:120+112*v/bound
    cohorts='; '.join(dict.fromkeys(r.get('cohort','Cohort not supplied') for r in rows))
    out=f'<h4>{esc(TASKS[family])}: change against the named comparator</h4><p class="small">{esc(cohorts)}. Paired percentage-point differences in per-activation outcomes; grouped 95% intervals. '+('Negative is better.' if family=='hallucination' else 'Positive is better.')+'</p>'
    for r in rows:
        validate_row(r);v=r['value'];ci=r.get('ci')
        svg='<svg viewBox="0 0 240 28" role="img" aria-label="Paired change"><path d="M120 3V25" stroke="#98ACBF"/>'
        if ci:svg+=f'<path d="M{x(ci[0])} 9V19M{x(ci[0])} 14H{x(ci[1])}M{x(ci[1])} 9V19" stroke="#087F83" fill="none"/>'
        svg+=f'<circle cx="{x(v)}" cy="14" r="4" fill="#246AB3"/></svg>'
        out+=f'<div class="variant-row"><span>{esc(label(r["condition"]))}<small>{esc(r.get("uncertainty","Group count not supplied"))}</small></span>{svg}<strong>{v*100:+.2f}<small>percentage points</small></strong></div>'
    return out+f'<p class="small">Axis: −{bound*100:.2f} to +{bound*100:.2f} percentage points. A line crossing zero indicates that this interval includes no change; it is not a significance gate.</p>'


def full_dev_rows(report):
    out=list(report.get('full_development',{}).get('metrics',[]))
    extra=report.get('full_development_a32',{})
    if extra and extra.get('reviewed_by')!='root':raise ValueError('Unreviewed larger-development results')
    for r in extra.get('cell_endpoints',[]):
        m=r['proposed'];out.append({'family':r['family'],'condition':'best_n_exact-n32',
          'endpoint':'Contradictions / specific readouts' if r['family']=='hallucination' else 'Cell recovery',
          'value':m['value'],'ci':m['ci95'],'numerator':m['numerator'],'denominator':m['denominator'],
          'eligible_count':m['items'],'eligibility_unit':'items','missing_count':0,'cohort':'Full development: complete original grids',
          'uncertainty':f'Grouped 95% interval; {m["independent_groups"]} related groups'+('; '+m['warning'] if m.get('warning') else '')})
    frozen=report.get('frozen_development_pruning',{})
    if frozen and frozen.get('reviewed_by')!='root':raise ValueError('Unreviewed development pruning evidence')
    present={(r['family'],r['condition']) for r in out if headline(r)}
    for r in frozen.get('rows',[]):
        if ('chain_intermediates',r['condition']) in present:continue
        out.append({'family':'chain_intermediates','condition':r['condition'],'endpoint':'Cell recovery',
          'value':r['passed_cells']/r['expected_cells'],'ci':None,'numerator':r['passed_cells'],
          'denominator':r['expected_cells'],'eligible_count':r['expected_items'],'eligibility_unit':'items','missing_count':0,
          'cohort':frozen['scope'],'uncertainty':f'{r["expected_items"]} items; {frozen["independent_groups"]} related groups; interval not estimated in this source'})
    return out


def costs(rows):
    if not rows:return '<p class="small">A separate per-variant cost was not supplied. Shared generation/encoding costs are shown below; absence is not zero cost.</p>'
    out='<div class="table-scroll"><table><tr><th>Component</th><th>Value and unit</th><th>What was measured</th></tr>'
    for r in rows:
        value='Not measured' if r.get('value') is None else str(r['value'])
        out+=f'<tr><td>{esc(r.get("component",r.get("condition","")))}</td><td>{esc(value)} {esc(r.get("unit",""))}</td><td>{esc(r.get("scope",""))}<br>{esc(r.get("measurement",""))}</td></tr>'
    return out+'</table></div>'


def traces(rows):
    if not rows:return '<p class="small">No retained example is attached to this method in the published summary. Quality rates alone do not establish that every claim is faithful.</p>'
    out=''
    for t in rows:
        out+=f'<details class="trace"><summary>{esc(t.get("kind","Reviewed example"))} · {esc(t.get("cell_id",""))}</summary><div class="trace-pair"><div><h5>Before</h5><pre>{esc(t.get("baseline",""))}</pre></div><div><h5>After</h5><pre>{esc(t.get("selected",""))}</pre></div></div><p>{esc(t.get("evidence",""))}</p><p>{esc(t.get("interpretation",""))}</p></details>'
    return out


def scaling(report):
    rows=[r for r in report.get('methods',{}).get('sample_selection',{}).get('scaling',[]) if r['label'].split(':')[0] in TASKS]
    if not rows:return ''
    out='<section id="sampling"><div class="section-heading"><div><h2>Does asking for more samples help?</h2><p>More samples can help some tasks and hurt others. Supplied error bars are grouped 95% intervals; missing intervals are not treated as zero uncertainty.</p></div></div>'+development_scaling(report)+'<details class="info"><summary>Earlier shared pilot: six saved prefixes, partial grids</summary><div class="charts">'
    for s in rows:
        family=s['label'].split(':')[0];points=s['points'];xs={n:48+48*i for i,n in enumerate((1,2,4,8,16,32))};y=lambda v:190-145*v
        if len({p['n'] for p in points})!=len(points) or any(p['n'] not in xs for p in points):raise ValueError('Duplicate or unsupported sampling prefix')
        for p in points:
            validate_row(p)
            if p['value'] is not None and not 0<=p['value']<=1 or p.get('ci') is not None and not 0<=p['ci'][0]<=p['ci'][1]<=1:raise ValueError('Sampling curve requires benchmark rates')
        out+=f'<article class="task-chart"><h3>{esc(TASKS.get(family,family))}</h3><p class="small">'+('Error per activation; lower is better, not accuracy' if family=='hallucination' else 'Match per activation; higher is better')+'</p><svg class="sampling-plot" viewBox="0 0 350 235" role="img" aria-label="Sampling curve, rates and grouped intervals">'
        for v in (0,.5,1):out+=f'<path d="M40 {y(v)}H310" stroke="#D6E1EC"/><text x="34" y="{y(v)+4}" text-anchor="end">{v*100:g}%</text>'
        for a,b in zip(points,points[1:]):
            if a['value'] is not None and b['value'] is not None:out+=f'<path d="M{xs[a["n"]]} {y(a["value"])}L{xs[b["n"]]} {y(b["value"])}" stroke="#246AB3" fill="none"/>'
        for p in points:
            x=xs[p['n']];v=p['value'];ci=p.get('ci')
            if v is not None:
                if ci:out+=f'<path d="M{x-4} {y(ci[0])}H{x+4}M{x} {y(ci[0])}V{y(ci[1])}M{x-4} {y(ci[1])}H{x+4}" stroke="#087F83"/>'
                out+=f'<circle cx="{x}" cy="{y(v)}" r="4" fill="#246AB3"/>'
            out+=f'<text x="{x}" y="211" text-anchor="middle">{p["n"]}</text>'
        matches=[r for r in report['methods']['sample_selection'].get('metrics',[]) if r.get('family')==family and r.get('condition')=='best_n_exact-n32' and headline(r)]
        match=re.search(r'(\d+) (?:(?:independent|related) )?groups',matches[0].get('uncertainty','')) if matches else None
        group_text=(match[1]+' related groups; sites are not independent examples.') if match else 'Independent group count not supplied.'
        out+='<text x="175" y="232" text-anchor="middle">Number of shared samples</text></svg><p class="small">'+esc(s['cohort'])+'</p><p class="small">'+esc(group_text)+'</p><details><summary>Exact values, counts and intervals</summary><table><tr><th>Samples</th><th>Rate</th><th>95% interval</th><th>Denominator</th></tr>'
        for p in points:
            ci=p.get('ci');interval='Not estimated' if ci is None else f'{ci[0]*100:.2f}–{ci[1]*100:.2f}%'
            value='Unavailable' if p['value'] is None else f'{p["value"]*100:.2f}%'
            out+=f'<tr><td>{p["n"]}</td><td>{value}</td><td>{interval}</td><td>{p.get("count","Not supplied")}</td></tr>'
        out+='</table>'
        if matches:out+='<p class="small">'+esc(matches[0].get('uncertainty','Group count not supplied'))+'</p>'
        out+='</details></article>'
    out+='</div><p class="small">Shared pilot: 31 development items, 189 sites, partial original grids; only 2–8 related groups per task. These are selections from saved prefixes, not six independent generation runs. These few observations do not establish a scaling law.</p>'
    out+='</details><details class="info"><summary>Reconstruction and sample cost are separate from quality</summary><p>These curves show benchmark quality. No per-prefix reconstruction-fit curve is attached to this report snapshot; we do not infer one from quality. Reconstruction-fit diagnostics, when supplied, remain separate inside the contrastive-method tables. Sample count is the experimental prefix cost, not complete new-input latency or GPU dollars.</p>'+costs(report['methods']['sample_selection'].get('cost_components',[]))+'</details></section>'
    return out


def development_scaling(report):
    section=report.get('development_scaling')
    if not section:
        return '<p class="missing">The complete development curve is not attached to this snapshot; missing points are not zero.</p>'
    expected=['raw_n1-n1','capped_n1-n1']+[f'best_n_exact-n{n}' for n in (1,2,4,8,16,32)]
    if section.get('reviewed_by')!='root' or section.get('source_sha256')!='bc582289b378a286a72ce239148dfc6f22aece28e79f47124cfa9a2ee12cc5cf':
        raise ValueError('Require the reviewed complete development scaling source')
    measurement=section['measurement'];conditions=measurement['conditions']
    if [c['condition'] for c in conditions]!=expected:
        raise ValueError('Keep the exact eight development conditions')
    out='<h3>Complete development comparison</h3><p class="small">121 items · 5,236 readout sites. The six points reuse nested prefixes of the same saved pool. Raw and shortened originals are separate reference lines. Rates need not improve steadily; these observations do not establish a scaling law.</p><div class="charts">'
    rows=[]
    xs={n:48+48*i for i,n in enumerate((1,2,4,8,16,32))}
    for family,title in TASKS.items():
        metrics=[];endpoint='contradiction_rate' if family=='hallucination' else 'cell_recovery'
        for condition in conditions:
            if not condition['measurement_complete'] or set(condition['families'])!=set(TASKS):
                raise ValueError('Development curves require all complete families')
            f=condition['families'][family]
            if f['missing_stage1'] or f['missing_stage2']:raise ValueError('Missing development judgments')
            m=f['metrics'][endpoint]
            row={'family':family,'condition':condition['condition'],'endpoint':'Contradictions / specific readouts' if family=='hallucination' else 'Cell recovery',
                'value':m['value'],'ci':m['ci95'],'numerator':m['numerator'],'denominator':m['denominator'],
                'eligible_count':m['items'],'eligibility_unit':'items','missing_count':0,
                'cohort':'Full development: complete original grids',
                'uncertainty':f'{m["items"]} items; {m["independent_groups"]} related groups; grouped 95% interval'+('; '+m['warning'] if m.get('warning') else '')}
            validate_row(row)
            if row['value'] is not None and not 0<=row['value']<=1:raise ValueError('Development rates must lie in [0,1]')
            rows.append(row);metrics.append((condition,m,row))
        info=metrics[0][1]
        upper=max([.05]+[m['value'] for _,m,_ in metrics if m['value'] is not None]+[m['ci95'][1] for _,m,_ in metrics if m['ci95']])
        step=.05 if upper<=.25 else .1;maximum=min(1,math.ceil(upper/step)*step)
        y=lambda v:190-145*v/maximum
        out+=f'<article class="task-chart"><h3>{esc(title)}</h3><p class="small">Full development · Per activation · {info["items"]} items · {info["independent_groups"]} related groups. '+('Error rate: lower is better, not accuracy.' if family=='hallucination' else 'Match rate: higher is better.')+f' Zero-based axis: 0–{maximum*100:g}%.</p><svg class="sampling-plot" viewBox="0 0 350 235" role="img" aria-label="Complete development sampling curve, grouped intervals, original references">'
        for v in (0,maximum/2,maximum):out+=f'<path d="M40 {y(v)}H310" stroke="#D6E1EC"/><text x="34" y="{y(v)+4}" text-anchor="end">{v*100:g}%</text>'
        for (_,m,_),colour in zip(metrics[:2],('#7C8793','#BF7529')):
            if m['value'] is not None:out+=f'<path d="M40 {y(m["value"])}H310" stroke="{colour}" stroke-dasharray="5 4"/>'
        points=metrics[2:]
        for (a,ma,_),(b,mb,_) in zip(points,points[1:]):
            if ma['value'] is not None and mb['value'] is not None:out+=f'<path d="M{xs[a["n"]]} {y(ma["value"])}L{xs[b["n"]]} {y(mb["value"])}" fill="none" stroke="#246AB3"/>'
        for c,m,_ in points:
            x=xs[c['n']];ci=m['ci95']
            if m['value'] is not None:
                if ci:out+=f'<path d="M{x-4} {y(ci[0])}H{x+4}M{x} {y(ci[0])}V{y(ci[1])}M{x-4} {y(ci[1])}H{x+4}" stroke="#087F83"/>'
                out+=f'<circle cx="{x}" cy="{y(m["value"])}" r="4" fill="#246AB3"/>'
            out+=f'<text x="{x}" y="211" text-anchor="middle">{c["n"]}</text>'
        out+='<text x="175" y="232" text-anchor="middle">Number of shared samples</text></svg><p class="small">Blue: best reconstruction · grey dashed: released original, unmodified · amber dashed: capped original, whole bullets only. Reference intervals appear in the table.</p><details><summary>Exact rates, intervals and count denominators</summary>'+table([r for r in rows if r['family']==family])+'</details></article>'
    out+='</div><p class="small">Best of 1 also applies the selector’s eligibility checks. It is not the shortened original: one transcript site and eleven role sites have empty eligible selections. The curves above measure per-activation outcomes, not questions with at least one match. Capped original keeps up to four intact bullets within 256 tokens; it drops only whole trailing bullets. Sites are correlated within items; arithmetic has only seven related groups.</p>'
    original=[]
    for c in conditions:
        for family,f in c['families'].items():
            if family=='hallucination':continue
            for m in f.get('original_grid_metrics',{}).values():
                original.append({'family':family,'condition':c['condition'],
                    'endpoint':'Whole items: at least one passing site/layer',
                    'value':m['value'],'ci':m['ci95'],'numerator':m['numerator'],
                    'denominator':m['denominator'],'eligible_count':m['items'],'eligibility_unit':'items',
                    'missing_count':0,'cohort':'Full development: original whole-item aggregation',
                    'uncertainty':f'{m["independent_groups"]} related groups; grouped 95% interval'+('; '+m['warning'] if m.get('warning') else '')})
    if original:out+='<details><summary>Questions with at least one match</summary><p class="small">This is the original benchmark aggregation over complete grids. Its denominator is questions: a match at any preselected activation counts once, unlike the per-activation curves above.</p>'+table(original)+'</details>'
    out+='<details><summary>Paired changes, grouped by related examples</summary><p class="small">These intervals compare paired outputs. Overlapping absolute error bars do not establish the paired difference.</p>'
    paired=[]
    for r in measurement['paired_comparisons']:
        if r['endpoint'] not in ('contradiction_rate','cell_recovery'):continue
        paired.append({'family':r['family'],'condition':r['condition']+' vs '+r['baseline_condition'],
            'endpoint':'Paired delta: Contradictions / specific readouts' if r['family']=='hallucination' else 'Paired delta: Cell recovery',
            'value':r['delta'],'ci':r['ci95_delta'],'cohort':'Full development: complete original grids',
            'eligible_count':r['items'],'eligibility_unit':'items','missing_count':0,
            'uncertainty':f'{r["items"]} items; {r["independent_groups"]} related groups'+('; '+r['warning'] if r.get('warning') else '')})
    for family in TASKS:out+='<details><summary>'+esc(TASKS[family])+'</summary>'+paired_plot(paired,family)+'</details>'
    return out+'<details><summary>All paired values and exact intervals</summary>'+table(paired,True)+'</details></details>'


def method_sections(report,details_url='details.html'):
    section=report.get('signed_comparisons',{}).get('validation',{});dev=full_dev_rows(report)
    out='<div class="method-accordions">'
    for key,(name,description,record,status) in METHODS.items():
        method=report.get('methods',{}).get(key,{})
        rows=list(method.get('metrics',[]));conditions={r['condition'] for r in rows}
        if key=='sample_selection':conditions.update(('raw_n1-n1','capped_n1-n1','best_n_exact-n16','best_n_exact-n32','random_complete-n32'))
        if key=='pruning':conditions.update(('prune_loo_a32_0.005-n32','random_delete_matched_a32_0.005-n32'))
        def full(row):return row.get('scope')=='original_grid_development' or row.get('cohort','').startswith(('Full DEV','Full development'))
        diagnostic=[r for r in rows if r.get('scope','').startswith('isolated_')]
        stages={'Development pilot':[r for r in rows if not full(r) and r not in diagnostic],
          'Isolated reconstruction diagnostics':diagnostic,
          'Validation':normalized_signed(section,conditions),
          'Full development':[r for r in rows if full(r)]+[r for r in dev if r['condition'] in conditions]}
        measured=len(conditions)
        count_label='plotted variants' if key=='combinations' else 'recorded variants'
        out+=f'<details class="method-info" id="method-{key}"><summary><span>{esc(name)}</span><small>{measured} {count_label}' if measured else f'<details class="method-info" id="method-{key}"><summary><span>{esc(name)}</span><small>Diagnostic only'
        out+='</small></summary><p>'+esc(description)+'</p><p class="method-status">'+esc(status)+'</p>'
        panels=[]
        for stage,stage_rows in stages.items():
            for family in TASKS:
                family_rows=[r for r in stage_rows if r.get('family')==family]
                if any(headline(r) for r in family_rows):panels.append((stage,family,family_rows))
        if panels:
            out+=f'<label class="variant-select">Chart<select data-method-chart="{key}">'
            for i,(stage,family,_) in enumerate(panels):out+=f'<option value="{i}">{esc(stage)} · {esc(TASKS[family])}</option>'
            out+='</select></label>'
            for i,(stage,family,family_rows) in enumerate(panels):
                out+=f'<div data-method-panel="{key}-{i}"'+(' hidden' if i else '')+'>'+rate_plot(family_rows,TASKS[family],stage)+ '</div>'
        else:
            out+='<div class="diagnostic-graph"><strong>Frozen independent reader</strong><span>→</span><strong>Names / number tokens</strong><span>→</span><strong>Diagnostic support only</strong></div><p class="small">No benchmark-quality curve or uncertainty interval is available. Token presence does not prove a relation; absence does not imply falsehood.</p>'
        for stage,stage_rows in stages.items():
            if stage_rows:out+=f'<details><summary>{esc(stage)}: every measured result ({len(stage_rows)} rows)</summary>'+table(stage_rows)+'</details>'
        auxiliary=validation_auxiliary(section,conditions)
        if auxiliary:
            out+='<details><summary>Validation: assertion coverage, off-topic content and claim checks</summary><p class="small">False spans and true claims use different units. Unverifiable is not false. Per-output tallies are counts, not accuracy percentages.</p>'+table(auxiliary)+'</details>'
        lengths=[r for r in section.get('length_rows',[]) if r['condition'] in conditions]
        if lengths:
            out+='<details><summary>Validation: output lengths by task</summary><div class="table-scroll"><table><tr><th>Task / variant</th><th>Intended outputs</th><th>Mean tokens</th><th>Mean bullets</th></tr>'
            for r in lengths:out+=f'<tr><td>{esc(TASKS[r["family"]])}: {esc(label(r["condition"]))}</td><td>{r["outputs"]}</td><td>{r["mean_qwen_tokens_all_intended"]:.2f}</td><td>{r["mean_bullets_all_intended"]:.2f}</td></tr>'
            out+='</table></div><p class="small">Complete original validation grids. Qwen token counts; intervals for these length means were not supplied.</p></details>'
        paired=list(method.get('paired_metrics',[]))
        for r in section.get('paired_rows',[]):
            if r.get('scope')!='cell' or r['condition'] not in conditions or r['endpoint'] not in ('contradiction_rate','cell_recovery'):continue
            paired.append({'family':r['family'],'condition':r['condition']+' vs '+r['baseline_condition'],
              'endpoint':'Paired delta: Contradictions / specific readouts' if r['family']=='hallucination' else 'Paired delta: Cell recovery',
              'value':r['delta'],'ci':r['ci95_delta'],'cohort':'Validation: complete original grids',
              'uncertainty':f'Validation; {r["items"]} items; {r["independent_groups"]} related groups; grouped 95% interval'+('; '+r['warning'] if r.get('warning') else ''),
              'eligible_count':r['items'],'eligibility_unit':'items','missing_count':0})
        if paired:
            out+='<details><summary>Paired changes versus parents and controls</summary><p class="small">Use these paired intervals to assess method differences. Overlap between individual-rate error bars does not establish the paired difference.</p>'
            for stage in ('Development pilot','Validation','Full development'):
                subset=[r for r in paired if ('Validation' if r.get('cohort','').startswith('Validation') else 'Full development' if full(r) else 'Development pilot')==stage]
                if not subset:continue
                out+='<details><summary>'+stage+'</summary>'
                for family in TASKS:out+='<details><summary>'+esc(TASKS[family])+'</summary>'+paired_plot(subset,family)+'</details>'
                out+='</details>'
            out+='<details><summary>All paired endpoints and exact intervals</summary>'+table(paired,True)+'</details></details>'
        out+='<details><summary>Costs and runtime requirements</summary>'+costs(method.get('cost_components',[]))
        measured_cost=report.get('measured_cost_components',{});deployment=measured_cost.get('deployment',{})
        timer_keys={'sample_selection':['A8','A16','A32'],'pruning':['C32'],'pooling':['D32'],
          'contrastive_checks':['E1_mean32']}.get(key,[])
        for timer_key in timer_keys:
            timer=measured_cost.get('incremental_cache',{}).get(timer_key)
            if timer:out+=costs([{'component':f'Cached local selection: {timer_key}',
              'value':timer['median_seconds_per_cell'],'unit':'CPU task seconds / cell, median',
              'scope':'Eight fixed development cells; three repetitions; four threads; preparation excluded',
              'measurement':f'Observed range {timer["minimum"]}–{timer["maximum"]} seconds, not a confidence interval. Existing vectors reused; excludes new capture, generation and encoding.'}])
        campaign=measured_cost.get('campaign',{})
        if key=='contrastive_checks' and campaign.get('e3_gpu_task_seconds') is not None:
            out+=costs([{'component':'Likelihood experiment: three contexts per candidate',
              'value':campaign['e3_gpu_task_seconds'],'unit':'GPU task seconds / 189-cell pilot',
              'scope':f'{campaign["e3_candidates"]} candidates; {campaign["e3_context_sequences"]} context sequences; {campaign["e3_candidate_tokens_scored"]} candidate tokens',
              'measurement':'Measured likelihood stage, not complete new-input latency or one selected output cost'}])
        if key=='editing' and campaign.get('f_ar_gpu_task_seconds') is not None:
            out+=costs([{'component':'Fresh encoding of edited bullets','value':campaign['f_ar_gpu_task_seconds'],
              'unit':'GPU task seconds / both 189-cell edit rounds','scope':f'{campaign["f_new_ar_vectors"]} new reconstruction vectors',
              'measurement':'Measured additional encoding; helper cost is separate; excludes the unchanged parent pool'}])
        helper_field={'editing':'helper_f_two_rounds_usd_per_cell_observed'}.get(key)
        if helper_field and deployment.get(helper_field) is not None:
            out+=costs([{'component':'Both editing rounds: helper usage','value':deployment[helper_field],
              'unit':'USD / cell','scope':'Measured pilot component','measurement':'Usage-derived helper component only; excludes generation, encoding and judging'}])
        if not method.get('cost_components'):out+=costs(report.get('methods',{}).get('sample_selection',{}).get('cost_components',[])[:3])
        out+='<p class="small">Shared pool and cached work are reused across arms. These component costs are not a fresh-input end-to-end latency or a separate invoice for each variant. Missing prices and timers remain unknown.</p></details>'
        out+=qualitative.method_cards(report.get('qualitative_reviews'),key)
        out+='<details><summary>Additional examples, failures and interpretation</summary>'+traces(method.get('traces',[]))
        for finding in method.get('findings',[]):out+=f'<p>{esc(finding)}</p>'
        for limit in method.get('limits',[]):out+=f'<p class="small">{esc(limit)}</p>'
        out+='</details><details><summary>Source and exact identifiers</summary><p>Experiment record: '+esc(record)+'. Tables preserve the exact variant identifiers. Technical implementation and additional diagnostics are retained in the full study.</p><a href="'+esc(details_url)+'">Open source details</a></details></details>'
    return out+'</div>'


CSS='''
.method-accordions{display:block}.method-accordions>.method-info{background:#fff;border:1px solid var(--line);border-radius:8px;margin:14px 0;padding:20px 24px}.method-info>summary{display:flex;justify-content:space-between;gap:15px;max-width:none;font-size:18px}.method-info>summary small{font-size:12px;font-weight:400;color:var(--muted)}.method-info>details{border-top:1px solid var(--line);padding:14px 0}.method-status{border-left:3px solid #87A6BF;padding-left:14px}.variant-select{display:flex;gap:12px;align-items:center;margin:20px 0;font-size:13px}.variant-select select{font:inherit;max-width:100%;padding:8px;border:1px solid var(--line);background:#fff;border-radius:4px}.variant-row{display:grid;grid-template-columns:minmax(160px,1.4fr) minmax(110px,1fr) 80px;gap:14px;align-items:center;padding:8px 0;border-bottom:1px solid #EDF1F5;font-size:13px}.variant-row svg{width:100%;height:28px}.variant-row strong{text-align:right;font-size:16px;font-variant-numeric:tabular-nums}.variant-row small,.table-scroll small{display:block;font-size:11px;color:var(--muted)}.chart-axis{font-size:11px;color:var(--muted);border:0}.table-scroll{overflow-x:auto;max-width:100%;margin:12px 0}.table-scroll table{min-width:640px;font-size:12px}.table-scroll details{max-width:230px}.table-scroll summary{font-size:11px;font-weight:400}.small,.missing{font-size:12px!important;color:var(--muted)}.sampling-plot{width:100%;max-height:300px}.sampling-plot text{font:12px 'Segoe UI',Arial,sans-serif;fill:#5B6D7E}.trace{padding:10px 0}.trace-pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.trace pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 'Segoe UI',Arial,sans-serif;background:#F2F6FA;padding:14px}.trace h5{margin:10px 0;font-size:13px}.diagnostic-graph{display:flex;gap:14px;justify-content:center;align-items:center;flex-wrap:wrap;padding:30px;background:#F2F6FA;font-size:13px}.diagnostic-graph strong{max-width:145px;text-align:center}.method-info h4{margin-bottom:10px}[hidden]{display:none!important}@media(max-width:760px){.method-accordions>.method-info{padding:18px}.method-info>summary{font-size:16px;flex-direction:column;gap:5px}.variant-row{grid-template-columns:minmax(110px,1.2fr) minmax(90px,1fr) 65px;gap:5px;font-size:11px}.variant-row strong{font-size:14px}.variant-select{display:block}.variant-select select{display:block;margin-top:8px;width:100%}.trace-pair{grid-template-columns:1fr}.sampling-plot text{font-size:13px}}
'''
JS='''document.querySelectorAll('[data-method-chart]').forEach(select=>select.addEventListener('change',()=>{const key=select.dataset.methodChart;document.querySelectorAll('[data-method-panel]').forEach(panel=>{if(panel.dataset.methodPanel.startsWith(key+'-'))panel.hidden=panel.dataset.methodPanel!==key+'-'+select.value;});}));'''
