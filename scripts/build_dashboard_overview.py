"""Build a readable public overview from reviewed, sanitized dashboard data.

Rendering only: no metrics, intervals, selections or scientific facts are fitted.
The coordinator preserves the full dashboard as details.html and publishes it.
"""
import argparse
from hashlib import sha256
import html
import json
import math
from pathlib import Path
import re
try:
    import dashboard_method_sections as method_sections
except ModuleNotFoundError:
    from scripts import dashboard_method_sections as method_sections


DEFAULT = ('raw_n1-n1','best_n_exact-n16','best_n_exact-n32','best_n_specificity_mean-n32')
FAMILIES = {
    'hallucination':('Transcript contradictions','Lower is better','Specific readouts that contradict the transcript.'),
    'multihop_mt':('Multi-hop facts','Higher is better','Readouts that name the required person, place or thing.'),
    'chain_intermediates':('Arithmetic steps','Higher is better','Readouts that name a required intermediate number.'),
    'role_bound_association':('Who did what','Higher is better','Readouts that pass the who-did-what check.'),
}
NAMES = {
    'raw_n1-n1':('Original readout','1 sample','#8495A7'),
    'capped_n1-n1':('Shortened original','1 sample','#8495A7'),
    'best_n_exact-n16':('Best of 16','16 samples','#246AB3'),
    'best_n_exact-n32':('Best of 32','32 samples','#6194CB'),
    'random_complete-n32':('Random choice','32-sample pool','#8495A7'),
    'pooled_greedy_swap-n16':('Combine bullets','16 samples','#895FAB'),
    'pooled_greedy_swap-n32':('Combine bullets','32 samples','#A18CBD'),
    'best_n_specificity_mean-n32':('Compare against other activations','32 samples','#087F83'),
    'best_n_specificity_mean_then_prune_0.005-n32':('Compare, then shorten','32 samples','#087F83'),
    'best_n_specificity_mean_random_delete_matched_0.005-n32':('Compare, then random deletion','32 samples','#619E91'),
    'prune_loo_a32_0.005-n32':('Best of 32, then shorten','32 samples','#246AB3'),
    'random_delete_matched_a32_0.005-n32':('Best of 32, then random deletion','32 samples','#6194CB'),
}


def esc(value): return html.escape(str(value),quote=True)


def data_for_page(report, heldout_items=None):
    section = report.get('signed_comparisons',{}).get('validation')
    if not section or section['stage']!='validation' or section['review'].get('status')!='root_reviewed':
        raise ValueError('Overview requires an explicitly reviewed validation comparison')
    if set(section['family_counts'])!=set(FAMILIES) or not set(DEFAULT)<=set(section['condition_ids']):
        raise ValueError('Missing default methods or validation task')
    if any(c not in NAMES for c in section['condition_ids']):
        raise ValueError('Unknown signed method requires an explicit readable label')
    metrics = {}
    for scope,key in (('cells','cell_rows'),('items','original_item_rows')):
        metrics[scope] = {family:{} for family in FAMILIES}
        for row in section[key]:
            family,condition=row['family'],row['condition'];m=row['metric']
            if family not in FAMILIES or condition not in section['condition_ids'] or condition in metrics[scope][family]:
                raise ValueError('Duplicate or foreign overview metric')
            value=m['value'];interval=m['ci95']
            if value is not None and (not math.isfinite(value) or not 0<=value<=1):
                raise ValueError('Invalid reviewed rate')
            if interval is not None and (len(interval)!=2 or not all(math.isfinite(v) for v in interval) or not 0<=interval[0]<=interval[1]<=1):
                raise ValueError('Invalid reviewed interval')
            metrics[scope][family][condition] = m
        if any(set(rows)!=set(section['condition_ids']) for rows in metrics[scope].values()):
            raise ValueError('Incomplete reviewed method/task coverage')
    heldout_items = report.get('activity',{}).get('heldout_items',heldout_items)
    if not isinstance(heldout_items,int) or isinstance(heldout_items,bool) or heldout_items<1:
        raise ValueError('Supply the frozen held-out item count; never infer it from quality metrics')
    cost = {}
    for row in section.get('cost_rows',[]):
        components={c['component']:c for c in row['components']}
        if row['condition'] in DEFAULT:
            cost[row['condition']]={k:components[k] for k in ('experimental_candidate_budget','recurring_helper')}
    if set(cost)!=set(DEFAULT):raise ValueError('Missing reviewed sample/helper cost facts')
    return {'section':section,'metrics':metrics,'families':FAMILIES,'names':NAMES,'default':DEFAULT,
        'heldout_items':heldout_items,'cost':cost,'updated_utc':report['updated_utc'],'api':report.get('api',{}),
        'activity':report.get('activity',{}),'methods':report.get('methods',{})}


