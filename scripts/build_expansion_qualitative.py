"""Retain frozen anchors and deterministic endpoint-selected evidence; no inference."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.data import item_id, load_bank, paths
from analyze_consensus_conditions import read_arm
from analyze_signed_menu import enrich_traces
from build_expansion_parent_qualitative import propagate_evidence
from expanded_cpu_cached import atomic, sha

BASE='capped_n1-n1'

def choose_cases(baseline,proposed,cells,family):
    """Lexicographic first cases, whole-question recovery with a real witness."""
    buckets=defaultdict(list);outcomes={}
    if family=='hallucination':
        for cid in sorted(proposed):
            b,p=baseline[cid],proposed[cid]
            category=('win' if b['class']=='hallucinated' and p['class']=='consistent' else
                'regression' if b['class']=='consistent' and p['class']=='hallucinated' else
                'changed_no_endpoint_change' if b['text']!=p['text'] and b['class']==p['class'] else None)
            if category:buckets[category].append(cid)
            outcomes[cid]={'unit':'original_readout_site_class','baseline_class':b['class'],'proposed_class':p['class']}
    else:
        by_item=defaultdict(list)
        for cid in sorted(proposed):by_item[cells[cid]['item_id']].append(cid)
        for item,ids in sorted(by_item.items()):
            before=any(baseline[cid]['pass'] for cid in ids);after=any(proposed[cid]['pass'] for cid in ids)
            changed=[cid for cid in ids if baseline[cid]['text']!=proposed[cid]['text']]
            category='win' if after and not before else 'regression' if before and not after else 'changed_no_endpoint_change' if changed else None
            if category:
                eligible=([cid for cid in ids if proposed[cid]['pass']] if category=='win' else
                    [cid for cid in ids if baseline[cid]['pass']] if category=='regression' else changed)
                cid=eligible[0];buckets[category].append(cid)
                outcomes[cid]={'unit':'whole_original_question_grid','item_id':item,'baseline_item_pass':before,
                    'proposed_item_pass':after,'baseline_passing_cells':sum(baseline[k]['pass'] for k in ids),
                    'proposed_passing_cells':sum(proposed[k]['pass'] for k in ids),'grid_cells':len(ids),
                    'witness_rule':'first passing proposed site' if category=='win' else
                        'first passing baseline site' if category=='regression' else 'first text-changed site'}
    return [(category,ids[0],outcomes[ids[0]]) for category,ids in buckets.items()],{k:len(v) for k,v in buckets.items()}

def main():
    p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--analysis-sha256',required=True);p.add_argument('--judgments',type=Path,required=True)
    p.add_argument('--report',type=Path,default=Path('dashboard/report.json'));p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU required')
    if a.output.exists():raise FileExistsError('Use a new immutable evidence pack')
    if sha(a.analysis)!=a.analysis_sha256:raise ValueError('Native source analysis changed')
    analysis=json.loads(a.analysis.read_text());pins=dict(analysis['source_sha256']);pins[str(a.analysis)]=a.analysis_sha256
    # Verify the source-checked analysis before loading any official outcomes.
    if any(sha(path)!=value for path,value in pins.items()):raise ValueError('Pinned analysis evidence changed')
    inventory_path=Path('configs/expansion_manifest_v1.json')
    if sha(inventory_path)!=analysis['manifest_sha256']:raise ValueError('Expansion seal differs')
    inventory=json.loads(inventory_path.read_text());fresh_path=Path(inventory['fresh_manifest']['path'])
    cells={c['cell_id']:c for c in json.loads(fresh_path.read_text())['cells']}
    report_sha=sha(a.report);q=json.loads(a.report.read_text())['qualitative_reviews']
    panel_path=Path('configs/qualitative_shared_panel_v1.json');panel=json.loads(panel_path.read_text())
    if sha(panel_path)!=q['panel_sha256'] or len(q['anchors'])!=8 or [r['cell_id'] for r in q['anchors']]!=[r['cell_id'] for r in panel['anchors']]:raise ValueError('Historical eight-anchor panel changed')
    pins[str(a.report)]=report_sha;pins[str(panel_path)]=sha(panel_path)
    anchors={r['cell_id']:r for r in q['anchors']};completed={(r['condition'],r['family']) for r in analysis['complete_condition_families']}
    conditions=[r['condition_id'] for r in inventory['conditions'] if any(r['condition_id']==c for c,f in completed)]
    # Original row text/verdicts remain untouched; no qualitative judgment is generated.
    original={};baseline={};traces=[];case_meta={};missing=[]
    for family in inventory['families']:
        own={cid:c for cid,c in cells.items() if c['family']==family}
        if (BASE,family) not in completed or ('raw_n1-n1',family) not in completed:
            missing.append({'family':family,'reason':'original_raw_or_capped_judgment_missing'});continue
        baseline[family]=read_arm(a.judgments/BASE,family,own)
        raw=read_arm(a.judgments/'raw_n1-n1',family,own)
        for cid in anchors:
            if cells[cid]['family']!=family:continue
            if baseline[family][cid]['text']!=q['original_readouts'][cid]['capped']['text'] or raw[cid]['text']!=q['original_readouts'][cid]['raw']['text']:raise ValueError('Frozen anchor raw/capped text changed')
            original[cid]={'raw':q['original_readouts'][cid]['raw'],'capped':q['original_readouts'][cid]['capped']}
    for condition in conditions:
        trace={'condition':condition,'baseline_condition':BASE,'families':{}}
        for family in inventory['families']:
            if (condition,family) not in completed or family not in baseline:continue
            own={cid:c for cid,c in cells.items() if c['family']==family};proposed=read_arm(a.judgments/condition,family,own)
            selected,counts=choose_cases(baseline[family],proposed,own,family)
            fixed=[cid for cid in anchors if own.get(cid)]
            examples={'fixed_anchor':[],'outcome_selected':[]}
            for category,cid,outcome in [('fixed_anchor',cid,None) for cid in fixed]+selected:
                record={'cell_id':cid,'item_id':cells[cid]['item_id'],'layer':cells[cid]['layer'],'position':cells[cid]['position'],
                    'baseline':dict(baseline[family][cid]),'proposed':dict(proposed[cid])}
                kind='fixed_anchor' if category=='fixed_anchor' else 'outcome_selected'
                examples[kind].append(record);case_meta[condition,family,cid,kind]={'category':category,'endpoint_evidence':outcome}
            trace['families'][family]={'examples':examples,'available_category_counts':counts}
        traces.append(trace)
    measurement={'conditions':[{'condition':condition,'condition_root':str(a.judgments)} for condition in conditions]}
    pins.update(enrich_traces(traces,measurement,cells))
    # The historical enricher visits one object per deduplicated identity. Copy
    # its exact retained evidence to every occurrence of that same identity.
    propagate_evidence(traces)
    banks={family:{item_id(row):row for row in load_bank(family)} for family in inventory['families']}
    pins.update({str(paths(family)['bank']):sha(paths(family)['bank']) for family in inventory['families']})
    contexts={};grouped={}
    for trace in traces:
        condition=trace['condition'];families={}
        for family,details in trace['families'].items():
            family_cases={}
            for kind,records in details['examples'].items():
                prepared=[]
                for r in records:
                    cid=r['cell_id'];meta=case_meta[condition,family,cid,kind];cell=cells[cid]
                    contexts[cid]={'source_bank_item':banks[family][cell['item_id']],
                        'historical_anchor_context':q['contexts'].get(cid),
                        'evaluation_context':r['proposed'].get('evaluation_context'),
                        'evaluation_only':True}
                    prepared.append(r|meta|{'cell':{k:cell[k] for k in ('cell_id','family','item_id','group_id','layer','position','split','activation_sha256')},
                        'context_ref':cid,'baseline_condition':BASE,'condition':condition,
                        'text_changed':r['baseline']['text']!=r['proposed']['text'],
                        'review_status':'unreviewed_source_evidence','selection_policy':'historical_outcome_blind_panel' if kind=='fixed_anchor' else 'deterministic_outcome_selected_supplement'})
                family_cases[kind]=prepared
            families[family]=family_cases|{'available_category_counts':details['available_category_counts']}
        grouped[condition]={'families':families}
    if any(sha(path)!=value for path,value in pins.items()):raise ValueError('Evidence source changed while extracting')
    payload={'status':'prepared_pending_independent_review','updated_utc':datetime.now(timezone.utc).isoformat(),
        'manifest_sha256':analysis['manifest_sha256'],'analysis_sha256':a.analysis_sha256,'panel_sha256':q['panel_sha256'],
        'anchors':q['anchors'],'contexts':contexts,'original_readouts':original,'conditions':grouped,
        'reviewer_partitions':{f'partition_{i+1}':conditions[i::3] for i in range(3)},
        'missing':missing,'source_sha256':pins,'implementation_sha256':{str(Path(__file__)):sha(__file__),
            'scripts/analyze_signed_menu.py':sha('scripts/analyze_signed_menu.py'),
            'scripts/build_expansion_parent_qualitative.py':sha('scripts/build_expansion_parent_qualitative.py')},
        'case_selection_contract':{'order':'lexicographic item ID then cell ID','max_per_category_family_condition':1,
            'recovery_endpoint':'ANY passing complete site across original question grid; show passing witness site',
            'hall_win':'hallucinated to consistent at same site','hall_regression':'consistent to hallucinated at same site',
            'changed_no_endpoint_change':'changed text, unchanged whole-question recovery or same hallucination class'},
        'limits':['Outcome-blind anchors remain separate from outcome-selected cases.','Selected cases do not estimate prevalence.',
            'Official judge evidence is retained without reviewer endorsement or changed scores.',
            'Gold/context appears only in this post-selection review artifact; no paid calls or new inference.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);atomic(a.output,payload)
    print(json.dumps({'output':str(a.output),'sha256':sha(a.output),'conditions':len(grouped),'families':sum(len(c['families']) for c in grouped.values()),
        'fixed_anchor_cases':sum(len(f['fixed_anchor']) for c in grouped.values() for f in c['families'].values()),
        'selected_cases':sum(len(f['outcome_selected']) for c in grouped.values() for f in c['families'].values())}))

if __name__=='__main__':main()
