"""Prepare an unreviewed final presentation candidate from terminal reviewed inputs.

Never judges prose, selects winners, computes statistics, or authorizes a build.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

PRIOR_SHA = 'c9a5d4eaaf376a6b56bd0a9a6ce858ab7e0667638ff1c06a3d539efefa115b84'
DRAFT_SHA = 'd1889a8c31c5422b5805577cf00e8df9b353e81af9ac84a79a72a5c9bb17b2f7'
SEAL = '753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8'
TITLES = {'hallucination':'Transcript contradictions', 'multihop_mt':'Hidden intermediate names',
          'chain_intermediates':'Intermediate numbers', 'role_bound_association':'Who did what'}
CATEGORIES = {'fixed_anchor':'Fixed example', 'win':'Recorded improvement', 'regression':'Recorded regression',
              'changed_no_endpoint_change':'Changed text, same endpoint'}

def require(value, message):
    if not value: raise ValueError(message)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda: stream.read(1048576), b''): h.update(b)
    return h.hexdigest()

def blob(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

def key(condition, item, reference=None):
    return condition, item['family'], item['kind'], item['cell_id'], item.get('reference',reference)

def resolve(condition, item, sources):
    pack = sources[item['source_sha256']]
    matches = [c for c in pack['conditions'][condition]['families'][item['family']][item['kind']]
               if c['cell_id'] == item['cell_id']]
    require(len(matches) == 1, 'Ambiguous or absent source case')
    case = matches[0]; reference = item.get('reference',case.get('baseline_condition'))
    if 'parents' in case:
        if reference in case['parents']:
            parent = case['parents'][reference]
            require(parent['status'] == 'complete', 'Incomplete actual parent')
            before, endpoint = parent['output'], parent['endpoint_evidence']
        else:
            require(reference == case['original_baseline_condition'], 'Missing actual parent reference')
            before, endpoint = case['original_baseline'], case.get('endpoint_evidence')
    else:
        require(reference == case['baseline_condition'], 'Capped reference differs')
        before, endpoint = case['baseline'], case.get('endpoint_evidence')
    return {'before':before, 'after':case['proposed'], 'context':pack['contexts'][case['context_ref']],
            'selection_policy':case['selection_policy'], 'endpoint':endpoint}, case

def endpoint_identity(value):
    if value is None: return None
    return {('baseline'+k[len('parent'):] if k.startswith('parent_') else k):v for k,v in value.items()}

def endpoint_compatible(left, right):
    """Same original grid counts; cap/parent witness schemas can add fields."""
    a,b = endpoint_identity(left),endpoint_identity(right)
    if a is None or b is None: return a is b
    core = {'unit','item_id','grid_cells','baseline_item_pass','proposed_item_pass',
            'baseline_passing_cells','proposed_passing_cells'}
    return all(a.get(k) == b.get(k) for k in core) and all(a[k] == b[k] for k in a.keys() & b.keys())

def same_content(left, right):
    return all(left[k] == right[k] for k in ('before','after','context','selection_policy'))

def notes(h):
    text = h.get('observed_content_and_parent_review', h.get('observation',
                 h.get('observed_changes_and_limits', h.get('observed_change'))))
    if text is None:
        text = ' '.join(str(h.get(k,'')) for k in ('what_changed','where_it_fails_or_limits','judge_disagreement')).strip()
    require(isinstance(text,str) and bool(text.strip()), 'Human case observation missing')
    if h.get('endpoint_scope_limit'): text += ' '+h['endpoint_scope_limit']
    return text

def assemble_examples(prior, merged, sources, final_cap_sha, final_parent_sha):
    """Preserve old entries verbatim; dedup new references only with exact evidence."""
    examples = deepcopy(prior['dashboard_examples']); existing = {}; old_count = 0
    for condition, items in examples.items():
        for item in items:
            old_count += 1; evidence,case = resolve(condition,item,sources)
            identity = key(condition,item,case.get('baseline_condition'))
            # Historical repeated entries are already approved and must remain
            # verbatim, including any distinct source-backed witness metadata.
            existing.setdefault(identity,[]).append(evidence)
    added = {}; covered = []; seen = set()
    for row in merged['new_case_notes']:
        r = row['source_reference']; serialized = blob(r)
        require(serialized not in seen, 'Duplicate final source reference'); seen.add(serialized)
        parent = 'parent_condition' in r; reference = r.get('parent_condition','capped_n1-n1')
        item = {'source_sha256':final_parent_sha if parent else final_cap_sha,
                **{k:r[k] for k in ('family','kind','cell_id')}, 'reference':reference,
                'title':TITLES[r['family']]+' / '+CATEGORIES[r['category']], 'analysis':notes(row['human_review'])}
        evidence,case = resolve(r['condition'],item,sources)
        require(evidence['before'] == r['official_parent' if parent else 'official_before']
                and evidence['after'] == r['official_proposed' if parent else 'official_after'],
                'Official before/after reference differs from full source')
        require(evidence['context'] == row['context'] and case['selection_policy'] == r['selection_policy']
                and case['category'] == r['category'], 'Full context or case policy differs')
        recorded_endpoint = r.get('parent_endpoint_evidence' if parent else 'endpoint_evidence')
        require(endpoint_identity(evidence['endpoint']) == endpoint_identity(recorded_endpoint),
                'Official question-grid evidence differs')
        identity = key(r['condition'],item)
        if identity in existing:
            require(any(same_content(old,evidence)
                        and (evidence['endpoint'] is None or endpoint_compatible(old['endpoint'],evidence['endpoint']))
                        for old in existing[identity]),
                    'New reference conflicts with preserved old identity')
            action = 'existing_approved_entry_exact_evidence'
        elif identity in added:
            old_item,old_evidence = added[identity]
            require(same_content(old_evidence,evidence), 'Duplicate new identity has different context or official pair')
            a,b = endpoint_identity(old_evidence['endpoint']),endpoint_identity(evidence['endpoint'])
            require(a is None or b is None or endpoint_compatible(old_evidence['endpoint'],evidence['endpoint']), 'Duplicate new identity has different question-grid evidence')
            if parent: added[identity] = item,evidence
            action = 'duplicate_new_cap_parent_reference'
        else:
            added[identity] = item,evidence; action = 'new_distinct_entry'
        covered.append({'source_reference':deepcopy(r), 'identity':list(identity), 'action':action,
                        'human_review_path':row['review_path'], 'human_review_sha256':row['review_sha256']})
    for identity,(item,_) in added.items(): examples.setdefault(identity[0],[]).append(item)
    require(all(examples[c][:len(v)] == v for c,v in prior['dashboard_examples'].items()), 'Old approved entries changed')
    require(len(covered) == merged['required_new_case_reference_count'] == merged['reviewed_new_case_reference_count'],
            'Merged final reference accounting differs')
    return examples, {'prior_entries_preserved_verbatim':old_count, 'prior_distinct_identities':len(existing),
                      'new_distinct_entries':len(added), 'new_source_references':len(covered),
                      'total_entries':sum(map(len,examples.values())), 'reference_to_display_identity':covered}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('prior-review','draft','inventory','native','native-state','native-receipt','reconstruction','reconstruction-state','reconstruction-receipt',
                 'effort','effort-receipt','cap-pack','parent-pack','index','merged-notes','output','receipt'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--final-review',action='append',required=True,help='partition=path; all four required')
    p.add_argument('--narrative',type=Path,help='Optional human-authored prose/presentation overlay, never automatic conclusions')
    a = p.parse_args(); require(os.getenv('SLURM_JOB_ID') in ('25536417','25536291'),'Use existing owned CPU after final human reviews')
    require(not a.output.exists() and not a.receipt.exists(),'Use absent immutable candidate/receipt paths')
    pins = {}
    def pin(path, expected=None):
        path = str(path); digest = sha(path);require(expected is None or digest == expected,'Source authority differs: '+path)
        require(pins.setdefault(path,digest) == digest,'Source changed during assembly')
        return digest
    def read(path, expected=None):
        pin(path,expected)
        return json.loads(Path(path).read_text())
    def pin_sources(value):
        for path,digest in value.get('source_sha256',{}).items():
            require(sha(path) == digest,'Pinned source changed: '+path);require(pins.setdefault(path,digest) == digest,'Conflicting source authority')
    prior = read(a.prior_review,PRIOR_SHA);draft = read(a.draft,DRAFT_SHA);inventory = read(a.inventory,SEAL)
    require(prior['status'] == 'root_reviewed_progress' and sum(map(len,prior['dashboard_examples'].values())) == 1771,
            'Prior V16 approved entry set differs')
    active = {c['condition_id'] for c in inventory['conditions'] if c['status'] in ('cached_selector_full_bank','scheduled_full_bank')}
    require(len(active) == 70,'Finite menu differs')
    native,numeric,effort,cap,parent,index,merged = [read(x) for x in (a.native,a.reconstruction,a.effort,a.cap_pack,a.parent_pack,a.index,a.merged_notes)]
    nsha,rsha,esha = pins[str(a.native)],pins[str(a.reconstruction)],pins[str(a.effort)]
    for path,output,digest in ((a.native_state,a.native,nsha),(a.reconstruction_state,a.reconstruction,rsha)):
        state = read(path)
        require(state['status'] == 'complete_pending_root_review' and state['output_sha256'] == digest
                and Path(state['output']).resolve() == output.resolve(),'Terminal extraction authority differs')
        if path == a.native_state:
            require(state['scientific_inputs_validated_complete'] is True,'Native validation incomplete')
            source_receipt = read(a.native_receipt,state['receipt_sha256'])
            require(source_receipt['status'] == 'sealed_all280_terminal_inputs'
                    and source_receipt['descriptor_count'] == 32 and source_receipt['condition_family_count'] == 280,
                    'Native canonical receipt differs')
        else:
            source_receipt = read(a.reconstruction_receipt,state['snapshot_receipt_sha256'])
            require(source_receipt['quality_analysis_sha256'] == nsha,'Numeric receipt native binding differs')
    require(native['status'] == 'complete_exploratory' and not native['missing_condition_families']
            and len(native['complete_condition_families']) == 280,'Final native remains incomplete')
    require(numeric['diagnostic_version'] == 5 and numeric['quality_analysis_sha256'] == nsha
            and {(r['condition'],r['family']) for r in numeric['rows']} == {(c,f) for c in active for f in TITLES}
            and len(numeric['rows']) == 280 and not any(r['missing_selection_sites'] for r in numeric['rows']),
            'Final reconstruction scope/quality binding differs')
    require(effort['status'] == 'complete_retrospective','Final effort remains partial')
    er = read(a.effort_receipt)
    require(er['status'] == 'terminal_effort_sealed_pending_root_review' and er['effort_sha256'] == esha
            and er['native']['sha256'] == nsha,'Final effort receipt binding differs')
    require(merged['status'] == 'all_fresh_and_inherited_reviews_validated' and not merged['pending_partitions']
            and merged['eligible_for_complete_final_public_notes'] is True and merged['analysis_sha256'] == nsha
            and merged['index_sha256'] == pins[str(a.index)],'Final human notes incomplete/unbound')
    reviews = {}
    for arg in a.final_review:
        part,path = arg.split('=',1);require(part not in reviews,'Duplicate final partition');reviews[part] = Path(path)
    require(set(reviews) == set(index['partitions']) == {'root','agent_1','agent_2','agent_3'},'All four final review partitions required')
    for path in reviews.values():
        value = read(path);require(merged['source_sha256'].get(str(path)) == pins[str(path)],'Final reviewer missing merged pin')
    for value in (native,numeric,cap,parent,index,merged,effort):
        require(value['manifest_sha256'] == SEAL,'Final source manifest differs')
    for value in (cap,parent,index): require(value['analysis_sha256'] == nsha,'Final qualitative native binding differs')
    sources = {};qualitative_sources = deepcopy(prior['qualitative_sources'])
    for source in prior['qualitative_sources']:
        sources[source['sha256']] = read(Path(source['path']),source['sha256'])
    for path,pack in ((a.cap_pack,cap),(a.parent_pack,parent)):
        digest = pins[str(path)];require(merged['source_sha256'].get(str(path)) == digest,'Final pack missing merged authority')
        sources[digest] = pack;qualitative_sources.append({'path':str(path),'sha256':digest})
    # Validate the completed merger's full source map, including prior index/reviews and inherited proofs.
    pin_sources(merged)
    for source in prior['review_sources']: pin(Path(source['path']),source['sha256'])
    examples,accounting = assemble_examples(prior,merged,sources,pins[str(a.cap_pack)],pins[str(a.parent_pack)])
    candidate = deepcopy(draft)
    if a.narrative:
        narrative = read(a.narrative)
        allowed = {'headline','resource_summary','findings','method_findings','recommendations','presentation','condition_findings','limits'}
        require(set(narrative) <= allowed,'Narrative may not rewrite evidence/status/source identity')
        candidate.update(deepcopy(narrative))
    candidate.update(status='final_candidate_pending_root_human_review',root_reviewed=False,
        created_utc=datetime.now(timezone.utc).isoformat(),previous_review_sha256=PRIOR_SHA,
        manifest_sha256=SEAL,results_sha256=nsha,reconstruction_sha256=rsha,effort_sha256=esha,
        qualitative_sources=qualitative_sources,dashboard_examples=examples)
    candidate['presentation']['reconstruction_sha256'] = rsha
    candidate['review_sources'] = deepcopy(prior['review_sources'])
    required = [a.prior_review,a.draft,a.native,a.native_state,a.native_receipt,a.reconstruction_state,a.reconstruction_receipt,a.effort_receipt,a.index,a.merged_notes,a.reconstruction,a.effort,*reviews.values()]
    if a.narrative: required.append(a.narrative)
    candidate['review_sources'].extend({'path':str(path),'sha256':pins[str(path)]} for path in required)
    # Do not retain earlier cutoff values as terminal effort figures.
    ledger = effort['ledger_audit'];charges = {r['status']:r for r in ledger['global_commitment']}
    candidate['effort'] = {'status':effort['status'],'captured_utc':ledger['settlement_cutoff_utc'],
        'api_settled_usd':charges.get('settled',{}).get('actual_usd',0),
        'retained_unknown_usd':charges.get('unknown',{}).get('reserved_usd',0),
        'sampled_live_reservations_usd':charges.get('reserved',{}).get('reserved_usd',0),
        'gpu_dollars':None,'note':'Recorded provider-usage estimates, not invoices; unknown/reserved amounts retained. See exact bound effort artifact.'}
    candidate['final_assembly_pending'] = ['Root must refresh/calibrate all seven approach narratives and 28 task-specific quality/fit notes against final actual rows, CIs, masks, references and warnings.',
        'Root must fill final editing chosen-output example with exact eligible parent and round1 lineage; no inference from unselected proposals.',
        'Root must review all70 appendices, raw/capped distinction, reconstruction pp coverage, undefined/degenerate CI warnings, and explicitly authorize root_reviewed status.']
    candidate['original_draft_pending_fields'] = deepcopy(draft.get('pending_fields'))
    candidate['pending_fields'] = deepcopy(candidate['final_assembly_pending'])
    candidate['terminal_sources_pending'] = []
    pins[str(Path(__file__))] = sha(__file__)
    candidate['source_sha256'] = deepcopy(pins)
    require(all(sha(path) == digest for path,digest in pins.items()),'Sources changed before candidate output')
    receipt = {'status':'prospective_assembly_candidate_created_not_root_reviewed','source_sha256':pins,
               'accounting':accounting,'no_statistics_or_calls':True,'pending':candidate['final_assembly_pending']}
    for path,value in ((a.output,candidate),(a.receipt,receipt)):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(a.output),'sha256':sha(a.output),'receipt_sha256':sha(a.receipt),'counts':{k:v for k,v in accounting.items() if k!='reference_to_display_identity'}}))

if __name__ == '__main__': main()