def row_chart(condition, metric, maximum):
    name,budget,color=NAMES[condition];v=metric['value'];ci=metric['ci95'];x=lambda n:10+224*n/maximum
    if v is None:
        return f'<div class="rate-row"><div class="row-label">{esc(name)}<small>{esc(budget)}</small></div><span class="unknown">Not measured</span></div>'
    graph=f'<svg viewBox="0 0 244 32" role="img" aria-label="{esc(name)}: {v*100:.1f} percent">'
    graph+='<line x1="10" y1="16" x2="234" y2="16" stroke="#DFE7F0"/>'
    if ci:
        graph+=f'<path d="M{x(ci[0]):.2f} 11V21M{x(ci[0]):.2f} 16H{x(ci[1]):.2f}M{x(ci[1]):.2f} 11V21" stroke="{color}" stroke-width="2" fill="none" opacity=".6"/>'
    graph+=f'<circle cx="{x(v):.2f}" cy="16" r="5" fill="{color}"/><title>{esc(name)}: {metric["numerator"]}/{metric["denominator"]}; '+(f'95% interval {ci[0]*100:.2f}–{ci[1]*100:.2f}%' if ci else 'interval unavailable')+'</title></svg>'
    return f'<div class="rate-row"><div class="row-label"><span class="method-dot" style="background:{color}"></span>{esc(name)}<small>{esc(budget)}</small></div>{graph}<div class="rate-value">{v*100:.1f}%<small>{metric["numerator"]:,}/{metric["denominator"]:,}</small></div></div>'


def chart(data,family,conditions,scope='cells',full=False):
    title,direction,description=FAMILIES[family];counts=data['section']['family_counts'][family]
    rows=data['metrics'][scope][family]
    largest=max((rows[c]['ci95'] or [rows[c]['value'] or 0])[-1] for c in conditions)
    # Explicit zero-based focus axes encompass every displayed interval.
    step=.05 if largest<.3 else .2
    maximum=1 if full else min(1,max(step,math.ceil(largest/step)*step))
    marks=[maximum*i/4 for i in range(5)]
    axis='<svg viewBox="0 0 244 25" aria-hidden="true">'+''.join(f'<text x="{10+224*i/4}" y="17" text-anchor="middle">{v*100:g}%</text>' for i,v in enumerate(marks))+'</svg>'
    if scope=='items' and family!='hallucination':
        description='Items with a passing readout at any preselected layer or position.'
        denominator='whole items; a pass anywhere counts once'
    else:denominator='specific readouts' if family=='hallucination' else 'readout sites'
    out=f'<article class="task-chart" data-family="{family}"><div class="chart-heading"><h3>{title}</h3><span class="direction">{direction}</span></div><p class="chart-description">{description}</p>'
    out+=''.join(row_chart(c,rows[c],maximum) for c in conditions)
    out+='<div class="rate-row axis-row"><span></span>'+axis+'<span></span></div>'
    out+=f'<p class="chart-foot">{counts["items"]} validation items · Counts below rates use {denominator}.<br>Points are rates; lines show 95% intervals. Axis: 0–{maximum*100:g}%.</p></article>'
    return out


def coverage(data):
    s=data['section'];out='<details class="info"><summary>Where did we measure?</summary><p>One readout site means one internal vector at one layer and token position. Every method uses the same preselected sites.</p><table><thead><tr><th>Task</th><th>Items</th><th>Readout sites</th><th>Related groups</th></tr></thead><tbody>'
    for family,c in s['family_counts'].items():
        out+=f'<tr><td>{FAMILIES[family][0]}</td><td>{c["items"]}</td><td>{c["cells"]:,}</td><td>{c["groups"]}</td></tr>'
    out+='</tbody></table><p>All 12 preselected validation methods are complete. Missing results are not zero. Related examples stay together when estimating uncertainty.</p>'
    grid=s.get('coverage',{})
    if grid:
        if grid.get('status')!='root_reviewed' or grid.get('artifact_sha256')!=s['source_sha256']:
            raise ValueError('Unreviewed or foreign coverage metadata')
        out+='<p>Position ranks refer to each item’s selected token positions, not a shared absolute word index.</p>'
        for family,counts in grid['families'].items():
            out+=f'<p><strong>{FAMILIES[family][0]}:</strong> layers '+esc(', '.join(map(str,counts['layers'])))+f'; {len(counts["position_ranks"])} selected position rank(s).</p>'
    return out+'</details>'


