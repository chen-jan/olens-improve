"""Build a local standalone dashboard from compact reviewed experiment JSON.

No live API calls, backend, publication, or hardcoded scientific results. Missing
values remain missing. Test data require the explicit planned reveal flag.
"""

import argparse
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path


METHODS = {
    "sample_selection": "Sample selection",
    "consensus": "Consensus",
    "pruning": "Pruning",
    "pooling": "Pooling",
    "contrastive_checks": "Contrastive checks",
    "editing": "Editing",
    "independent_checks": "Independent checks",
    "combinations": "Combinations",
}


def escape(value):
    return html.escape(str(value), quote=True)


def value(value, unit=""):
    if value is None:
        return '<span class="missing">Not measured</span>'
    display = f"{value:.4g}" if isinstance(value, float) else value
    if isinstance(value, list) and all(isinstance(x, (float, int)) for x in value):
        display = '[' + ', '.join(f'{x:.4g}' for x in value) + ']'
    return escape(display) + (" " + escape(unit) if unit else "")


def paragraphs(values):
    return "".join(f"<p>{escape(text)}</p>" for text in values)


def display_label(identifier, kind=None):
    """Human-facing labels; exact artifact identifiers remain in provenance."""
    if identifier is None:
        return "Not measured"
    identifier = str(identifier)
    families = {"hallucination": "Contradiction checks", "multihop_mt": "Multi-hop facts",
                "chain": "Arithmetic chains", "chain_intermediates": "Arithmetic chains",
                "role": "Social roles", "role_bound_association": "Social roles"}
    if identifier in families:
        return families[identifier]
    if " vs " in identifier:
        return " versus ".join(display_label(part) for part in identifier.split(" vs "))
    method, separator, n = identifier.rpartition("-n")
    if not separator or not n.isdigit():
        method, n = identifier, None
    for token, explanation in (('_then_prune_', ' then remove low-contribution bullets; threshold '),
                               ('_random_delete_matched_', ' with random deletion matched to threshold ')):
        if token in method:
            parent,threshold=method.split(token,1)
            return display_label(parent+(f'-n{n}' if n else ''))+explanation+threshold
    labels = {"raw_n1": "Original lens (1 sample)", "raw N1": "Original lens (1 sample)",
              "capped_n1": "Capped single-sample baseline", "best_n_exact": "Best reconstruction",
              "best_n_released80": "Best reconstruction (published solver)",
              "random_complete": "Random complete sample", "pooled_greedy_swap": "Pool bullets",
              "best_n_specificity_mean": "Select by contrastive reconstruction (mean)",
              "best_n_specificity_max": "Select by contrastive reconstruction (maximum)",
              "likelihood_true_minus_mean_two_controls": "Select by contrastive likelihood",
              "own_mean_log_likelihood": "Select by target likelihood",
              "control_mean_log_likelihood": "Select by control likelihood",
              "editing_round1": "Edit reconstruction, round 1", "editing_round2": "Edit reconstruction, round 2"}
    if method.startswith('pooling_exact_support_lambda'):
        label='Pool bullets with repeat-support bonus '+method.removeprefix('pooling_exact_support_lambda')
    elif method=='exact_support_only':
        label='Select by exact whole-bullet support alone'
    elif method.startswith("prune_loo_a32_"):
        label = "Remove low-contribution bullets (threshold " + method.rsplit("_", 1)[-1] + ")"
    elif method.startswith("consensus_"):
        label = method.replace("consensus_exact", "Exact consensus").replace("consensus_semantic_v5_medium", "Repaired semantic consensus, medium effort").replace("consensus_semantic_v5", "Repaired semantic consensus, no reasoning").replace("consensus_semantic_v4", "Semantic consensus, instrumentation-limited").replace("_", " ").replace("compatoff", "compatibility off").replace("compaton", "compatibility on").replace('vetoon','contradiction veto on').replace('vetooff','contradiction veto off')
    else:
        label = labels.get(method, method.replace("_", " "))
    return label + (f" from {n} samples" if n and method not in ("raw_n1", "capped_n1") else "")


def metrics_table(rows):
    if not rows:
        return '<p class="missing">No validated comparison yet. Missing values are not zero.</p>'
    output = ['<div class="table-scroll"><table><thead><tr><th>Family / cohort</th><th>Condition</th><th>Endpoint / scope</th><th>Value</th><th>Numerator / denominator</th><th>Coverage / missing</th><th>Uncertainty</th></tr></thead><tbody>']
    scope_labels={'original_grid_development':'original DEV item/readout endpoint','full_grid_cell_diagnostic':'cell diagnostic, full DEV grid','partial_grid_cell_diagnostic':'partial-grid pilot cell diagnostic'}
    for row in rows:
        metric_value = row.get("value")
        is_rate = any(term in str(row.get('endpoint', '')).lower() for term in ('recovery', 'rate', 'share', ' / ', 'exceeds', 'paired delta'))
        rate_unit=' pp' if str(row.get('endpoint','')).lower().startswith('paired delta') else '%'
        shown_value = escape(f"{100*metric_value:.1f}{rate_unit}") if is_rate and isinstance(metric_value, (float, int)) else value(metric_value)
        uncertainty=row.get('uncertainty',row.get('ci'))
        if row.get('ci'):
            bounds=', '.join(f'{100*x:.1f}{rate_unit}' if is_rate else f'{x:.4g}' for x in row['ci'])
            suffix=str(row.get('uncertainty','')).partition(';')[2]
            uncertainty=f'Whole-group 95% interval [{bounds}]'+(';' + suffix if suffix else '')
        cells = [escape(display_label(row.get("family", "Missing family"))) + " / " + escape(row.get("cohort", "Unspecified")),
                 '<span title="' + escape(row.get("condition")) + '">' + escape(display_label(row.get("condition"))) + '</span>', value(row.get("endpoint")) + " / " + value(scope_labels.get(row.get('scope'),row.get('scope'))),
                 shown_value, value(row.get("numerator")) + " / " + value(row.get("denominator")),
                 value(row.get("eligible_count")) + " eligible; " + value(row.get("missing_count")) + " missing",
                 value(uncertainty)]
        output.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    output.append("</tbody></table></div>")
    return "".join(output)


