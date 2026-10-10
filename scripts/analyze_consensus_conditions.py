"""Fixed pilot consensus comparisons, including missingness/empty-output distinctions."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.evaluation import paired_group_interval


def load(p):return json.loads(p.read_text())
def lines(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def read_arm(root,family,cells):
    contract=load(root/family/'project_contract.json');results=load(root/family/'results.json')
    sites={(r['item_id'],r['layer'],r['position']):r['cell_id'] for r in cells.values() if r['family']==family}
    texts={sites[(r['id'],r['layer'],r['pos'])]:r['samples'][0] for r in lines(root/f'{family}.readouts.jsonl')}
    if set(texts)!=set(sites.values()):raise ValueError('Readout cohort differs')
    out={cid:{'text':text,'empty':not text.strip(),'pass':False,'class':'empty' if not text.strip() else None,'evidence':None} for cid,text in texts.items()}
    if family=='hallucination':
        stage=contract['hallucination_stage2']
        if stage['stage1_api_or_missing_readouts'] or stage['stage2_api_or_missing_readouts']:raise ValueError('Missing hall verdicts')
        for r in results['rows']:
            cid=sites[(r['id'],r['layer'],r['pos'])];v=r['verdict'][0]
            out[cid].update({'class':v['class'],'evidence':v})
    else:
        if contract['cell_diagnostic']['api_or_missing_unjudged_cells']:raise ValueError('Missing recovery verdicts')
        for r in contract['cell_diagnostic']['rows']:
            cid=sites[(r['item_id'],r['layer'],r['position'])];out[cid]['pass']=r['pass']
        # Missing outcome rows are legitimate abstentions only when text is empty.
        represented={sites[(r['item_id'],r['layer'],r['position'])] for r in contract['cell_diagnostic']['rows']}
        if any(not out[cid]['empty'] for cid in set(out)-represented):raise ValueError('Unreported nonempty recovery cell')
    return out


def aggregate(rows,family):
    values=defaultdict(lambda:[0,0])
    for cid,row in rows.items():
        item=cid.split('|')[1]
        if family=='hallucination':num=int(row['class']=='hallucinated');den=int(row['class'] in ('hallucinated','consistent','off_topic'))
        else:num=int(row['pass']);den=1
        values[item][0]+=num;values[item][1]+=den
    return dict(values)


def run(args):
    config=load(args.queue);manifest=load(args.manifest);cells={r['cell_id']:r for r in manifest['cells']}
    groups={r['item_id']:r['group_id'] for r in cells.values()};results={};details=[]
    for entry in config['queue']:
        if entry['name'] not in ('B-v5-none','B-medium-confirmation'):continue
        source={r['cell_id']:r for r in lines(Path(entry['selections']))}
        for cond in load(Path(entry['conditions'])):
            name=cond['method'];root=Path(entry['output'])/f"{name}-n{cond['n']}";out={};traces={}
            for family in sorted(manifest['families']):
                baseline=read_arm(args.baseline,family,cells);proposed=read_arm(root,family,cells)
                basevals=aggregate(baseline,family);propvals=aggregate(proposed,family)
                stats=paired_group_interval(basevals,propvals,groups)
                tokens=[next(s for s in source[cid]['selections'] if s['method']==name)['token_count'] for cid in proposed]
                bullets=[next(s for s in source[cid]['selections'] if s['method']==name)['bullet_count'] for cid in proposed]
                summary={'paired_vs_A16':stats,'intended_cells':len(proposed),'empty_outputs':sum(r['empty'] for r in proposed.values()),
                    'mean_tokens_all_intended':statistics.mean(tokens),'mean_bullets_all_intended':statistics.mean(bullets),
                    'source_sha256':sha(Path(entry['selections'])),'results_sha256':sha(root/family/'results.json')}
                if family=='hallucination':
                    classes=Counter(r['class'] for r in proposed.values());summary['classes']=dict(classes)
                    summary['assertion_share']=sum(v[1] for v in propvals.values())/len(proposed)
                    summary['consistent_share']=classes['consistent']/len(proposed)
                else:summary['passed_cells']=sum(r['pass'] for r in proposed.values())
                out[family]=summary
                buckets=defaultdict(list)
                for cid in sorted(proposed):
                    b,p=baseline[cid],proposed[cid]
                    if family=='hallucination':
                        category=('deleted_wrong' if b['class']=='hallucinated' and p['empty'] else
                            'wrong_to_consistent' if b['class']=='hallucinated' and p['class']=='consistent' else
                            'consistent_to_wrong' if b['class']=='consistent' and p['class']=='hallucinated' else
                            'unchanged' if b['class']==p['class'] else 'other')
                    else:category='win' if p['pass'] and not b['pass'] else 'regression' if b['pass'] and not p['pass'] else 'unchanged'
                    buckets[category].append({'cell_id':cid,'baseline':b,'proposed':p})
                traces[family]={k:(random.Random(20261010).sample(v,min(2,len(v))) if k=='unchanged' else v[:2]) for k,v in buckets.items()}
            results[name]=out;details.append({'method':name,'family_examples':traces})
    artifact={'status':'complete_development_partial_grid','manifest_sha256':sha(args.manifest),'families_by_condition':results,'examples':details,
        'limits':['Whole-bullet equivalence, not atomic-claim consensus.','Medium has46unverified requested pairs; benchmark verdicts complete.',
            'No dedicated compatibility-phase checks; abstain on unchecked pairs.','Groupbootstrap uses2chain and4role groups.',
            'A reduction by deletion/offtopic is not truthful recovery.','Targeted helper audits are not populationerrorrates.']}
    args.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',type=Path,default=Path('configs/evaluation_diagnostic_queue_v1.json'))
    p.add_argument('--manifest',type=Path,default=Path('configs/splits_pilot_shared_v2.json'))
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);run(p.parse_args())
