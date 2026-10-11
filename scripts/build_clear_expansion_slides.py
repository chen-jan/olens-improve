"""Plain-language presentation of the frozen expanded Oracle Lens evidence.

Preserves the complete source-bound appendix. No inference, fitting, bootstrap,
or new scientific judgments. Original-relative changes are descriptive arithmetic
on retained native rates; the existing paired contrasts keep their actual parents.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import build_expansion_slides as source
from build_slides import text, rect, line, TEAL, BLUE, INK, MUTED, LINE

RAW = 'raw_n1-n1'
CAP = 'capped_n1-n1'
ORANGE = 'B57123'
TASKS = {'hallucination': 'Hallucination (chat)', 'multihop_mt': 'Multihop (multi-token)',
         'chain_intermediates': 'Chained intermediates', 'role_bound_association': 'Role-bound association'}
ENDPOINTS = {'hallucination':'Contradicting readouts / lower better',
             'multihop_mt':'Required-name recovery / higher better',
             'chain_intermediates':'Required-number recovery / higher better',
             'role_bound_association':'Required-role recovery / higher better'}
METHODS = {
    'selection': ('Choose one description', 'Generate several descriptions. Keep the one that best matches the captured model state.'),
    'consensus': ('Keep repeated statements', 'Keep statements supported by several descriptions. Optional filters remove conflicting statements.'),
    'pruning': ('Remove weak bullets', 'Delete a bullet when removing it barely changes the match to the model state.'),
    'pooling': ('Combine original bullets', 'Build a description from up to four original bullets drawn from different samples.'),
    'verification': ('Compare with other model states', 'Prefer a description that fits this state more strongly than matched comparison states.'),
    'editing': ('Edit the description', 'Ask a helper to propose changes. Keep a change only when its match score improves.'),
    'combinations': ('Add a second step', 'Start from a selected or combined description, then apply another filter or deletion step.'),
}
RESULT_BULLETS = {
    'selection': ['Try 1, 2, 4, 8, 16 or 32 descriptions.', 'A stronger match score does not ensure more recovered facts.'],
    'consensus': ['Agreement filters can remove wrong claims.', 'They also remove many required names and relations.'],
    'pruning': ['A bullet can add little to the match score.', 'That bullet may still contain a required name.'],
    'pooling': ['Combine intact bullets from several descriptions.', 'The improved match score brings mixed task results.'],
    'verification': ['Compare the actual state with matched alternatives.', 'This helps some tasks; individual details can remain wrong.'],
    'editing': ['One or two helper editing rounds were tested.', 'The final recovery totals match the pooled parent.'],
    'combinations': ['Add filtering to an existing method.', 'Fewer errors can come with lower fact recovery.'],
}
RESULT_TITLES = {
    'selection':'More samples improve the match score; task gains vary',
    'consensus':'Keeping repeats removes errors and useful facts',
    'pruning':'Removing a weak bullet can lose a required name',
    'pooling':'Combining bullets brings mixed task gains',
    'verification':'Comparing model states helps some tasks',
    'editing':'Editing adds little beyond combining bullets',
    'combinations':'A second filter brings mixed task gains',
}


def task_name(family):
    return TASKS.get(family, source.TITLES[family])


def clear_name(condition, active):
    if condition == RAW: return 'Original released lens'
    if condition == CAP: return 'Original, four bullets'
    row = active[condition]; method = row['method']; n = row['n']
    fixed = {'best_n_exact': 'Choose best', 'random_complete': 'Choose random',
             'pooled_greedy_swap': 'Combine bullets', 'editing_round1': 'Edit once',
             'editing_round2': 'Edit twice', 'best_n_specificity_mean': 'Compare average',
             'best_n_specificity_max': 'Compare strongest',
             'best_n_specificity_mean_abstain_nonpositive': 'Compare + abstain',
             'likelihood_true_minus_mean_two_controls': 'Compare text likelihood',
             'own_mean_log_likelihood': 'True-state likelihood',
             'control_mean_log_likelihood': 'Control-only likelihood'}
    if method.startswith('consensus_'):
        support=round(row.get('thresholds',{}).get('support_fraction',0)*16)
        kind='same meaning' if 'semantic_' in method else 'same wording'
        return f'Keep repeats: {support}/16 / {kind}'
    if 'random_delete' in method:return 'Random bullet removal / '+str(row.get('thresholds',{}).get('loss_threshold', method.rsplit('_',1)[-1]))
    if method.startswith('prune_coefficient'):return 'Remove small weights / '+method.rsplit('_',1)[-1]
    if method.startswith('prune_loo'):return 'Remove weak bullets / '+method.rsplit('_',1)[-1]
    if method.startswith('pooled_specificity_mean_then'):return 'Combine + compare + remove'
    if method.startswith('pooled_specificity'):return 'Combine + compare'
    if method.startswith('pooled_greedy_swap_then'):return 'Combine + remove'
    if method.startswith('editing_round2_then'):return 'Edit twice + remove'
    return fixed.get(method,'Recorded combination') + f' / N={n}'


def simple_panel(x, y, family, conditions, metrics, names):
    """Always include the raw released lens, outside the frozen method group."""
    chosen = [RAW, CAP] + [c for c in conditions if c not in (RAW, CAP)]
    chosen = list(dict.fromkeys(chosen))
    colors = [ORANGE, MUTED, BLUE, TEAL, '7359AA', '388357']
    items = [rect(x, y, 500, 282, 'FFFFFF'),
             text(x+14, y+8, 470, 34, task_name(family), 22, bold=True),text(x+14,y+43,470,23,ENDPOINTS[family],15,MUTED)]
    px, pw = x+260, 158
    for j, c in enumerate(chosen):
        m = metrics[c, family]; yy = y+85+j*(140/max(1, len(chosen)-1)); color = colors[j]
        items += [text(x+14, yy-15, 235, 48, source.wrapped(names[c], 28), 17, color, c==RAW),
                  line(px, yy, px+pw, yy, LINE)]
        if m.get('ci95'):
            items.append(line(px+pw*m['ci95'][0], yy, px+pw*m['ci95'][1], yy, color, 3))
        if m['value'] is not None: items.append(source.dot(px+pw*m['value'], yy, color, 5))
        items.append(text(x+425, yy-13, 72, 32, source.percent(m['value'])+('†' if source.native_warning(m) else ''), 17, color, True))
    for z in (0, .5, 1): items.append(text(px+pw*z-14, y+258, 62, 24, f'{100*z:g}%', 14, MUTED))
    return items


def effect_panel(x,y,family,condition,metrics,names,pair):
    items=[rect(x,y,500,282,'FFFFFF'),text(x+14,y+8,470,34,task_name(family),22,bold=True),text(x+14,y+43,470,23,ENDPOINTS[family],15,MUTED)]
    for j,c in enumerate((RAW,condition)):
        yy=y+85+j*50;m=metrics[c,family];color=ORANGE if c==RAW else BLUE
        items += [text(x+14,yy-16,238,44,source.wrapped(names[c],29),17,color,c==RAW),
                  text(x+280,yy-14,190,35,source.percent(m['value']),25,color,True)]
    lo,hi=pair.get('ci95_delta') or (pair['delta'],pair['delta'])
    bound=max(.05,abs(lo),abs(hi),abs(pair['delta']))*1.12
    px,pw=x+80,365; at=lambda z:px+pw*(z/bound+1)/2; yy=y+205
    items += [text(x+14,y+166,470,31,'Change from original / percentage points',17,MUTED),
              line(px,yy,px+pw,yy,LINE),line(at(0),yy-22,at(0),yy+22,ORANGE,2),
              line(at(lo),yy,at(hi),yy,BLUE,4),source.dot(at(pair['delta']),yy,BLUE,6),
              text(x+14,y+239,480,30,source.pp(pair['delta'])+' / 95% interval '+source.ci(pair.get('ci95_delta'),True)+' pp'+(' †' if pair.get('warnings') or pair.get('warning') else ''),17,BLUE,True),
              text(at(0)-7,yy+24,48,24,'0',14,ORANGE)]
    return items


def revised_pages(inputs, qa=False):
    original, refs, core = original_pages_from(inputs, qa)
    results, inventory, review, active, metrics, hashes, pres, chosen, contrasts, examples = inputs
    names = {c:clear_name(c, active) for c in active}
    pages = []

    def add(title, items, notes):
        pages.append({'title':title, 'items':source.base(title,len(pages)+1,hashes,qa)+items,
                      'notes':notes+'\nExact source hashes: '+json.dumps(hashes)})

    # Findings stay ahead of the method detail.
    pages.extend(deepcopy(original[:2]))
    # Raw rates anchor the opening findings before the fuller baseline slide.
    pages[1]['items'].append(text(75,788,1445,54,'Original released lens: '+ ' / '.join(task_name(f)+': '+source.percent(metrics[RAW,f]['value']) for f in source.FAMILIES[:2])+'\n'+ ' / '.join(task_name(f)+': '+source.percent(metrics[RAW,f]['value']) for f in source.FAMILIES[2:]),18,ORANGE))
    glossary=[]
    for i,(key,(heading,body)) in enumerate(METHODS.items()):
        x=70+(i%2)*750; y=211+(i//2)*144
        glossary += [rect(x,y,710,130,'FFFFFF'),text(x+17,y+10,672,35,heading,25,TEAL,True),
                     text(x+17,y+52,672,67,source.wrapped(body,64),21)]
    add('Seven ways to improve one lens description', glossary,
        'Plain-language guide to the seven frozen approach groups. These are alternatives and combinations, not a required pipeline. Full algorithms and identifiers remain in the appendix.')
    vocab=[]
    for i,(heading,body) in enumerate([
        ('Sample count: N','N=32 means 32 original descriptions of the same captured state. Choosing best and choosing random use the same pool.'),
        ('Support threshold','2 of 16 means a statement must appear in at least two descriptions. A higher threshold keeps fewer statements.'),
        ('Removal threshold','Allow a small drop in the match score when deleting a bullet. Larger thresholds permit more deletion.'),
        ('Editing rounds','Once or twice means one or two proposal-and-score cycles. Edited text retains its recorded parent.')]):
        x=70+(i%2)*750; y=228+(i//2)*271
        vocab += [rect(x,y,710,245,'FFFFFF'),text(x+22,y+17,662,49,heading,29,TEAL,True),text(x+22,y+87,662,137,source.wrapped(body,47),27)]
    add('A version changes a setting, not the frozen model',vocab,
        'All model weights, activation identities and benchmark endpoints are frozen. Full variant identifiers record exact pool sizes, support/removal thresholds, filters and editing rounds. The helper is Luna. The match score is fraction of variance explained by the released activation reconstructor (FVE); it is separate from factual quality.')
    baseline=[text(75,223,440,520,source.wrapped('• Original released lens: one raw sample.\n\n• Four-bullet baseline: the same sample with at most four intact bullets.\n\n• Both are shown on every task result panel.\n\n• Other methods also use at most four bullets and 256 Qwen tokens.',37),25)]
    for i,f in enumerate(source.FAMILIES):baseline+=simple_panel(550+(i%2)*520,215+(i//2)*300,f,[],metrics,names)
    baseline.append(text(550,817,1010,26,'Orange: original released lens. Gray: same sample, four bullets. Exact task rates.',18,MUTED))
    add('Compare every method with the original released lens',baseline,
        'Original raw baseline is raw_n1-n1; four-bullet comparator is capped_n1-n1. Raw is cap-exempt. Their native rates and grouped pointwise 95% intervals are copied without alteration. Required names, numbers and relations are task-specific recovery endpoints; transcript error is wrong/(wrong+off_topic+consistent). Raw reconstruction diagnostics are unavailable in the frozen artifact; never substitute capped reconstruction for raw.')
    # A single simple sampling figure, early in the story.
    trend=[]
    for i,f in enumerate(source.FAMILIES):
        x=550+(i%2)*520; y=215+(i//2)*300
        trend+=source.approach_panel(x,y,f,[],metrics,names,selection=True)
        # Replace technical bank title with its plain task name.
        for item in trend:
            if item.get('x')==x+12 and item.get('y')==y+8:item['text']=task_name(f)+(' ↓' if f=='hallucination' else ' ↑')
        trend.append(text(x+270,y+39,223,25,'Original: '+source.percent(metrics[RAW,f]['value']),15,ORANGE))
    trend += [text(75,224,435,480,source.wrapped('• Read the sample count along the bottom: 1, 2, 4, 8, 16, 32.\n\n• Blue chooses the best match. Gray chooses randomly.\n\n• Orange shows the original released lens. Teal shows four bullets.\n\n• More samples bring mixed fact recovery.',36),25),
              text(550,817,1010,26,'Native task rates / grouped pointwise 95% intervals / orange original baseline',17,MUTED)]
    add('More samples bring mixed gains across the four tasks',trend,
        'All six frozen sample counts. Native absolute rates and grouped pointwise 95% intervals copied from final-v1. The scored N=1 condition differs from the raw cap-exempt original. Blue best and gray random are same-pool comparisons. The x-axis uses the six explicit doubling values, not a fitted scaling law.')
    # One plain mechanism slide followed by one concise result slide per method.
    for j,(group,(heading,body)) in enumerate(METHODS.items()):
        mechanism=deepcopy(original[4+j*2])
        mechanism['title']=heading+' / how it works';mechanism['items'][2]['text']=mechanism['title']
        pages.append(mechanism)
        a=pres['approaches'][group]; condition=a['contrast']['condition']
        variants=a.get('chart_conditions',[])
        if group=='selection': variants=['best_n_exact-n16','best_n_exact-n32','random_complete-n32']
        else: variants=[condition]+[c for c in variants if c!=condition][:2]
        variants=list(dict.fromkeys(variants))[:3]
        left=[]
        for i,b in enumerate(RESULT_BULLETS[group]):left.append(text(75,218+i*102,440,94,source.wrapped('• '+b,37),24))
        left.append(text(75,428,440,51,'Change from original lens',23,TEAL,True))
        changes=[]
        for f in source.FAMILIES:
            v,base=metrics[condition,f]['value'],metrics[RAW,f]['value']
            changes.append(task_name(f)+': '+source.pp(None if v is None or base is None else v-base))
        left.append(text(75,485,440,135,'\n'.join(changes),19))
        left.append(text(75,625,440,79,'Changes use the original lens. Right: paired pointwise 95% intervals from the added exploratory comparison.',19,MUTED))
        e=a['example'];before=e.get('baseline_excerpt',e['baseline_text']);after=e.get('selected_excerpt',e['selected_text'])
        left += [text(75,700,440,32,'Example: '+task_name(e['family']),18,TEAL,True),text(75,738,440,60,source.wrapped('After: '+after,47),17),text(75,802,440,42,source.wrapped(e['interpretation'],59),15,MUTED)]
        charts=[]; supplement=globals().get('original_reference_supplement'); pairs={} if supplement is None else {(r['condition'],r['family']):r for r in supplement['comparisons']}
        for i,f in enumerate(source.FAMILIES):
            pair=pairs.get((condition,f))
            charts+=(effect_panel(550+(i%2)*520,215+(i//2)*300,f,condition,metrics,names,pair) if pair else simple_panel(550+(i%2)*520,215+(i//2)*300,f,variants,metrics,names))
        charts.append(text(550,817,1010,26,('Orange: original / paired changes: added exploratory pointwise 95% / variants in appendix' if pairs else 'Orange: original / gray: four bullets / variants: recorded native rates, pointwise 95%'),16,MUTED))
        add(RESULT_TITLES[group],left+charts,
            'Highlighted condition: '+condition+'\nOriginal-relative differences are exploratory. '+('Post-hoc pointwise paired original-reference intervals are copied from the separately root-checked supplement; no simultaneous interval or new holdout is claimed. Supplement SHA: '+globals()['original_reference_supplement_sha256']+'\nExact original-reference records: '+json.dumps([pairs[condition,f] for f in source.FAMILIES]) if pairs else 'Descriptive changes subtract retained native rates; no original-relative paired interval was frozen for this intervention.')+'\nExact absolute source metrics: '+json.dumps({c:{f:metrics[c,f] for f in source.FAMILIES} for c in [RAW,CAP]+variants})+'\nActual frozen paired reference: '+json.dumps(a['contrast'])+'\nReviewed interpretation: '+json.dumps(review['method_findings'][group],ensure_ascii=False)+'\nFull original method result slide follows in the detailed appendix.\nExample exact before: '+before+'\nExample exact after: '+after+'\nFull source example: '+json.dumps(e,ensure_ascii=False))
    # Retain the useful later overview and limits without the duplicate sampling plot.
    pages.extend(deepcopy(original[19:core]))
    clear_core=len(pages)
    # Keep all original method-result detail, all 70 settings, all reconstruction
    # rows and all frozen paired contrast records visible and unchanged.
    pages.extend(deepcopy([original[5+j*2] for j in range(7)]))
    pages.extend(deepcopy(original[core:]))
    # Add a raw reference to retained method-detail charts, without changing
    # any previously plotted variant or exact source statistic.
    for j,p in enumerate(pages[clear_core:clear_core+7]):
        if j==0:continue # sampling panel already has the original reference
        for i,f in enumerate(source.FAMILIES):
            x=550+(i%2)*520;y=215+(i//2)*300;m=metrics[RAW,f]
            xx=x+245+168*m['value']
            p['items'] += [line(xx,y+47,xx,y+250,ORANGE,1),text(x+12,y+253,228,23,'Original: '+source.percent(m['value'])+' / orange line',14,ORANGE)]
    for p in pages:
        # Official WorkspaceBench names stay primary throughout the delivered
        # deck, including the presentation-only labels of the preserved appendix.
        for item in p['items']:
            if 'text' in item:
                for f,old in source.TITLES.items():item['text']=item['text'].replace(old,TASKS[f])
        for f,old in source.TITLES.items():p['title']=p['title'].replace(old,TASKS[f])
        if p['title']=='Reconstruction fit across the sample budgets':
            p['items'][-1]['text']='Match score: original raw fit unavailable / teal: original four bullets / blue: best / amber: pooled / 95% CI'
            p['items'][-1]['size']=17
        elif p['title'].startswith('All reconstruction settings'):
            footer=next(a for a in reversed(p['items']) if a.get('kind')=='text' and a.get('y',0)>=790)
            footer['text']='Original full-prose fit unavailable; four-bullet fit shown separately. † Coverage and interval warnings: notes.'
            footer['size']=17;footer['color']=ORANGE
    for i,p in enumerate(pages,1):p['items'][5]['text']=str(i)
    return pages, refs, clear_core


def build(args):
    if args.original_reference:
        supplement=json.loads(args.original_reference.read_text())
        if supplement.get('cohort')!='full' or supplement.get('reference')!=RAW or len(supplement.get('comparisons',[]))!=28:raise ValueError('Require complete full-bank original-reference supplement')
        for field,path in [('results_sha256',args.results),('manifest_sha256',args.inventory),('root_review_sha256',args.review)]:
            if supplement.get(field)!=source.digest(path):raise ValueError('Original-reference supplement source mismatch: '+field)
        globals()['original_reference_supplement']=supplement;globals()['original_reference_supplement_sha256']=source.digest(args.original_reference)
    original_pages=source.pages_from
    try:
        source.pages_from=revised_pages
        # revised_pages uses the original function rather than recursively calling
        # the process-local wrapper installed for source.build.
        revised_pages.__globals__['original_pages_from']=original_pages
        receipt=source.build(args.results,args.inventory,args.review,args.output,False,args.reconstruction)
    finally:source.pages_from=original_pages
    path=Path(args.output)/'build.json'
    receipt.update({'presentation_revision':'clear-v1','created_utc':datetime.now(timezone.utc).isoformat(),
                    'clear_builder_sha256':source.digest(__file__),
                    'original_relative_changes':'descriptive arithmetic; no new paired confidence interval',
                    'original_method_detail_slides':7,'complete_original_appendix_preserved':True})
    if args.original_reference:
        (Path(args.output)/'original-reference-source.json').write_bytes(args.original_reference.read_bytes())
        receipt['original_reference_sha256']=source.digest(args.original_reference)
        receipt['original_relative_changes']='separately reviewed post-hoc exploratory paired pointwise intervals; no joint interval'
        contract_path=Path(args.output)/'source-contract.json'
        contract=json.loads(contract_path.read_text())
        contract['chart_conditions']=list(dict.fromkeys(contract['chart_conditions']+[RAW,CAP]+[r['condition'] for r in supplement['comparisons']]))
        contract['original_reference_sha256']=source.digest(args.original_reference)
        contract['original_reference_uncertainty']='post-hoc exploratory paired pointwise 95%; no simultaneous adjustment'
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        receipt['outputs']['original-reference-source.json']=source.digest(Path(args.output)/'original-reference-source.json')
        receipt['outputs']['source-contract.json']=source.digest(contract_path)
    path.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,required=True);p.add_argument('--inventory',type=Path,default=Path('configs/expansion_manifest_v1.json'))
    p.add_argument('--review',type=Path,required=True);p.add_argument('--reconstruction',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--chrome',type=Path);p.add_argument('--node',default='node')
    p.add_argument('--original-reference',type=Path)
    args=p.parse_args();receipt=build(args)
    if args.chrome:source.render_pdf(args.output,args.chrome,args.node)
    print(json.dumps({k:receipt[k] for k in ('slides','core_slides','source_hashes','inference_calls')}))


if __name__=='__main__':main()
