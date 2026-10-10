"""Attach reviewed DEV pilot examples, preserving original verdicts and texts."""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def attach(report,artifact,path):
    if artifact['status']!='complete_development_partial_grid' or artifact['manifest_sha256']!=report['provenance']['cohort_manifest_sha256']:
        raise ValueError('Require the same complete pilot cohort')
    for source in artifact['source_paths_and_hashes']:
        if sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Selection source changed')
    for method,families in artifact['families_by_condition'].items():
        root=Path(artifact['authoritative_condition_paths'][method])
        for family,values in families.items():
            for filename,key in [('results.json','results_sha256'),('project_contract.json','project_contract_sha256')]:
                if sha256((root/family/filename).read_bytes()).hexdigest()!=values[key]:raise ValueError('Judgment source changed')
    examples=[
        ('pooled_specificity_mean_then_prune_0.005 vs pooled_specificity_mean','hallucination','wrong_to_consistent',
         'hallucination|chat-lmsys-0026|L20|p00471',
         'Reported contradiction improvement retains flagged details',
         'Pruning retains formerly wrong spans, including mandatory RNAV routes, while the verdict becomes consistent with zero true and five unverifiable claims. This does not demonstrate removal of the alleged contradiction.'),
        ('pooled_specificity_mean vs best_n_specificity_mean','hallucination','wrong_to_consistent',
         'hallucination|chat-dailydialog-0027|L20|p00123',
         'Pooling retains a formerly flagged span',
         'The draft-a-packing-list span remains while the frozen verdict changes from wrong to consistent. Preserve the official score; the change is not independent verification of the surviving content.'),
        ('pooled_specificity_mean vs best_n_specificity_mean','multihop_mt','win',
         'multihop_mt|mhh-simula-norsk-regnesentral|L60|p00033',
         'A bridge hit can refer to the wrong kind of entity',
         'The pooled output says Simula Research Laboratory. The frozen bridge alias is bare Simula; a regex hit does not establish that the language, rather than the laboratory name, was recovered.')]
    curated=[]
    for comparison,family,kind,cid,title,interpretation in examples:
        pair=next(e for e in artifact['examples'] if e['comparison']==comparison)
        example=next(e for e in pair['family_examples'][family][kind] if e['cell_id']==cid)
        curated.append({'kind':title,'cell_id':cid,'baseline':example['baseline']['text'],
                        'selected':example['proposed']['text'],'interpretation':interpretation,
                        'evidence':f'Frozen {comparison} judgments; reviewed in docs/experiments/020-pooled-specificity.md. These deliberately selected cases are not prevalence estimates.',
                        'review_source':'doc020'})
    method=report['methods']['combinations']
    method['traces']=[e for e in method.get('traces',[]) if e.get('review_source')!='doc020']+curated
    method['findings']=list(dict.fromkeys(method.get('findings',[])+[
        'In this partial-grid pilot, pooling with specificity followed by pruning did not beat simpler specificity then pruning: role recovery tied at 12/72, while multi-hop was 6 versus 7, chain 0 versus 1, and contradictory assertions 39/71 versus 36/72. These are small, judge-sensitive DEV comparisons.',
        'Some apparent improvements retain previously flagged spans or count a bare bridge string inside a different entity name. Frozen benchmark scores remain unchanged; such hits do not establish full faithful recovery.']))
    method['limits']=list(dict.fromkeys(method.get('limits',[])+artifact['limitations']))
    report['provenance']['specificity_review']={'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest()}
    report['progress']['phase']='Full DEV selectors and E1 pruning complete; full-grid method judging in progress'
    report['full_development']['method_comparison_status']='Full DEV selected-method comparisons are still being judged. No full-grid selector gain is established in this report.'
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,default=Path('dashboard/report.json'))
    p.add_argument('--artifact',type=Path,default=Path('${OLENS_DATA_ROOT}/selections/specificity-pooling-pilot189-v1/paired-analysis-v1.json'));a=p.parse_args()
    report=attach(json.loads(a.report.read_text()),json.loads(a.artifact.read_text()),a.artifact)
    a.report.write_text(json.dumps(report,indent=2)+'\n')
