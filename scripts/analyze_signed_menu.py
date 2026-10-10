"""Gate-checked frozen-menu metrics, lengths and reproducible paired traces.

No judging or inference. All families must be terminal before publication.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.reporting import digest, reporting_stage, summarize, FAMILIES, unique, BENCH_ROOT
from analyze_consensus_conditions import read_arm


def component_pairs(conditions):
    """Prespecified on/off and matched-deletion contrasts, if in the signed menu."""
    names = {f"{r['method']}-n{r['n']}" for r in conditions}
    pairs = []
    for prefix, parent in [('best_n_specificity_mean', 'best_n_specificity_mean-n32'),
                           ('a32', 'best_n_exact-n32')]:
        for threshold in ('.001', '.005'):
            value = '0' + threshold
            prune = (f'{prefix}_then_prune_{value}-n32' if prefix != 'a32'
                     else f'prune_loo_a32_{value}-n32')
            random_arm = (f'{prefix}_random_delete_matched_{value}-n32' if prefix != 'a32'
                          else f'random_delete_matched_a32_{value}-n32')
            for pair in [(parent, prune), (parent, random_arm), (random_arm, prune)]:
                if set(pair) <= names:
                    pairs.append(pair)
    for pair in [('best_n_exact-n16', 'pooled_greedy_swap-n16'),
                 ('best_n_exact-n32', 'pooled_greedy_swap-n32'),
                 ('best_n_exact-n32', 'best_n_specificity_mean-n32'),
                 ('best_n_exact-n16', 'best_n_exact-n32'),
                 ('pooled_greedy_swap-n16', 'pooled_greedy_swap-n32'),
                 ('prune_loo_a32_0.001-n32', 'best_n_specificity_mean_then_prune_0.001-n32'),
                 ('prune_loo_a32_0.005-n32', 'best_n_specificity_mean_then_prune_0.005-n32')]:
        if set(pair) <= names:
            pairs.append(pair)
    return list(dict.fromkeys(pairs))


def sample_changes(baseline, proposed, cells, family):
    buckets = defaultdict(list)
    for cid in sorted(proposed):
        b, p = baseline[cid], proposed[cid]
        if family == 'hallucination':
            category = ('wrong_to_consistent' if b['class']=='hallucinated' and p['class']=='consistent'
                        else 'consistent_to_wrong' if b['class']=='consistent' and p['class']=='hallucinated'
                        else 'wrong_to_offtopic' if b['class']=='hallucinated' and p['class']=='off_topic'
                        else 'wrong_to_empty' if b['class']=='hallucinated' and p['empty']
                        else 'unchanged' if b['class']==p['class'] else 'other_class_change')
        else:
            category = 'win' if p['pass'] and not b['pass'] else 'regression' if b['pass'] and not p['pass'] else 'unchanged'
        buckets[category].append({'cell_id':cid, 'item_id':cells[cid]['item_id'],
                                 'layer':cells[cid]['layer'], 'position':cells[cid]['position'],
                                 'baseline':b, 'proposed':p})
    examples = {}
    for category, rows in buckets.items():
        if category == 'unchanged':
            examples[category] = random.Random(20261010).sample(rows, min(3, len(rows)))
        else:
            chosen, seen = [], set()
            for row in rows:
                if row['item_id'] not in seen:
                    chosen.append(row); seen.add(row['item_id'])
                if len(chosen) == 3:
                    break
            examples[category] = chosen
    return {'cell_change_counts':{k:len(v) for k,v in buckets.items()}, 'examples':examples}


def role_contexts(item_ids):
    """Exact pinned MC options, for evaluation-only traces after authorization."""
    from olens_improve.data import load_bank, paths
    sys.path.insert(0, str(BENCH_ROOT/'src'))
    from wsbench.evals.role_bound_association.judge import build_block
    bank = load_bank('role_bound_association')
    items = unique(bank, lambda r:str(r['id']))
    source_paths = [paths('role_bound_association')['bank'],
        BENCH_ROOT/'src/wsbench/evals/role_bound_association/judge.py',
        BENCH_ROOT/'src/wsbench/evals/role_bound_association/prompts.py']
    hashes = {str(p):digest(p) for p in source_paths}
    contexts = {}
    for ident in item_ids:
        block, golds = build_block(items[ident], bank)
        contexts[ident] = {'exact_upstream_mc_block':block,'gold_choice_indexes':list(golds)}
    return contexts, hashes


def enrich_traces(traces, measurement, cells):
    """Attach retained verdicts to fixed sampled traces, never back to selection."""
    needed = defaultdict(dict)
    for comparison in traces:
        for family, details in comparison['families'].items():
            if family == 'hallucination':
                continue
            for examples in details['examples'].values():
                for sample in examples:
                    for label, condition in [('baseline',comparison['baseline_condition']),
                                             ('proposed',comparison['condition'])]:
                        needed[condition,family][sample['cell_id']] = sample[label]
    roots = {c['condition']:Path(c['condition_root'])/c['condition'] for c in measurement['conditions']}
    role_ids = {str(cells[cid]['item_id']) for (arm,family),rows in needed.items()
                if family == 'role_bound_association' for cid,row in rows.items() if not row['empty']}
    contexts, hashes = role_contexts(role_ids) if role_ids else ({},{})
    for (condition,family), samples in needed.items():
        folder = roots[condition]/family
        result_path = folder/'results.json'
        results = json.loads(result_path.read_text())['rows']
        hashes[str(result_path)] = digest(result_path)
        by_key = unique(results, (lambda r:(str(r['id']),int(r['layer']),int(r['pos'])))
                        if family=='role_bound_association' else lambda r:str(r['id']))
        raw_keys = set()
        for cid, sample in samples.items():
            if sample['empty']:
                continue
            cell = cells[cid];item = str(cell['item_id']);layer = str(cell['layer'])
            if family=='role_bound_association':
                raw_keys.add(by_key[item,cell['layer'],cell['position']]['key'])
            elif family=='chain_intermediates':
                raw_keys.add(f"{item}|L{cell['layer']:03d}")
        cached = {}
        if raw_keys:
            cache_path = folder/'cells.jsonl'
            before = digest(cache_path)
            with cache_path.open() as handle:
                for line in handle:
                    row = json.loads(line)
                    if row.get('key') in raw_keys and row.get('result') is not None:
                        cached[row['key']] = row
            if digest(cache_path) != before:
                raise ValueError('Retained verdict cache changed during trace extraction')
            hashes[str(cache_path)] = before
            if set(cached) != raw_keys:
                raise ValueError('A sampled trace lacks its retained raw verdict')
        for cid, sample in samples.items():
            if sample['empty']:
                sample['evidence'] = {'evaluation_only':True,'explicit_empty_abstention':True}
                continue
            cell = cells[cid];item = str(cell['item_id']);layer = str(cell['layer'])
            if family=='role_bound_association':
                official = by_key[item,cell['layer'],cell['position']]
                raw = cached[official['key']];context = contexts[item]
                answers = [raw['result'][f'q{i}_choice'] for i in (1,2,3)]
                golds = context['gold_choice_indexes']
                if raw['meta']['golds'] != golds or [a==g for a,g in zip(answers,golds)] != official['correct']:
                    raise ValueError('Retained role choices differ from official scored verdict/options')
                evidence = context | {'upstream_scored_result':official,'retained_raw_cache_record':raw,
                                      'returned_choice_indexes':answers,'rationale':raw['result'].get('evidence')}
            elif family=='chain_intermediates':
                official = by_key[item];raw = cached[f"{item}|L{cell['layer']:03d}"]
                evidence = {'named_values':official['named_by_layer'][layer],
                    'kind':official['kind_by_layer'][layer],'basis':official['basis_by_layer'][layer],
                    'reference_context':{k:official[k] for k in ('start','intermediates','answer','depth')},
                    'retained_raw_cache_record':raw}
            else:
                official = by_key[item]
                evidence = {'readout_text':sample['text'],'retained_layer_match_result':official['layers'][layer],
                    'required_roles':official['roles'],'optional_roles':official.get('optional_roles',[]),
                    'interpretation':'Retained language-hit evidence with exact readout text; not invented substring offsets.'}
            sample['evidence'] = evidence | {'evaluation_only':True}
    if any(digest(path) != expected for path,expected in hashes.items()):
        raise ValueError('Trace evidence source changed')
    return hashes


def run(args):
    # This must precede reading selected outputs, verdicts or their digests.
    frozen, stage, _ = reporting_stage(args.manifest, args.conditions,
        fresh_manifest=args.fresh_manifest, gate=args.gate,
        condition_list=args.condition_list, freeze=args.freeze)
    if {c['family'] for c in frozen['cells']} != set(FAMILIES):
        raise ValueError('Analysis requires all four frozen families')
    if args.output.exists():
        raise FileExistsError('Use a new immutable analysis artifact')
    if digest(args.selections) != args.selection_sha256:
        raise ValueError('Selected-output bytes differ from the exact declared source')
    conditions = json.loads(args.conditions.read_text())
    comparisons = component_pairs(conditions)
    measurement = summarize(args.manifest, args.conditions, args.judgments,
        selection_sha=args.selection_sha256, fresh_manifest=args.fresh_manifest,
        gate=args.gate, condition_list=args.condition_list, freeze=args.freeze,
        comparison_pairs=comparisons)
    if not all(r['measurement_complete'] for r in measurement['conditions']):
        raise ValueError('All signed conditions and all four families must be complete')
    cells = {c['cell_id']:c for c in frozen['cells']}
    names = [f"{r['method']}-n{r['n']}" for r in conditions]
    lengths = {name:defaultdict(list) for name in names}
    outputs = {name:{} for name in names}
    seen = set()
    with args.selections.open() as handle:
        for line in handle:
            row = json.loads(line); cid = row['cell_id']
            if cid in seen or cid not in cells:
                raise ValueError('Duplicate or foreign selected cell')
            seen.add(cid)
            if any(row[k] != cells[cid][k] for k in ('family','item_id','layer','position','split')):
                raise ValueError('Selected source differs from frozen cohort')
            actual = [f"{s['method']}-n{s['n']}" for s in row['selections']]
            if actual != names:
                raise ValueError('Selected menu differs from exact signed dispatch order')
            for selection, name in zip(row['selections'], names):
                for field in ('token_count', 'bullet_count'):
                    value = selection[field]
                    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                        raise ValueError('Invalid output length count')
                lengths[name][row['family']].append(selection)
                outputs[name][cid] = selection['text']
    if seen != set(cells):
        raise ValueError('Incomplete selected cohort')
    if digest(args.selections) != args.selection_sha256:
        raise ValueError('Selected source changed during analysis')
    lengths = {name:{family:{'outputs':len(rows),
        'mean_qwen_tokens_all_intended':statistics.mean(r['token_count'] for r in rows),
        'mean_bullets_all_intended':statistics.mean(r['bullet_count'] for r in rows)}
        for family,rows in families.items()} for name,families in lengths.items()}
    arms = {}
    for condition in measurement['conditions']:
        name = condition['condition']
        arms[name] = {}
        for family in condition['families']:
            rows = read_arm(Path(condition['condition_root']) / name, family, cells)
            if any(rows[cid]['text'] != outputs[name][cid] for cid in rows):
                raise ValueError('Judged text differs from selected source')
            arms[name][family] = rows
    pairs = list(dict.fromkeys((r['baseline_condition'],r['condition'])
                              for r in measurement['paired_comparisons']))
    traces = [{'baseline_condition':baseline,'condition':proposed,
        'families':{f:sample_changes(arms[baseline][f],arms[proposed][f],cells,f)
                    for f in arms[proposed]}} for baseline,proposed in pairs]
    evidence_hashes = enrich_traces(traces, measurement, cells)
    # Retain the original aggregator's stability check for subsequently read traces.
    for condition in measurement['conditions']:
        if any(digest(p) != expected for p,expected in condition['source_sha256'].items()):
            raise ValueError('Judgment/source bytes changed during trace extraction')
    result = {'status':f'complete_four_family_{stage}_comparison', 'measurement':measurement,
        'selection_source':str(args.selections), 'selection_source_sha256':args.selection_sha256,
        'component_comparison_pairs':comparisons, 'lengths':lengths, 'paired_traces':traces,
        'trace_evidence_source_sha256':evidence_hashes, 'trace_evidence_evaluation_only':True,
        'trace_sampling':'First three distinct items per changed category; three seeded unchanged cells; seed 20261010',
        'limits':['Separate family denominators; no hidden cross-family macro.',
            'Item ANY recovery and cell recovery are different endpoints.',
            'Transcript contradictions are distinct from true/unverifiable claim tallies and false spans.',
            'Grouped intervals are unadjusted; traces are sampled evidence, not prevalence estimates.',
            'A32 versus N1 combines candidate budget and selection; component/matched-deletion pairs address only their declared contrast.']}
    with args.output.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2); handle.write('\n')
    args.output.chmod(0o444)
    print(json.dumps({'status':result['status'],'output':str(args.output),'sha256':digest(args.output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('manifest','conditions','judgments','selections','output'):
        parser.add_argument('--'+flag,type=Path,required=True)
    for flag in ('fresh-manifest','gate','condition-list','freeze'):
        parser.add_argument('--'+flag,type=Path)
    parser.add_argument('--selection-sha256',required=True)
    run(parser.parse_args())