def traces(rows):
    if not rows:
        return '<p class="missing">Trace review pending.</p>'
    output = []
    for row in rows:
        output.append(f'<details><summary>{escape(row.get("kind", "Example"))}: {escape(row.get("cell_id", "Missing cell ID"))}</summary>')
        output.append('<div class="trace-pair">')
        for key, label in (("baseline", "Baseline"), ("selected", "Selected output")):
            output.append(f'<section><h4>{label}</h4><pre>{escape(row.get(key, "Not available"))}</pre></section>')
        output.append("</div>" + paragraphs([row.get("evidence", "Judge evidence not available."), row.get("interpretation", "Interpretation pending.")]) + "</details>")
    return "".join(output)

def full_development_section(section):
    if not section:return ''
    output='<section class="full-development"><h2>'+escape(section['title'])+'</h2><p class="meta">'+escape(section['scope'])+'</p>'+paragraphs([section['summary']])
    if section.get('method_comparison_status'):
        output+=paragraphs([section['method_comparison_status']])
    role_rows=[row for row in section['metrics'] if row.get('family') in ('role','role_bound_association') and row.get('condition')=='capped_n1-n1']
    item=next((row for row in role_rows if row.get('scope')=='original_grid_development'),None)
    cell=next((row for row in role_rows if row.get('endpoint')=='Cell recovery'),None)
    if item and cell:
        output+=paragraphs([f"The capped single-sample baseline passes {item['numerator']:,} of {item['denominator']:,} social-role items, but only {cell['numerator']:,} of {cell['denominator']:,} individual cells. The item score counts any passing site; it does not establish complete faithful explanations."])
    output+='<details class="full-development-evidence"><summary>Full DEV metrics, uncertainty, and baseline audit</summary>'
    output+='<h3>Original item aggregation and cell coverage</h3>'+metrics_table(section['metrics'])
    output+='<details><summary>Original versus capped single-sample baseline: paired whole-group uncertainty</summary>'+metrics_table(section['paired_metrics'])+'</details>'
    cost=section['judge_cost']
    pricing=('Audited usage including cache writes' if cost.get('pricing_revision')=='luna-cache-write-v1' else 'The pre-correction ledger')
    status=('Provider invoice reconciliation remains unavailable.' if cost.get('pricing_revision')=='luna-cache-write-v1' else 'Cache-write repricing is pending; this is not an invoice charge.')
    output+=paragraphs([f"{pricing} estimates ${cost['actual_usd']:.6f} across {cost['physical_attempts']:,} settled physical judge requests. {status} Campaign judging cost is separate from deployment selection cost."])
    output+='<details><summary>Four source-checked baseline audit examples</summary>'+traces(section['traces'])+'</details>'
    donor=section['donor_readiness']
    if section.get('donor'):
        output+=donor_section(section['donor'])
    else:
        output+=paragraphs([f"Matched-donor diagnostic ready: {donor['cells']:,} target outputs use {donor['distinct_donors']:,} distinct frozen donors. Judging is pending.",section['donor_limits']])
    output+='<h3>Baseline limitations</h3>'+paragraphs(section['limits'])
    output+='<details><summary>Full DEV sources</summary>'+paragraphs([str(section['source_sha256'])])+'</details></details></section>'
    return output


