"""Build a compact exploratory matrix from pinned measured sources."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil

FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')
ENDPOINTS = {family: ('original_grid_contradiction_rate' if family == 'hallucination'
                     else 'original_grid_item_pass_rate') for family in FAMILIES}
ACTIVE = {'cached_selector_full_bank', 'scheduled_full_bank'}


def read(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def category(method):
    if 'then_prune' in method or 'random_delete_matched' in method or method.startswith(('pooling_exact_', 'pooled_specificity')):
        return 'combinations' if not method.startswith('random_delete_matched_') else 'pruning'
    if method.startswith(('consensus', 'exact_support')):
        return 'consensus'
    if method.startswith(('prune_', 'random_delete_')):
        return 'pruning'
    if method.startswith('pooled_'):
        return 'pooling'
    if method.startswith('editing_'):
        return 'editing'
    if 'specificity' in method or 'likelihood' in method:
        return 'verification'
    return 'selection'


def label(row):
    method, n = row['method'], row['n']
    fixed = {'raw_n1': 'Original Oracle Lens', 'capped_n1': 'Original, capped to four bullets',
             'best_n_exact': 'Choose the best complete readout', 'random_complete': 'Choose a random complete readout',
             'pooled_greedy_swap': 'Combine original bullets', 'best_n_specificity_mean': 'Compare with average control activation',
             'best_n_specificity_max': 'Compare with strongest control activation',
             'best_n_specificity_mean_abstain_nonpositive': 'Control comparison, omit nonpositive results',
             'likelihood_true_minus_mean_two_controls': 'Likelihood: true activation minus controls',
             'own_mean_log_likelihood': 'Likelihood under the true activation',
             'control_mean_log_likelihood': 'Likelihood under control activations',
             'editing_round1': 'Edit once', 'editing_round2': 'Edit twice',
             'exact_support_only': 'Exact repetition only', 'pooled_specificity_mean': 'Combine bullets with activation specificity'}
    if method in fixed:
        title = fixed[method]
    elif method.startswith('consensus_'):
        semantic = 'semantic_' in method
        title = 'Semantic repetition' if semantic else 'Exact repetition'
        support = row.get('thresholds', {}).get('support_fraction', 0)
        title += f'; at least {round(support * 16)} of 16 samples'
        if row.get('helper_reasoning_effort') == 'medium': title += '; more helper reasoning'
        if row.get('thresholds', {}).get('compatibility_filter'): title += '; compatibility check'
        if row.get('thresholds', {}).get('contradiction_veto'): title += '; contradiction filter'
    elif method.startswith('pooling_exact_support_lambda'):
        title = 'Combine bullets with repetition weight ' + method.split('lambda')[1]
    elif method.startswith('prune_coefficient'):
        title = ('Best complete readout' if '_a32_' in method else 'Original capped readout')
        title += '; remove small reconstruction weights ' + method.rsplit('_', 1)[1]
    elif method.startswith(('prune_loo_', 'random_delete_matched_')):
        title = ('Best complete readout' if '_a32_' in method else 'Original capped readout')
        title += '; ' + ('random deletion control ' if method.startswith('random') else 'remove weak bullets ')
        title += method.rsplit('_', 1)[1]
    else:
        parent = method.split('_then_prune_')[0].split('_random_delete_matched_')[0]
        title = fixed.get(parent, parent.replace('_', ' '))
        title += '; ' + ('random deletion control ' if 'random_delete' in method else 'remove weak bullets ')
        title += method.rsplit('_', 1)[1]
    return title + (f' ({n} samples)' if n > 1 else '')


def checked_review(path, inventory_sha, results_sha, known):
    """Resolve reviewed cases from exact evidence, rather than copied prose."""
    if path is None:
        return {}, None
    review, review_sha = read(path)
    if (review.get('status') not in {'root_reviewed', 'root_reviewed_progress'}
            or review.get('manifest_sha256') != inventory_sha
            or review.get('results_sha256') != results_sha):
        raise ValueError('Dashboard review does not bind these results and menu')
    if set(review.get('condition_findings', {})) - known:
        raise ValueError('Foreign condition finding')
    sources = {}
    for source in review.get('qualitative_sources', []):
        pack, pack_sha = read(source['path'])
        if pack_sha != source['sha256'] or pack['manifest_sha256'] != inventory_sha:
            raise ValueError('Qualitative evidence source changed')
        sources[pack_sha] = pack
    examples = {}
    for condition, chosen in review.get('dashboard_examples', {}).items():
        if condition not in known:
            raise ValueError('Foreign reviewed condition')
        examples[condition] = []
        for item in chosen:
            pack = sources[item['source_sha256']]
            family, kind, cell_id = item['family'], item['kind'], item['cell_id']
            if family not in FAMILIES or kind not in {'fixed_anchor', 'outcome_selected'}:
                raise ValueError('Unknown case family or selection policy')
            cases = pack['conditions'][condition]['families'][family][kind]
            matches = [case for case in cases if case['cell_id'] == cell_id]
            if len(matches) != 1:
                raise ValueError('Reviewed case identity is ambiguous or missing')
            case = matches[0]
            reference = item.get('reference', case.get('baseline_condition'))
            if 'parents' in case:
                if reference == case['original_baseline_condition']:
                    before = case['original_baseline']
                    endpoint = case.get('endpoint_evidence')
                else:
                    parent = case['parents'][reference]
                    if parent['status'] != 'complete':
                        raise ValueError('Reviewed parent comparison is not complete')
                    before = parent['output']
                    endpoint = parent['endpoint_evidence']
            else:
                if reference != case['baseline_condition']:
                    raise ValueError('Different reference requires actual parent evidence')
                before = case['baseline']
                endpoint = case.get('endpoint_evidence')
            after = case['proposed']
            evidence = {'baseline_class': before['class'], 'selected_class': after['class'],
                        'baseline_site_pass': before['pass'], 'selected_site_pass': after['pass'],
                        'whole_question_evidence': endpoint}
            examples[condition].append({
                'title': item['title'], 'analysis': item['analysis'],
                'baseline_text': before['text'], 'text': after['text'],
                'baseline_condition': reference,
                'evidence': json.dumps(evidence, ensure_ascii=False),
                'context': json.dumps(pack['contexts'][case['context_ref']]['source_bank_item'],
                                      ensure_ascii=False, indent=2),
                'cell_id': cell_id, 'family': family, 'kind': kind,
                'selection_policy': case['selection_policy'],
                'source_sha256': item['source_sha256'],
                'official_evidence': {'reference': before.get('evidence'),
                                      'selected': after.get('evidence')},
            })
    return {**review, 'resolved_examples': examples}, review_sha


def checked_artifact(path, kind, review, inventory, inventory_sha, results_sha, known):
    """Optional diagnostics require explicit root authority, never imply quality."""
    if path is None:
        return None, None
    artifact, digest = read(path)
    if review.get(kind + '_sha256') != digest or artifact.get('manifest_sha256') != inventory_sha:
        raise ValueError(f'{kind} artifact is not bound by this root review and menu')
    if kind == 'reconstruction':
        if (artifact.get('quality_analysis_sha256') != results_sha
                or artifact.get('objective') != '1-squared_residual/squared_target'
                or artifact.get('solver') != 'scipy_exact'
                or artifact.get('vector_contract_sha256') != inventory['vector_contract']['sha256']):
            raise ValueError('Reconstruction source or objective differs')
        seen = set()
        for row in artifact['rows']:
            key = row['condition'], row['family']
            if key in seen or key[0] not in known or key[1] not in FAMILIES:
                raise ValueError('Duplicate or foreign reconstruction row')
            seen.add(key)
            if not 0 <= row['scored_site_count'] <= row['full_site_count']:
                raise ValueError('Invalid reconstruction coverage')
            for field in ('mean_fve', 'median_fve'):
                value = row[field]
                if value is not None and (isinstance(value, bool) or not math.isfinite(value)):
                    raise ValueError('Invalid reconstruction score')
            for paired in row.get('parent_comparisons', []):
                if paired['reference'] not in known:
                    raise ValueError('Foreign reconstruction reference')
    elif kind == 'effort':
        if set(artifact['method_effort']) != known or artifact.get('status') not in {'partial_retrospective', 'complete_retrospective'}:
            raise ValueError('Effort artifact uses another finite method menu')
    else:
        raise ValueError('Unknown optional artifact')
    return artifact, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=Path('configs/expansion_manifest_v1.json'))
    parser.add_argument('--original-whole', type=Path, default=Path('${OLENS_DATA_ROOT}/runs/whole-cohort-descriptive-v1.json'))
    parser.add_argument('--original-report', type=Path, default=Path('dashboard/report.json'))
    parser.add_argument('--results', type=Path)
    parser.add_argument('--review', type=Path,
                        help='Optional root-reviewed prose bound to the exact result hash')
    parser.add_argument('--reconstruction', type=Path, help='Root-bound secondary per-site fit diagnostics')
    parser.add_argument('--effort', type=Path, help='Root-bound retrospective resource accounting')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inventory, inventory_sha = read(args.inventory)
    whole, whole_sha = read(args.original_whole)
    report, report_sha = read(args.original_report)
    if inventory['status'] != 'sealed' or whole['status'] != 'complete_descriptive_whole_cohort':
        raise ValueError('Unsealed menu or incomplete original whole-bank source')
    rows = [row for row in inventory['conditions'] if row['status'] in ACTIVE]
    known = {row['condition_id'] for row in rows}
    cohorts = {'full': {'label': 'All 469 questions', 'scope': 'Original complete question grids; exploratory',
                         'rows': [], 'comparisons': whole['paired_comparisons'], 'lengths': whole['lengths']},
               'test': {'label': 'Original test subset', 'scope': 'Original frozen comparison, 268 questions', 'rows': []},
               'development': {'label': 'Original development', 'scope': '121 questions, complete grids', 'rows': []},
               'pilot': {'label': 'Small pilot: per activation', 'scope': '31 questions, 189 selected activations; diagnostic only', 'rows': []}}
    for arm in whole['conditions']:
        for family in FAMILIES:
            cohorts['full']['rows'].append({'condition': arm['condition'], 'family': family,
                                            'metric': arm['families'][family][ENDPOINTS[family]]})
    test = report['signed_comparisons']['test']
    cohorts['test']['rows'] = test['original_item_rows']
    cohorts['test']['comparisons'] = test['paired_rows']
    for arm in report['development_scaling']['measurement']['conditions']:
        for family in FAMILIES:
            metric = arm['families'][family]['original_grid_metrics'][ENDPOINTS[family]]
            cohorts['development']['rows'].append({'condition': arm['condition'], 'family': family, 'metric': metric})
    pilot_seen = set()
    for method in report['methods'].values():
        for metric in method['metrics']:
            family = metric['family']
            if (metric.get('scope') != 'partial_grid_cell_diagnostic' or family not in FAMILIES
                    or metric['condition'] not in known):
                continue
            if family == 'hallucination':
                if not metric['endpoint'].startswith('Transcript contradictions'): continue
            elif metric['endpoint'] != 'Cell mention/binding recovery':
                continue
            key = (family, metric['condition'])
            if key in pilot_seen: continue
            pilot_seen.add(key)
            cohorts['pilot']['rows'].append({'condition': key[1], 'family': family,
                'metric': {'value': metric['value'], 'numerator': metric['numerator'],
                           'denominator': metric['denominator'], 'ci95': metric.get('ci'),
                           'uncertainty': metric.get('uncertainty')}})
    extra = None
    extra_sha = None
    if args.results:
        extra, extra_sha = read(args.results)
        if extra['manifest_sha256'] != inventory_sha:
            raise ValueError('Expanded results belong to another sealed menu')
        for cohort, body in extra['cohorts'].items():
            if cohort not in cohorts: raise ValueError('Unknown cohort')
            # A newly finished family augments the preserved original results.
            # It must not erase complete old results from other families.
            previous = cohorts[cohort]
            merged_rows = {(row['condition'], row['family']): row for row in previous['rows']}
            merged_rows.update({(row['condition'], row['family']): row for row in body.get('rows', [])})
            def contrast_key(row):
                scope = row.get('scope')
                if scope in (None, 'original_item', 'original_grid'):
                    scope = 'native_grid'
                return (row['family'], row['condition'],
                        row.get('reference', row.get('baseline_condition')), scope)
            merged_comparisons = {contrast_key(row): row for row in previous.get('comparisons', [])}
            merged_comparisons.update({contrast_key(row): row for row in body.get('comparisons', [])})
            merged_lengths = dict(previous.get('lengths', {}))
            for condition, lengths in body.get('lengths', {}).items():
                merged_lengths[condition] = {**merged_lengths.get(condition, {}), **lengths}
            previous.update(body)
            previous.update(rows=list(merged_rows.values()), comparisons=list(merged_comparisons.values()),
                            lengths=merged_lengths)
            if body.get('rows') and cohort == 'test':
                previous['scope'] = 'Original test subset, 268 questions; expanded comparisons are exploratory'
    for cohort in cohorts.values():
        seen = set()
        for row in cohort['rows']:
            key = (row['condition'], row['family'])
            if key in seen or key[0] not in known or key[1] not in FAMILIES:
                raise ValueError('Duplicate or foreign metric row')
            seen.add(key)
            metric = row['metric']
            if metric['value'] is not None and not 0 <= metric['value'] <= 1:
                raise ValueError('Invalid measured rate')
    reviewed, review_sha = checked_review(args.review, inventory_sha, extra_sha, known)
    reconstruction, reconstruction_sha = checked_artifact(args.reconstruction, 'reconstruction', reviewed, inventory, inventory_sha, extra_sha, known)
    resource, resource_sha = checked_artifact(args.effort, 'effort', reviewed, inventory, inventory_sha, extra_sha, known)
    build_utc = datetime.now(timezone.utc).isoformat()
    data = {'updated_utc': extra.get('updated_utc', build_utc) if extra else build_utc,
            'build_utc': build_utc, 'manifest_sha256': inventory_sha,
            'source_hashes': {'original_whole': whole_sha, 'original_report': report_sha},
            'status': extra.get('status', 'running') if extra else 'running',
            'conditions': [{**{key: row[key] for key in ('condition_id', 'method', 'n', 'parent_condition_ids', 'thresholds')},
                            'label': label(row), 'group': category(row['method'])} for row in rows],
            'cohorts': cohorts, 'findings': reviewed.get('findings', []),
            'examples': reviewed.get('resolved_examples', {}),
            'method_findings': reviewed.get('method_findings', {}),
            'condition_findings': reviewed.get('condition_findings', {}),
            'effort': reviewed.get('effort', {}),
            'reconstruction': reconstruction,
            'resources': resource,
            'source_limits': extra.get('limits', []) if extra else []}
    if extra:
        data['source_hashes']['expanded_results'] = extra_sha
    if review_sha:
        data['source_hashes']['root_review'] = review_sha
    for kind, digest in [('reconstruction', reconstruction_sha), ('effort', resource_sha)]:
        if digest:
            data['source_hashes'][kind] = digest
    args.output.mkdir(parents=True, exist_ok=True)
    for asset in ('expansion.html', 'expansion.js', 'expansion.css'):
        shutil.copyfile(Path('dashboard')/asset, args.output/('index.html' if asset == 'expansion.html' else asset))
    serialized = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    (args.output/'expansion-data.json').write_text(serialized+'\n')
    page = args.output/'index.html'
    embedded = '<script type="application/json" id="embedded-data">' + serialized.replace('<', '\\u003c') + '</script>'
    page.write_text(page.read_text().replace('<script src="expansion.js">', embedded+'<script src="expansion.js">'))
    print(json.dumps({'output': str(args.output), 'active_conditions': len(rows),
                      'full_bank_measured_cells': len(cohorts['full']['rows']), 'new_api_calls': 0}))


if __name__ == '__main__':
    main()