def build(report,heldout_items=None,details_url='details.html'):
    data=data_for_page(report,heldout_items);s=data['section'];validation_items=sum(c['items'] for c in s['family_counts'].values());cells=sum(c['cells'] for c in s['family_counts'].values())
    updated=data['updated_utc'].replace('T',' ').split('.')[0].replace('+00:00','')+' UTC'
    findings=s['review']['findings'];details_url=esc(details_url)
    notes=''.join(f'<details class="finding-detail"><summary>{esc(f["claim"])}</summary><p>{esc(f["evidence"])}</p></details>' for f in findings)
    plots=''.join(chart(data,f,DEFAULT) for f in FAMILIES)
    budgets=''.join('<tr><td>'+esc(NAMES[c][0])+'</td><td>'+esc(data['cost'][c]['experimental_candidate_budget']['value'])+'</td><td>'+esc(data['cost'][c]['recurring_helper']['value'])+'</td></tr>' for c in DEFAULT)
    api=data['api'];usage='Not measured' if api.get('actual_usd') is None else f'${api["actual_usd"]:.2f}'
    held='Unknown' if api.get('reserved_usd') is None else f'${api["reserved_usd"]:.2f}'
    stamp=esc(api.get('observed_utc','Timestamp not available'))
    operational=data['activity'].get('overview_status',{})
    development_status=esc(operational.get('development','Full baselines complete. Additional sampling measurements are incomplete.'))
    test_status=esc(operational.get('test','Samples collected; quality results are pending.'))
    count=operational.get('heldout_conditions')
    if count is not None and (not isinstance(count,int) or isinstance(count,bool) or count<1):
        raise ValueError('Invalid operational held-out comparison count')
    test_menu=f'{count} preselected comparisons' if count is not None else 'Preselected comparisons'
    methods=[('sample_selection','Choose a complete readout','Ask for several descriptions and keep the one that best matches the internal snapshot.'),
        ('consensus','Keep repeated claims','Keep claims that recur across different samples. Agreement does not by itself establish truth.'),
        ('pruning','Remove weak bullets','Remove bullets that add little to the match. Check how much useful information is lost.'),
        ('pooling','Combine bullets','Choose up to four original bullets from different samples.'),
        ('contrastive_checks','Compare against other activations','Prefer descriptions that match this snapshot more than other fixed snapshots.'),
        ('editing','Edit a readout','Propose small wording changes, then keep changes that improve the match. Check that meaning is preserved.'),
        ('independent_checks','Check with another reader','Look for supporting names and numbers with another released reader. Word presence does not verify who did what.'),
        ('combinations','Combine approaches','Combine parts, then remove each part to check what it contributes.')]
    deep=method_sections.method_sections(report,details_url)
    sampling=method_sections.scaling(report)
    payload={k:data[k] for k in ('metrics','names','families','default')};payload['condition_ids']=s['condition_ids'];payload['family_counts']=s['family_counts']
    serialized=json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('&','\\u0026')
    content=f'''<header class="top"><a class="brand" href="#">Oracle Lens research</a><nav><a href="#results">Results</a><a href="#methods">Methods</a><a href="{details_url}">Full study</a></nav></header>
<main><section class="hero"><div><h1>A closer look<br>inside the model.</h1><p class="lead">One internal snapshot. Up to 32 possible descriptions. We test whether choosing or combining them gives a more useful readout.</p></div><aside class="verdict"><h2>No overall winner yet.</h2><p>Validation supports two options for final testing: <strong>Best of 16</strong> and <strong>Compare against other activations</strong>. Recovering a name or number can still leave the explanation wrong.</p><a href="#results">See the evidence</a></aside></section>
<section class="stages" aria-label="Study status"><div><span class="stage-state complete">Complete comparisons</span><h2>Development</h2><p>Shared pilots and complete baselines.<br>{development_status}</p></div><div><span class="stage-state complete">Complete</span><h2>Validation</h2><p>{validation_items} items · {len(s['condition_ids'])} methods<br>{cells:,} readout sites</p></div><div><span class="stage-state pending">Quality results pending</span><h2>Held-out test</h2><p>{data['heldout_items']} items · {esc(test_menu)}<br>{test_status}</p></div></section>
<section class="takeaways"><h2>What we know so far</h2><div class="takeaway-grid"><p><strong>Best of 16 is competitive.</strong><span>It uses half the candidates of Best of 32. More samples did not consistently help these validation tasks.</span></p><p><strong>Comparing other activations changes the tradeoff.</strong><span>Fewer contradiction flags can also mean more off-topic content.</span></p><p><strong>Shortening can lose useful details.</strong><span>Careful deletion did not generally beat equally short random deletion.</span></p></div></section>
<section id="results"><div class="section-heading"><div><h2>Four tasks. Four separate checks.</h2><p>Validation results, with uncertainty. These are not held-out results or an overall accuracy score.</p></div><a href="figures.html">Download charts</a></div><div class="controls"><div class="segments" role="group" aria-label="Methods shown"><button data-menu="key" aria-pressed="true">4 key comparisons</button><button data-menu="all" aria-pressed="false">All 12 methods</button></div><label>Measure<select id="scope"><option value="cells">Readout sites</option><option value="items">Whole items: any passing site</option></select></label><label class="range"><input type="checkbox" id="full-range">Full 0–100% axes</label></div><div class="charts" id="charts">{plots}</div><details class="info"><summary>How to read these charts</summary><p>Rates use the exact counts shown under each percentage. The default axes start at zero and include every displayed uncertainty interval; use full axes to compare with the entire 0–100% range. Tasks measure different things, so their percentages are not combined.</p><p>Whole-item recovery counts an item as recovered when any preselected readout passes. The contradiction task retains its readout ratio in both views. Intervals describe each method separately; paired method differences and their intervals are in the full study.</p><p>A connecting-name mention, intermediate number or accepted role answer does not prove a correct explanation. The arithmetic checks have only {s['family_counts']['chain_intermediates']['groups']} related groups in validation. See the reviewed examples and limitations below.</p></details>{coverage(data)}</section>
<section class="interpretation"><div class="section-heading"><div><h2>Why the caveats matter</h2><p>Reviewed conclusions and their exact supporting counts. Open only what you need.</p></div></div>{notes}</section>
<section class="cost-section"><div><h2>What does each option require?</h2><p>Samples and runtime helper calls per new vector. These describe the fixed method, not a promised latency.</p><table><thead><tr><th>Method</th><th>Samples</th><th>API helper calls</th></tr></thead><tbody>{budgets}</tbody></table></div><aside class="cost-note"><h3>Research cost snapshot</h3><p class="cost-number">{usage}<small>estimated experimental API usage</small></p><p>{held} held for outstanding or uncertain charges. The benchmark judge is separate from these local selectors.</p><details><summary>Cost limits and timestamp</summary><p>Observed {stamp}. Not invoice reconciled. GPU dollar prices and complete new-input latency are not yet established. Reusing a research cache does not make new inputs free.</p></details></aside></section>
{sampling}<section id="methods"><div class="section-heading"><div><h2>Explore every tested approach</h2><p>Seven approaches and their combinations. Open a section for charts, all measured variants, uncertainty, costs and failures.</p></div><a href="{details_url}">Full technical study</a></div>{deep}</section>
<footer><p>Public research snapshot · Updated {esc(updated)}. This page refreshes when a reviewed version is published; it is not an unattended live feed.</p><details><summary>Source and reproducibility</summary><p>Reviewed validation source: <code>{esc(s['source_sha256'])}</code>. All chart counts and intervals come from the same signed report as the full study. The model and released readers are frozen; no new training.</p></details><p><a href="report.md">Research report</a> · <a href="{details_url}">Detailed dashboard</a> · <a href="figures.html">Chart files</a></p></footer></main>'''
    return TEMPLATE.replace('__CONTENT__',content).replace('__DATA__',serialized).replace('</style>',method_sections.CSS+'</style>').replace('</script></body>',method_sections.JS+'</script></body>')