def full_dev_a32_section(section):
    if not section:
        return ''
    output='<section class="full-development"><h2>'+escape(section['title'])+'</h2><p class="meta">'+escape(section['scope'])+'</p>'+paragraphs([section['key_finding']])

    def table(rows, grid=False):
        result='<div class="table-scroll"><table><thead><tr><th>Family / endpoint</th><th>Capped single-sample baseline</th><th>Best of 32</th><th>Paired change [95% interval]</th><th>Groups</th></tr></thead><tbody>'
        for row in rows:
            def count(metric):
                return f'{metric["numerator"]:,}/{metric["denominator"]:,}'
            label=('Original item ANY recovery' if grid else 'Contradicted / specific readouts' if row['family']=='hallucination' else 'Cell mention/role recovery')
            ci=' to '.join(f'{b*100:+.2f}' for b in row['ci']) if row.get('ci') else 'Not measured'
            result+=f'<tr><td>{escape(display_label(row["family"]))}<br>{label}</td><td>{count(row["baseline"])}</td><td>{count(row["proposed"])}</td><td>{row["delta"]*100:+.2f} pp [{escape(ci)}]</td><td>{row["groups"]}<br>{escape(row.get("warning") or "")}</td></tr>'
        return result+'</tbody></table></div>'

    output+=table(section['cell_endpoints'])
    hall=section['hallucination_auxiliary_counts']
    a,b=hall['capped_n1-n1'],hall['best_n_exact-n32']
    output+=paragraphs([f"Flagged false spans rise from {a['false_span_tally']['numerator']:,} to {b['false_span_tally']['numerator']:,}, despite fewer readouts labeled contradicted. Off-topic outputs change from {a['off_topic_rate']['numerator']:,} to {b['off_topic_rate']['numerator']:,}. False spans and supported claims use different segmentation; these counts cannot be combined into claim precision."])
    role=next(row for row in section['original_item_endpoints'] if row['family']=='role_bound_association')
    output+=paragraphs([f"Social-role item ANY coverage stays {role['baseline']['numerator']}/{role['baseline']['denominator']} in both conditions. More passing cells do not imply more recovered items or fully faithful descriptions."])
    output+='<details><summary>Original item ANY aggregation, separate from cells</summary>'+table(section['original_item_endpoints'],True)+'</details>'
    output+='<details><summary>Comparison limits and source evidence</summary>'+paragraphs(section['limits'])+paragraphs([f"Reviewed by {section['reviewed_by']}; {section['bootstrap_replicates']:,} paired whole-group draws. Source: {section['source_path']}; SHA-256 {section['source_sha256']}; DEV cohort {section['manifest_sha256']}."])+'</details></section>'
    return output


def donor_section(section):
    output='<h3>Readouts from matched donor activations</h3>'
    output+=paragraphs(['No multi-hop or social-role recovery was observed with this fixed donor bank, while arithmetic recovery remained in some cells. This contextualizes target-specific recovery; it does not verify every emitted claim.',
        'The lower donor contradiction fraction comes with much more off-topic output and far less consistent output. It is not a fidelity improvement.'])
    hall=section['families']['hallucination']['coverage_and_classes']
    output+='<div class="table-scroll"><table><thead><tr><th>Contradiction-check class</th><th>Target activation</th><th>Matched donor activation</th></tr></thead><tbody>'
    for label, key in [('Contradictory','hallucinated'),('Off topic','off_topic'),('Consistent','consistent'),('Generic','generic')]:
        values=[f"{hall[arm]['class_counts'].get(key,0):,} / {hall[arm]['expected_cells']:,} ({100*hall[arm]['class_counts'].get(key,0)/hall[arm]['expected_cells']:.1f}%)" for arm in ('target','donor')]
        output+='<tr><td>'+escape(label)+'</td>'+''.join('<td>'+escape(v)+'</td>' for v in values)+'</tr>'
    output+='</tbody></table></div><details><summary>Recovery counts and paired target-group intervals</summary><div class="table-scroll"><table><thead><tr><th>Family</th><th>Target / donor cell recovery</th><th>Target / donor item recovery (ANY site)</th><th>Donor minus target, cells</th></tr></thead><tbody>'
    for family, row in section['families'].items():
        if family=='hallucination':continue
        m=row['cell_comparison']; n=row['coverage_and_classes']['target']['expected_cells']
        cells=f"{round(m['baseline']*n):,} / {n:,} versus {round(m['proposed']*n):,} / {n:,}"
        items=row['any_cell_item_counts']; interval=', '.join(f'{100*v:.1f}' for v in m['ci95_delta'])
        output+='<tr>'+''.join('<td>'+escape(v)+'</td>' for v in [display_label(family),cells,f"{items['target']} / {row['items']} versus {items['donor']} / {row['items']}",f"{100*m['delta']:.1f} pp; 95% interval [{interval}] pp; {row['independent_target_groups']} groups"] )+'</tr>'
    output+='</tbody></table></div>'+paragraphs(section['limitations'])+'</details>'
    output+='<details><summary>Donor source provenance</summary>'+paragraphs([str(section['source'])])+'</details>'
    return output


