"""Immutable exact-text projection of frozen selector exports; no model calls."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.data import canonical
from olens_improve.stage_io import validate_export_stage


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def export(args):
    if len(args.source)!=len(args.source_sha256):raise ValueError('One expected SHA per source required')
    if args.output.exists() or args.provenance.exists():raise FileExistsError('Use a new immutable export')
    manifest_body=args.manifest.read_bytes()
    fresh_path=getattr(args,'fresh_manifest',None);gate_path=getattr(args,'gate',None)
    fresh_body=fresh_path.read_bytes() if fresh_path else None
    gate_body=gate_path.read_bytes() if gate_path else None
    stage,cells,captures=validate_export_stage(manifest_body,fresh_body,gate_body)
    conditions=json.loads(args.conditions.read_text());ordered=[(r['method'],r['n']) for r in conditions];wanted=set(ordered)
    if len(wanted)!=len(ordered):raise ValueError('Duplicate condition')
    choices={cid:{} for cid in cells};activations={};parents=[];duplicates=Counter()
    for source,expected in zip(args.source,args.source_sha256):
        actual=sha(source)
        if actual!=expected:raise ValueError('Parent source SHA differs')
        index=len(parents);parents.append({'path':str(source),'sha256':actual});seen=set()
        with source.open() as stream:
            for line in stream:
                if not line.endswith('\n'):raise ValueError('Uncommitted source line')
                row=json.loads(line);cid=row['cell_id']
                if cid not in cells or cid in seen:raise ValueError('Foreign or duplicate source cell')
                seen.add(cid);cell=cells[cid]
                if any(row[k]!=cell[k] for k in ('family','item_id','layer','position','split')):raise ValueError('Cell metadata differs')
                if not row.get('activation_sha256'):raise ValueError('Missing target activation provenance')
                if captures and row['activation_sha256']!=captures[cid]['activation_sha256']:
                    raise ValueError('Source activation differs from analysis-authorized fresh capture')
                if cid in activations and activations[cid]!=row['activation_sha256']:raise ValueError('Source target activation differs')
                activations[cid]=row['activation_sha256']
                for selection in row['selections']:
                    key=(selection['method'],selection['n'])
                    if key not in wanted:continue
                    reduced={k:selection[k] for k in ('method','n','text','token_count','bullet_count')}
                    if not isinstance(reduced['text'],str):raise ValueError('Nontext output')
                    if key!=('raw_n1',1) and (reduced['token_count']>256 or reduced['bullet_count']>4):raise ValueError('Frozen output cap differs')
                    reduced.update({'reason':selection.get('reason'),'fits_scope':selection.get('fits_scope'),
                        'parent_source_index':index})
                    if key in choices[cid]:
                        previous=choices[cid][key]
                        if any(previous[k]!=reduced[k] for k in ('method','n','text','token_count','bullet_count')):
                            raise ValueError('Conflicting duplicated parent condition')
                        duplicates[key]+=1
                    else:choices[cid][key]=reduced
        if seen!=set(cells):raise ValueError('Incomplete parent source cohort')
    if any(set(v)!=wanted for v in choices.values()):raise ValueError('Missing declared condition/cell')
    temporary=args.output.with_suffix(args.output.suffix+'.tmp')
    with temporary.open('w') as stream:
        for cid,cell in cells.items():
            row={k:cell[k] for k in ('cell_id','family','item_id','layer','position','split')}
            row.update({'activation_sha256':activations[cid],'parent_sources':parents,'selections':[choices[cid][key] for key in ordered]})
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    temporary.replace(args.output)
    # Read the completed projection again and check every exposed text and count.
    verified=set();actual_conditions=Counter()
    with args.output.open() as stream:
        for line in stream:
            row=json.loads(line);cid=row['cell_id']
            if cid in verified:raise ValueError('Duplicate exported cell')
            verified.add(cid)
            if [(s['method'],s['n']) for s in row['selections']]!=ordered:raise ValueError('Dispatch order changed')
            for s in row['selections']:
                key=(s['method'],s['n'])
                if canonical(s)!=canonical(choices[cid][key]):raise ValueError('Export output/count identity changed')
                actual_conditions[key]+=1
    if verified!=set(cells):raise ValueError('Export cohort differs')
    result={'status':'complete_immutable_exact_text_projection','created_utc':datetime.now(timezone.utc).isoformat(),
        'manifest_sha256':sha(args.manifest),'dispatch_conditions_sha256':sha(args.conditions),
        'parent_sources':parents,'output_path':str(args.output),'output_sha256':sha(args.output),
        'output_bytes':args.output.stat().st_size,'cells':len(cells),'conditions':conditions,
        'condition_cell_counts':{m+f'-n{n}':count for (m,n),count in actual_conditions.items()},
        'identical_duplicate_parent_counts':{m+f'-n{n}':count for (m,n),count in duplicates.items()},
        'rules':['Exact final text/token/bullet counts copied without re-tokenization or rewriting.',
            'First source is authoritative when a later combination source repeats identical parent text/counts.',
            'Cell identity and complete condition coverage verified; full fits/traces remain in immutable parents.',
            'No judge labels or validation/test outputs used.']}
    if gate_body is not None:
        result.update({'split':stage,'fresh_manifest_sha256':hashlib.sha256(fresh_body).hexdigest(),
                       'coordinator_gate_sha256':hashlib.sha256(gate_body).hexdigest()})
    if stage!='development':
        result['rules'][-1]='No judge labels used; stage outputs projected only after exact analysis authorization.'
    args.provenance.write_text(json.dumps(result,indent=2)+'\n')
    args.output.chmod(0o444);args.provenance.chmod(0o444)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,action='append',required=True)
    p.add_argument('--source-sha256',action='append',required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--conditions',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--provenance',type=Path,required=True)
    p.add_argument('--fresh-manifest',type=Path);p.add_argument('--gate',type=Path)
    export(p.parse_args())
