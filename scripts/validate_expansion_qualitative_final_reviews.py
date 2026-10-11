#!/usr/bin/env python3
"""Merge final human notes with index-derived counts and exact prior authority.

No inference, verdict changes or automatic prose truth judgments. Earlier notes
are retained verbatim. Terminal final-index preparation remains the CPU owner.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path

from validate_expansion_qualitative_reviews_v4 import blob, sha, require, validate_partition

KINDS=('capped_N1_pairs','actual_parent_pairs')

def read(path):return json.loads(Path(path).read_text())
def pairs(index):
    for part,units in index['partitions'].items():
        for i,u in enumerate(units):
            for k in KINDS:
                for j,p in enumerate(u[k]):yield part,i,k,j,u,p
def refs(index):
    result=[r for *_,p in pairs(index) for r in p['references']]
    result += [r for u in index.get('inherited_comparisons',[]) for r in u['pair']['references']]
    require(len(result)==len(set(map(blob,result))),'Duplicate expected official references')
    return result
def human_notes(note):
    return {k:v for k,v in note.items() if k not in ('context','comparisons','condition_case_references','references','source_pair','source_pair_sha256')}
def official(ref,kind):
    keys=('official_before','official_after') if kind=='capped_N1_pairs' else ('official_parent','official_proposed')
    return ref[keys[0]],ref[keys[1]]
def inherited_note(unit,reference,index,prior,authorities):
    """Every new reference needs a matching exact official pair, not just text."""
    pair=unit['pair'];context=index['contexts'][unit['context_ref']]
    for link in pair.get('prior_exact_text_context_review_links',[]):
        key=(link['partition'],link['prior_unit_index'],link['pair_kind'],link['prior_pair_index'])
        require(key in authorities,'Inherited review authority is not in the prior validated partitions')
        old,note,path,digest=authorities[key];old_unit=prior['partitions'][key[0]][key[1]]
        require(link['path']==str(path) and link['sha256']==digest,'Inherited review path/hash changed')
        require(link['pair_kind']==unit['pair_kind'],'Inherited comparison kind differs')
        require(unit['family']==old_unit['family'] and unit['cell_id']==old_unit['cell_id'],'Inherited source cell differs')
        require(context==prior['contexts'][old_unit['context_ref']],'Inherited full context differs')
        require(pair['before']['text']==old['before']['text'] and pair['after']['text']==old['after']['text'],'Inherited exact before/after text differs')
        if any(official(reference,unit['pair_kind'])==official(r,unit['pair_kind']) for r in old['references']):
            return human_notes(note),link
    raise ValueError('Inherited reference has no exact previously reviewed official pair')

def run(index_path,prior_index_path,prior_notes_path,prior_reviews,reviews):
    index,prior,old_notes=[read(p) for p in (index_path,prior_index_path,prior_notes_path)]
    index_sha,prior_sha=sha(index_path),sha(prior_index_path)
    pins={str(p):sha(p) for p in (index_path,prior_index_path,prior_notes_path)}
    require(index['manifest_sha256']==prior['manifest_sha256']==old_notes['manifest_sha256'],'Qualitative inventory differs')
    require(index['source_sha256'].get(str(prior_index_path))==prior_sha,'Final index lacks exact prior-index binding')
    require(old_notes['index_sha256']==prior_sha and old_notes['status']=='all_fresh_and_inherited_reviews_validated' and not old_notes['pending_partitions'],'Prior notes are not complete/bound to prior index')
    for source in (index,old_notes):
        for p,h in source['source_sha256'].items():
            require(sha(p)==h,'Pinned source changed: '+p);pins[p]=h
    prior_refs=refs(prior);require({blob(x['source_reference']) for x in old_notes['new_case_notes']}==set(map(blob,prior_refs)) and len(old_notes['new_case_notes'])==len(prior_refs),'Prior audited reference bundle is incomplete or duplicated')
    require(set(prior_reviews)==set(prior['partitions']),'All prior review partitions required')
    authorities={}
    for part,path in prior_reviews.items():
        digest=sha(path);require(index['source_sha256'].get(str(path))==digest,'Prior review missing exact final-index pin');pins[str(path)]=digest
        review=read(path);require('complete' in review['status'],'Prior review status incomplete')
        for i,k,j,p,n in validate_partition(review,prior,prior_sha,part):authorities[(part,i,k,j)]=(p,n,path,digest)
        pins.update(review['source_sha256'])
    # Preserve the actual historical-count authority instead of assuming 426.
    historical=old_notes['historical_reviewed_pair_count']
    history_paths=[p for p in old_notes['source_sha256'] if p.endswith('expanded-qualitative-v3-new-case-index-v2.json')]
    if history_paths:
        require(len(history_paths)==1,'Ambiguous historical audit index')
        require(sum(1 for _ in pairs(read(history_paths[0])))==historical,'Historical audited pair count disagrees with pinned index')
    expected=refs(index);bundle=[];counts={};missing=[];metadata={}
    require(set(reviews)<=set(index['partitions']),'Foreign review partition')
    for part in index['partitions']:
        path=reviews.get(part)
        if path is None or not Path(path).exists():missing.append(part);continue
        review=read(path);require('complete' in review['status'],'Final review status incomplete');pins[str(path)]=sha(path)
        covered=validate_partition(review,index,index_sha,part);counts[part]=len(covered)
        pins.update(review['source_sha256'])
        metadata[part]={k:v for k,v in review.items() if k not in ('units','unit_reviews','observations')}
        for i,k,j,p,n in covered:
            u=index['partitions'][part][i]
            for ref in p['references']:bundle.append({'review_partition':part,'review_path':str(path),'review_sha256':pins[str(path)],'unit_index':i,'pair_kind':k,'pair_index':j,'context':index['contexts'][u['context_ref']],'source_reference':ref,'human_review':human_notes(n),'inheritance':None})
    inherited=0
    for u in index.get('inherited_comparisons',[]):
        for ref in u['pair']['references']:
            notes,link=inherited_note(u,ref,index,prior,authorities)
            bundle.append({'review_partition':'inherited','review_path':link['path'],'review_sha256':link['sha256'],'unit_index':link['prior_unit_index'],'pair_kind':u['pair_kind'],'context':index['contexts'][u['context_ref']],'source_reference':ref,'human_review':notes,'inheritance':deepcopy(u['pair']['prior_exact_text_context_review_links'])});inherited+=1
    ids=list(map(lambda z:blob(z['source_reference']),bundle));require(len(ids)==len(set(ids)),'Merged reference duplicated')
    if not missing:require(set(ids)==set(map(blob,expected)),'Final merged reference coverage incomplete')
    for p,h in pins.items():require(sha(p)==h,'Source changed during validation: '+p)
    return {'status':'all_fresh_and_inherited_reviews_validated' if not missing else 'partial_review_coverage_validated','manifest_sha256':index['manifest_sha256'],'analysis_sha256':index['analysis_sha256'],'index_sha256':index_sha,'source_sha256':pins,'implementation_sha256':sha(__file__),'historical_reviewed_pair_count':historical,'prior_audited_reference_count':len(prior_refs),'prior_audited_bundle_verbatim':deepcopy(old_notes),'partition_comparison_counts':counts,'required_partition_comparison_counts':{part:sum(len(u[k]) for u in units for k in KINDS) for part,units in index['partitions'].items()},'pending_partitions':missing,'inherited_reference_count':inherited,'required_new_case_reference_count':len(expected),'reviewed_new_case_reference_count':len(bundle),'eligible_for_complete_final_public_notes':not missing,'review_metadata':metadata,'new_case_notes':bundle,'limits':['Counts derive from exact index objects; no fixed330/426 expected counts.','Prior audited notes remain verbatim; official outcomes, full context and new whole-grid metadata remain unchanged.','Only exact text/context plus official pair equality inherit notes. Human mechanism hypotheses are not established by structural validation.','No automatic prose truth judgments, inference, verdict rewrite or publication.']}

def mapping(values):
    result={}
    for value in values:
        k,v=value.split('=',1);require(k not in result,'Duplicate partition argument');result[k]=Path(v)
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index',type=Path,required=True);p.add_argument('--prior-index',type=Path,required=True);p.add_argument('--prior-notes',type=Path,required=True)
    p.add_argument('--prior-review',action='append',required=True);p.add_argument('--review',action='append',default=[]);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-state',type=Path,default=Path(__file__).resolve().parents[1]/'.state/expanded-final-native-v1.service.json')
    a=p.parse_args();require(os.getenv('SLURM_JOB_ID') is not None,'Run full source-bound merge on an existing CPU allocation');require(not a.output.exists(),'Use a new immutable notes artifact')
    native_state_sha=sha(a.native_state);native=read(a.native_state);index=read(a.index)
    require(native['status']=='complete_pending_root_review' and native['scientific_inputs_validated_complete'] is True,'Final native gate is not scientifically terminal')
    require(sha(native['output'])==native['output_sha256']==index['analysis_sha256'],'Final notes do not bind the exact terminal native source')
    value=run(a.index,a.prior_index,a.prior_notes,mapping(a.prior_review),mapping(a.review))
    require(sha(a.native_state)==native_state_sha and sha(native['output'])==native['output_sha256'],'Terminal native authority changed during merge')
    value['source_sha256'][str(a.native_state)]=native_state_sha
    value['source_sha256'][native['output']]=native['output_sha256'];a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as stream:stream.write(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'output':str(a.output),'sha256':sha(a.output),'status':value['status'],'required_references':value['required_new_case_reference_count'],'reviewed_references':value['reviewed_new_case_reference_count'],'pending_partitions':value['pending_partitions']}))

if __name__=='__main__':main()