def candidate_diagnostic_section(section):
    if not section:return ''
    output='<details class="candidate-diagnostic"><summary>Why sample selection misses available matches: evaluation-only pilot diagnostic</summary>'
    output+='<h3>'+escape(section['title'])+'</h3>'+paragraphs([section['scope'], 'The available-match ceiling uses all 32 judged outputs. It is an optimistic evaluation diagnostic, not a deployable selector or a measure of full faithfulness.'])
    colors=['#bdcbd7','#587991','#bf6b42']
    names=['Available match (ceiling)','Uniform random expectation','Best reconstruction of 32']
    output+='<div class="curve"><svg viewBox="0 0 650 330" role="img" aria-label="Available, random expected, and reconstruction-selected match coverage">'
    output+='<path d="M180 35V270H625" class="axis"/>'
    for index,(family,row) in enumerate((f,r) for f,r in section['families'].items() if f!='hallucination'):
        y=48+index*75
        output+=f'<text x="8" y="{y+25}">{escape(display_label(family))}</text>'
        for j,key in enumerate(('available','random_expected','selected')):
            m=row[key]; width=330*m['rate']; yy=y+j*20
            output+=f'<rect x="180" y="{yy}" width="{width:.3f}" height="14" fill="{colors[j]}"/><text x="{188+width:.3f}" y="{yy+12}">{m["numerator"]:.4g} / {m["denominator"]}</text>'
    for j,label in enumerate(names):
        output+=f'<rect x="10" y="{285+j*15}" width="10" height="10" fill="{colors[j]}"/><text x="26" y="{294+j*15}">{escape(label)}</text>'
    output+='</svg></div><h3>Within-cell reconstruction ranking</h3>'
    output+=paragraphs(['The score is the fraction of positive/negative pairs where the positive readout has higher reconstruction FVE, with half credit for ties. A value of 50% means no pairwise discrimination; raw FVE is never pooled across unrelated activations.'])
    output+='<div class="curve"><svg viewBox="0 0 650 245" role="img" aria-label="Within-cell reconstruction rank with grouped 95 percent intervals"><path d="M205 15V195H605" class="axis"/><path d="M405 15V195" stroke="#bdcbd7" stroke-dasharray="4 4"/>'
    for index,(family,row) in enumerate(section['families'].items()):
        y=35+index*43; score=row['within_cell_rank_pooled_pairs']['rate']; lo,hi=row['rank_ci95']
        output+=f'<text x="8" y="{y+4}">{escape(display_label(family))}</text><path d="M{205+400*lo:.3f} {y}H{205+400*hi:.3f}" class="whisker"/><circle cx="{205+400*score:.3f}" cy="{y}" r="4"/><text x="205" y="{y+18}">{100*score:.1f}%; {row["rank_mixed_cells"]} mixed cells; {row["independent_groups"]} groups</text>'
    output+='<text x="200" y="225">0%</text><text x="395" y="225">50%</text><text x="580" y="225">100%</text></svg></div>'
    output+=paragraphs(section['limits'])
    output+='<details><summary>Diagnostic denominators, definitions, and source hashes</summary><div class="table-scroll"><table><thead><tr><th>Family</th><th>Rank definition</th><th>Pair wins / pairs</th><th>Undefined cells</th><th>Source items / groups</th></tr></thead><tbody>'
    for family,row in section['families'].items():
        pairs=row['within_cell_rank_pooled_pairs']
        output+='<tr>'+''.join('<td>'+escape(v)+'</td>' for v in [display_label(family),row['rank_definition'],f"{pairs['numerator']} / {pairs['denominator']}",row['rank_undefined_cells'],f"{row['items']} / {row['independent_groups']}"])+'</tr>'
    output+='</tbody></table></div>'+paragraphs([section['random_note'],str(section['source'])])+'</details></details>'
    return output


def combination_tables(rows):
    groups={}
    for row in rows:
        condition=str(row.get('condition',''))
        if 'random_delete_matched' in condition:group='Matched-count random deletion controls'
        elif 'support' in condition:group='Repeat support with pooling'
        elif 'specificity' in condition:group='Contrastive reconstruction followed by pruning'
        else:group='Pooling or editing followed by pruning'
        groups.setdefault(group,[]).append(row)
    return ''.join('<details><summary>'+escape(label)+'</summary>'+metrics_table(items)+'</details>' for label,items in groups.items()) if groups else metrics_table([])


def consensus_tables(rows):
    primary={'consensus_exact_support0-n16',
             'consensus_semantic_v5_support0_compatoff_vetoon-n16',
             'consensus_semantic_v5_medium_support0_compatoff_vetoon-n16'}
    selected=[row for row in rows if row.get('condition') in primary and
              row.get('endpoint') in ('Cell mention/binding recovery', 'Transcript contradictions / specific readouts (lower is better)', 'Specific assertion share')]
    return paragraphs(['Key controls: exact support alone, repaired semantic consensus without reasoning, and repaired semantic consensus with medium effort. Lower contradiction fractions require assertion coverage and recovery alongside them.'])+metrics_table(selected)+'<details><summary>All consensus variants, off-topic output, and claim counts</summary>'+metrics_table(rows)+'</details>'


def cost_components_table(rows,notes):
    if not rows:return ''
    output='<details><summary>Measured cost components: campaign, cache replay, and new input</summary><div class="table-scroll"><table><thead><tr><th>Component</th><th>Scope</th><th>Value / unit</th><th>Measurement and limits</th></tr></thead><tbody>'
    for row in rows:
        output+='<tr>'+''.join('<td>'+v+'</td>' for v in [escape(row['component']),escape(row['scope']),value(row['value'],row['unit']),escape(row['measurement'])])+'</tr>'
    return output+'</tbody></table></div>'+paragraphs(notes)+'</details>'


