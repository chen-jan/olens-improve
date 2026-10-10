"""Paired development-only donor controls; no generation, inference or judge changes."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.evaluation import paired_group_interval


def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    manifest = load(args.manifest)
    groups = {r['item_id']: r['group_id'] for r in manifest['cells']}
    if any(r['split'] != 'development' for r in manifest['cells']):raise ValueError('DEV only')
    sites = {(r['family'],r['item_id'],r['layer'],r['position']):r['cell_id'] for r in manifest['cells']}
    summaries={};provenance={}
    for family in sorted({r['family'] for r in manifest['cells']}):
        arms={};details={}
        for arm,root in [('target',args.baseline),('donor',args.donor)]:
            condition=load(root/'condition.json')
            if condition['manifest_sha256'] != sha(args.manifest):raise ValueError('Manifest mismatch')
            contract=load(root/family/'project_contract.json');results=load(root/family/'results.json')
            rows={};counts=Counter()
            if family=='hallucination':
                stage=contract['hallucination_stage2']
                if stage['stage1_api_or_missing_readouts'] or stage['stage2_api_or_missing_readouts']:raise ValueError('Missing hall stages')
                for r in results['rows']:
                    if len(r['verdict'])!=1:raise ValueError('One output per cell required')
                    label=r['verdict'][0]['class'];cid=sites[(family,r['id'],r['layer'],r['pos'])]
                    rows[cid]={'item_id':r['id'],'class':label,'numerator':int(label=='hallucinated'),'denominator':int(label in ('hallucinated','off_topic','consistent'))};counts[label]+=1
            else:
                coverage=contract['cell_diagnostic']
                if coverage['api_or_missing_unjudged_cells']:raise ValueError('Missing recovery cells')
                for r in coverage['rows']:
                    cid=sites[(family,r['item_id'],r['layer'],r['position'])]
                    rows[cid]={'item_id':r['item_id'],'pass':r['pass'],'numerator':int(r['pass']),'denominator':1}
            arms[arm]=rows
            details[arm]={'upstream_complete_preserved':results['complete'],'class_counts':dict(counts),
                'expected_cells':contract['manifest_expected_cells'],'produced_cells':contract['manifest_produced_cells'],
                'missing_cells':contract['manifest_missing_cells'],'results_sha256':sha(root/family/'results.json'),
                'project_contract_sha256':sha(root/family/'project_contract.json')}
        if arms['target'].keys()!=arms['donor'].keys():raise ValueError('Unpaired cells')
        contributions={}
        for arm,rows in arms.items():
            by_item=defaultdict(lambda:[0,0])
            for row in rows.values():
                by_item[row['item_id']][0]+=row['numerator'];by_item[row['item_id']][1]+=row['denominator']
            contributions[arm]=dict(by_item)
        comparison=paired_group_interval(contributions['target'],contributions['donor'],groups)
        comparison['direction']='donor minus target'
        info={'cell_comparison':comparison,'coverage_and_classes':details,'items':len(contributions['target']),
            'independent_target_groups':len({groups[k] for k in contributions['target']})}
        if family!='hallucination':
            any_item={arm:{item:(int(any(row['pass'] for row in rows.values() if row['item_id']==item)),1)
                for item in contributions[arm]} for arm,rows in arms.items()}
            info['any_cell_item_comparison']=paired_group_interval(any_item['target'],any_item['donor'],groups)
            info['any_cell_item_comparison']['direction']='donor minus target'
            info['any_cell_item_counts']={arm:sum(v[0] for v in x.values()) for arm,x in any_item.items()}
        else:
            info['assertion_share']={arm:sum(row['denominator'] for row in rows.values())/len(rows) for arm,rows in arms.items()}
        summaries[family]=info
    result={'status':'complete_project_development_grid','manifest_sha256':sha(args.manifest),
        'baseline_condition_sha256':sha(args.baseline/'condition.json'),'donor_condition_sha256':sha(args.donor/'condition.json'),
        'families':summaries,'limitations':['These are fixed target/donor mapping comparisons, not activation truth.',
            'Donor reuse couples targets: target-group bootstrap is conditional on this mapping and does not fully resample donor-source uncertainty.',
            'Pinned upstream complete flags remain false for the selected development subset.',
            'Recovery criteria do not verify additional emitted facts.']}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--donor',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())
