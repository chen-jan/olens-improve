"""Source-bound baseline examples and read-only paid-judge cost snapshot."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
from olens_improve.data import load_bank,item_id,paths


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--baseline',required=True);p.add_argument('--ledger',required=True);p.add_argument('--donor',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use allocated CPU resources')
    root=Path(a.root);sources={}
    def read(path,lines=False):
        path=Path(path);raw=path.read_bytes();sources[str(path)]=sha256(raw).hexdigest()
        return [json.loads(line) for line in raw.splitlines()] if lines else json.loads(raw)
    baseline=read(a.baseline,True);texts={(x['family'],x['item_id'],x['layer'],x['position']):{s['method']:s['text'] for s in x['selections']} for x in baseline}
    results={m:{f:read(root/f'{m}-n1'/f/'results.json') for f in ('hallucination','multihop_mt','chain_intermediates','role_bound_association')} for m in ('raw_n1','capped_n1')}
    def row(family,method,item,layer=None,pos=None):
        return next(x for x in results[method][family]['rows'] if x['id']==item and (layer is None or x['layer']==layer) and (pos is None or x['pos']==pos))
    cases=[]
    chain='chain-w2-d3p-0547';raw=row('chain_intermediates','raw_n1',chain);cap=row('chain_intermediates','capped_n1',chain)
    cases.append({'cell_id':f'chain_intermediates|{chain}|L52|p00070','family':'chain_intermediates','kind':'Judge ranking changes after capping','baseline':texts[('chain_intermediates',chain,52,70)]['raw_n1'],'selected':texts[('chain_intermediates',chain,52,70)]['capped_n1'],'evidence':f"Raw item pass {raw['pass']}; capped item pass {cap['pass']}. L52 named values {raw['named_by_layer']['52']} versus {cap['named_by_layer']['52']}; kinds {raw['kind_by_layer']['52']} versus {cap['kind_by_layer']['52']}.",'interpretation':'The correct intermediate 17 remains the first bullet in both texts. The changed top-named value diagnoses judge ranking/context sensitivity; it does not show that capping removed the correct number.'})
    item='chat-dailydialog-0035';raw=row('hallucination','raw_n1',item,60,56);cap=row('hallucination','capped_n1',item,60,56);t=texts[('hallucination',item,60,56)]
    if re.sub(r'\s+',' ',t['raw_n1']).strip()!=re.sub(r'\s+',' ',t['capped_n1']).strip():raise ValueError('Formatting-only example no longer matches')
    cases.append({'cell_id':f'hallucination|{item}|L60|p00056','family':'hallucination','kind':'Formatting-sensitive judge verdict','baseline':t['raw_n1'],'selected':t['capped_n1'],'evidence':f"Raw {raw['verdict'][0]['class']}, capped {cap['verdict'][0]['class']}; whitespace-normalized strings are identical. Frozen verdicts remain unchanged.",'interpretation':'This is evidence that the declared judge can change classification under formatting changes. It is not a verified correction to the benchmark verdict or a semantic gain.'})
    item='oa-boss-employee-envy-ba';mine=[r for r in results['raw_n1']['role_bound_association']['rows'] if r['id']==item];positive=row('role_bound_association','raw_n1',item,36,122);negative=row('role_bound_association','raw_n1',item,36,119)
    cases.append({'cell_id':f'role_bound_association|{item}|L36|p00122','family':'role_bound_association','kind':'Sparse passing sites and contextual role mapping','baseline':texts[('role_bound_association',item,36,119)]['raw_n1'],'selected':texts[('role_bound_association',item,36,122)]['raw_n1'],'evidence':f"Only {sum(bool(r['pass']) for r in mine)}/{len(mine)} raw sites pass, but the original ANY-grid item passes. Passing-site judge evidence: {positive['evidence']} Negative-site evidence: {negative['evidence']}",'interpretation':'This compares two existing sites, not two selector outputs at the same site. The role judge permits role descriptions and provides name/role mappings. Its closest-option mapping here merits contextual inspection; missing listed names alone is not a failure.'})
    item='mhh-borglum-son';raw=row('multihop_mt','raw_n1',item);t=texts[('multihop_mt',item,36,33)]
    cases.append({'cell_id':f'multihop_mt|{item}|L36|p00033','family':'multihop_mt','kind':'Credited bridge inside a conflicting relationship','baseline':t['raw_n1'],'selected':t['capped_n1'],'evidence':f"Bridge1 matched at L36; passing layers {raw['passing_layers']}. The bank credits Gutzon Borglum as the sculptor bridge and identifies Lincoln Borglum as the optional final target.",'interpretation':'The string match credits the bridge, while the output identifies Gutzon Borglum as the son and introduces Carl Gutzon Borglum. Bridge mention recovery does not validate the relationship or the rest of the explanation.'})
    banks={}
    for family,ident in [('chain_intermediates',chain),('role_bound_association','oa-boss-employee-envy-ba'),('multihop_mt','mhh-borglum-son')]:
        bank_path=paths(family)['bank'];sources[str(bank_path)]=sha256(bank_path.read_bytes()).hexdigest()
        banks[family]=next(x for x in load_bank(family) if item_id(x)==ident)
    db=sqlite3.connect('file:'+str(Path(a.ledger))+'?mode=ro',uri=True);db.execute('BEGIN');run_id='development-full-grid-baselines-v1'
    attempts=db.execute('SELECT attempt_id,status,actual,created_utc,updated_utc FROM attempts WHERE run_id=? ORDER BY attempt_id',(run_id,)).fetchall()
    eventrows=db.execute("SELECT e.attempt_id,e.details FROM events e JOIN attempts a USING(attempt_id) WHERE a.run_id=? AND e.kind='settled' ORDER BY e.attempt_id",(run_id,)).fetchall();db.commit();db.close()
    status=Counter(r[1] for r in attempts)
    if status.keys()!={'settled'}:raise ValueError('Baseline cost has unfinished attempts')
    events=[json.loads(r[1]) for r in eventrows]
    cost={'ledger_path':a.ledger,'run_id':run_id,'actual_usd':sum(r[2] for r in attempts)/1e9,'physical_attempts':len(attempts),'attempt_counts':dict(status),'input_tokens':sum(e['input_tokens'] for e in events),'output_tokens':sum(e['output_tokens'] for e in events),'cached_input_tokens':sum(e['cached_tokens'] for e in events),'attempt_snapshot_sha256':sha256(json.dumps(attempts).encode()).hexdigest(),'first_request_utc':min(r[3] for r in attempts),'last_settlement_utc':max(r[4] for r in attempts),'source_successful_response_spend_usd':sum(r['counts']['spend_usd'] for families in results.values() for r in families.values()),'scope':'Campaign benchmark judging; not selection/deployment cost. Ledger includes every charged physical attempt.'}
    donor=read(Path(a.donor)/'export.json');donor_path=Path(a.donor)/'selections.jsonl';donor_sha=sha256(donor_path.read_bytes()).hexdigest()
    if donor_sha!=donor['selection_sha256']:raise ValueError('Donor source bytes changed')
    sources[str(donor_path)]=donor_sha
    record={'scope':'complete original DEV baselines and isolated evaluation-only trace audit','generated_utc':datetime.now(timezone.utc).isoformat(),'new_api_calls':0,'new_gpu_calls':0,'cases':cases,'gold_diagnostic_only':banks,'judge_cost':cost,'donor_readiness':{k:v for k,v in donor.items() if k not in ['donor_target_multiplicities']},'donor_limits':'Pending judging. Target-group intervals are conditional on the fixed reused donor bank; they do not capture uncertainty over other donor-bank choices. No donor launch is authorized by this report.','source_sha256':sources}
    if any(sha256(Path(path).read_bytes()).hexdigest()!=expected for path,expected in sources.items()):raise ValueError('Source changed during review')
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'output':str(out),'cases':len(cases),'judge_cost':cost,'donor_cells':donor['cells'],'distinct_donors':donor['distinct_donors']}))

if __name__=='__main__':main()