def scaling_chart(rows):
    if not rows:
        return '<p class="missing">Quality versus sample count is not measured yet.</p>'
    # A small exact-data table also provides accessible chart values. Each series
    # requires an explicit endpoint/cohort label; unlike units never share axes.
    output = []
    for series in rows:
        points = series.get("points", [])
        numeric = [point for point in points if isinstance(point.get("value"), (float, int))]
        output.append(f'<section class="curve"><h4>{escape(series["label"])}</h4><p>{escape(series.get("cohort", "Cohort not specified"))}</p>')
        if numeric:
            low = min((point.get("ci") or [point["value"], point["value"]])[0] for point in numeric)
            high = max((point.get("ci") or [point["value"], point["value"]])[1] for point in numeric)
            spread = high-low or 1
            coordinates = []
            for point in numeric:
                # N is a prescribed discrete prefix, not a fitted scaling law.
                prefixes = [1, 2, 4, 8, 16, 32]
                if point["n"] not in prefixes:
                    raise ValueError("Scaling points must use the frozen N=1..32 prefixes")
                x = 40 + prefixes.index(point["n"])*88
                y = 130 - (point["value"]-low)/spread*95
                coordinates.append((x, y, point))
            poly = " ".join(f"{x},{y}" for x, y, _ in coordinates)
            label = escape(series["label"])
            output.append(f'<svg viewBox="0 0 540 170" role="img" aria-label="{label}"><path d="M40 20V135H500" class="axis"/><polyline points="{poly}" class="line"/>')
            for x, y, point in coordinates:
                if point.get("ci") is not None:
                    lower, upper = (130 - (bound-low)/spread*95 for bound in point["ci"])
                    output.append(f'<path d="M{x} {lower}V{upper}M{x-5} {lower}H{x+5}M{x-5} {upper}H{x+5}" class="whisker"/>')
                output.append(f'<circle cx="{x}" cy="{y}" r="4"/><text x="{x}" y="158" text-anchor="middle">N={point["n"]}</text><title>N={point["n"]}, value={point["value"]}</title>')
            output.append(f'<text x="6" y="36">{escape(round(high, 4))}</text><text x="6" y="133">{escape(round(low, 4))}</text></svg>')
        output.append('<table><thead><tr><th>Samples</th><th>Value</th><th>Uncertainty</th><th>Count</th></tr></thead><tbody>')
        for point in points:
            output.append("<tr>" + "".join(f"<td>{value(point.get(key, point.get("ci") if key == "uncertainty" else None))}</td>" for key in ("n", "value", "uncertainty", "count")) + "</tr>")
        output.append("</tbody></table></section>")
    return "".join(output)


def cost_chart(series_rows):
    if not series_rows:
        return '<p class="missing">Family-specific error or recovery versus budget is not available yet.</p>'
    output = []
    for series in series_rows:
        unit = series.get("cost_unit")
        if unit not in ("USD", "GPU seconds", "samples"):
            raise ValueError("A cost plot must identify USD, GPU seconds or sample prefix; do not mix units")
        scope = series.get('cost_scope')
        if scope not in ('campaign', 'incremental_cache', 'deployment', 'experimental_prefix') or not series.get('cost_definition'):
            raise ValueError('Cost charts require an explicit campaign/cache/deployment scope and definition')
        if unit == 'samples' and scope != 'experimental_prefix':
            raise ValueError('Sample-prefix plots must disclose experimental_prefix scope')
        points = series.get("points", [])
        numeric = [p for p in points if p.get("value") is not None and p.get("cost") is not None]
        proportion = series.get('value_unit') == 'proportion'
        rate = lambda v: ('Not measured' if v is None else f'{v*100:.1f}%' if proportion else value(v))
        label = series['label']
        if series.get('family'):
            label = label.replace(series['family'], display_label(series['family']), 1)
        output.append(f'<section class="curve"><h4>{escape(label)}</h4><p>{escape(series.get("cohort", "Unspecified cohort"))}; {escape(scope.replace("_", " "))} in {escape(unit)}: {escape(series["cost_definition"])}. Each point is a measured condition; no fitted frontier is implied.</p>')
        if series.get('family') == 'hallucination':
            output.append('<p>Read contradiction rates with specific-assertion coverage, off-topic share and recovery. A lower fraction alone can reflect abstention or irrelevant outputs. Coverage is shown with each exact condition below.</p>')
        if numeric:
            min_x, max_x = min(p["cost"] for p in numeric), max(p["cost"] for p in numeric)
            min_y = min((p.get("ci") or [p["value"], p["value"]])[0] for p in numeric)
            max_y = max((p.get("ci") or [p["value"], p["value"]])[1] for p in numeric)
            output.append('<svg viewBox="0 0 540 200" role="img" aria-label="Measured quality versus cost"><path d="M45 20V145H510" class="axis"/>')
            for point in numeric:
                if unit == 'samples' and point['cost'] not in (1, 2, 4, 8, 16, 32):
                    raise ValueError('Budget points must use frozen candidate prefixes')
                x = (55 + 88*(1, 2, 4, 8, 16, 32).index(point['cost']) if unit == 'samples'
                     else 55 + 440*(point["cost"]-min_x)/(max_x-min_x or 1))
                y = 135 - 100*(point["value"]-min_y)/(max_y-min_y or 1)
                if point.get("ci") is not None:
                    lower, upper = (135 - 100*(b-min_y)/(max_y-min_y or 1) for b in point["ci"])
                    output.append(f'<path d="M{x} {lower}V{upper}M{x-4} {lower}H{x+4}M{x-4} {upper}H{x+4}" class="whisker"/>')
                output.append(f'<circle cx="{x}" cy="{y}" r="5"><title>{escape(display_label(point.get("condition", "Unspecified")))}: budget {point["cost"]}, value {point["value"]}</title></circle>')
            output.append(f'<text x="6" y="36">{rate(max_y)}</text><text x="6" y="138">{rate(min_y)}</text>')
            if unit == 'samples':
                output.extend(f'<text x="{55+i*88}" y="166" text-anchor="middle">{n}</text>' for i,n in enumerate((1,2,4,8,16,32)))
            else:
                output.append(f'<text x="55" y="166">{escape(round(min_x, 4))}</text><text x="495" y="166" text-anchor="end">{escape(round(max_x, 4))}</text>')
            output.append(f'<text x="275" y="188" text-anchor="middle">{escape("Prescribed experimental sample prefixes" if unit == "samples" else unit)}</text></svg>')
        output.append('<details><summary>Exact conditions, coverage and measured cost components</summary><table><thead><tr><th>Condition</th><th>Budget</th><th>Value / interval</th><th>Count</th><th>Cached selector wall time / cell</th><th>Recurring helper calls / USD per cell</th><th>Generation component / limits</th></tr></thead><tbody>')
        for point in points:
            condition = point.get('condition', 'Unspecified')
            coverage = ''
            if 'assertion_share' in point:
                coverage = f'<br>Specific assertion share: {rate(point["assertion_share"])}; off-topic / specific: {rate(point.get("off_topic_share_of_specific"))}'
            interval = ('Not measured' if point.get('ci') is None else ' to '.join(rate(v) for v in point['ci']))
            output.append(f'<tr><td title="{escape(condition)}">{escape(display_label(condition))}</td><td>{value(point.get("cost"))}</td><td>{rate(point.get("value"))}<br>{interval}{coverage}</td><td>{value(point.get("count"))}</td><td>{value(point.get("cached_selector_wall_seconds"), "seconds")}<br>{escape(point.get("cached_timer_cohort", "Timing not measured"))}</td><td>{value(point.get("recurring_helper_calls_per_cell"))} calls / {value(point.get("recurring_helper_usd_per_cell"), "USD")}<br>{escape(point.get("helper_cost_scope", "Not measured"))}</td><td>{value(point.get("generation_component_gpu_seconds"), "GPU task seconds")}<br>{escape(point.get("generation_component_measurement", "Not measured"))}<br>{escape(point.get("control_note", ""))}</td></tr>')
        output.append("</tbody></table></details></section>")
    return "".join(output)


