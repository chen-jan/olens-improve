#!/usr/bin/env python3
"""Wait for the finite terminal source menu; seal once; run unchanged native analysis."""
import argparse,fcntl,hashlib,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GROUPS=('cached-v2','combinations-v2/merged','semantic-semantic-v1','semantic-medium-v1','likelihood-v1','editing-round1-v1','editing-round2-v1','editing-pruning-v1')
FAMILIES=('hallucination','multihop_mt','chain_intermediates','role_bound_association')
MANIFEST_SHA='753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8'
ACTIVE=('cached_selector_full_bank','scheduled_full_bank')
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
def atomic(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(temp,p)
def pins_unchanged(pins):
 for p,h in pins.items():require(sha(p)==h,'Pinned source changed: '+p)
def index_descriptors(records,active,families=FAMILIES):
 index={}
 for path,d in records:
  require('_queue_'not in str(path),'Queue alias is not canonical')
  require(d.get('ready')is True and d['inventory_sha256']==MANIFEST_SHA,'Unsealed descriptor')
  family=d['family'];require(family in families,'Foreign family')
  for c in d['conditions']:
   require(type(c['n'])is int and isinstance(c['method'],str),'Malformed method/N')
   key=f"{c['method']}-n{c['n']}";require(key in active,'Undeclared active condition '+key)
   pair=(key,family);require(pair not in index,'Duplicate condition-family descriptor '+str(pair));index[pair]=(path,d)
 require(set(index)=={(c,f)for c in active for f in families},'Finite condition-family menu incomplete')
 return index

def main():
 p=argparse.ArgumentParser();p.add_argument('--artifact-root',type=Path,default=Path('${OLENS_DATA_ROOT}/expansion-v1'));p.add_argument('--state',type=Path,default=ROOT/'.state/expanded-final-native-v1.service.json');p.add_argument('--snapshot',type=Path,default=ROOT/'.state/expanded-final-native-ready-v1');p.add_argument('--output',type=Path);p.add_argument('--poll-seconds',type=int,default=60);p.add_argument('--max-watch-seconds',type=int,default=30000);p.add_argument('--preflight',action='store_true');a=p.parse_args();os.chdir(ROOT)
 if not a.preflight:require(os.getenv('SLURM_JOB_ID')=='25536417','Only authorized owned CPU allocation25536417 may run this gate')
 a.output=a.output or a.artifact_root/'analysis/final-v1.json'
 lock=a.state.with_suffix('.lock');lock.parent.mkdir(parents=True,exist_ok=True);handle=lock.open('a');fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
 inventory_path=ROOT/'configs/expansion_manifest_v1.json';require(sha(inventory_path)==MANIFEST_SHA,'Manifest seal changed');inventory=load(inventory_path);active={c['condition_id']:c for c in inventory['conditions']if c['status']in ACTIVE};require(len(active)==70,'Expected exactly70 active conditions')
 static=[inventory_path,ROOT/'configs/expansion_analysis_v1.json',ROOT/'configs/expansion_runtime_authority_v1.json',ROOT/'configs/splits_pilot_shared_v2.json',Path(inventory['fresh_manifest']['path']),Path(__file__),ROOT/'scripts/analyze_expansion.py',ROOT/'scripts/verify_expansion_judge_contracts.py',ROOT/'scripts/expanded_cpu_cached.py',ROOT/'src/olens_improve/reporting.py',ROOT/'src/olens_improve/expanded_statistics.py']
 static_pins={str(x):sha(x)for x in static};require(static_pins[inventory['fresh_manifest']['path']]==inventory['fresh_manifest']['sha256'],'Fresh source changed')
 descriptor_paths=[a.artifact_root/'selections'/group/(family+'.ready.json')for group in GROUPS for family in FAMILIES]
 def terminal_paths(condition,family):
  base=a.artifact_root/'judgments'/condition
  return [base/(family+'.summary.json'),base/family/'results.json',base/family/'project_contract.json',base/(family+'.readouts.jsonl')]
 state={'status':'preflight'if a.preflight else'waiting_for_terminal_sources','started_utc':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'slurm_job_id':os.getenv('SLURM_JOB_ID'),'manifest_sha256':MANIFEST_SHA,'active_condition_count':70,'intended_family_units':280,'canonical_descriptor_count':32,'snapshot':str(a.snapshot),'output':str(a.output),'static_source_sha256':static_pins,'inference_calls':0,'new_allocations':0,'scientific_inputs_validated_complete':False}
 started=time.monotonic()
 while True:
  state['updated_utc']=datetime.now(timezone.utc).isoformat();state['terminal_files_present_by_family']={f:sum(all(p.exists()for p in terminal_paths(c,f))for c in active)for f in FAMILIES};state['canonical_ready_files_present']=sum(p.exists()for p in descriptor_paths);state['elapsed_seconds']=round(time.monotonic()-started,2)
  if a.preflight:print(json.dumps(state));return
  if a.output.exists():
   receipt_path=a.snapshot/'receipt.json';require(receipt_path.exists(),'Existing final output lacks sealed source receipt');receipt=load(receipt_path);pins_unchanged(receipt['source_sha256']);body=load(a.output);require(body['status']=='complete_exploratory'and len(body['complete_condition_families'])==280 and not body['missing_condition_families'],'Existing output is not a complete final source analysis');state.update(status='complete_pending_root_review',scientific_inputs_validated_complete=True,output_sha256=sha(a.output));atomic(a.state,state);return
  if all(n==70 for n in state['terminal_files_present_by_family'].values())and state['canonical_ready_files_present']==32:break
  atomic(a.state,state)
  if time.monotonic()-started>=a.max_watch_seconds:state['status']='waiting_timeout_no_snapshot';atomic(a.state,state);return
  time.sleep(a.poll_seconds)
 state['status']='validating_all_terminal_sources';atomic(a.state,state);pins_unchanged(static_pins)
 sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
 from analyze_expansion import runtime_authority
 from verify_expansion_judge_contracts import verify_judge_contract
 from olens_improve.reporting import family_counts,original_grid_pairs
 from expanded_cpu_cached import committed_lines
 runtime_hashes,runtime_pins=runtime_authority(ROOT/'configs/expansion_runtime_authority_v1.json');descriptor_bytes={p:p.read_bytes()for p in descriptor_paths};records=[(p,json.loads(descriptor_bytes[p]))for p in descriptor_paths];index=index_descriptors(records,active);pins={**static_pins,**runtime_pins};cells=load(inventory['fresh_manifest']['path'])['cells'];expected={f:sum(c['family']==f for c in cells)for f in FAMILIES}
 for path,d in records:
  pins[str(path)]=hashlib.sha256(descriptor_bytes[path]).hexdigest()
  for field,h in [('manifest','manifest_sha256'),('selections','selection_sha256')]:require(sha(d[field])==d[h],'Descriptor data changed');pins[d[field]]=d[h]
 for (condition,family),(path,d)in index.items():
  summary,result,contract,readouts=terminal_paths(condition,family)
  for p in (summary,result,contract,readouts):pins[str(p)]=sha(p)
  summary_body,result_body,contract_body=load(summary),load(result),load(contract)
  verify_judge_contract(family=family,method=active[condition]['method'],n=active[condition]['n'],expected_cells=expected[family],inventory_sha256=MANIFEST_SHA,descriptor=d,summary=summary_body,result=result_body,contract=contract_body,approved_runtime_source_hashes=runtime_hashes)
  family_cells=[c for c in cells if c['family']==family]
  metrics,coverage=family_counts(family,family_cells,list(committed_lines(readouts)),result_body)
  require(coverage['missing_stage1']==0 and coverage['missing_stage2']==0,'Native family judgment coverage is incomplete')
  original_grid_pairs(family,metrics,result_body)
 pins_unchanged(pins)
 receipt={'status':'sealed_all280_terminal_inputs','manifest_sha256':MANIFEST_SHA,'source_sha256':pins,'descriptor_count':32,'condition_family_count':280,'canonical_relative_paths':[str(p.relative_to(a.artifact_root/'selections'))for p in descriptor_paths],'original_runtime_authority_source_count':len(runtime_hashes),'sealed_utc':datetime.now(timezone.utc).isoformat()}
 if a.snapshot.exists():
  existing=load(a.snapshot/'receipt.json');require(existing['source_sha256']==pins,'Existing sealed snapshot differs');require(existing['status']==receipt['status'],'Existing snapshot is unsealed')
 else:
  temp=a.snapshot.with_name(a.snapshot.name+'.preparing');require(not temp.exists(),'Prior incomplete snapshot requires explicit review');temp.mkdir(parents=True)
  for path,d in records:
   dest=temp/path.relative_to(a.artifact_root/'selections');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes());require(sha(dest)==pins[str(path)],'Descriptor changed during source copy')
  pins_unchanged(pins);atomic(temp/'receipt.json',receipt);os.rename(temp,a.snapshot)
 receipt=load(a.snapshot/'receipt.json');pins_unchanged(receipt['source_sha256']);require(not a.output.exists(),'Final output appeared before launch')
 attempt=a.snapshot/'analysis-attempt.json';require(not attempt.exists(),'Final analysis already attempted; preserve failed run for root review')
 cmd=[sys.executable,str(ROOT/'scripts/analyze_expansion.py'),'--inventory-sha256',MANIFEST_SHA,'--judgments',str(a.artifact_root/'judgments'),'--runtime-authority',str(ROOT/'configs/expansion_runtime_authority_v1.json'),'--output',str(a.output)]
 for group in GROUPS:cmd+=['--ready-directory',str(a.snapshot/group)]
 atomic(attempt,{'status':'attempt_started_once','started_utc':datetime.now(timezone.utc).isoformat(),'command':cmd,'receipt_sha256':sha(a.snapshot/'receipt.json')});state.update(status='extracting_final_native',scientific_inputs_validated_complete=True,receipt_sha256=sha(a.snapshot/'receipt.json'),command=cmd);atomic(a.state,state)
 with a.state.with_suffix('.analyzer.log').open('x')as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=False)
 require(result.returncode==0,'Final analyzer failed; no automatic rerun');pins_unchanged(receipt['source_sha256']);body=load(a.output);require(body['status']=='complete_exploratory'and len(body['complete_condition_families'])==280 and not body['missing_condition_families'],'Analyzer produced incomplete scientific source coverage')
 state.update(status='complete_pending_root_review',output_sha256=sha(a.output),analyzer_exit_code=0,uncertainty={name:{'status':c['status'],'rows':len(c['rows']),'available_comparisons':len(c['comparisons']),'declared_contrasts':c['declared_contrasts'],'comparison_family_complete':c['comparison_family_complete'],'effective_non_degenerate_contrasts':c['effective_non_degenerate_contrasts'],'joint_interval_contrasts':c['joint_interval_contrasts'],'missing_comparisons':len(c['missing_comparisons']),'undefined_absolute_metrics':sum(r['metric']['value']is None for r in c['rows']),'degenerate_comparisons':sum(r.get('bootstrap_standard_error')==0 for r in c['comparisons']),'absolute_warning_records':[{'condition':r['condition'],'family':r['family'],'warnings':r['metric']['warnings'],'defined_draws':r['metric']['defined_draws']}for r in c['rows']if r['metric'].get('warnings')],'comparison_warning_records':[{'condition':r['condition'],'reference':r['reference'],'family':r['family'],'warning':r['warning'],'defined_draws':r['defined_draws']}for r in c['comparisons']if r.get('warning')]}for name,c in body['cohorts'].items()},limits=['Source completion is not certainty; undefined and degenerate intervals/warnings remain exactly in native artifact.','No delivery before root reviews final numbers.']);atomic(a.state,state);print(json.dumps({'status':state['status'],'output':str(a.output),'sha256':state['output_sha256']}))
if __name__=='__main__':
 try:main()
 except BlockingIOError:
  print('An existing final-native gate holds the lock; no duplicate work started.')
 except Exception as e:
  print(str(e),file=sys.stderr)
  state_path=Path(sys.argv[sys.argv.index('--state')+1])if '--state'in sys.argv else ROOT/'.state/expanded-final-native-v1.service.json'
  if state_path.exists():
   body=load(state_path)
   if body.get('pid')==os.getpid():body.update(status='failed_pending_root_review',error=str(e),updated_utc=datetime.now(timezone.utc).isoformat());atomic(state_path,body)
  raise
