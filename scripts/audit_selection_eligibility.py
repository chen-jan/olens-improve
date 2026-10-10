"""Read-only parser/AR eligibility and fixed-denominator audit of selector events."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from olens_improve.selection import Sample


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def run(args):
    manifest=json.loads(args.manifest.read_text());cells={r['cell_id']:r for r in manifest['cells']}
    if any(r['split']!='development' for r in cells.values()):raise ValueError('DEV only')
    expected=Counter(c['family'] for c in cells.values());seen=set();prefix=defaultdict(Counter);arms=defaultdict(Counter)
    reasons=defaultdict(Counter);flag_counts=defaultdict(Counter);invalid_examples=[];n1_comparison=defaultdict(Counter)
    source_contracts=set();prefixes=(1,2,4,8,16,32)
    for path in args.events:
        with path.open() as stream:
            for line in stream:
                if not line.endswith('\n'):raise ValueError('Uncommitted event tail')
                row=json.loads(line);cid=row['cell_id']
                if cid in seen or cid not in cells:raise ValueError('Duplicate/foreign cell')
                cell=cells[cid]
                if any(row[k]!=cell[k] for k in ('family','item_id','layer','position','split')):raise ValueError('Frozen cell metadata differs')
                family=row['family'];seen.add(cid);source_contracts.add(row['config_sha256'])
                flags={int(k):tuple(v) for k,v in row['parser_flags_by_sample'].items()}
                if set(flags)!=set(range(32)):raise ValueError('Sample indices not0..31')
                invalid={int(k):v for k,v in row['invalid_AR_atoms_by_sample'].items()}
                if not set(invalid).issubset(flags):raise ValueError('Foreign invalid-AR index')
                parsing={i:Sample('audit',i,(),flags[i]).parsing_uncertain for i in flags}
                for i,values in invalid.items():
                    if any(v.get('status')!='empty_after_cleanup' or v.get('cache_key') is not None for v in values):raise ValueError('Unclassified AR invalidity')
                for n in prefixes:
                    p=prefix[(family,n)];p['completed_cells']+=1;p['candidate_sample_records']+=n
                    parse_indices=[i for i in range(n) if parsing[i]];ar_indices=[i for i in range(n) if invalid.get(i)]
                    both=set(parse_indices)&set(ar_indices);ar_only=set(ar_indices)-set(parse_indices)
                    p['parsing_ineligible_samples']+=len(parse_indices);p['samples_with_invalid_AR_atoms']+=len(ar_indices)
                    p['both_parsing_and_invalid_AR']+=len(both);p['invalid_AR_additional_exclusions_after_parsing']+=len(ar_only)
                    p['complete_AR_eligible_samples']+=n-len(set(parse_indices)|set(ar_indices))
                    p['cells_with_parsing_exclusion']+=bool(parse_indices);p['cells_with_invalid_AR_exclusion']+=bool(ar_indices)
                    p['cells_without_parser_eligible_sample']+=len(parse_indices)==n
                    p['cells_without_AR_eligible_complete_sample']+=len(set(parse_indices)|set(ar_indices))==n
                    p['invalid_retained_AR_atoms']+=sum(len(invalid.get(i,())) for i in range(n))
                    for i in range(n):flag_counts[(family,n)].update(flags[i])
                selections={(s['method'],s['n']):s for s in row['selections']}
                if len(selections)!=len(row['selections']):raise ValueError('Duplicate arm')
                parent=selections[('capped_n1',1)];a1=selections[('best_n_exact',1)]
                comparison=n1_comparison[family];comparison['completed_cells']+=1
                comparison['N1_parsing_ineligible']+=parsing[0];comparison['N1_invalid_AR']+=bool(invalid.get(0))
                comparison['capped_N1_empty_outputs']+=not bool(parent['text'].strip())
                comparison['A1_empty_outputs']+=not bool(a1['text'].strip())
                comparison['A1_vs_capped_N1_changed_text']+=a1['text']!=parent['text']
                comparison['A1_empty_with_nonempty_capped_N1_due_parsing']+=not a1['text'].strip() and bool(parent['text'].strip()) and parsing[0]
                comparison['A1_empty_with_nonempty_capped_N1_due_invalid_AR_only']+=not a1['text'].strip() and bool(parent['text'].strip()) and not parsing[0] and bool(invalid.get(0))
                for (method,n),selection in selections.items():
                    key=(family,method,n);counts=arms[key];counts['completed_cells']+=1
                    counts['empty_outputs']+=not bool(selection['text'].strip())
                    counts['null_fits']+=selection['fits'] is None
                    scope=selection['fits_scope'];counts['null_fits_unmodified_raw_reference']+=scope=='unavailable_for_unmodified_raw_text'
                    counts['unscoreable_selected_output_fits']+=scope=='unavailable_AR_empty_after_cleanup'
                    noop=selection['reason']=='unavailable_parent_AR';counts['unavailable_parent_noops']+=noop
                    if noop:
                        if n!=1 or selection['text']!=parent['text'] or selection['phrase_ids']!=parent['phrase_ids']:
                            raise ValueError('Unavailable N1-parent branch changed output')
                        counts['noops_verified_identical_to_capped_N1']+=1
                    reasons[key][selection['reason']]+=1
                if invalid:
                    invalid_examples.append({'cell_id':cid,'invalid_sample_indices':sorted(invalid),
                        'invalid_atom_count':sum(len(v) for v in invalid.values()),'N1_invalid_AR':bool(invalid.get(0)),
                        'N1_parser_flags':list(flags[0]),'A1_reason':a1['reason']})
    missing=sorted(set(cells)-seen)
    if missing and not args.allow_partial:raise ValueError(f'Incomplete frozen cohort: {len(missing)} cells')
    result={'status':'complete_development_eligibility_audit' if not missing else 'partial_development_eligibility_audit',
        'checked_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':sha(args.manifest),
        'source_paths_and_hashes':[{'path':str(p),'sha256':sha(p)} for p in args.events],
        'selector_config_hashes':sorted(source_contracts),'expected_cells_by_family':dict(expected),
        'completed_cells':len(seen),'missing_cell_ids':missing,
        'prefixes_by_family':{family:{str(n):dict(prefix[(family,n)])|{'expected_cells':expected[family],
            'expected_candidate_sample_records':expected[family]*n,'parser_flag_occurrences':dict(flag_counts[(family,n)])}
            for n in prefixes} for family in sorted(expected)},
        'arms_by_family':{family:{method+f'-n{n}':dict(counts)|{'expected_cells':expected[family],
            'reason_counts':dict(reasons[(family,method,n)])} for (f,method,n),counts in sorted(arms.items()) if f==family}
            for family in sorted(expected)},
        'A1_vs_capped_N1_eligibility':{f:dict(n1_comparison[f]) for f in sorted(expected)},
        'invalid_AR_cells':invalid_examples,
        'limitations':['Fixed intended cell denominators are preserved; absent events are missing, never abstentions.',
            'Invalid AR counts refer to retained capped bullets with no cleaned scorer tokens, not false claims.',
            'AR-only excludes additional complete samples after parsing; pooling may reuse their remaining valid bullets.',
            'Random complete samples obey parsing/caps but may retain an unscoreable AR atom; A/E require complete AR scoreability.',
            'Raw reference null fits are expected by design; they are separate from invalid-AR null fits.',
            'A1 parser/AR abstentions versus capped N1 cannot be attributed to improved semantic scoring.',
            'No judge labels, outputs from validation/test, or automatic winner selection are used.']}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','completed_cells','expected_cells_by_family','A1_vs_capped_N1_eligibility')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--events',type=Path,action='append',required=True)
    parser.add_argument('--manifest',type=Path,default=Path('configs/development-full-grid-v2.json'))
    parser.add_argument('--allow-partial',action='store_true');parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
