"""Index new exact case and parent evidence without extending previous review coverage."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from expanded_cpu_cached import atomic, sha


def cases(pack):
    for condition, entry in pack['conditions'].items():
        for family, details in entry['families'].items():
            for kind in ('fixed_anchor', 'outcome_selected'):
                for row in details[kind]:
                    yield (condition, family, kind, row['cell_id']), row


def content_key(family, cid, before, after):
    return json.dumps([family, cid, before['text'], after['text']], ensure_ascii=False)


def ref(key, row):
    return {'condition': key[0], 'family': key[1], 'kind': key[2], 'cell_id': key[3],
            'category': row['category'], 'selection_policy': row['selection_policy'],
            'context_ref': row['context_ref'], 'endpoint_evidence': row['endpoint_evidence']}


def main():
    parser = argparse.ArgumentParser()
    for name in ('previous', 'current', 'previous-parents', 'current-parents', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a new immutable reviewer index')
    source_paths = [args.previous, args.current, args.previous_parents, args.current_parents]
    previous, current, old_parents, parents = [json.loads(p.read_text()) for p in source_paths]
    old = dict(cases(previous)); new = dict(cases(current))
    if any(new.get(key) != row for key, row in old.items()):
        raise ValueError('A previously selected full case changed')
    review_paths = sorted(Path('docs/reviews').glob('expanded-qualitative-partition*-v1.json'))
    review_paths += [Path('docs/reviews/expanded-pruning-parent-qualitative-v1.json')]
    pins = {str(p): sha(p) for p in source_paths+review_paths}
    prior_pairs = defaultdict(list)
    for key, row in old.items():
        prior_pairs[content_key(key[1],key[3],row['baseline'],row['proposed'])].append(ref(key,row))
    units = {}; baseline_groups = {}; parent_groups = {}; new_refs = 0; new_parent_refs = 0

    def unit(key, proposed):
        identity = json.dumps([key[1],key[3],proposed['text']],ensure_ascii=False)
        return units.setdefault(identity, {'family':key[1],'cell_id':key[3], 'context_ref':key[3],
            'proposed_text':proposed['text'],'capped_N1_pairs':[],'actual_parent_pairs':[]})

    for key, row in new.items():
        if key in old:
            continue
        new_refs += 1
        identity = content_key(key[1],key[3],row['baseline'],row['proposed'])
        if identity not in baseline_groups:
            group = {'before':row['baseline'],'after':row['proposed'],'references':[],
                'previous_identical_content_references':prior_pairs.get(identity,[]),
                'previous_review_provenance':[{'path':str(p),'sha256':pins[str(p)]} for p in review_paths[:3]],
                'review_status':'new_official_evidence_pending_review_even_when_content_was_seen'}
            baseline_groups[identity] = group
            unit(key,row['proposed'])['capped_N1_pairs'].append(group)
        baseline_groups[identity]['references'].append(ref(key,row)|{'official_before':row['baseline'], 'official_after':row['proposed']})

    old_parent_cases = dict(cases(old_parents))
    for key, row in cases(parents):
        before_row = old_parent_cases.get(key,{})
        for parent, comparison in row['parents'].items():
            if comparison['status'] != 'complete':
                continue
            old_comparison = before_row.get('parents',{}).get(parent,{})
            if old_comparison.get('status') == 'complete':
                if old_comparison != comparison:
                    raise ValueError('A previous complete parent comparison changed')
                continue
            new_parent_refs += 1
            identity = content_key(key[1],key[3],comparison['output'],row['proposed'])
            if identity not in parent_groups:
                group = {'before':comparison['output'],'after':row['proposed'],'references':[],
                    'review_status':'new_actual_parent_contrast_pending_review'}
                parent_groups[identity] = group
                unit(key,row['proposed'])['actual_parent_pairs'].append(group)
            parent_groups[identity]['references'].append(ref(key,row)|{'parent_condition':parent,
                'parent_endpoint_evidence':comparison['endpoint_evidence'],
                'official_parent':comparison['output'],'official_proposed':row['proposed'],
                'capped_N1_before':row['original_baseline']})
    partitions = {name:[] for name in ('root','agent_1','agent_2','agent_3')}; loads={name:0 for name in partitions}
    ordered = sorted(units.values(),key=lambda row:(-len(row['capped_N1_pairs'])-len(row['actual_parent_pairs']),row['family'],row['cell_id'],row['proposed_text']))
    for row in ordered:
        name=min(loads,key=lambda name:(loads[name],name));partitions[name].append(row)
        loads[name]+=len(row['capped_N1_pairs'])+len(row['actual_parent_pairs'])
    payload={'status':'delta_evidence_pending_independent_review','manifest_sha256':current['manifest_sha256'],
        'analysis_sha256':current['analysis_sha256'],'source_sha256':pins,
        'implementation_sha256':{str(Path(__file__)):sha(__file__)},
        'retained_previous_cases':len(old),'new_capped_N1_case_references':new_refs,
        'unique_new_capped_N1_content_pairs':len(baseline_groups),'new_actual_parent_references':new_parent_refs,
        'unique_new_actual_parent_content_pairs':len(parent_groups),'review_unit_count':len(units),
        'partitions':partitions,'partition_comparison_counts':loads,
        'contexts':{row['cell_id']:current['contexts'][row['cell_id']] for row in units.values()},
        'review_instructions':['Retain condition-specific official evidence and original-grid witnesses when identical content is deduplicated.',
            'Separate eight outcome-blind fixed anchors from lexicographic outcome-selected supplements.',
            'A judged match is not full prose faithfulness or full-answer correctness; distinguish observed shifts, judge disagreements and hypotheses.',
            'Compare derived conditions against actual frozen parents before attributing a capped-N1 gain to pruning, pooling or editing.',
            'Prior review hashes are provenance links only; new condition-family evidence remains unreviewed until inspected.',
            'No paid calls, score changes, new case selection or external factual verification.']}
    if any(sha(p)!=value for p,value in pins.items()):
        raise ValueError('Delta evidence changed while indexing')
    atomic(args.output,payload)
    print(json.dumps({'output':str(args.output),'sha256':sha(args.output),'new_baseline_refs':new_refs,
        'new_parent_refs':new_parent_refs,'units':len(units),'partition_comparison_counts':loads}))


if __name__ == '__main__':
    main()