def ablation_charts(series_rows):
    if not series_rows:
        return ''
    output = ['<details><summary>Component additions and removals: paired changes</summary><p>Dots show the change from the unchanged parent or matched control. Intervals resample whole related groups. These development comparisons do not establish full faithfulness.</p>']
    for series in series_rows:
        points = series['points']
        low = min([0.0] + [(p.get('ci') or [p['value']])[0] for p in points])
        high = max([0.0] + [(p.get('ci') or [p['value']])[-1] for p in points])
        scale = high - low or 1.0
        x = lambda v: 65 + 425 * (v - low) / scale
        height = 70 + len(points) * 35
        label = series['label'].replace(series['family'], display_label(series['family']), 1)
        output.append(f'<section class="curve"><h4>{escape(label)}</h4><p>{escape(series["cohort"])}</p><svg viewBox="0 0 540 {height}" role="img" aria-label="{escape(label)}"><path d="M{x(0)} 10V{height-30}" class="axis"/>')
        for i, point in enumerate(points):
            y = 30 + 35*i
            if point.get('ci'):
                a,b = map(x, point['ci'])
                output.append(f'<path d="M{a} {y}H{b}M{a} {y-4}V{y+4}M{b} {y-4}V{y+4}" class="whisker"/>')
            output.append(f'<text x="10" y="{y+4}">{i+1}</text><circle cx="{x(point["value"])}" cy="{y}" r="5"><title>{escape(display_label(point["condition"]))}: change {point["value"]}</title></circle>')
        output.append(f'<text x="65" y="{height-8}">{low*100:.1f} pp</text><text x="490" y="{height-8}" text-anchor="end">{high*100:.1f} pp</text></svg><table><thead><tr><th>Point / comparison</th><th>Paired change</th><th>95% interval</th><th>Groups / limits</th></tr></thead><tbody>')
        for i, point in enumerate(points):
            interval = ('Not measured' if point.get('ci') is None else ' to '.join(f'{v*100:.1f} pp' for v in point['ci']))
            output.append(f'<tr><td title="{escape(point["condition"])}">{i+1}. {escape(display_label(point["condition"]))}</td><td>{point["value"]*100:.1f} pp</td><td>{escape(interval)}</td><td>{value(point.get("groups"))}; {escape(point.get("warning") or "")}</td></tr>')
        output.append('</tbody></table></section>')
    output.append('</details>')
    return ''.join(output)


def validate_report(report):
    def records(node):
        if isinstance(node, dict):
            yield node
            for child in node.values():
                yield from records(child)
        elif isinstance(node, list):
            for child in node:
                yield from records(child)
    nested = list(records(report))
    if any(row.get("cohort") == "test" or row.get("split") == "test" for row in nested) and report.get("test_reveal_authorized") is not True:
        raise ValueError("Test dashboard requires the frozen planned reveal authorization")
    for row in nested:
        if row.get("official_full_grid") is True and (row.get("scope") != "full_grid" or row.get("complete_grid") is not True):
            raise ValueError("Official benchmark metrics require complete original full grids")
        for key in ("value", "numerator", "denominator", "eligible_count", "missing_count", "cost"):
            number = row.get(key)
            if isinstance(number, (float, int)) and (isinstance(number, bool) or not math.isfinite(number)):
                raise ValueError("Report numbers must be finite")
        if isinstance(row.get("denominator"), (float, int)) and row["denominator"] < 0:
            raise ValueError("Negative denominator")
        if isinstance(row.get("value"), (int, float)) and row.get("ci") is not None:
            ci = row["ci"]
            if not isinstance(ci, list) or len(ci) != 2 or not all(isinstance(b, (int, float)) and math.isfinite(b) for b in ci) or ci[0] > ci[1]:
                raise ValueError("Numeric CI must have finite ordered bounds")


