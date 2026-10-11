#!/usr/bin/env python3
"""Validate source-bound human reviews; collect notes without judging source prose."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
KINDS=('capped_N1_pairs','actual_parent_pairs')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def blob(x,compact=True):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,**({'separators':(',',':')}if compact else{})).encode()).hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
def binding(review,index,index_sha):
 bound=review.get('index_sha256',review.get('source_index_sha256',review.get('source_index',{}).get('sha256')))
 require(bound==index_sha,'Review index binding mismatch')
 require(review['manifest_sha256']==index['manifest_sha256'] and review['analysis_sha256']==index['analysis_sha256'],'Review cohort binding mismatch')
 require(all(review['source_sha256'].get(p)==h for p,h in index['source_sha256'].items()),'Review source pin map mismatch')
 for p,h in review['source_sha256'].items():
  if p not in index['source_sha256']:
   authority=review.get('parser_calibration',{}).get('approved_parser',{})
   require((h==index_sha or (p==authority.get('path') and h==authority.get('sha256'))) and sha(p)==h,'Unapproved extra review pin')
def validate_partition(review,index,index_sha,partition):
 binding(review,index,index_sha);require(review['partition']==partition,'Wrong review partition')
 units=index['partitions'][partition];out=[]
 if 'unit_reviews' in review:
  reviewed=review['unit_reviews'];require(len(reviewed)==len(units),'Unit review coverage mismatch')
  for i,(u,v)in enumerate(zip(units,reviewed)):
   require(v['unit_index']==i and v['family']==u['family'] and v['cell_id']==u['cell_id'],'Unit identity mismatch')
   require(v['exact_unit_sha256']in (blob(u),blob(u,False)),'Reviewed unit source mismatch')
   refs=[r for k in KINDS for p in u[k]for r in p['references']]
   require(v['condition_case_references']==refs,'Unit official reference mismatch')
   for k in KINDS:
    for j,p in enumerate(u[k]):out.append((i,k,j,p,v))
 elif 'observations'in review:
  seen=set()
  for v in review['observations']:
   i,k,j=v['review_unit_index'],v['pair_kind'],v['pair_index'];key=(i,k,j);require(key not in seen,'Duplicate reviewed pair');seen.add(key)
   u=units[i];p=u[k][j];require(v['family']==u['family']and v['cell_id']==u['cell_id'],'Pair identity mismatch')
   for end in ('before','after'):require(v[end+'_text_sha256']==hashlib.sha256(p[end]['text'].encode()).hexdigest(),'Reviewed text mismatch')
   require([r['official_reference_sha256']for r in v['references']]==[blob(r)for r in p['references']],'Pair official evidence pin mismatch')
   out.append((i,k,j,p,v))
  expected={(i,k,j)for i,u in enumerate(units)for k in KINDS for j,p in enumerate(u[k])};require(seen==expected,'Pair coverage incomplete')
 else:
  reviewed=review['units'];require(len(reviewed)==len(units),'Unit comparison coverage mismatch')
  for i,(u,v)in enumerate(zip(units,reviewed)):
   require(v['family']==u['family']and v['cell_id']==u['cell_id'],'Comparison unit identity mismatch')
   expected=[(k,j,p)for k in KINDS for j,p in enumerate(u[k])];require(len(v['comparisons'])==len(expected),'Unit pair count mismatch')
   for c,(k,j,p)in zip(v['comparisons'],expected):
    require(c['reference_kind']==k and c['source_pair_sha256']in (blob(p),blob(p,False)),'Comparison source pair mismatch')
    if 'source_pair'in c:require(c['source_pair']==p,'Full comparison payload mismatch')
    out.append((i,k,j,p,v))
 require(len(out)==index['partition_comparison_counts'][partition],'Partition comparison count mismatch')
 return out

def run(index_path,review_paths):
 index=json.loads(Path(index_path).read_text());index_sha=sha(index_path);pins={str(index_path):index_sha};initial={}
 for p,h in index['source_sha256'].items():require(sha(p)==h,'Pinned source changed: '+p);initial[p]=h
 pins.update(initial)
 prior_path=next(p for p in initial if p.endswith('expanded-qualitative-v3-new-case-index-v2.json'))
 prior=json.loads(Path(prior_path).read_text());prior_sha=initial[prior_path]
 prior_files={'root':'docs/reviews/expanded-qualitative-delta-root-v1.json','agent_1':'docs/reviews/expanded-qualitative-v3-agent1-v1.json','agent_2':'docs/reviews/expanded-qualitative-delta-agent2-v1.json','agent_3':'docs/reviews/expanded-qualitative-delta-agent3-v1.json'}
 prior_pairs={};prior_notes={}
 for part,path in prior_files.items():
  require(path in pins,'Prior review missing pin');review=json.loads(Path(path).read_text())
  for i,k,j,p,n in validate_partition(review,prior,prior_sha,part):prior_pairs[(part,i,k,j)]=p;prior_notes[(part,i,k,j)]=n
 require(len(prior_pairs)==426,'Historical 426-pair review proof incomplete')
 bundle=[];counts={};missing=[];review_metadata={}
 def human_notes(n):return {k:v for k,v in n.items()if k not in ('context','comparisons','condition_case_references','references','source_pair','source_pair_sha256')}
 for part in index['partitions']:
  path=review_paths.get(part)
  if path is None or not Path(path).exists():missing.append(part);continue
  review=json.loads(Path(path).read_text());pins[str(path)]=sha(path);covered=validate_partition(review,index,index_sha,part);counts[part]=len(covered)
  review_metadata[part]={k:v for k,v in review.items()if k not in ('units','unit_reviews','observations')}
  authority=review.get('parser_calibration',{}).get('approved_parser')
  if authority:require(sha(authority['path'])==authority['sha256'],'Parser authority changed');pins[authority['path']]=authority['sha256']
  for i,k,j,p,n in covered:
   u=index['partitions'][part][i]
   for ref in p['references']:bundle.append({'review_partition':part,'review_path':str(path),'review_sha256':pins[str(path)],'unit_index':i,'pair_kind':k,'pair_index':j,'context':index['contexts'][u['context_ref']],'source_reference':ref,'human_review':human_notes(n),'inheritance':None})
 inherited=0
 for u in index['inherited_comparisons']:
  p=u['pair'];links=p['prior_exact_text_context_review_links'];require(bool(links),'Inherited pair lacks review authority')
  link=links[0];key=(link['partition'],link['prior_unit_index'],link['pair_kind'],link['prior_pair_index']);old=prior_pairs[key]
  pu=prior['partitions'][key[0]][key[1]]
  require(pins[link['path']]==link['sha256'],'Inherited review authority changed')
  require(index['contexts'][u['context_ref']]==prior['contexts'][pu['context_ref']],'Inherited context differs')
  require(p['before']==old['before']and p['after']==old['after'],'Inherited official pair differs')
  for ref in p['references']:
   bundle.append({'review_partition':'inherited','review_path':link['path'],'review_sha256':link['sha256'],'unit_index':key[1],'pair_kind':u['pair_kind'],'context':index['contexts'][u['context_ref']],'source_reference':ref,'human_review':human_notes(prior_notes[key]),'inheritance':links});inherited+=1
 require(inherited==29,'Inherited reference count mismatch')
 identities=[blob(z['source_reference'])for z in bundle];require(len(identities)==len(set(identities)),'Reference doublecount')
 expected_refs=[r for units in index['partitions'].values()for u in units for k in KINDS for p in u[k]for r in p['references']]+[r for u in index['inherited_comparisons']for r in u['pair']['references']]
 require(len(expected_refs)==330 and len(set(map(blob,expected_refs)))==330,'Expected330-ref scope changed')
 if not missing:require(set(identities)==set(map(blob,expected_refs)),'Complete merger lacks exact330-ref coverage')
 for p,h in pins.items():require(sha(p)==h,'Source changed during validation: '+p)
 return {'status':'all_fresh_and_inherited_reviews_validated'if not missing else'partial_review_coverage_validated','index_sha256':index_sha,'manifest_sha256':index['manifest_sha256'],'analysis_sha256':index['analysis_sha256'],'source_sha256':pins,'historical_reviewed_pair_count':426,'partition_comparison_counts':counts,'pending_partitions':missing,'inherited_reference_count':inherited,'reviewed_new_case_reference_count':len(bundle),'required_new_case_reference_count':330,'eligible_for_complete330_ref_public_notes':not missing,'review_metadata':review_metadata,'new_case_notes':bundle,'limits':['Read-only structural/provenance validation of human review records; no automated prose truth judgments.','Official outcomes, discrepancies and whole-grid witnesses remain unchanged in each complete reference record.','Old1476 public examples remain untouched; this additive notes bundle authorizes no publication and partial coverage must not be presented as complete.']}
def main():
 a=argparse.ArgumentParser();a.add_argument('--index',type=Path,default=Path('docs/reviews/expanded-qualitative-v4-new-case-index-v1.json'));a.add_argument('--review',action='append',default=[]);a.add_argument('--output',type=Path,required=True);x=a.parse_args();paths={}
 for s in x.review:
  k,v=s.split('=',1);require(k not in paths,'Duplicate review partition argument');paths[k]=v
 require(not x.output.exists(),'Immutable output already exists');result=run(x.index,paths);x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'output':str(x.output),'sha256':sha(x.output),'status':result['status'],'references':result['reviewed_new_case_reference_count'],'pairs':result['partition_comparison_counts'],'pending':result['pending_partitions']}))
if __name__=='__main__':main()
