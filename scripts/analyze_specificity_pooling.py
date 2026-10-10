"""Paired, development-only specificity/pooling audit; no model or API calls."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from analyze_consensus_conditions import read_arm, aggregate, load, sha
from olens_improve.evaluation import paired_group_interval


def run(args):
    manifest=load(args.manifest);cells={r['cell_id']:r for r in manifest['cells']}
    if any(r['split']!='development' for r in cells.values()):raise ValueError('DEV only')
    groups={r['item_id']:r['group_id'] for r in cells.values()}
    root=args.judgments
    specifications=[
        ('raw_n1',1,'judgments-standard-repair'),('capped_n1',1,'judgments-standard-repair'),
        ('best_n_exact',32,'judgments-standard-repair'),
        ('pooled_greedy_swap',32,'judgments-standard-repair'),
        ('best_n_specificity_mean',32,'judgments-standard-repair'),
        ('best_n_specificity_mean_then_prune_0.005',32,'judgments-combinations'),
        ('pooled_specificity_mean',32,'judgments-specificity-pooling'),
        ('pooled_specificity_mean_then_prune_0.005',32,'judgments-specificity-pooling'),
        ('pooled_specificity_mean_random_delete_matched_0.005',32,'judgments-specificity-pooling'),
        ('best_n_specificity_mean_abstain_nonpositive',32,'judgments-specificity-abstention')]
    source={}
    for path in args.sources:
        with path.open() as stream:
            for line in stream:
                row=json.loads(line)
                for choice in row['selections']:
                    key=(choice['method'],choice['n'],row['cell_id'])
                    reduced={k:choice.get(k) for k in ('text','token_count','bullet_count','specificity_objective','mean_control_fve','fits','trace','phrase_ids')}
                    if key in source and source[key]['text']!=reduced['text']:raise ValueError('Conflicting source outputs')
                    source[key]=reduced
    arms={};summaries={};paths={}
    for method,n,directory in specifications:
        path=root/directory/f'{method}-n{n}';paths[method]=path
        condition=load(path/'condition.json')
        if condition['manifest_sha256']!=sha(args.manifest):raise ValueError('Manifest mismatch')
        arms[method]={};summaries[method]={}
        for family in sorted(manifest['families']):
            rows=read_arm(path,family,cells);arms[method][family]=rows
            result=load(path/family/'results.json')
            if family!='hallucination':
                for cid,row in rows.items():
                    cell=cells[cid]
                    evidence=next((r for r in result['rows'] if r.get('id')==cell['item_id'] and
                        (family!='role_bound_association' or (r['layer'],r['pos'])==(cell['layer'],cell['position']))),None)
                    if evidence is not None:
                        if family=='chain_intermediates':
                            row['evidence']={k:evidence[k] for k in ('intermediates','answer','start')}
                            row['evidence'].update({k:evidence[k].get(str(cell['layer'])) for k in ('named_by_layer','kind_by_layer','basis_by_layer')})
                        elif family=='multihop_mt':
                            row['evidence']={'roles':evidence['roles'],'optional_roles':evidence['optional_roles'],
                                'this_layer':evidence['layers'].get(str(cell['layer']))}
                        else:row['evidence']=evidence
            selections=[source[(method,n,cid)] for cid in rows]
            if any(s['text']!=rows[cid]['text'] for cid,s in zip(rows,selections)):raise ValueError('Judged/source text differs')
            info={'intended_cells':len(rows),'empty_outputs':sum(r['empty'] for r in rows.values()),
                'mean_tokens':statistics.mean(s['token_count'] for s in selections),
                'mean_bullets':statistics.mean(s['bullet_count'] for s in selections),
                'results_sha256':sha(path/family/'results.json'),
                'project_contract_sha256':sha(path/family/'project_contract.json')}
            if family=='hallucination':
                counts=Counter(r['class'] for r in rows.values());den=sum(counts[c] for c in ('hallucinated','consistent','off_topic'))
                info.update({'classes':dict(counts),'wrong_over_asserting':counts['hallucinated']/den if den else None,
                    'assertion_share':den/len(rows),'consistent_share':counts['consistent']/len(rows),
                    'secondary_wrong_over_wrong_plus_consistent':counts['hallucinated']/(counts['hallucinated']+counts['consistent']) if counts['hallucinated']+counts['consistent'] else None,
                    'stage2_claim_counts':{k:v for k,v in result['numbers']['extras'].items() if k.startswith('n_claims_') or k in ('n_readouts_claims_judged','n_cells_claims_unjudged','n_unverified_claim_quotes')}})
            else:info['passed_cells']=sum(r['pass'] for r in rows.values())
            summaries[method][family]=info
    comparisons={};examples=[]
    pairs=[('best_n_specificity_mean','pooled_specificity_mean'),
        ('pooled_greedy_swap','pooled_specificity_mean'),
        ('pooled_specificity_mean','pooled_specificity_mean_then_prune_0.005'),
        ('pooled_specificity_mean_random_delete_matched_0.005','pooled_specificity_mean_then_prune_0.005'),
        ('best_n_specificity_mean_then_prune_0.005','pooled_specificity_mean_then_prune_0.005'),
        ('best_n_specificity_mean','best_n_specificity_mean_abstain_nonpositive')]
    for baseline,proposed in pairs:
        label=proposed+' vs '+baseline;comparisons[label]={};family_examples={}
        for family in sorted(manifest['families']):
            b=arms[baseline][family];p=arms[proposed][family]
            comparison=paired_group_interval(aggregate(b,family),aggregate(p,family),groups)
            comparisons[label][family]=comparison
            buckets=defaultdict(list)
            for cid in sorted(p):
                left,right=b[cid],p[cid]
                if family=='hallucination':
                    category=('wrong_to_consistent' if left['class']=='hallucinated' and right['class']=='consistent' else
                        'consistent_to_wrong' if left['class']=='consistent' and right['class']=='hallucinated' else
                        'deleted_wrong' if left['class']=='hallucinated' and right['empty'] else
                        'unchanged' if left['class']==right['class'] else 'other')
                else:category='win' if right['pass'] and not left['pass'] else 'regression' if left['pass'] and not right['pass'] else 'unchanged'
                buckets[category].append({'cell_id':cid,'baseline':left,'proposed':right,
                    'source_evidence':{baseline:source[(baseline,1 if baseline in ('raw_n1','capped_n1') else 32,cid)],
                        proposed:source[(proposed,32,cid)]}})
            family_examples[family]={k:(random.Random(20261010).sample(v,min(3,len(v))) if k=='unchanged' else v[:3]) for k,v in buckets.items()}
            comparisons[label][family]['transition_counts']={k:len(v) for k,v in buckets.items()}
        examples.append({'comparison':label,'family_examples':family_examples})
    artifact={'status':'complete_development_partial_grid','manifest_sha256':sha(args.manifest),
        'source_paths_and_hashes':[{'path':str(p),'sha256':sha(p)} for p in args.sources],
        'authoritative_condition_paths':{m:str(p) for m,p in paths.items()},
        'families_by_condition':summaries,'paired_comparisons':comparisons,'examples':examples,
        'limitations':['Partial original read grids; no heldout outputs inspected.',
            'Whole related-source groups resampled; chain only2groups and role4groups.',
            'Recovery instrument passes do not verify every emitted claim.',
            'Wrong-rate reductions through deletion/offtopic are not sufficient evidence of useful recovery.',
            'Random deletion matches bullet count, not exact token length.',
            'Stage2 false counts are verified span counts, not a uniform atomic-claim denominator.',
            'Q<=0 is an operational abstention rule with numerical sensitivity, not a falsehood test.']}
    args.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'families_by_condition':summaries,'paired_comparisons':comparisons},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=Path('configs/splits_pilot_shared_v2.json'))
    parser.add_argument('--judgments',type=Path,default=Path('${OLENS_DATA_ROOT}/runs/development-shared-pilot-v2'))
    parser.add_argument('--sources',type=Path,action='append',required=True);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