def build(report):
    validate_report(report)
    cohort = report.get("cohort", "development")
    findings = report.get("reviewed_findings", [])
    if findings and not 3 <= len(findings) <= 5:
        raise ValueError("Provide three to five reviewed findings")
    for finding in findings:
        if not finding.get("reviewed_by") or not finding.get("evidence"):
            raise ValueError("Every finding requires its review author and evidence")
    tabs, panels = [], []
    for index, (key, label) in enumerate(METHODS.items()):
        method = report.get("methods", {}).get(key, {})
        status = method.get("status", "Not run")
        tabs.append(f'<button role="tab" id="tab-{key}" aria-controls="panel-{key}" aria-selected="{str(index==0).lower()}" tabindex="{0 if index==0 else -1}" data-key="{key}">{label}</button>')
        panel = f'<section class="method-panel" id="panel-{key}" role="tabpanel" aria-labelledby="tab-{key}" {"" if index==0 else "hidden"}><div class="method-heading"><h2>{label}</h2><span class="status">{escape(status)}</span></div>'
        panel += f'<p>{escape(method.get("hypothesis", "This comparison has not been specified in the current report."))}</p>'
        panel += paragraphs(method.get("findings", []))
        if key=='sample_selection':
            panel += candidate_diagnostic_section(report.get('candidate_diagnostic'))
        rows=method.get('metrics',[])
        shown=combination_tables(rows) if key=='combinations' else consensus_tables(rows) if key=='consensus' else metrics_table(rows)
        panel += "<h3>Comparisons and coverage</h3>" + shown
        if method.get("paired_metrics"):
            panel += '<details><summary>Paired differences with whole-group uncertainty</summary>' + metrics_table(method["paired_metrics"]) + "</details>"
        panel += "<h3>Quality versus sampling budget</h3>" + scaling_chart(method.get("scaling", []))
        panel += f'<section id="budget-{key}"><h3>Family-specific quality versus budget</h3>' + cost_chart(method.get("cost_frontier", [])) + '</section>'
        panel += ablation_charts(method.get('component_ablations', []))
        panel += cost_components_table(method.get('cost_components',[]),report.get('cost_notes',[]))
        panel += "<h3>Wins, regressions, and unchanged cases</h3>" + traces(method.get("traces", []))
        panel += "<h3>Limitations and next decision</h3>" + paragraphs(method.get("limits", ["No method-level conclusion yet."]))
        panel += f'<p><strong>Next action:</strong> {escape(method.get("next_action", "Complete and review the representative comparison."))}</p></section>'
        panels.append(panel)
    if findings:
        findings_html = "<ol class=\"findings\">" + "".join(
            f'<li><h2>{escape(item["claim"])}</h2><p>{escape(item.get("detail", ""))}</p><details><summary>Evidence and review</summary><p class="evidence">{escape(item["evidence"])}. Reviewed by {escape(item["reviewed_by"])}.</p></details></li>' for item in findings) + "</ol>"
        if report.get('full_development'):
            findings_html='<p class="meta">Reviewed partial-grid DEV pilot findings. Complete original-grid baselines appear separately below.</p>'+findings_html
    else:
        findings_html = '<div class="empty-findings"><h2>Scientific findings are pending review</h2><p>Generation and setup progress are shown separately. No method has been promoted from missing measurements.</p></div>'
    progress = report.get("progress", {})
    api = report.get("api", {})
    summary = '<dl class="progress">' + "".join(f'<div><dt>{label}</dt><dd>{value(number, unit)}</dd></div>' for label, number, unit in (
        ("Phase", progress.get("phase"), ""), ("Completed cells", progress.get("completed_cells"), ""),
        ("Expected cells", progress.get("expected_cells"), ""), ("Elapsed execution", progress.get("elapsed_hours"), "hours"),
        ("API usage estimate", api.get("actual_usd"), "USD"), ("API reserved", api.get("reserved_usd"), "USD"))) + "</dl>"
    if api.get('pricing_status'):summary+=paragraphs([api['pricing_status']])
    provenance = report.get("provenance", {})
    provenance_html = "<dl>" + "".join(f"<dt>{escape(key)}</dt><dd>{value(provenance.get(key))}</dd>" for key in
        ("scope", "split_manifest_sha256", "cohort_manifest_sha256", "source_commit", "artifact_sha256")) + "</dl>"
    payload = json.dumps(report, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    return TEMPLATE.replace("__TITLE__", escape(report.get("title", "Frozen Oracle Lens experiments"))).replace(
        "__UPDATED__", escape(report.get("updated_utc", "Timestamp missing"))).replace("__COHORT__", escape(cohort)).replace(
        "__RUNS__", escape(", ".join(report.get("run_ids", [])) or "No run IDs provided")).replace(
        "__FINDINGS__", findings_html).replace("__PROGRESS__", summary+full_dev_a32_section(report.get('full_development_a32'))+full_development_section(report.get('full_development'))).replace("__TABS__", "".join(tabs)).replace(
        "__PANELS__", "".join(panels)).replace("__NOTES__", paragraphs(report.get("endpoint_notes", ["Endpoints and denominators will accompany each validated comparison."])) + provenance_html).replace("__DATA__", payload)


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><link rel="icon" href="data:,"><style>
:root{--page:#fafcff;--ink:#172b35;--muted:#566875;--line:#dce7ee;--active:#164e63;--accent:#147a9b;--uncertain:#9a4b16}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:16px/1.6 'Segoe UI',Arial,sans-serif}main{max-width:1240px;margin:auto;padding:42px 30px 70px}h1{font-size:36px;line-height:1.18;font-weight:650;max-width:850px;margin:0 0 16px}h2{font-size:22px;line-height:1.35;font-weight:600;margin:0 0 8px}h3{font-size:18px;margin:30px 0 10px}h4{font-size:16px;margin:0 0 10px}p{max-width:80ch;margin:8px 0 14px}.meta,.evidence{color:var(--muted);font-size:14px;overflow-wrap:anywhere}dd{overflow-wrap:anywhere}.findings details{font-size:14px;padding:8px 12px;max-width:80ch}.meta{display:flex;gap:24px;flex-wrap:wrap}.findings{list-style:none;padding:0;margin:32px 0}.findings li{padding:20px 0 20px 20px;border-left:4px solid var(--accent);margin-bottom:18px}.findings p{margin-bottom:6px}.empty-findings{padding:22px;background:#eaf3f8;margin:28px 0}.progress{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:16px 0;margin:0 0 30px}.progress dt{font-size:13px;color:var(--muted)}.progress dd{margin:3px 0;font-weight:600}.tab-list{display:flex;overflow-x:auto;gap:6px;border-bottom:2px solid var(--line);padding-bottom:0}button{background:transparent;border:0;white-space:nowrap;font:inherit;font-size:14px;cursor:pointer;padding:12px 16px;color:var(--muted);border-bottom:3px solid transparent}button[aria-selected=true]{color:var(--active);border-bottom-color:var(--accent);font-weight:650}button:focus-visible{outline:3px solid var(--accent);outline-offset:-3px}.method-panel{padding:28px 0}.method-heading{display:flex;gap:18px;align-items:center;flex-wrap:wrap}.status{font-size:13px;color:var(--active);background:#e4eff5;padding:3px 10px;border-radius:4px}.missing{color:var(--uncertain)}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;padding:12px 10px;border-bottom:1px solid var(--line)}th{font-weight:600;color:var(--muted);background:#f0f5f9}.table-scroll{overflow-x:auto}details{border:1px solid var(--line);padding:14px 18px;margin:12px 0;border-radius:6px}summary{cursor:pointer;font-weight:600;overflow-wrap:anywhere}.trace-pair{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:18px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 'Segoe UI',Arial,sans-serif;margin:0;padding:16px;background:white;border-left:3px solid var(--line)}.curve{max-width:700px;margin:18px 0;overflow-x:auto}svg{width:100%;height:auto;background:white}svg .axis{fill:none;stroke:var(--line);stroke-width:2}svg .line{fill:none;stroke:var(--accent);stroke-width:3}svg .whisker{fill:none;stroke:var(--active);stroke-width:1.5}svg circle{fill:var(--active)}svg text{fill:var(--muted);font:12px 'Segoe UI',Arial,sans-serif}footer{border-top:1px solid var(--line);padding-top:20px;color:var(--muted);font-size:14px}[hidden]{display:none!important}@media(max-width:850px){main{padding:28px 18px}h1{font-size:29px}.progress{grid-template-columns:repeat(3,1fr)}.trace-pair{grid-template-columns:1fr}}@media(max-width:480px){.progress{grid-template-columns:repeat(2,1fr)}}
</style></head><body><main><header><h1>__TITLE__</h1><div class="meta"><span>Updated __UPDATED__</span><span>Cohort: __COHORT__</span><span>Runs: __RUNS__</span></div><p><a href="../docs/REPORT.md">Working research report (local Markdown)</a></p></header>
__FINDINGS__<section aria-label="Execution progress"><h3>Execution progress</h3>__PROGRESS__</section><nav class="tab-list" role="tablist" aria-label="Experiment methods">__TABS__</nav>__PANELS__
<footer>__NOTES__<p>FVE means fraction of variance explained. Reconstruction fit alone does not establish faithful recovery. Missing results are not zero, and development findings are provisional.</p></footer></main>
<script id="report-data" type="application/json">__DATA__</script><script>
const tabs=[...document.querySelectorAll('[role=tab]')];function activate(tab){tabs.forEach(t=>{const selected=t===tab;t.setAttribute('aria-selected',selected);t.tabIndex=selected?0:-1;document.getElementById(t.getAttribute('aria-controls')).hidden=!selected;});}tabs.forEach((tab,index)=>{tab.addEventListener('click',()=>activate(tab));tab.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;if(next!==undefined){event.preventDefault();activate(tabs[next]);tabs[next].focus();}});});
</script></body></html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="Compact reviewed experiment JSON")
    parser.add_argument("--output", required=True, help="Standalone local HTML")
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(build(report))
    temporary.replace(output)
    print(json.dumps({"output": str(output), "built_utc": datetime.now(timezone.utc).isoformat(), "publication": False}))


if __name__ == "__main__":
    main()
