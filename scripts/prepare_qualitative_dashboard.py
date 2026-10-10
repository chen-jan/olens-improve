"""Prepare a small public case payload; original artifacts stay read-only.

This does not approve publication. The coordinator reviews the prepared payload
and its source digests before setting status=root_reviewed and packaging it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

try:
    from dashboard_qualitative import PANEL_SHA, PANEL_IDS, PRIVATE
    from dashboard_method_sections import label
except ModuleNotFoundError:
    from scripts.dashboard_qualitative import PANEL_SHA, PANEL_IDS, PRIVATE
    from scripts.dashboard_method_sections import label

SKIP = {'retained_raw_cache_record','shared_cache_hit','trace_alias_recovery',
        'source_path','bank_path','cache_path','representative_cache_path',
        'readouts_path','source_sha256','source_sha256s','source_sha256_map',
        'job_id','pid','ts','fp','request_key','response_id','attempt_id',
        'input_tokens','output_tokens','input_path','output_path','tensor_path'}
BANK = {'prompt','response','stimulus','asked_question','steps','start',
        'intermediates','answer','target','target_alts','units','bridges','names',
        'role_a','role_b','action','gold_label','contrast_label'}


def cleaned(value):
    """Remove infrastructure fields, never modify scientific text or numbers."""
    if isinstance(value, dict):
        out = {}
        for k,v in value.items():
            if k in SKIP or k.endswith('_path') or k.endswith('_paths'):
                continue
            if k=='source_bank_item':
                out[k]={name:cleaned(v[name]) for name in BANK if name in v}
            else:
                out[k]=cleaned(v)
        return out
    if isinstance(value,list):return [cleaned(x) for x in value]
    if isinstance(value,str) and PRIVATE.search(value):
        raise ValueError('A scientific quote contains private infrastructure; review explicitly')
    return value


def name(condition):
    if re.fullmatch(r'best_n_exact-n\d+',condition):return 'Best of '+condition.rsplit('n',1)[1]
    return label(condition)


def view(evaluation, condition, selection=None):
    if evaluation is None:
        return {'label':name(condition),'text':selection['text'],
                'verdict':'Not judged: numerical-only variant'}
    verdict=(evaluation['class'] if evaluation.get('class') else
             'Empty abstention' if evaluation.get('empty') else
             'Required recovery match passed' if evaluation.get('pass') else
             'Required recovery match failed')
    return {'label':name(condition),'text':evaluation['text'],'verdict':verdict}


def selection_provenance(selection):
    keys=('method','n','phrase_ids','candidate_id','origin','token_count','bullet_count','reason')
    out={k:selection[k] for k in keys if k in selection}
    out['scoring_limit']='Only the cleaned first 32 tokens per bullet reach the reconstructor.'
    out['atoms']=[{k:a[k] for k in ('source_sample_index','sample_index','source_phrase_id',
        'source_span','original_token_count','scored_token_count','truncated') if k in a}
        for a in selection.get('atoms',selection.get('atom_metadata',[]))]
    return out


def pair(cid,b,p,bname,pname,comment,context_ref,provenance=None):
    return {'cell_id':cid,'baseline':view(b,bname),'proposed':view(p,pname),
        'unchanged':b['text']==p['text'],'assessment':comment,'context_ref':context_ref,
        'judge_evidence':cleaned({'before':b.get('evidence'),'after':p.get('evidence')}),
        'provenance':provenance or {'baseline_condition':bname,'condition':pname}}


def add_efg(out, full, independent):
    if (independent.get('status')!='independent_review_complete'
            or independent.get('panel_sha256')!=PANEL_SHA):
        raise ValueError('Require the independent E/F/G review receipt')
    records={r['anchor']['cell_id']:r for r in full['records']}
    if set(records)!=set(PANEL_IDS):raise ValueError('E/F/G panel differs')
    for cid,r in records.items():
        out['contexts'][cid]=cleaned(r['evaluation_context'])
        out['original_readouts'][cid]={'raw':view(r['raw_n1'],'raw_n1-n1'),
                                      'capped':view(r['capped_n1'],'capped_n1-n1')}
    methods={'contrastive_checks':{'takeaway':'Other-activation comparisons can change wording without fixing wrong entities or arithmetic. Likelihood improvements here are relative to Best of 8, not Best of 32.', 'variants':[],'supplements':[]},
        'editing':{'takeaway':'All eight shared edited outputs are unchanged. Rare changes include cosmetic cleanup and added words; no recovery win is established by these examples.','variants':[],'supplements':[]},
        'independent_checks':{'takeaway':'Existing token diagnostics cover four anchors; four remain unavailable. Token presence cannot establish a complete number, name or relation.','variants':[],'supplements':[]}}
    order=[c['condition'] for c in records[PANEL_IDS[0]]['comparisons'] if c['condition']!='capped_n1-n1']
    for condition in order:
        key='editing' if condition.startswith('editing') else 'contrastive_checks';cases=[]
        for cid in PANEL_IDS:
            r=records[cid];c=next(c for c in r['comparisons'] if c['condition']==condition)
            comment=c['manual_assessment']['comment']
            if cid=='hallucination|chat-lmsys-0023|L60|p00464' and condition=='likelihood_true_minus_mean_two_controls-n8':
                comment+=' Compared with Best of 8 only: Best of 32 is already consistent. Truncated DETR-D and DETR-T attributions remain.'
            selected=next((s for s in r['selection_source']['selections'] if f"{s['method']}-n{s['n']}"==condition),None)
            if selected is None:selected=next((s for s in r['editing_source']['selections'] if f"{s['method']}-n{s['n']}"==condition),None)
            provenance={'baseline_condition':c['baseline_condition'],'condition':condition,
                'original_activation_sha256':r['selection_source']['activation_sha256']}
            if selected:provenance.update(selection_provenance(selected))
            cases.append(pair(cid,c['baseline'],c['proposed'],c['baseline_condition'],condition,comment,cid,provenance))
        methods[key]['variants'].append({'id':condition,'label':name(condition),'cases':cases})
    near=[];tokens=[]
    for cid in PANEL_IDS:
        r=records[cid]
        near.append({'cell_id':cid,'context_ref':cid,'status':'available' if r['E2'] else 'unavailable',
            'reason':'No existing controlled phrase check at this fixed cell.','diagnostic':cleaned(r['E2']),
            'assessment':'Known source-correct phrases are isolated diagnostics. These are not selected prose outputs or proof of hidden-state truth.',
            'provenance':{'condition':'E2 controlled phrase check','new_inference':False}})
        tokens.append({'cell_id':cid,'context_ref':cid,'status':r['G']['availability'],
            'reason':'No existing independent-reader diagnostic at this fixed cell.',
            'diagnostic':cleaned({'instrument':r['G']['instrument'],'controlled_pairs':r['G']['controlled_pairs']}),
            'assessment':r['G']['manual_assessment']['comment'],
            'provenance':{'condition':'G independent token diagnostics','new_inference':False}})
        if tokens[-1]['status']=='unavailable_at_this_anchor':tokens[-1]['status']='unavailable'
    methods['contrastive_checks']['variants'].append({'id':'E2','label':'Controlled numbers and direction · diagnostic only','cases':near})
    methods['independent_checks']['variants']=[{'id':'G','label':'Token support · diagnostic only','cases':tokens}]
    for s in full['supplements']['F']:
        cid=s['cell_id'];out['contexts'][cid]=cleaned(s['evaluation_context']);comp=s['comparison'];f=s['family'];c=comp['families'][f]['examples']['rare_changed'][0]
        comment=s['manual_assessment']
        if cid.startswith('hallucination|chat-dailydialog-0047|'):
            comment+=' The last edited bullet has 36 tokens; only its first 32 are encoded, leaving the added need it beyond direct reconstruction evidence.'
        methods['editing']['supplements'].append(pair(cid,c['baseline'],c['proposed'],comp['baseline_condition'],comp['condition'],comment,cid)|{'label':cid+' · rare edit, no recovery win established'})
    out['methods'].update(methods)


def add_b_combinations(out, full):
    if full['panel_sha256']!=PANEL_SHA or full['coverage']['missing_fixed_anchors']:
        raise ValueError('B/combinations panel is incomplete or different')
    for key,takeaway in [('consensus','Repeated generic claims can displace a required name or number. Semantic matching can grant false support; selected helper audits do not estimate a population error rate.'),
                         ('combinations','Combining components can remove a wrong detail or the only useful mention. Several improved judge classes retain the previously flagged assertion.')]:
        out['methods'][key]={'takeaway':takeaway,'variants':[],'supplements':[],
            'supplement_archive':[]}
    for comp in full['comparisons']:
        key='consensus' if comp['condition'].startswith('consensus_') else 'combinations'
        fixed={c['cell_id']:c for fam in comp['families'].values()
               for c in fam['examples'].get('fixed_anchor',[])}
        if set(fixed)!=set(PANEL_IDS):raise ValueError('Keep every B/combinations anchor')
        cases=[]
        def convert(c):
            cid=c['cell_id'];b=c['baseline'];p=c['proposed']
            out['contexts'].setdefault(cid,cleaned({'source_bank_item':c['source_bank_item'],
                'evaluation_context':p.get('evaluation_context')}))
            provenance={'baseline_condition':comp['baseline_condition'],'condition':comp['condition'],
                'before':selection_provenance(b['selection_provenance']),
                'after':selection_provenance(p['selection_provenance'])}
            return pair(cid,b,p,comp['baseline_condition'],comp['condition'],
                c['manual_assessment']['note'],cid,provenance)
        for cid in PANEL_IDS:cases.append(convert(fixed[cid]))
        out['methods'][key]['variants'].append({'id':comp['condition'],
            'label':name(comp['condition']),'cases':cases})
        # The full packet has per-variant supplements. The public preview retains
        # the first two distinct pairs per conceptual method in its frozen order.
        supplements=out['methods'][key]['supplements']
        seen={(s['baseline']['text'],s['proposed']['text']) for s in supplements}
        for fam in comp['families'].values():
            for c in fam['examples'].get('selected_supplement',[]):
                prepared=convert(c)|{'label':c['cell_id']+' · '+name(comp['condition'])}
                out['methods'][key]['supplement_archive'].append(prepared)
                texts=c['baseline']['text'],c['proposed']['text']
                if len(supplements)>=2 or texts in seen:continue
                supplements.append(prepared)
                seen.add(texts)


def add_acd(out, full, annotations):
    fixed={c['cell']['cell_id']:c for c in full['cases'] if c['kind']=='outcome_blind_shared_anchor'}
    comments={c['cell_id']:c for c in annotations['cases']}
    if set(fixed)!=set(PANEL_IDS):raise ValueError('A/C/D panel differs')
    groups={'A':'sample_selection','C':'pruning','D':'pooling'}
    for group,key in groups.items():
        out['methods'][key]={'takeaway':{'A':'Correct mentions can coexist with wrong surrounding claims. More samples do not make every selected explanation faithful.','C':'Deleting a contradiction can help, but also remove useful information. A judge class flip may occur despite a previously flagged span remaining.','D':'Mixing bullets can improve reconstruction while retaining incompatible names, roles or calculations.'}[group],'variants':[],'supplements':[]}
    def group_of(cond):
        if cond.startswith(('pooled_',)):return 'D'
        if cond.startswith(('prune_', 'random_delete_','coefficient_')):return 'C'
        return 'A'
    def parent_of(cond):
        n=cond.rsplit('-n',1)[-1]
        if cond.startswith(('pooled_','random_complete','best_n_released80')):return 'best_n_exact-n'+n
        if group_of(cond)=='C':return 'capped_n1-n1' if 'n1_' in cond else 'best_n_exact-n32'
        return 'raw_n1-n1' if cond=='capped_n1-n1' else 'capped_n1-n1'
    for condition in full['condition_order']:
        group=group_of(condition);cases=[]
        for cid in PANEL_IDS:
            c=fixed[cid];outputs={o['condition']:o for o in c['outputs']};p=outputs[condition];b=outputs[parent_of(condition)]
            bank=cleaned(c['context']);out['contexts'].setdefault(cid,bank)
            for name_key,cond in [('raw','raw_n1-n1'),('capped','capped_n1-n1')]:
                original=outputs[cond];out['original_readouts'].setdefault(cid,{})[name_key]=view(original['retained_evaluation'],cond,original['selection'])
            cases.append({'cell_id':cid,'baseline':view(b['retained_evaluation'],b['condition'],b['selection']),
                'proposed':view(p['retained_evaluation'],condition,p['selection']),
                'unchanged':b['selection']['text']==p['selection']['text'],'context_ref':cid,
                'assessment_scope':'method_variants',
                'assessment':comments[cid]['reviewer_interpretation'][group],
                'judge_evidence':cleaned({'before':b['retained_evaluation'],'after':p['retained_evaluation']}),
                'provenance':selection_provenance(p['selection'])|{'condition':condition,'baseline_condition':b['condition'],
                    'quality_evidence_status':p['quality_evidence_status']}})
        out['methods'][groups[group]]['variants'].append({'id':condition,'label':name(condition),'cases':cases})
    for c in full['cases']:
        if c['kind']=='outcome_blind_shared_anchor':continue
        s=c['supplement'];cid=c['cell']['cell_id'];outputs={o['condition']:o for o in c['outputs']};b=outputs[s['baseline_condition']];p=outputs[s['condition']]
        out['contexts'][cid]=cleaned(c['context'])
        out['methods'][groups[s['method_group']]]['supplements'].append(pair(cid,b['retained_evaluation'],p['retained_evaluation'],s['baseline_condition'],s['condition'],comments[cid]['reviewer_interpretation'][s['method_group']],cid)|{'label':cid+' · '+s['category'].replace('_',' ')})


def load(path):return json.loads(Path(path).read_text())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--efg',type=Path,required=True);p.add_argument('--efg-review',type=Path,required=True)
    p.add_argument('--acd',type=Path);p.add_argument('--acd-annotations',type=Path)
    p.add_argument('--b-combinations',type=Path)
    p.add_argument('--panel',type=Path,default=Path('configs/qualitative_shared_panel_v1.json'))
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():raise FileExistsError('Use a new prepared artifact')
    if hashlib.sha256(args.panel.read_bytes()).hexdigest()!=PANEL_SHA:raise ValueError('Wrong panel bytes')
    panel=load(args.panel)
    out={'status':'prepared_pending_root_review','stage':'development_pilot','panel_sha256':PANEL_SHA,
        'anchors':[a|{'label':f"{a['family'].replace('_',' ')} · {a['item_id']} · layer {a['layer']}"} for a in panel['anchors']],
        'contexts':{},'original_readouts':{},'methods':{},'source_digests':{},
        'limits':['Illustrative development examples, not improvement rates.','Official verdicts remain separate from qualitative review.','Missing diagnostics and unjudged variants are not zero quality.']}
    add_efg(out,load(args.efg),load(args.efg_review))
    if load(args.efg_review)['original_artifact_sha256']!=hashlib.sha256(args.efg.read_bytes()).hexdigest():
        raise ValueError('Independent E/F/G receipt does not bind these source bytes')
    sources=[args.panel,args.efg,args.efg_review]
    if args.acd:
        if not args.acd_annotations:raise ValueError('Require the reviewed A/C/D annotations')
        annotation=load(args.acd_annotations)
        if annotation['full_evidence']['sha256']!=hashlib.sha256(args.acd.read_bytes()).hexdigest():
            raise ValueError('A/C/D annotation does not bind these source bytes')
        add_acd(out,load(args.acd),annotation);sources += [args.acd,args.acd_annotations]
    if args.b_combinations:
        add_b_combinations(out,load(args.b_combinations));sources.append(args.b_combinations)
    out['source_digests']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    if PRIVATE.search(json.dumps(out,ensure_ascii=False)):raise ValueError('Public payload still contains private infrastructure')
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),
        'bytes':args.output.stat().st_size,'methods':{k:len(v['variants']) for k,v in out['methods'].items()}}))


if __name__=='__main__':main()