TEMPLATE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="A clear view of frozen Oracle Lens inference experiments: validation results, uncertainty, methods and limitations."><title>Oracle Lens — readouts under study</title><link rel="icon" href="data:,"><style>
:root{--canvas:#F2F6FA;--paper:#fff;--ink:#15304A;--muted:#5B6D7E;--line:#D6E1EC;--blue:#246AB3;--teal:#087F83}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--canvas);color:var(--ink);font:16px/1.6 'Avenir Next','Segoe UI',Arial,sans-serif}a{color:var(--blue);text-underline-offset:4px}a:hover{text-decoration-thickness:2px}button,input,select{font:inherit}button,select{cursor:pointer}:focus-visible{outline:3px solid var(--teal);outline-offset:4px}.top,main{max-width:1240px;margin:auto;padding-left:42px;padding-right:42px}.top{display:flex;justify-content:space-between;align-items:center;padding-top:25px;padding-bottom:25px;border-bottom:1px solid var(--line)}.brand{font-weight:650;text-decoration:none;color:var(--ink)}nav{display:flex;gap:28px}nav a{font-size:14px;text-decoration:none}.hero{display:grid;grid-template-columns:1.4fr 1fr;gap:70px;padding:72px 0 52px;align-items:center}h1{font:normal clamp(40px,5.2vw,68px)/1.08 Georgia,'Times New Roman',serif;letter-spacing:-1.3px;margin:0 0 24px}h2{font-size:25px;line-height:1.25;letter-spacing:-.45px;margin:0 0 14px}h3{font-size:20px;line-height:1.3;margin:0}p{max-width:76ch;margin:0 0 15px}.lead{font-size:18px;color:var(--muted);max-width:44ch}.verdict{padding:30px 0 30px 30px;border-left:4px solid var(--teal)}.verdict h2{color:var(--teal);font-size:29px}.verdict p{font-size:16px;max-width:42ch}.stages{display:grid;grid-template-columns:repeat(3,1fr);padding:22px 0 24px;background:#E7EFF6;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.stages>div{padding:0 28px;border-right:1px solid #CDDCE8}.stages>div:last-child{border:none}.stages h2{font-size:20px;margin:8px 0}.stages p{font-size:14px;color:var(--muted);margin:0}.stage-state{font-size:12px;font-weight:650}.stage-state.complete{color:var(--teal)}.stage-state.pending{color:#8F591A}.takeaways{padding:45px 0 24px}.takeaway-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:34px}.takeaway-grid p{font-size:15px}.takeaway-grid strong{display:block;margin-bottom:8px}.takeaway-grid span{color:var(--muted)}section[id]{scroll-margin-top:25px}.section-heading{display:flex;justify-content:space-between;gap:25px;align-items:end;margin:27px 0 20px}.section-heading p{color:var(--muted);margin-bottom:0;font-size:15px}.section-heading>a{white-space:nowrap;font-size:14px}.controls{display:flex;gap:23px;align-items:center;flex-wrap:wrap;margin:25px 0}.segments{display:flex;border:1px solid #C1D2E3;border-radius:7px;overflow:hidden}.segments button{border:0;background:transparent;padding:9px 15px;font-size:14px;color:var(--muted)}.segments button[aria-pressed=true]{background:var(--ink);color:#fff}.controls label{font-size:13px;color:var(--muted);display:flex;gap:9px;align-items:center}.controls select{border:1px solid #C1D2E3;border-radius:5px;padding:8px;background:var(--paper);color:var(--ink);font-size:13px}.range input{accent-color:var(--blue)}.charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.task-chart{background:var(--paper);border-radius:10px;padding:26px 22px 20px;border:1px solid #DCE6EF;min-width:0}.chart-heading{display:flex;gap:12px;justify-content:space-between;align-items:baseline}.direction{color:var(--muted);font-size:12px;white-space:nowrap}.chart-description{color:var(--muted);font-size:13px;min-height:42px;margin-top:10px}.rate-row{display:grid;grid-template-columns:minmax(100px,1.2fr) minmax(95px,1.6fr) 62px;gap:7px;align-items:center;min-height:62px}.rate-row svg{width:100%;height:32px;overflow:visible}.row-label{font-size:13px;line-height:1.4;position:relative;padding-left:13px}.method-dot{position:absolute;width:7px;height:7px;border-radius:50%;left:0;top:6px}.row-label small{display:block;color:var(--muted);font-size:11px;margin-top:2px}.rate-value{font-size:18px;text-align:right;font-weight:650;font-variant-numeric:tabular-nums}.rate-value small{display:block;font-size:11px;font-weight:400;color:var(--muted);margin-top:2px}.axis-row{min-height:28px}.axis-row text{font:20px 'Segoe UI',Arial,sans-serif;fill:var(--muted)}.chart-foot{font-size:11px;line-height:1.6;color:var(--muted);margin:10px 0 0}.unknown{color:var(--muted);font-size:13px}.info{margin:15px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:15px 0}.info p{font-size:14px;color:var(--muted);margin-top:15px}summary{cursor:pointer;font-size:14px;font-weight:600;max-width:85ch}details[open]>summary{margin-bottom:12px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:12px 10px;text-align:left;border-bottom:1px solid var(--line)}th{font-weight:550;color:var(--muted);font-size:12px}.interpretation{padding:25px 0}.finding-detail{padding:16px 0;border-bottom:1px solid var(--line)}.finding-detail p{font-size:14px;color:var(--muted);margin-top:12px}.cost-section{display:grid;grid-template-columns:1.35fr 1fr;gap:65px;padding:42px 0 35px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-top:20px}.cost-section p{color:var(--muted);font-size:14px}.cost-note{background:#E7EFF6;padding:24px;border-radius:5px;align-self:start}.cost-number{font-size:32px!important;color:var(--ink)!important;font-variant-numeric:tabular-nums;margin:12px 0!important}.cost-number small{font-size:12px;display:block;color:var(--muted)}.cost-note details p{font-size:12px}.method-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 30px}.method-info{padding:18px 0;border-bottom:1px solid var(--line)}.method-info p{font-size:14px;color:var(--muted);margin-top:10px}.method-info a{font-size:13px}footer{padding:50px 0 30px;margin-top:35px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}footer details{margin:12px 0}code{overflow-wrap:anywhere;font:inherit}footer summary{font-size:12px}@media(max-width:1000px){.top,main{padding-left:25px;padding-right:25px}.hero{gap:30px}.chart-heading{align-items:start;flex-direction:column;gap:4px}.chart-description{min-height:55px}.cost-section{gap:30px}}@media(max-width:760px){.hero{grid-template-columns:1fr;padding:42px 0 30px;gap:15px}h1{font-size:49px}.verdict{padding:15px 0 12px 20px}.stages>div{padding:0 14px}.stages p{font-size:12px}.stages h2{font-size:16px}.takeaway-grid{grid-template-columns:1fr;gap:8px}.takeaways{padding:30px 0 10px}.charts,.cost-section{grid-template-columns:1fr}.chart-heading{flex-direction:row;align-items:baseline}.chart-description{min-height:0;margin-bottom:15px}.task-chart{padding:24px}.rate-row{grid-template-columns: minmax(110px,1fr) minmax(110px,1.5fr) 65px}.cost-section{gap:25px}.method-grid{grid-template-columns:1fr}.section-heading{align-items:start}.controls{gap:12px}.cost-note{width:100%}}@media(max-width:430px){.top,main{padding-left:18px;padding-right:18px}.top{gap:14px;padding-top:20px;padding-bottom:18px}nav{gap:13px}nav a{font-size:12px}.brand{font-size:14px}h1{font-size:43px}.lead{font-size:16px}.stages{grid-template-columns:1fr;background:transparent;padding:0}.stages>div{padding:14px 4px;border-right:0;border-bottom:1px solid var(--line);display:grid;grid-template-columns:90px 1fr;gap:0 12px}.stages h2{grid-column:1;grid-row:1/3;margin:0}.stage-state,.stages p{grid-column:2}.stages p{margin-top:4px}.chart-heading{flex-direction:column;gap:4px}.task-chart{padding:20px 15px}.rate-row{grid-template-columns:minmax(90px,1fr) minmax(95px,1.35fr) 59px;gap:3px}.rate-value{font-size:17px}.row-label{font-size:12px}.chart-foot{font-size:11px}.section-heading{flex-direction:column;gap:10px}.controls label{max-width:100%}.controls select{max-width:240px}.cost-section table{font-size:12px}.axis-row text{font-size:26px}.axis-row text:nth-child(2),.axis-row text:nth-child(4){display:none}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style></head><body>__CONTENT__<script id="overview-data" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.getElementById('overview-data').textContent);let all=false;const e=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function renderChart(family,conditions,scope,full){const [title,direction,baseDescription]=data.families[family],rows=data.metrics[scope][family],counts=data.family_counts[family];let largest=Math.max(...conditions.map(c=>rows[c].ci95?rows[c].ci95[1]:(rows[c].value||0))),step=largest<.3?.05:.2,max=full?1:Math.min(1,Math.max(step,Math.ceil(largest/step)*step));const x=v=>10+224*v/max;let description=baseDescription,denom=family==='hallucination'?'specific readouts':'readout sites';if(scope==='items'&&family!=='hallucination'){description='Items with a passing readout at any preselected layer or position.';denom='whole items; a pass anywhere counts once';}let result=`<article class="task-chart"><div class="chart-heading"><h3>${e(title)}</h3><span class="direction">${e(direction)}</span></div><p class="chart-description">${e(description)}</p>`;for(const c of conditions){const [name,budget,color]=data.names[c],m=rows[c],v=m.value,ci=m.ci95;if(v===null){result+=`<div class="rate-row"><div class="row-label">${e(name)}</div><span class="unknown">Not measured</span></div>`;continue;}let svg=`<svg viewBox="0 0 244 32" role="img" aria-label="${e(name)}: ${(v*100).toFixed(1)} percent"><line x1="10" y1="16" x2="234" y2="16" stroke="#DFE7F0"/>`;if(ci)svg+=`<path d="M${x(ci[0])} 11V21M${x(ci[0])} 16H${x(ci[1])}M${x(ci[1])} 11V21" stroke="${color}" stroke-width="2" fill="none" opacity=".6"/>`;svg+=`<circle cx="${x(v)}" cy="16" r="5" fill="${color}"/><title>${e(name)}: ${m.numerator}/${m.denominator}; ${ci?'95% interval '+(ci[0]*100).toFixed(2)+'–'+(ci[1]*100).toFixed(2)+'%':'interval unavailable'}</title></svg>`;result+=`<div class="rate-row"><div class="row-label"><span class="method-dot" style="background:${color}"></span>${e(name)}<small>${e(budget)}</small></div>${svg}<div class="rate-value">${(v*100).toFixed(1)}%<small>${m.numerator.toLocaleString()}/${m.denominator.toLocaleString()}</small></div></div>`;}let ticks='';for(let i=0;i<=4;i++)ticks+=`<text x="${10+224*i/4}" y="17" text-anchor="middle">${Number((max*i/4*100).toFixed(2))}%</text>`;return result+`<div class="rate-row axis-row"><span></span><svg viewBox="0 0 244 25" aria-hidden="true">${ticks}</svg><span></span></div><p class="chart-foot">${counts.items} validation items · Counts below rates use ${e(denom)}.<br>Points are rates; lines show 95% intervals. Axis: 0–${Number((max*100).toFixed(2))}%.</p></article>`;}
function refresh(){const conditions=all?data.condition_ids:data.default,scope=document.getElementById('scope').value,full=document.getElementById('full-range').checked;document.getElementById('charts').innerHTML=Object.keys(data.families).map(f=>renderChart(f,conditions,scope,full)).join('');}document.querySelectorAll('[data-menu]').forEach(b=>b.addEventListener('click',()=>{all=b.dataset.menu==='all';document.querySelectorAll('[data-menu]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));refresh();}));document.getElementById('scope').addEventListener('change',refresh);document.getElementById('full-range').addEventListener('change',refresh);
</script></body></html>'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--heldout-items',type=int);p.add_argument('--details-url',default='details.html')
    args=p.parse_args();body=args.report.read_bytes();report=json.loads(body)
    rendered=build(report,args.heldout_items,args.details_url)
    if re.search(r'/(?:orcd|home|tmp|scratch|workspace)/',rendered):raise ValueError('Use sanitized public input only')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(rendered)
    print(json.dumps({'output':str(args.output),'source_report_sha256':sha256(body).hexdigest(),
                      'output_sha256':sha256(rendered.encode()).hexdigest(),'publication':False}))


if __name__=='__main__':main()
