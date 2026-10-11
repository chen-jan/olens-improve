"""Terminal-only descriptive editor selection counts; no fitting or judging.

Origin is candidate provenance, not evidence that selected prose changed. Fit
change counts are copied from the approved final v5 aggregate, not recomputed.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from expanded_editor_fit_intake_v2 import canonical_digest, unique_dispatch_arguments, validate_event_linkage

FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')
SEAL = '753b2d9cab0daea0d19efef7d3222fd44921dbcf4669e6864d4f1bd4805421f8'
V5 = 'cb9cc9a7578f0a617e6a567e2c14e3fcee720e1a807c0b452ca9b40f925a99f8'
HELPER = 'ec6a8de982fd25023a1130c6c4cb4ae87418765e0991629b171f58bf1c6e436f'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda: stream.read(1048576), b''): h.update(b)
    return h.hexdigest()


def require(value, message):
    if not value: raise ValueError(message)


def committed(path):
    with Path(path).open() as stream:
        for line in stream:
            require(line.endswith('\n'), 'Nonterminal journal record')
            if line.strip(): yield json.loads(line)


def selected_category(event, previous, current_ids):
    """Keep inherited R1 edits distinct from new R2 proposals, even for equal text."""
    best = event['best']; cid = event['cell_id']; number = event['round']
    require(best is not None, 'Missing selected candidate')
    byid = {c['candidate_id']: c for c in event['candidates']}
    require(len(byid) == len(event['candidates']) and byid.get(best['candidate_id']) == best,
            'Selected candidate differs from scored union')
    origin = best['origin']; candidate_id = best['candidate_id']
    if origin == 'unchanged_parent':
        require(candidate_id in {cid+':initial:best_n_exact', cid+':initial:pooled_greedy_swap'},
                'Unchanged origin is not an original eligible parent')
        return 'selected_original_parent'
    if number == 2 and origin == 'editing_round1':
        require(previous is not None and candidate_id in previous['candidates']
                and previous['candidates'][candidate_id] == (sha_text(best['text']), origin),
                'Inherited round1 edit differs from terminal history')
        return 'selected_prior_round_edit'
    require(origin == f'editing_round{number}' and candidate_id in current_ids,
            'Selected current-round origin lacks exact proposal identity')
    return 'selected_new_current_round_edit'


def sha_text(text): return hashlib.sha256(text.encode()).hexdigest()


def describe_event(event, previous, current_ids):
    category = selected_category(event, previous, current_ids)
    best = event['best']; candidates = {c['candidate_id']: c for c in event['candidates']}
    counts = Counter({category: 1})
    for label, method in (('pooled_parent', 'pooled_greedy_swap'), ('best32_parent', 'best_n_exact')):
        parent = candidates.get(event['cell_id']+':initial:'+method)
        counts[label+'_text_comparisons'] += int(parent is not None)
        if parent is not None:
            equal = best['text'] == parent['text']
            counts[label+'_byte_identical'] += int(equal)
            counts[label+'_changed_text'] += int(not equal)
        else: counts[label+'_unavailable'] += 1
    if event['round'] == 2:
        require(previous is not None, 'Round2 lacks terminal round1 cell')
        equal = sha_text(best['text']) == previous['selected_text_sha256']
        counts['previous_round_text_comparisons'] += 1
        counts['previous_round_byte_identical'] += int(equal)
        counts['previous_round_changed_text'] += int(not equal)
        counts['previous_round_same_selected_candidate_id'] += int(best['candidate_id'] == previous['selected_candidate_id'])
    if category == 'selected_new_current_round_edit':
        parent = candidates.get(best['parent_candidate_id'])
        require(parent is not None, 'Selected proposal lacks its actual eligible parent')
        equal = best['text'] == parent['text']
        counts['selected_current_edit_actual_parent_byte_identical'] += int(equal)
        counts['selected_current_edit_actual_parent_changed_text'] += int(not equal)
    record = {'selected_candidate_id': best['candidate_id'], 'selected_text_sha256': sha_text(best['text']),
              'candidates': {k: (sha_text(c['text']), c['origin']) for k, c in candidates.items()}}
    return counts, record


def copied_fit_counts(row, row_index):
    fields = ('reference', 'kind', 'paired_sites', 'intended_paired_sites', 'missing_or_invalid_pairs',
              'improved_sites', 'worsened_sites', 'unchanged_or_within_numerical_tolerance',
              'site_change_equivalence_tolerance', 'warning')
    return [{'source_row_index': row_index, 'source_parent_comparison_index': i,
             **{key: p[key] for key in fields if key in p}}
            for i, p in enumerate(row['parent_comparisons'])
            if p['reference'] in ('best_n_exact-n32', 'pooled_greedy_swap-n32', 'editing_round1-n32')]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reconstruction', type=Path, required=True); p.add_argument('--reconstruction-sha256', required=True)
    p.add_argument('--reconstruction-state', type=Path, required=True)
    p.add_argument('--native', type=Path, required=True); p.add_argument('--native-sha256', required=True)
    p.add_argument('--native-state', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    require(os.environ.get('SLURM_JOB_ID') in ('25536417', '25536291'), 'Use existing owned CPU after final gates')
    require(not a.output.exists(), 'Supplement output exists; no overwrite')
    pins = {}
    def pin(path, expected=None):
        path = str(Path(path).resolve()); actual = sha(path)
        require(expected is None or actual == expected, 'Source differs from retained authority: '+path)
        require(pins.setdefault(path, actual) == actual, 'Source changed during intake: '+path)
        return Path(path)
    def read(path, expected=None): return json.loads(pin(path, expected).read_text())
    numeric = read(a.reconstruction, a.reconstruction_sha256); native = read(a.native, a.native_sha256)
    for state_path, output_path, expected in ((a.reconstruction_state, a.reconstruction, a.reconstruction_sha256),
                                             (a.native_state, a.native, a.native_sha256)):
        state = read(state_path)
        require(state['status'] == 'complete_pending_root_review' and state['output_sha256'] == expected,
                'Final extraction gate is not terminal for supplied output')
        require(Path(state['output']).resolve() == output_path.resolve(), 'Terminal gate output path differs')
        if state_path == a.native_state:
            require(state['scientific_inputs_validated_complete'] is True, 'Native source validation is incomplete')
    require(native['manifest_sha256'] == numeric['manifest_sha256'] == SEAL
            and numeric['quality_analysis_sha256'] == a.native_sha256 and numeric['diagnostic_version'] == 5,
            'Final numerical/native authority differs')
    require(native['status'] == 'complete_exploratory' and not native['missing_condition_families'], 'Native remains partial')
    require(len(native['complete_condition_families']) == 280 and len(numeric['rows']) == 280
            and not any(r['missing_selection_sites'] for r in numeric['rows']), 'Final70x4 selections incomplete')
    implementation = {str(Path(k).resolve()): v for k, v in numeric['implementation_sha256'].items()}
    base = Path(__file__).resolve().parent
    for name, value in (('analyze_expansion_reconstruction_v5.py', V5), ('expanded_editor_fit_intake_v2.py', HELPER)):
        require(implementation.get(str(base/name)) == value, 'Unapproved final numerical implementation')
        pin(base/name, value)
    source = {str(Path(k).resolve()): v for k, v in numeric['source_sha256'].items()}
    def authorized(path):
        path = str(Path(path).resolve()); require(path in source, 'Source absent from approved final aggregate')
        return pin(path, source[path])
    audits = {(x['round'], x['family']): x for x in numeric['editor_fit_authority_audits']}
    require(len(audits) == len(numeric['editor_fit_authority_audits']) == 8
            and set(audits) == {(r, f) for r in (1, 2) for f in FAMILIES}, 'Eight editor authorities incomplete')
    fitrows = {(r['condition'], r['family']): (i, r) for i, r in enumerate(numeric['rows'])}
    require(len(fitrows) == 280, 'Duplicate final condition-family rows')
    result = []
    for family in FAMILIES:
        previous = {}
        for number in (1, 2):
            audit = audits[number, family]; task = audit['dispatch_task']
            require(audit['completed_task_receipt']['task_sha256'] == hashlib.sha256(json.dumps(task, sort_keys=True).encode()).hexdigest(),
                    'Successful immutable task receipt differs')
            args = unique_dispatch_arguments(task['command']); folder = Path(args['--output'])
            spec = read(authorized(folder/'spec.json')); status = read(authorized(folder/'status.json'))
            linkage = canonical_digest(spec)
            require(linkage == audit['canonical_spec_sha256'] and spec['round'] == number
                    and status['status'] == 'complete' and status['round'] == number, 'Editor terminal/spec differs')
            cohort = read(authorized(args['--cells-manifest']))['cells']; cells = {c['cell_id']: c for c in cohort}
            require(len(cells) == len(cohort) == status['cells'] == audit['sites'], 'Editor cohort duplicates/incomplete')
            proposals = {}
            for row in committed(authorized(args['--proposals'])):
                require(row['cell_id'] not in proposals and row['round'] == number, 'Duplicate/foreign proposal row')
                proposals[row['cell_id']] = {c['candidate_id'] for c in row['editing']['proposals']}
            require(set(proposals) == set(cells) == set(spec['candidate_ids']), 'Exact proposal/spec cohort differs')
            if number == 2:
                authorized(args['--history'])
                require(set(previous) == set(cells), 'Previous-round exact cohort differs')
            counts = Counter(); seen = set(); next_previous = {}
            for event in committed(authorized(folder/'scored_candidates.jsonl')):
                cid = event['cell_id']; require(cid in cells and cid not in seen, 'Off-cohort/duplicate terminal event')
                validate_event_linkage(event, spec, linkage)
                require(all(event[k] == cells[cid][k] for k in ('family', 'item_id', 'layer', 'position', 'split', 'activation_sha256')),
                        'Terminal event identity differs')
                scored_ids = [c['candidate_id'] for c in event['candidates']]
                rejected_ids = [c['candidate_id'] for c in event['rejected']]
                require(len(scored_ids) == len(set(scored_ids)) and set(scored_ids) == set(spec['candidate_ids'][cid])
                        and len(rejected_ids) == len(set(rejected_ids)) and not set(scored_ids) & set(rejected_ids),
                        'Scored spec candidate set or separate rejected identities differ')
                if number == 2:
                    byid = {c['candidate_id']: c for c in event['candidates']}
                    require(all(k in byid and (sha_text(byid[k]['text']), byid[k]['origin']) == value
                                for k, value in previous[cid]['candidates'].items()), 'Retained previous candidates changed')
                count, record = describe_event(event, previous.get(cid), proposals[cid])
                counts.update(count); next_previous[cid] = record; seen.add(cid)
            require(seen == set(cells), 'Terminal journal omits cohort cells')
            index, row = fitrows[f'editing_round{number}-n32', family]
            result.append({'condition': row['condition'], 'family': family, 'round': number, 'cells': len(cells),
                           'counts': {k: counts[k] for k in ('selected_original_parent', 'selected_prior_round_edit', 'selected_new_current_round_edit')} | dict(counts),
                           'existing_common_valid_fit_change_counts': copied_fit_counts(row, index),
                           'dispatch_task_sha256': audit['dispatch_task_sha256'], 'canonical_spec_sha256': linkage})
            previous = next_previous
    pin(__file__)
    require(all(sha(k) == v for k, v in pins.items()), 'Pinned terminal evidence changed before output')
    output = {'status': 'terminal_descriptive_selection_supplement_pending_root_review', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'manifest_sha256': SEAL, 'quality_analysis_sha256': a.native_sha256, 'reconstruction_sha256': a.reconstruction_sha256,
              'rows': result, 'source_sha256': pins, 'new_fits': 0, 'new_api_calls': 0,
              'limits': ['Origin counts and exact full-text identity counts are distinct; a new candidate ID may retain identical text.',
                         'Round2 editing_round1 origin is a prior edit, never a newly selected round2 proposal.',
                         'Fit change counts reuse exact approved v5 common-valid masks and >1e-5 tolerance; no new statistics or quality endpoint.',
                         'Unavailable parents/fit comparisons remain explicit; selected text equality does not establish truth or causal improvement.']}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as stream: stream.write(json.dumps(output, indent=2)+'\n')
    print(json.dumps({'output': str(a.output), 'sha256': sha(a.output), 'rows': len(result)}))


if __name__ == '__main__': main()
